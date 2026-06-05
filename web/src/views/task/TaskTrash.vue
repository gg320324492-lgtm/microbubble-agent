<template>
  <el-card class="task-list-card">
    <div style="overflow-x: auto">
      <el-table v-loading="loading" :data="trashTasks" stripe style="width: 100%">
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
              />
              <el-avatar v-else :size="24" style="background: #409eff">
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

        <el-table-column label="自动删除" width="160">
          <template #default="{ row }">
            <el-tooltip
              v-if="row.auto_delete_at"
              :content="`将于 ${formatDateTime(row.auto_delete_at)} 永久删除`"
              placement="top"
            >
              <span :class="getAutoDeleteClass(row.auto_delete_at)">
                <el-icon v-if="isUrgent(row.auto_delete_at)" class="auto-delete-icon">
                  <Clock />
                </el-icon>
                {{ getAutoDeleteText(row.auto_delete_at) }}
              </span>
            </el-tooltip>
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
import { ref, watch } from 'vue'
import { Delete, RefreshRight, DeleteFilled, Clock } from '@element-plus/icons-vue'
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

const emit = defineEmits(['restore', 'permanent-delete', 'page-change', 'size-change'])

const currentPage = ref(props.trashPage)
const pageSize = ref(props.trashPageSize)

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

// 自动删除倒计时
function getAutoDeleteText(autoDeleteAt) {
  const diff = dayjs(autoDeleteAt).diff(dayjs(), 'hour')
  if (diff < 0) return '即将删除'
  if (diff < 1) return `${Math.round(diff * 60)}分钟后删除`
  if (diff < 24) return `${Math.round(diff)}小时后删除`
  return `${Math.round(diff / 24)}天后删除`
}

function isUrgent(autoDeleteAt) {
  const diff = dayjs(autoDeleteAt).diff(dayjs(), 'hour')
  return diff < 24
}

function getAutoDeleteClass(autoDeleteAt) {
  const diff = dayjs(autoDeleteAt).diff(dayjs(), 'hour')
  if (diff < 0) return 'auto-delete-imminent'
  if (diff < 6) return 'auto-delete-urgent'
  if (diff < 24) return 'auto-delete-warning'
  if (diff < 72) return 'auto-delete-normal'
  return 'auto-delete-safe'
}
</script>

<style scoped>
.task-title-cell {
  display: flex;
  align-items: center;
  gap: 8px;
}

.task-deleted {
  color: var(--color-text-secondary);
}

.assignee-cell {
  display: flex;
  align-items: center;
  gap: 8px;
}

.deleted-time {
  font-size: 13px;
  color: var(--color-text-secondary);
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
  display: flex;
  justify-content: flex-end;
  margin-top: 16px;
}

/* 自动删除倒计时颜色 */
.auto-delete-imminent {
  color: #ff4d4f;
  font-weight: 600;
}

.auto-delete-urgent {
  color: #ff4d4f;
  font-weight: 500;
}

.auto-delete-warning {
  color: #faad14;
}

.auto-delete-normal {
  color: var(--color-text-secondary);
}

.auto-delete-safe {
  color: var(--color-text-secondary);
}

.auto-delete-none {
  color: var(--color-text-placeholder);
}

.auto-delete-icon {
  animation: pulse 1.5s infinite;
  margin-right: 2px;
}

@keyframes pulse {
  0%, 100% { opacity: 0.6; }
  50% { opacity: 1; }
}
</style>
