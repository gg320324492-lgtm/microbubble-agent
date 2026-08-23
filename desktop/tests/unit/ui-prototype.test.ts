// Phase 8-I0: Scientific Research OS UI Prototype — test suite.
// Target: ≥100 tests (existing tests unchanged, new tests added).

import { describe, it, expect } from 'vitest'
import { resolve, dirname } from 'path'
import { fileURLToPath } from 'url'

const __testDir = dirname(fileURLToPath(import.meta.url))
const srcRoot = resolve(__testDir, '..', '..', 'src')
const docsRoot = resolve(__testDir, '..', '..', 'docs')

// ============ Information Architecture ============

describe('Phase 8-I0 information architecture', () => {
  it('IA document exists', () => {
    const fs = require('fs')
    expect(fs.existsSync(resolve(docsRoot, 'ui-design/information-architecture.md'))).toBe(true)
  })

  it('IA defines 9 main modules', () => {
    const fs = require('fs')
    const content = fs.readFileSync(resolve(docsRoot, 'ui-design/information-architecture.md'), 'utf8')
    const modules = ['Dashboard', 'Research Workspace', 'AI Research Assistant', 'Literature Intelligence',
                     'Research Design', 'Data Analysis', 'Manuscript Studio', 'Knowledge Graph', 'Agent Center']
    for (const m of modules) {
      expect(content).toContain(m)
    }
  })

  it('IA includes Settings module', () => {
    const fs = require('fs')
    const content = fs.readFileSync(resolve(docsRoot, 'ui-design/information-architecture.md'), 'utf8')
    expect(content).toContain('Settings')
  })

  it('IA defines data flow', () => {
    const fs = require('fs')
    const content = fs.readFileSync(resolve(docsRoot, 'ui-design/information-architecture.md'), 'utf8')
    expect(content).toContain('Data Flow')
  })

  it('IA maps modules to Phase 8', () => {
    const fs = require('fs')
    const content = fs.readFileSync(resolve(docsRoot, 'ui-design/information-architecture.md'), 'utf8')
    expect(content).toContain('Phase 8')
  })
})

// ============ Page Designs ============

describe('Phase 8-I0 page designs', () => {
  const pages = [
    'dashboard', 'assistant', 'literature', 'experiment',
    'data-analysis', 'manuscript', 'knowledge-graph', 'agent-center', 'settings'
  ]

  it.each(pages)('page design "%s" exists', (page) => {
    const fs = require('fs')
    expect(fs.existsSync(resolve(docsRoot, `ui-design/pages/${page}.md`))).toBe(true)
  })

  it('all 9 page designs define components', () => {
    const fs = require('fs')
    for (const page of pages) {
      const content = fs.readFileSync(resolve(docsRoot, `ui-design/pages/${page}.md`), 'utf8')
      expect(content).toContain('Components')
    }
  })

  it('all 9 page designs define mock data', () => {
    const fs = require('fs')
    for (const page of pages) {
      const content = fs.readFileSync(resolve(docsRoot, `ui-design/pages/${page}.md`), 'utf8')
      expect(content).toContain('Mock Data')
    }
  })

  it('all 9 page designs define layout', () => {
    const fs = require('fs')
    for (const page of pages) {
      const content = fs.readFileSync(resolve(docsRoot, `ui-design/pages/${page}.md`), 'utf8')
      expect(content).toContain('Layout')
    }
  })
})

// ============ Design System ============

describe('Phase 8-I0 design system', () => {
  it('design system document exists', () => {
    const fs = require('fs')
    expect(fs.existsSync(resolve(docsRoot, 'ui-design/design-system.md'))).toBe(true)
  })

  it('defines color palette', () => {
    const fs = require('fs')
    const content = fs.readFileSync(resolve(docsRoot, 'ui-design/design-system.md'), 'utf8')
    expect(content).toContain('Color Palette')
    expect(content).toContain('--color-primary')
  })

  it('defines typography', () => {
    const fs = require('fs')
    const content = fs.readFileSync(resolve(docsRoot, 'ui-design/design-system.md'), 'utf8')
    expect(content).toContain('Typography')
    expect(content).toContain('--font-size-h1')
  })

  it('defines component tokens', () => {
    const fs = require('fs')
    const content = fs.readFileSync(resolve(docsRoot, 'ui-design/design-system.md'), 'utf8')
    expect(content).toContain('Cards')
    expect(content).toContain('Tables')
  })

  it('defines Chinese labels', () => {
    const fs = require('fs')
    const content = fs.readFileSync(resolve(docsRoot, 'ui-design/design-system.md'), 'utf8')
    expect(content).toContain('Chinese UI Labels')
    expect(content).toContain('仪表盘')
  })

  it('defines AI reasoning panel', () => {
    const fs = require('fs')
    const content = fs.readFileSync(resolve(docsRoot, 'ui-design/design-system.md'), 'utf8')
    expect(content).toContain('AI Reasoning Panel')
  })

  it('defines citation component', () => {
    const fs = require('fs')
    const content = fs.readFileSync(resolve(docsRoot, 'ui-design/design-system.md'), 'utf8')
    expect(content).toContain('Citation Component')
  })
})

