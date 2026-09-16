// write_file 工具 — 创建/覆写 UTF-8 文本（permission: confirm）。
// 覆写前自动备份原内容到 .agent-backups/<时间戳>/<相对路径>（AGENT.md 守则承诺）；
// 单文件上限 2MB；成功回喂只含 summary + 相对路径，diff 走卡片展示不进模型上下文。
import { copyFileSync, existsSync, mkdirSync, readFileSync, statSync, writeFileSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { randomBytes } from 'node:crypto'
import type { ToolContext, ToolResult } from '../tool-registry'
import { buildCreateDiff, buildLineDiff } from './diff'
import { displayRel } from './walk'

export const WRITE_FILE_MAX_BYTES = 2 * 1024 * 1024

interface WriteData {
  path: string
  bytes: number
  created: boolean
  backupPath?: string
  diff?: import('@shared/types').FileDiff
  rolledBack?: boolean
}

/** 执行写入；返回结果 data 含 diff 与备份相对路径（回滚按钮依据） */
async function doWrite(resolvedInput: Record<string, unknown>, ctx: ToolContext): Promise<ToolResult> {
  const abs = typeof resolvedInput['path'] === 'string' ? resolvedInput['path'] : ''
  const content = typeof resolvedInput['content'] === 'string' ? resolvedInput['content'] : ''
  const root = ctx.workspaceRoot
  if (!abs) return { ok: false, summary: '缺少 path 参数', error: '缺少 path 参数' }
  if (resolvedInput['content'] === undefined || resolvedInput['content'] === null) {
    return { ok: false, summary: '缺少 content 参数', error: '缺少 content 参数' }
  }

  const bytes = Buffer.byteLength(content, 'utf8')
  if (bytes > WRITE_FILE_MAX_BYTES) {
    return {
      ok: false,
      summary: `内容 ${bytes} 字节，超过单文件上限 2MB（${WRITE_FILE_MAX_BYTES} 字节），拒绝写入`,
      error: '超过 2MB 上限'
    }
  }

  const rel = displayRel(abs, root)
  const existed = existsSync(abs) && statSync(abs).isFile()

  let backupRel: string | undefined
  let oldText: string | undefined
  if (existed) {
    const oldBuf = readFileSync(abs)
    oldText = oldBuf.toString('utf8')
    const stamp = `${new Date().toISOString().replace(/[-:T]/g, '').slice(0, 14)}-${randomBytes(2).toString('hex')}`
    backupRel = `.agent-backups/${stamp}/${rel.replaceAll('\\', '/')}`
    const backupAbs = join(root, backupRel)
    mkdirSync(dirname(backupAbs), { recursive: true })
    copyFileSync(abs, backupAbs)
  }

  mkdirSync(dirname(abs), { recursive: true })
  writeFileSync(abs, content, 'utf8')

  const data: WriteData = {
    path: rel,
    bytes,
    created: !existed,
    ...(backupRel ? { backupPath: backupRel } : {})
  }
  return {
    ok: true,
    summary: existed ? `已覆写 ${rel}（原内容已备份，可在卡片回滚）` : `已创建 ${rel}（${bytes} 字节）`,
    // 回喂只带 summary + 相对路径等小字段；diff 仅进卡片（cardData），保护模型上下文
    data,
    cardData: { ...data, diff: existed ? buildLineDiff(oldText ?? '', content, rel) : buildCreateDiff(content, rel) }
  } as ToolResult
}

export const writeFileTool: import('../tool-registry').AgentTool = {
  name: 'write_file',
  description:
    '创建或覆写工作区内的 UTF-8 文本文件（上限 2MB），自动创建父目录。覆写已存在文件前会自动备份原内容到 .agent-backups/ 并需用户确认；新文件同样需要用户确认。path 相对工作区。',
  permission: 'confirm',
  parameters: {
    type: 'object',
    properties: {
      path: { type: 'string', description: '相对工作区的目标文件路径' },
      content: { type: 'string', description: '要写入的完整 UTF-8 文本内容（整文件覆写，不是追加）' }
    },
    required: ['path', 'content']
  },
  /** 确认前预览（无副作用）：生成 diff 供用户审阅 */
  async preview(resolvedInput, ctx) {
    const abs = typeof resolvedInput['path'] === 'string' ? resolvedInput['path'] : ''
    const content = typeof resolvedInput['content'] === 'string' ? resolvedInput['content'] : ''
    if (!abs) return { ok: false, summary: '缺少 path 参数', error: '缺少 path 参数' }
    const bytes = Buffer.byteLength(content, 'utf8')
    if (bytes > WRITE_FILE_MAX_BYTES) {
      return { ok: false, summary: `内容 ${bytes} 字节，超过单文件上限 2MB，拒绝写入`, error: '超过 2MB 上限' }
    }
    const rel = displayRel(abs, ctx.workspaceRoot)
    const existed = existsSync(abs) && statSync(abs).isFile()
    const diff = existed
      ? buildLineDiff(readFileSync(abs, 'utf8'), content, rel)
      : buildCreateDiff(content, rel)
    return {
      ok: true,
      summary: existed ? `将覆写 ${rel}（请审阅差异）` : `将新建 ${rel}（${bytes} 字节，请审阅内容）`,
      data: { path: rel, bytes, created: !existed, diff }
    }
  },
  async execute(input, ctx) {
    // registry 已把 path 围栏解析为绝对路径后传入
    return doWrite(input, ctx)
  }
}
