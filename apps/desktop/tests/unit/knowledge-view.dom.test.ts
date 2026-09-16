// @vitest-environment jsdom
// KnowledgeView 占位转正契约 — 空态引导 / 列表渲染 / 检索入口（api stub 驱动）
import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import KnowledgeView from '@renderer/views/KnowledgeView.vue'
import type { KnowledgeDocMeta, KnowledgeSearchHit } from '@shared/types'

const doc = (id: number, title: string): KnowledgeDocMeta => ({
  id,
  title,
  tags: ['实验'],
  fileName: `${title}.md`,
  fileSize: 120,
  source: 'local_import',
  createdAt: 1789000000000,
  updatedAt: 1789000000000
})

function stubKb(list: KnowledgeDocMeta[], search: KnowledgeSearchHit[]): void {
  Object.assign(window, {
    api: {
      knowledge: {
        list: vi.fn().mockResolvedValue(list),
        get: vi.fn(),
        import: vi.fn(),
        update: vi.fn(),
        delete: vi.fn(),
        search: vi.fn().mockResolvedValue(search)
      }
    }
  })
}

beforeEach(() => {
  // 每用例重新挂 stub
})

describe('KnowledgeView（知识库占位转正）', () => {
  it('空库 — 显示导入按钮与空态引导文案', async () => {
    stubKb([], [])
    const w = mount(KnowledgeView)
    await flushPromises()
    expect(w.get('[data-testid="kb-import"]').text()).toContain('导入文档')
    expect(w.get('[data-testid="kb-empty"]').text()).toContain('知识库还是空的')
  })

  it('列表 — 标题/标签/时间渲染；输入关键词触发检索并显示命中片段', async () => {
    stubKb([doc(1, '臭氧实验笔记')], [
      { id: 1, title: '臭氧实验笔记', tags: ['实验'], snippet: '…臭氧微纳米气泡…', highlight: { start: 1, end: 3 }, updatedAt: 1789000000000 }
    ])
    const w = mount(KnowledgeView)
    await flushPromises()
    expect(w.text()).toContain('臭氧实验笔记')
    expect(w.text()).toContain('实验')
    // 输入即检
    await w.get('[data-testid="kb-search"]').setValue('臭氧')
    await w.get('[data-testid="kb-search"]').trigger('input')
    await flushPromises()
    expect(window.api.knowledge.search).toHaveBeenCalledWith('臭氧')
    expect(w.text()).toContain('臭氧微纳米气泡')
  })
})
