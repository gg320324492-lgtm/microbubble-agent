<template>
  <div class="mobile-meeting-view">
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

    <main class="meeting-main" :style="{ paddingBottom: 'calc(var(--tabbar-height, 56px) + var(--sab, 0px))' }">
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

      <div v-else-if="meetings.length === 0" class="empty-state">
        <div class="empty-icon">📅</div>
        <div class="empty-title">暂无会议记录</div>
        <div class="empty-hint">点击右上角 + 创建</div>
      </div>

      <div v-else class="meeting-list">
        <button
          v-for="meeting in meetings"
          :key="meeting.id"
          type="button"
          class="meeting-card"
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

    <!-- 操作菜单（替代桌面 4 个按钮） -->
    <Teleport to="body">
      <Transition name="action-sheet">
        <div v-if="showActionSheet" class="action-overlay" @click.self="showActionSheet = false">
          <div class="action-panel">
            <div class="action-title">会议操作</div>
            <button type="button" class="action-item" @click="handleCreateMeeting">
              <span class="action-icon" style="background: #FF7A5C">+</span>
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
              <span class="action-icon" style="background: #67C23A">📋</span>
              <span>粘贴转录分析</span>
            </button>
            <button type="button" class="action-item" @click="handleStartLive">
              <span class="action-icon" style="background: #E6A23C">🎤</span>
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
              <span class="action-icon" style="background: #909399">🎙</span>
              <span>声纹识别测试</span>
            </button>
            <button
              id="meeting-voiceprint-enroll"
              type="button"
              name="meeting-voiceprint-enroll"
              class="action-item"
              aria-label="录入声纹"
              title="录入声纹"
              @click="handleEnrollVoice"
            >
              <span class="action-icon" style="background: #409EFF">🎙️</span>
              <span>录入声纹</span>
            </button>
            <button type="button" class="action-item cancel" @click="showActionSheet = false">取消</button>
          </div>
        </div>
      </Transition>
    </Teleport>

    <!-- 录入声纹：成员选择 Sheet（点 "录入声纹" ActionSheet 项后弹出） -->
    <Teleport to="body">
      <Transition name="member-picker-sheet">
        <div v-if="showEnrollPicker" class="member-picker-overlay" @click.self="closeEnrollPicker">
          <div class="member-picker-panel" :style="{ paddingBottom: 'calc(16px + var(--sab, 0px) + var(--tabbar-height, 56px))' }">
            <div class="member-picker-handle" />
            <div class="member-picker-header">
              <h3>选择要录入声纹的成员</h3>
              <button
                type="button"
                class="member-picker-close"
                aria-label="关闭"
                title="关闭"
                @click="closeEnrollPicker"
              >✕</button>
            </div>

            <div v-if="loadingMembers" class="member-picker-loading">
              <div class="loading-spinner" />
              <span>加载成员列表…</span>
            </div>

            <div v-else-if="availableMembers.length === 0" class="member-picker-empty">
              暂无可录入的成员
            </div>

            <div v-else class="member-picker-list">
              <button
                v-for="m in availableMembers"
                :key="m.id"
                type="button"
                class="member-picker-item"
                @click="selectMemberForEnroll(m)"
              >
                <div class="picker-avatar">{{ m.name?.charAt(0) || '?' }}</div>
                <div class="picker-info">
                  <div class="picker-name">{{ m.name }}</div>
                  <div class="picker-meta">
                    <span v-if="m.voice_enrolled_at" class="status-enrolled">
                      ✓ 已录入（{{ m.voice_sample_count || 1 }} 次）
                    </span>
                    <span v-else class="status-pending">未录入</span>
                  </div>
                </div>
                <span class="picker-arrow">›</span>
              </button>
            </div>
          </div>
        </div>
      </Transition>
    </Teleport>

    <!-- 搜索 Sheet -->
    <Teleport to="body">
      <Transition name="search-sheet">
        <div v-if="showSearch" class="search-overlay" @click.self="showSearch = false">
          <div class="search-panel">
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
import PageHeader from '@/components/mobile/PageHeader.vue'
import MeetingCreateDialog from '@/views/meeting/MeetingCreateDialog.vue'
import PasteAnalyzeDialog from '@/components/PasteAnalyzeDialog.vue'
import VoiceTestFlow from '@/components/mobile/VoiceTestFlow.vue'
import VoiceprintEnrollFlow from '@/components/mobile/VoiceprintEnrollFlow.vue'

const route = useRoute()
const router = useRouter()

const {
  meetings, total, currentPage, pageSize, loading,
  keyword, dateFrom, dateTo,
  fetchMeetings,
} = useMeeting()

