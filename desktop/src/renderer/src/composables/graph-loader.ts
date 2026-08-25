// Knowledge Graph Loader Composable — Phase 8-M0-E 适配层.
// 包装 graphRagAdapter, 让页面不直接接触 service 路径.
// Phase 8-M0-F 修正: 提供 stub 实现, 避免运行时 import error (GraphRAGAdapter 需要完整 graph 栈).
export function useGraphLoader() {
  return {
    retrieveContext: async (_query: string, _topK: number = 5): Promise<unknown> => {
      return {
        entities: [],
        relations: [],
        citations: [],
        evidence: []
      }
    }
  }
}
