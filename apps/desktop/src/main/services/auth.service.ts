// 本地账号服务 — 首启注册管理员 / 登录 / 会话恢复 / 登出。
// 铁律（骨架设计 §1.3）: 登录全程零网络请求；session token 只存主进程内存 + 库内哈希，
// 明文 token 仅通过注入的 hooks 持久化（生产为 safeStorage 加密，测试为内存）。
// 密码哈希格式 scrypt$N$r$p$salt$hash 与归档实现兼容。
import { createHash, randomBytes, scryptSync, timingSafeEqual } from 'node:crypto'
import type { SqlDatabase } from '../db/adapters'
import { SESSION_TTL_MS } from '@shared/constants'
import {
  CLAIMABLE_TABLES,
  claimSummary,
  planClaim,
  type CloudIdentity,
  type LocalUserRow
} from './cloud-identity'
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

/** 统一登录结果（工单 M2-3a+）：会话 + 首次认领信息 */
export interface CloudLoginResult {
  session: AuthSession
  /** 本次是否首次接入（首次会做数据认领） */
  firstClaim: boolean
  /** 本次是否新建了云端身份缓存行 */
  createdUser: boolean
  /** 认领到的数据条数（按表标签） */
  claimedCounts: Record<string, number>
  /** 面向用户的一句话（非首次为空串） */
  summary: string
}

export class AuthService {
  /** 当前登录会话的明文 token — 仅主进程内存 */
  private currentToken: string | null = null
  private currentUserId: string | null = null
  private currentExpiresAt = 0

  constructor(
    private readonly db: SqlDatabase,
    private readonly persistence: SessionPersistence,
    /**
     * 首次认领前的安全钩子（工单 M2-3a+ 附加安全网）。
     *
     * 认领会把旧本地账号名下的数据 re-point 到云端身份 —— 这是对**用户真实数据**的写操作。
     * 注入此钩子让装配层在认领前落一份数据库备份，出岔子可回滚。
     * 钩子失败**不阻塞登录**（只记日志），避免备份问题把用户锁在门外。
     */
    private readonly beforeClaim?: () => void
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

  /**
   * 统一登录（工单 M2-3a+ §2）：以**父级账号身份**登录本机。
   *
   * 流程：
   *   1. 决策（纯函数 planClaim）：复用已有缓存行 / 新建 / 认领旧本地账号数据
   *   2. 首次认领时，把「无主旧账号」名下的数据 re-point 到该云端身份（**一次性**）
   *   3. 起本地会话（令牌仍走 safeStorage；离线宽容依赖它）
   *
   * 多账号隔离：只认领 cloud_user_id 为 NULL 的旧行；已被别的云端账号认领过的行绝不参与。
   * 本地 users 表行保留（向前兼容），仅新增云端映射列。
   */
  loginWithCloud(identity: CloudIdentity): CloudLoginResult {
    const users = this.db
      .prepare('SELECT id, username, cloud_user_id AS cloudUserId FROM users')
      .all() as LocalUserRow[]
    const plan = planClaim(identity, users)

    let localUserId: string
    if (plan.reuseLocalUserId) {
      localUserId = plan.reuseLocalUserId
    } else {
      localUserId = `u-cloud-${identity.cloudUserId}`
      const now = Date.now()
      this.db
        .prepare(
          'INSERT INTO users (id, username, display_name, password_hash, role, is_active, created_at, updated_at, cloud_user_id, cloud_username) VALUES (?, ?, ?, ?, ?, 1, ?, ?, ?, ?)'
        )
        .run(
          localUserId,
          plan.createUsername ?? identity.cloudUsername,
          identity.cloudUsername,
          // 哨兵值：云端身份不持有本地密码，本地密码校验永不通过
          'cloud:sso',
          'member',
          now,
          now,
          String(identity.cloudUserId),
          identity.cloudUsername
        )
    }

    const counts: Record<string, number> = {}
    if (plan.firstClaim && plan.orphanUserIds.length > 0) {
      // ★ 认领前先落一份备份（写用户真实数据前的安全网）；失败不阻塞登录
      try {
        this.beforeClaim?.()
      } catch (e) {
        console.log(`[auth] 认领前备份失败（不阻塞登录）：${e instanceof Error ? e.message : String(e)}`)
      }
      const placeholders = plan.orphanUserIds.map(() => '?').join(',')
      for (const { table, label } of CLAIMABLE_TABLES) {
        try {
          const info = this.db
            .prepare(`UPDATE ${table} SET user_id = ? WHERE user_id IN (${placeholders})`)
            .run(localUserId, ...plan.orphanUserIds)
          const n = Number((info as { changes?: number }).changes ?? 0)
          if (n > 0) counts[label] = n
        } catch {
          // 表不存在（老库/未迁移）→ 跳过，不阻塞登录
        }
      }
      this.db.prepare('UPDATE users SET claimed_at = ? WHERE id = ?').run(Date.now(), localUserId)
      console.log(
        `[auth] 云端身份 ${identity.cloudUsername} 首次接入，认领：${Object.entries(counts)
          .map(([k, v]) => `${k} ${v} 条`)
          .join('、') || '无'}`
      )
    }

    const session = this.startSession(localUserId)
    return {
      session,
      firstClaim: plan.firstClaim,
      createdUser: plan.reuseLocalUserId === null,
      claimedCounts: counts,
      summary: plan.firstClaim ? claimSummary(counts) : ''
    }
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
