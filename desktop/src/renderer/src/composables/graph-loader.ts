// Knowledge Graph Loader Composable — Phase 8-M0-E 适配层.
// 包装 graphRagAdapter, 让页面不直接接触 service 路径.
import { graphRagAdapter } from '../../services/knowledge-graph/graph-rag-adapter'

export function useGraphLoader() {
  return {
    retrieveContext: (query: string, topK: number = 5) => graphRagAdapter.retrieve(query, topK) as unknown as Promise<unknown>
  }
}
