<template>
  <div class="audio-recorder">
    <button class="record-btn" :class="{ recording }" @click="toggleRecording">
      <span v-if="recording">⏹️</span>
      <span v-else>🎙️</span>
    </button>
    <span v-if="recording" class="recording-time">{{ formatTime(recordingTime) }}</span>
    <span v-else class="hint">点击开始录音</span>
  </div>
</template>

<script setup>
import { ref } from 'vue'

const emit = defineEmits(['recorded'])

const recording = ref(false)
const recordingTime = ref(0)
let timer = null

const toggleRecording = () => {
  recording.value = !recording.value
  if (recording.value) {
    recordingTime.value = 0
    timer = setInterval(() => {
      recordingTime.value++
    }, 1000)
  } else {
    clearInterval(timer)
    emit('recorded', { duration: recordingTime.value })
  }
}

const formatTime = (seconds) => {
  const mins = Math.floor(seconds / 60)
  const secs = seconds % 60
  return `${mins}:${secs.toString().padStart(2, '0')}`
}
</script>

<style scoped>
.audio-recorder {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 16px;
  background: var(--color-bg-page);
  border-radius: var(--radius-md);
}

.record-btn {
  width: 48px;
  height: 48px;
  border-radius: var(--radius-full);
  background: var(--color-primary);
  color: white;
  border: none;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 20px;
  transition: all var(--duration-fast) var(--ease-out);
}

.record-btn:hover {
  transform: scale(1.05);
}

.record-btn.recording {
  background: var(--color-danger);
  animation: pulse 1.5s infinite;
}

@keyframes pulse {
  0%, 100% { transform: scale(1); }
  50% { transform: scale(1.1); }
}

.recording-time {
  font-size: 18px;
  font-weight: 600;
  color: var(--color-danger);
}

.hint {
  font-size: 14px;
  color: var(--color-text-tertiary);
}
</style>
