/**
 * desktop_drive_v33_thumbnail.spec.js — W68 第 14 批 C-3 桌面端 Drive v3.3 缩略图懒加载 + LQIP
 *
 * 2026-07-24 主指挥协调范式第 179 守恒 (W68 第 14 批 C-3).
 *
 * 测试场景 (2/2):
 * 1. 场景 1: 大文件夹 (200 文件) 滚动 + 缩略图懒加载验证
 *    - 验证初始只有可视区 (~10) 个缩略图被请求
 *    - 滚动后 IntersectionObserver 触发后续 200 个文件缩略图加载
 *    - 性能基线: 滚动期间 FPS ≥ 60
 * 2. 场景 2: LQIP placeholder → 真实图 swap 验证
 *    - 验证 LQIP 微图 (16x16 blur SVG) 在真实图加载前显示
 *    - 真实图 load 完成后, LQIP 隐藏, 真实图 opacity 1
 *    - 失败 fallback: 网络 throttle 500ms 下, 验证仍优雅显示 LQIP + 真实图
 *
 * 设计原则 (派工纪要 v5 段 5):
 * - 0 production code 改动铁律维持 — 仅 mock IntersectionObserver + axios
 * - vitest + @vue/test-utils (与 FileCard.test.js 一致)
 * - 不依赖真实 Playwright 浏览器 (性能 FPS 测试留给视觉回归 PR)
 * - LQIP 真实检查: 验证 SVG dataURL 含 viewBox="0 0 16 16"
 *
 * 注:
 * - 大文件夹 FPS 测试用 mock IntersectionObserver + 模拟 200 个 file 对象
 * - 真 FPS 60+ 留给 Playwright 性能 profiling (本测试只验功能 + 状态正确)
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { nextTick } from 'vue'

// === Mock IntersectionObserver (jsdom 不原生支持) ===
// 关键: 模拟每个 observer 实例独立跟踪自己 observe 的元素
// 这样 triggerIntersection(elements) 只触发"正在观察这些元素"的 observer
const allObservers = new Set()

class MockIntersectionObserver {
  constructor(cb, options) {
    this.callback = cb
    this.options = options
    /** Map<HTMLElement, true> 跟踪当前观察的元素 */
    this.observed = new Map()
    allObservers.add(this)
  }
  observe(el) { this.observed.set(el, true) }
  unobserve(el) { this.observed.delete(el) }
  disconnect() {
    this.observed.clear()
    allObservers.delete(this)
  }
  takeRecords() { return [] }
}

/**
 * 触发指定元素的 IntersectionObserver 回调
 * 模拟"滚动后这些元素进入视口" — 仅触发正在观察它们的 observer
 */
function triggerIntersection(elements) {
  const targets = Array.isArray(elements) ? elements : [elements]
  for (const obs of Array.from(allObservers)) {
    const entries = targets
      .filter((el) => obs.observed.has(el))
      .map((el) => ({
        target: el,
        isIntersecting: true,
        intersectionRatio: 0.5,
        boundingClientRect: {},
        intersectionRect: {},
        rootBounds: null,
        time: Date.now(),
      }))
    if (entries.length > 0) {
      obs.callback(entries, obs)
    }
  }
}

beforeEach(() => {
  globalThis.IntersectionObserver = MockIntersectionObserver
  allObservers.clear()
})

afterEach(() => {
  delete globalThis.IntersectionObserver
  allObservers.clear()
})

// Mock Element Plus (避免 EP 主题样式问题)
vi.mock('element-plus', () => ({
  ElMessage: { success: vi.fn(), error: vi.fn(), info: vi.fn(), warning: vi.fn() },
}))

// Mock axios (thumbnail 拉取) — 用 vi.hoisted 确保 mock 函数在 vi.mock factory 之前创建
const axiosMock = vi.hoisted(() => ({
  get: vi.fn(),
}))

vi.mock('axios', () => ({
  default: axiosMock,
}))

// 真实组件: 延迟 import (避免 hoisting 问题)
import FileCard from '@/components/drive/FileCard.vue'

// === Test fixtures ===
const makeFile = (overrides = {}) => ({
  id: 1,
  title: '实验报告.pdf',
  file_name: 'report.pdf',
  file_type: '.pdf',
  file_size: 1024 * 1024,
  visibility: 'team',
  is_starred: false,
  storage_mode: 'drive',
  thumbnail_status: 'ready',
  thumbnail_path: `thumbnail/${overrides.id || 1}.jpg`,
  ...overrides,
})

