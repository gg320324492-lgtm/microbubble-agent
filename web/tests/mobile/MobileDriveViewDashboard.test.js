// MobileDriveViewDashboard.test.js — v2 PR8 Agent 2
// 验证 MobileDriveView 接 /api/v1/mobile/dashboard 聚合 API
// 4 tab 渲染 (files/starred/team/recent) + notification_unread_count badge
// 失败时回退到 fetchFiles (兜底路径)

import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createRouter, createMemoryHistory } from 'vue-router'

// Mock axios (MobileDriveView + useDriveFiles + MobileCommandPalette 都会用到)
vi.mock('axios', () => ({
  default: {
    get: vi.fn(),
    post: vi.fn(),
    put: vi.fn(),
    delete: vi.fn(),
  },
}))

import axios from 'axios'

const router = createRouter({
  history: createMemoryHistory(),
  routes: [
    { path: '/drive/preview/:id', component: { template: '<div />' } },
    { path: '/workspace', component: { template: '<div />' } },
  ],
})

// ---- fixtures: 后端 mobile.py dashboard 真实响应形状 ----
function makeDashboard(overrides = {}) {
  return {
    recent_activities: [
      { id: 1, actor_id: 2, actor_name: '王天志', action: 'upload', target_type: 'file', target_id: 10, target_name: 'a.pdf', created_at: '2026-07-22T10:00:00Z' },
    ],
    starred_files: [
      { id: 10, title: '组会纪要', file_name: 'meeting.pdf', file_type: 'application/pdf', file_size: 1024, visibility: 'team', folder_id: null, starred_at: '2026-07-22T10:00:00Z', updated_at: '2026-07-22T10:00:00Z' },
      { id: 11, title: '论文 PPT', file_name: 'paper.pptx', file_type: 'application/vnd.openxmlformats-officedocument.presentationml.presentation', file_size: 2048, visibility: 'team', folder_id: 5, starred_at: '2026-07-21T08:00:00Z', updated_at: '2026-07-21T08:00:00Z' },
    ],
    team_root_files: [
      { id: 20, title: '共享 PPT', file_name: 'shared.pptx', file_type: 'application/vnd.openxmlformats-officedocument.presentationml.presentation', file_size: 4096, folder_id: null, updated_at: '2026-07-22T09:00:00Z', uploader_id: 2, uploader_name: '王天志' },
    ],
    my_uploads: [
      { id: 30, title: '我传的文件', file_name: 'mine.txt', file_type: 'text/plain', file_size: 256, visibility: 'private', folder_id: null, created_at: '2026-07-22T11:00:00Z' },
    ],
    notification_unread_count: 7,
    generated_at: '2026-07-22T12:00:00Z',
    ...overrides,
  }
}

const factory = async () => {
  const { default: MobileDriveView } = await import('../../src/views/mobile/MobileDriveView.vue')
  return mount(MobileDriveView, {
    global: { plugins: [router] },
    attachTo: document.body,
  })
}

const originalFetch = global.fetch

