// tests/KnowledgeEntityTab.test.js — W86 mini-4 KnowledgeEntityTab 单元测试
//
// 验证: W86 mini-4 升级后 KnowledgeEntityTab 正确导入 KnowledgeGraphExplorer
// - 组件可正常 mount (不报 import 错误)
// - 暴露 searchEntitiesLocal / fetchEntityGraphLocal (老 API 保持兼容)
// - KnowledgeGraphExplorer 子组件渲染 (节点/边 props 传递)
//
// 派工 v6 §1.2 实战: 真验证组件 import 链, 不只跑 build
import { mount, flushPromises } from '@vue/test-utils'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { ElMessage } from 'element-plus'

// mock axios 避免真实 HTTP 请求
vi.mock('axios', () => ({
  default: {
    get: vi.fn(() => Promise.resolve({ data: { items: [], total: 0, nodes: [], edges: [] } })),
  },
}))

// mock ECharts (KnowledgeGraphExplorer 内部依赖)
vi.mock('echarts', () => ({
  default: {
    init: vi.fn(() => ({
      setOption: vi.fn(),
      on: vi.fn(),
      off: vi.fn(),
      dispose: vi.fn(),
      resize: vi.fn(),
    })),
  },
  init: vi.fn(() => ({
    setOption: vi.fn(),
    on: vi.fn(),
    off: vi.fn(),
    dispose: vi.fn(),
    resize: vi.fn(),
  })),
}))

// mock ElMessage
vi.mock('element-plus', () => ({
  ElMessage: { error: vi.fn(), success: vi.fn() },
}))

import KnowledgeEntityTab from '@/components/knowledge/KnowledgeEntityTab.vue'
import KnowledgeGraphExplorer from '@/components/knowledge/KnowledgeGraphExplorer.vue'

describe('W86 mini-4 KnowledgeEntityTab', () => {
  it('正确导入 KnowledgeGraphExplorer 子组件 (派工 v6 实战真验证)', () => {
    // 验证子组件 import 成功 (W86 mini-4 fix 核心: 用 Phase 9 Explorer 替代老 ECharts option)
    expect(KnowledgeGraphExplorer).toBeDefined()
    expect(typeof KnowledgeGraphExplorer).toBe('object') // SFC is object
  })

  it('组件可 mount, KnowledgeGraphExplorer 渲染 (子组件 props 传递)', async () => {
    const wrapper = mount(KnowledgeEntityTab, {
      props: {
        entityList: [
          { id: 1, subject: '微纳米气泡', predicate: '直径', object: '100纳米', condition: null, confidence: 0.9, source_count: 2, occurrence_count: 5 },
        ],
        entityTotal: 1,
        entityPage: 1,
        entityGraphData: {
          nodes: [
            { id: 1, subject: '微纳米气泡', predicate: '直径', object: '100纳米', occurrence_count: 5 },
            { id: 2, subject: '超声', predicate: '频率', object: '20kHz', occurrence_count: 3 },
          ],
          edges: [
            { source: 1, target: 2, knowledge_id: 1, weight: 5.0 },
          ],
        },
      },
    })

    await flushPromises()
    // KnowledgeGraphExplorer 应该被渲染 (W86 mini-4 核心 fix)
    expect(wrapper.findComponent(KnowledgeGraphExplorer).exists()).toBe(true)
  })

  it('暴露 searchEntitiesLocal / fetchEntityGraphLocal API (老 API 兼容)', () => {
    const wrapper = mount(KnowledgeEntityTab, {
      props: {
        entityList: [],
        entityTotal: 0,
        entityPage: 1,
        entityGraphData: { nodes: [], edges: [] },
      },
    })
    // defineExpose 保留老 API (KnowledgeView 可能调用)
    expect(typeof wrapper.vm.searchEntitiesLocal).toBe('function')
    expect(typeof wrapper.vm.fetchEntityGraphLocal).toBe('function')
  })

  it('fetchEntityGraphLocal 触发 API 调用, 写 entityGraphData', async () => {
    const axios = (await import('axios')).default
    // W86 mini-6: onMounted 先调一次 (默认 mock 返回空), fetchEntityGraphLocal 排第 2 个 mock
    axios.get.mockResolvedValueOnce({
      data: { nodes: [], edges: [] },
    })
    axios.get.mockResolvedValueOnce({
      data: {
        nodes: [{ id: 99, subject: '测试', predicate: 't', object: 't' }],
        edges: [{ source: 99, target: 99, knowledge_id: 1, weight: 1.0 }],
      },
    })

    const wrapper = mount(KnowledgeEntityTab, {
      props: {
        entityList: [],
        entityTotal: 0,
        entityPage: 1,
        entityGraphData: { nodes: [], edges: [] },
      },
    })

    // W86 mini-6: 等 onMounted 完成
    await flushPromises()

    await wrapper.vm.fetchEntityGraphLocal()
    await flushPromises()

    // 验证 emit('refresh', { graph: ... }) — 至少有一次含 graph
    expect(wrapper.emitted('refresh')).toBeTruthy()
    const refreshEmits = wrapper.emitted('refresh')
    const graphEmit = refreshEmits.find(e => e[0]?.graph?.nodes?.length === 1)
    expect(graphEmit).toBeTruthy()
    expect(graphEmit[0].graph.nodes).toHaveLength(1)
    expect(graphEmit[0].graph.edges).toHaveLength(1)
  })

  it('searchEntitiesLocal 处理搜索参数 + 触发 emit', async () => {
    const axios = (await import('axios')).default
    // W86 mini-6: onMounted 会先调一次 fetchEntityGraphLocal (auto-fetch),
    //   searchEntitiesLocal 排第 2 个 mockResolvedValueOnce
    axios.get.mockResolvedValueOnce({
      data: { nodes: [], edges: [] },
    })
    axios.get.mockResolvedValueOnce({
      data: { items: [{ id: 5, subject: '搜索结果' }], total: 1 },
    })

    const wrapper = mount(KnowledgeEntityTab, {
      props: {
        entityList: [],
        entityTotal: 0,
        entityPage: 1,
        entityGraphData: { nodes: [], edges: [] },
      },
    })

    // W86 mini-6: 等 onMounted 触发的 fetchEntityGraphLocal 完成
    await flushPromises()

    await wrapper.vm.searchEntitiesLocal()
    await flushPromises()

    expect(wrapper.emitted('refresh')).toBeTruthy()
    // 找到 list emit (可能是第二个, 因为 onMounted 先 emit graph)
    const refreshEmits = wrapper.emitted('refresh')
    const searchEmit = refreshEmits.find(e => e[0]?.list !== undefined)
    expect(searchEmit).toBeTruthy()
    expect(searchEmit[0].list).toHaveLength(1)
    expect(searchEmit[0].total).toBe(1)
  })
})
