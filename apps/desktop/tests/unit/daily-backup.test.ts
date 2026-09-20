// R-9 B 每日定时备份 — 命名同源 + 节拍决策 + 保留清理 + 体积闸（全部离线纯函数）
import { describe, expect, it } from 'vitest'
import {
  BACKUP_DEFAULT_PREFIX,
  BACKUP_EXT,
  BACKUP_SAFETY_PREFIX,
  buildBackupFileName,
  backupTimestamp,
  isManagedBackupName,
  parseBackupFileName,
  selectForRetention
} from '@shared/backup-naming'
import {
  BACKUP_MAX_FILES_BYTES,
  DEFAULT_DAILY_BACKUP_CONFIG,
  FIXED_TIME_GRACE_MS,
  assertFilesSizeWithinLimit,
  decideDailyBackup,
  localDateKey,
  normalizeDailyBackupConfig,
  parseClock
} from '@main/services/backup/daily-backup'

const at = (y: number, mo: number, d: number, h = 0, mi = 0, s = 0): number => new Date(y, mo - 1, d, h, mi, s).getTime()

describe('命名同源 — 生成与解析必须互逆（父项目「命名/清理不匹配」教训）', () => {
  it('buildBackupFileName 生成既有格式；parse 能原样解析回来', () => {
    const d = new Date(2026, 8, 20, 3, 4, 5)
    const name = buildBackupFileName(undefined, d)
    expect(name).toBe(`workbench-20260920-030405${BACKUP_EXT}`)
    const p = parseBackupFileName(name)
    expect(p?.prefix).toBe(BACKUP_DEFAULT_PREFIX)
    expect(p?.stamp).toBe('20260920-030405')
    expect(p?.seq).toBe(1)
    expect(p?.at).toBe(d.getTime())
  })

  it('冲突序号 (n) 与自定义前缀都能往返', () => {
    const d = new Date(2026, 8, 20, 3, 4, 5)
    expect(buildBackupFileName(undefined, d, 2)).toBe(`workbench-20260920-030405 (2)${BACKUP_EXT}`)
    expect(parseBackupFileName(`workbench-20260920-030405 (2)${BACKUP_EXT}`)?.seq).toBe(2)
    const safety = buildBackupFileName(BACKUP_SAFETY_PREFIX, d)
    expect(safety).toBe(`pre-restore-20260920-030405${BACKUP_EXT}`)
    expect(parseBackupFileName(safety)?.prefix).toBe(BACKUP_SAFETY_PREFIX)
  })

  it('非本应用命名模式一律解析失败（不误伤用户文件）', () => {
    for (const bad of [
      'workbench.mnbbak',
      'workbench-2026092-030405.mnbbak',
      'workbench-20260920-0304.mnbbak',
      'workbench-20261320-030405.mnbbak', // 13 月
      'workbench-20260920-990405.mnbbak', // 99 时
      'notes.txt',
      'mybackup-20260920-030405.mnbbak.zip',
      ''
    ]) {
      expect(parseBackupFileName(bad), bad).toBeNull()
      expect(isManagedBackupName(bad), bad).toBe(false)
    }
  })

  it('backupTimestamp 补零正确', () => {
    expect(backupTimestamp(new Date(2026, 0, 2, 3, 4, 5))).toBe('20260102-030405')
  })
})

describe('保留策略 — 只删本应用命名模式的同前缀文件', () => {
  const names = [
    'workbench-20260901-000000.mnbbak',
    'workbench-20260902-000000.mnbbak',
    'workbench-20260903-000000.mnbbak',
    'workbench-20260904-000000.mnbbak',
    'pre-restore-20260905-000000.mnbbak', // 其它前缀 → 不动
    '用户自己放的文件.txt', // 非本应用模式 → 不动
    'mybackup-20260906-000000.mnbbak' // 非白名单前缀 → 不动
  ]

  it('keep=2 → 只删最旧的 2 份 workbench-*，其它前缀与用户文件一律保留', () => {
    const doomed = selectForRetention(names, { keep: 2 })
    expect(doomed.sort()).toEqual(['workbench-20260901-000000.mnbbak', 'workbench-20260902-000000.mnbbak'])
  })

  it('keep=0 或负数 → 不清理（返回空）', () => {
    expect(selectForRetention(names, { keep: 0 })).toEqual([])
    expect(selectForRetention(names, { keep: -3 })).toEqual([])
  })

  it('份数不足时不删；排序按解析时间而非字符串', () => {
    expect(selectForRetention(names, { keep: 10 })).toEqual([])
    const shuffled = ['workbench-20260903-000000.mnbbak', 'workbench-20260901-000000.mnbbak', 'workbench-20260902-000000.mnbbak']
    // 返回顺序为「较新 → 较旧」（与排序一致），断言时按集合比较更稳
    expect(selectForRetention(shuffled, { keep: 1 }).sort()).toEqual([
      'workbench-20260901-000000.mnbbak',
      'workbench-20260902-000000.mnbbak'
    ])
  })

  it('可指定其它前缀（如安全网）单独清理', () => {
    expect(selectForRetention(names, { prefix: BACKUP_SAFETY_PREFIX, keep: 0 })).toEqual([])
    expect(selectForRetention(names, { prefix: BACKUP_SAFETY_PREFIX, keep: 1 })).toEqual([])
  })
})

