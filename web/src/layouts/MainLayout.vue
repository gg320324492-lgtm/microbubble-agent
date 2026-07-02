<template>
  <!-- 移动端独立抽屉 — 在 el-container 外部，不受 Element Plus aside 样式影响 -->
  <Transition name="mobile-drawer">
    <div v-if="isMobile && showMobileMenu" class="mobile-drawer-root">
      <div class="mobile-drawer-mask" @click="showMobileMenu = false" />
      <div class="mobile-drawer-body">
        <div class="mobile-drawer-brand">
          <div class="mobile-drawer-logo">
            <el-icon size="24"><Aim /></el-icon>
          </div>
          <span>小气助手</span>
        </div>
        <div
          v-for="(item, index) in menuRoutes"
          :key="item.path"
          class="mobile-drawer-item"
          :class="{ active: currentRoute === item.path }"
          :style="{ '--i': index }"
          @click="navigateTo(item.path)"
        >
          <el-icon size="20"><component :is="iconMap[item.meta.icon]" /></el-icon>
          <span>{{ item.meta.title }}</span>
        </div>
      </div>
    </div>
  </Transition>

  <el-container class="layout-container">
    <!-- 桌面端侧边栏 — 移动端完全不渲染 -->
    <el-aside
      v-if="!isMobile"
      :width="sidebarWidth"
      class="aside glass glass-lg"
    >
      <div class="logo">
        <div class="logo-icon">
          <el-icon size="24"><Aim /></el-icon>
        </div>
        <span v-show="!isCollapse" class="title">小气助手</span>
      </div>

      <el-menu
        :default-active="currentRoute"
        :collapse="isCollapse"
        router
        class="sidebar-menu"
      >
        <el-menu-item
          v-for="route in menuRoutes"
          :key="route.path"
          :index="'/' + route.path"
          class="menu-item"
        >
          <el-icon><component :is="iconMap[route.meta.icon]" /></el-icon>
          <template #title><span style="color:inherit">{{ route.meta.title }}</span></template>
        </el-menu-item>
      </el-menu>

      <!-- 侧边栏底部 - 项目动态 (v31 检索质量已合并到此页 tab) -->
      <div class="sidebar-bottom">
        <div
          class="sidebar-bottom-item"
          :class="{ active: currentRoute === '/project-stats' }"
          @click="router.push('/project-stats')"
        >
          <el-icon><DataBoard /></el-icon>
          <span v-show="!isCollapse">项目动态</span>
        </div>
      </div>
    </el-aside>

    <!-- 主内容区 -->
    <el-container>
      <!-- 顶部栏 -->
      <el-header class="header">
        <div class="header-left">
          <!-- 2026-06-25: 移动端不显示折叠按钮（避免与 MobileHeader 的 ≡ 重复，且 TabBar 已替代主导航） -->
          <el-icon v-if="!isMobile" :class="['collapse-btn', { 'collapse-btn-mobile': isMobile }]" @click="toggleSidebar">
            <Fold v-if="!isCollapse" />
            <Expand v-else />
          </el-icon>
          <el-breadcrumb v-if="!isMobile" separator="/">
            <el-breadcrumb-item :to="{ path: '/' }">首页</el-breadcrumb-item>
            <el-breadcrumb-item>{{ currentTitle }}</el-breadcrumb-item>
          </el-breadcrumb>
        </div>

        <div class="header-right">
          <el-popover placement="bottom-end" :width="320" trigger="click" v-model:visible="popoverVisible" @show="handlePopoverShow">
            <template #reference>
              <el-badge :value="notificationCount" :max="99" :hidden="notificationCount === 0">
                <el-icon :size="isMobile ? 36 : 32" class="bell-icon"><Bell /></el-icon>
              </el-badge>
            </template>
            <div v-if="popoverVisible" class="notification-panel">
              <div class="notification-panel-title">提醒通知</div>
              <div class="notification-panel-body">
                <template v-if="notifications.length > 0">
                  <div
                    v-for="item in notifications"
                    :key="item.id"
                    class="notification-item"
                    @click="goToTask(item.task_id)"
                  >
                    <div class="notification-item-title">{{ item.task_title }}</div>
                    <div class="notification-item-time">{{ formatTime(item.remind_at) }}</div>
                  </div>
                  <el-button type="primary" size="small" class="mark-read-btn" @click="handleMarkAllRead">全部标为已读</el-button>
                </template>
                <p v-else style="color:var(--color-info);text-align:center;padding:20px 0">暂无新提醒</p>
              </div>
              <div class="notification-panel-footer">
                <el-button text size="small" @click="router.push({ path: '/tasks', query: { assignee_id: userStore.userInfo?.id } })">查看我的任务</el-button>
              </div>
            </div>
          </el-popover>

          <!-- v2 PR6: 网盘协作通知铃铛 (@ 提醒 + 评论) -->
          <NotificationBell />

          <!-- v68 (2026-06-26): 主题切换按钮（铃铛之后、用户 dropdown 之前） -->
          <ThemeToggleButton />

          <el-dropdown>
            <div class="user-info">
              <el-avatar :size="32" :src="userAvatar" :alt="username" icon="UserFilled" />
              <div v-if="!isMobile" class="user-detail">
                <span class="username">{{ username }}</span>
                <span class="user-role">{{ userRole }}</span>
              </div>
            </div>
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item @click="router.push('/settings')">个人设置</el-dropdown-item>
                <el-dropdown-item divided @click="handleLogout">退出登录</el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>
        </div>
      </el-header>

      <!-- 内容区 -->
      <el-main :class="['main', { 'mobile-main': isMobile }]">
        <router-view />
      </el-main>
    </el-container>
  </el-container>

  <!-- 全局浮动录音指示器 — 有会议正在录音时显示 -->
  <Transition name="recording-banner">
    <div
      v-if="recordingMeetingId"
      class="recording-indicator"
      :class="{ 'is-offline': !network.online.value }"
      role="status"
      aria-label="正在听会，点击返回"
      @click="goToRecording"
    >
      <span class="recording-dot" />
      <span class="recording-text">正在听会</span>
      <span v-if="!network.online.value" class="recording-warning" title="网络已断开，录音暂存本地">⚠</span>
      <span class="recording-title">{{ recordingMeetingTitle }}</span>
      <el-icon class="recording-arrow"><ArrowRight /></el-icon>
    </div>
  </Transition>

  <!-- 移动端底部导航 TabBar（PR #2 新增：基于 NutUI nut-tabbar）
       /chat 路由也显示 TabBar（在 input 框下方），用户偏好 persistent nav -->
  <MobileTabBar v-if="isMobile" />
