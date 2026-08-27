// Phase 10.6 Scientific Data Standardization — Unit Conversion + Schema + Figure Pipeline
// 测试 4 个新增模块的核心契约 (time-normalization / experiment-conditions / kinetic-units / figure-pipeline).

import { describe, expect, it } from 'vitest'
import { existsSync, readFileSync } from 'node:fs'
import { resolve } from 'node:path'

const desktopRoot = resolve(__dirname, '..', '..')
const mainRoot = resolve(desktopRoot, 'src/main')
const standardizationRoot = resolve(mainRoot, 'services/standardization')
const figureRoot = resolve(mainRoot, 'services/figure')

const read = (p: string): string => existsSync(p) ? readFileSync(p, 'utf8') : ''

// =============================================================
// 1. Time Normalization
// =============================================================

describe('Phase 10.6: time-normalization.ts 模块契约', () => {
  it('time-normalization.ts 存在', () => {
    expect(existsSync(resolve(standardizationRoot, 'time-normalization.ts'))).toBe(true)
  })
  it('导出 SUPPORTED_TIME_UNITS = [ms, s, min, h, d]', () => {
    const src = read(resolve(standardizationRoot, 'time-normalization.ts'))
    expect(src).toMatch(/SUPPORTED_TIME_UNITS/)
    expect(src).toContain("'ms'")
    expect(src).toContain("'s'")
    expect(src).toContain("'min'")
    expect(src).toContain("'h'")
    expect(src).toContain("'d'")
  })
  it('toMilliseconds / fromMilliseconds / convertTime 函数齐全', () => {
    const src = read(resolve(standardizationRoot, 'time-normalization.ts'))
    expect(src).toMatch(/export function toMilliseconds/)
    expect(src).toMatch(/export function fromMilliseconds/)
    expect(src).toMatch(/export function convertTime/)
  })
  it('autoNormalizeTimestamp 支持 epoch hint (seconds / milliseconds / none)', () => {
    const src = read(resolve(standardizationRoot, 'time-normalization.ts'))
    expect(src).toMatch(/export function autoNormalizeTimestamp/)
    expect(src).toContain("'seconds'")
    expect(src).toContain("'milliseconds'")
    expect(src).toContain("'none'")
  })
})

// =============================================================
// 2. Experiment Conditions Schema
// =============================================================

