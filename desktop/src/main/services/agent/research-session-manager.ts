// Research Session Manager (Phase 8-F0).
//
// Phase 8-F0: the persistence boundary ABOVE the agent. Owns session lifecycle,
// conversation history, memory items, and checkpoints. Fully injectable storage
// (default in-memory) so a durable store can be swapped later — no database dep.
//
// Phase 8-F0 strict:
//   - NEVER contains apiKey / secret / token value / cipher / authorization
//   - Does NOT modify Phase 8-E0 / 8-A1 / 8-B / 8-C / 8-D / 7 / 6 modules

import type {
  ResearchSession,
  ConversationEntry,
  ConversationRole,
  MemoryItem,
  MemoryType,
  AgentCheckpoint,
  SessionEvent,
  SessionEventType
} from '../../../shared/agent/research-session-schema'
import {
  isValidResearchSession,
  isValidConversationEntry,
  isValidConversationRole,
  isValidMemoryItem,
  isValidMemoryType,
  isValidAgentCheckpoint
} from '../../../shared/agent/research-session-schema'
import type { MemoryProvider } from '../../../shared/agent/memory-provider'
import { LocalMemoryProvider } from '../../../shared/agent/memory-provider'

export type SessionEventListener = (event: SessionEvent) => void

// ============ Injectable storage ============

export interface SessionStorageLike {
  save(session: ResearchSession): void
  get(sessionId: string): ResearchSession | null
  list(): ResearchSession[]
  remove(sessionId: string): boolean
}

/** Phase 8-F0: in-memory session store (default). */
export class LocalSessionStore implements SessionStorageLike {
  private readonly sessions = new Map<string, ResearchSession>()
  save(session: ResearchSession): void { this.sessions.set(session.sessionId, session) }
  get(sessionId: string): ResearchSession | null { return this.sessions.get(sessionId) ?? null }
  list(): ResearchSession[] { return Array.from(this.sessions.values()).sort((a, b) => a.createdAt - b.createdAt) }
  remove(sessionId: string): boolean { return this.sessions.delete(sessionId) }
}

// ============ ResearchSessionManager ============

export interface ResearchSessionManagerOptions {
  storage?: SessionStorageLike
  memory?: MemoryProvider
}

export class ResearchSessionManager {
  private readonly storage: SessionStorageLike
  readonly memory: MemoryProvider
  private readonly listeners = new Set<SessionEventListener>()
  private readonly conversations = new Map<string, ConversationEntry[]>()
  private readonly checkpoints = new Map<string, AgentCheckpoint[]>()
  private seq = 0

  constructor(options: ResearchSessionManagerOptions = {}) {
    this.storage = options.storage ?? new LocalSessionStore()
    this.memory = options.memory ?? new LocalMemoryProvider()
  }

  onSessionEvent(listener: SessionEventListener): () => void {
    this.listeners.add(listener)
    return () => this.listeners.delete(listener)
  }

  private nextId(prefix: string): string {
    this.seq += 1
    return `${prefix}:${this.seq}`
  }

  private emit(typeEvent: SessionEventType, sessionId: string, payload?: Record<string, unknown>): void {
    const event: SessionEvent = { type: typeEvent, sessionId, timestamp: Date.now(), ...(payload ? { payload } : {}) }
    for (const l of this.listeners) {
      try { l(event) } catch {
        // Listener errors must not break the manager.
      }
    }
  }

  // ============ Session lifecycle ============

  createSession(input: { sessionId: string; title: string; projectId?: string; now?: number }): ResearchSession {
    if (!input || typeof input.sessionId !== 'string' || input.sessionId.length === 0) {
      throw new Error('research session manager: sessionId required (Phase 8-F0 strict)')
    }
    if (typeof input.title !== 'string' || input.title.length === 0) {
      throw new Error('research session manager: title required (Phase 8-F0 strict)')
    }
    if (this.getSession(input.sessionId)) {
      throw new Error(`research session manager: session '${input.sessionId}' already exists (Phase 8-F0 strict)`)
    }
    const now = input.now ?? Date.now()
    const session: ResearchSession = {
      sessionId: input.sessionId,
      ...(input.projectId !== undefined ? { projectId: input.projectId } : {}),
      title: input.title,
      createdAt: now,
      updatedAt: now,
      status: 'active'
    }
    if (!isValidResearchSession(session)) {
      throw new Error('research session manager: invalid ResearchSession (Phase 8-F0 strict)')
    }
    this.storage.save(session)
    this.conversations.set(input.sessionId, [])
    this.checkpoints.set(input.sessionId, [])
    this.emit('session_created', input.sessionId)
    return session
  }

  getSession(sessionId: string): ResearchSession | null {
    return this.storage.get(sessionId)
  }

  listSessions(): ResearchSession[] {
    return this.storage.list()
  }

