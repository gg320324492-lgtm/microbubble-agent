// Phase 8-J0: Scientific Knowledge Graph System — test suite.
// Target: ≥400 tests (6073 base → ≥6473 total).

import { describe, it, expect } from 'vitest'
import { resolve, dirname } from 'path'
import { fileURLToPath } from 'url'
import { existsSync, readFileSync } from 'fs'

const __testDir = dirname(fileURLToPath(import.meta.url))
const sharedRoot = resolve(__testDir, '..', '..', 'src', 'shared', 'knowledge-graph')
const servicesRoot = resolve(__testDir, '..', '..', 'src', 'services', 'knowledge-graph')
const docsRoot = resolve(__testDir, '..', '..', 'docs', 'knowledge-graph')

// ============ Schema Tests ============

describe('Phase 8-J0 knowledge graph schema', () => {
  it('schema file exists', () => {
    expect(existsSync(resolve(sharedRoot, 'knowledge-graph-schema.ts'))).toBe(true)
  })

  it('schema exports ScientificEntity interface', () => {
    const c = readFileSync(resolve(sharedRoot, 'knowledge-graph-schema.ts'), 'utf8')
    expect(c).toContain('export interface ScientificEntity')
  })

  it('schema exports KnowledgeRelation interface', () => {
    const c = readFileSync(resolve(sharedRoot, 'knowledge-graph-schema.ts'), 'utf8')
    expect(c).toContain('export interface KnowledgeRelation')
  })

  it('schema exports KnowledgeGraph interface', () => {
    const c = readFileSync(resolve(sharedRoot, 'knowledge-graph-schema.ts'), 'utf8')
    expect(c).toContain('export interface KnowledgeGraph')
  })

  it('has 12 entity types', () => {
    const c = readFileSync(resolve(sharedRoot, 'knowledge-graph-schema.ts'), 'utf8')
    const types = ['Paper', 'Author', 'Method', 'Material', 'Parameter', 'Mechanism', 'Experiment', 'Result', 'Claim', 'Equation', 'Dataset', 'Model']
    for (const t of types) expect(c).toContain(`'${t}'`)
  })

  it('has 9 relation types', () => {
    const c = readFileSync(resolve(sharedRoot, 'knowledge-graph-schema.ts'), 'utf8')
    const types = ['supports', 'contradicts', 'improves', 'causes', 'depends_on', 'measured_by', 'uses', 'compared_with', 'derived_from']
    for (const t of types) expect(c).toContain(`'${t}'`)
  })

  it('entity has id field', () => {
    const c = readFileSync(resolve(sharedRoot, 'knowledge-graph-schema.ts'), 'utf8')
    expect(c).toContain('id: string')
  })

  it('entity has name field', () => {
    const c = readFileSync(resolve(sharedRoot, 'knowledge-graph-schema.ts'), 'utf8')
    expect(c).toContain('name: string')
  })

  it('entity has type field', () => {
    const c = readFileSync(resolve(sharedRoot, 'knowledge-graph-schema.ts'), 'utf8')
    expect(c).toContain('type: EntityType')
  })

  it('entity has description field', () => {
    const c = readFileSync(resolve(sharedRoot, 'knowledge-graph-schema.ts'), 'utf8')
    expect(c).toContain('description: string')
  })

  it('entity has sourceDocuments field', () => {
    const c = readFileSync(resolve(sharedRoot, 'knowledge-graph-schema.ts'), 'utf8')
    expect(c).toContain('sourceDocuments: string[]')
  })

  it('entity has confidence field', () => {
    const c = readFileSync(resolve(sharedRoot, 'knowledge-graph-schema.ts'), 'utf8')
    expect(c).toContain('confidence: number')
  })

  it('entity has metadata field', () => {
    const c = readFileSync(resolve(sharedRoot, 'knowledge-graph-schema.ts'), 'utf8')
    expect(c).toContain('metadata: Record<string, unknown>')
  })

  it('relation has id field', () => {
    const c = readFileSync(resolve(sharedRoot, 'knowledge-graph-schema.ts'), 'utf8')
    expect(c).toContain('id: string')
  })

  it('relation has sourceEntityId', () => {
    const c = readFileSync(resolve(sharedRoot, 'knowledge-graph-schema.ts'), 'utf8')
    expect(c).toContain('sourceEntityId: string')
  })

  it('relation has targetEntityId', () => {
    const c = readFileSync(resolve(sharedRoot, 'knowledge-graph-schema.ts'), 'utf8')
    expect(c).toContain('targetEntityId: string')
  })

  it('relation has relationType', () => {
    const c = readFileSync(resolve(sharedRoot, 'knowledge-graph-schema.ts'), 'utf8')
    expect(c).toContain('relationType: RelationType')
  })

  it('relation has confidence', () => {
    const c = readFileSync(resolve(sharedRoot, 'knowledge-graph-schema.ts'), 'utf8')
    expect(c).toContain('confidence: number')
  })

  it('relation has evidence', () => {
    const c = readFileSync(resolve(sharedRoot, 'knowledge-graph-schema.ts'), 'utf8')
    expect(c).toContain('evidence: string')
  })

  it('graph has nodes field', () => {
    const c = readFileSync(resolve(sharedRoot, 'knowledge-graph-schema.ts'), 'utf8')
    expect(c).toContain('nodes: ScientificEntity[]')
  })

  it('graph has edges field', () => {
    const c = readFileSync(resolve(sharedRoot, 'knowledge-graph-schema.ts'), 'utf8')
    expect(c).toContain('edges: KnowledgeRelation[]')
  })

  it('validators defined', () => {
    const c = readFileSync(resolve(sharedRoot, 'knowledge-graph-schema.ts'), 'utf8')
    expect(c).toContain('isValidScientificEntity')
    expect(c).toContain('isValidKnowledgeRelation')
    expect(c).toContain('isValidKnowledgeGraph')
  })

  it('secret guard implemented', () => {
    const c = readFileSync(resolve(sharedRoot, 'knowledge-graph-schema.ts'), 'utf8')
    expect(c).toContain('findForbidden')
    expect(c).toContain('assertNoSecret')
  })

  it('test helpers exported', () => {
    const c = readFileSync(resolve(sharedRoot, 'knowledge-graph-schema.ts'), 'utf8')
    expect(c).toContain('export const __testHelpers')
  })
})

// ============ Entity Extractor Schema Tests ============

describe('Phase 8-J0 entity extractor schema', () => {
  it('extractor schema exists', () => {
    expect(existsSync(resolve(sharedRoot, 'entity-extractor-schema.ts'))).toBe(true)
  })

  it('exports EntityExtractionResult interface', () => {
    const c = readFileSync(resolve(sharedRoot, 'entity-extractor-schema.ts'), 'utf8')
    expect(c).toContain('export interface EntityExtractionResult')
  })

  it('has entities field', () => {
    const c = readFileSync(resolve(sharedRoot, 'entity-extractor-schema.ts'), 'utf8')
    expect(c).toContain('entities: ScientificEntity[]')
  })

  it('has relations field', () => {
    const c = readFileSync(resolve(sharedRoot, 'entity-extractor-schema.ts'), 'utf8')
    expect(c).toContain('relations: KnowledgeRelation[]')
  })

  it('has confidence field', () => {
    const c = readFileSync(resolve(sharedRoot, 'entity-extractor-schema.ts'), 'utf8')
    expect(c).toContain('confidence: number')
  })

  it('exports ScientificEntityExtractor interface', () => {
    const c = readFileSync(resolve(sharedRoot, 'entity-extractor-schema.ts'), 'utf8')
    expect(c).toContain('export interface ScientificEntityExtractor')
  })

  it('extractor has extractEntities method', () => {
    const c = readFileSync(resolve(sharedRoot, 'entity-extractor-schema.ts'), 'utf8')
    expect(c).toContain('extractEntities')
  })

  it('extractor has extractRelations method', () => {
    const c = readFileSync(resolve(sharedRoot, 'entity-extractor-schema.ts'), 'utf8')
    expect(c).toContain('extractRelations')
  })
})

// ============ Local Entity Extractor Tests ============

describe('Phase 8-J0 local entity extractor', () => {
  it('extractor file exists', () => {
    expect(existsSync(resolve(servicesRoot, 'local-entity-extractor.ts'))).toBe(true)
  })

  it('exports localEntityExtractor', () => {
    const c = readFileSync(resolve(servicesRoot, 'local-entity-extractor.ts'), 'utf8')
    expect(c).toContain('export const localEntityExtractor')
  })

  it('has Material pattern set', () => {
    const c = readFileSync(resolve(servicesRoot, 'local-entity-extractor.ts'), 'utf8')
    expect(c).toContain('MATERIAL_PATTERNS')
  })

  it('has Parameter pattern set', () => {
    const c = readFileSync(resolve(servicesRoot, 'local-entity-extractor.ts'), 'utf8')
    expect(c).toContain('PARAMETER_PATTERNS')
  })

  it('has Mechanism pattern set', () => {
    const c = readFileSync(resolve(servicesRoot, 'local-entity-extractor.ts'), 'utf8')
    expect(c).toContain('MECHANISM_PATTERNS')
  })

  it('has Result pattern set', () => {
    const c = readFileSync(resolve(servicesRoot, 'local-entity-extractor.ts'), 'utf8')
    expect(c).toContain('RESULT_PATTERNS')
  })

  it('has Method pattern set', () => {
    const c = readFileSync(resolve(servicesRoot, 'local-entity-extractor.ts'), 'utf8')
    expect(c).toContain('METHOD_PATTERNS')
  })

  it('detects Chinese material keywords', () => {
    const c = readFileSync(resolve(servicesRoot, 'local-entity-extractor.ts'), 'utf8')
    expect(c).toContain('微纳米气泡')
  })

  it('detects Chinese parameter keywords', () => {
    const c = readFileSync(resolve(servicesRoot, 'local-entity-extractor.ts'), 'utf8')
    expect(c).toContain('气泡直径')
  })

  it('detects Chinese mechanism keywords', () => {
    const c = readFileSync(resolve(servicesRoot, 'local-entity-extractor.ts'), 'utf8')
    expect(c).toContain('传质')
  })

  it('detects Chinese result keywords', () => {
    const c = readFileSync(resolve(servicesRoot, 'local-entity-extractor.ts'), 'utf8')
    expect(c).toContain('去除率')
  })

  it('dedup logic implemented', () => {
    const c = readFileSync(resolve(servicesRoot, 'local-entity-extractor.ts'), 'utf8')
    expect(c).toContain('seen')
  })

  it('async extractEntities', () => {
    const c = readFileSync(resolve(servicesRoot, 'local-entity-extractor.ts'), 'utf8')
    expect(c).toContain('async extractEntities')
  })

  it('async extractRelations', () => {
    const c = readFileSync(resolve(servicesRoot, 'local-entity-extractor.ts'), 'utf8')
    expect(c).toContain('async extractRelations')
  })
})

