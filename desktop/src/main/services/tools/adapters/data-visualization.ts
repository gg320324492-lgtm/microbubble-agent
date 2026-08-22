// Data Visualization Adapter (Phase 7-T6: Scientific Tool Adapters).
//
// Phase 7-T6 strict: pure function, no IO, no state, no actual rendering.
// Phase 7-T+ will render figures in the renderer; this adapter only
// produces figure metadata.

import type { ToolAdapter } from '@shared/tools/tool-adapter-schema'

type PlotType =
  | 'kinetic-curve'
  | 'CFD-contour'
  | 'particle-distribution'
  | 'spectrum'
  | 'microscopy'
  | 'other'

interface DataVisualizationInput {
  title?: string
  series: Array<{ name?: string; x: number[]; y: number[] }>
  plotType: PlotType
  xLabel?: string
  yLabel?: string
}

interface FigureMetadata {
  figureId: string
  format: 'svg' | 'png' | 'canvas'
  width: number
  height: number
  title: string
  xLabel: string
  yLabel: string
  seriesCount: number
  plotType: PlotType
}

function validateInput(input: unknown): { ok: true; value: DataVisualizationInput } | { ok: false; error: string } {
  if (!input || typeof input !== 'object') return { ok: false, error: 'args must be an object' }
  const a = input as Record<string, unknown>
  if (!Array.isArray(a.series)) return { ok: false, error: 'series must be an array' }
  if (a.series.length === 0) return { ok: false, error: 'series array is empty' }
  if (typeof a.plotType !== 'string') return { ok: false, error: 'plotType must be a string' }
  const validPlotTypes = ['kinetic-curve', 'CFD-contour', 'particle-distribution', 'spectrum', 'microscopy', 'other']
  if (!validPlotTypes.includes(a.plotType as string)) {
    return { ok: false, error: `unknown plotType '${String(a.plotType)}'` }
  }
  for (const s of a.series) {
    if (!s || typeof s !== 'object') return { ok: false, error: 'series entry must be an object' }
    const se = s as Record<string, unknown>
    if (!Array.isArray(se.x)) return { ok: false, error: 'series.x must be an array' }
    if (!Array.isArray(se.y)) return { ok: false, error: 'series.y must be an array' }
    if ((se.x as unknown[]).length !== (se.y as unknown[]).length) {
      return { ok: false, error: 'series.x and series.y length mismatch' }
    }
  }
  return {
    ok: true,
    value: {
      title: typeof a.title === 'string' ? a.title : undefined,
      series: a.series as DataVisualizationInput['series'],
      plotType: a.plotType as PlotType,
      xLabel: typeof a.xLabel === 'string' ? a.xLabel : undefined,
      yLabel: typeof a.yLabel === 'string' ? a.yLabel : undefined
    }
  }
}

let figureCounter = 0
function nextFigureId(plotType: PlotType): string {
  figureCounter += 1
  return `fig:${plotType}:${Date.now()}:${figureCounter}`
}

export const DATA_VISUALIZATION_ADAPTER: ToolAdapter = {
  toolId: 'tool:data-visualization',
  version: '1.0.0',
  execute: async (args) => {
    const v = validateInput(args)
    if (!v.ok) return { success: false, error: { code: 'INVALID_ARGS', message: v.error } }
    try {
      const meta: FigureMetadata = {
        figureId: nextFigureId(v.value.plotType),
        format: 'svg',
        width: 800,
        height: 600,
        title: v.value.title ?? `${v.value.plotType} plot`,
        xLabel: v.value.xLabel ?? 'x',
        yLabel: v.value.yLabel ?? 'y',
        seriesCount: v.value.series.length,
        plotType: v.value.plotType
      }
      return { success: true, data: meta as unknown as Record<string, unknown> }
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
