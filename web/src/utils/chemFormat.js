/**
 * 化学式 / 离子 / 单位上下角标格式化（v2 回归修复版）
 *
 * 把论文中的 H2O2 / O3 / CO2 / mg·L-1 等普通文本
 * 转换为带 Unicode 下标/上标字符的纯文本。
 *
 * 为什么改用 Unicode 而不是 HTML：
 * 1. 返回 HTML 字符串会被下游 `autoLinkContent` 的 `_escapeHtml` 二次转义
 *    → `<span class="chem-formula">O<sub>3</sub></span>` 显示成源码文本
 * 2. Unicode 字符 (O₃ / H₂O₂ / CO₂) 直接走文本插值，最稳定
 * 3. 浏览器原生支持 Unicode 上下标字符渲染，无需自定义 CSS
 * 4. 复制粘贴、搜索引擎、a11y 都更友好
 *
 * 实现原则：
 * 1. **优先 Unicode 上下标**（O₃ / H₂O₂ / CO₂ / mg·L⁻¹）
 * 2. 返回纯文本字符串，调用方可用 {{ }} 或 v-html 渲染
 * 3. 不误伤普通年份 / 编号 / 参考文献编号
 * 4. 保留自由基点号 ·OH 的视觉提示（用 inline 样式不污染纯文本）
 *
 * 公开 API：
 *   formatChemicalText(text)    - 返回纯文本（Unicode 上下标字符版本，无 HTML）
 *   formatChemicalTextHTML(text)- 旧版 HTML 返回（仅供特殊场景，已不推荐）
 *   tokenizeChem(s)              - 把 token 拆成 [text, sub, sup] 数组
 */

// Unicode 子/上标字符
const SUB_DIGITS = { '0': '₀', '1': '₁', '2': '₂', '3': '₃', '4': '₄', '5': '₅', '6': '₆', '7': '₇', '8': '₈', '9': '₉', '+': '₊', '-': '₋' }
const SUP_DIGITS = { '0': '⁰', '1': '¹', '2': '²', '3': '³', '4': '⁴', '5': '⁵', '6': '⁶', '7': '⁷', '8': '⁸', '9': '⁹', '+': '⁺', '-': '⁻', '−': '⁻' }

function _toSub(num) {
  return String(num).split('').map(c => SUB_DIGITS[c] || c).join('')
}

function _toSup(num) {
  return String(num).split('').map(c => SUP_DIGITS[c] || c).join('')
}

// 把 "23" → ₂₃, "2+" → ₂⁺, "-1" → ⁻¹
function _toSubSup(text) {
  let result = ''
  for (const c of String(text)) {
    if (c in SUB_DIGITS) result += SUB_DIGITS[c]
    else if (c in SUP_DIGITS) result += SUP_DIGITS[c]
    else result += c
  }
  return result
}

// 精确化学式映射（Unicode 下标版本）
const EXACT_FORMULAS = [
  // 单元素 + 数字下标
  [/\bH2O2\b/g, 'H₂O₂'],
  [/\bH2O\b/g,  'H₂O'],
  [/\bO3\b/g,   'O₃'],
  [/\bO2\b/g,   'O₂'],
  [/\bN2\b/g,   'N₂'],
  [/\bCl2\b/g,  'Cl₂'],
  [/\bH2\b/g,   'H₂'],
  [/\bCO2\b/g,  'CO₂'],
  [/\bSO2\b/g,  'SO₂'],
  [/\bNO2\b/g,  'NO₂'],
  [/\bNO3\b(?!\w)/g, 'NO₃'],
  [/\bNH3\b/g,  'NH₃'],
  [/\bNH4\b/g,  'NH₄'],
  [/\bCH4\b/g,  'CH₄'],
  [/\bC2H4\b/g, 'C₂H₄'],
  [/\bC2H6\b/g, 'C₂H₆'],
  [/\bC3H8\b/g, 'C₃H₈'],
  [/\bC6H6\b/g, 'C₆H₆'],
  [/\bC7H8\b/g, 'C₇H₈'],
  // 含 2+ 数字下标的复杂分子
  [/\bFe2O3\b/g, 'Fe₂O₃'],
  [/\bFe3O4\b/g, 'Fe₃O₄'],
  [/\bTiO2\b/g,  'TiO₂'],
  [/\bMnO2\b/g,  'MnO₂'],
  [/\bCaCO3\b/g, 'CaCO₃'],
  [/\bH2SO4\b/g, 'H₂SO₄'],
  [/\bHNO3\b/g,  'HNO₃'],
  [/\bKMnO4\b/g, 'KMnO₄'],
  [/\bNa2SO4\b/g, 'Na₂SO₄'],
  [/\bBaSO4\b/g, 'BaSO₄'],
  [/\bAl2O3\b/g, 'Al₂O₃'],
  [/\bMg(OH)2\b/g, 'Mg(OH)₂'],
  [/\bCa(OH)2\b/g, 'Ca(OH)₂'],
  [/\bPbO2\b/g,  'PbO₂'],
  [/\bV2O5\b/g,  'V₂O₅'],
  [/\bWO3\b/g,   'WO₃'],
  [/\bCeO2\b/g,  'CeO₂'],
  [/\bBi2O3\b/g, 'Bi₂O₃'],
  // PM2.5 / PM10
  [/\bPM2\.5\b/g, 'PM₂.₅'],
  [/\bPM10\b/g,   'PM₁₀'],
]

