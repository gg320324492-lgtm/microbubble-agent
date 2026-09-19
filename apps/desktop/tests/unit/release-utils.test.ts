// M6-2 清账①⑤ — 发布脚本纯函数：版本同步校验 / latest.yml 生成与校验 / out 分批清理
import { existsSync, readFileSync } from 'node:fs'
import { createRequire } from 'node:module'
import { resolve } from 'node:path'
import { describe, expect, it } from 'vitest'
import {
  artifactNames,
  buildLatestYml,
  checkVersionSync,
  chunk,
  classifyNativeAbi,
  electronTarget,
  extractAppVersion,
  planOutCleanup,
  verifyLatestYml
} from '../../scripts/lib/release-utils.mjs'

const require = createRequire(import.meta.url)
const APP_ROOT = resolve(__dirname, '../..')
const REPO_NODE_MODULES = resolve(APP_ROOT, '../../node_modules')

describe('版本两处同步校验（R-1 类翻车防线）', () => {
  it('真实仓库文件必须同步：package.json.version === constants.ts APP_VERSION', () => {
    const pkgVersion = JSON.parse(readFileSync(resolve(APP_ROOT, 'package.json'), 'utf8')).version as string
    const constantsSource = readFileSync(resolve(APP_ROOT, 'src/shared/constants.ts'), 'utf8')

    const res = checkVersionSync({ pkgVersion, constantsSource })
    expect(res.ok, res.ok ? '' : res.reason).toBe(true)
    expect(res.ok && res.version).toBe(pkgVersion)
    // 版本形如 0.1.x-alpha（发布目标 v0.1.5-alpha）
    expect(pkgVersion).toMatch(/^\d+\.\d+\.\d+(-[0-9A-Za-z.-]+)?$/)
  })

  it('不一致时给出可定位的原因；提取失败也能识别', () => {
    const mismatch = checkVersionSync({ pkgVersion: '0.1.5-alpha', constantsSource: "APP_VERSION = '0.1.4-alpha'" })
    expect(mismatch.ok).toBe(false)
    expect(mismatch.ok === false && mismatch.reason).toContain('0.1.5-alpha')
    expect(mismatch.ok === false && mismatch.reason).toContain('0.1.4-alpha')

    const missing = checkVersionSync({ pkgVersion: '0.1.5-alpha', constantsSource: 'export const X = 1' })
    expect(missing.ok).toBe(false)

    expect(extractAppVersion('APP_VERSION = "1.2.3"')).toBe('1.2.3')
    expect(extractAppVersion("export const APP_VERSION = '1.2.3-beta.1'")).toBe('1.2.3-beta.1')
    expect(extractAppVersion('')).toBeNull()
  })
})

describe('latest.yml 生成与一致性校验（清账①）', () => {
  const expected = {
    version: '0.1.5-alpha',
    fileName: 'MicroBubbleWorkbench-0.1.5-alpha-setup.exe',
    sha512: 'AbCdEf0123456789+/==',
    size: 92113488
  }

  it('生成的字段与 electron-updater 解析器约定一致，且自校验通过', () => {
    const yml = buildLatestYml({ ...expected, releaseDate: '2026-09-19T00:00:00.000Z' })
    expect(yml).toContain('version: 0.1.5-alpha')
    expect(yml).toContain(`path: ${expected.fileName}`)
    expect(yml).toContain(`  - url: ${expected.fileName}`)
    expect(yml).toContain(`    sha512: ${expected.sha512}`)
    expect(yml).toContain(`    size: ${expected.size}`)
    expect(yml).toContain("releaseDate: '2026-09-19T00:00:00.000Z'")

    const check = verifyLatestYml(yml, expected)
    expect(check.ok, check.issues.join('; ')).toBe(true)
  })

  it('version/sha512/size/url 任一不符都被判失败（消灭手工补）', () => {
    const yml = buildLatestYml({ ...expected, releaseDate: '2026-09-19T00:00:00.000Z' })

    expect(verifyLatestYml(yml, { ...expected, version: '9.9.9' }).ok).toBe(false)
    expect(verifyLatestYml(yml, { ...expected, size: 1 }).ok).toBe(false)
    expect(verifyLatestYml(yml, { ...expected, sha512: 'other' }).ok).toBe(false)
    expect(verifyLatestYml(yml, { ...expected, fileName: 'other.exe' }).ok).toBe(false)
    // 缺字段
    expect(verifyLatestYml('version: 0.1.5-alpha\n', expected).ok).toBe(false)
  })

  it('三件套命名规则与打包产物一致', () => {
    const names = artifactNames('0.1.5-alpha')
    expect(names.exe).toBe('MicroBubbleWorkbench-0.1.5-alpha-setup.exe')
    expect(names.blockmap).toBe('MicroBubbleWorkbench-0.1.5-alpha-setup.exe.blockmap')
    expect(names.latestYml).toBe('latest.yml')
  })
})

