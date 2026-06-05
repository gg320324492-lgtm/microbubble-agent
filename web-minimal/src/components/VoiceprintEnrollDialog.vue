<template>
  <div v-if="visible" class="dialog-overlay" @click.self="$emit('close')">
    <div class="dialog">
      <div class="dialog-header">
        <h3>录入声纹</h3>
        <button class="btn btn-ghost" @click="$emit('close')">✕</button>
      </div>
      <div class="dialog-body">
        <div class="step-indicator">
          <div v-for="step in 3" :key="step" class="step" :class="{ active: currentStep >= step }">
            {{ step }}
          </div>
        </div>
        <div v-if="currentStep === 1" class="step-content">
          <p>请朗读以下文字：</p>
          <div class="text-to-read">微纳米气泡是未来水处理技术的重要方向</div>
          <button class="btn btn-primary" @click="nextStep">开始录音</button>
        </div>
        <div v-if="currentStep === 2" class="step-content">
          <div class="recording-indicator">
            <div class="pulse"></div>
            <span>录音中...</span>
          </div>
          <button class="btn btn-secondary" @click="nextStep">完成录音</button>
        </div>
        <div v-if="currentStep === 3" class="step-content">
          <div class="success-icon">✅</div>
          <p>声纹录入成功！</p>
          <button class="btn btn-primary" @click="$emit('close')">完成</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'

defineProps({
  visible: {
    type: Boolean,
    default: false
  }
})

defineEmits(['close', 'enrolled'])

const currentStep = ref(1)

const nextStep = () => {
  if (currentStep.value < 3) {
    currentStep.value++
  }
}
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
  overflow: hidden;
}

.dialog-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 20px 24px;
  border-bottom: 1px solid var(--color-border);
}

.dialog-header h3 {
  font-size: 18px;
  font-weight: 600;
  color: var(--color-text-primary);
}

.dialog-body {
  padding: 24px;
}

.step-indicator {
  display: flex;
  justify-content: center;
  gap: 24px;
  margin-bottom: 32px;
}

.step {
  width: 36px;
  height: 36px;
  border-radius: var(--radius-full);
  background: var(--color-bg-active);
  color: var(--color-text-tertiary);
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: 600;
}

.step.active {
  background: var(--color-primary);
  color: white;
}

.step-content {
  text-align: center;
}

.step-content p {
  font-size: 14px;
  color: var(--color-text-secondary);
  margin-bottom: 16px;
}

.text-to-read {
  background: var(--color-bg-page);
  padding: 16px;
  border-radius: var(--radius-md);
  font-size: 16px;
  color: var(--color-text-primary);
  margin-bottom: 24px;
}

.recording-indicator {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 12px;
  margin-bottom: 24px;
}

.pulse {
  width: 12px;
  height: 12px;
  border-radius: var(--radius-full);
  background: var(--color-danger);
  animation: pulse 1.5s infinite;
}

@keyframes pulse {
  0%, 100% { opacity: 1; transform: scale(1); }
  50% { opacity: 0.5; transform: scale(1.2); }
}

.success-icon {
  font-size: 48px;
  margin-bottom: 16px;
}
</style>
