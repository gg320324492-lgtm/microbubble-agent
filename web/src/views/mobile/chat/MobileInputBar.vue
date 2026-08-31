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

    <!-- 思考模式选择 (2026-08-31 自设置页迁入对话界面) -->
    <div class="mode-strip">
      <button
        type="button"
        class="mode-chip"
        :aria-expanded="showModePicker ? 'true' : 'false'"
        aria-label="切换思考模式"
        title="思考模式"
        @click="showModePicker = !showModePicker"
      >
        <span class="mode-chip-icon">{{ currentMode.icon }}</span>
        <span class="mode-chip-name">{{ currentMode.name }}</span>
        <span class="mode-chip-caret" aria-hidden="true">▾</span>
      </button>
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

    <!-- 思考模式选择面板 (Teleport 到 body 防止被 footer 圆角裁剪) -->
    <Teleport to="body">
      <Transition name="mode-pop">
        <div
          v-if="showModePicker"
          class="mode-picker-backdrop"
          @click.self="showModePicker = false"
        >
          <div class="mode-picker" role="radiogroup" aria-label="思考模式">
            <div class="mode-picker-title">🧠 思考模式</div>
            <button
              v-for="m in thinkingModes"
              :key="m.value"
              type="button"
              class="mode-option"
              role="radio"
              :aria-checked="uiStore.thinkingMode === m.value ? 'true' : 'false'"
              :class="{ active: uiStore.thinkingMode === m.value }"
              @click="pickMode(m.value)"
            >
              <span class="mode-icon">{{ m.icon }}</span>
              <span class="mode-text">
                <span class="mode-name">{{ m.name }}</span>
                <span class="mode-desc">{{ m.desc }}</span>
              </span>
              <span class="mode-check" aria-hidden="true">{{ uiStore.thinkingMode === m.value ? '✓' : '' }}</span>
            </button>
          </div>
        </div>
      </Transition>
    </Teleport>
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

import { ref, computed, watch } from 'vue'
import { Picture, Paperclip, Promotion, VideoPause } from '@element-plus/icons-vue'
import MobileVoiceInputButton from '@/components/mobile/MobileVoiceInputButton.vue'
import { useUiStore } from '@/stores/useUiStore'

// 2026-08-31: 思考模式三档选择自设置页迁入 (原 van-radio 模板因项目无 Vant 从未渲染成功)
const uiStore = useUiStore()
const showModePicker = ref(false)
const thinkingModes = [
  { value: 'fast', icon: '⚡', name: '快速', desc: 'Qwen3-8B · 跳过深度推理' },
  { value: 'balanced', icon: '⚖️', name: '平衡', desc: 'Qwen3-8B · 同款模型 · 默认 Self-RAG' },
  { value: 'deep', icon: '🧠', name: '深度', desc: 'DeepSeek-R1 · thinking + 重检索' },
]
const currentMode = computed(() =>
  thinkingModes.find((m) => m.value === uiStore.thinkingMode) || thinkingModes[1]
)
function pickMode(v) {
  uiStore.setThinkingMode(v)
  showModePicker.value = false
}

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

/* ===== 思考模式选择 (2026-08-31 自设置页迁入) ===== */
.mode-strip {
  display: flex;
  padding: 0 4px 6px;
}
.mode-chip {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  padding: 5px 12px;
  border-radius: var(--mg-radius-pill, 999px);
  border: 1.5px solid var(--mg-glass-border, rgba(124, 107, 216, 0.18));
  background: var(--mg-glass-bg, rgba(255, 255, 255, 0.55));
  color: var(--mg-text, #322940);
  font-size: 12px;
  font-weight: 700;
  cursor: pointer;
  -webkit-tap-highlight-color: transparent;
  transition: transform 150ms ease, border-color 150ms ease;
}
.mode-chip:active { transform: scale(0.96); }
.mode-chip-icon { font-size: 13px; line-height: 1; }
.mode-chip-caret { font-size: 9px; opacity: 0.6; }

/* Teleport 到 body 的面板仍携带本组件 scoped 属性, 选择器照常生效 */
.mode-picker-backdrop {
  position: fixed;
  inset: 0;
  z-index: 2100;
  background: rgba(20, 12, 40, 0.32);
  display: flex;
  align-items: flex-end;
  padding: 0 14px calc(env(safe-area-inset-bottom, 0px) + 96px);
}
.mode-picker-backdrop .mode-picker {
  width: 100%;
  border-radius: 22px;
  padding: 16px 14px 14px;
  background: var(--mg-glass-bg-strong, rgba(255, 255, 255, 0.92));
  border: 1.5px solid var(--mg-glass-border, rgba(124, 107, 216, 0.2));
  -webkit-backdrop-filter: blur(22px);
  backdrop-filter: blur(22px);
  box-shadow: 0 18px 50px rgba(50, 30, 90, 0.28);
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.mode-picker-backdrop .mode-picker-title {
  font-size: 14px;
  font-weight: 800;
  color: var(--mg-text, #322940);
  padding: 0 2px 2px;
}
.mode-picker-backdrop .mode-option {
  display: flex;
  align-items: center;
  gap: 12px;
  width: 100%;
  padding: 12px 14px;
  border-radius: var(--mg-radius-md, 14px);
  border: 1.5px solid var(--mg-glass-border, rgba(124, 107, 216, 0.16));
  background: var(--mg-glass-bg, rgba(255, 255, 255, 0.55));
  cursor: pointer;
  text-align: left;
  -webkit-tap-highlight-color: transparent;
  transition: transform 150ms ease, border-color 150ms ease, background 150ms ease;
}
.mode-picker-backdrop .mode-option:active { transform: scale(0.98); }
.mode-picker-backdrop .mode-option.active {
  border-color: transparent;
  background: var(--mg-gradient-soft, linear-gradient(135deg, rgba(124, 107, 216, 0.14), rgba(240, 138, 192, 0.14)));
  box-shadow: 0 0 0 1.5px var(--mg-primary, #7C6BD8);
}
.mode-picker-backdrop .mode-icon { font-size: 20px; flex-shrink: 0; }
.mode-picker-backdrop .mode-text { display: flex; flex-direction: column; gap: 2px; min-width: 0; }
.mode-picker-backdrop .mode-name {
  font-size: 14px;
  font-weight: 700;
  color: var(--mg-text, #322940);
}
.mode-picker-backdrop .mode-desc {
  font-size: 11.5px;
  color: var(--mg-text-soft, #8A7BA8);
}
.mode-picker-backdrop .mode-check {
  margin-left: auto;
  width: 24px;
  height: 24px;
  border-radius: 50%;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  font-size: 13px;
  font-weight: 800;
  color: var(--mg-on-primary, #fff);
  background: var(--mg-gradient-btn, linear-gradient(135deg, #7C6BD8, #F08AC0));
  flex-shrink: 0;
}
.mode-picker-backdrop .mode-check:empty { background: transparent; }

/* 进出场 */
.mode-pop-enter-active, .mode-pop-leave-active { transition: opacity 200ms ease; }
.mode-pop-enter-active .mode-picker, .mode-pop-leave-active .mode-picker { transition: transform 200ms ease; }
.mode-pop-enter-from, .mode-pop-leave-to { opacity: 0; }
.mode-pop-enter-from .mode-picker, .mode-pop-leave-to .mode-picker { transform: translateY(40px); }
</style>