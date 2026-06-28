<template>
  <Transition name="badge-fade">
    <div v-if="visible" class="upload-status-badge" :class="badgeClass" role="status" aria-live="polite">
      <span class="badge-icon" :class="iconClass">
        <span v-if="effectiveOnline" class="dot" />
        <span v-else class="dot dot-offline" />
      </span>
      <span class="badge-text">{{ message }}</span>
      <button v-if="!effectiveOnline && pendingCount > 0" class="badge-action" @click="onManualRetry">
        手动重试
      </button>
    </div>
  </Transition>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  online: { type: Boolean, default: true },
  uploadedCount: { type: Number, default: 0 },
  totalCount: { type: Number, default: 0 },
  pendingCount: { type: Number, default: 0 },
  state: { type: String, default: 'idle' },  // idle/recording/paused/stopped
})

const emit = defineEmits(['manual-retry'])

const effectiveOnline = computed(() => props.online)

const visible = computed(() => {
  // 录音中或刚停止的会议才显示
  if (props.state === 'idle') return false
  return props.totalCount > 0 || props.pendingCount > 0 || !props.online
})

const badgeClass = computed(() => ({
  'is-offline': !props.effectiveOnline,
  'is-uploading': props.effectiveOnline && props.pendingCount > 0,
  'is-complete': props.effectiveOnline && props.pendingCount === 0 && props.totalCount > 0,
}))

const iconClass = computed(() => ({
  'pulse-green': props.effectiveOnline && props.pendingCount === 0,
  'pulse-orange': props.effectiveOnline && props.pendingCount > 0,
  'pulse-red': !props.effectiveOnline,
}))

const message = computed(() => {
  if (!props.effectiveOnline) {
    if (props.totalCount > 0) {
      return `⚠ 网络已断开，录音已暂存本地（${props.totalCount} 片，待联网重传）`
    }
    return '⚠ 网络已断开，录音暂存于本地'
  }
  if (props.pendingCount > 0) {
    return `上传中：${props.uploadedCount} / ${props.totalCount} 片`
  }
  if (props.totalCount > 0) {
    return '✓ 录音已安全保存'
  }
  return '录音中…'
})

function onManualRetry() {
  emit('manual-retry')
}
</script>

<style scoped>
.upload-status-badge {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 8px 14px;
  border-radius: 20px;
  font-size: 13px;
  font-weight: 500;
  background: var(--color-bg-card, #fff);
  box-shadow: var(--shadow-sm, 0 2px 8px rgba(0,0,0,0.08));
  border: 1px solid var(--color-border, #eee);
  color: var(--color-text-primary, #333);
  margin: 12px auto;
  max-width: 90%;
  transition: var(--transition-all-normal);
}

.upload-status-badge.is-offline {
  background: rgba(245, 108, 108, 0.08);
  border-color: rgba(245, 108, 108, 0.3);
  color: var(--color-danger);
}

.upload-status-badge.is-uploading {
  background: rgba(var(--color-accent-rgb), 0.08);
  border-color: rgba(var(--color-accent-rgb), 0.3);
  color: var(--color-warning);
}

.upload-status-badge.is-complete {
  background: rgba(103, 194, 58, 0.08);
  border-color: rgba(103, 194, 58, 0.3);
  color: var(--color-success);
}

.badge-icon {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 18px;
  height: 18px;
}

.dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: var(--color-success);
}

.dot-offline { background: var(--color-danger); }

.pulse-green .dot { animation: pulse 1.5s infinite; }
.pulse-orange .dot { background: var(--color-accent); animation: pulse 1s infinite; }
.pulse-red .dot { background: var(--color-danger); animation: pulse 0.8s infinite; }

.badge-text { flex: 1; }

.badge-action {
  background: var(--color-primary);
  color: var(--color-bg-card);
  border: none;
  border-radius: 14px;
  padding: 4px 12px;
  font-size: 12px;
  cursor: pointer;
  transition: var(--transition-all-fast);
}
.badge-action:hover { background: var(--color-danger); }

/* Transition */
.badge-fade-enter-active,
.badge-fade-leave-active {
  transition: opacity 0.3s, transform 0.3s;
}
.badge-fade-enter-from,
.badge-fade-leave-to {
  opacity: 0;
  transform: translateY(-4px);
}
</style>
