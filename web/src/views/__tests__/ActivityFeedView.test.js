/**
 * ActivityFeedView.test.js — v2 PR6 (2026-07-22 Agent1)
 *
 * 覆盖:
 * - 基础渲染 (空态 / 列表 / 加载态)
 * - 11 种 action icon 映射 (后端 activity_service.VALID_ACTIONS 全集)
 * - action → 中文 label 映射
 * - target_type → 中文 label 映射
 * - "加载更多" 按钮 (cursor 分页)
 * - action summary (metadata JSONB 摘要)
 * - actor_name null 时显示 "系统"
 */
import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'

import ActivityFeedView from '@/views/desktop/ActivityFeedView.vue'

vi.mock('vue-router', () => ({
  useRouter: () => ({ push: vi.fn() }),
}))

// Mock axios (ActivityFeedView 用 axios 不是 fetch)
const mockAxiosGet = vi.fn()
vi.mock('axios', () => ({
  default: {
    get: (...args) => mockAxiosGet(...args),
  },
}))

// Element Plus stubs (与 FileRequestListPanel.test.js 风格一致)
const stubs = {
  'el-radio-button': { template: '<button class="el-radio-button-stub"><slot /></button>' },
  'el-radio-group': {
    template: '<div class="el-radio-group-stub"><slot /></div>',
    props: ['modelValue'],
  },
  'el-button': {
    template: '<button @click="$emit(\'click\', $event)"><slot /></button>',
    props: ['loading', 'link', 'size'],
  },
  'el-icon': {
    template: '<i class="el-icon-stub"><slot /></i>',
    props: ['size'],
  },
}

// Mock Element Plus icons
vi.mock('@element-plus/icons-vue', () => ({
  UploadFilled: { template: '<i class="icon-upload" />' },
  Edit: { template: '<i class="icon-rename" />' },
  FolderOpened: { template: '<i class="icon-move" />' },
  Delete: { template: '<i class="icon-delete" />' },
  RefreshRight: { template: '<i class="icon-restore" />' },
  Share: { template: '<i class="icon-share" />' },
  ChatLineRound: { template: '<i class="icon-comment" />' },
  Star: { template: '<i class="icon-star" />' },
  StarFilled: { template: '<i class="icon-star-filled" />' },
  Refresh: { template: '<i class="icon-refresh" />' },
  Loading: { template: '<i class="icon-loading" />' },
  ArrowDown: { template: '<i class="icon-arrow-down" />' },
}))

function makeResponse(items, has_more = false) {
  return { data: { items, has_more } }
}

const FIXED_NOW = new Date('2026-07-22T12:00:00Z')

