<template>
  <div class="participant-avatars">
    <span
      v-for="(participant, index) in displayedParticipants"
      :key="participant.id"
      class="avatar"
      :style="{ zIndex: maxDisplay - index }"
    >
      {{ participant.name.charAt(0) }}
    </span>
    <span v-if="remainingCount > 0" class="avatar more">
      +{{ remainingCount }}
    </span>
  </div>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  participants: {
    type: Array,
    default: () => []
  },
  maxDisplay: {
    type: Number,
    default: 3
  }
})

const displayedParticipants = computed(() => {
  return props.participants.slice(0, props.maxDisplay)
})

const remainingCount = computed(() => {
  return Math.max(0, props.participants.length - props.maxDisplay)
})
</script>

<style scoped>
.participant-avatars {
  display: flex;
  align-items: center;
}

.avatar {
  width: 32px;
  height: 32px;
  border-radius: var(--radius-full);
  background: linear-gradient(135deg, var(--color-accent), #FFB347);
  color: white;
  font-size: 12px;
  font-weight: 600;
  display: flex;
  align-items: center;
  justify-content: center;
  margin-left: -8px;
  border: 2px solid white;
  position: relative;
}

.avatar:first-child {
  margin-left: 0;
}

.avatar.more {
  background: var(--color-bg-active);
  color: var(--color-text-secondary);
  font-size: 11px;
}
</style>
