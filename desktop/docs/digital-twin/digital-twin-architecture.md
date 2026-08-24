# 数字孪生架构

## 概述

数字孪生层 — 为科研实验建立可校准、可预测的数学代理模型,基于已有实验数据训练参数,通过确定性预测引擎推断新实验结果。

## 数据模型

### DigitalTwinModel

```
DigitalTwinModel
  id          唯一标识
  name        孪生名称
  domain      领域
  inputs      输入变量名数组
  outputs     输出变量名数组
  parameters  参数数组 (TwinParameter)
  accuracy    准确度 (0..1)
  status      状态: draft | training | validated | deployed | deprecated
  createdAt   创建时间
  updatedAt   更新时间
```

### TwinPrediction

```
TwinPrediction
  modelId     关联模型 ID
  input       输入特征字典
  output      输出预测字典
  confidence  置信度 (0..1)
  timestamp   时间戳
```

### TwinParameter

```
TwinParameter
  name        参数名
  value       当前值
  range       有效范围字符串
  unit        单位
```

## 核心组件

### FeatureEngineer

特征工程层,支持 3 种数据形态:

- `extractFeatures(rows, column, kind)` — 提取单列特征
- `normalize(feature)` — 归一化到 [0, 1]
- `selectFeatures(features, criteria)` — 基于方差与必要列筛选
- `validateInput(input, schema)` — 输入 schema 校验

支持的 kind: `numeric` / `time-series` / `parameter-optimization`

### DigitalTwinEngine

本地确定性预测引擎,无 ML 依赖,纯函数:

- `linearPredict(spec, input)` — y = intercept + Σ(coeff[i] · x[i])
- `polynomialPredict(spec, x)` — y = Σ(coeff[i] · x^i)
- `kineticPredict(spec, t)` — C(t) = C0 · exp(-k · order · t)
- `predict(spec, input)` — 统一接口,根据 spec.kind 路由
- `predictAndRecord(spec, modelId, input)` — 产生 TwinPrediction

### ModelCalibrator

模型校准工具:

- `comparePrediction(pred, obs, tol)` — 单点对比,返回绝对/相对误差
- `calculateError(predictions)` — 聚合 MAE / RMSE / R²
- `updateParameters(params, lr, grad)` — 梯度下降更新参数
- `runCalibration(spec, dataset, opts)` — 全数据集校准

### ExperimentTwinAdapter

连接 ExperimentResult 与 DigitalTwinModel:

- `buildTwinModel(spec, accuracy)` — 构造孪生模型
- `calibrateFromExperiment({experiment, result, twinModel})` — 用实验结果校准模型, 更新 accuracy
- `compareExperimentResult(result, predictions, tol)` — 对比实验与预测

### DigitalTwinTemplates

3 个预定义模板 (Object.freeze):

- `o3-mnb-degradation` — O3-MNB 降解数字孪生
- `cfd-flow-optimization` — CFD 流场优化数字孪生
- `material-synthesis` — 材料合成数字孪生

通过 `getTwinTemplate(kind)` 获取,`listTwinTemplates()` 列出全部。

## 工作流示例

```ts
import { buildTwinModel, calibrateFromExperiment } from './services/digital-twin/experiment-twin-adapter'
import { getTwinTemplate } from './services/digital-twin/digital-twin-templates'

const tmpl = getTwinTemplate('o3-mnb-degradation')
const twin = buildTwinModel({
  name: 'o3-twin-1',
  domain: tmpl.domain,
  inputs: tmpl.inputs,
  outputs: tmpl.outputs,
  parameters: tmpl.parameterRanges.map((p) => ({
    name: p.name, value: 0.5, range: p.range, unit: p.unit
  }))
})

const report = calibrateFromExperiment({ experiment, result, twinModel: twin })
console.log(report.calibration.rSquared, report.updatedAccuracy)
```

## 安全边界

- TwinParameter.value 必须是 finite number
- TwinPrediction.output / input 数值必须 finite
- accuracy 与 confidence 严格 0..1 范围
- 所有 getter 返回防御性拷贝
- 模板 Object.freeze,只读访问通过 getTwinTemplate 返回拷贝
- 无 LLM 直连, 无后端调用, 无密钥存储