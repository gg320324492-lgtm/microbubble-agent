<template>
  <Teleport to="body">
    <Transition name="biometric-fade">
      <div
        v-if="modelValue"
        class="biometric-overlay"
        role="dialog"
        aria-modal="true"
        aria-label="生物识别"
        @click.self="onBackdropClick"
      >
        <div class="biometric-panel" :style="{ paddingBottom: panelPaddingBottom }">
          <div class="biometric-handle" />

          <div class="biometric-header">
            <div class="biometric-icon-wrap" :class="{ pulsing: loading }">
              <span class="biometric-icon">{{ iconEmoji }}</span>
            </div>
            <h3 class="biometric-title">
              {{ phase === 'verify' ? `验证 ${bioLabel}` : phase === 'pin-setup' ? '设置 PIN 码' : phase === 'pin-verify' ? '输入 PIN 码' : '选择认证方式' }}
            </h3>
            <p v-if="phase === 'verify'" class="biometric-subtitle">
              请将手指放在 {{ sensorHint }} 上
            </p>
            <p v-else-if="phase === 'pin-setup'" class="biometric-subtitle">
              设置 6 位数字 PIN 码 (用于 {{ bioLabel }} 失败时 fallback)
            </p>
            <p v-else-if="phase === 'pin-verify'" class="biometric-subtitle">
              {{ hint }}
            </p>
            <p v-else class="biometric-subtitle">
              {{ hint || '请选择认证方式' }}
            </p>
          </div>

          <!-- PIN 输入 -->
          <div v-if="phase === 'pin-setup' || phase === 'pin-verify'" class="pin-section">
            <div class="pin-display">
              <span
                v-for="i in 6"
                :key="i"
                class="pin-dot"
                :class="{ filled: pin.length >= i, error: pinError }"
              >{{ pin.length >= i ? '•' : '' }}</span>
            </div>
            <div class="pin-pad">
              <button
                v-for="d in padLayout"
                :key="d"
                type="button"
                class="pin-key"
                :disabled="loading"
                :aria-label="`数字 ${d}`"
                @click="onPinKey(d)"
              >{{ d }}</button>
              <button
                type="button"
                class="pin-key pin-key-action"
                :disabled="loading"
                :aria-label="'清空'"
                @click="onPinClear"
              >⌫</button>
              <button
                type="button"
                class="pin-key pin-key-action"
                :disabled="loading"
                :aria-label="'数字 0'"
                @click="onPinKey('0')"
              >0</button>
              <button
                type="button"
                class="pin-key pin-key-confirm"
                :disabled="pin.length < 6 || loading"
                :aria-label="'确认'"
                @click="onPinConfirm"
              >✓</button>
            </div>
            <p v-if="pinError" class="pin-error">⚠️ {{ pinError }}</p>
            <p v-if="lockRemaining > 0" class="pin-locked">🔒 已锁定, 还需等待 {{ lockRemaining }}s</p>
          </div>

          <!-- 选择认证方式 -->
          <div v-else-if="phase === 'choose'" class="biometric-choose">
            <button
              v-if="canUseBio"
              type="button"
              class="choose-btn"
              :disabled="loading"
              @click="startWebAuthn"
            >
              <span class="choose-icon">{{ iconEmoji }}</span>
              <span class="choose-label">{{ bioLabel }} 一键登录</span>
            </button>
            <button
              type="button"
              class="choose-btn"
              :disabled="loading"
              @click="goToPinSetup"
            >
              <span class="choose-icon">🔢</span>
              <span class="choose-label">设置 PIN 码 (6 位)</span>
            </button>
            <button
              v-if="hasPin"
              type="button"
              class="choose-btn"
              :disabled="loading"
              @click="goToPinVerify"
            >
              <span class="choose-icon">🔐</span>
              <span class="choose-label">使用 PIN 码登录</span>
            </button>
          </div>

          <!-- loading / status -->
          <div v-else-if="phase === 'verify'" class="biometric-status">
            <p class="biometric-status-text">
              <span v-if="loading">⏳ 等待 {{ bioLabel }} 验证...</span>
              <span v-else-if="lastError">⚠️ {{ lastError }}</span>
              <span v-else>👆 点下方按钮开始验证</span>
            </p>
            <button
              v-if="!loading"
              type="button"
              class="biometric-retry"
              @click="startWebAuthn"
            >重新验证</button>
            <button
              v-if="!loading"
              type="button"
              class="biometric-cancel"
              @click="onFallbackPin"
            >改用 PIN 码</button>
          </div>

          <button
            v-if="phase !== 'verify' || !loading"
            type="button"
            class="biometric-close"
            :aria-label="'关闭'"
            @click="close"
          >取消</button>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<script setup>
