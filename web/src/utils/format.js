import dayjs from 'dayjs'

// 数据库存储 UTC 时间，前端统一转北京时间（UTC+8）
const toBeijing = (date) => dayjs(date).add(8, 'hour')

export function formatDate(date) {
  if (!date) return '-'
  return toBeijing(date).format('YYYY-MM-DD')
}

export function formatDateTime(date) {
  if (!date) return '-'
  return toBeijing(date).format('YYYY-MM-DD HH:mm')
}

export function formatTime(date) {
  if (!date) return '-'
  return toBeijing(date).format('HH:mm')
}

export function formatRelativeTime(date) {
  if (!date) return '-'
  const d = dayjs(date)
  const now = dayjs()
  const diffMinutes = now.diff(d, 'minute')
  const diffHours = now.diff(d, 'hour')
  const diffDays = now.diff(d, 'day')

  if (diffMinutes < 1) return '刚刚'
  if (diffMinutes < 60) return `${diffMinutes}分钟前`
  if (diffHours < 24) return `${diffHours}小时前`
  if (diffDays < 7) return `${diffDays}天前`
  return d.format('YYYY-MM-DD')
}

// 文件大小格式化 (B/KB/MB/GB) — MobileVoiceprintsPanel 依赖
export function formatSize(bytes) {
  if (!bytes || bytes <= 0) return '—'
  const units = ['B', 'KB', 'MB', 'GB']
  let i = 0
  let v = bytes
  while (v >= 1024 && i < units.length - 1) {
    v /= 1024
    i += 1
  }
  return `${v.toFixed(1)} ${units[i]}`
}

// 解析后端时间字段为 Date。
// 后端 DateTime 列经 str() 序列化产出 naive UTC 串（"2026-09-12 05:08:12.345"，无时区标记），
// 直接 new Date() 会按浏览器本地时区解读 → 北京时间显示差 8 小时。
// 约定：无时区标记的串一律视为 UTC（与 CommentItem 的 iso+'Z' 同口径）；已带 Z/±hh:mm 的原样解析。
export function parseDbDate(input) {
  if (!input) return null
  if (input instanceof Date) return isNaN(input.getTime()) ? null : input
  if (typeof input === 'number') return new Date(input)
  if (typeof input !== 'string') return null
  const s = input.trim()
  if (!s) return null
  // 微信/部分接口可能产出 6 位微秒，JS 只认毫秒，截到 3 位
  const norm = s.replace(' ', 'T').replace(/\.(\d{3})\d*$/, '.$1')
  if (/Z|[+-]\d{2}:?\d{2}$/i.test(norm)) {
    const d = new Date(norm)
    return isNaN(d.getTime()) ? null : d
  }
  const d = new Date(norm + 'Z')
  return isNaN(d.getTime()) ? null : d
}

// 紧凑日期格式（用于 Dashboard 等空间有限的场景）
export function formatCompactDate(date, emptyText = '无截止日期') {
  if (!date) return emptyText
  const d = dayjs(date)
  const now = dayjs()
  const isSameYear = d.year() === now.year()
  // 有时间信息（非00:00）则显示时间
  if (d.hour() !== 0 || d.minute() !== 0) {
    return isSameYear ? d.format('MM/DD HH:mm') : d.format('YY/MM/DD HH:mm')
  }
  return isSameYear ? d.format('MM/DD') : d.format('YY/MM/DD')
}
