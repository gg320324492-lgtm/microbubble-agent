<!--
  CommentItem.vue — v2 PR6-P5 单条评论组件 (recursive)

  功能:
  - 渲染单条评论 (avatar + author + time + content + mentions + 删除)
  - "回复 N 条" 折叠/展开
  - 内联 reply 输入框 (own state, own useMentionAutocomplete 实例)
  - 递归渲染子评论 (depth+1)
  - depth >= MAX_COMMENT_DEPTH 时隐藏 "回复" 按钮 (硬上限)

  Props:
  - comment: { id, parent_comment_id, thread_depth, replies, ... }
  - fileId: number
  - currentUserId: number?
  - isFileOwner: boolean
  - membersList: []
  - usernameMap: { id: username }
-->
<template>
  <div class="comment-item-wrapper" :data-depth="comment.thread_depth || 0">
    <div class="comment-item">
      <el-avatar
        :size="depth === 0 ? 36 : 28"
        :src="userAvatarUrl(comment.user_id)"
        class="comment-avatar"
      >
        {{ (comment.user_name || '?').slice(0, 1) }}
      </el-avatar>
      <div class="comment-body">
        <div class="comment-meta">
          <strong class="comment-author">{{ comment.user_name || `用户 #${comment.user_id}` }}</strong>
          <span class="comment-time">{{ formatTime(comment.created_at) }}</span>
        <!-- v2 PR6-P6: 已编辑标记 (mentions 变化 / 或 service 端加 edited_at 后更精准) -->
        <span v-if="comment._edited" class="comment-edited-tag" title="此评论已编辑">已编辑</span>
          <el-popconfirm
            v-if="canDelete(comment)"
            title="确认删除此评论?"
            confirm-button-text="删除"
            cancel-button-text="取消"
            @confirm="onDelete(comment)"
          >
            <template #reference>
              <el-button
                link
                size="small"
                type="danger"
                class="comment-delete-btn"
                aria-label="删除评论"
              >
                删除
              </el-button>
            </template>
          </el-popconfirm>
        </div>
        <div class="comment-content" v-html="formatContent(comment.content)" />
        <div v-if="comment.mentions && comment.mentions.length > 0" class="comment-mentions">
          <span class="mention-tag" v-for="mid in comment.mentions" :key="mid">
            @{{ usernameById(mid) }}
          </span>
        </div>

        <div class="comment-actions">
          <button
            v-if="canReply(comment)"
            type="button"
            class="comment-reply-btn"
            :aria-label="`回复 ${comment.user_name || '评论'}`"
            :title="`回复 ${comment.user_name || '评论'}`"
            @click="toggleReplyForm"
          >
            <el-icon><ChatDotRound /></el-icon>
            回复
          </button>
          <button
            v-if="canEdit(comment)"
            type="button"
            class="comment-edit-btn"
            :aria-label="`编辑 ${comment.user_name || '评论'}`"
            :title="`编辑 (5 分钟内可改)`"
            @click="toggleEditForm"
          >
            <el-icon><Edit /></el-icon>
            编辑
          </button>
          <button
            v-if="(comment.replies && comment.replies.length > 0) || (comment.reply_count > 0 && repliesCollapsed)"
            type="button"
            class="comment-toggle-replies-btn"
            :aria-label="repliesCollapsed ? '展开回复' : '折叠回复'"
            :title="repliesCollapsed ? '展开回复' : '折叠回复'"
            @click="repliesCollapsed = !repliesCollapsed"
          >
            <el-icon><component :is="repliesCollapsed ? ArrowDown : ArrowUp" /></el-icon>
            {{ repliesCollapsed
              ? `查看 ${comment.reply_count || comment.replies.length} 条回复`
              : '折叠回复' }}
          </button>
        </div>
      </div>
    </div>

    <!-- 内联 reply 输入框 (v2 PR6-P5) -->
    <div v-if="showReplyForm" class="comment-reply-form">
      <el-input
        ref="replyInputRef"
        v-model="replyContent"
        type="textarea"
        :rows="2"
        :placeholder="`回复 ${comment.user_name || '评论'}...`"
        :maxlength="1000"
        show-word-limit
        resize="none"
        class="comment-reply-input"
        @input="onReplyInput"
        @keydown="onReplyKeydown"
        @blur="onReplyBlur"
      />
      <div
        v-if="mention.isOpen.value && mention.rawCandidates.value.length > 0"
        class="mention-dropdown"
        role="listbox"
      >
        <div
          v-for="(m, idx) in mention.rawCandidates.value"
          :key="m.id"
          class="mention-item"
          :class="{ active: idx === mention.selectedIndex.value }"
          role="option"
          :aria-selected="idx === mention.selectedIndex.value"
          @mousedown.prevent="onMentionItemClick(idx)"
          @mouseenter="mention.selectedIndex.value = idx"
        >
          <el-avatar :size="22" :src="m.avatar" class="mention-avatar">
            {{ (m.name || '?').slice(0, 1) }}
          </el-avatar>
          <div class="mention-info">
            <div class="mention-name">{{ m.name }}</div>
            <div class="mention-username">@{{ m.wechat_id || m.username }}</div>
          </div>
        </div>
      </div>
      <div class="comment-reply-actions">
        <el-button size="small" @click="cancelReply">取消</el-button>
        <el-button
          size="small"
          type="primary"
          :disabled="!canPostReply"
          :loading="replying"
          @click="submitReply"
        >
          回复
        </el-button>
      </div>
    </div>

    <!-- v2 PR6-P6: inline 编辑输入框 (owner only, 5 分钟窗口) -->
    <div v-if="showEditForm" class="comment-edit-form">
      <el-input
        ref="editInputRef"
        v-model="editContent"
        type="textarea"
        :rows="3"
        placeholder="编辑评论..."
        :maxlength="2000"
        show-word-limit
        resize="none"
        class="comment-edit-input"
        @input="onEditInput"
        @keydown="onEditKeydown"
        @blur="onEditBlur"
      />
      <div
        v-if="editMention.isOpen.value && editMention.rawCandidates.value.length > 0"
        class="mention-dropdown"
        role="listbox"
      >
        <div
          v-for="(m, idx) in editMention.rawCandidates.value"
          :key="m.id"
          class="mention-item"
          :class="{ active: idx === editMention.selectedIndex.value }"
          role="option"
          :aria-selected="idx === editMention.selectedIndex.value"
          @mousedown.prevent="onEditMentionItemClick(idx)"
          @mouseenter="editMention.selectedIndex.value = idx"
        >
          <el-avatar :size="22" :src="m.avatar" class="mention-avatar">
            {{ (m.name || '?').slice(0, 1) }}
          </el-avatar>
          <div class="mention-info">
            <div class="mention-name">{{ m.name }}</div>
            <div class="mention-username">@{{ m.wechat_id || m.username }}</div>
          </div>
        </div>
      </div>
      <div class="comment-edit-actions">
        <el-button size="small" @click="cancelEdit">取消</el-button>
        <el-button
          size="small"
          type="primary"
          :disabled="!canPostEdit"
          :loading="editing"
          @click="submitEdit"
        >
          保存
        </el-button>
      </div>
    </div>

    <!-- 递归: 子评论 (depth+1) -->
    <div v-if="comment.replies && comment.replies.length > 0 && !repliesCollapsed" class="comment-replies">
      <CommentItem
        v-for="reply in comment.replies"
        :key="reply.id"
        :comment="reply"
        :depth="depth + 1"
        :file-id="fileId"
        :current-user-id="currentUserId"
        :is-file-owner="isFileOwner"
        :members-list="membersList"
        :username-map="usernameMap"
        @deleted="$emit('deleted', $event)"
      />
    </div>
  </div>
