// M6-2 清账①⑤ — 发布脚本纯函数：版本同步校验 / latest.yml 生成与校验 / out 分批清理
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { describe, expect, it } from 'vitest'
import {
  artifactNames,
  buildLatestYml,
  checkVersionSync,
  chunk,
  extractAppVersion,
  planOutCleanup,
  verifyLatestYml
} from '../../scripts/lib/release-utils.mjs'

const APP_ROOT = resolve(__dirname, '../..')

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

    expect(verifyLatestYml(yml, { ...expected, version: '0.1.6-alpha' }).ok).toBe(false)
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
