# Chat Knowledge Hot Path (Phase 4-C)

> **目的**: 让 Chat Citation 利用 Phase 4-B KnowledgeService 的 LRU cache + batch 能力。
> Chat 收到 citation event 时, 异步 prefetch (后台将 knowledge 拉入 cache), 渲染侧可从 cache 命中读 metadata。
> **不接 RAG / Retriever / Backend / Chat API 修改**。
>
> **范围**:
> - Chat store 在 'citation' / 'refs' event 处触发 knowledgeService.prefetchKnowledgeForCitations
> - 异步, 不阻塞 chunk 流, 失败静默
> - Session 隔离: 切换 / cancel 时不污染新 session
> - CitationCard 接受 cachedHint prop, 命中时显示 category
> - Phase 4+ 留口: 暂不接 RAG enhancements / metadata enrichment
>
> **冻结范围**: 不修改 Citation 协议 (Phase 3-B0 frozen); 不修改 chat 协议 / API / backend.

---

## 1. 引入 (Phase 4-C 之前的瓶颈)

原来流:
```
SSE citation event
   ↓
chat store.handleStreamChunk case 'citation'
   ↓
streamingMessage.citations.push(citation)
   ↓
渲染时: Phase 3-C1 仅显示 citation 自身 title/snippet
```

问题:
- 用户点 citation 时 (`/knowledge/detail?id=N`), 还要额外 IPC fetch
- 多次重复显示同一 citation (e.g. 流过长, 重复 scroll) 都会重新 fetch
- 没用 Phase 4-B 已经存在的 LRU cache

Phase 4-C 修复: 收到 citation event 时 fire-and-forget prefetch (LRU warming), UI 渲染时 cache 命中拿 metadata.

## 2. 架构 (Phase 4-C 后)

```
[main] SSE chunk
   │
   │  data: { type: 'citation', citation: { knowledgeId: 99, ... } }
   ↓
[preload] ipcRenderer.on('chat:stream-chunk', ...) → fanout
   ↓
[main.ts 一次性注册全局 listener]
   ↓
[chat store handleStreamChunk(ctx, event)]
   │
   ├─ case 'citation' / 'refs':
   │    appendCitations(streamingMessage.value.citations, c)
   │    triggerPrefetch([c]) ← Phase 4-C NEW
   │
   ├─ triggerPrefetch:
   │    ├─ 1. invalid id 过滤 (knowledgeId 是 number 且 > 0)
   │    ├─ 2. dedup by knowledgeId (inflightPrefetches Map)
   │    ├─ 3. 快照当前 sessionId + streamId
   │    ├─ 4. knowledgeService.prefetchKnowledgeForCitations([c]) (Phase 4-B)
   │    │      LRU cache miss -> IPC GET /knowledge/{id}
   │    │      LRU cache hit -> 0 IPC
   │    ├─ 5. .then 结果:
   │    │    ├─ sessionId / streamId 不匹配 -> 丢弃 (session 隔离)
   │    │    ├─ result.ok = false -> 丢弃 (失败静默)
   │    │    └─ success -> cachedHints.value.set(id, response)  ← Vue reactive Map
   │    ├─ 6. .catch -> 丢弃 (静默)
   │    └─ 7. .finally -> inflightPrefetches.delete(id)
   │
   ├─ 渲染:
   │    CitationList 调 store.getCachedHint(c.knowledgeId)
   │    →
   │      hit  -> CitationCard 显示 category (缓存中)
   │      miss -> 普通形态 (Phase 3-C1)
   │
   └─ Lifecycle 管理:
        ├─ selectSession(newId)  -> clearCachedHints() (session 隔离)
        ├─ handleStreamError       -> cachedHints 清 (UI hint 不留 stale)
        └─ cancelActiveStream()    -> cachedHints 清 (同上)
```

## 3. Chat Store 改动 (Phase 4-C)

### 3.1 新增 state

```ts
const cachedHints = ref<Map<number, KnowledgeResponse>>(new Map())
const inflightPrefetches = new Map<number, Promise<void>>()
```

### 3.2 新增 actions / helpers

```ts
function triggerPrefetch(citations: StreamCitationEntry[]): void {
  // 1. invalid filter
  // 2. dedup by id
  // 3. capture session + streamId
  // 4. knowledgeService.prefetchKnowledgeForCitations -> result
  // 5. assert session + stream 仍 active -> cachedHints.set
  // 6. catch -> silent
  // 7. finally -> cleanup inflightPrefetches
}

function getCachedHint(knowledgeId: number): KnowledgeResponse | null {
  return knowledgeService.cacheLookup(knowledgeId)
}

function clearCachedHints(): void {
  inflightPrefetches.clear()
  cachedHints.value = new Map()
}
```

