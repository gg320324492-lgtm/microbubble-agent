/**
 * variables-text-secondary-cascade.test.js — 双主题级联 + 对比度确定性门禁 (2026-10-07)
 *
 * 背景 (复检官机械坐实的级联 bug, 本测试是它的可证伪门禁):
 *   variables.css 里 --color-text-secondary 有 3 处声明:
 *     :root #909399 (light 原值) / [data-theme="dark"] #a8aab0 (v69 提亮)
 *     / light axe campaign 又在裸 :root 写 #6B6E76。
 *   :root 与 [data-theme="dark"] 特异度同为 (0,1,0), 后者更靠后 ⇒
 *   **dark 计算值被 light 值盖死**成 #6B6E76, 暗色全站副文本 ≈2:1
 *   (#6B6E76 在任何深底上到不了 4.5 —— #1a1d23 上 3.31, #2a2d35 上 2.70,
 *   组件级无解)。修复 = 把覆盖型声明改挂 :root:not([data-theme="dark"])。
 *
 * 为什么不靠 jsdom computed style (cssVariables.test.js 的口径): jsdom 不做
 * 完整级联, 抓不住"同特异度、靠源顺序盖死"这类病; axe 也测不了 —— 它只扫
 * light 页面 (a11y spec 全程不切 dark)。故本测试直接解析 variables.css 真实
 * 声明, 按 特异度 + 源顺序 模拟三种选择器形态
 *   :root / [data-theme="dark"] / :root:not([data-theme="dark"]) / [data-theme]
 * 在 light / dark 两种 documentElement 属性态下的胜者, 再按 WCAG 2.1 相对
 * 亮度公式复算对各自页面底的对比度。任何人把 1815/1816 改回裸 :root,
 * dark 胜者即被打回 #6B6E76 → 本测试必红 (反向验证实测见修复提交说明)。
 *
 * 范围: 只管全局 token 级联 (variables.css)。组件/页面作用域的局部覆盖
 * (.meeting-view / [data-theme="dark"] .meeting-view 等) 是另一套机制, 不在本门禁内。
 */
import { describe, it, expect } from 'vitest'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, resolve } from 'node:path'

const HERE = dirname(fileURLToPath(import.meta.url))
const CSS_PATH = resolve(HERE, '../../src/assets/variables.css')
const CSS = readFileSync(CSS_PATH, 'utf8')

// ---------- 最小 CSS 解析 ----------
// ⚠️ 先整体去注释再解析: 注释里可能出现 token 名/选择器字样。
function stripComments(s) {
  return s.replace(/\/\*[\s\S]*?\*\//g, '')
}

/**
 * 顶层规则扫描。返回 [{ selector, body, index }]。
 * - @keyframes/@font-face 整体跳过 (其内部不是真选择器)
 * - @media/@supports 递归解析内部规则 (variables.css:263/272 有 2 个 @media)
 * - 其余 at-rule 一律 fail loud — 未建模的结构不许静默吞掉
 */
function topLevelRules(css) {
  const rules = []
  function parse(src, base, inAtRule) {
    let i = 0
    let bufStart = 0
    while (i < src.length) {
      const ch = src[i]
      if (ch === '{') {
        const sel = src.slice(bufStart, i).trim()
        let d = 1
        let j = i + 1
        while (j < src.length && d > 0) {
          if (src[j] === '{') d++
          else if (src[j] === '}') d--
          j++
        }
        const body = src.slice(i + 1, j - 1)
        if (/^@(keyframes|-webkit-keyframes|font-face)\b/.test(sel)) {
          // skip
        } else if (/^@(media|supports)\b/.test(sel)) {
          parse(body, base + i + 1, true)
        } else if (sel.startsWith('@')) {
          throw new Error(`variables.css 出现未建模的 at-rule: ${sel.slice(0, 60)}`)
        } else {
          rules.push({ selector: sel, body, index: base + i })
        }
        i = j
        bufStart = i
        continue
      } else if (ch === '}') {
        if (!inAtRule) throw new Error(`variables.css 不平衡 } @ ${base + i}`)
        // 内层 @media 解析到自己的收尾 }
        i++
        bufStart = i
        continue
      }
      i++
    }
  }
  parse(css, 0, false)
  return rules
}

const RULES = topLevelRules(stripComments(CSS))

// ---------- 选择器建模 (只认这 4 种声明形态, 其余 fail loud) ----------
// theme: 'light' | 'dark' — useThemeStore 恒 setAttribute('data-theme', mode);
// light 态属性值为 "light" (或 JS 起飞前缺省), 两者对 :not([data-theme="dark"]) 等价。
function selectorMatches(selector, theme) {
  const s = selector.trim()
  if (s === ':root') return true
  if (s === '[data-theme]') return true
  if (s === '[data-theme="dark"]') return theme === 'dark'
  if (s === ':root:not([data-theme="dark"])') return theme !== 'dark'
  return null // 未建模
}

// 这 4 种形态的特异度 (只数 :root 伪类与属性选择器; :not 贡献=其参数, 已含在 [] 计数里)
function specificity(selector) {
  const s = selector.trim()
  let w = (s.match(/:root/g) || []).length
  w += (s.match(/\[[^\]]*\]/g) || []).length
  return w
}

