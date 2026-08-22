// Phase 6-B model-selector store tests.
//
// Coverage (>= 25 cases):
//   - Initial state (2)
//   - loadAvailable (5)
//   - select / clear (4)
//   - selectForSession (4)
//   - resolveForSession (3)
//   - capability display (3)
//   - security: no apiKey field, no secret in dumps (4)
//
// Phase 6-B strict: store mocks window.api.model IPC; renderer-side tests.

import { describe, it, expect, beforeEach, vi } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { useModelSelectorStore, type AvailableProvider } from '../../src/renderer/src/stores/model-selector'
import { isValidConversationModelContext, capabilityLabel } from '../../src/shared/model/conversation-model'

// ============ Test fixtures ============

function makeApi(opts: {
  configs?: Array<{
    providerId: string
    type: 'cloud' | 'local' | 'openai-compatible'
    defaultModel: string
    displayName: string
    capabilities: string[]
    updatedAt?: number
  }>
  hasKey?: boolean[]
  listConfigsError?: Error
} = {}) {
  const configs = opts.configs ?? []
  const hasKey = opts.hasKey ?? configs.map(() => false)
  const listConfigs = opts.listConfigsError
    ? vi.fn(async () => { throw opts.listConfigsError })
    : vi.fn(async () => ({ configs, hasKey }))
  globalThis.window = { api: { model: { listConfigs, keyExists: vi.fn() } } } as unknown as Window & typeof globalThis
  return { listConfigs }
}

beforeEach(() => {
  setActivePinia(createPinia())
})

// ============ Initial state ============

describe('Phase 6-B model-selector — initial state', () => {
  it('starts empty: no providers, no selection, no overrides', () => {
    makeApi()
    const store = useModelSelectorStore()
    expect(store.available).toEqual([])
    expect(store.selected).toBeNull()
    expect(store.sessionOverrides.size).toBe(0)
    expect(store.loading).toBe(false)
    expect(store.lastError).toBeNull()
  })
  it('computed getters reflect empty initial state', () => {
    makeApi()
    const store = useModelSelectorStore()
    expect(store.selectedId).toBeNull()
    expect(store.selectedModel).toBeNull()
    expect(store.selectedDisplayName).toBeNull()
    expect(store.selectedCapabilities).toEqual([])
    expect(store.availableWithKey).toEqual([])
  })
})

// ============ loadAvailable ============

describe('Phase 6-B model-selector — loadAvailable', () => {
  it('populates available from listConfigs IPC', async () => {
    makeApi({
      configs: [
        { providerId: 'openai', type: 'openai-compatible', defaultModel: 'gpt-4o-mini', displayName: 'OpenAI', capabilities: ['streaming'] },
        { providerId: 'ollama', type: 'local', defaultModel: 'qwen3:8b', displayName: 'Ollama', capabilities: ['streaming', 'tools'] }
      ],
      hasKey: [true, false]
    })
    const store = useModelSelectorStore()
    await store.loadAvailable()
    expect(store.available).toHaveLength(2)
    expect(store.available[0].providerId).toBe('openai')
    expect(store.available[0].hasKey).toBe(true)
    expect(store.available[1].hasKey).toBe(false)
  })
  it('parses capabilities string[] into ModelCapability[]', async () => {
    makeApi({
      configs: [{ providerId: 'openai', type: 'cloud', defaultModel: 'm', displayName: 'X', capabilities: ['streaming', 'tools', 'vision'] }],
      hasKey: [true]
    })
    const store = useModelSelectorStore()
    await store.loadAvailable()
    expect(store.available[0].capabilities).toEqual(['streaming', 'tools', 'vision'])
  })
  it('sets lastError when IPC rejects', async () => {
    makeApi({ listConfigsError: new Error('ipc fail') })
    const store = useModelSelectorStore()
    await expect(store.loadAvailable()).rejects.toThrow('ipc fail')
    expect(store.lastError).toBe('ipc fail')
    expect(store.loading).toBe(false)
  })
  it('sets loading=true during the call', async () => {
    let resolveList: (r: unknown) => void = () => {}
    const listConfigs = vi.fn(async () => new Promise<unknown>((res) => { resolveList = res }))
    globalThis.window = { api: { model: { listConfigs, keyExists: vi.fn() } } } as unknown as Window & typeof globalThis
    const store = useModelSelectorStore()
    const inFlight = store.loadAvailable()
    expect(store.loading).toBe(true)
    resolveList({ configs: [], hasKey: [] })
    await inFlight
    expect(store.loading).toBe(false)
  })
  it('clears providers when listConfigs returns empty', async () => {
    makeApi({
      configs: [{ providerId: 'openai', type: 'openai-compatible', defaultModel: 'm', displayName: 'X', capabilities: ['streaming'] }],
      hasKey: [true]
    })
    const store = useModelSelectorStore()
    await store.loadAvailable()
    expect(store.available).toHaveLength(1)
    makeApi({ configs: [] })
    await store.loadAvailable()
    expect(store.available).toEqual([])
  })
})

