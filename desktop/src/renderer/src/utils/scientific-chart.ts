import type { EChartsOption } from 'echarts'

import type { ModelFitResult } from '../services/research/data-analysis.service'

const TIME_END_MINUTES = 120
const TIME_STEP_MINUTES = 5

export interface ResearchChartTheme {
  primary: string
  ai: string
  success: string
  text: string
  strongText: string
  border: string
  strongBorder: string
  surface: string
  fontFamily: string
}

type StyleReader = Pick<CSSStyleDeclaration, 'getPropertyValue'>

const FALLBACK_CHART_THEME: ResearchChartTheme = Object.freeze({
  primary: 'royalblue',
  ai: 'mediumpurple',
  success: 'seagreen',
  text: 'slategray',
  strongText: 'midnightblue',
  border: 'lightgray',
  strongBorder: 'darkgray',
  surface: 'white',
  fontFamily: 'sans-serif'
})

export function resolveResearchChartTheme(style?: StyleReader | null): ResearchChartTheme {
  const token = (name: string, fallback: string): string =>
    style?.getPropertyValue(name).trim() || fallback

  return {
    primary: token('--research-primary-500', FALLBACK_CHART_THEME.primary),
    ai: token('--research-ai-500', FALLBACK_CHART_THEME.ai),
    success: token('--research-success-500', FALLBACK_CHART_THEME.success),
    text: token('--research-text-secondary', FALLBACK_CHART_THEME.text),
    strongText: token('--research-text-primary', FALLBACK_CHART_THEME.strongText),
    border: token('--research-border-subtle', FALLBACK_CHART_THEME.border),
    strongBorder: token('--research-border-strong', FALLBACK_CHART_THEME.strongBorder),
    surface: token('--research-bg-card', FALLBACK_CHART_THEME.surface),
    fontFamily: token('--research-font-sans', FALLBACK_CHART_THEME.fontFamily)
  }
}

const MODEL_LABELS: Record<string, string> = {
  'first-order': '一级动力学',
  'zero-order': '零级动力学'
}

export function kineticModelLabel(model: string): string {
  return MODEL_LABELS[model] ?? `未知模型（${model}）`
}

function finiteOrNull(value: number): number | null {
  return Number.isFinite(value) ? value : null
}

function validUnitValue(value: number): number | null {
  return Number.isFinite(value) && value >= 0 && value <= 1 ? value : null
}

function validResidualValue(value: number): number | null {
  return Number.isFinite(value) && value >= 0 ? value : null
}

export function describeKineticFit(model?: ModelFitResult | null): string {
  const axes = '横轴为时间（分钟），纵轴为归一化浓度 C/C₀。'
  if (!model) return `动力学拟合图。${axes} 暂无有效模型，无法绘图。`

  const modelLabel = kineticModelLabel(model.model)
  const rSquared = validUnitValue(model.rSquared)
  const credibility = rSquared === null
    ? '拟合可信度待评估'
    : `拟合可信度 ${rSquared.toFixed(3)}`
  const residual = validResidualValue(model.residualError)
  const residualDescription = residual === null
    ? '残差范围待评估'
    : `残差范围 ±${residual.toFixed(3)}`
  const base = `动力学拟合图，模型 ${modelLabel}，${credibility}，${residualDescription}。${axes}`

  if (model.model !== 'first-order') {
    return `${base} 当前科学图表不支持该模型绘图，仅支持具有有效 k 参数的一级动力学模型。`
  }
  const k = finiteOrNull(model.parameters?.k)
  if (k === null || k <= 0) return `${base} 缺少有效的一级动力学参数 k，暂无可绘制曲线。`
  return base
}

export function formatKineticTooltip(params: unknown): string {
  const candidates = Array.isArray(params) ? params : [params]
  const selected = candidates.find(item => asTooltipRecord(item).seriesName === '模型预测曲线') ?? candidates[0]
  const value = asTooltipRecord(selected).value
  if (!Array.isArray(value) || !Number.isFinite(value[0]) || !Number.isFinite(value[1])) {
    return '暂无有效的动力学图表数据'
  }
  const time = Number(value[0])
  const concentration = Number(value[1])
  const timeLabel = Number.isInteger(time) ? String(time) : time.toFixed(1)
  return `时间：${timeLabel} 分钟<br/>归一化浓度 C/C₀：${concentration.toFixed(3)}`
}

function asTooltipRecord(value: unknown): Record<string, unknown> {
  return value !== null && typeof value === 'object' ? value as Record<string, unknown> : {}
}

function baseOption(description: string, hasResidualRange: boolean): EChartsOption {
  return {
    aria: {
      enabled: true,
      description
    },
    animationDuration: 420,
    grid: { left: 62, right: 24, top: 34, bottom: 52, containLabel: true },
    tooltip: {
      trigger: 'axis',
      formatter: formatKineticTooltip
    },
    legend: {
      bottom: 4,
      data: hasResidualRange ? ['模型预测曲线', '残差范围'] : ['模型预测曲线']
    },
    xAxis: {
      type: 'value',
      name: '时间（分钟）',
      min: 0,
      max: TIME_END_MINUTES
    },
    yAxis: {
      type: 'value',
      name: '归一化浓度 C/C₀',
      min: 0,
      max: 1
    },
    series: []
  }
}

export function buildKineticFitOption(model: ModelFitResult): EChartsOption {
  const residual = validResidualValue(model.residualError)
  const option = baseOption(describeKineticFit(model), residual !== null)
  const k = finiteOrNull(model.parameters?.k)

  if (model.model !== 'first-order' || k === null || k <= 0) return option

  const prediction: Array<[number, number]> = []
  const lower: Array<[number, number]> = []
  const upper: Array<[number, number]> = []
  const residualMagnitude = residual

  for (let time = 0; time <= TIME_END_MINUTES; time += TIME_STEP_MINUTES) {
    const value = Math.exp(-k * time)
    prediction.push([time, value])
    if (residualMagnitude !== null) {
      const lowerBound = Math.max(0, value - residualMagnitude)
      const upperBound = Math.min(1, value + residualMagnitude)
      lower.push([time, lowerBound])
      upper.push([time, upperBound - lowerBound])
    }
  }

  const residualSeries = residualMagnitude === null
    ? []
    : [
        {
          name: '残差范围下界',
          type: 'line' as const,
          data: lower,
          symbol: 'none',
          silent: true,
          stack: 'residual-range',
          lineStyle: { width: 0, opacity: 0 },
          areaStyle: { opacity: 0 },
          tooltip: { show: false }
        },
        {
          name: '残差范围',
          type: 'line' as const,
          data: upper,
          symbol: 'none',
          silent: true,
          stack: 'residual-range',
          lineStyle: { width: 0, opacity: 0 },
          areaStyle: { opacity: 0.14 },
          tooltip: { show: false }
        }
      ]

  option.series = [
    ...residualSeries,
    {
      name: '模型预测曲线',
      type: 'line',
      data: prediction,
      smooth: true,
      showSymbol: false,
      symbol: 'circle',
      lineStyle: { width: 3 },
      emphasis: { focus: 'series' }
    }
  ]
  return option
}
