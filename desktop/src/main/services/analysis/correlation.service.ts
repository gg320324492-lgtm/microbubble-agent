// Correlation Service — Phase 8-M1-D
// 纯函数: Pearson r + t 检验 p-value + 强度判定.

import type { CorrelationResult, DataPoint } from './types'

function studentTPValue(r: number, n: number): number {
  if (n < 3) return 1
  if (Math.abs(r) >= 1) return 0
  // t = r * sqrt((n-2)/(1-r²))
  const t = r * Math.sqrt((n - 2) / Math.max(1 - r * r, 1e-12))
  // 双尾 p-value 近似 (t 分布; n 大时退化为正态近似)
  if (n > 30) {
    // 正态近似
    const z = Math.abs(t)
    const phiUnused = Math.exp(-z * z / 2) / Math.sqrt(2 * Math.PI)
    void phiUnused
    return 2 * (1 - normalCdf(z))
  }
  // t 分布精确近似 (Lange 近似)
  const v = n - 2
  const x = v / (v + t * t)
  const a = v / 2
  const b = 0.5
  return regularizedIncompleteBeta(x, a, b)
}

function normalCdf(z: number): number {
  // Abramowitz & Stegun 近似
  const t = 1 / (1 + 0.2316419 * z)
  const d = 0.3989422804014327 * Math.exp(-z * z / 2)
  const p = d * t * (0.319381530 + t * (-0.356563782 + t * (1.781477937 + t * (-1.821255978 + t * 1.330274429))))
  return 1 - p
}

function lnGamma(x: number): number {
  // Lanczos 近似
  const c = [76.18009172947146, -86.50532032941677, 24.01409824083091, -1.231739572450155, 0.1208650973866179e-2, -0.5395239384953e-5]
  let y = x
  const tmp = x + 5.5 - (x + 0.5) * Math.log(x + 5.5)
  let ser = 1.000000000190015
  for (let j = 0; j < 6; j++) {
    y += 1
    ser += c[j] / y
  }
  return -tmp + Math.log((2.5066282746310005 * ser) / x)
}

function regularizedIncompleteBeta(x: number, a: number, b: number): number {
  if (x <= 0) return 0
  if (x >= 1) return 1
  const bt = Math.exp(
    -lnGamma(a + b) + lnGamma(a) + lnGamma(b) + a * Math.log(x) + b * Math.log(1 - x)
  )
  if (x < (a + 1) / (a + b + 2)) {
    return bt * betacf(x, a, b) / a
  }
  return 1 - bt * betacf(1 - x, b, a) / b
}

function betacf(x: number, a: number, b: number): number {
  const maxIter = 100
  const eps = 3e-7
  let qab = a + b
  let qap = a + 1
  let qam = a - 1
  let c = 1
  let d = 1 - qab * x / qap
  if (Math.abs(d) < 1e-30) d = 1e-30
  d = 1 / d
  let h = d
  for (let m = 1; m <= maxIter; m++) {
    const m2 = 2 * m
    let aa = m * (b - m) * x / ((qam + m2) * (a + m2))
    d = 1 + aa * d
    if (Math.abs(d) < 1e-30) d = 1e-30
    c = 1 + aa / c
    if (Math.abs(c) < 1e-30) c = 1e-30
    d = 1 / d
    h *= d * c
    aa = -(a + m) * (qab + m) * x / ((a + m2) * (qap + m2))
    d = 1 + aa * d
    if (Math.abs(d) < 1e-30) d = 1e-30
    c = 1 + aa / c
    if (Math.abs(c) < 1e-30) c = 1e-30
    d = 1 / d
    const del = d * c
    h *= del
    if (Math.abs(del - 1) < eps) break
  }
  return h
}

export function computeCorrelation(xMetric: string, yMetric: string, data: DataPoint[]): CorrelationResult {
  const valid = data.filter((d) => d.valid && Number.isFinite(d.x) && Number.isFinite(d.y))
  if (valid.length < 3) {
    return { xMetric, yMetric, pearsonR: 0, pearsonP: 1, strength: 0, n: valid.length, interpretation: '数据不足' }
  }
  const xs = valid.map((d) => d.x)
  const ys = valid.map((d) => d.y)
  const n = xs.length
  const meanX = xs.reduce((a, b) => a + b, 0) / n
  const meanY = ys.reduce((a, b) => a + b, 0) / n
  let sxy = 0, sxx = 0, syy = 0
  for (let i = 0; i < n; i++) {
    const dx = xs[i] - meanX
    const dy = ys[i] - meanY
    sxy += dx * dy
    sxx += dx * dx
    syy += dy * dy
  }
  const denom = Math.sqrt(sxx * syy)
  const r = denom === 0 ? 0 : sxy / denom
  const p = studentTPValue(r, n)
  const abs = Math.abs(r)
  const strength: 0 | 1 | 2 | 3 = abs < 0.2 ? 0 : abs < 0.4 ? 1 : abs < 0.7 ? 2 : 3
  return {
    xMetric, yMetric,
    pearsonR: r, pearsonP: p, strength, n,
    interpretation: `${xMetric} vs ${yMetric}: r = ${r.toFixed(3)} (${['无', '弱', '中', '强'][strength]}), p = ${p.toFixed(4)}, n = ${n}`
  }
}