/**
 * W100 +55c: formatTimeDivider 三档单元测试
 *
 * 覆盖:
 * - 同一天 → "今天 HH:MM"
 * - 昨天 → "昨天 HH:MM"
 * - 7 天前 → "YYYY-MM-DD"
 * - 跨时区/跨日界边界 (now = 当日 00:00, 昨天 23:59)
 */

import { describe, expect, it } from 'vitest'
import { formatTimeDivider } from '../timeDivider'

describe('W100 +55c formatTimeDivider 三档', () => {
  it('① 同一天 → "今天 HH:MM"', () => {
    const now = new Date(2026, 7, 3, 14, 30, 0) // 2026-08-03 14:30
    const msg = new Date(2026, 7, 3, 9, 15, 0) // 当日 09:15
    expect(formatTimeDivider(msg, now)).toMatch(/^今天\s\d{2}:\d{2}$/)
  })

  it('② 昨天 → "昨天 HH:MM"', () => {
    const now = new Date(2026, 7, 3, 14, 30, 0)
    const msg = new Date(2026, 7, 2, 22, 5, 0) // 昨天 22:05
    expect(formatTimeDivider(msg, now)).toMatch(/^昨天\s\d{2}:\d{2}$/)
  })

  it('③ 7 天前 → "YYYY-MM-DD"', () => {
    const now = new Date(2026, 7, 3, 14, 30, 0)
    const msg = new Date(2026, 6, 27, 8, 0, 0) // 7 天前
    // zh-CN locale 输出 2026/07/27 或 2026-07-27 (依赖环境)
    const out = formatTimeDivider(msg, now)
    expect(out).not.toMatch(/^今天/)
    expect(out).not.toMatch(/^昨天/)
    // 含 2026 + 07 + 27
    expect(out).toContain('2026')
    expect(out).toContain('27')
  })

  it('④ 跨日界: now=00:00, 昨天 23:59 → "昨天 HH:MM"', () => {
    const now = new Date(2026, 7, 3, 0, 0, 0) // 当日 00:00 整
    const msg = new Date(2026, 7, 2, 23, 59, 0) // 昨天 23:59
    expect(formatTimeDivider(msg, now)).toMatch(/^昨天\s\d{2}:\d{2}$/)
  })
})
