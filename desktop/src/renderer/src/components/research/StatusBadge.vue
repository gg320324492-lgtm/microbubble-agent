<script setup lang="ts">
/**
 * 状态徽章。
 */
defineProps<{
  status: 'success' | 'warning' | 'error' | 'info' | 'neutral'
  label: string
}>()

</script>

<template>
  <span :class="['status-badge', `status-badge--${status}`]" :style="{ background: 'var(--status-badge-bg)' }">
    {{ label }}
  </span>
</template>

<style scoped>
.status-badge { --status-badge-bg: var(--research-bg-hover); display: inline-flex; align-items: center; min-height: 22px; font-size: var(--research-text-xs); font-weight: var(--research-font-weight-medium); padding: var(--research-space-1) var(--research-space-2); border-radius: var(--research-radius-pill); white-space: nowrap; color: var(--research-text-secondary); }
.status-badge--success { --status-badge-bg: var(--research-success-50); color: var(--research-success-700); }
.status-badge--warning { --status-badge-bg: var(--research-warning-50); color: var(--research-text-primary); }
.status-badge--error { --status-badge-bg: var(--research-danger-50); color: var(--research-danger-600); }
.status-badge--info { --status-badge-bg: var(--research-primary-50); color: var(--research-primary-700); }
</style>
