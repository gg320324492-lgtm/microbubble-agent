<script setup>
/**
 * SessionSidebar.vue — 多会话侧栏 (#043 Phase 6 + v78 UI-redesign)
 *
 * v78 改进点:
 * - session 卡片 actions 改 right-click/long-press 弹 ActionSheet（不再 hover-only 5 buttons 重叠标题）
 * - overlap bug 修复：title-row 改 .session-content 用 flex + min-width: 0，actions 永远不绝对定位
 * - sortedSessions 已自动置顶冒泡（chatSessions.ts:v78）
 * - 4-attr a11y 全部 button 加齐
 */
import { ref, computed } from 'vue'
import { useChatSessionsStore } from '@/stores/chatSessions'
import { useChatHistoryStore } from '@/stores/chatHistory'
import { ElMessageBox, ElMessage } from 'element-plus'
import { Search, Edit, Share, Download, CollectionTag, Delete } from '@element-plus/icons-vue'

const emit = defineEmits(['switch', 'create', 'share', 'export', 'edit-tags'])
const props = defineProps({ collapsed: { type: Boolean, default: false } })

const store = useChatSessionsStore()
const chatHistoryStore = useChatHistoryStore()

// v78: filterKw + context menu state
const filterKw = ref('')
const contextMenuSession = ref(null)
const contextMenuX = ref(0)
const contextMenuY = ref(0)

const filteredSessions = computed(() => {
  const kw = filterKw.value.trim().toLowerCase()
  const all = store.sortedSessions
  if (!kw) return all
  return all.filter((s) => {
    if ((s.title || '').toLowerCase().includes(kw)) return true
    if ((s.tags || []).some((t) => t.toLowerCase().includes(kw))) return true
    return false
  })
})

const formatTime = (iso) => {
  if (!iso) return ''
  try {
    const d = new Date(iso)
    const now = new Date()
    const diffMs = now - d
    const diffMin = Math.floor(diffMs / 60000)
    if (diffMin < 1) return '刚刚'
    if (diffMin < 60) return `${diffMin} 分钟前`
    const diffHour = Math.floor(diffMin / 60)
    if (diffHour < 24) return `${diffHour} 小时前`
    const diffDay = Math.floor(diffHour / 24)
    if (diffDay < 7) return `${diffDay} 天前`
    return d.toLocaleDateString('zh-CN', { month: '2-digit', day: '2-digit' })
  } catch { return '' }
}

const onCreate = () => {
  emit('create')
}

const onSwitch = (id) => {
  if (store.switchSession(id)) {
    emit('switch', id)
  }
}

// v78: right-click 弹上下文菜单 (替代 hover buttons)
const onContextMenu = (s, e) => {
  e.preventDefault()
  contextMenuSession.value = s
  contextMenuX.value = e.clientX
  contextMenuY.value = e.clientY
  contextMenuOpen.value = true
}
const contextMenuOpen = ref(false)
const closeContextMenu = () => {
  contextMenuOpen.value = false
  contextMenuSession.value = null
}

const onDelete = async (session) => {
  closeContextMenu()
  try {
    await ElMessageBox.confirm(
      `删除会话「${session.title}」？此操作不可撤销。`,
      '确认删除',
      { type: 'warning', confirmButtonText: '删除', cancelButtonText: '取消' }
    )
    store.deleteSession(session.id)
    ElMessage.success('已删除')
  } catch { /* 用户取消 */ }
}

const onRename = async (session) => {
  closeContextMenu()
  try {
    const { value } = await ElMessageBox.prompt('新会话标题：', '重命名', {
      inputValue: session.title,
      confirmButtonText: '保存',
      cancelButtonText: '取消',
    })
    store.renameSession(session.id, value.trim() || session.title)
  } catch { /* 用户取消 */ }
}

const onShare = (session) => {
  closeContextMenu()
  emit('share', session)
}

const onExport = (session) => {
  closeContextMenu()
  emit('export', session)
}

const onEditTags = (session) => {
  closeContextMenu()
  emit('edit-tags', session)
}

// v78: 长按触发 context menu（移动端兼容）
let longPressTimer = null
const onTouchStart = (s, e) => {
  longPressTimer = setTimeout(() => {
    const t = e.touches?.[0]
    if (t) {
      contextMenuSession.value = s
      contextMenuX.value = t.clientX
      contextMenuY.value = t.clientY
      contextMenuOpen.value = true
    }
  }, 500)
}
const onTouchEnd = () => {
  if (longPressTimer) {
    clearTimeout(longPressTimer)
    longPressTimer = null
  }
}

