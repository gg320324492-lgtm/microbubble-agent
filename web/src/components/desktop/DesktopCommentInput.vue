<!--
  DesktopCommentInput.vue — W68 路线 F-4 桌面端评论输入栏

  2026-07-24 主指挥协调范式第 45 守恒.

  职责:
  - textarea 自动 focus (mounted) + 字数限制 (max 1000)
  - @mention 自动补全 (复用 useMentionAutocomplete composable, 跟 mobile 同步)
  - 发送按钮 loading 状态 (busy prop)
  - 同步 draft reply 输入 (parent 给初始内容, 比如 @username 前缀)
  - v-model 双向绑定 (父组件拿到当前内容)

  与 mobile MobileCommentInput 区分:
  - 桌面版不带 vibrate / keyboard adjust (iOS Safari 才需要)
  - 桌面版 Enter 直接发送 (Shift+Enter 换行), 与 mobile 一致
  - 桌面版发送按钮在右下角 (mobile 在右侧)
  - 桌面版高度更大 (rows=3, mobile rows=1)

  0 production code 改动铁律:
  - 不动 mobile MobileCommentInput (F-3 完工)
  - 仅 desktop components
-->

<template>
  <div class="desktop-comment-input" :class="{ focused }">
    <div class="dci-compose">
      <el-input
        ref="inputRef"
        v-model="text"
        type="textarea"
        :rows="3"
        autosize
        :placeholder="effectivePlaceholder"
        :maxlength="1000"
        show-word-limit
        resize="none"
        class="dci-textarea"
        @input="onInput"
        @keydown="onKeydown"
        @focus="onFocus"
        @blur="onBlur"
      />
      <!-- @username autocomplete dropdown -->
      <div
        v-if="mention.isOpen.value && mention.rawCandidates.value.length > 0"
        class="dci-mention-dropdown"
        role="listbox"
      >
        <div
          v-for="(m, idx) in mention.rawCandidates.value"
          :key="m.id"
          class="dci-mention-item"
          :class="{ active: idx === mention.selectedIndex.value }"
          role="option"
          :aria-selected="idx === mention.selectedIndex.value"
          @mousedown.prevent="onMentionItemClick(idx)"
          @mouseenter="mention.selectedIndex.value = idx"
        >
          <div class="dci-mention-avatar">{{ (m.name || m.username || '?').slice(0, 1) }}</div>
          <div class="dci-mention-info">
            <div class="dci-mention-name">{{ m.name || m.username }}</div>
            <div class="dci-mention-username">@{{ m.wechat_id || m.username }}</div>
          </div>
        </div>
      </div>
      <div class="dci-actions">
        <span class="dci-hint">Cmd/Ctrl + Enter 发送 · Shift + Enter 换行</span>
        <button
          type="button"
          class="dci-send-btn"
          :disabled="!canSend"
          aria-label="发送评论"
          title="发送评论 (Cmd/Ctrl + Enter)"
          @click="onSend"
        >
          <span v-if="busy" class="dci-send-loading" aria-hidden="true">⏳</span>
          <span v-else>发送</span>
        </button>
      </div>
      <!-- 已 mention 用户预览 — B-3 v3.2 -->
      <div v-if="mentionedPreview.length > 0" class="dci-mentioned-preview" aria-label="将提醒的用户">
        <span class="dci-mentioned-label">将提醒:</span>
        <span
          v-for="m in mentionedPreview"
          :key="m.id"
          class="dci-mentioned-chip"
        >@{{ m.name || m.username }}</span>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, watch } from 'vue'
import { useMentionAutocomplete } from '@/composables/useMentionAutocomplete'

const props = defineProps({
  modelValue: { type: String, default: '' },
  fileId: { type: [String, Number], default: null },
  membersList: { type: Array, default: () => [] },
  placeholder: { type: String, default: '写评论...' },
  busy: { type: Boolean, default: false },
  autoFocus: { type: Boolean, default: true },
})

const emit = defineEmits(['update:modelValue', 'post', 'typing'])

const text = ref(props.modelValue || '')
const inputRef = ref(null)
const focused = ref(false)

const effectivePlaceholder = computed(() => props.placeholder || '写评论... @username 提醒')

const canSend = computed(() => {
  const trimmed = text.value.trim()
  return trimmed.length > 0 && trimmed.length <= 1000 && !props.busy
})

