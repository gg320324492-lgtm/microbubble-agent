<!--
  CommentThread.vue — v2 PR6 文件评论组件

  功能:
  - 列出文件评论（按 created_at 倒序）
  - 发布评论（自动解析 @username + 触发 mention + activity log）
  - 删除自己的评论 (owner or file owner)
  - 空态 / 加载态 / 错误态

  Props:
  - fileId: number 必填

  设计:
  - 复用 useNotificationsStore (fetchComments / postComment / deleteComment)
  - @ 自动 mention: 通过 postComment 后端自动解析 (@wangtianzhi 而非 @王天志)
  - 不做客户端 mention autocomplete (PR8 增强项)

  Dark mode: 非 scoped 块 (v60-v67 教训)
-->
<template>
  <div class="comment-thread">
    <div class="comment-thread-header">
      <h3>
        评论
        <el-badge
          v-if="comments.length > 0"
          :value="comments.length"
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
    <div v-else-if="comments.length === 0" class="comment-thread-empty">
      <el-icon :size="32"><ChatDotRound /></el-icon>
      <p>暂无评论</p>
      <p class="hint">在下方输入框写下第一条评论 (支持 @username)</p>
    </div>

    <!-- 评论列表 (倒序) -->
    <ul v-else class="comment-thread-list">
      <li
        v-for="c in comments"
        :key="c.id"
        class="comment-item"
      >
        <el-avatar
          :size="36"
          :src="userAvatarUrl(c.user_id)"
          class="comment-avatar"
        >
          {{ (c.user_name || '?').slice(0, 1) }}
        </el-avatar>
        <div class="comment-body">
          <div class="comment-meta">
            <strong class="comment-author">{{ c.user_name || `用户 #${c.user_id}` }}</strong>
            <span class="comment-time">{{ formatTime(c.created_at) }}</span>
            <el-popconfirm
              v-if="canDelete(c)"
              title="确认删除此评论？"
              confirm-button-text="删除"
              cancel-button-text="取消"
              @confirm="onDelete(c)"
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
          <div class="comment-content" v-html="formatContent(c.content)" />
          <div v-if="c.mentions && c.mentions.length > 0" class="comment-mentions">
            <span class="mention-tag" v-for="mid in c.mentions" :key="mid">
              @{{ usernameById(mid) }}
            </span>
          </div>
        </div>
      </li>
    </ul>

    <!-- 发布输入框 -->
    <div class="comment-thread-compose">
      <el-input
        v-model="newContent"
        type="textarea"
        :rows="3"
        :placeholder="placeholder"
        :maxlength="1000"
        show-word-limit
        resize="none"
      />
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

const props = defineProps({
  fileId: { type: Number, required: true },
  currentUserId: { type: Number, default: null },
  isFileOwner: { type: Boolean, default: false },
})

const route = useRoute()
const store = useNotificationsStore()
const newContent = ref('')
const posting = ref(false)
const loading = ref(false)
const errorMsg = ref(null)
const usernameMap = ref({})  // { user_id: username } 缓存

const comments = computed(() => store.commentsByFileId[props.fileId] || [])

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

/**
 * 渲染评论内容 + 解析 @username 为高亮 span
 *
 * 注意:
 * - 必须 escapeHtml 防 XSS (content 是用户输入)
 * - @username 来自后端 mention 解析结果 (comment.mentions[] 里的 user_id)
 * - 这里只 highlight 已经在 mention 列表里的 username, 不在列表里的 @xxx 当纯文本
 */
function formatContent(raw) {
  if (!raw) return ''
  // 1. escape HTML
  const escaped = raw
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;')
  // 2. @username 高亮 (匹配 _MENTION_PATTERN)
  // 复用后端 regex 语义: @([一-龥A-Za-z]{1,16})
  return escaped.replace(
    /@([一-龥A-Za-z]{1,16})/g,
    '<span class="mention">@$1</span>'
  )
}

function canDelete(comment) {
  if (!props.currentUserId) return false
  // 评论 owner 或 文件 owner 可删
  return comment.user_id === props.currentUserId || props.isFileOwner
}

function userAvatarUrl(userId) {
  if (!userId) return ''
  // 头像 URL 模式: /api/v1/members/{id}/avatar
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
    // 解析后获取所有 user_id 的 username (单次批查)
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
    // 一次性查 members 列表 (简单实现, 规模不大)
    const resp = await axios.get('/api/v1/members', {
      headers: { Authorization: `Bearer ${localStorage.getItem('access_token') || ''}` },
    })
    const map = { ...usernameMap.value }
    for (const m of resp.data.items || []) {
      map[m.id] = m.username || m.name
    }
    usernameMap.value = map
  } catch (e) {
    // ignore — fallback 到 id
  }
}

async function onPost() {
  const trimmed = newContent.value.trim()
  if (!trimmed) return
  posting.value = true
  errorMsg.value = null
  try {
    const resp = await store.postComment(props.fileId, trimmed)
    newContent.value = ''
    // 提示 mention 数量
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

async function onDelete(comment) {
  try {
    await store.deleteComment(props.fileId, comment.id)
    ElMessage.success('评论已删除')
  } catch (e) {
    errorMsg.value = e.message || '删除失败'
  }
}

onMounted(() => {
  fetchComments()
})

// fileId 变化时刷新
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

.comment-item {
  display: flex;
  align-items: flex-start;
  gap: 12px;
  padding: 12px;
  background: var(--color-bg-page, #f5f7fa);
  border-radius: 8px;
  transition: background 0.15s;
}

.comment-avatar {
  flex-shrink: 0;
}

.comment-body {
  flex: 1;
  min-width: 0;
}

.comment-meta {
  display: flex;
  align-items: center;
  gap: 8px;
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

.comment-thread-compose {
  margin-top: 8px;
  padding-top: 12px;
  border-top: 1px solid var(--color-border-light, #ebeef5);
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

/* Dark mode 非 scoped 块 (v60-v67 教训) */
[data-theme="dark"] .comment-item {
  background: var(--color-bg-page, #2a2d35);
}

[data-theme="dark"] .comment-content :deep(.mention) {
  background: rgba(255, 122, 92, 0.16);
}

[data-theme="dark"] .comment-thread-compose {
  border-top-color: var(--color-border-dark, rgba(255, 255, 255, 0.08));
}

[data-theme="dark"] .comment-thread-hint code {
  background: var(--color-bg-page, #2a2d35);
}
</style>
</content>
</invoke>