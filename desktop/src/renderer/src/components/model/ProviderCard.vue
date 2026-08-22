<script setup lang="ts">
/**
 * ProviderCard.vue (Phase 6-A4: Model Settings).
 *
 * Renders a single provider's status, endpoint, defaultModel, and action buttons.
 *
 * Phase 6-A4 strict forbids:
 *   - NEVER display API key plaintext
 *   - NEVER call provider directly (only IPC via parent)
 *   - NEVER store key in component state
 */
import { computed } from 'vue'
import type { ProviderEntry } from '../../stores/model-provider'
import Button from '../ui/Button.vue'

interface Props {
  entry: ProviderEntry
  isActive?: boolean
}
const props = withDefaults(defineProps<Props>(), { isActive: false })

const emit = defineEmits<{
  test: [providerId: string]
  setActive: [providerId: string]
  deleteConfig: [providerId: string]
  saveKey: [providerId: string]
  deleteKey: [providerId: string]
}>()

const statusLabel = computed(() => {
  switch (props.entry.connectionStatus) {
    case 'connected':
      return '🟢 Connected'
    case 'failed':
      return '🔴 Failed'
    case 'checking':
      return '🟡 Checking…'
    case 'unknown':
    default:
      return '⚪ Unknown'
  }
})

const statusClass = computed(() => `provider-card__status--${props.entry.connectionStatus}`)

const latencyLabel = computed(() => {
  if (typeof props.entry.lastLatencyMs !== 'number') return '—'
  return `${props.entry.lastLatencyMs}ms`
})

const keyLabel = computed(() => (props.entry.hasKey ? '🔑 Configured' : '⚠ Needs API key'))

const endpointLabel = computed(() => props.entry.config.endpoint ?? '—')

const typeLabel = computed(() => {
  switch (props.entry.config.type) {
    case 'cloud':
      return 'Cloud'
    case 'local':
      return 'Local'
    case 'openai-compatible':
      return 'OpenAI-compatible'
  }
  return 'Unknown'
})
</script>

<template>
  <article :class="['provider-card', { 'is-active': isActive }]">
    <header class="provider-card__header">
      <div class="provider-card__title-row">
        <h3 class="provider-card__title">{{ entry.config.displayName }}</h3>
        <span :class="['provider-card__status', statusClass]">{{ statusLabel }}</span>
      </div>
      <div class="provider-card__meta">
        <span class="provider-card__chip">{{ typeLabel }}</span>
        <span class="provider-card__chip">{{ entry.config.providerId }}</span>
        <span :class="['provider-card__chip', entry.hasKey ? 'is-ok' : 'is-warn']">
          {{ keyLabel }}
        </span>
      </div>
    </header>

    <dl class="provider-card__details">
      <div class="provider-card__row">
        <dt>Model</dt>
        <dd>{{ entry.config.defaultModel }}</dd>
      </div>
      <div class="provider-card__row">
        <dt>Endpoint</dt>
        <dd class="provider-card__mono">{{ endpointLabel }}</dd>
      </div>
      <div class="provider-card__row">
        <dt>Latency</dt>
        <dd>{{ latencyLabel }}</dd>
      </div>
      <div v-if="entry.lastError" class="provider-card__row provider-card__row--error">
        <dt>Last error</dt>
        <dd>{{ entry.lastError }}</dd>
      </div>
    </dl>

    <footer class="provider-card__actions">
      <Button
        variant="secondary"
        size="small"
        :loading="entry.connectionStatus === 'checking'"
        data-testid="test-btn"
        @click="emit('test', entry.config.providerId)"
      >
        Test connection
      </Button>
      <Button
        v-if="!isActive && entry.hasKey"
        variant="primary"
        size="small"
        data-testid="set-active-btn"
        @click="emit('setActive', entry.config.providerId)"
      >
        Set as default
      </Button>
      <span v-else-if="isActive" class="provider-card__active-tag">★ Active</span>
      <Button
        v-if="!entry.hasKey"
        variant="ghost"
        size="small"
        data-testid="add-key-btn"
        @click="emit('saveKey', entry.config.providerId)"
      >
        Add API key
      </Button>
      <Button
        v-if="entry.hasKey"
        variant="ghost"
        size="small"
        data-testid="delete-key-btn"
        @click="emit('deleteKey', entry.config.providerId)"
      >
        Remove key
      </Button>
      <Button
        variant="danger"
        size="small"
        data-testid="delete-config-btn"
        @click="emit('deleteConfig', entry.config.providerId)"
      >
        Delete
      </Button>
    </footer>
  </article>
</template>

<style scoped>
.provider-card {
  background: #1e293b;
  border: 1px solid #334155;
  border-radius: 8px;
  padding: 1rem 1.25rem;
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}
.provider-card.is-active {
  border-color: #f97316;
  box-shadow: 0 0 0 2px rgba(249, 115, 22, 0.15);
}
.provider-card__title-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.provider-card__title {
  margin: 0;
  font-size: 1rem;
  font-weight: 600;
  color: #f1f5f9;
}
.provider-card__status { font-size: 0.85rem; font-weight: 500; }
.provider-card__status--connected { color: #22c55e; }
.provider-card__status--failed { color: #ef4444; }
.provider-card__status--checking { color: #eab308; }
.provider-card__status--unknown { color: #94a3b8; }
.provider-card__meta {
  display: flex;
  gap: 0.4rem;
  flex-wrap: wrap;
  margin-top: 0.4rem;
}
.provider-card__chip {
  font-size: 0.72rem;
  padding: 0.15rem 0.5rem;
  border-radius: 4px;
  background: #334155;
  color: #cbd5e1;
}
.provider-card__chip.is-ok { background: rgba(34, 197, 94, 0.15); color: #86efac; }
.provider-card__chip.is-warn { background: rgba(234, 179, 8, 0.15); color: #fde68a; }
.provider-card__details {
  display: grid;
  grid-template-columns: max-content 1fr;
  gap: 0.3rem 0.8rem;
  margin: 0;
}
.provider-card__row { display: contents; }
.provider-card__row dt {
  color: #94a3b8;
  font-size: 0.78rem;
}
.provider-card__row dd {
  color: #e2e8f0;
  font-size: 0.85rem;
  margin: 0;
}
.provider-card__row--error dd { color: #fca5a5; }
.provider-card__mono { font-family: ui-monospace, SFMono-Regular, Menlo, monospace; font-size: 0.78rem; }
.provider-card__actions {
  display: flex;
  gap: 0.5rem;
  flex-wrap: wrap;
  padding-top: 0.6rem;
  border-top: 1px solid #334155;
}
.provider-card__active-tag {
  font-size: 0.85rem;
  color: #f97316;
  font-weight: 600;
  padding: 0.3rem 0.7rem;
}
</style>
