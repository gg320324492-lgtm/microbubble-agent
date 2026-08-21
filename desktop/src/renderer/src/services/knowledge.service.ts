// Knowledge Service Layer (Phase 4-A) + Phase 4-B Performance Layer.
//
// 业务层, 介于 store/view (上层) 与 api/knowledge (IPC gateway, 下层) 之间.
// Phase 4-B 加:
//   - LRU cache (utils/lru-cache.ts) 避免重复 fetch
//   - getManyKnowledge batch 实现 (dedup + invalid 过滤 + 保序)
//   - prefetchKnowledgeForCitations 留口 (Phase 4-B: 委托 batch; Phase 4+: 接 RAG metadata)
//
// 架构:
//   KnowledgeView
//     ↓ 调 store action
//   stores/knowledge.ts (Pinia 状态 + UI 缓存)
//     ↓ 调 service
//   services/knowledge.service.ts  ← Phase 4-A NEW, Phase 4-B 增强
//     ├─ 内置 LRU cache (Phase 4-B)
//     ├─ debugLog 钩子
//     └─ Phase 4+ 留口 (RAG / Telemetry / Multi-window / IndexedDB 持久化)
//     ↓ 调 api
//   api/knowledge.ts (IPC + payload 包装)
//     ↓ window.api.api.request
//   main/api.service.request (Bearer + 单飞 refresh)
//     ↓ fetch
//   FastAPI /api/v1/knowledge/*
//
// 不在范围 (Phase 4+):
//   - RAG / Retriever / Embedding
//   - Backend schema 修改
//   - 多 window sync / IndexedDB 持久化
//   - LRU TTL (Phase 4+)
//   - SSE streaming citation prefetch (Phase 4+ 接 chat store 流)

import * as knowledgeApi from '../api/knowledge'
import type {
  DynamicCategory,
  KnowledgeList,
  KnowledgeResponse,
  KnowledgeSearchResult,
  KnowledgeListItem
} from '@shared/knowledge-types'
import type { ApiResult } from '@shared/preload-api'
import type { StreamCitationEntry } from '@shared/chat-types'
import { LRUCache } from '../utils/lru-cache'

/**
 * Phase 4-B: 单例 LRU cache, maxSize = 200.
 * 假设一个 lab session 浏览 ≤ 200 个 knowledge 详情, 够用.
 * Phase 4+ 可调整为可配置 (按 user category / tenant).
 *
 * 注:
 *   - 不分 tenant / user (Phase 4-A 简化: 单 user 桌面 app, 不考虑 multi-tenant)
 *   - 不分 type (KnowledgeResponse 统一缓存)
 *   - 不做 TTL (Knowledge 文档内容由 backend content 字段决定, 当前 stable)
 */
const KNOWLEDGE_CACHE_MAX = 200
const knowledgeCache = new LRUCache<number, KnowledgeResponse>(KNOWLEDGE_CACHE_MAX)

/**
 * 内部: 调方法前 console.debug 调试日志.
 * Phase 4+ 接 telemetry hook 时替换为 dispatchEvent.
 */
function debugLog(method: string, args: unknown): void {
  if (typeof console !== 'undefined' && console.debug) {
    // eslint-disable-next-line no-console
    console.debug(`[KnowledgeService] ${method}`, args)
  }
}

/**
 * 内部: knowledgeId 合法校验.
 * Phase 4-A 复用同样的 4 重检查, 集中在一处.
 */
function isValidKnowledgeId(raw: unknown): raw is number {
  return typeof raw === 'number'
    && Number.isFinite(raw)
    && Number.isInteger(raw)
    && raw > 0
}

/**
 * Phase 4-B: 业务方法 (激活 Phase 4-A 留口的 cacheLookup + getManyKnowledge).
 */
