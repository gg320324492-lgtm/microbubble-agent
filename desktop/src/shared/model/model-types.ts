// Model Types (Phase 6-A1: Model Provider Foundation).
//
// Provider-agnostic configuration shapes. Vendor SDK imports NO types here;
// vendor packages translate from/to CanonicalMessage via Provider factories.
//
// Frozen contract after Phase 6-A1 commit.

export type ModelProviderType =
  | 'cloud' // MiniMax / Qwen / Mimo / OpenAI cloud
  | 'local' // Ollama / vLLM (self-hosted)
  | 'openai-compatible' // any OpenAI-compatible HTTP endpoint

export type ModelCapability =
  | 'streaming' // SSE / chunked HTTP
  | 'tools' // tool_use / tool_result events
  | 'vision' // image input
  | 'function-calling'
  | 'json-mode'

/**
 * User-facing model selection (Phase 6-A1 frozen).
 *
 * - providerId: stable id (Phase 6-A: 'minimax' | 'qwen' | 'mimo' | 'openai' | 'ollama' | 'vllm' | 'openai-compatible')
 * - defaultModel: vendor-specific model name (e.g. 'minimax-cn', 'gpt-4o', 'qwen-plus')
 * - endpoint: required for 'local' and 'openai-compatible'
 */
export interface ModelConfig {
  providerId: string
  displayName: string
  type: ModelProviderType
  defaultModel: string
  endpoint?: string
  capabilities: ModelCapability[]
  /** Free-form extras (e.g. vLLM gpu_layers, ollama num_ctx) */
  extra?: Record<string, unknown>
}

/**
 * Validate ModelConfig. Phase 6-A1 strict.
 *
 * - providerId / displayName / defaultModel required (non-empty string)
 * - type must be one of 3 types
 * - capabilities must be non-empty for cloud/openai-compatible (local may omit)
 * - endpoint required for 'local' and 'openai-compatible'
 * - phase 6-A1 does NOT validate endpoint url format (Phase 6-A2 feature)
 */
export function isValidModelConfig(cfg: unknown): cfg is ModelConfig {
  if (!cfg || typeof cfg !== 'object') return false
  const c = cfg as Partial<ModelConfig>
  if (typeof c.providerId !== 'string' || c.providerId.length === 0) return false
  if (typeof c.displayName !== 'string' || c.displayName.length === 0) return false
  if (typeof c.defaultModel !== 'string' || c.defaultModel.length === 0) return false
  if (c.type !== 'cloud' && c.type !== 'local' && c.type !== 'openai-compatible') return false
  if (!Array.isArray(c.capabilities) || c.capabilities.length === 0) return false
  for (const cap of c.capabilities) {
    if (cap !== 'streaming' && cap !== 'tools' && cap !== 'vision' && cap !== 'function-calling' && cap !== 'json-mode') return false
  }
  if ((c.type === 'local' || c.type === 'openai-compatible') && (typeof c.endpoint !== 'string' || c.endpoint.length === 0)) return false
  return true
}
