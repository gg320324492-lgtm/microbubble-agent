// 语义化版本比较（M6-1）— 纯函数，零依赖、零 Electron，可离线单测。
//
// 之所以自己实现而不直接用 semver 包：需要严格可控的 prerelease 语义，
// 且适配层之外的代码不允许依赖第三方运行时包（semver 仅作为 electron-updater
// 的传递依赖存在，不直接 import）。
//
// 规则（SemVer 2.0.0 §11）：
//   1.0.0-alpha < 1.0.0-alpha.1 < 1.0.0-alpha.beta < 1.0.0-beta < 1.0.0-beta.2
//   < 1.0.0-beta.11 < 1.0.0-rc.1 < 1.0.0
//   即：带 prerelease 的版本 < 同号正式版；数值型标识符按数值比较（beta.11 > beta.2）。

export interface ParsedVersion {
  major: number
  minor: number
  patch: number
  /** 空数组表示正式版（无 prerelease） */
  prerelease: string[]
}

const CORE_RE = /^(\d+)\.(\d+)\.(\d+)(?:-([0-9A-Za-z.-]+))?(?:\+[0-9A-Za-z.-]+)?$/

/** 解析版本串；非法返回 null（调用方按"无法比较"处理） */
export function parseVersion(input: string): ParsedVersion | null {
  if (typeof input !== 'string') return null
  const m = CORE_RE.exec(input.trim())
  if (!m) return null
  const pre = m[4] ? m[4].split('.').filter((s) => s.length > 0) : []
  return { major: Number(m[1]), minor: Number(m[2]), patch: Number(m[3]), prerelease: pre }
}

/** 比较单个 prerelease 标识符：数值型按数值，其余按 ASCII；数值 < 非数值 */
function comparePrereleaseId(a: string, b: string): number {
  const na = /^\d+$/.test(a)
  const nb = /^\d+$/.test(b)
  if (na && nb) return Math.sign(Number(a) - Number(b))
  if (na) return -1
  if (nb) return 1
  return a < b ? -1 : a > b ? 1 : 0
}

/**
 * 比较两个版本串。
 * @returns 负数 a<b；0 相等；正数 a>b。任一不可解析时返回 0（视为相同，绝不误报有更新）
 */
export function compareVersions(a: string, b: string): number {
  const pa = parseVersion(a)
  const pb = parseVersion(b)
  if (!pa || !pb) return 0

  for (const key of ['major', 'minor', 'patch'] as const) {
    if (pa[key] !== pb[key]) return Math.sign(pa[key] - pb[key])
  }

  const preA = pa.prerelease
  const preB = pb.prerelease
  // 正式版 > 任何同号 prerelease
  if (preA.length === 0 && preB.length === 0) return 0
  if (preA.length === 0) return 1
  if (preB.length === 0) return -1

  const len = Math.max(preA.length, preB.length)
  for (let i = 0; i < len; i++) {
    const x = preA[i]
    const y = preB[i]
    // 前缀相同则字段少者更小：alpha < alpha.1
    if (x === undefined) return -1
    if (y === undefined) return 1
    const c = comparePrereleaseId(x, y)
    if (c !== 0) return c
  }
  return 0
}

/** candidate 是否比 current 更新（严格大于） */
export function isNewer(candidate: string, current: string): boolean {
  return compareVersions(candidate, current) > 0
}
