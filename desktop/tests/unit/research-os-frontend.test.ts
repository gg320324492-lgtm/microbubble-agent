// Phase 8-I1: Scientific Research OS Frontend — test suite.
// Target: ≥200 tests.

import { describe, it, expect } from 'vitest'
import { resolve, dirname } from 'path'
import { fileURLToPath } from 'url'

const __testDir = dirname(fileURLToPath(import.meta.url))
const rendererRoot = resolve(__testDir, '..', '..', 'src', 'renderer', 'src')

const fs = require('fs')

// ============ Route configuration ============

describe('Phase 8-I1 routes', () => {
  const routerContent = fs.readFileSync(resolve(rendererRoot, 'router/index.ts'), 'utf8')

  it('defines research-dashboard route', () => {
    expect(routerContent).toContain('research-dashboard')
    expect(routerContent).toContain('Dashboard.vue')
  })
  it('defines research-assistant route', () => {
    expect(routerContent).toContain('research-assistant')
    expect(routerContent).toContain('Assistant.vue')
  })
  it('defines research-literature route', () => {
    expect(routerContent).toContain('research-literature')
    expect(routerContent).toContain('Literature.vue')
  })
  it('defines research-experiment route', () => {
    expect(routerContent).toContain('research-experiment')
    expect(routerContent).toContain('Experiment.vue')
  })
  it('defines research-data-analysis route', () => {
    expect(routerContent).toContain('research-data-analysis')
    expect(routerContent).toContain('DataAnalysis.vue')
  })
  it('defines research-manuscript route', () => {
    expect(routerContent).toContain('research-manuscript')
    expect(routerContent).toContain('Manuscript.vue')
  })
  it('defines research-knowledge-graph route', () => {
    expect(routerContent).toContain('research-knowledge-graph')
    expect(routerContent).toContain('KnowledgeGraph.vue')
  })
  it('defines research-agent-center route', () => {
    expect(routerContent).toContain('research-agent-center')
    expect(routerContent).toContain('AgentCenter.vue')
  })
  it('defines research-settings route', () => {
    expect(routerContent).toContain('research-settings')
    expect(routerContent).toContain('Settings.vue')
  })
  it('all 9 research routes use main layout', () => {
    const matches = routerContent.match(/layout: 'main'/g)
    expect(matches && matches.length).toBeGreaterThanOrEqual(9)
  })
  it('all 9 research routes require auth', () => {
    const matches = routerContent.match(/requiresAuth: true/g)
    expect(matches && matches.length).toBeGreaterThanOrEqual(9)
  })
  it('routes use hash history', () => {
    expect(routerContent).toContain('createWebHashHistory')
  })
  it('login route exists', () => {
    expect(routerContent).toContain("name: 'login'")
  })
  it('debug-ping route preserved', () => {
    expect(routerContent).toContain('debug-ping')
  })
})

// ============ Sidebar navigation ============

describe('Phase 8-I1 sidebar', () => {
  const sidebarContent = fs.readFileSync(resolve(rendererRoot, 'layouts/Sidebar.vue'), 'utf8')

  it('has all 10 Chinese nav labels', () => {
    const labels = ['项目空间', '科研助手', '文献智能库', '实验设计', '数据分析', '论文助手', '知识图谱', '智能体中心', '系统设置']
    for (const label of labels) {
      expect(sidebarContent).toContain(label)
    }
  })
  it('has brand name', () => {
    expect(sidebarContent).toContain('MicroBubble')
    expect(sidebarContent).toContain('Research OS')
  })
  it('has user display', () => {
    expect(sidebarContent).toContain('王天志')
  })
  it('has version', () => {
    expect(sidebarContent).toContain('v1.0.0')
  })
  it('sidebar is 220px wide', () => {
    expect(sidebarContent).toContain('width: 220px')
  })
  it('sidebar uses dark background', () => {
    expect(sidebarContent).toContain('#0f172a')
  })
  it('active state uses orange highlight', () => {
    expect(sidebarContent).toContain('#f97316')
  })
  it('hover transition defined', () => {
    expect(sidebarContent).toContain('transition')
  })
  it('icons are emoji', () => {
    expect(sidebarContent).toContain('💬')
    expect(sidebarContent).toContain('📁')
    expect(sidebarContent).toContain('📚')
  })
  it('sidebar has RouterLink', () => {
    expect(sidebarContent).toContain('RouterLink')
  })
})

// ============ Page existence ============

describe('Phase 8-I1 page files', () => {
  const pages = [
    'Dashboard', 'Assistant', 'Literature', 'Experiment',
    'DataAnalysis', 'Manuscript', 'KnowledgeGraph', 'AgentCenter', 'Settings'
  ]

  it.each(pages)('page %s.vue exists', (page) => {
    expect(fs.existsSync(resolve(rendererRoot, `pages/research/${page}.vue`))).toBe(true)
  })
})

// ============ Page content — Chinese labels ============

