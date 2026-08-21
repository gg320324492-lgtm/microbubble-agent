# Agent State Model (Phase 5-C)

> **目的**: Agent State Model Foundation —— 推导 Desktop Chat Assistant 当前的 Agent 状态 (idle / thinking / planning / tool_running / waiting_user / completed / failed)。
> **不接** Agent backend / Tool execution / RAG / Retriever / Backend。
> **不修改** Phase 3-B0 frozen schema / Chat API / SSE。
>
> **范围**:
> - AgentState 类型 (7 states, Phase 5-C frozen)
> - deriveAgentState 纯函数 (utils/agent-state.ts)
> - chat store 集成 agentStateHint computed
> - AgentStatusBadge.vue UI 组件
> - 6 spec 场景单测 (20 cases)
> - Doc
>
> **不范围**:
> - ❌ Agent backend / Tool execution / RAG / Retriever
> - ❌ Backend schema / Chat API / SSE schema 改动
> - ❌ 工具权限 / 沙箱 / 用户授权
> - ❌ 真实 multi-turn planning (Phase 5+)

---

## 1. 状态机 (Phase 5-C frozen)

```
        ┌──────────────────────────────────────┐
        │      idle (默认 / 起始)                  │
        └──────────────────────────────────────┘
              ↑↓ thinking ← (label 非空)
              ↑↓ tool_running ← (call_only tool)
              ↑↓ failed ← (lastError / tool_error)
              ↑↓ completed ← (流结束 + content)
              ↑↓ planning / waiting_user  (Phase 5+ 留口)
```

7 状态:

| state | 触发条件 | 备注 |
|-------|---------|------|
| `idle` | 默认 (无 streaming activity) | Phase 5-C 起始态 |
| `thinking` | `isStreaming=true` + `streamingMessage.thinking` 非空 | thought label 存在 |
| `planning` | 留口 | Phase 5+ 接 plan_step event 后启用 |
| `tool_running` | `isStreaming=true` + 任何 tool_call status=`call_only` | 等待 tool_result |
| `waiting_user` | 留口 | Phase 5+ 接权限 / 追问事件后启用 |
| `completed` | `isStreaming=false` + `streamingMessage.content` 非空 | 流结束, 有结果 |
| `failed` | `lastError` 存在 OR tool_result.error | 异常退出 |

## 2. deriveAgentState (Phase 5-C frozen)

### 2.1 优先级

```
1. failed
2. tool_running (流中 + call_only)
3. thinking (流中 + thinking label)
4. completed (流结束 + content 非空)
5. idle (默认)
```

### 2.2 状态派生代码

```ts
function deriveAgentState(input: DeriveAgentStateInput = {}): AgentState {
  // 1. failed
  if (lastError) return 'failed'

  // 2. tool_running (流中 + 任何 call_only 工具)
  if (isStreaming && sm) {
    if (sm.tool_calls.some((t) => t.status === 'call_only')) return 'tool_running'
  }

  // 3. thinking
  if (isStreaming && sm) {
    const t = (sm.thinking ?? '').trim()
    if (t.length > 0) return 'thinking'
  }

  // 4. completed (流已结束 + 有内容)
  if (!isStreaming) {
    if (sm.content.trim().length > 0) return 'completed'
  }

  // 5. idle
  return 'idle'
}
```

### 2.3 状态图标 + 标签

```ts
AGENT_STATE_LABELS = {
  idle: '空闲',
  thinking: '思考中',
  planning: '规划中',
  tool_running: '执行工具',
  waiting_user: '等待用户',
  completed: '已完成',
  failed: '失败'
}

AGENT_STATE_ICONS = {
  idle: '○',
  thinking: '💭',
  planning: '🧭',
  tool_running: '🔧',
  waiting_user: '⏸',
  completed: '✅',
  failed: '❌'
}
```

### 2.4 AgentStateHint (UI 显示控制)

```ts
export interface AgentStateHint {
  state: AgentState
  label: string
  icon: string
  visible: boolean  // 流中 / failed / completed 短暂显示
}
```

`deriveAgentStateHint(input)`:
- 流中 (isStreaming=true) → visible=true
- 普通 idle / completed → visible=false (除 completed 临时显示)
- failed → visible=true (always)

## 3. 组件 (Phase 5-C NEW)

### 3.1 AgentStatusBadge.vue

```vue
<AgentStatusBadge :hint="store.agentStateHint" />
```

渲染状态徽章:
- 流中 thinking: 黄色徽章 + 脉冲动画
- 流中 tool_running: 紫色徽章 + 脉冲
- failed: 红色徽章
- 其它: 不显示 (v-if false)

## 4. ChatView 集成

