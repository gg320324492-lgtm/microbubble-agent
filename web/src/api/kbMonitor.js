// KB 自动入库监控 API 封装 — qa-bench v3.1 决策 D5 (Dashboard KB 监控)
//
// W68 第 7 批 A-4 (2026-07-24) — 锚点范式第 78 守恒.
//
// 3 个端点 (全部 admin/leader only, 后端 get_current_admin 兜底, write tier 30/min):
//   GET /api/v1/admin/kb-monitor/overview?hours=24  → 入库/失败/重试/队列 核心统计 + 逐小时趋势
//   GET /api/v1/admin/kb-monitor/queue-depth        → 队列深度快照 (pending/analyzing + eta)
//   GET /api/v1/admin/kb-monitor/failures?limit=50  → 失败 / 滞留列表
//
// 复用 admin/analytics 鉴权风格 (axios 全局带 Authorization header).

import axios from 'axios'

/** 监控总览: 过去 hours 小时的入库/失败/重试/队列统计 + 逐小时趋势 */
export const fetchKbOverview = (hours = 24) =>
  axios.get('/api/v1/admin/kb-monitor/overview', { params: { hours } }).then((r) => r.data)

/** 队列深度快照 (轻量, 可高频轮询) */
export const fetchKbQueueDepth = () =>
  axios.get('/api/v1/admin/kb-monitor/queue-depth').then((r) => r.data)

/** 失败 / 滞留列表 (include_stuck: 是否含超轮次仍 pending 的滞留项) */
export const fetchKbFailures = (limit = 50, includeStuck = true) =>
  axios
    .get('/api/v1/admin/kb-monitor/failures', {
      params: { limit, include_stuck: includeStuck },
    })
    .then((r) => r.data)
