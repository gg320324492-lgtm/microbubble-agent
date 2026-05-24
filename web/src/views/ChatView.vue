<template>
  <div class="chat-container">
    <!-- 对话区域 -->
    <el-card class="chat-card">
      <template #header>
        <div class="chat-header">
          <div class="header-info">
            <el-avatar :size="40" style="background: var(--color-primary)">
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
            <el-icon size="48" color="var(--color-primary)"><Aim /></el-icon>
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
            :style="{ background: msg.role === 'user' ? 'var(--color-success)' : 'var(--color-primary)' }"
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
                  <el-icon size="24" color="var(--color-primary)"><Document /></el-icon>
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

              <!-- 【简要】回复展开按钮 -->
              <div v-if="msg.is_brief" class="detail-expand">
                <el-button text type="primary" size="small" @click="expandDetail(index)">
                  <el-icon><ArrowDown /></el-icon>
                  点击查看详情
                </el-button>
              </div>

              <!-- 存入知识库按钮（文件消息且有待存入的内容） -->
              <div v-if="msg.knowledge_content" class="knowledge-save">
                <el-button text type="success" size="small" @click="saveToKnowledge(msg)">
                  <el-icon><Document /></el-icon>
                  存入知识库
                </el-button>
              </div>
            </div>
            <div class="message-time">{{ formatTime(msg.timestamp) }}</div>
          </div>
        </div>

        <!-- 加载中 -->
        <div v-if="loading" class="message-item agent-message">
          <el-avatar :size="36" style="background: var(--color-primary)">气</el-avatar>
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
        <div v-else class="text-input-area" @dragover.prevent="onDragOver" @dragleave="onDragLeave" @drop.prevent="onDrop" :class="{ 'drag-over': isDragging }">
          <!-- 拖拽提示 -->
          <div v-if="isDragging" class="drag-overlay">
            <el-icon size="40" color="var(--color-primary)"><Upload /></el-icon>
            <span>松开鼠标上传文件</span>
          </div>

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
            <el-icon size="20" color="var(--color-primary)"><Document /></el-icon>
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
              class="upload-btn"
            >
              <el-icon><Picture /></el-icon>
            </el-button>
          </el-tooltip>

          <!-- 文件上传按钮 -->
          <el-tooltip content="发送文件 (PDF/Word/Excel/TXT)">
            <el-button
              circle
              @click="triggerFileUpload"
              :disabled="loading"
              class="upload-btn"
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
import { useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import { Close, Picture, Paperclip, Document, Upload, ArrowDown } from '@element-plus/icons-vue'
import axios from 'axios'
import dayjs from 'dayjs'
import VoiceRecorder from '@/components/VoiceRecorder.vue'
import AudioPlayer from '@/components/AudioPlayer.vue'

const messageListRef = ref(null)
const voiceRecorderRef = ref(null)
const audioPlayerRef = ref(null)
const imageInputRef = ref(null)
const fileInputRef = ref(null)
const route = useRoute()
const inputText = ref('')
const loading = ref(false)
const voiceMode = ref(false)
const sessionId = `user_${Date.now()}`
const selectedImage = ref(null)
const imagePreviewUrl = ref('')
const selectedFile = ref(null)
const filePreviewType = ref('') // 'image' or 'document'
const isDragging = ref(false)

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

// 拖拽相关
const onDragOver = () => {
  isDragging.value = true
}

const onDragLeave = () => {
  isDragging.value = false
}

const onDrop = (event) => {
  isDragging.value = false
  const files = event.dataTransfer?.files
  if (!files || files.length === 0) return

  const file = files[0]
  if (file.type.startsWith('image/')) {
    if (file.size > 10 * 1024 * 1024) {
      ElMessage.error('图片大小不能超过10MB')
      return
    }
    selectedImage.value = file
    imagePreviewUrl.value = URL.createObjectURL(file)
  } else {
    if (file.size > 50 * 1024 * 1024) {
      ElMessage.error('文件大小不能超过50MB')
      return
    }
    selectedFile.value = file
    filePreviewType.value = 'document'
  }
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
        // Content-Type 由 axios 自动设置（包含正确的 boundary）
      })
    } else if (currentImage) {
      // 发送图片消息
      const formData = new FormData()
      formData.append('message', text || '请描述这张图片')
      formData.append('session_id', sessionId)
      formData.append('image', currentImage)

      res = await axios.post('/api/v1/chat/image', formData, {
        // Content-Type 由 axios 自动设置（包含正确的 boundary）
      })
    } else {
      // 发送文字消息
      res = await axios.post('/api/v1/chat', {
        message: text,
        session_id: sessionId
      })
    }

    // 添加AI回复
    const isBrief = res.data.is_brief === true
    const briefIndex = messages.value.length
    messages.value.push({
      role: 'assistant',
      content: res.data.content,
      timestamp: new Date(),
      type: 'text',
      is_brief: isBrief,
      knowledge_content: res.data.knowledge_content || null,
      file_url: res.data.file_url || null,
      file_name: res.data.file_name || null
    })

    // 如果是【简要】回复，启动轮询获取【详细】
    if (isBrief) {
      startDetailPoll(sessionId, briefIndex)
    }
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
      // Content-Type 由 axios 自动设置（包含正确的 boundary）,
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

