<script setup>
/**
 * NavRail.vue — v78 UI-redesign 左侧 nav rail
 *
 * 设计: 替代 MainLayout 顶部菜单栏 hover popup 模式，左侧持久 nav rail
 * - 顶: 用户头像 + 名字
 * - 中: 6 个 nav icon (聊天 / 任务 / 会议 / 知识 / 协作 / 网盘)
 * - 底: ⚙️ 设置按钮 + 主题切换 (light/dark × orange/ocean/forest = 6 主题)
 *
 * W72 B-4 (派生新任务, 派工 v6 段 5 反馈 #5 实战):
 * - 6 主题 dark mode 适配: useThemeStore.accent × isDark
 * - 跨端点: useIsMobile() → 桌面端 fixed, 移动端 drawer (汉堡按钮触发)
 * - 6 类路由高亮: 派工 v6 段 5 反馈 #3 实战 type hint 必含
 * - 当前路由检测: useRoute() + route.path.startsWith(item.route)
 *
 * a11y 4-attr 全部就绪
 * dark mode 走非 scoped 块（v60-v67 教训）
 */
import { computed, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ChatDotRound, List, Calendar, DataAnalysis, Document, Notebook, Setting, Moon, Sunny, Folder } from '@element-plus/icons-vue'
import { useThemeStore } from '@/stores/useThemeStore'
import { useUserStore } from '@/stores/user'
import { useIsMobile } from '@/composables/useIsMobile'

/** @typedef {'orange'|'ocean'|'forest'} NavAccent — 6 主题的 accent 维度 (派工 v6 段 5 反馈 #3 实战) */

const route = useRoute()
const router = useRouter()
const themeStore = useThemeStore()
const userStore = useUserStore()
const { isMobile } = useIsMobile()

/** @type {Array<{name: string, label: string, icon: any, route: string}>} */
const navItems = [
  { name: 'chat', label: '聊天', icon: ChatDotRound, route: '/chat' },
  { name: 'task', label: '任务', icon: List, route: '/tasks' },
  { name: 'meeting', label: '会议', icon: Calendar, route: '/meetings' },
  { name: 'knowledge', label: '知识', icon: DataAnalysis, route: '/knowledge' },
  { name: 'workspace', label: '协作', icon: Document, route: '/workspace?tab=projects' },
  { name: 'drive', label: '网盘', icon: Folder, route: '/drive' },
]

const activeRoute = computed(() => route.path)
const userName = computed(() => userStore.userInfo?.name || '未登录')
const drawerOpen = ref(false)

/** 6 主题 dark mode 适配 — accent + isDark 双维度 (派工 v6 段 5 反馈 #5 实战) */
const accentName = computed(() => themeStore.accent)
const themeAttr = computed(() => `accent-${accentName.value}-${themeStore.isDark ? 'dark' : 'light'}`)

// 路由切换时关闭移动 drawer
watch(activeRoute, () => { drawerOpen.value = false })

const onNavClick = (item) => {
  router.push(item.route).catch(() => {})
  if (isMobile.value) drawerOpen.value = false
}

const onSettingsClick = () => {
  router.push('/settings').catch(() => {})
  if (isMobile.value) drawerOpen.value = false
}

const onAvatarClick = () => {
  router.push('/settings').catch(() => {})
  if (isMobile.value) drawerOpen.value = false
}

const onThemeToggle = () => {
  themeStore.toggle()
}

const onAccentClick = () => {
  // 循环 orange → ocean → forest → orange
  const order = themeStore.ACCENT_OPTIONS
  const idx = order.indexOf(themeStore.accent)
  const next = order[(idx + 1) % order.length]
  themeStore.setAccent(next)
}

const toggleDrawer = () => {
  drawerOpen.value = !drawerOpen.value
}
</script>