describe('原生模块 ABI 判定（M6-2 修复：CI 装到 Node ABI 导致应用启动即崩）', () => {
  it('Node 能加载 = Node ABI（需修正）；报 128 = 已是 Electron ABI；其余为未知', () => {
    expect(classifyNativeAbi({ ok: true })).toBe('node')
    expect(
      classifyNativeAbi({
        ok: false,
        error:
          "The module '…\\better_sqlite3.node' was compiled against a different Node.js version using\nNODE_MODULE_VERSION 128. This version of Node.js requires\nNODE_MODULE_VERSION 127."
      })
    ).toBe('electron')
    expect(classifyNativeAbi({ ok: false, error: 'Cannot find module' })).toBe('unknown')
    expect(classifyNativeAbi({ ok: false })).toBe('unknown')
  })

  it('electronTarget 取 electron 包版本（prebuild-install 的 --target）', () => {
    expect(electronTarget('32.3.3')).toBe('32.3.3')
    expect(electronTarget(' 32.3.3 ')).toBe('32.3.3')
  })

  it('真实环境自检：本地打包所依赖的 better-sqlite3 必须是 Electron ABI', () => {
    // 本地 node_modules 若退回 Node ABI，打包出的应用会启动即崩（v0.1.5-alpha 首航实测）
    const binary = resolve(REPO_NODE_MODULES, '.pnpm/better-sqlite3@12.11.1/node_modules/better-sqlite3/build/Release/better_sqlite3.node')
    if (!existsSync(binary)) return // 布局变化时跳过（CI 由 release.mjs native 步骤兜底）
    let probe: { ok: boolean; error?: string }
    try {
      // eslint-disable-next-line @typescript-eslint/no-var-requires
      require(binary)
      probe = { ok: true }
    } catch (e) {
      probe = { ok: false, error: e instanceof Error ? e.message : String(e) }
    }
    expect(classifyNativeAbi(probe)).toBe('electron')
  })
})

describe('out/ 分批清理（清账⑤）', () => {
  it('按批大小切分，覆盖全部条目且不重复', () => {
    const entries = Array.from({ length: 95 }, (_, i) => `dir-${i}`)
    const batches = planOutCleanup(entries, 40)
    expect(batches.length).toBe(3)
    expect(batches[0].length).toBe(40)
    expect(batches[1].length).toBe(40)
    expect(batches[2].length).toBe(15)
    expect(batches.flat().sort()).toEqual([...entries].sort())
  })

  it('少于一批 / 空输入 边界', () => {
    expect(planOutCleanup(['a', 'b'], 40)).toEqual([['a', 'b']])
    expect(planOutCleanup([], 40)).toEqual([])
    expect(chunk([1, 2, 3], 1)).toEqual([[1], [2], [3]])
    // 非法批大小回退为 1，避免死循环
    expect(chunk([1, 2], 0)).toEqual([[1], [2]])
  })
})
