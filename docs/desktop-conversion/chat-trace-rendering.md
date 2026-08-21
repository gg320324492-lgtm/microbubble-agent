# Chat Trace Timeline Rendering (Phase 5-B)

> **目的**: Agent Timeline / Trace Renderer —— 把 Assistant 消息的若干分散事件 (thinking / tool_use / tool_result / citation / rich_block) 统一展示为时间线。
> **不修改** Phase 3-B0 frozen schema; **不接** Agent backend / Tool execution / RAG / Retriever。
>
> **范围**:
> - TraceItem 数据模型 (utils/chat-trace.ts)
> - TraceTimeline 组件 (collapsed 默认)
> - ChatView 集成 (completed 消息默认 collapsed, 流中默认 expanded)
> - 单测 5 场景 + 24 cases
> - Doc
>
> **不范围**:
> - ❌ Agent backend / Tool execution / RAG / Retriever
> - ❌ Backend schema / Chat API / SSE schema 改动
> - ❌ 工具执行沙箱 / 用户授权
> - ❌ 多 turn planning (Phase 5+)
> - ❌ Agent 状态机 (Phase 5+)

---

## 1. 协议依据 (Phase 3-B0 frozen)

`shared/chat-types.ts` (Phase 3-B0 frozen, 不修改):

```ts
// Phase 5-A 加 (Phase 5-B 复用):
StreamingMessage {
  thinking: string | null
  rich_blocks: StreamRichBlock[]
  tool_calls: ToolCallSnapshot[]
  citations: StreamCitationEntry[]
  content: string
}

ChatMessageOut {
  rich_blocks: StreamRichBlock[]
  tool_trace: Record<string, unknown>[]
  message_metadata: { thinking?: string, citations?: StreamCitationEntry[] }
  content: string
}
```

## 2. Trace Model (Phase 5-B)

### 2.1 设计思路

- 单源: 复用 StreamingMessage / ChatMessageOut 的现有字段
- 纯函数: utils/chat-trace.ts 是 0 依赖模块, 测试无 DOM
- 时间线 frozen: 顺序固定为 thinking → tool_call → tool_result → citation → rich_block → answer

### 2.2 TraceItem 类型 (dataclass.ts)

```ts
type TraceItemKind = 'thinking' | 'tool_call' | 'tool_result' | 'citation' | 'rich_block' | 'answer'

interface ThinkingTraceItem     { kind: 'thinking'; label: string; order: number }
interface ToolCallTraceItem     { kind: 'tool_call'; tool: ToolCallSnapshot; order: number }
interface ToolResultTraceItem   { kind: 'tool_result'; tool: ToolCallSnapshot; order: number }
interface CitationTraceItem     { kind: 'citation'; citation: StreamCitationEntry; order: number }
interface RichBlockTraceItem    { kind: 'rich_block'; block: StreamRichBlock; order: number }
interface AnswerTraceItem       { kind: 'answer'; content: string; order: number; partial?: boolean }

type TraceItem = ThinkingTraceItem | ToolCallTraceItem | ToolResultTraceItem | CitationTraceItem | RichBlockTraceItem | AnswerTraceItem
```

### 2.3 buildTrace 主入口

```ts
function buildTrace(input: BuildTraceInput): TraceItem[]
```

构造顺序:
1. thinking (1 个, 若存在)
2. tool_calls (按存储顺序, 每个 tool_call 后跟 tool_result 若 status != 'call_only')
3. citations (按存储顺序)
4. rich_blocks (按存储顺序)
5. answer (1 个, 若存在)

失败 / 缺字段: 静默跳过 (dropEmpty 默认 true).

`buildTraceFromMessage(msg)` 从 ChatMessageOut 提取 (compatibility cast).

## 3. TraceTimeline 组件 (Phase 5-B NEW)

### 3.1 行为

```
Phase 5-B:
  completed message -> defaultCollapsed=true (显示 summary)
  streaming message -> defaultCollapsed=false (实时展开)
  user 点击 head -> 折叠 / 展开
```

### 3.2 视觉

```
┌─────────────────────────────────────────────────────────┐
│ ▶ 展开 Trace                                            │
│   💭 thinking · 🔧 2 tools · 📚 1 citation           │  (collapsed summary)
└─────────────────────────────────────────────────────────┘

↓ 展开后

┌─────────────────────────────────────────────────────────┐
│ ▼ 收起 Trace                                            │
├─────────────────────────────────────────────────────────┤
│ 💭 分析用户意图                                          │
│ 🔧 web_search  [调用中]   1200ms                       │
│   ▼ 输入参数                                            │
│     { "query": "微纳米气泡" }                          │
│ ✅ web_search 结果  1200ms                              │
│   ▼ 输出                                               │
│     { "results": [...] }                                │
│ 📚 引用 1 条                                            │
│ ▼ 微纳米气泡机理研究综述                                │
│   微纳米气泡是指直径小于 1 微米...                       │
└─────────────────────────────────────────────────────────┘
```

### 3.3 折叠逻辑

