<script setup lang="ts">
/**
 * Chat View (Phase 2-Impl-3A 基础模块)。
 *
 * 三段式布局:
 *   ┌────────────────────────────────────────────────────┐
 *   │  Header: session.title + 消息数                        │
 *   ├──────────────┬──────────────────────────────────────┤
 *   │  左侧:       │  右侧: 消息列表 + 输入框                │
 *   │  sessions    │                                       │
 *   └──────────────┴──────────────────────────────────────┘
 *
 * 数据流 (全部 IPC → main api.service → 后端):
 *   GET /chat/sessions                 → sessions list (左栏)
 *   GET /chat/sessions/{id}            → loadMessages
 *   GET /chat/sessions/{id}/messages   → messages list (中右)
 *   POST /chat                         → sendUserMessage (Phase 2 同步)
 *
 * 范围外:
 *   - ❌ Streaming (Phase 3+ 接 /chat/stream SSE)
 *   - ❌ RAG / 知识库引用 / 多模态 (Phase 3+)
 *   - ❌ 编辑 / 重发 / 反馈 (Phase 3+)
 *
 * Markdown 渲染:
 *   - Assistant 消息复用 MarkdownViewer (Phase 2-Impl-2B), 安全 (无 v-html)
 *   - User 消息纯文本 (white-space: pre-wrap), 不解析 markdown
 */
import { computed, nextTick, onMounted, ref } from 'vue'
import { useChatStore } from '../stores/chat'
import { Loading, EmptyState, ErrorState, MarkdownViewer } from '../components/ui'
import {
  formatMessageTime,
  roleIcon,
  roleLabel,
  shouldRenderAsMarkdown
} from '@shared/chat-types'

const store = useChatStore()

const inputDraft = ref('')
const listEl = ref<HTMLElement | null>(null)

const hasMessages = computed(() => store.visibleMessages.length > 0)

async function onSend(): Promise<void> {
  const text = inputDraft.value.trim()
  if (text.length === 0 || store.sending) return
  inputDraft.value = ''
  const ok = await store.sendUserMessage(text)
  if (ok) {
    await nextTick()
    scrollToBottom()
  } else {
    // 失败: 还原输入
    inputDraft.value = text
  }
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
  // 拉默认 session 的消息
  await store.selectSession(store.currentSessionId)
  await nextTick()
  scrollToBottom()
})
</script>

