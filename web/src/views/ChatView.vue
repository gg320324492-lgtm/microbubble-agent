<template>
  <div class="chat-container">
    <!-- 对话区域 -->
    <el-card class="chat-card">
      <template #header>
        <div class="chat-header">
          <div class="header-info">
            <el-avatar :size="40" style="background: #409eff">
              <el-icon size="24"><Aim /></el-icon>
            </el-avatar>
            <div>
              <div class="agent-name">小气助手</div>
              <div class="agent-status">
                <span class="status-dot"></span>
                在线
              </div>
            </div>
          </div>
          <div class="header-actions">
            <el-tooltip content="切换语音模式">
              <el-button
                :type="voiceMode ? 'primary' : 'default'"
                circle
                @click="toggleVoiceMode"
              >
                <el-icon><Microphone /></el-icon>
              </el-button>
            </el-tooltip>
            <el-tooltip content="清空对话">
              <el-button circle @click="clearChat">
                <el-icon><Delete /></el-icon>
              </el-button>
            </el-tooltip>
          </div>
        </div>
      </template>

      <!-- 消息列表 -->
      <div class="message-list" ref="messageListRef">
        <!-- 欢迎消息 -->
        <div class="welcome-banner" v-if="messages.length === 1">
          <div class="welcome-icon">
            <el-icon size="48" color="#409eff"><Aim /></el-icon>
          </div>
          <h2>你好，我是小气！</h2>
          <p>微纳米气泡课题组的AI助手</p>
          <div class="quick-actions">
            <el-button size="small" @click="sendQuickMessage('查看我的任务')">
              📋 我的任务
            </el-button>
            <el-button size="small" @click="sendQuickMessage('最近有什么会议？')">
              📅 最近会议
            </el-button>
            <el-button size="small" @click="sendQuickMessage('水处理项目进度怎么样？')">
              📊 项目进度
            </el-button>
            <el-button size="small" @click="sendQuickMessage('微纳米气泡的生成方法有哪些？')">
              📚 知识问答
            </el-button>
          </div>
        </div>

        <!-- 消息列表 -->
        <div
          v-for="(msg, index) in messages"
          :key="index"
          :class="['message-item', msg.role === 'user' ? 'user-message' : 'agent-message']"
        >
          <el-avatar
            :size="36"
            :style="{ background: msg.role === 'user' ? '#67c23a' : '#409eff' }"
          >
            {{ msg.role === 'user' ? '我' : '气' }}
          </el-avatar>
          <div class="message-content">
            <div class="message-bubble">
              <!-- 图片消息 -->
              <div v-if="msg.type === 'image'" class="image-message">
                <img
                  v-if="msg.imageUrl"
                  :src="msg.imageUrl"
                  alt="用户发送的图片"
                  @click="previewImage(msg.imageUrl)"
                />
                <div v-if="msg.content !== '[图片]'" class="message-text" v-html="formatMessage(msg.content)"></div>
              </div>

              <!-- 文件消息 -->
              <div v-else-if="msg.type === 'file'" class="file-message">
                <div class="file-attachment">
                  <el-icon size="24" color="#409eff"><Document /></el-icon>
                  <span class="file-attachment-name">{{ msg.fileName || '文件' }}</span>
                </div>
                <div v-if="msg.content && !msg.content.startsWith('[文件:')" class="message-text" v-html="formatMessage(msg.content)"></div>
              </div>

              <!-- 文字消息 -->
              <div v-else-if="msg.type !== 'voice'" class="message-text" v-html="formatMessage(msg.content)"></div>

              <!-- 语音消息 -->
              <div v-else class="voice-message">
                <div class="voice-icon" @click="playVoice(msg)">
                  <el-icon size="20"><VideoPlay /></el-icon>
                </div>
                <div class="voice-duration">{{ msg.duration || '00:05' }}</div>
                <AudioPlayer
                  v-if="msg.audioUrl"
                  :src="msg.audioUrl"
                  ref="audioPlayerRef"
                  style="display: none"
                />
              </div>
            </div>
            <div class="message-time">{{ formatTime(msg.timestamp) }}</div>
          </div>
        </div>

        <!-- 加载中 -->
        <div v-if="loading" class="message-item agent-message">
          <el-avatar :size="36" style="background: #409eff">气</el-avatar>
          <div class="message-content">
            <div class="message-bubble">
              <div class="typing-indicator">
                <span></span>
                <span></span>
                <span></span>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- 输入区域 -->
      <div class="input-area">
        <!-- 语音模式 -->
        <div v-if="voiceMode" class="voice-input-area">
          <VoiceRecorder
            ref="voiceRecorderRef"
            :disabled="loading"
            @record-start="onRecordStart"
            @record-stop="onRecordStop"
            @record-error="onRecordError"
          />
          <div class="voice-mode-tip">
            <span>点击切换回</span>
            <el-button text type="primary" @click="toggleVoiceMode">文字模式</el-button>
          </div>
        </div>

        <!-- 文字模式 -->
        <div v-else class="text-input-area">
          <!-- 图片预览 -->
          <div v-if="selectedImage" class="image-preview">
            <img :src="imagePreviewUrl" alt="预览" />
            <el-button
              class="remove-image-btn"
              :icon="Close"
              circle
              size="small"
              @click="removeImage"
            />
          </div>

          <!-- 文件预览 -->
          <div v-if="selectedFile && filePreviewType === 'document'" class="file-preview">
            <el-icon size="20" color="#409eff"><Document /></el-icon>
            <span class="file-name">{{ selectedFile.name }}</span>
            <span class="file-size">({{ (selectedFile.size / 1024).toFixed(0) }}KB)</span>
            <el-button
              class="remove-image-btn"
              :icon="Close"
              circle
              size="small"
              @click="removeFile"
            />
          </div>

          <el-input
            v-model="inputText"
            placeholder="输入消息... (Enter发送，Shift+Enter换行)"
            :rows="1"
            type="textarea"
            resize="none"
            @keydown="handleKeydown"
            :disabled="loading"
          />

          <!-- 图片上传按钮 -->
          <el-tooltip content="发送图片">
            <el-button
              circle
              @click="triggerImageUpload"
              :disabled="loading"
            >
              <el-icon><Picture /></el-icon>
            </el-button>
          </el-tooltip>

          <!-- 文件上传按钮 -->
          <el-tooltip content="发送文件">
            <el-button
              circle
              @click="triggerFileUpload"
              :disabled="loading"
            >
              <el-icon><Paperclip /></el-icon>
            </el-button>
          </el-tooltip>

          <input
            ref="imageInputRef"
            type="file"
            accept="image/*"
            style="display: none"
            @change="handleImageSelect"
          />

          <input
            ref="fileInputRef"
            type="file"
            accept=".pdf,.doc,.docx,.xls,.xlsx,.txt,.md"
            style="display: none"
            @change="handleFileSelect"
          />

          <el-button
            type="primary"
            @click="sendMessage"
            :disabled="(!inputText.trim() && !selectedImage && !selectedFile) || loading"
            :loading="loading"
          >
            <el-icon><Promotion /></el-icon>
            发送
          </el-button>
        </div>
      </div>
    </el-card>
  </div>
