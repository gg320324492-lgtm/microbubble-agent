# 实验生命周期管理

## 概述

科研实验闭环系统的核心 — 覆盖实验从草稿到完成的完整生命周期,记录每个实验操作,关联数据集,产出可量化的实验结果。

## 数据模型

### Experiment

```
Experiment
  id            唯一标识
  projectId     所属项目
  title         标题
  objective     实验目标
  hypothesis    假设
  status        状态: draft | planned | running | paused | completed | failed
  design        实验设计描述
  records       实验记录数组
  datasets      关联的数据集 ID 数组
  results       实验结果数组
  createdAt     创建时间
  updatedAt     更新时间
```

### ExperimentRecord

```
ExperimentRecord
  id            记录 ID
  experimentId  所属实验
  timestamp     记录时间戳
  operator      操作员
  parameters    参数数组 (ExperimentParameter)
  observations  观察字符串
  notes         备注
```

### ExperimentParameter

```
ExperimentParameter
  name          参数名
  value         值 (string | number | boolean)
  unit          单位
  type          类型: numeric | categorical | boolean | text
```

### ExperimentResult

```
ExperimentResult
  metrics       数值指标字典
  conclusion    结论文本
  confidence    置信度 (0..1)
```

## 核心组件

### ExperimentManager

负责实验生命周期管理:

- `createExperiment(input)` — 创建实验 (status=draft)
- `updateExperiment(id, patch)` — 修改实验元数据
- `startExperiment(id)` — 切换到 running
- `pauseExperiment(id)` — 切换到 paused
- `completeExperiment(id)` — 切换到 completed
- `failExperiment(id)` — 切换到 failed
- `addRecord(experimentId, input)` — 添加实验记录
- `attachDataset(experimentId, datasetId)` — 关联数据集
- `setResult(experimentId, result)` — 设置实验结果
- `getExperimentProgress(experimentId)` — 获取进度 (total/completed/percent/status)

**确定性 + 防御性拷贝**: 内部 Map 存储,所有 getter 返回深拷贝;listExperiments 按 ID 排序保证确定性。

### ExperimentEngine

执行引擎 — 输入 ExperimentPlan (Phase 8-H0),按 5 步执行:

```
1. 创建 Experiment
2. 生成 tasks (基于 measurements)
3. 分配 Agent (ExperimentAgent 角色)
4. 跟踪状态 (pending → running → completed/failed)
5. 收集结果 (metrics + conclusion + confidence)
```

输出 `ExperimentExecutionResult` (experimentId, planId, status, executedSteps, outputs, confidence, errors)。

### ExperimentDataAdapter

连接 ExperimentRecord 与 ScientificDataset (Phase 8-H2):

- `recordToDataset(record, name)` — 单记录 → 数据集
- `validateDataset(ds)` — 验证数据集结构
- `mergeRecords(records, name)` — 多记录合并 → 数据集

不修改 Phase 8-H2 契约,仅消费。

### ExperimentLoopEngine

闭环优化引擎 — 基于实验结果生成下一轮实验计划:

```
Experiment Result
  ↓
Data Analyst (analyze)
  ↓
Optimization Advisor (suggestions + importantVariables)
  ↓
Next Experiment Recommendation
  ↓
NextExperimentPlan
```

输出 `NextExperimentPlan` (sourceExperimentId, recommendedChanges, summary, rationale, confidence, inheritedPlanId, suggestedVariables)。

通过 `toNextExperimentPlan(prev, next)` 可转回 ExperimentPlan 供下一轮 execute()。

### ExperimentTemplates

预定义实验模板 (4 种):

- `o3-mnb-degradation` — 臭氧微纳米气泡降解实验
- `cfd-optimization` — CFD 流场优化实验
- `material-experiment` — 材料合成实验
- `biological-experiment` — 生物实验

通过 `getExperimentTemplate(kind)` 获取,`listExperimentTemplates()` 列出全部。

## 工作流示例

```ts
import { ExperimentManager } from './services/experiment/experiment-manager'
import { ExperimentEngine } from './services/experiment/experiment-engine'
import { ExperimentLoopEngine } from './services/experiment/experiment-loop-engine'
import { getExperimentTemplate } from './services/experiment/experiment-templates'

const manager = new ExperimentManager()
const engine = new ExperimentEngine(manager)
const loop = new ExperimentLoopEngine()

const tmpl = getExperimentTemplate('o3-mnb-degradation')
const result = engine.execute(plan, {
  projectId: 'proj-1',
  title: tmpl.name,
  objective: tmpl.objective,
  operator: 'wang'
})

if (result.status === 'completed') {
  const exp = manager.getExperiment(result.experimentId)!
  const lastResult = exp.results[exp.results.length - 1]
  const next = loop.closeLoop(exp, lastResult)
  console.log(next?.summary)
}
```

## 安全边界

- 状态枚举严格限定 6 种,转换走 transitionStatus()
- ExperimentParameter 值类型受 ParameterType 强制约束 (numeric 必须 number)
- 所有 getter 返回防御性拷贝,外部无法修改内部状态
- 实验记录 / 结果数组在内部深拷贝
- 模板 Object.freeze,只读访问通过 getExperimentTemplate 返回拷贝
- 无后端调用、无 API key 存储、无 LLM 直连