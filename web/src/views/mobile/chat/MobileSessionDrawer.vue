<template>
  <Teleport to="body">
    <Transition name="session-drawer">
      <div v-if="modelValue" class="session-drawer-root" @click.self="close">
        <div class="session-drawer-mask" @click="close" />
        <div class="session-drawer-body">
          <div class="drawer-header">
            <h3>会话列表</h3>
            <button
              type="button"
              class="close-btn"
              aria-label="关闭"
              title="关闭"
              @click="close"
            >✕</button>
          </div>

          <button
            type="button"
            class="new-session-btn"
            @click="$emit('create')"
          >
            <span class="plus-icon">+</span>
            <span>新建对话</span>
          </button>

          <div class="session-list">
            <button
              v-for="session in sessions"
              :key="session.id"
              type="button"
              class="session-item"
              :class="{ active: session.id === currentId }"
              @click="$emit('switch', session.id)"
            >
              <div class="session-title">{{ session.title || '新对话' }}</div>
              <div class="session-preview">{{ session.preview || '暂无消息' }}</div>
            </button>
          </div>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<script setup>
/**
 * MobileSessionDrawer.vue — 移动端会话列表抽屉
 *
 * PR #3: 替代桌面 SessionSidebar（左侧 240px）
 * - 移动端从左侧滑出
 * - 点击 mask 关闭
 * - 会话列表 + 新建按钮
 */

defineProps({
  modelValue: { type: Boolean, default: false },
  sessions: { type: Array, default: () => [] },
  currentId: { type: String, default: '' },
})

const emit = defineEmits(['update:modelValue', 'create', 'switch'])

function close() {
  emit('update:modelValue', false)
}
</script>

<style scoped>
.session-drawer-root {
  position: fixed;
  inset: 0;
  z-index: 3000;
  display: flex;
  pointer-events: none;
}
.session-drawer-mask {
  position: absolute;
  inset: 0;
  background: rgba(0, 0, 0, 0.4);
  pointer-events: auto;
  opacity: 0;
  transition: opacity 0.25s ease;
}
.session-drawer-body {
  position: relative;
  width: 80vw;
  max-width: 320px;
  height: 100%;
  background: var(--color-bg-card);
  box-shadow: var(--shadow-sidebar);
  display: flex;
  flex-direction: column;
  pointer-events: auto;
  /* iOS 顶部安全区 */
  padding-top: var(--sat);
  transform: translateX(-100%);
  transition: transform 0.3s var(--ease-bounce);
}

[data-theme="dark"] .session-drawer-body {
  background: var(--color-bg-card);
  border-right: 1px solid var(--color-border-base);
}

/* 抽屉打开 */
.session-drawer-enter-active .session-drawer-mask,
.session-drawer-leave-active .session-drawer-mask {
  transition: opacity 0.25s ease;
}
.session-drawer-enter-active .session-drawer-body,
.session-drawer-leave-active .session-drawer-body {
  transition: transform 0.3s var(--ease-bounce);
}
.session-drawer-enter-from .session-drawer-mask,
.session-drawer-leave-to .session-drawer-mask {
  opacity: 0;
}
.session-drawer-enter-from .session-drawer-body,
.session-drawer-leave-to .session-drawer-body {
  transform: translateX(-100%);
}

/* 显式打开态（用于 Transition 嵌套 fallback） */
.session-drawer-root > .session-drawer-mask {
  opacity: 1;
}
.session-drawer-root > .session-drawer-body {
  transform: translateX(0);
}

.drawer-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 16px;
  border-bottom: 1px solid var(--color-border);
}

.drawer-header h3 {
  font-size: var(--font-size-md, 15px);
  font-weight: var(--font-weight-semibold, 600);
  color: var(--color-text-primary);
  margin: 0;
}

.close-btn {
  width: 32px;
  height: 32px;
  border-radius: 50%;
  background: transparent;
  border: none;
  color: var(--color-text-regular);
  font-size: 18px;
  cursor: pointer;
}
.close-btn:active {
  background: var(--color-bg-hover);
}

.new-session-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  margin: 12px 16px;
  padding: 12px;
  border-radius: var(--radius-md);
  background: linear-gradient(135deg, var(--color-primary) 0%, var(--color-primary-light) 100%);
  /* stylelint-disable-next-line color-named */
  color: white;
  border: none;
  font-size: var(--font-size-base, 14px);
  font-weight: var(--font-weight-medium, 500);
  cursor: pointer;
  box-shadow: var(--shadow-primary);
}
.plus-icon {
  font-size: 20px;
  line-height: 1;
}

.session-list {
  flex: 1;
  overflow-y: auto;
  padding: 0 8px;
}

.session-item {
  width: 100%;
  text-align: left;
  background: transparent;
  border: none;
  padding: 12px;
  border-radius: var(--radius-md);
  cursor: pointer;
  color: var(--color-text-regular);
  margin-bottom: 4px;
  -webkit-tap-highlight-color: transparent;
}
.session-item:active,
.session-item.active {
  background: var(--color-primary-bg);
  color: var(--color-text-primary);
}

.session-title {
  font-size: var(--font-size-base, 14px);
  font-weight: var(--font-weight-medium, 500);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  margin-bottom: 2px;
}

.session-preview {
  font-size: 12px;
  color: var(--color-text-secondary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
</style>