// ============ select / clear ============

describe('Phase 6-B model-selector — select / clear', () => {
  beforeEach(() => {
    makeApi({
      configs: [
        { providerId: 'openai', type: 'openai-compatible', defaultModel: 'gpt-4o-mini', displayName: 'OpenAI', capabilities: ['streaming', 'tools'] },
        { providerId: 'ollama', type: 'local', defaultModel: 'qwen3:8b', displayName: 'Ollama', capabilities: ['streaming'] }
      ],
      hasKey: [true, false]
    })
  })
  it('select(providerId) uses provider defaultModel', async () => {
    const store = useModelSelectorStore()
    await store.loadAvailable()
    await store.select('openai')
    expect(store.selected?.providerId).toBe('openai')
    expect(store.selected?.model).toBe('gpt-4o-mini')
    expect(store.selected?.displayName).toBe('OpenAI')
    expect(store.selected?.capabilities).toEqual(['streaming', 'tools'])
  })
  it('select(providerId, model) uses explicit model', async () => {
    const store = useModelSelectorStore()
    await store.loadAvailable()
    await store.select('openai', 'gpt-4o')
    expect(store.selected?.model).toBe('gpt-4o')
  })
  it('select throws on unknown providerId', async () => {
    const store = useModelSelectorStore()
    await store.loadAvailable()
    await expect(store.select('not-registered')).rejects.toThrow(/unknown providerId/)
  })
  it('clear() resets selected to null', async () => {
    const store = useModelSelectorStore()
    await store.loadAvailable()
    await store.select('openai')
    store.clear()
    expect(store.selected).toBeNull()
    expect(store.selectedId).toBeNull()
    expect(store.selectedModel).toBeNull()
  })
})

// ============ selectForSession ============

describe('Phase 6-B model-selector — selectForSession', () => {
  beforeEach(() => {
    makeApi({
      configs: [{ providerId: 'openai', type: 'openai-compatible', defaultModel: 'gpt-4o-mini', displayName: 'OpenAI', capabilities: ['streaming'] }],
      hasKey: [true]
    })
  })
  it('sets per-session override', async () => {
    const store = useModelSelectorStore()
    await store.loadAvailable()
    store.selectForSession('sess-1', { providerId: 'openai', model: 'gpt-4o', displayName: 'OpenAI' })
    expect(store.sessionOverrides.get('sess-1')?.model).toBe('gpt-4o')
  })
  it('null ctx removes the override', async () => {
    const store = useModelSelectorStore()
    await store.loadAvailable()
    store.selectForSession('sess-1', { providerId: 'openai', model: 'gpt-4o' })
    store.selectForSession('sess-1', null)
    expect(store.sessionOverrides.has('sess-1')).toBe(false)
  })
  it('empty sessionId is a no-op', async () => {
    const store = useModelSelectorStore()
    await store.loadAvailable()
    store.selectForSession('', { providerId: 'openai', model: 'gpt-4o' })
    expect(store.sessionOverrides.size).toBe(0)
  })
  it('different sessions get independent overrides', async () => {
    const store = useModelSelectorStore()
    await store.loadAvailable()
    store.selectForSession('a', { providerId: 'openai', model: 'm1' })
    store.selectForSession('b', { providerId: 'openai', model: 'm2' })
    expect(store.sessionOverrides.get('a')?.model).toBe('m1')
    expect(store.sessionOverrides.get('b')?.model).toBe('m2')
  })
})

// ============ resolveForSession ============