function declarationsOf(token) {
  const esc = token.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
  const re = new RegExp(`(^|[\\s;])${esc}\\s*:\\s*([^;]+);`, 'm')
  const out = []
  for (const r of RULES) {
    const m = r.body.match(re)
    if (m) out.push({ selector: r.selector.trim(), value: m[2].trim(), index: r.index })
  }
  if (!out.length) throw new Error(`token 无任何声明: ${token}`)
  return out
}

/** 某主题下的胜者 = 特异度最高, 平手取源顺序最靠后 (CSS 级联规则) */
function winner(token, theme) {
  const cands = declarationsOf(token).map((d) => ({ ...d, sp: specificity(d.selector) }))
  for (const c of cands) {
    const m = selectorMatches(c.selector, theme)
    if (m === null) {
      throw new Error(
        `${token} 出现未建模的选择器形态: "${c.selector}" — ` +
          `请在 selectorMatches/specificity 里补建模 (防止胜者算错造成假绿)`
      )
    }
    c.matches = m
  }
  const matched = cands.filter((c) => c.matches)
  if (!matched.length) throw new Error(`${token} 在 ${theme} 下无匹配声明`)
  matched.sort((a, b) => a.sp - b.sp || a.index - b.index)
  return matched[matched.length - 1]
}

// ---------- WCAG 2.1 计算 ----------
function hex(str) {
  let h = str.trim().replace('#', '')
  if (h.length === 3) h = h.split('').map((c) => c + c).join('')
  if (!/^[0-9a-fA-F]{6}$/.test(h)) throw new Error(`not hex: ${str}`)
  return { r: parseInt(h.slice(0, 2), 16), g: parseInt(h.slice(2, 4), 16), b: parseInt(h.slice(4, 6), 16) }
}
function lum(c) {
  const f = (v) => {
    v /= 255
    return v <= 0.03928 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4)
  }
  return 0.2126 * f(c.r) + 0.7152 * f(c.g) + 0.0722 * f(c.b)
}
function cr(fg, bg) {
  const a = lum(hex(fg))
  const b = lum(hex(bg))
  return (Math.max(a, b) + 0.05) / (Math.min(a, b) + 0.05)
}
const fmt = (v) => v.toFixed(3)

// light campaign 实证底色 (W91-X-19 axe 段落, 值不许漂)
const LIGHT_WHITE = '#ffffff'
const LIGHT_WORST_WARM = '#fff0ed' // .session-* 在 .is-active 暖底上, 最差底色

