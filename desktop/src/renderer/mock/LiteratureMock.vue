<template>
  <div class="literature-mock">
    <div class="paper-list">
      <h3>PDF文献库</h3>
      <div class="paper-card" v-for="paper in papers" :key="paper.id"
           :class="{ selected: selectedId === paper.id }" @click="selectedId = paper.id">
        <div class="paper-title">{{ paper.title }}</div>
        <div class="paper-meta">{{ paper.authors }} ({{ paper.year }})</div>
        <div class="paper-rating">{{ '★'.repeat(paper.stars) }}{{ '☆'.repeat(5 - paper.stars) }}</div>
      </div>
    </div>
    <div class="paper-detail" v-if="selected">
      <h3>论文详情</h3>
      <div class="score-row">
        <span>可靠性</span>
        <div class="score-bar"><div class="score-fill" :style="{ width: selected.reliability * 100 + '%' }"></div></div>
        <span>{{ selected.reliability }}</span>
      </div>
      <div class="score-row">
        <span>证据</span>
        <div class="score-bar"><div class="score-fill" :style="{ width: selected.evidence * 100 + '%' }"></div></div>
        <span>{{ selected.evidence }}</span>
      </div>
      <div class="risk-section">
        <h4>风险提示</h4>
        <div class="risk-item" v-for="r in selected.risks" :key="r">⚠ {{ r }}</div>
      </div>
      <div class="evidence-section">
        <h4>证据提取</h4>
        <div class="evidence-item" v-for="e in selected.evidenceItems" :key="e">• {{ e }}</div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'

const selectedId = ref(1)

const papers = [
  { id: 1, title: 'Microbubble O3 degradation', authors: 'Zhang et al.', year: 2024, stars: 4, reliability: 0.82, evidence: 0.78, risks: ['统计方法不充分'], evidenceItems: ['kLa测量', '去除效率数据'] },
  { id: 2, title: 'Nanobubble characterization', authors: 'Li et al.', year: 2023, stars: 3, reliability: 0.65, evidence: 0.60, risks: ['机制证据薄弱'], evidenceItems: ['粒径分布'] },
  { id: 3, title: 'Ozone mass transfer', authors: 'Wang et al.', year: 2023, stars: 5, reliability: 0.90, evidence: 0.88, risks: [], evidenceItems: ['传质系数', '气液平衡'] }
]

const selected = computed(() => papers.find(p => p.id === selectedId.value))
</script>

<style scoped>
.literature-mock { display: flex; height: 100%; }
.paper-list { width: 300px; border-right: 1px solid #e2e8f0; padding: 16px; overflow-y: auto; }
.paper-detail { flex: 1; padding: 16px; }
.paper-card { padding: 12px; border: 1px solid #e2e8f0; border-radius: 6px; margin-bottom: 8px; cursor: pointer; }
.paper-card.selected { border-color: #2563eb; background: #eff6ff; }
.paper-title { font-size: 13px; font-weight: 500; margin-bottom: 2px; }
.paper-meta { font-size: 11px; color: #64748b; margin-bottom: 4px; }
.paper-rating { font-size: 12px; color: #f59e0b; }
.score-row { display: flex; align-items: center; gap: 8px; margin-bottom: 8px; font-size: 13px; }
.score-bar { flex: 1; height: 6px; background: #e2e8f0; border-radius: 3px; }
.score-fill { height: 100%; background: #2563eb; border-radius: 3px; }
.risk-section, .evidence-section { margin-top: 16px; }
.risk-item { font-size: 12px; color: #92400e; margin-bottom: 4px; }
.evidence-item { font-size: 12px; margin-bottom: 4px; }
h3 { font-size: 14px; font-weight: 600; margin-bottom: 12px; }
h4 { font-size: 13px; font-weight: 500; margin-bottom: 6px; }
</style>
