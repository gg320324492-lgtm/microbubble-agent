import { describe, it, expect } from 'vitest'
import { nextTick } from 'vue'

/**
 * W83 B-2 P1-2: useViewport 单元测试
 *
 * 派工依据:
 * - W82 A-2 Survey 3 §6 P1: useIsMobile.js + useResponsive.js BREAKPOINTS 重复
 * - W83 B-2 P1-2 派工: 收敛为单一 viewport store
 * - 统一断点 (3 段): mobile < 768 / tablet 768-1023 / desktop >= 1024
 *   派工 v6 段 5 推荐 3 段 (W82 A-2 Survey 3 §6 P1)
 *
 * 兼容层 (thin-shell 委派):
 * - useIsMobile.js 保留 4 档 bp 命名 (xs/sm/md/lg) 与 isMobile (w<1024) 兼容
 * - useResponsive.js 保留 4 档 bp 命名 (sm/md/lg/xl) 与 isMobile (w<1024) 兼容
 *
 * 策略:
 * - 直接修改 useViewportRef() 内部 ref.value, 触发 Vue reactivity 重新计算
 * - 因为 useViewport 是单例 + 多个 setup 调用, computed 缓存可能在测试间共享
 * - 每个测试后强制 nextTick 确保依赖追踪刷新
 */

