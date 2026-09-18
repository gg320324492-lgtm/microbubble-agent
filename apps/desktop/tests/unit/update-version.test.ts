// M6-1 版本比较 — semver + prerelease 语义（纯函数，离线）
import { describe, expect, it } from 'vitest'
import { compareVersions, isNewer, parseVersion } from '@main/services/update/version'

describe('版本比较 — 语义化与 prerelease', () => {
  it('主线数字比较：0.1.5-alpha > 0.1.4-alpha，0.2.0 > 0.1.9', () => {
    expect(compareVersions('0.1.5-alpha', '0.1.4-alpha')).toBeGreaterThan(0)
    expect(compareVersions('0.2.0', '0.1.9')).toBeGreaterThan(0)
    expect(compareVersions('1.0.0', '1.0.0')).toBe(0)
    expect(compareVersions('0.1.4', '0.1.5')).toBeLessThan(0)
  })

  it('prerelease 语义：0.1.5-alpha < 0.1.5，且 0.1.5 > 0.1.5-alpha', () => {
    expect(compareVersions('0.1.5-alpha', '0.1.5')).toBeLessThan(0)
    expect(compareVersions('0.1.5', '0.1.5-alpha')).toBeGreaterThan(0)
    // 全部版本都是 prerelease 时，同号 prerelease 之间仍要能分出大小
    expect(compareVersions('0.1.5-alpha', '0.1.4-alpha')).toBeGreaterThan(0)
  })

  it('prerelease 标识符比较：alpha < alpha.1 < beta < beta.2 < beta.11 < rc.1', () => {
    const order = ['0.1.0-alpha', '0.1.0-alpha.1', '0.1.0-beta', '0.1.0-beta.2', '0.1.0-beta.11', '0.1.0-rc.1', '0.1.0']
    for (let i = 0; i < order.length - 1; i++) {
      expect(compareVersions(order[i], order[i + 1]), `${order[i]} < ${order[i + 1]}`).toBeLessThan(0)
      expect(compareVersions(order[i + 1], order[i]), `${order[i + 1]} > ${order[i]}`).toBeGreaterThan(0)
    }
  })

  it('isNewer 严格大于：同版本 / 更旧版本均返回 false', () => {
    expect(isNewer('0.1.5-alpha', '0.1.4-alpha')).toBe(true)
    expect(isNewer('0.1.4-alpha', '0.1.4-alpha')).toBe(false)
    expect(isNewer('0.1.3-alpha', '0.1.4-alpha')).toBe(false)
  })

  it('无法解析的版本串返回 0 / false（绝不误报有更新）', () => {
    expect(compareVersions('v0.1.5', '0.1.5')).toBe(0)
    expect(compareVersions('', '0.1.5')).toBe(0)
    expect(compareVersions('not-a-version', '0.1.5')).toBe(0)
    expect(isNewer('abc', '0.1.4-alpha')).toBe(false)
    expect(parseVersion('0.1.5-alpha')).toEqual({ major: 0, minor: 1, patch: 5, prerelease: ['alpha'] })
    expect(parseVersion('bad')).toBeNull()
  })
})
