<script setup lang="ts">
/**
 * SplashScreen — Phase 8-M0-H0 启动体验
 * 展示 logo / 版本号 / 启动进度, 主进程 ready-to-show 后 500ms 自动跳转.
 */
import { computed } from 'vue'
import { useAppConfig } from '../composables/use-app-config'
import { APP_DEMO_WARNING } from '../shared/config-types'

const { config, isDemo, appVersion, environment } = useAppConfig()

const envLabel = computed(() => {
  if (isDemo.value) return `${environment.value} · demo`
  return environment.value
})
</script>

<template>
  <main class="splash" data-testid="splash-screen" aria-label="应用启动">
    <div class="splash__brand" aria-hidden="true">
      <svg viewBox="0 0 64 64" width="64" height="64" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <circle cx="32" cy="32" r="22" />
        <circle cx="32" cy="32" r="10" />
        <circle cx="32" cy="32" r="3" fill="currentColor" />
      </svg>
    </div>
    <h1 class="splash__title">{{ config.appName }}</h1>
    <p class="splash__subtitle">科研操作系统 · Scientific Research OS</p>
    <div class="splash__meta" role="status" aria-live="polite">
      <span>v{{ appVersion }}</span>
      <span class="splash__meta-sep">·</span>
      <span>{{ envLabel }}</span>
    </div>
    <p v-if="isDemo" class="splash__demo-warning" data-testid="splash-demo-warning">
      {{ APP_DEMO_WARNING }}
    </p>
    <div class="splash__loader" aria-hidden="true">
      <span class="splash__loader-dot splash__loader-dot--1" />
      <span class="splash__loader-dot splash__loader-dot--2" />
      <span class="splash__loader-dot splash__loader-dot--3" />
    </div>
  </main>
</template>

<style scoped>
.splash {
  display: grid;
  place-items: center;
  gap: var(--research-space-3);
  min-height: 100vh;
  padding: var(--research-page-gutter);
  background: linear-gradient(135deg, var(--research-graphite-950) 0%, var(--research-instrument-900) 100%);
  color: var(--research-instrument-text);
  text-align: center;
}
.splash__brand { color: var(--research-signal-cyan); animation: splash-pulse 2.4s ease-in-out infinite; }
@keyframes splash-pulse {
  0%, 100% { transform: scale(1); opacity: 1; }
  50% { transform: scale(1.06); opacity: 0.85; }
}
.splash__title { margin: 0; font-size: var(--research-text-page-title); font-weight: var(--research-font-weight-bold); }
.splash__subtitle { margin: 0; color: var(--research-instrument-muted); font-size: var(--research-text-body); }
.splash__meta { display: inline-flex; align-items: center; gap: var(--research-space-2); color: var(--research-instrument-muted); font-family: var(--research-font-scientific); font-size: var(--research-text-sm); }
.splash__meta-sep { opacity: 0.4; }
.splash__demo-warning {
  margin: var(--research-space-2) 0 0;
  padding: var(--research-space-2) var(--research-space-3);
  border-radius: var(--research-radius-pill);
  background: var(--research-warning-500);
  color: var(--research-text-inverse);
  font-size: var(--research-text-xs);
  font-weight: var(--research-font-weight-semibold);
}
.splash__loader { display: inline-flex; gap: var(--research-space-2); margin-block-start: var(--research-space-4); }
.splash__loader-dot { width: 8px; height: 8px; border-radius: var(--research-radius-pill); background: var(--research-signal-cyan); animation: splash-bounce 1.2s ease-in-out infinite; }
.splash__loader-dot--2 { animation-delay: 0.15s; }
.splash__loader-dot--3 { animation-delay: 0.3s; }
@keyframes splash-bounce {
  0%, 80%, 100% { transform: translateY(0); opacity: 0.4; }
  40% { transform: translateY(-8px); opacity: 1; }
}
@media (prefers-reduced-motion: reduce) {
  .splash__brand, .splash__loader-dot { animation: none; }
}
</style>
