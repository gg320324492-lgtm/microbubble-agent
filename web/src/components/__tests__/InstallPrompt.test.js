import { describe, it, expect, beforeEach, vi, afterEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { nextTick } from 'vue'

/**
 * InstallPrompt.test.js — PWA 安装提示组件测试
 *
 * 覆盖 4 个核心场景:
 *  1. iOS standalone=true → 不显示 (用户已添加到主屏幕)
 *  2. dismissed=true (localStorage 标记) → 不显示
 *  3. beforeinstallprompt 事件触发 → 显示提示 (通过 deferredPrompt prop)
 *  4. 点 "现在添加" 按钮 → 调 deferredPrompt.prompt() + 标记 dismissed
 *
 * Mock 策略:
 *  - localStorage: jsdom 内置, beforeEach clear
 *  - matchMedia: vi.stubGlobal mock
 *  - navigator.userAgent / navigator.standalone: 测试时手动覆盖
 */
import InstallPrompt from '../InstallPrompt.vue'

function makeDeferredPrompt(choice = 'accepted') {
  return {
    prompt: vi.fn().mockResolvedValue(undefined),
    userChoice: Promise.resolve({ outcome: choice }),
  }
}

describe('InstallPrompt — PWA install prompt', () => {
  beforeEach(() => {
    // 清空 localStorage
    try {
      localStorage.clear()
    } catch (err) {
      // 隐私模式下可能抛错, 忽略
    }
    // 重置 navigator.standalone
    Object.defineProperty(window.navigator, 'standalone', {
      configurable: true,
      value: false,
      writable: true,
    })
    // 重置 userAgent (避免 jsdom 默认含 Safari)
    Object.defineProperty(window.navigator, 'userAgent', {
      configurable: true,
      value: 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0',
      writable: true,
    })
    // mock matchMedia (PWA display-mode 判定)
    const matchMediaStub = vi.fn().mockReturnValue({ matches: false })
    vi.stubGlobal('matchMedia', matchMediaStub)
  })

  afterEach(() => {
    vi.unstubAllGlobals()
    vi.restoreAllMocks()
  })

  it('1. iOS Safari standalone=true → 隐藏提示 (用户已添加到主屏幕)', async () => {
    // 模拟 iOS + standalone=true
    Object.defineProperty(window.navigator, 'userAgent', {
      configurable: true,
      value: 'Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) Safari/604.1',
      writable: true,
    })
    Object.defineProperty(window.navigator, 'standalone', {
      configurable: true,
      value: true,
      writable: true,
    })
    // 标记 first_seen 8 天前 + drive 访问 5 次, 让普通条件已通过
    const eightDaysAgo = Date.now() - 8 * 24 * 60 * 60 * 1000
    localStorage.setItem('install_prompt_first_seen', String(eightDaysAgo))
    localStorage.setItem('install_prompt_drive_visits', '5')
    // 挂载组件 (即使传 deferredPrompt, standalone=true 应覆盖)
    const wrapper = mount(InstallPrompt, {
      props: { deferredPrompt: makeDeferredPrompt() },
    })
    await nextTick()
    await flushPromises()
    // 预期: 不显示
    expect(wrapper.find('[data-testid="install-prompt"]').exists()).toBe(false)
    wrapper.unmount()
  })

  it('2. dismissed=true → 隐藏提示 (localStorage 标记 dismissed 未过期)', async () => {
    // 标记 first_seen 8 天前 (满足 7 天延迟)
    const eightDaysAgo = Date.now() - 8 * 24 * 60 * 60 * 1000
    localStorage.setItem('install_prompt_first_seen', String(eightDaysAgo))
    // 标记 dismissed 30 天内 (未过期) + drive 访问 < 3
    localStorage.setItem('install_prompt_dismissed_at', String(Date.now() - 1000))
    localStorage.setItem('install_prompt_drive_visits', '0')
    // 挂载组件 + 传 deferredPrompt (但 dismissed 应覆盖)
    const wrapper = mount(InstallPrompt, {
      props: { deferredPrompt: makeDeferredPrompt() },
    })
    await nextTick()
    await flushPromises()
    // 预期: 不显示
    expect(wrapper.find('[data-testid="install-prompt"]').exists()).toBe(false)
    wrapper.unmount()
  })

  it('3. 条件满足 + deferredPrompt 入参 → 显示提示', async () => {
    // 标记 first_seen 8 天前 (满足 7 天延迟)
    const eightDaysAgo = Date.now() - 8 * 24 * 60 * 60 * 1000
    localStorage.setItem('install_prompt_first_seen', String(eightDaysAgo))
    // 标记 dismissed 31 天前 (过期, 自动清除)
    const thirtyOneDaysAgo = Date.now() - 31 * 24 * 60 * 60 * 1000
    localStorage.setItem('install_prompt_dismissed_at', String(thirtyOneDaysAgo))
    // 挂载组件 + 传 deferredPrompt
    const wrapper = mount(InstallPrompt, {
      props: { deferredPrompt: makeDeferredPrompt() },
    })
    await nextTick()
    await flushPromises()
    // 预期: 提示显示
    expect(wrapper.find('[data-testid="install-prompt"]').exists()).toBe(true)
    expect(wrapper.find('.install-prompt__title').text()).toBe('添加到主屏幕')
    expect(wrapper.find('[data-testid="install-prompt-install"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="install-prompt-dismiss"]').exists()).toBe(true)
    wrapper.unmount()
  })

  it('4. 点 "现在添加" 按钮 → 调 deferredPrompt.prompt() + 标记 dismissed', async () => {
    // 准备满足显示条件
    const eightDaysAgo = Date.now() - 8 * 24 * 60 * 60 * 1000
    localStorage.setItem('install_prompt_first_seen', String(eightDaysAgo))
    // 创建 prompt mock (用 vi.fn 让 vitest 跟踪)
    const promptFn = vi.fn().mockResolvedValue(undefined)
    const dp = {
      prompt: promptFn,
      userChoice: Promise.resolve({ outcome: 'accepted' }),
    }
    const wrapper = mount(InstallPrompt, {
      props: { deferredPrompt: dp },
    })
    await nextTick()
    await flushPromises()
    expect(wrapper.find('[data-testid="install-prompt"]').exists()).toBe(true)
    // 点 "现在添加"
    await wrapper.find('[data-testid="install-prompt-install"]').trigger('click')
    await flushPromises()
    await flushPromises() // 等 userChoice Promise + 后续逻辑
    // 预期: prompt() 被调
    expect(promptFn).toHaveBeenCalledTimes(1)
    // 预期: dismissed 标记被设
    expect(localStorage.getItem('install_prompt_dismissed_at')).not.toBeNull()
    // 预期: UI 隐藏
    expect(wrapper.find('[data-testid="install-prompt"]').exists()).toBe(false)
    wrapper.unmount()
  })
})