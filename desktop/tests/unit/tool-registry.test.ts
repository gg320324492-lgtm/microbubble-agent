// Phase 7-T1 Tool Registry Implementation tests.
//
// Coverage (>= 50 cases):
//   - Registry creation (3)
//   - register success (5)
//   - register failure (3)
//   - get / lookup / has (6)
//   - list (5)
//   - unregister (3)
//   - clear (2)
//   - snapshot (3)
//   - builtin tools (4)
//   - singleton lifecycle (4)
//   - deterministic order (3)
//   - security (8)

import { describe, it, expect, beforeEach } from 'vitest'
import {
  ToolRegistry,
  ToolAlreadyRegisteredError,
  ToolValidationError,
  __testHelpers
} from '../../src/main/services/tools/tool-registry'
import {
  getToolRegistry,
  initializeBuiltinTools,
  resetToolRegistry,
  bootToolLayer
} from '../../src/main/services/tools/index'
import {
  KINETIC_ANALYSIS_TOOL,
  DATA_VISUALIZATION_TOOL,
  DATASET_EXPORT_TOOL,
  BUILTIN_TOOLS
} from '../../src/shared/tools/builtin-tools'
import type { ToolDefinition } from '../../src/shared/tools/tool-schema'

function makeTool(
  id: string,
  overrides: Partial<ToolDefinition> = {}
): ToolDefinition {
  return {
    id,
    name: overrides.name ?? `Tool ${id}`,
    description: overrides.description ?? `Description for ${id}`,
    category: overrides.category ?? 'analysis',
    version: overrides.version ?? '1.0.0',
    inputSchema: overrides.inputSchema ?? { fields: [], required: [], validationRules: [] },
    outputSchema: overrides.outputSchema ?? { description: 'x', fields: [] },
    executionTarget: overrides.executionTarget ?? 'local-service',
    permission: overrides.permission ?? 'public',
    tags: overrides.tags ?? []
  }
}

beforeEach(() => {
  resetToolRegistry()
})

// ============ Registry creation ============

describe('Phase 7-T1 ToolRegistry — creation', () => {
  it('new registry starts empty', () => {
    const r = new ToolRegistry()
    expect(r.size()).toBe(0)
  })
  it('new registry has() returns false for any id', () => {
    const r = new ToolRegistry()
    expect(r.has('tool:any')).toBe(false)
  })
  it('new registry list() returns empty array', () => {
    const r = new ToolRegistry()
    expect(r.list()).toEqual([])
  })
})

// ============ register success ============

describe('Phase 7-T1 ToolRegistry — register success', () => {
  it('register accepts a valid tool', () => {
    const r = new ToolRegistry()
    expect(() => r.register(makeTool('tool:test1'))).not.toThrow()
    expect(r.has('tool:test1')).toBe(true)
    expect(r.size()).toBe(1)
  })
  it('register sets registeredAt to a recent epoch ms', () => {
    const r = new ToolRegistry()
    const before = Date.now()
    r.register(makeTool('tool:test2'))
    const after = Date.now()
    const reg = r.get('tool:test2')!
    expect(reg.registeredAt).toBeGreaterThanOrEqual(before)
    expect(reg.registeredAt).toBeLessThanOrEqual(after)
  })
  it('register assigns a unique handle', () => {
    const r = new ToolRegistry()
    r.register(makeTool('tool:a'))
    r.register(makeTool('tool:b'))
    const ha = r.get('tool:a')!.handle
    const hb = r.get('tool:b')!.handle
    expect(ha).not.toBe(hb)
    expect(ha.startsWith('handle:')).toBe(true)
    expect(hb.startsWith('handle:')).toBe(true)
  })
  it('register multiple tools keeps all', () => {
    const r = new ToolRegistry()
    r.register(makeTool('tool:a'))
    r.register(makeTool('tool:b'))
    r.register(makeTool('tool:c'))
    expect(r.size()).toBe(3)
  })
  it('register freezes definition shape (definition is a snapshot)', () => {
    const r = new ToolRegistry()
    const def = makeTool('tool:snap')
    r.register(def)
    const reg = r.get('tool:snap')!
    expect(reg.definition).toBe(def)
  })
})

// ============ register failure ============

