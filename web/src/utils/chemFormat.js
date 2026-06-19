/**
 * 统一科学文本格式化器 (v3 — 通用 parser 版)
 *
 * 不再"发现一个加一个映射"。所有规则走底层通用 parser：
 * - 公式 (formula)     : 元素符号 + 数字 → 下标 (O3 → O₃, H2O2 → H₂O₂)
 * - 单位指数 (unit)     : 已知单位 + -1/-2/-3 → 上标 (L·h-1 → L·h⁻¹)
 * - 离子电荷 (charge)   : 元素 + +/- → 上标 (OH- → OH⁻, Fe3+ → Fe³⁺)
 * - 自由基 (radical)    : ·OH / •OH / O2·- → 保留点号视觉提示
 * - 体积立方 (vol-cubic): m3 → m³ (OCR 误识别修复)
 * - 科学计数 (sci-not)  : ×10-3 → ×10⁻³
 *
 * 设计原则：
 * 1. **不返回 HTML 标签**（v26 修复：避免下游 _escapeHtml 二次转义）
 * 2. **输出 Unicode 字符**（O₃ / H₂O₂ / OH⁻ / mg·L⁻¹ / ²³⁺）
 * 3. **不误伤**：年份 (2026) / 页码 / Fig. N / Table N / DOI / [1] / 普通英文
 * 4. **可顺序调用**：formatScientificText 内部按特定顺序调用 4 个子函数
 *
 * 公开 API:
 *   formatScientificText(text)              - 一站式入口（论文正文用）
 *   formatChemicalFormula(text)             - 仅化学式
 *   formatUnitExponent(text)                - 仅单位指数
 *   formatIonCharge(text)                   - 仅离子电荷
 *   formatRadicals(text)                    - 仅自由基
 *   formatChemicalText(text) [兼容旧 API]    - = formatScientificText
 */

// ============================================================
// Unicode 子/上标字符表
// ============================================================

const SUB_DIGITS = { '0': '₀', '1': '₁', '2': '₂', '3': '₃', '4': '₄', '5': '₅', '6': '₆', '7': '₇', '8': '₈', '9': '₉', '+': '₊', '-': '₋' }
const SUP_DIGITS = { '0': '⁰', '1': '¹', '2': '²', '3': '³', '4': '⁴', '5': '⁵', '6': '⁶', '7': '⁷', '8': '⁸', '9': '⁹', '+': '⁺', '-': '⁻', '−': '⁻' }

function _toSub(num) {
  return String(num).split('').map(c => SUB_DIGITS[c] || c).join('')
}

function _toSup(num) {
  return String(num).split('').map(c => SUP_DIGITS[c] || c).join('')
}

function _toSubSup(text) {
  let result = ''
  for (const c of String(text)) {
    if (c in SUB_DIGITS) result += SUB_DIGITS[c]
    else if (c in SUP_DIGITS) result += SUP_DIGITS[c]
    else result += c
  }
  return result
}

// ============================================================
// 已知单位白名单（用于单位指数识别）
// ============================================================

const LENGTH_UNITS = ['m', 'cm', 'mm', 'km', 'dm', 'μm', 'nm', 'pm', 'Å']
const VOLUME_UNITS = ['L', 'mL', 'μL', 'nL', 'kL']
const MASS_UNITS = ['g', 'kg', 'mg', 'μg', 'ng', 'pg']
const TIME_UNITS = ['s', 'min', 'h', 'ms', 'μs', 'ns']
const AMOUNT_UNITS = ['mol', 'mmol', 'μmol', 'nmol', 'pmol']
const CONC_UNITS = ['M', 'mM', 'μM', 'nM']

const ALL_UNITS = [
  ...VOLUME_UNITS, ...LENGTH_UNITS, ...MASS_UNITS,
  ...TIME_UNITS, ...AMOUNT_UNITS, ...CONC_UNITS,
]
// 按长度倒序排，贪婪匹配（"mL" 优先于 "L"，"mmol" 优先于 "mol"）
ALL_UNITS.sort((a, b) => b.length - a.length)

// 单位指数中的"基础量"（指数前可出现的单位；不含指数本身）
const UNIT_BASE_GROUP = `(?:${ALL_UNITS.join('|')})`
const UNIT_EXP_NUMBER = '(-1|-2|-3|-¹|-²|-³)'

