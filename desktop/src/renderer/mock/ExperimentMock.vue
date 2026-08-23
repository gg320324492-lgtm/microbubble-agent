<template>
  <div class="experiment-mock">
    <div class="top-cards">
      <div class="card">
        <h3>研究问题</h3>
        <div class="question-text">{{ design.question }}</div>
      </div>
      <div class="card">
        <h3>假设</h3>
        <div class="hypothesis" v-for="h in design.hypotheses" :key="h.statement">
          <div class="hypothesis-text">{{ h.statement }}</div>
          <div class="confidence">置信度: {{ h.confidence * 100 }}%</div>
        </div>
      </div>
      <div class="card">
        <h3>变量设计</h3>
        <div class="variable" v-for="v in design.variables" :key="v.name">
          <span class="var-type" :class="v.type">{{ v.type === 'independent' ? '自变量' : '因变量' }}</span>
          {{ v.name }} ({{ v.range }})
        </div>
      </div>
    </div>
    <div class="bottom-cards">
      <div class="card">
        <h3>实验分组</h3>
        <div class="group" v-for="g in design.groups" :key="g.name">
          <span class="group-name">{{ g.name }}</span>
          <span class="group-condition">{{ g.condition }}</span>
        </div>
        <div class="metrics">
          <h4>评估指标</h4>
          <div class="metric" v-for="m in design.metrics" :key="m">• {{ m }}</div>
        </div>
      </div>
      <div class="card">
        <h3>推荐模型</h3>
        <div class="model-rec">
          <div class="model-name">{{ design.model.name }}</div>
          <div class="model-confidence">置信度: {{ design.model.confidence * 100 }}%</div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
const design = {
  question: 'O3微纳米气泡降解效率优化',
  hypotheses: [
    { statement: '更小气泡提高传质效率', confidence: 0.80 },
    { statement: '自由基途径加速降解', confidence: 0.65 }
  ],
  variables: [
    { name: '气泡直径', type: 'independent', range: '50-500 nm' },
    { name: '去除效率', type: 'dependent', range: '0-100%' }
  ],
  groups: [
    { name: '对照组', condition: '常规曝气' },
    { name: '实验组1', condition: '200nm微纳米气泡' }
  ],
  metrics: ['粒径分布 (DLS)', 'O3浓度 (UV-Vis)'],
  model: { name: 'pseudo-first-order', confidence: 0.85 }
}
</script>

<style scoped>
.experiment-mock { padding: 24px; }
.top-cards, .bottom-cards { display: flex; gap: 16px; margin-bottom: 16px; }
.card { background: white; border: 1px solid #e2e8f0; border-radius: 8px; padding: 16px; flex: 1; }
.question-text { font-size: 14px; font-weight: 500; color: #1e293b; }
.hypothesis { margin-bottom: 8px; }
.hypothesis-text { font-size: 13px; }
.confidence { font-size: 11px; color: #10b981; }
.variable { font-size: 13px; margin-bottom: 4px; }
.var-type { font-size: 11px; padding: 2px 6px; border-radius: 3px; margin-right: 4px; }
.var-type.independent { background: #dbeafe; color: #1d4ed8; }
.var-type.dependent { background: #dcfce7; color: #166534; }
.group { display: flex; justify-content: space-between; font-size: 13px; margin-bottom: 4px; }
.group-name { font-weight: 500; }
.group-condition { color: #64748b; }
.metrics { margin-top: 12px; }
.metric { font-size: 12px; color: #64748b; }
.model-name { font-size: 14px; font-weight: 500; font-family: monospace; }
.model-confidence { font-size: 12px; color: #10b981; }
h3 { font-size: 13px; font-weight: 600; margin-bottom: 8px; }
h4 { font-size: 12px; font-weight: 500; margin-bottom: 4px; }
</style>
