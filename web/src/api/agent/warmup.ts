/**
 * 聊天模型预热 (2026-09-18 冷加载防御)
 *
 * 背景: 本地 ollama 模型闲置 OLLAMA_KEEP_ALIVE(10m) 后自动卸载, 首条消息要等
 * GPU 冷加载 (~100s), 期间 SSE 长时间静默容易被链路掐断 (ERR_CONNECTION_CLOSED
 * 事故). 聊天页挂载时 fire-and-forget 调一次 POST /api/v1/chat/warmup,
 * 用户打字的窗口正好覆盖模型加载.
 *
 * 后端语义: 幂等 (已驻留→ready / 预热中→warming / 探测失败→unavailable),
 * 永不 5xx; 本调用也永不 throw — 预热失败静默, 对话链路由后端首 token
 * 看门狗 + 云端降级兜底 (app/core/llm.py).
 */

let warmedThisPageLoad = false

/** 测试专用: 复位每页一次的去重标记 */
export function resetWarmupForTest(): void {
  warmedThisPageLoad = false
}

export async function warmupChatModel(): Promise<void> {
  if (warmedThisPageLoad) return
  warmedThisPageLoad = true
  try {
    const token = localStorage.getItem('access_token') || ''
    await fetch('/api/v1/chat/warmup', {
      method: 'POST',
      headers: token ? { Authorization: `Bearer ${token}` } : {}
    })
    // 响应内容无需处理: ready/warming/unavailable 都不改变页面行为
  } catch {
    // 网络差 / 未登录等场景静默, 不影响聊天页
  }
}