// 展开【详细】回复
const expandDetail = (index) => {
  // 【详细】回复会在后台生成后追加到 messages，
  // 前端通过轮询检测新消息并自动展示
  scrollToBottom()
}

// 存入知识库
const saveToKnowledge = async (msg) => {
  if (!msg.knowledge_content) {
    ElMessage.warning('没有可存入的内容')
    return
  }
  try {
    await axios.post('/api/v1/knowledge/from-chat', {
      title: msg.file_name || '来自文件的知识',
      content: msg.knowledge_content
    })
    ElMessage.success('已存入知识库')
    // 清除该消息的知识内容，防止重复存入
    msg.knowledge_content = null
  } catch (e) {
    console.error('存入知识库失败:', e)
    ElMessage.error(e.response?.data?.detail || '存入知识库失败')
  }
}

// 轮询检测【详细】回复
let detailPollInterval = null
const startDetailPoll = (sessionId, lastBriefIndex) => {
  stopDetailPoll()
  detailPollInterval = setInterval(async () => {
    try {
      const res = await axios.get(`/api/v1/chat/history/${sessionId}?after_index=${lastBriefIndex}`)
      if (res.data.messages && res.data.messages.length > 0) {
        // 找到【详细】回复并追加
        for (const msg of res.data.messages) {
          if (msg.role === 'assistant' && !msg.is_brief) {
            messages.value.push({
              ...msg,
              timestamp: new Date(),
              type: 'text'
            })
          }
        }
        scrollToBottom()
        stopDetailPoll()
      }
    } catch (e) {
      // 忽略轮询错误
    }
  }, 2000) // 每2秒检测一次
}

const stopDetailPoll = () => {
  if (detailPollInterval) {
    clearInterval(detailPollInterval)
    detailPollInterval = null
  }
}

onMounted(() => {
  scrollToBottom()
  // 接收从 MeetingView 粘贴转录跳转过来的消息
  if (route.query.initialMessage) {
    inputText.value = route.query.initialMessage
    sendMessage()
  }
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
  animation: fadeSlideUp var(--duration-slower) var(--ease-out) both;
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
  font-size: var(--font-size-md);
  font-weight: var(--font-weight-bold);
  color: var(--color-text-primary);
}

.agent-status {
  font-size: var(--font-size-xs);
  color: var(--color-success);
  display: flex;
  align-items: center;
  gap: 4px;
}

.status-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--color-success);
}

.header-actions {
  display: flex;
  gap: var(--space-2);
}

