<script setup lang="ts">
/**
 * PlanTimeline (Phase 5-D: Agent Planning Renderer).
 *
 * 渲染 SSE plan_step 事件累积的 PlanStep 列表.
 * - 完成: ✓
 * - 进行: ▶
 * - 等待: ○
 * - 失败: ❌
 *
 * 普通消息无 plan_steps -> 不显示 (v-if 短路).
 *
 * Phase 5-D: 不生成计划 / 不执行 tool / 不接 Agent backend.
 */
import { computed } from 'vue'
import type { PlanStep, PlanStepStatus } from '../../utils/agent-plan'

interface Props {
  steps: PlanStep[]
}
const props = defineProps<Props>()

const ordered = computed<PlanStep[]>(() =>
  [...props.steps].sort((a, b) => a.order - b.order)
)

const isEmpty = computed(() => props.steps.length === 0)

function iconOf(s: PlanStepStatus): string {
  switch (s) {
    case 'pending': return '○'
    case 'running': return '▶'
    case 'completed': return '✓'
    case 'failed': return '❌'
  }
}

function variantOf(s: PlanStepStatus): string {
  return `step-${s}`
}
</script>

<template>
  <div v-if="!isEmpty" class="plan-timeline">
    <header class="plan-timeline__head">
      <span class="plan-timeline__icon">🧭</span>
      <span class="plan-timeline__title">Agent Plan</span>
      <span class="plan-timeline__count">{{ steps.length }} 步</span>
    </header>
    <ol class="plan-timeline__list">
      <li v-for="s in ordered" :key="`step-${s.id}-${s.order}`" :class="['plan-step', variantOf(s.status)]">
        <span class="plan-step__icon">{{ iconOf(s.status) }}</span>
        <span class="plan-step__body">
          <span class="plan-step__title">{{ s.title }}</span>
          <span v-if="s.tool" class="plan-step__tool">{{ s.tool }}</span>
          <span v-if="s.status === 'failed' && s.error" class="plan-step__error">{{ s.error }}</span>
        </span>
      </li>
    </ol>
  </div>
</template>

<style scoped>
.plan-timeline {
  margin: 0.5rem 0;
  padding: 0.5rem 0.75rem;
  background: rgba(168, 85, 247, 0.04);
  border: 1px solid rgba(168, 85, 247, 0.22);
  border-radius: 6px;
  font-size: 0.85rem;
}
.plan-timeline__head {
  display: flex;
  align-items: center;
  gap: 0.4rem;
  font-size: 0.78rem;
  color: #d8b4fe;
  margin-bottom: 0.4rem;
  font-weight: 600;
}
.plan-timeline__icon { font-size: 0.9rem; }
.plan-timeline__count {
  font-size: 0.72rem;
  color: #94a3b8;
  margin-left: auto;
}
.plan-timeline__list {
  margin: 0;
  padding: 0;
  list-style: none;
  display: flex;
  flex-direction: column;
  gap: 0.3rem;
}
.plan-step {
  display: flex;
  align-items: flex-start;
  gap: 0.5rem;
  padding: 0.3rem 0.5rem;
  border-radius: 4px;
  background: rgba(168, 85, 247, 0.06);
}
.plan-step__icon {
  font-size: 0.9rem;
  font-weight: 600;
  flex-shrink: 0;
  width: 1.2rem;
  text-align: center;
}
.plan-step-pending .plan-step__icon { color: #64748b; }
.plan-step-running .plan-step__icon {
  color: #c084fc;
  animation: plan-pulse 1.4s linear infinite;
}
.plan-step-completed .plan-step__icon { color: #10b981; }
.plan-step-failed .plan-step__icon { color: #ef4444; }
.plan-step__body {
  display: flex;
  flex-direction: column;
  gap: 0.1rem;
  min-width: 0;
}
.plan-step__title {
  color: #f1f5f9;
  font-size: 0.85rem;
  font-weight: 500;
  word-break: break-word;
}
.plan-step__tool {
  font-size: 0.72rem;
  color: #94a3b8;
  font-family: ui-monospace, SFMono-Regular, Consolas, monospace;
}
.plan-step__error {
  font-size: 0.7rem;
  color: #fca5a5;
  font-family: ui-monospace, SFMono-Regular, Consolas, monospace;
}
@keyframes plan-pulse {
  0%, 100% { opacity: 0.6; }
  50% { opacity: 1; }
}
</style>
