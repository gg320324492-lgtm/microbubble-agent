/**
 * 测试 v2 前端 — SSE 客户端 + RichContent 分发
 *
 * 跑法（在 web 目录）：npm run test:unit -- chatSSE
 */
import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { defineComponent, h } from 'vue'

// ============================================================
// 1. SSE 客户端测试（mock fetch + ReadableStream）
// ============================================================

describe('sseFetch', () => {
  beforeEach(() => {
    localStorage.clear()
  })

  it('正常解析多帧 SSE 流', async () => {
    // 构造一个 ReadableStream，输出 3 帧 + [DONE]
    const encoder = new TextEncoder()
    const frames = [
      'data: {"type":"thinking","label":"正在分析..."}\n\n',
      'data: {"type":"tool_use","tool_name":"query_meetings"}\n\n',
      'data: {"type":"text_delta","delta":"你好"}\n\n',
      'data: {"type":"done","duration_ms":1500}\n\n',
      'data: [DONE]\n\n'
    ]
    let idx = 0
    const stream = new ReadableStream({
      pull(controller) {
        if (idx < frames.length) {
          controller.enqueue(encoder.encode(frames[idx++]))
        } else {
          controller.close()
        }
      }
    })

    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      body: stream,
      text: async () => ''
    })

    const { sseFetch } = await import('@/api/agent/sse')
    const events = []
    for await (const evt of sseFetch('/api/v1/chat/stream', { message: 'hi', session_id: 's1' })) {
      events.push(evt)
    }

    expect(events.length).toBe(4)
    expect(events[0].type).toBe('thinking')
    expect(events[0].label).toBe('正在分析...')
    expect(events[1].type).toBe('tool_use')
    expect(events[1].tool_name).toBe('query_meetings')
    expect(events[2].type).toBe('text_delta')
    expect(events[2].delta).toBe('你好')
    expect(events[3].type).toBe('done')
    expect(events[3].duration_ms).toBe(1500)
  })

  it('HTTP 错误时抛出', async () => {
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 500,
      text: async () => 'Internal Server Error'
    })
    const { sseFetch } = await import('@/api/agent/sse')
    await expect(async () => {
      for await (const _ of sseFetch('/api/v1/chat/stream', {})) {}
    }).rejects.toThrow(/HTTP 500/)
  })

  it('带 Bearer token', async () => {
    localStorage.setItem('access_token', 'fake-jwt-token')
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 401,
      text: async () => 'unauth'
    })
    const { sseFetch } = await import('@/api/agent/sse')
    try {
      for await (const _ of sseFetch('/api/v1/chat/stream', {})) {}
    } catch {}
    expect(globalThis.fetch).toHaveBeenCalledWith(
      '/api/v1/chat/stream',
      expect.objectContaining({
        method: 'POST',
        headers: expect.objectContaining({ 'Authorization': 'Bearer fake-jwt-token' })
      })
    )
  })
})


// 2026-07-12: TOOL_LABELS describe 块已删除 (对应 @/api/agent/toolLabels.ts 已清理, 孤儿 API)


// ============================================================
// 3. RichContent 注册表测试
// ============================================================

describe('RichContent registry', () => {
  it('type 映射到正确组件', async () => {
    const { resolveBlock } = await import('@/components/chat/blocks/registry')
    expect(resolveBlock('meeting')).toBeDefined()
    expect(resolveBlock('task_list')).toBeDefined()
    expect(resolveBlock('knowledge_ref')).toBeDefined()
    expect(resolveBlock('member')).toBeDefined()
    expect(resolveBlock('fallback')).toBeDefined()
  })

  it('未知 type fallback 到 FallbackBlock', async () => {
    const { resolveBlock } = await import('@/components/chat/blocks/registry')
    const fb = resolveBlock('some_unknown_type_xyz')
    expect(fb).toBeDefined()
    // fallback 和未知 type 应该是同一个组件
    const fallback = resolveBlock('fallback')
    expect(fb).toBe(fallback)
  })

  it('registerBlock 动态注册新 type', async () => {
    const { resolveBlock, registerBlock } = await import('@/components/chat/blocks/registry')
    const TestComponent = defineComponent({ name: 'TestComp', render: () => h('div', 'test') })
    registerBlock('test_custom_type', TestComponent)
    expect(resolveBlock('test_custom_type')).toBe(TestComponent)
  })
})


// ============================================================
// 4. RichContent 渲染测试
// ============================================================

describe('RichContent.vue', () => {
  it('按 block.type 分发到正确组件', async () => {
    const RichContent = (await import('@/components/chat/RichContent.vue')).default
    const wrapper = mount(RichContent, {
      props: { block: { type: 'meeting', data: { meetings: [] } } }
    })
    expect(wrapper.find('.meeting-card').exists()).toBe(true)
  })

  it('未知 type 渲染为 fallback', async () => {
    const RichContent = (await import('@/components/chat/RichContent.vue')).default
    const wrapper = mount(RichContent, {
      props: { block: { type: 'unknown_xyz', data: { content: 'hello' } } }
    })
    expect(wrapper.find('.fallback-block').exists()).toBe(true)
  })
})


// ============================================================
// 5. MeetingCard 组件数据格式测试
// ============================================================

describe('MeetingCard 数据兼容', () => {
  it('支持单个会议数据 (id + title)', async () => {
    const MeetingCard = (await import('@/components/chat/blocks/MeetingCard.vue')).default
    const wrapper = mount(MeetingCard, {
      props: { block: { type: 'meeting', data: { id: 1, title: '例会', status: 'completed' } } }
    })
    expect(wrapper.find('.meeting-card').exists()).toBe(true)
    expect(wrapper.text()).toContain('例会')
  })

  it('支持列表数据 (meetings: [...])', async () => {
    const MeetingCard = (await import('@/components/chat/blocks/MeetingCard.vue')).default
    const wrapper = mount(MeetingCard, {
      props: { block: { type: 'meeting', data: { meetings: [
        { id: 1, title: 'A' }, { id: 2, title: 'B' }
      ] } } }
    })
    expect(wrapper.text()).toContain('A')
    expect(wrapper.text()).toContain('B')
  })

  it('支持分组数据 (groups: [...])', async () => {
    const MeetingCard = (await import('@/components/chat/blocks/MeetingCard.vue')).default
    const wrapper = mount(MeetingCard, {
      props: { block: { type: 'meeting', data: { groups: [
        { date: '2026-06-12', meeting_id: 1, title: 'X' }
      ] } } }
    })
    expect(wrapper.text()).toContain('X')
  })
})
