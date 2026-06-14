<template>
  <footer
    class="mobile-input-bar"
    :style="{ paddingBottom: inputPaddingBottom }"
  >
    <!-- 选中预览 -->
    <div v-if="selectedImage || selectedFile" class="attachment-preview">
      <span v-if="selectedImage" class="attachment-tag">
        🖼 {{ selectedImage.name }}
        <button type="button" @click="clearImage" aria-label="移除图片">✕</button>
      </span>
      <span v-if="selectedFile" class="attachment-tag">
        📎 {{ selectedFile.name }}
        <button type="button" @click="clearFile" aria-label="移除文件">✕</button>
      </span>
    </div>

    <div class="input-row">
      <button
        type="button"
        class="action-btn"
        :aria-label="'上传图片'"
        title="图片"
        @click="$emit('image')"
      >🖼️</button>

      <button
        type="button"
        class="action-btn"
        :aria-label="'上传文件'"
        title="文件"
        @click="$emit('file')"
      >📎</button>

      <textarea
        ref="textareaRef"
        :value="modelValue"
        :placeholder="placeholder"
        class="input-textarea"
        rows="1"
        :aria-label="'聊天输入框'"
        :title="'聊天输入框'"
        @input="onInput"
        @keydown="onKeydown"
        @focus="$emit('focus')"
      />

      <button
        v-if="isSending"
        type="button"
        class="stop-btn"
        aria-label="停止生成"
        title="停止生成"
        @click="$emit('stop')"
      >⏹</button>
      <button
        v-else-if="modelValue.trim() || selectedImage || selectedFile"
        type="button"
        class="send-btn"
        aria-label="发送"
        title="发送"
        @click="$emit('send')"
      >↑</button>
      <button
        v-else
        type="button"
        class="voice-btn"
        :aria-label="'按住说话'"
        title="按住说话"
        @touchstart.prevent="onVoiceStart"
        @touchend="onVoiceEnd"
        @touchcancel="onVoiceEnd"
        @mousedown.prevent="onVoiceStart"
        @mouseup="onVoiceEnd"
        @mouseleave="onVoiceEnd"
      >🎤</button>
    </div>

    <!-- 录音提示 -->
    <div v-if="voiceRecording" class="voice-tip">
      <span class="rec-dot" />
      正在录音... 松开发送
    </div>
  </footer>
</template>

<script setup>
/**
 * MobileInputBar.vue — 移动端输入栏（贴底 + 键盘自适应）
 *
 * PR #3:
 * - position: fixed; bottom: 0
 * - padding-bottom 动态跟随键盘高度（useKeyboardInset）
 * - 选中图片/文件预览
 * - 长按麦克风录音（移动端原生交互）
 * - 输入框 textarea 自适应高度
 */

import { ref, watch } from 'vue'

const props = defineProps({
  modelValue: { type: String, default: '' },
  placeholder: { type: String, default: '问问小气…' },
  selectedImage: { type: Object, default: null },
  selectedFile: { type: Object, default: null },
  inputPaddingBottom: { type: String, default: 'var(--sab, 0px)' },
  // 2026-06-14 方案 C Stage 5 收尾：流式中显示 ⏹ 停止按钮
  isSending: { type: Boolean, default: false },
})

const emit = defineEmits([
  'update:modelValue',
  'send',
  'stop',  // 2026-06-14 方案 C Stage 5 收尾
  'image',
  'file',
  'voice-start',
  'voice-end',
  'focus',
  'clear-image',
  'clear-file',
])

const textareaRef = ref(null)
const voiceRecording = ref(false)

function onInput(e) {
  emit('update:modelValue', e.target.value)
  autoResize()
}

function onKeydown(e) {
  // 移动端通常用换行键发送；这里保持桌面行为（Enter 发送，Shift+Enter 换行）
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault()
    emit('send')
  }
}

