/**
 * 详情页「返回」按钮的统一判据 (2026-11-10)。
 *
 * ⛔ 两种旧判据都不成立:
 *   ① `window.history.length > 1` —— SPA 里几乎恒真 (about:blank 也算一条),
 *      新标签页直接打开详情时会把用户弹到空白页, 永远走不到 fallback。
 *   ② `document.referrer` —— 这是**文档级**属性, vue-router 的 pushState
 *      站内导航不会改它 ⇒ 从网盘深层点进文件会被误判成"外部直接打开",
 *      返回时跳回网盘根而不是刚才那个文件夹 (比 ① 更隐蔽)。
 *
 * ✅ 判据 = vue-router 4 在 history.state 里维护的 `back` 字段:
 *    - 站内 push 过来 ⇒ state.back = 上一个 location (非 null) ⇒ router.back()
 *    - 新标签 / 书签 / 外部链接直接打开 ⇒ 初始导航是 replace, state.back = null
 *      ⇒ 用调用方给的 fallback 路由 (明确的一层, 不是"回不了就白屏")
 *
 * 两个来源都查: router.options.history.state (vue-router 内存态) 与
 * window.history.state (同一对象, 刷新后浏览器恢复的那份)。
 */
export function canGoBackInApp(router) {
  const read = (state) => {
    if (!state || typeof state !== 'object' || !('back' in state)) return null
    return state.back != null
  }
  try {
    const v = read(router?.options?.history?.state)
    if (v !== null) return v
  } catch { /* 落到 window 兜底 */ }
  try {
    const v = read(window.history.state)
    if (v !== null) return v
  } catch { /* 无 state 可读 */ }
  return false
}

/**
 * @param {object} router vue-router 实例
 * @param {string} fallback 无站内返回目标时要去的明确路由
 */
export function goBackOr(router, fallback) {
  if (canGoBackInApp(router)) router.back()
  else router.push(fallback)
}
