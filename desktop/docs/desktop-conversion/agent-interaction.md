# Agent Interaction Protocol Freeze (Phase 5-E3)

> **purpose**: User Action protocol + chat store contract + UI rendering contract frozen.
> 不修改 Phase 3-B0 frozen schema / Chat API / SSE.
> 仅消费已有 SSE events (suggestions / retry / sync_required).
> 不接 Tool execution / Agent backend / RAG / Retriever / Model Provider / Backend API.

## 1. UserAction Model (Phase 5-E frozen)

```ts
type UserActionType = 'suggestion' | 'retry' | 'confirm' | 'cancel' | 'sync'

interface UserAction {
  id: string
  label: string
  type: UserActionType
  payload?: Record<string, unknown>
  disabled?: boolean
}
```

### 1.1 5 actions (Phase 5-E frozen)

| type | source | UI | emit channel |
|------|------|------|---------------|
| suggestion | SSE event `suggestions` | question chip | `action` |
| retry | SSE event `retry` / failure-derived | retry button | `retry` |
| cancel | flow cancel / UI button | cancel button | `cancel` |
| confirm | Phase 6+ permission / high-risk | confirm button | `action` |
| sync | SSE event `sync_required` derived | reload button | `sync` |

### 1.2 工厂 (utils/agent-interaction.ts)

```ts
suggestionAction(id, label, payload?)   // type='suggestion'
retryAction(id, label='重试')             // type='retry'
cancelAction(id, label='取消')             // type='cancel'
confirmAction(id, label, payload?)        // type='confirm'
syncAction(id, label='重新加载')            // type='sync'
```

### 1.3 parseSuggestions (Phase 5-E: SSE event.suggestions -> UserAction[])

```ts
parseSuggestions(input: unknown): UserAction[]
```

- string[] -> suggestionAction (id=`s_${i}`)
- object[] -> use `text`/`label` field; missing id fallback `s_${i}`
- invalid entries (null / undefined / non-string) skipped
- non-array input -> []

### 1.4 mergeUserActions

```ts
mergeUserActions(a, b): UserAction[]  // dedup by id, first occurrence wins
```

### 1.5 summarizeUserActions

Returns 5-category counts: total / suggestion / retry / confirm / cancel / sync.

## 2. SSE event -> action flow (Phase 5-E frozen)

| SSE event | chat store handler | action type appended |
|-----------|-------------------|----------------------|
| `suggestions` | `parseSuggestions(event.suggestions)` | suggestionAction x N |
| `retry` | `mergeUserActions([retryAction(now)])` | retryAction x 1 |
| `sync_required` | `mergeUserActions([syncAction(now)])` + `handleStreamError` | syncAction x 1 |

Notes:
- **dedup by id**: `mergeUserActions` ensures same id dedup; first occurrence wins
- **fail silently**: invalid entries / parse failures dropped (no throw)
- **session isolation**: each new SSE chunk runs `streamStaleCheck` first (activeStreamId + currentSessionId match); mismatched chunks discarded

## 3. pendingActions lifecycle (Phase 5-E session isolation)

`pendingActions: ref<UserAction[]>([])` lives in chat store. Lifecycle reset points:

| trigger | code | effect |
|---------|------|--------|
| `sendUserMessageStream` entry | `pendingActions.value = []` | new stream starts fresh |
| `selectSession` switch | `pendingActions.value = []` | session isolation (Phase 5-E strict) |
| `cancelActiveStream` | `pendingActions.value = []` | cancel clears stale hints |
| `handleStreamError` | `pendingActions.value = []` | error stream clears stale hints |

### 3.1 flow diagram

```
[main] SSE chunk (suggestions / retry / sync_required)
   ↓
[preload] ipcRenderer.on('chat:stream-chunk', ctx, event)
   ↓
[main.ts] 一次性注册全局 listener
   ↓
[chat store handleStreamChunk(ctx, event)]
   ├─ streamStaleCheck (ctx.sessionId === currentSessionId + activeStreamId === ctx.streamId)
   ├─ case 'suggestions' | 'retry' | 'sync_required' -> append pendingActions
   └─ (others pass through)
   ↓
[ChatView <AgentActionCard v-for='a in streamingActions'>]
   ↓
user click -> onAgentAction / onAgentRetry / onAgentCancel / onAgentSync
   ├─ retry    -> store.retryLastMessage() (Phase 3-A existing path)
   ├─ cancel   -> store.cancelActiveStream() (Phase 3-A existing path)
   ├─ sync     -> store.selectSession(currentSessionId) (Phase 6 upgrade to listMessages)
   └─ action   -> suggestion / confirm (Phase 6+ payload + permission modal)
```

## 4. Session isolation (Phase 5-E strict)

- `pendingActions` lives in `useChatStore` (Pinia module-level singleton)
- Lifecycle reset points above ensure **no stale hints leak across sessions**
- AgentActionCard hidden by default (ChatView v-if `streamingActions.length > 0`)
- Pending actions only render in **current streaming message context**

## 5. UI rendering contract (Phase 5-E frozen)

### 5.1 AgentActionCard.vue (5 variants)

