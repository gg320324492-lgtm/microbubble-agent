# QA Bench Report — 2026-07-02T16:59:51.843310

**总题数**: 35 | **PASS**: 5 | **WARN**: 21 | **FAIL**: 9 | **ERROR**: 0

**通过率**: 14.3%

## 按分类

| 分类 | PASS | WARN | FAIL | ERROR |
|---|---|---|---|---|
| meeting | 0 | 7 | 3 | 0 |
| member | 5 | 7 | 3 | 0 |
| task | 0 | 7 | 3 | 0 |

## 问题分布

| 类型 | 次数 |
|---|---|
| `intent_mismatch` | 27 |
| `duration_warn` | 12 |
| `missing_tools` | 4 |
| `fake_xml_leaked` | 3 |
| `missing_required_terms` | 2 |
| `duration_too_long` | 2 |
| `filler_phrases` | 1 |

## 7 维评分汇总 (v3.0)

**评分题数**: 35 | **一票否决**: 3


### 维度均分

| 维度 | 权重 | 均分 |
|---|---|---|
| intent | 10% | 0.23 |
| tool | 25% | 0.89 |
| content | 30% | 0.98 |
| rich | 5% | 1.00 |
| defense | 15% | 0.97 |
| perf | 10% | 0.82 |
| consistency | 5% | 1.00 |

### 分级分布

| 等级 | 范围 | 题数 |
|---|---|---|
| A | 90-100 | 17 |
| B | 75-89 | 12 |
| C | 60-74 | 3 |
| D | 40-59 | 0 |
| F | 0-39 | 3 |

## 失败题详情


### A01 (member) — FAIL
**问题**: 杨慈是研究什么的？
- `fake_xml_leaked`: l_leaked", "patterns": ["<function\\s*=[^>]+>"]
- `missing_required_terms`: ed_terms", "missing": ["蜡样芽孢杆菌", "微生物消杀"]

**回答预览 (前 200 字)**:
```
<tool_call>
<function=search_knowledge>
<parameter=query>微纳米气泡 饮用水安全</parameter>
<parameter=top_k>5</parameter>
</function>
</tool_call>
```

### A03 (member) — WARN
**问题**: 请教谁研究饮用水？
- `intent_mismatch`: mismatch", "expect": "recommend_person", "actual": "search_info"

**回答预览 (前 200 字)**:
```
课题组有2位成员从事饮用水相关研究：

- **宋洋**（研二），研究方向：**饮用水处理**，主要关注生物稳定性、管网生物膜、膜耦合，研究气泡与膜的耦合应用。
- **杨慈**（研三），研究方向：**饮用水安全**，主要关注蜡样芽孢杆菌、微生物消杀，探索微纳米气泡在饮用水安全保障领域的应用。

如果您想了解他们的具体研究内容、联系方式或正在进行的任务，我可以进一步提供信息。
```

### A04 (member) — FAIL
**问题**: 课题组有谁做水处理？
- `intent_mismatch`: mismatch", "expect": "recommend_person", "actual": "search_info"
- `missing_required_terms`: ed_terms", "missing": ["雒培媛", "杨慈"]

