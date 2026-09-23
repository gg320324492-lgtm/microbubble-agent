// M2-3c 补完 #2 —— 侧栏网盘入口 + 知识库「0 B」修复 的 DOM 断言
//
// 为什么用真挂载：M8-2/M2-3b 双实证——模板结构性错误 typecheck 抓不到。
import { mount, flushPromises } from '@vue/test-utils'
import { afterEach, describe, expect, it, vi } from 'vitest'
import KnowledgeView from '@renderer/views/KnowledgeView.vue'

/** 桩 window.api（知识库页需要） */
function stubKnowledgeApi(docs: { id: number; title: string; tags: string[]; fileSize: number; updatedAt: number }[]): void {
  ;(globalThis as unknown as { window: Record<string, unknown> }).window = {
    api: {
      knowledge: {
        sourceState: async () => ({ state: 'ready', title: '', hint: '', canOpenSettings: false, actionLabel: '' }),
        list: async () => docs,
        search: async () => [],
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

afterEach(() => {
  vi.restoreAllMocks()
})

describe('侧栏 — 网盘入口', () => {
  // 说明：SideNav 内部依赖较深（store + 组合式 useRoute），挂载测试成本高于收益；
  // 此处做**源码级断言**（导航项存在 + 顺序），**视觉由真机验证覆盖**（见交付报告）。
  it('导航表含「网盘」项、指向 /app/drive、且排在「知识库」之后', async () => {
    const { readFileSync } = await import('node:fs')
    const src = readFileSync('src/renderer/src/layouts/SideNav.vue', 'utf8')
    expect(src).toContain("to: '/app/drive'")
    expect(src).toContain("label: '网盘'")
    expect(src).toContain("icon: 'folder'")
    // 顺序：知识库在前、网盘在后（工单要求「置于知识库之后」）
    expect(src.indexOf("'/app/knowledge'")).toBeGreaterThanOrEqual(0)
    expect(src.indexOf("'/app/knowledge'")).toBeLessThan(src.indexOf("'/app/drive'"))
    // 既有入口未被动过
    expect(src).toContain("to: '/app/assistant'")
  })
})

describe('知识库列表 — 「0 B」修复', () => {
  it('远程条目（fileSize=0）不显示「0 B」，改显「文档」徽标', async () => {
    stubKnowledgeApi([
      { id: 1, title: '占位条目一', tags: ['占位'], fileSize: 0, updatedAt: Date.now() },
      { id: 2, title: '占位条目二', tags: [], fileSize: 0, updatedAt: Date.now() }
    ])
    const w = mount(KnowledgeView, { global: { stubs: { transition: false } } })
    await flushPromises()
    await flushPromises()
    const text = w.text()
    // ★ 核心断言：不再出现误导性的「0 B」
    expect(text).not.toContain('0 B')
    // 改为类型徽标
    expect(w.findAll('[data-testid="kb-badge"]').length).toBeGreaterThan(0) // UI1-3：统一「文档」徽标
    expect(text).toContain('文档')
  })

  it('UI1-3 新设计：卡片不再显示字节大小，统一「文档」徽标（父级契约无该字段）', async () => {
    stubKnowledgeApi([{ id: 3, title: '占位本地条目', tags: [], fileSize: 2048, updatedAt: Date.now() }])
    const w = mount(KnowledgeView, { global: { stubs: { transition: false } } })
    await flushPromises()
    await flushPromises()
    expect(w.text()).not.toContain('0 B')
    expect(w.text()).not.toContain('KB')
    expect(w.find('[data-testid="kb-badge"]').exists()).toBe(true)
  })
})
