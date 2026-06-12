<script setup>
/**
 * SessionSidebar.vue — 多会话侧栏
 *
 * 240px 折叠侧栏，会话列表 + 切换 / 删除 / 重命名
 * 持久化：useChatSessionsStore（localStorage）
 */
import { computed } from 'vue'
import { useChatSessionsStore } from '@/stores/chatSessions'
import { ElMessageBox, ElMessage } from 'element-plus'

const emit = defineEmits(['switch', 'create'])
const props = defineProps({ collapsed: { type: Boolean, default: false } })

const store = useChatSessionsStore()

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
    <div v-if="!collapsed" class="session-list">
      <div
        v-for="s in store.sortedSessions"
        :key="s.id"
        class="session-item"
        :class="{ active: s.id === store.currentId }"
        @click="onSwitch(s.id)"
      >
        <div class="session-title">{{ s.title || '新对话' }}</div>
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
  background: #fafbfc;
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
.session-item:hover { background: rgba(255, 122, 92, 0.08); }
.session-item.active { background: rgba(255, 122, 92, 0.15); border-left: 3px solid #FF7A5C; }
.session-title { font-size: 13px; font-weight: 500; color: #333; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.session-meta { display: flex; gap: 8px; font-size: 11px; color: #999; margin-top: 4px; }
.session-preview { font-size: 11px; color: #888; margin-top: 4px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.session-actions { position: absolute; right: 8px; top: 8px; display: none; }
.session-item:hover .session-actions { display: flex; gap: 2px; }
.empty { text-align: center; color: #999; padding: 20px 0; font-size: 12px; }
</style>
