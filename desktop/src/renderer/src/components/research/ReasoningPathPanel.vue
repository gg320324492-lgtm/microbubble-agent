<script setup lang="ts">
import { computed } from 'vue'

export interface ReasoningPath {
  nodes: string[]
  edges: { from: string; to: string; type: string }[]
  conclusion: string
}

const props = withDefaults(defineProps<{
  path?: ReasoningPath | null
  ariaLabel?: string
}>(), {
  path: null,
  ariaLabel: '推理路径面板'
})

const isEmpty = computed(() => !props.path)
const pathNodes = computed(() => props.path?.nodes ?? [])
const pathEdges = computed(() => props.path?.edges ?? [])
</script>

<template>
  <section class="reasoning-path-panel" :aria-label="ariaLabel">
    <button type="button" class="reasoning-path-panel__focusable" @keydown.enter.prevent><span aria-hidden="true">.</span></button>
    <header class="reasoning-path-panel__head">
      <h2 class="reasoning-path-panel__title">推理路径</h2>
    </header>

    <div v-if="!isEmpty && path" class="reasoning-path-panel__body">
      <ol class="reasoning-path-panel__nodes">
        <li v-for="(node, idx) in pathNodes" :key="idx" class="reasoning-path-panel__node">
          {{ node }}
        </li>
      </ol>
      <div v-if="pathEdges.length > 0" class="reasoning-path-panel__edges">
        <span v-for="(edge, idx) in pathEdges" :key="idx" class="reasoning-path-panel__edge">
          {{ edge.from }} → {{ edge.to }} ({{ edge.type }})
        </span>
      </div>
      <p class="reasoning-path-panel__conclusion">{{ path.conclusion }}</p>
    </div>

    <div v-else class="reasoning-path-panel__empty" role="status">暂无推理路径</div>
  </section>
</template>

<style scoped>
.reasoning-path-panel { min-width: 0; overflow-x: hidden; background: linear-gradient(180deg, #ffffff 0%, #fef3ec 100%); border: 1px solid rgba(255, 122, 92, 0.2); border-radius: 12px; padding: 16px; }
.reasoning-path-panel:focus-visible { outline: 2px solid var(--research-primary-500, #FF7A5C); outline-offset: 2px; }
.reasoning-path-panel__head { margin-bottom: 12px; }
.reasoning-path-panel__title { font-size: 14px; font-weight: 600; color: #1e293b; margin: 0; }
.reasoning-path-panel__nodes { list-style: decimal; padding-left: 20px; margin: 0 0 12px; }
.reasoning-path-panel__node { font-size: 13px; color: #1e293b; margin-bottom: 4px; }
.reasoning-path-panel__edges { display: flex; flex-direction: column; gap: 4px; margin-bottom: 12px; }
.reasoning-path-panel__edge { font-size: 11px; color: #475569; padding: 4px 8px; background: rgba(15, 23, 42, 0.04); border-radius: 4px; }
.reasoning-path-panel__conclusion { font-size: 12px; color: #FF7A5C; font-weight: 600; padding: 8px; background: rgba(255, 122, 92, 0.08); border-radius: 4px; margin: 0; }
.reasoning-path-panel__empty { text-align: center; padding: 24px; color: #94a3b8; font-size: 13px; }
@media (max-width: 1480px) { .reasoning-path-panel { padding: 12px; } }
@media (min-width: 1720px) { .reasoning-path-panel { padding: 20px; } }
@media (prefers-reduced-motion: reduce) { .reasoning-path-panel, .reasoning-path-panel * { transition: none !important; } }
</style>