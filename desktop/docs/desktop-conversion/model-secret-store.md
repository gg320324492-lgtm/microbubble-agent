# Model SecretStore + IPC (Phase 6-A2)

> **purpose**: Persist model provider API keys in the Electron main process with OS-level encryption; expose a strict no-secret-leaking IPC surface to the renderer.
> **follows**: Phase 6-A1 (foundation types + interface + normalizer + tests + doc, commit `f7f197447`). Pre-vendor-wiring layer — no real provider connections yet (no MiniMax / Qwen / Mimo / OpenAI / Ollama / vLLM).

## 1. Threat model

The renderer is treated as untrusted:

- Browser-like context: `nodeIntegration: false`, `sandbox: true`, `contextIsolation: true`.
- A renderer compromise (XSS / supply chain attack against a Vue dep) MUST NOT result in plaintext API key exfiltration.

Phase 6-A2 contract (frozen):

| Item | Behavior |
|------|----------|
| raw API key visibility | main process ONLY |
| cipher-text visibility | main process ONLY (renderer never sees cipher) |
| log entries | never include key contents; only providerId + ok/err code |
| invalid `providerId` | rejected at every entry point |
| empty key | rejected at save |
| `safeStorage` unavailable | save throws (no plaintext fallback) |

## 2. Files (Phase 6-A2)

```
desktop/src/main/services/model-provider/
  - model-secret-store.ts   (NEW)  Phase 6-A2 SecretStore
  - vault-compat.ts         (NEW)  safeStorage availability helper
  - model-ipc.ts            (NEW)  Phase 6-A2 IPC handlers

desktop/src/shared/model/
  - model-ipc.ts            (NEW)  Channel name constants (shared between main + preload)

desktop/src/shared/
  - ipc-types.ts            (MODIFY)  +4 model channels (chat:* untouched)
  - preload-api.ts          (MODIFY)  +DesktopModelApi (window.api.model)

desktop/src/preload/
  - index.ts                (MODIFY)  +modelApi bridge (no key echo)

desktop/tests/unit/
  - model-secret-store.test.ts  (NEW)  44 cases (>= 30 spec requirement)

desktop/docs/desktop-conversion/
  - model-secret-store.md       (NEW)  this file
```

## 3. `SecretStore` API (frozen contract)

`desktop/src/main/services/model-provider/model-secret-store.ts`:

| Function | Signature | Behavior |
|----------|-----------|----------|
| `save` | `(providerId, apiKey) => void` | encrypt via `safeStorage.encryptString`, persist base64 cipher via `electron-store`. Throws on invalid input. |
| `exists` | `(providerId) => boolean` | presence check. `false` for invalid id (no throw). |
| `get` | `(providerId) => string \| null` | **INTERNAL USE ONLY** — Phase 6-A3+ main-side provider factories call this. **NEVER** call from IPC handlers exposed to renderer. |
| `deleteKey` | `(providerId) => void` | idempotent; silent no-op for invalid id. |
| `list` | `() => string[]` | providerIds only; never keys. |
| `clearAll` | `() => void` | wipe all stored keys (logout / vault reset). |

### Validation

`isValidProviderId(id)` accepts:

```
^[a-z][a-z0-9-]*$
```

length 2..32 chars. This format mirrors Phase 1-2 token-vault symmetry and rejects SQL/path-traversal chars early.

### Storage shape

`electron-store` with `name: 'model-provider-keys'`. Each entry:

```
model_api_key_<providerId>  =  base64(ciphertext)   // ciphertext = safeStorage.encryptString(key)
```

The `STORAGE_PREFIX` is `'model_api_key_'` — distinct from the auth `refresh_token` prefix, so the two vaults never collide.

## 4. `safeStorage` integration

Reuses the Phase 1-2 `safeStorage.encryptString` / `decryptString` pair.

- **Windows**: DPAPI per-user master key.
- **macOS**: Keychain.
- **Linux**: libsecret (gnome-keyring / KWallet).

If `safeStorage.isEncryptionAvailable()` returns `false`, `save()` throws with explicit remediation. We do NOT fallback to plaintext — better to block save than to leak.

## 5. IPC channel namespace (`model:*`)

| Channel | Direction | Args | Result (renderer-visible) |
|---------|-----------|------|---------------------------|
| `model:list-providers` | renderer → main | (none) | `{ providerIds: string[] }` |
| `model:save-key` | renderer → main | `(providerId, apiKey)` | `{ ok: true, exists: true }` |
| `model:delete-key` | renderer → main | `(providerId)` | `{ ok: true, exists: boolean }` (existed before delete) |
| `model:key-exists` | renderer → main | `(providerId)` | `{ exists: boolean }` |

**Crucial**: NONE of these result types contain the raw API key or the cipher-text. Even the existence boolean is purely metadata.

### Why no `model:get-key` channel?

There is deliberately no IPC channel that returns the key. The key is only needed inside main process when constructing a provider request (Phase 6-A3+). Renderer never needs the plaintext key — the Settings UI shows "configured" / "not configured" via `keyExists`, and the form has a single "save" button that re-enters the key on rotation.

## 6. Preload bridge (`window.api.model`)

```ts
window.api.model.listProviders()        // Promise<{ providerIds: string[] }>
window.api.model.saveKey(id, key)       // Promise<{ ok: true, exists: boolean }>
window.api.model.deleteKey(id)          // Promise<{ ok: true, exists: boolean }>
window.api.model.keyExists(id)          // Promise<{ exists: boolean }>
```

