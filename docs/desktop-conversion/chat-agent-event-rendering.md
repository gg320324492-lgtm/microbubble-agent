# Chat Agent Event Rendering (Phase 5-A)

> **目的**: Phase 5-A 落地 Agent Tool 渲染的 **基础** —— StreamEvent `tool_use` / `tool_result` / `rich_block` 的积累 + UI 展示。
> **严格范围**: 仅消费 Phase 3-B0 frozen schema, 不接 Agent backend / Tool execution / RAG / Retriever / Backend 修改。
>
> **Phase 5-A 不做的事**:
> - ❌ Agent backend / Tool execution / RAG pipeline
> - ❌ Backend schema 改动 / SSE schema 改动
> - ❌ Replay / Auto-resume / 工具调用重试
> - ❌ 工具权限 / 沙箱 / 用户授权流
> - ❌ 多 turn planning (Phase 5+)

---

## 1. 协议依据 (Phase 3-B0 frozen)

`shared/chat-types.ts` (Phase 3-B0 frozen schema, 不修改):

```ts
type StreamEventType =
  | 'text_delta' | 'thinking' | 'tool_use' | 'tool_result' | 'citation'
  | 'rich_block' | 'done' | 'error'            // 8 核心
  | 'intent_detected' | 'plan_step' | 'tool_compressed'
  | 'synthesis_start' | 'critique' | 'retry'
  | 'message_persisted' | 'sync_required'
  | 'refs' | 'suggestions'                       // 9 拓展

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
  block?: StreamRichBlock
  // ... (其他字段)
}

interface StreamRichBlock {
  type: string        // 'json' | 'markdown' | 'text' | ... (Phase 5-A 仅识别这 3 种)
  data?: unknown
  title?: string
  [k: string]: unknown
}
```

## 2. 端到端架构 (Phase 5-A)

```
[main] SSE chunk
  │
  │  data: { type: 'tool_use', tool_use_id: 'tu_1', tool_name: 'web_search', tool_input: {q: '微纳米气泡'} }
  ↓
[preload] ipcRenderer.on('chat:stream-chunk', ctx, event)
  ↓
[main.ts] 一次性注册全局 listener
  ↓
[chat store handleStreamChunk(ctx, event)]
  │
  ├─ case 'tool_use':
  │    appendToolCall({
  │      tool_use_id: 'tu_1',
  │      name: 'web_search',
  │      input: { q: '微纳米气泡' },
  │      started_at: '...',
  │      status: 'call_only',
  │      output: null, error: null, duration_ms: null,
  │      finished_at: null
  │    })
  │
  ├─ case 'tool_result':
  │    找到 tool_use_id 对应 snapshot, update:
  │      finished_at, duration_ms, output, error, status
  │      (error 字段非空 -> status='error', 否则 'success')
  │
  ├─ case 'rich_block':
  │    streamingMessage.rich_blocks.push(event.block)
  │
  └─ case sync_required / tool_use_id 缺失 / 等等 -> 静默 ack
       (不污染流, 不阻塞)

[handleStreamEnd]
  │
  └─ 写 ChatMessageOut.tool_trace = streamingMessage.tool_calls
      (向后端 type 兼容 — 完成后端 schema 接收 ToolCallSnapshot[])

[ChatView 渲染]
  │  v-for ToolCallCard(t) over tool_calls
  │  v-for ToolResultCard(t) over tool_calls.filter(t.status != 'call_only')
  │  v-for RichBlockRenderer(b) over rich_blocks
  ↓
[DOM] 用户看到 tool_use + tool_result + rich_block 完整卡片序列
```

## 3. Chat Store 改动 (Phase 5-A)

### 3.1 类型新增

```ts
// shared/chat-types.ts
type ToolCallStatus = 'call_only' | 'success' | 'error'

interface ToolCallSnapshot {
  tool_use_id: string
  name: string
  input: Record<string, unknown>
  started_at: string
  finished_at: string | null
  status: ToolCallStatus
  output: Record<string, unknown> | null
  error: string | null
  duration_ms: number | null
}

interface StreamingMessage {
  // ... (Phase 3-A 字段)
  rich_blocks: StreamRichBlock[]      // Phase 5-A: 收紧 from Record<string, unknown>[] to StreamRichBlock[]
  tool_calls: ToolCallSnapshot[]      // Phase 5-A NEW
  // ...
}

interface ChatMessageOut {
  rich_blocks: StreamRichBlock[]      // Phase 5-A: 收紧
  tool_trace: Record<string, unknown>[] // 兼容, 实际写 ToolCallSnapshot[]
  // ...
}
```

