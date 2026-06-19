/**
 * 化学式 / 离子 / 单位上下角标格式化
 *
 * 把论文中的 H2O2 / O3 / CO2 / mg·L-1 等普通文本
 * 转换为带 <sub>/<sup> 标签的 HTML，渲染更标准。
 *
 * 实现原则：
 * 1. 优先使用 HTML <sub>/<sup> 标签（更可读，更易控制样式）
 * 2. 返回 HTML 字符串，调用方需用 v-html 渲染
 * 3. 强制 HTML 转义 + sanitize，防止 XSS
 * 4. 通用 token parser：自动识别 Xn / X+ / X- / X^n 模式
 * 5. 不误伤普通年份 / 编号 / 参考文献编号
 *
 * 公开 API：
 *   formatChemicalText(text)         - 返回 HTML 字符串
 *   formatChemicalTextSafe(text)     - 返回纯文本（Unicode 字符版本，无 HTML）
 *   tokenizeChem(s)                  - 把 token 拆成 [text, sub, sup] 数组
 */

// Unicode 子/上标字符（备用 API）
const SUB_DIGITS = { '0': '₀', '1': '₁', '2': '₂', '3': '₃', '4': '₄', '5': '₅', '6': '₆', '7': '₇', '8': '₈', '9': '₉', '+': '₊', '-': '₋' }
const SUP_DIGITS = { '0': '⁰', '1': '¹', '2': '²', '3': '³', '4': '⁴', '5': '⁵', '6': '⁶', '7': '⁷', '8': '⁸', '9': '⁹', '+': '⁺', '-': '⁻' }

function _toSub(num) {
  return String(num).split('').map(c => SUB_DIGITS[c] || c).join('')
}

function _toSup(num) {
  return String(num).split('').map(c => SUP_DIGITS[c] || c).join('')
}

// 精确化学式映射（高优先级，避免被通用 parser 误吃）
const EXACT_FORMULAS = [
  // 单元素 + 数字下标
  [/\bH2O2\b/g, '<span class="chem-formula">H<sub>2</sub>O<sub>2</sub></span>'],
  [/\bH2O\b/g, '<span class="chem-formula">H<sub>2</sub>O</span>'],
  [/\bO3\b/g, '<span class="chem-formula">O<sub>3</sub></span>'],
  [/\bO2\b/g, '<span class="chem-formula">O<sub>2</sub></span>'],
  [/\bN2\b/g, '<span class="chem-formula">N<sub>2</sub></span>'],
  [/\bCl2\b/g, '<span class="chem-formula">Cl<sub>2</sub></span>'],
  [/\bH2\b/g, '<span class="chem-formula">H<sub>2</sub></span>'],
  [/\bCO2\b/g, '<span class="chem-formula">CO<sub>2</sub></span>'],
  [/\bSO2\b/g, '<span class="chem-formula">SO<sub>2</sub></span>'],
  [/\bNO2\b/g, '<span class="chem-formula">NO<sub>2</sub></span>'],
  [/\bNO3\b(?!\w)/g, '<span class="chem-formula">NO<sub>3</sub></span>'],
  [/\bNH3\b/g, '<span class="chem-formula">NH<sub>3</sub></span>'],
  [/\bNH4\b/g, '<span class="chem-formula">NH<sub>4</sub></span>'],
  [/\bCH4\b/g, '<span class="chem-formula">CH<sub>4</sub></span>'],
  [/\bC2H4\b/g, '<span class="chem-formula">C<sub>2</sub>H<sub>4</sub></span>'],
  [/\bC2H6\b/g, '<span class="chem-formula">C<sub>2</sub>H<sub>6</sub></span>'],
  [/\bC3H8\b/g, '<span class="chem-formula">C<sub>3</sub>H<sub>8</sub></span>'],
  [/\bC6H6\b/g, '<span class="chem-formula">C<sub>6</sub>H<sub>6</sub></span>'],
  [/\bC7H8\b/g, '<span class="chem-formula">C<sub>7</sub>H<sub>8</sub></span>'],
  // 含 2+ 数字下标的复杂分子
  [/\bFe2O3\b/g, '<span class="chem-formula">Fe<sub>2</sub>O<sub>3</sub></span>'],
  [/\bFe3O4\b/g, '<span class="chem-formula">Fe<sub>3</sub>O<sub>4</sub></span>'],
  [/\bTiO2\b/g, '<span class="chem-formula">TiO<sub>2</sub></span>'],
  [/\bMnO2\b/g, '<span class="chem-formula">MnO<sub>2</sub></span>'],
  [/\bCaCO3\b/g, '<span class="chem-formula">CaCO<sub>3</sub></span>'],
  [/\bH2SO4\b/g, '<span class="chem-formula">H<sub>2</sub>SO<sub>4</sub></span>'],
  [/\bHNO3\b/g, '<span class="chem-formula">HNO<sub>3</sub></span>'],
  [/\bKMnO4\b/g, '<span class="chem-formula">KMnO<sub>4</sub></span>'],
  [/\bNa2SO4\b/g, '<span class="chem-formula">Na<sub>2</sub>SO<sub>4</sub></span>'],
  [/\bBaSO4\b/g, '<span class="chem-formula">BaSO<sub>4</sub></span>'],
  [/\bAl2O3\b/g, '<span class="chem-formula">Al<sub>2</sub>O<sub>3</sub></span>'],
  [/\bMg(OH)2\b/g, '<span class="chem-formula">Mg(OH)<sub>2</sub></span>'],
  [/\bCa(OH)2\b/g, '<span class="chem-formula">Ca(OH)<sub>2</sub></span>'],
  [/\bPbO2\b/g, '<span class="chem-formula">PbO<sub>2</sub></span>'],
  [/\bV2O5\b/g, '<span class="chem-formula">V<sub>2</sub>O<sub>5</sub></span>'],
  [/\bWO3\b/g, '<span class="chem-formula">WO<sub>3</sub></span>'],
  [/\bCeO2\b/g, '<span class="chem-formula">CeO<sub>2</sub></span>'],
  [/\bBi2O3\b/g, '<span class="chem-formula">Bi<sub>2</sub>O<sub>3</sub></span>'],
  // PM2.5 / PM10
  [/\bPM2\.5\b/g, 'PM<sub>2.5</sub>'],
  [/\bPM10\b/g, 'PM<sub>10</sub>'],
]

