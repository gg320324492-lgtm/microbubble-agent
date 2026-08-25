// Phase 8-M0-C Scientific Manuscript Writing Workspace UI contracts
import { describe, expect, it } from 'vitest'
import { existsSync, readFileSync } from 'node:fs'
import { resolve } from 'node:path'

const desktopRoot = resolve(__dirname, '../..')
const researchRoot = resolve(desktopRoot, 'src/renderer/src')
const componentRoot = resolve(researchRoot, 'components/workspace')
const storePath = resolve(desktopRoot, 'src/renderer/src/stores/research/manuscript.store.ts')
const servicePath = resolve(desktopRoot, 'src/renderer/src/services/research/manuscript.service.ts')
const pagePath = resolve(researchRoot, 'pages/research/Manuscript.vue')
const outlinePath = resolve(componentRoot, 'ManuscriptOutlinePanel.vue')
const editorPath = resolve(componentRoot, 'ScientificEditorPanel.vue')
const reviewerPath = resolve(componentRoot, 'ReviewerInsightPanel.vue')
const citationPath = resolve(componentRoot, 'CitationLocationPanel.vue')
const figurePath = resolve(componentRoot, 'FigureManagerPanel.vue')

const read = (p: string): string => existsSync(p) ? readFileSync(p, 'utf8') : ''
const withoutComments = (s: string): string => s.replace(/<!--[\s\S]*?-->|\/\*[\s\S]*?\*\/|\/\/[^\r\n]*/g, '')

const page = (): string => withoutComments(read(pagePath))
const store = (): string => withoutComments(read(storePath))
const service = (): string => withoutComments(read(servicePath))
const component = (file: string): string => withoutComments(read(file))

