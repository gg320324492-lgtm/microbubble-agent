# Dashboard Page Design

## Layout

```
┌─────────────────────────────────────────────────┐
│  Header: 科研项目总览                              │
├─────────────────────────────────────────────────┤
│  ┌──────────┐ ┌──────────┐ ┌──────────┐        │
│  │ 项目进度  │ │ AI洞察   │ │ 实验状态  │        │
│  │ ██████░░ │ │ 💡发现   │ │ ● 运行中  │        │
│  │ 75%      │ │ 动力学..  │ │ ● 已完成  │        │
│  └──────────┘ └──────────┘ └──────────┘        │
├─────────────────────────────────────────────────┤
│  ┌─────────────────────┐ ┌─────────────────────┐│
│  │ 最近论文             │ │ 警告面板             ││
│  │ • Zhang 2024 ★★★★☆  │ │ ⚠ 数据质量警告      ││
│  │ • Li 2023 ★★★☆☆    │ │ ⚠ 模型拟合不足      ││
│  └─────────────────────┘ └─────────────────────┘│
└─────────────────────────────────────────────────┘
```

## Components

- `StatCard.vue` — project progress, AI insights count, experiment count
- `InsightCard.vue` — AI-generated insight with suggestion
- `PaperList.vue` — recent papers with star rating
- `WarningPanel.vue` — data quality / model warnings
- `ExperimentStatus.vue` — running/completed experiment indicators

## Mock Data

```typescript
projects: [
  { name: 'O3-MNBs TC降解', progress: 0.75, status: 'active' },
  { name: '纳米气泡表征', progress: 0.3, status: 'planning' }
]
insights: [
  { finding: '动力学模型选择可能不足', suggestion: '补充自由基验证实验', severity: 'warning' }
]
warnings: [
  { type: 'data_quality', message: '浓度数据缺失 15%', severity: 'medium' }
]
```
