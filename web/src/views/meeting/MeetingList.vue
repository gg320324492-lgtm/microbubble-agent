<template>
  <div class="meeting-list">
    <el-empty v-if="meetings.length === 0" description="暂无会议" />
    <div v-else class="meeting-items">
      <div v-for="meeting in meetings" :key="meeting.id" class="meeting-item" @click="$emit('select', meeting)">
        <div class="meeting-title">{{ meeting.title }}</div>
        <div class="meeting-time">{{ formatDate(meeting.start_time) }}</div>
        <div class="meeting-status">
          <el-tag :type="statusType(meeting.status)">
            {{ statusLabel(meeting.status) }}
          </el-tag>
        </div>
      </div>
    </div>
    <!-- 分页 -->
    <el-pagination
      v-if="total > pageSize"
      :current-page="currentPage"
      :page-size="pageSize"
      :total="total"
      layout="prev, pager, next"
      @update:current-page="(v) => $emit('page-change', v)"
    />
  </div>
</template>

<script setup>
import { formatDate } from '@/utils/format'

defineProps({
  meetings: { type: Array, default: () => [] },
  total: { type: Number, default: 0 },
  currentPage: { type: Number, default: 1 },
  pageSize: { type: Number, default: 20 }
})

defineEmits(['select', 'page-change'])

const statusLabel = (s) => ({ scheduled: '已预约', recording: '录制中', processing: '处理中', completed: '已完成', cancelled: '已取消', error: '处理失败' }[s] || s)
const statusType = (s) => ({ scheduled: 'info', recording: 'warning', processing: 'warning', completed: 'success', cancelled: 'info', error: 'danger' }[s] || 'info')
</script>
