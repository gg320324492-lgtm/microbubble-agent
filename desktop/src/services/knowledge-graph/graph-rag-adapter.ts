// Graph-Enhanced RAG Adapter — 混合检索 + 图扩展 + 上下文融合。
import type { RAGContext, SearchResult, CitationReference, ContextChunk } from '../../shared/knowledge/context-schema'
import type { HybridRetriever } from '../../shared/knowledge/retriever-schema'
import { GraphRetriever, type GraphContext } from './graph-retriever'

export class GraphRAGAdapter {
  constructor(
    private hybridRetriever: HybridRetriever,
    private graphRetriever: GraphRetriever,
    private buildContext: (results: SearchResult[], query: string) => RAGContext
  ) {}

  async retrieve(query: string, topK: number = 5): Promise<RAGContext> {
    // Step 1: Keyword/vector retrieval via HybridRetriever
    const hybridResults = await this.hybridRetriever.retrieve(query, topK)

    // Step 2: Graph expansion
    const graphContext = this.graphRetriever.expand(query, 2, 20)

    // Step 3: Merge context — graph entities supplement hybrid results
    const mergedResults = this.mergeResults(hybridResults, graphContext)

    // Step 4: Build RAGContext using existing builder (no modification)
    return this.buildContext(mergedResults, query)
  }

  private mergeResults(hybrid: SearchResult[], graph: GraphContext): SearchResult[] {
    const result = [...hybrid]
    const seen = new Set<string>(hybrid.map(r => r.chunk.chunkId))

    // Add graph-derived search results
    for (const entity of graph.entities.slice(0, 3)) {
      const chunkId = entity.sourceDocuments[0] ?? entity.id
      if (seen.has(chunkId)) continue
      seen.add(chunkId)
      result.push(this.entityToSearchResult(entity, chunkId, graph))
    }
    return result
  }

  private entityToSearchResult(entity: import('../../shared/knowledge-graph/knowledge-graph-schema').ScientificEntity, chunkId: string, graph: GraphContext): SearchResult {
    const citation: CitationReference = {
      documentId: entity.id,
      chunkId: chunkId,
      confidence: entity.confidence
    }
    const chunk: ContextChunk = {
      chunkId: chunkId,
      content: `${entity.type}: ${entity.name} — ${entity.description}`,
      score: entity.confidence,
      citation
    }
    return { chunk, score: entity.confidence }
  }
}