The renderer CANNOT:

- call `ipcRenderer.invoke('model:get-key', id)` (no such channel)
- access `ipcRenderer` instance (not exposed)
- read `safeStorage` (not in renderer process)
- read the `electron-store` JSON file (it's in `userData/` which renderer cannot access)

`contextBridge.exposeInMainWorld` snapshots the bridge at preload time; renderer cannot mutate the exposed object.

## 7. Lifecycle

```
[ProviderPanel.vue (Phase 6-A4)]
   ↓ user types API key in input
   ↓ clicks "Save"
window.api.model.saveKey('openai', 'sk-xxx')
   ↓
preload: ipcRenderer.invoke('model:save-key', 'openai', 'sk-xxx')
   ↓
main: handler validates string args + calls SecretStore.save
   ↓
SecretStore.save:
   - isValidProviderId('openai') -> true
   - safeStorage.isEncryptionAvailable() -> true
   - cipher = safeStorage.encryptString('sk-xxx')
   - electron-store.set('model_api_key_openai', cipher.toString('base64'))
   ↓
renderer: { ok: true, exists: true }  (no key material)
```

Rotation: user re-enters new key in same field → `saveKey` overwrites the cipher.
Removal: user clicks "Remove" → `deleteKey` removes the entry (idempotent).
Logout: `clearAll` wipes all model keys (called by auth logout flow in Phase 6-A4).

## 8. Test coverage (44 / 44 PASSED, exceeds spec >= 30)

`tests/unit/model-secret-store.test.ts`:

| describe | cases |
|----------|-------|
| providerId validation (10 cases) | non-string, empty, length 1, length 33, leading digit, uppercase, underscore, space, valid lowercase+dash, digits-in-middle |
| apiKey validation (3 cases) | non-string, empty, undefined |
| save / exists / get / delete / list / clearAll (10 cases) | save+exists+get roundtrip, overwrite, exists for missing, get for missing, get for invalid id, delete, delete-idempotent, delete-invalid-id, list never returns keys, list empty, clearAll |
| STORAGE_PREFIX / keyFor helpers (2 cases) | constant value, prefix composition |
| IPC `model:list-providers` (2 cases) | empty list, stored ids (no key leakage) |
| IPC `model:save-key` (6 cases) | saves ok, response contains no key, bad providerId, bad apiKey, empty id, empty key |
| IPC `model:delete-key` (4 cases) | deletes existing, idempotent missing, response no key, bad providerId |
| IPC `model:key-exists` (4 cases) | stored true, missing false, response no key, bad providerId |
| **Total** | **44** |

Test isolation technique:
- `vi.mock('electron')` provides fake `safeStorage` (in-process cipher) + fake `ipcMain` (handler registry).
- `vi.mock('electron-store')` provides Map-backed store (real electron-store needs `app.getPath('userData')`).
- `vi.mock('../../src/main/services/model-provider/vault-compat')` makes `safeStorageAvailable()` always true.

## 9. Forbidden patterns (permanent)

- ❌ Add a `model:get-key` channel that returns plaintext. (Reason: would defeat the entire purpose of main-process-only keys.)
- ❌ Log key contents anywhere. (Reason: dev tools console / file logs are world-readable.)
- ❌ Fallback to plaintext save when `safeStorage` is unavailable. (Reason: silent downgrade to "open" storage.)
- ❌ Add `model:*` channels that return cipher-text. (Reason: renderer never needs to decrypt — keeps encryption as main-only responsibility.)
- ❌ Store keys in `localStorage` / `sessionStorage` / cookies. (Reason: not encrypted, not OS-protected.)
- ❌ Send keys over `webContents.send` broadcasts. (Reason: broadcast envelope is replayable to all subscribers.)

## 10. Phase 6 Roadmap

| phase | scope | status |
|-------|-------|--------|
| 6-A audit | doc-only design | done (9fbd8d589) |
| 6-A1 foundation | types + interface + normalizer + tests + doc | done (f7f197447) |
| **6-A2 SecretStore + IPC** | main/services/model-provider/secret-store.ts + IPC + preload + tests + doc | **this commit** |
| 6-A3 Registry | vendor factories (MiniMax / Qwen / Mimo / OpenAI / Ollama / vLLM) — uses SecretStore.get() in main | next |
| 6-A4 Settings UI | renderer/views/settings + ProviderPanel.vue — uses window.api.model.{listProviders,saveKey,deleteKey,keyExists} | follow |
| 6-A5 Wiring | chat-stream.service.ts route switch (feature-flagged) | follow |
| 6-A6 E2E | Ollama local e2e + docs | follow |

## 11. References

- `docs/desktop-conversion/model-provider-architecture.md` (Phase 6-A audit, 9fbd8d589)
- `docs/desktop-conversion/model-provider-foundation.md` (Phase 6-A1, f7f197447)
- `docs/desktop-conversion/security.md` (token storage principles — apply to model keys)

## Status (2026-08-22 Phase 6-A2)

- 1 SecretStore (safeStorage + electron-store)
- 1 vault-compat helper
- 1 IPC handler module (4 channels)
- preload bridge updated (window.api.model)
- 44 unit tests PASSED (exceeds spec >= 30)
- No real provider connections
- No chat:* IPC changes
- Doc complete (11 sections)
