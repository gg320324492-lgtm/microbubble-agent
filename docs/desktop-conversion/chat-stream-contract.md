# MicroBubble Chat SSE Streaming Contract (Phase 3-B0 **协议冻结版**)

> **目的**: Desktop Chat 流式端到端契约 (含 Phase 2-Impl-3A/B + Phase 3-A reliability),
> Phase 3-B0 冻结作为 RAG / Citation 后续接入的协议层基础。
>
> **任何后端 schema 改动** 同步 update: §3 StreamEventType / §4 处理矩阵 / §7 兼容项
> 任何 desktop 端类型改动 同步 update §5 StreamContext / §6 MessageIdentity。
>
> **来源** (2026-08-21 只读确认, 之后如后端变更必须重 verify):
> - `app/api/v1/chat.py:309-405` (chat_stream_route)
> - `app/api/v1/chat.py:54` (ChatRequest) — Phase 3-B0 审计: **不含 client_msg_id**
> - `app/api/v1/chat_history.py:249` (append_message) — 支持 client_msg_id
> - `app/api/v1/chat_history.py:158` (ChatMessageCreate) — 含 client_msg_id 字段
> - `app/agent/protocol.py:55-160` (StreamEvent + 17 event types)
>
> **冻结状态**:
> - ✅ Phase 2-Impl-3A 同步 sendMessage + Phase 2-Impl-3B SSE 接 + Phase 3-A 401 refresh / cancel / retry / session 隔离 / client_msg_id 内部关联
> - ❌ Phase 3+ RAG / Citation 实际渲染 (`citation` event 已 freeze schema, 渲染 Phase 3+)
> - ❌ Phase 3+ Agent tool call 渲染 (`tool_use` / `tool_result` 已 freeze schema)
> - ❌ Phase 3+ 多模态上传 / WebSocket / function calling

---

## 1. End-to-end SSE 流 (含 Phase 3-A StreamContext)

```
[Renderer]            [Preload]              [Main process]                [Backend]
    │                     │                        │                           │
    │ startStream(req)     │                        │                           │
    │   via invoke('chat:  │                        │                           │
    │   start-stream')     │                        │                           │
    │                     ├───────────────────────►│                           │
    │                     │                        │                           │
    │                     │      resolve(streamId) │                           │
    │◄─────────────────────┤◄───────────────────────┤                           │
    │                     │                        │                           │
    │                     │                        │ fetch POST /chat/stream    │
    │                     │                        │   Bearer access_token      │
    │                     │                        ├──────────────────────────►│
    │                     │                        │                           │
    │                     │                        │◄─── SSE stream begin ─────┤
    │                     │                        │    data: event JSON       │
    │                     │                        │    ...                     │
    │                     │                        │    data: [DONE]            │
    │                     │                        │                           │
    │                     │ webContents.send('chat:stream-chunk', ctx, event)│
    │◄ onChunk(ctx, ev) ──┤◄───────────────────────┤                           │
    │                     │                        │                           │
    │ (Phase 3-A added: ctx.sessionId)              │                           │
    │                     │                        │                           │
    │ (Phase 3-A retry / cancel via IPC API)        │                           │
    │                     │                        │                           │
```

### 1.1 IPC Channels (Phase 3-A 不变)

| Channel | Direction | Payload |
|---------|-----------|---------|
| `chat:start-stream` | renderer → main (invoke) | `ChatStreamRequest` → resolves `streamId: string` |
| `chat:cancel-stream` | renderer → main (invoke) | `streamId: string` → resolves `{ ok: true }` |
| `chat:stream-chunk` | main → renderer (broadcast) | `(StreamContext, StreamEvent)` |
| `chat:stream-end` | main → renderer (broadcast) | `(StreamContext, {ok: true})` |
| `chat:stream-error` | main → renderer (broadcast) | `(StreamContext, {code, message})` |

### 1.2 Preload API (Phase 3-A 同步 ctx 签名)

