<template>
  <div class="mobile-meeting-detail mg-page">
    <PageHeader :title="meeting?.title || '会议详情'" show-back @back="$router.back()">
      <template #right>
        <button
          type="button"
          class="header-action danger"
          aria-label="删除会议"
          title="删除会议"
          @click="handleDelete"
        >
          <el-icon :size="20"><Delete /></el-icon>
        </button>
      </template>
    </PageHeader>

    <main
      v-if="meeting"
      class="detail-main"
      :style="{ paddingBottom: 'calc(24px + var(--sab, 0px))' }"
    >
      <!-- Hero 卡片 -->
      <div class="hero-card mg-glass-strong mg-rise">
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

        <!-- 操作区 (audio_url 存在时显示，2026-06-25 从 Sheet 迁移) -->
        <div v-if="meeting.audio_url" class="hero-actions">
          <button type="button" class="action-btn primary" @click="playAudio">
            🔊 播放录音
          </button>
          <button type="button" class="action-btn" @click="handleStartLive">
            🎤 重新听会
          </button>
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
          <section v-if="meeting.summary" class="content-section mg-glass mg-rise mg-stagger-1">
            <h3 class="section-title">会议摘要</h3>
            <p class="section-text">{{ meeting.summary }}</p>
          </section>

          <section v-if="meeting.key_points?.length" class="content-section mg-glass mg-rise mg-stagger-2">
            <h3 class="section-title">讨论要点</h3>
            <ul class="point-list">
              <li v-for="(point, i) in meeting.key_points" :key="i" class="point-item">
                <span class="point-index">{{ i + 1 }}</span>
                <span class="point-text">{{ point }}</span>
              </li>
            </ul>
          </section>

          <section v-if="meeting.decisions?.length" class="content-section mg-glass mg-rise mg-stagger-3">
            <h3 class="section-title">决议事项</h3>
            <ul class="decision-list">
              <li v-for="(decision, i) in meeting.decisions" :key="i" class="decision-item">
                <span class="decision-icon">✓</span>
                <span class="decision-text">{{ decision }}</span>
              </li>
            </ul>
          </section>

          <div v-if="!meeting.summary && !meeting.key_points?.length && !meeting.decisions?.length" class="empty-tab mg-glass">
            <div class="empty-icon">📝</div>
            <div class="empty-title">暂无会议纪要</div>
            <div v-if="meeting.audio_url" class="empty-hint">录音上传后自动生成</div>
          </div>
        </div>

        <!-- 转录 -->
        <div v-if="activeTab === 'transcript'" class="transcript-tab">
          <!-- 2026-08-04 P0: 桌面端优先 transcript_polished, 移动端之前只读 transcript,
               导致后端已生成润色版但前端显示 "暂无转录内容". 改用同一份 composable
               选择 polished || raw. -->
          <div v-if="displaySegments.length" class="transcript-list mg-glass mg-rise">
            <div
              v-for="(seg, i) in displaySegments"
              :key="i"
              class="transcript-segment"
            >
              <div class="seg-meta">
                <span class="seg-speaker">{{ seg.speaker || '发言人' }}</span>
                <!-- 2026-08-04 P0: 后端 transcript_polished 用 `ts` 字段,
                     老代码读 `seg.timestamp` 永远是 undefined. 改用 ts ?? start 兼容. -->
                <span v-if="formatSegTs(seg) != null" class="seg-time">{{ formatTime(formatSegTs(seg)) }}</span>
              </div>
              <div class="seg-text">{{ seg.text }}</div>
            </div>
            <!-- 2026-08-04 P0: 大转录不一次性渲染, 桌面端 50/页, 移动端更轻 30/页 + 展开按钮 -->
            <button
              v-if="hasMoreSegments"
              type="button"
              class="load-more"
              @click="loadMoreSegments"
            >
              展开剩余 {{ totalSegments - visibleSegmentCount }} 段
            </button>
          </div>
          <div v-else class="empty-tab mg-glass">
            <div class="empty-icon">🎙️</div>
            <div class="empty-title">暂无转录内容</div>
            <div v-if="meeting.error_reason" class="empty-hint error">{{ meeting.error_reason }}</div>
          </div>
        </div>

        <!-- 发言统计 -->
        <div v-if="activeTab === 'stats'" class="stats-tab">
          <div v-if="speakerStats?.length" class="stats-list mg-glass mg-rise">
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
          <div v-else class="empty-tab mg-glass">
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

    <!-- 会议信息 Sheet 已删除 (2026-06-25) - 删除入口移到 PageHeader，操作移到 hero-card -->
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
import { Delete } from '@element-plus/icons-vue'
import dayjs from 'dayjs'
import axios from 'axios'
import PageHeader from '@/components/mobile/PageHeader.vue'
import { useMeetingTranscript } from '@/composables/useMeetingTranscript'

const route = useRoute()
const router = useRouter()

const meeting = ref(null)
const loading = ref(true)
const activeTab = ref('minutes')
const PAGE_SIZE = 30

