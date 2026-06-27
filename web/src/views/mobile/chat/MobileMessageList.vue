<template>
  <div ref="messagesRef" class="mobile-message-list" @scroll.passive="onScroll">
    <TransitionGroup name="msg" tag="div" class="msg-group">
      <template v-for="(msg, idx) in messages" :key="msg.id || idx">
        <!-- 时间分隔（移动端 1 分钟阈值，更密集） -->
        <div
          v-if="shouldShowTimeDivider(idx)"
          class="time-divider"
        >
          {{ formatTime(msg.timestamp) }}
        </div>

        <MobileMessageBubble
          :msg="msg"
          :is-last="idx === messages.length - 1"
          @longpress="(e) => $emit('longpress', msg, e)"
          @play-tts="(text) => $emit('play-tts', text)"
        />
      </template>
    </TransitionGroup>

    <!-- 欢迎页（仅 1 条助手欢迎消息时显示） -->
    <div v-if="showWelcome" class="welcome-hero">
      <div class="hero-avatar">
        <span class="hero-icon">💬</span>
      </div>
      <h2>你好，我是小气</h2>
      <p>课题组智能助手，可查任务、会议、知识、公式</p>
      <div class="quick-actions">
        <button
          v-for="qa in quickActions"
          :key="qa.label"
          type="button"
          class="quick-btn"
          @click="$emit('quick-action', qa.text)"
        >
          <span class="qa-icon">{{ qa.icon }}</span>
          <span>{{ qa.label }}</span>
        </button>
      </div>
    </div>
  </div>
</template>

<script setup>
/**
 * MobileMessageList.vue — 移动端消息列表
 *
 * PR #3:
 * - 消息滚动到底部（仅在用户已经在底部时跟随新消息）
 * - 长按气泡触发 ActionSheet（在 MobileChatView 监听）
 * - 时间分隔：移动端 1 分钟阈值（桌面 5 分钟）
 * - 欢迎页（仅 1 条助手消息时）
 */

import { ref, computed, nextTick } from 'vue'
import MobileMessageBubble from './MobileMessageBubble.vue'

const props = defineProps({
  messages: { type: Array, default: () => [] },
  /** 是否自动滚动到底部（用户已在底部时） */
  autoScroll: { type: Boolean, default: true },
})

const emit = defineEmits(['longpress', 'play-tts', 'quick-action'])

const messagesRef = ref(null)
const lastScrollTop = ref(0)
const isAtBottom = ref(true)

const quickActions = [
  { icon: '📋', label: '我的任务', text: '我最近有什么任务？' },
  { icon: '📅', label: '最近会议', text: '上周开了什么会？有什么结论？' },
  { icon: '📊', label: '项目进度', text: '项目进度如何？' },
  { icon: '📚', label: '知识问答', text: 'zeta 电位是什么？' },
]

const showWelcome = computed(
  () => props.messages.length === 1 && props.messages[0]?.role === 'assistant'
)

function shouldShowTimeDivider(idx) {
  if (idx === 0) return false
  const prev = props.messages[idx - 1]
  const cur = props.messages[idx]
  if (!prev?.timestamp || !cur?.timestamp) return false
  // 移动端 1 分钟阈值
  return new Date(cur.timestamp) - new Date(prev.timestamp) > 1 * 60 * 1000
}

function formatTime(t) {
  if (!t) return ''
  return new Date(t).toLocaleTimeString('zh-CN', {
    hour: '2-digit',
    minute: '2-digit',
  })
}

function onScroll(e) {
  const el = e.target
  const distanceFromBottom = el.scrollHeight - el.scrollTop - el.clientHeight
  isAtBottom.value = distanceFromBottom < 80
  lastScrollTop.value = el.scrollTop
}

/** 滚动到底部（外部调用） */
async function scrollToBottom(force = false) {
  await nextTick()
  if (!messagesRef.value) return
  if (!force && !isAtBottom.value) return // 用户不在底部，不自动滚
  messagesRef.value.scrollTo({
    top: messagesRef.value.scrollHeight,
    behavior: force ? 'auto' : 'smooth',
  })
}

defineExpose({ scrollToBottom })
</script>

<style scoped>
.mobile-message-list {
  flex: 1;
  overflow-y: auto;
  padding: var(--mobile-padding-y, 12px) var(--mobile-padding-x, 16px);
  /* 底部 padding 由父组件根据键盘高度动态设置 */
  -webkit-overflow-scrolling: touch;
}

.msg-group {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.time-divider {
  text-align: center;
  font-size: 11px;
  color: var(--color-text-secondary);
  margin: 8px 0;
  position: relative;
}
.time-divider::before,
.time-divider::after {
  content: '';
  position: absolute;
  top: 50%;
  width: 30%;
  height: 1px;
  background: var(--color-border-light);
}
.time-divider::before { left: 5%; }
.time-divider::after { right: 5%; }

/* 消息入场动画 */
.msg-enter-active {
  transition: opacity 250ms ease, transform 250ms ease;
}
.msg-enter-from {
  opacity: 0;
  transform: translateY(8px);
}

/* 欢迎页 */
.welcome-hero {
  text-align: center;
  padding: 40px 20px;
}
.hero-avatar {
  width: 80px;
  height: 80px;
  margin: 0 auto 16px;
  background: linear-gradient(135deg, var(--color-primary) 0%, var(--color-accent) 100%);
  border-radius: var(--radius-full);
  display: flex;
  align-items: center;
  justify-content: center;
  box-shadow: var(--shadow-primary);
}
.hero-icon {
  font-size: 36px;
}
.welcome-hero h2 {
  font-size: 20px;
  font-weight: var(--font-weight-semibold, 600);
  margin: 0 0 6px;
  color: var(--color-text-primary);
}
.welcome-hero p {
  color: var(--color-text-secondary);
  font-size: 13px;
  margin: 0 0 24px;
}
.quick-actions {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 8px;
}
.quick-btn {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 12px 14px;
  background: var(--color-bg-card);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  cursor: pointer;
  font-size: 13px;
  color: var(--color-text-primary);
  -webkit-tap-highlight-color: transparent;
  transition: all 150ms;
}
.quick-btn:active {
  border-color: var(--color-primary);
  background: var(--color-primary-bg);
}
.qa-icon {
  font-size: 18px;
}
</style>

<!-- v77 P2.6-B: dark mode 适配（v60-v67 教训：必须非 scoped） -->
<style>
/* 消息列表 + 时间分割 + 引用块在 dark 模式适配 */
[data-theme="dark"] .message-time-divider {
  color: var(--color-text-placeholder);
  background: var(--color-bg-page);
}
[data-theme="dark"] .message-quote {
  background: var(--color-bg-page);
  border-left: 3px solid var(--color-primary);
  color: var(--color-text-secondary);
}
[data-theme="dark"] .qa-card {
  background: var(--color-bg-card);
  border: 1px solid var(--color-border-light);
  color: var(--color-text-primary);
}
[data-theme="dark"] .qa-card.active {
  border-color: var(--color-primary);
  background: var(--color-primary-bg);
}
</style>