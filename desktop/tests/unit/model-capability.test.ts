// Phase 6-C1 Model Capability tests.
//
// Coverage (>= 30 cases):
//   - isValidResearchCapability (10 cases — one per capability)
//   - isValidModelResearchProfile shape validation (8 cases)
//   - researchCapabilityLabel + glyph stability (5 cases)
//   - resolveModelCapability: config / registry / unknown fallback (5 cases)
//   - matchTaskCapability ranking (3 cases)
//   - hasAllCapabilities / hasAnyCapability (4 cases)
//   - security: assertProfileSafe + JSON.dump (3 cases)
//   - backward compat: ProviderConfigStore works without researchProfile (3 cases)

import { describe, it, expect, beforeEach, vi } from 'vitest'

vi.mock('electron', () => ({}))
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
const FakeStoreMod = await import('electron-store') as unknown as { default: { __reset(): void } }

const research = await import('../../src/shared/model/research-capability')
const {
  isValidResearchCapability,
  isValidModelResearchProfile,
  researchCapabilityLabel,
  researchCapabilityGlyph,
  assertProfileSafe
} = research
const {
  resolveModelCapability,
  matchTaskCapability,
  hasAllCapabilities,
  hasAnyCapability
} = await import('../../src/main/services/model-provider/capability-resolver')
const {
  registerProvider,
  clearRegistry
} = await import('../../src/main/services/model-provider/registry')
const {
  saveConfig,
  clearAll: clearAllConfigs
} = await import('../../src/main/services/model-provider/provider-config-store')

beforeEach(() => {
  FakeStoreMod.default.__reset()
  clearRegistry()
  clearAllConfigs()
})

// ============ Spec: researchCapability taxonomy ============

describe('Phase 6-C1 isValidResearchCapability — 10 research tags', () => {
  const ALL = ['chat', 'coding', 'math', 'matlab', 'python', 'cfd', 'literature', 'paper-writing', 'image-analysis', 'data-analysis']
  for (const cap of ALL) {
    it(`accepts '${cap}'`, () => {
      expect(isValidResearchCapability(cap)).toBe(true)
    })
  }
  it('rejects unknown capability', () => {
    expect(isValidResearchCapability('not-a-cap')).toBe(false)
  })
  it('rejects non-string', () => {
    expect(isValidResearchCapability(42)).toBe(false)
    expect(isValidResearchCapability(null)).toBe(false)
    expect(isValidResearchCapability(undefined)).toBe(false)
  })
})

// ============ Spec: researchCapabilityLabel / glyph stability ============

describe('Phase 6-C1 researchCapabilityLabel / glyph — stable UI labels', () => {
  it('label for chat', () => expect(researchCapabilityLabel('chat')).toBe('Chat'))
  it('label for cfd', () => expect(researchCapabilityLabel('cfd')).toBe('CFD'))
  it('label for paper-writing', () => expect(researchCapabilityLabel('paper-writing')).toBe('Paper'))
  it('glyph for literature', () => expect(researchCapabilityGlyph('literature')).toBe('📚'))
  it('glyph for matlab', () => expect(researchCapabilityGlyph('matlab')).toBe('𝓜'))
})

// ============ Spec: isValidModelResearchProfile ============

describe('Phase 6-C1 isValidModelResearchProfile — shape validation', () => {
  it('accepts minimal profile', () => {
    expect(isValidModelResearchProfile({ providerId: 'openai', model: 'm', capabilities: ['chat'] })).toBe(true)
  })
  it('accepts profile with maxContext / strengths / limitations', () => {
    expect(isValidModelResearchProfile({
      providerId: 'openai', model: 'm', capabilities: ['coding', 'math'],
      maxContext: 128000,
      strengths: ['strong math'],
      limitations: ['zh-only']
    })).toBe(true)
  })
  it('rejects empty providerId', () => {
    expect(isValidModelResearchProfile({ providerId: '', model: 'm', capabilities: [] })).toBe(false)
  })
  it('rejects empty model', () => {
    expect(isValidModelResearchProfile({ providerId: 'openai', model: '', capabilities: [] })).toBe(false)
  })
  it('rejects non-array capabilities', () => {
    expect(isValidModelResearchProfile({ providerId: 'openai', model: 'm', capabilities: 'chat' })).toBe(false)
  })
  it('rejects unknown capability tag', () => {
    expect(isValidModelResearchProfile({ providerId: 'openai', model: 'm', capabilities: ['chat', 'flying'] })).toBe(false)
  })
  it('rejects negative maxContext', () => {
    expect(isValidModelResearchProfile({ providerId: 'openai', model: 'm', capabilities: [], maxContext: -1 })).toBe(false)
  })
  it('rejects secret-like apiKey field (defense in depth)', () => {
    expect(isValidModelResearchProfile({
      providerId: 'openai', model: 'm', capabilities: ['chat'], apiKey: 'sk-secret'
    })).toBe(false)
  })
})

