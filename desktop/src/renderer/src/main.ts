import { createApp } from 'vue'
import { createPinia } from 'pinia'
import App from './App.vue'
import { router } from './router'
import { useAuthStore } from './stores/auth'

const app = createApp(App)
const pinia = createPinia()

app.use(pinia)
// router 必须在 pinia 之后（router.beforeEach 里要 useAuthStore）
app.use(router)

app.mount('#app')

/**
 * main → renderer broadcast: session expired (Phase 2-Impl-1)。
 *
 * 触发场景: 主进程 forceClearOnRefreshFail 后 webContents.send('auth:session-expired')
 *
 * 行为: 强制清空 auth + user store, 跳 /login。
 * 使用 router.push 而非 replace, 让用户按浏览器后退可回到上一页 (但 Pinia 已清, 不影响)。
 */
const authStore = useAuthStore()
window.api.session.onSessionExpired(() => {
  // eslint-disable-next-line no-console
  console.warn('[main.ts] session expired broadcast received → /login')
  authStore.clearSession()
  void router.push({ name: 'login' })
})
