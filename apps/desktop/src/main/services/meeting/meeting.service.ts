// 本地会议档案服务（M2-2）— 会议 CRUD + 纪要 + 转录（导入/粘贴）+ 附件（增删开）+ FTS 检索。
// 附件本体：filesDir/meetings/<meetingId>/<name>；删除走注入 trashItem，打开走注入 openPath。
// 检索：FTS 单虚表三列（标题/纪要/转录拼接），复用 cjk-bigram 与 buildExcerpt。
import { existsSync, mkdirSync, writeFileSync } from 'node:fs'
import { basename, join } from 'node:path'
import type { SqlDatabase } from '../../db/adapters'
import type { MeetingFile, MeetingSearchHit } from '@shared/types'
import { ftsDeleteRow, ftsSyncRow } from '../../db/fts'
import { matchPhraseFor } from '../knowledge/cjk-bigram'
import { buildExcerpt } from '../knowledge/knowledge.service'

export interface MeetingRow {
  id: number
  user_id: string
  title: string
  meeting_date: number | null
  location: string
  attendees: string
  minutes: string
  created_at: number
  updated_at: number
}

export interface TranscriptRow {
  id: number
  meeting_id: number
  content: string
  source: 'paste' | 'txt' | 'srt'
  created_at: number
  updated_at: number
}

export interface MeetingFileRow {
  id: number
  meeting_id: number
  file_name: string
  file_size: number
  created_at: number
}

export interface MeetingDeps {
  trashItem(absPath: string): Promise<void>
  openPath(absPath: string): Promise<string | undefined>
}

const SEARCH_LIMIT = 50
const TRANSCRIPT_SOURCES = new Set(['paste', 'txt', 'srt'])

export class MeetingService {
  constructor(
    private readonly db: SqlDatabase,
    private readonly filesDir: string | null,
    private readonly deps: MeetingDeps | null
  ) {}

  // ---------- 会议 CRUD ----------

  create(
    userId: string,
    input: { title: string; meetingDate?: number | null; location?: string; attendees?: string[]; minutes?: string }
  ): number {
    const title = String(input?.title ?? '').trim()
    if (!title) throw new Error('会议标题不能为空')
    const now = Date.now()
    const attendees = JSON.stringify((input?.attendees ?? []).map((a) => String(a).trim()).filter(Boolean))
    const res = this.db
      .prepare(
        `INSERT INTO meetings (user_id, title, meeting_date, location, attendees, minutes, created_at, updated_at)
         VALUES (?, ?, ?, ?, ?, ?, ?, ?)`
      )
      .run(
        userId,
        title,
        input?.meetingDate ?? null,
        String(input?.location ?? ''),
        attendees,
        String(input?.minutes ?? ''),
        now,
        now
      )
    const id = Number(res.lastInsertRowid)
    this.rebuildFts(userId, id)
    return id
  }

  list(userId: string): MeetingRow[] {
    return this.db
      .prepare('SELECT * FROM meetings WHERE user_id = ? ORDER BY COALESCE(meeting_date, updated_at) DESC')
      .all(userId) as MeetingRow[]
  }

  get(userId: string, id: number): {
    meeting: MeetingRow
    transcripts: TranscriptRow[]
    files: MeetingFileRow[]
  } | null {
    const meeting = this.getById(userId, id)
    if (!meeting) return null
    const transcripts = this.db
      .prepare('SELECT * FROM meeting_transcripts WHERE meeting_id = ? ORDER BY id ASC')
      .all(id) as TranscriptRow[]
    const files = this.db
      .prepare('SELECT * FROM meeting_files WHERE meeting_id = ? ORDER BY id ASC')
      .all(id) as MeetingFileRow[]
    return { meeting, transcripts, files }
  }

  update(
    userId: string,
    id: number,
    patch: { title?: string; meetingDate?: number | null; location?: string; attendees?: string[]; minutes?: string }
  ): boolean {
    const meeting = this.getById(userId, id)
    if (!meeting) return false
    const title = patch.title !== undefined ? String(patch.title).trim() || meeting.title : meeting.title
    const meetingDate = patch.meetingDate !== undefined ? patch.meetingDate : meeting.meeting_date
    const location = patch.location !== undefined ? String(patch.location) : meeting.location
    const attendees =
      patch.attendees !== undefined
        ? JSON.stringify(patch.attendees.map((a) => String(a).trim()).filter(Boolean))
        : meeting.attendees
    const minutes = patch.minutes !== undefined ? String(patch.minutes) : meeting.minutes
    this.db
      .prepare(
        `UPDATE meetings SET title = ?, meeting_date = ?, location = ?, attendees = ?, minutes = ?, updated_at = ?
         WHERE id = ? AND user_id = ?`
      )
      .run(title, meetingDate, location, attendees, minutes, Date.now(), id, userId)
    this.rebuildFts(userId, id)
    return true
  }

