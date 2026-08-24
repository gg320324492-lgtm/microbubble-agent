// Experiment Advisor — AI 推荐引擎。
//
// 输入: 实时指标 + 数字孪生预测 + 实验状态
// 输出: AIRecommendation 列表
// 纯确定性, 无 LLM 直连。

import type { AIRecommendation, RealtimeMetric } from '../../shared/control/experiment-control-schema'

export interface AdvisorContext {
  experimentId: string
  metrics: RealtimeMetric[]
  twinConfidence?: number
  experimentStatus?: string
}

export interface AdvisorRule {
  id: string
  matchMetric: string
  condition: (latestValue: number) => boolean
  buildRecommendation: (ctx: AdvisorContext) => Omit<AIRecommendation, 'id' | 'experimentId' | 'createdAt'>
}

export const DEFAULT_RULES: readonly AdvisorRule[] = Object.freeze([
  Object.freeze({
    id: 'optimize-ozone-flow',
    matchMetric: 'ozone_dose',
    condition: (v: number) => v < 3,
    buildRecommendation: (ctx: AdvisorContext) => ({
      kind: 'optimize',
      title: '提升臭氧流量',
      rationale: `当前臭氧剂量 ${ctx.metrics.find((m: RealtimeMetric) => m.metric === 'ozone_dose')?.value ?? '?'} mg/L 偏低, 建议提升到 5-7 mg/L 范围`,
      confidence: 0.8
    })
  }),
  Object.freeze({
    id: 'adjust-pressure',
    matchMetric: 'pressure',
    condition: (v: number) => v > 1.5 || v < 0.5,
    buildRecommendation: (ctx: AdvisorContext) => ({
      kind: 'adjust',
      title: '调整压力',
      rationale: `当前压力 ${ctx.metrics.find((m: RealtimeMetric) => m.metric === 'pressure')?.value ?? '?'} bar 偏离工作区间, 建议调整到 0.8-1.2 bar`,
      confidence: 0.75
    })
  }),
  Object.freeze({
    id: 'change-sampling-interval',
    matchMetric: 'temperature',
    condition: (v: number) => Math.abs(v - 25) > 10,
    buildRecommendation: () => ({
      kind: 'switch',
      title: '调整采样间隔',
      rationale: '温度偏离中心值过大, 建议提高采样频率以捕获瞬态',
      confidence: 0.7
    })
  }),
  Object.freeze({
    id: 'record-baseline',
    matchMetric: 'ph',
    condition: (v: number) => v < 6 || v > 8,
    buildRecommendation: () => ({
      kind: 'record',
      title: '记录基线数据',
      rationale: 'pH 偏离中性区间, 建议记录基线数据用于后续对比',
      confidence: 0.65
    })
  })
] as AdvisorRule[])

export class ExperimentAdvisor {
  private rules: AdvisorRule[]
  private nextId = 0

  constructor(rules: AdvisorRule[] = [...DEFAULT_RULES]) {
    this.rules = rules
  }

  addRule(rule: AdvisorRule): void {
    this.rules.push(rule)
  }

  ruleCount(): number { return this.rules.length }

  advise(ctx: AdvisorContext): AIRecommendation[] {
    const out: AIRecommendation[] = []
    const latestByMetric = new Map<string, number>()
    for (const m of ctx.metrics) {
      const cur = latestByMetric.get(m.metric)
      if (cur === undefined || m.timestamp >= (ctx.metrics.find((x) => x.metric === m.metric && x.timestamp > cur)?.timestamp ?? 0)) {
        latestByMetric.set(m.metric, m.value)
      }
    }
    // simpler: take the latest by timestamp per metric
    const latestMap = new Map<string, RealtimeMetric>()
    for (const m of ctx.metrics) {
      const cur = latestMap.get(m.metric)
      if (!cur || m.timestamp > cur.timestamp) latestMap.set(m.metric, m)
    }
    for (const [, latest] of latestMap) {
      for (const rule of this.rules) {
        if (rule.matchMetric !== latest.metric) continue
        if (!rule.condition(latest.value)) continue
        const partial = rule.buildRecommendation(ctx)
        this.nextId++
        const rec: AIRecommendation = {
          id: `rec-${this.nextId}-${Date.now()}`,
          experimentId: ctx.experimentId,
          createdAt: Date.now(),
          ...partial
        }
        out.push(rec)
      }
    }
    // confidence floor if twin low
    if (ctx.twinConfidence !== undefined && ctx.twinConfidence < 0.5) {
      for (const r of out) r.confidence = Math.max(0.1, r.confidence - 0.2)
    }
    return out
  }

  clearRules(): void { this.rules = [] }
}