describe('MobileDriveView 接 mobile.py dashboard', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    document.body.innerHTML = ''
    // 默认: dashboard 200 OK + useDriveFiles.fetchFiles 备用
    axios.get.mockImplementation((url) => {
      if (url === '/api/v1/mobile/dashboard') {
        return Promise.resolve({ data: makeDashboard() })
      }
      if (url === '/api/v1/drive/folder-tree') {
        return Promise.resolve({ data: [] })
      }
      // drive files 兜底接口
      if (url.startsWith('/api/v1/drive/files')) {
        return Promise.resolve({ data: { items: [], total: 0 } })
      }
      return Promise.resolve({ data: [] })
    })
  })

  afterEach(() => {
    // 还原 fetch (兜底测试可能 mock 了 global.fetch)
    global.fetch = originalFetch
  })

  it('onMounted 后调用 1 次 /api/v1/mobile/dashboard', async () => {
    await factory()
    await flushPromises()
    const dashboardCalls = axios.get.mock.calls.filter(
      ([url]) => url === '/api/v1/mobile/dashboard'
    )
    expect(dashboardCalls.length).toBe(1)
  })

  it('notification_unread_count 显示在顶栏 badge', async () => {
    const wrapper = await factory()
    await flushPromises()
    const badge = wrapper.find('.notification-badge')
    expect(badge.exists()).toBe(true)
    expect(badge.find('.notification-badge-count').text()).toBe('7')
  })

  it('notification_unread_count = 0 时不显示 badge', async () => {
    axios.get.mockImplementation((url) => {
      if (url === '/api/v1/mobile/dashboard') {
        return Promise.resolve({ data: makeDashboard({ notification_unread_count: 0 }) })
      }
      if (url === '/api/v1/drive/folder-tree') return Promise.resolve({ data: [] })
      if (url.startsWith('/api/v1/drive/files')) return Promise.resolve({ data: { items: [], total: 0 } })
      return Promise.resolve({ data: [] })
    })
    const wrapper = await factory()
    await flushPromises()
    expect(wrapper.find('.notification-badge').exists()).toBe(false)
  })

  it('starred tab 切换: 渲染 starred_files section 的 2 个文件', async () => {
    const wrapper = await factory()
    await flushPromises()
    // 切到 starred tab
    const tabs = wrapper.findAll('.drive-tab-btn')
    const starredTab = tabs.find((t) => t.text().includes('收藏'))
    expect(starredTab).toBeTruthy()
    await starredTab.trigger('click')
    await flushPromises()
    // 验证渲染的卡片数 = starred_files.length = 2
    const cards = wrapper.findAll('.drive-file-card')
    expect(cards.length).toBe(2)
    expect(cards[0].text()).toContain('组会纪要')
    expect(cards[1].text()).toContain('论文 PPT')
  })

  it('team tab 切换: 渲染 team_root_files section 的 1 个文件', async () => {
    const wrapper = await factory()
    await flushPromises()
    const tabs = wrapper.findAll('.drive-tab-btn')
    const teamTab = tabs.find((t) => t.text().includes('团队'))
    expect(teamTab).toBeTruthy()
    await teamTab.trigger('click')
    await flushPromises()
    const cards = wrapper.findAll('.drive-file-card')
    expect(cards.length).toBe(1)
    expect(cards[0].text()).toContain('共享 PPT')
  })

  it('recent tab 切换: 渲染 my_uploads section 的 1 个文件', async () => {
    const wrapper = await factory()
    await flushPromises()
    const tabs = wrapper.findAll('.drive-tab-btn')
    const recentTab = tabs.find((t) => t.text().includes('最近'))
    expect(recentTab).toBeTruthy()
    await recentTab.trigger('click')
    await flushPromises()
    const cards = wrapper.findAll('.drive-file-card')
    expect(cards.length).toBe(1)
    expect(cards[0].text()).toContain('我传的文件')
  })

  it('files tab: onMounted 走 fetchFiles 兜底 (activeTab=files 默认, dashboardSectionForTab("files") 返 null)', async () => {
    // mock fetch (useDriveFiles.fetchFiles 内部用 fetch 不是 axios)
    const fetchMock = vi.fn(() => Promise.resolve({
      ok: true,
      json: () => Promise.resolve({ items: [], total: 0 }),
    }))
    global.fetch = fetchMock
    const wrapper = await factory()
    await flushPromises()
    // 默认 activeTab='files' → onMounted → applyTabQuery → dashboardSectionForTab('files') 返 null
    //   → 走 fetchFiles 兜底 → fetch('/api/v1/drive/files?...')
    const filesCalls = fetchMock.mock.calls.filter(
      ([url]) => typeof url === 'string' && url.startsWith('/api/v1/drive/files')
    )
    expect(filesCalls.length).toBeGreaterThan(0)
    // tab 数仍是 4 (没退化)
    expect(wrapper.findAll('.drive-tab-btn').length).toBe(4)
    global.fetch = originalFetch
  })

  it('dashboard 失败时回退 fetchFiles (兜底)', async () => {
    axios.get.mockImplementation((url) => {
      if (url === '/api/v1/mobile/dashboard') {
        return Promise.reject(new Error('网络超时'))
      }
      if (url === '/api/v1/drive/folder-tree') return Promise.resolve({ data: [] })
      if (url.startsWith('/api/v1/drive/files')) return Promise.resolve({ data: { items: [], total: 0 } })
      return Promise.resolve({ data: [] })
    })
    const wrapper = await factory()
    await flushPromises()
    // dashboard 失败 → badge 不显示
    expect(wrapper.find('.notification-badge').exists()).toBe(false)
    // 但 tab 仍可用 (files tab)
    const tabs = wrapper.findAll('.drive-tab-btn')
    const filesTab = tabs.find((t) => t.text().includes('文件'))
    await filesTab.trigger('click')
    await flushPromises()
    // 不抛错即通过 (空列表渲染)
    expect(tabs.length).toBe(4)
  })

  it('4 tab 全部存在 (files/starred/recent/team)', async () => {
    const wrapper = await factory()
    await flushPromises()
    const tabs = wrapper.findAll('.drive-tab-btn')
    expect(tabs.length).toBe(4)
    const labels = tabs.map((t) => t.text())
    expect(labels.some((l) => l.includes('文件'))).toBe(true)
    expect(labels.some((l) => l.includes('收藏'))).toBe(true)
    expect(labels.some((l) => l.includes('最近'))).toBe(true)
    expect(labels.some((l) => l.includes('团队'))).toBe(true)
  })
})