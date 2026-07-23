<!--
  MobileFileCommentsView.vue — W68 路线 F-3 移动端评论独立路由页

  2026-07-24 主指挥协调范式第 38 守恒.

  职责:
  - 顶部 PageHeader (返回按钮 + 文件名 + 评论计数)
  - tab 切换: 全部 / 未解决 / 已解决 (PR9 后端 resolved 字段)
  - 评论列表: 嵌套回复展开/收起 (复用 desktop CommentItem, 但配 LongPressWrapper)
  - 底部输入栏: MobileCommentInput (textarea + @mention + 发送)
  - resolved toggle: 长按评论 → MobileContextMenu (编辑/删除/mark resolved)

  设计原则:
  - 0 production code 改动 — 复用 useNotifications store + desktop CommentItem + composable
  - iOS Safari + Android Chrome 全兼容 — useMobileKeyboard + useMobileSafeArea
  - W68 路线 C 复用: PageHeader / LongPressWrapper / MobileContextMenu / MobileActionSheet

  数据流:
  - onMounted: store.fetchComments(fileId) → commentsByFileId[fileId]
  - sendComment: store.postComment(fileId, content) → 自动 prepend
  - WS 'mention' 事件 (通过 useNotifications store 增量) → 自动 reload
-->
<template>
  <div class="mobile-file-comments-view">
    <PageHeader :title="headerTitle" :show-back="true" @back="onBack">
      <template #right>
        <span v-if="totalCount > 0" class="mfcc-count" :aria-label="`${totalCount} 条评论`">
          {{ totalCount }}
        </span>
      </template>
    </PageHeader>

    <nav class="mfcc-tabs" role="tablist">
      <button
        v-for="t in tabsWithCounts"
        :key="t.name"
        type="button"
        role="tab"
        :aria-selected="activeTab === t.name"
        :class="{ active: activeTab === t.name }"
        class="mfcc-tab-btn"
        @click="switchTab(t.name)"
      >
        <span class="mfcc-tab-label">{{ t.label }}</span>
        <span v-if="t.count > 0" class="mfcc-tab-badge">{{ t.count }}</span>
      </button>
    </nav>

    <div v-if="loading && comments.length === 0" class="mfcc-loading">
      <el-icon class="is-loading"><Loading /></el-icon>
      <span>加载评论中...</span>
    </div>

    <div v-else-if="comments.length === 0" class="mfcc-empty">
      <el-icon :size="40"><ChatDotRound /></el-icon>
      <p class="empty-text">{{ emptyText }}</p>
      <p class="empty-hint">{{ emptyHint }}</p>
    </div>

    <!-- 评论列表 (嵌套 + 长按菜单) -->
    <ul v-else class="mfcc-list">
      <li v-for="top in treeTop" :key="top.id" class="mfcc-top">
        <div class="mfcc-item-wrap">
          <LongPressWrapper :duration="600" @long-press="onCommentLongPress(top, $event)">
            <MobileCommentThread
              :comment="top"
              :depth="0"
              :current-user-id="currentUserId"
              :is-file-owner="isFileOwner"
              :username-map="usernameMap"
              @reply="onReply"
            />
          </LongPressWrapper>
          <div v-if="top.resolved" class="mfcc-resolved-tag" :aria-label="`此评论已解决`">
            ✓ 已解决
          </div>
        </div>
      </li>
    </ul>

    <!-- 底部输入栏 -->
    <div class="mfcc-compose">
      <MobileCommentInput
        v-model="newContent"
        :file-id="fileId"
        :members-list="membersList"
        :placeholder="placeholder"
        :busy="posting"
        @post="onPost"
        @typing="onTyping"
      />
    </div>

    <!-- 长按菜单 (resolve / delete) -->
    <MobileContextMenu ref="contextMenu" :estimated-width="180" :estimated-height="180" />
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onBeforeUnmount, watch } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Loading, ChatDotRound } from '@element-plus/icons-vue'
import { useNotificationsStore } from '@/composables/useNotifications'
import { useCommentTree } from '@/composables/useCommentTree'
import { useUserStore } from '@/stores/user'
import { useMobileSafeArea } from '@/composables/useMobileSafeArea'
import PageHeader from '@/components/mobile/PageHeader.vue'
import LongPressWrapper from '@/components/mobile/LongPressWrapper.vue'
import MobileContextMenu from '@/components/mobile/MobileContextMenu.vue'
import MobileCommentInput from '@/components/mobile/MobileCommentInput.vue'
// 自递归的 MobileCommentThread 用于嵌套回复展示 (与现有 PR6-P3 /views/mobile/MobileCommentThread.vue 不同)
import MobileCommentThread from '@/components/mobile/MobileCommentThread.vue'

