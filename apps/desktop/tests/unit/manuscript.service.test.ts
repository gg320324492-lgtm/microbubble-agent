// 本地稿件库契约（M3-2）— 迁移 009 / 字数统计纯函数 / 四态 / 检索 / 附件。全部离线。
import { existsSync, mkdirSync, mkdtempSync, readFileSync, renameSync, rmSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { basename, join } from 'node:path'
import { afterAll, afterEach, beforeAll, describe, expect, it, vi } from 'vitest'
import { openNodeSqlite } from '@main/db/adapters'
import { runMigrations } from '@main/db/migrations'
import { ManuscriptService, MANUSCRIPT_STATUSES, manuscriptStats } from '@main/services/manuscript/manuscript.service'

let filesDir = ''
let trashDir = ''
const trashCalls: string[] = []
const openPathCalls: string[] = []
let db: ReturnType<typeof openNodeSqlite>
let svc: ManuscriptService
const USER = 'user-a'

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
  filesDir = mkdtempSync(join(tmpdir(), 'm32-ms-files-'))
  trashDir = join(mkdtempSync(join(tmpdir(), 'm32-ms-trash-')), 'bin')
  db = openNodeSqlite(':memory:')
  runMigrations(db)
  svc = new ManuscriptService(db, filesDir, { trashItem, openPath })
})

