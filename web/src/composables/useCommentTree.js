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
  function buildCommentTree(comments) {
    if (!comments || comments.length === 0) {
      return { top: [], byId: {} }
    }
    const byId = {}
    for (const c of comments) {
      byId[c.id] = { ...c, replies: [] }
    }
    const top = []
    for (const c of comments) {
      const node = byId[c.id]
      if (c.parent_comment_id && byId[c.parent_comment_id]) {
        byId[c.parent_comment_id].replies.push(node)
      } else {
        // 孤儿 → 顶层 (避免数据丢失)
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