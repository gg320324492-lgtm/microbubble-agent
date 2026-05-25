<template>
  <!-- 诊断：显示 isMobile 和窗口宽度 -->
  <div style="position:fixed;top:4px;right:4px;z-index:99999;background:#000;color:#0f0;padding:4px 8px;font-size:11px;font-family:monospace;border-radius:4px;pointer-events:none;">
    isMobile:{{ isMobile }} w:{{ windowWidth }}
  </div>

  <!-- 移动端独立抽屉 — 在 el-container 外部，不受 Element Plus aside 样式影响 -->
  <div v-if="isMobile && showMobileMenu" class="mobile-drawer-root">
    <div class="mobile-drawer-mask" @click="showMobileMenu = false" />
    <div class="mobile-drawer-body">
      <!-- 诊断：极简纯文字，不用 el-icon，不用 SVG，看文字能否渲染 -->
      <div style="padding:8px 16px 20px;font-size:18px;font-weight:700;color:#2D2D2D;border-bottom:1px solid #EBEEF5;margin-bottom:8px;">
        小气助手
      </div>
      <div
        v-for="item in menuRoutes"
        :key="item.path"
        style="display:flex;align-items:center;height:52px;padding:0 16px;margin:4px 0;border-radius:12px;font-size:16px;font-weight:600;color:#333;cursor:pointer;"
        :style="currentRoute === item.path ? { background: '#FF7A5C', color: '#fff' } : {}"
        @click="navigateTo(item.path)"
      >
        {{ item.meta.title }}
      </div>
    </div>
  </div>

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
          :index="route.path"
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
          <el-icon class="collapse-btn" @click="toggleSidebar">
            <template v-if="!isMobile">
              <Fold v-if="!isCollapse" />
              <Expand v-else />
            </template>
            <template v-else>
              <Fold v-if="!showMobileMenu" />
              <Expand v-else />
            </template>
          </el-icon>
          <el-breadcrumb v-if="!isMobile" separator="/">
            <el-breadcrumb-item :to="{ path: '/' }">首页</el-breadcrumb-item>
            <el-breadcrumb-item>{{ currentTitle }}</el-breadcrumb-item>
          </el-breadcrumb>
        </div>

        <div class="header-right">
          <el-badge :value="notificationCount" :max="99" class="badge" :hidden="notificationCount === 0">
            <el-icon size="20" class="bell-icon" @click="markAllRead"><Bell /></el-icon>
          </el-badge>

          <el-dropdown>
            <div class="user-info">
              <el-avatar :size="32" icon="UserFilled" />
              <div v-if="!isMobile" class="user-detail">
                <span class="username">{{ username }}</span>
                <span class="user-role">{{ userRole }}</span>
              </div>
            </div>
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item>个人设置</el-dropdown-item>
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
import { useUserStore } from '@/stores/user'
import { useMemberStore } from '@/stores/member'

const route = useRoute()
const router = useRouter()
const userStore = useUserStore()
const memberStore = useMemberStore()

const windowWidth = ref(window.innerWidth)
const isMobile = ref(window.innerWidth <= 768)
const isCollapse = ref(false)
const showMobileMenu = ref(false)

const sidebarWidth = computed(() => {
  if (isMobile.value) return '0px'
  return isCollapse.value ? '64px' : '220px'
})

const currentRoute = computed(() => route.path)
const currentTitle = computed(() => route.meta?.title || '首页')
const username = computed(() => userStore.username)
const userRole = computed(() => userStore.userRole)
const notificationCount = computed(() => userStore.notificationCount)

const menuRoutes = computed(() => {
  const mainRoute = router.options.routes.find(r => r.path === '/')
  return mainRoute?.children || []
})

const onResize = () => {
  windowWidth.value = window.innerWidth
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
  router.push(path)
}

onMounted(() => {
  window.addEventListener('resize', onResize)
  userStore.loadFromStorage()
  userStore.fetchNotificationCount()
  memberStore.fetchMembers()
})

onBeforeUnmount(() => {
  window.removeEventListener('resize', onResize)
})

const handleLogout = () => {
  userStore.logout()
  ElMessage.success('已退出登录')
  router.push('/login')
}

const markAllRead = async () => {
  if (notificationCount.value === 0) return
  try {
    await axios.post('/api/v1/reminders/mark-read')
    userStore.notificationCount = 0
  } catch {
    // ignore
  }
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
  -webkit-backdrop-filter: blur(16px);
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
  transition: color 200ms ease-out;
  color: var(--color-text-secondary);
  padding: 6px;
  border-radius: var(--radius-md);
}

.bell-icon:hover {
  color: var(--color-primary);
  background: var(--color-primary-bg);
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

/* 窄屏适配 */
@media (max-width: 768px) {
  .logo .title {
    font-size: 18px;
  }
}
</style>
