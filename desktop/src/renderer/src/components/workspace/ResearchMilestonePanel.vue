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
  // [类 20.191] 2026-08-27: 移除硬编码 5 个默认 milestone (知识库初始化 / 实验方案设计 / etc.).
  // 这些都是 demo 数据, 没有真实任务对应. 父组件必须传 milestones, 否则显示空态.
  milestones: () => []
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
    <!-- [类 20.191] 2026-08-27: 空数组时显示空态, 而不是渲染空 wrapper -->
    <div v-if="!milestones || milestones.length === 0" class="milestone-panel__empty">
      暂无里程碑数据. 请在父组件传入 milestones, 或从后端 ResearchProgress.milestones 字段读取.
    </div>
    <template v-else>
      <div v-for="m in milestones" :key="m.id" class="milestone-panel__row">
        <div class="milestone-panel__dot" :style="{ background: statusColor[m.status] }"></div>
        <div class="milestone-panel__body">
          <div class="milestone-panel__name">{{ m.title }}</div>
          <div class="milestone-panel__status" :style="{ color: statusColor[m.status] }">{{ statusLabel[m.status] }}</div>
        </div>
      </div>
    </template>
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
.milestone-panel__empty {
  font-size: 12px;
  color: #94a3b8;
  padding: 12px 0;
  text-align: center;
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
</content>
</invoke>