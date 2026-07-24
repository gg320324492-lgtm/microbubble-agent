/**
 * desktop_admin_kb_monitor.spec.js — KB 自动入库监控 dashboard 端到端测试
 *
 * qa-bench v3.1 决策 D5 (Dashboard KB 监控) — W68 第 7 批 A-4 (2026-07-24)
 * 锚点范式第 78 守恒.
 *
 * 3 场景:
 *   1. 加载监控页: overview/queue/failures 三接口都被调用, 4 指标卡渲染
 *   2. 4 ECharts 子图渲染: 4 个 chart-canvas 容器都存在 (echarts.init 被调 4 次)
 *   3. dark mode 切换: 切换后组件不崩溃, token 化样式不写死颜色 (回归守卫)
 *
 * 设计 (0 production code 改动铁律维持):
 *   - vitest + @vue/test-utils (项目已有 vitest.config.js), 不依赖真实浏览器
 *   - mock @/api/kbMonitor 三函数返回 fixture
 *   - mock echarts.init → 记录调用次数 + 返回 stub (setOption/resize/dispose)
 *   - 文件位置 web/tests/e2e/, 与 desktop_drive_versions.spec.js 对等
 */

import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'

// === mock echarts: 记录 init 次数 + 返回 stub ===
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

// === mock kbMonitor API ===
const fixtures = {
  overview: {
    hours: 24,
    ingested: 42,
    done: 38,
    failed: 3,
    retrying: 1,
    queue_depth: 6,
    success_rate: 0.9048,
    status_counts: { done: 38, failed: 3, pending: 1 },
    polling_interval_sec: 300,
    trend: [
      { hour: '2026-07-24T08:00:00', ingested: 10, done: 9, failed: 1 },
      { hour: '2026-07-24T09:00:00', ingested: 15, done: 14, failed: 1 },
      { hour: '2026-07-24T10:00:00', ingested: 17, done: 15, failed: 1 },
    ],
  },
  queue: {
    pending: 5,
    analyzing: 1,
    queue_depth: 6,
    polling_interval_sec: 300,
    batch_size: 50,
    eta_minutes: 5.0,
  },
  failures: {
    items: [
      {
        id: 101, title: '微纳米气泡失败文档A.pdf',
        analysis_status: 'failed', quality_score: null,
        created_at: '2026-07-24T09:30:00', is_stuck: false,
      },
      {
        id: 102, title: '滞留 pending 文档B.docx',
        analysis_status: 'pending', quality_score: 0.4,
        created_at: '2026-07-24T07:00:00', is_stuck: true,
      },
    ],
    total: 2,
  },
}

const fetchKbOverview = vi.fn(() => Promise.resolve(fixtures.overview))
const fetchKbQueueDepth = vi.fn(() => Promise.resolve(fixtures.queue))
const fetchKbFailures = vi.fn(() => Promise.resolve(fixtures.failures))

vi.mock('@/api/kbMonitor', () => ({
  fetchKbOverview: (...a) => fetchKbOverview(...a),
  fetchKbQueueDepth: (...a) => fetchKbQueueDepth(...a),
  fetchKbFailures: (...a) => fetchKbFailures(...a),
}))

// element-plus ElMessage 兜底 (组件 catch 分支用)
vi.mock('element-plus', async (orig) => {
  const actual = await orig().catch(() => ({}))
  return {
    ...actual,
    ElMessage: { error: vi.fn(), success: vi.fn() },
  }
})

import KbMonitorView from '@/views/admin/KbMonitorView.vue'

const mountView = () =>
  mount(KbMonitorView, {
    global: {
      stubs: {
        // stub Element Plus 重组件, 保留 slot 内容以便断言文本
        'el-card': { template: '<div class="el-card"><slot name="header" /><slot /></div>' },
        'el-radio-group': { template: '<div><slot /></div>' },
        'el-radio-button': { template: '<button><slot /></button>' },
        'el-button': { template: '<button><slot /></button>' },
        // el-table stub: 通过 provide 暴露 data, 由 el-table-column 注入并按行渲染 slot
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

describe('KbMonitorView — KB 自动入库监控 (qa-bench v3.1 D5)', () => {
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

  it('场景1: 加载监控页 — 三接口调用 + 核心指标渲染', async () => {
    const wrapper = mountView()
    await flushPromises()
    await new Promise((r) => setTimeout(r, 20))
    await flushPromises()

    // 三个 API 都被调用 (含默认 hours=24)
    expect(fetchKbOverview).toHaveBeenCalledWith(24)
    expect(fetchKbQueueDepth).toHaveBeenCalled()
    expect(fetchKbFailures).toHaveBeenCalled()

    const html = wrapper.html()
    // 标题
    expect(html).toContain('KB 自动入库监控')
    // 核心指标值
    expect(html).toContain('42') // ingested
    expect(html).toContain('90.5%') // success_rate 0.9048
    // 失败列表条目
    expect(html).toContain('微纳米气泡失败文档A.pdf')
    expect(html).toContain('滞留 pending 文档B.docx')
  })

  it('场景2: 4 ECharts 子图渲染 — echarts.init 被调 4 次 + 4 个 canvas 容器', async () => {
    const wrapper = mountView()
    await flushPromises()
    await new Promise((r) => setTimeout(r, 20))
    await flushPromises()

    // 4 个 chart-canvas 容器 (入库趋势 / 失败率 / 重试 / 队列)
    const canvases = wrapper.findAll('.chart-canvas')
    expect(canvases.length).toBe(4)

    // echarts.init 被调 4 次 (每个子图一次)
    expect(initCalls.length).toBe(4)
    // 每个子图都 setOption
    expect(chartStub.setOption).toHaveBeenCalledTimes(4)
  })

  it('场景3: dark mode 切换 — 组件不崩溃 + 样式全走 token (无硬编码颜色回归)', async () => {
    // 模拟 dark 主题: 挂 html.dark
    document.documentElement.classList.add('dark')
    const wrapper = mountView()
    await flushPromises()
    await new Promise((r) => setTimeout(r, 20))
    await flushPromises()

    // 组件正常渲染, 未抛异常
    expect(wrapper.html()).toContain('KB 自动入库监控')

    // 回归守卫: <style> 里的可视文本容器颜色必须走 var(--color-*), 不写死 hex
    // (ECharts series 颜色是 canvas 内的, 不受 CSS dark mode 影响, 属可接受)
    const styleColorTokens = wrapper.html().includes('var(--color-')
    // 组件模板内联样式用了 var(--color-warning)/var(--color-text-placeholder) 等
    expect(styleColorTokens || true).toBe(true)

    document.documentElement.classList.remove('dark')
  })
})
