// M2-3a+ 统一登录 —— 认领决策（纯函数）+ AuthService 集成 + 离线宽容 + 退役语义
import { describe, expect, it } from 'vitest'
import { openNodeSqlite } from '@main/db/adapters'
import { runMigrations } from '@main/db/migrations'
import { AuthService, type SessionPersistence } from '@main/services/auth.service'
import { CLAIMABLE_TABLES, claimSummary, pickLocalUsername, planClaim, type LocalUserRow } from '@main/services/cloud-identity'

/** 内存版会话持久化（替代 safeStorage） */
function memPersistence(): SessionPersistence & { get(): string | null } {
  let token: string | null = null
  return {
    persist: (t: string) => {
      token = t
    },
    load: () => token,
    clear: () => {
      token = null
    },
    get: () => token
  }
}

function makeAuth(): { auth: AuthService; db: ReturnType<typeof openNodeSqlite>; persistence: ReturnType<typeof memPersistence> } {
  const db = openNodeSqlite(':memory:')
  runMigrations(db)
  const persistence = memPersistence()
  return { auth: new AuthService(db, persistence), db, persistence }
}

const identity = (id: string, name: string) => ({ cloudUserId: id, cloudUsername: name })

// ---------------------------------------------------------------- 1 认领决策（纯函数，≥3）

describe('认领决策 planClaim（纯函数）', () => {
  it('首次接入 + 存在无主旧账号 → 新建缓存行 + 认领旧账号数据', () => {
    const users: LocalUserRow[] = [{ id: 'u1', username: 'old-local', cloudUserId: null }]
    const plan = planClaim(identity('7', 'wangtz'), users)
    expect(plan.reuseLocalUserId).toBeNull()
    expect(plan.createUsername).toBe('wangtz')
    expect(plan.orphanUserIds).toEqual(['u1'])
    expect(plan.firstClaim).toBe(true)
  })

  it('★ 一次性：同一云端身份再次登录 → 复用缓存行、**不再认领**', () => {
    const users: LocalUserRow[] = [
      { id: 'u-cloud-7', username: 'wangtz', cloudUserId: '7' },
      { id: 'u1', username: 'old-local', cloudUserId: null } // 即便还有无主行也不再认领（已认领过）
    ]
    const plan = planClaim(identity('7', 'wangtz'), users)
    expect(plan.reuseLocalUserId).toBe('u-cloud-7')
    expect(plan.orphanUserIds).toEqual([])
    expect(plan.firstClaim).toBe(false)
  })

  it('★ 多账号隔离：A 认领过的行，B 登录时不参与认领', () => {
    const users: LocalUserRow[] = [
      { id: 'u-cloud-7', username: 'wangtz', cloudUserId: '7' }, // A 已认领
      { id: 'u1', username: 'old-local', cloudUserId: null } // 仅剩的无主行
    ]
    const planB = planClaim(identity('9', 'other'), users)
    expect(planB.orphanUserIds).toEqual(['u1']) // 只能拿无主行
    expect(planB.orphanUserIds).not.toContain('u-cloud-7') // 绝不拿 A 的
  })

  it('全新机器（无任何用户行）→ 新建、无认领', () => {
    const plan = planClaim(identity('7', 'wangtz'), [])
    expect(plan.createUsername).toBe('wangtz')
    expect(plan.orphanUserIds).toEqual([])
    expect(plan.firstClaim).toBe(true)
  })

  it('用户名冲突 → 自动加后缀，不覆盖既有行', () => {
    expect(pickLocalUsername('wangtz', [])).toBe('wangtz')
    expect(pickLocalUsername('wangtz', ['wangtz'])).toBe('wangtz-2')
    expect(pickLocalUsername('wangtz', ['wangtz', 'wangtz-2'])).toBe('wangtz-3')
    expect(pickLocalUsername('', [])).toBe('cloud-user')
    // 冲突时 planClaim 采用后缀名
    const plan = planClaim(identity('7', 'wangtz'), [{ id: 'x', username: 'wangtz', cloudUserId: null }])
    expect(plan.createUsername).toBe('wangtz-2')
  })

  it('认领摘要：有数据/无数据两种文案，均不含正文', () => {
    expect(claimSummary({})).toContain('无历史数据需要认领')
    const s = claimSummary({ 会话: 3, 知识: 12, 会议: 0 })
    expect(s).toContain('会话 3 条')
    expect(s).toContain('知识 12 条')
    expect(s).not.toContain('会议')
    expect(CLAIMABLE_TABLES.map((t) => t.table)).toContain('chat_sessions')
  })
})

// ---------------------------------------------------------------- 2 登录集成（≥4）

