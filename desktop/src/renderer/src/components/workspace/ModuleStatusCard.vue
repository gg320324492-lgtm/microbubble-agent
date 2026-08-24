<script setup lang="ts">
import { computed } from 'vue'
import type { WorkspaceModule } from '../../../../shared/workspace/research-workspace-schema'

const props = withDefaults(defineProps<{ module: WorkspaceModule }>(), {})

const statusLabel = computed(() => {
  if (props.module.status === 'ready') return '就绪'
  if (props.module.status === 'running') return '运行中'
  if (props.module.status === 'paused') return '暂停'
  if (props.module.status === 'completed') return '已完成'
  if (props.module.status === 'failed') return '失败'
  return '已禁用'
})

const statusColor = computed(() => {
  if (props.module.status === 'ready') return '#10b981'
  if (props.module.status === 'running') return '#FF7A5C'
  if (props.module.status === 'paused') return '#f59e0b'
  if (props.module.status === 'completed') return '#3b82f6'
  if (props.module.status === 'failed') return '#ef4444'
  return '#94a3b8'
})
</script>

<template>
  <div class="module-card" :data-status="module.status">
    <div class="module-card__head">
      <span class="module-card__category">{{ module.category }}</span>
      <span class="module-card__status" :style="{ background: statusColor }">{{ statusLabel }}</span>
    </div>
    <div class="module-card__name">{{ module.name }}</div>
    <div class="module-card__desc">{{ module.description }}</div>
  </div>
</template>

<style scoped>
.module-card {
  background: linear-gradient(180deg, #ffffff 0%, #f8fafc 100%);
  border: 1px solid rgba(15, 23, 42, 0.08);
  border-radius: 12px;
  padding: 16px;
  transition: transform 200ms ease, box-shadow 200ms ease;
}
.module-card:hover {
  transform: translateY(-2px);
  box-shadow: 0 8px 24px rgba(15, 23, 42, 0.08);
}
.module-card__head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
}
.module-card__category {
  font-size: 11px;
  font-weight: 600;
  color: #94a3b8;
  text-transform: uppercase;
  letter-spacing: 0.05em;
}
.module-card__status {
  font-size: 11px;
  color: white;
  padding: 2px 8px;
  border-radius: 999px;
}
.module-card__name {
  font-size: 16px;
  font-weight: 600;
  color: #1e293b;
  margin-bottom: 4px;
}
.module-card__desc {
  font-size: 12px;
  color: #475569;
  line-height: 1.5;
}
</style>