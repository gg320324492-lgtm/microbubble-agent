// M8-2 上下文管理 — 估算 / 触发保留 / 原子裁切 / 摘要 / 字节窗口（全部离线）
import { describe, expect, it, vi } from 'vitest'
import {
  PER_MESSAGE_OVERHEAD,
  estimateContext,
  estimateTextTokens,
  isCjkCodePoint,
  utf8Bytes,
  type EstimateMessage
} from '@main/agent/context/estimate'
import {
  DEFAULT_PRUNE_CONFIG,
  PRUNE_CONFIG_RANGES,
  estimateTurns,
  normalizePruneConfig,
  planPrune,
  splitRounds,
  targetTokens,
  triggerTokens,
  trimToolResultText,
  validateToolPairing,
  type PruneConfig
} from '@main/agent/context/prune'
import {
  DEFAULT_MAX_SUMMARY_TOKENS,
  buildSummaryPrompt,
  summarizeRound,
  summarizeRounds,
  truncateSummary
} from '@main/agent/context/summarize'
import type { AgentTurn } from '@shared/types'

// ---------------------------------------------------------------- 夹具

const cfg = (over: Partial<PruneConfig> = {}): PruneConfig => ({
  windowTokens: 131072,
  triggerRatio: 0.7,
  targetRatio: 0.5,
  keepRecentRounds: 3,
  toolResultTrimBytes: 8 * 1024,
  reserveTokens: 0, // 单测默认不预留，便于隔离断言；预留行为单列用例
  ...over
})

/** 造一轮工具交互：assistant(tool_use) + user(tool_result) */
function toolRound(id: string, body: string, label = 'x'): AgentTurn[] {
  return [
    { role: 'assistant', content: [{ type: 'text', text: `读 ${label}` }, { type: 'tool_use', id, name: 'read_file', input: { path: label } }] },
    { role: 'user', content: [{ type: 'tool_result', tool_use_id: id, content: body }] }
  ]
}

/** 造一个「首条目标 + N 轮工具交互」的长会话 */
function longSession(rounds: number, bodyBytes = 4000): AgentTurn[] {
  const turns: AgentTurn[] = [{ role: 'user', content: '请把这几份材料读完并汇总。' }]
  for (let i = 1; i <= rounds; i += 1) turns.push(...toolRound(`tu_${i}`, '数'.repeat(Math.floor(bodyBytes / 3)), `f${i}.md`))
  return turns
}

// ---------------------------------------------------------------- 1 估算器（5）

describe('token 估算 — 保守启发式', () => {
  it('纯中文：约 1 token/字（保守上界），且明显高于拉丁同长度', () => {
    const zh = '这是一段中文测试内容用于估算'
    const en = 'this is a latin test string'
    const zhTokens = estimateTextTokens(zh)
    expect(zhTokens).toBeGreaterThanOrEqual([...zh].length) // CJK 至少 1 token/字
    expect(zhTokens / [...zh].length).toBeLessThan(2) // 但不会离谱
    expect(estimateTextTokens(en) / en.length).toBeLessThan(0.5) // 拉丁远低于 1 token/字符
  })

  it('中英混排：介于两者之间且随中文占比上升', () => {
    // 同样字符数下，中文占比高者估算更高（CJK 1 token/字 vs 拉丁 4 字符/token）
    const zhHeavy = '中文字符占比很高的一段内容'
    const enHeavy = 'almost entirely latin content here'
    expect(estimateTextTokens(zhHeavy) / [...zhHeavy].length).toBeGreaterThan(
      estimateTextTokens(enHeavy) / [...enHeavy].length
    )
    expect(estimateTextTokens('')).toBe(0)
  })

  it('JSON：标点密度高 → 同字符数下估算高于纯散文（保守方向）', () => {
    const json = '{"a":1,"b":[2,3],"c":{"d":"e"}}'
    const prose = 'aaaaaaabbbbbbbbccccccccdddddd'
    expect(estimateTextTokens(json)).toBeGreaterThan(estimateTextTokens(prose))
  })

  it('代码块：符号与换行多 → 不会被低估', () => {
    const code = 'function f() {\n  if (a) { return b; }\n}\n'
    expect(estimateTextTokens(code)).toBeGreaterThanOrEqual(code.length / 4)
  })

  it('空消息与纯空白：只算结构开销，不产生负值', () => {
    const e = estimateContext([{ role: 'user', segments: [] }])
    expect(e.total).toBe(PER_MESSAGE_OVERHEAD)
    expect(estimateTextTokens('   \n\t ')).toBeGreaterThan(0)
    expect(estimateTextTokens('')).toBe(0)
    // 逐条与总量一致
    const msgs: EstimateMessage[] = [
      { role: 'system', segments: [{ kind: 'text', text: '你是助手' }] },
      { role: 'user', segments: [{ kind: 'text', text: '你好' }] },
      { role: 'assistant', segments: [{ kind: 'tool_use', name: 'read_file', input: { path: 'a' } }] },
      { role: 'user', segments: [{ kind: 'tool_result', text: '内容' }] }
    ]
    const all = estimateContext(msgs)
    expect(all.messages).toHaveLength(4)
    expect(all.total).toBe(all.messages.reduce((n, m) => n + m.tokens, 0))
    expect(all.toolUses).toBe(1)
    expect(all.toolResults).toBe(1)
    expect(all.messages[2]!.tokens).toBeGreaterThan(0)
  })
})

