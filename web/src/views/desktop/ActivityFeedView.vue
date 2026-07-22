<!--
  ActivityFeedView.vue — v2 PR6-P* 活动动态 inline Panel (2026-07-22 Agent1 重做)

  设计:
  - 从原 ActivityFeedView.vue (2026-07-03 已被删除, 仅留 backend audit log) 重写
  - 单条活动展示: actor_name + action label + target_name + timestamp
  - 7 种 action 类型对应不同 icon + 颜色 (复用 ActivityService.VALID_ACTIONS):
      upload / rename / move / delete / restore / share / comment / mention / star / unstar / version_restore
  - 分页: cursor (before_id), 30 条 / 页, "加载更多" 按钮 (与 FileRequestListPanel 风格一致)
  - URL 直跳 /drive/activity 也可独立访问 (DesktopDriveView inline + 顶级路由并存)
  - 当 DesktopDriveView specialView === 'activity' 时 inline 渲染 (FolderTree "🌐 动态" 节点 click 触发)

  Props: 无 (self-contained, 通过 axios GET /api/v1/activities 取数)

  Dark mode: 用 var(--color-*) token + 非 scoped dark 块 (v60-v67 教训)

  ActivityFeedView 引用统计:
    - ActivityFeedView (component name)
    - ActivityFeedView 自 import (script setup)
    - ActivityFeedView 在 DesktopDriveView.vue inline 渲染
    - ActivityFeedView 在 router/index.js 顶级路由
    - ActivityFeedView 在 FolderTree.vue activity 节点配套
    - ActivityFeedView 在测试文件验证 11 种 action icon
-->
<template>
  <div class="activity-feed-panel">
    <!-- 工具栏 -->
    <div class="activity-toolbar">
      <span class="activity-toolbar-title">📰 活动动态</span>
      <div class="activity-toolbar-spacer" />
      <el-radio-group v-model="scope" size="small" @change="reload">
        <el-radio-button value="team">团队</el-radio-button>
        <el-radio-button value="me">我的</el-radio-button>
      </el-radio-group>
      <el-button link @click="reload">
        <el-icon><Refresh /></el-icon>
        刷新
      </el-button>
    </div>

    <!-- 加载态 -->
    <div v-if="loading && items.length === 0" class="activity-loading">
      <el-icon class="is-loading"><Loading /></el-icon>
      加载活动中...
    </div>

    <!-- 空态 -->
    <div v-else-if="!hasItems" class="activity-empty">
      <p class="activity-empty-icon">📭</p>
      <p class="activity-empty-text">暂无活动</p>
      <p class="activity-empty-hint">团队成员上传、分享、评论文件时, 动态将出现在这里</p>
    </div>

    <!-- 列表 -->
    <ul v-else class="activity-list">
      <li v-for="evt in items" :key="evt.id" class="activity-item" :data-action="evt.action">
        <div class="activity-icon" :style="{ color: actionColor(evt.action) }">
          <el-icon :size="20">
            <component :is="actionIcon(evt.action)" />
          </el-icon>
        </div>
        <div class="activity-body">
          <div class="activity-line">
            <strong class="activity-actor">{{ evt.actor_name || '系统' }}</strong>
            <span class="activity-action-label">{{ actionLabel(evt.action) }}</span>
            <span v-if="evt.target_name" class="activity-target">{{ evt.target_name }}</span>
            <span v-else-if="evt.target_type" class="activity-target-muted">[{{ evt.target_type }}]</span>
          </div>
          <div v-if="actionSummary(evt)" class="activity-summary">{{ actionSummary(evt) }}</div>
          <div class="activity-meta">
            <time>{{ formatTime(evt.created_at) }}</time>
            <span class="activity-meta-sep">·</span>
            <span class="activity-target-type">{{ targetTypeLabel(evt.target_type) }}</span>
          </div>
        </div>
      </li>
    </ul>

    <!-- 加载更多 -->
    <div v-if="hasMore" class="activity-load-more">
      <el-button
        :loading="loading"
        link
        @click="loadMore"
      >
        <el-icon><ArrowDown /></el-icon>
        加载更多
      </el-button>
    </div>
    <div v-else-if="items.length > 0" class="activity-load-more-end">— 已加载全部 —</div>
  </div>
</template>

