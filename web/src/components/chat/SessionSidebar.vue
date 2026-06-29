<script setup>
/**
 * SessionSidebar.vue — 多会话侧栏
 *
 * 240px 折叠侧栏，会话列表 + 切换 / 删除 / 重命名
 * 持久化：useChatSessionsStore（localStorage）
 * 同步状态：useChatHistoryStore（#043 服务端同步徽章）
 */
import { computed } from 'vue'
import { useChatSessionsStore } from '@/stores/chatSessions'
import { useChatHistoryStore } from '@/stores/chatHistory'  // #043
import { ElMessageBox, ElMessage } from 'element-plus'

const emit = defineEmits(['switch', 'create'])
const props = defineProps({ collapsed: { type: Boolean, default: false } })

const store = useChatSessionsStore()
const chatHistoryStore = useChatHistoryStore()  // #043 同步状态徽章

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

const onRename = async (session) => {
  try {
    const { value } = await ElMessageBox.prompt('新会话标题：', '重命名', {
      inputValue: session.title,
      confirmButtonText: '保存',
      cancelButtonText: '取消',
    })
    store.renameSession(session.id, value.trim() || session.title)
  } catch { /* 用户取消 */ }
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
        v-for="s in store.sortedSessions"
        :key="s.id"
        class="session-item"
        :class="{ active: s.id === store.currentId }"
        @click="onSwitch(s.id)"
      >
        <div class="session-title">
          <span>{{ s.title || '新对话' }}</span>
          <!-- #043: 服务端同步状态小标记 -->
          <span v-if="s._isLocalOnly" class="local-only-tag" title="仅本地（未同步到云端）">本地</span>
          <span v-else-if="s._syncStatus === 'synced'" class="synced-tag" title="已同步到云端">✓</span>
        </div>
        <div class="session-meta">
          <span class="time">{{ formatTime(s.updatedAt) }}</span>
          <span v-if="s.messageCount" class="count">{{ s.messageCount }} 条</span>
        </div>
        <div v-if="s.preview" class="session-preview">{{ s.preview }}</div>
        <div class="session-actions">
          <el-button text size="small" @click.stop="onRename(s)" title="重命名">✎</el-button>
          <el-button text size="small" type="danger" @click.stop="onDelete(s, $event)" title="删除">×</el-button>
        </div>
      </div>
      <div v-if="!store.sessions.length" class="empty">暂无会话</div>
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
.sidebar-header { padding: 12px; border-bottom: 1px solid #f0f1f3; }
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
.session-title { font-size: 13px; font-weight: 500; color: var(--color-text-primary); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.session-meta { display: flex; gap: 8px; font-size: 11px; color: var(--color-text-secondary); margin-top: 4px; }
.session-preview { font-size: 11px; color: var(--color-text-secondary); margin-top: 4px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.session-actions { position: absolute; right: 8px; top: 8px; display: none; }
.session-item:hover .session-actions { display: flex; gap: 2px; }
.empty { text-align: center; color: var(--color-text-secondary); padding: 20px 0; font-size: 12px; }

/* #043 同步状态徽章 */
.sync-badge {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 6px 12px;
  margin: 4px 8px;
  border-radius: 4px;
  font-size: 11px;
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
  display: inline-block;
  margin-left: 6px;
  padding: 0 4px;
  border-radius: 2px;
  background: var(--color-text-placeholder, #c0c4cc);
  color: var(--el-color-white);
  font-size: 9px;
  line-height: 14px;
  vertical-align: middle;
}
.synced-tag {
  margin-left: 6px;
  color: var(--el-color-success);
  font-size: 10px;
  vertical-align: middle;
}
.session-title { display: flex; align-items: center; gap: 4px; }
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
