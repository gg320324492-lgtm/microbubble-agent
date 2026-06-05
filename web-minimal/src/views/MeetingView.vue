<template>
  <div class="meeting-view">
    <!-- 头部 -->
    <header class="header">
      <div class="header-left">
        <h2>会议管理</h2>
        <p>管理团队会议，记录会议内容</p>
      </div>
      <div class="header-right">
        <div class="view-toggle">
          <button
            class="view-btn"
            :class="{ active: viewMode === 'list' }"
            @click="viewMode = 'list'"
          >
            列表
          </button>
          <button
            class="view-btn"
            :class="{ active: viewMode === 'calendar' }"
            @click="viewMode = 'calendar'"
          >
            日历
          </button>
        </div>
        <button class="btn btn-primary" @click="showCreateDialog = true">➕ 新建会议</button>
      </div>
    </header>

    <!-- 会议状态卡片 -->
    <section class="status-cards">
      <div class="status-card">
        <div class="status-icon">📅</div>
        <div class="status-value">{{ meetingStats.today }}</div>
        <div class="status-label">今日会议</div>
      </div>
      <div class="status-card">
        <div class="status-icon">🔴</div>
        <div class="status-value">{{ meetingStats.live }}</div>
        <div class="status-label">进行中</div>
      </div>
      <div class="status-card">
        <div class="status-icon">✅</div>
        <div class="status-value">{{ meetingStats.past }}</div>
        <div class="status-label">已完成</div>
      </div>
    </section>

    <!-- 日历视图 -->
    <section v-if="viewMode === 'calendar'" class="calendar-view">
      <div class="calendar-header">
        <div class="calendar-title">{{ currentMonth }}</div>
        <div class="calendar-nav">
          <button @click="prevMonth">←</button>
          <button @click="goToToday">今天</button>
          <button @click="nextMonth">→</button>
        </div>
      </div>
      <div class="calendar-grid">
        <div class="calendar-day-header">日</div>
        <div class="calendar-day-header">一</div>
        <div class="calendar-day-header">二</div>
        <div class="calendar-day-header">三</div>
        <div class="calendar-day-header">四</div>
        <div class="calendar-day-header">五</div>
        <div class="calendar-day-header">六</div>
        <div
          v-for="(day, index) in calendarDays"
          :key="index"
          class="calendar-day"
          :class="{
            'other-month': !day.currentMonth,
            'today': day.isToday,
            'has-meeting': day.hasMeeting
          }"
          @click="selectDate(day)"
        >
          {{ day.date }}
        </div>
      </div>
    </section>

    <!-- 会议列表 -->
    <section class="meeting-list">
      <div class="meeting-list-header">
        <div class="meeting-list-title">会议列表</div>
        <div class="meeting-list-actions">
          <button class="btn btn-ghost btn-small">筛选</button>
          <button class="btn btn-ghost btn-small">排序</button>
        </div>
      </div>

      <div v-if="loading" class="loading">
        <div v-for="i in 3" :key="i" class="meeting-item skeleton">
          <div class="skeleton-circle" style="width: 60px; height: 60px"></div>
          <div class="skeleton-content">
            <div class="skeleton-text" style="width: 60%"></div>
            <div class="skeleton-text" style="width: 40%"></div>
          </div>
        </div>
      </div>

      <div v-else-if="groupedByDate.length === 0" class="empty-state">
        <div class="icon">📅</div>
        <p>暂无会议</p>
        <button class="btn btn-secondary" @click="showCreateDialog = true">创建第一个会议</button>
      </div>

      <div v-else>
        <div v-for="group in groupedByDate" :key="group.date" class="date-group">
          <div class="date-label" :class="{ today: isToday(group.date) }">
            {{ formatGroupDate(group.date) }}
          </div>
          <div
            v-for="meeting in group.meetings"
            :key="meeting.id"
            class="meeting-item"
            @click="goToMeeting(meeting)"
          >
            <div class="meeting-time">
              <div class="time">{{ formatMeetingTime(meeting.start_time) }}</div>
            </div>
            <div class="meeting-divider" :class="getMeetingTypeClass(meeting)"></div>
            <div class="meeting-content">
              <div class="meeting-title">{{ meeting.title }}</div>
              <div class="meeting-meta">
                <span
                  class="meeting-tag"
                  :style="{ color: getMeetingStatusColor(meeting) }"
                >
                  {{ getMeetingStatus(meeting) }}
                </span>
                <span class="meeting-location">📍 {{ meeting.location || '线上会议' }}</span>
              </div>
            </div>
            <div class="meeting-participants">
              <div class="participant-avatars">
                <span
                  v-for="p in (meeting.participants || []).slice(0, 3)"
                  :key="p"
                  class="participant-avatar"
                >
                  {{ getParticipantInitial(p) }}
                </span>
              </div>
              <span v-if="(meeting.participants || []).length > 3" class="participant-count">
                +{{ meeting.participants.length - 3 }}
              </span>
            </div>
            <div class="meeting-actions">
              <button
                v-if="meeting.status === 'upcoming'"
                class="btn btn-primary btn-small"
                @click.stop="handleStartMeeting(meeting)"
              >
                开始
              </button>
              <button
                v-if="meeting.status === 'live'"
                class="btn btn-danger btn-small"
                @click.stop="handleEndMeeting(meeting)"
              >
                结束
              </button>
              <button
                class="btn btn-ghost btn-small"
                @click.stop="goToMeeting(meeting)"
              >
                详情
              </button>
            </div>
          </div>
        </div>
      </div>
    </section>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useMeeting } from '@/composables/useMeeting'
