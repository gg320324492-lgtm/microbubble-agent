// Knowledge Service Layer (Phase 4-A).
//
// 业务逻辑层, 介于 store / view (上层) 与 api/knowledge (IPC gateway, 下层) 之间.
//
// 架构:
//   KnowledgeView
//     ↓ 调 store action
//   stores/knowledge.ts (Pinia 状态 + 缓存)
//     ↓ 调 service
//   services/knowledge.service.ts (业务方法, 日志/钩子/未来 caching)
//     ↓ 调 api
//   api/knowledge.ts (IPC + payload 包装)
//     ↓ window.api.api.request
//   main/api.service.request (Bearer + 单飞 refresh)
//     ↓ fetch
//   FastAPI /api/v1/knowledge/*
//
// Phase 4-A 范围:
//   - 单层服务, 每个方法一行到三行实现
//   - console.debug 调试日志 (Phase 4+ 接 telemetry hook)
//   - Citation 模块入口: getKnowledgeForCitation(id)
//     (Phase 4-A 与 getKnowledge 等价; Phase 4+ 加入 batch / 缓存 / 与 citation 协议联动的 metadata)
//
// 不在范围 (Phase 4+ / Phase 3+):
//   - RAG / Retriever / Embedding / Backend schema / Agent Tool
//   - Cache (lru / ttl / IndexedDB) — Phase 4+
//   - 批量拉取 — getManyKnowledge() 留口 Phase 4+
//   - 跨域 (Phase 4+ 多端同步)

import * as knowledgeApi from '../api/knowledge'
import type {
  DynamicCategory,
  KnowledgeList,
  KnowledgeResponse,
  KnowledgeSearchResult,
  KnowledgeListItem
} from '@shared/knowledge-types'
import type { ApiRequestPayload, ApiResult } from '@shared/preload-api'
import type { StreamCitationEntry } from '@shared/chat-types'

/**
 * 内部: 调方法前 console.debug 调试日志.
 * Phase 4+ 接 telemetry hook 时替换为 dispatchEvent.
 *
 * 注: 始终 console.debug 不上 console.log, 生产环境 output 不见 (Vite prod 模式自动剔除).
 */
function debugLog(method: string, args: unknown): void {
  if (typeof console !== 'undefined' && console.debug) {
    // eslint-disable-next-line no-console
    console.debug(`[KnowledgeService] ${method}`, args)
  }
}

/**
 * Phase 4-A: Knowledge 业务方法.
 * 服务是单例导出 (无状态). 没有 registry / DI / 缓存;
 * 那样会让 Phase 4-A 过度复杂, Phase 4+ 加.
 */
export const knowledgeService = {
  /**
   * 列出左侧"知识库分类".
   */
  async getCategories(): Promise<ApiResult<DynamicCategory[]>> {
    debugLog('getCategories', null)
    return knowledgeApi.getCategories()
  },

  /**
   * 文档列表 (支持 category / keyword / page / pageSize).
   */
  async listKnowledge(
    opts: Parameters<typeof knowledgeApi.listKnowledge>[0] = {}
  ): Promise<ApiResult<KnowledgeList>> {
    debugLog('listKnowledge', opts)
    return knowledgeApi.listKnowledge(opts)
  },

  /**
   * 单文档详情.
   */
  async getKnowledge(id: number): Promise<ApiResult<KnowledgeResponse>> {
    debugLog('getKnowledge', { id })
    return knowledgeApi.getKnowledge(id)
  },

  /**
   * 语义搜索 (Phase 2 留口, Phase 4-A 透传).
   */
  async semanticSearch(
    opts: Parameters<typeof knowledgeApi.semanticSearch>[0]
  ): Promise<ApiResult<KnowledgeSearchResult[]>> {
    debugLog('semanticSearch', opts)
    return knowledgeApi.semanticSearch(opts)
  },

  /**
   * Phase 4-A NEW: Citation 引用卡片详情上下文加载.
   *
   * 当前与 getKnowledge(id) 等价 (单文档拉取).
   * Phase 4+ 计划:
   *   - 入参多个 citation id 时批量 (getManyKnowledge) 一次 API 拉取
   *   - 命中本地 LRU cache
   *   - 与 citation metadata 联动 (返回 KnowledgeResponse + citation-aware fields)
   *
   * 当前: 入参是单 id, 内部 delegate; 不修改返回值.
   * 边界: id ≤ 0 / NaN / 非 number 一律返回 error (不抛).
   */
  async getKnowledgeForCitation(
    citation: StreamCitationEntry
  ): Promise<ApiResult<KnowledgeResponse>> {
    debugLog('getKnowledgeForCitation', { knowledgeId: citation.knowledgeId })
    if (typeof citation.knowledgeId !== 'number' || !Number.isFinite(citation.knowledgeId) || citation.knowledgeId <= 0) {
      return {
        ok: false,
        error: {
          code: 'INVALID_INPUT',
          message: `getKnowledgeForCitation: 无效 knowledgeId (${String(citation.knowledgeId)})`
        }
      }
    }
    return knowledgeApi.getKnowledge(citation.knowledgeId)
  },

  /**
   * Phase 4+ 留口: 批量拉取多个 id.
   * 当前抛错, 不允许误调.
   */
  async getManyKnowledge(_ids: number[]): Promise<ApiResult<KnowledgeResponse[]>> {
    return {
      ok: false,
      error: {
        code: 'NOT_IMPLEMENTED',
        message: 'getManyKnowledge Phase 4+ 待实现 (当前 Phase 4-A 不支持批量)'
      }
    }
  },

  /**
   * Phase 4+ 留口: 由 Citation 提供的 knowledgeId 推导本地缓存命中.
   * 当前永远返回 null (未命中); Phase 4+ 接 LRU.
   */
  cacheLookup(_id: number): KnowledgeResponse | null {
    return null
  },

  /**
   * Phase 4+ 留口: 列出 KnowledgeListItem (轻量, 用于 batch 列表渲染).
   * 当前不存在 phase 2 backend endpoint; Phase 4+ 接 /knowledge/list 轻量 endpoint.
   */
  async listItems(_limit: number): Promise<ApiResult<KnowledgeListItem[]>> {
    return {
      ok: false,
      error: { code: 'NOT_IMPLEMENTED', message: 'listItems Phase 4+ 待实现' }
    }
  }
}

/**
 * 低层 API gateway 接口签名 (Phase 4+ DI 用于测试):
 *   import * as apiModule from '../api/knowledge'
 *   vi.mock('../api/knowledge')
 * 暴露给测试拦截使用.
 */
export const _internal = { apiModule: knowledgeApi }

/**
 * Phase 4+ 留口: ApiRequestPayload 暴露给业务组合路径.
 * 当前未直接用, 留作 service 内部临时构造请求 (例如 batch).
 */
export type { ApiRequestPayload }
