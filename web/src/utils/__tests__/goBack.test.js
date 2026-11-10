// goBack.test.js — 详情页返回判据 (2026-11-10)
//
// 事故链: history.length 恒真 ⇒ 新标签直接打开详情时 router.back() 弹到空白页;
// 曾用 document.referrer 修, 但 SPA 站内 pushState 不改 referrer ⇒ 从网盘深层
// 点进文件会被误判成外部直达, 返回跳回根目录。
// 唯一可靠判据 = vue-router 的 history.state.back。
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { goBackOr, canGoBackInApp } from '../goBack'

function makeRouter(state) {
  return {
    options: { history: { state } },
    back: vi.fn(),
    push: vi.fn(),
  }
}

const originalState = window.history.state
beforeEach(() => {
  window.history.replaceState(null, '')
})
afterEach(() => {
  window.history.replaceState(originalState, '')
})

describe('canGoBackInApp', () => {
  it('站内 push 过来 (state.back 非 null) ⇒ 可回', () => {
    expect(canGoBackInApp(makeRouter({ back: '/drive', current: '/drive/file/1' }))).toBe(true)
  })

  it('初始导航 (state.back=null) ⇒ 不可回', () => {
    expect(canGoBackInApp(makeRouter({ back: null, current: '/drive/file/1' }))).toBe(false)
  })

  it('router 没给 state 时读 window.history.state', () => {
    window.history.replaceState({ back: '/drive', current: '/x' }, '')
    expect(canGoBackInApp(makeRouter(undefined))).toBe(true)
  })

  it('两侧都没 back 字段 ⇒ 不可回 (不靠 history.length 猜)', () => {
    expect(canGoBackInApp(makeRouter({ current: '/x' }))).toBe(false)
  })
})

describe('goBackOr', () => {
  it('可回 ⇒ 只调 router.back(), 不动 fallback', () => {
    const r = makeRouter({ back: '/drive', current: '/drive/file/1' })
    goBackOr(r, '/drive')
    expect(r.back).toHaveBeenCalledTimes(1)
    expect(r.push).not.toHaveBeenCalled()
  })

  it('不可回 ⇒ 只调 router.push(fallback)', () => {
    const r = makeRouter({ back: null, current: '/drive/file/1' })
    goBackOr(r, '/drive')
    expect(r.push).toHaveBeenCalledWith('/drive')
    expect(r.back).not.toHaveBeenCalled()
  })

  it('评论页用文件详情当 fallback, 不会被写成网盘根', () => {
    const r = makeRouter({ back: null, current: '/drive/file/9/comments' })
    goBackOr(r, '/drive/file/9')
    expect(r.push).toHaveBeenCalledWith('/drive/file/9')
  })
})
