// Experiment Monitor — 实时监控服务。

import type {
  ControlDashboard, DeviceStatusPanel, RealtimeMetric,
  ExperimentTimelineEntry
} from '../../shared/control/experiment-control-schema'

export interface ExperimentMonitorOptions {
  metricsRetention?: number
  timelineRetention?: number
}

export class ExperimentMonitor {
  private dashboards: Map<string, ControlDashboard> = new Map()
  private metrics: Map<string, RealtimeMetric[]> = new Map()
  private timeline: Map<string, ExperimentTimelineEntry[]> = new Map()
  private devicePanels: Map<string, DeviceStatusPanel> = new Map()
  private metricsRetention: number
  private timelineRetention: number

  constructor(options: ExperimentMonitorOptions = {}) {
    this.metricsRetention = options.metricsRetention ?? 200
    this.timelineRetention = options.timelineRetention ?? 100
  }

  createDashboard(input: { experimentId: string; title: string; deviceIds?: string[]; metrics?: string[] }): ControlDashboard {
    const now = Date.now()
    const id = `dash-${now}-${Math.floor(Math.random() * 1e6)}`
    const dash: ControlDashboard = {
      id,
      experimentId: input.experimentId,
      title: input.title,
      deviceIds: [...(input.deviceIds ?? [])],
      metrics: [...(input.metrics ?? [])],
      createdAt: now,
      updatedAt: now
    }
    this.dashboards.set(id, dash)
    return { ...dash, deviceIds: [...dash.deviceIds], metrics: [...dash.metrics] }
  }

  getDashboard(id: string): ControlDashboard | null {
    const d = this.dashboards.get(id)
    return d ? { ...d, deviceIds: [...d.deviceIds], metrics: [...d.metrics] } : null
  }

  subscribeExperiment(experimentId: string): ControlDashboard[] {
    const out: ControlDashboard[] = []
    for (const d of this.dashboards.values()) {
      if (d.experimentId === experimentId) out.push({ ...d, deviceIds: [...d.deviceIds], metrics: [...d.metrics] })
    }
    return out
  }

  pushMetric(metric: RealtimeMetric): void {
    let arr = this.metrics.get(metric.deviceId)
    if (!arr) {
      arr = []
      this.metrics.set(metric.deviceId, arr)
    }
    arr.push(metric)
    if (arr.length > this.metricsRetention) arr.splice(0, arr.length - this.metricsRetention)
  }

  getRealtimeMetrics(deviceId: string, metricName?: string): RealtimeMetric[] {
    const arr = this.metrics.get(deviceId) ?? []
    return metricName ? arr.filter((m) => m.metric === metricName) : [...arr]
  }

  latestMetric(deviceId: string, metricName: string): RealtimeMetric | null {
    const arr = this.metrics.get(deviceId) ?? []
    for (let i = arr.length - 1; i >= 0; i--) {
      if (arr[i].metric === metricName) return arr[i]
    }
    return null
  }

  registerDevicePanel(panel: DeviceStatusPanel): void {
    this.devicePanels.set(panel.deviceId, { ...panel })
  }

  updateDeviceStatus(deviceId: string, status: string, lastSeen: number, recentReadings: number): DeviceStatusPanel | null {
    const p = this.devicePanels.get(deviceId)
    if (!p) return null
    p.status = status
    p.lastSeen = lastSeen
    p.recentReadings = recentReadings
    return { ...p }
  }

  getDeviceStatus(deviceId: string): DeviceStatusPanel | null {
    const p = this.devicePanels.get(deviceId)
    return p ? { ...p } : null
  }

  listDeviceStatuses(): DeviceStatusPanel[] {
    const out: DeviceStatusPanel[] = []
    for (const p of this.devicePanels.values()) out.push({ ...p })
    return out
  }

  appendTimeline(entry: ExperimentTimelineEntry): void {
    let arr = this.timeline.get(entry.experimentId)
    if (!arr) {
      arr = []
      this.timeline.set(entry.experimentId, arr)
    }
    arr.push(entry)
    if (arr.length > this.timelineRetention) arr.splice(0, arr.length - this.timelineRetention)
  }

  getTimeline(experimentId: string): ExperimentTimelineEntry[] {
    return [...(this.timeline.get(experimentId) ?? [])]
  }

  size(): number {
    return this.dashboards.size + this.metrics.size + this.timeline.size + this.devicePanels.size
  }

  clear(): void {
    this.dashboards.clear()
    this.metrics.clear()
    this.timeline.clear()
    this.devicePanels.clear()
  }
}