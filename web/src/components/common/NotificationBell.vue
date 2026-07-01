<!--
  NotificationBell.vue — v2 PR6 顶栏铃铛

  功能:
  - 红点 (未读数 1-99)
  - 下拉列表 (最近 10 条 mention)
  - "全部已读" 按钮
  - 跳详情: 点击行 → /drive/file/{file_id}
  - WS 自动推送 (via useNotifications store)
  - 30s polling 兜底

  Dark mode: 非 scoped 块 (v60-v67 教训)
-->
<template>
  <el-popover
    placement="bottom-end"
    :width="380"
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
          <el-button link size="small" @click="onRefresh">
            刷新
          </el-button>
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

      <ul v-else class="notification-bell-list">
        <li
          v-for="n in notifications.slice(0, 10)"
          :key="n.id"
          :class="{ 'is-unread': !n.is_read }"
          @click="onItemClick(n)"
        >
          <div class="notif-icon">
            <el-icon><ChatDotRound /></el-icon>
          </div>
          <div class="notif-content">
            <div class="notif-title">
              <strong v-if="n.mentioned_by_name">
                {{ n.mentioned_by_name }}
              </strong>
              <strong v-else>有人</strong>
              在
              <em>{{ n.file_name || `文件 #${n.file_id}` }}</em>
              @ 了你
            </div>
            <div class="notif-time">{{ formatTime(n.created_at) }}</div>
          </div>
          <div v-if="!n.is_read" class="notif-dot" />
        </li>
      </ul>

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
import { Bell, ChatDotRound } from '@element-plus/icons-vue'
import { useNotificationsStore } from '@/composables/useNotifications'

const router = useRouter()
const store = useNotificationsStore()
const popoverVisible = ref(false)

const notifications = computed(() => store.notifications)
const unreadCount = computed(() => store.unreadCount)
const loadingNotifications = computed(() => store.loadingNotifications)

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
  // 标记已读 (best-effort)
  if (!n.is_read) {
    store.markRead(n.id)
  }
  // 关闭 popover + 跳详情
  popoverVisible.value = false
  router.push(`/drive/file/${n.file_id}`)
}

function onViewAll() {
  popoverVisible.value = false
  router.push('/drive/activity')
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
/* 顶栏铃铛按钮 */
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

/* Popover 面板 */
.notification-bell-popover {
  padding: 0 !important;
}

.notification-bell-panel {
  max-height: 480px;
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

.notification-bell-list {
  list-style: none;
  margin: 0;
  padding: 0;
  overflow-y: auto;
  max-height: 320px;
}
.notification-bell-list li {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  padding: 10px 16px;
  cursor: pointer;
  border-bottom: 1px solid var(--color-border-light, #f5f7fa);
  transition: background 0.15s;
  position: relative;
}
.notification-bell-list li:hover {
  background: var(--color-bg-hover, rgba(0, 0, 0, 0.04));
}
.notification-bell-list li.is-unread {
  background: var(--color-primary-bg, rgba(255, 122, 92, 0.06));
}

.notif-icon {
  flex-shrink: 0;
  width: 32px;
  height: 32px;
  border-radius: 50%;
  background: var(--color-primary-bg, rgba(255, 122, 92, 0.12));
  color: var(--color-primary, #FF7A5C);
  display: flex;
  align-items: center;
  justify-content: center;
}
.notif-icon .el-icon {
  font-size: 16px;
}

.notif-content {
  flex: 1;
  min-width: 0;
}
.notif-title {
  font-size: 13px;
  line-height: 1.4;
  color: var(--color-text-primary, #303133);
  overflow: hidden;
  text-overflow: ellipsis;
}
.notif-title em {
  font-style: normal;
  font-weight: 600;
  color: var(--color-primary, #FF7A5C);
}
.notif-time {
  font-size: 11px;
  color: var(--color-text-secondary, #909399);
  margin-top: 4px;
}

.notif-dot {
  position: absolute;
  top: 16px;
  right: 12px;
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: var(--color-primary, #FF7A5C);
}

.notification-bell-footer {
  padding: 8px 16px;
  text-align: center;
  border-top: 1px solid var(--color-border-light, #ebeef5);
}

/* Dark mode 非 scoped 块 (v60-v67 教训) */
[data-theme="dark"] .notification-bell-btn {
  color: var(--color-text-secondary);
}
[data-theme="dark"] .notification-bell-list li {
  border-bottom-color: var(--color-border-dark, rgba(255, 255, 255, 0.08));
}
[data-theme="dark"] .notification-bell-list li.is-unread {
  background: rgba(255, 122, 92, 0.1);
}
[data-theme="dark"] .notification-bell-header {
  border-bottom-color: var(--color-border-dark, rgba(255, 255, 255, 0.08));
}
[data-theme="dark"] .notification-bell-footer {
  border-top-color: var(--color-border-dark, rgba(255, 255, 255, 0.08));
}
</style>