</template>

<script setup>
import { ref, computed, nextTick } from 'vue'
import { ElMessage } from 'element-plus'
import { ChatDotRound, ArrowDown, ArrowUp, Edit } from '@element-plus/icons-vue'
import { useNotificationsStore } from '@/composables/useNotifications'
import { useMentionAutocomplete } from '@/composables/useMentionAutocomplete'
import { useCommentTree, MAX_COMMENT_DEPTH } from '@/composables/useCommentTree'

// v2 PR6-P6: 编辑窗口 (秒), 与后端 COMMENT_EDIT_WINDOW_SECONDS=300 镜像
const COMMENT_EDIT_WINDOW_SECONDS = 300

const props = defineProps({
  comment: { type: Object, required: true },
  depth: { type: Number, default: 0 },
  fileId: { type: Number, required: true },
  currentUserId: { type: Number, default: null },
  isFileOwner: { type: Boolean, default: false },
  membersList: { type: Array, default: () => [] },
  usernameMap: { type: Object, default: () => ({}) },
})

defineEmits(['deleted'])

const store = useNotificationsStore()
const { canReply } = useCommentTree()

const showReplyForm = ref(false)
const replyContent = ref('')
const replying = ref(false)
const repliesCollapsed = ref(false)
const replyInputRef = ref(null)

