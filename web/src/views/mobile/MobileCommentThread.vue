<!--
  MobileCommentThread.vue — v2 PR6 移动端评论组件 (PR6-P3 + PR6-P5 mobile 镜像)

  v2 PR6-P5 threading: 完全复用 desktop CommentItem 组件
  v2 PR6-P4 autocomplete: 共享 useMentionAutocomplete composable
-->
<template>
  <div class="mobile-comment-thread">
    <div class="mct-header">
      <h3>
        <el-icon><ChatDotRound /></el-icon>
        评论
        <el-badge
          v-if="treeTop.length > 0"
          :value="treeTop.length"
          :max="99"
          class="mct-count"
        />
      </h3>
    </div>

    <div v-if="loading && treeTop.length === 0" class="mct-loading">
      <el-icon class="is-loading"><Loading /></el-icon>
      <span>加载评论中...</span>
    </div>

    <div v-else-if="treeTop.length === 0" class="mct-empty">
      <el-icon :size="36"><ChatDotRound /></el-icon>
      <p>暂无评论</p>
      <p class="hint">在下方输入框写下第一条评论</p>
    </div>

    <!-- v2 PR6-P5: 评论树 (复用 desktop CommentItem 组件) -->
    <ul v-else class="mct-list">
      <li v-for="top in treeTop" :key="top.id" class="mct-top">
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

    <div class="mct-compose">
      <el-input
        ref="inputRef"
        v-model="newContent"
        type="textarea"
        :rows="1"
        autosize
        :placeholder="placeholder"
        :maxlength="1000"
        show-word-limit
        class="mct-input"
        @input="onContentInput"
        @keydown="onContentKeydown"
        @blur="onContentBlur"
      />
      <!-- @username autocomplete dropdown (v2 PR6-P4 mobile 镜像) -->
      <div
        v-if="mention.isOpen.value && mention.rawCandidates.value.length > 0"
        class="mct-mention-dropdown"
        role="listbox"
      >
        <div
          v-for="(m, idx) in mention.rawCandidates.value"
          :key="m.id"
          class="mct-mention-item"
          :class="{ active: idx === mention.selectedIndex.value }"
          role="option"
          :aria-selected="idx === mention.selectedIndex.value"
          @mousedown.prevent="onMentionItemClick(idx)"
          @mouseenter="mention.selectedIndex.value = idx"
        >
          <el-avatar :size="24" :src="m.avatar" class="mct-mention-avatar">
            {{ (m.name || '?').slice(0, 1) }}
          </el-avatar>
          <div class="mct-mention-info">
            <div class="mct-mention-name">{{ m.name }}</div>
            <div class="mct-mention-username">@{{ m.wechat_id || m.username }}</div>
          </div>
        </div>
      </div>
      <button
        type="button"
        class="mct-post-btn"
        :disabled="!canPost"
        aria-label="发布评论"
        title="发布评论"
        @click="onPost"
      >
        <el-icon v-if="posting" class="is-loading"><Loading /></el-icon>
        <span v-else>发布</span>
      </button>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
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

const store = useNotificationsStore()
const { buildCommentTree } = useCommentTree()

const newContent = ref('')
const posting = ref(false)
const loading = ref(false)
const usernameMap = ref({})
const membersList = ref([])
const inputRef = ref(null)

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
  return '写评论... @username 提醒'
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
}
function onContentBlur() {
  setTimeout(() => mention.close(), 150)
}
function onMentionItemClick(index) { mention.selectCandidate(index) }

async function fetchComments() {
  if (!props.fileId) return
  loading.value = true
  try {
    await store.fetchComments(props.fileId)
    await batchResolveUsernames()
  } catch (e) {
    ElMessage.error(e.message || '加载评论失败')
  } finally {
    loading.value = false
  }
}

async function onPost() {
  const trimmed = newContent.value.trim()
  if (!trimmed) return
  posting.value = true
  try {
    const resp = await store.postComment(props.fileId, trimmed)
    newContent.value = ''
    const mentionCount = resp.mentioned_user_ids?.length || 0
    ElMessage.success(
      mentionCount > 0 ? `评论已发布, 提醒 ${mentionCount} 人` : '评论已发布',
    )
    await batchResolveUsernames()
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || e.message || '发布失败')
  } finally {
    posting.value = false
  }
}

