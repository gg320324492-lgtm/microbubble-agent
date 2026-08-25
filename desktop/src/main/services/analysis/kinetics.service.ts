// Kinetics Service — Phase 8-M1-D
// 纯函数: 一级 / 零级 / 拟二级动力学 LSQ 拟合 + R² + 残差 + 收敛判定.
// 模型:
//   first-order:        ln(C) = ln(C0) - k*t        (线性化 LSQ, k > 0)
//   zero-order:          C = C0 - k*t                 (线性化 LSQ, k > 0)
//   pseudo-second-order: t/C = 1/(k*C0²) + t/C0    (线性化 LSQ, k > 0)

import type { CurvePoint, DataPoint, FitParameters, KineticFitResult, KineticModelKind } from './types'

function linearLeastSquares(xs: number[], ys: number[]): { slope: number; intercept: number; r2: number; residual: number } {
  if (xs.length < 2) return { slope: 0, intercept: 0, r2: 0, residual: Infinity }
  const n = xs.length
  const meanX = xs.reduce((a, b) => a + b, 0) / n
  const meanY = ys.reduce((a, b) => a + b, 0) / n
  let sxy = 0
  let sxx = 0
  let syy = 0
  for (let i = 0; i < n; i++) {
    const dx = xs[i] - meanX
    const dy = ys[i] - meanY
    sxy += dx * dy
    sxx += dx * dx
    syy += dy * dy
  }
  if (sxx === 0) return { slope: 0, intercept: 0, r2: 0, residual: Infinity }
  const slope = sxy / sxx
  const intercept = meanY - slope * meanX
  const r2 = syy === 0 ? 1 : Math.max(0, Math.min(1, (sxy * sxy) / (sxx * syy)))
  let rss = 0
  for (let i = 0; i < n; i++) {
    const r = ys[i] - (slope * xs[i] + intercept)
    rss += r * r
  }
  return { slope, intercept, r2, residual: Math.sqrt(rss / n) }
}

function adjustR2(r2: number, n: number, p: number): number {
  if (n - p - 1 <= 0) return r2
  return 1 - (1 - r2) * (n - 1) / (n - p - 1)
}

function generateCurve(model: KineticModelKind, params: FitParameters, xMin: number, xMax: number, n: number = 50): CurvePoint[] {
  const curve: CurvePoint[] = []
  if (xMax <= xMin) return curve
  const step = (xMax - xMin) / (n - 1)
  for (let i = 0; i < n; i++) {
    const x = xMin + i * step
    let y = 0
    if (model === 'first-order') {
      const C0 = Math.exp(params['intercept'] ?? 0)
      const k = -(params['slope'] ?? 0)
      y = C0 * Math.exp(-k * x)
    } else if (model === 'zero-order') {
      const C0 = params['intercept'] ?? 0
      const k = -(params['slope'] ?? 0)
      y = C0 - k * x
    } else if (model === 'pseudo-second-order') {
      const inv_k_C02 = params['intercept'] ?? 0
      const inv_C0 = params['slope'] ?? 0
      const k = inv_C0 * inv_C0 / Math.max(inv_k_C02, 1e-9)
      const C0 = 1 / Math.max(inv_C0, 1e-9)
      y = (k * C0 * C0 * x) / (1 + k * C0 * x)
    }
    curve.push({ x, y })
  }
  return curve
}