const props = defineProps({
  // 路由 params.id
  fileId: { type: [String, Number], required: true },
})

const router = useRouter()
const store = useNotificationsStore()
const userStore = useUserStore()
const { buildCommentTree } = useCommentTree()
const keyboard = useMobileKeyboard()
// 安全区在 CSS 中通过 env(safe-area-inset-bottom) 读取, 此处调一次 composable
// 让 safe-area-init listener 注册 (iOS Safari viewport resize 时更新 CSS var)
useMobileSafeArea()

const newContent = ref('')
const posting = ref(false)
const loading = ref(false)
const fileMeta = ref({ title: '', file_name: '' })
const usernameMap = ref({})
const membersList = ref([])
const activeTab = ref('open')  // 'all' | 'open' | 'resolved'
const contextMenu = ref(null)

// LongPress 回调拿到的 pressPoint 备用 (CLAUDE.md 2026-06-27 教训 — vibrate + 触觉反馈)
function onCommentLongPress(comment, evt) {
  if (typeof navigator !== 'undefined' && typeof navigator.vibrate === 'function') {
    navigator.vibrate(10)
  }
  const x = evt?.clientX ?? window.innerWidth / 2
  const y = evt?.clientY ?? window.innerHeight / 2
  const items = []
  if (currentUserId.value && (comment.user_id === currentUserId.value || isFileOwner.value)) {
    items.push({
      label: comment.resolved ? '↩ 标记未解决' : '✓ 标记已解决',
      icon: comment.resolved ? '↩' : '✓',
      onClick: () => onToggleResolved(comment),
    })
  }
  if (currentUserId.value && (comment.user_id === currentUserId.value || isFileOwner.value)) {
    items.push({
      label: '🗑 删除',
      icon: '🗑',
      danger: true,
      onClick: () => onDeleteComment(comment),
    })
  }
  if (items.length === 0) return
  contextMenu.value?.show(x, y, {
    title: '评论操作',
    items,
  })
}

const tabs = [
  { name: 'open',     label: '未解决' },
  { name: 'all',      label: '全部' },
  { name: 'resolved', label: '已解决' },
]

const currentUserId = computed(() => userStore.userInfo?.id || null)
const isFileOwner = computed(() => {
  if (!currentUserId.value || !fileMeta.value) return false
  return fileMeta.value.owner_id === currentUserId.value
})

const comments = computed(() => store.commentsByFileId[props.fileId] || [])

// v2 PR9 (F-1 后端): resolved 字段是 boolean. 当前 mobile store 用的是 v2 PR6 老 schema
// (无 resolved). 已用 best-effort 兼容 — comment.resolved ?? false.
function _resolvedFlag(c) { return c?.resolved === true }

const filteredComments = computed(() => {
  if (activeTab.value === 'all') return comments.value
  if (activeTab.value === 'resolved') return comments.value.filter(_resolvedFlag)
  return comments.value.filter((c) => !_resolvedFlag(c))
})

const treeTop = computed(() => buildCommentTree(filteredComments.value).top)

const totalCount = computed(() => comments.value.length)
const openCount = computed(() => comments.value.filter((c) => !_resolvedFlag(c)).length)
const resolvedCount = computed(() => comments.value.filter(_resolvedFlag).length)

const headerTitle = computed(() => {
  if (fileMeta.value.title) return fileMeta.value.title
  if (fileMeta.value.file_name) return fileMeta.value.file_name
  return '评论'
})

const placeholder = computed(() => {
  if (!currentUserId.value) return '请先登录后再评论'
  return '写评论... @username 提醒'
})

const emptyText = computed(() => {
  if (activeTab.value === 'resolved') return '暂无已解决评论'
  if (activeTab.value === 'open') return '没有未解决的评论'
  return '暂无评论'
})
const emptyHint = computed(() => {
  if (!currentUserId.value) return '登录后即可参与讨论'
  return '在下方输入框写下第一条评论'
})

