<template>
  <header class="mobile-chat-header">
    <div class="header-inner">
      <button
        id="mobile-header-menu"
        name="mobile-header-menu"
        type="button"
        class="icon-btn menu-btn"
        aria-label="打开会话列表"
        title="会话"
        @click="$emit('open-menu')"
      >
        <el-icon :size="22"><Menu /></el-icon>
      </button>

      <div class="header-title">
        <div class="title-text">{{ title }}</div>
        <div class="status-text" :class="{ 'is-active': isActive }">
          <span class="status-dot" />
          {{ isActive ? '生成中...' : '在线' }}
        </div>
      </div>

      <!-- v78 UI-redesign: 搜索下沉到 SessionDrawer，header 不再显示搜索 button -->
      <!-- #043 兼容保留 search emit 但不渲染触发器 -->
      <button
        id="mobile-header-theme"
        name="mobile-header-theme"
        type="button"
        class="icon-btn theme-btn"
        :aria-label="isDark ? '切换浅色' : '切换深色'"
        :title="isDark ? '切换浅色' : '切换深色'"
        @click="$emit('toggle-theme')"
      >
        <el-icon :size="20"><component :is="isDark ? 'Sunny' : 'Moon'" /></el-icon>
      </button>
    </div>
  </header>
</template>

<script setup>
/**
 * MobileHeader.vue — 移动端 Chat 顶部栏 (v78 UI-redesign)
 *
 * v78 变化:
 * - emoji 图标 → Element Plus icons (Menu / Moon / Sunny)
 * - 搜索 button 从 header 移除（沉到 SessionDrawer，⌘K 快捷键仍可用）
 * - 极简 ☰ menu / 标题 + 状态 / 🌙 三件套
 */

import { Menu, Moon, Sunny } from '@element-plus/icons-vue'

defineProps({
  title: { type: String, default: '小气' },
  isActive: { type: Boolean, default: false },
  isDark: { type: Boolean, default: false },
})

defineEmits(['open-menu', 'toggle-theme', 'search'])
</script>

<style scoped>
.mobile-chat-header {
  position: sticky;
  top: 0;
  z-index: 50;
  background: var(--color-bg-card);
  border-bottom: 1px solid var(--color-border);
  -webkit-backdrop-filter: blur(12px);
  backdrop-filter: blur(12px);
  /* iOS 顶部安全区 */
  padding-top: var(--sat);
}

[data-theme="dark"] .mobile-chat-header {
  background: rgba(42, 45, 53, 0.92);
  border-bottom-color: var(--color-border-base);
}

.header-inner {
  display: flex;
  align-items: center;
  justify-content: space-between;
  height: var(--header-mobile-height, 52px);
  padding: 0 var(--mobile-padding-x, 16px);
  gap: 8px;
}

.icon-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  width: var(--touch-target-min, 44px);
  height: var(--touch-target-min, 44px);
  border-radius: 50%;
  background: transparent;
  border: none;
  color: var(--color-text-regular);
  cursor: pointer;
  -webkit-tap-highlight-color: transparent;
  font-size: 22px;
  line-height: 1;
}

.icon-btn:active {
  background: var(--color-primary-bg);
  color: var(--color-primary);
}

.header-title {
  flex: 1;
  text-align: center;
  min-width: 0;
}

.title-text {
  font-size: var(--font-size-md, 15px);
  font-weight: var(--font-weight-semibold, 600);
  color: var(--color-text-primary);
}

.status-text {
  font-size: 11px;
  color: var(--color-text-secondary);
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 4px;
  margin-top: 1px;
}

.status-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--color-success, #67C23A);
}

.status-text.is-active .status-dot {
  background: var(--color-primary);
  animation: pulse-dot 1.2s infinite;
}

@keyframes pulse-dot {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.4; }
}

</style>

<!-- v78 + v77 教训 (v60-v67): dark mode 必须非 scoped 块 -->
<style>
[data-theme="dark"] .title-text { color: var(--color-text-primary); }
[data-theme="dark"] .status-text { color: var(--color-text-secondary); }
</style>
