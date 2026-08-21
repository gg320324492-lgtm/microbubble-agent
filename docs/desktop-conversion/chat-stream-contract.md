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
