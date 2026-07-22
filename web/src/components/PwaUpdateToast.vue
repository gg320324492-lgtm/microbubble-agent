<template>
  <Transition name="pwa-update-toast">
    <aside
      v-if="visible"
      class="pwa-update-toast"
      role="status"
      aria-live="polite"
      data-testid="pwa-update-toast"
    >
      <div class="pwa-update-toast__mark" aria-hidden="true">↻</div>
      <div class="pwa-update-toast__content">
        <strong>新版本已就绪</strong>
        <span>{{ version ? `${version} 已准备好，刷新后即可使用` : '刷新后即可使用最新版本' }}</span>
      </div>
      <div class="pwa-update-toast__actions">
        <button
          type="button"
          class="pwa-update-toast__button pwa-update-toast__button--refresh"
          data-testid="pwa-update-toast-refresh"
          @click="handleRefresh"
        >点此刷新</button>
        <button
          type="button"
          class="pwa-update-toast__button pwa-update-toast__button--dismiss"
          data-testid="pwa-update-toast-dismiss"
          aria-label="忽略此版本更新提示"
          @click="handleDismiss"
        >忽略</button>
      </div>
    </aside>
  </Transition>
</template>

<script setup>
import { onMounted, onUnmounted, ref } from 'vue'

const DISMISS_PREFIX = 'pwa_update_dismissed_'
const DISMISS_AT_SUFFIX = '_at'
const DISMISS_TTL_MS = 7 * 24 * 60 * 60 * 1000

const visible = ref(false)
const version = ref('')
const dismissed = ref(false)

function keyFor(updateVersion) {
  return `${DISMISS_PREFIX}${updateVersion}`
}

function isDismissedRecently(updateVersion) {
  if (!updateVersion || typeof localStorage === 'undefined') return false
  try {
    const key = keyFor(updateVersion)
    if (localStorage.getItem(key) !== '1') return false
    const timestamp = Number(localStorage.getItem(`${key}${DISMISS_AT_SUFFIX}`))
    // A legacy flag without a timestamp remains suppressed for compatibility.
    if (!Number.isFinite(timestamp) || timestamp <= 0) return true
    if (Date.now() - timestamp < DISMISS_TTL_MS) return true
    localStorage.removeItem(key)
    localStorage.removeItem(`${key}${DISMISS_AT_SUFFIX}`)
  } catch (err) {
    return false
  }
  return false
}

function showUpdate(update) {
  const updateVersion = typeof update?.version === 'string' ? update.version.trim() : ''
  const alreadyDismissed = updateVersion && isDismissedRecently(updateVersion)
  if (!updateVersion || alreadyDismissed) {
    dismissed.value = Boolean(alreadyDismissed)
    return
  }
  version.value = updateVersion
  dismissed.value = false
  visible.value = true
}

function handleRefresh() {
  window.location.reload()
}

function handleDismiss() {
  if (!version.value) {
    visible.value = false
    return
  }
  const key = keyFor(version.value)
  try {
    localStorage.setItem(key, '1')
    localStorage.setItem(`${key}${DISMISS_AT_SUFFIX}`, String(Date.now()))
  } catch (err) {
    // Closing remains available when storage is disabled or full.
  }
  dismissed.value = true
  visible.value = false
}

let serviceWorkerMessageHandler
let appUpdateHandler

onMounted(() => {
  serviceWorkerMessageHandler = (event) => {
    if (event.data?.type === 'SW_UPDATED') showUpdate(event.data)
  }
  appUpdateHandler = (event) => showUpdate(event.detail)
  if (typeof navigator !== 'undefined' && 'serviceWorker' in navigator) {
    navigator.serviceWorker.addEventListener('message', serviceWorkerMessageHandler)
  }
  window.addEventListener('pwa-update-available', appUpdateHandler)
})

onUnmounted(() => {
  if (typeof navigator !== 'undefined' && 'serviceWorker' in navigator && serviceWorkerMessageHandler) {
    navigator.serviceWorker.removeEventListener('message', serviceWorkerMessageHandler)
  }
  if (appUpdateHandler) window.removeEventListener('pwa-update-available', appUpdateHandler)
})

defineExpose({ visible, version, dismissed, showUpdate })
</script>

