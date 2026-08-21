# MicroBubble Chat SSE Streaming Contract (Phase 2-Impl-3B)

> **目的**: Desktop Chat SSE 流式传输的端到端契约。
> 任何后端 schema 改动（`app/api/v1/chat.py:StreamEvent` / `app/agent/protocol.py`）必须同步更新本文件。
>
> **来源**: `app/api/v1/chat.py:309-405` (chat_stream_route) + `app/agent/protocol.py:55-160` (StreamEvent + to_sse) 实际代码 (2026-08-21 只读确认)。
>
> **消费者**: Desktop `main/services/chat/chat-stream.service.ts` + `renderer/stores/chat.ts`。
>
> **Phase 2-Impl-3B 范围**:
> - ✅ SSE transport (HTTP/1.1 `data:` 帧)
> - ✅ IPC streaming chunk / end / error
> - ✅ `text_delta` / `thinking` / `done` / `error` / `message_persisted` 字段处理
> - ✅ 占位 assistant message + 100ms debounce + Markdown re-render
> - ❌ Agent tool_call (`tool_use` / `tool_result` / `plan_step`) 渲染 - Phase 3+
> - ❌ RAG citation (`rich_block` / `refs`) 渲染 - Phase 3+
> - ❌ Function calling / 多模态 - Phase 3+
> - ❌ 自评 / 重试 (`critique` / `retry` / `synthesis_start`) - Phase 3+

---

## 1. End-to-end SSE 流

```
[Renderer]              [Preload]              [Main process]            [Backend]
    │                      │                          │                       │
    ├─ startStream(req) ───►│                          │                       │
    │   via invoke('chat:    │                          │                       │
    │   start-stream', req)  │                          │                       │
    │                      ├─────────────────────────►│                       │
    │                      │ invoke('chat:start-stream'│                       │
    │                      │   → resolve(streamId)      │                       │
    │                      │                          ├─ POST /chat/stream ────►│
    │                      │                          │   Authorization: Bearer
    │                      │                          │   Content-Type: application/json
    │                      │                          │   body: ChatRequest    │
    │                      │                          │                       │
    │                      │                          │◄── SSE stream begin ──┤
    │                      │                          │    data: {"type":"synthesis_start", ...}
    │                      │                          │    data: {"type":"text_delta", "delta":"..."}
    │                      │                          │    data: {"type":"text_delta", "delta":"..."}
    │                      │                          │    data: {"type":"done", "usage":{...}}
    │                      │                          │    data: [DONE]         │
    │                      │                          │                       │
    │◄─ onChunk(streamId,  ─┤                          │                       │
    │     event)            │  webContents.send('chat: │                       │
    │   via contextBridge   │    stream-chunk', sid, ev)                       │
    │                      │◄─────────────────────────┤                       │
    │◄─ onEnd(streamId,    ─┤                          │                       │
    │     {ok:true})        │  webContents.send('chat: │                       │
    │                      │    stream-end', sid, {ok:true})                   │
    │◄─ onError(streamId,  ─┤                          │                       │
    │     error)            │  webContents.send('chat: │                       │
    │   (only on failure)   │    stream-error', sid, err)                      │
```

### 1.1 IPC Channels (Phase 2-Impl-3B 新增)

| Channel | Direction | Payload |
|---------|-----------|---------|
| `chat:start-stream` | renderer → main (invoke) | `ChatStreamRequest` → resolves `streamId: string` |
| `chat:cancel-stream` | renderer → main (invoke) | `streamId: string` → resolves `{ ok: true }` |
| `chat:stream-chunk` | main → renderer (broadcast) | `(streamId: string, event: StreamEvent)` |
| `chat:stream-end` | main → renderer (broadcast) | `(streamId: string, payload: { ok: true })` |
| `chat:stream-error` | main → renderer (broadcast) | `(streamId: string, error: { code: string, message: string })` |

### 1.2 Preload API (Phase 2-Impl-3B 新增)

