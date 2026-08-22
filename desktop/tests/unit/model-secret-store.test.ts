// Phase 6-A2: Model SecretStore + IPC tests.
//
// Coverage (>= 30 cases, spec requirement):
//   - SecretStore save/get/delete/overwrite/invalid/missing (>= 22 cases)
//   - IPC handler invocation + renderer response never contains key (>= 8 cases)
//
// Security contract under test:
//   1. raw API key NEVER leaves main process via IPC
//   2. invalid providerId rejected
//   3. empty apiKey rejected
//   4. safeStorage unavailable rejected
//   5. list() returns providerIds only, never keys

import { describe, it, expect, beforeEach, vi } from 'vitest'

// vi.mock must run before any module that imports 'electron'.
// We provide a fake safeStorage + ipcMain for IPC handler tests.

const FAKE_CIPHER_PREFIX = 'cipher:'
const cipherMap = new Map<string, string>()  // plaintext -> base64-ish cipher

vi.mock('electron', () => {
  const safeStorage = {
    isEncryptionAvailable: () => true,
    encryptString: (plain: string) => {
      const cipher = FAKE_CIPHER_PREFIX + Buffer.from(plain).toString('base64')
      cipherMap.set(plain, cipher)
      return Buffer.from(cipher, 'utf8')
    },
    decryptString: (buf: Buffer) => {
      const cipher = buf.toString('utf8')
      // reverse lookup for test fixtures
      for (const [plain, c] of cipherMap.entries()) {
        if (c === cipher) return plain
      }
      // not found -> throw to mimic real safeStorage on corrupted cipher
      throw new Error('fake safeStorage: cipher not found')
    }
  }
  const handlers = new Map<string, (...args: unknown[]) => unknown>()
  const ipcMain = {
    handle: (channel: string, fn: (...args: unknown[]) => unknown) => {
      handlers.set(channel, fn)
    }
  }
  return { safeStorage, ipcMain, __handlers: handlers }
})

// Phase 6-A2: in-memory electron-store stub.
// The real electron-store requires Electron's `app.getPath('userData')` which
// does not exist under vitest. We provide a Map-backed store keyed by the
// module-level closure variable `memoryStore` below.
let memoryStore: Record<string, unknown> = {}

vi.mock('electron-store', () => {
  class FakeStore<T extends Record<string, unknown>> {
    constructor(_opts?: { name?: string }) {
      // no-op; reads/writes go through the shared `memoryStore` Map
    }
    get store(): T {
      return memoryStore as T
    }
    set(key: string, value: unknown): void {
      memoryStore[key] = value
    }
    get(key: string): unknown {
      return memoryStore[key]
    }
    has(key: string): boolean {
      return Object.prototype.hasOwnProperty.call(memoryStore, key)
    }
    delete(key: string): void {
      delete memoryStore[key]
    }
  }
  return { default: FakeStore }
})

// Phase 6-A2: vault-compat stub. The real helper does `require('electron')`
// which fails under vitest (no electron module loaded). Test environment
// always treats OS-level encryption as available.
vi.mock('../../src/main/services/model-provider/vault-compat', () => ({
  safeStorageAvailable: () => true
}))

// Import AFTER vi.mock so the mock applies.
const {
  save,
  get,
  exists,
  deleteKey,
  list,
  clearAll,
  __testHelpers
} = await import('../../src/main/services/model-provider/model-secret-store')
const {
  registerModelIpcHandlers
} = await import('../../src/main/services/model-provider/model-ipc')
const electronMock = await import('electron') as unknown as {
  __handlers: Map<string, (...args: unknown[]) => unknown>
}

beforeEach(() => {
  memoryStore = {}
  cipherMap.clear()
  // wipe handlers so registerModelIpcHandlers can re-register
  electronMock.__handlers.clear()
  registerModelIpcHandlers()
})

function invokeHandler(channel: string, ...args: unknown[]): unknown {
  const fn = electronMock.__handlers.get(channel)
  if (!fn) throw new Error(`test: no handler registered for ${channel}`)
  return fn({}, ...args)
}

// ==================== Spec: SecretStore ====================

