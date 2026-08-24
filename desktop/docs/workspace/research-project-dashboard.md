# 科研项目仪表盘

## 概述

科研项目仪表盘 — 在 `ResearchWorkspace` 主页上展示项目总览、研究进度、模块状态、活动时间线 4 大维度,提供一站式科研项目管理视图。

## 仪表盘布局

```
┌─────────────────────────────────────────────────────────────┐
│  标题: 微纳米气泡研究项目                                    │
│  副标题: O3-MNB 降解 + 数字孪生 + 论文生成                 │
└─────────────────────────────────────────────────────────────┘

┌──────────────────────┬──────────────────────────────────────┐
│  项目总览 (左侧)      │  研究进度 (右侧)                    │
│  - 标题              │  总体: 65%                          │
│  - 领域              │  任务: 14/24 (58%)                  │
│  - 状态              │  实验: 4/6 (67%)                    │
│  - 成员              │  论文: 1/3 (33%)                    │
│  - 任务              │  知识: 65/80 (81%)                  │
│  健康度: 正常 65%    │  进度条                              │
│  活跃: 6/8           │                                       │
└──────────────────────┴──────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│  模块状态网格 (8 个模块)                                     │
│  ┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐               │
│  │ AI     │ │ DATA   │ │ AI     │ │ LAB    │               │
│  │ 智能体 │ │ 知识库 │ │ 多智能 │ │ 实验   │               │
│  │ 就绪   │ │ 就绪   │ │ 运行中 │ │ 运行中 │               │
│  └────────┘ └────────┘ └────────┘ └────────┘               │
│  ┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐               │
│  │ MODEL  │ │ IOT    │ │ OPS    │ │ OUTPUT │               │
│  │ 孪生   │ │ 设备   │ │ 控制   │ │ 论文   │               │
│  │ 运行中 │ │ 就绪   │ │ 就绪   │ │ 暂停   │               │
│  └────────┘ └────────┘ └────────┘ └────────┘               │
└─────────────────────────────────────────────────────────────┘

┌──────────────────────┬──────────────────────────────────────┐
│  研究里程碑 (左侧)    │  活动时间线 (右侧)                  │
│  ● 知识库初始化 ✓    │  ▸ 智能体 - 规划新实验              │
│  ● 实验方案设计 ▶    │  ▸ 实验   - 实验执行完成            │
│  ● 数字孪生校准 ▶    │  ▸ 孪生   - 数字孪生校准              │
│  ○ 设备接入          │  ▸ 论文   - 论文草稿更新              │
│  ○ 论文撰写          │  ▸ 设备   - 设备数据接入              │
└──────────────────────┴──────────────────────────────────────┘
```

## 关键组件

### ProjectSummaryPanel

显示项目基础信息 + 健康度指标:

- 标题、领域、状态
- 成员数、任务数
- 健康度 (基于总体完成百分比)
- 活跃模块数

### ResearchProgressCard

研究进度卡片,带 4 个分项指标:

- 任务进度 (completedTasks / totalTasks)
- 实验进度 (completedExperiments / totalExperiments)
- 论文进度 (publishedManuscripts / totalManuscripts)
- 知识进度 (indexedKnowledge / totalKnowledge)
- 总体进度条 (橙色渐变)

### ModuleStatusCard

8 个模块的状态卡片:

- 分类标签 (AI/Data/Lab/Model/IoT/Ops/Output)
- 状态徽章 (就绪/运行中/暂停/已完成/失败/已禁用)
- 6 种状态对应 6 种颜色

### ResearchMilestonePanel

里程碑面板,显示项目阶段进度:

- 已完成 (绿色)
- 进行中 (橙色)
- 待开始 (灰色)
- 阻塞 (红色)

### ActivityTimeline

活动时间线,按事件类型分色:

- 智能体 → 橙色
- 实验 → 蓝色
- 论文 → 紫色
- 设备 → 绿色
- 孪生 → 金黄
- 知识 → 粉色
- 系统 → 灰色

## 数据计算逻辑

### 总体百分比

```ts
totalDone = tasks.completed + experiments.completed + manuscripts.published
total = tasks.total + experiments.total + manuscripts.total
percent = total > 0 ? Math.round(totalDone / total * 100) : 0
```

### 活跃模块数

```ts
activeModules = modules.filter(m => m.enabled && (m.status === 'ready' || m.status === 'running')).length
```

### 健康度

健康度 = 总体百分比 (百分制)

## 集成示例

UI 层从 Pinia store 读取:

```ts
const store = useResearchWorkspaceStore()
const ws = store.workspace
const modules = store.modules
const activities = store.activities
const progress = store.progress
const summary = store.summary
```

## 安全边界

- 所有数值字段严格有限性
- healthScore 与 percent 必须 >= 0
- 所有 getter 返回防御性拷贝
- 无 LLM 直连, 无后端调用, 无密钥存储