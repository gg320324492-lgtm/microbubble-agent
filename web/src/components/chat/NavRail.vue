<script setup>
/**
 * NavRail.vue — v78 UI-redesign 左侧 nav rail
 *
 * 设计: 替代 MainLayout 顶部菜单栏 hover popup 模式，左侧持久 nav rail
 * - 顶: 用户头像 + 名字
 * - 中: 5 个 nav icon (聊天 / 任务 / 会议 / 知识 / 假设)
 * - 底: ⚙️ 设置按钮弹 ThemeSettingsDrawer
 *
 * a11y 4-attr 全部就绪
 * dark mode 走非 scoped 块（v60-v67 教训）
 */
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ChatDotRound, List, Calendar, DataAnalysis, Document, Notebook, Setting, Moon, Sunny } from '@element-plus/icons-vue'
import { useThemeStore } from '@/stores/useThemeStore'
import { useUserStore } from '@/stores/user'

const route = useRoute()
const router = useRouter()
const themeStore = useThemeStore()
const userStore = useUserStore()

const navItems = [
  { name: 'chat', label: '聊天', icon: ChatDotRound, route: '/chat' },
  { name: 'task', label: '任务', icon: List, route: '/tasks' },
  { name: 'meeting', label: '会议', icon: Calendar, route: '/meetings' },
  { name: 'knowledge', label: '知识', icon: DataAnalysis, route: '/knowledge' },
  { name: 'project', label: '项目', icon: Document, route: '/projects' },
  { name: 'hypothesis', label: '假设', icon: Notebook, route: '/hypotheses' },
]

const activeRoute = computed(() => route.path)
const userName = computed(() => userStore.userInfo?.name || '未登录')

const onNavClick = (item) => {
  router.push(item.route).catch(() => {})
}

const onSettingsClick = () => {
  router.push('/settings').catch(() => {})
}

const onAvatarClick = () => {
  router.push('/settings').catch(() => {})
}

const onThemeToggle = () => {
  themeStore.toggle()
}
</script>

<template>
  <nav class="nav-rail" aria-label="主导航">
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

    <!-- 主导航 icon 列 -->
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

    <!-- 底部设置 + 主题切换 -->
    <div class="nav-rail-foot">
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
</style>