/**
 * MobileBiometricAuth.vue — 移动端生物识别认证弹窗
 *
 * W68 第 8 批 B-3: Mobile UX v3.2 生物识别集成
 *
 * 设计：
 * - v-model:show 控制显示
 * - phase 状态机: choose → verify (webauthn) | pin-setup | pin-verify
 * - iOS Face ID / Touch ID / Android 指纹图标自适应 (从 useMobileBiometric.support)
 * - 失败自动降级到 PIN 码
 * - PIN 6 位数字, 失败 5 次锁 5 分钟
 *
 * 事件:
 *   @success: 认证成功 (method: 'webauthn' | 'pin')
 *   @cancel: 用户关闭
 *   @error: 错误
 *
 * 用法:
 *   const showBio = ref(false)
 *   <MobileBiometricAuth v-model:show="showBio" title="Face ID 登录" @success="onBioSuccess" />
 */

import { ref, computed, watch, onMounted } from 'vue'
import { useHaptic } from '@/composables/chat/useHaptic'
import { useMobileBiometric } from '@/composables/useMobileBiometric'

const props = defineProps({
  modelValue: { type: Boolean, default: false },
  title: { type: String, default: '' },
  hint: { type: String, default: '' },
  /** 是否启用 PIN 设置 (默认 true) */
  enablePinSetup: { type: Boolean, default: true },
  /** 是否启用 WebAuthn 一键 (默认 true, 设备支持时显示) */
  enableWebAuthn: { type: Boolean, default: true },
  /** 失败后自动 fallback PIN (默认 true) */
  autoFallbackPin: { type: Boolean, default: true },
})

const emit = defineEmits(['update:modelValue', 'success', 'cancel', 'error'])

const haptic = useHaptic()
const bio = useMobileBiometric()

const phase = ref('choose') // 'choose' | 'verify' | 'pin-setup' | 'pin-verify'
const pin = ref('')
const pinError = ref('')
const pinSetupConfirm = ref('') // PIN 二次确认缓存
const loading = ref(false)
const lastError = ref('')
const lockRemaining = ref(0)

let lockTimer = null

const support = computed(() => bio.support.value)
const canUseBio = computed(() => props.enableWebAuthn && (support.value?.available ?? false))
const hasPin = computed(() => bio.hasPIN())

const bioLabel = computed(() => support.value?.displayName || '生物识别')
const iconEmoji = computed(() => {
  const t = support.value?.authenticatorType
  if (t === 'face') return '😊'
  if (t === 'touch') return '👆'
  if (t === 'fingerprint') return '☝️'
  return '🔐'
})

const sensorHint = computed(() => {
  const t = support.value?.authenticatorType
  if (t === 'face') return 'Face ID 传感器'
  if (t === 'touch') return 'Home 键 / 屏下指纹'
  if (t === 'fingerprint') return '指纹传感器'
  return '传感器'
})

const panelPaddingBottom = computed(() => {
  return 'calc(20px + var(--sab, 0px))'
})

const padLayout = ['1', '2', '3', '4', '5', '6', '7', '8', '9']

watch(() => props.modelValue, async (val) => {
  if (val) {
    // 打开弹窗: 初始化探测 + 状态
    if (!support.value) {
      await bio.detectSupport()
    }
    pin.value = ''
    pinError.value = ''
    lastError.value = ''
    // 默认进入 choose phase
    if (canUseBio.value) {
      phase.value = 'choose'
    } else if (hasPin.value) {
      phase.value = 'pin-verify'
    } else if (props.enablePinSetup) {
      phase.value = 'pin-setup'
    } else {
      phase.value = 'choose'
    }
    startLockCountdown()
  } else {
    stopLockCountdown()
  }
})