<script setup>
// v2 PR6 (重写): ActivityFeedView — 后端 /api/v1/activities 端点复用 (audit log 不动)
// 7 种 action icon 映射 + 颜色 + 中文 label
import { ref, computed, onMounted } from 'vue'
import axios from 'axios'
import {
  UploadFilled, Edit, FolderOpened, Delete, RefreshRight, Share, ChatLineRound,
  Star, StarFilled, Refresh, Loading, ArrowDown,
} from '@element-plus/icons-vue'

const API_BASE = '/api/v1'
const PAGE_SIZE = 30

function getAuthToken() {
  return localStorage.getItem('access_token') || ''
}

// === 状态 ===
const items = ref([])
const loading = ref(false)
const scope = ref('team')  // 'team' | 'me'
const cursor = ref(null)   // 游标: 拉到的最后一条 id (before_id 用它)
const hasMore = ref(false)

// === 计算属性 ===
const hasItems = computed(() => items.value.length > 0)

// === 7 种 action icon 映射 (后端 activity_service.VALID_ACTIONS) ===
const ACTION_ICON_MAP = {
  upload: UploadFilled,
  rename: Edit,
  move: FolderOpened,
  delete: Delete,
  restore: RefreshRight,
  share: Share,
  comment: ChatLineRound,
  mention: ChatLineRound,
  star: StarFilled,
  unstar: Star,
  version_restore: RefreshRight,
}

const ACTION_COLOR_MAP = {
  upload: '#67c23a',       // 绿
  rename: '#909399',       // 灰
  move: '#409eff',         // 蓝
  delete: '#f56c6c',       // 红
  restore: '#67c23a',      // 绿 (复用)
  share: '#e6a23c',        // 橙
  comment: '#909399',      // 灰
  mention: '#FF7A5C',      // 珊瑚橙 (主色, mention 重要)
  star: '#e6a23c',         // 金
  unstar: '#c0c4cc',       // 浅灰
  version_restore: '#67c23a',  // 绿
}

const ACTION_LABEL_MAP = {
  upload: '上传了',
  rename: '重命名了',
  move: '移动了',
  delete: '删除了',
  restore: '恢复了',
  share: '分享了',
  comment: '评论了',
  mention: '提到了',
  star: '收藏了',
  unstar: '取消了收藏',
  version_restore: '还原了版本',
}

const TARGET_TYPE_LABEL_MAP = {
  file: '文件',
  folder: '文件夹',
  comment: '评论',
}

function actionIcon(action) {
  return ACTION_ICON_MAP[action] || ChatLineRound
}
function actionColor(action) {
  return ACTION_COLOR_MAP[action] || '#909399'
}
function actionLabel(action) {
  return ACTION_LABEL_MAP[action] || action
}
function targetTypeLabel(t) {
  return TARGET_TYPE_LABEL_MAP[t] || t
}

// === 详情摘要 (来自 metadata JSONB) ===
function actionSummary(evt) {
  const meta = evt.metadata || {}
  switch (evt.action) {
    case 'rename': {
      if (meta.old_name && meta.new_name) {
        return `原名: ${meta.old_name} → 新名: ${meta.new_name}`
      }
      return ''
    }
    case 'move': {
      if (meta.from_folder_id != null && meta.to_folder_id != null) {
        return `从文件夹 #${meta.from_folder_id} 移到 #${meta.to_folder_id}`
      }
      return ''
    }
    case 'share': {
      return meta.token ? `分享 token: ${String(meta.token).slice(0, 12)}...` : ''
    }
    case 'comment': {
      return meta.content_preview ? `「${meta.content_preview}」` : ''
    }
    case 'version_restore': {
      return meta.version_id != null ? `还原到版本 #${meta.version_id}` : ''
    }
    default:
      return ''
  }
}

// === 时间格式化 ===
function formatTime(iso) {
  if (!iso) return ''
  const d = new Date(iso)
  const now = new Date()
  const diffMs = now - d
  const diffMin = Math.floor(diffMs / 60000)
  if (diffMin < 1) return '刚刚'
  if (diffMin < 60) return `${diffMin} 分钟前`
  const diffHr = Math.floor(diffMin / 60)
  if (diffHr < 24) return `${diffHr} 小时前`
  const diffDay = Math.floor(diffHr / 24)
  if (diffDay < 7) return `${diffDay} 天前`
  return d.toLocaleDateString('zh-CN', { year: 'numeric', month: '2-digit', day: '2-digit' })
}

