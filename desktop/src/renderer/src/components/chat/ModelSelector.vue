<script setup lang="ts">
/**
 * ModelSelector.vue (Phase 6-B: Active Model Integration;
 *                      Phase 6-C1: research capability chips).
 *
 * Chat-header widget for selecting the active model provider + model.
 * Reads from `useModelSelectorStore` (Phase 6-B); never holds apiKey.
 *
 * Phase 6-B strict forbids:
 *   - NEVER display API key plaintext
 *   - NEVER store key in component state
 *   - All actions route through Pinia store (no direct IPC)
 *
 * Phase 6-C1 extension:
 *   - Each provider row shows its ResearchCapability chips
 *   - Selected row shows its capability badges in the trigger label
 */
import { computed, onMounted } from 'vue'
import { useModelSelectorStore } from '../../stores/model-selector'
import {
  capabilityLabel,
  type ModelCapability
} from '@shared/model/conversation-model'
import {
  researchCapabilityLabel,
  researchCapabilityGlyph,
  type ResearchCapability
} from '@shared/model/research-capability'

const store = useModelSelectorStore()

const showDropdown = computed(() => store.available.length > 0)
const selectedLabel = computed(() => {
  if (!store.selected) return 'Default (no provider selected)'
  const name = store.selected.displayName ?? store.selected.providerId
  return `${name} · ${store.selected.model}`
})
const capabilities = computed(() => store.capabilityList())
const selectedResearchCaps = computed<ResearchCapability[]>(() => {
  const cfg = store.available.find((p) => p.providerId === store.selectedId)
  const rp = (cfg as unknown as { researchProfile?: { capabilities?: ResearchCapability[] } } | undefined)?.researchProfile
  return rp?.capabilities ?? []
})

function researchCapsFor(providerId: string): ResearchCapability[] {
  const cfg = store.available.find((p) => p.providerId === providerId) as unknown as
    | { researchProfile?: { capabilities?: ResearchCapability[] } }
    | undefined
  return cfg?.researchProfile?.capabilities ?? []
}

onMounted(async () => {
  if (store.available.length === 0) {
    try { await store.loadAvailable() } catch (_e) { /* surfaced via store.lastError */ }
  }
})

async function onPickProvider(providerId: string): Promise<void> {
  await store.select(providerId)
}

function onClear(): void {
  store.clear()
}
</script>

<template>
  <div class="model-selector" data-testid="model-selector">
    <button
      class="model-selector__trigger"
      data-testid="model-selector-trigger"
      type="button"
      :title="selectedLabel"
    >
      <span class="model-selector__icon">🧠</span>
      <span class="model-selector__label">{{ selectedLabel }}</span>
      <span v-if="showDropdown" class="model-selector__chevron">▾</span>
    </button>
    <div v-if="showDropdown" class="model-selector__menu" data-testid="model-selector-menu">
      <div class="model-selector__section-title">Available providers</div>
      <button
        v-for="p in store.available"
        :key="p.providerId"
        :class="['model-selector__item', { 'is-active': store.selectedId === p.providerId, 'is-disabled': !p.hasKey }]"
        :disabled="!p.hasKey"
        :data-testid="`provider-${p.providerId}`"
        type="button"
        @click="onPickProvider(p.providerId)"
      >
        <span class="model-selector__item-name">{{ p.displayName }}</span>
        <span class="model-selector__item-meta">{{ p.defaultModel }}</span>
        <span :class="['model-selector__key', p.hasKey ? 'is-ok' : 'is-warn']">
          {{ p.hasKey ? '🔑' : '⚠ no key' }}
        </span>
        <span
          v-for="r in researchCapsFor(p.providerId)"
          :key="`${p.providerId}-${r}`"
          class="model-selector__chip is-research is-tiny"
          :data-testid="`research-${p.providerId}-${r}`"
        >
          {{ researchCapabilityGlyph(r) }} {{ researchCapabilityLabel(r) }}
        </span>
      </button>
      <button
        class="model-selector__clear"
        data-testid="model-selector-clear"
        type="button"
        @click="onClear"
      >
        Use default (legacy)
      </button>
      <div v-if="capabilities.length > 0 || selectedResearchCaps.length > 0" class="model-selector__caps">
        <span class="model-selector__section-title">Capabilities</span>
        <span v-for="c in capabilities" :key="c" class="model-selector__chip">
          {{ capabilityLabel(c as ModelCapability) }}
        </span>
        <span v-for="r in selectedResearchCaps" :key="r" class="model-selector__chip is-research">
          {{ researchCapabilityGlyph(r) }} {{ researchCapabilityLabel(r) }}
        </span>
      </div>
    </div>
  </div>
</template>

<style scoped>
.model-selector {
  position: relative;
  display: inline-flex;
}
.model-selector__trigger {
  display: inline-flex;
  align-items: center;
  gap: 0.4rem;
  background: #1e293b;
  border: 1px solid #334155;
  border-radius: 6px;
  padding: 0.35rem 0.7rem;
  color: #e2e8f0;
  font-size: 0.85rem;
  cursor: pointer;
}
.model-selector__trigger:hover { border-color: #f97316; }
.model-selector__icon { font-size: 1rem; }
.model-selector__label {
  max-width: 240px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.model-selector__chevron { font-size: 0.7rem; color: #94a3b8; }
.model-selector__menu {
  position: absolute;
  top: calc(100% + 4px);
  left: 0;
  z-index: 50;
  background: #0f172a;
  border: 1px solid #334155;
  border-radius: 6px;
  min-width: 280px;
  padding: 0.4rem;
  display: none;
}
.model-selector:hover .model-selector__menu,
.model-selector:focus-within .model-selector__menu { display: block; }
.model-selector__section-title {
  font-size: 0.7rem;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: #94a3b8;
  padding: 0.4rem 0.5rem 0.2rem;
}
.model-selector__item {
  display: grid;
  grid-template-columns: 1fr auto auto;
  align-items: center;
  gap: 0.4rem;
  width: 100%;
  background: transparent;
  border: 0;
  color: #e2e8f0;
  padding: 0.4rem 0.5rem;
  border-radius: 4px;
  cursor: pointer;
  font-size: 0.85rem;
  text-align: left;
}
.model-selector__item:hover:not(.is-disabled):not(:disabled) { background: rgba(249, 115, 22, 0.1); }
.model-selector__item.is-active { background: rgba(249, 115, 22, 0.18); color: #fde68a; }
.model-selector__item.is-disabled, .model-selector__item:disabled {
  opacity: 0.5; cursor: not-allowed;
}
.model-selector__item-meta { color: #94a3b8; font-size: 0.75rem; }
.model-selector__key.is-ok { color: #86efac; font-size: 0.75rem; }
.model-selector__key.is-warn { color: #fde68a; font-size: 0.75rem; }
.model-selector__clear {
  display: block;
  width: 100%;
  background: transparent;
  border: 1px dashed #475569;
  color: #94a3b8;
  border-radius: 4px;
  padding: 0.4rem 0.5rem;
  font-size: 0.8rem;
  cursor: pointer;
  margin-top: 0.4rem;
}
.model-selector__clear:hover { color: #f1f5f9; border-color: #f97316; }
.model-selector__caps {
  display: flex;
  flex-wrap: wrap;
  gap: 0.3rem;
  margin-top: 0.4rem;
  padding: 0.4rem 0.5rem;
  border-top: 1px solid #334155;
}
.model-selector__chip {
  font-size: 0.7rem;
  padding: 0.15rem 0.4rem;
  background: #334155;
  color: #cbd5e1;
  border-radius: 3px;
}
</style>
