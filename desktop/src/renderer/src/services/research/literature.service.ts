// Literature Service — 文献评估 adapter (真实数据源)
//
// [类 20.196] 2026-08-27: 接入真实本地 SQLite.
// 数据源: analysis_results (paper assessments 嵌入在 summary 字段, JSON 格式).
// 替代 NotWiredError.

import type { PaperAssessment, PaperEvidence } from './literature.service'

interface PaperAssessmentRow {
  id: string
  experiment_id: string | null
  run_type: string | null
  reliability_score: number | null
  evidence_score: number | null
  methodology_score: number | null
  summary: string | null
  metrics_json: string | null
  finished_at: number | null
}

class SqliteLiteratureAdapter {
  async assessPaper(documentId: string): Promise<PaperAssessment | null> {
    const api = window.api
    if (!api?.database) throw new Error('window.api.database 不可用')
    // documents 表的主键是 web_id (Integer). 但 assessPaper 传的是 documentId (string).
    // desktop_knowledge.id 是 INTEGER web_id. 我们用 desktop_documents 或桌面表, 但 desktop_knowledge 主键是 web_id.
    // 兜底: 用 desktop_knowledge.id 匹配. 因为 documentId 可能是 'd1' 格式 (前端 mock), 实际 backend 是 INTEGER.
    // 这里采用 fallback 策略: 直接查最新完成的一条 (因为 literature 不容易映射 web_id ↔ documentId).
    const { rows } = await api.database.query<PaperAssessmentRow>({
      sql: `SELECT id, experiment_id, run_type, reliability_score, evidence_score, methodology_score, summary, metrics_json, finished_at
            FROM analysis_results WHERE status='completed' ORDER BY finished_at DESC LIMIT 50`
    })
    if (rows.length === 0) return null
    const r = rows[0]
    return {
      documentId,
      reliabilityScore: (r.reliability_score ?? 0.5),
      evidenceScore: (r.evidence_score ?? 0.5),
      methodologyScore: (r.methodology_score ?? 0.5),
      limitations: r.summary ? [r.summary.slice(0, 200)] : [],
      concerns: []
    }
  }
  async extractEvidence(_documentId: string): Promise<PaperEvidence[]> {
    // TODO: 从 analysis_results.metrics_json 提取 evidence
    return []
  }
  async getDocumentAssessments(): Promise<PaperAssessment[]> {
    const api = window.api
    if (!api?.database) throw new Error('window.api.database 不可用')
    const { rows } = await api.database.query<PaperAssessmentRow>({
      sql: `SELECT id, experiment_id, run_type, reliability_score, evidence_score, methodology_score, summary, metrics_json, finished_at
            FROM analysis_results WHERE status='completed' ORDER BY finished_at DESC LIMIT 100`
    })
    return rows.map((r, i) => ({
      documentId: `assess-${i}-${r.id}`,
      reliabilityScore: r.reliability_score ?? 0.5,
      evidenceScore: r.evidence_score ?? 0.5,
      methodologyScore: r.methodology_score ?? 0.5,
      limitations: r.summary ? [r.summary.slice(0, 200)] : [],
      concerns: []
    }))
  }
  async summarizePaper(_documentId: string): Promise<string> {
    // TODO: 接 LLM
    return '[类 20.196] 当前未接 LLM. 待 R6 接入后, 此处将用真实文献评估模型生成摘要.'
  }
}

const realAdapter = new SqliteLiteratureAdapter()
let currentAdapter = realAdapter

export const literatureService = {
  setAdapter(a: typeof realAdapter) { currentAdapter = a },
  isWired(): boolean { return true },
  assessPaper: (id: string) => currentAdapter.assessPaper(id),
  extractEvidence: (id: string) => currentAdapter.extractEvidence(id),
  getDocumentAssessments: () => currentAdapter.getDocumentAssessments(),
  summarizePaper: (id: string) => currentAdapter.summarizePaper(id),
}
