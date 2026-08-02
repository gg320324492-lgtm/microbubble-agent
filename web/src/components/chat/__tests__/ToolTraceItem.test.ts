/**
 * ToolTraceItem 组件单测 — W100 +21
 * 8 case 覆盖：thinking 渲染 / tool 折叠态 / 点击展开 / a11y (aria-expanded 切换) /
 * keyboard (Enter/Space) / JSON 美化 / 复制按钮 / preview 单行截断
 */
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { nextTick } from 'vue'
import ToolTraceItem from '../ToolTraceItem.vue'

const mockClipboard = {
  writeText: vi.fn().mockResolvedValue(undefined),
}
Object.defineProperty(navigator, 'clipboard', {
  value: mockClipboard,
  writable: true,
  configurable: true,
})

const sampleToolTrace = {
  type: 'tool' as const,
  name: 'search_knowledge',
  state: 'done' as const,
  duration_ms: 234,
  tool_output: { results: [{ id: 1, title: '微纳米气泡综述' }] },
  tool_output_preview: '{"results":[{"id":1,"title":"微纳米气泡综述"}]}',
}

const sampleThinkingTrace = {
  type: 'thinking' as const,
  label: '🧠 意图：research',
}

describe('ToolTraceItem — W100 +21', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockClipboard.writeText.mockClear().mockResolvedValue(undefined)
  })

  it('① thinking 类型直接渲染 label，不可展开', () => {
    const wrapper = mount(ToolTraceItem, {
      props: { trace: sampleThinkingTrace, index: 0 },
    })
    expect(wrapper.find('[data-testid="tti-0-thinking"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="tti-0-thinking"]').text()).toContain('意图')
    expect(wrapper.find('[data-testid="tti-0-tool"]').exists()).toBe(false)
  })

  it('② tool 类型默认折叠，显示 ✓ + 耗时 + preview', () => {
    const wrapper = mount(ToolTraceItem, {
      props: { trace: sampleToolTrace, index: 1 },
    })
    const t = wrapper.find('[data-testid="tti-1-tool"]')
    expect(t.exists()).toBe(true)
    expect(t.attributes('data-state')).toBe('done')
    expect(wrapper.find('[data-testid="tti-1-row"]').exists() || wrapper.find('[role="button"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="tti-1-preview"]').text()).toContain('微纳米气泡综述')
    expect(wrapper.find('[data-testid="tti-1-detail"]').exists()).toBe(false)
  })

  it('③ 点击 row 展开，aria-expanded 切换到 true，detail 显示', async () => {
    const wrapper = mount(ToolTraceItem, {
      props: { trace: sampleToolTrace, index: 2 },
    })
    const btn = wrapper.find('[role="button"]')
    expect(btn.attributes('aria-expanded')).toBe('false')
    await btn.trigger('click')
    await nextTick()
    expect(btn.attributes('aria-expanded')).toBe('true')
    expect(wrapper.find('[data-testid="tti-2-detail"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="tti-2-detail"]').text()).toContain('微纳米气泡综述')
  })

  it('④ keyboard Enter 触发展开（a11y 必需）', async () => {
    const wrapper = mount(ToolTraceItem, {
      props: { trace: sampleToolTrace, index: 3 },
    })
    const btn = wrapper.find('[role="button"]')
    expect(btn.attributes('aria-expanded')).toBe('false')
    await btn.trigger('keydown', { key: 'Enter' })
    await nextTick()
    expect(btn.attributes('aria-expanded')).toBe('true')
  })

  it('⑤ keyboard Space 触发展开', async () => {
    const wrapper = mount(ToolTraceItem, {
      props: { trace: sampleToolTrace, index: 4 },
    })
    const btn = wrapper.find('[role="button"]')
    await btn.trigger('keydown', { key: ' ' })
    await nextTick()
    expect(btn.attributes('aria-expanded')).toBe('true')
  })

  it('⑥ 展开后 JSON 美化（2 空格缩进）显示', async () => {
    const wrapper = mount(ToolTraceItem, {
      props: { trace: sampleToolTrace, index: 5 },
    })
    await wrapper.find('[role="button"]').trigger('click')
    await nextTick()
    const json = wrapper.find('[data-testid="tti-5-detail"] pre code')
    expect(json.exists()).toBe(true)
    expect(json.text()).toContain('\n')
    expect(json.text()).toContain('  "results"')
  })

  it('⑦ 复制按钮调用 navigator.clipboard.writeText + 显示"已复制"', async () => {
    const wrapper = mount(ToolTraceItem, {
      props: { trace: sampleToolTrace, index: 6 },
    })
    await wrapper.find('[role="button"]').trigger('click')
    await nextTick()
    const copyBtn = wrapper.find('[data-testid="tti-6-copy"]')
    expect(copyBtn.exists()).toBe(true)
    await copyBtn.trigger('click')
    expect(mockClipboard.writeText).toHaveBeenCalledTimes(1)
    const text = mockClipboard.writeText.mock.calls[0][0]
    expect(text).toContain('"results"')
    expect(text).toContain('\n')
    await nextTick()
    expect(wrapper.find('[data-testid="tti-6-copy"]').text()).toContain('已复制')
  })

  it('⑧ 边界：tool_output 缺失 → detail 显示 "(没有 output)" 占位', async () => {
    const wrapper = mount(ToolTraceItem, {
      props: {
        trace: { type: 'tool', name: 'no_output_tool', state: 'done', duration_ms: 50 },
        index: 7,
      },
    })
    await wrapper.find('[role="button"]').trigger('click')
    await nextTick()
    expect(wrapper.find('[data-testid="tti-7-empty"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="tti-7-empty"]').text()).toContain('没有')
  })

  it('⑨ drive 列表提取 items[0].id 并 emit 文件跳转', async () => {
    const wrapper = mount(ToolTraceItem, {
      props: {
        trace: { type: 'tool', name: 'list_drive_files', state: 'done', tool_output: { items: [{ id: 42 }] } },
        index: 8,
      },
    })
    await wrapper.find('[role="button"]').trigger('click')
    await wrapper.find('[data-testid="tti-8-jump"]').trigger('click')
    expect(wrapper.emitted('jump')).toEqual([[{ type: 'drive', id: 42 }]])
  })

  it('⑩ task 统计无详情 ID 时 emit 任务列表跳转', async () => {
    const wrapper = mount(ToolTraceItem, {
      props: {
        trace: { type: 'tool', name: 'get_task_stats', state: 'done', tool_output: { stats: { total: 3 } } },
        index: 9,
      },
    })
    await wrapper.find('[role="button"]').trigger('click')
    const jump = wrapper.find('[data-testid="tti-9-jump"]')
    expect(jump.attributes('aria-label')).toContain('打开任务')
    await jump.trigger('click')
    expect(wrapper.emitted('jump')).toEqual([[{ type: 'task', id: undefined }]])
  })

  it('⑪ meeting 兼容 meetings[0].id 并 emit 会议详情跳转', async () => {
    const wrapper = mount(ToolTraceItem, {
      props: {
        trace: { type: 'tool', name: 'query_meetings', state: 'done', tool_output: { meetings: [{ id: 7 }] } },
        index: 10,
      },
    })
    await wrapper.find('[role="button"]').trigger('click')
    await wrapper.find('[data-testid="tti-10-jump"]').trigger('click')
    expect(wrapper.emitted('jump')).toEqual([[{ type: 'meeting', id: 7 }]])
  })
})
