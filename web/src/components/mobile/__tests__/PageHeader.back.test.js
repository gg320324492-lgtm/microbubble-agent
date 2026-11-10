// PageHeader.back.test.js — 返回箭头不许连退两级 (2026-11-10)
//
// 事故: PageHeader.onBack 既 emit('back') 又自己 history.back(), 而大量调用方
// 在 @back 里写 router.back() / $router.back() ⇒ 一次点击退两级,
// 详情页直接回主界面 (主指挥实测)。规则: 有监听方 ⇒ 完全交给监听方。
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'

import PageHeader from '../PageHeader.vue'

const backSpy = vi.hoisted(() => vi.fn())
vi.mock('vue-router', () => ({ useRouter: () => ({ back: backSpy }) }))

function mountHeader(props = {}, listeners = {}) {
  return mount(PageHeader, {
    props: { title: '详情', showBack: true, ...props },
    attrs: listeners,
  })
}

describe('PageHeader 返回箭头', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    // jsdom 的 history.length 默认 1; 置 2 让"没有监听方"的分支可观察
    Object.defineProperty(window.history, 'length', { configurable: true, value: 3 })
  })

  it('有 @back 监听方 ⇒ 只 emit, 组件不再 history.back()', async () => {
    const onBack = vi.fn()
    const w = mountHeader({}, { onBack })
    const before = window.location.href
    await w.find('.header-back').trigger('click')
    await flushPromises()
    expect(onBack).toHaveBeenCalledTimes(1)
    // 组件不该再动 history (监听方会自行决定回哪一层)
    expect(window.location.href).toBe(before)
  })

  it('没有 @back 监听方 ⇒ 走默认 history.back()', async () => {
    const w = mountHeader()
    const spy = vi.spyOn(window.history, 'back').mockImplementation(() => {})
    await w.find('.header-back').trigger('click')
    await flushPromises()
    expect(spy).toHaveBeenCalledTimes(1)
    spy.mockRestore()
  })

  it('showBack=false 时不渲染返回按钮', () => {
    const w = mountHeader({ showBack: false })
    expect(w.find('.header-back').exists()).toBe(false)
  })
})
