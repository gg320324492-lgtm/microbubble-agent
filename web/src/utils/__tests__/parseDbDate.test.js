/**
 * parseDbDate 回归测试 (时区显示 8 小时偏差根治, 2026-09-12)
 *
 * 背景: 后端 DateTime 列存 naive UTC, 经 str()/isoformat() 序列化产出无时区标记串,
 * 前端 new Date() 按浏览器本地时区解读 → 北京时间显示差 8 小时 (中午上传显示成凌晨 05:0x)。
 * 约定: 无时区标记的串一律视为 UTC (补 Z), 已带 Z/±hh:mm 的原样解析。
 *
 * 用例覆盖:
 * ① str(datetime) 产出 "2026-09-12 05:08:12.345678" (空格+6位微秒) → UTC 解析 + 微秒截断
 * ② isoformat() 产出 "2026-09-12T05:08:12" (T 分隔, 无标记) → UTC 解析
 * ③ 已带 Z 的 ISO 串 → 不二次补 Z (原样解析)
 * ④ 已带 ±hh:mm 偏移的串 → 原样解析
 * ⑤ date-only "2026-09-12" → 有效 Date (ES 规范 UTC 午夜)
 * ⑥ 非法/空输入 → null (调用方兜底显示原始串)
 * ⑦ Date 对象 / 数字时间戳透传
 * ⑧ 与带 Z 等价串解析到同一时刻 (naive 视为 UTC 的核心断言)
 */
import { describe, expect, it } from 'vitest'
import { parseDbDate } from '../format'

describe('parseDbDate naive UTC 补 Z 解析', () => {
  it('① 后端 str(datetime): 空格分隔 + 6 位微秒 → 按 UTC 解析, 微秒截到毫秒', () => {
    const d = parseDbDate('2026-09-12 05:08:12.345678')
    expect(d).not.toBeNull()
    expect(d.toISOString()).toBe('2026-09-12T05:08:12.345Z')
  })

  it('② isoformat(): T 分隔无时区标记 → 按 UTC 解析', () => {
    const d = parseDbDate('2026-09-12T05:08:12')
    expect(d).not.toBeNull()
    expect(d.toISOString()).toBe('2026-09-12T05:08:12.000Z')
  })

  it('③ 已带 Z 的串不再二次补 Z', () => {
    const d = parseDbDate('2026-09-12T05:08:12Z')
    expect(d.toISOString()).toBe('2026-09-12T05:08:12.000Z')
  })

  it('④ 已带 ±hh:mm 偏移的串原样解析', () => {
    const d = parseDbDate('2026-09-12T13:08:12+08:00')
    expect(d.toISOString()).toBe('2026-09-12T05:08:12.000Z')
  })

  it('⑤ date-only 串返回有效 Date', () => {
    const d = parseDbDate('2026-09-12')
    expect(d).not.toBeNull()
    expect(isNaN(d.getTime())).toBe(false)
  })

  it('⑥ 非法与空输入返回 null', () => {
    expect(parseDbDate(null)).toBeNull()
    expect(parseDbDate(undefined)).toBeNull()
    expect(parseDbDate('')).toBeNull()
    expect(parseDbDate('not-a-date')).toBeNull()
  })

  it('⑦ Date 对象 / 数字时间戳透传', () => {
    const now = new Date('2026-09-12T05:08:12Z')
    expect(parseDbDate(now).getTime()).toBe(now.getTime())
    expect(parseDbDate(now.getTime()).getTime()).toBe(now.getTime())
  })

  it('⑧ 核心断言: naive 串与等价带 Z 串解析到同一时刻', () => {
    const naive = parseDbDate('2026-09-12 05:08:12')
    const zulu = parseDbDate('2026-09-12T05:08:12Z')
    expect(naive.getTime()).toBe(zulu.getTime())
  })
})