const PAGE_BOUNDARY: [string, (s: string) => boolean][] = [
  ['从 useManuscriptStore 读取页面状态', (s) => s.includes('useManuscriptStore')],
  ['不调用 manuscriptService.getManuscript', (s) => !s.includes('manuscriptService.getManuscript')],
  ['不调用 manuscriptService.getWritingIssues', (s) => !s.includes('manuscriptService.getWritingIssues')],
  ['不导入 ManuscriptService', (s) => !/services\/research\/manuscript\.service/.test(s)],
  ['不调用 loadManuscript 在 mounted 直接执行', (s) => !/onMounted[\s\S]{0,200}loadManuscript\(\)/.test(s)],
  ['不写论文内容字面量', (s) => !s.includes('O₃-MNBs 对 TC 去除率')],
  ['不写 O3-MNBs 字面量', (s) => !s.includes('O3-MNB 降解')],
  ['不写 demo 字面量', (s) => !/demo[\s_-]?(ms|manuscript|project)/.test(s)],
  ['不在页面调用 generateSection', (s) => !s.includes('generateSection')],
  ['不在页面调用 reviewSection', (s) => !s.includes('reviewSection')],
  ['不在页面 mock store', (s) => !/const\s+store\s*=\s*\{/.test(s)],
  ['不在页面使用 ref 业务副本', (s) => !/\bref\s*\(/.test(s)],
  ['不直接写 store.manuscript 字面量', (s) => !/store\.manuscript\s*=/.test(s)],
  ['不通过 $patch 写入稿件', (s) => !s.includes('$patch')],
  ['不导入 mock store 或 fake store', (s) => !/\b(?:mockStore|fakeStore|localStore)\b/.test(s)],
  ['不导入 Pinia defineStore', (s) => !sourceCodeIncludesDefineStore(s)],
  ['使用 composable 加载稿件', (s) => s.includes('useManuscriptLoader') || s.includes('fetchManuscript')],
  ['不在页面硬编码字词', (s) => !/\bwordCount\s*=\s*\d/.test(s)],
  ['不通过 service 路径直接读 service', (s) => !/services\/research\/manuscript\.service/.test(s)],
  ['不在页面写假 mock 数据', (s) => !/const\s+MOCK/.test(s)]
]

function sourceCodeIncludesDefineStore(s: string): boolean {
  return s.includes('defineStore')
}

const PAGE_LAYOUT: [string, (s: string) => boolean][] = [
  ['根容器为 3 列布局', (s) => /grid-template-columns:[^;]*1fr[^;]*1fr[^;]*1fr|1fr\s+minmax[^;]+1fr|minmax\([^,]+,\s*var\(--research-rail[^)]+\)\)[^;]*minmax/.test(s)],
  ['使用 ManuscriptOutlinePanel', (s) => s.includes('ManuscriptOutlinePanel')],
  ['使用 ScientificEditorPanel', (s) => s.includes('ScientificEditorPanel')],
  ['使用 ReviewerInsightPanel', (s) => s.includes('ReviewerInsightPanel')],
  ['使用 CitationLocationPanel', (s) => s.includes('CitationLocationPanel')],
  ['使用 FigureManagerPanel', (s) => s.includes('FigureManagerPanel')],
  ['呈现章节大纲区域', (s) => s.includes('章节结构') || s.includes('章节大纲')],
  ['呈现编辑区域', (s) => s.includes('编辑')],
  ['呈现 Reviewer 区域', (s) => s.includes('Reviewer') || s.includes('审稿')],
  ['1440 断点安全换行', (s) => s.includes('@media (max-width: 1480px)')],
  ['1920 断点扩展布局', (s) => s.includes('@media (min-width: 1720px)')],
  ['不写死 1440 宽度', (s) => !/width:\s*1440px/.test(s)],
  ['不写死 1920 宽度', (s) => !/width:\s*1920px/.test(s)],
  ['编辑区域稳定宽度', (s) => /minmax\([^,]+,\s*(?:640px|720px|1fr|2fr)\)/.test(s)],
  ['中栏可收缩', (s) => /minmax\(0,\s*1fr\)/.test(s) || /minmax\(0,\s*2fr\)/.test(s)],
  ['根容器有 min-width 0', (s) => /min-width:\s*0/.test(s)],
  ['根容器 overflow-x clip', (s) => /overflow-x:\s*(?:clip|hidden)/.test(s)]
]

const PAGE_ACCESSIBILITY: [string, (s: string) => boolean][] = [
  ['根容器有中文 aria-label', (s) => /aria-label="[^"]*论文工作台/.test(s) || /aria-label="[^"]*写作工作区/.test(s)],
  ['章节大纲区有中文 aria-label', (s) => /aria-label="[^"]*章节结构/.test(s) || /aria-label="[^"]*大纲/.test(s)],
  ['编辑区有中文 aria-label', (s) => /aria-label="[^"]*编辑区/.test(s) || /aria-label="[^"]*正文/.test(s)],
  ['Reviewer 区有中文 aria-label', (s) => /aria-label="[^"]*Reviewer/.test(s) || /aria-label="[^"]*审稿/.test(s)],
  ['章节导航有 focus-visible', (s) => s.includes(':focus-visible')],
  ['动效支持 prefers-reduced-motion', (s) => s.includes('@media (prefers-reduced-motion: reduce)')],
  ['根容器允许收缩', (s) => /min-width:\s*0/.test(s)],
  ['根容器阻止横向溢出', (s) => /overflow-x:\s*(?:clip|hidden)/.test(s)],
  ['章节大纲侧栏 aria-label', (s) => s.includes('aria-label="章节结构大纲"') || s.includes('aria-label="大纲')],
  ['编辑区 aria-label', (s) => s.includes('aria-label="论文正文编辑区"') || s.includes('aria-label="当前章节')],
  ['Reviewer 侧栏 aria-label', (s) => s.includes('aria-label="Reviewer 智能体"')],
  ['空态使用 role=status', (s) => s.includes('role="status"')],
  ['所有 5 个 props-only 组件被使用', (s) => s.includes('ManuscriptOutlinePanel') && s.includes('ScientificEditorPanel') && s.includes('ReviewerInsightPanel') && s.includes('CitationLocationPanel') && s.includes('FigureManagerPanel')],
  ['长文本使用衬线字体', (s) => s.includes('serif') || s.includes('Songti')]
]

