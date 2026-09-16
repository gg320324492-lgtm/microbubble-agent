// WorkspaceService 契约 — 围栏 ≥7 例（工单 C-1 §5）/ 持久化往返 / AGENT.md 与 .gitignore 维护
// 全部用真实临时目录（os.tmpdir），绝不触碰真实工作区
import { existsSync, mkdirSync, mkdtempSync, readFileSync, rmSync, symlinkSync, writeFileSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { afterEach, describe, expect, it } from 'vitest'
import { WorkspaceEscapeError, WorkspaceService } from '@main/services/workspace/workspace.service'

const cleanup: string[] = []

function makeRoot(): string {
  const dir = mkdtempSync(join(tmpdir(), 'c1-root-'))
  cleanup.push(dir)
  return dir
}

function makeStore(): string {
  const dir = mkdtempSync(join(tmpdir(), 'c1-store-'))
  cleanup.push(dir)
  return dir
}

function makeService(root?: string): { ws: WorkspaceService; root: string } {
  const r = root ?? makeRoot()
  const ws = new WorkspaceService(makeStore())
  ws.setRoot(r)
  return { ws, root: r }
}

afterEach(() => {
  while (cleanup.length) {
    try {
      rmSync(cleanup.pop() as string, { recursive: true, force: true })
    } catch {
      /* Windows 句柄延迟释放时忽略 */
    }
  }
})

describe('WorkspaceService 围栏（安全核心）', () => {
  it('用例1 — ../ 上跳出界 → 拒绝', () => {
    const { ws } = makeService()
    expect(() => ws.resolveInWorkspace('../../outside.txt')).toThrow(WorkspaceEscapeError)
    expect(() => ws.resolveInWorkspace('data/../../outside.txt')).toThrow(WorkspaceEscapeError)
  })

  it('用例2 — 绝对路径出界 → 拒绝（绝对路径一律不入参）', () => {
    const { ws } = makeService()
    expect(() => ws.resolveInWorkspace('C:\\Windows\\notepad.exe')).toThrow(WorkspaceEscapeError)
    expect(() => ws.resolveInWorkspace('/etc/passwd')).toThrow(WorkspaceEscapeError)
  })

  it('用例3 — 符号链接/目录联接出界 → 拒绝', () => {
    const root = makeRoot()
    const outside = mkdtempSync(join(tmpdir(), 'c1-out-'))
    cleanup.push(outside)
    writeFileSync(join(outside, 'secret.txt'), 'outside')
    // junction 在 Windows 无需管理员权限，POSIX 上 type 参数被忽略（等同目录符号链接）
    symlinkSync(outside, join(root, 'link'), 'junction')
    const { ws } = makeService(root)
    expect(() => ws.resolveInWorkspace(join('link', 'secret.txt'))).toThrow(WorkspaceEscapeError)
  })

  it('用例4 — 空路径 → 拒绝', () => {
    const { ws } = makeService()
    expect(() => ws.resolveInWorkspace('')).toThrow(WorkspaceEscapeError)
    expect(() => ws.resolveInWorkspace('   ')).toThrow(WorkspaceEscapeError)
  })

  it('用例5 — 未设 root → 拒绝', () => {
    const ws = new WorkspaceService(makeStore())
    expect(ws.getRoot()).toBeNull()
    expect(() => ws.resolveInWorkspace('notes.md')).toThrow(WorkspaceEscapeError)
  })

  it('用例6 — 恰好等于根 → 放行', () => {
    const { ws } = makeService()
    expect(ws.resolveInWorkspace('.')).toBe(ws.getRoot())
    expect(ws.resolveInWorkspace('sub/..')).toBe(ws.getRoot())
  })

  it('用例7 — .git 段落 → 拒绝（含大小写变体与深层）', () => {
    const { ws } = makeService()
    expect(() => ws.resolveInWorkspace('.git/config')).toThrow(WorkspaceEscapeError)
    expect(() => ws.resolveInWorkspace('sub/.git/objects')).toThrow(WorkspaceEscapeError)
    expect(() => ws.resolveInWorkspace('.GIT/config')).toThrow(WorkspaceEscapeError)
  })

  it('工作区内正常相对路径 → 放行且解析为绝对路径；.gitignore 非禁区', () => {
    const { ws, root } = makeService()
    expect(ws.resolveInWorkspace('data/../notes.md')).toBe(join(ws.getRoot() as string, 'notes.md'))
    expect(ws.resolveInWorkspace('notes.md').startsWith(root)).toBe(true)
    expect(ws.resolveInWorkspace('.gitignore')).toBe(join(ws.getRoot() as string, '.gitignore'))
  })
})

describe('WorkspaceService 持久化与维护', () => {
  it('持久化往返 — 新实例恢复同一 root；未设置的目录为 null', () => {
    const root = makeRoot()
    const store = makeStore()
    const ws1 = new WorkspaceService(store)
    ws1.setRoot(root)
    const ws2 = new WorkspaceService(store)
    expect(ws2.getRoot()).not.toBeNull()
    expect(ws2.getRoot()).toBe(ws1.getRoot())
    expect(ws2.resolveInWorkspace('x.txt').startsWith(ws1.getRoot() as string)).toBe(true)
  })

  it('AGENT.md 不存在时生成，已存在时绝不覆盖', () => {
    const withMarker = makeRoot()
    writeFileSync(join(withMarker, 'AGENT.md'), 'KEEP-MARKER 总指挥预置守则')
    const wsA = new WorkspaceService(makeStore())
    wsA.setRoot(withMarker)
    expect(readFileSync(join(withMarker, 'AGENT.md'), 'utf8')).toBe('KEEP-MARKER 总指挥预置守则')

    const bare = makeRoot()
    const wsB = new WorkspaceService(makeStore())
    wsB.setRoot(bare)
    expect(existsSync(join(bare, 'AGENT.md'))).toBe(true)
    expect(readFileSync(join(bare, 'AGENT.md'), 'utf8')).toContain('Agent 行为守则')
  })

  it('.gitignore 追加 .agent-backups/ 不覆盖已有内容，且幂等', () => {
    const root = makeRoot()
    writeFileSync(join(root, '.gitignore'), 'node_modules/\n')
    const ws = new WorkspaceService(makeStore())
    ws.setRoot(root)
    const once = readFileSync(join(root, '.gitignore'), 'utf8')
    expect(once).toContain('node_modules/')
    expect(once).toContain('.agent-backups/')
    ws.setRoot(root) // 二次设置不得重复追加
    const twice = readFileSync(join(root, '.gitignore'), 'utf8')
    expect(twice.split('.agent-backups/').length - 1).toBe(1)
  })

  it('.gitignore 不存在时新建并只含备份目录', () => {
    const root = makeRoot()
    const ws = new WorkspaceService(makeStore())
    ws.setRoot(root)
    expect(readFileSync(join(root, '.gitignore'), 'utf8').trim()).toBe('.agent-backups/')
  })

  it('setRoot 校验 — 不存在的路径与文件路径拒绝', () => {
    const ws = new WorkspaceService(makeStore())
    expect(() => ws.setRoot(join(tmpdir(), 'c1-no-such-dir-xyz'))).toThrow('目录不存在')
    const file = join(makeRoot(), 'a.txt')
    writeFileSync(file, 'x')
    expect(() => ws.setRoot(file)).toThrow('不是目录')
  })

  it('深层新路径 — 未存在文件按最近已存在祖先（根）校验后放行', () => {
    const { ws } = makeService()
    const resolved = ws.resolveInWorkspace('newdir/deep/新文件.md')
    expect(resolved.startsWith(ws.getRoot() as string)).toBe(true)
    expect(resolved.endsWith('新文件.md')).toBe(true)
    mkdirSync(resolved.replace(/[\\/]新文件\.md$/, ''), { recursive: true }) // 证明路径可直接交给 fs 使用
  })

  it('clearRoot（R-1 打磨）— 清除后回未设置态、持久化文件删除、工作区文件不动、可重设', () => {
    const root = makeRoot()
    writeFileSync(join(root, 'keep.txt'), '保留')
    const store = makeStore()
    const ws = new WorkspaceService(store)
    ws.setRoot(root)
    expect(ws.getRoot()).not.toBeNull()
    ws.clearRoot()
    expect(ws.getRoot()).toBeNull()
    expect(() => ws.resolveInWorkspace('keep.txt')).toThrow(WorkspaceEscapeError)
    expect(existsSync(join(root, 'keep.txt'))).toBe(true) // 工作区文件不受影响
    expect(existsSync(join(store, 'workspace.json'))).toBe(false) // 持久化已清除
    ws.setRoot(root) // 清除后可重新设置
    expect(ws.getRoot()).not.toBeNull()
  })
})
