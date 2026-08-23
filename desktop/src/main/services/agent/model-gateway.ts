// Model Gateway (Phase 8-D0: Research Agent Model Gateway).
//
// Phase 8-D0: composes OnlineModelAdapters + a small task-aware selector,
// generates ModelRequests from a RAGContext (Phase 8-C3), and surfaces
// deterministic failures when no adapter can serve a task.
//
// Pipeline:
//   RAGContext  ->  buildRequest  ->  pickAdapter  ->  adapter.chat / adapter.stream  ->  ModelResponse / StreamChunk
//
// Phase 8-D0 strict:
//   - NEVER contains apiKey / secret / token value / cipher
//   - Does NOT import model-provider SDKs / local model code
//   - Reuses the Phase 6 capability-router / health-tracker / budget-manager
//     only at construction (injected); this gateway itself is pure

import type {
  ModelRequest,
  ModelResponse,
  ModelRequest as MRequest,
  StreamChunk,
  TaskType,
  ChatMessage
} from '../../../shared/agent/model-gateway-schema'
import { isValidRAGContext } from '../../../shared/knowledge/context-schema'
import type {
  RAGContext,
  ContextChunk
} from '../../../shared/knowledge/context-schema'
import type { OnlineModelAdapter, AdapterCapabilities } from './model-adapter'
import { ZERO_USAGE } from './model-adapter'

export const DEFAULT_TIMEOUT_MS = 30_000
export const DEFAULT_TEMPERATURE = 0.2
export const DEFAULT_TOKEN_BUDGET = 1_500

export interface ModelGatewayOptions {
  adapters: OnlineModelAdapter[]
  preferredOrder?: string[]
  defaultTokenBudget?: number
  defaultTemperature?: number
  defaultTaskType?: TaskType
  /** Optional system-prompt template; must contain {context} and {question}. */
  systemPromptTemplate?: string
  /** When true, retries with the next adapter on chat failure. */
  fallbackOnError?: boolean
}

/** Phase 8-D0: result wrapper for streaming (preserves adapter id + total chunks). */
export interface StreamOutcome {
  provider: string
  fullText: string
  chunkCount: number
  usage?: ModelResponse['usage']
}

export class ModelGateway {
  private readonly adapters: Map<string, OnlineModelAdapter>
  private readonly preferredOrder: string[]
  private readonly defaultTokenBudget: number
  private readonly defaultTemperature: number
  private readonly defaultTaskType: TaskType
  private readonly systemPromptTemplate: string
  private readonly fallbackOnError: boolean

  constructor(options: ModelGatewayOptions) {
    if (!Array.isArray(options?.adapters) || options.adapters.length === 0) {
      throw new Error('model gateway: at least one adapter required (Phase 8-D0 strict)')
    }
    this.adapters = new Map()
    for (const a of options.adapters) {
      if (!a?.id) throw new Error('model gateway: every adapter needs an id (Phase 8-D0 strict)')
      if (this.adapters.has(a.id)) throw new Error(`model gateway: duplicate adapter id '${a.id}' (Phase 8-D0 strict)`)
      this.adapters.set(a.id, a)
    }
    this.preferredOrder = (options.preferredOrder ?? options.adapters.map((a) => a.id))
    this.defaultTokenBudget = normalizePositiveInt(options.defaultTokenBudget ?? DEFAULT_TOKEN_BUDGET, 'defaultTokenBudget')
    this.defaultTemperature = normalizeTemperature(options.defaultTemperature ?? DEFAULT_TEMPERATURE)
    this.defaultTaskType = options.defaultTaskType ?? 'qa'
    this.systemPromptTemplate = options.systemPromptTemplate ?? DEFAULT_SYSTEM_TEMPLATE
    this.fallbackOnError = options.fallbackOnError ?? true
  }

  listProviderIds(): string[] { return Array.from(this.adapters.keys()) }

  capabilities(providerId: string): AdapterCapabilities | undefined {
    return this.adapters.get(providerId)?.capabilities()
  }

  async healthCheckAll(): Promise<Array<{ provider: string; ok: boolean; latencyMs?: number; error?: string }>> {
    const out: Array<{ provider: string; ok: boolean; latencyMs?: number; error?: string }> = []
    for (const a of this.adapters.values()) {
      const h = await a.healthCheck()
      out.push({ provider: a.id, ...h })
    }
    return out
  }

  /** Phase 8-D0: single-shot answer. */
  async generateAnswer(
    ragContext: RAGContext,
    options: { taskType?: TaskType; tokenBudget?: number; temperature?: number } = {}
  ): Promise<ModelResponse> {
    const req = this.buildRequest(ragContext, options)
    const adapter = this.pickAdapter(req.taskType)
    if (!adapter) throw new Error('model gateway: no adapter supports the task (Phase 8-D0 strict)')
    const attempted = new Set<string>()
    let lastErr: unknown
    for (const a of this.orderAdapters(req.taskType)) {
      if (attempted.has(a.id)) continue
      attempted.add(a.id)
      try {
        return await a.chat(req)
      } catch (e) {
        lastErr = e
        if (!this.fallbackOnError) break
      }
    }
    throw lastErr instanceof Error
      ? lastErr
      : new Error(`model gateway: all adapters failed (Phase 8-D0 strict)`)
  }