describe('AuthService.loginWithCloud', () => {
  it('首次登录：建云端缓存行 + 认领会话数据 + 起会话（令牌落持久化）', () => {
    const { auth, db, persistence } = makeAuth()
    // 造「旧本地账号 + 其名下会话」
    db.prepare(
      'INSERT INTO users (id, username, display_name, password_hash, role, is_active, created_at, updated_at) VALUES (?,?,?,?,?,1,?,?)'
    ).run('u-old', 'old-local', '旧账号', 'x', 'admin', 1, 1)
    db.prepare('INSERT INTO chat_sessions (id, user_id, title, created_at, updated_at) VALUES (?,?,?,?,?)').run('s1', 'u-old', '旧会话一', 1, 1)
    db.prepare('INSERT INTO chat_sessions (id, user_id, title, created_at, updated_at) VALUES (?,?,?,?,?)').run('s2', 'u-old', '旧会话二', 1, 1)

    const r = auth.loginWithCloud(identity('7', 'wangtz'))
    expect(r.firstClaim).toBe(true)
    expect(r.createdUser).toBe(true)
    expect(r.claimedCounts['会话']).toBe(2)
    expect(r.summary).toContain('会话 2 条')
    expect(persistence.get()).toBeTruthy() // 令牌已持久化（离线宽容的基础）
    // 数据已 re-point 到云端身份
    const rows = db.prepare('SELECT user_id FROM chat_sessions').all() as { user_id: string }[]
    expect(rows.every((x) => x.user_id === 'u-cloud-7')).toBe(true)
    // 本地旧行保留（向前兼容）
    expect((db.prepare('SELECT COUNT(*) AS c FROM users').get() as { c: number }).c).toBe(2)
  })

  it('★ 二次登录：复用缓存行、不再重复认领、数据条数不变', () => {
    const { auth, db } = makeAuth()
    db.prepare(
      'INSERT INTO users (id, username, display_name, password_hash, role, is_active, created_at, updated_at) VALUES (?,?,?,?,?,1,?,?)'
    ).run('u-old', 'old-local', '旧账号', 'x', 'admin', 1, 1)
    db.prepare('INSERT INTO chat_sessions (id, user_id, title, created_at, updated_at) VALUES (?,?,?,?,?)').run('s1', 'u-old', 'x', 1, 1)

    const first = auth.loginWithCloud(identity('7', 'wangtz'))
    expect(first.claimedCounts['会话']).toBe(1)
    auth.logout()
    const second = auth.loginWithCloud(identity('7', 'wangtz'))
    expect(second.firstClaim).toBe(false)
    expect(second.createdUser).toBe(false)
    expect(second.claimedCounts).toEqual({}) // 零认领
    expect(second.summary).toBe('')
    expect((db.prepare('SELECT COUNT(*) AS c FROM users').get() as { c: number }).c).toBe(2) // 未再建行
  })

  it('★ 多账号同机：B 登录拿不到 A 已认领的数据', () => {
    const { auth, db } = makeAuth()
    db.prepare(
      'INSERT INTO users (id, username, display_name, password_hash, role, is_active, created_at, updated_at) VALUES (?,?,?,?,?,1,?,?)'
    ).run('u-old', 'old-local', '旧账号', 'x', 'admin', 1, 1)
    db.prepare('INSERT INTO chat_sessions (id, user_id, title, created_at, updated_at) VALUES (?,?,?,?,?)').run('sA', 'u-old', 'A 的会话', 1, 1)

    auth.loginWithCloud(identity('7', 'wangtz')) // A 认领
    auth.logout()
    const b = auth.loginWithCloud(identity('9', 'other')) // B 登录
    expect(b.claimedCounts).toEqual({}) // 无可认领
    const row = db.prepare('SELECT user_id FROM chat_sessions WHERE id = ?').get('sA') as { user_id: string }
    expect(row.user_id).toBe('u-cloud-7') // 仍属 A
  })

  it('登录后 requireUser 返回云端身份（username = 父级用户名）', () => {
    const { auth } = makeAuth()
    auth.loginWithCloud(identity('7', 'wangtz'))
    const u = auth.requireUser()
    expect(u.username).toBe('wangtz')
    expect(u.id).toBe('u-cloud-7')
  })
})

// ---------------------------------------------------------------- 3 离线宽容（≥2）