// v78: 切换置顶（保留 #043 setPinned helper）
const onTogglePinned = (session) => {
  closeContextMenu()
  store.setPinned(session.id, !session.is_pinned)
}
</script>

<template>
  <aside class="session-sidebar" :class="{ collapsed }" @click="closeContextMenu">
    <div class="sidebar-header">
      <el-button
        v-if="!collapsed"
        id="chat-new-session-btn"
        name="chat-new-session"
        type="primary"
        size="small"
        class="new-btn"
        aria-label="新建对话"
        title="新建对话"
        @click.stop="onCreate"
      >
        <el-icon><Edit /></el-icon>
        <span class="new-btn-text">新对话</span>
      </el-button>
      <el-button
        v-else
        id="chat-new-session-btn-collapsed"
        name="chat-new-session-collapsed"
        text size="small"
        @click.stop="onCreate"
        aria-label="新建对话"
        title="新建对话"
      >
        <el-icon><Edit /></el-icon>
      </el-button>
      <!-- v78: 搜索保留 (按 title + tags 过滤) -->
      <div v-if="!collapsed" class="sidebar-search">
        <el-input
          v-model="filterKw"
          id="chat-sidebar-filter"
          name="chat-sidebar-filter"
          aria-label="过滤会话"
          title="过滤会话标题或标签"
          placeholder="过滤会话标题或标签"
          size="small"
          clearable
        >
          <template #prefix><el-icon><Search /></el-icon></template>
        </el-input>
      </div>
    </div>
    <!-- 同步状态徽章 -->
    <div v-if="!collapsed && chatHistoryStore.syncStatus === 'syncing'" class="sync-badge sync-loading">
      <span class="sync-icon rotating">⟳</span>
      <span class="sync-text">同步中...</span>
    </div>
    <div v-else-if="!collapsed && chatHistoryStore.syncStatus === 'error' && chatHistoryStore.syncError" class="sync-badge sync-error">
      <span class="sync-icon">⚠</span>
      <span class="sync-text" :title="chatHistoryStore.syncError">同步失败</span>
    </div>
    <div v-if="!collapsed" class="session-list">
      <div
        v-for="s in filteredSessions"
        :key="s.id"
        class="session-item"
        :class="{ active: s.id === store.currentId }"
        @click="onSwitch(s.id)"
        @contextmenu="onContextMenu(s, $event)"
        @touchstart="onTouchStart(s, $event)"
        @touchend="onTouchEnd"
        @touchmove="onTouchEnd"
      >
        <div class="session-content">
          <div class="session-title">
            <span class="session-title-text">{{ s.title || '新对话' }}</span>
            <span v-if="s.is_pinned" class="pinned-mark" title="已收藏" aria-label="已收藏">📌</span>
            <!-- 同步状态小标记 -->
            <span v-if="s._isLocalOnly" class="local-only-tag" title="仅本地（未同步到云端）">本地</span>
            <span v-else-if="s._syncStatus === 'synced'" class="synced-tag" title="已同步到云端" aria-label="已同步到云端">✓</span>
            <span v-else-if="s._syncStatus === 'error'" class="error-tag" title="同步失败" aria-label="同步失败">⚠</span>
            <!-- tags inline chip（最多 2 个 + +N） -->
            <el-tag
              v-for="tag in (s.tags || []).slice(0, 2)"
              :key="tag"
              size="small"
              effect="plain"
              class="session-tag-chip"
            >{{ tag }}</el-tag>
            <el-tag
              v-if="(s.tags || []).length > 2"
              size="small"
              effect="plain"
              class="session-tag-more"
            >+{{ s.tags.length - 2 }}</el-tag>
          </div>
          <div class="session-meta">
            <span class="time">{{ formatTime(s.updatedAt) }}</span>
            <span v-if="s.messageCount" class="count">{{ s.messageCount }} 条</span>
          </div>
          <div v-if="s.preview" class="session-preview">{{ s.preview }}</div>
        </div>
        <!-- v78: actions 彻底移除 absolute hover，改为 right-click/long-press 上下文菜单 -->
      </div>
      <div v-if="!filteredSessions.length && !store.sessions.length" class="empty">暂无会话</div>
      <div v-else-if="!filteredSessions.length" class="empty">没有匹配「{{ filterKw }}」的会话</div>
    </div>

    <!-- v78: 右键/长按 上下文菜单 -->
    <ul
      v-if="contextMenuOpen && contextMenuSession"
      class="session-context-menu"
      :style="{ top: contextMenuY + 'px', left: contextMenuX + 'px' }"
      role="menu"
      aria-label="会话操作菜单"
      @click.stop
    >
      <li role="menuitem" class="ctx-item" @click="onRename(contextMenuSession)">
        <el-icon><Edit /></el-icon><span>重命名</span>
      </li>
      <li role="menuitem" class="ctx-item" @click="onTogglePinned(contextMenuSession)">
        <span>{{ contextMenuSession.is_pinned ? '📍' : '📌' }}</span>
        <span>{{ contextMenuSession.is_pinned ? '取消置顶' : '置顶会话' }}</span>
      </li>
      <li role="menuitem" class="ctx-item" @click="onShare(contextMenuSession)">
        <el-icon><Share /></el-icon><span>分享</span>
      </li>
      <li role="menuitem" class="ctx-item" @click="onExport(contextMenuSession)">
        <el-icon><Download /></el-icon><span>导出</span>
      </li>
      <li role="menuitem" class="ctx-item" @click="onEditTags(contextMenuSession)">
        <el-icon><CollectionTag /></el-icon><span>编辑标签</span>
      </li>
      <li role="separator" class="ctx-sep" />
      <li role="menuitem" class="ctx-item danger" @click="onDelete(contextMenuSession)">
        <el-icon><Delete /></el-icon><span>删除</span>
      </li>
    </ul>
  </aside>
