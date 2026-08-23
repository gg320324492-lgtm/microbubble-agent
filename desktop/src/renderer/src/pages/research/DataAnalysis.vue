<script setup lang="ts">
/**
 * 数据分析 — Pinia store 驱动。
 */
import { onMounted } from 'vue'
import { useDatasetStore } from '../../stores/research/dataset.store'
import ChartPanel from '../../components/research/ChartPanel.vue'
import StatusBadge from '../../components/research/StatusBadge.vue'

const store = useDatasetStore()
onMounted(() => store.loadReport())
</script>

<template>
  <div class="analysis">
    <div class="analysis__header">
      <h1 class="analysis__title">数据分析</h1>
      <StatusBadge v-if="store.report" status="success" label="分析完成" />
      <StatusBadge v-else-if="store.isLoading" status="info" label="加载中" />
    </div>

    <template v-if="store.report">
      <div class="analysis__top">
        <div class="analysis__card">
          <h3>数据质量</h3>
          <div class="analysis__q-row"><span>完整度</span><div class="analysis__bar"><div class="analysis__bar-fill green" :style="{ width: (store.quality?.completeness ?? 0) * 100 + '%' }" /></div><span>{{ ((store.quality?.completeness ?? 0) * 100).toFixed(0) }}%</span></div>
          <div class="analysis__q-row"><span>缺失值</span><span>0</span></div>
          <div class="analysis__q-row"><span>警告</span><span>{{ store.quality?.warnings?.length ?? 0 }}</span></div>
        </div>
        <div class="analysis__card">
          <h3>统计分析</h3>
          <div class="analysis__stat" v-for="s in store.statistics" :key="s.metric">
            <div class="analysis__stat-name">{{ s.metric }}</div>
            <div class="analysis__stat-value">{{ s.value }}</div>
            <div class="analysis__stat-interp">{{ s.interpretation }}</div>
          </div>
        </div>
        <div class="analysis__card">
          <h3>模型拟合 <StatusBadge status="success" label="拟合良好" /></h3>
          <div v-if="store.models[0]" class="analysis__fit">
            <div class="analysis__fit-row"><span>模型</span><span class="mono">{{ store.models[0].model }}</span></div>
            <div class="analysis__fit-row"><span>R²</span><span class="mono">{{ store.models[0].rSquared }}</span></div>
            <div class="analysis__fit-row"><span>残差</span><span class="mono">{{ store.models[0].residualError }}</span></div>
          </div>
        </div>
      </div>

      <div class="analysis__card" style="margin-bottom: 20px;">
        <h3>🔬 科学解读</h3>
        <div class="analysis__conclusion" v-for="c in store.conclusions" :key="c.observation">
          <div class="analysis__conc-obs">{{ c.observation }}</div>
          <div class="analysis__conc-interp">{{ c.interpretation }}</div>
          <div class="analysis__conc-conf">置信度 {{ (c.confidence * 100).toFixed(0) }}%</div>
        </div>
      </div>
    </template>
  </div>
</template>

<style scoped>
.analysis { padding: 24px 28px; max-width: 1200px; }
.analysis__header { display: flex; align-items: center; gap: 12px; margin-bottom: 20px; }
.analysis__title { margin: 0; font-size: 20px; font-weight: 700; color: #0f172a; }
.analysis__top { display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 14px; margin-bottom: 16px; }
.analysis__card { background: #fff; border: 1px solid #e5e7eb; border-radius: 12px; padding: 16px; }
.analysis__card h3 { margin: 0 0 10px; font-size: 13px; font-weight: 600; color: #0f172a; display: flex; align-items: center; gap: 8px; }
.analysis__q-row { display: flex; justify-content: space-between; font-size: 13px; margin-bottom: 6px; color: #475569; }
.analysis__bar { flex: 1; height: 6px; background: #f1f5f9; border-radius: 3px; margin: 0 8px; }
.analysis__bar-fill { height: 100%; border-radius: 3px; }
.analysis__bar-fill.green { background: #10b981; }
.analysis__stat { margin-bottom: 10px; }
.analysis__stat-name { font-size: 12px; color: #94a3b8; }
.analysis__stat-value { font-size: 15px; font-weight: 600; color: #1e293b; }
.analysis__stat-interp { font-size: 11px; color: #64748b; }
.analysis__fit-row { display: flex; justify-content: space-between; font-size: 13px; padding: 4px 0; border-bottom: 1px solid #f1f5f9; }
.analysis__fit-row span:first-child { color: #64748b; }
.mono { font-family: 'JetBrains Mono', monospace; font-weight: 500; }
.analysis__conclusion { margin-bottom: 12px; padding: 10px 14px; background: #f8fafc; border-radius: 8px; }
.analysis__conc-obs { font-size: 13px; font-weight: 500; color: #1e293b; }
.analysis__conc-interp { font-size: 12px; color: #64748b; margin-top: 2px; }
.analysis__conc-conf { font-size: 11px; color: #10b981; font-weight: 500; margin-top: 4px; }
</style>