function fitFirstOrder(data: DataPoint[]): KineticFitResult {
  const xs: number[] = []
  const ys: number[] = []
  for (const d of data) {
    if (!d.valid || !Number.isFinite(d.y) || d.y <= 0) continue
    xs.push(d.x)
    ys.push(Math.log(d.y))
  }
  const fit = linearLeastSquares(xs, ys)
  const k = -fit.slope
  const C0 = Math.exp(fit.intercept)
  const r2 = fit.r2
  const adjustedR2 = adjustR2(r2, xs.length, 2)
  const xMin = xs.length > 0 ? Math.min(...xs) : 0
  const xMax = xs.length > 0 ? Math.max(...xs) : 1
  return {
    model: 'first-order',
    parameters: { k, C0, halfLife: Math.log(2) / Math.max(k, 1e-9) },
    rSquared: r2,
    adjustedRSquared: adjustedR2,
    residualError: fit.residual,
    iterations: 1,
    converged: Number.isFinite(fit.residual),
    curve: generateCurve('first-order', { slope: fit.slope, intercept: fit.intercept }, xMin, xMax),
    interpretation: k > 0
      ? `一级动力学拟合: k = ${k.toFixed(4)} min⁻¹, C₀ = ${C0.toFixed(3)}, R² = ${r2.toFixed(3)}`
      : '数据不满足一级动力学特征 (k ≤ 0)'
  }
}

function fitZeroOrder(data: DataPoint[]): KineticFitResult {
  const xs: number[] = []
  const ys: number[] = []
  for (const d of data) {
    if (!d.valid || !Number.isFinite(d.y)) continue
    xs.push(d.x)
    ys.push(d.y)
  }
  const fit = linearLeastSquares(xs, ys)
  const k = -fit.slope
  const C0 = fit.intercept
  const r2 = fit.r2
  const adjustedR2 = adjustR2(r2, xs.length, 2)
  const xMin = xs.length > 0 ? Math.min(...xs) : 0
  const xMax = xs.length > 0 ? Math.max(...xs) : 1
  return {
    model: 'zero-order',
    parameters: { k, C0 },
    rSquared: r2,
    adjustedRSquared: adjustedR2,
    residualError: fit.residual,
    iterations: 1,
    converged: Number.isFinite(fit.residual),
    curve: generateCurve('zero-order', { slope: fit.slope, intercept: fit.intercept }, xMin, xMax),
    interpretation: k > 0
      ? `零级动力学拟合: k = ${k.toFixed(4)} mg/(L·min), C₀ = ${C0.toFixed(3)}, R² = ${r2.toFixed(3)}`
      : '数据不满足零级动力学特征 (k ≤ 0)'
  }
}

function fitPseudoSecondOrder(data: DataPoint[]): KineticFitResult {
  const xs: number[] = []
  const ys: number[] = []
  for (const d of data) {
    if (!d.valid || !Number.isFinite(d.y) || d.y <= 0 || d.x <= 0) continue
    xs.push(d.x)
    ys.push(d.x / d.y)
  }
  const fit = linearLeastSquares(xs, ys)
  const inv_C0 = fit.slope
  const inv_k_C02 = fit.intercept
  const C0 = 1 / Math.max(inv_C0, 1e-9)
  const k = C0 * C0 / Math.max(inv_k_C02, 1e-9)
  const r2 = fit.r2
  const adjustedR2 = adjustR2(r2, xs.length, 2)
  const xMin = xs.length > 0 ? Math.min(...xs) : 0
  const xMax = xs.length > 0 ? Math.max(...xs) : 1
  return {
    model: 'pseudo-second-order',
    parameters: { k, C0 },
    rSquared: r2,
    adjustedRSquared: adjustedR2,
    residualError: fit.residual,
    iterations: 1,
    converged: Number.isFinite(fit.residual),
    curve: generateCurve('pseudo-second-order', { slope: fit.slope, intercept: fit.intercept }, xMin, xMax),
    interpretation: k > 0
      ? `拟二级动力学拟合: k = ${k.toFixed(4)} g/(mg·min), C₀ = ${C0.toFixed(3)}, R² = ${r2.toFixed(3)}`
      : '数据不满足拟二级动力学特征 (k ≤ 0)'
  }
}

export function fitKinetic(model: KineticModelKind, data: DataPoint[]): KineticFitResult {
  if (model === 'first-order') return fitFirstOrder(data)
  if (model === 'zero-order') return fitZeroOrder(data)
  return fitPseudoSecondOrder(data)
}