// 2026-08-04 P0: 抽出 polished||raw + ts/start 兼容逻辑到 composable, 桌面/移动复用.
const { displaySegments, totalSegments, hasMoreSegments, loadMoreSegments } = useMeetingTranscript(meeting, PAGE_SIZE)
function formatSegTs(seg) {
  if (!seg) return null
  if (typeof seg.ts === 'number') return seg.ts
  if (typeof seg.start === 'number') return seg.start
  if (typeof seg.timestamp === 'number') return seg.timestamp
  return null
}

const tabs = computed(() => [
  { name: 'minutes', label: '纪要' },
  {
    name: 'transcript',
    label: '转录',
    count: totalSegments.value || 0,
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
  return {
    scheduled: '已预约',
    recording: '录制中',
    processing: '处理中',
    completed: '已完成',
    completed_with_warnings: '已完成（含警告）',
    cancelled: '已取消',
    error: '处理失败',
  }[s] || s
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
  // 2026-08-04 P0: 与桌面端一致走受控 proxy, 避免相对路径在 MinIO 上 404.
  window.open(`/api/v1/meetings/${meeting.value.id}/audio`, '_blank')
}

function handleStartLive() {
  // 跳到移动端全屏听会页（MobileMeetingRoom）
  // 注：移动端走"录音机+离线后处理"模式，不是桌面 WS 实时转录
  router.push('/meetings/room')
}

async function handleDelete() {
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
  display: flex;
  flex-direction: column;
}

.detail-main {
  flex: 1;
  padding: var(--mobile-padding-y, 12px) var(--mobile-padding-x, 16px);
}

/* Hero 卡片 — 玻璃配方由 .mg-glass-strong 提供 */
.hero-card {
  padding: 16px;
  margin-bottom: 12px;
}
.hero-title {
  font-size: 18px;
  font-weight: 800;
  color: var(--mg-text-strong);
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
  color: var(--mg-text-soft);
  margin-bottom: 8px;
}
.meta-icon { margin-right: 4px; }
.hero-status {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
}
.status-text {
  padding: 3px 10px;
  border-radius: var(--mg-radius-pill);
  font-size: 11px;
  font-weight: 600;
  color: var(--mg-primary);
  background: var(--mg-tint);
}
.status-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
}
.status-dot.status-scheduled { background: var(--mg-info); }
/* 录制中 = 危险红语义 + 光晕强调 */
.status-dot.status-recording {
  background: var(--mg-danger);
  box-shadow: 0 0 0 4px var(--mg-danger-soft);
  animation: pulse-dot 1s infinite;
}
.status-dot.status-processing { background: var(--mg-warning); animation: pulse-dot 1s infinite; }
.status-dot.status-completed,
.status-dot.status-completed_with_warnings { background: var(--mg-success); }
.status-dot.status-cancelled { background: var(--mg-text-faint); }
.status-dot.status-error { background: var(--mg-danger); }

/* Tab bar — 玻璃胶囊分段控件 */
.tab-bar {
  display: flex;
  background: var(--mg-glass-bg);
  border: 1.5px solid var(--mg-glass-border);
  -webkit-backdrop-filter: blur(var(--mg-glass-blur));
  backdrop-filter: blur(var(--mg-glass-blur));
  border-radius: var(--mg-radius-pill);
  padding: 4px;
  margin-bottom: 12px;
  box-shadow: var(--mg-shadow-sm);
}
.tab-item {
  flex: 1;
  min-height: 44px;
  padding: 10px;
  border: none;
  background: transparent;
  border-radius: var(--mg-radius-pill);
  font-size: 13px;
  color: var(--mg-text-soft);
  font-weight: 600;
  cursor: pointer;
  -webkit-tap-highlight-color: transparent;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 4px;
  transition: transform 150ms ease;
}
.tab-item:active { transform: scale(0.97); }
.tab-item.active {
  background: var(--mg-gradient-btn);
  color: var(--mg-on-primary);
  font-weight: 700;
  box-shadow: var(--mg-primary-shadow);
}
.tab-badge {
  font-size: 11px;
  background: rgba(255, 255, 255, 0.3);
  padding: 0 5px;
  border-radius: 8px;
}
.tab-item:not(.active) .tab-badge {
  background: var(--mg-tint);
  color: var(--mg-primary);
}

/* Tab content — 不再是整块卡片, 各 section 独立玻璃卡分组 */
.tab-content {
  min-height: 200px;
}

.content-section {
  margin-bottom: 12px;
  padding: 14px 16px;
  border-radius: var(--mg-radius-md);
}
.section-title {
  font-size: 15px;
  font-weight: 800;
  color: var(--mg-text-strong);
  margin: 0 0 8px;
  padding-left: 8px;
  border-left: 3px solid var(--mg-primary);
}
.section-text {
  font-size: 14px;
  color: var(--mg-text);
  line-height: 1.7;
  white-space: pre-wrap;
}

.point-list,
.decision-list {
  list-style: none;
  padding: 0;
  margin: 0;
}
/* 讨论要点 = 【发言人】高亮块, 紫调局部底色 */
.point-item {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  padding: 10px 12px;
  background: var(--mg-tint);
  border-radius: 12px;
  margin-bottom: 6px;
  font-size: 13px;
  color: var(--mg-text);
  line-height: 1.6;
}
.decision-item {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  padding: 10px 12px;
  background: var(--mg-success-soft);
  border-radius: 12px;
  margin-bottom: 6px;
  font-size: 13px;
  color: var(--mg-text);
  line-height: 1.6;
}
.point-index {
  flex-shrink: 0;
  width: 22px;
  height: 22px;
  border-radius: 50%;
  background: var(--mg-gradient-btn);
  color: var(--mg-on-primary);
  font-size: 11px;
  font-weight: 700;
  display: flex;
  align-items: center;
  justify-content: center;
}
.decision-icon {
  flex-shrink: 0;
  color: var(--mg-success);
  font-weight: 700;
}

/* 转录 — 玻璃卡由 .mg-glass 提供 */
.transcript-list {
  padding: 4px 16px 16px;
}
.transcript-segment {
  padding: 12px 0;
  border-bottom: 1px solid var(--mg-divider);
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
  font-weight: 700;
  color: var(--mg-primary);
}
.seg-time {
  font-size: 11px;
  color: var(--mg-text-faint);
}
.seg-text {
  font-size: 14px;
  color: var(--mg-text);
  line-height: 1.6;
}

/* 统计 — 玻璃卡由 .mg-glass 提供 */
.stats-list {
  padding: 16px;
}
.stat-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px;
  background: var(--mg-tint);
  border-radius: 12px;
  margin-bottom: 8px;
}
.stat-rank {
  font-size: 14px;
  font-weight: 800;
  color: var(--mg-primary);
  min-width: 30px;
}
.stat-info {
  flex: 1;
  min-width: 0;
}
.stat-name {
  font-size: 14px;
  font-weight: 600;
  color: var(--mg-text-strong);
  margin-bottom: 6px;
}
.stat-bar-wrap {
  height: 6px;
  background: var(--mg-track);
  border-radius: 3px;
  overflow: hidden;
  margin-bottom: 4px;
}
.stat-bar {
  height: 100%;
  background: var(--mg-gradient-btn);
  border-radius: 3px;
  transition: width 0.5s;
}
.stat-detail {
  display: flex;
  justify-content: space-between;
  font-size: 11px;
  color: var(--mg-text-soft);
}