afterEach(() => {
  trashCalls.length = 0
  trashItem.mockClear()
  openPath.mockClear()
  openPathCalls.length = 0
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

function createOne(title: string, content = ''): number {
  return svc.create(USER, { title, content })
}

describe('字数统计纯函数', () => {
  it('纯中文 — 每字计 1', () => {
    expect(manuscriptStats('臭氧微纳米气泡降解')).toEqual({ cjkChars: 9, words: 9 })
  })

  it('纯英文 — 按连续串计词', () => {
    expect(manuscriptStats('hello world foo')).toEqual({ cjkChars: 0, words: 3 })
  })

  it('中英混合 — 中文字 + 英文词求和', () => {
    const r = manuscriptStats('臭氧 microbubble 实验 ozonation')
    expect(r.cjkChars).toBe(4) // 臭氧实验
    expect(r.words).toBe(6) // 4 中文字 + 2 英文词
  })
})

describe('迁移 009 与 CRUD', () => {
  it('迁移 009 — manuscripts / manuscript_files / manuscripts_fts 就位', () => {
    const names = (db.prepare("SELECT name FROM sqlite_master WHERE name LIKE 'manuscript%'").all() as { name: string }[]).map((r) => r.name)
    expect(names).toContain('manuscripts')
    expect(names).toContain('manuscript_files')
    expect(names).toContain('manuscripts_fts')
  })

  it('create/get — 字段往返（期刊/标签/正文）', () => {
    const id = createOne('臭氧降解论文', '正文初稿：降解动力学。')
    svc.update(USER, id, { targetJournal: '环境科学学报', tags: ['臭氧', '降解'] })
    const doc = svc.get(USER, id)!.manuscript
    expect(doc.title).toBe('臭氧降解论文')
    expect(doc.status).toBe('draft') // 默认态
    expect(doc.target_journal).toBe('环境科学学报')
    expect(JSON.parse(doc.tags)).toEqual(['臭氧', '降解'])
  })

  it('create — 空标题拒绝', () => {
    expect(() => svc.create(USER, { title: '  ' })).toThrow('标题不能为空')
  })

  it('status 四态流转全合法；非法态拒绝', () => {
    const id = createOne('状态机稿件')
    for (const s of MANUSCRIPT_STATUSES) {
      expect(svc.update(USER, id, { status: s })).toBe(true)
      expect(svc.get(USER, id)!.manuscript.status).toBe(s)
    }
    expect(() => svc.update(USER, id, { status: 'flying' as never })).toThrow('非法状态')
  })

  it('list — status 筛选与更新时间倒序', async () => {
    const d1 = createOne('草稿稿')
    svc.update(USER, d1, { status: 'draft' })
    createOne('另一篇')
    const drafts = svc.list(USER, 'draft')
    expect(drafts.every((r) => r.status === 'draft')).toBe(true)
    const all = svc.list(USER)
    for (let i = 1; i < all.length; i++) expect(all[i - 1].updated_at).toBeGreaterThanOrEqual(all[i].updated_at)
  })
})

describe('FTS5 中文检索', () => {
  it('2 字中文词 — 正文内命中、期刊元信息随行', () => {
    const id = createOne('微纳气泡综述', '正文讨论臭氧化耦合工艺。')
    svc.update(USER, id, { targetJournal: 'Water Research' })
    const hits = svc.search(USER, '臭氧化')
    const hit = hits.find((h) => h.id === id)
    expect(hit).toBeDefined()
    expect(hit!.targetJournal).toBe('Water Research')
    expect(hit!.snippet).toContain('臭氧化')
  })

  it('编辑后索引同步 — 旧词 0 命中、新词命中', () => {
    const id = createOne('同步检查稿', '旧关键词是过硫酸盐')
    expect(svc.search(USER, '过硫酸盐')).toHaveLength(1)
    svc.update(USER, id, { content: '改为讨论高铁酸盐' })
    expect(svc.search(USER, '过硫酸盐')).toHaveLength(0)
    expect(svc.search(USER, '高铁酸盐')).toHaveLength(1)
  })

  it('无命中 / 纯符号 / 空查询安全返回空', () => {
    expect(svc.search(USER, '不存在词xyz')).toHaveLength(0)
    expect(svc.search(USER, '!!!')).toHaveLength(0)
    expect(svc.search(USER, '')).toHaveLength(0)
  })
})

describe('附件三件套与删除', () => {
  it('添加 — 复制落盘字节一致；重名追加 (2)', () => {
    const mid = createOne('附件稿', '')
    const data = new Uint8Array([0x74, 0x65, 0x73, 0x74])
    svc.addFile(USER, mid, { name: '图1.png', data })
    const disk = join(filesDir, 'manuscripts', String(mid), '图1.png')
    expect(existsSync(disk)).toBe(true)
    expect(Buffer.from(readFileSync(disk)).equals(Buffer.from(data))).toBe(true)
    const f2 = svc.addFile(USER, mid, { name: '图1.png', data: new Uint8Array([9]) })
    expect(f2!.file_name).toBe('图1 (2).png')
  })

  it('删除附件 — 移入回收站（注入断言）、记录清除', async () => {
    const mid = createOne('待删附件稿', '')
    const f = svc.addFile(USER, mid, { name: '待删.txt', data: new Uint8Array([1]) })
    const abs = join(filesDir, 'manuscripts', String(mid), '待删.txt')
    const ok = await svc.removeFile(USER, mid, f!.id)
    expect(ok).toBe(true)
    expect(trashCalls[0]).toBe(abs)
    expect(existsSync(abs)).toBe(false)
    expect(existsSync(join(trashDir, '待删.txt'))).toBe(true)
  })

  it('打开附件 — openPath 注入收到绝对路径恰一次', () => {
    const mid = createOne('打开稿', '')
    const f = svc.addFile(USER, mid, { name: 'open.txt', data: new Uint8Array([9]) })
    const path = svc.openFile(USER, mid, f!.id)
    expect(path).toBe(join(filesDir, 'manuscripts', String(mid), 'open.txt'))
    expect(openPathCalls).toEqual([path])
  })

  it('整条删除 — 附件移入回收站、记录与 FTS 清除', async () => {
    const mid = createOne('整删稿', '发光细菌记录')
    svc.addFile(USER, mid, { name: '材料.docx', data: new Uint8Array([7, 7]) })
    const abs = join(filesDir, 'manuscripts', String(mid), '材料.docx')
    const ok = await svc.delete(USER, mid)
    expect(ok).toBe(true)
    expect(svc.get(USER, mid)).toBeNull()
    expect(svc.search(USER, '发光细菌')).toHaveLength(0)
    expect(trashCalls).toContain(abs)
    expect(existsSync(abs)).toBe(false)
  })

  it('用户隔离 — B 用户 list/search/get 全空', () => {
    expect(svc.list('user-b')).toHaveLength(0)
    expect(svc.search('user-b', '降解')).toHaveLength(0)
    expect(svc.get('user-b', 1)).toBeNull()
  })
})
