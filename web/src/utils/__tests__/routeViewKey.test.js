import { describe, it, expect } from 'vitest'
import { buildRouteViewKey } from '@/utils/routeViewKey'

/**
 * 2026-11-09 P0 回归守卫：会议详情播放录音时切换 TabStrip 不应中断音频。
 *
 * 事故机制：App.vue 原先用 :key="route.fullPath"，而 MeetingDetailView 的
 * watch(activeTab) 会 router.replace({ query: { ...route.query, tab } })
 * ⇒ fullPath 变 ⇒ 整棵路由组件重建 ⇒ <audio> 被销毁 ⇒ 播放停止。
 *
 * 这里守「key 在 tab 变化时不变」，同时守「其它 query / params / hash
 * 变化仍会重建」，避免把深链初始化语义一并改坏。
 */
describe('buildRouteViewKey', () => {
  const base = {
    path: '/meetings/273',
    params: { id: '273' },
    query: { tab: 'transcript' },
    hash: '',
  }

  it('只切 ?tab= 时 key 不变（播放中的 <audio> 不会被卸载）', () => {
    expect(buildRouteViewKey(base)).toBe(
      buildRouteViewKey({ ...base, query: { tab: 'minutes' } })
    )
    expect(buildRouteViewKey(base)).toBe(
      buildRouteViewKey({ ...base, query: { tab: 'stats' } })
    )
  })

  it('带上其它 query 时忽略 tab 不影响稳定性', () => {
    const a = { ...base, query: { tab: 'transcript', resume: '1', view: 'compact' } }
    const b = { ...base, query: { view: 'compact', tab: 'minutes', resume: '1' } }
    expect(buildRouteViewKey(a)).toBe(buildRouteViewKey(b))
  })

  it('其它 query 键值变化仍触发 remount（resume / search / id / list / idx）', () => {
    for (const q of [
      { tab: 'transcript', resume: '2' },
      { tab: 'transcript', search: '纳米气泡' },
      { tab: 'transcript', id: '42' },
      { tab: 'transcript', list: 'a,b' },
      { tab: 'transcript', idx: '3' },
    ]) {
      expect(buildRouteViewKey({ ...base, query: q })).not.toBe(buildRouteViewKey(base))
    }
  })

  it('path / params / hash 变化仍触发 remount', () => {
    expect(buildRouteViewKey({ ...base, path: '/meetings/274' })).not.toBe(buildRouteViewKey(base))
    expect(buildRouteViewKey({ ...base, params: { id: '274' } })).not.toBe(buildRouteViewKey(base))
    expect(buildRouteViewKey({ ...base, hash: '#seg12' })).not.toBe(buildRouteViewKey(base))
  })

  it('array query 稳定序列化，null / undefined 不造成假变化', () => {
    const a = buildRouteViewKey({ ...base, query: { tab: 'transcript', tag: ['a', 'b'] } })
    const b = buildRouteViewKey({ ...base, query: { tab: 'stats', tag: ['a', 'b'] } })
    expect(a).toBe(b)
    expect(buildRouteViewKey({ ...base, query: { tab: undefined } })).toBe(
      buildRouteViewKey({ ...base, query: {} })
    )
  })
})
