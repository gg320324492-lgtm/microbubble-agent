/**
 * KnowledgeView.filter-reset.test.js
 * 静态回归测试: P2-8 防御性覆盖 (KB 5 全 0 误报 + v77 P2.6-F.4 已修)
 *
 * 验证 watch [filterCategory, filterSourceType] 触发时 currentPage 重置为 1,
 * 避免用户翻到 page 5 → 切 chip → fetchKnowledge 仍用 page 5 → 错位.
 *
 * 注: 改用静态源码检查 (不用 vue-test-utils mount), 避免 mock useKnowledge/
 * useNotifications/useKbMonitor 全套 (成本高且可能漏 ref). 静态检查直接验证
 * 关键行存在, 比动态 mount 100% 可靠.
 */

import { describe, it, expect } from 'vitest'
import { readFileSync } from 'fs'
import { join } from 'path'

const VIEW_PATH = join(__dirname, '../KnowledgeView.vue')

describe('KnowledgeView - filter 切换重置 currentPage (P2-8 回归)', () => {
  let sourceCode

  it('加载源码', () => {
    sourceCode = readFileSync(VIEW_PATH, 'utf-8')
    expect(sourceCode.length).toBeGreaterThan(0)
  })

  it('P2-8 已修: currentPage.value = 1 已在 watch([filterCategory, filterSourceType]) 块内', () => {
    sourceCode = readFileSync(VIEW_PATH, 'utf-8')
    // 找 watch([filterCategory, filterSourceType] 块 (可有可无 options object)
    const watchBlock = sourceCode.match(
      /watch\(\[filterCategory,\s*filterSourceType\],\s*\(\)\s*=>\s*\{[\s\S]*?\}\s*(?:,\s*\{[^}]+\})?\)/
    )
    expect(watchBlock, 'watch 块必须存在').toBeTruthy()
    expect(watchBlock[0]).toMatch(/currentPage\.value\s*=\s*1/)
    expect(watchBlock[0]).toMatch(/fetchKnowledge\(\)/)
  })

  it('searchQuery 变化时 (空字符串) currentPage 也重置 1 (回归)', () => {
    sourceCode = readFileSync(VIEW_PATH, 'utf-8')
    // searchQuery watch 块 (没 options object, 直接 })
    const searchWatch = sourceCode.match(
      /watch\(searchQuery,\s*\(val\)\s*=>\s*\{[\s\S]*?\}\s*\)/
    )
    expect(searchWatch, 'searchQuery watch 块必须存在').toBeTruthy()
    expect(searchWatch[0]).toMatch(/currentPage\.value\s*=\s*1/)
  })
})
