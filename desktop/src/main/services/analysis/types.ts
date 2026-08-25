// Analysis Engine Types — Phase 8-M1-D
// 所有 analysis 服务共享的纯函数契约. 无 I/O, 无副作用.

export type KineticModelKind = 'first-order' | 'zero-order' | 'pseudo-second-order'
export type RegressionDegree = 1 | 2 | 3 | 4
export type CurveFamily = 'exponential-decay' | 'logarithmic' | 'power-law' | 'gaussian'

export interface StatisticsResult {
  metric: string
  count: number
  missingRate: number
  mean: number | null
  std: number | null
  median: number | null
  min: number | null
  max: number | null
  p25: number | null
  p75: number | null
  outliers: number
  /** 自由描述 (中文/英文) */
  interpretation: string
}

export interface FitParameters {
  [name: string]: number
}

export interface KineticFitResult {
  model: KineticModelKind
  parameters: FitParameters
  rSquared: number
  adjustedRSquared: number
  residualError: number
  iterations: number
  converged: boolean
  /** 拟合曲线采样点 (x, y) 用于绘图 */
  curve: Array<{ x: number; y: number }>
  interpretation: string
}

export interface RegressionFitResult {
  degree: RegressionDegree
  coefficients: number[]
  rSquared: number
  adjustedRSquared: number
  residualError: number
  /** 回归曲线采样点 */
  curve: Array<{ x: number; y: number }>
  interpretation: string
}

export interface CorrelationResult {
  xMetric: string
  yMetric: string
  pearsonR: number
  pearsonP: number
  /** 0 = 无, 1 = 弱, 2 = 中, 3 = 强 */
  strength: 0 | 1 | 2 | 3
  n: number
  interpretation: string
}

export interface CurvePoint {
  x: number
  y: number
}

export interface CurveFitResult {
  /** 例如 'exponential-decay' | 'logarithmic' | 'power-law' | 'gaussian' */
  family: string
  parameters: FitParameters
  rSquared: number
  curve: CurvePoint[]
  interpretation: string
}

export interface AnalysisInput {
  xValues: number[]
  yValues: number[]
}

export interface DataPoint {
  x: number
  y: number
  valid: boolean
}