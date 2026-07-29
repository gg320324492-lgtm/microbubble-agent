// KnowledgeGraphLabel.test.js — W86 mini-5 图谱节点 label 修复单元测试
//
// 根因 (派工 v6 §1.2 真验证): entity_service._entity_to_dict 只返
// subject / predicate / object 三元组, 无 name / label / title / text
// → normalizeGraphData 老优先级链 fallback 到 id → 节点标数字 (entity_id 1-65).
//
// 验证:
//   1. entity 节点 name 取 subject (而非 id 数字)
//   2. object / predicate 兜底顺序
//   3. 通用字段 (name/label/title/text) 优先级不被 subject 抢占 (不破坏 paper 图谱)
//   4. 全部 fallback 缺失时仍退回 id (保留老 fallback chain)
//   5. ECharts option.series[0].data[].name 落到 subject
//   6. ResizeObserver 绑定 + unmount 时 disconnect (自适应高度)
import { mount, flushPromises } from '@vue/test-utils'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { normalizeGraphData } from '@/utils/paperAdapter'

const setOptionSpy = vi.fn()
vi.mock('echarts', () => {
  const makeInstance = () => ({
    setOption: (...args) => setOptionSpy(...args),
    on: vi.fn(),
    off: vi.fn(),
    dispose: vi.fn(),
    resize: vi.fn(),
  })
  return { default: { init: vi.fn(makeInstance) }, init: vi.fn(makeInstance) }
})

import KnowledgeGraphExplorer from '@/components/knowledge/KnowledgeGraphExplorer.vue'

// entity_service._entity_to_dict 的真实返回形状 (无 name/label/title/text)
const entityNodes = [
  { id: 1, subject: '微纳米气泡', predicate: '直径', object: '100纳米', occurrence_count: 5 },
  { id: 2, subject: '超声空化', predicate: '频率', object: '20kHz', occurrence_count: 3 },
]
const entityEdges = [{ source: 1, target: 2, knowledge_id: 1, weight: 5.0 }]

describe('W86 mini-5 图谱节点 label (normalizeGraphData)', () => {
  it('entity 节点 name 取 subject 而非 entity_id 数字 (核心 fix)', () => {
    const { nodes } = normalizeGraphData({ nodes: entityNodes, edges: entityEdges })
    expect(nodes).toHaveLength(2)
    expect(nodes[0].name).toBe('微纳米气泡')
    expect(nodes[1].name).toBe('超声空化')
    // 回归防护: 修复前这里是 '1' / '2'
    expect(nodes[0].name).not.toBe('1')
    expect(nodes[0].name).not.toBe(String(nodes[0].id))
  })

  it('id 仍保持 entity_id (节点点击回查详情依赖 id, 不能被 subject 顶替)', () => {
    const { nodes, links } = normalizeGraphData({ nodes: entityNodes, edges: entityEdges })
    expect(nodes.map(n => n.id)).toEqual(['1', '2'])
    // links 端点仍能匹配上 nodeIds, 边没被过滤掉
    expect(links).toHaveLength(1)
    expect(links[0]).toMatchObject({ source: '1', target: '2' })
  })

  it('subject 缺失时按 object → predicate 兜底', () => {
    const { nodes } = normalizeGraphData({
      nodes: [
        { id: 10, object: '仅对象', predicate: 'p' },
        { id: 11, predicate: '仅关系' },
      ],
      edges: [],
    })
    expect(nodes[0].name).toBe('仅对象')
    expect(nodes[1].name).toBe('仅关系')
  })

  it('通用展示字段优先级高于 subject (不破坏 paper / topic 图谱)', () => {
    const { nodes } = normalizeGraphData({
      nodes: [
        { id: 20, name: '论文标题', subject: '不该被选中' },
        { id: 21, label: '标签名', subject: '不该被选中' },
        { id: 22, title: '标题名', subject: '不该被选中' },
        { id: 23, text: '文本名', subject: '不该被选中' },
      ],
      edges: [],
    })
    expect(nodes.map(n => n.name)).toEqual(['论文标题', '标签名', '标题名', '文本名'])
  })

  it('所有展示字段缺失时退回 id (保留老 fallback chain)', () => {
    const { nodes } = normalizeGraphData({ nodes: [{ id: 42 }], edges: [] })
    expect(nodes[0].name).toBe('42')
  })
})

describe('W86 mini-5 KnowledgeGraphExplorer 渲染 + 自适应高度', () => {
  beforeEach(() => setOptionSpy.mockClear())

  it('ECharts series data[].name 落到 subject (端到端到 option 层)', async () => {
    mount(KnowledgeGraphExplorer, {
      props: { nodes: entityNodes, edges: entityEdges, loading: false },
      attachTo: document.body,
    })
    await flushPromises()

    expect(setOptionSpy).toHaveBeenCalled()
    const option = setOptionSpy.mock.calls[0][0]
    const data = option.series[0].data
    expect(data.map(d => d.name)).toEqual(['微纳米气泡', '超声空化'])
    // label.formatter '{b}' 渲染的就是 name, 所以 name 正确即节点文字正确
    expect(option.series[0].label.show).toBe(true)
    expect(option.series[0].label.formatter).toBe('{b}')
  })

  it('loading / 空数据时不初始化图表 (不报错)', async () => {
    const wrapper = mount(KnowledgeGraphExplorer, {
      props: { nodes: [], edges: [], loading: false },
    })
    await flushPromises()
    expect(wrapper.find('.kg-chart').exists()).toBe(false)
    expect(setOptionSpy).not.toHaveBeenCalled()
  })

  it('mount 时 observe chartRef, unmount 时 disconnect (父容器高度自适应)', async () => {
    const observe = vi.fn()
    const disconnect = vi.fn()
    const original = global.ResizeObserver
    global.ResizeObserver = class {
      constructor(cb) { this.cb = cb }
      observe(...a) { observe(...a) }
      disconnect() { disconnect() }
    }

    try {
      const wrapper = mount(KnowledgeGraphExplorer, {
        props: { nodes: entityNodes, edges: entityEdges, loading: false },
        attachTo: document.body,
      })
      await flushPromises()
      expect(observe).toHaveBeenCalled()

      wrapper.unmount()
      expect(disconnect).toHaveBeenCalled()
    } finally {
      global.ResizeObserver = original
    }
  })

  it('无 ResizeObserver 环境降级不抛错 (老浏览器兜底)', async () => {
    const original = global.ResizeObserver
    // eslint-disable-next-line no-undefined
    global.ResizeObserver = undefined
    try {
      const wrapper = mount(KnowledgeGraphExplorer, {
        props: { nodes: entityNodes, edges: entityEdges, loading: false },
        attachTo: document.body,
      })
      await flushPromises()
      expect(() => wrapper.unmount()).not.toThrow()
    } finally {
      global.ResizeObserver = original
    }
  })
})
