// 备份容器命名（R-9 B）— 单一常量来源，供「生成」与「保留清理」共用。
//
// 为什么必须同源：父项目曾因备份产物命名与扫描/清理规则**模式不匹配**，导致云端备份
// 静默不达（无人发现）。若生成用一套规则、清理用另一套，轻则漏清、重则误删用户文件。
// 因此：命名由本模块唯一定义，createBackup 与保留清理都从这里取。

/** 容器扩展名 */
export const BACKUP_EXT = '.mnbbak'
/** 常规备份前缀（createBackup 未指定 prefix 时的默认值） */
export const BACKUP_DEFAULT_PREFIX = 'workbench'
/** 恢复前安全网前缀（restoreBackup 自动快照用） */
export const BACKUP_SAFETY_PREFIX = 'pre-restore'
/** 应用管理的全部前缀（清理只认这些，绝不误删用户文件） */
export const MANAGED_BACKUP_PREFIXES = [BACKUP_DEFAULT_PREFIX, BACKUP_SAFETY_PREFIX] as const

/** 本地时间戳：YYYYMMDD-HHMMSS（与既有产物格式一致） */
export function backupTimestamp(date: Date): string {
  const p = (n: number): string => String(n).padStart(2, '0')
  return (
    `${date.getFullYear()}${p(date.getMonth() + 1)}${p(date.getDate())}` +
    `-${p(date.getHours())}${p(date.getMinutes())}${p(date.getSeconds())}`
  )
}

/** 生成文件名；seq ≥ 2 时追加 ` (n)`（与既有冲突处理一致） */
export function buildBackupFileName(prefix: string | undefined, date: Date, seq = 1): string {
  const p = (prefix ?? '').trim()
  const base = p ? `${p}-${backupTimestamp(date)}` : `${BACKUP_DEFAULT_PREFIX}-${backupTimestamp(date)}`
  return seq >= 2 ? `${base} (${seq})${BACKUP_EXT}` : `${base}${BACKUP_EXT}`
}

export interface ParsedBackupName {
  /** 前缀（无前缀时为默认前缀） */
  prefix: string
  /** 本地时间戳原文 YYYYMMDD-HHMMSS */
  stamp: string
  /** 冲突序号（无后缀为 1） */
  seq: number
  /** 从时间戳解析出的本地时间（毫秒） */
  at: number
}

/** 解析文件名；不符合本应用命名模式一律返回 null */
export function parseBackupFileName(name: string): ParsedBackupName | null {
  const m = /^(.+)-(\d{8})-(\d{6})(?: \((\d+)\))?\.mnbbak$/.exec(String(name ?? ''))
  if (!m) return null
  const [, prefix, d, t, seqRaw] = m
  const year = Number(d.slice(0, 4))
  const month = Number(d.slice(4, 6))
  const day = Number(d.slice(6, 8))
  const hour = Number(t.slice(0, 2))
  const minute = Number(t.slice(2, 4))
  const second = Number(t.slice(4, 6))
  if (month < 1 || month > 12 || day < 1 || day > 31 || hour > 23 || minute > 59 || second > 59) return null
  const at = new Date(year, month - 1, day, hour, minute, second).getTime()
  if (!Number.isFinite(at)) return null
  return { prefix, stamp: `${d}-${t}`, seq: seqRaw ? Number(seqRaw) : 1, at }
}

/** 是否本应用管理的备份文件（前缀在白名单内且命名可解析） */
export function isManagedBackupName(name: string): boolean {
  const p = parseBackupFileName(name)
  return p !== null && (MANAGED_BACKUP_PREFIXES as readonly string[]).includes(p.prefix)
}

/**
 * 保留策略：同前缀保留最近 N 份，返回应删除的文件名。
 * - keep ≤ 0 → 不清理（返回空数组）
 * - 只考虑**本应用命名模式 + 指定前缀**的文件；其余（用户自己放的文件、其它前缀）一律不动
 * - 排序按解析出的时间戳（而非文件名字符串），冲突序号大者视为更新
 */
export function selectForRetention(
  names: readonly string[],
  opts: { prefix?: string; keep: number }
): string[] {
  const keep = Math.floor(opts.keep)
  if (!Number.isFinite(keep) || keep <= 0) return []
  const prefix = (opts.prefix ?? BACKUP_DEFAULT_PREFIX).trim() || BACKUP_DEFAULT_PREFIX

  const candidates = names
    .map((name) => ({ name, parsed: parseBackupFileName(name) }))
    .filter((x): x is { name: string; parsed: ParsedBackupName } => x.parsed !== null && x.parsed.prefix === prefix)

  candidates.sort((a, b) => b.parsed.at - a.parsed.at || b.parsed.seq - a.parsed.seq)
  return candidates.slice(keep).map((x) => x.name)
}
