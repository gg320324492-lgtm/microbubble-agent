// Agent Service — Phase 8-M1-E
// 统一入口: 持有 ScientificTools + AgentMemory 单例, 提供 chat/list/history 顶层 API.

import type { DatabaseService } from '../database.service'
import { createAgentTools, TOOL_METADATA } from './agent-tools'
import { createAgentMemory, type AgentMemory, type ChatMessage } from './agent-memory'
import type { ScientificToolMetadata, ScientificToolRegistry } from './agent-schemas'

export interface AgentService {
  tools: ScientificToolRegistry
  memory: AgentMemory
  listTools(): ScientificToolMetadata[]
  invokeTool(name: string, params: Record<string, unknown>): Promise<unknown>
  recordMessage(sessionId: string, role: ChatMessage['role'], content: string, toolName?: string, toolResult?: string): void
  getHistory(sessionId: string, limit?: number): ChatMessage[]
  searchMemory(query: string, limit?: number): ChatMessage[]
  clearMemory(sessionId: string): number
}

class AgentServiceImpl implements AgentService {
  readonly tools: ScientificToolRegistry
  readonly memory: AgentMemory

  constructor(getService: () => DatabaseService | null) {
    this.tools = createAgentTools(getService)
    this.memory = createAgentMemory(getService)
  }

  listTools(): ScientificToolMetadata[] { return this.tools.list() }
  invokeTool(name: string, params: Record<string, unknown>): Promise<unknown> { return this.tools.invoke(name, params) }
  recordMessage(sessionId: string, role: ChatMessage['role'], content: string, toolName?: string, toolResult?: string): void {
    this.memory.recordMessage(sessionId, role, content, toolName, toolResult)
  }
  getHistory(sessionId: string, limit?: number): ChatMessage[] { return this.memory.history(sessionId, limit) }
  searchMemory(query: string, limit?: number): ChatMessage[] { return this.memory.search(query, limit) }
  clearMemory(sessionId: string): number { return this.memory.clear(sessionId) }
}

let serviceInstance: AgentService | null = null

export function bootstrapAgentService(getService: () => DatabaseService | null): AgentService {
  if (serviceInstance) return serviceInstance
  serviceInstance = new AgentServiceImpl(getService)
  return serviceInstance
}

export function getAgentService(): AgentService | null {
  return serviceInstance
}

export { TOOL_METADATA }