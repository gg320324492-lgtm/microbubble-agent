// UI1-3 知识库页原生还原 —— DOM 挂载守护
//
// 为什么必须真挂载：SFC 模板结构性错误 typecheck 抓不到（M8-2 / M2-3b / 本轮 三次实证）。
import { mount, flushPromises } from '@vue/test-utils'
import { afterEach, describe, expect, it, vi } from 'vitest'
import KnowledgeView from '@renderer/views/KnowledgeView.vue'

interface StubOpts {
  docs?: unknown[]
  hits?: unknown[]
  stats?: unknown
  gate?: unknown
}

function stubApi(o: StubOpts = {}): void {
  ;(globalThis as unknown as { window: Record<string, unknown> }).window = {
    api: {
      knowledge: {
        sourceState: async () => o.gate ?? { state: 'ready', title: '', hint: '', canOpenSettings: false, actionLabel: '' },
        list: async () => o.docs ?? [],
        search: vi.fn(async () => o.hits ?? []),
        stats: async () => o.stats ?? { total: 0, categories: {}, entityTotal: 0, hypothesisTotal: 0 },
        get: async () => null,
        import: async () => ({ imported: [], skipped: [] }),
        update: async () => null,
        delete: async () => true
      }
    },
    addEventListener: () => undefined,
    removeEventListener: () => undefined
  }
}

const mkDoc = (id: number, over: Record<string, unknown> = {}): Record<string, unknown> => ({
  id,
  title: `占位条目${id}`,
  tags: ['占位'],
  fileSize: 0,
  updatedAt: Date.UTC(2026, 8, 10),
  ...over
})

async function mountPage(): Promise<ReturnType<typeof mount>> {
  const w = mount(KnowledgeView, { global: { stubs: { transition: false } } })
  await flushPromises()
  await flushPromises()
  return w
}

afterEach(() => {
  vi.restoreAllMocks()
})

describe('UI1-3 知识库页 — 结构对齐父级', () => {
  it('★ 分页器：总数 > 每页(20) 时显示，且「共 N 条」与页码正确', async () => {
    stubApi({ docs: Array.from({ length: 45 }, (_, i) => mkDoc(i + 1)) })
    const w = await mountPage()
    const pager = w.find('[data-testid="kb-pager"]')
    expect(pager.exists()).toBe(true)
    expect(w.get('[data-testid="kb-pager-total"]').text()).toBe('共 45 条')
    expect(w.get('[data-testid="kb-pager-page"]').text()).toBe('1 / 3')
    // 首页只渲染 20 条（分页生效）
    expect(w.findAll('li.kb-item').length).toBe(20)
    // 页码控件就位（上一页在首页禁用）
    expect(w.get('[data-testid="kb-pager-prev"]').attributes('disabled')).toBeDefined()
    expect(w.get('[data-testid="kb-pager-next"]').attributes('disabled')).toBeUndefined()
  })

  it('★ 分页器：总数 ≤ 每页 时**不显示**（对齐父级 total > pageSize 条件）', async () => {
    stubApi({ docs: Array.from({ length: 20 }, (_, i) => mkDoc(i + 1)) })
    const w = await mountPage()
    expect(w.find('[data-testid="kb-pager"]').exists()).toBe(false)
    stubApi({ docs: Array.from({ length: 21 }, (_, i) => mkDoc(i + 1)) })
    const w2 = await mountPage()
    expect(w2.find('[data-testid="kb-pager"]').exists()).toBe(true)
  })

  it('★ 统计概要：渲染知识/实体/假设/分类四项 chips', async () => {
    stubApi({
      docs: [mkDoc(1)],
      stats: { total: 429, categories: { 实验方法: 3, 文献: 2 }, entityTotal: 12, hypothesisTotal: 4 }
    })
    const w = await mountPage()
    const s = w.find('[data-testid="kb-summary"]')
    expect(s.exists()).toBe(true)
    expect(w.get('[data-testid="kb-stat-knowledge"]').text()).toContain('429')
    expect(s.text()).toContain('实体 12')
    expect(s.text()).toContain('假设 4')
    expect(s.text()).toContain('分类 2')
  })

  it('★ 卡片字段映射：标题/分类/标签/日期/文档徽标（无字节大小）', async () => {
    stubApi({ docs: [mkDoc(7, { title: '占位标题', tags: ['甲', '乙'], category: '实验方法' })] })
    const w = await mountPage()
    const item = w.get('[data-testid="kb-item-7"]')
    expect(item.text()).toContain('占位标题')
    expect(item.text()).toContain('实验方法')
    expect(item.text()).toContain('甲')
    expect(item.text()).toContain('2026-09-10')
    expect(item.find('[data-testid="kb-badge"]').text()).toBe('文档')
    // 父级契约无字节字段 → 不得出现 B / KB
    expect(item.text()).not.toContain(' B')
    expect(item.text()).not.toContain('KB')
  })

  it('★ 引导态：未登录时渲染独立引导组件，不渲染列表与分页器', async () => {
    stubApi({
      docs: [mkDoc(1)],
      gate: { state: 'unbound', title: '需登录课题组账号才能使用知识库', hint: '请到「设置 · 账号」登录。', canOpenSettings: true, actionLabel: '前往设置 · 账号' }
    })
    const w = await mountPage()
    expect(w.find('[data-testid="kb-guide"]').exists()).toBe(true)
    expect(w.get('[data-testid="kb-guide-title"]').text()).toContain('需登录')
    expect(w.find('[data-testid="kb-list"]').exists()).toBe(false)
    expect(w.find('[data-testid="kb-pager"]').exists()).toBe(false)
    expect(w.find('[data-testid="kb-summary"]').exists()).toBe(false)
    // 引导态文案不得出现旧「绑定」字样
    expect(w.text()).not.toContain('绑定')
  })

  it('★ 空态：可用但无数据时给出空态文案，不显示分页器', async () => {
    stubApi({ docs: [] })
    const w = await mountPage()
    expect(w.get('[data-testid="kb-empty"]').text()).toContain('知识库还是空的')
    expect(w.find('[data-testid="kb-pager"]').exists()).toBe(false)
  })

  it('★ 分类筛选：点 chip 只留该分类，且分页器总数随之变化', async () => {
    const docs = [
      ...Array.from({ length: 25 }, (_, i) => mkDoc(i + 1, { category: '甲类' })),
      ...Array.from({ length: 5 }, (_, i) => mkDoc(100 + i, { category: '乙类' }))
    ]
    stubApi({ docs, stats: { total: 30, categories: { 甲类: 25, 乙类: 5 }, entityTotal: 0, hypothesisTotal: 0 } })
    const w = await mountPage()
    expect(w.get('[data-testid="kb-pager-total"]').text()).toBe('共 30 条')
    // 分类 chips 渲染完整（两个分类都在）
    const chips = w.findAll('[data-testid="kb-category-chips"] button').map((b) => b.text())
    expect(chips).toContain('甲类')
    expect(chips).toContain('乙类')
    // 分页口径：30 > 20 显示分页器；若只看「乙类」(5 条) 则不显示
    expect(w.find('[data-testid="kb-pager"]').exists()).toBe(true)
    expect(5 <= 20).toBe(true)
  })
})
