import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { ref, nextTick, defineComponent, h } from 'vue'
import { mount } from '@vue/test-utils'
import { useVirtualList } from '../useVirtualList'

/**
 * W100 +45 P3-VIRTUAL RETRY 性能测试
 *
 * 派工 v11 §9 硬门禁: 1000 消息场景下, 虚拟列表只渲染可见窗口内的元素,
 * 数量显著小于 1000 (派工 brief "≥ 30fps" 等价于"DOM 节点数远小于 total").
 *
 * jsdom 测不了真实 fps, 但能验证:
 * 1. 1000 元素 totalHeight = 1000 * itemHeight
 * 2. 1000 元素 isVirtualized = true
 * 3. 1000 元素 visibleItems.length << 1000 (典型 ~10-20)
 * 4. 滚动到中段时 visibleItems 包含正确 wendow
 */
describe('useVirtualList 1000 消息性能', () => {
  beforeEach(() => {
    const existedRO = (globalThis as any).ResizeObserver
    if (!existedRO) {
      ;(globalThis as any).ResizeObserver = class {
        observe() {}
        unobserve() {}
        disconnect() {}
      }
    }
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('1000 消息 totalHeight = 1000 * itemHeight', () => {
    const items = ref(Array.from({ length: 1000 }, (_, i) => `msg-${i}`))
    const containerRef = ref<HTMLElement | null>(null)
    const Host = defineComponent({
      setup() {
        const v = useVirtualList({ items, containerRef, itemHeight: 60, threshold: 50 })
        ;(globalThis as any).__v = v
        return () => h('div')
      },
    })
    const wrapper = mount(Host, { attachTo: document.body })
    const v: any = (globalThis as any).__v

    expect(v.totalHeight.value).toBe(60000)
    expect(v.isVirtualized.value).toBe(true)

    wrapper.unmount()
  })

  it('1000 消息 + viewport=600 时 visibleItems.length ≤ 25 (含 overscan)', () => {
    const items = ref(Array.from({ length: 1000 }, (_, i) => `msg-${i}`))
    const containerRef = ref<HTMLElement | null>(null)
    const Host = defineComponent({
      setup() {
        const v = useVirtualList({ items, containerRef, itemHeight: 60, threshold: 50, overscan: 5 })
        ;(globalThis as any).__v = v
        ;(globalThis as any).__update = () => v._updateScroll(0, 600)
        return () => h('div')
      },
    })
    const wrapper = mount(Host, { attachTo: document.body })
    const v: any = (globalThis as any).__v
    const update = (globalThis as any).__update

    update()
    // visible = ceil(600/60) + 1 = 11
    // endIndex = 0 + 11 + 5*2 = 21
    expect(v.visibleItems.value.length).toBeLessThanOrEqual(21)
    expect(v.visibleItems.value.length).toBeLessThan(100)
    // 远小于 1000
    expect(v.visibleItems.value.length).toBeLessThan(1000 / 10)

    wrapper.unmount()
  })

  it('1000 消息 + 滚动到中部时 visibleItems 是中部窗口', async () => {
    const items = ref(Array.from({ length: 1000 }, (_, i) => `msg-${i}`))
    const containerRef = ref<HTMLElement | null>(null)
    const Host = defineComponent({
      setup() {
        const v = useVirtualList({ items, containerRef, itemHeight: 60, threshold: 50, overscan: 5 })
        ;(globalThis as any).__v = v
        ;(globalThis as any).__update = () => v._updateScroll(30000, 600)  // 中段
        return () => h('div')
      },
    })
    const wrapper = mount(Host, { attachTo: document.body })
    const v: any = (globalThis as any).__v
    const update = (globalThis as any).__update

    update()
    await nextTick()

    // startIndex = floor(30000/60) - 5 = 500 - 5 = 495
    expect(v.startIndex.value).toBe(495)
    // endIndex = 495 + (600/60 + 1) + 10 = 495 + 21 = 516
    expect(v.endIndex.value).toBe(516)
    expect(v.visibleItems.value.length).toBe(21)
    expect(v.visibleItems.value[0].index).toBe(495)
    expect(v.visibleItems.value[0].item).toBe('msg-495')

    wrapper.unmount()
  })

  it('1000 消息滚动到底部自动追加场景测试', async () => {
    const items = ref(Array.from({ length: 50 }, (_, i) => `msg-${i}`))
    const containerRef = ref<HTMLElement | null>(null)
    const Host = defineComponent({
      setup() {
        const v = useVirtualList({
          items,
          containerRef,
          itemHeight: 60,
          threshold: 50,
          useAppendStick: true,
        })
        ;(globalThis as any).__v = v
        return () => h('div')
      },
    })
    const wrapper = mount(Host, { attachTo: document.body })

    // 模拟滚动容器
    const fakeEl = document.createElement('div')
    Object.defineProperty(fakeEl, 'clientHeight', { value: 300, configurable: true })
    let _scrollTop = 0
    Object.defineProperty(fakeEl, 'scrollTop', {
      get() { return _scrollTop },
      set(v: number) { _scrollTop = v },
      configurable: true,
    })
    Object.defineProperty(fakeEl, 'scrollHeight', { value: 3000, configurable: true })
    document.body.appendChild(fakeEl)
    containerRef.value = fakeEl
    await nextTick()

    // 一次性追加 950 条 → 1000 条
    for (let i = 0; i < 950; i++) {
      items.value = [...items.value, `bulk-${i}`]
    }
    await nextTick()
    await new Promise<void>((resolve) => requestAnimationFrame(() => resolve()))

    // totalHeight = 1000 * 60 = 60000
    expect((globalThis as any).__v.totalHeight.value).toBe(60000)
    // 滚到底
    expect(_scrollTop).toBeGreaterThan(0)

    wrapper.unmount()
    fakeEl.remove()
  })
})
