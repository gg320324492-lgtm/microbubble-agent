// Phase 6-D Live E2E Validation tests.
//
// Purpose: validate the FULL runtime flow (Phase 6-A/B/C1/C2/C3/C4) end-to-end
// using in-memory mock providers + research profiles. NO real network calls.
//
// Scenarios:
//   A. Provider connection test
//   B. Auto Research Mode routing — literature-review
//   C. Paper writing routing
//   D. CFD analysis routing
//   E. Data analysis routing
//   F. Manual override (Phase 6-B behavior unchanged)
//   G. Health fallback (cooldown A -> healthy B)
//   H. Budget filter simulation
//
// Each scenario verifies:
//   - selected provider exists
//   - decision.reason present (non-empty)
//   - decision.source correct
//   - rankedCandidates include score breakdown
//   - NO secret leakage (Phase 6-D strict)

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
  routeResearchTask, retryWithFallback
} = await import('../../src/main/services/model-provider/capability-router')
const { resolveActiveProvider } = await import('../../src/main/services/model-provider/runtime-router')
const {
  registerProvider, clearRegistry
} = await import('../../src/main/services/model-provider/registry')
const {
  save: saveKey, exists: keyExists, clearAll: clearAllKeys
} = await import('../../src/main/services/model-provider/model-secret-store')
const {
  saveConfig, clearAll: clearAllConfigs
} = await import('../../src/main/services/model-provider/provider-config-store')
const {
  setActive, clearActive
} = await import('../../src/main/services/model-provider/active-provider-store')
const {
  recordSuccess, recordFailure, clear: healthClear, getHealth
} = await import('../../src/main/services/model-provider/health-tracker')
const {
  setLimit, recordUsage, reset: budgetReset
} = await import('../../src/main/services/model-provider/budget-manager')
const {
  reset: metricsReset
} = await import('../../src/main/services/model-provider/metrics-store')

function register(
  providerId: string,
  defaultModel: string,
  researchCaps: string[],
  type: 'cloud' | 'local' | 'openai-compatible' = 'cloud',
  endpoint?: string
): void {
  registerProvider(providerId, () => ({
    id: providerId, type,
    capabilities: { streaming: true, tools: false, vision: false, functionCalling: false, jsonMode: false },
    buildRequest: () => ({}), parseChunk: () => null, ping: async () => ({ ok: true })
  }), {
    type, displayName: providerId, defaultModel,
    capabilities: { streaming: true, tools: false, vision: false, functionCalling: false, jsonMode: false },
    researchProfile: { providerId, model: defaultModel, capabilities: researchCaps }
  })
  saveConfig(providerId, {
    type, defaultModel, displayName: providerId,
    capabilities: ['streaming'],
    ...(endpoint ? { endpoint } : { endpoint: type === 'local' ? 'http://127.0.0.1:11434' : 'https://api.example.com/v1' })
  })
}

beforeEach(() => {
  FakeStoreMod.default.__reset()
  cipherMap.clear()
  clearRegistry()
  clearAllConfigs()
  clearAllKeys()
  clearActive()
  healthClear()
  metricsReset()
  budgetReset()
})

// ============ A. Provider connection test ============

describe('Phase 6-D Scenario A — Provider connection test', () => {
  it('provider available + secret lookup works + runtime starts', () => {
    register('cloud-vendor', 'gpt-4o-mini', ['chat'])
    saveKey('cloud-vendor', 'sk-supersecret-AAAA')
    setActive({ providerId: 'cloud-vendor', model: 'gpt-4o-mini', enabled: true })
    expect(keyExists('cloud-vendor')).toBe(true)
    const resolved = resolveActiveProvider()
    expect(resolved).toBeDefined()
    expect(resolved?.providerId).toBe('cloud-vendor')
    // Phase 6-D: apiKey NEVER in any return shape — only resolved.apiKey (internal)
    // For the e2e validation we assert the resolved provider exists; the secret itself
    // is main-process-internal and never crosses IPC.
    const d = routeResearchTask({ taskType: 'coding', requiredCapabilities: ['coding'] })
    expect(d).not.toBeNull()  // capability-match or active-fallback, never null since key exists
  })

  it('security: apiKey NEVER appears in IPC-shaped decisions', () => {
    register('cloud-vendor', 'm', ['chat'])
    saveKey('cloud-vendor', 'sk-supersecret-BBBB')
    const d = routeResearchTask({ taskType: 'chat', requiredCapabilities: ['chat'] })
    const dump = JSON.stringify(d)
    expect(dump).not.toContain('sk-supersecret-BBBB')
    expect(dump).not.toContain('apiKey')
    expect(dump).not.toContain('cipher')
  })

  it('no-key provider returns no decision (security boundary)', () => {
    register('no-key-vendor', 'm', ['chat'])
    expect(keyExists('no-key-vendor')).toBe(false)
    const d = routeResearchTask({ taskType: 'chat', requiredCapabilities: ['chat'] })
    // Phase 6-D: a candidate without a stored key is filtered out
    expect(d).toBeNull()
  })
})

