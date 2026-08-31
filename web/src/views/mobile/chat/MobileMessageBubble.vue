<template>
  <div :class="['msg-row', msg.role]">
    <!-- assistant 头像在左 -->
    <div v-if="msg.role === 'assistant'" class="bubble-avatar">
      <span class="avatar-icon">💬</span>
    </div>

    <LongPressWrapper class="bubble-wrapper" @longpress="onLongPress">
      <div class="bubble" :class="`bubble-${msg.role}`">
        <!-- ===== W99 +15 移动端接入：ThinkingCapsule 取代 RetrievalStatus + 3-dot typing-bubble ===== -->
        <ThinkingCapsule
          v-if="msg.role === 'assistant' && msg.phase"
          :phase="msg.phase"
          :started-at="msg.phaseStartedAt"
          :found-count="msg.foundCount"
          :retry-count="msg.retryCount"
          compact
        />
        <!-- ===== W100 +22 plan_step 折叠展开：compact 模式 / W100 +49c RICHTEXT-UNFOLD ===== -->
        <PlanSteps
          v-if="msg.plan && msg.plan.length"
          :steps="msg.plan"
          :collapsed-by-default="!!msg.collapsedByDefault"
          compact
        />
        <!-- 工具调用 trace — W100 +21 接入 ToolTraceItem（可点展开） -->
        <div v-if="msg.toolTrace && msg.toolTrace.length" class="tool-trace">
          <ToolTraceItem
            v-for="(t, i) in msg.toolTrace"
            :key="i"
            :trace="t"
            :index="i"
            compact
            :data-testid="`mobile-tti-${i}`"
            @jump="$emit('jump', $event)"
          />
        </div>

        <!-- 文本内容 — W100 +25 双段折叠 / W100 +49a RICHTEXT-UNFOLD -->
        <ContentBriefDetail
          v-if="msg.role === 'assistant' && msg.content"
          :content="msg.content"
          :collapsed-by-default="!!msg.collapsedByDefault"
          compact
          class="msg-content"
          :data-testid="`mobile-cbd-${msg.id}`"
        />
        <!-- W100 +26: SSE 事件徽章 (compact 模式 — 移动端字号更小) -->
        <EventBadges
          v-if="msg.role === 'assistant'"
          :msg="msg"
          compact
          :data-testid="`mobile-eb-${msg.id}`"
        />
        <div
          v-else-if="msg.content"
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

        <!-- [CHAT-P1-E E2] 移动端追问 chips (复用桌面组件, 走 ResponsiveProps.sessionId) -->
        <FollowUpChips
          v-if="msg.role === 'assistant' && msg.state === 'idle'"
          :session-id="sessionId"
          :on-click="onFollowUpClick"
        />

        <!-- 错误 -->
        <div v-if="msg.error" class="msg-error">⚠️ {{ msg.error }}</div>

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
          >
            <el-icon><Headset /></el-icon>
          </button>
          <!-- W100 +23: 重生成 + 复制按钮 (移动端始终显示) -->
          <ChatMessageActions
            v-if="msg.role === 'assistant' && msg.content"
            mode="mobile"
            :message-id="msg.id"
            @regenerate.stop="$emit('regenerate', msg)"
            @copy.stop="$emit('copy', msg)"
          />
          <!-- W100 +24: 知识图谱 / 公式 / 假设入口 (移动端 compact 模式) -->
          <ProEntries
            v-if="msg.role === 'assistant' && msg.content"
            mode="mobile"
            :intent="msg.intent || null"
            :content="msg.content"
            :tool-trace="msg.toolTrace || []"
            @entry-click.stop="$emit('pro-entry', msg, $event)"
          />
          <!-- W98 CHAT-P1-D3: 移动端反馈按钮 -->
          <FeedbackButtons
            v-if="msg.role === 'assistant' && msg.content"
            :message-id="msg.server_id"
            :session-id="msg.sessionId || null"
            :agent-reply="msg.content"
          />
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
 *
 * [CHAT-P1-E] E1/E2/E5 mobile 端:
 * - E1: KnowledgeRefBlock 内部已带 long-press ElMessageBox 弹窗, 移动端自动启用
 * - E2: FollowUpChips 复用桌面组件
 * - E5: RetrievalStatus 复用桌面组件 (compact 模式)
 */

