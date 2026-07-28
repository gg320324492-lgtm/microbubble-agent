/**
 * useFileCommentsDesktop.test.js — W85 B-2 P1-1 Step 1 thin-shell 委派测试
 *
 * 2026-07-29 W85 第 1 批 B-2 P1 冗余重构 batch 3.
 *
 * 覆盖:
 * 1. 核心 CRUD (listComments / postComment / postReply / updateComment /
 *    deleteComment / toggleResolved) 100% 委派 useFileComments base — 引用同一函数
 * 2. desktop-only 数据层: startEditComment / cancelEditComment / switchTab
 * 3. filteredComments 委派 base.filterByTab
 * 4. @deprecated UI wrapper 兼容层仍导出且可调 (W86 Step 2 前不破坏老消费方)
 * 5. fileId 切换 watch → editing/tab state reset
 *
 * Mock 策略: mock useFileComments 返回 spy 集合, 验证 thin-shell 是纯委派.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { ref, computed, nextTick } from 'vue'

// element-plus ElMessage mock (deprecated wrapper 用)
vi.mock('element-plus', () => ({
  ElMessage: {
    success: vi.fn(),
    error: vi.fn(),
    info: vi.fn(),
  },
}))

// axios mock (fetchFileMeta / batchResolveMembers 用)
vi.mock('axios', () => ({
  default: {
    get: vi.fn(),
    post: vi.fn(),
    patch: vi.fn(),
    delete: vi.fn(),
  },
}))

// useFileComments base mock — thin-shell 委派验证核心
const baseMock = {
  comments: ref([]),
  loading: ref(false),
  posting: ref(false),
  error: ref(null),
  total: computed(() => 0),
  openCount: computed(() => 0),
  resolvedCount: computed(() => 0),
  listComments: vi.fn().mockResolvedValue([]),
  postComment: vi.fn().mockResolvedValue({}),
  postReply: vi.fn().mockResolvedValue({}),
  deleteComment: vi.fn().mockResolvedValue(undefined),
  updateComment: vi.fn().mockResolvedValue({}),
  toggleResolved: vi.fn().mockResolvedValue(undefined),
  filterByTab: vi.fn(() => []),
}
vi.mock('@/composables/useFileComments', () => ({
  useFileComments: vi.fn(() => baseMock),
}))

import axios from 'axios'
import { ElMessage } from 'element-plus'
import { useFileComments } from '@/composables/useFileComments'
import { useFileCommentsDesktop } from '@/composables/useFileCommentsDesktop'

describe('useFileCommentsDesktop (W85 B-2 P1-1 thin-shell 委派)', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  describe('核心 CRUD 委派 (场景 1)', () => {
    it('返回的核心 action 与 base 是同一引用 (纯委派, 无重复实现)', () => {
      const d = useFileCommentsDesktop(1)
      expect(useFileComments).toHaveBeenCalledTimes(1)
      expect(d.listComments).toBe(baseMock.listComments)
      expect(d.postComment).toBe(baseMock.postComment)
      expect(d.postReply).toBe(baseMock.postReply)
      expect(d.updateComment).toBe(baseMock.updateComment)
      expect(d.deleteComment).toBe(baseMock.deleteComment)
      expect(d.toggleResolved).toBe(baseMock.toggleResolved)
    })

    it('返回的核心 state 与 base 是同一引用', () => {
      const d = useFileCommentsDesktop(1)
      expect(d.comments).toBe(baseMock.comments)
      expect(d.loading).toBe(baseMock.loading)
      expect(d.posting).toBe(baseMock.posting)
      expect(d.error).toBe(baseMock.error)
      expect(d.total).toBe(baseMock.total)
      expect(d.openCount).toBe(baseMock.openCount)
      expect(d.resolvedCount).toBe(baseMock.resolvedCount)
    })
  })

  describe('desktop-only 数据层 (场景 2)', () => {
    it('startEditComment 设置 editingCommentId + editDraft', () => {
      const d = useFileCommentsDesktop(1)
      d.startEditComment({ id: 42, content: '老内容' })
      expect(d.editingCommentId.value).toBe(42)
      expect(d.editDraft.value).toBe('老内容')
      d.cancelEditComment()
      expect(d.editingCommentId.value).toBe(null)
      expect(d.editDraft.value).toBe('')
    })

    it('switchTab 更新 activeTab', () => {
      const d = useFileCommentsDesktop(1)
      expect(d.activeTab.value).toBe('open')
      d.switchTab('resolved')
      expect(d.activeTab.value).toBe('resolved')
    })

    it('fetchFileMeta 走 axios GET /drive/files/{fid}', async () => {
      axios.get.mockResolvedValue({ data: { id: 7, title: 'f', owner_id: 3 } })
      const d = useFileCommentsDesktop(7)
      const meta = await d.fetchFileMeta()
      expect(axios.get).toHaveBeenCalledWith(
        '/api/v1/drive/files/7',
        expect.objectContaining({ headers: expect.any(Object) }),
      )
      expect(meta.owner_id).toBe(3)
    })
  })

  describe('filteredComments 委派 base.filterByTab (场景 3)', () => {
    it('activeTab 切换后 filterByTab 以新 tab 调用', () => {
      const d = useFileCommentsDesktop(1)
      // 触发 computed
      void d.filteredComments.value
      expect(baseMock.filterByTab).toHaveBeenCalledWith('open')
      d.switchTab('all')
      void d.filteredComments.value
      expect(baseMock.filterByTab).toHaveBeenCalledWith('all')
    })
  })

  describe('@deprecated UI wrapper 兼容层 (场景 4, W86 Step 2 前保留)', () => {
    it('onEditComment 委派 base.updateComment + 成功清空 editing 状态', async () => {
      const d = useFileCommentsDesktop(1)
      d.startEditComment({ id: 5, content: 'x' })
      await d.onEditComment(5, '新内容')
      expect(baseMock.updateComment).toHaveBeenCalledWith(5, '新内容')
      expect(ElMessage.success).toHaveBeenCalled()
      expect(d.editingCommentId.value).toBe(null)
    })

    it('onToggleResolved 委派 base.toggleResolved (取反)', async () => {
      const d = useFileCommentsDesktop(1)
      await d.onToggleResolved({ id: 9, resolved: false })
      expect(baseMock.toggleResolved).toHaveBeenCalledWith(9, true)
    })

    it('onDeleteComment 委派 base.deleteComment', async () => {
      const d = useFileCommentsDesktop(1)
      await d.onDeleteComment({ id: 11 })
      expect(baseMock.deleteComment).toHaveBeenCalledWith(11)
    })

    it('onReplyPrefix 返回 @username 前缀', () => {
      const d = useFileCommentsDesktop(1)
      expect(d.onReplyPrefix({ user_name: '张三' })).toBe('@张三 ')
      expect(d.onReplyPrefix({ user_id: 4 })).toBe('@用户 #4 ')
    })
  })

  describe('fileId 切换 reset (场景 5)', () => {
    it('fileId ref 变化 → editing/tab state 重置', async () => {
      const fid = ref(1)
      const d = useFileCommentsDesktop(fid)
      d.startEditComment({ id: 3, content: 'c' })
      d.switchTab('resolved')
      fid.value = 2
      await nextTick()
      expect(d.editingCommentId.value).toBe(null)
      expect(d.editDraft.value).toBe('')
      expect(d.activeTab.value).toBe('open')
    })
  })
})
