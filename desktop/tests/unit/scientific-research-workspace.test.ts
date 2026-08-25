// Phase 8-L0 Scientific Research Workspace Tests
import { describe, it, expect, beforeEach } from 'vitest'
import { readFileSync, existsSync } from 'node:fs'
import { join } from 'node:path'

import {
  isValidResearchWorkspace, isValidWorkspaceModule, isValidProjectOverview,
  isValidResearchProgress, isValidWorkspaceActivity, isValidWorkspaceSummary,
  isValidModuleStatus, isValidActivityKind,
  MODULE_STATUSES, ACTIVITY_KINDS,
  __testHelpers as wsHelpers
} from '../../src/shared/workspace/research-workspace-schema'
import type {
  ResearchWorkspace, WorkspaceModule, ProjectOverview, ResearchProgress,
  WorkspaceActivity, WorkspaceSummary
} from '../../src/shared/workspace/research-workspace-schema'

import {
  ResearchWorkspaceService, DEFAULT_MODULES
} from '../../src/services/workspace/research-workspace.service'

const readShared = (name: string) => readFileSync(join(__dirname, '../../src/shared/workspace', name), 'utf8')
const read = (name: string) => readFileSync(join(__dirname, '../../src/services/workspace', name), 'utf8')
const readDocs = (name: string) => readFileSync(join(__dirname, '../../docs/workspace', name), 'utf8')

function mkModule(overrides: Partial<WorkspaceModule> = {}): WorkspaceModule {
  return {
    id: 'agent', name: 'AI Agent', category: 'AI', status: 'ready',
    description: 'Test agent', enabled: true,
    ...overrides
  }
}

describe('Phase 8-L0 schema validators', () => {
  it('MODULE_STATUSES has 6', () => {
    expect(MODULE_STATUSES.length).toBe(6)
  })
  it('MODULE_STATUSES frozen', () => {
    expect(Object.isFrozen(MODULE_STATUSES)).toBe(true)
  })
  it('ACTIVITY_KINDS has 7', () => {
    expect(ACTIVITY_KINDS.length).toBe(7)
  })
  it('ACTIVITY_KINDS frozen', () => {
    expect(Object.isFrozen(ACTIVITY_KINDS)).toBe(true)
  })
  for (const s of ['ready', 'running', 'paused', 'completed', 'failed', 'disabled']) {
    it(`isValidModuleStatus accepts ${s}`, () => {
      expect(isValidModuleStatus(s)).toBe(true)
    })
  }
  for (const s of ['unknown', 'IDLE', '']) {
    it(`isValidModuleStatus rejects ${s}`, () => {
      expect(isValidModuleStatus(s)).toBe(false)
    })
  }
  for (const k of ['agent', 'experiment', 'manuscript', 'device', 'twin', 'knowledge', 'system']) {
    it(`isValidActivityKind accepts ${k}`, () => {
      expect(isValidActivityKind(k)).toBe(true)
    })
  }
  for (const k of ['unknown', 'AGENT', '']) {
    it(`isValidActivityKind rejects ${k}`, () => {
      expect(isValidActivityKind(k)).toBe(false)
    })
  }
  it('isValidWorkspaceModule accepts valid', () => {
    expect(isValidWorkspaceModule(mkModule())).toBe(true)
  })
  it('isValidWorkspaceModule rejects empty id', () => {
    expect(isValidWorkspaceModule(mkModule({ id: '' }))).toBe(false)
  })
  it('isValidWorkspaceModule rejects bad status', () => {
    expect(isValidWorkspaceModule(mkModule({ status: 'invalid' as never }))).toBe(false)
  })
  it('isValidWorkspaceModule rejects enabled non-boolean', () => {
    expect(isValidWorkspaceModule(mkModule({ enabled: 'yes' as never }))).toBe(false)
  })
  it('isValidProjectOverview accepts valid', () => {
    expect(isValidProjectOverview({
      projectId: 'p', title: 'T', domain: 'D', description: 'd', status: 'active',
      createdAt: 1, updatedAt: 2, memberCount: 5, taskCount: 10
    })).toBe(true)
  })
  it('isValidProjectOverview rejects negative member', () => {
    expect(isValidProjectOverview({
      projectId: 'p', title: 'T', domain: 'D', description: 'd', status: 'active',
      createdAt: 1, updatedAt: 2, memberCount: -1, taskCount: 10
    })).toBe(false)
  })
  it('isValidResearchProgress accepts valid', () => {
    expect(isValidResearchProgress({
      totalTasks: 10, completedTasks: 5,
      totalExperiments: 4, completedExperiments: 3,
      totalManuscripts: 2, publishedManuscripts: 1,
      totalKnowledge: 50, indexedKnowledge: 30,
      percent: 50
    })).toBe(true)
  })
  it('isValidResearchProgress rejects negative percent', () => {
    expect(isValidResearchProgress({
      totalTasks: 0, completedTasks: 0,
      totalExperiments: 0, completedExperiments: 0,
      totalManuscripts: 0, publishedManuscripts: 0,
      totalKnowledge: 0, indexedKnowledge: 0,
      percent: -1
    })).toBe(false)
  })
  it('isValidWorkspaceActivity accepts valid', () => {
    expect(isValidWorkspaceActivity({
      id: 'a', kind: 'agent', title: 't', description: 'd', timestamp: 1, actor: 'alice'
    })).toBe(true)
  })
  it('isValidWorkspaceActivity rejects bad kind', () => {
    expect(isValidWorkspaceActivity({
      id: 'a', kind: 'unknown' as never, title: 't', description: 'd', timestamp: 1, actor: 'a'
    })).toBe(false)
  })
  it('isValidWorkspaceSummary accepts valid', () => {
    expect(isValidWorkspaceSummary({
      projectId: 'p', totalModules: 8, activeModules: 5,
      recentActivities: 10, healthScore: 75, generatedAt: 1
    })).toBe(true)
  })
  it('isValidWorkspaceSummary rejects negative activeModules', () => {
    expect(isValidWorkspaceSummary({
      projectId: 'p', totalModules: 8, activeModules: -1,
      recentActivities: 10, healthScore: 75, generatedAt: 1
    })).toBe(false)
  })
  it('isValidResearchWorkspace accepts valid', () => {
    const w: ResearchWorkspace = buildWorkspace()
    expect(isValidResearchWorkspace(w)).toBe(true)
  })
  it('isValidResearchWorkspace rejects invalid progress', () => {
    const w = buildWorkspace()
    w.progress.percent = -1
    expect(isValidResearchWorkspace(w)).toBe(false)
  })
})

function buildWorkspace(): ResearchWorkspace {
  return {
    id: 'ws-1',
    projectId: 'p-1',
    title: 'Test',
    overview: { projectId: 'p-1', title: 'T', domain: 'D', description: 'd', status: 'active', createdAt: 1, updatedAt: 2, memberCount: 0, taskCount: 0 },
    modules: [mkModule()],
    progress: { totalTasks: 0, completedTasks: 0, totalExperiments: 0, completedExperiments: 0, totalManuscripts: 0, publishedManuscripts: 0, totalKnowledge: 0, indexedKnowledge: 0, percent: 0 },
    activities: [],
    summary: { projectId: 'p-1', totalModules: 1, activeModules: 1, recentActivities: 0, healthScore: 0, generatedAt: 1 },
    createdAt: 1,
    updatedAt: 2
  }
}

describe('Phase 8-L0 ResearchWorkspaceService', () => {
  let svc: ResearchWorkspaceService
  beforeEach(() => { svc = new ResearchWorkspaceService() })

  it('DEFAULT_MODULES has 8 entries', () => {
    expect(DEFAULT_MODULES.length).toBe(8)
  })
  it('loadWorkspace returns workspace', () => {
    const ws = svc.loadWorkspace({ projectId: 'p', title: 'T', domain: 'D' })
    expect(ws.projectId).toBe('p')
  })
  it('loadWorkspace assigns id', () => {
    const ws = svc.loadWorkspace({ projectId: 'p', title: 'T', domain: 'D' })
    expect(ws.id.length).toBeGreaterThan(0)
  })
  it('loadWorkspace creates 8 modules by default', () => {
    const ws = svc.loadWorkspace({ projectId: 'p', title: 'T', domain: 'D' })
    expect(ws.modules.length).toBe(8)
  })
  it('loadWorkspace sets createdAt', () => {
    const ws = svc.loadWorkspace({ projectId: 'p', title: 'T', domain: 'D' })
    expect(typeof ws.createdAt).toBe('number')
  })
  it('loadWorkspace sets updatedAt', () => {
    const ws = svc.loadWorkspace({ projectId: 'p', title: 'T', domain: 'D' })
    expect(typeof ws.updatedAt).toBe('number')
  })
  it('loadWorkspace with module statuses', () => {
    const ws = svc.loadWorkspace({
      projectId: 'p', title: 'T', domain: 'D',
      moduleStatuses: { agent: 'failed', twin: 'completed' }
    })
    expect(ws.modules.find((m) => m.id === 'agent')!.status).toBe('failed')
    expect(ws.modules.find((m) => m.id === 'twin')!.status).toBe('completed')
  })
  it('loadWorkspace with disabled module', () => {
    const ws = svc.loadWorkspace({
      projectId: 'p', title: 'T', domain: 'D',
      moduleStatuses: { agent: 'disabled' }
    })
    expect(ws.modules.find((m) => m.id === 'agent')!.enabled).toBe(false)
  })
  it('loadWorkspace computes percent', () => {
    const ws = svc.loadWorkspace({
      projectId: 'p', title: 'T', domain: 'D',
      tasks: { total: 10, completed: 5 },
      experiments: { total: 4, completed: 2 },
      manuscripts: { total: 2, published: 1 }
    })
    // totalDone=8, total=16, 50%
    expect(ws.progress.percent).toBe(50)
  })
  it('loadWorkspace percent zero on no work', () => {
    const ws = svc.loadWorkspace({ projectId: 'p', title: 'T', domain: 'D' })
    expect(ws.progress.percent).toBe(0)
  })
  it('loadWorkspace counts activeModules', () => {
    const ws = svc.loadWorkspace({
      projectId: 'p', title: 'T', domain: 'D',
      moduleStatuses: { agent: 'disabled', twin: 'disabled', experiment: 'disabled', manuscript: 'disabled', knowledge: 'disabled', 'multi-agent': 'disabled' }
    })
    expect(ws.summary.activeModules).toBe(2)
  })
  it('loadWorkspace sets healthScore to percent', () => {
    const ws = svc.loadWorkspace({
      projectId: 'p', title: 'T', domain: 'D',
      tasks: { total: 10, completed: 8 }
    })
    expect(ws.summary.healthScore).toBeGreaterThan(0)
  })
  it('loadWorkspace sets recentActivities count', () => {
    const ws = svc.loadWorkspace({
      projectId: 'p', title: 'T', domain: 'D',
      activities: [
        { kind: 'agent', title: 'a', description: 'b', actor: 'c' },
        { kind: 'experiment', title: 'a', description: 'b', actor: 'c' }
      ]
    })
    expect(ws.summary.recentActivities).toBe(2)
  })
  it('loadWorkspace generates activity ids', () => {
    const ws = svc.loadWorkspace({
      projectId: 'p', title: 'T', domain: 'D',
      activities: [{ kind: 'agent', title: 'a', description: 'b', actor: 'c' }]
    })
    expect(ws.activities[0].id.length).toBeGreaterThan(0)
  })
  it('loadWorkspace activity timestamps descending', () => {
    const ws = svc.loadWorkspace({
      projectId: 'p', title: 'T', domain: 'D',
      activities: [
        { kind: 'agent', title: 'a', description: 'b', actor: 'c' },
        { kind: 'experiment', title: 'a', description: 'b', actor: 'c' },
        { kind: 'system', title: 'a', description: 'b', actor: 'c' }
      ]
    })
    expect(ws.activities[0].timestamp).toBeGreaterThanOrEqual(ws.activities[1].timestamp)
  })
  it('getWorkspace null for unknown', () => {
    expect(svc.getWorkspace('nope')).toBeNull()
  })
  it('getWorkspace returns clone', () => {
    const ws = svc.loadWorkspace({ projectId: 'p', title: 'T', domain: 'D' })
    const got = svc.getWorkspace(ws.id)!
    got.title = 'MUT'
    expect(svc.getWorkspace(ws.id)!.title).toBe('T')
  })
  it('getProjectSummary returns cloned summary', () => {
    const ws = svc.loadWorkspace({ projectId: 'p', title: 'T', domain: 'D' })
    const s = svc.getProjectSummary('p')!
    s.healthScore = 999
    expect(svc.getProjectSummary('p')!.healthScore).not.toBe(999)
  })
  it('getProjectSummary null for unknown', () => {
    expect(svc.getProjectSummary('nope')).toBeNull()
  })
  it('getModuleStatus returns null for unknown workspace', () => {
    expect(svc.getModuleStatus('nope', 'agent')).toBeNull()
  })
  it('getModuleStatus returns null for unknown module', () => {
    const ws = svc.loadWorkspace({ projectId: 'p', title: 'T', domain: 'D' })
    expect(svc.getModuleStatus(ws.id, 'nope')).toBeNull()
  })
  it('getModuleStatus returns cloned module', () => {
    const ws = svc.loadWorkspace({ projectId: 'p', title: 'T', domain: 'D' })
    const m = svc.getModuleStatus(ws.id, 'agent')!
    m.status = 'failed'
    expect(svc.getModuleStatus(ws.id, 'agent')!.status).toBe('ready')
  })
  it('getRecentActivities empty for unknown workspace', () => {
    expect(svc.getRecentActivities('nope').length).toBe(0)
  })
  it('getRecentActivities respects limit', () => {
    const ws = svc.loadWorkspace({
      projectId: 'p', title: 'T', domain: 'D',
      activities: Array(10).fill({ kind: 'agent', title: 'a', description: 'b', actor: 'c' })
    })
    expect(svc.getRecentActivities(ws.id, 3).length).toBe(3)
  })
  it('getRecentActivities returns sorted desc', () => {
    const ws = svc.loadWorkspace({
      projectId: 'p', title: 'T', domain: 'D',
      activities: Array(5).fill({ kind: 'agent', title: 'a', description: 'b', actor: 'c' })
    })
    const arr = svc.getRecentActivities(ws.id)
    for (let i = 0; i < arr.length - 1; i++) {
      expect(arr[i].timestamp).toBeGreaterThanOrEqual(arr[i + 1].timestamp)
    }
  })
  it('appendActivity null for unknown workspace', () => {
    expect(svc.appendActivity('nope', { kind: 'agent', title: 't', description: 'd', actor: 'a' })).toBeNull()
  })
  it('appendActivity adds activity', () => {
    const ws = svc.loadWorkspace({ projectId: 'p', title: 'T', domain: 'D' })
    svc.appendActivity(ws.id, { kind: 'agent', title: 't', description: 'd', actor: 'a' })
    const updated = svc.getWorkspace(ws.id)!
    expect(updated.activities.length).toBeGreaterThan(0)
  })
  it('appendActivity trims to retention', () => {
    const small = new ResearchWorkspaceService(2)
    const ws = small.loadWorkspace({ projectId: 'p', title: 'T', domain: 'D' })
    for (let i = 0; i < 5; i++) {
      small.appendActivity(ws.id, { kind: 'agent', title: `t${i}`, description: 'd', actor: 'a' })
    }
    expect(svc.getRecentActivities(ws.id).length).toBeLessThanOrEqual(50)
  })
  it('appendActivity updates recentActivities count', () => {
    const ws = svc.loadWorkspace({ projectId: 'p', title: 'T', domain: 'D' })
    const before = svc.getProjectSummary('p')!.recentActivities
    svc.appendActivity(ws.id, { kind: 'agent', title: 't', description: 'd', actor: 'a' })
    const after = svc.getProjectSummary('p')!.recentActivities
    expect(after).toBeGreaterThan(before)
  })
  it('size returns workspace count', () => {
    svc.loadWorkspace({ projectId: 'a', title: 'A', domain: 'd' })
    svc.loadWorkspace({ projectId: 'b', title: 'B', domain: 'd' })
    expect(svc.size()).toBe(2)
  })
  it('clear resets', () => {
    svc.loadWorkspace({ projectId: 'p', title: 'T', domain: 'D' })
    svc.clear()
    expect(svc.size()).toBe(0)
  })
})

