// Knowledge Reasoning Service — 面向推理的图查询服务。
import type { ScientificEntity, KnowledgeRelation } from '../../shared/knowledge-graph/knowledge-graph-schema'
import { KnowledgeGraphStore } from './knowledge-graph-store'

export interface MechanismPath {
  entities: ScientificEntity[]
  relations: KnowledgeRelation[]
  path: string[]
}

export interface EvidenceChain {
  sourceEntity: ScientificEntity
  targetEntity: ScientificEntity
  intermediateEntities: ScientificEntity[]
  relations: KnowledgeRelation[]
  confidence: number
}

export class KnowledgeReasoningService {
  constructor(private store: KnowledgeGraphStore) {}

  findMechanismPath(startName: string, endName: string, maxLength: number = 5): MechanismPath | null {
    const startEntities = this.store.searchEntities(startName)
    const endEntities = this.store.searchEntities(endName)
    if (startEntities.length === 0 || endEntities.length === 0) return null

    const startIds = new Set(startEntities.map(e => e.id))
    const endIds = new Set(endEntities.map(e => e.id))
    const visited = new Set<string>()

    for (const startId of startIds) {
      for (const endId of endIds) {
        const path = this.bfsPath(startId, endId, maxLength, visited)
        if (path) {
          const entityIds = new Set(path)
          const entities = Array.from(entityIds).map(id => this.store.getEntity(id)!).filter(Boolean)
          const allRelations = this.store.getAllEdges().filter(r =>
            path.includes(r.sourceEntityId) && path.includes(r.targetEntityId)
          )
          return {
            entities,
            relations: allRelations,
            path: path.map(id => this.store.getEntity(id)?.name ?? id)
          }
        }
      }
    }
    return null
  }

  findEvidenceChain(sourceName: string, targetName: string): EvidenceChain[] {
    const sources = this.store.searchEntities(sourceName)
    const targets = this.store.searchEntities(targetName)
    const chains: EvidenceChain[] = []
    for (const s of sources) {
      for (const t of targets) {
        const path = this.bfsPath(s.id, t.id, 4, new Set())
        if (path && path.length >= 2) {
          const intermediates: ScientificEntity[] = []
          for (let i = 1; i < path.length - 1; i++) {
            const e = this.store.getEntity(path[i])
            if (e) intermediates.push(e)
          }
          const relations = this.store.getAllEdges().filter(r =>
            path.includes(r.sourceEntityId) && path.includes(r.targetEntityId)
          )
          const confidence = relations.length > 0
            ? relations.reduce((s, r) => s + r.confidence, 0) / relations.length
            : 0
          chains.push({ sourceEntity: s, targetEntity: t, intermediateEntities: intermediates, relations, confidence })
        }
      }
    }
    return chains.sort((a, b) => b.confidence - a.confidence)
  }

  findRelatedMethods(methodName: string): ScientificEntity[] {
    const matches = this.store.searchEntities(methodName)
    if (matches.length === 0) return []
    const related = new Set<string>()
    for (const m of matches) {
      const { out, inn } = this.store.neighbors(m.id)
      for (const n of [...out, ...inn]) if (n.type === 'Method') related.add(n.id)
    }
    const result: ScientificEntity[] = []
    for (const id of related) {
      const e = this.store.getEntity(id)
      if (e) result.push(e)
    }
    return result.sort((a, b) => b.confidence - a.confidence)
  }

  private bfsPath(start: string, end: string, maxLength: number, visited: Set<string>): string[] | null {
    const queue: Array<{ id: string; path: string[] }> = [{ id: start, path: [start] }]
    visited.add(start)
    while (queue.length > 0) {
      const { id, path } = queue.shift()!
      if (path.length > maxLength) continue
      const { out, inn } = this.store.neighbors(id)
      for (const n of [...out, ...inn]) {
        if (visited.has(n.id)) continue
        const newPath = [...path, n.id]
        if (n.id === end) return newPath
        visited.add(n.id)
        queue.push({ id: n.id, path: newPath })
      }
    }
    return null
  }
}
