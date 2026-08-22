// Stream Normalizer (Phase 6-A1: Model Provider Foundation).
//
// Vendor SSE chunks -> Phase 3-B0 StreamEvent normalization.
// Phase 3-B0 frozen StreamEventType union not modified; vendor-specific
// shapes translated here.
//
// Supported vendor formats (Phase 6-A1):
//   1. OpenAI-compatible SSE: data: {json}\n\n (per-line JSON)
//   2. JSONL: each line is a JSON object (no data: prefix)
//   3. Plain text-only delta: bare string -> text_delta chunk
//   4. SSE terminator: [DONE] -> done
//   5. Error envelopes: { error: ... } -> error
//
// Phase 6-A1: vendors with non-SSE formats (custom SSE wrappers etc.)
// should override parseChunk in their factory; this normalizer is the
// default skeleton for openai-compatible providers.

import type { StreamEvent } from '@shared/model/provider-types'

/**
 * Phase 6-A1: safely extract tool call args from arbitrary vendor shape.
 * Accepts string (JSON-encoded) or object. Returns empty object on parse failure.
 */
function extractToolCallArgs(raw: unknown): Record<string, unknown> {
  if (raw == null) return {}
  if (typeof raw === 'string') {
    try { return JSON.parse(raw) as Record<string, unknown> } catch (_e) { return { _raw: raw } }
  }
  if (typeof raw === 'object') return raw as Record<string, unknown>
  return {}
}

/**
 * Phase 6-A1: Parse a single vendor stream chunk.
 *
 * @param raw - raw chunk text (may include SSE framing, JSONL line, or plain text)
 * @returns normalized StreamEvent or null if chunk should be skipped (e.g. empty, comments)
 */
export function normalizeStreamChunk(raw: string): StreamEvent | null {
  if (raw === null || raw === undefined) return null
  const text = String(raw).trim()
  if (text.length === 0) return null

  // Comment lines (SSE keepalive)
  if (text.startsWith(':')) return null

  // SSE terminator (Phase 6-A1: openai-compat only)
  if (text === '[DONE]') return { type: 'done' }

  // SSE data: line (may have data: prefix with optional space)
  if (text.startsWith('data:')) {
    const payload = text.slice('data:'.length).trim()
    if (payload === '[DONE]') return { type: 'done' }
    if (payload.length === 0) return null
    return parseJsonEvent(payload)
  }

  // Pure JSONL line
  if (text.startsWith('{')) return parseJsonEvent(text)

  // Plain text chunk (Phase 6-A1: treat as text_delta)
  return { type: 'text_delta', delta: text }
}

/**
 * Phase 6-A1: parse JSON payload -> StreamEvent.
 * Supports common OpenAI-compatible shapes:
 *   - { choices: [{ delta: { content }, finish_reason }] }     -> text_delta / done
 *   - { choices: [{ delta: { tool_calls: [...] } }] }          -> tool_use
 *   - { error: { message, code? } }                              -> error
 *   - { type: 'tool_result', tool_call_id, content }            -> tool_result (Phase 6-A2+ Phase 5-D)
 *   - { type: 'thinking', thinking }                              -> thinking
 *   - { type: 'citation', citation }                              -> citation
 *   - { type: 'rich_block', block }                              -> rich_block
 *   - { type: 'done', finish_reason, usage }                      -> done
 *   - { type: 'error', error: { message } }                      -> error
 *
 * Phase 6-A1: openai-compat default schema only. Vendor-specific
 * adapters should override parseChunk in their factory.
 */
