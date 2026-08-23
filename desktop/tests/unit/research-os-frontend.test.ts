import { readFileSync, existsSync } from 'node:fs'
import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'
import { defineComponent } from 'vue'
import { describe, expect, it } from 'vitest'
import { mountResearch } from '../helpers/mount-research'
import { RESEARCH_NAV, RESEARCH_PAGES, RESEARCH_STATES } from '../fixtures/research-ui'
import StatusBadge from '../../src/renderer/src/components/research/StatusBadge.vue'

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

describe('research UI test harness', () => {
  it('mounts Vue with isolated Pinia and memory router instances', async () => {
    const Probe = defineComponent({ template: '<RouterLink to="/research/agent-center">Agent</RouterLink>' })
    const { wrapper, pinia, router } = await mountResearch(Probe)

    expect(wrapper.get('a').attributes('href')).toBe('/research/agent-center')
    expect(router.currentRoute.value.name).toBe('research-dashboard')
    expect(pinia.state.value).toEqual({})
    wrapper.unmount()
  })

  it('mounts an existing production SFC and renders its props', async () => {
    const { wrapper } = await mountResearch(StatusBadge, {
      props: { status: 'success', label: '已完成' }
    })
    expect(wrapper.classes()).toContain('status-badge')
    expect(wrapper.text()).toBe('已完成')
    expect(wrapper.attributes('style')).toContain('background')
    wrapper.unmount()
  })
})

describe('shared visual foundation', () => {
  const tokenPath = resolve(rendererRoot, 'styles/research-design-tokens.css')

  it('defines the shared research token sheet', () => {
    expect(existsSync(tokenPath), 'styles/research-design-tokens.css should exist').toBe(true)
    const content = source('styles/research-design-tokens.css')
    expect(content).toContain('--research-sidebar-width')
    expect(content).toContain('--research-primary-500')
    expect(content).toContain('--research-bg-card')
  })

  it('sidebar uses shared research tokens and custom icons', () => {
    const content = source('layouts/Sidebar.vue')
    expect(content).toContain('var(--research-sidebar-width)')
    expect(content).toContain('ResearchIcon')
    expect(content).not.toMatch(/[💬📁📚🧪📊📝🔗🤖⚙️]/u)
    expect(content).not.toContain('#0f172a')
    expect(content).not.toContain('#f97316')
    expect(content).not.toContain('width: 220px')
  })

  it('provides reusable icon, panel and state primitives', () => {
    for (const [component, path] of [
      ['ResearchIcon', 'components/icons/ResearchIcon.vue'],
      ['ResearchPanel', 'components/research/ResearchPanel.vue'],
      ['ResearchState', 'components/research/ResearchState.vue']
    ]) {
      expect(
        existsSync(resolve(rendererRoot, path)),
        `${component}.vue should exist`
      ).toBe(true)
    }
  })
})

describe('research navigation contract', () => {
  const sidebarContent = source('layouts/Sidebar.vue')
  const routerContent = source('router/index.ts')

  it.each(RESEARCH_NAV)('renders %s with route %s and icon %s', (label, routeName, icon) => {
    const item = objectContainingMarker(sidebarContent, `routeName: '${routeName}'`)
    expect(item).not.toBe('')
    expect(item).toContain(`label: '${label}'`)
    expect(item).toContain(`routeName: '${routeName}'`)
    expect(item).toContain(`icon: '${icon}'`)
  })

  it('does not combine navigation fields from adjacent objects', () => {
    const sample = "[{ label: 'A', routeName: 'route-a', icon: 'one' }, { label: 'B', routeName: 'route-b', icon: 'two', meta: { nested: true } }]"
    const item = objectContainingMarker(sample, "routeName: 'route-b'")
    expect(item).toContain("label: 'B'")
    expect(item).toContain("meta: { nested: true }")
    expect(item).not.toContain("label: 'A'")
  })

  it('opens on the research dashboard by default', () => {
    expect(objectContainingMarker(routerContent, "path: '/'" )).toMatch(
      /redirect:\s*(?:\(\)\s*=>\s*['"]\/research\/dashboard['"]|\{\s*name:\s*['"]research-dashboard['"]\s*\})/
    )
  })

  it('loads the shared research design tokens from the renderer entry', () => {
    expect(source('main.ts')).toContain("import './styles/research-design-tokens.css'")
  })
})

describe('unified research states', () => {
  const stateContent = source('components/research/ResearchState.vue')

  it.each(RESEARCH_STATES)('supports the %s state with approved copy', (state, label) => {
    expect(stateContent).toContain(state)
    expect(stateContent).toContain(label)
  })
})

describe('approved Chinese page structure', () => {
  it.each(RESEARCH_PAGES)('%s exposes its approved information architecture', (page, labels) => {
    const content = source(`pages/research/${page}.vue`)
    expect(content, `${page}.vue should exist`).not.toBe('')
    for (const label of labels) expect(content).toContain(label)
  })

  it.each(['Dashboard', 'DataAnalysis'])('%s renders the common dataset state primitive', (page) => {
    expect(source(`pages/research/${page}.vue`)).toContain('ResearchState')
  })

  it('Dashboard renders a stable dataset state contract', () => {
    const content = source('pages/research/Dashboard.vue')
    expect(content).toContain('datasetStore.isLoading')
    expect(content).toContain('ResearchState')
  })
})

describe('research page and presentation boundaries', () => {
  const storePages = ['Dashboard', 'Assistant', 'ProjectWorkspace', 'Literature', 'Experiment', 'DataAnalysis', 'Manuscript', 'AgentCenter']

  it.each(storePages)('%s may connect to a real research Store', (page) => {
    expect(source(`pages/research/${page}.vue`)).toMatch(/stores\/research\/[^'"]+\.store/)
  })

  it('research pages may connect Pinia while presentational components stay isolated', () => {
    const content = source('components/research/ResearchPanel.vue')
    expect(content).not.toMatch(/stores\/research|services\/research/)
  })

  it('removes pictographic Emoji from research page UI', () => {
    const content = RESEARCH_PAGES.map(([page]) => source(`pages/research/${page}.vue`)).join('\n')
    expect(content).not.toMatch(/[💬📁📚🧪📊📝🔗🤖⚙️💡⚠️✅]/u)
  })
})
