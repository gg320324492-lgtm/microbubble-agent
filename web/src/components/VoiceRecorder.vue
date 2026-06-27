<template>
  <div class="voice-recorder">
    <!-- 录音按钮 -->
    <div
      class="record-btn"
      :class="{ recording: isRecording, processing: isProcessing }"
      @mousedown="startRecording"
      @mouseup="stopRecording"
      @touchstart.prevent="startRecording"
      @touchend.prevent="stopRecording"
    >
      <el-icon v-if="!isRecording && !isProcessing" size="24">
        <Microphone />
      </el-icon>
      <el-icon v-else-if="isRecording" size="24" class="recording-icon">
        <VideoPause />
      </el-icon>
      <el-icon v-else size="24" class="processing-icon">
        <Loading />
      </el-icon>
    </div>

    <!-- 录音状态提示 -->
    <div class="record-tip">
      <span v-if="!isRecording && !isProcessing">按住说话</span>
      <span v-else-if="isRecording" class="recording-text">
        {{ formatDuration(recordingDuration) }} 松开结束
      </span>
      <span v-else>识别中...</span>
    </div>

    <!-- 录音波形动画 -->
    <div v-if="isRecording" class="waveform">
      <div v-for="i in 5" :key="i" class="wave-bar" :style="{ animationDelay: `${i * 0.1}s` }"></div>
    </div>
  </div>
</template>

<script setup>
import { ref, onUnmounted } from 'vue'
import { ElMessage } from 'element-plus'

const props = defineProps({
  disabled: Boolean
})

const emit = defineEmits(['record-start', 'record-stop', 'record-error'])

const isRecording = ref(false)
const isProcessing = ref(false)
const recordingDuration = ref(0)

let mediaRecorder = null
let audioChunks = []
let durationTimer = null

// 开始录音
const startRecording = async () => {
  if (props.disabled || isRecording.value || isProcessing.value) return

  try {
    const stream = await navigator.mediaDevices.getUserMedia({
      audio: {
        sampleRate: 16000,
        channelCount: 1,
        echoCancellation: true,
        noiseSuppression: true
      }
    })

    // 创建MediaRecorder
    mediaRecorder = new MediaRecorder(stream, {
      mimeType: getSupportedMimeType()
    })

    audioChunks = []

    mediaRecorder.ondataavailable = (event) => {
      if (event.data.size > 0) {
        audioChunks.push(event.data)
      }
    }

    mediaRecorder.onstop = () => {
      const audioBlob = new Blob(audioChunks, { type: mediaRecorder.mimeType })
      stream.getTracks().forEach(track => track.stop())
      emit('record-stop', audioBlob)
    }

    mediaRecorder.start(100) // 每100ms收集一次数据
    isRecording.value = true
    recordingDuration.value = 0

    // 开始计时
    durationTimer = setInterval(() => {
      recordingDuration.value++
    }, 1000)

    emit('record-start')

  } catch (error) {
    console.error('录音失败:', error)
    if (error.name === 'NotAllowedError') {
      ElMessage.error('请允许麦克风权限')
    } else {
      ElMessage.error('录音失败: ' + error.message)
    }
    emit('record-error', error)
  }
}

// 停止录音
const stopRecording = () => {
  if (!isRecording.value || !mediaRecorder) return

  mediaRecorder.stop()
  isRecording.value = false
  isProcessing.value = true

  if (durationTimer) {
    clearInterval(durationTimer)
    durationTimer = null
  }
}

// 处理完成（外部调用）
const processingComplete = () => {
  isProcessing.value = false
  recordingDuration.value = 0
}

// 获取支持的MIME类型
const getSupportedMimeType = () => {
  const types = [
    'audio/webm;codecs=opus',
    'audio/webm',
    'audio/ogg;codecs=opus',
    'audio/mp4'
  ]

  for (const type of types) {
    if (MediaRecorder.isTypeSupported(type)) {
      return type
    }
  }

  return 'audio/webm'
}

// 格式化时长
const formatDuration = (seconds) => {
  const mins = Math.floor(seconds / 60)
  const secs = seconds % 60
  return `${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`
}

// 清理
onUnmounted(() => {
  if (durationTimer) {
    clearInterval(durationTimer)
  }
  if (mediaRecorder && mediaRecorder.state === 'recording') {
    mediaRecorder.stop()
  }
})

defineExpose({
  processingComplete
})
</script>

<style scoped>
.voice-recorder {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
}

.record-btn {
  width: 56px;
  height: 56px;
  border-radius: 50%;
  background: var(--color-primary);
  color: var(--color-bg-card);
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  transition: all 0.3s;
  user-select: none;
}

.record-btn:hover {
  background: var(--color-primary);
  transform: scale(1.05);
}

.record-btn:active {
  transform: scale(0.95);
}

.record-btn.recording {
  background: var(--color-danger);
  animation: pulse 1.5s infinite;
}

.record-btn.processing {
  background: var(--color-info);
  cursor: not-allowed;
}

@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.6; }
}

.recording-icon {
  animation: blink 1s infinite;
}

@keyframes blink {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.5; }
}

.processing-icon {
  animation: spin 1s linear infinite;
}

.record-tip {
  font-size: 12px;
  color: var(--color-info);
}

.recording-text {
  color: var(--color-danger);
  font-weight: bold;
}

.waveform {
  display: flex;
  gap: 3px;
  align-items: center;
  height: 20px;
}

.wave-bar {
  width: 3px;
  height: 20px;
  background: var(--color-danger);
  border-radius: 2px;
  animation: wave 0.8s ease-in-out infinite;
  transform-origin: center center;
}

@keyframes wave {
  0%, 100% { transform: scaleY(0.4); }
  50% { transform: scaleY(1); }
}
</style>
