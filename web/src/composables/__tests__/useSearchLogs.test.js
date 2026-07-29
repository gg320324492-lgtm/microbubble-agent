/**
 * useSearchLogs.test.js — RAG PR6 (W92) 检索日志 composable 单测
 *
 * 覆盖 (14 case):
 *  1-2  GATE_DIMENSIONS 7 维常量 + 门禁阈值常量
 *  3-5  refresh 并发拉列表+聚合 / 参数正确 / dimensions 落地
 *  6-7  hasAllDimensions 门禁 (a) 自检: 齐备 true / 缺一 false
 *  8-9  recallGatePass / slowGatePass 直读后端门禁判定
 * 10-11 失败保留上次数据 (不闪烁) + 403 专用文案
 * 12-13 筛选 applyFilters 回第 1 页 + 空值不进 params
 * 14    分页 goToPage / setPageSize offset 计算
 *
 * 与 useKbMonitor.test.js 同风格 (jsdom + axios mock), 不改实现。
 */

import { describe, it, expect, vi, beforeEach } from 'vitest'

const mockAxiosGet = vi.fn()

vi.mock('axios', () => ({
  default: {
    get: (...args) => mockAxiosGet(...args),
  },
}))

import {
  useSearchLogs,
  GATE_DIMENSIONS,
  RECALL_RATE_TARGET,
  SLOW_QUERY_RATE_TARGET,
} from '../useSearchLogs'

const ROW = {
  id: 1,
  created_at: '2026-07-30T10:00:00',
  query: '微纳米气泡',
  candidate_count: 10,
  hit: true,
  clicked_id: 42,
  click_position: 2,
  latency_ms: 320,
  user_id: 7,
  user_name: '王天志',
  embedding_model: 'Qwen/Qwen3-Embedding-0.6B',
  source: 'knowledge_search',
  session_id: 'sess-1',
  top_ids: [42, 43, 44],
}

const SUMMARY = {
  days: 30,
  total_searches: 100,
  total_clicks: 35,
  recall_rate: 0.35,
  recall_rate_gate_pass: true,
  slow_query_count: 3,
  slow_query_rate: 0.03,
  slow_query_gate_pass: true,
  slow_query_threshold_ms: 500,
  avg_latency_ms: 210.5,
  p95_latency_ms: 480,
  avg_click_position: 2.1,
  distinct_users: 4,
  latency_semantics: 'derived proxy',
}

/** 按 URL 分派 mock: 列表 vs 聚合 */
function mockOk({ dimensions = [...GATE_DIMENSIONS], summary = SUMMARY, items = [ROW], total = 1 } = {}) {
  mockAxiosGet.mockImplementation((url) => {
    if (url.endsWith('/summary')) return Promise.resolve({ data: summary })
    return Promise.resolve({ data: { items, total, limit: 50, offset: 0, dimensions } })
  })
}

function listCall() {
  return mockAxiosGet.mock.calls.find(([url]) => !url.endsWith('/summary'))
}

