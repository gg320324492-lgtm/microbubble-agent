/**
 * 智能自动滚动
 * - 用户在底部 200px → 自动跟随
 * - 用户向上滚动 → 停止自动滚动，显示"↓ N 条新消息"按钮
 */
import { ref, computed } from 'vue'

export function useAutoScroll(containerRef) {
  const isAtBottom = ref(true)
  const newMessageCount = ref(0)

  function onScroll() {
    if (!containerRef.value) return
    const el = containerRef.value
    const threshold = 200
    isAtBottom.value = el.scrollHeight - el.scrollTop - el.clientHeight < threshold
    if (isAtBottom.value) {
      newMessageCount.value = 0
    }
  }

  function scrollToBottom(smooth = true) {
    if (!containerRef.value) return
    const el = containerRef.value
    el.scrollTo({
      top: el.scrollHeight,
      behavior: smooth ? 'smooth' : 'auto',
    })
    isAtBottom.value = true
    newMessageCount.value = 0
  }

  function notifyNewMessage() {
    if (!isAtBottom.value) {
      newMessageCount.value++
    }
  }

  return {
    isAtBottom,
    newMessageCount,
    onScroll,
    scrollToBottom,
    notifyNewMessage,
  }
}
