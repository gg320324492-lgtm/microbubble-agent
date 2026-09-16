// 工作区服务 — Agent 文件操作的安全围栏（工单 C-1）。
// 工作区 = 一个 GitHub 仓库的本地根目录；.git/ 读写禁区、不执行 git 命令。
// 持久化用 node:fs 写 <storeDir>/workspace.json（不引入 electron-store）。
import { existsSync, mkdirSync, readFileSync, realpathSync, rmSync, statSync, writeFileSync } from 'node:fs'
import { basename, dirname, isAbsolute, join, relative, resolve, sep } from 'node:path'

/** 围栏越界 / 禁区命中 — 调用方（工具循环）据此把错误回给模型 */
export class WorkspaceEscapeError extends Error {
  constructor(message: string) {
    super(message)
    this.name = 'WorkspaceEscapeError'
  }
}

const STORE_FILE = 'workspace.json'
const AGENT_MD_FILE = 'AGENT.md'
const GITIGNORE_FILE = '.gitignore'
const GIT_DIR = '.git'
const BACKUP_IGNORE = '.agent-backups/'

/** AGENT.md 缺失时自动生成的守则模板（已存在则绝不覆盖 — 总指挥预置的守则以仓库内为准） */
const AGENT_MD_TEMPLATE = `# AGENT.md — Agent 行为守则

本文件由「小气 · 科研工作台」在首次设置工作区时自动生成（已存在则绝不覆盖）。

## 铁律
1. 只在工作区根目录范围内读写文件；.git/ 为禁区，任何工具不得进入。
2. Agent 不执行任何 git 命令（commit / push / checkout 等一律禁止）。
3. 删除文件走回收站；覆盖写文件前先备份到 .agent-backups/（该目录已在 .gitignore 中维护）。
4. 实验数据只增不改：修改既有记录前必须先征得用户确认。
`

export class WorkspaceService {
  private root: string | null = null

  /** storeDir：JSON 持久化文件所在目录（主进程传 userData 下的路径） */
  constructor(private readonly storeDir: string) {
    this.load()
  }

  private get storeFile(): string {
    return join(this.storeDir, STORE_FILE)
  }

  private load(): void {
    try {
      if (!existsSync(this.storeFile)) return
      const raw = JSON.parse(readFileSync(this.storeFile, 'utf8')) as { root?: unknown }
      if (typeof raw.root === 'string' && raw.root && existsSync(raw.root)) this.root = raw.root
    } catch {
      /* 持久化文件损坏视为未设置，等待下次 setRoot 重写 */
    }
  }

  getRoot(): string | null {
    return this.root
  }

  /**
   * 设置工作区根：必须已存在且为目录；落地前完成
   * AGENT.md 生成（存在即跳过）与 .gitignore 的 .agent-backups/ 维护（追加不覆盖）。
   * 存储前 realpathSync — 根路径本身不允许是符号链接，后续围栏才有稳定基准。
   */
  setRoot(dir: string): void {
    if (typeof dir !== 'string' || dir.trim() === '') throw new Error('工作区路径不能为空')
    if (!existsSync(dir)) throw new Error(`目录不存在: ${dir}`)
    const st = statSync(dir)
    if (!st.isDirectory()) throw new Error(`不是目录: ${dir}`)
    const root = realpathSync(dir)
    this.ensureAgentMd(root)
    this.ensureGitignore(root)
    this.root = root
    mkdirSync(this.storeDir, { recursive: true })
    writeFileSync(this.storeFile, JSON.stringify({ root }, null, 2), 'utf8')
  }

  /** 清除工作区 — 回到未设置态，删除持久化文件（不影响工作区目录内的任何文件） */
  clearRoot(): void {
    this.root = null
    try {
      rmSync(this.storeFile, { force: true })
    } catch {
      /* 删除失败不阻塞（下次 setRoot 会覆写） */
    }
  }

  private ensureAgentMd(root: string): void {
    const file = join(root, AGENT_MD_FILE)
    if (existsSync(file)) return
    writeFileSync(file, AGENT_MD_TEMPLATE, 'utf8')
  }

  private ensureGitignore(root: string): void {
    const file = join(root, GITIGNORE_FILE)
    let content = ''
    try {
      content = readFileSync(file, 'utf8')
    } catch {
      /* 不存在则新建 */
    }
    const has = content.split(/\r?\n/).some((line) => line.trim() === BACKUP_IGNORE)
    if (has) return
    const glue = content === '' || content.endsWith('\n') ? '' : '\n'
    writeFileSync(file, `${content}${glue}${BACKUP_IGNORE}\n`, 'utf8')
  }

  /**
   * 围栏解析 — 把工作区相对路径解析为可直接交给 node:fs 的绝对路径。
   * 规则（工单 C-1 §1）：
   *   a) resolve(root, input) 后仍以 root 为前缀（恰好等于根放行）
   *   b) 对路径上最近一个已存在祖先做 realpathSync 再校验（防符号链接/目录联接逃逸）
   *   c) 路径任何段落等于 .git → 直接拒绝（大小写不敏感，Windows 文件系统本就不区分）
   *   d) 空路径 / 未设 root → 抛 WorkspaceEscapeError
   * 越界一律抛 WorkspaceEscapeError；返回值为真实路径（已解析链接），杜绝后续 fs 调用绕行。
   */
  resolveInWorkspace(inputPath: string): string {
    if (!this.root) throw new WorkspaceEscapeError('未设置工作区，请先在设置页选择工作区目录')
    if (typeof inputPath !== 'string' || inputPath.trim() === '') {
      throw new WorkspaceEscapeError('路径不能为空')
    }
    if (inputPath.includes('\0')) throw new WorkspaceEscapeError('路径包含非法字符')
    if (isAbsolute(inputPath)) throw new WorkspaceEscapeError(`拒绝绝对路径入参: ${inputPath}`)

    const root = this.root
    if (!existsSync(root)) throw new WorkspaceEscapeError(`工作区目录已不存在: ${root}`)

    const resolved = resolve(root, inputPath)

    // a) 前缀校验（relative 在 win32 对大小写不敏感，恰好等于根时 rel 为空串 → 放行）
    const rel = relative(root, resolved)
    if (rel === '..' || rel.startsWith(`..${sep}`) || isAbsolute(rel)) {
      throw new WorkspaceEscapeError(`路径越出工作区: ${inputPath}`)
    }

    // c) .git 禁区 — 任何段落命中即拒
    if (rel !== '' && rel.split(sep).some((seg) => seg.toLowerCase() === GIT_DIR)) {
      throw new WorkspaceEscapeError(`.git 为禁区: ${inputPath}`)
    }

    // b) 符号链接逃逸防护 — 找最近一个已存在的祖先（含自身），realpath 后复核仍以根为前缀
    const real = this.realpathNearest(resolved)
    const relReal = relative(root, real)
    if (relReal === '..' || relReal.startsWith(`..${sep}`) || isAbsolute(relReal)) {
      throw new WorkspaceEscapeError(`路径经符号链接越出工作区: ${inputPath}`)
    }
    return real
  }

  /** 从 target 向上找最近一个已存在的祖先目录，realpath 后拼回未存在的尾部 */
  private realpathNearest(target: string): string {
    let cur = target
    const tail: string[] = []
    for (;;) {
      if (existsSync(cur)) {
        const real = realpathSync(cur)
        return tail.length === 0 ? real : join(real, ...tail)
      }
      const parent = dirname(cur)
      if (parent === cur) return target // 已到盘根仍不存在 — 交给上层前缀校验兜底
      tail.unshift(basename(cur))
      cur = parent
    }
  }
}