function autoResize() {
  const el = textareaRef.value
  if (!el) return
  el.style.height = 'auto'
  el.style.height = Math.min(el.scrollHeight, 100) + 'px'
}

function onVoiceStart(e) {
  voiceRecording.value = true
  emit('voice-start', e)
}
function onVoiceEnd(e) {
  if (voiceRecording.value) {
    voiceRecording.value = false
    emit('voice-end', e)
  }
}

function clearImage() {
  emit('clear-image')
}
function clearFile() {
  emit('clear-file')
}

// 外部修改 modelValue 时同步高度
watch(
  () => props.modelValue,
  () => {
    setTimeout(autoResize, 0)
  }
)
</script>

<style scoped>
.mobile-input-bar {
  position: fixed;
  left: 0;
  right: 0;
  bottom: 0;
  z-index: 100;
  background: var(--color-bg-card);
  border-top: 1px solid var(--color-border);
  -webkit-backdrop-filter: blur(12px);
  backdrop-filter: blur(12px);
  /* 底部 padding 由 inputPaddingBottom prop 动态控制（键盘高度 + safe-area） */
  padding-top: 8px;
}

[data-theme="dark"] .mobile-input-bar {
  background: rgba(42, 45, 53, 0.92);
  border-top-color: var(--color-border-base);
}

.attachment-preview {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  padding: 0 var(--mobile-padding-x, 16px) 6px;
}
.attachment-tag {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 4px 8px 4px 10px;
  background: var(--color-primary-bg);
  color: var(--color-primary);
  border-radius: var(--radius-full);
  font-size: 12px;
  max-width: 180px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.attachment-tag button {
  background: transparent;
  border: none;
  color: var(--color-primary);
  cursor: pointer;
  font-size: 14px;
  padding: 0;
  line-height: 1;
}

.input-row {
  display: flex;
  align-items: flex-end;
  gap: 6px;
  padding: 0 var(--mobile-padding-x, 16px) 8px;
}

.action-btn {
  width: 40px;
  height: 40px;
  border-radius: 50%;
  background: transparent;
  border: none;
  font-size: 20px;
  cursor: pointer;
  color: var(--color-text-secondary);
  -webkit-tap-highlight-color: transparent;
  flex-shrink: 0;
}
.action-btn:active {
  background: var(--color-primary-bg);
  color: var(--color-primary);
}

.input-textarea {
  flex: 1;
  min-height: 40px;
  max-height: 100px;
  padding: 10px 12px;
  border: 1px solid var(--color-border);
  border-radius: 20px;
  background: var(--color-bg-page);
  color: var(--color-text-primary);
  font-size: 15px;
  line-height: 1.4;
  resize: none;
  outline: none;
  font-family: inherit;
  /* iOS Safari 不自动缩放（必须 ≥ 16px） */
}

[data-theme="dark"] .input-textarea {
  background: var(--color-bg-page);
  border-color: var(--color-border-base);
}

.input-textarea:focus {
  border-color: var(--color-primary);
}

.send-btn,
.voice-btn {
  width: 40px;
  height: 40px;
  border-radius: 50%;
  background: linear-gradient(135deg, var(--color-primary) 0%, var(--color-primary-light) 100%);
  color: white;
  border: none;
  font-size: 20px;
  cursor: pointer;
  flex-shrink: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  -webkit-tap-highlight-color: transparent;
  font-weight: bold;
}
.send-btn:active,
.voice-btn:active {
  transform: scale(0.95);
}

.voice-tip {
  position: absolute;
  top: -40px;
  left: 50%;
  transform: translateX(-50%);
  background: var(--color-text-primary);
  color: var(--color-bg-card);
  padding: 6px 14px;
  border-radius: var(--radius-full);
  font-size: 12px;
  display: flex;
  align-items: center;
  gap: 6px;
}
.rec-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: var(--color-danger, #F56C6C);
  animation: pulse 1s infinite;
}
@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.3; }
}
</style>