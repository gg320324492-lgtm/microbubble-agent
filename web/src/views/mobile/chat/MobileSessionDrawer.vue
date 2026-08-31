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

          <!-- [CHAT-P1-E E3] 移动端归档过滤 tab -->
          <div class="archive-filter-tabs">
            <button
              type="button"
              class="archive-tab"
              :class="{ active: archiveFilter === 'all' }"
              @click="archiveFilter = 'all'"
            >全部</button>
            <button
              type="button"
              class="archive-tab"
              :class="{ active: archiveFilter === 'active' }"
              @click="archiveFilter = 'active'"
            >未归档</button>
            <button
              type="button"
              class="archive-tab"
              :class="{ active: archiveFilter === 'archived' }"
              @click="archiveFilter = 'archived'"
            >已归档</button>
          </div>

          <!-- W100 +28: 批量管理 toggle -->
          <div class="batch-row">
            <button
              type="button"
              class="batch-toggle-btn"
              :class="{ active: batchMode }"
              @click="toggleBatchMode"
            >{{ batchMode ? '退出批量' : '批量管理' }}</button>
            <template v-if="batchMode">
              <button type="button" class="batch-mini-btn" @click="selectAll">全选</button>
              <button type="button" class="batch-mini-btn" :disabled="!selectedIds.size" @click="clearSelection">清空</button>
            </template>
          </div>

          <div class="session-list">
            <LongPressWrapper
              v-for="session in filteredSessions"
              :key="session.id"
              :delay="600"
              @longpress="onLongPress(session)"
            >
              <div
                class="session-item-wrapper"
                :class="{ active: session.id === currentId, selected: batchMode && selectedIds.has(session.id), 'batch-mode': batchMode }"
                @click="batchMode ? toggleSelect(session.id) : onSwitch(session)"
              >
                <label v-if="batchMode" class="batch-checkbox" @click.stop>
                  <input
                    type="checkbox"
                    :checked="selectedIds.has(session.id)"
                    @change="toggleSelect(session.id)"
                    :aria-label="`选择 ${session.title || '新对话'}`"
                  />
                </label>
                <button
                  type="button"
                  class="session-item"
                  :class="{ active: session.id === currentId }"
                >
                  <div class="session-title">
                    <span class="session-title-text">{{ session.title || '新对话' }}</span>
                    <span v-if="session.is_pinned" class="pinned-mark" title="已收藏">📌</span>
                    <span v-if="session.is_archived" class="archived-mark" title="已归档">🗄️</span>
                  </div>
                  <div class="session-preview">{{ session.preview || '暂无消息' }}</div>
                  <div v-if="session.tags && session.tags.length" class="session-tags">
                    <span v-for="tag in session.tags.slice(0, 3)" :key="tag" class="tag-chip">{{ tag }}</span>
                    <span v-if="session.tags.length > 3" class="tag-more">+{{ session.tags.length - 3 }}</span>
                  </div>
                </button>
              </div>
            </LongPressWrapper>
            <div v-if="!sessions.length" class="empty">暂无会话</div>
          </div>

          <!-- W100 +28: 批量操作 action bar -->
          <div v-if="batchMode" class="batch-action-bar" data-testid="mobile-batch-action-bar">
            <span class="batch-count">已选 {{ selectedIds.size }} 个</span>
            <div class="batch-actions">
              <button
                type="button"
                class="batch-action-btn"
                :disabled="!selectedIds.size"
                @click="onBatchArchive"
              >🗄️ 归档</button>
              <button
                type="button"
                class="batch-action-btn danger"
                :disabled="!selectedIds.size"
                @click="onBatchDelete"
              >🗑 删除</button>
            </div>
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
  'toggle-pin',
  // [CHAT-P1-E E3] 移动端归档/恢复
  'toggle-archive',
  // W100 +28: 批量操作
  'batch-archive',
  'batch-delete',
])

// ============================================================================
// #043 Phase 6: long-press → ActionSheet 状态
// ============================================================================
const showActionSheet = ref(false)
const actionSession = ref(null)