</template>

<script setup>
import { ref, nextTick, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { Close, Picture, Paperclip, Document } from '@element-plus/icons-vue'
import axios from 'axios'
import dayjs from 'dayjs'
import VoiceRecorder from '@/components/VoiceRecorder.vue'
import AudioPlayer from '@/components/AudioPlayer.vue'

const messageListRef = ref(null)
const voiceRecorderRef = ref(null)
const audioPlayerRef = ref(null)
const imageInputRef = ref(null)
const fileInputRef = ref(null)
const inputText = ref('')
const loading = ref(false)
const voiceMode = ref(false)
const sessionId = `user_${Date.now()}`
const selectedImage = ref(null)
const imagePreviewUrl = ref('')
const selectedFile = ref(null)
const filePreviewType = ref('') // 'image' or 'document'

const messages = ref([
  {
    role: 'assistant',
    content: '你好！我是小气，微纳米气泡课题组的AI助手。我可以帮你管理任务、查询会议、回答专业问题。有什么可以帮你的吗？',
    timestamp: new Date(),
    type: 'text'
  }
])

// 触发图片上传
const triggerImageUpload = () => {
  imageInputRef.value?.click()
}

// 处理图片选择
const handleImageSelect = (event) => {
  const file = event.target.files[0]
  if (!file) return

  // 检查文件类型
  if (!file.type.startsWith('image/')) {
    ElMessage.error('请选择图片文件')
    return
  }

  // 检查文件大小（限制10MB）
  if (file.size > 10 * 1024 * 1024) {
    ElMessage.error('图片大小不能超过10MB')
    return
  }

  selectedImage.value = file
  imagePreviewUrl.value = URL.createObjectURL(file)

  // 清空input以允许重复选择同一文件
  event.target.value = ''
}

// 移除选中的图片
const removeImage = () => {
  selectedImage.value = null
  imagePreviewUrl.value = ''
}

// 触发文件上传
const triggerFileUpload = () => {
  fileInputRef.value?.click()
}

// 处理文件选择
const handleFileSelect = (event) => {
  const file = event.target.files[0]
  if (!file) return

  if (file.size > 50 * 1024 * 1024) {
    ElMessage.error('文件大小不能超过50MB')
    return
  }

  selectedFile.value = file
  filePreviewType.value = 'document'
  event.target.value = ''
}

// 移除选中的文件
const removeFile = () => {
  selectedFile.value = null
  filePreviewType.value = ''
}

// 发送消息（支持文字、图片和文件）
const sendMessage = async () => {
  const text = inputText.value.trim()
  if ((!text && !selectedImage.value && !selectedFile.value) || loading.value) return

  // 构建用户消息内容
  let userContent = text
  let userMessageType = 'text'

  if (selectedImage.value) {
    userMessageType = 'image'
    userContent = text ? `[图片] ${text}` : '[图片]'
  } else if (selectedFile.value) {
    userMessageType = 'file'
    userContent = text ? `[文件: ${selectedFile.value.name}] ${text}` : `[文件: ${selectedFile.value.name}]`
  }

  // 添加用户消息
  messages.value.push({
    role: 'user',
    content: userContent,
    timestamp: new Date(),
    type: userMessageType,
    imageUrl: selectedImage.value ? imagePreviewUrl.value : null,
    fileName: selectedFile.value?.name || null
  })

  const currentImage = selectedImage.value
  const currentFile = selectedFile.value
  inputText.value = ''
  selectedImage.value = null
  imagePreviewUrl.value = ''
  selectedFile.value = null
  filePreviewType.value = ''
  loading.value = true
  scrollToBottom()

  try {
    let res

    if (currentFile) {
      // 发送文件消息
      const formData = new FormData()
      formData.append('message', text || '')
      formData.append('session_id', sessionId)
      formData.append('file', currentFile)

      res = await axios.post('/api/v1/chat/file', formData, {
        headers: { 'Content-Type': 'multipart/form-data' }
      })
    } else if (currentImage) {
      // 发送图片消息
      const formData = new FormData()
      formData.append('message', text || '请描述这张图片')
      formData.append('session_id', sessionId)
      formData.append('image', currentImage)

      res = await axios.post('/api/v1/chat/image', formData, {
        headers: { 'Content-Type': 'multipart/form-data' }
      })
    } else {
      // 发送文字消息
      res = await axios.post('/api/v1/chat', {
        message: text,
        session_id: sessionId
      })
    }

    // 添加AI回复
    messages.value.push({
      role: 'assistant',
      content: res.data.content,
      timestamp: new Date(),
      type: 'text'
    })
  } catch (e) {
    console.error('发送失败:', e)
    ElMessage.error(e.response?.data?.detail || '发送失败，请重试')
    messages.value.push({
      role: 'assistant',
      content: '抱歉，我暂时无法回复，请稍后再试。',
      timestamp: new Date(),
      type: 'text'
    })
  } finally {
    loading.value = false
    scrollToBottom()
  }
}

// 发送快捷消息
const sendQuickMessage = (text) => {
  inputText.value = text
  sendMessage()
}

// 处理键盘事件
const handleKeydown = (e) => {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault()
    sendMessage()
  }
}