### 3.2 Handler 实现

```ts
case 'tool_use':
  // appendOnly, dedup by tool_use_id
  if (!event.tool_use_id) break
  const snap: ToolCallSnapshot = {
    tool_use_id: event.tool_use_id,
    name: event.tool_name ?? 'unknown',
    input: event.tool_input ?? {},
    started_at: new Date().toISOString(),
    finished_at: null,
    status: 'call_only',
    output: null, error: null, duration_ms: null
  }
  appendToolCall(snap)  // Map.has dedup or replace
  break

case 'tool_result':
  if (!event.tool_use_id) break
  const existing = streamingMessage.value.tool_calls.find(
    (t) => t.tool_use_id === event.tool_use_id
  )
  if (existing) {
    existing.finished_at = new Date().toISOString()
    existing.duration_ms = event.tool_duration_ms ?? null
    existing.output = event.tool_output ?? null
    existing.error = event.tool_error ?? null
    existing.status = event.tool_error ? 'error' : 'success'
  }
  break

case 'rich_block':
  if (event.block) {
    streamingMessage.value.rich_blocks.push(event.block)
  }
  break
```

### 3.3 Lifecycle

| 时刻 | tool_calls | rich_blocks |
|------|-------------|--------------|
| 创建 streamingMessage | `[]` | `[]` |
| 收 tool_use event | append call_only | — |
| 收 tool_result event | update 已有 snapshot | — |
| 收 rich_block event | — | push block |
| handleStreamEnd | 写 `tool_trace` (ChatMessageOut) | 写 `rich_blocks` (ChatMessageOut) |
| 切 session / cancel / error | 清 streamingMessage (含 tool_calls / rich_blocks) | 同步清 |

## 4. UI 组件 (Phase 5-A NEW)

### 4.1 ToolCallCard.vue

```
┌─────────────────────────────────────────────────────────┐
│ 🔧 web_search              [调用中]   42ms             │
│ ▼ 输入参数                                                 │
│   {                                                          │
│     "query": "微纳米气泡"                                 │
│   }                                                          │
└─────────────────────────────────────────────────────────┘
```

- 显示: 工具名 + status pill (调用中=黄 / 已完成=绿 / 失败=红) + duration (有则) + input JSON
- 状态 derived from snapshot.status
- 0 v-html: input JSON 走 JSON.stringify + 文本插值
- 不触发工具执行 (Phase 5-A 仅渲染)

### 4.2 ToolResultCard.vue

```
┌─────────────────────────────────────────────────────────┐
│ ✅ web_search 结果                              42ms   │
│ ▼ 输出                                                    │
│   { ... }                                                  │
└─────────────────────────────────────────────────────────┘
```

- 表示 tool_result 到达
- 错误时: 红边 + 显示 error 文本
- 输出: JSON 折叠详情
- 仅显示 status != 'call_only' 的 snapshot (有结果)

### 4.3 RichBlockRenderer.vue

```
┌─────────────────────────────────────────────────────────┐
│ 📦 Sample JSON              [json]                     │
│ {                                                          │
│   "foo": "bar"                                            │
│ }                                                          │
└─────────────────────────────────────────────────────────┘
```

按 `block.type` 分支:
| type | 渲染 |
|------|------|
| `markdown` | MarkdownViewer (Phase 2-Impl-2B 自写 parser, 0 v-html) |
| `json` | `<pre>` JSON.stringify |
| `text` | `<pre>` raw text |
| 其它 | fallback `<details>` 折叠, 显示 type label |

安全: 0 v-html (整个 Phase 5-A 范围内), 文本逐字 Vue 插值.

### 4.4 ChatView 集成

```
Assistant message (completed) / streaming:
  MarkdownViewer     (Phase 2-Impl-2B)    ← 正文 markdown
  CitationList       (Phase 3-C1+)        ← 引用列表
  ToolCallCard(s)    (Phase 5-A NEW)      ← tool_use 调用
  ToolResultCard(s)  (Phase 5-A NEW)      ← tool_result 输出
  RichBlockRenderer(s) (Phase 5-A NEW)    ← rich_block
```

