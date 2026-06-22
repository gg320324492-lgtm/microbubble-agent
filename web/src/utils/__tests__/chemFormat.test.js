import { describe, it, expect } from 'vitest'
import {
  formatScientificText,
  formatChemicalFormula,
  formatUnitExponent,
  formatIonCharge,
  formatRadicals,
  formatVolumeCubic,
  formatScientificNotation,
} from '../chemFormat'

// ============================================================
// 1. 化学式通用识别
// ============================================================

describe('formatChemicalFormula - 通用公式识别', () => {
  it('单元素 + 数字下标', () => {
    expect(formatChemicalFormula('O3')).toBe('O₃')
    expect(formatChemicalFormula('O2')).toBe('O₂')
    expect(formatChemicalFormula('N2')).toBe('N₂')
    expect(formatChemicalFormula('Cl2')).toBe('Cl₂')
    expect(formatChemicalFormula('H2')).toBe('H₂')
  })

  it('双元素组合', () => {
    expect(formatChemicalFormula('H2O')).toBe('H₂O')
    expect(formatChemicalFormula('H2O2')).toBe('H₂O₂')
    expect(formatChemicalFormula('CO2')).toBe('CO₂')
    expect(formatChemicalFormula('SO2')).toBe('SO₂')
    expect(formatChemicalFormula('NH3')).toBe('NH₃')
    expect(formatChemicalFormula('NH4')).toBe('NH₄')
    expect(formatChemicalFormula('CH4')).toBe('CH₄')
    expect(formatChemicalFormula('NO3')).toBe('NO₃')
    expect(formatChemicalFormula('NO2')).toBe('NO₂')
  })

  it('复杂分子', () => {
    expect(formatChemicalFormula('CaCO3')).toBe('CaCO₃')
    expect(formatChemicalFormula('H2SO4')).toBe('H₂SO₄')
    expect(formatChemicalFormula('HNO3')).toBe('HNO₃')
    expect(formatChemicalFormula('KMnO4')).toBe('KMnO₄')
    expect(formatChemicalFormula('Na2SO4')).toBe('Na₂SO₄')
    expect(formatChemicalFormula('Fe2O3')).toBe('Fe₂O₃')
    expect(formatChemicalFormula('Co3O4')).toBe('Co₃O₄')
    expect(formatChemicalFormula('MnO2')).toBe('MnO₂')
    expect(formatChemicalFormula('Al2O3')).toBe('Al₂O₃')
  })

  it('带分组括号的复杂化学式', () => {
    expect(formatChemicalFormula('Mg(OH)2')).toBe('Mg(OH)₂')
    expect(formatChemicalFormula('Ca(OH)2')).toBe('Ca(OH)₂')
  })

  it('复合写法 (与连接符 + - / ·)', () => {
    expect(formatChemicalFormula('O3-MNBs')).toBe('O₃-MNBs')
    expect(formatChemicalFormula('O3/H2O2')).toBe('O₃/H₂O₂')
    expect(formatChemicalFormula('H2O2+N2-MNBs')).toBe('H₂O₂+N₂-MNBs')
    expect(formatChemicalFormula('O3/O2')).toBe('O₃/O₂')
    expect(formatChemicalFormula('O3-MNBs/H2O2')).toBe('O₃-MNBs/H₂O₂')
  })

  it('不在科学上下文时不误伤', () => {
    // 年份、页码、DOI、普通编号都不变
    expect(formatChemicalFormula('2026')).toBe('2026')
    expect(formatChemicalFormula('Fig. 2')).toBe('Fig. 2')
    expect(formatChemicalFormula('Table 3')).toBe('Table 3')
    expect(formatChemicalFormula('2.1')).toBe('2.1')
    expect(formatChemicalFormula('Section 4')).toBe('Section 4')
    expect(formatChemicalFormula('Eq. (1)')).toBe('Eq. (1)')
  })

  it('空字符串和 null', () => {
    expect(formatChemicalFormula('')).toBe('')
    expect(formatChemicalFormula(null)).toBe('')
    expect(formatChemicalFormula(undefined)).toBe('')
  })

  it('多化学式在同一段', () => {
    expect(formatChemicalFormula('O3 and H2O2')).toBe('O₃ and H₂O₂')
    expect(formatChemicalFormula('The O3/H2O2 ratio')).toBe('The O₃/H₂O₂ ratio')
  })
})

// ============================================================
// 2. 单位指数自动识别
// ============================================================

