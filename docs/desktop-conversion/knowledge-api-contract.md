# MicroBubble Knowledge API Contract (Phase 2-Impl-2A)

> **目的**: Desktop 知识库模块消费的 endpoint 契约，**Phase 2-Impl-2A 仅做基础列表 / 搜索 / 详情入口**。
> 任何后端 schema 改动（`app/api/v1/knowledge.py` + `app/schemas/knowledge.py`）必须同步更新本文件。
>
> **来源**: `app/api/v1/knowledge.py` + `app/schemas/knowledge.py` 实际代码 (2026-08-21 只读确认)。
>
> **消费者**: Desktop 客户端 `renderer/api/knowledge.ts` + `main/services/api/`。
>
> **非范围 (Phase 2-Impl-2A)**:
> - RAG streaming (`/knowledge/qa` `/knowledge/research` 流式 SSE) — Phase 3+
> - AI Chat 流式 — Phase 3+
> - 上传大文件优化 (`/knowledge/upload` Multipart) — Phase 3+

---

## 1. Phase 2-Impl-2A 使用端点 (4 个)

| Method | Path | 鉴权 | 用途 |
|--------|------|------|------|
| `GET` | `/api/v1/knowledge/categories` | 是 | 左侧"知识库分类"列表 |
| `GET` | `/api/v1/knowledge` | 是 | 中间"文档列表" (含搜索 keyword 过滤) |
| `GET` | `/api/v1/knowledge/search/semantic` | 是 | 语义搜索（Phase 3+ RAG 入口；本次仅 schema freeze, UI 入口暂留占位） |
| `GET` | `/api/v1/knowledge/{id}` | 是 | 文档详情（Phase 2-Impl-2A 仅路由入口，详细页 Phase 2-Impl-2B+） |

Base URL: `https://agent.mnb-lab.cn/api/v1`

---

## 2. 通用约定

- 全部走 `Bearer <access_token>` (主进程注入)
- 错误: FastAPI `{detail: '...'}` 或 `{detail: [...]}` 归一化 (主进程 api.service 已做)
- 列表形态: `{items: [...], total: int}` (类似其它 paginated endpoint)

---

## 3. 端点契约

### 3.1 `GET /knowledge/categories`

**Response**: `List[DynamicCategory]`

```ts
interface DynamicCategory {
  name: string       // e.g. "微纳米气泡", "DFT 计算"
  count: number      // 该分类下的文档数
}
```

来源: `app/api/v1/knowledge.py:412` `@router.get("/knowledge/categories", response_model=List[DynamicCategory])`

后端实现: `KnowledgeGraphService.get_dynamic_categories()` —— 从实际数据自动聚合（不写死）。

### 3.2 `GET /knowledge`

**Query**:
- `category?: string` — 按分类过滤
- `keyword?: string` — 关键词搜索 (substring match title/content)
- `has_file?: boolean` — 只返回含上传文件的条目
- `source_type?: string` — `auto_expansion` / `auto_research` / `conversation` / `paper` / `chat`
- `page: int = 1`
- `page_size: int = 20` (max 100)

**Response**: `KnowledgeList`

```ts
interface KnowledgeList {
  items: KnowledgeListItem[]
  total: number
}

interface KnowledgeListItem {
  id: number
  title: string
  category: string | null
  tags: string[] | null
  key_concepts: string[] | null
  related_topics: string[] | null
  knowledge_type: string | null
  source: string | null        // 原始 URL / DOI / 上传文件路径
  source_type: string | null
  summary: string | null
  snippet: string | null       // content 前 200 字符, 卡片预览
  analysis_status: string | null
  quality_score: number | null
  needs_review: boolean
  topic: string | null
  created_by: number | null
  created_at: string           // ISO 8601
  updated_at: string           // ISO 8601
  thumbnail_url: string | null
  image_count: number
  file_path: string | null
  file_name: string | null
  file_type: string | null
  meta: Record<string, unknown> | null
}
```

来源: `app/api/v1/knowledge.py:101` + `app/schemas/knowledge.py:KnowledgeListItem`

**注意**: list 不含 `content`；要看全文必须调 `/knowledge/{id}`。

### 3.3 `GET /knowledge/search/semantic`

**Query**:
- `query: string` (必填)
- `limit: int = 10`
- `threshold?: float`

**Response**: `List[KnowledgeSearchResult]`

```ts
interface KnowledgeSearchResult {
  id: number
  title: string
  content: string          // snippet 级别, 不是全文
  category: string | null
  tags: string[] | null
  source: string | null
  score: number            // cosine similarity 0..1
}
```

来源: `app/api/v1/knowledge.py:531` + `app/schemas/knowledge.py:KnowledgeSearchResult`

**Phase 2-Impl-2A**: schema freeze; UI 入口留占位 (按钮 disabled 标 "Phase 3+")。完整 RAG 流式 `/knowledge/qa` 与 `/knowledge/research` 留 Phase 3。

### 3.4 `GET /knowledge/{id}`

**Path**: `id: int`

