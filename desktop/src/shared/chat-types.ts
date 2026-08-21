// Chat 模块共享类型契约（Phase 2-Impl-3B 接 SSE streaming）。
// 任何后端字段改动必须先改 docs/desktop-conversion/chat-stream-contract.md 再改本文件。

// ============ 枚举与角色 ============

/**
 * 消息角色。后端约定 + 兼容兜底。
 * user / assistant 必支持; system / tool Phase 3+ 启用 (工具调用 / RAG)。
 */
export type ChatMessageRole = 'user' | 'assistant' | 'system' | 'tool' | string

export const CHAT_ROLE = {
  USER: 'user',
  ASSISTANT: 'assistant',
  SYSTEM: 'system',
  TOOL: 'tool'
} as const

// ============ Session Schema ============

export interface ChatSessionListItem {
  id: string
  title: string
  preview: string
  is_pinned: boolean
  is_archived: boolean
  tags: string[]
  message_count: number
  last_message_at: string | null
  created_at: string
  updated_at: string
}

export interface ChatSessionListResponse {
  items: ChatSessionListItem[]
  total: number
  page: number
  page_size: number
}

export interface ChatSessionOut {
  id: string
  user_id: number
  title: string
  preview: string
  is_pinned: boolean
  is_archived: boolean
  tags: string[]
  message_count: number
  last_message_at: string | null
  created_at: string
  updated_at: string
  deleted_at: string | null
  messages: ChatMessageOut[] | null
}

// ============ Message Schema ============

export interface ChatMessageOut {
  id: number
  session_id: string
  role: ChatMessageRole
  content: string
  rich_blocks: Record<string, unknown>[]
  tool_trace: Record<string, unknown>[]
  message_metadata: Record<string, unknown>
  is_partial: boolean
  is_deleted: boolean
  client_msg_id: string | null
  attached_knowledge_ids: number[]
  image_url: string | null
  created_at: string
}

export interface ChatMessagesPage {
  items: ChatMessageOut[]
  has_more: boolean
  next_after_id: number | null
}

// ============ Sync Chat (Phase 2-Impl-3A) ============

export interface ChatRequest {
  message: string
  session_id: string
  model?: string
  thinking_mode?: 'fast' | 'balanced' | 'deep' | null
}

export interface ChatUsage {
  input_tokens?: number
  output_tokens?: number
  total_tokens?: number
  [k: string]: number | undefined
}

export interface ChatResponse {
  content: string
  session_id: string
  file_url: string | null
  file_name: string | null
  knowledge_content: string | null
  is_brief: boolean
  rich_blocks: Record<string, unknown>[]
  tool_trace: Record<string, unknown>[]
  usage: ChatUsage | null
  duration_ms: number | null
  intent: Record<string, unknown> | null
  critique: Record<string, unknown> | null
}

// ============ Stream Event Types (Phase 2-Impl-3B) ============

/**
 * 后端 17 种 StreamEvent type 全集 (Pydantic Literal 镜像)。
 * 任何新 type 上线时同步扩展。
 */
export type StreamEventType =
  | 'text_delta' | 'tool_use' | 'tool_result' | 'rich_block'
  | 'thinking' | 'brief' | 'detail' | 'error' | 'done'
  | 'intent_detected' | 'plan_step' | 'tool_compressed'
  | 'synthesis_start' | 'critique' | 'retry'
  | 'message_persisted' | 'sync_required'
  | 'refs' | 'suggestions'
  | string  // 兜底

/**
 * RichBlock 简化形状 (实际后端用 RichBlock pydantic model)。
 * Phase 2 不渲染, Phase 3 接。
 */
export interface StreamRichBlock {
  type: string
  data?: unknown
  title?: string
  [k: string]: unknown
}

/**
 * 后端 StreamEvent 形状 (Pydantic model_dump_json 反序列化的镜像)。
 */
export interface StreamEvent {
  type: StreamEventType

  // text_delta / brief / detail
  delta?: string

  // tool_use
  tool_name?: string
  tool_input?: Record<string, unknown>
  tool_use_id?: string

  // tool_result
  tool_output?: Record<string, unknown>
  tool_duration_ms?: number
  tool_error?: string

  // rich_block
  block?: StreamRichBlock

  // thinking / plan_step
  label?: string

  // error
  code?: string
  message?: string

  // done
  usage?: {
    input_tokens?: number
    output_tokens?: number
    total_tokens?: number
    [k: string]: number | undefined
  }
  duration_ms?: number
  session_id?: string

  // #043 message_persisted
  message_id?: number
  role?: string
  client_msg_id?: string
  is_partial?: boolean

  // #043 sync_required
  reason?: 'aborted' | 'error' | string
}

/**
 * StreamingRequest —— 与 ChatRequest 同形 (Phase 2 简化, 仅 message + session_id)。
 */
export interface ChatStreamRequest {
  message: string
  session_id: string
  model?: string
  thinking_mode?: 'fast' | 'balanced' | 'deep' | null
}

/**
 * Stream done payload (Phase 2 简化, 后端 done event 已携带 usage/duration_ms/session_id)。
 * 主进程仅作为结束信号 (ok=true)。
 */
export interface StreamEndPayload {
  ok: true
}

/**
 * Stream error payload (Phase 2 统一规整)。
 */
export interface StreamErrorPayload {
  code: string                  // 业务 code (NETWORK_ERROR / STREAM_ERROR / ...)
  message: string
}

/**
 * 主进程 → renderer 推 chunk 时, 用 discriminated union。
 * Phase 2 简化: 直接发原始 StreamEvent payload; message_id / role (persisted) 字段也走这里。
 */
export type ChunkPayload = StreamEvent

/**
 * Renderer 端维护 streamingMessage 形态 (in-memory, 不持久化)。
 */
export interface StreamingMessage {
  id: number                              // 临时 ID (Date.now())
  session_id: string
  role: ChatMessageRole
  content: string                         // 累加中的 markdown 文本
  thinking: string | null                 // 最新 thinking label
  rich_blocks: Record<string, unknown>[]
  tool_trace: Record<string, unknown>[]
  started_at: string                      // ISO
  finished_at: string | null
  /** Phase 3+ 持久化消息 ID (#043) */
  persisted_message_id: number | null
}

// ============ UI 派生 ============

export function formatMessageTime(iso: string | null | undefined): string {
  if (!iso) return ''
  const d = new Date(iso)
  if (isNaN(d.getTime())) return ''
  return d.toLocaleString('zh-CN', { hour: '2-digit', minute: '2-digit' })
}

export function roleLabel(role: ChatMessageRole): string {
  switch (role) {
    case 'user': return '你'
    case 'assistant': return '小气'
    case 'system': return '系统'
    case 'tool': return '工具'
    default: return String(role)
  }
}

export function roleIcon(role: ChatMessageRole): string {
  switch (role) {
    case 'user': return '👤'
    case 'assistant': return '🧠'
    case 'system': return '⚙️'
    case 'tool': return '🔧'
    default: return '·'
  }
}

/**
 * 派生：assistant / system 消息用 MarkdownViewer 渲染; user / tool 纯文本。
 */
export function shouldRenderAsMarkdown(role: ChatMessageRole): boolean {
  return role === 'assistant' || role === 'system'
}
