<!--
  NotificationBell.vue — v2 PR6/7/8 顶栏铃铛 (卡片化)

  v2 PR6-P8 卡片化重设计:
  - 每条通知是独立卡片 (hover 浮起阴影, 边界明确)
  - 顶部 title (粗黑, 1 行省略号)
  - 中部 body (灰色 12px, 最多 2 行省略号)
  - 底部元数据条: file_type icon + 时间 + 操作按钮 (标记已读 / 跳详情)
  - 未读左色条 + 浅色背景 (识别度强)

  Dark mode: 非 scoped 块 (v60-v67 教训)
-->
<template>
  <el-popover
    placement="bottom-end"
    :width="420"
    trigger="click"
    v-model:visible="popoverVisible"
    popper-class="notification-bell-popover"
  >
    <template #reference>
      <button
        class="notification-bell-btn"
        :aria-label="`通知 ${unreadCount > 0 ? unreadCount + ' 条未读' : ''}`"
        title="通知"
      >
        <el-icon><Bell /></el-icon>
        <span
          v-if="unreadCount > 0"
          class="notification-bell-badge"
          :class="{ 'is-many': unreadCount >= 10 }"
        >
          {{ unreadCount > 99 ? '99+' : unreadCount }}
        </span>
      </button>
    </template>

    <div class="notification-bell-panel">
      <div class="notification-bell-header">
        <h3>通知</h3>
        <div class="notification-bell-actions">
          <el-button
            v-if="unreadCount > 0"
            link
            type="primary"
            size="small"
            @click="onMarkAllRead"
          >
            全部已读
          </el-button>
          <el-button link size="small" @click="onRefresh">刷新</el-button>
        </div>
      </div>

      <div v-if="loadingNotifications" class="notification-bell-loading">
        加载中...
      </div>

      <div
        v-else-if="notifications.length === 0"
        class="notification-bell-empty"
      >
        暂无通知
      </div>

      <div v-else class="notification-bell-list">
        <!-- v2 PR6-P8: 卡片化 (之前是 <ul> + <li>, 改为 <article> 卡片) -->
        <article
          v-for="n in notifications.slice(0, 10)"
          :key="n.id"
          class="notif-card"
          :class="{ 'is-unread': !n.is_read }"
          @click="onItemClick(n)"
        >
          <!-- 左侧: file_type icon (颜色按 type) -->
          <div class="notif-icon" :class="`is-type-${n.file_type || 'other'}`">
            <el-icon><component :is="fileTypeIcon(n.file_type)" /></el-icon>
          </div>

          <!-- 中间: 文字内容 -->
          <div class="notif-body">
            <!-- title 行: 粗黑 + dedup 徽章 (PR6-P7) -->
            <div class="notif-title-row">
              <strong class="notif-title">{{ n.title || buildFallbackTitle(n) }}</strong>
              <span
                v-if="n.repeated_count > 1"
                class="notif-merge-badge"
                :title="`5 秒内有 ${n.repeated_count} 条同类通知已合并`"
              >
                x{{ n.repeated_count }}
              </span>
            </div>
            <!-- body 行: 灰色 2 行 -->
            <div v-if="n.body" class="notif-body-text">{{ n.body }}</div>
            <!-- 元数据行: 时间 + 文件类型 chip + 未读点 -->
            <div class="notif-meta">
              <span class="notif-meta-time">{{ formatTime(n.created_at) }}</span>
              <span v-if="n.file_type" class="notif-meta-type">{{ fileTypeLabel(n.file_type) }}</span>
              <span v-if="!n.is_read" class="notif-meta-dot" title="未读"></span>
            </div>
          </div>

          <!-- 右侧: 跳转 icon (hover 显示) -->
          <el-icon class="notif-action"><ArrowRight /></el-icon>
        </article>
      </div>

      <div v-if="notifications.length > 10" class="notification-bell-footer">
        <el-button link size="small" @click="onViewAll">
          查看全部 ({{ notifications.length }})
        </el-button>
      </div>
    </div>
  </el-popover>
</template>

<script setup>
import { ref, computed, onMounted, onBeforeUnmount } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import {
  Bell, ChatDotRound, ArrowRight,
  Document, Picture, VideoPlay, Headset, Tickets, FolderOpened, EditPen,
} from '@element-plus/icons-vue'
import { useNotificationsStore } from '@/composables/useNotifications'

const router = useRouter()
const store = useNotificationsStore()
const popoverVisible = ref(false)

const notifications = computed(() => store.notifications)
const unreadCount = computed(() => store.unreadCount)
const loadingNotifications = computed(() => store.loadingNotifications)

