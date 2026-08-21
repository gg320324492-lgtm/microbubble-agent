import { describe, it, expect } from 'vitest'
import { LRUCache } from '../../src/renderer/src/utils/lru-cache'

describe('LRUCache 基础 ops', () => {
  it('构造: maxSize 必须正整数', () => {
    expect(() => new LRUCache(0)).toThrow()
    expect(() => new LRUCache(-1)).toThrow()
    expect(() => new LRUCache(1.5)).toThrow()
    expect(() => new LRUCache(NaN)).toThrow()
    expect(() => new LRUCache(Infinity)).toThrow()
    // valid
    expect(() => new LRUCache(1)).not.toThrow()
    expect(() => new LRUCache(100)).not.toThrow()
  })

  it('空 cache: get / size / has', () => {
    const c = new LRUCache<string, number>(3)
    expect(c.size()).toBe(0)
    expect(c.get('a')).toBeUndefined()
    expect(c.has('a')).toBe(false)
    expect(c.keys()).toEqual([])
  })

  it('set / get / has 基础', () => {
    const c = new LRUCache<string, number>(3)
    c.set('a', 1)
    c.set('b', 2)
    expect(c.size()).toBe(2)
    expect(c.get('a')).toBe(1)
    expect(c.get('b')).toBe(2)
    expect(c.get('c')).toBeUndefined()
    expect(c.has('a')).toBe(true)
    expect(c.has('c')).toBe(false)
  })

  it('update 已存在 key 不增长 size', () => {
    const c = new LRUCache<string, number>(3)
    c.set('a', 1)
    c.set('a', 100)
    expect(c.size()).toBe(1)
    expect(c.get('a')).toBe(100)
  })

  it('delete / clear', () => {
    const c = new LRUCache<string, number>(3)
    c.set('a', 1)
    c.set('b', 2)
    expect(c.delete('a')).toBe(true)
    expect(c.has('a')).toBe(false)
    expect(c.size()).toBe(1)
    expect(c.delete('nonexistent')).toBe(false)
    c.clear()
    expect(c.size()).toBe(0)
    expect(c.get('b')).toBeUndefined()
  })
})

describe('LRUCache LRU eviction', () => {
  it('超 maxSize 时淘汰最久未用 (头部)', () => {
    const c = new LRUCache<string, number>(2)
    c.set('a', 1)
    c.set('b', 2)
    c.set('c', 3)  // 触发淘汰 -> a 被踢
    expect(c.size()).toBe(2)
    expect(c.has('a')).toBe(false)
    expect(c.has('b')).toBe(true)
    expect(c.has('c')).toBe(true)
    expect(c.get('b')).toBe(2)
    expect(c.get('c')).toBe(3)
  })

  it('get 命中后 promote 到 MRU (尾部), 推迟淘汰', () => {
    const c = new LRUCache<string, number>(2)
    c.set('a', 1)
    c.set('b', 2)
    // 此时顺序: [a, b] (a 最久)
    c.get('a')  // promote a -> [b, a]
    c.set('c', 3)  // 淘汰 b (现在的头部)
    expect(c.has('a')).toBe(true)
    expect(c.has('b')).toBe(false)
    expect(c.has('c')).toBe(true)
    expect(c.keys()).toEqual(['a', 'c'])  // a (MRU) -> c (新)
  })

  it('update 已存在 key 也 promote', () => {
    const c = new LRUCache<string, number>(2)
    c.set('a', 1)
    c.set('b', 2)
    // [a, b]
    c.set('a', 100)  // promote a -> [b, a]
    c.set('c', 3)  // 淘汰 b
    expect(c.has('a')).toBe(true)
    expect(c.has('b')).toBe(false)
    expect(c.has('c')).toBe(true)
  })

  it('keys() 顺序: 最久 -> 最新', () => {
    const c = new LRUCache<string, number>(5)
    c.set('one', 1)
    c.set('two', 2)
    c.set('three', 3)
    c.get('one')  // promote one: [two, three, one]
    expect(c.keys()).toEqual(['two', 'three', 'one'])
  })

  it('peekOrder (Phase 4-A 测试入口)', () => {
    const c = new LRUCache<string, number>(3)
    c.set('a', 1)
    c.set('b', 2)
    expect(c.peekOrder()).toEqual(['a', 'b'])
  })
})

describe('LRUCache 边界条件', () => {
  it('value 为 undefined (允许但 prompt 警告)', () => {
    const c = new LRUCache<string, number | undefined>(3)
    c.set('a', undefined)
    expect(c.has('a')).toBe(true)
    expect(c.get('a')).toBeUndefined()
  })

  it('null / 0 / false 等 falsy value 正常', () => {
    // maxSize 6 防止任一 entry 被淘汰, 这里只测 falsy value 行为
    const c = new LRUCache<string, unknown>(6)
    c.set('a', null)
    c.set('b', 0)
    c.set('c', false)
    c.set('d', '')
    expect(c.get('a')).toBeNull()
    expect(c.get('b')).toBe(0)
    expect(c.get('c')).toBe(false)
    expect(c.get('d')).toBe('')
  })

  it('1000 entries 大量插入', () => {
    const c = new LRUCache<number, number>(1000)
    for (let i = 0; i < 1000; i++) c.set(i, i * 2)
    expect(c.size()).toBe(1000)
    expect(c.get(500)).toBe(1000)
    for (let i = 1000; i < 1500; i++) c.set(i, i * 2)
    // maxSize 1000, 老的 0..499 应被淘汰
    expect(c.has(0)).toBe(false)
    expect(c.has(499)).toBe(false)
    expect(c.has(500)).toBe(true)
    expect(c.size()).toBe(1000)
  })

  it('非 string key (number / object)', () => {
    const objKey = { id: 1 }
    const c = new LRUCache<object, string>(2)
    c.set(objKey, 'a')
    expect(c.get(objKey)).toBe('a')
    expect(c.get({ id: 1 })).toBeUndefined()  // 不同引用
  })
})