// v2 PR6-P6: 编辑表单 state (与 reply 完全独立)
const showEditForm = ref(false)
const editContent = ref('')
const editing = ref(false)
const editInputRef = ref(null)

const mention = useMentionAutocomplete({
  textareaRef: replyInputRef,
  members: props.membersList,
  onSelect: (member, ctx) => {
    if (!ctx || ctx.triggerPos < 0) return
    const before = replyContent.value.substring(0, ctx.triggerPos)
    const after = replyContent.value.substring(ctx.triggerPos + 1 + ctx.query.length)
    const mentionText = `@${member.wechat_id || member.username} `
    replyContent.value = before + mentionText + after
    setTimeout(() => {
      const ta = replyInputRef.value?.$el?.querySelector?.('textarea')
      if (ta) {
        const newPos = before.length + mentionText.length
        ta.focus()
        ta.setSelectionRange(newPos, newPos)
      }
    }, 0)
  },
})

// v2 PR6-P6: edit 独立 mention autocomplete 实例
const editMention = useMentionAutocomplete({
  textareaRef: editInputRef,
  members: props.membersList,
  onSelect: (member, ctx) => {
    if (!ctx || ctx.triggerPos < 0) return
    const before = editContent.value.substring(0, ctx.triggerPos)
    const after = editContent.value.substring(ctx.triggerPos + 1 + ctx.query.length)
    const mentionText = `@${member.wechat_id || member.username} `
    editContent.value = before + mentionText + after
    setTimeout(() => {
      const ta = editInputRef.value?.$el?.querySelector?.('textarea')
      if (ta) {
        const newPos = before.length + mentionText.length
        ta.focus()
        ta.setSelectionRange(newPos, newPos)
      }
    }, 0)
  },
})

// v2 PR6-P6: edit 模式 computed
const canPostEdit = computed(() => {
  const t = editContent.value.trim()
  return t.length > 0 && t.length <= 2000 && !editing.value
})

// v2 PR6-P6: 是否可编辑 (owner only + 5 分钟窗口)
function canEdit(c) {
  if (!props.currentUserId) return false
  if (c.user_id !== props.currentUserId) return false
  if (!c.created_at) return false
  const t = new Date(c.created_at).getTime()
  if (isNaN(t)) return false
  const elapsed = (Date.now() - t) / 1000
  return elapsed <= COMMENT_EDIT_WINDOW_SECONDS
}

const canPostReply = computed(() => {
  const t = replyContent.value.trim()
  return t.length > 0 && t.length <= 1000 && !replying.value
})

