<template>
  <footer
    class="mobile-input-bar glass glass-lg mg-glass-strong"
    :style="{ paddingBottom: inputPaddingBottom }"
  >
    <!-- 选中预览 -->
    <div v-if="selectedImage || selectedFile" class="attachment-preview">
      <span v-if="selectedImage" class="attachment-tag">
        <el-icon :size="14" class="attachment-icon"><Picture /></el-icon>
        {{ selectedImage.name }}
        <button type="button" @click="clearImage" aria-label="移除图片">✕</button>
      </span>
      <span v-if="selectedFile" class="attachment-tag">
        <el-icon :size="14" class="attachment-icon"><Paperclip /></el-icon>
        {{ selectedFile.name }}
        <button type="button" @click="clearFile" aria-label="移除文件">✕</button>
      </span>
    </div>

    <div class="input-row">
      <button
        id="mobile-input-image"
        name="mobile-input-image"
        type="button"
        class="action-btn"
        aria-label="上传图片"
        title="图片"
        @click="$emit('image')"
      >
        <el-icon :size="20"><Picture /></el-icon>
      </button>

      <button
        id="mobile-input-file"
        name="mobile-input-file"
        type="button"
        class="action-btn"
        aria-label="上传文件"
        title="文件"
        @click="$emit('file')"
      >
        <el-icon :size="20"><Paperclip /></el-icon>
      </button>

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
        id="mobile-input-stop"
        name="mobile-input-stop"
        type="button"
        class="stop-btn"
        aria-label="停止生成"
        title="停止生成"
        @click="$emit('stop')"
      >
        <el-icon :size="20"><VideoPause /></el-icon>
      </button>
      <button
        v-else-if="modelValue.trim() || selectedImage || selectedFile"
        id="mobile-input-send"
        name="mobile-input-send"
        type="button"
        class="send-btn"
        aria-label="发送"
        title="发送"
        @click="$emit('send')"
      >
        <el-icon :size="20"><Promotion /></el-icon>
      </button>
      <MobileVoiceInputButton
        v-else
        :text="modelValue"
        :disabled="isSending"
        :auto-send="false"
        @update:text="$emit('update:modelValue', $event)"
        @transcribed="onTranscribed"
        @recording="onVoiceRecordingState"
        @send="onVoiceAutoSend"
      />
    </div>

    <!-- 录音提示 (W68 路线 G-1: 现在由 MobileVoiceInputButton 浮层显示, 此处保留 fallback) -->
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
import { Picture, Paperclip, Promotion, VideoPause } from '@element-plus/icons-vue'
import MobileVoiceInputButton from '@/components/mobile/MobileVoiceInputButton.vue'

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
  // 2026-07-24 W68 路线 G-1: 语音输入迁移到 MobileVoiceInputButton, 仍保留事件向上抛
  'voice-start',
  'voice-end',
  'voice-transcribed',  // (text: string) ASR 完成后
  'voice-auto-send',   // (text: string) autoSend=true 时
  'voice-state',       // ('start' | 'cancel' | 'error')
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
  // 2026-07-24 W68 G-1: 新路径通过 MobileVoiceInputButton 内部 start(), 这里只保留老路径兼容
  emit('voice-state', 'start')
}
function onVoiceEnd(e) {
  if (voiceRecording.value) {
    voiceRecording.value = false
    emit('voice-end', e)
  }
}

function onTranscribed(text) {
  // ASR 完成后透传 (父组件已通过 v-model:text 收到 update:text, 这里只用于钩子)
  emit('voice-transcribed', text)
}

function onVoiceAutoSend(text) {
  emit('voice-auto-send', text)
}

function onVoiceRecordingState(state) {
  emit('voice-state', state)
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
  /* 悬浮玻璃胶囊: 左右让位与 TabBar 胶囊对齐, bottom 避开 TabBar */
  left: var(--mg-tabbar-float, 14px);
  right: var(--mg-tabbar-float, 14px);
  bottom: var(--tabbar-height, 76px);
  z-index: 1100; /* 高于 TabBar 内容（TabBar 容器 z=2500，input bar 视觉在上层） */
  background: var(--mg-glass-bg-strong);
  border: 1.5px solid var(--mg-glass-border);
  border-radius: var(--mg-radius-pill);
  -webkit-backdrop-filter: blur(24px);
  backdrop-filter: blur(24px);
  box-shadow: var(--mg-shadow-lg);
  /* 底部 padding 由 inputPaddingBottom prop 动态控制（键盘高度 + safe-area） */
  padding-top: 6px;
}

.attachment-preview {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  padding: 0 10px 6px;
}
.attachment-tag {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 4px 8px 4px 10px;
  background: var(--mg-glass-bg-strong);
  color: var(--mg-primary);
  border: 1px solid var(--mg-glass-border);
  border-radius: var(--mg-radius-pill);
  font-size: 12px;
  max-width: 180px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.attachment-tag button {
  background: transparent;
  border: none;
  color: var(--mg-primary);
  cursor: pointer;
  font-size: 14px;
  padding: 0;
  line-height: 1;
}

.input-row {
  display: flex;
  align-items: flex-end;
  gap: 6px;
  padding: 0 8px 6px;
}

.action-btn {
  width: 40px;
  height: 40px;
  border-radius: 50%;
  background: transparent;
  border: none;
  font-size: 20px;
  cursor: pointer;
  color: var(--mg-text-soft);
  -webkit-tap-highlight-color: transparent;
  flex-shrink: 0;
  transition: transform 150ms ease;
}
.action-btn:active {
  background: var(--mg-gradient-soft);
  color: var(--mg-primary);
  transform: scale(0.97);
}

.input-textarea {
  flex: 1;
  min-height: 40px;
  max-height: 100px;
  padding: 10px 12px;
  border: 1px solid var(--mg-glass-border);
  border-radius: var(--mg-radius-pill);
  background: var(--mg-glass-bg);
  color: var(--mg-text);
  font-size: 15px;
  line-height: 1.4;
  resize: none;
  outline: none;
  font-family: inherit;
  /* iOS Safari 不自动缩放（必须 ≥ 16px） */
}

.input-textarea::placeholder {
  color: var(--mg-text-faint);
}

.input-textarea:focus {
  border-color: var(--mg-primary);
  box-shadow: 0 0 0 3px var(--mg-glass-bg-strong);
}

.send-btn,
.stop-btn,
.voice-btn {
  width: 40px;
  height: 40px;
  border-radius: 50%;
  background: var(--mg-gradient-btn);
  /* stylelint-disable-next-line color-named */
  color: var(--mg-on-primary);
  border: none;
  font-size: 20px;
  cursor: pointer;
  flex-shrink: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  -webkit-tap-highlight-color: transparent;
  font-weight: bold;
  box-shadow: var(--mg-primary-shadow);
  transition: transform 150ms ease;
}
.send-btn:active,
.stop-btn:active,
.voice-btn:active {
  transform: scale(0.95);
}

.voice-tip {
  position: absolute;
  top: -40px;
  left: 50%;
  transform: translateX(-50%);
  background: var(--mg-glass-bg-strong);
  border: 1px solid var(--mg-glass-border);
  -webkit-backdrop-filter: blur(12px);
  backdrop-filter: blur(12px);
  color: var(--mg-text);
  padding: 6px 14px;
  border-radius: var(--mg-radius-pill);
  font-size: 12px;
  display: flex;
  align-items: center;
  gap: 6px;
}
.rec-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: var(--mg-danger);
  animation: pulse 1s infinite;
}
</style>