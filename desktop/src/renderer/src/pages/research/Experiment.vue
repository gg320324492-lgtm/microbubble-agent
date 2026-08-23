<script setup lang="ts">
/**
 * 实验设计 — 工作流风格。
 */
import Timeline from '../../components/research/Timeline.vue'
import StatusBadge from '../../components/research/StatusBadge.vue'

const design = {
  question: 'O₃微纳米气泡降解四环素效率优化',
  hypotheses: [
    { statement: '更小气泡直径增加气液界面面积，提高臭氧传质效率', confidence: 0.80 },
    { statement: '自由基（·OH）途径是 TC 降解的主要活性机制', confidence: 0.65 },
  ],
  variables: [
    { name: '气泡直径', type: '自变量', range: '50 – 500 nm', unit: 'nm' },
    { name: '臭氧浓度', type: '自变量', range: '5 – 25 mg/L', unit: 'mg/L' },
    { name: 'pH', type: '控制变量', range: '5.0 – 9.0', unit: '' },
    { name: 'TC 去除率', type: '因变量', range: '0 – 100%', unit: '%' },
  ],
  groups: [
    { name: '对照组', condition: '常规曝气（无微纳米气泡）' },
    { name: '实验组 1', condition: '200 nm 微纳米气泡 + 10 mg/L O₃' },
    { name: '实验组 2', condition: '100 nm 微纳米气泡 + 15 mg/L O₃' },
    { name: '实验组 3', condition: '50 nm 微纳米气泡 + 20 mg/L O₃' },
  ],
  metrics: ['TC 去除率 (%)', 'TOC 去除率 (%)', '动力学常数 k (min⁻¹)', '半衰期 t₁/₂ (min)'],
  model: { name: '伪一级动力学', confidence: 0.85 },
}

const steps = [
  { label: '研究问题定义', status: 'done' as const },
  { label: '科学假设生成', status: 'done' as const },
  { label: '变量与分组设计', status: 'done' as const },
  { label: '评价指标确定', status: 'current' as const },
  { label: '推荐分析模型', status: 'pending' as const },
]
</script>

<template>
  <div class="experiment">
    <div class="experiment__header">
      <h1 class="experiment__title">实验设计</h1>
      <StatusBadge status="info" label="设计阶段" />
    </div>

    <div class="experiment__body">
      <!-- 左栏：工作流 -->
      <div class="experiment__workflow">
        <h3>设计流程</h3>
        <Timeline :steps="steps" />
      </div>

      <!-- 中栏：设计内容 -->
      <div class="experiment__content">
        <!-- 研究问题 -->
        <div class="experiment__section">
          <h3>研究问题</h3>
          <div class="experiment__question">{{ design.question }}</div>
        </div>

        <!-- 假设 -->
        <div class="experiment__section">
          <h3>科学假设</h3>
          <div class="experiment__hypothesis" v-for="(h, i) in design.hypotheses" :key="i">
            <span class="experiment__hypothesis-label">H{{ i + 1 }}</span>
            <div>
              <div>{{ h.statement }}</div>
              <div class="experiment__confidence">置信度 {{ (h.confidence * 100).toFixed(0) }}%</div>
            </div>
          </div>
        </div>

        <!-- 变量 -->
        <div class="experiment__section">
          <h3>变量设计</h3>
          <table class="experiment__table">
            <thead><tr><th>变量名</th><th>类型</th><th>范围</th><th>单位</th></tr></thead>
            <tbody>
              <tr v-for="v in design.variables" :key="v.name">
                <td>{{ v.name }}</td>
                <td><StatusBadge :status="v.type === '因变量' ? 'info' : v.type === '控制变量' ? 'neutral' : 'success'" :label="v.type" /></td>
                <td>{{ v.range }}</td>
                <td>{{ v.unit }}</td>
              </tr>
            </tbody>
          </table>
        </div>

        <!-- 分组 -->
        <div class="experiment__section">
          <h3>实验分组</h3>
          <div class="experiment__group" v-for="g in design.groups" :key="g.name">
            <span class="experiment__group-name">{{ g.name }}</span>
            <span class="experiment__group-cond">{{ g.condition }}</span>
          </div>
        </div>

        <!-- 指标 -->
        <div class="experiment__section">
          <h3>评价指标</h3>
          <div class="experiment__metrics">
            <span class="experiment__metric" v-for="m in design.metrics" :key="m">{{ m }}</span>
          </div>
        </div>
      </div>

      <!-- 右栏：推荐模型 -->
      <div class="experiment__right">
        <h3>推荐分析模型</h3>
        <div class="experiment__model-card">
          <div class="experiment__model-name">{{ design.model.name }}</div>
          <div class="experiment__model-conf">置信度 {{ (design.model.confidence * 100).toFixed(0) }}%</div>
          <div class="experiment__model-desc">标准动力学模型，适用于稀释体系降解过程</div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.experiment { padding: 24px 28px; }
.experiment__header { display: flex; align-items: center; gap: 12px; margin-bottom: 20px; }
.experiment__title { margin: 0; font-size: 20px; font-weight: 700; color: #0f172a; }
.experiment__body { display: grid; grid-template-columns: 180px 1fr 220px; gap: 20px; }
.experiment__workflow { background: #fff; border: 1px solid #e5e7eb; border-radius: 12px; padding: 16px; }
.experiment__workflow h3 { margin: 0 0 12px; font-size: 13px; font-weight: 600; color: #0f172a; }
.experiment__content { display: flex; flex-direction: column; gap: 16px; }
.experiment__section { background: #fff; border: 1px solid #e5e7eb; border-radius: 12px; padding: 16px; }
.experiment__section h3 { margin: 0 0 10px; font-size: 14px; font-weight: 600; color: #0f172a; }
.experiment__question { font-size: 15px; font-weight: 600; color: #1e293b; }
.experiment__hypothesis { display: flex; gap: 10px; margin-bottom: 10px; font-size: 13px; color: #334155; }
.experiment__hypothesis-label { font-weight: 700; color: #3b82f6; flex-shrink: 0; }
.experiment__confidence { font-size: 12px; color: #10b981; margin-top: 2px; }
.experiment__table { width: 100%; border-collapse: collapse; font-size: 13px; }
.experiment__table th { text-align: left; padding: 8px; color: #64748b; border-bottom: 1px solid #e5e7eb; font-weight: 500; }
.experiment__table td { padding: 8px; border-bottom: 1px solid #f1f5f9; }
.experiment__group { display: flex; justify-content: space-between; padding: 8px 0; border-bottom: 1px solid #f1f5f9; font-size: 13px; }
.experiment__group-name { font-weight: 500; color: #1e293b; }
.experiment__group-cond { color: #64748b; }
.experiment__metrics { display: flex; flex-wrap: wrap; gap: 8px; }
.experiment__metric { font-size: 12px; padding: 4px 10px; background: #f0fdf4; color: #166534; border-radius: 4px; }
.experiment__right { background: #fff; border: 1px solid #e5e7eb; border-radius: 12px; padding: 16px; }
.experiment__right h3 { margin: 0 0 12px; font-size: 13px; font-weight: 600; color: #0f172a; }
.experiment__model-card { background: #f0f9ff; border: 1px solid #bae6fd; border-radius: 8px; padding: 14px; }
.experiment__model-name { font-size: 14px; font-weight: 600; color: #1e293b; font-family: monospace; }
.experiment__model-conf { font-size: 12px; color: #10b981; margin: 4px 0; }
.experiment__model-desc { font-size: 12px; color: #64748b; }
</style>
