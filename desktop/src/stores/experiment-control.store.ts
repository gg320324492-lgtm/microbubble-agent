// Experiment Control Store — Pinia store for control center.

import { defineStore } from 'pinia'
import type {
  ControlDashboard, DeviceStatusPanel, RealtimeMetric,
  ExperimentTimelineEntry, AIRecommendation, ControlAction
} from '../shared/control/experiment-control-schema'
import type { TwinPrediction } from '../shared/digital-twin/digital-twin-schema'

export const useExperimentControlStore = defineStore('experiment-control', {
  state: () => ({
    devices: [] as DeviceStatusPanel[],
    metrics: [] as RealtimeMetric[],
    timeline: [] as ExperimentTimelineEntry[],
    recommendations: [] as AIRecommendation[],
    alerts: [] as { id: string; severity: 'info' | 'warning' | 'critical'; message: string; timestamp: number }[],
    dashboards: [] as ControlDashboard[],
    actions: [] as ControlAction[],
    predictions: [] as TwinPrediction[]
  }),

  getters: {
    deviceCount: (state) => state.devices.length,
    metricCount: (state) => state.metrics.length,
    recommendationCount: (state) => state.recommendations.length,
    alertCount: (state) => state.alerts.length,
    onlineDeviceCount: (state) => state.devices.filter((d) => d.status === 'online').length,
    offlineDeviceCount: (state) => state.devices.filter((d) => d.status === 'offline').length,
    criticalAlertCount: (state) => state.alerts.filter((a) => a.severity === 'critical').length
  },

  actions: {
    setDevices(devices: DeviceStatusPanel[]) { this.devices = devices },
    addDevice(d: DeviceStatusPanel) { this.devices.push(d) },
    updateDeviceStatus(deviceId: string, status: string, lastSeen: number, recentReadings: number) {
      const d = this.devices.find((x) => x.deviceId === deviceId)
      if (d) {
        d.status = status
        d.lastSeen = lastSeen
        d.recentReadings = recentReadings
      }
    },

    pushMetric(m: RealtimeMetric) { this.metrics.push(m) },
    setMetrics(metrics: RealtimeMetric[]) { this.metrics = metrics },
    latestMetric(metricName: string): RealtimeMetric | null {
      for (let i = this.metrics.length - 1; i >= 0; i--) {
        if (this.metrics[i].metric === metricName) return this.metrics[i]
      }
      return null
    },
    clearMetrics() { this.metrics = [] },

    appendTimeline(entry: ExperimentTimelineEntry) { this.timeline.push(entry) },
    setTimeline(entries: ExperimentTimelineEntry[]) { this.timeline = entries },

    setRecommendations(recs: AIRecommendation[]) { this.recommendations = recs },
    addRecommendation(r: AIRecommendation) { this.recommendations.push(r) },

    pushAlert(severity: 'info' | 'warning' | 'critical', message: string) {
      this.alerts.push({
        id: `alert-${Date.now()}-${Math.floor(Math.random() * 1e6)}`,
        severity,
        message,
        timestamp: Date.now()
      })
    },
    clearAlerts() { this.alerts = [] },

    addDashboard(d: ControlDashboard) { this.dashboards.push(d) },
    setDashboards(dashboards: ControlDashboard[]) { this.dashboards = dashboards },

    recordAction(a: ControlAction) { this.actions.push(a) },
    actionCount(): number { return this.actions.length },

    setPredictions(predictions: TwinPrediction[]) { this.predictions = [...predictions] },
    addPrediction(prediction: TwinPrediction) { this.predictions.push(prediction) },

    reset() {
      this.devices = []
      this.metrics = []
      this.timeline = []
      this.recommendations = []
      this.alerts = []
      this.dashboards = []
      this.actions = []
      this.predictions = []
    }
  }
})

export const __testHelpers = {}
