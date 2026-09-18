// M6-1 更新状态机 — 纯 reducer 流转（含错误态与禁用态）
import { describe, expect, it } from 'vitest'
import { canInstall, initialUpdateState, isBusy, reduceUpdate } from '@main/services/update/update-state'
import type { UpdateState } from '@shared/types'

/** 按事件序列折叠状态，便于断言流转链 */
function run(events: Parameters<typeof reduceUpdate>[1][], start: UpdateState = initialUpdateState()): UpdateState {
  return events.reduce((s, e) => reduceUpdate(s, e), start)
}

describe('更新状态机 — 正常流转', () => {
  it('idle → checking → available(v0.1.5-alpha) → downloading → ready', () => {
    let s = initialUpdateState()
    expect(s.status).toBe('idle')

    s = reduceUpdate(s, { type: 'check-start' })
    expect(s.status).toBe('checking')
    expect(isBusy(s)).toBe(true)

    s = reduceUpdate(s, { type: 'check-available', version: '0.1.5-alpha' })
    expect(s.status).toBe('available')
    expect(s.version).toBe('0.1.5-alpha')
    expect(s.percent).toBe(0)
    expect(canInstall(s)).toBe(false)

    s = reduceUpdate(s, { type: 'download-start' })
    expect(s.status).toBe('downloading')

    s = reduceUpdate(s, { type: 'download-progress', percent: 42.4 })
    expect(s.percent).toBe(42)

    s = reduceUpdate(s, { type: 'download-done' })
    expect(s.status).toBe('ready')
    expect(s.percent).toBe(100)
    expect(canInstall(s)).toBe(true)
  })

  it('无更新回到 idle 并记录 checkedAt；进度被夹取到 0..100', () => {
    const s1 = run([{ type: 'check-start' }, { type: 'check-none' }], initialUpdateState())
    expect(s1.status).toBe('idle')
    expect(s1.checkedAt).toBeGreaterThan(0)
    expect(s1.version).toBeNull()

    const s2 = run(
      [
        { type: 'check-start' },
        { type: 'check-available', version: '0.1.5-alpha' },
        { type: 'download-start' },
        { type: 'download-progress', percent: 150 }
      ],
      initialUpdateState()
    )
    expect(s2.percent).toBe(100)

    const s3 = reduceUpdate(s2, { type: 'download-progress', percent: -5 })
    expect(s3.percent).toBe(0)
  })
})

describe('更新状态机 — 错误态', () => {
  it('检查失败进入 error 并保留原因，重新检查可回到 checking', () => {
    let s = run([{ type: 'check-start' }, { type: 'check-error', message: 'feed 404' }], initialUpdateState())
    expect(s.status).toBe('error')
    expect(s.error).toBe('feed 404')
    expect(s.version).toBeNull()

    s = reduceUpdate(s, { type: 'check-start' })
    expect(s.status).toBe('checking')
    expect(s.error).toBeNull()
  })

  it('下载失败进入 error；error 态不允许直接 download-start', () => {
    const s = run(
      [
        { type: 'check-start' },
        { type: 'check-available', version: '0.1.5-alpha' },
        { type: 'download-start' },
        { type: 'download-error', message: '网络中断' }
      ],
      initialUpdateState()
    )
    expect(s.status).toBe('error')
    expect(s.error).toBe('网络中断')
    expect(canInstall(s)).toBe(false)

    const s2 = reduceUpdate(s, { type: 'download-start' })
    expect(s2).toBe(s) // 非法流转：原状态引用不变
  })
})

describe('更新状态机 — 禁用态与幂等', () => {
  it('禁用态下 check-start 被忽略，始终停留 idle', () => {
    let s = reduceUpdate(initialUpdateState(), { type: 'set-disabled', disabled: true })
    expect(s.disabled).toBe(true)
    expect(s.status).toBe('idle')

    s = reduceUpdate(s, { type: 'check-start' })
    expect(s.status).toBe('idle')

    // 即便收到 available 也不会推进
    s = reduceUpdate(s, { type: 'check-available', version: '0.1.5-alpha' })
    expect(s.status).toBe('idle')
    expect(s.version).toBeNull()
  })

  it('解除禁用后恢复可检查；ready 态忽略 check-start（不丢弃已下载包）', () => {
    let s = reduceUpdate(initialUpdateState(true), { type: 'set-disabled', disabled: false })
    expect(s.disabled).toBe(false)
    s = reduceUpdate(s, { type: 'check-start' })
    expect(s.status).toBe('checking')

    const ready = run(
      [
        { type: 'check-start' },
        { type: 'check-available', version: '0.1.5-alpha' },
        { type: 'download-start' },
        { type: 'download-done' }
      ],
      initialUpdateState()
    )
    expect(reduceUpdate(ready, { type: 'check-start' })).toBe(ready)

    // reset 回到 idle 但保留禁用标记
    const reset = reduceUpdate(ready, { type: 'reset' })
    expect(reset.status).toBe('idle')
    expect(reset.version).toBeNull()
  })
})