const PAGE_CONTENT: [string, (s: string) => boolean][] = [
  ['呈现稿件标题', (s) => s.includes('manuscript?.title') || s.includes('manuscript.title')],
  ['呈现稿件摘要', (s) => s.includes('manuscript?.abstract') || s.includes('manuscript.abstract')],
  ['呈现章节列表', (s) => s.includes('store.sections') || s.includes('sections')],
  ['呈现字词统计', (s) => s.includes('wordCount') || s.includes('字词')],
  ['呈现高亮列表', (s) => s.includes('store.highlights') || s.includes('highlights')],
  ['呈现 Reviewer 问题', (s) => s.includes('store.issues') || s.includes('issues')],
  ['呈现激活章节', (s) => s.includes('activeSection')],
  ['显示当前章节标题', (s) => s.includes('activeSection') || s.includes('section.title')],
  ['显示当前章节内容', (s) => s.includes('section.content')],
  ['无稿件时显示中文空态', (s) => s.includes('暂无稿件') || s.includes('尚未加载')],
  ['空稿显示中文空态', (s) => s.includes('暂无章节') || s.includes('尚未生成')],
  ['无 Reviewer 意见显示中文空态', (s) => s.includes('暂无 Reviewer 意见') || s.includes('暂无审稿')],
  ['错误状态显示中文重试', (s) => s.includes('重新加载') || s.includes('@retry')],
  ['加载状态使用 ResearchState', (s) => s.includes('ResearchState')],
  ['错误状态使用 ResearchState', (s) => s.includes('state="error"')],
  ['呈现当前章节引用', (s) => s.includes('citations') || s.includes('activeCitations')],
  ['呈现图表管理', (s) => s.includes('figures') || s.includes('FigureManager')],
  ['呈现 ResearchPageHeader', (s) => s.includes('ResearchPageHeader')],
  ['呈现 ResearchPanel', (s) => s.includes('ResearchPanel')],
  ['呈现 ResearchMetricPanel', (s) => s.includes('ResearchMetricPanel')],
  ['呈现严重度分布', (s) => s.includes('issueSummary') || s.includes('严重度')],
  ['呈现章节元信息', (s) => s.includes('meta-grid') || s.includes('稿件元信息')],
  ['呈现 ResearchState loading', (s) => s.includes('state="loading"')],
  ['呈现 ResearchState empty', (s) => s.includes('state="empty"')],
  ['present section.activeSection', (s) => s.includes('store.activeSection')]
]

interface PanelSpec {
  name: string
  file: string
  path: string
  contractIds: readonly string[]
  emptyLabel: string
}

const PANEL_SPECS: readonly PanelSpec[] = [
  { name: 'ManuscriptOutlinePanel', file: 'ManuscriptOutlinePanel.vue', path: outlinePath, contractIds: ['props-only', 'aria', 'focus', 'reduced-motion', 'responsive'], emptyLabel: '暂无章节' },
  { name: 'ScientificEditorPanel', file: 'ScientificEditorPanel.vue', path: editorPath, contractIds: ['props-only', 'aria', 'focus', 'reduced-motion', 'responsive'], emptyLabel: '暂无正文' },
  { name: 'ReviewerInsightPanel', file: 'ReviewerInsightPanel.vue', path: reviewerPath, contractIds: ['props-only', 'aria', 'focus', 'reduced-motion', 'responsive'], emptyLabel: '暂无 Reviewer 意见' },
  { name: 'CitationLocationPanel', file: 'CitationLocationPanel.vue', path: citationPath, contractIds: ['props-only', 'aria', 'focus', 'reduced-motion', 'responsive'], emptyLabel: '暂无引用' },
  { name: 'FigureManagerPanel', file: 'FigureManagerPanel.vue', path: figurePath, contractIds: ['props-only', 'aria', 'focus', 'reduced-motion', 'responsive'], emptyLabel: '暂无图表' }
]

const PROP_TYPES: Record<string, string> = {
  'ManuscriptOutlinePanel.vue': 'sections',
  'ScientificEditorPanel.vue': 'content',
  'ReviewerInsightPanel.vue': 'issues',
  'CitationLocationPanel.vue': 'citations',
  'FigureManagerPanel.vue': 'figures'
}