describe('formatUnitExponent - 单位指数识别', () => {
  it('流量单位 L·h-1', () => {
    expect(formatUnitExponent('L·h-1')).toBe('L·h⁻¹')
    expect(formatUnitExponent('200 L·h-1')).toBe('200 L·h⁻¹')
    expect(formatUnitExponent('1000 L·h-1')).toBe('1000 L·h⁻¹')
  })

  it('流量单位 mL·min-1', () => {
    expect(formatUnitExponent('mL·min-1')).toBe('mL·min⁻¹')
    expect(formatUnitExponent('100 mL·min-1')).toBe('100 mL·min⁻¹')
  })

  it('浓度单位 mg·L-1', () => {
    expect(formatUnitExponent('mg·L-1')).toBe('mg·L⁻¹')
    expect(formatUnitExponent('5 mg·L-1')).toBe('5 mg·L⁻¹')
  })

  it('体积流速 m3·h-1', () => {
    expect(formatUnitExponent('m3·h-1')).toBe('m³·h⁻¹')
    expect(formatUnitExponent('cm3·min-1')).toBe('cm³·min⁻¹')
  })

  it('简单单位指数（无基础单位）', () => {
    expect(formatUnitExponent('s-1')).toBe('s⁻¹')
    expect(formatUnitExponent('cm-1')).toBe('cm⁻¹')
    expect(formatUnitExponent('min-1')).toBe('min⁻¹')
    expect(formatUnitExponent('h-1')).toBe('h⁻¹')
  })

  it('-2 / -3 指数', () => {
    expect(formatUnitExponent('m-2')).toBe('m⁻²')
    expect(formatUnitExponent('m-3')).toBe('m⁻³')
    expect(formatUnitExponent('L·m-2')).toBe('L·m⁻²')
  })

  it('不同分隔符 (· / ・ / /)', () => {
    expect(formatUnitExponent('L·h-1')).toBe('L·h⁻¹')
    expect(formatUnitExponent('L・h-1')).toBe('L・h⁻¹')
    expect(formatUnitExponent('L/h-1')).toBe('L/h⁻¹')
  })

  it('OCR 变体（无分隔符）', () => {
    expect(formatUnitExponent('L h-1')).toBe('L h⁻¹')
    expect(formatUnitExponent('mL min-1')).toBe('mL min⁻¹')
  })

  it('不误伤普通文本', () => {
    // Page 1 不应该被错误转换
    expect(formatUnitExponent('Page 1 of 10')).toBe('Page 1 of 10')
    expect(formatUnitExponent('see Figure 2-1')).toBe('see Figure 2-1')
    // 纯数字
    expect(formatUnitExponent('1234')).toBe('1234')
    // 不在白名单的单位不转换
    expect(formatUnitExponent('xyz-1')).toBe('xyz-1')
  })

  it('空字符串和 null', () => {
    expect(formatUnitExponent('')).toBe('')
    expect(formatUnitExponent(null)).toBe('')
  })

  it('体积立方 m3 → m³', () => {
    expect(formatVolumeCubic('m3')).toBe('m³')
    expect(formatVolumeCubic('cm3')).toBe('cm³')
    expect(formatVolumeCubic('mm3')).toBe('mm³')
    // 不是体积立方时不变
    expect(formatVolumeCubic('O3')).toBe('O3')
  })
})

// ============================================================
// 3. 离子与电荷自动识别
// ============================================================

describe('formatIonCharge - 离子电荷识别', () => {
  it('简单电荷', () => {
    expect(formatIonCharge('H+')).toBe('H⁺')
    expect(formatIonCharge('Na+')).toBe('Na⁺')
    expect(formatIonCharge('K+')).toBe('K⁺')
    expect(formatIonCharge('OH-')).toBe('OH⁻')
    expect(formatIonCharge('Cl-')).toBe('Cl⁻')
  })

  it('带数字的电荷', () => {
    expect(formatIonCharge('Fe3+')).toBe('Fe³⁺')
    expect(formatIonCharge('Fe2+')).toBe('Fe²⁺')
    expect(formatIonCharge('Ca2+')).toBe('Ca²⁺')
    expect(formatIonCharge('Cu2+')).toBe('Cu²⁺')
    expect(formatIonCharge('Zn2+')).toBe('Zn²⁺')
    expect(formatIonCharge('Al3+')).toBe('Al³⁺')
    expect(formatIonCharge('Mn2+')).toBe('Mn²⁺')
    expect(formatIonCharge('Mg2+')).toBe('Mg²⁺')
  })

  it('复合离子', () => {
    expect(formatIonCharge('NH4+')).toBe('NH₄⁺')
    expect(formatIonCharge('HCO3-')).toBe('HCO₃⁻')
    expect(formatIonCharge('NO3-')).toBe('NO₃⁻')
    expect(formatIonCharge('SO42-')).toBe('SO₄²⁻')
    expect(formatIonCharge('CO32-')).toBe('CO₃²⁻')
  })

  it('带空格的复合离子电荷', () => {
    expect(formatIonCharge('CO3 2-')).toBe('CO₃²⁻')
    expect(formatIonCharge('SO4 2-')).toBe('SO₄²⁻')
  })

  it('不同减号字符', () => {
    // ASCII -
    expect(formatIonCharge('OH-')).toBe('OH⁻')
    // Unicode 减号 − (U+2212)
    expect(formatIonCharge('OH−')).toBe('OH⁻')
    // 半角负号 - (U+2212 已在上方)
  })

  it('不误伤公式 + 连接符', () => {
    // O3-MNBs: formula + connector + word，不应被当成 O3 + 电荷
    expect(formatIonCharge('O3-MNBs')).toBe('O3-MNBs')
    expect(formatIonCharge('CO3-MNBs')).toBe('CO3-MNBs')
    expect(formatIonCharge('H2O2+N2-MNBs')).toBe('H2O2+N2-MNBs')
  })

  it('不误伤普通文本', () => {
    expect(formatIonCharge('2026')).toBe('2026')
    expect(formatIonCharge('Fig. 2')).toBe('Fig. 2')
    expect(formatIonCharge('the temperature')).toBe('the temperature')
  })

  it('空字符串和 null', () => {
    expect(formatIonCharge('')).toBe('')
    expect(formatIonCharge(null)).toBe('')
  })
})

