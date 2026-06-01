import { createRouter, createWebHistory } from 'vue-router'

const routes = [
  {
    path: '/login',
    name: 'Login',
    component: () => import('@/views/LoginView.vue'),
    meta: { title: '登录' }
  },
  {
    path: '/',
    component: () => import('@/layouts/MainLayout.vue'),
    redirect: '/dashboard',
    meta: { requiresAuth: true },
    children: [
      {
        path: 'dashboard',
        name: 'Dashboard',
        component: () => import('@/views/Dashboard.vue'),
        meta: { title: '仪表盘', icon: 'Odometer' }
      },
      {
        path: 'chat',
        name: 'Chat',
        component: () => import('@/views/ChatView.vue'),
        meta: { title: '智能对话', icon: 'ChatDotRound' }
      },
      {
        path: 'tasks',
        name: 'Tasks',
        component: () => import('@/views/TaskView.vue'),
        meta: { title: '任务管理', icon: 'List' }
      },
      {
        path: 'meetings',
        name: 'Meetings',
        component: () => import('@/views/MeetingView.vue'),
        meta: { title: '会议管理', icon: 'VideoCamera' }
      },
      {
        path: 'meetings/:id',
        name: 'MeetingDetail',
        component: () => import('@/views/MeetingDetailView.vue'),
        meta: { title: '会议详情' }
      },
      {
        path: 'projects',
        name: 'Projects',
        component: () => import('@/views/ProjectView.vue'),
        meta: { title: '项目管理', icon: 'Folder' }
      },
      {
        path: 'members',
        name: 'Members',
        component: () => import('@/views/MemberView.vue'),
        meta: { title: '成员管理', icon: 'User' }
      },
      {
        path: 'knowledge',
        name: 'Knowledge',
        component: () => import('@/views/KnowledgeView.vue'),
        meta: { title: '知识库', icon: 'Document' }
      },
      {
        path: 'knowledge/:id',
        name: 'KnowledgeDetail',
        component: () => import('@/views/KnowledgeDetailView.vue'),
        meta: { title: '知识详情' }
      },
      {
        path: 'memory',
        name: 'Memory',
        component: () => import('@/views/MemoryView.vue'),
        meta: { title: '长期记忆', icon: 'Memo' }
      },
      {
        path: 'voiceprint',
        name: 'Voiceprint',
        component: () => import('@/views/VoiceprintView.vue'),
        meta: { title: '声纹库中心', icon: 'mic' }
      },
      {
        path: 'settings',
        name: 'Settings',
        component: () => import('@/views/SettingsView.vue'),
        meta: { title: '个人设置', icon: 'Setting' }
      }
    ]
  }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

// 路由守卫
router.beforeEach((to, from, next) => {
  const token = localStorage.getItem('access_token')

  if (to.meta.requiresAuth && !token) {
    next('/login')
  } else if (to.path === '/login' && token) {
    next('/')
  } else {
    next()
  }
})

export default router