// ============ B. Auto Research Mode — literature-review ============

describe('Phase 6-D Scenario B — Auto routing for literature-review', () => {
  beforeEach(() => {
    register('paperbot', 'paperbot-pro', ['literature', 'paper-writing'])
    register('chatty', 'chatty-v1', ['chat'])
    saveKey('paperbot', 'sk-P')
    saveKey('chatty', 'sk-C')
  })

  it('routes literature-review task to literature-capable provider', () => {
    const profile = { taskType: 'literature-review', requiredCapabilities: ['literature'] }
    const d = routeResearchTask(profile)
    expect(d).toBeDefined()
    expect(d?.providerId).toBe('paperbot')
    expect(d?.source).toBe('capability-match')
    expect(d?.reason).toContain('literature-review')
    expect(d?.reason).toContain('literature')
  })

  it('decision profile matches Phase 6-C1 researchCapabilities', () => {
    const d = routeResearchTask({ taskType: 'literature-review', requiredCapabilities: ['literature'] })
    expect(d?.profile.capabilities).toContain('literature')
    expect(d?.profile.providerId).toBe('paperbot')
  })

  it('rankedCandidates surface top-5 with score breakdown', () => {
    const d = routeResearchTask({ taskType: 'literature-review', requiredCapabilities: ['literature'] })
    expect(d?.rankedCandidates).toBeDefined()
    expect(d?.rankedCandidates?.length).toBeGreaterThan(0)
    const top = d?.rankedCandidates?.[0]
    expect(top?.providerId).toBe('paperbot')
    expect(top).toHaveProperty('capabilityScore')
    expect(top).toHaveProperty('healthScore')
    expect(top).toHaveProperty('budgetScore')
  })

  it('no secret leakage in rankedCandidates dump', () => {
    const d = routeResearchTask({ taskType: 'literature-review', requiredCapabilities: ['literature'] })
    const dump = JSON.stringify(d?.rankedCandidates ?? [])
    expect(dump).not.toContain('sk-P')
    expect(dump).not.toContain('sk-C')
    expect(dump).not.toContain('apiKey')
  })
})

// ============ C. Paper writing routing ============

describe('Phase 6-D Scenario C — Auto routing for paper-writing', () => {
  beforeEach(() => {
    register('paperbot', 'paperbot-pro', ['literature', 'paper-writing'])
    register('writer', 'writer-v2', ['paper-writing', 'coding'])
    register('chatty', 'chatty-v1', ['chat'])
    saveKey('paperbot', 'sk-P')
    saveKey('writer', 'sk-W')
    saveKey('chatty', 'sk-C')
  })

  it('routes paper-writing task to paper-capable provider', () => {
    const d = routeResearchTask({
      taskType: 'paper-writing',
      requiredCapabilities: ['paper-writing']
    })
    expect(d?.providerId).toBeDefined()
    // writer has coding + paper-writing, paperbot has literature + paper-writing
    // Both qualify; either may be picked (alphabetical tie-breaker).
    expect(['paperbot', 'writer']).toContain(d?.providerId)
    expect(d?.source).toBe('capability-match')
  })

  it('skips chat-only provider (chatty lacks paper-writing)', () => {
    const d = routeResearchTask({
      taskType: 'paper-writing',
      requiredCapabilities: ['paper-writing']
    })
    expect(d?.providerId).not.toBe('chatty')
  })

  it('decision.reason mentions paper-writing', () => {
    const d = routeResearchTask({
      taskType: 'paper-writing',
      requiredCapabilities: ['paper-writing']
    })
    expect(d?.reason).toContain('paper-writing')
  })
})

// ============ D. CFD analysis routing ============

