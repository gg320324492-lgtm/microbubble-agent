<!--
  ActivityFeedView.vue — v2 PR6 活动动态流视图

  路由: /drive/activity
  功能:
  - 时间线 (今天 / 昨天 / 本周 / 更早)
  - scope 切换: team / me
  - load more (cursor 分页)

  Dark mode: 非 scoped 块 (v60-v67 教训)
-->
<template>
  <div class="page-container activity-feed-view">
    <div class="page-header">
      <h2>活动动态</h2>
      <p class="page-subtitle">查看团队成员最近的文件操作</p>
    </div>

    <div class="activity-toolbar">
      <el-radio-group v-model="scope" @change="onScopeChange">
        <el-radio-button label="team">团队</el-radio-button>
        <el-radio-button label="me">我的</el-radio-button>
      </el-radio-group>
      <el-button link @click="onRefresh">刷新</el-button>
    </div>

    <div v-if="loadingActivities && activities.length === 0" class="activity-loading">
      加载中...
    </div>

    <div v-else-if="activities.length === 0" class="activity-empty">
      暂无活动
    </div>

    <div v-else class="activity-timeline">
      <template v-for="group in groupedActivities" :key="group.label">
        <div class="activity-group-label">{{ group.label }}</div>
        <ul class="activity-list">
          <li v-for="evt in group.items" :key="evt.id" class="activity-item">
            <div class="activity-avatar" :class="`is-action-${evt.action}`">
              <el-icon><component :is="actionIcon(evt.action)" /></el-icon>
            </div>
            <div class="activity-content">
              <div class="activity-line">
                <strong v-if="evt.actor_name">{{ evt.actor_name }}</strong>
                <strong v-else>系统</strong>
                {{ actionText(evt.action) }}
                <em @click="onTargetClick(evt)">{{ evt.target_name || `#${evt.target_id}` }}</em>
              </div>
              <div class="activity-meta">
                <span class="activity-time">{{ formatTime(evt.created_at) }}</span>
                <span class="activity-action-tag">{{ actionText(evt.action) }}</span>
              </div>
            </div>
          </li>
        </ul>
      </template>
    </div>

    <div v-if="hasMore" class="activity-load-more">
      <el-button @click="onLoadMore" :loading="loadingActivities">
        加载更多
      </el-button>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import {
  Upload, Edit, Share, Delete, Refresh, Star,
  ChatDotRound, FolderOpened, Comment,
} from '@element-plus/icons-vue'
import { useNotificationsStore } from '@/composables/useNotifications'

const router = useRouter()
const store = useNotificationsStore()

const scope = ref('team')
const activities = computed(() => store.activities)
const loadingActivities = computed(() => store.loadingActivities)
const hasMore = ref(true)

async function onScopeChange() {
  hasMore.value = true
  await store.fetchActivities(scope.value, null, 50)
}

async function onRefresh() {
  hasMore.value = true
  await store.fetchActivities(scope.value, null, 50)
}

async function onLoadMore() {
  if (activities.value.length === 0) return
  const lastId = activities.value[activities.value.length - 1].id
  const resp = await store.fetchActivities(scope.value, lastId, 50)
  hasMore.value = resp.has_more
}

function actionIcon(action) {
  const map = {
    upload: Upload,
    rename: Edit,
    move: FolderOpened,
    delete: Delete,
    restore: Refresh,
    share: Share,
    version_restore: Refresh,
    comment: ChatDotRound,
    mention: ChatDotRound,
    star: Star,
    unstar: Star,
  }
  return map[action] || Comment
}

function actionText(action) {
  const map = {
    upload: '上传了',
    rename: '重命名了',
    move: '移动了',
    delete: '删除了',
    restore: '恢复了',
    share: '分享了',
    version_restore: '恢复了历史版本',
    comment: '评论了',
    mention: '提到了',
    star: '收藏了',
    unstar: '取消收藏了',
  }
  return map[action] || action
}

function onTargetClick(evt) {
  if (evt.target_type === 'file' && evt.target_id) {
    router.push(`/drive/file/${evt.target_id}`)
  } else if (evt.target_type === 'folder' && evt.target_id) {
    router.push(`/drive?folder=${evt.target_id}`)
  }
}

function formatTime(iso) {
  if (!iso) return ''
  return new Date(iso).toLocaleString('zh-CN', { hour12: false })
}

