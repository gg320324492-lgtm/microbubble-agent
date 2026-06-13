import { describe, it, expect, vi } from 'vitest'
import { nextTick } from 'vue'

/**
 * PR #10: useIsMobile 单元测试
 *
 * 策略：直接修改 useViewportRef() 内部 ref.value，触发 Vue reactivity 重新计算。
 * 因为 useIsMobile 是单例 + 多个 setup 调用，computed 缓存可能在测试间共享，
 * 所以每个测试后强制 nextTick 确保依赖追踪刷新。
 */

describe('useIsMobile', () => {
  async function setupWithViewport(width, height = 800) {
    // 动态 import 确保拿到单例 ref
    const mod = await import('../useIsMobile')
    Object.defineProperty(window, 'innerWidth', { value: width, writable: true, configurable: true })
    Object.defineProperty(window, 'innerHeight', { value: height, writable: true, configurable: true })
    // 直接修改单例 ref.value
    mod.useViewportRef().value = { width, height, dpr: 1 }
    await nextTick()
    return mod
  }

  it('innerWidth < 768 时 isMobile 和 isMobileXS 为 true', async () => {
    const { useIsMobile } = await setupWithViewport(500)
    const { isMobile, isMobileXS } = useIsMobile()
    expect(isMobile.value).toBe(true)
    expect(isMobileXS.value).toBe(true)
  })

  it('innerWidth >= 1024 时 isDesktop 为 true', async () => {
    const { useIsMobile } = await setupWithViewport(1280)
    const { isMobile, isMobileXS, isDesktop } = useIsMobile()
    expect(isMobile.value).toBe(false)
    expect(isMobileXS.value).toBe(false)
    expect(isDesktop.value).toBe(true)
  })

  it('innerWidth 在 1024-1280 之间为 tablet（iPad 横屏）', async () => {
    // BP = { xs: 480, sm: 768, md: 1024, lg: 1280 }
    // isMobile = w < BP.md = w < 1024
    // isTablet = w >= BP.md && w < BP.lg = 1024 <= w < 1280
    // 1100 在 tablet 范围，isMobile = false (因为 1100 >= 1024)
    const mod = await setupWithViewport(1100)
    const { isMobile, isMobileXS, isTablet, isDesktop, bp } = mod.useIsMobile()
    expect(bp.value).toBe('md')
    expect(isMobile.value).toBe(false) // 1100 >= 1024 不算 mobile
    expect(isMobileXS.value).toBe(false) // 1100 >= 768 不算 xs
    expect(isTablet.value).toBe(true) // 1024 <= 1100 < 1280
    expect(isDesktop.value).toBe(false) // 1100 < 1280 不算 desktop
  })

  it('isPortrait 在宽 < 高时为 true', async () => {
    const { useIsMobile } = await setupWithViewport(375, 812)
    const { isPortrait } = useIsMobile()
    expect(isPortrait.value).toBe(true)
  })

  it('bp 返回正确的断点名', async () => {
    const mod1 = await setupWithViewport(400)
    expect(mod1.useIsMobile().bp.value).toBe('xs')

    const mod2 = await setupWithViewport(800)
    expect(mod2.useIsMobile().bp.value).toBe('sm')

    const mod3 = await setupWithViewport(1100)
    expect(mod3.useIsMobile().bp.value).toBe('md')

    const mod4 = await setupWithViewport(1500)
    expect(mod4.useIsMobile().bp.value).toBe('lg')
  })

  it('dpr 返回 devicePixelRatio', async () => {
    const { useIsMobile } = await setupWithViewport(500)
    const { dpr } = useIsMobile()
    expect(dpr.value).toBeGreaterThan(0)
  })
})