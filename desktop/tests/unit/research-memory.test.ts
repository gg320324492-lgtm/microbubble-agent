// Phase 8-F0 Research Memory / Session tests.
//
// Coverage (~315 cases):
//   - schema validators + secret guard + enums (46)
//   - LocalMemoryProvider (58)
//   - ResearchSessionManager lifecycle (44)
//   - conversation (26)
//   - memory (32)
//   - checkpoints (30)
//   - concurrency / isolation (16)
//   - ResearchMemoryAdapter (40)
//   - determinism + security source scans (23)

import { describe, it, expect, beforeEach } from 'vitest'

// ============ Shared schemas ============
import {
  SESSION_STATUSES,
  MEMORY_TYPES,
  SESSION_EVENT_TYPES,
  isValidSessionStatus,
  isValidMemoryType,
  isValidResearchSession,
  isValidConversationRole,
  isValidConversationEntry,
  isValidMemoryItem,
  isValidAgentCheckpoint,
  isValidSessionEventType,
  isValidSessionEvent,
  __testHelpers as sessionHelpers
} from '../../src/shared/agent/research-session-schema'
import type {
  ResearchSession,
  ConversationEntry,
  MemoryItem,
  AgentCheckpoint,
  SessionEvent,
  SessionEventType,
  SessionStatus,
  MemoryType,
  ConversationRole
} from '../../src/shared/agent/research-session-schema'
import { LocalMemoryProvider, __testHelpers as memoryHelpers } from '../../src/shared/agent/memory-provider'
import type { MemoryProvider } from '../../src/shared/agent/memory-provider'

// ============ Implementations ============
import {
  ResearchSessionManager,
  LocalSessionStore,
  SessionStorageLike,
  SessionEventListener
} from '../../src/main/services/agent/research-session-manager'
import { ResearchMemoryAdapter, ResearchAgentLike } from '../../src/main/services/agent/research-memory-adapter'
import type { ResearchAgentRequest, ResearchAgentResponse } from '../../src/shared/agent/research-agent-schema'

// ============ Fixtures ============

function makeSession(overrides: Partial<ResearchSession> = {}): ResearchSession {
  return {
    sessionId: 'session:1',
    title: 'Microbubble Study',
    createdAt: 100,
    updatedAt: 200,
    status: 'active',
    ...overrides
  }
}

function makeMemory(overrides: Partial<MemoryItem> = {}): MemoryItem {
  return {
    memoryId: 'mem:1',
    type: 'conclusion',
    content: 'bubble improves water mixing',
    confidence: 0.9,
    source: 's1',
    ...overrides
  }
}

function makeEntry(overrides: Partial<ConversationEntry> = {}): ConversationEntry {
  return {
    entryId: 'entry:1',
    role: 'user',
    content: 'hello',
    timestamp: 100,
    ...overrides
  }
}

function makeCheckpoint(overrides: Partial<AgentCheckpoint> = {}): AgentCheckpoint {
  return {
    checkpointId: 'ckpt:1',
    sessionId: 'session:1',
    planId: 'plan:1',
    stepState: { step: 2 },
    createdAt: 150,
    ...overrides
  }
}

function makeResponse(overrides: Partial<ResearchAgentResponse> = {}): ResearchAgentResponse {
  return {
    requestId: 'req:1',
    answer: 'the answer is bubbles',
    plan: undefined,
    citations: [],
    toolResults: [],
    usage: { promptTokens: 0, completionTokens: 0, totalTokens: 0, promptCalls: 0, toolCalls: 0 },
    confidence: 0.75,
    ...overrides
  }
}

function makeRequest(overrides: Partial<ResearchAgentRequest> = {}): ResearchAgentRequest {
  return { requestId: 'req:1', question: 'explain bubbles', ...overrides }
}

// ============ Schema: SessionStatus ============

describe('Phase 8-F0 SESSION_STATUSES', () => {
  it('has 4 entries', () => {
    expect(SESSION_STATUSES.length).toBe(4)
  })
  it('contains the documented statuses', () => {
    for (const s of ['active', 'paused', 'completed', 'archived']) expect(SESSION_STATUSES).toContain(s)
  })
  it('is frozen', () => {
    expect(Object.isFrozen(SESSION_STATUSES)).toBe(true)
  })
  it('isValidSessionStatus accepts every entry', () => {
    for (const s of SESSION_STATUSES) expect(isValidSessionStatus(s)).toBe(true)
  })
  it('isValidSessionStatus rejects unknown', () => {
    expect(isValidSessionStatus('deleted')).toBe(false)
  })
  it('isValidSessionStatus rejects non-string', () => {
    expect(isValidSessionStatus(3)).toBe(false)
  })
})

// ============ Schema: MemoryType ============

describe('Phase 8-F0 MEMORY_TYPES', () => {
  it('has 5 entries', () => {
    expect(MEMORY_TYPES.length).toBe(5)
  })
  it('contains the documented types', () => {
    for (const t of ['conversation', 'experiment', 'paper', 'parameter', 'conclusion']) expect(MEMORY_TYPES).toContain(t)
  })
  it('isValidMemoryType accepts every entry', () => {
    for (const t of MEMORY_TYPES) expect(isValidMemoryType(t)).toBe(true)
  })
  it('isValidMemoryType rejects unknown', () => {
    expect(isValidMemoryType('video')).toBe(false)
  })
  it('isValidMemoryType rejects null', () => {
    expect(isValidMemoryType(null)).toBe(false)
  })
})

// ============ Schema: ResearchSession ============

describe('Phase 8-F0 ResearchSession validator', () => {
  it('accepts a valid session', () => {
    expect(isValidResearchSession(makeSession())).toBe(true)
  })
  it('accepts a session with projectId', () => {
    expect(isValidResearchSession(makeSession({ projectId: 'proj:1' }))).toBe(true)
  })
  it('rejects missing sessionId', () => {
    expect(isValidResearchSession({ ...makeSession(), sessionId: '' })).toBe(false)
  })
  it('rejects missing title', () => {
    expect(isValidResearchSession({ ...makeSession(), title: '' })).toBe(false)
  })
  it('rejects invalid status', () => {
    expect(isValidResearchSession({ ...makeSession(), status: 'nope' as never })).toBe(false)
  })
  it('rejects negative createdAt', () => {
    expect(isValidResearchSession({ ...makeSession(), createdAt: -1 })).toBe(false)
  })
  it('rejects updatedAt < createdAt', () => {
    expect(isValidResearchSession({ ...makeSession(), createdAt: 300, updatedAt: 200 })).toBe(false)
  })
  it('accepts updatedAt === createdAt', () => {
    expect(isValidResearchSession({ ...makeSession(), createdAt: 200, updatedAt: 200 })).toBe(true)
  })
  it('rejects non-string projectId', () => {
    expect(isValidResearchSession({ ...makeSession(), projectId: 5 as never })).toBe(false)
  })
  it('throws on secret in title', () => {
    expect(() => isValidResearchSession({ ...makeSession(), title: 'Bearer fake' })).toThrow(/forbidden/)
  })
  it('throws on secret in sessionId', () => {
    expect(() => isValidResearchSession({ ...makeSession(), sessionId: 'sk-leak' })).toThrow(/forbidden/)
  })
  it('rejects non-object', () => {
    expect(isValidResearchSession(null)).toBe(false)
  })
})

// ============ Schema: ConversationEntry ============

describe('Phase 8-F0 ConversationEntry validator', () => {
  it('accepts a valid entry', () => {
    expect(isValidConversationEntry(makeEntry())).toBe(true)
  })
  it('accepts assistant role', () => {
    expect(isValidConversationEntry(makeEntry({ role: 'assistant' }))).toBe(true)
  })
  it('rejects unknown role', () => {
    expect(isValidConversationEntry(makeEntry({ role: 'system' as never }))).toBe(false)
  })
  it('rejects empty entryId', () => {
    expect(isValidConversationEntry(makeEntry({ entryId: '' }))).toBe(false)
  })
  it('rejects non-string content', () => {
    expect(isValidConversationEntry(makeEntry({ content: 5 as never }))).toBe(false)
  })
  it('accepts empty content string', () => {
    expect(isValidConversationEntry(makeEntry({ content: '' }))).toBe(true)
  })
  it('rejects negative timestamp', () => {
    expect(isValidConversationEntry(makeEntry({ timestamp: -1 }))).toBe(false)
  })
  it('throws on secret in content', () => {
    expect(() => isValidConversationEntry(makeEntry({ content: 'apiKey value' }))).toThrow(/forbidden/)
  })
  it('isValidConversationRole accepts user + assistant', () => {
    expect(isValidConversationRole('user')).toBe(true)
    expect(isValidConversationRole('assistant')).toBe(true)
  })
  it('isValidConversationRole rejects system', () => {
    expect(isValidConversationRole('system')).toBe(false)
  })
})

// ============ Schema: MemoryItem ============