</template>

<script setup>
import { ref, computed, onMounted, onBeforeUnmount } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import axios from 'axios'
import dayjs from 'dayjs'
import { useUserStore } from '@/stores/user'
import { useMemberStore } from '@/stores/member'
import { useRecordingState } from '@/composables/useRecordingState'
import { useNetworkStatus } from '@/composables/useNetworkStatus'
import { useIsMobile } from '@/composables/useIsMobile'
import MobileTabBar from '@/components/mobile/TabBar.vue'
// v68 (2026-06-26): 桌面端顶栏主题切换按钮（与移动端 MobileHeader 风格一致）
import ThemeToggleButton from '@/components/ThemeToggleButton.vue'
// v2 PR6: 网盘协作通知 (@ 提醒 + 评论) + WS 推送
import NotificationBell from '@/components/common/NotificationBell.vue'
import { ArrowRight, DataBoard, Aim, Bell, Odometer, ChatDotRound, List, VideoCamera, Folder, User, Document, Memo, Setting, Fold, Expand, Files } from '@element-plus/icons-vue'

// 侧边栏/面包屑路由 meta.icon 字符串 → 图标组件映射
// unplugin-vue-components 无法解析动态 <component :is="string">，必须显式 import
// v78: 删除 mic 别名 (声纹已合并到 /workspace 走 Files 图标)
const iconMap = {
  Odometer, ChatDotRound, List, VideoCamera, Folder,
  User, Document, Memo, Setting, Files,
}

