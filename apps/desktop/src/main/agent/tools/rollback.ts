// 备份回滚纯函数 — 从 .agent-backups 恢复原内容（ipc 回滚 handler 调用；可离线单测）
import { copyFileSync, existsSync, mkdirSync, statSync } from 'node:fs'
import { dirname } from 'node:path'

/**
 * 把备份内容恢复到目标路径（覆盖目标当前内容）。
 * 路径围栏由调用方先经 WorkspaceService.resolveInWorkspace 解析，这里只做文件级校验。
 */
export function restoreFromBackup(targetAbs: string, backupAbs: string): void {
  if (!existsSync(backupAbs)) throw new Error('备份文件不存在（可能已被清理）')
  if (!statSync(backupAbs).isFile()) throw new Error('备份不是文件')
  mkdirSync(dirname(targetAbs), { recursive: true })
  copyFileSync(backupAbs, targetAbs)
}
