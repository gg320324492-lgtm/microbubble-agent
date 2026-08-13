/**
 * authRefresh.js 单飞 + 退避 + 429 cooldown 测试 (类 20.155, 2026-08-14)
 *
 * 6 case 覆盖:
 * ① 5 并发 401 → 仅 1 个 refresh POST (单飞)
 * ② refresh 401 → 1 次 hardLogout (幂等) + token 清空 + 1 次 router.push
 * ③ refresh 429 → 不 router.push + 设置 cooldown + 不调 hardLogout + token 保留
 * ④ cooldown 期间被调 → reject 不发请求 (打断风暴)
 * ⑤ refresh 5xx → reject (无重试) + token 保留
 * ⑥ WS 在 hardLogout 后调 disableReconnect (wsClient 联动)
 */
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

// 每个测试都建独立 fresh store + mocks (vi.resetModules 在 import 前)
const freshSetup = async (initialStore = {}) => {
  vi.resetModules()

  // localStorage mock
  const store = { ...initialStore }
  globalThis.localStorage = {
    getItem: (k) => store[k] ?? null,
    setItem: (k, v) => { store[k] = String(v) },
    removeItem: (k) => { delete store[k] },
    clear: () => { for (const k in store) delete store[k] },
    key: (i) => Object.keys(store)[i] || null,
    get length() { return Object.keys(store).length },
  }

  // router mock
  const routerPush = vi.fn()
  vi.doMock('@/router', () => ({
    default: {
      push: routerPush,
      currentRoute: { value: { path: '/dashboard' } },
    },
  }))

  // useUserStore mock
  const userLogout = vi.fn()
  vi.doMock('@/stores/user', () => ({
    useUserStore: () => ({ logout: userLogout, userInfo: null }),
  }))

  // wsClient mock
  const wsDisableReconnect = vi.fn()
  vi.doMock('@/utils/wsClient', () => ({
    default: {
      disableReconnect: wsDisableReconnect,
    },
  }))

  // axios mock — bareAxios = axios.create() 的 post 可控
  const postSpy = vi.fn()
  const axiosMod = await import('axios')
  vi.spyOn(axiosMod.default, 'create').mockReturnValue({
    post: postSpy,
    defaults: { headers: { common: {} } },
  })

  const authRefresh = (await import('../../utils/authRefresh')).default
  authRefresh._resetForTest()

  return { store, postSpy, routerPush, userLogout, wsDisableReconnect, authRefresh }
}

afterEach(() => {
  vi.useRealTimers()
  vi.doUnmock('@/router')
  vi.doUnmock('@/stores/user')
  vi.doUnmock('@/utils/wsClient')
})

