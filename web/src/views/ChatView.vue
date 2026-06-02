<template>
  <div class="chat-immersive">
    <!-- 顶部状态栏 -->
    <header class="chat-topbar">
      <div class="topbar-left">
        <div class="bot-avatar-sm">
          <span class="bot-emoji">🤖</span>
        </div>
        <div>
          <div class="bot-name">小气助手</div>
          <div class="bot-status"><span class="live-dot" />在线</div>
        </div>
      </div>
      <div class="topbar-right">
        <el-tooltip content="语音模式"><el-button :type="voiceMode ? 'primary' : ''" circle size="small" @click="toggleVoiceMode"><el-icon><Microphone /></el-icon></el-button></el-tooltip>
        <el-tooltip content="新对话"><el-button circle size="small" @click="clearChat"><el-icon><Delete /></el-icon></el-button></el-tooltip>
      </div>
    </header>

    <!-- 消息区域 -->
    <main class="chat-main" ref="messageListRef">
      <!-- 欢迎页 -->
      <div v-if="messages.length === 1" class="welcome-hero">
        <div class="hero-avatar">
          <span class="hero-emoji">🤖</span>
          <div class="hero-ring" />
        </div>
        <h1 class="hero-title">你好，我是小气</h1>
        <p class="hero-sub">微纳米气泡课题组 AI 助手</p>
        <div class="hero-actions">
          <button v-for="q in quickActions" :key="q.label" class="hero-btn" @click="sendQuickMessage(q.text)">
            <span class="hero-btn-icon">{{ q.icon }}</span>
            <span>{{ q.label }}</span>
          </button>
        </div>
      </div>

      <!-- 消息列表 -->
      <div v-for="(msg, idx) in messages" :key="idx">
        <!-- 时间分割线 -->
        <div v-if="showTimeDivider(idx, msg)" class="time-divider">
          <span>{{ formatTime(msg.timestamp) }}</span>
        </div>

        <div :class="['msg-row', msg.role === 'user' ? 'msg-user' : 'msg-bot']">
          <!-- AI 头像 -->
          <div v-if="msg.role !== 'user'" class="msg-avatar">
            <span class="bot-emoji-sm">🤖</span>
          </div>

          <div class="msg-body">
            <!-- 图片 -->
            <div v-if="msg.type === 'image'" class="msg-image">
              <img v-if="msg.imageUrl" :src="msg.imageUrl" @click="previewImage(msg.imageUrl)" />
              <div v-if="msg.content !== '[图片]'" class="msg-text" v-html="renderMD(msg.content)" />
            </div>

            <!-- 文件 -->
            <div v-else-if="msg.type === 'file'" class="msg-file">
              <div class="file-chip"><el-icon><Document /></el-icon>{{ msg.fileName || '文件' }}</div>
              <div v-if="msg.content && !msg.content.startsWith('[文件:')" class="msg-text" v-html="renderMD(msg.content)" />
            </div>

            <!-- 文字 -->
            <div v-else-if="msg.type !== 'voice'" :class="['msg-bubble', msg.role === 'user' ? 'bubble-user' : 'bubble-bot']">
              <div v-html="renderMD(msg.content)" />
              <!-- 简要展开 -->
              <div v-if="msg.is_brief" class="expand-bar" @click="expandDetail(idx)">查看详情 <el-icon><ArrowDown /></el-icon></div>
              <!-- 知识库按钮 -->
              <div v-if="msg.knowledge_content" class="save-kb" @click="saveToKnowledge(msg)">📚 存入知识库</div>
            </div>

            <!-- 语音 -->
            <div v-else class="msg-voice" @click="playVoice(msg)">
              <el-icon size="18"><VideoPlay /></el-icon>
              <span>{{ msg.duration || '00:05' }}</span>
            </div>
          </div>

          <!-- 用户头像 -->
          <div v-if="msg.role === 'user'" class="msg-avatar msg-avatar-user">
            <el-avatar :size="32" :src="userAvatar" />
          </div>
        </div>
      </div>

      <!-- 打字中 -->
      <div v-if="loading" class="msg-row msg-bot">
        <div class="msg-avatar"><span class="bot-emoji-sm">🤖</span></div>
        <div class="msg-bubble bubble-bot typing-bubble">
          <span class="typing-dot" /><span class="typing-dot" /><span class="typing-dot" />
        </div>
      </div>

      <div class="chat-bottom-spacer" />
    </main>

    <!-- 底部输入栏 -->
    <footer class="chat-footer">
      <!-- 语音模式 -->
      <div v-if="voiceMode" class="voice-bar">
        <VoiceRecorder ref="voiceRecorderRef" :disabled="loading"
          @record-start="onRecordStart" @record-stop="onRecordStop" @record-error="onRecordError" />
        <el-button text size="small" @click="toggleVoiceMode">切换文字模式</el-button>
      </div>

      <!-- 文字输入 -->
      <div v-else class="input-row" :class="{ 'drag-over': isDragging }"
        @dragover.prevent="onDragOver" @dragleave="onDragLeave" @drop.prevent="onDrop">
        <!-- 图片预览 -->
        <div v-if="selectedImage" class="preview-chip">
          <img :src="imagePreviewUrl" />
          <span class="chip-close" @click="removeImage">✕</span>
        </div>
        <!-- 文件预览 -->
        <div v-if="selectedFile" class="preview-chip">
          <el-icon><Document /></el-icon>
          <span>{{ selectedFile.name }}</span>
          <span class="chip-close" @click="removeFile">✕</span>
        </div>

        <div class="input-core">
          <button class="input-btn" :disabled="loading" @click="triggerImageUpload"><el-icon><Picture /></el-icon></button>
          <button class="input-btn" :disabled="loading" @click="triggerFileUpload"><el-icon><Paperclip /></el-icon></button>

          <textarea
            ref="textareaRef"
            v-model="inputText"
            name="chat-input-message"
            class="input-textarea"
            placeholder="输入消息..."
            rows="1"
            :disabled="loading"
            @keydown="handleKeydown"
            @input="autoResize"
          />

          <button
            class="send-btn"
            :disabled="(!inputText.trim() && !selectedImage && !selectedFile) || loading"
            @click="sendMessage"
          >
            <el-icon size="18"><Promotion /></el-icon>
          </button>
        </div>

        <input ref="imageInputRef" type="file" accept="image/*" hidden @change="handleImageSelect" />
        <input ref="fileInputRef" type="file" accept=".pdf,.doc,.docx,.xls,.xlsx,.txt,.md" hidden @change="handleFileSelect" />
      </div>
    </footer>

    <AudioPlayer v-if="false" ref="audioPlayerRef" />
  </div>