onMounted(() => {
  // 预探测
  bio.detectSupport().catch(() => {})
})

function startLockCountdown() {
  stopLockCountdown()
  if (!bio.isLocked.value) {
    lockRemaining.value = 0
    return
  }
  // 计算剩余秒数
  const until = parseInt(localStorage.getItem('mobile_biometric_locked_until') || '0', 10)
  const remaining = Math.max(0, Math.ceil((until - Date.now()) / 1000))
  lockRemaining.value = remaining
  if (remaining > 0) {
    lockTimer = setInterval(() => {
      const u = parseInt(localStorage.getItem('mobile_biometric_locked_until') || '0', 10)
      const r = Math.max(0, Math.ceil((u - Date.now()) / 1000))
      lockRemaining.value = r
      if (r <= 0) {
        stopLockCountdown()
        if (phase.value === 'pin-verify') {
          pinError.value = ''
        }
      }
    }, 1000)
  }
}

function stopLockCountdown() {
  if (lockTimer) {
    clearInterval(lockTimer)
    lockTimer = null
  }
}

function close() {
  emit('update:modelValue', false)
  emit('cancel')
}

function onBackdropClick() {
  if (!loading.value) close()
}

function onPinKey(d) {
  if (pin.value.length >= 6 || loading.value || lockRemaining.value > 0) return
  pin.value += d
  pinError.value = ''
}

function onPinClear() {
  pin.value = pin.value.slice(0, -1)
  pinError.value = ''
}

async function onPinConfirm() {
  if (pin.value.length < 6) return
  loading.value = true
  try {
    if (phase.value === 'pin-setup') {
      if (!pinSetupConfirm.value) {
        // 第一次输入: 缓存, 让用户再输入一次
        pinSetupConfirm.value = pin.value
        pin.value = ''
        pinError.value = '请再次输入确认'
        haptic.tap()
        loading.value = false
        return
      }
      if (pinSetupConfirm.value !== pin.value) {
        pinError.value = '两次输入不一致, 请重新设置'
        pinSetupConfirm.value = ''
        pin.value = ''
        haptic.warning()
        loading.value = false
        return
      }
      const ok = await bio.registerPIN(pin.value)
      if (ok) {
        pinSetupConfirm.value = ''
        phase.value = 'pin-verify'
        pin.value = ''
        pinError.value = 'PIN 已设置, 请输入验证'
        haptic.success()
      }
    } else if (phase.value === 'pin-verify') {
      const result = await bio.verifyPIN(pin.value)
      if (result.ok) {
        haptic.success()
        pin.value = ''
        emit('success', { method: 'pin' })
        emit('update:modelValue', false)
      } else {
        pinError.value = result.error || 'PIN 错误'
        pin.value = ''
        haptic.error()
        startLockCountdown()
      }
    }
  } catch (e) {
    pinError.value = e?.message || 'PIN 处理失败'
  } finally {
    loading.value = false
  }
}

async function startWebAuthn() {
  loading.value = true
  lastError.value = ''
  phase.value = 'verify'
  try {
    const result = await bio.authenticate()
    if (result.ok) {
      haptic.success()
      emit('success', { method: 'webauthn' })
      emit('update:modelValue', false)
    } else if (result.dismissed) {
      // 用户取消 — 留在 verify phase, 让用户重试或 fallback
      lastError.value = '已取消, 请重试或改用 PIN 码'
      phase.value = 'choose'
    } else {
      lastError.value = result.error || '验证失败'
      haptic.error()
      if (props.autoFallbackPin) {
        phase.value = 'pin-setup'
      }
    }
  } catch (e) {
    lastError.value = e?.message || '未知错误'
    haptic.error()
  } finally {
    loading.value = false
  }
}

