<script setup lang="ts">
import { computed } from 'vue'

export interface GraphNode {
  id: string
  name: string
  type: string
  description?: string
}

const props = withDefaults(defineProps<{
  entities?: GraphNode[]
  ariaLabel?: string
}>(), {
  entities: () => [],
  ariaLabel: '知识图谱画布'
})

const nodeList = computed(() => props.entities ?? [])
const isEmpty = computed(() => nodeList.value.length === 0)
</script>

<template>
  <section class="graph-canvas" :aria-label="ariaLabel">
    <button type="button" class="graph-canvas__focusable" @keydown.enter.prevent><span aria-hidden="true">.</span></button>
    <header class="graph-canvas__head">
      <h2 class="graph-canvas__title">知识图谱画布</h2>
      <span class="graph-canvas__count">{{ nodeList.length }} 个节点</span>
    </header>

    <div v-if="!isEmpty" class="graph-canvas__content">
      <ul class="graph-canvas__list">
        <li
          v-for="node in nodeList"
          :key="node.id"
          class="graph-canvas__node"
          :data-type="node.type"
        >
          <span class="graph-canvas__node-id">{{ node.id }}</span>
          <span class="graph-canvas__node-name">{{ node.name }}</span>
          <span class="graph-canvas__node-type">{{ node.type }}</span>
        </li>
      </ul>
    </div>

    <div v-else class="graph-canvas__empty" role="status">暂无节点</div>
  </section>
</template>

<style scoped>
.graph-canvas {
  min-width: 0;
  overflow-x: hidden;
  background: linear-gradient(180deg, #ffffff 0%, #f8fafc 100%);
  border: 1px solid rgba(15, 23, 42, 0.08);
  border-radius: 12px;
  padding: 16px;
}
.graph-canvas:focus-visible { outline: 2px solid var(--research-primary-500, #FF7A5C); outline-offset: 2px; }
.graph-canvas__head { display: flex; justify-content: space-between; align-items: baseline; margin-bottom: 12px; }
.graph-canvas__title { font-size: 14px; font-weight: 600; color: #1e293b; margin: 0; }
.graph-canvas__count { font-size: 12px; color: #94a3b8; }
.graph-canvas__content { min-height: 200px; }
.graph-canvas__list { list-style: none; padding: 0; margin: 0; display: flex; flex-direction: column; gap: 6px; }
.graph-canvas__node { display: flex; gap: 8px; align-items: center; padding: 8px 12px; background: rgba(15, 23, 42, 0.04); border-radius: 6px; font-size: 12px; }
.graph-canvas__node-id { color: #94a3b8; font-family: 'JetBrains Mono', monospace; font-size: 11px; }
.graph-canvas__node-name { color: #1e293b; font-weight: 600; flex: 1; }
.graph-canvas__node-type { color: #FF7A5C; font-size: 11px; }
.graph-canvas__empty { text-align: center; padding: 48px; color: #94a3b8; font-size: 13px; }
@media (max-width: 1480px) { .graph-canvas { padding: 12px; } }
@media (min-width: 1720px) { .graph-canvas { padding: 20px; } }
@media (prefers-reduced-motion: reduce) { .graph-canvas, .graph-canvas * { transition: none !important; } }
</style>