export function parseJsonEvent(payload: string): StreamEvent | null {
  let parsed: unknown
  try {
    parsed = JSON.parse(payload)
  } catch (_e) {
    return null
  }
  if (!parsed || typeof parsed !== 'object') return null
  const obj = parsed as Record<string, unknown>

  // Phase 6-A1: error envelope (OpenAI-style { error: { message, code? } })
  if (obj.error && typeof obj.error === 'object') {
    const err = obj.error as { message?: string; code?: string }
    return {
      type: 'error',
      error_code: err.code,
      message: err.message ?? 'unknown error'
    }
  }
  if (obj.type === 'error' && typeof obj.message === 'string') {
    return { type: 'error', message: obj.message }
  }

  // Phase 6-A1: explicit type field wins (vendor-specific events)
  const explicitType = obj.type
  if (explicitType === 'thinking' && typeof obj.thinking === 'string') {
    return { type: 'thinking', reasoning: obj.thinking }
  }
  if (explicitType === 'citation') {
    return { type: 'citation', block: obj as Record<string, unknown> }
  }
  if (explicitType === 'rich_block') {
    return { type: 'rich_block', block: obj as Record<string, unknown> }
  }
  if (explicitType === 'tool_use' && typeof obj.tool_name === 'string') {
    const fnObj = (typeof obj.function === 'object' && obj.function !== null) ? obj.function as { name?: unknown; arguments?: unknown } : null
    const fnName = typeof fnObj?.name === 'string' ? fnObj.name : (typeof obj.tool_name === 'string' ? obj.tool_name : '')
    const args = extractToolCallArgs(fnObj?.arguments)
    return {
      type: 'tool_use',
      tool_name: fnName,
      tool_use_id: typeof obj.tool_use_id === 'string' ? obj.tool_use_id : '',
      tool_input: args
    }
  }
  if (explicitType === 'tool_result' && typeof obj.tool_use_id === 'string') {
    return {
      type: 'tool_result',
      tool_use_id: obj.tool_use_id,
      tool_output: (obj.tool_output as Record<string, unknown>) ?? undefined,
      tool_duration_ms: typeof obj.tool_duration_ms === 'number' ? obj.tool_duration_ms : undefined,
      tool_error: typeof obj.tool_error === 'string' ? obj.tool_error : undefined
    }
  }
  if (explicitType === 'done') {
    return {
      type: 'done',
      finish_reason: (obj.finish_reason as StreamEvent['finish_reason']) ?? 'stop',
      usage: obj.usage as Record<string, number> | undefined
    }
  }

  // Phase 6-A1: OpenAI-compatible SSE delta extraction
  if (Array.isArray(obj.choices) && obj.choices.length > 0) {
    const choice = obj.choices[0] as Record<string, unknown>
    const delta = (choice.delta ?? choice.message) as Record<string, unknown> | undefined
    const finish = choice.finish_reason as string | undefined

    // Tool calls delta (OpenAI shape)
    if (delta && Array.isArray(delta.tool_calls) && delta.tool_calls.length > 0) {
      const tc = delta.tool_calls[0] as {
        id?: string
        function?: { name?: string; arguments?: string | Record<string, unknown> }
      }
      const fnObj = (typeof tc.function === 'object' && tc.function !== null) ? tc.function : null
      const fnName = typeof fnObj?.name === 'string' ? fnObj.name : ''
      const args = extractToolCallArgs(fnObj?.arguments)
      return {
        type: 'tool_use',
        tool_name: fnName,
        tool_use_id: typeof tc.id === 'string' ? tc.id : '',
        tool_input: args
      }
    }

    // Content delta
    if (delta && typeof delta.content === 'string' && delta.content.length > 0) {
      const ev: StreamEvent = { type: 'text_delta', delta: delta.content }
      if (finish) ev.finish_reason = finish as StreamEvent['finish_reason']
      return ev
    }

    // finish_reason only (final chunk without content)
    if (finish && finish !== null) {
      return {
        type: 'done',
        finish_reason: finish as StreamEvent['finish_reason'],
        usage: obj.usage as Record<string, number> | undefined
      }
    }
  }

  // No recognized structure
  return null
}

/**
 * Phase 6-A1: validate that a normalized event has a known type.
 * Used by Provider factories for sanity checks before emit.
 */
export function isKnownStreamEvent(ev: StreamEvent | null): ev is StreamEvent {
  if (!ev || typeof ev !== 'object') return false
  return typeof ev.type === 'string' && ev.type.length > 0
}

/**
 * Phase 6-A1: normalize a full SSE response stream (multi-chunk).
 * Splits raw stream text into chunks and parses each.
 *
 * @param rawStream - full SSE response body (Phase 6-A1: may include data: ... lines)
 * @returns array of StreamEvents; [] if input is empty
 */
export function normalizeStream(rawStream: string): StreamEvent[] {
  if (typeof rawStream !== 'string' || rawStream.length === 0) return []
  const out: StreamEvent[] = []
  const lines = rawStream.split(/\r?\n/)
  for (const line of lines) {
    const trimmed = line.trim()
    if (trimmed.length === 0) continue
    const ev = normalizeStreamChunk(trimmed)
    if (ev !== null) out.push(ev)
  }
  return out
}