import { useMemberStore } from '@/stores/member'
import dayjs from 'dayjs'

const router = useRouter()
const {
  loading,
  stats: meetingStats,
  groupedByDate,
  fetchMeetings,
  startMeeting,
  endMeeting,
  getParticipantInitial,
  formatMeetingTime,
  getMeetingStatus,
  getMeetingStatusColor
} = useMeeting()

const memberStore = useMemberStore()
const showCreateDialog = ref(false)
const viewMode = ref('list')
const currentDate = ref(dayjs())

const currentMonth = computed(() => {
  return currentDate.value.format('YYYY年M月')
})

const calendarDays = computed(() => {
  const startOfMonth = currentDate.value.startOf('month')
  const endOfMonth = currentDate.value.endOf('month')
  const startDay = startOfMonth.day()
  const daysInMonth = endOfMonth.date()

  const days = []

  // 上个月的日期
  for (let i = startDay - 1; i >= 0; i--) {
    const date = startOfMonth.subtract(i + 1, 'day')
    days.push({
      date: date.date(),
      fullDate: date.format('YYYY-MM-DD'),
      currentMonth: false,
      isToday: date.isSame(dayjs(), 'day'),
      hasMeeting: false
    })
  }

  // 本月的日期
  for (let i = 1; i <= daysInMonth; i++) {
    const date = startOfMonth.add(i - 1, 'day')
    days.push({
      date: i,
      fullDate: date.format('YYYY-MM-DD'),
      currentMonth: true,
      isToday: date.isSame(dayjs(), 'day'),
      hasMeeting: false // TODO: 检查是否有会议
    })
  }

  // 下个月的日期
  const remaining = 42 - days.length
  for (let i = 1; i <= remaining; i++) {
    const date = endOfMonth.add(i, 'day')
    days.push({
      date: i,
      fullDate: date.format('YYYY-MM-DD'),
      currentMonth: false,
      isToday: date.isSame(dayjs(), 'day'),
      hasMeeting: false
    })
  }

  return days
})

const isToday = (date) => {
  return dayjs(date).isSame(dayjs(), 'day')
}

const formatGroupDate = (date) => {
  const d = dayjs(date)
  const now = dayjs()

  if (d.isSame(now, 'day')) {
    return `今天 · ${d.format('M月D日 dddd')}`
  } else if (d.isSame(now.add(1, 'day'), 'day')) {
    return `明天 · ${d.format('M月D日 dddd')}`
  } else if (d.isSame(now.subtract(1, 'day'), 'day')) {
    return `昨天 · ${d.format('M月D日 dddd')}`
  } else {
    return d.format('M月D日 dddd')
  }
}

const getMeetingTypeClass = (meeting) => {
  if (meeting.type === 'interview') return 'interview'
  return 'default'
}

const prevMonth = () => {
  currentDate.value = currentDate.value.subtract(1, 'month')
}

const nextMonth = () => {
  currentDate.value = currentDate.value.add(1, 'month')
}

const goToToday = () => {
  currentDate.value = dayjs()
}

const selectDate = (day) => {
  // TODO: 筛选该日期的会议
  console.log('选择日期:', day.fullDate)
}

const goToMeeting = (meeting) => {
  router.push(`/meetings/${meeting.id}`)
}

const handleStartMeeting = async (meeting) => {
  await startMeeting(meeting.id)
}

const handleEndMeeting = async (meeting) => {
  if (confirm('确定要结束这个会议吗？')) {
    await endMeeting(meeting.id)
  }
}

onMounted(() => {
  fetchMeetings()
  memberStore.fetchMembers()
})
</script>

<style scoped>
.meeting-view {
  display: flex;
  flex-direction: column;
  gap: 24px;
}

/* 头部 */
.header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.header-left h2 {
  font-size: 24px;
  font-weight: 600;
  color: var(--color-text-primary);
}

.header-left p {
  font-size: 14px;
  color: var(--color-text-tertiary);
  margin-top: 4px;
}

