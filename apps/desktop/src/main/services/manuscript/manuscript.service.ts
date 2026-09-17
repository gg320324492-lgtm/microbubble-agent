// 本地稿件库服务（M3-2）— 稿件 CRUD（四态流转）+ 字数统计 + 附件三件套 + FTS 检索。
// 与 knowledge/meetings/experiment 同构：附件本体 filesDir/manuscripts/<manuscriptId>/<name>；
// 删除走注入 trashItem、打开走注入 openPath；检索复用 cjk-bigram + buildExcerpt + fts.ts。
import { existsSync, mkdirSync, writeFileSync } from 'node:fs'
import { basename, join } from 'node:path'
import type { SqlDatabase } from '../../db/adapters'
import { ftsDeleteRow, ftsSyncRow } from '../../db/fts'
import { matchPhraseFor } from '../knowledge/cjk-bigram'
import { buildExcerpt } from '../knowledge/knowledge.service'

export const MANUSCRIPT_STATUSES = ['draft', 'revising', 'submitted', 'published'] as const
export type ManuscriptStatus = (typeof MANUSCRIPT_STATUSES)[number]

export interface ManuscriptRow {
  id: number
  user_id: string
  title: string
  status: ManuscriptStatus
  target_journal: string
  tags: string
  content: string
  created_at: number
  updated_at: number
}

export interface ManuscriptFileRow {
  id: number
  manuscript_id: number
  file_name: string
  file_size: number
  created_at: number
}

export interface ManuscriptDeps {
  trashItem(absPath: string): Promise<void>
  openPath(absPath: string): Promise<string | undefined>
}

const SEARCH_LIMIT = 50

/** 字数统计纯函数 — 中文字符逐字计；英文/数字连续串计 1 词；总词数 = 中文字数 + 西文词数 */
export function manuscriptStats(content: string): { cjkChars: number; words: number } {
  const cjkMatches = content.match(/[\u4e00-\u9fff]/g)
  const cjkChars = cjkMatches ? cjkMatches.length : 0
  const latinWords = content.match(/[A-Za-z0-9]+/g)
  const latinCount = latinWords ? latinWords.length : 0
  return { cjkChars, words: cjkChars + latinCount }
}

export class ManuscriptService {
  constructor(
    private readonly db: SqlDatabase,
    private readonly filesDir: string | null,
    private readonly deps: ManuscriptDeps | null
  ) {}

  // ---------- 稿件 CRUD ----------

  create(
    userId: string,
    input: { title: string; status?: ManuscriptStatus; targetJournal?: string; tags?: string[]; content?: string }
  ): number {
    const title = String(input?.title ?? '').trim()
    if (!title) throw new Error('稿件标题不能为空')
    const status = this.normalizeStatus(input?.status)
    const now = Date.now()
    const tags = JSON.stringify((input?.tags ?? []).map((t) => String(t).trim()).filter(Boolean))
    const content = String(input?.content ?? '')
    const res = this.db
      .prepare(
        `INSERT INTO manuscripts (user_id, title, status, target_journal, tags, content, created_at, updated_at)
         VALUES (?, ?, ?, ?, ?, ?, ?, ?)`
      )
      .run(userId, title, status, String(input?.targetJournal ?? ''), tags, content, now, now)
    const id = Number(res.lastInsertRowid)
    this.syncFts(id, title, content)
    return id
  }

  list(userId: string, status?: ManuscriptStatus): ManuscriptRow[] {
    if (status) {
      return this.db
        .prepare('SELECT * FROM manuscripts WHERE user_id = ? AND status = ? ORDER BY updated_at DESC')
        .all(userId, status) as ManuscriptRow[]
    }
    return this.db
      .prepare('SELECT * FROM manuscripts WHERE user_id = ? ORDER BY updated_at DESC')
      .all(userId) as ManuscriptRow[]
  }

  get(userId: string, id: number): { manuscript: ManuscriptRow; files: ManuscriptFileRow[] } | null {
    const manuscript = this.getById(userId, id)
    if (!manuscript) return null
    const files = this.db
      .prepare('SELECT * FROM manuscript_files WHERE manuscript_id = ? ORDER BY id ASC')
      .all(id) as ManuscriptFileRow[]
    return { manuscript, files }
  }

  update(
    userId: string,
    id: number,
    patch: { title?: string; status?: ManuscriptStatus; targetJournal?: string; tags?: string[]; content?: string }
  ): boolean {
    const row = this.getById(userId, id)
    if (!row) return false
    const title = patch.title !== undefined ? String(patch.title).trim() || row.title : row.title
    const status = patch.status !== undefined ? this.normalizeStatus(patch.status) : row.status
    const targetJournal = patch.targetJournal !== undefined ? String(patch.targetJournal) : row.target_journal
    const tags =
      patch.tags !== undefined ? JSON.stringify(patch.tags.map((t) => String(t).trim()).filter(Boolean)) : row.tags
    const content = patch.content !== undefined ? String(patch.content) : row.content
    this.db
      .prepare(
        `UPDATE manuscripts SET title = ?, status = ?, target_journal = ?, tags = ?, content = ?, updated_at = ?
         WHERE id = ? AND user_id = ?`
      )
      .run(title, status, targetJournal, tags, content, Date.now(), id, userId)
    this.syncFts(id, title, content)
    return true
  }

