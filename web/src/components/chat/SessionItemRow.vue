<script setup lang="ts">
/**
 * SessionItemRow.vue — 单条 session 卡片渲染 (W100 +45 P3-VIRTUAL RETRY)
 *
 * 提取 SessionSidebar 中 3 个 v-for (pinned / recent / filteredSessions) 内部
 * 单一 session 卡片的全部子节点, 使 SessionSidebar 与未来虚拟列表渲染复用同一段逻辑.
 *
 * 数据契约:
 * - session: 单一 session 对象 (从 store.sortedSessions 衍生)
 * - showBatchCheckbox: 是否显示批量 checkbox (batch 模式)
 * - selected: 当前是否被选中 (batch 模式)
 * - active: 当前是否 active
 * - store, selectedIds, formatTime, onSwitch, onContextMenu, onTouchStart, onTouchEnd,
 *   onTogglePinned, onToggleArchive, onDelete, toggleSelect — 由 SessionSidebar 注入
 *   (避免每个 row 都重新监听 store)
 */
import { Search, Edit, Share, Download, CollectionTag, Delete, FolderOpened, Top, Select } from '@element-plus/icons-vue'
import SessionActions from './SessionActions.vue'

defineProps<{
  session: any
  showBatchCheckbox?: boolean
  selected?: boolean
  active?: boolean
  store: any
  selectedIds?: Set<any>
  formatTime: (iso: string) => string
  onSwitch: (id: string) => void
  onContextMenu: (s: any, e: MouseEvent) => void
  onTouchStart: (s: any, e: TouchEvent) => void
  onTouchEnd: () => void
  onTogglePinned: (s: any) => void
  onToggleArchive: (s: any) => Promise<void>
  onDelete: (s: any) => Promise<void>
  toggleSelect: (id: string) => void
  isVirtual?: boolean
  virtualTop?: number
}>()

const emit = defineEmits<{
  (e: 'switch', id: string): void
  (e: 'toggle', id: string): void
}>()
</script>

<template>
  <div
    :class="[
      'session-item',
      active ? 'active' : '',
      selected ? 'selected' : '',
      isVirtual ? 'virtual' : 'inline',
    ]"
    :data-session-id="session.id"
    :style="isVirtual ? { position: 'absolute', top: virtualTop + 'px', left: 0, right: 0 } : undefined"
    @click="showBatchCheckbox ? toggleSelect(session.id) : onSwitch(session.id)"
    @contextmenu="onContextMenu(session, $event)"
    @touchstart="onTouchStart(session, $event)"
    @touchend="onTouchEnd"
    @touchmove="onTouchEnd"
  >
    <label v-if="showBatchCheckbox" class="batch-checkbox" @click.stop>
      <input
        type="checkbox"
        :checked="selected"
        @change="toggleSelect(session.id)"
        :aria-label="`选择 ${session.title || '新对话'}`"
      />
    </label>
    <div class="session-content">
      <div class="session-title">
        <span class="session-title-text">{{ session.title || '新对话' }}</span>
        <span v-if="session.is_pinned" class="pinned-mark" title="已收藏" aria-label="已收藏">📌</span>
        <span v-if="session._isLocalOnly" class="local-only-tag" title="仅本地（未同步到云端）">本地</span>
        <span v-else-if="session._syncStatus === 'synced'" class="synced-tag" title="已同步到云端" aria-label="已同步到云端">✓</span>
        <span v-else-if="session._syncStatus === 'error'" class="error-tag" title="同步失败" aria-label="同步失败">⚠</span>
        <span v-if="session.is_archived" class="archived-mark" title="已归档">🗄️</span>
        <el-tag
          v-for="tag in (session.tags || []).slice(0, 2)"
          :key="tag"
          size="small"
          effect="plain"
          class="session-tag-chip"
        >{{ tag }}</el-tag>
        <el-tag
          v-if="(session.tags || []).length > 2"
          size="small"
          effect="plain"
          class="session-tag-more"
        >+{{ session.tags.length - 2 }}</el-tag>
      </div>
      <div class="session-meta">
        <span class="time">{{ formatTime(session.updatedAt) }}</span>
        <span v-if="session.messageCount" class="count">{{ session.messageCount }} 条</span>
      </div>
      <div v-if="session.preview && !showBatchCheckbox" class="session-preview">{{ session.preview }}</div>
    </div>
    <SessionActions
      v-if="!showBatchCheckbox"
      mode="sidebar"
      :session="session"
      @pin="onTogglePinned"
      @archive="onToggleArchive"
      @delete="onDelete"
    />
  </div>
</template>

<style scoped>
/* ★ 防御塌缩: SessionItemRow 在 virtual 模式下走 SessionSidebar scope
   styles 缺失(本组件独立 file,scope 不互通). 即使没引父级 .session-item
   CSS, 这里独立保证卡片最低 64px 高 + overflow 隔离. */
.session-item {
  min-height: 64px;
  padding: 10px 12px;
  margin: 2px 8px;
  border-radius: 12px;
  cursor: pointer;
  display: flex;
  align-items: center;
  gap: 4px;
  /* 子元素不允许溢出影响父层位置 (prevent title/meta/preview 视觉重叠) */
  overflow: hidden;
  position: relative;
  background: transparent;
  transition: background 0.15s;
  border-left: 3px solid transparent;
}
.session-item.active {
  background: #fff5f2;
  border-left-color: #FF7A5C;
}
.session-item.selected {
  background: rgba(64, 158, 255, 0.08);
  border-left-color: var(--el-color-primary);
}
.session-content {
  display: flex;
  flex-direction: column;
  min-width: 0;
  flex: 1;
  flex-shrink: 0;
}
.session-title {
  display: flex; align-items: center; gap: 4px; flex-wrap: wrap;
  font-size: 13px; font-weight: 500;
  min-width: 0;
}
.session-title-text {
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  flex: 1;
  min-width: 0;
}
.session-meta {
  display: flex; gap: 8px; font-size: 11px;
  margin-top: 4px;
  white-space: nowrap;
}
.session-preview {
  font-size: 11px;
  margin-top: 4px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
</style>
