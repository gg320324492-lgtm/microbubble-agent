<template>
  <header class="mobile-chat-header">
    <div class="header-inner">
      <button
        type="button"
        class="icon-btn menu-btn"
        :aria-label="'打开会话列表'"
        title="会话"
        @click="$emit('open-menu')"
      >
        <span class="menu-icon">≡</span>
      </button>

      <div class="header-title">
        <div class="title-text">{{ title }}</div>
        <div class="status-text" :class="{ 'is-active': isActive }">
          <span class="status-dot" />
          {{ isActive ? '生成中...' : '在线' }}
        </div>
      </div>

      <button
        type="button"
        class="icon-btn theme-btn"
        :aria-label="isDark ? '切换浅色' : '切换深色'"
        :title="isDark ? '切换浅色' : '切换深色'"
        @click="$emit('toggle-theme')"
      >
        {{ isDark ? '☀️' : '🌙' }}
      </button>
    </div>
  </header>
</template>

<script setup>
/**
 * MobileHeader.vue — 移动端 Chat 顶部栏
 *
 * PR #3: 极简三件套：☰ 会话菜单 / 标题 + 状态 / 🌙 主题切换
 * - 状态指示：在线 vs 生成中（点动效）
 * - 主题切换：调用 useThemeStore().toggle()
 */

defineProps({
  title: { type: String, default: '小气' },
  isActive: { type: Boolean, default: false },
  isDark: { type: Boolean, default: false },
})

defineEmits(['open-menu', 'toggle-theme'])
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

.menu-icon {
  font-size: 26px;
  font-weight: 300;
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
  0%, 100% { opacity: 0.5; transform: scale(1); }
  50% { opacity: 1; transform: scale(1.4); }
}
</style>