  /** 整条删除：附件文件逐个移入系统回收站，记录与 FTS 一并清除（语义同会议/ELN） */
  async delete(userId: string, id: number): Promise<boolean> {
    const row = this.getById(userId, id)
    if (!row) return false
    const files = this.db.prepare('SELECT * FROM manuscript_files WHERE manuscript_id = ?').all(id) as ManuscriptFileRow[]
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
    this.db.prepare('DELETE FROM manuscript_files WHERE manuscript_id = ?').run(id)
    ftsDeleteRow(this.db, 'manuscripts_fts', id)
    this.db.prepare('DELETE FROM manuscripts WHERE id = ? AND user_id = ?').run(id, userId)
    return true
  }

  // ---------- 附件 ----------

  addFile(userId: string, manuscriptId: number, input: { name: string; data: Uint8Array }): ManuscriptFileRow | null {
    if (!this.getById(userId, manuscriptId)) return null
    const name = basename(String(input?.name ?? '')).trim()
    if (!name) throw new Error('缺少附件文件名')
    const data = input?.data
    if (!data || data.byteLength === 0) throw new Error('附件内容为空')
    const dir = this.attachmentDir(manuscriptId)
    if (!dir) throw new Error('附件存储目录未配置')
    mkdirSync(dir, { recursive: true })
    const abs = this.uniquePath(dir, name)
    writeFileSync(abs, data)
    const now = Date.now()
    const res = this.db
      .prepare('INSERT INTO manuscript_files (manuscript_id, file_name, file_size, created_at) VALUES (?, ?, ?, ?)')
      .run(manuscriptId, basename(abs), data.byteLength, now)
    const row = this.db.prepare('SELECT * FROM manuscript_files WHERE id = ?').get(Number(res.lastInsertRowid)) as ManuscriptFileRow
    return { id: row.id, manuscript_id: row.manuscript_id, file_name: row.file_name, file_size: row.file_size, created_at: row.created_at }
  }

  /** 删除附件：文件移入系统回收站（注入 trashItem），记录清除 */
  async removeFile(userId: string, manuscriptId: number, fileId: number): Promise<boolean> {
    if (!this.getById(userId, manuscriptId)) return false
    const row = this.db
      .prepare('SELECT * FROM manuscript_files WHERE id = ? AND manuscript_id = ?')
      .get(fileId, manuscriptId) as ManuscriptFileRow | undefined
    if (!row) return false
    const abs = this.attachmentPath(manuscriptId, row.file_name)
    if (abs && existsSync(abs)) {
      try {
        await this.deps?.trashItem(abs)
      } catch {
        /* 回收站失败不阻塞记录删除 */
      }
    }
    this.db.prepare('DELETE FROM manuscript_files WHERE id = ? AND manuscript_id = ?').run(fileId, manuscriptId)
    return true
  }

  /** 打开附件：经注入 openPath 打开磁盘文件；返回解析出的路径 */
  openFile(userId: string, manuscriptId: number, fileId: number): string | null {
    if (!this.getById(userId, manuscriptId)) return null
    const row = this.db
      .prepare('SELECT * FROM manuscript_files WHERE id = ? AND manuscript_id = ?')
      .get(fileId, manuscriptId) as ManuscriptFileRow | undefined
    if (!row) return null
    const abs = this.attachmentPath(manuscriptId, row.file_name)
    if (!abs || !existsSync(abs)) throw new Error('附件文件不存在（可能已被移动或删除）')
    void this.deps?.openPath(abs)
    return abs
  }

  // ---------- 检索 ----------

  search(userId: string, query: string): { id: number; title: string; status: ManuscriptStatus; targetJournal: string; snippet: string; highlight: { start: number; end: number } | null; updatedAt: number }[] {
    const phrase = matchPhraseFor(String(query ?? ''))
    if (!phrase) return []
    const rows = this.db
      .prepare(
        `SELECT m.* FROM manuscripts_fts f JOIN manuscripts m ON m.id = f.rowid
         WHERE manuscripts_fts MATCH ? AND m.user_id = ?
         ORDER BY rank LIMIT ?`
      )
      .all(phrase, userId, SEARCH_LIMIT) as ManuscriptRow[]
    return rows.map((r) => {
      const { snippet, highlight } = buildExcerpt(r.content, query)
      return {
        id: r.id,
        title: r.title,
        status: r.status,
        targetJournal: r.target_journal,
        snippet,
        highlight,
        updatedAt: r.updated_at
      }
    })
  }

  // ---------- 内部 ----------

  private getById(userId: string, id: number): ManuscriptRow | null {
    return (this.db.prepare('SELECT * FROM manuscripts WHERE id = ? AND user_id = ?').get(id, userId) as ManuscriptRow | undefined) ?? null
  }

  private normalizeStatus(status: unknown): ManuscriptStatus {
    const s = String(status ?? 'draft')
    if (!(MANUSCRIPT_STATUSES as readonly string[]).includes(s)) throw new Error(`非法状态: ${s}`)
    return s as ManuscriptStatus
  }

  private syncFts(id: number, title: string, content: string): void {
    ftsSyncRow(this.db, 'manuscripts_fts', id, { title_seg: title, content_seg: content })
  }

  private attachmentDir(manuscriptId: number): string | null {
    if (!this.filesDir) return null
    return join(this.filesDir, 'manuscripts', String(manuscriptId))
  }

  private attachmentPath(manuscriptId: number, fileName: string): string | null {
    const dir = this.attachmentDir(manuscriptId)
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
