// 全局快捷键解析契约（M4）— 纯函数：归一化/校验/缩放保留键拒绝/冲突检测
import { describe, expect, it } from 'vitest'
import { parseShortcut, isConflict } from '@main/services/desktop/shortcut'

describe('parseShortcut', () => {
  it('合法组合归一化 — 大小写无关、修饰键按序', () => {
    expect(parseShortcut('Ctrl+Alt+M')).toEqual({ ok: true, accelerator: 'Ctrl+Alt+M' })
    const r1 = parseShortcut('ctrl+alt+m')
    expect(r1.ok).toBe(true)
    if (r1.ok) expect(r1.accelerator).toBe('Ctrl+Alt+M')
    const r2 = parseShortcut('Alt+Ctrl+M')
    expect(r2.ok).toBe(true)
    if (r2.ok) expect(r2.accelerator).toBe('Ctrl+Alt+M')
  })

  it('非法组合 — 无修饰键 / 修饰键结尾 / 非字母数字 / 非法修饰键', () => {
    expect(parseShortcut('M').ok).toBe(false)
    expect(parseShortcut('Ctrl+').ok).toBe(false)
    expect(parseShortcut('Ctrl+Alt+Shift').ok).toBe(false)
    expect(parseShortcut('Ctrl+F12').ok).toBe(false) // 仅字母数字
    expect(parseShortcut('Foo+M').ok).toBe(false)
  })

  it('缩放保留键 — Ctrl+0/-/= 拒绝（与 9d8755570 缩放锁定共存）', () => {
    for (const key of ['0', '-', '=']) {
      const r = parseShortcut(`Ctrl+${key}`)
      expect(r.ok).toBe(false)
      if (!r.ok) expect(r.error).toContain('保留')
    }
    // 非 Ctrl 修饰键组合不与缩放冲突
    expect(parseShortcut('Alt+Shift+0').ok).toBe(true)
  })
})

describe('isConflict 冲突检测', () => {
  it('归一化后同组合视为冲突', () => {
    expect(isConflict(['Ctrl+Alt+M'], 'ctrl+alt+m')).toBe(true)
    expect(isConflict(['Ctrl+Alt+M'], 'Ctrl+Alt+N')).toBe(false)
  })
  it('非法候选不视为冲突', () => {
    expect(isConflict(['Ctrl+Alt+M'], 'garbage')).toBe(false)
  })
})
