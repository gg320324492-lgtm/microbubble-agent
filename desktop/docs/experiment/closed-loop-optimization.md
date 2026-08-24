# 闭环实验优化

## 概述

科研实验的闭环反馈机制 — 当前实验结果自动驱动下一轮实验的设计,实现"实验 → 分析 → 优化 → 实验"的迭代循环。

## 闭环流程

```
┌─────────────────────────────────────────────────────┐
│                                                     │
│  Experiment (当前实验)                              │
│       ↓                                             │
│  Experiment Result (metrics + confidence)           │
│       ↓                                             │
│  Data Analyst (analyze)                             │
│       ↓ ExperimentOptimizationResult                │
│  Optimization Advisor (suggestions + variables)      │
│       ↓                                             │
│  NextExperimentRecommendation[]                     │
│       ↓                                             │
│  NextExperimentPlan (inheritedPlanId + summary)     │
│       ↓                                             │
│  下一轮 Experiment (execute(plan))                  │
│       ↓                                             │
│  ... (循环)                                         │
│                                                     │
└─────────────────────────────────────────────────────┘
```

## 数据契约

### 输入

- `Experiment` — 当前实验 (含 records + datasets + results)
- `ExperimentResult` — 最近一次结果 (metrics + conclusion + confidence)

### 输出

`NextExperimentPlan`:

```
NextExperimentPlan
  sourceExperimentId     来源实验 ID
  recommendedChanges[]   NextExperimentRecommendation[]
  summary                总结文本
  rationale              推理文本
  confidence             置信度 (0..1)
  inheritedPlanId        下一轮 plan ID
  suggestedVariables     建议变量名数组
```

## 三阶段细节

### Stage 1 — Data Analyst (analyze)

输入 `Experiment` + `ExperimentResult`,产出 `ExperimentOptimizationResult`:

- `importantVariables` — 从 metrics 中提取重要变量
- `suggestions` — 优化建议
- `nextExperiments` — 下一轮变量调整建议
- `issues` + `explanations` — 异常与说明

实现位于 `ExperimentLoopEngine.analyze()`,纯确定性,无 LLM 调用。

### Stage 2 — Optimization Advisor (closeLoop)

基于 Stage 1 的 `ExperimentOptimizationResult`,产出 `NextExperimentPlan`:

- 过滤掉 `confidence < analystConfidenceFloor` 的实验结果
- 截取最多 `maxRecommendations` 条建议
- 汇总 suggestedVariables (排序去重)

### Stage 3 — Plan Inheritance (toNextExperimentPlan)

将 `NextExperimentPlan` 转回 `ExperimentPlan` (Phase 8-H0 类型):

- `planId` ← `inheritedPlanId`
- `hypothesis` ← `summary`
- 每个 `variable.range` 若有 `recommendedChanges` 对应则替换
- `groups` + `measurements` 沿用
- `expectedOutcome` ← `summary`

## 集成接口

```ts
import { ExperimentLoopEngine } from './services/experiment/experiment-loop-engine'

const loop = new ExperimentLoopEngine({
  analystConfidenceFloor: 0.5,
  maxRecommendations: 3
})

// 单次分析
const opt = loop.analyze(experiment, lastResult)

// 闭环
const next = loop.closeLoop(experiment, lastResult)
if (next) {
  const nextPlan = loop.toNextExperimentPlan(prevPlan, next)
  engine.execute(nextPlan, input)
}
```

## 事件集成

与 ResearchEventBus 集成,通过 `experiment-events.ts` 定义的事件类型:

- `experiment.created` — 实验创建
- `experiment.started` — 实验开始 (transition to running)
- `experiment.recorded` — 添加记录
- `experiment.completed` — 实验完成
- `experiment.optimized` — 闭环优化产出 NextExperimentPlan

订阅示例:

```ts
import { ResearchEventBus } from './services/project/research-event-bus'

const bus = new ResearchEventBus()
bus.subscribe('experiment.completed' as any, (event) => {
  console.log('experiment done:', event.payload)
})
```

## 复用 Phase 8-H1 类型

| 复用源 | 用途 |
|--------|------|
| `NextExperimentRecommendation` | NextExperimentPlan.recommendedChanges |
| `OptimizationSuggestion` | Stage 1 产出 |
| `VariableImportance` | Stage 1 产出 |
| `ExperimentOptimizationResult` | Stage 1 中间结果 |

## 安全边界

- `analystConfidenceFloor` 过滤低置信度结果,避免噪声触发下一轮
- `maxRecommendations` 限制每轮建议数
- 所有数值严格用 `Number.isFinite` 校验
- 仅消费 Phase 8-H1 类型,不修改其契约
- 无 LLM 直连,无后端调用,无密钥存储