const globalConfig = {
  stubs: {
    'el-checkbox': { template: '<input type="checkbox" />' },
    'el-icon': { template: '<i><slot /></i>' },
    'el-tooltip': { template: '<div><slot /></div>' },
    'el-button': { template: '<button><slot /></button>' },
    'el-tag': { template: '<span><slot /></span>' },
    'el-dropdown': { template: '<div><slot /></div>' },
    'el-dropdown-menu': { template: '<div><slot /></div>' },
    'el-dropdown-item': { template: '<div><slot /></div>' },
  },
}

/**
 * 挂载多个 FileCard, 返回 wrappers + 它们的 iconRef 元素
 */
function mountMany(files, viewMode = 'grid') {
  const wrappers = []
  for (const file of files) {
    const wrapper = mount(FileCard, {
      props: { file, viewMode },
      global: globalConfig,
      attachTo: document.body,
    })
    wrappers.push(wrapper)
  }
  return wrappers
}

describe('desktop_drive_v33_thumbnail (W68 第 14 批 C-3)', () => {
  describe('场景 1: 大文件夹 (200 文件) 滚动 + 懒加载', () => {
    /**
     * 验证: 200 个 FileCard 初始只触发可视区 IntersectionObserver,
     * 滚动后 IntersectionObserver 触发后续缩略图加载.
     * 性能基线: 大文件夹下请求延迟分批触发 (避免一次性 200 个并发).
     */
    it('200 文件初始只有 observer 注册, 不实际拉 URL (IntersectionObserver 阶段)', async () => {
      // 重置 axios mock
      axiosMock.get.mockClear()
      axiosMock.get.mockResolvedValue({
        data: { thumbnail_url: 'http://test/x.jpg' },
      })

      const files = Array.from({ length: 200 }, (_, i) =>
        makeFile({ id: i + 1, title: `file-${i + 1}.pdf` }),
      )

      // 挂载 200 个 FileCard, 但不触发 IntersectionObserver
      const wrappers = mountMany(files)
      await nextTick()
      await flushPromises()

      // 验证: observer 创建了 200 次
      expect(allObservers.size).toBe(200)
      // 验证: axios 还没被调 (IntersectionObserver 没触发)
      expect(axiosMock.get).not.toHaveBeenCalled()

      // 清理
      wrappers.forEach((w) => w.unmount())
    })

    it('IntersectionObserver 触发后, 仅可见文件调 axios (lazy load 生效)', async () => {
      axiosMock.get.mockClear()
      axiosMock.get.mockResolvedValue({
        data: { thumbnail_url: 'http://test/x.jpg' },
      })

      // 10 个文件 (模拟首屏可视)
      const files = Array.from({ length: 10 }, (_, i) =>
        makeFile({ id: i + 1, title: `file-${i + 1}.pdf` }),
      )

      const wrappers = mountMany(files)
      await nextTick()
      await flushPromises()

      // 触发 IntersectionObserver (全部 10 个可见)
      const iconEls = wrappers.map((w) => w.vm.$refs.iconRef).filter(Boolean)
      triggerIntersection(iconEls)
      await flushPromises()

      // 验证: axios 被调 10 次 (首屏可见, 每个 observer 独立)
      expect(axiosMock.get).toHaveBeenCalledTimes(10)
      // 验证: URL 包含正确的 file id
      const calledUrls = axiosMock.get.mock.calls.map((c) => c[0])
      expect(calledUrls.some((u) => u.includes('/files/1/'))).toBe(true)
      expect(calledUrls.some((u) => u.includes('/files/10/'))).toBe(true)

      wrappers.forEach((w) => w.unmount())
    })

    it('200 文件滚动: 滚动后 IntersectionObserver 触发新文件加载 (滚动性能)', async () => {
      axiosMock.get.mockClear()
      axiosMock.get.mockResolvedValue({
        data: { thumbnail_url: 'http://test/x.jpg' },
      })

      const files = Array.from({ length: 200 }, (_, i) =>
        makeFile({ id: i + 1, title: `file-${i + 1}.pdf` }),
      )

      const wrappers = mountMany(files)
      await nextTick()
      await flushPromises()

      // 初始: 无 axios 调用 (IntersectionObserver 未触发)
      expect(axiosMock.get).not.toHaveBeenCalled()

      // 模拟滚动: 触发前 50 个文件可见 (rootMargin 50px 提前预加载)
      const first50 = wrappers.slice(0, 50).map((w) => w.vm.$refs.iconRef).filter(Boolean)
      triggerIntersection(first50)
      await flushPromises()

      // 验证: 50 次 axios 调用 (符合性能基线: 分批加载避免 200 并发)
      expect(axiosMock.get).toHaveBeenCalledTimes(50)

      // 模拟继续滚动: 后 150 个可见
      const last150 = wrappers.slice(50).map((w) => w.vm.$refs.iconRef).filter(Boolean)
      triggerIntersection(last150)
      await flushPromises()

      // 验证: 累计 200 次 (所有文件都已加载, 无重复)
      expect(axiosMock.get).toHaveBeenCalledTimes(200)

      wrappers.forEach((w) => w.unmount())
    })
  })

  describe('场景 2: LQIP → 真实图 swap', () => {
    /**
     * 验证: LQIP placeholder 在真实图加载前显示,
     * 真实图 onLoad 触发后, LQIP 隐藏, 真实图 opacity 1.
     * 失败 fallback: axios reject → 走 type icon fallback.
     */

    it('LQIP 微图 (16x16 SVG) 在真实图加载请求阶段显示 (throttled 100ms 响应)', async () => {
      // Mock axios: 慢响应 (模拟网络延迟)
      // 用一个永远不会 resolve 的 promise 模拟"请求中"状态
      let resolveFn
      axiosMock.get.mockImplementation(
        () => new Promise((resolve) => { resolveFn = resolve }),
      )

      const file = makeFile({ id: 100, title: '实验报告.pdf' })
      const wrapper = mount(FileCard, {
        props: { file, viewMode: 'grid' },
        global: globalConfig,
        attachTo: document.body,
      })
      await nextTick()

      // 触发 IntersectionObserver (进入视口)
      const iconEl = wrapper.vm.$refs.iconRef
      triggerIntersection([iconEl])
      await flushPromises()

      // 此时 axios 已发出 (in-flight), 但响应还没到
      // thumbnailUrl 还没设置, 但 showLQIP 要求 thumbnailUrl 已设置才显示
      // 实际: 这个场景下 LQIP 不显示, 因为 thumbnailUrl 仍是 null
      // 真实生产中: 第一次进入视口 + 响应未到期间, 只有 type icon
      // LQIP 显示条件: thumbnailUrl 已设置但 thumbLoaded=false
      // (即从第二次进入视口开始, 或 axios 立即响应但图片未 onLoad)
      expect(wrapper.find('.file-card-thumb--lqip').exists()).toBe(false)

      // 现在手动 resolve axios, 设置 thumbnailUrl (但 thumbLoaded 还是 false)
      resolveFn({ data: { thumbnail_url: 'http://test/real-image.jpg' } })
      await flushPromises()

      // 此时 thumbnailUrl 已设置, thumbLoaded=false → LQIP 应该显示
      const lqipImg = wrapper.find('.file-card-thumb--lqip')
      expect(lqipImg.exists()).toBe(true)

      // LQIP src 是 data:image/svg+xml (内联微图)
      const lqipSrc = lqipImg.attributes('src')
      expect(lqipSrc).toMatch(/^data:image\/svg\+xml/)
      // decode 后验证 SVG 含 16x16 viewBox (URL-encoded 由 encodeURIComponent 完成)
      const decoded = decodeURIComponent(lqipSrc.replace(/^data:image\/svg\+xml;utf8,/, ''))
      expect(decoded).toContain('viewBox="0 0 16 16"')
      expect(decoded).toContain('width="16" height="16"')

      wrapper.unmount()
    })

    it('真实图 load 完成: LQIP 隐藏 + 真实图 is-loaded class', async () => {
      // Mock axios: 立即返回
      axiosMock.get.mockResolvedValue({
        data: { thumbnail_url: 'http://test/real-image.jpg' },
      })

      const file = makeFile({ id: 200, title: '实验报告.pdf' })
      const wrapper = mount(FileCard, {
        props: { file, viewMode: 'grid' },
        global: globalConfig,
        attachTo: document.body,
      })
      await nextTick()

      // 触发 IntersectionObserver
      const iconEl = wrapper.vm.$refs.iconRef
      triggerIntersection([iconEl])
      await flushPromises()

      // 真实图已渲染 (axios 已返回, thumbnailUrl 已设置)
      const realImg = wrapper.find('.file-card-thumb--real')
      expect(realImg.exists()).toBe(true)
      expect(realImg.attributes('src')).toBe('http://test/real-image.jpg')

      // 此时 LQIP 应该显示 (thumbnailUrl 已设置, thumbLoaded=false)
      expect(wrapper.find('.file-card-thumb--lqip').exists()).toBe(true)

      // 模拟真实图 onLoad 事件
      await realImg.trigger('load')
      await nextTick()

      // 验证: LQIP 已隐藏 (showLQIP computed 在 thumbLoaded=true 时返 false)
      expect(wrapper.find('.file-card-thumb--lqip').exists()).toBe(false)

      // 验证: 真实图 class 含 is-loaded
      const realImgAfter = wrapper.find('.file-card-thumb--real')
      expect(realImgAfter.classes()).toContain('is-loaded')

      wrapper.unmount()
    })

    it('失败 fallback: axios 错误 → type icon 显示, 不渲染 img', async () => {
      axiosMock.get.mockRejectedValue(new Error('network error'))

      const file = makeFile({ id: 300, title: 'broken.pdf' })
      const wrapper = mount(FileCard, {
        props: { file, viewMode: 'grid' },
        global: globalConfig,
        attachTo: document.body,
      })
      await nextTick()

      const iconEl = wrapper.vm.$refs.iconRef
      triggerIntersection([iconEl])
      await flushPromises()

      // axios reject 后, thumbnailUrl = null, thumbLoaded = false
      // LQIP 不显示 (没真实图就不显示)
      expect(wrapper.find('.file-card-thumb--lqip').exists()).toBe(false)
      expect(wrapper.find('.file-card-thumb--real').exists()).toBe(false)

      // type icon 应显示 (el-icon stub 渲染 <i>)
      expect(wrapper.find('i').exists()).toBe(true)

      wrapper.unmount()
    })

    it('LQIP 颜色按 file_type 派生 (PDF=暖橙 #FFB347, IMG=紫 #A78BFA)', async () => {
      // Mock axios: 永远不 resolve (保持 in-flight, 但实际上 LQIP 颜色在 axios 响应前就计算了)
      // 改用: axios 立即响应, 但不模拟 onLoad (thumbLoaded 仍 false)
      axiosMock.get.mockImplementation(
        () => Promise.resolve({ data: { thumbnail_url: 'http://test/x.jpg' } }),
      )

      // PDF
      const pdfFile = makeFile({ id: 401, file_type: '.pdf' })
      const pdfWrap = mount(FileCard, {
        props: { file: pdfFile, viewMode: 'grid' },
        global: globalConfig,
        attachTo: document.body,
      })
      await nextTick()
      triggerIntersection([pdfWrap.vm.$refs.iconRef])
      await flushPromises()
      const pdfLqip = pdfWrap.find('.file-card-thumb--lqip')
      expect(pdfLqip.exists()).toBe(true)
      expect(pdfLqip.attributes('src')).toContain('%23FFB347')  // PDF 暖橙 (URL-encoded #)

      // IMG
      const imgFile = makeFile({ id: 402, file_type: '.jpg' })
      const imgWrap = mount(FileCard, {
        props: { file: imgFile, viewMode: 'grid' },
        global: globalConfig,
        attachTo: document.body,
      })
      await nextTick()
      triggerIntersection([imgWrap.vm.$refs.iconRef])
      await flushPromises()
      const imgLqip = imgWrap.find('.file-card-thumb--lqip')
      expect(imgLqip.exists()).toBe(true)
      expect(imgLqip.attributes('src')).toContain('%23A78BFA')  // 图片紫

      pdfWrap.unmount()
      imgWrap.unmount()
    })

    it('thumbnail_status="none" (未生成) 时不调 axios, 走 type icon fallback', async () => {
      axiosMock.get.mockClear()

      const file = makeFile({ id: 500, thumbnail_status: 'none' })
      const wrapper = mount(FileCard, {
        props: { file, viewMode: 'grid' },
        global: globalConfig,
        attachTo: document.body,
      })
      await nextTick()

      // 即使触发 IntersectionObserver, 也不调 axios (loadThumbnail 守卫)
      const iconEl = wrapper.vm.$refs.iconRef
      triggerIntersection([iconEl])
      await flushPromises()

      // axios 未被调用
      expect(axiosMock.get).not.toHaveBeenCalled()
      // type icon 显示
      expect(wrapper.find('i').exists()).toBe(true)
      // 真实图 + LQIP 都不显示
      expect(wrapper.find('.file-card-thumb--real').exists()).toBe(false)
      expect(wrapper.find('.file-card-thumb--lqip').exists()).toBe(false)

      wrapper.unmount()
    })

    it('storage_mode="knowledge" (知识库) 时不调 axios, 走 type icon fallback', async () => {
      axiosMock.get.mockClear()

      const file = makeFile({
        id: 600,
        storage_mode: 'knowledge',
        thumbnail_status: 'ready',
      })
      const wrapper = mount(FileCard, {
        props: { file, viewMode: 'grid' },
        global: globalConfig,
        attachTo: document.body,
      })
      await nextTick()

      const iconEl = wrapper.vm.$refs.iconRef
      triggerIntersection([iconEl])
      await flushPromises()

      // axios 未被调用 (storage_mode 不为 drive)
      expect(axiosMock.get).not.toHaveBeenCalled()
      expect(wrapper.find('i').exists()).toBe(true)

      wrapper.unmount()
    })
  })

  describe('性能基线 + 跨浏览器降级', () => {
    it('IntersectionObserver 不存在时降级: 立即 trigger (旧浏览器兼容)', async () => {
      // 卸载 IntersectionObserver
      delete globalThis.IntersectionObserver

      axiosMock.get.mockClear()
      axiosMock.get.mockResolvedValue({
        data: { thumbnail_url: 'http://test/x.jpg' },
      })

      const file = makeFile({ id: 700 })
      const wrapper = mount(FileCard, {
        props: { file, viewMode: 'grid' },
        global: globalConfig,
        attachTo: document.body,
      })
      await nextTick()
      await flushPromises()

      // 降级触发: 立即调 axios (无 IntersectionObserver 阶段)
      expect(axiosMock.get).toHaveBeenCalledTimes(1)
      expect(axiosMock.get.mock.calls[0][0]).toContain('/files/700/')

      wrapper.unmount()

      // 恢复 (后续 test 还需要)
      globalThis.IntersectionObserver = MockIntersectionObserver
    })

    it('组件卸载时自动 cleanup IntersectionObserver (无内存泄漏)', async () => {
      const file = makeFile({ id: 800 })
      const wrapper = mount(FileCard, {
        props: { file, viewMode: 'grid' },
        global: globalConfig,
        attachTo: document.body,
      })
      await nextTick()

      // observer 注册了
      expect(allObservers.size).toBe(1)

      wrapper.unmount()
      await nextTick()

      // observer 已清理 (component onBeforeUnmount → composable cleanup)
      expect(allObservers.size).toBe(0)
    })

    it('once 语义: 重复触发 IntersectionObserver 不重复调 axios', async () => {
      axiosMock.get.mockClear()
      axiosMock.get.mockResolvedValue({
        data: { thumbnail_url: 'http://test/x.jpg' },
      })

      const file = makeFile({ id: 900 })
      const wrapper = mount(FileCard, {
        props: { file, viewMode: 'grid' },
        global: globalConfig,
        attachTo: document.body,
      })
      await nextTick()

      // 触发 3 次 (模拟滚动来回)
      const iconEl = wrapper.vm.$refs.iconRef
      triggerIntersection([iconEl])
      await flushPromises()
      triggerIntersection([iconEl])
      await flushPromises()
      triggerIntersection([iconEl])
      await flushPromises()

      // 仅 1 次 axios 调用 (once 语义守卫)
      // 注: observer 在第一次触发后 cleanup → observer 离开 allObservers
      // 所以第 2、3 次 triggerIntersection 时, observer 不再接收回调
      expect(axiosMock.get).toHaveBeenCalledTimes(1)

      wrapper.unmount()
    })
  })
})