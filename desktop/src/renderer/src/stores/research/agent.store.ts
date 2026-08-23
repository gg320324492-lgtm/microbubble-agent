// Agent Store — AI 智能体执行状态管理。
import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { researchAgentService, type AgentMessage, type AgentEvent, type ResearchSession, type CitationItem, type EvidenceItem } from '../../services/research/research-agent.service'

export const useAgentStore = defineStore('research-agent', () => {
  const sessions = ref<ResearchSession[]>([])
  const activeSessionId = ref<string | null>(null)
  const messages = ref<AgentMessage[]>([])
  const events = ref<AgentEvent[]>([])
  const citations = ref<CitationItem[]>([])
  const evidence = ref<EvidenceItem[]>([])
  const isLoading = ref(false)
  const isSending = ref(false)

  const activeSession = computed(() => sessions.value.find(s => s.id === activeSessionId.value))

  async function loadSessions() {
    isLoading.value = true
    try { sessions.value = await researchAgentService.getSessions() }
    finally { isLoading.value = false }
  }

  async function selectSession(id: string) {
    activeSessionId.value = id
    isLoading.value = true
    try {
      const session = await researchAgentService.getSession(id)
      messages.value = session?.messages ?? []
      events.value = await researchAgentService.getEvents(id)
      citations.value = await researchAgentService.getCitations(id)
      evidence.value = await researchAgentService.getEvidence(id)
    } finally { isLoading.value = false }
  }

  async function sendMessage(content: string) {
    if (!activeSessionId.value || isSending.value) return
    isSending.value = true
    try {
      const msg = await researchAgentService.sendMessage(activeSessionId.value, content)
      messages.value = [...messages.value, msg]
    } finally { isSending.value = false }
  }

  return { sessions, activeSessionId, activeSession, messages, events, citations, evidence, isLoading, isSending, loadSessions, selectSession, sendMessage }
})