describe('useSearchLogs (RAG PR6 W92 检索日志 7 维)', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('1. GATE_DIMENSIONS 恰好 7 维 (门禁 a: >= 7 维)', () => {
    expect(GATE_DIMENSIONS).toHaveLength(7)
    expect([...GATE_DIMENSIONS]).toEqual([
      'created_at',
      'query',
      'candidate_count',
      'hit',
      'click_position',
      'latency_ms',
      'user_id',
    ])
  })

  it('2. 门禁阈值常量与 plan 一致 (回收率 30% / 慢查询 5%)', () => {
    expect(RECALL_RATE_TARGET).toBe(0.3)
    expect(SLOW_QUERY_RATE_TARGET).toBe(0.05)
  })

  it('3. refresh 同时拉列表与聚合 (2 次 GET)', async () => {
    mockOk()
    const { refresh, rows, summary, total } = useSearchLogs()
    await refresh()
    expect(mockAxiosGet).toHaveBeenCalledTimes(2)
    expect(rows.value).toHaveLength(1)
    expect(total.value).toBe(1)
    expect(summary.value.total_searches).toBe(100)
  })

  it('4. 列表请求打到 /api/v1/admin/search-logs 且带 30s timeout', async () => {
    mockOk()
    const { refresh } = useSearchLogs()
    await refresh()
    const [url, cfg] = listCall()
    expect(url).toBe('/api/v1/admin/search-logs')
    expect(cfg.timeout).toBe(30000)
    expect(cfg.params).toMatchObject({ days: 30, limit: 50, offset: 0 })
  })

  it('5. 后端返回的 dimensions 落到 state', async () => {
    mockOk()
    const { refresh, dimensions } = useSearchLogs()
    await refresh()
    expect(dimensions.value).toEqual([...GATE_DIMENSIONS])
  })

  it('6. hasAllDimensions=true 当后端 7 维齐备', async () => {
    mockOk()
    const { refresh, hasAllDimensions } = useSearchLogs()
    await refresh()
    expect(hasAllDimensions.value).toBe(true)
  })

  it('7. hasAllDimensions=false 当后端少一维 (门禁 a 前端自检生效)', async () => {
    mockOk({ dimensions: GATE_DIMENSIONS.filter((d) => d !== 'latency_ms') })
    const { refresh, hasAllDimensions } = useSearchLogs()
    await refresh()
    expect(hasAllDimensions.value).toBe(false)
  })

  it('8. recallGatePass 直读后端判定 (不在前端重算阈值)', async () => {
    mockOk({ summary: { ...SUMMARY, recall_rate: 0.12, recall_rate_gate_pass: false } })
    const { refresh, recallGatePass } = useSearchLogs()
    await refresh()
    expect(recallGatePass.value).toBe(false)
  })

  it('9. slowGatePass 直读后端判定', async () => {
    mockOk({ summary: { ...SUMMARY, slow_query_rate: 0.4, slow_query_gate_pass: false } })
    const { refresh, slowGatePass } = useSearchLogs()
    await refresh()
    expect(slowGatePass.value).toBe(false)
  })

  it('9b. slowGateEvaluable=false 时 UI 须显示不可判定 (代理耗时不冒充门禁通过)', async () => {
    mockOk({
      summary: { ...SUMMARY, slow_query_rate: 0.0449, slow_query_gate_pass: true, slow_query_gate_evaluable: false },
    })
    const { refresh, slowGateEvaluable, slowGatePass } = useSearchLogs()
    await refresh()
    // 后端算出 rate 达标, 但门禁不可判定 —— 前端必须能区分这两件事
    expect(slowGatePass.value).toBe(true)
    expect(slowGateEvaluable.value).toBe(false)
  })

  it('10. 请求失败保留上次数据 (只置 error, 表格不闪烁)', async () => {
    mockOk()
    const { refresh, rows, error } = useSearchLogs()
    await refresh()
    expect(rows.value).toHaveLength(1)

    mockAxiosGet.mockRejectedValue(new Error('network down'))
    await refresh()
    expect(error.value).toBe('network down')
    expect(rows.value).toHaveLength(1) // 旧数据仍在
  })

  it('11. 403 给管理员权限专用文案', async () => {
    mockAxiosGet.mockRejectedValue({ response: { status: 403 } })
    const { refresh, error } = useSearchLogs()
    await refresh()
    expect(error.value).toBe('需要管理员权限')
  })

  it('12. applyFilters 把筛选写进 params 并回到第 1 页', async () => {
    mockOk()
    const { refresh, applyFilters, currentPage, goToPage } = useSearchLogs()
    await refresh()
    await goToPage(3)
    expect(currentPage.value).toBe(3)

    mockAxiosGet.mockClear()
    await applyFilters({ q: '气泡', source: 'agent_chat', hitOnly: true, slowOnly: true })
    expect(currentPage.value).toBe(1)
    const [, cfg] = listCall()
    expect(cfg.params).toMatchObject({
      q: '气泡',
      source: 'agent_chat',
      hit_only: true,
      slow_only: true,
      offset: 0,
    })
  })

  it('13. 空筛选值不进 params (避免后端收到空串)', async () => {
    mockOk()
    const { refresh } = useSearchLogs()
    await refresh()
    const [, cfg] = listCall()
    expect(cfg.params).not.toHaveProperty('q')
    expect(cfg.params).not.toHaveProperty('source')
    expect(cfg.params).not.toHaveProperty('user_id')
    expect(cfg.params).not.toHaveProperty('hit_only')
  })

  it('14. 分页 offset 计算正确 + setPageSize 回第 1 页', async () => {
    mockOk()
    const { refresh, goToPage, setPageSize, offset, limit, currentPage } = useSearchLogs()
    await refresh()

    await goToPage(4)
    expect(offset.value).toBe(150) // (4-1) * 50

    await setPageSize(20)
    expect(limit.value).toBe(20)
    expect(offset.value).toBe(0)
    expect(currentPage.value).toBe(1)
  })
})
