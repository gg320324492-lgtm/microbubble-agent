import { describe, it, expect } from 'vitest'
import {
  hasValidScore,
  sortCitations,
  dedupCitations,
  toPercent,
  normalizeCitations
} from '../../src/renderer/src/utils/citation'
import type { StreamCitationEntry } from '../../src/shared/chat-types'

/**
 * 工厂: 用最少字段构造 citation 用于测试.
 */
function c(
  knowledgeId: number,
  opts: Partial<StreamCitationEntry> = {}
): StreamCitationEntry {
  return {
    knowledgeId,
    title: opts.title ?? `T${knowledgeId}`,
    ...opts
  } as StreamCitationEntry
}

describe('toPercent', () => {
  it('空 citations 不渲染', () => {
    expect(toPercent(undefined)).toBeNull()
    expect(toPercent(null)).toBeNull()
    expect(toPercent(NaN)).toBeNull()
    expect(toPercent('0.5')).toBeNull()
  })

  it('0..1 边界与舍入', () => {
    expect(toPercent(0)).toBe('0%')
    expect(toPercent(1)).toBe('100%')
    expect(toPercent(0.5)).toBe('50%')
    expect(toPercent(0.005)).toBe('1%')   // round up
    expect(toPercent(0.0049)).toBe('0%')  // round down (Math.round)
  })

  it('越界返回 null (不展示)', () => {
    expect(toPercent(-0.01)).toBeNull()
    expect(toPercent(1.01)).toBeNull()
    expect(toPercent(NaN)).toBeNull()
    expect(toPercent(Infinity)).toBeNull()
  })
})

describe('hasValidScore', () => {
  it('number + 0..1 范围 = valid', () => {
    expect(hasValidScore(c(1, { score: 0.5 }))).toBe(true)
    expect(hasValidScore(c(2, { score: 0 }))).toBe(true)
    expect(hasValidScore(c(3, { score: 1 }))).toBe(true)
  })

  it('缺 / 越界 / 非数字 = invalid', () => {
    expect(hasValidScore(c(4))).toBe(false)
    expect(hasValidScore(c(5, { score: undefined }))).toBe(false)
    expect(hasValidScore(c(6, { score: null as unknown as number }))).toBe(false)
    expect(hasValidScore(c(7, { score: -0.1 }))).toBe(false)
    expect(hasValidScore(c(8, { score: 1.1 }))).toBe(false)
    expect(hasValidScore(c(9, { score: NaN }))).toBe(false)
  })
})

describe('sortCitations', () => {
  it('空数组返回空数组 (新 array)', () => {
    const out = sortCitations([])
    expect(out).toEqual([])
    expect(out).not.toBe([])  // 应该是新 array
  })

  it('单条 citation 不动顺序', () => {
    const input = [c(1, { score: 0.42 })]
    const out = sortCitations(input)
    expect(out).toHaveLength(1)
    expect(out[0]!.knowledgeId).toBe(1)
  })

  it('多条按 score 降序 (primary key = score), 后端推来的相对顺序保留 (stable sort)', () => {
    const a = c(10, { score: 0.30 })
    const b = c(11, { score: 0.80 })
    const c1 = c(12, { score: 0.55 })
    const input = [a, b, c1]
    const out = sortCitations(input)
    expect(out.map((x) => x.knowledgeId)).toEqual([11, 12, 10])
  })

  it('相同 score 保留原始顺序 (JS Array.sort ES2019 stable)', () => {
    const a = c(20, { score: 0.7, title: 'first' })
    const b = c(21, { score: 0.7, title: 'second' })
    const d = c(22, { score: 0.7, title: 'third' })
    const out = sortCitations([a, b, d])
    expect(out.map((x) => x.title)).toEqual(['first', 'second', 'third'])
  })

  it('无 score 的 citation 保原顺序 (排在有 score 之后)', () => {
    const a = c(30) // no score
    const b = c(31, { score: 0.9 })
    const c1 = c(32) // no score
    const d = c(33, { score: 0.5 })
    const out = sortCitations([a, b, c1, d])
    expect(out.map((x) => x.knowledgeId)).toEqual([31, 33, 30, 32])
  })

  it('全无 score = 原顺序', () => {
    const a = c(40)
    const b = c(41)
    const c1 = c(42)
    expect(sortCitations([a, b, c1]).map((x) => x.knowledgeId)).toEqual([40, 41, 42])
  })

  it('不修改入参 (纯函数)', () => {
    const input = [c(50, { score: 0.1 }), c(51, { score: 0.9 })]
    const snapshot = input.map((x) => x.knowledgeId)
    sortCitations(input)
    expect(input.map((x) => x.knowledgeId)).toEqual(snapshot)
  })
})

describe('dedupCitations', () => {
  it('空数组 = 空数组', () => {
    expect(dedupCitations([])).toEqual([])
  })

  it('单条无重复 = 单条', () => {
    const out = dedupCitations([c(1, { score: 0.5 })])
    expect(out).toHaveLength(1)
  })

  it('重复 knowledgeId: 第一次保留, 后续丢弃 (Phase 3-C1 语义)', () => {
    const a = c(1, { title: 'first' })
    const b = c(1, { title: 'second-dup' })
    const c1 = c(2, { title: 'third' })
    const out = dedupCitations([a, b, c1])
    expect(out).toHaveLength(2)
    expect(out[0]!.title).toBe('first')
    expect(out[1]!.title).toBe('third')
  })

  it('非法 knowledgeId (NaN / undefined / string) 跳过', () => {
    const good = c(10, { score: 0.5 })
    const bad1 = { knowledgeId: NaN, title: 'bad' } as StreamCitationEntry
    const bad2 = { knowledgeId: undefined, title: 'undef' } as unknown as StreamCitationEntry
    const bad3 = { knowledgeId: 'x', title: 'string' } as unknown as StreamCitationEntry
    const out = dedupCitations([good, bad1, bad2, bad3])
    expect(out).toHaveLength(1)
    expect(out[0]!.knowledgeId).toBe(10)
  })

  it('不修改入参', () => {
    const input = [c(1), c(2), c(1)]
    const snapshotLength = input.length
    dedupCitations(input)
    expect(input).toHaveLength(snapshotLength)
  })
})

describe('normalizeCitations (sort + dedup)', () => {
  it('先 dedup 再 sort: duplicate + 不同 score', () => {
    const a = c(1, { score: 0.3, title: 'low-fist' })
    const dup = c(1, { score: 0.9, title: 'high-dup-should-lose' })  // dup, lose
    const b = c(2, { score: 0.7 })
    const c1 = c(3, { score: 0.5 })
    const out = normalizeCitations([a, dup, b, c1])
    expect(out.map((x) => x.knowledgeId)).toEqual([2, 3, 1])
    expect(out[2]!.title).toBe('low-fist')  // first occurrence kept
  })

  it('空 + 单条边界', () => {
    expect(normalizeCitations([])).toEqual([])
    expect(normalizeCitations([c(1, { score: 0.1 })])).toHaveLength(1)
  })
})
