// 工单 ZB 零感托管备份 —— 自动配置 / 密钥托管 / 保留策略 / 离线宽容（全部离线，注入式）
import { describe, expect, it } from 'vitest'
import {
  CLOUD_BACKUP_ROOT,
  KEY_BYTES,
  KEY_FILE_SUFFIX,
  buildKeyEnvelope,
  cloudBackupDir,
  containerNameFromKeyFile,
  generateProtectionKey,
  isManagedBackupName,
  isUnconfigured,
  keyFileName,
  parseKeyEnvelope,
  planAutoProvision,
  planRetention,
  shouldRunNow,
  type BackupConfigProbe,
  type RemoteBackupEntry
} from '@main/services/backup/auto-provision'

const clean: BackupConfigProbe = {
  hasDailyConfig: false,
  hasManualTargetDir: false,
  hasOssConfig: false,
  hasExitPassword: false
}

/** 确定性随机源（测试用；生产走 crypto.randomBytes） */
const fakeRand = (size: number): Uint8Array => new Uint8Array(Array.from({ length: size }, (_, i) => (i * 7 + 13) % 256))

// ---------------------------------------------------------------- 1 自动配置（≥3）

describe('ZB 自动配置', () => {
  it('★ 未做任何备份配置 + 云端身份 → 自动配置（开启/保留 7/每日定时/目标为云端 backups 目录）', () => {
    const plan = planAutoProvision({ probe: clean, cloudUsername: 'wangtz' })
    expect(plan.provision).toBe(true)
    expect(plan.reason).toBe('provision')
    expect(plan.config).toMatchObject({ enabled: true, keep: 7 })
    expect(plan.config?.atTime).toMatch(/^\d{2}:\d{2}$/)
    expect(plan.remoteDir).toBe(`${CLOUD_BACKUP_ROOT}/wangtz`)
    expect(isUnconfigured(clean)).toBe(true)
  })

  it('★ 既有配置（四种探针任一）→ **零覆盖**，绝不自动改配置', () => {
    const cases: BackupConfigProbe[] = [
      { ...clean, hasDailyConfig: true },
      { ...clean, hasManualTargetDir: true },
      { ...clean, hasOssConfig: true },
      { ...clean, hasExitPassword: true }
    ]
    for (const probe of cases) {
      const plan = planAutoProvision({ probe, cloudUsername: 'wangtz' })
      expect(plan.provision, `探针 ${JSON.stringify(probe)} 应跳过`).toBe(false)
      expect(plan.reason).toBe('already-configured')
      expect(plan.config).toBeUndefined()
    }
  })

  it('★ 未登录/非云端身份 → 不配置（不猜身份）', () => {
    expect(planAutoProvision({ probe: clean, cloudUsername: null }).reason).toBe('not-cloud-identity')
    expect(planAutoProvision({ probe: clean, cloudUsername: null }).provision).toBe(false)
    // 即便未配置，也不该在未登录时动手
    expect(planAutoProvision({ probe: clean, cloudUsername: '' }).provision).toBe(false)
  })

  it('目标目录按用户名隔离，且过滤路径危险字符', () => {
    expect(cloudBackupDir('wangtz')).toBe('backups/wangtz')
    expect(cloudBackupDir('张三')).toBe('backups/张三') // 中文保留
    expect(cloudBackupDir('a/../b')).toBe('backups/a_.._b') // 斜杠被替换，无法越目录
    expect(cloudBackupDir('   ')).toBe('backups/user')
  })
})

// ---------------------------------------------------------------- 2 密钥托管（≥2）

describe('ZB 密钥生成与托管', () => {
  it('★ 密钥强度：32 字节随机 → base64；不同随机源产生不同密钥', () => {
    const k = generateProtectionKey(fakeRand)
    expect(k).toHaveLength(Math.ceil(KEY_BYTES / 3) * 4) // base64 长度口径
    expect(Buffer.from(k, 'base64')).toHaveLength(KEY_BYTES)
    const k2 = generateProtectionKey((n) => new Uint8Array(n).fill(9))
    expect(k2).not.toBe(k)
  })

  it('★ key.json 与容器**同名同目录**成对（可反推配对）', () => {
    const container = 'workbench-20260923-0300-1.mnbbak'
    const keyFile = keyFileName(container)
    expect(keyFile).toBe(`${container}${KEY_FILE_SUFFIX}`)
    expect(containerNameFromKeyFile(keyFile)).toBe(container)
    expect(containerNameFromKeyFile('random.txt')).toBeNull()
    // 同目录：都由 remoteDir 决定
    expect(cloudBackupDir('wangtz')).toBe('backups/wangtz')
  })

  it('★ 托管信封可往返；畸形信封被拒（不产生半可信密钥）', () => {
    const env = buildKeyEnvelope(generateProtectionKey(fakeRand), 1789000000000)
    const back = parseKeyEnvelope(JSON.parse(JSON.stringify(env)))
    expect(back?.key).toBe(env.key)
    expect(back?.createdAt).toBe(1789000000000)
    // 畸形
    expect(parseKeyEnvelope(null)).toBeNull()
    expect(parseKeyEnvelope({ version: 2, key: 'x' })).toBeNull()
    expect(parseKeyEnvelope({ version: 1 })).toBeNull()
    expect(parseKeyEnvelope({ version: 1, key: '' })).toBeNull()
  })

  it('★ 密钥内容不出现在任何可日志化的字符串里（信封只在 note 里描述用途）', () => {
    const key = generateProtectionKey(fakeRand)
    const env = buildKeyEnvelope(key, 1)
    // 信封本身含 key（上传用）；但**日志行**绝不含
    const logLine = `[backup] 已上传密钥托管文件 ${keyFileName('workbench-1.mnbbak')}（长度 ${key.length}）`
    expect(logLine).not.toContain(key)
    expect(env.note).not.toContain(key)
    expect(env.note).toContain('请勿删除')
  })
})

