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

          <!-- #043 Phase 6: 搜索 trigger（移动端放最顶 header 上方也合理；放这里更醒目） -->
          <button
            type="button"
            class="search-trigger"
            aria-label="搜索会话"
            @click="$emit('search')"
          >
            <span class="search-icon">🔍</span>
            <span>搜索会话</span>
          </button>

          <div class="session-list">
            <LongPressWrapper
              v-for="session in sessions"
              :key="session.id"
              :delay="600"
              @longpress="onLongPress(session)"
            >
              <button
                type="button"
                class="session-item"
                :class="{ active: session.id === currentId }"
                @click="onSwitch(session)"
              >
                <div class="session-title">
                  <span class="session-title-text">{{ session.title || '新对话' }}</span>
                  <span v-if="session.is_pinned" class="pinned-mark" title="已收藏">📌</span>
                </div>
                <div class="session-preview">{{ session.preview || '暂无消息' }}</div>
                <div v-if="session.tags && session.tags.length" class="session-tags">
                  <span v-for="tag in session.tags.slice(0, 3)" :key="tag" class="tag-chip">{{ tag }}</span>
                  <span v-if="session.tags.length > 3" class="tag-more">+{{ session.tags.length - 3 }}</span>
                </div>
              </button>
            </LongPressWrapper>
            <div v-if="!sessions.length" class="empty">暂无会话</div>
          </div>
        </div>
      </div>
    </Transition>
  </Teleport>

  <!-- #043 Phase 6: long-press 触发的底部 ActionSheet（5 项操作） -->
  <MobileActionSheet
    v-model="showActionSheet"
    title="会话操作"
    :actions="actionSheetItems"
    @select="onActionSelect"
  />
</template>

<script setup>
/**
 * MobileSessionDrawer.vue — 移动端会话列表抽屉 (#043 Phase 6 升级)
 *
 * PR #3: 替代桌面 SessionSidebar（左侧 240px）
 * #043 Phase 6:
 *   - 顶部加搜索 trigger（emit 'search' 给 MobileChatView 弹搜索 sheet）
 *   - session-item 用 LongPressWrapper 包裹 600ms 触发
 *   - 长按弹 MobileActionSheet 5 项：重命名 / 编辑标签 / 分享 / 导出 / 删除
 *   - tags inline chip 渲染
 */
import { ref, computed } from 'vue'
import LongPressWrapper from '@/components/mobile/LongPressWrapper.vue'
import MobileActionSheet from '@/components/mobile/MobileActionSheet.vue'

const props = defineProps({
  modelValue: { type: Boolean, default: false },
  sessions: { type: Array, default: () => [] },
  currentId: { type: String, default: '' },
})

const emit = defineEmits([
  'update:modelValue',
  'create',
  'switch',
  'search',
  'rename',
  'edit-tags',
  'share',
  'export',
  'delete',
])

// ============================================================================
// #043 Phase 6: long-press → ActionSheet 状态
// ============================================================================
const showActionSheet = ref(false)
const actionSession = ref(null)

const actionSheetItems = computed(() => {
  const s = actionSession.value
  const pinned = !!s?.is_pinned
  return [
    { name: '重命名', icon: '✎', key: 'rename' },
    { name: '编辑标签', icon: '🏷', key: 'edit-tags' },
    { name: pinned ? '取消收藏' : '收藏', icon: pinned ? '📌' : '📍', key: 'toggle-pin' },
    { name: '分享', icon: '🔗', key: 'share' },
    { name: '导出', icon: '📤', key: 'export' },
    { name: '删除', icon: '🗑', key: 'delete', danger: true },
  ]
})

function onLongPress(session) {
  actionSession.value = session
  showActionSheet.value = true
  // 触觉反馈（CLAUDE.md 2026-06-27 mobile long-press 铁律）
  if (typeof navigator !== 'undefined' && navigator.vibrate) {
    navigator.vibrate(10)
  }
}

function onActionSelect(action) {
  const s = actionSession.value
  if (!s) return
  // MobileActionSheet 不会自动 emit 字符串 key — 我们的 action 携带 key 字段
  const key = action?.key
  if (!key) return
  switch (key) {
    case 'rename': emit('rename', s); break
    case 'edit-tags': emit('edit-tags', s); break
    case 'toggle-pin': emit('toggle-pin', s); break
    case 'share': emit('share', s); break
    case 'export': emit('export', s); break
    case 'delete': emit('delete', s); break
  }
}

function onSwitch(session) {
  emit('switch', session.id)
  close()
}

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
  margin: 12px 16px 8px;
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

/* #043 Phase 6: 搜索 trigger */
.search-trigger {
  display: flex; align-items: center; gap: 8px;
  margin: 0 16px 8px;
  padding: 10px 12px;
  border-radius: var(--radius-md);
  background: var(--color-bg-warm);
  border: 1px solid var(--color-border-light);
  color: var(--color-text-secondary);
  font-size: 13px;
  cursor: pointer;
  text-align: left;
  -webkit-tap-highlight-color: transparent;
}
.search-icon { font-size: 16px; }
.search-trigger:active { background: var(--color-bg-hover); }

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
  display: flex; align-items: center; gap: 4px;
  font-size: var(--font-size-base, 14px);
  font-weight: var(--font-weight-medium, 500);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  margin-bottom: 2px;
}
.session-title-text { overflow: hidden; text-overflow: ellipsis; }
.pinned-mark { font-size: 11px; }

.session-preview {
  font-size: 12px;
  color: var(--color-text-secondary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

/* #043 Phase 6: tags inline chip */
.session-tags {
  display: flex; gap: 4px; flex-wrap: wrap;
  margin-top: 4px;
}
.tag-chip {
  font-size: 10px;
  padding: 1px 6px;
  border-radius: 3px;
  background: var(--color-primary-bg);
  color: var(--color-primary);
}
.tag-more {
  font-size: 10px;
  color: var(--color-text-secondary);
  align-self: center;
}

.empty {
  padding: 20px 16px;
  text-align: center;
  color: var(--color-text-secondary);
  font-size: 12px;
}
</style>
