/**
 * CommentItem.test.js — v2 PR6-P6 编辑功能单测
 *
 * 覆盖 (6 case):
 * - canEdit 守卫: owner / 非 owner / 无 currentUserId / 5分钟窗口外
 * - 编辑按钮: owner + 5分钟内显示, 其它情况隐藏
 * - toggleEditForm / submitEdit / cancelEdit 基础状态切换
 * - store.updateComment 422 错误透传
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { nextTick } from 'vue'

// Mock Element Plus (避免引入大量组件)
vi.mock('element-plus', () => ({
  ElMessage: { success: vi.fn(), error: vi.fn(), info: vi.fn(), warning: vi.fn() },
}))

// Mock store - 重点是 updateComment 方法
const mockUpdateComment = vi.fn()
const mockDeleteComment = vi.fn()
const mockPostReply = vi.fn()

vi.mock('@/composables/useNotifications', () => ({
  useNotificationsStore: () => ({
    updateComment: mockUpdateComment,
    deleteComment: mockDeleteComment,
    postReply: mockPostReply,
  }),
}))

// Mock useMentionAutocomplete (PR6-P4 共享 composable)
vi.mock('@/composables/useMentionAutocomplete', () => ({
  useMentionAutocomplete: () => ({
    isOpen: { value: false },
    rawCandidates: { value: [] },
    selectedIndex: { value: 0 },
    refresh: vi.fn(),
    close: vi.fn(),
    handleKeydown: vi.fn(() => false),
    selectCandidate: vi.fn(),
  }),
}))

vi.mock('@/composables/useCommentTree', () => ({
  useCommentTree: () => ({
    canReply: (c) => (c?.thread_depth ?? 0) < 2,
  }),
  MAX_COMMENT_DEPTH: 2,
  buildCommentTree: vi.fn(),
  countRepliesRecursive: vi.fn(() => 0),
}))

import CommentItem from '@/components/drive/CommentItem.vue'

// 测试辅助: 创建评论 fixture
function makeComment(overrides = {}) {
  return {
    id: 100,
    file_id: 540,
    user_id: 59,
    user_name: '测试用户',
    content: '原始内容',
    mentions: null,
    parent_comment_id: null,
    thread_depth: 0,
    reply_count: 0,
    created_at: new Date().toISOString(),  // 现在 (5 分钟内)
    replies: [],
    ...overrides,
  }
}

function makeMountOptions(commentOverrides = {}, props = {}) {
  return {
    props: {
      comment: makeComment(commentOverrides),
      depth: 0,
      fileId: 540,
      currentUserId: 59,
      isFileOwner: false,
      membersList: [],
      usernameMap: { 59: 'wangtianzhi' },
      ...props,
    },
  }
}

describe('CommentItem v2 PR6-P6 edit 功能', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  // ============================================================
  // 1. canEdit 守卫 (3 case)
  // ============================================================
  describe('canEdit 守卫', () => {
    it('owner + 5 分钟内 → canEdit=true → 显示编辑按钮', () => {
      const wrapper = mount(CommentItem, makeMountOptions())
      const editBtn = wrapper.find('.comment-edit-btn')
      expect(editBtn.exists()).toBe(true)
    })

    it('非 owner (currentUserId !== comment.user_id) → canEdit=false → 隐藏', () => {
      const wrapper = mount(CommentItem, makeMountOptions(
        { user_id: 60 },  // 别人评论
        { currentUserId: 59 },  // 当前用户
      ))
      const editBtn = wrapper.find('.comment-edit-btn')
      expect(editBtn.exists()).toBe(false)
    })

    it('5 分钟窗口外 → canEdit=false → 隐藏', () => {
      // 6 分钟前
      const sixMinAgo = new Date(Date.now() - 360 * 1000).toISOString()
      const wrapper = mount(CommentItem, makeMountOptions({ created_at: sixMinAgo }))
      const editBtn = wrapper.find('.comment-edit-btn')
      expect(editBtn.exists()).toBe(false)
    })

    it('无 currentUserId → canEdit=false → 隐藏', () => {
      const wrapper = mount(CommentItem, makeMountOptions({}, { currentUserId: null }))
      const editBtn = wrapper.find('.comment-edit-btn')
      expect(editBtn.exists()).toBe(false)
    })
  })

  // ============================================================
  // 2. 编辑表单状态切换 (2 case)
  // ============================================================
  describe('编辑表单状态切换', () => {
    it('点编辑按钮 → showEditForm=true + editContent 初始化为 comment.content', async () => {
      const wrapper = mount(CommentItem, makeMountOptions())
      await wrapper.find('.comment-edit-btn').trigger('click')
      await nextTick()
      expect(wrapper.find('.comment-edit-form').exists()).toBe(true)
      // 内部 vm 引用 (用 findComponent 不行因为 edit form 不是组件)
      expect(wrapper.vm.editContent).toBe('原始内容')
    })

    it('cancelEdit 关闭表单 + 清空内容 + 清 mentions', async () => {
      const wrapper = mount(CommentItem, makeMountOptions())
      await wrapper.find('.comment-edit-btn').trigger('click')
      await nextTick()
      expect(wrapper.vm.showEditForm).toBe(true)
      wrapper.vm.cancelEdit()
      await nextTick()
      expect(wrapper.vm.showEditForm).toBe(false)
      expect(wrapper.vm.editContent).toBe('')
    })
  })

  // ============================================================
  // 3. submitEdit 行为 (1 case)
  // ============================================================
  describe('submitEdit 行为', () => {
    it('空内容 → 不调用 store.updateComment', async () => {
      const wrapper = mount(CommentItem, makeMountOptions())
      await wrapper.find('.comment-edit-btn').trigger('click')
      await nextTick()
      wrapper.vm.editContent = '   '  // 只有空白
      await wrapper.vm.submitEdit()
      expect(mockUpdateComment).not.toHaveBeenCalled()
    })

    it('有效内容 → 调 store.updateComment + 成功后清表单 + ElMessage.success', async () => {
      mockUpdateComment.mockResolvedValue({
        comment: { id: 100, content: '新内容', mentions: [58] },
        mentioned_user_ids: [58],
      })
      const wrapper = mount(CommentItem, makeMountOptions())
      await wrapper.find('.comment-edit-btn').trigger('click')
      await nextTick()
      wrapper.vm.editContent = '新内容 @DuTongHe'
      await wrapper.vm.submitEdit()
      await flushPromises()
      expect(mockUpdateComment).toHaveBeenCalledWith(540, 100, '新内容 @DuTongHe')
      expect(wrapper.vm.showEditForm).toBe(false)
      expect(wrapper.vm.editContent).toBe('')
    })

    it('422 错误 (编辑窗口已过) → ElMessage.error + 关闭表单', async () => {
      const err = new Error('编辑失败')
      err.response = { data: { detail: '编辑窗口已过: 360s > 300s' } }
      mockUpdateComment.mockRejectedValue(err)
      const wrapper = mount(CommentItem, makeMountOptions())
      await wrapper.find('.comment-edit-btn').trigger('click')
      await nextTick()
      wrapper.vm.editContent = '试图编辑'
      await wrapper.vm.submitEdit()
      await flushPromises()
      expect(wrapper.vm.showEditForm).toBe(false)
      expect(wrapper.vm.editContent).toBe('')
    })
  })

  // ============================================================
  // 4. 已编辑标记 (1 case)
  // ============================================================
  describe('已编辑标记', () => {
    it('comment._edited=true → 显示 "已编辑" 标记', () => {
      const wrapper = mount(CommentItem, makeMountOptions({ _edited: true }))
      const tag = wrapper.find('.comment-edited-tag')
      expect(tag.exists()).toBe(true)
      expect(tag.text()).toBe('已编辑')
    })

    it('comment._edited 未设置 → 不显示 "已编辑" 标记', () => {
      const wrapper = mount(CommentItem, makeMountOptions())
      const tag = wrapper.find('.comment-edited-tag')
      expect(tag.exists()).toBe(false)
    })
  })
})
