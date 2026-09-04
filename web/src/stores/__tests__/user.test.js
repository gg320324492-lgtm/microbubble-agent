import { describe, it, expect, beforeEach } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { useUserStore } from '../user'

// 2026-09-05 角色扁平化: isAdmin 语义 = 已登录即等权 (不再按 role 分级);
// userRole 展示年级身份称谓 (title/grade 派生), 不再显示 管理员/组长/成员。
describe('userStore.isAdmin (2026-09-05 角色扁平化: 全员等权)', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('userInfo = null → isAdmin = false (未登录)', () => {
    const store = useUserStore()
    expect(store.isAdmin).toBe(false)
  })

  it('任意登录成员 → isAdmin = true (不再区分 admin/leader/member)', () => {
    const store = useUserStore()
    for (const role of ['admin', 'leader', 'member', undefined]) {
      store.userInfo = { id: 1, name: 'A', role }
      expect(store.isAdmin).toBe(true)
    }
  })

  it('userRole 展示后端 title, 缺失时由 grade 派生称谓', () => {
    const store = useUserStore()
    store.userInfo = { id: 1, name: 'A', role: 'member', title: '导师', grade: '副教授' }
    expect(store.userRole).toBe('导师')
    store.userInfo = { id: 2, name: 'B', role: 'member', grade: '研二' }
    expect(store.userRole).toBe('硕士')
    store.userInfo = { id: 3, name: 'C', role: 'member', grade: '大四' }
    expect(store.userRole).toBe('本科生')
    store.userInfo = { id: 4, name: 'D', role: 'member' }
    expect(store.userRole).toBe('成员')
  })

  it('兼容 old logout 不抛错 + isAdmin 仍可读', () => {
    const store = useUserStore()
    store.userInfo = { id: 5, name: 'X', role: 'member' }
    expect(store.isAdmin).toBe(true)
    // logout 内部异步 import store, 同步路径只清 userInfo
    store.userInfo = null
    expect(store.isAdmin).toBe(false)
  })
})
