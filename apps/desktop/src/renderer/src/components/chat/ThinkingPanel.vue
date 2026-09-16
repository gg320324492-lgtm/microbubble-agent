<script setup lang="ts">
// thinking 折叠面板 — 思维链独立展示，默认折叠，绝不混入正文
import { ref } from 'vue'

defineProps<{ text: string; streaming?: boolean }>()

const expanded = ref(false)
</script>

<template>
  <div class="think" data-testid="thinking-panel">
    <button class="think-head" :aria-expanded="expanded" data-testid="thinking-toggle" @click="expanded = !expanded">
      <span class="chevron" aria-hidden="true">{{ expanded ? '▾' : '▸' }}</span>
      思考过程
      <span v-if="streaming" class="dot" aria-hidden="true"></span>
    </button>
    <pre v-if="expanded" class="think-body" data-testid="thinking-content">{{ text }}</pre>
  </div>
</template>

<style scoped>
.think {
  margin: var(--space-2) 0;
  border: 1px dashed var(--color-border);
  border-radius: var(--radius-md);
  background: var(--color-bg-secondary);
}
.think-head {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  width: 100%;
  padding: var(--space-2) var(--space-3);
  border: none;
  background: transparent;
  cursor: pointer;
  font-size: var(--font-size-xs);
  color: var(--color-text-secondary);
}
.think-head:hover {
  color: var(--color-text-regular);
}
.chevron {
  color: var(--color-text-placeholder);
}
.dot {
  width: 6px;
  height: 6px;
  border-radius: var(--radius-full);
  background: var(--color-primary);
  animation: thinkPulse 1.2s ease-in-out infinite;
}
@keyframes thinkPulse {
  50% {
    opacity: 0.3;
  }
}
.think-body {
  margin: 0;
  padding: var(--space-2) var(--space-3) var(--space-3);
  max-height: 260px;
  overflow: auto;
  border-top: 1px dashed var(--color-border-light);
  font-family: inherit;
  font-size: var(--font-size-xs);
  line-height: 1.7;
  color: var(--color-text-secondary);
  white-space: pre-wrap;
  word-break: break-word;
}
</style>
