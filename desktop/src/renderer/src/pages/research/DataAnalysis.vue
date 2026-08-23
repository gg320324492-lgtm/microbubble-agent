<script setup lang="ts">
/**
 * 数据分析 — 上传/质量/统计/拟合/可视化/解读。
 */
import ChartPanel from '../../components/research/ChartPanel.vue'
import StatusBadge from '../../components/research/StatusBadge.vue'

const quality = { completeness: 1.0, missing: 0, outliers: 0, warnings: 0 }
const stats = [
  { name: '均值', value: '4.75 mg/L', interp: '平均 O₃ 浓度' },
  { name: '标准差', value: '2.31 mg/L', interp: '浓度波动范围' },
  { name: '相关系数', value: 'r = -0.987', interp: '强负相关（浓度↓去除率↑）' },
]
const modelFit = { name: '伪一级动力学', kObs: '0.0243 min⁻¹', rSquared: '0.9887', adjR2: '0.9851', residual: '0.0211', n: 48, halfLife: '28.5 min' }
const importance = [
  { name: '曝气量', score: 0.42 },
  { name: '初始pH', score: 0.21 },
  { name: '初始TC浓度', score: 0.17 },
  { name: '气泡粒径', score: 0.11 },
  { name: '温度', score: 0.06 },
]
const conclusions = [
  { obs: '降解过程符合一级动力学特征', interp: '浓度依赖行为，拟合优度高', conf: 0.90 },
  { obs: '曝气量对降解率影响最大', interp: '传质过程是主要限速步骤', conf: 0.85 },
  { obs: 'pH 与降解率呈显著负相关', interp: '碱性条件有利于 TC 降解', conf: 0.82 },
]

const rawData = [
  { id: 'EXP-001', time: 0, tc: 20.0, ratio: 1.0, removal: 0.0, ozone: 1.2, ph: 7.0, temp: 25.0 },
  { id: 'EXP-001', time: 10, tc: 17.42, ratio: 0.871, removal: 12.9, ozone: 1.2, ph: 7.0, temp: 25.0 },
  { id: 'EXP-001', time: 20, tc: 15.21, ratio: 0.761, removal: 23.9, ozone: 1.2, ph: 7.0, temp: 25.0 },
  { id: 'EXP-001', time: 30, tc: 13.12, ratio: 0.656, removal: 34.4, ozone: 1.2, ph: 7.0, temp: 25.0 },
]
</script>

<template>
  <div class="analysis">
    <div class="analysis__header">
      <h1 class="analysis__title">数据分析</h1>
      <StatusBadge status="success" label="分析完成" />
    </div>

    <!-- 上部：质量/统计/拟合 -->
    <div class="analysis__top">
      <div class="analysis__card">
        <h3>数据质量</h3>
        <div class="analysis__q-row"><span>完整度</span><div class="analysis__bar"><div class="analysis__bar-fill green" style="width:100%"></div></div><span>100%</span></div>
        <div class="analysis__q-row"><span>缺失值</span><span>{{ quality.missing }}</span></div>
        <div class="analysis__q-row"><span>异常值</span><span>{{ quality.outliers }}</span></div>
        <div class="analysis__q-row"><span>警告</span><span>{{ quality.warnings }}</span></div>
      </div>
      <div class="analysis__card">
        <h3>统计分析</h3>
        <div class="analysis__stat" v-for="s in stats" :key="s.name">
          <div class="analysis__stat-name">{{ s.name }}</div>
          <div class="analysis__stat-value">{{ s.value }}</div>
          <div class="analysis__stat-interp">{{ s.interp }}</div>
        </div>
      </div>
      <div class="analysis__card">
        <h3>模型拟合 <StatusBadge status="success" label="拟合良好" /></h3>
        <div class="analysis__fit">
          <div class="analysis__fit-row"><span>模型</span><span class="mono">{{ modelFit.name }}</span></div>
          <div class="analysis__fit-row"><span>k<sub>obs</sub></span><span class="mono">{{ modelFit.kObs }}</span></div>
          <div class="analysis__fit-row"><span>R²</span><span class="mono">{{ modelFit.rSquared }}</span></div>
          <div class="analysis__fit-row"><span>t<sub>1/2</sub></span><span class="mono">{{ modelFit.halfLife }}</span></div>
          <div class="analysis__fit-row"><span>n</span><span class="mono">{{ modelFit.n }}</span></div>
        </div>
      </div>
    </div>

    <!-- 中部：变量重要性 + 可视化 -->
    <div class="analysis__middle">
      <div class="analysis__card">
        <h3>变量重要性</h3>
        <div class="analysis__imp" v-for="v in importance" :key="v.name">
          <span class="analysis__imp-name">{{ v.name }}</span>
          <div class="analysis__bar"><div class="analysis__bar-fill blue" :style="{ width: v.score * 100 / 0.5 + '%' }" /></div>
          <span class="analysis__imp-score">{{ v.score.toFixed(2) }}</span>
        </div>
      </div>
      <ChartPanel title="降解曲线" type="line">
        <div class="analysis__chart-placeholder">
          <div class="analysis__chart-line"></div>
          <div class="analysis__chart-label">C/C₀ vs 时间 (min)</div>
        </div>
      </ChartPanel>
    </div>

    <!-- 数据表 -->
    <div class="analysis__card" style="margin-bottom: 20px;">
      <h3>原始数据（共 48 条记录）</h3>
      <table class="analysis__table">
        <thead><tr><th>序号</th><th>实验ID</th><th>时间 (min)</th><th>TC 浓度 (mg/L)</th><th>C/C₀</th><th>降解率 (%)</th><th>曝气量 (L/min)</th><th>pH</th><th>温度 (°C)</th></tr></thead>
        <tbody>
          <tr v-for="(r, i) in rawData" :key="i">
            <td>{{ i + 1 }}</td><td>{{ r.id }}</td><td>{{ r.time }}</td><td>{{ r.tc }}</td>
            <td>{{ r.ratio }}</td><td>{{ r.removal }}</td><td>{{ r.ozone }}</td><td>{{ r.ph }}</td><td>{{ r.temp }}</td>
          </tr>
        </tbody>
      </table>
    </div>

    <!-- AI 科学解读 -->
    <div class="analysis__card">
      <h3>🔬 科学解读</h3>
      <div class="analysis__conclusion" v-for="c in conclusions" :key="c.obs">
        <div class="analysis__conc-obs">{{ c.obs }}</div>
        <div class="analysis__conc-interp">{{ c.interp }}</div>
        <div class="analysis__conc-conf">置信度 {{ (c.conf * 100).toFixed(0) }}%</div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.analysis { padding: 24px 28px; max-width: 1200px; }