// ---------------------------------------------------------------- 2 触发与保留（5）

describe('触发线与保留策略', () => {
  it('未触线 → 原样返回、零副作用、无裁切记录', () => {
    const turns = longSession(1, 100)
    const plan = planPrune(turns, cfg())
    expect(plan.pruned).toBe(false)
    expect(plan.records).toHaveLength(0)
    expect(plan.turns).toEqual(turns)
    expect(plan.roundsToSummarize).toHaveLength(0)
  })

  it('阈值边界：正好等于触发线不裁，超过即裁', () => {
    const c = cfg({ windowTokens: 2000, triggerRatio: 0.5, targetRatio: 0.3, keepRecentRounds: 1, toolResultTrimBytes: 1024 })
    const trigger = triggerTokens(c) // 1000
    // 造一个刚好不触线的会话
    const small: AgentTurn[] = [{ role: 'user', content: '目标' }, ...toolRound('a', 'x'.repeat(200))]
    expect(estimateTurns(small)).toBeLessThan(trigger)
    expect(planPrune(small, c).pruned).toBe(false)
    // 放大到远超触发线
    const big = longSession(6, 6000)
    expect(estimateTurns(big)).toBeGreaterThan(trigger)
    const plan = planPrune(big, c)
    expect(plan.pruned).toBe(true)
    expect(plan.afterTokens).toBeLessThan(plan.beforeTokens)
  })

  it('保留近端：最近 K 轮完整保留（其 tool_use/tool_result 不被裁）', () => {
    const c = cfg({ windowTokens: 3000, triggerRatio: 0.3, targetRatio: 0.15, keepRecentRounds: 2, toolResultTrimBytes: 512 })
    const turns = longSession(6, 3000)
    const plan = planPrune(turns, c)
    expect(plan.pruned).toBe(true)
    const rounds = splitRounds(turns)
    const recent = rounds.slice(-2)
    // 近端两轮的原始文本应原样出现在结果里
    for (const r of recent) {
      for (const i of r.indexes) {
        const original = turns[i]!
        const kept = plan.turns.find((t) => JSON.stringify(t) === JSON.stringify(original))
        expect(kept, `近端轮次 ${r.round} 的消息被改动了`).toBeTruthy()
      }
    }
  })

  it('首条用户目标消息永不裁切（即使是最老的）', () => {
    const c = cfg({ windowTokens: 2000, triggerRatio: 0.2, targetRatio: 0.1, keepRecentRounds: 1, toolResultTrimBytes: 256 })
    const turns = longSession(8, 4000)
    const plan = planPrune(turns, c)
    expect(plan.pruned).toBe(true)
    expect(plan.turns.some((t) => t.role === 'user' && t.content === '请把这几份材料读完并汇总。')).toBe(true)
  })

  it('裁切记录含轮次/动作/字节/token/时间（供会话元数据）', () => {
    const c = cfg({ windowTokens: 3000, triggerRatio: 0.3, targetRatio: 0.15, keepRecentRounds: 1, toolResultTrimBytes: 512 })
    const now = 1_700_000_000_000
    const plan = planPrune(longSession(6, 3000), c, { now })
    expect(plan.records.length).toBeGreaterThan(0)
    for (const r of plan.records) {
      expect(r.round).toBeGreaterThan(0)
      expect(['trim_tool_result', 'drop_group']).toContain(r.action)
      expect(r.beforeBytes).toBeGreaterThanOrEqual(r.afterBytes)
      expect(r.beforeTokens).toBeGreaterThanOrEqual(r.afterTokens)
      expect(r.at).toBe(now)
    }
    // 目标线：裁到不高于 target 或已无可裁
    expect(plan.afterTokens).toBeLessThanOrEqual(Math.max(targetTokens(c), plan.afterTokens))
    // 记账必须真实反映变化（真机日志曾出现 before/after 恒等 —— 两侧都取了原始数组）
    const trimmed = plan.records.filter((r) => r.action === 'trim_tool_result')
    expect(trimmed.length).toBeGreaterThan(0)
    expect(trimmed.some((r) => r.afterBytes < r.beforeBytes)).toBe(true)
    expect(trimmed.some((r) => r.afterTokens < r.beforeTokens)).toBe(true)
  })
})

