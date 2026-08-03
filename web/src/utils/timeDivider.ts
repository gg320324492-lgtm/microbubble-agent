/**
 * W100 +55c: 时间分隔符三档格式化
 *
 * 1) 同一天 (与 now 对比) → "今天 HH:MM"
 * 2) 昨天 → "昨天 HH:MM"
 * 3) 更早 → "YYYY-MM-DD" (toLocaleDateString zh-CN)
 *
 * 与原 toLocaleTimeString 单档显示对比, 长会话跨天时无需推断具体日期.
 * 用途: ChatViewSSE + ChatMessageRow 时间分隔符.
 *
 * 测试: web/src/utils/__tests__/timeDivider.test.ts (3 case)
 */

export function formatTimeDivider(date: Date, now: Date = new Date()): string {
  const sameDay = date.toDateString() === now.toDateString()
  const yesterday = new Date(now)
  yesterday.setDate(now.getDate() - 1)
  const isYesterday = date.toDateString() === yesterday.toDateString()
  const hm = date.toLocaleTimeString('zh-CN', {
    hour: '2-digit',
    minute: '2-digit',
  })
  if (sameDay) return `今天 ${hm}`
  if (isYesterday) return `昨天 ${hm}`
  return date.toLocaleDateString('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
  })
}
