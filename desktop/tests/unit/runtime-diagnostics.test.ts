// Phase 6-D Runtime Diagnostics tests.
//
// Coverage (>= 30 cases):
//   - getProviderDiagnostics shape (6)
//   - status mapping (4)
//   - success rate / latency (4)
//   - budget display (4)
//   - hasApiKey boolean (3)
//   - researchCapabilities (3)
//   - getAllProviderDiagnostics (3)
//   - assertSnapshotSafe (5)

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

const {
  getProviderDiagnostics, getAllProviderDiagnostics, assertSnapshotSafe
} = await import('../../src/main/services/model-provider/runtime-diagnostics')
const {
  registerProvider, clearRegistry
} = await import('../../src/main/services/model-provider/registry')
const {
  saveConfig, clearAll: clearAllConfigs
} = await import('../../src/main/services/model-provider/provider-config-store')
const {
  save: saveKey, clearAll: clearAllKeys
} = await import('../../src/main/services/model-provider/model-secret-store')
const {
  recordSuccess, recordFailure, clear: healthClear, setHealthClock, resetHealthClock
} = await import('../../src/main/services/model-provider/health-tracker')
const {
  recordRequest: metricsRecord, reset: metricsReset
} = await import('../../src/main/services/model-provider/metrics-store')
const {
  setLimit, recordUsage, reset: budgetReset
} = await import('../../src/main/services/model-provider/budget-manager')

function register(providerId: string, caps: string[], researchCaps: string[]): void {
  registerProvider(providerId, () => ({
    id: providerId, type: 'cloud',
    capabilities: { streaming: true, tools: false, vision: false, functionCalling: false, jsonMode: false },
    buildRequest: () => ({}), parseChunk: () => null, ping: async () => ({ ok: true })
  }), {
    type: 'cloud', displayName: providerId, defaultModel: 'm',
    capabilities: { streaming: true, tools: false, vision: false, functionCalling: false, jsonMode: false },
    researchProfile: { providerId, model: 'm', capabilities: researchCaps }
  })
  saveConfig(providerId, {
    type: 'cloud', defaultModel: 'm', displayName: providerId,
    capabilities: caps,
    endpoint: 'https://api.example.com/v1'
  })
}

beforeEach(() => {
  FakeStoreMod.default.__reset()
  cipherMap.clear()
  clearRegistry()
  clearAllConfigs()
  clearAllKeys()
  healthClear()
  metricsReset()
  budgetReset()
  resetHealthClock()
})

// ============ Spec: getProviderDiagnostics shape ============

describe('Phase 6-D getProviderDiagnostics — shape', () => {
  it('returns null for unknown providerId', () => {
    expect(getProviderDiagnostics('not-registered')).toBeNull()
  })
  it('returns null for empty providerId', () => {
    expect(getProviderDiagnostics('')).toBeNull()
  })
  it('returns object with required fields', () => {
    register('aa', ['streaming'], ['coding'])
    saveKey('aa', 'sk-x')
    const d = getProviderDiagnostics('aa')
    expect(d).toBeDefined()
    expect(d).toHaveProperty('providerId', 'aa')
    expect(d).toHaveProperty('displayName')
    expect(d).toHaveProperty('defaultModel')
    expect(d).toHaveProperty('type')
    expect(d).toHaveProperty('status')
    expect(d).toHaveProperty('successRate')
    expect(d).toHaveProperty('totalRequests')
    expect(d).toHaveProperty('capabilities')
    expect(d).toHaveProperty('hasApiKey')
    expect(d).toHaveProperty('budget')
    expect(d).toHaveProperty('researchCapabilities')
  })
  it('displayName reflects registry meta', () => {
    register('aa', [], [])
    saveKey('aa', 'sk')
    const d = getProviderDiagnostics('aa')
    expect(d?.displayName).toBe('aa')
  })
  it('defaultModel reflects registry meta', () => {
    register('aa', [], [])
    saveKey('aa', 'sk')
    const d = getProviderDiagnostics('aa')
    expect(d?.defaultModel).toBe('m')
  })
  it('type reflects ConfigStore', () => {
    register('aa', [], [])
    saveKey('aa', 'sk')
    const d = getProviderDiagnostics('aa')
    expect(d?.type).toBe('cloud')
  })
})

// ============ Spec: status mapping ============

