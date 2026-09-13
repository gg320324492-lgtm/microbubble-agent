// 设置服务契约 — 全局与按用户作用域、JSON 往返
import { describe, expect, it } from 'vitest'
import { openNodeSqlite } from '@main/db/adapters'
import { runMigrations } from '@main/db/migrations'
import { SettingsService } from '@main/services/settings.service'

function makeSettings(): SettingsService {
  const db = openNodeSqlite(':memory:')
  runMigrations(db)
  return new SettingsService(db)
}

describe('SettingsService', () => {
  it('set/get JSON 值往返，未知 key 返回 null', () => {
    const s = makeSettings()
    expect(s.get('nope')).toBeNull()
    s.set('ui.theme', { mode: 'dark', accent: 'coral' })
    expect(s.get('ui.theme')).toEqual({ mode: 'dark', accent: 'coral' })
  })

  it('用户作用域隔离: 同 key 不同 user 互不干扰', () => {
    const s = makeSettings()
    s.set('last.project', 'p-1', 'user-a')
    s.set('last.project', 'p-2', 'user-b')
    expect(s.get('last.project', 'user-a')).toBe('p-1')
    expect(s.get('last.project', 'user-b')).toBe('p-2')
  })

  it('覆盖写入 + null 值可存储', () => {
    const s = makeSettings()
    s.set('k', 1)
    s.set('k', 2)
    expect(s.get('k')).toBe(2)
    s.set('k', null)
    expect(s.get('k')).toBeNull()
  })
})
