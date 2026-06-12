<script setup>
/**
 * ChatViewSSE.vue — v2 极简版（接 SSE 流式 + Rich Block 渲染）
 *
 * 替换原 564 行 ChatView.vue 90% 体积，专注核心：
 * - 真实 SSE 流式（/api/v1/chat/stream）替换 setInterval 轮询
 * - assistant 消息支持 rich_blocks 渲染
 * - 工具调用中间态展示（"🔍 正在 X..."）
 * - 保留必要的图片/文件上传、欢迎页、快捷指令
 *
 * 复用：
 * - 工具标签 TOOL_LABELS（web/src/api/agent/toolLabels.ts）
 * - Rich Block 注册表（web/src/components/chat/blocks/registry.ts）
 * - Pinia store（如有，chat.ts）
 */
import { ref, onMounted, onUnmounted, nextTick } from 'vue'
import { ElMessage } from 'element-plus'
import { ChatDotRound } from '@element-plus/icons-vue'
import axios from 'axios'
import RichContent from '@/components/chat/RichContent.vue'
import { sseFetch } from '@/api/agent/sse'
import { useNetworkStatus } from '@/composables/useNetworkStatus'
import { renderMarkdown } from '@/utils/markdown'

// --- 状态 ---
const messages = ref([])
const inputText = ref('')
const loading = ref(false)
const sessionId = ref(localStorage.getItem('chat_session_id') || `user_${Date.now()}`)
const sessionKey = 'chat_session_id'
const messagesKey = 'chat_messages_v2'
const isDragging = ref(false)
const textareaRef = ref(null)
const messagesRef = ref(null)
const selectedImage = ref(null)
const imagePreviewUrl = ref('')
const selectedFile = ref(null)
const voiceMode = ref(false)
const imageInputRef = ref(null)
const fileInputRef = ref(null)

// --- 网络状态 ---
const { isOnline } = useNetworkStatus()

// 快捷指令
const quickActions = [
  { icon: '📋', label: '我的任务', text: '我最近有什么任务？' },
  { icon: '📅', label: '最近会议', text: '上周开了什么会？有什么结论？' },
  { icon: '📊', label: '项目进度', text: '项目进度如何？' },
  { icon: '📚', label: '知识问答', text: 'zeta 电位是什么？' }
]

// --- 生命周期 ---
onMounted(() => {
  // 恢复历史
  const cached = localStorage.getItem(messagesKey)
  if (cached) {
    try { messages.value = JSON.parse(cached) } catch { messages.value = [] }
  }
  if (messages.value.length === 0) {
    messages.value = [{
      id: crypto.randomUUID(),
      role: 'assistant',
      content: '你好！我是"小气"，课题组智能助手。有什么可以帮你的吗？',
      richBlocks: [],
      timestamp: new Date().toISOString()
    }]
  }
})

onUnmounted(() => {
  persistMessages()
})

const persistMessages = () => {
  // 限制 200 条
  const slice = messages.value.slice(-200)
  localStorage.setItem(messagesKey, JSON.stringify(slice))
  localStorage.setItem(sessionKey, sessionId.value)
}

const scrollToBottom = async () => {
  await nextTick()
  if (messagesRef.value) {
    messagesRef.value.scrollTop = messagesRef.value.scrollHeight
  }
}

// --- Markdown 渲染（统一入口由 utils/markdown.ts 提供，含 highlight.js） ---