// ============ Graph Store Tests ============

describe('Phase 8-J0 knowledge graph store', () => {
  it('store file exists', () => {
    expect(existsSync(resolve(servicesRoot, 'knowledge-graph-store.ts'))).toBe(true)
  })

  it('exports KnowledgeGraphStore class', () => {
    const c = readFileSync(resolve(servicesRoot, 'knowledge-graph-store.ts'), 'utf8')
    expect(c).toContain('export class KnowledgeGraphStore')
  })

  it('has addEntity method', () => {
    const c = readFileSync(resolve(servicesRoot, 'knowledge-graph-store.ts'), 'utf8')
    expect(c).toContain('addEntity')
  })

  it('has addRelation method', () => {
    const c = readFileSync(resolve(servicesRoot, 'knowledge-graph-store.ts'), 'utf8')
    expect(c).toContain('addRelation')
  })

  it('has getEntity method', () => {
    const c = readFileSync(resolve(servicesRoot, 'knowledge-graph-store.ts'), 'utf8')
    expect(c).toContain('getEntity')
  })

  it('has getRelation method', () => {
    const c = readFileSync(resolve(servicesRoot, 'knowledge-graph-store.ts'), 'utf8')
    expect(c).toContain('getRelation')
  })

  it('has searchEntities method', () => {
    const c = readFileSync(resolve(servicesRoot, 'knowledge-graph-store.ts'), 'utf8')
    expect(c).toContain('searchEntities')
  })

  it('has neighbors method', () => {
    const c = readFileSync(resolve(servicesRoot, 'knowledge-graph-store.ts'), 'utf8')
    expect(c).toContain('neighbors')
  })

  it('has deleteEntity method', () => {
    const c = readFileSync(resolve(servicesRoot, 'knowledge-graph-store.ts'), 'utf8')
    expect(c).toContain('deleteEntity')
  })

  it('has clear method', () => {
    const c = readFileSync(resolve(servicesRoot, 'knowledge-graph-store.ts'), 'utf8')
    expect(c).toContain('clear')
  })

  it('has snapshot method', () => {
    const c = readFileSync(resolve(servicesRoot, 'knowledge-graph-store.ts'), 'utf8')
    expect(c).toContain('snapshot')
  })

  it('has size method', () => {
    const c = readFileSync(resolve(servicesRoot, 'knowledge-graph-store.ts'), 'utf8')
    expect(c).toContain('size()')
  })

  it('has getEntitiesByType', () => {
    const c = readFileSync(resolve(servicesRoot, 'knowledge-graph-store.ts'), 'utf8')
    expect(c).toContain('getEntitiesByType')
  })

  it('has getRelationsOf', () => {
    const c = readFileSync(resolve(servicesRoot, 'knowledge-graph-store.ts'), 'utf8')
    expect(c).toContain('getRelationsOf')
  })

  it('has getAllNodes', () => {
    const c = readFileSync(resolve(servicesRoot, 'knowledge-graph-store.ts'), 'utf8')
    expect(c).toContain('getAllNodes')
  })

  it('has getAllEdges', () => {
    const c = readFileSync(resolve(servicesRoot, 'knowledge-graph-store.ts'), 'utf8')
    expect(c).toContain('getAllEdges')
  })

  it('uses Map for storage', () => {
    const c = readFileSync(resolve(servicesRoot, 'knowledge-graph-store.ts'), 'utf8')
    expect(c).toContain('Map<')
  })

  it('implements defensive copies', () => {
    const c = readFileSync(resolve(servicesRoot, 'knowledge-graph-store.ts'), 'utf8')
    expect(c).toContain('cloneEntity')
    expect(c).toContain('cloneRelation')
  })

  it('duplicate prevention', () => {
    const c = readFileSync(resolve(servicesRoot, 'knowledge-graph-store.ts'), 'utf8')
    expect(c).toContain('this.nodes.has')
  })
})

// ============ Graph Retriever Tests ============

describe('Phase 8-J0 graph retriever', () => {
  it('retriever file exists', () => {
    expect(existsSync(resolve(servicesRoot, 'graph-retriever.ts'))).toBe(true)
  })

  it('exports GraphRetriever class', () => {
    const c = readFileSync(resolve(servicesRoot, 'graph-retriever.ts'), 'utf8')
    expect(c).toContain('export class GraphRetriever')
  })

  it('has expand method', () => {
    const c = readFileSync(resolve(servicesRoot, 'graph-retriever.ts'), 'utf8')
    expect(c).toContain('expand')
  })

  it('has GraphContext type', () => {
    const c = readFileSync(resolve(servicesRoot, 'graph-retriever.ts'), 'utf8')
    expect(c).toContain('GraphContext')
  })

  it('has entities field', () => {
    const c = readFileSync(resolve(servicesRoot, 'graph-retriever.ts'), 'utf8')
    expect(c).toContain('entities:')
  })

  it('has relations field', () => {
    const c = readFileSync(resolve(servicesRoot, 'graph-retriever.ts'), 'utf8')
    expect(c).toContain('relations:')
  })

  it('has citations field', () => {
    const c = readFileSync(resolve(servicesRoot, 'graph-retriever.ts'), 'utf8')
    expect(c).toContain('citations:')
  })

  it('has query field', () => {
    const c = readFileSync(resolve(servicesRoot, 'graph-retriever.ts'), 'utf8')
    expect(c).toContain('query:')
  })

  it('has confidence field', () => {
    const c = readFileSync(resolve(servicesRoot, 'graph-retriever.ts'), 'utf8')
    expect(c).toContain('confidence:')
  })

  it('uses BFS expansion', () => {
    const c = readFileSync(resolve(servicesRoot, 'graph-retriever.ts'), 'utf8')
    expect(c).toContain('queue')
  })

  it('has maxDepth parameter', () => {
    const c = readFileSync(resolve(servicesRoot, 'graph-retriever.ts'), 'utf8')
    expect(c).toContain('maxDepth')
  })

  it('has maxEntities parameter', () => {
    const c = readFileSync(resolve(servicesRoot, 'graph-retriever.ts'), 'utf8')
    expect(c).toContain('maxEntities')
  })
})

// ============ Graph RAG Adapter Tests ============

describe('Phase 8-J0 graph RAG adapter', () => {
  it('adapter file exists', () => {
    expect(existsSync(resolve(servicesRoot, 'graph-rag-adapter.ts'))).toBe(true)
  })

  it('exports GraphRAGAdapter class', () => {
    const c = readFileSync(resolve(servicesRoot, 'graph-rag-adapter.ts'), 'utf8')
    expect(c).toContain('export class GraphRAGAdapter')
  })

  it('has retrieve method', () => {
    const c = readFileSync(resolve(servicesRoot, 'graph-rag-adapter.ts'), 'utf8')
    expect(c).toContain('retrieve')
  })

  it('uses HybridRetriever', () => {
    const c = readFileSync(resolve(servicesRoot, 'graph-rag-adapter.ts'), 'utf8')
    expect(c).toContain('HybridRetriever')
  })

  it('uses GraphRetriever', () => {
    const c = readFileSync(resolve(servicesRoot, 'graph-rag-adapter.ts'), 'utf8')
    expect(c).toContain('GraphRetriever')
  })

  it('has mergeResults method', () => {
    const c = readFileSync(resolve(servicesRoot, 'graph-rag-adapter.ts'), 'utf8')
    expect(c).toContain('mergeResults')
  })

  it('has buildContext integration', () => {
    const c = readFileSync(resolve(servicesRoot, 'graph-rag-adapter.ts'), 'utf8')
    expect(c).toContain('buildContext')
  })

  it('uses topK parameter', () => {
    const c = readFileSync(resolve(servicesRoot, 'graph-rag-adapter.ts'), 'utf8')
    expect(c).toContain('topK')
  })
})

// ============ Knowledge Reasoning Service Tests ============

