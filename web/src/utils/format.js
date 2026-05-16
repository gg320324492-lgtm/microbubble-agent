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
