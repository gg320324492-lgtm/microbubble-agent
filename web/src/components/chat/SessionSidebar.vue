<script setup>
/**
 * SessionSidebar.vue — 多会话侧栏 (#043 Phase 6 升级)
 *
 * 240px 折叠侧栏，会话列表 + 切换 / 重命名 / 分享 / 导出 / 标签 / 删除
 * 持久化：useChatSessionsStore（localStorage）
 * 同步状态：useChatHistoryStore（#043 服务端同步徽章）
 *
 * Phase 6 升级点：
 * - 顶部搜索输入框（按 title + tags 过滤）
 * - session-item 加 tags inline chip
 * - 5 个 hover actions（重命名 / 分享 / 导出 / 标签 / 删除）+ click.stop 嵌套防护
 */
import { ref, computed } from 'vue'
import { useChatSessionsStore } from '@/stores/chatSessions'
import { useChatHistoryStore } from '@/stores/chatHistory'
import { ElMessageBox, ElMessage } from 'element-plus'
import { Search } from '@element-plus/icons-vue'

const emit = defineEmits(['switch', 'create', 'share', 'export', 'edit-tags'])
const props = defineProps({ collapsed: { type: Boolean, default: false } })

const store = useChatSessionsStore()
const chatHistoryStore = useChatHistoryStore()

// #043 Phase 6: 搜索关键词
const filterKw = ref('')

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

const onDelete = async (session, e) => {
  e.stopPropagation()
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

const onRename = async (session, e) => {
  e.stopPropagation()
  try {
    const { value } = await ElMessageBox.prompt('新会话标题：', '重命名', {
      inputValue: session.title,
      confirmButtonText: '保存',
      cancelButtonText: '取消',
    })
    store.renameSession(session.id, value.trim() || session.title)
  } catch { /* 用户取消 */ }
}

const onShare = (session, e) => {
  e.stopPropagation()
  emit('share', session)
}

const onExport = (session, e) => {
  e.stopPropagation()
  emit('export', session)
}

const onEditTags = (session, e) => {
  e.stopPropagation()
  emit('edit-tags', session)
}
</script>

<template>
  <aside class="session-sidebar" :class="{ collapsed }">
    <div class="sidebar-header">
      <el-button v-if="!collapsed" type="primary" size="small" class="new-btn" @click="onCreate">
        <span class="icon">＋</span> 新对话
      </el-button>
      <el-button v-else text size="small" @click="onCreate" title="新对话">
        <span class="icon">＋</span>
      </el-button>
      <!-- #043 Phase 6: 搜索输入框（按 title + tags 过滤） -->
      <div v-if="!collapsed" class="sidebar-search">
        <el-input
          v-model="filterKw"
          name="chat-sidebar-filter"
          placeholder="过滤会话标题或标签"
          size="small"
          clearable
        >
          <template #prefix><el-icon><Search /></el-icon></template>
        </el-input>
      </div>
    </div>
    <!-- #043: 同步状态徽章（loading / error） -->
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
      >
        <div class="session-title">
          <span class="session-title-text">{{ s.title || '新对话' }}</span>
          <span v-if="s.is_pinned" class="pinned-mark" title="已收藏">📌</span>
          <!-- #043: 服务端同步状态小标记 -->
          <span v-if="s._isLocalOnly" class="local-only-tag" title="仅本地（未同步到云端）">本地</span>
          <span v-else-if="s._syncStatus === 'synced'" class="synced-tag" title="已同步到云端">✓</span>
          <span v-else-if="s._syncStatus === 'error'" class="error-tag" title="同步失败">⚠</span>
          <!-- #043 Phase 6: tags inline chip（最多 2 个 + +N） -->
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
        <div class="session-actions">
          <el-button text size="small" @click.stop="onRename(s, $event)" title="重命名">✎</el-button>
          <el-button text size="small" @click.stop="onShare(s, $event)" title="分享">🔗</el-button>
          <el-button text size="small" @click.stop="onExport(s, $event)" title="导出">📤</el-button>
          <el-button text size="small" @click.stop="onEditTags(s, $event)" title="编辑标签">🏷</el-button>
          <el-button text size="small" type="danger" @click.stop="onDelete(s, $event)" title="删除">×</el-button>
        </div>
      </div>
      <div v-if="!filteredSessions.length && !store.sessions.length" class="empty">暂无会话</div>
      <div v-else-if="!filteredSessions.length" class="empty">没有匹配「{{ filterKw }}」的会话</div>
    </div>
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
}
.session-sidebar.collapsed { width: 0; overflow: hidden; border-right: none; }
.sidebar-header { padding: 12px; border-bottom: 1px solid #f0f1f3; display: flex; flex-direction: column; gap: 8px; }
.new-btn { width: 100%; }
.icon { font-size: 16px; margin-right: 4px; }
.session-list { flex: 1; overflow-y: auto; padding: 8px 0; }
.session-item {
  position: relative;
  padding: 10px 16px;
  margin: 2px 8px;
  border-radius: 6px;
  cursor: pointer;
  transition: background 0.15s;
}
.session-item:hover { background: var(--color-primary-bg); }
.session-item.active { background: var(--color-primary-bg); border-left: 3px solid var(--color-primary); }
.session-title {
  display: flex; align-items: center; gap: 4px; flex-wrap: wrap;
  font-size: 13px; font-weight: 500; color: var(--color-text-primary);
}
.session-title-text { white-space: nowrap; overflow: hidden; text-overflow: ellipsis; max-width: 160px; }
.session-meta { display: flex; gap: 8px; font-size: 11px; color: var(--color-text-secondary); margin-top: 4px; }
.session-preview { font-size: 11px; color: var(--color-text-secondary); margin-top: 4px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.session-actions { position: absolute; right: 8px; top: 8px; display: none; }
.session-item:hover .session-actions { display: flex; gap: 2px; }
.empty { text-align: center; color: var(--color-text-secondary); padding: 20px 0; font-size: 12px; }

/* #043 Phase 6: tags inline chip */
.session-tag-chip { margin-left: 2px; }
.session-tag-more { margin-left: 2px; opacity: 0.7; }
.pinned-mark { font-size: 10px; }

/* #043 同步状态徽章 */
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

/* #043 同步状态小标记（session-title 右侧） */
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
