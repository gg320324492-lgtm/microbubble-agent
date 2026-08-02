import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import { defineComponent, h } from 'vue'
import ToolTraceItem from '@/components/chat/ToolTraceItem.vue'

const MessageListHarness = defineComponent({
  props: { messages: { type: Array, required: true } },
  setup(props) {
    return () => h('section', props.messages.map((message: any) => h('article', {
      key: message.id,
      class: `message-${message.role}`,
    }, message.content)))
  },
})

function makeMessages(count: number) {
  return Array.from({ length: count }, (_, index) => ({
    id: `message-${index}`,
    role: index % 2 === 0 ? 'user' : 'assistant',
    content: `微纳米气泡性能基线消息 ${index}`,
    timestamp: new Date(1_700_000_000_000 + index * 1_000).toISOString(),
  }))
}

describe('chat 1000 item performance baseline', () => {
  it('mounts 1000 chat messages in jsdom', () => {
    const startedAt = performance.now()
    const wrapper = mount(MessageListHarness, { props: { messages: makeMessages(1000) } })
    const durationMs = performance.now() - startedAt

    expect(wrapper.findAll('article')).toHaveLength(1000)
    expect(durationMs).toBeLessThan(5_000)
    console.info(`[perf] Chat message harness x1000 mount: ${durationMs.toFixed(2)}ms`)
  })

  it('mounts 1000 ToolTraceItem instances in jsdom', () => {
    const traces = Array.from({ length: 1000 }, (_, index) => h(ToolTraceItem, {
      trace: {
        type: 'tool',
        name: `search_knowledge_${index}`,
        state: 'done',
        duration_ms: index + 1,
        tool_output: { results: [{ id: index, title: `result-${index}` }] },
        tool_output_preview: `result-${index}`,
      },
      index,
    }))
    const Harness = defineComponent({ setup: () => () => h('section', traces) })

    const startedAt = performance.now()
    const wrapper = mount(Harness)
    const durationMs = performance.now() - startedAt

    expect(wrapper.findAll('.tti-tool')).toHaveLength(1000)
    expect(durationMs).toBeLessThan(10_000)
    console.info(`[perf] ToolTraceItem x1000 mount: ${durationMs.toFixed(2)}ms`)
  })
})
