// Graph Retriever — 通过图扩展查询。
import type { ScientificEntity, KnowledgeRelation } from '../../shared/knowledge-graph/knowledge-graph-schema'
import { KnowledgeGraphStore } from './knowledge-graph-store'

export interface GraphContext {
  entities: ScientificEntity[]
  relations: KnowledgeRelation[]
  citations: string[]
  query: string
  confidence: number
}

export class GraphRetriever {
  constructor(private store: KnowledgeGraphStore) {}

  expand(query: string, maxDepth: number = 2, maxEntities: number = 20): GraphContext {
    const queryEntities = this.store.searchEntities(query)
    if (queryEntities.length === 0) {
      return { entities: [], relations: [], citations: [], query, confidence: 0 }
    }

    const visitedEntities = new Set<string>()
    const collectedEntities: ScientificEntity[] = []
    const collectedRelations: KnowledgeRelation[] = []
    const citations = new Set<string>()

    const queue: Array<{ id: string; depth: number }> = queryEntities.map(e => ({ id: e.id, depth: 0 }))
    for (const e of queryEntities) {
      visitedEntities.add(e.id)
      collectedEntities.push(e)
    }

    while (queue.length > 0 && collectedEntities.length < maxEntities) {
      const { id, depth } = queue.shift()!
      if (depth >= maxDepth) continue
      const { out, inn } = this.store.neighbors(id)
      const neighbors = [...out, ...inn]
      for (const n of neighbors) {
        if (!visitedEntities.has(n.id) && collectedEntities.length < maxEntities) {
          visitedEntities.add(n.id)
          collectedEntities.push(n)
          queue.push({ id: n.id, depth: depth + 1 })
        }
      }
      const relations = this.store.getRelationsOf(id)
      for (const r of relations) {
        collectedRelations.push(r)
        for (const sd of r.evidence.split(/\s+/)) {
          if (sd.startsWith('doc:')) citations.add(sd.slice(4))
        }
      }
    }

    const avgConf = collectedEntities.length > 0
      ? collectedEntities.reduce((s, e) => s + e.confidence, 0) / collectedEntities.length
      : 0

    return {
      entities: collectedEntities,
      relations: collectedRelations,
      citations: Array.from(citations),
      query,
      confidence: avgConf
    }
  }
}
