// Auth Service — Phase 8-M1-G
// 本地账户 + 角色 + 会话管理. password_hash 用 scrypt (Node 内置, 无 native 依赖).

import { randomBytes, scryptSync, timingSafeEqual } from 'node:crypto'
import type { DatabaseService } from '../database.service'

export type UserRole = 'admin' | 'researcher' | 'viewer' | 'operator'

export interface User {
  id: string
  username: string
  displayName: string | null
  role: UserRole
  isActive: boolean
  lastLoginAt: number | null
  createdAt: number
  updatedAt: number
}

export interface Session {
  id: string
  userId: string
  issuedAt: number
  expiresAt: number
  lastSeenAt: number | null
  ipAddress: string | null
  userAgent: string | null
  revokedAt: number | null
}

export interface AuthService {
  createUser(input: { username: string; password: string; displayName?: string; role?: UserRole }): User
  login(username: string, password: string, context?: { ipAddress?: string; userAgent?: string }): { user: User; session: Session; token: string }
  logout(token: string): boolean
  validateToken(token: string): User | null
  listUsers(): User[]
  setUserActive(userId: string, isActive: boolean): boolean
  changePassword(userId: string, oldPassword: string, newPassword: string): boolean
  cleanupExpiredSessions(): number
  sessionTtlMs: number
}

const SCRYPT_N = 16384
const SCRYPT_R = 8
const SCRYPT_P = 1
const KEY_LEN = 32
const SALT_LEN = 16
const DEFAULT_SESSION_TTL_MS = 60 * 60 * 1000

function hashPassword(password: string): string {
  const salt = randomBytes(SALT_LEN)
  const hash = scryptSync(password.normalize('NFKC'), salt, KEY_LEN, { N: SCRYPT_N, r: SCRYPT_R, p: SCRYPT_P })
  return `scrypt$${SCRYPT_N}$${SCRYPT_R}$${SCRYPT_P}$${salt.toString('hex')}$${hash.toString('hex')}`
}

function verifyPassword(password: string, stored: string): boolean {
  const parts = stored.split('$')
  if (parts.length !== 6 || parts[0] !== 'scrypt') return false
  const salt = Buffer.from(parts[4], 'hex')
  const expected = Buffer.from(parts[5], 'hex')
  const actual = scryptSync(password.normalize('NFKC'), salt, expected.length, { N: Number(parts[1]), r: Number(parts[2]), p: Number(parts[3]) })
  if (actual.length !== expected.length) return false
  return timingSafeEqual(actual, expected)
}

class AuthServiceImpl implements AuthService {
  sessionTtlMs = DEFAULT_SESSION_TTL_MS

  constructor(private readonly getService: () => DatabaseService | null) {}

  createUser(input: { username: string; password: string; displayName?: string; role?: UserRole }): User {
    if (!input.username || input.username.length < 1 || input.username.length > 64) throw new Error('username 长度 1-64')
    if (!input.password || input.password.length < 8) throw new Error('password 长度 ≥ 8')
    const svc = this.getService()
    if (!svc) throw new Error('数据库未就绪')
    const existing = svc.db.queryOne<{ id: string }>('SELECT id FROM users WHERE username = ?', [input.username])
    if (existing) throw new Error('用户名已存在')
    const id = `user-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`
    const now = Date.now()
    const passwordHash = hashPassword(input.password)
    svc.db.execute(
      `INSERT INTO users (id, username, display_name, password_hash, role, is_active, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)`,
      [id, input.username, input.displayName ?? null, passwordHash, input.role ?? 'researcher', 1, now, now]
    )
    return { id, username: input.username, displayName: input.displayName ?? null, role: input.role ?? 'researcher', isActive: true, lastLoginAt: null, createdAt: now, updatedAt: now }
  }

