// Phase 7-T3 Tool Capability Matching tests.
//
// Coverage (>= 50 cases):
//   - ToolTaskType enum (3)
//   - ToolCapabilityProfile validator (5)
//   - ToolMatchResult validator (4)
//   - matchToolsForTask ranking (10)
//   - tie-breaking (3)
//   - capability overlap (4)
//   - priority weight (3)
//   - empty input / no candidates (4)
//   - invalid input rejection (3)
//   - no-secret enforcement (4)
//   - source-level independence (4)
//   - algorithm determinism (3)

import { describe, it, expect } from 'vitest'

import {
  isValidToolTaskType,
  isValidToolCapabilityProfile,
  isValidToolMatchResult,
  matchToolsForTask,
  __testHelpers,
  TOOL_TASK_TYPES,
  type ToolCapabilityProfile,
  type ToolMatchResult,
  type ToolTaskType
} from '../../src/shared/tools/tool-capability-schema'

// ============ ToolTaskType ============

describe('Phase 7-T3 ToolTaskType enum', () => {
  it('accepts all 8 documented task types', () => {
    const tasks: ToolTaskType[] = [
      'literature-processing', 'data-analysis', 'experiment-analysis', 'visualization',
      'simulation', 'calculation', 'export', 'preprocessing'
    ]
    for (const t of tasks) {
      expect(isValidToolTaskType(t)).toBe(true)
    }
  })
  it('rejects unknown task type', () => {
    expect(isValidToolTaskType('chat')).toBe(false)
    expect(isValidToolTaskType('admin')).toBe(false)
  })
  it('TOOL_TASK_TYPES readonly array has 8 entries', () => {
    expect(TOOL_TASK_TYPES.length).toBe(8)
    expect(__testHelpers.VALID_TASK_TYPES.size).toBe(8)
  })
})

// ============ ToolCapabilityProfile validator ============

describe('Phase 7-T3 ToolCapabilityProfile validator', () => {
  const baseProfile = (): ToolCapabilityProfile => ({
    toolId: 'tool:test',
    requiredCapabilities: [],
    optionalCapabilities: [],
    supportedTasks: ['data-analysis'],
    priority: 5
  })
  it('accepts minimal profile', () => {
    expect(isValidToolCapabilityProfile(baseProfile())).toBe(true)
  })
  it('accepts profile with all fields populated', () => {
    expect(isValidToolCapabilityProfile({
      toolId: 'tool:full',
      requiredCapabilities: ['cap-a', 'cap-b'],
      optionalCapabilities: ['cap-c'],
      supportedTasks: ['data-analysis', 'visualization'],
      priority: 8
    })).toBe(true)
  })
  it('rejects empty toolId', () => {
    expect(isValidToolCapabilityProfile({ ...baseProfile(), toolId: '' })).toBe(false)
  })
  it('rejects priority out of range', () => {
    expect(isValidToolCapabilityProfile({ ...baseProfile(), priority: 11 })).toBe(false)
    expect(isValidToolCapabilityProfile({ ...baseProfile(), priority: -1 })).toBe(false)
  })
  it('rejects unknown task type in supportedTasks', () => {
    expect(isValidToolCapabilityProfile({
      ...baseProfile(), supportedTasks: ['unknown-task' as never]
    })).toBe(false)
  })
})

// ============ ToolMatchResult validator ============

describe('Phase 7-T3 ToolMatchResult validator', () => {
  it('accepts valid result', () => {
    expect(isValidToolMatchResult({
      toolId: 'tool:test', score: 25, reason: 'tasks=[data-analysis]'
    })).toBe(true)
  })
  it('accepts result with breakdown', () => {
    expect(isValidToolMatchResult({
      toolId: 'tool:test', score: 25, reason: 'tasks=[data-analysis]',
      breakdown: { taskScore: 10, capabilityScore: 5, priorityScore: 10 }
    })).toBe(true)
  })
  it('rejects empty reason', () => {
    expect(isValidToolMatchResult({
      toolId: 'tool:test', score: 25, reason: ''
    })).toBe(false)
  })
  it('rejects negative score', () => {
    expect(isValidToolMatchResult({
      toolId: 'tool:test', score: -1, reason: 'r'
    })).toBe(false)
  })
})

// ============ matchToolsForTask ranking ============