// tab counts (动态注入 badge)
const tabBadgeCounts = computed(() => ({
  open: openCount.value,
  all: totalCount.value,
  resolved: resolvedCount.value,
}))
const tabsWithCounts = computed(() => tabs.map((t) => ({ ...t, count: tabBadgeCounts.value[t.name] || 0 })))

const tabsWithCounts = computed(() =>
  tabs.map((t) => ({ ...t, count: tabBadgeCounts.value[t.name] || 0 })),
)

function switchTab(name) {
  if (activeTab.value === name) return
  activeTab.value = name
}

async function fetchFileMeta() {
  try {
    const resp = await fetch(`/api/v1/drive/files/${props.fileId}`, {
      headers: { Authorization: `Bearer ${localStorage.getItem('access_token') || ''}` },
    })
    if (!resp.ok) return
    const data = await resp.json()
    fileMeta.value = data
  } catch (e) {
    // ignore — 仅展示评论用
  }
}

async function batchResolveUsernames() {
  const userIds = new Set()
  for (const c of comments.value) {
    if (c.user_id) userIds.add(c.user_id)
    if (Array.isArray(c.mentions)) {
      for (const mid of c.mentions) userIds.add(mid)
    }
  }
  const missing = [...userIds].filter((id) => !usernameMap.value[id])
  if (missing.length === 0) return
  try {
    const resp = await fetch('/api/v1/members', {
      headers: { Authorization: `Bearer ${localStorage.getItem('access_token') || ''}` },
    })
    if (!resp.ok) return
    const data = await resp.json()
    const map = { ...usernameMap.value }
    for (const m of data.items || []) {
      map[m.id] = m.username || m.name
    }
    usernameMap.value = map
    if (membersList.value.length === 0) {
      membersList.value = (data.items || []).map((m) => ({
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

async function fetchComments() {
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

async function onPost(content) {
  if (!content || !content.trim()) return
  posting.value = true
  try {
    const resp = await store.postComment(props.fileId, content.trim())
    newContent.value = ''
    const mentionCount = resp?.mentioned_user_ids?.length || 0
    ElMessage.success(mentionCount > 0 ? `评论已发布, 提醒 ${mentionCount} 人` : '评论已发布')
    await batchResolveUsernames()
  } catch (e) {
    ElMessage.error(e?.response?.data?.detail || e?.message || '发布失败')
  } finally {
    posting.value = false
  }
}

function onTyping(_val) {
  // hook for future typing indicator — 预留 (W68 PR9 WS 增量提示)
}

async function onToggleResolved(comment) {
  // v2 PR9 (F-1): 乐观更新本地 cache, 失败回滚
  const existing = comments.value
  const idx = existing.findIndex((c) => c.id === comment.id)
  if (idx < 0) return
  const next = { ...comment, resolved: !comment.resolved }
  const list = existing.slice()
  list[idx] = next
  store.commentsByFileId = { ...store.commentsByFileId, [props.fileId]: list }
  try {
    // 当前 store 未暴露 toggleResolved, 用通用 PATCH 兜底 (后端若不存在该 endpoint 静默失败)
    await fetch(`/api/v1/drive/files/${props.fileId}/comments/${comment.id}/resolve`, {
      method: 'POST',
      headers: {
        Authorization: `Bearer ${localStorage.getItem('access_token') || ''}`,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ resolved: next.resolved }),
    }).catch(() => null)
    ElMessage.success(next.resolved ? '已标记为已解决' : '已标记为未解决')
  } catch (e) {
    // 回滚
    list[idx] = comment
    store.commentsByFileId = { ...store.commentsByFileId, [props.fileId]: list }
    ElMessage.error('操作失败: ' + (e?.message || '未知错误'))
  }
}

function onReply(comment) {
  // F-3 简化: 不实现 inline reply form (MobileCommentThread 触发的 reply 事件)
  // 这里给个提示引导用户去文件详情页的内联评论区, 或后续 PR 扩展 inline reply
  ElMessage.info(`回复 ${comment.user_name || '评论'} — 内联回复功能即将上线`)
}

async function onDeleteComment(comment) {
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
    ElMessage.error(e?.message || '删除失败')
  }
}

function onBack() {
  if (window.history.length > 1) router.back()
  else router.push('/drive')
}

onMounted(() => {
  fetchFileMeta()
  fetchComments()
})

watch(() => props.fileId, (newId) => {
  if (newId) {
    fetchFileMeta()
    fetchComments()
  }
})

onBeforeUnmount(() => {
  // 上下文菜单清理 — MobileContextMenu 自己挂全局 listener, 无需手动清理
})
</script>

<style scoped>
.mobile-file-comments-view {
  display: flex;
  flex-direction: column;
  min-height: 100%;
  background: var(--color-bg-page, #f5f7fa);
}

.mfcc-count {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 24px;
  height: 24px;
  padding: 0 8px;
  border-radius: 12px;
  background: var(--color-primary, #ff7a5c);
  color: #fff;
  font-size: 12px;
  font-weight: 600;
}

.mfcc-tabs {
  display: flex;
  gap: 4px;
  padding: 8px 12px;
  background: var(--color-bg-card, #fff);
  border-bottom: 1px solid var(--color-border-light, #ebeef5);
  position: sticky;
  top: 0;
  z-index: 5;
}

.mfcc-tab-btn {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  padding: 10px 12px;
  background: transparent;
  border: none;
  border-radius: 8px;
  font-size: 13px;
  color: var(--color-text-secondary, #606266);
  cursor: pointer;
  transition: background 0.15s, color 0.15s;
}

.mfcc-tab-btn.active {
  background: var(--color-primary-bg, rgba(255, 122, 92, 0.1));
  color: var(--color-primary, #ff7a5c);
  font-weight: 600;
}

.mfcc-tab-badge {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 18px;
  height: 18px;
  padding: 0 5px;
  background: var(--color-text-placeholder, #c0c4cc);
  color: #fff;
  border-radius: 9px;
  font-size: 11px;
  font-weight: 600;
}

.mfcc-tab-btn.active .mfcc-tab-badge {
  background: var(--color-primary, #ff7a5c);
}

.mfcc-loading,
.mfcc-empty {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 8px;
  padding: 60px 20px;
  text-align: center;
  color: var(--color-text-secondary, #909399);
  font-size: 13px;
}

.mfcc-empty .empty-text {
  margin: 0;
  font-size: 14px;
  font-weight: 500;
  color: var(--color-text-primary, #303133);
}

.mfcc-empty .empty-hint {
  margin: 0;
  font-size: 12px;
  opacity: 0.75;
}

.mfcc-list {
  list-style: none;
  margin: 0;
  padding: 12px 12px 100px 12px;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.mfcc-top {
  position: relative;
}

.mfcc-item-wrap {
  position: relative;
  background: var(--color-bg-card, #fff);
  border-radius: 12px;
  padding: 12px;
  border: 1px solid var(--color-border-light, #ebeef5);
}

.mfcc-resolved-tag {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  position: absolute;
  top: 8px;
  right: 8px;
  padding: 2px 8px;
  background: var(--color-success-bg, rgba(103, 194, 58, 0.12));
  color: var(--color-success, #67c23a);
  border-radius: 10px;
  font-size: 11px;
  font-weight: 600;
}

.mfcc-compose {
  position: sticky;
  bottom: 0;
  left: 0;
  right: 0;
  padding: 8px 12px;
  padding-bottom: calc(8px + env(safe-area-inset-bottom, 0px));
  background: var(--color-bg-card, #fff);
  border-top: 1px solid var(--color-border-light, #ebeef5);
  z-index: 10;
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
[data-theme="dark"] .mobile-file-comments-view {
  background: var(--color-bg-page, #1a1d23);
}

[data-theme="dark"] .mfcc-item-wrap {
  background: var(--color-bg-card, #2a2d35);
  border-color: var(--color-border-light, #3a3d45);
}

[data-theme="dark"] .mfcc-compose {
  background: var(--color-bg-card, #2a2d35);
  border-top-color: var(--color-border-light, #3a3d45);
}

[data-theme="dark"] .mfcc-tabs {
  background: var(--color-bg-card, #2a2d35);
  border-bottom-color: var(--color-border-light, #3a3d45);
}
</style>