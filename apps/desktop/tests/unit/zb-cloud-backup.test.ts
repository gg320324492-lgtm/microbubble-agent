// 工单 ZB 云端备份执行器 —— 注入式端到端（零网络零 Electron ABI）
import { describe, expect, it } from 'vitest'
import { CloudBackupService, joinRemote, probeFromSettings } from '@main/services/backup/cloud-backup.service'
import { keyFileName } from '@main/services/backup/auto-provision'

interface Harness {
  svc: CloudBackupService
  uploaded: { path: string; size: number }[]
  deleted: string[]
  keys: string[]
  logs: string[]
  notices: string[]
}

function harness(opts: {
  username?: string | null
  online?: boolean
  existingKey?: string | null
  remoteEntries?: { name: string; createdAt: number }[]
  failUpload?: boolean
} = {}): Harness {
  const uploaded: { path: string; size: number }[] = []
  const deleted: string[] = []
  const keys: string[] = []
  const logs: string[] = []
  const notices: string[] = []
  let key: string | null = opts.existingKey ?? null

  const svc = new CloudBackupService({
    getCloudUsername: () => (opts.username === undefined ? 'wangtz' : opts.username),
    getProtectionKey: () => key,
    setProtectionKey: (k) => {
      key = k
      keys.push(k)
    },
    packContainer: async () => ({ fileName: 'workbench-20260923-0300-1.mnbbak', bytes: new Uint8Array(1024) }),
    uploadFile: async (path, bytes) => {
      if (opts.failUpload) return { ok: false, error: '网络不可用' }
      uploaded.push({ path, size: bytes.length })
      return { ok: true }
    },
    listRemote: async () => ({ ok: true, entries: opts.remoteEntries ?? [] }),
    deleteRemote: async (path) => {
      deleted.push(path)
      return { ok: true }
    },
    isOnline: () => opts.online !== false,
    random: (n) => new Uint8Array(n).fill(7),
    notify: (title, body) => notices.push(`${title}|${body}`),
    log: (m) => logs.push(m)
  })
  return { svc, uploaded, deleted, keys, logs, notices }
}

