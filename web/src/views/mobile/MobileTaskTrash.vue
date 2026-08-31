<template>
  <div class="mobile-task-trash mg-page">
    <PageHeader title="回收站" show-back @back="$router.back()">
      <template #right>
        <button
          v-if="!editMode"
          type="button"
          class="header-action"
          aria-label="编辑"
          title="编辑"
          @click="editMode = true"
        >✏️</button>
        <button
          v-else
          type="button"
          class="header-action"
          aria-label="取消"
          title="取消"
          @click="exitEditMode"
        >✕</button>
      </template>
    </PageHeader>

    <main
      class="trash-main"
      :style="{ paddingBottom: 'calc(var(--tabbar-height, 56px) + var(--sab, 0px))' }"
    >
      <!-- 顶部提示 -->
      <div class="trash-hint mg-glass mg-rise">
        <span class="hint-icon">ℹ️</span>
        <span>回收站任务将在 3 天后自动永久删除</span>
      </div>

      <!-- CardList 列表（支持多选） -->
      <CardList
        class="trash-list mg-rise mg-stagger-1"
        :items="trashTasks"
        :selectable="editMode"
        v-model:selected="selectedRows"
        :field-config="fieldConfig"
        :loading="loading"
        empty-icon="🗑"
        empty-title="回收站是空的"
        empty-hint="删除的任务会在这里保留 3 天"
        @item-click="onItemClick"
      >
        <template #batch-actions="{ selected, clear }">
          <button
            type="button"
            class="batch-btn danger"
            @click="batchPermanentDelete"
          >
            🗑 永久删除 ({{ selected.length }})
          </button>
          <button
            type="button"
            class="batch-btn"
            @click="clear"
          >取消</button>
        </template>
        <template #item-actions="{ item }">
          <div class="item-actions">
            <template v-if="canRestore(item)">
              <button type="button" class="item-btn restore" @click.stop="restoreTask(item.id)">
                ↩️ 恢复
              </button>
              <button type="button" class="item-btn danger" @click.stop="permanentDelete(item.id)">
                🗑 永久删除
              </button>
            </template>
            <span v-else class="no-permission">无权限</span>
          </div>
        </template>
      </CardList>

      <!-- 分页 -->
      <div v-if="trashTotal > trashPageSize" class="pagination">
        <span class="page-info">第 {{ trashPage }} / {{ totalPages }} 页</span>
        <div class="page-actions">
          <button
            type="button"
            :disabled="trashPage <= 1"
            @click="onPageChange(trashPage - 1)"
          >上一页</button>
          <button
            type="button"
            :disabled="trashPage >= totalPages"
            @click="onPageChange(trashPage + 1)"
          >下一页</button>
        </div>
      </div>
    </main>
  </div>
</template>

<script setup>
/**
 * MobileTaskTrash.vue — 移动端任务回收站
 *
 * PR #8a: 用 CardList 多选模式 + 操作按钮 slot
 * - 多选模式（editMode toggle）
 * - 自动删除倒计时（颜色分级）
 * - 简易分页
 */

