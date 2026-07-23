import { ref, computed, onMounted, onBeforeUnmount } from 'vue'

/**
 * useMobileKeyboard — 移动端软键盘弹出适配（iOS Safari + Android Chrome）
 *
 * 解决两大痛点：
 *  1. iOS Safari `100vh` 不随键盘缩小 → 底部输入框被键盘遮挡
 *     修法：优先用 `100dvh`（dynamic viewport height），并用 visualViewport API
 *     实时读取键盘弹出后的真实可视高度，通过 --kb-vh 变量暴露给 CSS
 *  2. Android Chrome 键盘弹出会 resize window（改变 innerHeight）→ 需区分
 *     真实键盘弹出 vs 地址栏收缩
 *
 * ⚠️ iOS Safari 铁律：
 *  - iOS Safari 键盘弹出时 **不** 改变 window.innerHeight（视口"上推"而非缩小）
 *    → 必须用 `window.visualViewport.height` 才能拿到真实可视高度
 *  - visualViewport.height < window.innerHeight 差值 = 键盘高度（阈值 150px 过滤误报）
 *  - focus 后需 scrollIntoView，否则输入框可能在键盘下方
 *  - 100vh → 100dvh 已在 mobile-base.css / variables.css 用 @supports 兜底
 *
 * ⚠️ Android Chrome：
 *  - 键盘弹出**会** resize（innerHeight 变小）→ visualViewport 同样可用
 *  - `interactive-widget=resizes-content`（meta viewport）可让布局自动适配，但
 *    老版本不支持 → 仍需 JS 兜底
 *
 * 用法：
 *   const { keyboardHeight, isKeyboardOpen, viewportHeight, ensureVisible } = useMobileKeyboard()
 *   watch(isKeyboardOpen, (open) => { if (open) scrollToBottom() })
 *   // 输入框 focus 时：
 *   <input @focus="(e) => ensureVisible(e.target)" />
 */

// 键盘判定阈值：可视高度收缩超过此值才认为键盘弹出（过滤地址栏收缩等小抖动）
const KEYBOARD_THRESHOLD_PX = 150

function getVisualViewportHeight(): number {
  if (typeof window === 'undefined') return 0
  if (window.visualViewport) return window.visualViewport.height
  return window.innerHeight
}

function getLayoutViewportHeight(): number {
  if (typeof window === 'undefined') return 0
  return window.innerHeight
}

export function useMobileKeyboard() {
  const viewportHeight = ref<number>(getVisualViewportHeight())
  const layoutHeight = ref<number>(getLayoutViewportHeight())

  // 键盘高度 = 布局视口 - 可视视口（收缩量）
  const keyboardHeight = computed(() => {
    const diff = layoutHeight.value - viewportHeight.value
    return diff > 0 ? diff : 0
  })

  const isKeyboardOpen = computed(() => keyboardHeight.value >= KEYBOARD_THRESHOLD_PX)

  function syncCssVar() {
    if (typeof document === 'undefined') return
    const root = document.documentElement
    // 键盘弹出后真实可视高度（px）→ 组件可用 height: var(--kb-vh) 替代 100vh
    root.style.setProperty('--kb-vh', `${viewportHeight.value}px`)
    root.style.setProperty('--kb-height', `${keyboardHeight.value}px`)
  }

  function update() {
    viewportHeight.value = getVisualViewportHeight()
    layoutHeight.value = getLayoutViewportHeight()
    syncCssVar()
  }

  // visualViewport resize/scroll 在键盘弹出/收起、地址栏伸缩时都会触发
  let rafId: number | null = null
  function onViewportChange() {
    // rAF 合并高频事件（iOS 键盘动画期间会连发多次）
    if (rafId != null) return
    rafId = requestAnimationFrame(() => {
      rafId = null
      update()
    })
  }

  /**
   * 确保元素在键盘上方可见。
   * iOS Safari focus 后视口"上推"但输入框可能仍被遮挡 → 延迟 scrollIntoView。
   */
  function ensureVisible(el?: HTMLElement | null) {
    const target = el || (typeof document !== 'undefined'
      ? (document.activeElement as HTMLElement | null)
      : null)
    if (!target || typeof target.scrollIntoView !== 'function') return
    // 键盘动画约 250-300ms，延迟后再滚动才准确
    setTimeout(() => {
      try {
        target.scrollIntoView({ block: 'center', behavior: 'smooth' })
      } catch {
        target.scrollIntoView(false)
      }
    }, 300)
  }

  onMounted(() => {
    if (typeof window === 'undefined') return
    update()
    if (window.visualViewport) {
      window.visualViewport.addEventListener('resize', onViewportChange)
      window.visualViewport.addEventListener('scroll', onViewportChange)
    }
    // Android Chrome 兜底：无 visualViewport 时用 window.resize
    window.addEventListener('resize', onViewportChange, { passive: true })
  })

  onBeforeUnmount(() => {
    if (typeof window === 'undefined') return
    if (window.visualViewport) {
      window.visualViewport.removeEventListener('resize', onViewportChange)
      window.visualViewport.removeEventListener('scroll', onViewportChange)
    }
    window.removeEventListener('resize', onViewportChange)
    if (rafId != null) cancelAnimationFrame(rafId)
    // 清理 CSS 变量，避免遗留影响其它页面
    if (typeof document !== 'undefined') {
      document.documentElement.style.removeProperty('--kb-vh')
      document.documentElement.style.removeProperty('--kb-height')
    }
  })

  return {
    viewportHeight,
    layoutHeight,
    keyboardHeight,
    isKeyboardOpen,
    ensureVisible,
    update,
  }
}

export default useMobileKeyboard