```ts
interface DesktopChatStreamApi {
  startStream(req: ChatStreamRequest): Promise<string>
  cancelStream(streamId: string): Promise<{ ok: true } | { ok: false; error: string }>
  onChunk(cb: (ctx: StreamContext, event: StreamEvent) => void): () => void
  onEnd(cb: (ctx: StreamContext, payload: StreamEndPayload) => void): () => void
  onError(cb: (ctx: StreamContext, error: StreamErrorPayload) => void): () => void
}
```

> Phase 3-B0 升级要点: 所有 listener 第 1 参数改为 `StreamContext` (不再只 streamId), renderer 端通过 `ctx.sessionId` 校验 stale chunks。

---

## 2. SSE Wire Format (Phase 3-A 不变)

```
HTTP/1.1 200 OK
Content-Type: text/event-stream
Cache-Control: no-cache
Connection: keep-alive
X-Accel-Buffering: no

data: {"type": "synthesis_start"}\n\n
data: {"type": "text_delta", "delta": "你好"}\n\n
data: {"type": "citation", "citation": {"knowledgeId": 12, "title": "...", "score": 0.92}}\n\n
data: {"type": "tool_use", "tool_name": "knowledge_search", "tool_input": {...}}\n\n
data: {"type": "text_delta", "delta": "，世界"}\n\n
data: {"type": "done", "usage": {...}, "duration_ms": 1200}\n\n
data: [DONE]\n\n
```

每条 SSE 帧: `data: <json>\n\n`; 最后一条总是 `data: [DONE]\n\n`。

---

## 3. StreamEventType 协议冻结 (Phase 3-B0)

### 3.1 8 核心 type (Phase 3-A + Phase 3+ 必接)

| Type | 字段 | 用途 | 接入状态 |
|------|------|------|----------|
| `text_delta` | `delta: string` | 文本逐字流, content += delta | ✅ Phase 3-A |
| `thinking` | `label: string` | "正在 X..." 提示 (阶段进度) | ✅ Phase 3-A |
| `tool_use` | `tool_name / tool_input / tool_use_id` | 工具调用开始 | ⏸ Phase 3+ |
| `tool_result` | `tool_output / tool_duration_ms / tool_error` | 工具调用结果 | ⏸ Phase 3+ |
| `citation` | `citation: StreamCitationEntry \| []` | RAG 引用 (Phase 3+ 接入) | 🆕 Phase 3-B0 frozen |
| `rich_block` | `block: StreamRichBlock` | 富文本块 (Phase 3+ 接入) | ⏸ Phase 3+ |
| `done` | `usage / duration_ms / session_id` | 流结束 | ✅ Phase 3-A |
| `error` | `code / message` | 流错误 | ✅ Phase 3-A |

### 3.2 9 拓展 type (Phase 2 兼容 / Phase 3+ 渐进)

| Type | 来源 / 状态 |
|------|-------------|
| `brief` / `detail` | DEPRECATED, Phase 1-Impl-2 后端不再 emit |
| `intent_detected` | 方案 C Stage 1 意图分类 |
| `plan_step` | 方案 C Stage 2 工具规划 |
| `tool_compressed` | 工具结果压缩 |
| `synthesis_start` | Stage 3 综合开始 |
| `critique` / `retry` | 方案 C 自评 / 重试 |
| `message_persisted` | #043 持久化 (Phase 3-A 已用) |
| `sync_required` | #043 中断提示 |
| `refs` | #CHAT-P0-A 旧引用名 (Phase 3+ 用 `citation`) |
| `suggestions` | 追问 chips |

**RAG 必接**:
- 新增 `citation` event (Phase 3-B0 frozen) — 字段 `citation` 是 `StreamCitationEntry` 或其数组
- 旧 `refs` event 兼容 (后端可能仍 emit; Phase 3+ 优先 `citation`)
- 一份 entry = 一条引用卡片 (knowledgeId + title + snippet + score)

---