.analysis__header { display: flex; align-items: center; gap: 12px; margin-bottom: 20px; }
.analysis__title { margin: 0; font-size: 20px; font-weight: 700; color: #0f172a; }
.analysis__top { display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 14px; margin-bottom: 16px; }
.analysis__middle { display: grid; grid-template-columns: 1fr 1fr; gap: 14px; margin-bottom: 16px; }
.analysis__card { background: #fff; border: 1px solid #e5e7eb; border-radius: 12px; padding: 16px; }
.analysis__card h3 { margin: 0 0 10px; font-size: 13px; font-weight: 600; color: #0f172a; display: flex; align-items: center; gap: 8px; }
.analysis__q-row { display: flex; justify-content: space-between; font-size: 13px; margin-bottom: 6px; color: #475569; }
.analysis__bar { flex: 1; height: 6px; background: #f1f5f9; border-radius: 3px; margin: 0 8px; }
.analysis__bar-fill { height: 100%; border-radius: 3px; }
.analysis__bar-fill.green { background: #10b981; }
.analysis__bar-fill.blue { background: #3b82f6; }
.analysis__stat { margin-bottom: 10px; }
.analysis__stat-name { font-size: 12px; color: #94a3b8; }
.analysis__stat-value { font-size: 15px; font-weight: 600; color: #1e293b; }
.analysis__stat-interp { font-size: 11px; color: #64748b; }
.analysis__fit-row { display: flex; justify-content: space-between; font-size: 13px; padding: 4px 0; border-bottom: 1px solid #f1f5f9; }
.analysis__fit-row span:first-child { color: #64748b; }
.mono { font-family: 'JetBrains Mono', monospace; font-weight: 500; }
.analysis__imp { display: flex; align-items: center; gap: 8px; margin-bottom: 8px; }
.analysis__imp-name { font-size: 13px; color: #475569; min-width: 80px; }
.analysis__imp-score { font-size: 12px; font-weight: 600; color: #3b82f6; min-width: 32px; text-align: right; }
.analysis__chart-placeholder { height: 120px; display: flex; flex-direction: column; align-items: center; justify-content: center; }
.analysis__chart-line { width: 80%; height: 2px; background: #3b82f6; margin-bottom: 8px; }
.analysis__chart-label { font-size: 11px; color: #94a3b8; }
.analysis__table { width: 100%; border-collapse: collapse; font-size: 12px; }
.analysis__table th { text-align: left; padding: 8px; color: #64748b; border-bottom: 2px solid #e5e7eb; font-weight: 500; }
.analysis__table td { padding: 8px; border-bottom: 1px solid #f1f5f9; color: #334155; }
.analysis__conclusion { margin-bottom: 12px; padding: 10px 14px; background: #f8fafc; border-radius: 8px; }
.analysis__conc-obs { font-size: 13px; font-weight: 500; color: #1e293b; }
.analysis__conc-interp { font-size: 12px; color: #64748b; margin-top: 2px; }
.analysis__conc-conf { font-size: 11px; color: #10b981; font-weight: 500; margin-top: 4px; }
</style>
