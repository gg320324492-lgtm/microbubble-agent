/**
 * useRAGEval.js — RAG 离线评估 Composable (PR5 W91 +11)
 *
 * PR5 RAGEvalPanel 配套 composable:
 * - listReports(limit) 拉最近 N 条 RAGEvaluationReport
 * - runEvaluation(limit) 触发后端跑一次 (admin 入口)
 * - fetchReportDetail(id) 拉单条 per_question 详情
 *
 * 路径修正事实: 派工 brief 列 web/src/composables/useRAGEval.ts
 * 经仓库实情真查 (DERIVE-18 §13), 项目 composable 多数 .js
 * (useKnowledge.js / useIsMobile.js / useKbMonitor.js), 修正为 .js
 * 与 PR4 PR7 useSearchLogs.ts 不混. 类 20 #24 brief 错配据实.
 *
 * 派工 v11 段 10 新 6 项 + 派工 v11 段 7 E30 vitest: 必跑 vitest PASS.
 */

import { ref } from 'vue'
import axios from 'axios'
import { useNow } from './useNow'

export function useRAGEval() {
  const reports = ref([])
  const loading = ref(false)
  const error = ref(null)
  const lastUpdate = ref(null)

  // 墙钟统一入口 (useNow): intervalMs=0 → 不起定时器, 完全跟随取数节奏。
  // lastUpdate 的语义是"报告列表新鲜度"—— 只在 listReports 成功那一刻打点,
  // 不是定时更新, 所以不能挂 useNow(pollInterval) 直接读 now.value。
  // 正确做法: 成功分支里先 tick() 让 now.value 取当前时刻, 再把它记进 lastUpdate。
  const { now, tick } = useNow(0)

  async function listReports(limit = 10) {
    loading.value = true
    error.value = null
    try {
      const resp = await axios.get('/api/v1/admin/rag-eval/reports', {
        params: { limit },
      })
      reports.value = resp.data?.reports || []
      tick()                        // 成功这一刻的墙钟值 (而非上次 tick 的时刻)
      lastUpdate.value = now.value  // tick() 每次重新赋值, lastUpdate 持有的 Date 不会被后续 tick 改动
    } catch (e) {
      error.value = e?.response?.data?.detail || e.message
    } finally {
      loading.value = false
    }
  }

  async function runEvaluation(limit = 22) {
    loading.value = true
    error.value = null
    try {
      const resp = await axios.post('/api/v1/admin/rag-eval/run', {
        limit,
      })
      // 跑完立即刷新列表
      await listReports(10)
      return resp.data?.report
    } catch (e) {
      error.value = e?.response?.data?.detail || e.message
      throw e
    } finally {
      loading.value = false
    }
  }

  async function fetchReportDetail(id) {
    try {
      const resp = await axios.get(`/api/v1/admin/rag-eval/reports/${id}`)
      return resp.data?.report
    } catch (e) {
      error.value = e?.response?.data?.detail || e.message
      throw e
    }
  }

  return {
    reports,
    loading,
    error,
    lastUpdate,
    listReports,
    runEvaluation,
    fetchReportDetail,
  }
}
