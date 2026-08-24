<script setup lang="ts">
import { computed } from 'vue'
import type { DeviceStatusPanel as DeviceStatusData } from '../../../../shared/control/experiment-control-schema'

const props = withDefaults(defineProps<{
  devices: DeviceStatusData[]
  variant?: 'research' | 'scada'
}>(), {
  variant: 'research'
})

const deviceTypeLabels: Record<string, string> = {
  reactor: '反应器',
  pump: '泵',
  'ozone-generator': '臭氧发生器',
  sensor: '传感器'
}

const deviceStatusLabels: Record<string, string> = {
  online: '在线',
  connecting: '连接中',
  offline: '离线',
  error: '异常'
}

const deviceTypeLabel = (type: string): string => deviceTypeLabels[type] ?? type
const deviceStatusLabel = (status: string): string => deviceStatusLabels[status] ?? status

const panelClass = computed(() => [
  'device-status-panel',
  `device-status-panel--${props.variant}`
])
</script>

<template>
  <section :class="panelClass" aria-label="设备状态">
    <header class="device-status-panel__header">
      <h2 class="device-status-panel__title">设备状态</h2>
    </header>

    <ul v-if="props.devices.length" class="device-status-panel__list" role="list">
      <li v-for="device in props.devices" :key="device.deviceId" class="device-status-panel__item">
        <div class="device-status-panel__identity">
          <span
            :class="['device-status-panel__signal', `device-status-panel__signal--${device.status}`]"
            aria-hidden="true"
          />
          <div class="device-status-panel__identity-copy">
            <h3 class="device-status-panel__name">{{ device.name }}</h3>
            <p class="device-status-panel__type">{{ deviceTypeLabel(device.type) }}</p>
          </div>
        </div>
        <div class="device-status-panel__meta">
          <span :class="['device-status-panel__status', `is-${device.status}`]" role="status">
            {{ deviceStatusLabel(device.status) }}
          </span>
          <span class="device-status-panel__readings">近期读数 {{ device.recentReadings }}</span>
        </div>
      </li>
    </ul>

    <p v-else class="device-status-panel__empty" role="status">暂无设备状态</p>
  </section>
</template>

<style scoped>
.device-status-panel {
  min-width: 0;
  padding: var(--research-space-5);
  border: 1px solid var(--research-border-subtle);
  border-radius: var(--research-radius-panel);
  background: var(--research-bg-card);
  box-shadow: var(--research-shadow-soft);
}

.device-status-panel--scada {
  border-color: var(--research-instrument-line);
  background: var(--research-instrument-900);
  color: var(--research-instrument-text);
}

.device-status-panel__header { margin-bottom: var(--research-space-4); }

.device-status-panel__title,
.device-status-panel__name,
.device-status-panel__type { margin: 0; }

.device-status-panel__title {
  color: var(--research-text-primary);
  font-size: var(--research-text-section-title);
  font-weight: var(--research-font-weight-semibold);
  line-height: var(--research-line-height-tight);
}

.device-status-panel--scada .device-status-panel__title,
.device-status-panel--scada .device-status-panel__name { color: var(--research-instrument-text); }

.device-status-panel__list {
  display: grid;
  gap: var(--research-space-3);
  margin: 0;
  padding: 0;
  list-style: none;
}

.device-status-panel__item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--research-space-3);
  min-width: 0;
  padding: var(--research-space-3);
  border: 1px solid var(--research-border-subtle);
  border-radius: var(--research-radius-card);
  background: var(--research-bg-panel);
}

.device-status-panel--scada .device-status-panel__item {
  border-color: var(--research-instrument-line);
  background: var(--research-instrument-850);
}

.device-status-panel__identity {
  display: grid;
  grid-template-columns: auto minmax(0, 1fr);
  align-items: center;
  gap: var(--research-space-3);
  min-width: 0;
}

.device-status-panel__signal {
  --device-status-signal: var(--research-border-strong);
  width: var(--research-space-2);
  height: var(--research-space-2);
  border-radius: var(--research-radius-pill);
  background: var(--device-status-signal);
}

.device-status-panel__signal--online { --device-status-signal: var(--research-success-500); }
.device-status-panel__signal--connecting { --device-status-signal: var(--research-warning-500); }
.device-status-panel__signal--error { --device-status-signal: var(--research-danger-500); }

.device-status-panel--scada .device-status-panel__signal--online {
  --device-status-signal: var(--research-signal-green);
  animation: device-status-panel-pulse var(--research-duration-slow) var(--research-ease-standard) infinite;
}

.device-status-panel--scada .device-status-panel__signal--connecting { --device-status-signal: var(--research-signal-amber); }
.device-status-panel--scada .device-status-panel__signal--error { --device-status-signal: var(--research-signal-red); }
.device-status-panel--scada .device-status-panel__signal--offline { --device-status-signal: var(--research-instrument-muted); }

.device-status-panel__identity-copy { min-width: 0; }

.device-status-panel__name {
  color: var(--research-text-primary);
  font-size: var(--research-text-body);
  font-weight: var(--research-font-weight-medium);
  line-height: var(--research-line-height-tight);
  overflow-wrap: anywhere;
}

.device-status-panel__type,
.device-status-panel__readings,
.device-status-panel__empty {
  color: var(--research-text-secondary);
  font-size: var(--research-text-sm);
  line-height: var(--research-line-height-body);
}

.device-status-panel--scada .device-status-panel__type,
.device-status-panel--scada .device-status-panel__readings,
.device-status-panel--scada .device-status-panel__empty { color: var(--research-instrument-muted); }

.device-status-panel__meta {
  display: grid;
  justify-items: end;
  gap: var(--research-space-1);
  flex: 0 0 auto;
  font-size: var(--research-text-xs);
}

.device-status-panel__status { color: var(--research-text-secondary); font-weight: var(--research-font-weight-semibold); }
.device-status-panel__status.is-online { color: var(--research-success-700); }
.device-status-panel__status.is-connecting { color: var(--research-warning-600); }
.device-status-panel__status.is-error { color: var(--research-danger-600); }
.device-status-panel--scada .device-status-panel__status.is-online { color: var(--research-signal-green); }
.device-status-panel--scada .device-status-panel__status.is-connecting { color: var(--research-signal-amber); }
.device-status-panel--scada .device-status-panel__status.is-error { color: var(--research-signal-red); }
.device-status-panel--scada .device-status-panel__status.is-offline { color: var(--research-instrument-muted); }

.device-status-panel__empty { margin: 0; }

@keyframes device-status-panel-pulse {
  50% { opacity: 0.5; }
}

@media (prefers-reduced-motion: reduce) {
  .device-status-panel--scada .device-status-panel__signal--online { animation: none; }
}
</style>
