import { createApp } from 'vue'
import { createPinia } from 'pinia'
import App from './App.vue'
import { router } from './router'
import { useAuthStore } from './stores/auth'
import { useChatStore } from './stores/chat'

const app = createApp(App)
const pinia = createPinia()

app.use(pinia)
// router 必须在 pinia 之后（router.beforeEach 里要 useAuthStore）
app.use(router)

app.mount('#app')

/**
 * main → renderer broadcast: session expired (Phase 2-Impl-1)。
 */
const authStore = useAuthStore()
window.api.session.onSessionExpired(() => {
  // eslint-disable-next-line no-console
  console.warn('[main.ts] session expired broadcast received → /login')
  authStore.clearSession()
  void router.push({ name: 'login' })
})

/**
 * Chat SSE stream listeners (Phase 2-Impl-3B).
 *
 * 全局注册一次 (App 单例):
 *   chunk / end / error 三个事件由 ChatView 触发渲染.
 *   这里只把事件分发给 Pinia store, 让组件保持 dumb.
 */
const chatStore = useChatStore()
window.api.chat.onChunk((streamId, event) => {
  chatStore.handleStreamChunk(streamId, event)
  // 100ms 防抖触发 MarkdownViewer 重渲染
  chatStore.scheduleStreamingContentRender()
})
window.api.chat.onEnd((_streamId, payload) => {
  if (payload && payload.ok) {
    chatStore.handleStreamEnd(_streamId)
  }
})
window.api.chat.onError((streamId, error) => {
  void streamId
  chatStore.handleStreamError(error.code ?? 'STREAM_ERROR', error.message ?? '未知错误')
})
