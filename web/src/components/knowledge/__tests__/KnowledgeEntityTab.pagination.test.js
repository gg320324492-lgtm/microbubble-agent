// KnowledgeEntityTab.pagination.test.js — W86 mini-8 el-pagination 暗色主题颜色 + emit page-change
//
// 根因 (派工 v6 §1.2 真验证, 3 路搜证):
//   1. KnowledgeEntityTab.vue:79 @current-change emit('page-change', p), KnowledgeView.vue
//      父组件之前没监听 @page-change → 点击翻页 emit 出去没人接 → 数据不变 → 用户看到"无反应".
//   2. KnowledgeEntityTab.vue:358 .entity-pagination 没居中 + 暗色主题下页码数字
//      与按钮文字使用 --el-text-color-regular, 在暗色背景下不够亮 → 用户反馈"看不清".
//
// 修复 (派工前提铁律 12 第 9 条: 0 production code 例外本批纯前端 fix):
//   1. KnowledgeEntityTab.vue .entity-pagination 加 display:flex + justify-content:center (居中).
//   2. KnowledgeEntityTab.vue [data-theme="dark"] .entity-pagination 显式覆盖
//      .el-pager li / .btn-prev / .btn-next 的 color + background, 使用项目自有 token
//      --color-text-regular / --color-primary / --color-border-base.
//   3. KnowledgeView.vue:88 加 @page-change="handleEntityPageChange" 监听.
//   4. KnowledgeView.vue 加 handleEntityPageChange(page) 函数: entityPage.value = page
//      + entityTabRef.value.searchEntitiesLocal() 触发子组件复用 searchEntitiesLocal 直接发请求.
//
// 验证 (4 个 e2e 测试):
//   1. mount 时 el-pagination 渲染 (current-page = props.entityPage, total = props.entityTotal)
//   2. 点击翻页触发 emit('page-change', 2) — 验证子组件事件链路正确
//   3. 暗色主题覆盖 .el-pager li color 强制为 --color-text-regular (CSS 字符串断言)
//   4. 居中布局: .entity-pagination 有 display:flex + justify-content:center
import { mount, flushPromises } from '@vue/test-utils'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { readFileSync } from 'fs'
import { resolve } from 'path'

vi.mock('echarts', () => {
  const makeInstance = () => ({
    setOption: vi.fn(),
    on: vi.fn(),
    off: vi.fn(),
    dispose: vi.fn(),
    resize: vi.fn(),
  })
  return { default: { init: vi.fn(makeInstance) }, init: vi.fn(makeInstance) }
})

vi.mock('element-plus', () => ({
  ElMessage: { error: vi.fn(), success: vi.fn() },
}))

vi.mock('axios', () => ({
  default: {
    get: vi.fn(() => Promise.resolve({ data: { items: [], total: 0, nodes: [], edges: [] } })),
  },
}))

import KnowledgeEntityTab from '@/components/knowledge/KnowledgeEntityTab.vue'

const COMPONENT_PATH = resolve(__dirname, '../KnowledgeEntityTab.vue')

// EP 组件全局 stub (test-utils mount 不会自动 app.use(ElementPlus))
const globalStubs = {
  'el-pagination': {
    name: 'ElPagination',
    props: ['currentPage', 'pageSize', 'total', 'layout'],
    emits: ['current-change', 'update:current-page'],
    template: '<div class="el-pagination"><slot /></div>',
  },
  'el-col': { template: '<div><slot /></div>' },
  'el-row': { template: '<div><slot /></div>' },
  'el-progress': {
    name: 'ElProgress',
    props: ['percentage', 'strokeWidth', 'showText'],
    template: '<div class="el-progress" :data-percentage="percentage" />',
  },
  'el-button': { template: '<button><slot /></button>' },
  'el-input': { template: '<input />' },
}

const mountTab = (propsOverride = {}) => {
  const baseProps = {
    entityList: [],
    entityTotal: 0,
    entityPage: 1,
    entityGraphData: { nodes: [], edges: [] },
  }
  return mount(KnowledgeEntityTab, {
    props: { ...baseProps, ...propsOverride },
    global: {
      stubs: {
        ...globalStubs,
        KnowledgeGraphExplorer: { template: '<div data-testid="kg-explorer-stub" />' },
      },
    },
  })
}

describe('W86 mini-8 el-pagination 暗色主题颜色 + emit page-change', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('Fix 1.1 el-pagination 渲染 — current-page=props.entityPage, total=props.entityTotal', async () => {
    const wrapper = mountTab({ entityTotal: 131, entityPage: 3 })
    await flushPromises()
    const pag = wrapper.findComponent({ name: 'ElPagination' })
    expect(pag.exists()).toBe(true)
    expect(pag.props('currentPage')).toBe(3)
    expect(pag.props('total')).toBe(131)
    expect(pag.props('pageSize')).toBe(20)
    expect(pag.props('layout')).toBe('total, prev, pager, next')
  })

  it('Fix 1.2 点击 next 按钮 → emit page-change 事件 (子组件事件链路正确)', async () => {
    const wrapper = mountTab({ entityTotal: 131, entityPage: 1 })
    await flushPromises()
    const pag = wrapper.findComponent({ name: 'ElPagination' })
    expect(pag.exists()).toBe(true)
    // EP pagination 在测试中通过 emit current-change 模拟点击下一页
    await pag.vm.$emit('current-change', 2)
    await flushPromises()
    const pageChangeEmits = wrapper.emitted('page-change')
    expect(pageChangeEmits).toBeTruthy()
    expect(pageChangeEmits.length).toBe(1)
    expect(pageChangeEmits[0]).toEqual([2])
  })

  it('Fix 2.1 暗色主题 CSS 覆盖 .el-pager li color 强制为 --color-text-regular', () => {
    const content = readFileSync(COMPONENT_PATH, 'utf8')
    expect(content).toMatch(/\[data-theme="dark"\]\s*\.entity-pagination\s*\.el-pager li/)
    expect(content).toMatch(/color:\s*var\(--color-text-regular\)\s*!important/)
    expect(content).toMatch(/\[data-theme="dark"\]\s*\.entity-pagination\s*\.el-pager li\.is-active/)
    expect(content).toMatch(/background-color:\s*var\(--color-primary\)\s*!important/)
  })

  it('Fix 2.2 .entity-pagination 居中布局 — display:flex + justify-content:center', () => {
    const content = readFileSync(COMPONENT_PATH, 'utf8')
    expect(content).toMatch(/\.entity-pagination\s*\{[^}]*display:\s*flex[^}]*justify-content:\s*center/)
  })
})
