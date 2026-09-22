// DL-1 缺陷回放：统一登录与远程数据源的状态断层
//
// 症状：用户经统一登录成功进入主界面，知识库/网盘却显示「未绑定」引导态。
// 根因（已定位）：数据源状态读的是 M2-3a 时代的**独立绑定状态存储**，而该存储只在已退役的
//   绑定 IPC 里置位；统一登录路径没有联动 → 且写入时机早于会话建立（键用旧/空用户 id），
//   读取时用新身份 → 键不匹配 → 永远读不到 → 误显「未绑定」。
//
// 修复：以**认证态为唯一事实源**推导（提供者模式），废除独立状态存储。
// 本文件是防复发的不变量断言。
import { describe, expect, it } from 'vitest'
import { cloudGuidance, cloudUsableStateFromAuth, type CloudAuthSnapshot } from '@main/services/cloud/guidance'

const snap = (over: Partial<CloudAuthSnapshot> = {}): CloudAuthSnapshot => ({
  loggedIn: false,
  isCloudIdentity: false,
  hasCloudTokens: false,
  ...over
})

describe('DL-1 状态推导：以认证态为唯一事实源', () => {
  it('★ 登录 → 数据源 bound（ready）；未登录 → unbound', () => {
    // 统一登录成功后的快照
    expect(cloudUsableStateFromAuth(snap({ loggedIn: true, isCloudIdentity: true, hasCloudTokens: true }))).toBe('ready')
    // 未登录
    expect(cloudUsableStateFromAuth(snap())).toBe('unbound')
  })

  it('★ 登出 → 回 unbound（无需任何「解绑」动作联动）', () => {
    const loggedIn = snap({ loggedIn: true, isCloudIdentity: true, hasCloudTokens: true })
    expect(cloudUsableStateFromAuth(loggedIn)).toBe('ready')
    // 登出 = 会话结束 + 令牌清除 → 同一推导函数直接给 unbound
    expect(cloudUsableStateFromAuth(snap())).toBe('unbound')
  })

  it('★ 不变量（防复发）：**已登录且是云端身份**时，数据源绝不允许是 unbound', () => {
    // 这是 DL-1 的核心不变量：只要登录成功，就不得再显示「未登录/未绑定」引导。
    // 遍历令牌与错误的组合，断言不会退化成 unbound。
    const combos: { hasCloudTokens: boolean; error?: { kind: 'network' | 'timeout' | 'server' } }[] = [
      { hasCloudTokens: true },
      { hasCloudTokens: true, error: { kind: 'network' } },
      { hasCloudTokens: true, error: { kind: 'timeout' } },
      { hasCloudTokens: true, error: { kind: 'server' } },
      { hasCloudTokens: false } // 令牌丢了 → 最多到 expired（提示重新登录），也不能是 unbound
    ]
    for (const c of combos) {
      const state = cloudUsableStateFromAuth(
        snap({ loggedIn: true, isCloudIdentity: true, hasCloudTokens: c.hasCloudTokens }),
        c.error as never
      )
      expect(state, `组合 ${JSON.stringify(c)} 不得为 unbound`).not.toBe('unbound')
    }
  })

  it('★ 不变量：未登录时绝不允许是 ready（不得凭残留状态放行）', () => {
    expect(cloudUsableStateFromAuth(snap({ hasCloudTokens: true }))).toBe('unbound')
    expect(cloudUsableStateFromAuth(snap({ isCloudIdentity: true }))).toBe('unbound')
  })

  it('已登录但云端令牌不可读 → expired（提示重新登录，而非静默 unbound）', () => {
    const state = cloudUsableStateFromAuth(snap({ loggedIn: true, isCloudIdentity: true, hasCloudTokens: false }))
    expect(state).toBe('expired')
    const g = cloudGuidance(state, '知识库')
    expect(g.title).toContain('失效')
    expect(g.canOpenSettings).toBe(true)
  })

  it('已登录 + 网络类错误 → offline（不是 unbound；引导指向网络而非登录）', () => {
    const state = cloudUsableStateFromAuth(
      snap({ loggedIn: true, isCloudIdentity: true, hasCloudTokens: true }),
      { kind: 'network', message: 'x' }
    )
    expect(state).toBe('offline')
    const g = cloudGuidance(state, '网盘')
    expect(g.title).toBe('当前离线')
    expect(g.canOpenSettings).toBe(false)
  })

  it('非云端身份（旧本地账号）→ unbound（引导登录，而非放行）', () => {
    expect(cloudUsableStateFromAuth(snap({ loggedIn: true, isCloudIdentity: false, hasCloudTokens: true }))).toBe('unbound')
  })
})

describe('DL-1 文案：不得再出现「绑定」旧措辞', () => {
  it('未登录引导文案为「需登录课题组账号…」，且不再出现「绑定」字样', () => {
    for (const feature of ['知识库', '网盘']) {
      const g = cloudGuidance('unbound', feature)
      expect(g.title).toContain(feature)
      expect(g.title).toContain('登录')
      expect(g.hint).not.toContain('绑定')
      expect(g.actionLabel).not.toContain('绑定')
      expect(g.actionLabel).toContain('账号')
    }
  })

  it('失效文案同样不含「绑定」字样', () => {
    const g = cloudGuidance('expired', '知识库')
    expect(g.title).not.toContain('绑定')
    expect(g.hint).not.toContain('绑定')
  })
})
