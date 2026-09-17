// 命令注册表契约（M4）— 注册/过滤（标题/关键词/拼音首字母）/执行/注销。纯逻辑零依赖。
import { describe, expect, it, vi } from 'vitest'
import { CommandRegistry } from '@shared/command-registry'

function make(): CommandRegistry {
  const r = new CommandRegistry()
  r.register({ id: 'nav-eln', title: '实验 ELN', keywords: 'sy shiyan eln', action: () => undefined })
  r.register({ id: 'nav-knowledge', title: '知识库', keywords: 'zsk zhishi knowledge', action: () => undefined })
  r.register({ id: 'quit', title: '退出应用', keywords: 'tc tuichu quit exit', action: () => undefined })
  return r
}

describe('CommandRegistry', () => {
  it('注册 + 列表 — 按注册顺序返回全部', () => {
    const r = make()
    expect(r.list()).toHaveLength(3)
    expect(r.list().map((c) => c.id)).toEqual(['nav-eln', 'nav-knowledge', 'quit'])
  })

  it('注册重复 id 抛错；空 id 抛错', () => {
    const r = make()
    expect(() => r.register({ id: 'quit', title: '重复', action: () => undefined })).toThrow('已注册')
    expect(() => r.register({ id: '', title: '空', action: () => undefined })).toThrow('不能为空')
  })

  it('过滤 — 标题子串大小写不敏感', () => {
    const r = make()
    expect(r.filter('退出').map((c) => c.id)).toEqual(['quit'])
    expect(r.filter('eln').map((c) => c.id)).toEqual(['nav-eln'])
  })

  it('过滤 — keywords 子串与拼音首字母前缀', () => {
    const r = make()
    expect(r.filter('sy').map((c) => c.id)).toEqual(['nav-eln']) // 拼音首字母 'sy' 前缀
    expect(r.filter('zhishi').map((c) => c.id)).toEqual(['nav-knowledge'])
    expect(r.filter('exit').map((c) => c.id)).toEqual(['quit'])
  })

  it('过滤空查询返回全部', () => {
    const r = make()
    expect(r.filter('')).toHaveLength(3)
    expect(r.filter('  ')).toHaveLength(3)
  })

  it('execute — 执行回调并返回 true；未知 id 返回 false', () => {
    const r = new CommandRegistry()
    const action = vi.fn()
    r.register({ id: 'a', title: 'A', action })
    expect(r.execute('a')).toBe(true)
    expect(action).toHaveBeenCalledTimes(1)
    expect(r.execute('nope')).toBe(false)
  })

  it('unregister — 注销后 execute 返回 false、filter 不再包含', () => {
    const r = make()
    expect(r.unregister('quit')).toBe(true)
    expect(r.execute('quit')).toBe(false)
    expect(r.filter('退出')).toHaveLength(0)
    expect(r.unregister('quit')).toBe(false) // 二次注销 false
  })
})
