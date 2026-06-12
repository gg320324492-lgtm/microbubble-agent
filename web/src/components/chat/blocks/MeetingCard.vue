<script setup>
/**
 * MeetingCard.vue — 会议卡片（单次/详情/列表项通用）
 *
 * 接收 block.data，包含字段（来自后端 query_meetings / get_meeting_detail / get_recent_meeting_conclusions）：
 * - 单个会议: {id, title, start_time, status, summary, key_points_count, decisions_count,
 *              agenda_summary, participants, location, audio_url, task_count}
 * - 列表: {meetings: [...]} 或 {groups: [...]}
 */
import { computed } from 'vue'
import { useRouter } from 'vue-router'

const props = defineProps({ block: { type: Object, required: true } })
const router = useRouter()

// 兼容多种数据格式
const meetings = computed(() => {
  const d = props.block.data || {}
  if (Array.isArray(d.meetings)) return d.meetings
  if (Array.isArray(d.groups)) return d.groups
  if (d.id && d.title) return [d]  // 单个会议
  return []
})

const formatDate = (dt) => {
  if (!dt) return ''
  try {
    return new Date(dt).toLocaleString('zh-CN', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' })
  } catch { return dt }
}

const goToMeeting = (id) => {
  if (id) router.push(`/meetings/${id}`)
}

const statusColor = (s) => {
  const map = { completed: '#67c23a', scheduled: '#909399', recording: '#f56c6c', processing: '#e6a23c' }
  return map[s] || '#909399'
}

const statusLabel = (s) => {
  const map = { completed: '已完成', scheduled: '已排期', recording: '录音中', processing: '处理中' }
  return map[s] || s
}
</script>

<template>
  <div class="meeting-card rich-card">
    <div class="card-header">
      <span class="icon">📅</span>
      <span class="title">{{ block.title || '会议列表' }} ({{ meetings.length }})</span>
    </div>
    <div v-for="m in meetings" :key="m.id || m.meeting_id" class="meeting-item" @click="goToMeeting(m.id || m.meeting_id)">
      <div class="meeting-title">
        <span class="status-dot" :style="{ background: statusColor(m.status) }" />
        {{ m.title }}
      </div>
      <div class="meeting-meta">
        <span class="time">{{ formatDate(m.start_time) }}</span>
        <span v-if="m.location" class="location">📍 {{ m.location }}</span>
        <span v-if="m.status" class="status" :style="{ color: statusColor(m.status) }">{{ statusLabel(m.status) }}</span>
      </div>
      <div v-if="m.summary" class="meeting-summary">{{ m.summary.slice(0, 100) }}{{ m.summary.length > 100 ? '...' : '' }}</div>
      <div v-if="m.agenda_summary" class="meeting-agenda">📋 {{ m.agenda_summary }}</div>
      <div class="meeting-stats">
        <span v-if="m.key_points_count || m.key_points?.length" class="stat">💡 {{ m.key_points_count ?? m.key_points.length }} 要点</span>
        <span v-if="m.decisions_count || m.decisions?.length" class="stat">✅ {{ m.decisions_count ?? m.decisions.length }} 决议</span>
        <span v-if="m.task_count" class="stat">📝 {{ m.task_count }} 任务</span>
        <span v-if="m.audio_url" class="stat audio">🎙️ 有录音</span>
      </div>
      <div v-if="m.participants && m.participants.length" class="meeting-participants">
        <span v-for="p in m.participants.slice(0, 5)" :key="p.id" class="participant">{{ p.name }}</span>
        <span v-if="m.participants.length > 5" class="more">+{{ m.participants.length - 5 }}</span>
      </div>
    </div>
    <div v-if="!meetings.length" class="empty">暂无会议</div>
  </div>
</template>

<style scoped>
.rich-card {
  background: white;
  border: 1px solid #e8eaed;
  border-radius: 10px;
  padding: 12px 14px;
  margin: 8px 0;
  box-shadow: 0 1px 2px rgba(0,0,0,0.04);
}
.card-header {
  display: flex; align-items: center; gap: 8px;
  font-weight: 600; font-size: 14px;
  margin-bottom: 10px; color: #FF7A5C;
}
.icon { font-size: 18px; }
.meeting-item {
  padding: 10px 0;
  border-top: 1px solid #f0f1f3;
  cursor: pointer;
  transition: background 0.15s;
}
.meeting-item:first-of-type { border-top: none; }
.meeting-item:hover { background: #fafbfc; margin: 0 -8px; padding: 10px 8px; border-radius: 6px; }
.meeting-title { font-weight: 500; font-size: 14px; display: flex; align-items: center; gap: 6px; }
.status-dot { width: 8px; height: 8px; border-radius: 50%; flex-shrink: 0; }
.meeting-meta { display: flex; gap: 12px; font-size: 12px; color: #999; margin-top: 4px; flex-wrap: wrap; }
.meeting-summary { font-size: 13px; color: #555; margin-top: 6px; line-height: 1.5; }
.meeting-agenda { font-size: 12px; color: #666; margin-top: 4px; }
.meeting-stats { display: flex; gap: 8px; margin-top: 6px; flex-wrap: wrap; }
.stat {
  font-size: 11px;
  background: #f0f4f8;
  padding: 2px 8px;
  border-radius: 10px;
  color: #555;
}
.stat.audio { background: #fff7e6; color: #d4880f; }
.meeting-participants { display: flex; gap: 4px; margin-top: 6px; flex-wrap: wrap; }
.participant {
  font-size: 11px;
  background: #e8f4ff;
  color: #1976d2;
  padding: 2px 8px;
  border-radius: 10px;
}
.more { font-size: 11px; color: #999; padding: 2px 4px; }
.empty { text-align: center; color: #999; padding: 20px 0; font-size: 13px; }
</style>