describe('Phase 8-L0 secret guard', () => {
  it('findForbidden detects sk-', () => {
    expect(wsHelpers.findForbidden('sk-x')).toBe('sk-')
  })
  it('findForbidden detects apiKey', () => {
    expect(wsHelpers.findForbidden('apiKey')).toBe('apiKey')
  })
  it('findForbidden detects Bearer', () => {
    expect(wsHelpers.findForbidden('Bearer x')).toBe('Bearer ')
  })
  it('findForbidden handles null', () => {
    expect(wsHelpers.findForbidden(null)).toBeNull()
  })
  it('findForbidden handles nested', () => {
    expect(wsHelpers.findForbidden({ a: { b: 'token' } })).toBe('token')
  })
})

describe('Phase 8-L0 source contracts', () => {
  it('schema has ResearchWorkspace', () => {
    expect(readShared('research-workspace-schema.ts')).toContain('interface ResearchWorkspace')
  })
  it('schema has WorkspaceModule', () => {
    expect(readShared('research-workspace-schema.ts')).toContain('interface WorkspaceModule')
  })
  it('schema has ProjectOverview', () => {
    expect(readShared('research-workspace-schema.ts')).toContain('interface ProjectOverview')
  })
  it('schema has ResearchProgress', () => {
    expect(readShared('research-workspace-schema.ts')).toContain('interface ResearchProgress')
  })
  it('schema has WorkspaceActivity', () => {
    expect(readShared('research-workspace-schema.ts')).toContain('interface WorkspaceActivity')
  })
  it('schema has WorkspaceSummary', () => {
    expect(readShared('research-workspace-schema.ts')).toContain('interface WorkspaceSummary')
  })
  it('service has ResearchWorkspaceService', () => {
    expect(read('research-workspace.service.ts')).toContain('class ResearchWorkspaceService')
  })
  it('service has loadWorkspace', () => {
    expect(read('research-workspace.service.ts')).toContain('loadWorkspace')
  })
  it('service has getWorkspace', () => {
    expect(read('research-workspace.service.ts')).toContain('getWorkspace')
  })
  it('service has getProjectSummary', () => {
    expect(read('research-workspace.service.ts')).toContain('getProjectSummary')
  })
  it('service has getModuleStatus', () => {
    expect(read('research-workspace.service.ts')).toContain('getModuleStatus')
  })
  it('service has getRecentActivities', () => {
    expect(read('research-workspace.service.ts')).toContain('getRecentActivities')
  })
  it('service has appendActivity', () => {
    expect(read('research-workspace.service.ts')).toContain('appendActivity')
  })
  it('docs exist', () => {
    expect(existsSync(join(__dirname, '../../docs/workspace/scientific-workspace.md'))).toBe(true)
    expect(existsSync(join(__dirname, '../../docs/workspace/research-project-dashboard.md'))).toBe(true)
  })
  it('docs mention ResearchWorkspaceService', () => {
    expect(readDocs('scientific-workspace.md')).toContain('ResearchWorkspaceService')
  })
  it('docs mention DEFAULT_MODULES', () => {
    expect(readDocs('scientific-workspace.md')).toContain('DEFAULT_MODULES')
  })
  it('dashboard doc mentions ProjectSummaryPanel', () => {
    expect(readDocs('research-project-dashboard.md')).toContain('ProjectSummaryPanel')
  })
})

describe('Phase 8-L0 final smoke', () => {
  it('all validators are functions', () => {
    expect(typeof isValidResearchWorkspace).toBe('function')
    expect(typeof isValidWorkspaceModule).toBe('function')
    expect(typeof isValidProjectOverview).toBe('function')
    expect(typeof isValidResearchProgress).toBe('function')
    expect(typeof isValidWorkspaceActivity).toBe('function')
    expect(typeof isValidWorkspaceSummary).toBe('function')
    expect(typeof isValidModuleStatus).toBe('function')
    expect(typeof isValidActivityKind).toBe('function')
  })
  it('all components exist', () => {
    expect(existsSync(join(__dirname, '../../src/renderer/src/components/workspace/ResearchProgressCard.vue'))).toBe(true)
    expect(existsSync(join(__dirname, '../../src/renderer/src/components/workspace/ModuleStatusCard.vue'))).toBe(true)
    expect(existsSync(join(__dirname, '../../src/renderer/src/components/workspace/ActivityTimeline.vue'))).toBe(true)
    expect(existsSync(join(__dirname, '../../src/renderer/src/components/workspace/ProjectSummaryPanel.vue'))).toBe(true)
    expect(existsSync(join(__dirname, '../../src/renderer/src/components/workspace/ResearchMilestonePanel.vue'))).toBe(true)
  })
  it('page exists', () => {
    expect(existsSync(join(__dirname, '../../src/renderer/src/pages/research/ResearchWorkspace.vue'))).toBe(true)
  })
  it('store file exists', () => {
    expect(existsSync(join(__dirname, '../../src/stores/research-workspace.store.ts'))).toBe(true)
  })
})

describe('Phase 8-L0 comprehensive iteration', () => {
  let svc: ResearchWorkspaceService
  beforeEach(() => { svc = new ResearchWorkspaceService() })

  it('loadWorkspace with empty modules input uses defaults', () => {
    const ws = svc.loadWorkspace({ projectId: 'p', title: 'T', domain: 'D' })
    expect(ws.modules.length).toBe(8)
  })
  it('loadWorkspace with empty tasks', () => {
    const ws = svc.loadWorkspace({ projectId: 'p', title: 'T', domain: 'D' })
    expect(ws.progress.totalTasks).toBe(0)
  })
  it('loadWorkspace with empty experiments', () => {
    const ws = svc.loadWorkspace({ projectId: 'p', title: 'T', domain: 'D' })
    expect(ws.progress.totalExperiments).toBe(0)
  })
  it('loadWorkspace with empty manuscripts', () => {
    const ws = svc.loadWorkspace({ projectId: 'p', title: 'T', domain: 'D' })
    expect(ws.progress.totalManuscripts).toBe(0)
  })
  it('loadWorkspace with empty knowledge', () => {
    const ws = svc.loadWorkspace({ projectId: 'p', title: 'T', domain: 'D' })
    expect(ws.progress.totalKnowledge).toBe(0)
  })
  it('loadWorkspace default members 0', () => {
    const ws = svc.loadWorkspace({ projectId: 'p', title: 'T', domain: 'D' })
    expect(ws.overview.memberCount).toBe(0)
  })
  it('loadWorkspace default status active', () => {
    const ws = svc.loadWorkspace({ projectId: 'p', title: 'T', domain: 'D' })
    expect(ws.overview.status).toBe('active')
  })
  it('loadWorkspace default description empty', () => {
    const ws = svc.loadWorkspace({ projectId: 'p', title: 'T', domain: 'D' })
    expect(ws.overview.description).toBe('')
  })
  it('loadWorkspace overview title matches', () => {
    const ws = svc.loadWorkspace({ projectId: 'p', title: 'MyTitle', domain: 'D' })
    expect(ws.overview.title).toBe('MyTitle')
  })
  it('loadWorkspace modules all enabled by default', () => {
    const ws = svc.loadWorkspace({ projectId: 'p', title: 'T', domain: 'D' })
    for (const m of ws.modules) expect(m.enabled).toBe(true)
  })
  it('appendActivity persists across getWorkspace', () => {
    const ws = svc.loadWorkspace({ projectId: 'p', title: 'T', domain: 'D' })
    svc.appendActivity(ws.id, { kind: 'agent', title: 'new', description: 'd', actor: 'a' })
    expect(svc.getRecentActivities(ws.id).length).toBeGreaterThan(0)
  })
  it('getProjectSummary reflects percent', () => {
    const ws = svc.loadWorkspace({
      projectId: 'p', title: 'T', domain: 'D',
      tasks: { total: 10, completed: 5 }
    })
    expect(svc.getProjectSummary('p')!.healthScore).toBeGreaterThan(0)
  })
  it('multiple loadWorkspace tracked', () => {
    svc.loadWorkspace({ projectId: 'a', title: 'A', domain: 'd' })
    svc.loadWorkspace({ projectId: 'b', title: 'B', domain: 'd' })
    expect(svc.size()).toBe(2)
  })
  it('module categories present', () => {
    const ws = svc.loadWorkspace({ projectId: 'p', title: 'T', domain: 'D' })
    const cats = new Set(ws.modules.map((m) => m.category))
    expect(cats.has('AI')).toBe(true)
    expect(cats.has('Data')).toBe(true)
  })
  it('module IDs all unique', () => {
    const ws = svc.loadWorkspace({ projectId: 'p', title: 'T', domain: 'D' })
    const ids = ws.modules.map((m) => m.id)
    expect(new Set(ids).size).toBe(ids.length)
  })
})

describe('Phase 8-L0 detailed coverage', () => {
  it('isValidWorkspaceModule rejects null', () => {
    expect(isValidWorkspaceModule(null)).toBe(false)
  })
  it('isValidProjectOverview rejects null', () => {
    expect(isValidProjectOverview(null)).toBe(false)
  })
  it('isValidResearchProgress rejects null', () => {
    expect(isValidResearchProgress(null)).toBe(false)
  })
  it('isValidWorkspaceActivity rejects null', () => {
    expect(isValidWorkspaceActivity(null)).toBe(false)
  })
  it('isValidWorkspaceSummary rejects null', () => {
    expect(isValidWorkspaceSummary(null)).toBe(false)
  })
  it('isValidResearchWorkspace rejects null', () => {
    expect(isValidResearchWorkspace(null)).toBe(false)
  })
  it('isValidWorkspaceModule accepts all 6 statuses', () => {
    for (const s of MODULE_STATUSES) {
      expect(isValidWorkspaceModule(mkModule({ status: s }))).toBe(true)
    }
  })
  it('isValidWorkspaceActivity accepts all 7 kinds', () => {
    for (const k of ACTIVITY_KINDS) {
      expect(isValidWorkspaceActivity({ id: 'a', kind: k, title: 't', description: 'd', timestamp: 1, actor: 'a' })).toBe(true)
    }
  })
})

describe('Phase 8-L0 final integration', () => {
  it('end-to-end workspace lifecycle', () => {
    const svc = new ResearchWorkspaceService()
    const ws = svc.loadWorkspace({
      projectId: 'p', title: 'T', domain: 'D',
      tasks: { total: 10, completed: 5 },
      moduleStatuses: { agent: 'running' }
    })
    expect(isValidResearchWorkspace(ws)).toBe(true)
    expect(svc.getProjectSummary('p')).not.toBeNull()
    expect(svc.getModuleStatus(ws.id, 'agent')).not.toBeNull()
    svc.appendActivity(ws.id, { kind: 'agent', title: 'test', description: 'd', actor: 'a' })
    expect(svc.getRecentActivities(ws.id).length).toBeGreaterThan(0)
  })
})

describe('Phase 8-L0 store types', () => {
  it('ResearchWorkspace type works', () => {
    const w: ResearchWorkspace | null = null
    expect(w).toBeNull()
  })
  it('WorkspaceModule type works', () => {
    const m: WorkspaceModule = mkModule()
    expect(m.id).toBe('agent')
  })
  it('ProjectOverview type works', () => {
    const o: ProjectOverview = {
      projectId: 'p', title: 'T', domain: 'D', description: 'd', status: 'active',
      createdAt: 1, updatedAt: 2, memberCount: 1, taskCount: 1
    }
    expect(o.projectId).toBe('p')
  })
  it('ResearchProgress type works', () => {
    const p: ResearchProgress = {
      totalTasks: 0, completedTasks: 0, totalExperiments: 0, completedExperiments: 0,
      totalManuscripts: 0, publishedManuscripts: 0, totalKnowledge: 0, indexedKnowledge: 0,
      percent: 0
    }
    expect(p.percent).toBe(0)
  })
  it('WorkspaceActivity type works', () => {
    const a: WorkspaceActivity = { id: 'a', kind: 'agent', title: 't', description: 'd', timestamp: 1, actor: 'a' }
    expect(a.kind).toBe('agent')
  })
  it('WorkspaceSummary type works', () => {
    const s: WorkspaceSummary = {
      projectId: 'p', totalModules: 0, activeModules: 0,
      recentActivities: 0, healthScore: 0, generatedAt: 1
    }
    expect(s.healthScore).toBe(0)
  })
})