// 清空对话
const clearChat = () => {
  messages.value = [{
    role: 'assistant',
    content: '对话已清空，有什么可以帮你的吗？',
    timestamp: new Date(),
    type: 'text'
  }]
}

// 切换语音模式
const toggleVoiceMode = () => {
  voiceMode.value = !voiceMode.value
}

// 录音开始
const onRecordStart = () => {
  console.log('录音开始')
}

// 录音结束
const onRecordStop = async (audioBlob) => {
  console.log('录音结束，音频大小:', audioBlob.size)

  // 添加用户语音消息
  const userMsg = {
    role: 'user',
    content: '[语音消息]',
    timestamp: new Date(),
    type: 'voice',
    audioUrl: URL.createObjectURL(audioBlob),
    duration: '00:05'
  }
  messages.value.push(userMsg)
  scrollToBottom()

  // 发送到后端进行识别和对话
  loading.value = true

  try {
    const formData = new FormData()
    formData.append('audio', audioBlob, 'recording.webm')
    formData.append('session_id', sessionId)

    const res = await axios.post('/api/v1/voice/chat', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
      responseType: 'blob'
    })

    // 获取识别结果（从响应头）
    const userText = res.headers['x-user-text'] || '语音识别完成'
    const responseText = res.headers['x-response-text'] || '回复生成完成'

    // 更新用户消息显示识别结果
    userMsg.content = userText

    // 创建AI语音回复
    const audioUrl = URL.createObjectURL(res.data)

    messages.value.push({
      role: 'assistant',
      content: responseText,
      timestamp: new Date(),
      type: 'voice',
      audioUrl: audioUrl,
      duration: '00:08'
    })

  } catch (e) {
    console.error('语音对话失败:', e)
    ElMessage.error('语音识别失败，请重试')

    messages.value.push({
      role: 'assistant',
      content: '抱歉，语音识别失败，请重试或使用文字输入。',
      timestamp: new Date(),
      type: 'text'
    })
  } finally {
    loading.value = false
    if (voiceRecorderRef.value) {
      voiceRecorderRef.value.processingComplete()
    }
    scrollToBottom()
  }
}

