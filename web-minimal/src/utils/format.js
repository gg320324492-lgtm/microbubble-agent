import dayjs from 'dayjs'
import relativeTime from 'dayjs/plugin/relativeTime'
import 'dayjs/locale/zh-cn'

dayjs.extend(relativeTime)
dayjs.locale('zh-cn')

/**
 * 格式化日期
 * @param {string|Date} date - 日期
 * @param {string} format - 格式
 * @returns {string}
 */
export const formatDate = (date, format = 'YYYY-MM-DD') => {
  if (!date) return ''
  return dayjs(date).format(format)
}

/**
 * 格式化时间
 * @param {string|Date} date - 日期
 * @returns {string}
 */
export const formatTime = (date) => {
  if (!date) return ''
  return dayjs(date).format('HH:mm')
}

/**
 * 格式化日期时间
 * @param {string|Date} date - 日期
 * @returns {string}
 */
export const formatDateTime = (date) => {
  if (!date) return ''
  return dayjs(date).format('YYYY-MM-DD HH:mm')
}

/**
 * 格式化相对时间
 * @param {string|Date} date - 日期
 * @returns {string}
 */
export const formatRelativeTime = (date) => {
  if (!date) return ''
  return dayjs(date).fromNow()
}

/**
 * 格式化文件大小
 * @param {number} bytes - 字节数
 * @returns {string}
 */
export const formatFileSize = (bytes) => {
  if (bytes === 0) return '0 B'
  const k = 1024
  const sizes = ['B', 'KB', 'MB', 'GB', 'TB']
  const i = Math.floor(Math.log(bytes) / Math.log(k))
  return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i]
}

/**
 * 格式化数字
 * @param {number} num - 数字
 * @returns {string}
 */
export const formatNumber = (num) => {
  if (num === undefined || num === null) return '0'
  return num.toLocaleString()
}

/**
 * 格式化百分比
 * @param {number} value - 值
 * @param {number} total - 总数
 * @returns {string}
 */
export const formatPercentage = (value, total) => {
  if (!total) return '0%'
  return Math.round((value / total) * 100) + '%'
}

/**
 * 格式化时长（秒）
 * @param {number} seconds - 秒数
 * @returns {string}
 */
export const formatDuration = (seconds) => {
  if (!seconds) return '0秒'
  const hours = Math.floor(seconds / 3600)
  const minutes = Math.floor((seconds % 3600) / 60)
  const secs = Math.floor(seconds % 60)

  if (hours > 0) {
    return `${hours}小时${minutes}分钟`
  } else if (minutes > 0) {
    return `${minutes}分钟${secs}秒`
  } else {
    return `${secs}秒`
  }
}

/**
 * 格式化日期为友好的显示
 * @param {string|Date} date - 日期
 * @returns {string}
 */
export const formatFriendlyDate = (date) => {
  if (!date) return ''
  const d = dayjs(date)
  const now = dayjs()
  const diffDays = now.diff(d, 'day')

  if (diffDays === 0) {
    return '今天'
  } else if (diffDays === 1) {
    return '昨天'
  } else if (diffDays === 2) {
    return '前天'
  } else if (diffDays < 7) {
    return `${diffDays}天前`
  } else {
    return d.format('MM月DD日')
  }
}

/**
 * 格式化星期
 * @param {string|Date} date - 日期
 * @returns {string}
 */
export const formatWeekday = (date) => {
  if (!date) return ''
  const weekdays = ['星期日', '星期一', '星期二', '星期三', '星期四', '星期五', '星期六']
  return weekdays[dayjs(date).day()]
}
