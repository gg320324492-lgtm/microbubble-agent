// Phase 6-C2 Agent Capability Router tests.
//
// Coverage (>= 30 cases):
//   - isValidResearchTaskType (10 cases)
//   - researchTaskLabel stability (3 cases)
//   - isValidResearchTaskProfile (8 cases)
//   - BUILT_IN_TASK_PROFILES completeness (9 task types)
//   - resolveTaskProfile (3 cases)
//   - routeResearchTask: capability-match / active-fallback / no-route / invalid (10 cases)
//   - routeResearchTaskExtended: task-routed / active-fallback / no-route / invalid (4 cases)
//   - security: assertProfileSafe + reason strings (3 cases)

import { describe, it, expect, beforeEach, vi } from 'vitest'

const FAKE_CIPHER_PREFIX = 'cipher:'
const cipherMap = new Map<string, string>()

vi.mock('electron', () => {
  const safeStorage = {
    isEncryptionAvailable: () => true,
    encryptString: (plain: string) => {
      const cipher = FAKE_CIPHER_PREFIX + Buffer.from(plain).toString('base64')
      cipherMap.set(plain, cipher)
      return Buffer.from(cipher, 'utf8')
    },
    decryptString: (buf: Buffer) => {
      const cipher = buf.toString('utf8')
      for (const [plain, c] of cipherMap.entries()) {
        if (c === cipher) return plain
      }
      throw new Error('fake safeStorage: cipher not found')
    }
  }
  return { safeStorage }
})

vi.mock('electron-store', () => {
  let _memoryStore: Record<string, unknown> = {}
  class FakeStore<T extends Record<string, unknown>> {
    constructor(_opts?: { name?: string }) {}
    get store(): T { return _memoryStore as T }
    set(key: string, value: unknown): void { _memoryStore[key] = value }
    get(key: string): unknown { return _memoryStore[key] }
    has(key: string): boolean { return Object.prototype.hasOwnProperty.call(_memoryStore, key) }
    delete(key: string): void { delete _memoryStore[key] }
    static __reset(): void { _memoryStore = {} }
  }
  return { default: FakeStore }
})
vi.mock('../../src/main/services/model-provider/vault-compat', () => ({
  safeStorageAvailable: () => true
}))
const FakeStoreMod = await import('electron-store') as unknown as { default: { __reset(): void } }

const researchTask = await import('../../src/shared/model/research-task')
const {
  isValidResearchTaskType,
  researchTaskLabel,
  isValidResearchTaskProfile,
  resolveTaskProfile,
  BUILT_IN_TASK_PROFILES
} = researchTask
const {
  routeResearchTask,
  routeResearchTaskExtended
} = await import('../../src/main/services/model-provider/capability-router')
const {
  registerProvider,
  clearRegistry
} = await import('../../src/main/services/model-provider/registry')
const {
  save: saveKey,
  clearAll: clearAllKeys
} = await import('../../src/main/services/model-provider/model-secret-store')
const {
  setActive,
  clearActive
} = await import('../../src/main/services/model-provider/active-provider-store')

function registerWithCaps(
  providerId: string,
  displayName: string,
  defaultModel: string,
  type: 'cloud' | 'local' | 'openai-compatible',
  caps: string[]
): void {
  registerProvider(providerId, () => ({
    id: providerId, type,
    capabilities: { streaming: true, tools: false, vision: false, functionCalling: false, jsonMode: false },
    buildRequest: () => ({}), parseChunk: () => null, ping: async () => ({ ok: true })
  }), {
    type, displayName, defaultModel,
    capabilities: { streaming: true, tools: false, vision: false, functionCalling: false, jsonMode: false },
    researchProfile: { providerId, model: defaultModel, capabilities: caps }
  })
}

beforeEach(() => {
  FakeStoreMod.default.__reset()
  cipherMap.clear()
  clearRegistry()
  clearAllKeys()
  clearActive()
})

// ============ Spec: researchTask taxonomy ============

describe('Phase 6-C2 isValidResearchTaskType — 9 task types', () => {
  const ALL = ['literature-review', 'paper-writing', 'coding', 'matlab', 'python-analysis', 'cfd-analysis', 'image-analysis', 'experiment-design', 'data-analysis']
  for (const t of ALL) {
    it(`accepts '${t}'`, () => {
      expect(isValidResearchTaskType(t)).toBe(true)
    })
  }
  it('rejects unknown task type', () => {
    expect(isValidResearchTaskType('unknown')).toBe(false)
  })
  it('rejects non-string', () => {
    expect(isValidResearchTaskType(42)).toBe(false)
    expect(isValidResearchTaskType(null)).toBe(false)
  })
})

describe('Phase 6-C2 researchTaskLabel — stable UI labels', () => {
  it('literature-review -> Literature Review', () => {
    expect(researchTaskLabel('literature-review')).toBe('Literature Review')
  })
  it('python-analysis -> Python Analysis', () => {
    expect(researchTaskLabel('python-analysis')).toBe('Python Analysis')
  })
  it('paper-writing -> Paper Writing', () => {
    expect(researchTaskLabel('paper-writing')).toBe('Paper Writing')
  })
})