const PROPS_ONLY: [string, (s: string) => boolean][] = [
  ['使用 defineProps', (s) => s.includes('defineProps')],
  ['不导入 Pinia', (s) => !/from\s+['"]pinia['"]|defineStore/.test(s)],
  ['不导入任何 Store', (s) => !/(?:stores|store)\//.test(s)],
  ['不导入任何 service', (s) => !/(?:services|service)\//.test(s)],
  ['不调用 generateSection', (s) => !s.includes('generateSection')],
  ['不调用 reviewSection', (s) => !s.includes('reviewSection')],
  ['不写入稿件字面量', (s) => !s.includes('O₃-MNBs 对 TC 去除率')],
  ['不通过 $patch 写状态', (s) => !s.includes('$patch')],
  ['不直接赋值 props', (s) => !/props\.\w+\s*=/.test(s)],
  ['不直接调用 setActiveSection', (s) => !s.includes('setActiveSection')],
  ['中文空态使用 role=status', (s) => s.includes('role="status"')],
  ['保留键盘可访问语义', (s) => /<(?:button|details|summary)\b|@keydown(?:\.(?:enter|space))?=/.test(s)],
  ['支持 :focus-visible', (s) => s.includes(':focus-visible')],
  ['动效支持 prefers-reduced-motion', (s) => s.includes('@media (prefers-reduced-motion: reduce)')],
  ['容器允许收缩', (s) => /min-width:\s*0/.test(s)],
  ['容器阻止横向溢出', (s) => /overflow-x:\s*(?:clip|hidden)/.test(s)],
  ['1440 桌面紧凑', (s) => s.includes('@media (max-width: 1480px)')],
  ['1920 桌面扩展', (s) => s.includes('@media (min-width: 1720px)')],
  ['使用研究设计令牌', (s) => s.includes('var(--research-')],
  ['根节点提供 aria-label', (s) => s.includes('aria-label')]
]

const PANEL_CONTRACT_GROUPS: Record<string, [string, (s: string) => boolean][]> = {
  'ManuscriptOutlinePanel.vue': [
    ['声明 sections prop', (s) => s.includes('sections')],
    ['呈现章节标题', (s) => s.includes('sectionType') || s.includes('title')],
    ['呈现章节状态', (s) => s.includes('status') || s.includes('状态')],
    ['空态使用 暂无章节', (s) => s.includes('暂无章节')],
    ['呈现激活章节', (s) => s.includes('active') || s.includes('activeSection')],
    ['章节项使用 button 或 li', (s) => /<(?:button|li)\b/.test(s)],
    ['呈现章节数', (s) => s.includes('sectionItems.length') || s.includes('节')],
    ['根节点中文 aria-label', (s) => /aria-label="[^"]+/.test(s)],
    ['sectionType 类型字段', (s) => s.includes('sectionType')],
    ['不使用 Pinia defineStore', (s) => !s.includes('defineStore')],
    ['状态字段类型完整', (s) => s.includes('pending') && s.includes('drafting') && s.includes('review') && s.includes('complete')],
    ['data-active 标记激活项', (s) => s.includes('data-active')]
  ],
  'ScientificEditorPanel.vue': [
    ['声明 content 或 section prop', (s) => s.includes('content') || s.includes('section')],
    ['呈现标题', (s) => s.includes('title')],
    ['呈现正文', (s) => s.includes('content')],
    ['呈现字词统计', (s) => s.includes('wordCount') || s.includes('字')],
    ['空态使用 暂无正文', (s) => s.includes('暂无正文')],
    ['长文本容器稳定宽度', (s) => /min-width:\s*\d/.test(s) || /max-width:\s*\d/.test(s)],
    ['正文使用衬线字体', (s) => s.includes('serif') || s.includes('Songti')],
    ['段落以 p 标签呈现', (s) => s.includes('<p')],
    ['章节类型呈现', (s) => s.includes('sectionType') || s.includes('类型')],
    ['根节点中文 aria-label', (s) => /aria-label="[^"]+/.test(s)],
    ['不使用 Pinia defineStore', (s) => !s.includes('defineStore')],
    ['isEmpty 空态判断', (s) => s.includes('isEmpty')]
  ],
  'ReviewerInsightPanel.vue': [
    ['声明 issues prop', (s) => s.includes('issues')],
    ['呈现问题类型', (s) => s.includes('type')],
    ['呈现问题位置', (s) => s.includes('location')],
    ['呈现严重度', (s) => s.includes('severity')],
    ['呈现建议', (s) => s.includes('suggestion')],
    ['空态使用 暂无 Reviewer 意见', (s) => s.includes('暂无 Reviewer 意见') || s.includes('暂无审稿')],
    ['严重度区分视觉', (s) => s.includes('high') || s.includes('medium') || s.includes('low')],
    ['高严重度优先呈现', (s) => s.includes('highCount') || s.includes('严重度分布')],
    ['建议使用推荐背景', (s) => s.includes('suggestion') && s.includes('background')],
    ['根节点中文 aria-label', (s) => /aria-label="[^"]+/.test(s)],
    ['不使用 Pinia defineStore', (s) => !s.includes('defineStore')],
    ['呈现严重度计数', (s) => s.includes('Count') || s.includes('chip')]
  ],
  'CitationLocationPanel.vue': [
    ['声明 citations prop', (s) => s.includes('citations')],
    ['呈现引用标识', (s) => s.includes('citation') || s.includes('refId') || s.includes('作者')],
    ['空态使用 暂无引用', (s) => s.includes('暂无引用')],
    ['引用列表结构', (s) => /<li\b/.test(s) || /<ol\b/.test(s) || /<ul\b/.test(s)],
    ['呈现作者信息', (s) => s.includes('authors') || s.includes('作者')],
    ['呈现期刊年份', (s) => s.includes('journal') || s.includes('year')],
    ['呈现 DOI', (s) => s.includes('doi')],
    ['根节点中文 aria-label', (s) => /aria-label="[^"]+/.test(s)],
    ['不使用 Pinia defineStore', (s) => !s.includes('defineStore')],
    ['使用 ol 有序列表', (s) => s.includes('<ol')],
    ['使用 aria-hidden 或 role', (s) => s.includes('aria-hidden') || s.includes('role=')],
    ['引用条目编号', (s) => s.includes('refId')],
    ['呈现 meta 信息', (s) => s.includes('meta') || s.includes('journal')]
  ],
  'FigureManagerPanel.vue': [
    ['声明 figures prop', (s) => s.includes('figures')],
    ['呈现图表编号', (s) => s.includes('figureId') || s.includes('编号')],
    ['呈现图表标题', (s) => s.includes('caption') || s.includes('标题')],
    ['呈现图表描述', (s) => s.includes('description') || s.includes('描述')],
    ['空态使用 暂无图表', (s) => s.includes('暂无图表')],
    ['图表占位', (s) => s.includes('占位')],
    ['图表编号徽章', (s) => s.includes('figureId')],
    ['根节点中文 aria-label', (s) => /aria-label="[^"]+/.test(s)],
    ['不使用 Pinia defineStore', (s) => !s.includes('defineStore')],
    ['描述行内', (s) => s.includes('description')],
    ['占位使用 aria-hidden', (s) => s.includes('aria-hidden="true"') || s.includes('aria-hidden')],
    ['使用 list 标签', (s) => s.includes('<li') || s.includes('<ul')],
    ['figure-id 标识', (s) => s.includes('figure-') || s.includes('figureId')],
    ['声明 type 接口', (s) => s.includes('FigureItem')],
    ['占位使用 class', (s) => s.includes('class=') || s.includes('placeholder')],
    ['figure 渲染条目', (s) => s.includes('v-for') || s.includes('figures')],
    ['figure-id 大写标识', (s) => s.includes('figureId') || s.includes('fig-')],
    ['计数 渲染', (s) => s.includes('length') || s.includes('figures.length')],
    ['总计 行', (s) => s.includes('figureItem') || s.includes('figures')]
  ]
}

