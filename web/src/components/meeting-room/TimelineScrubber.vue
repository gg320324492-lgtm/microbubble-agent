<template>
  <div class="timeline-scrubber">
    <span class="time-display">{{ formatTime(currentTs) }}</span>
    <el-slider
      :model-value="currentTs"
      :min="0"
      :max="duration || 1"
      :step="1"
      :format-tooltip="formatTime"
      :show-tooltip="false"
      @change="onJump"
    />
    <span class="time-display">{{ formatTime(duration) }}</span>
  </div>
</template>

<script setup>
const props = defineProps({
  currentTs: { type: Number, default: 0 },
  duration: { type: Number, default: 0 },
})
const emit = defineEmits(['jump'])

function formatTime(seconds) {
  const s = Math.max(0, Math.floor(seconds || 0))
  const m = Math.floor(s / 60)
  const r = s % 60
  return `${m.toString().padStart(2, '0')}:${r.toString().padStart(2, '0')}`
}

function onJump(value) {
  emit('jump', value)
}
</script>

<style scoped>
.timeline-scrubber {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 8px 16px;
  background: rgba(0, 0, 0, 0.3);
}
.time-display { color: white; font-family: monospace; font-size: 12px; }
</style>
