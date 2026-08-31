<template>
  <div class="mobile-meeting-view mg-page">
    <PageHeader title="会议管理" show-back @back="$router.back()">
      <template #right>
        <button
          type="button"
          class="header-action"
          aria-label="搜索"
          title="搜索"
          @click="showSearch = true"
        >🔍</button>
        <button
          type="button"
          class="header-action primary"
          aria-label="新建"
          title="新建"
          @click="showActionSheet = true"
        >+</button>
      </template>
    </PageHeader>

    <main class="meeting-main" :style="{ paddingBottom: 'calc(var(--tabbar-height, 76px) + var(--sab, 0px))' }">
      <!-- 日期范围快速筛选 -->
      <div class="quick-filters">
        <button
          v-for="f in dateFilters"
          :key="f.label"
          type="button"
          class="filter-chip"
          :class="{ active: activeDateFilter === f.value }"
          @click="applyDateFilter(f.value)"
        >{{ f.label }}</button>
      </div>

      <!-- 会议列表 -->
      <div v-if="loading && meetings.length === 0" class="loading-state">
        <div class="skeleton-card" v-for="i in 3" :key="i">
          <div class="skeleton-line w-60" />
          <div class="skeleton-line w-90" />
          <div class="skeleton-line w-40" />
        </div>
      </div>

      <div v-else-if="meetings.length === 0" class="empty-state mg-glass">
        <div class="empty-icon">📅</div>
        <div class="empty-title">暂无会议记录</div>
        <div class="empty-hint">点击右上角 + 创建</div>
      </div>

      <div v-else class="meeting-list">
        <button
          v-for="meeting in meetings"
          :key="meeting.id"
          type="button"
          class="meeting-card mg-glass mg-rise"
          @click="$router.push(`/meetings/${meeting.id}`)"
        >
          <div class="card-time-block">
            <div class="time-month">{{ formatMonth(meeting.start_time) }}</div>
            <div class="time-day">{{ formatDay(meeting.start_time) }}</div>
            <div class="time-hour">{{ formatHour(meeting.start_time) }}</div>
          </div>

          <div class="card-info">
            <div class="card-header">
              <div class="card-title">{{ meeting.title }}</div>
              <span class="status-dot" :class="'status-' + meeting.status" />
            </div>

            <div class="card-meta">
              <span class="status-tag" :class="'tag-' + meeting.status">
                {{ getStatusLabel(meeting.status) }}
              </span>
              <span v-if="meeting.location" class="meta-location">📍 {{ meeting.location }}</span>
              <span v-if="meeting.audio_url" class="meta-audio" title="有录音">🎙️</span>
            </div>

            <div v-if="meeting.participants?.length" class="card-participants">
              <div class="participants-avatars">
                <div
                  v-for="p in meeting.participants.slice(0, 4)"
                  :key="p.member_id"
                  class="mini-avatar"
                  :title="p.name"
                >{{ p.name?.charAt(0) || '?' }}</div>
                <div v-if="meeting.participants.length > 4" class="mini-avatar more">
                  +{{ meeting.participants.length - 4 }}
                </div>
              </div>
            </div>

            <div v-if="meeting.summary" class="card-summary">
              {{ meeting.summary.substring(0, 80) }}{{ meeting.summary.length > 80 ? '...' : '' }}
            </div>
          </div>
        </button>
      </div>

      <!-- 分页（仅显示总数） -->
      <div v-if="total > pageSize" class="pagination-info">
        共 {{ total }} 条 · 第 {{ currentPage }} / {{ Math.ceil(total / pageSize) }} 页
      </div>
    </main>

    <MobileFab :actions="fabActions" />

    <!-- 操作菜单（替代桌面 4 个按钮） -->
    <Teleport to="body">
      <Transition name="action-sheet">
        <div v-if="showActionSheet" class="action-overlay" @click.self="showActionSheet = false">
          <div class="action-panel mg-glass-strong">
            <div class="action-title">会议操作</div>
            <button type="button" class="action-item" @click="handleCreateMeeting">
              <span class="action-icon" style="background: var(--color-primary)">+</span>
              <span>手动创建</span>
            </button>
            <button
              id="meeting-paste-analyze"
              type="button"
              name="meeting-paste-analyze"
              class="action-item"
              aria-label="粘贴转录分析"
              title="粘贴转录分析"
              @click="handlePasteAnalyze"
            >
              <span class="action-icon" style="background: var(--color-success)">📋</span>
              <span>粘贴转录分析</span>
            </button>
            <button type="button" class="action-item" @click="handleStartLive">
              <span class="action-icon" style="background: var(--color-warning)">🎤</span>
              <span>开始听会</span>
            </button>
            <button
              id="meeting-voice-test"
              type="button"
              name="meeting-voice-test"
              class="action-item"
              aria-label="声纹识别测试"
              title="声纹识别测试"
              @click="handleVoiceTest"
            >
              <span class="action-icon" style="background: var(--color-info)">🎙</span>
              <span>声纹识别测试</span>
            </button>
            <button
              id="meeting-voiceprint-enroll"
              type="button"
              name="meeting-voiceprint-enroll"
              class="action-item"
              aria-label="录入我的声纹"
              title="录入我的声纹"
              @click="handleEnrollVoice"
            >
              <span class="action-icon" style="background: var(--color-primary)">🎙️</span>
              <span>录入我的声纹</span>
            </button>
            <button type="button" class="action-item cancel" @click="showActionSheet = false">取消</button>
          </div>
        </div>
      </Transition>
    </Teleport>

    <!-- 搜索 Sheet -->
    <Teleport to="body">
      <Transition name="search-sheet">
        <div v-if="showSearch" class="search-overlay" @click.self="showSearch = false">
          <div class="search-panel mg-glass-strong">
            <div class="search-header">
              <h3>搜索会议</h3>
              <button type="button" @click="showSearch = false">✕</button>
            </div>
            <input
              ref="searchInputRef"
              v-model="keyword"
              type="search"
              class="search-input"
              placeholder="搜索会议主题..."
              @keyup.enter="onSearch"
            />
            <div class="search-actions">
              <button type="button" class="btn-secondary" @click="onReset">重置</button>
              <button type="button" class="btn-primary" @click="onSearch">搜索</button>
            </div>
          </div>
        </div>
      </Transition>
    </Teleport>

    <!-- 创建会议对话框（移动端仍用 el-dialog fullscreen） -->
    <MeetingCreateDialog
      v-model:visible="showCreateDialog"
      :is-mobile="true"
      @success="onMeetingSaved"
    />

    <!-- 声纹识别测试全屏（ActionSheet 入口，复用声纹中心同款） -->
    <VoiceTestFlow v-model="showVoiceTest" />

    <!-- 录入声纹全屏（ActionSheet → 成员选择 → 复用声纹中心同款） -->
    <VoiceprintEnrollFlow
      v-if="enrollingMember"
      v-model="showEnroll"
      :member="enrollingMember"
      @success="onEnrollSuccess"
    />

    <!-- 粘贴转录分析（复用桌面端 el-dialog 组件，isMobile 模式自动 95vw 适配） -->
    <PasteAnalyzeDialog ref="pasteAnalyzeDialogRef" @saved="onMeetingSaved" />
  </div>
