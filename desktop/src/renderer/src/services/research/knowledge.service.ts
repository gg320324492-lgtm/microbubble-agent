// Knowledge Service — 真实文献/知识库 adapter.
//
// [类 20.191] 2026-08-27: 接入本地 SQLite desktop_knowledge 表.
// [类 20.209] 2026-08-28: 扩 DocumentItem 字段 (snippet/summary/category/file_name/updated_at/analysis_status),
//   KnowledgeView 直接显示, 不再依赖 web KnowledgeListItem.
// 数据源: desktop_knowledge (含 4 个子表 chunks/relations/entities/formulas, 主表全量字段).

import type { DocumentItem, SearchResult, KnowledgeFolder } from './knowledge.service'

// [类 20.209] 在文件内联定义类型, 避免循环 import 失败.
//   原代码 import from './knowledge.service' (自身) → TS 解析不到定义.
//   之前能跑因为 types/d.ts 在 ambient context 兜底.
export interface DocumentItem {
  id: string
  title: string
  authors: string
  journal: string
  year: number
  type: 'paper' | 'report' | 'dataset' | 'experiment' | string
  tags: string[]
  credibility: number
  citations: number
  relevance: number
  // [类 20.209] 扩展字段 (兼容 web KnowledgeListItem + KnowledgeView 模板):
  snippet?: string | null
  summary?: string | null
  category?: string | null
  file_name?: string | null
  file_type?: string | null
  analysis_status?: string | null
  updated_at?: string | null
  topic?: string | null
  key_concepts?: string[]
  source?: string | null
  source_type?: string | null
  source_url?: string | null
  entities?: unknown
  image_count?: number
}

export interface SearchResult {
  documentId: string
  score: number
  excerpt: string
}

export interface KnowledgeFolder {
  id: string
  name: string
  count: number
}

interface KnowledgeRow {
  id: number
  title: string
  category: string | null
  topic: string | null
  tags_json: string | null
  key_concepts_json: string | null
  knowledge_type: string | null
  source: string | null
  source_type: string | null
  source_url: string | null
  summary: string | null
  content: string | null
  entities_json: string | null
  quality_score: number | null
  analysis_status: string | null
  file_path: string | null
  file_name: string | null
  file_type: string | null
  created_at_epoch: number | null
  updated_at_epoch: number | null
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

function parseJson<T = unknown>(raw: string | null): T | null {
  if (!raw) return null
  try { return JSON.parse(raw) as T } catch { return null }
}

function epochToIso(epoch: number | null): string | null {
  if (!epoch) return null
  // [类 20.210] 2026-08-28: desktop_knowledge epoch 是秒 (10 位),
  //   desktop_tasks 是毫秒 (13 位). 用长度判断避免 58562 年这类显示错误.
  const ms = epoch < 1e12 ? epoch * 1000 : epoch
  return new Date(ms).toISOString()
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

function rowToDocument(r: KnowledgeRow): DocumentItem {
  const tags = parseJsonArray<string>(r.tags_json)
  const credibility = typeof r.quality_score === 'number' ? Math.min(1, Math.max(0, r.quality_score)) : 0.5
  // [类 20.209] 扩展 DocumentItem shape 兼容 web KnowledgeListItem:
  //   snippet / summary / category / file_name / updated_at / analysis_status / topic / key_concepts / source
  const snippet = r.content ? r.content.slice(0, 200) : ''
  const extended = r as unknown as Record<string, unknown>
  return {
    id: String(r.id),
    title: r.title,
    authors: '',
    journal: r.file_name ?? r.category ?? '',
    year: r.created_at_epoch ? new Date(r.created_at_epoch < 1e12 ? r.created_at_epoch * 1000 : r.created_at_epoch).getFullYear() : new Date().getFullYear(),
    type: mapType(r.knowledge_type),
    tags,
    credibility,
    citations: 0,
    relevance: credibility,
    // 扩展字段:
    snippet,
    summary: r.summary ?? '',
    category: r.category ?? '',
    file_name: r.file_name ?? '',
    analysis_status: r.analysis_status ?? 'pending',
    updated_at: epochToIso(r.updated_at_epoch),
    topic: r.topic ?? '',
    key_concepts: parseJsonArray<string>(r.key_concepts_json),
    source: r.source ?? '',
    source_type: r.source_type ?? '',
    source_url: r.source_url ?? '',
    file_type: r.file_type ?? '',
    entities: parseJson(r.entities_json),
    image_count: 0
  } as DocumentItem
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
    // [类 20.209] SELECT 字段扩全, 含 updated_at_epoch/source/source_url/analysis_status/content
    const { rows } = await api.database.query<KnowledgeRow>({
      sql: `SELECT id, title, category, topic, tags_json, key_concepts_json, knowledge_type,
                   source, source_type, source_url, summary, content, entities_json,
                   quality_score, analysis_status, file_path, file_name, file_type,
                   created_at_epoch, updated_at_epoch
            FROM desktop_knowledge
            ORDER BY created_at_epoch DESC
            LIMIT 500`
    })
    return rows.map(rowToDocument)
  }
  async getDocument(id: string): Promise<DocumentItem | undefined> {
    const api = window.api
    if (!api?.database) throw new Error('window.api.database 不可用')
    const { rows } = await api.database.query<KnowledgeRow>({
      sql: `SELECT id, title, category, topic, tags_json, key_concepts_json, knowledge_type,
                   source, source_type, source_url, summary, content, entities_json,
                   quality_score, analysis_status, file_path, file_name, file_type,
                   created_at_epoch, updated_at_epoch
            FROM desktop_knowledge
            WHERE id = ? `,
      params: [Number(id)]
    })
    if (rows.length === 0) return undefined
    return rowToDocument(rows[0])
  }
  async searchDocuments(query: string): Promise<SearchResult[]> {
    if (!query.trim()) return []
    const api = window.api
    if (!api?.database) throw new Error('window.api.database 不可用')
    const like = `%${query.replace(/[%_]/g, '\\$&')}%`
    // [类 20.200] 2026-08-28: 修 SQL 语法 (空行 + 缺 WHERE).
    //   老 query: FROM desktop_knowledge \n\n AND (...)  → SQLite 报 syntax error
    //   改为 WHERE 1=1 前缀, 真正可用 LIKE 过滤
    const { rows } = await api.database.query<KnowledgeRow>({
      sql: `SELECT id, title, category, topic, tags_json, key_concepts_json, knowledge_type,
                   source, source_type, source_url, summary, content, entities_json,
                   quality_score, analysis_status, file_path, file_name, file_type,
                   created_at_epoch, updated_at_epoch
            FROM desktop_knowledge
            WHERE 1=1
              AND (title LIKE ? OR category LIKE ? OR topic LIKE ? OR tags_json LIKE ?)
            ORDER BY quality_score DESC, created_at_epoch DESC
            LIMIT 100`,
      params: [like, like, like, like]
    })
    return rows.map((r) => {
      const d = rowToDocument(r)
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
export const realKnowledgeAdapter = realAdapter

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
