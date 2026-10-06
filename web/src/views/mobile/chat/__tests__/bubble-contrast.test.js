/**
 * bubble-contrast.test.js — L-6 移动端聊天气泡 WCAG 对比度回归门禁 (2026-10-07)
 *
 * 背景: L-6 登记的两处 dark 违规 (2026-10-04 实测) —
 *   1. 助手气泡最坏背景对比度 4.47 (AA 正文线 4.5, .msg-meta --mg-text-soft)
 *   2. 用户气泡 白字 / 粉底 2.31 (--mg-on-primary on --mg-gradient-btn #F08AC0 段)
 * 修复后必须被盯住。
 *
 * 为什么不加 axe a11y 覆盖 (评估结论, 详见 L-6 修复 commit message):
 *   - axe color-contrast 不采样 background-image —— 用户气泡是 linear-gradient,
 *     axe 只会报 incomplete (不进 violations), 改回旧色也永远不红;
 *   - 助手气泡最坏背景来自 .mg-page 的 radial-gradient 极光, axe 只读
 *     background-color (#16131F) → 算出 ~5.9 假通过, 4.47 抓不到。
 *   ⇒ 两处违规都在 axe 结构性盲区, 只有确定性计算能反向验证 (旧色 → 红)。
 *   本测试直接解析 mobile-glass.css / MobileMessageBubble.vue 的真实 token 与接线,
 *   按 WCAG 2.1 相对亮度公式复算; 任何人改色/改接线都会被重算拦下。
 *
 * 范围外但已实测登记 (不在本门禁断言内):
 *   - .tool-trace 深色文字 —— 受 variables.css 级联 bug 影响 (第 3 个
 *     --color-text-secondary 声明写在 :root 1813 行, 与 [data-theme=dark] 809 行
 *     同特异度且更靠后 → dark 下实测 computed = #6B6E76 而非 #a8aab0,
 *     该色在任何深底上都到不了 4.5 —— 单靠气泡侧无解, 已作为独立发现上报);
 *   - .msg-error (--mg-danger) / markdown 链接色 / light 下 --mg-text-soft 3.376 ——
 *     均为既存、状态依赖或范围外, light text-soft 只锁了不回归下限 (见 3.x)。
 *
 * 模型 (与登记值 4.47 / 2.31 的复现模型一致, 复现值 4.473 / 2.307):
 *   页面背景 = --mg-page-bg (不透明) ← aurora-N (radial, alpha) —— 三块极光中心
 *   在 390x844 视口互不重叠 (fade 半径 260/248px, 中心距 ≥565 > 508),
 *   故最坏背景 = 三块中心逐层 8-bit 合成里亮度最高的那个。
 *   助手气泡 = 页面背景 ← 玻璃 (alpha) ← 文字。
 *   用户气泡 = 渐变 (sRGB 逐段 512 点采样; gamma 解码为凸函数, 端点校验 + 采样双保险)
 *             ← 白字; pre/code 上再叠 tint。
 */

import { describe, it, expect } from 'vitest'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, resolve } from 'node:path'

const HERE = dirname(fileURLToPath(import.meta.url))
const WEB_ROOT = resolve(HERE, '../../../../../') // src/views/mobile/chat/__tests__ -> web/
const GLASS_CSS = readFileSync(resolve(WEB_ROOT, 'src/assets/mobile-glass.css'), 'utf8')
const BUBBLE_VUE = readFileSync(
  resolve(WEB_ROOT, 'src/views/mobile/chat/MobileMessageBubble.vue'),
  'utf8'
)

