<template>
  <div class="mvi-wrap" :class="{ 'is-recording': isRecording, 'is-cancelled': isCancelled }">
    <button
      id="mobile-voice-input-btn"
      name="mobile-voice-input-btn"
      type="button"
      class="mvi-btn"
      :aria-label="ariaLabel"
      :title="ariaLabel"
      :disabled="disabled"
      @touchstart.passive.prevent="onTouchStart"
      @touchend.passive.prevent="onTouchEnd"
      @touchcancel.passive="onTouchEnd"
      @mousedown.prevent="onMouseDown"
      @mouseup="onMouseUp"
      @mouseleave="onMouseUp"
    >
      <el-icon :size="20"><Microphone /></el-icon>
    </button>

    <!-- 录音中浮层: 波浪 + 时长 + 提示 -->
    <Teleport to="body">
      <Transition name="mvi-overlay">
        <div
          v-if="isRecording || isProcessing"
          id="mobile-voice-input-overlay"
          class="mvi-overlay"
          :class="{ 'is-cancel-zone': isCancelZone }"
          role="status"
          aria-live="polite"
        >
          <div class="mvi-panel glass glass-lg">
            <div class="mvi-row mvi-bars">
              <span
                v-for="(h, i) in barHeights"
                :key="i"
                class="mvi-bar"
                :style="{ height: h + 'px' }"
              />
            </div>
            <div class="mvi-row mvi-time">
              <span class="rec-dot" />
              <span class="mvi-elapsed">{{ formattedElapsed }}</span>
              <span class="mvi-hint">
                {{
                  isCancelZone
                    ? '松手取消'
                    : isProcessing
                    ? '转写中…'
                    : '松开发送，上滑取消'
                }}
              </span>
            </div>
          </div>
        </div>
      </Transition>
    </Teleport>
  </div>
</template>

<script setup>
/**
 * MobileVoiceInputButton.vue — 移动端语音输入按钮 (W68 路线 G-1)
 *
 * 设计：
 * - 长按麦克风按钮开始录音 (类似微信)
 * - 上滑超 50px 取消 (dy < -50)
 * - 松开发送 (走父组件 asr → inputText 插入 + autoSend 决定是否发)
 * - 浮层: 5 根音量柱 + 时长 + 状态提示
 * - iOS Safari PWA 兼容: 浮层 Teleport 到 body (避免父容器 transform 限制)
 * - dark mode: 浮层玻璃态 glass-lg, 非 scoped 块 (CLAUDE.md v60-v67 教训)
 *
 * 关键事件：
 * - 父组件 v-model:text 双向绑定 (录音后插入文本)
 * - @transcribed(text) 事件, 父组件可追加额外逻辑 (e.g. 不自动发, 让用户编辑)
 * - @recording 事件 (start/cancel/error), 父组件可锁定键盘
 *
 * 触觉反馈 (CLAUDE.md 2026-06-27 教训):
 * - start: tap() 10ms
 * - success: success() [10, 50, 10]
 * - cancel: warning() [30, 50, 30]
 *
 * 入参:
 * - autoSend: false (默认, 仅插入文本不发送) / true (识别后自动 sendMessage)
 * - placeholder: 父组件 v-model:text 受控
 */

import { computed, ref } from 'vue'
import { Microphone } from '@element-plus/icons-vue'
import { useMobileVoiceInput } from '@/composables/useMobileVoiceInput'

const props = defineProps({
  /** ASR 后是否自动发送 (默认 false, 仅插入文本) */
  autoSend: { type: Boolean, default: false },
  /** 禁用录音 (e.g. 流式中) */
  disabled: { type: Boolean, default: false },
  /** aria-label 覆盖 */
  ariaLabel: { type: String, default: '按住说话' },
  /** 父组件受控文本 (asr 完成后回写) */
  text: { type: String, default: '' },
  /** 上滑取消阈值 (px) */
  slideCancelThreshold: { type: Number, default: 50 },
})

const emit = defineEmits([
  'update:text', // v-model:text 支持 (父组件用 v-model 绑定)
  'transcribed', // (text: string) 识别成功后
  'recording', // (state: 'start' | 'cancel' | 'error') 录音生命周期
  'send', // (text: string) autoSend=true 时触发, 父组件调 sendMessage
])

const isCancelZone = ref(false) // 上滑超阈值, 提示松手取消

// ===== useMobileVoiceInput 实例 =====
const voice = useMobileVoiceInput({
  autoSend: props.autoSend,
  slideCancelThreshold: props.slideCancelThreshold,
  onTranscribed: (text) => {
    // 插入 textarea (v-model:text)
    emit('update:text', text)
    emit('transcribed', text)
  },
  onAutoSend: (text) => {
    // autoSend=true 时调父组件 send
    emit('send', text)
  },
  onCancelled: () => {
    isCancelZone.value = false
    emit('recording', 'cancel')
  },
  onError: (err) => {
    isCancelZone.value = false
    emit('recording', 'error')
    // eslint-disable-next-line no-console
    console.warn('[MobileVoiceInput] error:', err.message)
  },
})

const isRecording = computed(() => voice.isRecording.value)
const isProcessing = computed(() => voice.isProcessing.value)
const isCancelled = computed(() => voice.state.value === 'cancelled')
const barHeights = computed(() => voice.barHeights.value)
const elapsedMs = computed(() => voice.elapsedMs.value)

// mm:ss 格式
const formattedElapsed = computed(() => {
  const total = Math.floor(elapsedMs.value / 1000)
  const m = Math.floor(total / 60)
  const s = total % 60
  return `${m.toString().padStart(2, '0')}:${s.toString().padStart(2, '0')}`
})