// ============================================================
// 4. 自由基 / 活性氧
// ============================================================

describe('formatRadicals - 自由基识别', () => {
  it('保持 ·OH 形式', () => {
    expect(formatRadicals('·OH')).toBe('·OH')
    expect(formatRadicals('•OH')).toBe('•OH')
  })

  it('OCR 脏数据 . 替换为 ·', () => {
    expect(formatRadicals('O2.-')).toBe('O2·-')
    expect(formatRadicals('OH.-')).toBe('OH·-')
  })

  // v28 step 109.27: OCR 把 ·OH 误识成 -OH（连字符）+ 小写词开头
  it('-OH + 小写词开头 → ·OH（OCR radical 错误修正）', () => {
    expect(formatRadicals('-OH generation was determined')).toBe('·OH generation was determined')
    expect(formatRadicals('-OH produced in water')).toBe('·OH produced in water')
    expect(formatRadicals('and -OH attack')).toBe('and ·OH attack')
  })

  it('化学键 -OH 不转换（5-OH / C-OH）', () => {
    expect(formatRadicals('5-OH')).toBe('5-OH')
    expect(formatRadicals('C-OH')).toBe('C-OH')
    expect(formatRadicals('R-OH')).toBe('R-OH')
  })

  it('空字符串和 null', () => {
    expect(formatRadicals('')).toBe('')
    expect(formatRadicals(null)).toBe('')
  })
})

// ============================================================
// 5. 科学计数法
// ============================================================

describe('formatScientificNotation - 科学计数法', () => {
  it('×10-N 转换', () => {
    expect(formatScientificNotation('×10-3')).toBe('×10⁻³')
    expect(formatScientificNotation('×10-9')).toBe('×10⁻⁹')
    expect(formatScientificNotation('×10-12')).toBe('×10⁻¹²')
  })

  it('不同乘号字符', () => {
    expect(formatScientificNotation('x10-3')).toBe('x10⁻³')
    expect(formatScientificNotation('X10-3')).toBe('X10⁻³')
    expect(formatScientificNotation('*10-3')).toBe('*10⁻³')
  })

  it('必须显式 × 前缀才转换', () => {
    // 纯 10-3 不应被转换（可能是 Eq. 10-3 这种范围）
    expect(formatScientificNotation('10-3 to 10-9')).toBe('10-3 to 10-9')
  })

  it('空字符串和 null', () => {
    expect(formatScientificNotation('')).toBe('')
    expect(formatScientificNotation(null)).toBe('')
  })
})

// ============================================================
// 6. formatScientificText — 主入口（组合所有规则）
// ============================================================