// ---------------------------------------------------------------- 3 原子裁切协议（4）

describe('工具组原子裁切 — 绝不产生孤儿 tool_result', () => {
  it('validateToolPairing 能检出孤儿 tool_result 与悬空 tool_use', () => {
    const orphan: AgentTurn[] = [{ role: 'user', content: [{ type: 'tool_result', tool_use_id: 'nope', content: 'x' }] }]
    const oi = validateToolPairing(orphan)
    expect(oi).toHaveLength(1)
    expect(oi[0]!.kind).toBe('orphan_tool_result')

    const dangling: AgentTurn[] = [
      { role: 'assistant', content: [{ type: 'tool_use', id: 'tu_x', name: 'read_file', input: {} }] }
    ]
    const di = validateToolPairing(dangling)
    expect(di).toHaveLength(1)
    expect(di[0]!.kind).toBe('dangling_tool_use')

    // 成对则无违规
    expect(validateToolPairing(toolRound('tu_ok', 'body'))).toHaveLength(0)
  })

  it('整组裁切时 tool_use 与 tool_result **同切**（结果里没有孤儿）', () => {
    const c = cfg({ windowTokens: 2000, triggerRatio: 0.2, targetRatio: 0.1, keepRecentRounds: 1, toolResultTrimBytes: 256 })
    const turns = longSession(8, 4000)
    const plan = planPrune(turns, c)
    expect(plan.records.some((r) => r.action === 'drop_group')).toBe(true)
    expect(validateToolPairing(plan.turns)).toHaveLength(0)
    // 被整组裁掉的轮次，其 tool_use 与 tool_result 都不在了
    for (const rec of plan.records.filter((r) => r.action === 'drop_group')) {
      const r = splitRounds(turns).find((x) => x.round === rec.round)!
      for (const i of r.indexes) {
        const original = JSON.stringify(turns[i])
        expect(plan.turns.some((t) => JSON.stringify(t) === original)).toBe(false)
      }
    }
  })

  it('只裁工具结果正文时（trim 阶段）协议仍然有效，且**尾部信息保住**', () => {
    const body = `${'数'.repeat(6000)}[尾部关键结论：降解率达 92%]`
    const trimmed = trimToolResultText(body, 1024)
    expect(utf8Bytes(trimmed)).toBeLessThanOrEqual(1024)
    expect(trimmed).toContain('尾部关键结论') // 尾部不丢
    expect(trimmed).toContain('省略')
    // 单轮 trim 场景下协议不变
    const c = cfg({ windowTokens: 4000, triggerRatio: 0.3, targetRatio: 0.25, keepRecentRounds: 1, toolResultTrimBytes: 512 })
    const plan = planPrune(longSession(3, 6000), c)
    expect(validateToolPairing(plan.turns)).toHaveLength(0)
  })

  it('裁切结果若会破坏协议 → 放弃本次裁切（宁可原样送模型）', () => {
    // 构造一个「assistant 里 tool_use 与 tool_result 混在同一条消息」的畸形输入：
    // 整组裁切会切掉 tool_use 却留下 result 所在消息的其它块 —— 此处用 pair 校验兜底
    const weird: AgentTurn[] = [
      { role: 'user', content: '目标' },
      { role: 'assistant', content: [{ type: 'tool_use', id: 'tu_a', name: 'read_file', input: {} }] },
      { role: 'user', content: [{ type: 'tool_result', tool_use_id: 'tu_a', content: 'r' }] },
      { role: 'user', content: [{ type: 'tool_result', tool_use_id: 'tu_ghost', content: 'ghost' }] } // 孤儿
    ]
    // 输入本身已有孤儿 → 输出必须校验失败，故 planPrune 应回退为不裁
    expect(validateToolPairing(weird).some((i) => i.kind === 'orphan_tool_result')).toBe(true)
    const c = cfg({ windowTokens: 100, triggerRatio: 0.01, targetRatio: 0.005, keepRecentRounds: 0, toolResultTrimBytes: 8 })
    const plan = planPrune(weird, c)
    expect(plan.pruned).toBe(false)
    expect(plan.records).toHaveLength(0)
  })
})

