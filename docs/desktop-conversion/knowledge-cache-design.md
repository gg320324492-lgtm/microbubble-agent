# Knowledge Cache Design (Phase 4-B)

> **目的**: Phase 4-B KnowledgeService 性能基础 (LRU cache + batch + prefetch) 设计文档。
> 不嵌入 RAG / Retriever / Backend 修改。
>
> **来源**: Phase 4-A service 抽象 + Phase 4-B 性能层叠加。
> **消费者**: Desktop renderer (KnowledgeView / KnowledgeDetailView / Chat Citation)。

---

## 1. 动机 (Phase 4-A 之后的瓶颈)

Phase 4-A service 是 IPC 透明转发, 每次调用都打后端:
- 用户浏览 5 个 knowledge 详情 → 5 次 HTTP
- 用户在 Chat 看到 3 个 citation → 3 次 HTTP
- 用户 hover/click 反复访问同一 id → 重复 fetch

Phase 4-B 落地 LRU cache + batch fetch + citation prefetch, 减少重复 IPC。

## 2. 架构 (Phase 4-B 后)

```
View / Store
    ↓
knowledgeService (Phase 4-A → Phase 4-B 增强)
    ├─ LRU cache (本层新增)
    │   └─ knowledgeCache: LRUCache<number, KnowledgeResponse>
    │       maxSize = 200, 内存, 单例, module-level
    ├─ getKnowledge(id)         cache hit → 不打 IPC
    ├─ getManyKnowledge(ids)    dedup + invalid filter + partial-cache + parallel
    ├─ prefetchKnowledgeForCitations(citations)  委托 batch
    ├─ cacheLookup(id)          (Phase 4-A 留口激活) → 返真实 cache 值
    └─ listItems(limit)         cache-only (Phase 4+ 接后端轻量 endpoint)
    ↓
api/knowledge.ts (Phase 4-A / Phase 4-B 不动)
    ↓
window.api.api.request
    ↓
main service → FastAPI
```

## 3. LRU Cache 设计

### 3.1 选型

| 候选 | 优 | 劣 | 决策 |
|------|----|----|------|
| 内置 `Map<K, V>` + 手动管理 | 0 依赖 | 需自己实现 LRU 语义 | 选 |
| `lru-cache` (npm) | 成熟 | 多 1 依赖 | 不要 |
| `quick-lru` (npm) | 轻量 | 同上 | 不要 |
| `IndexedDB` | 持久化 | 异步, 接入重 | Phase 4+ |

**纯 TypeScript, 0 依赖**, 实现于 `renderer/src/utils/lru-cache.ts`.

### 3.2 API

```ts
class LRUCache<K, V> {
  constructor(maxSize: number)  // 正整数校验
  get(key: K): V | undefined    // 命中 promote 到 MRU
  set(key: K, value: V): void  // 超过 maxSize 时淘汰最久未用 (老的 evict)
  delete(key: K): boolean
  clear(): void
  size(): number
  has(key: K): boolean
  keys(): K[]                   // LRU order, 最久未用在前
  peekOrder(): K[]              // same as keys(), 测试接口
}
```

### 3.3 复杂度

- get / set / delete / has / clear: **O(1)**
- keys / peekOrder: **O(n)** (Map 序列化)
- size: **O(1)**

### 3.4 关键不变量

- **get 命中后 promote 到 MRU**: `map.delete(key) + map.set(key, v)`
- **set 超 maxSize 时淘汰最久未用**: `map.keys().next().value` 拿到头
- **update 已存在 key 也 promote**: 避免新插入变 MRU、旧值仍 MRU

### 3.5 maxSize 选型

| 参数 | 值 | 理由 |
|------|---|------|
| `KNOWLEDGE_CACHE_MAX` | **200** | lab session 内浏览 ≤ 200 个 knowledge 详情, 够用; 内存 ~ 200 * 50KB = 10MB |

Phase 4+ 可调: 按 user category / tenant / 全局 vs session 维度。

### 3.6 限制 (Phase 4-B 不做, 留 Phase 4+)

| 不做 | 原因 | 后续 |
|------|------|------|
| TTL | Knowledge 文档由 backend 决定 stable, 暂不加 TTL | Phase 4+ 加, TTL + manual invalidate |
| 持久化 | renderer 端内存, 关闭 app 即丢 | IndexedDB persistence (Phase 4+) |
| 多 window 同步 | 桌面单窗口 app | Phase 4+ multi-window sync via SharedWorker |
| 统计 metrics | Phase 4-B 仅 console.debug | Phase 4+ 接 telemetry hook |
| LRU-K 优化 | 简单 LRU 够用 | Phase 4+ LFU / ARC (高频 re-visit) |

## 4. 缓存策略