.header-actions .el-button {
  transition: all var(--duration-fast) var(--ease-out);
}

.header-actions .el-button:hover {
  transform: scale(1.08);
  background: var(--color-primary-bg);
  color: var(--color-primary);
}

.message-list {
  flex: 1;
  overflow-y: auto;
  padding: var(--space-5);
  background: var(--color-bg-page);
}

/* 欢迎横幅 */
.welcome-banner {
  text-align: center;
  padding: var(--space-10) var(--space-5);
  margin-bottom: var(--space-5);
  animation: fadeSlideUp var(--duration-slower) var(--ease-out) both;
}

.welcome-icon {
  margin-bottom: var(--space-4);
}

.welcome-banner h2 {
  font-size: var(--font-size-xl);
  color: var(--color-text-primary);
  margin-bottom: var(--space-2);
}

.welcome-banner p {
  font-size: var(--font-size-base);
  color: var(--color-text-secondary);
  margin-bottom: var(--space-6);
}

.quick-actions {
  display: flex;
  flex-wrap: wrap;
  justify-content: center;
  gap: var(--space-2);
}

.quick-actions .el-button {
  border-radius: var(--radius-full);
  transition: all var(--duration-fast) var(--ease-out);
  border-color: var(--color-primary-border);
  color: var(--color-primary);
  background: var(--color-primary-bg);
}

.quick-actions .el-button:hover {
  transform: translateY(-2px) scale(1.02);
  box-shadow: var(--shadow-primary);
  background: var(--color-primary);
  color: #fff;
}

/* 消息样式 */
.message-item {
  display: flex;
  gap: var(--space-3);
  margin-bottom: var(--space-5);
  animation: fadeSlideUp var(--duration-slow) var(--ease-out) both;
}

.user-message {
  flex-direction: row-reverse;
}

.message-content {
  max-width: 70%;
}

.message-bubble {
  padding: var(--space-3) var(--space-4);
  border-radius: var(--radius-lg);
  font-size: var(--font-size-base);
  line-height: 1.6;
  transition: transform var(--duration-fast) var(--ease-out),
              box-shadow var(--duration-fast) var(--ease-out);
}

.user-message .message-bubble {
  background: var(--color-primary);
  color: #fff;
  border-top-right-radius: var(--radius-sm);
}

.user-message .message-bubble:hover {
  transform: scale(1.01);
  box-shadow: var(--shadow-primary);
}

.agent-message .message-bubble {
  background: var(--color-bg-card);
  color: var(--color-text-primary);
  border-top-left-radius: var(--radius-sm);
  box-shadow: var(--shadow-sm);
}

.agent-message .message-bubble:hover {
  box-shadow: var(--shadow-md);
}

.message-time {
  font-size: var(--font-size-xs);
  color: var(--color-text-secondary);
  margin-top: var(--space-1);
}

.user-message .message-time {
  text-align: right;
}

/* 语音消息 */
.voice-message {
  display: flex;
  align-items: center;
  gap: var(--space-3);
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
  transition: transform var(--duration-fast) var(--ease-out);
}

.voice-icon:hover {
  transform: scale(1.1);
}

.agent-message .voice-icon {
  background: var(--color-primary-bg);
}

.voice-duration {
  font-size: var(--font-size-sm);
}

/* 输入区域 */
.input-area {
  padding: var(--space-4) var(--space-5);
  border-top: 1px solid var(--color-border);
  background: var(--color-bg-card);
}

.text-input-area {
  display: flex;
  gap: var(--space-3);
  align-items: flex-end;
  position: relative;
  min-height: 60px;
  transition: all var(--duration-normal) var(--ease-out);
}

.text-input-area.drag-over {
  background: var(--color-primary-bg);
  border: 2px dashed var(--color-primary);
  border-radius: var(--radius-lg);
  padding: var(--space-3);
}

