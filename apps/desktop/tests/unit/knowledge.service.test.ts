// 本地知识库契约（M2-1）— 迁移 006 / 导入 / FTS5 中文检索 / 编辑同步 / 删除回收站注入。
// 全部离线：临时目录 + node:sqlite + fake trashItem
import { existsSync, mkdirSync, mkdtempSync, readFileSync, renameSync, rmSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { basename, join } from 'node:path'
import { afterAll, beforeAll, afterEach, describe, expect, it, vi } from 'vitest'
import { openNodeSqlite } from '@main/db/adapters'
import { runMigrations } from '@main/db/migrations'
import {
  KnowledgeService,
  buildExcerpt,
  originalCopyPathOf
} from '@main/services/knowledge/knowledge.service'
import { matchPhraseFor, segmentForIndex } from '@main/services/knowledge/cjk-bigram'

let filesDir = ''
let trashDir = ''
const trashCalls: string[] = []
let db: ReturnType<typeof openNodeSqlite>
let svc: KnowledgeService
const USER = 'user-a'

/** fake 回收站 — 记录调用并把文件移入 trash 目录（验证「移入而非物理删除」） */
const trashItem = vi.fn(async (abs: string): Promise<void> => {
  trashCalls.push(abs)
  mkdirSync(trashDir, { recursive: true })
  renameSync(abs, join(trashDir, basename(abs)))
})

beforeAll(() => {
  filesDir = mkdtempSync(join(tmpdir(), 'm2-files-'))
  trashDir = join(mkdtempSync(join(tmpdir(), 'm2-trash-')), 'bin')
  db = openNodeSqlite(':memory:')
  runMigrations(db)
  svc = new KnowledgeService(db, filesDir, { trashItem })
})

afterEach(() => {
  trashCalls.length = 0
  vi.mocked(trashItem).mockClear()
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

function importOne(name: string, content: string): number {
  const res = svc.importFromFiles(USER, [{ name, content }])
  expect(res.imported).toHaveLength(1)
  return res.imported[0].id
}

describe('迁移 006 与导入', () => {
  it('迁移 006 — knowledge_documents 与 knowledge_fts 就位', () => {
    // FTS 虚表可查询即证明建表成功
    const cols = db.prepare("SELECT COUNT(*) c FROM sqlite_master WHERE name LIKE 'knowledge%'").get() as { c: number }
    expect(cols.c).toBeGreaterThanOrEqual(2)
    expect(() => db.prepare('SELECT * FROM knowledge_fts').all()).not.toThrow()
  })

  it('导入正常 — 标题去扩展名、字节数正确、原件副本落盘', () => {
    const id = importOne('臭氧实验笔记.md', '# 臭氧微纳米气泡降解实验\n\n降解率数据待补。')
    expect(existsSync(originalCopyPathOf(filesDir, id, '臭氧实验笔记.md'))).toBe(true)
    expect(readFileSync(originalCopyPathOf(filesDir, id, '臭氧实验笔记.md'), 'utf8')).toContain('臭氧')
    const doc = svc.get(USER, id)
    expect(doc?.title).toBe('臭氧实验笔记')
    expect(doc?.fileName).toBe('臭氧实验笔记.md')
    expect(doc?.fileSize).toBeGreaterThan(0)
    expect(doc?.tags).toEqual([])
  })

  it('重名文档给提示不静默覆盖；空内容拒绝', () => {
    const r1 = svc.importFromFiles(USER, [{ name: '重名文档.md', content: '第一份' }])
    expect(r1.imported).toHaveLength(1)
    const r2 = svc.importFromFiles(USER, [{ name: '重名文档.md', content: '第二份' }])
    expect(r2.imported).toHaveLength(0)
    expect(r2.skipped[0].reason).toContain('同名文档已存在')
    const empty = svc.importFromFiles(USER, [{ name: 'empty.md', content: '   ' }])
    expect(empty.imported).toHaveLength(0)
    expect(empty.skipped[0].reason).toBe('空内容')
  })

  it('列表按更新时间倒序且不含正文', () => {
    const docs = svc.list(USER)
    expect(docs.length).toBeGreaterThanOrEqual(2)
    for (const d of docs) expect('content' in d).toBe(false)
    for (let i = 1; i < docs.length; i++) expect(docs[i - 1].updatedAt).toBeGreaterThanOrEqual(docs[i].updatedAt)
  })
})

describe('FTS5 中文检索（硬验收项）', () => {
  it('2 字中文词稳定命中（臭氧 / 气泡）', () => {
    expect(svc.search(USER, '臭氧').map((h) => h.title)).toContain('臭氧实验笔记')
    expect(svc.search(USER, '气泡').map((h) => h.title)).toContain('臭氧实验笔记')
  })

  it('多字中文词与短语命中；无命中返回空', () => {
    expect(svc.search(USER, '微纳米气泡')).toHaveLength(1)
    expect(svc.search(USER, '中文检索测试不存在词')).toHaveLength(0)
    expect(svc.search(USER, '!!!')).toHaveLength(0) // 无有效 token 安全返回空
  })

  it('snippet 来自原文且高亮偏移正确', () => {
    const hits = svc.search(USER, '降解率')
    expect(hits).toHaveLength(1)
    const { snippet, highlight } = hits[0]
    expect(snippet).toContain('降解率')
    expect(highlight).not.toBeNull()
    expect(snippet.slice(highlight!.start, highlight!.end)).toBe('降解率')
  })

  it('latin 词命中（大小写不敏感）', () => {
    importOne('latin-doc.md', 'The OZONE experiment uses hElLo world tokens.')
    const hits = svc.search(USER, 'hello')
    expect(hits.map((h) => h.title)).toContain('latin-doc')
  })

  it('编辑后索引同步 — 旧词不再命中、新词命中', () => {
    const id = importOne('同步检查.md', '唯一关键词是斑马鱼')
    expect(svc.search(USER, '斑马鱼')).toHaveLength(1)
    svc.update(USER, id, { content: '改写成水溞趋光性实验记录' })
    expect(svc.search(USER, '斑马鱼')).toHaveLength(0)
    expect(svc.search(USER, '水溞')).toHaveLength(1)
    expect(svc.get(USER, id)?.content).toContain('趋光性')
  })

  it('标题也入索引 — 按标题词可检索', () => {
    importOne('四环素降解综述.md', '综述正文。')
    expect(svc.search(USER, '四环素').map((h) => h.title)).toContain('四环素降解综述')
  })
})

describe('编辑 / 删除 / 用户隔离', () => {
  it('update — 标题/标签可改、updated_at 前移、FTS 同步', async () => {
    const id = importOne('tag-doc.md', '标签演示')
    const before = svc.get(USER, id)!
    await new Promise((r) => setTimeout(r, 5))
    const after = svc.update(USER, id, { title: '改名文档', tags: ['实验', '臭氧'] })
    expect(after?.title).toBe('改名文档')
    expect(after?.tags).toEqual(['实验', '臭氧'])
    expect(after!.updatedAt).toBeGreaterThan(before.updatedAt)
    expect(svc.search(USER, '改名文档')).toHaveLength(1)
  })

  it('delete — 记录删除 + 原件副本移入回收站（注入验证，非物理删除）+ 索引清理', async () => {
    const id = importOne('待删除文档.md', '删除我之后搜不到')
    const copyPath = originalCopyPathOf(filesDir, id, '待删除文档.md')
    expect(existsSync(copyPath)).toBe(true)
    const ok = await svc.delete(USER, id)
    expect(ok).toBe(true)
    expect(svc.get(USER, id)).toBeNull()
    expect(svc.search(USER, '搜不到')).toHaveLength(0)
    expect(trashCalls[0]).toBe(copyPath) // 调用注入的回收站，传绝对路径
    expect(existsSync(copyPath)).toBe(false)
    expect(existsSync(join(trashDir, basename(copyPath)))).toBe(true) // 在回收站目录而非被 unlink
  })

  it('用户隔离 — B 用户查不到 A 的文档', () => {
    importOne('私有文档.md', 'A 的私有内容')
    expect(svc.list('user-b')).toHaveLength(0)
    expect(svc.search('user-b', '私有')).toHaveLength(0)
    expect(svc.get('user-b', 1)).toBeNull()
  })
})

describe('分词器与摘录（选型实现契约）', () => {
  it('bigram 切分与查询构造', () => {
    expect(segmentForIndex('中文检索')).toBe('中文 文检 检索')
    expect(matchPhraseFor('臭氧')).toBe('"臭氧"')
    expect(matchPhraseFor('微纳米气泡')).toBe('"微纳 纳米 米气 气泡"')
    expect(matchPhraseFor('!!!')).toBeNull()
    expect(matchPhraseFor('')).toBeNull()
  })

  it('buildExcerpt — 半径窗口与边界省略号', () => {
    const long = '前'.repeat(100) + '目标词' + '后'.repeat(100)
    const { snippet, highlight } = buildExcerpt(long, '目标词', 10)
    expect(snippet.startsWith('…')).toBe(true)
    expect(highlight).not.toBeNull()
    expect(snippet.slice(highlight!.start, highlight!.end)).toBe('目标词')
  })
})
