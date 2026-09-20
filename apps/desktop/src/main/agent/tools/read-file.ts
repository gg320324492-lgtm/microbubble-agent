// read_file 工具 — UTF-8 文本读取（工单 C-1 §2 + M8-1 §1 输出预算）
//
// M8-1 变更：
//   · 新增 offset / length 参数（按行，1 基），与截断续读提示闭环
//   · 256KB 硬截断 → 24KB **字节预算**，逐行装入且不切断多字节字符（原实现 subarray 会切出乱码）
//   · 截断后附结构化续读提示，模型可直接照做继续读
import { readFileSync, statSync } from 'node:fs'
import type { AgentTool, ToolResult } from '../tool-registry'
import { displayRel } from './walk'
import {
  READ_TEXT_MAX_BYTES,
  buildContinuationNotice,
  limitPrefixLines,
  utf8ByteLength
} from './output-limit'

/** 兜底硬上限：单文件超过此大小直接拒绝整读（避免把 1GB 文件读进内存），引导用 offset/length 分段 */
const HARD_READ_LIMIT = 8 * 1024 * 1024

function parsePositiveInt(v: unknown): number | undefined {
  const n = typeof v === 'string' ? Number(v) : typeof v === 'number' ? v : NaN
  return Number.isFinite(n) && n > 0 ? Math.floor(n) : undefined
}

export const readFileTool: AgentTool = {
  name: 'read_file',
  description:
    `读取工作区内一个 UTF-8 文本文件。默认返回前 ${READ_TEXT_MAX_BYTES / 1024}KB（按字节预算逐行截断，不切断多字节字符）；` +
    '内容过长时结果尾部会给出续读提示，按提示带 offset/length 参数（按行，1 基）继续读取。二进制文件拒绝读取。',
  permission: 'auto',
  parameters: {
    type: 'object',
    properties: {
      path: { type: 'string', description: '相对工作区的文件路径，如 docs/notes.md' },
      offset: { type: 'number', description: '起始行号（1 基）。续读时用上一次提示里的 nextOffset' },
      length: { type: 'number', description: '本次最多读取的行数；省略则读到预算用尽' }
    },
    required: ['path']
  },
  async execute(input, ctx): Promise<ToolResult> {
    const file = typeof input['path'] === 'string' ? input['path'] : ''
    if (file === '') return { ok: false, summary: '缺少 path 参数', error: '缺少 path 参数' }

    const offset = parsePositiveInt(input['offset']) ?? 1
    const length = parsePositiveInt(input['length'])

    let st
    try {
      st = statSync(file)
    } catch {
      const rel = displayRel(file, ctx.workspaceRoot)
      return { ok: false, summary: `文件不存在: ${rel}`, error: '文件不存在' }
    }
    if (st.isDirectory()) {
      const rel = displayRel(file, ctx.workspaceRoot)
      return { ok: false, summary: `目标是目录而非文件: ${rel}`, error: '目标是目录' }
    }
    if (st.size > HARD_READ_LIMIT) {
      const rel = displayRel(file, ctx.workspaceRoot)
      return {
        ok: false,
        summary: `文件过大（${st.size} 字节，超过 ${HARD_READ_LIMIT} 字节硬上限）: ${rel}。请用 offset/length 分段读取`,
        error: '文件过大，请分段读取'
      }
    }

    const buf = readFileSync(file)
    if (buf.includes(0)) {
      const rel = displayRel(file, ctx.workspaceRoot)
      return { ok: false, summary: `二进制文件拒绝读取: ${rel}`, error: '二进制文件' }
    }

    const raw = buf.toString('utf8')
    const allLines = raw.split(/\r?\n/)
    const totalBytes = buf.length
    const rel = displayRel(file, ctx.workspaceRoot)

    // 按 offset/length 先切出请求的窗口（整行），再对该窗口做字节预算
    const startLine = Math.min(offset, allLines.length + 1)
    const windowLines =
      length === undefined ? allLines.slice(startLine - 1) : allLines.slice(startLine - 1, startLine - 1 + length)
    const windowText = windowLines.join('\n')
    const windowBytes = utf8ByteLength(windowText)

    const limited = limitPrefixLines(windowText, {
      maxBytes: READ_TEXT_MAX_BYTES,
      notice: ({ returnedBodyLines }) => {
        const next = startLine + returnedBodyLines
        return buildContinuationNotice({
          originalBytes: windowBytes,
          maxBytes: READ_TEXT_MAX_BYTES,
          strategy: 'prefix_lines',
          returnedBodyLines,
          nextOffset: next,
          resumeCall: `read_file(path="${rel}", offset=${next}, length=2000)`
        })
      },
      oversizedNotice: ({ originalBytes }) =>
        buildContinuationNotice({
          originalBytes,
          maxBytes: READ_TEXT_MAX_BYTES,
          strategy: 'prefix_lines',
          returnedBodyLines: 0,
          oversizedLine: true
        })
    })

    // 提示里的 returnedBytes 需回填真实值（notice 在截断时先于最终文本生成）
    const finalText = limited.text
    const bytes = utf8ByteLength(finalText)
    const rangeNote =
      startLine > 1 || length !== undefined
        ? `（第 ${startLine}${length === undefined ? '' : `–${startLine + windowLines.length - 1}`} 行 / 共 ${allLines.length} 行）`
        : ''

    return {
      ok: true,
      summary: limited.truncated
        ? `已读取 ${rel}${rangeNote}：原始 ${totalBytes} 字节，按 ${READ_TEXT_MAX_BYTES} 字节预算截断（返回 ${bytes} 字节）`
        : `已读取 ${rel}${rangeNote}（${totalBytes} 字节）`,
      data: {
        path: rel,
        size: totalBytes,
        truncated: limited.truncated,
        offset: startLine,
        returnedLines: limited.returnedBodyLines,
        totalLines: allLines.length,
        content: finalText,
        ...(limited.truncation ? { truncation: limited.truncation } : {})
      }
    }
  }
}
