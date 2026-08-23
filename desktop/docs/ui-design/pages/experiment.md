# Research Design Page Design

## Layout

```
┌─────────────────────────────────────────────────┐
│  Header: 实验设计                                │
├─────────────────────────────────────────────────┤
│  ┌──────────┐ ┌──────────┐ ┌──────────┐        │
│  │ 研究问题  │ │ 假设      │ │ 变量设计  │        │
│  │          │ │          │ │          │        │
│  │ O3微纳米  │ │ H1: 更小  │ │ 自变量:   │        │
│  │ 气泡降解  │ │ 气泡提高  │ │ • 气泡直径 │        │
│  │ 效率优化  │ │ 传质效率  │ │ • 臭氧浓度 │        │
│  │          │ │          │ │ 因变量:   │        │
│  │          │ │ H2: 自由  │ │ • 去除效率 │        │
│  │          │ │ 基途径   │ │          │        │
│  └──────────┘ └──────────┘ └──────────┘        │
├─────────────────────────────────────────────────┤
│  ┌─────────────────────┐ ┌─────────────────────┐│
│  │ 实验分组             │ │ 推荐模型             ││
│  │                     │ │                     ││
│  │ 对照组: 常规曝气      │ │ 动力学: pseudo-1st  ││
│  │ 实验组1: 200nm气泡   │ │ 传质: 两膜理论      ││
│  │ 实验组2: 50nm气泡    │ │ 优化: RSM           ││
│  │ 实验组3: 100nm气泡   │ │ 统计: ANOVA         ││
│  │                     │ │                     ││
│  │ 评估指标:            │ │ 置信度: 85%         ││
│  │ • 粒径分布 (DLS)     │ │                     ││
│  │ • O3浓度 (UV-Vis)    │ │                     ││
│  └─────────────────────┘ └─────────────────────┘│
└─────────────────────────────────────────────────┘
```

## Components

- `ResearchQuestionCard.vue` — problem statement
- `HypothesisPanel.vue` — generated hypotheses with confidence
- `VariableDesigner.vue` — independent/dependent/control variables
- `ExperimentGroupList.vue` — control + treatment groups
- `MetricSelector.vue` — evaluation metrics
- `ModelRecommendation.vue` — recommended analysis models
- `DesignSummary.vue` — complete design overview

## Mock Data

```typescript
design: {
  question: 'O3微纳米气泡降解效率优化',
  hypotheses: [
    { statement: '更小气泡提高传质效率', confidence: 0.80 },
    { statement: '自由基途径加速降解', confidence: 0.65 }
  ],
  variables: [
    { name: '气泡直径', type: 'independent', range: '50-500 nm' },
    { name: '去除效率', type: 'dependent', range: '0-100%' }
  ],
  groups: [
    { name: '对照组', condition: '常规曝气' },
    { name: '实验组1', condition: '200nm微纳米气泡' }
  ],
  model: { name: 'pseudo-first-order', confidence: 0.85 }
}
```