```ts
interface DesktopChatStreamApi {
  startStream(req: ChatStreamRequest): Promise<string>
  cancelStream(streamId: string): Promise<{ ok: true }>
  onChunk(cb: ChunkListener): () => void     // returns unsubscribe
  onEnd(cb: EndListener): () => void          // returns unsubscribe
  onError(cb: ErrorListener): () => void      // returns unsubscribe
}
```

---

## 2. SSE Wire Format (后端 → main)

```
HTTP/1.1 200 OK
Content-Type: text/event-stream
Cache-Control: no-cache
Connection: keep-alive
X-Accel-Buffering: no

data: {"type": "synthesis_start"}\n\n
data: {"type": "text_delta", "delta": "你好"}\n\n
data: {"type": "text_delta", "delta": "，世界"}\n\n
data: {"type": "done", "usage": {"input_tokens": 100, "output_tokens": 50}, "duration_ms": 1200}\n\n
data: [DONE]\n\n
```

每条 SSE 帧格式固定为 `data: <json>\n\n`, 最后一条总是 `data: [DONE]\n\n` (Phase 2-Impl-3B 用于干净停止)。

---

## 3. StreamEvent Schema (Pydantic 镜像)

```ts
type StreamEventType = 
  // 原 9 种事件
  | 'text_delta' | 'tool_use' | 'tool_result' | 'rich_block'
  | 'thinking' | 'brief' | 'detail' | 'error' | 'done'
  // 方案 C 新增 6 种
  | 'intent_detected' | 'plan_step' | 'tool_compressed'
  | 'synthesis_start' | 'critique' | 'retry'
  // #043 持久化
  | 'message_persisted' | 'sync_required'
  // #CHAT-P0-A 反馈锚点
  | 'refs' | 'suggestions'
  | string  // 兜底

interface StreamEvent {
  type: StreamEventType

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

  // rich_block
  block?: { type: string; data?: unknown; title?: string; [k: string]: unknown }

  // thinking / plan_step
  label?: string

  // error
  code?: string
  message?: string

  // done
  usage?: { input_tokens?: number; output_tokens?: number; total_tokens?: number; [k: string]: number | undefined }
  duration_ms?: number
  session_id?: string

  // #043 message_persisted
  message_id?: number
  role?: 'user' | 'assistant' | string
  client_msg_id?: string
  is_partial?: boolean

  // #043 sync_required
  reason?: 'aborted' | 'error' | string
}
```

来源: `app/agent/protocol.py:80-160 (StreamEvent)`

---

## 4. Phase 2-Impl-3B 字段处理矩阵

| Event | 来源字段 | Renderer 处理 |
|-------|----------|--------------|
| `text_delta` | `delta` | 累加到 streamingMessage.content (Phase 3+ 富化) |
| `thinking` | `label` | 临时更新 streamingMessage.thinking (淡黄 UI strip, 100ms 后被 text_delta 替换) |
| `synthesis_start` | — | 无 payload, 标记 "starting" 状态 |
| `brief` / `detail` | `delta` | **DEPRECATED, 忽略** (Phase 1 兼容 v1 客户端) |
| `done` | `usage` / `duration_ms` / `session_id` | finalize: streamingMessage → 真实 assistant, 标记 isStreaming=false |
| `message_persisted` | `message_id` / `role` | 记录 message_id (后端已落库), Phase 3+ 用 |
| `error` | `code` / `message` | error UI + isStreaming=false |
| `sync_required` | `reason` | error 兜底 (网络中断); 提示用户刷新 |
| `tool_use` / `tool_result` / `rich_block` / `refs` | — | **acknowledge, 不渲染** (Phase 3+ 接 agent/tool/citation) |
| `intent_detected` / `plan_step` / `tool_compressed` / `critique` / `retry` | — | **acknowledge, 不渲染** |
| `suggestions` | — | Phase 3+ 接追问 chips |

---

## 5. Renderer 行为契约

### 5.1 streamingMessage 形态

