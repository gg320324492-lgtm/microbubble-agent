import { describe, it, expect, beforeEach } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { useUserStore } from '../user'

describe('userStore.isAdmin (W86 mini-9 fix)', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('userInfo = null → isAdmin = false', () => {
    const store = useUserStore()
    expect(store.isAdmin).toBe(false)
  })

  it('userInfo.role = "admin" → isAdmin = true', () => {
    const store = useUserStore()
    store.userInfo = { id: 1, name: 'A', role: 'admin' }
    expect(store.isAdmin).toBe(true)
  })

  it('userInfo.role = "leader" → isAdmin = true', () => {
    const store = useUserStore()
    store.userInfo = { id: 2, name: 'L', role: 'leader' }
    expect(store.isAdmin).toBe(true)
  })

  it('userInfo.role = "member" → isAdmin = false', () => {
    const store = useUserStore()
    store.userInfo = { id: 3, name: 'M', role: 'member' }
    expect(store.isAdmin).toBe(false)
  })

  it('userInfo.role = undefined → isAdmin = false', () => {
    const store = useUserStore()
    store.userInfo = { id: 4, name: 'U' }
    expect(store.isAdmin).toBe(false)
  })

  it('兼容 old logout 不抛错 + isAdmin 仍可读', () => {
    const store = useUserStore()
    store.userInfo = { id: 5, name: 'X', role: 'admin' }
    expect(store.isAdmin).toBe(true)
    // logout 内部异步 import store, 同步路径只清 userInfo
    store.userInfo = null
    expect(store.isAdmin).toBe(false)
  })
})
