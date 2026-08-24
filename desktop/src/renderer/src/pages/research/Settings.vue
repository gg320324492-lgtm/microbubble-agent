<script setup lang="ts">
import { computed, nextTick, onMounted, reactive, ref } from 'vue'
import ResearchIcon from '../../components/icons/ResearchIcon.vue'
import ResearchState from '../../components/research/ResearchState.vue'
import StatusBadge from '../../components/research/StatusBadge.vue'
import { useModelProviderStore, type ProviderEntry } from '../../stores/model-provider'

type SettingsTab = 'model' | 'knowledge' | 'profile' | 'api'
interface ProviderDraft { displayName: string; defaultModel: string; endpoint: string }
type OperationKind = 'load' | 'save-provider' | 'test-provider' | 'save-key' | 'remove-provider'
interface SettingsOperation { kind: OperationKind; providerId?: string }

const store = useModelProviderStore()
const activeTab = ref<SettingsTab>('model')
const providerLoadState = ref<'loading' | 'ready' | 'error'>(store.providers.length ? 'ready' : 'loading')
const operation = ref<SettingsOperation | null>(null)
const operationBusy = computed(() => operation.value !== null)
const savedProviderId = ref<string | null>(null)
const providerSaveErrors = reactive<Record<string, boolean>>({})
const providerDrafts = reactive<Record<string, ProviderDraft>>({})
const dirtyDrafts = reactive<Record<string, boolean>>({})
const keyDrafts = reactive<Record<string, string>>({})
const keyErrors = reactive<Record<string, boolean>>({})
const confirmRemoveId = ref<string | null>(null)
const providerStateUncertain = ref(false)

const tabs: Array<{ id: SettingsTab; label: string; icon: 'model' | 'folder' | 'user' | 'settings' }> = [
  { id: 'model', label: '模型配置', icon: 'model' },
  { id: 'knowledge', label: '知识库管理', icon: 'folder' },
  { id: 'profile', label: '研究者信息', icon: 'user' },
  { id: 'api', label: 'API 与密钥', icon: 'settings' }
]

