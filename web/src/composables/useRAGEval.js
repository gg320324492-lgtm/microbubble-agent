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

export function useRAGEval() {
  const reports = ref([])
  const loading = ref(false)
  const error = ref(null)
  const lastUpdate = ref(null)

  async function listReports(limit = 10) {
    loading.value = true
    error.value = null
    try {
      const resp = await axios.get('/api/v1/admin/rag-eval/reports', {
        params: { limit },
      })
      reports.value = resp.data?.reports || []
      lastUpdate.value = new Date()
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