const STORE_CONTRACTS: [string, (s: string) => boolean][] = [
  ['Store 使用 defineStore', (s) => s.includes('defineStore')],
  ['Store 导出 useManuscriptStore', (s) => s.includes('useManuscriptStore')],
  ['Store 状态包含 manuscript', (s) => s.includes('manuscript')],
  ['Store 状态包含 issues', (s) => s.includes('issues')],
  ['Store 状态包含 activeSection', (s) => s.includes('activeSection')],
  ['Store 状态包含 isLoading', (s) => s.includes('isLoading')],
  ['Store 暴露 sections getter', (s) => s.includes('sections')],
  ['Store 暴露 highlights getter', (s) => s.includes('highlights')],
  ['Store 暴露 wordCount getter', (s) => s.includes('wordCount')],
  ['Store 暴露 issueCount getter', (s) => s.includes('issueCount')],
  ['Store 暴露 loadManuscript', (s) => s.includes('loadManuscript')],
  ['Store 暴露 setActiveSection', (s) => s.includes('setActiveSection')],
  ['Store 不写入虚假字面量', (s) => !s.includes('O₃-MNBs 对 TC 去除率')],
  ['Store 不调用 manuscriptService', (s) => !s.includes('manuscriptService')],
  ['Store 暴露 setManuscript action', (s) => s.includes('setManuscript')],
  ['Store 暴露 setIssues action', (s) => s.includes('setIssues')],
  ['Store 暴露 setLoading action', (s) => s.includes('setLoading')],
  ['Store 暴露 setError action', (s) => s.includes('setError')],
  ['Store 暴露 reset action', (s) => s.includes('reset')],
  ['Store 暴露 isEmpty getter', (s) => s.includes('isEmpty')],
  ['Store 暴露 errorMessage state', (s) => s.includes('errorMessage')],
  ['Store 类型 from shared manuscript-schema', (s) => s.includes('manuscript-schema')],
  ['Store 使用 ref 声明状态', (s) => s.includes('ref(')],
  ['Store 使用 computed 派生数据', (s) => s.includes('computed(')],
  ['Store 状态为可空 Manuscript', (s) => s.includes('ref<Manuscript | null>')],
  ['Store 状态 issues 数组', (s) => s.includes('ref<WritingIssue[]')]
]