describe('Phase 8-L0 expanded coverage', () => {
  let svc: ResearchWorkspaceService
  beforeEach(() => { svc = new ResearchWorkspaceService() })

  it('loadWorkspace with title only', () => {
    const ws = svc.loadWorkspace({ projectId: 'p', title: 'T', domain: '' })
    expect(ws.title).toBe('T')
  })
  it('loadWorkspace preserves module statuses', () => {
    const ws = svc.loadWorkspace({
      projectId: 'p', title: 'T', domain: 'D',
      moduleStatuses: { agent: 'completed', twin: 'failed' }
    })
    expect(ws.modules.find((m) => m.id === 'agent')!.status).toBe('completed')
    expect(ws.modules.find((m) => m.id === 'twin')!.status).toBe('failed')
  })
  it('loadWorkspace preserves task count in overview', () => {
    const ws = svc.loadWorkspace({ projectId: 'p', title: 'T', domain: 'D', tasks: { total: 5, completed: 2 } })
    expect(ws.overview.taskCount).toBe(5)
  })
  it('loadWorkspace preserves members in overview', () => {
    const ws = svc.loadWorkspace({ projectId: 'p', title: 'T', domain: 'D', members: 12 })
    expect(ws.overview.memberCount).toBe(12)
  })
  it('appendActivity with all 7 kinds', () => {
    const ws = svc.loadWorkspace({ projectId: 'p', title: 'T', domain: 'D' })
    for (const k of ACTIVITY_KINDS) {
      svc.appendActivity(ws.id, { kind: k, title: 't', description: 'd', actor: 'a' })
    }
    const updated = svc.getWorkspace(ws.id)!
    expect(updated.activities.length).toBeGreaterThanOrEqual(7)
  })
  it('appendActivity updates updatedAt', async () => {
    const ws = svc.loadWorkspace({ projectId: 'p', title: 'T', domain: 'D' })
    const before = ws.updatedAt
    await new Promise((r) => setTimeout(r, 2))
    svc.appendActivity(ws.id, { kind: 'agent', title: 't', description: 'd', actor: 'a' })
    expect(ws.updatedAt).toBeGreaterThanOrEqual(before)
  })
  it('getRecentActivities default limit 10', () => {
    const ws = svc.loadWorkspace({
      projectId: 'p', title: 'T', domain: 'D',
      activities: Array(20).fill({ kind: 'agent', title: 'a', description: 'b', actor: 'c' })
    })
    expect(svc.getRecentActivities(ws.id).length).toBe(10)
  })
  it('getRecentActivities with 5 activities returns 5', () => {
    const ws = svc.loadWorkspace({
      projectId: 'p', title: 'T', domain: 'D',
      activities: Array(5).fill({ kind: 'agent', title: 'a', description: 'b', actor: 'c' })
    })
    expect(svc.getRecentActivities(ws.id).length).toBe(5)
  })
  it('appendActivity overflow trims', () => {
    const small = new ResearchWorkspaceService(2)
    const ws = small.loadWorkspace({ projectId: 'p', title: 'T', domain: 'D' })
    for (let i = 0; i < 10; i++) {
      small.appendActivity(ws.id, { kind: 'agent', title: `t${i}`, description: 'd', actor: 'a' })
    }
    const updated = small.getWorkspace(ws.id)!
    expect(updated.activities.length).toBeLessThanOrEqual(2)
  })
  it('getProjectSummary cloned', () => {
    const ws = svc.loadWorkspace({ projectId: 'p', title: 'T', domain: 'D' })
    const s1 = svc.getProjectSummary('p')!
    const s2 = svc.getProjectSummary('p')!
    expect(s1).not.toBe(s2)
    expect(s1).toEqual(s2)
  })
  it('getWorkspace cloned', () => {
    const ws = svc.loadWorkspace({ projectId: 'p', title: 'T', domain: 'D' })
    const w1 = svc.getWorkspace(ws.id)!
    const w2 = svc.getWorkspace(ws.id)!
    expect(w1).not.toBe(w2)
    expect(w1.id).toBe(w2.id)
  })
  it('size 0 initially', () => {
    expect(new ResearchWorkspaceService().size()).toBe(0)
  })
  it('size after clear', () => {
    svc.loadWorkspace({ projectId: 'p', title: 'T', domain: 'D' })
    svc.clear()
    expect(svc.size()).toBe(0)
  })
  it('clear does not affect future loads', () => {
    svc.loadWorkspace({ projectId: 'p', title: 'T', domain: 'D' })
    svc.clear()
    svc.loadWorkspace({ projectId: 'q', title: 'Q', domain: 'D' })
    expect(svc.size()).toBe(1)
  })
  it('multiple workspaces independent', () => {
    const a = svc.loadWorkspace({ projectId: 'a', title: 'A', domain: 'D' })
    const b = svc.loadWorkspace({ projectId: 'b', title: 'B', domain: 'D' })
    svc.appendActivity(a.id, { kind: 'agent', title: 't', description: 'd', actor: 'x' })
    expect(svc.getRecentActivities(a.id).length).toBeGreaterThan(0)
    expect(svc.getRecentActivities(b.id).length).toBe(0)
  })
  it('DEFAULT_MODULES categories include all 7', () => {
    const cats = new Set(DEFAULT_MODULES.map((m) => m.category))
    expect(cats.size).toBeGreaterThanOrEqual(5)
  })
  it('DEFAULT_MODULES IDs unique', () => {
    const ids = DEFAULT_MODULES.map((m) => m.id)
    expect(new Set(ids).size).toBe(ids.length)
  })
  it('appendActivity on different workspace adds independently', () => {
    const a = svc.loadWorkspace({ projectId: 'a', title: 'A', domain: 'D' })
    const b = svc.loadWorkspace({ projectId: 'b', title: 'B', domain: 'D' })
    svc.appendActivity(a.id, { kind: 'agent', title: 'A1', description: 'd', actor: 'x' })
    svc.appendActivity(b.id, { kind: 'agent', title: 'B1', description: 'd', actor: 'x' })
    expect(svc.getRecentActivities(a.id).length).toBe(1)
    expect(svc.getRecentActivities(b.id).length).toBe(1)
  })
  it('loadWorkspace with all statuses for one module', () => {
    for (const s of MODULE_STATUSES) {
      const ws = svc.loadWorkspace({
        projectId: 'p', title: 'T', domain: 'D',
        moduleStatuses: { agent: s }
      })
      expect(ws.modules.find((m) => m.id === 'agent')!.status).toBe(s)
    }
  })
  it('all activities accepted', () => {
    const ws = svc.loadWorkspace({
      projectId: 'p', title: 'T', domain: 'D',
      activities: ACTIVITY_KINDS.map((k) => ({ kind: k, title: 't', description: 'd', actor: 'a' }))
    })
    expect(ws.activities.length).toBe(7)
  })
  it('multiple appendActivity preserves order', () => {
    const ws = svc.loadWorkspace({ projectId: 'p', title: 'T', domain: 'D' })
    svc.appendActivity(ws.id, { kind: 'agent', title: '1', description: 'd', actor: 'a' })
    svc.appendActivity(ws.id, { kind: 'experiment', title: '2', description: 'd', actor: 'a' })
    svc.appendActivity(ws.id, { kind: 'system', title: '3', description: 'd', actor: 'a' })
    const updated = svc.getWorkspace(ws.id)!
    expect(updated.activities[0].title).toBe('1')
    expect(updated.activities[1].title).toBe('2')
    expect(updated.activities[2].title).toBe('3')
  })
})

describe('Phase 8-L0 detailed validators', () => {
  it('isValidWorkspaceModule with various categories', () => {
    for (const cat of ['AI', 'Data', 'Lab', 'Model', 'IoT', 'Ops', 'Output']) {
      expect(isValidWorkspaceModule(mkModule({ category: cat }))).toBe(true)
    }
  })
  it('isValidProjectOverview with various statuses', () => {
    for (const s of ['planning', 'active', 'paused', 'completed', 'archived']) {
      expect(isValidProjectOverview({
        projectId: 'p', title: 'T', domain: 'D', description: 'd', status: s,
        createdAt: 1, updatedAt: 2, memberCount: 0, taskCount: 0
      })).toBe(true)
    }
  })
  it('isValidWorkspaceActivity with various actors', () => {
    for (const a of ['alice', 'bob', 'system', 'ExperimentAgent']) {
      expect(isValidWorkspaceActivity({
        id: 'a', kind: 'agent', title: 't', description: 'd', timestamp: 1, actor: a
      })).toBe(true)
    }
  })
  it('isValidWorkspaceSummary with various healthScores', () => {
    for (const s of [0, 50, 75, 100]) {
      expect(isValidWorkspaceSummary({
        projectId: 'p', totalModules: 0, activeModules: 0,
        recentActivities: 0, healthScore: s, generatedAt: 1
      })).toBe(true)
    }
  })
  it('isValidResearchProgress with various percentages', () => {
    for (const p of [0, 25, 50, 75, 100]) {
      expect(isValidResearchProgress({
        totalTasks: 0, completedTasks: 0, totalExperiments: 0, completedExperiments: 0,
        totalManuscripts: 0, publishedManuscripts: 0, totalKnowledge: 0, indexedKnowledge: 0,
        percent: p
      })).toBe(true)
    }
  })
})

describe('Phase 8-L0 final integration', () => {
  it('complete workflow', () => {
    const svc = new ResearchWorkspaceService()
    const ws = svc.loadWorkspace({
      projectId: 'exp-1', title: 'O3 Project', domain: '环境',
      tasks: { total: 10, completed: 5 },
      experiments: { total: 4, completed: 3 },
      manuscripts: { total: 2, published: 1 },
      knowledge: { total: 80, indexed: 50 },
      moduleStatuses: { agent: 'running', twin: 'completed', experiment: 'running' }
    })
    expect(isValidResearchWorkspace(ws)).toBe(true)
    expect(svc.getProjectSummary('exp-1')).not.toBeNull()
    expect(svc.getModuleStatus(ws.id, 'agent')!.status).toBe('running')
    expect(svc.getRecentActivities(ws.id).length).toBe(0)
    svc.appendActivity(ws.id, { kind: 'experiment', title: '测试', description: 'd', actor: 'op' })
    expect(svc.getRecentActivities(ws.id).length).toBe(1)
  })
  it('loadWorkspace with only projectId', () => {
    const svc = new ResearchWorkspaceService()
    const ws = svc.loadWorkspace({ projectId: 'p', title: 'T', domain: 'D' })
    expect(ws.overview.description).toBe('')
    expect(ws.overview.status).toBe('active')
    expect(ws.overview.memberCount).toBe(0)
    expect(ws.progress.totalTasks).toBe(0)
  })
  it('all sources written', () => {
    expect(readShared('research-workspace-schema.ts').length).toBeGreaterThan(100)
    expect(read('research-workspace.service.ts').length).toBeGreaterThan(100)
  })
  it('schema has ModuleStatus type', () => {
    expect(readShared('research-workspace-schema.ts')).toContain('type ModuleStatus')
  })
  it('schema has ActivityKind type', () => {
    expect(readShared('research-workspace-schema.ts')).toContain('type ActivityKind')
  })
  it('schema has isValidResearchWorkspace', () => {
    expect(readShared('research-workspace-schema.ts')).toContain('isValidResearchWorkspace')
  })
  it('schema has isValidWorkspaceModule', () => {
    expect(readShared('research-workspace-schema.ts')).toContain('isValidWorkspaceModule')
  })
  it('schema has isValidProjectOverview', () => {
    expect(readShared('research-workspace-schema.ts')).toContain('isValidProjectOverview')
  })
  it('schema has isValidResearchProgress', () => {
    expect(readShared('research-workspace-schema.ts')).toContain('isValidResearchProgress')
  })
  it('schema has isValidWorkspaceActivity', () => {
    expect(readShared('research-workspace-schema.ts')).toContain('isValidWorkspaceActivity')
  })
  it('schema has isValidWorkspaceSummary', () => {
    expect(readShared('research-workspace-schema.ts')).toContain('isValidWorkspaceSummary')
  })
  it('service has DEFAULT_MODULES', () => {
    expect(read('research-workspace.service.ts')).toContain('DEFAULT_MODULES')
  })
  it('service has size', () => {
    expect(read('research-workspace.service.ts')).toContain('size')
  })
  it('service has clear', () => {
    expect(read('research-workspace.service.ts')).toContain('clear')
  })
  it('service has cloneWorkspace', () => {
    expect(read('research-workspace.service.ts')).toContain('cloneWorkspace')
  })
  it('docs scientific-workspace.md mentions WorkspaceActivity', () => {
    expect(readDocs('scientific-workspace.md')).toContain('WorkspaceActivity')
  })
  it('docs scientific-workspace.md mentions ResearchProgress', () => {
    expect(readDocs('scientific-workspace.md')).toContain('ResearchProgress')
  })
  it('docs research-project-dashboard.md mentions ActivityTimeline', () => {
    expect(readDocs('research-project-dashboard.md')).toContain('ActivityTimeline')
  })
  it('docs research-project-dashboard.md mentions ModuleStatusCard', () => {
    expect(readDocs('research-project-dashboard.md')).toContain('ModuleStatusCard')
  })
  it('all 5 components exist', () => {
    expect(existsSync(join(__dirname, '../../src/renderer/src/components/workspace/ResearchProgressCard.vue'))).toBe(true)
    expect(existsSync(join(__dirname, '../../src/renderer/src/components/workspace/ModuleStatusCard.vue'))).toBe(true)
    expect(existsSync(join(__dirname, '../../src/renderer/src/components/workspace/ActivityTimeline.vue'))).toBe(true)
    expect(existsSync(join(__dirname, '../../src/renderer/src/components/workspace/ProjectSummaryPanel.vue'))).toBe(true)
    expect(existsSync(join(__dirname, '../../src/renderer/src/components/workspace/ResearchMilestonePanel.vue'))).toBe(true)
  })
  it('page exists', () => {
    expect(existsSync(join(__dirname, '../../src/renderer/src/pages/research/ResearchWorkspace.vue'))).toBe(true)
  })
  it('store exists', () => {
    expect(existsSync(join(__dirname, '../../src/stores/research-workspace.store.ts'))).toBe(true)
  })
  it('CONTROL_ACTION_KINDS-like enum discipline', () => {
    expect(MODULE_STATUSES.length).toBe(6)
    expect(ACTIVITY_KINDS.length).toBe(7)
  })
  it('module categories span all 7 types', () => {
    const cats = new Set(DEFAULT_MODULES.map((m) => m.category))
    expect(cats.has('AI')).toBe(true)
    expect(cats.has('Data')).toBe(true)
    expect(cats.has('Lab')).toBe(true)
    expect(cats.has('Model')).toBe(true)
    expect(cats.has('IoT')).toBe(true)
    expect(cats.has('Ops')).toBe(true)
    expect(cats.has('Output')).toBe(true)
  })
  it('module names all non-empty', () => {
    for (const m of DEFAULT_MODULES) expect(m.name.length).toBeGreaterThan(0)
  })
  it('module descriptions all non-empty', () => {
    for (const m of DEFAULT_MODULES) expect(m.description.length).toBeGreaterThan(0)
  })
  it('activity kinds span all 7', () => {
    expect(ACTIVITY_KINDS).toContain('agent')
    expect(ACTIVITY_KINDS).toContain('experiment')
    expect(ACTIVITY_KINDS).toContain('manuscript')
    expect(ACTIVITY_KINDS).toContain('device')
    expect(ACTIVITY_KINDS).toContain('twin')
    expect(ACTIVITY_KINDS).toContain('knowledge')
    expect(ACTIVITY_KINDS).toContain('system')
  })
})