<template>
  <div class="chat-view">
    <!-- Header -->
    <header class="chat-header">
      <div class="chat-header__left">
        <h2 class="chat-header__title">💬 {{ store.currentSessionTitle }}</h2>
        <span class="chat-header__badge">
          消息 {{ store.visibleMessages.length }} 条
        </span>
      </div>
      <div class="chat-header__right">
        <span class="chat-header__hint">
          Phase 2-Impl-3A · 同步模式
        </span>
      </div>
    </header>

    <!-- Body: 左栏 + 主区 -->
    <div class="chat-body">
      <!-- 左栏: Session List -->
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

      <!-- 主区: Messages + Input -->
      <section class="chat-main">
        <!-- Error 全局条 -->
        <ErrorState
          v-if="store.lastError"
          :message="store.lastError.message"
          @retry="store.clearError"
        />

        <!-- Messages list -->
        <div ref="listEl" class="chat-messages">
          <Loading
            v-if="store.messagesLoading && !hasMessages"
            variant="spinner"
            text="加载消息中..."
          />

          <EmptyState
            v-else-if="!hasMessages && !store.messagesLoading"
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
                  <span v-if="msg.is_partial" class="chat-message__partial">流式中...</span>
                </div>
                <div class="chat-message__content">
                  <MarkdownViewer
                    v-if="shouldRenderAsMarkdown(msg.role)"
                    :source="msg.content"
                    body-class="chat-md"
                  />
                  <pre v-else class="chat-message__text">{{ msg.content }}</pre>
                </div>
                <div v-if="msg.attached_knowledge_ids && msg.attached_knowledge_ids.length > 0" class="chat-message__attachments">
                  <span class="muted">📎 引用 {{ msg.attached_knowledge_ids.length }} 条知识</span>
                </div>
              </div>
            </div>
          </template>

          <!-- 发送中 placeholder -->
          <div v-if="store.sending" class="chat-message chat-message--assistant chat-message--pending">
            <div class="chat-message__avatar">🧠</div>
            <div class="chat-message__body">
              <div class="chat-message__head">
                <span class="chat-message__role">小气</span>
                <span class="chat-message__time">thinking...</span>
              </div>
              <div class="chat-message__content">
                <div class="chat-message__thinking">
                  <span class="dot-flashing">●●●</span> 思考中...
                </div>
              </div>
            </div>
          </div>
        </div>

        <!-- Input -->
        <form class="chat-input" @submit.prevent="onSend">
          <textarea
            v-model="inputDraft"
            class="chat-input__textarea"
            placeholder="向小气提问 (Shift+Enter 换行, Enter 发送)"
            :disabled="store.sending"
            rows="3"
            @keydown.enter.exact.prevent="onSend"
          />
          <button
            type="submit"
            class="chat-input__send"
            :disabled="store.sending || inputDraft.trim().length === 0"
          >
            <span v-if="store.sending" class="chat-input__spinner" />
            {{ store.sending ? '发送中…' : '发送 ⏎' }}
          </button>
        </form>
      </section>
    </div>
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
.chat-header__hint {
  font-size: 0.75rem;
  color: #64748b;
}

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
.chat-session-item:hover {
  background: rgba(148, 163, 184, 0.06);
}
.chat-session-item.is-active {
  background: rgba(249, 115, 22, 0.12);
  color: #f97316;
  border-color: rgba(249, 115, 22, 0.3);
}
.chat-session-item__title {
  font-size: 0.85rem;
  font-weight: 600;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.chat-session-item__preview {
  font-size: 0.75rem;
  color: #94a3b8;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.chat-session-item__meta {
  margin-top: 0.3rem;
  font-size: 0.7rem;
  color: #64748b;
  display: flex;
  gap: 0.4rem;
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
.chat-message--system,
.chat-message--tool {
  background: rgba(148, 163, 184, 0.06);
  border: 1px solid rgba(148, 163, 184, 0.18);
}
.chat-message--pending {
  opacity: 0.85;
}
.chat-message__avatar {
  font-size: 1.3rem;
  width: 2rem;
  text-align: center;
  flex-shrink: 0;
}
.chat-message__body {
  flex: 1;
  min-width: 0;
}
.chat-message__head {
  display: flex;
  align-items: center;
  gap: 0.6rem;
  margin-bottom: 0.4rem;
  font-size: 0.8rem;
}
.chat-message__role {
  font-weight: 600;
  color: #f1f5f9;
}
.chat-message__time {
  color: #64748b;
  font-size: 0.75rem;
}
.chat-message__partial {
  color: #fbbf24;
  font-size: 0.7rem;
}
.chat-message__content {
  font-size: 0.92rem;
}
.chat-message__text {
  margin: 0;
  white-space: pre-wrap;
  word-break: break-word;
  color: #e2e8f0;
}
.chat-message__attachments {
  margin-top: 0.4rem;
  font-size: 0.75rem;
}
.chat-message__thinking {
  display: flex;
  align-items: center;
  gap: 0.4rem;
  color: #fbbf24;
  font-size: 0.85rem;
}
.dot-flashing {
  display: inline-block;
  animation: dot-flashing 1.4s infinite linear;
  font-weight: bold;
  letter-spacing: 0.2em;
}
@keyframes dot-flashing {
  0% { opacity: 0.2; }
  50% { opacity: 1; }
  100% { opacity: 0.2; }
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
.chat-input__textarea:focus {
  outline: none;
  border-color: #f97316;
}
.chat-input__textarea:disabled {
  opacity: 0.5;
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
.chat-input__send:hover:not(:disabled) {
  background: #ea580c;
}
.chat-input__send:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}
.chat-input__spinner {
  width: 12px;
  height: 12px;
  border: 2px solid #fff;
  border-right-color: transparent;
  border-radius: 50%;
  animation: spin 0.6s linear infinite;
}
@keyframes spin {
  to { transform: rotate(360deg); }
}

:deep(.chat-md) {
  color: #e2e8f0;
}
:deep(.chat-md .md-p) {
  color: #cbd5e1;
}
</style>
