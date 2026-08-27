// Knowledge Service — 真实文献/知识库 adapter.
//
// [类 20.191] 2026-08-27: 接入本地 SQLite desktop_knowledge 表.
// 数据源: desktop_knowledge (含 4 个子表 chunks/relations/entities/formulas,
// 这里只读主表, 详细子表按需后续接入).
// 真实字段 (desktop_knowledge): id / web_id / title / content / category /
// topic / tags_json / key_concepts_json / related_topics_json / knowledge_type /
// summary / entities (jsonb) / file_path / file_name / file_type /
// auto_researched / needs_review / analysis_status / quality_score / created_at_epoch.
//
// 适配到前端 DocumentItem shape:
//   id, title, authors, journal, year, type, tags, credibility, citations, relevance

import type { DocumentItem, SearchResult, KnowledgeFolder } from './knowledge.service'

interface KnowledgeRow {
  id: number
  title: string
  category: string | null
  topic: string | null
  tags_json: string | null  // JSON array string
  key_concepts_json: string | null
  knowledge_type: string | null
  summary: string | null
  entities_json: string | null  // JSON object string (注意是 entities_json, 不是 entities)
  quality_score: number | null
  file_path: string | null
  file_name: string | null
  file_type: string | null
  created_at_epoch: number | null
}

function parseJsonArray<T = string>(raw: string | null): T[] {
  if (!raw) return []
  try {
    const v = JSON.parse(raw)
    return Array.isArray(v) ? v : []
  } catch {
    return []
  }
}

function mapType(local: string | null): DocumentItem['type'] {
  switch (local) {
    case 'experiment': return 'experiment'
    case 'dataset': return 'dataset'
    case 'report': return 'report'
    case 'paper':
    default: return 'paper'
  }
}

function mapRowToDocument(r: KnowledgeRow): DocumentItem {
  const tags = parseJsonArray<string>(r.tags_json)
  const credibility = typeof r.quality_score === 'number' ? Math.min(1, Math.max(0, r.quality_score)) : 0.5
  // authors: desktop_knowledge 没有此字段 (Phase 11 阶段).
  // 真实 authors 在 web PG 端. 留 TODO: P11 Stage 3 拉 PG 后补全.
  // 暂用 topic + 类型 作 placeholder (空字符串不行, 折中用类型标签).
  return {
    id: String(r.id),
    title: r.title,
    authors: '', // TODO: 从 PG web_id 关联拉 authors
    journal: r.file_name ?? r.category ?? '',
    year: r.created_at_epoch ? new Date(r.created_at_epoch * 1000).getFullYear() : new Date().getFullYear(),
    type: mapType(r.knowledge_type),
    tags,
    credibility,
    citations: 0, // TODO: PG 拉真实引用计数
    relevance: credibility
  }
}

interface KnowledgeAdapter {
  getDocuments(): Promise<DocumentItem[]>
  getDocument(id: string): Promise<DocumentItem | undefined>
  searchDocuments(query: string): Promise<SearchResult[]>
  getFolders(): Promise<KnowledgeFolder[]>
  getDocumentCount(): Promise<number>
  importDocument(file: File): Promise<DocumentItem | null>
}

class SqliteKnowledgeAdapter implements KnowledgeAdapter {
  async getDocuments(): Promise<DocumentItem[]> {
    const api = window.api
    if (!api?.database) throw new Error('window.api.database 不可用')
    const { rows } = await api.database.query<KnowledgeRow>({
      sql: `SELECT id, title, category, topic, tags_json, key_concepts_json, knowledge_type,
                   summary, entities_json, quality_score, file_path, file_name, file_type, created_at_epoch
            FROM desktop_knowledge
            ORDER BY created_at_epoch DESC
            LIMIT 500`
    })
    return rows.map(mapRowToDocument)
  }
  async getDocument(id: string): Promise<DocumentItem | undefined> {
    const api = window.api
    if (!api?.database) throw new Error('window.api.database 不可用')
    const { rows } = await api.database.query<KnowledgeRow>({
      sql: `SELECT id, title, category, topic, tags_json, key_concepts_json, knowledge_type,
                   summary, entities_json, quality_score, file_path, file_name, file_type, created_at_epoch
            FROM desktop_knowledge
            WHERE id = ? `,
      params: [Number(id)]
    })
    if (rows.length === 0) return undefined
    return mapRowToDocument(rows[0])
  }
  async searchDocuments(query: string): Promise<SearchResult[]> {
    if (!query.trim()) return []
    const api = window.api
    if (!api?.database) throw new Error('window.api.database 不可用')
    const like = `%${query.replace(/[%_]/g, '\\$&')}%`
    const { rows } = await api.database.query<KnowledgeRow>({
      sql: `SELECT id, title, category, topic, tags_json, key_concepts_json, knowledge_type,
                   summary, entities_json, quality_score, file_path, file_name, file_type, created_at_epoch
            FROM desktop_knowledge
           
              AND (title LIKE ? OR category LIKE ? OR topic LIKE ? OR tags_json LIKE ?)
            ORDER BY quality_score DESC NULLS LAST, created_at_epoch DESC
            LIMIT 100`,
      params: [like, like, like, like]
    })
    return rows.map((r) => {
      const d = mapRowToDocument(r)
      return { documentId: d.id, score: d.credibility, excerpt: d.title }
    })
  }
  async getFolders(): Promise<KnowledgeFolder[]> {
    const api = window.api
    if (!api?.database) throw new Error('window.api.database 不可用')
    // desktop_knowledge 没 folder 表. 简化: 按 category 聚合, 算 count.
    const { rows } = await api.database.query<{ category: string; count: number }>({
      sql: `SELECT COALESCE(category, '未分类') AS category, COUNT(*) AS count
            FROM desktop_knowledge
            GROUP BY category
            ORDER BY count DESC`
    })
    return rows.map((r, i) => ({
      id: `cat-${i}-${r.category}`,
      name: r.category,
      count: r.count
    }))
  }
  async getDocumentCount(): Promise<number> {
    const api = window.api
    if (!api?.database) throw new Error('window.api.database 不可用')
    const { rows: [row] } = await api.database.query<{ count: number }>({
      sql: 'SELECT COUNT(*) AS count FROM desktop_knowledge'
    })
    return row?.count ?? 0
  }
  async importDocument(_file: File): Promise<DocumentItem | null> {
    // TODO: 走 IPC data:import.commit 上传 CSV
    return null
  }
}

const realAdapter: KnowledgeAdapter = new SqliteKnowledgeAdapter()

let currentAdapter: KnowledgeAdapter = realAdapter

export const knowledgeService = {
  setAdapter(a: KnowledgeAdapter) { currentAdapter = a },
  isWired(): boolean { return true },
  getDocuments: () => currentAdapter.getDocuments(),
  getDocument: (id: string) => currentAdapter.getDocument(id),
  searchDocuments: (q: string) => currentAdapter.searchDocuments(q),
  getFolders: () => currentAdapter.getFolders(),
  getDocumentCount: () => currentAdapter.getDocumentCount(),
  importDocument: (f: File) => currentAdapter.importDocument(f),
}