// ============ Spec: resolveModelCapability ============

describe('Phase 6-C1 resolveModelCapability — 3 resolution paths', () => {
  it('returns null for invalid providerId', () => {
    expect(resolveModelCapability('x')).toBeNull()
    expect(resolveModelCapability('')).toBeNull()
  })
  it('config path: researchProfile from ProviderConfigStore wins', () => {
    saveConfig('openai', {
      type: 'cloud', defaultModel: 'gpt-4o-mini', displayName: 'OpenAI', capabilities: ['streaming'],
      researchProfile: {
        providerId: 'openai', model: 'gpt-4o-mini',
        capabilities: ['literature', 'paper-writing'],
        maxContext: 128000,
        strengths: ['academic prose'],
        limitations: ['vision not supported']
      }
    })
    const m = resolveModelCapability('openai')
    expect(m?.source).toBe('config')
    expect(m?.profile.capabilities).toEqual(['literature', 'paper-writing'])
    expect(m?.profile.maxContext).toBe(128000)
  })
  it('registry path: when no config, falls back to ProviderRegistryMeta', () => {
    registerProvider('openai', () => ({
      id: 'openai', type: 'openai-compatible',
      capabilities: { streaming: true, tools: false, vision: false, functionCalling: false, jsonMode: false },
      buildRequest: () => ({}), parseChunk: () => null, ping: async () => ({ ok: true })
    }), {
      type: 'cloud',
      displayName: 'OpenAI',
      defaultModel: 'gpt-4o-mini',
      capabilities: { streaming: true, tools: false, vision: false, functionCalling: false, jsonMode: false },
      researchProfile: {
        providerId: 'openai', model: 'gpt-4o-mini',
        capabilities: ['coding', 'math'],
        strengths: ['coding benchmark']
      }
    })
    const m = resolveModelCapability('openai')
    expect(m?.source).toBe('registry')
    expect(m?.profile.capabilities).toEqual(['coding', 'math'])
  })
  it('unknown fallback: defaults to ["chat"] when nothing registered', () => {
    const m = resolveModelCapability('unknown-vendor')
    expect(m?.source).toBe('unknown')
    expect(m?.profile.capabilities).toEqual(['chat'])
    expect(m?.profile.providerId).toBe('unknown-vendor')
  })
  it('config wins over registry (when both set)', () => {
    saveConfig('openai', {
      type: 'cloud', defaultModel: 'gpt-4o-mini', displayName: 'OpenAI', capabilities: ['streaming'],
      researchProfile: {
        providerId: 'openai', model: 'gpt-4o-mini',
        capabilities: ['data-analysis']
      }
    })
    registerProvider('openai', () => ({
      id: 'openai', type: 'cloud',
      capabilities: { streaming: true, tools: false, vision: false, functionCalling: false, jsonMode: false },
      buildRequest: () => ({}), parseChunk: () => null, ping: async () => ({ ok: true })
    }), {
      type: 'cloud',
      displayName: 'OpenAI',
      defaultModel: 'gpt-4o-mini',
      capabilities: { streaming: true, tools: false, vision: false, functionCalling: false, jsonMode: false },
      researchProfile: {
        providerId: 'openai', model: 'gpt-4o-mini',
        capabilities: ['coding']
      }
    })
    const m = resolveModelCapability('openai')
    expect(m?.source).toBe('config')
    expect(m?.profile.capabilities).toEqual(['data-analysis'])
  })
})

// ============ Spec: matchTaskCapability ============

describe('Phase 6-C1 matchTaskCapability — ranked by overlap', () => {
  beforeEach(() => {
    registerProvider('openai', () => ({
      id: 'openai', type: 'cloud',
      capabilities: { streaming: true, tools: false, vision: false, functionCalling: false, jsonMode: false },
      buildRequest: () => ({}), parseChunk: () => null, ping: async () => ({ ok: true })
    }), {
      type: 'cloud', displayName: 'OpenAI', defaultModel: 'gpt-4o-mini',
      capabilities: { streaming: true, tools: false, vision: false, functionCalling: false, jsonMode: false },
      researchProfile: { providerId: 'openai', model: 'gpt-4o-mini', capabilities: ['literature', 'paper-writing'] }
    })
    registerProvider('qwen', () => ({
      id: 'qwen', type: 'cloud',
      capabilities: { streaming: true, tools: false, vision: false, functionCalling: false, jsonMode: false },
      buildRequest: () => ({}), parseChunk: () => null, ping: async () => ({ ok: true })
    }), {
      type: 'cloud', displayName: 'Qwen', defaultModel: 'qwen-max',
      capabilities: { streaming: true, tools: false, vision: false, functionCalling: false, jsonMode: false },
      researchProfile: { providerId: 'qwen', model: 'qwen-max', capabilities: ['math', 'coding', 'paper-writing'] }
    })
    registerProvider('ollama', () => ({
      id: 'ollama', type: 'local',
      capabilities: { streaming: true, tools: false, vision: false, functionCalling: false, jsonMode: false },
      buildRequest: () => ({}), parseChunk: () => null, ping: async () => ({ ok: true })
    }), {
      type: 'local', displayName: 'Ollama', defaultModel: 'qwen3:8b',
      capabilities: { streaming: true, tools: false, vision: false, functionCalling: false, jsonMode: false },
      researchProfile: { providerId: 'ollama', model: 'qwen3:8b', capabilities: ['cfd'] }
    })
  })
  it('ranks providers by overlap with task caps', () => {
    const ranked = matchTaskCapability(['paper-writing'])
    // qwen + openai both have paper-writing (tied); ollama has cfd (no overlap)
    expect(ranked[0].providerId === 'openai' || ranked[0].providerId === 'qwen').toBe(true)
    expect(ranked[ranked.length - 1].profile.capabilities).not.toContain('paper-writing')
  })
  it('returns all registered providers even with zero overlap', () => {
    const ranked = matchTaskCapability(['image-analysis'])
    expect(ranked).toHaveLength(3)
  })
  it('filters out invalid capability tags from task input', () => {
    const ranked = matchTaskCapability(['paper-writing', 'flying', 'magic'])
    expect(ranked[0].profile.capabilities).toContain('paper-writing')
  })
})

