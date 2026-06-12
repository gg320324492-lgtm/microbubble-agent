<template>
  <div class="mobile-meeting-detail">
    <PageHeader :title="meeting?.title || '会议详情'" show-back @back="$router.back()">
      <template #right>
        <button
          type="button"
          class="header-action"
          aria-label="会议信息"
          title="会议信息"
          @click="showInfoSheet = true"
        >ℹ️</button>
      </template>
    </PageHeader>

    <main
      v-if="meeting"
      class="detail-main"
      :style="{ paddingBottom: 'calc(var(--tabbar-height, 56px) + var(--sab, 0px))' }"
    >
      <!-- Hero 卡片 -->
      <div class="hero-card">
        <div class="hero-title">{{ meeting.title }}</div>
        <div class="hero-meta">
          <div class="hero-time">
            <span class="meta-icon">🕐</span>
            <span>{{ formatDate(meeting.start_time) }}</span>
          </div>
          <div v-if="meeting.location" class="hero-loc">
            <span class="meta-icon">📍</span>
            <span>{{ meeting.location }}</span>
          </div>
        </div>
        <div class="hero-status">
          <span class="status-dot" :class="'status-' + meeting.status" />
          <span class="status-text">{{ getStatusLabel(meeting.status) }}</span>
        </div>
      </div>

      <!-- 标签页 -->
      <div class="tab-bar">
        <button
          v-for="tab in tabs"
          :key="tab.name"
          type="button"
          class="tab-item"
          :class="{ active: activeTab === tab.name }"
          @click="activeTab = tab.name"
        >
          {{ tab.label }}
          <span v-if="tab.count" class="tab-badge">{{ tab.count }}</span>
        </button>
      </div>

      <!-- Tab 内容 -->
      <div class="tab-content">
        <!-- 会议纪要 -->
        <div v-if="activeTab === 'minutes'" class="minutes-tab">
          <section v-if="meeting.summary" class="content-section">
            <h3 class="section-title">会议摘要</h3>
            <p class="section-text">{{ meeting.summary }}</p>
          </section>

          <section v-if="meeting.key_points?.length" class="content-section">
            <h3 class="section-title">讨论要点</h3>
            <ul class="point-list">
              <li v-for="(point, i) in meeting.key_points" :key="i" class="point-item">
                <span class="point-index">{{ i + 1 }}</span>
                <span class="point-text">{{ point }}</span>
              </li>
            </ul>
          </section>

          <section v-if="meeting.decisions?.length" class="content-section">
            <h3 class="section-title">决议事项</h3>
            <ul class="decision-list">
              <li v-for="(decision, i) in meeting.decisions" :key="i" class="decision-item">
                <span class="decision-icon">✓</span>
                <span class="decision-text">{{ decision }}</span>
              </li>
            </ul>
          </section>

          <div v-if="!meeting.summary && !meeting.key_points?.length && !meeting.decisions?.length" class="empty-tab">
            <div class="empty-icon">📝</div>
            <div class="empty-title">暂无会议纪要</div>
            <div v-if="meeting.audio_url" class="empty-hint">录音上传后自动生成</div>
          </div>
        </div>

        <!-- 转录 -->
        <div v-if="activeTab === 'transcript'" class="transcript-tab">
          <div v-if="meeting.transcript?.length" class="transcript-list">
            <div
              v-for="(seg, i) in meeting.transcript"
              :key="i"
              class="transcript-segment"
            >
              <div class="seg-meta">
                <span class="seg-speaker">{{ seg.speaker || '发言人' }}</span>
                <span v-if="seg.timestamp" class="seg-time">{{ formatTime(seg.timestamp) }}</span>
              </div>
              <div class="seg-text">{{ seg.text }}</div>
            </div>
          </div>
          <div v-else class="empty-tab">
            <div class="empty-icon">🎙️</div>
            <div class="empty-title">暂无转录内容</div>
          </div>
        </div>

        <!-- 发言统计 -->
        <div v-if="activeTab === 'stats'" class="stats-tab">
          <div v-if="speakerStats?.length" class="stats-list">
            <div
              v-for="(stat, i) in speakerStats"
              :key="i"
              class="stat-item"
            >
              <div class="stat-rank">#{{ i + 1 }}</div>
              <div class="stat-info">
                <div class="stat-name">{{ stat.name }}</div>
                <div class="stat-bar-wrap">
                  <div
                    class="stat-bar"
                    :style="{ width: stat.percent + '%' }"
                  />
                </div>
                <div class="stat-detail">
                  <span>共 {{ stat.count }} 次发言</span>
                  <span>{{ stat.duration }}</span>
                </div>
              </div>
            </div>
          </div>
          <div v-else class="empty-tab">
            <div class="empty-icon">📊</div>
            <div class="empty-title">暂无发言统计</div>
          </div>
        </div>
      </div>
    </main>

    <div v-else-if="loading" class="loading-state">
      <div class="loading-spinner" />
      <p>加载中...</p>
    </div>

    <!-- 会议信息 Sheet（替代桌面右侧 side 栏） -->
    <Teleport to="body">
      <Transition name="info-sheet">
        <div v-if="showInfoSheet" class="info-overlay" @click.self="showInfoSheet = false">
          <div class="info-panel">
            <div class="info-header">
              <h3>会议信息</h3>
              <button type="button" @click="showInfoSheet = false">✕</button>
            </div>

            <div v-if="meeting" class="info-content">
              <div class="info-row">
                <span class="info-label">主题</span>
                <span class="info-value">{{ meeting.title }}</span>
              </div>
              <div class="info-row">
                <span class="info-label">时间</span>
                <span class="info-value">{{ formatDate(meeting.start_time) }}</span>
              </div>
              <div v-if="meeting.location" class="info-row">
                <span class="info-label">地点</span>
                <span class="info-value">{{ meeting.location }}</span>
              </div>
              <div class="info-row">
                <span class="info-label">状态</span>
                <span class="info-value">{{ getStatusLabel(meeting.status) }}</span>
              </div>

              <div v-if="meeting.participants?.length" class="info-section">
                <div class="info-section-title">参与人 ({{ meeting.participants.length }})</div>
                <div class="participants-list">
                  <div
                    v-for="p in meeting.participants"
                    :key="p.member_id"
                    class="participant-item"
                  >
                    <div class="participant-avatar">{{ p.name?.charAt(0) || '?' }}</div>
                    <span>{{ p.name }}</span>
                  </div>
                </div>
              </div>

              <div v-if="meeting.description" class="info-section">
                <div class="info-section-title">说明</div>
                <p class="info-description">{{ meeting.description }}</p>
              </div>

              <div v-if="meeting.agenda?.length" class="info-section">
                <div class="info-section-title">议题</div>
                <ol class="agenda-list">
                  <li v-for="(a, i) in meeting.agenda" :key="i">{{ a }}</li>
                </ol>
              </div>

              <div class="info-actions">
                <button
                  v-if="meeting.audio_url"
                  type="button"
                  class="info-btn primary"
                  @click="playAudio"
                >🔊 播放录音</button>
                <button
                  v-if="meeting.audio_url"
                  type="button"
                  class="info-btn"
                  @click="handleStartLive"
                >🎤 重新听会</button>
                <button
                  type="button"
                  class="info-btn danger"
                  @click="handleDelete"
                >🗑 删除会议</button>
              </div>
            </div>
          </div>
        </div>
      </Transition>
    </Teleport>
  </div>
