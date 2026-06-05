<template>
  <div v-if="visible" class="dialog-overlay">
    <div class="dialog">
      <div class="dialog-header">
        <h3>{{ title }}</h3>
      </div>
      <div class="dialog-body">
        <div class="progress-container">
          <div class="progress-bar">
            <div class="progress-fill" :style="{ width: progress + '%' }"></div>
          </div>
          <span class="progress-text">{{ progress }}%</span>
        </div>
        <div class="status-text">{{ statusText }}</div>
      </div>
    </div>
  </div>
</template>

<script setup>
defineProps({
  visible: {
    type: Boolean,
    default: false
  },
  title: {
    type: String,
    default: '处理中...'
  },
  progress: {
    type: Number,
    default: 0
  },
  statusText: {
    type: String,
    default: '请稍候...'
  }
})
</script>

<style scoped>
.dialog-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.5);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
}

.dialog {
  background: white;
  border-radius: var(--radius-lg);
  width: 100%;
  max-width: 400px;
  padding: 32px;
}

.dialog-header {
  margin-bottom: 24px;
}

.dialog-header h3 {
  font-size: 18px;
  font-weight: 600;
  color: var(--color-text-primary);
}

.progress-container {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 16px;
}

.progress-bar {
  flex: 1;
  height: 8px;
  background: var(--color-bg-active);
  border-radius: 4px;
  overflow: hidden;
}

.progress-fill {
  height: 100%;
  background: var(--color-primary);
  border-radius: 4px;
  transition: width var(--duration-normal) var(--ease-out);
}

.progress-text {
  font-size: 14px;
  font-weight: 600;
  color: var(--color-text-primary);
  min-width: 40px;
  text-align: right;
}

.status-text {
  font-size: 14px;
  color: var(--color-text-secondary);
}
</style>
