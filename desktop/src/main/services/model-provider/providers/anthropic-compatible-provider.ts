// Anthropic-Compatible Provider (Phase 12: 主拍决策 3 — 1.0 支持两类通用 LLM 接口).
//
// 适配任何 Anthropic Messages API 兼容的 HTTP 端点 (anthropic.com / MiMo Anthropic / 中转).
// 协议: POST /v1/messages
//   请求: { model, system, messages, max_tokens, temperature, stream: true }
//   响应: SSE event: message_start | content_block_start | content_block_delta (delta.type=text/thinking/input_json) | content_block_stop | message_delta | message_stop | ping
//
// 与 openai-compatible-provider 的关键差异:
//   - system 是顶层 string 字段 (不是 messages[0])
//   - messages 只含 user/assistant 对话
//   - 流式 SSE event-based (event: + data:), 不是单 data: 行
//   - 响应 model 在 message_start 中

import type {
  CanonicalRequest,
  ModelProvider,
  ProviderCapabilities,
  StreamEvent
} from '@shared/model/provider-types'
import type { ModelConfig } from '@shared/model/model-types'
import { normalizeStreamChunk } from '../stream-normalizer'

export const ANTHROPIC_COMPATIBLE_ID = 'anthropic-compatible'

function capabilitiesFromConfig(cfg: ModelConfig): ProviderCapabilities {
  const set = new Set(cfg.capabilities)
  return {
    streaming: set.has('streaming'),
    tools: set.has('tools'),
    vision: set.has('vision'),
    functionCalling: set.has('function-calling'),
    jsonMode: set.has('json-mode')
  }
}

/** Phase 12: 把 CanonicalRequest 转换为 Anthropic /v1/messages payload.
 *  - system 提取到顶层 string
 *  - messages 仅含 user/assistant/tool
 *  - tool message 转为 content blocks array
 *  - tools 转换: 简单 {name,description,input_schema} → Anthropic format */
export function buildAnthropicCompatibleRequest(
  req: CanonicalRequest,
  cfg: ModelConfig
): {
  model: string
  system?: string
  messages: Array<Record<string, unknown>>
  max_tokens?: number
  temperature?: number
  stop_sequences?: string[]
  stream: boolean
  tools?: Array<Record<string, unknown>>
} {
  let system: string | undefined
  const messages: Array<Record<string, unknown>> = []
  for (const m of req.messages) {
    if (m.role === 'system') {
      system = (system ? system + '\n\n' : '') + (typeof m.content === 'string' ? m.content : '')
      continue
    }
    if (m.role === 'user') {
      messages.push({
        role: 'user',
        content: typeof m.content === 'string' ? m.content : ''
      })
    } else if (m.role === 'assistant') {
      // Phase 12: Anthropic assistant message 可含 tool_use blocks (下轮扩展)
      messages.push({
        role: 'assistant',
        content: typeof m.content === 'string' ? m.content : ''
      })
    } else if (m.role === 'tool') {
      // Anthropic tool_result 格式: { type: 'tool_result', tool_use_id, content }
      const tr: Record<string, unknown> = {
        type: 'tool_result',
        content: typeof m.content === 'string' ? m.content : ''
      }
      if (typeof m.tool_call_id === 'string') tr.tool_use_id = m.tool_call_id
      messages.push({ role: 'user', content: [tr] })
    }
  }
  const out: ReturnType<typeof buildAnthropicCompatibleRequest> = {
    model: cfg.defaultModel,
    messages,
    stream: req.stream !== false
  }
  if (system) out.system = system
  if (typeof req.max_tokens === 'number') out.max_tokens = req.max_tokens
  if (typeof req.temperature === 'number') out.temperature = req.temperature
  if (Array.isArray(req.stop)) out.stop_sequences = req.stop
  return out
}

/** Phase 12: parse Anthropic SSE chunk (one of):
 *   event: message_start    data: {"type":"message_start","message":{...}}
 *   event: content_block_start   data: {"type":"content_block_start","index":0,"content_block":{"type":"text",...}}
 *   event: content_block_delta   data: {"type":"content_block_delta","index":0,"delta":{"type":"text_delta","text":"hi"}}
 *   event: content_block_stop    data: {"type":"content_block_stop","index":0}
 *   event: message_delta         data: {"type":"message_delta","delta":{"stop_reason":"end_turn"}}
 *   event: message_stop          data: {"type":"message_stop"}
 *   event: ping                  data: {"type":"ping"}
 *   event: error                 data: {"type":"error","error":{...}}
 *
 * Phase 12: 我们用 normalizeStreamChunk 处理 (它对 `data: {json}` 通用).
 *  注意 Anthropic SSE 每行以 `event: TYPE\ndata: {JSON}\n\n` 形式,
 *  normalizeStreamChunk 只读 `data:` 行, 跨多行有效. */
