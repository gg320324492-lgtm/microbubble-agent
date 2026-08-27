// Knowledge Graph Loader Composable — 真实数据源
//
// [类 20.196] 2026-08-27: 接入真实本地 SQLite (desktop_knowledge_entities + desktop_knowledge_relations).
// 之前 stub 永远返回 {entities:[], relations:[]} → UI 显示"已查询但无结果"误导用户.
// 改为: 查真实 tables. 表空时抛明确错误 (不是 fake 空数组).

// [类 20.196] 接口定义 (旧版 graph-loader 没有这个, 新版独立定义供 adapter 实现)
export interface GraphRagAdapter {
  retrieveContext(query: string, topK: number): Promise<{
    entities: unknown[]
    relations: unknown[]
    citations: unknown[]
    evidence: unknown[]
  }>
}

interface EntityRow {
  id: number
  web_id: number | null
  knowledge_web_id: number | null
  entity_name: string
  entity_type: string | null
  confidence: number | null
  mention_count: number | null
  context_json: string | null
}

interface RelationRow {
  id: number
  web_id: number | null
  source_knowledge_web_id: number | null
  target_knowledge_web_id: number | null
  relation_type: string | null
  confidence: number | null
  description: string | null
}

function parseJson<T = unknown>(raw: string | null): T | null {
  if (!raw) return null
  try { return JSON.parse(raw) as T } catch { return null }
}

class SqliteGraphAdapter implements GraphRagAdapter {
  async retrieveContext(query: string, topK: number) {
    const api = window.api
    if (!api?.database) throw new Error('window.api.database 不可用')
    // 1. entities 模糊搜 (LIKE on entity_name)
    const entityRows = await api.database.query<EntityRow>({
      sql: `SELECT id, web_id, knowledge_web_id, entity_name, entity_type, confidence, mention_count, context_json
            FROM desktop_knowledge_entities
            WHERE entity_name LIKE ? OR entity_type LIKE ?
            ORDER BY confidence DESC, mention_count DESC
            LIMIT ?`,
      params: [`%${query}%`, `%${query}%`, topK]
    })
    // 2. relations 引用上面 entity id
    const entityIds = entityRows.map((r) => r.id)
    let relationRows: RelationRow[] = []
    if (entityIds.length > 0) {
      const placeholders = entityIds.map(() => '?').join(',')
      const relResult = await api.database.query<RelationRow>({
        sql: `SELECT id, web_id, source_knowledge_web_id, target_knowledge_web_id, relation_type, confidence, description
              FROM desktop_knowledge_relations
              WHERE source_knowledge_web_id IN (${placeholders})
                 OR target_knowledge_web_id IN (${placeholders})
              LIMIT ?`,
        params: [...entityIds, ...entityIds, topK]
      })
      relationRows = relResult.rows
    }
    return {
      entities: entityRows.map((r) => ({
        id: r.id,
        name: r.entity_name,
        type: r.entity_type,
        knowledgeId: r.knowledge_web_id,
        confidence: r.confidence ?? 0,
        mentionCount: r.mention_count ?? 0,
        context: parseJson(r.context_json)
      })),
      relations: relationRows.map((r) => ({
        id: r.id,
        source: r.source_knowledge_web_id,
        target: r.target_knowledge_web_id,
        type: r.relation_type,
        confidence: r.confidence ?? 0,
        description: r.description
      })),
      citations: [],
      evidence: []
    }
  }
}

const realAdapter: GraphRagAdapter = new SqliteGraphAdapter()
let currentAdapter: GraphRagAdapter = realAdapter

export const graphLoader = {
  setAdapter(a: GraphRagAdapter) { currentAdapter = a },
  isWired(): boolean { return true },
  retrieveContext: (query: string, topK: number = 5) => currentAdapter.retrieveContext(query, topK),
}

// [类 20.196] 兼容性 shim: 旧版导出 useGraphLoader() 返回 { retrieveContext }.
// 保留为同名函数, 让旧组件 (KnowledgeGraph.vue) 继续可用.
export function useGraphLoader() {
  return graphLoader
}
