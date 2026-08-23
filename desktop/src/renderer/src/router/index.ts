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
    path: '/settings/models',
    name: 'settings-models',
    component: () => import('../views/settings/ModelSettingsView.vue'),
    meta: { requiresAuth: true, layout: 'main', title: '模型设置' }
  },
  {
    path: '/home',
    name: 'home',
    redirect: () => '/dashboard'
  },
  // ── Phase 8-I1/I2: 科研工作台路由 ──
  {
    path: '/research/project',
    name: 'research-project',
    component: () => import('../pages/research/ProjectWorkspace.vue'),
    meta: { requiresAuth: true, layout: 'main', title: '项目空间' }
  },
  {
    path: '/research/dashboard',
    name: 'research-dashboard',
    component: () => import('../pages/research/Dashboard.vue'),
    meta: { requiresAuth: true, layout: 'main', title: '首页' }
  },
  {
    path: '/research/assistant',
    name: 'research-assistant',
    component: () => import('../pages/research/Assistant.vue'),
    meta: { requiresAuth: true, layout: 'main', title: 'AI 科研助手' }
  },
  {
    path: '/research/literature',
    name: 'research-literature',
    component: () => import('../pages/research/Literature.vue'),
    meta: { requiresAuth: true, layout: 'main', title: '文献智能库' }
  },
  {
    path: '/research/experiment',
    name: 'research-experiment',
    component: () => import('../pages/research/Experiment.vue'),
    meta: { requiresAuth: true, layout: 'main', title: '实验设计' }
  },
  {
    path: '/research/data-analysis',
    name: 'research-data-analysis',
    component: () => import('../pages/research/DataAnalysis.vue'),
    meta: { requiresAuth: true, layout: 'main', title: '数据分析' }
  },
  {
    path: '/research/manuscript',
    name: 'research-manuscript',
    component: () => import('../pages/research/Manuscript.vue'),
    meta: { requiresAuth: true, layout: 'main', title: '论文助手' }
  },
  {
    path: '/research/knowledge-graph',
    name: 'research-knowledge-graph',
    component: () => import('../pages/research/KnowledgeGraph.vue'),
    meta: { requiresAuth: true, layout: 'main', title: '知识图谱' }
  },
  {
    path: '/research/agent-center',
    name: 'research-agent-center',
    component: () => import('../pages/research/AgentCenter.vue'),
    meta: { requiresAuth: true, layout: 'main', title: '智能体中心' }
  },
  {
    path: '/research/settings',
    name: 'research-settings',
    component: () => import('../pages/research/Settings.vue'),
    meta: { requiresAuth: true, layout: 'main', title: '系统设置' }
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
