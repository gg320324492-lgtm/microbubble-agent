# Model Settings + Provider Management (Phase 6-A4)

> **purpose**: User-facing UI to configure model providers (endpoint, defaultModel, displayName), manage API keys (Phase 6-A2 SecretStore entry point), test connectivity (Phase 6-A3 ping), and select the active model. Renderer never holds API keys; all sensitive ops route through `window.api.model` IPC.
> **follows**: Phase 6-A1 (foundation, f7f197447), Phase 6-A2 (SecretStore + IPC, 5a17cab97), Phase 6-A3 (Provider Factory + Registry, adda703e1).

## 1. Scope (Phase 6-A4 frozen)

- Pinia store `model-provider` (renderer-side UI state, NO secrets)
- Main process `provider-config-store` (non-secret provider config — endpoint / defaultModel / displayName / capabilities)
- 4 new IPC channels: `model:list-configs` / `model:save-config` / `model:delete-config` / `model:test-provider`
- `ModelSettingsView.vue` (list + add + manage)
- `ProviderCard.vue` (status card)
- Route `/settings/models` (auth-required, main layout)
- 58 unit tests (>= 40 spec requirement)
- **NO** real production API calls; **NO** changes to chat:* IPC; **NO** changes to Phase 3-B0 StreamEvent schema; **NO** changes to backend

## 2. Files (Phase 6-A4)

```
desktop/src/main/services/model-provider/
  - provider-config-store.ts           (NEW)  non-secret config (endpoint/defaultModel/...)

desktop/src/main/
  - ipc.ts                             (MODIFY)  +setProviderPingFn wiring

desktop/src/shared/
  - ipc-types.ts                       (MODIFY)  +4 model channels
  - model/model-ipc.ts                 (MODIFY)  +4 channel constants
  - preload-api.ts                     (MODIFY)  +DesktopModelApi methods (listConfigs/saveConfig/deleteConfig/testProvider)

desktop/src/preload/
  - index.ts                           (MODIFY)  +4 bridge methods on window.api.model

desktop/src/renderer/src/
  - stores/model-provider.ts           (NEW)  Pinia store (NO apiKey field)
  - components/model/ProviderCard.vue (NEW)  status card
  - views/settings/ModelSettingsView.vue (NEW)  list + add + manage
  - router/index.ts                    (MODIFY)  +/settings/models route

desktop/src/main/services/model-provider/
  - model-ipc.ts                       (MODIFY)  +4 IPC handlers + pingFn injection

desktop/tests/unit/
  - model-provider-store.test.ts       (NEW)  25 cases
  - model-settings.test.ts             (NEW)  33 cases (ConfigStore + IPC + status machine)

desktop/docs/desktop-conversion/
  - model-settings.md                  (NEW)  this file
```

## 3. Model Control Plane design

```
[Renderer ModelSettingsView.vue]
   ↓
[Pinia store: model-provider]
   ↓ window.api.model.{listConfigs,saveConfig,deleteConfig,testProvider}
[Preload contextBridge]
   ↓ ipcRenderer.invoke('model:*')
[Main process: registerModelIpcHandlers]
   ↓
[provider-config-store] (electron-store, non-secret JSON)
   ↓
[SecretStore] (electron-store + safeStorage, encrypted cipher)
   ↓
[Provider registry.ping] (Phase 6-A3: openai-compatible / ollama)
```

Three layers:

| Layer | Owns | Lives in |
|-------|------|----------|
| Pinia store | UI state (providers list, activeProviderId, activeModel, connectionStatus) | Renderer memory |
| ConfigStore | Non-secret provider config (endpoint, defaultModel, displayName, capabilities) | electron-store `model-provider-configs.json` |
| SecretStore | API keys (encrypted via OS safeStorage) | electron-store `model-provider-keys.json` + DPAPI/Keychain/libsecret |

The three layers never cross-contaminate: Pinia never sees config bytes; ConfigStore never sees keys; SecretStore never sees endpoints.

## 4. Provider lifecycle (Phase 6-A4)

