// Chat 模块共享类型契约（Phase 3-A: Reliability & UX Hardening）。
// 任何后端字段改动必须先改 docs/desktop-conversion/chat-stream-contract.md 再改本文件。

// ============ 枚举与角色 ============

/**
 * 消息角色。后端约定 + 兼容兜底。
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

// ============ Stream Event Types (Phase 2-Impl-3B, Phase 3-B0 frozen) ============

/**
 * 后端 StreamEvent type 全集 (Pydantic Literal 镜像, Phase 3-B0 frozen).
 *
 * Phase 3-B0 协议冻结:
 *   - 8 核心 type (Phase 3-A 显示接入): text_delta / thinking / tool_use /
 *     tool_result / citation / rich_block / done / error
 *   - 9 拓展 type (Phase 2 兼容 + Phase 3+ 接入): brief / detail /
 *     intent_detected / plan_step / tool_compressed / synthesis_start /
 *     critique / retry / message_persisted / sync_required / refs /
 *     suggestions
 *
 * Phase 3+ (RAG/Citation 接入) 必接:
 *   - 'citation': RAG 引用的结构化字段
 *   - 'tool_use' / 'tool_result': 工具调用场景 (Phase 3-B0+ 渲染)
 *
 * 任何新增 event type 必须: ① 后端 StreamEvent Literal 加同名字段
 *   ② shared/chat-types.ts StreamEventType 同步
 *   ③ 本类型扩展 interface 加对应字段
 *   ④ chat-stream-contract.md §3 同步表格
 */
export type StreamEventType =
  // === 8 核心 ===
  | 'text_delta'
  | 'thinking'
  | 'tool_use'
  | 'tool_result'
  | 'citation'
  | 'rich_block'
  | 'done'
  | 'error'
  // === 9 拓展 (后端已实现 / Phase 3+ 渐进接入) ===
  | 'brief'               // DEPRECATED - v1 客户端兼容 (Phase 1 简答)
  | 'detail'              // DEPRECATED - v1 客户端兼容
  | 'intent_detected'     // 意图分类 (方案 C)
  | 'plan_step'           // 工具规划单步
  | 'tool_compressed'     // Haiku 压缩工具结果
  | 'synthesis_start'     // 综合阶段开始
  | 'critique'            // 自评结果
  | 'retry'               // critique 低分触发重试
  | 'message_persisted'   // #043 持久化成功
  | 'sync_required'       // #043 中断提示前端重新拉历史
  | 'refs'                // #CHAT-P0-A 知识引用 (后端旧名, Phase 3+ 兼容)
  | 'suggestions'         // #CHAT-P0-A 追问 chips
  | string  // 兜底 (新 event type 出现时不会被 TS 编译拦截)

export interface StreamRichBlock {
  type: string
  data?: unknown
  title?: string
  [k: string]: unknown
}

/**
 * Citation 留口 (Phase 3+ 接 RAG).
 *
 * 后端 StreamEvent.citation 是 list[dict] (每个引用一条); 当前 Phase 3-A 不接,
 * Phase 3-B0 冻结 schema 准备 Phase 3+ 接入.
 */
export interface StreamCitationEntry {
  knowledgeId: number
  title: string
  snippet?: string
  url?: string
  score?: number                         // 0..1
  source?: 'kb' | 'memory' | 'auto_research' | string
  [k: string]: unknown                   // 后续 RAG 字段扩展
}

export interface StreamEvent {
  type: StreamEventType

  // text_delta / brief / detail
  delta?: string

  // === tool ===
  tool_name?: string
  tool_input?: Record<string, unknown>
  tool_use_id?: string
  tool_output?: Record<string, unknown>
  tool_duration_ms?: number
  tool_error?: string

  // === citation (Phase 3+ 接入 RAG) ===
  citation?: StreamCitationEntry | StreamCitationEntry[]

  // === rich_block ===
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

  // #CHAT-P0-A refs (deprecated alias, Phase 3+ 用 citation)
  refs?: StreamCitationEntry[]

  // suggestions 追问 chips (Phase 3+ 启用)
  suggestions?: unknown[]
}

export interface ChatStreamRequest {
  message: string
  session_id: string
  model?: string
  thinking_mode?: 'fast' | 'balanced' | 'deep' | null
}

export interface StreamEndPayload {
  ok: true
}

export interface StreamErrorPayload {
  code: string
  message: string
}

export type ChunkPayload = StreamEvent

// ============ Phase 3-A: Reliability & UX Hardening ============

/**
 * Stream context —— IPC push 时携带, renderer 校验 session 匹配.
 *
 * 流式 chunk / end / error 总是带 StreamContext.
 * renderer 端如果 currentSessionId !== ctx.sessionId → ignore (用户已切换会话).
 */
export interface StreamContext {
  streamId: string
  sessionId: string
}

/**
 * MessageIdentity —— 客户端 msg_id (UUID) + 服务端 msg_id 同步.
 *
 * 流程:
 *   renderer 生成 clientMsgId (UUID v4) for optimistic msg
 *   POST /chat/stream { message, session_id, client_msg_id (Phase 2-Impl-3A backend 已支持 #043 client_msg_id 幂等键, 但本 Phase 不传 - 留 Phase 3+ backend 升级时启用) }
 *   backend message_persisted event: { message_id, client_msg_id }
 *   renderer 替换 optimistic 的 clientMsgId 对应 msg 的 id 为服务端 message_id
 *
 * Phase 3-A: clientMsgId 用于内部追踪 + 重试去重。server message_id 同步
 * 走 message_persisted event. (Phase 2-Impl-3A backend 支持 #043 client_msg_id 字段;
 * Phase 3-A 不主动传 client_msg_id 给 backend, 仅作消息内部映射)
 */
export interface MessageIdentity {
  clientMsgId: string                       // UUID v4
  serverMessageId: number | null           // null 直到 message_persisted 事件到达
}

/**
 * 流式 chunk IPC payload (Phase 3-A 重塑):
 *   [StreamContext, StreamEvent]
 *   renderer 按 context.sessionId 匹配才处理.
 *
 * Phase 2-Impl-3B 用 [streamId, event] —— Phase 3-A 升为 context + 携带 sessionId.
 */
export type StreamChunkIpcPayload = [StreamContext, StreamEvent]
export type StreamEndIpcPayload = [StreamContext, StreamEndPayload]
export type StreamErrorIpcPayload = [StreamContext, StreamErrorPayload]

// ============ Renderer Streaming Message ============

export interface StreamingMessage {
  id: number
  session_id: string
  role: ChatMessageRole
  content: string
  thinking: string | null
  rich_blocks: Record<string, unknown>[]
  tool_trace: Record<string, unknown>[]
  started_at: string
  finished_at: string | null
  /** Phase 3-A 服务端同步后填 */
  persisted_message_id: number | null
  /** Phase 3-A 内部 clientMsgId, 用来在 messages array 中 find-and-replace 服务端 messageId */
  client_msg_id: string
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

export function shouldRenderAsMarkdown(role: ChatMessageRole): boolean {
  return role === 'assistant' || role === 'system'
}

/**
 * 生成 clientMsgId (UUID v4-ish, 主进程兼容). Phase 3-A 不依赖外部 uuid 包.
 */
export function generateClientMsgId(): string {
  // 18 char base36 随机 + epoch ms
  const r = Math.random().toString(36).slice(2, 12)
  const t = Date.now().toString(36)
  return `cm_${t}_${r}`
}
