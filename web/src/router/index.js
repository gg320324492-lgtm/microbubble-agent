import { createRouter, createWebHistory } from 'vue-router'
import { resolveMobileComponent, resolveMobileOnly } from '@/utils/resolveMobile'

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
        component: resolveMobileOnly('MobileTaskTrash'),
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
        component: resolveMobileComponent('WorkspaceView', 'MobileWorkspaceView'),
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
        // PR3.1: 课题组网盘 (Lab Group Drive) - 桌面端主视图, 移动端 PR4 复用 KB 第 6 tab
        path: 'drive',
        name: 'Drive',
        component: resolveMobileComponent('DesktopDriveView', 'MobileDriveView'),
        meta: { title: '课题组网盘', icon: 'Folder' }
      },
      {
        // v2 PR2: 回收站 (顶级路由, 不嵌套在 /drive 下避免与 FileGrid 冲突)
        path: 'drive/trash',
        name: 'DriveTrash',
        component: resolveMobileComponent('desktop/DriveTrashView', 'MobileDriveTrashView'),
        meta: { title: '回收站', icon: 'Delete' }
      },
      {
        // v2 PR7: 文件请求管理 (Dropbox 招牌"收作业"创建/关闭页)
        // 移动端暂用 trash 占位 (PR8 独立 mobile 版)
        path: 'drive/requests',
        name: 'DriveFileRequests',
        component: resolveMobileComponent('desktop/FileRequestListView', 'MobileDriveTrashView'),
        meta: { title: '文件请求', icon: 'Promotion' }
      },
      {
        // v2 PR6-P2 + PR6-P3: 文件详情页
        // 桌面端: FileDetailView (左右 2 栏)
        // 移动端: MobileFileDetailView (单列 + sticky 顶部 + bottom action sheet)
        path: 'drive/file/:id',
        name: 'DriveFileDetail',
        component: resolveMobileComponent('desktop/FileDetailView', 'MobileFileDetailView'),
        meta: { title: '文件详情' },
        props: true,
      },
      {
        // W68 路线 F-3: 文件评论独立路由页 (mobile-only)
        // 桌面端访问走 FileDetailView 详情页 (评论嵌内)
        path: 'drive/file/:id/comments',
        name: 'DriveFileComments',
        component: resolveMobileOnly('MobileFileCommentsView'),
        meta: { title: '文件评论', mobileOnly: true },
        props: true,
      },
      {
        // W68 第 4 批: 文件版本历史桌面端独立路由 (desktop-only)
        // 桌面端: DesktopFileVersionsView 全屏时间线 (本批新建)
        // 移动端: 暂不暴露, 用户走 VersionHistoryDialog (PR4 既有)
        path: 'drive/file/:id/versions',
        name: 'DriveFileVersions',
        component: () => import('@/views/desktop/DesktopFileVersionsView.vue'),
        meta: { title: '文件版本历史', desktopOnly: true },
        props: true,
      },
      {
        // PR8: 移动端文件 swipe 预览 (mobile-only)
        // 桌面端访问走 FileDetailView 详情页
        // 单文件模式: /drive/preview/:id
        // 多文件模式: /drive/preview/:id?list=id1,id2,id3&idx=0
        path: 'drive/preview/:id',
        name: 'DriveFilePreviewSwipe',
        // mobile-only: 桌面端走 DesktopDriveView 文件 grid 直接预览 (FilePreviewDialog)
        component: resolveMobileOnly('MobileFilePreviewSwipe'),
        meta: { title: '文件预览', mobileOnly: true },
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
        // v78 决策"项目动态硬编码入口不动": 不加 icon, 让 menuRoutes filter r.meta?.icon 自动排除
        // 入口走 MainLayout L60-69 .sidebar-bottom 硬编码 (含 DataBoard icon)
        meta: { title: '项目动态' }
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

  // PR8: mobile-only 路由在桌面端重定向到文件详情页
  if (to.meta?.mobileOnly && typeof window !== 'undefined' && window.innerWidth >= 768) {
    const fileId = to.params.id
    return next(`/drive/file/${fileId}`)
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