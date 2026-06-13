/**
 * useChatStream Stage 4 纯逻辑测试（方案 C 2026-06-14）
 *
 * 不调用真实 useChatStream()（避免依赖 sessionsStore / Element Plus 等重组件），
 * 抽出 useChatStream 内部的关键事件处理逻辑，单独测试其行为。
 *
 * 覆盖：
 * - tool_compressed 事件应附加 compression 到最近同名的 tool 项
 * - retry 事件应清空 content 并增加 retryCount
 * - critique 事件低分时应在 toolTrace 加 ⚠️ 徽章
 * - intent_detected 事件应在 toolTrace 顶部加 🧠 意图
 * - text_delta 长度异常检查（防 2026-06-12 brief 重复 bug）
 * - stopGeneration 行为模拟：state='aborted' + abort controller
 * - abort 状态机：state==='aborted' 时跳过 switch case
 *
 * 跑法：npx vitest run src/composables/__tests__/useChatStream.stage4.test.js
 */

import { describe, it, expect, vi } from 'vitest'

// ============================================================================
// 工具函数（从 useChatStream.ts 抽出的纯逻辑）
// ============================================================================

/**
 * 模拟 useChatStream.sendSSE 内 switch case 的 tool_compressed 分支
 * 真实代码：
 *   const lastTool = [...currentAssistant.toolTrace!].reverse()
 *     .find((t) => t.type === 'tool' && t.name === evt.tool_name)
 *   if (lastTool) lastTool.compression = evt.compression
 *   currentAssistant.toolTrace!.push({ type: 'thinking', label: evt.label || ... })
 */
function applyToolCompressed(assistant, evt) {
  const lastTool = [...assistant.toolTrace].reverse().find(
    (t) => t.type === 'tool' && t.name === evt.tool_name,
  )
  if (lastTool) {
    lastTool.compression = evt.compression
  }
  assistant.toolTrace.push({
    type: 'thinking',
    label: evt.label || `🗜️ 压缩：${evt.compression?.summary || ''}`,
  })
}

/** 模拟 retry 事件分支 */
function applyRetry(assistant, evt) {
  assistant.retryCount = (assistant.retryCount || 0) + 1
  assistant.content = ''  // 关键：清空避免重复
  assistant.toolTrace.push({
    type: 'thinking',
    label: `🔄 重试中（第 ${assistant.retryCount} 次）：${evt.retry_reason || ''}`,
  })
}

/** 模拟 critique 事件分支（低分加 ⚠️） */
function applyCritique(assistant, evt) {
  assistant.critique = evt.critique || { score: 0, suggestion: evt.label }
  if (evt.critique && evt.critique.score < 7) {
    assistant.toolTrace.push({
      type: 'thinking',
      label: `⚠️ 自评 ${evt.critique.score}/10 — ${evt.critique.suggestion || ''}`,
    })
  } else if (evt.critique) {
    assistant.toolTrace.push({
      type: 'thinking',
      label: `📊 自评 ${evt.critique.score}/10`,
    })
  }
}

/** 模拟 intent_detected 事件分支 */
function applyIntentDetected(assistant, evt) {
  assistant.intent = evt.intent || { category: evt.label || 'unknown', confidence: 0 }
  assistant.toolTrace.push({
    type: 'thinking',
    label: evt.label || `🧠 意图：${evt.intent?.category || 'unknown'}`,
  })
}

/** 模拟 text_delta 长度异常检查（防 brief 重复 bug） */
function checkTextDeltaAnomaly(prevContent, delta) {
  if (delta && delta.length > 100) {
    const prevPrefix = (prevContent || '').slice(0, 50)
    if (prevPrefix && !delta.includes(prevPrefix)) {
      return { anomalous: true, message: `长度异常：${delta.length} 字` }
    }
  }
  return { anomalous: false }
}

/** 模拟 stopGeneration 行为 */
function simulateStopGeneration(assistant, controller) {
  if (!controller) return
  controller.abort()
  if (assistant && assistant.state === 'streaming') {
    assistant.state = 'aborted'
  }
}

/** 模拟 abort 状态机守卫 */
function shouldSkipEvent(assistant) {
  return assistant && assistant.state === 'aborted'
}

// ============================================================================
// 测试
// ============================================================================