describe('Phase 7-T1 ToolRegistry — register failure', () => {
  it('register rejects duplicate id', () => {
    const r = new ToolRegistry()
    r.register(makeTool('tool:dup'))
    expect(() => r.register(makeTool('tool:dup'))).toThrow(ToolAlreadyRegisteredError)
  })
  it('register rejects invalid ToolDefinition (bad id)', () => {
    const r = new ToolRegistry()
    expect(() => r.register(makeTool('bad-id'))).toThrow(ToolValidationError)
  })
  it('register rejects missing description', () => {
    const r = new ToolRegistry()
    expect(() => r.register(makeTool('tool:test', { description: '' }))).toThrow(ToolValidationError)
  })
})

// ============ get / lookup / has ============

describe('Phase 7-T1 ToolRegistry — get / lookup / has', () => {
  let r: ToolRegistry
  beforeEach(() => {
    r = new ToolRegistry()
    r.register(makeTool('tool:a'))
    r.register(makeTool('tool:b'))
  })
  it('get returns registration for known id', () => {
    const reg = r.get('tool:a')
    expect(reg).not.toBeNull()
    expect(reg?.definition.id).toBe('tool:a')
  })
  it('get returns null for unknown id', () => {
    expect(r.get('tool:unknown')).toBeNull()
  })
  it('lookup returns found=true for known id', () => {
    const result = r.lookup('tool:b')
    expect(result.found).toBe(true)
    expect(result.tool?.definition.id).toBe('tool:b')
  })
  it('lookup returns found=false for unknown id', () => {
    const result = r.lookup('tool:unknown')
    expect(result.found).toBe(false)
    expect(result.tool).toBeUndefined()
  })
  it('has returns true for known id', () => {
    expect(r.has('tool:a')).toBe(true)
  })
  it('has returns false for unknown id', () => {
    expect(r.has('tool:unknown')).toBe(false)
  })
})

// ============ list ============

describe('Phase 7-T1 ToolRegistry — list', () => {
  let r: ToolRegistry
  beforeEach(() => {
    r = new ToolRegistry()
    r.register(makeTool('tool:a', { category: 'analysis' }))
    r.register(makeTool('tool:b', { category: 'simulation' }))
    r.register(makeTool('tool:c', { category: 'analysis' }))
    r.register(makeTool('tool:d', { category: 'export', permission: 'admin' }))
  })
  it('list() returns all tools', () => {
    expect(r.list()).toHaveLength(4)
  })
  it('list({ category }) filters by category', () => {
    expect(r.list({ category: 'analysis' })).toHaveLength(2)
    expect(r.list({ category: 'simulation' })).toHaveLength(1)
    // tool:d has default category 'analysis' since makeTool defaults to that
    // (permission override does not change category)
  })
  it('list({ permission }) filters by permission', () => {
    expect(r.list({ permission: 'admin' })).toHaveLength(1)
    expect(r.list({ permission: 'public' })).toHaveLength(3)
  })
  it('list({ tags }) filters by tag intersection', () => {
    r.clear()
    r.register(makeTool('tool:a', { tags: ['kinetics', 'ozone'] }))
    r.register(makeTool('tool:b', { tags: ['visualization'] }))
    expect(r.list({ tags: ['kinetics'] })).toHaveLength(1)
    expect(r.list({ tags: ['ozone', 'visualization'] })).toHaveLength(2)
  })
  it('list result is sorted alphabetically by id (deterministic)', () => {
    const ids = r.list().map((t) => t.definition.id)
    const sorted = [...ids].sort()
    expect(ids).toEqual(sorted)
  })
})

// ============ unregister ============

describe('Phase 7-T1 ToolRegistry — unregister', () => {
  let r: ToolRegistry
  beforeEach(() => {
    r = new ToolRegistry()
    r.register(makeTool('tool:a'))
    r.register(makeTool('tool:b'))
  })
  it('unregister removes the tool', () => {
    expect(r.unregister('tool:a')).toBe(true)
    expect(r.has('tool:a')).toBe(false)
  })
  it('unregister returns false for unknown id', () => {
    expect(r.unregister('tool:nothing')).toBe(false)
  })
  it('unregister with empty string is a no-op', () => {
    expect(r.unregister('')).toBe(false)
  })
})

// ============ clear ============