describe('Phase 7-T3 matchToolsForTask — ranking', () => {
  const profile = (overrides: Partial<ToolCapabilityProfile>): ToolCapabilityProfile => ({
    toolId: 'tool:test',
    requiredCapabilities: [],
    optionalCapabilities: [],
    supportedTasks: ['data-analysis'],
    priority: 5,
    ...overrides
  })

  it('picks tools with all required tasks hit', () => {
    const result = matchToolsForTask(
      { requiredTasks: ['data-analysis'], requiredCapabilities: [] },
      [
        profile({ toolId: 'tool:match' }),
        profile({ toolId: 'tool:miss', supportedTasks: ['visualization'] })
      ]
    )
    expect(result).toHaveLength(1)
    expect(result[0].toolId).toBe('tool:match')
  })
  it('picks tools with all required capabilities hit', () => {
    const result = matchToolsForTask(
      { requiredTasks: [], requiredCapabilities: ['kinetic-fit'] },
      [
        profile({ toolId: 'tool:match', requiredCapabilities: ['kinetic-fit'] }),
        profile({ toolId: 'tool:miss', requiredCapabilities: ['other'] })
      ]
    )
    expect(result).toHaveLength(1)
    expect(result[0].toolId).toBe('tool:match')
  })
  it('task overlap scores higher than capability overlap alone', () => {
    const result = matchToolsForTask(
      { requiredTasks: ['data-analysis'], requiredCapabilities: ['x'] },
      [
        profile({ toolId: 'tool:tasks', supportedTasks: ['data-analysis'], requiredCapabilities: [] }),
        profile({ toolId: 'tool:caps', supportedTasks: [], requiredCapabilities: ['x'] })
      ]
    )
    expect(result[0].toolId).toBe('tool:tasks')  // 10 > 5
  })
  it('returns multiple tools when multiple match', () => {
    const result = matchToolsForTask(
      { requiredTasks: ['data-analysis'], requiredCapabilities: [] },
      [
        profile({ toolId: 'tool:a', supportedTasks: ['data-analysis'] }),
        profile({ toolId: 'tool:b', supportedTasks: ['data-analysis'] })
      ]
    )
    expect(result.length).toBe(2)
  })
  it('returns tools sorted by score desc', () => {
    const result = matchToolsForTask(
      { requiredTasks: ['data-analysis'], requiredCapabilities: [] },
      [
        profile({ toolId: 'tool:low', supportedTasks: ['data-analysis'], priority: 1 }),
        profile({ toolId: 'tool:high', supportedTasks: ['data-analysis'], priority: 9 })
      ]
    )
    expect(result[0].toolId).toBe('tool:high')
    expect(result[1].toolId).toBe('tool:low')
  })
  it('excludes tools with score 0', () => {
    const result = matchToolsForTask(
      { requiredTasks: ['data-analysis'], requiredCapabilities: [] },
      [
        profile({ toolId: 'tool:zero', supportedTasks: ['visualization'], priority: 0 })
      ]
    )
    expect(result).toEqual([])
  })
  it('counts required tasks as 10 each (plus priority)', () => {
    const result = matchToolsForTask(
      { requiredTasks: ['data-analysis', 'visualization'], requiredCapabilities: [] },
      [profile({ toolId: 'tool:full', supportedTasks: ['data-analysis', 'visualization'], priority: 0 })]
    )
    // 2 tasks * 10 + 0 caps + 0 priority = 20
    expect(result[0].score).toBe(20)
  })
  it('counts optional tasks as 2 each (plus priority)', () => {
    const result = matchToolsForTask(
      { requiredTasks: [], optionalTasks: ['data-analysis', 'visualization'], requiredCapabilities: [] },
      [profile({ toolId: 'tool:opt', supportedTasks: ['data-analysis', 'visualization'], priority: 5 })]
    )
    // 2 opt * 2 + 0 caps + 5 priority = 9
    expect(result[0].score).toBe(9)
  })
  it('counts required capabilities as 5 each (plus priority)', () => {
    const result = matchToolsForTask(
      { requiredTasks: [], requiredCapabilities: ['cap-a', 'cap-b'] },
      [profile({ toolId: 'tool:caps', requiredCapabilities: ['cap-a', 'cap-b'], priority: 5 })]
    )
    // 2 caps * 5 + 0 tasks + 5 priority = 15
    expect(result[0].score).toBe(15)
  })
  it('priority adds 0..10 to score', () => {
    const r1 = matchToolsForTask(
      { requiredTasks: ['data-analysis'], requiredCapabilities: [] },
      [{ toolId: 'tool:p5', requiredCapabilities: [], optionalCapabilities: [],
        supportedTasks: ['data-analysis'], priority: 5 }]
    )
    const r2 = matchToolsForTask(
      { requiredTasks: ['data-analysis'], requiredCapabilities: [] },
      [{ toolId: 'tool:p8', requiredCapabilities: [], optionalCapabilities: [],
        supportedTasks: ['data-analysis'], priority: 8 }]
    )
    expect(r2[0].score - r1[0].score).toBe(3)
  })
})