const showActionSheet = ref(false)
const showSearch = ref(false)
const showCreateDialog = ref(false)
const showVoiceTest = ref(false)
const showEnrollPicker = ref(false)
const showEnroll = ref(false)
const pasteAnalyzeDialogRef = ref(null)
const searchInputRef = ref(null)

// 录入声纹：成员选择状态
const loadingMembers = ref(false)
const availableMembers = ref([])
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
function handleEnrollVoice() {
  showActionSheet.value = false
  // 关闭 ActionSheet 后打开成员选择 Sheet（fetch 在打开时拉取）
  fetchMembersForEnroll()
  showEnrollPicker.value = true
}
async function fetchMembersForEnroll() {
  loadingMembers.value = true
  try {
    // 包含已录入和未录入的成员（支持"重新录入"场景）
    const res = await axios.get('/api/v1/members', {
      params: { page_size: 100 },
    })
    availableMembers.value = res.data?.items || []
  } catch (e) {
    console.error(e)
    ElMessage.error('加载成员列表失败')
    availableMembers.value = []
  } finally {
    loadingMembers.value = false
  }
}
function closeEnrollPicker() {
  showEnrollPicker.value = false
}
function selectMemberForEnroll(m) {
  enrollingMember.value = m
  showEnrollPicker.value = false
  // 等 picker sheet 关闭动画结束再开 enroll flow（避免叠加渲染）
  setTimeout(() => {
    showEnroll.value = true
  }, 250)
}
function onEnrollSuccess() {
  showEnroll.value = false
  enrollingMember.value = null
  // 录入成功后刷新成员列表（再打开 picker 时状态最新）
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
  background: var(--color-bg-page);
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
  padding: 6px 14px;
  background: var(--color-bg-card);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-full);
  font-size: 13px;
  color: var(--color-text-regular);
  cursor: pointer;
  -webkit-tap-highlight-color: transparent;
}
.filter-chip.active {
  background: var(--color-primary);
  color: white;
  border-color: var(--color-primary);
}

/* 会议卡片 */
.meeting-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.meeting-card {
  display: flex;
  background: var(--color-bg-card);
  border: 1px solid var(--color-border-light);
  border-radius: var(--radius-md);
  padding: 12px;
  text-align: left;
  cursor: pointer;
  -webkit-tap-highlight-color: transparent;
  gap: 12px;
  align-items: flex-start;
}
.meeting-card:active {
  background: var(--color-bg-hover);
}

[data-theme="dark"] .meeting-card {
  border-color: var(--color-border-base);
}

