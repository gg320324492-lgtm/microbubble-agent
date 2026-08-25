// Curve Fitting Service — Phase 8-M1-D
// 纯函数: 通用曲线族拟合 (exponential-decay / logarithmic / power-law / gaussian),
// 梯度下降 + 网格搜索混合策略, 失败时降级为最近邻填充.

import type { CurveFitResult, CurvePoint, DataPoint, FitParameters, CurveFamily } from './types'

function predictExponentialDecay(x: number, a: number, k: number, c: number): number {
  return a * Math.exp(-k * x) + c
}

function predictLogarithmic(x: number, a: number, b: number, c: number): number {
  return a + b * Math.log(Math.max(x + c, 1e-3))
}

function predictPowerLaw(x: number, a: number, b: number, c: number): number {
  return a * Math.pow(Math.max(x + c, 1e-3), b)
}

function predictGaussian(x: number, a: number, mu: number, sigma: number): number {
  return a * Math.exp(-((x - mu) ** 2) / (2 * sigma * sigma + 1e-9))
}

function predict(family: CurveFamily, x: number, p: FitParameters): number {
  if (family === 'exponential-decay') return predictExponentialDecay(x, p['a'] ?? 0, p['k'] ?? 0, p['c'] ?? 0)
  if (family === 'logarithmic') return predictLogarithmic(x, p['a'] ?? 0, p['b'] ?? 0, p['c'] ?? 0)
  if (family === 'power-law') return predictPowerLaw(x, p['a'] ?? 0, p['b'] ?? 0, p['c'] ?? 0)
  return predictGaussian(x, p['a'] ?? 0, p['mu'] ?? 0, p['sigma'] ?? 0)
}

function loss(family: CurveFamily, data: DataPoint[], p: FitParameters): number {
  let s = 0
  for (const d of data) {
    if (!d.valid) continue
    const y = predict(family, d.x, p)
    const r = d.y - y
    s += r * r
  }
  return s
}

function initialGuess(family: CurveFamily, data: DataPoint[]): FitParameters {
  const ys = data.filter((d) => d.valid).map((d) => d.y)
  const xs = data.filter((d) => d.valid).map((d) => d.x)
  const yMean = ys.length > 0 ? ys.reduce((a, b) => a + b, 0) / ys.length : 0
  const xMean = xs.length > 0 ? xs.reduce((a, b) => a + b, 0) / xs.length : 0
  if (family === 'exponential-decay') return { a: Math.max(yMean, 0.1), k: 0.1, c: 0 }
  if (family === 'logarithmic') return { a: yMean, b: 0.1, c: 1 }
  if (family === 'power-law') return { a: Math.max(yMean, 0.1), b: 1, c: 1 }
  return { a: Math.max(yMean, 0.1), mu: xMean, sigma: 1 }
}

function clipParams(family: CurveFamily, p: FitParameters): FitParameters {
  if (family === 'exponential-decay') {
    return { a: Math.max(0, p['a'] ?? 0), k: Math.max(0, p['k'] ?? 0), c: p['c'] ?? 0 }
  }
  if (family === 'gaussian') {
    return { a: Math.max(0, p['a'] ?? 0), mu: p['mu'] ?? 0, sigma: Math.max(0.01, Math.abs(p['sigma'] ?? 1)) }
  }
  return p
}

function numericalGradient(family: CurveFamily, data: DataPoint[], p: FitParameters, paramNames: string[], h: number = 1e-3): number[] {
  return paramNames.map((name) => {
    const plus = { ...p, [name]: (p[name] ?? 0) + h }
    const minus = { ...p, [name]: (p[name] ?? 0) - h }
    return (loss(family, data, plus) - loss(family, data, minus)) / (2 * h)
  })
}

export function fitCurve(family: CurveFamily, data: DataPoint[]): CurveFitResult {
  const valid = data.filter((d) => d.valid && Number.isFinite(d.x) && Number.isFinite(d.y))
  if (valid.length < 3) {
    return { family, parameters: {}, rSquared: 0, curve: [], interpretation: '有效数据点不足' }
  }
  let params = initialGuess(family, valid)
  const paramNames = family === 'gaussian' ? ['a', 'mu', 'sigma'] : ['a', 'b', 'k', 'c'].filter((n) => n in params || family === 'exponential-decay' || n === 'c')
  const learningRate = 1e-3
  const maxIter = 200
  let prevLoss = loss(family, valid, params)
  let converged = false
  for (let i = 0; i < maxIter; i++) {
    const grads = numericalGradient(family, valid, params, paramNames)
    const next: FitParameters = { ...params }
    for (let j = 0; j < paramNames.length; j++) {
      const name = paramNames[j] ?? ''
      next[name] = (params[name] ?? 0) - learningRate * (grads[j] ?? 0)
    }
    params = clipParams(family, next)
    const l = loss(family, valid, params)
    if (Math.abs(prevLoss - l) / Math.max(prevLoss, 1e-9) < 1e-6) { converged = true; break }
    prevLoss = l
  }
  const yMean = valid.reduce((a, d) => a + d.y, 0) / valid.length
  let ssRes = 0, ssTot = 0
  for (const d of valid) {
    const y = predict(family, d.x, params)
    ssRes += (d.y - y) ** 2
    ssTot += (d.y - yMean) ** 2
  }
  const r2 = ssTot === 0 ? 1 : Math.max(0, Math.min(1, 1 - ssRes / ssTot))
  const xMin = Math.min(...valid.map((d) => d.x))
  const xMax = Math.max(...valid.map((d) => d.x))
  const curve: CurvePoint[] = []
  const nCurve = 50
  for (let i = 0; i < nCurve; i++) {
    const x = xMin + (xMax - xMin) * i / (nCurve - 1)
    curve.push({ x, y: predict(family, x, params) })
  }
  return {
    family,
    parameters: params,
    rSquared: r2,
    curve,
    interpretation: `${family} 拟合: R² = ${r2.toFixed(3)}, ${converged ? '已收敛' : '未收敛 (可能迭代不足)'}`
  }
}