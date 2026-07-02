# QA Bench Report — 2026-07-02T18:10:28.120260

**总题数**: 10 | **PASS**: 5 | **WARN**: 4 | **FAIL**: 1 | **ERROR**: 0

**通过率**: 50.0%

## 按分类

| 分类 | PASS | WARN | FAIL | ERROR |
|---|---|---|---|---|
| member | 5 | 4 | 1 | 0 |

## 问题分布

| 类型 | 次数 |
|---|---|
| `intent_mismatch` | 5 |
| `missing_required_terms` | 1 |
| `duration_warn` | 1 |

## 7 维评分汇总 (v3.0)

**评分题数**: 10 | **一票否决**: 0


### 维度均分

| 维度 | 权重 | 均分 |
|---|---|---|
| intent | 10% | 0.50 |
| tool | 25% | 1.00 |
| content | 30% | 0.97 |
| rich | 5% | 1.00 |
| defense | 15% | 1.00 |
| perf | 10% | 0.96 |
| consistency | 5% | 1.00 |

### 分级分布

| 等级 | 范围 | 题数 |
|---|---|---|
| A | 90-100 | 8 |
| B | 75-89 | 2 |
| C | 60-74 | 0 |
| D | 40-59 | 0 |
| F | 0-39 | 0 |

## 失败题详情


### A03 (member) — WARN
**问题**: 请教谁研究饮用水？
- `intent_mismatch`: mismatch", "expect": "recommend_person", "actual": "search_info"

**回答预览 (前 200 字)**:
```
课题组有两位成员主要研究饮用水方向：

1. **宋洋**（研二），研究方向是**饮用水处理**，专注于微纳米气泡与膜的耦合应用，技能包括生物稳定性、管网生物膜、膜耦合。
2. **杨慈**（研三），研究方向是**饮用水安全**，探索微纳米气泡在饮用水安全保障领域的应用，技能包括饮用水安全、蜡样芽孢杆菌、微生物消杀。

```json
{
  "type": "member",
  "data":
```

### A04 (member) — FAIL
**问题**: 课题组有谁做水处理？
- `intent_mismatch`: mismatch", "expect": "recommend_person", "actual": "search_info"
- `missing_required_terms`: ed_terms", "missing": ["雒培媛", "杨慈"]

**回答预览 (前 200 字)**:
```
课题组有 **1** 名成员从事水处理相关研究：**宋洋**（研二）。他的研究方向是 **饮用水处理**，主要关注气泡与膜的耦合应用，技能包括生物稳定性、管网生物膜和膜耦合技术。

```json
{
  "type": "member",
  "data": {
    "members": [
      {
        "id": 13,
        "name": "宋洋",
  
```

### A05 (member) — WARN
**问题**: 陈金薪 leader 角色
- `intent_mismatch`: mismatch", "expect": "data_query", "actual": "search_info"

**回答预览 (前 200 字)**:
```
**陈金薪**，研二，课题组 **leader**（组长）。

- **研究方向**：气泡成核过程调控
- **核心技能**：自由基、界面反应、气泡溃灭
- **简介**：解析气泡溃灭过程的界面活化特征与 ·OH 生成动力学
- **在研项目**：气泡成核过程调控与设备研发（active）

```json
{
  "type": "member",
  "data": {
    "member
```

### A08 (member) — WARN
**问题**: 杜同贺 邮箱
- `intent_mismatch`: mismatch", "expect": "data_query", "actual": "search_info"

**回答预览 (前 200 字)**:
```
杜同贺的邮箱是：**320324492@qq.com**
```

### A09 (member) — WARN
**问题**: 列出所有 leader
- `duration_warn`: ion_warn", "duration_ms": 45879
- `intent_mismatch`: mismatch", "expect": "data_query", "actual": "search_info"

**回答预览 (前 200 字)**:
```
课题组中 role 为 **leader** 的成员只有一位：

**陈金薪**  
- **年级**：研二  
- **研究方向**：气泡成核过程调控  
- **技能**：自由基、界面反应、气泡溃灭  
- **简介**：解析气泡溃灭过程的界面活化特征与·OH生成动力学  

课题组的 **管理员（admin）** 共有 4 位：  
1. **王天志**（副教授，课题组负责人）  
2. *
```