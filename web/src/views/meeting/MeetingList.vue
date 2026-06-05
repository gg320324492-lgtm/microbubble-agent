<template>
  <div class="meeting-list">
    <el-empty v-if="meetings.length === 0" description="暂无会议" />
    <div v-else class="meeting-items">
      <div v-for="meeting in meetings" :key="meeting.id" class="meeting-item" @click="$emit('select', meeting)">
        <div class="meeting-title">{{ meeting.title }}</div>
        <div class="meeting-time">{{ formatDate(meeting.start_time) }}</div>
        <div class="meeting-status">
          <el-tag :type="meeting.status === 'completed' ? 'success' : 'info'">
            {{ meeting.status }}
          </el-tag>
        </div>
      </div>
    </div>
    <!-- 分页 -->
    <el-pagination
      v-if="total > pageSize"
      v-model:current-page="currentPage"
      :page-size="pageSize"
      :total="total"
      layout="prev, pager, next"
      @current-change="$emit('page-change', $event)"
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
</script>
