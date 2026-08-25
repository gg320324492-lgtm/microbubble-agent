// ELN Engine — Phase 9-C
// ELN 业务逻辑: 创建 / 更新 (版本化) / 提交 / 审核 / 列表 / 导出.

import type { DatabaseService } from '../database.service'
import type {
  ELNEntry,
  ELNEntryType,
  ELNEntryVersion,
  ELNReview,
  ELNReviewStatus,
  ELNService
} from './types'

class ELNEngineImpl implements ELNService {
  constructor(private readonly getService: () => DatabaseService | null) {}

  createEntry(input: { experimentId: string; type: ELNEntryType; title: string; content: string; authorId?: string; metadata?: Record<string, unknown> }): ELNEntry {
    const svc = this.getService()
    if (!svc) throw new Error('数据库未就绪')
    const id = `eln-${Date.now()}-${Math.random().toString(36).slice(2, 6)}`
    const now = Date.now()
    svc.db.execute(
      `INSERT INTO eln_entries (id, experiment_id, type, title, content, author_id, status, metadata_json, version, created_at, updated_at)
       VALUES (?, ?, ?, ?, ?, ?, 'draft', ?, 1, ?, ?)`,
      [id, input.experimentId, input.type, input.title, input.content, input.authorId ?? null, input.metadata ? JSON.stringify(input.metadata) : null, now, now]
    )
    svc.db.execute(
      `INSERT INTO eln_entry_versions (id, entry_id, version, content, author_id, created_at) VALUES (?, ?, 1, ?, ?, ?)`,
      [`${id}-v1`, id, input.content, input.authorId ?? null, now]
    )
    svc.audit.record({ action: 'eln.entry.create', module: 'eln', metadata: { id, experimentId: input.experimentId, type: input.type, authorId: input.authorId } })
    return { id, experimentId: input.experimentId, type: input.type, title: input.title, content: input.content, authorId: input.authorId ?? null, status: 'draft', metadata: input.metadata ?? {}, version: 1, createdAt: now, updatedAt: now }
  }

  getEntry(id: string): { entry: ELNEntry; history: ELNEntryVersion[]; reviews: ELNReview[] } | null {
    const svc = this.getService()
    if (!svc) return null
    const row = svc.db.queryOne<Record<string, unknown>>('SELECT * FROM eln_entries WHERE id = ?', [id])
    if (!row) return null
    const historyRows = svc.db.query<Record<string, unknown>>('SELECT version, content, author_id, created_at FROM eln_entry_versions WHERE entry_id = ? ORDER BY version ASC', [id])
    const reviewRows = svc.db.query<Record<string, unknown>>('SELECT id, entry_id, reviewer_id, decision, comment, created_at FROM eln_reviews WHERE entry_id = ? ORDER BY created_at ASC', [id])
    return {
      entry: this.mapEntry(row),
      history: historyRows.map((h) => ({
        version: Number(h['version']),
        content: String(h['content']),
        authorId: h['author_id'] == null ? null : String(h['author_id']),
        createdAt: Number(h['created_at'])
      })),
      reviews: reviewRows.map((r) => ({
        id: String(r['id']),
        entryId: String(r['entry_id']),
        reviewerId: r['reviewer_id'] == null ? null : String(r['reviewer_id']),
        decision: r['decision'] == null ? 'approve' : String(r['decision']) as 'approve' | 'reject',
        comment: r['comment'] == null ? null : String(r['comment']),
        createdAt: Number(r['created_at'])
      }))
    }
  }

  listByExperiment(experimentId: string): ELNEntry[] {
    const svc = this.getService()
    if (!svc) return []
    return svc.db.query<Record<string, unknown>>(
      'SELECT * FROM eln_entries WHERE experiment_id = ? ORDER BY created_at DESC', [experimentId]
    ).map((r) => this.mapEntry(r))
  }

  updateEntry(id: string, content: string, authorId?: string): ELNEntry {
    const svc = this.getService()
    if (!svc) throw new Error('数据库未就绪')
    const row = svc.db.queryOne<Record<string, unknown>>('SELECT version FROM eln_entries WHERE id = ?', [id])
    if (!row) throw new Error(`ELN 条目 ${id} 不存在`)
    const nextVersion = Number(row['version']) + 1
    const now = Date.now()
    svc.db.execute(
      `UPDATE eln_entries SET content = ?, version = ?, updated_at = ? WHERE id = ?`,
      [content, nextVersion, now, id]
    )
    svc.db.execute(
      `INSERT INTO eln_entry_versions (id, entry_id, version, content, author_id, created_at) VALUES (?, ?, ?, ?, ?, ?)`,
      [`${id}-v${nextVersion}`, id, nextVersion, content, authorId ?? null, now]
    )
    svc.audit.record({ action: 'eln.entry.update', module: 'eln', metadata: { id, version: nextVersion, authorId } })
    return this.getEntry(id)?.entry ?? this.refreshEntry(id, content, now, nextVersion, authorId)
  }

