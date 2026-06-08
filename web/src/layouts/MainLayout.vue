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
          <el-icon size="20"><component :is="item.meta.icon" /></el-icon>
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
      class="aside"
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
          <el-icon><component :is="route.meta.icon" /></el-icon>
          <template #title><span style="color:inherit">{{ route.meta.title }}</span></template>
        </el-menu-item>
      </el-menu>
    </el-aside>

    <!-- 主内容区 -->
    <el-container>
      <!-- 顶部栏 -->
      <el-header class="header">
        <div class="header-left">
          <el-icon :class="['collapse-btn', { 'collapse-btn-mobile': isMobile }]" @click="toggleSidebar">
            <template v-if="!isMobile">
              <Fold v-if="!isCollapse" />
              <Expand v-else />
            </template>
            <template v-else>
              <Transition name="icon-swap" mode="out-in">
                <Fold v-if="!showMobileMenu" key="fold" />
                <Expand v-else key="expand" />
              </Transition>
            </template>
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
                <el-icon :size="isMobile ? 26 : 24" class="bell-icon"><Bell /></el-icon>
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
                <p v-else style="color:#909399;text-align:center;padding:20px 0">暂无新提醒</p>
              </div>
              <div class="notification-panel-footer">
                <el-button text size="small" @click="router.push('/tasks')">查看我的任务</el-button>
              </div>
            </div>
          </el-popover>

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
</template>

<script setup>
import { ref, computed, onMounted, onBeforeUnmount } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import axios from 'axios'
import dayjs from 'dayjs'
import { useUserStore } from '@/stores/user'
import { useMemberStore } from '@/stores/member'

const route = useRoute()
const router = useRouter()
const userStore = useUserStore()
const memberStore = useMemberStore()

const isMobile = ref(window.innerWidth <= 768)
const isCollapse = ref(false)
const showMobileMenu = ref(false)
const popoverVisible = ref(false)

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
  return (mainRoute?.children || []).filter(r => r.meta?.icon)
})

const onResize = () => {
  isMobile.value = window.innerWidth <= 768
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
  window.addEventListener('resize', onResize)
  userStore.loadFromStorage()
  userStore.fetchNotificationCount()
  userStore.fetchNotifications()
  memberStore.fetchMembers()

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

onBeforeUnmount(() => {
  window.removeEventListener('resize', onResize)
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
  background: var(--color-bg-sidebar);
  backdrop-filter: blur(16px);
  border-right: 1px solid var(--color-sidebar-border);
  box-shadow: var(--shadow-sidebar);
  transition: width 0.3s;
  overflow: hidden;
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
  color: #fff;
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
  transition: all 200ms ease-out;
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
  transition: all 200ms ease-out;
}

.sidebar-menu .el-menu-item:hover {
  background: rgba(255, 122, 92, 0.12) !important;
  color: var(--color-primary);
}

.sidebar-menu .el-menu-item:hover::before {
  width: 4px;
  height: 24px;
}

.sidebar-menu .el-menu-item.is-active {
  background: var(--color-primary) !important;
  color: #ffffff !important;
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
  transition: color 200ms ease-out;
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
  background: rgba(255, 122, 92, 0.2);
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
  transition: all 200ms ease-out;
  color: var(--color-text-secondary);
  padding: 8px;
  border-radius: 50%;
  background: rgba(144, 147, 153, 0.06);
}

.bell-icon:hover {
  color: var(--color-primary);
  background: var(--color-primary-bg);
  transform: scale(1.1);
}

.user-info {
  display: flex;
  align-items: center;
  gap: 10px;
  cursor: pointer;
  padding: 6px 10px;
  border-radius: var(--radius-lg);
  transition: background 200ms ease-out;
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
  background: #fff;
  overflow-y: auto;
  padding: 20px 12px;
  box-shadow: 2px 0 20px rgba(0, 0, 0, 0.12);
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
  color: #2D2D2D;
}

.mobile-drawer-logo {
  width: 40px;
  height: 40px;
  background: linear-gradient(135deg, #FF7A5C 0%, #FFB347 100%);
  border-radius: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #fff;
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
  color: #333;
  font-size: 15px;
  font-weight: 600;
  cursor: pointer;
}

.mobile-drawer-item:active {
  background: rgba(255, 122, 92, 0.1);
}

.mobile-drawer-item.active {
  background: #FF7A5C;
  color: #fff;
}

/* ===== 移动端抽屉过渡动画 ===== */

/* --- 根容器淡入 --- */
.mobile-drawer-enter-active {
  transition: opacity 0.35s cubic-bezier(0.4, 0, 0.2, 1);
}
.mobile-drawer-leave-active {
  transition: opacity 0.3s cubic-bezier(0.4, 0, 1, 1);
}
.mobile-drawer-enter-from,
.mobile-drawer-leave-to {
  opacity: 0;
}

/* --- 遮罩：淡入 + backdrop-blur 渐变 --- */
.mobile-drawer-enter-active .mobile-drawer-mask {
  animation: drawer-mask-in 0.35s cubic-bezier(0.4, 0, 0.2, 1) both;
}
.mobile-drawer-leave-active .mobile-drawer-mask {
  animation: drawer-mask-out 0.3s cubic-bezier(0.4, 0, 1, 1) both;
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
  animation: drawer-slide-in 0.4s cubic-bezier(0.34, 1.56, 0.64, 1) both;
}
.mobile-drawer-leave-active .mobile-drawer-body {
  animation: drawer-slide-out 0.28s cubic-bezier(0.4, 0, 1, 1) both;
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
  animation: logo-pop-in 0.4s cubic-bezier(0.34, 1.56, 0.64, 1) both;
  animation-delay: 80ms;
}
.mobile-drawer-enter-active .mobile-drawer-brand span {
  animation: brand-text-in 0.3s ease-out both;
  animation-delay: 120ms;
}

@keyframes logo-pop-in {
  from { transform: scale(0); opacity: 0; }
  to   { transform: scale(1); opacity: 1; }
}
@keyframes brand-text-in {
  from { opacity: 0; transform: translateX(-8px); }
  to   { opacity: 1; transform: translateX(0); }
}

/* --- 菜单项：弹簧逐个弹出 + 反向退出 --- */
.mobile-drawer-enter-active .mobile-drawer-item {
  animation: drawer-item-in 0.45s cubic-bezier(0.34, 1.56, 0.64, 1) both;
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
  transition: all 0.25s ease-out;
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
  color: #303133;
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
  color: #606266;
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
  background: rgba(255, 122, 92, 0.06);
}

.notification-item-title {
  font-size: 14px;
  font-weight: 500;
  color: #303133;
  line-height: 1.4;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.notification-item-time {
  font-size: 12px;
  color: #909399;
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

/* 窄屏适配 */
@media (max-width: 768px) {
  .logo .title {
    font-size: 18px;
  }

  .header {
    padding: 0 12px;
  }

  .header-right {
    gap: 8px;
  }

  .bell-icon {
    padding: 10px;
    border-radius: var(--radius-lg);
    min-width: 40px;
    min-height: 40px;
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