// ============================================================
// 1. 化学式自动识别 (formula → subscript)
// ============================================================

/**
 * 通用公式正则:
 *   - 必须以 [A-Z][a-z]? 开头（化学元素符号）
 *   - 可选紧跟数字（原子数 → 下标）
 *   - 后面可继续接 [A-Z][a-z]?\d* 块（多元素连续）
 *   - 边界：左边不能是字母/数字（避免误伤连续字母），右边不能是小写字母（避免截断 2 字符元素符号）
 *
 * 匹配:
 *   O3 / H2O2 / Co3O4 / Fe2O3 / MnO2 / CaCO3 / NH4+
 *   O3-MNBs / O3/H2O2 / H2O2+N2
 *
 * 不匹配:
 *   2026 / 2.1 / Fig.2 / Table3 / DOI:10.xxx / [12]
 *   段首 "C"（罗马数字？本 parser 不强制过滤，靠 lookahead 边界）
 */

// 单元匹配：Element + 数字（不含 groups）
// group 形式：(FORMULA_GROUP)NUMBER，组内允许多元素 (OH) / (SO4) / (CO3) / (NH4)
const FORMULA_GROUP_RE = /\(((?:[A-Z][a-z]?\d*)+)\)(\d+)(?![A-Za-z\d])/g

// 主公式正则：连续 Element + 数字
// Lookahead `(?![a-z\d])`: 拒绝小写字母或数字，但允许大写字母（表示下一个元素）
// Lookbehind `(?<!\d)`: 只拒绝前面是数字（避免截断 "123CO2" 这种）
//   注意：不能拒绝字母（否则 "CO2" 中 O 前面是 C，lookbehind 会拒绝 O2）
const FORMULA_RE = /(?<!\d)([A-Z][a-z]?\d+(?:[A-Z][a-z]?\d+)*)(?![a-z\d])/g

function _formatFormulaSegment(seg) {
  // seg 是像 "H2O2" "Co3O4" "CaCO3" 的连续元素+数字串
  // 在内部继续拆 Element + Digit 对
  return seg.replace(/([A-Z][a-z]?)(\d+)/g, (_m, elem, num) => {
    return elem + _toSub(num)
  })
}

function formatChemicalFormula(text) {
  if (!text) return ''
  let result = String(text)

  // 先处理 (group)N 模式 (e.g. (OH)2 → (OH)₂)
  result = result.replace(FORMULA_GROUP_RE, (_m, group, num) => {
    return `(${_formatFormulaSegment(group)})${_toSub(num)}`
  })

  // 然后处理连续的 Element+Digit 块
  // 用一个更复杂的正则匹配"完整的连续公式段"
  result = result.replace(
    FORMULA_RE,
    (_m, seg) => _formatFormulaSegment(seg)
  )

  return result
}

// ============================================================
// 2. 单位指数自动识别 (unit exponent → superscript)
// ============================================================

/**
 * 通用单位指数正则:
 *   模式: <unit>(<sep>?<unit>?)(-1|-2|-3)
 *   其中 unit 必须在白名单中
 *
 * 匹配:
 *   L·h-1 / mL·min-1 / mg·L-1 / m3·h-1
 *   cm-1 / s-1 / min-1 / h-1
 *   200 L·h-1 / 100 mL·min-1
 *
 * 不匹配:
 *   Page-1 (P 不是单位)
 *   2-1 (数字开头不是元素符号)
 *   Fig-2 / Table-3 (特殊前缀)
 */