  submitEntry(id: string, authorId?: string): ELNEntry {
    return this.transitionStatus(id, 'submitted', 'eln.entry.submit', authorId)
  }

  approveEntry(id: string, reviewerId?: string, comment?: string): ELNEntry {
    const updated = this.transitionStatus(id, 'approved', 'eln.entry.approve', reviewerId)
    this.recordReview(id, reviewerId, 'approve', comment)
    return updated
  }

  rejectEntry(id: string, reviewerId?: string, comment?: string): ELNEntry {
    const updated = this.transitionStatus(id, 'rejected', 'eln.entry.reject', reviewerId)
    this.recordReview(id, reviewerId, 'reject', comment)
    return updated
  }

  exportEntry(id: string, format: 'md'): string {
    const entry = this.getEntry(id)
    if (!entry) throw new Error(`ELN 条目 ${id} 不存在`)
    if (format !== 'md') throw new Error(`不支持的导出格式: ${format}`)
    return `# ${entry.entry.title}\n\n` +
      `**类型**: ${entry.entry.type}\n` +
      `**状态**: ${entry.entry.status}\n` +
      `**版本**: v${entry.entry.version}\n` +
      `**作者**: ${entry.entry.authorId ?? '匿名'}\n` +
      `**创建**: ${new Date(entry.entry.createdAt).toISOString()}\n\n` +
      `## 内容\n\n${entry.entry.content}\n\n` +
      (entry.reviews.length > 0
        ? `## 审核历史\n\n${entry.reviews.map((r) => `- ${new Date(r.createdAt).toISOString()} ${r.reviewerId ?? '匿名'}: **${r.decision}** ${r.comment ?? ''}`).join('\n')}\n`
        : '')
  }

  private transitionStatus(id: string, status: ELNReviewStatus, action: string, actor?: string): ELNEntry {
    const svc = this.getService()
    if (!svc) throw new Error('数据库未就绪')
    const now = Date.now()
    svc.db.execute(
      `UPDATE eln_entries SET status = ?, updated_at = ? WHERE id = ?`,
      [status, now, id]
    )
    svc.audit.record({ action, module: 'eln', metadata: { id, status, actor } })
    const entry = this.getEntry(id)?.entry
    if (!entry) throw new Error(`ELN 条目 ${id} 不存在`)
    return entry
  }

  private recordReview(entryId: string, reviewerId: string | undefined, decision: 'approve' | 'reject', comment: string | undefined): void {
    const svc = this.getService()
    if (!svc) return
    const id = `rev-${Date.now()}-${Math.random().toString(36).slice(2, 6)}`
    svc.db.execute(
      `INSERT INTO eln_reviews (id, entry_id, reviewer_id, decision, comment, created_at) VALUES (?, ?, ?, ?, ?, ?)`,
      [id, entryId, reviewerId ?? null, decision, comment ?? null, Date.now()]
    )
  }

  private refreshEntry(id: string, content: string, now: number, version: number, authorId: string | undefined): ELNEntry {
    const svc = this.getService()
    if (!svc) throw new Error('数据库未就绪')
    const row = svc.db.queryOne<Record<string, unknown>>('SELECT * FROM eln_entries WHERE id = ?', [id])
    if (!row) throw new Error('条目丢失')
    return { ...this.mapEntry(row), content, version, updatedAt: now, authorId: authorId ?? null }
  }

  private mapEntry(r: Record<string, unknown>): ELNEntry {
    return {
      id: String(r['id']),
      experimentId: String(r['experiment_id']),
      type: String(r['type']) as ELNEntryType,
      title: String(r['title']),
      content: String(r['content']),
      authorId: r['author_id'] == null ? null : String(r['author_id']),
      status: String(r['status']) as ELNReviewStatus,
      metadata: r['metadata_json'] == null ? {} : JSON.parse(String(r['metadata_json'])) as Record<string, unknown>,
      version: Number(r['version']),
      createdAt: Number(r['created_at']),
      updatedAt: Number(r['updated_at'])
    }
  }
}

export function createELNEngine(getService: () => DatabaseService | null): ELNService {
  return new ELNEngineImpl(getService)
}

export type { ELNService }
