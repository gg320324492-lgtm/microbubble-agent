/**
 * useSearchLogs.ts — RAG PR6 (W92) 检索日志 7 维消费 composable
 *
 * 缺口 7 (plan `rag-quirky-otter.md` §1.1 #6 + §2 PR6):
 *   后端埋点自 v30/v31 起完整 (`app/models/search_log.py` + `analytics.py`),
 *   前端从未消费逐行日志。本 composable 是前端接通侧的唯一数据入口。
 *
 * 后端契约 (app/api/v1/search_logs_admin.py):
 * - GET /api/v1/admin/search-logs?days&limit&offset&q&source&user_id&hit_only&slow_only
 *     → { items: SearchLogRow[], total, limit, offset, dimensions: string[] }
 * - GET /api/v1/admin/search-logs/summary?days
 *     → { total_searches, total_clicks, recall_rate, recall_rate_gate_pass,
 *         slow_query_count, slow_query_rate, slow_query_gate_pass, ... }
 *
 * 7 维 (量化门禁 a: ≥ 7 维):
 *   created_at / query / candidate_count / hit / click_position / latency_ms / user_id
 *
 * ⚠️ latency_ms 语义: 后端派生代理值 (updated_at - created_at = 点击决策耗时),
 *    **不是检索耗时** — search_logs 无检索耗时列, PR6 非 alembic 例外 PR 不得加。
 *    真检索耗时留 PR7 observability。UI 必须标注此语义, 禁止误标"检索耗时"。
 *
 * 设计原则:
 * - 0 production code 改动铁律 — 纯前端新增, 复用全局 axios (拦截器已带 token)
 * - 失败保留上次数据 (与 useKbMonitor 同一纪律, W5 T5.4 教训)
 * - 无自动 polling: 管理页是低频人工查询, 显式 refresh 即可 (避免无谓请求)
 */

import { ref, computed } from 'vue'
import axios from 'axios'

const API_BASE = '/api/v1/admin/search-logs'
const REQUEST_TIMEOUT_MS = 30 * 1000

/** 后端 GATE_DIMENSIONS 的前端镜像 — 与 search_logs_admin.py 单一真源对齐 */
export const GATE_DIMENSIONS = [
  'created_at',
  'query',
  'candidate_count',
  'hit',
  'click_position',
  'latency_ms',
  'user_id',
] as const

/** 门禁阈值 (plan §2 PR6 门禁 b / c) */
export const RECALL_RATE_TARGET = 0.3
export const SLOW_QUERY_RATE_TARGET = 0.05

export interface SearchLogRow {
  id: number
  created_at: string | null
  query: string
  candidate_count: number
  hit: boolean
  clicked_id: number | null
  click_position: number | null
  latency_ms: number | null
  user_id: number | null
  user_name: string | null
  embedding_model: string | null
  source: string | null
  session_id: string | null
  top_ids: number[]
}

export interface SearchLogSummary {
  days: number
  total_searches: number
  total_clicks: number
  recall_rate: number
  recall_rate_gate_pass: boolean
  slow_query_count: number
  slow_query_rate: number
  slow_query_gate_pass: boolean
  slow_query_threshold_ms: number
  avg_latency_ms: number | null
  p95_latency_ms: number | null
  avg_click_position: number | null
  distinct_users: number
  latency_semantics: string
}

export interface SearchLogFilters {
  days: number
  q: string
  source: string
  userId: number | null
  hitOnly: boolean
  slowOnly: boolean
}

export function useSearchLogs() {
  const rows = ref<SearchLogRow[]>([])
  const summary = ref<SearchLogSummary | null>(null)
  const dimensions = ref<string[]>([])
  const total = ref(0)
  const limit = ref(50)
  const offset = ref(0)
  const loading = ref(false)
  const error = ref<string | null>(null)

  const filters = ref<SearchLogFilters>({
    days: 30,
    q: '',
    source: '',
    userId: null,
    hitOnly: false,
    slowOnly: false,
  })

  /** 当前页码 (1-based, 给 el-pagination) */
  const currentPage = computed({
    get: () => Math.floor(offset.value / limit.value) + 1,
    set: (p: number) => {
      offset.value = Math.max(0, (p - 1) * limit.value)
    },
  })

  /** 7 维是否齐备 — 门禁 (a) 前端自检 */
  const hasAllDimensions = computed(() =>
    GATE_DIMENSIONS.every((d) => dimensions.value.includes(d))
  )

  /** 门禁 (b) 回收率是否达标 */
  const recallGatePass = computed(() => summary.value?.recall_rate_gate_pass ?? false)

  /** 门禁 (c) 慢查询占比是否达标 */
  const slowGatePass = computed(() => summary.value?.slow_query_gate_pass ?? false)

  function buildParams() {
    const f = filters.value
    const p: Record<string, unknown> = {
      days: f.days,
      limit: limit.value,
      offset: offset.value,
    }
    if (f.q) p.q = f.q
    if (f.source) p.source = f.source
    if (f.userId != null) p.user_id = f.userId
    if (f.hitOnly) p.hit_only = true
    if (f.slowOnly) p.slow_only = true
    return p
  }

  async function fetchRows() {
    const res = await axios.get(API_BASE, {
      params: buildParams(),
      timeout: REQUEST_TIMEOUT_MS,
    })
    rows.value = res.data?.items || []
    total.value = res.data?.total ?? 0
    dimensions.value = res.data?.dimensions || []
  }

  async function fetchSummary() {
    const res = await axios.get(`${API_BASE}/summary`, {
      params: { days: filters.value.days },
      timeout: REQUEST_TIMEOUT_MS,
    })
    summary.value = res.data
  }

  /** 拉取列表 + 聚合。失败保留上次数据 (只置 error), 不清空表格。 */
  async function refresh() {
    loading.value = true
    try {
      await Promise.all([fetchRows(), fetchSummary()])
      error.value = null
    } catch (e: any) {
      if (e?.response?.status === 403) {
        error.value = '需要管理员权限'
      } else {
        error.value = e?.response?.data?.detail || e?.message || '加载失败'
      }
    } finally {
      loading.value = false
    }
  }

  /** 改筛选条件后回到第 1 页再拉 */
  async function applyFilters(patch: Partial<SearchLogFilters> = {}) {
    filters.value = { ...filters.value, ...patch }
    offset.value = 0
    await refresh()
  }

  async function goToPage(page: number) {
    currentPage.value = page
    await refresh()
  }

  async function setPageSize(size: number) {
    limit.value = size
    offset.value = 0
    await refresh()
  }

  function resetFilters() {
    filters.value = {
      days: 30,
      q: '',
      source: '',
      userId: null,
      hitOnly: false,
      slowOnly: false,
    }
    offset.value = 0
  }

  return {
    // state
    rows,
    summary,
    dimensions,
    total,
    limit,
    offset,
    loading,
    error,
    filters,
    // computed
    currentPage,
    hasAllDimensions,
    recallGatePass,
    slowGatePass,
    // actions
    refresh,
    applyFilters,
    goToPage,
    setPageSize,
    resetFilters,
  }
}
