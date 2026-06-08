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

    <div style="overflow-x: auto">
      <el-table
        v-loading="loading"
        :data="trashTasks"
        stripe
        style="width: 100%"
        @selection-change="handleSelectionChange"
      >
        <el-table-column v-if="editMode" type="selection" width="45" />
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
              <el-avatar v-else :size="24" style="background: #409eff" :alt="`${memberStore.getMemberName(row.assignee_id)}的头像`">
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
  </el-card>
</template>

<script setup>
import { ref, watch, onMounted, onUnmounted } from 'vue'
import { Delete, RefreshRight, DeleteFilled, Clock, Edit } from '@element-plus/icons-vue'
import { formatDateTime } from '@/utils/format'
import { getStatusType, getStatusLabel, getPriorityType, getPriorityLabel } from '@/utils/task'
import { useMemberStore } from '@/stores/member'
import dayjs from 'dayjs'

const memberStore = useMemberStore()

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

const editMode = ref(false)
const selectedRows = ref([])

const handleSelectionChange = (rows) => {
  selectedRows.value = rows
}

const exitEditMode = () => {
  editMode.value = false
  selectedRows.value = []
}

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
  color: #d73838;
  font-weight: var(--font-weight-bold);
  animation: pulse-danger 1.2s ease-in-out infinite;
}

/* < 6h：紧急 */
.auto-delete-urgent {
  color: #e85a4f;
  font-weight: var(--font-weight-semibold);
}

/* 6-24h：警告 */
.auto-delete-warning {
  color: #f59e0b;
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