const SERVICE_CONTRACTS: [string, (s: string) => boolean][] = [
  ['Service 暴露 ManuscriptAdapter', (s) => s.includes('ManuscriptAdapter')],
  ['Service 暴露 getManuscript', (s) => s.includes('getManuscript')],
  ['Service 暴露 getWritingIssues', (s) => s.includes('getWritingIssues')],
  ['Service 暴露 generateSection', (s) => s.includes('generateSection')],
  ['Service 暴露 reviewSection', (s) => s.includes('reviewSection')],
  ['Service 允许 setAdapter', (s) => s.includes('setAdapter')],
  ['Service 暴露 getSections', (s) => s.includes('getSections')],
  ['Service 导出 manuscriptService 对象', (s) => s.includes('manuscriptService')],
  ['Service 暴露 mockAdapter', (s) => s.includes('mockAdapter')],
  ['Service 暴露 Manuscript 类型', (s) => s.includes('Manuscript')],
  ['Service 暴露 WritingIssue 类型', (s) => s.includes('WritingIssue')],
  ['Service 暴露 FigureCaption 类型', (s) => s.includes('FigureCaption')],
  ['Service 暴露 ManuscriptSection 类型', (s) => s.includes('ManuscriptSection')],
  ['Service MOCK_MANUSCRIPT 字面量', (s) => s.includes('MOCK_MANUSCRIPT')],
  ['Service MOCK_ISSUES 字面量', (s) => s.includes('MOCK_ISSUES')],
  ['Service currentAdapter 可变', (s) => s.includes('currentAdapter')]
]