### 4.1 getKnowledge(id) 流程

```
getKnowledge(id)
  │
  ├─ invalid id (0/负/NaN/非 number) → INVALID_INPUT, 不调 IPC
  │
  ├─ cache.get(id) 命中 → 立即返回 (0 IPC)
  │
  └─ cache miss:
      │
      ├─ IPC api.getKnowledge(id)
      │
      ├─ 成功 → cache.set(id, data) + return result
      │
      └─ 失败 → **不写 cache** + return error (失败不污染)
```

**关键: 失败不污染 cache** — 下次同 id 仍 miss, 允许 retry; 不会让错误状态冻结命中。

### 4.2 cacheLookup(id) (Phase 4-A 留口激活)

Phase 4-A 永远返 null. Phase 4-B 接 LRU, 命中返真实值, miss 返 null (调用方应调 getKnowledge)。

```ts
cacheLookup(id: number): KnowledgeResponse | null
```

### 4.3 listItems(limit) (Phase 4-A NOT_IMPLEMENTED → Phase 4-B cache-only)

Phase 4-A 留口的 NOT_IMPLEMENTED 替换为 cache-only 实现:
- 全部 cache 内的 KnowledgeResponse 转 light item
- 截断到 limit
- **不调 IPC** (Phase 4+ 接后端 /knowledge/list 轻量 endpoint 后再加 fetch 路径)

## 5. getManyKnowledge Batch 设计

### 5.1 流程

```
getManyKnowledge(ids: number[])
  │
  ├─ empty → ok + []
  │
  ├─ dedup (Set) + 防御上界 (>500 不再 dedup)
  │
  ├─ invalid id 过滤 (0/负/NaN/非 number)
  │
  ├─ empty after filter → ok + []
  │
  ├─ partial-cache lookup:
  │   ├─ cache hit -> cacheResults
  │   └─ cache miss -> toFetch (异步拉取队列)
  │
  ├─ Promise.allSettled(toFetch.map(knowledgeApi.getKnowledge))
  │
  ├─ 写回 cache (成功 only; 失败不污染)
  │
  └─ 按原 (deduped + filtered) 顺序返回
```

### 5.2 顺序保证

- 入参 `[20, 10, 30]` → 输出 `[doc(20), doc(10), doc(30)]`
- 关键: `for (const id of validIds)` 遍历, 按输入顺序查 cacheResults / fetchedResults
- 不依赖 Promise.allSettled 完成顺序 (parallel fetch 速度不一致)

### 5.3 部分失败语义

- Promise.allSettled 不 reject; 失败项丢弃, 成功项保留
- `ok: true, data: [...successful]`
- 失败项不写 cache (同 getKnowledge)
- 全部失败 → `ok: true, data: []` (无 ok: false, 因为 partial success 仍是 service 维度成功)

### 5.4 批大小

- 当前无显式限制 (Phase 4-A 决策)
- 防御: dedup 上界 500 (避免误传 1000 项)
- Phase 4+ 可加 chunked fetch (e.g. 50/批) 配合后端限流

### 5.5 性能估算

- 假设 5 citation, 全部 cache miss: 5 次并行 IPC, ~50-200ms total (parallel)
- 假设 5 citation, 全部 cache hit: 0 IPC, ~5ms (map lookups)
- 假设 5 citation, 3 命中 + 2 miss: 2 IPC, ~30-100ms

## 6. prefetchKnowledgeForCitations (Phase 4-B 留口)

### 6.1 当前实现

```ts
async prefetchKnowledgeForCitations(citations: StreamCitationEntry[]): Promise<ApiResult<KnowledgeResponse[]>> {
  // 1. 抽 knowledgeId
  // 2. invalid 过滤
  // 3. 委托 getManyKnowledge(ids) -> dedup + cache + partial + batch
}
```

### 6.2 未来扩展 (Phase 4+)

- **hot-path 集成**: Chat streaming chunk 中 emit citation 时立即触发 prefetch (填入 cache, 用户 click 时 hit)
- **批量合并**: 100ms 内多个 citation 合并 1 次 batch
- **RAG metadata enrichment**: 返回值带 `KnowledgeResponse + citation_metadata` (highlight char 位置, 自定义 mark)
- **失败重试**: 网断期间先用 cache 兜底, 重连后 retry

### 6.3 不在范围 (Phase 4-B)

- ❌ 修改 Chat streaming store / 调用链路
- ❌ 自动 trigger (依赖外部指令)
- ❌ RAG / metadata enrichment

## 7. 生命周期

### 7.1 创建

- `LRUCache` 实例在 `services/knowledge.service.ts` 模块加载时 `(module-level lazy)` 1 次
- `KNOWLEDGE_CACHE_MAX = 200` const singleton
- 随 Electron renderer 进程启动自动创建

