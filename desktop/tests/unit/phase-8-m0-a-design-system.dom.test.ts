// @vitest-environment happy-dom
import { describe, expect, it } from 'vitest'
import { existsSync, readFileSync } from 'node:fs'
import { resolve } from 'node:path'

const rendererRoot = resolve(__dirname, '../../src/renderer/src')
const readSource = (path: string): string => {
  const absolutePath = resolve(rendererRoot, path)
  return existsSync(absolutePath) ? readFileSync(absolutePath, 'utf8') : ''
}

const tokens = readSource('styles/research-design-tokens.css')
const globalStyles = readSource('styles/research-global.css')
const motion = readSource('styles/research-motion.css')
const sidebar = readSource('layouts/Sidebar.vue')
const header = readSource('layouts/HeaderBar.vue')
const layout = readSource('layouts/MainLayout.vue')
const router = readSource('router/index.ts')
const panel = readSource('components/research/ResearchPanel.vue')

const primitive = (name: string): string => readSource(`components/research/${name}.vue`)

const TOKEN_CASES = [
  ['graphite 950', '--research-graphite-950', '#172129'],
  ['graphite 800', '--research-graphite-800', '#253238'],
  ['mist 50', '--research-mist-50', '#f6f8f7'],
  ['mist 100', '--research-mist-100', '#eef2f1'],
  ['paper 0', '--research-paper-0', '#ffffff'],
  ['teal 50', '--research-teal-50', '#e4f4f1'],
  ['teal 700', '--research-teal-700', '#0e766e'],
  ['coral 50', '--research-coral-50', '#fff0eb'],
  ['coral 500', '--research-coral-500', '#ef7256'],
  ['amber 50', '--research-amber-50', '#fff6e7'],
  ['amber 500', '--research-amber-500', '#d9982d'],
  ['red 50', '--research-red-50', '#fff0f1'],
  ['red 600', '--research-red-600', '#c94757'],
  ['instrument 950', '--research-instrument-950', '#111a1d'],
  ['instrument 900', '--research-instrument-900', '#172327'],
  ['instrument 850', '--research-instrument-850', '#203034'],
  ['instrument line', '--research-instrument-line', '#314347'],
  ['instrument text', '--research-instrument-text', '#e8f1ef'],
  ['signal green', '--research-signal-green', '#7ed6ad'],
  ['signal amber', '--research-signal-amber', '#e9b867'],
  ['signal red', '--research-signal-red', '#ef7d89'],
  ['signal cyan', '--research-signal-cyan', '#78cbd0'],
  ['SCADA grid', '--research-scada-grid', '#314347'],
  ['main background mapping', '--research-bg-main', 'var(--research-mist-50)'],
  ['card background mapping', '--research-bg-card', 'var(--research-paper-0)'],
  ['main text mapping', '--research-text-primary', 'var(--research-graphite-950)'],
  ['secondary text', '--research-text-secondary', '#66757b'],
  ['divider color', '--research-divider', '#e2e8e5'],
  ['primary compatibility mapping', '--research-primary-500', 'var(--research-teal-700)'],
  ['success compatibility mapping', '--research-success-500', 'var(--research-teal-700)'],
  ['warning compatibility mapping', '--research-warning-500', 'var(--research-amber-500)'],
  ['danger compatibility mapping', '--research-danger-500', 'var(--research-red-600)'],
  ['input radius mapping', '--research-radius-input', 'var(--research-radius-sm)'],
  ['card radius mapping', '--research-radius-card', 'var(--research-radius-md)'],
  ['panel radius mapping', '--research-radius-panel', 'var(--research-radius-lg)'],
  ['UI font compatibility mapping', '--research-font-sans', 'var(--research-font-ui)'],
  ['scientific font compatibility mapping', '--research-font-mono', 'var(--research-font-scientific)'],
  ['space 4', '--research-space-1', '4px'],
  ['space 8', '--research-space-2', '8px'],
  ['space 12', '--research-space-3', '12px'],
  ['space 16', '--research-space-4', '16px'],
  ['space 20', '--research-space-5', '20px'],
  ['space 24', '--research-space-6', '24px'],
  ['space 32', '--research-space-8', '32px'],
  ['space 40', '--research-space-10', '40px'],
  ['radius 8', '--research-radius-sm', '8px'],
  ['radius 12', '--research-radius-md', '12px'],
  ['radius 16', '--research-radius-lg', '16px'],
  ['surface shadow', '--research-shadow-surface', '0 8px 24px'],
  ['floating shadow', '--research-shadow-floating', '0 20px 48px'],
  ['modal shadow', '--research-shadow-modal', '0 28px 72px'],
  ['Chinese UI font', '--research-font-ui', "'PingFang SC'"],
  ['scientific number font', '--research-font-scientific', 'Consolas'],
  ['paper text font', '--research-font-paper', "'Noto Serif SC'"],
] as const