describe('Phase 6-D getProviderDiagnostics — status mapping', () => {
  it('unknown state -> status=unknown', () => {
    register('aa', [], [])
    saveKey('aa', 'sk')
    expect(getProviderDiagnostics('aa')?.status).toBe('unknown')
  })
  it('healthy state -> status=connected', () => {
    register('aa', [], [])
    saveKey('aa', 'sk')
    recordSuccess('aa', 100)
    expect(getProviderDiagnostics('aa')?.status).toBe('connected')
  })
  it('degraded state -> status=checking', () => {
    register('aa', [], [])
    saveKey('aa', 'sk')
    for (let i = 0; i < 10; i++) recordSuccess('aa', 6000)
    expect(getProviderDiagnostics('aa')?.status).toBe('checking')
  })
  it('cooldown state -> status=failed', () => {
    register('aa', [], [])
    saveKey('aa', 'sk')
    recordFailure('aa'); recordFailure('aa'); recordFailure('aa')
    expect(getProviderDiagnostics('aa')?.status).toBe('failed')
  })
})

// ============ Spec: success rate / latency ============

describe('Phase 6-D getProviderDiagnostics — success rate', () => {
  it('100% when all success', () => {
    register('aa', [], [])
    saveKey('aa', 'sk')
    metricsRecord('aa', 100, true)
    metricsRecord('aa', 200, true)
    expect(getProviderDiagnostics('aa')?.successRate).toBe(1)
  })
  it('0% when all failure', () => {
    register('aa', [], [])
    saveKey('aa', 'sk')
    metricsRecord('aa', 100, false)
    metricsRecord('aa', 200, false)
    expect(getProviderDiagnostics('aa')?.successRate).toBe(0)
  })
  it('partial rate is fractional', () => {
    register('aa', [], [])
    saveKey('aa', 'sk')
    metricsRecord('aa', 100, true)
    metricsRecord('aa', 200, false)
    expect(getProviderDiagnostics('aa')?.successRate).toBe(0.5)
  })
  it('latencyMs is null when no successes', () => {
    register('aa', [], [])
    saveKey('aa', 'sk')
    expect(getProviderDiagnostics('aa')?.latencyMs).toBeNull()
  })
})

// ============ Spec: budget display ============

describe('Phase 6-D getProviderDiagnostics — budget display', () => {
  it('limit=0 -> remaining=Infinity', () => {
    register('aa', [], [])
    saveKey('aa', 'sk')
    const b = getProviderDiagnostics('aa')?.budget
    expect(b?.limit).toBe(0)
    expect(b?.used).toBe(0)
    expect(b?.remaining).toBe(Number.POSITIVE_INFINITY)
  })
  it('limit=1000 used=300 -> remaining=700', () => {
    register('aa', [], [])
    saveKey('aa', 'sk')
    setLimit('aa', 1000)
    recordUsage('aa', 300)
    const b = getProviderDiagnostics('aa')?.budget
    expect(b?.limit).toBe(1000)
    expect(b?.used).toBe(300)
    expect(b?.remaining).toBe(700)
  })
  it('limit=100 used=100 -> remaining=0', () => {
    register('aa', [], [])
    saveKey('aa', 'sk')
    setLimit('aa', 100)
    recordUsage('aa', 100)
    const b = getProviderDiagnostics('aa')?.budget
    expect(b?.remaining).toBe(0)
  })
  it('limit=100 used=200 -> remaining=0 (clamped)', () => {
    register('aa', [], [])
    saveKey('aa', 'sk')
    setLimit('aa', 100)
    recordUsage('aa', 200)
    const b = getProviderDiagnostics('aa')?.budget
    expect(b?.remaining).toBe(0)
  })
})

// ============ Spec: hasApiKey boolean (Phase 6-D strict) ============

describe('Phase 6-D getProviderDiagnostics — hasApiKey boolean', () => {
  it('hasApiKey=true when key stored', () => {
    register('aa', [], [])
    saveKey('aa', 'sk-x')
    expect(getProviderDiagnostics('aa')?.hasApiKey).toBe(true)
  })
  it('hasApiKey=false when no key stored', () => {
    register('aa', [], [])
    expect(getProviderDiagnostics('aa')?.hasApiKey).toBe(false)
  })
  it('hasApiKey is BOOLEAN, not the key string', () => {
    register('aa', [], [])
    saveKey('aa', 'sk-supersecret-9999')
    const d = getProviderDiagnostics('aa')
    expect(typeof d?.hasApiKey).toBe('boolean')
    const dump = JSON.stringify(d)
    expect(dump).not.toContain('sk-supersecret')
  })
})

// ============ Spec: researchCapabilities ============

