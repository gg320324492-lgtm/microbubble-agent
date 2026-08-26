// Anthropic-Compatible Provider Transformer 单元测试 — Phase 12

import { describe, expect, it } from 'vitest'
import { existsSync, readFileSync } from 'node:fs'
import { resolve } from 'node:path'

const desktopRoot = resolve(__dirname, '..', '..')
const mainRoot = resolve(desktopRoot, 'src/main')

describe('Phase 12: Anthropic-Compatible Provider 文件', () => {
  it('anthropic-compatible-provider.ts 存在', () => {
    expect(existsSync(resolve(mainRoot, 'services/model-provider/providers/anthropic-compatible-provider.ts'))).toBe(true)
  })
  it('导出 ANTHROPIC_COMPATIBLE_ID, buildAnthropicCompatibleRequest, createAnthropicCompatibleProvider, pingAnthropicCompatible', () => {
    const src = readFileSync(resolve(mainRoot, 'services/model-provider/providers/anthropic-compatible-provider.ts'), 'utf-8')
    expect(src).toMatch(/export const ANTHROPIC_COMPATIBLE_ID/)
    expect(src).toMatch(/export function buildAnthropicCompatibleRequest/)
    expect(src).toMatch(/export function createAnthropicCompatibleProvider/)
    expect(src).toMatch(/export async function pingAnthropicCompatible/)
    expect(src).toMatch(/export function parseAnthropicCompatibleChunk/)
  })
})

describe('Phase 12: buildAnthropicCompatibleRequest 转换', () => {
  it('system 提到顶层 (不在 messages 里)', async () => {
    const { buildAnthropicCompatibleRequest } = await import('../../src/main/services/model-provider/providers/anthropic-compatible-provider')
    const req = {
      model: 'mimo-v2.5',
      messages: [
        { role: 'system', content: 'You are a helper.' },
        { role: 'user', content: 'hi' }
      ],
      stream: true,
      max_tokens: 100
    }
    const cfg = { providerId: 'a', displayName: 'a', type: 'openai-compatible' as const, defaultModel: 'mimo-v2.5', capabilities: [] }
    const out = buildAnthropicCompatibleRequest(req, cfg)
    expect(out.system).toBe('You are a helper.')
    expect(out.messages.length).toBe(1)
    expect(out.messages[0].role).toBe('user')
    expect(out.messages[0].content).toBe('hi')
    expect(out.model).toBe('mimo-v2.5')
    expect(out.max_tokens).toBe(100)
    expect(out.stream).toBe(true)
  })

  it('多 system 消息 → 合并到单个 system 字段 (\\n\\n 分隔)', async () => {
    const { buildAnthropicCompatibleRequest } = await import('../../src/main/services/model-provider/providers/anthropic-compatible-provider')
    const out = buildAnthropicCompatibleRequest(
      { model: 'x', messages: [
        { role: 'system', content: 'Rule 1' },
        { role: 'system', content: 'Rule 2' },
        { role: 'user', content: 'q' }
      ], stream: false },
      { providerId: 'a', displayName: 'a', type: 'openai-compatible' as const, defaultModel: 'x', capabilities: [] }
    )
    expect(out.system).toBe('Rule 1\n\nRule 2')
    expect(out.messages.length).toBe(1)
  })

  it('tool message → 转 Anthropic tool_result content block', async () => {
    const { buildAnthropicCompatibleRequest } = await import('../../src/main/services/model-provider/providers/anthropic-compatible-provider')
    const out = buildAnthropicCompatibleRequest(
      { model: 'x', messages: [
        { role: 'user', content: 'q' },
        { role: 'tool', content: '42', tool_call_id: 'call_abc', name: 'calc' }
      ], stream: false },
      { providerId: 'a', displayName: 'a', type: 'openai-compatible' as const, defaultModel: 'x', capabilities: [] }
    )
    // tool message 变 user with tool_result content block
    const lastMsg = out.messages[out.messages.length - 1]
    expect(lastMsg.role).toBe('user')
    expect(Array.isArray(lastMsg.content)).toBe(true)
    expect(lastMsg.content[0].type).toBe('tool_result')
    expect(lastMsg.content[0].tool_use_id).toBe('call_abc')
    expect(lastMsg.content[0].content).toBe('42')
  })

  it('max_tokens / temperature / stop_sequences passthrough', async () => {
    const { buildAnthropicCompatibleRequest } = await import('../../src/main/services/model-provider/providers/anthropic-compatible-provider')
    const out = buildAnthropicCompatibleRequest(
      { model: 'x', messages: [{ role: 'user', content: 'q' }], stream: false, max_tokens: 200, temperature: 0.5, stop: ['END'] } as never,
      { providerId: 'a', displayName: 'a', type: 'openai-compatible' as const, defaultModel: 'x', capabilities: [] }
    )
    expect(out.max_tokens).toBe(200)
    expect(out.temperature).toBe(0.5)
    expect(out.stop_sequences).toEqual(['END'])
  })
})

