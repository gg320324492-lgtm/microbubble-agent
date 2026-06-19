/**
 * 化学式 / 单位 / 离子上下角标标准化
 *
 * 把论文正文中的 H2O2 / O3 / CO2 / mg·L-1 等普通文本
 * 转换为标准 Unicode 上下标格式 H₂O₂ / O₃ / CO₂ / mg·L⁻¹
 *
 * 设计原则：
 * - 只对明确的化学式 / 单位 / 离子模式生效，不误伤普通数字
 * - 用 Unicode 上下标字符（₀₁₂₃₄₅₆₇₈₉ / ⁰¹²³⁴⁵⁶⁷⁸⁹）而非 <sup>/<sub>
 *   避免破坏 HTML 结构
 */

// Unicode 下标字符映射
const SUB_DIGITS = { '0': '₀', '1': '₁', '2': '₂', '3': '₃', '4': '₄', '5': '₅', '6': '₆', '7': '₇', '8': '₈', '9': '₉' }
const SUP_DIGITS = { '0': '⁰', '1': '¹', '2': '²', '3': '³', '4': '⁴', '5': '⁵', '6': '⁶', '7': '⁷', '8': '⁸', '9': '⁹' }
const SUP_PLUS = '⁺'
const SUP_MINUS = '⁻'

function _toSub(num) {
  return String(num).split('').map(c => SUB_DIGITS[c] || c).join('')
}

function _toSup(num) {
  return String(num).split('').map(c => SUP_DIGITS[c] || c).join('')
}

// 常见化学式（精确匹配，避免误伤）
const EXACT_FORMULAS = [
  // 含数字下标的分子
  [/\bH2O2\b/g, 'H₂O₂'],
  [/\bH2O\b/g, 'H₂O'],
  [/\bO3\b/g, 'O₃'],
  [/\bCO2\b/g, 'CO₂'],
  [/\bSO2\b/g, 'SO₂'],
  [/\bNO2\b/g, 'NO₂'],
  [/\bNO3\b/g, 'NO₃'],
  [/\bNH3\b/g, 'NH₃'],
  [/\bNH4\b/g, 'NH₄'],
  [/\bCH4\b/g, 'CH₄'],
  [/\bC2H4\b/g, 'C₂H₄'],
  [/\bC2H6\b/g, 'C₂H₆'],
  [/\bC3H8\b/g, 'C₃H₈'],
  [/\bFe2O3\b/g, 'Fe₂O₃'],
  [/\bFe3O4\b/g, 'Fe₃O₄'],
  [/\bTiO2\b/g, 'TiO₂'],
  [/\bZnO\b/g, 'ZnO'],
  [/\bMnO2\b/g, 'MnO₂'],
  [/\bCaCO3\b/g, 'CaCO₃'],
  [/\bNaOH\b/g, 'NaOH'],
  [/\bH2SO4\b/g, 'H₂SO₄'],
  [/\bHNO3\b/g, 'HNO₃'],
  [/\bHCl\b/g, 'HCl'],
  [/\bKMnO4\b/g, 'KMnO₄'],
  [/\bNa2SO4\b/g, 'Na₂SO₄'],
  [/\bNaCl\b/g, 'NaCl'],
  [/\bBaSO4\b/g, 'BaSO₄'],
  [/\bAl2O3\b/g, 'Al₂O₃'],
  [/\bCr2O7\b/g, 'Cr₂O₇'],
  [/\bMgO\b/g, 'MgO'],
  [/\bCuO\b/g, 'CuO'],
  [/\bZnO\b/g, 'ZnO'],
  [/\bPbO2\b/g, 'PbO₂'],
  [/\bV2O5\b/g, 'V₂O₅'],
  [/\bWO3\b/g, 'WO₃'],
  [/\bCeO2\b/g, 'CeO₂'],
  [/\bBi2O3\b/g, 'Bi₂O₃'],
  [/\bAgBr\b/g, 'AgBr'],
  [/\bAgCl\b/g, 'AgCl'],
  // PM2.5
  [/\bPM2\.5\b/g, 'PM₂.₅'],
  [/\bPM10\b/g, 'PM₁₀'],
]

