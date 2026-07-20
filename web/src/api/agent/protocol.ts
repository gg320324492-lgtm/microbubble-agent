/**
 * SSE 事件类型定义（与后端 app/agent/protocol.py StreamEvent 对齐）
 *
 * 新增事件类型时：改后端 StreamEvent + 改这里 + 改 chat.ts / sse.ts 的 switch case
 *
 * ⚠️ SSE 事件 delta 语义铁律（CLAUDE.md 552 行）⚠️
 * 每个事件类型必须标注 [increment] 或 [snapshot]：
 * - [increment] delta 是新增 token，前端必须 `content += delta`
 * - [snapshot] delta 是完整快照，前端必须 `content = delta`（替换）或不 append
 * 混用会导致 2026-06-12 brief 重复输出 bug（commit cf70ff5）再现。
 */

export type StreamEventType =
  // ===== 原 9 种事件 =====
  | 'text_delta'        // [increment] 文本逐字流
  | 'tool_use'          // [snapshot] 工具调用开始
  | 'tool_result'       // [snapshot] 工具调用结果
  | 'rich_block'        // [snapshot] 富文本块
  | 'thinking'          // [snapshot] "正在 X..." 提示
  | 'brief'             // [snapshot, deprecated] v1 客户端兼容，v2+ 忽略
  | 'detail'            // [snapshot, deprecated] v1 客户端兼容，v2+ 忽略
  | 'error'             // [snapshot] 错误
  | 'done'              // [snapshot] 流结束
  // ===== 2026-06-14 方案 C 新增 6 种事件 =====
  | 'intent_detected'   // [snapshot] 意图分类结果
  | 'plan_step'         // [snapshot] 工具规划单步
  | 'tool_compressed'   // [snapshot] 工具结果被 Haiku 压缩
  | 'synthesis_start'   // [snapshot] 综合阶段开始（无 delta）
  | 'critique'          // [snapshot] 自评结果
  | 'retry'             // [snapshot] critique 低分触发重试，前端必须清空 content
  // ===== 2026-06-29 #043 新增 2 种事件 =====
  | 'message_persisted' // [snapshot] 后端已落库某条消息（user 流开始时 + assistant 流结束时 各 yield 一次）
  | 'sync_required'     // [snapshot] 流式中断/异常，前端需重新拉历史（流中断兜底）

export type RichBlockType =
  | 'meeting'
  | 'task_list'
  | 'knowledge_ref'
  | 'formula'
  | 'hypothesis'
  | 'member'
  | 'project'
  | 'transcript'
  | 'chart'
  | 'table'
  | 'fallback'

export interface RichBlock {
  type: RichBlockType
  data: Record<string, any>
  title?: string
  compact?: boolean
  timestamp?: string
  // 2026-06-14 方案 C 新增：折叠态展示 + LLM-driven 决策
  summary?: string                   // 折叠态一行摘要，如「成员推荐 3 人（27→3）」
  expanded?: boolean                 // 当前是否展开（前端 toggle 时写入）
  collapsed_by_default?: boolean     // LLM 在 synthesis 阶段可 override 默认折叠/展开
}

/** 意图分类（intent_detected 事件） */
export interface IntentInfo {
  category: 'recommend_person' | 'search_info' | 'explain_concept' | 'execute_action' | 'data_query' | 'casual_chat'
  confidence: number
  keywords: string[]
  suggested_tools: string[]
  reasoning: string
}

/** 工具规划单步（plan_step 事件） */
export interface PlanStep {
  step: string
  tool?: string
  status: 'pending' | 'running' | 'done'
}

/** 工具结果压缩信息（tool_compressed 事件） */
export interface ToolCompression {
  original_count: number
  selected_count: number
  reasoning: string
  summary: string
}

/** 自评结果（critique 事件） */
export interface CritiqueInfo {
  score: number  // 1-10
  addresses_question: boolean
  has_synthesis: boolean
  has_citations: boolean
  missing: string[]
  suggestion: string
}

export interface StreamEvent {
  type: StreamEventType
  // text_delta / brief / detail
  delta?: string
  // tool_use
  tool_name?: string
  tool_input?: Record<string, any>
  tool_use_id?: string
  // tool_result
  tool_output?: Record<string, any>
  tool_duration_ms?: number
  tool_error?: string
  // rich_block
  block?: RichBlock
  // thinking / plan_step
  label?: string
  // error
  code?: string
  message?: string
  // done
  usage?: { input_tokens: number; output_tokens: number; total_tokens: number }
  duration_ms?: number
  session_id?: string
  // ===== 方案 C 新增字段 =====
  // intent_detected
  intent?: IntentInfo
  // plan_step
  step?: string
  plan_status?: 'pending' | 'running' | 'done'
  // tool_compressed
  compression?: ToolCompression
  // critique
  critique?: CritiqueInfo
  // retry
  retry_reason?: string
  retry_count?: number
  // ===== #043 新增字段（message_persisted 事件） =====
  message_id?: number                                   // server message id
  persisted_role?: 'user' | 'assistant' | 'system' | 'tool'
  persisted_client_msg_id?: string                      // 幂等键
  persisted_is_partial?: boolean                       // 是否 partial（流式中断标记）
  // ===== #043 新增字段（sync_required 事件） =====
  sync_reason?: 'aborted' | 'error'                     // 中断原因
  // ===== 2026-07-13 #P1 三档推理模式反馈字段 (done 事件携带) =====
  // mode: 实际跑的 mode (fast / balanced / deep)
  mode?: 'fast' | 'balanced' | 'deep'
  // model: 实际跑的 model name (Ollama tag 或 Anthropic model id)
  model?: string
  // thinking_tokens_used: Anthropic SDK 返回的 thinking tokens (Ollama deepseek-r1 当前返 0)
  thinking_tokens_used?: number
}