function formatTime(iso) {
  if (!iso) return ''
  const t = new Date(iso).getTime()
  if (isNaN(t)) return ''
  const now = Date.now()
  const sec = Math.floor((now - t) / 1000)
  if (sec < 60) return '刚刚'
  if (sec < 3600) return `${Math.floor(sec / 60)} 分钟前`
  if (sec < 86400) return `${Math.floor(sec / 3600)} 小时前`
  return new Date(iso).toLocaleDateString('zh-CN')
}

function formatContent(raw) {
  if (!raw) return ''
  const escaped = raw
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;')
  return escaped.replace(
    /@([一-龥A-Za-z0-9_.\-]{1,32})/g,
    '<span class="mention">@$1</span>',
  )
}

function canDelete(c) {
  if (!props.currentUserId) return false
  return c.user_id === props.currentUserId || props.isFileOwner
}

function userAvatarUrl(userId) {
  if (!userId) return ''
  return `/api/v1/members/${userId}/avatar`
}

function usernameById(userId) {
  return props.usernameMap[userId] || `用户 #${userId}`
}

function toggleReplyForm() {
  showReplyForm.value = !showReplyForm.value
  if (showReplyForm.value) {
    repliesCollapsed.value = false
    nextTick(() => {
      const ta = replyInputRef.value?.$el?.querySelector?.('textarea')
      ta?.focus()
    })
  }
}

function cancelReply() {
  showReplyForm.value = false
  replyContent.value = ''
  mention.close()
}

async function submitReply() {
  const trimmed = replyContent.value.trim()
  if (!trimmed) return
  replying.value = true
  try {
    const resp = await store.postReply(props.fileId, props.comment.id, trimmed)
    const mc = resp.mentioned_user_ids?.length || 0
    ElMessage.success(
      mc > 0 ? `回复已发布, 提醒 ${mc} 人` : '回复已发布',
    )
    replyContent.value = ''
    showReplyForm.value = false
    mention.close()
  } catch (e) {
    const detail = e.response?.data?.detail || e.message
    if (detail && (detail.includes('深度') || detail.includes('父评论'))) {
      ElMessage.error(`回复失败: ${detail}`)
    } else {
      ElMessage.error('回复失败')
    }
  } finally {
    replying.value = false
  }
}

async function onDelete(c) {
  try {
    await store.deleteComment(props.fileId, c.id)
    ElMessage.success('评论已删除')
  } catch (e) {
    ElMessage.error(e.message || '删除失败')
  }
}

function onReplyInput() { mention.refresh() }
function onReplyKeydown(event) {
  if (mention.handleKeydown(event)) return
  if (event.key === 'Enter' && (event.ctrlKey || event.metaKey)) {
    event.preventDefault()
    submitReply()
  }
}
function onReplyBlur() {
  setTimeout(() => mention.close(), 150)
}
function onMentionItemClick(index) { mention.selectCandidate(index) }

// ===== v2 PR6-P6: 编辑 handlers =====

function toggleEditForm() {
  showEditForm.value = !showEditForm.value
  if (showEditForm.value) {
    // 初始化为当前评论内容
    editContent.value = props.comment.content || ''
    showReplyForm.value = false  // 关闭 reply form 避免冲突
    nextTick(() => {
      const ta = editInputRef.value?.$el?.querySelector?.('textarea')
      ta?.focus()
    })
  }
}

function cancelEdit() {
  showEditForm.value = false
  editContent.value = ''
  editMention.close()
}

