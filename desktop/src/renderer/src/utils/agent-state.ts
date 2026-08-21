// Agent State Model (Phase 5-C: Agent State Model Foundation).
//
// 纯 TypeScript, 0 依赖. 不修改 Phase 3-B0 frozen schema / Chat API / SSE.
// 仅消费当前流式状态 (StreamingMessage + Trace) 推导当前 Agent 状态.
//
// 状态机 (Phase 5-C frozen):
//   idle           - 没有任何 agent 活动
//   thinking       - streamingMessage.thinking 有值
//   planning       - 留口: Phase 5+ 接 plan_step event 后启用
//   tool_running   - 有 tool_call 状态为 'call_only' (结果未到)
//   waiting_user   - 留口: Phase 5+ 接权限/追问事件后启用
//   completed      - 流正常结束 (has content + no error)
//   failed         - 流异常或工具失败

import type { StreamingMessage } from '@shared/chat-types'
import type { TraceItem } from './chat-trace'

// ============ AgentState 类型 ============

export type AgentState =
  | 'idle'
  | 'thinking'
  | 'planning'
  | 'tool_running'
  | 'waiting_user'
  | 'completed'
  | 'failed'

export const AGENT_STATE_LABELS: Record<AgentState, string> = {
  idle: '空闲',
  thinking: '思考中',
  planning: '规划中',
  tool_running: '执行工具',
  waiting_user: '等待用户',
  completed: '已完成',
  failed: '失败'
}

export const AGENT_STATE_ICONS: Record<AgentState, string> = {
  idle: '○',
  thinking: '💭',
  planning: '🧭',
  tool_running: '🔧',
  waiting_user: '⏸',
  completed: '✅',
  failed: '❌'
}

// ============ deriveAgentState 主入口 ============

export interface DeriveAgentStateInput {
  /**
   * 当前 streamingMessage (Phase 5-A: 已有 tool_calls / thinking / rich_blocks 等).
   * 流结束后仍保留 (直到 selectSession 或 handleStreamError 清空).
   */
  streamingMessage?: StreamingMessage | null
  /**
   * 流 trace (Phase 5-B). 用于在 streamingMessage 缺失时退化 (Phase 5+ 场景).
   */
  trace?: TraceItem[]
  /** 流是否活跃 (Phase 5-B: isStreaming). */
  isStreaming?: boolean
  /** Phase 5-A: 最近流错误 (lastError). */
  lastError?: { code: string; message: string } | null
}

/**
 * 推导 AgentState (Phase 5-C frozen 规则).
 *
 * 优先级 (高 -> 低):
 *   1. failed      — lastError 存在 OR 最近 tool_result.error OR 流抛 error
 *   2. tool_running — 任何 tool_call 状态 = 'call_only' (即有结果未到)
 *   3. thinking    — streamingMessage.thinking 非空
 *   4. completed   — 流已结束且 content 非空
 *   5. idle        — 其它
 *
 * planning / waiting_user: Phase 5-C 留口, 不推导 (返回 idle).
 *
 * 纯函数 + 0 副作用. 失败静默: 输入缺字段时退化到 idle.
 */
export function deriveAgentState(input: DeriveAgentStateInput = {}): AgentState {
  const sm = input.streamingMessage ?? null
  const trace = input.trace ?? null
  const isStreaming = input.isStreaming ?? false
  const lastError = input.lastError ?? null

  // 1. failed
  if (lastError) return 'failed'

  // 2. tool_running (流中 + 任何 call_only 工具)
  if (isStreaming && sm) {
    const tools = sm.tool_calls ?? []
    if (tools.some((t) => t.status === 'call_only')) {
      return 'tool_running'
    }
  }
  // trace fallback (Phase 5-B 流已结束但 trace 还在)
  if (!isStreaming && trace) {
    const hasCallOnly = trace.some((it) => it.kind === 'tool_call' && it.tool.status === 'call_only')
    if (hasCallOnly) return 'tool_running'  // 历史 trace 残留 call_only
  }

  // 3. thinking
  if (isStreaming && sm) {
    const t = (sm.thinking ?? '').trim()
    if (t.length > 0) return 'thinking'
  }

  // 4. completed (流已结束 + 有内容)
  if (!isStreaming) {
    if (sm && typeof sm.content === 'string' && sm.content.trim().length > 0) {
      return 'completed'
    }
    if (trace) {
      const answer = trace.find((it) => it.kind === 'answer')
      if (answer && answer.content.length > 0) return 'completed'
    }
  }

  // 5. idle
  return 'idle'
}

// ============ 派生 UI 提示 (Phase 5-C optional) ============

export interface AgentStateHint {
  state: AgentState
  /** 短文本（标签） */
  label: string
  /** 图标 */
  icon: string
  /** 流中场景是否值得显示 (idle / completed 默认隐藏) */
  visible: boolean
}

/**
 * 构造 AgentStateHint (UI 用, 含可见性判断).
 * 流中显示 thinking / planning / tool_running / waiting_user.
 * failed / completed 仅错误或刚刚完成时短暂显示.
 * idle 不显示.
 */
export function deriveAgentStateHint(input: DeriveAgentStateInput = {}): AgentStateHint {
  const state = deriveAgentState(input)
  const isStreaming = input.isStreaming ?? false
  const visible =
    isStreaming ||
    state === 'failed' ||
    (state === 'completed' && (input.streamingMessage?.content ?? '').length > 0)
  return {
    state,
    label: AGENT_STATE_LABELS[state],
    icon: AGENT_STATE_ICONS[state],
    visible
  }
}
