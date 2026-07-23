<!--
  MobileCommentInput.vue — W68 路线 F-3 移动端评论输入栏 (独立组件)

  2026-07-24 主指挥协调范式第 38 守恒.

  职责:
  - textarea 自动 focus (mounted)
  - @mention 自动补全 (复用 useMentionAutocomplete, 与 MobileCommentThread 共享)
  - 发送按钮 loading 状态 (busy prop)
  - keyboard adjust (调用 useMobileKeyboard 让 iOS Safari 键盘上推内容)
  - v-model 双向绑定 (父组件拿到当前内容, 用于草稿恢复)

  设计:
  - 0 production code 改动铁律 — 复用 desktop comment store
  - 与 MobileCommentThread 风格统一 (textarea 紧凑 + 发送按钮右)
  - 长按输入框 600ms 不触发 (避免误触 LongPressWrapper)
-->
<template>
  <div class="mobile-comment-input" :class="{ focused }">
    <div class="mci-compose">
      <el-input
        ref="inputRef"
        v-model="text"
        type="textarea"
        :rows="1"
        autosize
        :placeholder="effectivePlaceholder"
        :maxlength="1000"
        show-word-limit
        class="mci-textarea"
        @input="onInput"
        @keydown="onKeydown"
        @focus="onFocus"
        @blur="onBlur"
      />
      <!-- @username autocomplete dropdown -->
      <div
        v-if="mention.isOpen.value && mention.rawCandidates.value.length > 0"
        class="mci-mention-dropdown"
        role="listbox"
      >
        <div
          v-for="(m, idx) in mention.rawCandidates.value"
          :key="m.id"
          class="mci-mention-item"
          :class="{ active: idx === mention.selectedIndex.value }"
          role="option"
          :aria-selected="idx === mention.selectedIndex.value"
          @mousedown.prevent="onMentionItemClick(idx)"
          @mouseenter="mention.selectedIndex.value = idx"
        >
          <div class="mci-mention-avatar">{{ (m.name || m.username || '?').slice(0, 1) }}</div>
          <div class="mci-mention-info">
            <div class="mci-mention-name">{{ m.name || m.username }}</div>
            <div class="mci-mention-username">@{{ m.wechat_id || m.username }}</div>
          </div>
        </div>
      </div>
      <button
        type="button"
        class="mci-send-btn"
        :disabled="!canSend"
        aria-label="发送评论"
        title="发送评论"
        @click="onSend"
      >
        <span v-if="busy" class="mci-send-loading" aria-hidden="true">⏳</span>
        <span v-else>发送</span>
      </button>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onBeforeUnmount, watch } from 'vue'
import { useMentionAutocomplete } from '@/composables/useMentionAutocomplete'
import { useMobileKeyboard } from '@/composables/useMobileKeyboard'

const props = defineProps({
  modelValue: { type: String, default: '' },
  fileId: { type: [String, Number], required: true },
  membersList: { type: Array, default: () => [] },
  placeholder: { type: String, default: '写评论...' },
  busy: { type: Boolean, default: false },
})

const emit = defineEmits(['update:modelValue', 'post', 'typing'])

const text = ref(props.modelValue || '')
const inputRef = ref(null)
const focused = ref(false)
const keyboard = useMobileKeyboard()

const effectivePlaceholder = computed(() => props.placeholder || '写评论... @username 提醒')

const canSend = computed(() => {
  const trimmed = text.value.trim()
  return trimmed.length > 0 && trimmed.length <= 1000 && !props.busy
})

const mention = useMentionAutocomplete({
  textareaRef: inputRef,
  members: props.membersList,
  onSelect: (member, ctx) => {
    if (!ctx || ctx.triggerPos < 0) return
    const before = text.value.substring(0, ctx.triggerPos)
    const after = text.value.substring(ctx.triggerPos + 1 + ctx.query.length)
    const mentionText = `@${member.wechat_id || member.username} `
    text.value = before + mentionText + after
    setTimeout(() => {
      const ta = inputRef.value?.$el?.querySelector?.('textarea')
      if (ta) {
        const newPos = before.length + mentionText.length
        ta.focus()
        ta.setSelectionRange(newPos, newPos)
      }
    }, 0)
  },
})

