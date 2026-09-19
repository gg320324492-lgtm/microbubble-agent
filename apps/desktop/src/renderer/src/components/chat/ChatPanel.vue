<script setup lang="ts">
// 对话面板 — Agent 循环流式渲染（C-2）：live 虚拟气泡承接轮次/工具卡片/思维链事件，
// send 返回后由带 meta 的持久化消息接管（工具卡片还原为完成态、thinking 折叠面板）；Esc 随时中断
import { computed, nextTick, onMounted, onUnmounted, ref, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import type { ChatMessage, ChatStreamEvent, ModelProvider, ToolCallRecord } from '@shared/types'
import { useAuthStore } from '../../stores/auth'
import { useChatStore } from '../../stores/chat'
import { applyStreamEvent, createLiveState, ROLLBACK_CONFIRM_TEXT, type LiveAgentState } from '../../stores/chat-events'
import { sessionUsageLabel } from '@shared/usage'
import ToolCard from './ToolCard.vue'
import ThinkingPanel from './ThinkingPanel.vue'

const auth = useAuthStore()
const store = useChatStore()

const draft = ref('')
const sending = ref(false)
const providers = ref<ModelProvider[]>([])
const defaultProvider = computed(() => providers.value.find((p) => p.isDefault) ?? null)
const wsRoot = ref<string | null>(null)
const live = ref<LiveAgentState | null>(null)
const streaming = computed(() => live.value !== null)
// V1 用量记账：当前会话累计用量（迁移 010 两列随会话列表下发，无需新 IPC 通道）
const activeSession = computed(() => store.sessions.find((s) => s.id === store.activeId) ?? null)
const activeUsage = computed(() => sessionUsageLabel(activeSession.value))

let offStream: (() => void) | null = null

async function loadProviders(): Promise<void> {
  try {
    providers.value = await window.api.model.list()
  } catch {
    providers.value = []
  }
}

function onStreamEvent(e: ChatStreamEvent): void {
  if (e.sessionId !== store.activeId || !live.value) return
  // 完成收口交给 send promise（持久化消息接管），这里只消费增量/轮次/工具卡片事件
  if (e.type === 'done' || e.type === 'error') return
  applyStreamEvent(live.value, e)
  void scrollToBottom()
}
const messagesEl = ref<HTMLElement | null>(null)

async function onSend(): Promise<void> {
  const text = draft.value.trim()
  if (!text || sending.value) return
  if (!store.activeId) {
    ElMessage.warning('请先在左侧选择或新建会话')
    return
  }
  const isLive = defaultProvider.value !== null
  if (isLive) live.value = createLiveState()
  sending.value = true
  try {
    await store.send(text)
    draft.value = ''
    await scrollToBottom()
  } catch (e) {
    ElMessage.error(e instanceof Error ? e.message : '发送失败')
  } finally {
    live.value = null
    sending.value = false
  }
}

async function onStop(): Promise<void> {
  if (!store.activeId) return
  // main 侧双停（HTTP 流 + 循环）；live 气泡由 onSend 的 finally 收口
  await window.api.chat.abort(store.activeId)
}

function onKeydown(e: KeyboardEvent): void {
  if (e.key === 'Escape' && streaming.value) {
    void onStop()
    return
  }
  if (e.key === 'Enter' && !e.shiftKey && !e.isComposing) {
    e.preventDefault()
    void onSend()
  }
}

/** 写工具确认（C-3）：乐观更新 live 卡片，权威状态由 main 的 tool 事件跟进 */
async function onResolve(call: ToolCallRecord, approve: boolean): Promise<void> {
  if (!store.activeId || !live.value) return
  applyStreamEvent(live.value, {
    type: 'tool',
    sessionId: store.activeId,
    messageId: '',
    call: { ...call, status: approve ? 'running' : 'rejected', summary: approve ? '已批准，执行中…' : '用户拒绝执行' }
  })
  try {
    await window.api.chat.confirmResolve(store.activeId, call.id, approve)
  } catch (e) {
    ElMessage.error(e instanceof Error ? e.message : '确认失败')
  }
}

/** 回滚一次 write_file：二次确认 → main 恢复备份 + 审计 + 回写 meta，这里同步本地卡片 */
async function onRollback(m: ChatMessage, call: ToolCallRecord): Promise<void> {
  if (!store.activeId) return
  try {
    await ElMessageBox.confirm(ROLLBACK_CONFIRM_TEXT, '回滚确认', {
      type: 'warning',
      confirmButtonText: '回滚',
      cancelButtonText: '取消'
    })
  } catch {
    return // 取消
  }
  try {
    const res = await window.api.chat.rollbackWrite(store.activeId, m.id, call.id)
    const target = m.meta?.tools?.find((t) => t.id === call.id)
    if (target) {
      target.summary = '已回滚：已恢复原内容'
      if (target.data && typeof target.data === 'object') (target.data as Record<string, unknown>)['rolledBack'] = true
    }
    ElMessage.success(`已回滚 ${res.path}`)
  } catch (e) {
    ElMessage.error(e instanceof Error ? e.message : '回滚失败')
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

onMounted(() => {
  void loadProviders()
  window.api.workspace
    .get()
    .then((s) => {
      wsRoot.value = s.root
    })
    .catch(() => {
      wsRoot.value = null
    })
  offStream = window.api.chat.onStreamEvent(onStreamEvent)
})
onUnmounted(() => offStream?.())

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
      <span v-if="activeUsage" class="chat-usage" data-testid="chat-usage" :title="`本会话累计用量：输入 ${activeSession?.tokensIn} / 输出 ${activeSession?.tokensOut} tokens`">
        ↑{{ activeUsage.input }} ↓{{ activeUsage.output }}
      </span>
      <span v-if="defaultProvider" class="chat-model chat-model-on" :title="defaultProvider.baseUrl + ' · ' + defaultProvider.model">
        <span class="chat-model-dot" aria-hidden="true"></span>
        {{ defaultProvider.name }} / {{ defaultProvider.model }}
      </span>
      <span v-else class="chat-model" title="到「设置 → 模型服务」配置 API Key">
        <span class="chat-model-dot chat-model-dot-off" aria-hidden="true"></span>
        未配置模型 · 本地回声
      </span>
      <span
        v-if="defaultProvider && !wsRoot"
        class="chat-model"
        title="到「设置 → 工作区」选择 GitHub 仓库根后，Agent 可使用文件工具"
      >
        <span class="chat-model-dot chat-model-dot-off" aria-hidden="true"></span>
        未设置工作区 · 纯对话
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
            <!-- Agent 结构化内容：思维链折叠面板 + 工具卡片（还原为完成态；未决确认降级展示） -->
            <ThinkingPanel v-if="m.role === 'assistant' && m.meta?.thinking" :text="m.meta.thinking" />
            <template v-if="m.role === 'assistant' && m.meta?.tools">
              <ToolCard v-for="c in m.meta.tools" :key="c.id" :call="c" :interactive="true" @rollback="onRollback(m, c)" />
            </template>
            <div class="msg-content">{{ m.content }}</div>
            <div v-if="m.meta?.stopped" class="meta-note">⏹ 已停止 — 以上为已生成的部分内容</div>
            <div v-else-if="m.meta?.hitRoundCap" class="meta-note">⏳ 已达单次任务最大轮数（{{ m.meta.rounds }} 轮），可继续对话接着做</div>
            <div v-if="m.meta && m.meta.toolsAvailable === false" class="meta-note">
              未设置工作区（或模型协议不支持工具）— 本次为纯对话回答
            </div>
            <div class="msg-time">{{ fmtTime(m.createdAt) }}</div>
          </div>
        </div>

        <!-- Agent 循环 live 气泡：轮次提示 / 工具卡片流转 / thinking / 增量正文 -->
        <div v-if="live" class="msg msg-assistant" data-testid="live-bubble">
          <div class="msg-avatar" aria-hidden="true">AI</div>
          <div class="msg-bubble is-streaming">
            <div v-if="live.label" class="round-hint" data-testid="round-hint">{{ live.label }}</div>
            <ThinkingPanel v-if="live.thinking" :text="live.thinking" streaming />
            <ToolCard v-for="c in live.tools" :key="c.id" :call="c" :live="true" @resolve="onResolve" />
            <div v-if="live.text" class="msg-content">{{ live.text }}<span class="stream-cursor" aria-hidden="true">▍</span></div>
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
      <div class="composer-bar">
        <span class="composer-hint">{{
          streaming ? '生成中… Esc 或点停止可中断（已生成内容保留）' : 'Enter 发送 · Shift+Enter 换行'
        }}</span>
        <button v-if="streaming" class="composer-stop" @click="onStop">■ 停止</button>
        <button class="composer-send" :disabled="sending || !draft.trim() || !store.activeId" @click="onSend">
          {{ sending ? '发送中…' : '发送' }}
        </button>
      </div>
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
.chat-usage {
  flex-shrink: 0;
  padding: 2px 8px;
  border-radius: var(--radius-full);
  background: var(--color-bg-tag);
  color: var(--color-text-secondary);
  font-size: var(--font-size-xs);
  font-variant-numeric: tabular-nums;
}
.chat-model {
  flex-shrink: 0;
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: var(--font-size-xs);
  color: var(--color-text-secondary);
}
.chat-model-on {
  color: var(--color-success);
}
.chat-model-dot {
  width: 7px;
  height: 7px;
  border-radius: var(--radius-full);
  background: var(--color-success);
}
.chat-model-dot-off {
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
.is-streaming {
  border-color: rgba(var(--color-primary-rgb), 0.5);
}
.stream-cursor {
  display: inline-block;
  color: var(--color-primary);
  animation: cursorBlink 0.9s steps(2) infinite;
}
@keyframes cursorBlink {
  50% { opacity: 0; }
}
.round-hint {
  margin-bottom: var(--space-2);
  font-size: var(--font-size-xs);
  color: var(--color-primary);
}
.meta-note {
  margin-top: var(--space-2);
  font-size: var(--font-size-xs);
  color: var(--color-text-secondary);
}
.composer-bar {
  margin-top: var(--space-2);
  display: flex;
  align-items: center;
  gap: var(--space-3);
}
.composer-hint {
  flex: 1;
  font-size: 11px;
  color: var(--color-text-placeholder);
}
.composer-stop {
  padding: 8px 18px;
  border: 1px solid var(--color-danger);
  border-radius: var(--radius-md);
  background: transparent;
  color: var(--color-danger);
  font-size: var(--font-size-sm);
  cursor: pointer;
}
.composer-stop:hover {
  background: var(--color-danger-bg);
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
  margin-top: 0;
  font-size: 11px;
  color: var(--color-text-placeholder);
}
</style>
