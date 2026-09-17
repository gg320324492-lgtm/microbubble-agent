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
        path: 'eln',
        name: 'eln',
        component: () => import('../views/ExperimentView.vue'),
        meta: { title: '实验 ELN', icon: 'flask' }
      },
      {
        path: 'manuscripts',
        name: 'manuscripts',
        component: () => import('../views/ManuscriptsView.vue'),
        meta: { title: '稿件', icon: 'doc' }
      },
      {
        path: 'knowledge',
        name: 'knowledge',
        component: () => import('../views/KnowledgeView.vue'),
        meta: { title: '知识库', icon: 'book' }
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

  if (to.path.startsWith('/app') && !auth.isAuthenticated) {
    return auth.needsSetup ? { name: 'setup' } : { name: 'login' }
  }
  if ((to.name === 'login' || to.name === 'setup') && auth.isAuthenticated) {
    return { name: 'assistant' }
  }
  if (to.name === 'login' && auth.needsSetup) {
    return { name: 'setup' }
  }
  if (to.name === 'setup' && auth.userCount > 0) {
    return { name: 'login' }
  }
  return true
})
