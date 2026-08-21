# Knowledge Service Architecture (Phase 4-A)

> **目的**: Desktop Knowledge 数据访问层抽象, 介于 store/view 与 IPC gateway 之间。
> Phase 4-A 落地, Phase 4+ 在此基础上叠加缓存 / RAG / multi-window 等。
>
> **不修改 backend / chat / agent / RAG pipeline** — 仅 Desktop 端架构调整。

---

## 1. Phase 4-A 之前的架构

```
KnowledgeView / KnowledgeDetailView
   ↓
stores/knowledge.ts (Pinia)
   ↓ (直接 import 函数)
api/knowledge.ts (IPC wrappers)
   ↓ window.api.api.request
main service → FastAPI
```

**问题**:
- store 直接持有 IPC 层 import, 业务/状态/协议耦合
- 缺少统一的业务方法入口 (logging / hooks / future caching)
- 测试时必须 mock 整个 ipc / 模块依赖, 不能精细拦截

## 2. Phase 4-A 之后的架构

```
KnowledgeView / KnowledgeDetailView
   ↓
stores/knowledge.ts (Pinia 状态 + UI 缓存)
   ↓ (迁移到 service)
services/knowledge.service.ts  ← 🆕 Phase 4-A NEW
   ↓ (委托 + future hook)
api/knowledge.ts (IPC wrapper, 单层 protocol)
   ↓ window.api.api.request
main service → FastAPI
```

## 3. 三层职责

| 层 | 路径 | 职责 | Phase 4-A 状态 |
|----|------|------|----------------|
| View | `views/{KnowledgeView,KnowledgeDetailView}.vue` | UI 渲染, 路由参数解析 | 不动 |
| Store | `stores/knowledge.ts` | Pinia 状态 (ref + 派生 + actions), UI 缓存; 仅负责状态管理 | 改 import: api/knowledge → knowledgeService |
| **Service** | `services/knowledge.service.ts` | 🆕 业务方法封装; logging; future caching/RAG hooks | 新建 |
| API (IPC) | `api/knowledge.ts` | window.api.api.request 包装; payload 形状; 类型对齐 | 不动 (调用保留) |
| Main IPC | `main/services/api/api.service.ts` | Bearer 注入 + 单飞 refresh | 不动 |
| Backend | `app/api/v1/knowledge.py` | FastAPI endpoint | **不修改** |

## 4. KnowledgeService 方法集 (Phase 4-A frozen)

| 方法 | 入参 | 返回 | 备注 |
|------|------|------|------|
| `getCategories()` | — | `ApiResult<DynamicCategory[]>` | 透传 |
| `listKnowledge(opts?)` | `category?, keyword?, page?, pageSize?` | `ApiResult<KnowledgeList>` | 透传; 默认 page=1, pageSize=20 |
| `getKnowledge(id)` | `id: number` | `ApiResult<KnowledgeResponse>` | 透传 |
| `semanticSearch(opts)` | `query, limit?, threshold?` | `ApiResult<KnowledgeSearchResult[]>` | 透传 (Phase 2 留口) |
| **`getKnowledgeForCitation(citation)`** 🆕 | `StreamCitationEntry` | `ApiResult<KnowledgeResponse>` | **invalid id 验证 + error 阻止 IPC** |
| `getManyKnowledge(ids)` | `number[]` | `ApiResult<KnowledgeResponse[]>` | **NOT_IMPLEMENTED** (Phase 4+ 留口) |
| `cacheLookup(id)` | `id: number` | `KnowledgeResponse \| null` | 永远 null (Phase 4+ 接 LRU) |
| `listItems(limit)` | `limit: number` | `ApiResult<KnowledgeListItem[]>` | **NOT_IMPLEMENTED** (Phase 4+ 接轻量 endpoint) |

### 4.1 getKnowledgeForCitation (Phase 4-A 行为)

```ts
async getKnowledgeForCitation(citation: StreamCitationEntry): Promise<ApiResult<KnowledgeResponse>>
```

- **校验 1**: `citation.knowledgeId` 是 number (合法 number, 非 NaN, ≥ 1)
- **校验 2 失败**: 返回 `{ ok: false, error: { code: 'INVALID_INPUT', message: 'getKnowledgeForCitation: 无效 knowledgeId (X)' } }` — **不调用 IPC**
- **校验通过**: 委托 `api.knowledge.getKnowledge(citation.knowledgeId)` (单文档拉取, Phase 4-A 与 `getKnowledge(id)` 等价)
- **Phase 4+**: 批量 + cache + 与 citation metadata 联动

### 4.2 NOT_IMPLEMENTED 留口

