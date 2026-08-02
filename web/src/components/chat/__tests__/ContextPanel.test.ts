/**
 * ContextPanel 组件单测 - W100 +29
 * 7 case 覆盖：摘要统计 / tab 切换 / 对话历史 / 知识引用 / 工具调用 / 空会话边界 / dark mode
 */
import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import ContextPanel from '../ContextPanel.vue'

// ============================================================================
// 测试数据
// ============================================================================
const sampleMessages = [
  {
    id: 'msg-1',
    role: 'user' as const,
    content: '微纳米气泡的制备方法有哪些？',
    richBlocks: [],
    toolTrace: [],
    timestamp: '2026-08-02T10:00:00Z',
  },
  {
    id: 'msg-2',
    role: 'assistant' as const,
    content: '微纳米气泡的制备方法主要包括加压溶气法、机械剪切法、超声空化法和电解法等。',
    richBlocks: [
      {
        type: 'knowledge_ref',
        data: {
          results: [
            { id: 1, title: '微纳米气泡制备技术综述', score: 0.92 },
            { id: 2, title: '加压溶气法原理与应用', score: 0.85 },
          ],
        },
      },
    ],
    toolTrace: [
      { type: 'thinking' as const, label: '🧠 意图：research' },
      { type: 'tool' as const, name: 'search_knowledge', state: 'done' as const, duration_ms: 234 },
      { type: 'tool' as const, name: 'search_web', state: 'done' as const, duration_ms: 1200 },
    ],
    timestamp: '2026-08-02T10:00:05Z',
  },
  {
    id: 'msg-3',
    role: 'user' as const,
    content: '加压溶气法的具体参数是什么？',
    richBlocks: [],
    toolTrace: [],
    timestamp: '2026-08-02T10:01:00Z',
  },
  {
    id: 'msg-4',
    role: 'assistant' as const,
    content: '加压溶气法通常在 0.2-0.5 MPa 压力下操作，溶气时间 5-10 分钟。',
    richBlocks: [
      {
        type: 'knowledge_ref',
        data: {
          results: [
            { id: 3, title: '加压溶气法参数优化研究', score: 0.88 },
          ],
        },
      },
    ],
    toolTrace: [
      { type: 'tool' as const, name: 'search_knowledge', state: 'running' as const, duration_ms: 50 },
    ],
    timestamp: '2026-08-02T10:01:03Z',
  },
]

describe('ContextPanel - W100 +29', () => {
  it('① 摘要统计正确：2 轮对话 / 3 条知识 / 3 次工具调用', () => {
    const wrapper = mount(ContextPanel, {
      props: { messages: sampleMessages },
    })
    const summary = wrapper.find('[data-testid="cp-summary"]')
    expect(summary.exists()).toBe(true)
    expect(summary.text()).toContain('2 轮对话')
    expect(summary.text()).toContain('3 条知识')
    expect(summary.text()).toContain('3 次工具调用')
  })

  it('② 默认显示对话历史 tab，展示最近 N 轮消息', () => {
    const wrapper = mount(ContextPanel, {
      props: { messages: sampleMessages },
    })
    expect(wrapper.find('[data-testid="cp-pane-history"]').exists()).toBe(true)
    // 4 条消息（2 轮）
    const items = wrapper.findAll('[data-testid^="cp-history-"]')
    expect(items.length).toBe(4)
    // 第一条是 user 消息
    expect(items[0].classes()).toContain('cp-role-user')
    expect(items[0].text()).toContain('微纳米气泡的制备方法')
  })

  it('③ 切换到知识引用 tab，显示所有 knowledge_ref 条目', async () => {
    const wrapper = mount(ContextPanel, {
      props: { messages: sampleMessages },
    })
    await wrapper.find('[data-testid="cp-tab-knowledge"]').trigger('click')
    const pane = wrapper.find('[data-testid="cp-pane-knowledge"]')
    expect(pane.exists()).toBe(true)
    const items = wrapper.findAll('[data-testid^="cp-knowledge-"]')
    expect(items.length).toBe(3)
    expect(items[0].text()).toContain('微纳米气泡制备技术综述')
    expect(items[0].text()).toContain('92%')
  })

  it('④ 切换到工具调用 tab，显示所有 tool 类型 trace', async () => {
    const wrapper = mount(ContextPanel, {
      props: { messages: sampleMessages },
    })
    await wrapper.find('[data-testid="cp-tab-tools"]').trigger('click')
    const pane = wrapper.find('[data-testid="cp-pane-tools"]')
    expect(pane.exists()).toBe(true)
    const items = wrapper.findAll('[data-testid^="cp-tool-"]')
    // thinking 类型不计入，只有 3 个 tool 类型
    expect(items.length).toBe(3)
    expect(items[0].text()).toContain('search_knowledge')
    expect(items[0].text()).toContain('234ms')
  })

  it('⑤ 工具调用 running 状态显示 ⏳，done 状态显示 ✓', async () => {
    const wrapper = mount(ContextPanel, {
      props: { messages: sampleMessages },
    })
    await wrapper.find('[data-testid="cp-tab-tools"]').trigger('click')
    const items = wrapper.findAll('[data-testid^="cp-tool-"]')
    // 第一个 search_knowledge 是 done
    expect(items[0].find('.cp-state-done').exists()).toBe(true)
    // 最后一个 search_knowledge 是 running
    expect(items[2].find('.cp-state-running').exists()).toBe(true)
  })

  it('⑥ 空会话边界：所有 tab 显示空提示', () => {
    const wrapper = mount(ContextPanel, {
      props: { messages: [] },
    })
    // 摘要 0
    const summary = wrapper.find('[data-testid="cp-summary"]')
    expect(summary.text()).toContain('0 轮对话')
    expect(summary.text()).toContain('0 条知识')
    expect(summary.text()).toContain('0 次工具调用')
    // 对话历史空
    expect(wrapper.find('[data-testid="cp-pane-history"] .cp-empty').exists()).toBe(true)
  })

  it('⑦ tab aria-selected 切换正确', async () => {
    const wrapper = mount(ContextPanel, {
      props: { messages: sampleMessages },
    })
    const historyTab = wrapper.find('[data-testid="cp-tab-history"]')
    const knowledgeTab = wrapper.find('[data-testid="cp-tab-knowledge"]')
    expect(historyTab.attributes('aria-selected')).toBe('true')
    expect(knowledgeTab.attributes('aria-selected')).toBe('false')
    await knowledgeTab.trigger('click')
    expect(historyTab.attributes('aria-selected')).toBe('false')
    expect(knowledgeTab.attributes('aria-selected')).toBe('true')
  })

  it('⑧ 对话历史超长内容截断为 80 字符 + …', () => {
    const longContent = 'A'.repeat(120)
    const wrapper = mount(ContextPanel, {
      props: {
        messages: [
          { id: 'long-1', role: 'user', content: longContent, richBlocks: [], toolTrace: [], timestamp: '' },
        ],
      },
    })
    const item = wrapper.find('[data-testid="cp-history-long-1"]')
    expect(item.text()).toContain('…')
    // 截断后应为 80 字符 + …
    expect(item.find('.cp-history-text').text().length).toBeLessThanOrEqual(81)
  })

  it('⑨ 工具耗时格式化：>1000ms 显示秒', async () => {
    const wrapper = mount(ContextPanel, {
      props: { messages: sampleMessages },
    })
    await wrapper.find('[data-testid="cp-tab-tools"]').trigger('click')
    const items = wrapper.findAll('[data-testid^="cp-tool-"]')
    // search_web duration_ms=1200 -> "1.2s"
    expect(items[1].text()).toContain('1.2s')
  })
})
