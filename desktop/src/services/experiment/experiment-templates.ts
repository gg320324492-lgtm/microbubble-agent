// Experiment Templates — 4 个预定义实验模板。

export type ExperimentTemplateKind =
  | 'o3-mnb-degradation'
  | 'cfd-optimization'
  | 'material-experiment'
  | 'biological-experiment'

export const EXPERIMENT_TEMPLATE_KINDS: readonly ExperimentTemplateKind[] = Object.freeze([
  'o3-mnb-degradation', 'cfd-optimization', 'material-experiment', 'biological-experiment'
])

export interface ExperimentTemplate {
  kind: ExperimentTemplateKind
  name: string
  domain: string
  objective: string
  defaultParameters: string[]
  defaultObservations: string[]
}

const TEMPLATES: readonly ExperimentTemplate[] = Object.freeze([
  Object.freeze({
    kind: 'o3-mnb-degradation',
    name: '臭氧微纳米气泡降解实验',
    domain: '环境科学',
    objective: '评估 O3-MNB 系统对有机污染物的降解效率',
    defaultParameters: ['o3_dose_mg_L', 'bubble_size_um', 'retention_time_min', 'ph'],
    defaultObservations: ['degradation_rate_percent', 'toc_removal_percent', 'cod_removal_percent']
  }),
  Object.freeze({
    kind: 'cfd-optimization',
    name: 'CFD 流场优化实验',
    domain: '工程',
    objective: '通过 CFD 仿真优化反应器内流场分布',
    defaultParameters: ['inlet_velocity_m_s', 'reactor_diameter_mm', 'baffle_angle_deg'],
    defaultObservations: ['pressure_drop_pa', 'residence_time_s', 'mixing_index']
  }),
  Object.freeze({
    kind: 'material-experiment',
    name: '材料合成实验',
    domain: '材料科学',
    objective: '合成特定形貌的纳米材料并表征',
    defaultParameters: ['temperature_c', 'reaction_time_h', 'precursor_concentration_mol_L'],
    defaultObservations: ['particle_size_nm', 'crystal_phase', 'surface_area_m2_g']
  }),
  Object.freeze({
    kind: 'biological-experiment',
    name: '生物实验',
    domain: '生物医学',
    objective: '评估微泡对细胞活性与生物膜的影响',
    defaultParameters: ['cell_density_cells_mL', 'bubble_concentration_per_mL', 'exposure_time_min'],
    defaultObservations: ['cell_viability_percent', 'membrane_integrity_index', 'ros_level_au']
  })
] as ExperimentTemplate[])

export function getExperimentTemplate(kind: ExperimentTemplateKind): ExperimentTemplate {
  const t = TEMPLATES.find((x) => x.kind === kind)
  if (!t) throw new Error(`unknown experiment template kind: ${kind}`)
  return { ...t, defaultParameters: [...t.defaultParameters], defaultObservations: [...t.defaultObservations] }
}

export function listExperimentTemplates(): ExperimentTemplate[] {
  return TEMPLATES.map((t) => ({ ...t, defaultParameters: [...t.defaultParameters], defaultObservations: [...t.defaultObservations] }))
}

export const __testHelpers = { TEMPLATES, EXPERIMENT_TEMPLATE_KINDS }