.drag-overlay {
  position: absolute;
  inset: 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: var(--space-2);
  background: rgba(255, 240, 237, 0.95);
  border-radius: var(--radius-lg);
  z-index: 10;
  font-size: var(--font-size-base);
  color: var(--color-primary);
}

.upload-btn:hover {
  color: var(--color-primary);
  border-color: var(--color-primary);
  transform: scale(1.05);
}

.text-input-area .el-input {
  flex: 1;
}

.text-input-area .el-button[type="primary"] {
  border-radius: var(--radius-md);
  transition: all var(--duration-fast) var(--ease-out);
  box-shadow: var(--shadow-primary);
}

.text-input-area .el-button[type="primary"]:hover:not(:disabled) {
  transform: scale(1.02);
  filter: brightness(1.08);
}

.text-input-area .el-button[type="primary"]:active:not(:disabled) {
  transform: scale(0.97);
}

/* 图片预览 */
.image-preview {
  position: relative;
  margin-bottom: 8px;
}

.image-preview img {
  max-width: 120px;
  max-height: 80px;
  border-radius: var(--radius-md);
  border: 2px solid var(--color-border);
  object-fit: cover;
}

.remove-image-btn {
  position: absolute;
  top: -8px;
  right: -8px;
  background: var(--color-danger) !important;
  border-color: var(--color-danger) !important;
  color: #fff !important;
  transition: all var(--duration-fast) var(--ease-out);
}

.remove-image-btn:hover {
  background: var(--color-danger) !important;
  border-color: var(--color-danger) !important;
  transform: scale(1.1);
}

/* 文件预览 */
.file-preview {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  padding: var(--space-2) var(--space-3);
  background: var(--color-info-bg);
  border-radius: var(--radius-md);
  margin-bottom: var(--space-2);
  position: relative;
}

.file-name {
  font-size: var(--font-size-sm);
  color: var(--color-text-primary);
  max-width: 200px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.file-size {
  font-size: var(--font-size-xs);
  color: var(--color-text-secondary);
}

/* 文件消息 */
.file-message .file-attachment {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  padding: var(--space-2) var(--space-3);
  background: var(--color-info-bg);
  border-radius: var(--radius-md);
  margin-bottom: var(--space-2);
}

.file-attachment-name {
  font-size: var(--font-size-sm);
  color: var(--color-text-primary);
}

/* 用户图片消息 */
.user-message .image-message {
  margin-bottom: 8px;
}

.user-message .image-message img {
  max-width: 200px;
  max-height: 150px;
  border-radius: var(--radius-md);
}

.voice-input-area {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: var(--space-3);
  padding: var(--space-5) 0;
}

.voice-mode-tip {
  font-size: var(--font-size-sm);
  color: var(--color-text-secondary);
}

/* 打字动画 */
.typing-indicator {
  display: flex;
  gap: var(--space-1);
  padding: var(--space-1) 0;
}

.typing-indicator span {
  width: 8px;
  height: 8px;
  background: var(--color-primary);
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

/* 【简要】展开按钮 */
.detail-expand {
  margin-top: var(--space-2);
  padding-top: var(--space-2);
  border-top: 1px solid var(--color-border);
  text-align: center;
}

.detail-expand .el-button {
  transition: all var(--duration-fast) var(--ease-out);
  border-radius: var(--radius-md);
}

.detail-expand .el-button:hover {
  transform: scale(1.02);
  background: var(--color-primary-bg);
}

/* 存入知识库按钮 */
.knowledge-save {
  margin-top: var(--space-2);
  padding-top: var(--space-2);
  border-top: 1px dashed var(--color-border);
  text-align: center;
}

.knowledge-save .el-button {
  transition: all var(--duration-fast) var(--ease-out);
  border-radius: var(--radius-md);
  color: var(--color-success);
}

.knowledge-save .el-button:hover {
  transform: scale(1.02);
  background: rgba(10, 207, 107, 0.1);
}
</style>
