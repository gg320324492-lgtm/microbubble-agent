import { describe, it, expect } from 'vitest'
import {
  deriveAgentState,
  deriveAgentStateHint,
  AGENT_STATE_LABELS,
  AGENT_STATE_ICONS,
  type AgentState
} from '../../src/renderer/src/utils/agent-state'
import type { StreamingMessage, ToolCallSnapshot } from '../../src/shared/chat-types'

/**
 * Phase 5-C: Agent State Model unit tests.
 *
 * 覆盖 spec Step 6 6 场景:
 *   1. idle
 *   2. thinking
 *   3. tool_running
 *   4. failed
 *   5. completed
 *   6. session isolation (UI hint 跟随 store session)
 */

function tool(
  id: string,
  status: 'call_only' | 'success' | 'error' = 'call_only'
): ToolCallSnapshot {
  return {
    tool_use_id: id,
    name: 'test_tool',
    input: {},
    started_at: '2026-08-21T00:00:00Z',
    finished_at: status === 'call_only' ? null : '2026-08-21T00:00:01Z',
    status,
    output: status === 'success' ? { ok: true } : null,
    error: status === 'error' ? 'fail' : null,
    duration_ms: status === 'call_only' ? null : 100
  }
}

function streamingMessage(overrides: Partial<StreamingMessage> = {}): StreamingMessage {
  return {
    id: 1,
    session_id: 'default',
    role: 'assistant' as const,
    content: '',
    thinking: null,
    rich_blocks: [],
    tool_calls: [],
    citations: [],
    started_at: '2026-08-21T00:00:00Z',
    finished_at: null,
    persisted_message_id: null,
    client_msg_id: 'cm_test',
    ...overrides
  }
}

describe('AgentState (Spec 1: idle)', () => {
  it('无输入 -> idle', () => {
    expect(deriveAgentState({})).toBe('idle')
  })

  it('无 streamingMessage -> idle', () => {
    expect(deriveAgentState({ isStreaming: false })).toBe('idle')
  })

  it('空 content -> idle', () => {
    expect(deriveAgentState({
      streamingMessage: streamingMessage({ content: '' }),
      isStreaming: false
    })).toBe('idle')
  })
})

describe('AgentState (Spec 2: thinking)', () => {
  it('isStreaming + thinking label -> thinking', () => {
    expect(deriveAgentState({
      streamingMessage: streamingMessage({ thinking: '分析用户意图' }),
      isStreaming: true
    })).toBe('thinking')
  })

  it('thinking 但 isStreaming=false -> 不推导 thinking (历史态)', () => {
    expect(deriveAgentState({
      streamingMessage: streamingMessage({ thinking: 'old thinking' }),
      isStreaming: false
    })).toBe('idle')
  })

  it('thinking 前缀空白 trim (空 -> 不触发)', () => {
    expect(deriveAgentState({
      streamingMessage: streamingMessage({ thinking: '   ' }),
      isStreaming: true
    })).toBe('idle')
  })
})

describe('AgentState (Spec 3: tool_running)', () => {
  it('isStreaming + 1 call_only tool -> tool_running', () => {
    expect(deriveAgentState({
      streamingMessage: streamingMessage({ tool_calls: [tool('t1', 'call_only')] }),
      isStreaming: true
    })).toBe('tool_running')
  })

  it('混合 success + call_only 仍 tool_running', () => {
    expect(deriveAgentState({
      streamingMessage: streamingMessage({
        tool_calls: [tool('t1', 'success'), tool('t2', 'call_only')]
      }),
      isStreaming: true
    })).toBe('tool_running')
  })

  it('全部 tool success -> 不是 tool_running', () => {
    expect(deriveAgentState({
      streamingMessage: streamingMessage({ tool_calls: [tool('t1', 'success')] }),
      isStreaming: true
    })).toBe('idle')
  })

  it('tool_running 优先级 > thinking', () => {
    expect(deriveAgentState({
      streamingMessage: streamingMessage({
        thinking: 'analysis',
        tool_calls: [tool('t1', 'call_only')]
      }),
      isStreaming: true
    })).toBe('tool_running')
  })
})

describe('AgentState (Spec 4: failed)', () => {
  it('lastError 存在 -> failed', () => {
    expect(deriveAgentState({
      lastError: { code: 'STREAM_ERROR', message: 'fail' }
    })).toBe('failed')
  })

  it('failed 优先级 > tool_running (即使有 call_only tool)', () => {
    expect(deriveAgentState({
      streamingMessage: streamingMessage({ tool_calls: [tool('t1', 'call_only')] }),
      isStreaming: true,
      lastError: { code: 'CANCEL', message: 'user' }
    })).toBe('failed')
  })
})

describe('AgentState (Spec 5: completed)', () => {
  it('!isStreaming + content 非空 -> completed', () => {
    expect(deriveAgentState({
      streamingMessage: streamingMessage({ content: 'final answer' }),
      isStreaming: false
    })).toBe('completed')
  })

  it('!isStreaming + thinking 有值 (历史) -> completed (content 优先)', () => {
    expect(deriveAgentState({
      streamingMessage: streamingMessage({ thinking: 'old', content: 'ok' }),
      isStreaming: false
    })).toBe('completed')
  })

  it('!isStreaming + content 空 -> idle', () => {
    expect(deriveAgentState({
      streamingMessage: streamingMessage({ content: '' }),
      isStreaming: false
    })).toBe('idle')
  })
})

describe('AgentState (Spec 6: session isolation)', () => {
  it('流中 session A 的 call_only tool -> 切 session B 后 (selectSession 清 streamingMessage) -> idle', () => {
    // 模拟 selectSession: streamingMessage 清空
    // 然后 deriveAgentState 应该返 idle (因为没流中数据)
    const hintA = deriveAgentStateHint({
      streamingMessage: streamingMessage({ tool_calls: [tool('t1', 'call_only')] }),
      isStreaming: true
    })
    expect(hintA.state).toBe('tool_running')

    // 切 session 后 streamingMessage null
    const hintB = deriveAgentStateHint({
      streamingMessage: null,
      isStreaming: false
    })
    expect(hintB.state).toBe('idle')
  })

  it('hint.visible: 流中 -> true', () => {
    const hint = deriveAgentStateHint({
      streamingMessage: streamingMessage({ tool_calls: [tool('t1', 'call_only')] }),
      isStreaming: true
    })
    expect(hint.visible).toBe(true)
  })

  it('hint.visible: idle -> false (普通消息)', () => {
    expect(deriveAgentStateHint({}).visible).toBe(false)
  })

  it('hint.visible: completed -> true (短时间内仍展示)', () => {
    const hint = deriveAgentStateHint({
      streamingMessage: streamingMessage({ content: 'final' }),
      isStreaming: false
    })
    expect(hint.state).toBe('completed')
    expect(hint.visible).toBe(true)
  })
})

describe('AGENT_STATE_LABELS / ICONS', () => {
  it('all 7 states have label', () => {
    const expectedStates: AgentState[] = ['idle', 'thinking', 'planning', 'tool_running', 'waiting_user', 'completed', 'failed']
    for (const s of expectedStates) {
      expect(AGENT_STATE_LABELS[s]).toBeTruthy()
      expect(AGENT_STATE_ICONS[s]).toBeTruthy()
    }
  })
})
