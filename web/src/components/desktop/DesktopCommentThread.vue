<!--
  DesktopCommentThread.vue — W68 路线 F-4 桌面端单条评论组件 (recursive)

  2026-07-24 主指挥协调范式第 45 守恒.

  职责:
  - 渲染单条评论 (avatar + author + time + content + 操作菜单)
  - 嵌套回复递归渲染 (depth < MAX_COMMENT_DEPTH=2)
  - 内联编辑表单 (5 分钟内 owner 可编辑, 复用 F-3 同样的 5 分钟窗口)
  - 右键/操作按钮触发菜单: resolved toggle / delete / edit / reply

  与现有 desktop CommentItem (PR6-P5) 区分:
  - PR6-P5 CommentItem 是内联在 FileDetailView 右侧栏的小组件
  - F-4 DesktopCommentThread 是独立路由页 DesktopFileCommentsView 的列表项
  - F-4 加 inline edit + 操作菜单 hover 显示 + 头像 hash 配色 (跟 mobile 同步)

  数据契约:
  - comment: { id, user_id, user_name, content, mentions, parent_comment_id,
               thread_depth, reply_count, resolved, created_at, _edited, replies }
  - depth: 当前嵌套深度 (0/1/2)
  - currentUserId: 当前登录用户 ID
  - isFileOwner: 是否文件 owner
  - usernameMap: { user_id: username }
  - editingCommentId / editDraft / onEdit / onCancelEdit: 父组件状态管理
  - onToggleResolved / onDeleteComment / onReply: 父组件回调

  0 production code 改动铁律:
  - 不动 v2 PR6-P5 老 CommentItem (PR3 阶段使用)
  - 不动 v2 PR9 PR9 后端 API (F-1 完工)
  - 仅 desktop views/components/composables
-->

<template>
  <article
    class="desktop-comment-item"
    :class="{ resolved: comment.resolved, owner: isOwner, editing: isEditing }"
    :data-depth="depth"
    :aria-label="`${comment.user_name || '用户'} 的评论`"
  >
    <div class="dci-row">
      <div class="dci-avatar" :style="avatarStyle" aria-hidden="true">
        {{ avatarInitial }}
      </div>

      <div class="dci-body">
        <!-- meta 行 -->
        <div class="dci-meta">
          <strong class="dci-author">{{ comment.user_name || `用户 #${comment.user_id}` }}</strong>
          <span class="dci-time">{{ formatTime(comment.created_at) }}</span>
          <span v-if="comment._edited" class="dci-edited" title="此评论已编辑">已编辑</span>
          <span v-if="comment.resolved" class="dci-resolved-pill">✓ 已解决</span>
          <span v-if="depth > 0" class="dci-depth-tag">#{{ depth + 1 }} 层</span>
        </div>

        <!-- 编辑模式 -->
        <div v-if="isEditing" class="dci-edit-form">
          <el-input
            v-model="editDraftLocal"
            type="textarea"
            :rows="3"
            :maxlength="1000"
            show-word-limit
            resize="none"
            class="dci-edit-textarea"
          />
          <div class="dci-edit-actions">
            <el-button size="small" @click="onCancelEdit">取消</el-button>
            <el-button size="small" type="primary" :disabled="!canSaveEdit" @click="onSaveEdit">
              保存
            </el-button>
          </div>
        </div>

        <!-- 显示模式 -->
        <template v-else>
          <div class="dci-content" v-html="formattedContent" />
          <div v-if="hasMentions" class="dci-mentions">
            <span v-for="mid in comment.mentions" :key="mid" class="dci-mention-tag">
              @{{ usernameById(mid) }}
            </span>
          </div>
        </template>

        <!-- 操作行 -->
        <div v-if="!isEditing" class="dci-actions">
          <button
            v-if="canReply"
            type="button"
            class="dci-action-btn"
            :aria-label="`回复 ${comment.user_name || '评论'}`"
            @click="$emit('reply', comment)"
          >
            <el-icon><ChatDotRound /></el-icon>
            <span>回复</span>
          </button>
          <button
            v-if="canEdit"
            type="button"
            class="dci-action-btn"
            aria-label="编辑评论"
            @click="onStartEdit"
          >
            <el-icon><Edit /></el-icon>
            <span>编辑</span>
          </button>
          <button
            v-if="canManage"
            type="button"
            class="dci-action-btn"
            :aria-label="comment.resolved ? '标记未解决' : '标记已解决'"
            @click="$emit('toggle-resolved', comment)"
          >
            <el-icon><component :is="comment.resolved ? RefreshLeft : Select" /></el-icon>
            <span>{{ comment.resolved ? '标记未解决' : '标记已解决' }}</span>
          </button>
          <button
            v-if="canManage"
            type="button"
            class="dci-action-btn dci-action-btn--danger"
            aria-label="删除评论"
            @click="$emit('delete', comment)"
          >
            <el-icon><Delete /></el-icon>
            <span>删除</span>
          </button>
          <button
            v-if="hasNestedReplies"
            type="button"
            class="dci-action-btn dci-action-btn--toggle"
            :aria-label="collapsed ? `展开 ${comment.replies.length} 条回复` : '折叠回复'"
            @click="collapsed = !collapsed"
          >
            <el-icon><component :is="collapsed ? ArrowDown : ArrowUp" /></el-icon>
            <span>{{ collapsed ? `查看 ${comment.replies.length} 条回复` : '折叠回复' }}</span>
          </button>
        </div>
      </div>
    </div>

    <!-- 嵌套回复 (递归) -->
    <ul v-if="!collapsed && hasNestedReplies" class="dci-replies">
      <li v-for="reply in comment.replies" :key="reply.id" class="dci-reply-item">
        <DesktopCommentThread
          :comment="reply"
          :depth="depth + 1"
          :current-user-id="currentUserId"
          :is-file-owner="isFileOwner"
          :username-map="usernameMap"
          :editing-comment-id="editingCommentId"
          :edit-draft="editDraft"
          @reply="$emit('reply', $event)"
          @edit="$emit('edit', $event)"
          @toggle-resolved="$emit('toggle-resolved', $event)"
          @delete="$emit('delete', $event)"
          @save-edit="(id, content) => $emit('save-edit', id, content)"
          @cancel-edit="$emit('cancel-edit')"
        />
      </li>
    </ul>
  </article>
