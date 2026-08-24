# Phase 8-M0-B2：科研助手与 AI 研究团队设计

**日期：** 2026-08-25
**范围：** 仅 `desktop/**`
**前置版本：** Phase 8-M0-B1

## 目标

将 `Assistant.vue` 升级为以科研对话为核心的「对话中枢」，并将 `AgentCenter.vue` 升级为可观察的「AI 研究团队中心」。界面只显示现有 Agent Store 能够证明的数据；无角色级实时数据时，明确显示「待接入数据」，不伪造队列、任务、耗时或执行记录。

## 已确认的视觉方向

采用 A「对话中枢」：

- Assistant 在宽屏中采用会话列表 / 对话主区 / 证据引用三栏。
- 研究者先阅读结论，再按需展开证据、推理摘要、引用与下一步行动。
- Agent Center 保持独立团队指挥界面，但与 Assistant 使用相同的事件、消息、证据和引用来源。

## 数据边界

页面只能使用既有 `useAgentStore()` 暴露的 `sessions`、`activeSession`、`messages`、`events`、`citations`、`evidence`、`isLoading` 和 `isSending`。Assistant 的研究上下文栏以真实当前会话名称和会话状态表达上下文，不导入项目 Store。

| 展示区域 | 允许的真实来源 | 无数据行为 |
| --- | --- | --- |
| 会话与研究模式 | `sessions`、`activeSession` | 显示会话空态 |
| AI 回复正文 | `messages` 中 assistant 消息 | 只显示真实正文；缺失分区显示空态 |
| 研究轨迹与协作 | `events` | `ResearchTimeline` 空态 |
| 证据和引用 | `evidence`、`citations` | `EvidencePanel` 空态 |
| 工具执行 | `messages[].toolCalls`、可关联 `events` | `ToolExecutionPanel` 空态 |
| 五个固定角色 | 固定角色定义 + 事件标签或消息内容中可精确匹配的角色名称 | 状态、当前任务、队列均显示「待接入数据」 |

角色是页面信息架构，不是执行记录。只有事件可真实匹配到角色时才展示活动状态、动作或时间；没有可用时间戳差时显示「暂无耗时数据」。

## Assistant 设计

### 布局

- 顶部科研上下文栏：当前研究会话、研究模式、AI 状态。
- 左栏：研究会话。
- 主栏：真实消息、`ResearchTimeline` 工具/研究事件轨迹、从可精确识别角色名称的真实事件或消息派生的 `AgentStatusPanel`，以及发送区。
- 右栏：`EvidencePanel`，显示真实证据与引用。

### 回应结构

每个 assistant 消息呈现以下五个可访问分区。当前 Store 没有结构化回答分段，因此结论只呈现该消息的原始真实正文；其余分区明确标为「当前会话」来源，绝不将会话级数据伪装为这条消息的专属输出：

1. **结论**：默认展开；至少显示真实消息正文。
2. **证据**：可折叠；关联真实 evidence。
3. **推理摘要**：可折叠；只显示真实事件摘要，缺失时显示空态。
4. **引用**：可折叠；关联真实 citations。
5. **下一步行动**：可折叠；只显示真实可用的事件或工具结果，缺失时显示空态。

使用原生 `details/summary` 或具备等价键盘和 ARIA 语义的按钮面板。默认状态不预填任何研究结论、引用或活动。

## Agent Center 设计

固定角色为：文献智能体、实验智能体、分析智能体、写作智能体、审稿智能体。

页面包含：

- `ResearchMetricPanel` 团队概览（只统计真实会话、消息、事件和引用数量）和五张角色卡；
- `ResearchTimeline` 协作时间线；
- `EvidencePanel` 证据与引用；
- `ToolExecutionPanel` 工具执行历史；
- 既有研究任务输入、加载、错误与重试入口。

既有 `AgentEvent` 没有角色标识字段，因此角色卡只在真实事件标签或真实消息内容包含该角色名称时建立精确匹配；否则以「待接入数据」显示状态、当前任务和队列。不以 `idle`、`0`、事件类型猜测或虚构文字替代未知值。

## 新共享组件

### `AgentWorkspaceCard`

仅接受 props，禁止导入 Pinia 或 Service。

```ts
{
  name: string
  role: string
  status?: 'pending' | 'running' | 'completed' | 'error'
  currentTask?: string
  queue?: string | number
  dataAvailable?: boolean
}
```

当 `dataAvailable` 为 `false`，以中文「待接入数据」替代未知 status、currentTask 和 queue。

### `ToolExecutionPanel`

仅接受 props，禁止导入 Pinia 或 Service。

```ts
{
  executions?: {
    id: string | number
    agent?: string
    tool: string
    stage?: string
    duration?: string
    status: 'running' | 'completed' | 'error'
    output?: string
  }[]
  ariaLabel?: string
}
```

该组件显示 Agent、工具、阶段、耗时与状态。缺失耗时不推算；缺失项目显示中文「暂无耗时数据」。

## 交互、无障碍与响应式

- 所有交互元素均可键盘访问，并使用清晰的中文 `aria-label`。
- `details/summary` 与重试按钮需保留焦点可见样式。
- `prefers-reduced-motion: reduce` 下禁用运行状态脉冲、折叠和宽度变换动画。
- 1440×900：Assistant 保持可收缩的三栏；次要文本可隐藏，内容区不横向溢出。
- 1920×1080：Assistant 使用完整三栏，Agent Center 维持五角色横向团队卡和可观察区。
- 所有主网格及长文本容器使用 `min-width: 0`、`minmax(0, …)` 和安全换行。

## 状态与恢复

- 加载：复用 `ResearchState`，不清空可保留的真实数据。
- 空态：使用共享组件的中文空态，区分会话、消息、证据、活动和工具无数据。
- 错误：展示可理解的中文错误，重试复用现有 Store action，不新增 service 或 backend 调用。

## 测试与验证

新增至少 150 个 B2 UI 契约，覆盖：

- Assistant 中文标签、五个回应分区、默认结论展开、折叠语义、真实证据与引用、`ResearchTimeline` 与 `AgentStatusPanel` 的精确角色名称映射；
- Agent Center 五个固定角色、真实状态映射、`ResearchMetricPanel` 的真实计数、时间线与工具历史；
- 两个新共享组件的 props 边界，以及没有 Store/Service import；
- 加载、空、错误、重试、ARIA、键盘焦点、reduced motion；
- 1440×900 与 1920×1080 的无横向溢出契约；
- 反伪造数据约束：没有真实来源时，页面和组件显示「待接入数据」或对应空态。

最终验证命令：

```text
npm run test:unit
npx tsc --noEmit -p tsconfig.node.json
npx vue-tsc --noEmit -p tsconfig.web.json
npm run build
```

最终实现提交信息：

```text
Phase 8-M0-B2 Scientific Research OS Assistant Agent Center Upgrade
```
