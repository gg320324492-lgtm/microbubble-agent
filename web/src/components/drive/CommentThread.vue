<!--
  CommentThread.vue — v2 PR6 文件评论组件 (desktop)

  v2 PR6-P5 threading:
  - 顶层评论用 CommentItem 递归渲染 (含内联 reply + 嵌套子评论)
  - 自身只保留"顶层评论"列表 + "发布顶层评论"输入框
  - @username autocomplete 复用 useMentionAutocomplete composable (PR6-P4)
-->
<template>
  <div class="comment-thread">
    <div class="comment-thread-header">
      <h3>
        评论
        <el-badge
          v-if="treeTop.length > 0"
          :value="treeTop.length"
          :max="99"
          class="comment-thread-count"
        />
      </h3>
    </div>

    <!-- 加载态 -->
    <div v-if="loading" class="comment-thread-loading">
      <el-icon class="is-loading"><Loading /></el-icon>
      <span>加载评论中...</span>
    </div>

    <!-- 空态 -->
    <div v-else-if="treeTop.length === 0" class="comment-thread-empty">
      <el-icon :size="32"><ChatDotRound /></el-icon>
      <p>暂无评论</p>
      <p class="hint">在下方输入框写下第一条评论 (支持 @username)</p>
    </div>

    <!-- v2 PR6-P5: 评论树 (顶层 + 嵌套 replies, 递归渲染) -->
    <ul v-else class="comment-thread-list">
      <li v-for="top in treeTop" :key="top.id" class="comment-thread-top">
        <CommentItem
          :comment="top"
          :depth="0"
          :file-id="props.fileId"
          :current-user-id="props.currentUserId"
          :is-file-owner="props.isFileOwner"
          :members-list="membersList"
          :username-map="usernameMap"
        />
      </li>
    </ul>

    <!-- 发布输入框 (顶层评论) -->
    <div class="comment-thread-compose">
      <el-input
        ref="inputRef"
        v-model="newContent"
        type="textarea"
        :rows="3"
        :placeholder="placeholder"
        :maxlength="1000"
        show-word-limit
        resize="none"
        @input="onContentInput"
        @keydown="onContentKeydown"
        @blur="onContentBlur"
      />
      <!-- @username autocomplete dropdown (v2 PR6-P4) -->
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
          <el-avatar :size="24" :src="m.avatar" class="mention-avatar">
            {{ (m.name || '?').slice(0, 1) }}
          </el-avatar>
          <div class="mention-info">
            <div class="mention-name">{{ m.name }}</div>
            <div class="mention-username">@{{ m.wechat_id || m.username }}</div>
          </div>
          <span v-if="m.role === 'admin'" class="mention-badge">admin</span>
        </div>
      </div>
      <div class="comment-thread-actions">
        <span class="comment-thread-hint">
          💡 用 <code>@username</code> 提醒成员
        </span>
        <el-button
          type="primary"
          :disabled="!canPost"
          :loading="posting"
          @click="onPost"
        >
          发布
        </el-button>
      </div>
    </div>

    <!-- 错误提示 (非阻塞) -->
    <el-alert
      v-if="errorMsg"
      :title="errorMsg"
      type="error"
      :closable="true"
      class="comment-thread-error"
      @close="errorMsg = null"
    />
  </div>
</template>

<script setup>
import { ref, computed, onMounted, watch } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import { Loading, ChatDotRound } from '@element-plus/icons-vue'
import axios from 'axios'
import { useNotificationsStore } from '@/composables/useNotifications'
import { useMentionAutocomplete } from '@/composables/useMentionAutocomplete'
import { useCommentTree } from '@/composables/useCommentTree'
import CommentItem from '@/components/drive/CommentItem.vue'

const props = defineProps({
  fileId: { type: Number, required: true },
  currentUserId: { type: Number, default: null },
  isFileOwner: { type: Boolean, default: false },
})

const route = useRoute()
const store = useNotificationsStore()
const { buildCommentTree } = useCommentTree()

const newContent = ref('')
const posting = ref(false)
const loading = ref(false)
const errorMsg = ref(null)
const usernameMap = ref({})
const membersList = ref([])
const inputRef = ref(null)

// v2 PR6-P4: @username autocomplete (顶层输入框)
const mention = useMentionAutocomplete({
  textareaRef: inputRef,
  members: membersList,
  onSelect: (member, ctx) => {
    if (!ctx || ctx.triggerPos < 0) return
    const before = newContent.value.substring(0, ctx.triggerPos)
    const after = newContent.value.substring(ctx.triggerPos + 1 + ctx.query.length)
    const mentionText = `@${member.wechat_id || member.username} `
    newContent.value = before + mentionText + after
    setTimeout(() => {
      const ta = inputRef.value?.$el?.querySelector?.('textarea')
      if (ta) {
        const newPos = before.length + mentionText.length
        ta.focus()
        ta.setSelectionRange(newPos, newPos)
      }
    }, 0)
  },
})

const comments = computed(() => store.commentsByFileId[props.fileId] || [])
const treeTop = computed(() => buildCommentTree(comments.value).top)

const placeholder = computed(() => {
  if (!props.currentUserId) return '请先登录后再评论'
  return '写一条评论... @username 提醒团队成员'
})

