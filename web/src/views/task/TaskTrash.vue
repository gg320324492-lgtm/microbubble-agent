<template>
  <div class="task-trash">
    <el-empty v-if="trashTasks.length === 0" description="垃圾桶为空" />
    <div v-else class="trash-list">
      <div v-for="task in trashTasks" :key="task.id" class="trash-item">
        <div class="trash-info">
          <div class="trash-title">{{ task.title }}</div>
          <div class="trash-meta">
            <span>删除于: {{ formatDate(task.deleted_at) }}</span>
            <span v-if="task.auto_delete_at" class="auto-delete">
              {{ getAutoDeleteText(task.auto_delete_at) }}
            </span>
          </div>
        </div>
        <div class="trash-actions">
          <el-button size="small" @click="$emit('restore', task.id)">
            <el-icon><RefreshRight /></el-icon> 恢复
          </el-button>
          <el-button size="small" type="danger" @click="$emit('permanent-delete', task.id)">
            <el-icon><Delete /></el-icon> 永久删除
          </el-button>
        </div>
      </div>
    </div>
    <!-- 分页 -->
    <el-pagination
      v-if="trashTotal > trashPageSize"
      v-model:current-page="trashPage"
      :page-size="trashPageSize"
      :total="trashTotal"
      layout="prev, pager, next"
      @current-change="$emit('page-change', $event)"
    />
  </div>
</template>

<script setup>
import { RefreshRight, Delete } from '@element-plus/icons-vue'
import { formatDate } from '@/utils/format'
import dayjs from 'dayjs'

defineProps({
  trashTasks: { type: Array, default: () => [] },
  trashTotal: { type: Number, default: 0 },
  trashPage: { type: Number, default: 1 },
  trashPageSize: { type: Number, default: 20 }
})

defineEmits(['restore', 'permanent-delete', 'page-change'])

function getAutoDeleteText(autoDeleteAt) {
  const diff = dayjs(autoDeleteAt).diff(dayjs(), 'hour')
  if (diff < 0) return '即将删除'
  if (diff < 1) return `${Math.round(diff * 60)}分钟后删除`
  if (diff < 24) return `${Math.round(diff)}小时后删除`
  return `${Math.round(diff / 24)}天后删除`
}
</script>