const route = useRoute()
const router = useRouter()
const userStore = useUserStore()
const memberStore = useMemberStore()

// 全局录音状态
const { recordingMeetingId, recordingMeetingTitle, checkActiveRecording } = useRecordingState()
const network = useNetworkStatus()

const goToRecording = () => {
  if (recordingMeetingId.value) {
    router.push(`/meetings?resume=${recordingMeetingId.value}`)
  }
}

const isMobile = useIsMobile().isMobile
const isCollapse = ref(false)
const showMobileMenu = ref(false)
const popoverVisible = ref(false)

// /chat 路由不显示 TabBar（标准 mobile UX：聊天专注模式 + 避免覆盖 MobileInputBar）
const isChatRoute = computed(() => route.path.startsWith('/chat'))

const sidebarWidth = computed(() => {
  if (isMobile.value) return '0px'
  return isCollapse.value ? '64px' : '220px'
})

const currentRoute = computed(() => route.path)
const currentTitle = computed(() => route.meta?.title || '首页')
const username = computed(() => userStore.username)
const userRole = computed(() => userStore.userRole)
const notificationCount = computed(() => userStore.notificationCount)
const notifications = computed(() => userStore.notifications)
const userAvatar = computed(() => userStore.userInfo?.avatar || '')

const menuRoutes = computed(() => {
  const mainRoute = router.options.routes.find(r => r.path === '/')
  // 2026-07-02: PR7 反转后, drive/trash / drive/requests 在 FolderTree 内访问 (主侧边栏不再单独显示)
  // 活动动态已升级为顶级 /activity (meta.icon='Bell') 自动出现
  const HIDDEN_PATHS = new Set(['drive/trash', 'drive/requests'])
  return (mainRoute?.children || []).filter(r => r.meta?.icon && !HIDDEN_PATHS.has(r.path))
})

// PR #2: isMobile 改用 useIsMobile composable（matchMedia + 防抖）
// 不再需要本地 onResize + window resize 监听
// 跨断点组件切换由 useAdaptiveRoute 自动处理

function syncMobileDrawerClose() {
  // 跨断点时强制关闭移动端抽屉
  if (isMobile.value) {
    showMobileMenu.value = false
  }
}

const toggleSidebar = () => {
  if (isMobile.value) {
    showMobileMenu.value = !showMobileMenu.value
  } else {
    isCollapse.value = !isCollapse.value
  }
}

const navigateTo = (path) => {
  showMobileMenu.value = false
  router.push('/' + path)
}

onMounted(async () => {
  userStore.loadFromStorage()

  // 未登录时不发起 API 请求，避免 401 刷屏
  const token = localStorage.getItem('access_token')
  if (!token) return

  userStore.fetchNotificationCount()
  userStore.fetchNotifications()
  memberStore.fetchMembers()
  checkActiveRecording()

  // 刷新用户信息，获取新鲜头像 URL
  try {
    const res = await axios.get('/api/v1/auth/me')
    const fresh = res.data
    const stored = JSON.parse(localStorage.getItem('user_info') || '{}')
    Object.assign(stored, fresh)
    localStorage.setItem('user_info', JSON.stringify(stored))
    userStore.loadFromStorage()
  } catch {
    // localStorage 兜底
  }
})

const handleLogout = () => {
  userStore.logout()
  ElMessage.success('已退出登录')
  router.push('/login')
}

const handleMarkAllRead = async () => {
  if (notificationCount.value === 0) return
  try {
    await axios.post('/api/v1/reminders/mark-read')
    userStore.notificationCount = 0
    userStore.notifications = []
    ElMessage.success('已全部标为已读')
  } catch {
    ElMessage.error('操作失败')
  }
}

const handlePopoverShow = () => {
  userStore.fetchNotifications()
}

const goToTask = (taskId) => {
  router.push('/tasks')
}

const formatTime = (t) => {
  if (!t) return ''
  return dayjs(t).add(8, 'hour').format('MM-DD HH:mm')
}
</script>

