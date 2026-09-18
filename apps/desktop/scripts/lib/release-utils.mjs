// 发布脚本纯函数层（M6-2 清账①⑤）— 本地与 CI 共用同一套逻辑，零副作用、可离线单测。
//
// 设计原则：所有判断/生成逻辑放这里，scripts/release.mjs 只做 CLI 编排（读文件、调外部命令）。
// latest.yml 由本模块生成而非依赖 electron-builder 的产物：electron-builder 在 generic provider 下
// 会按版本 prerelease 段推导频道名产出 alpha.yml（M6-1 实测），与 electron-updater 默认的
// latest 频道不一致；自己生成可保证文件名与内容始终匹配默认频道。

/** 更新源 feed 覆盖环境变量（与 src/shared/constants.ts 的 ENV_UPDATE_FEED 同名） */
export const ENV_UPDATE_FEED = 'MNB_UPDATE_FEED'

/** 沙箱批量删除守卫单次文件阈值（本地打包时 rmSync('out') 会触发，故需分批） */
export const OUT_CLEANUP_BATCH_SIZE = 40

/**
 * 从 constants.ts 源码提取 APP_VERSION（正则提取，避免为脚本引入 TS 编译链）。
 * @param {string} source
 * @returns {string | null}
 */
export function extractAppVersion(source) {
  const m = /APP_VERSION\s*=\s*['"]([^'"]+)['"]/.exec(String(source ?? ''))
  return m ? m[1] : null
}

/**
 * 版本两处同步校验（R-1 类翻车防线）：package.json ↔ src/shared/constants.ts
 * @param {{ pkgVersion: string, constantsSource: string }} input
 * @returns {{ ok: true, version: string } | { ok: false, reason: string }}
 */
export function checkVersionSync(input) {
  const pkgVersion = String(input?.pkgVersion ?? '')
  const constantsVersion = extractAppVersion(input?.constantsSource)
  if (!constantsVersion) return { ok: false, reason: 'constants.ts 中未找到 APP_VERSION' }
  if (!pkgVersion) return { ok: false, reason: 'package.json 中未找到 version' }
  if (pkgVersion !== constantsVersion) {
    return {
      ok: false,
      reason: `版本两处不一致：package.json=${pkgVersion} / constants.ts=${constantsVersion}`
    }
  }
  return { ok: true, version: pkgVersion }
}

/**
 * 生成 latest.yml（electron-updater 默认频道 latest）。
 * 字段与 electron-updater 解析器一致：version / files[].url|sha512|size / path / sha512 / releaseDate
 * @param {{ version: string, fileName: string, sha512: string, size: number, releaseDate?: string }} input
 */
export function buildLatestYml(input) {
  const releaseDate = input.releaseDate ?? new Date().toISOString()
  return [
    `version: ${input.version}`,
    'files:',
    `  - url: ${input.fileName}`,
    `    sha512: ${input.sha512}`,
    `    size: ${input.size}`,
    `path: ${input.fileName}`,
    `sha512: ${input.sha512}`,
    `releaseDate: '${releaseDate}'`,
    ''
  ].join('\n')
}

/**
 * 校验 latest.yml 与实际产物逐字段一致（消灭手工补）。
 * @param {string} ymlText
 * @param {{ version: string, fileName: string, sha512: string, size: number }} expected
 * @returns {{ ok: boolean, issues: string[] }}
 */
export function verifyLatestYml(ymlText, expected) {
  const text = String(ymlText ?? '')
  const issues = []
  const one = (re) => {
    const m = re.exec(text)
    return m ? m[1].trim() : null
  }

  const version = one(/^version:\s*(.+)$/m)
  if (version !== expected.version) issues.push(`version 不一致：yml=${version} 期望=${expected.version}`)

  const path = one(/^path:\s*(.+)$/m)
  if (path !== expected.fileName) issues.push(`path 不一致：yml=${path} 期望=${expected.fileName}`)

  const urls = [...text.matchAll(/^\s+- url:\s*(.+)$/gm)].map((m) => m[1].trim())
  if (urls.length !== 1) issues.push(`files[].url 条目数异常：${urls.length}`)
  else if (urls[0] !== expected.fileName) issues.push(`files[].url 不一致：yml=${urls[0]} 期望=${expected.fileName}`)

  const sha512s = [...text.matchAll(/sha512:\s*(\S+)/g)].map((m) => m[1].trim())
  if (sha512s.length === 0) issues.push('缺少 sha512 字段')
  for (const s of sha512s) {
    if (s !== expected.sha512) issues.push(`sha512 不一致：yml=${s} 期望=${expected.sha512}`)
  }

  const sizes = [...text.matchAll(/size:\s*(\d+)/g)].map((m) => Number(m[1]))
  if (sizes.length === 0) issues.push('缺少 size 字段')
  for (const s of sizes) {
    if (s !== expected.size) issues.push(`size 不一致：yml=${s} 期望=${expected.size}`)
  }

  return { ok: issues.length === 0, issues }
}

/** 按批次切分（纯函数） */
export function chunk(items, size) {
  const list = [...(items ?? [])]
  const n = Math.max(1, Number(size) || 1)
  const out = []
  for (let i = 0; i < list.length; i += n) out.push(list.slice(i, i + n))
  return out
}

/**
 * out/ 分批清理计划（清账⑤）。
 * 本地沙箱对单次 rmSync 有 50 文件阈值，一次性删 out/ 会触发
 * SAFE_DELETE_BULK_CONFIRM_REQUIRED；按顶层条目分批删除可绕开。
 * CI 无此限制，但共用同一脚本（幂等，多删几次无副作用）。
 * @param {string[]} topLevelEntries out/ 的顶层条目名
 * @returns {string[][]} 分批结果
 */
export function planOutCleanup(topLevelEntries, batchSize = OUT_CLEANUP_BATCH_SIZE) {
  return chunk(topLevelEntries, batchSize)
}

/** 期望的 NSIS 三件套文件名 */
export function artifactNames(version) {
  const exe = `MicroBubbleWorkbench-${version}-setup.exe`
  return { exe, blockmap: `${exe}.blockmap`, latestYml: 'latest.yml' }
}

/**
 * 判定原生模块（.node）的 ABI 归属（M6-2 修复）。
 *
 * 判定技巧：Node 能 require 成功 ⇒ 该二进制是 **Node ABI**，打包进 Electron 必崩
 * （实测 Electron 32 需 NODE_MODULE_VERSION 128，而 Node 22 是 127）；
 * 抛错且提到 128 ⇒ 已是 Electron ABI，正确；其余错误视为未知（不擅自改写）。
 *
 * @param {{ ok: boolean, error?: string }} probe
 * @returns {'node' | 'electron' | 'unknown'}
 */
export function classifyNativeAbi(probe) {
  if (probe?.ok) return 'node'
  const err = String(probe?.error ?? '')
  return /NODE_MODULE_VERSION\s+128/.test(err) ? 'electron' : 'unknown'
}

/** 从 electron 包版本得到 prebuild-install 需要的 target */
export function electronTarget(version) {
  return String(version ?? '').trim()
}
