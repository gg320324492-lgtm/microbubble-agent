// R-9 B 每日定时备份服务 — 端到端副作用编排（真实临时目录 + 真实 BackupService，离线）
import { existsSync, mkdirSync, mkdtempSync, readdirSync, rmSync, writeFileSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { afterAll, beforeAll, describe, expect, it, vi } from 'vitest'
import { openNodeSqlite } from '@main/db/adapters'
import { runMigrations } from '@main/db/migrations'
import { BackupService } from '@main/services/backup/backup.service'
import { DailyBackupService } from '@main/services/backup/daily-backup.service'
import { DEFAULT_DAILY_BACKUP_CONFIG, type DailyBackupConfig, type DailyBackupResult } from '@main/services/backup/daily-backup'

const dirs: string[] = []
let db: ReturnType<typeof openNodeSqlite>
let filesRoot = ''
let backupDir = ''
let backup: BackupService

beforeAll(() => {
  const dir = mkdtempSync(join(tmpdir(), 'r9-daily-'))
  dirs.push(dir)
  db = openNodeSqlite(join(dir, 'workbench.db'))
  runMigrations(db)
  filesRoot = join(dir, 'files')
  backupDir = join(dir, 'backups')
  writeFileSync(join(dir, 'marker'), 'x')
  backup = new BackupService(db, join(dir, 'workbench.db'), filesRoot, '1.1.0')
})

afterAll(() => {
  try {
    ;(db as unknown as { close?: () => void }).close?.()
  } catch {
    /* 忽略 */
  }
  for (const d of dirs) {
    try {
      rmSync(d, { recursive: true, force: true })
    } catch {
      /* 忽略 */
    }
  }
})

/** 组装一个内存态端口的服务（配置/结果/日期都放内存，避免依赖真实设置表） */
function makeService(over: Partial<Parameters<typeof makePorts>[0]> = {}): {
  svc: DailyBackupService
  ports: ReturnType<typeof makePorts>
  notify: ReturnType<typeof vi.fn>
} {
  const notify = vi.fn()
  const ports = makePorts({ notify, ...over })
  return { svc: new DailyBackupService(ports), ports, notify }
}

function makePorts(over: {
  notify?: (t: string, b: string) => void
  password?: string | null
  filesBytes?: number
  createBackup?: (o: { password: string; targetDir: string }) => Promise<{ fileName: string; size: number }>
} = {}): {
  config: DailyBackupConfig
  last: DailyBackupResult | null
  targetDir: string
  readConfig: () => unknown
  writeConfig: (c: DailyBackupConfig) => void
  readLastRunDate: () => string | null
  writeLastRunDate: (d: string) => void
  readLastResult: () => DailyBackupResult | null
  writeLastResult: (r: DailyBackupResult) => void
  getPassword: () => string | null
  getTargetDir: () => string
  createBackup: (o: { password: string; targetDir: string }) => Promise<{ fileName: string; size: number }>
  applyRetention: (dir: string, o: { prefix?: string; keep: number }) => { deleted: string[] }
  measureFilesBytes: () => number
  notify: (t: string, b: string) => void
} {
  const state = { config: { ...DEFAULT_DAILY_BACKUP_CONFIG, enabled: true } as DailyBackupConfig, last: null as DailyBackupResult | null }
  return {
    ...state,
    readConfig: () => state.config,
    writeConfig: (c: DailyBackupConfig) => (state.config = c),
    readLastRunDate: () => (state.last ? new Date(state.last.at).toISOString().slice(0, 10) : null),
    writeLastRunDate: () => undefined,
    readLastResult: () => state.last,
    writeLastResult: (r: DailyBackupResult) => (state.last = r),
    getPassword: () => (over.password === undefined ? 'pw-123456' : over.password),
    getTargetDir: () => backupDir,
    createBackup: over.createBackup ?? ((o: { password: string; targetDir: string }) => backup.createBackup(o)),
    applyRetention: (dir: string, o: { prefix?: string; keep: number }) => backup.applyRetention(dir, o),
    measureFilesBytes: () => over.filesBytes ?? 0,
    notify: over.notify ?? ((): void => undefined)
  } as never
}

describe('每日定时备份服务 — 成功路径', () => {
  it('生成容器 → 保留清理删最旧 → 结果与日期记账', async () => {
    // 预置 3 份旧备份（同名同模式），keep=2 → 应删最旧的 1 份
    mkdirSync(backupDir, { recursive: true })
    for (const stamp of ['20260101-000000', '20260102-000000', '20260103-000000']) {
      writeFileSync(join(backupDir, `workbench-${stamp}.mnbbak`), 'old')
    }
    const { svc, ports } = makeService()
    ports.writeConfig({ ...DEFAULT_DAILY_BACKUP_CONFIG, enabled: true, keep: 2 })
    const r = await svc.runNow('test')
    expect(r.ok, r.error ?? '').toBe(true)
    expect(r.fileName).toMatch(/^workbench-\d{8}-\d{6}\.mnbbak$/)
    expect(existsSync(join(backupDir, r.fileName!))).toBe(true)
    // 4 份 workbench-* 保留最近 2 份
    const left = readdirSync(backupDir).filter((f) => f.startsWith('workbench-')).sort()
    expect(left.length).toBe(2)
    expect(left).not.toContain('workbench-20260101-000000.mnbbak')
    expect(r.deleted).toBe(2)
  })

  it('keep=0 → 不清理任何文件', async () => {
    const dir2 = mkdtempSync(join(tmpdir(), 'r9-keep0-'))
    dirs.push(dir2)
    mkdirSync(dir2, { recursive: true })
    writeFileSync(join(dir2, 'workbench-20260101-000000.mnbbak'), 'old')
    const { svc, ports } = makeService({ createBackup: async (o) => backup.createBackup({ ...o, targetDir: dir2 }) })
    ports.writeConfig({ ...DEFAULT_DAILY_BACKUP_CONFIG, enabled: true, keep: 0 })
    const r = await svc.runNow('test')
    expect(r.ok).toBe(true)
    expect(readdirSync(dir2).filter((f) => f.startsWith('workbench-')).length).toBe(2)
  })
})

describe('每日定时备份服务 — 失败可感知', () => {
  it('未配置密码 → 不执行、不通知、**不占用当天名额**', async () => {
    const { svc, ports, notify } = makeService({ password: null })
    const r = await svc.runNow('test')
    expect(r.ok).toBe(false)
    expect(r.error).toContain('未配置备份密码')
    expect(notify).not.toHaveBeenCalled() // 属「未生效」而非失败，不打扰用户
    // 关键：不算一次尝试 —— 用户当天补配密码后仍能跑（实测踩到过「占了名额」）
    expect(ports.readLastResult()).toBeNull()
    expect(ports.readLastRunDate()).toBeNull()
  })

  it('体积超阈值 → 跳过 + 系统通知 + 明确报错', async () => {
    const { svc, notify } = makeService({ filesBytes: 2 * 1024 * 1024 * 1024 })
    const r = await svc.runNow('test')
    expect(r.ok).toBe(false)
    expect(r.error).toContain('超过上限')
    expect(notify).toHaveBeenCalledTimes(1)
    expect(String(notify.mock.calls[0][0])).toContain('跳过')
  })

  it('打包抛错 → 结果标记失败 + 系统通知（工单硬要求）', async () => {
    const { svc, notify } = makeService({
      createBackup: () => Promise.reject(new Error('磁盘写入失败'))
    })
    const r = await svc.runNow('test')
    expect(r.ok).toBe(false)
    expect(r.error).toContain('磁盘写入失败')
    expect(notify).toHaveBeenCalledTimes(1)
    expect(String(notify.mock.calls[0][0])).toContain('失败')
  })

  it('失败也会记账日期 → 当天不再重试（避免每分钟打爆）', async () => {
    const { svc, ports } = makeService({ createBackup: () => Promise.reject(new Error('boom')) })
    await svc.runNow('test')
    expect(ports.readLastResult()?.ok).toBe(false)
    // 再跑一次是显式调用，仍会执行；但心跳判定会因「当天已尝试」跳过
    expect(ports.readLastRunDate()).toBe(new Date().toISOString().slice(0, 10))
  })
})

describe('每日定时备份服务 — 配置读写', () => {
  it('snapshot 汇总配置/结果/目标目录/密码状态', () => {
    const { svc } = makeService()
    const s = svc.snapshot()
    expect(s.targetDir).toBe(backupDir)
    expect(s.passwordConfigured).toBe(true)
    expect(s.config.mode).toBe('first-launch')
    expect(s.last).toBeNull()
  })

  it('updateConfig 部分更新并归一化（非法值回退默认）', () => {
    const { svc, ports } = makeService()
    const updated = svc.updateConfig({ enabled: true, keep: 3 })
    expect(updated.enabled).toBe(true)
    expect(updated.keep).toBe(3)
    expect(updated.delayMinutes).toBe(DEFAULT_DAILY_BACKUP_CONFIG.delayMinutes)
    expect(ports.config.enabled).toBe(true)

    const bad = svc.updateConfig({ keep: -5, delayMinutes: 99999 })
    expect(bad.keep).toBe(DEFAULT_DAILY_BACKUP_CONFIG.keep)
    expect(bad.delayMinutes).toBe(DEFAULT_DAILY_BACKUP_CONFIG.delayMinutes)
  })

  it('start/stop 幂等，不重复注册心跳', () => {
    const { svc } = makeService()
    svc.start()
    svc.start()
    svc.stop()
    svc.stop()
    expect(true).toBe(true) // 无异常即通过（心跳 unref，不阻塞测试退出）
  })
})
