import { createApp } from 'vue'
import { createPinia } from 'pinia'
import App from './App.vue'
import { router } from './router'
import { useAuthStore } from './stores/auth'
import { useChatStore } from './stores/chat'
import './styles/research-design-tokens.css'
import './styles/research-global.css'
import './styles/research-motion.css'

const app = createApp(App)
const pinia = createPinia()

app.use(pinia)
app.use(router)

app.mount('#app')

const authStore = useAuthStore()
window.api.session.onSessionExpired(() => {
  // eslint-disable-next-line no-console
  console.warn('[main.ts] session expired broadcast received → /login')
  authStore.clearSession()
  void router.push({ name: 'login' })
})

/**
 * Chat SSE stream listeners (Phase 3-A: StreamContext 携带 sessionId).
 *
 * 全局注册一次 (App 单例).
 */
const chatStore = useChatStore()
window.api.chat.onChunk((ctx, event) => {
  chatStore.handleStreamChunk(ctx, event)
  chatStore.scheduleStreamingContentRender()
})
window.api.chat.onEnd((ctx, payload) => {
  if (payload && payload.ok) {
    chatStore.handleStreamEnd(ctx)
  }
})
window.api.chat.onError((ctx, error) => {
  void ctx
  chatStore.handleStreamError(ctx, error.code ?? 'STREAM_ERROR', error.message ?? '未知错误')
})