## 4. StreamEvent Schema (Phase 3-A + Phase 3-B0 frozen)

```ts
interface StreamEvent {
  type: StreamEventType       // 见 §3 (17+1 string)

  // text_delta / brief / detail
  delta?: string

  // tool_use
  tool_name?: string
  tool_input?: Record<string, unknown>
  tool_use_id?: string

  // tool_result
  tool_output?: Record<string, unknown>
  tool_duration_ms?: number
  tool_error?: string

  // citation (Phase 3-B0 NEW)
  citation?: StreamCitationEntry | StreamCitationEntry[]

  // rich_block
  block?: StreamRichBlock

  // thinking / plan_step
  label?: string

  // error
  code?: string
  message?: string

  // done
  usage?: {
    input_tokens?: number
    output_tokens?: number
    total_tokens?: number
    [k: string]: number | undefined
  }
  duration_ms?: number
  session_id?: string

  // #043 message_persisted
  message_id?: number
  role?: 'user' | 'assistant' | string
  client_msg_id?: string
  is_partial?: boolean

  // #043 sync_required
  reason?: 'aborted' | 'error' | string

  // #CHAT-P0-A (Phase 3-B0 兼容)
  refs?: StreamCitationEntry[]
  suggestions?: unknown[]
}

interface StreamCitationEntry {
  knowledgeId: number
  title: string
  snippet?: string
  url?: string
  score?: number             // 0..1
  source?: 'kb' | 'memory' | 'auto_research' | string
  [k: string]: unknown
}

interface StreamRichBlock {
  type: string
  data?: unknown
  title?: string
  [k: string]: unknown
}
```

---

## 5. StreamContext (Phase 3-A 引入)

```ts
interface StreamContext {
  streamId: string       // 流唯一标识
  sessionId: string      // 所属 session id (Phase 3-A 用于 stale chunk 校验)
}
```

**为什么需要 StreamContext**:
- 单 App 多窗口 时, 所有窗口通过 `webContents.send` 收同一份 chunk
- 用户切换 session 后, 老流的 chunks 仍可能到达 (main 关闭 AbortController 有延迟)
- renderer 校验 `ctx.sessionId !== currentSessionId` → 丢弃 stale chunks
- 同时比对 `ctx.streamId === activeStreamId` 避免 race

### 5.1 切换 Session 时的清理 (Phase 3-A)

```
selectSession(newSid):
  1. cancelActiveStream()    → main 端 abort + 清理 activeStreams Map
  2. 清 streamingMessage state
  3. 清 messages
  4. loadMessages(newSid)
```

即便 main 漏一条 stale chunk 流到新 session, renderer 也因 ctx.sessionId 不匹配而 ignore。

---

## 6. MessageIdentity 协议冻结 (Phase 3-B0 内部使用, Phase 3+ 协议启用)

> **Phase 3-B0 关键发现**: backend `ChatRequest` (用于 `/chat/stream`) **目前不接受** `client_msg_id` 字段。
> 其他路径 (POST `/chat/sessions/{id}/messages` 追加 / `resend`) 已支持 client_msg_id 幂等键。
> 因此 Phase 3-B0 维持内部生成 + 等待 message_persisted 事件回填; **Phase 3+ 需 backend chat.py ChatRequest 升级后**, desktop 才会协议层启用 client_msg_id 透传。

### 6.1 Phase 3-A 内部关联流程 (不变)

1. renderer 生成 `client_msg_id` (`generateClientMsgId()` UUID-like)
2. optimistic user msg + streamingMessage 携带 `client_msg_id` (内部)
3. 后端 `message_persisted` event `{role: 'user'/'assistant', client_msg_id, message_id, ...}` 到达
4. renderer 通过 `client_msg_id` 匹配并替换 msg `id` 为服务端 `message_id`
5. Phase 2 backend 流式落库逻辑保留 (Phase 3-A 不传 client_msg_id, 仅靠 service 层互不影响)

