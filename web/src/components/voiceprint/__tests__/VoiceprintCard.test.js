/**
 * VoiceprintCard.test.js — v77 P2.6-G.2 收官 新增 Vitest 单测
 *
 * 覆盖 getBarClass(value) 阈值切 3 档 class 的纯逻辑:
 * - per-card max 归一化 (maxAbs computed) 避免老成员波形全 0 不可见
 * - 0.33 / 0.66 阈值切 .bar--low / .bar--mid / .bar--high
 * - NaN / null / undefined 兜底 .bar--low
 * - maxAbs=0 (全 0 embedding) 兜底 .bar--low
 *
 * 模式: 与 P2.6-F.2 ~ P2.6-F.5 一致 — 测纯逻辑不挂 el-* 子组件 (jsdom + EP 渲染问题)
 *       只用 el-avatar stub (组件用到), 不挂载 fingerprint bar 模板细节
 */
import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import VoiceprintCard from '../VoiceprintCard.vue'

const makeMember = (embedding) => ({
  id: 1,
  name: '王天志',
  avatar: '',
  sample_count: 5,
  embedding,
})

const factory = (props = {}) => mount(VoiceprintCard, {
  props: { member: makeMember([0.1, -0.05, 0, 0.2, -0.15]), ...props },
  global: {
    stubs: {
      'el-avatar': { template: '<div class="el-avatar-stub" />' },
    },
  },
})

describe('VoiceprintCard.vue v77 P2.6-G.2 getBarClass 阈值', () => {
  it('1. maxAbs=0.20 阈值切 3 档: |0.20|→high, |0.10|→mid, |0.05|→low', () => {
    const wrapper = factory({ member: makeMember([0.20, -0.20, 0.10, -0.10, 0.05, -0.05]) })
    const bars = wrapper.findAll('.bar')
    expect(bars).toHaveLength(6)
    expect(bars[0].classes()).toContain('bar--high')  // |0.20| / 0.20 = 1.00 ≥ 0.66
    expect(bars[1].classes()).toContain('bar--high')  // |-0.20| / 0.20 = 1.00
    expect(bars[2].classes()).toContain('bar--mid')   // |0.10| / 0.20 = 0.50 ∈ [0.33, 0.66)
    expect(bars[3].classes()).toContain('bar--mid')
    expect(bars[4].classes()).toContain('bar--low')   // |0.05| / 0.20 = 0.25 < 0.33
    expect(bars[5].classes()).toContain('bar--low')
  })

  it('2. 边界值: ratio 恰好 0.33 → mid, 恰好 0.66 → high', () => {
    // maxAbs=0.30, |0.099| / 0.30 = 0.33 → mid, |0.198| / 0.30 = 0.66 → high
    const wrapper = factory({ member: makeMember([0.099, 0.198]) })
    const bars = wrapper.findAll('.bar')
    expect(bars[0].classes()).toContain('bar--mid')
    expect(bars[1].classes()).toContain('bar--high')
  })

  it('3. NaN 兜底 .bar--low (maxAbs 不变, NaN 跳过)', () => {
    // NaN 跳过 maxAbs 比较, 0.1 仍为 maxAbs = 0.1, 0.1/0.1 = 1.0 → high
    const wrapper = factory({ member: makeMember([NaN, 0.1, NaN]) })
    const bars = wrapper.findAll('.bar')
    expect(bars[0].classes()).toContain('bar--low')   // NaN
    expect(bars[1].classes()).toContain('bar--high')  // |0.1|/0.1 = 1.0
    expect(bars[2].classes()).toContain('bar--low')   // NaN
  })

  it('4. null / undefined 兜底 .bar--low (null 视为 0, undefined NaN 跳过)', () => {
    // Number(null) = 0 (有限, abs=0 不参与 max), Number(undefined) = NaN (跳过)
    // 0.1 → abs=0.1 > 0 → max=0.1 → 0.1/0.1 = 1.0 → high
    const wrapper = factory({ member: makeMember([null, undefined, 0.1]) })
    const bars = wrapper.findAll('.bar')
    expect(bars[0].classes()).toContain('bar--low')   // null → Number(null)=0 → Number.isFinite 但 0 不 > max=0.1 → 跳过 max; getBarClass: Number.isFinite(0)=true 但 ratio=0/0.1=0 → low
    expect(bars[1].classes()).toContain('bar--low')   // undefined → NaN → Number.isFinite=false → low
    expect(bars[2].classes()).toContain('bar--high')  // 0.1 → 0.1/0.1=1.0 → high
  })

  it('5. maxAbs=0 (全 0 embedding) 全部 .bar--low', () => {
    const wrapper = factory({ member: makeMember([0, 0, 0]) })
    const bars = wrapper.findAll('.bar')
    expect(bars).toHaveLength(3)
    bars.forEach((bar) => {
      expect(bar.classes()).toContain('bar--low')
      expect(bar.classes()).not.toContain('bar--mid')
      expect(bar.classes()).not.toContain('bar--high')
    })
  })

  it('6. 空 embedding 不渲染 bar (老 fallback)', () => {
    const wrapper = factory({ member: makeMember([]) })
    expect(wrapper.findAll('.bar')).toHaveLength(0)
  })

  it('7. negative value 不影响 class 切档 (只看 |value| / maxAbs)', () => {
    // 原 barColor() 用 '64, 158, 255' 信息蓝区分正负, 收敛后只看 ratio
    const wrapper = factory({ member: makeMember([-0.20, 0.20, -0.10, 0.10]) })
    const bars = wrapper.findAll('.bar')
    expect(bars[0].classes()).toContain('bar--high')  // 与 bars[1] 同
    expect(bars[1].classes()).toContain('bar--high')
    expect(bars[2].classes()).toContain('bar--mid')   // 与 bars[3] 同
    expect(bars[3].classes()).toContain('bar--mid')
  })

  it('8. max bar 数 = member.embedding.length (动态)', () => {
    const wrapper = factory({ member: makeMember(new Array(256).fill(0.1)) })
    expect(wrapper.findAll('.bar')).toHaveLength(256)
  })
})