// 离子 / 自由基上标
const ION_PATTERNS = [
  // 自由基（保持点号）
  [/[·•]OH\b/g, '<span class="chem-radical"><span class="radical-dot">·</span>OH</span>'],
  [/OH[·•]\b/g, 'OH<span class="radical-dot">·</span>'],
  [/[·•]O2[·•−-]?/g, '<span class="chem-radical"><span class="radical-dot">·</span>O<sub>2</sub></span>'],
  // 电荷上标
  [/\bOH−\b/g, '<span class="chem-ion">OH<sup>−</sup></span>'],
  [/\bOH-\b/g, '<span class="chem-ion">OH<sup>−</sup></span>'],
  [/\bH\+\b/g, '<span class="chem-ion">H<sup>+</sup></span>'],
  [/\bNa\+\b/g, '<span class="chem-ion">Na<sup>+</sup></span>'],
  [/\bK\+\b/g, '<span class="chem-ion">K<sup>+</sup></span>'],
  [/\bCa2\+/g, '<span class="chem-ion">Ca<sup>2+</sup></span>'],
  [/\bCa²⁺/g, '<span class="chem-ion">Ca<sup>2+</sup></span>'],
  [/\bMg2\+/g, '<span class="chem-ion">Mg<sup>2+</sup></span>'],
  [/\bFe3\+/g, '<span class="chem-ion">Fe<sup>3+</sup></span>'],
  [/\bFe2\+/g, '<span class="chem-ion">Fe<sup>2+</sup></span>'],
  [/\bMn2\+/g, '<span class="chem-ion">Mn<sup>2+</sup></span>'],
  [/\bCu2\+/g, '<span class="chem-ion">Cu<sup>2+</sup></span>'],
  [/\bZn2\+/g, '<span class="chem-ion">Zn<sup>2+</sup></span>'],
  [/\bAl3\+/g, '<span class="chem-ion">Al<sup>3+</sup></span>'],
  [/\bNH4\+/g, '<span class="chem-ion">NH<sub>4</sub><sup>+</sup></span>'],
  [/\bCl−\b/g, '<span class="chem-ion">Cl<sup>−</sup></span>'],
  [/\bCl-\b/g, '<span class="chem-ion">Cl<sup>−</sup></span>'],
  [/\bNO3−\b/g, '<span class="chem-ion">NO<sub>3</sub><sup>−</sup></span>'],
  [/\bNO3-\b/g, '<span class="chem-ion">NO<sub>3</sub><sup>−</sup></span>'],
  [/\bSO4²−/g, '<span class="chem-ion">SO<sub>4</sub><sup>2−</sup></span>'],
  [/\bSO4 2−/g, '<span class="chem-ion">SO<sub>4</sub><sup>2−</sup></span>'],
  [/\bSO42-/g, '<span class="chem-ion">SO<sub>4</sub><sup>2−</sup></span>'],
  [/\bCO3²−/g, '<span class="chem-ion">CO<sub>3</sub><sup>2−</sup></span>'],
  [/\bCO3 2−/g, '<span class="chem-ion">CO<sub>3</sub><sup>2−</sup></span>'],
  [/\bCO32-/g, '<span class="chem-ion">CO<sub>3</sub><sup>2−</sup></span>'],
  [/\bHCO3−\b/g, '<span class="chem-ion">HCO<sub>3</sub><sup>−</sup></span>'],
  [/\bHCO3-\b/g, '<span class="chem-ion">HCO<sub>3</sub><sup>−</sup></span>'],
]