function clearRemoveConfirmation(): void {
  confirmRemoveId.value = null
}
function pruneRecord<T>(record: Record<string, T>, currentIds: Set<string>): void {
  for (const id of Object.keys(record)) {
    if (!currentIds.has(id)) delete record[id]
  }
}
function syncAndPruneDrafts(forceProviderId?: string): void {
  const currentIds = new Set(store.providers.map(entry => entry.config.providerId))
  pruneRecord(providerDrafts, currentIds)
  pruneRecord(dirtyDrafts, currentIds)
  pruneRecord(providerSaveErrors, currentIds)
  pruneRecord(keyDrafts, currentIds)
  pruneRecord(keyErrors, currentIds)
  if (savedProviderId.value && !currentIds.has(savedProviderId.value)) savedProviderId.value = null
  if (confirmRemoveId.value && !currentIds.has(confirmRemoveId.value)) clearRemoveConfirmation()
  for (const entry of store.providers) {
    const id = entry.config.providerId
    if (!providerDrafts[id] || !dirtyDrafts[id] || forceProviderId === id) {
      providerDrafts[id] = {
        displayName: entry.config.displayName,
        defaultModel: entry.config.defaultModel,
        endpoint: entry.config.endpoint ?? ''
      }
      dirtyDrafts[id] = false
    }
    if (keyDrafts[id] === undefined) keyDrafts[id] = ''
  }
}
function markDraftDirty(id: string): void {
  clearRemoveConfirmation()
  dirtyDrafts[id] = true
  providerSaveErrors[id] = false
  if (savedProviderId.value === id) savedProviderId.value = null
}
function markKeyEdited(): void {
  clearRemoveConfirmation()
}
function selectTab(id: SettingsTab): void {
  clearRemoveConfirmation()
  if (activeTab.value === id) return
  activeTab.value = id
}
function onTabKeydown(event: KeyboardEvent, id: SettingsTab): void {
  if (event.key === 'Enter' || event.key === ' ') {
    event.preventDefault()
    selectTab(id)
    return
  }
  const current = tabs.findIndex(tab => tab.id === id)
  let target = current
  if (event.key === 'ArrowDown' || event.key === 'ArrowRight') target = (current + 1) % tabs.length
  else if (event.key === 'ArrowUp' || event.key === 'ArrowLeft') target = (current - 1 + tabs.length) % tabs.length
  else if (event.key === 'Home') target = 0
  else if (event.key === 'End') target = tabs.length - 1
  else return
  event.preventDefault()
  const targetId = tabs[target].id
  selectTab(targetId)
  document.getElementById(`settings-tab-${targetId}`)?.focus()
}
async function loadProviders(): Promise<void> {
  if (operationBusy.value) return
  clearRemoveConfirmation()
  operation.value = { kind: 'load' }
  providerLoadState.value = store.providers.length ? 'ready' : 'loading'
  try {
    await store.loadProviders()
    syncAndPruneDrafts()
    providerLoadState.value = 'ready'
    providerStateUncertain.value = false
  } catch {
    providerLoadState.value = 'error'
  } finally {
    operation.value = null
  }
}
async function testProvider(entry: ProviderEntry): Promise<void> {
  if (operationBusy.value || providerStateUncertain.value) return
  clearRemoveConfirmation()
  operation.value = { kind: 'test-provider', providerId: entry.config.providerId }
  try { await store.testProvider(entry.config.providerId) }
  finally { operation.value = null }
}
function connectionLabel(entry: ProviderEntry): string {
  if (entry.connectionStatus === 'checking') return '正在检测'
  if (entry.connectionStatus === 'connected') return `已连接${entry.lastLatencyMs === undefined ? '' : ` · ${entry.lastLatencyMs} 毫秒`}`
  if (entry.connectionStatus === 'failed') return '连接失败'
  return '连接状态未检测'
}
function providerTypeLabel(type: ProviderEntry['config']['type']): string {
  if (type === 'cloud') return '云端'
  if (type === 'local') return '本地'
  return '兼容接口'
}
async function saveProvider(entry: ProviderEntry): Promise<void> {
  const id = entry.config.providerId
  if (operationBusy.value || providerStateUncertain.value) return
  clearRemoveConfirmation()
  operation.value = { kind: 'save-provider', providerId: id }
  savedProviderId.value = null
  providerSaveErrors[id] = false
  const draft = providerDrafts[id]
  try {
    await store.saveProvider(id, {
      type: entry.config.type,
      displayName: draft.displayName.trim() || entry.config.displayName,
      defaultModel: draft.defaultModel.trim() || entry.config.defaultModel,
      capabilities: entry.config.capabilities,
      ...(draft.endpoint.trim() ? { endpoint: draft.endpoint.trim() } : {}),
      ...(entry.config.researchProfile ? { researchProfile: entry.config.researchProfile } : {})
    })
    dirtyDrafts[id] = false
    syncAndPruneDrafts(id)
    savedProviderId.value = store.providers.some(provider => provider.config.providerId === id) ? id : null
  } catch {
    providerSaveErrors[id] = true
  } finally {
    operation.value = null
  }
}
async function saveKey(entry: ProviderEntry): Promise<void> {
  const id = entry.config.providerId
  if (operationBusy.value || providerStateUncertain.value || !keyDrafts[id]) return
  clearRemoveConfirmation()
  const apiKey = keyDrafts[id]
  operation.value = { kind: 'save-key', providerId: id }
  keyErrors[id] = false
  try {
    await store.saveApiKey(id, apiKey)
    syncAndPruneDrafts()
    if (store.providers.some(provider => provider.config.providerId === id)) keyDrafts[id] = ''
  } catch {
    keyErrors[id] = true
  } finally {
    operation.value = null
  }
}
async function removeProvider(id: string): Promise<void> {
  if (operationBusy.value || providerStateUncertain.value) return
  if (confirmRemoveId.value !== id) {
    confirmRemoveId.value = id
    return
  }
  operation.value = { kind: 'remove-provider', providerId: id }
  try {
    await store.removeProvider(id)
    syncAndPruneDrafts()
  } catch {
    providerStateUncertain.value = true
  } finally {
    clearRemoveConfirmation()
    if (keyDrafts[id] !== undefined) keyDrafts[id] = ''
    await nextTick()
    delete keyDrafts[id]
    delete providerDrafts[id]
    delete dirtyDrafts[id]
    delete providerSaveErrors[id]
    delete keyErrors[id]
    if (savedProviderId.value === id) savedProviderId.value = null
    operation.value = null
  }
}
syncAndPruneDrafts()
onMounted(loadProviders)
</script>

