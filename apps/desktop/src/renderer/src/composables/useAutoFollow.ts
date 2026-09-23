// CU1/CU2 聊天体验：输入框常驻 + 自动滚动跟随（纯逻辑，可离线测）
//
// CU2 的判定必须与 DOM 解耦，否则只能靠真机肉眼看——这里把「该不该跟随」抽成纯函数。
//
// 规则（用户上滚暂停跟随、回底恢复）：
//   · 距底部 ≤ threshold 视为「在底部」→ 继续跟随
//   · 用户上滚超过阈值 → 暂停跟随（不再抢滚动位置）
//   · 用户手动回到底部 → 自动恢复跟随
// 注意：**程序性滚动本身会触发 scroll 事件**，若不区分「用户滚动」与「程序滚动」，
// 会出现「跟随中把自己判定成用户上滚」的死循环。故本模块用 `isProgrammatic` 标记区分。

export interface ScrollMetrics {
  scrollTop: number
  clientHeight: number
  scrollHeight: number
}

/** 跟随判定的默认阈值（px）：距底 48px 内算「在底部」 */
export const FOLLOW_THRESHOLD = 48

/** 距底部距离（负数（内容不足一屏）归一为 0） */
export function distanceFromBottom(m: ScrollMetrics): number {
  const d = m.scrollHeight - m.scrollTop - m.clientHeight
  return d > 0 ? d : 0
}

/** 是否处于「贴底」状态 */
export function isAtBottom(m: ScrollMetrics, threshold: number = FOLLOW_THRESHOLD): boolean {
  return distanceFromBottom(m) <= threshold
}

/**
 * 由一次滚动事件推导「此后是否继续跟随」。
 * @param wasFollowing 本次滚动前的跟随状态
 * @param programmatic 本次滚动是否由程序触发（自动滚动）
 */
export function nextFollowing(
  m: ScrollMetrics,
  wasFollowing: boolean,
  programmatic: boolean,
  threshold: number = FOLLOW_THRESHOLD
): boolean {
  // 程序性滚动不改变跟随意图（否则会自锁）
  if (programmatic) return wasFollowing
  // 用户滚动：贴底 → 恢复跟随；离开底部 → 暂停
  return isAtBottom(m, threshold)
}

/** 目标滚动位置：直接到底（新消息/流式输出时用） */
export function bottomScrollTop(m: Pick<ScrollMetrics, 'scrollHeight'>): number {
  return m.scrollHeight
}

/** 内容增长后是否应把视图拉到底 */
export function shouldScrollOnGrow(following: boolean): boolean {
  return following
}

/**
 * 新消息到达时的跟随决策（含「用户刚上滚」的保护）：
 * 只有处于跟随时才滚动，绝不打断用户回看历史。
 */
export function followOnNewMessage(following: boolean): boolean {
  return following
}
