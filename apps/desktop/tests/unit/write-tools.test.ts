// C-3 写工具契约 — write_file / delete_file / mkdir / diff / 备份回滚（全部临时目录 + 注入 fake）
import { existsSync, mkdirSync, mkdtempSync, readFileSync, readdirSync, renameSync, rmSync, writeFileSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { basename, join } from 'node:path'
import { afterAll, afterEach, beforeAll, describe, expect, it, vi } from "vitest"
import { openNodeSqlite } from '@main/db/adapters'
import { runMigrations } from '@main/db/migrations'
import { AuditService } from '@main/services/workspace/audit.service'
import { WorkspaceService } from '@main/services/workspace/workspace.service'
import { WorkspaceEscapeError } from '@main/services/workspace/workspace.service'
import { ToolRegistry, type ToolContext } from '@main/agent/tool-registry'
import { writeFileTool, WRITE_FILE_MAX_BYTES } from '@main/agent/tools/write-file'
import { mkdirTool } from '@main/agent/tools/mkdir'
import { createDeleteFileTool } from '@main/agent/tools/delete-file'
import { restoreFromBackup } from '@main/agent/tools/rollback'
import { buildCreateDiff, buildLineDiff, DIFF_MAX_LINES } from '@main/agent/tools/diff'
import type { FileDiff } from '@shared/types'

const cleanup: string[] = []
let fixtureRoot = ''
let trashDir = ''
const trashCalls: string[] = []

beforeAll(() => {
  fixtureRoot = mkdtempSync(join(tmpdir(), 'c3-w-root-'))
  trashDir = join(mkdtempSync(join(tmpdir(), 'c3-w-trash-')), 'bin')
  cleanup.push(fixtureRoot, trashDir)
  mkdirSync(join(fixtureRoot, 'docs'), { recursive: true })
  writeFileSync(join(fixtureRoot, 'docs', 'old.txt'), '第一行\n旧内容\n最后一行')
})

/** fake 回收站 — 记录调用并把文件移入 trash 目录（验证「移入而非物理删除」） */
const trashItem = vi.fn(async (abs: string): Promise<void> => {
  trashCalls.push(abs)
  mkdirSync(trashDir, { recursive: true })
  renameSync(abs, join(trashDir, `${basename(abs)}.${trashCalls.length}.trash`))
})

function makeRegistry(): { registry: ToolRegistry; ws: WorkspaceService; audit: AuditService; root: string; ctx: ToolContext } {
  const db = openNodeSqlite(':memory:')
  runMigrations(db)
  const audit = new AuditService(db)
  const store = mkdtempSync(join(tmpdir(), 'c3-w-store-'))
  cleanup.push(store)
  const ws = new WorkspaceService(store)
  ws.setRoot(fixtureRoot)
  const registry = new ToolRegistry(ws, audit)
  registry.register(writeFileTool)
  registry.register(mkdirTool)
  registry.register(createDeleteFileTool({ trashItem }))
  return { registry, ws, audit, root: ws.getRoot() as string, ctx: { userId: 'u1', workspaceRoot: ws.getRoot() as string } }
}

afterEach(() => {
  trashCalls.length = 0
  trashItem.mockClear()
})

function readDirLen(dir: string): number {
  return readdirSync(dir).length
}

afterAll(() => {
  for (const dir of cleanup) {
    try {
      rmSync(dir, { recursive: true, force: true })
    } catch {
      /* Windows 句柄延迟释放时忽略 */
    }
  }
})

describe('write_file', () => {
  it('新建 — 写入成功、无备份、diff 为 create（仅 cardData，不进回喂）', async () => {
    const h = makeRegistry()
    const res = await h.registry.invoke('write_file', { path: 'notes/new-a.txt', content: '你好\n世界' }, h.ctx)
    expect(res.ok).toBe(true)
    expect(readFileSync(join(h.root, 'notes', 'new-a.txt'), 'utf8')).toBe('你好\n世界')
    const data = res.data as { created: boolean; backupPath?: string; path: string }
    expect(data.created).toBe(true)
    expect(data.backupPath).toBeUndefined()
    expect(res.data && typeof res.data === 'object' && 'diff' in res.data).toBe(false) // 回喂不带 diff
    const card = res.cardData as { diff: FileDiff }
    expect(card.diff.kind).toBe('create')
    expect(card.diff.lines.every((l) => l.kind === 'add')).toBe(true)
    expect(res.summary).toContain('new-a.txt') // 回喂只含相对路径
    expect(res.summary).not.toContain('你好') // 绝不回全文
  })

  it('覆写 — 原内容备份到 .agent-backups 且备份内容正确、diff 含删/增行', async () => {
    const h = makeRegistry()
    writeFileSync(join(h.root, 'docs', 'exist.txt'), '旧行一\n旧行二')
    const res = await h.registry.invoke('write_file', { path: 'docs/exist.txt', content: '新行一' }, h.ctx)
    expect(res.ok).toBe(true)
    const data = res.data as { created: boolean; backupPath: string }
    const card = res.cardData as { diff: FileDiff }
    expect(data.created).toBe(false)
    expect(data.backupPath).toMatch(/^\.agent-backups\/.+docs\/exist\.txt$/)
    expect(readFileSync(join(h.root, data.backupPath), 'utf8')).toBe('旧行一\n旧行二') // 备份的是原内容
    expect(readFileSync(join(h.root, 'docs', 'exist.txt'), 'utf8')).toBe('新行一')
    expect(card.diff.lines.some((l) => l.kind === 'del' && l.text === '旧行一')).toBe(true)
    expect(card.diff.lines.some((l) => l.kind === 'add' && l.text === '新行一')).toBe(true)
    expect(res.summary).toContain('备份')
  })

  it('父目录自动创建；超过 2MB 拒绝且不落盘', async () => {
    const h = makeRegistry()
    const deep = await h.registry.invoke('write_file', { path: 'a/b/c/d.txt', content: 'deep' }, h.ctx)
    expect(deep.ok).toBe(true)
    expect(readFileSync(join(h.root, 'a', 'b', 'c', 'd.txt'), 'utf8')).toBe('deep')

    const big = 'x'.repeat(WRITE_FILE_MAX_BYTES + 1)
    const res = await h.registry.invoke('write_file', { path: 'big.txt', content: big }, h.ctx)
    expect(res.ok).toBe(false)
    expect(res.error).toContain('2MB')
    expect(existsSync(join(h.root, 'big.txt'))).toBe(false)
  })

  it('.git 段落由围栏拒绝（invoke 抛 WorkspaceEscapeError）', async () => {
    const h = makeRegistry()
    await expect(h.registry.invoke('write_file', { path: '.git/evil.txt', content: 'x' }, h.ctx)).rejects.toThrow(WorkspaceEscapeError)
  })

  it('preview 生成 diff 但零副作用（不写盘、不建备份）', async () => {
    const h = makeRegistry()
    const before = readFileSync(join(h.root, 'docs', 'old.txt'), 'utf8')
    const backupsBefore = existsSync(join(h.root, '.agent-backups')) ? readDirLen(join(h.root, '.agent-backups')) : 0
    const pv = await writeFileTool.preview!({ path: join(h.root, 'docs', 'old.txt'), content: '全新内容' }, h.ctx)
    expect(pv.ok).toBe(true)
    const data = pv.data as { diff: FileDiff; created: boolean }
    expect(data.created).toBe(false)
    expect(data.diff.lines.some((l) => l.kind === 'del' && l.text === '旧内容')).toBe(true)
    expect(data.diff.lines.some((l) => l.kind === 'add' && l.text === '全新内容')).toBe(true)
    expect(readFileSync(join(h.root, 'docs', 'old.txt'), 'utf8')).toBe(before) // 文件未动
    const backupsAfter = existsSync(join(h.root, '.agent-backups')) ? readDirLen(join(h.root, '.agent-backups')) : 0
    expect(backupsAfter).toBe(backupsBefore) // 未新建备份
  })
})

describe('delete_file', () => {
  it('走回收站而非物理删除 — 注入函数被调、文件移入回收站目录', async () => {
    const h = makeRegistry()
    writeFileSync(join(h.root, 'doomed.txt'), '删我')
    const res = await h.registry.invoke('delete_file', { path: 'doomed.txt' }, h.ctx)
    expect(res.ok).toBe(true)
    expect(trashItem).toHaveBeenCalledTimes(1)
    expect(trashCalls[0]).toBe(join(h.root, 'doomed.txt')) // 调用的是绝对路径
    expect(existsSync(join(h.root, 'doomed.txt'))).toBe(false) // 原位置已移除
    expect(existsSync(join(trashDir, 'doomed.txt.1.trash'))).toBe(true) // 在回收站目录里
    const data = res.data as { trashed: boolean }
    expect(data.trashed).toBe(true)
  })

  it('不存在/目录 → ok:false；preview 给出文件信息', async () => {
    const h = makeRegistry()
    const missing = await h.registry.invoke('delete_file', { path: 'nope.txt' }, h.ctx)
    expect(missing.ok).toBe(false)
    expect(missing.error).toContain('不存在')
    const dir = await h.registry.invoke('delete_file', { path: 'docs' }, h.ctx)
    expect(dir.ok).toBe(false)
    expect(dir.error).toContain('目录')
    const pv = await createDeleteFileTool({ trashItem }).preview!({ path: join(h.root, 'docs', 'old.txt') }, h.ctx)
    expect(pv.ok).toBe(true)
    expect(pv.summary).toContain('回收站')
  })
})

describe('mkdir', () => {
  it('创建含父目录；二次创建幂等；同名文件拒绝', async () => {
    const h = makeRegistry()
    const first = await h.registry.invoke('mkdir', { path: 'x/y/z' }, h.ctx)
    expect(first.ok).toBe(true)
    expect(first.summary).toContain('x/y/z')
    const second = await h.registry.invoke('mkdir', { path: 'x/y/z' }, h.ctx)
    expect(second.ok).toBe(true)
    expect(second.summary).toContain('幂等')
    writeFileSync(join(h.root, '占用.txt'), 'f')
    const clash = await h.registry.invoke('mkdir', { path: '占用.txt' }, h.ctx)
    expect(clash.ok).toBe(false)
    expect(clash.error).toContain('同名文件')
  })
})

describe('diff 与回滚', () => {
  it('buildLineDiff 前后缀修剪正确；超 200 行截断', () => {
    const d = buildLineDiff('公共头\n旧A\n旧B\n公共尾', '公共头\n新A\n公共尾', 'x.txt')
    expect(d.lines.map((l) => `${l.kind}:${l.text}`)).toEqual(['ctx:公共头', 'del:旧A', 'del:旧B', 'add:新A', 'ctx:公共尾'])
    const oldBig = Array.from({ length: DIFF_MAX_LINES + 30 }, (_, i) => `old${i}`).join('\n')
    const d2 = buildLineDiff(oldBig, 'all new', 'y.txt')
    expect(d2.truncated).toBe(true)
    expect(d2.lines.length).toBe(DIFF_MAX_LINES)
    const d3 = buildCreateDiff('a\nb', 'z.txt')
    expect(d3.kind).toBe('create')
    expect(d3.lines).toHaveLength(2)
  })

  it('restoreFromBackup — 恢复原内容；备份缺失抛错', () => {
    const dir = mkdtempSync(join(tmpdir(), 'c3-w-rb-'))
    cleanup.push(dir)
    writeFileSync(join(dir, 'target.txt'), '被覆盖后的内容')
    writeFileSync(join(dir, 'backup.txt'), '原始内容')
    restoreFromBackup(join(dir, 'target.txt'), join(dir, 'backup.txt'))
    expect(readFileSync(join(dir, 'target.txt'), 'utf8')).toBe('原始内容')
    expect(() => restoreFromBackup(join(dir, 't2.txt'), join(dir, 'no-such-backup'))).toThrow('备份文件不存在')
  })
})
