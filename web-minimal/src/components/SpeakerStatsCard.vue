<template>
  <div class="speaker-stats-card">
    <h4>{{ speakerName }}</h4>
    <div class="stats">
      <div class="stat">
        <span class="stat-value">{{ stats.segments }}</span>
        <span class="stat-label">发言次数</span>
      </div>
      <div class="stat">
        <span class="stat-value">{{ formatDuration(stats.duration) }}</span>
        <span class="stat-label">发言时长</span>
      </div>
      <div class="stat">
        <span class="stat-value">{{ stats.percentage }}%</span>
        <span class="stat-label">占比</span>
      </div>
    </div>
  </div>
</template>

<script setup>
defineProps({
  speakerName: {
    type: String,
    default: ''
  },
  stats: {
    type: Object,
    default: () => ({
      segments: 0,
      duration: 0,
      percentage: 0
    })
  }
})

const formatDuration = (seconds) => {
  if (!seconds) return '0秒'
  const mins = Math.floor(seconds / 60)
  const secs = Math.floor(seconds % 60)
  if (mins > 0) return `${mins}分${secs}秒`
  return `${secs}秒`
}
</script>

<style scoped>
.speaker-stats-card {
  background: white;
  border-radius: var(--radius-lg);
  padding: 20px;
  border: 1px solid var(--color-border);
}

.speaker-stats-card h4 {
  font-size: 16px;
  font-weight: 600;
  color: var(--color-text-primary);
  margin-bottom: 16px;
}

.stats {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 12px;
}

.stat {
  text-align: center;
}

.stat-value {
  display: block;
  font-size: 20px;
  font-weight: 700;
  color: var(--color-text-primary);
  margin-bottom: 4px;
}

.stat-label {
  font-size: 12px;
  color: var(--color-text-tertiary);
}
</style>