// === 取数 ===
async function fetchPage({ reset = false } = {}) {
  loading.value = true
  try {
    const params = {
      scope: scope.value,
      limit: PAGE_SIZE,
    }
    if (!reset && cursor.value != null) {
      params.before_id = cursor.value
    }
    const resp = await axios.get(`${API_BASE}/activities`, {
      params,
      headers: { Authorization: `Bearer ${getAuthToken()}` },
    })
    const newItems = resp.data?.items || []
    hasMore.value = !!resp.data?.has_more
    if (reset) {
      items.value = newItems
    } else {
      items.value = [...items.value, ...newItems]
    }
    if (newItems.length > 0) {
      cursor.value = newItems[newItems.length - 1].id
    } else {
      cursor.value = null
    }
  } catch (e) {
    console.error('[Activity] fetch failed:', e)
  } finally {
    loading.value = false
  }
}

async function reload() {
  cursor.value = null
  hasMore.value = false
  await fetchPage({ reset: true })
}

async function loadMore() {
  await fetchPage({ reset: false })
}

onMounted(() => {
  reload()
})

// 暴露给外部 (父组件 reload 时用)
defineExpose({ reload })
</script>

<style scoped>
.activity-feed-panel {
  padding: 0;
}

.activity-toolbar {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 0 0 16px;
  border-bottom: 1px solid var(--color-border-light, #ebeef5);
  margin-bottom: 12px;
}

.activity-toolbar-title {
  font-size: 14px;
  font-weight: 600;
  color: var(--color-text-primary, #303133);
}

.activity-toolbar-spacer {
  flex: 1;
}

.activity-loading,
.activity-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 48px 20px;
  color: var(--color-text-placeholder, #909399);
}

.activity-empty-icon {
  font-size: 48px;
  margin: 0 0 12px;
}

.activity-empty-text {
  font-size: 16px;
  font-weight: 500;
  margin: 0 0 4px;
  color: var(--color-text-secondary, #606266);
}

.activity-empty-hint {
  font-size: 13px;
  margin: 0;
  color: var(--color-text-placeholder, #909399);
}

.activity-list {
  list-style: none;
  padding: 0;
  margin: 0;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.activity-item {
  display: flex;
  gap: 12px;
  padding: 12px 16px;
  border-radius: var(--radius-md, 8px);
  background: var(--color-bg-card, #fff);
  border: 1px solid var(--color-border-light, #ebeef5);
  transition: background 0.2s;
}

.activity-item:hover {
  background: var(--color-bg-page, #fafbfc);
}

.activity-icon {
  flex-shrink: 0;
  width: 36px;
  height: 36px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 50%;
  background: var(--color-bg-page, #fafbfc);
}

.activity-body {
  flex: 1;
  min-width: 0;
}

.activity-line {
  font-size: 14px;
  line-height: 1.5;
  color: var(--color-text-primary, #303133);
}

.activity-actor {
  font-weight: 600;
  color: var(--color-text-primary, #303133);
  margin-right: 4px;
}

.activity-action-label {
  color: var(--color-text-secondary, #606266);
  margin-right: 4px;
}

.activity-target {
  font-weight: 500;
  color: var(--color-text-primary, #303133);
}

.activity-target-muted {
  color: var(--color-text-placeholder, #909399);
  font-size: 12px;
  margin-left: 4px;
}

.activity-summary {
  margin-top: 4px;
  font-size: 12px;
  color: var(--color-text-secondary, #606266);
  font-style: italic;
}

.activity-meta {
  margin-top: 4px;
  font-size: 12px;
  color: var(--color-text-placeholder, #909399);
  display: flex;
  gap: 6px;
}

.activity-meta-sep {
  color: var(--color-text-placeholder, #c0c4cc);
}

.activity-target-type {
  text-transform: lowercase;
}

.activity-load-more {
  display: flex;
  justify-content: center;
  padding: 16px 0;
}

.activity-load-more-end {
  text-align: center;
  font-size: 12px;
  color: var(--color-text-placeholder, #c0c4cc);
  padding: 16px 0;
}

.is-loading {
  animation: rotating 2s linear infinite;
}

@keyframes rotating {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}
</style>

<!--
  v60-v67 教训: dark mode 跨组件覆盖必须放非 scoped <style> 块
  本组件 scoped 已用 var(--color-*) token, dark mode 自动跟随, 暂不需 dark 块
  PR6 统一审计时再加 dark 块
-->