// Phase 6-A3 Provider Factory + Registry tests.
//
// Coverage (>= 50 cases, spec requirement):
//   - Registry: register / lookup / list / has / clear (12 cases)
//   - OpenAI-Compatible provider: buildRequest / parseChunk / ping (22 cases)
//   - Ollama provider: buildRequest / parseChunk / ping (16 cases)
//   - Integration: getProvider lazy-build + cache + invalidate (4 cases)
//
// Phase 6-A3 frozen contracts under test:
//   1. Registry registers by id, returns undefined for missing
//   2. OpenAI-compatible: data: {json}\n\n, [DONE], error envelope, content delta, tool_use delta
//   3. Ollama: NDJSON (not SSE), { message: { content } } streaming, { done: true } terminator
//   4. Both: NO real network in tests (mock fetch)
//   5. Capabilities derived from ModelConfig.capabilities
//   6. Output MUST be Phase 3-B0 StreamEvent (do not modify type union)

import { describe, it, expect, beforeEach, vi } from 'vitest'

import {
  registerProvider,
  getProvider,
  listProviders,
  hasProvider,
  clearRegistry,
  registrySize
} from '../../src/main/services/model-provider/registry'
import {
  buildOpenAiCompatibleRequest,
  parseOpenAiCompatibleChunk,
  pingOpenAiCompatible,
  createOpenAiCompatibleProvider,
  OPENAI_COMPATIBLE_ID
} from '../../src/main/services/model-provider/providers/openai-compatible-provider'
import {
  buildOllamaRequest,
  parseOllamaChunk,
  pingOllama,
  createOllamaProvider,
  OLLAMA_ID
} from '../../src/main/services/model-provider/providers/ollama-provider'
import type { ModelConfig } from '../../src/shared/model/model-types'
import type {
  CanonicalRequest,
  CanonicalMessage,
  ModelProvider
} from '../../src/shared/model/provider-types'

// ==================== Helpers ====================

function validOaiConfig(overrides: Partial<ModelConfig> = {}): ModelConfig {
  return {
    providerId: OPENAI_COMPATIBLE_ID,
    displayName: 'Test OpenAI',
    type: 'openai-compatible',
    defaultModel: 'gpt-test',
    endpoint: 'https://api.example.com/v1',
    capabilities: ['streaming', 'tools'],
    ...overrides
  }
}

function validOllamaConfig(overrides: Partial<ModelConfig> = {}): ModelConfig {
  return {
    providerId: OLLAMA_ID,
    displayName: 'Local Ollama',
    type: 'local',
    defaultModel: 'qwen3:8b',
    endpoint: 'http://127.0.0.1:11434',
    capabilities: ['streaming'],
    ...overrides
  }
}

function messagesFixture(): CanonicalMessage[] {
  return [
    { role: 'system', content: 'You are a helpful assistant.' },
    { role: 'user', content: 'Hello' },
    { role: 'assistant', content: 'Hi there' },
    { role: 'tool', content: '42', tool_call_id: 'call_001', name: 'lookup' }
  ]
}

// ==================== Spec: Registry ====================