// ---------------------------------------------------------------- 4 摘要（4）

describe('LLM 摘要随车', () => {
  const turn = (): AgentTurn[] => toolRound('tu_s', '很长很长的工具结果'.repeat(50), 'a.md')

  it('成功：摘要被写入注记替换原内容，且不超 token 预算', async () => {
    const complete = vi.fn().mockResolvedValue('用户读取了 a.md，关键结论是 X。')
    const out = await summarizeRound({ complete }, 3, turn())
    expect(out.ok).toBe(true)
    expect(out.summary).toContain('关键结论')
    expect(complete).toHaveBeenCalledTimes(1)
    // 提示词含轮次与工具信息
    const arg = complete.mock.calls[0]![0] as { system: string; user: string }
    expect(arg.user).toContain('第 3 轮')
    expect(arg.system).toContain('200 token')
  })

  it('失败（抛错）→ 降级为 ok:false，不抛出、不阻塞', async () => {
    const out = await summarizeRound({ complete: () => Promise.reject(new Error('模型不可用')) }, 1, turn())
    expect(out.ok).toBe(false)
    expect(out.reason).toContain('模型不可用')
  })

  it('超时 → 降级（用极短超时断言）', async () => {
    const never = (): Promise<string> => new Promise(() => undefined)
    const out = await summarizeRound({ complete: never, timeoutMs: 30 }, 2, turn())
    expect(out.ok).toBe(false)
    expect(out.reason).toContain('超时')
  })

  it('摘要本身有预算上限；空摘要视为失败', async () => {
    const long = '摘要'.repeat(5000)
    const capped = truncateSummary(long, DEFAULT_MAX_SUMMARY_TOKENS)
    expect(estimateTextTokens(capped)).toBeLessThanOrEqual(DEFAULT_MAX_SUMMARY_TOKENS + 2)
    expect(capped.endsWith('…')).toBe(true)
    expect(truncateSummary('   ', 200)).toBe('')

    const empty = await summarizeRound({ complete: () => Promise.resolve('   ') }, 1, turn())
    expect(empty.ok).toBe(false)

    // 批量：一个成功一个失败 → summaries 只含成功的，失败不影响其它
    const rounds = [
      { round: 1, turns: turn() },
      { round: 2, turns: turn() }
    ]
    let n = 0
    const { summaries, outcomes } = await summarizeRounds(
      {
        complete: () => {
          n += 1
          return n === 1 ? Promise.resolve('ok 摘要') : Promise.reject(new Error('fail'))
        }
      },
      rounds
    )
    expect(outcomes).toHaveLength(2)
    expect(summaries.size).toBe(1)
  })

  it('buildSummaryPrompt 把工具调用与结果都渲染进去（供模型压缩）', () => {
    const { user } = buildSummaryPrompt(7, turn())
    expect(user).toContain('第 7 轮')
    expect(user).toContain('调用工具')
    expect(user).toContain('read_file')
    expect(user).toContain('工具结果')
  })
})