describe('variables.css --color-text-secondary 双主题级联 (覆盖型声明必须 light-scoped)', () => {
  const TOKEN = '--color-text-secondary'
  const RGB = '--color-text-secondary-rgb'

  const lightWin = winner(TOKEN, 'light')
  const darkWin = winner(TOKEN, 'dark')
  const lightRgbWin = winner(RGB, 'light')
  const darkRgbWin = winner(RGB, 'dark')

  describe('1. 胜者身份 (级联模拟: 特异度 + 源顺序)', () => {
    it('light 胜者 = light-scoped 声明 #6B6E76 (axe 实证 5.10/4.60, 不许变)', () => {
      expect(lightWin.value).toBe('#6B6E76')
      // 且必须来自 light-scoped 选择器, 不能是裸 :root 撞运气
      expect(lightWin.selector, 'light 值应由 :root:not([data-theme="dark"]) 提供').toBe(
        ':root:not([data-theme="dark"])'
      )
    })

    it('dark 胜者 = v69 既定值 #a8aab0 (bug 态这里是 #6B6E76 → 必红)', () => {
      expect(darkWin.value).toBe('#a8aab0')
      expect(darkWin.selector, 'dark 值应由 [data-theme="dark"] 提供 — 裸 :root 盖死 dark 即红').toBe(
        '[data-theme="dark"]'
      )
    })

    it('rgb 三元组同验: light = 107,110,118 / dark = 168,170,176', () => {
      expect(lightRgbWin.value).toBe('107, 110, 118')
      expect(darkRgbWin.value).toBe('168, 170, 176')
      expect(darkRgbWin.selector).toBe('[data-theme="dark"]')
    })

    it('双主题 hex ↔ rgb 自洽 (防两处只改一处)', () => {
      const norm = (s) => s.split(',').map((x) => x.trim()).join(',')
      const toRgb = (h) => {
        const c = hex(h)
        return `${c.r}, ${c.g}, ${c.b}`
      }
      expect(norm(toRgb(lightWin.value))).toBe(norm(lightRgbWin.value))
      expect(norm(toRgb(darkWin.value))).toBe(norm(darkRgbWin.value))
      expect(norm(lightRgbWin.value)).toBe('107,110,118')
      expect(norm(darkRgbWin.value)).toBe('168,170,176')
    })

    it('无主题属性 (JS 起飞前) 与 light 同胜者', () => {
      // :root:not(...) 对缺省属性同样匹配 — 用 light 模拟即可, 但显式锁住语义:
      expect(selectorMatches(':root:not([data-theme="dark"])', 'light')).toBe(true)
      expect(selectorMatches('[data-theme="dark"]', 'light')).toBe(false)
    })
  })

  describe('2. 对各自页面底的对比度 (WCAG 2.1, AA 正文线 4.5)', () => {
    const lightBg = winner('--color-bg-page', 'light').value
    const darkBg = winner('--color-bg-page', 'dark').value
    const darkCard = winner('--color-bg-card', 'dark').value

    it(`light #6B6E76 on 页面底 ${lightBg} >= 4.5`, () => {
      const v = cr(lightWin.value, lightBg)
      expect(v, `light ${lightWin.value} on ${lightBg} = ${fmt(v)}`).toBeGreaterThanOrEqual(4.5)
    })

    it('light #6B6E76 on 白底 >= 4.5 (campaign 实证 5.10)', () => {
      const v = cr(lightWin.value, LIGHT_WHITE)
      expect(v, `light ${lightWin.value} on ${LIGHT_WHITE} = ${fmt(v)}`).toBeGreaterThanOrEqual(4.5)
    })

    it('light #6B6E76 on 最差暖底 #fff0ed >= 4.5 (campaign 实证 4.60, 不许变)', () => {
      const v = cr(lightWin.value, LIGHT_WORST_WARM)
      expect(v, `light ${lightWin.value} on ${LIGHT_WORST_WARM} = ${fmt(v)}`).toBeGreaterThanOrEqual(4.5)
    })

    it(`dark #a8aab0 on 页面底 ${darkBg} >= 4.5 (bug 态 #6B6E76 只有 3.31 → 必红)`, () => {
      const v = cr(darkWin.value, darkBg)
      expect(v, `dark ${darkWin.value} on ${darkBg} = ${fmt(v)}`).toBeGreaterThanOrEqual(4.5)
    })

    it(`dark #a8aab0 on 卡片底 ${darkCard} >= 4.5 (bug 态 2.70 → 必红; .tool-trace 等同族)`, () => {
      const v = cr(darkWin.value, darkCard)
      expect(v, `dark ${darkWin.value} on ${darkCard} = ${fmt(v)}`).toBeGreaterThanOrEqual(4.5)
    })
  })

  describe('3. 结构守卫 (1813 段分类: 覆盖型 light-scoped / 新增型留裸 :root)', () => {
    it('覆盖型两条声明都在 light-only 块内, 不在裸 :root 块内', () => {
      const decls = declarationsOf(TOKEN).concat(declarationsOf(RGB))
      for (const d of decls) {
        if (d.value === '#6B6E76' || d.value === '107, 110, 118') {
          expect(d.selector, `${TOKEN}: ${d.value} 必须 light-scoped`).toBe(
            ':root:not([data-theme="dark"])'
          )
        }
      }
    })

    it('新增型 token 仍由裸 :root 提供 (移进 light-only 会让 dark 引用变 undefined)', () => {
      for (const t of ['--color-primary-text', '--color-primary-strong', '--color-warning-text']) {
        const light = winner(t, 'light')
        const dark = winner(t, 'dark')
        // dark 必须仍能解析到值 (--color-primary-text 另有 dark 翻转, 值可以不同)
        expect(light.value, `${t} light`).not.toBe('')
        expect(dark.value, `${t} dark 不得 undefined`).not.toBe('')
        expect([':root', '[data-theme="dark"]']).toContain(light.selector)
      }
    })

    it('dark 块仍声明 v69 值 (有人删 dark 声明时先红)', () => {
      const darkDecl = declarationsOf(TOKEN).find((d) => d.selector === '[data-theme="dark"]')
      expect(darkDecl, '[data-theme="dark"] 的 --color-text-secondary 声明被删').toBeTruthy()
      expect(darkDecl.value).toBe('#a8aab0')
    })
  })
})
