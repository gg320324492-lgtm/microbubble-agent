// 跨进程共享领域类型 — 账号/设置/应用信息
export type UserRole = 'admin' | 'researcher'

export interface LocalUser {
  id: string
  username: string
  displayName: string | null
  role: UserRole
  isActive: boolean
  createdAt: number
}

export interface AuthSession {
  user: LocalUser
  /** epoch ms — 会话过期时间（60min 滑动续期） */
  expiresAt: number
}

export interface AppInfo {
  version: string
  platform: string
  dbPath: string
  appName: string
}

/** 统一 IPC 返回包 — preload 解包，失败时 reject(Error) */
export type IpcResult<T> = { ok: true; data: T } | { ok: false; error: { code: string; message: string } }