.header-right {
  display: flex;
  align-items: center;
  gap: 16px;
}

.view-toggle {
  display: flex;
  background: var(--color-bg-active);
  border-radius: var(--radius-md);
  padding: 4px;
}

.view-btn {
  padding: 8px 16px;
  border-radius: var(--radius-sm);
  font-size: 13px;
  font-weight: 500;
  cursor: pointer;
  transition: all var(--duration-fast) var(--ease-out);
  background: none;
  border: none;
  color: var(--color-text-secondary);
}

.view-btn.active {
  background: white;
  color: var(--color-text-primary);
  box-shadow: var(--shadow-xs);
}

/* 状态卡片 */
.status-cards {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 20px;
}

.status-card {
  background: white;
  border-radius: var(--radius-lg);
  padding: 24px;
  border: 1px solid var(--color-border);
  text-align: center;
}

.status-icon {
  font-size: 32px;
  margin-bottom: 12px;
}

.status-value {
  font-size: 28px;
  font-weight: 700;
  color: var(--color-text-primary);
  margin-bottom: 4px;
}

.status-label {
  font-size: 13px;
  color: var(--color-text-tertiary);
}

/* 日历视图 */
.calendar-view {
  background: white;
  border-radius: var(--radius-lg);
  border: 1px solid var(--color-border);
  padding: 24px;
}

.calendar-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 24px;
}

.calendar-title {
  font-size: 18px;
  font-weight: 600;
  color: var(--color-text-primary);
}

.calendar-nav {
  display: flex;
  gap: 8px;
}

.calendar-nav button {
  padding: 8px 12px;
  border-radius: var(--radius-sm);
  background: var(--color-bg-hover);
  border: none;
  cursor: pointer;
  transition: all var(--duration-fast) var(--ease-out);
}

.calendar-nav button:hover {
  background: var(--color-bg-active);
}

.calendar-grid {
  display: grid;
  grid-template-columns: repeat(7, 1fr);
  gap: 4px;
}

.calendar-day-header {
  text-align: center;
  font-size: 12px;
  font-weight: 600;
  color: var(--color-text-tertiary);
  padding: 8px;
}

.calendar-day {
  text-align: center;
  padding: 12px 8px;
  border-radius: var(--radius-sm);
  cursor: pointer;
  transition: all var(--duration-fast) var(--ease-out);
  font-size: 14px;
}

.calendar-day:hover {
  background: var(--color-bg-hover);
}

.calendar-day.today {
  background: var(--color-primary);
  color: white;
}

.calendar-day.has-meeting {
  position: relative;
}

.calendar-day.has-meeting::after {
  content: '';
  position: absolute;
  bottom: 4px;
  left: 50%;
  transform: translateX(-50%);
  width: 6px;
  height: 6px;
  border-radius: var(--radius-full);
  background: var(--color-accent);
}

.calendar-day.other-month {
  color: var(--color-text-placeholder);
}

/* 会议列表 */
.meeting-list {
  background: white;
  border-radius: var(--radius-lg);
  border: 1px solid var(--color-border);
  overflow: hidden;
}

.meeting-list-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 20px 24px;
  border-bottom: 1px solid var(--color-border);
}

.meeting-list-title {
  font-size: 16px;
  font-weight: 600;
  color: var(--color-text-primary);
}

.meeting-list-actions {
  display: flex;
  gap: 12px;
}

/* 日期分组 */
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

.date-label.today {
  color: var(--color-text-primary);
}

/* 会议项 */
.meeting-item {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 16px 24px;
  border-bottom: 1px solid var(--color-border);
  transition: all var(--duration-fast) var(--ease-out);
  cursor: pointer;
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

.meeting-divider {
  width: 3px;
  height: 48px;
  border-radius: 2px;
  flex-shrink: 0;
}

.meeting-divider.default {
  background: var(--color-primary);
}

.meeting-divider.interview {
  background: var(--color-success);
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

/* 空状态 */
.empty-state {
  text-align: center;
  padding: 48px 24px;
  color: var(--color-text-tertiary);
}

.empty-state .icon {
  font-size: 48px;
  margin-bottom: 16px;
}

.empty-state p {
  font-size: 14px;
  margin-bottom: 16px;
}

/* 加载状态 */
.loading {
  padding: 24px;
}

/* 响应式 */
@media (max-width: 1024px) {
  .status-cards {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 768px) {
  .header {
    flex-direction: column;
    align-items: flex-start;
    gap: 16px;
  }

  .header-right {
    width: 100%;
    justify-content: space-between;
  }

  .meeting-item {
    flex-wrap: wrap;
  }

  .meeting-actions {
    opacity: 1;
    width: 100%;
    justify-content: flex-end;
  }
}
</style>
