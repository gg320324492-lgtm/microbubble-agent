# QA Bench Report — 2026-07-02T16:36:48.999128

**总题数**: 200 | **PASS**: 0 | **WARN**: 1 | **FAIL**: 13 | **ERROR**: 186

**通过率**: 0.0%

## 按分类

| 分类 | PASS | WARN | FAIL | ERROR |
|---|---|---|---|---|
| A | 0 | 1 | 13 | 5 |
| B | 0 | 0 | 0 | 19 |
| C | 0 | 0 | 0 | 19 |
| D | 0 | 0 | 0 | 18 |
| E | 0 | 0 | 0 | 19 |
| F | 0 | 0 | 0 | 18 |
| G | 0 | 0 | 0 | 18 |
| H | 0 | 0 | 0 | 19 |
| K | 0 | 0 | 0 | 23 |
| M | 0 | 0 | 0 | 19 |
| P | 0 | 0 | 0 | 9 |

## 问题分布

| 类型 | 次数 |
|---|---|
| `missing_tools` | 9 |
| `duration_warn` | 6 |
| `forbidden_names_data_bug` | 5 |
| `forbidden_names_appeared` | 5 |
| `fake_xml_leaked` | 2 |

## 7 维评分汇总 (v3.0)

**评分题数**: 14 | **一票否决**: 7


### 维度均分

| 维度 | 权重 | 均分 |
|---|---|---|
| intent | 10% | 1.00 |
| tool | 25% | 0.36 |
| content | 30% | 0.54 |
| rich | 5% | 1.00 |
| defense | 15% | 0.96 |
| perf | 10% | 0.83 |
| consistency | 5% | 1.00 |

### 分级分布

| 等级 | 范围 | 题数 |
|---|---|---|
| A | 90-100 | 1 |
| B | 75-89 | 2 |
| C | 60-74 | 4 |
| D | 40-59 | 0 |
| F | 0-39 | 7 |

## 失败题详情


### A-L1-0001 (A) — FAIL
**问题**: 王天志是干什么的？
- `missing_tools`: ng_tools", "missing": ["query_members"], "note": "tools_any — 任一即可"

**回答预览 (前 200 字)**:
```
王天志是我们课题组的**副教授**，也是**课题组负责人**。他的研究方向是 **微纳米气泡技术与应用** [1]。

## 核心信息
- **职称/角色**：副教授、课题组负责人
- **研究方向**：微纳米气泡技术与应用
- **技能专长**：项目管理、气泡生成、水处理、技术产业化
- **简介**：长期从事微纳米气泡技术研究与应用开发 [1]

王天志老师在微纳米气泡领域有着系统的理论基础和
```

### A-L1-0002 (A) — FAIL
**问题**: 杜同贺是学生吗？他的研究方向是什么？
- `missing_tools`: ng_tools", "missing": ["query_members"], "note": "tools_any — 任一即可"
- `forbidden_names_data_bug`: data_bug", "severity": "warn", "names": ["杜同贺"], "note": "forbidden 名字同时在 must_contain_any, qa-bench 数据设计 bug. 不计入真问题."

**回答预览 (前 200 字)**:
```
杜同贺是课题组的研一学生，即研究生一年级 [1]。他的研究方向是**污染控制与水质提升**，具体围绕微纳米气泡强化工艺研究与数据分析展开 [1]。

**基本信息**：
- **年级**：研一
- **研究方向**：污染控制与水质提升
- **技能**：微纳米气泡、水质提升、数据分析
- **个人简介**：围绕污染控制与水质提升，开展微纳米气泡强化工艺研究与数据分析
- **参与项目**：饮用水水
```

### A-L2-0003 (A) — FAIL
**问题**: 我们课题组成员里谁在做臭氧氧化相关研究？
- `fake_xml_leaked`: l_leaked", "patterns": ["<function\\s*=[^>]+>"]

**回答预览 (前 200 字)**:
```
<tool_call>
<function=query_members>
<parameter=research_area>臭氧微纳米气泡</parameter>
</function>
</tool_call>
```