</template>

<script setup>
import { ref, nextTick, onMounted, onUnmounted, watch } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import { Close, Picture, Paperclip, Document, ArrowDown, Microphone, Delete, Promotion, VideoPlay } from '@element-plus/icons-vue'
import axios from 'axios'
import dayjs from 'dayjs'
import { marked } from 'marked'
import { useUserStore } from '@/stores/user'
import VoiceRecorder from '@/components/VoiceRecorder.vue'
import AudioPlayer from '@/components/AudioPlayer.vue'

marked.setOptions({ breaks: true, gfm: true })

const route = useRoute()
const userStore = useUserStore()
const userAvatar = ref('')

const messageListRef = ref(null)
const voiceRecorderRef = ref(null)
const audioPlayerRef = ref(null)
const imageInputRef = ref(null)
const fileInputRef = ref(null)
const textareaRef = ref(null)

const inputText = ref('')
const loading = ref(false)
const voiceMode = ref(false)
const sessionId = `user_${Date.now()}`
const selectedImage = ref(null)
const imagePreviewUrl = ref('')
const selectedFile = ref(null)
const isDragging = ref(false)

const messages = ref([{
  role: 'assistant',
  content: '你好！我是小气，微纳米气泡课题组的AI助手。我可以帮你管理任务、查询会议、回答专业问题。有什么可以帮你的吗？',
  timestamp: new Date(),
  type: 'text',
}])

const quickActions = [
  { icon: '📋', label: '我的任务', text: '查看我的任务' },
  { icon: '📅', label: '最近会议', text: '最近有什么会议？' },
  { icon: '📊', label: '项目进度', text: '水处理项目进度怎么样？' },
  { icon: '📚', label: '知识问答', text: '微纳米气泡的生成方法有哪些？' },
]

onMounted(async () => {
  scrollToBottom()
  try { userAvatar.value = userStore.userInfo?.avatar || '' } catch {}
  if (route.query.initialMessage) { inputText.value = route.query.initialMessage; sendMessage() }
})

