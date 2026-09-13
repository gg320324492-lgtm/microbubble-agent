// 本地账号服务 — 首启注册管理员 / 登录 / 会话恢复 / 登出。
// 铁律（骨架设计 §1.3）: 登录全程零网络请求；session token 只存主进程内存 + 库内哈希，
// 明文 token 仅通过注入的 hooks 持久化（生产为 safeStorage 加密，测试为内存）。
// 密码哈希格式 scrypt$N$r$p$salt$hash 与归档实现兼容。
import { createHash, randomBytes, scryptSync, timingSafeEqual } from 'node:crypto'
import type { SqlDatabase } from '../db/adapters'
import { SESSION_TTL_MS } from '@shared/constants'
import type { AuthSession, LocalUser, UserRole } from '@shared/types'

const SCRYPT_N = 16384
const SCRYPT_R = 8
const SCRYPT_P = 1
const KEY_LEN = 32
const SALT_LEN = 16

export function hashPassword(password: string): string {
  const salt = randomBytes(SALT_LEN)
  const hash = scryptSync(password.normalize('NFKC'), salt, KEY_LEN, { N: SCRYPT_N, r: SCRYPT_R, p: SCRYPT_P })
  return `scrypt$${SCRYPT_N}$${SCRYPT_R}$${SCRYPT_P}$${salt.toString('hex')}$${hash.toString('hex')}`
}

export function verifyPassword(password: string, stored: string): boolean {
  const parts = stored.split('$')
  if (parts.length !== 6 || parts[0] !== 'scrypt') return false
  const salt = Buffer.from(parts[4], 'hex')
  const expected = Buffer.from(parts[5], 'hex')
  const actual = scryptSync(password.normalize('NFKC'), salt, expected.length, {
    N: Number(parts[1]),
    r: Number(parts[2]),
    p: Number(parts[3])
  })
  return actual.length === expected.length && timingSafeEqual(actual, expected)
}

const sha256 = (s: string) => createHash('sha256').update(s).digest('hex')

/** 明文 token 持久化钩子 — 生产接 safeStorage，测试接内存变量 */
export interface SessionPersistence {
  persist(token: string): void
  load(): string | null
  clear(): void
}

interface UserRow {
  id: string
  username: string
  display_name: string | null
  role: string
  is_active: number
  created_at: number
}

function mapUser(r: UserRow): LocalUser {
  return {
    id: r.id,
    username: r.username,
    displayName: r.display_name,
    role: (r.role === 'admin' ? 'admin' : 'researcher') as UserRole,
    isActive: r.is_active === 1,
    createdAt: r.created_at
  }
}

export class AuthService {
  /** 当前登录会话的明文 token — 仅主进程内存 */
  private currentToken: string | null = null
  private currentUserId: string | null = null
  private currentExpiresAt = 0

  constructor(
    private readonly db: SqlDatabase,
    private readonly persistence: SessionPersistence
  ) {}

  getUserCount(): number {
    const row = this.db.prepare('SELECT COUNT(*) AS c FROM users').get() as { c: number }
    return row.c
  }

  /** 首启注册 — 仅当库内零用户时可用，第一个账号即本机管理员 */
  registerFirstAdmin(input: { username: string; displayName?: string; password: string }): AuthSession {
    const username = input.username.trim()
    const displayName = input.displayName?.trim() || null
    if (!username || username.length > 64) throw new Error('用户名长度需在 1-64 之间')
    if (input.password.length < 8 || input.password.length > 128) throw new Error('密码长度需在 8-128 之间')
    if (displayName && displayName.length > 32) throw new Error('显示名称最长 32 字符')
    if (this.getUserCount() > 0) throw new Error('本机已初始化，请直接登录')
    const id = `u-${Date.now()}-${randomBytes(3).toString('hex')}`
    const now = Date.now()
    this.db
      .prepare(
        'INSERT INTO users (id, username, display_name, password_hash, role, is_active, created_at, updated_at) VALUES (?, ?, ?, ?, ?, 1, ?, ?)'
      )
      .run(id, username, displayName, hashPassword(input.password), 'admin', now, now)
    return this.startSession(id)
  }

  login(username: string, password: string): AuthSession {
    const row = this.db.prepare('SELECT id, password_hash, is_active FROM users WHERE username = ?').get(username.trim()) as
      | { id: string; password_hash: string; is_active: number }
      | undefined
    if (!row || !verifyPassword(password, row.password_hash)) throw new Error('用户名或密码错误')
    if (row.is_active !== 1) throw new Error('账号已停用')
    return this.startSession(row.id)
  }

  /** 重启恢复 — 读持久化 token，校验未过期未吊销，滑动续期 */
  restore(): AuthSession | null {
    const token = this.persistence.load()
    if (!token) return null
    const row = this.db
      .prepare('SELECT id, user_id, expires_at FROM user_sessions WHERE token_hash = ? AND revoked_at IS NULL')
      .get(sha256(token)) as { id: string; user_id: string; expires_at: number } | undefined
    if (!row) {
      this.persistence.clear()
      return null
    }
    if (row.expires_at <= Date.now()) {
      this.persistence.clear()
      return null
    }
    const expiresAt = Date.now() + SESSION_TTL_MS
    this.db.prepare('UPDATE user_sessions SET expires_at = ?, last_seen_at = ? WHERE id = ?').run(expiresAt, Date.now(), row.id)
    this.currentToken = token
    this.currentUserId = row.user_id
    this.currentExpiresAt = expiresAt
    return { user: this.requireUser(), expiresAt }
  }

  logout(): boolean {
    if (this.currentToken) {
      this.db
        .prepare('UPDATE user_sessions SET revoked_at = ? WHERE token_hash = ?')
        .run(Date.now(), sha256(this.currentToken))
    }
    this.currentToken = null
    this.currentUserId = null
    this.currentExpiresAt = 0
    this.persistence.clear()
    return true
  }

  /** IPC 鉴权门 — 未登录抛错，由 ipc 层转成 AUTH_REQUIRED */
  requireUser(): LocalUser {
    if (!this.currentUserId) {
      const err = new Error('未登录') as Error & { code?: string }
      err.code = 'AUTH_REQUIRED'
      throw err
    }
    const row = this.db
      .prepare('SELECT id, username, display_name, role, is_active, created_at FROM users WHERE id = ?')
      .get(this.currentUserId) as UserRow | undefined
    if (!row || row.is_active !== 1) {
      this.logout()
      const err = new Error('登录状态已失效') as Error & { code?: string }
      err.code = 'AUTH_REQUIRED'
      throw err
    }
    return mapUser(row)
  }

  /** 当前会话是否仍有效（内存检查，不查库） */
  hasLiveSession(): boolean {
    return this.currentToken !== null && this.currentExpiresAt > Date.now()
  }

  private startSession(userId: string): AuthSession {
    const token = randomBytes(32).toString('hex')
    const now = Date.now()
    const expiresAt = now + SESSION_TTL_MS
    this.db
      .prepare(
        'INSERT INTO user_sessions (id, user_id, token_hash, issued_at, expires_at, last_seen_at) VALUES (?, ?, ?, ?, ?, ?)'
      )
      .run(`s-${now}-${randomBytes(3).toString('hex')}`, userId, sha256(token), now, expiresAt, now)
    this.currentToken = token
    this.currentUserId = userId
    this.currentExpiresAt = expiresAt
    this.persistence.persist(token)
    return { user: this.requireUser(), expiresAt }
  }
}
