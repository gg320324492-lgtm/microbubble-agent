// 用量展示格式化（V1）— 主进程与渲染进程共用的纯函数
/** 紧凑展示：999 → "999"，1234 → "1.2k"，12345 → "12k" */
export function formatTokens(n: unknown): string {
  const v = typeof n === 'number' && Number.isFinite(n) && n > 0 ? Math.floor(n) : 0
  if (v < 1000) return String(v)
  return `${(v / 1000).toFixed(v < 10000 ? 1 : 0)}k`
}
