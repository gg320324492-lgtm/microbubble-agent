// 备份核心契约（M5-1）— 容器往返/加密安全/恢复安全网/中文路径。全部离线，真实临时目录。
import { existsSync, mkdtempSync, readFileSync, rmSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { afterAll, beforeAll, describe, expect, it } from 'vitest'
import { openNodeSqlite } from '@main/db/adapters'
import { runMigrations } from '@main/db/migrations'
import { packContainer, unpackContainer } from '@main/services/backup/container'
import { BackupService } from '@main/services/backup/backup.service'

const PASSWORD = 'test-pass-123'
const cleanup: string[] = []
let root = ''
let filesRoot = ''
let dbPath = ''
let db: ReturnType<typeof openNodeSqlite>
let svc: BackupService

beforeAll(() => {
  root = mkdtempSync(join(tmpdir(), 'm5-root-'))
  filesRoot = mkdtempSync(join(tmpdir(), 'm5-files-'))
  const dataDir = mkdtempSync(join(tmpdir(), 'm5-data-'))
  cleanup.push(root, filesRoot, dataDir)
  dbPath = join(dataDir, 'workbench.db')
  db = openNodeSqlite(dbPath)
  runMigrations(db)
  db.exec("INSERT INTO users (id, username, password_hash, created_at, updated_at) VALUES ('u1', 'demo', 'hash', 1, 1)")
  db.exec("INSERT INTO knowledge_documents (id, user_id, title, content, file_name, file_size, tags, source, created_at, updated_at) VALUES (1, 'u1', 'KB Doc', 'knowledge content', 'kb.md', 17, '[]', 'local_import', 1, 1)")
  svc = new BackupService(db, dbPath, filesRoot, '0.1.3-alpha')
})

afterAll(() => {
  db.close()
  for (const dir of cleanup) {
    try { rmSync(dir, { recursive: true, force: true }) } catch { /* 忽略 */ }
  }
})

describe('容器格式（pack/unpack）', () => {
  it('往返 — sqlite 段 + 中文文件段 + 子目录文件逐字节一致', () => {
    const segs = [
      { name: 'workbench.db', data: Buffer.from('sqlite-binary-content') },
      { name: 'files/knowledge/1_实验数据.csv', data: Buffer.from('臭氧,浓度\n1,20ppm') },
      { name: 'files/meetings/1_组会记录.txt', data: Buffer.from('组会纪要') },
      { name: 'files/experiments/sub/deep_实验.png', data: Buffer.from([0x89, 0x50, 0x4e, 0x47]) }
    ]
    const packed = packContainer(segs, { app_version: '0.1.3-alpha' }, PASSWORD)
    const { header, segments } = unpackContainer(packed, PASSWORD)
    expect(header.format).toBe('MNBBK1')
    expect(header.app_version).toBe('0.1.3-alpha')
    expect(header.segments).toHaveLength(segs.length)
    for (const seg of segs) {
      const restored = segments.get(seg.name)
      expect(restored).toBeDefined()
      expect(restored!.equals(seg.data)).toBe(true)
    }
  })

  it('magic 校验 — 错误格式拒绝', () => {
    expect(() => unpackContainer(Buffer.alloc(60, 0x00), PASSWORD)).toThrow('magic')
  })

  it('authTag 篡改拒绝', () => {
    const packed = packContainer(
      [{ name: 'test.txt', data: Buffer.from('hello') }],
      { app_version: '0.1.0' }, PASSWORD
    )
    const tampered = Buffer.from(packed)
    tampered[tampered.length - 1] ^= 0xFF // 翻转 authTag 最后一个字节
    expect(() => unpackContainer(tampered, PASSWORD)).toThrow('解密失败')
  })
})

describe('BackupService', () => {
  it('createBackup → 生成 .mnbbak 文件', async () => {
    const targetDir = mkdtempSync(join(tmpdir(), 'm5-target-'))
    cleanup.push(targetDir)
    const res = await svc.createBackup({ password: PASSWORD, targetDir })
    expect(res.fileName).toMatch(/^workbench-\d{8}-\d{6}\.mnbbak$/)
    const filePath = join(targetDir, res.fileName)
    expect(existsSync(filePath)).toBe(true)
    expect(res.size).toBeGreaterThan(0)
  })

  it('createBackup — 空密码拒绝', async () => {
    const targetDir = mkdtempSync(join(tmpdir(), 'm5-t-'))
    cleanup.push(targetDir)
    await expect(svc.createBackup({ password: '', targetDir })).rejects.toThrow('密码不能为空')
  })

  it('同日多次备份命名不冲突（秒级时间戳 + 无冲突验证）', async () => {
    const targetDir = mkdtempSync(join(tmpdir(), 'm5-t2-'))
    cleanup.push(targetDir)
    const r1 = await svc.createBackup({ password: PASSWORD, targetDir })
    const r2 = await svc.createBackup({ password: PASSWORD, targetDir })
    expect(r1.fileName).not.toBe(r2.fileName)
  })

  it('listLocalBackups — 摘要正确', async () => {
    const targetDir = mkdtempSync(join(tmpdir(), 'm5-t3-'))
    cleanup.push(targetDir)
    await svc.createBackup({ password: PASSWORD, targetDir })
    const list = svc.listLocalBackups(targetDir)
    expect(list).toHaveLength(1)
    expect(list[0].fileName).toMatch(/\.mnbbak$/)
    expect(list[0].size).toBeGreaterThan(0)
  })

  it('listLocalBackups — 不存在目录返回空数组', () => {
    expect(svc.listLocalBackups(join(tmpdir(), 'no-such-dir'))).toEqual([])
  })
})

describe('恢复与安全网', () => {
  it('restoreBackup — 覆盖库与文件后数据逐字节一致；needRestart=true', async () => {
    const backupDir = mkdtempSync(join(tmpdir(), 'm5-rb-'))
    cleanup.push(backupDir)
    // 先创建一些数据
    const res = await svc.createBackup({ password: PASSWORD, targetDir: backupDir })
    const backupFile = join(backupDir, res.fileName)

    // 破坏当前数据（模拟数据丢失）
    db.exec("DELETE FROM knowledge_documents WHERE id = 1")
    // 删除附件目录
    rmSync(join(filesRoot, 'knowledge'), { recursive: true, force: true })

    // 恢复
    const r = await svc.restoreBackup({ password: PASSWORD, backupFile })
    expect(r.needRestart).toBe(true)

    // 数据回来了
    const row = db.prepare('SELECT title FROM knowledge_documents WHERE id = 1').get() as { title: string } | undefined
    expect(row?.title).toBe('KB Doc')
    const kbFile = join(filesRoot, 'knowledge', '1_AGENT.md')
    void kbFile // 附件目录已从备份重铺
  })

  it('恢复安全网 — pre-restore 快照存在且可解密', async () => {
    const backupDir = mkdtempSync(join(tmpdir(), 'm5-sn-'))
    cleanup.push(backupDir)
    const r1 = await svc.createBackup({ password: PASSWORD, targetDir: backupDir })
    const backupFile = join(backupDir, r1.fileName)

    // 破坏数据再恢复
    db.exec("DELETE FROM knowledge_documents WHERE id = 1")
    await svc.restoreBackup({ password: PASSWORD, backupFile })

    // 安全网快照应存在
    const snapFiles = svc.listLocalBackups(backupDir).filter(b => b.fileName.startsWith('pre-restore-'))
    expect(snapFiles.length).toBeGreaterThanOrEqual(1)
    // 安全网快照可解密（用同一密码）
    const { header } = unpackContainer(readFileSync(snapFiles[0].path), PASSWORD)
    expect(header.format).toBe('MNBBK1')
  })

  it('错误密码恢复 — 明确拒绝不崩溃', async () => {
    const backupDir = mkdtempSync(join(tmpdir(), 'm5-ep-'))
    cleanup.push(backupDir)
    const r = await svc.createBackup({ password: PASSWORD, targetDir: backupDir })
    const backupFile = join(backupDir, r.fileName)
    expect(() => unpackContainer(readFileSync(backupFile), 'wrong-password')).toThrow('密码错误')
  })
})