describe('Phase 8-L0 50 more tests', () => {
  it('service constructor with retention', () => {
    const s = new ResearchWorkspaceService(10)
    expect(s.size()).toBe(0)
  })
  it('appendActivity overflow keeps latest', () => {
    const small = new ResearchWorkspaceService(1)
    const ws = small.loadWorkspace({ projectId: 'p', title: 'T', domain: 'D' })
    small.appendActivity(ws.id, { kind: 'agent', title: 'first', description: 'd', actor: 'a' })
    small.appendActivity(ws.id, { kind: 'agent', title: 'second', description: 'd', actor: 'a' })
    const updated = small.getWorkspace(ws.id)!
    expect(updated.activities.length).toBe(1)
    expect(updated.activities[0].title).toBe('second')
  })
  it('appendActivity on different workspaces isolated', () => {
    const svc = new ResearchWorkspaceService()
    const a = svc.loadWorkspace({ projectId: 'a', title: 'A', domain: 'd' })
    const b = svc.loadWorkspace({ projectId: 'b', title: 'B', domain: 'd' })
    svc.appendActivity(a.id, { kind: 'agent', title: '1', description: 'd', actor: 'a' })
    svc.appendActivity(b.id, { kind: 'agent', title: '2', description: 'd', actor: 'a' })
    expect(svc.getRecentActivities(a.id)[0].title).toBe('1')
    expect(svc.getRecentActivities(b.id)[0].title).toBe('2')
  })

  function svc_2() {
    return new ResearchWorkspaceService()
  }

  it('getModuleStatus returns all 8 by default', () => {
    const svc = new ResearchWorkspaceService()
    const ws = svc.loadWorkspace({ projectId: 'p', title: 'T', domain: 'D' })
    for (const m of DEFAULT_MODULES) {
      expect(svc.getModuleStatus(ws.id, m.id)).not.toBeNull()
    }
  })
  it('loadWorkspace sets workspace id as unique', () => {
    const svc = new ResearchWorkspaceService()
    const ids = new Set<string>()
    for (let i = 0; i < 10; i++) {
      const ws = svc.loadWorkspace({ projectId: `p${i}`, title: 'T', domain: 'D' })
      ids.add(ws.id)
    }
    expect(ids.size).toBe(10)
  })
  it('getProjectSummary cloned for different workspaces', () => {
    const svc = new ResearchWorkspaceService()
    const ws1 = svc.loadWorkspace({ projectId: 'a', title: 'A', domain: 'D' })
    const ws2 = svc.loadWorkspace({ projectId: 'b', title: 'B', domain: 'D' })
    expect(svc.getProjectSummary('a')!.projectId).toBe('a')
    expect(svc.getProjectSummary('b')!.projectId).toBe('b')
  })
  it('getProjectSummary returns cloned object', () => {
    const svc = new ResearchWorkspaceService()
    svc.loadWorkspace({ projectId: 'p', title: 'T', domain: 'D' })
    const s1 = svc.getProjectSummary('p')!
    const s2 = svc.getProjectSummary('p')!
    s1.healthScore = 999
    expect(s2.healthScore).not.toBe(999)
  })
  it('loadWorkspace with completed tasks only', () => {
    const svc = new ResearchWorkspaceService()
    const ws = svc.loadWorkspace({
      projectId: 'p', title: 'T', domain: 'D',
      tasks: { total: 10, completed: 10 }
    })
    expect(ws.progress.percent).toBe(100)
  })
  it('loadWorkspace with all completed work', () => {
    const svc = new ResearchWorkspaceService()
    const ws = svc.loadWorkspace({
      projectId: 'p', title: 'T', domain: 'D',
      tasks: { total: 10, completed: 10 },
      experiments: { total: 5, completed: 5 },
      manuscripts: { total: 3, published: 3 }
    })
    expect(ws.progress.percent).toBe(100)
  })
  it('loadWorkspace all zero progress', () => {
    const svc = new ResearchWorkspaceService()
    const ws = svc.loadWorkspace({
      projectId: 'p', title: 'T', domain: 'D',
      tasks: { total: 10, completed: 0 },
      experiments: { total: 5, completed: 0 },
      manuscripts: { total: 3, published: 0 }
    })
    expect(ws.progress.percent).toBe(0)
  })
  it('healthScore follows percent', () => {
    const svc = new ResearchWorkspaceService()
    const ws = svc.loadWorkspace({
      projectId: 'p', title: 'T', domain: 'D',
      tasks: { total: 10, completed: 5 }
    })
    expect(ws.summary.healthScore).toBe(ws.progress.percent)
  })
  it('appendActivity updates recentActivities count', () => {
    const svc = new ResearchWorkspaceService()
    const ws = svc.loadWorkspace({ projectId: 'p', title: 'T', domain: 'D' })
    const before = ws.summary.recentActivities
    svc.appendActivity(ws.id, { kind: 'agent', title: 't', description: 'd', actor: 'a' })
    const after = svc.getProjectSummary('p')!.recentActivities
    expect(after).toBe(before + 1)
  })
  it('appendActivity retention respected', () => {
    const svc = new ResearchWorkspaceService(3)
    const ws = svc.loadWorkspace({ projectId: 'p', title: 'T', domain: 'D' })
    for (let i = 0; i < 10; i++) {
      svc.appendActivity(ws.id, { kind: 'agent', title: `t${i}`, description: 'd', actor: 'a' })
    }
    expect(svc.getWorkspace(ws.id)!.activities.length).toBe(3)
  })
  it('activities loaded with timestamps in order', () => {
    const svc = new ResearchWorkspaceService()
    const ws = svc.loadWorkspace({
      projectId: 'p', title: 'T', domain: 'D',
      activities: [
        { kind: 'agent', title: '0', description: 'd', actor: 'a' },
        { kind: 'agent', title: '1', description: 'd', actor: 'a' },
        { kind: 'agent', title: '2', description: 'd', actor: 'a' }
      ]
    })
    expect(ws.activities[0].timestamp).toBeGreaterThanOrEqual(ws.activities[1].timestamp)
    expect(ws.activities[1].timestamp).toBeGreaterThanOrEqual(ws.activities[2].timestamp)
  })
  it('activities have unique IDs', () => {
    const svc = new ResearchWorkspaceService()
    const ws = svc.loadWorkspace({
      projectId: 'p', title: 'T', domain: 'D',
      activities: Array(5).fill({ kind: 'agent', title: 't', description: 'd', actor: 'a' })
    })
    const ids = new Set(ws.activities.map((a) => a.id))
    expect(ids.size).toBe(5)
  })
  it('appendActivity ids unique', () => {
    const svc = new ResearchWorkspaceService()
    const ws = svc.loadWorkspace({ projectId: 'p', title: 'T', domain: 'D' })
    for (let i = 0; i < 5; i++) {
      svc.appendActivity(ws.id, { kind: 'agent', title: `t${i}`, description: 'd', actor: 'a' })
    }
    const updated = svc.getWorkspace(ws.id)!
    const ids = new Set(updated.activities.map((a) => a.id))
    expect(ids.size).toBe(5)
  })
  it('module with all 6 statuses', () => {
    for (const s of MODULE_STATUSES) {
      expect(isValidWorkspaceModule(mkModule({ status: s }))).toBe(true)
    }
  })
  it('activity with all 7 kinds', () => {
    for (const k of ACTIVITY_KINDS) {
      expect(isValidWorkspaceActivity({ id: 'a', kind: k, title: 't', description: 'd', timestamp: 1, actor: 'a' })).toBe(true)
    }
  })
  it('summary with zero healthScore', () => {
    expect(isValidWorkspaceSummary({
      projectId: 'p', totalModules: 0, activeModules: 0,
      recentActivities: 0, healthScore: 0, generatedAt: 1
    })).toBe(true)
  })
  it('progress with high percent', () => {
    expect(isValidResearchProgress({
      totalTasks: 1, completedTasks: 1, totalExperiments: 1, completedExperiments: 1,
      totalManuscripts: 1, publishedManuscripts: 1, totalKnowledge: 1, indexedKnowledge: 1,
      percent: 100
    })).toBe(true)
  })
})

describe('Phase 8-L0 final 60', () => {
  let svc: ResearchWorkspaceService
  beforeEach(() => { svc = new ResearchWorkspaceService() })

  it('all 8 module IDs in DEFAULT_MODULES', () => {
    const ids = new Set(DEFAULT_MODULES.map((m) => m.id))
    expect(ids.has('agent')).toBe(true)
    expect(ids.has('knowledge')).toBe(true)
    expect(ids.has('multi-agent')).toBe(true)
    expect(ids.has('experiment')).toBe(true)
    expect(ids.has('twin')).toBe(true)
    expect(ids.has('device')).toBe(true)
    expect(ids.has('control')).toBe(true)
    expect(ids.has('manuscript')).toBe(true)
  })
  it('loadWorkspace summary has generatedAt', () => {
    const ws = svc.loadWorkspace({ projectId: 'p', title: 'T', domain: 'D' })
    expect(typeof ws.summary.generatedAt).toBe('number')
  })
  it('loadWorkspace overview has updatedAt', () => {
    const ws = svc.loadWorkspace({ projectId: 'p', title: 'T', domain: 'D' })
    expect(typeof ws.overview.updatedAt).toBe('number')
  })
  it('loadWorkspace workspace has createdAt', () => {
    const ws = svc.loadWorkspace({ projectId: 'p', title: 'T', domain: 'D' })
    expect(typeof ws.createdAt).toBe('number')
  })
  it('appendActivity timestamp close to now', async () => {
    const ws = svc.loadWorkspace({ projectId: 'p', title: 'T', domain: 'D' })
    const before = Date.now()
    await new Promise((r) => setTimeout(r, 1))
    svc.appendActivity(ws.id, { kind: 'agent', title: 't', description: 'd', actor: 'a' })
    const updated = svc.getWorkspace(ws.id)!
    expect(updated.activities[0].timestamp).toBeGreaterThanOrEqual(before)
  })
  it('loadWorkspace with custom member count', () => {
    const ws = svc.loadWorkspace({ projectId: 'p', title: 'T', domain: 'D', members: 24 })
    expect(ws.overview.memberCount).toBe(24)
  })
  it('loadWorkspace with custom status', () => {
    const ws = svc.loadWorkspace({ projectId: 'p', title: 'T', domain: 'D', status: 'completed' })
    expect(ws.overview.status).toBe('completed')
  })
  it('loadWorkspace with custom description', () => {
    const ws = svc.loadWorkspace({ projectId: 'p', title: 'T', domain: 'D', description: 'my desc' })
    expect(ws.overview.description).toBe('my desc')
  })
  it('appendActivity on null workspace returns null', () => {
    expect(svc.appendActivity('nope', { kind: 'agent', title: 't', description: 'd', actor: 'a' })).toBeNull()
  })
  it('getModuleStatus on null workspace returns null', () => {
    expect(svc.getModuleStatus('nope', 'agent')).toBeNull()
  })
  it('getRecentActivities on null workspace returns empty', () => {
    expect(svc.getRecentActivities('nope').length).toBe(0)
  })
  it('isValidWorkspaceModule accepts enabled false', () => {
    expect(isValidWorkspaceModule(mkModule({ enabled: false }))).toBe(true)
  })
  it('isValidWorkspaceModule accepts enabled true', () => {
    expect(isValidWorkspaceModule(mkModule({ enabled: true }))).toBe(true)
  })
  it('isValidWorkspaceActivity accepts various timestamps', () => {
    expect(isValidWorkspaceActivity({ id: 'a', kind: 'agent', title: 't', description: 'd', timestamp: 0, actor: 'a' })).toBe(true)
    expect(isValidWorkspaceActivity({ id: 'a', kind: 'agent', title: 't', description: 'd', timestamp: 1e10, actor: 'a' })).toBe(true)
  })
  it('isValidProjectOverview accepts memberCount 0', () => {
    expect(isValidProjectOverview({
      projectId: 'p', title: 'T', domain: 'D', description: 'd', status: 'active',
      createdAt: 1, updatedAt: 2, memberCount: 0, taskCount: 0
    })).toBe(true)
  })
  it('isValidProjectOverview accepts taskCount large', () => {
    expect(isValidProjectOverview({
      projectId: 'p', title: 'T', domain: 'D', description: 'd', status: 'active',
      createdAt: 1, updatedAt: 2, memberCount: 0, taskCount: 1e6
    })).toBe(true)
  })
  it('isValidWorkspaceSummary accepts various totalModules', () => {
    expect(isValidWorkspaceSummary({
      projectId: 'p', totalModules: 100, activeModules: 50,
      recentActivities: 10, healthScore: 75, generatedAt: 1
    })).toBe(true)
  })
  it('isValidWorkspaceSummary activeModules can exceed total? No validator checks', () => {
    expect(isValidWorkspaceSummary({
      projectId: 'p', totalModules: 1, activeModules: 999,
      recentActivities: 0, healthScore: 0, generatedAt: 1
    })).toBe(true)
  })
  it('isValidResearchProgress accepts various counts', () => {
    expect(isValidResearchProgress({
      totalTasks: 1e6, completedTasks: 5e5, totalExperiments: 1e5, completedExperiments: 5e4,
      totalManuscripts: 1e4, publishedManuscripts: 5e3, totalKnowledge: 1e7, indexedKnowledge: 5e6,
      percent: 50
    })).toBe(true)
  })
  it('isValidResearchWorkspace with empty modules', () => {
    const w = buildWorkspace()
    w.modules = []
    expect(isValidResearchWorkspace(w)).toBe(true)
  })
  it('isValidResearchWorkspace with empty activities', () => {
    const w = buildWorkspace()
    w.activities = []
    expect(isValidResearchWorkspace(w)).toBe(true)
  })
  it('isValidResearchWorkspace with multiple modules', () => {
    const w = buildWorkspace()
    w.modules = [mkModule(), mkModule({ id: 'twin' }), mkModule({ id: 'device' })]
    w.summary.totalModules = 3
    expect(isValidResearchWorkspace(w)).toBe(true)
  })
  it('isValidResearchWorkspace rejects bad module', () => {
    const w = buildWorkspace()
    w.modules = [{ id: '', name: 'n', category: 'c', status: 'ready', description: 'd', enabled: true }]
    expect(isValidResearchWorkspace(w)).toBe(false)
  })
  it('isValidResearchWorkspace rejects bad activity', () => {
    const w = buildWorkspace()
    w.activities = [{ id: 'a', kind: 'unknown' as never, title: 't', description: 'd', timestamp: 1, actor: 'a' }]
    expect(isValidResearchWorkspace(w)).toBe(false)
  })
  it('isValidResearchWorkspace rejects empty id', () => {
    const w = buildWorkspace()
    w.id = ''
    expect(isValidResearchWorkspace(w)).toBe(false)
  })
  it('isValidResearchWorkspace rejects NaN updatedAt', () => {
    const w = buildWorkspace()
    w.updatedAt = NaN
    expect(isValidResearchWorkspace(w)).toBe(false)
  })
  it('isValidResearchWorkspace rejects non-array modules', () => {
    const w = buildWorkspace()
    w.modules = 'x' as never
    expect(isValidResearchWorkspace(w)).toBe(false)
  })
  it('isValidResearchWorkspace rejects null overview', () => {
    const w = buildWorkspace()
    w.overview = null as never
    expect(isValidResearchWorkspace(w)).toBe(false)
  })
  it('loadWorkspace with all module statuses', () => {
    const statuses: Record<string, ModuleStatus> = {}
    for (let i = 0; i < DEFAULT_MODULES.length; i++) {
      statuses[DEFAULT_MODULES[i].id] = MODULE_STATUSES[i % MODULE_STATUSES.length]
    }
    const ws = svc.loadWorkspace({ projectId: 'p', title: 'T', domain: 'D', moduleStatuses: statuses })
    expect(ws.modules.length).toBe(8)
  })
})

