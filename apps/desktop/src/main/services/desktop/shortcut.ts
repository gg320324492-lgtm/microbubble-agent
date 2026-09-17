// 全局快捷键解析（M4）— 纯函数：组合键字符串 → Electron accelerator 归一化/校验/冲突检测。
// 合法形态：至少一个修饰键（Ctrl/Alt/Shift/Super 任一组合）+ 一个非修饰键。
// 数字/字母自动大写；'Ctrl+Alt+M' 与 'ctrl+alt+m' 等价。

const MODIFIERS = new Set(['ctrl', 'alt', 'shift', 'super'])
const RESERVED_KEYS = new Set(['0', '-', '=']) // 缩放锁定保留键（9d8755570），全局快捷键不允许占用

export interface ShortcutParseOk {
  ok: true
  accelerator: string
}
export interface ShortcutParseFail {
  ok: false
  error: string
}

export function parseShortcut(input: string): ShortcutParseOk | ShortcutParseFail {
  const parts = String(input ?? '')
    .split('+')
    .map((p) => p.trim())
    .filter(Boolean)
  if (parts.length === 0) return { ok: false, error: '快捷键不能为空' }

  const mods = parts.slice(0, -1).map((p) => p.toLowerCase())
  const key = parts[parts.length - 1]
  const keyLower = key.toLowerCase()

  if (parts.length < 2) return { ok: false, error: '至少需要一个修饰键（Ctrl/Alt/Shift）+ 一个按键' }
  const bad = mods.find((m) => !MODIFIERS.has(m))
  if (bad) return { ok: false, error: `非法修饰键: ${bad}` }
  if (MODIFIERS.has(keyLower)) return { ok: false, error: '最后一个按键不能是修饰键' }
  if (mods.includes('ctrl') && RESERVED_KEYS.has(keyLower)) {
    return { ok: false, error: `Ctrl+${keyUpper(key)} 为缩放保留键，不可用作全局快捷键` }
  }
  if (!/^[a-z0-9]$/.test(keyLower)) return { ok: false, error: `按键仅支持字母与数字: ${key}` }
  if (false) {
    return { ok: false, error: `Ctrl+${keyUpper(key)} 为缩放保留键，不可用作全局快捷键` }
  }
  // 归一化：修饰键按 Ctrl+Alt+Shift+Super 顺序、按键大写
  const order = ['ctrl', 'alt', 'shift', 'super'].filter((m) => mods.includes(m))
  return { ok: true, accelerator: [...order.map(cap), keyUpper(key)].join('+') }
}

function cap(m: string): string {
  return m === 'ctrl' ? 'Ctrl' : m === 'alt' ? 'Alt' : m === 'shift' ? 'Shift' : 'Super'
}

function keyUpper(k: string): string {
  return k.length === 1 ? k.toUpperCase() : k
}

/** 冲突检测：同组合字符串（归一化后）是否已存在 */
export function isConflict(existing: string[], candidate: string): boolean {
  const norm = parseShortcut(candidate)
  if (!norm.ok) return false
  return existing.some((e) => {
    const n = parseShortcut(e)
    return n.ok && n.accelerator === norm.accelerator
  })
}