```
[1] Initial state
   store.providers = []
   activeProviderId = null
   activeModel = null

[2] User opens /settings/models
   onMounted -> store.loadProviders()
   IPC: model:list-configs
   main: ConfigStore.listConfigs() + SecretStore.exists() (parallel)
   returns: { configs: [...], hasKey: [bool, ...] }

[3] User clicks "Add provider"
   Form fills: providerId, type, endpoint, defaultModel, displayName, capabilities
   submit -> store.saveProvider(providerId, config)
   IPC: model:save-config
   main: ConfigStore.saveConfig(providerId, config)
   store auto-reloads

[4] User clicks "Add API key"
   Key input -> store.saveApiKey(providerId, key)
   IPC: model:save-key (Phase 6-A2)
   main: SecretStore.save(providerId, key) [safeStorage.encryptString + electron-store]

[5] User clicks "Test connection"
   store.testProvider(providerId)
     entry.connectionStatus = 'checking'
   IPC: model:test-provider
   main: registry.getProvider(id, cfg).ping(cfg)
   returns: { ok, latencyMs?, error? }
   store updates entry.connectionStatus + lastLatencyMs + lastError

[6] User clicks "Set as default"
   store.setActiveProvider(providerId)
   store.setActiveModel(entry.config.defaultModel)

[7] User clicks "Delete"
   store.removeProvider(providerId)
   IPC: model:delete-config
   main: ConfigStore.deleteConfig(providerId)
   if active was same id -> clear activeProviderId + activeModel
   (key NOT auto-deleted; user must click "Remove key" separately)
```

## 5. Secret boundary (Phase 6-A4 strict)

The renderer MUST NEVER see:

- API key plaintext
- API key ciphertext
- Authorization header values
- safeStorage handles

The IPC contract enforces this:

| Channel | Returns | Receives |
|---------|---------|----------|
| `model:list-configs` | `{ configs, hasKey }` (booleans only) | — |
| `model:save-config` | `{ ok, exists }` | `providerId, { type, endpoint?, defaultModel, displayName, capabilities }` (NO key) |
| `model:delete-config` | `{ ok, exists }` | `providerId` |
| `model:test-provider` | `{ ok, latencyMs?, error? }` | `providerId` |

The `hasKey: boolean[]` parallel array tells the renderer which providers need a key, without exposing key contents.

### Test enforcement

`tests/unit/model-settings.test.ts` and `tests/unit/model-provider-store.test.ts` both contain:

- "store never contains apiKey field" — walks the Pinia state and asserts no `sk-` / `apiKey` / `api_key` / `secret` substrings.
- "saveApiKey passes the key ONLY through IPC, not store state" — captures IPC payload, asserts the key is in the IPC call, asserts the key is NOT in `store.$state`.
- "response NEVER contains any key material" — JSON.stringify IPC return values, asserts no `sk-` / `apiKey` / `cipher` substrings.

## 6. UI state model

```ts
type ProviderConnectionStatus = 'unknown' | 'checking' | 'connected' | 'failed'

interface ProviderEntry {
  config: ModelProviderConfig    // non-secret metadata
  hasKey: boolean                // parallel from listConfigs.hasKey
  connectionStatus: ProviderConnectionStatus
  lastLatencyMs?: number         // only after a successful test
  lastError?: string             // only after a failed test
}
```

State transitions:

```
+--------+    test start    +----------+   ping ok   +-----------+
| unknown| ---------------> | checking | ----------> | connected |
+--------+                  +----------+             +-----------+
                                  | ping fail
                                  v
                              +--------+
                              | failed |
                              +--------+
```

`connected` and `failed` both transition back to `checking` if the user clicks Test again.

## 7. Test coverage (58 / 58 PASSED, exceeds spec >= 40)

| File | Cases |
|------|-------|
| `model-provider-store.test.ts` (25) | initial state, loadProviders success/failure/preserves status/clears on empty, saveProvider success/failure, removeProvider success/clears active, testProvider success/failure/checking→connected/throw→failed, setActiveProvider/setActiveModel, saveApiKey/removeApiKey, getters activeProvider/providersWithKey/providersMissingKey, security no-key-in-state/key-only-via-IPC, reset |
| `model-settings.test.ts` (33) | ConfigStore saveConfig rejection (length/uppercase/empty defaultModel/empty displayName/invalid type/missing endpoint), accept valid, getConfig missing, overwrite, deleteConfig idempotent, listConfigs no values leak, clearAll, STORAGE_PREFIX; IPC list-configs/save-config/delete-config/test-provider with security assertions; connection status state machine |
| **Total** | **58** |