  /** 整会删除：附件文件逐个移入系统回收站，记录（会议/转录/附件行）与 FTS 一并清除 */
  async delete(userId: string, id: number): Promise<boolean> {
    const meeting = this.getById(userId, id)
    if (!meeting) return false
    const files = this.db.prepare('SELECT * FROM meeting_files WHERE meeting_id = ?').all(id) as MeetingFileRow[]
    for (const f of files) {
      const abs = this.attachmentPath(id, f.file_name)
      if (abs && existsSync(abs)) {
        try {
          await this.deps?.trashItem(abs)
        } catch {
        }
      }
    }
    this.db.prepare('DELETE FROM meeting_files WHERE meeting_id = ?').run(id)
    this.db.prepare('DELETE FROM meeting_transcripts WHERE meeting_id = ?').run(id)
    ftsDeleteRow(this.db, 'meeting_fts', id)
    this.db.prepare('DELETE FROM meetings WHERE id = ? AND user_id = ?').run(id, userId)
    return true
  }

  // ---------- 转录 ----------

  importTranscript(
    userId: string,
    meetingId: number,
    input: { content: string; source: 'paste' | 'txt' | 'srt' }
  ): TranscriptRow | null {
    if (!this.getById(userId, meetingId)) return null
    const content = String(input?.content ?? '')
    if (!content.trim()) throw new Error('转录内容不能为空')
    const source = TRANSCRIPT_SOURCES.has(input?.source) ? input.source : 'paste'
    const now = Date.now()
    const res = this.db
      .prepare('INSERT INTO meeting_transcripts (meeting_id, content, source, created_at, updated_at) VALUES (?, ?, ?, ?, ?)')
      .run(meetingId, content, source, now, now)
    const transcriptId = Number(res.lastInsertRowid)
    this.rebuildFts(userId, meetingId)
    return this.getTranscriptById(meetingId, transcriptId)
  }

  updateTranscript(userId: string, meetingId: number, transcriptId: number, content: string): TranscriptRow | null {
    if (!this.getById(userId, meetingId)) return null
    const text = String(content ?? '')
    if (!text.trim()) throw new Error('转录内容不能为空')
    const res = this.db
      .prepare('UPDATE meeting_transcripts SET content = ?, updated_at = ? WHERE id = ? AND meeting_id = ?')
      .run(text, Date.now(), transcriptId, meetingId)
    if (res.changes === 0) return null
    this.rebuildFts(userId, meetingId)
    return this.getTranscriptById(meetingId, transcriptId)
  }

  // ---------- 附件 ----------

  addFile(userId: string, meetingId: number, input: { name: string; data: Uint8Array }): MeetingFile | null {
    if (!this.getById(userId, meetingId)) return null
    const name = basename(String(input?.name ?? '')).trim()
    if (!name) throw new Error('缺少附件文件名')
    const data = input?.data
    if (!data || data.byteLength === 0) throw new Error('附件内容为空')
    const dir = this.meetingDir(meetingId)
    if (!dir) throw new Error('附件存储目录未配置')
    mkdirSync(dir, { recursive: true })
    const abs = this.uniquePath(dir, name)
    writeFileSync(abs, data)
    const now = Date.now()
    const res = this.db
      .prepare('INSERT INTO meeting_files (meeting_id, file_name, file_size, created_at) VALUES (?, ?, ?, ?)')
      .run(meetingId, basename(abs), data.byteLength, now)
    const row = this.db.prepare('SELECT * FROM meeting_files WHERE id = ?').get(Number(res.lastInsertRowid)) as MeetingFileRow
    return { id: row.id, meetingId: row.meeting_id, fileName: row.file_name, fileSize: row.file_size, createdAt: row.created_at }
  }

  /** 删除附件：文件移入系统回收站（注入 trashItem），记录清除 */
  async removeFile(userId: string, meetingId: number, fileId: number): Promise<boolean> {
    if (!this.getById(userId, meetingId)) return false
    const row = this.db
      .prepare('SELECT * FROM meeting_files WHERE id = ? AND meeting_id = ?')
      .get(fileId, meetingId) as MeetingFileRow | undefined
    if (!row) return false
    const abs = this.attachmentPath(meetingId, row.file_name)
    if (abs && existsSync(abs)) {
      try {
        await this.deps?.trashItem(abs)
      } catch {
        /* 回收站失败不阻塞记录删除 */
      }
    }
    this.db.prepare('DELETE FROM meeting_files WHERE id = ? AND meeting_id = ?').run(fileId, meetingId)
    return true
  }