describe('ZB 云端备份执行器', () => {
  it('★ 一次完整执行：容器 + key.json 成对上传到 backups/<用户>/，并按保留清理', async () => {
    const h = harness({
      remoteEntries: Array.from({ length: 9 }, (_, i) => ({
        name: `workbench-202609${String(i + 1).padStart(2, '0')}-0300-1.mnbbak`,
        createdAt: Date.UTC(2026, 8, i + 1)
      }))
    })
    const r = await h.svc.runOnce({ enabled: true, keep: 7 })
    expect(r.ok).toBe(true)
    expect(r.ran).toBe(true)
    expect(r.container).toBe('workbench-20260923-0300-1.mnbbak')
    expect(r.keyFile).toBe(keyFileName('workbench-20260923-0300-1.mnbbak'))
    // 两个上传都在同一用户目录下（成对、同目录）
    expect(h.uploaded.map((u) => u.path)).toEqual([
      'backups/wangtz/workbench-20260923-0300-1.mnbbak',
      'backups/wangtz/workbench-20260923-0300-1.mnbbak.key.json'
    ])
    // 保留：9 份 → 保留 7，删最旧 2 份 + 其密钥（共 4 项）
    expect(r.deleted).toHaveLength(4)
    expect(r.deleted).toContain('workbench-20260901-0300-1.mnbbak')
    expect(r.deleted).toContain('workbench-20260901-0300-1.mnbbak.key.json')
    expect(h.deleted.every((p) => p.startsWith('backups/wangtz/'))).toBe(true)
  })

  it('★ 保护密钥只生成一次并持久化；二次执行复用同一密钥', async () => {
    const h = harness()
    await h.svc.runOnce({ enabled: true, keep: 7 })
    expect(h.keys).toHaveLength(1)
    await h.svc.runOnce({ enabled: true, keep: 7 })
    expect(h.keys).toHaveLength(1) // 未重复生成
  })

  it('★ 密钥内容绝不出现在日志中（只记长度）', async () => {
    const h = harness()
    await h.svc.runOnce({ enabled: true, keep: 7 })
    const joined = h.logs.join('\n')
    // 密钥内容（base64 of 32×7 字节）
    const leaked = h.keys[0]!
    expect(joined).not.toContain(leaked)
    expect(joined).toContain('内容不入日志')
    // 上传记录里也不含密钥内容（只有路径与大小）
    expect(h.uploaded.every((u) => !u.path.includes(leaked))).toBe(true)
  })

  it('★ 断网：顺延不报错，且**不产生任何上传/删除**', async () => {
    const h = harness({ online: false })
    const r = await h.svc.runOnce({ enabled: true, keep: 7 })
    expect(r.ran).toBe(false)
    expect(r.reason).toBe('offline-deferred')
    expect(r.ok).toBe(true) // 离线不是错误
    expect(h.uploaded).toHaveLength(0)
    expect(h.deleted).toHaveLength(0)
    expect(h.notices).toHaveLength(0) // 不打扰用户
    expect(h.logs.join()).toContain('顺延')
  })

  it('★ 未登录：不执行也不上传（不猜身份）', async () => {
    const h = harness({ username: null })
    const r = await h.svc.runOnce({ enabled: true, keep: 7 })
    expect(r.ran).toBe(false)
    expect(r.reason).toBe('not-logged-in')
    expect(h.uploaded).toHaveLength(0)
  })

  it('★ 未开启：不执行（配置为关时不打扰）', async () => {
    const h = harness()
    const r = await h.svc.runOnce({ enabled: false, keep: 7 })
    expect(r.ran).toBe(false)
    expect(h.uploaded).toHaveLength(0)
  })

  it('★ 上传失败：可感知（系统通知）+ 返回错误，不静默；DL-7 起失败原因落日志', async () => {
    const h = harness({ failUpload: true })
    const r = await h.svc.runOnce({ enabled: true, keep: 7 })
    expect(r.ok).toBe(false)
    expect(r.ran).toBe(true)
    expect(r.reason).toBe('error')
    expect(h.notices.length).toBeGreaterThan(0)
    expect(h.notices.join()).toContain('云端备份失败')
    // DL-7 Part C：notifyFail 必须同步落日志（title+body 与通知一致），主进程 console.log 同路径可取证
    const failLines = h.logs.filter((l) => l.includes('云端备份失败'))
    expect(failLines).toHaveLength(1)
    expect(failLines[0]).toBe('[backup] 云端备份失败：网络不可用')
    // 把将出现在主进程日志里的片段原样打印，供验收报告引用
    console.log('[DL-7 Part C 主进程日志片段]', failLines[0])
  })

  it('★ 列远端失败时跳过清理（不因清理失败而误删）', async () => {
    const h = harness()
    const svc2 = new CloudBackupService({
      getCloudUsername: () => 'wangtz',
      getProtectionKey: () => 'k',
      setProtectionKey: () => undefined,
      packContainer: async () => ({ fileName: 'a.mnbbak', bytes: new Uint8Array(1) }),
      uploadFile: async () => ({ ok: true }),
      listRemote: async () => ({ ok: false, error: 'boom' }),
      deleteRemote: async () => ({ ok: true }),
      isOnline: () => true
    })
    const r = await svc2.runOnce({ enabled: true, keep: 7 })
    expect(r.ok).toBe(true)
    expect(r.deleted).toEqual([])
    void h
  })

  it('远端路径拼接：统一正斜杠且不产生双斜杠', () => {
    expect(joinRemote('backups/wangtz', 'a.mnbbak')).toBe('backups/wangtz/a.mnbbak')
    expect(joinRemote('backups/wangtz/', 'a.mnbbak')).toBe('backups/wangtz/a.mnbbak')
    expect(joinRemote('backups/wangtz//', 'a.mnbbak')).toBe('backups/wangtz/a.mnbbak')
  })

  it('★ 配置探针：任一既有配置即视为「已配置」（零覆盖的前置判定）', () => {
    const none = probeFromSettings(() => undefined)
    expect(none).toEqual({ hasDailyConfig: false, hasManualTargetDir: false, hasOssConfig: false, hasExitPassword: false })
    expect(probeFromSettings((k) => (k === 'backup.daily.config' ? { enabled: true } : undefined)).hasDailyConfig).toBe(true)
    expect(probeFromSettings((k) => (k === 'backup.oss.bucket' ? 'b' : undefined)).hasOssConfig).toBe(true)
    expect(probeFromSettings((k) => (k === 'backup.exitPassword' ? 'x' : undefined)).hasExitPassword).toBe(true)
  })
})

describe('ZB UI 状态行（最小改动）', () => {
  it('★ 状态行含「已自动保护」前缀（开启时），保留份数口径为 n/keep', async () => {
    const { readFileSync } = await import('node:fs')
    const src = readFileSync('src/renderer/src/components/settings/BackupSection.vue', 'utf8')
    expect(src).toContain('已自动保护')
    expect(src).toContain('已保留')
    // 前缀仅在开启时出现（未开启不误导用户以为在自动保护）
    expect(src).toMatch(/daily\.value\.enabled \? '已自动保护 · ' : ''/)
  })
})