### A-L2-0004 (A) — FAIL
**问题**: 杨慈是在读博士吗？
- `missing_tools`: ng_tools", "missing": ["query_members"], "note": "tools_any — 任一即可"
- `forbidden_names_data_bug`: data_bug", "severity": "warn", "names": ["杨慈"], "note": "forbidden 名字同时在 must_contain_any, qa-bench 数据设计 bug. 不计入真问题."

**回答预览 (前 200 字)**:
```
杨慈目前不是在读博士，而是**硕士三年级（研三）**学生。他的研究方向是**饮用水安全**，主要探索微纳米气泡在饮用水安全保障领域的应用，参与的项目是“饮用水水质提升与安全保障”。

```json
{
  "type": "member",
  "data": {
    "members": [
      {
        "id": 18,
        "name": "杨慈",
 
```

### A-L2-0005 (A) — WARN
**问题**: 我们课题组的博士后有哪几位？
- `duration_warn`: ion_warn", "duration_ms": 54014

**回答预览 (前 200 字)**:
```
课题组目前没有博士后成员。从成员数据库看，现有成员包括博士生（博一）、硕士生（研一至研三）、本科生（大三、大四）以及副教授。如果您需要了解其他年级的成员信息，我可以为您进一步查询。

```json
{
  "type": "member",
  "data": {
    "members": []
  }
}
```
```

### A-L2-0006 (A) — FAIL
**问题**: 王天志的导师是谁？
- `missing_tools`: ng_tools", "missing": ["query_members"], "note": "tools_any — 任一即可"
- `forbidden_names_appeared`: appeared", "names": ["王天志"]

**回答预览 (前 200 字)**:
```
根据系统记录，**王天志**本身是本课题组的负责人，职称**副教授**，属于导师角色而非学生。

- **研究方向**：微纳米气泡技术与应用
- **角色**：课题组负责人（admin）
- **技能**：项目管理、气泡生成、水处理、技术产业化
- **简介**：长期从事微纳米气泡技术研究与应用开发

系统中没有记录王天志读博时的导师信息。如果您想了解他博士阶段的导师是谁，建议直接向本人确认。


```

### A-L2-0008 (A) — FAIL
**问题**: 赵航佳目前带几个学生？
- `duration_warn`: ion_warn", "duration_ms": 33069
- `missing_tools`: ng_tools", "missing": ["query_members"], "note": "tools_any — 任一即可"
- `forbidden_names_data_bug`: data_bug", "severity": "warn", "names": ["赵航佳"], "note": "forbidden 名字同时在 must_contain_any, qa-bench 数据设计 bug. 不计入真问题."

**回答预览 (前 200 字)**:
```
根据现有资料，赵航佳目前是**博士一年级**学生，研究方向为黑臭水体治理，重点研究微纳米气泡与底泥-水界面的相互作用机制。从成员档案来看，**没有显示他指导或带领学生的记录**。作为博一学生，他更可能处于被指导阶段，而非导师角色。  
如果需要了解他参与的项目或团队协作情况，可以进一步查询。

```json
{
  "type": "member",
  "data": {
    "membe
```

### A-L2-0009 (A) — FAIL
**问题**: 我们课题组现在有多少在读硕士研究生？
- `duration_warn`: ion_warn", "duration_ms": 56485
- `forbidden_names_appeared`: appeared", "names": ["杜同贺", "杨慈", "宋洋", "李胜景"]

**回答预览 (前 200 字)**:
```
课题组目前有 **22 名在读硕士研究生**，分布如下：

- **研一**：7 人  
  耿嘉栋、吴怡霏、刘莫菲、陈天祥、刘子煜、张懿、杜同贺
- **研二**：10 人  
  关小未、宋洋、董昊宇、蒋芦笛、刘子毅、胡小琪、李胜景、王书馨、陈金薪、吴孟铨
- **研三**：5 人  
  李锐远、杨慈、余歆睿、韩重阳、张宏魁

```json
{
  "type": "member",
  
```

### A-L2-0011 (A) — FAIL
**问题**: 王天志最近一周完成了哪些任务？
- `missing_tools`: ng_tools", "missing": ["query_member_tasks"], "note": "tools_any — 任一即可"
- `forbidden_names_data_bug`: data_bug", "severity": "warn", "names": ["王天志"], "note": "forbidden 名字同时在 must_contain_any, qa-bench 数据设计 bug. 不计入真问题."

**回答预览 (前 200 字)**:
```
王天志最近一周完成了 **1 项** 任务：

- **任务标题**：跟王天志讨论论文  
- **优先级**：中等  
- **截止时间**：2026-07-03 07:00  
- **状态**：已完成（done）  

该任务目前没有关联的项目信息，描述字段为空。如果您需要查看更早的任务记录或当前进行中的任务，我可以继续帮您查询。
```

### A-L2-0012 (A) — FAIL
**问题**: 王天志手上还有多少个未完成的任务？
- `missing_tools`: ng_tools", "missing": ["query_member_tasks"], "note": "tools_any — 任一即可"
- `forbidden_names_appeared`: appeared", "names": ["王天志"]

**回答预览 (前 200 字)**:
```
王天志目前**没有未完成的任务**。

他当前有 1 个任务，状态为 **done（已完成）**：
- **任务标题**：跟王天志讨论论文
- **截止日期**：2026-07-03 07:00
- **优先级**：中等
- **进度**：100%

所有任务均已处理完毕，暂无待办或进行中的事项。
```

### A-L2-0016 (A) — FAIL
**问题**: 杜同贺和周之超谁当前任务更多？
- `fake_xml_leaked`: l_leaked", "patterns": ["<function\\s*=[^>]+>"]
- `duration_warn`: ion_warn", "duration_ms": 44244
- `missing_tools`: ng_tools", "missing": ["query_member_tasks"], "note": "tools_any — 任一即可"

**回答预览 (前 200 字)**:
```
<tool_call>
<function=query_all_member_tasks>
</function>
</tool_call>
```

### A-L2-0017 (A) — FAIL
**问题**: 我们课题组的博士生导师有哪几位？
- `duration_warn`: ion_warn", "duration_ms": 57621
- `forbidden_names_appeared`: appeared", "names": ["王天志"]

**回答预览 (前 200 字)**:
```
根据系统记录，课题组目前的博士生导师是：

**王天志** - 副教授
- **研究方向**：微纳米气泡技术与应用
- **主要技能**：项目管理、气泡生成、水处理、技术产业化
- **简介**：副教授，课题组负责人，长期从事微纳米气泡技术研究与应用开发

王天志老师是课题组的核心负责人，带领团队在微纳米气泡的生成、表征、水处理、农业应用等多个方向开展研究。从课题组成员构成来看，他指导的研究生覆盖
```

### A-L2-0019 (A) — FAIL
**问题**: 课题组成员中谁的研究方向跟微纳米气泡相关？
- `forbidden_names_appeared`: appeared", "names": ["王天志"]

**回答预览 (前 200 字)**:
```
课题组中有一位成员的研究方向直接与微纳米气泡相关：**王天志**。

**王天志**是课题组负责人，副教授，长期从事微纳米气泡技术研究与应用开发。他的研究方向是**微纳米气泡技术与应用**，主要技能包括项目管理、气泡生成、水处理以及技术产业化。作为课题组的核心成员，他在微纳米气泡的基础研究和应用转化方面都有深入布局。

```json
{
  "type": "member",
  "data":
```

### A-L3-0007 (A) — FAIL
**问题**: 杜同贺和赵航佳都在研究什么方向？给我一个对比。
- `duration_warn`: ion_warn", "duration_ms": 36602
- `missing_tools`: ng_tools", "missing": ["query_members"], "note": "tools_any — 任一即可"
- `forbidden_names_data_bug`: data_bug", "severity": "warn", "names": ["杜同贺", "赵航佳"], "note": "forbidden 名字同时在 must_contain_any, qa-bench 数据设计 bug. 不计入真问题."

**回答预览 (前 200 字)**:
```
杜同贺和赵航佳都在课题组从事微纳米气泡相关研究，但具体方向和侧重点有所不同。以下是详细对比：

## 一、研究方向概述

### 杜同贺
- **研究方向**：污染控制与水质提升
- **技能专长**：微纳米气泡、水质提升、数据分析
- **个人简介**：围绕污染控制与水质提升，开展微纳米气泡强化工艺研究与数据分析
- **参与项目**：饮用水水质提升与安全保障（项目状态：进行中）

### 赵航
```