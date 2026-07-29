/**
 * KnowledgeView.entity-pagination.test.js — W86 mini-8 父组件监听 @page-change 回归
 *
 * 根因 (派工 v6 §1.2 真验证):
 *   KnowledgeEntityTab.vue:79 @current-change emit('page-change', p), KnowledgeView.vue
 *   之前没监听 @page-change → 点击翻页 emit 出去没人接 → 数据不变 → 用户看到"无反应".
 *
 * 修复:
 *   1. KnowledgeView.vue KnowledgeEntityTab 上加 @page-change="handleEntityPageChange" 监听
 *   2. KnowledgeView.vue 加 handleEntityPageChange(page) 函数:
 *      entityPage.value = page + entityTabRef.value?.searchEntitiesLocal()
 *      → entityPage ref 更新 (与 useKnowledge composable 单向数据流保持一致)
 *      → 复用子组件 searchEntitiesLocal 直接发请求 (与 watch(activeTab) 同路径, 不重复实现)
 *
 * 验证 (静态源码回归, 与 P2-8 filter-reset 模式一致):
 *   1. KnowledgeEntityTab 标签含 @page-change 监听
 *   2. handleEntityPageChange 函数存在, 含 entityPage.value = page
 *   3. handleEntityPageChange 函数含 searchEntitiesLocal() 调用
 */

import { describe, it, expect } from 'vitest'
import { readFileSync } from 'fs'
import { join } from 'path'

const VIEW_PATH = join(__dirname, '../KnowledgeView.vue')

describe('KnowledgeView - W86 mini-8 entity pagination 父组件监听 (回归)', () => {
  let sourceCode

  it('加载源码', () => {
    sourceCode = readFileSync(VIEW_PATH, 'utf-8')
    expect(sourceCode.length).toBeGreaterThan(0)
  })

  it('Fix 1: KnowledgeEntityTab 上加 @page-change 监听', () => {
    sourceCode = readFileSync(VIEW_PATH, 'utf-8')
    // 找 KnowledgeEntityTab 开始标签到结束标签
    const tabMatch = sourceCode.match(/<KnowledgeEntityTab[\s\S]*?\/>/)
    expect(tabMatch, 'KnowledgeEntityTab 标签必须存在').toBeTruthy()
    expect(tabMatch[0]).toMatch(/@page-change\s*=\s*"handleEntityPageChange"/)
  })

  it('Fix 2: handleEntityPageChange 函数存在, 写入 entityPage.value', () => {
    sourceCode = readFileSync(VIEW_PATH, 'utf-8')
    // 找函数定义
    const fnMatch = sourceCode.match(
      /const\s+handleEntityPageChange\s*=\s*\(\s*page\s*\)\s*=>\s*\{[\s\S]*?\n\}/
    )
    expect(fnMatch, 'handleEntityPageChange 函数必须存在').toBeTruthy()
    expect(fnMatch[0]).toMatch(/entityPage\.value\s*=\s*page/)
  })

  it('Fix 3: handleEntityPageChange 函数含 searchEntitiesLocal() 调用 (复用子组件 search 路径)', () => {
    sourceCode = readFileSync(VIEW_PATH, 'utf-8')
    const fnMatch = sourceCode.match(
      /const\s+handleEntityPageChange\s*=\s*\(\s*page\s*\)\s*=>\s*\{[\s\S]*?\n\}/
    )
    expect(fnMatch, 'handleEntityPageChange 函数必须存在').toBeTruthy()
    expect(fnMatch[0]).toMatch(/entityTabRef\.value\?\.searchEntitiesLocal\(\)/)
  })
})
