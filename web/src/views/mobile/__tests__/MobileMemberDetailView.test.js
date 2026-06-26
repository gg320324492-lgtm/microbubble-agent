import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createRouter, createMemoryHistory } from 'vue-router'
import MobileMemberDetailView from '../MobileMemberDetailView.vue'

// Mock axios
vi.mock('axios', () => ({
  default: {
    get: vi.fn(),
    post: vi.fn(),
  },
}))

import axios from 'axios'

const router = createRouter({
  history: createMemoryHistory(),
  routes: [
    { path: '/mobile/members', component: { template: '<div />' } },
    { path: '/mobile/members/:id', component: { template: '<div />' } },
    { path: '/mobile/voiceprint', component: { template: '<div />' } },
  ],
})

const makeMember = (overrides = {}) => ({
  id: 1,
  name: '王天志',
  role: 'member',
  grade: '博一',
  research_area: '气泡生成',
  email: 'wang@example.com',
  phone: '13800138000',
  bio: '研究微纳米气泡的博士生',
  skills: ['NTA', 'DLS'],
  voice_enrolled_at: '2026-06-01T03:00:00Z',
  voice_sample_count: 3,
  ...overrides,
})

const factory = async (routeParams = { id: '1' }) => {
  // 必须 await router.push 让 route.params 更新
  if (routeParams.id) {
    await router.push({ path: `/mobile/members/${routeParams.id}` })
  } else {
    await router.push({ path: '/mobile/members' })
  }
  return mount(MobileMemberDetailView, {
    global: { plugins: [router] },
  })
}

describe('MobileMemberDetailView', () => {
  beforeEach(() => {
    // v75 修复: clearAllMocks 只清 mock.calls/history, 不清 mockImplementationOnce 队列
    // 第 2 case 用 mockImplementationOnce(() => new Promise(() => {})) 永不 resolve
    // 第 3 case mockRejectedValueOnce 只是加到 queue 末尾, 取的还是第 1 个 = 永不 resolve
    // 修法: 用 mockReset 清掉所有 queue + implementation
    vi.resetAllMocks()
  })

  it('未传 id 时显示空态', async () => {
    axios.get.mockResolvedValueOnce({ data: makeMember() })
    const wrapper = await factory({ id: '' })
    await flushPromises()
    // 没有 id 应该不调 API
    expect(axios.get).not.toHaveBeenCalled()
  })

  it('加载中显示 spinner', async () => {
    axios.get.mockImplementationOnce(() => new Promise(() => {}))  // 永不 resolve
    const wrapper = await factory()
    expect(wrapper.find('.loading-spinner').exists()).toBe(true)
  })

  it('API 404 显示"未找到该成员"', async () => {
    axios.get.mockRejectedValueOnce(new Error('Not Found'))
    const wrapper = await factory()
    await flushPromises()
    expect(wrapper.find('.empty-title').text()).toBe('未找到该成员')
  })

  it('API 成功渲染成员信息', async () => {
    const m = makeMember()
    axios.get.mockResolvedValueOnce({ data: m })
    const wrapper = await factory()
    await flushPromises()
    // text() 去前后空白后包含核心字段
    const text = wrapper.text().replace(/\s+/g, '')
    expect(text).toContain('王天志')
    expect(text).toContain('气泡生成')
    expect(text).toContain('wang@example.com')
  })

  it('已录入声纹显示声纹 section', async () => {
    const m = makeMember()
    axios.get.mockResolvedValueOnce({ data: m })
    const wrapper = await factory()
    await flushPromises()
    const text = wrapper.text().replace(/\s+/g, '')
    expect(text).toContain('录入时间')
    expect(text).toContain('采样次数')
  })

  it('未录入声纹时显示"未录入声纹"tag + 顶部录入按钮', async () => {
    // mock 返回 voice_enrolled_at=null 的成员 → v-else 分支渲染
    const m = { ...makeMember(), voice_enrolled_at: null, voice_sample_count: 0 }
    axios.get.mockResolvedValueOnce({ data: m })
    const wrapper = await factory()
    await flushPromises()
    // 顶部右上角 🎤 按钮（仅未录入时显示）应该存在
    expect(wrapper.find('.header-action').exists()).toBe(true)
  })

  it('有 skills 时显示技能 tag', async () => {
    axios.get.mockResolvedValueOnce({ data: makeMember() })
    const wrapper = await factory()
    await flushPromises()
    expect(wrapper.text()).toContain('NTA')
    expect(wrapper.text()).toContain('DLS')
  })

  it('有 bio 时显示个人简介 section', async () => {
    axios.get.mockResolvedValueOnce({ data: makeMember() })
    const wrapper = await factory()
    await flushPromises()
    expect(wrapper.find('.bio-text').text()).toBe('研究微纳米气泡的博士生')
  })
})
