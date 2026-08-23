<template>
  <div class="data-mock">
    <div class="top-cards">
      <div class="card">
        <h3>数据质量</h3>
        <div class="metric-row">
          <span>完整度</span>
          <div class="bar"><div class="bar-fill green" :style="{ width: quality.completeness * 100 + '%' }"></div></div>
          <span>{{ quality.completeness * 100 }}%</span>
        </div>
        <div class="metric-row"><span>缺失值</span><span>{{ quality.missingCount }}</span></div>
        <div class="metric-row"><span>异常值</span><span>{{ quality.outlierCount }}</span></div>
        <div class="metric-row"><span>警告</span><span>{{ quality.warningCount }}</span></div>
      </div>
      <div class="card">
        <h3>统计分析</h3>
        <div class="stat-item" v-for="s in statistics" :key="s.name">
          <span class="stat-name">{{ s.name }}</span>
          <span class="stat-value">{{ s.value }}</span>
          <span class="stat-interpretation">{{ s.interpretation }}</span>
        </div>
      </div>
      <div class="card">
        <h3>模型拟合</h3>
        <div class="model-fit" v-for="m in models" :key="m.name">
          <div class="model-name">{{ m.name }}</div>
          <div class="model-r2">R² = {{ m.rSquared }}</div>
          <div class="model-error">残差 = {{ m.residualError }}</div>
        </div>
      </div>
    </div>
    <div class="bottom-cards">
      <div class="card chart-card">
        <h3>可视化</h3>
        <div class="chart-placeholder">
          <div class="chart-line"></div>
          <div class="chart-label">O3浓度-时间曲线</div>
        </div>
      </div>
      <div class="card">
        <h3>科学解读</h3>
        <div class="conclusion" v-for="c in conclusions" :key="c.observation">
          <div class="obs">📋 {{ c.observation }}</div>
          <div class="interp">{{ c.interpretation }}</div>
          <div class="conf">置信度: {{ c.confidence * 100 }}%</div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
const quality = { completeness: 1.0, missingCount: 0, outlierCount: 0, warningCount: 0 }
const statistics = [
  { name: '均值', value: '4.75 mg/L', interpretation: '平均O3浓度' },
  { name: '相关系数', value: '-0.987', interpretation: '强负相关' }
]
const models = [
  { name: 'first-order', rSquared: 0.998, residualError: 0.12 }
]
const conclusions = [
  { observation: '一级动力学最佳描述数据', interpretation: '浓度依赖行为', confidence: 0.90 }
]
</script>

<style scoped>
.data-mock { padding: 24px; }
.top-cards, .bottom-cards { display: flex; gap: 16px; margin-bottom: 16px; }
.card { background: white; border: 1px solid #e2e8f0; border-radius: 8px; padding: 16px; flex: 1; }
.chart-card { min-height: 200px; }
.metric-row { display: flex; justify-content: space-between; font-size: 13px; margin-bottom: 6px; }
.bar { flex: 1; height: 6px; background: #e2e8f0; border-radius: 3px; margin: 0 8px; }
.bar-fill { height: 100%; border-radius: 3px; }
.bar-fill.green { background: #10b981; }
.stat-item { margin-bottom: 8px; }
.stat-name { font-size: 12px; color: #64748b; }
.stat-value { font-size: 14px; font-weight: 500; margin-left: 8px; }
.stat-interpretation { font-size: 11px; color: #64748b; display: block; }
.model-name { font-size: 13px; font-weight: 500; font-family: monospace; }
.model-r2 { font-size: 12px; color: #10b981; }
.model-error { font-size: 12px; color: #64748b; }
.chart-placeholder { height: 120px; background: #f8fafc; border-radius: 6px; display: flex; align-items: center; justify-content: center; position: relative; }
.chart-line { width: 80%; height: 2px; background: #2563eb; position: relative; }
.chart-label { font-size: 11px; color: #64748b; position: absolute; bottom: -20px; }
.conclusion { margin-bottom: 8px; }
.obs { font-size: 13px; font-weight: 500; }
.interp { font-size: 12px; color: #64748b; }
.conf { font-size: 11px; color: #10b981; }
h3 { font-size: 13px; font-weight: 600; margin-bottom: 8px; }
</style>