- `collapsed` 由 ref 控制
- head 显示 ▶ / ▼ + 标题 (展开/收起 Trace) + summary only (collapsed)
- body 显示所有 TraceItem 按 order 顺序
- 各 item kind 派发到对应组件:
  - thinking → `.trace-item--thinking` (黄条)
  - tool_call → ToolCallCard
  - tool_result → ToolResultCard
  - citation → CitationList (单条数组)
  - rich_block → RichBlockRenderer
  - answer → MarkdownViewer (Phase 2-Impl-2B 复用)

## 4. ChatView 集成

```
Assistant message (completed):
  MarkdownViewer     (Phase 2-Impl-2B)
  CitationList       
  ToolCallCard(s)    
  ToolResultCard(s)  
  RichBlockRenderer(s)
  TraceTimeline       ← Phase 5-B NEW (defaultCollapsed=true)
  attachments

Assistant message (streaming):
  ...
  TraceTimeline       ← Phase 5-B NEW (defaultCollapsed=false)
                       (active stream, leak实时)
```

普通消息 (无 tool/citation/rich_block/thinking): TraceTimeline 渲染空内容 → v-if 短路 → 0 节点差异.

## 5. 单元测试 (Phase 5-B, 24 cases / 5 spec 场景 + 鲁棒 + summary)

`tests/unit/chat-trace-rendering.test.ts`:

| describe / Spec 场景 | cases | 覆盖 |
|---------------------|-------|------|
| Spec 1: trace 生成 | 5 | thinking / tool_call+result / call_only 不派生 result / success+error 都派生 / rich_block 累加 / answer 末尾 |
| Spec 2: 事件排序 | 2 | order 单调递增 / 多 tool 顺序与输入一致 |
| Spec 3: 空 trace | 5 | 空输入 / 空字符串 / null / 空数组 / dropEmpty: false |
| Spec 4: 普通消息无 trace | 2 | 只 answer / 0 额外 kinds |
| Spec 5: tool 失败 trace | 2 | status=error 仍派生 / mixed success+error |
| 鲁棒性 | 3 | 缺 tool_use_id / NaN citation / 空 type rich_block |
| summarizeTrace + formatTraceSummary | 2 | 全 0 / 完整 |
| buildTraceFromMessage | 2 | 完整 metadata 提取 / 空 metadata 非空 rich_blocks |

Total: **24 cases PASSED** (spec 5 场景 + 鲁棒 + summary + msg 输入).

## 6. 关键不变量 (Phase 5-B frozen)

1. **Phase 3-B0 frozen schema 不动** — 仅消费现有字段
2. **顺序固定** — thinking → tool_call/tool_result → citation → rich_block → answer
3. **0 依赖** — utils/chat-trace.ts 纯 TS, 不引第三方
4. **dedup by tool_use_id** — 复用 Phase 5-A store 行为
5. **失败静默** — 缺字段 / 非法 entry 跳过, 不抛
6. **dropEmpty 默认 true** — 普通消息 0 节点差异
7. **component 复用** — TraceTimeline 复用 ToolCallCard / ToolResultCard / CitationList / RichBlockRenderer / MarkdownViewer
8. **Collapse UX** — completed 默认 collapsed, 流中 expanded

## 7. 已知限制 (Phase 5-B)

| 限制 | 当前 | 后续 |
|------|------|------|
| thinking 字段 | Single string (Phase 3-A 限制, 后端 emit 单条) | Phase 5+ 后端 multi-thinking event |
| tool 顺序 | 数组顺序 (SSE arrive order) | Phase 5+ 时间戳精确控制 |
| 折叠默认 | completed=collapsed, streaming=expanded | Phase 5+ 用户偏好设置 |
| 展开动画 | 0 (硬切) | Phase 5+ CSS transition |
| Phase 5-B 不改 schema | — | Phase 5+ 加 stream group event, 嵌套 trace |
| 日志 / metrics | 0 | Phase 5+ telemetry hook |

## 8. 非范围 (Phase 5-B 严格)

- ❌ Agent backend / Tool execution / RAG / Retriever
- ❌ Backend schema / Chat API / SSE schema 改动
- ❌ 工具执行沙箱 / 用户授权
- ❌ 改 Phase 3-B0 frozen citation / tool schema

## Status (2026-08-21 Phase 5-B)

- ✅ TraceItem 数据模型 (utils/chat-trace.ts)
- ✅ TraceTimeline 组件 (collapsed / expanded)
- ✅ ChatView 集成 (completed + streaming 两条路径)
- ✅ 24 transition tests + 5 spec 场景
- ✅ Doc 8 节
- ❌ Phase 5+ Agent backend / Replay / Plan 视图未触碰

---

📌 **维护规则 (Phase 5-B 起)**:
- 改 TraceItem 类型 → 同步 buildTrace + buildTraceFromMessage + TraceTimeline 三处
- 新增 kind → TraceTimeline 加 v-if 分支 + 在 i18n 准备 (Phase 5+)
- buildTrace 修顺序 → 必保持 thinking → tool_call/tool_result → citation → rich_block → answer (Phase 5-B 冻结)
- 跑现有 buildTraceFromMessage 单测确认 Phase 5-A 行为不退化
- 改 TraceTimeline collapse 行为 → 必保持 completed=collapsed, streaming=expanded 默认
- 维护 spec §5 5 场景 + 鲁棒 + summary 测试