// ===== 手势 =====
let pressStartY = 0
let pressStartTime = 0

async function onTouchStart(e) {
  if (props.disabled) return
  pressStartY = e.touches?.[0]?.clientY || 0
  pressStartTime = Date.now()
  isCancelZone.value = false
  if (voice.onTouchMove && voice.onTouchMove._setStartY) {
    voice.onTouchMove._setStartY(pressStartY)
  }
  const ok = await voice.start()
  if (ok) emit('recording', 'start')
}

function onTouchEnd() {
  if (!isRecording.value && !isProcessing.value) return
  if (isCancelZone.value) {
    // 在取消区松手 → 取消
    voice.cancel()
    isCancelZone.value = false
    return
  }
  voice.stop()
}

async function onMouseDown(e) {
  // 桌面 dev 用, 触屏设备不会触发
  if (props.disabled) return
  pressStartY = e.clientY || 0
  pressStartTime = Date.now()
  isCancelZone.value = false
  if (voice.onTouchMove && voice.onTouchMove._setStartY) {
    voice.onTouchMove._setStartY(pressStartY)
  }
  const ok = await voice.start()
  if (ok) emit('recording', 'start')
}

function onMouseUp() {
  if (!isRecording.value && !isProcessing.value) return
  if (isCancelZone.value) {
    voice.cancel()
    isCancelZone.value = false
    return
  }
  voice.stop()
}

// 暴露 onTouchMove 给父容器 (MobileInputBar 需要 @touchmove.passive 监听整个输入栏)
// 注: 因为按钮是 input bar 的一分子, 我们也可以把 onTouchMove 挂在按钮上
//     但 touchmove 默认 passive=true, 不 preventDefault, 不会 cancel gesture
//     这里给父组件一个 prop 决定: 是否监听输入栏整体 touchmove
import { onMounted, onBeforeUnmount } from 'vue'

function _handleGlobalTouchMove(e) {
  if (!isRecording.value) return
  const touch = e.touches[0]
  if (!touch) return
  const dy = touch.clientY - pressStartY
  // 上滑超阈值 → 进入取消区
  if (dy < -props.slideCancelThreshold) {
    if (!isCancelZone.value) isCancelZone.value = true
  } else {
    if (isCancelZone.value) isCancelZone.value = false
  }
}

onMounted(() => {
  if (typeof window !== 'undefined') {
    window.addEventListener('touchmove', _handleGlobalTouchMove, { passive: true })
    window.addEventListener('mousemove', _handleGlobalTouchMove)
  }
})

onBeforeUnmount(() => {
  if (typeof window !== 'undefined') {
    window.removeEventListener('touchmove', _handleGlobalTouchMove)
    window.removeEventListener('mousemove', _handleGlobalTouchMove)
  }
  voice.dispose()
})

// 暴露 onTouchMove 供父容器 (MobileInputBar) 调
defineExpose({
  onTouchMove: _handleGlobalTouchMove,
  isCancelZone,
})
</script>

<style scoped>
.mvi-wrap {
  position: relative;
  display: inline-block;
}

.mvi-btn {
  width: 40px;
  height: 40px;
  border-radius: 50%;
  background: linear-gradient(
    135deg,
    var(--color-primary) 0%,
    var(--color-primary-light) 100%
  );
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
  transition: transform 150ms;
}

.mvi-btn:active,
.mvi-btn.is-recording {
  transform: scale(1.1);
}

.mvi-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.mvi-overlay {
  position: fixed;
  inset: 0;
  z-index: 5000;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(0, 0, 0, 0.35);
  pointer-events: none;
}

.mvi-panel {
  background: var(--color-bg-card);
  border-radius: 20px;
  padding: 24px 32px;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 16px;
  min-width: 220px;
  box-shadow: var(--shadow-lg);
}

.mvi-row {
  display: flex;
  align-items: center;
  gap: 8px;
}

.mvi-bars {
  height: 48px;
  align-items: center;
}

.mvi-bar {
  display: inline-block;
  width: 6px;
  background: linear-gradient(
    180deg,
    var(--color-primary) 0%,
    var(--color-primary-light) 100%
  );
  border-radius: 3px;
  transition: height 100ms ease-out;
}

.mvi-overlay.is-cancel-zone .mvi-bar {
  background: linear-gradient(
    180deg,
    var(--color-danger, #f56c6c) 0%,
    #ff9985 100%
  );
}

.mvi-time {
  font-size: 14px;
  color: var(--color-text-primary);
}

.mvi-elapsed {
  font-weight: 600;
  font-variant-numeric: tabular-nums;
}

.mvi-hint {
  color: var(--color-text-secondary);
  font-size: 12px;
}

.rec-dot {
  width: 10px;
  height: 10px;
  border-radius: 50%;
  background: var(--color-danger, #f56c6c);
  animation: pulse 1s infinite;
}

.mvi-overlay.is-cancel-zone .rec-dot {
  animation: none;
  background: var(--color-danger, #f56c6c);
}

.mvi-overlay-enter-active,
.mvi-overlay-leave-active {
  transition: opacity 200ms ease;
}
.mvi-overlay-enter-from,
.mvi-overlay-leave-to {
  opacity: 0;
}

@keyframes pulse {
  0%,
  100% {
    transform: scale(1);
    opacity: 1;
  }
  50% {
    transform: scale(1.2);
    opacity: 0.6;
  }
}
</style>

<!-- v77 P2.6-B: dark mode 适配 (v60-v67 教训: 必须非 scoped 块) -->
<style>
[data-theme="dark"] .mvi-panel {
  background: var(--color-bg-card);
  color: var(--color-text-primary);
}

[data-theme="dark"] .mvi-hint {
  color: var(--color-text-secondary);
}
</style>