const actionSheetItems = computed(() => {
  const s = actionSession.value
  const pinned = !!s?.is_pinned
  const archived = !!s?.is_archived
  return [
    { name: '重命名', icon: '✎', key: 'rename' },
    { name: '编辑标签', icon: '🏷', key: 'edit-tags' },
    { name: pinned ? '取消收藏' : '收藏', icon: pinned ? '📌' : '📍', key: 'toggle-pin' },
    // [CHAT-P1-E E3] 归档/恢复 (归档区显示"恢复")
    { name: archived ? '✅ 恢复会话' : '🗄️ 归档会话', icon: archived ? '✅' : '🗄️', key: 'toggle-archive' },
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
    // [CHAT-P1-E E3] 移动端归档/恢复 emit
    case 'toggle-archive': emit('toggle-archive', s); break
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

// [CHAT-P1-E E3] 移动端归档过滤
const archiveFilter = ref('active')
const filteredSessions = computed(() => {
  if (archiveFilter.value === 'all') return props.sessions
  if (archiveFilter.value === 'active') {
    return props.sessions.filter((s) => !s.is_archived)
  }
  if (archiveFilter.value === 'archived') {
    return props.sessions.filter((s) => s.is_archived)
  }
  return props.sessions
})

// W100 +28: 批量操作
const batchMode = ref(false)
const selectedIds = ref(new Set())

const toggleBatchMode = () => {
  batchMode.value = !batchMode.value
  if (!batchMode.value) selectedIds.value.clear()
}

const toggleSelect = (id) => {
  if (selectedIds.value.has(id)) {
    selectedIds.value.delete(id)
  } else {
    selectedIds.value.add(id)
  }
  selectedIds.value = new Set(selectedIds.value)
}

const selectAll = () => {
  filteredSessions.value.forEach(s => selectedIds.value.add(s.id))
  selectedIds.value = new Set(selectedIds.value)
}

const clearSelection = () => {
  selectedIds.value.clear()
  selectedIds.value = new Set()
}

const onBatchArchive = () => {
  const ids = [...selectedIds.value]
  emit('batch-archive', ids)
  batchMode.value = false
  selectedIds.value.clear()
  selectedIds.value = new Set()
}

const onBatchDelete = () => {
  const ids = [...selectedIds.value]
  emit('batch-delete', ids)
  batchMode.value = false
  selectedIds.value.clear()
  selectedIds.value = new Set()
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
  /* 视图局部深玻璃 token (mobile-glass.css 无深紫变量, 禁止新增全局 token, 故局部定义;
     深紫底色经 var() fallback 携带, 其余为黑白遮罩豁免) */
  --mgsd-fg: var(--mg-on-primary);
  --mgsd-fg-soft: rgba(255, 255, 255, 0.64);
  --mgsd-fg-faint: rgba(255, 255, 255, 0.42);
  --mgsd-border: rgba(255, 255, 255, 0.14);
  --mgsd-item-active: rgba(255, 255, 255, 0.12);
  position: relative;
  width: 80vw;
  max-width: 320px;
  height: 100%;
  background: var(--mgsd-panel, rgba(36, 30, 55, 0.82));
  -webkit-backdrop-filter: blur(24px);
  backdrop-filter: blur(24px);
  color: var(--mgsd-fg);
  border-right: 1.5px solid var(--mgsd-border);
  box-shadow: var(--mg-shadow-lg);
  display: flex;
  flex-direction: column;
  pointer-events: auto;
  /* iOS 顶部安全区 */
  padding-top: var(--sat);
  transform: translateX(-100%);
  transition: transform 0.3s var(--ease-bounce);
}

/* [CHAT-P1-E E3] 移动端归档过滤 tab */
.archive-filter-tabs {
  display: flex;
  gap: 4px;
  padding: 0 16px 8px;
}
.archive-tab {
  flex: 1;
  min-height: 44px;
  padding: 6px 8px;
  font-size: 13px;
  background: transparent;
  border: 1px solid var(--mgsd-border);
  border-radius: var(--mg-radius-pill);
  cursor: pointer;
  color: var(--mgsd-fg-soft);
  -webkit-tap-highlight-color: transparent;
  transition: transform 150ms ease;
}
.archive-tab:active {
  transform: scale(0.97);
}
.archive-tab.active {
  background: var(--mg-gradient-btn);
  color: var(--mg-on-primary);
  border-color: transparent;
}

[data-theme="dark"] .session-drawer-body {
  /* dark 下纯黑遮罩再压深一档 (黑白遮罩豁免 lint) */
  background: rgba(0, 0, 0, 0.55);
  border-right: 1.5px solid var(--mgsd-border);
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
  border-bottom: 1px solid var(--mgsd-border);
}

.drawer-header h3 {
  font-size: var(--font-size-md, 15px);
  font-weight: var(--font-weight-semibold, 600);
  color: var(--mgsd-fg);
  margin: 0;
}

.close-btn {
  width: 44px;
  height: 44px;
  border-radius: 50%;
  background: transparent;
  border: none;
  color: var(--mgsd-fg-soft);
  font-size: 18px;
  cursor: pointer;
}
.close-btn:active {
  background: var(--mgsd-item-active);
}

.new-session-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  min-height: 44px;
  margin: 12px 16px 8px;
  padding: 12px;
  border-radius: var(--mg-radius-md);
  background: var(--mg-gradient-btn);
  /* stylelint-disable-next-line color-named */
  color: var(--mg-on-primary);
  border: none;
  font-size: var(--font-size-base, 14px);
  font-weight: var(--font-weight-medium, 500);
  cursor: pointer;
  box-shadow: var(--mg-primary-shadow);
  transition: transform 150ms ease;
}
.new-session-btn:active {
  transform: scale(0.97);
}
.plus-icon {
  font-size: 20px;
  line-height: 1;
}

/* #043 Phase 6: 搜索 trigger */
.search-trigger {
  display: flex; align-items: center; gap: 8px;
  min-height: 44px;
  margin: 0 16px 8px;
  padding: 10px 12px;
  border-radius: var(--mg-radius-pill);
  background: var(--mgsd-item-active);
  border: 1px solid var(--mgsd-border);
  color: var(--mgsd-fg-soft);
  font-size: 13px;
  cursor: pointer;
  text-align: left;
  -webkit-tap-highlight-color: transparent;
}
.search-icon { font-size: 16px; }
.search-trigger:active { background: var(--mgsd-item-active); transform: scale(0.97); }

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
  border-radius: var(--mg-radius-md);
  cursor: pointer;
  color: var(--mgsd-fg);
  margin-bottom: 4px;
  -webkit-tap-highlight-color: transparent;
}
.session-item:active,
.session-item.active {
  background: var(--mgsd-item-active);
  color: var(--mgsd-fg);
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
  color: var(--mgsd-fg-soft);
  /* ★ 修复: preview 数据含 \n 时旧 nowrap 渲染出多行导致卡片看起来重叠.
     用 -webkit-line-clamp 强制 2 行截断 */
  display: -webkit-box;
  -webkit-line-clamp: 2;
  line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
  text-overflow: ellipsis;
  word-break: break-word;
}

/* #043 Phase 6: tags inline chip */
.session-tags {
  display: flex; gap: 4px; flex-wrap: wrap;
  margin-top: 4px;
}
.tag-chip {
  font-size: 10px;
  padding: 1px 6px;
  border-radius: var(--mg-radius-pill);
  background: var(--mgsd-item-active);
  color: var(--mgsd-fg-soft);
}
.tag-more {
  font-size: 10px;
  color: var(--mgsd-fg-faint);
  align-self: center;
}

.empty {
  padding: 20px 16px;
  text-align: center;
  color: var(--mgsd-fg-faint);
  font-size: 12px;
}

/* W100 +28: 批量操作 */
.batch-row {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 0 16px 8px;
}
.batch-toggle-btn {
  min-height: 44px;
  padding: 6px 12px;
  font-size: 13px;
  background: transparent;
  border: 1px solid var(--mgsd-border);
  border-radius: var(--mg-radius-pill);
  cursor: pointer;
  color: var(--mgsd-fg-soft);
  -webkit-tap-highlight-color: transparent;
}
.batch-toggle-btn.active {
  background: var(--mg-gradient-btn);
  color: var(--mg-on-primary);
  border-color: transparent;
}
.batch-mini-btn {
  min-height: 44px;
  padding: 6px 12px;
  font-size: 13px;
  background: transparent;
  border: 1px solid var(--mgsd-border);
  border-radius: var(--mg-radius-pill);
  cursor: pointer;
  color: var(--mgsd-fg-soft);
  -webkit-tap-highlight-color: transparent;
}
.batch-mini-btn:disabled { opacity: 0.4; cursor: not-allowed; }

.session-item-wrapper {
  display: flex;
  align-items: center;
  gap: 4px;
  margin-bottom: 4px;
  border-radius: var(--radius-md);
  cursor: pointer;
  /* ★ ★ 修复移动端 sidebar 卡片重叠: 用户实测 19 条卡片互相重叠.
     同桌面 SessionSidebar 根因: .session-item-wrapper 用 flex row + align-items center,
     内部 button .session-item 默认 flex-shrink: 1 被 batch-checkbox 36px 撑高压成
     单行塌陷. min-height + flex-shrink: 0 + box-shadow 三件套 */
  min-height: 64px !important;
  overflow: hidden !important;
  position: relative !important;
  box-sizing: border-box !important;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.04);
  /* 卡片间更多视觉分隔 */
  margin: 2px 4px 8px !important;
  padding: 4px 0;
}
.session-item-wrapper.active {
  background: var(--mgsd-item-active);
}
.session-item-wrapper.selected {
  background: var(--mgsd-item-active);
}
.session-item-wrapper.batch-mode {
  padding: 0 4px;
}
.session-item-wrapper .session-item {
  flex: 1;
  min-width: 0;
  flex-shrink: 0;
}

.batch-checkbox {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 36px;
  height: 36px;
  flex-shrink: 0;
  cursor: pointer;
}
.batch-checkbox input {
  width: 18px;
  height: 18px;
  cursor: pointer;
}

.archived-mark { font-size: 11px; }

.batch-action-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 10px 16px;
  border-top: 1px solid var(--mgsd-border);
  background: transparent;
  gap: 8px;
  /* iOS 底部安全区 */
  padding-bottom: calc(10px + var(--sab, 0px));
}
.batch-count {
  font-size: 13px;
  color: var(--mgsd-fg-soft);
  white-space: nowrap;
}
.batch-actions {
  display: flex;
  gap: 8px;
}
.batch-action-btn {
  padding: 8px 16px;
  font-size: 13px;
  background: var(--mgsd-item-active);
  border: 1px solid var(--mgsd-border);
  border-radius: var(--mg-radius-md);
  cursor: pointer;
  color: var(--mgsd-fg);
  -webkit-tap-highlight-color: transparent;
  min-height: 44px;
}
.batch-action-btn:disabled { opacity: 0.4; cursor: not-allowed; }
.batch-action-btn.danger { color: var(--mg-danger); border-color: var(--mg-danger); }
</style>
