<script setup lang="ts">
/**
 * ModelSettingsView.vue (Phase 6-A4: Model Settings + Provider Management).
 *
 * Top-level Settings page. Renders the list of configured providers via ProviderCard.
 * Provides actions: test / set-active / save-key / delete-key / delete-config.
 *
 * Phase 6-A4 strict forbids:
 *   - NEVER display API key plaintext
 *   - NEVER store key in component state
 *   - All actions route through window.api.model IPC -> main process
 */
import { onMounted, ref, computed } from 'vue'
import { useModelProviderStore } from '../../stores/model-provider'
import Card from '../../components/ui/Card.vue'
import EmptyState from '../../components/ui/EmptyState.vue'
import Loading from '../../components/ui/Loading.vue'
import ProviderCard from '../../components/model/ProviderCard.vue'
import type { ModelProviderConfig } from '@shared/preload-api'

const store = useModelProviderStore()

const showAddProvider = ref(false)
const draftProviderId = ref('')
const draftType = ref<'cloud' | 'local' | 'openai-compatible'>('openai-compatible')
const draftEndpoint = ref('')
const draftDefaultModel = ref('')
const draftDisplayName = ref('')
const draftCapabilities = ref('streaming')

const showAddKey = ref<string | null>(null)
const keyInput = ref('')

const hasAnyProvider = computed(() => store.providers.length > 0)

onMounted(async () => {
  await store.loadProviders()
})

async function onTest(providerId: string): Promise<void> {
  await store.testProvider(providerId)
}

async function onSetActive(providerId: string): Promise<void> {
  const entry = store.providers.find((p) => p.config.providerId === providerId)
  store.setActiveProvider(providerId)
  if (entry) store.setActiveModel(entry.config.defaultModel)
}

async function onDeleteConfig(providerId: string): Promise<void> {
  await store.removeProvider(providerId)
}

function onAskKey(providerId: string): void {
  showAddKey.value = providerId
  keyInput.value = ''
}

async function onSubmitKey(providerId: string): Promise<void> {
  if (keyInput.value.length === 0) return
  await store.saveApiKey(providerId, keyInput.value)
  keyInput.value = ''
  showAddKey.value = null
}

async function onDeleteKey(providerId: string): Promise<void> {
  await store.removeApiKey(providerId)
}

async function onSubmitProvider(): Promise<void> {
  const providerId = draftProviderId.value.trim()
  if (providerId.length === 0) return
  const cfg: Omit<ModelProviderConfig, 'providerId' | 'updatedAt'> = {
    type: draftType.value,
    defaultModel: draftDefaultModel.value.trim() || 'default-model',
    displayName: draftDisplayName.value.trim() || providerId,
    capabilities: draftCapabilities.value
      .split(',')
      .map((s) => s.trim())
      .filter((s) => s.length > 0),
    ...(draftEndpoint.value.trim() ? { endpoint: draftEndpoint.value.trim() } : {})
  }
  await store.saveProvider(providerId, cfg)
  draftProviderId.value = ''
  draftEndpoint.value = ''
  draftDefaultModel.value = ''
  draftDisplayName.value = ''
  draftCapabilities.value = 'streaming'
  showAddProvider.value = false
}
</script>