// ============ Spec: isValidResearchTaskProfile ============

describe('Phase 6-C2 isValidResearchTaskProfile — shape validation', () => {
  it('accepts minimal profile', () => {
    expect(isValidResearchTaskProfile({
      taskType: 'coding', requiredCapabilities: ['coding']
    })).toBe(true)
  })
  it('accepts profile with optional + priority', () => {
    expect(isValidResearchTaskProfile({
      taskType: 'literature-review',
      requiredCapabilities: ['literature'],
      optionalCapabilities: ['paper-writing'],
      priority: 8
    })).toBe(true)
  })
  it('rejects unknown taskType', () => {
    expect(isValidResearchTaskProfile({
      taskType: 'flying', requiredCapabilities: ['chat']
    })).toBe(false)
  })
  it('rejects empty requiredCapabilities', () => {
    expect(isValidResearchTaskProfile({
      taskType: 'coding', requiredCapabilities: []
    })).toBe(false)
  })
  it('rejects non-array requiredCapabilities', () => {
    expect(isValidResearchTaskProfile({
      taskType: 'coding', requiredCapabilities: 'coding'
    })).toBe(false)
  })
  it('rejects unknown capability tag', () => {
    expect(isValidResearchTaskProfile({
      taskType: 'coding', requiredCapabilities: ['flying']
    })).toBe(false)
  })
  it('rejects priority out of range', () => {
    expect(isValidResearchTaskProfile({
      taskType: 'coding', requiredCapabilities: ['coding'], priority: 11
    })).toBe(false)
    expect(isValidResearchTaskProfile({
      taskType: 'coding', requiredCapabilities: ['coding'], priority: -1
    })).toBe(false)
  })
  it('rejects secret-like apiKey field (defense in depth)', () => {
    expect(isValidResearchTaskProfile({
      taskType: 'coding', requiredCapabilities: ['coding'], apiKey: 'sk-secret'
    })).toBe(false)
  })
})

// ============ Spec: BUILT_IN_TASK_PROFILES ============

describe('Phase 6-C2 BUILT_IN_TASK_PROFILES — all 9 tasks defined', () => {
  for (const t of ['literature-review', 'paper-writing', 'coding', 'matlab', 'python-analysis', 'cfd-analysis', 'image-analysis', 'experiment-design', 'data-analysis'] as const) {
    it(`'${t}' has a built-in profile`, () => {
      expect(BUILT_IN_TASK_PROFILES[t]).toBeDefined()
      expect(BUILT_IN_TASK_PROFILES[t].requiredCapabilities.length).toBeGreaterThan(0)
    })
  }
})

// ============ Spec: resolveTaskProfile ============

describe('Phase 6-C2 resolveTaskProfile', () => {
  it('returns built-in for known taskType', () => {
    const p = resolveTaskProfile('python-analysis')
    expect(p.requiredCapabilities).toContain('python')
    expect(p.requiredCapabilities).toContain('data-analysis')
  })
  it('returns built-in for matlab task', () => {
    const p = resolveTaskProfile('matlab')
    expect(p.requiredCapabilities).toContain('matlab')
  })
  it('returns built-in for cfd task', () => {
    const p = resolveTaskProfile('cfd-analysis')
    expect(p.requiredCapabilities).toContain('cfd')
  })
})

// ============ Spec: routeResearchTask ============

describe('Phase 6-C2 routeResearchTask — capability-match path', () => {
  beforeEach(() => {
    registerWithCaps('paperbot', 'PaperBot', 'paperbot-pro', 'cloud', ['paper-writing', 'literature'])
    registerWithCaps('coder', 'Coder', 'coder-7b', 'cloud', ['coding', 'python'])
    registerWithCaps('cfdengine', 'CFDEngine', 'cfd-2', 'local', ['cfd', 'math'])
    saveKey('paperbot', 'sk-paper')
    saveKey('coder', 'sk-coder')
    saveKey('cfdengine', 'sk-cfd')
  })
  it('paper-writing task picks paper-capable model with key', () => {
    const d = routeResearchTask({
      taskType: 'paper-writing',
      requiredCapabilities: ['paper-writing']
    })
    expect(d?.source).toBe('capability-match')
    expect(d?.providerId).toBe('paperbot')
  })
  it('coding task picks coder (no overlap with paper/cfd)', () => {
    const d = routeResearchTask({
      taskType: 'coding',
      requiredCapabilities: ['coding']
    })
    expect(d?.source).toBe('capability-match')
    expect(d?.providerId).toBe('coder')
  })
  it('cfd task picks cfd provider', () => {
    const d = routeResearchTask({
      taskType: 'cfd-analysis',
      requiredCapabilities: ['cfd']
    })
    expect(d?.source).toBe('capability-match')
    expect(d?.providerId).toBe('cfdengine')
  })
  it('skips providers without stored key (security boundary)', () => {
    clearAllKeys()
    saveKey('paperbot', 'sk-paper')
    // coder + cfdengine have no key now; paperbot has key but lacks 'coding'
    const d = routeResearchTask({
      taskType: 'coding', requiredCapabilities: ['coding']
    })
    // coder is filtered (no key); cfdengine is filtered (no key + no coding);
    // paperbot has key but doesn't satisfy required=['coding']. No candidate.
    expect(d).toBeNull()
  })
})