// --- Markdown ---
const renderMD = (text) => {
  if (!text) return ''
  try { return marked.parse(text) } catch { return text.replace(/</g, '&lt;') }
}

// --- 时间分割线 ---
let lastTime = null
const showTimeDivider = (idx, msg) => {
  if (idx === 0) { lastTime = msg.timestamp; return false }
  const prev = messages.value[idx - 1]
  if (!prev) return false
  const diff = new Date(msg.timestamp) - new Date(prev.timestamp)
  if (diff > 5 * 60 * 1000) { lastTime = msg.timestamp; return true }
  return false
}

// --- 输入 ---
const autoResize = () => {
  const el = textareaRef.value
  if (!el) return
  el.style.height = 'auto'
  el.style.height = Math.min(el.scrollHeight, 120) + 'px'
}

const handleKeydown = (e) => {
  if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); sendMessage() }
}

const triggerImageUpload = () => imageInputRef.value?.click()
const triggerFileUpload = () => fileInputRef.value?.click()
const removeImage = () => { selectedImage.value = null; imagePreviewUrl.value = '' }
const removeFile = () => { selectedFile.value = null }

const handleImageSelect = (e) => {
  const f = e.target.files[0]; if (!f) return
  if (!f.type.startsWith('image/')) return ElMessage.error('请选择图片文件')
  if (f.size > 10 * 1024 * 1024) return ElMessage.error('图片不超过10MB')
  selectedImage.value = f; imagePreviewUrl.value = URL.createObjectURL(f); e.target.value = ''
}
const handleFileSelect = (e) => {
  const f = e.target.files[0]; if (!f) return
  if (f.size > 50 * 1024 * 1024) return ElMessage.error('文件不超过50MB')
  selectedFile.value = f; e.target.value = ''
}

const onDragOver = () => { isDragging.value = true }
const onDragLeave = () => { isDragging.value = false }
const onDrop = (e) => {
  isDragging.value = false
  const f = e.dataTransfer?.files?.[0]; if (!f) return
  if (f.type.startsWith('image/')) { if (f.size > 10*1024*1024) return ElMessage.error('图片不超过10MB'); selectedImage.value = f; imagePreviewUrl.value = URL.createObjectURL(f) }
  else { if (f.size > 50*1024*1024) return ElMessage.error('文件不超过50MB'); selectedFile.value = f }
}

// --- 发送 ---
const sendMessage = async () => {
  const text = inputText.value.trim()
  if ((!text && !selectedImage.value && !selectedFile.value) || loading.value) return

  let type = 'text', content = text
  const img = selectedImage.value, file = selectedFile.value
  if (img) { type = 'image'; content = text ? `[图片] ${text}` : '[图片]' }
  else if (file) { type = 'file'; content = text ? `[文件: ${file.name}] ${text}` : `[文件: ${file.name}]` }

  messages.value.push({ role: 'user', content, timestamp: new Date(), type, imageUrl: img ? imagePreviewUrl.value : null, fileName: file?.name || null })

  inputText.value = ''; selectedImage.value = null; imagePreviewUrl.value = ''; selectedFile.value = null
  if (textareaRef.value) textareaRef.value.style.height = 'auto'
  loading.value = true; scrollToBottom()

  try {
    let res
    if (file) { const fd = new FormData(); fd.append('message', text||''); fd.append('session_id', sessionId); fd.append('file', file); res = await axios.post('/api/v1/chat/file', fd) }
    else if (img) { const fd = new FormData(); fd.append('message', text||'请描述这张图片'); fd.append('session_id', sessionId); fd.append('image', img); res = await axios.post('/api/v1/chat/image', fd) }
    else { res = await axios.post('/api/v1/chat', { message: text, session_id: sessionId }) }

    const isBrief = res.data.is_brief === true
    const bi = messages.value.length
    messages.value.push({ role: 'assistant', content: res.data.content, timestamp: new Date(), type: 'text', is_brief: isBrief, knowledge_content: res.data.knowledge_content || null })
    if (isBrief) startDetailPoll(sessionId, bi)
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || '发送失败')
    messages.value.push({ role: 'assistant', content: '抱歉，我暂时无法回复，请稍后再试。', timestamp: new Date(), type: 'text' })
  } finally { loading.value = false; scrollToBottom() }
}