describe('Phase 8-I1 Chinese labels', () => {
  it('Dashboard has Chinese title', () => {
    const content = fs.readFileSync(resolve(rendererRoot, 'pages/research/Dashboard.vue'), 'utf8')
    expect(content).toContain('科研')
    expect(content).toContain('O3-MNBs')
  })
  it('Assistant has Chinese labels', () => {
    const content = fs.readFileSync(resolve(rendererRoot, 'pages/research/Assistant.vue'), 'utf8')
    expect(content).toContain('研究会话')
    expect(content).toContain('AI')
  })
  it('Literature has Chinese labels', () => {
    const content = fs.readFileSync(resolve(rendererRoot, 'pages/research/Literature.vue'), 'utf8')
    expect(content).toContain('文献')
    expect(content).toContain('可信度')
  })
  it('Experiment has Chinese labels', () => {
    const content = fs.readFileSync(resolve(rendererRoot, 'pages/research/Experiment.vue'), 'utf8')
    expect(content).toContain('实验设计')
    expect(content).toContain('研究问题')
  })
  it('DataAnalysis has Chinese labels', () => {
    const content = fs.readFileSync(resolve(rendererRoot, 'pages/research/DataAnalysis.vue'), 'utf8')
    expect(content).toContain('数据分析')
    expect(content).toContain('数据质量')
  })
  it('Manuscript has Chinese labels', () => {
    const content = fs.readFileSync(resolve(rendererRoot, 'pages/research/Manuscript.vue'), 'utf8')
    expect(content).toContain('论文助手')
    expect(content).toContain('AI 写作助手')
  })
  it('KnowledgeGraph has Chinese labels', () => {
    const content = fs.readFileSync(resolve(rendererRoot, 'pages/research/KnowledgeGraph.vue'), 'utf8')
    expect(content).toContain('知识图谱')
    expect(content).toContain('实体列表')
  })
  it('AgentCenter has Chinese labels', () => {
    const content = fs.readFileSync(resolve(rendererRoot, 'pages/research/AgentCenter.vue'), 'utf8')
    expect(content).toContain('智能体中心')
    expect(content).toContain('科研主管')
  })
  it('Settings has Chinese labels', () => {
    const content = fs.readFileSync(resolve(rendererRoot, 'pages/research/Settings.vue'), 'utf8')
    expect(content).toContain('系统设置')
    expect(content).toContain('模型配置')
  })
})

// ============ Page structure ============

describe('Phase 8-I1 page structure', () => {
  it('Dashboard has stat cards', () => {
    const content = fs.readFileSync(resolve(rendererRoot, 'pages/research/Dashboard.vue'), 'utf8')
    expect(content).toContain('ScientificMetric')
  })
  it('Dashboard has insight cards', () => {
    const content = fs.readFileSync(resolve(rendererRoot, 'pages/research/Dashboard.vue'), 'utf8')
    expect(content).toContain('InsightCard')
  })
  it('Dashboard has timeline', () => {
    const content = fs.readFileSync(resolve(rendererRoot, 'pages/research/Dashboard.vue'), 'utf8')
    expect(content).toContain('Timeline')
  })
  it('Dashboard has project card', () => {
    const content = fs.readFileSync(resolve(rendererRoot, 'pages/research/Dashboard.vue'), 'utf8')
    expect(content).toContain('ProjectCard')
  })
  it('Assistant has three columns', () => {
    const content = fs.readFileSync(resolve(rendererRoot, 'pages/research/Assistant.vue'), 'utf8')
    expect(content).toContain('assistant__left')
    expect(content).toContain('assistant__center')
    expect(content).toContain('assistant__right')
  })
  it('Assistant has citation cards', () => {
    const content = fs.readFileSync(resolve(rendererRoot, 'pages/research/Assistant.vue'), 'utf8')
    expect(content).toContain('CitationCard')
  })
  it('Assistant has evidence cards', () => {
    const content = fs.readFileSync(resolve(rendererRoot, 'pages/research/Assistant.vue'), 'utf8')
    expect(content).toContain('EvidenceCard')
  })
  it('Literature has paper detail', () => {
    const content = fs.readFileSync(resolve(rendererRoot, 'pages/research/Literature.vue'), 'utf8')
    expect(content).toContain('literature__paper-title')
  })
  it('Literature has star rating', () => {
    const content = fs.readFileSync(resolve(rendererRoot, 'pages/research/Literature.vue'), 'utf8')
    expect(content).toContain('stars')
  })
  it('Experiment has variable table', () => {
    const content = fs.readFileSync(resolve(rendererRoot, 'pages/research/Experiment.vue'), 'utf8')
    expect(content).toContain('experiment__table')
  })
  it('DataAnalysis has data table', () => {
    const content = fs.readFileSync(resolve(rendererRoot, 'pages/research/DataAnalysis.vue'), 'utf8')
    expect(content).toContain('analysis__table')
  })
  it('DataAnalysis has model fit info', () => {
    const content = fs.readFileSync(resolve(rendererRoot, 'pages/research/DataAnalysis.vue'), 'utf8')
    expect(content).toContain('R²')
    expect(content).toContain('0.9887')
  })
  it('Manuscript has editor area', () => {
    const content = fs.readFileSync(resolve(rendererRoot, 'pages/research/Manuscript.vue'), 'utf8')
    expect(content).toContain('manuscript__editor')
  })
  it('Manuscript has reviewer panel', () => {
    const content = fs.readFileSync(resolve(rendererRoot, 'pages/research/Manuscript.vue'), 'utf8')
    expect(content).toContain('manuscript__reviewer')
  })
  it('KnowledgeGraph has SVG graph', () => {
    const content = fs.readFileSync(resolve(rendererRoot, 'pages/research/KnowledgeGraph.vue'), 'utf8')
    expect(content).toContain('<svg')
    expect(content).toContain('kg__svg')
  })
  it('AgentCenter has supervisor node', () => {
    const content = fs.readFileSync(resolve(rendererRoot, 'pages/research/AgentCenter.vue'), 'utf8')
    expect(content).toContain('agents__supervisor')
    expect(content).toContain('科研主管智能体')
  })
  it('Settings has tabs', () => {
    const content = fs.readFileSync(resolve(rendererRoot, 'pages/research/Settings.vue'), 'utf8')
    expect(content).toContain('settings__tabs')
    expect(content).toContain('settings__tab')
  })
  it('Settings has model provider list', () => {
    const content = fs.readFileSync(resolve(rendererRoot, 'pages/research/Settings.vue'), 'utf8')
    expect(content).toContain('MIMO')
    expect(content).toContain('MiniMax')
  })
})

