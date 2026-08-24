// Knowledge Graph Store — 内存图存储（确定性 + 防御性拷贝）。
import type { ScientificEntity, KnowledgeRelation, EntityType } from '../../shared/knowledge-graph/knowledge-graph-schema'

export class KnowledgeGraphStore {
  private nodes: Map<string, ScientificEntity> = new Map()
  private edges: Map<string, KnowledgeRelation> = new Map()

  addEntity(entity: ScientificEntity): boolean {
    if (this.nodes.has(entity.id)) return false
    this.nodes.set(entity.id, this.cloneEntity(entity))
    return true
  }

  addRelation(relation: KnowledgeRelation): boolean {
    if (this.edges.has(relation.id)) return false
    if (!this.nodes.has(relation.sourceEntityId)) return false
    if (!this.nodes.has(relation.targetEntityId)) return false
    this.edges.set(relation.id, this.cloneRelation(relation))
    return true
  }

  getEntity(id: string): ScientificEntity | null {
    const e = this.nodes.get(id)
    return e ? this.cloneEntity(e) : null
  }

  getRelation(id: string): KnowledgeRelation | null {
    const r = this.edges.get(id)
    return r ? this.cloneRelation(r) : null
  }

  getEntitiesByType(type: EntityType): ScientificEntity[] {
    const result: ScientificEntity[] = []
    const ids = Array.from(this.nodes.keys()).sort()
    for (const id of ids) {
      const e = this.nodes.get(id)!
      if (e.type === type) result.push(this.cloneEntity(e))
    }
    return result
  }

  getRelationsOf(entityId: string): KnowledgeRelation[] {
    const result: KnowledgeRelation[] = []
    const ids = Array.from(this.edges.keys()).sort()
    for (const id of ids) {
      const r = this.edges.get(id)!
      if (r.sourceEntityId === entityId || r.targetEntityId === entityId) {
        result.push(this.cloneRelation(r))
      }
    }
    return result
  }

  searchEntities(query: string, typeFilter?: EntityType): ScientificEntity[] {
    const q = query.toLowerCase()
    const result: ScientificEntity[] = []
    const ids = Array.from(this.nodes.keys()).sort()
    for (const id of ids) {
      const e = this.nodes.get(id)!
      if ((!typeFilter || e.type === typeFilter) && e.name.toLowerCase().includes(q)) {
        result.push(this.cloneEntity(e))
      }
    }
    return result
  }

  neighbors(entityId: string): { out: ScientificEntity[]; in: ScientificEntity[] } {
    const out: ScientificEntity[] = []
    const inn: ScientificEntity[] = []
    const ids = Array.from(this.edges.keys()).sort()
    for (const id of ids) {
      const r = this.edges.get(id)!
      if (r.sourceEntityId === entityId) {
        const target = this.nodes.get(r.targetEntityId)
        if (target) out.push(this.cloneEntity(target))
      }
      if (r.targetEntityId === entityId) {
        const source = this.nodes.get(r.sourceEntityId)
        if (source) inn.push(this.cloneEntity(source))
      }
    }
    return { out: this.dedup(out), in: this.dedup(inn) }
  }

  getAllNodes(): ScientificEntity[] {
    const result: ScientificEntity[] = []
    const ids = Array.from(this.nodes.keys()).sort()
    for (const id of ids) result.push(this.cloneEntity(this.nodes.get(id)!))
    return result
  }

  getAllEdges(): KnowledgeRelation[] {
    const result: KnowledgeRelation[] = []
    const ids = Array.from(this.edges.keys()).sort()
    for (const id of ids) result.push(this.cloneRelation(this.edges.get(id)!))
    return result
  }

  deleteEntity(id: string): boolean {
    if (!this.nodes.has(id)) return false
    this.nodes.delete(id)
    // Delete related edges
    const edgeIds = Array.from(this.edges.keys())
    for (const eid of edgeIds) {
      const e = this.edges.get(eid)!
      if (e.sourceEntityId === id || e.targetEntityId === id) {
        this.edges.delete(eid)
      }
    }
    return true
  }

  clear(): void {
    this.nodes.clear()
    this.edges.clear()
  }

  snapshot(): { nodes: ScientificEntity[]; edges: KnowledgeRelation[] } {
    return { nodes: this.getAllNodes(), edges: this.getAllEdges() }
  }

  size(): { nodes: number; edges: number } {
    return { nodes: this.nodes.size, edges: this.edges.size }
  }

  // ============ Defensive Copies ============

  private cloneEntity(e: ScientificEntity): ScientificEntity {
    return {
      id: e.id, name: e.name, type: e.type, description: e.description,
      sourceDocuments: [...e.sourceDocuments],
      confidence: e.confidence,
      metadata: { ...e.metadata }
    }
  }

  private cloneRelation(r: KnowledgeRelation): KnowledgeRelation {
    return {
      id: r.id, sourceEntityId: r.sourceEntityId, targetEntityId: r.targetEntityId,
      relationType: r.relationType, confidence: r.confidence, evidence: r.evidence
    }
  }

  private dedup(entities: ScientificEntity[]): ScientificEntity[] {
    const seen = new Set<string>()
    const result: ScientificEntity[] = []
    for (const e of entities) {
      if (!seen.has(e.id)) {
        seen.add(e.id)
        result.push(e)
      }
    }
    return result
  }
}
