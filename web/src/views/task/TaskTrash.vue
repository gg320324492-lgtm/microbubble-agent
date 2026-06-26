<template>
  <el-card class="task-list-card">
    <!-- 顶部操作栏 -->
    <div class="trash-toolbar">
      <el-button v-if="!editMode" text type="primary" @click="editMode = true">
        <el-icon><Edit /></el-icon> 编辑
      </el-button>
      <template v-else>
        <el-button text @click="exitEditMode">取消</el-button>
        <span v-if="selectedRows.length > 0" class="batch-count">已选 {{ selectedRows.length }} 项</span>
        <el-button text type="danger" :disabled="selectedRows.length === 0" @click="batchPermanentDelete">
          <el-icon><DeleteFilled /></el-icon>
          批量永久删除 {{ selectedRows.length > 0 ? `(${selectedRows.length})` : '' }}
        </el-button>
      </template>
    </div>

    <!-- PR #7: 移动端用 CardList，桌面端用 el-table（双栈物理隔离） -->
    <template v-if="isMobile">
      <CardList
        :items="trashTasks"
        :selectable="editMode"
        v-model:selected="selectedRows"
        :field-config="mobileFieldConfig"
        :has-more="hasMore"
        :loading="loading"
        empty-icon="🗑"
        empty-title="回收站是空的"
        empty-hint="删除的任务会在这里保留 3 天"
        @item-click="onMobileItemClick"
      >
        <template #batch-actions="{ selected, clear }">
          <el-button text type="danger" size="small" @click="batchPermanentDelete">
            永久删除 ({{ selected.length }})
          </el-button>
          <el-button text size="small" @click="clear">取消</el-button>
        </template>
        <template #item-actions="{ item }">
          <div class="mobile-task-actions">
            <template v-if="isAdmin || item.created_by === currentUserId || item.assignee_id === currentUserId">
              <button type="button" class="mobile-action-btn restore" @click.stop="$emit('restore', item.id)">
                ↩️ 恢复
              </button>
              <button type="button" class="mobile-action-btn delete" @click.stop="$emit('permanent-delete', item.id)">
                🗑 永久删除
              </button>
            </template>
            <span v-else class="no-permission">无权限</span>
          </div>
        </template>
      </CardList>

      <!-- 移动端简易分页 -->
      <div v-if="trashTotal > 0" class="mobile-pagination">
        <span class="page-info">第 {{ currentPage }} / {{ totalPages }} 页</span>
        <div class="page-actions">
          <button type="button" :disabled="currentPage <= 1" @click="onPageChange(currentPage - 1)">
            上一页
          </button>
          <button type="button" :disabled="currentPage >= totalPages" @click="onPageChange(currentPage + 1)">
            下一页
          </button>
        </div>
      </div>
    </template>

    <template v-else>
      <div style="overflow-x: auto">
        <el-table
          ref="tableRef"
          v-loading="loading"
          :data="trashTasks"
          stripe
          style="width: 100%"
          @selection-change="handleSelectionChange"
        >
          <el-table-column type="selection" width="45" :class-name="editMode ? '' : 'col-hidden'" />
          <el-table-column prop="title" label="任务标题" min-width="200">
            <template #default="{ row }">
              <div class="task-title-cell">
                <el-icon color="#909399"><Delete /></el-icon>
                <span class="task-deleted">{{ row.title }}</span>
              </div>
            </template>
          </el-table-column>

          <el-table-column prop="assignee_id" label="负责人" width="150">
            <template #default="{ row }">
              <div class="assignee-cell">
                <el-avatar
                  v-if="memberStore.getMemberAvatar(row.assignee_id)"
                  :src="memberStore.getMemberAvatar(row.assignee_id)"
                  :size="24"
                  :alt="`${memberStore.getMemberName(row.assignee_id)}的头像`"
                />
                <el-avatar v-else :size="24" style="background: var(--color-primary)" :alt="`${memberStore.getMemberName(row.assignee_id)}的头像`">
                  {{ memberStore.getMemberName(row.assignee_id).charAt(0) }}
                </el-avatar>
                <span>{{ memberStore.getMemberName(row.assignee_id) }}</span>
              </div>
            </template>
          </el-table-column>

          <el-table-column prop="priority" label="优先级" width="100">
            <template #default="{ row }">
              <el-tag :type="getPriorityType(row.priority)" size="small">
                {{ getPriorityLabel(row.priority) }}
              </el-tag>
            </template>
          </el-table-column>

          <el-table-column prop="status" label="原状态" width="120">
            <template #default="{ row }">
              <el-tag :type="getStatusType(row.status)" size="small">
                {{ getStatusLabel(row.status) }}
              </el-tag>
            </template>
          </el-table-column>

          <el-table-column label="删除时间" width="140">
            <template #default="{ row }">
              <span class="deleted-time">{{ formatDateTime(row.deleted_at) }}</span>
            </template>
          </el-table-column>

          <el-table-column label="自动删除" width="170">
            <template #default="{ row }">
              <div v-if="row.auto_delete_at" class="auto-delete-cell">
                <div :class="['auto-delete-relative', getAutoDeleteClass(row.auto_delete_at)]">
                  <el-icon v-if="getAutoDeleteIcon(row.auto_delete_at)" class="auto-delete-icon">
                    <Clock />
                  </el-icon>
                  {{ getAutoDeleteText(row.auto_delete_at) }}
                </div>
                <div class="auto-delete-absolute">
                  {{ formatAutoDeleteExact(row.auto_delete_at) }} 删除
                </div>
              </div>
              <span v-else class="auto-delete-none">—</span>
            </template>
          </el-table-column>

          <el-table-column label="操作" width="220" fixed="right">
            <template #default="{ row }">
              <div class="task-actions">
                <template v-if="isAdmin || row.created_by === currentUserId || row.assignee_id === currentUserId">
                  <el-button text type="success" @click="$emit('restore', row.id)">
                    <el-icon><RefreshRight /></el-icon>
                    恢复
                  </el-button>
                  <el-button text type="danger" @click="$emit('permanent-delete', row.id)">
                    <el-icon><DeleteFilled /></el-icon>
                    永久删除
                  </el-button>
                </template>
                <span v-else class="no-permission">--</span>
              </div>
            </template>
          </el-table-column>
        </el-table>
      </div>

      <!-- 分页 -->
      <div class="pagination">
        <el-pagination
          v-model:current-page="currentPage"
          v-model:page-size="pageSize"
          :page-sizes="[10, 20, 50]"
          :total="trashTotal"
          layout="total, sizes, prev, pager, next"
          @size-change="onSizeChange"
          @current-change="onPageChange"
        />
      </div>
    </template>
  </el-card>
