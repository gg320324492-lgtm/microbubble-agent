// KnowledgeEntityTab.list.test.js — W86 mini-7 实体列表 onMounted 自动 fetch
//
// 根因 (派工 v6 §1.2 真验证, 3 路搜证):
//   1. KnowledgeView.vue:454 onMounted 调 searchEntities({ page: 1, page_size: 1 })
//      → entityList.value = [1 item] + entityTotal.value = 131 (用户看到 "实体 131" 但列表只有 1 条)
//   2. KnowledgeEntityTab.vue:156-160 onMounted 只调 fetchEntityGraphLocal (W86 mini-6 fix),
//      **未**自动 searchEntitiesLocal → 必须 watch(activeTab) 触发才补 20 条.
//   3. 若用户直接在 ?tab=entities 落地 → activeTab 默认 'knowledge' → URL watcher 后改 'entities'
//      → activeTab watcher 触发 searchEntitiesLocal → emit list=20 → 列表补齐.
//   4. 但若 user 当前 activeTab 已是 'entities' (e.g. 直接路由命中或刷新), watcher 不触发,
//      entityList 永远停在 useKnowledge 初始化的 [1 item], 用户看到 1 条.
//
// 修复 (派工 v6 §1.2 + 派工 v4 铁律 3 + 派工前提铁律 12):
//   1. KnowledgeEntityTab.vue onMounted 同时调 fetchEntityGraphLocal + searchEntitiesLocal
//      (沿用 W86 mini-6 fixEntityGraphLocal 模式), entityList 为空时自动补 20 条.
//   2. KnowledgeView.vue handleEntityRefresh 加 guard: graph emit 不影响 list 状态
//      (避免 graph 数据单独更新时空 list 覆盖正确 list).
//
// 验证 (4 个 e2e 测试):
//   1. onMounted 触发后 emit 含 list 20 items + total 131
//   2. props.entityList 非空时 onMounted 不重复 search (避免 N 次重复)
//   3. emit list 后 props.entityList 通过 父组件 handleEntityRefresh 更新到 20 items
//   4. handleEntityRefresh guard: graph emit 不会覆盖 entityList
import { mount, flushPromises } from '@vue/test-utils'
import { describe, it, expect, vi, beforeEach } from 'vitest'

vi.mock('echarts', () => {
  const makeInstance = () => ({
    setOption: vi.fn(),
    on: vi.fn(),
    off: vi.fn(),
    dispose: vi.fn(),
    resize: vi.fn(),
  })
  return { default: { init: vi.fn(makeInstance) }, init: vi.fn(makeInstance) }
})

vi.mock('element-plus', () => ({
  ElMessage: { error: vi.fn(), success: vi.fn() },
}))

vi.mock('axios', () => ({
  default: {
    get: vi.fn(() => Promise.resolve({ data: { items: [], total: 0, nodes: [], edges: [] } })),
  },
}))

import KnowledgeEntityTab from '@/components/knowledge/KnowledgeEntityTab.vue'