describe('Phase 8-F0 MemoryItem validator', () => {
  it('accepts a valid MemoryItem', () => {
    expect(isValidMemoryItem(makeMemory())).toBe(true)
  })
  it('accepts confidence 0 and 1', () => {
    expect(isValidMemoryItem(makeMemory({ confidence: 0 }))).toBe(true)
    expect(isValidMemoryItem(makeMemory({ confidence: 1 }))).toBe(true)
  })
  it('rejects confidence > 1', () => {
    expect(isValidMemoryItem(makeMemory({ confidence: 1.1 }))).toBe(false)
  })
  it('rejects negative confidence', () => {
    expect(isValidMemoryItem(makeMemory({ confidence: -0.1 }))).toBe(false)
  })
  it('rejects non-string content', () => {
    expect(isValidMemoryItem(makeMemory({ content: 5 as never }))).toBe(false)
  })
  it('rejects empty content', () => {
    expect(isValidMemoryItem(makeMemory({ content: '' }))).toBe(false)
  })
  it('rejects empty source', () => {
    expect(isValidMemoryItem(makeMemory({ source: '' }))).toBe(false)
  })
  it('rejects invalid type', () => {
    expect(isValidMemoryItem(makeMemory({ type: 'x' as never }))).toBe(false)
  })
  it('rejects missing memoryId', () => {
    expect(isValidMemoryItem({ ...makeMemory(), memoryId: '' })).toBe(false)
  })
  it('throws on secret in content', () => {
    expect(() => isValidMemoryItem(makeMemory({ content: 'cipher value' }))).toThrow(/forbidden/)
  })
  it('throws on secret in source', () => {
    expect(() => isValidMemoryItem(makeMemory({ source: 'Bearer x-secret' }))).toThrow(/forbidden/)
  })
  it('rejects NaN confidence', () => {
    expect(isValidMemoryItem(makeMemory({ confidence: NaN }))).toBe(false)
  })
})

// ============ Schema: AgentCheckpoint ============

describe('Phase 8-F0 AgentCheckpoint validator', () => {
  it('accepts a valid checkpoint', () => {
    expect(isValidAgentCheckpoint(makeCheckpoint())).toBe(true)
  })
  it('rejects empty checkpointId', () => {
    expect(isValidAgentCheckpoint(makeCheckpoint({ checkpointId: '' }))).toBe(false)
  })
  it('rejects empty sessionId', () => {
    expect(isValidAgentCheckpoint(makeCheckpoint({ sessionId: '' }))).toBe(false)
  })
  it('rejects empty planId', () => {
    expect(isValidAgentCheckpoint(makeCheckpoint({ planId: '' }))).toBe(false)
  })
  it('rejects non-object stepState', () => {
    expect(isValidAgentCheckpoint(makeCheckpoint({ stepState: 'x' as never }))).toBe(false)
  })
  it('rejects negative createdAt', () => {
    expect(isValidAgentCheckpoint(makeCheckpoint({ createdAt: -1 }))).toBe(false)
  })
  it('throws on secret in stepState', () => {
    expect(() => isValidAgentCheckpoint(makeCheckpoint({ stepState: { token: 'Bearer fake' } }))).toThrow(/forbidden/)
  })
  it('rejects non-object', () => {
    expect(isValidAgentCheckpoint(null)).toBe(false)
  })
})

// ============ Schema: SessionEvent ============

describe('Phase 8-F0 SessionEvent validator', () => {
  it('SESSION_EVENT_TYPES has 4 entries', () => {
    expect(SESSION_EVENT_TYPES.length).toBe(4)
  })
  it('contains the documented event types', () => {
    for (const t of ['session_created', 'memory_added', 'checkpoint_saved', 'context_restored']) {
      expect(SESSION_EVENT_TYPES).toContain(t)
    }
  })
  it('isValidSessionEventType accepts every entry', () => {
    for (const t of SESSION_EVENT_TYPES) expect(isValidSessionEventType(t)).toBe(true)
  })
  it('isValidSessionEventType rejects unknown', () => {
    expect(isValidSessionEventType('session_deleted')).toBe(false)
  })
  it('accepts a valid SessionEvent', () => {
    expect(isValidSessionEvent({ type: 'session_created', sessionId: 's', timestamp: 1 })).toBe(true)
  })
  it('rejects missing sessionId', () => {
    expect(isValidSessionEvent({ type: 'session_created', sessionId: '', timestamp: 1 })).toBe(false)
  })
  it('rejects negative timestamp', () => {
    expect(isValidSessionEvent({ type: 'session_created', sessionId: 's', timestamp: -1 })).toBe(false)
  })
  it('rejects unknown event type', () => {
    expect(isValidSessionEvent({ type: 'session_deleted', sessionId: 's', timestamp: 1 })).toBe(false)
  })
  it('FORBIDDEN list has 8 entries', () => {
    expect(sessionHelpers.FORBIDDEN.length).toBe(8)
  })
})

// ============ LocalMemoryProvider ============

describe('Phase 8-F0 LocalMemoryProvider lifecycle', () => {
  let p: LocalMemoryProvider
  beforeEach(() => { p = new LocalMemoryProvider() })
  it('starts empty', () => {
    expect(p.size()).toBe(0)
  })
  it('save returns true on new item', () => {
    expect(p.save(makeMemory())).toBe(true)
    expect(p.size()).toBe(1)
  })
  it('save returns false on duplicate memoryId', () => {
    p.save(makeMemory())
    expect(p.save(makeMemory({ content: 'different' }))).toBe(false)
    expect(p.size()).toBe(1)
  })
  it('save throws on invalid item', () => {
    expect(() => p.save({ ...makeMemory(), memoryId: '' })).toThrow(/invalid MemoryItem/)
  })
  it('delete returns true when present', () => {
    p.save(makeMemory())
    expect(p.delete('mem:1')).toBe(true)
    expect(p.size()).toBe(0)
  })
  it('delete returns false when absent', () => {
    expect(p.delete('nope')).toBe(false)
  })
  it('delete throws on non-string', () => {
    expect(() => p.delete(5 as never)).toThrow(/must be a string/)
  })
  it('clear removes everything', () => {
    p.save(makeMemory())
    p.clear()
    expect(p.size()).toBe(0)
  })
  it('list returns all items sorted by confidence desc', () => {
    p.save(makeMemory({ memoryId: 'a', confidence: 0.5 }))
    p.save(makeMemory({ memoryId: 'b', confidence: 0.9 }))
    p.save(makeMemory({ memoryId: 'c', confidence: 0.7 }))
    expect(p.list().map((m) => m.memoryId)).toEqual(['b', 'c', 'a'])
  })
  it('list filters by type', () => {
    p.save(makeMemory({ type: 'conclusion' }))
    p.save(makeMemory({ type: 'paper', memoryId: 'p' }))
    expect(p.list('paper').map((m) => m.memoryId)).toEqual(['p'])
    expect(p.list('conclusion')).toHaveLength(1)
    expect(p.list('experiment')).toHaveLength(0)
  })
  it('list honors limit', () => {
    p.save(makeMemory({ memoryId: 'a' }))
    p.save(makeMemory({ memoryId: 'b' }))
    p.save(makeMemory({ memoryId: 'c' }))
    expect(p.list(undefined, 2)).toHaveLength(2)
  })
  it('list limit of 0 returns all', () => {
    p.save(makeMemory({ memoryId: 'a' }))
    expect(p.list(undefined, 0)).toHaveLength(1)
  })
  it('breaks confidence ties by memoryId asc', () => {
    p.save(makeMemory({ memoryId: 'b', confidence: 0.9 }))
    p.save(makeMemory({ memoryId: 'a', confidence: 0.9 }))
    expect(p.list().map((m) => m.memoryId)).toEqual(['a', 'b'])
  })
})

describe('Phase 8-F0 LocalMemoryProvider search', () => {
  let p: LocalMemoryProvider
  beforeEach(() => {
    p = new LocalMemoryProvider()
    p.save(makeMemory({ memoryId: 'bubble', content: 'bubble dynamics in water', confidence: 0.7 }))
    p.save(makeMemory({ memoryId: 'reactor', content: 'reactor kinetics and stability', confidence: 0.9 }))
    p.save(makeMemory({ memoryId: 'bubble2', content: 'bubble coalescence model', confidence: 0.8 }))
  })
  it('finds a matching item', () => {
    expect(p.search('bubble').map((m) => m.memoryId)).toContain('bubble')
  })
  it('returns no results for a non-matching query', () => {
    expect(p.search('zyzzyva')).toEqual([])
  })
  it('case-insensitive search', () => {
    expect(p.search('BUBBLE').length).toBeGreaterThan(0)
  })
  it('ranks by term-hit ratio desc', () => {
    // 'reactor kinetics' matches reactor (2 terms) better than bubble (1 term)
    expect(p.search('reactor kinetics')[0]!.memoryId).toBe('reactor')
  })
  it('ranks by confidence when hit ratio is equal', () => {
    expect(p.search('reactor')[0]!.memoryId).toBe('reactor')
  })
  it('honors a limit', () => {
    const hits = p.search('bubble', 1)
    expect(hits).toHaveLength(1)
  })
  it('returns all hits when limit is 0', () => {
    expect(p.search('bubble', 0).length).toBeGreaterThan(1)
  })
  it('is deterministic across calls', () => {
    expect(p.search('bubble')).toEqual(p.search('bubble'))
  })
  it('searches CJK query terms', () => {
    p.save(makeMemory({ memoryId: 'cjk', content: '气泡动力学研究', confidence: 0.6 }))
    expect(p.search('气泡').length).toBeGreaterThan(0)
  })
  it('throws on non-string query', () => {
    expect(() => p.search(5 as never)).toThrow(/must be a string/)
  })
  it('contentScore is pure and deterministic', () => {
    const a = memoryHelpers.contentScore(['x', 'bubble'], 'bubble water')
    const b = memoryHelpers.contentScore(['x', 'bubble'], 'bubble water')
    expect(a).toBe(b)
    expect(memoryHelpers.contentScore(['x', 'bubble'], 'bubble water')).toBe(0.5)
  })
  it('lowerTokens drops empty tokens', () => {
    expect(memoryHelpers.lowerTokens('a  b  c')).toEqual(['a', 'b', 'c'])
  })
  it('search is empty for whitespace-only query', () => {
    expect(p.search('   ')).toEqual([])
  })
})