async function submitEdit() {
  const trimmed = editContent.value.trim()
  if (!trimmed) return
  editing.value = true
  try {
    const resp = await store.updateComment(props.fileId, props.comment.id, trimmed)
    const mc = resp.mentioned_user_ids?.length || 0
    ElMessage.success(
      mc > 0 ? `评论已编辑, 提醒 ${mc} 人` : '评论已编辑',
    )
    editContent.value = ''
    showEditForm.value = false
    editMention.close()
  } catch (e) {
    const detail = e.response?.data?.detail || e.message
    if (detail && (detail.includes('编辑窗口已过') || detail.includes('无权编辑'))) {
      ElMessage.error(`编辑失败: ${detail}`)
      // 5 分钟窗口已过: 关闭 form 避免再次尝试
      if (detail.includes('编辑窗口已过')) {
        showEditForm.value = false
        editContent.value = ''
      }
    } else if (detail) {
      ElMessage.error(`编辑失败: ${detail}`)
    } else {
      ElMessage.error('编辑失败')
    }
  } finally {
    editing.value = false
  }
}

function onEditInput() { editMention.refresh() }
function onEditKeydown(event) {
  if (editMention.handleKeydown(event)) return
  if (event.key === 'Enter' && (event.ctrlKey || event.metaKey)) {
    event.preventDefault()
    submitEdit()
  }
}
function onEditBlur() {
  setTimeout(() => editMention.close(), 150)
}
function onEditMentionItemClick(index) { editMention.selectCandidate(index) }
</script>

