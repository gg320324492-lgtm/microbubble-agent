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
  /** Agent 结构化信息（thinking/工具轮次），仅 assistant 消息可能非空 */
  meta: MessageMeta | null
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
  | { type: 'thinking'; sessionId: string; messageId: string; delta: string }
  | { type: 'tool'; sessionId: string; messageId: string; call: ToolCallRecord }
  | { type: 'round'; sessionId: string; messageId: string; round: number; label: string }
  | { type: 'done'; sessionId: string; messageId: string; content: string; meta?: MessageMeta | null }
  | { type: 'error'; sessionId: string; messageId: string; message: string }

/** 一次工具调用（工具卡片数据；status 流转 running → ok | error；写工具含确认态） */
export interface ToolCallRecord {
  id: string
  name: string
  input: unknown
  status: 'running' | 'ok' | 'error' | 'awaiting_confirm' | 'rejected'
  summary: string
  data?: unknown
}

/** 行级 diff 单行（工具卡片确认面板渲染） */
export interface DiffLine {
  kind: 'add' | 'del' | 'ctx'
  text: string
}

/** write_file 的 diff 数据（放 ToolCallRecord.data.diff；不进模型回喂） */
export interface FileDiff {
  path: string
  kind: 'create' | 'overwrite'
  lines: DiffLine[]
  truncated: boolean
}

/** assistant 消息的 Agent 结构化信息（chat_messages.meta JSON 列；工具卡片/思维链还原用） */
export interface MessageMeta {
  thinking?: string
  tools?: ToolCallRecord[]
  rounds?: number
  /** 用户中途停止（Esc/停止按钮），已产生的部分内容已保留 */
  stopped?: boolean
  /** 达到单次任务最大轮数（15）被截断 */
  hitRoundCap?: boolean
  /** false = 本次为纯对话降级（未设工作区或协议不支持工具） */
  toolsAvailable?: boolean
}

// ============ Agent 循环（主进程）与 Anthropic 协议形状 ============

export interface AnthropicToolDef {
  name: string
  description: string
  input_schema: Record<string, unknown>
}

/** 循环内部 turns 的内容块（assistant 回放用 text/tool_use，回喂用 tool_result） */
export type AgentContentBlock =
  | { type: 'text'; text: string }
  | { type: 'tool_use'; id: string; name: string; input: unknown }
  | { type: 'tool_result'; tool_use_id: string; content: string; is_error?: boolean }

/** 循环内部消息（content 可为纯文本或块数组；system 走顶层字段不进 turns） */
export interface AgentTurn {
  role: 'user' | 'assistant'
  content: string | AgentContentBlock[]
}

/** 单轮流式回调事件（主进程内部） */
export type StreamTurnEvent = { kind: 'text' | 'thinking'; delta: string }

export interface ToolUseBlock {
  id: string
  name: string
  input: Record<string, unknown>
}

export type StopReason = 'tool_use' | 'end_turn' | 'max_tokens' | 'stop_sequence' | 'aborted' | 'other'

export interface StreamTurnResult {
  stopReason: StopReason
  text: string
  thinking: string
  toolUses: ToolUseBlock[]
  /** 供下一轮回喂的 assistant content blocks（text + tool_use，thinking 不回传） */
  assistantBlocks: AgentContentBlock[]
}

export interface StreamTurnRequest {
  system: string
  turns: AgentTurn[]
  tools: AnthropicToolDef[]
  onEvent: (e: StreamTurnEvent) => void
}

/** Agent 循环的流式请求函数（真实实现 = 网关 streamAgentTurn；测试注入假网关） */
export type StreamTurnFn = (userId: string, sessionId: string, req: StreamTurnRequest) => Promise<StreamTurnResult>

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