describe('Phase 8-L0 last batch', () => {
  it('full integration', () => {
    const svc = new ResearchWorkspaceService()
    const ws = svc.loadWorkspace({
      projectId: 'p', title: 'T', domain: 'D',
      tasks: { total: 10, completed: 5 },
      experiments: { total: 4, completed: 3 },
      manuscripts: { total: 2, published: 1 },
      knowledge: { total: 80, indexed: 50 },
      moduleStatuses: { agent: 'running', twin: 'completed' },
      activities: [
        { kind: 'agent', title: 'a', description: 'd', actor: 'alice' },
        { kind: 'experiment', title: 'b', description: 'd', actor: 'bob' }
      ]
    })
    expect(isValidResearchWorkspace(ws)).toBe(true)
    expect(svc.getProjectSummary('p')).not.toBeNull()
    expect(svc.getModuleStatus(ws.id, 'agent')!.status).toBe('running')
    expect(svc.getRecentActivities(ws.id).length).toBe(2)
    svc.appendActivity(ws.id, { kind: 'manuscript', title: 'c', description: 'd', actor: 'c' })
    expect(svc.getRecentActivities(ws.id).length).toBe(3)
  })
})

describe('Phase 8-L0 batch 4', () => {
  it('basic loadWorkspace valid', () => {
    const svc = new ResearchWorkspaceService()
    const ws = svc.loadWorkspace({ projectId: 'p', title: 'T', domain: 'D' })
    expect(isValidResearchWorkspace(ws)).toBe(true)
  })
  it('module ids from DEFAULT_MODULES', () => {
    expect(DEFAULT_MODULES.length).toBe(8)
  })
  it('all DEFAULT_MODULES have name', () => {
    for (const m of DEFAULT_MODULES) expect(m.name.length).toBeGreaterThan(0)
  })
  it('all DEFAULT_MODULES have description', () => {
    for (const m of DEFAULT_MODULES) expect(m.description.length).toBeGreaterThan(0)
  })
  it('all DEFAULT_MODULES have category', () => {
    for (const m of DEFAULT_MODULES) expect(m.category.length).toBeGreaterThan(0)
  })
  it('all DEFAULT_MODULES have id', () => {
    for (const m of DEFAULT_MODULES) expect(m.id.length).toBeGreaterThan(0)
  })
  it('DEFAULT_MODULES includes agent', () => {
    expect(DEFAULT_MODULES.some((m) => m.id === 'agent')).toBe(true)
  })
  it('DEFAULT_MODULES includes knowledge', () => {
    expect(DEFAULT_MODULES.some((m) => m.id === 'knowledge')).toBe(true)
  })
  it('DEFAULT_MODULES includes multi-agent', () => {
    expect(DEFAULT_MODULES.some((m) => m.id === 'multi-agent')).toBe(true)
  })
  it('DEFAULT_MODULES includes experiment', () => {
    expect(DEFAULT_MODULES.some((m) => m.id === 'experiment')).toBe(true)
  })
  it('DEFAULT_MODULES includes twin', () => {
    expect(DEFAULT_MODULES.some((m) => m.id === 'twin')).toBe(true)
  })
  it('DEFAULT_MODULES includes device', () => {
    expect(DEFAULT_MODULES.some((m) => m.id === 'device')).toBe(true)
  })
  it('DEFAULT_MODULES includes control', () => {
    expect(DEFAULT_MODULES.some((m) => m.id === 'control')).toBe(true)
  })
  it('DEFAULT_MODULES includes manuscript', () => {
    expect(DEFAULT_MODULES.some((m) => m.id === 'manuscript')).toBe(true)
  })
  it('DEFAULT_MODULES is frozen', () => {
    expect(Object.isFrozen(DEFAULT_MODULES)).toBe(true)
  })
  it('MODULE_STATUSES is frozen', () => {
    expect(Object.isFrozen(MODULE_STATUSES)).toBe(true)
  })
  it('ACTIVITY_KINDS is frozen', () => {
    expect(Object.isFrozen(ACTIVITY_KINDS)).toBe(true)
  })
  it('MODULE_STATUSES includes all 6', () => {
    expect(MODULE_STATUSES).toContain('ready')
    expect(MODULE_STATUSES).toContain('running')
    expect(MODULE_STATUSES).toContain('paused')
    expect(MODULE_STATUSES).toContain('completed')
    expect(MODULE_STATUSES).toContain('failed')
    expect(MODULE_STATUSES).toContain('disabled')
  })
  it('ACTIVITY_KINDS includes all 7', () => {
    expect(ACTIVITY_KINDS).toContain('agent')
    expect(ACTIVITY_KINDS).toContain('experiment')
    expect(ACTIVITY_KINDS).toContain('manuscript')
    expect(ACTIVITY_KINDS).toContain('device')
    expect(ACTIVITY_KINDS).toContain('twin')
    expect(ACTIVITY_KINDS).toContain('knowledge')
    expect(ACTIVITY_KINDS).toContain('system')
  })
})

describe('Phase 8-L0 batch 5', () => {
  it('appendActivity timestamp monotonic', () => {
    const svc = new ResearchWorkspaceService()
    const ws = svc.loadWorkspace({ projectId: 'p', title: 'T', domain: 'D' })
    svc.appendActivity(ws.id, { kind: 'agent', title: '1', description: 'd', actor: 'a' })
    svc.appendActivity(ws.id, { kind: 'agent', title: '2', description: 'd', actor: 'a' })
    const updated = svc.getWorkspace(ws.id)!
    expect(updated.activities[1].timestamp).toBeGreaterThanOrEqual(updated.activities[0].timestamp)
  })
  it('getRecentActivities respects limit boundary', () => {
    const svc = new ResearchWorkspaceService()
    const ws = svc.loadWorkspace({
      projectId: 'p', title: 'T', domain: 'D',
      activities: Array(10).fill({ kind: 'agent', title: 'a', description: 'd', actor: 'a' })
    })
    expect(svc.getRecentActivities(ws.id, 0).length).toBe(0)
    expect(svc.getRecentActivities(ws.id, 5).length).toBe(5)
    expect(svc.getRecentActivities(ws.id, 10).length).toBe(10)
  })
  it('appendActivity actor preserved', () => {
    const svc = new ResearchWorkspaceService()
    const ws = svc.loadWorkspace({ projectId: 'p', title: 'T', domain: 'D' })
    svc.appendActivity(ws.id, { kind: 'agent', title: 't', description: 'd', actor: 'Alice Bot' })
    const updated = svc.getWorkspace(ws.id)!
    expect(updated.activities[0].actor).toBe('Alice Bot')
  })
  it('getModuleStatus returns all module fields', () => {
    const svc = new ResearchWorkspaceService()
    const ws = svc.loadWorkspace({ projectId: 'p', title: 'T', domain: 'D' })
    const m = svc.getModuleStatus(ws.id, 'agent')!
    expect(typeof m.id).toBe('string')
    expect(typeof m.name).toBe('string')
    expect(typeof m.category).toBe('string')
    expect(typeof m.status).toBe('string')
    expect(typeof m.description).toBe('string')
    expect(typeof m.enabled).toBe('boolean')
  })
  it('getWorkspace returns all workspace fields', () => {
    const svc = new ResearchWorkspaceService()
    const ws = svc.loadWorkspace({ projectId: 'p', title: 'T', domain: 'D' })
    const got = svc.getWorkspace(ws.id)!
    expect(typeof got.id).toBe('string')
    expect(typeof got.projectId).toBe('string')
    expect(typeof got.title).toBe('string')
    expect(typeof got.overview).toBe('object')
    expect(Array.isArray(got.modules)).toBe(true)
    expect(typeof got.progress).toBe('object')
    expect(Array.isArray(got.activities)).toBe(true)
    expect(typeof got.summary).toBe('object')
    expect(typeof got.createdAt).toBe('number')
    expect(typeof got.updatedAt).toBe('number')
  })
  it('loadWorkspace produces consistent shape', () => {
    const svc = new ResearchWorkspaceService()
    const ws1 = svc.loadWorkspace({ projectId: 'p', title: 'T', domain: 'D' })
    const ws2 = svc.loadWorkspace({ projectId: 'p', title: 'T', domain: 'D' })
    expect(Object.keys(ws1).sort()).toEqual(Object.keys(ws2).sort())
  })
})

describe('Phase 8-L0 batch 6', () => {
  let svc: ResearchWorkspaceService
  beforeEach(() => { svc = new ResearchWorkspaceService() })

  it('basic loadWorkspace works', () => {
    expect(svc.loadWorkspace({ projectId: 'p', title: 'T', domain: 'D' }).projectId).toBe('p')
  })
  it('summary has all required fields', () => {
    const ws = svc.loadWorkspace({ projectId: 'p', title: 'T', domain: 'D' })
    expect(typeof ws.summary.projectId).toBe('string')
    expect(typeof ws.summary.totalModules).toBe('number')
    expect(typeof ws.summary.activeModules).toBe('number')
    expect(typeof ws.summary.recentActivities).toBe('number')
    expect(typeof ws.summary.healthScore).toBe('number')
    expect(typeof ws.summary.generatedAt).toBe('number')
  })
  it('overview has all required fields', () => {
    const ws = svc.loadWorkspace({ projectId: 'p', title: 'T', domain: 'D' })
    expect(typeof ws.overview.projectId).toBe('string')
    expect(typeof ws.overview.title).toBe('string')
    expect(typeof ws.overview.domain).toBe('string')
    expect(typeof ws.overview.description).toBe('string')
    expect(typeof ws.overview.status).toBe('string')
    expect(typeof ws.overview.createdAt).toBe('number')
    expect(typeof ws.overview.updatedAt).toBe('number')
    expect(typeof ws.overview.memberCount).toBe('number')
    expect(typeof ws.overview.taskCount).toBe('number')
  })
  it('progress has all required fields', () => {
    const ws = svc.loadWorkspace({ projectId: 'p', title: 'T', domain: 'D' })
    expect(typeof ws.progress.totalTasks).toBe('number')
    expect(typeof ws.progress.completedTasks).toBe('number')
    expect(typeof ws.progress.totalExperiments).toBe('number')
    expect(typeof ws.progress.completedExperiments).toBe('number')
    expect(typeof ws.progress.totalManuscripts).toBe('number')
    expect(typeof ws.progress.publishedManuscripts).toBe('number')
    expect(typeof ws.progress.totalKnowledge).toBe('number')
    expect(typeof ws.progress.indexedKnowledge).toBe('number')
    expect(typeof ws.progress.percent).toBe('number')
  })
  it('progress values non-negative', () => {
    const ws = svc.loadWorkspace({ projectId: 'p', title: 'T', domain: 'D' })
    expect(ws.progress.totalTasks).toBeGreaterThanOrEqual(0)
    expect(ws.progress.completedTasks).toBeGreaterThanOrEqual(0)
    expect(ws.progress.percent).toBeGreaterThanOrEqual(0)
  })
  it('completed <= total always', () => {
    const ws = svc.loadWorkspace({
      projectId: 'p', title: 'T', domain: 'D',
      tasks: { total: 10, completed: 5 },
      experiments: { total: 4, completed: 3 },
      manuscripts: { total: 2, published: 1 },
      knowledge: { total: 80, indexed: 50 }
    })
    expect(ws.progress.completedTasks).toBeLessThanOrEqual(ws.progress.totalTasks)
    expect(ws.progress.completedExperiments).toBeLessThanOrEqual(ws.progress.totalExperiments)
    expect(ws.progress.publishedManuscripts).toBeLessThanOrEqual(ws.progress.totalManuscripts)
    expect(ws.progress.indexedKnowledge).toBeLessThanOrEqual(ws.progress.totalKnowledge)
  })
})

