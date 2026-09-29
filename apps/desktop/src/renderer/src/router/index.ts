// 路由 — hash 模式（Electron file:// 场景）；守卫负责 setup/login/workbench 三态分流
import { createRouter, createWebHashHistory } from 'vue-router'
import { useAuthStore } from '../stores/auth'

export const routes = [
  { path: '/', redirect: '/app/assistant' },
  {
    path: '/setup',
    name: 'setup',
    component: () => import('../views/SetupView.vue'),
    meta: { title: '创建管理员账号' }
  },
  {
    path: '/login',
    name: 'login',
    component: () => import('../views/LoginView.vue'),
    meta: { title: '登录' }
  },
  {
    path: '/app',
    component: () => import('../layouts/ShellLayout.vue'),
    redirect: '/app/assistant',
    children: [
      {
        path: 'assistant',
        name: 'assistant',
        component: () => import('../views/AssistantView.vue'),
        meta: { title: 'AI 助手', icon: 'chat' }
      },
      {
        path: 'knowledge',
        name: 'knowledge',
        component: () => import('../views/KnowledgeView.vue'),
        meta: { title: '知识库', icon: 'book' }
      },
      {
        path: 'drive',
        name: 'drive',
        component: () => import('../views/DriveView.vue'),
        meta: { title: '网盘', icon: 'folder' }
      },
      {
        path: 'meetings',
        name: 'meetings',
        component: () => import('../views/MeetingsView.vue'),
        meta: { title: '会议', icon: 'calendar' }
      },
      {
        path: 'settings',
        name: 'settings',
        component: () => import('../views/SettingsView.vue'),
        meta: { title: '设置', icon: 'gear' }
      }
    ]
  },
  { path: '/:pathMatch(.*)*', redirect: '/app/assistant' }
]

export const router = createRouter({
  history: createWebHashHistory(),
  routes
})

router.beforeEach(async (to) => {
  const auth = useAuthStore()
  await auth.init()

  // M2-3a+ 统一登录：**本地建号已退役**，不再分流到 setup。
  // 有缓存会话（含离线宽容）→ 直接进；无会话 → 登录窗（父级账号）。
  if (to.path.startsWith('/app') && !auth.isAuthenticated) {
    return { name: 'login' }
  }
  if ((to.name === 'login' || to.name === 'setup') && auth.isAuthenticated) {
    return { name: 'assistant' }
  }
  // setup 路由保留但**不可达**（直接访问也送回登录窗）——本地 users 表结构保留不删
  if (to.name === 'setup') {
    return { name: 'login' }
  }
  return true
})