describe('Phase 6-A3 Registry — registerProvider / hasProvider / listProviders', () => {
  beforeEach(() => clearRegistry())

  it('rejects invalid providerId (length < 2)', () => {
    expect(() =>
      registerProvider('a', () => ({ id: 'a' } as unknown as ModelProvider), {
        type: 'cloud',
        capabilities: { streaming: true, tools: false, vision: false, functionCalling: false, jsonMode: false },
        displayName: 'X',
        defaultModel: 'm'
      })
    ).toThrow(/invalid providerId/)
  })
  it('rejects invalid providerId (length > 32)', () => {
    expect(() =>
      registerProvider('a'.repeat(33), () => ({ id: 'a' } as unknown as ModelProvider), {
        type: 'cloud',
        capabilities: { streaming: true, tools: false, vision: false, functionCalling: false, jsonMode: false },
        displayName: 'X',
        defaultModel: 'm'
      })
    ).toThrow(/invalid providerId/)
  })
  it('rejects non-function factory', () => {
    expect(() =>
      registerProvider('valid-id', null as unknown as () => ModelProvider, {
        type: 'cloud',
        capabilities: { streaming: true, tools: false, vision: false, functionCalling: false, jsonMode: false },
        displayName: 'X',
        defaultModel: 'm'
      })
    ).toThrow(/factory/)
  })
  it('rejects missing meta', () => {
    expect(() =>
      registerProvider('valid-id', () => ({ id: 'x' } as unknown as ModelProvider), null as unknown as {
        type: ModelConfig['type']
        capabilities: ModelProvider['capabilities']
        displayName: string
        defaultModel: string
      })
    ).toThrow(/meta/)
  })
  it('rejects empty displayName', () => {
    expect(() =>
      registerProvider('valid-id', () => ({ id: 'x' } as unknown as ModelProvider), {
        type: 'cloud',
        capabilities: { streaming: true, tools: false, vision: false, functionCalling: false, jsonMode: false },
        displayName: '',
        defaultModel: 'm'
      })
    ).toThrow(/displayName/)
  })
  it('rejects empty defaultModel', () => {
    expect(() =>
      registerProvider('valid-id', () => ({ id: 'x' } as unknown as ModelProvider), {
        type: 'cloud',
        capabilities: { streaming: true, tools: false, vision: false, functionCalling: false, jsonMode: false },
        displayName: 'X',
        defaultModel: ''
      })
    ).toThrow(/defaultModel/)
  })
  it('rejects invalid type', () => {
    expect(() =>
      registerProvider('valid-id', () => ({ id: 'x' } as unknown as ModelProvider), {
        type: 'unknown' as ModelConfig['type'],
        capabilities: { streaming: true, tools: false, vision: false, functionCalling: false, jsonMode: false },
        displayName: 'X',
        defaultModel: 'm'
      })
    ).toThrow(/type/)
  })
  it('registers valid provider and reports hasProvider=true', () => {
    registerProvider('my-vendor', () => ({ id: 'my-vendor' } as unknown as ModelProvider), {
      type: 'cloud',
      capabilities: { streaming: true, tools: false, vision: false, functionCalling: false, jsonMode: false },
      displayName: 'My Vendor',
      defaultModel: 'm'
    })
    expect(hasProvider('my-vendor')).toBe(true)
    expect(hasProvider('never-registered')).toBe(false)
  })
  it('listProviders returns empty array when nothing registered', () => {
    expect(listProviders()).toEqual([])
    expect(registrySize()).toBe(0)
  })
  it('listProviders returns meta (no factory callable from list)', () => {
    registerProvider('my-vendor', () => ({ id: 'my-vendor' } as unknown as ModelProvider), {
      type: 'cloud',
      capabilities: { streaming: true, tools: false, vision: false, functionCalling: false, jsonMode: false },
      displayName: 'My Vendor',
      defaultModel: 'm1'
    })
    const list = listProviders()
    expect(list).toHaveLength(1)
    expect(list[0].providerId).toBe('my-vendor')
    expect(list[0].displayName).toBe('My Vendor')
    expect(list[0].defaultModel).toBe('m1')
    expect((list[0] as unknown as { factory?: unknown }).factory).toBeUndefined()
  })
  it('re-registering overwrites previous entry', () => {
    const factory1 = (): ModelProvider => ({ id: 'a' } as unknown as ModelProvider)
    const factory2 = (): ModelProvider => ({ id: 'a-v2' } as unknown as ModelProvider)
    registerProvider('my-vendor', factory1, {
      type: 'cloud',
      capabilities: { streaming: true, tools: false, vision: false, functionCalling: false, jsonMode: false },
      displayName: 'v1',
      defaultModel: 'm'
    })
    registerProvider('my-vendor', factory2, {
      type: 'cloud',
      capabilities: { streaming: false, tools: false, vision: false, functionCalling: false, jsonMode: false },
      displayName: 'v2',
      defaultModel: 'm2'
    })
    expect(registrySize()).toBe(1)
    const list = listProviders()
    expect(list[0].displayName).toBe('v2')
    expect(list[0].defaultModel).toBe('m2')
  })
  it('clearRegistry empties all entries', () => {
    registerProvider('aa', () => ({ id: 'aa' } as unknown as ModelProvider), {
      type: 'cloud',
      capabilities: { streaming: true, tools: false, vision: false, functionCalling: false, jsonMode: false },
      displayName: 'A',
      defaultModel: 'm'
    })
    registerProvider('bb', () => ({ id: 'bb' } as unknown as ModelProvider), {
      type: 'cloud',
      capabilities: { streaming: true, tools: false, vision: false, functionCalling: false, jsonMode: false },
      displayName: 'B',
      defaultModel: 'm'
    })
    expect(registrySize()).toBe(2)
    clearRegistry()
    expect(registrySize()).toBe(0)
    expect(hasProvider('aa')).toBe(false)
  })
})

