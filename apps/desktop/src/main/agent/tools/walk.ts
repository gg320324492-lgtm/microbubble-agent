// 工具共用递归遍历 — glob / grep 共享。
// 安全约束：.git 任何层级全程跳过；符号链接/目录联接一律不进入（防止链接出界读取）；
// 节点预算硬上限防失控大树。visit 返回 false 即中止整体遍历（用于命中上限提前收工）。
import { readdirSync } from 'node:fs'
import { join } from 'node:path'

export const MAX_WALK_NODES = 20000

export function walkTree(root: string, visit: (abs: string, rel: string, isDir: boolean) => boolean): void {
  let budget = MAX_WALK_NODES
  const rec = (dir: string, rel: string): boolean => {
    let entries: import('node:fs').Dirent[]
    try {
      entries = readdirSync(dir, { withFileTypes: true })
    } catch {
      return true // 无权/已消失的目录跳过，不中断整体
    }
    for (const entry of entries) {
      if (budget-- <= 0) return false
      if (entry.name.toLowerCase() === '.git' || entry.isSymbolicLink()) continue
      const childAbs = join(dir, entry.name)
      const childRel = rel === '' ? entry.name : `${rel}/${entry.name}`
      const isDir = entry.isDirectory()
      if (!visit(childAbs, childRel, isDir)) return false
      if (isDir && !rec(childAbs, childRel)) return false
    }
    return true
  }
  rec(root, '')
}

/** 绝对路径转工作区相对显示（仅用于 summary 展示；根本身显示为 .） */
export function displayRel(abs: string, workspaceRoot: string): string {
  const normAbs = abs.replaceAll('\\', '/')
  const normRoot = workspaceRoot.replaceAll('\\', '/').replace(/\/+$/, '')
  if (!normAbs.startsWith(`${normRoot}/`)) return abs
  const rel = normAbs.slice(normRoot.length + 1)
  return rel === '' ? '.' : rel
}
