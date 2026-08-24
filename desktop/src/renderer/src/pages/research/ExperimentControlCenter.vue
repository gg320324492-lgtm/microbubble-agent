<script setup lang="ts">
import { computed, onMounted } from 'vue'
import { useExperimentControlStore } from '../../../../stores/experiment-control.store'
import DeviceCard from '../../components/control/DeviceCard.vue'
import RealtimeChart from '../../components/control/RealtimeChart.vue'
import ExperimentTimeline from '../../components/control/ExperimentTimeline.vue'
import PredictionPanel from '../../components/control/PredictionPanel.vue'
import AIAdviceCard from '../../components/control/AIAdviceCard.vue'

const store = useExperimentControlStore()

const metricsList = computed(() => {
  const seen = new Set<string>()
  const out: string[] = []
  for (const m of store.metrics) {
    if (!seen.has(m.metric)) { seen.add(m.metric); out.push(m.metric) }
  }
  return out
})

onMounted(() => {
  if (store.devices.length === 0) {
    store.pushAlert('info', '控制中心已就绪')
  }
})
</script>

<template>
  <div class="control-center">
    <header class="control-center__header">
      <h1 class="control-center__title">实验控制中心</h1>
      <p class="control-center__subtitle">统一管理设备、监控实验、获取 AI 推荐</p>
    </header>

    <section class="control-center__section">
      <h2 class="control-center__section-title">设备仪表盘</h2>
      <div class="control-center__grid control-center__grid--devices">
        <DeviceCard v-for="d in store.devices" :key="d.deviceId" :panel="d" />
      </div>
    </section>

    <section class="control-center__section">
      <h2 class="control-center__section-title">实时图表</h2>
      <div class="control-center__grid control-center__grid--charts">
        <RealtimeChart v-for="name in metricsList" :key="name" :metric-name="name" :metrics="store.metrics" />
      </div>
    </section>

    <section class="control-center__columns">
      <div class="control-center__col">
        <h2 class="control-center__section-title">实验时间线</h2>
        <ExperimentTimeline :entries="store.timeline" />
      </div>
      <div class="control-center__col">
        <h2 class="control-center__section-title">数字孪生预测</h2>
        <PredictionPanel :predictions="[]" />
      </div>
      <div class="control-center__col">
        <h2 class="control-center__section-title">AI 推荐</h2>
        <AIAdviceCard :recommendations="store.recommendations" />
      </div>
    </section>
  </div>
</template>

<style scoped>
.control-center {
  padding: 32px;
  max-width: 1400px;
  margin: 0 auto;
}
.control-center__header {
  margin-bottom: 32px;
}
.control-center__title {
  font-size: 28px;
  font-weight: 700;
  color: #1e293b;
  margin: 0 0 4px;
}
.control-center__subtitle {
  font-size: 14px;
  color: #64748b;
  margin: 0;
}
.control-center__section {
  margin-bottom: 24px;
}
.control-center__section-title {
  font-size: 16px;
  font-weight: 600;
  color: #1e293b;
  margin: 0 0 12px;
}
.control-center__grid {
  display: grid;
  gap: 16px;
}
.control-center__grid--devices {
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
}
.control-center__grid--charts {
  grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
}
.control-center__columns {
  display: grid;
  grid-template-columns: 1fr 1fr 1fr;
  gap: 16px;
}
@media (max-width: 1024px) {
  .control-center__columns {
    grid-template-columns: 1fr;
  }
}
</style>