describe('节拍决策 — 首启延迟 / 固定时刻 / 错过不补跑', () => {
  const base = { ...DEFAULT_DAILY_BACKUP_CONFIG, enabled: true }

  it('未启用 → 永不触发', () => {
    const r = decideDailyBackup({ config: { ...base, enabled: false }, sessionStartedAt: at(2026, 9, 20, 9), lastRunDate: null, now: at(2026, 9, 20, 23) })
    expect(r.due).toBe(false)
    expect(r.reason).toBe('disabled')
  })

  it('当天已跑过 → 不再触发', () => {
    const r = decideDailyBackup({ config: base, sessionStartedAt: at(2026, 9, 20, 9), lastRunDate: '2026-09-20', now: at(2026, 9, 20, 23) })
    expect(r.due).toBe(false)
    expect(r.reason).toBe('already-ran-today')
  })

  it('first-launch：未到延迟 → 不触发；到点 → 触发', () => {
    const start = at(2026, 9, 20, 9, 0, 0)
    const notYet = decideDailyBackup({ config: base, sessionStartedAt: start, lastRunDate: null, now: at(2026, 9, 20, 9, 9, 59) })
    expect(notYet.due).toBe(false)
    expect(notYet.reason).toBe('waiting-delay')
    expect(notYet.dueAt).toBe(start + 10 * 60 * 1000)

    const due = decideDailyBackup({ config: base, sessionStartedAt: start, lastRunDate: null, now: at(2026, 9, 20, 9, 10, 0) })
    expect(due.due).toBe(true)
    expect(due.reason).toBe('first-launch-due')
  })

  it('first-launch：延迟为 0 时启动即可跑', () => {
    const start = at(2026, 9, 20, 9, 0, 0)
    expect(decideDailyBackup({ config: { ...base, delayMinutes: 0 }, sessionStartedAt: start, lastRunDate: null, now: start }).due).toBe(true)
  })

  it('fixed-time：到点触发；未到不触发', () => {
    const cfg = { ...base, mode: 'fixed-time' as const, atTime: '03:00' }
    expect(decideDailyBackup({ config: cfg, sessionStartedAt: at(2026, 9, 20, 0), lastRunDate: null, now: at(2026, 9, 20, 2, 59) }).reason).toBe('before-time')
    const r = decideDailyBackup({ config: cfg, sessionStartedAt: at(2026, 9, 20, 0), lastRunDate: null, now: at(2026, 9, 20, 3, 0, 30) })
    expect(r.due).toBe(true)
    expect(r.reason).toBe('fixed-time-due')
  })

  it('fixed-time：**错过不补跑**（超出宽容窗口即当天不再触发）', () => {
    const cfg = { ...base, mode: 'fixed-time' as const, atTime: '03:00' }
    const late = decideDailyBackup({
      config: cfg,
      sessionStartedAt: at(2026, 9, 20, 9),
      lastRunDate: null,
      now: at(2026, 9, 20, 9, 0) // 启动时已过 03:00 六小时
    })
    expect(late.due).toBe(false)
    expect(late.reason).toBe('missed-no-catchup')
    // 边界：恰在宽容窗口内仍触发
    const edge = decideDailyBackup({
      config: cfg,
      sessionStartedAt: at(2026, 9, 20, 0),
      lastRunDate: null,
      now: at(2026, 9, 20, 3, 0) + FIXED_TIME_GRACE_MS
    })
    expect(edge.due).toBe(true)
  })
})

describe('配置归一化与工具函数', () => {
  it('非法/缺失字段回退默认（坏配置不能把定时器打死）', () => {
    expect(normalizeDailyBackupConfig(null)).toEqual(DEFAULT_DAILY_BACKUP_CONFIG)
    expect(normalizeDailyBackupConfig({ enabled: 'yes', delayMinutes: -5, keep: -1, atTime: '99:99' })).toEqual(DEFAULT_DAILY_BACKUP_CONFIG)
    const ok = normalizeDailyBackupConfig({ enabled: true, mode: 'fixed-time', delayMinutes: 30, atTime: '23:59', keep: 0 })
    expect(ok).toEqual({ enabled: true, mode: 'fixed-time', delayMinutes: 30, atTime: '23:59', keep: 0 })
  })

  it('parseClock 解析与回退', () => {
    expect(parseClock('03:05')).toEqual({ hour: 3, minute: 5 })
    expect(parseClock('3:5')).toEqual({ hour: 3, minute: 5 })
    expect(parseClock('bad')).toEqual({ hour: 3, minute: 0 })
    expect(parseClock('25:00')).toEqual({ hour: 3, minute: 0 })
  })

  it('localDateKey 用本地时区（不用 UTC，避免跨时区错一天）', () => {
    expect(localDateKey(at(2026, 9, 20, 0, 0, 1))).toBe('2026-09-20')
    expect(localDateKey(at(2026, 9, 20, 23, 59, 59))).toBe('2026-09-20')
  })

  it('体积闸：超阈值明确失败并给出可读原因', () => {
    expect(assertFilesSizeWithinLimit(0).ok).toBe(true)
    expect(assertFilesSizeWithinLimit(BACKUP_MAX_FILES_BYTES).ok).toBe(true)
    const over = assertFilesSizeWithinLimit(BACKUP_MAX_FILES_BYTES + 1)
    expect(over.ok).toBe(false)
    expect(over.reason).toContain('超过上限')
    expect(assertFilesSizeWithinLimit(Number.NaN).ok).toBe(false)
    expect(assertFilesSizeWithinLimit(-1).ok).toBe(false)
  })
})
