// 本地实验记录本服务（M3-1）— 实验条目 CRUD（编号自动生成/四态流转）+ 附件三件套 + FTS 检索。
// 与 knowledge/meetings 同构：附件本体 filesDir/experiments/<experimentId>/<name>；
// 删除走注入 trashItem、打开走注入 openPath；检索复用 cjk-bigram + buildExcerpt + fts.ts。
import { existsSync, mkdirSync, writeFileSync } from 'node:fs'
import { basename, join } from 'node:path'
import type { SqlDatabase } from '../../db/adapters'
import { ftsDeleteRow, ftsSyncRow } from '../../db/fts'
import { matchPhraseFor } from '../knowledge/cjk-bigram'
import { buildExcerpt } from '../knowledge/knowledge.service'

export const EXPERIMENT_STATUSES = ['draft', 'ongoing', 'completed', 'archived'] as const
export type ExperimentStatus = (typeof EXPERIMENT_STATUSES)[number]

export interface ExperimentRow {
  id: number
  user_id: string
  title: string
  code: string
  status: ExperimentStatus
  tags: string
  content: string
  created_at: number
  updated_at: number
}

export interface ExperimentFileRow {
  id: number
  experiment_id: number
  file_name: string
  file_size: number
  created_at: number
}

export interface ExperimentDeps {
  trashItem(absPath: string): Promise<void>
  openPath(absPath: string): Promise<string | undefined>
}

const SEARCH_LIMIT = 50

export class ExperimentService {
  constructor(
    private readonly db: SqlDatabase,
    private readonly filesDir: string | null,
    private readonly deps: ExperimentDeps | null
  ) {}

  // ---------- 实验条目 CRUD ----------

  create(
    userId: string,
    input: { title: string; code?: string; status?: ExperimentStatus; tags?: string[]; content?: string }
  ): number {
    const title = String(input?.title ?? '').trim()
    if (!title) throw new Error('实验标题不能为空')
    const status = this.normalizeStatus(input?.status)
    const now = Date.now()
    const code = input?.code !== undefined && String(input.code).trim() !== '' ? String(input.code).trim() : this.generateCode()
    this.ensureCodeFree(code)
    const tags = JSON.stringify((input?.tags ?? []).map((t) => String(t).trim()).filter(Boolean))
    const content = String(input?.content ?? '')
    const res = this.db
      .prepare(
        `INSERT INTO experiments (user_id, title, code, status, tags, content, created_at, updated_at)
         VALUES (?, ?, ?, ?, ?, ?, ?, ?)`
      )
      .run(userId, title, code, status, tags, content, now, now)
    const id = Number(res.lastInsertRowid)
    this.syncFts(id, title, content)
    return id
  }

  /** 编号自动生成：EXP-YYYYMMDD-当日序号（两位）。取号走当日计数器，删除不回收——编号永不复用 */
  generateCode(now = new Date()): string {
    const y = now.getFullYear()
    const m = String(now.getMonth() + 1).padStart(2, '0')
    const d = String(now.getDate()).padStart(2, '0')
    const prefix = `EXP-${y}${m}${d}-`
    const key = `EXP-${y}${m}${d}`
    const counter = this.db.prepare('SELECT value FROM eln_counters WHERE key = ?').get(key) as { value: number } | undefined
    let seq = (counter?.value ?? 0) + 1
    while (this.db.prepare('SELECT id FROM experiments WHERE code = ?').get(`${prefix}${String(seq).padStart(2, '0')}`)) seq++
    if (counter) this.db.prepare('UPDATE eln_counters SET value = ? WHERE key = ?').run(seq, key)
    else this.db.prepare('INSERT INTO eln_counters (key, value) VALUES (?, ?)').run(key, seq)
    return `${prefix}${String(seq).padStart(2, '0')}`
  }

  list(userId: string, status?: ExperimentStatus): ExperimentRow[] {
    if (status) {
      return this.db
        .prepare('SELECT * FROM experiments WHERE user_id = ? AND status = ? ORDER BY updated_at DESC')
        .all(userId, status) as ExperimentRow[]
    }
    return this.db
      .prepare('SELECT * FROM experiments WHERE user_id = ? ORDER BY updated_at DESC')
      .all(userId) as ExperimentRow[]
  }

