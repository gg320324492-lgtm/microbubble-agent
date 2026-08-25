<script setup lang="ts">
/**
 * DemoWarningBanner — Phase 8-M0-H0 全局 Demo 警告
 * 演示模式下全局展示, 不可关闭. 明确告知用户当前为演示数据.
 */
import { computed } from 'vue'
import ResearchIcon from '../icons/ResearchIcon.vue'
import { useDemoMode } from '../../composables/use-demo-mode'

const { isDemoMode } = useDemoMode()
const show = computed(() => isDemoMode.value)
</script>

<template>
  <aside
    v-if="show"
    class="demo-warning-banner"
    role="alert"
    aria-live="assertive"
    data-testid="demo-warning-banner"
  >
    <span class="demo-warning-banner__icon" aria-hidden="true">
      <ResearchIcon name="warning" :size="16" />
    </span>
    <span class="demo-warning-banner__text">
      <strong>演示数据 · 非真实实验结果</strong>
      <span class="demo-warning-banner__hint">所有图谱、文献、实验数据均为 O₃-MNBs 演示项目 fixture, 不应作为科研依据。</span>
    </span>
  </aside>
</template>

<style scoped>
.demo-warning-banner {
  position: sticky;
  inset-block-start: 0;
  z-index: var(--research-z-toast, 120);
  display: flex;
  align-items: center;
  gap: var(--research-space-3);
  padding: var(--research-space-2) var(--research-space-4);
  border-block-end: 2px solid var(--research-warning-500);
  background: linear-gradient(90deg, var(--research-warning-50) 0%, var(--research-warning-100) 100%);
  color: var(--research-warning-700);
  font-size: var(--research-text-sm);
}
.demo-warning-banner__icon {
  display: grid;
  width: 32px;
  height: 32px;
  flex: 0 0 32px;
  place-items: center;
  border-radius: var(--research-radius-pill);
  background: var(--research-warning-500);
  color: var(--research-text-inverse);
}
.demo-warning-banner__text { display: grid; gap: 2px; min-width: 0; }
.demo-warning-banner__text strong { font-size: var(--research-text-body); font-weight: var(--research-font-weight-bold); letter-spacing: 0.02em; }
.demo-warning-banner__hint { color: var(--research-warning-600); font-size: var(--research-text-xs); }
@media (max-width: 1480px) {
  .demo-warning-banner__hint { display: none; }
}
@media (prefers-reduced-motion: reduce) {
  .demo-warning-banner { transition: none; }
}
</style>
