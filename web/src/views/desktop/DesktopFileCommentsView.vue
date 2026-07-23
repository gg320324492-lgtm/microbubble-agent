<!--
  DesktopFileCommentsView.vue — W68 路线 F-4 桌面端评论独立路由页

  2026-07-24 主指挥协调范式第 45 守恒.

  职责:
  - 顶部导航 (返回 + 文件名 + 评论计数)
  - 评论列表 (嵌套回复展开/收起) - 复用 DesktopCommentThread recursive
  - 底部输入栏 (DesktopCommentInput - textarea + @mention + 发送按钮)
  - resolved 切换 tab (未解决 / 全部 / 已解决)
  - 评论操作菜单 (resolved toggle / delete / edit / reply)
    - 通过 DesktopCommentThread emit('reply'/'toggle-resolved'/'delete'/'save-edit'/'cancel-edit')
    - 右键菜单复用 Element Plus el-popover 模式 (而非 MobileContextMenu 浮动定位)

  设计原则:
  - 0 production code 改动铁律 — 复用 useFileComments (F-3) + DesktopCommentThread + DesktopCommentInput
  - 桌面布局: max-width 容器居中 (跟 MobileFileCommentsView F-3 对等, 路径相同)
  - desktop 端有 inline edit (5 分钟窗口), 移动端 mobile 暂未实现 (PR9 后端已支持)
  - desktop 端走 el-popover + hover 触发操作按钮, mobile 端走 LongPressWrapper

  数据流:
  - onMounted: fetchFileMeta + listComments + batchResolveMembers (并行)
  - sendComment: postComment → 自动 prepend
  - onReply: 写入 newContent + mention prefix → focus 输入栏
  - onEditSave: updateComment → 清空 editing state
  - onDelete / onToggleResolved: 走 base composable
-->

<template>
  <div class="desktop-file-comments-view">
    <!-- 顶部导航 -->
    <div class="dfcv-header">
      <el-button link @click="goBack" class="dfcv-back-btn" aria-label="返回">
        <el-icon><ArrowLeft /></el-icon>
        <span>返回</span>
      </el-button>
      <h2 class="dfcv-title">
        <el-icon class="dfcv-title-icon"><ChatDotRound /></el-icon>
        <span>{{ headerTitle }}</span>
        <el-badge
          v-if="total > 0"
          :value="total"
          :max="99"
          class="dfcv-count-badge"
          type="primary"
        />
      </h2>
      <span class="dfcv-subtitle">{{ headerSubtitle }}</span>
    </div>

    <!-- tab 切换 -->
    <nav class="dfcv-tabs" role="tablist">
      <button
        v-for="t in tabsWithCounts"
        :key="t.name"
        type="button"
        role="tab"
        :aria-selected="activeTab === t.name"
        :class="{ active: activeTab === t.name }"
        class="dfcv-tab-btn"
        @click="switchTab(t.name)"
      >
        <span>{{ t.label }}</span>
        <span v-if="t.count > 0" class="dfcv-tab-badge">{{ t.count }}</span>
      </button>
    </nav>

    <!-- 评论列表 -->
    <main class="dfcv-body">
      <!-- 加载态 -->
      <div v-if="loading && treeTop.length === 0" class="dfcv-loading">
        <el-icon class="is-loading"><Loading /></el-icon>
        <span>加载评论中...</span>
      </div>

      <!-- 空态 -->
      <div v-else-if="treeTop.length === 0" class="dfcv-empty">
        <el-icon :size="48"><ChatDotRound /></el-icon>
        <p class="empty-title">{{ emptyText }}</p>
        <p class="empty-hint">{{ emptyHint }}</p>
      </div>

      <!-- 数据态 -->
      <ul v-else class="dfcv-list">
        <li v-for="top in treeTop" :key="top.id" class="dfcv-top-item">
          <DesktopCommentThread
            :comment="top"
            :depth="0"
            :current-user-id="currentUserId"
            :is-file-owner="isFileOwner"
            :username-map="usernameMap"
            :editing-comment-id="editingCommentId"
            :edit-draft="editDraft"
            @reply="onReply"
            @edit="startEditComment"
            @toggle-resolved="onToggleResolved"
            @delete="onDeleteCommentWithConfirm"
            @save-edit="onSaveEdit"
            @cancel-edit="cancelEditComment"
          />
        </li>
      </ul>
    </main>

    <!-- 底部输入栏 (sticky) -->
    <div class="dfcv-compose">
      <DesktopCommentInput
        v-model="newContent"
        :file-id="fileId"
        :members-list="membersList"
        :placeholder="placeholder"
        :busy="posting"
        :auto-focus="false"
        @post="onPost"
        @typing="onTyping"
      />
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, watch } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { ArrowLeft, ChatDotRound, Loading } from '@element-plus/icons-vue'
import { useCommentTree } from '@/composables/useCommentTree'
import { useFileCommentsDesktop } from '@/composables/useFileCommentsDesktop'
import DesktopCommentThread from '@/components/desktop/DesktopCommentThread.vue'
import DesktopCommentInput from '@/components/desktop/DesktopCommentInput.vue'