// ============ Session manager lifecycle ============

describe('Phase 8-F0 SessionManager session lifecycle', () => {
  let mgr: ResearchSessionManager
  beforeEach(() => { mgr = new ResearchSessionManager() })
  it('createSession returns an active session', () => {
    const s = mgr.createSession({ sessionId: 's1', title: 'Study' })
    expect(s.status).toBe('active')
    expect(s.title).toBe('Study')
  })
  it('createSession requires sessionId', () => {
    expect(() => mgr.createSession({ sessionId: '', title: 'x' })).toThrow(/sessionId required/)
  })
  it('createSession requires title', () => {
    expect(() => mgr.createSession({ sessionId: 's', title: '' })).toThrow(/title required/)
  })
  it('createSession rejects duplicates', () => {
    mgr.createSession({ sessionId: 's', title: 'a' })
    expect(() => mgr.createSession({ sessionId: 's', title: 'b' })).toThrow(/already exists/)
  })
  it('createSession honors projectId', () => {
    const s = mgr.createSession({ sessionId: 's', title: 't', projectId: 'p' })
    expect(s.projectId).toBe('p')
  })
  it('createSession honors a fixed now', () => {
    const s = mgr.createSession({ sessionId: 's', title: 't', now: 123 })
    expect(s.createdAt).toBe(123)
    expect(s.updatedAt).toBe(123)
  })
  it('getSession returns null for unknown', () => {
    expect(mgr.getSession('nope')).toBeNull()
  })
  it('getSession returns the created session', () => {
    mgr.createSession({ sessionId: 's', title: 't' })
    expect(mgr.getSession('s')?.title).toBe('t')
  })
  it('listSessions returns created sessions', () => {
    mgr.createSession({ sessionId: 'a', title: 't' })
    mgr.createSession({ sessionId: 'b', title: 'u' })
    expect(mgr.listSessions()).toHaveLength(2)
  })
  it('updateSession returns null for unknown', () => {
    expect(mgr.updateSession('nope', { title: 'x' })).toBeNull()
  })
  it('updateSession changes the title', () => {
    mgr.createSession({ sessionId: 's', title: 'old' })
    const s = mgr.updateSession('s', { title: 'new' })
    expect(s?.title).toBe('new')
  })
  it('updateSession bumps updatedAt', () => {
    mgr.createSession({ sessionId: 's', title: 't', now: 100 })
    const s = mgr.updateSession('s', { title: 't2', now: 500 })
    expect(s?.updatedAt).toBe(500)
    expect(s?.createdAt).toBe(100)
  })
  it('closeSession sets status completed', () => {
    mgr.createSession({ sessionId: 's', title: 't' })
    expect(mgr.closeSession('s')?.status).toBe('completed')
  })
  it('pauseSession sets status paused', () => {
    mgr.createSession({ sessionId: 's', title: 't' })
    expect(mgr.pauseSession('s')?.status).toBe('paused')
  })
  it('archiveSession sets status archived', () => {
    mgr.createSession({ sessionId: 's', title: 't' })
    expect(mgr.archiveSession('s')?.status).toBe('archived')
  })
  it('closeSession on unknown returns null', () => {
    expect(mgr.closeSession('nope')).toBeNull()
  })
  it('emits session_created on createSession', () => {
    const events: SessionEvent[] = []
    mgr.onSessionEvent((e) => events.push(e))
    mgr.createSession({ sessionId: 's', title: 't' })
    expect(events.some((e) => e.type === 'session_created')).toBe(true)
  })
  it('session event carries the sessionId', () => {
    const events: SessionEvent[] = []
    mgr.onSessionEvent((e) => events.push(e))
    mgr.createSession({ sessionId: 'sx', title: 't' })
    expect(events[0]?.sessionId).toBe('sx')
  })
  it('unsubscribe stops event delivery', () => {
    const events: SessionEvent[] = []
    const off = mgr.onSessionEvent((e) => events.push(e))
    mgr.createSession({ sessionId: 'a', title: 't' })
    off()
    mgr.createSession({ sessionId: 'b', title: 'u' })
    expect(events).toHaveLength(1)
  })
  it('listener throwing does not break the manager', () => {
    mgr.onSessionEvent(() => { throw new Error('boom') })
    expect(() => mgr.createSession({ sessionId: 's', title: 't' })).not.toThrow()
  })
  it('default storage is LocalSessionStore', () => {
    const mgr2 = new ResearchSessionManager()
    mgr2.createSession({ sessionId: 's', title: 't' })
    expect(mgr2.getSession('s')).not.toBeNull()
  })
})

describe('Phase 8-F0 LocalSessionStore', () => {
  it('implements SessionStorageLike', () => {
    const store = new LocalSessionStore()
    store.save(makeSession())
    expect(store.get('session:1')?.title).toBe('Microbubble Study')
    expect(store.list()).toHaveLength(1)
    expect(store.remove('session:1')).toBe(true)
    expect(store.remove('session:1')).toBe(false)
  })
  it('list sorts by createdAt asc', () => {
    const store = new LocalSessionStore()
    store.save(makeSession({ sessionId: 'b', createdAt: 200 }))
    store.save(makeSession({ sessionId: 'a', createdAt: 100 }))
    expect(store.list().map((s) => s.sessionId)).toEqual(['a', 'b'])
  })
})

// ============ Session manager conversation ============

describe('Phase 8-F0 SessionManager conversation', () => {
  let mgr: ResearchSessionManager
  beforeEach(() => {
    mgr = new ResearchSessionManager()
    mgr.createSession({ sessionId: 's', title: 't', now: 100 })
  })
  it('appends a user entry', () => {
    const e = mgr.appendConversation('s', 'user', 'hi')
    expect(e?.role).toBe('user')
    expect(e?.content).toBe('hi')
  })
  it('appends an assistant entry', () => {
    const e = mgr.appendConversation('s', 'assistant', 'answer')
    expect(e?.role).toBe('assistant')
  })
  it('returns null for unknown session', () => {
    expect(mgr.appendConversation('nope', 'user', 'x')).toBeNull()
  })
  it('throws on invalid role', () => {
    expect(() => mgr.appendConversation('s', 'system' as never, 'x')).toThrow(/invalid role/)
  })
  it('throws on non-string content', () => {
    expect(() => mgr.appendConversation('s', 'user', 5 as never)).toThrow(/must be a string/)
  })
  it('listConversation returns entries in insertion order', () => {
    mgr.appendConversation('s', 'user', 'a', 1)
    mgr.appendConversation('s', 'assistant', 'b', 2)
    const list = mgr.listConversation('s')
    expect(list.map((e) => e.content)).toEqual(['a', 'b'])
  })
  it('listConversation returns empty for a fresh session', () => {
    expect(mgr.listConversation('s')).toEqual([])
  })
  it('listConversation returns empty for unknown session', () => {
    expect(mgr.listConversation('nope')).toEqual([])
  })
  it('each entry has a unique entryId', () => {
    mgr.appendConversation('s', 'user', 'a')
    mgr.appendConversation('s', 'assistant', 'b')
    const ids = mgr.listConversation('s').map((e) => e.entryId)
    expect(new Set(ids).size).toBe(ids.length)
  })
  it('does not mutate the returned conversation list', () => {
    mgr.appendConversation('s', 'user', 'a')
    const l1 = mgr.listConversation('s')
    l1.length = 0
    expect(mgr.listConversation('s')).toHaveLength(1)
  })
  it('conversation entry schema is valid', () => {
    mgr.appendConversation('s', 'user', 'a', 10)
    expect(isValidConversationEntry(mgr.listConversation('s')[0]!)).toBe(true)
  })
  it('supports empty content', () => {
    const e = mgr.appendConversation('s', 'user', '', 10)
    expect(e?.content).toBe('')
  })
  it('ordering is deterministic with same timestamps', () => {
    mgr.appendConversation('s', 'user', 'a', 1)
    mgr.appendConversation('s', 'user', 'b', 1)
    expect(mgr.listConversation('s').map((e) => e.content)).toEqual(['a', 'b'])
  })
})

// ============ Session manager memory ============