<template>
  <section class="settings" aria-label="系统设置">
    <header class="settings__header">
      <p><ResearchIcon name="settings" :size="17" />科研工作站配置</p>
      <h1>系统设置</h1>
      <span>模型配置与密钥操作沿用现有主进程安全通道。</span>
    </header>

    <div class="settings__workspace">
      <div v-if="providerStateUncertain" class="settings__uncertain settings__uncertain--global" data-testid="provider-state-uncertain" role="alert"><span>删除请求可能已执行，但刷新失败，请重新加载确认</span><button type="button" data-action="reload-after-uncertain" :disabled="operationBusy" :aria-busy="operation?.kind === 'load' ? 'true' : 'false'" @click="loadProviders">{{ operation?.kind === 'load' ? '正在重新加载...' : '重新加载确认' }}</button></div>
      <nav class="settings__nav" role="tablist" aria-label="设置分组" aria-orientation="vertical">
        <button v-for="tab in tabs" :id="`settings-tab-${tab.id}`" :key="tab.id" type="button" role="tab" :data-settings-tab="tab.id" :aria-selected="activeTab === tab.id ? 'true' : 'false'" :aria-controls="`settings-panel-${tab.id}`" :tabindex="activeTab === tab.id ? 0 : -1" @click="selectTab(tab.id)" @keydown="onTabKeydown($event, tab.id)">
          <ResearchIcon :name="tab.icon" :size="18" /><span>{{ tab.label }}</span><ResearchIcon name="expand" :size="14" />
        </button>
      </nav>

      <section :id="`settings-panel-${activeTab}`" class="settings__panel" role="tabpanel" :aria-labelledby="`settings-tab-${activeTab}`">
        <template v-if="activeTab === 'model'">
          <div class="settings__panel-heading"><div><p>现有模型提供商</p><h2>模型配置</h2></div><div class="settings__heading-actions"><span>非密钥配置</span><button type="button" class="settings__secondary" data-action="refresh-providers" :disabled="operationBusy || providerStateUncertain" @click="loadProviders">{{ operation?.kind === 'load' ? '正在刷新...' : '刷新配置' }}</button></div></div>
          <ResearchState v-if="providerLoadState === 'loading' && store.providers.length === 0" data-testid="settings-provider-state" state="loading" />
          <ResearchState v-else-if="providerLoadState === 'error' && store.providers.length === 0" data-testid="settings-provider-state" state="error" title="模型配置加载失败，请重试" @retry="loadProviders" />
          <ResearchState v-else-if="store.providers.length === 0" data-testid="settings-provider-state" state="empty" title="暂无模型提供商" description="请通过现有模型配置入口添加提供商。" />
          <div v-else class="settings__providers">
            <div v-if="providerLoadState === 'error' && !providerStateUncertain" class="settings__retained-error" data-testid="settings-provider-retained-error" role="alert"><span>模型配置刷新失败，请重试。已保留当前提供商。</span><button type="button" data-action="refresh-providers" :disabled="operationBusy" @click="loadProviders">重新加载</button></div>
            <template v-for="entry in store.providers" :key="entry.config.providerId">
            <form v-if="providerDrafts[entry.config.providerId]" class="settings__provider" :data-provider-id="entry.config.providerId" @submit.prevent="saveProvider(entry)">
              <header><div><ResearchIcon name="model" :size="20" /><div><h3>{{ entry.config.displayName }}</h3><p>{{ entry.config.providerId }} · {{ providerTypeLabel(entry.config.type) }} · {{ entry.config.defaultModel }}</p></div></div><div class="settings__statuses"><StatusBadge :status="entry.hasKey ? 'success' : 'warning'" :label="entry.hasKey ? '密钥已配置' : '未配置密钥'" /><StatusBadge :status="entry.connectionStatus === 'connected' ? 'success' : entry.connectionStatus === 'failed' ? 'error' : 'neutral'" :label="connectionLabel(entry)" /></div></header>
              <div class="settings__form-grid">
                <label :for="`provider-${entry.config.providerId}-display-name`">显示名称</label>
                <input :id="`provider-${entry.config.providerId}-display-name`" v-model="providerDrafts[entry.config.providerId].displayName" data-field="display-name" type="text" :disabled="operationBusy || providerStateUncertain" @input="markDraftDirty(entry.config.providerId)" />
                <label :for="`provider-${entry.config.providerId}-model`">默认模型</label>
                <input :id="`provider-${entry.config.providerId}-model`" v-model="providerDrafts[entry.config.providerId].defaultModel" type="text" :disabled="operationBusy || providerStateUncertain" @input="markDraftDirty(entry.config.providerId)" />
                <label :for="`provider-${entry.config.providerId}-endpoint`">服务地址</label>
                <input :id="`provider-${entry.config.providerId}-endpoint`" v-model="providerDrafts[entry.config.providerId].endpoint" type="url" :placeholder="entry.config.type === 'cloud' ? '使用提供商默认地址' : '请输入本地服务地址'" :disabled="operationBusy || providerStateUncertain" @input="markDraftDirty(entry.config.providerId)" />
              </div>
              <div class="settings__provider-actions">
                <button type="button" class="settings__secondary" data-action="test-provider" :disabled="operationBusy || providerStateUncertain" @click="testProvider(entry)"><ResearchIcon name="running" :size="15" />{{ operation?.kind === 'test-provider' && operation.providerId === entry.config.providerId ? '正在检测...' : '检测连接' }}</button>
                <button type="submit" class="settings__primary" data-action="save-provider" :disabled="operationBusy || providerStateUncertain" :aria-busy="operation?.kind === 'save-provider' && operation.providerId === entry.config.providerId ? 'true' : 'false'"><ResearchIcon name="check" :size="15" />{{ operation?.kind === 'save-provider' && operation.providerId === entry.config.providerId ? '正在保存...' : '保存配置' }}</button>
              </div>
              <div v-if="providerSaveErrors[entry.config.providerId]" class="settings__inline-error" data-testid="provider-save-error" role="alert"><span>保存失败，请重试。输入内容已保留。</span><button type="button" :disabled="operationBusy || providerStateUncertain" @click="saveProvider(entry)">重新保存</button></div>
              <p v-if="savedProviderId === entry.config.providerId" class="settings__saved" role="status">配置已保存</p>
            </form>
            </template>
          </div>
        </template>

        <template v-else-if="activeTab === 'knowledge'">
          <div class="settings__panel-heading"><div><p>数据边界</p><h2>知识库管理</h2></div></div>
          <section class="settings__notice"><ResearchIcon name="folder" :size="24" /><div><h3>沿用当前知识库配置</h3><p>当前设置接口未提供独立的检索库、阈值或存储容量配置。本页不展示虚构容量，也不会新增持久化路径。</p></div></section>
        </template>

        <template v-else-if="activeTab === 'profile'">
          <div class="settings__panel-heading"><div><p>账户边界</p><h2>研究者信息</h2></div></div>
          <section class="settings__notice"><ResearchIcon name="user" :size="24" /><div><h3>沿用当前账户资料</h3><p>当前科研设置接口不提供姓名、团队与研究方向编辑动作。请在账户资料入口维护真实信息。</p></div></section>
        </template>

        <template v-else>
          <div class="settings__panel-heading"><div><p>主进程安全存储</p><h2>API 与密钥</h2></div><div class="settings__heading-actions"><span>密钥由主进程安全保存</span><button type="button" class="settings__secondary" data-action="refresh-providers" :disabled="operationBusy || providerStateUncertain" @click="loadProviders">{{ operation?.kind === 'load' ? '正在刷新...' : '刷新配置' }}</button></div></div>
          <ResearchState v-if="providerLoadState === 'loading' && store.providers.length === 0" data-testid="settings-provider-state" state="loading" />
          <ResearchState v-else-if="providerLoadState === 'error' && store.providers.length === 0" data-testid="settings-provider-state" state="error" title="模型配置加载失败，请重试" @retry="loadProviders" />
          <ResearchState v-else-if="store.providers.length === 0" data-testid="settings-provider-state" state="empty" title="暂无模型提供商" description="添加模型提供商后，才能配置对应的 API 密钥。" />
          <div v-else class="settings__keys">
            <div v-if="providerLoadState === 'error' && !providerStateUncertain" class="settings__retained-error" data-testid="settings-provider-retained-error" role="alert"><span>模型配置刷新失败，请重试。已保留当前提供商。</span><button type="button" data-action="refresh-providers" :disabled="operationBusy" @click="loadProviders">重新加载</button></div>
            <template v-for="entry in store.providers" :key="entry.config.providerId">
            <section v-if="keyDrafts[entry.config.providerId] !== undefined" class="settings__key-card">
              <div><h3>{{ entry.config.displayName }}</h3><StatusBadge :status="entry.hasKey ? 'success' : 'warning'" :label="entry.hasKey ? '密钥已配置' : '未配置密钥'" /></div>
              <label :for="`api-key-${entry.config.providerId}`">{{ entry.config.displayName }} API 密钥</label>
              <div class="settings__key-input"><input :id="`api-key-${entry.config.providerId}`" v-model="keyDrafts[entry.config.providerId]" :data-testid="`api-key-${entry.config.providerId}`" type="password" autocomplete="off" placeholder="输入新密钥" :disabled="operationBusy || providerStateUncertain" @input="markKeyEdited" /><button type="button" class="settings__primary" :data-action="`save-key-${entry.config.providerId}`" :disabled="operationBusy || providerStateUncertain || !keyDrafts[entry.config.providerId]" @click="saveKey(entry)">{{ operation?.kind === 'save-key' && operation.providerId === entry.config.providerId ? '正在保存...' : '安全保存' }}</button></div>
              <div v-if="keyErrors[entry.config.providerId]" class="settings__inline-error" role="alert"><span>密钥保存失败，请重试。输入内容已保留。</span><button type="button" :disabled="operationBusy || providerStateUncertain" @click="saveKey(entry)">重试</button></div>
              <p>密钥不会写入业务数据仓库，保存后不会读回明文。</p>
            </section>
            </template>
          </div>
          <section class="settings__danger" data-testid="settings-danger-zone" aria-label="危险操作">
            <header><ResearchIcon name="warning" :size="20" /><div><h3>危险操作</h3><p>删除模型配置会同时移除该配置的可用入口。</p></div></header>
            <div v-for="entry in store.providers" :key="entry.config.providerId" class="settings__danger-row"><span>删除模型配置：{{ entry.config.displayName }}</span><button type="button" :data-action="`remove-provider-${entry.config.providerId}`" :disabled="operationBusy || providerStateUncertain" @click="removeProvider(entry.config.providerId)">{{ operation?.kind === 'remove-provider' && operation.providerId === entry.config.providerId ? '正在删除...' : confirmRemoveId === entry.config.providerId ? '再次点击确认删除' : '删除配置' }}</button></div>
          </section>
        </template>
      </section>
    </div>
  </section>
