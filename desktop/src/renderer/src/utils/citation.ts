// Citation 纯前端 helpers (Phase 3-C2).
//
// 不依赖 Vue / DOM / 任何前端层. 纯函数, 可被 store / component / test 复用.
//
// Phase 3-C2 范围:
//   - sortCitations: 按 score desc 稳定排序; 无 score 保原序
//   - dedupCitations: 按 knowledgeId 去重 (保第一次出现)
//   - toPercent: 0..1 -> "N%" 字符串
//
// 不在范围 (Phase 3+ RAG / Retriever):
//   - 远程获取 (一切网络操作)
//   - 后端 schema 假设 (仅消费 Phase 3-B0 frozen StreamCitationEntry)
//   - 排序加权 (Phase 3-C2 仅 score, 不引入 recent/source/hot 等启发式)

import type { StreamCitationEntry } from '@shared/chat-types'

/**
 * 检查 citation 是否有有效 score (0..1 数字).
 * 不接受 NaN / null / undefined / 越界值.
 */
export function hasValidScore(c: StreamCitationEntry): c is StreamCitationEntry & { score: number } {
  return typeof c.score === 'number'
    && Number.isFinite(c.score)
    && c.score >= 0
    && c.score <= 1
}

/**
 * 按 score desc 排序 (Phase 3-C2).
 *
 * 规则:
 *   1. 有 score 的 citation 排在前面 (按 score 降序)
 *   2. 无 score 的 citation 排在后面 (按原顺序; ES2019 stable sort 保证)
 *   3. 不会修改入参 (返回新数组)
 *
 * 用于: 渲染时一次性 sortCitationArray(citations), 给出最终顺序.
 * 不修改 stream 协议.
 */
export function sortCitations<T extends StreamCitationEntry>(citations: ReadonlyArray<T>): T[] {
  const arr = [...citations]
  arr.sort((a, b) => {
    const aHas = hasValidScore(a)
    const bHas = hasValidScore(b)
    if (aHas && !bHas) return -1
    if (!aHas && bHas) return 1
    if (!aHas && !bHas) return 0
    // both have valid score
    return (b as { score: number }).score - (a as { score: number }).score
  })
  return arr
}

/**
 * 按 knowledgeId 去重 (Phase 3-C2).
 *
 * 规则:
 *   - 第一次出现保留, 后续丢弃
 *   - 跳过 knowledgeId 非法 (非 number) 的 entry
 *   - 不修改入参 (返回新数组)
 */
export function dedupCitations<T extends StreamCitationEntry>(citations: ReadonlyArray<T>): T[] {
  const seen = new Set<number>()
  const out: T[] = []
  for (const c of citations) {
    if (typeof c.knowledgeId !== 'number' || !Number.isFinite(c.knowledgeId)) continue
    if (seen.has(c.knowledgeId)) continue
    seen.add(c.knowledgeId)
    out.push(c)
  }
  return out
}

/**
 * 0..1 score 转 "N%" 字符串 (Phase 3-C2).
 * 无效输入返回 null (调用方应隐藏 score UI).
 *
 * 注: Math.round(0.005 * 100) = 1, 这是预期行为 (向上对齐可读).
 */
export function toPercent(score: unknown): string | null {
  if (typeof score !== 'number' || !Number.isFinite(score)) return null
  if (score < 0 || score > 1) return null
  return `${Math.round(score * 100)}%`
}

/**
 * 综合: sort + dedup. Phase 3-C2 渲染管线一条龙.
 * (Step 5 测试覆盖)
 */
export function normalizeCitations<T extends StreamCitationEntry>(citations: ReadonlyArray<T>): T[] {
  return sortCitations(dedupCitations(citations))
}
