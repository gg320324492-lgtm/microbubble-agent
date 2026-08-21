// Knowledge 模块共享类型契约。
// 一律对照 app/api/v1/knowledge.py + app/schemas/knowledge.py (Pydantic)。
// 任何后端字段改动必须先改 docs/desktop-conversion/knowledge-api-contract.md 再改本文件。

/**
 * 左侧 "知识库分类" 列表项 (来自 DynamicCategory)。
 */
export interface DynamicCategory {
  name: string
  count: number
}

/**
 * 文档列表项 (KnowledgeListItem, 不含 content 全文)。
 */
export interface KnowledgeListItem {
  id: number
  title: string
  category: string | null
  tags: string[] | null
  key_concepts: string[] | null
  related_topics: string[] | null
  knowledge_type: string | null
  source: string | null
  source_type: string | null
  summary: string | null
  snippet: string | null
  analysis_status: string | null
  quality_score: number | null
  needs_review: boolean
  topic: string | null
  created_by: number | null
  created_at: string
  updated_at: string
  thumbnail_url: string | null
  image_count: number
  file_path: string | null
  file_name: string | null
  file_type: string | null
  meta: Record<string, unknown> | null
}

/**
 * 知识列表分页包装 (KnowledgeList)。
 */
export interface KnowledgeList {
  items: KnowledgeListItem[]
  total: number
}

/**
 * 文档详情基础字段 (来自 KnowledgeBase, KnowledgeResponse 继承这些 + 自身。
 * 不强求完全覆盖所有字段; UI 用到的子集 + 自由扩展)。
 */
export interface KnowledgeBaseFields {
  title: string
  content: string
  category: string | null
  tags: string[] | null
  key_concepts: string[] | null
  related_topics: string[] | null
  knowledge_type: string | null
  topic: string | null
  analysis_status: string | null
  quality_score: number | null
  needs_review: boolean
  thumbnail_url: string | null
  image_count: number
  meta: Record<string, unknown> | null
  created_by: number | null
  created_at: string
  updated_at: string
}

/**
 * 文档详情 (KnowledgeResponse) — 全部字段 (含 id + source + file_* 等)。
 */
export interface KnowledgeResponse extends KnowledgeBaseFields {
  id: number
  source: string | null
  source_type: string | null
  file_path: string | null
  file_name: string | null
  file_type: string | null
  summary: string | null
}

/**
 * 语义搜索结果项 (KnowledgeSearchResult)。
 * Phase 2-Impl-2A 仅 schema freeze, UI 入口留 Phase 3+。
 */
export interface KnowledgeSearchResult {
  id: number
  title: string
  content: string
  category: string | null
  tags: string[] | null
  source: string | null
  score: number
}

/**
 * UI 派生：analysis_status → 中文 + 颜色 (与 web 端 analysis_status map 类似)。
 * 'pending' | 'processing' | 'completed' | 'failed' | 其他 -> '未分析'
 */
export function statusLabel(s: string | null | undefined): string {
  switch (s) {
    case 'completed': return '已分析'
    case 'processing': return '分析中'
    case 'pending': return '待分析'
    case 'failed': return '失败'
    default: return s ?? '未分析'
  }
}

export function statusVariant(s: string | null | undefined): 'ok' | 'warn' | 'error' | 'mute' {
  switch (s) {
    case 'completed': return 'ok'
    case 'processing': return 'warn'
    case 'pending': return 'mute'
    case 'failed': return 'error'
    default: return 'mute'
  }
}

/**
 * UI 派生：把 ISO 时间字符串格式化成 zh-CN 本地时间。
 * 失败兜底空字符串。
 */
export function formatDateTime(iso: string | null | undefined): string {
  if (!iso) return ''
  const d = new Date(iso)
  if (isNaN(d.getTime())) return iso
  return d.toLocaleString('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit'
  })
}
