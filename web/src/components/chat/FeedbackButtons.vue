<!--
  FeedbackButtons.vue — W98 CHAT-P1-D3 用户反馈按钮 (assistant 消息下方)

  功能:
  - 挂每条 assistant 消息下 (ChatViewSSE.vue + MobileMessageBubble.vue)
  - 👍 / 👎 切换态 (点击立即乐观更新, 后端确认后)




  - 选评语 (ElMessageBox.prompt 弹出输入框)
  - 触发时取 msg.server_id (A5 SSE message_id) → POST /chat/feedback
  - 旧消息无 server_id → 按钮隐藏 (优雅降级)

  期望改动:
  - 不暴露内部按钮状态, 仅一个 v-model:user-rating + 评语可选
  - 父组件 props: messageId, sessionId, agentReply (截断 500 字)
-->
<template>
  <div v-if="canRender" class="feedback-buttons" role="group" :aria-label="'消息反馈'">
    <button
      type="button"
      class="fb-btn"
      :class="{ active: localRating === 1 }"
      :aria-label="'回答有帮助'"
      :title="localRating === 1 ? '已点赞 (再点取消)' : '回答有帮助'"
      :aria-pressed="localRating === 1"
      data-hover-prompt="帮助我们回答得更好"
      :disabled="submitting"
      @click.stop="onClick(1)"
    >
      <span class="fb-icon" aria-hidden="true">👍</span>
      <span class="fb-label">回答有帮助</span>
    </button>
    <button
      v-if="localRating === -1"
      type="button"
      class="fb-btn fb-comment-btn"
      aria-label="补充评语"
      title="补充评语"
      :disabled="submitting"
      @click.stop="onAddComment"
    >
      <el-icon><EditPen /></el-icon>
    </button>
    <button
      type="button"
      class="fb-btn"
      :class="{ active: localRating === -1 }"
      :aria-label="'需要改进'"
      :title="localRating === -1 ? '已点踩 (再点取消)' : '需要改进'"
      :aria-pressed="localRating === -1"
      data-hover-prompt="帮助我们回答得更好"
      :disabled="submitting"
      @click.stop="onClick(-1)"
    >
      <span class="fb-icon" aria-hidden="true">👎</span>
      <span class="fb-label">需要改进</span>
    </button>
  </div>
</template>

<script setup>
/**
 * FeedbackButtons.vue — W98 CHAT-P1-D3 用户反馈按钮
 *
 * 后端: POST /api/v1/chat/feedback
 *  payload: { message_id, rating, comment?, session_id?, agent_reply? }
 *  响应:   { ok, feedback_id, rating }
 *
 * Props:
 *  - messageId (Number|String|null) — chat_messages.id (A5 SSE 注入的 server_id)
 *  - sessionId (String|null)        — 上层 session id (可选)
 *  - agentReply (String)            — AI 回复内容 (最多 500 字截断)
 *
 * 状态:
 *  - localRating: 用户当前选择 (-1=👎 / 1=👍 / null=未选)
 *  - submitting: 提交中 (防止重复点击)
 */
import { ref, computed } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { EditPen } from '@element-plus/icons-vue'
import axios from 'axios'

const props = defineProps({
  messageId: {
    type: [Number, String],
    default: null,
  },
  sessionId: {
    type: String,
    default: null,
  },
  agentReply: {
    type: String,
    default: '',
  },
})

const emit = defineEmits(['submitted'])

const localRating = ref(null)
const submitting = ref(false)

// 旧消息无 messageId → 按钮隐藏 (优雅降级)
const canRender = computed(() => {
  if (props.messageId === null || props.messageId === undefined || props.messageId === '') return false
  // 后端 message_id 必须 ge=1
  const n = Number(props.messageId)
  return Number.isFinite(n) && n >= 1
})

