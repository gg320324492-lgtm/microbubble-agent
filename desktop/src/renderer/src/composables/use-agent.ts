// useAgent Composable — Phase 8-M1-E
// 渲染端 agent 桥接, 桥接 ScientificTools + AgentMemory. 不含 LLM 调用 (Phase 8-M1-F 接入).

import { ref, computed } from 'vue'
import type { Ref } from 'vue'

export type AgentRole = 'user' | 'assistant' | 'tool'

export interface AgentMessage {
  id: number
  agent: string
  role: AgentRole
  content: string
  timestamp: number
  toolName?: string
  toolResult?: string
}

export interface ScientificToolMeta {
  name: string
  description: string
  parametersJson: string
}

interface AgentApi {
  listTools?: () => Promise<ScientificToolMeta[]>
  invokeTool?: (name: string, params: Record<string, unknown>) => Promise<unknown>
  sendMessage?: (sessionId: string, role: AgentRole, content: string, toolName?: string, toolResult?: string) => Promise<{ ok: boolean }>
  getHistory?: (sessionId: string, limit?: number) => Promise<AgentMessage[]>
  searchMemory?: (query: string, limit?: number) => Promise<AgentMessage[]>
  clearMemory?: (sessionId: string) => Promise<number>
}

function getAgentApi(): AgentApi | null {
  if (typeof window === 'undefined') return null
  return (window as unknown as { api?: { agent?: AgentApi } }).api?.agent ?? null
}

export interface AgentBus {
  history: Ref<AgentMessage[]>
  tools: Ref<ScientificToolMeta[]>
  isLoading: Ref<boolean>
  errorMessage: Ref<string>
  hasHistory: Ref<boolean>
  loadTools(): Promise<void>
  loadHistory(sessionId: string, limit?: number): Promise<void>
  recordMessage(sessionId: string, role: AgentRole, content: string, toolName?: string, toolResult?: string): Promise<void>
  invokeTool(name: string, params: Record<string, unknown>): Promise<unknown | null>
  searchMemory(query: string, limit?: number): Promise<AgentMessage[]>
  clearMemory(sessionId: string): Promise<number>
  reset(): void
}

export function useAgent(): AgentBus {
  const history = ref<AgentMessage[]>([])
  const tools = ref<ScientificToolMeta[]>([])
  const isLoading = ref(false)
  const errorMessage = ref('')

  async function loadTools(): Promise<void> {
    const api = getAgentApi()
    if (!api?.listTools) { tools.value = []; return }
    isLoading.value = true; errorMessage.value = ''
    try {
      tools.value = await api.listTools()
    } catch (err) {
      errorMessage.value = err instanceof Error ? err.message : '加载工具失败'
    } finally {
      isLoading.value = false
    }
  }

  async function loadHistory(sessionId: string, limit?: number): Promise<void> {
    const api = getAgentApi()
    if (!api?.getHistory) { history.value = []; return }
    isLoading.value = true; errorMessage.value = ''
    try {
      history.value = await api.getHistory(sessionId, limit)
    } catch (err) {
      errorMessage.value = err instanceof Error ? err.message : '加载历史失败'
    } finally {
      isLoading.value = false
    }
  }

  async function recordMessage(sessionId: string, role: AgentRole, content: string, toolName?: string, toolResult?: string): Promise<void> {
    const api = getAgentApi()
    if (!api?.sendMessage) return
    try {
      await api.sendMessage(sessionId, role, content, toolName, toolResult)
    } catch (err) {
      errorMessage.value = err instanceof Error ? err.message : '记录消息失败'
    }
  }

  async function invokeTool(name: string, params: Record<string, unknown>): Promise<unknown | null> {
    const api = getAgentApi()
    if (!api?.invokeTool) return null
    isLoading.value = true; errorMessage.value = ''
    try {
      return await api.invokeTool(name, params)
    } catch (err) {
      errorMessage.value = err instanceof Error ? err.message : '调用工具失败'
      return null
    } finally {
      isLoading.value = false
    }
  }

  async function searchMemory(query: string, limit?: number): Promise<AgentMessage[]> {
    const api = getAgentApi()
    if (!api?.searchMemory) return []
    try {
      return await api.searchMemory(query, limit)
    } catch (err) {
      errorMessage.value = err instanceof Error ? err.message : '搜索失败'
      return []
    }
  }

  async function clearMemory(sessionId: string): Promise<number> {
    const api = getAgentApi()
    if (!api?.clearMemory) return 0
    try {
      const n = await api.clearMemory(sessionId)
      history.value = []
      return n
    } catch (err) {
      errorMessage.value = err instanceof Error ? err.message : '清空失败'
      return 0
    }
  }

  function reset(): void {
    history.value = []
    errorMessage.value = ''
  }

  return {
    history, tools, isLoading, errorMessage,
    hasHistory: computed(() => history.value.length > 0),
    loadTools, loadHistory, recordMessage, invokeTool, searchMemory, clearMemory, reset
  }
}