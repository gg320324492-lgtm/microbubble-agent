# Data Analysis Page Design

## Layout

```
┌─────────────────────────────────────────────────┐
│  Header: 数据分析                    [上传数据]    │
├─────────────────────────────────────────────────┤
│  ┌──────────┐ ┌──────────┐ ┌──────────┐        │
│  │ 数据质量  │ │ 统计分析  │ │ 模型拟合  │        │
│  │          │ │          │ │          │        │
│  │ 完整度:  │ │ 均值: 5.0│ │ 最佳模型: │        │
│  │ ████████ │ │ 标准差:  │ │ 1st-order│        │
│  │ 100%     │ │ 2.3     │ │ R²=0.998│        │
│  │          │ │ 相关:    │ │          │        │
│  │ 缺失值: 0│ │ r=-0.85 │ │ 残差:    │        │
│  │ 异常值: 0│ │ (强负)   │ │ 0.12    │        │
│  │ 警告: 0  │ │          │ │          │        │
│  └──────────┘ └──────────┘ └──────────┘        │
├─────────────────────────────────────────────────┤
│  ┌─────────────────────┐ ┌─────────────────────┐│
│  │ 可视化               │ │ 科学解读             ││
│  │                     │ │                     ││
│  │  📈 O3浓度-时间曲线  │ │ 📋 质量解读:         ││
│  │  ──────────●──────  │ │ 数据完整可靠         ││
│  │  ●──────●           │ │                     ││
│  │  ●────●             │ │ 📋 统计解读:         ││
│  │                     │ │ 强负相关表明O3消耗   ││
│  │  📊 模型拟合图       │ │ 与去除效率正相关     ││
│  │  ●●●●●●●●●●●●●●●●  │ │                     ││
│  │  ────────────────── │ │ 📋 模型解读:         ││
│  │  (first-order fit)  │ │ 一级动力学最适描述   ││
│  └─────────────────────┘ └─────────────────────┘│
└─────────────────────────────────────────────────┘
```

## Components

- `DataUpload.vue` — file upload with drag-drop
- `QualityReport.vue` — completeness, missing, outliers, warnings
- `StatisticsPanel.vue` — mean, std, correlation results
- `ModelFitPanel.vue` — model fits ranked by R²
- `VisualizationChart.vue` — chart display (line/bar/scatter)
- `InterpretationPanel.vue` — scientific conclusions

## Mock Data

```typescript
quality: { completeness: 1.0, missingValues: {}, outliers: {}, warnings: [] }
statistics: [
  { metric: 'concentration_mean', value: 4.75, interpretation: '平均O3浓度为4.75 mg/L' },
  { metric: 'correlation', value: -0.987, interpretation: '强负相关' }
]
models: [
  { model: 'first-order', rSquared: 0.998, residualError: 0.12 }
]
conclusions: [
  { observation: '一级动力学最佳描述数据', interpretation: '浓度依赖行为', confidence: 0.90 }
]
```
