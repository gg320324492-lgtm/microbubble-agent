<template>
  <div class="meeting-list">
    <div v-for="group in groupedMeetings" :key="group.date" class="date-group">
      <div class="date-label">{{ group.date }}</div>
      <div v-for="meeting in group.meetings" :key="meeting.id" class="meeting-item">
        <div class="meeting-time">
          <div class="time">{{ meeting.time }}</div>
        </div>
        <div class="meeting-content">
          <div class="meeting-title">{{ meeting.title }}</div>
          <div class="meeting-meta">
            <span class="meeting-tag" :style="{ color: getStatusColor(meeting.status) }">
              {{ getStatusLabel(meeting.status) }}
            </span>
            <span class="meeting-location">📍 {{ meeting.location }}</span>
          </div>
        </div>
        <div class="meeting-participants">
          <div class="participant-avatars">
            <span v-for="p in meeting.participants.slice(0, 3)" :key="p" class="participant-avatar">
              {{ p.charAt(0) }}
            </span>
          </div>
          <span v-if="meeting.participants.length > 3" class="participant-count">
            +{{ meeting.participants.length - 3 }}
          </span>
        </div>
        <div class="meeting-actions">
          <button class="btn btn-ghost btn-small" @click="$emit('view', meeting)">详情</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
defineProps({
  groupedMeetings: {
    type: Array,
    default: () => []
  }
})

defineEmits(['view'])

const getStatusLabel = (status) => {
  const labels = {
    upcoming: '即将开始',
    live: '进行中',
    ended: '已结束'
  }
  return labels[status] || status
}

const getStatusColor = (status) => {
  const colors = {
    upcoming: '#3b82f6',
    live: '#ef4444',
    ended: '#10b981'
  }
  return colors[status] || '#666666'
}
</script>

<style scoped>
.meeting-list {
  display: flex;
  flex-direction: column;
}

.date-group {
  padding: 16px 24px 8px;
  background: var(--color-bg-page);
  border-bottom: 1px solid var(--color-border);
}

.date-label {
  font-size: 13px;
  font-weight: 600;
  color: var(--color-text-secondary);
}

.meeting-item {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 16px 24px;
  border-bottom: 1px solid var(--color-border);
  transition: all var(--duration-fast) var(--ease-out);
}

.meeting-item:last-child {
  border-bottom: none;
}

.meeting-item:hover {
  background: var(--color-bg-hover);
}

.meeting-time {
  width: 60px;
  text-align: center;
  flex-shrink: 0;
}

.meeting-time .time {
  font-size: 16px;
  font-weight: 600;
  color: var(--color-text-primary);
}

.meeting-content {
  flex: 1;
}

.meeting-title {
  font-size: 14px;
  font-weight: 500;
  color: var(--color-text-primary);
  margin-bottom: 4px;
}

.meeting-meta {
  display: flex;
  gap: 12px;
  align-items: center;
}

.meeting-tag {
  font-size: 12px;
  font-weight: 500;
}

.meeting-location {
  font-size: 12px;
  color: var(--color-text-tertiary);
}

.meeting-participants {
  display: flex;
  align-items: center;
  gap: 8px;
}

.participant-avatars {
  display: flex;
}

.participant-avatar {
  width: 28px;
  height: 28px;
  border-radius: var(--radius-full);
  background: var(--color-primary);
  color: white;
  font-size: 10px;
  display: flex;
  align-items: center;
  justify-content: center;
  margin-left: -8px;
  border: 2px solid white;
}

.participant-avatar:first-child {
  margin-left: 0;
}

.participant-count {
  font-size: 12px;
  color: var(--color-text-tertiary);
}

.meeting-actions {
  display: flex;
  gap: 8px;
  opacity: 0;
  transition: opacity var(--duration-fast) var(--ease-out);
}

.meeting-item:hover .meeting-actions {
  opacity: 1;
}
</style>