const props = defineProps({
  fileId: { type: [String, Number], required: true },
})

const router = useRouter()
const { buildCommentTree } = useCommentTree()

const {
  // state
  fileMeta,
  comments,
  loading,
  posting,
  total,
  openCount,
  resolvedCount,
  filteredComments,
  membersList,
  usernameMap,
  editingCommentId,
  editDraft,
  activeTab,
  currentUserId,
  isFileOwner,
  // actions
  fetchFileMeta,
  batchResolveMembers,
  listComments,
  postComment,
  onEditComment,
  onToggleResolved,
  onDeleteComment,
  onReplyPrefix,
  startEditComment,
  cancelEditComment,
  switchTab,
} = useFileCommentsDesktop(props.fileId)

const newContent = ref('')

// === 计算属性 ===
const treeTop = computed(() => buildCommentTree(filteredComments.value).top)

const tabs = [
  { name: 'open',     label: '未解决' },
  { name: 'all',      label: '全部' },
  { name: 'resolved', label: '已解决' },
]

const tabsWithCounts = computed(() =>
  tabs.map((t) => ({
    ...t,
    count: t.name === 'open' ? openCount.value
      : t.name === 'all' ? total.value
      : resolvedCount.value,
  })),
)

const headerTitle = computed(() => {
  if (fileMeta.value?.title) return fileMeta.value.title
  if (fileMeta.value?.file_name) return fileMeta.value.file_name
  return '评论'
})

const headerSubtitle = computed(() => {
  if (!fileMeta.value?.file_type) return ''
  const size = fileMeta.value.file_size
  if (size && size > 0) {
    return `${fileMeta.value.file_type.toUpperCase()} · ${formatSize(size)}`
  }
  return fileMeta.value.file_type.toUpperCase()
})