/* Empty */
.empty-tab {
  text-align: center;
  padding: 48px 20px;
}
.empty-icon {
  font-size: 40px;
  margin-bottom: 8px;
}
.empty-title {
  font-size: 14px;
  font-weight: 700;
  color: var(--mg-text);
  margin-bottom: 4px;
}
.empty-hint {
  font-size: 12px;
  color: var(--mg-text-soft);
}
.empty-hint.error {
  color: var(--mg-danger);
}

.load-more {
  display: block;
  margin: 12px auto 0;
  padding: 10px 18px;
  min-height: 44px;
  background: var(--mg-glass-bg-strong);
  border: 1.5px solid var(--mg-glass-border);
  border-radius: var(--mg-radius-pill);
  color: var(--mg-primary);
  font-weight: 700;
  font-size: 13px;
  cursor: pointer;
  -webkit-tap-highlight-color: transparent;
  transition: transform 150ms ease;
}
.load-more:active { transform: scale(0.97); }

.loading-state {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 12px;
  color: var(--mg-text-soft);
}
.loading-spinner {
  width: 32px;
  height: 32px;
  border: 3px solid var(--mg-track);
  border-top-color: var(--mg-primary);
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}

/* Header action */
.header-action {
  width: 44px;
  height: 44px;
  border-radius: 50%;
  background: transparent;
  border: none;
  font-size: 18px;
  color: var(--mg-text-soft);
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
}
.header-action:active { background: var(--mg-glass-bg-strong); }
/* 删除会议按钮: 危险语义 */
.header-action.danger {
  color: var(--mg-danger);
}
.header-action.danger:active {
  background: var(--mg-danger-soft);
}

/* hero-card 操作区 (从 Sheet 迁移) */
.hero-actions {
  display: flex;
  flex-direction: column;
  gap: 8px;
  margin-top: 12px;
}
.action-btn {
  padding: 12px;
  min-height: 44px;
  border-radius: 14px;
  border: 1.5px solid var(--mg-glass-border);
  background: var(--mg-glass-bg-strong);
  font-size: 13px;
  font-weight: 600;
  color: var(--mg-text);
  cursor: pointer;
  -webkit-tap-highlight-color: transparent;
  text-align: left;
  transition: transform 150ms ease;
}
.action-btn:active { transform: scale(0.97); }
.action-btn.primary {
  background: var(--mg-gradient-btn);
  color: var(--mg-on-primary);
  border: none;
  font-weight: 800;
  box-shadow: var(--mg-primary-shadow);
}
</style>