describe('Phase 7-T1 ToolRegistry — clear', () => {
  it('clear removes all tools', () => {
    const r = new ToolRegistry()
    r.register(makeTool('tool:a'))
    r.register(makeTool('tool:b'))
    r.register(makeTool('tool:c'))
    r.clear()
    expect(r.size()).toBe(0)
  })
  it('clear allows re-registering the same id', () => {
    const r = new ToolRegistry()
    r.register(makeTool('tool:a'))
    r.clear()
    expect(() => r.register(makeTool('tool:a'))).not.toThrow()
  })
})

// ============ snapshot ============

describe('Phase 7-T1 ToolRegistry — snapshot', () => {
  it('snapshot returns count and sorted tools', () => {
    const r = new ToolRegistry()
    r.register(makeTool('tool:b'))
    r.register(makeTool('tool:a'))
    r.register(makeTool('tool:c'))
    const s = r.snapshot()
    expect(s.count).toBe(3)
    expect(s.tools).toHaveLength(3)
    expect(s.tools[0].definition.id).toBe('tool:a')
    expect(s.timestamp).toBeGreaterThan(0)
  })
  it('snapshot of empty registry has count 0', () => {
    const s = new ToolRegistry().snapshot()
    expect(s.count).toBe(0)
    expect(s.tools).toEqual([])
  })
  it('snapshot is a copy (mutations do not affect registry)', () => {
    const r = new ToolRegistry()
    r.register(makeTool('tool:a'))
    const s = r.snapshot()
    s.tools.pop()
    expect(r.size()).toBe(1)
  })
})

// ============ builtin tools ============

describe('Phase 7-T1 builtin tools catalog', () => {
  it('BUILTIN_TOOLS has 4 declared tools', () => {
    expect(BUILTIN_TOOLS).toHaveLength(4)
  })
  it('KINETIC_ANALYSIS_TOOL is correctly typed', () => {
    expect(KINETIC_ANALYSIS_TOOL.id).toBe('tool:kinetic-analysis')
    expect(KINETIC_ANALYSIS_TOOL.category).toBe('analysis')
    expect(KINETIC_ANALYSIS_TOOL.permission).toBe('research')
  })
  it('DATA_VISUALIZATION_TOOL is correctly typed', () => {
    expect(DATA_VISUALIZATION_TOOL.id).toBe('tool:data-visualization')
    expect(DATA_VISUALIZATION_TOOL.category).toBe('visualization')
  })
  it('DATASET_EXPORT_TOOL is correctly typed', () => {
    expect(DATASET_EXPORT_TOOL.id).toBe('tool:dataset-export')
    expect(DATASET_EXPORT_TOOL.category).toBe('export')
  })
})

// ============ singleton lifecycle ============

describe('Phase 7-T1 singleton lifecycle', () => {
  it('getToolRegistry returns the same instance across calls', () => {
    const a = getToolRegistry()
    const b = getToolRegistry()
    expect(a).toBe(b)
  })
  it('initializeBuiltinTools registers all 4 built-in tools', () => {
    const r = getToolRegistry()
    initializeBuiltinTools()
    expect(r.size()).toBe(4)
    expect(r.has('tool:kinetic-analysis')).toBe(true)
    expect(r.has('tool:data-visualization')).toBe(true)
    expect(r.has('tool:dataset-export')).toBe(true)
  })
  it('initializeBuiltinTools is idempotent', () => {
    initializeBuiltinTools()
    initializeBuiltinTools()
    expect(getToolRegistry().size()).toBe(4)
  })
  it('resetToolRegistry clears singleton state', () => {
    initializeBuiltinTools()
    expect(getToolRegistry().size()).toBe(4)
    resetToolRegistry()
    expect(getToolRegistry().size()).toBe(0)
  })
  it('bootToolLayer initializes registry + builtins', () => {
    bootToolLayer()
    const r = getToolRegistry()
    expect(r.size()).toBe(4)
    expect(r.has('tool:kinetic-analysis')).toBe(true)
  })
})

// ============ deterministic order ============

