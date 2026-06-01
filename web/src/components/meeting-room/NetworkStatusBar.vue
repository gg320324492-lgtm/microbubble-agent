<template>
  <div class="network-bar" :class="status">
    <span v-if="status === 'offline'">● 已离线，{{ pendingCount }} 块缓冲中</span>
    <span v-else-if="status === 'weak'">● 弱网（{{ effectiveType }}），{{ pendingCount }} 块缓冲中</span>
    <span v-else>● 已连接</span>
  </div>
</template>

<script setup>
import { useNetworkStatus } from '@/composables/useNetworkStatus'

const { status, effectiveType, pendingCount, setPendingCount } = useNetworkStatus()

// 暴露给父组件用于注入 pending count
defineExpose({ setPendingCount })
</script>

<style scoped>
.network-bar {
  padding: 4px 16px;
  font-size: 12px;
  background: transparent;
  color: #999;
  text-align: center;
  transition: all 0.3s;
}
.network-bar.offline { background: #f56c6c; color: white; }
.network-bar.weak { background: #e6a23c; color: white; }
</style>