import { ref, computed, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import axios from 'axios'
import dayjs from 'dayjs'
import { useUserStore } from '@/stores/user'
import { useMemberStore } from '@/stores/member'
import PageHeader from '@/components/mobile/PageHeader.vue'
import CardList from '@/components/mobile/CardList.vue'

const props = defineProps({
  /** 当前用户 ID（用于权限判断） */
  currentUserId: { type: [Number, String], default: null },
  /** 是否管理员 */
  isAdmin: { type: Boolean, default: false },
})

// 注：保留 emit 以兼容未来嵌入式调用（作为独立路由时不依赖父级监听）
const emit = defineEmits(['restore', 'permanent-delete', 'batch-permanent-delete'])

const userStore = useUserStore()
const memberStore = useMemberStore()

const trashTasks = ref([])
const trashTotal = ref(0)
const trashPage = ref(1)
const trashPageSize = ref(20)
const loading = ref(false)
const selectedRows = ref([])
const editMode = ref(false)

const totalPages = computed(() => Math.max(1, Math.ceil(trashTotal.value / trashPageSize.value)))

const currentUserId = computed(() => props.currentUserId || userStore.userInfo?.id)
const isAdmin = computed(() => props.isAdmin || userStore.userInfo?.role === 'admin')

// CardList 配置
const fieldConfig = computed(() => ({
  title: (row) => row.title,
  subtitle: (row) => `${memberStore.getMemberName(row.assignee_id) || '未分配'}`,
  badge: (row) => ({
    label: getAutoDeleteText(row.auto_delete_at) || '待删除',
    type: row.auto_delete_at ? getAutoDeleteType(row.auto_delete_at) : 'info',
  }),
  fields: (row) => [
    { key: 'deleted', label: '删除时间', value: row.deleted_at ? dayjs(row.deleted_at).format('MM-DD HH:mm') : '—' },
    { key: 'auto', label: '自动删除', value: row.auto_delete_at ? `${dayjs(row.auto_delete_at).format('MM-DD HH:mm')} 删除` : '—' },
  ],
}))

// 自动删除倒计时
function getAutoDeleteHours(autoDeleteAt) {
  if (!autoDeleteAt) return Infinity
  return dayjs(autoDeleteAt).diff(dayjs(), 'hour', true)
}

function getAutoDeleteText(autoDeleteAt) {
  if (!autoDeleteAt) return ''
  const diffMin = dayjs(autoDeleteAt).diff(dayjs(), 'minute')
  const diffHour = dayjs(autoDeleteAt).diff(dayjs(), 'hour')
  const diffDay = Math.floor(diffMin / (60 * 24))
  if (diffMin <= 0) return '即将删除'
  if (diffMin < 60) return `${diffMin} 分钟后`
  if (diffMin < 24 * 60) return `${diffHour} 小时后`
  return `${diffDay} 天后`
}

function getAutoDeleteType(autoDeleteAt) {
  const hours = getAutoDeleteHours(autoDeleteAt)
  if (hours <= 6) return 'danger'
  if (hours <= 24) return 'warning'
  return 'info'
}

function canRestore(item) {
  return isAdmin.value || item.created_by === currentUserId.value || item.assignee_id === currentUserId.value
}

// 加载
async function fetchTrash() {
  loading.value = true
  try {
    const res = await axios.get('/api/v1/tasks', {
      params: {
        page: trashPage.value,
        page_size: trashPageSize.value,
        include_deleted: true,
      },
    })
    trashTasks.value = res.data?.items || []
    trashTotal.value = res.data?.pagination?.total || res.data?.total || 0
  } catch (e) {
    console.error('[MobileTaskTrash] load failed:', e)
  } finally {
    loading.value = false
  }
}

function onPageChange(page) {
  trashPage.value = page
  fetchTrash()
}

function onItemClick() {
  // 移动端点击触发多选（CardList 内置行为）
}

function exitEditMode() {
  editMode.value = false
  selectedRows.value = []
}

function batchPermanentDelete() {
  const ids = selectedRows.value.map((r) => r.id)
  if (ids.length === 0) return
  if (!window.confirm(`确定要永久删除 ${ids.length} 个任务吗？此操作不可恢复！`)) return
  axios.post('/api/v1/tasks/batch-permanent-delete', { ids })
    .then(() => {
      ElMessage.success(`已永久删除 ${ids.length} 个任务`)
      emit('batch-permanent-delete', ids)
      exitEditMode()
      fetchTrash()
    })
    .catch((e) => {
      ElMessage.error('批量删除失败: ' + (e.response?.data?.detail || e.message))
    })
}

// 恢复单个任务（直接调 API + emit 兼容）
async function restoreTask(taskId) {
  try {
    await axios.post(`/api/v1/tasks/${taskId}/restore`)
    ElMessage.success('已恢复')
    emit('restore', taskId)
    fetchTrash()
  } catch (e) {
    ElMessage.error('恢复失败: ' + (e.response?.data?.detail || e.message))
  }
}

// 永久删除单个任务（直接调 API + emit 兼容）
async function permanentDelete(taskId) {
  if (!window.confirm('确定要永久删除该任务吗？此操作不可恢复！')) return
  try {
    await axios.delete(`/api/v1/tasks/${taskId}/permanent`)
    ElMessage.success('已永久删除')
    emit('permanent-delete', taskId)
    fetchTrash()
  } catch (e) {
    ElMessage.error('删除失败: ' + (e.response?.data?.detail || e.message))
  }
}

onMounted(() => {
  fetchTrash()
})
</script>

<style scoped>
/* 液态毛玻璃 (Liquid Glass) — 2026-08-31 升级
   背景/文字色由全局 .mg-page 提供, 本块不重复设根 background */
.mobile-task-trash {
  min-height: 100vh;
  display: flex;
  flex-direction: column;
}

.trash-main {
  flex: 1;
  padding: var(--mobile-padding-y, 12px) var(--mobile-padding-x, 16px);
}

/* PageHeader 玻璃化 */
:deep(.mobile-page-header) {
  background: var(--mg-glass-bg);
  -webkit-backdrop-filter: blur(24px);
  backdrop-filter: blur(24px);
  border-bottom: 1px solid var(--mg-glass-border);
}
:deep(.header-title) {
  color: var(--mg-text-strong);
}
:deep(.header-back) {
  color: var(--mg-text);
}
:deep(.header-back:active) {
  background: var(--mg-gradient-soft);
  color: var(--mg-primary);
}

/* 顶部提示 — mg-glass 卡 (模板已加), 文案色保持高可读 (v92 X-2 a11y 教训: 警示色文字对比度不足) */
.trash-hint {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 14px;
  border-radius: var(--mg-radius-md);
  box-shadow: var(--mg-shadow-sm);
  font-size: 12px;
  font-weight: 600;
  color: var(--mg-text);
  margin-bottom: 12px;
}
.hint-icon { flex-shrink: 0; }

.header-action {
  width: 44px;
  height: 44px;
  border-radius: 50%;
  background: transparent;
  border: none;
  font-size: 18px;
  color: var(--mg-text);
  cursor: pointer;
  -webkit-tap-highlight-color: transparent;
}
.header-action:active { background: var(--mg-gradient-soft); }

/* 任务行 = mg-glass 列表卡 (radius-md / padding 13px 14px / 行间距 10px) */
.trash-list :deep(.list-body) {
  gap: 10px;
}
.trash-list :deep(.list-item) {
  background: var(--mg-glass-bg-strong);
  border: 1.5px solid var(--mg-glass-border);
  border-radius: var(--mg-radius-md);
  padding: 13px 14px;
  box-shadow: var(--mg-shadow-sm);
  transition: transform 150ms ease;
}
.trash-list :deep(.list-item:active) { transform: scale(0.99); }
.trash-list :deep(.list-item.selected) {
  background: var(--mg-gradient-soft);
  border-color: var(--mg-primary);
}
.trash-list :deep(.list-item.selected .checkbox) {
  background: var(--mg-primary);
  border-color: var(--mg-primary);
}
.trash-list :deep(.check-mark) { color: var(--mg-on-primary); }
.trash-list :deep(.item-title) { color: var(--mg-text-strong); }
.trash-list :deep(.item-subtitle) { color: var(--mg-text-soft); }
.trash-list :deep(.field-key) { color: var(--mg-text-soft); }
.trash-list :deep(.field-value) { color: var(--mg-text); }
.trash-list :deep(.empty-title) { color: var(--mg-text-soft); }
.trash-list :deep(.empty-hint) { color: var(--mg-text-faint); }

/* 批量操作条 */
.trash-list :deep(.batch-bar) {
  background: var(--mg-glass-bg-strong);
  -webkit-backdrop-filter: blur(12px);
  backdrop-filter: blur(12px);
  border: 1.5px solid var(--mg-glass-border);
  border-radius: var(--mg-radius-md);
  box-shadow: var(--mg-shadow-sm);
  color: var(--mg-text);
  margin-bottom: 10px;
}

/* 倒计时/优先级芯片: danger/warning/info 语义 (CardList badge--* class) */
:deep(.badge-tag) {
  border-radius: var(--mg-radius-pill);
  padding: 3px 10px;
  font-weight: 600;
  background: var(--mg-info-soft);
  color: var(--mg-info);
}
:deep(.badge--danger) { background: var(--mg-danger-soft); color: var(--mg-danger); }
:deep(.badge--warning) { background: var(--mg-warning-soft); color: var(--mg-warning); }
:deep(.badge--info)    { background: var(--mg-info-soft);    color: var(--mg-info); }
:deep(.badge--success) { background: var(--mg-success-soft); color: var(--mg-success); }
:deep(.badge--primary) { background: var(--mg-gradient-soft); color: var(--mg-primary); }

/* CardList slot */
.item-actions {
  display: flex;
  gap: 8px;
  margin-top: 8px;
}
.item-btn {
  flex: 1;
  min-height: 44px;
  padding: 10px 6px;
  border-radius: 14px;
  border: 1.5px solid var(--mg-glass-border);
  font-size: 12px;
  font-weight: 600;
  cursor: pointer;
  background: var(--mg-glass-bg-strong);
  color: var(--mg-text);
  -webkit-tap-highlight-color: transparent;
  transition: transform 150ms ease, opacity 150ms ease;
}
.item-btn:active { transform: scale(0.97); opacity: 0.85; }
.item-btn.restore {
  background: var(--mg-success-soft);
  color: var(--mg-success);
  border-color: transparent;
}
.item-btn.danger {
  background: var(--mg-danger-soft);
  color: var(--mg-danger);
  border-color: transparent;
}
.no-permission {
  font-size: 11px;
  color: var(--mg-text-faint);
  padding: 6px;
}

/* Batch */
.batch-btn {
  flex: 1;
  min-height: 44px;
  padding: 10px 8px;
  border-radius: 14px;
  border: 1.5px solid var(--mg-glass-border);
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
  background: var(--mg-glass-bg-strong);
  color: var(--mg-text);
  -webkit-tap-highlight-color: transparent;
  transition: transform 150ms ease, opacity 150ms ease;
}
.batch-btn:active { transform: scale(0.97); opacity: 0.85; }
.batch-btn.danger {
  background: var(--mg-danger-soft);
  color: var(--mg-danger);
  border-color: transparent;
}

/* 分页 */
.pagination {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 16px;
  margin-top: 12px;
  background: var(--mg-glass-bg);
  border: 1.5px solid var(--mg-glass-border);
  -webkit-backdrop-filter: blur(var(--mg-glass-blur));
  backdrop-filter: blur(var(--mg-glass-blur));
  border-radius: var(--mg-radius-md);
  box-shadow: var(--mg-shadow-sm);
}
.page-info {
  font-size: 13px;
  color: var(--mg-text-soft);
}
.page-actions {
  display: flex;
  gap: 8px;
}
.page-actions button {
  min-height: 44px;
  padding: 10px 14px;
  border-radius: var(--mg-radius-pill);
  border: 1.5px solid var(--mg-glass-border);
  background: var(--mg-glass-bg-strong);
  font-size: 12px;
  font-weight: 600;
  color: var(--mg-text);
  cursor: pointer;
  -webkit-tap-highlight-color: transparent;
  transition: transform 150ms ease;
}
.page-actions button:active:not(:disabled) { transform: scale(0.97); }
.page-actions button:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}
</style>