### 3.3 改动接入

- `handleStreamChunk` case 'citation' / 'refs': append 后 triggerPrefetch
- `selectSession`: clearCachedHints (session 隔离)
- `handleStreamError`: 清 cachedHints (cancel-like 后清 UI hint)
- 新增 exports: `cachedHints`, `getCachedHint`, `clearCachedHints`

### 3.4 Lifecycle

| 时刻 | cachedHints | inflightPrefetches |
|------|-------------|-------------------|
| 启动 (mount) | empty | empty |
| session 切换 | clear() | clear() |
| 流 cancel / error | clear() | 不动 (promise 自然 .finally 清) |
| 组件 unmount | 不动 (Pinia module-level) | 不动 |

## 4. Session 隔离 (关键)

### 4.1 需求

> 切换 session / 流失效 不得污染新 session.

### 4.2 实现

- 异步 prefetch 解析时, 快照 startSessionId / startStreamId, 解析后比对当前 currentSessionId / activeStreamId:
  - 不匹配 -> 丢弃 (UI hint 不写), cache LRU 写不撤回 (设计: cache 跨 session 复用)
- session 切换: selectSession 主动 clearCachedHints (in-flight abandon, 后续解析不会再写新 session)
- 流 cancel/error: handleStreamError 清 cachedHints (强制 UI hint 失效)

### 4.3 测试验证

- Spec Step 5 场景 3: 切换后, 旧 session prefetch 解析 -> cachedHints 为空
- Spec Step 5 场景 4: 流 cancel 后, handleStreamError 清 cachedHints

## 5. Failure 静默 (关键)

- IPC 失败: 仅不写 cachedHints, **cache LRU 仍写成功项** (service 行为)
- 服务端错误 (4xx / 5xx): result.ok = false, 丢弃
- Promise rejection: .catch -> 丢弃
- Promise 在 stream-end 后才 resolve: session 比较失败 -> 丢弃
- 全部 silent: console.error 不打 (Phase 4+ telemetry hook)

## 6. CitationCard 数据增强

### 6.1 Props

```ts
interface Props {
  citation: StreamCitationEntry
  index?: number
  cachedHint?: KnowledgeResponse | null  // Phase 4-C NEW
}
```

### 6.2 渲染逻辑

| cachedHint | 行为 |
|------------|------|
| null | Phase 3-C1 形态 (citation 自身 title/snippet); 仅显示 `→ 详情` / `↗ 打开` |
| 有 | 紫色边框 (`.citation-card--cached`); meta 行多显示 `category` chip (青绿) |

### 6.3 视觉

```vue
<button :class="[..., { 'citation-card--cached': hasCachedHint }]">
  <div class="citation-card__head">
    [{{ index+1 }}]  {{ title }}  [score%]
  </div>
  <div class="citation-card__snippet">{{ snippet }}</div>
  <div class="citation-card__meta">
    📁 {{ sourceLabel }}
    <span v-if="cachedHint?.category" class="citation-card__category">{{ cachedHint.category }}</span>
    <span>{{ kind === 'url' ? '↗ 打开' : '→ 详情' }}</span>
  </div>
</button>
```

`citation-card--cached` 视觉: 绿色边框 (提示用户已缓存, 详情页加载会更快).

### 6.4 CitationList 注入

`CitationList` 不直接依赖 chat store; 新增可选 prop `getCachedHint?: (id: number) => KnowledgeResponse | null`. ChatView 注入 `store.getCachedHint`, 既保组件解耦, 又自动响应 Vue reactive (cachedHints 写入触发列表重渲).

## 7. 性能特征

### 7.1 单次 citation event

- 立即累计 citations (sync) — 不阻塞 SSE
- 立即 fire prefetch (async, fire-and-forget)
- 0 IPC if cache hit (Phase 4-B LRU)
- 1 IPC if cache miss (Phase 4-B fallback)

### 7.2 100 citation 流

- 100 累计 calls, 100 dedup by id
- 已经全部 cache hit: 0 IPC
- 全部 cache miss: 100 parallel IPC (Promise.allSettled via service.getManyKnowledge if batched)
- 99 hit + 1 miss: 99 cache + 1 IPC

### 7.3 Citation 渲染

- Phase 4-C: 渲染时 1 次 cacheLookup (HashMap O(1)), 99% 命中
- Phase 4-B 之前: 0 cache hit, 每次渲染依赖 citation 自身字段

## 8. 关键不变量 (Phase 4-C frozen)