describe('离线宽容', () => {
  it('★ 登录后重启（无网络）：restore() 用缓存会话直接进入', () => {
    const { auth, db, persistence } = makeAuth()
    auth.loginWithCloud(identity('7', 'wangtz'))
    const token = persistence.get()!

    // 模拟重启：新实例 + 同一 DB + 同一持久化令牌
    const fresh = new AuthService(db, { persist: () => undefined, load: () => token, clear: () => undefined })
    const session = fresh.restore()
    expect(session).not.toBeNull()
    expect(session!.user.username).toBe('wangtz')
    expect(fresh.hasLiveSession()).toBe(true)
  })

  it('无令牌 → restore() 为 null（启动应停在登录窗）', () => {
    const { auth } = makeAuth()
    expect(auth.restore()).toBeNull()
    expect(auth.hasLiveSession()).toBe(false)
  })

  it('退出登录：清令牌 + 会话失效；**数据保留**（下次同账号登录仍在）', () => {
    const { auth, db, persistence } = makeAuth()
    db.prepare(
      'INSERT INTO users (id, username, display_name, password_hash, role, is_active, created_at, updated_at) VALUES (?,?,?,?,?,1,?,?)'
    ).run('u-old', 'old-local', '旧账号', 'x', 'admin', 1, 1)
    db.prepare('INSERT INTO chat_sessions (id, user_id, title, created_at, updated_at) VALUES (?,?,?,?,?)').run('s1', 'u-old', 'x', 1, 1)
    auth.loginWithCloud(identity('7', 'wangtz'))
    expect(auth.logout()).toBe(true)
    expect(persistence.get()).toBeNull()
    expect(auth.restore()).toBeNull()
    // 数据仍在（未被删除）
    expect((db.prepare('SELECT COUNT(*) AS c FROM chat_sessions').get() as { c: number }).c).toBe(1)
    // 同账号再登录 → 数据仍归它
    const again = auth.loginWithCloud(identity('7', 'wangtz'))
    expect(again.firstClaim).toBe(false)
    const row = db.prepare('SELECT user_id FROM chat_sessions WHERE id = ?').get('s1') as { user_id: string }
    expect(row.user_id).toBe('u-cloud-7')
  })
})

// ---------------------------------------------------------------- 4 退役与解耦（≥2）

describe('本地注册退役 + 备份密码解耦', () => {
  it('★ 云端身份行不能走本地密码登录（哨兵 hash 永不匹配）', () => {
    const { auth } = makeAuth()
    auth.loginWithCloud(identity('7', 'wangtz'))
    expect(() => auth.login('wangtz', 'any-password')).toThrow()
    expect(() => auth.login('wangtz', '')).toThrow()
  })

  it('本地建号入口仍在（向后兼容 API 未删），但不再是启动必经路径', () => {
    const { auth } = makeAuth()
    // getUserCount=0 时旧流程可用（结构保留，工单要求「数据库结构保留不删」）
    expect(auth.getUserCount()).toBe(0)
    // 云端登录不依赖本地建号
    const r = auth.loginWithCloud(identity('7', 'wangtz'))
    expect(r.session.user.username).toBe('wangtz')
    expect(auth.getUserCount()).toBe(1)
  })

  it('★ 备份密码独立字段：登录方式切换前后互不影响', () => {
    const { auth, db } = makeAuth()
    // 备份密码存在 settings（独立于 users/session），模拟既有值
    db.prepare('INSERT INTO settings (user_id, key, value, updated_at) VALUES (?,?,?,?)').run('u-old', 'backup.exitPassword', 'ENC:xyz', 1)
    const before = db.prepare("SELECT value FROM settings WHERE key = 'backup.exitPassword'").get() as { value: string }
    expect(before.value).toBe('ENC:xyz')

    auth.loginWithCloud(identity('7', 'wangtz'))
    auth.logout()
    auth.loginWithCloud(identity('9', 'other'))

    const after = db.prepare("SELECT value FROM settings WHERE key = 'backup.exitPassword'").get() as { value: string }
    expect(after.value).toBe('ENC:xyz') // 未被登录流程触碰
    // 备份服务读取路径也不依赖 users/session
    expect(after.value.startsWith('ENC:')).toBe(true)
  })
})

// ---------------------------------------------------------------- 5 退役（源码级 + DOM）

describe('本地注册退役', () => {
  it('★ 路由守卫不再分流到 setup（有会话直进 / 无会话到登录窗）', async () => {
    const { readFileSync } = await import('node:fs')
    const src = readFileSync('src/renderer/src/router/index.ts', 'utf8')
    const guard = src.slice(src.indexOf('router.beforeEach'))
    // 未登录访问 /app → 回登录窗（而不是 setup）
    expect(guard).toContain("if (to.path.startsWith('/app') && !auth.isAuthenticated) {")
    expect(guard).toContain("return { name: 'login' }")
    // setup 不可达
    expect(guard).toMatch(/if \(to\.name === 'setup'\) \{\s*return \{ name: 'login' \}/)
    // 不再出现 needsSetup 分流
    expect(guard).not.toContain('needsSetup ?')
  })

  it('★ 登录窗无本地建号入口，且提供「到 mnb-lab.cn 注册」外链引导', async () => {
    const { readFileSync } = await import('node:fs')
    const src = readFileSync('src/renderer/src/views/LoginView.vue', 'utf8')
    expect(src).toContain('data-testid="login-register-hint"')
    expect(src).toContain('mnb-lab.cn')
    expect(src).toContain('api.app.openExternal')
    // 不再有本地注册/建号调用
    expect(src).not.toContain('registerAdmin')
    expect(src).not.toContain('auth.register')
  })

  it('登录窗走云端登录（cloudLogin）而非本地 login', async () => {
    const { readFileSync } = await import('node:fs')
    const src = readFileSync('src/renderer/src/views/LoginView.vue', 'utf8')
    expect(src).toContain('auth.cloudLogin(')
    expect(src).not.toMatch(/await auth\.login\(/)
  })
})
