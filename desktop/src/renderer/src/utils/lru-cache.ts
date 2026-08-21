// LRU Cache (Phase 4-B: Knowledge Service Performance).
//
// 纯 TypeScript, 0 依赖. 利用 JS Map 的插入顺序 = LRU 顺序特性.
//
// 复杂度:
//   - get: O(1)
//   - set: O(1) (含 LRU 淘汰)
//   - delete: O(1)
//   - clear: O(1)
//   - keys(): O(n) (从 Map.values() 序列化为数组)
//   - size: O(1)
//
// 设计要点:
//   - get 命中时把 key 移到 Map 末尾 (最近使用)
//   - set 触发 size 检查, 超 maxSize 删最久未用
//   - 显式类型参数 K / V, 不限制 key 类型
//   - 不做 TTL (Phase 4+ 单独 commit)
//   - 不持久化 (内存, Phase 4+ IndexedDB 单独 commit)
//   - 不并发安全 (JS 单线程够用; Phase 4+ 浏览器 worker 单独 commit)

/**
 * LRU Cache, key-value, maxSize bound, Map-backed.
 */
export class LRUCache<K, V> {
  private readonly map: Map<K, V>
  private readonly maxSize: number

  constructor(maxSize: number) {
    if (!Number.isFinite(maxSize) || maxSize <= 0 || !Number.isInteger(maxSize)) {
      throw new Error(`LRUCache: maxSize 必须是正整数 (received: ${maxSize})`)
    }
    this.map = new Map<K, V>()
    this.maxSize = maxSize
  }

  /**
   * 取值: 命中后**移到末尾 (最近使用)**.
   * 未命中: 返回 undefined.
   */
  get(key: K): V | undefined {
    const v = this.map.get(key)
    if (v === undefined) {
      // 容错: 区分 'value undefined' 与 'not present'
      if (!this.map.has(key)) return undefined
      // value 真为 undefined, 仍 promote (rare)
      this.map.delete(key)
      // 这里 v 已确认为 V (因为 map.has(key) 为 true 时, get 返回值是 V, 即使 v 是 undefined 也通过类型守卫)
      this.map.set(key, v as V)
      return v
    }
    // 命中后 promote
    this.map.delete(key)
    this.map.set(key, v)
    return v
  }

  /**
   * 写入: 已存在则更新 + promote; 不存在则 insert.
   * 超 maxSize 时淘汰最久未用 (Map 头部).
   */
  set(key: K, value: V): void {
    if (this.map.has(key)) {
      this.map.delete(key)
    } else if (this.map.size >= this.maxSize) {
      // 淘汰最久未用 (Map 头部)
      const oldestKey = this.map.keys().next().value as K | undefined
      if (oldestKey !== undefined) {
        this.map.delete(oldestKey)
      }
    }
    this.map.set(key, value)
  }

  /**
   * 显式删除.
   */
  delete(key: K): boolean {
    return this.map.delete(key)
  }

  /**
   * 清空 cache (Phase 4+ 用于 logout / 用户切换).
   */
  clear(): void {
    this.map.clear()
  }

  /**
   * 当前 entry 数.
   */
  size(): number {
    return this.map.size
  }

  /**
   * 是否存在该 key.
   */
  has(key: K): boolean {
    return this.map.has(key)
  }

  /**
   * 全部 key (按 LRU 顺序, 最久未用在前).
   * 用于调试 / metrics.
   */
  keys(): K[] {
    return [...this.map.keys()]
  }

  /**
   * 命中后的 LRU order 测试入口 (Phase 4-A 测试覆盖).
   */
  peekOrder(): K[] {
    return [...this.map.keys()]
  }
}
