# Agent Collaboration Flow

## 概述

多智能体协作流程 — 智能体之间通过消息传递和质疑辩论完成复杂科研任务。

## 协调流程

```
用户输入
   ↓
CoordinatorAgent 接收任务
   ↓
任务分析（关键词匹配）
   ↓
智能体选择
   ↓
消息分发（request 类型）
   ↓
智能体执行（纯函数）
   ↓
结果收集（response 类型）
   ↓
结果聚合
   ↓
CollaborationResult 输出
```

## 任务分析

CoordinatorAgent 通过关键词匹配选择智能体：

| 关键词 | 选中智能体 |
|---------|----------|
| 文献/综述/review | LiteratureAgent |
| 实验/设计/design | ExperimentAgent |
| 数据/分析/模型 | DataAnalysisAgent |
| 机理 | MechanismAgent |
| 论文/manuscript | WritingAgent, ReviewerAgent |

## 智能体选择示例

输入："分析 TC 降解机理并设计实验"
- 关键词匹配：机理、实验、设计
- 选中智能体：MechanismAgent, ExperimentAgent

## 智能体执行

每个智能体接收 AgentTask，返回包含结果字符串和置信度的对象：

```ts
{
  result: string
  confidence: number  // 0..1
}
```

## 质疑辩论机制

```
MechanismAgent 提出主张
   ↓
ReviewerAgent 质疑
   ↓
Coordinator 裁决
   ↓
若 accept → 结束
若 revise → 修订主张 → 重新质疑（最多3轮）
```

## 辩论示例

```
MechanismAgent: "·OH 自由基主导 TC 降解"
ReviewerAgent: "证据基础是否充分？需要补充验证实验"
Coordinator: "需要补充实验数据"
```

## 预定义工作流模板

### 1. 文献综述 (literature-review)

```
LiteratureAgent → 检索相关文献
LiteratureAgent → 提取关键证据
ReviewerAgent → 评估证据质量
```

### 2. 实验设计 (experiment-design)

```
MechanismAgent → 分析机理
ExperimentAgent → 设计变量与分组
ReviewerAgent → 审查设计合理性
```

### 3. 论文写作 (paper-writing)

```
WritingAgent → 生成初稿
ReviewerAgent → SCI审稿
WritingAgent → 根据审稿意见修改
```

### 4. 完整研究流程 (complete-research)

```
CoordinatorAgent → 调度研究流程
LiteratureAgent → 文献调研与证据汇总
MechanismAgent → 机理分析
ExperimentAgent → 实验设计
DataAnalysisAgent → 数据分析与建模
WritingAgent → 论文初稿撰写
ReviewerAgent → SCI审稿
```

## 消息类型

- request：任务请求
- response：任务响应
- evidence：证据提交
- critique：质疑与批评
- suggestion：建议

## 集成接口

```ts
import { coordinate } from './services/agents/agent-coordinator'
import { conductDebate } from './services/agents/agent-debate'
import { getWorkflowTemplate } from './services/agents/scientific-workflows'

// 协调任务
const result = coordinate(task)
console.log(result.agents, result.finalResult)

// 辩论
const debate = conductDebate('·OH 主导机理', 'ReviewerAgent', 3)
console.log(debate.finalVerdict)

// 工作流
const workflow = getWorkflowTemplate('literature-review')
console.log(workflow?.steps)
```

## 与现有 Phase 8 模块的集成

- Phase 8-C Retriever：文献智能体可使用
- Phase 8-J0 Knowledge Graph：机理智能体可使用
- Phase 8-H2 Data Analysis：数据分析智能体可使用
- Phase 8-H3 Manuscript：写作智能体可使用