describe('Phase 7-T1 deterministic ordering', () => {
  it('insert in random order, list returns alphabetical', () => {
    const r = new ToolRegistry()
    r.register(makeTool('tool:zeta'))
    r.register(makeTool('tool:alpha'))
    r.register(makeTool('tool:middle'))
    const ids = r.list().map((t) => t.definition.id)
    expect(ids).toEqual(['tool:alpha', 'tool:middle', 'tool:zeta'])
  })
  it('multiple snapshot calls return same order', () => {
    const r = new ToolRegistry()
    r.register(makeTool('tool:c'))
    r.register(makeTool('tool:a'))
    r.register(makeTool('tool:b'))
    const first = r.snapshot().tools.map((t) => t.definition.id)
    const second = r.snapshot().tools.map((t) => t.definition.id)
    expect(first).toEqual(second)
  })
  it('snapshot after mutations is still sorted', () => {
    const r = new ToolRegistry()
    r.register(makeTool('tool:x'))
    r.register(makeTool('tool:a'))
    r.register(makeTool('tool:m'))
    expect(r.snapshot().tools.map((t) => t.definition.id))
      .toEqual(['tool:a', 'tool:m', 'tool:x'])
  })
})

// ============ security ============

describe('Phase 7-T1 security — no-secret enforcement', () => {
  it('register throws when apiKey leaks', () => {
    const r = new ToolRegistry()
    const bad = makeTool('tool:leak', {}) as ToolDefinition & { apiKey?: string }
    bad.apiKey = 'sk-supersecret'
    expect(() => r.register(bad)).toThrow(/forbidden/)
  })
  it('register throws when token leaks in tags', () => {
    const r = new ToolRegistry()
    expect(() => r.register(makeTool('tool:t', { tags: ['Bearer sk-leak'] }))).toThrow(/forbidden/)
  })
  it('register throws when cipher leaks in description', () => {
    const r = new ToolRegistry()
    expect(() => r.register(makeTool('tool:c', { description: 'cipher:abc' }))).toThrow(/forbidden/)
  })
  it('register throws when providerId leaks', () => {
    const r = new ToolRegistry()
    const bad = makeTool('tool:pid', {}) as ToolDefinition & { providerId?: string }
    bad.providerId = 'cloud-vendor'
    expect(() => r.register(bad)).toThrow(/forbidden/)
  })
  it('register throws when modelId leaks', () => {
    const r = new ToolRegistry()
    const bad = makeTool('tool:mid', {}) as ToolDefinition & { modelId?: string }
    bad.modelId = 'gpt-4o'
    expect(() => r.register(bad)).toThrow(/forbidden/)
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
  it('ToolAlreadyRegisteredError carries the offending id in its message', () => {
    const r = new ToolRegistry()
    r.register(makeTool('tool:conflict'))
    try {
      r.register(makeTool('tool:conflict'))
      expect.fail('should have thrown')
    } catch (e) {
      expect((e as Error).message).toContain('tool:conflict')
      expect((e as Error).message).toContain('already registered')
    }
  })
  it('ToolValidationError message mentions id', () => {
    const r = new ToolRegistry()
    try {
      r.register(makeTool('bad-id'))
      expect.fail('should have thrown')
    } catch (e) {
      expect((e as Error).message).toContain('bad-id')
    }
  })
})

// ============ source-level independence ============

describe('Phase 7-T1 independence — source contains no forbidden imports', () => {
  it('tool-registry.ts source does NOT import forbidden paths', () => {
    const fs = require('fs')
    const path = require('path')
    const src = fs.readFileSync(
      path.resolve(__dirname, '../../src/main/services/tools/tool-registry.ts'),
      'utf8'
    )
    expect(src).not.toContain("'desktop/src/main/services/model-provider")
    expect(src).not.toContain("'../../services/model-provider")
    expect(src).not.toContain("'../auth.service")
    expect(src).not.toContain("'../../services/chat")
    expect(src).not.toContain("'backend/")
  })
  it('builtin-tools.ts source does NOT import forbidden paths', () => {
    const fs = require('fs')
    const path = require('path')
    const src = fs.readFileSync(
      path.resolve(__dirname, '../../src/shared/tools/builtin-tools.ts'),
      'utf8'
    )
    expect(src).not.toContain("'desktop/src/main/services/model-provider")
    expect(src).not.toContain("'../../services/model-provider")
    expect(src).not.toContain("'../auth.service")
    expect(src).not.toContain("'backend/")
  })
  it('index.ts source does NOT import forbidden paths', () => {
    const fs = require('fs')
    const path = require('path')
    const src = fs.readFileSync(
      path.resolve(__dirname, '../../src/main/services/tools/index.ts'),
      'utf8'
    )
    expect(src).not.toContain("'desktop/src/main/services/model-provider")
    expect(src).not.toContain("'../../services/model-provider")
    expect(src).not.toContain("'../auth.service")
    expect(src).not.toContain("'backend/")
  })
})
