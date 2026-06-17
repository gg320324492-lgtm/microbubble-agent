/**
 * useKeyboardInset.ts — 软键盘高度适配（visualViewport）
 *
 * PR #3: MobileChatView 输入框贴底时，软键盘弹起需要：
 * 1. 计算 keyboardHeight = window.innerHeight - visualViewport.height
 * 2. 输入栏 padding-bottom 动态设为 keyboardHeight
 * 3. 消息区 scroll 到底部时考虑 keyboardHeight 偏移
 *
 * 全局单例：所有 useKeyboardInset() 调用共享状态。
 */

import { ref, computed, onMounted, onUnmounted } from 'vue'

const state = ref({
  visualHeight: typeof window !== 'undefined' ? window.innerHeight : 720,
  keyboardHeight: 0,
})

let initialized = false
let timer = null

function update() {
  if (typeof window === 'undefined') return
  const vv = window.visualViewport
  if (!vv) {
    state.value = { visualHeight: window.innerHeight, keyboardHeight: 0 }
    return
  }
  // 键盘高度 = 窗口总高度 - visualViewport 高度
  // iOS Safari：vv.height 在键盘弹起时缩小，差值即为键盘高度
  const keyboardHeight = Math.max(0, window.innerHeight - vv.height)
  state.value = {
    visualHeight: vv.height,
    keyboardHeight,
  }
}

function onResize() {
  if (timer) clearTimeout(timer)
  timer = setTimeout(update, 50)
}

function attach() {
  if (initialized || typeof window === 'undefined') return
  initialized = true
  if (window.visualViewport) {
    update()
    window.visualViewport.addEventListener('resize', onResize)
    window.visualViewport.addEventListener('scroll', onResize)
  }
}

export function useKeyboardInset() {
  attach()

  onUnmounted(() => {
    // 全局单例，不在 unmounted 时 detach
  })

  const visualHeight = computed(() => state.value.visualHeight)
  const keyboardHeight = computed(() => state.value.keyboardHeight)
  const isKeyboardOpen = computed(() => state.value.keyboardHeight > 100)

  /** 输入栏需要的 padding-bottom（含 safe-area） */
  const inputPaddingBottom = computed(
    () => `calc(${keyboardHeight.value}px + var(--sab, 0px))`
  )

  /** 消息区需要的 padding-bottom（输入栏 72px + TabBar 56px + 键盘 + safe-area）
      输入栏现在浮在 TabBar 上方（bottom: var(--tabbar-height)），所以消息区要把
      两个高度都留出来，否则最后几条消息会被输入栏盖住 */
  const messagesPaddingBottom = computed(
    () => `calc(72px + var(--tabbar-height, 56px) + ${keyboardHeight.value}px + var(--sab, 0px))`
  )

  return {
    visualHeight,
    keyboardHeight,
    isKeyboardOpen,
    inputPaddingBottom,
    messagesPaddingBottom,
  }
}

export default useKeyboardInset