</template>

<script setup>
import { ref, computed, watch, onMounted, onUnmounted } from 'vue'
import { Delete, RefreshRight, DeleteFilled, Clock, Edit } from '@element-plus/icons-vue'
import { formatDateTime } from '@/utils/format'
import { getStatusType, getStatusLabel, getPriorityType, getPriorityLabel } from '@/utils/task'
import { useMemberStore } from '@/stores/member'
import { useIsMobile } from '@/composables/useIsMobile'
import CardList from '@/components/mobile/CardList.vue'
import dayjs from 'dayjs'

const memberStore = useMemberStore()
const { isMobile } = useIsMobile()

const props = defineProps({
  trashTasks: { type: Array, default: () => [] },
  trashTotal: { type: Number, default: 0 },
  trashPage: { type: Number, default: 1 },
  trashPageSize: { type: Number, default: 20 },
  loading: { type: Boolean, default: false },
  isAdmin: { type: Boolean, default: false },
  currentUserId: { type: [Number, String], default: null }
})

const emit = defineEmits(['restore', 'permanent-delete', 'batch-permanent-delete', 'page-change', 'size-change'])

// ============================================================================
// 移动端 CardList 配置（PR #7）
// ============================================================================
const mobileFieldConfig = computed(() => ({
  title: (row) => row.title,
  subtitle: (row) => `${memberStore.getMemberName(row.assignee_id)} · 优先级：${getPriorityLabel(row.priority)}`,
  badge: (row) => ({
    label: getAutoDeleteText(row.auto_delete_at) || getStatusLabel(row.status),
    type: row.auto_delete_at ? getAutoDeleteType(row.auto_delete_at) : getStatusType(row.status),
  }),
  fields: (row) => [
    { key: 'deleted', label: '删除时间', value: formatDateTime(row.deleted_at) || '—' },
    { key: 'auto', label: '自动删除', value: row.auto_delete_at ? formatAutoDeleteExact(row.auto_delete_at) : '—' },
  ],
}))