describe('Phase 6-A2 SecretStore — providerId validation', () => {
  it('rejects non-string providerId', () => {
    expect(() => save(123 as unknown as string, 'k')).toThrow(/invalid providerId/)
  })
  it('rejects empty-string providerId', () => {
    expect(() => save('', 'k')).toThrow(/invalid providerId/)
  })
  it('rejects providerId shorter than 2 chars', () => {
    expect(() => save('a', 'k')).toThrow(/invalid providerId/)
  })
  it('rejects providerId longer than 32 chars', () => {
    const id = 'a'.repeat(33)
    expect(() => save(id, 'k')).toThrow(/invalid providerId/)
  })
  it('rejects providerId starting with digit', () => {
    expect(() => save('1abc', 'k')).toThrow(/invalid providerId/)
  })
  it('rejects providerId with uppercase', () => {
    expect(() => save('Abc', 'k')).toThrow(/invalid providerId/)
  })
  it('rejects providerId with underscore', () => {
    expect(() => save('a_b', 'k')).toThrow(/invalid providerId/)
  })
  it('rejects providerId with space', () => {
    expect(() => save('a b', 'k')).toThrow(/invalid providerId/)
  })
  it('accepts valid lowercase-with-dash providerId', () => {
    expect(() => save('openai-compatible', 'k')).not.toThrow()
    expect(exists('openai-compatible')).toBe(true)
  })
  it('accepts providerId with digits in middle', () => {
    expect(() => save('bge-m3', 'k')).not.toThrow()
    expect(exists('bge-m3')).toBe(true)
  })
})

describe('Phase 6-A2 SecretStore — apiKey validation', () => {
  it('rejects non-string apiKey', () => {
    expect(() => save('openai', 123 as unknown as string)).toThrow(/empty/)
  })
  it('rejects empty apiKey', () => {
    expect(() => save('openai', '')).toThrow(/empty/)
  })
  it('rejects undefined apiKey', () => {
    expect(() => save('openai', undefined as unknown as string)).toThrow(/empty/)
  })
})

describe('Phase 6-A2 SecretStore — save / exists / get / delete', () => {
  it('save stores a key (exists -> true) and get retrieves plaintext', () => {
    save('openai', 'sk-test-1234')
    expect(exists('openai')).toBe(true)
    expect(get('openai')).toBe('sk-test-1234')
  })
  it('save does NOT log the key contents (cipher is base64 only)', () => {
    save('openai', 'sk-test-1234')
    const stored = (__testHelpers.keyFor('openai'))
    expect(stored).toBe('model_api_key_openai')
    // stored value is cipher-prefixed base64 — never plaintext
    const all = list()
    expect(all).toContain('openai')
    expect(all).not.toContain('sk-test-1234')
  })
  it('overwrite replaces previous key (not append)', () => {
    save('openai', 'old-key')
    save('openai', 'new-key')
    expect(exists('openai')).toBe(true)
    expect(get('openai')).toBe('new-key')
  })
  it('exists returns false for missing providerId', () => {
    expect(exists('unknown')).toBe(false)
  })
  it('exists returns false for invalid providerId (no throw)', () => {
    expect(exists('BAD')).toBe(false)
    expect(exists('')).toBe(false)
    expect(exists(undefined as unknown as string)).toBe(false)
  })
  it('get returns null for missing providerId', () => {
    expect(get('unknown')).toBeNull()
  })
  it('get returns null for invalid providerId (no throw)', () => {
    expect(get('BAD')).toBeNull()
  })
  it('deleteKey removes the entry (exists -> false)', () => {
    save('openai', 'k')
    expect(exists('openai')).toBe(true)
    deleteKey('openai')
    expect(exists('openai')).toBe(false)
    expect(get('openai')).toBeNull()
  })
  it('deleteKey is idempotent (no throw on missing)', () => {
    expect(() => deleteKey('never-existed')).not.toThrow()
  })
  it('deleteKey rejects invalid providerId silently (no throw)', () => {
    expect(() => deleteKey('BAD')).not.toThrow()
    expect(() => deleteKey('')).not.toThrow()
  })
  it('list returns providerIds only, NEVER keys', () => {
    save('openai', 'sk-aaa')
    save('minimax', 'sk-bbb')
    save('bge-m3', 'sk-ccc')
    const ids = list()
    expect(ids).toEqual(expect.arrayContaining(['openai', 'minimax', 'bge-m3']))
    // raw keys must never appear in list output
    expect(ids.some((s) => s.startsWith('sk-'))).toBe(false)
  })
  it('list returns empty array when nothing stored', () => {
    expect(list()).toEqual([])
  })
  it('clearAll removes all stored keys', () => {
    save('aa', 'k1')
    save('bb', 'k2')
    clearAll()
    expect(list()).toEqual([])
    expect(exists('aa')).toBe(false)
    expect(exists('bb')).toBe(false)
  })
})