// ==================== Spec: OpenAI-compatible ====================

describe('Phase 6-A3 OpenAI-compatible — buildRequest', () => {
  it('translates all 4 message roles', () => {
    const req: CanonicalRequest = { model: 'gpt-test', stream: true, messages: messagesFixture() }
    const out = buildOpenAiCompatibleRequest(req, validOaiConfig()) as {
      messages: Array<{ role: string; content: string }>
    }
    expect(out.messages).toHaveLength(4)
    expect(out.messages[0]).toEqual({ role: 'system', content: 'You are a helpful assistant.' })
    expect(out.messages[1]).toEqual({ role: 'user', content: 'Hello' })
    expect(out.messages[2]).toEqual({ role: 'assistant', content: 'Hi there' })
    expect(out.messages[3].role).toBe('tool')
    expect(out.messages[3].content).toBe('42')
  })
  it('tool role message includes tool_call_id and name', () => {
    const req: CanonicalRequest = {
      model: 'gpt-test',
      stream: true,
      messages: [{ role: 'tool', content: 'r', tool_call_id: 'call_x', name: 'fn' }]
    }
    const out = buildOpenAiCompatibleRequest(req, validOaiConfig()) as {
      messages: Array<Record<string, unknown>>
    }
    expect(out.messages[0].tool_call_id).toBe('call_x')
    expect(out.messages[0].name).toBe('fn')
  })
  it('includes model from cfg.defaultModel', () => {
    const out = buildOpenAiCompatibleRequest(
      { model: 'gpt-test', stream: true, messages: [] },
      validOaiConfig({ defaultModel: 'gpt-4o-mini' })
    ) as { model: string }
    expect(out.model).toBe('gpt-4o-mini')
  })
  it('omits temperature/max_tokens/stop when undefined', () => {
    const out = buildOpenAiCompatibleRequest(
      { model: 'gpt-test', stream: true, messages: [] },
      validOaiConfig()
    ) as Record<string, unknown>
    expect(out).not.toHaveProperty('temperature')
    expect(out).not.toHaveProperty('max_tokens')
    expect(out).not.toHaveProperty('stop')
  })
  it('passes temperature/max_tokens/stop when provided', () => {
    const out = buildOpenAiCompatibleRequest(
      { model: 'gpt-test', stream: true, messages: [], temperature: 0.7, max_tokens: 256, stop: ['</end>'] },
      validOaiConfig()
    ) as { temperature?: number; max_tokens?: number; stop?: string[] }
    expect(out.temperature).toBe(0.7)
    expect(out.max_tokens).toBe(256)
    expect(out.stop).toEqual(['</end>'])
  })
  it('sets stream:true by default', () => {
    const out = buildOpenAiCompatibleRequest(
      { model: 'gpt-test', stream: true, messages: [] },
      validOaiConfig()
    ) as { stream: boolean }
    expect(out.stream).toBe(true)
  })
  it('sets stream:false when req.stream=false', () => {
    const out = buildOpenAiCompatibleRequest(
      { model: 'gpt-test', stream: false, messages: [] },
      validOaiConfig()
    ) as { stream: boolean }
    expect(out.stream).toBe(false)
  })
})

