// KnowledgeEntityTab.color.test.js — W86 mini-6 图谱按 predicate/subject 着色 + 切 tab 自动 fetch
//
// 根因 (派工 v6 §1.2 真验证):
//   1. paperAdapter.normalizeGraphData 老代码 `n.category || n.type || n.group || 'default'`
//      对 entity 三元组 (无 category 字段) 全部 fallback 到 'default' → categories 只 1 项
//      → ECharts legend 隐藏 → 所有节点同色 (全蓝).
//   2. KnowledgeEntityTab.fetchEntityGraphLocal 只 emit('refresh') 不直接 fetch,
//      用户首次进入实体 tab 看到空图, 必须手动点"刷新图谱"才能加载.
//
// 修复:
//   1. paperAdapter.normalizeGraphData 新增 _getCategoryFromSubject 按 subject 关键词派生
//      5 类 category (substance/method/parameter/equipment/concept) + 5 色 palette.
//   2. KnowledgeEntityTab.onMounted 在 entityGraphData 为空时自动调 fetchEntityGraphLocal,
//      配合父组件 watch(activeTab) 实现"切 tab 即加载, 不需手动刷新".
//
// 验证 (6 个 e2e 测试):
//   1. entity 节点 (subject='溶液pH') → category='parameter' + 颜色 #FFE66D
//   2. entity 节点 (subject='微纳米气泡') → category='substance' + 颜色 #FF6B6B
//   3. entity 节点 (subject='臭氧氧化法') → category='method' + 颜色 #4ECDC4
//   4. entity 节点 (subject='反应器') → category='equipment' + 颜色 #95E1D3
//   5. entity 节点 (subject='未知概念') → category='concept' + 颜色 #A8DADC
//   6. KnowledgeEntityTab onMounted → fetchEntityGraphLocal 自动调用 ≥1 次
import { mount, flushPromises } from '@vue/test-utils'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { normalizeGraphData } from '@/utils/paperAdapter'

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

// 5 类颜色 (与 paperAdapter.js CATEGORY_COLORS 同步)
const CATEGORY_COLORS = {
  substance:  '#FF6B6B',
  method:     '#4ECDC4',
  parameter:  '#FFE66D',
  equipment:  '#95E1D3',
  concept:    '#A8DADC',
}