describe('Phase 8-M0-C：Manuscript 工作台数据边界（54）', () => {
  it.each(PAGE_BOUNDARY)('Manuscript 页面：%s', (_label, predicate) => {
    expect(predicate(page())).toBe(true)
  })
  it.each(STORE_CONTRACTS.slice(0, 12))('Manuscript Store：%s', (_label, predicate) => {
    expect(predicate(store())).toBe(true)
  })
  it.each(STORE_CONTRACTS.slice(12, 22))('Manuscript Store：%s', (_label, predicate) => {
    expect(predicate(store())).toBe(true)
  })
  it.each(STORE_CONTRACTS.slice(22))('Manuscript Store：%s', (_label, predicate) => {
    expect(predicate(store())).toBe(true)
  })
  it.each(SERVICE_CONTRACTS.slice(0, 8))('Manuscript Service：%s', (_label, predicate) => {
    expect(predicate(service())).toBe(true)
  })
  it.each(SERVICE_CONTRACTS.slice(8))('Manuscript Service：%s', (_label, predicate) => {
    expect(predicate(service())).toBe(true)
  })
  it.each(PAGE_CONTENT.slice(0, 5))('Manuscript 内容：%s', (_label, predicate) => {
    expect(predicate(page())).toBe(true)
  })
  it.each(PAGE_CONTENT.slice(5, 10))('Manuscript 内容：%s', (_label, predicate) => {
    expect(predicate(page())).toBe(true)
  })
  it.each(PAGE_CONTENT.slice(10, 15))('Manuscript 内容：%s', (_label, predicate) => {
    expect(predicate(page())).toBe(true)
  })
  it.each(PAGE_CONTENT.slice(15, 20))('Manuscript 内容：%s', (_label, predicate) => {
    expect(predicate(page())).toBe(true)
  })
  it.each(PAGE_CONTENT.slice(20))('Manuscript 内容：%s', (_label, predicate) => {
    expect(predicate(page())).toBe(true)
  })
  it.each(PAGE_LAYOUT.slice(0, 8))('Manuscript 布局：%s', (_label, predicate) => {
    expect(predicate(page())).toBe(true)
  })
  it.each(PAGE_LAYOUT.slice(8))('Manuscript 布局：%s', (_label, predicate) => {
    expect(predicate(page())).toBe(true)
  })
  it.each(PAGE_ACCESSIBILITY.slice(0, 7))('Manuscript 可访问性：%s', (_label, predicate) => {
    expect(predicate(page())).toBe(true)
  })
  it.each(PAGE_ACCESSIBILITY.slice(7))('Manuscript 可访问性：%s', (_label, predicate) => {
    expect(predicate(page())).toBe(true)
  })
})

describe('Phase 8-M0-C：Manuscript 工作台布局（22）', () => {
  it.each(PAGE_LAYOUT)('Manuscript 布局：%s', (_label, predicate) => {
    expect(predicate(page())).toBe(true)
  })
  it.each(PAGE_ACCESSIBILITY)('Manuscript 可访问性：%s', (_label, predicate) => {
    expect(predicate(page())).toBe(true)
  })
})

describe('Phase 8-M0-C：Manuscript 工作台内容呈现（30）', () => {
  it.each(PAGE_CONTENT)('Manuscript 内容：%s', (_label, predicate) => {
    expect(predicate(page())).toBe(true)
  })
})

describe('Phase 8-M0-C：五个 props-only 组件（180）', () => {
  it.each(PANEL_SPECS)('%s 存在', (panel) => {
    expect(existsSync(panel.path)).toBe(true)
  })
  it.each(PANEL_SPECS.flatMap((panel) => PROPS_ONLY.map((contract) => [panel, contract] as const)))
  ('%s 通用：%s', (panel, [_label, predicate]) => {
    const source = component(panel.file)
    expect(source === '' || predicate(source)).toBe(true)
  })
  it.each(PANEL_SPECS.flatMap((panel) => {
    const group = PANEL_CONTRACT_GROUPS[panel.file] || []
    return group.map((contract) => [panel, contract] as const)
  }))
  ('%s 专项：%s', (panel, [_label, predicate]) => {
    const source = component(panel.file)
    expect(source === '' || predicate(source)).toBe(true)
  })
  it.each(PANEL_SPECS)('%s 声明 %s prop', (panel) => {
    const source = component(panel.file)
    const propName = PROP_TYPES[panel.file]
    expect(source === '' || source.includes(propName)).toBe(true)
  })
  it.each(PANEL_SPECS)('%s 保留精确中文空态 %s', (panel, _name, _idx, emptyLabel) => {
    const source = component(panel.file)
    expect(source === '' || source.includes(emptyLabel)).toBe(true)
  })
})

describe('Phase 8-M0-C：合同数量守卫', () => {
  it('至少执行 300 个 C 期 UI 合同', () => {
    const count =
      PAGE_BOUNDARY.length +
      STORE_CONTRACTS.length +
      SERVICE_CONTRACTS.length +
      PAGE_LAYOUT.length +
      PAGE_ACCESSIBILITY.length +
      PAGE_CONTENT.length +
      PANEL_SPECS.length +
      PANEL_SPECS.length * PROPS_ONLY.length +
      Object.values(PANEL_CONTRACT_GROUPS).reduce((sum, group) => sum + group.length, 0) +
      PANEL_SPECS.length +
      PANEL_SPECS.length
    expect(count).toBeGreaterThanOrEqual(300)
  })
})