# Agent Center Page Design

## Layout

```
┌─────────────────────────────────────────────────┐
│  Header: 智能体中心                              │
├─────────────────────────────────────────────────┤
│  ┌─────────────────────────────────────────────┐│
│  │            多智能体架构图                     ││
│  │                                             ││
│  │         ┌─────────────────┐                  ││
│  │         │ 研究主管 Agent   │                  ││
│  │         └────────┬────────┘                  ││
│  │     ┌───────┬────┼────┬───────┐             ││
│  │     v       v    v    v       v             ││
│  │  ┌─────┐┌─────┐┌────┐┌─────┐┌─────┐       ││
│  │  │文献  ││实验  ││数据││写作  ││审稿  │       ││
│  │  │Agent ││Agent ││Agent││Agent ││Agent │       ││
│  │  └─────┘└─────┘└────┘└─────┘└─────┘       ││
│  │                                             ││
│  └─────────────────────────────────────────────┘│
├─────────────────────────────────────────────────┤
│  ┌─────────────────────┐ ┌─────────────────────┐│
│  │ Agent状态             │ │ 任务分配             ││
│  │                     │ │                     ││
│  │ 🟢 文献Agent 运行中   │ │ 当前任务:            ││
│  │    正在分析论文...    │ │ • 文献检索 (文献Agent)││
│  │ 🟡 实验Agent 待命    │ │ • 数据拟合 (数据Agent)││
│  │ 🟢 数据Agent 运行中   │ │ • 结果写作 (写作Agent)││
│  │ ⚪ 写作Agent 空闲    │ │                     ││
│  │ ⚪ 审稿Agent 空闲    │ │ 队列: 3 任务         ││
│  └─────────────────────┘ └─────────────────────┘│
└─────────────────────────────────────────────────┘
```

## Components

- `AgentArchitecture.vue` — multi-agent hierarchy diagram
- `AgentStatusCard.vue` — individual agent status
- `TaskAssignment.vue` — task queue and assignment
- `AgentLog.vue` — agent activity log

## Mock Data

```typescript
agents: [
  { name: '文献Agent', status: 'running', task: '分析论文 Zhang 2024' },
  { name: '实验Agent', status: 'idle', task: null },
  { name: '数据Agent', status: 'running', task: '拟合动力学模型' },
  { name: '写作Agent', status: 'idle', task: null },
  { name: '审稿Agent', status: 'idle', task: null }
]
tasks: [
  { name: '文献检索', agent: '文献Agent', status: 'running' },
  { name: '数据拟合', agent: '数据Agent', status: 'running' },
  { name: '结果写作', agent: '写作Agent', status: 'queued' }
]
```
