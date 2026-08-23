# Scientific Research OS — Design System

## Color Palette

```css
/* Primary — scientific blue */
--color-primary: #2563EB;
--color-primary-light: #3B82F6;
--color-primary-dark: #1D4ED8;

/* Accent — research orange */
--color-accent: #F59E0B;
--color-accent-light: #FBBF24;

/* Semantic */
--color-success: #10B981;
--color-warning: #F59E0B;
--color-danger: #EF4444;
--color-info: #3B82F6;

/* Neutral — clean gray */
--color-bg: #F8FAFC;
--color-surface: #FFFFFF;
--color-border: #E2E8F0;
--color-text: #1E293B;
--color-text-secondary: #64748B;
--color-text-muted: #94A3B8;

/* Dark mode */
--color-bg-dark: #0F172A;
--color-surface-dark: #1E293B;
--color-border-dark: #334155;
```

## Typography

```css
/* Headings */
--font-size-h1: 24px;  /* page title */
--font-size-h2: 20px;  /* section title */
--font-size-h3: 16px;  /* card title */
--font-size-h4: 14px;  /* subtitle */

/* Body */
--font-size-body: 14px;
--font-size-small: 12px;
--font-size-caption: 11px;

/* Font family */
--font-sans: 'Inter', -apple-system, sans-serif;
--font-mono: 'JetBrains Mono', monospace;
```

## Component Tokens

### Cards
```css
--card-radius: 8px;
--card-padding: 16px;
--card-shadow: 0 1px 3px rgba(0,0,0,0.08);
--card-border: 1px solid var(--color-border);
```

### Tables
```css
--table-header-bg: var(--color-bg);
--table-row-hover: #F1F5F9;
--table-border: 1px solid var(--color-border);
--table-cell-padding: 8px 12px;
```

### Status Indicators
```css
--status-running: var(--color-success);
--status-warning: var(--color-warning);
--status-error: var(--color-danger);
--status-idle: var(--color-text-muted);
```

## AI Reasoning Panel

```css
--ai-panel-bg: #F0F9FF;
--ai-panel-border: #BAE6FD;
--ai-panel-radius: 8px;
--ai-thinking-color: #0EA5E9;
--ai-result-color: #10B981;
```

## Citation Component

```css
--citation-bg: #FEF3C7;
--citation-border: #F59E0B;
--citation-text: #92400E;
--citation-number: #B45309;
```

## Spacing Scale

```
4px  — xs
8px  — sm
12px — md
16px — lg
24px — xl
32px — 2xl
48px — 3xl
```

## Border Radius

```
4px  — sm (buttons, inputs)
8px  — md (cards, panels)
12px — lg (modals)
16px — xl (large containers)
```

## Shadows

```
0 1px 2px rgba(0,0,0,0.05)  — sm
0 1px 3px rgba(0,0,0,0.08)  — md
0 4px 6px rgba(0,0,0,0.10)  — lg
```

## Animation

```
150ms — fast (hover, focus)
200ms — normal (transitions)
300ms — slow (page transitions)
```

## Chinese UI Labels

| English | Chinese |
|---------|---------|
| Dashboard | 首页/仪表盘 |
| Research Workspace | 项目空间 |
| AI Assistant | AI科研助手 |
| Literature | 文献智能库 |
| Experiment Design | 实验设计 |
| Data Analysis | 数据分析 |
| Manuscript | 论文助手 |
| Knowledge Graph | 知识图谱 |
| Agent Center | 智能体中心 |
| Settings | 系统设置 |
| Running | 运行中 |
| Completed | 已完成 |
| Idle | 空闲 |
| Warning | 警告 |
| Error | 错误 |
| Confidence | 置信度 |