1. **Citation 协议不动** — Phase 3-B0 frozen schema, 仅消费 phase=4 增强
2. **Chat API / SSE 协议不动** — chat-stream.service schema 不变
3. **不阻塞流** — triggerPrefetch 异步 fire-and-forget, 流继续
4. **失败静默** — IPC 失败 / Promise reject 全部 catch, 不污染 stream
5. **Session 隔离** — 异步结果依赖 session+streamId 快照比对 (不匹配则丢弃)
6. **UI 渲染 reactive** — cachedHints 是 ref<Map>, Vue 自动 rerender CitationList
7. **Cache 全局复用** — LRU cache 跨 session 共享 (LRU 自动驱逐)
8. **Component 解耦** — CitationList 用 callback prop, 不直接 import chat store
9. **import 边界清晰** — KnowledgeResponse from @shared/knowledge-types (不污染 chat-types)

## 9. 单元测试 (Phase 4-C)

`tests/unit/chat-knowledge-hotpath.test.ts` — 5 cases / 4 spec 场景:

| Spec 场景 | Test | 覆盖 |
|----------|------|------|
| 1. citation 触发 prefetch | "Spec 1" + "Spec 1 (续)" | IPC 调用 + cachedHints 写入 |
| 2. prefetch 失败不影响 stream | "Spec 2" | cachedHints 未写入, isStreaming 仍 true |
| 3. session 切换隔离 | "Spec 3" | 切 session 后旧 prefetch 结果不写 |
| 4. cancel 后 ignore | "Spec 4" | 流 cancel 后 cachedHints 清 |

Total: **82 tests PASSED** (citation 19 + knowledge-route 21 + lru-cache 14 + knowledge-service 23 + chat-knowledge-hotpath 5).

测试基础设施更新:
- `vitest.config.ts` 加 `@shared` / `@` alias (与 electron-vite.config.ts 对齐)
- node environment; pinia store → setActivePinia
- `tests/unit/chat-knowledge-hotpath.test.ts` 5 cases

## 10. 已知限制 (Phase 4-C)

| 限制 | 当前 | 后续 |
|------|------|------|
| prefetch 触发 | 仅 chunk event 时 (SSE 主动) | Phase 4+ 用户 hover / scroll-to-citation 时提前 |
| 批量合并 | 每条 citation 立即 fire prefetch | Phase 4+ 100ms 合并窗口 |
| RAG metadata | 仅 KnowledgeResponse 字段 | Phase 4+ 接 citation.rag_metadata (highlighted char 范围 / 自定义 snippet) |
| 用户主动 prefetch | 隐藏开关 (UI 不暴露) | Phase 4+ 显式 cache lookup button |
| Offline 支持 | 0 (cache 仅内存) | Phase 4+ IndexedDB (Phase 4-B 列的 TTL 演进) |
| 多窗口同步 | 0 (单窗口) | Phase 4+ SharedWorker |

## 11. 非范围 (Phase 4-C 严格)

- ❌ RAG / Retriever / Embedding / Vector Search
- ❌ Backend schema / API / Chat API
- ❌ 修改 Citation 协议 / SSE 协议
- ❌ 自动 prefetch 用户 hover / scroll (留 Phase 4+)
- ❌ RAG metadata 高亮 / snippet 自定义 (留 Phase 4+)
- ❌ CITATION protocol 修改 (Phase 3-B0 frozen)

## Status (2026-08-21 Phase 4-C)

- ✅ Chat store 接 prefetch (citation/refs event 触发)
- ✅ Session 隔离 (snapshot + 比对)
- ✅ Cancel 失败静默 (cleared by handleStreamError)
- ✅ CitationCard cachedHint prop + 视觉
- ✅ CitationList callback prop (解耦)
- ✅ 5 hot-path tests + 82 total tests PASSED
- ✅ vitest alias 扩展 (@shared + @)
- ✅ Doc 11 节
- ❌ Phase 4+ RAG / 用户主动 prefetch / IndexedDB 等未触碰

---

📌 **维护规则 (Phase 4-C 起)**:
- 改 triggerPrefetch 逻辑 → 必须保: 失败静默 + session 隔离 + 不阻塞流 3 不变量
- 新增 cachedHints 字段 → 必含 `Map<number, KnowledgeResponse>`, 不要 array (性能 + dedup)
- 修改 CitationCard prop → `cachedHint` 必为可选 prop, 缺失时不抛错 (Phase 3-C1 兼容)
- 修改 CitationList → 必须保留 callback prop 模式 (不直接依赖 chat store)
- 测试 prefetch 必含 session + stream 状态断言 (防 race condition)
- Phase 4+ 接 RAG / IndexedDB 时, 必先 update §10 限制 + §11 非范围
