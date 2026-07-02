# QA Bench Report — 2026-07-02T18:08:01.339277

**总题数**: 10 | **PASS**: 5 | **WARN**: 3 | **FAIL**: 2 | **ERROR**: 0

**通过率**: 50.0%

## 按分类

| 分类 | PASS | WARN | FAIL | ERROR |
|---|---|---|---|---|
| member | 5 | 3 | 2 | 0 |

## 问题分布

| 类型 | 次数 |
|---|---|
| `intent_mismatch` | 3 |
| `duration_warn` | 1 |
| `forbidden_names_listing_question` | 1 |
| `duration_too_long` | 1 |
| `forbidden_names_appeared` | 1 |
| `missing_required_terms` | 1 |

## 7 维评分汇总 (v3.0)

**评分题数**: 10 | **一票否决**: 0


### 维度均分

| 维度 | 权重 | 均分 |
|---|---|---|
| intent | 10% | 0.70 |
| tool | 25% | 0.90 |
| content | 30% | 0.91 |
| rich | 5% | 1.00 |
| defense | 15% | 1.00 |
| perf | 10% | 0.88 |
| consistency | 5% | 1.00 |

### 分级分布

| 等级 | 范围 | 题数 |
|---|---|---|
| A | 90-100 | 7 |
| B | 75-89 | 2 |
| C | 60-74 | 1 |
| D | 40-59 | 0 |
| F | 0-39 | 0 |

## 失败题详情


### A01 (member) — WARN
**问题**: 杨慈是研究什么的？
- `duration_warn`: ion_warn", "duration_ms": 41119
- `forbidden_names_listing_question`: question", "severity": "info", "names": ["杜同贺"], "note": "query 是 '列出/所有/哪些' 题型, 答案列名字合理. 不计入真问题."

**回答预览 (前 200 字)**:
```
杨慈是课题组的**研三**成员，研究方向是**饮用水安全**，主要技能包括**蜡样芽孢杆菌**和**微生物消杀**。她致力于探索微纳米气泡技术在饮用水安全保障领域的应用，特别是在微生物风险控制方面。

### 研究方向详解
杨慈的研究聚焦于饮用水中的微生物安全问题，具体关注**蜡样芽孢杆菌**（*Bacillus cereus*）这类食源性致病菌的消杀。她的工作核心是利用微纳米气泡的独特物理化学性
```

### A02 (member) — FAIL
**问题**: 宋洋做什么方向？
- `duration_too_long`: too_long", "duration_ms": 76518
- `forbidden_names_appeared`: appeared", "names": ["杨慈"]

**回答预览 (前 200 字)**:
```
## 宋洋的研究方向

**宋洋（研二）** 的主要研究方向是 **饮用水处理**，具体聚焦于 **生物稳定性、管网生物膜、膜耦合** 三个方向。他属于课题组的 **微纳米气泡饮用水处理组**，核心研究内容是 **气泡与膜的耦合应用**，即探索微纳米气泡技术如何与膜工艺协同提升饮用水处理效果。

### 1. 核心研究方向

| 维度 | 内容 |
|------|------|
| **研究领域
```

### A04 (member) — FAIL
**问题**: 课题组有谁做水处理？
- `intent_mismatch`: mismatch", "expect": "recommend_person", "actual": "search_info"
- `missing_required_terms`: ed_terms", "missing": ["雒培媛", "宋洋", "杨慈"]

**回答预览 (前 200 字)**:
```
[计划阶段] 我已主动查询 2 个工具获取背景信息。
```

### A05 (member) — WARN
**问题**: 陈金薪 leader 角色
- `intent_mismatch`: mismatch", "expect": "data_query", "actual": "search_info"

**回答预览 (前 200 字)**:
```
**陈金薪**是课题组的**组长（Leader）**，目前为**研二**学生。

### 📋 基本信息
- **研究方向**：气泡成核过程调控
- **核心技能**：自由基、界面反应、气泡溃灭
- **个人简介**：解析气泡溃灭过程的界面活化特征与·OH生成动力学
- **参与项目**：气泡成核过程调控与设备研发（进行中）

### 🧪 研究内容解读
陈金薪的研究聚焦于微纳米气泡的**基础科学问题
```

### A06 (member) — WARN
**问题**: 雒培媛 现在在哪？
- `intent_mismatch`: mismatch", "expect": "search_info", "actual": "data_query"

**回答预览 (前 200 字)**:
```
雒培媛目前已毕业，现在在同济大学攻读博士。她的研究方向是微纳米气泡水处理，曾参与课题组的微纳米气泡相关研究与实验工作。
```