// --- 发送（SSE 流式） ---
const sendMessage = async (text) => {
  const content = (text ?? inputText.value).trim()
  if ((!content && !selectedImage.value && !selectedFile.value) || loading.value) return

  // 用户消息
  const userMsg = {
    id: crypto.randomUUID(),
    role: 'user',
    content,
    richBlocks: [],
    timestamp: new Date().toISOString(),
    type: selectedImage.value ? 'image' : selectedFile.value ? 'file' : 'text'
  }
  messages.value.push(userMsg)
  inputText.value = ''
  const file = selectedFile.value
  const img = selectedImage.value
  selectedImage.value = null
  imagePreviewUrl.value = ''
  selectedFile.value = null
  if (textareaRef.value) textareaRef.value.style.height = 'auto'

  // Assistant 占位
  const assistantMsg = {
    id: crypto.randomUUID(),
    role: 'assistant',
    content: '',
    richBlocks: [],
    toolTrace: [],  // 工具调用过程
    timestamp: new Date().toISOString(),
    state: 'streaming',
    is_brief: true,
    error: null
  }
  messages.value.push(assistantMsg)
  loading.value = true
  await scrollToBottom()

  try {
    // 图片/文件走旧端点（流式还没覆盖 image/file）
    if (file || img) {
      await sendNonStream(content, file, img, assistantMsg)
    } else {
      await sendSSE(content, assistantMsg)
    }
    persistMessages()
  } catch (e) {
    console.error('SSE error', e)
    ElMessage.error(e.message || '发送失败')
    assistantMsg.error = e.message || '发送失败'
    assistantMsg.content = assistantMsg.content || '抱歉，我暂时无法回复，请稍后再试。'
  } finally {
    loading.value = false
    assistantMsg.state = 'idle'
    assistantMsg.is_brief = false
    await scrollToBottom()
  }
}

const sendSSE = async (content, assistantMsg) => {
  for await (const evt of sseFetch('/api/v1/chat/stream', {
    message: content,
    session_id: sessionId.value
  })) {
    if (evt.type === 'text_delta' || evt.type === 'brief' || evt.type === 'detail') {
      assistantMsg.content += evt.delta || ''
      await scrollToBottom()
    } else if (evt.type === 'thinking') {
      assistantMsg.toolTrace.push({ type: 'thinking', label: evt.label })
    } else if (evt.type === 'tool_use') {
      assistantMsg.toolTrace.push({
        type: 'tool',
        name: evt.tool_name,
        state: 'running'
      })
    } else if (evt.type === 'tool_result') {
      const last = assistantMsg.toolTrace[assistantMsg.toolTrace.length - 1]
      if (last && last.type === 'tool' && last.name === evt.tool_name) {
        last.state = 'done'
        last.duration_ms = evt.tool_duration_ms
      }
    } else if (evt.type === 'rich_block') {
      assistantMsg.richBlocks.push(evt.block)
    } else if (evt.type === 'error') {
      assistantMsg.error = evt.message
    } else if (evt.type === 'done') {
      assistantMsg.usage = evt.usage
      assistantMsg.durationMs = evt.duration_ms
    }
  }
}

const sendNonStream = async (text, file, img, assistantMsg) => {
  let res
  if (file) {
    const fd = new FormData(); fd.append('message', text || ''); fd.append('session_id', sessionId.value); fd.append('file', file)
    res = await axios.post('/api/v1/chat/file', fd)
  } else if (img) {
    const fd = new FormData(); fd.append('message', text || '请描述这张图片'); fd.append('session_id', sessionId.value); fd.append('image', img)
    res = await axios.post('/api/v1/chat/image', fd)
  } else {
    res = await axios.post('/api/v1/chat', { message: text, session_id: sessionId.value })
  }
  assistantMsg.content = res.data.content || ''
  // 非流式也带 rich_blocks
  if (Array.isArray(res.data.rich_blocks)) {
    assistantMsg.richBlocks = res.data.rich_blocks
  }
}