export function parseAnthropicCompatibleChunk(raw: string): StreamEvent | null {
  // SSE 多行格式: `event: TYPE\ndata: {JSON}\n\n` (也可能是 ping/keep-alive)
  // 提取所有 `data: ` 行的 payload 部分, 用空行分隔 → 多 data: 行合并解析
  const lines = raw.split(/\r?\n/)
  const payloads: string[] = []
  for (const ln of lines) {
    const m = /^data:\s?(.*)$/.exec(ln)
    if (m && m[1].length > 0 && m[1] !== '[DONE]') {
      payloads.push(m[1])
    }
  }
  if (payloads.length === 0) return null
  // 多 data: 行 → 用空行分隔后解析最后一条 (最关键 delta/stop)
  // 单条直接解析
  for (let i = payloads.length - 1; i >= 0; i--) {
    const evt = parseAnthropicStreamEvent(payloads[i])
    if (evt) return evt
  }
  return null
}

/**
 * Phase 12: parse Anthropic /v1/messages SSE event payload (data: line only).
 * Supports:
 *   { type: 'message_start', message: { ... } }                    -> null (no-op)
 *   { type: 'content_block_start', content_block: { type, text } } -> null (no-op)
 *   { type: 'content_block_delta', delta: { type: 'text_delta', text } } -> text_delta
 *   { type: 'content_block_delta', delta: { type: 'thinking_delta', thinking } } -> thinking
 *   { type: 'content_block_stop' }                                  -> null
 *   { type: 'message_delta', delta: { stop_reason } }               -> null
 *   { type: 'message_stop' }                                       -> done
 *   { type: 'ping' }                                                -> null
 *   { type: 'error', error: { type, message } }                     -> error
 */
export function parseAnthropicStreamEvent(data: string): StreamEvent | null {
  let parsed: unknown
  try {
    parsed = JSON.parse(data)
  } catch {
    return null
  }
  if (!parsed || typeof parsed !== 'object') return null
  const obj = parsed as Record<string, unknown>
  const type = typeof obj.type === 'string' ? obj.type : null

  switch (type) {
    case 'message_start':
    case 'content_block_start':
    case 'content_block_stop':
    case 'message_delta':
    case 'ping':
      return null

    case 'content_block_delta': {
      const delta = obj.delta as { type?: string; text?: string; thinking?: string } | undefined
      if (!delta) return null
      if (delta.type === 'text_delta' && typeof delta.text === 'string') {
        return { type: 'text_delta', delta: delta.text }
      }
      if (delta.type === 'thinking_delta' && typeof delta.thinking === 'string') {
        return { type: 'thinking', delta: delta.thinking }
      }
      if (delta.type === 'input_json_delta' && typeof delta.partial_json === 'string') {
        // tool_use 流式增量 — 暂不处理, 留 Phase 13
        return null
      }
      return null
    }

    case 'message_stop':
      return { type: 'done' }

    case 'error': {
      const err = obj.error as { type?: string; message?: string } | undefined
      return {
        type: 'error',
        error_code: err?.type,
        message: err?.message ?? 'unknown error'
      }
    }

    default:
      return null
  }
}

/** Phase 12: Anthropic 不支持 model list, ping 通过发送最小请求验证. */
export async function pingAnthropicCompatible(
  endpoint: string,
  apiKey: string,
  defaultModel: string
): Promise<{ ok: boolean; latencyMs?: number; error?: string }> {
  if (!endpoint || !apiKey) return { ok: false, error: 'endpoint or key missing' }
  const t0 = Date.now()
  try {
    const resp = await fetch(`${endpoint}/v1/messages`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'x-api-key': apiKey,
        'anthropic-version': '2023-06-01'
      },
      body: JSON.stringify({
        model: defaultModel,
        max_tokens: 1,
        messages: [{ role: 'user', content: 'ping' }]
      })
    })
    return { ok: resp.ok, latencyMs: Date.now() - t0, error: resp.ok ? undefined : `HTTP ${resp.status}` }
  } catch (e) {
    return { ok: false, latencyMs: Date.now() - t0, error: e instanceof Error ? e.message : String(e) }
  }
}

/** Phase 12: 工厂函数. 接收 apiKeyResolver, 适配 OpenAI-compatible 模式. */
export function createAnthropicCompatibleProvider(
  apiKeyResolver: () => string | null = () => null,
  fetcher: typeof fetch = fetch
): (cfg: ModelConfig) => ModelProvider {
  return (cfg: ModelConfig) => {
    const endpoint = cfg.endpoint?.replace(/\/$/, '') ?? 'https://api.anthropic.com'
    return {
      id: cfg.providerId,
      type: cfg.type,
      capabilities: capabilitiesFromConfig(cfg),
      buildRequest: (req: CanonicalRequest) => buildAnthropicCompatibleRequest(req, cfg),
      parseChunk: parseAnthropicCompatibleChunk,
      ping: async () => {
        const key = apiKeyResolver()
        if (!key) return { ok: false, error: 'API key not configured' }
        return pingAnthropicCompatible(endpoint, key, cfg.defaultModel)
      },
      rawCall: async (req: CanonicalRequest) => {
        const key = apiKeyResolver()
        if (!key) return { ok: false, error: 'API key not configured' }
        const body = buildAnthropicCompatibleRequest(req, cfg)
        const resp = await fetcher(`${endpoint}/v1/messages`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'x-api-key': key,
            'anthropic-version': '2023-06-01'
          },
          body: JSON.stringify(body)
        })
        if (!resp.ok) {
          return { ok: false, error: `HTTP ${resp.status}` }
        }
        const json = await resp.json()
        return { ok: true, data: json }
      }
    }
  }
}