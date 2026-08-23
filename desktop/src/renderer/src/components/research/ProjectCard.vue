<script setup lang="ts">
/**
 * 科研项目卡片 — Dashboard / 首页使用。
 * Props: title, progress 0..1, status, description
 */
import { computed } from 'vue'
import ResearchIcon from '../icons/ResearchIcon.vue'

const props = defineProps<{
  title: string
  progress: number
  status: 'active' | 'planning' | 'completed' | 'paused'
  description?: string
}>()

const STATUS_MAP: Record<typeof props.status, string> = {
  active: '进行中',
  planning: '规划中',
  completed: '已完成',
  paused: '已暂停'
}
const progressPercent = computed(() => Math.round(Math.min(1, Math.max(0, props.progress)) * 100))
</script>

<template>
  <div class="project-card">
    <div class="project-card__header">
      <h3 class="project-card__title">{{ title }}</h3>
      <span :class="['project-card__status', `project-card__status--${status}`]">
        {{ STATUS_MAP[status] }}
      </span>
    </div>
    <p v-if="description" class="project-card__desc">{{ description }}</p>
    <div class="project-card__progress">
      <div class="project-card__bar">
        <div class="project-card__fill research-progress-animated" :style="{ width: progressPercent + '%' }" />
      </div>
      <span class="project-card__pct"><ResearchIcon name="progress" :size="12" />{{ progressPercent }}%</span>
    </div>
  </div>
</template>

<style scoped>
.project-card {
  background: var(--research-bg-card);
  border: 1px solid var(--research-border-subtle);
  border-radius: var(--research-radius-card);
  padding: var(--research-space-5);
  box-shadow: var(--research-shadow-soft);
  transition: box-shadow var(--research-duration-fast) var(--research-ease-standard);
}
.project-card:hover { box-shadow: var(--research-shadow-medium); }
.project-card__header { display: flex; justify-content: space-between; align-items: center; gap: var(--research-space-3); margin-bottom: var(--research-space-2); }
.project-card__title { margin: 0; font-size: var(--research-text-card-title); font-weight: var(--research-font-weight-semibold); color: var(--research-text-primary); }
.project-card__status { padding: var(--research-space-1) var(--research-space-2); border-radius: var(--research-radius-pill); background: var(--research-bg-hover); color: var(--research-text-secondary); font-size: var(--research-text-sm); font-weight: var(--research-font-weight-medium); }
.project-card__status--active { background: var(--research-success-50); color: var(--research-success-700); }
.project-card__status--planning { background: var(--research-warning-50); color: var(--research-text-primary); }
.project-card__status--completed { background: var(--research-primary-50); color: var(--research-primary-700); }
.project-card__desc { margin: 0 0 var(--research-space-3); font-size: var(--research-text-body); color: var(--research-text-secondary); line-height: var(--research-line-height-body); }
.project-card__progress { display: flex; align-items: center; gap: var(--research-space-3); }
.project-card__bar { flex: 1; height: 6px; background: var(--research-bg-hover); border-radius: var(--research-radius-pill); overflow: hidden; }
.project-card__fill { height: 100%; background: linear-gradient(90deg, var(--research-primary-600), var(--research-primary-400)); border-radius: var(--research-radius-pill); }
.project-card__pct { display: inline-flex; align-items: center; justify-content: flex-end; gap: var(--research-space-1); font-size: var(--research-text-sm); font-weight: var(--research-font-weight-semibold); color: var(--research-primary-700); min-width: 52px; text-align: right; font-variant-numeric: tabular-nums; }
</style>
