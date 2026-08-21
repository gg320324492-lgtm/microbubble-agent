// renderer 路由表 + auth guard。
//
// 规则（详见 docs/desktop-conversion/plan-v1.md §Phase 1）：
// - 未登录访问受保护路由 -> 重定向到 /login
// - 已登录访问 /login    -> 重定向到 /home
// - 应用启动时调用一次 auth.attemptRestore 后再放行
//
// Phase 1 路由：/login, /home, /debug(PingTest, 仅开发可见)
//
// 注意：createRouter 必须在 createPinia 之后使用，调用方 main.ts 保证顺序。

import { createRouter, createWebHashHistory, type RouteRecordRaw } from 'vue-router'
import { useAuthStore } from '../stores/auth'

const routes: RouteRecordRaw[] = [
  {
    path: '/',
    redirect: () => '/home'
  },
  {
    path: '/login',
    name: 'login',
    component: () => import('../views/LoginView.vue'),
    meta: { requiresAuth: false }
  },
  {
    path: '/home',
    name: 'home',
    component: () => import('../views/HomeView.vue'),
    meta: { requiresAuth: true }
  },
  // Phase 0 调试组件（保留入口，Phase 2 以后移除或放设置页）
  {
    path: '/debug/ping',
    name: 'debug-ping',
    component: () => import('../components/PingTest.vue'),
    meta: { requiresAuth: false }
  }
]

export const router = createRouter({
  // 桌面端走 hash 模式，避免 Electron file:// + history 模式的 reload 坑
  history: createWebHashHistory(),
  routes
})

// 全局前置守卫：未登录跳 /login；已登录访问 /login 跳 /home
router.beforeEach(async (to) => {
  const auth = useAuthStore()
  // 仅尝试一次 restore（避免重启页面多次请求）
  if (!auth.restoreAttempted) {
    await auth.attemptRestore()
  }
  const requiresAuth = to.meta.requiresAuth === true
  if (requiresAuth && !auth.isAuthenticated) {
    return { name: 'login' }
  }
  if (to.name === 'login' && auth.isAuthenticated) {
    return { name: 'home' }
  }
  return true
})
