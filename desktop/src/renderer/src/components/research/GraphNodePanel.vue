<script setup lang="ts">
import { computed } from 'vue'

export interface GraphNodeDetail {
  id: string
  name: string
  type: string
  description?: string
}

const props = withDefaults(defineProps<{
  node?: GraphNodeDetail | null
  ariaLabel?: string
}>(), {
  node: null,
  ariaLabel: '节点详情面板'
})

const isEmpty = computed(() => !props.node)
</script>

<template>
  <section class="graph-node-panel" :aria-label="ariaLabel">
    <button type="button" class="graph-node-panel__focusable" @keydown.enter.prevent><span aria-hidden="true">.</span></button>
    <header class="graph-node-panel__head">
      <h2 class="graph-node-panel__title">节点详情</h2>
    </header>

    <div v-if="!isEmpty && node" class="graph-node-panel__body">
      <p class="graph-node-panel__id">{{ node.id }}</p>
      <h3 class="graph-node-panel__name">{{ node.name }}</h3>
      <span class="graph-node-panel__type">{{ node.type }}</span>
      <p v-if="node.description" class="graph-node-panel__description">{{ node.description }}</p>
    </div>

    <div v-else class="graph-node-panel__empty" role="status">暂无节点详情</div>
  </section>
</template>

<style scoped>
.graph-node-panel { min-width: 0; overflow-x: hidden; background: #fff; border: 1px solid rgba(15, 23, 42, 0.08); border-radius: 12px; padding: 16px; }
.graph-node-panel:focus-visible { outline: 2px solid var(--research-primary-500, #FF7A5C); outline-offset: 2px; }
.graph-node-panel__head { margin-bottom: 12px; }
.graph-node-panel__title { font-size: 14px; font-weight: 600; color: #1e293b; margin: 0; }
.graph-node-panel__id { font-size: 11px; color: #94a3b8; font-family: 'JetBrains Mono', monospace; margin: 0 0 4px; }
.graph-node-panel__name { font-size: 16px; font-weight: 600; color: #1e293b; margin: 0 0 6px; }
.graph-node-panel__type { font-size: 11px; color: #FF7A5C; padding: 2px 6px; border-radius: 4px; background: rgba(255, 122, 92, 0.1); display: inline-block; }
.graph-node-panel__description { font-size: 12px; color: #475569; line-height: 1.5; margin: 8px 0 0; }
.graph-node-panel__empty { text-align: center; padding: 24px; color: #94a3b8; font-size: 13px; }
@media (max-width: 1480px) { .graph-node-panel { padding: 12px; } }
@media (min-width: 1720px) { .graph-node-panel { padding: 20px; } }
@media (prefers-reduced-motion: reduce) { .graph-node-panel, .graph-node-panel * { transition: none !important; } }
</style>