</template>

<script setup>
/**
 * MobileMeetingView.vue — 移动端会议列表
 *
 * PR #4: 桌面 4 按钮（手动创建/粘贴/听会/测试）折叠为底部 ActionSheet
 * 列表卡片化（不用 el-table 卡片化）：时间块 + 标题 + meta + 参与者头像
 * 移动端快速筛选：今日/本周/本月/全部
 */

import { ref, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import axios from 'axios'
import dayjs from 'dayjs'
import { useMeeting } from '@/composables/useMeeting'
import { useUserStore } from '@/stores/user'
import PageHeader from '@/components/mobile/PageHeader.vue'
import MeetingCreateDialog from '@/views/meeting/MeetingCreateDialog.vue'
import PasteAnalyzeDialog from '@/components/PasteAnalyzeDialog.vue'
import VoiceTestFlow from '@/components/mobile/VoiceTestFlow.vue'
import VoiceprintEnrollFlow from '@/components/mobile/VoiceprintEnrollFlow.vue'
import MobileFab from '@/components/mobile/MobileFab.vue'

const route = useRoute()
const router = useRouter()
const userStore = useUserStore()

const {
  meetings, total, currentPage, pageSize, loading,
  keyword, dateFrom, dateTo,
  fetchMeetings,
} = useMeeting()

const showActionSheet = ref(false)
const showSearch = ref(false)
const showCreateDialog = ref(false)
const showVoiceTest = ref(false)
const showEnroll = ref(false)
const pasteAnalyzeDialogRef = ref(null)
const searchInputRef = ref(null)

// 录入声纹：当前用户（自录入模式，无成员选择）
const enrollingMember = ref(null)

// 日期范围快速筛选
const activeDateFilter = ref('all')
const dateFilters = [
  { label: '全部', value: 'all' },
  { label: '今天', value: 'today' },
  { label: '本周', value: 'week' },
  { label: '本月', value: 'month' },
]

function applyDateFilter(filter) {
  activeDateFilter.value = filter
  const today = dayjs()
  switch (filter) {
    case 'today':
      dateFrom.value = today.format('YYYY-MM-DD')
      dateTo.value = today.format('YYYY-MM-DD')
      break
    case 'week':
      dateFrom.value = today.startOf('week').format('YYYY-MM-DD')
      dateTo.value = today.endOf('week').format('YYYY-MM-DD')
      break
    case 'month':
      dateFrom.value = today.startOf('month').format('YYYY-MM-DD')
      dateTo.value = today.endOf('month').format('YYYY-MM-DD')
      break
    case 'all':
    default:
      dateFrom.value = ''
      dateTo.value = ''
  }
  currentPage.value = 1
  fetchMeetings()
}

// 格式化
function formatMonth(t) {
  if (!t) return '--'
  return dayjs(t).add(8, 'hour').format('M月')
}
function formatDay(t) {
  if (!t) return '--'
  return dayjs(t).add(8, 'hour').format('DD')
}
function formatHour(t) {
  if (!t) return '--'
  return dayjs(t).add(8, 'hour').format('HH:mm')
}

function getStatusLabel(s) {
  return { scheduled: '已预约', recording: '录制中', processing: '处理中', completed: '已完成', cancelled: '已取消', error: '处理失败' }[s] || s
}

const fabActions = [
  { name: 'create', label: 'Create meeting', icon: '＋', handler: handleCreateMeeting },
  { name: 'paste', label: 'Analyze transcript', icon: '📋', handler: handlePasteAnalyze },
  { name: 'live', label: 'Start recording', icon: '🎤', handler: handleStartLive },
  { name: 'voice', label: 'Voiceprint test', icon: '🎙', handler: handleVoiceTest },
]

// 操作菜单处理
function handleCreateMeeting() {
  showActionSheet.value = false
  showCreateDialog.value = true
}
function handlePasteAnalyze() {
  showActionSheet.value = false
  // 复用桌面端 PasteAnalyzeDialog（isMobile=true 时自动 95vw 适配）
  pasteAnalyzeDialogRef.value?.open()
}
function handleStartLive() {
  showActionSheet.value = false
  // 跳到移动端全屏听会页（MobileMeetingRoom）
  // 注：移动端走"录音机+离线后处理"模式，不是桌面 WS 实时转录
  router.push('/meetings/room')
}
function handleVoiceTest() {
  showActionSheet.value = false
  // 复用声纹中心同款 VoiceTestFlow（POST /api/v1/voiceprint/test 全链路）
  showVoiceTest.value = true
}
async function handleEnrollVoice() {
  showActionSheet.value = false
  // 自录入模式：登录谁就录入谁，无需成员选择
  if (!userStore.userInfo?.id) {
    ElMessage.warning('请先登录')
    return
  }
  try {
    // fetch 完整 member（含 voice_enrolled_at / voice_sample_count）
    // 让 VoiceprintEnrollFlow 准确显示"✓ 已录入（X 次）" / "未录入"
    const res = await axios.get(`/api/v1/members/${userStore.userInfo.id}`)
    enrollingMember.value = res.data
    showEnroll.value = true
  } catch (e) {
    console.error(e)
    ElMessage.error('加载成员信息失败')
  }
}
function onEnrollSuccess() {
  showEnroll.value = false
  enrollingMember.value = null
  ElMessage.success('声纹录入成功')
}

function onMeetingSaved() {
  fetchMeetings()
}

function onSearch() {
  showSearch.value = false
  currentPage.value = 1
  fetchMeetings()
}

function onReset() {
  keyword.value = ''
  dateFrom.value = ''
  dateTo.value = ''
  activeDateFilter.value = 'all'
  currentPage.value = 1
  fetchMeetings()
  showSearch.value = false
}

onMounted(() => {
  fetchMeetings()
  // 处理 /meetings?resume={id} 跳转（MainLayout 录音指示器点击调用）
  // 之前漏了 → 移动端点击指示器没反应（同路由 query 变化不重渲）
  // 跳到 /meetings/room 后，MobileMeetingRoom.onMounted 会自动从 useRecordingState
  // 拿 recordingMeetingId 复用（line 200-203）实现"恢复现有听会"
  const resumeId = route.query.resume
  if (resumeId) {
    router.replace('/meetings/room')
  }
})
</script>

<style scoped>
.mobile-meeting-view {
  min-height: 100vh;
  display: flex;
  flex-direction: column;
}

.meeting-main {
  flex: 1;
  padding: var(--mobile-padding-y, 12px) var(--mobile-padding-x, 16px);
}

/* 日期快速筛选 */
.quick-filters {
  display: flex;
  gap: 8px;
  margin-bottom: 12px;
  overflow-x: auto;
  -webkit-overflow-scrolling: touch;
  scrollbar-width: none;
}
.quick-filters::-webkit-scrollbar { display: none; }
.filter-chip {
  flex-shrink: 0;
  min-height: 44px;
  padding: 6px 16px;
  display: inline-flex;
  align-items: center;
  background: var(--mg-glass-bg-strong);
  border: 1.5px solid var(--mg-glass-border);
  -webkit-backdrop-filter: blur(10px);
  backdrop-filter: blur(10px);
  border-radius: var(--mg-radius-pill);
  font-size: 13px;
  font-weight: 600;
  color: var(--mg-text-soft);
  cursor: pointer;
  -webkit-tap-highlight-color: transparent;
  transition: transform 150ms ease;
}
.filter-chip:active { transform: scale(0.97); }
.filter-chip.active {
  background: var(--mg-gradient-btn);
  color: var(--mg-on-primary);
  border-color: transparent;
  box-shadow: var(--mg-primary-shadow);
}

/* 会议卡片 — 玻璃配方由 .mg-glass 全局类提供, 此处只管布局/局部覆盖 */
.meeting-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.meeting-card {
  display: flex;
  width: 100%;
  border-radius: var(--mg-radius-md);
  padding: 13px 14px;
  text-align: left;
  cursor: pointer;
  -webkit-tap-highlight-color: transparent;
  gap: 12px;
  align-items: flex-start;
  transition: transform 150ms ease;
}
.meeting-card:active {
  transform: scale(0.97);
}

.card-time-block {
  flex-shrink: 0;
  width: 60px;
  text-align: center;
  background: var(--mg-gradient-soft);
  border-radius: 12px;
  padding: 8px 4px;
}
.time-month {
  font-size: 11px;
  color: var(--mg-text-soft);
  margin-bottom: 2px;
}
.time-day {
  font-size: 22px;
  font-weight: 800;
  color: var(--mg-primary);
  line-height: 1;
}
.time-hour {
  font-size: 10px;
  color: var(--mg-text-faint);
  margin-top: 4px;
}

.card-info {
  flex: 1;
  min-width: 0;
}
.card-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 8px;
  margin-bottom: 6px;
}
.card-title {
  font-size: 15px;
  font-weight: 700;
  color: var(--mg-text-strong);
  flex: 1;
  line-height: 1.3;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
.status-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  flex-shrink: 0;
  margin-top: 6px;
}
.status-dot.status-scheduled { background: var(--mg-info); }
/* 录制中 = 危险红语义 + 光晕强调 */
.status-dot.status-recording {
  background: var(--mg-danger);
  box-shadow: 0 0 0 4px var(--mg-danger-soft);
  animation: pulse-dot 1s infinite;
}
.status-dot.status-processing { background: var(--mg-warning); animation: pulse-dot 1s infinite; }
.status-dot.status-completed { background: var(--mg-success); }
.status-dot.status-cancelled { background: var(--mg-text-faint); }
.status-dot.status-error { background: var(--mg-danger); }
.card-meta {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 6px;
  margin-bottom: 6px;
  font-size: 11px;
  color: var(--mg-text-soft);
}
/* 状态标签 = mg-chip 语义变体配色 (processing→warn / completed→ok / error→dgr) */
.status-tag {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 3px 10px;
  border-radius: var(--mg-radius-pill);
  font-size: 11px;
  font-weight: 600;
}
.tag-scheduled { background: var(--mg-info-soft); color: var(--mg-info); }
.tag-recording { background: var(--mg-danger-soft); color: var(--mg-danger); }
.tag-processing { background: var(--mg-warning-soft); color: var(--mg-warning); }
.tag-completed { background: var(--mg-success-soft); color: var(--mg-success); }
.tag-cancelled { background: var(--mg-glass-bg-strong); color: var(--mg-text-faint); }
.tag-error { background: var(--mg-danger-soft); color: var(--mg-danger); }