**Response**: `KnowledgeResponse`

```ts
interface KnowledgeResponse extends KnowledgeBase {
  id: number
  source: string | null
  source_type: string | null
  file_path: string | null
  file_name: string | null
  file_type: string | null
  summary: string | null
  // ... 其他字段继承自 KnowledgeBase
  // 核心: id / title / content / category / tags / created_at / updated_at
}

interface KnowledgeBase {
  title: string
  content: string                // 全文
  category: string | null
  tags: string[] | null
  key_concepts: string[] | null
  related_topics: string[] | null
  knowledge_type: string | null
  topic: string | null
  analysis_status: string | null
  quality_score: number | null
  needs_review: boolean
  thumbnail_url: string | null
  image_count: number
  meta: Record<string, unknown> | null
  created_by: number | null
  created_at: string
  updated_at: string
}
```

来源: `app/api/v1/knowledge.py:943` + `app/schemas/knowledge.py:KnowledgeResponse` (继承 `KnowledgeBase`)

---

## 4. Phase 2-Impl-2A UI 行为契约

### 4.1 KnowledgeView.vue 双栏布局

```
┌─────────────────┬──────────────────────────────────────┐
│  知识库分类      │  [搜索框:  _________________  🔍 ]   │
│                 │                                      │
│  ⌬ 全部 (42)   │  文档列表 (n items)                    │
│  ├ 微纳米气泡(18)│  ┌─────────────────────────────────┐ │
│  ├ DFT 计算(12) │  │ 标题 1   [状态]   updated_at      │ │
│  ├ ...          │  │ snippet (前 200 字)              │ │
│                 │  │ tags                              │ │
│                 │  └─────────────────────────────────┘ │
│                 │  ┌─────────────────────────────────┐ │
│                 │  │ ...                              │ │
│                 │  └─────────────────────────────────┘ │
└─────────────────┴──────────────────────────────────────┘
```

### 4.2 左侧 categories

- 数据源: `GET /knowledge/categories`
- 顶部"全部"项汇总所有分类的 count
- 点击分类 → 中间 list 用 `?category=` query 重拉

### 4.3 中间 list

- 数据源: `GET /knowledge?page=1&page_size=20&category=...&keyword=...`
- 卡片显示: title + snippet + tags + updated_at
- 状态徽标: `analysis_status` (pending / completed / failed 派生)
- 点击卡片 → 进入详情（Phase 2-Impl-2A 留路由占位 `?id=` query, 详情页另起 Phase 2-Impl-2B）

### 4.4 搜索框

- 用户输入 → 触发 debounced search (300ms)
- `keyword` 参数接到 list endpoint
- 暂不实现 semantic search UI

### 4.5 详情入口

- 卡片点击 → `router.push({ name: 'knowledge-detail', query: { id } })`
- Phase 2-Impl-2A 仅占位: 注册 `knowledge-detail` 路由 + 简单 view 显示 "ID: X, TODO"
- 完整详情页 Phase 2-Impl-2B

---

## 5. 与 web 端差异

| 维度 | web | desktop |
|------|-----|---------|
| 列表 view | `KnowledgeView.vue` 复杂多 tab + RAG 入口 + 分类树 + AI chat | Desktop Phase 2-Impl-2A: 三栏 / 双栏简化, 无 RAG |
| 数据流 | `axios.get('/api/v1/knowledge/...')` | `window.api.api.request → IPC → main api.service → fetch` |
| RAG | `/knowledge/qa` 流式 SSE | **不做 (Phase 3+)** |
| 详情页 | 滚动阅读 + 评论 + 引用图谱 | Phase 2-Impl-2B |
| 上传 | drag-drop + multipart | **不做 (Phase 3+)** |

---

## 6. 已知 desktop ↔ backend 兼容性项

| 项 | 处理 |
|-----|------|
| `updated_at` / `created_at` 是 ISO 8601 字符串, 不是 number | UI 用 `new Date(str).toLocaleString('zh-CN')` 渲染 |
| `snippet` 是 content 前 200 字符, 可能含 `\n` / markdown | UI 用 CSS `white-space: pre-wrap; max 2 行` |
| `tags` 可能为 `null` | UI fallback 显示 `[无标签]` |
| `category` 可能为 `null` | UI 显示 "未分类" |
| `analysis_status` 可能未填 (旧数据迁移) | UI fallback "未分析" |
| `source_type` 维度多 | Phase 3 引入过滤器 |

---

## Status (2026-08-21 Phase 2-Impl-2A)

- ✅ 4 endpoint schema 确认
- ✅ Desktop types 字段对齐
- ⏳ Phase 2-Impl-2B: 详情页
- ⏳ Phase 3+: 完整 RAG streaming + AI chat + 上传

---

📌 **维护规则**:
- 后端 schema 改动 → 必须先改本 doc，再实现 desktop
- Desktop 若发现后端字段差异 → PR 同时改本 doc
- 任何 token 相关调整 → 必须有 security.md + plan-v1.md 同步
