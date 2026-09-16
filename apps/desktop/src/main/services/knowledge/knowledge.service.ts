// 本地知识库服务（M2-1）— 导入/列表/详情/编辑/删除/FTS5 中文检索。
// 检索：应用层 CJK bigram 预切词写 FTS 索引，查询同切分作 phrase 匹配；
//       snippet/excerpt 在应用层从原文计算（FTS 索引列是切词文本，不适合直接展示）。
// 原件副本：userData/files/knowledge/<id>_<name>，删除时经注入的 trashItem 走系统回收站。
import { existsSync, mkdirSync, writeFileSync } from 'node:fs'
import { basename, dirname, join } from 'node:path'
import type { SqlDatabase } from '../../db/adapters'
import { matchPhraseFor, segmentForIndex } from './cjk-bigram'

export interface KnowledgeDocRow {
  id: number
  user_id: string
  title: string
  content: string
  file_name: string | null
  file_size: number
  tags: string
  source: string
  created_at: number
  updated_at: number
}

export interface KnowledgeDocMeta {
  id: number
  title: string
  tags: string[]
  fileName: string | null
  fileSize: number
  source: string
  createdAt: number
  updatedAt: number
}

export interface KnowledgeDocFull extends KnowledgeDocMeta {
  content: string
}

export interface ImportInput {
  name: string
  content: string
}

export interface ImportResult {
  imported: KnowledgeDocMeta[]
  skipped: { name: string; reason: string }[]
}

export interface SearchHit {
  id: number
  title: string
  tags: string[]
  snippet: string
  highlight: { start: number; end: number } | null
  updatedAt: number
}

export interface TrashDeps {
  trashItem(absPath: string): Promise<void>
}

const EXCERPT_RADIUS = 60
const SEARCH_LIMIT = 50

export class KnowledgeService {
  constructor(
    private readonly db: SqlDatabase,
    private readonly filesDir: string | null,
    private readonly trash: TrashDeps | null
  ) {}

  // ---------- 导入 ----------

  importFromFiles(userId: string, files: ImportInput[]): ImportResult {
    const result: ImportResult = { imported: [], skipped: [] }
    for (const file of files ?? []) {
      const name = String(file?.name ?? '').trim()
      const content = typeof file?.content === 'string' ? file.content : ''
      if (!name) {
        result.skipped.push({ name: name || '(未命名)', reason: '缺少文件名' })
        continue
      }
      if (!content.trim()) {
        result.skipped.push({ name, reason: '空内容' })
        continue
      }
      const dup = this.db
        .prepare('SELECT id FROM knowledge_documents WHERE user_id = ? AND file_name = ?')
        .get(userId, name) as { id: number } | undefined
      if (dup) {
        result.skipped.push({ name, reason: `同名文档已存在（id=${dup.id}），未覆盖` })
        continue
      }
      const now = Date.now()
      const title = name.replace(/\.(md|markdown|txt)$/i, '')
      const size = Buffer.byteLength(content, 'utf8')
      const res = this.db
        .prepare(
          `INSERT INTO knowledge_documents (user_id, title, content, file_name, file_size, tags, source, created_at, updated_at)
           VALUES (?, ?, ?, ?, ?, '[]', 'local_import', ?, ?)`
        )
        .run(userId, title, content, name, size, now, now)
      const id = Number(res.lastInsertRowid)
      this.syncFts(id, title, content)
      this.saveOriginalCopy(id, name, content)
      result.imported.push(this.toMeta(this.getById(userId, id) as KnowledgeDocRow))
    }
    return result
  }

  // ---------- 列表 / 详情 ----------

  list(userId: string): KnowledgeDocMeta[] {
    const rows = this.db
      .prepare(
        `SELECT id, user_id, title, file_name, file_size, tags, source, created_at, updated_at
         FROM knowledge_documents WHERE user_id = ? ORDER BY updated_at DESC`
      )
      .all(userId) as KnowledgeDocRow[]
    return rows.map((r) => this.toMeta(r))
  }

  get(userId: string, id: number): KnowledgeDocFull | null {
    const row = this.getById(userId, id)
    return row ? this.toFull(row) : null
  }

  // ---------- 编辑 ----------

  update(
    userId: string,
    id: number,
    patch: { title?: string; content?: string; tags?: string[] }
  ): KnowledgeDocFull | null {
    const row = this.getById(userId, id)
    if (!row) return null
    const title = patch.title !== undefined ? String(patch.title).trim() || row.title : row.title
    const content = patch.content !== undefined ? String(patch.content) : row.content
    const tags = patch.tags !== undefined ? JSON.stringify(patch.tags.map((t) => String(t).trim()).filter(Boolean)) : row.tags
    this.db
      .prepare('UPDATE knowledge_documents SET title = ?, content = ?, tags = ?, file_size = ?, updated_at = ? WHERE id = ? AND user_id = ?')
      .run(title, content, tags, Buffer.byteLength(content, 'utf8'), Date.now(), id, userId)
    this.syncFts(id, title, content)
    this.saveOriginalCopy(id, row.file_name ?? `${title}.md`, content)
    return this.get(userId, id)
  }

