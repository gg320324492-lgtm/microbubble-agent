<template>
  <!-- 移动端独立抽屉 -->
  <Transition name="mobile-drawer">
    <div v-if="isMobile && showMobileMenu" class="mobile-drawer-root">
      <div class="mobile-drawer-mask" @click="showMobileMenu = false" />
      <div class="mobile-drawer-body">
        <div class="mobile-drawer-brand">
          <div class="mobile-drawer-logo">
            <span>M</span>
          </div>
          <span>MicroBubble</span>
        </div>
        <div
          v-for="(item, index) in menuRoutes"
          :key="item.path"
          class="mobile-drawer-item"
          :class="{ active: currentRoute === item.path }"
          :style="{ '--i': index }"
          @click="navigateTo(item.path)"
        >
          <span class="drawer-icon">{{ getIcon(item.meta.icon) }}</span>
          <span>{{ item.meta.title }}</span>
        </div>
      </div>
    </div>
  </Transition>

  <div class="layout-container">
    <!-- 桌面端侧边栏 -->
    <aside v-if="!isMobile" class="sidebar" :class="{ collapsed: isCollapse }">
      <div class="sidebar-logo" @click="isCollapse = !isCollapse">
        <div class="logo-icon">
          <span>M</span>
        </div>
        <span v-show="!isCollapse" class="logo-text">MicroBubble</span>
      </div>

      <nav class="sidebar-nav">
        <div
          v-for="route in menuRoutes"
          :key="route.path"
          class="nav-item"
          :class="{ active: currentRoute === route.path }"
          @click="navigateTo(route.path)"
        >
          <span class="nav-icon">{{ getIcon(route.meta.icon) }}</span>
          <span v-show="!isCollapse" class="nav-text">{{ route.meta.title }}</span>
        </div>
      </nav>
    </aside>

    <!-- 主内容区 -->
    <div class="main-container">
      <!-- 顶部栏 -->
      <header class="header">
        <div class="header-left">
          <button class="menu-btn" @click="toggleSidebar">
            <span v-if="isMobile">☰</span>
            <span v-else>{{ isCollapse ? '☰' : '✕' }}</span>
          </button>
          <div v-if="!isMobile" class="breadcrumb">
            <span class="breadcrumb-home" @click="navigateTo('/dashboard')">首页</span>
            <span class="breadcrumb-separator">/</span>
            <span class="breadcrumb-current">{{ currentTitle }}</span>
          </div>
        </div>

        <div class="header-right">
          <div class="notification-btn" @click="showNotifications = !showNotifications">
            <span>🔔</span>
            <span v-if="notificationCount > 0" class="notification-badge">{{ notificationCount }}</span>
          </div>
          <div class="user-avatar" @click="showUserMenu = !showUserMenu">
            <span>{{ userInitial }}</span>
          </div>
        </div>
      </header>

      <!-- 内容区 -->
      <main class="content">
        <router-view />
      </main>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useRouter, useRoute } from 'vue-router'

const router = useRouter()
const route = useRoute()

// 响应式状态
const isCollapse = ref(false)
const isMobile = ref(false)
const showMobileMenu = ref(false)
const showNotifications = ref(false)
const showUserMenu = ref(false)
const notificationCount = ref(3)
const userInitial = ref('张')

// 路由相关
const currentRoute = computed(() => route.path)
const currentTitle = computed(() => {
  const matched = route.matched
  if (matched.length > 0) {
    return matched[matched.length - 1].meta.title || ''
  }
  return ''
})

// 菜单路由
const menuRoutes = computed(() => {
  return router.getRoutes()
    .filter(r => r.meta?.icon && r.path !== '/')
    .map(r => ({
      path: r.path,
      meta: r.meta
    }))
})

// 图标映射
const iconMap = {
  'Odometer': '📊',
  'ChatDotRound': '💬',
  'List': '✅',
  'VideoCamera': '📅',
  'Folder': '📁',
  'User': '👥',
  'Document': '📚',
  'Memo': '📝',
  'Mic': '🎤',
  'Setting': '⚙️'
}

const getIcon = (iconName) => {
  return iconMap[iconName] || '📄'
}

// 方法
const navigateTo = (path) => {
  router.push(path)
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

// 响应式检测
const checkMobile = () => {
  isMobile.value = window.innerWidth < 768
}

onMounted(() => {
  checkMobile()
  window.addEventListener('resize', checkMobile)
})

onUnmounted(() => {
  window.removeEventListener('resize', checkMobile)
})
</script>

<style scoped>
/* 布局容器 */
.layout-container {
  display: flex;
  min-height: 100vh;
  background: var(--color-bg-page);
}

/* 侧边栏 */
.sidebar {
  width: var(--sidebar-width);
  background: var(--color-bg-sidebar);
  border-right: 1px solid var(--color-border);
  transition: width var(--duration-normal) var(--ease-out);
  position: fixed;
  top: 0;
  left: 0;
  bottom: 0;
  z-index: 100;
  display: flex;
  flex-direction: column;
}

.sidebar.collapsed {
  width: var(--sidebar-collapsed-width);
}

.sidebar-logo {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 24px;
  border-bottom: 1px solid var(--color-border);
  cursor: pointer;
  transition: all var(--duration-fast) var(--ease-out);
}

.sidebar-logo:hover {
  background: var(--color-bg-hover);
}

.logo-icon {
  width: 40px;
  height: 40px;
  background: var(--color-primary);
  border-radius: var(--radius-md);
  display: flex;
  align-items: center;
  justify-content: center;
  color: white;
  font-weight: 700;
  font-size: 18px;
  flex-shrink: 0;
}

.logo-text {
  font-size: 18px;
  font-weight: 700;
  color: var(--color-text-primary);
  white-space: nowrap;
}

/* 导航菜单 */
.sidebar-nav {
  flex: 1;
  padding: 16px 0;
  overflow-y: auto;
}

.nav-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px 24px;
  cursor: pointer;
  transition: all var(--duration-fast) var(--ease-out);
  color: var(--color-text-secondary);
  font-size: var(--font-size-base);
  font-weight: var(--font-weight-medium);
}

