/**
 * kb-monitor-dashboard.spec.js — W71 B-5 Dashboard MVP 补全 e2e
 *
 * 子 plan ② 收口 (docs/chatgpt-structured-floyd-w69-plan.md §2.5):
 *   Dashboard MVP 补 2 el-card (7 天入库数 + 7 天回滚数) + 5min polling + 5 新 ECharts 卡片.
 *   (W68 第 7 批 A-4 `bc3a60619` 已交付 4 ECharts 子图, 本任务补齐缺口)
 *
 * 4 场景 (锚点范式第 200 守恒):
 *   scenario_1: 2 新 el-card 渲染 (7 天入库 + 7 天回滚) + summary 数值透传
 *   scenario_2: 5min polling 触发 (useKbMonitor setInterval 5*60*1000, mock axios 1 次 fetch)
 *   scenario_3: 5 个新 ECharts 卡片渲染 (7天入库/7天回滚/5道防线/7维评分/抽检率)
 *   scenario_4: 4 旧 ECharts 子图仍在 (入库趋势/失败率/重试/队列, 回归守卫)
 *
 * 设计 (0 production code 改动铁律 16/15 守恒, web/src/views/admin/ 派工 v6 允许):
 *   - vitest + @vue/test-utils, 不依赖真实浏览器
 *   - mock @/api/kbMonitor 三函数 + @/composables/useKbMonitor summary
 *   - mock echarts.init → 记录 9 次调用 (4 旧 + 5 新)
 *   - scenario_2 直接测 useKbMonitor 真实 setInterval (vi.useFakeTimers + mock axios)
 */

import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import { ref } from 'vue'
import { mount, flushPromises } from '@vue/test-utils'

// === mock echarts: 记录 init 次数 (期望 9 = 4 旧 + 5 新) ===
const initCalls = []
const chartStub = {
  setOption: vi.fn(),
  resize: vi.fn(),
  dispose: vi.fn(),
}
vi.mock('echarts', () => ({
  init: vi.fn((el) => {
    initCalls.push(el)
    return chartStub
  }),
}))

// === mock kbMonitor API (overview/queue/failures) ===
const fixtures = {
  overview: {
    hours: 24, ingested: 42, done: 38, failed: 3, retrying: 1,
    queue_depth: 6, success_rate: 0.9048, polling_interval_sec: 300,
    status_counts: { done: 38, failed: 3, pending: 1 },
    trend: [
      { hour: '2026-07-24T08:00:00', ingested: 10, done: 9, failed: 1 },
      { hour: '2026-07-24T09:00:00', ingested: 15, done: 14, failed: 1 },
    ],
  },
  queue: { pending: 5, analyzing: 1, queue_depth: 6, polling_interval_sec: 300, batch_size: 50, eta_minutes: 5.0 },
  failures: { items: [], total: 0 },
}
const fetchKbOverview = vi.fn(() => Promise.resolve(fixtures.overview))
const fetchKbQueueDepth = vi.fn(() => Promise.resolve(fixtures.queue))
const fetchKbFailures = vi.fn(() => Promise.resolve(fixtures.failures))
vi.mock('@/api/kbMonitor', () => ({
  fetchKbOverview: (...a) => fetchKbOverview(...a),
  fetchKbQueueDepth: (...a) => fetchKbQueueDepth(...a),
  fetchKbFailures: (...a) => fetchKbFailures(...a),
}))

// === mock useKbMonitor: 暴露可控 summary (7 天入库/回滚) ===
const summaryRef = ref({
  today_intake: 12,
  weekly_intake: [10, 15, 17, 20, 22, 18, 18], // 求和 = 120 (本周新增)
  hit_rate: 0.87,
  negative_feedback_rate: 0.05,
  rollback_count: 8, // 本周回滚
  last_update: '2026-07-24T10:00:00',
  gray_scale_enabled: 100,
  total_in_db: 340,
})
vi.mock('@/composables/useKbMonitor', () => ({
  useKbMonitor: () => ({
    summary: summaryRef,
    lastUpdate: ref(new Date('2026-07-24T10:00:00')),
    error: ref(null),
    loading: ref(false),
    refresh: vi.fn(),
    startPolling: vi.fn(),
    stopPolling: vi.fn(),
  }),
}))

// element-plus ElMessage 兜底
vi.mock('element-plus', async (orig) => {
  const actual = await orig().catch(() => ({}))
  return { ...actual, ElMessage: { error: vi.fn(), success: vi.fn() } }
})

import KbMonitorView from '@/views/admin/KbMonitorView.vue'

