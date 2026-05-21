<template>
  <div class="live-transcript">
    <!-- 状态栏 -->
    <div class="transcript-header">
      <div class="status-info">
        <span :class="['status-badge', status]">
          <span class="status-dot"></span>
          {{ statusText }}
        </span>
        <span v-if="isRecording" class="duration">{{ formatDuration(duration) }}</span>
      </div>
      <div class="header-actions">
        <el-button
          v-if="!isRecording"
          type="primary"
          size="small"
          @click="startTranscript"
        >
          <el-icon><VideoCamera /></el-icon>
          开始转写
        </el-button>
        <el-button
          v-else
          type="danger"
          size="small"
          @click="stopTranscript"
        >
          <el-icon><VideoPause /></el-icon>
          停止转写
        </el-button>
      </div>
    </div>

    <!-- 转写内容 -->
    <div class="transcript-content" ref="contentRef">
      <div v-if="transcriptItems.length === 0" class="empty-state">
        <el-icon size="48" color="#dcdfe6"><Document /></el-icon>
        <p>点击"开始转写"按钮开始实时记录会议内容</p>
      </div>

      <div
        v-for="(item, index) in transcriptItems"
        :key="index"
        class="transcript-item"
      >
        <div class="item-time">{{ formatTime(item.timestamp) }}</div>
        <div class="item-speaker">
          <el-tag size="small" :type="getSpeakerType(item.speaker)">
            {{ item.speaker }}
          </el-tag>
        </div>
        <div class="item-text">{{ item.text }}</div>
      </div>

      <!-- 实时识别中 -->
      <div v-if="isRecording && currentText" class="transcript-item realtime">
        <div class="item-time">{{ formatTime(new Date()) }}</div>
        <div class="item-speaker">
          <el-tag size="small" type="warning">识别中</el-tag>
        </div>
        <div class="item-text">{{ currentText }}...</div>
      </div>
    </div>

    <!-- 统计信息 -->
    <div class="transcript-footer">
      <div class="stats">
        <span>共 {{ transcriptItems.length }} 条记录</span>
        <span>{{ uniqueSpeakers.length }} 位发言人</span>
      </div>
      <div class="footer-actions">
        <el-button text size="small" @click="exportTranscript">
          <el-icon><Download /></el-icon>
          导出
        </el-button>
        <el-button text size="small" @click="clearTranscript">
          <el-icon><Delete /></el-icon>
          清空
        </el-button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, nextTick, onUnmounted } from 'vue'
import { ElMessage } from 'element-plus'

const props = defineProps({
  meetingId: {
    type: [Number, String],
    required: true
  }
})

const emit = defineEmits(['transcript-update', 'transcript-complete'])

const contentRef = ref(null)
const status = ref('idle') // idle, recording, paused
const isRecording = ref(false)
const duration = ref(0)
const currentText = ref('')
const transcriptItems = ref([])

let ws = null
let durationTimer = null
let mediaRecorder = null
let audioStream = null

// 状态文本
const statusText = computed(() => {
  const map = {
    idle: '未开始',
    recording: '转写中',
    paused: '已暂停'
  }
  return map[status.value] || '未知'
})

// 唯一发言人
const uniqueSpeakers = computed(() => {
  const speakers = new Set(transcriptItems.value.map(item => item.speaker))
  return Array.from(speakers)
})

// 开始转写
const startTranscript = async () => {
  try {
    // 获取麦克风权限
    audioStream = await navigator.mediaDevices.getUserMedia({
      audio: {
        sampleRate: 16000,
        channelCount: 1,
        echoCancellation: true,
        noiseSuppression: true
      }
    })

    // 建立WebSocket连接
    const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    const wsUrl = `${wsProtocol}//${window.location.host}/ws/meeting/${props.meetingId}/transcript`
    ws = new WebSocket(wsUrl)

    ws.onopen = () => {
      console.log('WebSocket连接已建立')
      status.value = 'recording'
      isRecording.value = true
      duration.value = 0

      // 开始计时
      durationTimer = setInterval(() => {
        duration.value++
      }, 1000)

      // 开始录音并发送
      startRecording()
    }

    ws.onmessage = (event) => {
      const data = JSON.parse(event.data)

      if (data.type === 'transcript') {
        // 添加转写条目
        transcriptItems.value.push({
          timestamp: new Date(),
          speaker: data.speaker || '参会者',
          text: data.text
        })

        // 清空当前识别文本
        currentText.value = ''

        // 滚动到底部
        scrollToBottom()

        // 触发更新事件
        emit('transcript-update', transcriptItems.value)
      } else if (data.type === 'interim') {
        // 临时识别结果
        currentText.value = data.text
      }
    }

    ws.onerror = (error) => {
      console.error('WebSocket错误:', error)
      ElMessage.error('连接失败，请重试')
      stopTranscript()
    }

    ws.onclose = () => {
      console.log('WebSocket连接已关闭')
    }

  } catch (error) {
    console.error('启动转写失败:', error)
    if (error.name === 'NotAllowedError') {
      ElMessage.error('请允许麦克风权限')
    } else {
      ElMessage.error('启动转写失败: ' + error.message)
    }
  }
}

