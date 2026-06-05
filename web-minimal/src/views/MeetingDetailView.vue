<template>
  <div class="meeting-detail-view">
    <header class="header">
      <div class="header-left">
        <button class="btn btn-ghost" @click="$router.back()">← 返回</button>
        <h2>会议详情</h2>
      </div>
      <div class="header-right">
        <button class="btn btn-primary">开始会议</button>
      </div>
    </header>

    <div class="meeting-info">
      <div class="meeting-header">
        <h1>{{ meeting.title }}</h1>
        <span class="tag" :class="meeting.status">{{ meeting.status }}</span>
      </div>
      <div class="meeting-meta">
        <span>📅 {{ meeting.date }}</span>
        <span>⏰ {{ meeting.time }}</span>
        <span>📍 {{ meeting.location }}</span>
      </div>
      <p class="meeting-description">{{ meeting.description }}</p>
    </div>

    <div class="meeting-participants">
      <h3>参与者</h3>
      <div class="participant-list">
        <div v-for="p in meeting.participants" :key="p" class="participant">
          <div class="participant-avatar">{{ p.charAt(0) }}</div>
          <span>{{ p }}</span>
        </div>
      </div>
    </div>

    <div class="meeting-agenda">
      <h3>议程</h3>
      <div class="agenda-list">
        <div v-for="(item, index) in meeting.agenda" :key="index" class="agenda-item">
          <span class="agenda-number">{{ index + 1 }}</span>
          <span>{{ item }}</span>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'

const meeting = ref({
  title: '周会 - 项目进度汇报',
  status: 'upcoming',
  date: '2026年6月5日',
  time: '14:00 - 15:00',
  location: '会议室 A',
  description: '本周项目进度汇报，讨论遇到的问题和下周计划',
  participants: ['张三', '李四', '王五', '赵六'],
  agenda: [
    '上周工作总结',
    '本周工作计划',
    '问题讨论',
    '下周安排'
  ]
})
</script>

<style scoped>
.meeting-detail-view {
  display: flex;
  flex-direction: column;
  gap: 32px;
}

.header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.header-left {
  display: flex;
  align-items: center;
  gap: 16px;
}

.header-left h2 {
  font-size: 24px;
  font-weight: 600;
  color: var(--color-text-primary);
}

.meeting-info {
  background: white;
  border-radius: var(--radius-lg);
  padding: 32px;
  border: 1px solid var(--color-border);
}

.meeting-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 16px;
}

.meeting-header h1 {
  font-size: 28px;
  font-weight: 700;
  color: var(--color-text-primary);
}

.tag {
  padding: 6px 14px;
  border-radius: var(--radius-full);
  font-size: 13px;
  font-weight: 500;
}

.tag.upcoming {
  background: var(--color-info-bg);
  color: var(--color-info);
}

.tag.live {
  background: var(--color-danger-bg);
  color: var(--color-danger);
}

.tag.ended {
  background: var(--color-success-bg);
  color: var(--color-success);
}

.meeting-meta {
  display: flex;
  gap: 24px;
  margin-bottom: 16px;
  font-size: 14px;
  color: var(--color-text-secondary);
}

.meeting-description {
  font-size: 15px;
  color: var(--color-text-secondary);
  line-height: 1.6;
}

.meeting-participants,
.meeting-agenda {
  background: white;
  border-radius: var(--radius-lg);
  padding: 24px;
  border: 1px solid var(--color-border);
}

.meeting-participants h3,
.meeting-agenda h3 {
  font-size: 18px;
  font-weight: 600;
  color: var(--color-text-primary);
  margin-bottom: 16px;
}

.participant-list {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
}

.participant {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 16px;
  background: var(--color-bg-page);
  border-radius: var(--radius-full);
}

.participant-avatar {
  width: 32px;
  height: 32px;
  border-radius: var(--radius-full);
  background: var(--color-primary);
  color: white;
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: 600;
}

.agenda-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.agenda-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px 16px;
  background: var(--color-bg-page);
  border-radius: var(--radius-md);
}

.agenda-number {
  width: 28px;
  height: 28px;
  border-radius: var(--radius-full);
  background: var(--color-primary);
  color: white;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 14px;
  font-weight: 600;
}
</style>
