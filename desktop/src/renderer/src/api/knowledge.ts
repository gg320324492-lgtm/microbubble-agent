// Knowledge API 入口（renderer 端封装）。
//
// 全部走 window.api.api.request（主进程注入 Bearer + 单飞 refresh），
// 禁止 renderer axios 直接调知识库 endpoint。

import type {
  DynamicCategory,
  KnowledgeList,
  KnowledgeResponse,
  KnowledgeSearchResult
} from '@shared/knowledge-types'
import type { ApiResult, ApiRequestPayload } from '@shared/preload-api'

/**
 * 左侧分类列表：GET /api/v1/knowledge/categories
 */
export async function getCategories(): Promise<ApiResult<DynamicCategory[]>> {
  return window.api.api.request<DynamicCategory[]>({
    method: 'GET',
    path: '/knowledge/categories'
  })
}

/**
 * 文档列表：GET /api/v1/knowledge?category=&keyword=&page=&page_size=
 */
export async function listKnowledge(opts: {
  category?: string | null
  keyword?: string
  page?: number
  pageSize?: number
} = {}): Promise<ApiResult<KnowledgeList>> {
  const query: ApiRequestPayload['query'] = {}
  if (opts.category && opts.category !== 'all') {
    query['category'] = opts.category
  }
  if (opts.keyword && opts.keyword.trim().length > 0) {
    query['keyword'] = opts.keyword.trim()
  }
  query['page'] = opts.page ?? 1
  query['page_size'] = opts.pageSize ?? 20

  return window.api.api.request<KnowledgeList>({
    method: 'GET',
    path: '/knowledge',
    query
  })
}

/**
 * 文档详情：GET /api/v1/knowledge/{id}
 */
export async function getKnowledge(id: number): Promise<ApiResult<KnowledgeResponse>> {
  return window.api.api.request<KnowledgeResponse>({
    method: 'GET',
    path: `/knowledge/${id}`
  })
}

/**
 * 语义搜索：GET /api/v1/knowledge/search/semantic?query=&limit=
 *
 * Phase 2-Impl-2A 仅 schema freeze; UI 入口暂留 Phase 3+ (RAG streaming 完整集成)。
 */
export async function semanticSearch(opts: {
  query: string
  limit?: number
  threshold?: number
}): Promise<ApiResult<KnowledgeSearchResult[]>> {
  const query: ApiRequestPayload['query'] = {
    query: opts.query,
    limit: opts.limit ?? 10
  }
  if (typeof opts.threshold === 'number') {
    query['threshold'] = opts.threshold
  }
  return window.api.api.request<KnowledgeSearchResult[]>({
    method: 'GET',
    path: '/knowledge/search/semantic',
    query
  })
}