describe('Phase 6-A3 OpenAI-compatible — parseChunk', () => {
  it('returns null on empty input', () => {
    expect(parseOpenAiCompatibleChunk('')).toBeNull()
  })
  it('returns null on comment line', () => {
    expect(parseOpenAiCompatibleChunk(': keepalive')).toBeNull()
  })
  it('handles [DONE] as done event', () => {
    const ev = parseOpenAiCompatibleChunk('[DONE]')
    expect(ev?.type).toBe('done')
  })
  it('handles data: [DONE]', () => {
    const ev = parseOpenAiCompatibleChunk('data: [DONE]')
    expect(ev?.type).toBe('done')
  })
  it('handles data: prefix SSE content delta', () => {
    const ev = parseOpenAiCompatibleChunk(
      'data: {"choices":[{"delta":{"content":"hello"},"finish_reason":null}]}'
    )
    expect(ev?.type).toBe('text_delta')
    expect(ev?.delta).toBe('hello')
  })
  it('handles JSONL content delta (no data: prefix)', () => {
    const ev = parseOpenAiCompatibleChunk(
      '{"choices":[{"delta":{"content":"world"},"finish_reason":null}]}'
    )
    expect(ev?.type).toBe('text_delta')
    expect(ev?.delta).toBe('world')
  })
  it('handles OpenAI tool_calls delta', () => {
    const ev = parseOpenAiCompatibleChunk(
      'data: {"choices":[{"delta":{"tool_calls":[{"id":"call_1","function":{"name":"lookup","arguments":"{\\"q\\":\\"x\\"}"}}]}}]}'
    )
    expect(ev?.type).toBe('tool_use')
    expect(ev?.tool_name).toBe('lookup')
    expect(ev?.tool_use_id).toBe('call_1')
  })
  it('handles finish_reason-only chunk', () => {
    const ev = parseOpenAiCompatibleChunk(
      'data: {"choices":[{"delta":{},"finish_reason":"stop"}],"usage":{"total_tokens":42}}'
    )
    expect(ev?.type).toBe('done')
    expect(ev?.finish_reason).toBe('stop')
  })
  it('handles OpenAI error envelope', () => {
    const ev = parseOpenAiCompatibleChunk(
      'data: {"error":{"message":"rate limited","code":"rate_limit_exceeded"}}'
    )
    expect(ev?.type).toBe('error')
    expect(ev?.message).toBe('rate limited')
    expect(ev?.error_code).toBe('rate_limit_exceeded')
  })
  it('returns null on JSON-like garbage (unrecognized shape)', () => {
    // stream-normalizer returns null when JSON parses but no recognized event shape
    expect(parseOpenAiCompatibleChunk('{"totally_unrecognized":true}')).toBeNull()
  })
  it('handles data: line with empty payload', () => {
    expect(parseOpenAiCompatibleChunk('data: ')).toBeNull()
  })
})

describe('Phase 6-A3 OpenAI-compatible — ping', () => {
  function mockFetch(impl: (url: string, init: RequestInit) => Promise<Response>): typeof fetch {
    return ((url: string, init: RequestInit) => impl(url, init)) as unknown as typeof fetch
  }
  it('returns ok with latency on 200', async () => {
    const fetcher = mockFetch(async () =>
      new Response(JSON.stringify({ data: [] }), { status: 200 })
    )
    const r = await pingOpenAiCompatible(validOaiConfig(), 'sk-test', fetcher)
    expect(r.ok).toBe(true)
    expect(typeof r.latencyMs).toBe('number')
  })
  it('returns ok=false on non-200', async () => {
    const fetcher = mockFetch(async () =>
      new Response('forbidden', { status: 401, statusText: 'Unauthorized' })
    )
    const r = await pingOpenAiCompatible(validOaiConfig(), 'sk-test', fetcher)
    expect(r.ok).toBe(false)
    expect(r.error).toContain('401')
  })
  it('returns ok=false when endpoint missing', async () => {
    const fetcher = mockFetch(async () => new Response('ok', { status: 200 }))
    const cfg = validOaiConfig({ endpoint: undefined })
    const r = await pingOpenAiCompatible(cfg, null, fetcher)
    expect(r.ok).toBe(false)
    expect(r.error).toContain('endpoint')
  })
  it('includes Authorization header when apiKey present', async () => {
    let captured: RequestInit | undefined
    const fetcher = mockFetch(async (_u, init) => {
      captured = init
      return new Response('{}', { status: 200 })
    })
    await pingOpenAiCompatible(validOaiConfig(), 'sk-test-1234', fetcher)
    const headers = captured?.headers as Record<string, string> | undefined
    expect(headers?.Authorization).toBe('Bearer sk-test-1234')
  })
  it('omits Authorization when apiKey absent', async () => {
    let captured: RequestInit | undefined
    const fetcher = mockFetch(async (_u, init) => {
      captured = init
      return new Response('{}', { status: 200 })
    })
    await pingOpenAiCompatible(validOaiConfig(), null, fetcher)
    const headers = captured?.headers as Record<string, string> | undefined
    expect(headers?.Authorization).toBeUndefined()
  })
  it('returns ok=false on network error', async () => {
    const fetcher = mockFetch(async () => {
      throw new Error('ECONNREFUSED')
    })
    const r = await pingOpenAiCompatible(validOaiConfig(), 'sk-test', fetcher)
    expect(r.ok).toBe(false)
    expect(r.error).toBe('ECONNREFUSED')
  })
})