describe('Phase 6-D getProviderDiagnostics — researchCapabilities', () => {
  it('reflects Phase 6-C1 researchProfile', () => {
    register('aa', [], ['coding', 'math', 'paper-writing'])
    saveKey('aa', 'sk')
    const d = getProviderDiagnostics('aa')
    expect(d?.researchCapabilities).toEqual(['coding', 'math', 'paper-writing'])
  })
  it('returns ["chat"] (unknown fallback) when no researchProfile', () => {
    registerProvider('bb', () => ({
      id: 'bb', type: 'cloud',
      capabilities: { streaming: true, tools: false, vision: false, functionCalling: false, jsonMode: false },
      buildRequest: () => ({}), parseChunk: () => null, ping: async () => ({ ok: true })
    }), {
      type: 'cloud', displayName: 'bb', defaultModel: 'm',
      capabilities: { streaming: true, tools: false, vision: false, functionCalling: false, jsonMode: false }
      // no researchProfile
    })
    // Phase 6-C1 unknown fallback returns ['chat']
    expect(getProviderDiagnostics('bb')?.researchCapabilities).toEqual(['chat'])
  })
  it('preserves order from registry', () => {
    register('aa', [], ['paper-writing', 'literature', 'coding'])
    saveKey('aa', 'sk')
    expect(getProviderDiagnostics('aa')?.researchCapabilities).toEqual([
      'paper-writing', 'literature', 'coding'
    ])
  })
})

// ============ Spec: getAllProviderDiagnostics ============

describe('Phase 6-D getAllProviderDiagnostics', () => {
  it('returns empty array when no providers', () => {
    expect(getAllProviderDiagnostics()).toEqual([])
  })
  it('returns one snapshot per registered provider', () => {
    register('aa', [], [])
    register('bb', [], [])
    saveKey('aa', 'sk-a')
    saveKey('bb', 'sk-b')
    const all = getAllProviderDiagnostics()
    expect(all).toHaveLength(2)
    const ids = all.map((d) => d.providerId).sort()
    expect(ids).toEqual(['aa', 'bb'])
  })
  it('all snapshots pass assertSnapshotSafe', () => {
    register('aa', [], ['coding'])
    register('bb', [], ['math'])
    saveKey('aa', 'sk-a')
    saveKey('bb', 'sk-b')
    const all = getAllProviderDiagnostics()
    for (const d of all) expect(() => assertSnapshotSafe(d)).not.toThrow()
  })
})

// ============ Spec: assertSnapshotSafe ============

describe('Phase 6-D assertSnapshotSafe', () => {
  it('accepts clean snapshot', () => {
    register('aa', [], [])
    saveKey('aa', 'sk')
    const d = getProviderDiagnostics('aa')
    expect(() => assertSnapshotSafe(d!)).not.toThrow()
  })
  it('throws on sk- substring in dump', () => {
    expect(() => assertSnapshotSafe({
      providerId: 'aa', displayName: 'aa', defaultModel: 'm', type: 'cloud',
      status: 'connected', latencyMs: null, successRate: 1, totalRequests: 0,
      capabilities: [], hasApiKey: false, budget: { limit: 0, used: 0, remaining: Infinity },
      researchCapabilities: [],
      lastError: 'sk-supersecret-leaked'  // forbidden
    } as never)).toThrow(/sk-/)
  })
  it('throws on apiKey substring', () => {
    expect(() => assertSnapshotSafe({
      providerId: 'aa', displayName: 'aa', defaultModel: 'm', type: 'cloud',
      status: 'connected', latencyMs: null, successRate: 1, totalRequests: 0,
      capabilities: [], hasApiKey: false, budget: { limit: 0, used: 0, remaining: Infinity },
      researchCapabilities: [],
      // attach an explicit 'apiKey' field — would-be leak (defense in depth)
      extra: { apiKey: 'secret-leak' }
    } as unknown as Parameters<typeof assertSnapshotSafe>[0])).toThrow(/forbidden substring/)
  })
  it('throws on Bearer substring', () => {
    expect(() => assertSnapshotSafe({
      providerId: 'aa', displayName: 'aa', defaultModel: 'm', type: 'cloud',
      status: 'connected', latencyMs: null, successRate: 1, totalRequests: 0,
      capabilities: [], hasApiKey: false, budget: { limit: 0, used: 0, remaining: Infinity },
      researchCapabilities: [],
      authHeader: 'Bearer sk-supersecret'
    } as never)).toThrow(/forbidden substring/)
  })
  it('throws on cipher substring', () => {
    expect(() => assertSnapshotSafe({
      providerId: 'aa', displayName: 'aa', defaultModel: 'm', type: 'cloud',
      status: 'connected', latencyMs: null, successRate: 1, totalRequests: 0,
      capabilities: [], hasApiKey: false, budget: { limit: 0, used: 0, remaining: Infinity },
      researchCapabilities: [],
      note: 'cipher:abc123'  // would-be leak
    } as never)).toThrow(/cipher/)
  })
})
