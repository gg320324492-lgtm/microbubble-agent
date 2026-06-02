<template>
  <div class="ai-float-btn">
    <div v-if="!expanded" class="ai-collapsed" @click="toggle">
      🤖
    </div>
    <div v-else class="ai-panel">
      <div class="ai-header">
        <span>小气助手</span>
        <el-button text @click="toggle">×</el-button>
      </div>
      <div class="ai-actions">
        <el-button @click="onSummarizeRecent" :loading="loading.action === 'summarize_recent'" size="small">
          📝 总结最近 30 秒
        </el-button>
        <el-button @click="onTranslate" :loading="loading.action === 'translate'" size="small">
          🌐 中英翻译
        </el-button>
        <el-button @click="onSummarizeNow" :loading="loading.action === 'summarize_now'" size="small">
          📋 现在总结
        </el-button>
        <el-button @click="onAskVisible = true" :loading="loading.action === 'ask'" size="small">
          🤔 AI 提问
        </el-button>
      </div>
      <div class="ai-history" v-if="history.length > 0">
        <div v-for="(item, i) in history" :key="i" class="history-item">
          <span class="action-label">{{ actionLabel(item.action) }}</span>
          <span class="text">{{ item.text }}</span>
          <el-button v-if="item.ttsBase64" link @click="playTTS(item.ttsBase64)">🔊</el-button>
        </div>
      </div>
    </div>
    <el-dialog v-model="onAskVisible" title="AI 提问" width="400px">
      <el-input v-model="askQuestion" name="askQuestion" type="textarea" :rows="3" placeholder="例如：刚才说的数据有出处吗？" />
      <template #footer>
        <el-button @click="onAskVisible = false">取消</el-button>
        <el-button type="primary" @click="onAsk">提问</el-button>
      </template>
    </el-dialog>
    <audio ref="ttsAudio" style="display:none" />
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'

const props = defineProps({
  onSendAICommand: { type: Function, required: true },
})
const emit = defineEmits(['air-reply'])

const expanded = ref(false)
const loading = ref({ action: null })
const history = ref([])
const onAskVisible = ref(false)
const askQuestion = ref('')
const ttsAudio = ref(null)

const storageKey = `meeting_ai_history_${window.location.pathname.split('/').pop()}`

onMounted(() => {
  // 从 localStorage 恢复
  try {
    const saved = localStorage.getItem(storageKey)
    if (saved) history.value = JSON.parse(saved)
  } catch (e) {}
})

function toggle() {
  expanded.value = !expanded.value
}

function onSummarizeRecent() {
  loading.value.action = 'summarize_recent'
  props.onSendAICommand('summarize_recent', { seconds: 30 })
  setTimeout(() => loading.value.action = null, 5000)
}

function onTranslate() {
  loading.value.action = 'translate'
  // 简化：翻译最近 transcript 的内容（生产可让用户选中文字）
  props.onSendAICommand('translate', { text: '（翻译占位）', lang: 'en' })
  setTimeout(() => loading.value.action = null, 5000)
}

function onSummarizeNow() {
  loading.value.action = 'summarize_now'
  props.onSendAICommand('summarize_now', {})
  setTimeout(() => loading.value.action = null, 10000)
}

function onAsk() {
  if (!askQuestion.value.trim()) return
  loading.value.action = 'ask'
  props.onSendAICommand('ask', { question: askQuestion.value })
  askQuestion.value = ''
  onAskVisible.value = false
  setTimeout(() => loading.value.action = null, 5000)
}

function actionLabel(action) {
  return { summarize_recent: '📝 30s', translate: '🌐 翻译', summarize_now: '📋 纪要', ask: '🤔 问' }[action] || action
}

function playTTS(base64) {
  const bytes = Uint8Array.from(atob(base64), c => c.charCodeAt(0))
  const blob = new Blob([bytes], { type: 'audio/mpeg' })
  ttsAudio.value.src = URL.createObjectURL(blob)
  ttsAudio.value.play()
}

function addHistoryItem(item) {
  history.value.push({ ...item, ts: Date.now() })
  // 截断最近 50 条
  if (history.value.length > 50) history.value = history.value.slice(-50)
  // 持久化
  try {
    localStorage.setItem(storageKey, JSON.stringify(history.value))
  } catch (e) {}
}

defineExpose({ addHistoryItem })
</script>

<style scoped>
.ai-float-btn {
  position: fixed;
  right: 24px;
  bottom: 100px;
  z-index: 100;
}
.ai-collapsed {
  width: 50px;
  height: 50px;
  line-height: 50px;
  text-align: center;
  font-size: 24px;
  background: #ff7a5c;
  border-radius: 50%;
  cursor: pointer;
  box-shadow: 0 4px 12px rgba(255, 122, 92, 0.4);
}
.ai-panel {
  width: 280px;
  max-height: 400px;
  background: rgba(30, 30, 50, 0.95);
  border-radius: 8px;
  padding: 12px;
  overflow-y: auto;
}
.ai-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  color: white;
  font-size: 14px;
  margin-bottom: 12px;
}
.ai-actions {
  display: flex;
  flex-direction: column;
  gap: 4px;
  margin-bottom: 12px;
}
.ai-history {
  border-top: 1px solid rgba(255,255,255,0.2);
  padding-top: 8px;
}
.history-item {
  padding: 6px 0;
  color: white;
  font-size: 12px;
  display: flex;
  gap: 6px;
  align-items: flex-start;
}
.action-label {
  flex-shrink: 0;
  font-weight: 500;
  color: #ff7a5c;
}
.text {
  flex: 1;
  word-break: break-word;
}
</style>