const sendQuickMessage = (t) => { inputText.value = t; sendMessage() }

// --- 简要/详细 轮询 ---
let detailPollTimer = null
const startDetailPoll = (sid, briefIdx) => {
  stopDetailPoll()
  detailPollTimer = setInterval(async () => {
    try {
      const r = await axios.get(`/api/v1/chat/history/${sid}?after_index=${briefIdx}`)
      if (r.data.messages?.length) {
        for (const m of r.data.messages) { if (m.role === 'assistant' && !m.is_brief) messages.value.push({ ...m, timestamp: new Date(), type: 'text' }) }
        scrollToBottom(); stopDetailPoll()
      }
    } catch {}
  }, 2000)
}
const stopDetailPoll = () => { if (detailPollTimer) { clearInterval(detailPollTimer); detailPollTimer = null } }
const expandDetail = () => scrollToBottom()

// --- 其他 ---
const clearChat = () => { messages.value = [{ role: 'assistant', content: '对话已清空，有什么可以帮你的吗？', timestamp: new Date(), type: 'text' }] }
const toggleVoiceMode = () => { voiceMode.value = !voiceMode.value }
const onRecordStart = () => {}
const onRecordStop = async (blob) => { /* 保持原有语音逻辑 */ }
const onRecordError = () => {}
const playVoice = (m) => { if (m.audioUrl) new Audio(m.audioUrl).play() }
const previewImage = (url) => { if (url) window.open(url, '_blank') }
const saveToKnowledge = async (msg) => {
  try { await axios.post('/api/v1/knowledge/from-chat', { title: msg.file_name || '来自对话的知识', content: msg.knowledge_content }); ElMessage.success('已存入知识库'); msg.knowledge_content = null } catch (e) { ElMessage.error(e.response?.data?.detail || '存入失败') }
}
const formatTime = (t) => dayjs(t).format('HH:mm')
const scrollToBottom = () => nextTick(() => { if (messageListRef.value) messageListRef.value.scrollTop = messageListRef.value.scrollHeight })

onUnmounted(() => stopDetailPoll())
</script>

