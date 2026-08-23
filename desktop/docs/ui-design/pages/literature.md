# Literature Intelligence Page Design

## Layout

```
┌─────────────────────────────────────────────────┐
│  Header: 文献智能库                    [搜索] [筛选]│
├─────────────────────────────────────────────────┤
│  ┌─────────────────────┐ ┌─────────────────────┐│
│  │ PDF文献库            │ │ 论文详情             ││
│  │                     │ │                     ││
│  │ 📄 Zhang 2024 ★★★★☆ │ │ 可靠性: ★★★★☆ 0.82 ││
│  │ 📄 Li 2023 ★★★☆☆   │ │ 证据: ★★★★☆ 0.78  ││
│  │ 📄 Wang 2023 ★★★★★ │ │ 方法: ★★★☆☆ 0.65  ││
│  │ 📄 Chen 2022 ★★☆☆☆ │ │                     ││
│  │                     │ │ 风险提示:            ││
│  │                     │ │ • 统计方法不充分     ││
│  │                     │ │ • 机制证据薄弱       ││
│  └─────────────────────┘ │                     ││
│                          │ 证据提取:            ││
│                          │ • kLa测量方法        ││
│                          │ • 去除效率数据       ││
│                          └─────────────────────┘│
└─────────────────────────────────────────────────┘
```

## Components

- `PaperLibrary.vue` — PDF list with search/filter
- `PaperCard.vue` — paper summary with star rating
- `PaperDetail.vue` — full paper analysis
- `CredibilityScore.vue` — reliability/evidence/methodology scores
- `RiskAlert.vue` — quality warnings
- `EvidenceExtractor.vue` — extracted evidence items
- `CitationGraph.vue` — citation relationship visualization

## Mock Data

```typescript
papers: [
  { id: 1, authors: 'Zhang et al.', title: 'Microbubble O3 degradation of tetracycline', journal: 'Chem. Eng. J.', year: 2024, credibility: 0.82 },
  { id: 2, authors: 'Li et al.', title: 'Nanobubble characterization methods', journal: 'Ultrasonics', year: 2023, credibility: 0.65 }
]
risks: ['统计方法不充分', '机制证据薄弱', '样本量不足']
evidence: [{ type: 'measurement', value: 'kLa = 0.45 min⁻¹', source: 'Zhang 2024' }]
```