async function onDelete(comment) {
  try {
    await ElMessageBox.confirm('确认删除此评论?', '删除确认', {
      confirmButtonText: '删除',
      cancelButtonText: '取消',
      type: 'warning',
    })
  } catch {
    return
  }
  try {
    await store.deleteComment(props.fileId, comment.id)
    ElMessage.success('评论已删除')
  } catch (e) {
    ElMessage.error(e.message || '删除失败')
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
.mobile-comment-thread {
  display: flex;
  flex-direction: column;
  gap: 12px;
  padding-bottom: 80px;
}

.mct-header {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 0;
  border-bottom: 1px solid var(--color-border-light, #ebeef5);
}

.mct-header h3 {
  margin: 0;
  font-size: 15px;
  font-weight: 600;
  display: flex;
  align-items: center;
  gap: 6px;
  color: var(--color-text-primary, #303133);
}

.mct-count {
  margin-left: 2px;
}

.mct-loading,
.mct-empty {
  padding: 40px 16px;
  text-align: center;
  color: var(--color-text-secondary, #909399);
  font-size: 13px;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
}

.mct-empty .hint {
  font-size: 12px;
  opacity: 0.75;
}

.mct-list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

/* Sticky 底部发布栏 */
.mct-compose {
  position: sticky;
  bottom: 0;
  left: 0;
  right: 0;
  display: flex;
  gap: 8px;
  align-items: flex-end;
  padding: 8px 12px;
  background: var(--color-bg-card, #fff);
  border-top: 1px solid var(--color-border-light, #ebeef5);
  z-index: 10;
}

.mct-input {
  flex: 1;
}

/* v2 PR6-P4: mobile 紧凑 mention dropdown */
.mct-compose {
  position: relative;
}
.mct-mention-dropdown {
  position: absolute;
  left: 0;
  right: 0;
  bottom: 100%;
  margin-bottom: 4px;
  background: var(--color-bg-card, #fff);
  border: 1px solid var(--color-border-light, #ebeef5);
  border-radius: 8px;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.08);
  max-height: 200px;
  overflow-y: auto;
  z-index: 1000;
}
.mct-mention-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 10px;
  cursor: pointer;
  font-size: 13px;
  transition: background 0.15s;
}
.mct-mention-item.active {
  background: var(--color-primary-bg, rgba(255, 122, 92, 0.08));
}
.mct-mention-avatar {
  flex-shrink: 0;
}
.mct-mention-info {
  flex: 1;
  min-width: 0;
}
.mct-mention-name {
  font-size: 13px;
  font-weight: 500;
  color: var(--color-text-primary, #303133);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.mct-mention-username {
  font-size: 11px;
  color: var(--color-text-secondary, #909399);
  font-family: monospace;
}

.mct-post-btn {
  flex-shrink: 0;
  height: 36px;
  padding: 0 14px;
  background: var(--color-primary, #409eff);
  color: var(--el-color-white);
  border: none;
  border-radius: 8px;
  font-size: 13px;
  font-weight: 500;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  min-width: 56px;
}

.mct-post-btn:disabled {
  background: var(--color-bg-page, #f5f7fa);
  color: var(--color-text-placeholder, #c0c4cc);
  cursor: not-allowed;
}

.mct-post-btn:not(:disabled):active {
  opacity: 0.85;
}

.is-loading {
  animation: spin 1s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}
</style>

<!-- v60-v67 教训: dark mode 跨组件覆盖必须放非 scoped <style> 块 -->
<style>
[data-theme="dark"] .mobile-comment-thread {
  background: var(--color-bg-page, #1a1d23);
}

[data-theme="dark"] .mct-compose {
  background: var(--color-bg-card, #2a2d35);
  border-top-color: var(--color-border-light, #3a3d45);
}

[data-theme="dark"] .mct-mention-dropdown {
  background: var(--color-bg-card, #2a2d35);
  border-color: var(--color-border-light, #3a3d45);
}

[data-theme="dark"] .mct-mention-item.active {
  background: rgba(255, 122, 92, 0.16);
}

[data-theme="dark"] .mention {
  color: var(--color-primary-light-3, #79bbff);
  background: rgba(64, 158, 255, 0.12);
}
</style>