`getManyKnowledge` 与 `listItems` 返回 `NOT_IMPLEMENTED` 而非抛错:
- 调用方 `if (!r.ok && r.error.code === 'NOT_IMPLEMENTED')` 检查
- renderer 端不会误调 (UI 不暴露); 留 Phase 4+ 实现
- 抛错会让 IPC 通道 + Vue reactive 维护困难; 错误返回与 ApiResult 类型一致

## 5. 内部: debugLog

```
[KnowledgeService] getCategories null
[KnowledgeService] listKnowledge { category: '微纳米气泡', page: 2, ... }
[KnowledgeService] getKnowledgeForCitation { knowledgeId: 42 }
```

- console.debug 输出 (生产构建自动 tree-shake)
- Phase 4+ 可替换为 telemetry hook (`window.dispatchEvent` 或独立 reporter 模块)

## 6. 单元测试覆盖 (Phase 4-A)

`tests/unit/knowledge-service.test.ts` — **vitest 14 cases / 5 describe**:

| describe | cases | 覆盖 |
|----------|------|------|
| `getCategories` | 2 | 成功 + IPC 错误透传 |
| `listKnowledge` | 2 | 成功 + 默认参数 |
| `getKnowledge` | 2 | 成功 + IPC 错误透传 |
| `getKnowledgeForCitation` | 5 | valid / invalid id (0, -1, NaN) / IPC 错误透传 |
| **Phase 4+ 留口** | 3 | getManyKnowledge / listItems / cacheLookup 永远 NOT_IMPLEMENTED / null |

**测试策略**: 全局 mock `window.api.api.request`, 验证 service 委托的 path/payload 与返回透传, 不依赖 module-level mock.

**测试结果**: 14 / 14 PASSED. 全套 (citation + knowledge-route + knowledge-service): **54 passed**.

## 7. 迁移影响

| 文件 | 变化 |
|------|------|
| `renderer/src/services/knowledge.service.ts` | NEW (~160 行) |
| `renderer/src/stores/knowledge.ts` | `import api/knowledge` → `import knowledgeService`; 3 个 method 调用点改写 |
| `renderer/src/views/{KnowledgeView,KnowledgeDetailView}.vue` | 不动 (走 store 间接接 service) |
| `renderer/src/api/knowledge.ts` | 不动 (IPC gateway 仍存在, service 委托给它) |
| `app/api/v1/knowledge.py` | **不修改** (Phase 4-A 严格) |

UI 行为零变化 — Store 改 import 是 refactor, 不是 functional change.

## 8. 设计原则 (Phase 4-A frozen)

| 原则 | 落地 |
|------|------|
| **Service 是业务方法, 不是 IPC 包装的别名** | 加了 debugLog + invalid id 校验; 不只是 `=>` |
| **Store 不直接 import IPC layer** | import 走 service |
| **API gateway 仍存在且简洁** | api/knowledge.ts 不动; 仅被 service 引用 |
| **Phase 4+ 接口已预留, 不实现** | getManyKnowledge / listItems / cacheLookup 三方法签名 freeze |
| **NOT_IMPLEMENTED 而非抛错** | ApiResult 一致性, caller 可检查错误码 |
| **0 不必要的依赖** | 不引入 DI / lru-cache / reaction-emitter 等; 仅 console.debug |

## 9. 非范围 (Phase 4-A 严格排除)

- ❌ Retriever / Embedding / RAG pipeline (Phase 4+ RAG 接入)
- ❌ Backend schema / API 修改
- ❌ Chat / Agent tool 接入
- ❌ LRU cache (Phase 4+ 单独 commit)
- ❌ 批量拉取 (Phase 4+ 单独 commit)
- ❌ 跨 window 同步
- ❌ Telemetry hook 替换 console.debug

## Status (2026-08-21 Phase 4-A)

- ✅ KnowledgeService 抽象落地
- ✅ Store 迁移完成 (UI 不变)
- ✅ Phase 4+ 接口 freeze (getManyKnowledge / listItems / cacheLookup NOT_IMPLEMENTED)
- ✅ getKnowledgeForCitation invalid id 校验
- ✅ 14 unit tests PASSED (总 54 测试)
- ✅ Doc §Knowledge Service Architecture 落地
- ❌ Phase 4+ RAG / Cache / Batch / Telemetry 未触碰

---

📌 **维护规则 (Phase 4-A 起)**:
- 新增业务方法 → service 写, store 调 service; View 不接 service
- 修改现有 service 方法的入参/出参 → break store 的 type, 需同步 store 接驳
- NOT_IMPLEMENTED 方法 → ApiResult 错误返回, 不抛
- Phase 4+ 新增业务方法 → 必须含一段注释说明用途 + Phase 4+ 启用时的接口稳定性
- Phase 4+ / Phase 3+ backend 需新增 endpoint → Desktop 端 pipeline: backend → main service → api → service → store. 不要跨层漏接
