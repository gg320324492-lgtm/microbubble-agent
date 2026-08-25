// Template Store — Phase 9-C
// workflow_templates 表 CRUD.

import type { DatabaseService } from '../database.service'
import type { TemplateStoreService, WorkflowTemplateRecord } from './types'

class TemplateStoreImpl implements TemplateStoreService {
  constructor(private readonly getService: () => DatabaseService | null) {}

  createTemplate(input: { name: string; description: string; category: string; stepsJson: string; createdBy?: string }): WorkflowTemplateRecord {
    const svc = this.getService()
    if (!svc) throw new Error('数据库未就绪')
    const id = `tpl-${Date.now()}-${Math.random().toString(36).slice(2, 6)}`
    const now = Date.now()
    svc.db.execute(
      `INSERT INTO workflow_templates (id, name, description, category, steps_json, schema_version, built_in, created_by, version, created_at, updated_at)
       VALUES (?, ?, ?, ?, ?, 1, 0, ?, 1, ?, ?)`,
      [id, input.name, input.description, input.category, input.stepsJson, input.createdBy ?? null, now, now]
    )
    svc.audit.record({ action: 'workflow.template.create', module: 'eln', metadata: { id, name: input.name, createdBy: input.createdBy } })
    return { id, name: input.name, description: input.description, category: input.category, stepsJson: input.stepsJson, schemaVersion: 1, builtIn: false, createdBy: input.createdBy ?? null, version: 1, createdAt: now, updatedAt: now }
  }

  listTemplates(userId?: string): WorkflowTemplateRecord[] {
    const svc = this.getService()
    if (!svc) return []
    const sql = userId
      ? 'SELECT * FROM workflow_templates WHERE created_by = ? OR built_in = 1 ORDER BY created_at DESC'
      : 'SELECT * FROM workflow_templates ORDER BY created_at DESC'
    const params = userId ? [userId] : []
    return svc.db.query<Record<string, unknown>>(sql, params).map((r) => this.mapRow(r))
  }

  getTemplate(id: string): WorkflowTemplateRecord | null {
    const svc = this.getService()
    if (!svc) return null
    const row = svc.db.queryOne<Record<string, unknown>>('SELECT * FROM workflow_templates WHERE id = ?', [id])
    return row ? this.mapRow(row) : null
  }

  updateTemplate(id: string, name: string, stepsJson: string): WorkflowTemplateRecord {
    const svc = this.getService()
    if (!svc) throw new Error('数据库未就绪')
    const now = Date.now()
    const result = svc.db.execute(
      `UPDATE workflow_templates SET name = ?, steps_json = ?, version = version + 1, updated_at = ? WHERE id = ?`,
      [name, stepsJson, now, id]
    )
    if (result.changes === 0) throw new Error(`模板 ${id} 不存在`)
    const updated = this.getTemplate(id)
    if (!updated) throw new Error(`模板 ${id} 更新后丢失`)
    svc.audit.record({ action: 'workflow.template.update', module: 'eln', metadata: { id, name, version: updated.version } })
    return updated
  }

  deleteTemplate(id: string): boolean {
    const svc = this.getService()
    if (!svc) return false
    const result = svc.db.execute('DELETE FROM workflow_templates WHERE id = ? AND built_in = 0', [id])
    svc.audit.record({ action: 'workflow.template.delete', module: 'eln', metadata: { id, deleted: result.changes > 0 } })
    return result.changes > 0
  }

  private mapRow(r: Record<string, unknown>): WorkflowTemplateRecord {
    return {
      id: String(r['id']),
      name: String(r['name']),
      description: r['description'] == null ? '' : String(r['description']),
      category: String(r['category']),
      stepsJson: String(r['steps_json']),
      schemaVersion: Number(r['schema_version']),
      builtIn: Number(r['built_in']) === 1,
      createdBy: r['created_by'] == null ? null : String(r['created_by']),
      version: Number(r['version']),
      createdAt: Number(r['created_at']),
      updatedAt: Number(r['updated_at'])
    }
  }
}

export function createTemplateStoreService(getService: () => DatabaseService | null): TemplateStoreService {
  return new TemplateStoreImpl(getService)
}

export type { TemplateStoreService } from './types'
