// Research Memory Adapter (Phase 8-F0).
//
// Phase 8-F0: connects a ResearchAgent to a ResearchSessionManager WITHOUT
// touching the agent core. Before run: load previous session context. After
// run: store question + answer + citations + confidence into the session.
//
// Phase 8-F0 strict:
//   - NEVER contains apiKey / secret / token value / cipher / authorization
//   - Does NOT modify Phase 8-E0 / 8-A1 / 8-B / 8-C / 8-D modules

import type {
  ResearchAgentRequest,
  ResearchAgentResponse
} from '../../../shared/agent/research-agent-schema'
import type {
  ConversationEntry,
  MemoryItem,
  AgentCheckpoint
} from '../../../shared/agent/research-session-schema'
import type { ResearchSessionManager } from './research-session-manager'

/** Phase 8-F0: minimal agent surface the adapter talks to (structural). */
export interface ResearchAgentLike {
  run(req: ResearchAgentRequest): Promise<ResearchAgentResponse>
}

export interface LoadedContext {
  conversation: ConversationEntry[]
  memory: MemoryItem[]
  checkpoints: AgentCheckpoint[]
  source: string
}

export interface StoredResult {
  conversationEntries: ConversationEntry[]
  memories: MemoryItem[]
}

export interface RunWithMemoryResult {
  response: ResearchAgentResponse
  loaded: LoadedContext | null
  stored: StoredResult
}

export class ResearchMemoryAdapter {
  private readonly manager: ResearchSessionManager

  constructor(options: { manager: ResearchSessionManager }) {
    if (!options?.manager) {
      throw new Error('research memory adapter: manager required (Phase 8-F0 strict)')
    }
    this.manager = options.manager
  }

  /** Phase 8-F0: load everything the agent should see before a run. */
  loadContext(sessionId: string): LoadedContext | null {
    if (!this.manager.getSession(sessionId)) return null
    return {
      conversation: this.manager.listConversation(sessionId),
      memory: this.manager.listMemory(sessionId),
      checkpoints: this.manager.listCheckpoints(sessionId),
      source: 'session'
    }
  }

  /** Phase 8-F0: persist the outcome of one agent run into the session. */
  storeRun(sessionId: string, response: ResearchAgentResponse): StoredResult {
    if (!this.manager.getSession(sessionId)) {
      throw new Error(`research memory adapter: unknown session '${sessionId}' (Phase 8-F0 strict)`)
    }
    const userEntry = this.manager.appendConversation(sessionId, 'user', response.requestId)
    const assistantEntry = this.manager.appendConversation(sessionId, 'assistant', response.answer)
    const memories: MemoryItem[] = []
    if (response.answer.length > 0) {
      const conclusion = this.manager.addMemory(sessionId, {
        type: 'conclusion',
        content: response.answer,
        confidence: response.confidence,
        source: response.requestId
      })
      if (conclusion) memories.push(conclusion)
    }
    return {
      conversationEntries: [userEntry, assistantEntry].filter((e): e is ConversationEntry => e !== null),
      memories
    }
  }

  /**
   * Phase 8-F0: run an agent inside a session.
   *   load previous context -> agent.run(request) -> store result
   */
  async runWithMemory(
    agent: ResearchAgentLike,
    sessionId: string,
    request: ResearchAgentRequest
  ): Promise<RunWithMemoryResult> {
    if (!agent || typeof agent.run !== 'function') {
      throw new Error('research memory adapter: agent with run() required (Phase 8-F0 strict)')
    }
    const loaded = this.loadContext(sessionId)
    const response = await agent.run(request)
    const stored = this.storeRun(sessionId, response)
    return { response, loaded, stored }
  }

  getManager(): ResearchSessionManager {
    return this.manager
  }
}

export const __testHelpers = {}