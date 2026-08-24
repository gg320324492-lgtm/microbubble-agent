<script setup lang="ts">
withDefaults(defineProps<{
  label: string
  tone?: 'default' | 'success' | 'warning' | 'danger' | 'ai' | 'scada'
}>(), { tone: 'default' })
</script>

<template>
  <span :class="['research-status-badge', `research-status-badge--${tone}`]" role="status" aria-live="polite">
    <span class="research-status-badge__dot" aria-hidden="true" />
    {{ label }}
  </span>
</template>

<style scoped>
.research-status-badge { --badge-color: var(--research-text-secondary); --badge-bg: var(--research-bg-hover); display: inline-flex; min-height: 24px; align-items: center; gap: var(--research-space-2); padding: var(--research-space-1) var(--research-space-2); border-radius: var(--research-radius-pill); background: var(--badge-bg); color: var(--badge-color); font-size: var(--research-text-xs); font-weight: var(--research-font-weight-medium); white-space: nowrap; }
.research-status-badge__dot { width: 6px; height: 6px; border-radius: 50%; background: currentColor; }
.research-status-badge--success { --badge-color: var(--research-success-700); --badge-bg: var(--research-success-50); }
.research-status-badge--warning { --badge-color: var(--research-warning-600); --badge-bg: var(--research-warning-50); }
.research-status-badge--danger { --badge-color: var(--research-danger-600); --badge-bg: var(--research-danger-50); }
.research-status-badge--ai { --badge-color: var(--research-ai-700); --badge-bg: var(--research-ai-50); }
.research-status-badge--scada { --badge-color: var(--research-signal-green); --badge-bg: rgb(126 214 173 / 12%); }
</style>