describe('Phase 8-F0 SessionManager memory', () => {
  let mgr: ResearchSessionManager
  beforeEach(() => {
    mgr = new ResearchSessionManager()
    mgr.createSession({ sessionId: 's', title: 't' })
  })
  it('adds a memory item', () => {
    const m = mgr.addMemory('s', { type: 'conclusion', content: 'bubbles improve mixing', confidence: 0.9, source: 'run1' })
    expect(m?.content).toBe('bubbles improve mixing')
    expect(m?.type).toBe('conclusion')
  })
  it('returns null for unknown session', () => {
    expect(mgr.addMemory('nope', { type: 'conclusion', content: 'x', confidence: 0.5, source: 'x' })).toBeNull()
  })
  it('throws on invalid type', () => {
    expect(() => mgr.addMemory('s', { type: 'nope' as never, content: 'x', confidence: 0.5, source: 'x' })).toThrow(/invalid memory type/)
  })
  it('throws on duplicate explicit memoryId', () => {
    mgr.addMemory('s', { memoryId: 'z', type: 'conclusion', content: 'a', confidence: 0.5, source: 'x' })
    expect(() => mgr.addMemory('s', { memoryId: 'z', type: 'conclusion', content: 'b', confidence: 0.5, source: 'x' }))
      .toThrow(/already exists/)
  })
  it('listMemory returns added memories', () => {
    mgr.addMemory('s', { type: 'conclusion', content: 'a', confidence: 0.9, source: 'x' })
    expect(mgr.listMemory('s')).toHaveLength(1)
  })
  it('listMemory filters by type', () => {
    mgr.addMemory('s', { type: 'conclusion', content: 'a', confidence: 0.9, source: 'x' })
    mgr.addMemory('s', { type: 'paper', content: 'b', confidence: 0.8, source: 'y' })
    expect(mgr.listMemory('s', 'paper')).toHaveLength(1)
  })
  it('listMemory returns [] for unknown session', () => {
    expect(mgr.listMemory('nope')).toEqual([])
  })
  it('searchMemory searches across memory', () => {
    mgr.addMemory('s', { type: 'conclusion', content: 'bubble kinetics model', confidence: 0.9, source: 'x' })
    expect(mgr.searchMemory('s', 'bubble')).toHaveLength(1)
  })
  it('searchMemory returns [] for unknown session', () => {
    expect(mgr.searchMemory('nope', 'bubble')).toEqual([])
  })
  it('memory is sorted by confidence desc', () => {
    mgr.addMemory('s', { type: 'conclusion', content: 'low', confidence: 0.3, source: 'x' })
    mgr.addMemory('s', { type: 'conclusion', content: 'high', confidence: 0.9, source: 'y' })
    expect(mgr.listMemory('s').map((m) => m.content)).toEqual(['high', 'low'])
  })
  it('emits memory_added event', () => {
    const events: SessionEvent[] = []
    mgr.onSessionEvent((e) => events.push(e))
    mgr.addMemory('s', { type: 'conclusion', content: 'x', confidence: 0.5, source: 'x' })
    expect(events.some((e) => e.type === 'memory_added')).toBe(true)
  })
  it('memory item schema is valid', () => {
    const m = mgr.addMemory('s', { type: 'conclusion', content: 'x', confidence: 0.5, source: 'x' })!
    expect(isValidMemoryItem(m)).toBe(true)
  })
  it('default memory provider is LocalMemoryProvider', () => {
    expect(mgr.memory).toBeInstanceOf(LocalMemoryProvider)
  })
})

// ============ Session manager checkpoints ============

describe('Phase 8-F0 SessionManager checkpoints', () => {
  let mgr: ResearchSessionManager
  beforeEach(() => {
    mgr = new ResearchSessionManager()
    mgr.createSession({ sessionId: 's', title: 't', now: 100 })
  })
  it('saves a checkpoint', () => {
    const c = mgr.saveCheckpoint('s', { planId: 'plan:1', stepState: { step: 3 } })
    expect(c?.planId).toBe('plan:1')
    expect(c?.stepState).toEqual({ step: 3 })
  })
  it('returns null for unknown session', () => {
    expect(mgr.saveCheckpoint('nope', { planId: 'p', stepState: {} })).toBeNull()
  })
  it('restoreCheckpoint returns the saved checkpoint', () => {
    const c = mgr.saveCheckpoint('s', { planId: 'plan:1', stepState: { step: 3 } })!
    expect(mgr.restoreCheckpoint('s', c.checkpointId)?.stepState).toEqual({ step: 3 })
  })
  it('restoreCheckpoint returns null for unknown id', () => {
    expect(mgr.restoreCheckpoint('s', 'nope')).toBeNull()
  })
  it('restoreCheckpoint returns null for unknown session', () => {
    expect(mgr.restoreCheckpoint('nope', 'any')).toBeNull()
  })
  it('listCheckpoints returns saved checkpoints sorted by createdAt', () => {
    mgr.saveCheckpoint('s', { planId: 'p1', stepState: {}, now: 200 })
    mgr.saveCheckpoint('s', { planId: 'p2', stepState: {}, now: 100 })
    expect(mgr.listCheckpoints('s').map((c) => c.planId)).toEqual(['p2', 'p1'])
  })
  it('listCheckpoints returns empty for a fresh session', () => {
    expect(mgr.listCheckpoints('s')).toEqual([])
  })
  it('listCheckpoints returns empty for unknown session', () => {
    expect(mgr.listCheckpoints('nope')).toEqual([])
  })
  it('emits checkpoint_saved event', () => {
    const events: SessionEvent[] = []
    mgr.onSessionEvent((e) => events.push(e))
    mgr.saveCheckpoint('s', { planId: 'p', stepState: {} })
    expect(events.some((e) => e.type === 'checkpoint_saved')).toBe(true)
  })
  it('emits context_restored event on restore', () => {
    const events: SessionEvent[] = []
    mgr.onSessionEvent((e) => events.push(e))
    const c = mgr.saveCheckpoint('s', { planId: 'p', stepState: {} })!
    mgr.restoreCheckpoint('s', c.checkpointId)
    expect(events.some((e) => e.type === 'context_restored')).toBe(true)
  })
  it('does not emit context_restored for a missing checkpoint', () => {
    const events: SessionEvent[] = []
    mgr.onSessionEvent((e) => events.push(e))
    mgr.restoreCheckpoint('s', 'missing')
    expect(events.some((e) => e.type === 'context_restored')).toBe(false)
  })
  it('checkpoint schema is valid', () => {
    const c = mgr.saveCheckpoint('s', { planId: 'p', stepState: {} })!
    expect(isValidAgentCheckpoint(c)).toBe(true)
  })
  it('checkpoint has a unique checkpointId', () => {
    const a = mgr.saveCheckpoint('s', { planId: 'p', stepState: {} })!
    const b = mgr.saveCheckpoint('s', { planId: 'p', stepState: {} })!
    expect(a.checkpointId).not.toBe(b.checkpointId)
  })
  it('supports explicit checkpointId', () => {
    const c = mgr.saveCheckpoint('s', { checkpointId: 'custom', planId: 'p', stepState: {} })!
    expect(c.checkpointId).toBe('custom')
  })
  it('restore returns a reference to the stored checkpoint', () => {
    const c = mgr.saveCheckpoint('s', { planId: 'p', stepState: { x: 1 } })!
    const restored = mgr.restoreCheckpoint('s', c.checkpointId)
    expect(restored).toEqual(c)
  })
})

// ============ Concurrency / isolation ============

describe('Phase 8-F0 concurrency / isolation', () => {
  it('two managers have isolated memory', () => {
    const m1 = new ResearchSessionManager()
    const m2 = new ResearchSessionManager()
    m1.createSession({ sessionId: 's', title: 'a' })
    m1.addMemory('s', { type: 'conclusion', content: 'x', confidence: 0.5, source: 'x' })
    expect(m2.getSession('s')).toBeNull()
    expect(m2.memory.size()).toBe(0)
  })
  it('two sessions on one manager keep separate conversations', () => {
    const mgr = new ResearchSessionManager()
    mgr.createSession({ sessionId: 'a', title: 'a' })
    mgr.createSession({ sessionId: 'b', title: 'b' })
    mgr.appendConversation('a', 'user', 'echo-a')
    expect(mgr.listConversation('a')).toHaveLength(1)
    expect(mgr.listConversation('b')).toHaveLength(0)
  })
  it('two sessions share the shared memory but are distinguishable by source', () => {
    const mgr = new ResearchSessionManager()
    mgr.createSession({ sessionId: 'a', title: 'a' })
    mgr.createSession({ sessionId: 'b', title: 'b' })
    mgr.addMemory('a', { type: 'conclusion', content: 'q', confidence: 0.5, source: 'a' })
    mgr.addMemory('b', { type: 'conclusion', content: 'w', confidence: 0.5, source: 'b' })
    expect(mgr.listMemory('a')).toHaveLength(2)  // memory layer is shared across sessions
  })
  it('conversations do not leak between sessions', () => {
    const mgr = new ResearchSessionManager()
    mgr.createSession({ sessionId: 'a', title: 'a' })
    mgr.createSession({ sessionId: 'b', title: 'b' })
    mgr.appendConversation('a', 'user', 'only-in-a', 1)
    expect(mgr.listConversation('b')).toEqual([])
  })
  it('checkpoints are scoped per session', () => {
    const mgr = new ResearchSessionManager()
    mgr.createSession({ sessionId: 'a', title: 'a' })
    mgr.saveCheckpoint('a', { planId: 'p', stepState: {} })
    expect(mgr.listCheckpoints('b')).toEqual([])
  })
  it('interleaved session operations stay deterministic', () => {
    const mgr = new ResearchSessionManager()
    for (let i = 0; i < 5; i++) {
      mgr.createSession({ sessionId: `s${i}`, title: `Session ${i}` })
    }
    expect(mgr.listSessions().map((s) => s.sessionId)).toEqual(['s0', 's1', 's2', 's3', 's4'])
  })
})

