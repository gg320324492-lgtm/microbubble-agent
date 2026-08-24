// @vitest-environment happy-dom
import { existsSync, readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'
import ResearchState from '@/components/research/ResearchState.vue'

/**
 * Phase 8-M0-B1 is intentionally red before implementation.  These contracts
 * inspect source from the desktop test root so shared presentation components
 * cannot silently gain a Store or service dependency.
 */
const desktopRoot = resolve(__dirname, '../..')
const rendererRoot = resolve(desktopRoot, 'src/renderer/src')
const researchComponentRoot = resolve(rendererRoot, 'components/research')

const researchComponentPath = (fileName: string): string =>
  resolve(researchComponentRoot, fileName)

const readResearchComponent = (fileName: string): string => {
  const path = researchComponentPath(fileName)
  return existsSync(path) ? readFileSync(path, 'utf8') : ''
}

const readDashboard = (): string =>
  readFileSync(resolve(rendererRoot, 'pages/research/Dashboard.vue'), 'utf8')

const readHeader = (): string =>
  readFileSync(resolve(rendererRoot, 'layouts/HeaderBar.vue'), 'utf8')

const withoutComments = (source: string): string =>
  source.replace(/<!--[\s\S]*?-->|\/\*[\s\S]*?\*\/|\/\/[^\r\n]*/g, '')

type SourcePredicate = (source: string) => boolean

interface ComponentContract {
  name: string
  fileName: string
  className: string
  props: readonly string[]
}

const COMPONENTS: readonly ComponentContract[] = [
  {
    name: 'ResearchMetricPanel',
    fileName: 'ResearchMetricPanel.vue',
    className: 'research-metric-panel',
    props: ['items', 'ariaLabel']
  },
  {
    name: 'ResearchTimeline',
    fileName: 'ResearchTimeline.vue',
    className: 'research-timeline',
    props: ['items', "'pending'", "'running'"]
  },
  {
    name: 'AgentStatusPanel',
    fileName: 'AgentStatusPanel.vue',
    className: 'agent-status-panel',
    props: ['agents', 'queue', 'action']
  },
  {
    name: 'EvidencePanel',
    fileName: 'EvidencePanel.vue',
    className: 'evidence-panel',
    props: ['evidence', 'citations']
  },
  {
    name: 'DeviceStatusPanel',
    fileName: 'DeviceStatusPanel.vue',
    className: 'device-status-panel',
    props: ['devices', 'variant']
  },
  {
    name: 'SCADAChartPanel',
    fileName: 'SCADAChartPanel.vue',
    className: 'scada-chart-panel',
    props: ['metrics', 'metricName', 'label']
  },
  {
    name: 'PredictionPanel',
    fileName: 'PredictionPanel.vue',
    className: 'prediction-panel',
    props: ['predictions', 'variant']
  }
] as const

const componentSourceCases: readonly [ComponentContract, string, SourcePredicate][] = COMPONENTS.flatMap((component) => [
  [component, '使用 defineProps 接收展示数据', (source) => source.includes('defineProps')],
  [component, '不导入 Pinia', (source) => !/from\s+['"]pinia['"]|defineStore/.test(source)],
  [component, '不导入任何 Store', (source) => !/(?:stores|store)\//.test(source)],
  [component, '不导入任何 service（含 type import）', (source) => !/(?:services|service)\//.test(source)],
  [component, '提供根节点 aria-label', (source) => source.includes('aria-label')],
  [component, `提供 ${component.className} 根类名`, (source) => source.includes(component.className)],
  [component, '提供中文空状态', (source) => /(?:暂无|尚无|暂未接入|等待)/.test(source)],
  [component, '用 role=status 宣告空状态', (source) => source.includes('role="status"')],
  [component, '使用研究设计令牌', (source) => source.includes('var(--research-')]
])

const componentPropCases: readonly [ComponentContract, string][] = COMPONENTS
  .flatMap((component) => component.props.map((prop) => [component, prop] as const))
  .filter(([component, prop]) => !(
    (component.name === 'ResearchMetricPanel' && prop === 'items')
    || (component.name === 'ResearchTimeline' && (prop === 'items' || prop === "'pending'"))
    || (component.name === 'AgentStatusPanel' && prop === 'queue')
  ))

const componentTypeContractCases: readonly [ComponentContract, string, SourcePredicate][] = [
  [
    COMPONENTS[0],
    '指标状态 union 以 neutral 为规范中性态，而非 normal',
    (source) =>
      /\bstatus\s*\??\s*:\s*[^;\r\n]*['"]neutral['"]/.test(source)
      && !/\bstatus\s*\??\s*:\s*[^;\r\n]*['"]normal['"]/.test(source)
  ],
  [
    COMPONENTS[1],
    '时间线状态 union 包含 neutral',
    (source) => /\bstatus\s*\??\s*:\s*[^;\r\n]*['"]neutral['"]/.test(source)
  ],
  [
    COMPONENTS[1],
    '时间线条目 description 为必填字段',
    (source) => /\bdescription\s*:/.test(source) && !/\bdescription\s*\?:/.test(source)
  ],
  [
    COMPONENTS[2],
    '队列接受 number，缺失时如实显示待接入数据',
    (source) =>
      /\bqueue\s*\??\s*:\s*(?:number\b|number\s*\|\s*string|string\s*\|\s*number)/.test(source)
      && source.includes("queue ?? '待接入数据'")
  ]
]

const componentVisualCases: readonly [ComponentContract, string, SourcePredicate][] = COMPONENTS.map((component) =>
  [component, '保留 min-width: 0 防止内容横向溢出', (source) => /min-width:\s*0/.test(source)]
)

const evidenceLocalInterfaceCases = [
  'interface EvidenceItem',
  'interface CitationItem'
] as const

const scopedPresentationA11yCases = [
  ['ResearchTimeline.vue', '交互时间线具有 :focus-visible', ':focus-visible'],
  ['ResearchTimeline.vue', '时间线装饰标记具有 aria-hidden', 'aria-hidden'],
  ['ResearchTimeline.vue', '时间线动效支持 reduced-motion', '@media (prefers-reduced-motion: reduce)'],
  ['AgentStatusPanel.vue', '运行状态装饰具有 aria-hidden', 'aria-hidden'],
  ['AgentStatusPanel.vue', '运行状态动效支持 reduced-motion', '@media (prefers-reduced-motion: reduce)'],
  ['EvidencePanel.vue', '可操作证据具有 :focus-visible', ':focus-visible'],
  ['EvidencePanel.vue', '证据装饰具有 aria-hidden', 'aria-hidden'],
  ['DeviceStatusPanel.vue', '设备信号装饰具有 aria-hidden', 'aria-hidden'],
  ['DeviceStatusPanel.vue', '设备信号动效支持 reduced-motion', '@media (prefers-reduced-motion: reduce)'],
  ['SCADAChartPanel.vue', 'SCADA 图表装饰具有 aria-hidden', 'aria-hidden'],
  ['SCADAChartPanel.vue', 'SCADA 动效支持 reduced-motion', '@media (prefers-reduced-motion: reduce)'],
  ['PredictionPanel.vue', '预测动效支持 reduced-motion', '@media (prefers-reduced-motion: reduce)']
] as const

const dashboardCompositionCases = [
  ['ResearchPageHeader', 'ResearchPageHeader.vue'],
  ['ResearchMetricPanel', 'ResearchMetricPanel.vue'],
  ['ResearchTimeline', 'ResearchTimeline.vue'],
  ['AgentStatusPanel', 'AgentStatusPanel.vue'],
  ['EvidencePanel', 'EvidencePanel.vue'],
  ['DeviceStatusPanel', 'DeviceStatusPanel.vue']
] as const

const cockpitLabelCases = [
  '科研驾驶舱',
  '项目名称',
  '研究领域',
  '研究目标',
  '阶段',
  '进度',
  'AI 研究活动',
  '实验状态',
  '设备健康',
  '近期科学洞见'
] as const

const dashboardFocusCases = [
  ['科研焦点标题', '科研焦点'],
  ['科研焦点区域类名', 'dashboard__focus'],
  ['项目名称字段', '项目名称'],
  ['研究领域字段', '研究领域'],
  ['研究目标字段', '研究目标'],
  ['阶段字段', '阶段'],
  ['进度字段', '进度'],
  ['项目名称来自当前项目', 'projectStore.currentProject.name'],
  ['研究领域来自当前项目', 'projectStore.currentProject.domain'],
  ['研究目标来自当前项目', 'projectStore.currentProject.description'],
  ['进度来自 projectProgress', 'projectProgress']
] as const

const allowedDashboardStoreCases = [
  ['Project store', 'useProjectStore', 'stores/research/project.store'],
  ['Knowledge store', 'useKnowledgeStore', 'stores/research/knowledge.store'],
  ['Dataset store', 'useDatasetStore', 'stores/research/dataset.store'],
  ['Manuscript store', 'useManuscriptStore', 'stores/research/manuscript.store']
] as const

const prohibitedDashboardStoreCases = [
  'stores/research/agent.store',
  'stores/research/workflow.store',
  'stores/research/experiment.store',
  'stores/experiment-control.store',
  'stores/research/device.store',
  'stores/research/digital-twin.store'
] as const

const dashboardStateCases = [
  'loadDashboard',
  'onMounted(loadDashboard)',
  'loadError',
  'isLoading',
  'hasResearchData',
  'ResearchState',
  'state="loading"',
  'state="error"',
  'state="empty"',
  '@retry="loadDashboard"'
] as const

const dashboardDataDerivedCases: readonly [string, SourcePredicate][] = [
  ['视图模型使用 computed 派生', (source) => source.includes('computed(')],
  ['实验状态不读取项目 stats.experiments', (source) => !source.includes('projectStore.currentProject.stats.experiments')],
  ['近期科学洞见从数据结论派生', (source) => source.includes('datasetStore.conclusions')],
  ['证据覆盖从知识库文档数派生', (source) => source.includes('knowledgeStore.totalDocuments')],
  ['论文展示不读取项目 stats.manuscriptStatus', (source) => !source.includes('projectStore.currentProject.stats.manuscriptStatus')],
  ['论文展示从 manuscript Store 派生或明确显示暂无草稿', (source) => source.includes('manuscriptStore.manuscript') && source.includes('暂无草稿')],
  ['AI 时间线仅传本地 computed 空数组，不伪造活动字面量', (source) =>
    /const\s+researchTimeline\s*=\s*computed(?:<ResearchTimelineItem\[\]>)?\s*\(\s*\(\)\s*=>\s*\[\s*\]\s*\)/.test(source)
    && source.includes('<ResearchTimeline :items="researchTimeline"')
    && !/\btitle\s*:\s*['"]/.test(source)],
  ['AgentStatus 仅传本地 computed 空数组，不伪造 queue 或 action', (source) =>
    /const\s+agentStatuses\s*=\s*computed(?:<ResearchAgentStatusItem\[\]>)?\s*\(\s*\(\)\s*=>\s*\[\s*\]\s*\)/.test(source)
    && source.includes('<AgentStatusPanel :agents="agentStatuses"')
    && !/\bqueue\s*:\s*\d+/.test(source)
    && !/\baction\s*:\s*['"]/.test(source)],
  ['不把设备健康度写死为 98–100%', (source) => !/(?:设备健康|deviceHealth)[\s\S]{0,120}(?:98|99|100)\s*%/.test(source)]
]

const dashboardResponsiveCases: readonly [string, SourcePredicate][] = [
  ['1440 宽屏收束断点', (source) => source.includes('@media (max-width: 1480px)')],
  ['1920 宽屏密度断点', (source) => source.includes('@media (min-width: 1720px)')],
  ['科研驾驶舱使用 command grid', (source) => source.includes('dashboard__command-grid')],
  ['网格轨道允许收缩', (source) => source.includes('minmax(0,')],
  ['仪表盘子项具有 min-width: 0', (source) => /min-width:\s*0/.test(source)],
  ['不写死 1440 或 1920 像素主内容宽度', (source) => !/width:\s*(?:1440|1920)px/.test(source)],
  ['1440 视口的 command grid 精确折叠选择器', (source) => /@media\s*\(max-width:\s*1480px\)\s*\{[\s\S]*?\.dashboard__command-grid\s*\{[\s\S]*?grid-template-columns:\s*1fr/.test(source)],
  ['1920 视口的 command grid 精确密度选择器', (source) => /@media\s*\(min-width:\s*1720px\)\s*\{[\s\S]*?\.dashboard__command-grid\s*\{[\s\S]*?grid-template-columns:\s*minmax\(0,\s*1\.25fr\)\s*minmax\(320px,\s*\.75fr\)/.test(source)],
  ['主工作区具有显式横向溢出防护', (source) => /overflow-x:\s*(?:clip|hidden)/.test(source)]
]

const viewportContractCases: readonly [
  viewport: '1440' | '1920',
  mediaQuery: string,
  commandGridOutcome: string,
  overflowOutcome: string | RegExp
][] = [
  ['1440', '@media (max-width: 1480px)', 'grid-template-columns: 1fr', /overflow-x:\s*(?:clip|hidden)/],
  ['1920', '@media (min-width: 1720px)', 'grid-template-columns: minmax(0, 1.25fr) minmax(320px, .75fr)', /overflow-x:\s*(?:clip|hidden)/]
]

const scadaSemanticCases: readonly [string, string, string, SourcePredicate][] = [
  ['DeviceStatusPanel', 'DeviceStatusPanel.vue', "声明 'research' | 'scada' 变体联合类型", (source) => source.includes("'research' | 'scada'")],
  ['DeviceStatusPanel', 'DeviceStatusPanel.vue', '导入设备 schema 时别名为 DeviceStatusData', (source) => /import\s+type\s+\{\s*DeviceStatusPanel\s+as\s+DeviceStatusData\s*\}/.test(source) && source.includes('devices: DeviceStatusData[]')],
  ['DeviceStatusPanel', 'DeviceStatusPanel.vue', '呈现中文设备状态', (source) => source.includes('设备状态')],
  ['DeviceStatusPanel', 'DeviceStatusPanel.vue', '提供 aria-label', (source) => source.includes('aria-label')],
  ['DeviceStatusPanel', 'DeviceStatusPanel.vue', '使用 signal-green 在线信号', (source) => source.includes('--research-signal-green')],
  ['DeviceStatusPanel', 'DeviceStatusPanel.vue', '使用 signal-amber 警告信号', (source) => source.includes('--research-signal-amber')],
  ['DeviceStatusPanel', 'DeviceStatusPanel.vue', '使用 signal-red 错误信号', (source) => source.includes('--research-signal-red')],
  ['DeviceStatusPanel', 'DeviceStatusPanel.vue', '具有 scada 设备根类', (source) => source.includes('device-status-panel--scada')],
  ['DeviceStatusPanel', 'DeviceStatusPanel.vue', '设备信号动画在 reduced-motion 下停用', (source) => source.includes('@media (prefers-reduced-motion: reduce)')],
  ['PredictionPanel', 'PredictionPanel.vue', "声明 'research' | 'scada' 变体联合类型", (source) => source.includes("'research' | 'scada'")],
  ['PredictionPanel', 'PredictionPanel.vue', '按 timestamp 派生最新预测，而非直接取数组末项', (source) => /sort\([\s\S]{0,240}timestamp/.test(source) && !/predictions\.at\(-1\)/.test(source)],
  ['PredictionPanel', 'PredictionPanel.vue', '呈现暂无数字孪生预测空状态', (source) => source.includes('暂无数字孪生预测')],
  ['PredictionPanel', 'PredictionPanel.vue', '提供 aria-label', (source) => source.includes('aria-label')],
  ['PredictionPanel', 'PredictionPanel.vue', '使用 instrument-900 仪器样式', (source) => source.includes('--research-instrument-900')],
  ['PredictionPanel', 'PredictionPanel.vue', '输出为空时呈现中文预测无输出状态', (source) => /v-if\s*=\s*"outputEntries\.length"/.test(source) && /暂无(?:数字孪生)?预测(?:结果|输出)/.test(source)],
  ['PredictionPanel', 'PredictionPanel.vue', '预测动效在 reduced-motion 下停用', (source) => source.includes('@media (prefers-reduced-motion: reduce)')],
  ['SCADAChartPanel', 'SCADAChartPanel.vue', '接收 metrics 数据', (source) => source.includes('metrics')],
  ['SCADAChartPanel', 'SCADAChartPanel.vue', '接收 metricName 筛选条件', (source) => source.includes('metricName')],
  ['SCADAChartPanel', 'SCADAChartPanel.vue', '可选 deviceId 限定图表范围并按其过滤', (source) => /deviceId\s*\?:\s*string/.test(source) && /filter\([\s\S]{0,240}metric\.deviceId\s*===\s*props\.deviceId/.test(source)],
  ['SCADAChartPanel', 'SCADAChartPanel.vue', '呈现中文实时指标', (source) => source.includes('实时指标')],
  ['SCADAChartPanel', 'SCADAChartPanel.vue', '提供 aria-label', (source) => source.includes('aria-label')],
  ['SCADAChartPanel', 'SCADAChartPanel.vue', '使用 scada-grid 网格令牌', (source) => source.includes('--research-scada-grid')],
  ['SCADAChartPanel', 'SCADAChartPanel.vue', '提供 SVG 趋势轨迹', (source) => source.includes('<svg')],
  ['SCADAChartPanel', 'SCADAChartPanel.vue', '装饰 SVG 不重复根节点可访问名称', (source) => {
    const svgElement = source.match(/<svg\b[\s\S]*?>/)?.[0] ?? ''
    return /aria-hidden\s*=\s*"true"/.test(svgElement)
      || (/aria-label/.test(svgElement) && !/chartAriaLabel/.test(svgElement))
  }],
  ['SCADAChartPanel', 'SCADAChartPanel.vue', '图表可收缩避免横向溢出', (source) => /min-width:\s*0/.test(source)],
  ['SCADAChartPanel', 'SCADAChartPanel.vue', '图表动效在 reduced-motion 下停用', (source) => source.includes('@media (prefers-reduced-motion: reduce)')],
  ['SCADAChartPanel', 'SCADAChartPanel.vue', '图表装饰标记具有 aria-hidden', (source) => source.includes('aria-hidden')]
]

const dashboardA11yCases: readonly [string, SourcePredicate][] = [
  ['科研驾驶舱根节点使用 section/div 而非 main，并保留 aria-label', (source) =>
    !/<main\b/.test(source)
    && /<(?:section|div)\b[^>]*class="dashboard"[^>]*aria-label="科研驾驶舱"/.test(source)
    && source.includes('aria-label="科研关键指标"')],
  ['项目进度具有 progressbar 语义', (source) => source.includes('role="progressbar"')],
  ['项目进度声明最小值', (source) => source.includes('aria-valuemin="0"')],
  ['项目进度声明最大值', (source) => source.includes('aria-valuemax="100"')],
  ['项目进度提供动态当前值', (source) => source.includes(':aria-valuenow')]
]

const headerGlobalAiCases: readonly [string, SourcePredicate][] = [
  ['全局 AI 状态区域', (source) => source.includes('header-bar__ai-status')],
  ['全局 AI 无障碍名称', (source) => source.includes('aria-label="全局 AI 状态"')],
  ['Current AI task 标签', (source) => source.includes('当前 AI 任务')],
  ['系统状态不伪造为在线', (source) => !source.includes('系统状态：在线')],
  ['项目上下文与待连接系统状态使用 amber/neutral 而非 teal/success', (source) => {
    const systemStatusRule = source.match(/\.header-ai-status__system\s*\{([^}]*)}/)?.[1] ?? ''
    return source.includes('class="header-ai-status__system"')
      && source.includes('项目上下文')
      && source.includes('系统状态：待连接')
      && !/--research-(?:teal|success)/.test(systemStatusRule)
      && /--research-(?:signal-amber|warning|neutral)/.test(systemStatusRule)
  }],
  ['当前项目名作为上下文', (source) => source.includes('projectStore.currentProject.name')],
  ['状态以 polite live region 宣告', (source) => source.includes('aria-live="polite"')],
  ['无后端时系统状态明确为待连接', (source) => source.includes('系统状态：待连接')]
]

describe('Phase 8-M0-B1：七个 props-only 共享组件（108）', () => {
  it.each(COMPONENTS)('%s 生产组件文件存在', (component) => {
    expect(existsSync(researchComponentPath(component.fileName))).toBe(true)
  })

  it.each(componentSourceCases)('%s %s', (component, rule, predicate) => {
    const source = readResearchComponent(component.fileName)
    expect(source === '' || predicate(source)).toBe(true)
  })

  it.each(componentPropCases)('%s 声明 %s prop', (component, prop) => {
    const source = readResearchComponent(component.fileName)
    expect(source === '' || source.includes(prop)).toBe(true)
  })

  it.each(componentTypeContractCases)('%s %s', (component, rule, predicate) => {
    const source = readResearchComponent(component.fileName)
    expect(source === '' || predicate(source)).toBe(true)
  })

  it.each(componentVisualCases)('%s %s', (component, rule, predicate) => {
    const source = readResearchComponent(component.fileName)
    expect(source === '' || predicate(source)).toBe(true)
  })

  it.each(evidenceLocalInterfaceCases)('EvidencePanel 定义本地展示接口：%s', (marker) => {
    const source = readResearchComponent('EvidencePanel.vue')
    expect(source === '' || source.includes(marker)).toBe(true)
  })

  it.each(scopedPresentationA11yCases)('%s %s', (fileName, rule, marker) => {
    const source = readResearchComponent(fileName)
    expect(source === '' || source.includes(marker)).toBe(true)
  })
})

describe('Phase 8-M0-B1：科研驾驶舱组合与真实数据边界（74）', () => {
  it.each(dashboardCompositionCases)('Dashboard 实际 import 并渲染 %s', (componentName, fileName) => {
    const source = withoutComments(readDashboard())
    expect(new RegExp(`import\\s+${componentName}\\s+from\\s+['"][^'"]*${fileName}['"]`).test(source)).toBe(true)
    expect(new RegExp(`<${componentName}(?:\\s|/|>)`).test(source)).toBe(true)
  })

  it.each(cockpitLabelCases)('Dashboard 呈现科研驾驶舱结构：%s', (label) => {
    const source = withoutComments(readDashboard())
    expect(source.includes(label)).toBe(true)
  })

  it.each(dashboardFocusCases)('Dashboard 科研焦点包含 %s', (_label, marker) => {
    const source = withoutComments(readDashboard())
    expect(source.includes(marker)).toBe(true)
  })

  it.each(allowedDashboardStoreCases)('%s 是 Dashboard 允许的数据来源', (_name, store, path) => {
    const source = withoutComments(readDashboard())
    expect(source.includes(store)).toBe(true)
    expect(source.includes(path)).toBe(true)
  })

  it.each(prohibitedDashboardStoreCases)('Dashboard 不虚构数据：不导入 %s', (storePath) => {
    const source = withoutComments(readDashboard())
    expect(source.includes(storePath)).toBe(false)
  })

  it('Dashboard 仅组合四个已批准的 research data Store', () => {
    const source = withoutComments(readDashboard())
    const storeImports = source.match(/from\s+['"][^'"]*stores\/[^'"]+['"]/g) ?? []
    expect(storeImports).toHaveLength(4)
  })

  it('Dashboard 不直接导入 research service 作为伪造数据来源', () => {
    const source = withoutComments(readDashboard())
    expect(/from\s+['"][^'"]*(?:services|service)\//.test(source)).toBe(false)
  })

  it.each(dashboardStateCases)('Dashboard 保留真实状态：%s', (marker) => {
    const source = withoutComments(readDashboard())
    expect(source.includes(marker)).toBe(true)
  })

  it.each(dashboardDataDerivedCases)('Dashboard 真实数据边界：%s', (_label, predicate) => {
    const source = withoutComments(readDashboard())
    expect(predicate(source)).toBe(true)
  })

  it.each(dashboardResponsiveCases)('Dashboard %s', (_label, predicate) => {
    const source = withoutComments(readDashboard())
    expect(predicate(source)).toBe(true)
  })

  it.each(viewportContractCases)(
    'Dashboard 在 %s 视口使用 %s，并输出 %s 与横向溢出防护',
    (viewport, mediaQuery, commandGridOutcome, overflowOutcome) => {
      const source = withoutComments(readDashboard())
      expect(source.includes(mediaQuery)).toBe(true)
      expect(source.includes('.dashboard__command-grid')).toBe(true)
      expect(source.includes(commandGridOutcome)).toBe(true)
      if (typeof overflowOutcome === 'string') {
        expect(source.includes(overflowOutcome)).toBe(true)
      } else {
        expect(overflowOutcome.test(source)).toBe(true)
      }
      expect(viewport === '1440' || viewport === '1920').toBe(true)
    }
  )

  it.each(dashboardA11yCases)('Dashboard 保持无障碍契约：%s', (_label, predicate) => {
    const source = withoutComments(readDashboard())
    expect(predicate(source)).toBe(true)
  })
})

describe('Phase 8-M0-B1：顶栏全局 AI 上下文（8）', () => {
  it.each(headerGlobalAiCases)('HeaderBar 具有 %s', (_label, predicate) => {
    expect(predicate(readHeader())).toBe(true)
  })
})

describe('Phase 8-M0-B1：SCADA 仪器语义（27）', () => {
  it.each(scadaSemanticCases)('%s %s：%s', (_componentName, fileName, rule, predicate) => {
    const source = readResearchComponent(fileName)
    expect(source === '' || predicate(source)).toBe(true)
  })
})

describe('Phase 8-M0-B1：M0-A 真实 DOM 无障碍基础（2）', () => {
  it('错误状态渲染中文重试按钮，并可被键盘聚焦和触发', async () => {
    const wrapper = mount(ResearchState, { attachTo: document.body, props: { state: 'error' } })
    const retry = wrapper.get('button[type="button"]')

    expect(retry.text()).toContain('重新分析')
    retry.element.focus()
    expect(document.activeElement).toBe(retry.element)

    await retry.trigger('click')
    expect(wrapper.emitted('retry')).toHaveLength(1)
    wrapper.unmount()
  })

  it('空状态用中文 status live region 呈现真实空数据', () => {
    const wrapper = mount(ResearchState, { attachTo: document.body, props: { state: 'empty' } })
    const region = wrapper.get('[role="status"]')

    expect(region.attributes('aria-live')).toBe('polite')
    expect(region.text()).toContain('暂无科研数据')
    wrapper.unmount()
  })
})

describe('Phase 8-M0-B1：红灯契约数量守卫（1）', () => {
  it('显式计数 217 个源码契约、2 个 DOM 用例和 1 个守卫', () => {
    const sourceContractCount = COMPONENTS.length
      + componentSourceCases.length
      + componentPropCases.length
      + componentTypeContractCases.length
      + componentVisualCases.length
      + evidenceLocalInterfaceCases.length
      + scopedPresentationA11yCases.length
      + dashboardCompositionCases.length
      + cockpitLabelCases.length
      + dashboardFocusCases.length
      + allowedDashboardStoreCases.length
      + prohibitedDashboardStoreCases.length
      + 2
      + dashboardStateCases.length
      + dashboardDataDerivedCases.length
      + dashboardResponsiveCases.length
      + viewportContractCases.length
      + dashboardA11yCases.length
      + headerGlobalAiCases.length
      + scadaSemanticCases.length
    const domBehaviorTestCount = 2
    const countGuardTestCount = 1
    const totalRegisteredTests = sourceContractCount + domBehaviorTestCount + countGuardTestCount

    expect(sourceContractCount).toBe(217)
    expect(domBehaviorTestCount).toBe(2)
    expect(countGuardTestCount).toBe(1)
    expect(totalRegisteredTests).toBe(220)
    expect(totalRegisteredTests).toBeGreaterThanOrEqual(150)
  })
})