describe('W86 mini-7 实体列表 onMounted 自动 fetch', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('Fix 1.1 onMounted 触发 → searchEntitiesLocal 自动调用, emit list 20 items + total 131', async () => {
    const axios = (await import('axios')).default
    // mock 顺序: 第 1 次 = fetchEntityGraphLocal (onMounted 调), 第 2 次 = searchEntitiesLocal (onMounted 调)
    axios.get.mockResolvedValueOnce({
      data: { nodes: [{ id: 1, subject: '微纳米气泡' }], edges: [] },
    })
    axios.get.mockResolvedValueOnce({
      data: {
        items: Array.from({ length: 20 }, (_, i) => ({
          id: i + 1,
          subject: `实体${i + 1}`,
          predicate: '关联',
          object: `对象${i + 1}`,
          confidence: 0.9,
          source_count: 1,
          occurrence_count: 1,
        })),
        total: 131,
      },
    })

    const wrapper = mount(KnowledgeEntityTab, {
      props: {
        entityList: [],          // 父组件 useKnowledge onMounted 初始化为 [1 item], 此处模拟初始空
        entityTotal: 0,
        entityPage: 1,
        entityGraphData: { nodes: [], edges: [] },
      },
    })

    await flushPromises()

    // 期望 onMounted 触发 fetchEntityGraphLocal + searchEntitiesLocal (W86 mini-7 fix)
    expect(axios.get).toHaveBeenCalled()
    const calledUrls = axios.get.mock.calls.map(c => c[0])

    // 验证 graph 调用
    expect(calledUrls.some(u => u.includes('/api/v1/knowledge/entities/graph'))).toBe(true)

    // 验证 search 调用 — 关键 (派工 v6 §1.2 实战: 老代码 search 不在 onMounted)
    // URL: '/api/v1/knowledge/entities' (无 ? 时是 search, 含 'graph' 是 graph endpoint)
    expect(calledUrls.some(u => /\/api\/v1\/knowledge\/entities(\?|$)/.test(u) && !u.includes('graph'))).toBe(true)

    // 验证 emit 含 list 20 items + total 131
    expect(wrapper.emitted('refresh')).toBeTruthy()
    const listEmit = wrapper.emitted('refresh').find(e => e[0]?.list !== undefined)
    expect(listEmit).toBeTruthy()
    expect(listEmit[0].list).toHaveLength(20)
    expect(listEmit[0].total).toBe(131)
  })

  it('Fix 1.2 onMounted 跳过 search — props.entityList 非空 (避免重复请求)', async () => {
    const axios = (await import('axios')).default
    axios.get.mockResolvedValue({
      data: { nodes: [{ id: 1, subject: '微纳米气泡' }], edges: [] },
    })

    const existingList = Array.from({ length: 20 }, (_, i) => ({
      id: i + 1,
      subject: `已加载${i + 1}`,
      predicate: '关联',
      object: `对象${i + 1}`,
    }))

    mount(KnowledgeEntityTab, {
      props: {
        entityList: existingList,  // 父组件已有 20 条
        entityTotal: 131,
        entityPage: 1,
        entityGraphData: { nodes: [{ id: 1 }], edges: [] },  // graph 已加载 → fetchEntityGraphLocal 跳过
      },
    })

    await flushPromises()

    const calledUrls = axios.get.mock.calls.map(c => c[0])
    // entityList 非空 → searchEntitiesLocal 不应触发 (避免 N 次重复)
    const searchCalls = calledUrls.filter(u => /\/api\/v1\/knowledge\/entities(\?|$)/.test(u) && !u.includes('graph'))
    expect(searchCalls).toHaveLength(0)
  })

  it('Fix 1.3 emit 后 handleEntityRefresh 父组件更新 entityList → 列表渲染 20 条', async () => {
    const axios = (await import('axios')).default
    axios.get.mockResolvedValueOnce({
      data: { nodes: [], edges: [] },
    })
    axios.get.mockResolvedValueOnce({
      data: {
        items: Array.from({ length: 20 }, (_, i) => ({
          id: i + 1,
          subject: `实体${i + 1}`,
          predicate: '关联',
          object: `对象${i + 1}`,
          confidence: 0.9,
          source_count: 1,
          occurrence_count: 1,
        })),
        total: 131,
      },
    })

    // 模拟 KnowledgeView 父组件: 用 v-model 风格接收 emit('refresh', { list, total })
    const wrapper = mount(KnowledgeEntityTab, {
      props: {
        entityList: [],  // 初始空 (useKnowledge 初始化后是 1 item, 这里测从空 → 20)
        entityTotal: 0,
        entityPage: 1,
        entityGraphData: { nodes: [], edges: [] },
      },
    })

    await flushPromises()

    // 模拟 KnowledgeView.handleEntityRefresh
    const refreshEmits = wrapper.emitted('refresh')
    const listEmit = refreshEmits.find(e => e[0]?.list)
    expect(listEmit).toBeTruthy()

    // 父组件更新 entityList prop
    await wrapper.setProps({
      entityList: listEmit[0].list,
      entityTotal: listEmit[0].total,
    })
    await flushPromises()

    // 验证 20 条 entity-card 渲染 (派工 v6 §1.2 实战: 列表应渲染 20 而非 1)
    const cards = wrapper.findAll('.entity-card')
    expect(cards).toHaveLength(20)

    // 验证 panel-count 文案
    expect(wrapper.text()).toContain('20 个实体')
  })

  it('Fix 1.4 handleEntityRefresh guard: graph emit 不会覆盖 entityList (派工 v6 §1.2)', async () => {
    // 模拟场景: graph emit payload = { graph: ... } (无 list 字段)
    // 父组件 handleEntityRefresh 接收后, payload.list === undefined → 不应覆盖 entityList
    // (避免 graph 单独更新时误覆盖列表, 保证用户已加载的列表不被清空)
    const axios = (await import('axios')).default
    axios.get.mockResolvedValueOnce({
      data: { nodes: [{ id: 1, subject: '微纳米气泡' }], edges: [] },
    })

    const existingList = Array.from({ length: 20 }, (_, i) => ({
      id: i + 1,
      subject: `已加载${i + 1}`,
      predicate: '关联',
      object: `对象${i + 1}`,
    }))

    const wrapper = mount(KnowledgeEntityTab, {
      props: {
        entityList: existingList,
        entityTotal: 131,
        entityPage: 1,
        entityGraphData: { nodes: [], edges: [] },
      },
    })

    await flushPromises()

    // 触发 fetchEntityGraphLocal (graph 单独 emit, 不应含 list)
    await wrapper.vm.fetchEntityGraphLocal()
    await flushPromises()

    // 验证 emit 含 graph 但不含 list (或 list 是 undefined, 不覆盖)
    const refreshEmits = wrapper.emitted('refresh')
    const graphEmit = refreshEmits.find(e => e[0]?.graph)
    expect(graphEmit).toBeTruthy()
    // graph emit 不应误传 list 字段 (派工 v6 §1.2 实战: list undefined 让父组件 guard 跳过)
    expect(graphEmit[0].list).toBeUndefined()
  })
})