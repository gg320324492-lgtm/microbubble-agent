<template>
  <div class="audio-player">
    <button class="play-btn" @click="togglePlay">
      <span v-if="playing">⏸️</span>
      <span v-else>▶️</span>
    </button>
    <div class="progress-bar" @click="seek">
      <div class="progress-fill" :style="{ width: progress + '%' }"></div>
    </div>
    <span class="time">{{ formatTime(currentTime) }} / {{ formatTime(duration) }}</span>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'

const props = defineProps({
  src: {
    type: String,
    default: ''
  }
})

const playing = ref(false)
const currentTime = ref(0)
const duration = ref(0)
const audio = ref(null)

const progress = computed(() => {
  if (!duration.value) return 0
  return (currentTime.value / duration.value) * 100
})

const togglePlay = () => {
  playing.value = !playing.value
}

const seek = (e) => {
  // TODO: 实现跳转
}

const formatTime = (seconds) => {
  const mins = Math.floor(seconds / 60)
  const secs = Math.floor(seconds % 60)
  return `${mins}:${secs.toString().padStart(2, '0')}`
}
</script>

<style scoped>
.audio-player {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px;
  background: var(--color-bg-page);
  border-radius: var(--radius-md);
}

.play-btn {
  width: 40px;
  height: 40px;
  border-radius: var(--radius-full);
  background: var(--color-primary);
  color: white;
  border: none;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 16px;
  transition: all var(--duration-fast) var(--ease-out);
}

.play-btn:hover {
  transform: scale(1.05);
}

.progress-bar {
  flex: 1;
  height: 4px;
  background: var(--color-border);
  border-radius: 2px;
  cursor: pointer;
}

.progress-fill {
  height: 100%;
  background: var(--color-primary);
  border-radius: 2px;
  transition: width var(--duration-fast) var(--ease-out);
}

.time {
  font-size: 12px;
  color: var(--color-text-tertiary);
  white-space: nowrap;
}
</style>