const canPost = computed(() => {
  const trimmed = newContent.value.trim()
  return trimmed.length > 0 && trimmed.length <= 1000 && !posting.value
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

function canDelete(comment) {
  if (!props.currentUserId) return false
  return comment.user_id === props.currentUserId || props.isFileOwner
}

function userAvatarUrl(userId) {
  if (!userId) return ''
  return `/api/v1/members/${userId}/avatar`
}

function usernameById(userId) {
  return usernameMap.value[userId] || `用户 #${userId}`
}

async function fetchComments() {
  if (!props.fileId) return
  loading.value = true
  errorMsg.value = null
  try {
    await store.fetchComments(props.fileId)
    await batchResolveUsernames()
  } catch (e) {
    errorMsg.value = e.message || '加载评论失败'
  } finally {
    loading.value = false
  }
}

async function batchResolveUsernames() {
  const userIds = new Set()
  for (const c of comments.value) {
    if (c.user_id) userIds.add(c.user_id)
    if (c.mentions) {
      for (const mid of c.mentions) userIds.add(mid)
    }
  }
  const missing = [...userIds].filter((id) => !usernameMap.value[id])
  if (missing.length === 0) return
  try {
    const resp = await axios.get('/api/v1/members', {
      headers: { Authorization: `Bearer ${localStorage.getItem('access_token') || ''}` },
    })
    const map = { ...usernameMap.value }
    for (const m of resp.data.items || []) {
      map[m.id] = m.username || m.name
    }
    usernameMap.value = map
    if (membersList.value.length === 0) {
      membersList.value = (resp.data.items || []).map((m) => ({
        id: m.id,
        username: m.username,
        wechat_id: m.wechat_id,
        name: m.name,
        avatar: m.avatar,
        role: m.role,
      }))
    }
  } catch (e) {
    // ignore
  }
}

function onContentInput() { mention.refresh() }
function onContentKeydown(event) {
  if (mention.handleKeydown(event)) return
  if (event.key === 'Enter' && (event.ctrlKey || event.metaKey)) {
    event.preventDefault()
    onPost()
  }
}
function onContentBlur() {
  setTimeout(() => mention.close(), 150)
}
function onMentionItemClick(index) { mention.selectCandidate(index) }

async function onPost() {
  const trimmed = newContent.value.trim()
  if (!trimmed) return
  posting.value = true
  errorMsg.value = null
  try {
    const resp = await store.postComment(props.fileId, trimmed)
    newContent.value = ''
    if (resp.mentioned_user_ids && resp.mentioned_user_ids.length > 0) {
      ElMessage.success(`评论已发布, 提醒了 ${resp.mentioned_user_ids.length} 人`)
    } else {
      ElMessage.success('评论已发布')
    }
    await batchResolveUsernames()
  } catch (e) {
    errorMsg.value = e.response?.data?.detail || e.message || '发布失败'
  } finally {
    posting.value = false
  }
}

onMounted(() => {
  fetchComments()
})

watch(() => props.fileId, (newId) => {
  if (newId) fetchComments()
})
</script>

<style scoped>
.comment-thread {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.comment-thread-header {
  display: flex;
  align-items: center;
  gap: 8px;
}

.comment-thread-header h3 {
  margin: 0;
  font-size: 15px;
  font-weight: 600;
  color: var(--color-text-primary, #303133);
  display: flex;
  align-items: center;
  gap: 8px;
}

.comment-thread-count {
  margin-left: 4px;
}

.comment-thread-loading,
.comment-thread-empty {
  padding: 40px 16px;
  text-align: center;
  color: var(--color-text-secondary, #909399);
  font-size: 13px;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
}

.comment-thread-empty .hint {
  font-size: 12px;
  color: var(--color-text-secondary);
  opacity: 0.75;
}

.comment-thread-list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.comment-thread-compose {
  margin-top: 8px;
  padding-top: 12px;
  border-top: 1px solid var(--color-border-light, #ebeef5);
  position: relative;
}

.comment-thread-actions {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-top: 8px;
}

.comment-thread-hint {
  font-size: 12px;
  color: var(--color-text-secondary, #909399);
}

.comment-thread-hint code {
  background: var(--color-bg-page, #f5f7fa);
  padding: 1px 4px;
  border-radius: 3px;
  font-family: monospace;
  font-size: 11px;
}

.comment-thread-error {
  margin-top: 8px;
}

/* v2 PR6-P4: 顶层 compose 的 mention dropdown */
.mention-dropdown {
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
.mention-avatar {
  flex-shrink: 0;
}
.mention-info {
  flex: 1;
  min-width: 0;
}
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
.mention-badge {
  font-size: 10px;
  padding: 1px 5px;
  background: var(--color-warning-light-9, #fdf6ec);
  color: var(--color-warning, #e6a23c);
  border-radius: 8px;
}

/* Dark mode 非 scoped 块 (v60-v67 教训) */
[data-theme="dark"] .comment-thread-compose {
  border-top-color: var(--color-border-dark, rgba(255, 255, 255, 0.08));
}

[data-theme="dark"] .mention-dropdown {
  background: var(--color-bg-card, #2a2d35);
  border-color: var(--color-border-light, #3a3d45);
}

[data-theme="dark"] .mention-item:hover,
[data-theme="dark"] .mention-item.active {
  background: rgba(255, 122, 92, 0.16);
}

[data-theme="dark"] .comment-thread-hint code {
  background: var(--color-bg-page, #2a2d35);
}
</style>