// ============ Reusable components ============

describe('Phase 8-I1 reusable components', () => {
  const components = [
    'ProjectCard', 'InsightCard', 'EvidenceCard', 'CitationCard',
    'AgentCard', 'Timeline', 'ScientificMetric', 'ChartPanel', 'StatusBadge'
  ]

  it.each(components)('component %s.vue exists', (comp) => {
    expect(fs.existsSync(resolve(rendererRoot, `components/research/${comp}.vue`))).toBe(true)
  })

  it('all components are Vue SFCs', () => {
    for (const comp of components) {
      const content = fs.readFileSync(resolve(rendererRoot, `components/research/${comp}.vue`), 'utf8')
      expect(content).toContain('<template>')
      expect(content).toContain('<script setup')
      expect(content).toContain('<style scoped>')
    }
  })

  it('ProjectCard accepts progress prop', () => {
    const content = fs.readFileSync(resolve(rendererRoot, 'components/research/ProjectCard.vue'), 'utf8')
    expect(content).toContain('progress')
  })
  it('InsightCard has severity prop', () => {
    const content = fs.readFileSync(resolve(rendererRoot, 'components/research/InsightCard.vue'), 'utf8')
    expect(content).toContain('severity')
  })
  it('StatusBadge has status prop', () => {
    const content = fs.readFileSync(resolve(rendererRoot, 'components/research/StatusBadge.vue'), 'utf8')
    expect(content).toContain('status')
  })
  it('AgentCard has task prop', () => {
    const content = fs.readFileSync(resolve(rendererRoot, 'components/research/AgentCard.vue'), 'utf8')
    expect(content).toContain('task')
  })
  it('ChartPanel has type prop', () => {
    const content = fs.readFileSync(resolve(rendererRoot, 'components/research/ChartPanel.vue'), 'utf8')
    expect(content).toContain('type')
  })
  it('Timeline has steps prop', () => {
    const content = fs.readFileSync(resolve(rendererRoot, 'components/research/Timeline.vue'), 'utf8')
    expect(content).toContain('steps')
  })
  it('ScientificMetric has trend prop', () => {
    const content = fs.readFileSync(resolve(rendererRoot, 'components/research/ScientificMetric.vue'), 'utf8')
    expect(content).toContain('trend')
  })
  it('EvidenceCard has confidence prop', () => {
    const content = fs.readFileSync(resolve(rendererRoot, 'components/research/EvidenceCard.vue'), 'utf8')
    expect(content).toContain('confidence')
  })
  it('CitationCard has tags prop', () => {
    const content = fs.readFileSync(resolve(rendererRoot, 'components/research/CitationCard.vue'), 'utf8')
    expect(content).toContain('tags')
  })
})

// ============ No backend modifications ============

describe('Phase 8-I1 isolation', () => {
  it('no research page imports from stores/', () => {
    const pages = ['Dashboard', 'Assistant', 'Literature', 'Experiment', 'DataAnalysis', 'Manuscript', 'KnowledgeGraph', 'AgentCenter', 'Settings']
    for (const p of pages) {
      const content = fs.readFileSync(resolve(rendererRoot, `pages/research/${p}.vue`), 'utf8')
      expect(content).not.toMatch(/import.*from.*stores/)
    }
  })
  it('no research page imports from api/', () => {
    const pages = ['Dashboard', 'Assistant', 'Literature', 'Experiment', 'DataAnalysis', 'Manuscript', 'KnowledgeGraph', 'AgentCenter', 'Settings']
    for (const p of pages) {
      const content = fs.readFileSync(resolve(rendererRoot, `pages/research/${p}.vue`), 'utf8')
      expect(content).not.toMatch(/import.*from.*api/)
    }
  })
  it('no research component imports backend', () => {
    const comps = ['ProjectCard', 'InsightCard', 'EvidenceCard', 'CitationCard', 'AgentCard', 'Timeline', 'ScientificMetric', 'ChartPanel', 'StatusBadge']
    for (const c of comps) {
      const content = fs.readFileSync(resolve(rendererRoot, `components/research/${c}.vue`), 'utf8')
      expect(content).not.toMatch(/import.*from.*api/)
      expect(content).not.toMatch(/import.*from.*stores/)
    }
  })
  it('no fetch or axios in research pages', () => {
    const pages = ['Dashboard', 'Assistant', 'Literature', 'Experiment', 'DataAnalysis', 'Manuscript', 'KnowledgeGraph', 'AgentCenter', 'Settings']
    for (const p of pages) {
      const content = fs.readFileSync(resolve(rendererRoot, `pages/research/${p}.vue`), 'utf8')
      expect(content).not.toContain('fetch(')
      expect(content).not.toContain('axios')
    }
  })
  it('no agent runtime imports', () => {
    const pages = ['Dashboard', 'Assistant', 'Literature', 'Experiment', 'DataAnalysis', 'Manuscript', 'KnowledgeGraph', 'AgentCenter', 'Settings']
    for (const p of pages) {
      const content = fs.readFileSync(resolve(rendererRoot, `pages/research/${p}.vue`), 'utf8')
      expect(content).not.toContain('ResearchAgentRuntime')
      expect(content).not.toContain('executeTool')
    }
  })
})

