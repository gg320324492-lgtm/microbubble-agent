# MicroBubble AI Chat API Contract (Phase 2-Impl-3A)

> **目的**: Desktop Chat UI 框架（Phase 2-Impl-3A）消费的 endpoint 契约。
> 任何后端 schema 改动（`app/api/v1/chat.py` + `app/api/v1/chat_history.py` + `app/schemas/chat_history.py`）必须同步更新本文件。
>
> **来源**: `app/api/v1/chat.py` + `app/api/v1/chat_history.py` + `app/schemas/chat_history.py` 实际代码 (2026-08-21 只读确认)。
>
> **消费者**: Desktop `renderer/api/chat.ts` + `main/services/api/`。
>
> **范围** (Phase 2-Impl-3A):
> - ✅ Session 列表 / 单 session 拉取
> - ✅ Messages 列表加载
> - ✅ 用户消息发送 (POST /chat, 同步)
> - ✅ Assistant 回复渲染 (Markdown 安全)
> - ✅ Markdown 复用 MarkdownViewer
> - ❌ **Streaming** (Phase 3+ 接 `/chat/stream` SSE)
> - ❌ **RAG / WebSocket** (Phase 3+)
> - ❌ 上传 / 附件 / 反馈 (Phase 3+)

---

## 1. Phase 2-Impl-3A 使用端点 (4 个)

| Method | Path | 鉴权 | 用途 |
|--------|------|------|------|
| `GET` | `/api/v1/chat/sessions` | 是 | Session 列表（左侧） |
| `GET` | `/api/v1/chat/sessions/{id}` | 是 | 单 session 详情（含 messages 全量） |
| `GET` | `/api/v1/chat/sessions/{id}/messages` | 是 | 历史消息分页 |
| `POST` | `/api/v1/chat` | 是 | 发送 user 消息，拿 assistant 回复（**同步**）|

Base URL: `https://agent.mnb-lab.cn/api/v1`

### 1.1 留口（Phase 3+ 接）

- `POST /api/v1/chat/stream` (SSE) → StreamChunk 类型已在 `shared/chat-types.ts` freeze
- `WS /api/v1/ws/...` → WebSocket 推送
- `POST /api/v1/chat/image` / `/chat/file` → 多模态上传
- `POST /api/v1/chat/sessions/{id}/messages` → 用户手工追加消息

---

## 2. 通用约定

- 全部走 `Bearer <access_token>` (主进程注入)
- 错误: FastAPI `{detail: '...'}` 归一化 (api.service 已做)
- 时间: ISO 8601 字符串, `formatDateTime()` helper

---

## 3. Schema 对齐

### 3.1 `ChatSessionListItem` (会话列表项, 不含 messages)

```ts
interface ChatSessionListItem {
  id: string                  // 后端用 str (业务内 UUID)
  title: string
  preview: string
  is_pinned: boolean
  is_archived: boolean
  tags: string[]
  message_count: number
  last_message_at: string | null
  created_at: string
  updated_at: string
}

interface ChatSessionListResponse {
  items: ChatSessionListItem[]
  total: number
  page: number
  page_size: number
}
```

来源: `app/schemas/chat_history.py:56 (ChatSessionListItem)` + `:68 (ChatSessionListResponse)`

### 3.2 `ChatSessionOut` (单 session 详情)

```ts
interface ChatSessionOut {
  id: string
  user_id: number
  title: string
  preview: string
  is_pinned: boolean
  is_archived: boolean
  tags: string[]
  message_count: number
  last_message_at: string | null
  created_at: string
  updated_at: string
  deleted_at: string | null
  messages: ChatMessageOut[] | null  // 仅 GET /sessions/{id} 填
}
```

来源: `app/schemas/chat_history.py:33 (ChatSessionOut)`

### 3.3 `ChatMessageOut` (消息)

```ts
interface ChatMessageOut {
  id: number
  session_id: string
  role: 'user' | 'assistant' | 'system' | 'tool' | string
  content: string                 // 文本主体 (assistant 时是 markdown 源)
  rich_blocks: Record<string, unknown>[]    // v2 新增, 富结构块 (Phase 3+)
  tool_trace: Record<string, unknown>        // 工具调用痕迹 (Phase 3+)
  message_metadata: Record<string, unknown>  // 别名 metadata, SQLAlchemy ORM 兼容
  is_partial: boolean               // 流式中是否部分内容 (Phase 2 不用)
  is_deleted: boolean
  client_msg_id: string | null      // 客户端幂等 ID
  attached_knowledge_ids: number[]  // 关联知识 ID
  image_url: string | null          // 上传图片 URL
  created_at: string
}

interface ChatMessagesPage {
  items: ChatMessageOut[]
  has_more: boolean
  next_after_id: number | null     // 游标分页
}
```

来源: `app/schemas/chat_history.py:95 (ChatMessageOut)` + `:125 (ChatMessagesPage)`

### 3.4 `ChatRequest` / `ChatResponse` (同步, Phase 2-Impl-3A 使用)