describe('useChatStream Stage 4 — 6 个新事件 case', () => {
  it('tool_compressed 应附加 compression 到最近同名的 tool 项', () => {
    const assistant = {
      content: '',
      richBlocks: [],
      toolTrace: [
        { type: 'tool', name: 'query_members', state: 'done', duration_ms: 50 },
        { type: 'tool', name: 'search_knowledge', state: 'done', duration_ms: 80 },
      ],
    }
    applyToolCompressed(assistant, {
      type: 'tool_compressed',
      tool_name: 'query_members',
      compression: { original_count: 27, selected_count: 3, summary: '成员 3 人（27→3）' },
      label: '🗜️ 压缩 query_members',
    })
    const queryMembers = assistant.toolTrace.find((t) => t.name === 'query_members')
    expect(queryMembers.compression).toBeDefined()
    expect(queryMembers.compression.summary).toContain('3 人')
  })

  it('retry 应清空 content 并增加 retryCount', () => {
    const assistant = {
      content: '旧的失败回答',
      richBlocks: [],
      toolTrace: [],
      retryCount: undefined,
    }
    applyRetry(assistant, {
      type: 'retry',
      retry_reason: 'critique 5 < 7',
    })
    expect(assistant.content).toBe('')
    expect(assistant.retryCount).toBe(1)
    expect(assistant.toolTrace[0].label).toContain('重试中')
  })

  it('critique 低分应加 ⚠️ 徽章', () => {
    const assistant = { content: '', richBlocks: [], toolTrace: [] }
    applyCritique(assistant, {
      type: 'critique',
      critique: { score: 5, suggestion: '需要更多推荐理由' },
    })
    expect(assistant.critique.score).toBe(5)
    expect(assistant.toolTrace[0].label).toContain('⚠️')
    expect(assistant.toolTrace[0].label).toContain('5/10')
  })

  it('critique 高分应加 📊 而非 ⚠️', () => {
    const assistant = { content: '', richBlocks: [], toolTrace: [] }
    applyCritique(assistant, {
      type: 'critique',
      critique: { score: 9, suggestion: '回答完整' },
    })
    expect(assistant.toolTrace[0].label).toContain('📊')
    expect(assistant.toolTrace[0].label).toContain('9/10')
    expect(assistant.toolTrace[0].label).not.toContain('⚠️')
  })

  it('intent_detected 应在 toolTrace 顶部加 🧠 意图', () => {
    const assistant = { content: '', richBlocks: [], toolTrace: [] }
    applyIntentDetected(assistant, {
      type: 'intent_detected',
      intent: { category: 'recommend_person', confidence: 0.92 },
      label: '🧠 意图：推荐人 (置信度 92%)',
    })
    expect(assistant.intent.category).toBe('recommend_person')
    expect(assistant.intent.confidence).toBe(0.92)
    expect(assistant.toolTrace[0].label).toContain('🧠 意图')
  })
})


describe('useChatStream Stage 4 — text_delta 长度异常检查', () => {
  it('text_delta > 100 字且不含已有内容前缀应触发警告', () => {
    const result = checkTextDeltaAnomaly('杨慈研究饮用水安全', 'a'.repeat(150))
    expect(result.anomalous).toBe(true)
    expect(result.message).toContain('长度异常')
    expect(result.message).toContain('150')
  })

  it('text_delta < 100 字不触发警告', () => {
    const result = checkTextDeltaAnomaly('prev', 'a'.repeat(50))
    expect(result.anomalous).toBe(false)
  })

  it('text_delta 长度异常但包含已有内容前缀不警告', () => {
    const result = checkTextDeltaAnomaly('杨慈', '杨慈研究饮用水安全' + 'b'.repeat(100))
    expect(result.anomalous).toBe(false)
  })

  it('空 prevContent 不警告（首次流式输出）', () => {
    const result = checkTextDeltaAnomaly('', 'a'.repeat(150))
    expect(result.anomalous).toBe(false)
  })

  it('空 delta 不警告', () => {
    const result = checkTextDeltaAnomaly('prev', '')
    expect(result.anomalous).toBe(false)
  })
})


describe('useChatStream Stage 4 — stopGeneration', () => {
  it('stopGeneration 应设置 state=aborted + 调 abort controller', () => {
    const controller = { abort: vi.fn() }
    const assistant = { state: 'streaming', content: '正在生成' }
    simulateStopGeneration(assistant, controller)
    expect(controller.abort).toHaveBeenCalled()
    expect(assistant.state).toBe('aborted')
  })

  it('stopGeneration 对 null controller 无副作用', () => {
    const assistant = { state: 'streaming' }
    expect(() => simulateStopGeneration(assistant, null)).not.toThrow()
    expect(assistant.state).toBe('streaming')  // 不变
  })

  it('stopGeneration 不修改非 streaming 状态的 assistant', () => {
    const controller = { abort: vi.fn() }
    const assistant = { state: 'idle', content: '已完成' }
    simulateStopGeneration(assistant, controller)
    expect(controller.abort).toHaveBeenCalled()  // 仍然调 abort
    expect(assistant.state).toBe('idle')  // 但 state 不改（已经在 idle）
  })
})


describe('useChatStream Stage 4 — abort 状态机守卫', () => {
  it('state=aborted 时 sendSSE 应跳过 switch case', () => {
    const assistant = { state: 'aborted' }
    expect(shouldSkipEvent(assistant)).toBe(true)
  })

  it('state=streaming 时不跳过', () => {
    const assistant = { state: 'streaming' }
    expect(shouldSkipEvent(assistant)).toBe(false)
  })

  it('state=idle 时不跳过（流正常结束）', () => {
    const assistant = { state: 'idle' }
    expect(shouldSkipEvent(assistant)).toBe(false)
  })

  it('null assistant 也不跳过（防御）', () => {
    expect(shouldSkipEvent(null)).toBeFalsy()
  })
})