### 6.2 MessageIdentity 类型

```ts
interface MessageIdentity {
  clientMsgId: string            // UUID-like (desktop 内部, 不传 backend)
  serverMessageId: number | null // 服务端落库后回填
}

interface StreamingMessage {
  // ... (Phase 3-A fields)
  persisted_message_id: number | null
  client_msg_id: string
}
```

### 6.3 Phase 3+ 计划 (协议层启用)

- 改动 backend `ChatRequest` 加 `client_msg_id: Optional[str] = Field(None, max_length=64)`
- desktop 改 `ChatStreamRequest` 加同字段, IPC push 时携带
- 后端 v2_agent 接收 client_msg_id, 在 user 落库时用作幂等键
- 后续流式重发 / 网络断重连 / retry 都能去重

---

## 7. Stream Refresh (Phase 3-A 401 一级自动 refresh)

### 7.1 触发条件

SSE HTTP 上游返回 `401 Unauthorized` (access_token 过期)。

### 7.2 流程

```
runStream(streamId, req, signal, attempt=1):
  accessToken = currentAccessToken
  if (!accessToken):
    pushError(ctx, 'NO_ACTIVE_SESSION', '未登录')
    return

  response = await fetch(POST /chat/stream, Bearer: accessToken)

  if (response.status === 401):
    if (attempt === 1):
      refreshed = await tryRefreshToken(ctx)  // vault.get + authService.performRefresh
      if (refreshed):
        runStream(streamId, req, signal, attempt=2)  // 递归, 新 token 已注入
      else:
        pushError(ctx, 'AUTH_EXPIRED', 'refresh 失败, 请重新登录')
    else:
      // attempt=2 也 401 → 强制清场
      pushError(ctx, 'AUTH_EXPIRED', 'refresh 后仍 401')
      authService.forceClearOnRefreshFail()
    return

  // 正常处理
  await parseSSE(response.body, ctx)
```

### 7.3 安全约束

- `tryRefreshToken` 全在 main process, renderer 不知 token
- `vaultLoadRefreshToken` 读 OS 安全存储 (safeStorage.encryptString 加密)
- 401 refresh 仅 attempt=1 触发; attempt=2 仍 401 → 清场 (与 API request 一致)
- renderer 端无需任何 token 处理, 通过 `chat:session-expired` 广播跳 /login

### 7.4 与 api.service 的关系

- `api.service.request` 已有 single-flight refresh (Phase 1-Impl-2)
- `chat-stream.service.tryRefreshToken` 是其简化版本 (单 attempt, 无并发合并)
- Phase 4+ 抽共用 `TokenRefreshManager` 单飞避免 401 race

---

## 8. Cancel Stream (Phase 3-A UI)

### 8.1 用户主动取消

```
[ChatView] 点击 ⏹ 停止生成 button
  ↓
cancelActiveStream() (renderer store)
  ↓
await window.api.chat.cancelStream(streamId)
  ↓
ipcRenderer.invoke('chat:cancel-stream', sid)
  ↓
main: cancelChatStream(sid):
  activeStreams[sid].controller.abort()
  activeStreams.delete(sid)
  ↓
fetch reader throws AbortError
  ↓
pushError(ctx, 'ABORTED', '流已取消')
  ↓
renderer: handleStreamError 清 streamingMessage + 写 lastError='ABORTED'
```

### 8.2 切换 session 自动 cancel (Phase 3-A)

`selectSession(newSid)` 第一步 `cancelActiveStream()` — 防止 stale 流写入新 session。

---

## 9. Retry Stream (Phase 3-A UX)

### 9.1 失败后重试

- `lastSentText` 记录上次发送的完整文本
- 失败时显示 `🔁 重试` button (在 ErrorState 旁)
- 点击 → `retryLastMessage()` → 复用 `lastSentText`, 新 client_msg_id (Phase 3+ 协议层启用后去重)

### 9.2 Phase 3+ 优化 (留口)

