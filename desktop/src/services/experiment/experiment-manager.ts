// Experiment Manager — 科研实验生命周期管理器（确定性 + 防御性拷贝）。
import type {
  Experiment, ExperimentRecord, ExperimentResult,
  ExperimentStatus, ExperimentParameter
} from '../../shared/experiment/experiment-schema'

export class ExperimentManager {
  private experiments: Map<string, Experiment> = new Map()
  private nextId = 0

  createExperiment(input: {
    projectId: string
    title: string
    objective: string
    hypothesis?: string
    design?: string
  }): Experiment {
    this.nextId++
    const now = Date.now()
    const id = `exp-${this.nextId}-${now}`
    const exp: Experiment = {
      id,
      projectId: input.projectId,
      title: input.title,
      objective: input.objective,
      hypothesis: input.hypothesis ?? '',
      status: 'draft',
      design: input.design ?? '',
      records: [],
      datasets: [],
      results: [],
      createdAt: now,
      updatedAt: now
    }
    this.experiments.set(id, this.cloneExperiment(exp))
    return this.cloneExperiment(exp)
  }

  getExperiment(id: string): Experiment | null {
    const e = this.experiments.get(id)
    return e ? this.cloneExperiment(e) : null
  }

  updateExperiment(id: string, patch: Partial<{ title: string; objective: string; hypothesis: string; design: string }>): Experiment | null {
    const e = this.experiments.get(id)
    if (!e) return null
    const updated: Experiment = { ...e, ...patch, updatedAt: Date.now() }
    this.experiments.set(id, this.cloneExperiment(updated))
    return this.cloneExperiment(updated)
  }

  startExperiment(id: string): Experiment | null {
    return this.transitionStatus(id, 'running')
  }

  pauseExperiment(id: string): Experiment | null {
    return this.transitionStatus(id, 'paused')
  }

  completeExperiment(id: string): Experiment | null {
    return this.transitionStatus(id, 'completed')
  }

  failExperiment(id: string): Experiment | null {
    return this.transitionStatus(id, 'failed')
  }

  private transitionStatus(id: string, status: ExperimentStatus): Experiment | null {
    const e = this.experiments.get(id)
    if (!e) return null
    const updated: Experiment = { ...e, status, updatedAt: Date.now() }
    this.experiments.set(id, this.cloneExperiment(updated))
    return this.cloneExperiment(updated)
  }

  addRecord(experimentId: string, input: {
    operator: string
    parameters: ExperimentParameter[]
    observations: string
    notes?: string
  }): ExperimentRecord | null {
    const e = this.experiments.get(experimentId)
    if (!e) return null
    this.nextId++
    const id = `rec-${this.nextId}`
    const record: ExperimentRecord = {
      id, experimentId, timestamp: Date.now(),
      operator: input.operator,
      parameters: input.parameters.map((p) => ({ ...p })),
      observations: input.observations,
      notes: input.notes ?? ''
    }
    e.records.push(record)
    e.updatedAt = Date.now()
    this.experiments.set(experimentId, this.cloneExperiment(e))
    return this.cloneRecord(record)
  }

  attachDataset(experimentId: string, datasetId: string): Experiment | null {
    const e = this.experiments.get(experimentId)
    if (!e) return null
    if (!e.datasets.includes(datasetId)) e.datasets.push(datasetId)
    e.updatedAt = Date.now()
    this.experiments.set(experimentId, this.cloneExperiment(e))
    return this.cloneExperiment(e)
  }

  setResult(experimentId: string, result: ExperimentResult): Experiment | null {
    const e = this.experiments.get(experimentId)
    if (!e) return null
    e.results.push({ ...result })
    e.updatedAt = Date.now()
    this.experiments.set(experimentId, this.cloneExperiment(e))
    return this.cloneExperiment(e)
  }

  getExperimentProgress(experimentId: string): { total: number; completed: number; percent: number; status: ExperimentStatus } {
    const e = this.experiments.get(experimentId)
    if (!e) return { total: 0, completed: 0, percent: 0, status: 'draft' }
    const total = e.records.length
    const completed = e.results.length
    return {
      total,
      completed,
      percent: total > 0 ? Math.min(100, Math.round((completed / total) * 100)) : 0,
      status: e.status
    }
  }

  listExperiments(projectId?: string): Experiment[] {
    const result: Experiment[] = []
    const ids = Array.from(this.experiments.keys()).sort()
    for (const id of ids) {
      const e = this.experiments.get(id)!
      if (!projectId || e.projectId === projectId) {
        result.push(this.cloneExperiment(e))
      }
    }
    return result
  }

  size(): number { return this.experiments.size }
  clear(): void { this.experiments.clear(); this.nextId = 0 }
  snapshot(): Experiment[] { return this.listExperiments() }

  private cloneExperiment(e: Experiment): Experiment {
    return {
      id: e.id, projectId: e.projectId, title: e.title, objective: e.objective,
      hypothesis: e.hypothesis, status: e.status, design: e.design,
      records: e.records.map((r) => this.cloneRecord(r)),
      datasets: [...e.datasets],
      results: e.results.map((r) => ({ ...r, metrics: { ...r.metrics } })),
      createdAt: e.createdAt, updatedAt: e.updatedAt
    }
  }

  private cloneRecord(r: ExperimentRecord): ExperimentRecord {
    return {
      id: r.id, experimentId: r.experimentId, timestamp: r.timestamp,
      operator: r.operator,
      parameters: r.parameters.map((p) => ({ ...p })),
      observations: r.observations, notes: r.notes
    }
  }
}