// 分组: 今天 / 昨天 / 本周 / 更早
const groupedActivities = computed(() => {
  const now = new Date()
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate())
  const yesterday = today.getTime() - 86400000
  const weekAgo = today.getTime() - 7 * 86400000

  const groups = { '今天': [], '昨天': [], '本周': [], '更早': [] }
  for (const evt of activities.value) {
    const t = new Date(evt.created_at).getTime()
    if (t >= today.getTime()) groups['今天'].push(evt)
    else if (t >= yesterday) groups['昨天'].push(evt)
    else if (t >= weekAgo) groups['本周'].push(evt)
    else groups['更早'].push(evt)
  }
  return Object.entries(groups)
    .filter(([_, items]) => items.length > 0)
    .map(([label, items]) => ({ label, items }))
})

onMounted(async () => {
  await store.fetchActivities(scope.value, null, 50)
})
</script>

<style scoped>
.page-container.activity-feed-view {
  padding: 24px;
  max-width: 900px;
  margin: 0 auto;
}

.page-header {
  margin-bottom: 24px;
}
.page-header h2 {
  margin: 0 0 4px;
  font-size: 24px;
  color: var(--color-text-primary);
}
.page-subtitle {
  margin: 0;
  color: var(--color-text-secondary);
  font-size: 13px;
}

.activity-toolbar {
  display: flex;
  align-items: center;
  gap: 16px;
  margin-bottom: 16px;
}

.activity-loading,
.activity-empty {
  padding: 64px;
  text-align: center;
  color: var(--color-text-secondary);
  font-size: 14px;
}

.activity-timeline {
  background: var(--color-bg-card);
  border-radius: 8px;
  padding: 16px;
  border: 1px solid var(--color-border-light);
}

.activity-group-label {
  font-size: 13px;
  font-weight: 600;
  color: var(--color-text-secondary);
  margin: 12px 0 8px;
  padding: 0 8px;
}
.activity-group-label:first-child {
  margin-top: 0;
}

.activity-list {
  list-style: none;
  margin: 0;
  padding: 0;
}

.activity-item {
  display: flex;
  align-items: flex-start;
  gap: 12px;
  padding: 12px 8px;
  border-bottom: 1px solid var(--color-border-light);
}
.activity-item:last-child {
  border-bottom: none;
}

.activity-avatar {
  flex-shrink: 0;
  width: 36px;
  height: 36px;
  border-radius: 50%;
  background: var(--color-primary-bg);
  color: var(--color-primary);
  display: flex;
  align-items: center;
  justify-content: center;
}
.activity-avatar.is-action-delete {
  background: rgba(245, 108, 108, 0.12);
  color: var(--color-danger);
}
.activity-avatar.is-action-share {
  background: rgba(103, 194, 58, 0.12);
  color: var(--color-success);
}
.activity-avatar.is-action-upload {
  background: rgba(64, 158, 255, 0.12);
  color: var(--color-info);
}
.activity-avatar.is-action-comment,
.activity-avatar.is-action-mention {
  background: rgba(230, 162, 60, 0.12);
  color: var(--color-warning);
}
.activity-avatar .el-icon {
  font-size: 18px;
}

.activity-content {
  flex: 1;
  min-width: 0;
}

.activity-line {
  font-size: 14px;
  color: var(--color-text-primary);
  line-height: 1.5;
}
.activity-line em {
  font-style: normal;
  font-weight: 600;
  color: var(--color-primary);
  cursor: pointer;
  text-decoration: underline;
  text-decoration-style: dotted;
}
.activity-line em:hover {
  text-decoration-style: solid;
}

.activity-meta {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-top: 4px;
  font-size: 12px;
  color: var(--color-text-secondary);
}

.activity-action-tag {
  padding: 2px 8px;
  background: var(--color-bg-page, #f5f7fa);
  border-radius: 4px;
  font-size: 11px;
}

.activity-load-more {
  text-align: center;
  margin-top: 16px;
}

/* Dark mode 非 scoped 块 (v60-v67 教训) */
[data-theme="dark"] .activity-timeline {
  background: var(--color-bg-card);
  border-color: var(--color-border-dark, rgba(255, 255, 255, 0.08));
}
[data-theme="dark"] .activity-item {
  border-bottom-color: var(--color-border-dark, rgba(255, 255, 255, 0.08));
}
[data-theme="dark"] .activity-action-tag {
  background: rgba(255, 255, 255, 0.06);
}
</style>