watch(text, (val) => {
  emit('update:modelValue', val)
})

watch(() => props.modelValue, (val) => {
  if (val !== text.value) text.value = val || ''
})

function onInput() {
  mention.refresh()
  emit('typing', text.value)
}

function onKeydown(event) {
  if (mention.handleKeydown(event)) return
  if (event.key === 'Enter' && !event.shiftKey && !event.isComposing) {
    event.preventDefault()
    if (canSend.value) onSend()
  }
}

function onFocus() {
  focused.value = true
  keyboard.show()
}

function onBlur() {
  focused.value = false
  setTimeout(() => mention.close(), 150)
  keyboard.hide()
}

function onMentionItemClick(index) {
  mention.selectCandidate(index)
}

function onSend() {
  if (!canSend.value) return
  emit('post', text.value)
}

onMounted(() => {
  if (props.modelValue) text.value = props.modelValue
})

onBeforeUnmount(() => {
  keyboard.hide()
})
</script>

<style scoped>
.mobile-comment-input {
  display: block;
  width: 100%;
}

.mci-compose {
  display: flex;
  gap: 8px;
  align-items: flex-end;
  position: relative;
}

.mci-textarea {
  flex: 1;
  min-width: 0;
}

.mci-mention-dropdown {
  position: absolute;
  left: 0;
  right: 0;
  bottom: 100%;
  margin-bottom: 6px;
  background: var(--color-bg-card, #fff);
  border: 1px solid var(--color-border-light, #ebeef5);
  border-radius: 10px;
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.1);
  max-height: 220px;
  overflow-y: auto;
  z-index: 1000;
}

.mci-mention-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 8px 12px;
  cursor: pointer;
  font-size: 13px;
  transition: background 0.15s;
}

.mci-mention-item.active {
  background: var(--color-primary-bg, rgba(255, 122, 92, 0.08));
}

.mci-mention-avatar {
  width: 28px;
  height: 28px;
  border-radius: 50%;
  background: var(--color-primary, #ff7a5c);
  color: #fff;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 12px;
  font-weight: 600;
  flex-shrink: 0;
}

.mci-mention-info {
  flex: 1;
  min-width: 0;
}

.mci-mention-name {
  font-size: 13px;
  font-weight: 500;
  color: var(--color-text-primary, #303133);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.mci-mention-username {
  font-size: 11px;
  color: var(--color-text-secondary, #909399);
  font-family: monospace;
}

.mci-send-btn {
  flex-shrink: 0;
  height: 36px;
  padding: 0 14px;
  background: var(--color-primary, #ff7a5c);
  color: #fff;
  border: none;
  border-radius: 8px;
  font-size: 13px;
  font-weight: 500;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  min-width: 56px;
  transition: opacity 0.15s, transform 0.1s;
}

.mci-send-btn:disabled {
  background: var(--color-bg-page, #f5f7fa);
  color: var(--color-text-placeholder, #c0c4cc);
  cursor: not-allowed;
}

.mci-send-btn:not(:disabled):active {
  transform: scale(0.97);
}

.mci-send-loading {
  display: inline-block;
  animation: spin 1s linear infinite;
  font-size: 14px;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}
</style>

<!-- v60-v67 教训: dark mode 跨组件覆盖必须放非 scoped <style> 块 -->
<style>
[data-theme="dark"] .mci-mention-dropdown {
  background: var(--color-bg-card, #2a2d35);
  border-color: var(--color-border-light, #3a3d45);
}

[data-theme="dark"] .mci-mention-item.active {
  background: rgba(255, 122, 92, 0.16);
}
</style>