describe('Phase 6-B model-selector — resolveForSession', () => {
  beforeEach(() => {
    makeApi({
      configs: [{ providerId: 'openai', type: 'openai-compatible', defaultModel: 'gpt-4o-mini', displayName: 'OpenAI', capabilities: ['streaming'] }],
      hasKey: [true]
    })
  })
  it('returns null when nothing is set', async () => {
    const store = useModelSelectorStore()
    await store.loadAvailable()
    expect(store.resolveForSession('sess-1')).toBeNull()
  })
  it('returns global selection when no per-session override', async () => {
    const store = useModelSelectorStore()
    await store.loadAvailable()
    await store.select('openai', 'gpt-4o-mini')
    expect(store.resolveForSession('sess-1')?.providerId).toBe('openai')
  })
  it('per-session override wins over global selection', async () => {
    const store = useModelSelectorStore()
    await store.loadAvailable()
    await store.select('openai', 'gpt-4o-mini')
    store.selectForSession('sess-x', { providerId: 'openai', model: 'gpt-4o-turbo', displayName: 'OpenAI' })
    expect(store.resolveForSession('sess-x')?.model).toBe('gpt-4o-turbo')
    expect(store.resolveForSession('sess-y')?.model).toBe('gpt-4o-mini')
  })
})

// ============ capability display ============

describe('Phase 6-B model-selector — capability display', () => {
  it('capabilityLabel returns Phase 3 stable names', () => {
    expect(capabilityLabel('streaming')).toBe('streaming')
    expect(capabilityLabel('tools')).toBe('tools')
    expect(capabilityLabel('vision')).toBe('vision')
    expect(capabilityLabel('function-calling')).toBe('function-calling')
    expect(capabilityLabel('json-mode')).toBe('json-mode')
  })
  it('capabilityList returns capabilities of selected', async () => {
    makeApi({
      configs: [{ providerId: 'openai', type: 'openai-compatible', defaultModel: 'm', displayName: 'X', capabilities: ['streaming', 'tools', 'vision'] }],
      hasKey: [true]
    })
    const store = useModelSelectorStore()
    await store.loadAvailable()
    await store.select('openai')
    expect(store.capabilityList()).toEqual(['streaming', 'tools', 'vision'])
  })
  it('capabilityList falls back to [] when nothing selected', async () => {
    makeApi()
    const store = useModelSelectorStore()
    expect(store.capabilityList()).toEqual([])
  })
})

// ============ Security ============

describe('Phase 6-B model-selector — security (no apiKey anywhere)', () => {
  it('store state dump NEVER contains apiKey substring', async () => {
    makeApi({
      configs: [{ providerId: 'openai', type: 'openai-compatible', defaultModel: 'gpt-4o-mini', displayName: 'OpenAI', capabilities: ['streaming'] }],
      hasKey: [true]
    })
    const store = useModelSelectorStore()
    await store.loadAvailable()
    await store.select('openai')
    store.selectForSession('s', { providerId: 'openai', model: 'gpt-4o-mini' })
    const dump = JSON.stringify(store.$state)
    expect(dump).not.toContain('sk-')
    expect(dump).not.toContain('apiKey')
    expect(dump).not.toContain('api_key')
    expect(dump).not.toContain('secret')
    expect(dump).not.toContain('cipher')
  })
  it('isValidConversationModelContext rejects payloads with apiKey field', () => {
    expect(isValidConversationModelContext({
      providerId: 'openai',
      model: 'gpt-4o-mini',
      apiKey: 'sk-supersecret'  // forbidden
    })).toBe(false)
  })
  it('isValidConversationModelContext accepts clean context', () => {
    expect(isValidConversationModelContext({
      providerId: 'openai',
      model: 'gpt-4o-mini',
      displayName: 'OpenAI',
      capabilities: ['streaming']
    })).toBe(true)
  })
  it('availableProvider shape NEVER contains apiKey field', async () => {
    makeApi({
      configs: [{ providerId: 'openai', type: 'openai-compatible', defaultModel: 'gpt-4o-mini', displayName: 'OpenAI', capabilities: ['streaming'] }],
      hasKey: [true]
    })
    const store = useModelSelectorStore()
    await store.loadAvailable()
    const first = store.available[0] as AvailableProvider & { apiKey?: unknown }
    expect(first.apiKey).toBeUndefined()
    expect(JSON.stringify(first)).not.toContain('apiKey')
  })
})

// ============ reset ============

describe('Phase 6-B model-selector — reset', () => {
  it('clears all state', async () => {
    makeApi({
      configs: [{ providerId: 'openai', type: 'openai-compatible', defaultModel: 'gpt-4o-mini', displayName: 'OpenAI', capabilities: ['streaming'] }],
      hasKey: [true]
    })
    const store = useModelSelectorStore()
    await store.loadAvailable()
    await store.select('openai')
    store.selectForSession('s', { providerId: 'openai', model: 'gpt-4o-mini' })
    store.reset()
    expect(store.available).toEqual([])
    expect(store.selected).toBeNull()
    expect(store.sessionOverrides.size).toBe(0)
    expect(store.lastError).toBeNull()
  })
})