function getAutoDeleteType(autoDeleteAt) {
  const hours = getAutoDeleteHours(autoDeleteAt)
  if (hours <= 6) return 'danger'
  if (hours <= 24) return 'warning'
  return 'info'
}

const totalPages = computed(() => Math.max(1, Math.ceil(props.trashTotal / props.trashPageSize)))
const hasMore = computed(() => props.trashPage < totalPages.value)

function onMobileItemClick(item) {
  // 移动端默认点击行为由 CardList 多选触发；如需详情，可在父组件监听 item-click
}

const editMode = ref(false)
const selectedRows = ref([])

const handleSelectionChange = (rows) => {
  selectedRows.value = rows
}

const exitEditMode = () => {
  editMode.value = false
  selectedRows.value = []
  // 清除表格选择状态
  if (tableRef.value) {
    tableRef.value.clearSelection()
  }
}

const tableRef = ref(null)

const batchPermanentDelete = () => {
  const ids = selectedRows.value.map(r => r.id)
  emit('batch-permanent-delete', ids)
}

const currentPage = ref(props.trashPage)
const pageSize = ref(props.trashPageSize)

// 响应式时间，每 30s 刷新以驱动实时倒计时
const now = ref(dayjs())
let timer = null

onMounted(() => {
  timer = setInterval(() => {
    now.value = dayjs()
  }, 30 * 1000)
})

onUnmounted(() => {
  if (timer) clearInterval(timer)
})

watch(() => props.trashPage, (v) => { currentPage.value = v })
watch(() => props.trashPageSize, (v) => { pageSize.value = v })

const onPageChange = (page) => {
  currentPage.value = page
  emit('page-change', page)
}

const onSizeChange = (size) => {
  pageSize.value = size
  emit('size-change', size)
}

// 自动删除倒计时 — 精确到分钟
function getAutoDeleteText(autoDeleteAt) {
  if (!autoDeleteAt) return ''
  const expire = dayjs(autoDeleteAt)
  const diffMin = expire.diff(now.value, 'minute')
  const diffHour = expire.diff(now.value, 'hour')
  const diffDay = Math.floor(diffMin / (60 * 24))
  const remMin = diffMin % 60

  if (diffMin <= 0) return '即将自动删除'
  if (diffMin < 60) return `${diffMin} 分钟后删除`
  if (diffMin < 24 * 60) {
    if (remMin > 0) return `${diffHour} 小时 ${remMin} 分后删除`
    return `${diffHour} 小时后删除`
  }
  const remHourOfDay = Math.floor((diffMin % (60 * 24)) / 60)
  if (remHourOfDay > 0) return `${diffDay} 天 ${remHourOfDay} 小时后删除`
  return `${diffDay} 天后删除`
}

// 剩余小时数（用于颜色分级）
function getAutoDeleteHours(autoDeleteAt) {
  if (!autoDeleteAt) return Infinity
  return dayjs(autoDeleteAt).diff(now.value, 'hour', true)
}

// 颜色分级：< 6h 红 / 6-24h 橙 / 24-72h 黄 / > 72h 灰
function getAutoDeleteClass(autoDeleteAt) {
  const hours = getAutoDeleteHours(autoDeleteAt)
  if (hours <= 0) return 'auto-delete-imminent'
  if (hours <= 6) return 'auto-delete-urgent'
  if (hours <= 24) return 'auto-delete-warning'
  if (hours <= 72) return 'auto-delete-normal'
  return 'auto-delete-safe'
}

// 紧急时显示时钟图标
function getAutoDeleteIcon(autoDeleteAt) {
  return getAutoDeleteHours(autoDeleteAt) <= 24
}

// 准确删除时间 — "06-04 14:30"
function formatAutoDeleteExact(autoDeleteAt) {
  return dayjs(autoDeleteAt).format('MM-DD HH:mm')
}
</script>