</template>

<script setup>
import { ref, computed, watch } from 'vue'
import {
  ChatDotRound, Edit, Delete, RefreshLeft, Select, ArrowDown, ArrowUp,
} from '@element-plus/icons-vue'

const props = defineProps({
  comment: { type: Object, required: true },
  depth: { type: Number, default: 0 },
  currentUserId: { type: [Number, String], default: null },
  isFileOwner: { type: Boolean, default: false },
  usernameMap: { type: Object, default: () => ({}) },
  editingCommentId: { type: [Number, String], default: null },
  editDraft: { type: String, default: '' },
})

const emit = defineEmits([
  'reply', 'edit', 'toggle-resolved', 'delete', 'save-edit', 'cancel-edit',
])

const collapsed = ref(false)

// === 计算属性 ===
const isOwner = computed(() => {
  if (!props.currentUserId) return false
  return props.comment.user_id === props.currentUserId
})

const isEditing = computed(() => props.editingCommentId === props.comment.id)

// 编辑时本地草稿 (避免每次输入都向上 emit 触发父组件响应式重渲)
const editDraftLocal = ref(props.editDraft || '')
// 同步父组件 editDraft
watch(() => props.editDraft, (val) => {
  if (val !== editDraftLocal.value) editDraftLocal.value = val || ''
})
// 进入编辑时初始化
watch(isEditing, (val) => {
  if (val) editDraftLocal.value = props.editDraft || ''
})

const canReply = computed(() => props.depth < 2)  // MAX_COMMENT_DEPTH=2

const canEdit = computed(() => {
  if (!isOwner.value) return false
  if (!props.comment.created_at) return false
  const t = new Date(props.comment.created_at).getTime()
  if (isNaN(t)) return false
  // 5 分钟编辑窗口 (v2 PR6-P6)
  return Date.now() - t < 5 * 60 * 1000
})

const canManage = computed(() => {
  // owner of comment OR file owner can resolved/delete
  return isOwner.value || props.isFileOwner
})

const hasMentions = computed(() => Array.isArray(props.comment.mentions) && props.comment.mentions.length > 0)

const hasNestedReplies = computed(() => Array.isArray(props.comment.replies) && props.comment.replies.length > 0)

const avatarInitial = computed(() => (props.comment.user_name || '?').slice(0, 1))

const avatarStyle = computed(() => {
  const id = props.comment.user_id || 0
  const hue = (id * 47) % 360
  return {
    background: `hsl(${hue}, 65%, 60%)`,
    color: '#fff',
  }
})

const canSaveEdit = computed(() => {
  const t = editDraftLocal.value.trim()
  return t.length > 0 && t.length <= 1000
})

const formattedContent = computed(() => {
  const c = props.comment.content || ''
  return escapeHtml(c).replace(
    /@([一-龥A-Za-z0-9_.\-]{1,32})/g,
    '<span class="mention">@$1</span>',
  )
})

// === 工具函数 ===
function escapeHtml(s) {
  return String(s)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;')
}

function formatTime(iso) {
  if (!iso) return ''
  const t = new Date(iso).getTime()
  if (isNaN(t)) return ''
  const sec = Math.floor((Date.now() - t) / 1000)
  if (sec < 60) return '刚刚'
  if (sec < 3600) return `${Math.floor(sec / 60)} 分钟前`
  if (sec < 86400) return `${Math.floor(sec / 3600)} 小时前`
  return new Date(iso).toLocaleDateString('zh-CN')
}

function usernameById(userId) {
  return props.usernameMap[userId] || `用户 #${userId}`
}