// --- 输入栏 ---
const handleKeydown = (e) => {
  if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); sendMessage() }
}
const autoResize = () => {
  const el = textareaRef.value
  if (!el) return
  el.style.height = 'auto'
  el.style.height = Math.min(el.scrollHeight, 120) + 'px'
}
const sendQuickMessage = (t) => { inputText.value = t; sendMessage(t) }
const triggerImageUpload = () => imageInputRef.value?.click()
const triggerFileUpload = () => fileInputRef.value?.click()
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
const clearChat = () => {
  messages.value = [{
    id: crypto.randomUUID(),
    role: 'assistant',
    content: '对话已清空，有什么可以帮你的吗？',
    richBlocks: [],
    timestamp: new Date().toISOString()
  }]
  sessionId.value = `user_${Date.now()}`
  localStorage.removeItem(messagesKey)
  localStorage.setItem(sessionKey, sessionId.value)
}
const toggleVoiceMode = () => { voiceMode.value = !voiceMode.value }
const onRecordStart = () => {}
const onRecordStop = async (blob) => {
  // v2.1: 调 /voice/asr 后再发（先占位）
  console.log('语音停止，待接入 ASR', blob)
}
const onRecordError = () => {}
</script>

<template>
  <div class="chat-immersive" :class="{ 'is-dragging': isDragging }">
    <!-- 网络断线横幅 -->
    <div v-if="!isOnline" class="network-banner">
      <span class="nb-dot" />网络已断开，正在等待恢复...
    </div>

    <!-- 顶部 -->
    <header class="chat-header">
      <div class="header-left">
        <el-avatar :size="36" class="bot-avatar">
          <el-icon><ChatDotRound /></el-icon>
        </el-avatar>
        <div class="header-text">
          <div class="bot-name">小气</div>
          <div class="bot-status"><span class="status-dot" />在线</div>
        </div>
      </div>
      <div class="header-right">
        <el-button text @click="clearChat">清空对话</el-button>
      </div>
    </header>

    <!-- 消息区 -->
    <div ref="messagesRef" class="messages">
      <TransitionGroup name="msg">
      <template v-for="(msg, idx) in messages" :key="msg.id || idx">
        <!-- 时间分割 -->
        <div v-if="idx > 0 && new Date(msg.timestamp) - new Date(messages[idx-1].timestamp) > 5*60*1000" class="time-divider">
          {{ new Date(msg.timestamp).toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' }) }}
        </div>

        <!-- 用户消息 -->
        <div v-if="msg.role === 'user'" class="msg-row user">
          <div class="bubble user-bubble">
            <div v-html="renderMarkdown(msg.content)" />
            <div v-if="msg.imageUrl" class="msg-image">
              <img :src="msg.imageUrl" @click="window.open(msg.imageUrl, '_blank')" />
            </div>
          </div>
        </div>

        <!-- 助手消息 -->
        <div v-else class="msg-row bot">
          <el-avatar :size="32" class="bot-msg-avatar">
            <el-icon><ChatDotRound /></el-icon>
          </el-avatar>
          <div class="bubble bot-bubble">
            <!-- 工具调用过程 -->
            <div v-if="msg.toolTrace && msg.toolTrace.length" class="tool-trace">
              <div v-for="(t, i) in msg.toolTrace" :key="i" class="trace-item" :class="t.state">
                <span v-if="t.type === 'thinking'">{{ t.label }}</span>
                <span v-else>🔧 {{ t.name }} {{ t.state === 'running' ? '...' : '✓' }}<span v-if="t.duration_ms" class="duration"> {{ t.duration_ms }}ms</span></span>
              </div>
            </div>

            <!-- 文本回复（流式累积） -->
            <div v-if="msg.content" class="msg-content" v-html="renderMarkdown(msg.content)" />

            <!-- Rich Blocks 结构化内容 -->
            <div v-if="msg.richBlocks && msg.richBlocks.length" class="rich-blocks">
              <RichContent v-for="(rb, i) in msg.richBlocks" :key="i" :block="rb" />
            </div>

            <!-- 错误 -->
            <div v-if="msg.error" class="msg-error">⚠️ {{ msg.error }}</div>

            <!-- 打字中提示 -->
            <div v-if="msg.state === 'streaming' && !msg.content && !msg.toolTrace?.length" class="typing-bubble">
              <span /><span /><span />
            </div>

            <!-- 底部元信息 -->
            <div v-if="msg.state === 'idle' && (msg.usage || msg.durationMs)" class="msg-meta">
              <span v-if="msg.usage">📊 {{ msg.usage.total_tokens }} tokens</span>
              <span v-if="msg.durationMs">⏱ {{ (msg.durationMs / 1000).toFixed(1) }}s</span>
            </div>
          </div>
        </div>
      </template>
      </TransitionGroup>

      <!-- 欢迎页（仅首条消息时） -->
      <div v-if="messages.length === 1" class="welcome-hero">
        <el-avatar :size="80" class="hero-avatar">
          <el-icon><ChatDotRound /></el-icon>
        </el-avatar>
        <h2>你好，我是小气</h2>
        <p>课题组智能助手，可以帮你查会议、查任务、查知识、查公式</p>
        <div class="quick-actions">
          <button v-for="qa in quickActions" :key="qa.label" class="quick-btn" @click="sendQuickMessage(qa.text)">
            <span class="qa-icon">{{ qa.icon }}</span>
            <span>{{ qa.label }}</span>
          </button>
        </div>
      </div>
    </div>

    <!-- 输入区 -->
    <footer class="input-bar">
      <div class="input-core">
        <div class="input-actions-left">
          <el-button text @click="triggerImageUpload"><span class="iconfont">🖼️</span></el-button>
          <el-button text @click="triggerFileUpload"><span class="iconfont">📎</span></el-button>
          <el-button text @click="toggleVoiceMode"><span class="iconfont">🎤</span></el-button>
        </div>
        <textarea
          ref="textareaRef"
          v-model="inputText"
          class="input-textarea"
          placeholder="问问小气…"
          rows="1"
          @keydown="handleKeydown"
          @input="autoResize"
        />
        <el-button
          type="primary"
          class="send-btn"
          :disabled="!inputText.trim()"
          @click="sendMessage()"
        >
          <span>↑</span>
        </el-button>
      </div>
      <input ref="imageInputRef" type="file" accept="image/*" hidden @change="handleImageSelect" />
      <input ref="fileInputRef" type="file" hidden @change="handleFileSelect" />
    </footer>
  </div>
</template>

<style scoped>
.chat-immersive {
  display: flex; flex-direction: column;
  height: calc(100vh - 120px);
  background: linear-gradient(180deg, #f8f9fb 0%, #fefefe 100%);
  border-radius: var(--radius-lg);
  overflow: hidden;
  position: relative;
}
.network-banner {
  display: flex; align-items: center; gap: 8px;
  padding: 8px 16px;
  background: #ffebee; color: #c62828;
  font-size: 13px; font-weight: 500;
  border-bottom: 1px solid #f5c2c7;
}
.nb-dot {
  width: 8px; height: 8px; border-radius: 50%; background: #f56c6c;
  animation: pulse 1.5s infinite;
}
@keyframes pulse {
  0%, 100% { opacity: 0.5; }
  50% { opacity: 1; }
}
.msg-enter-active { transition: all 0.25s ease; }
.msg-enter-from { opacity: 0; transform: translateY(8px); }
.chat-header {
  display: flex; align-items: center; justify-content: space-between;
  padding: 12px 20px;
  background: rgba(255,255,255,0.85);
  backdrop-filter: blur(12px);
  border-bottom: 1px solid #eee;
}
.header-left { display: flex; align-items: center; gap: 12px; }
.bot-avatar { background: linear-gradient(135deg, #FF7A5C, #FFB347); }
.bot-msg-avatar { background: linear-gradient(135deg, #FF7A5C, #FFB347); flex-shrink: 0; }
.header-text { line-height: 1.2; }
.bot-name { font-weight: 600; font-size: 15px; }
.bot-status { font-size: 12px; color: #999; display: flex; align-items: center; gap: 4px; }
.status-dot { width: 6px; height: 6px; border-radius: 50%; background: #67c23a; }

.messages { flex: 1; overflow-y: auto; padding: 20px; }
.time-divider { text-align: center; font-size: 12px; color: #999; margin: 16px 0; }

.msg-row { display: flex; margin-bottom: 16px; gap: 8px; }
.msg-row.user { justify-content: flex-end; }
.msg-row.bot { justify-content: flex-start; }

.bubble { max-width: 80%; padding: 12px 16px; border-radius: 16px; line-height: 1.6; word-wrap: break-word; }
.user-bubble { background: linear-gradient(135deg, #FF7A5C, #FF9D85); color: white; border-bottom-right-radius: 6px; }
.bot-bubble { background: white; box-shadow: 0 1px 3px rgba(0,0,0,0.06); border-bottom-left-radius: 6px; }

.tool-trace { margin-bottom: 12px; padding: 8px 12px; background: #fafbfc; border-radius: 8px; border-left: 3px solid #FF7A5C; }
.trace-item { font-size: 12px; color: #666; padding: 2px 0; }
.trace-item.running { color: #FF7A5C; }
.trace-item .duration { color: #999; font-size: 11px; }

.msg-content :deep(p) { margin: 0 0 8px; }
.msg-content :deep(p:last-child) { margin-bottom: 0; }
.msg-content :deep(ul), .msg-content :deep(ol) { padding-left: 20px; }
.msg-content :deep(pre) { background: #f6f8fa; padding: 8px 12px; border-radius: 6px; overflow-x: auto; }
.msg-content :deep(code) { background: #f6f8fa; padding: 2px 6px; border-radius: 3px; font-size: 13px; }

.rich-blocks { margin-top: 12px; display: flex; flex-direction: column; gap: 8px; }
.msg-error { color: #f56c6c; font-size: 13px; margin-top: 8px; }
.msg-meta { font-size: 11px; color: #999; margin-top: 8px; display: flex; gap: 12px; }

.typing-bubble { display: inline-flex; gap: 4px; }
.typing-bubble span { width: 6px; height: 6px; border-radius: 50%; background: #FF7A5C; animation: td 1.4s infinite; }
.typing-bubble span:nth-child(2) { animation-delay: 0.2s; }
.typing-bubble span:nth-child(3) { animation-delay: 0.4s; }
@keyframes td { 0%, 60%, 100% { transform: scale(1); opacity: 0.5; } 30% { transform: scale(1.4); opacity: 1; } }

.welcome-hero { text-align: center; padding: 60px 20px 20px; }
.hero-avatar { background: linear-gradient(135deg, #FF7A5C, #FFB347); margin-bottom: 16px; }
.welcome-hero h2 { font-size: 24px; margin: 0 0 8px; color: #333; }
.welcome-hero p { color: #666; margin: 0 0 24px; }
.quick-actions { display: flex; gap: 12px; justify-content: center; flex-wrap: wrap; }
.quick-btn { display: flex; align-items: center; gap: 6px; padding: 10px 18px; background: white; border: 1px solid #e0e0e0; border-radius: 20px; cursor: pointer; transition: all 0.2s; }
.quick-btn:hover { border-color: #FF7A5C; color: #FF7A5C; transform: translateY(-1px); }
.qa-icon { font-size: 18px; }

.input-bar { padding: 16px 20px; background: rgba(255,255,255,0.85); backdrop-filter: blur(20px); border-top: 1px solid #eee; }
.input-core { display: flex; align-items: center; gap: 8px; background: white; border: 1px solid #e0e0e0; border-radius: 20px; padding: 4px 8px; }
.input-actions-left { display: flex; gap: 4px; }
.input-textarea { flex: 1; border: none; outline: none; resize: none; font: inherit; padding: 8px; max-height: 120px; background: transparent; }
.send-btn { width: 34px; height: 34px; padding: 0; border-radius: 50%; background: linear-gradient(135deg, #FF7A5C, #FFB347); border: none; color: white; font-size: 18px; }

@media (max-width: 768px) {
  .bubble { max-width: 92%; }
  .messages { padding: 12px; }
  .chat-immersive { border-radius: 0; height: calc(100vh - 56px); }
}
</style>
