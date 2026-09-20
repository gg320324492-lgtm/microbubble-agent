// 每日定时备份 — 节拍决策与体积防护（R-9 B）— 纯函数，零 Electron / 零文件系统依赖。
//
// 语义（工单 B 硬要求）：
//   · 默认「当天首次启动后延迟 N 分钟」执行一次（凌晨用户大概率不在线，故不做固定时刻默认）
//   · 允许改为固定时刻（HH:mm）
//   · **错过不补跑**：固定时刻模式下，若到点时应用未运行（或机器休眠错过），当天不再补，
//     第二天再说。首启延迟模式则只要过了 dueAt 就跑（它本身就是「启动后」语义）
//   · 每天最多一次；仅在「备份密码」已配置时生效（密码判定在服务层）

/** 定时备份节拍模式 */
export type DailyBackupMode = 'first-launch' | 'fixed-time'

export interface DailyBackupConfig {
  enabled: boolean
  mode: DailyBackupMode
  /** first-launch 模式：首启后延迟分钟数（默认 10） */
  delayMinutes: number
  /** fixed-time 模式：本地时刻 HH:mm */
  atTime: string
  /** 保留最近 N 份；0 = 不清理 */
  keep: number
}

export const DEFAULT_DAILY_BACKUP_CONFIG: DailyBackupConfig = {
  enabled: false,
  mode: 'first-launch',
  delayMinutes: 10,
  atTime: '03:00',
  keep: 7
}

/** 固定时刻模式的宽容窗口：超过则视为「错过」不补跑 */
export const FIXED_TIME_GRACE_MS = 5 * 60 * 1000

/** 容器打包体积上限（当前实现为整内存读，超限明确报错并跳过） */
export const BACKUP_MAX_FILES_BYTES = 1024 * 1024 * 1024

/** 本地日期键 YYYY-MM-DD（跨天判定用本地时区，与用户直觉一致） */
export function localDateKey(at: number): string {
  const d = new Date(at)
  const p = (n: number): string => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}`
}

/** 是否为合法 HH:mm（格式 + 时分范围都要过） */
export function isValidClock(atTime: string): boolean {
  const m = /^(\d{1,2}):(\d{1,2})$/.exec(String(atTime ?? '').trim())
  if (!m) return false
  const hour = Number(m[1])
  const minute = Number(m[2])
  return hour <= 23 && minute <= 59
}

/** 解析 HH:mm；非法输入回退到 fallback */
export function parseClock(atTime: string, fallback = '03:00'): { hour: number; minute: number } {
  const m = /^(\d{1,2}):(\d{1,2})$/.exec(String(atTime ?? '').trim())
  if (!m) return parseClock(fallback, '03:00')
  const hour = Number(m[1])
  const minute = Number(m[2])
  if (hour > 23 || minute > 59) return parseClock(fallback, '03:00')
  return { hour, minute }
}

/** 归并用户配置（容错：缺字段/非法值回退默认，避免坏配置把定时器打死） */
export function normalizeDailyBackupConfig(raw: unknown): DailyBackupConfig {
  const o = (raw ?? {}) as Partial<DailyBackupConfig>
  const mode: DailyBackupMode = o.mode === 'fixed-time' ? 'fixed-time' : 'first-launch'
  const delay = Number(o.delayMinutes)
  const keep = Number(o.keep)
  return {
    enabled: o.enabled === true,
    mode,
    delayMinutes: Number.isFinite(delay) && delay >= 0 && delay <= 24 * 60 ? Math.floor(delay) : DEFAULT_DAILY_BACKUP_CONFIG.delayMinutes,
    // 只校验格式会放进 '99:99' 这种值（测试抓到过），必须同时校验时分范围
    atTime: isValidClock(String(o.atTime ?? '')) ? String(o.atTime) : DEFAULT_DAILY_BACKUP_CONFIG.atTime,
    keep: Number.isFinite(keep) && keep >= 0 ? Math.floor(keep) : DEFAULT_DAILY_BACKUP_CONFIG.keep
  }
}

export interface DailyBackupInput {
  config: DailyBackupConfig
  /** 本次会话（应用启动）时刻 */
  sessionStartedAt: number
  /** 上次执行成功的本地日期键；null = 从未 */
  lastRunDate: string | null
  now: number
}

export interface DailyBackupDecision {
  due: boolean
  /** 本次应执行的时刻（未启用/今日已完成时为 null） */
  dueAt: number | null
  reason: string
}

/**
 * 节拍决策（纯函数）——服务层每分钟调用一次。
 * 返回 due=true 时服务层执行备份；执行后写入 lastRunDate 保证当天只跑一次。
 */
export function decideDailyBackup(input: DailyBackupInput): DailyBackupDecision {
  const { config, sessionStartedAt, lastRunDate, now } = input
  if (!config.enabled) return { due: false, dueAt: null, reason: 'disabled' }

  const today = localDateKey(now)
  if (lastRunDate === today) return { due: false, dueAt: null, reason: 'already-ran-today' }

  if (config.mode === 'first-launch') {
    const dueAt = sessionStartedAt + config.delayMinutes * 60 * 1000
    return now >= dueAt
      ? { due: true, dueAt, reason: 'first-launch-due' }
      : { due: false, dueAt, reason: 'waiting-delay' }
  }

  // fixed-time：到点才跑，且**错过不补跑**（超出宽容窗口即视为错过，今天不再触发）
  const { hour, minute } = parseClock(config.atTime)
  const d = new Date(now)
  const dueAt = new Date(d.getFullYear(), d.getMonth(), d.getDate(), hour, minute, 0, 0).getTime()
  if (now < dueAt) return { due: false, dueAt, reason: 'before-time' }
  if (now - dueAt > FIXED_TIME_GRACE_MS) return { due: false, dueAt, reason: 'missed-no-catchup' }
  return { due: true, dueAt, reason: 'fixed-time-due' }
}

/** files 目录体积防护判定（整内存打包前的硬闸） */
export function assertFilesSizeWithinLimit(bytes: number, limit = BACKUP_MAX_FILES_BYTES): { ok: boolean; reason?: string } {
  const n = Number(bytes)
  if (!Number.isFinite(n) || n < 0) return { ok: false, reason: `附件体积测量异常：${bytes}` }
  if (n > limit) {
    return {
      ok: false,
      reason: `附件体积 ${(n / 1024 / 1024 / 1024).toFixed(2)} GB 超过上限 ${(limit / 1024 / 1024 / 1024).toFixed(0)} GB，已跳过本次备份（当前容器为整内存打包，大体积请手工备份或等待后续流式版本）`
    }
  }
  return { ok: true }
}

/** 最近一次定时备份结果（设置页展示 + 失败可感知） */
export interface DailyBackupResult {
  at: number
  ok: boolean
  fileName?: string
  size?: number
  deleted?: number
  error?: string
}