- 失败消息卡片本身加 "重试" 按钮 (而非全局 panel)
- 网络错误 vs 服务器错误 vs 主动取消的 UX 区分 (currently 都写 lastError)

---

## 10. Renderer 渲染策略

### 10.1 流中 vs 完成

| 阶段 | 渲染 |
|------|------|
| 流中 (isStreaming=true) | 100ms debounce MarkdownViewer + thinking label + cursor |
| 完成 (isStreaming=false) | 持久化 ChatMessageOut, MarkdownViewer 一次解析 |
| 重试期间 | ErrorState 旁显 retry button |

### 10.2 Markdown 渲染复用 (无 v-html)

详见 `docs/desktop-conversion/plan-v1.md` Phase 2-Impl-2B 总结 + `docs/desktop-conversion/chat-performance.md` §3 性能。

---

## 11. Range Check (Phase 3-B0 协议对齐)

| 维度 | 后端实际 | Desktop 协议层 | 状态 |
|------|----------|----------------|------|
| 17 StreamEvent types | ✅ | ✅ StreamEventType union | 同步 |
| 401 refresh | N/A (需客户端触发) | ✅ main 一级 attempt=2 | 同步 |
| Cancel | ✅ AbortController | ✅ cancelStream IPC | 同步 |
| Retry | N/A | ✅ lastSentText + retryLastMessage | 内部 |
| Session 隔离 | N/A | ✅ StreamContext.sessionId | 桌面策略 |
| `citation` event | ⏸ 后端未 emit (Phase 3+ 待启) | ✅ schema freeze | 同步 (空跑) |
| `tool_use` / `tool_result` | ✅ | ✅ schema freeze | 同步 (空跑) |
| client_msg_id 协议 (流式) | ❌ ChatRequest 不接收 | ⚠ 内部使用, 不传 | **Gap** |
| client_msg_id 协议 (历史) | ✅ POST /messages / resend | ✅ message_persisted 事件回填 | 同步 |

---

## 12. Desktop Citation Rendering Lifecycle (Phase 3-C1)

> Phase 3-C1 在协议层 frozen 的基础上 (Phase 3-B0 `citation` event schema),
> 落地 **Desktop 客户端的 citation 渲染**. **不接 RAG / Retriever / 后端调用**。
> 仅消费流式 SSE `citation` event, 渲染到 ChatView.

### 12.1 数据流 (Phase 3-C1)

```
[Backend (Phase 3+ RAG 启用时)]
  │  data: {"type":"citation", "citation": {knowledgeId, title, snippet, score, url, source}}
  ↓
[Main: chat-stream.service.runStream]
  │ 解析 SSE frame → pushChunk(ctx, StreamEvent)
  ↓
[Preload: chunkListeners fanout]
  ↓
[Renderer store: handleStreamChunk(ctx, event)]
  ├─ streamStaleCheck(ctx) (Phase 3-A 沿用)
  ├─ case 'citation' | 'refs':
  │    appendCitations(streamingMessage.citations, event.citation)
  │    (dedup by knowledgeId)
  └─ content 累加照旧 (Phase 3-A)
↓
[StreamingMessage.citations (Render 触发)]
  ↓
[ChatView template]
  ├─ MarkdownViewer (Phase 2-Impl-2B 安全)
  └─ <CitationList :citations="streamingMessage.citations" />
        └─ for each: <CitationCard :citation="c" />
                      ├─ title (Vue text escape)
                      ├─ snippet (Vue text escape, 3-line clamp)
                      ├─ source label
                      └─ score % (optional)
↓
[handleStreamEnd]
  └─ ChatMessageOut.message_metadata.citations 持久化
        (历史消息 listMessages 加载时无 citations, UI 不渲染)
```

### 12.2 组件结构 (Phase 3-C1 新增)

```
desktop/src/renderer/src/components/chat/
├── CitationCard.vue   # 单条引用展示 + click jump
├── CitationList.vue    # 容器: `📚 引用 N 条` + 列表
└── index.ts             # barrel
```