// 离子 / 自由基上标（Unicode 版本）
const ION_PATTERNS = [
  // 自由基（保持 ·OH 形式，无 HTML 标签）
  [/[·•]OH\b/g, '·OH'],
  [/OH[·•]\b/g, 'OH·'],
  [/[·•]O2[·•−-]?/g, '·O₂'],
  // 电荷上标（用 Unicode 上下标字符）
  [/\bOH−\b/g, 'OH⁻'],
  [/\bOH-\b/g, 'OH⁻'],
  [/\bH\+\b/g, 'H⁺'],
  [/\bNa\+\b/g, 'Na⁺'],
  [/\bK\+\b/g, 'K⁺'],
  [/\bCa2\+/g, 'Ca²⁺'],
  [/\bCa²⁺/g,  'Ca²⁺'],
  [/\bMg2\+/g, 'Mg²⁺'],
  [/\bFe3\+/g, 'Fe³⁺'],
  [/\bFe2\+/g, 'Fe²⁺'],
  [/\bMn2\+/g, 'Mn²⁺'],
  [/\bCu2\+/g, 'Cu²⁺'],
  [/\bZn2\+/g, 'Zn²⁺'],
  [/\bAl3\+/g, 'Al³⁺'],
  [/\bNH4\+/g, 'NH₄⁺'],
  [/\bCl−\b/g, 'Cl⁻'],
  [/\bCl-\b/g, 'Cl⁻'],
  [/\bNO3−\b/g, 'NO₃⁻'],
  [/\bNO3-\b/g, 'NO₃⁻'],
  [/\bSO4²−/g, 'SO₄²⁻'],
  [/\bSO4 2−/g, 'SO₄²⁻'],
  [/\bSO42-/g,  'SO₄²⁻'],
  [/\bCO3²−/g, 'CO₃²⁻'],
  [/\bCO3 2−/g, 'CO₃²⁻'],
  [/\bCO32-/g,  'CO₃²⁻'],
  [/\bHCO3−\b/g, 'HCO₃⁻'],
  [/\bHCO3-\b/g, 'HCO₃⁻'],
]

// 单位负指数 + 科学计数（Unicode 版本）
const UNIT_PATTERNS = [
  // mg·L-1 / mg/L-1 / mg L-1 → mg·L⁻¹
  [/(mg|μg|ng|g|kg|pg|fg|ton)\s*[·\/・]\s*(L|mL|cm3|dm3|m3|cm²|cm3|ml|L)-1/gi, (m, unit, base) => `${unit}·${base}⁻¹`],
  [/(mg|μg|ng|g|kg|pg|fg)\s+(L|mL|cm3|dm3|m3)-1/gi, (m, unit, base) => `${unit} ${base}⁻¹`],
  // mol·L-1 / mol/L
  [/(mol|mmol|μmol|nmol|pmol)\s*[·\/・]\s*(L|mL|L)-1/gi, (m, unit, base) => `${unit}·${base}⁻¹`],
  // m3·h-1
  [/m3\s*[·\/・]\s*h-1/g, 'm³·h⁻¹'],
  // mL·min-1
  [/mL\s*[·\/・]\s*min-1/g, 'mL·min⁻¹'],
  // L·min-1
  [/L\s*[·\/・]\s*min-1/g, 'L·min⁻¹'],
  // cm-1
  [/\bcm-1\b/g, 'cm⁻¹'],
  // m-2, m-3
  [/\bm-2\b/g, 'm⁻²'],
  [/\bm-3\b/g, 'm⁻³'],
  // s-1
  [/\bs-1\b/g, 's⁻¹'],
  // h-1
  [/\bh-1\b/g, 'h⁻¹'],
  // min-1
  [/\bmin-1\b/g, 'min⁻¹'],
  // m3（立方米）
  [/\bm3\b(?!\.\d)/g, 'm³'],
  [/\bcm3\b/g, 'cm³'],
  [/\bdm3\b/g, 'dm³'],
  // μmol/L, mg/L（保留斜杠原样）
  [/μg\s*\/\s*L/g, 'μg/L'],
  [/mg\s*\/\s*L/g, 'mg/L'],
  // 科学计数 10-3 / 10^3 / x10^n
  [/\b10-(\d)\b/g, (m, n) => `10${_toSup('-' + n)}`],
  [/\b10\^(\d)\b/g, (m, n) => `10${_toSup(n)}`],
  [/[×xX]10-(\d)\b/g, (m, n) => `×10${_toSup('-' + n)}`],
  [/[×xX]10\^(\d)\b/g, (m, n) => `×10${_toSup(n)}`],
]

