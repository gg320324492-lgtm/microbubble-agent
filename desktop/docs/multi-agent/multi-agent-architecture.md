# Multi-Agent Architecture

## 概述

科研多智能体协作系统 — 协调 6 类专业化智能体完成复杂科研任务。

## 智能体架构

```
                    CoordinatorAgent
                    (调度 / 编排)
                          |
        +-----------------+------------------+
        |                 |                  |
  LiteratureAgent  ExperimentAgent  DataAnalysisAgent
  (文献调研)        (实验设计)        (数据分析)
        |                 |                  |
  MechanismAgent   WritingAgent    ReviewerAgent
  (机理推理)        (论文写作)        (质量审稿)
```

## 7 种智能体角色

- **LiteratureAgent** 文献智能体：检索论文、汇总证据
- **ExperimentAgent** 实验智能体：设计变量、规划分组
- **DataAnalysisAgent** 数据智能体：统计、建模、可视化
- **MechanismAgent** 机理智能体：推理机理路径、证据链
- **WritingAgent** 写作智能体：生成论文初稿
- **ReviewerAgent** 审稿智能体：评估质量、发现弱点
- **CoordinatorAgent** 协调智能体：调度、编排、聚合

## 核心组件

### Agent Schema（agent-schema.ts）
- ScientificAgentProfile：智能体档案
- AgentTask：智能体任务
- AgentMessage：智能体消息
- 角色枚举：7 种角色
- 任务状态：5 种状态
- 消息类型：5 种类型
- 安全防护：值级秘密检查

### Agent Registry（agent-registry.ts）
- 注册/移除/查询智能体
- 按能力、角色、知识域搜索
- 防御性拷贝
- 确定性排序
- 快照支持

### Specialized Agents（agents/*.ts）
- literature-agent：文献检索与摘要
- experiment-agent：实验变量与分组设计
- analysis-agent：统计与模型拟合
- mechanism-agent：机理路径推理
- writing-agent：论文初稿生成
- reviewer-agent：质量审查与弱点检测

### Agent Coordinator（agent-coordinator.ts）
- 任务分析 → 智能体选择 → 消息分发 → 结果聚合
- 返回 CollaborationResult

### Agent Debate（agent-debate.ts）
- 质疑/反质疑/裁决机制
- 多轮辩论
- 综合裁决

### Workflow Templates（scientific-workflows.ts）
- 4 个预定义工作流
- 文献综述 / 实验设计 / 论文写作 / 完整研究

## 数据流

```
用户问题
  ↓
CoordinatorAgent
  ↓
任务分析（关键词匹配）
  ↓
智能体选择
  ↓
消息分发（request）
  ↓
智能体执行
  ↓
结果收集（response）
  ↓
结果聚合
  ↓
CollaborationResult
```

## 安全边界

- 所有智能体实现纯函数（无副作用）
- 不导入 model-provider / auth / backend / chat runtime
- 值级秘密防护
- 防御性拷贝防止外部修改