const placeholder = computed(() => {
  if (!currentUserId.value) return '请先登录后再评论'
  return '写评论... @username 提醒 · Cmd/Ctrl + Enter 发送'
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

// === 工具函数 ===
function formatSize(bytes) {
  if (!bytes || bytes === 0) return '0 B'
  const k = 1024
  const sizes = ['B', 'KB', 'MB', 'GB']
  const i = Math.floor(Math.log(bytes) / Math.log(k))
  return `${(bytes / Math.pow(k, i)).toFixed(1)} ${sizes[i]}`
}

// === Actions ===
async function fetchAll() {
  await Promise.all([
    fetchFileMeta(),
    listComments(),
    batchResolveMembers(),
  ])
}

async function onPost(content) {
  if (!content || !content.trim()) return
  try {
    const resp = await postComment(content.trim())
    newContent.value = ''
    const mentionCount = resp?.mentioned_user_ids?.length || 0
    ElMessage.success(mentionCount > 0 ? `评论已发布, 提醒 ${mentionCount} 人` : '评论已发布')
  } catch (e) {
    ElMessage.error(e?.response?.data?.error?.message || e?.message || '发布失败')
  }
}

function onTyping(_val) {
  // hook for future typing indicator — 预留 (W68 PR9 WS 增量提示)
}

function onReply(comment) {
  if (!comment || !comment.user_id) return
  // 在输入栏添加 @username 前缀, 触发 focus
  const prefix = onReplyPrefix(comment)
  if (!newContent.value.startsWith(prefix)) {
    newContent.value = prefix + newContent.value
  }
  // focus textarea (下一 tick)
  setTimeout(() => {
    const ta = document.querySelector('.desktop-comment-input textarea')
    if (ta) {
      ta.focus()
      const pos = newContent.value.length
      ta.setSelectionRange(pos, pos)
    }
  }, 50)
  ElMessage.info(`回复 ${comment.user_name || '评论'} — 请在下方输入框继续`)
}

async function onSaveEdit(commentId, newContentVal) {
  await onEditComment(commentId, newContentVal)
}

async function onDeleteCommentWithConfirm(comment) {
  try {
    await ElMessageBox.confirm(
      `确认删除 ${comment?.user_name || '此用户'} 的评论? 子评论也会一并删除.`,
      '删除确认',
      {
        confirmButtonText: '删除',
        cancelButtonText: '取消',
        type: 'warning',
      },
    )
  } catch {
    return
  }
  await onDeleteComment(comment)
}

function goBack() {
  // desktop 优先回文件详情页 (评论嵌内) — 桌面端已经有 FileDetailView 含评论
  // 如果直接来自桌面 Drive grid, 退回 /drive
  if (window.history.length > 1) {
    router.back()
  } else {
    router.push(`/drive/file/${props.fileId}`)
  }
}

onMounted(() => {
  fetchAll()
})

watch(() => props.fileId, (newId, oldId) => {
  if (newId && newId !== oldId) {
    fetchAll()
  }
})
</script>

<style scoped>
.desktop-file-comments-view {
  display: flex;
  flex-direction: column;
  min-height: 100%;
  max-width: 880px;
  margin: 0 auto;
  background: var(--color-bg-page, #f5f7fa);
}

.dfcv-header {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 16px 24px 12px;
  background: var(--color-bg-card, #fff);
  border-bottom: 1px solid var(--color-border-light, #ebeef5);
  flex-wrap: wrap;
}

.dfcv-back-btn {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  font-size: 13px;
}

.dfcv-title {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  margin: 0;
  font-size: 18px;
  font-weight: 600;
  color: var(--color-text-primary, #303133);
  flex: 1;
  min-width: 0;
}

.dfcv-title-icon {
  color: var(--color-primary, #ff7a5c);
  flex-shrink: 0;
}

.dfcv-count-badge {
  margin-left: 4px;
}

.dfcv-subtitle {
  font-size: 12px;
  color: var(--color-text-secondary, #909399);
  margin-left: auto;
}

.dfcv-tabs {
  display: flex;
  gap: 6px;
  padding: 8px 24px;
  background: var(--color-bg-card, #fff);
  border-bottom: 1px solid var(--color-border-light, #ebeef5);
}

.dfcv-tab-btn {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 8px 16px;
  background: transparent;
  border: none;
  border-radius: 8px;
  font-size: 13px;
  color: var(--color-text-secondary, #606266);
  cursor: pointer;
  transition: background 0.15s, color 0.15s;
}

.dfcv-tab-btn:hover {
  background: var(--color-bg-page, #f5f7fa);
}

.dfcv-tab-btn.active {
  background: var(--color-primary-bg, rgba(255, 122, 92, 0.1));
  color: var(--color-primary, #ff7a5c);
  font-weight: 600;
}

.dfcv-tab-badge {
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

.dfcv-tab-btn.active .dfcv-tab-badge {
  background: var(--color-primary, #ff7a5c);
}

.dfcv-body {
  flex: 1;
  padding: 16px 24px;
  overflow-y: auto;
}

.dfcv-loading,
.dfcv-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 12px;
  padding: 80px 20px;
  text-align: center;
  color: var(--color-text-secondary, #909399);
  font-size: 14px;
}

.dfcv-empty .empty-title {
  margin: 0;
  font-size: 15px;
  font-weight: 500;
  color: var(--color-text-primary, #303133);
}

.dfcv-empty .empty-hint {
  margin: 0;
  font-size: 12px;
  opacity: 0.75;
}

.dfcv-list {
  list-style: none;
  margin: 0;
  padding: 0 0 24px 0;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.dfcv-top-item {
  list-style: none;
}

.dfcv-compose {
  position: sticky;
  bottom: 0;
  left: 0;
  right: 0;
  padding: 12px 24px;
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
[data-theme="dark"] .desktop-file-comments-view {
  background: var(--color-bg-page, #1a1d23);
}

[data-theme="dark"] .dfcv-header,
[data-theme="dark"] .dfcv-tabs,
[data-theme="dark"] .dfcv-compose {
  background: var(--color-bg-card, #2a2d35);
  border-color: var(--color-border-light, #3a3d45);
}
</style>