<style scoped>
.trash-toolbar {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 12px;
}

.batch-count {
  font-size: 13px;
  color: var(--color-text-secondary);
  margin-left: auto;
}

/* 隐藏选择列（非编辑模式） */
:deep(.col-hidden) {
  visibility: hidden;
  width: 0 !important;
  padding: 0 !important;
  overflow: hidden;
}
.task-title-cell {
  display: flex;
  align-items: center;
  gap: 12px;
}

.task-deleted {
  color: var(--color-text-secondary);
  text-decoration: line-through;
}

.assignee-cell {
  display: flex;
  align-items: center;
  gap: var(--space-2);
}

.deleted-time {
  color: var(--color-text-placeholder);
  font-size: var(--font-size-xs);
}

.task-actions {
  display: flex;
  gap: 4px;
}

.no-permission {
  color: var(--color-text-placeholder);
  font-size: 13px;
}

.pagination {
  margin-top: 20px;
  display: flex;
  justify-content: flex-end;
}

/* PR #7: 移动端样式（CardList + 简易分页） */
.mobile-task-actions {
  display: flex;
  gap: 8px;
  margin-top: 6px;
}
.mobile-action-btn {
  flex: 1;
  padding: 8px;
  border-radius: var(--radius-sm);
  border: none;
  font-size: 12px;
  cursor: pointer;
  -webkit-tap-highlight-color: transparent;
}
.mobile-action-btn.restore {
  background: var(--color-success-bg);
  color: var(--color-success, #67C23A);
}
.mobile-action-btn.delete {
  background: var(--color-danger-bg);
  color: var(--color-danger, #F56C6C);
}
.mobile-action-btn:active { opacity: 0.7; }

.mobile-pagination {
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

/* 自动删除倒计时 — 两行显示 */
.auto-delete-cell {
  display: flex;
  flex-direction: column;
  gap: 2px;
  line-height: 1.3;
}

.auto-delete-relative {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  font-size: 13px;
  font-variant-numeric: tabular-nums;
}

.auto-delete-absolute {
  font-size: 11px;
  color: var(--color-text-placeholder);
  font-variant-numeric: tabular-nums;
}

.auto-delete-icon {
  font-size: 12px;
  animation: pulse-warning 2s ease-in-out infinite;
}

.auto-delete-none {
  color: var(--color-text-placeholder);
}

/* <= 0h：已过期 */
.auto-delete-imminent {
  color: var(--color-danger);
  font-weight: var(--font-weight-bold);
  animation: pulse-danger 1.2s ease-in-out infinite;
}

/* < 6h：紧急 */
.auto-delete-urgent {
  color: var(--color-danger);
  font-weight: var(--font-weight-semibold);
}

/* 6-24h：警告 */
.auto-delete-warning {
  color: var(--color-warning);
  font-weight: var(--font-weight-medium);
}

/* 24-72h：正常 */
.auto-delete-normal {
  color: var(--color-text-secondary);
}

/* > 72h：安全 */
.auto-delete-safe {
  color: var(--color-text-placeholder);
}

@keyframes pulse-danger {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.5; }
}

@keyframes pulse-warning {
  0%, 100% { opacity: 0.7; }
  50% { opacity: 1; }
}
</style>

<style>
/* v69 P1b: dark mode 覆盖（v60-v67 教训：必须非 scoped） */
[data-theme="dark"] .batch-count { color: var(--color-text-secondary); }
[data-theme="dark"] .mobile-pagination {
  background: var(--color-bg-card);
}
[data-theme="dark"] .page-actions button {
  border-color: var(--color-border);
  background: var(--color-bg-page);
  color: var(--color-text-regular);
}
[data-theme="dark"] .auto-delete-imminent { color: var(--color-danger); }
[data-theme="dark"] .auto-delete-urgent { color: var(--color-warning); }
[data-theme="dark"] .auto-delete-warning { color: var(--color-warning); }
[data-theme="dark"] .mobile-action-btn.restore {
  background: var(--color-success-bg);
  color: var(--color-success, #67C23A);
}
[data-theme="dark"] .mobile-action-btn.delete {
  background: var(--color-danger-bg);
  color: var(--color-danger, #F56C6C);
}
</style>