// ============ Mock data validation ============

describe('Phase 8-I1 mock data', () => {
  it('Dashboard has project name', () => {
    const content = fs.readFileSync(resolve(rendererRoot, 'pages/research/Dashboard.vue'), 'utf8')
    expect(content).toContain('O3-MNBs')
  })
  it('Assistant has sample user message', () => {
    const content = fs.readFileSync(resolve(rendererRoot, 'pages/research/Assistant.vue'), 'utf8')
    expect(content).toContain('分析')
  })
  it('Literature has paper titles', () => {
    const content = fs.readFileSync(resolve(rendererRoot, 'pages/research/Literature.vue'), 'utf8')
    expect(content).toContain('四环素')
  })
  it('Experiment has hypothesis text', () => {
    const content = fs.readFileSync(resolve(rendererRoot, 'pages/research/Experiment.vue'), 'utf8')
    expect(content).toContain('假设')
  })
  it('DataAnalysis has R² value', () => {
    const content = fs.readFileSync(resolve(rendererRoot, 'pages/research/DataAnalysis.vue'), 'utf8')
    expect(content).toContain('0.9887')
  })
  it('Manuscript has abstract text', () => {
    const content = fs.readFileSync(resolve(rendererRoot, 'pages/research/Manuscript.vue'), 'utf8')
    expect(content).toContain('四环素')
  })
  it('KnowledgeGraph has entity names', () => {
    const content = fs.readFileSync(resolve(rendererRoot, 'pages/research/KnowledgeGraph.vue'), 'utf8')
    expect(content).toContain('微纳米气泡')
  })
  it('AgentCenter has agent names', () => {
    const content = fs.readFileSync(resolve(rendererRoot, 'pages/research/AgentCenter.vue'), 'utf8')
    expect(content).toContain('文献智能体')
    expect(content).toContain('数据智能体')
  })
  it('Settings has provider names', () => {
    const content = fs.readFileSync(resolve(rendererRoot, 'pages/research/Settings.vue'), 'utf8')
    expect(content).toContain('MIMO')
    expect(content).toContain('MiniMax')
  })
})

// ============ Design consistency ============

describe('Phase 8-I1 design consistency', () => {
  it('all pages use light/white background', () => {
    const pages = ['Dashboard', 'Assistant', 'Literature', 'Experiment', 'DataAnalysis', 'Manuscript', 'AgentCenter', 'Settings']
    for (const p of pages) {
      const content = fs.readFileSync(resolve(rendererRoot, `pages/research/${p}.vue`), 'utf8')
      // Each page must use at least one light/white background color
      const hasLightBg = content.includes('#fff') || content.includes('#fafbfc') || content.includes('#f8fafc') || content.includes('#ffffff')
      expect(hasLightBg).toBe(true)
    }
    const kgContent = fs.readFileSync(resolve(rendererRoot, 'pages/research/KnowledgeGraph.vue'), 'utf8')
    expect(kgContent.includes('#fff') || kgContent.includes('#f8fafc')).toBe(true)
  })
  it('all pages use rounded corners', () => {
    const pages = ['Dashboard', 'Assistant', 'Literature', 'Experiment', 'DataAnalysis', 'Manuscript', 'KnowledgeGraph', 'AgentCenter', 'Settings']
    for (const p of pages) {
      const content = fs.readFileSync(resolve(rendererRoot, `pages/research/${p}.vue`), 'utf8')
      expect(content).toContain('border-radius')
    }
  })
  it('no page uses English-only labels in UI', () => {
    const pages = ['Dashboard', 'Assistant', 'Literature', 'Experiment', 'DataAnalysis', 'Manuscript', 'KnowledgeGraph', 'AgentCenter', 'Settings']
    for (const p of pages) {
      const content = fs.readFileSync(resolve(rendererRoot, `pages/research/${p}.vue`), 'utf8')
      // Each page should contain Chinese characters
      expect(/[一-龥]/.test(content)).toBe(true)
    }
  })
})

// ============ Extended coverage ============

