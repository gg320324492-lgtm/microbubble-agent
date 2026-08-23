# AI Research Assistant Page Design

## Layout (Three-Column)

```
┌────────┬────────────────────────────┬────────────┐
│ 任务    │  AI推理工作台               │ 证据面板    │
│ 历史    │                            │            │
│        │  ┌──────────────────────┐  │ 📄 引用    │
│ ● 会话1 │  │ 用户: 分析降解动力学   │  │ [1] Zhang  │
│ ● 会话2 │  │                      │  │ [2] Li     │
│ ● 会话3 │  │ AI: 根据实验数据...    │  │            │
│        │  │                      │  │ 🔬 证据    │
│        │  │ [工具调用: 拟合模型]    │  │ kLa=0.45  │
│        │  │                      │  │ R²=0.98   │
│        │  │ [模型结果: first-order]│  │            │
│        │  └──────────────────────┘  │ 📊 置信度   │
│        │                            │ ████████░░ │
│        │  ┌──────────────────────┐  │ 85%        │
│        │  │ 输入框               │  │            │
│        │  └──────────────────────┘  │            │
└────────┴────────────────────────────┴────────────┘
```

## Components

- `TaskHistory.vue` — session list with status indicators
- `ReasoningWorkspace.vue` — message stream with tool calls
- `CitationPanel.vue` — inline citations with source links
- `EvidencePanel.vue` — extracted evidence with confidence
- `ToolResultCard.vue` — tool execution results (model fits, statistics)
- `ConfidenceBar.vue` — visual confidence indicator
- `ChatInput.vue` — input with context attachment

## Mock Data

```typescript
messages: [
  { role: 'user', content: '分析O3降解动力学' },
  { role: 'assistant', content: '根据实验数据分析...', toolCalls: [{ name: 'fitModels', result: { model: 'first-order', rSquared: 0.98 } }] }
]
citations: [
  { id: 1, authors: 'Zhang et al.', title: 'Microbubble O3 degradation', year: 2024 }
]
evidence: [
  { type: 'measurement', value: 'kLa = 0.45 min⁻¹', confidence: 0.85 }
]
```