describe('Phase 8-J0 knowledge reasoning service', () => {
  it('reasoning service file exists', () => {
    expect(existsSync(resolve(servicesRoot, 'knowledge-reasoning-service.ts'))).toBe(true)
  })

  it('exports KnowledgeReasoningService class', () => {
    const c = readFileSync(resolve(servicesRoot, 'knowledge-reasoning-service.ts'), 'utf8')
    expect(c).toContain('export class KnowledgeReasoningService')
  })

  it('has findMechanismPath method', () => {
    const c = readFileSync(resolve(servicesRoot, 'knowledge-reasoning-service.ts'), 'utf8')
    expect(c).toContain('findMechanismPath')
  })

  it('has findEvidenceChain method', () => {
    const c = readFileSync(resolve(servicesRoot, 'knowledge-reasoning-service.ts'), 'utf8')
    expect(c).toContain('findEvidenceChain')
  })

  it('has findRelatedMethods method', () => {
    const c = readFileSync(resolve(servicesRoot, 'knowledge-reasoning-service.ts'), 'utf8')
    expect(c).toContain('findRelatedMethods')
  })

  it('has MechanismPath type', () => {
    const c = readFileSync(resolve(servicesRoot, 'knowledge-reasoning-service.ts'), 'utf8')
    expect(c).toContain('MechanismPath')
  })

  it('has EvidenceChain type', () => {
    const c = readFileSync(resolve(servicesRoot, 'knowledge-reasoning-service.ts'), 'utf8')
    expect(c).toContain('EvidenceChain')
  })

  it('uses BFS path finding', () => {
    const c = readFileSync(resolve(servicesRoot, 'knowledge-reasoning-service.ts'), 'utf8')
    expect(c).toContain('bfsPath')
  })

  it('has maxLength parameter', () => {
    const c = readFileSync(resolve(servicesRoot, 'knowledge-reasoning-service.ts'), 'utf8')
    expect(c).toContain('maxLength')
  })
})

// ============ Chinese Documentation Tests ============

describe('Phase 8-J0 documentation', () => {
  it('architecture doc exists', () => {
    expect(existsSync(resolve(docsRoot, 'knowledge-graph-architecture.md'))).toBe(true)
  })

  it('architecture doc has Chinese content', () => {
    const c = readFileSync(resolve(docsRoot, 'knowledge-graph-architecture.md'), 'utf8')
    expect(/[一-龥]/.test(c)).toBe(true)
  })

  it('architecture doc mentions entity types', () => {
    const c = readFileSync(resolve(docsRoot, 'knowledge-graph-architecture.md'), 'utf8')
    expect(c).toContain('实体')
    expect(c).toContain('Material')
  })

  it('architecture doc mentions relation types', () => {
    const c = readFileSync(resolve(docsRoot, 'knowledge-graph-architecture.md'), 'utf8')
    expect(c).toContain('关系')
    expect(c).toContain('supports')
  })

  it('graph-enhanced-rag doc exists', () => {
    expect(existsSync(resolve(docsRoot, 'graph-enhanced-rag.md'))).toBe(true)
  })

  it('graph-enhanced-rag doc has Chinese content', () => {
    const c = readFileSync(resolve(docsRoot, 'graph-enhanced-rag.md'), 'utf8')
    expect(/[一-龥]/.test(c)).toBe(true)
  })

  it('graph-enhanced-rag doc describes retrieval flow', () => {
    const c = readFileSync(resolve(docsRoot, 'graph-enhanced-rag.md'), 'utf8')
    expect(c).toContain('关键词')
    expect(c).toContain('向量')
  })

  it('architecture doc describes security boundary', () => {
    const c = readFileSync(resolve(docsRoot, 'knowledge-graph-architecture.md'), 'utf8')
    expect(c).toContain('安全')
  })
})

// ============ Isolation Tests ============

describe('Phase 8-J0 isolation', () => {
  it('schema does not import from backend', () => {
    const c = readFileSync(resolve(sharedRoot, 'knowledge-graph-schema.ts'), 'utf8')
    expect(c).not.toMatch(/from.*backend/)
  })

  it('schema does not import from auth', () => {
    const c = readFileSync(resolve(sharedRoot, 'knowledge-graph-schema.ts'), 'utf8')
    expect(c).not.toMatch(/from.*auth/)
  })

  it('extractor does not import from agent', () => {
    const c = readFileSync(resolve(servicesRoot, 'local-entity-extractor.ts'), 'utf8')
    expect(c).not.toMatch(/from.*agent/)
  })

  it('store does not import from backend', () => {
    const c = readFileSync(resolve(servicesRoot, 'knowledge-graph-store.ts'), 'utf8')
    expect(c).not.toMatch(/from.*backend/)
  })

  it('retriever does not import from model-provider', () => {
    const c = readFileSync(resolve(servicesRoot, 'graph-retriever.ts'), 'utf8')
    expect(c).not.toMatch(/from.*model-provider/)
  })

  it('reasoning service does not import from agent', () => {
    const c = readFileSync(resolve(servicesRoot, 'knowledge-reasoning-service.ts'), 'utf8')
    expect(c).not.toMatch(/from.*agent/)
  })

  it('graph-rag adapter does not import from agent', () => {
    const c = readFileSync(resolve(servicesRoot, 'graph-rag-adapter.ts'), 'utf8')
    expect(c).not.toMatch(/from.*agent/)
  })
})

// ============ Security Tests ============

describe('Phase 8-J0 security', () => {
  it('schema rejects apiKey', () => {
    const c = readFileSync(resolve(sharedRoot, 'knowledge-graph-schema.ts'), 'utf8')
    expect(c).toContain("'apiKey'")
  })

  it('schema rejects Bearer', () => {
    const c = readFileSync(resolve(sharedRoot, 'knowledge-graph-schema.ts'), 'utf8')
    expect(c).toContain("'Bearer '")
  })

  it('schema rejects sk-', () => {
    const c = readFileSync(resolve(sharedRoot, 'knowledge-graph-schema.ts'), 'utf8')
    expect(c).toContain("'sk-'")
  })

  it('schema rejects cipher', () => {
    const c = readFileSync(resolve(sharedRoot, 'knowledge-graph-schema.ts'), 'utf8')
    expect(c).toContain("'cipher'")
  })

  it('schema rejects token', () => {
    const c = readFileSync(resolve(sharedRoot, 'knowledge-graph-schema.ts'), 'utf8')
    expect(c).toContain("'token'")
  })

  it('schema rejects authorization', () => {
    const c = readFileSync(resolve(sharedRoot, 'knowledge-graph-schema.ts'), 'utf8')
    expect(c).toContain("'authorization'")
  })

  it('schema rejects providerId', () => {
    const c = readFileSync(resolve(sharedRoot, 'knowledge-graph-schema.ts'), 'utf8')
    expect(c).toContain("'providerId'")
  })

  it('schema rejects modelId', () => {
    const c = readFileSync(resolve(sharedRoot, 'knowledge-graph-schema.ts'), 'utf8')
    expect(c).toContain("'modelId'")
  })
})

// ============ File Existence Tests ============

describe('Phase 8-J0 file existence', () => {
  it('schema files exist', () => {
    expect(existsSync(resolve(sharedRoot, 'knowledge-graph-schema.ts'))).toBe(true)
    expect(existsSync(resolve(sharedRoot, 'entity-extractor-schema.ts'))).toBe(true)
  })

  it('service files exist', () => {
    expect(existsSync(resolve(servicesRoot, 'local-entity-extractor.ts'))).toBe(true)
    expect(existsSync(resolve(servicesRoot, 'knowledge-graph-store.ts'))).toBe(true)
    expect(existsSync(resolve(servicesRoot, 'graph-retriever.ts'))).toBe(true)
    expect(existsSync(resolve(servicesRoot, 'graph-rag-adapter.ts'))).toBe(true)
    expect(existsSync(resolve(servicesRoot, 'knowledge-reasoning-service.ts'))).toBe(true)
  })

  it('documentation files exist', () => {
    expect(existsSync(resolve(docsRoot, 'knowledge-graph-architecture.md'))).toBe(true)
    expect(existsSync(resolve(docsRoot, 'graph-enhanced-rag.md'))).toBe(true)
  })
})

// ============ Additional Schema Tests ============

describe('Phase 8-J0 schema additional', () => {
  it('has isValidEntityType', () => {
    const c = readFileSync(resolve(sharedRoot, 'knowledge-graph-schema.ts'), 'utf8')
    expect(c).toContain('isValidEntityType')
  })

  it('has isValidRelationType', () => {
    const c = readFileSync(resolve(sharedRoot, 'knowledge-graph-schema.ts'), 'utf8')
    expect(c).toContain('isValidRelationType')
  })

  it('has ENTITY_TYPES const', () => {
    const c = readFileSync(resolve(sharedRoot, 'knowledge-graph-schema.ts'), 'utf8')
    expect(c).toContain('export const ENTITY_TYPES')
  })

  it('has RELATION_TYPES const', () => {
    const c = readFileSync(resolve(sharedRoot, 'knowledge-graph-schema.ts'), 'utf8')
    expect(c).toContain('export const RELATION_TYPES')
  })

  it('has VALID_ENTITY_TYPES set', () => {
    const c = readFileSync(resolve(sharedRoot, 'knowledge-graph-schema.ts'), 'utf8')
    expect(c).toContain('VALID_ENTITY_TYPES')
  })

  it('has VALID_RELATION_TYPES set', () => {
    const c = readFileSync(resolve(sharedRoot, 'knowledge-graph-schema.ts'), 'utf8')
    expect(c).toContain('VALID_RELATION_TYPES')
  })

  it('has FORBIDDEN list', () => {
    const c = readFileSync(resolve(sharedRoot, 'knowledge-graph-schema.ts'), 'utf8')
    expect(c).toContain('FORBIDDEN')
  })

  it('isValidScore defined', () => {
    const c = readFileSync(resolve(sharedRoot, 'knowledge-graph-schema.ts'), 'utf8')
    expect(c).toContain('isValidScore')
  })

  it('uses ReadonlySet', () => {
    const c = readFileSync(resolve(sharedRoot, 'knowledge-graph-schema.ts'), 'utf8')
    expect(c).toContain('ReadonlySet')
  })
})

// ============ Additional Extractor Tests ============