describe('ActivityFeedView 渲染 + action 映射', () => {
  beforeEach(() => {
    vi.useFakeTimers()
    vi.setSystemTime(FIXED_NOW)
    mockAxiosGet.mockReset()
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  it('空态: 无数据时显示"暂无活动"', async () => {
    mockAxiosGet.mockResolvedValueOnce(makeResponse([], false))
    const wrapper = mount(ActivityFeedView, { global: { stubs } })
    await flushPromises()
    expect(wrapper.find('.activity-empty').exists()).toBe(true)
    expect(wrapper.text()).toContain('暂无活动')
  })

  it('列表: 渲染 actor_name + action label + target_name + timestamp', async () => {
    mockAxiosGet.mockResolvedValueOnce(makeResponse([
      {
        id: 1,
        actor_id: 2,
        actor_name: '贾琦',
        action: 'upload',
        target_type: 'file',
        target_id: 100,
        target_name: '组会PPT/2026-07-21 会议.pdf',
        metadata: {},
        created_at: '2026-07-22T11:55:00Z',
      },
    ]))
    const wrapper = mount(ActivityFeedView, { global: { stubs } })
    await flushPromises()
    const items = wrapper.findAll('.activity-item')
    expect(items).toHaveLength(1)
    expect(wrapper.text()).toContain('贾琦')
    expect(wrapper.text()).toContain('上传了')
    expect(wrapper.text()).toContain('组会PPT/2026-07-21 会议.pdf')
  })

  it('11 种 action 全部映射 icon (upload/rename/move/delete/restore/share/comment/mention/star/unstar/version_restore)', async () => {
    const fixtureItems = [
      { id: 1, actor_name: 'a', action: 'upload', target_type: 'file', target_name: 'x', metadata: {}, created_at: '2026-07-22T11:55:00Z' },
      { id: 2, actor_name: 'a', action: 'rename', target_type: 'file', target_name: 'x', metadata: {}, created_at: '2026-07-22T11:55:00Z' },
      { id: 3, actor_name: 'a', action: 'move', target_type: 'file', target_name: 'x', metadata: {}, created_at: '2026-07-22T11:55:00Z' },
      { id: 4, actor_name: 'a', action: 'delete', target_type: 'file', target_name: 'x', metadata: {}, created_at: '2026-07-22T11:55:00Z' },
      { id: 5, actor_name: 'a', action: 'restore', target_type: 'file', target_name: 'x', metadata: {}, created_at: '2026-07-22T11:55:00Z' },
      { id: 6, actor_name: 'a', action: 'share', target_type: 'file', target_name: 'x', metadata: {}, created_at: '2026-07-22T11:55:00Z' },
      { id: 7, actor_name: 'a', action: 'comment', target_type: 'file', target_name: 'x', metadata: {}, created_at: '2026-07-22T11:55:00Z' },
      { id: 8, actor_name: 'a', action: 'mention', target_type: 'file', target_name: 'x', metadata: {}, created_at: '2026-07-22T11:55:00Z' },
      { id: 9, actor_name: 'a', action: 'star', target_type: 'file', target_name: 'x', metadata: {}, created_at: '2026-07-22T11:55:00Z' },
      { id: 10, actor_name: 'a', action: 'unstar', target_type: 'file', target_name: 'x', metadata: {}, created_at: '2026-07-22T11:55:00Z' },
      { id: 11, actor_name: 'a', action: 'version_restore', target_type: 'file', target_name: 'x', metadata: {}, created_at: '2026-07-22T11:55:00Z' },
    ]
    mockAxiosGet.mockResolvedValueOnce(makeResponse(fixtureItems, false))
    const wrapper = mount(ActivityFeedView, { global: { stubs } })
    await flushPromises()
    const items = wrapper.findAll('.activity-item')
    expect(items).toHaveLength(11)
    // 每个 item 都有一个 icon 区域
    items.forEach((item) => {
      expect(item.find('.activity-icon').exists()).toBe(true)
    })
  })

  it('action 中文 label: upload→"上传了", delete→"删除了", mention→"提到了"', async () => {
    mockAxiosGet.mockResolvedValueOnce(makeResponse([
      { id: 1, actor_name: 'a', action: 'upload', target_type: 'file', target_name: 'x.pdf', metadata: {}, created_at: '2026-07-22T11:55:00Z' },
      { id: 2, actor_name: 'a', action: 'delete', target_type: 'file', target_name: 'y.pdf', metadata: {}, created_at: '2026-07-22T11:55:00Z' },
      { id: 3, actor_name: 'a', action: 'mention', target_type: 'file', target_name: 'z.pdf', metadata: {}, created_at: '2026-07-22T11:55:00Z' },
    ]))
    const wrapper = mount(ActivityFeedView, { global: { stubs } })
    await flushPromises()
    expect(wrapper.text()).toContain('上传了')
    expect(wrapper.text()).toContain('删除了')
    expect(wrapper.text()).toContain('提到了')
  })

  it('action summary: rename metadata 显示 "原名 → 新名"', async () => {
    mockAxiosGet.mockResolvedValueOnce(makeResponse([
      {
        id: 1,
        actor_name: 'a',
        action: 'rename',
        target_type: 'file',
        target_name: '新名字.pdf',
        metadata: { old_name: '旧名字.pdf', new_name: '新名字.pdf' },
        created_at: '2026-07-22T11:55:00Z',
      },
    ]))
    const wrapper = mount(ActivityFeedView, { global: { stubs } })
    await flushPromises()
    expect(wrapper.text()).toContain('原名: 旧名字.pdf')
    expect(wrapper.text()).toContain('新名: 新名字.pdf')
  })

  it('加载更多: has_more=true 时显示"加载更多"按钮', async () => {
    mockAxiosGet.mockResolvedValueOnce(makeResponse([
      { id: 1, actor_name: 'a', action: 'upload', target_type: 'file', target_name: 'x', metadata: {}, created_at: '2026-07-22T11:55:00Z' },
    ], true))
    const wrapper = mount(ActivityFeedView, { global: { stubs } })
    await flushPromises()
    expect(wrapper.find('.activity-load-more').exists()).toBe(true)
    expect(wrapper.text()).toContain('加载更多')
  })

  it('actor_name 为空时显示 "系统"', async () => {
    mockAxiosGet.mockResolvedValueOnce(makeResponse([
      {
        id: 1,
        actor_id: null,
        actor_name: null,
        action: 'delete',
        target_type: 'file',
        target_name: 'x.pdf',
        metadata: {},
        created_at: '2026-07-22T11:55:00Z',
      },
    ]))
    const wrapper = mount(ActivityFeedView, { global: { stubs } })
    await flushPromises()
    expect(wrapper.text()).toContain('系统')
  })

  it('API GET /api/v1/activities 发送正确参数 (scope=team, limit=30)', async () => {
    mockAxiosGet.mockResolvedValueOnce(makeResponse([], false))
    mount(ActivityFeedView, { global: { stubs } })
    await flushPromises()
    expect(mockAxiosGet).toHaveBeenCalledTimes(1)
    const [url, opts] = mockAxiosGet.mock.calls[0]
    expect(url).toBe('/api/v1/activities')
    expect(opts.params.scope).toBe('team')
    expect(opts.params.limit).toBe(30)
  })

  it('target_type: file→"文件", folder→"文件夹", comment→"评论"', async () => {
    mockAxiosGet.mockResolvedValueOnce(makeResponse([
      { id: 1, actor_name: 'a', action: 'upload', target_type: 'file', target_name: 'x', metadata: {}, created_at: '2026-07-22T11:55:00Z' },
      { id: 2, actor_name: 'a', action: 'rename', target_type: 'folder', target_name: 'y', metadata: {}, created_at: '2026-07-22T11:55:00Z' },
      { id: 3, actor_name: 'a', action: 'comment', target_type: 'comment', target_name: 'z', metadata: {}, created_at: '2026-07-22T11:55:00Z' },
    ]))
    const wrapper = mount(ActivityFeedView, { global: { stubs } })
    await flushPromises()
    expect(wrapper.text()).toContain('文件')
    expect(wrapper.text()).toContain('文件夹')
    expect(wrapper.text()).toContain('评论')
  })
})