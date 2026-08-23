<script setup lang="ts">
/**
 * 智能体卡片 — Agent状态展示。
 */
import { computed } from 'vue'
import ResearchIcon from '../icons/ResearchIcon.vue'
import { isResearchIconName, type ResearchIconName } from '../icons/research-icons'

const props = defineProps<{
  icon: string
  name: string
  status: 'running' | 'completed' | 'idle' | 'error'
  task?: string
  result?: string
  duration?: string
}>()

const STATUS: Record<typeof props.status, { label: string; icon: ResearchIconName }> = {
  running: { label: '运行中', icon: 'running' },
  completed: { label: '已完成', icon: 'check' },
  idle: { label: '等待中', icon: 'idle' },
  error: { label: '异常', icon: 'error' }
}

const LEGACY_ICON_MAP: Record<string, ResearchIconName> = {
  '\u{1F4DA}': 'literature',
  '\u{1F9EA}': 'experiment',
  '\u{1F4CA}': 'data',
  '\u270D\uFE0F': 'manuscript',
  '\u{1F50D}': 'search'
}

const resolvedIcon = computed<ResearchIconName>(() =>
  isResearchIconName(props.icon) ? props.icon : LEGACY_ICON_MAP[props.icon] ?? 'agent'
)
</script>

<template>
  <article class="agent-card" :class="`agent-card--${status}`" :aria-label="`${name}：${STATUS[status].label}`">
    <div class="agent-card__icon"><ResearchIcon :name="resolvedIcon" :size="26" /></div>
    <div class="agent-card__name">{{ name }}</div>
    <div role="status" aria-live="polite" :class="['agent-card__status', { 'research-agent-running': status === 'running' }]">
      <ResearchIcon :name="STATUS[status].icon" :size="13" />
      {{ STATUS[status].label }}
    </div>
    <div v-if="task" class="agent-card__task">{{ task }}</div>
    <div v-if="result" class="agent-card__result">{{ result }}</div>
    <div v-if="duration !== undefined" class="agent-card__duration"><ResearchIcon name="clock" :size="12" />{{ duration }}</div>
  </article>
</template>

<style scoped>
.agent-card { min-width: 0; background: var(--research-bg-card); border: 1px solid var(--research-border-subtle); border-radius: var(--research-radius-card); padding: var(--research-space-4); text-align: center; box-shadow: var(--research-shadow-soft); transition: box-shadow var(--research-duration-fast) var(--research-ease-standard); }
.agent-card:hover { box-shadow: var(--research-shadow-medium); }
.agent-card--running { border-color: var(--research-ai-200); }
.agent-card--completed { border-color: var(--research-success-100); }
.agent-card--error { border-color: var(--research-danger-100); }
.agent-card__icon { display: grid; width: 44px; height: 44px; margin: 0 auto var(--research-space-2); place-items: center; border-radius: var(--research-radius-card); background: var(--research-ai-50); color: var(--research-ai-600); }
.agent-card__name { font-size: var(--research-text-body); font-weight: var(--research-font-weight-semibold); color: var(--research-text-primary); margin-bottom: var(--research-space-1); }
.agent-card__status { font-size: var(--research-text-sm); color: var(--research-text-secondary); display: flex; align-items: center; justify-content: center; gap: var(--research-space-1); }
.agent-card--running .agent-card__status { color: var(--research-ai-700); }
.agent-card--completed .agent-card__status { color: var(--research-success-700); }
.agent-card--error .agent-card__status { color: var(--research-danger-600); }
.agent-card__task { font-size: var(--research-text-xs); color: var(--research-text-secondary); margin-top: var(--research-space-2); line-height: var(--research-line-height-body); }
.agent-card__result { margin-top: var(--research-space-2); padding-top: var(--research-space-2); border-top: 1px solid var(--research-divider); color: var(--research-text-primary); font-size: var(--research-text-xs); line-height: var(--research-line-height-body); }
.agent-card__duration { display: flex; align-items: center; justify-content: center; gap: var(--research-space-1); margin-top: var(--research-space-2); color: var(--research-text-secondary); font-size: var(--research-text-xs); font-variant-numeric: tabular-nums; }
</style>
