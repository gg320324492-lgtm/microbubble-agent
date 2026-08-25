// Run Store — Phase 9-C
// workflow_runs + workflow_run_steps + workflow_run_events 持久化.

import type { DatabaseService } from '../database.service'
import type { RunEventRecord, RunRecord, RunStoreService, StepRecord } from './types'

class RunStoreImpl implements RunStoreService {
  constructor(private readonly getService: () => DatabaseService | null) {}

  insertRun(run: Omit<RunRecord, never>): void {
    const svc = this.getService()
    if (!svc) return
    svc.db.execute(
      `INSERT INTO workflow_runs (id, template_id, template_name, status, current_step_id, started_at, finished_at, started_by, parameters_json, results_json, source)
       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)`,
      [
        run.id, run.templateId, run.templateName, run.status, run.currentStepId,
        run.startedAt, run.finishedAt, run.startedBy,
        JSON.stringify(run.parameters), JSON.stringify(run.results), run.source
      ]
    )
  }

  updateRunStatus(runId: string, status: string, currentStepId: string | null, finishedAt: number | null): void {
    const svc = this.getService()
    if (!svc) return
    svc.db.execute(
      'UPDATE workflow_runs SET status = ?, current_step_id = ?, finished_at = ? WHERE id = ?',
      [status, currentStepId, finishedAt, runId]
    )
  }

  upsertStep(step: StepRecord): void {
    const svc = this.getService()
    if (!svc) return
    svc.db.execute(
      `INSERT INTO workflow_run_steps (run_id, step_id, state, started_at, finished_at, result_json, error, attempt)
       VALUES (?, ?, ?, ?, ?, ?, ?, ?)
       ON CONFLICT(run_id, step_id) DO UPDATE SET
         state = excludedCLUDed.state,
         started_at = excludedCLUDed.started_at,
         finished_at = excludedCLUDed.finished_at,
         result_json = excludedCLUDed.result_json,
         error = excludedCLUDed.error,
         attempt = excludedCLUDed.attempt`,
      [
        step.runId, step.stepId, step.state, step.startedAt, step.finishedAt,
        step.result == null ? null : JSON.stringify(step.result),
        step.error, step.attempt
      ]
    )
  }

  insertEvent(event: Omit<RunEventRecord, 'id' | 'sequence'>): void {
    const svc = this.getService()
    if (!svc) return
    const id = `evt-${Date.now()}-${Math.random().toString(36).slice(2, 6)}`
    const seqRow = svc.db.queryOne<{ s: number | null }>(
      'SELECT MAX(sequence) AS s FROM workflow_run_events WHERE run_id = ?',
      [event.runId]
    )
    const sequence = (seqRow?.s ?? 0) + 1
    svc.db.execute(
      `INSERT INTO workflow_run_events (id, run_id, step_id, type, at, message, payload_json, sequence) VALUES (?, ?, ?, ?, ?, ?, ?, ?)`,
      [id, event.runId, event.stepId, event.type, event.at, event.message, event.payload == null ? null : JSON.stringify(event.payload), sequence]
    )
  }

  getRun(runId: string): { run: RunRecord; steps: StepRecord[]; events: RunEventRecord[] } | null {
    const svc = this.getService()
    if (!svc) return null
    const runRow = svc.db.queryOne<Record<string, unknown>>('SELECT * FROM workflow_runs WHERE id = ?', [runId])
    if (!runRow) return null
    const stepRows = svc.db.query<Record<string, unknown>>('SELECT * FROM workflow_run_steps WHERE run_id = ? ORDER BY rowid', [runId])
    const eventRows = svc.db.query<Record<string, unknown>>('SELECT * FROM workflow_run_events WHERE run_id = ? ORDER BY sequence', [runId])
    return { run: this.mapRun(runRow), steps: stepRows.map((s) => this.mapStep(s)), events: eventRows.map((e) => this.mapEvent(e)) }
  }

  listRuns(filter: { startedBy?: string; templateId?: string; status?: string; limit?: number } = {}): RunRecord[] {
    const svc = this.getService()
    if (!svc) return []
    const where: string[] = []
    const params: unknown[] = []
    if (filter.startedBy) { where.push('started_by = ?'); params.push(filter.startedBy) }
    if (filter.templateId) { where.push('template_id = ?'); params.push(filter.templateId) }
    if (filter.status) { where.push('status = ?'); params.push(filter.status) }
    const sql = `SELECT * FROM workflow_runs ${where.length > 0 ? 'WHERE ' + where.join(' AND ') : ''} ORDER BY started_at DESC LIMIT ?`
    params.push(filter.limit ?? 50)
    return svc.db.query<Record<string, unknown>>(sql, params).map((r) => this.mapRun(r))
  }

  recoverRunningRuns(): number {
    const svc = this.getService()
    if (!svc) return 0
    const result = svc.db.execute(
      `UPDATE workflow_runs SET status = 'paused' WHERE status = 'running'`
    )
    return result.changes
  }

  pruneOldRuns(olderThanMs: number): number {
    const svc = this.getService()
    if (!svc) return 0
    const cutoff = Date.now() - olderThanMs
    const result = svc.db.execute('DELETE FROM workflow_runs WHERE finished_at IS NOT NULL AND finished_at < ?', [cutoff])
    return result.changes
  }

  private mapRun(r: Record<string, unknown>): RunRecord {
    return {
      id: String(r['id']),
      templateId: String(r['template_id']),
      templateName: String(r['template_name']),
      status: String(r['status']),
      currentStepId: r['current_step_id'] == null ? null : String(r['current_step_id']),
      startedAt: Number(r['started_at']),
      finishedAt: r['finished_at'] == null ? null : Number(r['finished_at']),
      startedBy: r['started_by'] == null ? null : String(r['started_by']),
      parameters: r['parameters_json'] == null ? {} : JSON.parse(String(r['parameters_json'])) as Record<string, unknown>,
      results: r['results_json'] == null ? {} : JSON.parse(String(r['results_json'])) as Record<string, unknown>,
      source: String(r['source']) as RunRecord['source']
    }
  }

  private mapStep(r: Record<string, unknown>): StepRecord {
    return {
      runId: String(r['run_id']),
      stepId: String(r['step_id']),
      state: String(r['state']),
      startedAt: r['started_at'] == null ? null : Number(r['started_at']),
      finishedAt: r['finished_at'] == null ? null : Number(r['finished_at']),
      result: r['result_json'] == null ? null : JSON.parse(String(r['result_json'])),
      error: r['error'] == null ? null : String(r['error']),
      attempt: Number(r['attempt'])
    }
  }

  private mapEvent(r: Record<string, unknown>): RunEventRecord {
    return {
      id: String(r['id']),
      runId: String(r['run_id']),
      stepId: r['step_id'] == null ? null : String(r['step_id']),
      type: String(r['type']),
      at: Number(r['at']),
      message: r['message'] == null ? '' : String(r['message']),
      payload: r['payload_json'] == null ? null : JSON.parse(String(r['payload_json'])),
      sequence: Number(r['sequence'])
    }
  }
}

export function createRunStoreService(getService: () => DatabaseService | null): RunStoreService {
  return new RunStoreImpl(getService)
}

export type { RunStoreService } from './types'
