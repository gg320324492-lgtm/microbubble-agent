// DL-2（合并单）—— 记住账号密码：载荷编解码 + 保存/清除规则（全部离线）
import { describe, expect, it } from 'vitest'
import {
  buildRememberPayload,
  parseRemember,
  serializeRemember,
  shouldClearOnLogout,
  shouldPersistRemember
} from '@main/services/auth/remember'

describe('DL-2 记住账号密码 — 载荷', () => {
  it('★ 往返：构造 → 序列化 → 解析，账号密码一致', () => {
    const built = buildRememberPayload({ username: '  wangtz  ', password: 'p@ss' })
    expect(built).toEqual({ username: 'wangtz', password: 'p@ss' }) // 用户名去空白
    const back = parseRemember(serializeRemember(built!))
    expect(back).toEqual({ username: 'wangtz', password: 'p@ss' })
  })

  it('★ 空用户名不构成有效载荷（返回 null，调用方应清除记录）', () => {
    expect(buildRememberPayload({ username: '', password: 'x' })).toBeNull()
    expect(buildRememberPayload({ username: '   ', password: 'x' })).toBeNull()
    expect(buildRememberPayload({})).toBeNull()
  })

  it('★ 畸形明文一律视为「未记住」（不抛错、不产生半可信凭据）', () => {
    expect(parseRemember(null)).toBeNull()
    expect(parseRemember(undefined)).toBeNull()
    expect(parseRemember('')).toBeNull()
    expect(parseRemember('不是 JSON')).toBeNull()
    expect(parseRemember('{}')).toBeNull()
    expect(parseRemember('{"username":""}')).toBeNull()
    expect(parseRemember('{"username":123}')).toBeNull()
    expect(parseRemember('null')).toBeNull()
    // 密码缺字段 → 补空串（账号仍可用）
    expect(parseRemember('{"username":"a"}')).toEqual({ username: 'a', password: '' })
  })
})

describe('DL-2 记住账号密码 — 保存与清除规则', () => {
  it('★ 勾选 + 载荷有效 + 加密成功 → 保存', () => {
    const payload = buildRememberPayload({ username: 'a', password: 'b' })
    expect(shouldPersistRemember({ remember: true, payload, encrypted: 'ENC:xxx' })).toBe(true)
  })

  it('★ 未勾选 → 不保存（调用方据此清除既有记录）', () => {
    const payload = buildRememberPayload({ username: 'a', password: 'b' })
    expect(shouldPersistRemember({ remember: false, payload, encrypted: 'ENC:xxx' })).toBe(false)
  })

  it('★ 加密不可用（encrypted 为空）→ 不保存 —— 绝不落明文', () => {
    const payload = buildRememberPayload({ username: 'a', password: 'b' })
    expect(shouldPersistRemember({ remember: true, payload, encrypted: null })).toBe(false)
    expect(shouldPersistRemember({ remember: true, payload, encrypted: '' })).toBe(false)
    // 载荷无效时同理
    expect(shouldPersistRemember({ remember: true, payload: null, encrypted: 'ENC:xxx' })).toBe(false)
  })

  it('★ 退出登录即清除（工单要求：下次登录窗不预填）', () => {
    expect(shouldClearOnLogout()).toBe(true)
  })
})