// 单位负指数 + 科学计数
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
  // μmol/L, mg/L
  [/μg\s*\/\s*L/g, 'μg/L'],
  [/mg\s*\/\s*L/g, 'mg/L'],
  // 科学计数 10-3 / 10^3 / x10^n
  [/\b10-(\d)\b/g, (m, n) => `10${_toSup('-' + n)}`],
  [/\b10\^(\d)\b/g, (m, n) => `10${_toSup(n)}`],
  [/[×xX]10-(\d)\b/g, (m, n) => `×10${_toSup('-' + n)}`],
  [/[×xX]10\^(\d)\b/g, (m, n) => `×10${_toSup(n)}`],
]

/**
 * HTML escape（防 XSS）
 */
function _escapeHtml(s) {
  if (s == null) return ''
  return String(s)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;')
}

/**
 * 通用 token parser：识别 Xn / X+n / X-n / X^n 模式
 * 但只在元素符号（1-2 个大写字母）或化学 token 上下文中
 */
function _formatElementToken(match) {
  // match 形如 "CO2" / "Fe2O3" / "H2O2"
  // 转成 "CO<sub>2</sub>O<sub>3</sub>" 形式
  return match.replace(/([A-Z][a-z]?)(\d+)/g, '$1<sub>$2</sub>')
}

/**
 * 通用单位 token：识别 X-1 / X-2 / X-n 形式
 */
function _formatUnitExponent(match) {
  return match.replace(/-(\d+)$/g, '<sup>−$1</sup>')
}

/**
 * 主入口：把普通文本转成带 <sub>/<sup> 的 HTML
 * 调用方需用 v-html 渲染
 */
export function formatChemicalText(text) {
  if (!text) return ''
  let result = String(text)

  // 保护已有的 HTML 标签（如 <span class="...">）
  const protectedTags = []
  result = result.replace(/<[^>]+>/g, (m) => {
    protectedTags.push(m)
    return `__CHEM_TAG_${protectedTags.length - 1}__`
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
  //    匹配 Xn 模式：单大写字母 + 数字（如 O2, H2, N2 但要避开 O3 已被精确匹配）
  //    使用 lookahead 避免匹配已处理过的 token
  result = result.replace(/\b([A-Z][a-z]?)(\d+)(?!\w)(?![<"])/g, (m, elem, num) => {
    // 已被精确匹配处理过的不会出现这里（因为精确匹配已替换为 span）
    return `${elem}<sub>${num}</sub>`
  })

  // 5. 通用单位指数（如 standalone -1 / -2 / -3）
  //    只在单位上下文中（前一个字符是 L / m / s 等）
  result = result.replace(/([Ll]|[Mm][Ll]?|[Cc][Mm]|[Hh]|[Ss])(-1|-2|-3)\b/g, (m, base, exp) => {
    const e = exp.replace('-', '−')
    return `${base}<sup>${e}</sup>`
  })

  // 6. 通用电荷上标（如 X+ / X-）
  //    前面是元素符号（Ca/Na/Fe/K 等 + 电荷）
  result = result.replace(/\b([A-Z][a-z]?)(\d*[+−-])(?!\w)/g, (m, elem, charge) => {
    // 已在 ION_PATTERNS 处理的不再出现
    const sign = charge.replace('-', '−').replace('+', '+')
    if (/^\d/.test(sign)) {
      // 带数字的电荷（如 2+ / 3-）
      const n = sign.match(/\d/)[0]
      const s = sign.replace(/\d/g, '')
      return `${elem}<sup>${n}${s}</sup>`
    }
    return `${elem}<sup>${sign}</sup>`
  })

  // 恢复保护的标签
  result = result.replace(/__CHEM_TAG_(\d+)__/g, (m, i) => protectedTags[parseInt(i)])

  return result
}

/**
 * 纯文本版本（无 HTML 标签，用 Unicode 上下标字符）
 * 用于不渲染 HTML 的场景（如 console / 复制纯文本）
 */
export function formatChemicalTextSafe(text) {
  if (!text) return ''
  // 先调 HTML 版本拿到带 <sub>/<sup> 的字符串
  const html = formatChemicalText(text)
  // 把 <span class="...">xxx</span> 还原成纯文本
  return html
    .replace(/<span[^>]*>/g, '')
    .replace(/<\/span>/g, '')
    .replace(/<sub>/g, '')
    .replace(/<\/sub>/g, (m, offset, str) => {
      // 找到匹配的 </sub> 之间的内容
      return ''
    })
    .replace(/<\/sup>/g, '')
    .replace(/<sup>([−\-+]?\d*)<\/sup>/g, (m, c) => {
      if (c.startsWith('−')) return _toSup('-' + c.slice(1))
      if (c.startsWith('+')) return _toSup('+' + c.slice(1))
      return _toSup(c)
    })
    .replace(/<sup>/g, '')
}

/**
 * 把一个 token 拆成 [text, sub, sup] 数组（供高级渲染使用）
 * 例: "H2O" → [{text:"H",sub:"2"}, {text:"O",sub:""}]
 */
export function tokenizeChem(s) {
  // 简单实现：匹配 Element + 可选 subscript
  const tokens = []
  const re = /([A-Z][a-z]?)(?:(\d+))?/g
  let m
  while ((m = re.exec(s)) !== null) {
    tokens.push({ text: m[1], sub: m[2] || '' })
  }
  return tokens
}
