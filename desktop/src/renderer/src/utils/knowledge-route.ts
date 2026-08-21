// Knowledge route helpers (Phase 3-D: Citation -> KnowledgeDetail 路由闭环).
//
// 纯函数, 可被 view 组件 / test 复用.
//
// Phase 3-D 范围:
//   - validateKnowledgeId: 输入校验 (number + positive integer)
//   - buildKnowledgePath: 路由描述符构造 (含 from=chat query)
//
// 不在范围 (Phase 3+ RAG / Phase 4+ Knowledge API):
//   - 调用后端获取 knowledge detail
//   - Knowledge service 注册 / 缓存
//   - 跨 window 的 session 持久化
//
// 安全约束 (Phase 3-B0 §11 协议冻结继承):
//   - knowledgeId 是后端约定的 number (record id), renderer 不可信, 必须校验
//   - 不通过 router.push 写入未校验的 query 防止 0/-1/NaN/XSS

import type { RouteLocationRaw } from 'vue-router'

/**
 * 校验 knowledgeId (CitationCard click 来源).
 * Phase 3-D:
 *   - 必须 typeof === 'number'
 *   - 必须 Number.isFinite
 *   - 必须 > 0 (DB id 从 1 开始)
 *   - 必须 Number.isInteger (整数)
 * 非法 -> 返回 null, 调用方停止跳转.
 */
export function validateKnowledgeId(raw: unknown): number | null {
  if (typeof raw !== 'number') return null
  if (!Number.isFinite(raw)) return null
  if (!Number.isInteger(raw)) return null
  if (raw <= 0) return null
  return raw
}

/**
 * 校验 raw query id (router 接收来自 URL 查询参数, 是 string | null).
 * 安全转换: string -> number -> validateKnowledgeId, 失败 null.
 */
export function validateKnowledgeIdFromQuery(raw: unknown): number | null {
  if (raw === undefined || raw === null) return null
  if (typeof raw === 'number') return validateKnowledgeId(raw)
  if (typeof raw === 'string') {
    const n = Number(raw)
    return validateKnowledgeId(n)
  }
  return null
}

export interface CitationOrigin {
  /** 'chat' = citation click 自 ChatView; 其它来源 Phase 4+ 接入 */
  source: 'chat' | 'other'
}

/**
 * 构造 knowledge-detail 路由描述符.
 *
 * 路由: { name: 'knowledge-detail', query: { id, from? } }
 *
 * @param id 已通过 validateKnowledgeId 校验的合法 id
 * @param origin 'chat' 时追加 query.from='chat' 给 back 按钮判断
 */
export function buildKnowledgePath(
  id: number,
  origin: CitationOrigin = { source: 'other' }
): RouteLocationRaw {
  const query: Record<string, string | number> = { id }
  if (origin.source === 'chat') {
    query['from'] = 'chat'
  }
  return {
    name: 'knowledge-detail',
    query
  }
}

/**
 * 判断 KnowledgeDetail 当前是否来自 citation click (chat 上下文).
 * 用于 back 按钮 -> 显示 "← 返回 Chat" 走 router.back().
 *
 * Phase 3-D: 仅识别 from=chat; 其它 source 走默认 "返回知识库".
 */
export function cameFromChat(query: Record<string, unknown> | unknown): boolean {
  if (!query || typeof query !== 'object') return false
  const from = (query as Record<string, unknown>)['from']
  return from === 'chat'
}

/**
 * 统一入口: 校验 + 构造 path. 用于 ChatView.onCitationKnowledgeOpen:
 *   const route = safeKnowledgePush(id, { source: 'chat' })
 *   if (route) router.push(route) else 不跳转
 *
 * 默认 origin = { source: 'other' }; 调用方需显式声明 'chat' 才能加 from=chat.
 * (Phase 3-D: 强制显式, 避免遗漏 source 导致 back 按钮误识别.)
 */
export function safeKnowledgePush(
  rawId: unknown,
  origin: CitationOrigin = { source: 'other' }
): RouteLocationRaw | null {
  const id = validateKnowledgeId(rawId)
  if (id === null) return null
  return buildKnowledgePath(id, origin)
}