| type | icon | background | color | border |
|------|------|-----------|-------|--------|
| suggestion | 💬 | purple | `#d8b4fe` | `rgba(168,85,247,0.3)` |
| retry | 🔁 | blue | `#c7d2fe` | `rgba(99,102,241,0.3)` |
| confirm | ✔ | cyan | `#5eead4` | `rgba(16,185,129,0.4)` |
| cancel | ✖ | red | `#fca5a5` | `rgba(239,68,68,0.3)` |
| sync | ⟳ | orange | `#fcd34d` | `rgba(245,158,11,0.3)` |

`disabled=true`: opacity 0.5 + cursor not-allowed.

### 5.2 ChatView 渲染位置

```
Assistant message (streaming):
  Markdown (Phase 2-Impl-2B)
  ↓
  TraceTimeline (Phase 5-B)
  ↓
  PlanTimeline (Phase 5-D)
  ↓
  CitationList (Phase 3-C1+)
  ↓
  AgentActionCard(s)   ← Phase 5-E2 NEW
```

Phase 5-E2: 普通消息 `streamingActions.length === 0` 时不渲染 (0 节点差异).

## 6. confirm 扩展设计 (Phase 6+)

| Phase | spec |
|-------|------|
| 5-E3 (current) | 仅 console.info 占位 |
| 6+ | 接权限弹窗 / onAgentConfirm 调用 modal -> 用户点击确认后调用 backend permission API |

### 6.1 confirm event 触发 (Phase 6+)

后端 SSE 新增 `confirm_required` event 携带 `{ confirm_id, action: 'high_risk_op', payload: { ... } }`. Desktop 解析后:

```ts
// Phase 6+ 设计
const confirm = confirmAction(confirm_id, '是否确认高风险操作?', {
  action: 'high_risk_op',
  payload: ...
})
```

### 6.2 confirm UI 流程 (Phase 6+)

```
user click confirm -> AgentActionCard emit('action', { type: 'confirm' })
   ↓
ChatView.onAgentAction -> confirm modal
   ↓
用户点击确认 -> 调用 backend API
   ↓
成功后流继续 / 失败后 error
```

## 7. sync 扩展设计 (Phase 6+)

| Phase | spec |
|-------|------|
| 5-E2 (current) | Phase 3-A `selectSession(currentSessionId)` reload 全段 |
| 6+ | `listMessages(sessionId, { afterId, limit })` 增量拉取 |

### 7.1 sync event 增量实现 (Phase 6+)

```ts
// Phase 6+ 设计
const syncMessage = syncAction(sync_id, '加载新消息')
// store.onAgentSync -> listMessages(sessionId, { afterId: lastMessageId })
```

### 7.2 sync 流整合

```
sync_required event -> pendingActions sync 卡片
user click sync -> ChatView.onAgentSync
   ↓
store.listMessages(sessionId, afterId=lastMessageId)
   ↓
新消息追加到 store.messages
```

## 8. Phase 6 Agent Runtime 留口

| 组件 | 留口 |
|------|------|
| confirm action | permission modal + backend API |
| sync action | listMessages incremental |
| suggestion action | sendUserMessageStream payload (Phase 6+ 复用 Phase 3-A send) |
| i18n | zh-CN hardcoded 当前; Phase 6+ i18n 框架 |
| multi-window | Phase 6+ 跨 window store sync (SharedWorker) |

## 9. 协议冻结 (Phase 5-E3 frozen)

- 5 actions type frozen
- pendingActions lifecycle frozen
- SSE event -> action mapping frozen
- AgentActionCard 5 variants + emit channels frozen
- ChatView 渲染位置 frozen (Markdown -> Trace -> Plan -> Citations -> AgentActionCard)

后续修改需新增 Phase 5-E4+ 版本号 + 重新冻结.

## 10. References

- `renderer/src/renderer/src/utils/agent-interaction.ts` — UserAction 模型 + 工厂 + parseSuggestions + mergeUserActions + summarizeUserActions
- `renderer/src/renderer/src/stores/chat.ts` — pendingActions + 3 SSE case handlers + 4 lifecycle reset
- `renderer/src/renderer/src/components/chat/AgentActionCard.vue` — 5 variants UI
- `renderer/src/renderer/src/views/ChatView.vue` — onAgentRetry / onAgentCancel / onAgentSync / onAgentAction handlers + streamingActions 渲染
- `tests/unit/agent-interaction.test.ts` — Phase 5-E1 (9 cases)
- `tests/unit/agent-interaction-runtime.test.ts` — Phase 5-E2 (12 cases)

## Status (2026-08-22 Phase 5-E3)

- ✅ Doc 落地 (UserAction / 5 actions / SSE flow / lifecycle / session isolation / UI contract / confirm 扩展 / sync 扩展 / Phase 6 留口)
- ✅ Protocol frozen (5 actions + lifecycle + emit channels)
- ✅ 引用文档 (Phase 5-E1 + 5-E2 + 5-E3 三阶段合并)
- ⏸ Phase 6+ confirm / sync / suggestion 完整实现留口

---

Maintenance rules (Phase 5-E3+):
- 不修改 Phase 3-B0 frozen SSE schema
- 修改 5 actions type -> 必须同步 utils/agent-interaction.ts + AgentActionCard + chat store + 4+ tests
- pendingActions lifecycle reset points 4 处固定: sendUserMessageStream / selectSession / cancelActiveStream / handleStreamError
- confirm / sync handler MUST 复用已有路径或 Phase 6+ 留口 (Phase 5-E3 不实现)
- 写新 doc 必须先 update §10 References
</content>
