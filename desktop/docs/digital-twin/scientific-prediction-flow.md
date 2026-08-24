# 科学预测流程

## 概述

数字孪生的预测流程 — 从输入特征到预测输出,经过特征工程 → 模型路由 → 校准 → 比对的完整链路。

## 流程图

```
┌──────────────────────────────────────────────────────────────┐
│                                                              │
│  实验结果 (metrics + confidence)                              │
│       ↓                                                      │
│  Feature Engineer (extractFeatures / normalize)              │
│       ↓                                                      │
│  TwinParameter → PredictionSpec                              │
│       ↓                                                      │
│  Digital Twin Engine (linear / polynomial / kinetic)         │
│       ↓ PredictionResult                                     │
│  TwinPrediction (modelId + output + confidence)              │
│       ↓                                                      │
│  Model Calibrator (comparePrediction + calculateError)        │
│       ↓                                                      │
│  CalibrationReport (accuracy update + predictions)            │
│       ↓                                                      │
│  下一轮 experiment feedback                                  │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

## 预测类型

### Linear

y = intercept + Σ(coeff[i] · x[i])

适用: 线性趋势的物理化学过程

### Polynomial

y = Σ(coeff[i] · x^i) for i in 0..degree

适用: 含曲率的过程 (反应速率、扩散)

### Kinetic

C(t) = C0 · exp(-k · order · t)

适用: 一级/伪一级动力学过程 (降解、衰变)

## 校准循环

```
Experiment Result (observed)
       ↓
predict(spec, input) → y_predicted
       ↓
comparePrediction(y_predicted, y_observed)
       ↓
calculateError([...comparisons])
       ↓
updateParameters(params, lr, gradient)
       ↓
下次 prediction 用更新后的 parameters
```

## 集成接口

```ts
import { linearPredict, polynomialPredict, kineticPredict, predict, predictAndRecord } from './services/digital-twin/digital-twin-engine'
import { runCalibration, comparePrediction, calculateError } from './services/digital-twin/model-calibrator'

// 单点预测
const r1 = linearPredict({ kind: 'linear', coefficients: [1, 2], intercept: 0 }, { x: 3, y: 4 })

// 数据集校准
const cal = runCalibration(
  { kind: 'linear', coefficients: [1, 0], intercept: 0 },
  { inputs: [{ x: 1 }, { x: 2 }, { x: 3 }], outputs: [1.1, 2.0, 3.05] }
)
console.log(cal.rSquared, cal.rmse)
```

## 复用现有 Phase 8 类型

| 复用源 | 用途 |
|--------|------|
| Phase 8-H2 `ScientificDataset` | extractFeatures 输入 |
| Phase 8-H1 `OptimizationResult` | 校准后的结果对比 |
| Phase 8-K0 `Experiment` + `ExperimentResult` | 实验孪生适配器输入 |

数字孪生**仅消费**这些类型, 不修改其契约。

## 安全边界

- 所有预测函数纯函数,无副作用
- TwinParameter.value 严格 Number.isFinite
- TwinPrediction.confidence 严格 0..1
- updateParameters 学习率严格 [0, 1]
- 无随机数,无时间戳依赖 (除 timestamp 字段)
- 无 LLM 直连,无后端调用,无密钥存储