.card-time-block {
  flex-shrink: 0;
  width: 60px;
  text-align: center;
  background: linear-gradient(135deg, var(--color-primary-bg), var(--color-accent-bg));
  border-radius: var(--radius-md);
  padding: 8px 4px;
}
.time-month {
  font-size: 11px;
  color: var(--color-text-regular);
  margin-bottom: 2px;
}
.time-day {
  font-size: 22px;
  font-weight: var(--font-weight-bold, 700);
  color: var(--color-primary);
  line-height: 1;
}
.time-hour {
  font-size: 10px;
  color: var(--color-text-secondary);
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
  font-weight: var(--font-weight-semibold, 600);
  color: var(--color-text-primary);
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
.status-dot.status-scheduled { background: #909399; }
.status-dot.status-recording { background: var(--color-warning, #E6A23C); animation: pulse-dot 1s infinite; }
.status-dot.status-processing { background: var(--color-warning, #E6A23C); animation: pulse-dot 1s infinite; }
.status-dot.status-completed { background: var(--color-success, #67C23A); }
.status-dot.status-cancelled { background: var(--color-info, #909399); }
.status-dot.status-error { background: var(--color-danger, #F56C6C); }
@keyframes pulse-dot {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.4; }
}

.card-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-bottom: 6px;
  font-size: 11px;
  color: var(--color-text-secondary);
}
.status-tag {
  padding: 1px 6px;
  border-radius: var(--radius-sm);
  font-size: 10px;
  background: var(--color-bg-page);
}
.tag-scheduled { background: var(--color-info-bg); color: var(--color-info); }
.tag-recording, .tag-processing { background: var(--color-warning-bg); color: var(--color-warning); }
.tag-completed { background: var(--color-success-bg); color: var(--color-success); }
.tag-cancelled { background: var(--color-bg-page); color: var(--color-text-secondary); }
.tag-error { background: var(--color-danger-bg); color: var(--color-danger); }

.meta-location { color: var(--color-text-secondary); }
.meta-audio { color: var(--color-primary); }

.card-participants { margin-bottom: 4px; }
.participants-avatars {
  display: flex;
  align-items: center;
}
.mini-avatar {
  width: 22px;
  height: 22px;
  border-radius: 50%;
  background: linear-gradient(135deg, var(--color-primary), var(--color-accent));
  color: white;
  font-size: 10px;
  font-weight: 600;
  display: flex;
  align-items: center;
  justify-content: center;
  margin-left: -6px;
  border: 2px solid var(--color-bg-card);
}
.mini-avatar:first-child { margin-left: 0; }
.mini-avatar.more {
  background: var(--color-bg-page);
  color: var(--color-text-secondary);
  font-size: 9px;
}

.card-summary {
  font-size: 12px;
  color: var(--color-text-secondary);
  line-height: 1.5;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

/* 加载 / 空 */
.loading-state, .empty-state {
  padding: 20px 0;
}
.empty-state {
  text-align: center;
  padding: 60px 20px;
}
.empty-icon {
  font-size: 48px;
  margin-bottom: 12px;
}
.empty-title {
  font-size: 15px;
  color: var(--color-text-regular);
  margin-bottom: 4px;
}
.empty-hint {
  font-size: 12px;
  color: var(--color-text-secondary);
}

.skeleton-card {
  background: var(--color-bg-card);
  border-radius: var(--radius-md);
  padding: 16px;
  margin-bottom: 10px;
}
.skeleton-line {
  height: 12px;
  background: var(--color-border);
  border-radius: var(--radius-sm);
  margin-bottom: 8px;
  position: relative;
  overflow: hidden;
}
.skeleton-line::after {
  content: '';
  position: absolute;
  inset: 0;
  background: linear-gradient(90deg, transparent, var(--color-bg-warm), transparent);
  animation: shimmer 1.5s infinite;
}
.skeleton-line.w-60 { width: 60%; }
.skeleton-line.w-90 { width: 90%; }
.skeleton-line.w-40 { width: 40%; }
@keyframes shimmer {
  0% { transform: translateX(-100%); }
  100% { transform: translateX(100%); }
}

/* 分页信息 */
.pagination-info {
  text-align: center;
  font-size: 11px;
  color: var(--color-text-secondary);
  padding: 12px 0;
}

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
  -webkit-tap-highlight-color: transparent;
}
.header-action:active { background: var(--color-primary-bg); }
.header-action.primary {
  background: linear-gradient(135deg, var(--color-primary), var(--color-primary-light));
  color: white;
  font-weight: 600;
  font-size: 22px;
  width: 36px;
  height: 36px;
  display: flex;
  align-items: center;
  justify-content: center;
}

/* ActionSheet */
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
  background: var(--color-bg-card);
  border-radius: var(--sheet-radius, 16px) var(--sheet-radius, 16px) 0 0;
  padding: 16px 16px calc(16px + var(--sab, 0px) + var(--tabbar-height, 56px));
}
.action-title {
  text-align: center;
  font-size: 13px;
  color: var(--color-text-secondary);
  margin-bottom: 12px;
}
.action-item {
  display: flex;
  align-items: center;
  gap: 14px;
  width: 100%;
  padding: 14px;
  margin-bottom: 6px;
  background: var(--color-bg-page);
  border: none;
  border-radius: var(--radius-md);
  font-size: 15px;
  color: var(--color-text-primary);
  cursor: pointer;
  -webkit-tap-highlight-color: transparent;
  text-align: left;
}
.action-item:active { background: var(--color-bg-hover); }
.action-item.cancel {
  background: var(--color-bg-card);
  border-top: 1px solid var(--color-border);
  border-radius: 0;
  justify-content: center;
  margin-top: 4px;
  font-weight: 500;
}
.action-icon {
  width: 32px;
  height: 32px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  color: white;
  font-size: 16px;
  font-weight: 600;
  flex-shrink: 0;
}

.action-sheet-enter-active, .action-sheet-leave-active {
  transition: opacity 0.25s ease;
}
.action-sheet-enter-active .action-panel, .action-sheet-leave-active .action-panel {
  transition: transform 0.3s cubic-bezier(0.32, 0.72, 0, 1);
}
.action-sheet-enter-from, .action-sheet-leave-to { opacity: 0; }
.action-sheet-enter-from .action-panel, .action-sheet-leave-to .action-panel {
  transform: translateY(100%);
}

/* 搜索 Sheet */
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
  background: var(--color-bg-card);
  border-radius: var(--sheet-radius, 16px) var(--sheet-radius, 16px) 0 0;
  padding: 16px 16px calc(16px + var(--sab, 0px) + var(--tabbar-height, 56px));
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
  font-weight: var(--font-weight-semibold, 600);
}
.search-header button {
  width: 32px;
  height: 32px;
  border-radius: 50%;
  background: transparent;
  border: none;
  font-size: 18px;
  color: var(--color-text-regular);
  cursor: pointer;
}
.search-input {
  width: 100%;
  padding: 12px 16px;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  background: var(--color-bg-page);
  font-size: 15px;
  outline: none;
  color: var(--color-text-primary);
}
.search-input:focus { border-color: var(--color-primary); }
.search-actions {
  display: flex;
  gap: 8px;
  margin-top: 12px;
}
.btn-secondary, .btn-primary {
  flex: 1;
  padding: 10px;
  border-radius: var(--radius-md);
  border: none;
  font-size: 14px;
  cursor: pointer;
}
.btn-secondary {
  background: var(--color-bg-page);
  color: var(--color-text-regular);
}
.btn-primary {
  background: var(--color-primary);
  color: white;
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

/* 录入声纹：成员选择 Sheet（与 MobileVoiceprintView 成员详情 Sheet 同款样式） */
.member-picker-overlay {
  position: fixed;
  inset: 0;
  z-index: 4500;
  background: rgba(0, 0, 0, 0.4);
  display: flex;
  align-items: flex-end;
}
.member-picker-panel {
  width: 100%;
  background: var(--color-bg-card);
  border-radius: var(--sheet-radius, 16px) var(--sheet-radius, 16px) 0 0;
  padding: 8px 20px;
  max-height: 75vh;
  display: flex;
  flex-direction: column;
}
.member-picker-handle {
  width: var(--sheet-handle-w, 36px);
  height: var(--sheet-handle-h, 4px);
  background: var(--color-border);
  border-radius: 2px;
  margin: 0 auto 12px;
  flex-shrink: 0;
}
.member-picker-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 4px 0 12px;
  border-bottom: 1px solid var(--color-border);
  flex-shrink: 0;
}
.member-picker-header h3 {
  margin: 0;
  font-size: 16px;
  font-weight: var(--font-weight-semibold, 600);
}
.member-picker-close {
  width: 32px;
  height: 32px;
  border-radius: 50%;
  background: transparent;
  border: none;
  font-size: 18px;
  color: var(--color-text-regular);
  cursor: pointer;
}
.member-picker-loading {
  padding: 32px 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 12px;
  color: var(--color-text-secondary);
  font-size: 13px;
}
.member-picker-empty {
  padding: 48px 20px;
  text-align: center;
  color: var(--color-text-secondary);
  font-size: 13px;
}
.member-picker-list {
  overflow-y: auto;
  -webkit-overflow-scrolling: touch;
  padding: 8px 0;
}
.member-picker-item {
  display: flex;
  align-items: center;
  gap: 12px;
  width: 100%;
  padding: 12px;
  background: transparent;
  border: none;
  border-radius: var(--radius-md);
  cursor: pointer;
  -webkit-tap-highlight-color: transparent;
  text-align: left;
}
.member-picker-item:active { background: var(--color-bg-hover); }
.picker-avatar {
  width: 40px;
  height: 40px;
  border-radius: 50%;
  background: linear-gradient(135deg, var(--color-primary), var(--color-accent));
  color: white;
  font-size: 16px;
  font-weight: var(--font-weight-semibold, 600);
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}
.picker-info { flex: 1; min-width: 0; }
.picker-name {
  font-size: 14px;
  font-weight: var(--font-weight-medium, 500);
  color: var(--color-text-primary);
  margin-bottom: 2px;
}
.picker-meta {
  font-size: 11px;
  color: var(--color-text-secondary);
}
.status-enrolled { color: var(--color-success, #67C23A); }
.status-pending { color: var(--color-text-placeholder); }
.picker-arrow {
  font-size: 18px;
  color: var(--color-text-placeholder);
  flex-shrink: 0;
}
.member-picker-sheet-enter-active, .member-picker-sheet-leave-active {
  transition: opacity 0.25s ease;
}
.member-picker-sheet-enter-active .member-picker-panel,
.member-picker-sheet-leave-active .member-picker-panel {
  transition: transform 0.3s cubic-bezier(0.32, 0.72, 0, 1);
}
.member-picker-sheet-enter-from, .member-picker-sheet-leave-to { opacity: 0; }
.member-picker-sheet-enter-from .member-picker-panel,
.member-picker-sheet-leave-to .member-picker-panel {
  transform: translateY(100%);
}
</style>