```ts
interface StreamingMessage {
  id: number                              // 临时 ID (Date.now())
  session_id: string
  role: 'assistant'
  content: string                         // 累加中的 markdown 文本
  thinking: string | null                 // 最新 thinking label
  rich_blocks: Record<string, unknown>[]
  tool_trace: Record<string, unknown>[]
  started_at: string
}
```

### 5.2 流程

1. 用户 Enter → store.sendUserMessageStream(text)
2. 立刻 push optimistic user (跟 Phase 2-Impl-3A 一致)
3. 创建 streamingMessage (临时 ID, content='', thinking=null), append 到 messages
4. 调 window.api.chat.startStream({ message: text, session_id })
5. main 返回 streamId, store 记录 activeStreamId
6. 监听 chunk:
   - `text_delta` → streamingMessage.content += event.delta
   - `thinking` → streamingMessage.thinking = event.label
   - `done` → finalize: streamingMessage.content 替换, 标记 isStreaming=false, 异步刷新 sessions
   - `error` → error UI + 移除 streamingMessage
   - `sync_required` → 同 error
7. 100ms debounce 对 streamingMessage.content 触发 MarkdownViewer 重渲染
8. End 后清掉 listener 引用

### 5.3 Markdown Re-render 优化

**关键**: 不要每 token 重新 parse markdown!

策略:
- streamingMessage.content 是 raw markdown 字符串
- 模板中用 `v-if="streamRenderEnabled"` 决定是否渲染 MarkdownViewer
- 100ms debounced setStreamRenderEnabled = !streamRenderEnabled (但沿用 computed)
- 更简单: 把 streaming content 直接当成 `<pre>` plain text 渲染, 仅在 `done` / 用户暂停时切换成 MarkdownViewer

**Phase 2-Impl-3B 落地**: 
- streaming 中用 `<pre class="streaming-pre">{{ streamingMessage.content }}</pre>` (普通文本, refresh 100ms 不渲染卡顿)
- done 后整个 message 替换为 `MarkdownViewer` 组件

---

## 6. 与 web 端差异

| 维度 | web `useChatStream.ts` | desktop |
|------|------------------------|---------|
| 流式 reader | `fetch + getReader()` + `TextDecoder` | 主进程 `fetch` + line parse, 转 IPC 推 chunk |
| token 位置 | renderer localStorage (历史) | **主进程内存, 永不出 renderer** |
| Markdown 渲染 | inline 解析 | Phase 2: streaming 时纯文本; done 后 MarkdownViewer |
| 取消 | reader.cancel() | `cancelStream(streamId)` IPC |

---

## 7. 已知项

| 项 | Desktop 处理 |
|-----|--------------|
| 流式中 401 (access 过期) | main 拿到 401, 全 session 强制 refresh; 流 abort + emit error (Phase 2 简化: 直接 error, 提示用户重发) |
| 流中断 (CancelledError) | 后端 yield `sync_required reason=aborted`; main emit error |
| `[DONE]` 标记 | main 检测到即 emit end, 无 payload |
| 后端 yield 中抛出异常 | 后端 yield `event.type=error, code=STREAM_ERROR` + 后续 `[DONE]` |
| 流式 content 含 `<script>` 等危险字符 | Phase 2 用 `<pre>` 纯文本安全; Phase 3 done 后交 MarkdownViewer 安全 render |
| 17 种 event type 全送达 | Phase 2 handle 5 种关键 (text_delta/thinking/done/error/message_persisted); 其余 acknowledge 不渲染 |

---

## Status (2026-08-21 Phase 2-Impl-3B)

- ✅ SSE transport 设计
- ✅ StreamEvent schema 对齐
- ✅ IPC streaming channel 设计
- ⏳ Phase 3: Agent tool call + RAG citation 渲染
- ⏳ Phase 3: 多模态上传
- ⏳ Phase 3: Function calling

---

📌 **维护规则**:
- 后端加新 event type → 同步更新 §3 §4 §7
- 取消 / 重连 / 401 refresh 接入 → Phase 3
- Markdown 渲染路径变化 → update §5.3