function onFallbackPin() {
  if (hasPin.value) {
    goToPinVerify()
  } else {
    goToPinSetup()
  }
}

function goToPinSetup() {
  pin.value = ''
  pinSetupConfirm.value = ''
  pinError.value = ''
  phase.value = 'pin-setup'
}

function goToPinVerify() {
  pin.value = ''
  pinError.value = ''
  phase.value = 'pin-verify'
}
</script>

<style scoped>
.biometric-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.6);
  z-index: 10000;
  display: flex;
  align-items: flex-end;
  justify-content: center;
  -webkit-tap-highlight-color: transparent;
}

.biometric-panel {
  width: 100%;
  max-width: 480px;
  background: var(--color-bg-card, #ffffff);
  border-top-left-radius: var(--radius-xl, 16px);
  border-top-right-radius: var(--radius-xl, 16px);
  padding: 8px 24px 20px;
  box-shadow: var(--shadow-lg, 0 8px 32px rgba(0, 0, 0, 0.2));
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.biometric-handle {
  width: 36px;
  height: 4px;
  background: var(--color-border, #dcdfe6);
  border-radius: 2px;
  margin: 8px auto 0;
}

.biometric-header {
  text-align: center;
  padding: 8px 12px 4px;
}

.biometric-icon-wrap {
  width: 72px;
  height: 72px;
  border-radius: 50%;
  background: linear-gradient(135deg, var(--color-primary-bg, #fff1ed) 0%, var(--color-accent-bg, #fff7e6) 100%);
  display: flex;
  align-items: center;
  justify-content: center;
  margin: 0 auto 12px;
  box-shadow: 0 4px 16px rgba(var(--color-primary-rgb, 255, 122, 92), 0.2);
  transition: transform 0.3s ease;
}
.biometric-icon-wrap.pulsing {
  animation: pulse 1.5s ease-in-out infinite;
}
@keyframes pulse {
  0%, 100% { transform: scale(1); }
  50% { transform: scale(1.08); }
}

.biometric-icon {
  font-size: 36px;
}

.biometric-title {
  font-size: 18px;
  font-weight: var(--font-weight-semibold, 600);
  color: var(--color-text-primary);
  margin: 0 0 6px;
}

.biometric-subtitle {
  font-size: 13px;
  color: var(--color-text-secondary);
  margin: 0;
  line-height: 1.4;
}

/* PIN Display */
.pin-display {
  display: flex;
  justify-content: center;
  gap: 12px;
  margin-bottom: 16px;
}

.pin-dot {
  width: 16px;
  height: 16px;
  border-radius: 50%;
  border: 2px solid var(--color-border, #dcdfe6);
  background: transparent;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 14px;
  color: var(--color-primary, #FF7A5C);
  transition: all 0.2s ease;
}

.pin-dot.filled {
  background: var(--color-primary, #FF7A5C);
  border-color: var(--color-primary, #FF7A5C);
}
.pin-dot.filled::after {
  /* 内容已是 • */
}

.pin-dot.error {
  border-color: var(--color-danger, #F56C6C);
  animation: shake 0.4s ease;
}
@keyframes shake {
  0%, 100% { transform: translateX(0); }
  25% { transform: translateX(-4px); }
  75% { transform: translateX(4px); }
}

/* PIN Pad */
.pin-pad {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 8px;
  margin-bottom: 12px;
}

.pin-key {
  padding: 16px 0;
  border: none;
  border-radius: var(--radius-md, 8px);
  background: var(--color-bg-page, #f5f7fa);
  color: var(--color-text-primary);
  font-size: 22px;
  font-weight: var(--font-weight-medium, 500);
  cursor: pointer;
  font-family: inherit;
  -webkit-tap-highlight-color: transparent;
  transition: background 0.15s ease, transform 0.1s ease;
}
.pin-key:active:not(:disabled) {
  background: var(--color-border-light, #ebeef5);
  transform: scale(0.96);
}
.pin-key:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}
.pin-key-action {
  font-size: 18px;
}
.pin-key-confirm {
  background: var(--color-primary, #FF7A5C);
  color: white;
}
.pin-key-confirm:active:not(:disabled) {
  background: var(--color-primary-dark, #e5694d);
}
.pin-key-confirm:disabled {
  background: var(--color-border, #dcdfe6);
  color: var(--color-text-secondary);
}

.pin-error {
  text-align: center;
  font-size: 13px;
  color: var(--color-danger, #F56C6C);
  margin: 8px 0 0;
}
.pin-locked {
  text-align: center;
  font-size: 13px;
  color: var(--color-warning, #E6A23C);
  margin: 4px 0 0;
}

/* Choose buttons */
.biometric-choose {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.choose-btn {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 14px 18px;
  border: none;
  border-radius: var(--radius-md, 8px);
  background: var(--color-bg-page, #f5f7fa);
  color: var(--color-text-primary);
  font-size: 15px;
  font-weight: var(--font-weight-medium, 500);
  cursor: pointer;
  font-family: inherit;
  -webkit-tap-highlight-color: transparent;
  text-align: left;
}
.choose-btn:active:not(:disabled) {
  background: var(--color-border-light, #ebeef5);
}
.choose-icon {
  font-size: 22px;
}
.choose-label {
  flex: 1;
}

.biometric-status {
  text-align: center;
}

.biometric-status-text {
  font-size: 14px;
  color: var(--color-text-secondary);
  margin: 0 0 12px;
}

.biometric-retry,
.biometric-cancel {
  width: 100%;
  padding: 12px;
  margin-bottom: 8px;
  border: none;
  border-radius: var(--radius-md, 8px);
  font-size: 15px;
  font-weight: var(--font-weight-medium, 500);
  cursor: pointer;
  font-family: inherit;
  -webkit-tap-highlight-color: transparent;
}

.biometric-retry {
  background: var(--color-primary, #FF7A5C);
  color: white;
}
.biometric-cancel {
  background: var(--color-bg-page, #f5f7fa);
  color: var(--color-text-secondary);
}
.biometric-cancel:active {
  background: var(--color-border-light, #ebeef5);
}

.biometric-close {
  width: 100%;
  padding: 12px;
  margin-top: 4px;
  border: none;
  border-radius: var(--radius-md, 8px);
  background: var(--color-bg-page, #f5f7fa);
  color: var(--color-text-primary);
  font-size: 15px;
  cursor: pointer;
  font-family: inherit;
  -webkit-tap-highlight-color: transparent;
}
.biometric-close:active {
  background: var(--color-border-light, #ebeef5);
}

/* Animation */
.biometric-fade-enter-active,
.biometric-fade-leave-active {
  transition: opacity 0.25s ease;
}
.biometric-fade-enter-from,
.biometric-fade-leave-to {
  opacity: 0;
}
.biometric-fade-enter-active .biometric-panel,
.biometric-fade-leave-active .biometric-panel {
  transition: transform 0.3s cubic-bezier(0.16, 1, 0.3, 1);
}
.biometric-fade-enter-from .biometric-panel,
.biometric-fade-leave-to .biometric-panel {
  transform: translateY(100%);
}
</style>

<!-- v77 P2.6-B: dark mode 适配 -->
<style>
[data-theme="dark"] .biometric-overlay {
  background: rgba(0, 0, 0, 0.75);
}
[data-theme="dark"] .biometric-panel {
  background: var(--color-bg-card, #1f1f1f);
  border-top: 1px solid var(--color-border-light, #2c2c2c);
}
[data-theme="dark"] .biometric-title {
  color: var(--color-text-primary);
}
[data-theme="dark"] .pin-key {
  background: var(--color-bg-page, #141414);
  color: var(--color-text-primary);
}
[data-theme="dark"] .pin-key:active:not(:disabled) {
  background: var(--color-border-light, #2c2c2c);
}
[data-theme="dark"] .choose-btn {
  background: var(--color-bg-page, #141414);
  color: var(--color-text-primary);
}
[data-theme="dark"] .biometric-close,
[data-theme="dark"] .biometric-cancel {
  background: var(--color-bg-page, #141414);
  color: var(--color-text-primary);
}
</style>