  get(userId: string, id: number): { experiment: ExperimentRow; files: ExperimentFileRow[] } | null {
    const experiment = this.getById(userId, id)
    if (!experiment) return null
    const files = this.db
      .prepare('SELECT * FROM experiment_files WHERE experiment_id = ? ORDER BY id ASC')
      .all(id) as ExperimentFileRow[]
    return { experiment, files }
  }

  update(
    userId: string,
    id: number,
    patch: { title?: string; code?: string; status?: ExperimentStatus; tags?: string[]; content?: string }
  ): boolean {
    const row = this.getById(userId, id)
    if (!row) return false
    const title = patch.title !== undefined ? String(patch.title).trim() || row.title : row.title
    const status = patch.status !== undefined ? this.normalizeStatus(patch.status) : row.status
    const tags =
      patch.tags !== undefined ? JSON.stringify(patch.tags.map((t) => String(t).trim()).filter(Boolean)) : row.tags
    const content = patch.content !== undefined ? String(patch.content) : row.content
    let code = row.code
    if (patch.code !== undefined) {
      code = String(patch.code).trim()
      if (!code) throw new Error('实验编号不能为空')
      this.ensureCodeFree(code, id)
    }
    this.db
      .prepare(
        `UPDATE experiments SET title = ?, code = ?, status = ?, tags = ?, content = ?, updated_at = ?
         WHERE id = ? AND user_id = ?`
      )
      .run(title, code, status, tags, content, Date.now(), id, userId)
    this.syncFts(id, title, content)
    return true
  }

  /** 整条删除：附件文件逐个移入系统回收站，记录与 FTS 一并清除（语义同会议） */
  async delete(userId: string, id: number): Promise<boolean> {
    const row = this.getById(userId, id)
    if (!row) return false
    const files = this.db.prepare('SELECT * FROM experiment_files WHERE experiment_id = ?').all(id) as ExperimentFileRow[]
    for (const f of files) {
      const abs = this.attachmentPath(id, f.file_name)
      if (abs && existsSync(abs)) {
        try {
          await this.deps?.trashItem(abs)
        } catch {
          /* 回收站失败不阻塞记录删除 */
        }
      }
    }
    this.db.prepare('DELETE FROM experiment_files WHERE experiment_id = ?').run(id)
    ftsDeleteRow(this.db, 'experiments_fts', id)
    this.db.prepare('DELETE FROM experiments WHERE id = ? AND user_id = ?').run(id, userId)
    return true
  }

  // ---------- 附件 ----------

  addFile(userId: string, experimentId: number, input: { name: string; data: Uint8Array }): ExperimentFileRow | null {
    if (!this.getById(userId, experimentId)) return null
    const name = basename(String(input?.name ?? '')).trim()
    if (!name) throw new Error('缺少附件文件名')
    const data = input?.data
    if (!data || data.byteLength === 0) throw new Error('附件内容为空')
    const dir = this.attachmentDir(experimentId)
    if (!dir) throw new Error('附件存储目录未配置')
    mkdirSync(dir, { recursive: true })
    const abs = this.uniquePath(dir, name)
    writeFileSync(abs, data)
    const now = Date.now()
    const res = this.db
      .prepare('INSERT INTO experiment_files (experiment_id, file_name, file_size, created_at) VALUES (?, ?, ?, ?)')
      .run(experimentId, basename(abs), data.byteLength, now)
    const row = this.db.prepare('SELECT * FROM experiment_files WHERE id = ?').get(Number(res.lastInsertRowid)) as ExperimentFileRow
    return { id: row.id, experiment_id: row.experiment_id, file_name: row.file_name, file_size: row.file_size, created_at: row.created_at }
  }

