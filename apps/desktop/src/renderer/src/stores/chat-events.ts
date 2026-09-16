// 流式循环事件 → live 缓冲的纯逻辑（ChatPanel 消费；独立出来便于离线单测）
// 设计：循环期间消息尚未落库返回，渲染层用虚拟气泡展示 live 状态；
// send promise 返回后由带 meta 的持久化消息接管，live 缓冲清空。
import type { ChatStreamEvent, ToolCallRecord } from '@shared/types'

export interface LiveAgentState {
  text: string
  thinking: string
  tools: ToolCallRecord[]
  round: number
  label: string
}

export function createLiveState(): LiveAgentState {
  return { text: '', thinking: '', tools: [], round: 0, label: '' }
}

/** 原地更新 live 状态；done 事件由调用方处理（清空缓冲 = 真实消息接管） */
export function applyStreamEvent(live: LiveAgentState, e: ChatStreamEvent): void {
  if (e.type === 'delta') {
    live.text += e.delta
  } else if (e.type === 'thinking') {
    live.thinking += e.delta
  } else if (e.type === 'round') {
    live.round = e.round
    live.label = e.label
  } else if (e.type === 'tool') {
    // 状态流转：running → ok/error 以同 id 整卡替换（key 为 tool_use id）
    const i = live.tools.findIndex((t) => t.id === e.call.id)
    if (i >= 0) live.tools[i] = e.call
    else live.tools.push(e.call)
  }
}