// 开始录音
const startRecording = () => {
  if (!audioStream) return

  const options = { mimeType: 'audio/webm;codecs=opus' }
  mediaRecorder = new MediaRecorder(audioStream, options)

  mediaRecorder.ondataavailable = (event) => {
    if (event.data.size > 0 && ws && ws.readyState === WebSocket.OPEN) {
      ws.send(event.data)
    }
  }

  mediaRecorder.start(500) // 每500ms发送一次数据
}

// 停止转写
const stopTranscript = () => {
  // 停止录音
  if (mediaRecorder && mediaRecorder.state === 'recording') {
    mediaRecorder.stop()
  }

  // 关闭音频流
  if (audioStream) {
    audioStream.getTracks().forEach(track => track.stop())
    audioStream = null
  }

  // 关闭WebSocket
  if (ws) {
    ws.close()
    ws = null
  }

  // 停止计时
  if (durationTimer) {
    clearInterval(durationTimer)
    durationTimer = null
  }

  status.value = 'idle'
  isRecording.value = false
  currentText.value = ''

  // 触发完成事件
  emit('transcript-complete', transcriptItems.value)

  ElMessage.success('转写已停止')
}

// 导出转写内容
const exportTranscript = () => {
  if (transcriptItems.value.length === 0) {
    ElMessage.warning('暂无转写内容')
    return
  }

  // 生成文本内容
  let content = '会议转写记录\n'
  content += '='.repeat(50) + '\n\n'

  transcriptItems.value.forEach(item => {
    content += `[${formatTime(item.timestamp)}] ${item.speaker}:\n`
    content += `${item.text}\n\n`
  })

  // 下载文件
  const blob = new Blob([content], { type: 'text/plain;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `会议转写_${new Date().toISOString().slice(0, 10)}.txt`
  a.click()
  URL.revokeObjectURL(url)

  ElMessage.success('导出成功')
}

// 清空转写内容
const clearTranscript = () => {
  transcriptItems.value = []
  ElMessage.success('已清空')
}

// 滚动到底部
const scrollToBottom = () => {
  nextTick(() => {
    if (contentRef.value) {
      contentRef.value.scrollTop = contentRef.value.scrollHeight
    }
  })
}

// 格式化时间
const formatTime = (date) => {
  if (!date) return ''
  return new Date(date).toLocaleTimeString('zh-CN', {
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit'
  })
}

// 格式化时长
const formatDuration = (seconds) => {
  const mins = Math.floor(seconds / 60)
  const secs = seconds % 60
  return `${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`
}

// 获取发言人标签类型
const getSpeakerType = (speaker) => {
  const types = ['', 'success', 'warning', 'info', 'danger']
  const index = uniqueSpeakers.value.indexOf(speaker) % types.length
  return types[index]
}

// 清理
onUnmounted(() => {
  if (isRecording.value) {
    stopTranscript()
  }
})

defineExpose({
  startTranscript,
  stopTranscript,
  getTranscript: () => transcriptItems.value
})
</script>

<style scoped>
.live-transcript {
  display: flex;
  flex-direction: column;
  height: 100%;
  background: #fff;
  border-radius: 8px;
  border: 1px solid #ebeef5;
}

.transcript-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 16px;
  border-bottom: 1px solid #ebeef5;
}

.status-info {
  display: flex;
  align-items: center;
  gap: 12px;
}

.status-badge {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
  color: #909399;
}

.status-badge.recording {
  color: #f56c6c;
}

.status-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: #909399;
}

.status-badge.recording .status-dot {
  background: #f56c6c;
  animation: blink 1s infinite;
}

@keyframes blink {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.5; }
}

.duration {
  font-size: 14px;
  font-weight: bold;
  color: #303133;
  font-family: monospace;
}

.transcript-content {
  flex: 1;
  overflow-y: auto;
  padding: 16px;
  max-height: 400px;
}

.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 200px;
  color: #909399;
}

.empty-state p {
  margin-top: 12px;
  font-size: 13px;
}

.transcript-item {
  display: flex;
  gap: 12px;
  padding: 8px 0;
  border-bottom: 1px solid #f0f0f0;
}

.transcript-item:last-child {
  border-bottom: none;
}

.transcript-item.realtime {
  opacity: 0.7;
}

.item-time {
  font-size: 12px;
  color: #909399;
  font-family: monospace;
  white-space: nowrap;
}

.item-speaker {
  flex-shrink: 0;
}

.item-text {
  font-size: 14px;
  color: #303133;
  line-height: 1.5;
}

.transcript-footer {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 16px;
  border-top: 1px solid #ebeef5;
  font-size: 12px;
  color: #909399;
}

.stats {
  display: flex;
  gap: 16px;
}

.footer-actions {
  display: flex;
  gap: 8px;
}
</style>
