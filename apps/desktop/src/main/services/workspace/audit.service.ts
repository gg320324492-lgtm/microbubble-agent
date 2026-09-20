// 工作区审计服务 — 工具调用前后各落一条（工单 C-1 §3），表结构见迁移 004
import type { SqlDatabase } from '../../db/adapters'

export interface AuditRow {
  id: number
  user_id: string
  tool: string
  input_summary: string
  ok: number
  created_at: number
  /** M8-3 证据链：命中的权限规则（如 "write@workspace=allow"），无则 null */
  permission_rule?: string | null
  /** 是否弹过确认（1/0） */
  confirmed?: number | null
  /** 用户选择：approve / reject / 空（未弹） */
  user_choice?: string | null
}

/** M8-3 证据链条目（record 的扩展入参，全部可选 → 旧调用零改动） */
export interface AuditEvidence {
  /** 命中规则描述，如 write@workspace=allow / write@default=ask */
  permissionRule?: string
  /** 是否弹了确认 */
  confirmed?: boolean
  /** 用户选择 */
  userChoice?: 'approve' | 'reject' | 'abort' | null
}

export class AuditService {
  constructor(private readonly db: SqlDatabase) {}

  record(userId: string, tool: string, inputSummary: string, ok: boolean, evidence?: AuditEvidence): void {
    // 证据链列可能尚未迁移（老库）→ 回退为不带证据写入，保证不因缺列而失败
    try {
      this.db
        .prepare(
          'INSERT INTO workspace_audit (user_id, tool, input_summary, ok, created_at, permission_rule, confirmed, user_choice) VALUES (?, ?, ?, ?, ?, ?, ?, ?)'
        )
        .run(
          userId,
          tool,
          inputSummary,
          ok ? 1 : 0,
          Date.now(),
          evidence?.permissionRule ?? null,
          evidence?.confirmed === undefined ? null : evidence.confirmed ? 1 : 0,
          evidence?.userChoice ?? null
        )
    } catch {
      this.db
        .prepare('INSERT INTO workspace_audit (user_id, tool, input_summary, ok, created_at) VALUES (?, ?, ?, ?, ?)')
        .run(userId, tool, inputSummary, ok ? 1 : 0, Date.now())
    }
  }

  /** 最近记录在前（id 倒序）；limit 缺省 20 */
  list(limit = 20): AuditRow[] {
    return this.db.prepare('SELECT * FROM workspace_audit ORDER BY id DESC LIMIT ?').all(limit) as AuditRow[]
  }
}