  updateSession(
    sessionId: string,
    patch: Partial<Omit<ResearchSession, 'sessionId' | 'createdAt'>> & { now?: number }
  ): ResearchSession | null {
    const session = this.getSession(sessionId)
    if (!session) return null
    const now = patch.now ?? Date.now()
    const updated: ResearchSession = {
      ...session,
      ...(patch.title !== undefined ? { title: patch.title } : {}),
      ...(patch.projectId !== undefined ? { projectId: patch.projectId } : {}),
      ...(patch.status !== undefined ? { status: patch.status } : {}),
      updatedAt: now
    }
    if (!isValidResearchSession(updated)) {
      throw new Error('research session manager: invalid update produced invalid session (Phase 8-F0 strict)')
    }
    this.storage.save(updated)
    return updated
  }

  closeSession(sessionId: string, now?: number): ResearchSession | null {
    return this.updateSession(sessionId, { status: 'completed', now })
  }

  pauseSession(sessionId: string, now?: number): ResearchSession | null {
    return this.updateSession(sessionId, { status: 'paused', now })
  }

  archiveSession(sessionId: string, now?: number): ResearchSession | null {
    return this.updateSession(sessionId, { status: 'archived', now })
  }

  // ============ Conversation ============

  appendConversation(sessionId: string, role: ConversationRole, content: string, now?: number): ConversationEntry | null {
    if (!isValidConversationRole(role)) {
      throw new Error(`research session manager: invalid role '${String(role)}' (Phase 8-F0 strict)`)
    }
    if (typeof content !== 'string') {
      throw new Error('research session manager: content must be a string (Phase 8-F0 strict)')
    }
    if (!this.getSession(sessionId)) return null
    const entry: ConversationEntry = {
      entryId: this.nextId('entry'),
      role,
      content,
      timestamp: now ?? Date.now()
    }
    if (!isValidConversationEntry(entry)) {
      throw new Error('research session manager: invalid ConversationEntry (Phase 8-F0 strict)')
    }
    this.conversations.get(sessionId)!.push(entry)
    this.touch(sessionId, now)
    return entry
  }

  listConversation(sessionId: string): ConversationEntry[] {
    return [...(this.conversations.get(sessionId) ?? [])]
  }

  // ============ Memory ============

  addMemory(sessionId: string, input: Omit<MemoryItem, 'memoryId'> & { memoryId?: string }): MemoryItem | null {
    if (!isValidMemoryType(input.type)) {
      throw new Error(`research session manager: invalid memory type '${String(input.type)}' (Phase 8-F0 strict)`)
    }
    if (!this.getSession(sessionId)) return null
    const item: MemoryItem = {
      memoryId: input.memoryId ?? this.nextId('mem'),
      type: input.type,
      content: input.content,
      confidence: input.confidence,
      source: input.source
    }
    if (!isValidMemoryItem(item)) {
      throw new Error('research session manager: invalid MemoryItem (Phase 8-F0 strict)')
    }
    if (!this.memory.save(item)) {
      throw new Error(`research session manager: memoryId '${item.memoryId}' already exists (Phase 8-F0 strict)`)
    }
    this.touch(sessionId)
    this.emit('memory_added', sessionId, { memoryId: item.memoryId })
    return item
  }

  listMemory(sessionId: string, type?: MemoryType, limit?: number): MemoryItem[] {
    if (!this.getSession(sessionId)) return []
    return this.memory.list(type, limit)
  }

  searchMemory(sessionId: string, query: string, limit?: number): MemoryItem[] {
    if (!this.getSession(sessionId)) return []
    return this.memory.search(query, limit)
  }

  // ============ Checkpoints ============

  saveCheckpoint(sessionId: string, input: { planId: string; stepState: Record<string, unknown>; checkpointId?: string; now?: number }): AgentCheckpoint | null {
    if (!this.getSession(sessionId)) return null
    const checkpoint: AgentCheckpoint = {
      checkpointId: input.checkpointId ?? this.nextId('ckpt'),
      sessionId,
      planId: input.planId,
      stepState: input.stepState,
      createdAt: input.now ?? Date.now()
    }
    if (!isValidAgentCheckpoint(checkpoint)) {
      throw new Error('research session manager: invalid AgentCheckpoint (Phase 8-F0 strict)')
    }
    this.checkpoints.get(sessionId)!.push(checkpoint)
    this.touch(sessionId, input.now)
    this.emit('checkpoint_saved', sessionId, { checkpointId: checkpoint.checkpointId, planId: checkpoint.planId })
    return checkpoint
  }

  restoreCheckpoint(sessionId: string, checkpointId: string): AgentCheckpoint | null {
    const list = this.checkpoints.get(sessionId) ?? []
    const found = list.find((c) => c.checkpointId === checkpointId) ?? null
    if (found) {
      this.emit('context_restored', sessionId, { checkpointId })
    }
    return found
  }

  listCheckpoints(sessionId: string): AgentCheckpoint[] {
    return [...(this.checkpoints.get(sessionId) ?? [])].sort((a, b) => a.createdAt - b.createdAt)
  }

  // ============ Internals ============

  private touch(sessionId: string, now?: number): void {
    const s = this.getSession(sessionId)
    if (s) this.storage.save({ ...s, updatedAt: now ?? Date.now() })
  }
}

export const __testHelpers = {}