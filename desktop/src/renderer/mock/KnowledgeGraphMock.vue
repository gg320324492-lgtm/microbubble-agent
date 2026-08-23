<template>
  <div class="kg-mock">
    <div class="graph-area">
      <div class="graph-placeholder">
        <div class="node center">微纳米气泡</div>
        <div class="node top">臭氧传质</div>
        <div class="node right">自由基</div>
        <div class="node bottom">降解效率</div>
        <div class="node left">论文引用</div>
        <svg class="edges" viewBox="0 0 400 300">
          <line x1="200" y1="150" x2="200" y2="50" stroke="#94a3b8" stroke-width="1.5"/>
          <line x1="200" y1="150" x2="320" y2="150" stroke="#94a3b8" stroke-width="1.5"/>
          <line x1="200" y1="150" x2="200" y2="250" stroke="#94a3b8" stroke-width="1.5"/>
          <line x1="200" y1="150" x2="80" y2="150" stroke="#94a3b8" stroke-width="1.5"/>
        </svg>
      </div>
    </div>
    <div class="side-panel">
      <div class="entity-section">
        <h3>实体列表</h3>
        <div class="entity-item" v-for="e in entities" :key="e.name">
          <span class="entity-icon">{{ e.icon }}</span>
          {{ e.name }} <span class="entity-count">({{ e.count }})</span>
        </div>
      </div>
      <div class="relation-section">
        <h3>关系详情</h3>
        <div class="relation" v-for="r in relations" :key="r.source + r.target">
          {{ r.source }} → {{ r.target }}
          <div class="relation-type">类型: {{ r.type }}</div>
          <div class="relation-strength">强度: {{ r.strength }}</div>
          <div class="relation-source">来源: {{ r.sourcePaper }}</div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
const entities = [
  { icon: '🔬', name: '微纳米气泡', count: 12 },
  { icon: '📄', name: '论文', count: 8 },
  { icon: '🧪', name: '实验', count: 5 },
  { icon: '📊', name: '结果', count: 15 }
]

const relations = [
  { source: '微纳米气泡', target: '臭氧传质', type: '促进', strength: 0.85, sourcePaper: 'Zhang 2024' },
  { source: '臭氧传质', target: '降解效率', type: '决定', strength: 0.90, sourcePaper: 'Li 2023' }
]
</script>

<style scoped>
.kg-mock { display: flex; height: 100%; }
.graph-area { flex: 1; padding: 16px; position: relative; }
.graph-placeholder { width: 100%; height: 100%; background: #f8fafc; border-radius: 8px; position: relative; }
.node { position: absolute; background: white; border: 1px solid #e2e8f0; border-radius: 6px; padding: 8px 12px; font-size: 12px; font-weight: 500; }
.node.center { top: 50%; left: 50%; transform: translate(-50%, -50%); background: #eff6ff; border-color: #2563eb; }
.node.top { top: 10%; left: 50%; transform: translateX(-50%); }
.node.right { top: 50%; right: 10%; transform: translateY(-50%); }
.node.bottom { bottom: 10%; left: 50%; transform: translateX(-50%); }
.node.left { top: 50%; left: 10%; transform: translateY(-50%); }
.edges { position: absolute; top: 0; left: 0; width: 100%; height: 100%; pointer-events: none; }
.side-panel { width: 260px; border-left: 1px solid #e2e8f0; padding: 16px; overflow-y: auto; }
.entity-section { margin-bottom: 24px; }
.entity-item { font-size: 13px; padding: 6px 0; display: flex; align-items: center; gap: 6px; }
.entity-count { color: #64748b; }
.relation { font-size: 12px; margin-bottom: 8px; padding: 8px; background: #f8fafc; border-radius: 4px; }
.relation-type, .relation-strength, .relation-source { font-size: 11px; color: #64748b; }
h3 { font-size: 13px; font-weight: 600; margin-bottom: 8px; }
</style>