// v2 PR6-P8: file_type → EP icon 映射
function fileTypeIcon(ft) {
  switch (ft) {
    case 'pdf': return Document
    case 'doc': return EditPen
    case 'excel': return Tickets
    case 'ppt': return VideoPlay
    case 'image': return Picture
    case 'audio': return Headset
    case 'video': return VideoPlay
    case 'text': return Document
    default: return FolderOpened
  }
}

// v2 PR6-P8: file_type → 中文 label
function fileTypeLabel(ft) {
  const map = {
    pdf: 'PDF', doc: 'Word', excel: 'Excel', ppt: 'PPT',
    image: '图片', audio: '音频', video: '视频',
    text: '文本', archive: '压缩包', other: '文件',
  }
  return map[ft] || '文件'
}

// v2 PR6-P8: 老数据 fallback (历史数据 title=null 时, 用 actor + file 拼)
// 注意: 这是前端兜底, 新数据 title 必填, 走不到这条路径
function buildFallbackTitle(n) {
  const actor = n.mentioned_by_name || '有人'
  const fname = n.file_name || `文件 #${n.file_id}`
  if (n.context && n.context.startsWith('reply:')) return `${actor} 回复了你的评论`
  return `${actor} 在 ${fname} 提到了你`
}

function formatTime(iso) {
  if (!iso) return ''
  const t = new Date(iso).getTime()
  const now = Date.now()
  const sec = Math.floor((now - t) / 1000)
  if (sec < 60) return '刚刚'
  if (sec < 3600) return `${Math.floor(sec / 60)} 分钟前`
  if (sec < 86400) return `${Math.floor(sec / 3600)} 小时前`
  return `${Math.floor(sec / 86400)} 天前`
}

async function onMarkAllRead() {
  await store.markAllRead()
  ElMessage.success('已全部标记为已读')
}

async function onRefresh() {
  await store.fetchNotifications(false, 50)
}

function onItemClick(n) {
  if (!n.is_read) {
    store.markRead(n.id)
  }
  popoverVisible.value = false
  router.push(`/drive/file/${n.file_id}`)
}

onMounted(async () => {
  store.startWs()
  store.startPolling(30000)
  await store.fetchNotifications(false, 50)
})

onBeforeUnmount(() => {
  // 不 disconnect (其他组件可能还用)
})
</script>