普通聊天 (无 tool / rich_block) → 0 节点差异, UI 零变化.

## 5. 测试覆盖 (Phase 5-A)

`tests/unit/chat-tool-event-rendering.test.ts` — 7 cases / 5 spec 场景:

| Spec 场景 | Test | 验证 |
|----------|------|------|
| 1. tool_use 事件 | "tool_use event" | 累加 ToolCallSnapshot, status=call_only |
| 2. tool_result 事件 | "tool_result event success" + "tool_result event error" | success / error 状态 + duration + output |
| 3. rich_block 事件 | "rich_block event" | 累加 rich_blocks |
| 4. 错误 tool 状态 | "tool_result 缺 tool_use_id" + "tool_result 找不到对应" | 静默 ack, 不写 tool_calls |
| 5. 普通消息无 tool | "普通消息无 tool (Spec 5)" | text_delta 正常, tool_calls=[] |

Total: **89 tests PASSED** (Phase 3-C2 / 3-D / 4-B / 4-C / 5-A).

## 6. 关键不变量 (Phase 5-A frozen)

1. **Phase 3-B0 frozen schema 不动** — 仅消费 tool_use / tool_result / rich_block
2. **dedup by tool_use_id** — 同 id 二次 append 替换 (而非 push 重复)
3. **完整 snapshot 语义** — start + finish 时填为完整 lifecycle 数据
4. **错误静默** — 缺 tool_use_id / 找不到对应 tool_use 不抛错, 不污染流
5. **temporal 顺序** — tool_calls 数组顺序 = 后端事件顺序
6. **handleStreamEnd 持久化** — tool_calls 写 metadata.tool_trace (Phase 5-A typing)
7. **Cleared on lifecycle** — session 切换 / cancel / error 全部清 tool_calls + rich_blocks
8. **0 v-html** — 全部渲染走 Vue 文本插值 / MarkdownViewer / `<pre>` 文本
9. **JSON 序列化容错** — String(data) 兜底, 失败不抛渲染错

## 7. 已知限制 (Phase 5-A)

| 限制 | 当前 | 后续 |
|------|------|------|
| Tool 执行 | 0 (仅展示) | Phase 5+ Agent backend |
| Replay / Resume | 0 | Phase 5+ |
| Plan 视图 (plan_step event) | ack 忽略 | Phase 5+ 接 agent plan |
| Critique / Retry event | ack 忽略 | Phase 5+ |
| Suggestion chips | ack 忽略 | Phase 5+ 追问 |
| 多 tool 并行 | 数组顺序 (UI 按序) | Phase 5+ 同 timeline |
| Tool 权限 / 沙箱 | 0 (前端只渲染) | Phase 5+ 后端自治 |

## 8. 非范围 (Phase 5-A 严格)

- ❌ Agent backend / Tool execution
- ❌ Backend schema / Chat API / SSE schema 改动
- ❌ RAG / Retriever / Embedding
- ❌ 工具执行沙箱 / 用户授权
- ❌ Phase 3-B0 frozen schema 改动

## Status (2026-08-21 Phase 5-A)

- ✅ Chat store 增加 tool_calls + rich_blocks 累加
- ✅ ToolCallCard / ToolResultCard / RichBlockRenderer 三 UI 组件
- ✅ ChatView 集成 (completed + streaming 两条路径)
- ✅ 7 transition tests + 5 spec 场景
- ✅ Doc 8 节
- ❌ Phase 5+ Agent backend / Tool execution / Replay / Plan 视图 未触碰

---

📌 **维护规则 (Phase 5-A 起)**:
- 改 ToolCallSnapshot 字段 → 同步更新 store handleStreamChunk + ToolCallCard/ToolResultCard Props
- 新增 tool event 处理 → 必须 dedup by tool_use_id + 静默 ack 失败
- RichBlock 渲染分支 → 0 v-html, 文本插值或 JSON.stringify
- 改进 Phase 5+ Agent Backend 时, 必先 update §7 限制 + §8 非范围
- 任何 streamingMessage 状态清理 → lifecycle (session 切换 / cancel / error) 必须同步清 tool_calls + rich_blocks