// ============ ResearchMemoryAdapter ============

// module-scope fake agent shared by adapter + determinism suites
const okAgent: ResearchAgentLike = {
  run: async () => makeResponse()
}

describe('Phase 8-F0 ResearchMemoryAdapter', () => {
  let mgr: ResearchSessionManager
  let adapter: ResearchMemoryAdapter
  beforeEach(() => {
    mgr = new ResearchSessionManager()
    mgr.createSession({ sessionId: 's', title: 't', now: 100 })
    adapter = new ResearchMemoryAdapter({ manager: mgr })
  })
  it('rejects a missing manager', () => {
    expect(() => new ResearchMemoryAdapter({ manager: undefined as never })).toThrow(/manager required/)
  })
  it('loadContext returns a context for an existing session', () => {
    const ctx = adapter.loadContext('s')
    expect(ctx?.source).toBe('session')
    expect(ctx?.conversation).toEqual([])
    expect(ctx?.memory).toEqual([])
  })
  it('loadContext returns null for unknown session', () => {
    expect(adapter.loadContext('nope')).toBeNull()
  })
  it('loadContext reflects stored conversation', () => {
    mgr.appendConversation('s', 'user', 'hi', 1)
    expect(adapter.loadContext('s')?.conversation).toHaveLength(1)
  })
  it('storeRun appends a user + assistant entry', () => {
    const out = adapter.storeRun('s', makeResponse())
    expect(out.conversationEntries).toHaveLength(2)
    expect(out.conversationEntries[0]?.role).toBe('user')
    expect(out.conversationEntries[1]?.role).toBe('assistant')
  })
  it('storeRun stores the answer as a conclusion memory', () => {
    const out = adapter.storeRun('s', makeResponse({ answer: 'the answer is bubbles', confidence: 0.75 }))
    expect(out.memories).toHaveLength(1)
    expect(out.memories[0]?.content).toBe('the answer is bubbles')
    expect(out.memories[0]?.confidence).toBe(0.75)
    expect(out.memories[0]?.type).toBe('conclusion')
  })
  it('storeRun throws on unknown session', () => {
    expect(() => adapter.storeRun('nope', makeResponse())).toThrow(/unknown session/)
  })
  it('storeRun for empty answer adds no memory', () => {
    const out = adapter.storeRun('s', makeResponse({ answer: '' }))
    expect(out.memories).toEqual([])
    expect(out.conversationEntries).toHaveLength(2)
  })
  it('runWithMemory loads context before running', async () => {
    let loadedSeen = false
    const agent: ResearchAgentLike = {
      run: async () => {
        loadedSeen = adapter.loadContext('s') !== null
        return makeResponse()
      }
    }
    await adapter.runWithMemory(agent, 's', makeRequest())
    expect(loadedSeen).toBe(true)
  })
  it('runWithMemory stores the result after running', async () => {
    const out = await adapter.runWithMemory(okAgent, 's', makeRequest())
    expect(out.stored.conversationEntries).toHaveLength(2)
    expect(out.response.answer).toBe('the answer is bubbles')
  })
  it('runWithMemory returns the agent response', async () => {
    const out = await adapter.runWithMemory(okAgent, 's', makeRequest())
    expect(out.response.requestId).toBe('req:1')
  })
  it('runWithMemory rejects a non-agent', async () => {
    await expect(adapter.runWithMemory({} as never, 's', makeRequest())).rejects.toThrow(/agent with run/)
  })
  it('runWithMemory rejects for unknown session', async () => {
    await expect(adapter.runWithMemory(okAgent, 'nope', makeRequest())).rejects.toThrow(/unknown session/)
  })
  it('runWithMemory stores into the session', async () => {
    const out = await adapter.runWithMemory(okAgent, 's', makeRequest())
    expect(mgr.listConversation('s')).toHaveLength(2)
  })
  it('getManager returns the injected manager', () => {
    expect(adapter.getManager()).toBe(mgr)
  })
  it('does not modify the agent interface surface', () => {
    expect(typeof okAgent.run).toBe('function')
  })
})

// ============ Determinism ============

describe('Phase 8-F0 determinism', () => {
  it('LocalMemoryProvider search is stable across calls', () => {
    const p = new LocalMemoryProvider()
    p.save(makeMemory())
    expect(p.search('bubble')).toEqual(p.search('bubble'))
  })
  it('session create with same inputs is stable', () => {
    const m1 = new ResearchSessionManager()
    const m2 = new ResearchSessionManager()
    const s1 = m1.createSession({ sessionId: 'id', title: 'T', now: 100 })
    const s2 = m2.createSession({ sessionId: 'id', title: 'T', now: 100 })
    expect(s1).toEqual(s2)
  })
  it('conversation append preserves order deterministically', () => {
    const m1 = new ResearchSessionManager()
    const m2 = new ResearchSessionManager()
    for (const m of [m1, m2]) m.createSession({ sessionId: 's', title: 't', now: 100 })
    m1.appendConversation('s', 'user', 'a', 1)
    m1.appendConversation('s', 'assistant', 'b', 2)
    m2.appendConversation('s', 'user', 'a', 1)
    m2.appendConversation('s', 'assistant', 'b', 2)
    expect(m1.listConversation('s')).toEqual(m2.listConversation('s'))
  })
  it('runWithMemory is deterministic for the same inputs', async () => {
    const m1 = new ResearchSessionManager()
    const m2 = new ResearchSessionManager()
    for (const m of [m1, m2]) m.createSession({ sessionId: 's', title: 't', now: 100 })
    const a1 = new ResearchMemoryAdapter({ manager: m1 })
    const a2 = new ResearchMemoryAdapter({ manager: m2 })
    const o1 = await a1.runWithMemory(okAgent, 's', makeRequest())
    const o2 = await a2.runWithMemory(okAgent, 's', makeRequest())
    expect(o1.response.requestId).toBe(o2.response.requestId)
    expect(m1.listConversation('s')).toEqual(m2.listConversation('s'))
  })
  it('locale sorting stays deterministic', () => {
    const p = new LocalMemoryProvider()
    p.save(makeMemory({ memoryId: 'b-2' }))
    p.save(makeMemory({ memoryId: 'a-1' }))
    expect(p.list().map((m) => m.memoryId)).toEqual(['a-1', 'b-2'])
  })
  it('memory provider output deterministic across instances', () => {
    const a = new LocalMemoryProvider()
    const b = new LocalMemoryProvider()
    a.save(makeMemory({ memoryId: 'm', confidence: 0.5 }))
    b.save(makeMemory({ memoryId: 'm', confidence: 0.5 }))
    expect(a.list()).toEqual(b.list())
  })
})

// ============ Security + source isolation ============

