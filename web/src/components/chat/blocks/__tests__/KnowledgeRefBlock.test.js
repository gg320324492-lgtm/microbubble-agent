/**
 * @fileoverview KnowledgeRefBlock.vue a11y 测试 (W101 P3-A11Y +2)
 *
 * 5 case 覆盖:
 * ① root role=list + aria-label
 * ② 每个 ref-item role=listitem + tabindex + aria-label (含 score)
 * ③ Enter 键盘触发跳转 (W101 +2 新增)
 * ④ Space 键盘触发跳转 (W101 +2 新增)
 * ⑤ header role=heading + aria-level=3
 *
 * 派工前提 (类 20.140 实战): 渲染列表卡片必须 role=list + role=listitem, 否则
 * 屏幕阅读器报 "list of N items" 但识别不到项目. 此测试强制该模式.
 *
 * 测试策略: mock vue-router (避免依赖实际路由表)
 */
import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { createRouter, createMemoryHistory } from 'vue-router'
import KnowledgeRefBlock from '../KnowledgeRefBlock.vue'

// Mock vue-router push
const pushMock = vi.fn()
const router = createRouter({
  history: createMemoryHistory(),
  routes: [{ path: '/knowledge/:id', name: 'knowledge', component: { template: '<div/>' } }],
})
router.push = pushMock

function makeWrapper(results = []) {
  return mount(KnowledgeRefBlock, {
    props: {
      block: { data: { results } },
      citations: [],
    },
    global: { plugins: [router] },
  })
}

const sampleResults = [
  { id: 1, title: '微纳米气泡综述', content: '微纳米气泡是一种直径小于...', snippet: '微纳米气泡', score: 0.95, category: '综述', tags: ['气泡'] },
  { id: 2, title: '水处理应用', content: '在水处理领域...', snippet: '水处理应用', score: 0.82, category: '应用', tags: [] },
]

describe('KnowledgeRefBlock a11y (W101 +2)', () => {
  beforeEach(() => {
    pushMock.mockClear()
  })

  it('① root: role="list" + aria-label="知识库引用列表"', () => {
    const w = makeWrapper(sampleResults)
    const root = w.find('.kb-ref')
    expect(root.attributes('role')).toBe('list')
    expect(root.attributes('aria-label')).toBe('知识库引用列表')
  })

  it('② ref-item: role=listitem + tabindex=0 + aria-label (含相似度)', () => {
    const w = makeWrapper(sampleResults)
    const items = w.findAll('.ref-item')
    expect(items.length).toBe(2)
    items.forEach((item, i) => {
      expect(item.attributes('role')).toBe('listitem')
      expect(item.attributes('tabindex')).toBe('0')
      const label = item.attributes('aria-label') || ''
      expect(label).toContain(`知识引用 ${i + 1}`)
      expect(label).toContain(sampleResults[i].title)
      // 每个 item 的 aria-label 含自身的 score
      const expectedScore = Math.round(sampleResults[i].score * 100) + '%'
      expect(label).toContain(expectedScore)
    })
  })

  it('③ Enter 键盘触发路由跳转', async () => {
    const w = makeWrapper(sampleResults)
    const firstItem = w.findAll('.ref-item')[0]
    await firstItem.trigger('keydown', { key: 'Enter' })
    expect(pushMock).toHaveBeenCalledWith('/knowledge/1')
  })

  it('④ Space 键盘触发路由跳转', async () => {
    const w = makeWrapper(sampleResults)
    const secondItem = w.findAll('.ref-item')[1]
    await secondItem.trigger('keydown', { key: ' ' })
    expect(pushMock).toHaveBeenCalledWith('/knowledge/2')
  })

  it('⑤ header: role=heading + aria-level=3', () => {
    const w = makeWrapper(sampleResults)
    const header = w.find('.card-header')
    expect(header.attributes('role')).toBe('heading')
    expect(header.attributes('aria-level')).toBe('3')
  })
})

describe('KnowledgeRefBlock a11y — 空状态', () => {
  it('空 results 时仍渲染 list 容器 (空 list 仍需 role)', () => {
    const w = makeWrapper([])
    const root = w.find('.kb-ref')
    expect(root.attributes('role')).toBe('list')
    expect(w.find('.empty').exists()).toBe(true)
  })
})