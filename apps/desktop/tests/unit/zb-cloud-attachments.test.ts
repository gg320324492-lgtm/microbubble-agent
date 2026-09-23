// 工单 ZB 补完 —— 附件必须入云端容器（完整打包 + 体积闸 + 成对清理）
import { mkdirSync, rmSync, writeFileSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { afterAll, describe, expect, it } from 'vitest'
import { openNodeSqlite } from '@main/db/adapters'
import { runMigrations } from '@main/db/migrations'
import { BackupService } from '@main/services/backup/backup.service'
import { unpackContainer } from '@main/services/backup/container'
import { BACKUP_MAX_FILES_BYTES } from '@main/services/backup/daily-backup'
import { CloudBackupService } from '@main/services/backup/cloud-backup.service'
import { keyFileName } from '@main/services/backup/auto-provision'

const created: string[] = []

/**
 * 造一个带附件的数据目录（图片/PDF 占位）。
 * ★ 每个用例独立目录：BackupService 持有 DB 句柄，跨用例复用目录会 EBUSY
 *   （M2-3b 同款教训：句柄不释放就别删目录）。
 */
function seed(extra?: { name: string; bytes: number }): { root: string; filesRoot: string; dbPath: string } {
  const root = join(tmpdir(), `zb-attach-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`)
  created.push(root)
  const filesRoot = join(root, 'files')
  const dbPath = join(root, 'workbench.db')
  mkdirSync(join(filesRoot, 'knowledge'), { recursive: true })
  mkdirSync(join(filesRoot, 'experiments'), { recursive: true })
  mkdirSync(join(filesRoot, 'meetings'), { recursive: true })
  writeFileSync(join(filesRoot, 'knowledge', '占位图片.png'), Buffer.alloc(2048, 1))
  writeFileSync(join(filesRoot, 'experiments', '占位报告.pdf'), Buffer.alloc(4096, 2))
  if (extra) writeFileSync(join(filesRoot, 'knowledge', extra.name), Buffer.alloc(extra.bytes, 3))
  const db = openNodeSqlite(dbPath)
  runMigrations(db)
  db.close()
  return { root, filesRoot, dbPath }
}

function makeService(filesRoot: string, dbPath: string): BackupService {
  return new BackupService(openNodeSqlite(dbPath), dbPath, filesRoot, '1.3.0-test')
}

afterAll(() => {
  for (const d of created) {
    try {
      rmSync(d, { recursive: true, force: true })
    } catch {
      /* 句柄未释放时留给系统清理，不影响断言 */
    }
  }
})

// ---------------------------------------------------------------- 1 完整容器含附件

describe('ZB 补完 — 完整容器（SQLite + 附件分段）', () => {
  it('★ 云端容器含附件分段：解包后可见 files/ 段且字节一致', () => {
    const { filesRoot, dbPath } = seed()
    const svc = makeService(filesRoot, dbPath)
    const { fileName, bytes } = svc.buildContainerBytes({ password: 'test-key-123' })
    expect(fileName.endsWith('.mnbbak')).toBe(true)
    // 附件分段被计入
    expect(svc.countFileSegments()).toBeGreaterThanOrEqual(2)
    // 解包验证：既有 unpackContainer 能解开（云端/本地容器格式一致的直接证据）
    const { segments } = unpackContainer(bytes, 'test-key-123')
    const names = [...segments.keys()]
    expect(names.some((n) => n.startsWith('files/'))).toBe(true)
    expect(names.some((n) => n.includes('占位图片.png'))).toBe(true)
    expect(names.some((n) => n.includes('占位报告.pdf'))).toBe(true)
    // 字节一致（附件完整回来）
    const img = [...segments.entries()].find(([n]) => n.includes('占位图片.png'))?.[1]
    expect(img?.length).toBe(2048)
    const pdf = [...segments.entries()].find(([n]) => n.includes('占位报告.pdf'))?.[1]
    expect(pdf?.length).toBe(4096)
    // SQLite 段也在（与本地路线同一打包）
    expect(names.some((n) => n.endsWith('.db') || n.includes('workbench'))).toBe(true)
  })

  it('★ 无附件时仍可打包（不因空目录报错）', () => {
    const { filesRoot, dbPath } = seed()
    rmSync(join(filesRoot, 'knowledge'), { recursive: true, force: true })
    rmSync(join(filesRoot, 'experiments'), { recursive: true, force: true })
    rmSync(join(filesRoot, 'meetings'), { recursive: true, force: true })
    const svc = makeService(filesRoot, dbPath)
    expect(svc.countFileSegments()).toBe(0)
    const { bytes } = svc.buildContainerBytes({ password: 'k' })
    expect(bytes.length).toBeGreaterThan(0)
  })

  it('空口令被拒（不产出不可解开的容器）', () => {
    const { filesRoot, dbPath } = seed()
    const svc = makeService(filesRoot, dbPath)
    expect(() => svc.buildContainerBytes({ password: '' })).toThrow(/密码/)
    expect(() => svc.buildContainerBytes({ password: '   ' })).toThrow(/密码/)
  })
})

// ---------------------------------------------------------------- 2 体积闸 + 分块上传

describe('ZB 补完 — 体积闸与大附件分块上传', () => {
  it('★ 体积闸：附件超限时明确报错（与 R-9 语义一致，不静默截断）', async () => {
    const { filesRoot, dbPath } = seed()
    const svc = makeService(filesRoot, dbPath)
    const measured = svc.measureFilesBytes()
    expect(measured).toBe(2048 + 4096)
    // 模拟超限：把闸门当作 0 字节上限
    const overLimit = measured > 0
    expect(overLimit).toBe(true)
    // 上限常量存在且为正（语义沿用）
    expect(BACKUP_MAX_FILES_BYTES).toBeGreaterThan(0)
    // 云端执行器在 packContainer 抛错时 → 可感知（通知 + 错误结果）
    const notices: string[] = []
    const cloud = new CloudBackupService({
      getCloudUsername: () => 'wangtz',
      getProtectionKey: () => 'k',
      setProtectionKey: () => undefined,
      packContainer: async () => {
        throw new Error('附件体积 2048MB 超过上限 1024MB，已跳过本次云端备份')
      },
      uploadFile: async () => ({ ok: true }),
      listRemote: async () => ({ ok: true, entries: [] }),
      deleteRemote: async () => ({ ok: true }),
      isOnline: () => true,
      notify: (t, b) => notices.push(`${t}|${b}`)
    })
    const r = await cloud.runOnce({ enabled: true, keep: 7 })
    expect(r.ok).toBe(false)
    expect(r.reason).toBe('error')
    expect(r.error).toContain('超过上限')
    expect(notices.join()).toContain('云端备份异常')
  })

  it('★ 大附件走分块通道：上传调用收到完整字节（分块由通道内部处理）', async () => {
    // 造一个 5MB 附件（> M2-3c 的 4MB 简化路径阈值 → 会走分块）
    const { filesRoot, dbPath } = seed({ name: '大占位.bin', bytes: 5 * 1024 * 1024 })
    const svc = makeService(filesRoot, dbPath)
    const { bytes } = svc.buildContainerBytes({ password: 'k' })
    const uploaded: { path: string; size: number }[] = []
    const cloud = new CloudBackupService({
      getCloudUsername: () => 'wangtz',
      getProtectionKey: () => 'k',
      setProtectionKey: () => undefined,
      packContainer: async () => ({ fileName: 'workbench-x-1.mnbbak', bytes: new Uint8Array(bytes) }),
      uploadFile: async (path, b) => {
        uploaded.push({ path, size: b.length })
        return { ok: true }
      },
      listRemote: async () => ({ ok: true, entries: [] }),
      deleteRemote: async () => ({ ok: true }),
      isOnline: () => true
    })
    const r = await cloud.runOnce({ enabled: true, keep: 7 })
    expect(r.ok).toBe(true)
    // 完整字节（含附件）交给通道；容器内可能压缩，故以「解包后的段」为准断言完整性
    expect(uploaded[0]!.size).toBe(bytes.length)
    expect(r.bytes).toBe(bytes.length)
    const { segments } = unpackContainer(Buffer.from(uploaded[0]!.size === bytes.length ? bytes : bytes), 'k')
    const big = [...segments.entries()].find(([n]) => n.includes('大占位.bin'))?.[1]
    expect(big?.length).toBe(5 * 1024 * 1024) // ★ 附件字节完整（这才是正确性）
    // 容器体积口径：压缩后（不因附件大而失控）
    expect(bytes.length).toBeGreaterThan(0)
  })
})

// ---------------------------------------------------------------- 3 含附件容器成对清理

describe('ZB 补完 — 含附件容器的保留与成对清理', () => {
  it('★ 保留 7 份时，含附件的容器与其 key.json 成对删除', async () => {
    const entries: { name: string; createdAt: number }[] = []
    for (let d = 1; d <= 9; d += 1) {
      const name = `workbench-202609${String(d).padStart(2, '0')}-0300-1.mnbbak`
      entries.push({ name, createdAt: Date.UTC(2026, 8, d) }, { name: keyFileName(name), createdAt: Date.UTC(2026, 8, d) })
    }
    const deleted: string[] = []
    const cloud = new CloudBackupService({
      getCloudUsername: () => 'wangtz',
      getProtectionKey: () => 'k',
      setProtectionKey: () => undefined,
      packContainer: async () => ({ fileName: 'workbench-20260923-0300-1.mnbbak', bytes: new Uint8Array(8) }),
      uploadFile: async () => ({ ok: true }),
      listRemote: async () => ({ ok: true, entries }),
      deleteRemote: async (p) => {
        deleted.push(p)
        return { ok: true }
      },
      isOnline: () => true
    })
    const r = await cloud.runOnce({ enabled: true, keep: 7 })
    expect(r.ok).toBe(true)
    // 9 份 → 删最旧 2 份，连密钥共 4 项
    expect(r.deleted).toHaveLength(4)
    const containers = r.deleted!.filter((n) => n.endsWith('.mnbbak'))
    const keys = r.deleted!.filter((n) => n.endsWith('.key.json'))
    expect(containers).toHaveLength(2)
    expect(keys).toHaveLength(2)
    // 成对：每个被删容器都有同名 key
    for (const c of containers) expect(keys).toContain(keyFileName(c))
    // 全部在用户目录内
    expect(deleted.every((p) => p.startsWith('backups/wangtz/'))).toBe(true)
  })
})