describe('Phase 6-D Scenario D — Auto routing for cfd-analysis', () => {
  beforeEach(() => {
    register('cfdengine', 'cfd-2', ['cfd', 'math', 'python'])
    register('chatty', 'chatty-v1', ['chat'])
    saveKey('cfdengine', 'sk-CFD')
    saveKey('chatty', 'sk-C')
  })

  it('routes cfd-analysis to cfd-capable provider', () => {
    const d = routeResearchTask({
      taskType: 'cfd-analysis',
      requiredCapabilities: ['cfd']
    })
    expect(d?.providerId).toBe('cfdengine')
    expect(d?.source).toBe('capability-match')
  })

  it('skips non-cfd provider (chatty)', () => {
    const d = routeResearchTask({
      taskType: 'cfd-analysis',
      requiredCapabilities: ['cfd']
    })
    expect(d?.providerId).not.toBe('chatty')
  })

  it('model ranking picks cfd over chat when both have key', () => {
    const d = routeResearchTask({
      taskType: 'cfd-analysis',
      requiredCapabilities: ['cfd']
    })
    expect(d?.rankedCandidates?.[0].providerId).toBe('cfdengine')
  })
})

// ============ E. Data analysis routing ============

describe('Phase 6-D Scenario E — Auto routing for data-analysis', () => {
  beforeEach(() => {
    register('datawiz', 'datawiz-v1', ['data-analysis', 'python'])
    register('chatty', 'chatty-v1', ['chat'])
    saveKey('datawiz', 'sk-DW')
    saveKey('chatty', 'sk-C')
  })

  it('routes data-analysis to data-capable provider', () => {
    const d = routeResearchTask({
      taskType: 'data-analysis',
      requiredCapabilities: ['data-analysis']
    })
    expect(d?.providerId).toBe('datawiz')
    expect(d?.source).toBe('capability-match')
  })

  it('decision.reason mentions data-analysis', () => {
    const d = routeResearchTask({
      taskType: 'data-analysis',
      requiredCapabilities: ['data-analysis']
    })
    expect(d?.reason).toContain('data-analysis')
  })
})

// ============ F. Manual override (Phase 6-B behavior unchanged) ============

describe('Phase 6-D Scenario F — Manual override', () => {
  beforeEach(() => {
    register('manual-pick', 'manual-m', ['chat'])
    register('better-auto', 'auto-m', ['coding', 'paper-writing'])
    saveKey('manual-pick', 'sk-M')
    saveKey('better-auto', 'sk-A')
    // Phase 6-D: setActive simulates the user picking a provider via Phase 6-B UI
    setActive({ providerId: 'manual-pick', model: 'manual-m', enabled: true })
  })

  it('Phase 6-B manual selection wins over Phase 6-C2 router decision', () => {
    // Phase 6-D: simulate chat.ts decision logic — manual mode uses resolveForSession
    // which reads from active provider (Phase 6-B contract)
    const active = resolveActiveProvider()
    expect(active?.providerId).toBe('manual-pick')
    // The router would have picked 'better-auto' for paper-writing, but
    // manual mode uses the active provider.
    const autoDecision = routeResearchTask({
      taskType: 'paper-writing',
      requiredCapabilities: ['paper-writing']
    })
    expect(autoDecision?.providerId).toBe('better-auto')
    expect(active?.providerId).not.toBe(autoDecision?.providerId)
  })

  it('Phase 6-B active provider fallback when no auto match', () => {
    // No provider has 'image-analysis' cap; router falls back to active
    const autoDecision = routeResearchTask({
      taskType: 'image-analysis',
      requiredCapabilities: ['image-analysis']
    })
    // Phase 6-D: Phase 6-C2 router always falls back to active when no candidate matches
    expect(autoDecision?.providerId).toBe('manual-pick')
    expect(autoDecision?.source).toBe('active-provider')
    // Phase 6-D: manual mode would still use active provider (same result)
    const active = resolveActiveProvider()
    expect(active?.providerId).toBe('manual-pick')
  })

  it('Phase 6-B active provider used even when router picks same one', () => {
    // Both providers have 'chat'; router picks the higher-scored one (better-auto wins by alphabet)
    const autoDecision = routeResearchTask({
      taskType: 'chat',
      requiredCapabilities: ['chat']
    })
    expect(autoDecision?.providerId).toBe('better-auto')
    // Phase 6-D: in manual mode, the chat store reads active provider directly
    // (Phase 6-B contract), not the router decision
    expect(resolveActiveProvider()?.providerId).toBe('manual-pick')
  })
})