describe('Phase 6-A3 OpenAI-compatible — factory wiring', () => {
  it('createOpenAiCompatibleProvider returns a function that builds ModelProvider', () => {
    const factory = createOpenAiCompatibleProvider(() => null, vi.fn() as unknown as typeof fetch)
    const provider = factory(validOaiConfig())
    expect(provider.id).toBe(OPENAI_COMPATIBLE_ID)
    expect(provider.type).toBe('openai-compatible')
    expect(provider.capabilities.streaming).toBe(true)
    expect(provider.capabilities.tools).toBe(true)
  })
  it('factory buildRequest delegates to buildOpenAiCompatibleRequest', () => {
    const factory = createOpenAiCompatibleProvider(() => null, vi.fn() as unknown as typeof fetch)
    const provider = factory(validOaiConfig())
    const req: CanonicalRequest = { model: 'gpt-test', stream: true, messages: [{ role: 'user', content: 'hi' }] }
    const out = provider.buildRequest(req, validOaiConfig()) as { model: string; messages: unknown[] }
    expect(out.model).toBe('gpt-test')
    expect(out.messages).toHaveLength(1)
  })
  it('factory ping uses provided apiKeyResolver', async () => {
    let resolved: string | null = 'sk-from-resolver'
    const fetcher = ((_u: string, init: RequestInit) => {
      const headers = init.headers as Record<string, string>
      expect(headers.Authorization).toBe('Bearer sk-from-resolver')
      return Promise.resolve(new Response('{}', { status: 200 }))
    }) as unknown as typeof fetch
    const factory = createOpenAiCompatibleProvider(() => resolved, fetcher)
    const provider = factory(validOaiConfig())
    const r = await provider.ping(validOaiConfig())
    expect(r.ok).toBe(true)
    resolved = null
  })
})

// ==================== Spec: Ollama ====================

describe('Phase 6-A3 Ollama — buildRequest', () => {
  it('translates all 4 message roles', () => {
    const out = buildOllamaRequest(
      { model: 'qwen3:8b', stream: true, messages: messagesFixture() },
      validOllamaConfig()
    ) as { messages: Array<{ role: string; content: string }> }
    expect(out.messages).toHaveLength(4)
    expect(out.messages[0]).toEqual({ role: 'system', content: 'You are a helpful assistant.' })
    expect(out.messages[3].role).toBe('tool')
  })
  it('passes temperature via options.temperature', () => {
    const out = buildOllamaRequest(
      { model: 'qwen3:8b', stream: true, messages: [], temperature: 0.3 },
      validOllamaConfig()
    ) as { options?: Record<string, unknown> }
    expect(out.options?.temperature).toBe(0.3)
  })
  it('passes max_tokens via options.num_predict (Ollama naming)', () => {
    const out = buildOllamaRequest(
      { model: 'qwen3:8b', stream: true, messages: [], max_tokens: 512 },
      validOllamaConfig()
    ) as { options?: Record<string, unknown> }
    expect(out.options?.num_predict).toBe(512)
  })
  it('omits options when no temperature/max_tokens', () => {
    const out = buildOllamaRequest(
      { model: 'qwen3:8b', stream: true, messages: [] },
      validOllamaConfig()
    ) as { options?: Record<string, unknown> }
    expect(out.options).toBeUndefined()
  })
  it('sets stream:true by default and false when req.stream=false', () => {
    const a = buildOllamaRequest({ model: 'qwen3:8b', stream: true, messages: [] }, validOllamaConfig()) as { stream: boolean }
    const b = buildOllamaRequest({ model: 'qwen3:8b', stream: false, messages: [] }, validOllamaConfig()) as { stream: boolean }
    expect(a.stream).toBe(true)
    expect(b.stream).toBe(false)
  })
  it('includes model from cfg.defaultModel', () => {
    const out = buildOllamaRequest(
      { model: 'qwen3:8b', stream: true, messages: [] },
      validOllamaConfig({ defaultModel: 'llama3:8b' })
    ) as { model: string }
    expect(out.model).toBe('llama3:8b')
  })
})

