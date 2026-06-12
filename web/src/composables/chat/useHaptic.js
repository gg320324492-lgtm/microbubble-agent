/**
 * useHaptic.js — 触觉反馈（navigator.vibrate）
 *
 * PR #3: MobileChatView 长按气泡时触发轻微震动
 *
 * 用法：
 *   const { tap, success, warning, error } = useHaptic()
 *   tap()  // 短促轻敲 10ms
 *   success() // 成功反馈 [10, 50, 10]
 */

export function useHaptic() {
  function vibrate(pattern) {
    if (typeof navigator === 'undefined' || !navigator.vibrate) return
    try {
      navigator.vibrate(pattern)
    } catch {
      // iOS Safari 在用户没有交互前会 throw，忽略
    }
  }

  return {
    /** 短促轻敲（点击反馈） */
    tap: () => vibrate(10),
    /** 成功反馈 */
    success: () => vibrate([10, 50, 10]),
    /** 警告反馈 */
    warning: () => vibrate([30, 50, 30]),
    /** 错误反馈 */
    error: () => vibrate([50, 100, 50]),
    /** 自定义 pattern */
    vibrate,
  }
}

export default useHaptic