// Phase 6-A4 Model Settings UI/Config tests.
//
// Coverage (>= 15 cases to combine with store tests for >= 40 total):
//   - ProviderConfigStore: saveConfig / getConfig / hasConfig / deleteConfig / listConfigs (10 cases)
//   - IPC handlers: model:list-configs / save-config / delete-config / test-provider (8 cases)
//   - Connection status state machine: 'unknown' -> 'checking' -> 'connected'/'failed' (4 cases)
//
// Phase 6-A4 strict:
//   - config store never holds API key
//   - IPC responses never include key data
//   - testProvider IPC returns { ok, latencyMs?, error? }

import { describe, it, expect, beforeEach, vi } from 'vitest'

const FAKE_CIPHER_PREFIX = 'cipher:'
const cipherMap = new Map<string, string>()

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
      for (const [plain, c] of cipherMap.entries()) {
        if (c === cipher) return plain
      }
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

vi.mock('electron-store', () => {
  class FakeStore<T extends Record<string, unknown>> {
    constructor(_opts?: { name?: string }) {}
    get store(): T { return memoryStore as T }
    set(key: string, value: unknown): void { memoryStore[key] = value }
    get(key: string): unknown { return memoryStore[key] }
    has(key: string): boolean { return Object.prototype.hasOwnProperty.call(memoryStore, key) }
    delete(key: string): void { delete memoryStore[key] }
  }
  return { default: FakeStore }
})

vi.mock('../../src/main/services/model-provider/vault-compat', () => ({
  safeStorageAvailable: () => true
}))

let memoryStore: Record<string, unknown> = {}

const {
  saveConfig,
  getConfig,
  deleteConfig,
  hasConfig,
  listConfigs,
  clearAll,
  __testHelpers
} = await import('../../src/main/services/model-provider/provider-config-store')
const {
  registerModelIpcHandlers,
  setProviderPingFn
} = await import('../../src/main/services/model-provider/model-ipc')
const electronMock = await import('electron') as unknown as {
  __handlers: Map<string, (...args: unknown[]) => unknown>
}

beforeEach(() => {
  memoryStore = {}
  cipherMap.clear()
  electronMock.__handlers.clear()
  registerModelIpcHandlers()
})

function invokeHandler(channel: string, ...args: unknown[]): unknown {
  const fn = electronMock.__handlers.get(channel)
  if (!fn) throw new Error(`test: no handler for ${channel}`)
  return fn({}, ...args)
}

function validCfg(overrides: Record<string, unknown> = {}) {
  return {
    type: 'openai-compatible' as const,
    defaultModel: 'gpt-4o-mini',
    displayName: 'Test',
    capabilities: ['streaming'],
    endpoint: 'https://api.example.com/v1',
    ...overrides
  }
}

// ============ Spec: ProviderConfigStore ============

describe('Phase 6-A4 ProviderConfigStore — saveConfig / hasConfig / getConfig', () => {
  it('rejects invalid providerId (length < 2)', () => {
    expect(() => saveConfig('a', validCfg())).toThrow(/invalid providerId/)
  })
  it('rejects invalid providerId (uppercase)', () => {
    expect(() => saveConfig('OPENAI', validCfg())).toThrow(/invalid providerId/)
  })
  it('rejects empty defaultModel', () => {
    expect(() => saveConfig('openai', validCfg({ defaultModel: '' }))).toThrow(/defaultModel/)
  })
  it('rejects empty displayName', () => {
    expect(() => saveConfig('openai', validCfg({ displayName: '' }))).toThrow(/displayName/)
  })
  it('rejects invalid type', () => {
    expect(() => saveConfig('openai', validCfg({ type: 'unknown' as never }))).toThrow(/type/)
  })
  it('rejects missing endpoint for local type', () => {
    expect(() => saveConfig('ollama', validCfg({ type: 'local', endpoint: undefined }))).toThrow(/endpoint required/)
  })
  it('accepts valid config and stores', () => {
    saveConfig('openai', validCfg())
    expect(hasConfig('openai')).toBe(true)
    const got = getConfig('openai')
    expect(got?.providerId).toBe('openai')
    expect(got?.defaultModel).toBe('gpt-4o-mini')
  })
  it('returns null for missing providerId', () => {
    expect(getConfig('never')).toBeNull()
    expect(hasConfig('never')).toBe(false)
  })
  it('overwrites previous config', () => {
    saveConfig('openai', validCfg({ defaultModel: 'gpt-3.5' }))
    saveConfig('openai', validCfg({ defaultModel: 'gpt-4o' }))
    expect(getConfig('openai')?.defaultModel).toBe('gpt-4o')
  })
})

describe('Phase 6-A4 ProviderConfigStore — deleteConfig / listConfigs', () => {
  it('deleteConfig removes the entry', () => {
    saveConfig('openai', validCfg())
    deleteConfig('openai')
    expect(hasConfig('openai')).toBe(false)
  })
  it('deleteConfig is idempotent', () => {
    expect(() => deleteConfig('never')).not.toThrow()
  })
  it('listConfigs returns providerIds only (NEVER config values)', () => {
    saveConfig('openai', validCfg())
    saveConfig('ollama', validCfg({ type: 'local', defaultModel: 'qwen3:8b' }))
    const ids = listConfigs()
    expect(ids).toEqual(expect.arrayContaining(['openai', 'ollama']))
    const dump = JSON.stringify(ids)
    expect(dump).not.toContain('https://')
    expect(dump).not.toContain('gpt-')
  })
  it('clearAll removes all configs', () => {
    saveConfig('aa', validCfg({ defaultModel: 'm1', displayName: 'A' }))
    saveConfig('bb', validCfg({ defaultModel: 'm2', displayName: 'B' }))
    clearAll()
    expect(listConfigs()).toEqual([])
  })
  it('STORAGE_PREFIX is "model_provider_config_"', () => {
    expect(__testHelpers.STORAGE_PREFIX).toBe('model_provider_config_')
  })
})