  // ---------- 删除 ----------

  async delete(userId: string, id: number): Promise<boolean> {
    const row = this.getById(userId, id)
    if (!row) return false
    // 原件副本移入系统回收站（注入 trashItem；副本不存在则跳过，不阻塞记录删除）
    if (this.trash && row.file_name) {
      const copyPath = this.originalCopyPath(id, row.file_name)
      if (copyPath && existsSync(copyPath)) {
        try {
          await this.trash.trashItem(copyPath)
        } catch {
          /* 回收站失败不阻塞记录删除（数据仍在库中已删，副本残留可手动清理） */
        }
      }
    }
    this.db.prepare('DELETE FROM knowledge_fts WHERE rowid = ?').run(id)
    this.db.prepare('DELETE FROM knowledge_documents WHERE id = ? AND user_id = ?').run(id, userId)
    return true
  }

  // ---------- 检索 ----------

  search(userId: string, query: string): SearchHit[] {
    const phrase = matchPhraseFor(String(query ?? ''))
    if (!phrase) return []
    const rows = this.db
      .prepare(
        `SELECT d.id, d.user_id, d.title, d.content, d.tags, d.updated_at
         FROM knowledge_fts f JOIN knowledge_documents d ON d.id = f.rowid
         WHERE knowledge_fts MATCH ? AND d.user_id = ?
         ORDER BY rank LIMIT ?`
      )
      .all(phrase, userId, SEARCH_LIMIT) as KnowledgeDocRow[]
    return rows.map((r) => {
      const { snippet, highlight } = buildExcerpt(r.content, String(query))
      return { id: r.id, title: r.title, tags: this.parseTags(r.tags), snippet, highlight, updatedAt: r.updated_at }
    })
  }

  // ---------- 内部 ----------

  private getById(userId: string, id: number): KnowledgeDocRow | null {
    return (this.db.prepare('SELECT * FROM knowledge_documents WHERE id = ? AND user_id = ?').get(id, userId) as KnowledgeDocRow | undefined) ?? null
  }

  private syncFts(id: number, title: string, content: string): void {
    this.db.prepare('DELETE FROM knowledge_fts WHERE rowid = ?').run(id)
    this.db.prepare('INSERT INTO knowledge_fts (rowid, title_seg, content_seg) VALUES (?, ?, ?)').run(id, segmentForIndex(title), segmentForIndex(content))
  }

  private saveOriginalCopy(id: number, name: string, content: string): void {
    if (!this.filesDir) return
    const copyPath = this.originalCopyPath(id, name)
    if (!copyPath) return
    mkdirSync(dirname(copyPath), { recursive: true })
    writeFileSync(copyPath, content, 'utf8')
  }

  private originalCopyPath(id: number, name: string): string | null {
    if (!this.filesDir) return null
    return join(this.filesDir, 'knowledge', `${id}_${basename(name)}`)
  }

  private toMeta(r: KnowledgeDocRow): KnowledgeDocMeta {
    return {
      id: r.id,
      title: r.title,
      tags: this.parseTags(r.tags),
      fileName: r.file_name,
      fileSize: r.file_size,
      source: r.source,
      createdAt: r.created_at,
      updatedAt: r.updated_at
    }
  }

  private toFull(r: KnowledgeDocRow): KnowledgeDocFull {
    return { ...this.toMeta(r), content: r.content }
  }

  private parseTags(raw: string): string[] {
    try {
      const v = JSON.parse(raw)
      return Array.isArray(v) ? v.map(String) : []
    } catch {
      return []
    }
  }
}

/** 从原文计算命中片段与高亮偏移（大小写不敏感；找不到原文位置则返回首段） */
export function buildExcerpt(content: string, query: string, radius = EXCERPT_RADIUS): { snippet: string; highlight: { start: number; end: number } | null } {
  const lower = content.toLowerCase()
  const needle = query.trim().toLowerCase()
  let start = needle ? lower.indexOf(needle) : -1
  if (start < 0) {
    const firstToken = needle.split(/\s+/).find((t) => t && lower.includes(t))
    if (firstToken) start = lower.indexOf(firstToken)
  }
  if (start < 0) {
    const head = content.slice(0, radius * 2)
    return { snippet: head + (content.length > radius * 2 ? '…' : ''), highlight: null }
  }
  const from = Math.max(0, start - radius)
  const to = Math.min(content.length, start + needle.length + radius)
  const snippet = `${from > 0 ? '…' : ''}${content.slice(from, to)}${to < content.length ? '…' : ''}`
  const hlStart = start - from + (from > 0 ? 1 : 0)
  return { snippet, highlight: { start: hlStart, end: hlStart + needle.length } }
}

/** 导出给测试：副本路径解析 */
export function originalCopyPathOf(filesDir: string, id: number, name: string): string {
  return join(filesDir, 'knowledge', `${id}_${basename(name)}`)
}
