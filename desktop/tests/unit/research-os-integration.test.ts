import { existsSync, readFileSync } from 'node:fs'
import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'
import { describe, expect, it } from 'vitest'
import { RESEARCH_NAV, RESEARCH_PAGES, RESEARCH_STATES } from '../fixtures/research-ui'

const testDir = dirname(fileURLToPath(import.meta.url))
const rendererRoot = resolve(testDir, '..', '..', 'src', 'renderer', 'src')

function source(relativePath: string): string {
  const absolutePath = resolve(rendererRoot, relativePath)
  return existsSync(absolutePath) ? readFileSync(absolutePath, 'utf8') : ''
}

function objectContainingMarker(content: string, marker: string): string {
  const markerIndex = content.indexOf(marker)
  if (markerIndex < 0 || content.indexOf(marker, markerIndex + marker.length) >= 0) return ''
  const start = content.lastIndexOf('{', markerIndex)
  if (start < 0) return ''
  let depth = 0
  let quote = ''
  let escaped = false
  for (let index = start; index < content.length; index += 1) {
    const char = content[index]
    if (quote) {
      if (escaped) escaped = false
      else if (char === '\\') escaped = true
      else if (char === quote) quote = ''
      continue
    }
    if (char === "'" || char === '"' || char === '`') quote = char
    else if (char === '{') depth += 1
    else if (char === '}' && --depth === 0) return content.slice(start, index + 1)
  }
  return ''
}

const STORE_CONTRACTS = [
  ['project.store.ts', 'useProjectStore'],
  ['agent.store.ts', 'useAgentStore'],
  ['knowledge.store.ts', 'useKnowledgeStore'],
  ['experiment.store.ts', 'useExperimentStore'],
  ['dataset.store.ts', 'useDatasetStore'],
  ['manuscript.store.ts', 'useManuscriptStore']
] as const

const PRESENTATIONAL_COMPONENTS = [
  { name: 'ResearchIcon', path: 'components/icons/ResearchIcon.vue' },
  ...[
    'ResearchPanel', 'ResearchState', 'ProjectCard', 'InsightCard', 'EvidenceCard',
    'CitationCard', 'AgentCard', 'Timeline', 'ScientificMetric', 'ChartPanel', 'StatusBadge'
  ].map((name) => ({ name, path: `components/research/${name}.vue` }))
] as const

const STORE_PAGES = ['Dashboard', 'Assistant', 'ProjectWorkspace', 'Literature', 'Experiment', 'DataAnalysis', 'Manuscript', 'AgentCenter'] as const
const ASYNC_STATE_PAGES = ['Dashboard', 'DataAnalysis'] as const
const B2_PAGE_LABELS: Partial<Record<(typeof RESEARCH_PAGES)[number][0], readonly string[]>> = {
  Assistant: ['研究会话', '科研对话工作区', '证据与可观测性'],
  AgentCenter: ['AI 研究团队', '协作时间线与证据', '工具执行']
}

function durableLabels(page: (typeof RESEARCH_PAGES)[number][0], labels: readonly string[]): readonly string[] {
  return B2_PAGE_LABELS[page] ?? labels
}