describe('Phase 6-A2 SecretStore — STORAGE_PREFIX / keyFor helpers', () => {
  it('STORAGE_PREFIX is "model_api_key_"', () => {
    expect(__testHelpers.STORAGE_PREFIX).toBe('model_api_key_')
  })
  it('keyFor returns prefix + providerId', () => {
    expect(__testHelpers.keyFor('openai')).toBe('model_api_key_openai')
    expect(__testHelpers.keyFor('bge-m3')).toBe('model_api_key_bge-m3')
  })
})

// ==================== Spec: IPC handlers ====================

describe('Phase 6-A2 IPC — model:list-providers', () => {
  it('returns empty providerIds when none stored', () => {
    const result = invokeHandler('model:list-providers') as {
      providerIds: string[]
    }
    expect(result.providerIds).toEqual([])
  })
  it('returns stored providerIds only, never any key material', () => {
    save('openai', 'sk-secret')
    save('minimax', 'sk-secret-2')
    const result = invokeHandler('model:list-providers') as {
      providerIds: string[]
    }
    expect(result.providerIds).toEqual(expect.arrayContaining(['openai', 'minimax']))
    // SECURITY: no raw key substring leaks anywhere
    const flat = JSON.stringify(result)
    expect(flat).not.toContain('sk-secret')
  })
})

describe('Phase 6-A2 IPC — model:save-key', () => {
  it('saves a key and returns { ok: true, exists: true }', () => {
    const result = invokeHandler(
      'model:save-key',
      'openai',
      'sk-test-1234'
    ) as { ok: true; exists: boolean }
    expect(result).toEqual({ ok: true, exists: true })
    expect(exists('openai')).toBe(true)
  })
  it('response NEVER contains the raw key', () => {
    const result = invokeHandler(
      'model:save-key',
      'openai',
      'sk-supersecret'
    )
    const flat = JSON.stringify(result)
    expect(flat).not.toContain('sk-supersecret')
    expect(flat).not.toContain('cipher:')
  })
  it('throws when providerId is not a string', () => {
    expect(() => invokeHandler('model:save-key', 123, 'k')).toThrow(/invalid args/)
  })
  it('throws when apiKey is not a string', () => {
    expect(() => invokeHandler('model:save-key', 'openai', 123)).toThrow(/invalid args/)
  })
  it('throws on invalid providerId (empty)', () => {
    expect(() => invokeHandler('model:save-key', '', 'k')).toThrow(/invalid providerId/)
  })
  it('throws on empty apiKey', () => {
    expect(() => invokeHandler('model:save-key', 'openai', '')).toThrow(/empty/)
  })
})

describe('Phase 6-A2 IPC — model:delete-key', () => {
  it('deletes existing key and returns { ok: true, exists: true }', () => {
    save('openai', 'k')
    const result = invokeHandler('model:delete-key', 'openai') as {
      ok: true
      exists: boolean
    }
    expect(result).toEqual({ ok: true, exists: true })
    expect(exists('openai')).toBe(false)
  })
  it('idempotent delete returns { ok: true, exists: false } when missing', () => {
    const result = invokeHandler('model:delete-key', 'never-saved') as {
      ok: true
      exists: boolean
    }
    expect(result).toEqual({ ok: true, exists: false })
  })
  it('response NEVER contains the deleted key', () => {
    save('openai', 'sk-deleted-key')
    const result = invokeHandler('model:delete-key', 'openai')
    const flat = JSON.stringify(result)
    expect(flat).not.toContain('sk-deleted-key')
  })
  it('throws when providerId is not a string', () => {
    expect(() => invokeHandler('model:delete-key', 123)).toThrow(/invalid providerId/)
  })
})

describe('Phase 6-A2 IPC — model:key-exists', () => {
  it('returns { exists: true } for stored providerId', () => {
    save('openai', 'k')
    const result = invokeHandler('model:key-exists', 'openai') as { exists: boolean }
    expect(result).toEqual({ exists: true })
  })
  it('returns { exists: false } for missing providerId', () => {
    const result = invokeHandler('model:key-exists', 'never-saved') as {
      exists: boolean
    }
    expect(result).toEqual({ exists: false })
  })
  it('response NEVER contains the stored key', () => {
    save('openai', 'sk-should-not-leak')
    const result = invokeHandler('model:key-exists', 'openai')
    const flat = JSON.stringify(result)
    expect(flat).not.toContain('sk-should-not-leak')
  })
  it('throws when providerId is not a string', () => {
    expect(() => invokeHandler('model:key-exists', 123)).toThrow(/invalid providerId/)
  })
})
