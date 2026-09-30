/**
 * MobileKnowledgeView.test.js (PR8: 移动端 KnowledgeView 移除 'files' tab)
 *
 * 静态回归测试: 验证 PR8 改动到位 (4 处清理 + 1 处 VALID_TABS 清理)。
 *
 * 因为 MobileKnowledgeView mount 需要 mock Element Plus + axios + router + Pinia store
 * (成本极高, 且会因 mock 漏 ref 造成 false positive), 采用与
 * KnowledgeView.filter-reset.test.js 同款的静态源码检查模式。
 * 直接验证关键变更存在, 比动态 mount 100% 可靠。
 */

import { describe, it, expect } from 'vitest'
import { readFileSync } from 'fs'
import { join } from 'path'

const VIEW_PATH = join(__dirname, '../mobile/MobileKnowledgeView.vue')

describe('MobileKnowledgeView - PR8 移除 files tab 静态回归', () => {
  let sourceCode

  it('加载源码', () => {
    sourceCode = readFileSync(VIEW_PATH, 'utf-8')
    expect(sourceCode.length).toBeGreaterThan(0)
  })

  it('VALID_TABS 白名单不含 files (URL ?tab=files 回退到默认)', () => {
    sourceCode = readFileSync(VIEW_PATH, 'utf-8')
    const validTabsMatch = sourceCode.match(
      /const VALID_TABS\s*=\s*\[([^\]]+)\]/
    )
    expect(validTabsMatch, 'VALID_TABS 数组必须存在').toBeTruthy()
    const tabsArray = validTabsMatch[1]
    // 已下线的 tab 不得复活: files (PR8 移到 /m-drive) / formulas (2026-09-13
    // 公式计算整体下线) / memory (随 Knowledge Brain 改版移除)
    expect(tabsArray).not.toMatch(/'files'|'formulas'|'memory'/)
    // 现役 4 个 tab key
    const count =
      (tabsArray.match(/'(knowledge|entities|hypotheses|health)'/g) || []).length
    expect(count).toBe(4)
  })

  it('tabItems 数组无 files entry', () => {
    sourceCode = readFileSync(VIEW_PATH, 'utf-8')
    const tabItemsMatch = sourceCode.match(
      /const tabItems\s*=\s*\[([\s\S]*?)\]/
    )
    expect(tabItemsMatch, 'tabItems 数组必须存在').toBeTruthy()
    expect(tabItemsMatch[1]).not.toMatch(/key:\s*'(files|formulas|memory)'/)
    // 现役 4 个 key (2026-09-30 S3.4 对齐源码真值: formulas 已随公式计算下线移除)
    const keyCount = (tabItemsMatch[1].match(/key:\s*'(knowledge|entities|hypotheses|health)'/g) || []).length
    expect(keyCount).toBe(4)
  })

  it('兼容旧 tabs 数组无 files entry', () => {
    sourceCode = readFileSync(VIEW_PATH, 'utf-8')
    const tabsMatch = sourceCode.match(
      /const tabs\s*=\s*\[([\s\S]*?)\]/
    )
    expect(tabsMatch, 'tabs 数组必须存在').toBeTruthy()
    expect(tabsMatch[1]).not.toMatch(/name:\s*'files'/)
  })

  it('模板无 v-else-if="activeTab === \'files\'" 分支', () => {
    sourceCode = readFileSync(VIEW_PATH, 'utf-8')
    // 在 <template>...</template> 范围内检查
    const templateMatch = sourceCode.match(/<template>([\s\S]*?)<\/template>/)
    expect(templateMatch, '模板必须存在').toBeTruthy()
    expect(templateMatch[1]).not.toMatch(/v-else-if="activeTab\s*===\s*'files'"/)
  })

  it('PageHeader 仍渲染（PR8 未误删 header）', () => {
    sourceCode = readFileSync(VIEW_PATH, 'utf-8')
    expect(sourceCode).toMatch(/<PageHeader/)
  })

  it('未注册的 string literal "files" 计数为 0', () => {
    sourceCode = readFileSync(VIEW_PATH, 'utf-8')
    // 单引号包裹的字符串 'files' 应为 0 (反例: 未清理)
    const matches = sourceCode.match(/'files'/g)
    expect(matches, '不应再出现字面量 \'files\'').toBeNull()
  })
})
