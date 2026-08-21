# MicroBubble Knowledge Detail Contract (Phase 2-Impl-2B)

> **目的**: Desktop Knowledge 详情页（Phase 2-Impl-2B "Pro View"）消费的 endpoint 契约。
> 任何后端 schema 改动（`app/api/v1/knowledge.py` + `app/schemas/knowledge.py`）必须同步更新本文件。
>
> **来源**: `app/schemas/knowledge.py` + `app/api/v1/knowledge.py:943` 实际代码 (2026-08-21 只读确认)。
>
> **范围** (Phase 2-Impl-2B):
> - ✅ Markdown 正文渲染 (`content`)
> - ✅ 元信息展示 (key_concepts / related_topics / knowledge_type / source_type / file_*)
> - ✅ 分页 (knowledge 列表)
> - ✅ Citation 基础结构（UI 占位，无 RAG 生成）
> - ❌ RAG Streaming（Phase 3+）
> - ❌ AI Chat（Phase 3+）
> - ❌ 上传/编辑（Phase 3+）

---

## 1. Phase 2-Impl-2B 使用端点（2 个直接 + 1 留口）

| Method | Path | 鉴权 | 用途 |
|--------|------|------|------|
| `GET` | `/api/v1/knowledge/{id}` | 是 | 详情（Phase 2-Impl-2A 已有, B 扩展使用） |
| `GET` | `/api/v1/knowledge?category=&keyword=&page=&page_size=` | 是 | 列表分页（Phase 2-Impl-2A 已有, B 加分页 UI） |
| `GET` | `/api/v1/knowledge/{id}/related` | 是 | Citation 留口（Phase 3+ 渲染） — `RelatedKnowledge[]` |

---

## 2. 字段对齐

### 2.1 KnowledgeResponse 详情字段

来源: `app/schemas/knowledge.py:KnowledgeResponse` (继承 `KnowledgeBase`)

| 字段 | 类型 | 用途 | Phase 2-Impl-2B 渲染位置 |
|------|------|------|-----------------------|
| `id` | int | 路由参数 / UI 调试 | Header (debug) |
| `title` | str | 标题 | Header |
| `content` | str | Markdown 正文（**需 sanitize 渲染**） | Body |
| `formatted_content` | str \| null | LLM 预格式化 HTML（**禁用 v-html, 严禁直接渲染**） | ❌ Phase 2 不渲染 |
| `summary` | str \| null | LLM 摘要 | Body 顶部 |
| `category` | str \| null | 分类 | Header badge |
| `tags` | string[] \| null | 标签 | Header |
| `key_concepts` | string[] \| null | 关键概念 | Side (Metadata) |
| `related_topics` | string[] \| null | 相关主题 | Side (Metadata) |
| `knowledge_type` | str \| null | 类型 (paper / report / wiki / ...) | Side (Metadata) |
| `topic` | str \| null | 学科领域 | Side (Metadata) |
| `analysis_status` | str \| null | 分析状态 (pending/processing/completed/failed) | Header status pill |
| `quality_score` | number \| null | 质量评分 (0..1) | Side (Metadata) |
| `needs_review` | boolean | 是否需要人工复核 | Side (badge) |
| `thumbnail_url` | str \| null | 缩略图 | ❌ Phase 2 不渲染缩略图 |
| `image_count` | number | 图片数 | Side (Metadata) |
| `meta` | object \| null | 自由字段 (qa-bench / auto_expansion 等) | Side (Metadata, JSON 折叠) |
| `source` | str \| null | 原文 URL / DOI / 文件路径 | Side (Metadata) |
| `source_type` | str \| null | 来源类型 (`auto_expansion` / `auto_research` / `conversation` / `paper` / `chat`) | Side (Metadata) |
| `file_path` | str \| null | 上传文件路径 | Side (Metadata, conditional display) |
| `file_name` | str \| null | 上传文件名 | Side (Metadata) |
| `file_type` | str \| null | 文件类型 (pdf/docx/...) | Side (Metadata) |
| `created_at` | ISO 8601 | 创建时间 | Side (Metadata) |
| `updated_at` | ISO 8601 | 更新时间 | Side (Metadata) |
| `created_by` | int \| null | 创建用户 ID | Side (Metadata) |

### 2.2 重要 caveat: `formatted_content`

- 后端来自 LLM 二次格式化（HTML 片段）
- **Desktop 严禁 `v-html` 直接渲染**:
  - LLM HTML 可能含 `<script>` / `<iframe>` / 危险属性
  - CSP `unsafe-inline` 已禁用
- **Phase 2-Impl-2B 处理**: 完全不展示 `formatted_content`, 仅展示 `content` 由自写 markdown 解析器渲染
- **Phase 3+ 计划**: 若要展示, 必须经 sanitize (DOMPurify 等), 现 spec 排除

---

## 3. Content Markdown 渲染规范

### 3.1 后端 content 字段性质
- 来源: PDF / Word / 上传 / 用户录入 → 抽文本 / LLM 二次切片
- 形态: 纯文本 (可能有 markdown 标记) + 中文/英文/数字/代码块
- ⚠️ **不可信**: 没有任何 schema 强约束, 可能含 HTML 标签 / `<script>` / 任意字符

### 3.2 Desktop 安全渲染原则

Phase 2-Impl-2B 内 **自写小型 markdown parser + AST + Vue 模板 v-for 渲染**:
- 全文本先 escape HTML 实体 (`<` → `&lt;` 等)
- 解析为 block AST (heading / paragraph / code / list / quote)
- 解析 inline token (code / bold / italic / link) — link URL 校验 scheme 仅 `http:`/`https:`
- Vue 模板 `v-for` 渲染 AST node, **永远不**使用 `v-html`
- 渲染 markdown AST 输出 HTML 字符串时, 二次 escape inline token (`<code>` 等)

