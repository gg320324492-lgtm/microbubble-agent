import { ref, computed, onMounted, onUnmounted } from 'vue'

/**
 * 视口与键盘高度 composable
 *
 * 主要解决两个移动端痛点：
 * 1. iOS Safari 100vh 不准（地址栏遮挡） → 用 visualViewport.height
 * 2. 软键盘弹起时输入框被遮挡 → 计算 keyboardHeight = window.innerHeight - visualViewport.height
 *
 * 用法：
 *   const { vh, keyboardHeight } = useViewport()
 *   :style="{ height: vh, paddingBottom: keyboardHeight + 'px' }"
 */

// 全局单例
const viewportState = ref({
  visualHeight: typeof window !== 'undefined' ? window.innerHeight : 720,
  visualWidth: typeof window !== 'undefined' ? window.innerWidth : 1280,
  layoutHeight: typeof window !== 'undefined' ? window.innerHeight : 720,
  keyboardHeight: 0,
  dpr: typeof window !== 'undefined' ? window.devicePixelRatio || 1 : 1,
})

let initialized = false
let resizeTimer = null

function update() {
  if (typeof window === 'undefined' || !window.visualViewport) return
  const vv = window.visualViewport
  viewportState.value = {
    visualHeight: vv.height,
    visualWidth: vv.width,
    layoutHeight: window.innerHeight,
    keyboardHeight: Math.max(0, window.innerHeight - vv.height),
    dpr: window.devicePixelRatio || 1,
  }
}

function onVisualResize() {
  if (resizeTimer) clearTimeout(resizeTimer)
  resizeTimer = setTimeout(update, 50)
}

function attach() {
  if (initialized || typeof window === 'undefined') return
  initialized = true
  if (window.visualViewport) {
    update()
    window.visualViewport.addEventListener('resize', onVisualResize)
    window.visualViewport.addEventListener('scroll', onVisualResize)
  }
  window.addEventListener('resize', onVisualResize, { passive: true })
}

function detach() {
  if (typeof window === 'undefined') return
  if (window.visualViewport) {
    window.visualViewport.removeEventListener('resize', onVisualResize)
    window.visualViewport.removeEventListener('scroll', onVisualResize)
  }
  window.removeEventListener('resize', onVisualResize)
  initialized = false
}

export function useViewport() {
  attach()

  onUnmounted(() => {
    // 全局单例，不在 unmounted 时 detach
  })

  const vh = computed(() => `${viewportState.value.visualHeight}px`)
  const dvh = computed(() => `${viewportState.value.visualHeight}px`) // 100dvh fallback

  const visualHeight = computed(() => viewportState.value.visualHeight)
  const visualWidth = computed(() => viewportState.value.visualWidth)
  const layoutHeight = computed(() => viewportState.value.layoutHeight)
  const keyboardHeight = computed(() => viewportState.value.keyboardHeight)
  const dpr = computed(() => viewportState.value.dpr)

  const isKeyboardOpen = computed(() => viewportState.value.keyboardHeight > 100)

  return {
    vh,
    dvh,
    visualHeight,
    visualWidth,
    layoutHeight,
    keyboardHeight,
    dpr,
    isKeyboardOpen,
  }
}

// 卸载 hook（用于测试 / 极端清理）
export function disposeViewport() {
  detach()
}

export default useViewport