// 录音错误
const onRecordError = (error) => {
  console.error('录音错误:', error)
}

// 播放语音
const playVoice = (msg) => {
  if (msg.audioUrl) {
    const audio = new Audio(msg.audioUrl)
    audio.play()
  }
}

// 预览图片
const previewImage = (url) => {
  if (url) {
    window.open(url, '_blank')
  }
}

// 滚动到底部
const scrollToBottom = () => {
  nextTick(() => {
    if (messageListRef.value) {
      messageListRef.value.scrollTop = messageListRef.value.scrollHeight
    }
  })
}

// 格式化消息（支持简单Markdown）
const formatMessage = (text) => {
  if (!text) return ''
  return text
    .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
    .replace(/\n/g, '<br>')
}

// 格式化时间
const formatTime = (timestamp) => {
  return dayjs(timestamp).format('HH:mm')
}

onMounted(() => {
  scrollToBottom()
})
</script>

<style scoped>
.chat-container {
  height: calc(100vh - 140px);
}

@media (max-width: 768px) {
  .chat-container {
    height: calc(100vh - 60px);
  }
  .message-content {
    max-width: 85%;
  }
  .message-list {
    padding: 12px;
  }
  .welcome-banner {
    padding: 20px 12px;
  }
  .welcome-banner h2 {
    font-size: 20px;
  }
  .quick-actions {
    flex-direction: column;
    align-items: center;
  }
}

.chat-card {
  height: 100%;
  display: flex;
  flex-direction: column;
}

.chat-card :deep(.el-card__body) {
  flex: 1;
  display: flex;
  flex-direction: column;
  padding: 0;
  overflow: hidden;
}

.chat-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.header-info {
  display: flex;
  align-items: center;
  gap: 12px;
}

.agent-name {
  font-size: 16px;
  font-weight: bold;
  color: #303133;
}

.agent-status {
  font-size: 12px;
  color: #67c23a;
  display: flex;
  align-items: center;
  gap: 4px;
}

.status-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: #67c23a;
}

.header-actions {
  display: flex;
  gap: 8px;
}