### 12.3 渲染规则

| 场景 | 渲染 |
|------|------|
| 流中 assistant 内容 > 0 | MarkdownViewer + (有 citation 时) CitationList |
| 流中 assistant 无内容 | cursor + (有 citation 时) CitationList |
| 完成 assistant (无 citation) | 仅 MarkdownViewer (UI 不变, Phase 3-C1 与原状兼容) |
| 完成 assistant (有 citation) | MarkdownViewer + CitationList (从 metadata 提取) |
| 用户消息 / 系统消息 / 工具消息 | 不渲染 citation |

**关键不变量**: 普通聊天无 citation 时, ChatView DOM 与 Phase 3-A 完全一致 (v-if 短路, 0 节点)。

### 12.4 安全

- ❌ **0 v-html** (title / snippet 全 Vue text 插值, 自动 escape)
- ❌ URL 仅允许 `http(s)://` / `mailto:` / 相对路径 (Phase 2-Impl-2B MarkdownViewer 已 freeze);
  citation.url 后端可信度假设: Phase 3+ RAG 服务端需验证
- ✅ 点击 → `window.open(url, '_blank', 'noopener,noreferrer')` → main `setWindowOpenHandler` → `shell.openExternal`
- ✅ 不暴露 ipcRenderer / channel 给 renderer

### 12.5 Source Jump

| 字段 | 行为 (Phase 3-C1) |
|------|---------------------|
| `citation.url` 存在 | window.open → shell.openExternal |
| `citation.knowledgeId` 存在 (无 url) | console.info 占位 (Phase 4+ 接 knowledge 路由) |
| 都无 | 卡片 disabled (无 click) |

**Phase 3-C1 不实现 knowledge 路由跳转** (留 Phase 4+ 接入知识库 DeserializedReferenceRelation)。
**Phase 3-C1 也不实现真实 RAG** (后端必须先扩展 stream event 后才能 emit citation; Phase 3+ 待 RAG 服务接入)。

### 12.6 类型契约增量

```ts
// shared/chat-types.ts
interface StreamingMessage {
  // ... Phase 3-A fields
  citations: StreamCitationEntry[]   // 🆕 Phase 3-C1 必填
}

// ChatMessageOut: 不修改, citations 走 message_metadata.citations (后端 ChatMessageOut schema 不含顶层 citations,
// 临时透传 metadata; Phase 3+ backend 升级为在 schema 添加独立字段, 持久化层补 listMessages 反序列化)
```

### 12.7 调试 / Mock

Phase 3-C1 不引 mock SSE server (Phase 4+ 可选)。手工触发方法:

```ts
// renderer dev console, after main window open:
// 1. 打开 ChatView 触发 main fetch (默认 'default' session 需先 login)
// 2. Phase 3-C1 验证步骤:
//    - 编译后手动在 store 注入 citation 事件 (developer-only path):
//      store.handleStreamChunk(streamCtx, { type: 'citation', citation: { knowledgeId: 12, title: '测试', snippet: '...', score: 0.85 } })
//    - 检查 UI 显示 CitationCard
// Phase 4+ 引 vitest unit tests 覆盖 CitationCard / CitationList 渲染
```

### 12.8 非范围 (Phase 3-C1 明确排除)

- ❌ RAG / Retriever / 后端 embedding 调用
- ❌ 知识库详情跳转 (`router.push(/knowledge/detail?id=...)` 留 Phase 4+)
- ❌ Citation 排序 / 评分 / highlight
- ❌ 单元测试 (Phase 4+ 加 vitest + Phase 3+ 后端真接)
- ❌ 后端 `client_msg_id` 协议层启用 (Phase 3+ backend chat.py ChatRequest 升级)

---

## 13. Citation Interaction Lifecycle (Phase 3-C2)