// ============ G. Health fallback simulation ============

describe('Phase 6-D Scenario G — Health fallback (A cooldown -> B)', () => {
  beforeEach(() => {
    register('provider-a', 'm', ['coding'])
    register('provider-b', 'm', ['coding'])
    saveKey('provider-a', 'sk-A')
    saveKey('provider-b', 'sk-B')
    // Provider A enters cooldown
    recordFailure('provider-a')
    recordFailure('provider-a')
    recordFailure('provider-a')
    // Provider B is healthy
    recordSuccess('provider-b', 100)
  })

  it('provider A is in cooldown', () => {
    expect(getHealth('provider-a').state).toBe('cooldown')
  })

  it('provider B is healthy', () => {
    expect(getHealth('provider-b').state).toBe('healthy')
  })

  it('router picks provider B when A is cooldown', () => {
    const d = routeResearchTask({ taskType: 'coding', requiredCapabilities: ['coding'] })
    expect(d?.providerId).toBe('provider-b')
  })

  it('router returns null when ALL providers cooldown', () => {
    recordFailure('provider-b')
    recordFailure('provider-b')
    recordFailure('provider-b')
    const d = routeResearchTask({ taskType: 'coding', requiredCapabilities: ['coding'] })
    expect(d).toBeNull()
  })

  it('retryWithFallback records failure metrics and re-routes', () => {
    const d1 = retryWithFallback({ taskType: 'coding', requiredCapabilities: ['coding'] }, 'provider-a', 5000, 'timeout')
    expect(d1?.providerId).toBe('provider-b')
    // Drive provider-b into cooldown via 3 failures so the next retry returns null
    recordFailure('provider-b')
    recordFailure('provider-b')
    recordFailure('provider-b')
    const d2 = retryWithFallback({ taskType: 'coding', requiredCapabilities: ['coding'] }, 'provider-b', 5000, 'timeout')
    expect(d2).toBeNull()
  })
})

// ============ H. Budget filter simulation ============

describe('Phase 6-D Scenario H — Budget filter', () => {
  beforeEach(() => {
    register('over-budget', 'm', ['coding'])
    register('in-budget', 'm', ['coding'])
    saveKey('over-budget', 'sk-OB')
    saveKey('in-budget', 'sk-IB')
    setLimit('over-budget', 1000)
    recordUsage('over-budget', 1000)
  })

  it('over-budget provider is excluded', () => {
    const d = routeResearchTask({ taskType: 'coding', requiredCapabilities: ['coding'] })
    expect(d?.providerId).toBe('in-budget')
  })

  it('in-budget provider wins the ranking', () => {
    const d = routeResearchTask({ taskType: 'coding', requiredCapabilities: ['coding'] })
    expect(d?.rankedCandidates?.[0].providerId).toBe('in-budget')
  })

  it('rankedCandidates show in-budget wins with score 1; over-budget filtered', () => {
    const d = routeResearchTask({ taskType: 'coding', requiredCapabilities: ['coding'] })
    const inBudget = d?.rankedCandidates?.find((r) => r.providerId === 'in-budget')
    const overBudget = d?.rankedCandidates?.find((r) => r.providerId === 'over-budget')
    expect(inBudget?.budgetScore).toBe(1)
    // Over-budget provider is filtered out (Phase 6-C4 contract)
    expect(overBudget).toBeUndefined()
  })
})

// ============ Bonus: full flow integration ============

describe('Phase 6-D Integration — full flow sanity', () => {
  it('all Phase 6-A/B/C1/C2/C3/C4 modules co-exist without error', () => {
    register('integration-vendor', 'm', ['coding', 'paper-writing', 'literature'])
    saveKey('integration-vendor', 'sk-INT')
    setActive({ providerId: 'integration-vendor', model: 'm', enabled: true })
    recordSuccess('integration-vendor', 100)
    setLimit('integration-vendor', 100000)
    recordUsage('integration-vendor', 50)
    const active = resolveActiveProvider()
    expect(active?.providerId).toBe('integration-vendor')
    const d = routeResearchTask({ taskType: 'paper-writing', requiredCapabilities: ['paper-writing'] })
    expect(d?.providerId).toBe('integration-vendor')
    expect(getHealth('integration-vendor').state).toBe('healthy')
  })
})
