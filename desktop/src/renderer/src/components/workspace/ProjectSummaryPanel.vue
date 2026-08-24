<script setup lang="ts">
import { computed } from 'vue'
import type { ProjectOverview, WorkspaceSummary } from '../../../../shared/workspace/research-workspace-schema'

const props = withDefaults(defineProps<{
  overview: ProjectOverview | null
  summary: WorkspaceSummary | null
}>(), {
  overview: null,
  summary: null
})

const healthScore = computed(() => props.summary?.healthScore ?? 0)
const healthColor = computed(() => {
  if (healthScore.value >= 80) return '#10b981'
  if (healthScore.value >= 50) return '#f59e0b'
  return '#ef4444'
})
const healthLabel = computed(() => {
  if (healthScore.value >= 80) return '健康'
  if (healthScore.value >= 50) return '正常'
  return '需关注'
})
</script>

<template>
  <div class="summary-panel">
    <div class="summary-panel__title">项目总览</div>
    <div class="summary-panel__body">
      <div class="summary-panel__row">
        <span class="summary-panel__label">标题</span>
        <span class="summary-panel__val">{{ overview?.title ?? '--' }}</span>
      </div>
      <div class="summary-panel__row">
        <span class="summary-panel__label">领域</span>
        <span class="summary-panel__val">{{ overview?.domain ?? '--' }}</span>
      </div>
      <div class="summary-panel__row">
        <span class="summary-panel__label">状态</span>
        <span class="summary-panel__val">{{ overview?.status ?? '--' }}</span>
      </div>
      <div class="summary-panel__row">
        <span class="summary-panel__label">成员</span>
        <span class="summary-panel__val">{{ overview?.memberCount ?? 0 }} 人</span>
      </div>
      <div class="summary-panel__row">
        <span class="summary-panel__label">任务</span>
        <span class="summary-panel__val">{{ overview?.taskCount ?? 0 }}</span>
      </div>
    </div>
    <div class="summary-panel__health">
      <div class="summary-panel__health-row">
        <span class="summary-panel__health-label">健康度</span>
        <span class="summary-panel__health-val" :style="{ color: healthColor }">{{ healthLabel }} {{ healthScore }}%</span>
      </div>
      <div class="summary-panel__health-row">
        <span class="summary-panel__health-label">活跃模块</span>
        <span class="summary-panel__health-val">{{ summary?.activeModules ?? 0 }} / {{ summary?.totalModules ?? 0 }}</span>
      </div>
    </div>
  </div>
</template>

<style scoped>
.summary-panel {
  background: linear-gradient(180deg, #ffffff 0%, #f8fafc 100%);
  border: 1px solid rgba(15, 23, 42, 0.08);
  border-radius: 12px;
  padding: 20px;
}
.summary-panel__title {
  font-size: 14px;
  font-weight: 600;
  color: #1e293b;
  margin-bottom: 12px;
}
.summary-panel__body {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.summary-panel__row {
  display: flex;
  justify-content: space-between;
  padding: 6px 0;
  border-bottom: 1px solid rgba(15, 23, 42, 0.04);
}
.summary-panel__label {
  font-size: 12px;
  color: #94a3b8;
}
.summary-panel__val {
  font-size: 13px;
  font-weight: 600;
  color: #1e293b;
}
.summary-panel__health {
  margin-top: 16px;
  padding-top: 16px;
  border-top: 2px solid rgba(15, 23, 42, 0.06);
}
.summary-panel__health-row {
  display: flex;
  justify-content: space-between;
  margin-bottom: 6px;
}
.summary-panel__health-label {
  font-size: 12px;
  color: #475569;
}
.summary-panel__health-val {
  font-size: 14px;
  font-weight: 700;
}
</style>