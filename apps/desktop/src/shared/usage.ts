// 用量展示格式化（V1）— 主进程与渲染进程共用的纯函数
/** 紧凑展示：999 → "999"，1234 → "1.2k"，12345 → "12k" */
export function formatTokens(n: unknown): string {
  const v = typeof n === 'number' && Number.isFinite(n) && n > 0 ? Math.floor(n) : 0
  if (v < 1000) return String(v)
  return `${(v / 1000).toFixed(v < 10000 ? 1 : 0)}k`
}

/**
 * 会话用量标签（对话面板 chip 的显隐与文案，纯函数便于离线单测）。
 * 无会话或总量为 0 → null（不渲染 chip）；否则给出紧凑的输入/输出文本。
 */
export function sessionUsageLabel(
  session: { tokensIn?: unknown; tokensOut?: unknown } | null | undefined
): { input: string; output: string } | null {
  if (!session) return null
  const inRaw = typeof session.tokensIn === 'number' && Number.isFinite(session.tokensIn) ? session.tokensIn : 0
  const outRaw = typeof session.tokensOut === 'number' && Number.isFinite(session.tokensOut) ? session.tokensOut : 0
  if (inRaw <= 0 && outRaw <= 0) return null
  return { input: formatTokens(inRaw), output: formatTokens(outRaw) }
}