<template>
  <!-- 移动端汉堡按钮 (W72 B-4 跨端点) -->
  <button
    v-if="isMobile"
    id="nav-rail-hamburger"
    name="nav-rail-hamburger"
    class="nav-hamburger"
    :aria-label="drawerOpen ? '关闭菜单' : '打开菜单'"
    :aria-expanded="drawerOpen"
    @click="toggleDrawer"
  >
    <span class="hamburger-line" />
    <span class="hamburger-line" />
    <span class="hamburger-line" />
  </button>

  <nav
    class="nav-rail"
    :class="{ 'mobile-drawer': isMobile, 'drawer-open': drawerOpen }"
    :data-theme-accent="themeAttr"
    aria-label="主导航"
  >
    <!-- 顶部用户头像 -->
    <button
      id="nav-rail-avatar"
      name="nav-rail-avatar"
      class="nav-avatar"
      :aria-label="`当前用户 ${userName}, 打开设置`"
      :title="`${userName} - 设置`"
      @click="onAvatarClick"
    >
      <el-avatar :size="36" :src="userStore.userInfo?.avatar">
        {{ userStore.userInfo?.name?.[0] || '?' }}
      </el-avatar>
    </button>

    <!-- 主导航 icon 列 (6 类) -->
    <ul class="nav-list" role="menubar">
      <li
        v-for="item in navItems"
        :key="item.name"
        role="none"
        class="nav-item"
        :class="{ active: activeRoute.startsWith(item.route) }"
      >
        <button
          :id="`nav-rail-${item.name}`"
          :name="`nav-rail-${item.name}`"
          class="nav-icon-btn"
          role="menuitem"
          :aria-label="item.label"
          :title="item.label"
          :aria-current="activeRoute.startsWith(item.route) ? 'page' : undefined"
          @click="onNavClick(item)"
        >
          <el-icon :size="20"><component :is="item.icon" /></el-icon>
          <span class="nav-label">{{ item.label }}</span>
        </button>
      </li>
    </ul>

    <!-- 底部设置 + 主题切换 + accent 循环 (W72 B-4 6 主题) -->
    <div class="nav-rail-foot">
      <button
        id="nav-rail-accent"
        name="nav-rail-accent"
        class="nav-icon-btn"
        :aria-label="`当前主色 ${accentName}, 点击切换`"
        :title="`主色: ${accentName}`"
        :data-accent="accentName"
        @click="onAccentClick"
      >
        <span class="accent-dot" :data-accent="accentName" />
      </button>
      <button
        id="nav-rail-theme-toggle"
        name="nav-rail-theme-toggle"
        class="nav-icon-btn"
        :aria-label="themeStore.isDark ? '切换浅色' : '切换深色'"
        :title="themeStore.isDark ? '切换浅色' : '切换深色'"
        @click="onThemeToggle"
      >
        <el-icon :size="20">
          <component :is="themeStore.isDark ? Sunny : Moon" />
        </el-icon>
      </button>
      <button
        id="nav-rail-settings"
        name="nav-rail-settings"
        class="nav-icon-btn"
        aria-label="设置"
        title="设置"
        @click="onSettingsClick"
      >
        <el-icon :size="20"><Setting /></el-icon>
      </button>
    </div>
  </nav>
</template>

<style scoped>
.nav-rail {
  display: flex;
  flex-direction: column;
  align-items: center;
  width: 64px;
  min-height: 100vh;
  padding: 12px 0;
  background: var(--color-bg-card);
  border-right: 1px solid var(--color-border-light);
  flex-shrink: 0;
}

.nav-avatar {
  background: transparent;
  border: none;
  padding: 0;
  cursor: pointer;
  margin-bottom: 16px;
  border-radius: 50%;
}
.nav-avatar:hover { box-shadow: 0 0 0 3px var(--color-primary-bg); }

.nav-list {
  list-style: none;
  padding: 0;
  margin: 0;
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 8px;
  width: 100%;
}

.nav-item {
  display: flex;
  justify-content: center;
}

.nav-icon-btn {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 4px;
  width: 48px;
  height: 48px;
  background: transparent;
  border: none;
  border-radius: var(--radius-md);
  cursor: pointer;
  color: var(--color-text-secondary);
  transition: var(--transition-all-fast, all 0.15s ease);
  -webkit-tap-highlight-color: transparent;
}
.nav-icon-btn:hover { background: var(--color-bg-hover); color: var(--color-text-primary); }
.nav-icon-btn:focus-visible { outline: 2px solid var(--color-primary); outline-offset: 2px; }

.nav-item.active .nav-icon-btn {
  background: var(--color-primary-bg);
  color: var(--color-primary);
}

.nav-label {
  font-size: 10px;
  font-weight: 500;
  white-space: nowrap;
}

