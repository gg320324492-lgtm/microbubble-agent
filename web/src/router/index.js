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
        // v78: 合并原 /projects + /members + /voiceprint 3 个独立路由为 1 个 /workspace
        // 顶部 3 tab (项目/成员/声纹), 详情走 dialog 弹层 (与桌面 ProjectView.showDetailDialog 一致)
        // 移动端走 MobileWorkspaceView (顶栏 + 横向 tab + sheet 弹层)
        // 路由 menuRoutes 自动按 meta.icon 过滤显示, sidebar + 移动 drawer 自动出现
        path: 'workspace',
        name: 'Workspace',
        component: resolveMobileComponent('WorkspaceView', 'mobile/MobileWorkspaceView'),
        meta: { title: '团队协作', icon: 'Files' }
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
        // v2 PR7 修复: nested children 改造, 子侧边栏在 4 view 切换时持续渲染
        // 桌面端: DriveLayout 容器 (左侧 DriveSubSidebar + 右侧 4 children 之一)
        //   解决"点击回收站/活动/请求后子侧边栏消失, 体验像弹到别的界面"
        // 移动端: MobileDriveView (单一页面, 无 children, 保持原状)
        path: 'drive',
        component: resolveMobileComponent('desktop/DriveLayout', 'mobile/MobileDriveView'),
        meta: { title: '课题组网盘', icon: 'Folder' },
        children: [
          {
            path: '',
            name: 'Drive',
            component: () => import('@/views/DesktopDriveView.vue')
          },
          {
            // v2 PR2: 回收站
            path: 'trash',
            name: 'DriveTrash',
            component: resolveMobileComponent('desktop/DriveTrashView', 'mobile/MobileDriveTrashView')
          },
          {
            // v2 PR6: 活动动态流
            path: 'activity',
            name: 'DriveActivity',
            component: resolveMobileComponent('desktop/ActivityFeedView', 'mobile/MobileDriveTrashView')  // 移动端暂用 trash 占位
          },
          {
            // v2 PR7: 文件请求管理 (Dropbox 招牌"收作业"创建/关闭页)
            path: 'requests',
            name: 'DriveFileRequests',
            component: resolveMobileComponent('desktop/FileRequestListView', 'mobile/MobileDriveTrashView')
          }
        ]
      },
      {
        // v2 PR6-P2 + PR6-P3: 文件详情页
        // 桌面端: FileDetailView (左右 2 栏)
        // 移动端: MobileFileDetailView (单列 + sticky 顶部 + bottom action sheet)
        path: 'drive/file/:id',
        name: 'DriveFileDetail',
        component: resolveMobileComponent('desktop/FileDetailView', 'mobile/MobileFileDetailView'),
        meta: { title: '文件详情' },
        props: true,
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
        // v78 合并审计日志到项目动态: 加 icon 让 menuRoutes 自动显示（取代原 .sidebar-bottom 硬编码入口）
        meta: { title: '项目动态', icon: 'DataBoard' }
      },
      {
        path: 'admin/agent-traces',
        name: 'AgentTraces',
        component: resolveMobileComponent('admin/AgentTracesView', 'admin/MobileAgentTracesView'),
        meta: { title: 'Agent Trace 监控' }
      },
      // v78 合并审计日志到项目动态: admin/audit 路由删除, 改用 /project-stats?tab=audit 访问
      // 旧路由保留作 fallback 兼容老链接 (去掉 meta.icon 自动从 sidebar 隐藏)
      // v2 PR7 审计日志视图 (admin only, 后端 Depends(get_current_admin) 兜底) 改嵌在 ProjectStatsView 第 2 个 tab
      // v78 UI redesign: 模板管理已合并到 /meetings 第二个 tab (TemplatesPanel), 此路由删除
    ]
  },
  {
    // v2 PR7: 公开文件请求提交页 (无需登录, 纯匿名)
    // router.beforeEach 守卫白名单 bypass
    path: '/r/:token',
    name: 'PublicFileRequestSubmit',
    component: () => import('@/views/public/FileRequestSubmitView.vue'),
    meta: { title: '提交文件', public: true, noAuth: true },  // noAuth 标志守卫跳过
    props: true,
  }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

// 路由守卫（保持原样）
router.beforeEach((to, from, next) => {
  // v2 PR7: 公开路由 (e.g. /r/:token 文件请求提交) 跳过 auth 检查
  if (to.meta?.noAuth) {
    return next()
  }

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