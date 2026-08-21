// renderer 路由表 + auth guard。
//
// 路由分层（Phase 2-Impl-1）:
//   - 不需 auth: /login
//   - 需 auth + MainLayout: /dashboard, /home, /debug/ping
//   - 根 / → 按 isAuthenticated 重定向到 /dashboard 或 /login
//
// Phase 2-Impl-1 起步：/dashboard 替代 /home 为默认页。
// /home 保留作为兼容 redirect → /dashboard。

import { createRouter, createWebHashHistory, type RouteRecordRaw } from 'vue-router'
import { useAuthStore } from '../stores/auth'

const routes: RouteRecordRaw[] = [
  {
    path: '/',
    redirect: () => '/dashboard'
  },
  {
    path: '/login',
    name: 'login',
    component: () => import('../views/LoginView.vue'),
    meta: { requiresAuth: false, layout: 'plain', title: '登录' }
  },
  {
    path: '/dashboard',
    name: 'dashboard',
    component: () => import('../views/DashboardView.vue'),
    meta: { requiresAuth: true, layout: 'main', title: '仪表盘' }
  },
  {
    path: '/home',
    name: 'home',
    redirect: () => '/dashboard'
  },
  // Phase 0 调试组件（保留入口）
  {
    path: '/debug/ping',
    name: 'debug-ping',
    component: () => import('../components/PingTest.vue'),
    meta: { requiresAuth: false, layout: 'plain', title: 'IPC 调试' }
  }
]

export const router = createRouter({
  // 桌面端走 hash 模式，避免 Electron file:// + history 模式的 reload 坑
  history: createWebHashHistory(),
  routes
})

// 全局前置守卫：未登录跳 /login；已登录访问 /login 跳 /dashboard
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
    return { name: 'dashboard' }
  }
  return true
})