describe('formatScientificText - 主入口', () => {
  it('组合多种规则', () => {
    // 化学式 + 单位指数
    expect(formatScientificText('200 L·h-1 with O3')).toBe('200 L·h⁻¹ with O₃')
    expect(formatScientificText('mg·L-1 of H2O2')).toBe('mg·L⁻¹ of H₂O₂')
    // 化学式 + 离子电荷
    expect(formatScientificText('O3 produces OH-')).toBe('O₃ produces OH⁻')
    expect(formatScientificText('Fe3+ reacts with OH-')).toBe('Fe³⁺ reacts with OH⁻')
    // 复合公式
    expect(formatScientificText('O3-MNBs at 100 L·h-1')).toBe('O₃-MNBs at 100 L·h⁻¹')
  })

  it('真实场景: 论文正文风格', () => {
    expect(formatScientificText('The reaction between O3 and H2O2 produces ·OH radicals'))
      .toBe('The reaction between O₃ and H₂O₂ produces ·OH radicals')
    expect(formatScientificText('O2·- is a strong oxidant'))
      .toBe('O₂·⁻ is a strong oxidant')
    expect(formatScientificText('Fe2O3 nanoparticles at 5 mg·L-1'))
      .toBe('Fe₂O₃ nanoparticles at 5 mg·L⁻¹')
  })

  it('不误伤页面文字', () => {
    expect(formatScientificText('Fig. 2 shows the results')).toBe('Fig. 2 shows the results')
    expect(formatScientificText('Published in 2026')).toBe('Published in 2026')
    expect(formatScientificText('Section 2.1 and Eq. (1)')).toBe('Section 2.1 and Eq. (1)')
    expect(formatScientificText('References [12] and [34]')).toBe('References [12] and [34]')
    expect(formatScientificText('DOI: 10.1234/abc')).toBe('DOI: 10.1234/abc')
  })

  it('空字符串和 null', () => {
    expect(formatScientificText('')).toBe('')
    expect(formatScientificText(null)).toBe('')
    expect(formatScientificText(undefined)).toBe('')
  })

  it('不返回任何 HTML 标签（防 _escapeHtml 二次转义）', () => {
    const result = formatScientificText('O3 and H2O2 at 100 L·h-1 produce OH-')
    expect(result).not.toMatch(/<[^>]+>/)
    expect(result).not.toContain('<sub>')
    expect(result).not.toContain('<sup>')
    expect(result).not.toContain('chem-formula')
  })

  it('多次调用结果稳定（幂等性）', () => {
    const text = '200 L·h-1 with O3 produces OH-'
    const once = formatScientificText(text)
    const twice = formatScientificText(once)
    expect(twice).toBe(once)
  })

  it('温度 °C 保留', () => {
    expect(formatScientificText('300 °C')).toBe('300 °C')
    expect(formatScientificText('at 25 °C')).toBe('at 25 °C')
  })
})

// ============================================================
// v27.2: 保护区机制 - 不误伤 Fig. S2 / DOI / 章节号 / 参考文献
// ============================================================

describe('formatScientificText - v27.2 保护区机制', () => {
  it('图表引用 Fig. S2 不被误伤 (SI/Supporting 图号)', () => {
    expect(formatScientificText('Fig. S2')).toBe('Fig. S2')
    expect(formatScientificText('Figs. S3-S4')).toBe('Figs. S3-S4')
    expect(formatScientificText('Fig. S10')).toBe('Fig. S10')
    expect(formatScientificText('Fig. S1a')).toBe('Fig. S1a')
  })

  it('普通图表引用 Fig. 1 保持原样', () => {
    expect(formatScientificText('Fig. 1')).toBe('Fig. 1')
    expect(formatScientificText('Figs. 3-4')).toBe('Figs. 3-4')
    expect(formatScientificText('Figure 1')).toBe('Figure 1')
    expect(formatScientificText('Scheme 1')).toBe('Scheme 1')
    expect(formatScientificText('Table 2')).toBe('Table 2')
    expect(formatScientificText('Text S4')).toBe('Text S4')
    expect(formatScientificText('Eq. 2')).toBe('Eq. 2')
  })

  it('DOI 不被误伤', () => {
    expect(formatScientificText('DOI: 10.1016/j.scitotenv.2024.123456'))
      .toBe('DOI: 10.1016/j.scitotenv.2024.123456')
    expect(formatScientificText('https://doi.org/10.1234/abc.def'))
      .toBe('https://doi.org/10.1234/abc.def')
  })

  it('参考文献 [1] [3-5] 保持原样', () => {
    expect(formatScientificText('see [1] and [3-5]')).toBe('see [1] and [3-5]')
    expect(formatScientificText('Refs. [1,2]')).toBe('Refs. [1,2]')
  })

  it('Section 章节号保持原样', () => {
    expect(formatScientificText('Section 2.1')).toBe('Section 2.1')
    expect(formatScientificText('Section 3.5.2')).toBe('Section 3.5.2')
    expect(formatScientificText('Chapter 4')).toBe('Chapter 4')
  })

  it('保护区内混合真实化学式仍能正确处理', () => {
    // Fig. S2 + H2O2 + 200 L·h-1
    expect(formatScientificText('Fig. S2 shows H2O2 at 200 L·h-1'))
      .toBe('Fig. S2 shows H₂O₂ at 200 L·h⁻¹')
    expect(formatScientificText('Fig. 1 and O3-MNBs'))
      .toBe('Fig. 1 and O₃-MNBs')
    expect(formatScientificText('Section 2.1 discusses H2O2'))
      .toBe('Section 2.1 discusses H₂O₂')
  })
})
