// CSS 级联断言（V1）— 纯函数，供 smoke 门禁与单测共用。
//
// 目的：堵住「CSS 覆盖静默失效」整类缺陷。M7 的 EP 特异性缺陷（`:root` 是伪类 0,1,0，
// 与 `[data-theme='paper']` 同级 → 被后加载的 EP 样式压掉）若早有本断言，CI 会直接拦截。
//
// 做法：不满足于"文本里出现过品牌色"，而是**按 CSS 级联规则求出真正胜出的那条声明**：
//   胜者 = 特异性最高者；特异性相同则文档序靠后者胜。
// 只有这样，"写了但没生效"才判为失败。

/** 单条声明 */
// { selector, value, index }

/**
 * 计算选择器特异性 → [id, class级(类/属性/伪类), 元素级]
 * 只覆盖本仓库会用到的选择器形态（元素 / 类 / 属性 / 伪类 / 后代 / 逗号组）。
 */
export function specificity(selector) {
  const s = String(selector ?? '').trim()
  if (!s) return [0, 0, 0]
  const ids = (s.match(/#[\w-]+/g) ?? []).length
  const classes = (s.match(/\.[\w-]+/g) ?? []).length
  const attrs = (s.match(/\[[^\]]*\]/g) ?? []).length
  // 伪类（排除 ::伪元素），形如 :root / :not(...) / :hover
  const pseudos = (s.match(/:(?!:)[\w-]+(\([^)]*\))?/g) ?? []).length
  // 元素名：出现在开头或分隔符（空格/>/+/~/,/(）之后
  const types = (s.match(/(?:^|[\s>+~,(])([a-zA-Z][\w-]*)/g) ?? []).length
  return [ids, classes + attrs + pseudos, types]
}

/** 比较特异性：[a,b,c] 字典序，返回 -1/0/1 */
export function compareSpecificity(a, b) {
  for (let i = 0; i < 3; i++) {
    if (a[i] !== b[i]) return a[i] < b[i] ? -1 : 1
  }
  return 0
}

/** 剥离 CSS 注释 —— 必须做：注释里常出现「EP 自己的 :root{--el-color-primary:#409eff}」这类
 *  说明文字，不剥离会被当成真声明解析，且注释文本会污染选择器特异性的统计。 */
export function stripComments(css) {
  return String(css ?? '').replace(/\/\*[\s\S]*?\*\//g, '')
}

/**
 * 收集某个自定义属性的所有声明（含所在选择器与文档序）。
 * @param {string} css 单份 CSS 文本
 * @param {string} prop 如 '--el-color-primary'
 * @param {number} baseIndex 文档序起始偏移（多份 CSS 拼接时用）
 */
export function collectDeclarations(css, prop, baseIndex = 0) {
  const out = []
  const text = stripComments(css)
  // 逐条规则扫描：selector { ... }（不处理 @media 嵌套，本仓库品牌色映射不在媒体查询内）
  const ruleRe = /([^{}]+)\{([^{}]*)\}/g
  let m
  let order = baseIndex
  while ((m = ruleRe.exec(text)) !== null) {
    const selector = m[1].trim()
    const body = m[2]
    const declRe = new RegExp(`${prop.replace(/[-[\]{}()*+?.,\\^$|#\s]/g, '\\$&')}\\s*:\\s*([^;]+);?`, 'g')
    let d
    while ((d = declRe.exec(body)) !== null) {
      out.push({ selector, value: d[1].trim(), index: order++ })
    }
  }
  return out
}

/** 求出真正胜出的声明（特异性优先，同级取文档序靠后） */
export function winningDeclaration(declarations) {
  let winner = null
  for (const d of declarations ?? []) {
    if (!winner) {
      winner = d
      continue
    }
    const cmp = compareSpecificity(specificity(d.selector), specificity(winner.selector))
    if (cmp > 0 || (cmp === 0 && d.index >= winner.index)) winner = d
  }
  return winner
}

/** 值比较归一化：去引号差异（压缩器会把 "Songti SC" 写成 'Songti SC'）、压空白、转小写 */
export function normalizeCssValue(v) {
  return String(v ?? '')
    .replace(/["']/g, '')
    .replace(/\s+/g, ' ')
    .trim()
    .toLowerCase()
}

/**
 * 断言：某自定义属性最终生效值等于期望值。
 * @param {string[]} cssTexts 按加载顺序拼接的 CSS 文本（前者先加载）
 * @param {string} prop
 * @param {string} expected
 * @returns {{ ok: boolean, winner: object|null, reason?: string }}
 */
export function assertCssVariable(cssTexts, prop, expected) {
  const all = []
  let base = 0
  for (const css of cssTexts ?? []) {
    const decls = collectDeclarations(css, prop, base)
    base += decls.length
    all.push(...decls)
  }
  const winner = winningDeclaration(all)
  if (!winner) {
    return { ok: false, winner: null, reason: `构建产物中未找到 ${prop} 的任何声明` }
  }
  const actual = normalizeCssValue(winner.value)
  const want = normalizeCssValue(expected)
  if (actual !== want) {
    return {
      ok: false,
      winner,
      reason: `${prop} 最终生效值为 ${winner.value}（来自选择器 "${winner.selector}"），期望 ${expected}`
    }
  }
  return { ok: true, winner }
}

/** 品牌色单一来源（与 theme-paper.css 的 --color-primary 一致） */
export const BRAND_PRIMARY = '#3e5c76'