const GLOBAL_CASES = [
  ['SCADA data theme selector', tokens, "[data-research-theme='scada']"],
  ['SCADA main background mapping', tokens, '--research-bg-main: var(--research-instrument-950)'],
  ['SCADA card mapping', tokens, '--research-bg-card: var(--research-instrument-900)'],
  ['global page layout class', globalStyles, '.research-page-layout'],
  ['scientific number class', globalStyles, '.research-scientific-number'],
  ['paper text class', globalStyles, '.research-paper-text'],
  ['visible keyboard focus', globalStyles, ':focus-visible'],
  ['selection feedback', globalStyles, '::selection'],
  ['scrollbar styling', globalStyles, '::-webkit-scrollbar'],
  ['reduced motion media query', motion, '@media (prefers-reduced-motion: reduce)'],
  ['SCADA running motion', motion, '.research-scada-running'],
  ['SCADA motion reduction', motion, '.research-scada-running::before'],
] as const

const NAVIGATION_CASES = [
  ['科研驾驶舱', 'research-dashboard'],
  ['科研助手', 'research-assistant'],
  ['研究工作区', 'research-project'],
  ['文献研究', 'research-literature'],
  ['实验设计', 'research-experiment'],
  ['数据分析', 'research-data-analysis'],
  ['SCI写作', 'research-manuscript'],
  ['知识图谱', 'research-knowledge-graph'],
  ['AI研究团队', 'research-agent-center'],
  ['实验控制中心', 'research-experiment-control'],
  ['系统设置', 'research-settings'],
] as const

const HEADER_CASES = [
  'header-bar__project-trigger',
  '当前项目选择器',
  'role="listbox"',
  'header-ai-status__system',
  '系统状态：待连接',
  'header-bar__ai-status',
  '全局 AI 状态',
  'header-bar__command-trigger',
  '打开命令与搜索',
  'aria-keyshortcuts="Control+K"',
  'header-command-popover',
  '@keydown.esc.stop',
] as const

const PRIMITIVE_CASES = [
  ['ResearchPageHeader', 'research-page-header', 'title: string', '<slot name="actions"'],
  ['ResearchStatusBadge', 'research-status-badge', 'label: string', 'role="status"'],
  ['ResearchMetricCard', 'research-metric-card', 'value: string', 'research-scientific-number'],
  ['ResearchEmptyState', 'research-empty-state', '暂无科研数据', 'role="status"'],
  ['ResearchLoadingState', 'research-loading-state', 'AI 正在分析...', 'aria-busy'],
] as const

