// Knowledge Graph Loader Composable — Phase 8-M0-E 适配层.
//
// [类 20.191] 2026-08-27: 原 stub 永远返回空数组 { entities:[], relations:[], citations:[], evidence:[] }
// 让 UI 显示 "无数据" 但实际是 fake "调用了 graph RAG 但没结果", 误导用户.
// 改为: 抛 GraphRagNotWiredError, 强制要求 wire 真实 GraphRAG adapter.

export class GraphRagNotWiredError extends Error {
  constructor(query: string) {
    super(
      `[graph-loader] GraphRAG adapter 未接入, query="${query}" 无法执行. ` +
      `原 stub (Phase 8-M0-F) 已删除 — 之前会静默返回空数组让 UI 误以为"已查询但无结果". ` +
      `真实数据路径: 1) 本地 desktop_knowledge_entities + desktop_knowledge_relations, 2) FastAPI /api/v1/graph-rag/* with vector search. ` +
      `调 graphLoader.setAdapter(realAdapter) 注入真实实现.`
    )
    this.name = 'GraphRagNotWiredError'
  }
}

export interface GraphRagAdapter {
  retrieveContext(query: string, topK: number): Promise<{
    entities: unknown[]
    relations: unknown[]
    citations: unknown[]
    evidence: unknown[]
  }>
}

const notWiredAdapter: GraphRagAdapter = {
  async retrieveContext(query: string) {
    throw new GraphRagNotWiredError(query)
  }
}

let currentAdapter: GraphRagAdapter = notWiredAdapter

export const graphLoader = {
  setAdapter(a: GraphRagAdapter) { currentAdapter = a },
  isWired(): boolean { return currentAdapter !== notWiredAdapter },
  retrieveContext: (query: string, topK: number = 5) => currentAdapter.retrieveContext(query, topK),
}

export function useGraphLoader() {
  return graphLoader
}
