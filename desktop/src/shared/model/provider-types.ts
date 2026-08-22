// Provider Types (Phase 6-A1: Model Provider Foundation).
//
// Phase 6-A1: vendor-agnostic Provider interface. Each concrete provider
// (MiniMax / Qwen / Mimo / OpenAI / Ollama / vLLM / openai-compatible)
// implements this in its own factory function. No vendor SDK imports here.
//
// Frozen contract after Phase 6-A1 commit.

import type { ModelConfig } from './model-types'

/**
 * Canonical ChatMessage (Phase 6-A1 frozen).
 *
 * Vendor SDKs translate from this to vendor-native shape.
 * Unified schema, no provider-specific fields here.
 */
export interface CanonicalMessage {
  role: 'system' | 'user' | 'assistant' | 'tool'
  content: string
  /** Optional tool_call_id (only for tool role) */
  name?: string
  tool_call_id?: string
}

/**
 * Canonical ChatRequest (Phase 6-A1 frozen).
 */
export interface CanonicalRequest {
  model: string
  messages: CanonicalMessage[]
  temperature?: number
  max_tokens?: number
  stop?: string[]
  stream: boolean
}

/**
 * Phase 3-B0 StreamEvent carrier. Vendor chunks normalize into this shape.
 * DO NOT modify Phase 3-B0 frozen StreamEventType union; reuse it as-is.
 */
export type StreamEventType =
  | 'text_delta'
  | 'thinking'
  | 'tool_use'
  | 'tool_result'
  | 'citation'
  | 'rich_block'
  | 'done'
  | 'error'
  | 'retry'
  | 'sync_required'
  | 'suggestions'
  | 'brief'
  | 'detail'
  | string

export interface StreamEvent {
  type: StreamEventType
  delta?: string
  tool_name?: string
  tool_use_id?: string
  tool_input?: Record<string, unknown>
  tool_output?: Record<string, unknown>
  tool_duration_ms?: number
  tool_error?: string
  reasoning?: string
  block?: Record<string, unknown>
  error_code?: string
  message?: string
  finish_reason?: 'stop' | 'length' | 'tool_calls' | string
  usage?: Record<string, number>
}

/**
 * Provider capability matrix (subset of ModelCapability).
 * Phase 6-A1: explicit subset for Provider factory selection.
 */
export interface ProviderCapabilities {
  streaming: boolean
  tools: boolean
  vision: boolean
  functionCalling: boolean
  jsonMode: boolean
}

/**
 * ModelProvider interface (Phase 6-A1 frozen).
 *
 * Vendor factories implement this. Phase 6-A1 ships 1 factory
 * (openai-compatible) as skeleton; rest are placeholder.
 */
export interface ModelProvider {
  readonly id: string
  readonly type: ModelConfig['type']
  readonly capabilities: ProviderCapabilities

  /**
   * Build vendor-native request payload from CanonicalRequest.
   * Phase 6-A1: 1:1 passthrough for openai-compatible; vendor-specific shapes per factory.
   */
  buildRequest(req: CanonicalRequest, cfg: ModelConfig): unknown

  /**
   * Parse a single vendor chunk into normalized StreamEvent.
   * Phase 3-B0 frozen StreamEventType union; vendor-specific normalization only.
   */
  parseChunk(raw: string): StreamEvent | null

  /**
   * Health check (Phase 6-A1: vendor-specific endpoint).
   */
  ping(cfg: ModelConfig): Promise<{ ok: boolean; latencyMs?: number; error?: string }>
}

/**
 * Type guard: ProviderCapabilities is a subset of ModelCapability[]. Used
 * to derive capabilities from a ModelConfig without manual field duplication.
 */
export function capabilitiesFrom(cfg: ModelConfig): ProviderCapabilities {
  const set = new Set(cfg.capabilities)
  return {
    streaming: set.has('streaming'),
    tools: set.has('tools'),
    vision: set.has('vision'),
    functionCalling: set.has('function-calling'),
    jsonMode: set.has('json-mode')
  }
}

/**
 * Validate provider id (Phase 6-A1: stable id registry).
 * Format: lowercase, hyphen-separated, 2-32 chars.
 * Allows vendor 自定义 id (Phase 6-A2 验证白名单).
 */
export function isValidProviderId(id: unknown): boolean {
  if (typeof id !== 'string') return false
  if (id.length < 2 || id.length > 32) return false
  return /^[a-z][a-z0-9-]*$/.test(id)
}