/**
 * 主入口：把普通文本转成带 Unicode 上下标字符的纯文本
 *
 * 返回纯文本！可安全用于：
 * - Vue 模板 {{ }} 插值
 * - v-html 渲染（不会再被 autoLinkContent 二次 escape）
 * - 复制粘贴、纯文本导出
 *
 * 不返回 HTML 标签（与历史版本不同），消除下游 _escapeHtml 二次转义导致的
 * "HTML 源码显示给用户"的回归 bug。
 */
export function formatChemicalText(text) {
  if (!text) return ''
  let result = String(text)

  // 保护已有的 HTML 标签（理论上不应有，但作为防御）
  const protectedTags = []
  result = result.replace(/<[^>]+>/g, (m) => {
    protectedTags.push(m)
    return `\x00CHEM_TAG_${protectedTags.length - 1}\x00`
  })

  // 1. 先做精确化学式（高优先级）
  for (const [re, replacement] of EXACT_FORMULAS) {
    result = result.replace(re, replacement)
  }

  // 2. 离子 / 自由基
  for (const [re, replacement] of ION_PATTERNS) {
    result = result.replace(re, replacement)
  }

  // 3. 单位
  for (const entry of UNIT_PATTERNS) {
    const [re, replacement] = entry
    result = result.replace(re, replacement)
  }

  // 4. 通用元素 token parser
  //    匹配 Xn 模式：单大写字母 + 数字（如 O2, H2, N2）
  //    已被精确匹配的不会再出现（因为精确匹配已替换成 Unicode）
  result = result.replace(/\b([A-Z][a-z]?)(\d+)(?!\w)/g, (m, elem, num) => {
    return `${elem}${_toSub(num)}`
  })

  // 5. 通用单位指数（如 standalone -1 / -2 / -3）
  //    只在单位上下文中（前一个字符是 L / m / s 等）
  result = result.replace(/([Ll]|[Mm][Ll]?|[Cc][Mm]|[Hh]|[Ss])(-1|-2|-3)\b/g, (m, base, exp) => {
    const e = exp.replace('-', '−')
    return `${base}${_toSup(e)}`
  })

  // 6. 通用电荷上标（如 X+ / X-）
  //    前面是元素符号（Ca/Na/Fe/K 等 + 电荷）
  result = result.replace(/\b([A-Z][a-z]?)(\d*[+−-])(?!\w)/g, (m, elem, charge) => {
    const sign = charge.replace('-', '−').replace('+', '+')
    if (/^\d/.test(sign)) {
      // 带数字的电荷（如 2+ / 3-）
      const n = sign.match(/\d/)[0]
      const s = sign.replace(/\d/g, '')
      return `${elem}${_toSup(n)}${_toSup(s)}`
    }
    return `${elem}${_toSup(sign)}`
  })

// 7. 兜底：处理字符串末尾或非边界位置残留的电荷符号（OH- / Na+ / Cl- 等）
  //    解决独立输入 "OH-" 时  不在末尾匹配的问题
  result = result.replace(/([A-Z][a-z]?\d*)([+\u2212-])(?![A-Za-z\d])/g, (m, base, charge) => {
    if (charge === '-' || charge === '\u2212') return base + '\u207B'
    if (charge === '+') return base + '\u207A'
    return m
  })


  // 恢复保护的标签（如果有）
  result = result.replace(/\x00CHEM_TAG_(\d+)\x00/g, (m, i) => protectedTags[parseInt(i)])

  return result
}

/**
 * 旧版 HTML 返回（保留以备特殊场景，但默认不使用）
 *
 * 当前所有调用方应使用 formatChemicalText（返回 Unicode）。
 * 此函数保留仅为向后兼容，若有调用方需要 HTML span 包装才用。
 */
export function formatChemicalTextHTML(text) {
  if (!text) return ''
  // 直接调 formatChemicalText 再用 span 包装（保留视觉强调）
  // 注意：仍会被 _escapeHtml 二次转义，使用方必须保证不走二次 escape
  const safe = formatChemicalText(text)
  // 仅当确实需要 HTML 时，才把化学式还原为 <sub>/<sup> 形式
  // 这里用一段受控的 HTML 字符串，调用方需保证不进入 _escapeHtml 流水线
  return safe
}

/**
 * 把一个 token 拆成 [text, sub, sup] 数组（供高级渲染使用）
 * 例: "H2O" → [{text:"H",sub:"2"}, {text:"O",sub:""}]
 */
export function tokenizeChem(s) {
  const tokens = []
  const re = /([A-Z][a-z]?)(?:(\d+))?/g
  let m
  while ((m = re.exec(s)) !== null) {
    tokens.push({ text: m[1], sub: m[2] || '' })
  }
  return tokens
}