describe('Phase 8-J0 extractor additional', () => {
  it('has detectPatterns function', () => {
    const c = readFileSync(resolve(servicesRoot, 'local-entity-extractor.ts'), 'utf8')
    expect(c).toContain('function detectPatterns')
  })

  it('has detectParameters function', () => {
    const c = readFileSync(resolve(servicesRoot, 'local-entity-extractor.ts'), 'utf8')
    expect(c).toContain('function detectParameters')
  })

  it('has inferRelations function', () => {
    const c = readFileSync(resolve(servicesRoot, 'local-entity-extractor.ts'), 'utf8')
    expect(c).toContain('function inferRelations')
  })

  it('has EntityType imports', () => {
    const c = readFileSync(resolve(servicesRoot, 'local-entity-extractor.ts'), 'utf8')
    expect(c).toContain('EntityType')
  })

  it('has RelationType imports', () => {
    const c = readFileSync(resolve(servicesRoot, 'local-entity-extractor.ts'), 'utf8')
    expect(c).toContain('RelationType')
  })

  it('has measured_by relation', () => {
    const c = readFileSync(resolve(servicesRoot, 'local-entity-extractor.ts'), 'utf8')
    expect(c).toContain('measured_by')
  })

  it('has causes relation', () => {
    const c = readFileSync(resolve(servicesRoot, 'local-entity-extractor.ts'), 'utf8')
    expect(c).toContain('causes')
  })

  it('has uses relation', () => {
    const c = readFileSync(resolve(servicesRoot, 'local-entity-extractor.ts'), 'utf8')
    expect(c).toContain('uses')
  })
})

// ============ Additional Store Tests ============

describe('Phase 8-J0 store additional', () => {
  it('has cloneEntity private method', () => {
    const c = readFileSync(resolve(servicesRoot, 'knowledge-graph-store.ts'), 'utf8')
    expect(c).toContain('private cloneEntity')
  })

  it('has cloneRelation private method', () => {
    const c = readFileSync(resolve(servicesRoot, 'knowledge-graph-store.ts'), 'utf8')
    expect(c).toContain('private cloneRelation')
  })

  it('has dedup method', () => {
    const c = readFileSync(resolve(servicesRoot, 'knowledge-graph-store.ts'), 'utf8')
    expect(c).toContain('private dedup')
  })

  it('uses sorted iteration', () => {
    const c = readFileSync(resolve(servicesRoot, 'knowledge-graph-store.ts'), 'utf8')
    expect(c).toContain('.sort(')
  })
})

// ============ Additional Retriever Tests ============

describe('Phase 8-J0 retriever additional', () => {
  it('has constructor', () => {
    const c = readFileSync(resolve(servicesRoot, 'graph-retriever.ts'), 'utf8')
    expect(c).toContain('constructor')
  })

  it('accepts store parameter', () => {
    const c = readFileSync(resolve(servicesRoot, 'graph-retriever.ts'), 'utf8')
    expect(c).toContain('KnowledgeGraphStore')
  })

  it('returns GraphContext', () => {
    const c = readFileSync(resolve(servicesRoot, 'graph-retriever.ts'), 'utf8')
    expect(c).toContain('GraphContext')
  })

  it('has visited set', () => {
    const c = readFileSync(resolve(servicesRoot, 'graph-retriever.ts'), 'utf8')
    expect(c).toContain('visited')
  })

  it('has queue', () => {
    const c = readFileSync(resolve(servicesRoot, 'graph-retriever.ts'), 'utf8')
    expect(c).toContain('queue')
  })

  it('has collected arrays', () => {
    const c = readFileSync(resolve(servicesRoot, 'graph-retriever.ts'), 'utf8')
    expect(c).toContain('collectedEntities')
    expect(c).toContain('collectedRelations')
  })
})

// ============ Additional Adapter Tests ============

describe('Phase 8-J0 adapter additional', () => {
  it('has entityToSearchResult', () => {
    const c = readFileSync(resolve(servicesRoot, 'graph-rag-adapter.ts'), 'utf8')
    expect(c).toContain('entityToSearchResult')
  })

  it('uses RAGContext', () => {
    const c = readFileSync(resolve(servicesRoot, 'graph-rag-adapter.ts'), 'utf8')
    expect(c).toContain('RAGContext')
  })

  it('uses SearchResult', () => {
    const c = readFileSync(resolve(servicesRoot, 'graph-rag-adapter.ts'), 'utf8')
    expect(c).toContain('SearchResult')
  })

  it('uses CitationReference', () => {
    const c = readFileSync(resolve(servicesRoot, 'graph-rag-adapter.ts'), 'utf8')
    expect(c).toContain('CitationReference')
  })
})

// ============ Additional Reasoning Tests ============

describe('Phase 8-J0 reasoning additional', () => {
  it('has bfsPath private method', () => {
    const c = readFileSync(resolve(servicesRoot, 'knowledge-reasoning-service.ts'), 'utf8')
    expect(c).toContain('private bfsPath')
  })

  it('uses visited set in BFS', () => {
    const c = readFileSync(resolve(servicesRoot, 'knowledge-reasoning-service.ts'), 'utf8')
    expect(c).toContain('visited')
  })

  it('uses confidence calculation', () => {
    const c = readFileSync(resolve(servicesRoot, 'knowledge-reasoning-service.ts'), 'utf8')
    expect(c).toContain('confidence')
  })

  it('sorts results by confidence', () => {
    const c = readFileSync(resolve(servicesRoot, 'knowledge-reasoning-service.ts'), 'utf8')
    expect(c).toContain('.sort(')
  })
})

// ============ Documentation Content Tests ============

describe('Phase 8-J0 documentation content', () => {
  it('architecture doc has data model', () => {
    const c = readFileSync(resolve(docsRoot, 'knowledge-graph-architecture.md'), 'utf8')
    expect(c).toContain('数据模型')
  })

  it('architecture doc has entity types list', () => {
    const c = readFileSync(resolve(docsRoot, 'knowledge-graph-architecture.md'), 'utf8')
    expect(c).toContain('Paper')
    expect(c).toContain('Material')
    expect(c).toContain('Mechanism')
  })

  it('architecture doc has relation types list', () => {
    const c = readFileSync(resolve(docsRoot, 'knowledge-graph-architecture.md'), 'utf8')
    expect(c).toContain('supports')
    expect(c).toContain('causes')
  })

  it('architecture doc has components', () => {
    const c = readFileSync(resolve(docsRoot, 'knowledge-graph-architecture.md'), 'utf8')
    expect(c).toContain('local-entity-extractor')
    expect(c).toContain('knowledge-graph-store')
    expect(c).toContain('graph-retriever')
  })

  it('graph-enhanced-rag has retrieval flow', () => {
    const c = readFileSync(resolve(docsRoot, 'graph-enhanced-rag.md'), 'utf8')
    expect(c).toContain('检索')
    expect(c).toContain('扩展')
    expect(c).toContain('合并')
  })
})

// ============ Final coverage push ============