.meta-location { color: var(--mg-text-soft); }
.meta-audio { color: var(--mg-primary); }

.card-participants { margin-bottom: 4px; }
.participants-avatars {
  display: flex;
  align-items: center;
}
.mini-avatar {
  width: 22px;
  height: 22px;
  border-radius: 50%;
  background: var(--mg-gradient);
  color: var(--mg-on-primary);
  font-size: 10px;
  font-weight: 600;
  display: flex;
  align-items: center;
  justify-content: center;
  margin-left: -6px;
  border: 2px solid var(--mg-glass-border);
}
.mini-avatar:first-child { margin-left: 0; }
.mini-avatar.more {
  background: var(--mg-glass-bg-strong);
  color: var(--mg-text-faint);
  font-size: 9px;
}

.card-summary {
  font-size: 12px;
  color: var(--mg-text-soft);
  line-height: 1.5;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

/* 加载 / 空 */
.loading-state {
  padding: 20px 0;
}
.empty-state {
  text-align: center;
  padding: 48px 20px;
}
.empty-icon {
  font-size: 48px;
  margin-bottom: 12px;
}
.empty-title {
  font-size: 15px;
  font-weight: 700;
  color: var(--mg-text);
  margin-bottom: 4px;
}
.empty-hint {
  font-size: 12px;
  color: var(--mg-text-soft);
}

.skeleton-card {
  background: var(--mg-glass-bg);
  border: 1.5px solid var(--mg-glass-border);
  border-radius: var(--mg-radius-md);
  padding: 16px;
  margin-bottom: 10px;
}
.skeleton-line {
  height: 12px;
  background: var(--mg-track);
  border-radius: var(--mg-radius-pill);
  margin-bottom: 8px;
  position: relative;
  overflow: hidden;
}
.skeleton-line::after {
  content: '';
  position: absolute;
  inset: 0;
  background: linear-gradient(90deg, transparent, rgba(255, 255, 255, 0.35), transparent);
  animation: shimmer 1.5s infinite;
}
.skeleton-line.w-60 { width: 60%; }
.skeleton-line.w-90 { width: 90%; }
.skeleton-line.w-40 { width: 40%; }
/* 分页信息 */
.pagination-info {
  text-align: center;
  font-size: 11px;
  color: var(--mg-text-faint);
  padding: 12px 0;
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
  -webkit-tap-highlight-color: transparent;
  display: flex;
  align-items: center;
  justify-content: center;
}
.header-action:active { background: var(--mg-glass-bg-strong); }
.header-action.primary {
  background: var(--mg-gradient-btn);
  color: var(--mg-on-primary);
  font-weight: 800;
  font-size: 22px;
  width: 44px;
  height: 44px;
  display: flex;
  align-items: center;
  justify-content: center;
  box-shadow: var(--mg-primary-shadow);
}

/* ActionSheet — 玻璃底由 .mg-glass-strong 提供, 此处只覆盖顶部圆角/占位 */
.action-overlay {
  position: fixed;
  inset: 0;
  z-index: 4000;
  background: rgba(0, 0, 0, 0.4);
  display: flex;
  align-items: flex-end;
  justify-content: center;
}
.action-panel {
  width: 100%;
  border-radius: var(--mg-radius-xl) var(--mg-radius-xl) 0 0;
  padding: 16px 16px calc(16px + var(--sab, 0px) + var(--tabbar-height, 76px));
}
.action-title {
  text-align: center;
  font-size: 13px;
  color: var(--mg-text-soft);
  margin-bottom: 12px;
}
.action-item {
  display: flex;
  align-items: center;
  gap: 14px;
  width: 100%;
  min-height: 48px;
  padding: 14px;
  margin-bottom: 6px;
  background: var(--mg-glass-bg);
  border: 1px solid var(--mg-glass-border);
  border-radius: var(--mg-radius-md);
  font-size: 15px;
  color: var(--mg-text);
  cursor: pointer;
  -webkit-tap-highlight-color: transparent;
  text-align: left;
  transition: transform 150ms ease, background 150ms ease;
}
.action-item:active { background: var(--mg-glass-bg-strong); transform: scale(0.99); }
.action-item.cancel {
  background: transparent;
  border: none;
  border-top: 1px solid var(--mg-glass-border);
  border-radius: 0;
  justify-content: center;
  margin-top: 4px;
  font-weight: 600;
  color: var(--mg-text-soft);
}
.action-icon {
  width: 32px;
  height: 32px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--mg-on-primary);
  font-size: 16px;
  font-weight: 600;
  flex-shrink: 0;
}