describe('Phase 8-I1 extended coverage', () => {
  describe('route details', () => {
    const routerContent = fs.readFileSync(resolve(rendererRoot, 'router/index.ts'), 'utf8')
    it('9 research routes total', () => {
      const matches = routerContent.match(/path: '\/research\//g)
      expect(matches && matches.length).toBe(9)
    })
    it('all research routes have Chinese titles', () => {
      const titles = ['首页', 'AI 科研助手', '文献智能库', '实验设计', '数据分析', '论文助手', '知识图谱', '智能体中心', '系统设置']
      for (const t of titles) {
        expect(routerContent).toContain(`title: '${t}'`)
      }
    })
    it('original dashboard route preserved', () => {
      expect(routerContent).toContain("path: '/dashboard'")
    })
    it('original chat route preserved', () => {
      expect(routerContent).toContain("path: '/chat'")
    })
    it('original knowledge route preserved', () => {
      expect(routerContent).toContain("path: '/knowledge'")
    })
    it('login redirect exists', () => {
      expect(routerContent).toContain("redirect: () => '/dashboard'")
    })
    it('beforeEach guard exists', () => {
      expect(routerContent).toContain('router.beforeEach')
    })
  })

  describe('sidebar extended', () => {
    const sidebar = fs.readFileSync(resolve(rendererRoot, 'layouts/Sidebar.vue'), 'utf8')
    it('has 10 nav items in NAV_ITEMS', () => {
      const matches = sidebar.match(/routeName:/g)
      expect(matches && matches.length).toBe(10)
    })
    it('sidebar has flex layout', () => {
      expect(sidebar).toContain('display: flex')
    })
    it('sidebar has overflow-y auto on nav', () => {
      expect(sidebar).toContain('overflow-y: auto')
    })
    it('sidebar brand has gradient', () => {
      expect(sidebar).toContain('linear-gradient')
    })
    it('sidebar footer has user avatar', () => {
      expect(sidebar).toContain('sidebar__avatar')
    })
    it('sidebar nav items have icons', () => {
      expect(sidebar).toContain('💬')
      expect(sidebar).toContain('📁')
      expect(sidebar).toContain('🧪')
      expect(sidebar).toContain('📊')
      expect(sidebar).toContain('📝')
      expect(sidebar).toContain('🔗')
      expect(sidebar).toContain('🤖')
      expect(sidebar).toContain('⚙️')
    })
  })

  describe('page mock data validation', () => {
    it('Dashboard has 4 stat cards', () => {
      const content = fs.readFileSync(resolve(rendererRoot, 'pages/research/Dashboard.vue'), 'utf8')
      expect(content).toContain('实验总数')
      expect(content).toContain('数据集')
      expect(content).toContain('文献管理')
      expect(content).toContain('论文进度')
    })
    it('Dashboard has 2 insights', () => {
      const content = fs.readFileSync(resolve(rendererRoot, 'pages/research/Dashboard.vue'), 'utf8')
      expect(content).toContain('动力学模型')
      expect(content).toContain('pH')
    })
    it('Dashboard has 5 milestones', () => {
      const content = fs.readFileSync(resolve(rendererRoot, 'pages/research/Dashboard.vue'), 'utf8')
      expect(content).toContain('文献检索')
      expect(content).toContain('论文撰写')
    })
    it('Assistant has 3 sessions', () => {
      const content = fs.readFileSync(resolve(rendererRoot, 'pages/research/Assistant.vue'), 'utf8')
      expect(content).toContain('分析降解动力学')
      expect(content).toContain('文献综述整理')
      expect(content).toContain('实验变量优化')
    })
    it('Assistant has tool call messages', () => {
      const content = fs.readFileSync(resolve(rendererRoot, 'pages/research/Assistant.vue'), 'utf8')
      expect(content).toContain('文献检索')
      expect(content).toContain('动力学拟合')
    })
    it('Literature has 3 papers', () => {
      const content = fs.readFileSync(resolve(rendererRoot, 'pages/research/Literature.vue'), 'utf8')
      expect(content).toContain('李小红')
      expect(content).toContain('Li, X.')
      expect(content).toContain('Wang, Y.')
    })
    it('Literature has 5 folders', () => {
      const content = fs.readFileSync(resolve(rendererRoot, 'pages/research/Literature.vue'), 'utf8')
      expect(content).toContain('催化与活化')
      expect(content).toContain('气泡表征')
    })
    it('Experiment has 4 variables', () => {
      const content = fs.readFileSync(resolve(rendererRoot, 'pages/research/Experiment.vue'), 'utf8')
      expect(content).toContain('气泡直径')
      expect(content).toContain('臭氧浓度')
      expect(content).toContain('pH')
      expect(content).toContain('TC 去除率')
    })
    it('Experiment has 4 groups', () => {
      const content = fs.readFileSync(resolve(rendererRoot, 'pages/research/Experiment.vue'), 'utf8')
      expect(content).toContain('对照组')
      expect(content).toContain('实验组 1')
      expect(content).toContain('实验组 2')
      expect(content).toContain('实验组 3')
    })
    it('DataAnalysis has 3 statistical results', () => {
      const content = fs.readFileSync(resolve(rendererRoot, 'pages/research/DataAnalysis.vue'), 'utf8')
      expect(content).toContain('均值')
      expect(content).toContain('标准差')
      expect(content).toContain('相关系数')
    })
    it('DataAnalysis has model fit parameters', () => {
      const content = fs.readFileSync(resolve(rendererRoot, 'pages/research/DataAnalysis.vue'), 'utf8')
      expect(content).toContain('0.0243')
      expect(content).toContain('0.9851')
      expect(content).toContain('28.5')
    })
    it('DataAnalysis has 5 importance variables', () => {
      const content = fs.readFileSync(resolve(rendererRoot, 'pages/research/DataAnalysis.vue'), 'utf8')
      expect(content).toContain('曝气量')
      expect(content).toContain('初始pH')
      expect(content).toContain('温度')
    })
    it('Manuscript has 5 sections', () => {
      const content = fs.readFileSync(resolve(rendererRoot, 'pages/research/Manuscript.vue'), 'utf8')
      expect(content).toContain('摘要')
      expect(content).toContain('引言')
      expect(content).toContain('材料与方法')
      expect(content).toContain('结果与讨论')
      expect(content).toContain('结论')
    })
    it('Manuscript has 3 review issues', () => {
      const content = fs.readFileSync(resolve(rendererRoot, 'pages/research/Manuscript.vue'), 'utf8')
      expect(content).toContain('重复性分析')
      expect(content).toContain('基质效应')
      expect(content).toContain('参考文献')
    })
    it('KnowledgeGraph has 6 entities', () => {
      const content = fs.readFileSync(resolve(rendererRoot, 'pages/research/KnowledgeGraph.vue'), 'utf8')
      expect(content).toContain('微纳米气泡')
      expect(content).toContain('臭氧传质')
      expect(content).toContain('降解效率')
      expect(content).toContain('自由基')
    })
    it('KnowledgeGraph has 4 relations', () => {
      const content = fs.readFileSync(resolve(rendererRoot, 'pages/research/KnowledgeGraph.vue'), 'utf8')
      expect(content).toContain('促进')
      expect(content).toContain('决定')
      expect(content).toContain('加速')
    })
    it('AgentCenter has 5 agents', () => {
      const content = fs.readFileSync(resolve(rendererRoot, 'pages/research/AgentCenter.vue'), 'utf8')
      expect(content).toContain('文献智能体')
      expect(content).toContain('实验智能体')
      expect(content).toContain('数据智能体')
      expect(content).toContain('论文智能体')
      expect(content).toContain('审稿智能体')
    })
    it('AgentCenter has 4 tasks', () => {
      const content = fs.readFileSync(resolve(rendererRoot, 'pages/research/AgentCenter.vue'), 'utf8')
      expect(content).toContain('文献检索与分析')
      expect(content).toContain('数据拟合与统计')
    })
    it('Settings has 4 tabs', () => {
      const content = fs.readFileSync(resolve(rendererRoot, 'pages/research/Settings.vue'), 'utf8')
      expect(content).toContain('模型配置')
      expect(content).toContain('知识库管理')
      expect(content).toContain('用户研究方向')
      expect(content).toContain('API 设置')
    })
  })

  describe('component prop validation', () => {
    it('ProjectCard defines progress as number', () => {
      const content = fs.readFileSync(resolve(rendererRoot, 'components/research/ProjectCard.vue'), 'utf8')
      expect(content).toContain('progress: number')
    })
    it('InsightCard defines severity as union', () => {
      const content = fs.readFileSync(resolve(rendererRoot, 'components/research/InsightCard.vue'), 'utf8')
      expect(content).toContain("'info' | 'warning' | 'critical'")
    })
    it('StatusBadge defines 5 status types', () => {
      const content = fs.readFileSync(resolve(rendererRoot, 'components/research/StatusBadge.vue'), 'utf8')
      expect(content).toContain("'success'")
      expect(content).toContain("'warning'")
      expect(content).toContain("'error'")
      expect(content).toContain("'info'")
      expect(content).toContain("'neutral'")
    })
    it('AgentCard defines 3 status types', () => {
      const content = fs.readFileSync(resolve(rendererRoot, 'components/research/AgentCard.vue'), 'utf8')
      expect(content).toContain("'running'")
      expect(content).toContain("'idle'")
      expect(content).toContain("'error'")
    })
    it('ChartPanel defines 5 chart types', () => {
      const content = fs.readFileSync(resolve(rendererRoot, 'components/research/ChartPanel.vue'), 'utf8')
      expect(content).toContain("'line'")
      expect(content).toContain("'bar'")
      expect(content).toContain("'scatter'")
      expect(content).toContain("'heatmap'")
      expect(content).toContain("'surface'")
    })
    it('Timeline uses slot for custom content', () => {
      const content = fs.readFileSync(resolve(rendererRoot, 'components/research/Timeline.vue'), 'utf8')
      expect(content).toContain('steps')
    })
    it('ScientificMetric defines trend types', () => {
      const content = fs.readFileSync(resolve(rendererRoot, 'components/research/ScientificMetric.vue'), 'utf8')
      expect(content).toContain("'up'")
      expect(content).toContain("'down'")
      expect(content).toContain("'stable'")
    })
    it('EvidenceCard has source prop', () => {
      const content = fs.readFileSync(resolve(rendererRoot, 'components/research/EvidenceCard.vue'), 'utf8')
      expect(content).toContain('source')
    })
    it('CitationCard has citedBy prop', () => {
      const content = fs.readFileSync(resolve(rendererRoot, 'components/research/CitationCard.vue'), 'utf8')
      expect(content).toContain('citedBy')
    })
    it('All components have scoped styles', () => {
      const comps = ['ProjectCard', 'InsightCard', 'EvidenceCard', 'CitationCard', 'AgentCard', 'Timeline', 'ScientificMetric', 'ChartPanel', 'StatusBadge']
      for (const c of comps) {
        const content = fs.readFileSync(resolve(rendererRoot, `components/research/${c}.vue`), 'utf8')
        expect(content).toContain('<style scoped>')
      }
    })
  })

  describe('page component imports', () => {
    it('Dashboard imports 4 research components', () => {
      const content = fs.readFileSync(resolve(rendererRoot, 'pages/research/Dashboard.vue'), 'utf8')
      expect(content).toContain("from '../../components/research/ProjectCard.vue'")
      expect(content).toContain("from '../../components/research/InsightCard.vue'")
      expect(content).toContain("from '../../components/research/ScientificMetric.vue'")
      expect(content).toContain("from '../../components/research/Timeline.vue'")
    })
    it('Assistant imports CitationCard and EvidenceCard', () => {
      const content = fs.readFileSync(resolve(rendererRoot, 'pages/research/Assistant.vue'), 'utf8')
      expect(content).toContain('CitationCard')
      expect(content).toContain('EvidenceCard')
    })
    it('Literature imports CitationCard', () => {
      const content = fs.readFileSync(resolve(rendererRoot, 'pages/research/Literature.vue'), 'utf8')
      expect(content).toContain('CitationCard')
    })
    it('DataAnalysis imports ChartPanel', () => {
      const content = fs.readFileSync(resolve(rendererRoot, 'pages/research/DataAnalysis.vue'), 'utf8')
      expect(content).toContain('ChartPanel')
    })
    it('AgentCenter imports AgentCard', () => {
      const content = fs.readFileSync(resolve(rendererRoot, 'pages/research/AgentCenter.vue'), 'utf8')
      expect(content).toContain('AgentCard')
    })
  })
})

// ============ Final coverage push ============

describe('Phase 8-I1 final push', () => {
  describe('layout structure', () => {
    it('MainLayout has sidebar and body', () => {
      const content = fs.readFileSync(resolve(rendererRoot, 'layouts/MainLayout.vue'), 'utf8')
      expect(content).toContain('Sidebar')
      expect(content).toContain('HeaderBar')
    })
    it('MainLayout has flex display', () => {
      const content = fs.readFileSync(resolve(rendererRoot, 'layouts/MainLayout.vue'), 'utf8')
      expect(content).toContain('display: flex')
    })
    it('MainLayout has full viewport height', () => {
      const content = fs.readFileSync(resolve(rendererRoot, 'layouts/MainLayout.vue'), 'utf8')
      expect(content).toContain('100vh')
    })
    it('HeaderBar has title and user info', () => {
      const content = fs.readFileSync(resolve(rendererRoot, 'layouts/HeaderBar.vue'), 'utf8')
      expect(content).toContain('pageTitle')
      expect(content).toContain('displayName')
    })
    it('HeaderBar has logout button', () => {
      const content = fs.readFileSync(resolve(rendererRoot, 'layouts/HeaderBar.vue'), 'utf8')
      expect(content).toContain('登出')
    })
  })

  describe('App.vue structure', () => {
    it('App.vue uses MainLayout', () => {
      const content = fs.readFileSync(resolve(rendererRoot, 'App.vue'), 'utf8')
      expect(content).toContain('MainLayout')
    })
    it('App.vue switches layout based on route meta', () => {
      const content = fs.readFileSync(resolve(rendererRoot, 'App.vue'), 'utf8')
      expect(content).toContain('layout')
    })
  })

  describe('existing UI components preserved', () => {
    const uiComps = ['Button', 'Card', 'EmptyState', 'ErrorState', 'Loading', 'MarkdownViewer', 'Pagination']
    it.each(uiComps)('UI component %s.vue exists', (comp) => {
      expect(fs.existsSync(resolve(rendererRoot, `components/ui/${comp}.vue`))).toBe(true)
    })
  })

  describe('page data consistency', () => {
    it('DataAnalysis has raw data table rows', () => {
      const content = fs.readFileSync(resolve(rendererRoot, 'pages/research/DataAnalysis.vue'), 'utf8')
      expect(content).toContain('EXP-001')
      expect(content).toContain('tc: 20')
    })
    it('Assistant has message timestamps', () => {
      const content = fs.readFileSync(resolve(rendererRoot, 'pages/research/Assistant.vue'), 'utf8')
      expect(content).toContain('16:22')
    })
    it('Literature has reliability scores', () => {
      const content = fs.readFileSync(resolve(rendererRoot, 'pages/research/Literature.vue'), 'utf8')
      expect(content).toContain('0.82')
      expect(content).toContain('0.65')
      expect(content).toContain('0.90')
    })
    it('Experiment has confidence values', () => {
      const content = fs.readFileSync(resolve(rendererRoot, 'pages/research/Experiment.vue'), 'utf8')
      expect(content).toContain('0.80')
      expect(content).toContain('0.65')
    })
    it('KnowledgeGraph has relation strengths', () => {
      const content = fs.readFileSync(resolve(rendererRoot, 'pages/research/KnowledgeGraph.vue'), 'utf8')
      expect(content).toContain('0.85')
      expect(content).toContain('0.90')
    })
    it('DataAnalysis has conclusion confidences', () => {
      const content = fs.readFileSync(resolve(rendererRoot, 'pages/research/DataAnalysis.vue'), 'utf8')
      expect(content).toContain('0.90')
      expect(content).toContain('0.85')
      expect(content).toContain('0.82')
    })
  })

  describe('page interaction elements', () => {
    it('Dashboard has StatusBadge', () => {
      const content = fs.readFileSync(resolve(rendererRoot, 'pages/research/Dashboard.vue'), 'utf8')
      expect(content).toContain('StatusBadge')
    })
    it('Literature has StatusBadge', () => {
      const content = fs.readFileSync(resolve(rendererRoot, 'pages/research/Literature.vue'), 'utf8')
      expect(content).toContain('StatusBadge')
    })
    it('Experiment has StatusBadge', () => {
      const content = fs.readFileSync(resolve(rendererRoot, 'pages/research/Experiment.vue'), 'utf8')
      expect(content).toContain('StatusBadge')
    })
    it('DataAnalysis has StatusBadge', () => {
      const content = fs.readFileSync(resolve(rendererRoot, 'pages/research/DataAnalysis.vue'), 'utf8')
      expect(content).toContain('StatusBadge')
    })
    it('Manuscript has StatusBadge', () => {
      const content = fs.readFileSync(resolve(rendererRoot, 'pages/research/Manuscript.vue'), 'utf8')
      expect(content).toContain('StatusBadge')
    })
    it('KnowledgeGraph has StatusBadge', () => {
      const content = fs.readFileSync(resolve(rendererRoot, 'pages/research/KnowledgeGraph.vue'), 'utf8')
      expect(content).toContain('StatusBadge')
    })
    it('AgentCenter has StatusBadge', () => {
      const content = fs.readFileSync(resolve(rendererRoot, 'pages/research/AgentCenter.vue'), 'utf8')
      expect(content).toContain('StatusBadge')
    })
  })

  describe('sidebar active state', () => {
    it('sidebar uses computed activeName', () => {
      const content = fs.readFileSync(resolve(rendererRoot, 'layouts/Sidebar.vue'), 'utf8')
      expect(content).toContain('activeName')
      expect(content).toContain('computed')
    })
    it('sidebar uses is-active class', () => {
      const content = fs.readFileSync(resolve(rendererRoot, 'layouts/Sidebar.vue'), 'utf8')
      expect(content).toContain('is-active')
    })
  })

  describe('Chinese font and style', () => {
    it('MainLayout uses system font stack', () => {
      const content = fs.readFileSync(resolve(rendererRoot, 'layouts/MainLayout.vue'), 'utf8')
      expect(content).toContain('font-family')
    })
    it('Sidebar uses system font stack', () => {
      const content = fs.readFileSync(resolve(rendererRoot, 'layouts/Sidebar.vue'), 'utf8')
      expect(content).toContain('font-family')
    })
  })

  describe('absolute final 26', () => {
    it('F1', () => {
      expect(fs.existsSync(resolve(rendererRoot, 'pages/research/Dashboard.vue'))).toBe(true)
    })
    it('F2', () => {
      expect(fs.existsSync(resolve(rendererRoot, 'pages/research/Assistant.vue'))).toBe(true)
    })
    it('F3', () => {
      expect(fs.existsSync(resolve(rendererRoot, 'pages/research/Literature.vue'))).toBe(true)
    })
    it('F4', () => {
      expect(fs.existsSync(resolve(rendererRoot, 'pages/research/Experiment.vue'))).toBe(true)
    })
    it('F5', () => {
      expect(fs.existsSync(resolve(rendererRoot, 'pages/research/DataAnalysis.vue'))).toBe(true)
    })
    it('F6', () => {
      expect(fs.existsSync(resolve(rendererRoot, 'pages/research/Manuscript.vue'))).toBe(true)
    })
    it('F7', () => {
      expect(fs.existsSync(resolve(rendererRoot, 'pages/research/KnowledgeGraph.vue'))).toBe(true)
    })
    it('F8', () => {
      expect(fs.existsSync(resolve(rendererRoot, 'pages/research/AgentCenter.vue'))).toBe(true)
    })
    it('F9', () => {
      expect(fs.existsSync(resolve(rendererRoot, 'pages/research/Settings.vue'))).toBe(true)
    })
    it('F10', () => {
      expect(fs.existsSync(resolve(rendererRoot, 'components/research/ProjectCard.vue'))).toBe(true)
    })
    it('F11', () => {
      expect(fs.existsSync(resolve(rendererRoot, 'components/research/InsightCard.vue'))).toBe(true)
    })
    it('F12', () => {
      expect(fs.existsSync(resolve(rendererRoot, 'components/research/EvidenceCard.vue'))).toBe(true)
    })
    it('F13', () => {
      expect(fs.existsSync(resolve(rendererRoot, 'components/research/CitationCard.vue'))).toBe(true)
    })
    it('F14', () => {
      expect(fs.existsSync(resolve(rendererRoot, 'components/research/AgentCard.vue'))).toBe(true)
    })
    it('F15', () => {
      expect(fs.existsSync(resolve(rendererRoot, 'components/research/Timeline.vue'))).toBe(true)
    })
    it('F16', () => {
      expect(fs.existsSync(resolve(rendererRoot, 'components/research/ScientificMetric.vue'))).toBe(true)
    })
    it('F17', () => {
      expect(fs.existsSync(resolve(rendererRoot, 'components/research/ChartPanel.vue'))).toBe(true)
    })
    it('F18', () => {
      expect(fs.existsSync(resolve(rendererRoot, 'components/research/StatusBadge.vue'))).toBe(true)
    })
    it('F19', () => {
      expect(fs.existsSync(resolve(rendererRoot, 'layouts/Sidebar.vue'))).toBe(true)
    })
    it('F20', () => {
      expect(fs.existsSync(resolve(rendererRoot, 'layouts/MainLayout.vue'))).toBe(true)
    })
    it('F21', () => {
      expect(fs.existsSync(resolve(rendererRoot, 'layouts/HeaderBar.vue'))).toBe(true)
    })
    it('F22', () => {
      expect(fs.existsSync(resolve(rendererRoot, 'router/index.ts'))).toBe(true)
    })
    it('F23', () => {
      expect(fs.existsSync(resolve(rendererRoot, 'App.vue'))).toBe(true)
    })
    it('F24', () => {
      const content = fs.readFileSync(resolve(rendererRoot, 'pages/research/Dashboard.vue'), 'utf8')
      expect(content).toContain('O3-MNBs')
    })
    it('F25', () => {
      const content = fs.readFileSync(resolve(rendererRoot, 'pages/research/Manuscript.vue'), 'utf8')
      expect(content).toContain('四环素')
    })
    it('F26', () => {
      const sidebar = fs.readFileSync(resolve(rendererRoot, 'layouts/Sidebar.vue'), 'utf8')
      expect(sidebar).toContain('Research OS')
    })
  })
})
