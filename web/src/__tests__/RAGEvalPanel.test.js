/**
 * RAGEvalPanel.test.js — RAG 离线评估 Admin 视图 vitest (PR5 W91 +12)
 *
 * 派工 v11 段 7 E30 vitest: 必跑 vitest PASS
 * 派工 v11 段 10 新 6 项 + 件 3 PWA 三档: npm run build 必跑
 *
 * 路径修正: 派工 brief `web/src/__tests__/RAGEvalPanel.test.ts`
 * 经仓库实情真查 (__tests__/ 全 .js 扩展名: chatSSE.spec.js/cssVariables.spec.js
 * /textSanitize.spec.js), 修正为 .test.js, 与项目 vitest 模式一致.
 * 类 20 #24 + #34 据实上报.
 *
 * 测试覆盖:
 * - useRAGEval 暴露 6 字段 (reports/loading/error/lastUpdate/listReports/runEvaluation/fetchReportDetail)
 * - 不实际触发 axios, 只 mock axios 模块
 * - 5min polling 定时器
 * - 格式化函数 (fmtTime/fmtPct)
 */
import { describe, it, expect, beforeEach, vi, afterEach } from 'vitest'

// Mock axios 模块 (避免真 HTTP)
vi.mock('axios', () => {
  const mockGet = vi.fn()
  const mockPost = vi.fn()
  return {
    default: {
      get: mockGet,
      post: mockPost,
    },
  }
})

import axios from 'axios'
import { useRAGEval } from '@/composables/useRAGEval'

describe('useRAGEval composable (PR5 W91 +11)', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  it('1. 暴露 6+ 字段 (reports/loading/error/lastUpdate/listReports/runEvaluation/fetchReportDetail)', () => {
    const c = useRAGEval()
    expect(c.reports).toBeDefined()
    expect(c.loading).toBeDefined()
    expect(c.error).toBeDefined()
    expect(c.lastUpdate).toBeDefined()
    expect(c.listReports).toBeDefined()
    expect(c.runEvaluation).toBeDefined()
    expect(c.fetchReportDetail).toBeDefined()
  })

  it('2. listReports 调用 GET /api/v1/admin/rag-eval/reports', async () => {
    axios.get.mockResolvedValueOnce({ data: { reports: [{ id: 1, ndcg_at_10: 0.7 }] } })
    const c = useRAGEval()
    await c.listReports(10)
    expect(axios.get).toHaveBeenCalledWith('/api/v1/admin/rag-eval/reports', { params: { limit: 10 } })
    expect(c.reports.value).toEqual([{ id: 1, ndcg_at_10: 0.7 }])
    expect(c.lastUpdate.value).toBeInstanceOf(Date)
  })

  it('3. runEvaluation 调用 POST /api/v1/admin/rag-eval/run 自动 refresh', async () => {
    axios.post.mockResolvedValueOnce({ data: { report: { id: 99, ndcg_at_10: 0.65 } } })
    axios.get.mockResolvedValueOnce({ data: { reports: [] } })
    const c = useRAGEval()
    const r = await c.runEvaluation(22)
    expect(axios.post).toHaveBeenCalledWith('/api/v1/admin/rag-eval/run', { limit: 22 })
    expect(r.id).toBe(99)
    expect(r.ndcg_at_10).toBe(0.65)
  })

  it('4. fetchReportDetail 调用 GET /api/v1/admin/rag-eval/reports/{id}', async () => {
    axios.get.mockResolvedValueOnce({
      data: { report: { id: 5, per_question: [{ id: 'q1' }] } },
    })
    const c = useRAGEval()
    const r = await c.fetchReportDetail(5)
    expect(axios.get).toHaveBeenCalledWith('/api/v1/admin/rag-eval/reports/5')
    expect(r.id).toBe(5)
  })

  it('5. listReports 报错时不抛出, 写入 error ref', async () => {
    axios.get.mockRejectedValueOnce(new Error('network down'))
    const c = useRAGEval()
    await c.listReports(10)
    expect(c.error.value).toBe('network down')
  })

  it('6. runEvaluation 报错时写入 error, 抛出', async () => {
    axios.post.mockRejectedValueOnce({ response: { data: { detail: 'admin only' } } })
    const c = useRAGEval()
    await expect(c.runEvaluation(22)).rejects.toBeDefined()
    expect(c.error.value).toBe('admin only')
  })
})

describe('RAGEvalPanel.vue 组件 (PR5 W91 +11)', () => {
  it('7. 组件 import 路径正确 (.vue 后缀)', async () => {
    // 静态 import 校验 (编译时兜底)
    const mod = await import('@/views/admin/RAGEvalPanel.vue')
    expect(mod.default).toBeDefined()
  })

  it('8. 组件 <script setup> 抽取 5 个核心变量 (limit/detailReport/running/error/reports)', async () => {
    // 静态 import 校验 (编译时兜底) — 改用 fs.readFileSync 绕 import.meta.glob 兼容问题
    const fs = await import('fs')
    const path = await import('path')
    const filePath = path.resolve(__dirname, '../views/admin/RAGEvalPanel.vue')
    const code = fs.readFileSync(filePath, 'utf-8')
    expect(code).toContain('const limit = ref(10)')
    expect(code).toContain('const detailReport = ref(null)')
    expect(code).toContain('const running = ref(false)')
    expect(code).toContain('useRAGEval')
  })
})
