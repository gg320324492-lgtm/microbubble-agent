/**
 * SSE 事件类型定义（与后端 app/agent/protocol.py StreamEvent 对齐）
 *
 * 新增事件类型时：改后端 StreamEvent + 改这里 + 改 chat.ts / sse.ts 的 switch case
 */

export type StreamEventType =
  | 'text_delta'
  | 'tool_use'
  | 'tool_result'
  | 'rich_block'
  | 'thinking'
  | 'brief'
  | 'detail'
  | 'error'
  | 'done'

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
  // thinking
  label?: string
  // error
  code?: string
  message?: string
  // done
  usage?: { input_tokens: number; output_tokens: number; total_tokens: number }
  duration_ms?: number
  session_id?: string
}