<!-- v77 P2.6-B: dark mode 适配（v60-v67 教训：必须非 scoped）
     2026-08-31 液态毛玻璃升级: --mg-* token 自带 dark 变体, 玻璃卡无需再覆盖;
     保留的老 class 名 (trash-item / countdown-*) 可能被其他历史渲染命中, 不删防回归.
     page-actions button 的 dark 覆盖已改为 --mg-* 玻璃值 (原 --color-bg-card 实色会盖掉玻璃). -->
<style>
[data-theme="dark"] .trash-item {
  background: var(--color-bg-card);
  border: 1px solid var(--color-border-light);
}
[data-theme="dark"] .trash-item .task-title {
  color: var(--color-text-primary);
}
[data-theme="dark"] .countdown-imminent {
  background: var(--color-danger-bg);
  color: var(--color-danger);
}
[data-theme="dark"] .countdown-urgent {
  background: var(--color-warning-bg);
  color: var(--color-warning);
}
[data-theme="dark"] .countdown-warning {
  background: var(--color-primary-bg);
  color: var(--color-primary);
}
[data-theme="dark"] .header-action {
  color: var(--mg-text);
}
[data-theme="dark"] .page-actions button {
  background: var(--mg-glass-bg-strong);
  color: var(--mg-text);
  border: 1.5px solid var(--mg-glass-border);
}
</style>