<template>
  <main class="model-settings">
    <Card title="Model providers" subtitle="Configure cloud + local LLM providers (Phase 6-A4).">
      <template #header>
        <div class="model-settings__header-row">
          <h3 class="ui-card__title">Model providers</h3>
          <button
            class="model-settings__add-btn"
            data-testid="add-provider-btn"
            @click="showAddProvider = !showAddProvider"
          >
            {{ showAddProvider ? 'Cancel' : '+ Add provider' }}
          </button>
        </div>
      </template>

      <Loading v-if="store.loading && !hasAnyProvider" message="Loading providers…" />

      <section v-if="showAddProvider" class="model-settings__form" data-testid="add-form">
        <h4>Add a new provider</h4>
        <label>
          Provider ID (lowercase a-z, 2-32 chars)
          <input
            v-model="draftProviderId"
            type="text"
            placeholder="my-vendor"
            data-testid="draft-providerId"
          />
        </label>
        <label>
          Display name
          <input v-model="draftDisplayName" type="text" placeholder="My Vendor" />
        </label>
        <label>
          Type
          <select v-model="draftType" data-testid="draft-type">
            <option value="cloud">Cloud</option>
            <option value="local">Local</option>
            <option value="openai-compatible">OpenAI-compatible</option>
          </select>
        </label>
        <label>
          Endpoint (required for local / openai-compatible)
          <input
            v-model="draftEndpoint"
            type="text"
            placeholder="https://api.example.com/v1"
            data-testid="draft-endpoint"
          />
        </label>
        <label>
          Default model
          <input
            v-model="draftDefaultModel"
            type="text"
            placeholder="gpt-4o-mini"
            data-testid="draft-defaultModel"
          />
        </label>
        <label>
          Capabilities (comma-separated)
          <input v-model="draftCapabilities" type="text" placeholder="streaming, tools" />
        </label>
        <button
          class="model-settings__submit"
          data-testid="submit-add-provider"
          :disabled="draftProviderId.trim().length < 2"
          @click="onSubmitProvider"
        >
          Save provider
        </button>
      </section>

      <EmptyState
        v-if="!store.loading && !hasAnyProvider"
        title="No providers configured"
        description="Add a cloud or local provider to get started."
      />

      <section v-else class="model-settings__list">
        <ProviderCard
          v-for="entry in store.providers"
          :key="entry.config.providerId"
          :entry="entry"
          :is-active="store.activeProviderId === entry.config.providerId"
          @test="onTest"
          @setActive="onSetActive"
          @deleteConfig="onDeleteConfig"
          @saveKey="onAskKey"
          @deleteKey="onDeleteKey"
        />
      </section>

      <section v-if="showAddKey" class="model-settings__key-form" data-testid="key-form">
        <h4>Add API key for {{ showAddKey }}</h4>
        <p class="model-settings__key-hint">
          Key is sent to main process, encrypted via OS keychain, and never returned to renderer.
        </p>
        <input
          v-model="keyInput"
          type="password"
          placeholder="sk-..."
          autocomplete="off"
          data-testid="key-input"
        />
        <div class="model-settings__key-actions">
          <button
            class="model-settings__submit"
            data-testid="submit-key"
            :disabled="keyInput.length === 0"
            @click="onSubmitKey(showAddKey)"
          >
            Save key
          </button>
          <button class="model-settings__cancel" @click="showAddKey = null">Cancel</button>
        </div>
      </section>
    </Card>
  </main>
</template>

<style scoped>
.model-settings { padding: 1.5rem; max-width: 960px; }
.model-settings__header-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  width: 100%;
}
.model-settings__add-btn {
  background: #f97316;
  color: #fff;
  border: 0;
  border-radius: 4px;
  padding: 0.4rem 0.8rem;
  font-size: 0.85rem;
  cursor: pointer;
}
.model-settings__add-btn:hover { background: #ea580c; }
.model-settings__form {
  display: grid;
  gap: 0.6rem;
  padding: 0.75rem 0;
}
.model-settings__form h4 { margin: 0 0 0.4rem; color: #f1f5f9; }
.model-settings__form label {
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
  font-size: 0.8rem;
  color: #94a3b8;
}
.model-settings__form input,
.model-settings__form select {
  background: #0f172a;
  border: 1px solid #334155;
  border-radius: 4px;
  padding: 0.4rem 0.6rem;
  color: #f1f5f9;
  font-family: inherit;
}
.model-settings__submit {
  background: #f97316;
  color: #fff;
  border: 0;
  border-radius: 4px;
  padding: 0.5rem 1rem;
  cursor: pointer;
}
.model-settings__submit:disabled { opacity: 0.5; cursor: not-allowed; }
.model-settings__cancel {
  background: transparent;
  border: 1px solid #475569;
  color: #e2e8f0;
  border-radius: 4px;
  padding: 0.5rem 1rem;
  cursor: pointer;
}
.model-settings__list {
  display: grid;
  gap: 0.75rem;
  padding-top: 0.75rem;
}
.model-settings__key-form {
  padding: 0.75rem 0;
  display: grid;
  gap: 0.5rem;
}
.model-settings__key-form h4 { margin: 0; color: #f1f5f9; }
.model-settings__key-hint { margin: 0; color: #94a3b8; font-size: 0.8rem; }
.model-settings__key-form input {
  background: #0f172a;
  border: 1px solid #334155;
  border-radius: 4px;
  padding: 0.4rem 0.6rem;
  color: #f1f5f9;
  font-family: inherit;
}
.model-settings__key-actions { display: flex; gap: 0.5rem; }
</style>
