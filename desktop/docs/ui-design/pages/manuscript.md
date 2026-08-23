# Manuscript Studio Page Design

## Layout

```
┌─────────────────────────────────────────────────┐
│  Header: 论文助手                    [生成] [导出]  │
├─────────────────────────────────────────────────┤
│  ┌──────────┐ ┌──────────────────────────────┐  │
│  │ 大纲      │ │ 内容编辑区                    │  │
│  │          │ │                              │  │
│  │ ● 摘要    │ │ 1. Introduction               │  │
│  │ ● 引言    │ │ 科学研究需要系统性调查...       │  │
│  │ ● 方法    │ │                              │  │
│  │ ● 结果    │ │ 2. Materials and Methods       │  │
│  │ ● 讨论    │ │ 实验材料和 procedures...       │  │
│  │ ● 结论    │ │                              │  │
│  │          │ │ 3. Results and Discussion      │  │
│  │ 图表      │ │ 实验结果如下...                │  │
│  │ • 图1     │ │                              │  │
│  │ • 图2     │ │                              │  │
│  │          │ │                              │  │
│  │ 参考文献  │ │ ┌──────────────────────────┐  │  │
│  │ [1] Zhang│ │ │ SCI语言审查              │  │  │
│  │ [2] Li   │ │ │ ⚠ 过度表述: "proves"     │  │  │
│  │          │ │ │ ✓ 无重复句子             │  │  │
│  │          │ │ │ ⚠ 缺少数据支持           │  │  │
│  │          │ │ └──────────────────────────┘  │  │
│  └──────────┘ └──────────────────────────────┘  │
└─────────────────────────────────────────────────┘
```

## Components

- `OutlinePanel.vue` — IMRaD section list
- `SectionEditor.vue` — section content display
- `FigureCaptionPanel.vue` — figure captions
- `ReferenceList.vue` — reference management
- `LanguageReviewPanel.vue` — writing issues with severity
- `HighlightList.vue` — key highlights

## Mock Data

```typescript
outline: {
  sections: [
    { type: 'introduction', title: '引言', keyPoints: ['研究背景', '知识空白', '研究目标'] },
    { type: 'methods', title: '材料与方法', keyPoints: ['实验材料', '实验步骤'] },
    { type: 'results', title: '结果与讨论', keyPoints: ['统计数据', '模型拟合'] },
    { type: 'discussion', title: '讨论', keyPoints: ['机制解释', '文献对比'] },
    { type: 'conclusion', title: '结论', keyPoints: ['主要贡献', '未来方向'] }
  ]
}
issues: [
  { type: 'overstatement', severity: 'medium', description: '过度表述: "proves"' },
  { type: 'repetition', severity: 'low', description: '重复句子检测' }
]
```
