import { describe, it, expect } from 'vitest'

/**
 * Phase 6-A1 Model Provider Foundation tests.
 *
 * Coverage (>= 20 cases):
 * - ModelConfig validation (5 cases)
 * - ProviderCapabilities / provider id validation (3 cases)
 * - CanonicalMessage conversion (5 cases)
 * - Provider interface mock + replayChunks (2 cases)
 * - Stream normalization (8 cases)
 * - Invalid input (3 cases)
 */

import {
  isValidModelConfig,
  type ModelConfig,
  type ModelProviderType
} from '../../src/shared/model/model-types'
import {
  capabilitiesFrom,
  isValidProviderId,
  type ModelProvider,
  type CanonicalMessage,
  type CanonicalRequest,
  type StreamEvent
} from '../../src/shared/model/provider-types'
import {
  toCanonicalMessage,
  toCanonicalMessages,
  fromCanonicalMessage
} from '../../src/shared/model/canonical-message'
import {
  normalizeStreamChunk,
  parseJsonEvent,
  normalizeStream,
  isKnownStreamEvent
} from '../../src/main/services/model-provider/stream-normalizer'
import {
  createMockProvider,
  replayChunks,
  MOCK_PROVIDER_ID
} from '../../src/main/services/model-provider/mock-provider'

// ===== Spec: ModelConfig validation (5) =====
describe('ModelConfig validation', () => {
  function validBase(): ModelConfig {
    return {
      providerId: 'openai-compatible',
      displayName: 'Test Local',
      type: 'openai-compatible',
      defaultModel: 'gpt-4o',
      endpoint: 'http://localhost:11434',
      capabilities: ['streaming']
    }
  }

  it('valid openai-compatible with endpoint passes', () => {
    expect(isValidModelConfig(validBase())).toBe(true)
  })

  it('valid cloud config (no endpoint required) passes', () => {
    const cfg = { ...validBase(), type: 'cloud' as ModelProviderType, endpoint: undefined }
    expect(isValidModelConfig(cfg)).toBe(true)
  })

  it('local without endpoint is rejected', () => {
    const cfg = { ...validBase(), type: 'local' as ModelProviderType }
    delete (cfg as { endpoint?: string }).endpoint
    expect(isValidModelConfig(cfg)).toBe(false)
  })

  it('missing providerId is rejected', () => {
    const cfg = validBase()
    ;(cfg as { providerId?: string }).providerId = ''
    expect(isValidModelConfig(cfg)).toBe(false)
  })

  it('invalid capability string is rejected', () => {
    expect(isValidModelConfig({ ...validBase(), capabilities: ['streaming', 'watermark' as ModelConfig['capabilities'][number]] })).toBe(false)
  })
})

// ===== Spec: Provider id + capabilities (3) =====
describe('Provider id and capabilities derivation', () => {
  it('valid provider id passes', () => {
    expect(isValidProviderId('minimax')).toBe(true)
    expect(isValidProviderId('openai-compatible')).toBe(true)
    expect(isValidProviderId('vllm-prod')).toBe(true)
  })

  it('invalid provider id fails (uppercase / starts with digit / too short)', () => {
    expect(isValidProviderId('MiniMax')).toBe(false)
    expect(isValidProviderId('1provider')).toBe(false)
    expect(isValidProviderId('a')).toBe(false)
    expect(isValidProviderId('a'.repeat(33))).toBe(false)
  })

  it('capabilitiesFrom derives from ModelConfig.capabilities', () => {
    const caps = capabilitiesFrom({
      providerId: 'x',
      displayName: 'X',
      type: 'cloud',
      defaultModel: 'm',
      capabilities: ['streaming', 'tools', 'vision']
    })
    expect(caps.streaming).toBe(true)
    expect(caps.tools).toBe(true)
    expect(caps.vision).toBe(true)
    expect(caps.functionCalling).toBe(false)
    expect(caps.jsonMode).toBe(false)
  })
})