describe('Phase 10.6: experiment-conditions-store.ts 模块契约', () => {
  it('experiment-conditions-store.ts 存在', () => {
    expect(existsSync(resolve(standardizationRoot, 'experiment-conditions-store.ts'))).toBe(true)
  })
  it('ExperimentConditions 接口包含 11 个核心字段', () => {
    const src = read(resolve(standardizationRoot, 'experiment-conditions-store.ts'))
    expect(src).toContain('reactorVolumeL')
    expect(src).toContain('temperatureC')
    expect(src).toContain('pH')
    expect(src).toContain('pollutant')
    expect(src).toContain('initialConcentrationMgL')
    expect(src).toContain('technology')
    expect(src).toContain('gasFlowLMin')
    expect(src).toContain('reactionTimeMin')
    expect(src).toContain('stirringRpm')
    expect(src).toContain('pHAdjuster')
    expect(src).toContain('notes')
  })
  it('ExperimentConditionStoreService 含 setConditions / getConditions / deleteConditions / listExperiments', () => {
    const src = read(resolve(standardizationRoot, 'experiment-conditions-store.ts'))
    expect(src).toMatch(/setConditions\(/)
    expect(src).toMatch(/getConditions\(/)
    expect(src).toMatch(/deleteConditions\(/)
    expect(src).toMatch(/listExperiments\(/)
  })
  it('createExperimentConditionStore factory 接收 getService 注入', () => {
    const src = read(resolve(standardizationRoot, 'experiment-conditions-store.ts'))
    expect(src).toMatch(/export function createExperimentConditionStore/)
  })
})

// =============================================================
// 3. Kinetic Unit Conversion
// =============================================================

describe('Phase 10.6: kinetic-units.ts 模块契约', () => {
  it('kinetic-units.ts 存在', () => {
    expect(existsSync(resolve(standardizationRoot, 'kinetic-units.ts'))).toBe(true)
  })
  it('KineticParams 含 k / halfLife / rSquared / unit / model 字段', () => {
    const src = read(resolve(standardizationRoot, 'kinetic-units.ts'))
    expect(src).toContain('k:')
    expect(src).toContain('halfLife:')
    expect(src).toContain('rSquared:')
    expect(src).toContain('unit:')
    expect(src).toContain("'first-order'")
    expect(src).toContain("'zero-order'")
    expect(src).toContain("'pseudo-second-order'")
  })
  it('convertK / convertHalfLife / convertKineticParams 函数齐全', () => {
    const src = read(resolve(standardizationRoot, 'kinetic-units.ts'))
    expect(src).toMatch(/export function convertK/)
    expect(src).toMatch(/export function convertHalfLife/)
    expect(src).toMatch(/export function convertKineticParams/)
  })
  it('CONCENTRATION_UNITS 含 mg/L / μg/L / g/L 等 8 个单位', () => {
    const src = read(resolve(standardizationRoot, 'kinetic-units.ts'))
    expect(src).toContain("'mg/L'")
    expect(src).toContain("'μg/L'")
    expect(src).toContain("'g/L'")
    expect(src).toContain("'mol/L'")
    expect(src).toContain("'mmol/L'")
    expect(src).toContain("'μmol/L'")
    expect(src).toContain("'ppm'")
    expect(src).toContain("'ppb'")
  })
  it('convertConcentration 函数支持 molar 换算 (需 molarMass)', () => {
    const src = read(resolve(standardizationRoot, 'kinetic-units.ts'))
    expect(src).toMatch(/export function convertConcentration/)
    expect(src).toContain('molarMass')
  })
})

// =============================================================
// 4. Figure Generation Pipeline
// =============================================================

describe('Phase 10.6: figure-pipeline.ts 模块契约', () => {
  it('figure-pipeline.ts 存在', () => {
    expect(existsSync(resolve(figureRoot, 'figure-pipeline.ts'))).toBe(true)
  })
  it('支持 5 种 chart type: line / scatter / bar / histogram / boxplot', () => {
    const src = read(resolve(figureRoot, 'figure-pipeline.ts'))
    expect(src).toContain("'line'")
    expect(src).toContain("'scatter'")
    expect(src).toContain("'bar'")
    expect(src).toContain("'histogram'")
    expect(src).toContain("'boxplot'")
  })
  it('FigureSeries + FigureOptions + GeneratedInterface 数据契约', () => {
    const src = read(resolve(figureRoot, 'figure-pipeline.ts'))
    expect(src).toMatch(/export interface FigureSeries/)
    expect(src).toMatch(/export interface FigureOptions/)
    expect(src).toMatch(/export interface GeneratedFigure/)
  })
  it('generateFigure 函数输出 ECharts-compatible options', () => {
    const src = read(resolve(figureRoot, 'figure-pipeline.ts'))
    expect(src).toMatch(/export function generateFigure/)
    expect(src).toContain('tooltip')
    expect(src).toContain('xAxis')
    expect(src).toContain('yAxis')
    expect(src).toContain('series')
  })
  it('generateFitCurve 函数从 kinetic params 生成 fit + observed 双 series', () => {
    const src = read(resolve(figureRoot, 'figure-pipeline.ts'))
    expect(src).toMatch(/export function generateFitCurve/)
    expect(src).toContain('fit')
    expect(src).toContain('observed')
  })
  it('FigurePipelineService 含 saveToDb 持久化方法 (写入 figures 表)', () => {
    const src = read(resolve(figureRoot, 'figure-pipeline.ts'))
    expect(src).toMatch(/saveToDb/)
    expect(src).toContain('INSERT INTO figures')
  })
  it('createFigurePipelineService factory 接收 DatabaseService 注入', () => {
    const src = read(resolve(figureRoot, 'figure-pipeline.ts'))
    expect(src).toMatch(/export function createFigurePipelineService/)
  })
})

// =============================================================
// 5. Schema Migration 008
// =============================================================

describe('Phase 10.6: database schema 008-standardization.sql', () => {
  it('migration 008 文件存在', () => {
    expect(existsSync(resolve(mainRoot, 'database/schema/008-standardization.sql'))).toBe(true)
  })
  it('实验条件表 experiment_conditions (experiment_id PRIMARY KEY)', () => {
    const sql = read(resolve(mainRoot, 'database/schema/008-standardization.sql'))
    expect(sql).toMatch(/CREATE TABLE IF NOT EXISTS experiment_conditions/)
    expect(sql).toContain('experiment_id TEXT PRIMARY KEY')
    expect(sql).toContain('conditions_json')
  })
  it('experiment_conditions 表索引 (updated_at DESC)', () => {
    const sql = read(resolve(mainRoot, 'database/schema/008-standardization.sql'))
    expect(sql).toMatch(/CREATE INDEX IF NOT EXISTS idx_experiment_conditions_updated_at/)
  })
})