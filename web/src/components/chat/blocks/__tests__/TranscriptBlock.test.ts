/**
 * TranscriptBlock 组件单测 — W100 +49b RICHTEXT-UNFOLD
 * 5 case 覆盖：默认 (block.collapsed_by_default != true) 全 transcript 渲染 /
 * 折叠模式 / 折叠模式点 header 展开 / 折叠模式超 3 行预览 / 边界（空 text）
 *
 * 默认模式 (block.collapsed_by_default != true):
 *   - 全部 parsed lines 直接渲染, 不渲染 toggle 按钮
 *   - header click 是 no-op (W100 +49b 修复: 仅折叠模式响应)
 *
 * 折叠模式 (block.collapsed_by_default === true):
 *   - header click 触发 toggle 切换预览 / 全 transcript
 */
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { nextTick } from 'vue'

// TranscriptBlock 通过 `useRouter()` 跳转 — 测试场景不需要, mock 掉避免 warning
vi.mock('vue-router', () => ({
  useRouter: () => ({ push: vi.fn() }),
  useRoute: () => ({ params: {}, query: {} }),
}))

import TranscriptBlock from '../TranscriptBlock.vue'

const sampleBlock = (extra: Record<string, any> = {}) => {
  const base = {
    type: 'transcript',
    collapsed_by_default: undefined as boolean | undefined,
    data: {
      meeting_id: 'mt-1',
      title: '例会 2026-08-03',
      transcript_text: '【张三】今天讨论 zeta 电位。\n【李四】同意。\n【王五】下一步计划。',
      entries_count: 3,
      truncated: false,
    },
  }
  // Override `data` if extra.data provided, otherwise spread top-level extra
  if (extra.data) {
    return { ...base, ...extra, data: { ...base.data, ...extra.data } }
  }
  return { ...base, ...extra }
}

describe('TranscriptBlock — W100 +49b RICHTEXT-UNFOLD 默认展开', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('① 默认 (collapsed_by_default 不传) = 全部 transcript 渲染，无 toggle 按钮', async () => {
    const wrapper = mount(TranscriptBlock, {
      props: { block: sampleBlock() },
      global: {
        stubs: { 'el-button': true },
      },
    })
    await nextTick()
    const root = wrapper.find('[data-testid="transcript-block"]')
    expect(root.exists()).toBe(true)
    expect(root.attributes('data-collapsed-by-default')).toBe('false')
    expect(wrapper.find('[data-testid="transcript-toggle"]').exists()).toBe(false)
    expect(wrapper.findAll('.dialogue-line').length).toBe(3)
  })

  it('② collapsed_by_default=true 折叠模式 = toggle 存在，全文未渲染 (预览)', async () => {
    const wrapper = mount(TranscriptBlock, {
      props: { block: sampleBlock({ collapsed_by_default: true }) },
      global: {
        stubs: { 'el-button': true },
      },
    })
    await nextTick()
    expect(wrapper.find('[data-testid="transcript-toggle"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="transcript-toggle"]').text()).toContain('展开')
    expect(wrapper.attributes('data-collapsed-by-default')).toBe('true')
    expect(wrapper.findAll('.preview-line').length).toBe(3)
    expect(wrapper.findAll('.dialogue-line').length).toBe(0)
  })

  it('③ 折叠模式点 header 切换展开', async () => {
    const wrapper = mount(TranscriptBlock, {
      props: { block: sampleBlock({ collapsed_by_default: true }) },
      global: {
        stubs: { 'el-button': true },
      },
    })
    await nextTick()
    const header = wrapper.find('.card-header')
    await header.trigger('click')
    await nextTick()
    expect(wrapper.findAll('.dialogue-line').length).toBe(3)
    expect(wrapper.find('[data-testid="transcript-toggle"]').text()).toContain('收起')
    await header.trigger('click')
    await nextTick()
    expect(wrapper.findAll('.preview-line').length).toBe(3)
  })

  it('④ 折叠模式超过 3 行时显示预览...', async () => {
    const wrapper = mount(TranscriptBlock, {
      props: {
        block: sampleBlock({
          collapsed_by_default: true,
          data: {
            meeting_id: 'mt-1',
            title: '长会议',
            transcript_text: 'A\nB\nC\nD\nE',
            entries_count: 5,
            truncated: false,
          },
        }),
      },
      global: {
        stubs: { 'el-button': true },
      },
    })
    await nextTick()
    expect(wrapper.find('.more').exists()).toBe(true)
    expect(wrapper.find('.more').text()).toContain('共 5 行')
  })

  it('⑤ 边界：空 transcript_text → 不渲染 preview / full', async () => {
    const wrapper = mount(TranscriptBlock, {
      props: {
        block: sampleBlock({
          data: {
            meeting_id: 'mt-1',
            title: '空会议',
            transcript_text: '',
            entries_count: 0,
            truncated: false,
          },
        }),
      },
      global: {
        stubs: { 'el-button': true },
      },
    })
    await nextTick()
    expect(wrapper.findAll('.preview-line').length).toBe(0)
    expect(wrapper.findAll('.dialogue-line').length).toBe(0)
  })
})
