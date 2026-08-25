// Statistics Service — Phase 8-M1-D
// 纯函数: 描述性统计 (mean / std / median / percentile / outlier detection).
// 无 I/O, 无副作用, 单测友好.

import type { DataPoint, StatisticsResult } from './types'

function mean(values: number[]): number | null {
  if (values.length === 0) return null
  let sum = 0
  for (const v of values) sum += v
  return sum / values.length
}

function stddev(values: number[], mu: number | null): number | null {
  if (mu === null || values.length < 2) return null
  let s = 0
  for (const v of values) {
    const d = v - mu
    s += d * d
  }
  return Math.sqrt(s / (values.length - 1))
}

function median(sorted: number[]): number | null {
  const n = sorted.length
  if (n === 0) return null
  if (n % 2 === 1) return sorted[(n - 1) / 2]
  return (sorted[n / 2 - 1] + sorted[n / 2]) / 2
}

function percentile(sorted: number[], p: number): number | null {
  const n = sorted.length
  if (n === 0) return null
  if (n === 1) return sorted[0]
  const rank = (p / 100) * (n - 1)
  const lo = Math.floor(rank)
  const hi = Math.ceil(rank)
  if (lo === hi) return sorted[lo]
  const frac = rank - lo
  return sorted[lo] * (1 - frac) + sorted[hi] * frac
}

function countOutliers(values: number[], mu: number | null, sd: number | null): number {
  if (mu === null || sd === null || sd === 0) return 0
  let n = 0
  for (const v of values) {
    if (Math.abs((v - mu) / sd) > 3) n += 1
  }
  return n
}

export function computeStatistics(metric: string, data: DataPoint[]): StatisticsResult {
  const ys = data.filter((d) => d.valid && Number.isFinite(d.y)).map((d) => d.y)
  const total = data.length
  const valid = ys.length
  const missing = total - valid
  const mu = mean(ys)
  const sd = stddev(ys, mu)
  const sorted = [...ys].sort((a, b) => a - b)
  const med = median(sorted)
  const min = sorted[0] ?? null
  const max = sorted[sorted.length - 1] ?? null
  const p25 = percentile(sorted, 25)
  const p75 = percentile(sorted, 75)
  const outliers = countOutliers(ys, mu, sd)
  const missingRate = total === 0 ? 0 : missing / total

  let interp = ''
  if (valid === 0) {
    interp = `${metric} 全部数据缺失, 无法计算统计量`
  } else if (mu === null) {
    interp = `${metric} 数据异常`
  } else {
    interp = `${metric}: 均值 ${mu.toFixed(3)}, 标准差 ${sd !== null ? sd.toFixed(3) : 'NaN'}, n=${valid}, 缺失率 ${(missingRate * 100).toFixed(1)}%`
  }

  return {
    metric,
    count: valid,
    missingRate,
    mean: mu,
    std: sd,
    median: med,
    min,
    max,
    p25,
    p75,
    outliers,
    interpretation: interp
  }
}