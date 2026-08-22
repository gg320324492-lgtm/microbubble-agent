// Dataset Analysis Adapter (Phase 7-T6: Scientific Tool Adapters).
//
// Phase 7-T6 strict: pure function, no IO, no state, no external calls.

import type { ToolAdapter } from '@shared/tools/tool-adapter-schema'

interface DatasetAnalysisInput {
  values: number[]
}

interface DatasetStats {
  count: number
  mean: number
  std: number
  min: number
  max: number
}

function validateInput(input: unknown): { ok: true; value: DatasetAnalysisInput } | { ok: false; error: string } {
  if (!input || typeof input !== 'object') return { ok: false, error: 'args must be an object' }
  const a = input as Record<string, unknown>
  if (!Array.isArray(a.values)) return { ok: false, error: 'values must be an array' }
  if (a.values.length === 0) return { ok: false, error: 'values array is empty' }
  for (const v of a.values) {
    if (typeof v !== 'number' || !Number.isFinite(v)) return { ok: false, error: 'values contains non-number' }
  }
  return { ok: true, value: { values: a.values as number[] } }
}

function computeStats(values: number[]): DatasetStats {
  const n = values.length
  let sum = 0
  for (const v of values) sum += v
  const mean = sum / n
  let sqDiff = 0
  for (const v of values) sqDiff += (v - mean) ** 2
  // Phase 7-T6 strict: population std (divide by N). Sample std (N-1) is Phase 7-T+ if needed.
  const std = Math.sqrt(sqDiff / n)
  let min = values[0]!
  let max = values[0]!
  for (const v of values) {
    if (v < min) min = v
    if (v > max) max = v
  }
  return { count: n, mean, std, min, max }
}

export const DATASET_ANALYSIS_ADAPTER: ToolAdapter = {
  toolId: 'tool:dataset-analysis',
  version: '1.0.0',
  execute: async (args) => {
    const v = validateInput(args)
    if (!v.ok) return { success: false, error: { code: 'INVALID_ARGS', message: v.error } }
    try {
      const stats = computeStats(v.value.values)
      return { success: true, data: stats as unknown as Record<string, unknown> }
    } catch (e) {
      return {
        success: false,
        error: {
          code: 'EXECUTION_ERROR',
          message: e instanceof Error ? e.message : String(e)
        }
      }
    }
  }
}
