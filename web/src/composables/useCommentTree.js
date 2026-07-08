/**
 * useCommentTree.js — v2 PR6-P5 评论嵌套 (threading) composable
 *
 * 提供:
 * - buildCommentTree(comments): flat list → 嵌套结构
 * - MAX_COMMENT_DEPTH = 2 (与后端一致)
 * - canReply(comment): 判断评论是否还能被回复
 *
 * 后端返回的 comments 字段:
 * - id / content / user_id / user_name / mentions
 * - parent_comment_id: int | null
 * - thread_depth: 0/1/2
 * - reply_count: int
 *
 * 树形结构:
 * {
 *   top: [
 *     { id, content, ..., replies: [{ id, ..., replies: [...] }] },
 *     ...
 *   ],
 *   byId: { id: comment }
 * }
 */
import { computed } from 'vue'

export const MAX_COMMENT_DEPTH = 2

export function useCommentTree() {
  // P2-7 fix (2026-07-08): cycle 检测. 之前 line 41 push 节点到 parent.replies
  // 不检测祖先链, 恶意/损坏数据 (A.parent=B, B.parent=A) 会让 template 递归渲染
  // → 栈溢出 + 浏览器挂起. 修复: 追溯祖先链检测 cycle, 把 cycle 节点放顶层.
  // 防御性 maxDepth 限 100 (实际 MAX_COMMENT_DEPTH=2, 超过视为异常).
  const _CYCLE_MAX_DEPTH = 100

  function _detectCycles(byId) {
    // 返 inCycle Set: 这些节点放顶层 (不进入 parent.replies, 避免无限递归).
    // 用 ancestor chain 追溯: 对每个节点, 顺着 parent 链走 maxDepth 步,
    // 任何时候遇到自己/重复节点 → 标记 cycle.
    const inCycle = new Set()
    for (const id of Object.keys(byId)) {
      const visited = new Set()
      let cur = byId[id]?.parent_comment_id
      let depth = 0
      while (cur && depth < _CYCLE_MAX_DEPTH) {
        if (cur === Number(id) || cur === id) {
          // 直接回到自己: A→B→A
          inCycle.add(Number(id))
          break
        }
        if (visited.has(cur)) {
          // 间接 cycle: A→B→C→A, 链中重复访问同一节点
          inCycle.add(Number(id))
          break
        }
        visited.add(cur)
        cur = byId[cur]?.parent_comment_id
        depth++
      }
      if (depth >= _CYCLE_MAX_DEPTH) {
        // 超过 maxDepth 视为异常 (恶意深嵌套), 放顶层
        inCycle.add(Number(id))
      }
    }
    return inCycle
  }

  function buildCommentTree(comments) {
    if (!comments || comments.length === 0) {
      return { top: [], byId: {} }
    }
    const byId = {}
    for (const c of comments) {
      byId[c.id] = { ...c, replies: [] }
    }
    // P2-7 fix: 先检测 cycle 节点, 构建树时放顶层
    const inCycle = _detectCycles(byId)
    const top = []
    for (const c of comments) {
      const node = byId[c.id]
      if (c.parent_comment_id && byId[c.parent_comment_id] && !inCycle.has(c.id)) {
        byId[c.parent_comment_id].replies.push(node)
      } else {
        // 孤儿 / cycle → 顶层 (避免数据丢失 + 防止无限递归)
        top.push(node)
      }
    }
    return { top, byId }
  }

  function canReply(comment) {
    if (!comment) return false
    return (comment.thread_depth ?? 0) < MAX_COMMENT_DEPTH
  }

  function getTotalCount(comments) {
    if (!comments) return 0
    return comments.length
  }

  function countRepliesRecursive(comment) {
    if (!comment || !comment.replies || comment.replies.length === 0) return 0
    let count = comment.replies.length
    for (const r of comment.replies) {
      count += countRepliesRecursive(r)
    }
    return count
  }

  return {
    buildCommentTree,
    canReply,
    getTotalCount,
    countRepliesRecursive,
    MAX_COMMENT_DEPTH,
  }
}

export default useCommentTree