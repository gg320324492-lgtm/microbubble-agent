<template>
  <el-dialog
    v-model="visible"
    :show-close="false"
    :close-on-click-modal="false"
    :close-on-press-escape="false"
    width="500px"
    top="15vh"
  >
    <div class="processing-container">
      <!-- 完成时的 Confetti 效果 -->
      <div v-if="done" class="confetti-container">
        <div v-for="i in 20" :key="i" class="confetti-piece" :style="confettiStyle(i)" />
      </div>

      <div class="processing-icon">
        <el-icon v-if="!done" class="is-loading" :size="60" color="var(--color-primary)"><Loading /></el-icon>
        <div v-else class="done-icon">✅</div>
      </div>
      <h2 class="processing-title">{{ titleText }}</h2>

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
          <div class="timeline-dot">
            <el-icon v-if="isStageDone(idx)" :size="20"><Check /></el-icon>
            <el-icon v-else-if="isStageCurrent(idx)" class="is-loading" :size="20"><Loading /></el-icon>
            <span v-else class="dot-empty"></span>
          </div>
          <div class="timeline-content">
            <div class="stage-name">{{ stage.label }}</div>
            <div v-if="isStageCurrent(idx) && progress?.detail" class="stage-detail">
              {{ progress.detail }}
            </div>
          </div>
        </div>
      </div>

      <p class="hint">预计 30-60 秒，您可以先看看其他内容</p>

      <div v-if="done" class="done-actions">
        <el-button type="primary" class="btn-pulse" @click="goToDetail">查看纪要</el-button>
      </div>
    </div>
  </el-dialog>
</template>

<script setup>
import { ref, computed, watch, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import { Loading, Check } from '@element-plus/icons-vue'
import { useMeetingProgress } from '@/composables/useMeetingProgress'
import { useUserStore } from '@/stores/user'

const props = defineProps({
  meetingId: { type: Number, required: true },
})
const emit = defineEmits(['close'])

const visible = ref(true)
const router = useRouter()
const userStore = useUserStore()

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

// Confetti 样式生成
const confettiColors = ['#FF7A5C', '#FFB347', '#67C23A', '#409EFF', '#E6A23C', '#F56C6C']
function confettiStyle(i) {
  const color = confettiColors[i % confettiColors.length]
  const left = Math.random() * 100
  const delay = Math.random() * 0.5
  const size = 4 + Math.random() * 6
  const rotation = Math.random() * 360
  return {
    left: `${left}%`,
    animationDelay: `${delay}s`,
    width: `${size}px`,
    height: `${size * 0.6}px`,
    background: color,
    transform: `rotate(${rotation}deg)`,
  }
}

const currentStageIndex = computed(() => {
  if (!progress.value) return -1
  return STAGE_ORDER.indexOf(progress.value.stage)
})

const titleText = computed(() => {
  if (done.value) return '✅ 处理完成'
  if (error.value) return '⚠️ 连接失败'
  return 'AI 正在整理会议纪要...'
})

function isStageDone(idx) {
  return currentStageIndex.value > idx
}

function isStageCurrent(idx) {
  return currentStageIndex.value === idx
}

function isStageFailed(idx) {
  return error.value && currentStageIndex.value === idx
}

function goToDetail() {
  visible.value = false
  router.push(`/meetings/${props.meetingId}`)
}

watch(visible, (v) => {
  if (!v) emit('close')
})

watch(
  done,
  (v) => {
    if (v) {
      setTimeout(() => {
        if (visible.value) goToDetail()
      }, 3000)
    }
  },
  { immediate: false }
)

onUnmounted(() => {
  disconnect()
})

// 连接 WS
const token = localStorage.getItem('access_token')
if (token) {
  connect(props.meetingId, token)
} else {
  error.value = '未登录'
}
</script>

<style scoped>
.processing-container {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 20px;
}
.processing-icon {
  margin-bottom: 20px;
  position: relative;
  z-index: 1;
}
.done-icon {
  font-size: 60px;
  line-height: 1;
  animation: done-bounce 0.5s ease-out;
}
/* Confetti */
.confetti-container {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  overflow: hidden;
  pointer-events: none;
  z-index: 0;
}
.confetti-piece {
  position: absolute;
  top: -10px;
  border-radius: 2px;
  animation: confetti-fall 2.5s ease-out forwards;
}
.processing-title {
  font-size: 24px;
  margin-bottom: 40px;
  color: var(--color-text-primary, #333);
}
.timeline {
  display: flex;
  flex-direction: column;
  gap: 24px;
  width: 100%;
  max-width: 500px;
}
.timeline-item {
  display: flex;
  align-items: center;
  gap: 16px;
  opacity: 0.4;
  transition: opacity 0.3s;
}
.timeline-item.is-done,
.timeline-item.is-current {
  opacity: 1;
}
.timeline-dot {
  width: 32px;
  height: 32px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--color-border-light);
  color: var(--color-text-secondary);
}
.is-done .timeline-dot {
  background: var(--color-success);
  /* stylelint-disable-next-line color-named */
  color: white;
}
.is-current .timeline-dot {
  background: var(--color-primary);
  /* stylelint-disable-next-line color-named */
  color: white;
  animation: pulse 1.5s infinite;
}
.is-failed .timeline-dot {
  background: var(--color-danger);
  /* stylelint-disable-next-line color-named */
  color: white;
}
.dot-empty {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: var(--color-border-light);
}
.stage-name {
  font-size: 16px;
  font-weight: 500;
}
.stage-detail {
  font-size: 13px;
  color: var(--color-text-secondary);
  margin-top: 4px;
}
.hint {
  margin-top: 40px;
  color: var(--color-text-secondary);
  font-size: 14px;
}
.done-actions {
  margin-top: 24px;
  position: relative;
  z-index: 1;
}
.btn-pulse {
  animation: btn-glow 2s ease-in-out infinite;
}
</style>