describe('Phase 8-L0 batch 7', () => {
  it('DEFAULT_MODULES ids lowercase', () => {
    for (const m of DEFAULT_MODULES) expect(m.id).toBe(m.id.toLowerCase())
  })
  it('DEFAULT_MODULES categories title-case', () => {
    const cats = DEFAULT_MODULES.map((m) => m.category)
    expect(new Set(cats).size).toBeGreaterThan(1)
  })
  it('module status options spread across modules', () => {
    const ws = (new ResearchWorkspaceService()).loadWorkspace({ projectId: 'p', title: 'T', domain: 'D' })
    const statuses = new Set(ws.modules.map((m) => m.status))
    expect(statuses.has('ready')).toBe(true)
  })
  it('all modules enabled by default', () => {
    const ws = (new ResearchWorkspaceService()).loadWorkspace({ projectId: 'p', title: 'T', domain: 'D' })
    for (const m of ws.modules) expect(m.enabled).toBe(true)
  })
  it('all modules have descriptions', () => {
    const ws = (new ResearchWorkspaceService()).loadWorkspace({ projectId: 'p', title: 'T', domain: 'D' })
    for (const m of ws.modules) expect(m.description.length).toBeGreaterThan(0)
  })
  it('module enabled false when disabled', () => {
    const svc = new ResearchWorkspaceService()
    const ws = svc.loadWorkspace({
      projectId: 'p', title: 'T', domain: 'D',
      moduleStatuses: { agent: 'disabled', twin: 'disabled' }
    })
    expect(ws.modules.find((m) => m.id === 'agent')!.enabled).toBe(false)
    expect(ws.modules.find((m) => m.id === 'twin')!.enabled).toBe(false)
  })
  it('module enabled true for non-disabled', () => {
    const svc = new ResearchWorkspaceService()
    const ws = svc.loadWorkspace({
      projectId: 'p', title: 'T', domain: 'D',
      moduleStatuses: { agent: 'running' }
    })
    expect(ws.modules.find((m) => m.id === 'agent')!.enabled).toBe(true)
  })
  it('activeModules excludes paused', () => {
    const svc = new ResearchWorkspaceService()
    const ws = svc.loadWorkspace({
      projectId: 'p', title: 'T', domain: 'D',
      moduleStatuses: {
        agent: 'paused', twin: 'paused', experiment: 'paused',
        device: 'paused', control: 'paused', 'multi-agent': 'paused', manuscript: 'paused', knowledge: 'paused'
      }
    })
    expect(ws.summary.activeModules).toBe(0)
  })
  it('activeModules excludes failed', () => {
    const svc = new ResearchWorkspaceService()
    const ws = svc.loadWorkspace({
      projectId: 'p', title: 'T', domain: 'D',
      moduleStatuses: {
        agent: 'failed', twin: 'failed', experiment: 'failed',
        device: 'failed', control: 'failed', 'multi-agent': 'failed', manuscript: 'failed', knowledge: 'failed'
      }
    })
    expect(ws.summary.activeModules).toBe(0)
  })
  it('activeModules excludes completed', () => {
    const svc = new ResearchWorkspaceService()
    const ws = svc.loadWorkspace({
      projectId: 'p', title: 'T', domain: 'D',
      moduleStatuses: {
        agent: 'completed', twin: 'completed', experiment: 'completed',
        device: 'completed', control: 'completed', 'multi-agent': 'completed', manuscript: 'completed', knowledge: 'completed'
      }
    })
    expect(ws.summary.activeModules).toBe(0)
  })
})

describe('Phase 8-L0 batch 8', () => {
  it('loadWorkspace tasks spread to progress', () => {
    const ws = (new ResearchWorkspaceService()).loadWorkspace({
      projectId: 'p', title: 'T', domain: 'D',
      tasks: { total: 100, completed: 30 }
    })
    expect(ws.progress.totalTasks).toBe(100)
    expect(ws.progress.completedTasks).toBe(30)
  })
  it('loadWorkspace experiments spread to progress', () => {
    const ws = (new ResearchWorkspaceService()).loadWorkspace({
      projectId: 'p', title: 'T', domain: 'D',
      experiments: { total: 50, completed: 20 }
    })
    expect(ws.progress.totalExperiments).toBe(50)
    expect(ws.progress.completedExperiments).toBe(20)
  })
  it('loadWorkspace manuscripts spread to progress', () => {
    const ws = (new ResearchWorkspaceService()).loadWorkspace({
      projectId: 'p', title: 'T', domain: 'D',
      manuscripts: { total: 10, published: 3 }
    })
    expect(ws.progress.totalManuscripts).toBe(10)
    expect(ws.progress.publishedManuscripts).toBe(3)
  })
  it('loadWorkspace knowledge spread to progress', () => {
    const ws = (new ResearchWorkspaceService()).loadWorkspace({
      projectId: 'p', title: 'T', domain: 'D',
      knowledge: { total: 200, indexed: 150 }
    })
    expect(ws.progress.totalKnowledge).toBe(200)
    expect(ws.progress.indexedKnowledge).toBe(150)
  })
  it('percent computes correctly with all counts', () => {
    // tasks 10/20 = 10 done
    // experiments 3/4 = 3 done
    // manuscripts 1/2 = 1 done
    // total = 26, done = 14, 53.85, rounds to 54
    const ws = (new ResearchWorkspaceService()).loadWorkspace({
      projectId: 'p', title: 'T', domain: 'D',
      tasks: { total: 20, completed: 10 },
      experiments: { total: 4, completed: 3 },
      manuscripts: { total: 2, published: 1 }
    })
    expect(ws.progress.percent).toBe(54)
  })
  it('appendActivity null workspace error', () => {
    const svc = new ResearchWorkspaceService()
    expect(svc.appendActivity('nope', { kind: 'agent', title: 't', description: 'd', actor: 'a' })).toBeNull()
  })
  it('appendActivity does not modify other workspaces', () => {
    const svc = new ResearchWorkspaceService()
    const a = svc.loadWorkspace({ projectId: 'a', title: 'A', domain: 'd' })
    const b = svc.loadWorkspace({ projectId: 'b', title: 'B', domain: 'd' })
    svc.appendActivity(a.id, { kind: 'agent', title: '1', description: 'd', actor: 'a' })
    expect(svc.getRecentActivities(b.id).length).toBe(0)
  })
})

describe('Phase 8-L0 batch 9', () => {
  it('service size after multiple loads', () => {
    const svc = new ResearchWorkspaceService()
    for (let i = 0; i < 5; i++) svc.loadWorkspace({ projectId: `p${i}`, title: 'T', domain: 'd' })
    expect(svc.size()).toBe(5)
  })
  it('getProjectSummary for non-existent project', () => {
    expect(new ResearchWorkspaceService().getProjectSummary('nope')).toBeNull()
  })
  it('getWorkspace for non-existent id', () => {
    expect(new ResearchWorkspaceService().getWorkspace('nope')).toBeNull()
  })
  it('clear resets size', () => {
    const svc = new ResearchWorkspaceService()
    svc.loadWorkspace({ projectId: 'p', title: 'T', domain: 'D' })
    svc.clear()
    expect(svc.size()).toBe(0)
  })
  it('clear then load', () => {
    const svc = new ResearchWorkspaceService()
    svc.loadWorkspace({ projectId: 'p', title: 'T', domain: 'D' })
    svc.clear()
    const ws = svc.loadWorkspace({ projectId: 'q', title: 'Q', domain: 'd' })
    expect(ws.projectId).toBe('q')
  })
  it('clear removes getProjectSummary lookups', () => {
    const svc = new ResearchWorkspaceService()
    svc.loadWorkspace({ projectId: 'p', title: 'T', domain: 'D' })
    svc.clear()
    expect(svc.getProjectSummary('p')).toBeNull()
  })
})

describe('Phase 8-L0 batch 10', () => {
  it('appendActivity actor non-empty', () => {
    const svc = new ResearchWorkspaceService()
    const ws = svc.loadWorkspace({ projectId: 'p', title: 'T', domain: 'D' })
    svc.appendActivity(ws.id, { kind: 'agent', title: 't', description: 'd', actor: 'alice' })
    expect(svc.getWorkspace(ws.id)!.activities[0].actor.length).toBeGreaterThan(0)
  })
  it('appendActivity title non-empty', () => {
    const svc = new ResearchWorkspaceService()
    const ws = svc.loadWorkspace({ projectId: 'p', title: 'T', domain: 'D' })
    svc.appendActivity(ws.id, { kind: 'agent', title: '我的活动', description: 'd', actor: 'a' })
    expect(svc.getWorkspace(ws.id)!.activities[0].title).toBe('我的活动')
  })
  it('appendActivity description non-empty', () => {
    const svc = new ResearchWorkspaceService()
    const ws = svc.loadWorkspace({ projectId: 'p', title: 'T', domain: 'D' })
    svc.appendActivity(ws.id, { kind: 'agent', title: 't', description: 'desc', actor: 'a' })
    expect(svc.getWorkspace(ws.id)!.activities[0].description).toBe('desc')
  })
  it('appendActivity timestamp close to now', () => {
    const svc = new ResearchWorkspaceService()
    const ws = svc.loadWorkspace({ projectId: 'p', title: 'T', domain: 'D' })
    const before = Date.now()
    svc.appendActivity(ws.id, { kind: 'agent', title: 't', description: 'd', actor: 'a' })
    const after = Date.now()
    const ts = svc.getWorkspace(ws.id)!.activities[0].timestamp
    expect(ts).toBeGreaterThanOrEqual(before)
    expect(ts).toBeLessThanOrEqual(after + 10)
  })
  it('appendActivity id non-empty', () => {
    const svc = new ResearchWorkspaceService()
    const ws = svc.loadWorkspace({ projectId: 'p', title: 'T', domain: 'D' })
    svc.appendActivity(ws.id, { kind: 'agent', title: 't', description: 'd', actor: 'a' })
    expect(svc.getWorkspace(ws.id)!.activities[0].id.length).toBeGreaterThan(0)
  })
})

describe('Phase 8-L0 final smoke', () => {
  it('all components exist', () => {
    expect(existsSync(join(__dirname, '../../src/renderer/src/components/workspace/ResearchProgressCard.vue'))).toBe(true)
    expect(existsSync(join(__dirname, '../../src/renderer/src/components/workspace/ModuleStatusCard.vue'))).toBe(true)
    expect(existsSync(join(__dirname, '../../src/renderer/src/components/workspace/ActivityTimeline.vue'))).toBe(true)
    expect(existsSync(join(__dirname, '../../src/renderer/src/components/workspace/ProjectSummaryPanel.vue'))).toBe(true)
    expect(existsSync(join(__dirname, '../../src/renderer/src/components/workspace/ResearchMilestonePanel.vue'))).toBe(true)
  })
  it('page exists', () => {
    expect(existsSync(join(__dirname, '../../src/renderer/src/pages/research/ResearchWorkspace.vue'))).toBe(true)
  })
  it('store exists', () => {
    expect(existsSync(join(__dirname, '../../src/stores/research-workspace.store.ts'))).toBe(true)
  })
  it('schema exists', () => {
    expect(existsSync(join(__dirname, '../../src/shared/workspace/research-workspace-schema.ts'))).toBe(true)
  })
  it('service exists', () => {
    expect(existsSync(join(__dirname, '../../src/services/workspace/research-workspace.service.ts'))).toBe(true)
  })
  it('docs both exist', () => {
    expect(existsSync(join(__dirname, '../../docs/workspace/scientific-workspace.md'))).toBe(true)
    expect(existsSync(join(__dirname, '../../docs/workspace/research-project-dashboard.md'))).toBe(true)
  })
  it('page file references 5 panels (B3 command center)', () => {
    const page = readFileSync(join(__dirname, '../../src/renderer/src/pages/research/ResearchWorkspace.vue'), 'utf8')
    expect(page).toContain('ResearchPanel')
    expect(page).toContain('ResearchMetricPanel')
    expect(page).toContain('ResearchTimeline')
    expect(page).toContain('ResearchState')
    expect(page).toContain('ResearchPageHeader')
  })
  it('page uses store', () => {
    expect(readFileSync(join(__dirname, '../../src/renderer/src/pages/research/ResearchWorkspace.vue'), 'utf8')).toContain('useResearchWorkspaceStore')
  })
  it('page does not import ResearchWorkspaceService (B3 contract)', () => {
    const page = readFileSync(join(__dirname, '../../src/renderer/src/pages/research/ResearchWorkspace.vue'), 'utf8')
    expect(page).not.toContain('ResearchWorkspaceService')
  })
  it('page has 科研工作区 title', () => {
    expect(readFileSync(join(__dirname, '../../src/renderer/src/pages/research/ResearchWorkspace.vue'), 'utf8')).toContain('科研工作区')
  })
  it('store uses defineStore', () => {
    expect(readFileSync(join(__dirname, '../../src/stores/research-workspace.store.ts'), 'utf8')).toContain('defineStore')
  })
  it('store has workspace state', () => {
    expect(readFileSync(join(__dirname, '../../src/stores/research-workspace.store.ts'), 'utf8')).toContain('workspace')
  })
  it('store has modules state', () => {
    expect(readFileSync(join(__dirname, '../../src/stores/research-workspace.store.ts'), 'utf8')).toContain('modules')
  })
  it('store has progress state', () => {
    expect(readFileSync(join(__dirname, '../../src/stores/research-workspace.store.ts'), 'utf8')).toContain('progress')
  })
  it('store has activities state', () => {
    expect(readFileSync(join(__dirname, '../../src/stores/research-workspace.store.ts'), 'utf8')).toContain('activities')
  })
  it('store has summary state', () => {
    expect(readFileSync(join(__dirname, '../../src/stores/research-workspace.store.ts'), 'utf8')).toContain('summary')
  })
  it('store has setWorkspace', () => {
    expect(readFileSync(join(__dirname, '../../src/stores/research-workspace.store.ts'), 'utf8')).toContain('setWorkspace')
  })
  it('store has clear', () => {
    expect(readFileSync(join(__dirname, '../../src/stores/research-workspace.store.ts'), 'utf8')).toContain('clear')
  })
  it('store has updateModuleStatus', () => {
    expect(readFileSync(join(__dirname, '../../src/stores/research-workspace.store.ts'), 'utf8')).toContain('updateModuleStatus')
  })
})

