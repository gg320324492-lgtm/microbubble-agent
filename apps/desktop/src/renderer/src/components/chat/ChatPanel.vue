<script setup lang="ts">
// 对话面板 — 消息流 + 空态欢迎页 + 输入区（M1-A 为本地回声应答，M1-B 接流式模型）
import { nextTick, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { useAuthStore } from '../../stores/auth'
import { useChatStore } from '../../stores/chat'

const auth = useAuthStore()
const store = useChatStore()

const draft = ref('')
const sending = ref(false)
const messagesEl = ref<HTMLElement | null>(null)

async function onSend(): Promise<void> {
  const text = draft.value.trim()
  if (!text || sending.value) return
  if (!store.activeId) {
    ElMessage.warning('请先在左侧选择或新建会话')
    return
  }
  sending.value = true
  try {
    await store.send(text)
    draft.value = ''
    await scrollToBottom()
  } catch (e) {
    ElMessage.error(e instanceof Error ? e.message : '发送失败')
  } finally {
    sending.value = false
  }
}

function onKeydown(e: KeyboardEvent): void {
  if (e.key === 'Enter' && !e.shiftKey && !e.isComposing) {
    e.preventDefault()
    void onSend()
  }
}

async function scrollToBottom(): Promise<void> {
  await nextTick()
  if (messagesEl.value) messagesEl.value.scrollTop = messagesEl.value.scrollHeight
}

watch(
  () => store.activeId,
  () => void scrollToBottom()
)

const suggestions = [
  { icon: '🧪', title: '设计实验方案', text: '帮我设计一个臭氧微纳米气泡降解四环素的对比实验方案' },
  { icon: '📊', title: '分析实验数据', text: '我有一组降解率随时间变化的数据，帮我分析动力学参数' },
  { icon: '📚', title: '梳理文献结论', text: '总结微纳米气泡强化臭氧化技术的研究进展' },
  { icon: '📝', title: '润色论文段落', text: '帮我润色一段论文摘要，使其更符合 SCI 期刊表达习惯' }
]

async function onStart(text: string): Promise<void> {
  await store.create()
  draft.value = text
}

function fmtTime(ts: number): string {
  return new Date(ts).toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })
}
</script>

<template>
  <section class="chat">
    <header class="chat-head">
      <span class="chat-title">{{ store.sessions.find((s) => s.id === store.activeId)?.title || 'AI 助手' }}</span>
      <span class="chat-model" title="模型网关将在 M1-B 接入">
        <span class="chat-model-dot" aria-hidden="true"></span>
        本地回声模式 · 模型网关 M1-B 接入
      </span>
    </header>

    <div ref="messagesEl" class="chat-body">
      <!-- 空态欢迎页 -->
      <div v-if="!store.activeId" class="chat-welcome">
        <h1>你好，{{ auth.user?.displayName || auth.user?.username }}</h1>
        <p>这是你的本地科研 Agent 工作台。对话与数据全部保存在本机。</p>
        <div class="chat-suggestions">
          <button v-for="sg in suggestions" :key="sg.title" class="suggestion" @click="onStart(sg.text)">
            <span class="suggestion-icon" aria-hidden="true">{{ sg.icon }}</span>
            <span class="suggestion-title">{{ sg.title }}</span>
            <span class="suggestion-text">{{ sg.text }}</span>
          </button>
        </div>
      </div>

      <!-- 消息流 -->
      <template v-else>
        <div v-for="m in store.messages" :key="m.id" class="msg" :class="`msg-${m.role}`">
          <div class="msg-avatar" aria-hidden="true">{{ m.role === 'user' ? '我' : 'AI' }}</div>
          <div class="msg-bubble">
            <div class="msg-content">{{ m.content }}</div>
            <div class="msg-time">{{ fmtTime(m.createdAt) }}</div>
          </div>
        </div>
      </template>
    </div>

    <footer class="chat-composer">
      <textarea
        v-model="draft"
        class="composer-input"
        rows="2"
        placeholder="向 AI 助手提问…（Enter 发送，Shift+Enter 换行）"
        :disabled="sending"
        @keydown="onKeydown"
      ></textarea>
      <button class="composer-send" :disabled="sending || !draft.trim() || !store.activeId" @click="onSend">
        {{ sending ? '发送中…' : '发送' }}
      </button>
      <p class="composer-hint">当前为本地回声模式；接入模型后此窗口即为完整 Agent（工具调用 · 流式输出）。</p>
    </footer>
  </section>
</template>