async function onClick(rating) {
  if (submitting.value) return
  // 乐观更新: 再点同一档 → 取消
  if (localRating.value === rating) {
    localRating.value = null
    // 取消时暂不调后端 (老反馈语义); 真要取消走 DELETE (留 P2)
    return
  }
  localRating.value = rating
  // 👎 触发评语询问 (非强阻止; 取消则纯 dislike 落库)
  if (rating === -1) {
    try {
      const { value: comment } = await ElMessageBox.prompt(
        '反馈将帮助我们改进回答质量 (可选)', '补充评语 (选填)',
        {
          confirmButtonText: '提交',
          cancelButtonText: '跳过',
          inputPlaceholder: '哪里可以改进？',
          inputType: 'textarea',
          inputValidator: (val) => (val ? val.length <= 1000 : true),
        },
      )
      await submit(rating, comment || null)
    } catch (e) {
      // 用户取消评语 → 仍然提交纯 dislike
      if (e === 'cancel') {
        await submit(rating, null)
        return
      }
      // 其它错误回滚乐观更新
      localRating.value = null
      ElMessage.error('反馈失败，请稍后再试')
    }
  } else {
    await submit(rating, null)
  }
}

async function onAddComment() {
  // 用户已点踩 → 后续补评语入口
  try {
    const { value: comment } = await ElMessageBox.prompt(
      '反馈将帮助我们改进回答质量 (可选)', '补充评语',
      {
        confirmButtonText: '提交',
        cancelButtonText: '取消',
        inputPlaceholder: '哪里可以改进？',
        inputType: 'textarea',
        inputValidator: (val) => !val || val.length <= 1000,
      },
    )
    if (comment) {
      await submit(localRating.value, comment)
    }
  } catch (e) {
    // 用户取消静默忽略
  }
}

async function submit(rating, comment) {
  if (submitting.value) return
  submitting.value = true
  try {
    const { data } = await axios.post('/api/v1/chat/feedback', {
      message_id: Number(props.messageId),
      rating,
      comment: comment || null,
      session_id: props.sessionId || null,
      agent_reply: (props.agentReply || '').slice(0, 500),
    })
    if (!data || !data.ok) {
      throw new Error('feedback not ok')
    }
    ElMessage.success(comment ? '感谢你的反馈和评语！' : '感谢你的反馈！')
    emit('submitted', { feedback_id: data.feedback_id, rating, comment })
  } catch (err) {
    // 401 等错误回滚乐观更新
    localRating.value = null
    const msg = err?.response?.data?.detail || err?.message || '提交失败'
    ElMessage.error(typeof msg === 'string' ? msg : '提交失败，请稍后再试')
    // eslint-disable-next-line no-console
    console.error('[FeedbackButtons] submit failed:', err)
  } finally {
    submitting.value = false
  }
}
</script>

<style scoped>
.feedback-buttons {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  margin-top: 6px;
  font-size: 12px;
}
.fb-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 4px;
  height: 24px;
  padding: 0 8px;
  border: 1px solid transparent;
  border-radius: 8px;
  background: transparent;
  cursor: pointer;
  opacity: 0.7;
  transition: all 0.18s ease;
  font-size: 12px;
  color: var(--color-text-secondary, #6b7280);
}
/* W99 N-6 改进 (4): hover 时弹"帮助我们回答得更好"提示 (CSS ::after tooltip) */
.fb-btn:hover:not(:disabled)::after {
  content: attr(data-hover-prompt);
  position: absolute;
  bottom: calc(100% + 4px);
  left: 50%;
  transform: translateX(-50%);
  padding: 3px 8px;
  background: var(--color-text-primary, #1f2937);
  color: var(--color-bg-card, #fff);
  font-size: 11px;
  border-radius: 6px;
  white-space: nowrap;
  pointer-events: none;
  opacity: 0.95;
  z-index: 10;
  box-shadow: 0 2px 6px rgba(0, 0, 0, 0.18);
}
.fb-btn {
  position: relative;
}
.fb-btn:hover:not(:disabled) {
  opacity: 1;
  background: rgba(0, 0, 0, 0.04);
}
.fb-btn.active {
  opacity: 1;
  border-color: var(--color-primary, #FF7A5C);
  background: rgba(255, 122, 92, 0.08);
  color: var(--color-primary, #FF7A5C);
}
.fb-label {
  font-size: 12px;
  line-height: 1;
}
.fb-comment-btn {
  width: 24px;
  padding: 0;
  font-size: 11px;
  color: var(--color-primary, #FF7A5C);
}
.fb-btn:disabled {
  cursor: not-allowed;
  opacity: 0.4;
}
.fb-icon {
  font-size: 14px;
  line-height: 1;
}
</style>
