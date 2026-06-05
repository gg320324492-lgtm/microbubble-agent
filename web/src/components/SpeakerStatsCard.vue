<template>
  <div class="speaker-stats-card">
    <div
      v-for="(speaker, idx) in stats"
      :key="speaker.name || idx"
      class="speaker-row fade-slide-up"
      :style="{ animationDelay: (idx * 60) + 'ms' }"
    >
      <el-tooltip :content="speaker.name" placement="top" :show-after="300">
        <el-avatar :size="32" :src="getAvatar(speaker.name)" class="speaker-avatar">
          {{ (speaker.name || '?')[0] }}
        </el-avatar>
      </el-tooltip>

      <div class="speaker-info">
        <div class="speaker-name-row">
          <span class="speaker-name">{{ speaker.name || '未知' }}</span>
          <span class="speaker-pct">{{ Math.round((speaker.speaking_ratio || 0) * 100) }}%</span>
        </div>
        <div class="progress-track">
          <div
            class="progress-fill"
            :style="{ width: Math.round((speaker.speaking_ratio || 0) * 100) + '%' }"
          />
        </div>
        <div class="speaker-meta">
          <span>{{ speaker.turn_count || 0 }} 次发言</span>
          <span class="meta-dot">·</span>
          <span>{{ formatWordCount(speaker.word_count) }}</span>
        </div>
      </div>
    </div>

    <el-empty v-if="!stats?.length" description="暂无发言统计" :image-size="60" />
  </div>
</template>

<script setup>
import { useMemberStore } from '@/stores/member'

const props = defineProps({
  stats: { type: Array, default: () => [] },
})

const memberStore = useMemberStore()

function getAvatar(name) {
  if (!name) return null
  const member = memberStore.members.find(m => m.name === name)
  return member?.avatar || null
}

function formatWordCount(count) {
  if (!count) return '0 字'
  if (count >= 1000) return (count / 1000).toFixed(1) + 'k 字'
  return count + ' 字'
}
</script>

<style scoped>
.speaker-stats-card {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.speaker-row {
  display: flex;
  align-items: center;
  gap: 12px;
}

.speaker-avatar {
  flex-shrink: 0;
  border: 2px solid #fff;
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.08);
}

.speaker-info {
  flex: 1;
  min-width: 0;
}

.speaker-name-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 4px;
}

.speaker-name {
  font-size: 14px;
  font-weight: 600;
  color: var(--color-text-primary, #2d2d2d);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.speaker-pct {
  font-size: 13px;
  font-weight: 600;
  color: var(--color-primary, #FF7A5C);
  flex-shrink: 0;
  margin-left: 8px;
}

.progress-track {
  height: 8px;
  background: var(--color-bg-page, #f5f7fa);
  border-radius: 4px;
  overflow: hidden;
  margin-bottom: 4px;
}

.progress-fill {
  height: 100%;
  background: linear-gradient(90deg, #FF7A5C, #FFB347);
  border-radius: 4px;
  transition: width 0.6s ease-out;
  min-width: 2px;
}

.speaker-meta {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 12px;
  color: var(--color-text-secondary, #909399);
}

.meta-dot {
  color: var(--color-text-placeholder, #c0c4cc);
}

/* 入场动画 */
.fade-slide-up {
  animation: fadeSlideUp 300ms ease-out both;
}

@keyframes fadeSlideUp {
  from { opacity: 0; transform: translateY(8px); }
  to { opacity: 1; transform: translateY(0); }
}
</style>