**回答预览 (前 200 字)**:
```
课题组有1名成员从事水处理相关研究：**宋洋**（研二），研究方向是**饮用水处理**，主要研究微纳米气泡在饮用水处理中的应用，特别是气泡与膜的耦合技术。她的核心技能包括生物稳定性、管网生物膜和膜耦合。

```json
{"type": "member", "data": {"members": [{"id": 13, "name": "宋洋", "grade": "研二", "research
```

### A05 (member) — WARN
**问题**: 陈金薪 leader 角色
- `intent_mismatch`: mismatch", "expect": "data_query", "actual": "search_info"

**回答预览 (前 200 字)**:
```
**陈金薪**是课题组的**组长（Leader）**，目前就读研二。

**研究方向**：气泡成核过程调控

**主要技能**：自由基、界面反应、气泡溃灭

**研究简介**：解析气泡溃灭过程的界面活化特征与·OH生成动力学

**参与项目**：「气泡成核过程调控与设备研发」（进行中）

**近期任务**：NTA测试数据分析（已完成，高优先级）

```json
{"type": "member"
```

### A08 (member) — WARN
**问题**: 杜同贺 邮箱
- `intent_mismatch`: mismatch", "expect": "data_query", "actual": "search_info"

**回答预览 (前 200 字)**:
```
**杜同贺**的邮箱是：**320324492@qq.com**
```

### A09 (member) — WARN
**问题**: 列出所有 leader
- `duration_warn`: ion_warn", "duration_ms": 51854
- `intent_mismatch`: mismatch", "expect": "data_query", "actual": "search_info"

**回答预览 (前 200 字)**:
```
课题组中只有一名 **leader**：**陈金薪**。他是研二学生，主要研究方向是**气泡成核过程调控**，专注于解析气泡溃灭过程的界面活化特征与·OH生成动力学，技能包括自由基、界面反应和气泡溃灭。

```json
{
  "type": "member",
  "data": {
    "members": [
      {
        "id": 7,
        "name
```

### A10 (member) — WARN
**问题**: 王天志 组长的研究方向
- `duration_warn`: ion_warn", "duration_ms": 59202

**回答预览 (前 200 字)**:
```
王天志是课题组的组长（副教授），他的研究方向是**微纳米气泡技术与应用**。根据他的个人简介，他长期从事微纳米气泡技术的研究与应用开发，并具备项目管理、气泡生成、水处理、技术产业化等技能 [1]。

## 微纳米气泡技术与应用：核心原理

微纳米气泡是指直径在微米（1-100 μm）或纳米级（<1 μm）的气泡，其核心特性在于**极高的比表面积**、**表面带负电荷（Zeta电位为负）**、**极
```

### A12 (member) — WARN
**问题**: 胡小琪 的研究
- `duration_warn`: ion_warn", "duration_ms": 36062

**回答预览 (前 200 字)**:
```
胡小琪是课题组的研二学生，研究方向为**黑臭水体**，具体课题是**臭氧微纳米气泡对黑臭水体泥/水界面微生境修复机理研究**。他目前参与了“饮用水水质提升与安全保障”项目（状态：active）[1]。

## 研究背景与意义
黑臭水体是我国城市水环境治理中的突出难题，其核心在于底泥‑水界面的污染负荷过高、微生物群落失衡、溶解氧匮乏。传统的清淤、曝气等手段存在能耗高、扰动底泥二次污染等问题。**臭氧
```

### A14 (member) — WARN
**问题**: 课题组有几个人？
- `intent_mismatch`: mismatch", "expect": "data_query", "actual": "search_info"

**回答预览 (前 200 字)**:
```
课题组成员数据库中暂无相关记录。目前无法查询到具体人数。

**参考**：
- 无相关资料可引用

请确认查询条件是否正确，或联系管理员确认成员数据是否已录入。
```

### A15 (member) — FAIL
**问题**: 组里有哪些角色？
- `duration_too_long`: too_long", "duration_ms": 66446
- `intent_mismatch`: mismatch", "expect": "data_query", "actual": "search_info"

**回答预览 (前 200 字)**:
```
根据课题组成员数据库，课题组内角色主要分为 **管理员（admin）**、**组长（leader）** 和 **普通成员（member）** 三类，同时成员按 **年级/职位** 可进一步细分。

## 📊 角色分类统计

| 角色类别 | 人数 | 代表成员（示例） | 主要职责 |
|----------|------|------------------|----------|
| **管理
```

### B01 (task) — WARN
**问题**: 我最近有什么任务？
- `duration_warn`: ion_warn", "duration_ms": 50413
- `intent_mismatch`: mismatch", "expect": "data_query", "actual": "search_info"

**回答预览 (前 200 字)**:
```
查询结果显示，您当前共有 **4 个任务**，全部处于 **已完成（Done）** 状态，**没有进行中或待办的任务**。以下是按时间排序的任务详情：

## 📋 您的任务列表

### 1. 明天下午3点跟王天志讨论论文
- **状态**：✅ 已完成
- **截止日期**：2026-07-03 07:00
- **优先级**：中等
- **描述**：（无详细描述）

### 2. 跟王天志讨论论
```

### B02 (task) — WARN
**问题**: 创建一个任务：完成实验报告
- `intent_mismatch`: mismatch", "expect": "execute_action", "actual": "search_info"

**回答预览 (前 200 字)**:
```
任务已成功创建：
- **任务标题**：完成实验报告
- **任务ID**：295

任务已添加到系统中，您可以随时通过任务ID进行查询、修改或分配。
```

### B03 (task) — FAIL
**问题**: 项目当前在做什么？
- `duration_warn`: ion_warn", "duration_ms": 40529
- `intent_mismatch`: mismatch", "expect": "data_query", "actual": "search_info"
- `missing_tools`: ng_tools", "missing": ["query_tasks"], "note": "tools_any — 任一即可"

**回答预览 (前 200 字)**:
```
根据课题组任务管理系统数据，当前项目主要在以下几个方向开展工作：

## 📊 **任务总体情况**
- **进行中任务**：20 个
- **已完成任务**：86 个
- **总任务数**：106 个

## 🔬 **当前重点工作方向**

### **1. 气泡成核过程调控与设备研发**
- **陈天祥**负责多项设备相关工作：200L新机器壳子定制、雾化喷头的选购、文献调研（微纳米气泡稳定性）
```

### B04 (task) — WARN
**问题**: 把任务 #1 标记为完成
- `intent_mismatch`: mismatch", "expect": "execute_action", "actual": "search_info"

**回答预览 (前 200 字)**:
```
任务 #1 已标记为完成。
```

### B05 (task) — WARN
**问题**: 紧急任务有哪些？
- `duration_warn`: ion_warn", "duration_ms": 55860
- `intent_mismatch`: mismatch", "expect": "data_query", "actual": "search_info"

**回答预览 (前 200 字)**:
```
当前课题组的紧急任务（高优先级且未完成）如下：

| 任务标题 | 负责人 | 状态 | 截止日期 |
|----------|--------|------|----------|
| **修改论文** | 李胜景 | 进行中 | 未设定 |
| **斜生栅藻SEM处理送样** | 关小未 | 进行中 | 未设定 |
| **准备数学考试** | 张懿 | 进行中 | 2026-06-20（已逾
```

### B06 (task) — WARN
**问题**: 我有多少进行中任务？
- `duration_warn`: ion_warn", "duration_ms": 49936
- `intent_mismatch`: mismatch", "expect": "data_query", "actual": "search_info"

**回答预览 (前 200 字)**:
```
您（测试小助手）目前有 **1 个进行中任务**：

| 任务标题 | 优先级 | 截止日期 | 进度 |
| :--- | :--- | :--- | :--- |
| **完成实验报告** | 中 | 未设置 | 0% |

---

### 团队整体进行中任务概览
目前团队共有 **20 个进行中任务**，分布在多位成员之间：

| 成员 | 任务标题 | 优先级 | 截止日期 | 进度 |
```

### B07 (task) — FAIL
**问题**: 删除任务 #999
- `intent_mismatch`: mismatch", "expect": "execute_action", "actual": "search_info"
- `missing_tools`: ng_tools", "missing": ["delete_task"], "note": "tools_any — 任一即可"

**回答预览 (前 200 字)**:
```
任务 #999 不存在，无法删除。

可以帮你做什么？  
- **查看任务列表** → `查询任务`  
- **新建任务** → `创建任务 #新任务`  

试试这些？
```

### B08 (task) — WARN
**问题**: 延期了怎么办？
- `filler_phrases`: _phrases", "count": 1
- `duration_warn`: ion_warn", "duration_ms": 45180
- `intent_mismatch`: mismatch", "expect": "casual_chat", "actual": "search_info"

**回答预览 (前 200 字)**:
```
目前课题组有 **6 个任务已逾期**（截止日期早于今天 2026-07-02），全部仍处于 **“进行中”** 状态，需要尽快跟进处理。

## 📅 逾期任务清单（按逾期时间排序）

| 任务 | 负责人 | 原定截止 | 逾期天数 | 优先级 |
|------|--------|----------|----------|--------|
| 互联网+ PPT 制作 | **韩重阳** |
```

### B09 (task) — WARN
**问题**: 高优先级任务
- `duration_warn`: ion_warn", "duration_ms": 50657
- `intent_mismatch`: mismatch", "expect": "data_query", "actual": "search_info"

**回答预览 (前 200 字)**:
```
## 📋 高优先级任务总览

共找到 **107** 条任务记录，其中高优先级任务筛选如下：

---

### 🔴 进行中（3项）

| 任务 | 负责人 | 截止日期 | 进度 |
|------|--------|----------|------|
| **修改论文** | 李胜景 | - | 0% |
| **斜生栅藻SEM处理送样** | 关小未 | - | 0% |
| **搭建膜法
```

### B10 (task) — FAIL
**问题**: 把任务 #3 分配给陈金薪
- `intent_mismatch`: mismatch", "expect": "execute_action", "actual": "search_info"
- `missing_tools`: ng_tools", "missing": ["update_task"], "note": "tools_any — 任一即可"

**回答预览 (前 200 字)**:
```
我需要先查询任务 #3 的具体信息，并确认陈金薪是否为课题组成员，然后进行分配操作。

**步骤 1：查询任务 #3 的信息**
```python
query_tasks(task_id=3)
```

**步骤 2：查询陈金薪的成员信息**
```python
get_member_profile(name="陈金薪")
```

根据查询到的信息，如果任务 #3 存在且状态允许分配，并且陈金
```

### C01 (meeting) — WARN
**问题**: 最近的会议
- `intent_mismatch`: mismatch", "expect": "data_query", "actual": "search_info"

**回答预览 (前 200 字)**:
```
目前数据库中暂无会议记录，可能会议信息尚未录入系统。建议您检查会议是否已通过其他方式登记，或者告诉我具体的会议日期范围，我可以帮您进一步查询。
```

### C02 (meeting) — FAIL
**问题**: 上周开了什么会？
- `fake_xml_leaked`: l_leaked", "patterns": ["<function\\s*=[^>]+>"]
- `intent_mismatch`: mismatch", "expect": "data_query", "actual": "search_info"
- `missing_tools`: ng_tools", "missing": ["query_meetings"], "note": "tools_any — 任一即可"

**回答预览 (前 200 字)**:
```
<tool_call>
<function=query_meetings>
<parameter=date_from>2026-06-22</parameter>
<parameter=date_to>2026-06-28</parameter>
</function>
</tool_call>
```

### C03 (meeting) — FAIL
**问题**: 有什么关于臭氧微纳米气泡的会议？
- `duration_too_long`: too_long", "duration_ms": 70431
- `intent_mismatch`: mismatch", "expect": "data_query", "actual": "search_info"

**回答预览 (前 200 字)**:
```
根据课题组会议记录，近期有多个与**臭氧微纳米气泡**相关的会议，按时间倒序列出如下：

### 1. 实验相关工作安排
- **日期**：2026-06-18
- **状态**：已完成
- **关键内容**：
  - 宋洋汇报了臭氧微纳米气泡在加压螺管输送系统的**水力相似性计算**，讨论了几何相似、运动相似和动力相似的原理 [1]。
  - 杜同贺汇报了**臭氧微纳米气泡协同紫外降解碘海醇**
```

### C04 (meeting) — WARN
**问题**: 今天的会议
- `intent_mismatch`: mismatch", "expect": "data_query", "actual": "search_info"

**回答预览 (前 200 字)**:
```
今天（2026年7月2日）暂时没有安排会议记录。

如果你想查看：
- **近期的会议**：可以告诉我查看本周或上周的会议
- **特定主题的会议**：比如"微纳米气泡相关会议"、"组会"等
- **明天或这周的安排**：我可以帮您查询其他日期的会议

需要我帮您查其他时间的会议吗？
```

### C05 (meeting) — WARN
**问题**: 2026年5月28日 例会讲了什么
- `intent_mismatch`: mismatch", "expect": "data_query", "actual": "search_info"

**回答预览 (前 200 字)**:
```
根据会议系统查询，**2026年5月28日及前后两天均无会议记录**。

可能的情况：
1. 当天确实没有安排例会
2. 会议记录尚未录入系统

如果您记得会议的其他信息（如主题关键词、大致时间段），我可以进一步帮您搜索。
```

### C06 (meeting) — FAIL
**问题**: 我有哪些待开的会议？
- `fake_xml_leaked`: l_leaked", "patterns": ["<function\\s*=[^>]+>"]
- `intent_mismatch`: mismatch", "expect": "data_query", "actual": "search_info"

**回答预览 (前 200 字)**:
```
<tool_call>
<function=query_meetings>
<parameter=keyword></parameter>
</function>
</tool_call>
```

### C07 (meeting) — WARN
**问题**: 明天有什么会议？
- `intent_mismatch`: mismatch", "expect": "data_query", "actual": "search_info"

**回答预览 (前 200 字)**:
```
明天（2026年7月3日）没有会议安排。

如果您需要安排明天的会议或查看其他日期的会议安排，请随时告诉我。
```

### C08 (meeting) — WARN
**问题**: 组会一般讨论什么
- `duration_warn`: ion_warn", "duration_ms": 46783
- `intent_mismatch`: mismatch", "expect": "explain_concept", "actual": "search_info"

**回答预览 (前 200 字)**:
```
组会是课题组定期举行的核心学术与管理活动，旨在**同步研究进展、解决技术难题、规划团队方向并促进成员协作**。它不仅是信息交换的平台，更是思想碰撞、问题诊断和资源整合的关键环节。根据近期会议记录，组会讨论内容通常涵盖以下几个核心维度 [1]：

## 1. **项目预算与成本核算**
   - **讨论内容**：针对具体项目的设备运行费用、耗材成本、电费等进行精细化核算与方案制定。
   - **
```

### C09 (meeting) — WARN
**问题**: 查一下第 3 个会议
- `duration_warn`: ion_warn", "duration_ms": 53182
- `intent_mismatch`: mismatch", "expect": "data_query", "actual": "search_info"

**回答预览 (前 200 字)**:
```
根据最近 30 天的会议记录，按时间倒序排列，第 3 个会议的详细信息如下：

### 📋 会议基本信息
- **标题**：脂质纳米气泡分子动力学模拟研究（北航林绪波副教授分享会）
- **日期**：2026-06-26
- **状态**：已完成
- **开始时间**：20:00
- **会议 ID**：137

### 📝 关键内容摘要
1. **研究目标**：为揭示脂质纳米气泡与膜的相互作用，
```

### C10 (meeting) — WARN
**问题**: 远紫外相关会议
- `duration_warn`: ion_warn", "duration_ms": 50902
- `intent_mismatch`: mismatch", "expect": "data_query", "actual": "search_info"

**回答预览 (前 200 字)**:
```
根据知识库记录，课题组近期涉及**远紫外（222nm）**的相关会议如下：

---

## 📌 课题组内部会议

### 1. 2026-06-12：远紫外(222nm)对于污水处理的应用
**徐佳乐博士学术报告**

**报告主题**：《远紫外(222nm)对于污水处理的应用：从光化学特性到背景成分的影响》

**核心内容**：
- **222nm 远紫外优势**：相比传统 254nm UV，
```