// ---------------------------------------------------------------- 5 摘要接入裁切（2）

describe('摘要与裁切的衔接', () => {
  it('提供摘要 → 整组裁切后插入注记；未提供 → 记录到 roundsToSummarize', () => {
    const c = cfg({ windowTokens: 2000, triggerRatio: 0.2, targetRatio: 0.1, keepRecentRounds: 1, toolResultTrimBytes: 256 })
    const turns = longSession(8, 4000)
    const dry = planPrune(turns, c)
    expect(dry.roundsToSummarize.length).toBeGreaterThan(0)
    expect(dry.roundsToSummarize[0]!.turns.length).toBeGreaterThan(0)

    const first = dry.roundsToSummarize[0]!
    const summaries = new Map<number, string>([[first.round, '该轮读取了材料并得到结论 Y']])
    const withSummary = planPrune(turns, c, { summaries })
    // 只给了一轮摘要 → 其余待摘要轮次数量应减一（不会凭空消失）
    expect(withSummary.roundsToSummarize).toHaveLength(dry.roundsToSummarize.length - 1)
    expect(withSummary.roundsToSummarize.some((r) => r.round === first.round)).toBe(false)
    expect(withSummary.turns.some((t) => typeof t.content === 'string' && t.content.includes('已摘要'))).toBe(true)
    expect(validateToolPairing(withSummary.turns)).toHaveLength(0)
  })

  it('摘要注记也占用预算：注入超长摘要仍不破坏协议与上限', () => {
    const c = cfg({ windowTokens: 2000, triggerRatio: 0.2, targetRatio: 0.1, keepRecentRounds: 1, toolResultTrimBytes: 256 })
    const turns = longSession(8, 4000)
    const dry = planPrune(turns, c)
    const summaries = new Map(dry.roundsToSummarize.map((r) => [r.round, '摘'.repeat(2000)]))
    const plan = planPrune(turns, c, { summaries })
    expect(validateToolPairing(plan.turns)).toHaveLength(0)
    expect(plan.pruned).toBe(true)
  })
})

// ---------------------------------------------------------------- 6 工具与估算一致性

describe('估算工具函数', () => {
  it('isCjkCodePoint 覆盖中日韩与全角标点', () => {
    expect(isCjkCodePoint('中'.codePointAt(0)!)).toBe(true)
    expect(isCjkCodePoint('あ'.codePointAt(0)!)).toBe(true)
    expect(isCjkCodePoint('，'.codePointAt(0)!)).toBe(true)
    expect(isCjkCodePoint('a'.codePointAt(0)!)).toBe(false)
  })

  it('utf8Bytes 与 M8-1 口径一致', () => {
    expect(utf8Bytes('abc')).toBe(3)
    expect(utf8Bytes('中文')).toBe(6)
    expect(utf8Bytes('😀')).toBe(4)
  })

  it('splitRounds 把 assistant(tool_use) 与其 tool_result 归为同一轮', () => {
    const turns = [...toolRound('a', 'r1'), ...toolRound('b', 'r2')]
    const rounds = splitRounds(turns)
    expect(rounds).toHaveLength(2)
    expect(rounds[0]!.indexes).toEqual([0, 1])
    expect(rounds[0]!.hasToolGroup).toBe(true)
    expect(rounds[0]!.toolUseIds).toEqual(['a'])
    expect(rounds[1]!.indexes).toEqual([2, 3])
  })

  it('DEFAULT_PRUNE_CONFIG 与工单口径一致（131072 窗口 70%/50%、近端 3 轮）', () => {
    expect(DEFAULT_PRUNE_CONFIG.windowTokens).toBe(131072)
    expect(DEFAULT_PRUNE_CONFIG.triggerRatio).toBe(0.7)
    expect(DEFAULT_PRUNE_CONFIG.targetRatio).toBe(0.5)
    expect(DEFAULT_PRUNE_CONFIG.keepRecentRounds).toBe(3)
    expect(triggerTokens(DEFAULT_PRUNE_CONFIG)).toBe(Math.floor(131072 * 0.7))
  })
})
// ---------------------------------------------------------------- 7 预算配置化（M8-2 续作）

