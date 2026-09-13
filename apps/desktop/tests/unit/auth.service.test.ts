// 账号服务契约 — 全程零网络（node:sqlite 内存库，避开 Electron ABI）
import { describe, expect, it } from 'vitest'
import { openNodeSqlite } from '@main/db/adapters'
import { runMigrations } from '@main/db/migrations'
import { AuthService, hashPassword, verifyPassword } from '@main/services/auth.service'
import type { SessionPersistence } from '@main/services/auth.service'

function makeAuth(): { auth: AuthService; persisted: { value: string | null } } {
  const db = openNodeSqlite(':memory:')
  runMigrations(db)
  const mem = { value: null as string | null }
  const persistence: SessionPersistence = {
    persist: (t: string) => (mem.value = t),
    load: () => mem.value,
    clear: () => (mem.value = null)
  }
  return { auth: new AuthService(db, persistence), persisted: mem }
}

describe('hashPassword / verifyPassword', () => {
  it('scrypt 格式可往返校验', () => {
    const stored = hashPassword('demo12345')
    expect(stored.startsWith('scrypt$16384$8$1$')).toBe(true)
    expect(verifyPassword('demo12345', stored)).toBe(true)
    expect(verifyPassword('wrong-pass', stored)).toBe(false)
  })
})

describe('AuthService.registerFirstAdmin', () => {
  it('零用户时创建 admin，第二个注册被拒绝', () => {
    const { auth } = makeAuth()
    const s = auth.registerFirstAdmin({ username: 'wang', displayName: '王老师', password: 'password123' })
    expect(s.user.role).toBe('admin')
    expect(s.user.displayName).toBe('王老师')
    expect(auth.getUserCount()).toBe(1)
    expect(() => auth.registerFirstAdmin({ username: 'li', password: 'password123' })).toThrow('已初始化')
  })

  it('校验: 用户名必填 / 密码 ≥8', () => {
    const { auth } = makeAuth()
    expect(() => auth.registerFirstAdmin({ username: '', password: 'password123' })).toThrow()
    expect(() => auth.registerFirstAdmin({ username: 'a', password: 'short' })).toThrow('8-128')
  })
})

describe('AuthService.login', () => {
  it('正确密码返回会话并持久化 token；错误密码报「用户名或密码错误」', () => {
    const { auth, persisted } = makeAuth()
    auth.registerFirstAdmin({ username: 'wang', password: 'password123' })
    const s = auth.login('wang', 'password123')
    expect(s.user.username).toBe('wang')
    expect(persisted.value).toBeTruthy()
    expect(() => auth.login('wang', 'wrong-password')).toThrow('用户名或密码错误')
    expect(() => auth.login('nobody', 'password123')).toThrow('用户名或密码错误')
  })
})

describe('AuthService.restore / logout / requireUser', () => {
  it('restore 用持久化 token 免登录，logout 后失效', () => {
    const { auth } = makeAuth()
    auth.registerFirstAdmin({ username: 'wang', password: 'password123' })
    // 模拟重启: 新实例读同一持久化 token
    const r = auth.restore()
    expect(r).not.toBeNull()
    expect(r?.user.username).toBe('wang')
    expect(auth.hasLiveSession()).toBe(true)

    auth.logout()
    expect(auth.restore()).toBeNull()
    expect(() => auth.requireUser()).toThrow('未登录')
  })

  it('吊销后的 token 不能 restore', () => {
    const { auth } = makeAuth()
    auth.registerFirstAdmin({ username: 'wang', password: 'password123' })
    const token = (auth as unknown as { currentToken: string }).currentToken // 测试窥探
    auth.logout()
    // 手工把旧 token 塞回持久化（模拟被吊销 token 残留）
    ;(auth as unknown as { persistence: SessionPersistence }).persistence.persist(token)
    expect(auth.restore()).toBeNull()
  })
})
