import dayjs from 'dayjs'

export function formatDate(date) {
  if (!date) return '-'
  return dayjs(date).format('YYYY-MM-DD')
}

export function formatDateTime(date) {
  if (!date) return '-'
  return dayjs(date).format('YYYY-MM-DD HH:mm')
}

export function formatTime(date) {
  if (!date) return '-'
  return dayjs(date).format('HH:mm')
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
