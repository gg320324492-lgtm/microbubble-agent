/**
 * textSanitize.spec.js — 测试 web/src/utils/textSanitize.js (2026-07-15)
 *
 * 与 backend pytest test_text_sanitize.py 镜像覆盖, 验证前端 sanitize
 * 逻辑与后端等价 (防止 JS/Python 两套实现漂移)。
 *
 * 覆盖:
 *  - 空输入 (null / undefined / "" / 空白)
 *  - LLM 套路开场白剥除 (好的,非常荣幸/以下是...)
 *  - 项目名称/研究方向 字段抽取
 *  - markdown 字符 (** _ ` # >) 清洗
 *  - 长度 cap 280 + 优雅截断
 *  - displayDescription 兜底返 '暂无描述'
 */

import { describe, it, expect } from 'vitest'
import { cleanDescriptionForDisplay, displayDescription } from '@/utils/textSanitize'

describe('cleanDescriptionForDisplay — 空输入', () => {
  it('null → 空字符串', () => {
    expect(cleanDescriptionForDisplay(null)).toBe('')
  })
  it('undefined → 空字符串', () => {
    expect(cleanDescriptionForDisplay(undefined)).toBe('')
  })
  it('空白 → 空字符串', () => {
    expect(cleanDescriptionForDisplay('   \n  \t  ')).toBe('')
  })
  it('空字符串 → 空字符串', () => {
    expect(cleanDescriptionForDisplay('')).toBe('')
  })
})

describe('cleanDescriptionForDisplay — 短干净描述 (pass-through)', () => {
  it('真项目风格带句号', () => {
    const raw = '研究微纳米气泡在饮用水处理中的应用，包括消毒抑菌、生物稳定性提升等。'
    const result = cleanDescriptionForDisplay(raw)
    expect(result).toBe(raw)
  })

  it('真项目风格无句号 → 自动补 。', () => {
    const raw = '研究气泡成核机理、发生器结构优化'
    const result = cleanDescriptionForDisplay(raw)
    expect(result.endsWith('。')).toBe(true)
    expect(result).toContain('气泡成核')
  })
})

describe('cleanDescriptionForDisplay — LLM 套路开场白剥除', () => {
  it('剥"好的,非常荣幸"开场白 (含研究动词+主题词句作为 fallback)', () => {
    const raw = '好的，非常荣幸能为您规划这份研究项目计划。本计划旨在充分利用6个月时间，让3人团队高效协作，研究微纳米气泡降解抗生素。'
    const result = cleanDescriptionForDisplay(raw)
    expect(result).not.toContain('好的')
    expect(result).not.toContain('非常荣幸')
    // "本计划旨在...研究微纳米气泡降解抗生素" 含研究动词 + 主题词,
    // 被 Step C-1 命中, 接受为有意义句子 (Step B 已剥除开场白)
    expect(result).toMatch(/研究/)
    expect(result).toMatch(/微纳米气泡|抗生素/)
  })

  it('剥"以下是"开场白', () => {
    const raw = '以下是您要求的项目计划。研究方向：微纳米气泡在水处理中降解抗生素的应用。'
    const result = cleanDescriptionForDisplay(raw)
    expect(result).not.toContain('以下是')
    expect(result).toContain('微纳米气泡在水处理中降解抗生素')
  })
})

describe('cleanDescriptionForDisplay — LLM 字段抽取', () => {
  it('抽取"项目名称:"字段值', () => {
    const raw = `好的，非常荣幸能为您规划。

### **项目总览**
*   **项目名称：** 微纳米气泡对典型抗生素的降解效能与机理研究
*   **总时长：** 6个月`
    const result = cleanDescriptionForDisplay(raw)
    expect(result).not.toContain('6个月')
    expect(result).toContain('微纳米气泡对典型抗生素')
  })

  it('抽取"研究方向:"字段值 (避 STOP_WORDS)', () => {
    const raw = `# 微气泡降解抗生素项目计划

**项目名称**：微纳米气泡在水处理中降解抗生素的应用研究

**项目周期**：6个月

**研究方向**：微纳米气泡技术在抗生素污染水体处理中的机理与效能研究`
    const result = cleanDescriptionForDisplay(raw)
    expect(result).not.toContain('#')
    expect(result).not.toContain('**')
    expect(result).not.toContain('6个月')
    expect(result).toContain('微纳米气泡')
    expect(result).toContain('抗生素')
  })

  it('含 STOP_WORDS 字段值被跳过 (含 6个月/3人 等)', () => {
    const raw = '项目名称：6个月团队 3人完成的项目简述'
    const result = cleanDescriptionForDisplay(raw)
    expect(result).not.toContain('6个月')
    expect(result).not.toContain('3人')
  })
})

describe('cleanDescriptionForDisplay — markdown 清洗', () => {
  it('inline markdown 字符被剥除', () => {
    const raw = '**研究** 微纳米 _气泡_ `降解` 抗生素 **# 第一阶段**'
    const result = cleanDescriptionForDisplay(raw)
    expect(result).not.toContain('**')
    expect(result).not.toContain('`')
    expect(result).not.toContain('# 第一阶段')
  })

  it('行首 # ## ### 标题符被剥除', () => {
    const raw = '### **项目名称**\n# 第一阶段研究\n**研究内容** 研究微纳米气泡'
    const result = cleanDescriptionForDisplay(raw)
    expect(result).not.toContain('# 第一阶段')
  })
})

describe('cleanDescriptionForDisplay — 长度 cap + 优雅截断', () => {
  it('超长 description 被截断到 maxLen', () => {
    const raw = '研究微纳米气泡技术在水处理中的应用，' + ('包括消毒、抑菌、稳定性提升等'.repeat(20))
    const result = cleanDescriptionForDisplay(raw, 80)
    expect(result.length).toBeLessThanOrEqual(80)
  })

  it('截断到最近的优雅点 (。 ； ; —)', () => {
    const raw = '研究微纳米气泡技术在水处理中的应用。' + '详细分析如下'.repeat(30) + '结论：本研究重要。'
    const result = cleanDescriptionForDisplay(raw, 80)
    // 至少要一个分句结尾
    expect(/[。；;]$/.test(result) || result.endsWith('...')).toBe(true)
  })
})

describe('displayDescription — 兜底返 "暂无描述"', () => {
  it('空输入返 "暂无描述"', () => {
    expect(displayDescription(null)).toBe('暂无描述')
    expect(displayDescription('')).toBe('暂无描述')
    expect(displayDescription(undefined)).toBe('暂无描述')
  })

  it('有内容返清洗结果', () => {
    const raw = '研究微纳米气泡在水处理中的应用'
    expect(displayDescription(raw)).not.toBe('暂无描述')
    expect(displayDescription(raw)).toContain('微纳米气泡')
  })
})
