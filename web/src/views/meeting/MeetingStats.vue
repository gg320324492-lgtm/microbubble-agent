<template>
  <div class="meeting-stats">
    <!-- 统计卡片 -->
    <div class="stat-cards">
      <div class="stat-card fade-slide-up">
        <div class="stat-icon">📋</div>
        <div class="stat-body">
          <div class="stat-value">{{ animatedTotal }}</div>
          <div class="stat-label">总会议数</div>
        </div>
      </div>
      <div class="stat-card fade-slide-up" style="animation-delay: 60ms">
        <div class="stat-icon">📅</div>
        <div class="stat-body">
          <div class="stat-value">{{ animatedMonth }}</div>
          <div class="stat-label">本月会议</div>
        </div>
      </div>
      <div class="stat-card fade-slide-up" style="animation-delay: 120ms">
        <div class="stat-icon">🎙️</div>
        <div class="stat-body">
          <div class="stat-value">{{ formatTotalDuration }}</div>
          <div class="stat-label">总录音时长</div>
        </div>
      </div>
    </div>

    <div class="stats-body">
      <!-- 最近会议 -->
      <el-card class="stats-card">
        <template #header><span>最近会议</span></template>
        <div v-if="recentMeetings.length === 0" class="empty-hint">暂无会议</div>
        <div v-else class="timeline">
          <div
            v-for="(m, idx) in recentMeetings"
            :key="m.id"
            class="timeline-item fade-slide-up"
            :style="{ animationDelay: (idx * 60) + 'ms' }"
          >
            <div class="timeline-dot" :class="'dot-' + m.status" />
            <div class="timeline-content">
              <router-link :to="`/meetings/${m.id}`" class="timeline-title">{{ m.title }}</router-link>
              <div class="timeline-meta">
                <span>{{ formatDate(m.start_time) }}</span>
                <el-tag :type="statusType(m.status)" size="small">{{ statusLabel(m.status) }}</el-tag>
              </div>
            </div>
          </div>
        </div>
      </el-card>

      <!-- 发言活跃度排行 -->
      <el-card class="stats-card">
        <template #header><span>发言活跃度排行</span></template>
        <SpeakerStatsCard :stats="topSpeakers" />
        <div v-if="topSpeakers.length === 0" class="empty-hint">暂无发言数据</div>
      </el-card>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import axios from 'axios'
import dayjs from 'dayjs'
import SpeakerStatsCard from '@/components/SpeakerStatsCard.vue'

const allMeetings = ref([])

// ===== 统计数据 =====

const totalMeetings = computed(() => allMeetings.value.length)

const monthMeetings = computed(() => {
  const now = dayjs()
  return allMeetings.value.filter(m => dayjs(m.start_time).isSame(now, 'month')).length
})

const totalDuration = computed(() => {
  return allMeetings.value.reduce((sum, m) => sum + (m.audio_duration || 0), 0)
})

const formatTotalDuration = computed(() => {
  const sec = totalDuration.value
  if (sec === 0) return '0'
  if (sec < 60) return `${sec}秒`
  if (sec < 3600) return `${Math.floor(sec / 60)}分`
  const h = Math.floor(sec / 3600)
  const m = Math.floor((sec % 3600) / 60)
  return m > 0 ? `${h}时${m}分` : `${h}时`
})

const recentMeetings = computed(() => {
  return [...allMeetings.value]
    .sort((a, b) => new Date(b.start_time) - new Date(a.start_time))
    .slice(0, 5)
})

// 聚合发言统计
const topSpeakers = computed(() => {
  const map = {}
  for (const m of allMeetings.value) {
    if (!m.speaker_stats?.length) continue
    for (const s of m.speaker_stats) {
      if (!map[s.name]) {
        map[s.name] = { name: s.name, turn_count: 0, word_count: 0, speaking_ratio: 0, meeting_count: 0 }
      }
      map[s.name].turn_count += s.turn_count || 0
      map[s.name].word_count += s.word_count || 0
      map[s.name].meeting_count++
    }
  }
  const list = Object.values(map).sort((a, b) => b.turn_count - a.turn_count)
  // 计算总发言次数占比
  const total = list.reduce((s, x) => s + x.turn_count, 0) || 1
  list.forEach(s => { s.speaking_ratio = s.turn_count / total })
  return list.slice(0, 8)
})

// ===== 数字动画 =====

const animatedTotal = ref(0)
const animatedMonth = ref(0)