.action-sheet-enter-active, .action-sheet-leave-active {
  transition: opacity 0.25s ease;
}
.action-sheet-enter-active .action-panel, .action-sheet-leave-active .action-panel {
  transition: transform 0.3s var(--ease-sheet);
}
.action-sheet-enter-from, .action-sheet-leave-to { opacity: 0; }
.action-sheet-enter-from .action-panel, .action-sheet-leave-to .action-panel {
  transform: translateY(100%);
}

/* 搜索 Sheet — 玻璃底由 .mg-glass-strong 提供 */
.search-overlay {
  position: fixed;
  inset: 0;
  z-index: 3500;
  background: rgba(0, 0, 0, 0.4);
  display: flex;
  align-items: flex-end;
}
.search-panel {
  width: 100%;
  border-radius: var(--mg-radius-xl) var(--mg-radius-xl) 0 0;
  padding: 16px 16px calc(16px + var(--sab, 0px) + var(--tabbar-height, 76px));
}
.search-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 12px;
}
.search-header h3 {
  margin: 0;
  font-size: 16px;
  font-weight: 800;
  color: var(--mg-text-strong);
}
.search-header button {
  width: 44px;
  height: 44px;
  border-radius: 50%;
  background: transparent;
  border: none;
  font-size: 18px;
  color: var(--mg-text-soft);
  cursor: pointer;
}
.search-header button:active { background: var(--mg-glass-bg-strong); }
.search-input {
  width: 100%;
  padding: 12px 16px;
  border: 1px solid var(--mg-glass-border);
  border-radius: var(--mg-radius-md);
  background: var(--mg-glass-bg-strong);
  -webkit-backdrop-filter: blur(10px);
  backdrop-filter: blur(10px);
  font-size: 15px;
  outline: none;
  color: var(--mg-text);
  font-family: inherit;
  transition: border-color 150ms ease, box-shadow 150ms ease;
}
.search-input::placeholder { color: var(--mg-text-faint); }
.search-input:focus {
  border-color: var(--mg-primary);
  box-shadow: 0 0 0 3px var(--mg-tint-strong);
}
.search-actions {
  display: flex;
  gap: 8px;
  margin-top: 12px;
}
.btn-secondary, .btn-primary {
  flex: 1;
  min-height: 44px;
  padding: 10px;
  border-radius: var(--mg-radius-md);
  border: none;
  font-size: 14px;
  cursor: pointer;
  transition: transform 150ms ease;
}
.btn-secondary:active, .btn-primary:active { transform: scale(0.97); }
.btn-secondary {
  background: var(--mg-glass-bg-strong);
  border: 1.5px solid var(--mg-glass-border);
  color: var(--mg-primary);
  font-weight: 700;
}
.btn-primary {
  background: var(--mg-gradient-btn);
  color: var(--mg-on-primary);
  font-weight: 800;
  box-shadow: var(--mg-primary-shadow);
}

.search-sheet-enter-active, .search-sheet-leave-active {
  transition: opacity 0.25s ease;
}
.search-sheet-enter-active .search-panel, .search-sheet-leave-active .search-panel {
  transition: transform 0.3s ease;
}
.search-sheet-enter-from, .search-sheet-leave-to { opacity: 0; }
.search-sheet-enter-from .search-panel, .search-sheet-leave-to .search-panel {
  transform: translateY(100%);
}
</style>

<!-- 液态毛玻璃升级 (2026-08-31): dark mode 主色由 --mg-* token 层 ([data-theme="dark"]) 自动适配,
     原非 scoped dark 覆盖块已移除, 避免不透明色覆盖玻璃配方。
     保留本最小块: hairline 兜底 + mobile_dark_v33.spec [C] 守卫 (非 scoped dark 块必须存在且含 var(--color-*)) -->
<style>
[data-theme="dark"] .mobile-meeting-view .filter-chip {
  border-color: var(--color-border-light);
}
</style>