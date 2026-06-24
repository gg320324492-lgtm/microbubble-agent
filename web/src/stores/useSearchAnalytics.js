/**
 * useSearchAnalytics.js — 检索质量埋点 Pinia store (v31)
 *
 * 跟踪当前活跃 search_event_id (KnowledgeView 搜索后存),
 * 用户点击结果时调 recordClick.
 *
 * 不持久化 (currentSearchId 是会话级别, 关页面就丢).
 *
 * 用法 (KnowledgeView):
 *   const sa = useSearchAnalyticsStore()
 *   await sa.startSearch(query, topIds, 'knowledge_search')  // 异步 POST
 *   sa.recordClick(id, position)                              // 异步 PATCH
 */

import { defineStore } from 'pinia'
import { ref } from 'vue'
import { recordSearchEvent, recordClick } from '@/api/analytics'

// session_id 用 localStorage 持久化 (同浏览器跨标签页共享)
const SESSION_KEY = 'mnb:search_analytics:session_id'

function getOrCreateSessionId() {
  if (typeof localStorage === 'undefined') {
    // SSR fallback (项目实际不用 SSR, 兜底而已)
    return `sess-${Date.now()}-${Math.random().toString(36).slice(2, 10)}`
  }
  let sid = null
  try {
    sid = localStorage.getItem(SESSION_KEY)
  } catch {
    /* localStorage 不可用 (隐私模式等), 用临时 ID */
  }
  if (!sid) {
    sid = `sess-${Date.now()}-${Math.random().toString(36).slice(2, 10)}`
    try {
      localStorage.setItem(SESSION_KEY, sid)
    } catch {
      /* 静默失败 */
    }
  }
  return sid
}

export const useSearchAnalyticsStore = defineStore('searchAnalytics', {
  state: () => ({
    currentSearchId: null, // 最近一次成功写入的 search_event_id (后续 click 用)
    lastTopIds: [],         // 最近一次搜索的 top_ids (用于 click 找位置)
  }),

  actions: {
    /**
     * 发起搜索时调用: POST 到后端, 存 search_event_id 备用.
     * 失败不抛异常 (静默忽略, 不影响搜索功能).
     */
    async startSearch(query, topIds, source = 'knowledge_search') {
      if (!query || !topIds || topIds.length === 0) return
      try {
        const resp = await recordSearchEvent({
          query,
          top_ids: topIds.slice(0, 20),  // 后端 max 20
          source,
          session_id: getOrCreateSessionId(),
        })
        this.currentSearchId = resp.search_event_id
        this.lastTopIds = topIds.slice(0, 20)
      } catch (err) {
        // 静默: 埋点失败不影响主流程
        // eslint-disable-next-line no-console
        console.debug('[search-analytics] startSearch failed:', err)
        this.currentSearchId = null
        this.lastTopIds = []
      }
    },

    /**
     * 用户点击某条结果时调用: PATCH 更新 clicked_id + click_position.
     * position 是 1-based (在 lastTopIds 数组里的索引+1).
     */
    async recordClick(clickedId, position) {
      if (!this.currentSearchId || !clickedId || !position) return
      try {
        await recordClick(this.currentSearchId, {
          clicked_id: clickedId,
          click_position: position,
        })
      } catch (err) {
        // eslint-disable-next-line no-console
        console.debug('[search-analytics] recordClick failed:', err)
      }
    },

    /** 清空当前搜索 (切换 query 或离开页面时调用) */
    reset() {
      this.currentSearchId = null
      this.lastTopIds = []
    },
  },
})
