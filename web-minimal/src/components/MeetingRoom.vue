<template>
  <div class="meeting-room">
    <div class="room-header">
      <h3>{{ meeting.title }}</h3>
      <div class="room-controls">
        <button class="control-btn" :class="{ active: muted }" @click="muted = !muted">
          {{ muted ? '🔇' : '🔊' }}
        </button>
        <button class="control-btn danger" @click="$emit('leave')">
          📞
        </button>
      </div>
    </div>
    <div class="room-body">
      <div class="participants-grid">
        <div v-for="p in participants" :key="p.id" class="participant-tile" :class="{ speaking: p.speaking }">
          <div class="participant-avatar">
            {{ p.name.charAt(0) }}
          </div>
          <span class="participant-name">{{ p.name }}</span>
        </div>
      </div>
      <div class="transcript-area">
        <div v-for="(msg, index) in transcript" :key="index" class="transcript-item">
          <span class="speaker">{{ msg.speaker }}:</span>
          <span class="text">{{ msg.text }}</span>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'

defineProps({
  meeting: {
    type: Object,
    default: () => ({})
  },
  participants: {
    type: Array,
    default: () => []
  },
  transcript: {
    type: Array,
    default: () => []
  }
})

defineEmits(['leave'])

const muted = ref(false)
</script>

<style scoped>
.meeting-room {
  background: white;
  border-radius: var(--radius-lg);
  border: 1px solid var(--color-border);
  overflow: hidden;
}

.room-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16px 24px;
  border-bottom: 1px solid var(--color-border);
}

.room-header h3 {
  font-size: 16px;
  font-weight: 600;
  color: var(--color-text-primary);
}

.room-controls {
  display: flex;
  gap: 8px;
}

.control-btn {
  width: 40px;
  height: 40px;
  border-radius: var(--radius-full);
  background: var(--color-bg-page);
  border: none;
  cursor: pointer;
  font-size: 18px;
  transition: all var(--duration-fast) var(--ease-out);
}

.control-btn:hover {
  background: var(--color-bg-active);
}

.control-btn.active {
  background: var(--color-danger-bg);
}

.control-btn.danger {
  background: var(--color-danger);
  color: white;
}

.room-body {
  padding: 24px;
}

.participants-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(100px, 1fr));
  gap: 16px;
  margin-bottom: 24px;
}

.participant-tile {
  text-align: center;
  padding: 16px;
  border-radius: var(--radius-md);
  border: 2px solid transparent;
  transition: all var(--duration-fast) var(--ease-out);
}

.participant-tile.speaking {
  border-color: var(--color-primary);
  background: var(--color-primary-bg);
}

.participant-avatar {
  width: 48px;
  height: 48px;
  border-radius: var(--radius-full);
  background: linear-gradient(135deg, var(--color-accent), #FFB347);
  color: white;
  font-size: 20px;
  font-weight: 600;
  display: flex;
  align-items: center;
  justify-content: center;
  margin: 0 auto 8px;
}

.participant-name {
  font-size: 12px;
  color: var(--color-text-secondary);
}

.transcript-area {
  max-height: 200px;
  overflow-y: auto;
  background: var(--color-bg-page);
  border-radius: var(--radius-md);
  padding: 16px;
}

.transcript-item {
  margin-bottom: 8px;
  font-size: 14px;
  line-height: 1.6;
}

.transcript-item:last-child {
  margin-bottom: 0;
}

.speaker {
  font-weight: 600;
  color: var(--color-primary);
  margin-right: 8px;
}

.text {
  color: var(--color-text-secondary);
}
</style>