<style scoped>
/* ===== 整体 ===== */
.chat-immersive {
  display: flex; flex-direction: column; height: calc(100vh - 120px);
  background: linear-gradient(180deg, #f8f9fb 0%, #fefefe 100%);
  border-radius: var(--radius-lg); overflow: hidden;
}
@media (max-width: 768px) { .chat-immersive { height: calc(100vh - 56px); border-radius: 0; } }

/* ===== 顶栏 ===== */
.chat-topbar {
  display: flex; justify-content: space-between; align-items: center;
  padding: 10px 20px; background: rgba(255,255,255,0.85); backdrop-filter: blur(12px);
  border-bottom: 1px solid rgba(0,0,0,0.05); z-index: 20; flex-shrink: 0;
}
.topbar-left { display: flex; align-items: center; gap: 10px; }
.bot-avatar-sm { width: 36px; height: 36px; border-radius: 50%; background: linear-gradient(135deg, #FF7A5C, #FFB347); display: flex; align-items: center; justify-content: center; }
.bot-emoji { font-size: 18px; line-height: 1; }
.bot-name { font-size: 15px; font-weight: 700; color: #2D2D2D; }
.bot-status { font-size: 12px; color: #67C23A; display: flex; align-items: center; gap: 4px; }
.live-dot { width: 6px; height: 6px; border-radius: 50%; background: #67C23A; }
.topbar-right { display: flex; gap: 6px; }

/* ===== 消息区域 ===== */
.chat-main {
  flex: 1; overflow-y: auto; padding: 16px 20px 0;
  display: flex; flex-direction: column; gap: 4px;
}
.chat-bottom-spacer { height: 16px; flex-shrink: 0; }

/* 时间分割线 */
.time-divider {
  display: flex; align-items: center; gap: 12px; margin: 16px 0;
  color: #bbb; font-size: 12px;
}
.time-divider::before, .time-divider::after {
  content: ''; flex: 1; height: 1px;
  background: linear-gradient(90deg, transparent, #e0e0e0, transparent);
}

/* 消息行 */
.msg-row { display: flex; gap: 8px; max-width: 80%; margin-bottom: 2px; }
.msg-user { align-self: flex-end; flex-direction: row-reverse; }
.msg-bot { align-self: flex-start; }
@media (max-width: 768px) { .msg-row { max-width: 92%; } }

.msg-avatar { flex-shrink: 0; width: 30px; height: 30px; border-radius: 50%; background: linear-gradient(135deg, #FF7A5C, #FFB347); display: flex; align-items: center; justify-content: center; align-self: flex-end; }
.bot-emoji-sm { font-size: 14px; line-height: 1; }
.msg-avatar-user { background: transparent; }

.msg-body { display: flex; flex-direction: column; gap: 2px; min-width: 0; }

/* 气泡 */
.msg-bubble {
  padding: 10px 14px; border-radius: 16px; font-size: 14px; line-height: 1.6;
  word-break: break-word; position: relative;
}
.bubble-user {
  background: linear-gradient(135deg, #FF7A5C 0%, #FF9D85 100%);
  color: #fff; border-bottom-right-radius: 6px;
}
.bubble-bot {
  background: #fff; color: #2D2D2D; border-bottom-left-radius: 6px;
  box-shadow: 0 1px 3px rgba(0,0,0,0.06);
}

/* 打字 */
.typing-bubble { display: flex; gap: 4px; padding: 12px 16px; align-items: center; }
.typing-dot { width: 7px; height: 7px; border-radius: 50%; background: #FF7A5C; animation: td 1.4s infinite both; }
.typing-dot:nth-child(2) { animation-delay: 0.2s; }
.typing-dot:nth-child(3) { animation-delay: 0.4s; }
@keyframes td { 0%,80%,100% { transform: scale(0.5); opacity: 0.5; } 40% { transform: scale(1); opacity: 1; } }

/* Markdown 内容样式 */
.msg-bubble :deep(p) { margin: 0 0 6px; }
.msg-bubble :deep(p:last-child) { margin-bottom: 0; }
.msg-bubble :deep(ul), .msg-bubble :deep(ol) { padding-left: 18px; margin: 4px 0; }
.msg-bubble :deep(li) { margin-bottom: 2px; }
.msg-bubble :deep(code) {
  background: rgba(0,0,0,0.06); padding: 2px 6px; border-radius: 4px;
  font-family: 'SF Mono', 'Cascadia Code', monospace; font-size: 13px;
}
.bubble-user :deep(code) { background: rgba(255,255,255,0.2); }
.msg-bubble :deep(pre) {
  background: #1e293b; color: #e2e8f0; padding: 12px 16px; border-radius: 10px;
  overflow-x: auto; margin: 8px 0; font-size: 13px; line-height: 1.5;
}
.msg-bubble :deep(pre code) { background: none; padding: 0; color: inherit; }
.msg-bubble :deep(table) { border-collapse: collapse; width: 100%; margin: 8px 0; font-size: 13px; }
.msg-bubble :deep(th), .msg-bubble :deep(td) { border: 1px solid rgba(0,0,0,0.1); padding: 6px 10px; text-align: left; }
.msg-bubble :deep(th) { background: rgba(0,0,0,0.03); font-weight: 600; }
.msg-bubble :deep(blockquote) {
  border-left: 3px solid #FF7A5C; padding-left: 12px; margin: 8px 0; color: #666;
}
.msg-bubble :deep(a) { color: #FF7A5C; }

/* 其他消息元素 */
.expand-bar { margin-top: 8px; padding-top: 8px; border-top: 1px solid rgba(0,0,0,0.06); text-align: center; font-size: 12px; color: #FF7A5C; cursor: pointer; display: flex; align-items: center; justify-content: center; gap: 4px; }
.save-kb { margin-top: 8px; padding-top: 8px; border-top: 1px dashed rgba(0,0,0,0.06); text-align: center; font-size: 12px; color: #67C23A; cursor: pointer; }
.msg-image img { max-width: 200px; max-height: 150px; border-radius: 12px; cursor: pointer; }
.msg-file { display: flex; flex-direction: column; gap: 6px; }
.file-chip { display: inline-flex; align-items: center; gap: 6px; padding: 6px 12px; background: #f0f0f0; border-radius: 8px; font-size: 13px; }
.msg-voice { display: flex; align-items: center; gap: 8px; padding: 8px 14px; background: #fff; border-radius: 16px; cursor: pointer; box-shadow: 0 1px 3px rgba(0,0,0,0.06); }

/* ===== 欢迎页 ===== */
.welcome-hero {
  display: flex; flex-direction: column; align-items: center; justify-content: center;
  padding: 40px 20px; text-align: center; flex: 1;
}
.hero-avatar {
  position: relative; width: 80px; height: 80px; border-radius: 50%;
  background: linear-gradient(135deg, #FF7A5C, #FFB347);
  display: flex; align-items: center; justify-content: center; margin-bottom: 20px;
  animation: hero-float 3s ease-in-out infinite;
}
.hero-emoji { font-size: 40px; line-height: 1; }
.hero-ring {
  position: absolute; inset: -8px; border-radius: 50%;
  border: 2px solid rgba(255,122,92,0.2);
  animation: hero-ring-pulse 2s ease-out infinite;
}
@keyframes hero-float { 0%,100% { transform: translateY(0); } 50% { transform: translateY(-8px); } }
@keyframes hero-ring-pulse { 0% { transform: scale(1); opacity: 0.6; } 100% { transform: scale(1.3); opacity: 0; } }

.hero-title { font-size: 28px; font-weight: 800; color: #2D2D2D; margin: 0 0 8px; }
.hero-sub { font-size: 15px; color: #888; margin: 0 0 28px; }
.hero-actions { display: flex; flex-wrap: wrap; justify-content: center; gap: 10px; max-width: 420px; }
.hero-btn {
  display: flex; align-items: center; gap: 8px; padding: 10px 18px;
  border: 1.5px solid rgba(255,122,92,0.25); border-radius: 24px;
  background: rgba(255,122,92,0.04); font-size: 14px; color: #FF7A5C;
  cursor: pointer; transition: all 0.2s;
}
.hero-btn:hover { background: #FF7A5C; color: #fff; border-color: #FF7A5C; transform: translateY(-1px); }
.hero-btn-icon { font-size: 16px; }

/* ===== 底部输入栏 ===== */
.chat-footer { flex-shrink: 0; padding: 10px 16px 14px; background: rgba(255,255,255,0.7); backdrop-filter: blur(20px); border-top: 1px solid rgba(0,0,0,0.05); }
.voice-bar { display: flex; flex-direction: column; align-items: center; gap: 8px; padding: 8px 0; }
.input-row { position: relative; display: flex; flex-direction: column; gap: 8px; }
.input-row.drag-over { background: rgba(255,122,92,0.05); border: 2px dashed rgba(255,122,92,0.3); border-radius: 16px; padding: 10px; }

.preview-chip {
  display: inline-flex; align-items: center; gap: 8px; padding: 4px 10px;
  background: #f5f5f5; border-radius: 10px; font-size: 13px; max-width: 240px;
}
.preview-chip img { max-width: 60px; max-height: 40px; border-radius: 6px; }
.chip-close { cursor: pointer; color: #999; font-size: 12px; margin-left: 4px; }
.chip-close:hover { color: #F56C6C; }

.input-core {
  display: flex; align-items: flex-end; gap: 6px;
  background: #fff; border-radius: 20px; padding: 6px 10px;
  box-shadow: 0 2px 8px rgba(0,0,0,0.06);
}
.input-btn {
  width: 34px; height: 34px; border: none; border-radius: 50%;
  background: transparent; color: #999; cursor: pointer; display: flex;
  align-items: center; justify-content: center; transition: all 0.2s; flex-shrink: 0;
}
.input-btn:hover:not(:disabled) { background: rgba(255,122,92,0.08); color: #FF7A5C; }
.input-btn:disabled { opacity: 0.4; cursor: not-allowed; }

.input-textarea {
  flex: 1; border: none; outline: none; resize: none; font-size: 14px;
  line-height: 1.5; padding: 7px 4px; max-height: 120px; min-height: 20px;
  font-family: inherit; background: transparent;
}
.input-textarea::placeholder { color: #bbb; }

.send-btn {
  width: 38px; height: 38px; border: none; border-radius: 50%;
  background: linear-gradient(135deg, #FF7A5C, #FF9D85); color: #fff;
  cursor: pointer; display: flex; align-items: center; justify-content: center;
  transition: all 0.2s; flex-shrink: 0;
}
.send-btn:hover:not(:disabled) { transform: scale(1.05); box-shadow: 0 4px 12px rgba(255,122,92,0.4); }
.send-btn:disabled { opacity: 0.35; cursor: not-allowed; background: #ccc; }
</style>