// === 编辑相关 ===
function onStartEdit() {
  emit('edit', props.comment)
}

function onSaveEdit() {
  if (!canSaveEdit.value) return
  emit('save-edit', props.comment.id, editDraftLocal.value)
}

function onCancelEdit() {
  emit('cancel-edit')
}
</script>

<style scoped>
.desktop-comment-item {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 12px 14px;
  border-radius: 10px;
  background: var(--color-bg-card, #fff);
  border: 1px solid var(--color-border-light, #ebeef5);
  transition: border-color 0.15s, background 0.15s;
}

.desktop-comment-item.resolved {
  opacity: 0.7;
  background: var(--color-success-bg, rgba(103, 194, 58, 0.04));
}

.desktop-comment-item.owner {
  border-left: 3px solid var(--color-primary, #ff7a5c);
}

.desktop-comment-item.editing {
  border-color: var(--color-primary, #ff7a5c);
  box-shadow: 0 0 0 1px var(--color-primary, #ff7a5c);
}

.desktop-comment-item[data-depth="1"],
.desktop-comment-item[data-depth="2"] {
  margin-left: 24px;
  background: var(--color-bg-page, #f5f7fa);
  border-color: transparent;
}

.dci-row {
  display: flex;
  align-items: flex-start;
  gap: 12px;
}

.dci-avatar {
  width: 36px;
  height: 36px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 14px;
  font-weight: 600;
  flex-shrink: 0;
}

.desktop-comment-item[data-depth="1"] .dci-avatar,
.desktop-comment-item[data-depth="2"] .dci-avatar {
  width: 28px;
  height: 28px;
  font-size: 12px;
}

.dci-body {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.dci-meta {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.dci-author {
  font-size: 13px;
  font-weight: 600;
  color: var(--color-text-primary, #303133);
}

.dci-time {
  font-size: 12px;
  color: var(--color-text-secondary, #909399);
}

.dci-edited {
  font-size: 10px;
  padding: 1px 6px;
  background: var(--color-warning-bg, rgba(230, 162, 60, 0.12));
  color: var(--color-warning, #e6a23c);
  border-radius: 6px;
}

.dci-resolved-pill {
  font-size: 10px;
  padding: 2px 8px;
  background: var(--color-success-bg, rgba(103, 194, 58, 0.14));
  color: var(--color-success, #67c23a);
  border-radius: 10px;
  font-weight: 600;
}

.dci-depth-tag {
  font-size: 10px;
  color: var(--color-text-placeholder, #c0c4cc);
}

.dci-content {
  font-size: 14px;
  line-height: 1.6;
  color: var(--color-text-primary, #303133);
  word-wrap: break-word;
}

.dci-content :deep(.mention) {
  color: var(--color-primary, #ff7a5c);
  background: var(--color-primary-bg, rgba(255, 122, 92, 0.08));
  padding: 0 2px;
  border-radius: 3px;
  font-weight: 500;
}

.dci-mentions {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
}

.dci-mention-tag {
  font-size: 11px;
  padding: 2px 6px;
  background: var(--color-primary-bg, rgba(255, 122, 92, 0.08));
  color: var(--color-primary, #ff7a5c);
  border-radius: 8px;
}

.dci-actions {
  display: flex;
  align-items: center;
  gap: 4px;
  margin-top: 2px;
  flex-wrap: wrap;
}

.dci-action-btn {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  background: transparent;
  border: none;
  padding: 4px 8px;
  border-radius: 4px;
  font-size: 12px;
  color: var(--color-text-secondary, #606266);
  cursor: pointer;
  transition: background 0.15s, color 0.15s;
}

.dci-action-btn:hover {
  background: var(--color-primary-bg, rgba(255, 122, 92, 0.08));
  color: var(--color-primary, #ff7a5c);
}

.dci-action-btn--danger:hover {
  background: var(--color-danger-bg, rgba(245, 108, 108, 0.08));
  color: var(--color-danger, #f56c6c);
}

.dci-action-btn--toggle {
  margin-left: auto;
}

.dci-edit-form {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.dci-edit-textarea {
  width: 100%;
}

.dci-edit-actions {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
}

.dci-replies {
  list-style: none;
  margin: 6px 0 0 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.dci-reply-item {
  list-style: none;
}
</style>

<!-- v60-v67 教训: dark mode 跨组件覆盖必须放非 scoped <style> 块 -->
<style>
[data-theme="dark"] .desktop-comment-item {
  background: var(--color-bg-card, #2a2d35);
  border-color: var(--color-border-light, #3a3d45);
}

[data-theme="dark"] .desktop-comment-item[data-depth="1"],
[data-theme="dark"] .desktop-comment-item[data-depth="2"] {
  background: rgba(255, 255, 255, 0.03);
}

[data-theme="dark"] .dci-content :deep(.mention),
[data-theme="dark"] .dci-mention-tag {
  background: rgba(255, 122, 92, 0.16);
}
</style>