const mountView = () =>
  mount(KbMonitorView, {
    global: {
      stubs: {
        'el-card': { template: '<div class="el-card"><slot name="header" /><slot /></div>' },
        'el-radio-group': { template: '<div><slot /></div>' },
        'el-radio-button': { template: '<button><slot /></button>' },
        'el-button': { template: '<button><slot /></button>' },
        'el-table': {
          props: ['data'],
          provide() {
            return { tableRows: () => this.data || [] }
          },
          template: '<div class="el-table"><slot /></div>',
        },
        'el-table-column': {
          props: ['prop', 'label'],
          inject: { tableRows: { default: () => () => [] } },
          template:
            '<div class="el-col"><template v-for="(row, i) in tableRows()" :key="i"><slot :row="row">{{ prop ? row[prop] : "" }}</slot></template></div>',
        },
        'el-tag': { template: '<span><slot /></span>' },
        'el-empty': { template: '<div class="el-empty"><slot /></div>' },
        'el-icon': { template: '<i><slot /></i>' },
      },
      directives: { loading: {} },
    },
  })

const settle = async () => {
  await flushPromises()
  await new Promise((r) => setTimeout(r, 20))
  await flushPromises()
}

describe('KbMonitorView Dashboard MVP 补全 (W71 B-5, 子 plan ② 收口)', () => {
  beforeEach(() => {
    initCalls.length = 0
    chartStub.setOption.mockClear()
    chartStub.resize.mockClear()
    chartStub.dispose.mockClear()
    fetchKbOverview.mockClear()
    fetchKbQueueDepth.mockClear()
    fetchKbFailures.mockClear()
  })
  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('scenario_1: 2 新 el-card 渲染 (7 天入库 120 条 + 7 天回滚 8 条)', async () => {
    const wrapper = mountView()
    await settle()
    const html = wrapper.html()
    // 2 新卡片标签
    expect(html).toContain('本周新增入库')
    expect(html).toContain('本周回滚')
    // summary 求和 weekly_intake = 120 + rollback_count = 8
    expect(html).toContain('120 条')
    expect(html).toContain('8 条')
    // 5min polling 提示
    expect(html).toContain('每 5 分钟自动刷新')
  })

  it('scenario_2: 5min polling 触发 (useKbMonitor setInterval 5min, mock 1 次 fetch)', async () => {
    // 直接验证 useKbMonitor 真实 polling 逻辑 (unmock 用真实实现)
    vi.resetModules()
    vi.useFakeTimers()
    const axiosMod = { default: { get: vi.fn(() => Promise.resolve({ data: { weekly_intake: [1], rollback_count: 0 } })) } }
    vi.doMock('axios', () => axiosMod)
    const { useKbMonitor: realUseKbMonitor } = await vi.importActual('@/composables/useKbMonitor')

    // 手动驱动 startPolling (脱离 onMounted 生命周期)
    const inst = realUseKbMonitor()
    inst.startPolling()
    // 立即拉一次
    expect(axiosMod.default.get).toHaveBeenCalledTimes(1)
    // 前进 5 分钟 → 第 2 次拉取 (5min polling 生效)
    await vi.advanceTimersByTimeAsync(5 * 60 * 1000)
    expect(axiosMod.default.get).toHaveBeenCalledTimes(2)
    // 验证 URL + 30s timeout 防御
    expect(axiosMod.default.get).toHaveBeenCalledWith(
      '/api/v1/knowledge/auto-intake-summary',
      expect.objectContaining({ timeout: 30000 }),
    )
    inst.stopPolling()
    vi.useRealTimers()
    vi.doUnmock('axios')
  })

  it('scenario_3: 5 个新 ECharts 卡片渲染 (7天入库/7天回滚/5道防线/7维评分/抽检率)', async () => {
    const wrapper = mountView()
    await settle()
    const html = wrapper.html()
    // 5 新卡片标题
    expect(html).toContain('7 天入库趋势（逐日）')
    expect(html).toContain('7 天回滚量')
    expect(html).toContain('5 道防线触发')
    expect(html).toContain('7 维评分')
    expect(html).toContain('抽检率')
  })

  it('scenario_4: 4 旧 ECharts 子图仍在 + 总计 9 canvas (回归守卫)', async () => {
    const wrapper = mountView()
    await settle()
    const html = wrapper.html()
    // 4 旧子图标题
    expect(html).toContain('入库趋势（逐小时）')
    expect(html).toContain('失败率（逐小时）')
    expect(html).toContain('成功 / 失败 / 重试 对比')
    expect(html).toContain('队列堆积')
    // 4 旧 + 5 新 = 9 canvas 容器 + echarts.init 9 次
    expect(wrapper.findAll('.chart-canvas').length).toBe(9)
    expect(initCalls.length).toBe(9)
  })
})