<style scoped>
.chat {
  flex: 1;
  display: grid;
  grid-template-rows: auto 1fr auto;
  min-width: 0;
  background: var(--color-bg-page);
}
.chat-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: var(--space-3) var(--space-5);
  border-bottom: 1px solid var(--color-border);
  background: var(--color-bg-card);
}
.chat-title {
  font-size: var(--font-size-md);
  font-weight: var(--font-weight-semibold);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.chat-model {
  flex-shrink: 0;
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: var(--font-size-xs);
  color: var(--color-text-secondary);
}
.chat-model-dot {
  width: 7px;
  height: 7px;
  border-radius: var(--radius-full);
  background: var(--color-warning);
}
.chat-body {
  overflow-y: auto;
  padding: var(--space-5);
}
/* 空态 */
.chat-welcome {
  max-width: 720px;
  margin: 8vh auto 0;
  text-align: center;
}
.chat-welcome h1 {
  font-size: 24px;
  font-weight: var(--font-weight-semibold);
}
.chat-welcome > p {
  margin-top: var(--space-2);
  color: var(--color-text-secondary);
}
.chat-suggestions {
  margin-top: var(--space-6);
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: var(--space-3);
}
.suggestion {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 4px;
  padding: var(--space-4);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-lg);
  background: var(--color-bg-card);
  cursor: pointer;
  text-align: left;
  transition: all var(--duration-fast) var(--ease-out);
}
.suggestion:hover {
  border-color: rgba(var(--color-primary-rgb), 0.45);
  box-shadow: var(--shadow-sm);
  transform: translateY(-2px);
}
.suggestion-icon {
  font-size: 18px;
}
.suggestion-title {
  font-size: var(--font-size-sm);
  font-weight: var(--font-weight-semibold);
  color: var(--color-text-primary);
}
.suggestion-text {
  font-size: var(--font-size-xs);
  color: var(--color-text-secondary);
  line-height: 1.6;
}
/* 消息流 */
.msg {
  display: flex;
  gap: var(--space-3);
  margin-bottom: var(--space-4);
  max-width: 780px;
}
.msg-user {
  margin-left: auto;
  flex-direction: row-reverse;
}
.msg-avatar {
  flex-shrink: 0;
  width: 30px;
  height: 30px;
  display: grid;
  place-items: center;
  border-radius: var(--radius-md);
  font-size: var(--font-size-xs);
  font-weight: var(--font-weight-semibold);
  background: var(--color-bg-secondary);
  color: var(--color-text-secondary);
}
.msg-user .msg-avatar {
  background: var(--gradient-welcome-hero);
  color: #fff;
}
.msg-assistant .msg-avatar {
  background: var(--wb-panel-950);
  color: var(--wb-panel-text);
}
.msg-bubble {
  min-width: 0;
  padding: var(--space-3) var(--space-4);
  border-radius: var(--radius-lg);
  background: var(--color-bg-card);
  border: 1px solid var(--color-border);
}
.msg-user .msg-bubble {
  background: var(--color-primary);
  border-color: var(--color-primary);
}
.msg-user .msg-content {
  color: #fff;
}
.msg-user .msg-time {
  color: rgba(255, 255, 255, 0.7);
}
.msg-content {
  font-size: var(--font-size-base);
  line-height: 1.75;
  white-space: pre-wrap;
  word-break: break-word;
}
.msg-time {
  margin-top: var(--space-1);
  font-size: 11px;
  color: var(--color-text-placeholder);
}
/* 输入区 */
.chat-composer {
  padding: var(--space-3) var(--space-5) var(--space-4);
  border-top: 1px solid var(--color-border);
  background: var(--color-bg-card);
}
.composer-input {
  width: 100%;
  resize: none;
  padding: var(--space-3);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-lg);
  background: var(--color-bg-page);
  color: var(--color-text-primary);
  font-size: var(--font-size-base);
  font-family: inherit;
  line-height: 1.6;
}
.composer-input:focus {
  outline: none;
  border-color: var(--color-primary);
  box-shadow: 0 0 0 3px rgba(var(--color-primary-rgb), 0.1);
}
.composer-send {
  margin-top: var(--space-2);
  float: right;
  padding: 8px 22px;
  border: none;
  border-radius: var(--radius-md);
  background: var(--color-primary);
  color: #fff;
  font-size: var(--font-size-sm);
  font-weight: var(--font-weight-medium);
  cursor: pointer;
  box-shadow: var(--shadow-primary);
  transition: filter var(--duration-fast) var(--ease-out);
}
.composer-send:hover:not(:disabled) {
  filter: brightness(1.06);
}
.composer-send:disabled {
  opacity: 0.5;
  cursor: not-allowed;
  box-shadow: none;
}
.composer-hint {
  clear: both;
  margin-top: var(--space-2);
  font-size: 11px;
  color: var(--color-text-placeholder);
}
</style>
