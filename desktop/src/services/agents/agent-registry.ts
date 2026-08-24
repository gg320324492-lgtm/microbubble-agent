// Agent Capability Registry — 智能体注册中心（确定性排序 + 防御性拷贝）。
import type { ScientificAgentProfile, AgentRole } from '../../shared/agents/agent-schema'

export class AgentRegistry {
  private agents: Map<string, ScientificAgentProfile> = new Map()

  registerAgent(profile: ScientificAgentProfile): boolean {
    if (this.agents.has(profile.id)) return false
    this.agents.set(profile.id, this.clone(profile))
    return true
  }

  removeAgent(id: string): boolean {
    if (!this.agents.has(id)) return false
    this.agents.delete(id)
    return true
  }

  getAgent(id: string): ScientificAgentProfile | null {
    const a = this.agents.get(id)
    return a ? this.clone(a) : null
  }

  findAgentsByCapability(capability: string): ScientificAgentProfile[] {
    const result: ScientificAgentProfile[] = []
    const ids = Array.from(this.agents.keys()).sort()
    for (const id of ids) {
      const a = this.agents.get(id)!
      if (a.capabilities.includes(capability)) result.push(this.clone(a))
    }
    return result
  }

  findAgentsByRole(role: AgentRole): ScientificAgentProfile[] {
    const result: ScientificAgentProfile[] = []
    const ids = Array.from(this.agents.keys()).sort()
    for (const id of ids) {
      const a = this.agents.get(id)!
      if (a.role === role) result.push(this.clone(a))
    }
    return result
  }

  findAgentsByDomain(domain: string): ScientificAgentProfile[] {
    const result: ScientificAgentProfile[] = []
    const ids = Array.from(this.agents.keys()).sort()
    for (const id of ids) {
      const a = this.agents.get(id)!
      if (a.knowledgeDomains.includes(domain)) result.push(this.clone(a))
    }
    return result
  }

  listAgents(): ScientificAgentProfile[] {
    const result: ScientificAgentProfile[] = []
    const ids = Array.from(this.agents.keys()).sort()
    for (const id of ids) result.push(this.clone(this.agents.get(id)!))
    return result
  }

  size(): number { return this.agents.size }

  clear(): void { this.agents.clear() }

  snapshot(): ScientificAgentProfile[] { return this.listAgents() }

  private clone(p: ScientificAgentProfile): ScientificAgentProfile {
    return {
      id: p.id, name: p.name, role: p.role, description: p.description,
      capabilities: [...p.capabilities], tools: [...p.tools],
      knowledgeDomains: [...p.knowledgeDomains], priority: p.priority
    }
  }
}