  /** 删除附件：文件移入系统回收站（注入 trashItem），记录清除 */
  async removeFile(userId: string, experimentId: number, fileId: number): Promise<boolean> {
    if (!this.getById(userId, experimentId)) return false
    const row = this.db
      .prepare('SELECT * FROM experiment_files WHERE id = ? AND experiment_id = ?')
      .get(fileId, experimentId) as ExperimentFileRow | undefined
    if (!row) return false
    const abs = this.attachmentPath(experimentId, row.file_name)
    if (abs && existsSync(abs)) {
      try {
        await this.deps?.trashItem(abs)
      } catch {
        /* 回收站失败不阻塞记录删除 */
      }
    }
    this.db.prepare('DELETE FROM experiment_files WHERE id = ? AND experiment_id = ?').run(fileId, experimentId)
    return true
  }

  /** 打开附件：经注入 openPath 打开磁盘文件；返回解析出的路径 */
  openFile(userId: string, experimentId: number, fileId: number): string | null {
    if (!this.getById(userId, experimentId)) return null
    const row = this.db
      .prepare('SELECT * FROM experiment_files WHERE id = ? AND experiment_id = ?')
      .get(fileId, experimentId) as ExperimentFileRow | undefined
    if (!row) return null
    const abs = this.attachmentPath(experimentId, row.file_name)
    if (!abs || !existsSync(abs)) throw new Error('附件文件不存在（可能已被移动或删除）')
    void this.deps?.openPath(abs)
    return abs
  }

  // ---------- 检索 ----------

  search(userId: string, query: string): { id: number; code: string; title: string; status: ExperimentStatus; tags: string[]; snippet: string; highlight: { start: number; end: number } | null; updatedAt: number }[] {
    const phrase = matchPhraseFor(String(query ?? ''))
    if (!phrase) return []
    const rows = this.db
      .prepare(
        `SELECT e.* FROM experiments_fts f JOIN experiments e ON e.id = f.rowid
         WHERE experiments_fts MATCH ? AND e.user_id = ?
         ORDER BY rank LIMIT ?`
      )
      .all(phrase, userId, SEARCH_LIMIT) as ExperimentRow[]
    return rows.map((r) => {
      const { snippet, highlight } = buildExcerpt(r.content, query)
      return {
        id: r.id,
        code: r.code,
        title: r.title,
        status: r.status,
        tags: this.parseTags(r.tags),
        snippet,
        highlight,
        updatedAt: r.updated_at
      }
    })
  }

  // ---------- 内部 ----------

  private getById(userId: string, id: number): ExperimentRow | null {
    return (this.db.prepare('SELECT * FROM experiments WHERE id = ? AND user_id = ?').get(id, userId) as ExperimentRow | undefined) ?? null
  }

  private normalizeStatus(status: unknown): ExperimentStatus {
    const s = String(status ?? 'ongoing')
    if (!(EXPERIMENT_STATUSES as readonly string[]).includes(s)) throw new Error(`非法状态: ${s}`)
    return s as ExperimentStatus
  }

  private ensureCodeFree(code: string, excludeId?: number): void {
    const row = excludeId
      ? (this.db.prepare('SELECT id FROM experiments WHERE code = ? AND id != ?').get(code, excludeId) as { id: number } | undefined)
      : (this.db.prepare('SELECT id FROM experiments WHERE code = ?').get(code) as { id: number } | undefined)
    if (row) throw new Error(`实验编号已存在: ${code}`)
  }

  private syncFts(id: number, title: string, content: string): void {
    ftsSyncRow(this.db, 'experiments_fts', id, { title_seg: title, content_seg: content })
  }

  private parseTags(raw: string): string[] {
    try {
      const v = JSON.parse(raw)
      return Array.isArray(v) ? v.map(String) : []
    } catch {
      return []
    }
  }

  private attachmentDir(experimentId: number): string | null {
    if (!this.filesDir) return null
    return join(this.filesDir, 'experiments', String(experimentId))
  }

  private attachmentPath(experimentId: number, fileName: string): string | null {
    const dir = this.attachmentDir(experimentId)
    return dir ? join(dir, fileName) : null
  }

  private uniquePath(dir: string, name: string): string {
    let abs = join(dir, name)
    if (!existsSync(abs)) return abs
    const dot = name.lastIndexOf('.')
    const stem = dot > 0 ? name.slice(0, dot) : name
    const ext = dot > 0 ? name.slice(dot) : ''
    let i = 2
    while (existsSync((abs = join(dir, `${stem} (${i})${ext}`)))) i++
    return abs
  }
}
