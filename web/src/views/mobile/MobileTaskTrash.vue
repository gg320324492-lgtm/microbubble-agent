<template>
  <div class="mobile-task-trash">
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
      <div class="trash-hint">
        <span class="hint-icon">ℹ️</span>
        <span>回收站任务将在 3 天后自动永久删除</span>
      </div>

      <!-- CardList 列表（支持多选） -->
      <CardList
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
.mobile-task-trash {
  min-height: 100vh;
  background: var(--color-bg-page);
  display: flex;
  flex-direction: column;
}

.trash-main {
  flex: 1;
  padding: var(--mobile-padding-y, 12px) var(--mobile-padding-x, 16px);
}

.trash-hint {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 8px 12px;
  background: var(--color-warning-bg);
  border-radius: var(--radius-md);
  font-size: 12px;
  color: var(--color-warning, #E6A23C);
  margin-bottom: 12px;
}

.header-action {
  width: 36px;
  height: 36px;
  border-radius: 50%;
  background: transparent;
  border: none;
  font-size: 18px;
  color: var(--color-text-regular);
  cursor: pointer;
}
.header-action:active { background: var(--color-primary-bg); }

/* CardList slot */
.item-actions {
  display: flex;
  gap: 6px;
  margin-top: 6px;
}
.item-btn {
  flex: 1;
  padding: 6px;
  border-radius: var(--radius-sm);
  border: none;
  font-size: 12px;
  cursor: pointer;
  -webkit-tap-highlight-color: transparent;
}
.item-btn.restore {
  background: var(--color-success-bg);
  color: var(--color-success, #67C23A);
}
.item-btn.danger {
  background: var(--color-danger-bg);
  color: var(--color-danger, #F56C6C);
}
.no-permission {
  font-size: 11px;
  color: var(--color-text-placeholder);
  padding: 6px;
}

/* Batch */
.batch-btn {
  flex: 1;
  padding: 8px;
  border-radius: var(--radius-sm);
  border: none;
  font-size: 13px;
  cursor: pointer;
  background: var(--color-bg-page);
  color: var(--color-text-primary);
}
.batch-btn.danger {
  background: var(--color-danger-bg);
  color: var(--color-danger, #F56C6C);
}

/* 分页 */
.pagination {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 16px;
  margin-top: 12px;
  background: var(--color-bg-card);
  border-radius: var(--radius-md);
}
.page-info {
  font-size: 13px;
  color: var(--color-text-secondary);
}
.page-actions {
  display: flex;
  gap: 8px;
}
.page-actions button {
  padding: 6px 14px;
  border-radius: var(--radius-sm);
  border: 1px solid var(--color-border);
  background: var(--color-bg-page);
  font-size: 12px;
  color: var(--color-text-regular);
  cursor: pointer;
}
.page-actions button:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}
</style>

<!-- v77 P2.6-B: dark mode 适配（v60-v67 教训：必须非 scoped） -->
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
[data-theme="dark"] .page-actions button {
  background: var(--color-bg-card);
  color: var(--color-text-primary);
  border: 1px solid var(--color-border-light);
}
</style>