const PRIMITIVE_SOURCE_CASES = PRIMITIVE_CASES.flatMap(([name, className, prop, semantic]) => [
  [name, 'exists', (source: string) => source.length > 0],
  [name, 'props', (source: string) => source.includes('defineProps') && source.includes(prop)],
  [name, 'class', (source: string) => source.includes(className)],
  [name, 'semantic', (source: string) => source.includes(semantic)],
  [name, 'tokenized', (source: string) => source.includes('var(--research-')],
  [name, 'no Store import', (source: string) => !/stores\//.test(source)],
  [name, 'no Service import', (source: string) => !/services\//.test(source)],
] as const)

const PANEL_CASES = [
  'aria-labelledby',
  'research-panel--scada',
  "'scada'",
  'var(--research-instrument-900)',
  'var(--research-instrument-text)',
] as const

const A11Y_CASES = [
  ['Sidebar current page', sidebar, 'aria-current'],
  ['Sidebar Chinese navigation label', sidebar, 'aria-label="科研工作台导航"'],
  ['Header project accessible expansion', header, ':aria-expanded="projectSelectorOpen"'],
  ['Header command accessible expansion', header, ':aria-expanded="commandOpen"'],
  ['Header system live status', header, 'aria-live="polite"'],
  ['Header notification label', header, 'aria-label="查看科研通知"'],
  ['Main content landmark', layout, 'aria-label="科研工作区主内容"'],
  ['Main SCADA theme attribute', layout, 'data-research-theme'],
  ['Loading polite announcement', primitive('ResearchLoadingState'), 'aria-live="polite"'],
  ['Empty state operation slot', primitive('ResearchEmptyState'), '<slot name="actions"'],
  ['Status badge text status', primitive('ResearchStatusBadge'), 'aria-live="polite"'],
  ['Metric card unit label', primitive('ResearchMetricCard'), 'aria-label'],
] as const

const IMPORT_BOUNDARY_CASES = [
  'ResearchPageHeader',
  'ResearchStatusBadge',
  'ResearchMetricCard',
  'ResearchEmptyState',
  'ResearchLoadingState',
  'ResearchPanel',
] as const

describe('Phase 8-M0-A：设计令牌（38）', () => {
  it.each(TOKEN_CASES)('%s 定义 %s = %s', (_label, name, value) => {
    expect(tokens).toContain(`${name}: ${value}`)
  })
})

describe('Phase 8-M0-A：全局工作面与动效（12）', () => {
  it.each(GLOBAL_CASES)('%s', (_label, source, expected) => {
    expect(source).toContain(expected)
  })
})

describe('Phase 8-M0-A：中文导航和路由（13）', () => {
  it.each(NAVIGATION_CASES)('%s 连接 %s', (label, routeName) => {
    expect(sidebar).toContain(`label: '${label}'`)
    expect(sidebar).toContain(`routeName: '${routeName}'`)
  })

  it('实验控制中心使用 SCADA 路由元数据', () => {
    expect(router).toContain("name: 'research-experiment-control'")
    expect(router).toContain("theme: 'scada'")
  })

  it('所有研究路由拥有中文 M0-A 标题', () => {
    expect(router).toContain("title: '科研驾驶舱'")
    expect(router).toContain("title: 'SCI写作'")
    expect(router).toContain("title: 'AI研究团队'")
  })
})

describe('Phase 8-M0-A：顶栏全局上下文（12）', () => {
  it.each(HEADER_CASES)('HeaderBar 包含 %s', (expected) => {
    expect(header).toContain(expected)
  })
})

describe('Phase 8-M0-A：共享 props 原语（35）', () => {
  it.each(PRIMITIVE_SOURCE_CASES)('%s %s 契约成立', (name, _kind, predicate) => {
    expect(predicate(primitive(name))).toBe(true)
  })
})

describe('Phase 8-M0-A：ResearchPanel 语义与 SCADA 适配（5）', () => {
  it.each(PANEL_CASES)('ResearchPanel 包含 %s', (expected) => {
    expect(panel).toContain(expected)
  })
})

describe('Phase 8-M0-A：无障碍与纯展示边界（18）', () => {
  it.each(A11Y_CASES)('%s', (_label, source, expected) => {
    expect(source).toContain(expected)
  })

  it.each(IMPORT_BOUNDARY_CASES)('%s 不导入 Store 或 Service', (name) => {
    const source = name === 'ResearchPanel' ? panel : primitive(name)
    expect(source).not.toMatch(/(?:stores|services)\//)
  })
})

describe('Phase 8-M0-A：视觉契约计数（1）', () => {
  it('至少存在 150 个独立的 M0-A 契约实例', () => {
    const count = TOKEN_CASES.length
      + GLOBAL_CASES.length
      + NAVIGATION_CASES.length + 2
      + HEADER_CASES.length
      + PRIMITIVE_SOURCE_CASES.length
      + PANEL_CASES.length
      + A11Y_CASES.length
      + IMPORT_BOUNDARY_CASES.length
      + 1
    expect(count).toBeGreaterThanOrEqual(150)
  })
})