<style scoped>
.layout-container {
  height: 100vh;
}

/* ===== 桌面端侧边栏 ===== */
.aside {
  /* v77 P2.5: backdrop-filter 由 .glass 工具类提供 (assets/glass.css)
     保留 --color-bg-sidebar 专属 token 风格（不与 .glass 默认 --color-bg-card 冲突） */
  background: var(--color-bg-sidebar);
  border-right: 1px solid var(--color-sidebar-border);
  box-shadow: var(--shadow-sidebar);
  transition: width 0.3s;
  overflow: hidden;
  position: relative;
}

.logo {
  height: 64px;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 12px;
  border-bottom: 1px solid var(--color-sidebar-border);
  padding: 0 16px;
}

.logo-icon {
  width: 40px;
  height: 40px;
  background: linear-gradient(135deg, var(--color-primary) 0%, var(--color-accent) 100%);
  border-radius: var(--radius-lg);
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--color-bg-card);
  flex-shrink: 0;
  box-shadow: var(--shadow-primary);
}

.logo .title {
  white-space: nowrap;
  font-size: 17px;
  font-weight: var(--font-weight-bold);
  color: var(--color-text-primary);
}

.sidebar-menu {
  background: transparent !important;
  border-right: none;
  padding: 8px;
}

.sidebar-menu .el-menu-item {
  height: 48px;
  line-height: 48px;
  margin: 4px 0;
  border-radius: var(--radius-lg);
  color: var(--color-text-primary);
  font-weight: var(--font-weight-medium);
  font-size: var(--font-size-base);
  transition: all var(--transition-all-normal) var(--ease-out);
  position: relative;
  overflow: hidden;
}

.sidebar-menu .el-menu-item::before {
  content: '';
  position: absolute;
  left: 0;
  top: 50%;
  transform: translateY(-50%);
  width: 0;
  height: 0;
  background: var(--color-primary);
  border-radius: 0 var(--radius-sm) var(--radius-sm) 0;
  transition: all var(--transition-all-normal) var(--ease-out);
}

.sidebar-menu .el-menu-item:hover {
  background: rgba(var(--color-primary-rgb), 0.12) !important;
  color: var(--color-primary);
}

.sidebar-menu .el-menu-item:hover::before {
  width: 4px;
  height: 24px;
}

.sidebar-menu .el-menu-item.is-active {
  background: var(--color-primary) !important;
  color: var(--color-bg-card) !important;
  font-weight: var(--font-weight-bold);
}

.sidebar-menu .el-menu-item.is-active::before {
  width: 4px;
  height: 32px;
  background: rgba(255, 255, 255, 0.9);
}

.sidebar-menu .el-menu-item .el-icon {
  font-size: 18px;
}

.el-menu--collapse .sidebar-menu .el-menu-item {
  justify-content: center;
  padding: 0 12px;
}

/* ===== 侧边栏底部 ===== */
.sidebar-bottom {
  position: absolute;
  bottom: 0;
  left: 0;
  right: 0;
  padding: 8px;
  border-top: 1px solid var(--color-border);
}

.sidebar-bottom-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px 16px;
  border-radius: var(--radius-md);
  cursor: pointer;
  color: var(--color-text-secondary);
  font-size: var(--font-size-sm);
  transition: all var(--duration-fast) var(--ease-out);
}

.sidebar-bottom-item:hover {
  background: rgba(var(--color-primary-rgb), 0.1);
  color: var(--color-primary);
}

.sidebar-bottom-item.active {
  background: var(--color-primary);
  color: var(--color-bg-card);
  font-weight: var(--font-weight-bold);
}

/* ===== 顶部栏 ===== */
.header :deep(.el-avatar) {
  border-radius: var(--radius-lg);
}

.header {
  background: var(--color-bg-card);
  display: flex;
  align-items: center;
  justify-content: space-between;
  box-shadow: var(--shadow-sm);
  padding: 0 20px;
  border-bottom: 1px solid var(--color-border);
}