> Phase 3-C2 在 Phase 3-C1 (UI 渲染) 基础上,
> 增强交互层: 排序 / score UI / knowledge 回调接口 / 单元测试。
> **Phase 3-C2 仍不是 RAG** — 不接 Retriever / Knowledge API / 后端 embedding。

### 13.1 渲染管线 (Phase 3-C2)

```
streamingMessage.citations
       │
       ↓  (SSE chunk arrived, store.appendCitations 累加)
       │
CitationList.vue onRender
       │
       ├─ sortCitations(citations)      ← utils/citation.ts
       │   ├─ 有 score: desc (high→low)
       │   ├─ 无 score: 保原序 (ES2019 stable sort)
       │   └─ 不修改入参
       │
       ├─ dedupCitations(citations)     ← utils/citation.ts
       │   └─ by knowledgeId, 首次保, 后续丢
       │
       ↓  sortedUnique: StreamCitationEntry[]
       │
v-for over CitationCard
       │
       ├─ toPercent(score): "N%" / null
       │   - null → 卡片无 score pill (隐藏)
       │   - <0 or >1 → null (校验)
       │
       ↓  卡片渲染
       │
click 行为 (Phase 3-C2)
       │
       ├─ kind === 'url'  → window.open(url, '_blank', 'noopener,noreferrer')
       │                   → main setWindowOpenHandler → shell.openExternal
       │
       ├─ kind === 'kb'   → emit('knowledge-open', knowledgeId)
       │                   → ChatView.onCitationKnowledgeOpen
       │                   → Phase 3-C2: console.info 占位 (Phase 4+ router.push)
       │
       └─ kind === 'none' → 卡片 disabled, 无 click
```

### 13.2 模块结构 (Phase 3-C2 NEW)

```
desktop/src/renderer/src/
├── utils/
│   └── citation.ts              # 🆕 Phase 3-C2 纯函数 helpers
│       ├─ sortCitations()
│       ├─ dedupCitations()
│       ├─ normalizeCitations() = sort + dedup
│       ├─ toPercent() 0..1 -> "N%"
│       └─ hasValidScore()
│
├── components/chat/
│   ├── CitationCard.vue          # +emit('knowledge-open', knowledgeId)
│   │                              # +toPercent(score) score pill UI
│   │                              # +alpha 强调高分 (>=0.7 alpha=1.0)
│   └── CitationList.vue          # +sortCitations(citations) computed
│                                  # +emit('knowledge-open', id) 透传
│
tests/unit/
└── citation.test.ts              # 🆕 vitest 单元测试 19 cases
```

### 13.3 排序规则 (Phase 3-C2)

| 优先级 | 规则 |
|--------|------|
| P0 | 有 score 的 citation 排前, 按 score 降序 (1.0 → 0.0) |
| P1 | 无 score 的 citation 保原顺序 (ES2019 stable sort) |
| P2 | 同一 score 多个: 保原顺序 (stable) |
| P3 | dedup 在 sort 前: dedup 与 sort 解耦, normalizeCitations = dedup + sort |

**关键不变量**: sort + dedup 都不修改入参 (纯函数)。

### 13.4 Score UI (Phase 3-C2)

```
[1]  微纳米气泡机理研究综述      [82%]   ← score pill
     微纳米气泡是指直径小于 1 微米...
     📁 知识库                                  ↗ 打开
```