describe('Phase 6-C2 routeResearchTask — active-provider fallback', () => {
  beforeEach(() => {
    registerWithCaps('chatty', 'Chatty', 'chatty-1', 'cloud', ['chat'])
    setActive({ providerId: 'chatty', model: 'chatty-1', enabled: true })
    saveKey('chatty', 'sk-chatty')
  })
  it('falls back to active provider when no capability match', () => {
    // No paper/cfd providers registered. Active provider has chat cap only.
    const d = routeResearchTask({
      taskType: 'paper-writing', requiredCapabilities: ['paper-writing']
    })
    expect(d?.source).toBe('active-provider')
    expect(d?.providerId).toBe('chatty')
    expect(d?.reason).toContain('fell back to active')
  })
})

describe('Phase 6-C2 routeResearchTask — no-route path', () => {
  it('returns null when nothing registered AND no active', () => {
    const d = routeResearchTask({
      taskType: 'coding', requiredCapabilities: ['coding']
    })
    expect(d).toBeNull()
  })
  it('returns null when active provider has no key', () => {
    registerWithCaps('chatty', 'Chatty', 'chatty-1', 'cloud', ['chat'])
    setActive({ providerId: 'chatty', model: 'chatty-1', enabled: true })
    // no key
    const d = routeResearchTask({
      taskType: 'coding', requiredCapabilities: ['coding']
    })
    expect(d).toBeNull()
  })
})

describe('Phase 6-C2 routeResearchTask — invalid profile', () => {
  it('treats null input as default fallback to coding', () => {
    registerWithCaps('coder', 'Coder', 'c', 'cloud', ['coding'])
    saveKey('coder', 'sk-c')
    const d = routeResearchTask(null)
    // No required caps (resolved to coding), coder matches
    expect(d?.providerId).toBe('coder')
  })
})

// ============ Spec: routeResearchTaskExtended ============

describe('Phase 6-C2 routeResearchTaskExtended — extended outcome', () => {
  it("returns 'task-routed' for capability match", () => {
    registerWithCaps('coder', 'Coder', 'c', 'cloud', ['coding'])
    saveKey('coder', 'sk-c')
    const r = routeResearchTaskExtended({ taskType: 'coding', requiredCapabilities: ['coding'] })
    expect(r.route).toBe('task-routed')
    expect(r.decision?.providerId).toBe('coder')
  })
  it("returns 'active-fallback' when active provider used", () => {
    registerWithCaps('chatty', 'Chatty', 'c', 'cloud', ['chat'])
    setActive({ providerId: 'chatty', model: 'c', enabled: true })
    saveKey('chatty', 'sk-c')
    const r = routeResearchTaskExtended({ taskType: 'paper-writing', requiredCapabilities: ['paper-writing'] })
    expect(r.route).toBe('active-fallback')
  })
  it("returns 'no-route' when nothing matches", () => {
    const r = routeResearchTaskExtended({ taskType: 'coding', requiredCapabilities: ['coding'] })
    expect(r.route).toBe('no-route')
    expect(r.decision).toBeNull()
  })
  it("returns 'invalid' for malformed profile", () => {
    const r = routeResearchTaskExtended({ taskType: 'flying', requiredCapabilities: ['coding'] })
    expect(r.route).toBe('invalid')
  })
})

// ============ Spec: Security ============

describe('Phase 6-C2 security — reason strings NEVER contain apiKey', () => {
  it('reason for capability-match is clean', () => {
    registerWithCaps('paperbot', 'PaperBot', 'paperbot-pro', 'cloud', ['paper-writing'])
    saveKey('paperbot', 'sk-supersecret')
    const d = routeResearchTask({
      taskType: 'paper-writing', requiredCapabilities: ['paper-writing']
    })
    expect(d?.reason).not.toContain('sk-supersecret')
  })
  it('RouterDecision shape never carries apiKey', () => {
    registerWithCaps('coder', 'Coder', 'c', 'cloud', ['coding'])
    saveKey('coder', 'sk-supersecret')
    const d = routeResearchTask({
      taskType: 'coding', requiredCapabilities: ['coding']
    })
    expect(d).toBeDefined()
    const dump = JSON.stringify(d)
    expect(dump).not.toContain('sk-supersecret')
    expect(dump).not.toContain('apiKey')
    expect(dump).not.toContain('cipher')
  })
  it('route does not throw on empty registry + invalid profile', () => {
    expect(() => routeResearchTask({
      taskType: 'flying' as never,
      requiredCapabilities: ['coding']
    })).not.toThrow()
  })
})