.header-left {
  display: flex;
  align-items: center;
  gap: 20px;
}

.collapse-btn {
  cursor: pointer;
  font-size: 20px;
  color: var(--color-text-secondary);
  transition: color 200ms var(--ease-out);
  padding: 6px;
  border-radius: var(--radius-md);
}

.collapse-btn:hover {
  color: var(--color-primary);
  background: var(--color-primary-bg);
}

.collapse-btn-mobile {
  font-size: 24px !important;
  padding: 10px !important;
  min-width: 44px;
  min-height: 44px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--color-primary-bg);
  color: var(--color-primary);
  border-radius: var(--radius-lg);
}

.collapse-btn-mobile:hover {
  background: rgba(var(--color-primary-rgb), 0.2);
}

.header-right {
  display: flex;
  align-items: center;
  gap: 20px;
}

.badge {
  cursor: pointer;
}

.bell-icon {
  cursor: pointer;
  transition: all var(--transition-all-normal) var(--ease-out);
  color: var(--color-text-regular, #606266);
  padding: 10px;
  border-radius: 50%;
  background: rgba(144, 147, 153, 0.1);
  border: 1px solid rgba(144, 147, 153, 0.15);
}

.bell-icon:hover {
  color: var(--color-primary);
  background: var(--color-primary-bg);
  border-color: var(--color-primary-light, #FF9D85);
  transform: scale(1.1);
  box-shadow: 0 2px 8px rgba(var(--color-primary-rgb), 0.2);
}

.user-info {
  display: flex;
  align-items: center;
  gap: 10px;
  cursor: pointer;
  padding: 6px 10px;
  border-radius: var(--radius-lg);
  transition: background 200ms var(--ease-out);
}

.user-info:hover {
  background: var(--color-bg-warm);
}

.user-detail {
  display: flex;
  flex-direction: column;
}

.username {
  font-size: 14px;
  color: var(--color-text-primary);
  font-weight: var(--font-weight-medium);
  line-height: 1.2;
}

.user-role {
  font-size: 12px;
  color: var(--color-text-secondary);
}

.main {
  background-color: var(--color-bg-page);
  padding: 20px;
  overflow-y: auto;
}

.main.mobile-main {
  padding: 12px;
}

/* ===== 移动端独立抽屉 ===== */
.mobile-drawer-root {
  position: fixed;
  inset: 0;
  z-index: 3000;
}

.mobile-drawer-mask {
  position: absolute;
  inset: 0;
  background: rgba(0, 0, 0, 0.35);
}

.mobile-drawer-body {
  position: absolute;
  top: 0;
  left: 0;
  width: 260px;
  height: 100%;
  background: var(--color-bg-card);
  overflow-y: auto;
  padding: 20px 12px;
  box-shadow: var(--shadow-sidebar);
}

.mobile-drawer-brand {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 8px 8px 20px;
  border-bottom: 1px solid #EBEEF5;
  margin-bottom: 8px;
  font-size: 18px;
  font-weight: 700;
  color: var(--color-text-primary);
}

.mobile-drawer-logo {
  width: 40px;
  height: 40px;
  background: var(--gradient-welcome-hero);
  border-radius: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--color-bg-card);
  flex-shrink: 0;
}

.mobile-drawer-item {
  display: flex;
  align-items: center;
  gap: 14px;
  height: 52px;
  padding: 0 12px;
  margin: 4px 0;
  border-radius: 12px;
  color: var(--color-text-primary);
  font-size: 15px;
  font-weight: 600;
  cursor: pointer;
}

.mobile-drawer-item:active {
  background: rgba(var(--color-primary-rgb), 0.1);
}

.mobile-drawer-item.active {
  background: var(--color-primary);
  color: var(--color-bg-card);
}

/* ===== 移动端抽屉过渡动画 ===== */

/* --- 根容器淡入 --- */
.mobile-drawer-enter-active {
  transition: opacity 0.35s var(--ease-in-out);
}
.mobile-drawer-leave-active {
  transition: opacity 0.3s var(--ease-in);
}
.mobile-drawer-enter-from,
.mobile-drawer-leave-to {
  opacity: 0;
}

/* --- 遮罩：淡入 + backdrop-blur 渐变 --- */
.mobile-drawer-enter-active .mobile-drawer-mask {
  animation: drawer-mask-in 0.35s var(--ease-in-out) both;
}
.mobile-drawer-leave-active .mobile-drawer-mask {
  animation: drawer-mask-out 0.3s var(--ease-in) both;
}

@keyframes drawer-mask-in {
  from { opacity: 0; backdrop-filter: blur(0px); }
  to   { opacity: 1; backdrop-filter: blur(4px); }
}
@keyframes drawer-mask-out {
  from { opacity: 1; backdrop-filter: blur(4px); }
  to   { opacity: 0; backdrop-filter: blur(0px); }
}

/* --- 抽屉主体：弹性滑入 + 干脆滑出 --- */
.mobile-drawer-enter-active .mobile-drawer-body {
  animation: drawer-slide-in 0.4s var(--ease-bounce) both;
}
.mobile-drawer-leave-active .mobile-drawer-body {
  animation: drawer-slide-out 0.28s var(--ease-in) both;
}

@keyframes drawer-slide-in {
  from { transform: translateX(-100%); }
  to   { transform: translateX(0); }
}
@keyframes drawer-slide-out {
  from { transform: translateX(0); }
  to   { transform: translateX(-100%); }
}

/* --- 品牌区：logo 缩放弹出 + 文字淡入 --- */
.mobile-drawer-enter-active .mobile-drawer-logo {
  animation: logo-pop-in 0.4s var(--ease-bounce) both;
  animation-delay: 80ms;
}
.mobile-drawer-enter-active .mobile-drawer-brand span {
  animation: brand-text-in 0.3s var(--ease-out) both;
  animation-delay: 120ms;
}

@keyframes logo-pop-in {
  from { scale: 0; opacity: 0; }
  to   { scale: 1; opacity: 1; }
}
@keyframes brand-text-in {
  from { opacity: 0; transform: translateX(-8px); }
  to   { opacity: 1; transform: translateX(0); }
}

/* --- 菜单项：弹簧逐个弹出 + 反向退出 --- */
.mobile-drawer-enter-active .mobile-drawer-item {
  animation: drawer-item-in 0.45s var(--ease-bounce) both;
  animation-delay: calc(var(--i, 0) * 60ms + 180ms);
}
.mobile-drawer-leave-active .mobile-drawer-item {
  animation: drawer-item-out 0.2s ease-in both;
  animation-delay: calc((3 - var(--i, 0)) * 40ms);
}

@keyframes drawer-item-in {
  from { opacity: 0; transform: translateX(-16px) scale(0.9); }
  to   { opacity: 1; transform: translateX(0) scale(1); }
}
@keyframes drawer-item-out {
  from { opacity: 1; transform: translateX(0) scale(1); }
  to   { opacity: 0; transform: translateX(-16px) scale(0.95); }
}

/* --- 汉堡图标旋转过渡 --- */
.icon-swap-enter-active,
.icon-swap-leave-active {
  transition: var(--transition-all-slow) var(--ease-out);
}
.icon-swap-enter-from {
  opacity: 0;
  transform: rotate(-90deg) scale(0.6);
}
.icon-swap-leave-to {
  opacity: 0;
  transform: rotate(90deg) scale(0.6);
}

/* ===== 通知面板 ===== */
.notification-panel {
  max-height: 400px;
  overflow-y: auto;
}

.notification-panel-title {
  font-size: 15px;
  font-weight: 600;
  color: var(--color-text-primary);
  padding-bottom: 12px;
  border-bottom: 1px solid #EBEEF5;
  margin-bottom: 12px;
}

.notification-panel-body {
  padding: 4px 0;
}

.notification-panel-body p {
  margin: 0 0 12px;
  font-size: 14px;
  color: var(--color-text-regular);
}

.notification-item {
  display: flex;
  flex-direction: column;
  gap: 4px;
  padding: 10px 12px;
  margin: 0 -12px;
  border-bottom: 1px solid #F2F3F5;
  cursor: pointer;
  transition: background 0.15s;
}

.notification-item:last-of-type {
  border-bottom: none;
}

.notification-item:hover {
  background: rgba(var(--color-primary-rgb), 0.06);
}

.notification-item-title {
  font-size: 14px;
  font-weight: 500;
  color: var(--color-text-primary);
  line-height: 1.4;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.notification-item-time {
  font-size: 12px;
  color: var(--color-info);
}

.mark-read-btn {
  margin-top: 8px;
  width: 100%;
}

.notification-panel-footer {
  padding-top: 12px;
  border-top: 1px solid #EBEEF5;
  margin-top: 8px;
}

/* ===== 全局浮动录音指示器 ===== */
.recording-indicator {
  position: fixed;
  bottom: 24px;
  right: 24px;
  z-index: 2900;
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 12px 20px;
  background: linear-gradient(135deg, var(--color-primary), var(--color-danger));
  color: var(--color-bg-card);
  border-radius: 50px;
  box-shadow: 0 4px 20px rgba(var(--color-primary-rgb), 0.4), 0 0 0 2px rgba(255, 255, 255, 0.2);
  cursor: pointer;
  font-size: 14px;
  font-weight: 600;
  transition: var(--transition-all-normal) ease;
  backdrop-filter: blur(12px);
  user-select: none;
}

.recording-indicator:hover {
  transform: translateY(-2px);
  box-shadow: 0 6px 24px rgba(255, 107, 107, 0.5), 0 0 0 2px rgba(255, 255, 255, 0.3);
}

.recording-dot {
  width: 10px;
  height: 10px;
  background: var(--color-bg-card);
  border-radius: 50%;
  flex-shrink: 0;
  animation: var(--animation-recording-pulse);
}

.recording-text {
  white-space: nowrap;
}

/* 离线状态 — 胶囊变橙红色，加警告图标 */
.recording-indicator.is-offline {
  background: linear-gradient(135deg, var(--color-danger), var(--color-primary-light));
  box-shadow: 0 4px 16px rgba(245, 108, 108, 0.5);
}
.recording-indicator.is-offline:hover {
  box-shadow: 0 6px 24px rgba(245, 108, 108, 0.6), 0 0 0 2px rgba(255, 255, 255, 0.3);
}
.recording-warning {
  font-size: 14px;
  animation: recording-pulse 1s var(--ease-in-out) infinite;
}

.recording-title {
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  max-width: 160px;
  opacity: 0.9;
  font-weight: 500;
}

.recording-arrow {
  flex-shrink: 0;
  transition: transform 0.2s;
}

.recording-indicator:hover .recording-arrow {
  transform: translateX(3px);
}

/* 录音指示器入场/退场动画 */
.recording-banner-enter-active {
  animation: var(--animation-banner-in);
}
.recording-banner-leave-active {
  animation: var(--animation-banner-out);
}

/* 窄屏适配（PR #2 增强：考虑 TabBar + Safe Area） */
@media (max-width: 768px) {
  /* 主内容区底部预留 TabBar 高度 + safe-area */
  .mobile-main {
    /* 给底部 TabBar 留出空间 */
    padding-bottom: calc(var(--tabbar-height, 56px) + var(--sab, 0px));
  }

  /* 录音指示器在 TabBar 上方 */
  .recording-indicator {
    bottom: calc(var(--tabbar-height, 56px) + var(--sab, 0px) + 12px);
    right: 16px;
    left: 16px;
    padding: 14px 18px;
    justify-content: center;
  }
  .recording-title {
    max-width: 120px;
  }

  .logo .title {
    font-size: 18px;
  }

  .header {
    padding: 0 var(--mobile-padding-x, 16px);
  }

  .header-right {
    gap: 8px;
  }

  .bell-icon {
    padding: 10px;
    border-radius: var(--radius-lg);
    min-width: var(--touch-target-min, 44px);
    min-height: var(--touch-target-min, 44px);
    display: flex;
    align-items: center;
    justify-content: center;
  }

  .user-info {
    padding: 4px 8px;
  }

  .user-info :deep(.el-avatar) {
    width: 36px !important;
    height: 36px !important;
  }
}
</style>

<!-- v69 P0: MainLayout dark mode 覆盖（v60-v67 教训：dark 跨组件规则必须放非 scoped 块） -->
<style>
  /* === 侧边栏 === */
  [data-theme="dark"] .aside {
    background: var(--color-bg-sidebar);
    border-right-color: var(--color-sidebar-border);
    box-shadow: var(--shadow-sidebar);
  }
  [data-theme="dark"] .sidebar-logo {
    background: transparent;
    color: var(--color-text-primary);
    border-bottom: 1px solid var(--color-border-light);
  }
  [data-theme="dark"] .sidebar-menu .el-menu-item,
  [data-theme="dark"] .sidebar-menu .el-sub-menu__title {
    color: var(--color-text-regular);
  }
  [data-theme="dark"] .sidebar-menu .el-menu-item:hover,
  [data-theme="dark"] .sidebar-menu .el-sub-menu__title:hover {
    background-color: rgba(var(--color-primary-rgb), 0.08) !important;
    color: var(--color-primary) !important;
  }
  [data-theme="dark"] .sidebar-menu .el-menu-item.is-active {
    background-color: var(--color-primary-bg) !important;
    color: var(--color-primary) !important;
  }
  [data-theme="dark"] .sidebar-bottom {
    border-top: 1px solid var(--color-border-light);
    background: transparent;
  }
  [data-theme="dark"] .sidebar-bottom-item {
    color: var(--color-text-secondary);
  }
  [data-theme="dark"] .sidebar-bottom-item:hover {
    background: var(--color-bg-hover);
    color: var(--color-text-primary);
  }

  /* === 顶栏 === */
  [data-theme="dark"] .header {
    background: var(--color-bg-card);
    border-bottom: 1px solid var(--color-border-light);
  }
  [data-theme="dark"] .bell-icon,
  [data-theme="dark"] .collapse-btn,
  [data-theme="dark"] .breadcrumb-text {
    color: var(--color-text-regular);
  }
  [data-theme="dark"] .bell-icon:hover,
  [data-theme="dark"] .collapse-btn:hover,
  [data-theme="dark"] .breadcrumb-text:hover {
    background: var(--color-bg-hover);
  }
  [data-theme="dark"] .user-info { color: var(--color-text-primary); }
  [data-theme="dark"] .user-info:hover { background: var(--color-bg-warm); }
  [data-theme="dark"] .user-name { color: var(--color-text-primary); }
  [data-theme="dark"] .user-role { color: var(--color-text-secondary); }

  /* === 通知面板（之前是硬编码 light 孤岛） === */
  [data-theme="dark"] .notification-panel {
    background: var(--color-bg-card);
    border: 1px solid var(--color-border-base);
    box-shadow: var(--shadow-md);
  }
  [data-theme="dark"] .notification-header {
    border-bottom: 1px solid var(--color-border-light);
    color: var(--color-text-primary);
  }
  [data-theme="dark"] .notification-item {
    border-bottom: 1px solid var(--color-border-light);
  }
  [data-theme="dark"] .notification-item:hover { background: var(--color-bg-hover); }
  [data-theme="dark"] .notification-item .notification-title { color: var(--color-text-primary); }
  [data-theme="dark"] .notification-item .notification-time { color: var(--color-text-secondary); }

  /* === 录音 banner + 浮动胶囊 === */
  [data-theme="dark"] .recording-banner,
  [data-theme="dark"] .global-recorder-pulse {
    background: var(--color-bg-card);
    border: 1px solid var(--color-border-base);
    color: var(--color-text-primary);
  }

  /* === 移动端 drawer === */
  [data-theme="dark"] .mobile-drawer { background: var(--color-bg-card) !important; }
</style>