// 离子 / 自由基（上标电荷）
const ION_PATTERNS = [
  // ⋅OH / ·OH 自由基
  [/⋅OH\b/g, '⋅OH'],
  [/·OH\b/g, '·OH'],
  // O2⋅− / O2·- 自由基
  [/O2[⋅·][−-]/g, 'O₂⋅⁻'],
  // SO4^2- / SO42-
  [/SO4[²2][−-]/g, 'SO₄²⁻'],
  [/SO4[−-]/g, 'SO₄⁻'],
  // OH- / OH⁻
  [/\bOH[−-]\b/g, 'OH⁻'],
  // H+ / H⁺
  [/\bH[+＋]\b/g, 'H⁺'],
  // Fe3+ / Fe2+
  [/\bFe3[+＋]\b/g, 'Fe³⁺'],
  [/\bFe2[+＋]\b/g, 'Fe²⁺'],
  // Cu2+
  [/\bCu2[+＋]\b/g, 'Cu²⁺'],
  // Na+
  [/\bNa[+＋]\b/g, 'Na⁺'],
  // Ca2+
  [/\bCa2[+＋]\b/g, 'Ca²⁺'],
  // Mg2+
  [/\bMg2[+＋]\b/g, 'Mg²⁺'],
  // Cl-
  [/\bCl[−-]\b/g, 'Cl⁻'],
  // NO3-
  [/\bNO3[−-]\b/g, 'NO₃⁻'],
]

// 单位中的负指数（L-1 → L⁻¹, m3 → m³）
const UNIT_PATTERNS = [
  // mg·L-1 / mg/L-1 / mg L-1
  [/(mg|μg|ng|g|kg)\s*[·/·]\s*(L|mL|m3|cm3|L)-1/gi, (m, unit, base) => `${unit}·${base}⁻¹`],
  [/(mg|μg|ng|g|kg)\s+(L|mL|m3|cm3)-1/gi, (m, unit, base) => `${unit} ${base}⁻¹`],
  // mol·L-1 / mol/L
  [/(mol|mmol|μmol)\s*[·/·]\s*(L|mL)-1/gi, (m, unit, base) => `${unit}·${base}⁻¹`],
  // m3·h-1 / m3/h
  [/m3\s*[·/·]\s*h-1/g, 'm³·h⁻¹'],
  // 单独的 L-1 / m-1 / s-1（在单位上下文中）
  [/\b(L|m|s|h|min|mol|rad)-1\b/g, (m, base) => `${base}⁻¹`],
  [/\b(L|m|s|h|min|mol|rad)-2\b/g, (m, base) => `${base}⁻²`],
  [/\b(L|m|s|h|min|mol|rad)-3\b/g, (m, base) => `${base}⁻³`],
  // cm-1
  [/\bcm-1\b/g, 'cm⁻¹'],
  // m3（立方米）
  [/\bm3\b(?!\.\d)/g, 'm³'],
  // cm3
  [/\bcm3\b/g, 'cm³'],
  // dm3
  [/\bdm3\b/g, 'dm³'],
  // 科学计数 10-3 / 10^3 / x10^n
  [/\b10-(\d)\b/g, (m, n) => `10${_toSup('-' + n)}`],
  [/\b10\^(\d)\b/g, (m, n) => `10${_toSup(n)}`],
  [/[×xX]10-(\d)\b/g, (m, n) => `×10${_toSup('-' + n)}`],
  [/[×xX]10\^(\d)\b/g, (m, n) => `×10${_toSup(n)}`],
  // μg/L → μg·L
  [/μg\s*\/\s*L/g, 'μg·L'],
  // mg/L → mg·L
  [/mg\s*\/\s*L/g, 'mg·L'],
]

/**
 * 对一段文本做化学式/单位/离子上下角标标准化
 *
 * @param {string} text - 原始文本
 * @returns {string} - 标准化后的文本
 */
export function formatChemicalText(text) {
  if (!text) return ''
  let result = String(text)

  // 跳过已经是 HTML 标签内的内容（避免破坏 href / class 等属性）
  // 简单策略：只处理 > 和 < 之间的文本内容
  // 用 placeholder 保护 HTML 标签
  const tags = []
  result = result.replace(/<[^>]+>/g, (m) => {
    tags.push(m)
    return `__CHEM_TAG_${tags.length - 1}__`
  })

  // 1. 精确化学式（先匹配长的，避免 H2O 先匹配导致 H2O2 残留）
  for (const [re, replacement] of EXACT_FORMULAS) {
    result = result.replace(re, replacement)
  }

  // 2. 离子/自由基
  for (const [re, replacement] of ION_PATTERNS) {
    result = result.replace(re, replacement)
  }

  // 3. 单位
  for (const entry of UNIT_PATTERNS) {
    const [re, replacement] = entry
    result = result.replace(re, replacement)
  }

  // 恢复 HTML 标签
  result = result.replace(/__CHEM_TAG_(\d+)__/g, (m, i) => tags[parseInt(i)])

  return result
}