describe('useViewport (P1-2 统一 viewport store)', () => {
  async function setupWithViewport(width, height = 800, dpr = 1) {
    // 动态 import 确保拿到单例 ref
    const mod = await import('../useViewport')
    Object.defineProperty(window, 'innerWidth', { value: width, writable: true, configurable: true })
    Object.defineProperty(window, 'innerHeight', { value: height, writable: true, configurable: true })
    Object.defineProperty(window, 'devicePixelRatio', { value: dpr, writable: true, configurable: true })
    // 直接修改单例 ref.value
    mod.useViewportRef().value = { width, height, dpr }
    await nextTick()
    return mod
  }

  describe('BREAKPOINTS', () => {
    it('BREAKPOINTS export 3 段 (mobile/tablet/desktop)', async () => {
      const { BREAKPOINTS } = await import('../useViewport')
      expect(BREAKPOINTS.mobile).toBe(768)
      expect(BREAKPOINTS.tablet).toBe(1024)
      expect(BREAKPOINTS.desktop).toBe(1280)
    })

    it('BREAKPOINTS 是 Object.freeze 不可变', async () => {
      const { BREAKPOINTS } = await import('../useViewport')
      expect(() => {
        BREAKPOINTS.mobile = 1000
      }).toThrow()
    })
  })

  describe('useViewport() 3 段断点响应', () => {
    it('innerWidth < 768: isMobile=true, isTablet=false, isDesktop=false', async () => {
      const { useViewport } = await setupWithViewport(500)
      const { isMobile, isTablet, isDesktop } = useViewport()
      expect(isMobile.value).toBe(true)
      expect(isTablet.value).toBe(false)
      expect(isDesktop.value).toBe(false)
    })

    it('innerWidth 768-1023: isMobile=true (< 1024), isTablet=false (3 段: 1024-1280)', async () => {
      const { useViewport } = await setupWithViewport(900)
      const { isMobile, isTablet, isDesktop } = useViewport()
      expect(isMobile.value).toBe(true)  // 900 < 1024
      expect(isTablet.value).toBe(false)  // 3 段: 1024-1280 = tablet, 900 不在内
      expect(isDesktop.value).toBe(false)
    })

    it('innerWidth >= 1024: isMobile=false, isDesktop=true', async () => {
      const { useViewport } = await setupWithViewport(1280)
      const { isMobile, isTablet, isDesktop } = useViewport()
      expect(isMobile.value).toBe(false)
      expect(isDesktop.value).toBe(true)
    })

    it('innerWidth 1024-1279: isTablet=true (3 段: 1024-1280), isDesktop=false', async () => {
      const { useViewport } = await setupWithViewport(1100)
      const { isMobile, isTablet, isDesktop, bp } = useViewport()
      expect(bp.value).toBe('tablet')  // 3 段: 1024-1280 = tablet (W83 B-2 派工决定, 1024 仍归 tablet)
      expect(isMobile.value).toBe(false)  // 1100 >= 1024
      expect(isTablet.value).toBe(true)  // 3 段: 1024-1280 = tablet
      expect(isDesktop.value).toBe(false)  // 1100 < 1280
    })
  })

  describe('bp 断点字符串', () => {
    it('500 -> mobile', async () => {
      const { useViewport } = await setupWithViewport(500)
      expect(useViewport().bp.value).toBe('mobile')
    })

    it('800 -> tablet', async () => {
      const { useViewport } = await setupWithViewport(800)
      expect(useViewport().bp.value).toBe('tablet')
    })

    it('1023 -> tablet (边界, 768-1279 全 tablet)', async () => {
      const { useViewport } = await setupWithViewport(1023)
      expect(useViewport().bp.value).toBe('tablet')
    })

    it('1024 -> tablet (3 段: 1024-1279 = tablet)', async () => {
      const { useViewport } = await setupWithViewport(1024)
      expect(useViewport().bp.value).toBe('tablet')
    })

    it('1100 -> tablet', async () => {
      const { useViewport } = await setupWithViewport(1100)
      expect(useViewport().bp.value).toBe('tablet')
    })

    it('1279 -> tablet (边界)', async () => {
      const { useViewport } = await setupWithViewport(1279)
      expect(useViewport().bp.value).toBe('tablet')
    })

    it('1280 -> desktop (3 段: >= 1280)', async () => {
      const { useViewport } = await setupWithViewport(1280)
      expect(useViewport().bp.value).toBe('desktop')
    })

    it('1500 -> desktop', async () => {
      const { useViewport } = await setupWithViewport(1500)
      expect(useViewport().bp.value).toBe('desktop')
    })
  })

  describe('方向 + DPR', () => {
    it('isPortrait 在宽 < 高时为 true', async () => {
      const { useViewport } = await setupWithViewport(375, 812)
      const { isPortrait, isLandscape } = useViewport()
      expect(isPortrait.value).toBe(true)
      expect(isLandscape.value).toBe(false)
    })

    it('isLandscape 在宽 > 高时为 true', async () => {
      const { useViewport } = await setupWithViewport(1024, 768)
      const { isPortrait, isLandscape } = useViewport()
      expect(isPortrait.value).toBe(false)
      expect(isLandscape.value).toBe(true)
    })

    it('isRetina 在 dpr >= 2 时为 true', async () => {
      const { useViewport } = await setupWithViewport(500, 800, 2)
      const { isRetina } = useViewport()
      expect(isRetina.value).toBe(true)
    })

    it('isRetina 在 dpr < 2 时为 false', async () => {
      const { useViewport } = await setupWithViewport(500, 800, 1)
      const { isRetina } = useViewport()
      expect(isRetina.value).toBe(false)
    })

    it('dpr 返回 devicePixelRatio', async () => {
      const { useViewport } = await setupWithViewport(500)
      const { dpr } = useViewport()
      expect(dpr.value).toBeGreaterThan(0)
    })
  })

  describe('useViewportRef() 单例共享', () => {
    it('多次 useViewport() 调用共享同一份 viewport 状态', async () => {
      const mod = await setupWithViewport(700)
      const v1 = mod.useViewport()
      const v2 = mod.useViewport()
      expect(v1.width.value).toBe(700)
      expect(v2.width.value).toBe(700)
      expect(v1.width.value).toBe(v2.width.value)
    })

    it('外部修改 useViewportRef().value 触发 reactivity', async () => {
      const mod = await setupWithViewport(700)
      const { isMobile } = mod.useViewport()
      expect(isMobile.value).toBe(true)

      // 修改单例 ref
      mod.useViewportRef().value = { width: 1500, height: 800, dpr: 1 }
      await nextTick()
      expect(isMobile.value).toBe(false)
    })
  })

  describe('refreshViewport() 手动刷新', () => {
    it('refreshViewport() 调用 updateViewport 不抛错', async () => {
      const { refreshViewport } = await import('../useViewport')
      expect(() => refreshViewport()).not.toThrow()
    })
  })

  describe('useIsMobile.js 兼容 (thin-shell 委派, 4 档 bp 命名)', () => {
    it('useIsMobile 500: isMobile=true, isMobileXS=true, 老 bp 命名 xs', async () => {
      const mod = await import('../useIsMobile')
      Object.defineProperty(window, 'innerWidth', { value: 500, writable: true, configurable: true })
      Object.defineProperty(window, 'innerHeight', { value: 800, writable: true, configurable: true })
      mod.useViewportRef().value = { width: 500, height: 800, dpr: 1 }
      await nextTick()
      const { isMobile, isMobileXS, isTablet, isDesktop, bp } = mod.useIsMobile()
      expect(isMobile.value).toBe(true)
      expect(isMobileXS.value).toBe(true)
      expect(isTablet.value).toBe(false)
      expect(isDesktop.value).toBe(false)
      expect(bp.value).toBe('xs')  // 老 ALS 4 档命名
    })

    it('useIsMobile 800: 老 bp 命名 sm', async () => {
      const mod = await import('../useIsMobile')
      Object.defineProperty(window, 'innerWidth', { value: 800, writable: true, configurable: true })
      Object.defineProperty(window, 'innerHeight', { value: 800, writable: true, configurable: true })
      mod.useViewportRef().value = { width: 800, height: 800, dpr: 1 }
      await nextTick()
      const { bp } = mod.useIsMobile()
      expect(bp.value).toBe('sm')
    })

    it('useIsMobile 1100: 老 bp 命名 md, isMobile=false (useViewport 3 段)', async () => {
      const mod = await import('../useIsMobile')
      Object.defineProperty(window, 'innerWidth', { value: 1100, writable: true, configurable: true })
      Object.defineProperty(window, 'innerHeight', { value: 800, writable: true, configurable: true })
      mod.useViewportRef().value = { width: 1100, height: 800, dpr: 1 }
      await nextTick()
      const { isMobile, isTablet, isDesktop, bp } = mod.useIsMobile()
      expect(bp.value).toBe('md')
      // 1100 >= 1024 → isMobile = false (useViewport 3 段语义)
      expect(isMobile.value).toBe(false)
      expect(isTablet.value).toBe(true)  // 1024-1280
      expect(isDesktop.value).toBe(false)
    })

    it('useIsMobile 1500: 老 bp 命名 lg, isDesktop=true', async () => {
      const mod = await import('../useIsMobile')
      Object.defineProperty(window, 'innerWidth', { value: 1500, writable: true, configurable: true })
      Object.defineProperty(window, 'innerHeight', { value: 800, writable: true, configurable: true })
      mod.useViewportRef().value = { width: 1500, height: 800, dpr: 1 }
      await nextTick()
      const { isMobile, isDesktop, bp } = mod.useIsMobile()
      expect(bp.value).toBe('lg')
      expect(isDesktop.value).toBe(true)
    })
  })

  describe('useResponsive.js 兼容 (thin-shell 委派, 4 档 bp 命名)', () => {
    it('useResponsive 400: isMobile=true, 老 bp 命名 sm', async () => {
      const mod = await import('../useResponsive')
      Object.defineProperty(window, 'innerWidth', { value: 400, writable: true, configurable: true })
      Object.defineProperty(window, 'innerHeight', { value: 800, writable: true, configurable: true })
      mod.useViewportRef().value = { width: 400, height: 800, dpr: 1 }
      await nextTick()
      const { isMobile, isPortrait, isLandscape, isRetina, bp } = mod.useResponsive()
      expect(isMobile.value).toBe(true)
      expect(isPortrait.value).toBe(true)
      expect(isLandscape.value).toBe(false)
      expect(isRetina.value).toBe(false)
      expect(bp.value).toBe('sm')  // 老 ALS 4 档命名
    })

    it('useResponsive 800: 老 bp 命名 md', async () => {
      const mod = await import('../useResponsive')
      Object.defineProperty(window, 'innerWidth', { value: 800, writable: true, configurable: true })
      Object.defineProperty(window, 'innerHeight', { value: 800, writable: true, configurable: true })
      mod.useViewportRef().value = { width: 800, height: 800, dpr: 1 }
      await nextTick()
      const { bp, isMobile, isTablet } = mod.useResponsive()
      expect(bp.value).toBe('md')
      expect(isMobile.value).toBe(true)  // 老 isMobile = w < 1024
      expect(isTablet.value).toBe(true)  // 768-1023
    })

    it('useResponsive 1279: 老 bp 命名 lg, isDesktop=true, isTablet=false', async () => {
      const mod = await import('../useResponsive')
      Object.defineProperty(window, 'innerWidth', { value: 1279, writable: true, configurable: true })
      Object.defineProperty(window, 'innerHeight', { value: 800, writable: true, configurable: true })
      mod.useViewportRef().value = { width: 1279, height: 800, dpr: 1 }
      await nextTick()
      const { bp, isTablet, isDesktop } = mod.useResponsive()
      expect(bp.value).toBe('lg')
      expect(isTablet.value).toBe(false)  // 老 isTablet = 768-1023
      expect(isDesktop.value).toBe(true)  // 老 isDesktop >= 1024
    })

    it('useResponsive 1280: 老 bp 命名 xl, isDesktop=true', async () => {
      const mod = await import('../useResponsive')
      Object.defineProperty(window, 'innerWidth', { value: 1280, writable: true, configurable: true })
      Object.defineProperty(window, 'innerHeight', { value: 800, writable: true, configurable: true })
      mod.useViewportRef().value = { width: 1280, height: 800, dpr: 1 }
      await nextTick()
      const { bp, isDesktop } = mod.useResponsive()
      expect(bp.value).toBe('xl')
      expect(isDesktop.value).toBe(true)
    })

    it('useResponsive 1500: 老 bp 命名 xl', async () => {
      const mod = await import('../useResponsive')
      Object.defineProperty(window, 'innerWidth', { value: 1500, writable: true, configurable: true })
      Object.defineProperty(window, 'innerHeight', { value: 800, writable: true, configurable: true })
      mod.useViewportRef().value = { width: 1500, height: 800, dpr: 1 }
      await nextTick()
      const { bp } = mod.useResponsive()
      expect(bp.value).toBe('xl')
    })
  })
})
