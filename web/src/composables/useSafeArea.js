import { computed } from 'vue'

/**
 * Safe Area 安全区适配 composable
 *
 * iPhone X+ 全面屏、刘海/灵动岛、底部 Home Indicator 需要 env(safe-area-inset-*) 适配。
 * 实际值在 variables.css 中通过 CSS 变量暴露：
 *   --sat (top)
 *   --sar (right)
 *   --sab (bottom)
 *   --sal (left)
 *
 * 用法：
 *   const { top, bottom, left, right } = useSafeArea()
 *   :style="{ paddingTop: top, paddingBottom: bottom }"
 */

function readCssVar(name) {
  if (typeof window === 'undefined' || typeof document === 'undefined') return '0px'
  return getComputedStyle(document.documentElement).getPropertyValue(name).trim() || '0px'
}

export function useSafeArea() {
  const top = computed(() => readCssVar('--sat'))
  const right = computed(() => readCssVar('--sar'))
  const bottom = computed(() => readCssVar('--sab'))
  const left = computed(() => readCssVar('--sal'))

  // 整组 inset（用于一次性设置 padding）
  const inset = computed(
    () => `${top.value} ${right.value} ${bottom.value} ${left.value}`
  )

  return {
    top,
    right,
    bottom,
    left,
    inset,
  }
}

export default useSafeArea