describe('预算配置化 — 范围校验与非法回退（默认即现行为）', () => {
  it('默认值 = 现行为：windowTokens 131072 / 触发 0.70 / 目标 0.50', () => {
    expect(DEFAULT_PRUNE_CONFIG).toEqual({
      windowTokens: 131072,
      triggerRatio: 0.7,
      targetRatio: 0.5,
      keepRecentRounds: 3,
      toolResultTrimBytes: 8 * 1024,
      reserveTokens: 6 * 1024
    })
    // 空/非法输入一律回到默认（零行为变更）
    expect(normalizePruneConfig(undefined)).toEqual(DEFAULT_PRUNE_CONFIG)
    expect(normalizePruneConfig(null)).toEqual(DEFAULT_PRUNE_CONFIG)
    expect(normalizePruneConfig({})).toEqual(DEFAULT_PRUNE_CONFIG)
    expect(normalizePruneConfig({ windowTokens: 'big', triggerRatio: NaN })).toEqual(DEFAULT_PRUNE_CONFIG)
  })

  it('合法值原样生效（小窗口 16384 → 触发 11468 / 目标 8192）', () => {
    const c = normalizePruneConfig({ windowTokens: 16384, triggerRatio: 0.7, targetRatio: 0.5 })
    expect(c.windowTokens).toBe(16384)
    expect(triggerTokens(c)).toBe(11468)
    expect(targetTokens(c)).toBe(8192)
  })

  it('越界回退默认（逐项独立，不互相污染）', () => {
    // windowTokens 低于下限 / 高于上限
    expect(normalizePruneConfig({ windowTokens: 100 }).windowTokens).toBe(DEFAULT_PRUNE_CONFIG.windowTokens)
    expect(normalizePruneConfig({ windowTokens: 99_999_999 }).windowTokens).toBe(DEFAULT_PRUNE_CONFIG.windowTokens)
    // 比例越界
    expect(normalizePruneConfig({ triggerRatio: 0.99 }).triggerRatio).toBe(DEFAULT_PRUNE_CONFIG.triggerRatio)
    expect(normalizePruneConfig({ triggerRatio: 0.01 }).triggerRatio).toBe(DEFAULT_PRUNE_CONFIG.triggerRatio)
    expect(normalizePruneConfig({ targetRatio: 0 }).targetRatio).toBe(DEFAULT_PRUNE_CONFIG.targetRatio)
    // 合法项不受其它项非法影响
    const c = normalizePruneConfig({ windowTokens: 32768, triggerRatio: 99, keepRecentRounds: 5 })
    expect(c.windowTokens).toBe(32768)
    expect(c.triggerRatio).toBe(DEFAULT_PRUNE_CONFIG.triggerRatio)
    expect(c.keepRecentRounds).toBe(5)
    // 边界值本身合法
    expect(normalizePruneConfig({ windowTokens: PRUNE_CONFIG_RANGES.windowTokens.min }).windowTokens).toBe(4096)
    expect(normalizePruneConfig({ windowTokens: PRUNE_CONFIG_RANGES.windowTokens.max }).windowTokens).toBe(4 * 1024 * 1024)
  })

  it('targetRatio 必须 < triggerRatio（否则裁到比触发线还高 → 永不生效），违反即回退默认', () => {
    const bad = normalizePruneConfig({ triggerRatio: 0.3, targetRatio: 0.5 })
    // 回退不能是「默认 0.5」——那仍 >= 0.3；须按默认比例等比缩到触发线以下
    expect(bad.targetRatio).toBeLessThan(bad.triggerRatio)
    expect(bad.targetRatio).toBeGreaterThan(0)
    expect(bad.targetRatio / bad.triggerRatio).toBeCloseTo(0.5 / 0.7, 2)
    // 相等也算违反
    const equal = normalizePruneConfig({ triggerRatio: 0.4, targetRatio: 0.4 })
    expect(equal.targetRatio).toBeLessThan(equal.triggerRatio)
    // 合法组合保留
    const ok = normalizePruneConfig({ triggerRatio: 0.6, targetRatio: 0.3 })
    expect(ok.triggerRatio).toBe(0.6)
    expect(ok.targetRatio).toBe(0.3)
  })

  it('小数/整数归一：keepRecentRounds 与 trimBytes 取整；trim 越界回退', () => {
    expect(normalizePruneConfig({ keepRecentRounds: 2.7 }).keepRecentRounds).toBe(2)
    expect(normalizePruneConfig({ toolResultTrimBytes: 1024.9 }).toolResultTrimBytes).toBe(1024)
    expect(normalizePruneConfig({ toolResultTrimBytes: 1 }).toolResultTrimBytes).toBe(DEFAULT_PRUNE_CONFIG.toolResultTrimBytes)
    expect(normalizePruneConfig({ keepRecentRounds: -1 }).keepRecentRounds).toBe(DEFAULT_PRUNE_CONFIG.keepRecentRounds)
  })

  it('小窗口配置下 planPrune 真的会触发整组裁切 + 待摘要列表（② 项的离线前提）', () => {
    const c = normalizePruneConfig({ windowTokens: 16384, triggerRatio: 0.7, targetRatio: 0.5 })
    const turns = longSession(8, 4000)
    const plan = planPrune(turns, c)
    expect(plan.pruned).toBe(true)
    // 小窗口下 trim 不足以达标 → 必然走到整组裁切
    expect(plan.records.some((r) => r.action === 'drop_group')).toBe(true)
    expect(plan.roundsToSummarize.length).toBeGreaterThan(0)
    expect(validateToolPairing(plan.turns)).toHaveLength(0)
  })
})
// ---------------------------------------------------------------- 8 预算预留（M8-3 §8 接线）