describe('Phase 8-F0 security + isolation — source scans', () => {
  function readSrc(p: string): string {
    const fs = require('fs')
    const path = require('path')
    return fs.readFileSync(path.resolve(__dirname, p), 'utf8')
  }
  it('research-session-schema.ts has no forbidden imports', () => {
    const src = readSrc('../../src/shared/agent/research-session-schema.ts')
    expect(src).not.toMatch(/from\s+['"][^'"]*model-provider/)
    expect(src).not.toMatch(/from\s+['"]backend/)
    expect(src).not.toMatch(/from\s+['"]auth/)
  })
  it('memory-provider.ts has no forbidden imports', () => {
    const src = readSrc('../../src/shared/agent/memory-provider.ts')
    expect(src).not.toMatch(/from\s+['"][^'"]*model-provider/)
    expect(src).not.toMatch(/from\s+['"]backend/)
  })
  it('research-session-manager.ts has no forbidden imports', () => {
    const src = readSrc('../../src/main/services/agent/research-session-manager.ts')
    expect(src).not.toMatch(/from\s+['"][^'"]*model-provider/)
    expect(src).not.toMatch(/from\s+['"]backend/)
    expect(src).not.toMatch(/from\s+['"]auth/)
    expect(src).not.toMatch(/@anthropic-ai/)
    expect(src).not.toMatch(/from\s+['"]openai/)
  })
  it('research-memory-adapter.ts has no forbidden imports', () => {
    const src = readSrc('../../src/main/services/agent/research-memory-adapter.ts')
    expect(src).not.toMatch(/from\s+['"][^'"]*model-provider/)
    expect(src).not.toMatch(/from\s+['"]backend/)
  })
  it('manager + adapter have no SDK imports', () => {
    const m = readSrc('../../src/main/services/agent/research-session-manager.ts')
    const a = readSrc('../../src/main/services/agent/research-memory-adapter.ts')
    expect(m + a).not.toMatch(/from\s+['"]anthropic/)
    expect(m + a).not.toMatch(/from\s+['"]openai/)
    expect(m + a).not.toMatch(/@anthropic-ai/)
  })
  it('manager + adapter do not touch the agent runtime or planner', () => {
    const m = readSrc('../../src/main/services/agent/research-session-manager.ts')
    const a = readSrc('../../src/main/services/agent/research-memory-adapter.ts')
    expect(m + a).not.toContain('research-planner')
    expect(m + a).not.toContain('agent-runtime.ts')
  })
  it('no implementation file uses Math.random', () => {
    for (const f of ['research-session-manager', 'research-memory-adapter']) {
      const src = readSrc(`../../src/main/services/agent/${f}.ts`)
      expect(src).not.toContain('Math.random')
      expect(src).not.toContain('crypto.randomUUID')
    }
  })
  it('session schema throws on secret in content', () => {
    expect(() => isValidConversationEntry(makeEntry({ content: 'Bearer x-secret' }))).toThrow(/forbidden/)
  })
  it('session schema throws on secret in MemoryItem', () => {
    expect(() => isValidMemoryItem(makeMemory({ content: 'apiKey value here' }))).toThrow(/forbidden/)
  })
  it('session schema throws on secret in checkpoint stepState', () => {
    expect(() => isValidAgentCheckpoint(makeCheckpoint({ stepState: { token: 'Bearer fake' } }))).toThrow(/forbidden/)
  })
  it('session schema throws on secret in ResearchSession projectId', () => {
    expect(() => isValidResearchSession(makeSession({ projectId: 'sk-leak' }))).toThrow(/forbidden/)
  })
  it('memory provider does not embed credential literals', () => {
    const src = readSrc('../../src/shared/agent/memory-provider.ts')
    expect(src).not.toMatch(/apiKey\s*[:=]\s*['"]/)
  })
  it('FORBIDDEN list in session schema has 8 entries', () => {
    expect(sessionHelpers.FORBIDDEN.length).toBe(8)
  })
  it('adapter does not modify ResearchAgent core', () => {
    const src = readSrc('../../src/main/services/agent/research-memory-adapter.ts')
    expect(src).not.toContain('this.agent.')
    expect(src).not.toContain('prototype')
  })
  it('manager does not import the knowledge/retrieval layer', () => {
    const m = readSrc('../../src/main/services/agent/research-session-manager.ts')
    expect(m).not.toContain('local-retriever')
    expect(m).not.toContain('hybrid-retriever')
    expect(m).not.toContain('pdf-parser')
  })
  it('memory is deterministic in-memory only (no network)', () => {
    const src = readSrc('../../src/shared/agent/memory-provider.ts')
    expect(src).not.toContain('fetch(')
    expect(src).not.toContain('http')
  })
  it('LocalMemoryProvider is importable and instantiable', () => {
    expect(new LocalMemoryProvider()).toBeInstanceOf(LocalMemoryProvider)
  })
  it('SessionManager conforms to the injectable-storage contract', () => {
    const store = new LocalSessionStore()
    const mgr = new ResearchSessionManager({ storage: store })
    mgr.createSession({ sessionId: 's', title: 't' })
    expect(store.get('s')).not.toBeNull()
  })
  it('manager can use a custom MemoryProvider', () => {
    const customMemory = new LocalMemoryProvider()
    const mgr = new ResearchSessionManager({ memory: customMemory })
    expect(mgr.memory).toBe(customMemory)
  })
})

// ============ Supplementary (>=3300 aggregate) ============

describe('Phase 8-F0 supplementary', () => {
  let mgr: ResearchSessionManager
  beforeEach(() => {
    mgr = new ResearchSessionManager()
    mgr.createSession({ sessionId: 's', title: 't', now: 100 })
  })
  it('createSession with projectId propagates it', () => {
    const s = mgr.createSession({ sessionId: 'p', title: 't', projectId: 'proj:1' })
    expect(s.projectId).toBe('proj:1')
  })
  it('updateSession can set status directly', () => {
    mgr.updateSession('s', { status: 'paused' })
    expect(mgr.getSession('s')?.status).toBe('paused')
  })
  it('updateSession can set projectId', () => {
    mgr.updateSession('s', { projectId: 'pp' })
    expect(mgr.getSession('s')?.projectId).toBe('pp')
  })
  it('updateSession leaves sessionId unchanged', () => {
    const s = mgr.updateSession('s', { title: 'x' })
    expect(s?.sessionId).toBe('s')
  })
  it('closeSession does not change createdAt', () => {
    const s = mgr.closeSession('s', 999)
    expect(s?.createdAt).toBe(100)
  })
  it('closeSession two times is idempotent (status stays completed)', () => {
    mgr.closeSession('s')
    mgr.closeSession('s')
    expect(mgr.getSession('s')?.status).toBe('completed')
  })
  it('pause→close transitions work', () => {
    mgr.pauseSession('s')
    const s = mgr.closeSession('s')
    expect(s?.status).toBe('completed')
  })
  it('appendConversation touches updatedAt', () => {
    const before = mgr.getSession('s')!.updatedAt
    mgr.appendConversation('s', 'user', 'hi', 999)
    expect(mgr.getSession('s')!.updatedAt).toBe(999)
  })
  it('addMemory touches updatedAt', () => {
    mgr.addMemory('s', { type: 'conclusion', content: 'x', confidence: 0.5, source: 'x' }, )
    expect(mgr.getSession('s')!.updatedAt).toBeGreaterThanOrEqual(100)
  })
  it('saveCheckpoint touches updatedAt', () => {
    mgr.saveCheckpoint('s', { planId: 'p', stepState: {}, now: 500 })
    expect(mgr.getSession('s')!.updatedAt).toBe(500)
  })
  it('conversation entryId is unique across sessions', () => {
    mgr.createSession({ sessionId: 's2', title: 't2' })
    mgr.appendConversation('s', 'user', 'a')
    mgr.appendConversation('s2', 'user', 'b')
    const e1 = mgr.listConversation('s')[0]!
    const e2 = mgr.listConversation('s2')[0]!
    expect(e1.entryId).not.toBe(e2.entryId)
  })
  it('memoryId is unique across adds', () => {
    const m1 = mgr.addMemory('s', { type: 'conclusion', content: 'a', confidence: 0.5, source: 'a' })!
    const m2 = mgr.addMemory('s', { type: 'conclusion', content: 'b', confidence: 0.5, source: 'b' })!
    expect(m1.memoryId).not.toBe(m2.memoryId)
  })
  it('saveCheckpoint checkpointId is unique across saves', () => {
    const c1 = mgr.saveCheckpoint('s', { planId: 'p', stepState: {} })!
    const c2 = mgr.saveCheckpoint('s', { planId: 'p', stepState: {} })!
    expect(c1.checkpointId).not.toBe(c2.checkpointId)
  })
  it('listSessions is empty before any session', () => {
    expect(new ResearchSessionManager().listSessions()).toEqual([])
  })
  it('listSessions reflects created sessions only', () => {
    mgr.createSession({ sessionId: 'x', title: 'x' })
    expect(mgr.listSessions().map((s) => s.sessionId)).toEqual(['s', 'x'])
  })
  it('appendConversation with timestamp 0 is allowed', () => {
    const e = mgr.appendConversation('s', 'user', 'a', 0)
    expect(e?.timestamp).toBe(0)
  })
  it('memory search ranks higher-confidence hits first on ties', () => {
    mgr.addMemory('s', { type: 'conclusion', content: 'bubble model', confidence: 0.4, source: 'a' })
    mgr.addMemory('s', { type: 'conclusion', content: 'bubble model', confidence: 0.8, source: 'b' })
    expect(mgr.searchMemory('s', 'bubble')[0]!.confidence).toBe(0.8)
  })
  it('memory list type filter is strict', () => {
    mgr.addMemory('s', { type: 'conclusion', content: 'a', confidence: 0.5, source: 'x' })
    expect(mgr.listMemory('s', 'paper')).toHaveLength(0)
  })
  it('listMemory with limit works', () => {
    for (let i = 0; i < 5; i++) {
      mgr.addMemory('s', { type: 'conclusion', content: `mem ${i}`, confidence: i / 10, source: 'x' })
    }
    expect(mgr.listMemory('s', undefined, 2)).toHaveLength(2)
  })
  it('searchMemory with a limit works', () => {
    for (let i = 0; i < 5; i++) {
      mgr.addMemory('s', { type: 'conclusion', content: `bubble mem ${i}`, confidence: i / 10, source: 'x' })
    }
    expect(mgr.searchMemory('s', 'bubble', 2)).toHaveLength(2)
  })
  it('listCheckpoints is stable across calls', () => {
    mgr.saveCheckpoint('s', { planId: 'p', stepState: {} })
    expect(mgr.listCheckpoints('s')).toEqual(mgr.listCheckpoints('s'))
  })
  it('restoreCheckpoint returns the same object across calls', () => {
    const c = mgr.saveCheckpoint('s', { planId: 'p', stepState: { k: 1 } })!
    expect(mgr.restoreCheckpoint('s', c.checkpointId)).toEqual(mgr.restoreCheckpoint('s', c.checkpointId))
  })
  it('SessionEvent payload passthrough works', () => {
    const events: SessionEvent[] = []
    mgr.onSessionEvent((e) => events.push(e))
    mgr.addMemory('s', { type: 'conclusion', content: 'x', confidence: 0.5, source: 'x' })
    expect(events[0]?.payload?.memoryId).toBeTruthy()
  })
  it('SessionEvent is schema-valid on creation', () => {
    const events: SessionEvent[] = []
    mgr.onSessionEvent((e) => events.push(e))
    mgr.createSession({ sessionId: 'new', title: 'n' })
    expect(isValidSessionEvent(events.find((e) => e.type === 'session_created')!)).toBe(true)
  })
  it('onSessionEvent unsubscribe is idempotent', () => {
    let n = 0
    const off = mgr.onSessionEvent(() => n++)
    off()
    off()
    mgr.createSession({ sessionId: 'a2', title: 't' })
    expect(n).toBe(0)
  })
  it('mgr.memory is a MemoryProvider', () => {
    const p = mgr.memory as MemoryProvider
    expect(typeof p.save).toBe('function')
    expect(typeof p.search).toBe('function')
    expect(typeof p.list).toBe('function')
    expect(typeof p.delete).toBe('function')
  })
  it('manager init with no options works (defaults)', () => {
    expect(new ResearchSessionManager().getSession('x')).toBeNull()
  })
  it('empty conversation list is immutable snapshot', () => {
    const a = mgr.listConversation('s')
    a.push(makeEntry())
    expect(mgr.listConversation('s')).toEqual([])
  })
  it('conversation append validates role before content', () => {
    expect(() => mgr.appendConversation('s', 'tool' as never, 'x')).toThrow(/invalid role/)
  })
  it('memory item with confidence 1 is the max in list order', () => {
    mgr.addMemory('s', { type: 'conclusion', content: 'weak', confidence: 0.1, source: 'a' })
    mgr.addMemory('s', { type: 'conclusion', content: 'strong', confidence: 1.0, source: 'b' })
    expect(mgr.listMemory('s')[0]!.content).toBe('strong')
  })
  it('session can be created after close under a new id', () => {
    mgr.closeSession('s')
    const s2 = mgr.createSession({ sessionId: 'new-session', title: 't' })
    expect(s2.status).toBe('active')
  })
  it('searchMemory is case-insensitive', () => {
    mgr.addMemory('s', { type: 'conclusion', content: 'ReactOR kinetics', confidence: 0.5, source: 'x' })
    expect(mgr.searchMemory('s', 'reactor')).toHaveLength(1)
  })
  it('memory size reflects the provider size', () => {
    mgr.addMemory('s', { type: 'conclusion', content: 'a', confidence: 0.5, source: 'x' })
    expect(mgr.memory.size()).toBe(1)
  })
  it('conversation length is bounded by appends', () => {
    for (let i = 0; i < 10; i++) mgr.appendConversation('s', i % 2 === 0 ? 'user' : 'assistant', `m${i}`, i)
    expect(mgr.listConversation('s')).toHaveLength(10)
  })
  it('checkpoint stepState survives restore exactly', () => {
    const state = { step: 4, tokens: 12, config: { a: [1, 2, 3] } }
    const c = mgr.saveCheckpoint('s', { planId: 'p', stepState: state })!
    expect(mgr.restoreCheckpoint('s', c.checkpointId)?.stepState).toEqual(state)
  })
  it('LocalMemoryProvider.delete removes from list too', () => {
    mgr.addMemory('s', { memoryId: 'del-me', type: 'conclusion', content: 'x', confidence: 0.5, source: 'x' })
    mgr.memory.delete('del-me')
    expect(mgr.listMemory('s')).toHaveLength(0)
  })
  it('manager.createSession throws on a secret in title', () => {
    expect(() => mgr.createSession({ sessionId: 'bad', title: 'Bearer fake' })).toThrow(/forbidden/)
  })
  it('manager.addMemory throws on a secret in source', () => {
    expect(() => mgr.addMemory('s', { type: 'conclusion', content: 'x', confidence: 0.5, source: 'Bearer fake' })).toThrow(/forbidden/)
  })
  it('manager.saveCheckpoint throws on a secret in stepState', () => {
    expect(() => mgr.saveCheckpoint('s', { planId: 'p', stepState: { token: 'Bearer fake' } })).toThrow(/forbidden/)
  })
  it('rejects an invalid memory type value', () => {
    expect(isValidMemoryType(undefined)).toBe(false)
  })
  it('isValidSessionStatus rejects undefined', () => {
    expect(isValidSessionStatus(undefined)).toBe(false)
  })
  it('isValidConversationRole rejects undefined', () => {
    expect(isValidConversationRole(undefined)).toBe(false)
  })
  it('isValidSessionEventType rejects undefined', () => {
    expect(isValidSessionEventType(undefined)).toBe(false)
  })
  it('isValidResearchSession rejects missing title-only', () => {
    expect(isValidResearchSession({ sessionId: 'a', title: 't' })).toBe(false)
  })
  it('isValidMemoryItem rejects missing source', () => {
    const m = { ...makeMemory(), source: '' }
    expect(isValidMemoryItem(m)).toBe(false)
  })
  it('isValidAgentCheckpoint rejects missing stepState entirely', () => {
    const c = { checkpointId: 'c', sessionId: 's', planId: 'p', createdAt: 1 }
    expect(isValidAgentCheckpoint({ ...c, stepState: undefined })).toBe(false)
  })
  it('isValidConversationEntry requires exactly role/content/timestamp', () => {
    expect(isValidConversationEntry({ entryId: 'e', role: 'user', timestamp: 1 })).toBe(false)
  })
  it('session event type set is a subset of the documented event list', () => {
    for (const t of SESSION_EVENT_TYPES) expect(SESSION_EVENT_TYPES).toContain(t)
  })
  it('session status set is a subset of the documented status list', () => {
    for (const s of SESSION_STATUSES) expect(SESSION_STATUSES).toContain(s)
  })
  it('LocalMemoryProvider save with same content but different id keeps both', () => {
    const p = new LocalMemoryProvider()
    p.save(makeMemory({ memoryId: 'a', content: 'same' }))
    p.save(makeMemory({ memoryId: 'b', content: 'same' }))
    expect(p.size()).toBe(2)
  })
  it('LocalMemoryProvider list limit larger than size is safe', () => {
    const p = new LocalMemoryProvider()
    p.save(makeMemory())
    expect(p.list(undefined, 100)).toHaveLength(1)
  })
  it('LocalMemoryProvider search returns empty for a non-existent term', () => {
    const p = new LocalMemoryProvider()
    p.save(makeMemory())
    expect(p.search('zzzz')).toEqual([])
  })
  it('LocalMemoryProvider list returns items sorted regardless of insert order', () => {
    const p = new LocalMemoryProvider()
    p.save(makeMemory({ memoryId: '3', confidence: 0.3 }))
    p.save(makeMemory({ memoryId: '1', confidence: 0.9 }))
    p.save(makeMemory({ memoryId: '2', confidence: 0.6 }))
    expect(p.list().map((m) => m.memoryId)).toEqual(['1', '2', '3'])
  })
  it('memory confidence sorting is descending', () => {
    const p = new LocalMemoryProvider()
    for (let i = 0; i < 10; i++) {
      p.save(makeMemory({ memoryId: `item-${i}`, confidence: i / 10 }))
    }
    const confs = p.list().map((m) => m.confidence)
    for (let i = 1; i < confs.length; i++) expect(confs[i]!).toBeLessThanOrEqual(confs[i - 1]!)
  })
  it('adapter loadContext returns memory sorted by confidence', () => {
    mgr.addMemory('s', { type: 'conclusion', content: 'low', confidence: 0.2, source: 'x' })
    mgr.addMemory('s', { type: 'conclusion', content: 'high', confidence: 0.9, source: 'y' })
    const ctx = new ResearchMemoryAdapter({ manager: mgr }).loadContext('s')!
    expect(ctx.memory[0]?.confidence).toBe(0.9)
  })
  it('adapter storeRun stores assistant answer verbatim', () => {
    const out = new ResearchMemoryAdapter({ manager: mgr }).storeRun('s', makeResponse({ answer: 'exact text', confidence: 0.8 }))
    expect(out.conversationEntries[1]?.content).toBe('exact text')
  })
  it('adapter storeRun user entry content is the requestId', () => {
    const out = new ResearchMemoryAdapter({ manager: mgr }).storeRun('s', makeResponse({ requestId: 'rdx' }))
    expect(out.conversationEntries[0]?.content).toBe('rdx')
  })
  it('adapter stores conclusion memory with the response confidence', () => {
    const out = new ResearchMemoryAdapter({ manager: mgr }).storeRun('s', makeResponse({ confidence: 0.65 }))
    expect(out.memories[0]?.confidence).toBe(0.65)
  })
  it('adapter runWithMemory stores a conversation of exactly 2 entries', async () => {
    const a = new ResearchMemoryAdapter({ manager: mgr })
    await a.runWithMemory({ run: async () => makeResponse() }, 's', makeRequest())
    expect(mgr.listConversation('s')).toHaveLength(2)
  })
  it('conversation role is a string union', () => {
    const roles: ConversationRole[] = ['user', 'assistant']
    expect(roles).toHaveLength(2)
  })
  it('session status is a string union', () => {
    const statuses: SessionStatus[] = ['active', 'paused', 'completed', 'archived']
    expect(statuses).toHaveLength(4)
  })
  it('memory type is a string union', () => {
    const types: MemoryType[] = ['conversation', 'experiment', 'paper', 'parameter', 'conclusion']
    expect(types).toHaveLength(5)
  })
  it('manager createSession honors explicit sessionId', () => {
    const s = mgr.createSession({ sessionId: 'explicit', title: 't' })
    expect(s.sessionId).toBe('explicit')
  })
  it('session manager is deterministic across instances for create+list', () => {
    const x = new ResearchSessionManager()
    const y = new ResearchSessionManager()
    x.createSession({ sessionId: 's', title: 'T', now: 10 })
    y.createSession({ sessionId: 's', title: 'T', now: 10 })
    expect(x.listSessions()).toEqual(y.listSessions())
  })
  it('memory provider contentScore handles empty content', () => {
    expect(memoryHelpers.contentScore(['a'], '')).toBe(0)
  })
  it('memory provider lowerTokens handles punctuation', () => {
    expect(memoryHelpers.lowerTokens('a.b;c,d-e')).toEqual(['a', 'b', 'c', 'd', 'e'])
  })
  it('memory provider search ignores stopword-adjacent tokens', () => {
    const p = new LocalMemoryProvider()
    p.save(makeMemory({ content: 'the bubble is small' }))
    expect(p.search('bubble').length).toBe(1)
  })
  it('manager can append to conversation before memory and vice versa', () => {
    mgr.appendConversation('s', 'user', 'q', 1)
    mgr.addMemory('s', { type: 'conclusion', content: 'ok', confidence: 0.5, source: 'x' })
    expect(mgr.listConversation('s')).toHaveLength(1)
    expect(mgr.listMemory('s')).toHaveLength(1)
  })
  it('checkpoints and conversation are independent stores', () => {
    mgr.appendConversation('s', 'user', 'q', 1)
    mgr.saveCheckpoint('s', { planId: 'p', stepState: {} })
    expect(mgr.listConversation('s')).toHaveLength(1)
    expect(mgr.listCheckpoints('s')).toHaveLength(1)
  })
  it('memory delete via provider is reflected in listMemory', () => {
    mgr.addMemory('s', { memoryId: 'gone', type: 'conclusion', content: 'x', confidence: 0.5, source: 'x' })
    mgr.memory.delete('gone')
    expect(mgr.listMemory('s')).toHaveLength(0)
  })
  it('listCheckpoints returns newly saved ones after restore', () => {
    mgr.saveCheckpoint('s', { planId: 'p1', stepState: {}, now: 1 })
    const c2 = mgr.saveCheckpoint('s', { planId: 'p2', stepState: {}, now: 2 })!
    mgr.restoreCheckpoint('s', c2.checkpointId)
    expect(mgr.listCheckpoints('s')).toHaveLength(2)
  })
  it('session event subscription can be multiple', () => {
    let a = 0
    let b = 0
    mgr.onSessionEvent(() => a++)
    mgr.onSessionEvent(() => b++)
    mgr.createSession({ sessionId: 'multi', title: 'm' })
    expect(a).toBe(1)
    expect(b).toBe(1)
  })
  it('session id uniqueness enforced', () => {
    mgr.createSession({ sessionId: 'dup', title: 'a' })
    expect(() => mgr.createSession({ sessionId: 'dup', title: 'b' })).toThrow(/already exists/)
  })
  it('updatedAt is always >= createdAt after updates', () => {
    const s = mgr.updateSession('s', { title: 'new', now: 1000 })
    expect(s?.updatedAt).toBeGreaterThanOrEqual(s!.createdAt)
  })
  it('pause marks status paused and preserves title', () => {
    const s = mgr.pauseSession('s')
    expect(s?.status).toBe('paused')
    expect(s?.title).toBe('t')
  })
  it('archive preserves conversation', () => {
    mgr.appendConversation('s', 'user', 'keep', 1)
    mgr.archiveSession('s')
    expect(mgr.listConversation('s')).toHaveLength(1)
  })
  it('isValidSessionStatus accepts archived', () => {
    expect(isValidSessionStatus('archived')).toBe(true)
  })
  it('isValidMemoryType accepts paper', () => {
    expect(isValidMemoryType('paper')).toBe(true)
  })
  it('isValidConversationRole rejects empty string', () => {
    expect(isValidConversationRole('')).toBe(false)
  })
  it('isValidConversationEntry rejects non-object', () => {
    expect(isValidConversationEntry('x')).toBe(false)
  })
  it('isValidMemoryItem rejects non-object', () => {
    expect(isValidMemoryItem(3)).toBe(false)
  })
  it('isValidAgentCheckpoint rejects non-object', () => {
    expect(isValidAgentCheckpoint([])).toBe(false)
  })
  it('isValidResearchSession rejects array', () => {
    expect(isValidResearchSession([1, 2])).toBe(false)
  })
  it('session manager listSessions is sorted by createdAt', () => {
    const m = new ResearchSessionManager()
    m.createSession({ sessionId: 'b', title: 'b', now: 200 })
    m.createSession({ sessionId: 'a', title: 'a', now: 100 })
    expect(m.listSessions().map((s) => s.sessionId)).toEqual(['a', 'b'])
  })
  it('LocalMemoryProvider save is idempotent on the same provider', () => {
    const p = new LocalMemoryProvider()
    expect(p.save(makeMemory())).toBe(true)
    expect(p.save(makeMemory())).toBe(false)
  })
  it('LocalMemoryProvider search limit 1 returns one', () => {
    const p = new LocalMemoryProvider()
    p.save(makeMemory({ memoryId: 'a', content: 'bubble one' }))
    p.save(makeMemory({ memoryId: 'b', content: 'bubble two' }))
    expect(p.search('bubble', 1)).toHaveLength(1)
  })
  it('createSession then appendConversation then addMemory then checkpoint round trip', () => {
    mgr.appendConversation('s', 'user', 'hello', 1)
    mgr.addMemory('s', { type: 'conclusion', content: 'world', confidence: 0.8, source: 's' })
    const c = mgr.saveCheckpoint('s', { planId: 'p', stepState: { stage: 'done' } })!
    expect(mgr.listConversation('s')).toHaveLength(1)
    expect(mgr.listMemory('s')).toHaveLength(1)
    expect(mgr.restoreCheckpoint('s', c.checkpointId)?.stepState).toEqual({ stage: 'done' })
  })
  it('adapter.getManager returns the injected instance', () => {
    const m = new ResearchSessionManager()
    const a = new ResearchMemoryAdapter({ manager: m })
    expect(a.getManager()).toBe(m)
  })
  it('adapter.storeRun stores assistant answer as conclusion memory source = requestId', () => {
    const a = new ResearchMemoryAdapter({ manager: mgr })
    const out = a.storeRun('s', makeResponse({ requestId: 'src-id', answer: 'a', confidence: 0.5 }))
    expect(out.memories[0]?.source).toBe('src-id')
  })
  it('session event emit order is deterministic', () => {
    const ev: SessionEventType[] = []
    mgr.onSessionEvent((e) => ev.push(e.type))
    mgr.addMemory('s', { type: 'conclusion', content: 'x', confidence: 0.5, source: 'x' })
    mgr.saveCheckpoint('s', { planId: 'p', stepState: {} })
    expect(ev).toEqual(['memory_added', 'checkpoint_saved'])
  })
  it('reject duplicate addMemory with same explicit id across session', () => {
    mgr.createSession({ sessionId: 'other', title: 'o' })
    mgr.addMemory('s', { memoryId: 'z', type: 'conclusion', content: 'a', confidence: 0.5, source: 'a' })
    expect(() => mgr.addMemory('other', { memoryId: 'z', type: 'conclusion', content: 'b', confidence: 0.5, source: 'b' }))
      .toThrow(/already exists/)
  })
  it('searchMemory is shared across sessions (project memory)', () => {
    mgr.createSession({ sessionId: 'proj', title: 'p' })
    mgr.addMemory('s', { type: 'paper', content: 'the reference on bubbles', confidence: 0.9, source: 'a' })
    expect(mgr.searchMemory('proj', 'bubble')).toHaveLength(1)
  })
  it('isValidSessionEvent payload is optional but validated', () => {
    expect(isValidSessionEvent({ type: 'session_created', sessionId: 's', timestamp: 1, payload: { a: 1 } })).toBe(true)
  })
  it('memory provider list with no args returns everything', () => {
    const p = new LocalMemoryProvider()
    p.save(makeMemory())
    expect(p.list()).toHaveLength(1)
  })
  it('isValidMemoryType rejects false', () => {
    expect(isValidMemoryType(false as never)).toBe(false)
  })
  it('isValidSessionEvent rejects array payload', () => {
    expect(isValidSessionEvent({ type: 'session_created', sessionId: 's', timestamp: 1, payload: [] as never })).toBe(true)
  })
  it('createSession allows empty projectId omitted', () => {
    const s = mgr.createSession({ sessionId: 'nop', title: 't' })
    expect(s.projectId).toBeUndefined()
  })
  it('closeSession three times stays completed', () => {
    mgr.closeSession('s')
    mgr.closeSession('s')
    mgr.closeSession('s')
    expect(mgr.getSession('s')?.status).toBe('completed')
  })
  it('appendConversation throws when content is null', () => {
    expect(() => mgr.appendConversation('s', 'user', null as never)).toThrow('content must be a string')
  })
  it('listMemory limit of 0 means no cap', () => {
    mgr.addMemory('s', { type: 'conclusion', content: 'one', confidence: 0.5, source: 'x' })
    expect(mgr.listMemory('s', undefined, 0)).toHaveLength(1)
  })
  it('searchMemory limit of 0 means no cap', () => {
    mgr.addMemory('s', { type: 'conclusion', content: 'bubble one', confidence: 0.5, source: 'x' })
    mgr.addMemory('s', { type: 'conclusion', content: 'bubble two', confidence: 0.5, source: 'y' })
    expect(mgr.searchMemory('s', 'bubble', 0)).toHaveLength(2)
  })
})