describe('research route integration', () => {
  const routerContent = source('router/index.ts')

  it.each(RESEARCH_NAV)('registers %s as authenticated main-layout route', (_label, routeName) => {
    const routePath = `/research/${routeName.replace(/^research-/, '')}`
    const routeBlock = objectContainingMarker(routerContent, `path: '${routePath}'`)
    expect(routeBlock).not.toBe('')
    expect(routeBlock).toContain(`name: '${routeName}'`)
    expect(routeBlock).toContain('requiresAuth: true')
    expect(routeBlock).toContain("layout: 'main'")
  })

  it('uses the research dashboard as the root destination', () => {
    expect(objectContainingMarker(routerContent, "path: '/'" )).toMatch(
      /redirect:\s*(?:\(\)\s*=>\s*['"]\/research\/dashboard['"]|\{\s*name:\s*['"]research-dashboard['"]\s*\})/
    )
  })
})

describe('real Store and service flow', () => {
  it.each(STORE_CONTRACTS)('%s exports the real %s Pinia hook', (file, storeHook) => {
    const content = source(`stores/research/${file}`)
    expect(content).toContain(`export const ${storeHook}`)
  })

  it.each(STORE_PAGES)('%s binds rendered content to Pinia state', (page) => {
    const content = source(`pages/research/${page}.vue`)
    expect(content).toMatch(/use[A-Za-z]+Store/)
    expect(content).toMatch(/stores\/research\/[^'"]+\.store/)
  })

  it('keeps direct service and transport access out of generic display components', () => {
    for (const component of PRESENTATIONAL_COMPONENTS) {
      const content = source(component.path)
      expect(content, `${component.name} should exist`).not.toBe('')
      expect(content).not.toMatch(/stores\/research|services\/research|\bfetch\(|\baxios\b/)
    }
  })
})

describe('stable loading, empty and error integration', () => {
  const stateContent = source('components/research/ResearchState.vue')

  it.each(RESEARCH_STATES)('ResearchState maps %s to consistent user copy', (state, label) => {
    expect(stateContent).toContain(state)
    expect(stateContent).toContain(label)
  })

  it.each(ASYNC_STATE_PAGES)('%s delegates asynchronous presentation to ResearchState', (page) => {
    const content = source(`pages/research/${page}.vue`)
    expect(content).toContain('ResearchState')
    expect(content).toMatch(/isLoading|loading/)
    expect(content).toMatch(/error/)
  })
})

describe('preserved router and architecture contracts', () => {
  const routerContent = source('router/index.ts')

  it('preserves hash history, auth guard and original routes', () => {
    expect(routerContent).toContain('createWebHashHistory')
    expect(routerContent).toContain('router.beforeEach')
    for (const route of ['login', 'debug-ping', 'dashboard', 'chat', 'knowledge']) {
      expect(routerContent).toContain(`name: '${route}'`)
    }
  })

  it.each([
    ['ProjectCard', 'progress'], ['InsightCard', 'severity'], ['EvidenceCard', 'confidence'],
    ['CitationCard', 'tags'], ['AgentCard', 'task'], ['Timeline', 'steps'],
    ['ScientificMetric', 'trend'], ['ChartPanel', 'type'], ['StatusBadge', 'status']
  ])('%s remains a typed research component with %s', (component, prop) => {
    const content = source(`components/research/${component}.vue`)
    expect(content).toContain('<template>')
    expect(content).toContain('defineProps')
    expect(content).toMatch(new RegExp(`\\b${prop}\\??\\s*:`))
  })

  it.each([
    ['agent.store.ts', 'research-agent.service'], ['knowledge.store.ts', 'knowledge.service'],
    ['experiment.store.ts', 'experiment.service'], ['dataset.store.ts', 'data-analysis.service'],
    ['manuscript.store.ts', 'manuscript.service']
  ])('%s remains connected to %s', (store, service) => {
    expect(source(`stores/research/${store}`)).toContain(service)
  })

  it.each([
    ['Dashboard', 'loadReport'], ['Assistant', 'loadSessions'], ['ProjectWorkspace', 'loadDocuments'],
    ['Literature', 'loadAssessments'], ['Experiment', 'loadDesign'], ['DataAnalysis', 'loadReport'],
    ['Manuscript', 'loadManuscript'], ['AgentCenter', 'loadSessions']
  ])('%s initializes real Store data with %s', (page, action) => {
    const content = source(`pages/research/${page}.vue`)
    expect(content).toContain('onMounted')
    expect(content).toContain(action)
  })

  it('keeps page transport and runtime boundaries intact', () => {
    for (const [page] of RESEARCH_PAGES) {
      const content = source(`pages/research/${page}.vue`)
      expect(content).not.toMatch(/from .*backend|ResearchAgentRuntime|executeTool|\bfetch\(|\baxios\b/)
    }
  })

  it('keeps Store and service security boundaries intact', () => {
    for (const [file] of STORE_CONTRACTS) {
      const content = source(`stores/research/${file}`)
      expect(content).not.toMatch(/from .*backend|WebSocket/)
    }
    for (const file of ['research-agent', 'knowledge', 'literature', 'experiment', 'data-analysis', 'manuscript']) {
      const content = source(`services/research/${file}.service.ts`)
      expect(content).not.toMatch(/from .*backend|localStorage|API[_ ]?KEY|Anthropic|OpenAI/)
    }
  })

  it('preserves key interaction and empty-state affordances', () => {
    const assistant = source('pages/research/Assistant.vue')
    expect(assistant).toContain('agentStore.isSending')
    expect(assistant).toContain(':disabled="agentStore.isSending"')
    expect(assistant).toContain('AI 正在分析...')
    const literature = source('pages/research/Literature.vue')
    expect(literature).toContain('literature__search')
    expect(literature).toContain('literature__empty')
    expect(source('pages/research/Experiment.vue')).toContain('experiment__empty')
    const analysis = source('pages/research/DataAnalysis.vue')
    expect(analysis).toContain('store.isLoading')
    expect(analysis).toContain('data-analysis-state')
    expect(analysis).toContain('@retry="loadReport"')
  })
})

describe('fixture-driven information architecture', () => {
  it.each(RESEARCH_PAGES)('%s contains durable labels instead of fixed mock values', (page, labels) => {
    const content = source(`pages/research/${page}.vue`)
    for (const label of durableLabels(page, labels)) expect(content).toContain(label)
  })

  it('does not encode the legacy demo dataset in UI contracts', () => {
    const allPages = RESEARCH_PAGES.map(([page]) => source(`pages/research/${page}.vue`)).join('\n').normalize('NFKC')
    expect(allPages).not.toMatch(/O3-MNBs|EXP-001|0\.9887|0\.0243|16:22/)
  })
})