  login(username: string, password: string, context: { ipAddress?: string; userAgent?: string } = {}): { user: User; session: Session; token: string } {
    const svc = this.getService()
    if (!svc) throw new Error('数据库未就绪')
    const row = svc.db.queryOne<Record<string, unknown>>('SELECT * FROM users WHERE username = ?', [username])
    if (!row) throw new Error('用户名或密码错误')
    if (Number(row['is_active']) !== 1) throw new Error('账户已停用')
    if (!verifyPassword(password, String(row['password_hash']))) throw new Error('用户名或密码错误')
    const sessionId = `sess-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`
    const token = randomBytes(32).toString('hex')
    const tokenHash = hashPassword(token).split('$').pop() ?? token
    const now = Date.now()
    const expiresAt = now + this.sessionTtlMs
    svc.db.execute(
      `INSERT INTO user_sessions (id, user_id, token_hash, issued_at, expires_at, ip_address, user_agent) VALUES (?, ?, ?, ?, ?, ?, ?)`,
      [sessionId, String(row['id']), tokenHash, now, expiresAt, context.ipAddress ?? null, context.userAgent ?? null]
    )
    svc.db.execute('UPDATE users SET last_login_at = ? WHERE id = ?', [now, String(row['id'])])
    return {
      user: this.mapUser(row),
      session: { id: sessionId, userId: String(row['id']), issuedAt: now, expiresAt, lastSeenAt: null, ipAddress: context.ipAddress ?? null, userAgent: context.userAgent ?? null, revokedAt: null },
      token
    }
  }

  logout(token: string): boolean {
    const svc = this.getService()
    if (!svc) return false
    const tokenHash = hashPassword(token).split('$').pop() ?? token
    const result = svc.db.execute(
      `UPDATE user_sessions SET revoked_at = ? WHERE token_hash = ? AND revoked_at IS NULL`,
      [Date.now(), tokenHash]
    )
    return result.changes > 0
  }

  validateToken(token: string): User | null {
    const svc = this.getService()
    if (!svc) return null
    const tokenHash = hashPassword(token).split('$').pop() ?? token
    const row = svc.db.queryOne<Record<string, unknown>>(
      `SELECT u.* FROM user_sessions s JOIN users u ON u.id = s.user_id WHERE s.token_hash = ? AND s.revoked_at IS NULL AND s.expires_at > ? LIMIT 1`,
      [tokenHash, Date.now()]
    )
    if (!row) return null
    return this.mapUser(row)
  }

  listUsers(): User[] {
    const svc = this.getService()
    if (!svc) return []
    return svc.db.query<Record<string, unknown>>('SELECT * FROM users ORDER BY created_at ASC').map((r) => this.mapUser(r))
  }

  setUserActive(userId: string, isActive: boolean): boolean {
    const svc = this.getService()
    if (!svc) return false
    const result = svc.db.execute('UPDATE users SET is_active = ?, updated_at = ? WHERE id = ?', [isActive ? 1 : 0, Date.now(), userId])
    return result.changes > 0
  }

  changePassword(userId: string, oldPassword: string, newPassword: string): boolean {
    if (!newPassword || newPassword.length < 8) throw new Error('新密码长度 ≥ 8')
    const svc = this.getService()
    if (!svc) return false
    const row = svc.db.queryOne<{ password_hash: string }>('SELECT password_hash FROM users WHERE id = ?', [userId])
    if (!row) return false
    if (!verifyPassword(oldPassword, row.password_hash)) throw new Error('原密码错误')
    const newHash = hashPassword(newPassword)
    const result = svc.db.execute('UPDATE users SET password_hash = ?, updated_at = ? WHERE id = ?', [newHash, Date.now(), userId])
    return result.changes > 0
  }

  cleanupExpiredSessions(): number {
    const svc = this.getService()
    if (!svc) return 0
    const result = svc.db.execute('DELETE FROM user_sessions WHERE expires_at < ? OR revoked_at IS NOT NULL', [Date.now()])
    return result.changes
  }

  private mapUser(row: Record<string, unknown>): User {
    return {
      id: String(row['id']),
      username: String(row['username']),
      displayName: row['display_name'] == null ? null : String(row['display_name']),
      role: String(row['role']) as UserRole,
      isActive: Number(row['is_active']) === 1,
      lastLoginAt: row['last_login_at'] == null ? null : Number(row['last_login_at']),
      createdAt: Number(row['created_at']),
      updatedAt: Number(row['updated_at'])
    }
  }
}

export function createAuthService(getService: () => DatabaseService | null): AuthService {
  return new AuthServiceImpl(getService)
}