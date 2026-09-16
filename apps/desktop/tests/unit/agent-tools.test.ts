// ToolRegistry + 四个只读工具 + AuditService 契约（工单 C-1 §5）
// node:sqlite（node:fs 直接读文件，不 import 任何依赖 Electron ABI 的模块）；夹具全部在真实临时目录
import { mkdirSync, mkdtempSync, readFileSync, rmSync, writeFileSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { afterAll, afterEach, beforeAll, describe, expect, it } from 'vitest'
import { openNodeSqlite } from '@main/db/adapters'
import { runMigrations } from '@main/db/migrations'
import { AuditService } from '@main/services/workspace/audit.service'
import { WorkspaceEscapeError, WorkspaceService } from '@main/services/workspace/workspace.service'
import { ToolRegistry, type ToolContext, type ToolResult } from '@main/agent/tool-registry'
import { listDirTool } from '@main/agent/tools/list-dir'
import { readFileTool } from '@main/agent/tools/read-file'
import { globTool } from '@main/agent/tools/glob'
import { grepTool } from '@main/agent/tools/grep'

let root = ''
let store = ''
let db: ReturnType<typeof openNodeSqlite>
let registry: ToolRegistry
let ctx: ToolContext

beforeAll(() => {
  root = mkdtempSync(join(tmpdir(), 'c1-tools-root-'))
  store = mkdtempSync(join(tmpdir(), 'c1-tools-store-'))

  // 夹具树（fake .git 也在临时目录内，用于验证工具跳过禁区）
  writeFileSync(join(root, 'notes.md'), '# 会议纪要\nreadme 提到臭氧实验\n')
  mkdirSync(join(root, 'data', 'deep'), { recursive: true })
  writeFileSync(join(root, 'data', 'readme.md'), 'readme first line\nDATA line 42\n')
  writeFileSync(join(root, 'data', 'deep', 'inner.txt'), 'deep content 123\n')
  mkdirSync(join(root, 'many'), { recursive: true })
  for (let i = 0; i < 210; i++) writeFileSync(join(root, 'many', `f${String(i).padStart(4, '0')}.txt`), 'x')
  writeFileSync(join(root, 'binary.bin'), Buffer.from([0x70, 0x00, 0x71]))
  writeFileSync(join(root, 'big.txt'), 'a'.repeat(300 * 1024))
  mkdirSync(join(root, '.git'), { recursive: true })
  writeFileSync(join(root, '.git', 'config'), 'readme inside git\n')

  db = openNodeSqlite(':memory:')
  runMigrations(db)
  const ws = new WorkspaceService(store)
  ws.setRoot(root)
  registry = new ToolRegistry(ws, new AuditService(db))
  registry.register(listDirTool)
  registry.register(readFileTool)
  registry.register(globTool)
  registry.register(grepTool)
  ctx = { userId: 'user-a', workspaceRoot: ws.getRoot() as string }
})

afterEach(() => {
  db.prepare('DELETE FROM workspace_audit').run()
})

afterAll(() => {
  db.close()
  for (const dir of [root, store]) {
    try {
      rmSync(dir, { recursive: true, force: true })
    } catch {
      /* Windows 句柄延迟释放时忽略 */
    }
  }
})

function invoke(name: string, input: Record<string, unknown>): Promise<ToolResult> {
  return registry.invoke(name, input, ctx)
}

describe('ToolRegistry 统一入口', () => {
  it('注册/获取/列表 — 四工具就位', () => {
    expect(registry.list().map((t) => t.name).sort()).toEqual(['glob', 'grep', 'list_dir', 'read_file'])
    expect(registry.get('list_dir')?.permission).toBe('auto')
    expect(registry.get('nope')).toBeUndefined()
  })

  it('未注册工具 invoke → 报错', async () => {
    await expect(registry.invoke('rm_rf', {}, ctx)).rejects.toThrow('未注册的工具')
  })

  it('invoke 成功 → 审计前后各一条；结果 ok=1', async () => {
    const res = await invoke('list_dir', { path: 'data' })
    expect(res.ok).toBe(true)
    const rows = new AuditService(db).list(10)
    expect(rows).toHaveLength(2)
    expect(rows[0].ok).toBe(1) // 后审计（id 大 = 最新）
    expect(rows[1].input_summary).toContain('"path":"data"') // 前审计记录原始入参
  })

  it('路径参数围栏校验在审计之前 — 越界尝试不留审计且抛 WorkspaceEscapeError', async () => {
    await expect(invoke('read_file', { path: '../outside.txt' })).rejects.toThrow(WorkspaceEscapeError)
    expect(new AuditService(db).list(10)).toHaveLength(0)
  })

  it('工具执行抛异常 → 返回 ok:false 的 ToolResult，审计落 ok=0', async () => {
    registry.register({
      name: 'boom',
      description: '测试用必炸工具',
      permission: 'auto',
      parameters: { type: 'object', properties: {}, required: [] },
      execute: async () => {
        throw new Error('爆炸')
      }
    })
    const res = await invoke('boom', {})
    expect(res.ok).toBe(false)
    expect(res.error).toContain('爆炸')
    const rows = new AuditService(db).list(10)
    expect(rows[0].ok).toBe(0)
    expect(rows[0].input_summary).toContain('爆炸')
  })
})

describe('list_dir', () => {
  it('正常 — 列出名称/类型，目录在前', async () => {
    const res = await invoke('list_dir', { path: 'data' })
    expect(res.ok).toBe(true)
    const entries = (res.data as { entries: { name: string; type: string }[] }).entries
    expect(entries.map((e) => e.name)).toEqual(['deep', 'readme.md']) // 目录在前
    expect(entries[0].type).toBe('dir')
    expect(entries[1].type).toBe('file')
    expect(res.summary).toContain('data')
  })

  it('异常 — 非目录/不存在 → ok:false', async () => {
    const notDir = await invoke('list_dir', { path: 'notes.md' })
    expect(notDir.ok).toBe(false)
    expect(notDir.error).toContain('不是目录')
    const missing = await invoke('list_dir', { path: 'no-such-dir' })
    expect(missing.ok).toBe(false)
    expect(missing.error).toContain('不存在')
  })
})

describe('read_file', () => {
  it('正常 — UTF-8 内容完整返回', async () => {
    const res = await invoke('read_file', { path: 'data/deep/inner.txt' })
    expect(res.ok).toBe(true)
    expect((res.data as { content: string }).content).toContain('deep content 123')
    expect((res.data as { truncated: boolean }).truncated).toBe(false)
  })

  it('异常 — NUL 字节判定二进制 → 拒读', async () => {
    const res = await invoke('read_file', { path: 'binary.bin' })
    expect(res.ok).toBe(false)
    expect(res.error).toContain('二进制')
  })

  it('边界 — 超 256KB 截断并在 summary 注明', async () => {
    const res = await invoke('read_file', { path: 'big.txt' })
    expect(res.ok).toBe(true)
    const data = res.data as { content: string; truncated: boolean; size: number }
    expect(data.truncated).toBe(true)
    expect(data.size).toBe(300 * 1024)
    expect(data.content.length).toBe(256 * 1024)
    expect(res.summary).toContain('截断')
  })
})

describe('glob', () => {
  it('正常 — **/*.md 命中根级与嵌套（含 setRoot 生成的 AGENT.md），跳过 .git', async () => {
    const res = await invoke('glob', { pattern: '**/*.md' })
    expect(res.ok).toBe(true)
    const matches = (res.data as { matches: string[] }).matches.sort()
    expect(matches).toEqual(['AGENT.md', 'data/readme.md', 'notes.md'])
    expect((res.data as { truncated: boolean }).truncated).toBe(false)
  })

  it('纯文件名模式递归所有层级；无命中返回空数组', async () => {
    const all = await invoke('glob', { pattern: 'inner.txt' })
    expect((all.data as { matches: string[] }).matches).toEqual(['data/deep/inner.txt'])
    const none = await invoke('glob', { pattern: '*.csv' })
    expect((none.data as { matches: string[] }).matches).toEqual([])
  })

  it('上限 200 条 — 210 个文件只返回 200 并标记截断', async () => {
    const res = await invoke('glob', { pattern: 'many/*.txt' })
    const data = res.data as { matches: string[]; truncated: boolean }
    expect(data.matches).toHaveLength(200)
    expect(data.truncated).toBe(true)
    expect(res.summary).toContain('200')
  })

  it('异常 — 绝对路径模式与 .. 段拒绝（ok:false）', async () => {
    const abs = await invoke('glob', { pattern: 'C:/Windows/*.exe' })
    expect(abs.ok).toBe(false)
    expect(abs.error).toContain('绝对')
    const dots = await invoke('glob', { pattern: 'data/../../*.txt' })
    expect(dots.ok).toBe(false)
    expect(dots.error).toContain('..')
  })
})

describe('grep', () => {
  it('正常 — 子串默认不分大小写，跳过 .git 与二进制', async () => {
    const res = await invoke('grep', { pattern: 'READ' })
    expect(res.ok).toBe(true)
    const matches = (res.data as { matches: string[] }).matches
    expect(matches).toContain('data/readme.md:1:readme first line')
    expect(matches.every((m) => !m.startsWith('.git/'))).toBe(true)
  })

  it('大小写开关 — case_sensitive 后小写不再命中大写模式', async () => {
    const sensitive = await invoke('grep', { pattern: 'READ', case_sensitive: true })
    expect((sensitive.data as { matches: string[] }).matches).toEqual([])
    const keep = await invoke('grep', { pattern: 'DATA', case_sensitive: true })
    expect((keep.data as { matches: string[] }).matches).toContain('data/readme.md:2:DATA line 42')
  })

  it('正则模式 — \\d+ 命中数字行；无效正则报错', async () => {
    const res = await invoke('grep', { pattern: '\\d{2,}', is_regex: true })
    const matches = (res.data as { matches: string[] }).matches
    expect(matches).toContain('data/readme.md:2:DATA line 42')
    expect(matches).toContain('data/deep/inner.txt:1:deep content 123')
    const bad = await invoke('grep', { pattern: '([', is_regex: true })
    expect(bad.ok).toBe(false)
    expect(bad.error).toContain('正则无效')
  })

  it('限定子目录 — path 指向 data 时只搜该范围', async () => {
    const res = await invoke('grep', { pattern: 'readme', path: 'data' })
    const matches = (res.data as { matches: string[] }).matches
    expect(matches.length).toBeGreaterThan(0)
    expect(matches.every((m) => m.startsWith('data/'))).toBe(true)
  })
})

describe('AuditService', () => {
  it('record/list — 新的在前，limit 生效', () => {
    const audit = new AuditService(db)
    audit.record('user-a', 'list_dir', 'a1', true)
    audit.record('user-a', 'read_file', 'a2', false)
    audit.record('user-b', 'glob', 'a3', true)
    const top2 = audit.list(2)
    expect(top2.map((r) => r.tool)).toEqual(['glob', 'read_file'])
    expect(top2[0].ok).toBe(1)
    expect(top2[1].ok).toBe(0)
    expect(top2[0].user_id).toBe('user-b')
  })

  it('迁移 004 — workspace_audit 表在迁移链中自动创建', () => {
    const tables = (db.prepare("SELECT name FROM sqlite_master WHERE type='table'").all() as { name: string }[]).map((r) => r.name)
    expect(tables).toContain('workspace_audit')
    expect(readFileSync(join(root, 'AGENT.md'), 'utf8')).toContain('Agent 行为守则') // setRoot 附带生效
  })
})