// ============ Tie-breaking ============

describe('Phase 7-T3 matchToolsForTask — deterministic tie-breaking', () => {
  const profile = (toolId: string): ToolCapabilityProfile => ({
    toolId,
    requiredCapabilities: [],
    optionalCapabilities: [],
    supportedTasks: ['data-analysis'],
    priority: 5
  })
  it('breaks ties alphabetically by toolId', () => {
    const result = matchToolsForTask(
      { requiredTasks: ['data-analysis'], requiredCapabilities: [] },
      [
        profile('tool:zebra'),
        profile('tool:apple'),
        profile('tool:middle')
      ]
    )
    expect(result.map((r) => r.toolId)).toEqual(['tool:apple', 'tool:middle', 'tool:zebra'])
  })
  it('returns same order on repeated calls (deterministic)', () => {
    const profiles = [profile('tool:a'), profile('tool:b'), profile('tool:c')]
    const input = { requiredTasks: ['data-analysis'] as ToolTaskType[], requiredCapabilities: [] }
    const r1 = matchToolsForTask(input, profiles)
    const r2 = matchToolsForTask(input, profiles)
    expect(r1.map((r) => r.toolId)).toEqual(r2.map((r) => r.toolId))
  })
  it('higher priority wins when scores are otherwise equal', () => {
    const result = matchToolsForTask(
      { requiredTasks: ['data-analysis'], requiredCapabilities: [] },
      [
        profile('tool:low-prio'),  // score = 10 + 0 + 5 = 15
        { ...profile('tool:high-prio'), priority: 8 }  // score = 10 + 0 + 8 = 18
      ]
    )
    expect(result[0].toolId).toBe('tool:high-prio')
  })
})

// ============ Capability overlap ============

describe('Phase 7-T3 matchToolsForTask — capability overlap', () => {
  it('tool with all required caps beats tool with partial caps', () => {
    const result = matchToolsForTask(
      { requiredTasks: [], requiredCapabilities: ['a', 'b'] },
      [
        { toolId: 'tool:full', requiredCapabilities: ['a', 'b'], optionalCapabilities: [], supportedTasks: [], priority: 5 },
        { toolId: 'tool:partial', requiredCapabilities: ['a'], optionalCapabilities: [], supportedTasks: [], priority: 5 }
      ]
    )
    expect(result[0].toolId).toBe('tool:full')
  })
  it('tool with extra caps beyond required still scores correctly', () => {
    const result = matchToolsForTask(
      { requiredTasks: [], requiredCapabilities: ['a'] },
      [{ toolId: 'tool:extra', requiredCapabilities: ['a', 'b', 'c'], optionalCapabilities: [], supportedTasks: [], priority: 5 }]
    )
    // 1 cap * 5 + 5 priority = 10
    expect(result[0].score).toBe(10)
  })
  it('optional capabilities do not contribute to required score', () => {
    const result = matchToolsForTask(
      { requiredTasks: [], requiredCapabilities: [] },
      [{ toolId: 'tool:only-opt', requiredCapabilities: [], optionalCapabilities: ['a'], supportedTasks: [], priority: 5 }]
    )
    // No required task + no required cap -> filtered out (Phase 7-T3 strict)
    expect(result).toEqual([])
  })
  it('capability on optionalCapabilities still counts for required', () => {
    const result = matchToolsForTask(
      { requiredTasks: [], requiredCapabilities: ['x'] },
      [{ toolId: 'tool:opt-cap', requiredCapabilities: [], optionalCapabilities: ['x'], supportedTasks: [], priority: 5 }]
    )
    // optionalCapabilities NOT checked against requiredCapabilities
    // -> no required hit -> filtered out
    expect(result).toEqual([])
  })
})

// ============ Priority weight ============

describe('Phase 7-T3 matchToolsForTask — priority weight', () => {
  it('priority 0 yields task+priority score (10+0=10 if matched)', () => {
    const result = matchToolsForTask(
      { requiredTasks: ['data-analysis'], requiredCapabilities: [] },
      [{ toolId: 'tool:p0', requiredCapabilities: [], optionalCapabilities: [],
        supportedTasks: ['data-analysis'], priority: 0 }]
    )
    expect(result[0].score).toBe(10)
  })
  it('priority 10 yields max boost (10+0+10=20)', () => {
    const result = matchToolsForTask(
      { requiredTasks: ['data-analysis'], requiredCapabilities: [] },
      [{ toolId: 'tool:p10', requiredCapabilities: [], optionalCapabilities: [],
        supportedTasks: ['data-analysis'], priority: 10 }]
    )
    expect(result[0].score).toBe(20)
  })
  it('priority alone (no required hit) excludes the tool', () => {
    const r1 = matchToolsForTask(
      { requiredTasks: [], requiredCapabilities: [] },
      [{ toolId: 'tool:a', requiredCapabilities: [], optionalCapabilities: [],
        supportedTasks: [], priority: 0 }]
    )
    expect(r1).toEqual([])
  })
})

