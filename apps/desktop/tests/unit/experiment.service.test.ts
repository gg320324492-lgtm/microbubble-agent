// 本地实验记录本契约（M3-1）— 迁移 008 / 编号生成 / 四态 / 检索 / 附件。全部离线。
import { existsSync, mkdirSync, mkdtempSync, readFileSync, renameSync, rmSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { basename, join } from 'node:path'
import { afterAll, afterEach, beforeAll, describe, expect, it, vi } from 'vitest'
import { openNodeSqlite } from '@main/db/adapters'
import { runMigrations } from '@main/db/migrations'
import { ExperimentService, EXPERIMENT_STATUSES } from '@main/services/experiment/experiment.service'

let filesDir = ''
let trashDir = ''
const trashCalls: string[] = []
const openPathCalls: string[] = []
let db: ReturnType<typeof openNodeSqlite>
let svc: ExperimentService
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
  filesDir = mkdtempSync(join(tmpdir(), 'm3-files-'))
  trashDir = join(mkdtempSync(join(tmpdir(), 'm3-trash-')), 'bin')
  db = openNodeSqlite(':memory:')
  runMigrations(db)
  svc = new ExperimentService(db, filesDir, { trashItem, openPath })
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

describe('迁移 008 与编号生成', () => {
  it('迁移 008 — experiments / experiment_files / experiments_fts 就位', () => {
    const names = (db.prepare("SELECT name FROM sqlite_master WHERE name LIKE 'experiment%'").all() as { name: string }[]).map((r) => r.name)
    expect(names).toContain('experiments')
    expect(names).toContain('experiment_files')
    expect(names).toContain('experiments_fts')
  })

  it('编号自动生成 — EXP-YYYYMMDD-01 起同日递增', () => {
    const id1 = svc.create(USER, { title: '实验一' })
    const code1 = svc.get(USER, id1)!.experiment.code
    expect(code1).toMatch(/^EXP-\d{8}-01$/)
    const id2 = svc.create(USER, { title: '实验二' })
    expect(svc.get(USER, id2)!.experiment.code).toMatch(/^EXP-\d{8}-02$/)
  })

  it('编号手改 — 可自定义；重复编号拒绝；改空拒绝', () => {
    const id = svc.create(USER, { title: '手改编号实验', code: 'EXP-CUSTOM-001' })
    expect(svc.get(USER, id)!.experiment.code).toBe('EXP-CUSTOM-001')
    expect(() => svc.create(USER, { title: '撞编号', code: 'EXP-CUSTOM-001' })).toThrow('已存在')
    expect(() => svc.update(USER, id, { code: '  ' })).toThrow('不能为空')
    const id2 = svc.create(USER, { title: '另一实验' })
    expect(() => svc.update(USER, id2, { code: 'EXP-CUSTOM-001' })).toThrow('已存在')
  })

  it('删除后编号可复用 — 序号顺延跳过已占用（不冲突）', () => {
    const id = svc.create(USER, { title: '占位实验' })
    const code = svc.get(USER, id)!.experiment.code
    void svc.delete(USER, id)
    const idNew = svc.create(USER, { title: '新实验' })
    expect(svc.get(USER, idNew)!.experiment.code).not.toBe(code)
    expect(svc.get(USER, idNew)!.experiment.code).toMatch(/^EXP-\d{8}-\d{2}$/)
  })
})

describe('CRUD 与四态流转', () => {
  it('create/get — 标题/标签/记录往返', () => {
    const id = svc.create(USER, { title: '降解动力学实验', tags: ['臭氧', '动力学'], content: '## 步骤\n\n1. 配液' })
    const doc = svc.get(USER, id)!.experiment
    expect(doc.title).toBe('降解动力学实验')
    expect(doc.status).toBe('ongoing') // 默认 ongoing
    expect(doc.content).toContain('配液')
    expect(JSON.parse(doc.tags)).toEqual(['臭氧', '动力学'])
  })

  it('status 四态流转 — 全部合法；非法状态拒绝', () => {
    const id = svc.create(USER, { title: '状态机实验' })
    for (const s of EXPERIMENT_STATUSES) {
      expect(svc.update(USER, id, { status: s })).toBe(true)
      expect(svc.get(USER, id)!.experiment.status).toBe(s)
    }
    expect(() => svc.update(USER, id, { status: 'flying' as never })).toThrow('非法状态')
  })

  it('list — status 筛选与更新时间倒序', async () => {
    const d1 = svc.create(USER, { title: '草稿实验' })
    svc.update(USER, d1, { status: 'draft' })
    const d2 = svc.create(USER, { title: '进行中实验' })
    void d2
    const drafts = svc.list(USER, 'draft')
    expect(drafts.every((r) => r.status === 'draft')).toBe(true)
    expect(drafts.map((r) => r.title)).toContain('草稿实验')
    const all = svc.list(USER)
    for (let i = 1; i < all.length; i++) expect(all[i - 1].updated_at).toBeGreaterThanOrEqual(all[i].updated_at)
  })
})

describe('FTS5 中文检索', () => {
  it('2 字中文词 — 记录内命中且高亮切片正确', () => {
    const id = svc.create(USER, { title: '气泡实验', content: '臭氧微纳米气泡降解四环素，降解率 62%。' })
    const hits = svc.search(USER, '气泡')
    const hit = hits.find((h) => h.id === id)
    expect(hit).toBeDefined()
    expect(hit!.snippet).toContain('气泡')
    expect(hit!.snippet.slice(hit!.highlight!.start, hit!.highlight!.end)).toBe('气泡')
  })

  it('标题检索与多字词', () => {
    const id = svc.create(USER, { title: '四环素降解综述实验', content: '正文' })
    expect(svc.search(USER, '四环素').map((h) => h.id)).toContain(id)
    expect(svc.search(USER, '降解综述').map((h) => h.id)).toContain(id)
  })

  it('编辑后索引同步 — 旧词 0 命中、新词命中', () => {
    const id = svc.create(USER, { title: '同步实验', content: '旧词是斑马鱼' })
    expect(svc.search(USER, '斑马鱼')).toHaveLength(1)
    svc.update(USER, id, { content: '改为水溞趋光性观察' })
    expect(svc.search(USER, '斑马鱼')).toHaveLength(0)
    expect(svc.search(USER, '水溞')).toHaveLength(1)
  })

  it('无命中 / 纯符号 / 空查询安全返回空', () => {
    expect(svc.search(USER, '不存在词xyz')).toHaveLength(0)
    expect(svc.search(USER, '!!!')).toHaveLength(0)
    expect(svc.search(USER, '')).toHaveLength(0)
  })
})

describe('附件三件套与删除', () => {
  it('添加 — 复制落盘字节一致；重名追加 (2)', () => {
    const mid = svc.create(USER, { title: '附件实验' })
    const data = new Uint8Array([0x64, 0x61, 0x74, 0x61])
    svc.addFile(USER, mid, { name: '谱图.csv', data })
    const disk = join(filesDir, 'experiments', String(mid), '谱图.csv')
    expect(existsSync(disk)).toBe(true)
    expect(Buffer.from(readFileSync(disk)).equals(Buffer.from(data))).toBe(true)
    const f2 = svc.addFile(USER, mid, { name: '谱图.csv', data: new Uint8Array([1]) })
    expect(f2!.file_name).toBe('谱图 (2).csv')
  })

  it('删除附件 — 移入回收站（注入断言）、记录清除', async () => {
    const mid = svc.create(USER, { title: '待删附件实验' })
    const f = svc.addFile(USER, mid, { name: '待删.txt', data: new Uint8Array([1]) })
    const abs = join(filesDir, 'experiments', String(mid), '待删.txt')
    const ok = await svc.removeFile(USER, mid, f!.id)
    expect(ok).toBe(true)
    expect(trashCalls[0]).toBe(abs)
    expect(existsSync(abs)).toBe(false)
    expect(existsSync(join(trashDir, '待删.txt'))).toBe(true)
  })

  it('打开附件 — openPath 注入收到绝对路径恰一次', () => {
    const mid = svc.create(USER, { title: '打开实验' })
    const f = svc.addFile(USER, mid, { name: '打开我.txt', data: new Uint8Array([9]) })
    const path = svc.openFile(USER, mid, f!.id)
    expect(path).toBe(join(filesDir, 'experiments', String(mid), '打开我.txt'))
    expect(openPathCalls).toEqual([path])
  })

  it('整条删除 — 附件移入回收站、记录与 FTS 清除', async () => {
    const mid = svc.create(USER, { title: '水母实验', content: '发光水母观察记录' })
    svc.addFile(USER, mid, { name: '水母照片.png', data: new Uint8Array([8, 8]) })
    const abs = join(filesDir, 'experiments', String(mid), '水母照片.png')
    const ok = await svc.delete(USER, mid)
    expect(ok).toBe(true)
    expect(svc.get(USER, mid)).toBeNull()
    expect(svc.search(USER, '水母')).toHaveLength(0)
    expect(trashCalls).toContain(abs)
    expect(existsSync(abs)).toBe(false)
  })

  it('用户隔离 — B 用户 list/search/get 全空', () => {
    expect(svc.list('user-b')).toHaveLength(0)
    expect(svc.search('user-b', '臭氧')).toHaveLength(0)
    expect(svc.get('user-b', 1)).toBeNull()
  })
})