export const knowledgeService = {
  /**
   * Phase 4-A: 列出左侧"知识库分类".
   * Phase 4-B: 仍透传 (categories 列表短, cache 收益小).
   */
  async getCategories(): Promise<ApiResult<DynamicCategory[]>> {
    debugLog('getCategories', null)
    return knowledgeApi.getCategories()
  },

  /**
   * Phase 4-A: 文档列表.
   * Phase 4-B: 仍透传 (列表 cache 命中率低, 留给 Phase 4+ 接入 typed query cache).
   */
  async listKnowledge(
    opts: Parameters<typeof knowledgeApi.listKnowledge>[0] = {}
  ): Promise<ApiResult<KnowledgeList>> {
    debugLog('listKnowledge', opts)
    return knowledgeApi.listKnowledge(opts)
  },

  /**
   * Phase 4-B: 文档详情 + LRU 缓存.
   *
   * 流程:
   *   1. 校验 id (失败: 不调 IPC, 返回 INVALID_INPUT)
   *   2. cache.get(id) -> 命中: 立即返回 (无 IPC)
   *   3. cache miss: 调 api.getKnowledge(id)
   *   4. 成功: cache.set + 返回 result
   *   5. 失败: 不污染 cache, 返回 result (上层 UI 显示 error)
   */
  async getKnowledge(id: number): Promise<ApiResult<KnowledgeResponse>> {
    debugLog('getKnowledge', { id })

    if (!isValidKnowledgeId(id)) {
      return {
        ok: false,
        error: {
          code: 'INVALID_INPUT',
          message: `getKnowledge: 无效 knowledgeId (${String(id)})`
        }
      }
    }

    // 1. cache hit
    const cached = knowledgeCache.get(id)
    if (cached !== undefined) {
      debugLog('getKnowledge.cacheHit', { id })
      return { ok: true, data: cached }
    }

    // 2. cache miss -> fetch
    const result = await knowledgeApi.getKnowledge(id)
    if (result.ok) {
      // 3. success: set cache (LRU 自动淘汰)
      knowledgeCache.set(id, result.data)
    }
    // 失败: 不 set cache, 不影响下次重试
    return result
  },

  /**
   * Phase 4-A: 语义搜索.
   * Phase 4-B: 仍透传 (Phases 3+ 接 RAG 时再考虑 cache 结果集).
   */
  async semanticSearch(
    opts: Parameters<typeof knowledgeApi.semanticSearch>[0]
  ): Promise<ApiResult<KnowledgeSearchResult[]>> {
    debugLog('semanticSearch', opts)
    return knowledgeApi.semanticSearch(opts)
  },

  /**
   * Phase 4-B NEW: 批量拉取多个 knowledge.
   *
   * 流程:
   *   1. dedup (Set)
   *   2. invalid id 过滤
   *   3. partial-cache: 已有走 cache, 缺失走 API
   *   4. Promise.allSettled 并行 API 拉取
   *   5. 缓存成功项 (失败不污染, 同 getKnowledge 语义)
   *   6. 按原始 (deduped + filtered) 顺序返回
   *
   * Phase 4-A 留口的 NOT_IMPLEMENTED 替换为真实实现.
   * 排序保持 vs 性能:
   *   - allSettled 拿全部 settled promise, 然后按 ids 索引排序
   *   - 数量大时 (e.g. 50) 并行 fetch 仍可控, LRU 缓存有上界
   *
   * 批大小: 当前无显式限制 (Phase 4+ 视后端限流加 chunked).
   */
  async getManyKnowledge(
    ids: ReadonlyArray<number>
  ): Promise<ApiResult<KnowledgeResponse[]>> {
    debugLog('getManyKnowledge', { inputCount: ids.length })

    if (!Array.isArray(ids) || ids.length === 0) {
      return { ok: true, data: [] }
    }

    // 1. dedup
    const seen = new Set<number>()
    const uniqueIds: number[] = []
    for (const id of ids) {
      if (typeof id === 'number' && seen.size < KNOWLEDGE_CACHE_MAX + 500) {
        // 上界防御: dedup 不应越界 (前端误传 1000 也只 dedup 500)
        if (!seen.has(id)) {
          seen.add(id)
          uniqueIds.push(id)
        }
      }
    }
    debugLog('getManyKnowledge.dedup', { input: ids.length, unique: uniqueIds.length })

    // 2. invalid 过滤
    const validIds: number[] = []
    for (const id of uniqueIds) {
      if (isValidKnowledgeId(id)) validIds.push(id)
    }
    debugLog('getManyKnowledge.validFilter', { unique: uniqueIds.length, valid: validIds.length })

    if (validIds.length === 0) {
      return { ok: true, data: [] }
    }

    // 3. partial-cache lookup
    const cacheResults = new Map<number, KnowledgeResponse>()
    const toFetch: number[] = []
    for (const id of validIds) {
      const cached = knowledgeCache.get(id)
      if (cached !== undefined) {
        cacheResults.set(id, cached)
      } else {
        toFetch.push(id)
      }
    }
    debugLog('getManyKnowledge.cacheSplit', {
      cached: cacheResults.size,
      toFetch: toFetch.length
    })

    // 4. parallel fetch missing
    const fetchResults = await Promise.allSettled(
      toFetch.map((id) => knowledgeApi.getKnowledge(id))
    )

    // 5. write back cache (success only)
    const fetchedResults = new Map<number, KnowledgeResponse>()
    fetchResults.forEach((settled, idx) => {
      const id = toFetch[idx]
      if (id === undefined) return
      if (settled.status === 'fulfilled' && settled.value.ok) {
        knowledgeCache.set(id, settled.value.data)
        fetchedResults.set(id, settled.value.data)
      }
      // 失败丢弃, 不污染 cache (同 getKnowledge)
    })

    // 6. 按原顺序返回 (deduped + valid)
    const ordered: KnowledgeResponse[] = []
    for (const id of validIds) {
      const got = cacheResults.get(id) ?? fetchedResults.get(id)
      if (got !== undefined) ordered.push(got)
    }
    return { ok: true, data: ordered }
  },

  /**
   * Phase 4-B NEW: Citation 预取 / 批量加载.
   *
   * 仅做: 委托 getManyKnowledge(id[]).
   * Phase 4+ 接 RAG / metadata enrichment (e.g. 返回 KnowledgeResponse + chat_metadata).
   *
   * 当前签名: cite list in -> KnowledgeResponse[] out (success 部分, 失败丢弃).
   * 注意:
   *   - 不是 stream chunk 的 hot-path 调用 (Phase 4+ 才接 chat streaming)
   *   - 当前 manual trigger 即可 (e.g. 用户 hover citation)
   */
  async prefetchKnowledgeForCitations(
    citations: ReadonlyArray<StreamCitationEntry>
  ): Promise<ApiResult<KnowledgeResponse[]>> {
    debugLog('prefetchKnowledgeForCitations', { count: citations.length })

    if (!Array.isArray(citations) || citations.length === 0) {
      return { ok: true, data: [] }
    }

    // 抽 knowledgeId + 过滤 invalid (Phase 4-A 复用 getManyKnowledge dedup + valid filter)
    const ids: number[] = []
    for (const c of citations) {
      if (isValidKnowledgeId(c.knowledgeId)) ids.push(c.knowledgeId)
    }
    // 委托给 getManyKnowledge (dedup + 缓存复用)
    return this.getManyKnowledge(ids)
  },

  /**
   * Phase 4-B REALIZED: cache 命中查询.
   * Phase 4-A 永久返 null, Phase 4-B 接 LRU.
   */
  cacheLookup(id: number): KnowledgeResponse | null {
    if (!isValidKnowledgeId(id)) return null
    const v = knowledgeCache.get(id)
    return v !== undefined ? v : null
  },

  /**
   * Phase 4-B REALIZED: listItems (轻量条目, 不含 content 全文).
   * Phase 4-A NOT_IMPLEMENTED -> Phase 4-B 改: 仅返回 cache 内已有项目.
   * 后端 /knowledge/list 轻量 endpoint 不在 Phase 4-B 范围, 这里 cache-only.
   * Phase 4+ 接后端列表 endpoint 时, 这里再加 fetch 路径.
   */
  async listItems(_limit: number): Promise<ApiResult<KnowledgeListItem[]>> {
    // cache 命中返; Phase 4+ 接后端 /knowledge/list 后再加 fetch
    const items: KnowledgeListItem[] = []
    for (const key of knowledgeCache.keys()) {
      const v = knowledgeCache.get(key)
      if (v) items.push(this.toLightItem(v))
    }
    return { ok: true, data: items.slice(0, _limit) }
  },

  /**
   * 辅助: KnowledgeResponse -> KnowledgeListItem (lightweight).
   * Phase 4-B 内部用, 不导出.
   */
  toLightItem(r: KnowledgeResponse): KnowledgeListItem {
    return {
      id: r.id,
      title: r.title,
      category: r.category,
      tags: r.tags,
      key_concepts: r.key_concepts,
      related_topics: r.related_topics,
      knowledge_type: r.knowledge_type,
      source: r.source,
      source_type: r.source_type,
      summary: r.summary,
      snippet: null,
      analysis_status: r.analysis_status,
      quality_score: r.quality_score,
      needs_review: r.needs_review,
      topic: r.topic,
      created_by: r.created_by,
      created_at: r.created_at,
      updated_at: r.updated_at,
      thumbnail_url: r.thumbnail_url,
      image_count: r.image_count,
      file_path: r.file_path,
      file_name: r.file_name,
      file_type: r.file_type,
      meta: r.meta
    }
  },

  /**
   * Phase 4-B: 调试 / 测试 / 主动清空.
   * 不暴露给 renderer; 仅供 Phase 4+ 接入 logout / user 切换.
   */
  _internal: {
    cacheSize: () => knowledgeCache.size(),
    cacheKeys: () => knowledgeCache.keys(),
    clearCache: () => knowledgeCache.clear(),
    /** 测试 / 维护: 把已知最大 cache 容量曝出 (供 Phase 4+ metrics) */
    maxCacheSize: KNOWLEDGE_CACHE_MAX
  }
}

/**
 * 低层 API gateway 接口签名 (Phase 4+ DI 留给测试拦截).
 */
export const _internal = { apiModule: knowledgeApi }
