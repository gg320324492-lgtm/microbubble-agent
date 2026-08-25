// Regression Service — Phase 8-M1-D
// 纯函数: OLS 多项式回归 + R² + adjusted R² + 系数.
// degree 1-4 (degree 1 退化为线性).

import type { CurvePoint, DataPoint, FitParameters, RegressionDegree, RegressionFitResult } from './types'

function designMatrix(xs: number[], degree: RegressionDegree): number[][] {
  const rows: number[][] = []
  for (const x of xs) {
    const row: number[] = []
    for (let d = 0; d <= degree; d++) row.push(Math.pow(x, d))
    rows.push(row)
  }
  return rows
}

function transpose(m: number[][]): number[][] {
  const r = m.length
  const c = m[0]?.length ?? 0
  const t: number[][] = []
  for (let j = 0; j < c; j++) {
    const row: number[] = []
    for (let i = 0; i < r; i++) row.push(m[i][j])
    t.push(row)
  }
  return t
}

function matMul(a: number[][], b: number[][]): number[][] {
  const r = a.length
  const k = a[0]?.length ?? 0
  const c = b[0]?.length ?? 0
  const out: number[][] = []
  for (let i = 0; i < r; i++) {
    const row: number[] = []
    for (let j = 0; j < c; j++) {
      let s = 0
      for (let x = 0; x < k; x++) s += (a[i][x] ?? 0) * (b[x][j] ?? 0)
      row.push(s)
    }
    out.push(row)
  }
  return out
}

/** 高斯消元求线性方程组 Ax = b. 返回 x 或 null (奇异). */
function solveLinear(A: number[][], b: number[]): number[] | null {
  const n = A.length
  if (n === 0) return []
  const m: number[][] = A.map((row, i) => [...row, b[i]])
  for (let k = 0; k < n; k++) {
    let pivot = k
    let maxVal = Math.abs(m[k][k] ?? 0)
    for (let i = k + 1; i < n; i++) {
      const v = Math.abs(m[i][k] ?? 0)
      if (v > maxVal) { maxVal = v; pivot = i }
    }
    if (maxVal < 1e-12) return null
    if (pivot !== k) { const tmp = m[k]; m[k] = m[pivot]; m[pivot] = tmp }
    const akk = m[k][k] ?? 0
    for (let i = k + 1; i < n; i++) {
      const factor = (m[i][k] ?? 0) / akk
      for (let j = k; j <= n; j++) m[i][j] = (m[i][j] ?? 0) - factor * (m[k][j] ?? 0)
    }
  }
  const x = new Array<number>(n).fill(0)
  for (let i = n - 1; i >= 0; i--) {
    let s = m[i][n] ?? 0
    for (let j = i + 1; j < n; j++) s -= (m[i][j] ?? 0) * x[j]
    x[i] = s / (m[i][i] ?? 1e-12)
  }
  return x
}

function predict(xs: number[], coeffs: number[]): number[] {
  return xs.map((x) => {
    let y = 0
    for (let d = 0; d < coeffs.length; d++) y += (coeffs[d] ?? 0) * Math.pow(x, d)
    return y
  })
}

function adjustR2(r2: number, n: number, p: number): number {
  if (n - p - 1 <= 0) return r2
  return 1 - (1 - r2) * (n - 1) / (n - p - 1)
}

export function fitRegression(degree: RegressionDegree, data: DataPoint[]): RegressionFitResult {
  const xs = data.filter((d) => d.valid && Number.isFinite(d.x) && Number.isFinite(d.y)).map((d) => d.x)
  const ys = data.filter((d) => d.valid && Number.isFinite(d.x) && Number.isFinite(d.y)).map((d) => d.y)
  if (xs.length < degree + 1) {
    return {
      degree, coefficients: new Array(degree + 1).fill(0), rSquared: 0, adjustedRSquared: 0, residualError: Infinity,
      curve: [], interpretation: `数据点不足 (n=${xs.length}, 需要 ≥ ${degree + 1})`
    }
  }
  const X = designMatrix(xs, degree)
  const Xt = transpose(X)
  const XtX = matMul(Xt, X)
  const Xty = matMul(Xt, ys.map((v) => [v])).map((r) => r[0] ?? 0)
  const coeffs = solveLinear(XtX, Xty) ?? new Array(degree + 1).fill(0)
  const yPred = predict(xs, coeffs)
  let ssRes = 0, ssTot = 0
  const meanY = ys.reduce((a, b) => a + b, 0) / ys.length
  for (let i = 0; i < ys.length; i++) {
    const yi = ys[i] ?? 0
    const ri = yi - (yPred[i] ?? 0)
    ssRes += ri * ri
    ssTot += (yi - meanY) * (yi - meanY)
  }
  const r2 = ssTot === 0 ? 1 : Math.max(0, Math.min(1, 1 - ssRes / ssTot))
  const adjusted = adjustR2(r2, xs.length, coeffs.length)
  const xMin = Math.min(...xs)
  const xMax = Math.max(...xs)
  const curve: CurvePoint[] = []
  const nCurve = 50
  for (let i = 0; i < nCurve; i++) {
    const x = xMin + (xMax - xMin) * i / (nCurve - 1)
    let y = 0
    for (let d = 0; d < coeffs.length; d++) y += (coeffs[d] ?? 0) * Math.pow(x, d)
    curve.push({ x, y })
  }
  const coeffsObj: FitParameters = {}
  for (let d = 0; d < coeffs.length; d++) coeffsObj[`c${d}`] = coeffs[d] ?? 0
  return {
    degree,
    coefficients: coeffs,
    rSquared: r2,
    adjustedRSquared: adjusted,
    residualError: Math.sqrt(ssRes / Math.max(xs.length, 1)),
    curve,
    interpretation: `多项式回归 (degree=${degree}): R² = ${r2.toFixed(3)}, adjusted R² = ${adjusted.toFixed(3)}, n = ${xs.length}`
  }
}