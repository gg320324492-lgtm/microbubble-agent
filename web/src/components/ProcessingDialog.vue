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
      <div class="processing-icon">
        <el-icon class="is-loading" :size="60" color="#FF7A5C"><Loading /></el-icon>
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
        <el-button type="primary" @click="goToDetail">查看纪要</el-button>
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
  background: #f0f0f0;
  color: #999;
}
.is-done .timeline-dot {
  background: #67c23a;
  color: white;
}
.is-current .timeline-dot {
  background: #ff7a5c;
  color: white;
  animation: pulse 1.5s infinite;
}
.is-failed .timeline-dot {
  background: #f56c6c;
  color: white;
}
.dot-empty {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: #ccc;
}
@keyframes pulse {
  0%, 100% { box-shadow: 0 0 0 0 rgba(255, 122, 92, 0.5); }
  50% { box-shadow: 0 0 0 8px rgba(255, 122, 92, 0); }
}
.stage-name {
  font-size: 16px;
  font-weight: 500;
}
.stage-detail {
  font-size: 13px;
  color: #999;
  margin-top: 4px;
}
.hint {
  margin-top: 40px;
  color: #999;
  font-size: 14px;
}
.done-actions {
  margin-top: 24px;
}
</style>