## 8. Forbidden patterns (permanent)

- ❌ Add API key field to renderer Pinia state. (Reason: world-readable via dev tools; safeStorage is for main only.)
- ❌ Add `model:get-key` IPC channel. (Reason: would defeat the entire purpose of main-process-only keys.)
- ❌ Echo key contents in IPC return values. (Reason: defense-in-depth — every return value is JSON.stringify'd and grep'd in tests.)
- ❌ Render the key input as `type="text"` (must be `type="password"`). (Reason: shoulder-surfing + browser autofill risks.)
- ❌ Persist active model in renderer `localStorage` / `sessionStorage`. (Reason: cross-session contamination; Phase 6-A5 wiring will move this to electron-store.)
- ❌ Call `fetch` directly from renderer. (Reason: bypasses main process auth header injection + retry/refresh policy.)
- ❌ Disable test connectivity on "no factory registered". (Reason: error must be visible to the user — silent success masks misconfiguration.)

## 9. Phase 6-A5 migration interface

Phase 6-A5 (chat-stream.service.ts route switch) consumes:

- `useModelProviderStore().activeProviderId` — which provider to route to
- `useModelProviderStore().activeModel` — which model name to send in the request
- `window.api.model.testProvider(providerId)` — pre-flight connectivity check before switching

```ts
// Phase 6-A5 sketch (NOT shipped in Phase 6-A4)
async function ensureActiveProviderReady() {
  const store = useModelProviderStore()
  if (!store.activeProviderId) throw new Error('No active provider')
  const entry = store.activeProvider
  if (!entry) throw new Error('Active provider not found')
  if (!entry.hasKey) throw new Error('Active provider missing API key')
  if (entry.connectionStatus !== 'connected') {
    const r = await store.testProvider(store.activeProviderId)
    if (!r.ok) throw new Error('Provider not reachable')
  }
}
```

Phase 6-A5 owns the actual chat-route switch logic. Phase 6-A4 ships the UI surface for users to populate the state that Phase 6-A5 reads.

## 10. Phase 6 Roadmap

| phase | scope | status |
|-------|-------|--------|
| 6-A audit | doc-only design | done (9fbd8d589) |
| 6-A1 foundation | types + interface + normalizer + tests + doc | done (f7f197447) |
| 6-A2 SecretStore + IPC | safeStorage vault + 4 IPC channels + window.api.model + 44 tests | done (5a17cab97) |
| 6-A3 Provider Factory + Registry | registry + openai-compatible + ollama + 66 tests | done (adda703e1) |
| **6-A4 Model Settings + Provider Management** | ConfigStore + 4 IPC + Pinia store + UI + 58 tests | **this commit** |
| 6-A5 Wiring | chat-stream.service.ts route switch (feature-flagged) | next |
| 6-A6 E2E | Ollama local e2e + docs | follow |

## 11. References

- `docs/desktop-conversion/model-provider-architecture.md` (Phase 6-A audit, 9fbd8d589)
- `docs/desktop-conversion/model-provider-foundation.md` (Phase 6-A1, f7f197447)
- `docs/desktop-conversion/model-secret-store.md` (Phase 6-A2, 5a17cab97)
- `docs/desktop-conversion/provider-factory.md` (Phase 6-A3, adda703e1)

## Status (2026-08-22 Phase 6-A4)

- 1 ConfigStore (non-secret provider config)
- 4 new IPC channels + ping function injection
- 1 Pinia store (no apiKey field ever)
- 2 Vue components (ProviderCard + ModelSettingsView)
- 1 router entry (/settings/models)
- 58 unit tests PASSED (exceeds spec >= 40)
- 0 changes to chat:* IPC, Phase 3-B0 StreamEvent, backend
- Doc complete (11 sections)