```
Assistant message (completed):
  ┌──────────────────────────────────┐
  │ [avatar] 小气  [AgentStatusBadge]  14:30  │  ← Phase 5-C NEW
  │ Markdown content                    │
  │ ...                                │
  └──────────────────────────────────┘

Assistant message (streaming):
  ┌──────────────────────────────────┐
  │ [avatar] 小气  [AgentStatusBadge: 🔧 执行工具]  流式中...  │  ← Phase 5-C NEW
  │ Markdown content                    │
  │ ...                                │
  └──────────────────────────────────┘
```

普通消息 (idle): 不显示 badge (visible=false).

## 5. 单测覆盖 (Phase 5-C, 20 cases / 6 spec 场景)

`tests/unit/agent-state-model.test.ts`:

| describe / Spec 场景 | cases | 覆盖 |
|---------------------|-------|------|
| Spec 1: idle | 3 | 空输入 / 无 streamingMessage / 空 content |
| Spec 2: thinking | 3 | thinking label + isStreaming / thinking 但 !isStreaming / thinking 空白 trim |
| Spec 3: tool_running | 4 | 1 call_only / mixed success+call_only / 全 success / 优先级 > thinking |
| Spec 4: failed | 2 | lastError 存在 / 优先级 > tool_running |
| Spec 5: completed | 3 | content 非空 + !isStreaming / thinking 历史 / content 空 |
| Spec 6: session isolation | 4 | 切 session 异 hint 流中 / idle 隐 / completed 短显 |
| AGENT_STATE_LABELS / ICONS | 1 | 7 states 都有 label + icon |

### 5.1 单独 verify

- chat store `agentStateHint` computed 跨 session 隔离: streamingMessage 切换时, `deriveAgentStateHint` 自动重算 (Phase 4-C selectSession 清 streamingMessage)
- 流中 vs 历史: `isStreaming` 区分

## 6. 关键不变量 (Phase 5-C frozen)

1. **Phase 3-B0 frozen schema 不动** — 仅消费 streamingMessage / isStreaming / lastError
2. **7 states 冻结** — 不增不减; planning / waiting_user 留口不实现
3. **纯函数** — deriveAgentState 0 副作用, 0 依赖
4. **优先级固定** — failed > tool_running > thinking > completed > idle
5. **session 隔离** — agentState 是 computed (派生), 自动跟随 streamingMessage / isStreaming 变化
6. **0 v-html** — AgentStatusBadge 全部 Vue 文本插值
7. **UI 条件显示** — visible=false (idle / 普通) 不渲染, 0 节点差异
8. **失败不抛** — 缺字段时返回 idle (退化)

## 7. 已知限制 (Phase 5-C)

| 限制 | 当前 | 后续 |
|------|------|------|
| planning / waiting_user | 0 推导 (留口) | Phase 5+ 接 plan_step / 权限 / 追问事件 |
| 状态历史 | 0 (单点 derive) | Phase 5+ 时序 transition (FSM) |
| 状态机转换 | 0 | Phase 5+ on(state) enter / exit 钩子 |
| multi-turn 规划 | 0 | Phase 5+ |
| 自定义 icon (per-project) | 固定 | Phase 5+ theme |
| i18n | 中文化 hardcoded | Phase 5+ i18n |

## 8. 非范围 (Phase 5-C 严格)

- ❌ Agent backend / Tool execution / RAG / Retriever
- ❌ Backend schema / Chat API / SSE schema 改动
- ❌ 工具执行沙箱 / 用户授权
- ❌ 改动 Phase 5-A / 5-B 已 frozen 设计

## Status (2026-08-21 Phase 5-C)

- ✅ AgentState 类型 (7 states frozen)
- ✅ deriveAgentState 纯函数 (utils/agent-state.ts)
- ✅ deriveAgentStateHint (UI 提示)
- ✅ chat store agentStateHint computed (session 隔离自然)
- ✅ AgentStatusBadge.vue (脉冲动画 / 颜色)
- ✅ ChatView 集成 (completed + streaming 两条路径)
- ✅ 20 单测 + 6 spec 场景
- ✅ Doc 8 节
- ❌ Phase 5+ Agent backend / multi-turn / Replay 未触碰

---

📌 **维护规则 (Phase 5-C 起)**:
- 改 AgentState 类型 → 同步更新 AGENT_STATE_LABELS / ICONS + 派生函数 + 5 cases 测试
- 改优先级 → 必保持 failed > tool_running > thinking > completed > idle (Phase 5-C frozen)
- 新增 AgentState → 必含: 状态本身 + label + icon + visible judgment + 3 边界测试
- 改 AgentStatusBadge 视觉 → 保持 0 v-html + 颜色对比 (可访问性)
- planning / waiting_user 状态 → 留 Phase 5+ 接入事件后启用, 不在 Phase 5-C 强行推
- 改 streamingMessage shape → 不在 Phase 5-C 范围 (Phase 5-A 维护)
- 维护规则 spec §5 6 场景 + 边界 + 集成测试