// ---------- 最小 CSS 解析 ----------
// ⚠️ 先整体去注释再解析: 注释里可能出现 token 名/选择器字样, 且 stripComments
// 会移动下标 —— 绝不能"匹配时 strip、取块时用原文"。
function stripComments(s) {
  return s.replace(/\/\*[\s\S]*?\*\//g, '')
}
function block(css, selector) {
  const re = new RegExp(
    '^' + selector.replace(/[.*+?^${}()|[\]\\]/g, '\\$&') + '\\s*\\{',
    'm'
  )
  const m = css.match(re)
  if (!m) throw new Error(`block not found: ${selector}`)
  const start = m.index + m[0].length - 1
  let depth = 0
  for (let j = start; j < css.length; j++) {
    if (css[j] === '{') depth++
    else if (css[j] === '}') {
      depth--
      if (depth === 0) return css.slice(start + 1, j)
    }
  }
  throw new Error(`unbalanced block: ${selector}`)
}
function tok(src, name) {
  const m = src.match(new RegExp(name + '\\s*:\\s*([^;]+);'))
  if (!m) throw new Error(`token not found: ${name}`)
  return m[1].trim()
}

// ---------- WCAG 2.1 计算 ----------
function rgba(str) {
  const m = str.match(
    /rgba?\(\s*([\d.]+)\s*,\s*([\d.]+)\s*,\s*([\d.]+)\s*(?:,\s*([\d.]+))?\s*\)/
  )
  if (!m) throw new Error(`not rgba(): ${str}`)
  return { r: +m[1], g: +m[2], b: +m[3], a: m[4] === undefined ? 1 : +m[4] }
}
function hex(str) {
  let h = str.trim().replace('#', '')
  if (h.length === 3) h = h.split('').map((c) => c + c).join('')
  if (!/^[0-9a-fA-F]{6}$/.test(h)) throw new Error(`not hex: ${str}`)
  return {
    r: parseInt(h.slice(0, 2), 16),
    g: parseInt(h.slice(2, 4), 16),
    b: parseInt(h.slice(4, 6), 16),
    a: 1,
  }
}
function color(str) {
  return str.trim().startsWith('#') ? hex(str) : rgba(str)
}
function toHex(c) {
  const p = (n) =>
    Math.max(0, Math.min(255, Math.round(n))).toString(16).padStart(2, '0')
  return '#' + p(c.r) + p(c.g) + p(c.b)
}
/** 8-bit 逐层 alpha 合成 (与浏览器栅格化一致) */
function over(bottom, top) {
  const a = top.a
  return {
    r: Math.round(bottom.r * (1 - a) + top.r * a),
    g: Math.round(bottom.g * (1 - a) + top.g * a),
    b: Math.round(bottom.b * (1 - a) + top.b * a),
    a: 1,
  }
}
function lum(c) {
  const f = (v) => {
    v /= 255
    return v <= 0.03928 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4)
  }
  return 0.2126 * f(c.r) + 0.7152 * f(c.g) + 0.0722 * f(c.b)
}
function cr(fg, bg) {
  const a = lum(fg)
  const b = lum(bg)
  return (Math.max(a, b) + 0.05) / (Math.min(a, b) + 0.05)
}
function gradStops(grad) {
  return [...grad.matchAll(/(#[0-9a-fA-F]{3,8}|rgba?\([^)]+\))\s*[\d.]*%/g)].map(
    (m) => color(m[1])
  )
}
function gradSamples(grad, perSeg = 256) {
  const st = gradStops(grad)
  const out = []
  for (let i = 0; i < st.length - 1; i++) {
    for (let k = 0; k < perSeg; k++) {
      const t = k / (perSeg - 1)
      out.push({
        r: st[i].r + (st[i + 1].r - st[i].r) * t,
        g: st[i].g + (st[i + 1].g - st[i].g) * t,
        b: st[i].b + (st[i + 1].b - st[i].b) * t,
        a: 1,
      })
    }
  }
  return { samples: out, stops: st }
}

// ---------- token 装载 (全部在去注释后的副本上解析) ----------
const GLASS = stripComments(GLASS_CSS)
const VUE = stripComments(BUBBLE_VUE)
const ROOT = block(GLASS, ':root')
const DARK = block(GLASS, '[data-theme="dark"]')

const T = {
  light: {
    page: color(tok(ROOT, '--mg-page-bg')),
    auroras: ['--mg-aurora-1', '--mg-aurora-2', '--mg-aurora-3'].map((n) =>
      color(tok(ROOT, n))
    ),
    glass: color(tok(ROOT, '--mg-glass-bg')),
    text: color(tok(ROOT, '--mg-text')),
    textSoft: color(tok(ROOT, '--mg-text-soft')),
    textFaint: color(tok(ROOT, '--mg-text-faint')),
  },
  dark: {
    page: color(tok(DARK, '--mg-page-bg')),
    auroras: ['--mg-aurora-1', '--mg-aurora-2', '--mg-aurora-3'].map((n) =>
      color(tok(DARK, n))
    ),
    // 专用 token: 不存在即红 (有人删了它 → 模型失效, 必须显式处理)
    glass: color(tok(DARK, '--mg-glass-bg-bubble')),
    text: color(tok(DARK, '--mg-text')),
    textSoft: color(tok(DARK, '--mg-text-soft')),
  },
  onPrimary: color(tok(ROOT, '--mg-on-primary')),
  gradientBubble: tok(ROOT, '--mg-gradient-bubble'), // 不存在即红
}

// 组件接线里的 user pre/code tint
const USER_PRE_TINT = color(
  tok(block(VUE, '.bubble-user .msg-content :deep(pre)'), 'background')
)

/** 最坏 (最亮) 玻璃合成背景: page <- aurora <- glass */
function worstBg(theme) {
  const t = T[theme]
  const glass = theme === 'dark' ? T.dark.glass : T.light.glass
  const rows = t.auroras.map((au) => {
    const under = over(t.page, au)
    return { c: over(under, glass) }
  })
  rows.sort((a, b) => lum(b.c) - lum(a.c))
  return rows[0].c
}

const fmt = (v) => v.toFixed(3)

describe('L-6 移动端聊天气泡 WCAG 对比度门禁 (mobile-glass.css + MobileMessageBubble.vue)', () => {
  describe('1. 助手气泡 dark — 登记值 4.47 (AA 4.5)', () => {
    const bg = worstBg('dark')

    it('.msg-meta --mg-text-soft on 最坏背景 >= 4.5', () => {
      const v = cr(T.dark.textSoft, bg)
      expect(
        v,
        `--mg-text-soft ${toHex(T.dark.textSoft)} on ${toHex(bg)} = ${fmt(v)} (登记旧值 4.473)`
      ).toBeGreaterThanOrEqual(4.5)
    })

    it('正文 --mg-text on 最坏背景 >= 4.5', () => {
      const v = cr(T.dark.text, bg)
      expect(v, `--mg-text ${toHex(T.dark.text)} on ${toHex(bg)} = ${fmt(v)}`).toBeGreaterThanOrEqual(4.5)
    })
  })

  describe('2. 用户气泡 — 登记值 2.31 (AA 4.5, 双主题同 token)', () => {
    it('白字 on --mg-gradient-bubble 全段 (stops + 512 采样) >= 4.5', () => {
      const { samples } = gradSamples(T.gradientBubble)
      let min = Infinity
      let minBg = null
      for (const s of samples) {
        const v = cr(T.onPrimary, s)
        if (v < min) {
          min = v
          minBg = s
        }
      }
      expect(
        min,
        `white ${toHex(T.onPrimary)} worst-sample ${toHex(minBg)} = ${fmt(min)} (登记旧值 2.307)`
      ).toBeGreaterThanOrEqual(4.5)
    })

    it('白字 on pre/code tint 压过的每个 stop >= 4.5', () => {
      let worst = Infinity
      let worstBgHex = null
      for (const st of gradStops(T.gradientBubble)) {
        const tinted = over(st, USER_PRE_TINT)
        const v = cr(T.onPrimary, tinted)
        if (v < worst) {
          worst = v
          worstBgHex = tinted
        }
      }
      expect(
        worst,
        `white on tinted stop ${toHex(worstBgHex)} = ${fmt(worst)} (旧白 tint 时 2.024)`
      ).toBeGreaterThanOrEqual(4.5)
    })
  })

  describe('3. 浅色主题不回归 (共享类两主题都算)', () => {
    const bg = worstBg('light')

    it('助手气泡 light 正文 --mg-text >= 4.5', () => {
      const v = cr(T.light.text, bg)
      expect(v, `light body = ${fmt(v)} (修复前 12.115)`).toBeGreaterThanOrEqual(4.5)
    })

    it('助手气泡 light --mg-text-faint >= 4.5 (修复前 4.833, 本就达标)', () => {
      const v = cr(T.light.textFaint, bg)
      expect(v, `light faint = ${fmt(v)}`).toBeGreaterThanOrEqual(4.5)
    })

    it('助手气泡 light --mg-text-soft 不低于修复前 3.37 (既存未达 AA, 范围外, 锁下限)', () => {
      const v = cr(T.light.textSoft, bg)
      expect(
        v,
        `light text-soft = ${fmt(v)} — 既存 3.376 不在 L-6 范围, 此断言只防变差, 不代表达标`
      ).toBeGreaterThanOrEqual(3.37)
    })
  })

  describe('4. 接线守卫 (模型与组件必须同步, 改这里先重算对比度)', () => {
    it('.bubble-user 背景接 var(--mg-gradient-bubble) + 文字 var(--mg-on-primary)', () => {
      const m = VUE.match(/\.bubble-user\s*\{([^}]*)\}/)
      expect(m, '.bubble-user 规则不见了').toBeTruthy()
      expect(m[1]).toContain('background: var(--mg-gradient-bubble)')
      expect(m[1]).toContain('color: var(--mg-on-primary)')
    })

    it('.bubble-assistant 基础接 var(--mg-glass-bg), dark override 接 var(--mg-glass-bg-bubble)', () => {
      const base = VUE.match(/\.bubble-assistant\s*\{([^}]*)\}/)
      expect(base, '.bubble-assistant 规则不见了').toBeTruthy()
      expect(base[1]).toContain('background: var(--mg-glass-bg)')
      const dark = VUE.match(/\[data-theme="dark"\]\s*\.bubble-assistant\s*\{([^}]*)\}/)
      expect(dark, 'dark override 不见了 — 没它 4.47 违规会回来').toBeTruthy()
      expect(dark[1]).toContain('background: var(--mg-glass-bg-bubble)')
    })
  })
})
