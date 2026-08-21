<script setup lang="ts">
/**
 * Chat View (Phase 3-A: Reliability Hardened).
 *
 * Phase 3-A 新增:
 *   - 停止 button (流中显示, 点击调 cancelActiveStream)
 *   - 重试 button (lastError 时显示, 调 retryLastMessage)
 *   - 复制 button (assistant message 每条带, 调 copyAssistantMessage)
 *   - session 切换时, store.selectSession() 自动 abort 活跃流 (Phase 3-A 简化)
 */
import { computed, nextTick, onMounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { useChatStore } from '../stores/chat'
import { Loading, EmptyState, ErrorState, MarkdownViewer, Button } from '../components/ui'
import { CitationList } from '../components/chat'
import {
  formatMessageTime,
  roleIcon,
  roleLabel,
  shouldRenderAsMarkdown,
  type StreamCitationEntry
} from '@shared/chat-types'
import { safeKnowledgePush } from '../utils/knowledge-route'

/**
 * Phase 3-D: Citation click -> KnowledgeDetail 路由闭环.
 *
 * - 校验 knowledgeId (number + positive integer). 非法不跳转.
 * - 推到 /knowledge/detail?id=N&from=chat (back 按钮识别)
 * - render 层: Phase 4+ 接 router.push (Knowledge 是 SPA 内 router, 不是真 link)
 * - ChatView context 通过 Pinia store 全局保持 (sessionId / messages / scroll 状态)
 *
 * Spec: Phase 3-D 严格禁止 Retriever / RAG / Backend schema 修改.
 */
function onCitationKnowledgeOpen(knowledgeId: number): void {
  const target = safeKnowledgePush(knowledgeId, { source: 'chat' })
  if (!target) {
    // 非法 id (Phase 3-D 不发生, ChatView 不会传非法值, 兜底提示)
    // eslint-disable-next-line no-console
    console.warn('[ChatView] invalid knowledgeId ignored:', knowledgeId)
    return
  }
  void router.push(target)
}

const store = useChatStore()

const inputDraft = ref('')
const listEl = ref<HTMLElement | null>(null)
const copyToast = ref<string | null>(null)
let copyToastTimer: ReturnType<typeof setTimeout> | null = null

const hasMessages = computed(() => store.visibleMessages.length > 0)
const hasStreaming = computed(() => store.isStreaming && !!store.streamingMessage)

/**
 * Phase 3-D: Chat → Knowledge 路由.
 * useRouter() 在 setup() 内通过注入拿到 router 实例.
 */
const router = useRouter()

/**
 * 派生: 从 message.message_metadata (含 citations) 取出 StreamCitationEntry[].
 * Phase 3-C1: 后端 ChatMessageOut 没有顶层 citations, 持久化在 message_metadata 里.
 */
function extractMessageCitations(msg: { message_metadata?: Record<string, unknown> }): StreamCitationEntry[] {
  const md = msg.message_metadata
  if (!md || !Array.isArray(md.citations)) return []
  return md.citations as StreamCitationEntry[]
}

async function onSend(): Promise<void> {
  const text = inputDraft.value.trim()
  if (text.length === 0 || store.sending) return
  inputDraft.value = ''
  const ok = await store.sendUserMessageStream(text)
  if (ok) {
    await nextTick()
    scrollToBottom()
  } else {
    inputDraft.value = text
  }
}

async function onCancel(): Promise<void> {
  await store.cancelActiveStream()
  // store.handleStreamError / handleStreamEnd 会清 streamingMessage
  await nextTick()
}

async function onRetry(): Promise<void> {
  await store.retryLastMessage()
  await nextTick()
  scrollToBottom()
}

async function onCopyMessage(msgId: number): Promise<void> {
  const ok = await store.copyAssistantMessage(msgId)
  showCopyToast(ok ? '已复制到剪贴板' : '复制失败, 请手动 Ctrl+C')
}

function showCopyToast(text: string): void {
  copyToast.value = text
  if (copyToastTimer) clearTimeout(copyToastTimer)
  copyToastTimer = setTimeout(() => { copyToast.value = null }, 2000)
}

function onSessionClick(sessionId: string): void {
  if (sessionId === store.currentSessionId) return
  void store.selectSession(sessionId)
}

function scrollToBottom(): void {
  if (!listEl.value) return
  listEl.value.scrollTop = listEl.value.scrollHeight
}

onMounted(async () => {
  await store.loadSessions()
  await store.selectSession(store.currentSessionId)
  await nextTick()
  scrollToBottom()
})

watch(
  () => store.streamingContentRender,
  () => nextTick(() => scrollToBottom())
)
</script>

<template>
  <div class="chat-view">
    <!-- Header -->
    <header class="chat-header">
      <div class="chat-header__left">
        <h2 class="chat-header__title">💬 {{ store.currentSessionTitle }}</h2>
        <span class="chat-header__badge">
          消息 {{ store.visibleMessages.length }} 条
          <span v-if="hasStreaming" class="chat-header__stream">· 流式中</span>
        </span>
      </div>
      <div class="chat-header__right">
        <span class="chat-header__hint">
          Phase 3-A · Reliability Hardened
        </span>
      </div>
    </header>

    <!-- Body: 左栏 + 主区 -->
    <div class="chat-body">
      <aside class="chat-sessions">
        <div class="chat-section-title">
          <span>会话列表</span>
          <span class="muted">({{ store.sessions.length }})</span>
        </div>
        <Loading v-if="store.sessionsLoading && store.sessions.length === 0" variant="skeleton" :rows="4" />
        <EmptyState
          v-else-if="store.sessions.length === 0 && !store.sessionsLoading"
          icon="💬"
          title="尚无会话"
          description="开始发送消息会自动创建默认会话"
        />
        <ul v-else class="chat-session-list">
          <li v-for="s in store.sessions" :key="s.id">
            <button
              type="button"
              :class="['chat-session-item', { 'is-active': s.id === store.currentSessionId }]"
              @click="onSessionClick(s.id)"
            >
              <div class="chat-session-item__title">{{ s.title || '(无标题)' }}</div>
              <div class="chat-session-item__preview">{{ s.preview || '（无预览）' }}</div>
              <div class="chat-session-item__meta">
                <span>{{ s.message_count }} 条</span>
                <span v-if="s.last_message_at">{{ formatMessageTime(s.last_message_at) }}</span>
                <span v-if="s.is_pinned" class="pin-badge">📌</span>
                <span v-if="s.is_archived" class="archived-badge">已归档</span>
              </div>
            </button>
          </li>
        </ul>
      </aside>

      <section class="chat-main">
        <div v-if="store.lastError" class="chat-error-row">
          <ErrorState
            :message="store.lastError.message"
            @retry="store.clearError"
          />
          <Button
            v-if="store.lastSentText && !store.isStreaming && !store.sending"
            variant="primary"
            size="small"
            @click="onRetry"
          >
            🔁 重试
          </Button>
        </div>

        <div ref="listEl" class="chat-messages">
          <Loading
            v-if="store.messagesLoading && !hasMessages && !hasStreaming"
            variant="spinner"
            text="加载消息中..."
          />

          <EmptyState
            v-else-if="!hasMessages && !store.messagesLoading && !hasStreaming"
            icon="✨"
            title="开始对话吧"
            description="在下方输入框中发送消息"
          />

          <template v-else>
            <div
              v-for="msg in store.visibleMessages"
              :key="msg.id"
              :class="['chat-message', `chat-message--${msg.role}`]"
            >
              <div class="chat-message__avatar">{{ roleIcon(msg.role) }}</div>
              <div class="chat-message__body">
                <div class="chat-message__head">
                  <span class="chat-message__role">{{ roleLabel(msg.role) }}</span>
                  <span class="chat-message__time">{{ formatMessageTime(msg.created_at) }}</span>
                </div>
                <div class="chat-message__content">
                  <MarkdownViewer
                    v-if="shouldRenderAsMarkdown(msg.role)"
                    :source="msg.content"
                    body-class="chat-md"
                  />
                  <pre v-else class="chat-message__text">{{ msg.content }}</pre>
                </div>
                <CitationList
                  v-if="msg.role === 'assistant'"
                  :citations="extractMessageCitations(msg)"
                  :get-cached-hint="store.getCachedHint"
                  @knowledge-open="onCitationKnowledgeOpen"
                />
                <div v-if="msg.attached_knowledge_ids && msg.attached_knowledge_ids.length > 0" class="chat-message__attachments">
                  <span class="muted">📎 引用 {{ msg.attached_knowledge_ids.length }} 条知识</span>
                </div>
                <div v-if="msg.role === 'assistant'" class="chat-message__actions">
                  <button type="button" class="chat-msg-btn" @click="onCopyMessage(msg.id)" title="复制 assistant 内容">
                    📋 复制
                  </button>
                </div>
              </div>
            </div>

            <div
              v-if="hasStreaming && store.streamingMessage"
              class="chat-message chat-message--assistant chat-message--streaming"
            >
              <div class="chat-message__avatar">🧠</div>
              <div class="chat-message__body">
                <div class="chat-message__head">
                  <span class="chat-message__role">小气</span>
                  <span class="chat-message__time">流式中...</span>
                  <span class="chat-message__pulse">●●●</span>
                </div>

                <div
                  v-if="store.streamingMessage.thinking"
                  class="chat-message__thinking-label"
                >
                  💭 {{ store.streamingMessage.thinking }}
                </div>

                <div v-if="store.streamingMessage.content" class="chat-message__content">
                  <MarkdownViewer
                    :source="store.streamingContentRender"
                    body-class="chat-md chat-md-streaming"
                  />
                </div>
                <div v-else class="chat-message__cursor-line">
                  <span class="chat-cursor">▍</span>
                </div>

                <!-- Phase 3-C1: 流中 citation 累加, 实时呈现 -->
                <CitationList
                  v-if="store.streamingMessage.citations && store.streamingMessage.citations.length > 0"
                  :citations="store.streamingMessage.citations"
                  :get-cached-hint="store.getCachedHint"
                  @knowledge-open="onCitationKnowledgeOpen"
                />

                <div class="chat-message__streaming-footer">
                  <span class="muted">
                    {{ store.streamingMessage.content.length }} chars
                  </span>
                </div>
              </div>
            </div>
          </template>
        </div>

        <form class="chat-input" @submit.prevent="onSend">
          <textarea
            v-model="inputDraft"
            class="chat-input__textarea"
            placeholder="向小气提问 (Shift+Enter 换行, Enter 发送)"
            :disabled="store.sending || hasStreaming"
            rows="3"
            @keydown.enter.exact.prevent="onSend"
          />
          <div class="chat-input__buttons">
            <Button
              v-if="hasStreaming"
              variant="danger"
              size="medium"
              @click="onCancel"
            >
              ⏹ 停止生成
            </Button>
            <button
              v-else
              type="submit"
              class="chat-input__send"
              :disabled="store.sending || hasStreaming || inputDraft.trim().length === 0"
            >
              <span v-if="store.sending" class="chat-input__spinner" />
              发送 ⏎
            </button>
          </div>
        </form>
      </section>
    </div>

    <!-- 复制 toast -->
    <Transition name="toast">
      <div v-if="copyToast" class="chat-toast">{{ copyToast }}</div>
    </Transition>
  </div>
</template>

<style scoped>
.chat-view {
  display: flex;
  flex-direction: column;
  height: 100%;
  background: #020617;
  color: #e2e8f0;
}

.chat-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0.8rem 1.5rem;
  background: #0f172a;
  border-bottom: 1px solid #1e293b;
  flex-shrink: 0;
}
.chat-header__title {
  margin: 0;
  font-size: 1.05rem;
  color: #f1f5f9;
}
.chat-header__badge {
  margin-left: 0.6rem;
  font-size: 0.75rem;
  color: #94a3b8;
}
.chat-header__stream { color: #fbbf24; margin-left: 0.3rem; }
.chat-header__hint { font-size: 0.75rem; color: #64748b; }

.chat-body {
  flex: 1;
  display: flex;
  min-height: 0;
}

.chat-sessions {
  width: 240px;
  min-width: 240px;
  background: #0f172a;
  border-right: 1px solid #1e293b;
  overflow-y: auto;
  padding: 0.8rem 0.5rem;
}
.chat-section-title {
  display: flex;
  justify-content: space-between;
  font-size: 0.7rem;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: #64748b;
  padding: 0.4rem 0.6rem;
}
.muted { color: #64748b; }

.chat-session-list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 0.15rem;
}
.chat-session-item {
  display: block;
  width: 100%;
  text-align: left;
  background: transparent;
  border: 1px solid transparent;
  border-radius: 4px;
  padding: 0.5rem 0.6rem;
  color: #cbd5e1;
  cursor: pointer;
  font-family: inherit;
}
.chat-session-item:hover { background: rgba(148, 163, 184, 0.06); }
.chat-session-item.is-active {
  background: rgba(249, 115, 22, 0.12);
  color: #f97316;
  border-color: rgba(249, 115, 22, 0.3);
}
.chat-session-item__title {
  font-size: 0.85rem; font-weight: 600;
  white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
}
.chat-session-item__preview {
  font-size: 0.75rem; color: #94a3b8;
  white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
}
.chat-session-item__meta {
  margin-top: 0.3rem;
  font-size: 0.7rem; color: #64748b;
  display: flex; gap: 0.4rem;
}
.pin-badge { color: #fbbf24; }
.archived-badge { color: #64748b; font-style: italic; }

.chat-main {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-width: 0;
  padding: 1rem 1.5rem;
  overflow: hidden;
}

.chat-error-row {
  display: flex;
  align-items: center;
  gap: 0.6rem;
  margin-bottom: 0.5rem;
}

.chat-messages {
  flex: 1;
  overflow-y: auto;
  padding-right: 0.5rem;
  display: flex;
  flex-direction: column;
  gap: 1rem;
}
.chat-message {
  display: flex;
  align-items: flex-start;
  gap: 0.6rem;
  padding: 0.6rem 0.8rem;
  border-radius: 8px;
}
.chat-message--user {
  background: rgba(99, 102, 241, 0.07);
  border: 1px solid rgba(99, 102, 241, 0.18);
}
.chat-message--assistant {
  background: rgba(249, 115, 22, 0.05);
  border: 1px solid rgba(249, 115, 22, 0.18);
}
.chat-message--system, .chat-message--tool {
  background: rgba(148, 163, 184, 0.06);
  border: 1px solid rgba(148, 163, 184, 0.18);
}
.chat-message--streaming {
  border-style: dashed;
  border-color: rgba(249, 115, 22, 0.3);
  animation: streaming-pulse 2s ease-in-out infinite;
}
@keyframes streaming-pulse {
  0%, 100% { background: rgba(249, 115, 22, 0.05); }
  50% { background: rgba(249, 115, 22, 0.12); }
}
.chat-message__avatar {
  font-size: 1.3rem; width: 2rem; text-align: center; flex-shrink: 0;
}
.chat-message__body { flex: 1; min-width: 0; }
.chat-message__head {
  display: flex; align-items: center; gap: 0.6rem;
  margin-bottom: 0.4rem; font-size: 0.8rem;
}
.chat-message__role { font-weight: 600; color: #f1f5f9; }
.chat-message__time { color: #64748b; font-size: 0.75rem; }
.chat-message__pulse {
  color: #fbbf24; font-weight: bold; letter-spacing: 0.2em;
  animation: dot-flashing 1.4s infinite linear;
}
@keyframes dot-flashing {
  0%, 100% { opacity: 0.2; }
  50% { opacity: 1; }
}
.chat-message__thinking-label {
  background: rgba(251, 191, 36, 0.08);
  border-left: 3px solid #fbbf24;
  padding: 0.3rem 0.6rem;
  margin-bottom: 0.4rem;
  font-size: 0.8rem;
  color: #fbbf24;
  border-radius: 2px;
}
.chat-message__content { font-size: 0.92rem; }
.chat-message__text {
  margin: 0; white-space: pre-wrap; word-break: break-word; color: #e2e8f0;
}
.chat-message__attachments { margin-top: 0.4rem; font-size: 0.75rem; }
.chat-message__streaming-footer {
  margin-top: 0.4rem; font-size: 0.7rem; color: #64748b;
}
.chat-message__actions {
  margin-top: 0.4rem;
  display: flex;
  gap: 0.4rem;
}
.chat-msg-btn {
  background: transparent;
  border: 1px solid #334155;
  color: #94a3b8;
  padding: 0.2rem 0.5rem;
  border-radius: 3px;
  font-size: 0.7rem;
  cursor: pointer;
  font-family: inherit;
  transition: all 0.15s;
}
.chat-msg-btn:hover {
  border-color: #f97316;
  color: #f97316;
}
.chat-message__cursor-line {
  display: flex;
  align-items: center;
  height: 1.5rem;
}
.chat-cursor {
  display: inline-block;
  color: #f97316;
  font-weight: bold;
  animation: cursor-blink 1.1s infinite;
}
@keyframes cursor-blink {
  0%, 50% { opacity: 1; }
  51%, 100% { opacity: 0; }
}

.chat-input {
  display: flex;
  gap: 0.5rem;
  align-items: flex-end;
  padding-top: 0.6rem;
  border-top: 1px solid #1e293b;
  flex-shrink: 0;
}
.chat-input__textarea {
  flex: 1;
  resize: vertical;
  min-height: 60px;
  max-height: 200px;
  padding: 0.6rem 0.8rem;
  background: #0f172a;
  border: 1px solid #334155;
  border-radius: 5px;
  color: #f1f5f9;
  font-family: inherit;
  font-size: 0.92rem;
  line-height: 1.5;
}
.chat-input__textarea:focus { outline: none; border-color: #f97316; }
.chat-input__textarea:disabled { opacity: 0.5; }
.chat-input__buttons {
  display: flex;
  flex-direction: column;
  gap: 0.3rem;
  align-items: stretch;
}
.chat-input__send {
  background: #f97316;
  color: #fff;
  border: 0;
  padding: 0.6rem 1rem;
  border-radius: 4px;
  font-size: 0.9rem;
  cursor: pointer;
  font-family: inherit;
  display: flex;
  align-items: center;
  gap: 0.3rem;
}
.chat-input__send:hover:not(:disabled) { background: #ea580c; }
.chat-input__send:disabled { opacity: 0.4; cursor: not-allowed; }
.chat-input__spinner {
  width: 12px; height: 12px;
  border: 2px solid #fff;
  border-right-color: transparent;
  border-radius: 50%;
  animation: spin 0.6s linear infinite;
}
@keyframes spin { to { transform: rotate(360deg); } }

.chat-toast {
  position: fixed;
  bottom: 1.5rem;
  left: 50%;
  transform: translateX(-50%);
  background: #1e293b;
  color: #f1f5f9;
  padding: 0.5rem 1rem;
  border-radius: 4px;
  border: 1px solid #334155;
  font-size: 0.85rem;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.3);
  z-index: 100;
}
.toast-enter-active, .toast-leave-active {
  transition: opacity 0.2s, transform 0.2s;
}
.toast-enter-from, .toast-leave-to {
  opacity: 0;
  transform: translate(-50%, 8px);
}

:deep(.chat-md) { color: #e2e8f0; }
:deep(.chat-md .md-p) { color: #cbd5e1; }
</style>