// 把单位列表转义用于正则
const UNIT_GROUP = ALL_UNITS.map(u => u.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')).join('|')

// 单位指数主正则: 单位 (可选分隔符 + 可选单位) + 负指数
// 关键: -N 必须是真正的负指数 (-1/-2/-3)，前面跟单位
const UNIT_EXP_RE = new RegExp(
  // 1. 主单位 (不贪婪，避免多匹配)
  `(${UNIT_GROUP})` +
  // 2. 可选分隔符 (· / ・ / / / space)
  `(?:[·／・\\s]+)?` +
  // 3. 可选基础单位 (e.g. h-1, L-1)
  `(?:(${UNIT_GROUP})(?:[·／・\\s]+))?` +
  // 4. 负指数（必须 -1/-2/-3 或 Unicode 上标）
  `(-1|-2|-3|-¹|-²|-³)` +
  // 5. 边界: 后面不能是数字或连字符（避免误吃 -10 中的 -1）
  `(?![-\\d])`,
  'g'
)

function formatUnitExponent(text) {
  if (!text) return ''
  let result = String(text)

  // 第一步: 体积立方 m3 → m³ / cm3 → cm³ (在单位指数处理之前)
  result = result.replace(
    /\b(m|cm|mm|km|dm|μm|nm)(3)(?![A-Za-z\d])/g,
    (_m, prefix, _three) => prefix + '³'
  )

  // 第二步: 单位指数 -1/-2/-3 → ⁻¹/⁻²/⁻³
  // Unicode 上标 ⁻¹/⁻²/⁻³ 直接透传，避免重复转换
  result = result.replace(UNIT_EXP_RE, (_m, unit1, unit2, exp) => {
    const expSup = exp.startsWith('-')
      ? '⁻' + _toSup(exp.slice(1))
      : _toSup(exp)
    if (unit2) {
      return `${unit1}${unit2}${expSup}`
    }
    return `${unit1}${expSup}`
  })

  return result
}

// ============================================================
// 3. 离子与电荷自动识别 (charge → superscript)
// ============================================================

/**
 * 通用离子电荷正则:
 *   模式: (<formula>)(<charge_num>?)(+/-)
 *   charge_num 是 superscript（电荷数）
 *   formula 部分已被 _formatFormulaSegment 处理（原子数 subscript）
 *
 * 关键: 区分电荷 "-" 与连接符 "-"
 *   电荷: 元素/公式 + 末尾 + (Na+, OH-, CO3 2-, SO42-, Fe3+)
 *   连接符: 公式 + - + 大写词 (O3-MNBs, CO3-MNBs)
 *
 * 区分方法: lookahead 必须是"非字母数字"
 *   电荷: 后跟空白/标点/字符串末尾
 *   连接符: 后跟大写字母 (新词)
 *
 * 匹配:
 *   H+ / Na+ / K+ / OH- / HCO3-
 *   Fe3+ / Mn2+ / Ca2+ / Cu2+ / Zn2+ / Al3+
 *   Fe2+ / Fe3+ / NH4+ / Cl- / NO3-
 *   CO32- / CO3 2- / SO42- / SO4 2-
 *   CO3^2- / SO4^2- (OCR caret 变体)
 *   O2·- (自由基 + 电荷，· 由 formatRadicals 处理)
 *
 * 不匹配:
 *   O3-MNBs (formula + connector + word)
 *   O3/H2O2 (formula + separator)
 *   2026 (数字开头)
 *   Fig-2 (P 不是元素符号，但 Fig 也含 F/i/g)
 *     → 实际: Fig 后跟 "-" 时，"Fig-" 整体 [A-Z][a-z]?\d*? 不匹配，
 *       因为 "F"+"ig" 不是 [A-Z][a-z]? 模式 (i,g 是 lowercase 但 ig 不行，
 *       regex 只允许 1 个 lowercase letter)
 *     → "Fig-2" 不会匹配离子正则
 */

// 离子正则: (Formula)(\s*)(optional digit)(optional radical)(sign)
// 4 个 capture groups 顺序: formula, digit, radical, sign
// 关键: extension 用 *? 和 \d+? 双重非贪婪，避免 O42 整体被吞作 formula
// 例: SO42- → 优先 SO4 + 2(charge) 解析，而非 SO42(atom)
//     O2·- → O + 2(atom) + · + -
//     Fe3+ → Fe + 3(charge) + +
//     H+   → H + sign
const CHARGE_RE = /(?<![A-Z][a-z])([A-Z][a-z]?(?:[A-Z][a-z]?\d+?)*?)\s*(\d*)([·•]?)([+−−-])(?![A-Za-z\d])/g

function formatIonCharge(text) {
  if (!text) return ''
  let result = String(text)

  // capture 顺序: 1=formula, 2=digit, 3=radical, 4=sign
  result = result.replace(CHARGE_RE, (_m, formulaPart, digit, radical, chargeSign) => {
    // formulaPart: "Na" / "OH" / "CO3" / "Fe" / "NH4" 等
    // 内部继续拆 Element + Digit 对（subscript）
    const formattedFormula = formulaPart.replace(/([A-Z][a-z]?)(\d+)/g, (_mm, el, n) => {
      return el + _toSub(n)
    })

    // 关键: radical (·/•) 存在时 digit 是原子数（subscript），不存在时是电荷数（superscript）
    // 例: O2·- → O₂·⁻ (digit=atom subscript)
    //     Fe3+ → Fe³⁺ (digit=charge superscript)
    //     SO42- → SO₄²⁻ (digit=charge superscript，因为没有 radical)
    let digitSup = ''
    if (digit) {
      digitSup = radical ? _toSub(digit) : _toSup(digit)
    }

    // charge sign 永远 superscript
    const chargeSignSup = chargeSign === '-' || chargeSign === '−' ? '⁻' : '⁺'

    return formattedFormula + digitSup + (radical || '') + chargeSignSup
  })

  return result
}

// ============================================================
// 4. 自由基 / 活性氧 (radical preservation)
// ============================================================

/**
 * 处理自由基点号 · 和 •
 * - ·OH / •OH (保持)
 * - O2·- → 先处理 formula (O₂) + charge (⁻)，· 是视觉提示
 * - O2.- → OCR 变体 . 当作 ·
 * - ·O2- → 同上
 */

// 自由基点号规范化：把 . + - 模式当作 ·⁻ (OCR 脏数据)
const RADICAL_NORMALIZE_RE = /([A-Z][a-z]?\d*)\.([+−−-])/g

// 自由基 ·OH / •OH 保留
const RADICAL_PRESERVE_RE = /([·•])([A-Z][a-z]?\d*)/g

function formatRadicals(text) {
  if (!text) return ''
  let result = String(text)

  // 1. 规范化 OCR 脏数据: O2.- → O2·- (dot before charge → middle dot)
  result = result.replace(RADICAL_NORMALIZE_RE, (_m, base, charge) => {
    return base + '·' + charge
  })

  // 2. ·OH / •OH 保持（不做转换）
  // 这里仅清理，无需操作

  return result
}

// ============================================================
// 5. 体积立方 (volume cubic: m3 → m³) — 已并入 formatUnitExponent
// ============================================================

// 体积立方的处理已经在 formatUnitExponent 第一步完成。
// 这里保留独立函数以兼容旧 API。
function formatVolumeCubic(text) {
  if (!text) return ''
  return String(text).replace(
    /\b(m|cm|mm|km|dm|μm|nm)(3)(?![A-Za-z\d])/g,
    (_m, prefix, _three) => prefix + '³'
  )
}

// ============================================================
// 6. 科学计数法 (scientific notation: ×10-3 → ×10⁻³)
// ============================================================

/**
 * 仅在显式有 × / x / X / * 前缀时转换（避免误伤 "Eq. 10-3" 这种普通范围）
 *
 * 匹配: ×10-3 / x10-3 / X10-3 / *10-3 → 对应 Unicode 上标
 */

const SCI_NOTATION_RE = /([×xX*])10(-1|-2|-3|-4|-5|-6|-7|-8|-9|-\d{2,})(?![-\d])/g

function formatScientificNotation(text) {
  if (!text) return ''
  let result = String(text)

  result = result.replace(SCI_NOTATION_RE, (_m, prefix, exp) => {
    // exp 形如 "-3" 或 "-12"
    const expNum = exp.replace('-', '')
    return `${prefix}10⁻${_toSup(expNum)}`
  })

  return result
}

// ============================================================
// 保护区（v27.2 铁律）
// ============================================================

/**
 * 不应该被化学式 / 单位 / 电荷 格式化器改动的"保护区"文本模式：
 * - 图表引用: Fig. 1 / Fig. S2 / Figs. S3-S4 / Figure 1 / Scheme 1 / Table S1 / Text S4 / Eq. 2
 * - 参考文献: [1] / [1,2] / [3–5]
 * - DOI: 10.1016/j.scitotenv.2024.123456
 * - URL: https://doi.org/...  http://...
 * - 章节编号: 2.1 / 3.5.2 / Section 2.1
 *
 * 关键问题: Fig. S2 中的 "S2" 会被 formula regex 误判为元素 S 的下标
 *
 * 策略: 用 placeholder 替换 → 跑格式化 → 还原
 */

// 单一 combined regex：一次扫描所有保护区，避免位置偏移问题
// 顺序：URL > DOI > Ref > Section > Fig（最长匹配优先）
const PROTECTED_ALL_RE = new RegExp(
  // URL: http(s)://...
  'https?://[^\\s<>"\']+' +
  '|' +
  // DOI: 10.xxxx/yyyyy
  '\\b10\\.\\d{4,9}/[-._;()\\/:A-Z0-9]+' +
  '|' +
  // 参考文献编号 [1] [1,2] [3–5] [12–15]
  '\\[\\d+(?:[\\s,–\\-]+\\d+)*\\]' +
  '|' +
  // 章节编号 Section 2.1 / §2.1 / Chapter 4
  '\\b(?:Section|§|Chapter)\\s+\\d+(?:\\.\\d+){0,3}\\b' +
  '|' +
  // 图表引用 Fig. 1 / Fig. S2 / Figs. S3-S4 / Figure 1 / Scheme 1 / Table S1 / Text S4 / Eq. 2
  '\\b(?:Fig|Figs|Figure|Scheme|Table|Text|Eq|Ref|Section)\\.?\\s+(?:S\\d+|\\d+)[a-z]?(?:[\\s,–\\-]+(?:S\\d+|\\d+)[a-z]?)*\\b',
  'gi'
)


// 使用 Unicode 控制字符 (U+0001/U+0002) 作 placeholder
// 这两个字符几乎不会在学术文本中自然出现
const PROTECT_OPEN = String.fromCharCode(1)
const PROTECT_CLOSE = String.fromCharCode(2)

function _protectRanges(text) {
  const ranges = []
  text = text.replace(PROTECTED_ALL_RE, (match, ...args) => {
    const offset = args[args.length - 2]
    ranges.push({ start: offset, end: offset + match.length, original: match })
    return PROTECT_OPEN + String(ranges.length - 1) + PROTECT_CLOSE
  })
  return { text, ranges }
}

function _restoreRanges(text, ranges) {
  let result = text
  for (let i = ranges.length - 1; i >= 0; i--) {
    const placeholder = PROTECT_OPEN + String(i) + PROTECT_CLOSE
    result = result.split(placeholder).join(ranges[i].original)
  }
  return result
}

// ============================================================
// 主入口：按特定顺序组合所有规则
// ============================================================

/**
 * 格式化顺序很关键:
 * 0. _protectRanges 把图号/DOI/章节号保护为 placeholder
 * 1. formatRadicals 先做（OCR 脏数据 . → ·）
 * 2. formatIonCharge 第二（在 formula 之前！避免 Fe3+ 被 formula 吃掉 3 → Fe₃+）
 * 3. formatUnitExponent 第三（包含体积立方 m3 → m³）
 * 4. formatScientificNotation 第四（避免被 formula 规则吃掉 10-3 中的 10）
 * 5. formatChemicalFormula 最后（subscript 数字）
 * 6. _restoreRanges 还原 placeholder
 */
function formatScientificText(text) {
  if (!text) return ''
  let result = String(text)

  // 0. 保护区：把不应被改动的内容替换为 placeholder
  const { text: protectedText, ranges } = _protectRanges(result)
  result = protectedText

  // 保护已有 HTML 标签（防御性，理论上不应有）
  const protectedTags = []
  result = result.replace(/<[^>]+>/g, (m) => {
    protectedTags.push(m)
    return `\x00SCI_TAG_${protectedTags.length - 1}\x00`
  })

  result = formatRadicals(result)
  result = formatIonCharge(result)
  result = formatUnitExponent(result)
  result = formatScientificNotation(result)
  result = formatChemicalFormula(result)

  // 恢复保护的标签
  result = result.replace(/\x00SCI_TAG_(\d+)\x00/g, (_m, i) => protectedTags[parseInt(i)])

  // 6. 还原保护区（URL/DOI/Fig/Ref/Section）
  result = _restoreRanges(result, ranges)

  return result
}

// 兼容旧 API
export const formatChemicalText = formatScientificText

// ============================================================
// 公开导出
// ============================================================

export {
  formatScientificText,
  formatChemicalFormula,
  formatUnitExponent,
  formatIonCharge,
  formatRadicals,
  formatVolumeCubic,
  formatScientificNotation,
  _toSub,
  _toSup,
  _toSubSup,
  ALL_UNITS,
}