```ts
interface ChatRequest {
  message: string
  session_id: string               // 默认 "default"
  model?: string                   // 覆盖 settings.AGENT_SYNTHESIS_MODEL
  thinking_mode?: 'fast' | 'balanced' | 'deep' | null
  // Phase 3+ 字段 (Phase 2-Impl-3A 不传):
  //   attached_knowledge_ids?: number[]
  //   image_url?: string
}

interface ChatResponse {
  content: string                  // 最终答案 (markdown 源)
  session_id: string
  file_url?: string | null
  file_name?: string | null
  knowledge_content?: string | null
  is_brief: boolean                 // DEPRECATED, 永远 false
  // v2 新增:
  rich_blocks: Record<string, unknown>[]
  tool_trace: Record<string, unknown>[]
  usage?: { [k: string]: number } | null   // token usage
  duration_ms?: number | null
  // 方案 C 新增:
  intent?: Record<string, unknown> | null
  critique?: Record<string, unknown> | null
}
```

来源: `app/api/v1/chat.py: ChatRequest` + `ChatResponse`

### 3.5 StreamChunk 留口 (Phase 3+)

```ts
interface StreamChunk {
  event: 'message_start' | 'content_delta' | 'tool_call' | 'message_end' | 'error' | string
  delta?: string                  // content 增量
  tool?: string                   // 工具名
  args?: Record<string, unknown>
  finish_reason?: 'stop' | 'length' | 'tool_calls' | string
  // 携带其它字段
  [k: string]: unknown
}
```

Phase 3+ 通过 `POST /chat/stream` (text/event-stream) 接收, 本 Phase 不接。

---

## 4. Phase 2-Impl-3A UI 行为契约

### 4.1 ChatView 三栏布局

```
┌────────────────────────────────────────────────────────────────────┐
│  Header: session.title    │  status  │  message_count  │  ...       │
├──────────────────────┬─────────────────────────────────────────────┤
│  左侧 Session List    │  右侧 Messages                              │
│  ┌────────────────┐  │  ┌────────────────────────────────────────┐  │
│  │ session A    ● │  │  │ ⓘ assistant (markdown 安全渲染)         │  │
│  │ session B      │  │  ├────────────────────────────────────────┤  │
│  │ session C      │  │  │ 👤 user (纯文本/字面)                   │  │
│  │ ...           │  │  ├────────────────────────────────────────┤  │
│  └────────────────┘  │  │ ⓘ assistant                            │  │
│                      │  └────────────────────────────────────────┘  │
│                      │  ┌────────────────────────────────────────┐  │
│                      │  │  ┌─ 输入框 ────────────────────────┐   │  │
│                      │  │  │  在这里输入消息...               │   │  │
│                      │  │  └─────────────────────────────┘   │  │
│                      │  │    [发送]                            │  │
│                      │  └────────────────────────────────────────┘  │
└──────────────────────┴─────────────────────────────────────────────┘
```

### 4.2 状态

- **idle / empty**: 无消息, 显示 "开始对话吧 ✨" 占位
- **sending**: 提交时输入框 disabled + 按钮 loading spinner, 临时 assistant 占位 "思考中..."
- **error**: 顶部 / 列表内红条 + 重试按钮
- **received**: 拉数据 OK, 渲染 messages

### 4.3 Markdown 复用

- Assistant 消息的 `content` 字段: 视为不可信 markdown → `MarkdownViewer.vue`
- User 消息: 纯文本 (`white-space: pre-wrap`), 不解析 markdown
- 严禁 `v-html`

---

## 5. 与 web 端差异

| 维度 | web | desktop |
|------|-----|---------|
| 数据流 | axios 直接调 | window.api.api.request → IPC → main |
| Streaming | useChatStream + fetch reader | **Phase 2 不接, 同步**; Phase 3+ 同样走 IPC + 流式 |
| Markdown 渲染 | useChatStream 内 inline | MarkdownViewer 复用 (Phase 2-Impl-2B) |
| Session 列表 | 左侧 / 下拉 | 左栏 240px |

---

## 6. 已知兼容性项

| 项 | 处理 |
|-----|------|
| `session_id` 是 `str` 不是 `int` | TS 用 `string` |
| `role` 枚举 (`user` / `assistant` / `system` / `tool`) | TS 用 `'user' | 'assistant' | string` 兼容 |
| `messages` 仅在 GET /sessions/{id} 时填, list 时为 null | store 区分 list / detail |
| `rich_blocks` 是 v2 新增, 老 session 可能为空数组 | UI 不渲染, Phase 3+ 接 |
| `last_message_at` 可能是 null | UI 隐藏时间 |
| `message_metadata` 在 JSON 输出时是 `metadata` (序列化别名) | TS 字段名 `message_metadata`, 而 API 返回 `metadata` |

---

## Status (2026-08-21 Phase 2-Impl-3A)

- ✅ 4 endpoint schema 确认
- ✅ Chat types 字段对齐
- ✅ StreamChunk freeze (Phase 3+)
- ⏳ Phase 2-Impl-3B+: 接入 SSE streaming
- ⏳ Phase 3+: RAG / WS / 多模态

---

📌 **维护规则**:
- 后端 schema 改动 → 必须先改本 doc，再实现 desktop
- Streaming 接入前必须再 update 本 doc (§1.1 留口)
- 任何 token 相关 → security.md + plan-v1.md 同步