describe('Phase 6-A3 Ollama — parseChunk (NDJSON, NOT SSE)', () => {
  it('returns null on empty input', () => {
    expect(parseOllamaChunk('')).toBeNull()
  })
  it('returns null on whitespace', () => {
    expect(parseOllamaChunk('   ')).toBeNull()
  })
  it('returns null on invalid JSON', () => {
    expect(parseOllamaChunk('not-json')).toBeNull()
  })
  it('handles content chunk { message: { content: "hi" } }', () => {
    const ev = parseOllamaChunk(
      JSON.stringify({ model: 'qwen3:8b', message: { role: 'assistant', content: 'hi' }, done: false })
    )
    expect(ev?.type).toBe('text_delta')
    expect(ev?.delta).toBe('hi')
  })
  it('handles done event { done: true } with default stop', () => {
    const ev = parseOllamaChunk(JSON.stringify({ done: true }))
    expect(ev?.type).toBe('done')
    expect(ev?.finish_reason).toBe('stop')
  })
  it('handles done event { done: true, done_reason: "length" }', () => {
    const ev = parseOllamaChunk(JSON.stringify({ done: true, done_reason: 'length' }))
    expect(ev?.type).toBe('done')
    expect(ev?.finish_reason).toBe('length')
  })
  it('captures usage stats in done event', () => {
    const ev = parseOllamaChunk(
      JSON.stringify({ done: true, eval_count: 50, prompt_eval_count: 20 })
    )
    expect(ev?.type).toBe('done')
    expect(ev?.usage?.completion_tokens).toBe(50)
    expect(ev?.usage?.prompt_tokens).toBe(20)
  })
  it('handles error envelope { error: "model not found" }', () => {
    const ev = parseOllamaChunk(JSON.stringify({ error: 'model not found' }))
    expect(ev?.type).toBe('error')
    expect(ev?.message).toBe('model not found')
  })
  it('skips SSE data: prefix (Ollama is NDJSON, not SSE)', () => {
    expect(parseOllamaChunk('data: {"foo":1}')).toBeNull()
  })
  it('returns null on unknown shape', () => {
    expect(parseOllamaChunk(JSON.stringify({ totally_unknown: true }))).toBeNull()
  })
})

describe('Phase 6-A3 Ollama — ping', () => {
  function mockFetch(impl: (url: string, init?: RequestInit) => Promise<Response>): typeof fetch {
    return ((url: string, init?: RequestInit) => impl(url, init)) as unknown as typeof fetch
  }
  it('returns ok when /api/tags returns models array', async () => {
    const fetcher = mockFetch(async () =>
      new Response(JSON.stringify({ models: [{ name: 'qwen3:8b' }] }), { status: 200 })
    )
    const r = await pingOllama(validOllamaConfig(), fetcher)
    expect(r.ok).toBe(true)
    expect(typeof r.latencyMs).toBe('number')
  })
  it('returns ok=false when models array missing (not Ollama)', async () => {
    const fetcher = mockFetch(async () =>
      new Response(JSON.stringify({ versions: ['v1'] }), { status: 200 })
    )
    const r = await pingOllama(validOllamaConfig(), fetcher)
    expect(r.ok).toBe(false)
    expect(r.error).toContain('models array')
  })
  it('returns ok=false when endpoint missing', async () => {
    const fetcher = mockFetch(async () => new Response('{}', { status: 200 }))
    const r = await pingOllama(validOllamaConfig({ endpoint: undefined }), fetcher)
    expect(r.ok).toBe(false)
    expect(r.error).toContain('endpoint')
  })
  it('returns ok=false on non-200', async () => {
    const fetcher = mockFetch(async () =>
      new Response('srv error', { status: 500, statusText: 'Internal Server Error' })
    )
    const r = await pingOllama(validOllamaConfig(), fetcher)
    expect(r.ok).toBe(false)
    expect(r.error).toContain('500')
  })
  it('returns ok=false on network error', async () => {
    const fetcher = mockFetch(async () => {
      throw new Error('ECONNREFUSED')
    })
    const r = await pingOllama(validOllamaConfig(), fetcher)
    expect(r.ok).toBe(false)
    expect(r.error).toBe('ECONNREFUSED')
  })
  it('does NOT send Authorization header (Ollama no-auth)', async () => {
    let captured: RequestInit | undefined
    const fetcher = mockFetch(async (_u, init) => {
      captured = init
      return new Response(JSON.stringify({ models: [] }), { status: 200 })
    })
    await pingOllama(validOllamaConfig(), fetcher)
    const headers = captured?.headers as Record<string, string> | undefined
    expect(headers?.Authorization).toBeUndefined()
  })
})

