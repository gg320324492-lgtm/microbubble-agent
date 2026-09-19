// V1 用量记账 — 归一化 / 协议提取 / 累计 / 展示格式化（全部离线）
import { describe, expect, it } from 'vitest'
import {
  ZERO_USAGE,
  addUsage,
  extractAnthropicUsage,
  extractOpenAiUsage,
  normalizeUsage,
  usageFromColumns
} from '@main/services/model/usage'
import { formatTokens, sessionUsageLabel } from '@shared/usage'

describe('usage 归一化 — NaN / 负数 / 缺失一律归零', () => {
  it('正常值原样保留并标记可信', () => {
    const u = normalizeUsage({ inputTokens: 1234, outputTokens: 567, cacheReadTokens: 89 })
    expect(u).toEqual({ inputTokens: 1234, outputTokens: 567, cacheReadTokens: 89, usageComplete: true })
  })

  it('NaN / Infinity / 负数 / 字符串垃圾 → 0，且 complete=false', () => {
    expect(normalizeUsage({ inputTokens: Number.NaN, outputTokens: -5 }).inputTokens).toBe(0)
    expect(normalizeUsage({ inputTokens: Number.NaN, outputTokens: -5 }).outputTokens).toBe(0)
    expect(normalizeUsage({ inputTokens: Number.NaN, outputTokens: -5 }).usageComplete).toBe(false)
    expect(normalizeUsage({ inputTokens: Number.POSITIVE_INFINITY, outputTokens: 1 }).usageComplete).toBe(false)
    expect(normalizeUsage({ inputTokens: 'abc', outputTokens: 'xyz' }).usageComplete).toBe(false)
    // 负数即使与合法值并存也只把该字段归零
    const mixed = normalizeUsage({ inputTokens: 100, outputTokens: -1 })
    expect(mixed.inputTokens).toBe(100)
    expect(mixed.outputTokens).toBe(0)
    expect(mixed.usageComplete).toBe(false)
  })

  it('缺失 / 空对象 / undefined 输入 → 全零且 complete=false（不抛错）', () => {
    expect(normalizeUsage({})).toEqual(ZERO_USAGE)
    expect(normalizeUsage(undefined as never)).toEqual(ZERO_USAGE)
    expect(normalizeUsage({ inputTokens: null, outputTokens: undefined }).usageComplete).toBe(false)
  })

  it('小数向下取整；数字字符串被接受', () => {
    expect(normalizeUsage({ inputTokens: 12.9, outputTokens: '34' })).toEqual({
      inputTokens: 12,
      outputTokens: 34,
      cacheReadTokens: 0,
      usageComplete: true
    })
  })
})

describe('协议提取 — Anthropic 跨事件 / OpenAI 兼容', () => {
  it('Anthropic message_start 取 input + cache_read，message_delta 取 output', () => {
    const start = extractAnthropicUsage({
      type: 'message_start',
      message: { usage: { input_tokens: 900, cache_read_input_tokens: 400 } }
    })
    expect(start).toEqual({ inputTokens: 900, cacheReadTokens: 400 })

    const delta = extractAnthropicUsage({ type: 'message_delta', usage: { output_tokens: 120 } })
    expect(delta).toEqual({ outputTokens: 120 })

    // 两片合并后是完整用量
    expect(normalizeUsage({ ...start, ...delta })).toEqual({
      inputTokens: 900,
      outputTokens: 120,
      cacheReadTokens: 400,
      usageComplete: true
    })
  })

  it('无 usage 的事件 / 非法输入 → 空对象（不影响既有解析）', () => {
    expect(extractAnthropicUsage({ type: 'content_block_delta', delta: { text: 'hi' } })).toEqual({})
    expect(extractAnthropicUsage(null)).toEqual({})
    expect(extractAnthropicUsage('nope')).toEqual({})
  })

  it('OpenAI 兼容：顶层 usage 或 choices[0].usage 都能取到', () => {
    expect(extractOpenAiUsage({ usage: { prompt_tokens: 11, completion_tokens: 22 } })).toEqual({
      inputTokens: 11,
      outputTokens: 22
    })
    expect(extractOpenAiUsage({ choices: [{ usage: { prompt_tokens: 3, completion_tokens: 4 } }] })).toEqual({
      inputTokens: 3,
      outputTokens: 4
    })
    expect(extractOpenAiUsage({ choices: [{ delta: { content: 'x' } }] })).toEqual({})
  })
})

describe('会话累计 — addUsage / 列还原', () => {
  it('多轮累加求和；complete 取与', () => {
    const a = normalizeUsage({ inputTokens: 100, outputTokens: 10 })
    const b = normalizeUsage({ inputTokens: 50, outputTokens: 5 })
    expect(addUsage(a, b)).toEqual({
      inputTokens: 150,
      outputTokens: 15,
      cacheReadTokens: 0,
      usageComplete: true
    })
    const broken = normalizeUsage({ inputTokens: 1 })
    expect(addUsage(a, broken).usageComplete).toBe(false)
    expect(addUsage(ZERO_USAGE, ZERO_USAGE)).toEqual(ZERO_USAGE)
  })

  it('usageFromColumns 还原两列；异常列归零', () => {
    expect(usageFromColumns(1200, 340)).toEqual({
      inputTokens: 1200,
      outputTokens: 340,
      cacheReadTokens: 0,
      usageComplete: true
    })
    expect(usageFromColumns(null, undefined).usageComplete).toBe(false)
    expect(usageFromColumns(-1, 5).inputTokens).toBe(0)
  })

  it('formatTokens 紧凑展示', () => {
    expect(formatTokens(0)).toBe('0')
    expect(formatTokens(999)).toBe('999')
    expect(formatTokens(1234)).toBe('1.2k')
    expect(formatTokens(12345)).toBe('12k')
    expect(formatTokens(Number.NaN)).toBe('0')
    expect(formatTokens(-5)).toBe('0')
  })
})

describe('会话用量标签 — chip 显隐契约（对话面板展示）', () => {
  it('无会话 / 总量为 0 → null（不渲染 chip）', () => {
    expect(sessionUsageLabel(null)).toBeNull()
    expect(sessionUsageLabel(undefined)).toBeNull()
    expect(sessionUsageLabel({ tokensIn: 0, tokensOut: 0 })).toBeNull()
    expect(sessionUsageLabel({ tokensIn: Number.NaN, tokensOut: 0 })).toBeNull()
    expect(sessionUsageLabel({})).toBeNull()
  })

  it('有量 → 给出紧凑的输入/输出文本（任一非零即显示）', () => {
    expect(sessionUsageLabel({ tokensIn: 1234, tokensOut: 567 })).toEqual({ input: '1.2k', output: '567' })
    expect(sessionUsageLabel({ tokensIn: 0, tokensOut: 20 })).toEqual({ input: '0', output: '20' })
    expect(sessionUsageLabel({ tokensIn: 20000, tokensOut: 0 })).toEqual({ input: '20k', output: '0' })
  })
})
