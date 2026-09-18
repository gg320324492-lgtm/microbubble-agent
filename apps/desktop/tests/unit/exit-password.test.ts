// M6-2 清账③ — backup.exitPassword 迁移 safeStorage（离线，cipher 注入）
import { describe, expect, it } from 'vitest'
import {
  EXIT_PASSWORD_ENC_KEY,
  EXIT_PASSWORD_KEY,
  SECRET_MASK,
  maskSecret,
  planExitPasswordMigration,
  planExitPasswordWrite,
  resolveExitPassword
} from '@main/services/backup/exit-password'

/** 可逆的假 cipher：enc:<base64>，用于断言"落盘的不是明文" */
const cipher = {
  encrypt: (s: string) => `enc:${Buffer.from(s, 'utf8').toString('base64')}`,
  decrypt: (c: string) => {
    if (!c.startsWith('enc:')) return null
    try {
      return Buffer.from(c.slice(4), 'base64').toString('utf8')
    } catch {
      return null
    }
  }
}

describe('exitPassword 迁移 — 旧明文 → 加密 → 清明文', () => {
  it('有旧明文且无加密值 → 产出密文并要求清明文', () => {
    const plan = planExitPasswordMigration({ legacyPlaintext: 'p@ssw0rd', encrypted: null, cipher })
    expect(plan.encrypted).toBe(cipher.encrypt('p@ssw0rd'))
    expect(plan.encrypted).not.toBe('p@ssw0rd')
    expect(plan.encrypted?.startsWith('enc:')).toBe(true)
    expect(plan.clearPlaintext).toBe(true)
  })

  it('无旧值（全新安装）→ 不写入任何东西', () => {
    expect(planExitPasswordMigration({ legacyPlaintext: null, encrypted: null, cipher })).toEqual({
      encrypted: null,
      clearPlaintext: false
    })
    expect(planExitPasswordMigration({ legacyPlaintext: undefined, encrypted: undefined, cipher })).toEqual({
      encrypted: null,
      clearPlaintext: false
    })
    expect(planExitPasswordMigration({ legacyPlaintext: '', encrypted: null, cipher })).toEqual({
      encrypted: null,
      clearPlaintext: false
    })
  })

  it('已有加密值 → 幂等不重复加密；仅清理残留明文', () => {
    const existing = cipher.encrypt('keep-me')
    expect(planExitPasswordMigration({ legacyPlaintext: null, encrypted: existing, cipher })).toEqual({
      encrypted: existing,
      clearPlaintext: false
    })
    expect(planExitPasswordMigration({ legacyPlaintext: 'stale', encrypted: existing, cipher })).toEqual({
      encrypted: existing,
      clearPlaintext: true
    })
  })
})

describe('exitPassword 读取与回显', () => {
  it('优先解密加密值；加密值解不开且无旧明文时视为无密码', () => {
    expect(resolveExitPassword({ legacyPlaintext: null, encrypted: cipher.encrypt('abc'), cipher })).toEqual({
      password: 'abc',
      needsMigration: false
    })
    // 密文损坏（换机/DPAPI 失效）
    expect(resolveExitPassword({ legacyPlaintext: null, encrypted: 'broken', cipher })).toEqual({
      password: null,
      needsMigration: false
    })
    // 密文损坏但有旧明文 → 用旧明文并提示迁移
    expect(resolveExitPassword({ legacyPlaintext: 'legacy', encrypted: 'broken', cipher })).toEqual({
      password: 'legacy',
      needsMigration: true
    })
  })

  it('写入路径：明文即刻转密文；空串 = 清除', () => {
    const set = planExitPasswordWrite('new-pwd', cipher)
    expect(set.encrypted).toBe(cipher.encrypt('new-pwd'))
    expect(set.clearPlaintext).toBe(true)

    expect(planExitPasswordWrite('', cipher)).toEqual({ encrypted: null, clearPlaintext: true })
    expect(planExitPasswordWrite(null, cipher)).toEqual({ encrypted: null, clearPlaintext: true })
  })

  it('加密值不回显：对外只给掩码，明文/密文都不外泄', () => {
    expect(maskSecret(true)).toBe(SECRET_MASK)
    expect(maskSecret(false)).toBeNull()
    expect(maskSecret(true)).not.toContain('enc:')
    // 键名约定：明文键被清空，密文另存新键
    expect(EXIT_PASSWORD_KEY).toBe('backup.exitPassword')
    expect(EXIT_PASSWORD_ENC_KEY).toBe('backup.exitPasswordEnc')
  })
})
