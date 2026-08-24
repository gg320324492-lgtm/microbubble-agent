<script setup lang="ts">
import { computed } from 'vue'
import type { AIRecommendation } from '../../../../shared/control/experiment-control-schema'

const props = withDefaults(defineProps<{ recommendations: AIRecommendation[] }>(), {
  recommendations: () => []
})

const sorted = computed(() => [...props.recommendations].sort((a, b) => b.confidence - a.confidence))

function pct(v: number): string {
  return `${Math.round(v * 100)}%`
}
</script>

<template>
  <div class="ai-advice">
    <div class="ai-advice__title">AI 推荐</div>
    <div v-if="sorted.length === 0" class="ai-advice__empty">当前无需调整</div>
    <div v-for="rec in sorted" :key="rec.id" class="ai-advice__card">
      <div class="ai-advice__head">
        <span class="ai-advice__kind">{{ rec.kind }}</span>
        <span class="ai-advice__conf">{{ pct(rec.confidence) }}</span>
      </div>
      <div class="ai-advice__title-text">{{ rec.title }}</div>
      <div class="ai-advice__rationale">{{ rec.rationale }}</div>
    </div>
  </div>
</template>

<style scoped>
.ai-advice {
  background: linear-gradient(180deg, #ffffff 0%, #fef3ec 100%);
  border: 1px solid rgba(255, 122, 92, 0.2);
  border-radius: 12px;
  padding: 16px;
}
.ai-advice__title {
  font-size: 14px;
  font-weight: 600;
  color: #1e293b;
  margin-bottom: 12px;
}
.ai-advice__empty {
  text-align: center;
  color: #94a3b8;
  padding: 24px;
}
.ai-advice__card {
  background: white;
  border: 1px solid rgba(15, 23, 42, 0.08);
  border-radius: 8px;
  padding: 12px;
  margin-bottom: 8px;
}
.ai-advice__head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 6px;
}
.ai-advice__kind {
  font-size: 11px;
  font-weight: 600;
  color: #FF7A5C;
  background: rgba(255, 122, 92, 0.1);
  padding: 2px 8px;
  border-radius: 999px;
}
.ai-advice__conf {
  font-size: 11px;
  color: #64748b;
}
.ai-advice__title-text {
  font-size: 14px;
  font-weight: 600;
  color: #1e293b;
  margin-bottom: 4px;
}
.ai-advice__rationale {
  font-size: 12px;
  color: #475569;
  line-height: 1.5;
}
</style>