</template>

<style scoped>
.settings{min-width:0;min-height:100%;padding:var(--research-page-gutter);background:var(--research-bg-main);color:var(--research-text-primary)}.settings__header{margin-block-end:var(--research-space-5)}.settings__header>p{display:flex;align-items:center;gap:var(--research-space-2);margin:0;color:var(--research-ai-700);font-size:var(--research-text-sm);font-weight:var(--research-font-weight-semibold)}.settings__header h1{margin:var(--research-space-1) 0;font-size:var(--research-text-page-title)}.settings__header>span{color:var(--research-text-secondary);font-size:var(--research-text-body)}.settings__workspace{display:grid;grid-template-columns:minmax(190px,.28fr) minmax(0,1fr);gap:var(--research-grid-gap);min-width:0}.settings__nav{display:grid;align-content:start;gap:var(--research-space-1);padding:var(--research-space-3);border:1px solid var(--research-border-subtle);border-radius:var(--research-radius-panel);background:var(--research-bg-card);box-shadow:var(--research-shadow-soft)}.settings__nav button{display:grid;grid-template-columns:auto minmax(0,1fr) auto;align-items:center;gap:var(--research-space-2);padding:var(--research-space-3);border:1px solid transparent;border-radius:var(--research-radius-button);background:transparent;color:var(--research-text-secondary);font:inherit;text-align:start;cursor:pointer}.settings__nav button:hover{background:var(--research-bg-hover);color:var(--research-text-primary)}.settings__nav button[aria-selected="true"]{border-color:var(--research-primary-200);background:var(--research-primary-50);color:var(--research-primary-700);font-weight:var(--research-font-weight-semibold)}.settings__nav button:focus-visible,.settings button:focus-visible,.settings input:focus-visible{outline:none;box-shadow:var(--research-shadow-focus-primary)}.settings__panel{min-width:0;padding:var(--research-space-5);border:1px solid var(--research-border-subtle);border-radius:var(--research-radius-panel);background:var(--research-bg-card);box-shadow:var(--research-shadow-soft)}.settings__panel-heading{display:flex;align-items:flex-start;justify-content:space-between;gap:var(--research-space-4);margin-block-end:var(--research-space-5)}.settings__panel-heading p{margin:0 0 var(--research-space-1);color:var(--research-text-secondary);font-size:var(--research-text-xs)}.settings__panel-heading h2{margin:0;font-size:var(--research-text-section-title)}.settings__panel-heading>span{padding:var(--research-space-1) var(--research-space-2);border-radius:var(--research-radius-pill);background:var(--research-bg-hover);color:var(--research-text-secondary);font-size:var(--research-text-xs)}
.settings__heading-actions{display:flex;align-items:center;justify-content:flex-end;gap:var(--research-space-2)}.settings__heading-actions>span{padding:var(--research-space-1) var(--research-space-2);border-radius:var(--research-radius-pill);background:var(--research-bg-hover);color:var(--research-text-secondary);font-size:var(--research-text-xs)}.settings__providers,.settings__keys{display:grid;gap:var(--research-space-4)}.settings__provider,.settings__key-card{min-width:0;padding:var(--research-space-4);border:1px solid var(--research-border-subtle);border-radius:var(--research-radius-card);background:var(--research-bg-panel)}.settings__provider>header,.settings__key-card>div:first-child{display:flex;align-items:center;justify-content:space-between;gap:var(--research-space-3)}.settings__provider>header>div:first-child{display:flex;align-items:center;gap:var(--research-space-3)}.settings__provider h3,.settings__key-card h3,.settings__notice h3,.settings__danger h3{margin:0;font-size:var(--research-text-card-title)}.settings__provider header p{margin:var(--research-space-1) 0 0;color:var(--research-text-secondary);font-size:var(--research-text-xs)}.settings__statuses{display:flex;flex-wrap:wrap;justify-content:flex-end;gap:var(--research-space-1)}.settings__form-grid{display:grid;grid-template-columns:minmax(90px,.22fr) minmax(0,1fr);align-items:center;gap:var(--research-space-3);margin-block:var(--research-space-4)}.settings label{color:var(--research-text-secondary);font-size:var(--research-text-sm);font-weight:var(--research-font-weight-medium)}.settings input{box-sizing:border-box;width:100%;min-width:0;padding:10px 12px;border:1px solid var(--research-border-strong);border-radius:var(--research-radius-input);background:var(--research-bg-card);color:var(--research-text-primary);font:inherit}.settings input:disabled{cursor:not-allowed;opacity:1;border-color:var(--research-border-strong);background:var(--research-bg-hover);color:var(--research-text-secondary)}.settings__provider-actions{display:flex;justify-content:flex-end;gap:var(--research-space-2)}.settings__primary,.settings__secondary{display:inline-flex;align-items:center;justify-content:center;gap:var(--research-space-2);padding:9px 14px;border-radius:var(--research-radius-button);font:inherit;font-weight:var(--research-font-weight-semibold);cursor:pointer}.settings__primary{border:1px solid var(--research-primary-600);background:var(--research-primary-600);color:var(--research-text-inverse)}.settings__secondary{border:1px solid var(--research-border-strong);background:var(--research-bg-card);color:var(--research-text-primary)}.settings button:disabled{cursor:not-allowed;opacity:1;border-color:var(--research-border-strong);background:var(--research-bg-hover);color:var(--research-text-secondary);box-shadow:none}.settings__inline-error{display:flex;align-items:center;justify-content:space-between;gap:var(--research-space-3);margin-block-start:var(--research-space-3);padding:var(--research-space-3);border:1px solid var(--research-danger-100);border-radius:var(--research-radius-button);background:var(--research-danger-50);color:var(--research-danger-600);font-size:var(--research-text-sm)}.settings__inline-error button{border:0;background:transparent;color:inherit;font:inherit;font-weight:var(--research-font-weight-semibold);cursor:pointer}.settings__saved{margin:var(--research-space-2) 0 0;color:var(--research-success-700);font-size:var(--research-text-sm)}.settings__retained-error,.settings__uncertain{display:flex;align-items:center;justify-content:space-between;gap:var(--research-space-3);padding:var(--research-space-3);border:1px solid var(--research-danger-100);border-radius:var(--research-radius-button);background:var(--research-danger-50);color:var(--research-danger-600);font-size:var(--research-text-sm)}.settings__retained-error button,.settings__uncertain button{padding:var(--research-space-2) var(--research-space-3);border:1px solid var(--research-danger-500);border-radius:var(--research-radius-button);background:var(--research-bg-card);color:var(--research-danger-600);font:inherit;font-weight:var(--research-font-weight-semibold);cursor:pointer}
.settings__uncertain--global{grid-column:1/-1}.settings__notice{display:flex;align-items:flex-start;gap:var(--research-space-4);padding:var(--research-space-5);border:1px dashed var(--research-border-strong);border-radius:var(--research-radius-card);background:var(--research-bg-panel)}.settings__notice>svg{color:var(--research-primary-600)}.settings__notice p{margin:var(--research-space-2) 0 0;color:var(--research-text-secondary);font-size:var(--research-text-sm);line-height:var(--research-line-height-body)}.settings__key-card label{display:block;margin-block:var(--research-space-4) var(--research-space-2)}.settings__key-input{display:grid!important;grid-template-columns:minmax(0,1fr) auto;gap:var(--research-space-2)}.settings__key-card>p{margin:var(--research-space-3) 0 0;color:var(--research-text-secondary);font-size:var(--research-text-xs);line-height:var(--research-line-height-body)}.settings__danger{margin-block-start:var(--research-space-6);padding:var(--research-space-4);border:1px solid var(--research-danger-100);border-radius:var(--research-radius-card);background:var(--research-danger-50)}.settings__danger>header{display:flex;align-items:flex-start;gap:var(--research-space-3);color:var(--research-danger-600)}.settings__danger header p{margin:var(--research-space-1) 0 0;font-size:var(--research-text-xs)}.settings__danger-row{display:flex;align-items:center;justify-content:space-between;gap:var(--research-space-3);margin-block-start:var(--research-space-3);padding-block-start:var(--research-space-3);border-block-start:1px solid var(--research-danger-100);font-size:var(--research-text-sm)}.settings__danger-row button{padding:8px 12px;border:1px solid var(--research-danger-500);border-radius:var(--research-radius-button);background:var(--research-bg-card);color:var(--research-danger-600);font:inherit;font-weight:var(--research-font-weight-semibold);cursor:pointer}.settings__danger-error{color:var(--research-danger-600);font-size:var(--research-text-sm)}
@media(max-width:1480px){.settings__workspace{grid-template-columns:minmax(180px,.25fr) minmax(0,1fr)}.settings__panel{padding:var(--research-space-4)}}
</style>
