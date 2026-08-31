import { describe, expect, it } from 'vitest'
import {
  advancePhase,
  countResults,
  isRetrievalTool,
  isTerminalPhase,
  PHASE_LABELS,
  phaseFromEvent,
  phaseLabel,
  sanitizeRestored,
} from '../assistantPhase'

describe('assistantPhase — W99 +12', () => {
  describe('phaseFromEvent 全事件映射（22 case）', () => {
    it('thinking → thinking', () => {
      expect(phaseFromEvent({ type: 'thinking' })).toBe('thinking')
    })
    it('intent_detected → thinking（并入）', () => {
      expect(phaseFromEvent({ type: 'intent_detected' })).toBe('thinking')
    })
    it('tool_use 检索类 → retrieving', () => {
      expect(phaseFromEvent({ type: 'tool_use', tool_name: 'search_knowledge' })).toBe(
        'retrieving',
      )
      expect(phaseFromEvent({ type: 'tool_use', tool_name: 'web_search' })).toBe(
        'retrieving',
      )
      expect(phaseFromEvent({ type: 'tool_use', tool_name: 'hybrid_retrieve' })).toBe(
        'retrieving',
      )
    })
    it('tool_use 非检索 → thinking（rank 守卫单调递进可触发，from thinking → thinking noop）', () => {
      expect(phaseFromEvent({ type: 'tool_use', tool_name: 'create_task' })).toBe(
        'thinking',
      )
    })
    it('tool_use tool_name undefined → thinking', () => {
      expect(phaseFromEvent({ type: 'tool_use' })).toBe('thinking')
    })
    it('tool_result 检索类 → found', () => {
      expect(phaseFromEvent({ type: 'tool_result', tool_name: 'web_search' })).toBe(
        'found',
      )
    })
    it('tool_result 非检索 → null（不切换阶段）', () => {
      expect(phaseFromEvent({ type: 'tool_result', tool_name: 'create_task' })).toBeNull()
    })
    it('synthesis_start → synthesizing', () => {
      expect(phaseFromEvent({ type: 'synthesis_start' })).toBe('synthesizing')
    })
    it('text_delta → generating', () => {
      expect(phaseFromEvent({ type: 'text_delta' })).toBe('generating')
    })
    it('retry → refining', () => {
      expect(phaseFromEvent({ type: 'retry' })).toBe('refining')
    })
    it('done → done', () => {
      expect(phaseFromEvent({ type: 'done' })).toBe('done')
    })
    it('error → error', () => {
      expect(phaseFromEvent({ type: 'error' })).toBe('error')
    })
    it('其他事件（rich_block / refs / suggestions 等）→ null', () => {
      expect(phaseFromEvent({ type: 'rich_block' })).toBeNull()
      expect(phaseFromEvent({ type: 'refs' })).toBeNull()
      expect(phaseFromEvent({ type: 'suggestions' })).toBeNull()
      expect(phaseFromEvent({ type: 'message_persisted' })).toBeNull()
      expect(phaseFromEvent({ type: 'sync_required' })).toBeNull()
      expect(phaseFromEvent({ type: 'plan_step' })).toBeNull()
      expect(phaseFromEvent({ type: 'critique' })).toBeNull()
      expect(phaseFromEvent({ type: 'brief' })).toBeNull()
      expect(phaseFromEvent({ type: 'detail' })).toBeNull()
    })
  })

  describe('isRetrievalTool 白名单', () => {
    it('true: search_knowledge / web_search / hybrid_retrieve', () => {
      expect(isRetrievalTool('search_knowledge')).toBe(true)
      expect(isRetrievalTool('web_search')).toBe(true)
      expect(isRetrievalTool('hybrid_retrieve')).toBe(true)
    })
    it('false: 非检索 + 空 + undefined', () => {
      expect(isRetrievalTool('create_task')).toBe(false)
      expect(isRetrievalTool('')).toBe(false)
      expect(isRetrievalTool(undefined)).toBe(false)
    })
  })

  describe('countResults 边界', () => {
    it('results 数组', () => {
      expect(countResults({ results: [1, 2, 3] })).toBe(3)
      expect(countResults({ results: [] })).toBe(0)
    })
    it('items 数组 fallback', () => {
      expect(countResults({ items: ['a', 'b'] })).toBe(2)
    })
    it('results 优先于 items', () => {
      expect(countResults({ results: [1, 2], items: [9, 9, 9] })).toBe(2)
    })
    it('null / undefined / 非数组', () => {
      expect(countResults(null)).toBe(0)
      expect(countResults(undefined)).toBe(0)
      expect(countResults({})).toBe(0)
      expect(countResults({ results: 'not-array' })).toBe(0)
      expect(countResults({ results: 123 })).toBe(0)
    })
  })

  describe('advancePhase 单调递进 + 终态守卫（核心防御）', () => {
    it('undefined → queued（初值）', () => {
      expect(advancePhase(undefined, 'queued')).toBe('queued')
    })
    it('单调递进 queued → thinking → retrieving → found → synthesizing → generating', () => {
      expect(advancePhase('queued', 'thinking')).toBe('thinking')
      expect(advancePhase('thinking', 'retrieving')).toBe('retrieving')
      expect(advancePhase('retrieving', 'found')).toBe('found')
      expect(advancePhase('found', 'synthesizing')).toBe('synthesizing')
      expect(advancePhase('synthesizing', 'generating')).toBe('generating')
    })

    it('**核心回归点**: generating 收 retrieving → 保持 generating（不回退闪烁）', () => {
      expect(advancePhase('generating', 'retrieving')).toBe('generating')
    })
    it('done 收任意 → 保持 done（终态不可复活）', () => {
      expect(advancePhase('done', 'thinking')).toBe('done')
      expect(advancePhase('done', 'aborted')).toBe('done')
      expect(advancePhase('done', 'error')).toBe('done')
    })
    it('aborted 收任意 → 保持 aborted（abort 后后端残余事件防御）', () => {
      expect(advancePhase('aborted', 'text_delta')).toBe('aborted')
      expect(advancePhase('aborted', 'done')).toBe('aborted')
    })
    it('error 收任意 → 保持 error', () => {
      expect(advancePhase('error', 'thinking')).toBe('error')
    })

    it('**retry 双向**: generating → refining → generating（重试后再次生成）', () => {
      expect(advancePhase('generating', 'refining')).toBe('refining')
      expect(advancePhase('refining', 'generating')).toBe('generating')
    })
    it('refining 从其他阶段来（不是从 generating）→ 显式落 refining', () => {
      expect(advancePhase('thinking', 'refining')).toBe('refining')
      expect(advancePhase('queued', 'refining')).toBe('refining')
    })

    it('相同阶段 noop', () => {
      expect(advancePhase('thinking', 'thinking')).toBe('thinking')
      expect(advancePhase('generating', 'generating')).toBe('generating')
    })

    // 2026-08-31 修正: 原断言 (queued 收 retrieving → 保持 queued) 与模块自身
    // 「只许前进」语义矛盾 — 前向跳级 rank 更高应放行 (后端缺 thinking 事件时
    // 胶囊才能跟上真实阶段, 禁跳级会卡死在「正在理解问题」)。
    // 真正要防的「后退拒绝」已由上方 generating 收 retrieving 用例覆盖。
    it('前向跳级被允许（queued 收 retrieving → retrieving, 只许前进语义）', () => {
      expect(advancePhase('queued', 'retrieving')).toBe('retrieving')
    })
  })

  describe('phaseLabel 插值', () => {
    it('所有 10 phase 都有非空文案', () => {
      const phases: Array<keyof typeof PHASE_LABELS> = [
        'queued',
        'thinking',
        'retrieving',
        'found',
        'synthesizing',
        'generating',
        'refining',
        'done',
        'aborted',
        'error',
      ]
      phases.forEach((p) => {
        const text = PHASE_LABELS[p]()
        expect(text.length).toBeGreaterThan(0)
      })
    })
    it('found 带 count → "找到 7 条相关内容"', () => {
      expect(phaseLabel('found', { foundCount: 7 })).toBe('找到 7 条相关内容')
    })
    it('found 缺 count → "找到 0 条相关内容"', () => {
      expect(phaseLabel('found')).toBe('找到 0 条相关内容')
    })
    it('refining 带 retryCount → "正在重新优化（第 2 次）"', () => {
      expect(phaseLabel('refining', { retryCount: 2 })).toBe('正在重新优化（第 2 次）')
    })
    it('refining 缺 retryCount → 默认文案', () => {
      expect(phaseLabel('refining')).toBe('正在重新优化')
    })
  })

  describe('isTerminalPhase 三真七假', () => {
    it('三真: done / aborted / error', () => {
      expect(isTerminalPhase('done')).toBe(true)
      expect(isTerminalPhase('aborted')).toBe(true)
      expect(isTerminalPhase('error')).toBe(true)
    })
    it('七假: 其余阶段', () => {
      const active = [
        'queued',
        'thinking',
        'retrieving',
        'found',
        'synthesizing',
        'generating',
        'refining',
      ] as const
      active.forEach((p) => expect(isTerminalPhase(p)).toBe(false))
    })
  })

  describe('完整序列快照（端到端集成）', () => {
    it('**检索问答**: queued → thinking → retrieving → found → synthesizing → generating → done', () => {
      let phase: AssistantPhase = 'queued'
      const trace: AssistantPhase[] = []
      const events = [
        { type: 'thinking' },
        { type: 'tool_use', tool_name: 'search_knowledge' },
        { type: 'tool_result', tool_name: 'search_knowledge' },
        { type: 'synthesis_start' },
        { type: 'text_delta' },
        { type: 'text_delta' },
        { type: 'text_delta' },
        { type: 'done' },
      ]
      events.forEach((evt) => {
        const next = phaseFromEvent(evt)
        if (next) phase = advancePhase(phase, next)
        trace.push(phase)
      })
      expect(trace).toEqual([
        'thinking', // thinking
        'retrieving', // tool_use
        'found', // tool_result
        'synthesizing', // synthesis_start
        'generating', // text_delta 1
        'generating', // text_delta 2 (noop)
        'generating', // text_delta 3 (noop)
        'done', // done
      ])
    })

    it('**普通问答**（无检索工具）: queued → thinking → generating → done', () => {
      let phase: AssistantPhase = 'queued'
      const events = [
        { type: 'thinking' },
        { type: 'text_delta' },
        { type: 'text_delta' },
        { type: 'done' },
      ]
      events.forEach((evt) => {
        const next = phaseFromEvent(evt)
        if (next) phase = advancePhase(phase, next)
      })
      expect(phase).toBe('done')
    })

    it('**重试序列**: generating → refining → generating → done', () => {
      let phase: AssistantPhase = 'generating'
      phase = advancePhase(phase, 'refining')
      expect(phase).toBe('refining')
      phase = advancePhase(phase, 'generating')
      expect(phase).toBe('generating')
      phase = advancePhase(phase, 'done')
      expect(phase).toBe('done')
    })

    it('**abort race**: 流中后端残余事件（已 aborted）→ 全部被守卫拒绝', () => {
      let phase: AssistantPhase = 'aborted'
      const trace: AssistantPhase[] = []
      const events = [
        { type: 'thinking' },
        { type: 'tool_use', tool_name: 'search_knowledge' },
        { type: 'text_delta' },
        { type: 'done' },
      ]
      events.forEach((evt) => {
        const next = phaseFromEvent(evt)
        if (next) phase = advancePhase(phase, next)
        trace.push(phase)
      })
      expect(trace).toEqual(['aborted', 'aborted', 'aborted', 'aborted'])
    })
  })

  describe('sanitizeRestored 僵尸 phase 净化（R1 高风险防御）', () => {
    it('state=streaming + 有 content → idle + done', () => {
      const m = { state: 'streaming', content: '部分内容' }
      const out = sanitizeRestored(m)
      expect(out.state).toBe('idle')
      expect(out.phase).toBe('done')
    })
    it('state=streaming + 无 content → aborted + aborted', () => {
      const m = { state: 'streaming', content: null }
      const out = sanitizeRestored(m)
      expect(out.state).toBe('aborted')
      expect(out.phase).toBe('aborted')
    })
    it('state=idle + 无 phase → done', () => {
      const m = { state: 'idle' }
      const out = sanitizeRestored(m)
      expect(out.phase).toBe('done')
    })
    it('phase 已为终态 → 保持不变', () => {
      const m = { state: 'idle', phase: 'aborted' }
      const out = sanitizeRestored(m)
      expect(out.phase).toBe('aborted')
    })
    it('phase 非终态 + state=idle → done', () => {
      const m = { state: 'idle', phase: 'generating' }
      const out = sanitizeRestored(m)
      expect(out.phase).toBe('done')
    })
    it('**核心 R1**: 删除 phaseStartedAt 防 elapsed 显示历史秒数', () => {
      const m = {
        state: 'streaming',
        content: '...',
        phase: 'generating',
        phaseStartedAt: 1700000000000,
      }
      const out = sanitizeRestored(m)
      expect('phaseStartedAt' in out).toBe(false)
    })
    it('重置 generatingDispatched', () => {
      const m = { state: 'streaming', content: '...', generatingDispatched: true }
      const out = sanitizeRestored(m)
      expect(out.generatingDispatched).toBeUndefined()
    })
  })
})

// 显式 import 类型以便 IDE 识别
type AssistantPhase =
  | 'queued'
  | 'thinking'
  | 'retrieving'
  | 'found'
  | 'synthesizing'
  | 'generating'
  | 'refining'
  | 'done'
  | 'aborted'
  | 'error'