describe('authRefresh — 类 20.155 单飞 + 退避 + 429 cooldown', () => {
  it('① 5 并发 refreshAccessToken → 仅 1 个 POST (单飞)', async () => {
    const { postSpy, authRefresh } = await freshSetup({
      access_token: 'expired-tok',
      refresh_token: 'valid-refresh-tok',
    })
    postSpy.mockImplementation(() => new Promise(resolve => {
      setTimeout(() => resolve({ data: { access_token: 'new-tok' } }), 20)
    }))

    const promises = Array.from({ length: 5 }, () => authRefresh.refreshAccessToken())
    const results = await Promise.all(promises)

    expect(postSpy).toHaveBeenCalledTimes(1)
    expect(results.every(r => r === 'new-tok')).toBe(true)
  })

  it('② refresh 401 → hardLogout 触发 + token 清空 + 仅 1 次 router.push (幂等)', async () => {
    const { store, postSpy, routerPush, userLogout, wsDisableReconnect, authRefresh } = await freshSetup({
      access_token: 'expired-tok',
      refresh_token: 'valid-refresh-tok',
    })
    postSpy.mockRejectedValue({ response: { status: 401, headers: {} } })

    await expect(authRefresh.refreshAccessToken()).rejects.toThrow()

    // token 清空
    expect(store.access_token).toBeUndefined()
    expect(store.refresh_token).toBeUndefined()
    // router.push 仅 1 次 (幂等)
    expect(routerPush).toHaveBeenCalledTimes(1)
    expect(routerPush).toHaveBeenCalledWith('/login')
    // useUserStore.logout 调了
    expect(userLogout).toHaveBeenCalledTimes(1)
    // ws 联动
    expect(wsDisableReconnect).toHaveBeenCalledTimes(1)
    // refresh post 仅 1 次 (不重试)
    expect(postSpy).toHaveBeenCalledTimes(1)
  })

  it('③ refresh 429 → 不 router.push + 设 cooldown + token 保留 + 不 hardLogout', async () => {
    const { store, postSpy, routerPush, userLogout, wsDisableReconnect, authRefresh } = await freshSetup({
      access_token: 'expired-tok',
      refresh_token: 'valid-refresh-tok',
    })
    postSpy.mockRejectedValue({
      response: { status: 429, headers: { 'retry-after': '30' } },
    })

    await expect(authRefresh.refreshAccessToken()).rejects.toThrow()

    // token 保留 (用户仍可用旧 token 继续操作 dashboard)
    expect(store.access_token).toBe('expired-tok')
    expect(store.refresh_token).toBe('valid-refresh-tok')
    // 不 router.push
    expect(routerPush).not.toHaveBeenCalled()
    // 不 hardLogout (userLogout 不应被调)
    expect(userLogout).not.toHaveBeenCalled()
    expect(wsDisableReconnect).not.toHaveBeenCalled()
    // cooldown 激活
    expect(authRefresh.isInCooldown()).toBe(true)
    expect(authRefresh.cooldownRemainingSeconds()).toBeLessThanOrEqual(30)
  })

  it('④ cooldown 期间 refreshAccessToken → reject 不发请求', async () => {
    const { postSpy, authRefresh } = await freshSetup({
      access_token: 'tok', refresh_token: 'rt',
    })
    // 触发 429 设 cooldown
    postSpy.mockRejectedValueOnce({
      response: { status: 429, headers: { 'retry-after': '60' } },
    })
    await expect(authRefresh.refreshAccessToken()).rejects.toThrow()

    // 重置 spy 计数, 但 mock 本身保留
    postSpy.mockClear()
    postSpy.mockResolvedValue({ data: { access_token: 'should-not-be-called' } })

    // cooldown 期间被调 → 0 POST, reject cooldown error
    await expect(authRefresh.refreshAccessToken()).rejects.toThrow(/cooldown/)
    expect(postSpy).not.toHaveBeenCalled()
  })

  it('⑤ refresh 5xx → reject (无重试) + token 保留 + 不硬登出', async () => {
    const { store, postSpy, routerPush, userLogout, authRefresh } = await freshSetup({
      access_token: 'expired-tok',
      refresh_token: 'valid-refresh-tok',
    })
    postSpy.mockRejectedValue({ response: { status: 503, headers: {} } })

    await expect(authRefresh.refreshAccessToken()).rejects.toThrow()

    expect(store.access_token).toBe('expired-tok')
    expect(routerPush).not.toHaveBeenCalled()
    expect(userLogout).not.toHaveBeenCalled()
    expect(postSpy).toHaveBeenCalledTimes(1)
  })

  it('⑥ hardLogout 幂等: 多次并发 refresh 401 → router.push 仅 1 次', async () => {
    const { postSpy, routerPush, authRefresh } = await freshSetup({
      access_token: 'tok', refresh_token: 'rt',
    })
    // 慢返回 → 让 N 个并发都在 _pendingRefresh 里
    postSpy.mockImplementation(() => new Promise((_, reject) => {
      setTimeout(() => reject({ response: { status: 401, headers: {} } }), 20)
    }))

    const promises = Array.from({ length: 3 }, () => authRefresh.refreshAccessToken().catch(() => {}))
    await Promise.all(promises)

    // 3 个并发 refresh 但 post 仅 1 次 (单飞)
    expect(postSpy).toHaveBeenCalledTimes(1)
    // router.push 仍仅 1 次 (hardLogout 幂等)
    expect(routerPush).toHaveBeenCalledTimes(1)
  })
})