describe('Phase 6-A3 Ollama — factory wiring', () => {
  it('createOllamaProvider builds ModelProvider with correct id/type', () => {
    const factory = createOllamaProvider(vi.fn() as unknown as typeof fetch)
    const provider = factory(validOllamaConfig())
    expect(provider.id).toBe(OLLAMA_ID)
    expect(provider.type).toBe('local')
    expect(provider.capabilities.streaming).toBe(true)
    expect(provider.capabilities.tools).toBe(false)
  })
})

// ==================== Spec: Integration ====================

describe('Phase 6-A3 Integration — getProvider lazy-build + cache', () => {
  beforeEach(() => clearRegistry())

  it('returns undefined for unregistered id', () => {
    expect(getProvider('not-registered')).toBeUndefined()
  })
  it('builds provider on first getProvider(cfg) call', () => {
    const factory = vi.fn(() => ({
      id: 'test',
      type: 'cloud' as const,
      capabilities: { streaming: true, tools: false, vision: false, functionCalling: false, jsonMode: false },
      buildRequest: () => ({}),
      parseChunk: () => null,
      ping: async () => ({ ok: true })
    }))
    registerProvider('test', factory, {
      type: 'cloud',
      capabilities: { streaming: true, tools: false, vision: false, functionCalling: false, jsonMode: false },
      displayName: 'Test',
      defaultModel: 'm'
    })
    const cfg = { providerId: 'test', displayName: 'T', type: 'cloud' as const, defaultModel: 'm', capabilities: ['streaming' as const] }
    const p = getProvider('test', cfg)
    expect(p).toBeDefined()
    expect(factory).toHaveBeenCalledTimes(1)
  })
  it('returns cached provider on subsequent calls with same cfg', () => {
    const factory = vi.fn(() => ({
      id: 'test',
      type: 'cloud' as const,
      capabilities: { streaming: true, tools: false, vision: false, functionCalling: false, jsonMode: false },
      buildRequest: () => ({}),
      parseChunk: () => null,
      ping: async () => ({ ok: true })
    }))
    registerProvider('test', factory, {
      type: 'cloud',
      capabilities: { streaming: true, tools: false, vision: false, functionCalling: false, jsonMode: false },
      displayName: 'Test',
      defaultModel: 'm'
    })
    const cfg = { providerId: 'test', displayName: 'T', type: 'cloud' as const, defaultModel: 'm', capabilities: ['streaming' as const] }
    getProvider('test', cfg)
    getProvider('test', cfg)
    expect(factory).toHaveBeenCalledTimes(1)
  })
  it('rebuilds when cfg changes', () => {
    const factory = vi.fn(() => ({
      id: 'test',
      type: 'cloud' as const,
      capabilities: { streaming: true, tools: false, vision: false, functionCalling: false, jsonMode: false },
      buildRequest: () => ({}),
      parseChunk: () => null,
      ping: async () => ({ ok: true })
    }))
    registerProvider('test', factory, {
      type: 'cloud',
      capabilities: { streaming: true, tools: false, vision: false, functionCalling: false, jsonMode: false },
      displayName: 'Test',
      defaultModel: 'm'
    })
    const cfg1 = { providerId: 'test', displayName: 'T', type: 'cloud' as const, defaultModel: 'm1', capabilities: ['streaming' as const] }
    const cfg2 = { providerId: 'test', displayName: 'T', type: 'cloud' as const, defaultModel: 'm2', capabilities: ['streaming' as const] }
    getProvider('test', cfg1)
    getProvider('test', cfg2)
    expect(factory).toHaveBeenCalledTimes(2)
  })
})