// ===== Spec: CanonicalMessage conversion (5) =====
describe('CanonicalMessage conversion', () => {
  function msg(role: string, content: string, md?: Record<string, unknown>): unknown {
    return {
      id: 1,
      session_id: 's',
      role,
      content,
      rich_blocks: [],
      tool_trace: [],
      message_metadata: md ?? {},
      is_partial: false,
      is_deleted: false,
      client_msg_id: null,
      attached_knowledge_ids: [],
      image_url: null,
      created_at: '2026-08-21T00:00:00Z'
    }
  }

  it('user message -> CanonicalMessage(user, content)', () => {
    const c = toCanonicalMessage(msg('user', 'hi') as never)
    expect(c).toEqual({ role: 'user', content: 'hi' })
  })

  it('assistant message -> CanonicalMessage(assistant)', () => {
    const c = toCanonicalMessage(msg('assistant', 'response') as never)
    expect(c?.role).toBe('assistant')
    expect(c?.content).toBe('response')
  })

  it('tool message keeps tool_call_id + name', () => {
    const c = toCanonicalMessage(msg('tool', 'result', {
      tool_call_id: 'tu_1',
      name: 'web_search'
    }) as never)
    expect(c).toEqual({
      role: 'tool',
      content: 'result',
      tool_call_id: 'tu_1',
      name: 'web_search'
    })
  })

  it('unsupported role is dropped (returns null)', () => {
    const c = toCanonicalMessage(msg('thinking', 'p1') as never)
    expect(c).toBeNull()
  })

  it('fromCanonicalMessage round-trip preserves core fields', () => {
    const orig: CanonicalMessage = { role: 'user', content: 'hello' }
    const back = fromCanonicalMessage(orig, { id: 7 })
    expect(back.role).toBe('user')
    expect(back.content).toBe('hello')
    expect(back.id).toBe(7)
    expect(toCanonicalMessages([back as never])).toEqual([orig])
  })
})

// ===== Spec: Provider interface mock + replayChunks (2) =====
describe('MockProvider + replayChunks', () => {
  function cfg(): ModelConfig {
    return {
      providerId: MOCK_PROVIDER_ID,
      displayName: 'Mock',
      type: 'openai-compatible',
      defaultModel: 'm',
      capabilities: ['streaming', 'tools']
    }
  }

  it('mock provider exposes id / type / capabilities + builds openai-compat payload', () => {
    const provider = createMockProvider(cfg(), [])
    expect(provider.id).toBe(MOCK_PROVIDER_ID)
    expect(provider.type).toBe('openai-compatible')
    expect(provider.capabilities.streaming).toBe(true)
    expect(provider.capabilities.tools).toBe(true)
    const req: CanonicalRequest = {
      model: 'm',
      messages: [{ role: 'user', content: 'hi' }],
      stream: true
    }
    const payload = provider.buildRequest(req, cfg()) as {
      model: string
      messages: unknown[]
      stream: boolean
    }
    expect(payload.model).toBe('m')
    expect(payload.messages[0]).toEqual({ role: 'user', content: 'hi' })
    expect(payload.stream).toBe(true)
  })

  it('replayChunks parses a sequence of SSE-style chunks into events', async () => {
    const provider = createMockProvider(cfg(), [
      { raw: '{"type":"text_delta","delta":"hello "}' },
      { raw: '{"type":"text_delta","delta":"world"}' },
      { raw: '[DONE]' }
    ])
    const events = await replayChunks(provider, [
      { raw: '{"type":"text_delta","delta":"hello "}' },
      { raw: '{"type":"text_delta","delta":"world"}' },
      { raw: '[DONE]' }
    ])
    expect(events.map((e) => e.type)).toEqual(['text_delta', 'text_delta', 'done'])
    expect((events[0] as { delta?: string }).delta).toBe('hello ')
  })
})

