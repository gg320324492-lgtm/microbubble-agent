<template>
  <Teleport to="body">
    <Transition name="processing-sheet">
      <div v-if="visible" class="sheet-overlay" @click.self="onClose">
        <div class="sheet-panel">
          <!-- 顶部把手 + 标题 -->
          <div class="sheet-handle" />
          <div class="sheet-header">
            <div class="header-content">
              <div class="header-icon" :class="{ done: done }">
                <span v-if="!done" class="loading-spinner" />
                <span v-else class="done-icon">✅</span>
              </div>
              <div>
                <h3 class="sheet-title">{{ titleText }}</h3>
                <p class="sheet-subtitle">{{ subtitleText }}</p>
              </div>
            </div>
            <button
              v-if="done"
              type="button"
              class="header-close"
              aria-label="关闭"
              title="关闭"
              @click="onClose"
            >✕</button>
          </div>

          <!-- Confetti 效果（完成时） -->
          <div v-if="done" class="confetti-container">
            <div
              v-for="i in 30"
              :key="i"
              class="confetti-piece"
              :style="confettiStyle(i)"
            />
          </div>

          <!-- 时间线 -->
          <div class="timeline">
            <div
              v-for="(stage, idx) in stages"
              :key="stage.key"
              class="timeline-item"
              :class="{
                'is-done': isStageDone(idx),
                'is-current': isStageCurrent(idx),
                'is-failed': isStageFailed(idx),
              }"
            >
              <div class="timeline-connector" v-if="idx > 0">
                <div
                  class="connector-line"
                  :class="{ filled: isStageDone(idx - 1) || isStageDone(idx) }"
                />
              </div>
              <div class="timeline-dot">
                <span v-if="isStageDone(idx)" class="dot-icon done">✓</span>
                <span v-else-if="isStageFailed(idx)" class="dot-icon failed">✕</span>
                <span v-else-if="isStageCurrent(idx)" class="dot-icon current spinner" />
                <span v-else class="dot-empty" />
              </div>
              <div class="timeline-content">
                <div class="stage-name">{{ stage.label }}</div>
                <div
                  v-if="isStageCurrent(idx) && progress?.detail"
                  class="stage-detail"
                >
                  {{ progress.detail }}
                </div>
                <div
                  v-else-if="isStageFailed(idx) && error"
                  class="stage-detail error-text"
                >
                  {{ error }}
                </div>
              </div>
            </div>
          </div>

          <!-- 底部提示 -->
          <div class="sheet-hint">
            <p>{{ dynamicHint }}</p>
            <p v-if="!done && !error" class="hint-subtle">预计 30-60 秒</p>
          </div>

          <!-- 完成操作 -->
          <div v-if="done" class="done-actions">
            <button type="button" class="btn-secondary" @click="onClose">关闭</button>
            <button type="button" class="btn-primary" @click="goToDetail">查看纪要</button>
          </div>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<script setup>
/**
 * ProcessingSheet.vue — 移动端会议后处理进度（底部 sheet 形式）
 *
 * PR #5: 独立组件（不用 el-dialog + CSS 改造）
 * - 底部 sheet 形式（与移动端整体设计一致）
 * - 时间线 + 完成 Confetti 动画
 * - 桌面端仍用 ProcessingDialog，移动端用本组件
 *
 * 关键纪律：与后端 progress_service.py ProgressStage 枚举保持一致
 */

import { ref, computed, onMounted, onBeforeUnmount } from 'vue'
import { useRouter } from 'vue-router'
import { useMeetingProgress } from '@/composables/useMeetingProgress'

const props = defineProps({
  meetingId: { type: Number, required: true },
  modelValue: { type: Boolean, default: true },
})
const emit = defineEmits(['update:modelValue', 'close'])

const visible = ref(props.modelValue)
const router = useRouter()

const stages = [
  { key: 'downloading_audio', label: '下载音频' },
  { key: 'transcribing', label: '语音转写' },
  { key: 'identifying_speakers', label: '识别发言人' },
  { key: 'generating_analysis', label: 'AI 分析' },
  { key: 'creating_tasks', label: '创建任务' },
  { key: 'storing_results', label: '保存结果' },
]

const STAGE_ORDER = [
  'downloading_audio',
  'transcribing',
  'identifying_speakers',
  'generating_analysis',
  'creating_tasks',
  'storing_results',
  'done',
]

const { connect, disconnect, progress, done, error } = useMeetingProgress()

const titleText = computed(() => {
  if (error.value) return '处理失败'
  if (done.value) return '会议纪要已生成'
  // 2026-06-25 集成时改文案，与桌面端 ProcessingDialog 保持一致
  return 'AI 正在整理会议纪要...'
})

