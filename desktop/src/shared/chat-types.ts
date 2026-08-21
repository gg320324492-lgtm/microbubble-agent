// Chat 模块共享类型契约（Phase 2-Impl-3A 同步-only）。
// 任何后端字段改动必须先改 docs/desktop-conversion/chat-api-contract.md 再改本文件。

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
  // 后端 `tool_trace: list[dict[str, Any]]` —— 数组 (Phase 3+ 启用)
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

// ============ Send / Response (Phase 2-Impl-3A 同步) ============

export interface ChatRequest {
  message: string
  session_id: string               // 默认 "default"
  model?: string
  thinking_mode?: 'fast' | 'balanced' | 'deep' | null
  // Phase 3+ 不在 Phase 2-Impl-3A:
  // attached_knowledge_ids?: number[]
  // image_url?: string
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
  is_brief: boolean                       // DEPRECATED 永远 false
  rich_blocks: Record<string, unknown>[]
  tool_trace: Record<string, unknown>[]
  usage: ChatUsage | null
  duration_ms: number | null
  intent: Record<string, unknown> | null
  critique: Record<string, unknown> | null
}

// ============ StreamChunk 留口 (Phase 3+) ============

export interface StreamChunk {
  event: 'message_start' | 'content_delta' | 'tool_call' | 'message_end' | 'error' | string
  delta?: string
  tool?: string
  args?: Record<string, unknown>
  finish_reason?: 'stop' | 'length' | 'tool_calls' | string
  [k: string]: unknown
}

// ============ UI 派生 ============

/**
 * 派生：后端 ISO 时间字符串 → zh-CN 本地化短格式 (用于消息左侧时间轴)。
 */
export function formatMessageTime(iso: string | null | undefined): string {
  if (!iso) return ''
  const d = new Date(iso)
  if (isNaN(d.getTime())) return ''
  return d.toLocaleString('zh-CN', {
    hour: '2-digit',
    minute: '2-digit'
  })
}

/**
 * 派生：role 字符串 → UI 用户标签中文。
 */
export function roleLabel(role: ChatMessageRole): string {
  switch (role) {
    case 'user': return '你'
    case 'assistant': return '小气'
    case 'system': return '系统'
    case 'tool': return '工具'
    default: return String(role)
  }
}

/**
 * 派生：role 字符串 → 简短视觉图标。
 */
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
 * 派生：assistant 消息的 content 是否需要 Markdown 渲染。
 * 仅 assistant 渲染 (避免 user 输入的 emoji / 链接被误解)。
 */
export function shouldRenderAsMarkdown(role: ChatMessageRole): boolean {
  return role === 'assistant' || role === 'system'
}