import LongPressWrapper from '@/components/mobile/LongPressWrapper.vue'
import MobileRichCard from './MobileRichCard.vue'
import FeedbackButtons from '@/components/chat/FeedbackButtons.vue'  // W98 CHAT-P1-D3
import ChatMessageActions from '@/components/chat/ChatMessageActions.vue'  // W100 +23 重生成 + 复制按钮
import ProEntries from '@/components/chat/ProEntries.vue'  // W100 +24 知识图谱/公式/假设入口
import FollowUpChips from '@/components/chat/FollowUpChips.vue'
// ===== W99 +15 移动端接入：ThinkingCapsule 取代 RetrievalStatus 挂载 =====
// RetrievalStatus 摘挂载保留文件 + 保留事件 dispatch（基线兼容）
import ThinkingCapsule from '@/components/chat/ThinkingCapsule.vue'
import ToolTraceItem from '@/components/chat/ToolTraceItem.vue'  // W100 +21 工具调用结果可点展开
import PlanSteps from '@/components/chat/PlanSteps.vue'  // W100 +22 plan_step 折叠展开 (compact 模式)
import ContentBriefDetail from '@/components/chat/ContentBriefDetail.vue'  // W100 +25 双段折叠 (compact)
import EventBadges from '@/components/chat/EventBadges.vue'  // W100 +26 SSE 事件徽章 (compact 模式)
import { Headset } from '@element-plus/icons-vue'  // W100 +51a TTS 按钮现代化
import { renderMarkdown } from '@/utils/markdown'

const props = defineProps({
  msg: { type: Object, required: true },
  isLast: { type: Boolean, default: false },
  // [CHAT-P1-E] sessionId + onFollowUpClick 透传 (从父 MobileChatView 传)
  sessionId: { type: String, default: '' },
})

const emit = defineEmits(['longpress', 'play-tts', 'followup', 'regenerate', 'copy', 'pro-entry', 'jump'])

function onLongPress(e) {
  emit('longpress', props.msg, e)
}

// [CHAT-P1-E E2] 追问点击 → emit 给父组件 (父组件触发 sendSSE)
function onFollowUpClick(suggestion) {
  emit('followup', suggestion)
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
  background: var(--mg-gradient);
  border: 1.5px solid var(--mg-glass-border);
  box-shadow: var(--mg-shadow-sm);
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
  background: var(--mg-gradient-btn);
  /* stylelint-disable-next-line color-named */
  color: var(--mg-on-primary);
  border-radius: 18px 18px 6px 18px;
  box-shadow: var(--mg-primary-shadow);
}
.bubble-assistant {
  background: var(--mg-glass-bg);
  color: var(--mg-text);
  border: 1.5px solid var(--mg-glass-border);
  -webkit-backdrop-filter: blur(var(--mg-glass-blur));
  backdrop-filter: blur(var(--mg-glass-blur));
  border-radius: 18px 18px 18px 6px;
  box-shadow: var(--mg-shadow-sm);
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
  border-left: 2px solid var(--mg-primary);
  font-size: 12px;
}
[data-theme="dark"] .tool-trace {
  background: rgba(255, 255, 255, 0.04);
}
.trace-item {
  color: var(--mg-text-soft);
  padding: 2px 0;
}
.trace-item.running {
  color: var(--mg-primary);
}
.trace-item .duration {
  color: var(--mg-text-faint);
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
  color: var(--mg-danger);
  font-size: 12px;
  margin-top: 6px;
}

/* ===== W99 +15 typing-bubble CSS 删除（已被 ThinkingCapsule 取代） ===== */

/* 完成态 meta 行: token/时长/TTS/操作组/反馈组全部子项。
   窄屏下允许整行换行, 但每个按钮/文字内部禁换行 (修复真机 CJK 竖排挤压) */
.msg-meta {
  font-size: 11px;
  color: var(--mg-text-soft);
  margin-top: 6px;
  display: flex;
  flex-wrap: wrap;
  gap: 6px 10px;
  align-items: center;
}
.msg-meta > * {
  white-space: nowrap;
  flex-shrink: 0;
}
.tts-btn {
  background: transparent;
  border: none;
  color: var(--mg-text-soft);
  font-size: 14px;
  padding: 2px 6px;
  cursor: pointer;
  border-radius: 4px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
}
.tts-btn:active {
  background: var(--mg-gradient-soft);
  color: var(--mg-primary);
}
.tts-btn :deep(.el-icon) {
  font-size: 18px;
}
</style>
