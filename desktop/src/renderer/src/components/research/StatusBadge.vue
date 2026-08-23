<script setup lang="ts">
/**
 * 状态徽章。
 */
defineProps<{
  status: 'success' | 'warning' | 'error' | 'info' | 'neutral'
  label: string
}>()

const STYLE: Record<string, { bg: string; color: string }> = {
  success: { bg: '#dcfce7', color: '#166534' },
  warning: { bg: '#fef3c7', color: '#92400e' },
  error:   { bg: '#fee2e2', color: '#991b1b' },
  info:    { bg: '#dbeafe', color: '#1e40af' },
  neutral: { bg: '#f1f5f9', color: '#475569' }
}
</script>

<template>
  <span class="status-badge" :style="{ background: STYLE[status].bg, color: STYLE[status].color }">
    {{ label }}
  </span>
</template>

<style scoped>
.status-badge { font-size: 11px; font-weight: 500; padding: 2px 8px; border-radius: 4px; white-space: nowrap; }
</style>
