// 本地会议档案契约（M2-2）— 迁移 007 / CRUD / 转录 / 附件 / FTS 检索。全部离线。
import { existsSync, mkdirSync, mkdtempSync, readFileSync, renameSync, rmSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { basename, join } from 'node:path'
import { afterAll, afterEach, beforeAll, describe, expect, it, vi } from 'vitest'
import { openNodeSqlite } from '@main/db/adapters'
import { runMigrations } from '@main/db/migrations'
import { MeetingService } from '@main/services/meeting/meeting.service'

let filesDir = ''
let trashDir = ''
const trashCalls: string[] = []
let db: ReturnType<typeof openNodeSqlite>
let svc: MeetingService
const USER = 'user-a'
let openPathCalls: string[] = []

const trashItem = vi.fn(async (abs: string): Promise<void> => {
  trashCalls.push(abs)
  mkdirSync(trashDir, { recursive: true })
  renameSync(abs, join(trashDir, basename(abs)))
})
const openPath = vi.fn(async (abs: string): Promise<string | undefined> => {
  openPathCalls.push(abs)
  return abs
})

beforeAll(() => {
  filesDir = mkdtempSync(join(tmpdir(), 'm2b-files-'))
  trashDir = join(mkdtempSync(join(tmpdir(), 'm2b-trash-')), 'bin')
  db = openNodeSqlite(':memory:')
  runMigrations(db)
  svc = new MeetingService(db, filesDir, { trashItem, openPath })
})

afterEach(() => {
  trashCalls.length = 0
  openPathCalls.length = 0
  trashItem.mockClear()
  openPath.mockClear()
})

afterAll(() => {
  db.close()
  for (const dir of [filesDir, trashDir]) {
    try {
      rmSync(dir, { recursive: true, force: true })
    } catch {
      /* 忽略 */
    }
  }
})

function createMeeting(title: string, minutes = ''): number {
  return svc.create(USER, { title, location: '线上', attendees: ['张三', '李四'], minutes })
}

describe('迁移 007 与会议 CRUD', () => {
  it('迁移 007 — meetings / transcripts / files / meeting_fts 就位', () => {
    const names = (db.prepare("SELECT name FROM sqlite_master WHERE name LIKE 'meeting%'").all() as { name: string }[]).map((r) => r.name)
    expect(names).toContain('meetings')
    expect(names).toContain('meeting_transcripts')
    expect(names).toContain('meeting_files')
    expect(names).toContain('meeting_fts')
  })

  it('create/get — 字段往返、attendees JSON 解析、minutes 存取', () => {
    const id = createMeeting('组会：臭氧降解进展', '## 结论\n\n降解率提升 5%')
    const detail = svc.get(USER, id)!
    expect(detail.meeting.title).toBe('组会：臭氧降解进展')
    expect(detail.meeting.location).toBe('线上')
    expect(detail.meeting.attendees).toBe('["张三","李四"]')
    expect(detail.meeting.minutes).toContain('降解率提升')
    expect(detail.transcripts).toHaveLength(0)
    expect(detail.files).toHaveLength(0)
  })

  it('create — 空标题拒绝', () => {
    expect(() => svc.create(USER, { title: '   ' })).toThrow('标题不能为空')
  })

  it('update — 纪要编辑后 FTS 同步（旧词 0 命中、新词命中）', () => {
    const id = createMeeting('检索同步会议', '旧关键词斑马鱼')
    expect(svc.search(USER, '斑马鱼')).toHaveLength(1)
    svc.update(USER, id, { minutes: '改为讨论水溞趋光性' })
    expect(svc.search(USER, '斑马鱼')).toHaveLength(0)
    expect(svc.search(USER, '水溞')).toHaveLength(1)
  })

  it('list — 按日期/更新时间倒序', () => {
    const a = createMeeting('早会议')
    const b = svc.create(USER, { title: '晚会议', meetingDate: new Date('2026-09-01').getTime() })
    const list = svc.list(USER)
    const ids = list.map((m) => m.id)
    expect(ids).toContain(a)
    expect(ids).toContain(b)
  })

  it('用户隔离 — B 看不到 A 的会议与检索', () => {
    expect(svc.list('user-b')).toHaveLength(0)
    expect(svc.search('user-b', '臭氧')).toHaveLength(0)
    expect(svc.get('user-b', 1)).toBeNull()
  })
})

describe('转录', () => {
  it('粘贴导入 — source=paste；.txt/.srt 导入标记对应 source', () => {
    const mid = createMeeting('转录测试会')
    const paste = svc.importTranscript(USER, mid, { content: '张三：开始吧', source: 'paste' })
    expect(paste?.source).toBe('paste')
    const txt = svc.importTranscript(USER, mid, { content: '00:01 张三 发言', source: 'txt' })
    expect(txt?.source).toBe('txt')
    const srt = svc.importTranscript(USER, mid, { content: '1\n00:00:01,000 --> 00:00:03,000\n李四：好\n', source: 'srt' })
    expect(srt?.source).toBe('srt')
    expect(svc.get(USER, mid)!.transcripts).toHaveLength(3)
  })

  it('转录编辑 — 内容更新后检索同步', () => {
    const mid = createMeeting('转录同步会')
    const t = svc.importTranscript(USER, mid, { content: '旧词是海豚音', source: 'txt' })
    expect(svc.search(USER, '海豚')).toHaveLength(1)
    svc.updateTranscript(USER, mid, t!.id, '新词是蓝鲸直播')
    expect(svc.search(USER, '海豚')).toHaveLength(0)
    expect(svc.search(USER, '蓝鲸')).toHaveLength(1)
  })

  it('转录 — 空内容拒绝、他人会议拒绝', () => {
    const mid = createMeeting('空转录会')
    expect(() => svc.importTranscript(USER, mid, { content: ' ', source: 'txt' })).toThrow('不能为空')
    expect(svc.importTranscript('user-b', mid, { content: 'x', source: 'txt' })).toBeNull()
  })
})

describe('附件', () => {
  it('添加 — 复制落盘且字节一致、记录入库', () => {
    const mid = createMeeting('附件会')
    const data = new Uint8Array([0x25, 0x50, 0x44, 0x46, 0x2d]) // "%PDF-"
    const f = svc.addFile(USER, mid, { name: '数据报告.pdf', data })
    expect(f).not.toBeNull()
    const disk = join(filesDir, 'meetings', String(mid), '数据报告.pdf')
    expect(existsSync(disk)).toBe(true)
    expect(Buffer.from(readFileSync(disk)).equals(Buffer.from(data))).toBe(true)
    expect(f!.fileSize).toBe(data.byteLength)
    void f
  })

  it('删除附件 — 文件移入回收站（注入断言）、记录清除', async () => {
    const mid = createMeeting('附件删除会')
    const f = svc.addFile(USER, mid, { name: '待删附件.txt', data: new Uint8Array([1, 2, 3]) })
    const abs = join(filesDir, 'meetings', String(mid), '待删附件.txt')
    expect(existsSync(abs)).toBe(true)
    const ok = await svc.removeFile(USER, mid, f!.id)
    expect(ok).toBe(true)
    expect(trashCalls[0]).toBe(abs) // 注入 trashItem 收到绝对路径
    expect(existsSync(abs)).toBe(false)
    expect(existsSync(join(trashDir, '待删附件.txt'))).toBe(true)
  })

  it('打开附件 — 注入 openPath 收到绝对路径恰一次', () => {
    const mid = createMeeting('附件打开会')
    const f = svc.addFile(USER, mid, { name: '打开我.txt', data: new Uint8Array([9]) })
    const path = svc.openFile(USER, mid, f!.id)
    expect(path).toBe(join(filesDir, 'meetings', String(mid), '打开我.txt'))
    expect(openPathCalls).toEqual([path])
  })

  it('附件重名不覆盖 — 追加序号成新文件', () => {
    const mid = createMeeting('附件重名会')
    svc.addFile(USER, mid, { name: 'same.txt', data: new Uint8Array([1]) })
    const f2 = svc.addFile(USER, mid, { name: 'same.txt', data: new Uint8Array([2]) })
    expect(f2!.fileName).toBe('same (2).txt')
  })
})

describe('检索与会话删除', () => {
  it('中文 2 字词 — 纪要内命中（hitSource=minutes）', () => {
    const id = svc.create(USER, { title: '组会记录', minutes: '讨论了气泡与臭氧的耦合方案' })
    const hits = svc.search(USER, '气泡')
    const hit = hits.find((h) => h.id === id)
    expect(hit).toBeDefined()
    expect(hit!.hitSource).toBe('minutes')
    expect(hit!.snippet).toContain('气泡')
  })

  it('中文 2 字词 — 转录内命中（hitSource=transcript）', () => {
    const mid = createMeeting('转录检索会')
    svc.importTranscript(USER, mid, { content: '本轮讨论了声呐与潮汐的关联', source: 'txt' })
    const hits = svc.search(USER, '声呐')
    const hit = hits.find((h) => h.id === mid)
    expect(hit).toBeDefined()
    expect(hit!.hitSource).toBe('transcript')
    expect(hit!.snippet).toContain('声呐')
  })

  it('标题命中 — hitSource=title，snippet 即标题', () => {
    const mid = svc.create(USER, { title: '针对蓝藻的专题会', minutes: '普通内容' })
    const hit = svc.search(USER, '蓝藻').find((h) => h.id === mid)
    expect(hit).toBeDefined()
    expect(hit!.hitSource).toBe('title')
    expect(hit!.highlight).toBeNull()
  })

  it('无命中与纯符号查询安全返回空', () => {
    expect(svc.search(USER, '不存在词xyz')).toHaveLength(0)
    expect(svc.search(USER, '!!!')).toHaveLength(0)
    expect(svc.search(USER, '')).toHaveLength(0)
  })

  it('整会删除 — 附件移入回收站、三表记录与 FTS 清除', async () => {
    const mid = createMeeting('待删会议', '讨论发光水母')
    svc.importTranscript(USER, mid, { content: '水母相关转录', source: 'txt' })
    svc.addFile(USER, mid, { name: '会议材料.docx', data: new Uint8Array([7, 7, 7]) })
    const abs = join(filesDir, 'meetings', String(mid), '会议材料.docx')
    expect(existsSync(abs)).toBe(true)

    const ok = await svc.delete(USER, mid)
    expect(ok).toBe(true)
    expect(svc.get(USER, mid)).toBeNull()
    expect(svc.search(USER, '水母')).toHaveLength(0)
    expect(trashCalls).toContain(abs) // 附件进回收站
    expect(existsSync(abs)).toBe(false)
    const tCount = (db.prepare('SELECT COUNT(*) c FROM meeting_transcripts WHERE meeting_id = ?').get(mid) as { c: number }).c
    expect(tCount).toBe(0)
  })
})