</template>

<script setup>
/**
 * MobileMeetingDetailView.vue — 移动端会议详情
 *
 * PR #4:
 * - hero 卡片压缩（标题 + 时间 + 状态）
 * - 3 tab 用底部按钮组（不用 el-tabs，移动端更稳）
 * - 侧栏信息 → 右上 ℹ️ 打开底部 Sheet
 * - 复用 desktop 服务的 fetchMeeting API
 */

import { ref, computed, onMounted, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import dayjs from 'dayjs'
import axios from 'axios'
import PageHeader from '@/components/mobile/PageHeader.vue'

const route = useRoute()
const router = useRouter()

const meeting = ref(null)
const loading = ref(true)
const activeTab = ref('minutes')
const showInfoSheet = ref(false)

const tabs = computed(() => [
  { name: 'minutes', label: '纪要' },
  {
    name: 'transcript',
    label: '转录',
    count: meeting.value?.transcript?.length || 0,
  },
  {
    name: 'stats',
    label: '统计',
    count: speakerStats.value?.length || 0,
  },
])

// 格式化
function formatDate(t) {
  if (!t) return ''
  return dayjs(t).add(8, 'hour').format('YYYY-MM-DD HH:mm')
}
function formatTime(t) {
  if (!t) return ''
  return dayjs(t).add(8, 'hour').format('HH:mm:ss')
}
function getStatusLabel(s) {
  return { scheduled: '已预约', recording: '录制中', processing: '处理中', completed: '已完成', cancelled: '已取消', error: '处理失败' }[s] || s
}

// 发言人统计（简单聚合）
const speakerStats = computed(() => {
  if (!meeting.value?.transcript?.length) return []
  const map = {}
  meeting.value.transcript.forEach((seg) => {
    const key = seg.speaker || '发言人'
    if (!map[key]) {
      map[key] = { name: key, count: 0, duration: 0 }
    }
    map[key].count += 1
    map[key].duration += (seg.text?.length || 0) // 简化：用字数代替时长
  })
  const list = Object.values(map)
  const max = Math.max(...list.map((s) => s.count), 1)
  return list
    .sort((a, b) => b.count - a.count)
    .map((s) => ({ ...s, percent: (s.count / max) * 100 }))
})

// 加载会议详情
async function fetchMeeting() {
  const id = route.params.id
  if (!id) return
  loading.value = true
  try {
    const res = await axios.get(`/api/v1/meetings/${id}`)
    meeting.value = res.data
  } catch (e) {
    ElMessage.error('加载会议失败')
  } finally {
    loading.value = false
  }
}

function playAudio() {
  if (!meeting.value?.audio_url) return
  window.open(meeting.value.audio_url, '_blank')
}

function handleStartLive() {
  router.push('/meetings?startLive=true')
}

async function handleDelete() {
  showInfoSheet.value = false
  try {
    await ElMessageBox.confirm('确定删除此会议？', '删除确认', {
      confirmButtonText: '删除',
      cancelButtonText: '取消',
      type: 'warning',
    })
    await axios.delete(`/api/v1/meetings/${meeting.value.id}`)
    ElMessage.success('已删除')
    router.replace('/meetings')
  } catch (e) {
    if (e !== 'cancel') {
      ElMessage.error('删除失败')
    }
  }
}

onMounted(() => {
  fetchMeeting()
})

watch(() => route.params.id, fetchMeeting)
</script>

<style scoped>
.mobile-meeting-detail {
  min-height: 100vh;
  background: var(--color-bg-page);
  display: flex;
  flex-direction: column;
}

.detail-main {
  flex: 1;
  padding: var(--mobile-padding-y, 12px) var(--mobile-padding-x, 16px);
}

/* Hero 卡片 */
.hero-card {
  background: linear-gradient(135deg, var(--color-primary-bg) 0%, var(--color-accent-bg) 100%);
  border-radius: var(--radius-md);
  padding: 16px;
  margin-bottom: 12px;
}
[data-theme="dark"] .hero-card {
  background: linear-gradient(135deg, rgba(255, 122, 92, 0.12), rgba(255, 179, 71, 0.08));
}
.hero-title {
  font-size: 17px;
  font-weight: var(--font-weight-semibold, 600);
  color: var(--color-text-primary);
  line-height: 1.4;
  margin-bottom: 10px;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
.hero-meta {
  display: flex;
  flex-direction: column;
  gap: 4px;
  font-size: 13px;
  color: var(--color-text-regular);
  margin-bottom: 8px;
}
.meta-icon { margin-right: 4px; }
.hero-status {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  color: var(--color-text-regular);
}
.status-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
}
.status-dot.status-scheduled { background: #909399; }
.status-dot.status-recording,
.status-dot.status-processing { background: var(--color-warning, #E6A23C); animation: pulse-dot 1s infinite; }
.status-dot.status-completed { background: var(--color-success, #67C23A); }
.status-dot.status-cancelled { background: var(--color-info, #909399); }
.status-dot.status-error { background: var(--color-danger, #F56C6C); }
@keyframes pulse-dot { 0%, 100% { opacity: 1; } 50% { opacity: 0.4; } }

/* Tab bar */
.tab-bar {
  display: flex;
  background: var(--color-bg-card);
  border-radius: var(--radius-md);
  padding: 4px;
  margin-bottom: 12px;
}
.tab-item {
  flex: 1;
  padding: 10px;
  border: none;
  background: transparent;
  border-radius: var(--radius-sm);
  font-size: 13px;
  color: var(--color-text-regular);
  cursor: pointer;
  -webkit-tap-highlight-color: transparent;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 4px;
}
.tab-item.active {
  background: var(--color-primary);
  color: white;
  font-weight: 500;
}
.tab-badge {
  font-size: 11px;
  background: rgba(255, 255, 255, 0.3);
  padding: 0 5px;
  border-radius: 8px;
}
.tab-item:not(.active) .tab-badge {
  background: var(--color-bg-page);
}

/* Tab content */
.tab-content {
  background: var(--color-bg-card);
  border-radius: var(--radius-md);
  padding: 16px;
  min-height: 200px;
}

.content-section {
  margin-bottom: 20px;
}
.section-title {
  font-size: 14px;
  font-weight: var(--font-weight-semibold, 600);
  color: var(--color-text-primary);
  margin: 0 0 8px;
  padding-left: 8px;
  border-left: 3px solid var(--color-primary);
}
.section-text {
  font-size: 14px;
  color: var(--color-text-regular);
  line-height: 1.7;
  white-space: pre-wrap;
}

.point-list,
.decision-list {
  list-style: none;
  padding: 0;
  margin: 0;
}
.point-item,
.decision-item {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  padding: 10px 12px;
  background: var(--color-bg-page);
  border-radius: var(--radius-sm);
  margin-bottom: 6px;
  font-size: 13px;
  color: var(--color-text-primary);
  line-height: 1.6;
}
.point-index {
  flex-shrink: 0;
  width: 22px;
  height: 22px;
  border-radius: 50%;
  background: var(--color-primary);
  color: white;
  font-size: 11px;
  font-weight: 600;
  display: flex;
  align-items: center;
  justify-content: center;
}
.decision-icon {
  flex-shrink: 0;
  color: var(--color-success, #67C23A);
  font-weight: 600;
}

/* 转录 */
.transcript-segment {
  padding: 12px 0;
  border-bottom: 1px solid var(--color-border-light);
}
.transcript-segment:last-child { border-bottom: none; }
.seg-meta {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 6px;
}
.seg-speaker {
  font-size: 12px;
  font-weight: var(--font-weight-semibold, 600);
  color: var(--color-primary);
}
.seg-time {
  font-size: 11px;
  color: var(--color-text-secondary);
}
.seg-text {
  font-size: 14px;
  color: var(--color-text-primary);
  line-height: 1.6;
}

/* 统计 */
.stat-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px;
  background: var(--color-bg-page);
  border-radius: var(--radius-sm);
  margin-bottom: 8px;
}
.stat-rank {
  font-size: 14px;
  font-weight: var(--font-weight-bold, 700);
  color: var(--color-primary);
  min-width: 30px;
}
.stat-info {
  flex: 1;
  min-width: 0;
}
.stat-name {
  font-size: 14px;
  font-weight: var(--font-weight-medium, 500);
  color: var(--color-text-primary);
  margin-bottom: 6px;
}
.stat-bar-wrap {
  height: 6px;
  background: var(--color-border);
  border-radius: 3px;
  overflow: hidden;
  margin-bottom: 4px;
}
.stat-bar {
  height: 100%;
  background: linear-gradient(90deg, var(--color-primary), var(--color-primary-light));
  border-radius: 3px;
  transition: width 0.5s;
}
.stat-detail {
  display: flex;
  justify-content: space-between;
  font-size: 11px;
  color: var(--color-text-secondary);
}

/* Empty */
.empty-tab {
  text-align: center;
  padding: 60px 20px;
}
.empty-icon {
  font-size: 40px;
  margin-bottom: 8px;
}
.empty-title {
  font-size: 14px;
  color: var(--color-text-regular);
  margin-bottom: 4px;
}
.empty-hint {
  font-size: 12px;
  color: var(--color-text-secondary);
}

.loading-state {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 12px;
}
.loading-spinner {
  width: 32px;
  height: 32px;
  border: 3px solid var(--color-border);
  border-top-color: var(--color-primary);
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}
@keyframes spin { to { transform: rotate(360deg); } }

/* Header action */
.header-action {
  width: 36px;
  height: 36px;
  border-radius: 50%;
  background: transparent;
  border: none;
  font-size: 18px;
  color: var(--color-text-regular);
  cursor: pointer;
}
.header-action:active { background: var(--color-primary-bg); }

/* Info Sheet */
.info-overlay {
  position: fixed;
  inset: 0;
  z-index: 4000;
  background: rgba(0, 0, 0, 0.4);
  display: flex;
  align-items: flex-end;
}
.info-panel {
  width: 100%;
  max-height: 80vh;
  background: var(--color-bg-card);
  border-radius: var(--sheet-radius, 16px) var(--sheet-radius, 16px) 0 0;
  padding: 16px 16px calc(16px + var(--sab, 0px) + var(--tabbar-height, 56px));
  overflow-y: auto;
}
.info-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 16px;
  padding-bottom: 12px;
  border-bottom: 1px solid var(--color-border);
}
.info-header h3 {
  margin: 0;
  font-size: 16px;
  font-weight: var(--font-weight-semibold, 600);
}
.info-header button {
  width: 32px;
  height: 32px;
  border-radius: 50%;
  background: transparent;
  border: none;
  font-size: 18px;
  color: var(--color-text-regular);
  cursor: pointer;
}

.info-row {
  display: flex;
  padding: 8px 0;
  font-size: 13px;
}
.info-label {
  flex: 0 0 60px;
  color: var(--color-text-secondary);
}
.info-value {
  flex: 1;
  color: var(--color-text-primary);
}

.info-section {
  margin-top: 16px;
  padding-top: 12px;
  border-top: 1px solid var(--color-border-light);
}
.info-section-title {
  font-size: 12px;
  color: var(--color-text-secondary);
  margin-bottom: 8px;
  font-weight: var(--font-weight-medium, 500);
}

.participants-list {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(120px, 1fr));
  gap: 8px;
}
.participant-item {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
  color: var(--color-text-primary);
}
.participant-avatar {
  width: 28px;
  height: 28px;
  border-radius: 50%;
  background: linear-gradient(135deg, var(--color-primary), var(--color-accent));
  color: white;
  font-size: 12px;
  font-weight: 600;
  display: flex;
  align-items: center;
  justify-content: center;
}

.info-description {
  font-size: 13px;
  color: var(--color-text-regular);
  line-height: 1.6;
  white-space: pre-wrap;
}
.agenda-list {
  padding-left: 20px;
  font-size: 13px;
  color: var(--color-text-regular);
  line-height: 1.7;
}
.agenda-list li { margin-bottom: 4px; }

.info-actions {
  margin-top: 20px;
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.info-btn {
  padding: 12px;
  border-radius: var(--radius-md);
  border: 1px solid var(--color-border);
  background: var(--color-bg-card);
  font-size: 14px;
  color: var(--color-text-primary);
  cursor: pointer;
  -webkit-tap-highlight-color: transparent;
}
.info-btn:active { background: var(--color-bg-hover); }
.info-btn.primary {
  background: var(--color-primary);
  color: white;
  border-color: var(--color-primary);
}
.info-btn.danger {
  background: var(--color-danger-bg);
  color: var(--color-danger, #F56C6C);
  border-color: var(--color-danger, #F56C6C);
}

.info-sheet-enter-active, .info-sheet-leave-active {
  transition: opacity 0.25s ease;
}
.info-sheet-enter-active .info-panel, .info-sheet-leave-active .info-panel {
  transition: transform 0.3s ease;
}
.info-sheet-enter-from, .info-sheet-leave-to { opacity: 0; }
.info-sheet-enter-from .info-panel, .info-sheet-leave-to .info-panel {
  transform: translateY(100%);
}
</style>