function animateCounter(targetRef, target, duration = 600) {
  const start = 0
  const startTime = performance.now()
  function update(now) {
    const elapsed = now - startTime
    const progress = Math.min(elapsed / duration, 1)
    const eased = 1 - Math.pow(1 - progress, 3)
    targetRef.value = Math.round(eased * target)
    if (progress < 1) requestAnimationFrame(update)
  }
  requestAnimationFrame(update)
}

// ===== 辅助函数 =====

const formatDate = (d) => dayjs(d).add(8, 'hour').format('MM/DD HH:mm')
const statusLabel = (s) => ({ scheduled: '已预约', recording: '录制中', processing: '处理中', completed: '已完成', cancelled: '已取消', error: '处理失败' }[s] || s)
const statusType = (s) => ({ scheduled: 'info', recording: 'warning', processing: 'warning', completed: 'success', cancelled: 'info', error: 'danger' }[s] || 'info')

// ===== 数据加载 =====

onMounted(async () => {
  try {
    const res = await axios.get('/api/v1/meetings', { params: { page_size: 100 } })
    allMeetings.value = res.data.items || []
    animateCounter(animatedTotal, totalMeetings.value)
    animateCounter(animatedMonth, monthMeetings.value)
  } catch (e) {
    console.error('加载会议统计失败:', e)
  }
})
</script>

<style scoped>
.meeting-stats {
  display: flex;
  flex-direction: column;
  gap: 16px;
  padding: 16px 20px;
  height: 100%;
  overflow-y: auto;
}

/* ====== 统计卡片 ====== */
.stat-cards {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 12px;
}

.stat-card {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 20px;
  background: #fff;
  border-radius: var(--radius-lg, 12px);
  border: 1px solid var(--color-border, #ebeef5);
  transition: all 0.2s;
}
.stat-card:hover {
  box-shadow: var(--shadow-md);
  transform: translateY(-2px);
}

.stat-icon {
  font-size: 32px;
  line-height: 1;
}

.stat-value {
  font-size: 28px;
  font-weight: 700;
  color: var(--color-text-primary, #2d2d2d);
  line-height: 1.2;
}

.stat-label {
  font-size: 13px;
  color: var(--color-text-secondary, #909399);
  margin-top: 2px;
}

/* ====== 内容区 ====== */
.stats-body {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16px;
}

.stats-card {
  border-radius: var(--radius-lg, 12px);
}
.stats-card :deep(.el-card__header) {
  font-weight: 600;
  font-size: 15px;
}

/* ====== 时间线 ====== */
.timeline {
  display: flex;
  flex-direction: column;
  gap: 0;
}

.timeline-item {
  display: flex;
  gap: 12px;
  padding: 12px 0;
  border-bottom: 1px solid var(--color-border, #ebeef5);
}
.timeline-item:last-child { border-bottom: none; }

.timeline-dot {
  width: 10px;
  height: 10px;
  border-radius: 50%;
  flex-shrink: 0;
  margin-top: 5px;
}
.dot-scheduled { background: #909399; }
.dot-recording { background: #FF7A5C; animation: dot-pulse 1.2s infinite; }
.dot-processing { background: #E6A23C; animation: dot-pulse 1.5s infinite; }
.dot-completed { background: #67C23A; }
.dot-cancelled { background: #909399; opacity: 0.5; }
.dot-error { background: #F56C6C; }

@keyframes dot-pulse {
  0%, 100% { opacity: 1; scale: 1; }
  50% { opacity: 0.5; scale: 1.4; }
}

.timeline-content { flex: 1; }
.timeline-title {
  font-size: 14px;
  font-weight: 500;
  color: var(--color-primary, #FF7A5C);
  text-decoration: none;
}
.timeline-title:hover { text-decoration: underline; }
.timeline-meta {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-top: 4px;
  font-size: 12px;
  color: var(--color-text-secondary, #909399);
}

.empty-hint {
  text-align: center;
  padding: 24px;
  color: var(--color-text-placeholder, #c0c4cc);
  font-size: 14px;
}

/* ====== 入场动画 ====== */
.fade-slide-up {
  animation: fadeSlideUp 300ms ease-out both;
}
@keyframes fadeSlideUp {
  from { opacity: 0; transform: translateY(12px); }
  to { opacity: 1; transform: translateY(0); }
}

/* ====== 响应式 ====== */
@media (max-width: 768px) {
  .stat-cards { grid-template-columns: 1fr; }
  .stats-body { grid-template-columns: 1fr; }
}
</style>