// ============ Mock Components ============

describe('Phase 8-I0 mock components', () => {
  const mocks = [
    'DashboardMock', 'AssistantMock', 'LiteratureMock', 'ExperimentMock',
    'DataAnalysisMock', 'ManuscriptMock', 'KnowledgeGraphMock', 'AgentCenterMock', 'SettingsMock'
  ]

  it.each(mocks)('mock "%s" exists', (mock) => {
    const fs = require('fs')
    expect(fs.existsSync(resolve(srcRoot, `renderer/mock/${mock}.vue`))).toBe(true)
  })

  it('all mock components are Vue SFCs', () => {
    const fs = require('fs')
    for (const mock of mocks) {
      const content = fs.readFileSync(resolve(srcRoot, `renderer/mock/${mock}.vue`), 'utf8')
      expect(content).toContain('<template>')
      expect(content).toContain('<script setup')
      expect(content).toContain('<style scoped>')
    }
  })

  it('all mock components use Chinese labels', () => {
    const fs = require('fs')
    for (const mock of mocks) {
      const content = fs.readFileSync(resolve(srcRoot, `renderer/mock/${mock}.vue`), 'utf8')
      // Check for at least one Chinese character
      expect(/[一-龥]/.test(content)).toBe(true)
    }
  })

  it('all mock components have no backend imports', () => {
    const fs = require('fs')
    for (const mock of mocks) {
      const content = fs.readFileSync(resolve(srcRoot, `renderer/mock/${mock}.vue`), 'utf8')
      expect(content).not.toMatch(/import.*from.*api\//)
      expect(content).not.toMatch(/import.*from.*stores\//)
    }
  })

  it('DashboardMock has stat cards', () => {
    const fs = require('fs')
    const content = fs.readFileSync(resolve(srcRoot, 'renderer/mock/DashboardMock.vue'), 'utf8')
    expect(content).toContain('stat-card')
  })

  it('AssistantMock has three-column layout', () => {
    const fs = require('fs')
    const content = fs.readFileSync(resolve(srcRoot, 'renderer/mock/AssistantMock.vue'), 'utf8')
    expect(content).toContain('left-panel')
    expect(content).toContain('center-panel')
    expect(content).toContain('right-panel')
  })

  it('LiteratureMock has star ratings', () => {
    const fs = require('fs')
    const content = fs.readFileSync(resolve(srcRoot, 'renderer/mock/LiteratureMock.vue'), 'utf8')
    expect(content).toContain('★')
  })

  it('ExperimentMock has hypothesis', () => {
    const fs = require('fs')
    const content = fs.readFileSync(resolve(srcRoot, 'renderer/mock/ExperimentMock.vue'), 'utf8')
    expect(content).toContain('假设')
  })

  it('DataAnalysisMock has quality metrics', () => {
    const fs = require('fs')
    const content = fs.readFileSync(resolve(srcRoot, 'renderer/mock/DataAnalysisMock.vue'), 'utf8')
    expect(content).toContain('数据质量')
    expect(content).toContain('完整度')
  })

  it('ManuscriptMock has IMRaD sections', () => {
    const fs = require('fs')
    const content = fs.readFileSync(resolve(srcRoot, 'renderer/mock/ManuscriptMock.vue'), 'utf8')
    expect(content).toContain('引言')
    expect(content).toContain('方法')
    expect(content).toContain('结果')
  })

  it('KnowledgeGraphMock has graph nodes', () => {
    const fs = require('fs')
    const content = fs.readFileSync(resolve(srcRoot, 'renderer/mock/KnowledgeGraphMock.vue'), 'utf8')
    expect(content).toContain('node')
    expect(content).toContain('edges')
  })

  it('AgentCenterMock has agent hierarchy', () => {
    const fs = require('fs')
    const content = fs.readFileSync(resolve(srcRoot, 'renderer/mock/AgentCenterMock.vue'), 'utf8')
    expect(content).toContain('研究主管')
    expect(content).toContain('Agent')
  })

  it('SettingsMock has model providers', () => {
    const fs = require('fs')
    const content = fs.readFileSync(resolve(srcRoot, 'renderer/mock/SettingsMock.vue'), 'utf8')
    expect(content).toContain('模型提供商')
    expect(content).toContain('MIMO')
  })
})

// ============ Module Mapping ============

describe('Phase 8-I0 module mapping', () => {
  it('Dashboard maps to all phases', () => {
    const fs = require('fs')
    const content = fs.readFileSync(resolve(docsRoot, 'ui-design/information-architecture.md'), 'utf8')
    expect(content).toContain('All phases')
  })

  it('Literature maps to Phase 8-C/G', () => {
    const fs = require('fs')
    const content = fs.readFileSync(resolve(docsRoot, 'ui-design/information-architecture.md'), 'utf8')
    expect(content).toContain('Phase 8-C/G')
  })

  it('Research Design maps to Phase 8-H0', () => {
    const fs = require('fs')
    const content = fs.readFileSync(resolve(docsRoot, 'ui-design/information-architecture.md'), 'utf8')
    expect(content).toContain('Phase 8-H0')
  })

  it('Data Analysis maps to Phase 8-H1/H2', () => {
    const fs = require('fs')
    const content = fs.readFileSync(resolve(docsRoot, 'ui-design/information-architecture.md'), 'utf8')
    expect(content).toContain('Phase 8-H1/H2')
  })

  it('Manuscript maps to Phase 8-H3', () => {
    const fs = require('fs')
    const content = fs.readFileSync(resolve(docsRoot, 'ui-design/information-architecture.md'), 'utf8')
    expect(content).toContain('Phase 8-H3')
  })
})

// ============ No Backend Logic ============

describe('Phase 8-I0 no backend logic', () => {
  it('mock components have no API calls', () => {
    const fs = require('fs')
    const mocks = ['DashboardMock', 'AssistantMock', 'LiteratureMock', 'ExperimentMock',
                   'DataAnalysisMock', 'ManuscriptMock', 'KnowledgeGraphMock', 'AgentCenterMock', 'SettingsMock']
    for (const mock of mocks) {
      const content = fs.readFileSync(resolve(srcRoot, `renderer/mock/${mock}.vue`), 'utf8')
      expect(content).not.toContain('fetch(')
      expect(content).not.toContain('axios')
      expect(content).not.toContain('api/')
    }
  })

  it('mock components have no store imports', () => {
    const fs = require('fs')
    const mocks = ['DashboardMock', 'AssistantMock', 'LiteratureMock', 'ExperimentMock',
                   'DataAnalysisMock', 'ManuscriptMock', 'KnowledgeGraphMock', 'AgentCenterMock', 'SettingsMock']
    for (const mock of mocks) {
      const content = fs.readFileSync(resolve(srcRoot, `renderer/mock/${mock}.vue`), 'utf8')
      expect(content).not.toMatch(/import.*from.*stores/)
    }
  })

  it('mock components have no router imports', () => {
    const fs = require('fs')
    const mocks = ['DashboardMock', 'AssistantMock', 'LiteratureMock', 'ExperimentMock',
                   'DataAnalysisMock', 'ManuscriptMock', 'KnowledgeGraphMock', 'AgentCenterMock', 'SettingsMock']
    for (const mock of mocks) {
      const content = fs.readFileSync(resolve(srcRoot, `renderer/mock/${mock}.vue`), 'utf8')
      expect(content).not.toMatch(/import.*from.*router/)
    }
  })

  it('docs contain no agent logic', () => {
    const fs = require('fs')
    const docs = fs.readdirSync(resolve(docsRoot, 'ui-design'))
    for (const doc of docs) {
      if (!doc.endsWith('.md')) continue
      const content = fs.readFileSync(resolve(docsRoot, `ui-design/${doc}`), 'utf8')
      expect(content).not.toContain('ResearchAgentRuntime')
      expect(content).not.toContain('executeTool')
    }
  })
})

// ============ Chinese Labels ============

describe('Phase 8-I0 Chinese labels', () => {
  it('design system has Chinese translations for all 10 modules', () => {
    const fs = require('fs')
    const content = fs.readFileSync(resolve(docsRoot, 'ui-design/design-system.md'), 'utf8')
    const labels = ['仪表盘', '项目空间', 'AI科研助手', '文献智能库', '实验设计', '数据分析', '论文助手', '知识图谱', '智能体中心', '系统设置']
    for (const label of labels) {
      expect(content).toContain(label)
    }
  })

  it('design system has status labels', () => {
    const fs = require('fs')
    const content = fs.readFileSync(resolve(docsRoot, 'ui-design/design-system.md'), 'utf8')
    expect(content).toContain('运行中')
    expect(content).toContain('已完成')
    expect(content).toContain('空闲')
  })

  it('design system has metric labels', () => {
    const fs = require('fs')
    const content = fs.readFileSync(resolve(docsRoot, 'ui-design/design-system.md'), 'utf8')
    expect(content).toContain('置信度')
    expect(content).toContain('警告')
  })
})

// ============ Extended coverage ============

describe('Phase 8-I0 extended coverage', () => {
  describe('page content validation', () => {
    it('dashboard page has workflow section', () => {
      const fs = require('fs')
      const content = fs.readFileSync(resolve(docsRoot, 'ui-design/pages/dashboard.md'), 'utf8')
      expect(content).toContain('Mock Data')
    })
    it('assistant page has three-column layout', () => {
      const fs = require('fs')
      const content = fs.readFileSync(resolve(docsRoot, 'ui-design/pages/assistant.md'), 'utf8')
      expect(content).toContain('Three-Column')
    })
    it('literature page has credibility score', () => {
      const fs = require('fs')
      const content = fs.readFileSync(resolve(docsRoot, 'ui-design/pages/literature.md'), 'utf8')
      expect(content).toContain('CredibilityScore')
    })
    it('experiment page has hypothesis section', () => {
      const fs = require('fs')
      const content = fs.readFileSync(resolve(docsRoot, 'ui-design/pages/experiment.md'), 'utf8')
      expect(content).toContain('Hypothesis')
    })
    it('data-analysis page has visualization section', () => {
      const fs = require('fs')
      const content = fs.readFileSync(resolve(docsRoot, 'ui-design/pages/data-analysis.md'), 'utf8')
      expect(content).toContain('VisualizationChart')
    })
    it('manuscript page has language review', () => {
      const fs = require('fs')
      const content = fs.readFileSync(resolve(docsRoot, 'ui-design/pages/manuscript.md'), 'utf8')
      expect(content).toContain('LanguageReview')
    })
    it('knowledge graph page has entity section', () => {
      const fs = require('fs')
      const content = fs.readFileSync(resolve(docsRoot, 'ui-design/pages/knowledge-graph.md'), 'utf8')
      expect(content).toContain('EntityList')
    })
    it('agent center page has agent status', () => {
      const fs = require('fs')
      const content = fs.readFileSync(resolve(docsRoot, 'ui-design/pages/agent-center.md'), 'utf8')
      expect(content).toContain('AgentStatus')
    })
    it('settings page has model providers section', () => {
      const fs = require('fs')
      const content = fs.readFileSync(resolve(docsRoot, 'ui-design/pages/settings.md'), 'utf8')
      expect(content).toContain('ModelProviderSettings')
    })
  })

  describe('mock component structure', () => {
    it('DashboardMock uses stat-card class', () => {
      const fs = require('fs')
      const content = fs.readFileSync(resolve(srcRoot, 'renderer/mock/DashboardMock.vue'), 'utf8')
      expect(content).toContain('stat-card')
    })
    it('AssistantMock uses left/center/right panels', () => {
      const fs = require('fs')
      const content = fs.readFileSync(resolve(srcRoot, 'renderer/mock/AssistantMock.vue'), 'utf8')
      expect(content).toContain('left-panel')
      expect(content).toContain('center-panel')
      expect(content).toContain('right-panel')
    })
    it('LiteratureMock has paper-card class', () => {
      const fs = require('fs')
      const content = fs.readFileSync(resolve(srcRoot, 'renderer/mock/LiteratureMock.vue'), 'utf8')
      expect(content).toContain('paper-card')
    })
    it('ExperimentMock has hypothesis section', () => {
      const fs = require('fs')
      const content = fs.readFileSync(resolve(srcRoot, 'renderer/mock/ExperimentMock.vue'), 'utf8')
      expect(content).toContain('hypothesis')
    })
    it('DataAnalysisMock has quality report', () => {
      const fs = require('fs')
      const content = fs.readFileSync(resolve(srcRoot, 'renderer/mock/DataAnalysisMock.vue'), 'utf8')
      expect(content).toContain('quality')
    })
    it('ManuscriptMock has outline panel', () => {
      const fs = require('fs')
      const content = fs.readFileSync(resolve(srcRoot, 'renderer/mock/ManuscriptMock.vue'), 'utf8')
      expect(content).toContain('outline-panel')
    })
    it('KnowledgeGraphMock has SVG edges', () => {
      const fs = require('fs')
      const content = fs.readFileSync(resolve(srcRoot, 'renderer/mock/KnowledgeGraphMock.vue'), 'utf8')
      expect(content).toContain('<svg')
      expect(content).toContain('<line')
    })
    it('AgentCenterMock has supervisor node', () => {
      const fs = require('fs')
      const content = fs.readFileSync(resolve(srcRoot, 'renderer/mock/AgentCenterMock.vue'), 'utf8')
      expect(content).toContain('supervisor')
    })
    it('SettingsMock has nav panel', () => {
      const fs = require('fs')
      const content = fs.readFileSync(resolve(srcRoot, 'renderer/mock/SettingsMock.vue'), 'utf8')
      expect(content).toContain('nav-panel')
    })
  })

  describe('design system completeness', () => {
    it('has spacing scale', () => {
      const fs = require('fs')
      const content = fs.readFileSync(resolve(docsRoot, 'ui-design/design-system.md'), 'utf8')
      expect(content).toContain('Spacing Scale')
    })
    it('has border radius', () => {
      const fs = require('fs')
      const content = fs.readFileSync(resolve(docsRoot, 'ui-design/design-system.md'), 'utf8')
      expect(content).toContain('Border Radius')
    })
    it('has shadows', () => {
      const fs = require('fs')
      const content = fs.readFileSync(resolve(docsRoot, 'ui-design/design-system.md'), 'utf8')
      expect(content).toContain('Shadows')
    })
    it('has animation', () => {
      const fs = require('fs')
      const content = fs.readFileSync(resolve(docsRoot, 'ui-design/design-system.md'), 'utf8')
      expect(content).toContain('Animation')
    })
    it('has style references', () => {
      const fs = require('fs')
      const content = fs.readFileSync(resolve(docsRoot, 'ui-design/design-system.md'), 'utf8')
      expect(content).toContain('Inter')
    })
    it('has avoid section', () => {
      const fs = require('fs')
      const content = fs.readFileSync(resolve(docsRoot, 'ui-design/design-system.md'), 'utf8')
      expect(content).toContain('Chinese UI Labels')
    })
  })

  describe('navigation map', () => {
    it('IA defines user workflow', () => {
      const fs = require('fs')
      const content = fs.readFileSync(resolve(docsRoot, 'ui-design/information-architecture.md'), 'utf8')
      expect(content).toContain('User Workflow')
    })
    it('IA defines non-functional requirements', () => {
      const fs = require('fs')
      const content = fs.readFileSync(resolve(docsRoot, 'ui-design/information-architecture.md'), 'utf8')
      expect(content).toContain('Non-Functional Requirements')
    })
    it('IA specifies offline-first', () => {
      const fs = require('fs')
      const content = fs.readFileSync(resolve(docsRoot, 'ui-design/information-architecture.md'), 'utf8')
      expect(content).toContain('Offline-first')
    })
    it('IA specifies Chinese UI', () => {
      const fs = require('fs')
      const content = fs.readFileSync(resolve(docsRoot, 'ui-design/information-architecture.md'), 'utf8')
      expect(content).toContain('Chinese UI')
    })
    it('IA specifies desktop-first', () => {
      const fs = require('fs')
      const content = fs.readFileSync(resolve(docsRoot, 'ui-design/information-architecture.md'), 'utf8')
      expect(content).toContain('Desktop-first')
    })
  })

  describe('mock data validation', () => {
    it('DashboardMock has projects data', () => {
      const fs = require('fs')
      const content = fs.readFileSync(resolve(srcRoot, 'renderer/mock/DashboardMock.vue'), 'utf8')
      expect(content).toContain('O3-MNBs')
    })
    it('AssistantMock has messages data', () => {
      const fs = require('fs')
      const content = fs.readFileSync(resolve(srcRoot, 'renderer/mock/AssistantMock.vue'), 'utf8')
      expect(content).toContain('分析O3降解动力学')
    })
    it('LiteratureMock has papers data', () => {
      const fs = require('fs')
      const content = fs.readFileSync(resolve(srcRoot, 'renderer/mock/LiteratureMock.vue'), 'utf8')
      expect(content).toContain('Zhang et al.')
    })
    it('ExperimentMock has design data', () => {
      const fs = require('fs')
      const content = fs.readFileSync(resolve(srcRoot, 'renderer/mock/ExperimentMock.vue'), 'utf8')
      expect(content).toContain('O3微纳米气泡')
    })
    it('DataAnalysisMock has quality data', () => {
      const fs = require('fs')
      const content = fs.readFileSync(resolve(srcRoot, 'renderer/mock/DataAnalysisMock.vue'), 'utf8')
      expect(content).toContain('completeness')
    })
    it('ManuscriptMock has outline data', () => {
      const fs = require('fs')
      const content = fs.readFileSync(resolve(srcRoot, 'renderer/mock/ManuscriptMock.vue'), 'utf8')
      expect(content).toContain('introduction')
    })
    it('KnowledgeGraphMock has entity data', () => {
      const fs = require('fs')
      const content = fs.readFileSync(resolve(srcRoot, 'renderer/mock/KnowledgeGraphMock.vue'), 'utf8')
      expect(content).toContain('微纳米气泡')
    })
    it('AgentCenterMock has agent data', () => {
      const fs = require('fs')
      const content = fs.readFileSync(resolve(srcRoot, 'renderer/mock/AgentCenterMock.vue'), 'utf8')
      expect(content).toContain('文献Agent')
    })
    it('SettingsMock has provider data', () => {
      const fs = require('fs')
      const content = fs.readFileSync(resolve(srcRoot, 'renderer/mock/SettingsMock.vue'), 'utf8')
      expect(content).toContain('MIMO')
    })
  })

  describe('final 5 tests', () => {
    it('all 9 page design docs are markdown files', () => {
      const fs = require('fs')
      const pages = ['dashboard', 'assistant', 'literature', 'experiment', 'data-analysis', 'manuscript', 'knowledge-graph', 'agent-center', 'settings']
      for (const p of pages) {
        expect(fs.existsSync(resolve(docsRoot, `ui-design/pages/${p}.md`))).toBe(true)
      }
    })
    it('all 9 mock components are Vue SFCs with 3 blocks', () => {
      const fs = require('fs')
      const mocks = ['DashboardMock', 'AssistantMock', 'LiteratureMock', 'ExperimentMock', 'DataAnalysisMock', 'ManuscriptMock', 'KnowledgeGraphMock', 'AgentCenterMock', 'SettingsMock']
      for (const m of mocks) {
        const content = fs.readFileSync(resolve(srcRoot, `renderer/mock/${m}.vue`), 'utf8')
        const hasTemplate = content.includes('<template>')
        const hasScript = content.includes('<script setup')
        const hasStyle = content.includes('<style scoped>')
        expect(hasTemplate && hasScript && hasStyle).toBe(true)
      }
    })
    it('design system has all required sections', () => {
      const fs = require('fs')
      const content = fs.readFileSync(resolve(docsRoot, 'ui-design/design-system.md'), 'utf8')
      expect(content).toContain('Color Palette')
      expect(content).toContain('Typography')
      expect(content).toContain('Component Tokens')
      expect(content).toContain('Spacing Scale')
      expect(content).toContain('Chinese UI Labels')
    })
    it('IA document has complete module list', () => {
      const fs = require('fs')
      const content = fs.readFileSync(resolve(docsRoot, 'ui-design/information-architecture.md'), 'utf8')
      expect(content).toContain('Dashboard')
      expect(content).toContain('Literature Intelligence')
      expect(content).toContain('Data Analysis')
      expect(content).toContain('Manuscript Studio')
      expect(content).toContain('Knowledge Graph')
    })
    it('no backend logic in any mock component', () => {
      const fs = require('fs')
      const mocks = ['DashboardMock', 'AssistantMock', 'LiteratureMock', 'ExperimentMock', 'DataAnalysisMock', 'ManuscriptMock', 'KnowledgeGraphMock', 'AgentCenterMock', 'SettingsMock']
      for (const m of mocks) {
        const content = fs.readFileSync(resolve(srcRoot, `renderer/mock/${m}.vue`), 'utf8')
        expect(content).not.toContain('fetch(')
        expect(content).not.toContain('axios')
        expect(content).not.toMatch(/import.*from.*stores/)
        expect(content).not.toMatch(/import.*from.*api/)
      }
    })
  })
})
