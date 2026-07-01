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
