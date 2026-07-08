/**
 * useCommentTree.test.js — v2 PR6-P5 threading 工具测试
 */
import { describe, it, expect } from 'vitest'
import { useCommentTree, MAX_COMMENT_DEPTH } from '@/composables/useCommentTree'

describe('useCommentTree', () => {
  const { buildCommentTree, canReply, countRepliesRecursive } = useCommentTree()

  describe('buildCommentTree', () => {
    it('空 comments → 空 tree', () => {
      const { top, byId } = buildCommentTree([])
      expect(top).toEqual([])
      expect(byId).toEqual({})
    })

    it('null/undefined → 空 tree', () => {
      expect(buildCommentTree(null).top).toEqual([])
      expect(buildCommentTree(undefined).top).toEqual([])
    })

    it('全顶层评论 (3 条) → top 数组', () => {
      const comments = [
        { id: 1, content: 'a', parent_comment_id: null, thread_depth: 0 },
        { id: 2, content: 'b', parent_comment_id: null, thread_depth: 0 },
        { id: 3, content: 'c', parent_comment_id: null, thread_depth: 0 },
      ]
      const { top } = buildCommentTree(comments)
      expect(top).toHaveLength(3)
      expect(top.map((c) => c.id)).toEqual([1, 2, 3])
      expect(top[0].replies).toEqual([])
    })

    it('1 顶层 + 1 子 → tree 结构', () => {
      const comments = [
        { id: 1, content: 'top', parent_comment_id: null, thread_depth: 0 },
        { id: 2, content: 'reply', parent_comment_id: 1, thread_depth: 1 },
      ]
      const { top, byId } = buildCommentTree(comments)
      expect(top).toHaveLength(1)
      expect(top[0].id).toBe(1)
      expect(top[0].replies).toHaveLength(1)
      expect(top[0].replies[0].id).toBe(2)
      expect(byId[1].replies).toHaveLength(1)
      expect(byId[2].replies).toEqual([])
    })

    it('3 层嵌套 (top → reply → reply_of_reply) → 递归树', () => {
      const comments = [
        { id: 1, content: 'top', parent_comment_id: null, thread_depth: 0 },
        { id: 2, content: 'r1', parent_comment_id: 1, thread_depth: 1 },
        { id: 3, content: 'r2', parent_comment_id: 2, thread_depth: 2 },
      ]
      const { top } = buildCommentTree(comments)
      expect(top).toHaveLength(1)
      expect(top[0].replies).toHaveLength(1)
      expect(top[0].replies[0].replies).toHaveLength(1)
      expect(top[0].replies[0].replies[0].id).toBe(3)
    })

    it('多顶层 + 多子混合', () => {
      const comments = [
        { id: 1, content: 'top1', parent_comment_id: null, thread_depth: 0 },
        { id: 2, content: 'top2', parent_comment_id: null, thread_depth: 0 },
        { id: 3, content: 'reply-of-1', parent_comment_id: 1, thread_depth: 1 },
        { id: 4, content: 'reply-of-2', parent_comment_id: 2, thread_depth: 1 },
      ]
      const { top } = buildCommentTree(comments)
      expect(top).toHaveLength(2)
      expect(top[0].replies).toHaveLength(1)
      expect(top[1].replies).toHaveLength(1)
    })

    it('孤儿 (parent 不存在) → 视为顶层, 避免数据丢失', () => {
      const comments = [
        { id: 1, content: 'normal', parent_comment_id: null, thread_depth: 0 },
        { id: 2, content: 'orphan', parent_comment_id: 9999, thread_depth: 1 },
      ]
      const { top } = buildCommentTree(comments)
      expect(top).toHaveLength(2)
    })

    it('不 mutate 原数组', () => {
      const comments = [
        { id: 1, content: 'top', parent_comment_id: null, thread_depth: 0 },
      ]
      const originalStr = JSON.stringify(comments)
      buildCommentTree(comments)
      expect(JSON.stringify(comments)).toBe(originalStr)
      expect(comments[0].replies).toBeUndefined()
    })

    it('P2-7 修复: 直接循环 (A→B→A) 不会栈溢出, 2 节点都放顶层', () => {
      // 恶意/损坏数据: A.parent=B, B.parent=A
      const comments = [
        { id: 1, content: 'A', parent_comment_id: 2, thread_depth: 0 },
        { id: 2, content: 'B', parent_comment_id: 1, thread_depth: 1 },
      ]
      const { top, byId } = buildCommentTree(comments)
      // 关键: 不应栈溢出 (修复前会无限递归)
      expect(top).toHaveLength(2)
      // 2 节点都放顶层
      expect(byId[1].replies).toEqual([])
      expect(byId[2].replies).toEqual([])
    })

    it('P2-7 修复: 间接循环 (A→B→C→A) → 3 节点都放顶层', () => {
      const comments = [
        { id: 1, content: 'A', parent_comment_id: 3, thread_depth: 0 },
        { id: 2, content: 'B', parent_comment_id: 1, thread_depth: 0 },
        { id: 3, content: 'C', parent_comment_id: 2, thread_depth: 0 },
      ]
      const { top, byId } = buildCommentTree(comments)
      // 3 节点都在顶层
      expect(top).toHaveLength(3)
      expect(byId[1].replies).toEqual([])
      expect(byId[2].replies).toEqual([])
      expect(byId[3].replies).toEqual([])
    })

    it('P2-7 修复: 正常嵌套 + cycle 节点混合 → 正常节点保留嵌套, cycle 节点放顶层', () => {
      // 场景: 1 个正常嵌套 + 1 个 cycle 独立
      const comments = [
        { id: 1, content: '正常父', parent_comment_id: null, thread_depth: 0 },
        { id: 2, content: '正常子', parent_comment_id: 1, thread_depth: 1 },
        // cycle 独立
        { id: 3, content: 'cycle A', parent_comment_id: 4, thread_depth: 0 },
        { id: 4, content: 'cycle B', parent_comment_id: 3, thread_depth: 0 },
      ]
      const { top, byId } = buildCommentTree(comments)
      // 正常嵌套: id 1 在顶层, id 2 在 id 1.replies
      expect(top).toHaveLength(3)  // id 1, 3, 4 都在顶层 (cycle 节点)
      expect(byId[1].replies).toHaveLength(1)
      expect(byId[1].replies[0].id).toBe(2)
      // cycle 节点不放进 parent
      expect(byId[3].replies).toEqual([])
      expect(byId[4].replies).toEqual([])
    })
  })

  describe('canReply', () => {
    it('depth=0 → 可回复', () => {
      expect(canReply({ thread_depth: 0 })).toBe(true)
    })
    it('depth=1 → 可回复', () => {
      expect(canReply({ thread_depth: 1 })).toBe(true)
    })
    it('depth=2 → 不可回复 (硬上限)', () => {
      expect(canReply({ thread_depth: 2 })).toBe(false)
    })
    it('depth=undefined → 当 depth=0 处理 (默认顶层可回复)', () => {
      expect(canReply({})).toBe(true)
    })
    it('null → false', () => {
      expect(canReply(null)).toBe(false)
    })
  })

  describe('countRepliesRecursive', () => {
    it('无 replies → 0', () => {
      expect(countRepliesRecursive({ id: 1, replies: [] })).toBe(0)
      expect(countRepliesRecursive({ id: 1 })).toBe(0)
    })
    it('1 直接子 → 1', () => {
      expect(countRepliesRecursive({ id: 1, replies: [{ id: 2, replies: [] }] })).toBe(1)
    })
    it('多代子评论 → 累加', () => {
      const tree = {
        id: 1, replies: [
          { id: 2, replies: [
            { id: 3, replies: [] },
            { id: 4, replies: [] },
          ] },
          { id: 5, replies: [] },
        ],
      }
      expect(countRepliesRecursive(tree)).toBe(4)
    })
  })

  describe('MAX_COMMENT_DEPTH 常量', () => {
    it('导出为 2 (允许 depth 0/1/2 共 3 层)', () => {
      expect(MAX_COMMENT_DEPTH).toBe(2)
    })
  })
})