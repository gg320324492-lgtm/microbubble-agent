<script setup lang="ts">
import { computed } from 'vue'
import type { DeviceStatusPanel } from '../../../../shared/control/experiment-control-schema'

const props = withDefaults(defineProps<{ panel: DeviceStatusPanel }>(), {})

const statusColor = computed(() => {
  if (props.panel.status === 'online') return '#10b981'
  if (props.panel.status === 'offline') return '#94a3b8'
  if (props.panel.status === 'error') return '#ef4444'
  if (props.panel.status === 'connecting') return '#f59e0b'
  return '#94a3b8'
})

const statusLabel = computed(() => {
  if (props.panel.status === 'online') return '在线'
  if (props.panel.status === 'offline') return '离线'
  if (props.panel.status === 'error') return '错误'
  if (props.panel.status === 'connecting') return '连接中'
  return props.panel.status
})

const typeLabel = computed(() => {
  if (props.panel.type === 'pump') return '泵'
  if (props.panel.type === 'ozone-generator') return '臭氧发生器'
  if (props.panel.type === 'sensor') return '传感器'
  if (props.panel.type === 'reactor') return '反应器'
  if (props.panel.type === 'controller') return '控制器'
  return props.panel.type
})

const lastSeenLabel = computed(() => {
  const dt = new Date(props.panel.lastSeen)
  return dt.toLocaleTimeString('zh-CN')
})
</script>

<template>
  <div class="device-card" :data-status="panel.status">
    <div class="device-card__head">
      <div class="device-card__name">{{ panel.name }}</div>
      <span class="device-card__status" :style="{ background: statusColor }">{{ statusLabel }}</span>
    </div>
    <div class="device-card__meta">
      <span class="device-card__type">{{ typeLabel }}</span>
      <span class="device-card__count">近期读数: {{ panel.recentReadings }}</span>
    </div>
    <div class="device-card__footer">
      <span class="device-card__time">最近: {{ lastSeenLabel }}</span>
    </div>
  </div>
</template>

<style scoped>
.device-card {
  background: linear-gradient(180deg, rgba(255,255,255,0.95) 0%, rgba(248,250,252,0.95) 100%);
  border: 1px solid rgba(15, 23, 42, 0.08);
  border-radius: 12px;
  padding: 16px;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.04);
  transition: transform 200ms ease, box-shadow 200ms ease;
}
.device-card:hover {
  transform: translateY(-2px);
  box-shadow: 0 8px 24px rgba(15, 23, 42, 0.08);
}
.device-card__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 8px;
}
.device-card__name {
  font-size: 16px;
  font-weight: 600;
  color: #1e293b;
}
.device-card__status {
  font-size: 12px;
  color: white;
  padding: 2px 8px;
  border-radius: 999px;
}
.device-card__meta {
  display: flex;
  gap: 12px;
  font-size: 13px;
  color: #64748b;
  margin-bottom: 8px;
}
.device-card__footer {
  font-size: 12px;
  color: #94a3b8;
  border-top: 1px solid rgba(15, 23, 42, 0.06);
  padding-top: 8px;
}
</style>