  /** Phase 8-D0: token streaming. */
  async *streamAnswer(
    ragContext: RAGContext,
    options: { taskType?: TaskType; tokenBudget?: number; temperature?: number } = {}
  ): AsyncIterable<StreamChunk> {
    const req = this.buildRequest(ragContext, options)
    const adapter = this.pickAdapter(req.taskType)
    if (!adapter) throw new Error('model gateway: no adapter supports the task (Phase 8-D0 strict)')
    for await (const chunk of adapter.stream(req)) {
      yield chunk
    }
  }

  /** Phase 8-D0: helper — collect a stream into a single outcome. */
  async collectStream(
    ragContext: RAGContext,
    options: { taskType?: TaskType; tokenBudget?: number; temperature?: number } = {}
  ): Promise<StreamOutcome> {
    const req = this.buildRequest(ragContext, options)
    const adapter = this.pickAdapter(req.taskType)
    if (!adapter) throw new Error('model gateway: no adapter supports the task (Phase 8-D0 strict)')
    let full = ''
    let count = 0
    let usage: ModelResponse['usage'] | undefined
    for await (const c of adapter.stream(req)) {
      if (c.delta) { full += c.delta; count++ }
      if (c.usage) usage = c.usage
    }
    return { provider: adapter.id, fullText: full, chunkCount: count, usage: usage ?? { ...ZERO_USAGE } }
  }

  // ============ Internals ============

  buildRequest(ragContext: RAGContext, options?: { taskType?: TaskType; tokenBudget?: number; temperature?: number }): ModelRequest {
    if (!isValidRAGContext(ragContext)) {
      throw new Error('model gateway: invalid RAGContext (Phase 8-D0 strict)')
    }
    const opts = options ?? {}
    const taskType = opts.taskType ?? this.defaultTaskType
    const tokenBudget = opts.tokenBudget ?? this.defaultTokenBudget
    const temperature = opts.temperature ?? this.defaultTemperature
    const contextBlock = ragContext.chunks.map((c, i) => this.formatChunk(c, i + 1)).join('\n')
    const systemContent = this.systemPromptTemplate
      .replace('{context}', contextBlock)
      .replace('{question}', ragContext.query)
    const messages: ChatMessage[] = [
      { role: 'system', content: systemContent },
      { role: 'user', content: ragContext.query }
    ]
    const req: MRequest = {
      messages,
      context: { query: ragContext.query, totalCandidates: ragContext.metadata.totalCandidates ?? null },
      taskType,
      tokenBudget,
      temperature
    }
    return req
  }

  private formatChunk(c: ContextChunk, n: number): string {
    const page = typeof c.citation.page === 'number' ? `, page ${c.citation.page}` : ''
    const docId = c.citation.documentId
    return `[${n}] (${docId}${page})\n${c.content}`
  }

  private pickAdapter(taskType: TaskType): OnlineModelAdapter | null {
    for (const id of this.preferredOrder) {
      const a = this.adapters.get(id)
      if (a && this.supportsTask(a, taskType)) return a
    }
    // Fall back to any adapter that supports the task.
    for (const a of this.adapters.values()) {
      if (this.supportsTask(a, taskType)) return a
    }
    return null
  }

  private *orderAdapters(taskType: TaskType): Iterable<OnlineModelAdapter> {
    const seen = new Set<string>()
    for (const id of this.preferredOrder) {
      const a = this.adapters.get(id)
      if (a && this.supportsTask(a, taskType) && !seen.has(a.id)) {
        seen.add(a.id); yield a
      }
    }
    for (const a of this.adapters.values()) {
      if (this.supportsTask(a, taskType) && !seen.has(a.id)) {
        seen.add(a.id); yield a
      }
    }
  }

  private supportsTask(a: OnlineModelAdapter, taskType: TaskType): boolean {
    return a.capabilities().tasks.includes(taskType)
  }
}

function normalizePositiveInt(v: number, label: string): number {
  if (!Number.isInteger(v) || v < 1) {
    throw new Error(`model gateway: ${label} must be a positive integer (Phase 8-D0 strict)`)
  }
  return v
}
function normalizeTemperature(v: number): number {
  if (typeof v !== 'number' || v < 0 || v > 2) {
    throw new Error('model gateway: defaultTemperature must be in [0,2] (Phase 8-D0 strict)')
  }
  return v
}

export const DEFAULT_SYSTEM_TEMPLATE =
  'You are a research agent. Answer the question using only the numbered context below. Cite facts as [n].\nCONTEXT:\n{context}\nQUESTION:\n{question}'

export const __testHelpers = {
  DEFAULT_SYSTEM_TEMPLATE,
  DEFAULT_TIMEOUT_MS,
  DEFAULT_TOKEN_BUDGET,
  DEFAULT_TEMPERATURE
}