- `toPercent(score)` → `"82%"` 或 `null`
- 显示条件: `scorePercent` 非空 (即 score ∈ [0, 1] 有效区间)
- 视觉强调: score ≥ 0.7 → opacity 1.0; 0.5-0.7 → opacity 0.85
- Pill 颜色: 暖色 (琥珀黄 #fbbf24) — 与 "KB 卡片" 紫主色区分

### 13.5 Knowledge 跳转接口 (Phase 3-C2 留口)

```
CitationCard.onClick()
  ├─ if url → window.open
  └─ if knowledgeId (no url)
       └─ emit('knowledge-open', knowledgeId)
              ↓
CitationList.vue 透传
       ↓
ChatView.vue @knowledge-open="onCitationKnowledgeOpen"
       ↓ (Phase 3-C2 实现)
console.info('[ChatView] citation knowledge-open requested. knowledgeId=', N)
       ↓ (Phase 4+ 接 router.push('/knowledge/detail?id=N'))
```

**Phase 3-C2 不实现**:
- ❌ 真实路由跳转 (router.push 不存在 'knowledge-detail' 名称 + 详情组件在 Phase 4+)
- ❌ Knowledge API 调用 (Phase 4+ 接 Knowledge Service)
- ❌ Knowledge 模态打开 (Phase 4+)

### 13.6 单元测试覆盖 (Phase 3-C2)

`tests/unit/citation.test.ts` — vitest 19 cases / 5 describe 块:

| 块 | 场景 |
|----|------|
| `toPercent` | 空值 / 边界 0..1 / 越界 |
| `hasValidScore` | valid / invalid (missing / NaN / -0.1 / 1.1) |
| `sortCitations` | 空 / 单条 / 多条降序 / 相同 score 保序 / 全无 score 保序 / 不修改入参 |
| `dedupCitations` | 空 / 单条 / 重复 knowledgeId 第一次保留 / 非法 knowledgeId 跳过 / 不修改入参 |
| `normalizeCitations` | dedup + sort 组合 + 边界 |

测试工具: vitest 2.1.9 + node environment (无需 DOM)。
脚本: `npm run test:unit`。

### 13.7 已知偏差 (Phase 3-C2)

| 项 | 当前 | 后续 |
|----|------|------|
| Score 来源 | Phase 3-C2 仅消费, 不计算 | Phase 3+ RAG 服务端产出 |
| 单元测试范围 | 纯 helpers; 组件 (CitationCard.vue / CitationList.vue) 未测 | Phase 4+ 加 happy-dom + @vue/test-utils 测组件 |
| Mock SSE citation | 当前无 mock, Phase 4+ 加 fixtures | Vitest mock → chunks → 触发渲染 |

---

## Status (2026-08-21 Phase 3-C2 frozen)

- ✅ Citation 排序 (score desc stable) 落地
- ✅ Score UI (toPercent pill + alpha 强调) 落地
- ✅ Knowledge 跳转接口 (emit + console.info 占位) 落地
- ✅ 单元测试 19 cases 全过
- ✅ Doc §13 Citation Interaction Lifecycle 增补
- ⏳ Phase 3+ RAG / Retriever / Knowledge API 接入
- ⏳ Phase 4+ router 接入 + 组件测试 + 真实 RAG

---

📌 **维护规则 (Phase 3-C2 起)**:
- 修改 `sortCitations` / `dedupCitations` 必须保持**纯函数** + **stable** + **不修改入参**
- 增加 score 字段 (Phase 3+ RAG) → update `StreamCitationEntry` + `hasValidScore`
- 任何新 event 字段接入 → 先 update §4 表 + 同步 utils 测试

---

## Status (2026-08-21 Phase 3-B0 frozen)

- ✅ 17 type streamEvent schema 冻结
- ✅ StreamContext + MessageIdentity 锁定
- ✅ 401 refresh / Cancel / Retry / Session 隔离设计冻结
- ⏳ Phase 3+ RAG / Citation 实际渲染 (schema 已就绪)
- ⏳ Phase 3+ backend chat.py ChatRequest 加 `client_msg_id` 字段后, desktop 协议层启用

---

📌 **维护规则**:
- 后端 schema 改动 → 必须先改本 doc §3 §4 §11
- 任何 token 相关调整 → security.md + plan-v1.md 同步
- 取消 / 重连 / 401 refresh 接入变化 → update §7 §8 §9
- Performance profile 变化 → chat-performance.md 同步
- **本文件改动必须经 Phase 3-B0+ 同步批 commit, 不与业务 commit 混杂**