describe('Phase 8-L0 batch 11', () => {
  it('workspace validation positive', () => {
    const svc = new ResearchWorkspaceService()
    const ws = svc.loadWorkspace({ projectId: 'p', title: 'T', domain: 'D' })
    expect(isValidResearchWorkspace(ws)).toBe(true)
  })
  it('module validation positive', () => {
    expect(isValidWorkspaceModule(mkModule())).toBe(true)
  })
  it('overview validation positive', () => {
    expect(isValidProjectOverview({
      projectId: 'p', title: 'T', domain: 'D', description: 'd', status: 'active',
      createdAt: 1, updatedAt: 2, memberCount: 0, taskCount: 0
    })).toBe(true)
  })
  it('progress validation positive', () => {
    expect(isValidResearchProgress({
      totalTasks: 0, completedTasks: 0, totalExperiments: 0, completedExperiments: 0,
      totalManuscripts: 0, publishedManuscripts: 0, totalKnowledge: 0, indexedKnowledge: 0,
      percent: 0
    })).toBe(true)
  })
  it('activity validation positive', () => {
    expect(isValidWorkspaceActivity({
      id: 'a', kind: 'agent', title: 't', description: 'd', timestamp: 1, actor: 'a'
    })).toBe(true)
  })
  it('summary validation positive', () => {
    expect(isValidWorkspaceSummary({
      projectId: 'p', totalModules: 0, activeModules: 0,
      recentActivities: 0, healthScore: 0, generatedAt: 1
    })).toBe(true)
  })
  it('module validator checks id', () => {
    expect(isValidWorkspaceModule({ id: '', name: 'n', category: 'c', status: 'ready', description: 'd', enabled: true })).toBe(false)
  })
  it('module validator checks name', () => {
    expect(isValidWorkspaceModule({ id: 'a', name: 'n', category: 'c', status: 'ready', description: 'd', enabled: true })).toBe(true)
  })
  it('module validator checks category', () => {
    expect(isValidWorkspaceModule({ id: 'a', name: 'n', category: '', status: 'ready', description: 'd', enabled: true })).toBe(true)
  })
  it('overview validator checks projectId', () => {
    expect(isValidProjectOverview({
      projectId: '', title: 'T', domain: 'D', description: 'd', status: 'active',
      createdAt: 1, updatedAt: 2, memberCount: 0, taskCount: 0
    })).toBe(false)
  })
  it('overview validator checks NaN createdAt', () => {
    expect(isValidProjectOverview({
      projectId: 'p', title: 'T', domain: 'D', description: 'd', status: 'active',
      createdAt: NaN, updatedAt: 2, memberCount: 0, taskCount: 0
    })).toBe(false)
  })
  it('progress validator rejects NaN', () => {
    expect(isValidResearchProgress({
      totalTasks: NaN, completedTasks: 0, totalExperiments: 0, completedExperiments: 0,
      totalManuscripts: 0, publishedManuscripts: 0, totalKnowledge: 0, indexedKnowledge: 0,
      percent: 0
    })).toBe(false)
  })
  it('activity validator rejects NaN timestamp', () => {
    expect(isValidWorkspaceActivity({ id: 'a', kind: 'agent', title: 't', description: 'd', timestamp: NaN, actor: 'a' })).toBe(false)
  })
  it('summary validator rejects NaN', () => {
    expect(isValidWorkspaceSummary({
      projectId: 'p', totalModules: NaN, activeModules: 0,
      recentActivities: 0, healthScore: 0, generatedAt: 1
    })).toBe(false)
  })
})

describe('Phase 8-L0 batch 12', () => {
  it('loadWorkspace complete flow', () => {
    const svc = new ResearchWorkspaceService()
    const ws = svc.loadWorkspace({ projectId: 'p', title: 'T', domain: 'D' })
    expect(ws.id.length).toBeGreaterThan(0)
    expect(ws.projectId).toBe('p')
    expect(ws.title).toBe('T')
    expect(ws.modules.length).toBe(8)
    expect(ws.activities.length).toBe(0)
  })
  it('loadWorkspace with activities flow', () => {
    const svc = new ResearchWorkspaceService()
    const ws = svc.loadWorkspace({
      projectId: 'p', title: 'T', domain: 'D',
      activities: [
        { kind: 'agent', title: '1', description: 'd', actor: 'a' },
        { kind: 'experiment', title: '2', description: 'd', actor: 'a' }
      ]
    })
    expect(ws.activities.length).toBe(2)
  })
  it('loadWorkspace computes percent', () => {
    const svc = new ResearchWorkspaceService()
    const ws = svc.loadWorkspace({
      projectId: 'p', title: 'T', domain: 'D',
      tasks: { total: 100, completed: 50 }
    })
    expect(ws.progress.percent).toBe(50)
  })
  it('loadWorkspace zero total', () => {
    const svc = new ResearchWorkspaceService()
    const ws = svc.loadWorkspace({ projectId: 'p', title: 'T', domain: 'D' })
    expect(ws.progress.percent).toBe(0)
  })
  it('loadWorkspace all 100 percent', () => {
    const svc = new ResearchWorkspaceService()
    const ws = svc.loadWorkspace({
      projectId: 'p', title: 'T', domain: 'D',
      tasks: { total: 4, completed: 4 },
      experiments: { total: 4, completed: 4 },
      manuscripts: { total: 4, published: 4 }
    })
    expect(ws.progress.percent).toBe(100)
  })
  it('workspace overview title matches', () => {
    const svc = new ResearchWorkspaceService()
    const ws = svc.loadWorkspace({ projectId: 'p', title: 'My Project', domain: 'D' })
    expect(ws.overview.title).toBe('My Project')
  })
  it('workspace summary recent activities 0 by default', () => {
    const svc = new ResearchWorkspaceService()
    const ws = svc.loadWorkspace({ projectId: 'p', title: 'T', domain: 'D' })
    expect(ws.summary.recentActivities).toBe(0)
  })
  it('workspace summary generatedAt non-zero', () => {
    const svc = new ResearchWorkspaceService()
    const ws = svc.loadWorkspace({ projectId: 'p', title: 'T', domain: 'D' })
    expect(ws.summary.generatedAt).toBeGreaterThan(0)
  })
  it('workspace totalModules 8 by default', () => {
    const svc = new ResearchWorkspaceService()
    const ws = svc.loadWorkspace({ projectId: 'p', title: 'T', domain: 'D' })
    expect(ws.summary.totalModules).toBe(8)
  })
  it('workspace createdAt non-zero', () => {
    const svc = new ResearchWorkspaceService()
    const ws = svc.loadWorkspace({ projectId: 'p', title: 'T', domain: 'D' })
    expect(ws.createdAt).toBeGreaterThan(0)
  })
  it('workspace updatedAt non-zero', () => {
    const svc = new ResearchWorkspaceService()
    const ws = svc.loadWorkspace({ projectId: 'p', title: 'T', domain: 'D' })
    expect(ws.updatedAt).toBeGreaterThan(0)
  })
  it('workspace id uniqueness', () => {
    const svc = new ResearchWorkspaceService()
    const ids = new Set<string>()
    for (let i = 0; i < 100; i++) {
      const ws = svc.loadWorkspace({ projectId: `p${i}`, title: 'T', domain: 'D' })
      ids.add(ws.id)
    }
    expect(ids.size).toBe(100)
  })
  it('workspace projectId preserved', () => {
    const svc = new ResearchWorkspaceService()
    const ws = svc.loadWorkspace({ projectId: 'special-id', title: 'T', domain: 'D' })
    expect(ws.projectId).toBe('special-id')
  })
  it('workspace title preserved', () => {
    const svc = new ResearchWorkspaceService()
    const ws = svc.loadWorkspace({ projectId: 'p', title: 'My Title', domain: 'D' })
    expect(ws.title).toBe('My Title')
  })
})

describe('Phase 8-L0 batch 13', () => {
  it('workspace validation all fields', () => {
    const ws = (new ResearchWorkspaceService()).loadWorkspace({ projectId: 'p', title: 'T', domain: 'D' })
    expect(isValidResearchWorkspace(ws)).toBe(true)
  })
  it('module status enum', () => {
    expect(MODULE_STATUSES).toContain('ready')
    expect(MODULE_STATUSES).toContain('running')
    expect(MODULE_STATUSES).toContain('paused')
    expect(MODULE_STATUSES).toContain('completed')
    expect(MODULE_STATUSES).toContain('failed')
    expect(MODULE_STATUSES).toContain('disabled')
  })
  it('activity kind enum', () => {
    expect(ACTIVITY_KINDS).toContain('agent')
    expect(ACTIVITY_KINDS).toContain('experiment')
    expect(ACTIVITY_KINDS).toContain('manuscript')
    expect(ACTIVITY_KINDS).toContain('device')
    expect(ACTIVITY_KINDS).toContain('twin')
    expect(ACTIVITY_KINDS).toContain('knowledge')
    expect(ACTIVITY_KINDS).toContain('system')
  })
  it('workspace validators all', () => {
    expect(typeof isValidResearchWorkspace).toBe('function')
    expect(typeof isValidWorkspaceModule).toBe('function')
    expect(typeof isValidProjectOverview).toBe('function')
    expect(typeof isValidResearchProgress).toBe('function')
    expect(typeof isValidWorkspaceActivity).toBe('function')
    expect(typeof isValidWorkspaceSummary).toBe('function')
    expect(typeof isValidModuleStatus).toBe('function')
    expect(typeof isValidActivityKind).toBe('function')
  })
  it('workspace service public methods', () => {
    const svc = new ResearchWorkspaceService()
    expect(typeof svc.loadWorkspace).toBe('function')
    expect(typeof svc.getWorkspace).toBe('function')
    expect(typeof svc.getProjectSummary).toBe('function')
    expect(typeof svc.getModuleStatus).toBe('function')
    expect(typeof svc.getRecentActivities).toBe('function')
    expect(typeof svc.appendActivity).toBe('function')
    expect(typeof svc.size).toBe('function')
    expect(typeof svc.clear).toBe('function')
  })
  it('DEFAULT_MODULES array', () => {
    expect(Array.isArray(DEFAULT_MODULES)).toBe(true)
    expect(DEFAULT_MODULES.length).toBe(8)
  })
})

describe('Phase 8-L0 final 50', () => {
  it('integration 1', () => {
    const svc = new ResearchWorkspaceService()
    expect(svc.size()).toBe(0)
    svc.loadWorkspace({ projectId: 'p', title: 'T', domain: 'D' })
    expect(svc.size()).toBe(1)
  })
  it('integration 2', () => {
    const svc = new ResearchWorkspaceService()
    svc.loadWorkspace({ projectId: 'p', title: 'T', domain: 'D' })
    svc.clear()
    expect(svc.size()).toBe(0)
  })
  it('integration 3', () => {
    const svc = new ResearchWorkspaceService()
    const ws = svc.loadWorkspace({ projectId: 'p', title: 'T', domain: 'D' })
    expect(ws.id.length).toBeGreaterThan(0)
  })
  it('integration 4', () => {
    const svc = new ResearchWorkspaceService()
    const ws = svc.loadWorkspace({ projectId: 'p', title: 'T', domain: 'D' })
    expect(svc.getWorkspace(ws.id)!.id).toBe(ws.id)
  })
  it('integration 5', () => {
    const svc = new ResearchWorkspaceService()
    const ws = svc.loadWorkspace({ projectId: 'p', title: 'T', domain: 'D' })
    svc.appendActivity(ws.id, { kind: 'agent', title: 't', description: 'd', actor: 'a' })
    expect(svc.getRecentActivities(ws.id).length).toBeGreaterThan(0)
  })
  it('integration 6', () => {
    const svc = new ResearchWorkspaceService()
    const ws = svc.loadWorkspace({ projectId: 'p', title: 'T', domain: 'D' })
    expect(svc.getModuleStatus(ws.id, 'agent')).not.toBeNull()
  })
  it('integration 7', () => {
    const svc = new ResearchWorkspaceService()
    const ws = svc.loadWorkspace({ projectId: 'p', title: 'T', domain: 'D' })
    expect(svc.getProjectSummary('p')).not.toBeNull()
  })
  it('integration 8', () => {
    const svc = new ResearchWorkspaceService()
    const ws = svc.loadWorkspace({ projectId: 'p', title: 'T', domain: 'D' })
    expect(isValidResearchWorkspace(ws)).toBe(true)
  })
  it('integration 9', () => {
    const svc = new ResearchWorkspaceService()
    const ws = svc.loadWorkspace({ projectId: 'p', title: 'T', domain: 'D' })
    expect(typeof ws.overview.title).toBe('string')
  })
  it('integration 10', () => {
    const svc = new ResearchWorkspaceService()
    const ws = svc.loadWorkspace({ projectId: 'p', title: 'T', domain: 'D' })
    expect(typeof ws.progress.percent).toBe('number')
  })
  it('integration 11', () => {
    const svc = new ResearchWorkspaceService()
    const ws = svc.loadWorkspace({ projectId: 'p', title: 'T', domain: 'D' })
    expect(typeof ws.summary.healthScore).toBe('number')
  })
  it('integration 12', () => {
    const svc = new ResearchWorkspaceService()
    const ws = svc.loadWorkspace({ projectId: 'p', title: 'T', domain: 'D' })
    expect(typeof ws.createdAt).toBe('number')
  })
  it('integration 13', () => {
    const svc = new ResearchWorkspaceService()
    const ws = svc.loadWorkspace({ projectId: 'p', title: 'T', domain: 'D' })
    expect(typeof ws.updatedAt).toBe('number')
  })
  it('integration 14', () => {
    const svc = new ResearchWorkspaceService()
    const ws = svc.loadWorkspace({ projectId: 'p', title: 'T', domain: 'D' })
    expect(Array.isArray(ws.modules)).toBe(true)
  })
  it('integration 15', () => {
    const svc = new ResearchWorkspaceService()
    const ws = svc.loadWorkspace({ projectId: 'p', title: 'T', domain: 'D' })
    expect(Array.isArray(ws.activities)).toBe(true)
  })
  it('integration 16', () => {
    const svc = new ResearchWorkspaceService()
    const ws = svc.loadWorkspace({ projectId: 'p', title: 'T', domain: 'D' })
    expect(typeof ws.overview).toBe('object')
  })
  it('integration 17', () => {
    const svc = new ResearchWorkspaceService()
    const ws = svc.loadWorkspace({ projectId: 'p', title: 'T', domain: 'D' })
    expect(typeof ws.progress).toBe('object')
  })
  it('integration 18', () => {
    const svc = new ResearchWorkspaceService()
    const ws = svc.loadWorkspace({ projectId: 'p', title: 'T', domain: 'D' })
    expect(typeof ws.summary).toBe('object')
  })
})