const subtitleText = computed(() => {
  if (error.value) return '请稍后重试或联系管理员'
  if (done.value) return '摘要 / 要点 / 决议 已生成'
  return 'AI 正在分析录音内容'
})

// 2026-06-25 v2：分阶段"可关闭"边界
// - 上传期（progress 空）：强提示"请勿关闭"，保护音频上传
// - Celery 启动后（progress 有值）：友好提示"可关闭"，后端独立处理
// - 完成态：引导去会议详情查看
// - 错误态：兜底提示重试
const dynamicHint = computed(() => {
  if (error.value) {
    return '处理失败，请稍后重试或联系管理员'
  }
  if (done.value) {
    return '处理已完成，您可以关闭此页面，稍后从会议详情查看纪要'
  }
  // Celery 已启动（WS 收到第一帧 stage 消息）→ 可安全关闭
  if (progress.value?.stage) {
    return '后台处理中，您可关闭此页面，结果将保存到会议详情'
  }
  // 前端还在 await upload + stop-recording，必须等
  return '正在上传音频，请勿关闭此页面'
})

function isStageDone(idx) {
  if (!progress.value?.stage) return false
  const currentIdx = STAGE_ORDER.indexOf(progress.value.stage)
  return currentIdx > idx
}

function isStageCurrent(idx) {
  if (!progress.value?.stage) {
    // 处理中但 progress 还未到（默认第一个）
    return idx === 0 && !done.value && !error.value
  }
  const currentIdx = STAGE_ORDER.indexOf(progress.value.stage)
  return currentIdx === idx
}

function isStageFailed(idx) {
  if (!error.value) return false
  // 失败的 stage 通常是当前 stage
  return progress.value?.stage === stages[idx]?.key
}

function onClose() {
  visible.value = false
  emit('update:modelValue', false)
  emit('close')
}

function goToDetail() {
  visible.value = false
  emit('update:modelValue', false)
  router.push(`/meetings/${props.meetingId}`)
}

// Confetti 样式
const confettiColors = ['#FF7A5C', '#FFB347', '#67C23A', '#409EFF', '#E6A23C', '#F56C6C']
function confettiStyle(i) {
  const color = confettiColors[i % confettiColors.length]
  const left = Math.random() * 100
  const delay = Math.random() * 0.6
  const size = 4 + Math.random() * 6
  const rotation = Math.random() * 360
  return {
    left: left + '%',
    background: color,
    width: size + 'px',
    height: size + 'px',
    animationDelay: delay + 's',
    transform: `rotate(${rotation}deg)`,
  }
}

// 生命周期
onMounted(() => {
  // 2026-06-25 修复：必须传 token，否则后端 WS URL 拼成 ?token=undefined → 鉴权拒绝
  const token = localStorage.getItem('access_token')
  if (token) {
    connect(props.meetingId, token)
  }
  // 无 token 时由 composable 内部 ws.onerror 触发 error.value = '连接失败'
})

onBeforeUnmount(() => {
  disconnect()
})
</script>

<style scoped>
.sheet-overlay {
  position: fixed;
  inset: 0;
  z-index: 4500;
  background: rgba(0, 0, 0, 0.5);
  display: flex;
  align-items: flex-end;
  justify-content: center;
}
.sheet-panel {
  width: 100%;
  max-height: 80vh;
  background: var(--color-bg-card);
  border-radius: var(--sheet-radius, 16px) var(--sheet-radius, 16px) 0 0;
  padding: 8px 20px calc(20px + var(--sab, 0px));
  overflow-y: auto;
  position: relative;
}

[data-theme="dark"] .sheet-panel {
  background: var(--color-bg-card);
}

/* 把手 */
.sheet-handle {
  width: var(--sheet-handle-w, 36px);
  height: var(--sheet-handle-h, 4px);
  background: var(--color-border);
  border-radius: 2px;
  margin: 0 auto 12px;
}

