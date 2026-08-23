<script setup lang="ts">
/**
 * Loading 占位 —— 骨架屏 / 旋转 spinner。
 * 不引 Element Plus el-skeleton。
 */
import { computed } from 'vue'
import ResearchIcon from '../icons/ResearchIcon.vue'

interface Props {
  variant?: 'spinner' | 'skeleton'
  text?: string
  message?: string
  rows?: number
}
const props = withDefaults(defineProps<Props>(), { variant: 'spinner', rows: 3 })

const displayText = computed(() => props.text ?? props.message ?? 'AI 正在分析...')
</script>

<template>
  <div v-if="variant === 'spinner'" class="ui-loading ui-loading--spinner" role="status" aria-busy="true">
    <ResearchIcon class="ui-spinner" name="running" :size="28" />
    <p class="ui-loading__text">{{ displayText }}</p>
  </div>
  <div v-else class="ui-loading ui-loading--skeleton">
    <div v-for="i in rows" :key="i" class="ui-skeleton" :style="{ width: 70 - i * 5 + '%' }" />
  </div>
</template>

<style scoped>
.ui-loading {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: var(--research-space-8) var(--research-space-4);
  color: var(--research-text-secondary);
  font-size: var(--research-text-sm);
}
.ui-loading--skeleton {
  align-items: stretch;
  gap: var(--research-space-3);
}
.ui-loading__text {
  margin: var(--research-space-2) 0 0;
}
.ui-spinner {
  color: var(--research-ai-600);
  animation: ui-spin calc(var(--research-duration-slow) + var(--research-duration-slow) + var(--research-duration-fast)) var(--research-ease-linear) infinite;
}
@keyframes ui-spin {
  to { transform: rotate(360deg); }
}
.ui-skeleton {
  height: 14px;
  background: linear-gradient(90deg, var(--research-bg-hover) 0%, var(--research-border-subtle) 50%, var(--research-bg-hover) 100%);
  background-size: 200% 100%;
  border-radius: var(--research-radius-input);
  animation: ui-shimmer calc(var(--research-duration-slow) + var(--research-duration-slow) + var(--research-duration-slow) + var(--research-duration-slow)) var(--research-ease-standard) infinite;
}
@keyframes ui-shimmer {
  0% { background-position: 200% 0; }
  100% { background-position: -200% 0; }
}
</style>
