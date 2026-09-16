// 工作区审计服务 — 工具调用前后各落一条（工单 C-1 §3），表结构见迁移 004
import type { SqlDatabase } from '../../db/adapters'

export interface AuditRow {
  id: number
  user_id: string
  tool: string
  input_summary: string
  ok: number
  created_at: number
}

export class AuditService {
  constructor(private readonly db: SqlDatabase) {}

  record(userId: string, tool: string, inputSummary: string, ok: boolean): void {
    this.db
      .prepare('INSERT INTO workspace_audit (user_id, tool, input_summary, ok, created_at) VALUES (?, ?, ?, ?, ?)')
      .run(userId, tool, inputSummary, ok ? 1 : 0, Date.now())
  }

  /** 最近记录在前（id 倒序）；limit 缺省 20 */
  list(limit = 20): AuditRow[] {
    return this.db.prepare('SELECT * FROM workspace_audit ORDER BY id DESC LIMIT ?').all(limit) as AuditRow[]
  }
}
