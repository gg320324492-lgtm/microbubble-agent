import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createRouter, createMemoryHistory } from 'vue-router'
import SpeakerSearchSheet from '../SpeakerSearchSheet.vue'

// Mock axios
vi.mock('axios', () => ({
  default: { get: vi.fn() },
}))

import axios from 'axios'

const router = createRouter({
  history: createMemoryHistory(),
  routes: [
    { path: '/mobile/voiceprint', component: { template: '<div />' } },
    { path: '/mobile/meetings/:id', component: { template: '<div />' } },
  ],
})

const makeMember = () => ({
  id: 1,
  name: '王天志',
  voice_sample_count: 3,
  voice_enrolled_at: '2026-06-01T03:00:00Z',
})

const makeHistory = () => [
  { meeting_id: 10, meeting_title: '组会 #95', confidence: 0.92, recorded_at: '2026-06-15T03:00:00Z' },
  { meeting_id: 20, meeting_title: '论文讨论', confidence: 0.65, recorded_at: '2026-06-14T03:00:00Z' },
]

const factory = (props = {}) => mount(SpeakerSearchSheet, {
  props: { modelValue: true, member: makeMember(), ...props },
  global: { plugins: [router] },
})

describe('SpeakerSearchSheet', () => {
  beforeEach(() => vi.clearAllMocks())

  it('modelValue=false 时不渲染根容器', () => {
    const wrapper = factory({ modelValue: false })
    expect(wrapper.find('.speaker-sheet-root').exists()).toBe(false)
  })

  it('modelValue=true + 选成员时调 /api/v1/voiceprint/{id}/history', async () => {
    axios.get.mockResolvedValueOnce({ data: makeHistory() })
    factory()
    await flushPromises()
    expect(axios.get).toHaveBeenCalledWith('/api/v1/voiceprint/1/history', { params: { limit: 50 } })
  })

  it('API 返回 history 后渲染历史项', async () => {
    axios.get.mockResolvedValueOnce({ data: makeHistory() })
    const wrapper = factory()
    await flushPromises()
    const items = wrapper.findAll('.history-item')
    expect(items.length).toBe(2)
  })

  it('空 history 显示空态', async () => {
    axios.get.mockResolvedValueOnce({ data: [] })
    const wrapper = factory()
    await flushPromises()
    expect(wrapper.find('.empty-state').exists()).toBe(true)
    expect(wrapper.find('.empty-title').text()).toBe('暂无说话记录')
  })

  it('点关闭按钮 emit update:modelValue=false', async () => {
    axios.get.mockResolvedValueOnce({ data: makeHistory() })
    const wrapper = factory()
    await flushPromises()
    await wrapper.find('.close-btn').trigger('click')
    expect(wrapper.emitted('update:modelValue')).toBeTruthy()
    expect(wrapper.emitted('update:modelValue')[0]).toEqual([false])
  })

  it('高置信度进度条宽度 = Math.round(confidence*100)%', async () => {
    axios.get.mockResolvedValueOnce({ data: makeHistory() })
    const wrapper = factory()
    await flushPromises()
    const fills = wrapper.findAll('.confidence-fill')
    expect(fills[0].attributes('style')).toContain('width: 92%')
    expect(fills[1].attributes('style')).toContain('width: 65%')
  })

  it('API 失败显示错误 toast', async () => {
    axios.get.mockRejectedValueOnce(new Error('网络错误'))
    const wrapper = factory()
    await flushPromises()
    expect(wrapper.find('.error-toast').exists()).toBe(true)
  })

  it('点 history item 跳 /mobile/meetings/{id}', async () => {
    axios.get.mockResolvedValueOnce({ data: makeHistory() })
    const wrapper = factory()
    await flushPromises()
    await wrapper.findAll('.history-item')[0].trigger('click')
    expect(router.currentRoute.value.path).toBe('/mobile/meetings/10')
  })
})
