<script setup lang="ts">
import { computed } from 'vue'
import type { ResearchProgress } from '../../../../shared/workspace/research-workspace-schema'

interface Milestone {
  id: string
  title: string
  status: 'pending' | 'in-progress' | 'completed' | 'blocked'
  dueDate?: string
}

withDefaults(defineProps<{
  progress: ResearchProgress | null
  milestones?: Milestone[]
}>(), {
  progress: null,
  milestones: () => [
    { id: 'm1', title: '知识库初始化', status: 'completed' },
    { id: 'm2', title: '实验方案设计', status: 'in-progress' },
    { id: 'm3', title: '数字孪生校准', status: 'in-progress' },
    { id: 'm4', title: '设备接入', status: 'pending' },
    { id: 'm5', title: '论文撰写', status: 'pending' }
  ]
})

const statusLabel = computed(() => ({
  pending: '待开始',
  'in-progress': '进行中',
  completed: '已完成',
  blocked: '阻塞'
}))
const statusColor = computed(() => ({
  pending: '#94a3b8',
  'in-progress': '#FF7A5C',
  completed: '#10b981',
  blocked: '#ef4444'
}))
</script>

<template>
  <div class="milestone-panel">
    <div class="milestone-panel__title">研究里程碑</div>
    <div v-for="m in milestones" :key="m.id" class="milestone-panel__row">
      <div class="milestone-panel__dot" :style="{ background: statusColor[m.status] }"></div>
      <div class="milestone-panel__body">
        <div class="milestone-panel__name">{{ m.title }}</div>
        <div class="milestone-panel__status" :style="{ color: statusColor[m.status] }">{{ statusLabel[m.status] }}</div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.milestone-panel {
  background: linear-gradient(180deg, #ffffff 0%, #f8fafc 100%);
  border: 1px solid rgba(15, 23, 42, 0.08);
  border-radius: 12px;
  padding: 16px;
}
.milestone-panel__title {
  font-size: 14px;
  font-weight: 600;
  color: #1e293b;
  margin-bottom: 12px;
}
.milestone-panel__row {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 8px 0;
  border-bottom: 1px solid rgba(15, 23, 42, 0.04);
}
.milestone-panel__dot {
  width: 12px;
  height: 12px;
  border-radius: 50%;
  flex-shrink: 0;
}
.milestone-panel__name {
  font-size: 13px;
  color: #1e293b;
  font-weight: 500;
}
.milestone-panel__status {
  font-size: 11px;
  margin-top: 2px;
}
</style>
