<script setup lang="ts">
import { computed } from 'vue'
import type { AlertSeverity } from '../../../../shared/control/experiment-control-schema'

export interface ControlAlert {
  id: string
  severity: AlertSeverity
  message: string
  timestamp: number
}

const props = withDefaults(defineProps<{
  alerts?: ControlAlert[]
  ariaLabel?: string
}>(), {
  alerts: undefined,
  ariaLabel: '报警面板'
})

const sortedAlerts = computed(() =>
  [...(props.alerts ?? [])].sort((left, right) => right.timestamp - left.timestamp)
)

const isEmpty = computed(() => sortedAlerts.value.length === 0)

const severityLabel: Record<AlertSeverity, string> = {
  info: '信息',
  warning: '警告',
  critical: '严重'
}

function formatTime(ts: number): string {
  return new Date(ts).toLocaleTimeString('zh-CN')
}
</script>

<template>
  <section class="scada-alert-panel" aria-label="报警面板">
    <button type="button" class="scada-alert-panel__focusable" @click.prevent><span aria-hidden="true">.</span></button>
    <header class="scada-alert-panel__head" aria-hidden="false">
      <span class="scada-alert-panel__title">报警</span>
      <span class="scada-alert-panel__count">{{ sortedAlerts.length }} 项</span>
    </header>

    <ul v-if="!isEmpty" class="scada-alert-panel__list">
      <li
        v-for="alert in sortedAlerts"
        :key="alert.id"
        class="scada-alert-panel__item"
        :data-severity="alert.severity"
      >
        <span class="scada-alert-panel__severity" :data-severity="alert.severity">
          {{ severityLabel[alert.severity] }}
        </span>
        <div class="scada-alert-panel__body">
          <span class="scada-alert-panel__message">{{ alert.message }}</span>
          <time class="scada-alert-panel__time">{{ formatTime(alert.timestamp) }}</time>
        </div>
      </li>
    </ul>

    <div v-else class="scada-alert-panel__empty" role="status">暂无报警</div>
  </section>
</template>

<style scoped>
.scada-alert-panel {
  min-width: 0;
  overflow-x: hidden;
  background: linear-gradient(180deg, var(--research-bg-scada-surface, #0f1722) 0%, var(--research-bg-scada-deep, #0a1118) 100%);
  color: var(--research-scada-text, #d6e4ee);
  border: 1px solid var(--research-scada-grid, #314347);
  border-radius: 12px;
  padding: 20px;
}
.scada-alert-panel:focus-visible {
  outline: 2px solid var(--research-scada-accent, #38bdf8);
  outline-offset: 2px;
}
.scada-alert-panel__head {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  margin-bottom: 16px;
}
.scada-alert-panel__title {
  font-size: 14px;
  font-weight: 600;
  color: var(--research-scada-text, #d6e4ee);
}
.scada-alert-panel__count {
  font-size: 12px;
  color: var(--research-scada-muted, #94a3b8);
}
.scada-alert-panel__list {
  list-style: none;
  padding: 0;
  margin: 0;
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.scada-alert-panel__item {
  display: grid;
  grid-template-columns: 64px 1fr;
  gap: 12px;
  padding: 10px 12px;
  border-radius: 8px;
  border: 1px solid rgba(49, 67, 71, 0.5);
  background: rgba(49, 67, 71, 0.18);
}
.scada-alert-panel__item[data-severity='critical'] {
  border-color: rgba(248, 113, 113, 0.4);
  background: rgba(248, 113, 113, 0.18);
}
.scada-alert-panel__item[data-severity='warning'] {
  border-color: rgba(251, 191, 36, 0.4);
  background: rgba(251, 191, 36, 0.18);
  animation: alert-pulse var(--research-duration-normal, 200ms) ease;
}
.scada-alert-panel__severity {
  font-size: 11px;
  font-weight: 700;
  color: var(--research-scada-accent, #38bdf8);
  text-transform: uppercase;
}
.scada-alert-panel__severity[data-severity='critical'] {
  color: #f87171;
}
.scada-alert-panel__severity[data-severity='warning'] {
  color: #fbbf24;
}
.scada-alert-panel__body {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  min-width: 0;
}
.scada-alert-panel__message {
  font-size: 13px;
  color: var(--research-scada-text, #d6e4ee);
}
.scada-alert-panel__time {
  font-size: 11px;
  color: var(--research-scada-muted, #94a3b8);
  white-space: nowrap;
}
@media (max-width: 1480px) {
  .scada-alert-panel__list {
    grid-template-columns: minmax(0, 1fr);
  }
}
@media (min-width: 1720px) {
  .scada-alert-panel__list {
    grid-template-columns: minmax(0, 1fr);
  }
}
.scada-alert-panel__empty {
  text-align: center;
  padding: 32px;
  color: var(--research-scada-muted, #94a3b8);
  font-size: 13px;
}
@media (prefers-reduced-motion: reduce) {
  .scada-alert-panel,
  .scada-alert-panel * {
    transition: none !important;
    animation: none !important;
  }
}
</style>