<script setup lang="ts">
import { computed } from 'vue'
import { useExperimentControlStore } from '../../../../stores/experiment-control.store'
import ResearchPageHeader from '../../components/research/ResearchPageHeader.vue'
import ResearchPanel from '../../components/research/ResearchPanel.vue'
import ResearchMetricPanel from '../../components/research/ResearchMetricPanel.vue'
import ResearchTimeline from '../../components/research/ResearchTimeline.vue'
import SCADADeviceTopology from '../../components/research/SCADADeviceTopology.vue'
import SCADAMetricGrid from '../../components/research/SCADAMetricGrid.vue'
import SCADAAlertPanel from '../../components/research/SCADAAlertPanel.vue'
import PredictionPanel from '../../components/research/PredictionPanel.vue'
import DeviceStatusPanel from '../../components/research/DeviceStatusPanel.vue'
import AIAdviceCard from '../../components/control/AIAdviceCard.vue'

const store = useExperimentControlStore()

const runStatus = computed(() => {
  const entries = [...store.timeline].sort((left, right) => right.timestamp - left.timestamp)
  return entries[0]?.event ?? '暂无 Run 记录'
})

const experimentStatus = computed(() => {
  if (store.dashboards.length > 0) {
    return store.dashboards.at(-1)!.title
  }
  const entries = [...store.timeline].sort((left, right) => right.timestamp - left.timestamp)
  return entries[0]?.description ?? '暂无实验状态'
})

const statusItems = computed(() => [
  { label: '设备在线', value: `${store.onlineDeviceCount} / ${store.deviceCount}` },
  { label: '实时指标', value: String(store.metricCount) },
  { label: '报警', value: String(store.alertCount), status: store.criticalAlertCount ? 'error' : undefined },
  { label: '预测记录', value: String(store.predictions.length) }
])
</script>

<template>
  <main
    class="experiment-control-center"
    data-research-theme="scada"
    aria-label="实验控制中心 SCADA"
  >
    <ResearchPageHeader title="实验控制中心" subtitle="数字孪生优先的 SCADA 视图" />

    <section class="experiment-control-center__status" aria-label="实验状态与 Run 状态">
      <div class="experiment-control-center__status-grid">
        <ResearchPanel title="实验状态">
          <p class="experiment-control-center__status-label">实验状态</p>
          <p v-if="store.dashboards.length === 0 && store.timeline.length === 0" class="experiment-control-center__status-empty" role="status">暂无实验状态</p>
          <p v-else class="experiment-control-center__status-value">{{ experimentStatus }}</p>
        </ResearchPanel>
        <ResearchPanel title="Run 状态">
          <p class="experiment-control-center__status-label">Run 状态</p>
          <p v-if="store.timeline.length === 0" class="experiment-control-center__status-empty" role="status">暂无 Run 记录</p>
          <p v-else class="experiment-control-center__status-value">{{ runStatus }}</p>
        </ResearchPanel>
        <ResearchPanel title="实时指标总览">
          <ResearchMetricPanel :metrics="statusItems" title="SCADA 指标" />
        </ResearchPanel>
      </div>
    </section>

    <section class="experiment-control-center__twin" aria-label="数字孪生拓扑">
      <h2 class="experiment-control-center__section-title">数字孪生拓扑</h2>
      <div class="experiment-control-center__twin-grid">
        <SCADADeviceTopology :devices="store.devices" aria-label="数字孪生设备拓扑" />
        <PredictionPanel :predictions="store.predictions" variant="scada" />
      </div>
      <p v-if="store.predictions.length === 0" class="experiment-control-center__empty" role="status">
        暂无数字孪生预测
      </p>
    </section>

    <section class="experiment-control-center__observability" aria-label="可观测性">
      <h2 class="experiment-control-center__section-title">可观测性</h2>
      <div class="experiment-control-center__observability-grid">
        <ResearchPanel title="设备状态">
          <DeviceStatusPanel v-if="store.devices.length > 0" :devices="store.devices" variant="research" />
          <p v-else class="experiment-control-center__empty" role="status">暂无设备接入数据</p>
        </ResearchPanel>

        <ResearchPanel title="实时指标">
          <SCADAMetricGrid :metrics="store.metrics" aria-label="实时指标网格" />
          <p v-if="store.metrics.length === 0" class="experiment-control-center__empty" role="status">
            暂无实时指标
          </p>
        </ResearchPanel>

        <SCADAAlertPanel :alerts="store.alerts" aria-label="报警面板" />
        <p v-if="store.alerts.length === 0" class="experiment-control-center__empty" role="status">
          暂无报警
        </p>

        <ResearchPanel title="AI 建议">
          <AIAdviceCard :recommendations="store.recommendations" />
          <p v-if="store.recommendations.length === 0" class="experiment-control-center__empty" role="status">
            暂无 AI 建议
          </p>
        </ResearchPanel>

        <ResearchPanel title="实验时间线">
          <ResearchTimeline
            v-if="store.timeline.length > 0"
            :entries="store.timeline"
            title="实验时间线"
          />
          <p v-else class="experiment-control-center__empty" role="status">暂无时间线</p>
        </ResearchPanel>
      </div>
    </section>
  </main>
