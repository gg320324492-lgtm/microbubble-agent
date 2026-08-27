<script setup lang="ts">
import { computed } from 'vue'
import type { DeviceStatusPanel } from '../../../../../shared/control/experiment-control-schema'

const props = withDefaults(defineProps<{
  device?: DeviceStatusPanel
  ariaLabel?: string
}>(), {
  device: undefined,
  ariaLabel: '数字孪生反应器面板'
})

const isOnline = computed(() => props.device?.status === 'online')
const statusLabel = computed(() => {
  if (!props.device) return '暂无反应器设备'
  if (props.device.status === 'online') return '在线运行'
  if (props.device.status === 'offline') return '已离线'
  if (props.device.status === 'error') return '错误'
  return props.device.status
})
const recentReadings = computed(() => props.device?.recentReadings ?? 0)
</script>

<template>
  <section
    class="reactor-twin-panel"
    :data-status="device?.status ?? 'empty'"
    :aria-label="ariaLabel"
  >
    <header class="reactor-twin-panel__head">
      <span class="reactor-twin-panel__label">反应器孪生</span>
      <span
        class="reactor-twin-panel__status"
        :data-online="isOnline ? 'true' : 'false'"
      >{{ statusLabel }}</span>
    </header>
    <div v-if="device" class="reactor-twin-panel__body">
      <div class="reactor-twin-panel__name">{{ device.name }}</div>
      <div class="reactor-twin-panel__row">
        <span class="reactor-twin-panel__metric-label">类型</span>
        <span class="reactor-twin-panel__metric-value">反应器</span>
      </div>
      <div class="reactor-twin-panel__row">
        <span class="reactor-twin-panel__metric-label">近期读数</span>
        <span class="reactor-twin-panel__metric-value">{{ recentReadings }}</span>
      </div>
    </div>
    <div v-else class="reactor-twin-panel__empty" role="status">
      <span>暂无反应器设备</span>
    </div>
  </section>
</template>

<style scoped>
.reactor-twin-panel {
  min-width: 0;
  overflow-x: hidden;
  background: linear-gradient(180deg, var(--research-bg-scada-surface, #0f1722) 0%, var(--research-bg-scada-deep, #0a1118) 100%);
  color: var(--research-scada-text, #d6e4ee);
  border: 1px solid var(--research-scada-grid, #314347);
  border-radius: 12px;
  padding: 16px;
  transition: transform var(--research-duration-fast, 200ms) ease, box-shadow var(--research-duration-fast, 200ms) ease;
}
.reactor-twin-panel:hover {
  transform: translateY(-2px);
  box-shadow: 0 0 24px rgba(56, 189, 248, 0.18);
}
.reactor-twin-panel:focus-visible {
  outline: 2px solid var(--research-scada-accent, #38bdf8);
  outline-offset: 2px;
}
.reactor-twin-panel__head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
}
.reactor-twin-panel__label {
  font-size: 11px;
  font-weight: 600;
  color: var(--research-scada-muted, #94a3b8);
  text-transform: uppercase;
  letter-spacing: 0.06em;
}
.reactor-twin-panel__status {
  font-size: 11px;
  padding: 2px 8px;
  border-radius: 999px;
  background: rgba(56, 189, 248, 0.18);
  color: var(--research-scada-accent, #38bdf8);
}
.reactor-twin-panel__status[data-online='false'] {
  background: rgba(148, 163, 184, 0.18);
  color: var(--research-scada-muted, #94a3b8);
}
.reactor-twin-panel__name {
  font-size: 16px;
  font-weight: 600;
  color: var(--research-scada-text, #d6e4ee);
  margin-bottom: 12px;
}
.reactor-twin-panel__row {
  display: flex;
  justify-content: space-between;
  padding: 6px 0;
  border-top: 1px solid rgba(49, 67, 71, 0.5);
}
.reactor-twin-panel__metric-label {
  font-size: 12px;
  color: var(--research-scada-muted, #94a3b8);
}
.reactor-twin-panel__metric-value {
  font-size: 13px;
  font-weight: 600;
  color: var(--research-scada-text, #d6e4ee);
}
.reactor-twin-panel__empty {
  text-align: center;
  padding: 24px;
  color: var(--research-scada-muted, #94a3b8);
  font-size: 13px;
}
@media (max-width: 1480px) { .twin-panel-grid { grid-template-columns: minmax(0, 1fr); } }
@media (min-width: 1720px) { .twin-panel-grid { grid-template-columns: minmax(0, 1fr); } }
@media (prefers-reduced-motion: reduce) {
  .reactor-twin-panel,
  .reactor-twin-panel * {
    transition: none !important;
  }
}
</style>