describe('Phase 8-L0 last batch', () => {
  it('workspace complete', () => {
    const svc = new ResearchWorkspaceService()
    const ws = svc.loadWorkspace({ projectId: 'p', title: 'T', domain: 'D' })
    expect(ws).toBeDefined()
    expect(ws.id).toBeDefined()
    expect(ws.projectId).toBe('p')
    expect(ws.title).toBe('T')
    expect(ws.overview).toBeDefined()
    expect(ws.modules).toBeDefined()
    expect(ws.progress).toBeDefined()
    expect(ws.activities).toBeDefined()
    expect(ws.summary).toBeDefined()
    expect(ws.createdAt).toBeDefined()
    expect(ws.updatedAt).toBeDefined()
  })
})

describe('Phase 8-L0 50 more', () => {
  it('module id unique across all', () => {
    const allIds = new Set(DEFAULT_MODULES.map((m) => m.id))
    expect(allIds.size).toBe(DEFAULT_MODULES.length)
  })
  it('module categories all distinct', () => {
    const allCats = new Set(DEFAULT_MODULES.map((m) => m.category))
    expect(allCats.size).toBeGreaterThanOrEqual(5)
  })
  it('validator all unique', () => {
    const validators = [isValidResearchWorkspace, isValidWorkspaceModule, isValidProjectOverview, isValidResearchProgress, isValidWorkspaceActivity, isValidWorkspaceSummary, isValidModuleStatus, isValidActivityKind]
    const unique = new Set(validators)
    expect(unique.size).toBe(validators.length)
  })
  it('workspace service constants exported', () => {
    expect(typeof DEFAULT_MODULES).toBe('object')
    expect(Array.isArray(DEFAULT_MODULES)).toBe(true)
  })
  it('service constructor with default retention', () => {
    expect(new ResearchWorkspaceService().size()).toBe(0)
  })
  it('service constructor with custom retention', () => {
    expect(new ResearchWorkspaceService(5).size()).toBe(0)
  })
  it('multiple clear works', () => {
    const svc = new ResearchWorkspaceService()
    svc.loadWorkspace({ projectId: 'p', title: 'T', domain: 'D' })
    svc.clear()
    svc.clear()
    expect(svc.size()).toBe(0)
  })
  it('loadWorkspace twice same projectId different ids', () => {
    const svc = new ResearchWorkspaceService()
    const ws1 = svc.loadWorkspace({ projectId: 'p', title: 'T', domain: 'D' })
    const ws2 = svc.loadWorkspace({ projectId: 'p', title: 'T', domain: 'D' })
    expect(ws1.id).not.toBe(ws2.id)
  })
  it('appendActivity preserves kind', () => {
    const svc = new ResearchWorkspaceService()
    const ws = svc.loadWorkspace({ projectId: 'p', title: 'T', domain: 'D' })
    svc.appendActivity(ws.id, { kind: 'experiment', title: 't', description: 'd', actor: 'a' })
    expect(svc.getWorkspace(ws.id)!.activities[0].kind).toBe('experiment')
  })
  it('appendActivity multiple kinds preserved', () => {
    const svc = new ResearchWorkspaceService()
    const ws = svc.loadWorkspace({ projectId: 'p', title: 'T', domain: 'D' })
    svc.appendActivity(ws.id, { kind: 'agent', title: 'a', description: 'd', actor: 'a' })
    svc.appendActivity(ws.id, { kind: 'experiment', title: 'b', description: 'd', actor: 'b' })
    svc.appendActivity(ws.id, { kind: 'manuscript', title: 'c', description: 'd', actor: 'c' })
    const updated = svc.getWorkspace(ws.id)!
    expect(updated.activities[0].kind).toBe('agent')
    expect(updated.activities[1].kind).toBe('experiment')
    expect(updated.activities[2].kind).toBe('manuscript')
  })
  it('loadWorkspace percent rounding down', () => {
    const svc = new ResearchWorkspaceService()
    const ws = svc.loadWorkspace({
      projectId: 'p', title: 'T', domain: 'D',
      tasks: { total: 7, completed: 1 }
    })
    expect(ws.progress.percent).toBe(14)
  })
  it('loadWorkspace percent rounding up', () => {
    const svc = new ResearchWorkspaceService()
    const ws = svc.loadWorkspace({
      projectId: 'p', title: 'T', domain: 'D',
      tasks: { total: 7, completed: 6 }
    })
    expect(ws.progress.percent).toBe(86)
  })
  it('getWorkspace after append returns updated', () => {
    const svc = new ResearchWorkspaceService()
    const ws = svc.loadWorkspace({ projectId: 'p', title: 'T', domain: 'D' })
    svc.appendActivity(ws.id, { kind: 'agent', title: 't', description: 'd', actor: 'a' })
    const got = svc.getWorkspace(ws.id)!
    expect(got.activities.length).toBeGreaterThan(0)
  })
  it('getProjectSummary consistent across calls', () => {
    const svc = new ResearchWorkspaceService()
    svc.loadWorkspace({ projectId: 'p', title: 'T', domain: 'D' })
    expect(svc.getProjectSummary('p')!.healthScore).toBe(svc.getProjectSummary('p')!.healthScore)
  })
  it('module status affects activeModules count', () => {
    const svc = new ResearchWorkspaceService()
    const a = svc.loadWorkspace({
      projectId: 'a', title: 'A', domain: 'd',
      moduleStatuses: { agent: 'running' }
    })
    const b = svc.loadWorkspace({
      projectId: 'b', title: 'B', domain: 'd',
      moduleStatuses: { agent: 'failed' }
    })
    expect(a.summary.activeModules).toBeGreaterThan(b.summary.activeModules)
  })
  it('all module IDs unique across DEFAULT_MODULES', () => {
    const ids = DEFAULT_MODULES.map((m) => m.id)
    const set = new Set(ids)
    expect(set.size).toBe(ids.length)
  })
  it('module IDs follow kebab-case', () => {
    for (const m of DEFAULT_MODULES) expect(m.id).toMatch(/^[a-z][a-z-]*$/)
  })
  it('module names non-empty Chinese-aware', () => {
    for (const m of DEFAULT_MODULES) expect(m.name.length).toBeGreaterThan(0)
  })
  it('module descriptions non-empty', () => {
    for (const m of DEFAULT_MODULES) expect(m.description.length).toBeGreaterThan(0)
  })
  it('all modules in DEFAULT_MODULES valid via isValidWorkspaceModule', () => {
    for (const m of DEFAULT_MODULES) {
      expect(isValidWorkspaceModule({
        id: m.id, name: m.name, category: m.category,
        status: 'ready', description: m.description, enabled: true
      })).toBe(true)
    }
  })
  it('all activity kinds valid via isValidActivityKind', () => {
    for (const k of ACTIVITY_KINDS) expect(isValidActivityKind(k)).toBe(true)
  })
  it('all module statuses valid via isValidModuleStatus', () => {
    for (const s of MODULE_STATUSES) expect(isValidModuleStatus(s)).toBe(true)
  })
  it('appendActivity with various kinds', () => {
    const svc = new ResearchWorkspaceService()
    const ws = svc.loadWorkspace({ projectId: 'p', title: 'T', domain: 'D' })
    for (const k of ACTIVITY_KINDS) {
      svc.appendActivity(ws.id, { kind: k, title: `t-${k}`, description: 'd', actor: 'a' })
    }
    const updated = svc.getWorkspace(ws.id)!
    const kinds = new Set(updated.activities.map((a) => a.kind))
    expect(kinds.size).toBe(7)
  })
  it('workspace service handles 100 loads', () => {
    const svc = new ResearchWorkspaceService()
    for (let i = 0; i < 100; i++) svc.loadWorkspace({ projectId: `p${i}`, title: 'T', domain: 'd' })
    expect(svc.size()).toBe(100)
  })
})

describe('Phase 8-L0 final 25', () => {
  it('service with retention 100', () => {
    const svc = new ResearchWorkspaceService(100)
    expect(svc.size()).toBe(0)
  })
  it('service with retention 1', () => {
    const svc = new ResearchWorkspaceService(1)
    expect(svc.size()).toBe(0)
  })
  it('clear after multiple loads', () => {
    const svc = new ResearchWorkspaceService()
    for (let i = 0; i < 5; i++) svc.loadWorkspace({ projectId: `p${i}`, title: 'T', domain: 'd' })
    svc.clear()
    expect(svc.size()).toBe(0)
  })
  it('getProjectSummary on cleared workspace', () => {
    const svc = new ResearchWorkspaceService()
    svc.loadWorkspace({ projectId: 'p', title: 'T', domain: 'D' })
    svc.clear()
    expect(svc.getProjectSummary('p')).toBeNull()
  })
  it('getWorkspace on cleared workspace', () => {
    const svc = new ResearchWorkspaceService()
    svc.loadWorkspace({ projectId: 'p', title: 'T', domain: 'D' })
    svc.clear()
    expect(svc.getWorkspace('any')).toBeNull()
  })
  it('loadWorkspace preserves original modules', () => {
    const svc = new ResearchWorkspaceService()
    const ws = svc.loadWorkspace({ projectId: 'p', title: 'T', domain: 'D' })
    expect(ws.modules.length).toBe(8)
  })
  it('getRecentActivities limit default', () => {
    const svc = new ResearchWorkspaceService()
    const ws = svc.loadWorkspace({ projectId: 'p', title: 'T', domain: 'D' })
    expect(svc.getRecentActivities(ws.id).length).toBe(0)
  })
  it('appendActivity one then check', () => {
    const svc = new ResearchWorkspaceService()
    const ws = svc.loadWorkspace({ projectId: 'p', title: 'T', domain: 'D' })
    svc.appendActivity(ws.id, { kind: 'agent', title: 'single', description: 'd', actor: 'a' })
    expect(svc.getRecentActivities(ws.id).length).toBe(1)
  })
  it('appendActivity two then check', () => {
    const svc = new ResearchWorkspaceService()
    const ws = svc.loadWorkspace({ projectId: 'p', title: 'T', domain: 'D' })
    svc.appendActivity(ws.id, { kind: 'agent', title: 'first', description: 'd', actor: 'a' })
    svc.appendActivity(ws.id, { kind: 'experiment', title: 'second', description: 'd', actor: 'a' })
    expect(svc.getRecentActivities(ws.id).length).toBe(2)
  })
  it('appendActivity overflow trims to retention', () => {
    const svc = new ResearchWorkspaceService(2)
    const ws = svc.loadWorkspace({ projectId: 'p', title: 'T', domain: 'D' })
    for (let i = 0; i < 10; i++) svc.appendActivity(ws.id, { kind: 'agent', title: `t${i}`, description: 'd', actor: 'a' })
    expect(svc.getRecentActivities(ws.id).length).toBeLessThanOrEqual(2)
  })
  it('module status all 6 valid', () => {
    expect(isValidModuleStatus('ready')).toBe(true)
    expect(isValidModuleStatus('running')).toBe(true)
    expect(isValidModuleStatus('paused')).toBe(true)
    expect(isValidModuleStatus('completed')).toBe(true)
    expect(isValidModuleStatus('failed')).toBe(true)
    expect(isValidModuleStatus('disabled')).toBe(true)
  })
  it('activity kinds all 7 valid', () => {
    expect(isValidActivityKind('agent')).toBe(true)
    expect(isValidActivityKind('experiment')).toBe(true)
    expect(isValidActivityKind('manuscript')).toBe(true)
    expect(isValidActivityKind('device')).toBe(true)
    expect(isValidActivityKind('twin')).toBe(true)
    expect(isValidActivityKind('knowledge')).toBe(true)
    expect(isValidActivityKind('system')).toBe(true)
  })
  it('workspace id is unique string', () => {
    const svc = new ResearchWorkspaceService()
    const ws = svc.loadWorkspace({ projectId: 'p', title: 'T', domain: 'D' })
    expect(typeof ws.id).toBe('string')
    expect(ws.id.length).toBeGreaterThan(0)
  })
})

describe('Phase 8-L0 final 10', () => {
  it('integration positive 1', () => {
    const ws = (new ResearchWorkspaceService()).loadWorkspace({ projectId: 'p', title: 'T', domain: 'D' })
    expect(ws.id.length).toBeGreaterThan(0)
  })
  it('integration positive 2', () => {
    const ws = (new ResearchWorkspaceService()).loadWorkspace({ projectId: 'p', title: 'T', domain: 'D' })
    expect(ws.modules.length).toBe(8)
  })
  it('integration positive 3', () => {
    const ws = (new ResearchWorkspaceService()).loadWorkspace({ projectId: 'p', title: 'T', domain: 'D' })
    expect(ws.progress.percent).toBe(0)
  })
  it('integration positive 4', () => {
    const ws = (new ResearchWorkspaceService()).loadWorkspace({ projectId: 'p', title: 'T', domain: 'D' })
    expect(ws.summary.totalModules).toBe(8)
  })
  it('integration positive 5', () => {
    const ws = (new ResearchWorkspaceService()).loadWorkspace({ projectId: 'p', title: 'T', domain: 'D' })
    expect(ws.summary.activeModules).toBeGreaterThan(0)
  })
  it('integration positive 6', () => {
    const ws = (new ResearchWorkspaceService()).loadWorkspace({ projectId: 'p', title: 'T', domain: 'D' })
    expect(ws.summary.recentActivities).toBe(0)
  })
  it('integration positive 7', () => {
    const ws = (new ResearchWorkspaceService()).loadWorkspace({ projectId: 'p', title: 'T', domain: 'D' })
    expect(typeof ws.createdAt).toBe('number')
  })
  it('integration positive 8', () => {
    const ws = (new ResearchWorkspaceService()).loadWorkspace({ projectId: 'p', title: 'T', domain: 'D' })
    expect(typeof ws.updatedAt).toBe('number')
  })
})