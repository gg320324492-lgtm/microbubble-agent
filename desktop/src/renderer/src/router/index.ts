// renderer 路由表 + auth guard。
//
// 路由分层（Phase 2-Impl-2A）:
//   - 不需 auth: /login, /debug/ping
//   - 需 auth + MainLayout: /dashboard, /knowledge, /knowledge/detail?id=N, /home, /tasks(soon), /meeting(soon)
//
// Phase 2 起步: /dashboard + /knowledge (含详情) + /home 重定向.
// Phase 2 后续批次填 tasks / meeting / knowledge graph 等.

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
    path: '/knowledge',
    name: 'knowledge',
    component: () => import('../views/KnowledgeView.vue'),
    meta: { requiresAuth: true, layout: 'main', title: '知识库' }
  },
  {
    path: '/knowledge/detail',
    name: 'knowledge-detail',
    component: () => import('../views/KnowledgeDetailView.vue'),
    meta: { requiresAuth: true, layout: 'main', title: '文档详情' }
  },
  {
    path: '/chat',
    name: 'chat',
    component: () => import('../views/ChatView.vue'),
    meta: { requiresAuth: true, layout: 'main', title: 'AI 对话' }
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
