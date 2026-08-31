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
      <!-- W100 +29 上下文可见性面板 toggle -->
      <button
        id="mobile-header-context"
        name="mobile-header-context"
        type="button"
        class="icon-btn context-btn"
        aria-label="AI 记住了什么"
        title="AI 记住了什么"
        @click="$emit('open-context')"
      >
        <el-icon :size="20"><View /></el-icon>
      </button>
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

import { Menu, Moon, Sunny, View } from '@element-plus/icons-vue'

defineProps({
  title: { type: String, default: '小气' },
  isActive: { type: Boolean, default: false },
  isDark: { type: Boolean, default: false },
})

defineEmits(['open-menu', 'toggle-theme', 'search', 'open-context'])
</script>

<style scoped>
.mobile-chat-header {
  position: sticky;
  top: 0;
  z-index: 50;
  /* 玻璃头部: 半透明 + blur18, 让 mg-page 极光透出 */
  background: var(--mg-glass-bg-strong);
  border-bottom: 1.5px solid var(--mg-glass-border);
  -webkit-backdrop-filter: blur(var(--mg-glass-blur));
  backdrop-filter: blur(var(--mg-glass-blur));
  /* iOS 顶部安全区 */
  padding-top: var(--sat);
}

[data-theme="dark"] .mobile-chat-header {
  border-bottom-color: var(--mg-glass-border);
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
  color: var(--mg-text);
  cursor: pointer;
  -webkit-tap-highlight-color: transparent;
  font-size: 22px;
  line-height: 1;
}

.icon-btn:active {
  background: var(--mg-gradient-soft);
  color: var(--mg-primary);
}

.header-title {
  flex: 1;
  text-align: center;
  min-width: 0;
}

.title-text {
  font-size: var(--font-size-md, 15px);
  font-weight: var(--font-weight-semibold, 600);
  color: var(--mg-text-strong);
}

.status-text {
  font-size: 11px;
  color: var(--mg-text-soft);
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
[data-theme="dark"] .mobile-chat-header .title-text { color: var(--mg-text-strong); }
[data-theme="dark"] .mobile-chat-header .status-text { color: var(--mg-text-soft); }
</style>