<style>
/* ========== 顶栏铃铛按钮 (与 PR6-P7 一致) ========== */
.notification-bell-btn {
  position: relative;
  background: transparent;
  border: none;
  cursor: pointer;
  padding: 8px;
  border-radius: 6px;
  color: var(--color-text-secondary, #606266);
  transition: background 0.2s, color 0.2s;
  display: inline-flex;
  align-items: center;
  justify-content: center;
}
.notification-bell-btn:hover {
  background: var(--color-bg-hover, rgba(0, 0, 0, 0.04));
  color: var(--color-primary, #FF7A5C);
}
.notification-bell-btn .el-icon {
  font-size: 20px;
}

.notification-bell-badge {
  position: absolute;
  top: 2px;
  right: 2px;
  min-width: 16px;
  height: 16px;
  padding: 0 4px;
  background: var(--color-danger);
  color: var(--el-color-white);
  border-radius: 8px;
  font-size: 10px;
  font-weight: 600;
  line-height: 16px;
  text-align: center;
}
.notification-bell-badge.is-many {
  font-size: 9px;
  padding: 0 5px;
}

/* ========== Popover 面板 ========== */
.notification-bell-popover {
  padding: 0 !important;
}

.notification-bell-panel {
  max-height: 540px;
  display: flex;
  flex-direction: column;
}

.notification-bell-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 16px;
  border-bottom: 1px solid var(--color-border-light, #ebeef5);
}
.notification-bell-header h3 {
  margin: 0;
  font-size: 14px;
  font-weight: 600;
  color: var(--color-text-primary, #303133);
}
.notification-bell-actions {
  display: flex;
  gap: 4px;
}

.notification-bell-loading,
.notification-bell-empty {
  padding: 32px;
  text-align: center;
  color: var(--color-text-secondary, #909399);
  font-size: 13px;
}

/* ========== v2 PR6-P8: 卡片化列表 ========== */
.notification-bell-list {
  display: flex;
  flex-direction: column;
  gap: 6px;  /* 卡片间距 */
  padding: 8px;
  overflow-y: auto;
  max-height: 440px;
}

.notif-card {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  padding: 10px 12px;
  cursor: pointer;
  border-radius: 8px;
  background: var(--color-bg-card, #FFFFFF);
  border: 1px solid var(--color-border-light, #ebeef5);
  transition: background 0.15s, border-color 0.15s, transform 0.15s, box-shadow 0.15s;
  position: relative;
  /* 未读卡片左边色条 */
  border-left: 3px solid transparent;
}
.notif-card:hover {
  background: var(--color-bg-hover, rgba(0, 0, 0, 0.02));
  border-color: var(--color-primary, #FF7A5C);
  transform: translateX(2px);
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.06);
}
.notif-card.is-unread {
  background: var(--color-primary-bg, rgba(255, 122, 92, 0.04));
  border-left-color: var(--color-primary, #FF7A5C);
}

/* file_type 图标 (左侧) */
.notif-icon {
  flex-shrink: 0;
  width: 36px;
  height: 36px;
  border-radius: 8px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--color-primary-bg, rgba(255, 122, 92, 0.12));
  color: var(--color-primary, #FF7A5C);
  font-size: 18px;
}
.notif-icon.is-type-pdf     { background: rgba(220, 53, 69, 0.12);  color: #DC3545; }
.notif-icon.is-type-doc     { background: rgba(13, 110, 253, 0.12); color: #0D6EFD; }
.notif-icon.is-type-excel   { background: rgba(25, 135, 84, 0.12);  color: #198754; }
.notif-icon.is-type-ppt     { background: rgba(255, 87, 34, 0.12);  color: #FF5722; }
.notif-icon.is-type-image   { background: rgba(156, 39, 176, 0.12); color: #9C27B0; }
.notif-icon.is-type-audio   { background: rgba(0, 188, 212, 0.12);  color: #00BCD4; }
.notif-icon.is-type-video   { background: rgba(233, 30, 99, 0.12);  color: #E91E63; }
.notif-icon.is-type-text    { background: rgba(96, 125, 139, 0.12); color: #607D8B; }
.notif-icon.is-type-archive { background: rgba(121, 85, 72, 0.12);  color: #795548; }

/* 中间内容区 */
.notif-body {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.notif-title-row {
  display: flex;
  align-items: center;
  gap: 6px;
}
.notif-title {
  font-size: 14px;
  font-weight: 600;
  line-height: 1.4;
  color: var(--color-text-primary, #303133);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  flex: 1;
  min-width: 0;
}

/* v2 PR6-P7: dedup 合并徽章 (保留) */
.notif-merge-badge {
  flex-shrink: 0;
  display: inline-block;
  padding: 0 6px;
  background: var(--color-primary, #FF7A5C);
  color: var(--el-color-white, #FFFFFF);
  font-size: 10px;
  font-weight: 600;
  border-radius: 8px;
  line-height: 16px;
  vertical-align: 1px;
}

/* v2 PR6-P8: body 文本 (灰色 2 行) */
.notif-body-text {
  font-size: 12px;
  line-height: 1.5;
  color: var(--color-text-secondary, #606266);
  overflow: hidden;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  word-break: break-word;
}

/* v2 PR6-P8: 元数据条 (时间 + 类型 + 未读点) */
.notif-meta {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 11px;
  color: var(--color-text-secondary, #909399);
  margin-top: 2px;
}
.notif-meta-time { white-space: nowrap; }
.notif-meta-type {
  padding: 0 5px;
  background: var(--color-bg-hover, rgba(0, 0, 0, 0.04));
  border-radius: 4px;
  font-size: 10px;
}
.notif-meta-dot {
  display: inline-block;
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--color-primary, #FF7A5C);
  margin-left: auto;
}

/* 右侧跳转箭头 (hover 显示) */
.notif-action {
  flex-shrink: 0;
  color: var(--color-text-secondary, #909399);
  font-size: 14px;
  opacity: 0;
  transition: opacity 0.15s, transform 0.15s;
  align-self: center;
}
.notif-card:hover .notif-action {
  opacity: 1;
  transform: translateX(2px);
  color: var(--color-primary, #FF7A5C);
}

/* ========== Footer ========== */
.notification-bell-footer {
  padding: 8px 16px;
  text-align: center;
  border-top: 1px solid var(--color-border-light, #ebeef5);
}

/* ========== Dark mode 非 scoped 块 (v60-v67 教训) ========== */
[data-theme="dark"] .notification-bell-btn {
  color: var(--color-text-secondary);
}
[data-theme="dark"] .notif-card {
  background: var(--color-bg-card-dark, rgba(255, 255, 255, 0.04));
  border-color: rgba(255, 255, 255, 0.08);
}
[data-theme="dark"] .notif-card:hover {
  background: rgba(255, 122, 92, 0.08);
  border-color: var(--color-primary, #FF7A5C);
}
[data-theme="dark"] .notif-card.is-unread {
  background: rgba(255, 122, 92, 0.08);
}
[data-theme="dark"] .notification-bell-header,
[data-theme="dark"] .notification-bell-footer {
  border-color: rgba(255, 255, 255, 0.08);
}
[data-theme="dark"] .notif-meta-type {
  background: rgba(255, 255, 255, 0.06);
}
</style>