// ===== Spec: Stream normalization (8) =====
describe('Stream normalization', () => {
  it('SSE data: line (text_delta)', () => {
    const ev = normalizeStreamChunk('data: {"choices":[{"delta":{"content":"hi"}}]}')
    expect(ev?.type).toBe('text_delta')
    expect((ev as { delta?: string }).delta).toBe('hi')
  })

  it('SSE [DONE] -> done event', () => {
    expect(normalizeStreamChunk('data: [DONE]')).toEqual({ type: 'done' })
    expect(normalizeStreamChunk('[DONE]')).toEqual({ type: 'done' })
  })

  it('SSE comment line (: keepalive) -> null (skipped)', () => {
    expect(normalizeStreamChunk(': keepalive')).toBeNull()
  })

  it('empty input -> null', () => {
    expect(normalizeStreamChunk('')).toBeNull()
    expect(normalizeStreamChunk('   ')).toBeNull()
    expect(normalizeStreamChunk(null as never)).toBeNull()
    expect(normalizeStreamChunk(undefined as never)).toBeNull()
  })

  it('JSONL line parsed as JSON event', () => {
    const ev = normalizeStreamChunk('{"type":"thinking","thinking":"step1"}')
    expect(ev).toEqual({ type: 'thinking', reasoning: 'step1' })
  })

  it('plain text chunk -> text_delta fallback', () => {
    const ev = normalizeStreamChunk('hello world')
    expect(ev).toEqual({ type: 'text_delta', delta: 'hello world' })
  })

  it('error envelope -> error event', () => {
    const ev = normalizeStreamChunk('{"error":{"message":"rate limit","code":"429"}}')
    expect(ev).toEqual({ type: 'error', error_code: '429', message: 'rate limit' })
  })

  it('finish_reason only (no content) -> done with finish_reason', () => {
    const ev = normalizeStreamChunk('{"choices":[{"finish_reason":"stop"}]}')
    expect(ev?.type).toBe('done')
    expect((ev as { finish_reason?: string }).finish_reason).toBe('stop')
  })
})

// ===== Spec: invalid input + parseJsonEvent (3+) =====
describe('parseJsonEvent edge cases', () => {
  it('null / non-object input -> null', () => {
    expect(parseJsonEvent('null')).toBeNull()
    expect(parseJsonEvent('"string"')).toBeNull()
    expect(parseJsonEvent('[]')).toBeNull()
  })

  it('malformed JSON -> null (does not throw)', () => {
    expect(parseJsonEvent('{not json')).toBeNull()
    expect(parseJsonEvent('not json at all')).toBeNull()
  })

  it('tool_use delta with JSON-string args -> parsed object', () => {
    const input = JSON.stringify({
      choices: [{
        delta: {
          tool_calls: [{
            id: 'tc_1',
            function: { name: 'search', arguments: '{"q":"hello"}' }
          }]
        }
      }]
    })
    const ev = parseJsonEvent(input)
    expect(ev?.type).toBe('tool_use')
    const t = ev as { tool_name: string; tool_input: { q: string } }
    expect(t.tool_name).toBe('search')
    expect(t.tool_input.q).toBe('hello')
  })

  it('normalizeStream parses a multi-line SSE blob', () => {
    const blob = [
      'data: {"choices":[{"delta":{"content":"line 1"}}]}',
      '',
      'data: {"choices":[{"delta":{"content":" line 2"}}]}',
      '',
      'data: [DONE]',
      ''
    ].join('\n')
    const events = normalizeStream(blob)
    expect(events.map((e) => e.type)).toEqual(['text_delta', 'text_delta', 'done'])
  })

  it('isKnownStreamEvent accepts valid and rejects null', () => {
    expect(isKnownStreamEvent({ type: 'text_delta' })).toBe(true)
    expect(isKnownStreamEvent(null)).toBe(false)
    expect(isKnownStreamEvent({} as unknown as StreamEvent)).toBe(false)
  })
})