### 7.2 存活

- App 整个生命周期内都在
- 路由切换 / SPA 页面跳转 不影响 (module-level)
- Memo 状态: Written once on success, never auto-cleared

### 7.3 失效

- LRU 自动驱逐 (maxSize 超限)
- 显式 `_internal.clearCache()` (Phase 4+ logout / user 切换)
- Phase 4+ 接入 IndexedDB 持久化时, 关闭 app 前应 flush

## 8. 关键不变量 (Phase 4-B frozen)

1. **失败不污染 cache** — IPC error 时不 set, 下次同 id 仍 miss
2. **顺序保持** — getManyKnowledge 按入参 (deduped + filtered) 顺序返回
3. **partial success 仍 ok** — 5 项中 4 项成功, ok: true with 4 items; 仅全部失败 / 入参非法 才 非 ok
4. **invalid id 弃** — 0 / 负 / NaN / 非 number 全部过滤, 不扔错
5. **dedup 防御** — 500+ dedup 上界, 防止误传
6. **0 额外依赖** — LRUCache 纯 TS, 0 npm 包
7. **UI 行为不变** — store 改 import 是 refactor, UI 表现零变化
8. **Token 不漂移** — 所有 fetch 仍走 window.api.api.request (主进程 Bearer + refresh)

## 9. 测试覆盖 (Phase 4-B)

| Suite | Cases | 覆盖 |
|-------|-------|------|
| `lru-cache.test.ts` (NEW) | 14 | 基础 ops / LRU eviction / boundary / 大量插入 |
| `knowledge-service.test.ts` (重写) | 23 | cache hit/miss/eviction/batch dedup/order invalid/failure/prefetch/listItems |
| `citation.test.ts` (Phase 3-C2) | 19 | 不变 |
| `knowledge-route.test.ts` (Phase 3-D) | 21 | 不变 |
| **Total** | **77 PASSED** | 295ms |

详细 case 见 `tests/unit/lru-cache.test.ts` + `tests/unit/knowledge-service.test.ts` §Phase 4-B 节.

## 10. 已知限制 (Phase 4-B)

| 限制 | 当前 | 后续 |
|------|------|------|
| TTL | 无 — 文档变更时不主动 invalidate | Phase 4+ 用户操作后 (e.g. refresh button) 调 `_internal.clearCache()` |
| 持久化 | 内存, 关闭 app 丢 | Phase 4+ IndexedDB |
| 跨 window | 单窗口 | Phase 4+ multi-window sync |
| Metrics | 仅 console.debug | Phase 4+ telemetry hook |
| Hot-path | 手动调 prefetch | Phase 4+ Chat streaming 集成 |
| 失败计数 | 无 | Phase 4+ metrics for cache miss rate / failure ratio |

## 11. 非范围 (Phase 4-B 严格)

- ❌ RAG / Retriever / Embedding
- ❌ Backend schema / API 修改
- ❌ Chat / Agent tool 接入
- ❌ Chat streaming 的 hot-path prefetch (仅留口)
- ❌ TTL / IndexedDB / multi-window / metrics
- ❌ LRU-K / LFU / ARC 等高级算法
- ❌ 其它 domain service 抽 (auth / dashboard / chat) — Phase 4+ 各自抽

## Status (2026-08-21 Phase 4-B)

- ✅ LRU Cache (纯 TS, 0 依赖) 落地 + 14 单测
- ✅ getKnowledge cache hit/miss + 失败不污染 + invalid id 校验
- ✅ getManyKnowledge batch 实现 (dedup + invalid filter + order + partial-cache)
- ✅ prefetchKnowledgeForCitations 留口 (dedup + 委托 batch)
- ✅ cacheLookup 激活 (Phase 4-A 留口)
- ✅ listItems cache-only (Phase 4+ 接后端 endpoint)
- ✅ 77 tests PASSED (citation 19 + knowledge-route 21 + lru-cache 14 + knowledge-service 23)
- ✅ Doc Knowledge Cache Design 9 节
- ❌ Phase 4+ RAG / Cache / Chat hot-path / Telemetry 未触碰

---

📌 **维护规则 (Phase 4-B 起)**:
- 改 LRU cache 行为 → 必须保 `不污染失败` + `顺序保持` + `partial success ok` 3 不变量
- 新增 cache service 方法 → 必含 _internal 调试入口 (cacheSize / clearCache)
- Phase 4+ 接 RAG / IndexedDB 时, 必先 update §10 限制 + §6 prefetch 章节
- TypeScript strict 启用时, `V | undefined` 必须显式 cast
- 任何 batch 方法必保 order preservation (write 测试, 不能"应该如此")