// 已 mention 用户预览 — B-3 v3.2
// 扫描文本中所有 @handle, 匹配 membersList (wechat_id / username / name), 去重
const mentionedPreview = computed(() => {
  const val = text.value || ''
  const handles = new Set()
  const re = /@([一-龥A-Za-z0-9_.\-]{1,32})/g
  let m
  while ((m = re.exec(val)) !== null) {
    handles.add(m[1].toLowerCase())
  }
  if (handles.size === 0) return []
  const seen = new Set()
  const result = []
  for (const member of props.membersList) {
    const keys = [member.wechat_id, member.username, member.name]
      .filter(Boolean)
      .map((k) => String(k).toLowerCase())
    if (keys.some((k) => handles.has(k)) && !seen.has(member.id)) {
      seen.add(member.id)
      result.push(member)
    }
  }
  return result
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
  // Cmd/Ctrl + Enter 直接发送 (桌面端快捷键)
  if (event.key === 'Enter' && (event.metaKey || event.ctrlKey)) {
    event.preventDefault()
    if (canSend.value) onSend()
    return
  }
  // 普通 Enter 直接发送 (不带 shift)
  if (event.key === 'Enter' && !event.shiftKey && !event.isComposing) {
    event.preventDefault()
    if (canSend.value) onSend()
  }
}

function onFocus() {
  focused.value = true
}

function onBlur() {
  focused.value = false
  setTimeout(() => mention.close(), 150)
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
  // desktop autoFocus 默认开启 (mounted 后下一 tick focus)
  if (props.autoFocus) {
    setTimeout(() => {
      const ta = inputRef.value?.$el?.querySelector?.('textarea')
      if (ta) ta.focus()
    }, 100)
  }
})
</script>

<style scoped>
.desktop-comment-input {
  display: block;
  width: 100%;
}

.dci-compose {
  display: flex;
  flex-direction: column;
  gap: 8px;
  position: relative;
}

.dci-textarea {
  width: 100%;
}

.dci-mention-dropdown {
  position: absolute;
  left: 0;
  bottom: 100%;
  margin-bottom: 8px;
  background: var(--color-bg-card, #fff);
  border: 1px solid var(--color-border-light, #ebeef5);
  border-radius: 10px;
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.12);
  max-height: 240px;
  overflow-y: auto;
  z-index: 100;
  min-width: 240px;
}

.dci-mention-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 8px 12px;
  cursor: pointer;
  font-size: 13px;
  transition: background 0.15s;
}

.dci-mention-item.active {
  background: var(--color-primary-bg, rgba(255, 122, 92, 0.08));
}

.dci-mention-avatar {
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

.dci-mention-info {
  flex: 1;
  min-width: 0;
}

.dci-mention-name {
  font-size: 13px;
  font-weight: 500;
  color: var(--color-text-primary, #303133);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.dci-mention-username {
  font-size: 11px;
  color: var(--color-text-secondary, #909399);
  font-family: monospace;
}

.dci-actions {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.dci-hint {
  font-size: 11px;
  color: var(--color-text-placeholder, #c0c4cc);
}

.dci-send-btn {
  flex-shrink: 0;
  height: 32px;
  padding: 0 18px;
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
  min-width: 72px;
  transition: opacity 0.15s, transform 0.1s;
}

.dci-send-btn:disabled {
  background: var(--color-bg-page, #f5f7fa);
  color: var(--color-text-placeholder, #c0c4cc);
  cursor: not-allowed;
}

.dci-send-btn:not(:disabled):hover {
  opacity: 0.92;
}

.dci-send-btn:not(:disabled):active {
  transform: scale(0.97);
}

.dci-send-loading {
  display: inline-block;
  animation: spin 1s linear infinite;
  font-size: 14px;
}

/* 已 mention 用户预览 — B-3 v3.2 */
.dci-mentioned-preview {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 6px;
  margin-top: 2px;
}

.dci-mentioned-label {
  font-size: 11px;
  color: var(--color-text-placeholder, #c0c4cc);
}

.dci-mentioned-chip {
  font-size: 11px;
  padding: 2px 8px;
  background: var(--color-primary-bg, rgba(255, 122, 92, 0.1));
  color: var(--color-primary, #ff7a5c);
  border-radius: 10px;
  font-weight: 500;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}
</style>

<!-- v60-v67 教训: dark mode 跨组件覆盖必须放非 scoped <style> 块 -->
<style>
[data-theme="dark"] .dci-mention-dropdown {
  background: var(--color-bg-card, #2a2d35);
  border-color: var(--color-border-light, #3a3d45);
}

[data-theme="dark"] .dci-mention-item.active {
  background: rgba(255, 122, 92, 0.16);
}

[data-theme="dark"] .dci-send-btn:disabled {
  background: rgba(255, 255, 255, 0.05);
}

[data-theme="dark"] .dci-mentioned-chip {
  background: rgba(255, 122, 92, 0.16);
}
</style>