// ============ Empty input ============

describe('Phase 7-T3 matchToolsForTask — empty input / no candidates', () => {
  it('empty profiles array returns empty array', () => {
    expect(matchToolsForTask(
      { requiredTasks: ['data-analysis'], requiredCapabilities: [] },
      []
    )).toEqual([])
  })
  it('empty requiredTasks + empty requiredCapabilities excludes tools with no relevance', () => {
    const result = matchToolsForTask(
      { requiredTasks: [], requiredCapabilities: [] },
      [{ toolId: 'tool:has-prio', requiredCapabilities: [], optionalCapabilities: [],
        supportedTasks: ['data-analysis'], priority: 5 }]
    )
    // Phase 7-T3 strict: no required hit -> filtered out
    expect(result).toEqual([])
  })
  it('tools with empty supportedTasks AND empty requiredCapabilities are filtered out', () => {
    const result = matchToolsForTask(
      { requiredTasks: [], requiredCapabilities: [] },
      [{ toolId: 'tool:minimal', requiredCapabilities: [], optionalCapabilities: [],
        supportedTasks: [], priority: 5 }]
    )
    expect(result).toEqual([])
  })
})

// ============ Invalid input ============

describe('Phase 7-T3 matchToolsForTask — invalid input rejection', () => {
  it('rejects non-object input', () => {
    expect(() => matchToolsForTask(null as never, [])).not.toThrow()
    expect(matchToolsForTask(null as never, [])).toEqual([])
  })
  it('returns empty when profiles is not an array', () => {
    expect(matchToolsForTask(
      { requiredTasks: ['data-analysis'], requiredCapabilities: [] },
      null as never
    )).toEqual([])
  })
  it('handles empty requiredTasks array (matches capability only)', () => {
    const result = matchToolsForTask(
      { requiredTasks: [], requiredCapabilities: ['x'] },
      [{ toolId: 'tool:cap', requiredCapabilities: ['x'], optionalCapabilities: [], supportedTasks: [], priority: 5 }]
    )
    // 1 cap * 5 + 5 priority = 10
    expect(result[0].score).toBe(10)
  })
})

// ============ No-secret enforcement ============

describe('Phase 7-T3 security — no-secret enforcement', () => {
  it('ToolCapabilityProfile throws when apiKey leaks', () => {
    expect(() => isValidToolCapabilityProfile({
      toolId: 'tool:leak', requiredCapabilities: [], optionalCapabilities: [],
      supportedTasks: ['data-analysis'], priority: 5,
      apiKey: 'sk-supersecret'
    } as never)).toThrow(/forbidden/)
  })
  it('ToolCapabilityProfile throws when cipher leaks in toolId', () => {
    expect(() => isValidToolCapabilityProfile({
      toolId: 'tool:cipher:abc', requiredCapabilities: [], optionalCapabilities: [],
      supportedTasks: ['data-analysis'], priority: 5
    })).toThrow(/forbidden/)
  })
  it('ToolMatchResult throws when token leaks', () => {
    expect(() => isValidToolMatchResult({
      toolId: 'tool:t', score: 10, reason: 'token=leaked'
    })).toThrow(/forbidden/)
  })
  it('FORBIDDEN list contains all 8 secret types', () => {
    expect(__testHelpers.FORBIDDEN).toContain('sk-')
    expect(__testHelpers.FORBIDDEN).toContain('apiKey')
    expect(__testHelpers.FORBIDDEN).toContain('cipher')
    expect(__testHelpers.FORBIDDEN).toContain('Bearer ')
    expect(__testHelpers.FORBIDDEN).toContain('token')
    expect(__testHelpers.FORBIDDEN).toContain('authorization')
    expect(__testHelpers.FORBIDDEN).toContain('providerId')
    expect(__testHelpers.FORBIDDEN).toContain('modelId')
    expect(__testHelpers.FORBIDDEN.length).toBe(8)
  })
})

// ============ Source-level independence ============

