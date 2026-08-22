// Phase 6-A4 Model Provider Store tests.
//
// Coverage:
//   - State shape: providers / activeProviderId / activeModel / loading / lastError
//   - loadProviders: success / failure / preserves connectionStatus across reload
//   - saveProvider: success / failure
//   - removeProvider: success / clears active if same id
//   - testProvider: success / failure / connectionStatus transitions
//   - setActiveProvider / setActiveModel
//   - saveApiKey / removeApiKey
//   - getters: activeProvider / providersWithKey / providersMissingKey
//   - SECURITY: store never holds apiKey value (IPC mock asserts)
//
// Phase 6-A4 strict: store mocks window.api.model IPC; renderer-side tests.

import { describe, it, expect, beforeEach, vi } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { useModelProviderStore } from '../../src/renderer/src/stores/model-provider'
import type { ModelProviderConfig, ModelTestProviderResult } from '../../src/shared/preload-api'

// ============ Test fixtures ============

function makeConfig(overrides: Partial<ModelProviderConfig> = {}): ModelProviderConfig {
  return {
    providerId: 'openai',
    type: 'openai-compatible',
    defaultModel: 'gpt-4o-mini',
    displayName: 'OpenAI',
    capabilities: ['streaming'],
    updatedAt: Date.now(),
    ...overrides
  }
}

function makeMockApi(opts: {
  configs?: ModelProviderConfig[]
  hasKey?: boolean[]
  saveConfig?: ReturnType<typeof vi.fn>
  deleteConfig?: ReturnType<typeof vi.fn>
  testProvider?: ReturnType<typeof vi.fn>
  saveKey?: ReturnType<typeof vi.fn>
  deleteKey?: ReturnType<typeof vi.fn>
} = {}) {
  const configs = opts.configs ?? []
  const hasKey = opts.hasKey ?? configs.map(() => false)
  const listConfigs = vi.fn(async () => ({ configs, hasKey }))
  const listProviders = vi.fn(async () => ({ providerIds: hasKey.map((_, i) => configs[i]?.providerId ?? '') }))
  const saveConfig = opts.saveConfig ?? vi.fn(async () => ({ ok: true as const, exists: true }))
  const deleteConfig = opts.deleteConfig ?? vi.fn(async () => ({ ok: true as const, exists: true }))
  const testProvider = opts.testProvider ?? vi.fn(async () => ({ ok: true, latencyMs: 100 }))
  const saveKey = opts.saveKey ?? vi.fn(async () => ({ ok: true as const, exists: true }))
  const deleteKey = opts.deleteKey ?? vi.fn(async () => ({ ok: true as const, exists: true }))
  const keyExists = vi.fn(async () => ({ exists: true }))

  globalThis.window = {
    api: {
      model: { listProviders, saveKey, deleteKey, keyExists, listConfigs, saveConfig, deleteConfig, testProvider }
    }
  } as unknown as Window & typeof globalThis
  return { listConfigs, listProviders, saveConfig, deleteConfig, testProvider, saveKey, deleteKey, keyExists }
}

beforeEach(() => {
  setActivePinia(createPinia())
})

// ============ Tests ============

describe('Phase 6-A4 model-provider store — initial state', () => {
  it('starts with empty providers, no active, loading=false', () => {
    makeMockApi({ configs: [] })
    const store = useModelProviderStore()
    expect(store.providers).toEqual([])
    expect(store.activeProviderId).toBeNull()
    expect(store.activeModel).toBeNull()
    expect(store.loading).toBe(false)
    expect(store.lastError).toBeNull()
  })
})

describe('Phase 6-A4 model-provider store — loadProviders', () => {
  it('populates providers from listConfigs IPC', async () => {
    makeMockApi({
      configs: [makeConfig({ providerId: 'openai' }), makeConfig({ providerId: 'ollama', type: 'local' })],
      hasKey: [true, false]
    })
    const store = useModelProviderStore()
    await store.loadProviders()
    expect(store.providers).toHaveLength(2)
    expect(store.providers[0].config.providerId).toBe('openai')
    expect(store.providers[0].hasKey).toBe(true)
    expect(store.providers[1].hasKey).toBe(false)
    expect(store.providers[0].connectionStatus).toBe('unknown')
  })
  it('sets lastError when IPC rejects', async () => {
    const listConfigs = vi.fn(async () => {
      throw new Error('ipc fail')
    })
    globalThis.window = { api: { model: { listConfigs } } } as unknown as Window & typeof globalThis
    const store = useModelProviderStore()
    await expect(store.loadProviders()).rejects.toThrow('ipc fail')
    expect(store.lastError).toBe('ipc fail')
    expect(store.loading).toBe(false)
  })
  it('preserves connectionStatus across reload', async () => {
    makeMockApi({
      configs: [makeConfig({ providerId: 'openai' })],
      hasKey: [true]
    })
    const store = useModelProviderStore()
    await store.loadProviders()
    await store.testProvider('openai')
    expect(store.providers[0].connectionStatus).toBe('connected')
    // reload again -> should preserve connectionStatus
    await store.loadProviders()
    expect(store.providers[0].connectionStatus).toBe('connected')
  })
  it('clears providers when listConfigs returns empty', async () => {
    makeMockApi({ configs: [makeConfig({ providerId: 'openai' })] })
    const store = useModelProviderStore()
    await store.loadProviders()
    expect(store.providers).toHaveLength(1)
    makeMockApi({ configs: [] })
    await store.loadProviders()
    expect(store.providers).toEqual([])
  })
})

