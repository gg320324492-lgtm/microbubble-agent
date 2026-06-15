import { createRouter, createWebHistory } from 'vue-router'
import { resolveMobileComponent } from '@/utils/resolveMobile'

/**
 * 路由表（PR #2 改造：所有 14 条路由包 resolveMobileComponent 路由级动态加载）
 *
 * 路由级桌面/移动双栈：
 * - 桌面（>= 1024px）：加载 views/xxx.vue 原组件
 * - 移动（< 1024px）：加载 views/mobile/xxx.vue 独立组件
 *
 * 物理隔离：移动端代码独立 chunk（vite manualChunks: nutui-mobile），不污染桌面 bundle
 * 旋转屏幕：useAdaptiveRoute 触发 router.replace → resolveMobileComponent 重选
 *
 * 注意：移动端组件在 PR #3-#8 才会陆续创建。PR #2 部署后，
 *       移动端访问这些路由会显示空白（MobileXxx.vue 404 模块不存在），
 *       这是预期的渐进式迁移过程，桌面端完全不受影响。
 */

const routes = [
  {
    path: '/login',
    name: 'Login',
    component: resolveMobileComponent('LoginView', 'MobileLoginView'),
    meta: { title: '登录' }
  },
  {
    path: '/',
    // MainLayout 内部按 isMobile 分支（桌面：el-aside / 移动：底部 TabBar）
    // 不需要独立 MobileMainLayout
    component: () => import('@/layouts/MainLayout.vue'),
    redirect: '/dashboard',
    meta: { requiresAuth: true },
    children: [
      {
        path: 'dashboard',
        name: 'Dashboard',
        component: resolveMobileComponent('Dashboard', 'dashboard/MobileDashboard'),
        meta: { title: '仪表盘', icon: 'Odometer' }
      },
      {
        path: 'chat',
        name: 'Chat',
        // 桌面用 ChatViewSSE（v2 极简 SSE + Rich Block）；移动用 MobileChatView（PR #3 创建）
        component: resolveMobileComponent('chat/ChatViewSSE', 'chat/MobileChatView'),
        meta: { title: '智能对话', icon: 'ChatDotRound' }
      },
      {
        path: 'tasks',
        name: 'Tasks',
        component: resolveMobileComponent('TaskView', 'tasks/MobileTaskView'),
        meta: { title: '任务管理', icon: 'List' }
      },
      {
        path: 'meetings',
        name: 'Meetings',
        component: resolveMobileComponent('MeetingView', 'meeting/MobileMeetingView'),
        meta: { title: '会议管理', icon: 'VideoCamera' }
      },
      {
        // 移动端听会房间（占位 UI，WS 实时录音集成 = 后续 PR）
        // 桌面端 fallback 到 MeetingView（用户不会从桌面 UI 触发此路由）
        path: 'meetings/room',
        name: 'MeetingRoom',
        component: resolveMobileComponent('MeetingView', 'meeting/MobileMeetingRoom'),
        meta: { title: '开始听会' }
      },
      {
        path: 'meetings/:id',
        name: 'MeetingDetail',
        component: resolveMobileComponent('MeetingDetailView', 'meeting/MobileMeetingDetailView'),
        meta: { title: '会议详情' }
      },
      {
        path: 'projects',
        name: 'Projects',
        component: resolveMobileComponent('ProjectView', 'projects/MobileProjectView'),
        meta: { title: '项目管理', icon: 'Folder' }
      },
      {
        path: 'members',
        name: 'Members',
        component: resolveMobileComponent('MemberView', 'members/MobileMemberView'),
        meta: { title: '成员管理', icon: 'User' }
      },
      {
        path: 'knowledge',
        name: 'Knowledge',
        component: resolveMobileComponent('KnowledgeView', 'knowledge/MobileKnowledgeView'),
        meta: { title: '知识库', icon: 'Document' }
      },
      {
        path: 'knowledge/:id',
        name: 'KnowledgeDetail',
        component: resolveMobileComponent('KnowledgeDetailView', 'knowledge/MobileKnowledgeDetailView'),
        meta: { title: '知识详情' }
      },
      {
        path: 'memory',
        name: 'Memory',
        component: resolveMobileComponent('MemoryView', 'memory/MobileMemoryView'),
        meta: { title: '长期记忆', icon: 'Memo' }
      },
      {
        path: 'voiceprint',
        name: 'Voiceprint',
        component: resolveMobileComponent('VoiceprintView', 'members/MobileVoiceprintView'),
        meta: { title: '声纹库中心', icon: 'mic' }
      },
      {
        path: 'settings',
        name: 'Settings',
        component: resolveMobileComponent('SettingsView', 'settings/MobileSettingsView'),
        meta: { title: '个人设置', icon: 'Setting' }
      },
      {
        path: 'project-stats',
        name: 'ProjectStats',
        component: resolveMobileComponent('ProjectStatsView', 'projects/MobileProjectStatsView'),
        meta: { title: '项目动态' }
      },
      {
        path: 'admin/agent-traces',
        name: 'AgentTraces',
        component: resolveMobileComponent('admin/AgentTracesView', 'admin/MobileAgentTracesView'),
        meta: { title: 'Agent Trace 监控' }
      }
    ]
  }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

// 路由守卫（保持原样）
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