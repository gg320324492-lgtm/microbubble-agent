// R-8 更新 feed 切换 — OSS 默认 / env 覆盖 / GitHub 回退 的解析优先级（全部离线）
import { describe, expect, it } from 'vitest'
import {
  ENV_UPDATE_FEED,
  ENV_UPDATE_FEED_PROVIDER,
  UPDATE_FEED_BASE,
  UPDATE_FEED_HOST,
  UPDATE_FEED_PREFIX
} from '@shared/constants'
import {
  normalizeFeedUrl,
  resolveAllowPrerelease,
  resolveEffectiveUpdateFeed,
  resolveUpdateFeedConfig
} from '@main/services/update/feed-config'

const DEV = { isPackaged: false }
const PACKED = { isPackaged: true }

describe('feed 常量 — OSS 直链 + 域名一行切换点', () => {
  it('UPDATE_FEED_BASE = OSS 主机 + releases/ 前缀，末位斜杠必需', () => {
    expect(UPDATE_FEED_HOST).toBe('https://mnb-workbench-releases.oss-cn-beijing.aliyuncs.com')
    expect(UPDATE_FEED_PREFIX).toBe('releases/')
    expect(UPDATE_FEED_BASE).toBe('https://mnb-workbench-releases.oss-cn-beijing.aliyuncs.com/releases/')
    expect(UPDATE_FEED_BASE.endsWith('/')).toBe(true)
  })
})

describe('生效 feed 解析 — env 覆盖 > 默认 OSS > GitHub 回退', () => {
  it('无覆盖时默认走 OSS generic（打包版常规路径）', () => {
    expect(resolveEffectiveUpdateFeed({ env: {}, ...PACKED })).toEqual({ url: UPDATE_FEED_BASE, source: 'oss' })
    // 未打包环境同样解析出 OSS（是否真跑检查由 isUpdateChannelAvailable 决定）
    expect(resolveEffectiveUpdateFeed({ env: {}, ...DEV }).source).toBe('oss')
  })

  it('MNB_UPDATE_FEED 覆盖优先级最高，并自动补末位斜杠', () => {
    const r = resolveEffectiveUpdateFeed({ env: { [ENV_UPDATE_FEED]: 'http://127.0.0.1:8788' }, ...DEV })
    expect(r).toEqual({ url: 'http://127.0.0.1:8788/', source: 'env' })
    // 覆盖 > GitHub 开关（两者同时给，覆盖赢）
    const both = resolveEffectiveUpdateFeed({
      env: { [ENV_UPDATE_FEED]: 'https://example.com/feed/', [ENV_UPDATE_FEED_PROVIDER]: 'github' },
      ...PACKED
    })
    expect(both).toEqual({ url: 'https://example.com/feed/', source: 'env' })
  })

  it('MNB_UPDATE_FEED_PROVIDER=github 回退到 GitHub provider（url 为 null）', () => {
    const r = resolveEffectiveUpdateFeed({ env: { [ENV_UPDATE_FEED_PROVIDER]: 'github' }, ...PACKED })
    expect(r).toEqual({ url: null, source: 'github' })
    // 大小写与空白容错
    expect(resolveEffectiveUpdateFeed({ env: { [ENV_UPDATE_FEED_PROVIDER]: ' GitHub ' }, ...PACKED }).source).toBe('github')
    // 其它值不触发回退
    expect(resolveEffectiveUpdateFeed({ env: { [ENV_UPDATE_FEED_PROVIDER]: 'oss' }, ...PACKED }).source).toBe('oss')
  })

  it('M6-1 契约不变：resolveUpdateFeedConfig 仍只回答"有无显式覆盖"', () => {
    expect(resolveUpdateFeedConfig({ env: {}, ...DEV })).toEqual({ feedUrl: null, forceDev: false })
    expect(resolveUpdateFeedConfig({ env: {}, ...PACKED })).toEqual({ feedUrl: null, forceDev: false })
    const overridden = resolveUpdateFeedConfig({ env: { [ENV_UPDATE_FEED]: 'http://127.0.0.1:8788' }, ...DEV })
    expect(overridden).toEqual({ feedUrl: 'http://127.0.0.1:8788', forceDev: true })
  })

  it('normalizeFeedUrl：去空白、补斜杠、空值归空', () => {
    expect(normalizeFeedUrl('https://a.com/f')).toBe('https://a.com/f/')
    expect(normalizeFeedUrl('  https://a.com/f/  ')).toBe('https://a.com/f/')
    expect(normalizeFeedUrl('')).toBe('')
    expect(normalizeFeedUrl('   ')).toBe('')
  })
})

describe('stable 频道语义 — 预发布开关按版本号判定', () => {
  it('正式版（无后缀）不放开预发布', () => {
    expect(resolveAllowPrerelease('1.0.1')).toBe(false)
    expect(resolveAllowPrerelease('1.0.0')).toBe(false)
    expect(resolveAllowPrerelease('2.0.0')).toBe(false)
  })

  it('带预发布后缀才放开（保留回退能力）', () => {
    expect(resolveAllowPrerelease('1.0.1-beta.1')).toBe(true)
    expect(resolveAllowPrerelease('0.1.6-alpha')).toBe(true) // v0.1.x 时期行为不变
    expect(resolveAllowPrerelease('1.0.0-rc.2')).toBe(true)
  })

  it('异常输入不放开（保守）', () => {
    expect(resolveAllowPrerelease('')).toBe(false)
    expect(resolveAllowPrerelease(undefined as never)).toBe(false)
  })
})