### 3.3 支持的 Markdown 子集（Phase 2-Impl-2B）

| 语法 | 示例 | 输出 |
|------|------|------|
| Heading | `# H1`, `## H2`, `### H3` | h1/h2/h3 (受控 depth ≤ 6) |
| Code block | ` ``` lang ` ... ` ``` ` | `<pre><code class="lang-xxx">` |
| Inline code | `` `code` `` | `<code>` |
| Bold | `**bold**` | `<strong>` |
| Italic | `*italic*` | `<em>` |
| List (- or *) | `- item` | `<ul><li>` |
| Ordered list | `1. item` | `<ol><li>` |
| Quote | `> text` | `<blockquote>` |
| Link | `[text](url)` | `<a>` (仅 http/https, 其他丢弃) |
| HR | `---` | `<hr>` |

**不支持**（Phase 2-Impl-2B 范围内）：
- 表格（Phase 3+ 用提取物 UI 单独展示）
- 图片（Phase 3+ 用 `image_url` extracted）
- 嵌套列表 / Todo / 任务列表 (GFM)
- 代码高亮（Phase 3+ 接 highlight.js）
- 数学公式 / KaTeX（Phase 3+ `formatted_content` 集成）

### 3.4 安全边界

输入任意 markdown 字符串, 走 parser:
1. escape HTML 实体
2. block 解析（识别 fence, header, list, quote, hr）
3. inline 解析（识别 code, bold, italic, link）
4. 输出 Vue 组件 (Vue 自动 escape text)；inline token HTML 需白名单

详见 `components/ui/MarkdownViewer.vue` 内部。

---

## 4. Pagination

来源: `app/api/v1/knowledge.py:101 list_knowledge` 已支持 `page` (ge=1) + `page_size` (ge=1, le=100)

Phase 2-Impl-2B 要求:
- List view 底部加分页器 (上一页 / 下一页 / 第 N 页 / 总页数)
- 默认 `page_size = 20` (与 Phase 2-Impl-2A 一致)
- Pinia store 加 `setPage(n)` + `goToNext()` / `goToPrev()` + `totalPages` 派生

分页器 UI:
```
[← 上一页]  第 1 / 5 页 (共 87 条)  [下一页 →]
```

---

## 5. Citation 留口 (Phase 3 准备)

### 5.1 类型契约

```ts
interface Citation {
  id: string                  // 唯一标识
  knowledgeId: number         // 主文档 ID
  sourceKnowledgeId: number   // 引用文档 ID
  snippet: string             // 引用文本片段
  score: number               // 0..1 相似度
  relationship: 'semantic' | 'explicit' | 'structural' | string
  reason?: string             // 为什么引用 (LLM 解释)
}
```

### 5.2 后端来源 (Phase 3+ 启用)
- `GET /api/v1/knowledge/{id}/related` → `RelatedKnowledge[]` (含 `relation_type` + `score` + `reason`)
- Phase 2-Impl-2B: schema freeze, **不在 UI 渲染**

### 5.3 UI 占位
- KnowledgeDetailView 底部加 "📚 引用与关联 (Phase 3+ 集成)" 区块
- 显示空态: "RAG streaming 暂未启用, 等待授权"

---

## 6. 与 web 端差异

| 维度 | web | desktop |
|------|-----|---------|
| Markdown 渲染 | 大量 (内嵌格式化 + 公式 + 图片 + 高亮 + 评论) | Phase 2 简版（heading + code + list + quote + link）, Phase 3+ 富化 |
| Citations | RAG 实时生成, 流式加载 | **Phase 2 占位, Phase 3 接** |
| Metadata | 滚动 + 内嵌 | 右侧 sticky panel |
| 上传/编辑 | drag-drop + 富文本编辑器 | 不做 (Phase 3+) |
| 滚动 | 单一滚动条 | Body 独立滚动 + Side 固定 |

---

## 7. 已知 desktop ↔ backend 兼容性项

| 项 | 处理 |
|-----|------|
| `formatted_content` 是 LLM 预格式化 HTML | Desktop 严禁使用 v-html; 字段保留 schema 但不渲染 |
| `content` 可能含 0 markdown 标记 (纯文本) | parser 容错降级到 paragraph |
| `key_concepts` / `related_topics` 可能为 null | UI 隐藏对应区块 |
| `meta` 是 `object \| null`, 字段全自由 | UI 折叠 JSON 展示 (可读文本) |
| `analysis_status` 旧数据可能为空 | UI fallback "未分析" |
| `created_at` / `updated_at` 是 ISO 8601 | 已用 `formatDateTime()` helper |

---

## Status (2026-08-21 Phase 2-Impl-2B)

- ✅ KnowledgeResponse schema 全部字段对齐
- ✅ 自写 markdown parser 安全策略 freeze
- ✅ Citation type freeze (Phase 3+)
- ✅ Pagination 规范 freeze
- ⏳ Phase 3: RAG streaming + 富 markdown + 编辑器

---

📌 **维护规则**:
- 后端 schema 改动 → 必须先改本 doc，再实现 desktop
- Desktop 若发现后端字段差异 → PR 同时改本 doc
- `content` 永远视为不可信输入, parser 必须 sanitize
- 任何 markdown 渲染变更 → 必须 `vue-tsc` + 实际页面试渲染验证
