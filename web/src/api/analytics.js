// 检索质量埋点 API 封装 (v31)
//
// 3 个端点:
//   POST /api/v1/analytics/search-event  记录搜索事件
//   PATCH /api/v1/analytics/search-event/:id/click  记录点击
//   GET /api/v1/analytics/stats?days=7  获取核心指标

import axios from 'axios'

/** 记录一次搜索事件. 返回 { search_event_id } */
export const recordSearchEvent = (payload) =>
  axios.post('/api/v1/analytics/search-event', payload).then(r => r.data)

/** 更新点击: clicked_id + click_position (1-based, 在 top_ids 数组中的位置) */
export const recordClick = (eventId, payload) =>
  axios.patch(`/api/v1/analytics/search-event/${eventId}/click`, payload).then(r => r.data)

/** 获取核心指标 (默认最近 7 天) */
export const fetchStats = (days = 7) =>
  axios.get('/api/v1/analytics/stats', { params: { days } }).then(r => r.data)

/** 获取最近 N 条搜索日志 (用于 AnalyticsView 表格) */
export const fetchRecentLogs = (limit = 50, source = null) =>
  axios.get('/api/v1/analytics/logs', {
    params: { limit, ...(source ? { source } : {}) },
  }).then(r => r.data)
