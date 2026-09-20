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

  it('边界 — 超 24KB 字节预算截断，并在文本尾部给出结构化续读提示（M8-1）', async () => {
    const res = await invoke('read_file', { path: 'big.txt' })
    expect(res.ok).toBe(true)
    const data = res.data as {
      content: string
      truncated: boolean
      size: number
      returnedLines: number
      totalLines: number
      truncation?: { nextOffset?: number; originalBytes: number; maxBytes: number }
    }
    expect(data.truncated).toBe(true)
    expect(data.size).toBe(300 * 1024)
    // 预算为 24KB（含提示本身），故返回文本不超过 24KB 且明显大于 0
    const bytes = Buffer.byteLength(data.content, 'utf8')
    expect(bytes).toBeLessThanOrEqual(24 * 1024)
    expect(bytes).toBeGreaterThan(1024)
    expect(res.summary).toContain('截断')
    // 续读协议闭环：提示可读且给出下一步（big.txt 是单行 300KB → 走「超长行」分支）
    expect(data.content).toContain('[已截断：')
    expect(data.content).toMatch(/超长行|read_file\(path=/)
    expect(data.truncation?.maxBytes).toBe(24 * 1024)
  })

  it('超长行 — 单行超过预算时返回该行前段而非空内容（M8-1 改进点）', async () => {
    const res = await invoke('read_file', { path: 'big.txt' })
    const data = res.data as { content: string }
    // 参考实现此处只返回提示、正文为空；本实现回退为首行部分内容，保证模型至少拿到可用片段
    const body = data.content.split('\n\n')[0] ?? ''
    expect(body.length).toBeGreaterThan(1024)
    expect(body).toMatch(/^a+$/) // 未混入提示文本
  })

  it('续读 — 多行文件按提示的 nextOffset 继续读，能读到后续行（与提示闭环）', async () => {
    // 造一个「行数很多、每行很短」的文件：截断后提示里的 offset 应正好指向未读到的首行
    const lines = Array.from({ length: 4000 }, (_, i) => `第${i + 1}行：${'x'.repeat(20)}`)
    writeFileSync(join(root, 'many-lines.txt'), lines.join('\n'))
    const first = await invoke('read_file', { path: 'many-lines.txt' })
    const d1 = first.data as { truncated: boolean; returnedLines: number; truncation?: { nextOffset?: number } }
    expect(d1.truncated).toBe(true)
    const next = d1.truncation?.nextOffset ?? 1
    expect(next).toBe(d1.returnedLines + 1)
    const res = await invoke('read_file', { path: 'many-lines.txt', offset: next, length: 10 })
    expect(res.ok).toBe(true)
    const data = res.data as { offset: number; returnedLines: number; content: string }
    expect(data.offset).toBe(next)
    expect(data.returnedLines).toBe(10)
    // 续读到的正是第 next 行起（内容可校验，证明 offset 语义正确）
    expect(data.content.split('\n')[0]).toBe(lines[next - 1])
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
describe('M8-2 read_file 超长行按字节窗口读取', () => {
  it('byteOffset 窗口：按字节取，尾部不切断多字节字符，并给出 byteOffset 续读提示', async () => {
    // 造一个单行 100KB 的中文文件（单行超 24KB 预算 → 走字节窗口）
    const oneLine = '中'.repeat(40000) // 120000 字节
    writeFileSync(join(root, 'one-line.txt'), oneLine)

    const first = await invoke('read_file', { path: 'one-line.txt', byteOffset: 0, byteLength: 6000 })
    expect(first.ok).toBe(true)
    const d1 = first.data as {
      byteOffset: number
      byteLength: number
      truncated: boolean
      content: string
      truncation?: { nextByteOffset?: number }
    }
    expect(d1.byteOffset).toBe(0)
    expect(d1.truncated).toBe(true)
    expect(d1.content).not.toContain('\uFFFD') // 未切断码点
    // 正文（提示之前）必须正好是整数字节的中文
    const body = d1.content.split('\n\n[已截断：')[0]!
    expect(Buffer.byteLength(body, 'utf8')).toBe(6000)
    expect(d1.truncation?.nextByteOffset).toBe(6000)
    expect(d1.content).toContain('byteOffset=6000')

    // 从非对齐偏移继续（6001 落在字符中间）→ 丢弃开头半个字符，仍安全
    const mid = await invoke('read_file', { path: 'one-line.txt', byteOffset: 6001, byteLength: 3000 })
    expect(mid.ok).toBe(true)
    const d2 = mid.data as { content: string; byteOffset: number }
    expect(d2.content).not.toContain('\uFFFD')
    expect(d2.content.split('\n\n[已截断：')[0]!.length).toBeGreaterThan(0)

    // 读到末尾 → truncated=false 且无续读提示
    const tail = await invoke('read_file', { path: 'one-line.txt', byteOffset: 119000 })
    const d3 = tail.data as { truncated: boolean; content: string }
    expect(d3.truncated).toBe(false)
    expect(d3.content).not.toContain('[已截断：')
  })

  it('字节窗口与行窗口正交：同一文件两种参数各取其义', async () => {
    const lines = Array.from({ length: 200 }, (_, i) => `第${i + 1}行内容`)
    writeFileSync(join(root, 'two-ways.txt'), lines.join('\n'))
    const byLine = await invoke('read_file', { path: 'two-ways.txt', offset: 3, length: 2 })
    const dl = byLine.data as { offset: number; returnedLines: number; content: string }
    expect(dl.offset).toBe(3)
    expect(dl.returnedLines).toBe(2)
    expect(dl.content.startsWith('第3行内容')).toBe(true)

    const byByte = await invoke('read_file', { path: 'two-ways.txt', byteOffset: 0, byteLength: 20 })
    const db = byByte.data as { byteOffset: number; content: string }
    expect(db.byteOffset).toBe(0)
    expect(db.content.startsWith('第1行内容')).toBe(true)
  })
})
