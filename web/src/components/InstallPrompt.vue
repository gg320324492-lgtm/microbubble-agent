<!--
  InstallPrompt.vue — PWA 安装提示组件

  设计原则 (PR #10 PWA install prompt 收口):
  - App.vue 监听 beforeinstallprompt 事件, 把 deferredPrompt 通过 prop 传入
  - iOS Safari 检测 navigator.standalone (false 提示, true 不提示)
  - dismissed 持久化: localStorage 标记, 7 天后自动重置 / 访问 Drive 3 次后重置
  - 渐进式: 只在首次访问 7 天后 / drive 访问 3 次后才显示
  - 安全: 失败静默, 不阻塞主流程

  用法 (App.vue 已挂载):
    <InstallPrompt :deferred-prompt="deferredPrompt" />

  设计令牌: --color-primary #FF7A5C / --color-accent #FFB347 (暖橙珊瑚色)
-->
<template>
  <Transition name="install-prompt">
    <div
      v-if="visible"
      class="install-prompt"
      role="alertdialog"
      aria-label="添加到主屏幕"
      data-testid="install-prompt"
    >
      <div class="install-prompt__icon" aria-hidden="true">📱</div>
      <div class="install-prompt__body">
        <div class="install-prompt__title">添加到主屏幕</div>
        <div class="install-prompt__sub">
          {{ isIOS ? '点击分享按钮，然后选择"添加到主屏幕"' : '更快访问，离线可用' }}
        </div>
      </div>
      <div class="install-prompt__actions">
        <button
          v-if="!isIOS && deferredPrompt"
          type="button"
          class="install-prompt__btn install-prompt__btn--primary"
          data-testid="install-prompt-install"
          @click="handleInstall"
        >
          现在添加
        </button>
        <button
          type="button"
          class="install-prompt__btn install-prompt__btn--ghost"
          data-testid="install-prompt-dismiss"
          @click="handleDismiss"
        >
          {{ isIOS ? '知道了' : '暂不' }}
        </button>
      </div>
    </div>
  </Transition>
</template>

<script setup>
/**
 * InstallPrompt.vue
 *
 * Props:
 *  - deferredPrompt: BeforeInstallPromptEvent | null  (App.vue 监听 beforeinstallprompt 事件后注入)
 *
 * 行为矩阵:
 *  - iOS Safari (standalone=false): 不调 deferredPrompt.prompt() (Safari 不支持),
 *    引导用户手动操作分享菜单
 *  - Android Chrome (standalone=false, deferredPrompt 入参): 调 prompt()
 *  - already installed (standalone=true): 隐藏
 *  - dismissed (localStorage 标记): 隐藏
 *
 * 触发条件 (任一):
 *  - 首次访问 7 天后 (localStorage `install_prompt_first_seen`)
 *  - 累计访问 Drive 路由 ≥ 3 次 (localStorage `install_prompt_drive_visits`)
 *
 * 防骚扰铁律:
 *  - 用户点 "暂不/知道了" 后 30 天内不再提示 (除非 drive 访问 ≥ 3 次重置)
 *  - 已安装 (standalone=true) 永远不提示
 *  - 已 dismiss 后用户可手动重置 (localStorage.removeItem)
 */
import { ref, onMounted, computed, watch } from 'vue'

const props = defineProps({
  deferredPrompt: {
    type: Object,
    default: null,
  },
})

const DISMISS_KEY = 'install_prompt_dismissed_at'
const DISMISS_DURATION_MS = 30 * 24 * 60 * 60 * 1000 // 30 天
const FIRST_SEEN_KEY = 'install_prompt_first_seen'
const FIRST_SEEN_DELAY_MS = 7 * 24 * 60 * 60 * 1000 // 7 天后才提示
const DRIVE_VISITS_KEY = 'install_prompt_drive_visits'
const DRIVE_VISITS_THRESHOLD = 3 // 累计访问 Drive 3 次后才提示

const visible = ref(false)
const isIOS = ref(false)

const isStandalone = computed(() => {
  if (typeof window === 'undefined') return false
  // iOS Safari
  if (window.navigator?.standalone === true) return true
  // 标准 PWA display-mode (Chrome/Edge/Android)
  if (window.matchMedia?.('(display-mode: standalone)').matches) return true
  return false
})

function evaluateVisibility() {
  // 已安装 → 永不显示
  if (isStandalone.value) {
    visible.value = false
    return
  }

  let firstSeen = null
  let dismissedAt = null
  let driveVisits = 0
  try {
    firstSeen = localStorage.getItem(FIRST_SEEN_KEY)
    dismissedAt = localStorage.getItem(DISMISS_KEY)
    driveVisits = Number(localStorage.getItem(DRIVE_VISITS_KEY) || 0)
  } catch (err) {
    // localStorage 不可用 → 不显示
    visible.value = false
    return
  }

  // 记录首次访问 (用于 7 天延迟)
  if (!firstSeen) {
    try {
      localStorage.setItem(FIRST_SEEN_KEY, String(Date.now()))
    } catch (err) {
      // 静默
    }
    return // 首次访问永远不立即提示
  }

  const firstSeenAt = Number(firstSeen)
  const now = Date.now()

  // dismissed 后 30 天内不提示 (除非 drive 访问 ≥ 3 次强制重置)
  if (dismissedAt) {
    const elapsed = now - Number(dismissedAt)
    if (elapsed < DISMISS_DURATION_MS && driveVisits < DRIVE_VISITS_THRESHOLD) {
      visible.value = false
      return
    }
    // 超过 30 天或 drive 访问 ≥ 3 次 → 清除 dismissed 标记
    if (elapsed >= DISMISS_DURATION_MS) {
      try {
        localStorage.removeItem(DISMISS_KEY)
      } catch (err) {
        // 静默
      }
    }
  }

  // 7 天后才提示 (或 drive 访问 ≥ 3 次)
  const elapsedSinceFirst = now - firstSeenAt
  const qualifiesByTime = elapsedSinceFirst >= FIRST_SEEN_DELAY_MS
  const qualifiesByDrive = driveVisits >= DRIVE_VISITS_THRESHOLD

  if (!qualifiesByTime && !qualifiesByDrive) {
    visible.value = false
    return
  }

  // iOS: navigator.standalone 检测 (false → 显示 iOS 手动提示)
  if (isIOS.value && !window.navigator.standalone) {
    visible.value = true
    return
  }

  // Android/Chrome: 有 deferredPrompt 才显示
  if (props.deferredPrompt) {
    visible.value = true
  }
}

// 监听 deferredPrompt prop 变化, 重新评估
watch(
  () => props.deferredPrompt,
  () => evaluateVisibility()
)

/**
 * 增加 Drive 访问计数 (App.vue 可通过 ref 调, 或 router 监听 /drive 路由时调)
 * 触发时机: 用户进入 /drive 路由时调
 */
function recordDriveVisit() {
  try {
    const current = Number(localStorage.getItem(DRIVE_VISITS_KEY) || 0)
    localStorage.setItem(DRIVE_VISITS_KEY, String(current + 1))
  } catch (err) {
    // 静默
  }
  evaluateVisibility()
}

async function handleInstall() {
  if (!props.deferredPrompt) return
  try {
    props.deferredPrompt.prompt()
    const choice = await props.deferredPrompt.userChoice
    if (choice?.outcome === 'accepted') {
      // 用户接受 → 标记 dismissed (避免重复提示)
      try {
        localStorage.setItem(DISMISS_KEY, String(Date.now()))
      } catch (err) {
        // 静默
      }
    }
    visible.value = false
  } catch (err) {
    // prompt() 抛错 → 静默隐藏
    visible.value = false
  }
}

function handleDismiss() {
  try {
    localStorage.setItem(DISMISS_KEY, String(Date.now()))
  } catch (err) {
    // 静默
  }
  visible.value = false
}

onMounted(() => {
  // 检测 iOS (Safari)
  const ua = window.navigator?.userAgent || ''
  isIOS.value = /iPad|iPhone|iPod/.test(ua) && !window.MSStream

  // 初始评估
  evaluateVisibility()
})

// 暴露给 App.vue 调 (通过 ref.recordDriveVisit())
defineExpose({ recordDriveVisit })
</script>

<style scoped>
.install-prompt {
  position: fixed;
  bottom: calc(var(--tabbar-height, 56px) + 12px + var(--sab, 0px));
  left: 12px;
  right: 12px;
  z-index: 5001;
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px 14px;
  background: var(--color-bg-card, #ffffff);
  border: 1px solid var(--color-primary-border, rgba(255, 122, 92, 0.2));
  border-radius: var(--radius-lg, 12px);
  box-shadow: var(--shadow-md, 0 4px 16px rgba(0, 0, 0, 0.08));
  font-size: 14px;
  /* 深色模式跟随 */
  color: var(--color-text-primary, #333);
}

.install-prompt__icon {
  font-size: 28px;
  flex-shrink: 0;
  line-height: 1;
}

.install-prompt__body {
  flex: 1;
  min-width: 0;
}

.install-prompt__title {
  font-weight: var(--font-weight-semibold, 600);
  color: var(--color-text-primary, #333);
  margin-bottom: 2px;
}

.install-prompt__sub {
  font-size: 12px;
  color: var(--color-text-secondary, #666);
  line-height: 1.4;
}

.install-prompt__actions {
  display: flex;
  gap: 6px;
  flex-shrink: 0;
}

.install-prompt__btn {
  border: none;
  background: transparent;
  padding: 6px 12px;
  border-radius: var(--radius-md, 8px);
  font-size: 13px;
  cursor: pointer;
  font-weight: var(--font-weight-medium, 500);
  transition: background var(--duration-fast, 150ms);
}

.install-prompt__btn--primary {
  background: var(--color-primary, #FF7A5C);
  color: var(--el-color-white);
}

.install-prompt__btn--primary:hover {
  background: var(--color-primary-dark, #E85A3A);
}

.install-prompt__btn--ghost {
  color: var(--color-text-secondary, #666);
}

.install-prompt__btn--ghost:hover {
  background: var(--color-primary-bg, #FFF0ED);
}

/* Transition */
.install-prompt-enter-active,
.install-prompt-leave-active {
  transition: transform 0.3s var(--ease-bounce, ease-out), opacity 0.3s;
}

.install-prompt-enter-from,
.install-prompt-leave-to {
  transform: translateY(120%);
  opacity: 0;
}

/* 深色模式 — 非 scoped 块确保跨组件覆盖 */
:global([data-theme='dark']) .install-prompt {
  background: var(--color-bg-card, #1f1f1f);
  border-color: rgba(255, 122, 92, 0.3);
}

:global([data-theme='dark']) .install-prompt__title {
  color: var(--color-text-primary, #f0f0f0);
}

:global([data-theme='dark']) .install-prompt__sub {
  color: var(--color-text-secondary, #a0a0a0);
}
</style>