describe('Phase 12: parseAnthropicCompatibleChunk (SSE event: + data:)', () => {
  it('content_block_delta text → text_delta event', async () => {
    const { parseAnthropicCompatibleChunk } = await import('../../src/main/services/model-provider/providers/anthropic-compatible-provider')
    const sse = 'event: content_block_delta\ndata: {"type":"content_block_delta","index":0,"delta":{"type":"text_delta","text":"嗨"}}\n\n'
    const evt = parseAnthropicCompatibleChunk(sse)
    expect(evt).not.toBeNull()
    expect(evt?.type).toBe('text_delta')
    expect(evt?.delta).toBe('嗨')
  })

  it('message_stop → done event', async () => {
    const { parseAnthropicCompatibleChunk } = await import('../../src/main/services/model-provider/providers/anthropic-compatible-provider')
    const sse = 'event: message_stop\ndata: {"type":"message_stop","amazon-bedrock-invocationMetrics":{}}\n\n'
    const evt = parseAnthropicCompatibleChunk(sse)
    expect(evt?.type).toBe('done')
  })

  it('event: error → error event', async () => {
    const { parseAnthropicCompatibleChunk } = await import('../../src/main/services/model-provider/providers/anthropic-compatible-provider')
    const sse = 'event: error\ndata: {"type":"error","error":{"type":"authentication_error","message":"invalid key"}}\n\n'
    const evt = parseAnthropicCompatibleChunk(sse)
    expect(evt?.type).toBe('error')
  })

  it('event: ping → null (skip)', async () => {
    const { parseAnthropicCompatibleChunk } = await import('../../src/main/services/model-provider/providers/anthropic-compatible-provider')
    const evt = parseAnthropicCompatibleChunk('event: ping\ndata: {"type":"ping"}\n\n')
    // ping 应跳过, 不生成 text
    if (evt) expect(evt.type).not.toBe('text_delta')
  })
})

describe('Phase 12: bootstrap.ts 注册两类 provider', () => {
  it('注册 xiaomi-mimo (OpenAI-compatible) + xiaomi-mimo-anthropic (Anthropic-compatible)', async () => {
    const src = readFileSync(resolve(mainRoot, 'services/model-provider/bootstrap.ts'), 'utf-8')
    expect(src).toContain("MIMO_PROVIDER_ID = 'xiaomi-mimo'")
    expect(src).toContain("MIMO_ANTHROPIC_PROVIDER_ID = 'xiaomi-mimo-anthropic'")
    expect(src).toContain('MIMO_BASE_URL = ')
    expect(src).toContain('MIMO_ANTHROPIC_BASE_URL = ')
    expect(src).toContain('createOpenAiCompatibleProvider')
    expect(src).toContain('createAnthropicCompatibleProvider')
    expect(src).toMatch(/registerProvider\(\s*MIMO_PROVIDER_ID/)
    expect(src).toMatch(/registerProvider\(\s*MIMO_ANTHROPIC_PROVIDER_ID/)
    expect(src).toMatch(/saveConfig\(\s*MIMO_PROVIDER_ID/)
    expect(src).toMatch(/saveConfig\(\s*MIMO_ANTHROPIC_PROVIDER_ID/)
  })
})