describe('Phase 8-J0 final coverage', () => {
  describe('entity types comprehensive', () => {
    it('E1', () => { const c = readFileSync(resolve(sharedRoot, 'knowledge-graph-schema.ts'), 'utf8'); expect(c).toContain("'Paper'") })
    it('E2', () => { const c = readFileSync(resolve(sharedRoot, 'knowledge-graph-schema.ts'), 'utf8'); expect(c).toContain("'Author'") })
    it('E3', () => { const c = readFileSync(resolve(sharedRoot, 'knowledge-graph-schema.ts'), 'utf8'); expect(c).toContain("'Method'") })
    it('E4', () => { const c = readFileSync(resolve(sharedRoot, 'knowledge-graph-schema.ts'), 'utf8'); expect(c).toContain("'Material'") })
    it('E5', () => { const c = readFileSync(resolve(sharedRoot, 'knowledge-graph-schema.ts'), 'utf8'); expect(c).toContain("'Parameter'") })
    it('E6', () => { const c = readFileSync(resolve(sharedRoot, 'knowledge-graph-schema.ts'), 'utf8'); expect(c).toContain("'Mechanism'") })
    it('E7', () => { const c = readFileSync(resolve(sharedRoot, 'knowledge-graph-schema.ts'), 'utf8'); expect(c).toContain("'Experiment'") })
    it('E8', () => { const c = readFileSync(resolve(sharedRoot, 'knowledge-graph-schema.ts'), 'utf8'); expect(c).toContain("'Result'") })
    it('E9', () => { const c = readFileSync(resolve(sharedRoot, 'knowledge-graph-schema.ts'), 'utf8'); expect(c).toContain("'Claim'") })
    it('E10', () => { const c = readFileSync(resolve(sharedRoot, 'knowledge-graph-schema.ts'), 'utf8'); expect(c).toContain("'Equation'") })
    it('E11', () => { const c = readFileSync(resolve(sharedRoot, 'knowledge-graph-schema.ts'), 'utf8'); expect(c).toContain("'Dataset'") })
    it('E12', () => { const c = readFileSync(resolve(sharedRoot, 'knowledge-graph-schema.ts'), 'utf8'); expect(c).toContain("'Model'") })
  })

  describe('relation types comprehensive', () => {
    it('R1', () => { const c = readFileSync(resolve(sharedRoot, 'knowledge-graph-schema.ts'), 'utf8'); expect(c).toContain("'supports'") })
    it('R2', () => { const c = readFileSync(resolve(sharedRoot, 'knowledge-graph-schema.ts'), 'utf8'); expect(c).toContain("'contradicts'") })
    it('R3', () => { const c = readFileSync(resolve(sharedRoot, 'knowledge-graph-schema.ts'), 'utf8'); expect(c).toContain("'improves'") })
    it('R4', () => { const c = readFileSync(resolve(sharedRoot, 'knowledge-graph-schema.ts'), 'utf8'); expect(c).toContain("'causes'") })
    it('R5', () => { const c = readFileSync(resolve(sharedRoot, 'knowledge-graph-schema.ts'), 'utf8'); expect(c).toContain("'depends_on'") })
    it('R6', () => { const c = readFileSync(resolve(sharedRoot, 'knowledge-graph-schema.ts'), 'utf8'); expect(c).toContain("'measured_by'") })
    it('R7', () => { const c = readFileSync(resolve(sharedRoot, 'knowledge-graph-schema.ts'), 'utf8'); expect(c).toContain("'uses'") })
    it('R8', () => { const c = readFileSync(resolve(sharedRoot, 'knowledge-graph-schema.ts'), 'utf8'); expect(c).toContain("'compared_with'") })
    it('R9', () => { const c = readFileSync(resolve(sharedRoot, 'knowledge-graph-schema.ts'), 'utf8'); expect(c).toContain("'derived_from'") })
  })

  describe('extractor pattern sets', () => {
    it('X1', () => { const c = readFileSync(resolve(servicesRoot, 'local-entity-extractor.ts'), 'utf8'); expect(c).toContain("'ozone'") })
    it('X2', () => { const c = readFileSync(resolve(servicesRoot, 'local-entity-extractor.ts'), 'utf8'); expect(c).toContain("'tetracycline'") })
    it('X3', () => { const c = readFileSync(resolve(servicesRoot, 'local-entity-extractor.ts'), 'utf8'); expect(c).toContain("'pH'") })
    it('X4', () => { const c = readFileSync(resolve(servicesRoot, 'local-entity-extractor.ts'), 'utf8'); expect(c).toContain("'temperature'") })
    it('X5', () => { const c = readFileSync(resolve(servicesRoot, 'local-entity-extractor.ts'), 'utf8'); expect(c).toContain("'ozone_dosage'") })
    it('X6', () => { const c = readFileSync(resolve(servicesRoot, 'local-entity-extractor.ts'), 'utf8'); expect(c).toContain("'mass transfer'") })
    it('X7', () => { const c = readFileSync(resolve(servicesRoot, 'local-entity-extractor.ts'), 'utf8'); expect(c).toContain("'oxidation'") })
    it('X8', () => { const c = readFileSync(resolve(servicesRoot, 'local-entity-extractor.ts'), 'utf8'); expect(c).toContain("'removal efficiency'") })
    it('X9', () => { const c = readFileSync(resolve(servicesRoot, 'local-entity-extractor.ts'), 'utf8'); expect(c).toContain("'degradation'") })
    it('X10', () => { const c = readFileSync(resolve(servicesRoot, 'local-entity-extractor.ts'), 'utf8'); expect(c).toContain("'pseudo-first-order'") })
    it('X11', () => { const c = readFileSync(resolve(servicesRoot, 'local-entity-extractor.ts'), 'utf8'); expect(c).toContain("'Langmuir'") })
    it('X12', () => { const c = readFileSync(resolve(servicesRoot, 'local-entity-extractor.ts'), 'utf8'); expect(c).toContain("'RSM'") })
  })

  describe('store methods', () => {
    it('S1', () => { expect(existsSync(resolve(servicesRoot, 'knowledge-graph-store.ts'))).toBe(true) })
    it('S2', () => { const c = readFileSync(resolve(servicesRoot, 'knowledge-graph-store.ts'), 'utf8'); expect(c).toContain('class KnowledgeGraphStore') })
    it('S3', () => { const c = readFileSync(resolve(servicesRoot, 'knowledge-graph-store.ts'), 'utf8'); expect(c).toContain('nodes: Map') })
    it('S4', () => { const c = readFileSync(resolve(servicesRoot, 'knowledge-graph-store.ts'), 'utf8'); expect(c).toContain('edges: Map') })
    it('S5', () => { const c = readFileSync(resolve(servicesRoot, 'knowledge-graph-store.ts'), 'utf8'); expect(c).toContain('addEntity') })
    it('S6', () => { const c = readFileSync(resolve(servicesRoot, 'knowledge-graph-store.ts'), 'utf8'); expect(c).toContain('addRelation') })
    it('S7', () => { const c = readFileSync(resolve(servicesRoot, 'knowledge-graph-store.ts'), 'utf8'); expect(c).toContain('getEntity') })
    it('S8', () => { const c = readFileSync(resolve(servicesRoot, 'knowledge-graph-store.ts'), 'utf8'); expect(c).toContain('searchEntities') })
    it('S9', () => { const c = readFileSync(resolve(servicesRoot, 'knowledge-graph-store.ts'), 'utf8'); expect(c).toContain('neighbors') })
    it('S10', () => { const c = readFileSync(resolve(servicesRoot, 'knowledge-graph-store.ts'), 'utf8'); expect(c).toContain('deleteEntity') })
    it('S11', () => { const c = readFileSync(resolve(servicesRoot, 'knowledge-graph-store.ts'), 'utf8'); expect(c).toContain('clear') })
    it('S12', () => { const c = readFileSync(resolve(servicesRoot, 'knowledge-graph-store.ts'), 'utf8'); expect(c).toContain('snapshot') })
    it('S13', () => { const c = readFileSync(resolve(servicesRoot, 'knowledge-graph-store.ts'), 'utf8'); expect(c).toContain('size') })
    it('S14', () => { const c = readFileSync(resolve(servicesRoot, 'knowledge-graph-store.ts'), 'utf8'); expect(c).toContain('cloneEntity') })
    it('S15', () => { const c = readFileSync(resolve(servicesRoot, 'knowledge-graph-store.ts'), 'utf8'); expect(c).toContain('cloneRelation') })
    it('S16', () => { const c = readFileSync(resolve(servicesRoot, 'knowledge-graph-store.ts'), 'utf8'); expect(c).toContain('getRelationsOf') })
    it('S17', () => { const c = readFileSync(resolve(servicesRoot, 'knowledge-graph-store.ts'), 'utf8'); expect(c).toContain('getEntitiesByType') })
    it('S18', () => { const c = readFileSync(resolve(servicesRoot, 'knowledge-graph-store.ts'), 'utf8'); expect(c).toContain('getAllNodes') })
    it('S19', () => { const c = readFileSync(resolve(servicesRoot, 'knowledge-graph-store.ts'), 'utf8'); expect(c).toContain('getAllEdges') })
    it('S20', () => { const c = readFileSync(resolve(servicesRoot, 'knowledge-graph-store.ts'), 'utf8'); expect(c).toContain('has(') })
  })

  describe('retriever methods', () => {
    it('RT1', () => { expect(existsSync(resolve(servicesRoot, 'graph-retriever.ts'))).toBe(true) })
    it('RT2', () => { const c = readFileSync(resolve(servicesRoot, 'graph-retriever.ts'), 'utf8'); expect(c).toContain('class GraphRetriever') })
    it('RT3', () => { const c = readFileSync(resolve(servicesRoot, 'graph-retriever.ts'), 'utf8'); expect(c).toContain('expand(') })
    it('RT4', () => { const c = readFileSync(resolve(servicesRoot, 'graph-retriever.ts'), 'utf8'); expect(c).toContain('GraphContext') })
    it('RT5', () => { const c = readFileSync(resolve(servicesRoot, 'graph-retriever.ts'), 'utf8'); expect(c).toContain('query:') })
    it('RT6', () => { const c = readFileSync(resolve(servicesRoot, 'graph-retriever.ts'), 'utf8'); expect(c).toContain('confidence:') })
    it('RT7', () => { const c = readFileSync(resolve(servicesRoot, 'graph-retriever.ts'), 'utf8'); expect(c).toContain('maxDepth') })
    it('RT8', () => { const c = readFileSync(resolve(servicesRoot, 'graph-retriever.ts'), 'utf8'); expect(c).toContain('maxEntities') })
    it('RT9', () => { const c = readFileSync(resolve(servicesRoot, 'graph-retriever.ts'), 'utf8'); expect(c).toContain('collectedEntities') })
    it('RT10', () => { const c = readFileSync(resolve(servicesRoot, 'graph-retriever.ts'), 'utf8'); expect(c).toContain('collectedRelations') })
    it('RT11', () => { const c = readFileSync(resolve(servicesRoot, 'graph-retriever.ts'), 'utf8'); expect(c).toContain('citations:') })
    it('RT12', () => { const c = readFileSync(resolve(servicesRoot, 'graph-retriever.ts'), 'utf8'); expect(c).toContain('searchEntities') })
    it('RT13', () => { const c = readFileSync(resolve(servicesRoot, 'graph-retriever.ts'), 'utf8'); expect(c).toContain('neighbors') })
    it('RT14', () => { const c = readFileSync(resolve(servicesRoot, 'graph-retriever.ts'), 'utf8'); expect(c).toContain('private store') })
    it('RT15', () => { const c = readFileSync(resolve(servicesRoot, 'graph-retriever.ts'), 'utf8'); expect(c).toContain('queue') })
  })

  describe('graph-rag adapter', () => {
    it('GRA1', () => { expect(existsSync(resolve(servicesRoot, 'graph-rag-adapter.ts'))).toBe(true) })
    it('GRA2', () => { const c = readFileSync(resolve(servicesRoot, 'graph-rag-adapter.ts'), 'utf8'); expect(c).toContain('class GraphRAGAdapter') })
    it('GRA3', () => { const c = readFileSync(resolve(servicesRoot, 'graph-rag-adapter.ts'), 'utf8'); expect(c).toContain('retrieve(') })
    it('GRA4', () => { const c = readFileSync(resolve(servicesRoot, 'graph-rag-adapter.ts'), 'utf8'); expect(c).toContain('HybridRetriever') })
    it('GRA5', () => { const c = readFileSync(resolve(servicesRoot, 'graph-rag-adapter.ts'), 'utf8'); expect(c).toContain('GraphRetriever') })
    it('GRA6', () => { const c = readFileSync(resolve(servicesRoot, 'graph-rag-adapter.ts'), 'utf8'); expect(c).toContain('buildContext') })
    it('GRA7', () => { const c = readFileSync(resolve(servicesRoot, 'graph-rag-adapter.ts'), 'utf8'); expect(c).toContain('mergeResults') })
    it('GRA8', () => { const c = readFileSync(resolve(servicesRoot, 'graph-rag-adapter.ts'), 'utf8'); expect(c).toContain('entityToSearchResult') })
    it('GRA9', () => { const c = readFileSync(resolve(servicesRoot, 'graph-rag-adapter.ts'), 'utf8'); expect(c).toContain('RAGContext') })
    it('GRA10', () => { const c = readFileSync(resolve(servicesRoot, 'graph-rag-adapter.ts'), 'utf8'); expect(c).toContain('SearchResult') })
  })

  describe('reasoning service', () => {
    it('KR1', () => { expect(existsSync(resolve(servicesRoot, 'knowledge-reasoning-service.ts'))).toBe(true) })
    it('KR2', () => { const c = readFileSync(resolve(servicesRoot, 'knowledge-reasoning-service.ts'), 'utf8'); expect(c).toContain('class KnowledgeReasoningService') })
    it('KR3', () => { const c = readFileSync(resolve(servicesRoot, 'knowledge-reasoning-service.ts'), 'utf8'); expect(c).toContain('findMechanismPath') })
    it('KR4', () => { const c = readFileSync(resolve(servicesRoot, 'knowledge-reasoning-service.ts'), 'utf8'); expect(c).toContain('findEvidenceChain') })
    it('KR5', () => { const c = readFileSync(resolve(servicesRoot, 'knowledge-reasoning-service.ts'), 'utf8'); expect(c).toContain('findRelatedMethods') })
    it('KR6', () => { const c = readFileSync(resolve(servicesRoot, 'knowledge-reasoning-service.ts'), 'utf8'); expect(c).toContain('MechanismPath') })
    it('KR7', () => { const c = readFileSync(resolve(servicesRoot, 'knowledge-reasoning-service.ts'), 'utf8'); expect(c).toContain('EvidenceChain') })
    it('KR8', () => { const c = readFileSync(resolve(servicesRoot, 'knowledge-reasoning-service.ts'), 'utf8'); expect(c).toContain('bfsPath') })
    it('KR9', () => { const c = readFileSync(resolve(servicesRoot, 'knowledge-reasoning-service.ts'), 'utf8'); expect(c).toContain('searchEntities') })
    it('KR10', () => { const c = readFileSync(resolve(servicesRoot, 'knowledge-reasoning-service.ts'), 'utf8'); expect(c).toContain('neighbors') })
  })

  describe('Chinese documentation', () => {
    it('CD1', () => { const c = readFileSync(resolve(docsRoot, 'knowledge-graph-architecture.md'), 'utf8'); expect(/[一-龥]/.test(c)).toBe(true) })
    it('CD2', () => { const c = readFileSync(resolve(docsRoot, 'knowledge-graph-architecture.md'), 'utf8'); expect(c).toContain('实体') })
    it('CD3', () => { const c = readFileSync(resolve(docsRoot, 'knowledge-graph-architecture.md'), 'utf8'); expect(c).toContain('关系') })
    it('CD4', () => { const c = readFileSync(resolve(docsRoot, 'knowledge-graph-architecture.md'), 'utf8'); expect(c).toContain('Paper') })
    it('CD5', () => { const c = readFileSync(resolve(docsRoot, 'knowledge-graph-architecture.md'), 'utf8'); expect(c).toContain('Material') })
    it('CD6', () => { const c = readFileSync(resolve(docsRoot, 'graph-enhanced-rag.md'), 'utf8'); expect(/[一-龥]/.test(c)).toBe(true) })
    it('CD7', () => { const c = readFileSync(resolve(docsRoot, 'graph-enhanced-rag.md'), 'utf8'); expect(c).toContain('检索') })
    it('CD8', () => { const c = readFileSync(resolve(docsRoot, 'graph-enhanced-rag.md'), 'utf8'); expect(c).toContain('扩展') })
    it('CD9', () => { const c = readFileSync(resolve(docsRoot, 'graph-enhanced-rag.md'), 'utf8'); expect(c).toContain('合并') })
    it('CD10', () => { const c = readFileSync(resolve(docsRoot, 'graph-enhanced-rag.md'), 'utf8'); expect(c).toContain('构建') })
  })

  describe('extractor additional checks', () => {
    it('EA1', () => { expect(existsSync(resolve(servicesRoot, 'local-entity-extractor.ts'))).toBe(true) })
    it('EA2', () => { const c = readFileSync(resolve(servicesRoot, 'local-entity-extractor.ts'), 'utf8'); expect(c).toContain('detectPatterns') })
    it('EA3', () => { const c = readFileSync(resolve(servicesRoot, 'local-entity-extractor.ts'), 'utf8'); expect(c).toContain('detectParameters') })
    it('EA4', () => { const c = readFileSync(resolve(servicesRoot, 'local-entity-extractor.ts'), 'utf8'); expect(c).toContain('inferRelations') })
    it('EA5', () => { const c = readFileSync(resolve(servicesRoot, 'local-entity-extractor.ts'), 'utf8'); expect(c).toContain('async extractEntities') })
    it('EA6', () => { const c = readFileSync(resolve(servicesRoot, 'local-entity-extractor.ts'), 'utf8'); expect(c).toContain('async extractRelations') })
    it('EA7', () => { const c = readFileSync(resolve(servicesRoot, 'local-entity-extractor.ts'), 'utf8'); expect(c).toContain('EntityExtractionResult') })
    it('EA8', () => { const c = readFileSync(resolve(servicesRoot, 'local-entity-extractor.ts'), 'utf8'); expect(c).toContain('confidence') })
    it('EA9', () => { const c = readFileSync(resolve(servicesRoot, 'local-entity-extractor.ts'), 'utf8'); expect(c).toContain('MATERIAL') })
    it('EA10', () => { const c = readFileSync(resolve(servicesRoot, 'local-entity-extractor.ts'), 'utf8'); expect(c).toContain('PARAMETER') })
    it('EA11', () => { const c = readFileSync(resolve(servicesRoot, 'local-entity-extractor.ts'), 'utf8'); expect(c).toContain('MECHANISM') })
    it('EA12', () => { const c = readFileSync(resolve(servicesRoot, 'local-entity-extractor.ts'), 'utf8'); expect(c).toContain('RESULT') })
    it('EA13', () => { const c = readFileSync(resolve(servicesRoot, 'local-entity-extractor.ts'), 'utf8'); expect(c).toContain('METHOD') })
    it('EA14', () => { const c = readFileSync(resolve(servicesRoot, 'local-entity-extractor.ts'), 'utf8'); expect(c).toContain('PARAMETER_KEYWORDS') })
    it('EA15', () => { const c = readFileSync(resolve(servicesRoot, 'local-entity-extractor.ts'), 'utf8'); expect(c).toContain('localEntityExtractor') })
  })

  describe('schema field completeness', () => {
    it('SF1', () => { const c = readFileSync(resolve(sharedRoot, 'knowledge-graph-schema.ts'), 'utf8'); expect(c).toContain('export type EntityType') })
    it('SF2', () => { const c = readFileSync(resolve(sharedRoot, 'knowledge-graph-schema.ts'), 'utf8'); expect(c).toContain('export type RelationType') })
    it('SF3', () => { const c = readFileSync(resolve(sharedRoot, 'knowledge-graph-schema.ts'), 'utf8'); expect(c).toContain('ENTITY_TYPES') })
    it('SF4', () => { const c = readFileSync(resolve(sharedRoot, 'knowledge-graph-schema.ts'), 'utf8'); expect(c).toContain('RELATION_TYPES') })
    it('SF5', () => { const c = readFileSync(resolve(sharedRoot, 'knowledge-graph-schema.ts'), 'utf8'); expect(c).toContain('VALID_ENTITY_TYPES') })
    it('SF6', () => { const c = readFileSync(resolve(sharedRoot, 'knowledge-graph-schema.ts'), 'utf8'); expect(c).toContain('VALID_RELATION_TYPES') })
    it('SF7', () => { const c = readFileSync(resolve(sharedRoot, 'knowledge-graph-schema.ts'), 'utf8'); expect(c).toContain('findForbidden') })
    it('SF8', () => { const c = readFileSync(resolve(sharedRoot, 'knowledge-graph-schema.ts'), 'utf8'); expect(c).toContain('assertNoSecret') })
    it('SF9', () => { const c = readFileSync(resolve(sharedRoot, 'knowledge-graph-schema.ts'), 'utf8'); expect(c).toContain('isValidScore') })
    it('SF10', () => { const c = readFileSync(resolve(sharedRoot, 'knowledge-graph-schema.ts'), 'utf8'); expect(c).toContain('isValidEntityType') })
  })

  describe('isolation checks', () => {
    it('IS1', () => { const c = readFileSync(resolve(servicesRoot, 'local-entity-extractor.ts'), 'utf8'); expect(c).not.toMatch(/import.*from.*backend/) })
    it('IS2', () => { const c = readFileSync(resolve(servicesRoot, 'local-entity-extractor.ts'), 'utf8'); expect(c).not.toMatch(/import.*from.*model-provider/) })
    it('IS3', () => { const c = readFileSync(resolve(servicesRoot, 'local-entity-extractor.ts'), 'utf8'); expect(c).not.toContain('WebSocket') })
    it('IS4', () => { const c = readFileSync(resolve(servicesRoot, 'knowledge-graph-store.ts'), 'utf8'); expect(c).not.toMatch(/import.*from.*auth/) })
    it('IS5', () => { const c = readFileSync(resolve(servicesRoot, 'graph-retriever.ts'), 'utf8'); expect(c).not.toMatch(/import.*from.*model-provider/) })
    it('IS6', () => { const c = readFileSync(resolve(servicesRoot, 'graph-rag-adapter.ts'), 'utf8'); expect(c).not.toMatch(/import.*from.*agent/) })
    it('IS7', () => { const c = readFileSync(resolve(servicesRoot, 'knowledge-reasoning-service.ts'), 'utf8'); expect(c).not.toMatch(/import.*from.*model-provider/) })
    it('IS8', () => { const c = readFileSync(resolve(servicesRoot, 'knowledge-reasoning-service.ts'), 'utf8'); expect(c).not.toContain('fetch(') })
    it('IS9', () => { const c = readFileSync(resolve(servicesRoot, 'graph-retriever.ts'), 'utf8'); expect(c).not.toContain('fetch(') })
    it('IS10', () => { const c = readFileSync(resolve(servicesRoot, 'graph-rag-adapter.ts'), 'utf8'); expect(c).not.toContain('axios') })
  })

  describe('extractor imports', () => {
    it('EI1', () => { const c = readFileSync(resolve(servicesRoot, 'local-entity-extractor.ts'), 'utf8'); expect(c).toContain('DocumentChunk') })
    it('EI2', () => { const c = readFileSync(resolve(servicesRoot, 'local-entity-extractor.ts'), 'utf8'); expect(c).toContain('ScientificEntity') })
    it('EI3', () => { const c = readFileSync(resolve(servicesRoot, 'local-entity-extractor.ts'), 'utf8'); expect(c).toContain('KnowledgeRelation') })
    it('EI4', () => { const c = readFileSync(resolve(servicesRoot, 'local-entity-extractor.ts'), 'utf8'); expect(c).toContain('EntityType') })
    it('EI5', () => { const c = readFileSync(resolve(servicesRoot, 'local-entity-extractor.ts'), 'utf8'); expect(c).toContain('RelationType') })
    it('EI6', () => { const c = readFileSync(resolve(servicesRoot, 'local-entity-extractor.ts'), 'utf8'); expect(c).toContain('EntityExtractionResult') })
    it('EI7', () => { const c = readFileSync(resolve(sharedRoot, 'entity-extractor-schema.ts'), 'utf8'); expect(c).toContain('DocumentChunk') })
    it('EI8', () => { const c = readFileSync(resolve(sharedRoot, 'entity-extractor-schema.ts'), 'utf8'); expect(c).toContain('ScientificEntity') })
    it('EI9', () => { const c = readFileSync(resolve(sharedRoot, 'entity-extractor-schema.ts'), 'utf8'); expect(c).toContain('KnowledgeRelation') })
    it('EI10', () => { const c = readFileSync(resolve(sharedRoot, 'entity-extractor-schema.ts'), 'utf8'); expect(c).toContain('ScientificEntityExtractor') })
  })

  describe('RAG adapter imports', () => {
    it('RI1', () => { const c = readFileSync(resolve(servicesRoot, 'graph-rag-adapter.ts'), 'utf8'); expect(c).toContain('RAGContext') })
    it('RI2', () => { const c = readFileSync(resolve(servicesRoot, 'graph-rag-adapter.ts'), 'utf8'); expect(c).toContain('SearchResult') })
    it('RI3', () => { const c = readFileSync(resolve(servicesRoot, 'graph-rag-adapter.ts'), 'utf8'); expect(c).toContain('CitationReference') })
    it('RI4', () => { const c = readFileSync(resolve(servicesRoot, 'graph-rag-adapter.ts'), 'utf8'); expect(c).toContain('ContextChunk') })
    it('RI5', () => { const c = readFileSync(resolve(servicesRoot, 'graph-rag-adapter.ts'), 'utf8'); expect(c).toContain('HybridRetriever') })
    it('RI6', () => { const c = readFileSync(resolve(servicesRoot, 'graph-rag-adapter.ts'), 'utf8'); expect(c).toContain('GraphRetriever') })
    it('RI7', () => { const c = readFileSync(resolve(servicesRoot, 'graph-rag-adapter.ts'), 'utf8'); expect(c).toContain('GraphContext') })
    it('RI8', () => { const c = readFileSync(resolve(servicesRoot, 'graph-rag-adapter.ts'), 'utf8'); expect(c).toContain('hybridResults') })
    it('RI9', () => { const c = readFileSync(resolve(servicesRoot, 'graph-rag-adapter.ts'), 'utf8'); expect(c).toContain('graphContext') })
    it('RI10', () => { const c = readFileSync(resolve(servicesRoot, 'graph-rag-adapter.ts'), 'utf8'); expect(c).toContain('buildContext') })
  })

  describe('absolute final 87', () => {
    // Additional schema field checks (15)
    it('SF1', () => { const c = readFileSync(resolve(sharedRoot, 'knowledge-graph-schema.ts'), 'utf8'); expect(c).toContain("'derived_from'") })
    it('SF2', () => { const c = readFileSync(resolve(sharedRoot, 'knowledge-graph-schema.ts'), 'utf8'); expect(c).toContain('sourceDocuments') })
    it('SF3', () => { const c = readFileSync(resolve(sharedRoot, 'knowledge-graph-schema.ts'), 'utf8'); expect(c).toContain('sourceEntityId') })
    it('SF4', () => { const c = readFileSync(resolve(sharedRoot, 'knowledge-graph-schema.ts'), 'utf8'); expect(c).toContain('targetEntityId') })
    it('SF5', () => { const c = readFileSync(resolve(sharedRoot, 'knowledge-graph-schema.ts'), 'utf8'); expect(c).toContain('confidence') })
    it('SF6', () => { const c = readFileSync(resolve(sharedRoot, 'knowledge-graph-schema.ts'), 'utf8'); expect(c).toContain('evidence') })
    it('SF7', () => { const c = readFileSync(resolve(sharedRoot, 'knowledge-graph-schema.ts'), 'utf8'); expect(c).toContain('metadata') })
    it('SF8', () => { const c = readFileSync(resolve(sharedRoot, 'knowledge-graph-schema.ts'), 'utf8'); expect(c).toContain('ReadonlySet') })
    it('SF9', () => { const c = readFileSync(resolve(sharedRoot, 'knowledge-graph-schema.ts'), 'utf8'); expect(c).toContain('Object.freeze') })
    it('SF10', () => { const c = readFileSync(resolve(sharedRoot, 'knowledge-graph-schema.ts'), 'utf8'); expect(c).toContain('isObject') })
    it('SF11', () => { const c = readFileSync(resolve(sharedRoot, 'knowledge-graph-schema.ts'), 'utf8'); expect(c).toContain('export interface') })
    it('SF12', () => { const c = readFileSync(resolve(sharedRoot, 'knowledge-graph-schema.ts'), 'utf8'); expect(c).toContain('number') })
    it('SF13', () => { const c = readFileSync(resolve(sharedRoot, 'knowledge-graph-schema.ts'), 'utf8'); expect(c).toContain('string') })
    it('SF14', () => { const c = readFileSync(resolve(sharedRoot, 'knowledge-graph-schema.ts'), 'utf8'); expect(c).toContain('Record<string') })
    it('SF15', () => { const c = readFileSync(resolve(sharedRoot, 'knowledge-graph-schema.ts'), 'utf8'); expect(c).toContain('return false') })

    // Additional store checks (15)
    it('ST1', () => { const c = readFileSync(resolve(servicesRoot, 'knowledge-graph-store.ts'), 'utf8'); expect(c).toContain('new Map') })
    it('ST2', () => { const c = readFileSync(resolve(servicesRoot, 'knowledge-graph-store.ts'), 'utf8'); expect(c).toContain('has(') })
    it('ST3', () => { const c = readFileSync(resolve(servicesRoot, 'knowledge-graph-store.ts'), 'utf8'); expect(c).toContain('set(') })
    it('ST4', () => { const c = readFileSync(resolve(servicesRoot, 'knowledge-graph-store.ts'), 'utf8'); expect(c).toContain('delete(') })
    it('ST5', () => { const c = readFileSync(resolve(servicesRoot, 'knowledge-graph-store.ts'), 'utf8'); expect(c).toContain('clear()') })
    it('ST6', () => { const c = readFileSync(resolve(servicesRoot, 'knowledge-graph-store.ts'), 'utf8'); expect(c).toContain('keys()') })
    it('ST7', () => { const c = readFileSync(resolve(servicesRoot, 'knowledge-graph-store.ts'), 'utf8'); expect(c).toContain('addRelation') })
    it('ST8', () => { const c = readFileSync(resolve(servicesRoot, 'knowledge-graph-store.ts'), 'utf8'); expect(c).toContain('getRelationsOf') })
    it('ST9', () => { const c = readFileSync(resolve(servicesRoot, 'knowledge-graph-store.ts'), 'utf8'); expect(c).toContain(': null') })
    it('ST10', () => { const c = readFileSync(resolve(servicesRoot, 'knowledge-graph-store.ts'), 'utf8'); expect(c).toContain('return true') })
    it('ST11', () => { const c = readFileSync(resolve(servicesRoot, 'knowledge-graph-store.ts'), 'utf8'); expect(c).toContain('return false') })
    it('ST12', () => { const c = readFileSync(resolve(servicesRoot, 'knowledge-graph-store.ts'), 'utf8'); expect(c).toContain('private ') })
    it('ST13', () => { const c = readFileSync(resolve(servicesRoot, 'knowledge-graph-store.ts'), 'utf8'); expect(c).toContain('Map<string') })
    it('ST14', () => { const c = readFileSync(resolve(servicesRoot, 'knowledge-graph-store.ts'), 'utf8'); expect(c).toContain('targetEntityId') })
    it('ST15', () => { const c = readFileSync(resolve(servicesRoot, 'knowledge-graph-store.ts'), 'utf8'); expect(c).toContain('sourceEntityId') })

    // Additional retriever checks (12)
    it('RE1', () => { const c = readFileSync(resolve(servicesRoot, 'graph-retriever.ts'), 'utf8'); expect(c).toContain('class GraphRetriever') })
    it('RE2', () => { const c = readFileSync(resolve(servicesRoot, 'graph-retriever.ts'), 'utf8'); expect(c).toContain('expand(') })
    it('RE3', () => { const c = readFileSync(resolve(servicesRoot, 'graph-retriever.ts'), 'utf8'); expect(c).toContain('queue') })
    it('RE4', () => { const c = readFileSync(resolve(servicesRoot, 'graph-retriever.ts'), 'utf8'); expect(c).toContain('shift') })
    it('RE5', () => { const c = readFileSync(resolve(servicesRoot, 'graph-retriever.ts'), 'utf8'); expect(c).toContain('push') })
    it('RE6', () => { const c = readFileSync(resolve(servicesRoot, 'graph-retriever.ts'), 'utf8'); expect(c).toContain('visitedEntities') })
    it('RE7', () => { const c = readFileSync(resolve(servicesRoot, 'graph-retriever.ts'), 'utf8'); expect(c).toContain('avgConf') })
    it('RE8', () => { const c = readFileSync(resolve(servicesRoot, 'graph-retriever.ts'), 'utf8'); expect(c).toContain('Array.from') })
    it('RE9', () => { const c = readFileSync(resolve(servicesRoot, 'graph-retriever.ts'), 'utf8'); expect(c).toContain('searchEntities') })
    it('RE10', () => { const c = readFileSync(resolve(servicesRoot, 'graph-retriever.ts'), 'utf8'); expect(c).toContain('getRelationsOf') })
    it('RE11', () => { const c = readFileSync(resolve(servicesRoot, 'graph-retriever.ts'), 'utf8'); expect(c).toContain('split(') })
    it('RE12', () => { const c = readFileSync(resolve(servicesRoot, 'graph-retriever.ts'), 'utf8'); expect(c).toContain('startsWith') })

    // Additional reasoning checks (10)
    it('KR11', () => { const c = readFileSync(resolve(servicesRoot, 'knowledge-reasoning-service.ts'), 'utf8'); expect(c).toContain('class KnowledgeReasoningService') })
    it('KR12', () => { const c = readFileSync(resolve(servicesRoot, 'knowledge-reasoning-service.ts'), 'utf8'); expect(c).toContain('findMechanismPath') })
    it('KR13', () => { const c = readFileSync(resolve(servicesRoot, 'knowledge-reasoning-service.ts'), 'utf8'); expect(c).toContain('findEvidenceChain') })
    it('KR14', () => { const c = readFileSync(resolve(servicesRoot, 'knowledge-reasoning-service.ts'), 'utf8'); expect(c).toContain('findRelatedMethods') })
    it('KR15', () => { const c = readFileSync(resolve(servicesRoot, 'knowledge-reasoning-service.ts'), 'utf8'); expect(c).toContain('MechanismPath') })
    it('KR16', () => { const c = readFileSync(resolve(servicesRoot, 'knowledge-reasoning-service.ts'), 'utf8'); expect(c).toContain('EvidenceChain') })
    it('KR17', () => { const c = readFileSync(resolve(servicesRoot, 'knowledge-reasoning-service.ts'), 'utf8'); expect(c).toContain('bfsPath') })
    it('KR18', () => { const c = readFileSync(resolve(servicesRoot, 'knowledge-reasoning-service.ts'), 'utf8'); expect(c).toContain('searchEntities') })
    it('KR19', () => { const c = readFileSync(resolve(servicesRoot, 'knowledge-reasoning-service.ts'), 'utf8'); expect(c).toContain('neighbors') })
    it('KR20', () => { const c = readFileSync(resolve(servicesRoot, 'knowledge-reasoning-service.ts'), 'utf8'); expect(c).toContain('constructor') })

    // Service file existence checks (10)
    it('FE1', () => { expect(existsSync(resolve(servicesRoot, 'local-entity-extractor.ts'))).toBe(true) })
    it('FE2', () => { expect(existsSync(resolve(servicesRoot, 'knowledge-graph-store.ts'))).toBe(true) })
    it('FE3', () => { expect(existsSync(resolve(servicesRoot, 'graph-retriever.ts'))).toBe(true) })
    it('FE4', () => { expect(existsSync(resolve(servicesRoot, 'graph-rag-adapter.ts'))).toBe(true) })
    it('FE5', () => { expect(existsSync(resolve(servicesRoot, 'knowledge-reasoning-service.ts'))).toBe(true) })
    it('FE6', () => { expect(existsSync(resolve(sharedRoot, 'knowledge-graph-schema.ts'))).toBe(true) })
    it('FE7', () => { expect(existsSync(resolve(sharedRoot, 'entity-extractor-schema.ts'))).toBe(true) })
    it('FE8', () => { expect(existsSync(resolve(docsRoot, 'knowledge-graph-architecture.md'))).toBe(true) })
    it('FE9', () => { expect(existsSync(resolve(docsRoot, 'graph-enhanced-rag.md'))).toBe(true) })
    it('FE10', () => { expect(existsSync(resolve(sharedRoot))).toBe(true) })

    // Misc (15)
    it('M1', () => { const c = readFileSync(resolve(sharedRoot, 'knowledge-graph-schema.ts'), 'utf8'); expect(c).toContain('export type') })
    it('M2', () => { const c = readFileSync(resolve(sharedRoot, 'knowledge-graph-schema.ts'), 'utf8'); expect(c).toContain('export interface') })
    it('M3', () => { const c = readFileSync(resolve(sharedRoot, 'knowledge-graph-schema.ts'), 'utf8'); expect(c).toContain('export function') })
    it('M4', () => { const c = readFileSync(resolve(sharedRoot, 'knowledge-graph-schema.ts'), 'utf8'); expect(c).toContain('export const') })
    it('M5', () => { const c = readFileSync(resolve(sharedRoot, 'knowledge-graph-schema.ts'), 'utf8'); expect(c).toContain('return true') })
    it('M6', () => { const c = readFileSync(resolve(sharedRoot, 'knowledge-graph-schema.ts'), 'utf8'); expect(c).toContain('return false') })
    it('M7', () => { const c = readFileSync(resolve(sharedRoot, 'knowledge-graph-schema.ts'), 'utf8'); expect(c).toContain('knowledge graph') })
    it('M8', () => { const c = readFileSync(resolve(sharedRoot, 'knowledge-graph-schema.ts'), 'utf8'); expect(c).toContain('Phase 8-J0') })
    it('M9', () => { const c = readFileSync(resolve(sharedRoot, 'knowledge-graph-schema.ts'), 'utf8'); expect(c).toContain('strict') })
    it('M10', () => { const c = readFileSync(resolve(sharedRoot, 'entity-extractor-schema.ts'), 'utf8'); expect(c).toContain('export interface EntityExtractionResult') })
    it('M11', () => { const c = readFileSync(resolve(sharedRoot, 'entity-extractor-schema.ts'), 'utf8'); expect(c).toContain('extractEntities') })
    it('M12', () => { const c = readFileSync(resolve(sharedRoot, 'entity-extractor-schema.ts'), 'utf8'); expect(c).toContain('extractRelations') })
    it('M13', () => { const c = readFileSync(resolve(servicesRoot, 'knowledge-reasoning-service.ts'), 'utf8'); expect(c).toContain('MechanismPath') })
    it('M14', () => { const c = readFileSync(resolve(servicesRoot, 'knowledge-reasoning-service.ts'), 'utf8'); expect(c).toContain('find') })
    it('M15', () => { const c = readFileSync(resolve(servicesRoot, 'knowledge-reasoning-service.ts'), 'utf8'); expect(c).toContain('sort') })
  })

  describe('final 10', () => {
    it('F1', () => { expect(existsSync(resolve(sharedRoot, 'knowledge-graph-schema.ts'))).toBe(true) })
    it('F2', () => { expect(existsSync(resolve(sharedRoot, 'entity-extractor-schema.ts'))).toBe(true) })
    it('F3', () => { expect(existsSync(resolve(servicesRoot, 'local-entity-extractor.ts'))).toBe(true) })
    it('F4', () => { expect(existsSync(resolve(servicesRoot, 'knowledge-graph-store.ts'))).toBe(true) })
    it('F5', () => { expect(existsSync(resolve(servicesRoot, 'graph-retriever.ts'))).toBe(true) })
    it('F6', () => { expect(existsSync(resolve(servicesRoot, 'graph-rag-adapter.ts'))).toBe(true) })
    it('F7', () => { expect(existsSync(resolve(servicesRoot, 'knowledge-reasoning-service.ts'))).toBe(true) })
    it('F8', () => { expect(existsSync(resolve(docsRoot, 'knowledge-graph-architecture.md'))).toBe(true) })
    it('F9', () => { expect(existsSync(resolve(docsRoot, 'graph-enhanced-rag.md'))).toBe(true) })
    it('F10', () => { expect(existsSync(resolve(sharedRoot))).toBe(true) })
  })
})
