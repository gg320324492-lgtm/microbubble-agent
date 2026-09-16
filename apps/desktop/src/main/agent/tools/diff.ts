// 行级 diff 生成 — 前后缀修剪算法（O(n)，无外部依赖）。
// 仅服务确认面板预览：上下文行各留 3 行，超出 200 行截断并标注。
import type { DiffLine, FileDiff } from '@shared/types'

export const DIFF_MAX_LINES = 200
const CONTEXT_LINES = 3

/** 覆写场景：旧文 → 新文的行级差异（同一变更块，前后各留少量上下文） */
export function buildLineDiff(oldText: string, newText: string, relPath: string): FileDiff {
  const oldLines = oldText.split(/\r?\n/)
  const newLines = newText.split(/\r?\n/)

  let prefix = 0
  while (prefix < oldLines.length && prefix < newLines.length && oldLines[prefix] === newLines[prefix]) prefix++
  let oldEnd = oldLines.length
  let newEnd = newLines.length
  while (oldEnd > prefix && newEnd > prefix && oldLines[oldEnd - 1] === newLines[newEnd - 1]) {
    oldEnd--
    newEnd--
  }

  const lines: DiffLine[] = []
  let truncated = false
  const push = (line: DiffLine): void => {
    if (lines.length < DIFF_MAX_LINES) lines.push(line)
    else truncated = true
  }
  for (const text of oldLines.slice(Math.max(0, prefix - CONTEXT_LINES), prefix)) push({ kind: 'ctx', text })
  for (let i = prefix; i < oldEnd; i++) push({ kind: 'del', text: oldLines[i] })
  for (let i = prefix; i < newEnd; i++) push({ kind: 'add', text: newLines[i] })
  for (const text of oldLines.slice(oldEnd, Math.min(oldLines.length, oldEnd + CONTEXT_LINES))) push({ kind: 'ctx', text })

  return { path: relPath, kind: 'overwrite', lines, truncated }
}

/** 新建场景：全文按新增行展示 */
export function buildCreateDiff(newText: string, relPath: string): FileDiff {
  const lines: DiffLine[] = []
  let truncated = false
  for (const text of newText.split(/\r?\n/)) {
    if (lines.length < DIFF_MAX_LINES) lines.push({ kind: 'add', text })
    else truncated = true
  }
  return { path: relPath, kind: 'create', lines, truncated }
}
