# Agent Plan Rendering (Phase 5-D)

> **目的**: Agent Planning Renderer Foundation —— 消费 Phase 3-B0 frozen SSE `plan_step` 事件, 建立 Desktop 展示层。
> **不接** Agent planner / Tool execution / Permission / RAG / Retriever / Backend。
> **不修改** Phase 3-B0 frozen schema / Chat API / SSE。
>
> **范围**:
> - PlanStep 模型 (utils/agent-plan.ts, Phase 5-D frozen)
> - Chat store 接 plan_step event (按 step.id dedup)
> - PlanTimeline.vue UI 组件
> - 联动 AgentState (running plan step -> 'planning')
> - 22 单测 + 5 spec 场景
> - Doc
>
> **不范围**:
> - ❌ Agent planner / Tool execution / RAG / Retriever
> - ❌ Backend schema / Chat API / SSE schema 改动
> - ❌ 工具权限 / 沙箱 / 用户授权
> - ❌ multi-turn planning / Agent 状态机

---

## 1. 协议依据 (Phase 3-B0 frozen)

`shared/chat-types.ts` (Phase 3-B0 frozen, 不修改):

```ts
// StreamEventType 含 plan_step (Phase 3-B0 frozen union 已含, Phase 5-D 仅消费)
type StreamEventType = ... | 'plan_step' | ...

// 注释 (Phase 3-B0 doc):
//   plan_step  [snapshot] 工具规划单步，含 step/tool/status（pending/running/done）
```

`shared/chat-types.ts` (Phase 5-D 增量, 非 frozen schema):
```ts
interface PlanStep {  // Phase 5-D: shared 边界 (main + renderer 都可读)
  id: string
  title: string
  status: 'pending' | 'running' | 'completed' | 'failed'
  order: number
  tool?: string
  started_at?: string | null
  finished_at?: string | null
  error?: string | null
}

StreamingMessage {
  plan_steps?: PlanStep[]   // 流中累积
}
```

## 2. PlanStep 模型 (Phase 5-D frozen)

### 2.1 类型

```ts
type PlanStepStatus = 'pending' | 'running' | 'completed' | 'failed'

interface PlanStep {
  id: string           // 后端 SSE event.step.id (key for dedup)
  title: string
  status: PlanStepStatus
  order: number        // 确定性顺序 (Phase 5-D 简化: 数组索引)
  tool?: string        // Phase 5-D 留口 (后端 emit.step.tool)
  started_at?: string | null
  finished_at?: string | null
  error?: string | null
}
```

### 2.2 工厂方法

```ts
pendingStep(id, title, order, tool?)         // status='pending'
runningStep(prev, started_at?)                // status='running', set started_at
completedStep(prev, finished_at?)              // status='completed'
failedStep(prev, error, finished_at?)           // status='failed', set error
```

### 2.3 parsePlanStepEvent (Phase 5-D 解析 SSE event payload)

```ts
parsePlanStepEvent({ id, title?, tool?, status? }, order): PlanStep | null
```

Status 映射 (后端 schema 异构兼容):
- `pending`   -> 'pending'
- `running`   -> 'running'
- `done` / `completed` -> 'completed'
- `failed` / `error` -> 'failed'
- undefined / 其它 -> 'pending'

返回 null 当缺 `id` (Phase 5-D 跳过非法 entry).

## 3. Store 集成 (Phase 5-D)

`renderer/src/renderer/src/stores/chat.ts`:

```ts
const planSteps = ref<PlanStep[]>([])

// handleStreamChunk case 'plan_step':
case 'plan_step':
  const stepData = (event as unknown as { step?: { id?: string; ... } }).step
  if (!stepData || typeof stepData !== 'object') break
  if (!stepData.id) break
  const parsed = parsePlanStepEvent(...)
  if (!parsed) break
  planSteps.value = appendPlanStep(planSteps.value, parsed)
  // 同步 streamingMessage.plan_steps (ChatView 直接读)
  if (streamingMessage.value) {
    streamingMessage.value.plan_steps = planSteps.value
  }
  break

// 流结束清理
handleStreamEnd / handleStreamError:
  planSteps.value = []  // session 隔离 (Phase 4-C selectSession 同步)
```

**session 隔离**: pinia module-level singleton; planSteps 由 handleStreamEnd / handleStreamError / selectSession 同步清。

## 4. PlanTimeline 组件 (Phase 5-D NEW)

`renderer/src/renderer/src/components/chat/PlanTimeline.vue` (~150 行):

### 4.1 Props

```ts
interface Props {
  steps: PlanStep[]
}
```

### 4.2 渲染规则

- 空 steps: `<div v-if="!isEmpty">` -> 不渲染 (普通消息 0 节点差异)
- 非空: 显示 "🧭 Agent Plan · N 步" 头部 + ordered `<ol>` 列表

### 4.3 视觉

```
┌─────────────────────────────────────────────────────────┐
│ 🧭 Agent Plan                              3 步        │
├─────────────────────────────────────────────────────────┤
│ ▶ Step 1 搜索文献                          [web_search]│
│ ▶ Step 2 数据分析                          [analyze]    │
│ ✓ Step 3 写报告                                        │
└─────────────────────────────────────────────────────────┘
```

- **pending**: `○` 灰色
- **running**: `▶` 紫色 + pulse 动画
- **completed**: `✓` 绿色
- **failed**: `❌` 红色 + error 字段

## 5. AgentState 联动 (Phase 5-D + Phase 5-C)