<style>
.pwa-update-toast {
  position: fixed;
  top: max(60px, calc(var(--header-mobile-height, 52px) + var(--sat, 0px) + 8px));
  left: 50%;
  z-index: 6000;
  display: flex;
  align-items: center;
  gap: 12px;
  width: min(620px, calc(100vw - 24px));
  min-height: 64px;
  padding: 10px 12px 10px 14px;
  color: var(--color-text-primary, #2d2d2d);
  background: var(--color-bg-card, #fff);
  border: 1px solid var(--color-primary-border, rgba(255, 122, 92, 0.22));
  border-left: 4px solid var(--color-primary, #ff7a5c);
  border-radius: var(--radius-lg, 12px);
  box-shadow: var(--shadow-lg, 0 8px 32px rgba(0, 0, 0, 0.12));
  transform: translateX(-50%);
}
.pwa-update-toast__mark {
  display: grid;
  flex: 0 0 34px;
  width: 34px;
  height: 34px;
  place-items: center;
  color: var(--color-primary-dark, #e85a3a);
  background: var(--color-primary-bg, #fff0ed);
  border-radius: 50%;
  font-size: 20px;
  line-height: 1;
}
.pwa-update-toast__content {
  display: flex;
  flex: 1;
  min-width: 0;
  flex-direction: column;
  gap: 2px;
}
.pwa-update-toast__content strong { font-size: 14px; line-height: 1.3; }
.pwa-update-toast__content span {
  overflow: hidden;
  color: var(--color-text-secondary, #606266);
  font-size: 12px;
  line-height: 1.4;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.pwa-update-toast__actions { display: flex; flex: 0 0 auto; gap: 4px; }
.pwa-update-toast__button {
  min-height: var(--touch-target-min, 44px);
  padding: 8px 10px;
  border: 0;
  border-radius: var(--radius-md, 8px);
  font: inherit;
  font-size: 13px;
  font-weight: var(--font-weight-medium, 500);
  cursor: pointer;
  transition: background var(--duration-fast, 150ms), transform var(--duration-fast, 150ms);
}
.pwa-update-toast__button:focus-visible {
  outline: 3px solid color-mix(in srgb, var(--color-primary, #ff7a5c) 45%, transparent);
  outline-offset: 2px;
}
.pwa-update-toast__button:active { transform: scale(0.97); }
.pwa-update-toast__button--refresh { color: #fff; background: var(--color-primary-dark, #e85a3a); }
.pwa-update-toast__button--refresh:hover { background: var(--color-primary, #ff7a5c); }
.pwa-update-toast__button--dismiss { color: var(--color-text-secondary, #606266); background: transparent; }
.pwa-update-toast__button--dismiss:hover { background: var(--color-primary-bg, #fff0ed); }
.pwa-update-toast-enter-active,
.pwa-update-toast-leave-active {
  transition: opacity var(--duration-normal, 200ms) var(--ease-out, ease-out), transform var(--duration-normal, 200ms) var(--ease-out, ease-out);
}
.pwa-update-toast-enter-from,
.pwa-update-toast-leave-to { opacity: 0; transform: translate(-50%, -18px); }
@media (max-width: 480px) {
  .pwa-update-toast { align-items: flex-start; gap: 9px; padding: 10px; }
  .pwa-update-toast__mark { flex-basis: 30px; width: 30px; height: 30px; }
  .pwa-update-toast__actions { flex-direction: column; align-items: stretch; }
  .pwa-update-toast__button { min-height: 36px; padding: 5px 8px; white-space: nowrap; }
}
@media (prefers-reduced-motion: reduce) {
  .pwa-update-toast-enter-active,
  .pwa-update-toast-leave-active,
  .pwa-update-toast__button { transition: none; }
}
/* Non-scoped theme rules keep dark mode consistent across the app shell. */
[data-theme='dark'] .pwa-update-toast {
  color: var(--color-text-primary, #f0f0f0);
  background: var(--color-bg-card, #1f1f1f);
  border-color: rgba(var(--color-primary-rgb, 255, 122, 92), 0.35);
}
[data-theme='dark'] .pwa-update-toast__mark { background: rgba(var(--color-primary-rgb, 255, 122, 92), 0.16); }
[data-theme='dark'] .pwa-update-toast__content span,
[data-theme='dark'] .pwa-update-toast__button--dismiss { color: var(--color-text-secondary, #a0a0a0); }
[data-theme='dark'] .pwa-update-toast__button--dismiss:hover { background: rgba(var(--color-primary-rgb, 255, 122, 92), 0.14); }
</style>