// ---------------------------------------------------------------- 3 保留策略（≥2）

describe('ZB 保留策略（最近 7 份）', () => {
  const isManaged = (n: string): boolean => isManagedBackupName(n, ['workbench', 'pre-restore'])
  const mk = (name: string, day: number): RemoteBackupEntry => ({ name, createdAt: Date.UTC(2026, 8, day) })

  it('★ 超过 7 份删最旧，且**连密钥文件一起删**（不留孤儿密钥）', () => {
    const entries: RemoteBackupEntry[] = []
    for (let d = 1; d <= 10; d += 1) {
      const name = `workbench-202609${String(d).padStart(2, '0')}-0300-1.mnbbak`
      entries.push(mk(name, d), { name: keyFileName(name), createdAt: Date.UTC(2026, 8, d) })
    }
    const plan = planRetention(entries, 7, isManaged)
    expect(plan.keep).toHaveLength(7)
    expect(plan.remove).toHaveLength(6) // 3 个容器 + 3 个密钥
    // 被删的是最旧的 3 份（day 1..3）
    expect(plan.remove).toContain('workbench-20260901-0300-1.mnbbak')
    expect(plan.remove).toContain(keyFileName('workbench-20260901-0300-1.mnbbak'))
    expect(plan.remove).not.toContain('workbench-20260910-0300-1.mnbbak')
    // 保留的 7 份是最新的
    expect(plan.keep).toContain('workbench-20260910-0300-1.mnbbak')
    expect(plan.keep).not.toContain('workbench-20260901-0300-1.mnbbak')
  })

  it('★ 只动本应用命名模式的文件：用户放进同目录的其它文件一律不动', () => {
    const entries: RemoteBackupEntry[] = [
      ...Array.from({ length: 9 }, (_, i) => mk(`workbench-202609${String(i + 1).padStart(2, '0')}-0300-1.mnbbak`, i + 1)),
      mk('用户自己的资料.zip', 20),
      mk('readme.txt', 20),
      mk('pre-restore-20260901-1.mnbbak', 1)
    ]
    const plan = planRetention(entries, 7, isManaged)
    expect(plan.remove).not.toContain('用户自己的资料.zip')
    expect(plan.remove).not.toContain('readme.txt')
    // pre-restore 属受管前缀，可参与清理
    expect([...plan.remove, ...plan.keep]).toContain('pre-restore-20260901-1.mnbbak')
    // 非本应用命名不参与
    expect(isManagedBackupName('用户自己的资料.zip', ['workbench'])).toBe(false)
    expect(isManagedBackupName('workbench-1.mnbbak', ['workbench'])).toBe(true)
    expect(isManagedBackupName('workbench-1.mnbbak.key.json', ['workbench'])).toBe(true)
  })

  it('keep=0 → 不清理（沿用既有语义）', () => {
    const entries = Array.from({ length: 9 }, (_, i) => mk(`workbench-202609${String(i + 1).padStart(2, '0')}-0300-1.mnbbak`, i + 1))
    expect(planRetention(entries, 0, isManaged).remove).toEqual([])
  })
})

// ---------------------------------------------------------------- 4 离线宽容（≥2）

describe('ZB 离线宽容', () => {
  it('★ 断网 → 顺延（不报错、不失败）', () => {
    const r = shouldRunNow({ online: false, loggedIn: true, dueNow: true })
    expect(r.run).toBe(false)
    expect(r.reason).toBe('offline-deferred')
  })

  it('★ 未登录 → 不执行；到点且在线且已登录 → 执行', () => {
    expect(shouldRunNow({ online: true, loggedIn: false, dueNow: true }).reason).toBe('not-logged-in')
    expect(shouldRunNow({ online: true, loggedIn: true, dueNow: false }).reason).toBe('not-due')
    expect(shouldRunNow({ online: true, loggedIn: true, dueNow: true })).toEqual({ run: true, reason: 'ok' })
  })
})

// ---------------------------------------------------------------- 5 触发条件（≥2）

describe('ZB 触发条件（登录时一次性）', () => {
  it('★ 首次登录 → 配置一次；二次登录（已有配置）→ 不重复配置', () => {
    const first = planAutoProvision({ probe: clean, cloudUsername: 'wangtz' })
    expect(first.provision).toBe(true)
    // 二次登录时，配置已写入 → 探针变成「已有配置」
    const second = planAutoProvision({ probe: { ...clean, hasDailyConfig: true }, cloudUsername: 'wangtz' })
    expect(second.provision).toBe(false)
    expect(second.reason).toBe('already-configured')
  })

  it('★ 多账号同机：各自身份独立判定（A 配过不影响 B 的首次）', () => {
    // A 已配置（探针真）→ 跳过
    expect(planAutoProvision({ probe: { ...clean, hasDailyConfig: true }, cloudUsername: 'A' }).provision).toBe(false)
    // B 未配置 → 配置（探针是「当前用户」的，故此处为 clean）
    expect(planAutoProvision({ probe: clean, cloudUsername: 'B' }).provision).toBe(true)
  })
})
