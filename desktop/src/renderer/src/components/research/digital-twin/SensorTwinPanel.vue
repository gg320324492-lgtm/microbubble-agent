<script setup lang="ts">
import { computed } from 'vue'
import type { DeviceStatusPanel } from '../../../../../shared/control/experiment-control-schema'

const props = withDefaults(defineProps<{
  devices?: DeviceStatusPanel[]
  ariaLabel?: string
}>(), {
  devices: undefined,
  ariaLabel: '数字孪生传感器面板'
})

const isEmpty = computed(() => !props.devices || props.devices.length === 0)
const sensors = computed(() => props.devices ?? [])
const statusLabel = computed(() => {
  if (isEmpty.value) return '暂无传感器设备'
  const any = sensors.value[0]
  if (!any) return '暂无传感器设备'
  return any.status === 'online' ? '在线运行' : '已离线'
})
</script>

<template>
  <section
    class="sensor-twin-panel"
    :data-status="sensors[0]?.status ?? 'empty'"
    :aria-label="ariaLabel"
  >
    <header class="sensor-twin-panel__head">
      <span class="sensor-twin-panel__label">传感器孪生</span>
      <span class="sensor-twin-panel__status" :data-online="sensors[0]?.status === 'online' ? 'true' : 'false'">
        {{ statusLabel }}
      </span>
    </header>
    <div v-if="!isEmpty" class="sensor-twin-panel__body">
      <ul class="sensor-twin-panel__list">
        <li v-for="sensor in sensors" :key="sensor.deviceId" class="sensor-twin-panel__item">
          <span class="sensor-twin-panel__name">{{ sensor.name }}</span>
          <span class="sensor-twin-panel__count">{{ sensor.recentReadings }}</span>
        </li>
      </ul>
    </div>
    <div v-else class="sensor-twin-panel__empty" role="status">
      <span>暂无传感器设备</span>
    </div>
  </section>
</template>

<style scoped>
.sensor-twin-panel {
  min-width: 0;
  overflow-x: hidden;
  background: linear-gradient(180deg, var(--research-bg-scada-surface, #0f1722) 0%, var(--research-bg-scada-deep, #0a1118) 100%);
  color: var(--research-scada-text, #d6e4ee);
  border: 1px solid var(--research-scada-grid, #314347);
  border-radius: 12px;
  padding: 16px;
}
.sensor-twin-panel:focus-visible {
  outline: 2px solid var(--research-scada-accent, #38bdf8);
  outline-offset: 2px;
}
.sensor-twin-panel__head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
}
.sensor-twin-panel__label {
  font-size: 11px;
  font-weight: 600;
  color: var(--research-scada-muted, #94a3b8);
  text-transform: uppercase;
  letter-spacing: 0.06em;
}
.sensor-twin-panel__status {
  font-size: 11px;
  padding: 2px 8px;
  border-radius: 999px;
  background: rgba(56, 189, 248, 0.18);
  color: var(--research-scada-accent, #38bdf8);
}
.sensor-twin-panel__status[data-online='false'] {
  background: rgba(148, 163, 184, 0.18);
  color: var(--research-scada-muted, #94a3b8);
}
.sensor-twin-panel__list {
  list-style: none;
  padding: 0;
  margin: 0;
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.sensor-twin-panel__item {
  display: flex;
  justify-content: space-between;
  padding: 6px 0;
  border-top: 1px solid rgba(49, 67, 71, 0.5);
}
.sensor-twin-panel__name {
  font-size: 13px;
  color: var(--research-scada-text, #d6e4ee);
}
.sensor-twin-panel__count {
  font-size: 12px;
  color: var(--research-scada-muted, #94a3b8);
}
.sensor-twin-panel__empty {
  text-align: center;
  padding: 24px;
  color: var(--research-scada-muted, #94a3b8);
  font-size: 13px;
}
@media (max-width: 1480px) { .sensor-twin-panel { flex-basis: 100%; } }
@media (min-width: 1720px) { .sensor-twin-panel { flex-basis: 33%; } }
@media (prefers-reduced-motion: reduce) {
  .sensor-twin-panel, .sensor-twin-panel * { transition: none !important; }
}
</style>