.nav-rail-foot {
  display: flex;
  flex-direction: column;
  gap: 4px;
  padding-top: 12px;
  border-top: 1px solid var(--color-border-light);
  width: 100%;
  align-items: center;
}

/* v78: 隐藏 nav-label 节省空间（仅 icon 显示） */
@media (max-height: 720px) {
  .nav-label { display: none; }
  .nav-icon-btn { width: 44px; height: 44px; }
}

/* ===== W72 B-4 派生新任务: 6 主题 + 跨端点 + 移动 drawer ===== */

/* 移动端汉堡按钮 — 只在 isMobile 时渲染 */
.nav-hamburger {
  position: fixed;
  top: 12px;
  left: 12px;
  z-index: 1100;
  display: flex;
  flex-direction: column;
  justify-content: center;
  align-items: center;
  gap: 4px;
  width: 36px;
  height: 36px;
  padding: 0;
  background: var(--color-bg-card);
  border: 1px solid var(--color-border-light);
  border-radius: var(--radius-md);
  cursor: pointer;
}
.hamburger-line {
  display: block;
  width: 18px;
  height: 2px;
  background: var(--color-text-primary);
  border-radius: 1px;
}

/* 移动端 drawer — 默认隐藏在左 -200px, drawer-open 时滑出 */
@media (max-width: 768px) {
  .nav-rail.mobile-drawer {
    position: fixed;
    top: 0;
    left: 0;
    z-index: 1000;
    transform: translateX(-100%);
    transition: transform 0.25s ease;
    height: 100vh;
    box-shadow: 2px 0 8px rgba(0, 0, 0, 0.15);
  }
  .nav-rail.mobile-drawer.drawer-open {
    transform: translateX(0);
  }
}

/* accent dot — 6 主题色点 */
.accent-dot {
  display: block;
  width: 16px;
  height: 16px;
  border-radius: 50%;
  border: 2px solid var(--color-border-light);
}
.accent-dot[data-accent="orange"] { background: #FF7A5C; }
.accent-dot[data-accent="ocean"]  { background: #4A90E2; }
.accent-dot[data-accent="forest"] { background: #5C9F6E; }

/* 6 主题 dark mode 适配 — 用 data-theme-accent 选择器 (派工 v6 段 5 反馈 #5 实战) */
.nav-rail[data-theme-accent="accent-orange-light"] { --rail-accent: #FF7A5C; }
.nav-rail[data-theme-accent="accent-orange-dark"]  { --rail-accent: #FF9B7E; }
.nav-rail[data-theme-accent="accent-ocean-light"]  { --rail-accent: #4A90E2; }
.nav-rail[data-theme-accent="accent-ocean-dark"]   { --rail-accent: #6FB1F5; }
.nav-rail[data-theme-accent="accent-forest-light"] { --rail-accent: #5C9F6E; }
.nav-rail[data-theme-accent="accent-forest-dark"]  { --rail-accent: #82B894; }

/* active state 用 --rail-accent (派工 v6 段 5 反馈 #3 实战: type hint NavAccent) */
.nav-item.active .nav-icon-btn {
  background: var(--rail-accent, var(--color-primary));
  color: #fff;
}
</style>

<!-- v78 + v77 教训 (v60-v67): dark mode 必须非 scoped 块 -->
<style>
[data-theme="dark"] .nav-rail {
  background: var(--color-bg-card);
  border-right-color: var(--color-border-light);
}
[data-theme="dark"] .nav-icon-btn { color: var(--color-text-secondary); }
[data-theme="dark"] .nav-icon-btn:hover { background: var(--color-bg-hover); color: var(--color-text-primary); }
[data-theme="dark"] .nav-item.active .nav-icon-btn {
  background: var(--color-primary-bg);
  color: var(--color-primary);
}
[data-theme="dark"] .nav-rail-foot { border-top-color: var(--color-border-light); }

/* W72 B-4: dark mode 下汉堡按钮 + drawer 适配 */
[data-theme="dark"] .nav-hamburger {
  background: var(--color-bg-card);
  border-color: var(--color-border-light);
}
[data-theme="dark"] .hamburger-line { background: var(--color-text-primary); }
[data-theme="dark"] .nav-rail.mobile-drawer {
  background: var(--color-bg-card);
  box-shadow: 2px 0 12px rgba(0, 0, 0, 0.5);
}
</style>