</template>

<style scoped>
.experiment-control-center {
  min-width: 0;
  min-height: 100%;
  padding: var(--research-page-gutter);
  overflow-x: clip;
  background: var(--research-bg-main, #f8fafc);
}
[data-research-theme='scada'] .experiment-control-center {
  background: var(--research-bg-scada-deep, #0a1118);
  color: var(--research-scada-text, #d6e4ee);
}
.experiment-control-center:focus-visible {
  outline: none;
}
.experiment-control-center__section-title {
  font-size: 14px;
  font-weight: 600;
  color: var(--research-scada-text, #d6e4ee);
  margin: 0 0 12px;
}
.experiment-control-center__status {
  margin-bottom: 24px;
  min-width: 0;
}
.experiment-control-center__status-grid {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(0, 1fr) minmax(0, 1.4fr);
  gap: var(--research-grid-gap);
}
.experiment-control-center__status-label {
  font-size: 12px;
  color: var(--research-scada-muted, #94a3b8);
  margin: 0 0 4px;
}
.experiment-control-center__status-value {
  font-size: 14px;
  font-weight: 600;
  color: var(--research-scada-text, #d6e4ee);
  margin: 0;
}
.experiment-control-center__status-empty {
  font-size: 13px;
  color: var(--research-scada-muted, #94a3b8);
  margin: 0;
}
.experiment-control-center__twin {
  margin-bottom: 24px;
  min-width: 0;
}
.experiment-control-center__twin-grid {
  display: grid;
  grid-template-columns: minmax(0, 1.35fr) minmax(300px, 0.65fr);
  gap: var(--research-grid-gap);
}
.experiment-control-center__observability {
  margin-bottom: 24px;
  min-width: 0;
}
.experiment-control-center__observability-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: var(--research-grid-gap);
}
.experiment-control-center__devices {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(min(100%, 220px), 1fr));
  gap: 12px;
}
.experiment-control-center__empty {
  font-size: 13px;
  color: var(--research-scada-muted, #94a3b8);
  margin: 8px 0 0;
}
@media (max-width: 1480px) {
  .experiment-control-center__twin-grid,
  .experiment-control-center__observability-grid,
  .experiment-control-center__status-grid {
    grid-template-columns: minmax(0, 1fr);
  }
}
@media (min-width: 1720px) {
  .experiment-control-center__twin-grid {
    grid-template-columns: minmax(0, 1.35fr) minmax(300px, 0.65fr);
  }
  .experiment-control-center__observability-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
  .experiment-control-center__status-grid {
    grid-template-columns: minmax(0, 1fr) minmax(0, 1fr) minmax(0, 1.4fr);
  }
}
@media (prefers-reduced-motion: reduce) {
  .experiment-control-center *,
  .experiment-control-center *::before,
  .experiment-control-center *::after {
    animation: none !important;
    transition: none !important;
  }
}
</style>