// Digital Twin Templates — 预定义孪生模板。

export type TwinTemplateKind =
  | 'o3-mnb-degradation'
  | 'cfd-flow-optimization'
  | 'material-synthesis'

export const TWIN_TEMPLATE_KINDS: readonly TwinTemplateKind[] = Object.freeze([
  'o3-mnb-degradation', 'cfd-flow-optimization', 'material-synthesis'
])

export interface TwinTemplate {
  kind: TwinTemplateKind
  name: string
  domain: string
  inputs: string[]
  outputs: string[]
  parameterRanges: { name: string; range: string; unit: string }[]
}

const TEMPLATES: readonly TwinTemplate[] = Object.freeze([
  Object.freeze({
    kind: 'o3-mnb-degradation',
    name: 'O3-MNB 降解数字孪生',
    domain: '环境科学',
    inputs: ['o3_dose_mg_L', 'bubble_size_um', 'retention_time_min', 'ph'],
    outputs: ['degradation_rate_percent', 'toc_removal_percent'],
    parameterRanges: [
      { name: 'k', range: '0.001-1.0', unit: '1/min' },
      { name: 'c0', range: '0.1-100', unit: 'mg/L' }
    ]
  }),
  Object.freeze({
    kind: 'cfd-flow-optimization',
    name: 'CFD 流场优化数字孪生',
    domain: '工程',
    inputs: ['inlet_velocity_m_s', 'reactor_diameter_mm', 'baffle_angle_deg'],
    outputs: ['pressure_drop_pa', 'mixing_index'],
    parameterRanges: [
      { name: 'coef_v', range: '-5..5', unit: 'pa*s/m' },
      { name: 'coef_d', range: '-5..5', unit: 'pa/mm' }
    ]
  }),
  Object.freeze({
    kind: 'material-synthesis',
    name: '材料合成数字孪生',
    domain: '材料科学',
    inputs: ['temperature_c', 'reaction_time_h', 'precursor_concentration_mol_L'],
    outputs: ['particle_size_nm', 'crystal_phase_index'],
    parameterRanges: [
      { name: 'a_t', range: '0.001-1.0', unit: 'nm/c' },
      { name: 'a_h', range: '0.001-1.0', unit: '1/h' }
    ]
  })
] as TwinTemplate[])

export function getTwinTemplate(kind: TwinTemplateKind): TwinTemplate {
  const t = TEMPLATES.find((x) => x.kind === kind)
  if (!t) throw new Error(`unknown twin template kind: ${kind}`)
  return { ...t, inputs: [...t.inputs], outputs: [...t.outputs], parameterRanges: t.parameterRanges.map((p) => ({ ...p })) }
}

export function listTwinTemplates(): TwinTemplate[] {
  return TEMPLATES.map((t) => ({
    ...t,
    inputs: [...t.inputs],
    outputs: [...t.outputs],
    parameterRanges: t.parameterRanges.map((p) => ({ ...p }))
  }))
}

export const __testHelpers = { TEMPLATES, TWIN_TEMPLATE_KINDS }