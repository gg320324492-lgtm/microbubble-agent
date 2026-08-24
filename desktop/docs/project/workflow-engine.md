# Workflow Engine

## 概述

科研工作流引擎 — 协调多步骤科研任务的自动执行。

## 数据流

```
ScientificWorkflow
       ↓
  WorkflowEngine.execute()
       ↓
  1. 检查依赖（dependencies）
  2. 选择可用任务
  3. 派发 AgentCoordinator
  4. 更新任务状态
  5. 发出事件
       ↓
  WorkflowExecutionResult
```

## 工作流步骤类型

- literature（文献调研）
- experiment（实验设计）
- analysis（数据分析）
- modeling（建模）
- writing（论文撰写）
- review（质量审查）

## 工作流状态

- draft（草稿）
- running（运行中）
- paused（已暂停）
- completed（已完成）
- failed（已失败）

## 预定义模板

### 1. 新论文研究（new-paper）

```
LiteratureAgent → 文献调研
  ↓
MechanismAgent → 机理分析
  ↓
ExperimentAgent → 实验设计
  ↓
DataAnalysisAgent → 数据分析
  ↓
WritingAgent → 论文撰写
  ↓
ReviewerAgent → 质量审查
```

### 2. 现有数据集分析（dataset-analysis）

```
DataAnalysisAgent → 数据探索
  ↓
DataAnalysisAgent → 质量检查
  ↓
DataAnalysisAgent → 统计建模
  ↓
MechanismAgent → 物理解释
```

### 3. 实验条件优化（experimental-optimization）

```
DataAnalysisAgent → 现状评估
  ↓
MechanismAgent → 机理分析
  ↓
ExperimentAgent → 实验设计
  ↓
DataAnalysisAgent → 结果分析
```

## 任务依赖管理

任务通过 dependencies 字段定义执行顺序：

```
T1: LiteratureAgent → 输出 literature_review
  ↓ (T1 完成)
T2: ExperimentAgent → 输入: literature_review
  ↓ (T2 完成)
T3: DataAnalysisAgent → 输入: experiment_data
```

## 集成接口

Workflow Engine 与 AgentCoordinator 集成：

```ts
import { WorkflowEngine } from './services/project/workflow-engine'
import { getProjectTemplate } from './services/project/project-templates'

const workflow = getProjectTemplate('new-paper')
const engine = new WorkflowEngine()
const result = engine.execute(workflow, {
  name: 'O3-MNBs TC降解研究',
  domain: '环境科学'
})

console.log(result.executedSteps, result.confidence)
```

## 事件集成

工作流与 ResearchEventBus 集成：

```ts
const bus = new ResearchEventBus()

bus.subscribe('task.completed', (event) => {
  console.log('Task completed:', event.payload)
})

bus.emit('task.completed', { taskId: 't1', output: '...' })
bus.emit('workflow.started', { workflowId: 'new-paper' })
bus.emit('workflow.completed', { workflowId: 'new-paper', confidence: 0.85 })
```

## 安全边界

- 任务输入必须为字符串类型
- 依赖 ID 数组必须为字符串数组
- 步骤结果仅限字符串输出
- 无后端调用、无 API key 存储