.message-list {
  flex: 1;
  overflow-y: auto;
  padding: 20px;
  background: #f5f7fa;
}

/* 欢迎横幅 */
.welcome-banner {
  text-align: center;
  padding: 40px 20px;
  margin-bottom: 20px;
}

.welcome-icon {
  margin-bottom: 16px;
}

.welcome-banner h2 {
  font-size: 24px;
  color: #303133;
  margin-bottom: 8px;
}

.welcome-banner p {
  font-size: 14px;
  color: #909399;
  margin-bottom: 24px;
}

.quick-actions {
  display: flex;
  flex-wrap: wrap;
  justify-content: center;
  gap: 8px;
}

/* 消息样式 */
.message-item {
  display: flex;
  gap: 12px;
  margin-bottom: 20px;
}

.user-message {
  flex-direction: row-reverse;
}

.message-content {
  max-width: 70%;
}

.message-bubble {
  padding: 12px 16px;
  border-radius: 12px;
  font-size: 14px;
  line-height: 1.6;
}

.user-message .message-bubble {
  background: #409eff;
  color: #fff;
  border-top-right-radius: 4px;
}

.agent-message .message-bubble {
  background: #fff;
  color: #303133;
  border-top-left-radius: 4px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.06);
}

.message-time {
  font-size: 12px;
  color: #909399;
  margin-top: 4px;
}

.user-message .message-time {
  text-align: right;
}

/* 语音消息 */
.voice-message {
  display: flex;
  align-items: center;
  gap: 12px;
  min-width: 120px;
}

.voice-icon {
  width: 32px;
  height: 32px;
  border-radius: 50%;
  background: rgba(255, 255, 255, 0.2);
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
}

.agent-message .voice-icon {
  background: #f0f9ff;
}

.voice-duration {
  font-size: 13px;
}

/* 输入区域 */
.input-area {
  padding: 16px 20px;
  border-top: 1px solid #ebeef5;
  background: #fff;
}

.text-input-area {
  display: flex;
  gap: 12px;
  align-items: flex-end;
}

.text-input-area .el-input {
  flex: 1;
}

/* 图片预览 */
.image-preview {
  position: relative;
  margin-bottom: 8px;
}

.image-preview img {
  max-width: 120px;
  max-height: 80px;
  border-radius: 8px;
  border: 2px solid #e4e7ed;
  object-fit: cover;
}

.remove-image-btn {
  position: absolute;
  top: -8px;
  right: -8px;
  background: #f56c6c !important;
  border-color: #f56c6c !important;
  color: #fff !important;
}

.remove-image-btn:hover {
  background: #f78989 !important;
  border-color: #f78989 !important;
}

/* 文件预览 */
.file-preview {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 12px;
  background: #f0f2f5;
  border-radius: 8px;
  margin-bottom: 8px;
  position: relative;
}

.file-name {
  font-size: 13px;
  color: #303133;
  max-width: 200px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.file-size {
  font-size: 12px;
  color: #909399;
}

/* 文件消息 */
.file-message .file-attachment {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 12px;
  background: #f0f2f5;
  border-radius: 6px;
  margin-bottom: 8px;
}

.file-attachment-name {
  font-size: 13px;
  color: #303133;
}

/* 用户图片消息 */
.user-message .image-message {
  margin-bottom: 8px;
}

.user-message .image-message img {
  max-width: 200px;
  max-height: 150px;
  border-radius: 8px;
}

.voice-input-area {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 12px;
  padding: 20px 0;
}

.voice-mode-tip {
  font-size: 13px;
  color: #909399;
}

/* 打字动画 */
.typing-indicator {
  display: flex;
  gap: 4px;
  padding: 4px 0;
}

.typing-indicator span {
  width: 8px;
  height: 8px;
  background: #909399;
  border-radius: 50%;
  animation: typing 1.4s infinite both;
}

.typing-indicator span:nth-child(2) {
  animation-delay: 0.2s;
}

.typing-indicator span:nth-child(3) {
  animation-delay: 0.4s;
}

@keyframes typing {
  0%, 80%, 100% {
    transform: scale(0.6);
    opacity: 0.6;
  }
  40% {
    transform: scale(1);
    opacity: 1;
  }
}
</style>
