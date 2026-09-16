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

/** 会话（chat_sessions 行的跨进程投影） */
export interface ChatSession {
  id: string
  title: string
  createdAt: number
  updatedAt: number
}

/** 消息（chat_messages 行的跨进程投影） */
export interface ChatMessage {
  id: string
  sessionId: string
  role: 'user' | 'assistant' | 'system'
  content: string
  createdAt: number
}

export type ModelProtocol = 'openai' | 'anthropic'

/** 模型服务配置（apiKey 永不明文出主进程，只回掩码） */
export interface ModelProvider {
  id: string
  name: string
  protocol: ModelProtocol
  baseUrl: string
  model: string
  apiKeyMasked: string | null
  isDefault: boolean
}

export interface ModelProviderInput {
  id?: string
  name: string
  protocol: ModelProtocol
  baseUrl: string
  model: string
  /** 明文 key 仅在保存瞬间进入主进程，空串=保留旧 key */
  apiKey?: string
}

/** chat:stream-event 载荷 */
export type ChatStreamEvent =
  | { type: 'delta'; sessionId: string; messageId: string; delta: string }
  | { type: 'done'; sessionId: string; messageId: string; content: string }
  | { type: 'error'; sessionId: string; messageId: string; message: string }

/** 统一 IPC 返回包 — preload 解包，失败时 reject(Error) */
export type IpcResult<T> = { ok: true; data: T } | { ok: false; error: { code: string; message: string } }

/** 工作区状态（workspace:get 返回；root 为 null 表示未设置） */
export interface WorkspaceState {
  root: string | null
}

/** 工作区审计记录（workspace_audit 行的跨进程投影） */
export interface WorkspaceAuditEntry {
  id: number
  userId: string
  tool: string
  inputSummary: string
  ok: boolean
  createdAt: number
}
