// renderer 路由表 + auth guard。
//
// 路由分层（Phase 2-Impl-2A）:
//   - 不需 auth: /login, /debug/ping
//   - 需 auth + MainLayout: /dashboard, /knowledge, /knowledge/detail?id=N, /home, /tasks(soon), /meeting(soon)
//
// 默认入口 / 与 /home 进入科研首页；/dashboard 作为旧视图兼容入口保留。
// Phase 2 后续批次填 tasks / meeting / knowledge graph 等.

import { createRouter, createWebHashHistory, type RouteRecordRaw } from 'vue-router'
import { useAuthStore } from '../stores/auth'

const routes: RouteRecordRaw[] = [
  {
    path: '/',
    redirect: { name: 'research-dashboard' }
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
    redirect: { name: 'research-dashboard' }
  },
  // ── Phase 8-I1/I2: 科研工作台路由 ──
  {
    path: '/research/project',
    name: 'research-project',
    component: () => import('../pages/research/ProjectWorkspace.vue'),
    meta: { requiresAuth: true, layout: 'main', title: '研究工作区' }
  },
  {
    path: '/research/dashboard',
    name: 'research-dashboard',
    component: () => import('../pages/research/Dashboard.vue'),
    meta: { requiresAuth: true, layout: 'main', title: '科研驾驶舱' }
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
    path: '/research/demo',
    name: 'research-demo',
    component: () => import('../pages/research/Demo.vue'),
    meta: { requiresAuth: true, layout: 'main', title: '演示场景 · O₃-MNBs' }
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
    meta: { requiresAuth: true, layout: 'main', title: 'SCI写作' }
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
    meta: { requiresAuth: true, layout: 'main', title: 'AI研究团队' }
  },
  {
    path: '/research/experiment-control',
    name: 'research-experiment-control',
    component: () => import('../pages/research/ExperimentControlCenter.vue'),
    meta: { requiresAuth: true, layout: 'main', title: '实验控制中心', theme: 'scada' }
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
  },
  // ---------- Phase 8-M0-H0 产品化路由 ----------
  {
    path: '/splash',
    name: 'splash',
    component: () => import('../views/SplashScreen.vue'),
    meta: { requiresAuth: false, layout: 'plain', title: '启动' }
  },
  {
    path: '/about',
    name: 'about',
    component: () => import('../views/AboutView.vue'),
    meta: { requiresAuth: true, layout: 'main', title: '关于' }
  },
  {
    path: '/system-status',
    name: 'system-status',
    component: () => import('../views/SystemStatusView.vue'),
    meta: { requiresAuth: true, layout: 'main', title: '系统状态' }
  },
  // ---------- Phase 8-M1-A: First launch ----------
  {
    path: '/system/first-launch',
    name: 'system-first-launch',
    component: () => import('../pages/system/FirstLaunch.vue'),
    meta: { requiresAuth: false, layout: 'plain', title: '首次启动' }
  },
  // ---------- R5: 迁移中心 + 本地历史资料工作区 ----------
  {
    path: '/migration',
    name: 'migration-center',
    component: () => import('../pages/migration/MigrationCenter.vue'),
    meta: { requiresAuth: true, layout: 'main', title: '迁移中心', icon: 'upload' }
  },
  {
    path: '/workspace/work-items',
    name: 'workspace-work-items',
    component: () => import('../pages/workspace/WorkItemsWorkspace.vue'),
    meta: { requiresAuth: true, layout: 'main', title: '工作项工作区', icon: 'progress' }
  },
  {
    path: '/workspace/meetings',
    name: 'workspace-meetings',
    component: () => import('../pages/workspace/MeetingArchiveWorkspace.vue'),
    meta: { requiresAuth: true, layout: 'main', title: '会议档案工作区', icon: 'citation' }
  },
  {
    path: '/workspace/files',
    name: 'workspace-files',
    component: () => import('../pages/workspace/FileLibraryWorkspace.vue'),
    meta: { requiresAuth: true, layout: 'main', title: '文件库工作区', icon: 'folder' }
  },
  {
    path: '/workspace/conversations',
    name: 'workspace-conversations',
    component: () => import('../pages/workspace/ConversationArchiveWorkspace.vue'),
    meta: { requiresAuth: true, layout: 'main', title: '对话归档工作区', icon: 'assistant' }
  }
]

export const router = createRouter({
  // 桌面端走 hash 模式，避免 Electron file:// + history 模式的 reload 坑
  history: createWebHashHistory(),
  routes
})

// 全局前置守卫：未登录跳 /login；已登录访问 /login 跳科研首页。
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
    return { name: 'research-dashboard' }
  }
  return true
})