```ts
// agent-state.ts
export function planStepsToAgentState(steps: PlanStep[]): AgentState | null {
  if (steps.length === 0) return null
  if (steps.some((s) => s.status === 'failed')) return 'failed'
  if (steps.some((s) => s.status === 'running' || s.status === 'pending')) return 'planning'
  if (steps.every((s) => s.status === 'completed')) return 'completed'
  return null
}
```

**chat store agentStateHint computed** (Phase 5-C + 5-D 联动):
```ts
const agentStateHint = computed<AgentStateHint>(() => {
  const planState = planStepsToAgentState(planSteps.value)
  if (planState) {
    // 优先返回 plan 推导 (planning / failed / completed)
    const base = deriveAgentStateHint({...})
    return { state: planState, ...base }
  }
  return deriveAgentStateHint({...})  // 回退到 Phase 5-C 推导
})
```

## 6. ChatView 集成

```vue
<PlanTimeline
  v-if="planSteps && planSteps.length > 0"
  :steps="planSteps"
/>
```

- 流中: 实时呈现 (Step 1 running -> Step 2 pending -> Step 3 pending 等)
- 完成 / cancel / session 切换: 清空, 不渲染
- 普通消息 (无 plan): 0 节点差异

## 7. 单元测试 (Phase 5-D, 22 cases / 5 spec 场景)

`tests/unit/agent-plan-rendering.test.ts`:

| describe / Spec 场景 | cases | 覆盖 |
|---------------------|-------|------|
| Spec 1: append + dedup | 3 | pendingStep 字段 / appendPlanStep + dedup / 不修改入参 |
| Spec 2: status update | 2 | pending -> running -> completed; running -> failed |
| Spec 3: order 排序 | 1 | plan_steps 按 order 排序 |
| parsePlanStepEvent | 7 | done / running / failed / error / undefined / 缺 id / order |
| Spec 4: failed step | 2 | summarizePlanSteps 混合 + 空 |
| planStepsToAgentState | 5 | 空 / failed / running / pending / all completed |
| 边界 (Spec 5) | 2 | pendingStep 无 tool / 空 list -> empty UI |

Total: **22 / 22 PASSED**

修了 1 处 TS strict: chat-types.ts 缺 `PlanStep` interface (PlanStep 在 utils/agent-plan.ts 中, shared 边界需 inline 镜像).

## 8. 关键不变量 (Phase 5-D frozen)

1. **Phase 3-B0 frozen schema 不动** — 仅消费 `plan_step` event
2. **PlanStep 7 状态 frozen** — pending / running / completed / failed (无 pending split)
3. **dedup by step.id** — 同 id 替换, last wins
4. **顺序 frozen** — order 字段确定性
5. **失败静默** — 缺 id / 非法 entry 跳过, 不抛
6. **session 隔离** — planSteps 由 lifecycle 同步清 (Phase 4-C 沿用)
7. **0 v-html** — PlanTimeline 全部 Vue 文本插值
8. **AgentState 联动** — running/pending/failed 优先返回, 回退到 Phase 5-C 推导
9. **普通消息 0 节点差异** — v-if 短路 + 空 list 处理

## 9. 已知限制 (Phase 5-D)

| 限制 | 当前 | 后续 |
|------|------|------|
| planning / waiting_user 仍依赖 plan_step event | 0 主动 planner | Phase 5+ |
| PlanStepSchema field 名 `tool` 等 | Phase 3-B0 注释引用 | Phase 5+ backend schema 对齐 |
| PlanStepState GraphView (DAG) | 顺序列表 | Phase 5+ |
| PlanStep 中断 / 重试 | 0 | Phase 5+ |
| Plan 编辑 / 步骤重排 | 0 | Phase 5+ |
| PlanStep 详细元信息 (duration / subtask / dependencies) | 0 | Phase 5+ |
| i18n | 中文化 hardcoded | Phase 5+ |

## 10. 非范围 (Phase 5-D 严格)

- ❌ Agent planner / Tool execution / RAG / Retriever
- ❌ Backend schema / Chat API / SSE schema 改动
- ❌ 工具执行沙箱 / 用户授权
- ❌ multi-turn planning (Phase 5+)
- ❌ 改 Phase 5-A / 5-B / 5-C frozen 设计

## Status (2026-08-22 Phase 5-D)

- ✅ PlanStep 类型 (chat-types.ts shared 镜像 + utils/agent-plan.ts 完整定义)
- ✅ plan_step event 消费 + dedup + sort
- ✅ PlanTimeline 组件 (4 状态 variant + pulse 动画)
- ✅ AgentState 联动 (running/pending -> 'planning')
- ✅ ChatView 集成 (流中实时 + 0 节点差异普通消息)
- ✅ 22 单测 + 5 spec 场景
- ✅ Doc 10 节
- ❌ Phase 5+ Agent planner / Tool execution / RAG 未触碰

---

📌 **维护规则 (Phase 5-D 起)**:
- 改 PlanStep 字段 → 同步 chat-types.ts (shared 镜像) + utils/agent-plan.ts (renderer 完整)
- 改 4 状态 → 同步 PlanTimeline UI 颜色 + 图标 + spec §4 测试
- 改 AgentState 联动规则 → 同步 planStepsToAgentState 函数 + spec §5 测试
- PlanStep 不参与持久化 → 仅流中可见 (完成消息无 plan_steps 字段, 历史 plan 留 Phase 5+)
- 改 StepType union → 同步 utils parsePlanStepEvent 映射 + chat store 处理
