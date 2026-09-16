// @vitest-environment jsdom
// 工具卡片 / thinking 折叠面板 / live 事件累积 — Agent UI 契约（工单 C-2 §5）
import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import ToolCard from '@renderer/components/chat/ToolCard.vue'
import ThinkingPanel from '@renderer/components/chat/ThinkingPanel.vue'
import { applyStreamEvent, createLiveState } from '@renderer/stores/chat-events'
import type { ChatStreamEvent, ToolCallRecord } from '@shared/types'

const runningCall: ToolCallRecord = { id: 't1', name: 'list_dir', input: { path: '.' }, status: 'running', summary: '运行中…' }

function mountToolCard(call: ToolCallRecord) {
  return mount(ToolCard, { props: { call } })
}

describe('ToolCard 工具卡片', () => {
  it('运行中状态渲染工具名与状态，默认收起；点击展开详情', async () => {
    const wrapper = mountToolCard(runningCall)
    expect(wrapper.get('[data-testid="tool-card"]').classes()).toContain('is-running')
    expect(wrapper.get('[data-testid="tool-status"]').text()).toContain('运行中')
    expect(wrapper.text()).toContain('list_dir')
    expect(wrapper.find('[data-testid="tool-detail"]').exists()).toBe(false)
    await wrapper.get('.tool-head').trigger('click')
    expect(wrapper.get('[data-testid="tool-detail"]').text()).toContain('运行中…')
  })

  it('成功状态流转 — 换 props 后显示成功并展开可见 data JSON', async () => {
    const wrapper = mountToolCard({ ...runningCall, status: 'ok', summary: '目录 . 共 2 项', data: { entries: ['notes.md'] } })
    expect(wrapper.get('[data-testid="tool-card"]').classes()).toContain('is-ok')
    expect(wrapper.get('[data-testid="tool-status"]').text()).toContain('成功')
    await wrapper.get('.tool-head').trigger('click')
    expect(wrapper.get('[data-testid="tool-detail"]').text()).toContain('共 2 项')
    expect(wrapper.get('.detail-data').text()).toContain('notes.md')
  })

  it('失败状态 — is-error 类与失败标识', () => {
    const wrapper = mountToolCard({ ...runningCall, status: 'error', summary: '目录不存在', input: { path: 'nope' } })
    expect(wrapper.get('[data-testid="tool-card"]').classes()).toContain('is-error')
    expect(wrapper.get('[data-testid="tool-status"]').text()).toContain('失败')
  })
})

describe('ThinkingPanel thinking 折叠面板', () => {
  it('默认折叠，点击「思考过程」展开全文，再点收起', async () => {
    const wrapper = mount(ThinkingPanel, { props: { text: '先查目录结构，再读文件。' } })
    expect(wrapper.find('[data-testid="thinking-content"]').exists()).toBe(false)
    await wrapper.get('[data-testid="thinking-toggle"]').trigger('click')
    expect(wrapper.get('[data-testid="thinking-content"]').text()).toContain('先查目录结构')
    expect(wrapper.get('[data-testid="thinking-toggle"]').attributes('aria-expanded')).toBe('true')
    await wrapper.get('[data-testid="thinking-toggle"]').trigger('click')
    expect(wrapper.find('[data-testid="thinking-content"]').exists()).toBe(false)
  })
})

describe('live 事件累积（chat-events）', () => {
  it('delta/thinking 追加、tool 同 id 整卡替换、round 更新', () => {
    const live = createLiveState()
    const events: ChatStreamEvent[] = [
      { type: 'round', sessionId: 's', messageId: 'm', round: 1, label: '第 1 轮 · 正在思考…' },
      { type: 'thinking', sessionId: 's', messageId: 'm', delta: '想一想' },
      { type: 'delta', sessionId: 's', messageId: 'm', delta: '你好' },
      { type: 'delta', sessionId: 's', messageId: 'm', delta: '，世界' },
      { type: 'tool', sessionId: 's', messageId: 'm', call: runningCall },
      { type: 'tool', sessionId: 's', messageId: 'm', call: { ...runningCall, status: 'ok', summary: '完成' } },
      { type: 'round', sessionId: 's', messageId: 'm', round: 2, label: '第 2 轮 · 正在思考…' }
    ]
    for (const e of events) applyStreamEvent(live, e)
    expect(live.text).toBe('你好，世界')
    expect(live.thinking).toBe('想一想')
    expect(live.round).toBe(2)
    expect(live.label).toContain('第 2 轮')
    expect(live.tools).toHaveLength(1) // 同 id 替换而非追加
    expect(live.tools[0].status).toBe('ok')
  })
})
