// M6-1 整改 — 装配期 feed 配置解析与"装配→适配层"接线断言（打回缺陷锁定用例）
//
// 缺陷复盘：装配漏传 forceDev → 适配层 forceDevUpdateConfig 恒 false →
// 未打包环境 electron-updater isUpdaterActive() 为 false → checkForUpdates() 不发请求返回 null
// → UI 误报「已是最新版本」。本文件把这条链的每一环都钉死在离线断言里。
import { describe, expect, it } from 'vitest'
import {
  isUpdateChannelAvailable,
  resolveForceDevUpdateConfig,
  resolveUpdateFeedConfig
} from '@main/services/update/feed-config'
import { ENV_UPDATE_FEED } from '@shared/constants'

const DEV = { isPackaged: false }
const PACKED = { isPackaged: true }

describe('装配期 feed 配置 — feedUrl 存在时必须放行未打包环境', () => {
  it('dev + MNB_UPDATE_FEED → feedUrl 透传且 forceDev=true', () => {
    const cfg = resolveUpdateFeedConfig({ env: { [ENV_UPDATE_FEED]: 'http://127.0.0.1:8788' }, ...DEV })
    expect(cfg.feedUrl).toBe('http://127.0.0.1:8788')
    expect(cfg.forceDev).toBe(true)
  })

  it('dev 无 feed 覆盖 → feedUrl=null 且 forceDev=false（不放行）', () => {
    expect(resolveUpdateFeedConfig({ env: {}, ...DEV })).toEqual({ feedUrl: null, forceDev: false })
  })

  it('空白/非字符串覆盖视为未设置', () => {
    expect(resolveUpdateFeedConfig({ env: { [ENV_UPDATE_FEED]: '   ' }, ...DEV }).feedUrl).toBeNull()
    expect(resolveUpdateFeedConfig({ env: { [ENV_UPDATE_FEED]: '' }, ...DEV }).forceDev).toBe(false)
    expect(resolveUpdateFeedConfig({ env: { [ENV_UPDATE_FEED]: undefined }, ...DEV }).feedUrl).toBeNull()
  })

  it('feedUrl 首尾空白被裁剪', () => {
    const cfg = resolveUpdateFeedConfig({ env: { [ENV_UPDATE_FEED]: '  http://127.0.0.1:8788  ' }, ...DEV })
    expect(cfg.feedUrl).toBe('http://127.0.0.1:8788')
  })
})

describe('装配 → 适配层接线断言（回归锁定）', () => {
  it('dev + feed 时最终 forceDevUpdateConfig 必须为 true（否则检查被整体跳过）', () => {
    const feed = resolveUpdateFeedConfig({ env: { [ENV_UPDATE_FEED]: 'http://127.0.0.1:8788' }, ...DEV })
    // 装配层传给适配层的 options 即 { feedUrl, forceDev }
    expect(resolveForceDevUpdateConfig({ feedUrl: feed.feedUrl, forceDev: feed.forceDev })).toBe(true)
  })

  it('dev 无 feed 时 forceDevUpdateConfig 为 false；打包版不受该开关影响', () => {
    const dev = resolveUpdateFeedConfig({ env: {}, ...DEV })
    expect(resolveForceDevUpdateConfig({ feedUrl: dev.feedUrl, forceDev: dev.forceDev })).toBe(false)

    const packed = resolveUpdateFeedConfig({ env: {}, ...PACKED })
    expect(resolveForceDevUpdateConfig({ feedUrl: packed.feedUrl, forceDev: packed.forceDev })).toBe(false)
    expect(isUpdateChannelAvailable({ env: {}, ...PACKED })).toBe(true) // 打包版走 isPackaged 分支
  })

  it('forceDev 缺少 feedUrl 时无效（防止无 feed 时误放行去读线上源）', () => {
    expect(resolveForceDevUpdateConfig({ feedUrl: null, forceDev: true })).toBe(false)
  })
})

describe('更新通道可用性判定（服务层与适配层共用同一事实来源）', () => {
  it('打包版恒可用；dev 需 feed 覆盖', () => {
    expect(isUpdateChannelAvailable({ env: {}, ...PACKED })).toBe(true)
    expect(isUpdateChannelAvailable({ env: { [ENV_UPDATE_FEED]: 'http://127.0.0.1:8788' }, ...DEV })).toBe(true)
    expect(isUpdateChannelAvailable({ env: {}, ...DEV })).toBe(false)
  })

  it('服务层放行与适配层放行一致（此前自相矛盾的直接回归）', () => {
    const input = { env: { [ENV_UPDATE_FEED]: 'http://127.0.0.1:8788' }, ...DEV }
    const serviceAllows = isUpdateChannelAvailable(input)
    const adapterAllows = resolveForceDevUpdateConfig({
      feedUrl: resolveUpdateFeedConfig(input).feedUrl,
      forceDev: resolveUpdateFeedConfig(input).forceDev
    })
    expect(serviceAllows).toBe(true)
    expect(adapterAllows).toBe(true)
    expect(serviceAllows).toBe(adapterAllows)
  })
})