<style scoped>
.comment-item-wrapper {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.comment-item-wrapper[data-depth="1"] {
  margin-left: 24px;
}
.comment-item-wrapper[data-depth="2"] {
  margin-left: 48px;
}

.comment-item {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  padding: 10px;
  background: var(--color-bg-page, #f5f7fa);
  border-radius: 8px;
  transition: background 0.15s;
}
.comment-item-wrapper[data-depth="1"] .comment-item,
.comment-item-wrapper[data-depth="2"] .comment-item {
  padding: 8px;
  background: transparent;
  border: 1px solid var(--color-border-light, #ebeef5);
}

.comment-avatar { flex-shrink: 0; }
.comment-body { flex: 1; min-width: 0; }
.comment-meta {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-bottom: 4px;
  font-size: 13px;
}
.comment-author {
  font-weight: 600;
  color: var(--color-text-primary, #303133);
}
.comment-time {
  font-size: 11px;
  color: var(--color-text-secondary, #909399);
}
.comment-delete-btn {
  margin-left: auto;
  font-size: 12px;
}
.comment-content {
  font-size: 14px;
  line-height: 1.5;
  color: var(--color-text-primary, #303133);
  overflow-wrap: anywhere;
  word-break: normal;
  white-space: pre-wrap;
}
.comment-content :deep(.mention) {
  color: var(--color-primary, #FF7A5C);
  font-weight: 600;
  background: rgba(255, 122, 92, 0.08);
  padding: 1px 4px;
  border-radius: 3px;
}

.comment-mentions {
  margin-top: 6px;
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
}
.mention-tag {
  font-size: 11px;
  padding: 2px 6px;
  background: var(--color-primary-bg, rgba(255, 122, 92, 0.12));
  color: var(--color-primary, #FF7A5C);
  border-radius: 10px;
}

/* v2 PR6-P5: 评论操作栏 */
.comment-actions {
  margin-top: 6px;
  display: flex;
  align-items: center;
  gap: 12px;
}
.comment-reply-btn,
.comment-toggle-replies-btn {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  background: none;
  border: none;
  padding: 4px 8px;
  font-size: 12px;
  color: var(--color-text-secondary, #909399);
  cursor: pointer;
  border-radius: 4px;
  transition: color 0.15s, background 0.15s;
}
.comment-reply-btn:hover,
.comment-toggle-replies-btn:hover {
  color: var(--color-primary, #FF7A5C);
  background: var(--color-primary-bg, rgba(255, 122, 92, 0.08));
}

/* v2 PR6-P5: 内联 reply 输入框 */
.comment-reply-form {
  position: relative;
  margin: 8px 0 0 calc(38px + 8px);
}
.comment-reply-input {
  width: 100%;
}
.comment-reply-actions {
  margin-top: 6px;
  display: flex;
  justify-content: flex-end;
  gap: 6px;
}

.comment-reply-form .mention-dropdown {
  position: absolute;
  left: 0;
  right: 0;
  bottom: 100%;
  margin-bottom: 4px;
  background: var(--color-bg-card, #fff);
  border: 1px solid var(--color-border-light, #ebeef5);
  border-radius: 8px;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.08);
  max-height: 240px;
  overflow-y: auto;
  z-index: 1000;
}
.mention-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 12px;
  cursor: pointer;
  transition: background 0.15s;
}
.mention-item:hover,
.mention-item.active {
  background: var(--color-primary-bg, rgba(255, 122, 92, 0.08));
}
.mention-avatar { flex-shrink: 0; }
.mention-info { flex: 1; min-width: 0; }
.mention-name {
  font-size: 13px;
  font-weight: 500;
  color: var(--color-text-primary, #303133);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.mention-username {
  font-size: 11px;
  color: var(--color-text-secondary, #909399);
  font-family: monospace;
}

.comment-replies {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

/* Dark mode (v60-v67 教训: 非 scoped 块) */
[data-theme="dark"] .comment-item {
  background: var(--color-bg-page, #2a2d35);
}
.comment-item-wrapper[data-depth="1"] .comment-item,
.comment-item-wrapper[data-depth="2"] .comment-item {
  background: transparent;
  border-color: var(--color-border-dark, rgba(255, 255, 255, 0.08));
}
[data-theme="dark"] .comment-content :deep(.mention) {
  background: rgba(255, 122, 92, 0.16);
}
[data-theme="dark"] .comment-reply-btn:hover,
[data-theme="dark"] .comment-toggle-replies-btn:hover {
  background: rgba(255, 122, 92, 0.16);
}
[data-theme="dark"] .comment-reply-form .mention-dropdown {
  background: var(--color-bg-card, #2a2d35);
  border-color: var(--color-border-light, #3a3d45);
}
[data-theme="dark"] .mention-item:hover,
[data-theme="dark"] .mention-item.active {
  background: rgba(255, 122, 92, 0.16);
}

/* ===== v2 PR6-P6: edit form + edited tag ===== */
.comment-edit-form {
  margin: 8px 0 8px 38px;  /* 与 reply form 对齐缩进 */
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 8px;
  background: var(--color-bg-page, #f5f7fa);
  border-radius: 8px;
}
.comment-edit-input {
  width: 100%;
}
.comment-edit-actions {
  display: flex;
  gap: 8px;
  justify-content: flex-end;
}
.comment-edit-btn {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 2px 6px;
  font-size: 12px;
  color: var(--color-text-secondary, #909399);
  background: transparent;
  border: none;
  border-radius: 4px;
  cursor: pointer;
  transition: color 0.15s;
}
.comment-edit-btn:hover {
  color: var(--color-primary, #ff7a5c);
}
.comment-edited-tag {
  display: inline-block;
  margin-left: 6px;
  padding: 0 4px;
  font-size: 10px;
  line-height: 16px;
  color: var(--color-text-placeholder, #c0c4cc);
  background: var(--color-bg-page, #f5f7fa);
  border-radius: 2px;
  vertical-align: middle;
}
</style>

<!-- v60-v67 教训: dark mode 跨组件覆盖必须非 scoped 块 -->
<style>
[data-theme="dark"] .comment-edit-form {
  background: var(--color-bg-card, #1e1f24);
}
[data-theme="dark"] .comment-edited-tag {
  color: var(--color-text-secondary, #a8aab0);
  background: var(--color-bg-page, #2a2d35);
}
[data-theme="dark"] .comment-edit-btn {
  color: var(--color-text-secondary, #a8aab0);
}
[data-theme="dark"] .comment-edit-btn:hover {
  color: var(--color-primary, #ff7a5c);
}
</style>