describe('W86 mini-6 图谱按 predicate/subject 着色', () => {
  it('Fix 1.1 entity 节点 (subject="溶液pH") → category="parameter" + 颜色 #FFE66D', () => {
    const { nodes, categories } = normalizeGraphData({
      nodes: [{ id: 1, subject: '溶液pH', predicate: '值', object: '7' }],
      edges: [],
    })
    expect(nodes).toHaveLength(1)
    expect(nodes[0].category).toBe('parameter')
    const cat = categories.find(c => c.name === 'parameter')
    expect(cat).toBeTruthy()
    expect(cat.itemStyle.color).toBe(CATEGORY_COLORS.parameter)
  })

  it('Fix 1.2 entity 节点 (subject="微纳米气泡") → category="substance" + 颜色 #FF6B6B', () => {
    const { nodes, categories } = normalizeGraphData({
      nodes: [{ id: 1, subject: '微纳米气泡', predicate: '直径', object: '100纳米' }],
      edges: [],
    })
    expect(nodes[0].category).toBe('substance')
    const cat = categories.find(c => c.name === 'substance')
    expect(cat.itemStyle.color).toBe(CATEGORY_COLORS.substance)
  })

  it('Fix 1.3 entity 节点 (subject="臭氧氧化法") → category="method" + 颜色 #4ECDC4', () => {
    const { nodes, categories } = normalizeGraphData({
      nodes: [{ id: 1, subject: '臭氧氧化法', predicate: '效率', object: '95%' }],
      edges: [],
    })
    expect(nodes[0].category).toBe('method')
    const cat = categories.find(c => c.name === 'method')
    expect(cat.itemStyle.color).toBe(CATEGORY_COLORS.method)
  })

  it('Fix 1.4 entity 节点 (subject="反应器") → category="equipment" + 颜色 #95E1D3', () => {
    const { nodes, categories } = normalizeGraphData({
      nodes: [{ id: 1, subject: '反应器', predicate: '容量', object: '10L' }],
      edges: [],
    })
    expect(nodes[0].category).toBe('equipment')
    const cat = categories.find(c => c.name === 'equipment')
    expect(cat.itemStyle.color).toBe(CATEGORY_COLORS.equipment)
  })

  it('Fix 1.5 entity 节点 (subject="未知概念") → category="concept" + 颜色 #A8DADC (兜底)', () => {
    const { nodes, categories } = normalizeGraphData({
      nodes: [{ id: 1, subject: '未知概念', predicate: '关联', object: '其他' }],
      edges: [],
    })
    expect(nodes[0].category).toBe('concept')
    const cat = categories.find(c => c.name === 'concept')
    expect(cat.itemStyle.color).toBe(CATEGORY_COLORS.concept)
  })

  it('Fix 1.6 5 类混合节点 → categories 含 5 项 itemStyle.color 全部映射', () => {
    const { categories } = normalizeGraphData({
      nodes: [
        { id: 1, subject: '溶液pH' },          // parameter
        { id: 2, subject: '微纳米气泡' },      // substance
        { id: 3, subject: '臭氧氧化法' },      // method
        { id: 4, subject: '反应器' },          // equipment
        { id: 5, subject: '未知概念' },        // concept
      ],
      edges: [],
    })
    expect(categories).toHaveLength(5)
    // 所有 5 类都有颜色 (回归防护: 老代码只 1 类 'default' 无颜色)
    for (const cat of categories) {
      expect(cat.itemStyle.color).toMatch(/^#[0-9A-F]{6}$/i)
      expect(Object.values(CATEGORY_COLORS)).toContain(cat.itemStyle.color)
    }
  })

  it('Fix 1.7 回归防护: 老 default category 不应出现 (派工 v6 §1.2)', () => {
    const { categories, nodes } = normalizeGraphData({
      nodes: [
        { id: 1, subject: '溶液' },
        { id: 2, subject: '催化剂' },
      ],
      edges: [],
    })
    // 所有 node category 都不应是 'default'
    for (const n of nodes) {
      expect(n.category).not.toBe('default')
    }
    // categories 列表不含 'default' (派工 v6 §1.2 实战: 老 bug 即 'default' 全蓝)
    expect(categories.find(c => c.name === 'default')).toBeUndefined()
  })

  it('Fix 1.8 显式 n.category 也走关键词校验 (例如 category="solution")', () => {
    // 防御: 后端若显式标 category='solution' (而非 entity subject), 也应映射到 substance
    const { nodes } = normalizeGraphData({
      nodes: [{ id: 1, subject: '其他', category: '溶液' }],
      edges: [],
    })
    expect(nodes[0].category).toBe('substance')
  })

  it('Fix 2.1 KnowledgeEntityTab onMounted → fetchEntityGraphLocal 自动调用 ≥1 次 (切 tab 不需手动)', async () => {
    const axios = (await import('axios')).default
    axios.get.mockClear()
    axios.get.mockResolvedValue({
      data: { nodes: [{ id: 1, subject: '微纳米气泡' }], edges: [] },
    })

    const wrapper = mount(KnowledgeEntityTab, {
      props: {
        entityList: [],
        entityTotal: 0,
        entityPage: 1,
        entityGraphData: { nodes: [], edges: [] },  // 空 → 触发 onMounted fetch
      },
    })

    await flushPromises()
    // onMounted 应至少调 1 次 axios.get('/api/v1/knowledge/entities/graph')
    expect(axios.get).toHaveBeenCalled()
    const calledUrls = axios.get.mock.calls.map(c => c[0])
    expect(calledUrls.some(u => u.includes('/api/v1/knowledge/entities/graph'))).toBe(true)

    // 应 emit('refresh', { graph: ... })
    expect(wrapper.emitted('refresh')).toBeTruthy()
    const graphEmit = wrapper.emitted('refresh').find(e => e[0]?.graph)
    expect(graphEmit).toBeTruthy()
    expect(graphEmit[0].graph.nodes).toHaveLength(1)
  })

  it('Fix 2.2 KnowledgeEntityTab onMounted 跳过 — props 已含 nodes (避免重复请求)', async () => {
    const axios = (await import('axios')).default
    axios.get.mockClear()

    const wrapper = mount(KnowledgeEntityTab, {
      props: {
        entityList: [],
        entityTotal: 0,
        entityPage: 1,
        entityGraphData: {
          nodes: [{ id: 99, subject: '已加载', predicate: 'x', object: 'y' }],
          edges: [],
        },
      },
    })

    await flushPromises()
    // props 已含 nodes → onMounted 不应再调 axios.get (避免 N 次重复)
    // (用户切换 tab 时父组件 watch 仍会触发, 这里只验证初次 onMounted 不重复)
    const calledUrls = axios.get.mock.calls.map(c => c[0])
    expect(calledUrls.filter(u => u.includes('/api/v1/knowledge/entities/graph'))).toHaveLength(0)
  })
})