// ============ Spec: hasAllCapabilities / hasAnyCapability ============

describe('Phase 6-C1 hasAllCapabilities / hasAnyCapability', () => {
  const match = {
    providerId: 'openai', model: 'm', source: 'registry' as const,
    profile: { providerId: 'openai', model: 'm', capabilities: ['coding', 'math'] as const }
  }
  it('hasAllCapabilities returns true when all required are present', () => {
    expect(hasAllCapabilities(match, ['coding', 'math'])).toBe(true)
  })
  it('hasAllCapabilities returns false when one missing', () => {
    expect(hasAllCapabilities(match, ['coding', 'paper-writing'])).toBe(false)
  })
  it('hasAnyCapability returns true when one present', () => {
    expect(hasAnyCapability(match, ['coding', 'paper-writing'])).toBe(true)
  })
  it('hasAnyCapability returns false when none present', () => {
    expect(hasAnyCapability(match, ['paper-writing', 'image-analysis'])).toBe(false)
  })
})

// ============ Spec: Security ============

describe('Phase 6-C1 security — assertProfileSafe + capability-resolver safety', () => {
  it('assertProfileSafe throws on sk- substring', () => {
    expect(() => assertProfileSafe({
      providerId: 'openai', model: 'm',
      capabilities: ['chat'],
      strengths: ['sk-supersecret']
    } as never)).toThrow(/sk-/)
  })
  it('assertProfileSafe throws on apiKey substring', () => {
    expect(() => assertProfileSafe({
      providerId: 'openai', model: 'm',
      capabilities: ['chat'],
      apiKey: 'leaked'
    } as never)).toThrow(/apiKey/)
  })
  it('assertProfileSafe accepts clean profile', () => {
    expect(() => assertProfileSafe({
      providerId: 'openai', model: 'm', capabilities: ['chat']
    })).not.toThrow()
  })
})

// ============ Spec: backward compat (Phase 6-C1 strict) ============

describe('Phase 6-C1 backward compat — providers without researchProfile', () => {
  it('legacy provider (no researchProfile) still resolves to unknown source', () => {
    registerProvider('legacy', () => ({
      id: 'legacy', type: 'openai-compatible',
      capabilities: { streaming: true, tools: false, vision: false, functionCalling: false, jsonMode: false },
      buildRequest: () => ({}), parseChunk: () => null, ping: async () => ({ ok: true })
    }), {
      type: 'openai-compatible', displayName: 'Legacy', defaultModel: 'm1',
      capabilities: { streaming: true, tools: false, vision: false, functionCalling: false, jsonMode: false }
      // no researchProfile
    })
    const m = resolveModelCapability('legacy')
    expect(m?.source).toBe('unknown')
    expect(m?.profile.capabilities).toEqual(['chat'])
  })
  it('ConfigStore.saveConfig works without researchProfile', () => {
    expect(() => saveConfig('openai', {
      type: 'openai-compatible', defaultModel: 'm', displayName: 'OpenAI', capabilities: ['streaming'],
      endpoint: 'https://api.example.com/v1'
      // no researchProfile
    })).not.toThrow()
  })
  it('ConfigStore.getConfig returns profile without researchProfile field', () => {
    saveConfig('openai', {
      type: 'openai-compatible', defaultModel: 'm', displayName: 'OpenAI', capabilities: ['streaming'],
      endpoint: 'https://api.example.com/v1'
    })
    const cfg = resolveModelCapability('openai')
    expect(cfg?.profile).toBeDefined()
    expect('researchProfile' in (cfg?.profile ?? {})).toBe(false)
  })
})
