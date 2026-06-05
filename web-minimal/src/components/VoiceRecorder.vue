<template>
  <div class="voice-recorder">
    <div class="recorder-controls">
      <button class="record-btn" :class="{ recording }" @click="toggleRecording">
        <span v-if="recording">⏹️</span>
        <span v-else>🎙️</span>
      </button>
      <div v-if="recording" class="waveform">
        <div v-for="i in 5" :key="i" class="bar" :style="{ animationDelay: `${i * 0.1}s` }"></div>
      </div>
    </div>
    <div v-if="recording" class="recording-info">
      <span class="time">{{ formatTime(recordingTime) }}</span>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'

const emit = defineEmits(['start', 'stop'])

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
    emit('start')
  } else {
    clearInterval(timer)
    emit('stop', { duration: recordingTime.value })
  }
}

const formatTime = (seconds) => {
  const mins = Math.floor(seconds / 60)
  const secs = seconds % 60
  return `${mins}:${secs.toString().padStart(2, '0')}`
}
</script>

<style scoped>
.voice-recorder {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 16px;
  padding: 24px;
}

.recorder-controls {
  display: flex;
  align-items: center;
  gap: 16px;
}

.record-btn {
  width: 64px;
  height: 64px;
  border-radius: var(--radius-full);
  background: var(--color-primary);
  color: white;
  border: none;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 24px;
  transition: all var(--duration-fast) var(--ease-out);
}

.record-btn:hover {
  transform: scale(1.05);
}

.record-btn.recording {
  background: var(--color-danger);
}

.waveform {
  display: flex;
  align-items: center;
  gap: 4px;
  height: 32px;
}

.bar {
  width: 4px;
  height: 100%;
  background: var(--color-danger);
  border-radius: 2px;
  animation: wave 1s ease-in-out infinite;
}

@keyframes wave {
  0%, 100% { transform: scaleY(0.5); }
  50% { transform: scaleY(1); }
}

.recording-info {
  text-align: center;
}

.time {
  font-size: 24px;
  font-weight: 600;
  color: var(--color-text-primary);
}
</style>