describe('Phase 6-A4 model-provider store — saveProvider', () => {
  it('calls IPC and reloads', async () => {
    const saveConfig = vi.fn(async () => ({ ok: true as const, exists: true }))
    makeMockApi({ saveConfig })
    const store = useModelProviderStore()
    await store.saveProvider('my-vendor', {
      type: 'cloud',
      defaultModel: 'm',
      displayName: 'My Vendor',
      capabilities: ['streaming']
    })
    expect(saveConfig).toHaveBeenCalledWith('my-vendor', {
      type: 'cloud',
      defaultModel: 'm',
      displayName: 'My Vendor',
      capabilities: ['streaming']
    })
  })
  it('propagates IPC error', async () => {
    const saveConfig = vi.fn(async () => {
      throw new Error('bad config')
    })
    makeMockApi({ saveConfig })
    const store = useModelProviderStore()
    await expect(store.saveProvider('foo', {
      type: 'cloud',
      defaultModel: 'm',
      displayName: 'X',
      capabilities: []
    })).rejects.toThrow('bad config')
    expect(store.lastError).toBe('bad config')
  })
})

describe('Phase 6-A4 model-provider store — removeProvider', () => {
  it('calls IPC delete and reloads', async () => {
    const deleteConfig = vi.fn(async () => ({ ok: true as const, exists: true }))
    makeMockApi({ configs: [makeConfig({ providerId: 'openai' })], hasKey: [false], deleteConfig })
    const store = useModelProviderStore()
    await store.loadProviders()
    await store.removeProvider('openai')
    expect(deleteConfig).toHaveBeenCalledWith('openai')
  })
  it('clears activeProviderId/activeModel when removing active', async () => {
    makeMockApi({ configs: [makeConfig({ providerId: 'openai' })], hasKey: [true] })
    const store = useModelProviderStore()
    await store.loadProviders()
    store.setActiveProvider('openai')
    store.setActiveModel('gpt-4o-mini')
    await store.removeProvider('openai')
    expect(store.activeProviderId).toBeNull()
    expect(store.activeModel).toBeNull()
  })
})

describe('Phase 6-A4 model-provider store — testProvider', () => {
  it('success: sets status=connected and stores latency', async () => {
    const testProvider = vi.fn(async () => ({ ok: true, latencyMs: 250 }))
    makeMockApi({ configs: [makeConfig({ providerId: 'openai' })], hasKey: [true], testProvider })
    const store = useModelProviderStore()
    await store.loadProviders()
    const r = await store.testProvider('openai')
    expect(r.ok).toBe(true)
    expect(store.providers[0].connectionStatus).toBe('connected')
    expect(store.providers[0].lastLatencyMs).toBe(250)
    expect(store.providers[0].lastError).toBeUndefined()
  })
  it('failure: sets status=failed and stores error', async () => {
    const testProvider = vi.fn(async () => ({ ok: false, error: 'HTTP 500' }))
    makeMockApi({ configs: [makeConfig({ providerId: 'openai' })], hasKey: [true], testProvider })
    const store = useModelProviderStore()
    await store.loadProviders()
    await store.testProvider('openai')
    expect(store.providers[0].connectionStatus).toBe('failed')
    expect(store.providers[0].lastError).toBe('HTTP 500')
  })
  it('transitions checking -> connected in sequence', async () => {
    let resolveTest: (r: ModelTestProviderResult) => void = () => {}
    const testProvider = vi.fn(async () => new Promise<ModelTestProviderResult>((res) => { resolveTest = res }))
    makeMockApi({ configs: [makeConfig({ providerId: 'openai' })], hasKey: [true], testProvider })
    const store = useModelProviderStore()
    await store.loadProviders()
    const inFlight = store.testProvider('openai')
    // Status should be 'checking' immediately
    expect(store.providers[0].connectionStatus).toBe('checking')
    resolveTest({ ok: true, latencyMs: 50 })
    await inFlight
    expect(store.providers[0].connectionStatus).toBe('connected')
  })
  it('IPC throw sets status=failed and returns ok:false', async () => {
    const testProvider = vi.fn(async () => {
      throw new Error('network down')
    })
    makeMockApi({ configs: [makeConfig({ providerId: 'openai' })], hasKey: [true], testProvider })
    const store = useModelProviderStore()
    await store.loadProviders()
    const r = await store.testProvider('openai')
    expect(r.ok).toBe(false)
    expect(store.providers[0].connectionStatus).toBe('failed')
    expect(store.providers[0].lastError).toBe('network down')
  })
})