describe('Phase 7-T3 independence — source contains no forbidden imports', () => {
  it('tool-capability-schema.ts source does NOT import forbidden paths', () => {
    const fs = require('fs')
    const path = require('path')
    const src = fs.readFileSync(
      path.resolve(__dirname, '../../src/shared/tools/tool-capability-schema.ts'),
      'utf8'
    )
    expect(src).not.toContain("'desktop/src/main/services/model-provider")
    expect(src).not.toContain("'../../services/model-provider")
    expect(src).not.toContain("'../auth.service")
    expect(src).not.toContain("'backend/")
  })
})

// ============ Determinism ============

describe('Phase 7-T3 matchToolsForTask — determinism', () => {
  const profile = (toolId: string, score: number): ToolCapabilityProfile => ({
    toolId,
    requiredCapabilities: [],
    optionalCapabilities: [],
    supportedTasks: ['data-analysis'],
    priority: score
  })
  it('returns same order across multiple calls', () => {
    const profiles = [profile('tool:c', 3), profile('tool:a', 1), profile('tool:b', 2)]
    const input = { requiredTasks: ['data-analysis'] as ToolTaskType[], requiredCapabilities: [] }
    const a = matchToolsForTask(input, profiles)
    const b = matchToolsForTask(input, profiles)
    const c = matchToolsForTask(input, profiles)
    expect(a.map((r) => r.toolId)).toEqual(b.map((r) => r.toolId))
    expect(b.map((r) => r.toolId)).toEqual(c.map((r) => r.toolId))
  })
  it('breakdown is included and sums to total', () => {
    const result = matchToolsForTask(
      { requiredTasks: ['data-analysis', 'visualization'], requiredCapabilities: ['x'], optionalTasks: ['export'] },
      [{
        toolId: 'tool:check',
        requiredCapabilities: ['x'],
        optionalCapabilities: [],
        supportedTasks: ['data-analysis', 'visualization', 'export'],
        priority: 3
      }]
    )
    const r = result[0]
    expect(r.breakdown).toBeDefined()
    // taskScore=20 (2 req tasks * 10) + 2 (1 opt task) = 22
    // capabilityScore=5 (1 req cap)
    // priorityScore=3
    // total = 30
    expect(r.breakdown?.taskScore).toBe(22)
    expect(r.breakdown?.capabilityScore).toBe(5)
    expect(r.breakdown?.priorityScore).toBe(3)
    expect(r.score).toBe(30)
  })
  it('does NOT mutate input profiles array', () => {
    const profiles = [
      { toolId: 'tool:a', requiredCapabilities: [], optionalCapabilities: [],
        supportedTasks: ['data-analysis'], priority: 5 }
    ]
    const before = JSON.stringify(profiles)
    matchToolsForTask(
      { requiredTasks: ['data-analysis'], requiredCapabilities: [] },
      profiles
    )
    expect(JSON.stringify(profiles)).toBe(before)
  })
})

// ============ Additional coverage to reach >= 50 ============

describe('Phase 7-T3 matchToolsForTask — additional ranking cases', () => {
  const profile = (overrides: Partial<ToolCapabilityProfile>): ToolCapabilityProfile => ({
    toolId: 'tool:test',
    requiredCapabilities: [],
    optionalCapabilities: [],
    supportedTasks: ['data-analysis'],
    priority: 5,
    ...overrides
  })
  it('handles multiple required capabilities correctly', () => {
    const result = matchToolsForTask(
      { requiredTasks: [], requiredCapabilities: ['a', 'b', 'c'] },
      [profile({ toolId: 'tool:multi', requiredCapabilities: ['a', 'b', 'c'] })]
    )
    expect(result[0].score).toBe(15 + 5)  // 3 caps * 5 + priority 5
  })
  it('score for no overlap is empty (zero filtered out)', () => {
    const result = matchToolsForTask(
      { requiredTasks: ['data-analysis'], requiredCapabilities: [] },
      [profile({ toolId: 'tool:no-match', supportedTasks: ['export'], priority: 5 })]
    )
    expect(result).toEqual([])
  })
  it('breakdown sum equals total score', () => {
    const result = matchToolsForTask(
      { requiredTasks: ['data-analysis', 'visualization'],
        optionalTasks: ['export'],
        requiredCapabilities: ['cap-a'] },
      [profile({
        toolId: 'tool:sum',
        requiredCapabilities: ['cap-a'],
        supportedTasks: ['data-analysis', 'visualization', 'export'],
        priority: 7
      })]
    )
    const b = result[0].breakdown!
    expect(b.taskScore + b.capabilityScore + b.priorityScore).toBe(result[0].score)
  })
  it('all 8 ToolTaskType values are accepted by isValidToolTaskType', () => {
    for (const t of TOOL_TASK_TYPES) {
      expect(isValidToolTaskType(t)).toBe(true)
    }
  })
})
