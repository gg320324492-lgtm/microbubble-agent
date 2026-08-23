<script setup lang="ts">
/**
 * 知识图谱 — 实体关系网络。
 */
import StatusBadge from '../../components/research/StatusBadge.vue'

const entities = [
  { icon: '🔬', name: '微纳米气泡', type: '材料', count: 12 },
  { icon: '⚙️', name: '臭氧传质', type: '机制', count: 8 },
  { icon: '📊', name: '降解效率', type: '结果', count: 15 },
  { icon: '📄', name: '论文引用', type: '文献', count: 24 },
  { icon: '🧪', name: '实验条件', type: '实验', count: 9 },
  { icon: '⚡', name: '自由基', type: '机制', count: 6 },
]

const relations = [
  { source: '微纳米气泡', target: '臭氧传质', type: '促进', strength: 0.85, paper: 'Zhang 2024' },
  { source: '臭氧传质', target: '降解效率', type: '决定', strength: 0.90, paper: 'Li 2023' },
  { source: '自由基', target: '降解效率', type: '加速', strength: 0.78, paper: 'Wang 2021' },
  { source: '实验条件', target: '降解效率', type: '影响', strength: 0.65, paper: 'Chen 2023' },
]
</script>

<template>
  <div class="kg">
    <div class="kg__header">
      <h1 class="kg__title">知识图谱</h1>
      <StatusBadge status="info" label="O₃-MNBs 降解四环素" />
    </div>

    <!-- 图谱可视化 -->
    <div class="kg__graph">
      <svg viewBox="0 0 600 400" class="kg__svg">
        <!-- 连线 -->
        <line x1="300" y1="200" x2="150" y2="80" stroke="#94a3b8" stroke-width="1.5" marker-end="url(#arrow)" />
        <line x1="300" y1="200" x2="450" y2="80" stroke="#94a3b8" stroke-width="1.5" marker-end="url(#arrow)" />
        <line x1="300" y1="200" x2="150" y2="320" stroke="#94a3b8" stroke-width="1.5" marker-end="url(#arrow)" />
        <line x1="300" y1="200" x2="450" y2="320" stroke="#94a3b8" stroke-width="1.5" marker-end="url(#arrow)" />
        <line x1="450" y1="80" x2="450" y2="320" stroke="#94a3b8" stroke-width="1" stroke-dasharray="4" marker-end="url(#arrow)" />
        <defs><marker id="arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6" orient="auto"><path d="M 0 0 L 10 5 L 0 10 z" fill="#94a3b8" /></marker></defs>
        <!-- 节点 -->
        <g v-for="(e, i) in entities" :key="e.name" :transform="`translate(${[300,150,450,150,150,450][i]}, ${[200,80,80,320,320,200][i]})`">
          <rect x="-50" y="-20" width="100" height="40" rx="8" fill="#fff" stroke="#e2e8f0" stroke-width="1.5" />
          <text x="0" y="5" text-anchor="middle" font-size="12" fill="#1e293b">{{ e.icon }} {{ e.name }}</text>
        </g>
      </svg>
    </div>

    <!-- 下部：实体列表 + 关系详情 -->
    <div class="kg__bottom">
      <div class="kg__card">
        <h3>实体列表</h3>
        <div class="kg__entity" v-for="e in entities" :key="e.name">
          <span>{{ e.icon }}</span>
          <span class="kg__entity-name">{{ e.name }}</span>
          <StatusBadge status="neutral" :label="e.type" />
          <span class="kg__entity-count">({{ e.count }})</span>
        </div>
      </div>
      <div class="kg__card">
        <h3>关系详情</h3>
        <div class="kg__relation" v-for="r in relations" :key="r.source + r.target">
          <div class="kg__rel-header">{{ r.source }} → {{ r.target }}</div>
          <div class="kg__rel-detail">类型: {{ r.type }} · 强度: {{ r.strength }} · 来源: {{ r.paper }}</div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.kg { padding: 24px 28px; }
.kg__header { display: flex; align-items: center; gap: 12px; margin-bottom: 20px; }
.kg__title { margin: 0; font-size: 20px; font-weight: 700; color: #0f172a; }
.kg__graph { background: #fff; border: 1px solid #e5e7eb; border-radius: 12px; padding: 20px; margin-bottom: 20px; display: flex; justify-content: center; }
.kg__svg { width: 100%; max-width: 600px; }
.kg__bottom { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }
.kg__card { background: #fff; border: 1px solid #e5e7eb; border-radius: 12px; padding: 16px; }
.kg__card h3 { margin: 0 0 12px; font-size: 14px; font-weight: 600; color: #0f172a; }
.kg__entity { display: flex; align-items: center; gap: 8px; padding: 6px 0; font-size: 13px; border-bottom: 1px solid #f1f5f9; }
.kg__entity-name { font-weight: 500; color: #1e293b; }
.kg__entity-count { color: #94a3b8; font-size: 12px; }
.kg__relation { padding: 10px 12px; background: #f8fafc; border-radius: 8px; margin-bottom: 8px; }
.kg__rel-header { font-size: 13px; font-weight: 500; color: #1e293b; margin-bottom: 4px; }
.kg__rel-detail { font-size: 12px; color: #64748b; }
</style>