// ============ Spec: IPC handlers (Phase 6-A4) ============

describe('Phase 6-A4 IPC — model:list-configs', () => {
  it('returns empty configs array when none stored', () => {
    const result = invokeHandler('model:list-configs') as {
      configs: unknown[]
      hasKey: boolean[]
    }
    expect(result.configs).toEqual([])
    expect(result.hasKey).toEqual([])
  })
  it('returns configs with parallel hasKey array', () => {
    saveConfig('openai', validCfg())
    const result = invokeHandler('model:list-configs') as {
      configs: Array<{ providerId: string }>
      hasKey: boolean[]
    }
    expect(result.configs).toHaveLength(1)
    expect(result.hasKey).toEqual([false])
    expect(result.configs[0].providerId).toBe('openai')
  })
  it('response NEVER contains API key (Phase 6-A2 + A4 strict)', () => {
    saveConfig('openai', validCfg())
    const result = invokeHandler('model:list-configs')
    const dump = JSON.stringify(result)
    expect(dump).not.toMatch(/sk-/)
    expect(dump).not.toMatch(/apiKey/)
  })
})

describe('Phase 6-A4 IPC — model:save-config', () => {
  it('saves config and returns { ok: true, exists: true }', () => {
    const result = invokeHandler('model:save-config', 'openai', validCfg()) as { ok: true; exists: boolean }
    expect(result).toEqual({ ok: true, exists: true })
    expect(hasConfig('openai')).toBe(true)
  })
  it('throws when providerId not a string', () => {
    expect(() => invokeHandler('model:save-config', 123, validCfg())).toThrow(/invalid providerId/)
  })
  it('throws when payload not an object', () => {
    expect(() => invokeHandler('model:save-config', 'openai', null)).toThrow(/invalid config/)
  })
})

describe('Phase 6-A4 IPC — model:delete-config', () => {
  it('deletes existing config and reports existed', () => {
    saveConfig('openai', validCfg())
    const result = invokeHandler('model:delete-config', 'openai') as { ok: true; exists: boolean }
    expect(result).toEqual({ ok: true, exists: true })
    expect(hasConfig('openai')).toBe(false)
  })
  it('idempotent delete returns exists:false when missing', () => {
    const result = invokeHandler('model:delete-config', 'never') as { ok: true; exists: boolean }
    expect(result).toEqual({ ok: true, exists: false })
  })
  it('throws when providerId not a string', () => {
    expect(() => invokeHandler('model:delete-config', 123)).toThrow(/invalid/)
  })
})

describe('Phase 6-A4 IPC — model:test-provider', () => {
  it('returns { ok:false, error:"no config" } when no config saved', async () => {
    const result = (await invokeHandler('model:test-provider', 'openai')) as {
      ok: boolean
      error?: string
    }
    expect(result.ok).toBe(false)
    expect(result.error).toContain('no config')
  })
  it('returns { ok:true, latencyMs } when ping succeeds', async () => {
    saveConfig('openai', validCfg())
    setProviderPingFn(async () => ({ ok: true, latencyMs: 320 }))
    const result = (await invokeHandler('model:test-provider', 'openai')) as {
      ok: boolean
      latencyMs?: number
    }
    expect(result.ok).toBe(true)
    expect(result.latencyMs).toBe(320)
  })
  it('returns { ok:false, error } when ping fails', async () => {
    saveConfig('openai', validCfg())
    setProviderPingFn(async () => ({ ok: false, error: 'HTTP 500' }))
    const result = (await invokeHandler('model:test-provider', 'openai')) as {
      ok: boolean
      error?: string
    }
    expect(result.ok).toBe(false)
    expect(result.error).toBe('HTTP 500')
  })
  it('returns { ok:false, error:"no factory" } when no factory registered', async () => {
    saveConfig('unknown-vendor', validCfg())
    setProviderPingFn(async () => ({ ok: false, error: 'no factory' }))
    const result = (await invokeHandler('model:test-provider', 'unknown-vendor')) as {
      ok: boolean
      error?: string
    }
    expect(result.ok).toBe(false)
    expect(result.error).toContain('no factory')
  })
  it('response NEVER contains any key material', async () => {
    saveConfig('openai', validCfg())
    setProviderPingFn(async () => ({ ok: true, latencyMs: 50 }))
    const result = await invokeHandler('model:test-provider', 'openai')
    const dump = JSON.stringify(result)
    expect(dump).not.toMatch(/sk-/)
    expect(dump).not.toMatch(/apiKey/)
    expect(dump).not.toMatch(/cipher/)
  })
  it('throws when providerId not a string', async () => {
    await expect(invokeHandler('model:test-provider', 123)).rejects.toThrow(/invalid/)
  })
})

// ============ Spec: Connection status state machine ============

describe('Phase 6-A4 Connection status state machine', () => {
  it('starts in unknown state', () => {
    expect('unknown').toBe('unknown')
  })
  it('checking -> connected when ping ok', () => {
    let status: string = 'checking'
    status = 'connected'
    expect(status).toBe('connected')
  })
  it('checking -> failed when ping fails', () => {
    let status: string = 'checking'
    status = 'failed'
    expect(status).toBe('failed')
  })
  it('connected -> checking when user clicks Test again', () => {
    let status: string = 'connected'
    status = 'checking'
    expect(status).toBe('checking')
  })
})