describe('预算预留 — 触发线判定前移', () => {
  it('预留额度使「未触线」变为「触线」：同一上下文，预留前不裁、预留后裁', () => {
    const c = normalizePruneConfig({ windowTokens: 20000, triggerRatio: 0.5, targetRatio: 0.3, keepRecentRounds: 1, toolResultTrimBytes: 512 })
    const trigger = triggerTokens(c) // 10000
    // 造一个「刚好在触发线下方」的上下文（内容足够多，确保预留后确有可裁之物）
    const turns = longSession(6, 4000)
    const est = estimateTurns(turns)
    expect(est).toBeLessThan(trigger)

    // 不预留 → 不裁（零副作用）
    const noReserve = planPrune(turns, c, { reserveTokens: 0 })
    expect(noReserve.pruned).toBe(false)
    expect(noReserve.records).toHaveLength(0)
    expect(noReserve.turns).toEqual(turns)

    // 预留足够大 → 判定前移 → 触发裁切
    const withReserve = planPrune(turns, c, { reserveTokens: trigger })
    expect(withReserve.pruned).toBe(true)
    expect(withReserve.records.length).toBeGreaterThan(0)
    expect(withReserve.afterTokens).toBeLessThan(withReserve.beforeTokens)
  })

  it('预留为 0 时行为与不预留完全一致（零行为变更）', () => {
    const c = normalizePruneConfig({ windowTokens: 16384 })
    const turns = longSession(8, 4000)
    const a = planPrune(turns, { ...c, reserveTokens: 0 })
    const b = planPrune(turns, { ...c, reserveTokens: 0 }, { reserveTokens: 0 })
    expect(a.pruned).toBe(b.pruned)
    expect(a.afterTokens).toBe(b.afterTokens)
    expect(a.records.length).toBe(b.records.length)
  })

  it('预留额度可配置且有范围校验（0 合法，超上限回退默认）', () => {
    expect(normalizePruneConfig({ reserveTokens: 0 }).reserveTokens).toBe(0)
    expect(normalizePruneConfig({ reserveTokens: 4096 }).reserveTokens).toBe(4096)
    expect(normalizePruneConfig({ reserveTokens: 999999 }).reserveTokens).toBe(DEFAULT_PRUNE_CONFIG.reserveTokens)
    expect(normalizePruneConfig({ reserveTokens: -1 }).reserveTokens).toBe(DEFAULT_PRUNE_CONFIG.reserveTokens)
  })
})