  /** 打开附件：经注入 openPath 打开磁盘文件；返回解析出的路径 */
  openFile(userId: string, meetingId: number, fileId: number): string | null {
    if (!this.getById(userId, meetingId)) return null
    const row = this.db
      .prepare('SELECT * FROM meeting_files WHERE id = ? AND meeting_id = ?')
      .get(fileId, meetingId) as MeetingFileRow | undefined
    if (!row) return null
    const abs = this.attachmentPath(meetingId, row.file_name)
    if (!abs || !existsSync(abs)) throw new Error('附件文件不存在（可能已被移动或删除）')
    void this.deps?.openPath(abs)
    return abs
  }

  // ---------- 检索 ----------

  search(userId: string, query: string): MeetingSearchHit[] {
    const phrase = matchPhraseFor(String(query ?? ''))
    if (!phrase) return []
    const rows = this.db
      .prepare(
        `SELECT m.* FROM meeting_fts f JOIN meetings m ON m.id = f.rowid
         WHERE meeting_fts MATCH ? AND m.user_id = ?
         ORDER BY rank LIMIT ?`
      )
      .all(phrase, userId, SEARCH_LIMIT) as MeetingRow[]
    return rows.map((m) => {
      const transcripts = this.db
        .prepare('SELECT content FROM meeting_transcripts WHERE meeting_id = ? ORDER BY id ASC')
        .all(m.id) as { content: string }[]
      const transcriptText = transcripts.map((t) => t.content).join('\n')
      const inTitle = containsIgnoreCase(m.title, query)
      const inMinutes = containsIgnoreCase(m.minutes, query)
      const inTranscript = containsIgnoreCase(transcriptText, query)
      let hitSource: 'title' | 'minutes' | 'transcript' = 'title'
      let snippetSource = m.title
      if (inMinutes) {
        hitSource = 'minutes'
        snippetSource = m.minutes
      } else if (inTranscript) {
        hitSource = 'transcript'
        snippetSource = transcriptText
      } else if (!inTitle && inTranscript) {
        hitSource = 'transcript'
      }
      const { snippet, highlight } = hitSource === 'title' ? { snippet: m.title, highlight: null } : buildExcerpt(snippetSource, query)
      return {
        id: m.id,
        title: m.title,
        meetingDate: m.meeting_date,
        location: m.location,
        hitSource,
        snippet,
        highlight,
        updatedAt: m.updated_at
      }
    })
  }

  // ---------- 内部 ----------

  private getById(userId: string, id: number): MeetingRow | null {
    return (this.db.prepare('SELECT * FROM meetings WHERE id = ? AND user_id = ?').get(id, userId) as MeetingRow | undefined) ?? null
  }

  private getTranscriptById(meetingId: number, transcriptId: number): TranscriptRow | null {
    return (
      (this.db.prepare('SELECT * FROM meeting_transcripts WHERE id = ? AND meeting_id = ?').get(transcriptId, meetingId) as TranscriptRow | undefined) ??
      null
    )
  }

  /** 重建某会议的 FTS 行：标题 + 纪要 + 全部转录拼接（转录变更频率低，整行重算成本可忽略） */
  private rebuildFts(userId: string, meetingId: number): void {
    const meeting = this.getById(userId, meetingId)
    if (!meeting) return
    const transcripts = this.db
      .prepare('SELECT content FROM meeting_transcripts WHERE meeting_id = ? ORDER BY id ASC')
      .all(meetingId) as { content: string }[]
    ftsSyncRow(this.db, 'meeting_fts', meetingId, {
      title_seg: meeting.title,
      minutes_seg: meeting.minutes,
      transcript_seg: transcripts.map((t) => t.content).join('\n')
    })
  }

  private meetingDir(meetingId: number): string | null {
    if (!this.filesDir) return null
    return join(this.filesDir, 'meetings', String(meetingId))
  }

  private attachmentPath(meetingId: number, fileName: string): string | null {
    const dir = this.meetingDir(meetingId)
    return dir ? join(dir, fileName) : null
  }

  /** 同名附件不覆盖：追加序号 */
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

function containsIgnoreCase(haystack: string, needle: string): boolean {
  return haystack.toLowerCase().includes(needle.trim().toLowerCase())
}
