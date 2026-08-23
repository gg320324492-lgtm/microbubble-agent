<script setup lang="ts">
/**
 * 科研项目卡片 — Dashboard / 首页使用。
 * Props: title, progress 0..1, status, description
 */
defineProps<{
  title: string
  progress: number
  status: 'active' | 'planning' | 'completed' | 'paused'
  description?: string
}>()

const STATUS_MAP: Record<string, { label: string; color: string }> = {
  active:     { label: '进行中', color: '#10B981' },
  planning:   { label: '规划中', color: '#F59E0B' },
  completed:  { label: '已完成', color: '#3B82F6' },
  paused:     { label: '已暂停', color: '#94A3B8' }
}
</script>

<template>
  <div class="project-card">
    <div class="project-card__header">
      <h3 class="project-card__title">{{ title }}</h3>
      <span class="project-card__status" :style="{ color: STATUS_MAP[status]?.color }">
        {{ STATUS_MAP[status]?.label }}
      </span>
    </div>
    <p v-if="description" class="project-card__desc">{{ description }}</p>
    <div class="project-card__progress">
      <div class="project-card__bar">
        <div class="project-card__fill" :style="{ width: Math.round(progress * 100) + '%' }" />
      </div>
      <span class="project-card__pct">{{ Math.round(progress * 100) }}%</span>
    </div>
  </div>
</template>

<style scoped>
.project-card {
  background: #fff;
  border: 1px solid #e5e7eb;
  border-radius: 12px;
  padding: 20px;
  transition: box-shadow .15s;
}
.project-card:hover { box-shadow: 0 2px 12px rgba(0,0,0,.06); }
.project-card__header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px; }
.project-card__title { margin: 0; font-size: 15px; font-weight: 600; color: #1e293b; }
.project-card__status { font-size: 12px; font-weight: 500; }
.project-card__desc { margin: 0 0 12px; font-size: 13px; color: #64748b; line-height: 1.5; }
.project-card__progress { display: flex; align-items: center; gap: 10px; }
.project-card__bar { flex: 1; height: 6px; background: #f1f5f9; border-radius: 3px; overflow: hidden; }
.project-card__fill { height: 100%; background: linear-gradient(90deg, #3b82f6, #60a5fa); border-radius: 3px; transition: width .3s; }
.project-card__pct { font-size: 13px; font-weight: 600; color: #3b82f6; min-width: 36px; text-align: right; }
</style>
