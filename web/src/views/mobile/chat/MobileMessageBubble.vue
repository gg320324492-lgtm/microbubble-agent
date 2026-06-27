<template>
  <div :class="['msg-row', msg.role]">
    <!-- assistant 头像在左 -->
    <div v-if="msg.role === 'assistant'" class="bubble-avatar">
      <span class="avatar-icon">💬</span>
    </div>

    <LongPressWrapper class="bubble-wrapper" @longpress="onLongPress">
      <div class="bubble" :class="`bubble-${msg.role}`">
        <!-- 工具调用 trace -->
        <div v-if="msg.toolTrace && msg.toolTrace.length" class="tool-trace">
          <div
            v-for="(t, i) in msg.toolTrace"
            :key="i"
            class="trace-item"
            :class="t.state"
          >
            <span v-if="t.type === 'thinking'">💭 {{ t.label }}</span>
            <span v-else>
              🔧 {{ t.name }}
              {{ t.state === 'running' ? '...' : '✓' }}
              <span v-if="t.duration_ms" class="duration">{{ t.duration_ms }}ms</span>
            </span>
          </div>
        </div>

        <!-- 文本内容 -->
        <div
          v-if="msg.content"
          class="msg-content"
          v-html="renderMarkdown(msg.content)"
        />

        <!-- 富文本块 -->
        <div v-if="msg.richBlocks && msg.richBlocks.length" class="rich-blocks">
          <MobileRichCard
            v-for="(rb, i) in msg.richBlocks"
            :key="i"
            :block="rb"
          />
        </div>

        <!-- 错误 -->
        <div v-if="msg.error" class="msg-error">⚠️ {{ msg.error }}</div>

        <!-- typing 指示器 -->
        <div
          v-if="msg.state === 'streaming' && !msg.content && !msg.toolTrace?.length"
          class="typing-bubble"
        >
          <span /><span /><span />
        </div>

        <!-- 完成态 meta -->
        <div
          v-if="msg.state === 'idle' && (msg.usage || msg.durationMs)"
          class="msg-meta"
        >
          <span v-if="msg.usage">📊 {{ msg.usage.total_tokens }}</span>
          <span v-if="msg.durationMs">⏱ {{ (msg.durationMs / 1000).toFixed(1) }}s</span>
          <button
            v-if="msg.content"
            type="button"
            class="tts-btn"
            aria-label="播放语音"
            title="播放语音"
            @click.stop="$emit('play-tts', msg.content)"
          >🔊</button>
        </div>
      </div>
    </LongPressWrapper>
  </div>
</template>

<script setup>
/**
 * MobileMessageBubble.vue — 移动端消息气泡
 *
 * PR #3:
 * - 贴边：user 右对齐，assistant 左对齐（带头像）
 * - 长按触发 LongPressWrapper → emit('longpress')
 * - 富文本块通过 MobileRichCard 渲染
 * - typing 动画 3 个点
 * - 完成态显示 token 数 + TTS 按钮
 */

import LongPressWrapper from '@/components/mobile/LongPressWrapper.vue'
import MobileRichCard from './MobileRichCard.vue'
import { renderMarkdown } from '@/utils/markdown'

const props = defineProps({
  msg: { type: Object, required: true },
  isLast: { type: Boolean, default: false },
})

const emit = defineEmits(['longpress', 'play-tts'])

function onLongPress(e) {
  emit('longpress', props.msg, e)
}
</script>

<style scoped>
.msg-row {
  display: flex;
  gap: 6px;
  align-items: flex-end;
}
.msg-row.user {
  justify-content: flex-end;
}
.msg-row.assistant {
  justify-content: flex-start;
}

.bubble-avatar {
  width: 32px;
  height: 32px;
  border-radius: 50%;
  background: linear-gradient(135deg, var(--color-primary) 0%, var(--color-accent) 100%);
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  align-self: flex-end;
}
.avatar-icon {
  font-size: 16px;
}

.bubble-wrapper {
  /* 限制气泡最大宽度 */
  max-width: 78%;
  min-width: 60px;
}

.bubble {
  padding: 10px 14px;
  border-radius: 18px;
  line-height: 1.55;
  font-size: 15px;
  overflow-wrap: break-word;
  overflow-wrap: anywhere;
  -webkit-user-select: text;
  user-select: text;
}

.bubble-user {
  background: linear-gradient(135deg, var(--color-primary) 0%, var(--color-primary-light) 100%);
  /* stylelint-disable-next-line color-named */
  color: white;
  border-bottom-right-radius: 4px;
}
.bubble-assistant {
  background: var(--color-bg-card);
  color: var(--color-text-primary);
  border: 1px solid var(--color-border-light);
  border-bottom-left-radius: 4px;
  box-shadow: var(--shadow-xs);
}

[data-theme="dark"] .bubble-assistant {
  background: var(--color-bg-card);
  border-color: var(--color-border-base);
}

/* Markdown 内容样式 */
.msg-content :deep(p) { margin: 0 0 6px; }
.msg-content :deep(p:last-child) { margin-bottom: 0; }
.msg-content :deep(ul), .msg-content :deep(ol) { padding-left: 20px; margin: 4px 0; }
.msg-content :deep(pre) {
  background: rgba(0, 0, 0, 0.05);
  padding: 8px 10px;
  border-radius: 6px;
  overflow-x: auto;
  font-size: 12px;
  margin: 6px 0;
}
.bubble-user .msg-content :deep(pre) {
  background: rgba(255, 255, 255, 0.15);
}
.msg-content :deep(code) {
  background: rgba(0, 0, 0, 0.05);
  padding: 1px 4px;
  border-radius: 3px;
  font-size: 13px;
}
.bubble-user .msg-content :deep(code) {
  background: rgba(255, 255, 255, 0.15);
}

/* 工具 trace */
.tool-trace {
  margin-bottom: 8px;
  padding: 6px 10px;
  background: rgba(0, 0, 0, 0.03);
  border-radius: 8px;
  border-left: 2px solid var(--color-primary);
  font-size: 12px;
}
[data-theme="dark"] .tool-trace {
  background: rgba(255, 255, 255, 0.04);
}
.trace-item {
  color: var(--color-text-secondary);
  padding: 2px 0;
}
.trace-item.running {
  color: var(--color-primary);
}
.trace-item .duration {
  color: var(--color-text-placeholder);
  font-size: 11px;
  margin-left: 4px;
}

/* 富文本块 */
.rich-blocks {
  margin-top: 8px;
  display: flex;
  flex-direction: column;
  gap: 6px;
}

/* 错误 */
.msg-error {
  color: var(--color-danger);
  font-size: 12px;
  margin-top: 6px;
}

/* typing 动画 */
.typing-bubble {
  display: inline-flex;
  gap: 4px;
  padding: 4px 0;
}
.typing-bubble span {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--color-primary);
  animation: td 1.4s infinite;
}
.typing-bubble span:nth-child(2) { animation-delay: 0.2s; }
.typing-bubble span:nth-child(3) { animation-delay: 0.4s; }
/* 完成态 */
.msg-meta {
  font-size: 11px;
  color: var(--color-text-secondary);
  margin-top: 6px;
  display: flex;
  gap: 10px;
  align-items: center;
}
.tts-btn {
  background: transparent;
  border: none;
  color: var(--color-text-secondary);
  font-size: 14px;
  padding: 2px 6px;
  cursor: pointer;
  border-radius: 4px;
}
.tts-btn:active {
  background: var(--color-primary-bg);
}
</style>