</template>

<style scoped>
.session-sidebar {
  display: flex; flex-direction: column;
  width: 240px;
  background: var(--color-bg-warm);
  border-right: 1px solid #e8eaed;
  transition: width 0.2s ease;
  flex-shrink: 0;
  position: relative;
}
.session-sidebar.collapsed { width: 0; overflow: hidden; border-right: none; }
.sidebar-header { padding: 12px; border-bottom: 1px solid #f0f1f3; display: flex; flex-direction: column; gap: 8px; }
.new-btn { width: 100%; }
.new-btn-text { margin-left: 4px; }
.icon { font-size: 16px; margin-right: 4px; }
.session-list { flex: 1; overflow-y: auto; padding: 8px 0; }
.session-item {
  padding: 10px 16px;
  margin: 2px 8px;
  border-radius: 6px;
  cursor: pointer;
  transition: background 0.15s;
}
.session-item:hover { background: var(--color-primary-bg); }
.session-item.active { background: var(--color-primary-bg); border-left: 3px solid var(--color-primary); }

/* v78: session-content 用 flex + min-width: 0 让 title-text 自然收缩，actions 绝对定位重叠 bug 修复 */
.session-content {
  display: flex;
  flex-direction: column;
  min-width: 0;
  width: 100%;
}
.session-title {
  display: flex; align-items: center; gap: 4px; flex-wrap: wrap;
  font-size: 13px; font-weight: 500; color: var(--color-text-primary);
  min-width: 0;
}
.session-title-text {
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  flex: 1;
  min-width: 0;
  /* v78: 移除写死 max-width: 160px，改 flex 自然收缩 */
}
.session-meta { display: flex; gap: 8px; font-size: 11px; color: var(--color-text-secondary); margin-top: 4px; }
.session-preview { font-size: 11px; color: var(--color-text-secondary); margin-top: 4px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }

/* v78: 上下文菜单（原 .session-actions hover 区彻底删除） */
.empty { text-align: center; color: var(--color-text-secondary); padding: 20px 0; font-size: 12px; }
.session-context-menu {
  position: fixed;
  z-index: 9999;
  min-width: 160px;
  list-style: none;
  padding: 4px 0;
  margin: 0;
  background: var(--color-bg-card);
  border: 1px solid var(--color-border-light);
  border-radius: var(--radius-md);
  box-shadow: var(--shadow-lg);
  font-size: 13px;
}
.ctx-item {
  display: flex; align-items: center; gap: 8px;
  padding: 8px 14px;
  cursor: pointer;
  user-select: none;
  color: var(--color-text-primary);
}
.ctx-item:hover { background: var(--color-bg-hover); }
.ctx-item.danger { color: var(--color-danger); }
.ctx-sep { height: 1px; margin: 4px 0; background: var(--color-border-light); list-style: none; }
.ctx-item .el-icon { font-size: 14px; }

/* tags inline chip */
.session-tag-chip { margin-left: 2px; }
.session-tag-more { margin-left: 2px; opacity: 0.7; }
.pinned-mark { font-size: 10px; }

/* 同步状态徽章 */
.sync-badge {
  display: flex; align-items: center; gap: 6px;
  padding: 6px 12px; margin: 4px 8px;
  border-radius: 4px; font-size: 11px;
}
.sync-badge.sync-loading {
  background: rgba(64, 158, 255, 0.1);
  color: var(--el-color-primary);
}
.sync-badge.sync-error {
  background: rgba(245, 108, 108, 0.1);
  color: var(--el-color-danger);
}
.sync-icon { font-size: 12px; }
.sync-icon.rotating {
  display: inline-block;
  animation: mb-sync-rotate 1s linear infinite;
}
@keyframes mb-sync-rotate {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}

/* 同步状态小标记（session-title 右侧） */
.local-only-tag {
  display: inline-block; margin-left: 6px; padding: 0 4px;
  border-radius: 2px;
  background: var(--color-text-placeholder, #c0c4cc);
  color: var(--el-color-white);
  font-size: 9px; line-height: 14px; vertical-align: middle;
}
.synced-tag { margin-left: 6px; color: var(--el-color-success); font-size: 10px; vertical-align: middle; }
.error-tag { margin-left: 6px; color: var(--el-color-danger); font-size: 10px; vertical-align: middle; }
</style>

<!-- v69 P1b fix-2 + v78 SessionSidebar dark 覆盖（v60-v67 教训：必须非 scoped） -->
<style>
[data-theme="dark"] .session-sidebar {
  background: var(--color-bg-card);
  border-right-color: var(--color-border-base);
}
[data-theme="dark"] .sidebar-header {
  border-bottom-color: var(--color-border-light);
}
[data-theme="dark"] .session-item:hover {
  background: var(--color-primary-bg);
}
[data-theme="dark"] .session-item.active {
  background: var(--color-primary-bg);
}
[data-theme="dark"] .session-title { color: var(--color-text-primary); }
[data-theme="dark"] .session-meta { color: var(--color-text-secondary); }
[data-theme="dark"] .session-preview { color: var(--color-text-secondary); }
[data-theme="dark"] .empty { color: var(--color-text-secondary); }

/* v78 dark 模式覆盖（context menu） */
[data-theme="dark"] .session-context-menu {
  background: var(--color-bg-card);
  border-color: var(--color-border-light);
}
[data-theme="dark"] .ctx-item { color: var(--color-text-primary); }
[data-theme="dark"] .ctx-item:hover { background: var(--color-bg-hover); }
[data-theme="dark"] .ctx-item.danger { color: var(--color-danger); }
[data-theme="dark"] .ctx-sep { background: var(--color-border-light); }

/* 同步状态 dark 模式 */
[data-theme="dark"] .sync-badge.sync-loading {
  background: rgba(64, 158, 255, 0.18);
  color: var(--el-color-primary-light-3);
}
[data-theme="dark"] .sync-badge.sync-error {
  background: rgba(245, 108, 108, 0.18);
  color: var(--el-color-danger-light-3);
}
[data-theme="dark"] .local-only-tag {
  background: var(--color-text-secondary, #909399);
}
</style>


<!-- v69 P1b fix-2: SessionSidebar dark 覆盖（v60-v67 教训：必须非 scoped） -->
<style>
[data-theme="dark"] .session-sidebar {
  background: var(--color-bg-card);
  border-right-color: var(--color-border-base);
}
[data-theme="dark"] .sidebar-header {
  border-bottom-color: var(--color-border-light);
}
[data-theme="dark"] .session-item:hover {
  background: var(--color-primary-bg);
}
[data-theme="dark"] .session-item.active {
  background: var(--color-primary-bg);
}
[data-theme="dark"] .session-title { color: var(--color-text-primary); }
[data-theme="dark"] .session-meta { color: var(--color-text-secondary); }
[data-theme="dark"] .session-preview { color: var(--color-text-secondary); }
[data-theme="dark"] .empty { color: var(--color-text-secondary); }

/* #043 dark 模式覆盖 */
[data-theme="dark"] .sync-badge.sync-loading {
  background: rgba(64, 158, 255, 0.18);
  color: var(--el-color-primary-light-3);
}
[data-theme="dark"] .sync-badge.sync-error {
  background: rgba(245, 108, 108, 0.18);
  color: var(--el-color-danger-light-3);
}
[data-theme="dark"] .local-only-tag {
  background: var(--color-text-secondary, #909399);
}
</style>
