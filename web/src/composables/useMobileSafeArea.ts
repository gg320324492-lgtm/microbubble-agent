import { ref, computed, onMounted, onBeforeUnmount } from 'vue'

/**
 * useMobileSafeArea — iOS Safari / Android PWA 安全区 + 刘海/灵动岛适配
 *
 * 在 `useSafeArea.js`（只读 CSS 变量 --sat/--sar/--sab/--sal）基础上扩展：
 *  1. 响应式追踪安全区 inset（orientationchange / resize 时重新读取）
 *  2. 横竖屏切换状态（portrait / landscape）
 *  3. notch / dynamic island 检测（顶部 inset 明显大于 0 → 判定有刘海）
 *
 * CSS 变量来源（variables.css:183-186）：
 *   --sat: env(safe-area-inset-top, 0px)
 *   --sar: env(safe-area-inset-right, 0px)
 *   --sab: env(safe-area-inset-bottom, 0px)
 *   --sal: env(safe-area-inset-left, 0px)
 *
 * ⚠️ iOS Safari 铁律：
 *  - env(safe-area-inset-*) 只有在 <meta viewport content="...viewport-fit=cover"> 时才非 0
 *  - 横屏时刘海在左/右 → --sal / --sar 变大；--sat 反而可能变小
 *  - orientationchange 事件触发时 innerWidth/Height 有延迟 → 需 setTimeout 二次确认
 *  - env() 在 getComputedStyle 里读到的是**计算后**的具体像素值（如 "47px"），可直接 parseFloat
 *
 * 用法：
 *   const { top, bottom, hasNotch, isLandscape, insetStyle } = useMobileSafeArea()
 *   <div :style="insetStyle"> ... </div>
 */

interface SafeAreaInset {
  top: number
  right: number
  bottom: number
  left: number
}

function pxToNumber(value: string): number {
  const n = parseFloat(value)
  return Number.isFinite(n) ? n : 0
}

function readInset(): SafeAreaInset {
  if (typeof window === 'undefined' || typeof document === 'undefined') {
    return { top: 0, right: 0, bottom: 0, left: 0 }
  }
  const style = getComputedStyle(document.documentElement)
  return {
    top: pxToNumber(style.getPropertyValue('--sat')),
    right: pxToNumber(style.getPropertyValue('--sar')),
    bottom: pxToNumber(style.getPropertyValue('--sab')),
    left: pxToNumber(style.getPropertyValue('--sal')),
  }
}

function readIsLandscape(): boolean {
  if (typeof window === 'undefined') return false
  // 优先用 matchMedia（比 innerWidth/Height 更早稳定），fallback 到尺寸对比
  if (typeof window.matchMedia === 'function') {
    return window.matchMedia('(orientation: landscape)').matches
  }
  return window.innerWidth > window.innerHeight
}

export function useMobileSafeArea() {
  const inset = ref<SafeAreaInset>(readInset())
  const landscape = ref<boolean>(readIsLandscape())

  const top = computed(() => `${inset.value.top}px`)
  const right = computed(() => `${inset.value.right}px`)
  const bottom = computed(() => `${inset.value.bottom}px`)
  const left = computed(() => `${inset.value.left}px`)

  // 刘海 / 灵动岛检测：竖屏顶部 inset ≥ 20px（iPhone X+ 通常 44-59px，普通 SE 为 0/20）
  // 横屏时刘海在侧边 → 判断 left/right inset
  const hasNotch = computed(() => {
    const i = inset.value
    if (landscape.value) return i.left >= 20 || i.right >= 20
    return i.top >= 24
  })

  // 灵动岛（Dynamic Island）：顶部 inset 通常 ≥ 54px（14 Pro 起 59px）
  const hasDynamicIsland = computed(() => !landscape.value && inset.value.top >= 54)

  const isLandscape = computed(() => landscape.value)
  const isPortrait = computed(() => !landscape.value)

  // 一次性 padding 样式（含横竖屏自动切换）
  const insetStyle = computed(() => ({
    paddingTop: top.value,
    paddingRight: right.value,
    paddingBottom: bottom.value,
    paddingLeft: left.value,
  }))

  const inset4 = computed(
    () => `${top.value} ${right.value} ${bottom.value} ${left.value}`
  )

  function refresh() {
    inset.value = readInset()
    landscape.value = readIsLandscape()
  }

  // orientationchange 后 env() 值有延迟，二次确认
  let orientationTimer: ReturnType<typeof setTimeout> | null = null
  function onOrientationChange() {
    refresh()
    if (orientationTimer) clearTimeout(orientationTimer)
    orientationTimer = setTimeout(refresh, 300)
  }

  let resizeTimer: ReturnType<typeof setTimeout> | null = null
  function onResize() {
    if (resizeTimer) clearTimeout(resizeTimer)
    resizeTimer = setTimeout(refresh, 100)
  }

  onMounted(() => {
    if (typeof window === 'undefined') return
    refresh()
    window.addEventListener('orientationchange', onOrientationChange)
    window.addEventListener('resize', onResize, { passive: true })
  })

  onBeforeUnmount(() => {
    if (typeof window === 'undefined') return
    window.removeEventListener('orientationchange', onOrientationChange)
    window.removeEventListener('resize', onResize)
    if (orientationTimer) clearTimeout(orientationTimer)
    if (resizeTimer) clearTimeout(resizeTimer)
  })

  return {
    // 原始像素值（number）
    inset,
    // px 字符串（computed）
    top,
    right,
    bottom,
    left,
    inset4,
    insetStyle,
    // 状态
    hasNotch,
    hasDynamicIsland,
    isLandscape,
    isPortrait,
    // 手动刷新
    refresh,
  }
}

export default useMobileSafeArea