/* Header */
.sheet-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 20px;
}
.header-content {
  display: flex;
  align-items: center;
  gap: 12px;
}
.header-icon {
  width: 44px;
  height: 44px;
  border-radius: 50%;
  background: var(--color-primary-bg);
  display: flex;
  align-items: center;
  justify-content: center;
}
.header-icon.done {
  background: var(--color-success-bg, #f0f9eb);
}
.loading-spinner {
  width: 24px;
  height: 24px;
  border: 3px solid var(--color-primary);
  border-top-color: transparent;
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}
.done-icon {
  font-size: 24px;
}
@keyframes spin { to { transform: rotate(360deg); } }

.sheet-title {
  font-size: 16px;
  font-weight: var(--font-weight-semibold, 600);
  color: var(--color-text-primary);
  margin: 0 0 2px;
}
.sheet-subtitle {
  font-size: 12px;
  color: var(--color-text-secondary);
  margin: 0;
}
.header-close {
  width: 32px;
  height: 32px;
  border-radius: 50%;
  background: transparent;
  border: none;
  font-size: 18px;
  color: var(--color-text-regular);
  cursor: pointer;
}
.header-close:active { background: var(--color-bg-hover); }

/* Confetti */
.confetti-container {
  position: absolute;
  inset: 0;
  pointer-events: none;
  overflow: hidden;
  border-radius: var(--sheet-radius, 16px) var(--sheet-radius, 16px) 0 0;
}
.confetti-piece {
  position: absolute;
  top: -10px;
  border-radius: 2px;
  animation: confetti-fall 2s ease-out forwards;
}
@keyframes confetti-fall {
  0% {
    transform: translateY(0) rotate(0deg);
    opacity: 1;
  }
  100% {
    transform: translateY(80vh) rotate(720deg);
    opacity: 0;
  }
}

/* 时间线 */
.timeline {
  display: flex;
  flex-direction: column;
  gap: 0;
  padding: 0 8px;
}
.timeline-item {
  display: flex;
  gap: 12px;
  position: relative;
  padding: 8px 0;
}
.timeline-connector {
  position: absolute;
  top: -16px;
  left: 13px;
  height: 16px;
  width: 2px;
  display: flex;
  align-items: center;
  justify-content: center;
}
.connector-line {
  width: 2px;
  height: 100%;
  background: var(--color-border);
}
.connector-line.filled {
  background: linear-gradient(180deg, var(--color-success, #67C23A), var(--color-primary));
}
.timeline-dot {
  flex-shrink: 0;
  width: 28px;
  height: 28px;
  border-radius: 50%;
  background: var(--color-bg-page);
  border: 2px solid var(--color-border);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1;
}
.timeline-item.is-current .timeline-dot {
  background: var(--color-primary-bg);
  border-color: var(--color-primary);
}
.timeline-item.is-done .timeline-dot {
  background: var(--color-success, #67C23A);
  border-color: var(--color-success, #67C23A);
}
.timeline-item.is-failed .timeline-dot {
  background: var(--color-danger-bg);
  border-color: var(--color-danger, #F56C6C);
}
.dot-icon {
  font-size: 14px;
  font-weight: 700;
  color: white;
}
.dot-icon.done { color: white; }
.dot-icon.failed { color: var(--color-danger, #F56C6C); }
.dot-icon.current.spinner {
  width: 12px;
  height: 12px;
  border: 2px solid var(--color-primary);
  border-top-color: transparent;
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}
.dot-empty {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--color-border);
}

.timeline-content {
  flex: 1;
  padding-top: 2px;
}
.stage-name {
  font-size: 14px;
  color: var(--color-text-primary);
  font-weight: var(--font-weight-medium, 500);
}
.timeline-item:not(.is-done):not(.is-current):not(.is-failed) .stage-name {
  color: var(--color-text-secondary);
}
.stage-detail {
  font-size: 12px;
  color: var(--color-text-secondary);
  margin-top: 2px;
}
.stage-detail.error-text {
  color: var(--color-danger, #F56C6C);
}

/* 提示 */
.sheet-hint {
  margin-top: 16px;
  padding: 12px;
  background: var(--color-bg-page);
  border-radius: var(--radius-sm);
  text-align: center;
  font-size: 12px;
  color: var(--color-text-secondary);
  line-height: 1.6;
}
.sheet-hint p { margin: 2px 0; }
.sheet-hint .hint-subtle {
  margin-top: 4px;
  font-size: 11px;
  opacity: 0.75;
}

/* 操作 */
.done-actions {
  display: flex;
  gap: 12px;
  margin-top: 20px;
}
.btn-secondary, .btn-primary {
  flex: 1;
  padding: 12px;
  border-radius: var(--radius-md);
  border: none;
  font-size: 14px;
  font-weight: var(--font-weight-medium, 500);
  cursor: pointer;
  -webkit-tap-highlight-color: transparent;
}
.btn-secondary {
  background: var(--color-bg-page);
  color: var(--color-text-primary);
  border: 1px solid var(--color-border);
}
.btn-primary {
  background: linear-gradient(135deg, var(--color-primary), var(--color-primary-light));
  color: white;
}

/* 进出动画 */
.processing-sheet-enter-active, .processing-sheet-leave-active {
  transition: opacity 0.25s ease;
}
.processing-sheet-enter-active .sheet-panel, .processing-sheet-leave-active .sheet-panel {
  transition: transform 0.3s cubic-bezier(0.32, 0.72, 0, 1);
}
.processing-sheet-enter-from, .processing-sheet-leave-to { opacity: 0; }
.processing-sheet-enter-from .sheet-panel, .processing-sheet-leave-to .sheet-panel {
  transform: translateY(100%);
}
</style>