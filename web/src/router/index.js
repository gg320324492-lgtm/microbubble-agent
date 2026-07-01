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
        component: resolveMobileComponent('Dashboard', 'MobileDashboard'),
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
        component: resolveMobileComponent('TaskView', 'MobileTaskView'),
        meta: { title: '任务管理', icon: 'List' }
      },
      {
        // 移动端任务回收站（桌面嵌入 TaskView，移动端独立路由）
        path: 'tasks/trash',
        name: 'MobileTaskTrash',
        component: () => import('@/views/mobile/MobileTaskTrash.vue'),
        meta: { title: '任务回收站' }
      },
      {
        path: 'meetings',
        name: 'Meetings',
        component: resolveMobileComponent('MeetingView', 'meeting/MobileMeetingView'),
        meta: { title: '会议管理', icon: 'VideoCamera' }
      },
      {
        // 听会房间 — 桌面端用 MeetingRoomView（全屏页面，2026-06-18 新建），
        // 移动端用 MobileMeetingRoom（PageHeader + 底部 sheet 帮助）。
        // 桌面 MainLayout "正在听会" 胶囊点击 → /meetings?resume={id} →
        // MeetingView 跳到本页 → onMounted 用 checkActiveRecording() 复用 recordingMeetingId
        // → 用户可继续听会 / 重新开始
        path: 'meetings/room',
        name: 'MeetingRoom',
        component: resolveMobileComponent('MeetingRoomView', 'meeting/MobileMeetingRoom'),
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
        component: resolveMobileComponent('ProjectView', 'MobileProjectView'),
        meta: { title: '项目管理', icon: 'Folder' }
      },
      {
        // 移动端项目详情（桌面 ProjectView 的 dialog 内容镜像成全屏页）
        path: 'projects/:id',
        name: 'ProjectDetail',
        component: resolveMobileComponent('ProjectView', 'mobile/MobileProjectDetailView'),
        meta: { title: '项目详情' }
      },
      {
        path: 'members',
        name: 'Members',
        component: resolveMobileComponent('MemberView', 'MobileMemberView'),
        meta: { title: '成员管理', icon: 'User' }
      },
      {
        // 移动端成员详情（从 MobileMemberView 卡片点击进入）
        path: 'members/:id',
        name: 'MemberDetail',
        component: resolveMobileComponent('MemberView', 'mobile/MobileMemberDetailView'),
        meta: { title: '成员详情' }
      },
      {
        path: 'knowledge',
        name: 'Knowledge',
        component: resolveMobileComponent('KnowledgeView', 'MobileKnowledgeView'),
        meta: { title: '知识库', icon: 'Document' }
      },
      {
        path: 'knowledge/:id',
        name: 'KnowledgeDetail',
        component: resolveMobileComponent('KnowledgeDetailView', 'MobileKnowledgeDetailView'),
        meta: { title: '知识详情' }
      },
      {
        path: 'memory',
        redirect: '/knowledge?tab=memory'
      },
      {
        path: 'voiceprint',
        name: 'Voiceprint',
        component: resolveMobileComponent('VoiceprintView', 'MobileVoiceprintView'),
        meta: { title: '声纹库中心', icon: 'mic' }
      },
      {
        // PR3.1: 课题组网盘 (Lab Group Drive) - 桌面端主视图, 移动端 PR4 复用 KB 第 6 tab
        path: 'drive',
        name: 'Drive',
        // 桌面 DesktopDriveView (本 PR3 创建), 移动端 MobileDriveView (PR4)
        component: resolveMobileComponent('DesktopDriveView', 'mobile/MobileDriveView'),
        meta: { title: '课题组网盘', icon: 'Files' }
      },
      {
        path: 'settings',
        name: 'Settings',
        component: resolveMobileComponent('SettingsView', 'MobileSettingsView'),
        meta: { title: '个人设置', icon: 'Setting' }
      },
      {
        path: 'project-stats',
        name: 'ProjectStats',
        component: resolveMobileComponent('ProjectStatsView', 'MobileProjectStatsView'),
        meta: { title: '项目动态' }
      },
      {
        path: 'admin/agent-traces',
        name: 'AgentTraces',
        component: resolveMobileComponent('admin/AgentTracesView', 'admin/MobileAgentTracesView'),
        meta: { title: 'Agent Trace 监控' }
      },
      // v78 UI redesign: 模板管理已合并到 /meetings 第二个 tab (TemplatesPanel), 此路由删除
      // 旧路由保留作 fallback 兼容老链接 (去掉 meta.icon 自动从 sidebar 隐藏)
      // 2026-06-30 由 v77 P2.6-G.2 的 /admin/templates 移入会议管理 tab
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