.nav-item:hover {
  background: var(--color-bg-hover);
  color: var(--color-text-primary);
}

.nav-item.active {
  background: var(--color-bg-active);
  color: var(--color-text-primary);
}

.nav-icon {
  font-size: 18px;
  width: 24px;
  text-align: center;
  flex-shrink: 0;
}

.nav-text {
  white-space: nowrap;
}

/* 主内容区 */
.main-container {
  flex: 1;
  margin-left: var(--sidebar-width);
  transition: margin-left var(--duration-normal) var(--ease-out);
  display: flex;
  flex-direction: column;
}

.sidebar.collapsed + .main-container {
  margin-left: var(--sidebar-collapsed-width);
}

/* 顶部栏 */
.header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16px 32px;
  background: white;
  border-bottom: 1px solid var(--color-border);
  position: sticky;
  top: 0;
  z-index: 50;
}

.header-left {
  display: flex;
  align-items: center;
  gap: 16px;
}

.menu-btn {
  background: none;
  border: none;
  font-size: 20px;
  cursor: pointer;
  padding: 8px;
  border-radius: var(--radius-sm);
  transition: all var(--duration-fast) var(--ease-out);
  color: var(--color-text-secondary);
}

.menu-btn:hover {
  background: var(--color-bg-hover);
  color: var(--color-text-primary);
}

.breadcrumb {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: var(--font-size-sm);
}

.breadcrumb-home {
  color: var(--color-text-tertiary);
  cursor: pointer;
}

.breadcrumb-home:hover {
  color: var(--color-text-primary);
}

.breadcrumb-separator {
  color: var(--color-text-placeholder);
}

.breadcrumb-current {
  color: var(--color-text-primary);
  font-weight: var(--font-weight-medium);
}

.header-right {
  display: flex;
  align-items: center;
  gap: 16px;
}

.notification-btn {
  position: relative;
  cursor: pointer;
  padding: 8px;
  border-radius: var(--radius-sm);
  transition: all var(--duration-fast) var(--ease-out);
}

.notification-btn:hover {
  background: var(--color-bg-hover);
}

.notification-badge {
  position: absolute;
  top: 0;
  right: 0;
  background: var(--color-danger);
  color: white;
  font-size: 10px;
  padding: 2px 6px;
  border-radius: var(--radius-full);
  min-width: 16px;
  text-align: center;
}

.user-avatar {
  width: 40px;
  height: 40px;
  background: linear-gradient(135deg, var(--color-accent), #FFB347);
  border-radius: var(--radius-full);
  display: flex;
  align-items: center;
  justify-content: center;
  color: white;
  font-weight: 600;
  cursor: pointer;
  transition: all var(--duration-fast) var(--ease-out);
}

.user-avatar:hover {
  transform: scale(1.05);
}

/* 内容区 */
.content {
  flex: 1;
  padding: 32px;
}

/* 移动端抽屉 */
.mobile-drawer-root {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  z-index: 1000;
}

.mobile-drawer-mask {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.5);
}

.mobile-drawer-body {
  position: absolute;
  top: 0;
  left: 0;
  bottom: 0;
  width: 280px;
  background: white;
  box-shadow: var(--shadow-lg);
}

.mobile-drawer-brand {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 24px;
  border-bottom: 1px solid var(--color-border);
}

.mobile-drawer-logo {
  width: 40px;
  height: 40px;
  background: var(--color-primary);
  border-radius: var(--radius-md);
  display: flex;
  align-items: center;
  justify-content: center;
  color: white;
  font-weight: 700;
  font-size: 18px;
}

.mobile-drawer-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 16px 24px;
  cursor: pointer;
  transition: all var(--duration-fast) var(--ease-out);
  color: var(--color-text-secondary);
  font-size: var(--font-size-base);
  font-weight: var(--font-weight-medium);
}

.mobile-drawer-item:hover {
  background: var(--color-bg-hover);
  color: var(--color-text-primary);
}

.mobile-drawer-item.active {
  background: var(--color-bg-active);
  color: var(--color-text-primary);
}

.drawer-icon {
  font-size: 18px;
  width: 24px;
  text-align: center;
}

/* 过渡动画 */
.mobile-drawer-enter-active,
.mobile-drawer-leave-active {
  transition: opacity var(--duration-normal) var(--ease-out);
}

.mobile-drawer-enter-active .mobile-drawer-body,
.mobile-drawer-leave-active .mobile-drawer-body {
  transition: transform var(--duration-normal) var(--ease-out);
}

.mobile-drawer-enter-from,
.mobile-drawer-leave-to {
  opacity: 0;
}

.mobile-drawer-enter-from .mobile-drawer-body,
.mobile-drawer-leave-to .mobile-drawer-body {
  transform: translateX(-100%);
}

/* 响应式 */
@media (max-width: 768px) {
  .sidebar {
    display: none;
  }

  .main-container {
    margin-left: 0;
  }

  .header {
    padding: 12px 16px;
  }

  .content {
    padding: 16px;
  }
}
</style>