describe('Phase 6-A4 model-provider store — setActiveProvider / setActiveModel', () => {
  it('setActiveProvider updates activeProviderId', () => {
    makeMockApi()
    const store = useModelProviderStore()
    store.setActiveProvider('openai')
    expect(store.activeProviderId).toBe('openai')
  })
  it('setActiveProvider(null) clears activeProviderId AND activeModel', () => {
    makeMockApi()
    const store = useModelProviderStore()
    store.setActiveProvider('openai')
    store.setActiveModel('gpt-4o')
    store.setActiveProvider(null)
    expect(store.activeProviderId).toBeNull()
    expect(store.activeModel).toBeNull()
  })
  it('setActiveModel updates activeModel independently', () => {
    makeMockApi()
    const store = useModelProviderStore()
    store.setActiveModel('gpt-4o-mini')
    expect(store.activeModel).toBe('gpt-4o-mini')
  })
})

describe('Phase 6-A4 model-provider store — saveApiKey / removeApiKey', () => {
  it('saveApiKey calls IPC and reloads', async () => {
    const saveKey = vi.fn(async () => ({ ok: true as const, exists: true }))
    makeMockApi({ saveKey })
    const store = useModelProviderStore()
    await store.saveApiKey('openai', 'sk-test')
    expect(saveKey).toHaveBeenCalledWith('openai', 'sk-test')
  })
  it('removeApiKey calls IPC and reloads', async () => {
    const deleteKey = vi.fn(async () => ({ ok: true as const, exists: true }))
    makeMockApi({ deleteKey })
    const store = useModelProviderStore()
    await store.removeApiKey('openai')
    expect(deleteKey).toHaveBeenCalledWith('openai')
  })
})

describe('Phase 6-A4 model-provider store — getters', () => {
  it('activeProvider returns entry with matching id', async () => {
    makeMockApi({
      configs: [makeConfig({ providerId: 'openai' }), makeConfig({ providerId: 'ollama', type: 'local' })],
      hasKey: [true, false]
    })
    const store = useModelProviderStore()
    await store.loadProviders()
    store.setActiveProvider('ollama')
    expect(store.activeProvider?.config.providerId).toBe('ollama')
  })
  it('activeProvider returns null when not set', () => {
    makeMockApi()
    const store = useModelProviderStore()
    expect(store.activeProvider).toBeNull()
  })
  it('providersWithKey filters to entries with hasKey=true', async () => {
    makeMockApi({
      configs: [makeConfig({ providerId: 'openai' }), makeConfig({ providerId: 'ollama', type: 'local' }), makeConfig({ providerId: 'qwen', type: 'cloud' })],
      hasKey: [true, false, true]
    })
    const store = useModelProviderStore()
    await store.loadProviders()
    expect(store.providersWithKey.map((p) => p.config.providerId)).toEqual(['openai', 'qwen'])
  })
  it('providersMissingKey filters to entries with hasKey=false', async () => {
    makeMockApi({
      configs: [makeConfig({ providerId: 'openai' }), makeConfig({ providerId: 'ollama', type: 'local' })],
      hasKey: [true, false]
    })
    const store = useModelProviderStore()
    await store.loadProviders()
    expect(store.providersMissingKey.map((p) => p.config.providerId)).toEqual(['ollama'])
  })
})

describe('Phase 6-A4 model-provider store — security', () => {
  it('store never contains apiKey field', async () => {
    makeMockApi({ configs: [makeConfig({ providerId: 'openai' })], hasKey: [true] })
    const store = useModelProviderStore()
    await store.loadProviders()
    // walk all state to ensure no key-like field
    const dump = JSON.stringify({
      providers: store.providers,
      activeProviderId: store.activeProviderId,
      activeModel: store.activeModel
    })
    expect(dump).not.toMatch(/sk-/)
    expect(dump).not.toMatch(/apiKey/)
    expect(dump).not.toMatch(/api_key/)
    expect(dump).not.toMatch(/secret/)
  })
  it('saveApiKey passes the key ONLY through IPC, not store state', async () => {
    let capturedKey: string | null = null
    const saveKey = vi.fn(async (id: string, key: string) => {
      capturedKey = key
      return { ok: true as const, exists: true }
    })
    makeMockApi({ saveKey })
    const store = useModelProviderStore()
    await store.saveApiKey('openai', 'sk-supersecret')
    expect(capturedKey).toBe('sk-supersecret')
    // store state must not contain the key
    const dump = JSON.stringify(store.$state)
    expect(dump).not.toContain('sk-supersecret')
  })
})

describe('Phase 6-A4 model-provider store — reset', () => {
  it('reset clears providers / active / lastError', async () => {
    makeMockApi({ configs: [makeConfig({ providerId: 'openai' })], hasKey: [true] })
    const store = useModelProviderStore()
    await store.loadProviders()
    store.setActiveProvider('openai')
    store.reset()
    expect(store.providers).toEqual([])
    expect(store.activeProviderId).toBeNull()
    expect(store.lastError).toBeNull()
  })
})
