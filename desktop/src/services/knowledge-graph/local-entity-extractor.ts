// Local Entity Extractor — 基于规则的确定性实体抽取（无 LLM）。
import type { DocumentChunk } from '../../shared/knowledge/document-schema'
import type { ScientificEntity, KnowledgeRelation, EntityType, RelationType } from '../../shared/knowledge-graph/knowledge-graph-schema'
import type { EntityExtractionResult } from '../../shared/knowledge-graph/entity-extractor-schema'

// ============ Rule Sets ============

const MATERIAL_PATTERNS = [
  'ozone', 'O₃', 'microbubble', 'micro-nano bubble', '微纳米气泡',
  'tetracycline', 'TC', '四环素', 'hydroxyl radical', '·OH',
  'nanobubble', 'nanoparticle', '活性氧', 'ROS', 'organic matter', 'water'
]

const PARAMETER_PATTERNS = [
  'pH', 'temperature', 'pressure', 'concentration', 'ozone dosage',
  'flow rate', 'bubble diameter', 'particle size', 'kLa',
  '曝气量', '气泡直径', '粒径', '臭氧浓度', '反应时间'
]

const MECHANISM_PATTERNS = [
  'hydroxyl radical', '·OH', 'mass transfer', 'oxidation',
  'ozonation', 'degradation', 'adsorption', 'singlet oxygen', '¹O₂',
  'hydroxyl', 'radical', 'pathway', '机理', '传质', '降解', '氧化'
]

const RESULT_PATTERNS = [
  'degradation rate', 'removal efficiency', 'TOC reduction',
  'reaction rate', 'half-life', 'mineralization',
  '去除率', '降解率', '反应速率', '半衰期', '矿化度'
]

const METHOD_PATTERNS = [
  'pseudo-first-order', 'first-order kinetics', 'Langmuir', 'Freundlich',
  'two-film theory', 'Box-Behnken', 'RSM',
  '一级动力学', '伪一级', '两膜理论', '响应面'
]

const PARAMETER_KEYWORDS: Record<string, EntityType> = {
  'ph': 'Parameter', '温度': 'Parameter', 'temperature': 'Parameter',
  'pressure': 'Parameter', '浓度': 'Parameter', 'concentration': 'Parameter',
  '曝气量': 'Parameter', '气泡直径': 'Parameter', 'bubble_diameter': 'Parameter',
  '粒径': 'Parameter', 'particle_size': 'Parameter',
  'ozone_dosage': 'Parameter', 'flow_rate': 'Parameter'
}

// ============ Detector ============

function detectPatterns(text: string, patterns: string[], type: EntityType, chunkId: string, baseConfidence: number): ScientificEntity[] {
  const lower = text.toLowerCase()
  const seen = new Set<string>()
  const entities: ScientificEntity[] = []
  for (const p of patterns) {
    if (lower.includes(p.toLowerCase()) && !seen.has(p)) {
      seen.add(p)
      entities.push({
        id: `${type.toLowerCase()}-${chunkId}-${p.replace(/\s+/g, '_')}`,
        name: p, type,
        description: `${type} detected in ${chunkId}`,
        sourceDocuments: [chunkId],
        confidence: baseConfidence,
        metadata: { chunkId }
      })
    }
  }
  return entities
}

function detectParameters(text: string, chunkId: string): ScientificEntity[] {
  const entities: ScientificEntity[] = []
  for (const [keyword, type] of Object.entries(PARAMETER_KEYWORDS)) {
    if (text.toLowerCase().includes(keyword.toLowerCase())) {
      entities.push({
        id: `parameter-${chunkId}-${keyword}`,
        name: keyword,
        type,
        description: `Parameter ${keyword}`,
        sourceDocuments: [chunkId],
        confidence: 0.82,
        metadata: { chunkId }
      })
    }
  }
  return entities
}

function inferRelations(entities: ScientificEntity[], chunkId: string): KnowledgeRelation[] {
  const relations: KnowledgeRelation[] = []
  const materials = entities.filter(e => e.type === 'Material')
  const parameters = entities.filter(e => e.type === 'Parameter')
  const mechanisms = entities.filter(e => e.type === 'Mechanism')
  const results = entities.filter(e => e.type === 'Result')

  for (const m of materials) {
    for (const p of parameters) {
      relations.push({
        id: `rel-${m.id}-${p.id}`, sourceEntityId: m.id, targetEntityId: p.id,
        relationType: 'measured_by' as RelationType, confidence: 0.70,
        evidence: `Material ${m.name} measured by parameter ${p.name} in ${chunkId}`
      })
    }
  }
  for (const mech of mechanisms) {
    for (const res of results) {
      relations.push({
        id: `rel-${mech.id}-${res.id}`, sourceEntityId: mech.id, targetEntityId: res.id,
        relationType: 'causes' as RelationType, confidence: 0.72,
        evidence: `Mechanism ${mech.name} causes result ${res.name} in ${chunkId}`
      })
    }
  }
  for (const mat of materials) {
    for (const mech of mechanisms) {
      relations.push({
        id: `rel-${mat.id}-${mech.id}`, sourceEntityId: mat.id, targetEntityId: mech.id,
        relationType: 'uses' as RelationType, confidence: 0.68,
        evidence: `Material ${mat.name} uses mechanism ${mech.name}`
      })
    }
  }
  return relations
}

// ============ Extractor ============

export const localEntityExtractor = {
  async extractEntities(chunk: DocumentChunk): Promise<EntityExtractionResult> {
    const text = chunk.content
    const entities: ScientificEntity[] = [
      ...detectPatterns(text, MATERIAL_PATTERNS, 'Material', chunk.id, 0.85),
      ...detectPatterns(text, PARAMETER_PATTERNS, 'Parameter', chunk.id, 0.80),
      ...detectPatterns(text, MECHANISM_PATTERNS, 'Mechanism', chunk.id, 0.78),
      ...detectPatterns(text, RESULT_PATTERNS, 'Result', chunk.id, 0.82),
      ...detectPatterns(text, METHOD_PATTERNS, 'Method', chunk.id, 0.75),
      ...detectParameters(text, chunk.id)
    ]
    // Deduplicate by name
    const seen = new Set<string>()
    const unique = entities.filter(e => {
      const key = `${e.type}:${e.name.toLowerCase()}`
      if (seen.has(key)) return false
      seen.add(key)
      return true
    })
    return { entities: unique, relations: [], confidence: 0.80 }
  },

  async extractRelations(chunk: DocumentChunk, entities: ScientificEntity[]): Promise<EntityExtractionResult> {
    const relations = inferRelations(entities, chunk.id)
    return { entities, relations, confidence: 0.72 }
  }
}
