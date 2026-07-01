# QA Bench Report — 2026-07-02T02:10:00.472013

**总题数**: 200 | **PASS**: 0 | **WARN**: 2 | **FAIL**: 26 | **ERROR**: 172

**通过率**: 0.0%

## 按分类

| 分类 | PASS | WARN | FAIL | ERROR |
|---|---|---|---|---|
| A | 0 | 1 | 18 | 0 |
| B | 0 | 1 | 8 | 10 |
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
| `forbidden_names_appeared` | 22 |
| `intent_mismatch` | 17 |
| `missing_tools` | 14 |
| `fake_xml_leaked` | 5 |
| `stream_error_event` | 5 |
| `stream_no_done` | 3 |
| `duration_warn` | 1 |
| `hallucinated_names` | 1 |

## 7 维评分汇总 (v3.0)

**评分题数**: 28 | **一票否决**: 19


### 维度均分

| 维度 | 权重 | 均分 |
|---|---|---|
| intent | 10% | 0.39 |
| tool | 25% | 0.50 |
| content | 30% | 0.46 |
| rich | 5% | 0.93 |
| defense | 15% | 0.84 |
| perf | 10% | 0.99 |
| consistency | 5% | 1.00 |

### 分级分布

| 等级 | 范围 | 题数 |
|---|---|---|
| A | 90-100 | 2 |
| B | 75-89 | 3 |
| C | 60-74 | 1 |
| D | 40-59 | 3 |
| F | 0-39 | 19 |

## 失败题详情


### A-L1-0001 (A) — WARN
**问题**: 王天志是干什么的？
- `duration_warn`: ion_warn", "duration_ms": 30207

**回答预览 (前 200 字)**:
```
王天志是课题组的负责人，担任副教授。他的主要研究方向是**微纳米气泡技术与应用**，长期从事该领域的技术研究与应用开发 [1]。

具体来说，他的工作涵盖以下几个方面：
- **核心研究**：微纳米气泡的生成机理、特性调控及其在水处理等领域的应用。
- **技能专长**：项目管理、气泡生成技术、水处理工艺以及技术产业化。
- **课题组角色**：作为负责人，他领导整个团队在微纳米气泡的基础研究、装
```

### A-L1-0002 (A) — FAIL
**问题**: 杜同贺是学生吗？他的研究方向是什么？
- `forbidden_names_appeared`: appeared", "names": ["杜同贺", "杨慈", "宋洋"]

**回答预览 (前 200 字)**:
```
杜同贺是课题组的**研一学生**（硕士研究生一年级），他的研究方向是**污染控制与水质提升**，主要围绕微纳米气泡强化工艺研究与数据分析展开工作 [1]。

## 基本信息

- **年级**：研一
- **研究方向**：污染控制与水质提升
- **技能**：微纳米气泡、水质提升、数据分析
- **简介**：围绕污染控制与水质提升，开展微纳米气泡强化工艺研究与数据分析
- **参与项目**：饮用水
```

### A-L2-0003 (A) — FAIL
**问题**: 我们课题组成员里谁在做臭氧氧化相关研究？
- `forbidden_names_appeared`: appeared", "names": ["王天志", "赵航佳"]

**回答预览 (前 200 字)**:
```
课题组中有多位成员的研究涉及**臭氧氧化**相关方向，主要集中在以下几位：

## 核心成员

1. **赵航佳**（博一）
   - 研究方向：**黑臭水体治理**
   - 技能：臭氧微纳米气泡、底泥-水界面、污染物去除
   - 简介：围绕微纳米气泡在黑臭水体治理中的应用开展研究，重点关注微纳米气泡与底泥-水界面污染物之间的相互作用机制

2. **胡小琪**（研二）
   - 研究方向：*
```

### A-L2-0004 (A) — FAIL
**问题**: 杨慈是在读博士吗？
- `forbidden_names_appeared`: appeared", "names": ["杨慈"]

**回答预览 (前 200 字)**:
```
杨慈目前**不是在读博士**，她是**硕士三年级**（研三）学生。

根据课题组成员信息，杨慈的基本情况如下：

- **年级**：研三（硕士三年级）
- **研究方向**：饮用水安全
- **主要技能**：饮用水安全、蜡样芽孢杆菌、微生物消杀
- **个人简介**：探索微纳米气泡在饮用水安全保障领域的应用
- **参与项目**：饮用水水质提升与安全保障（进行中）

所以杨慈是硕士研究生，不是博士
```

### A-L2-0005 (A) — FAIL
**问题**: 我们课题组的博士后有哪几位？
- `fake_xml_leaked`: l_leaked", "patterns": ["<function\\s*=[^>]+>"]
- `intent_mismatch`: mismatch", "expect": "search_info", "actual": "data_query"

**回答预览 (前 200 字)**:
```
<tool_call>
<function=query_members>
<parameter=grade>博士后研究员</parameter>
</function>
</tool_call>根据查询，当前课题组没有博士后研究员。
```

### A-L2-0006 (A) — FAIL
**问题**: 王天志的导师是谁？
- `forbidden_names_appeared`: appeared", "names": ["王天志"]

**回答预览 (前 200 字)**:
```
王天志老师是本课题组的负责人（PI），他的职称为**副教授**。他主要负责课题组的整体管理与研究方向把控，长期从事微纳米气泡技术的研究与应用开发。

如果您是想了解他具体的学术背景或师承关系（即他在博士阶段的导师），目前数据库中暂未收录这部分信息。

```json
{
  "type": "member",
  "data": {
    "members": [
      {
       
```

### A-L2-0008 (A) — FAIL
**问题**: 赵航佳目前带几个学生？
- `fake_xml_leaked`: l_leaked", "patterns": ["<function\\s*=[^>]+>"]
- `missing_tools`: ng_tools", "missing": ["query_members"], "note": "tools_any — 任一即可"
- `forbidden_names_appeared`: appeared", "names": ["赵航佳"]

**回答预览 (前 200 字)**:
```
<tool_call>
<function=query_members>
<parameter=supervisor_name>赵航佳</parameter>
</function>
</tool_call>根据工具返回的信息，赵航佳是课题组的**博一学生**，目前**没有显示其作为导师指导其他学生**的信息。他的个人资料中主要包含以下内容：

## 赵航佳基本信息
- **年级**：博士一年级

```

### A-L2-0009 (A) — FAIL
**问题**: 我们课题组现在有多少在读硕士研究生？
- `intent_mismatch`: mismatch", "expect": "search_info", "actual": "data_query"
- `forbidden_names_appeared`: appeared", "names": ["杜同贺", "杨慈", "宋洋", "李胜景"]

**回答预览 (前 200 字)**:
```
现在我有了所有成员的数据。让我统计一下在读硕士研究生的数量。从数据中筛选grade字段为"研一"、"研二"、"研三"的成员：

1. 关小未 - 研二
2. 宋洋 - 研二
3. 耿嘉栋 - 研一
4. 董昊宇 - 研二
5. 吴怡霏 - 研一
6. 蒋芦笛 - 研二
7. 李锐远 - 研三
8. 刘莫菲 - 研一
9. 刘子毅 - 研二
10. 陈天祥 - 研一
11. 杨慈 - 研三
12. 
```

### A-L2-0011 (A) — FAIL
**问题**: 王天志最近一周完成了哪些任务？
- `intent_mismatch`: mismatch", "expect": "search_info", "actual": "data_query"
- `missing_tools`: ng_tools", "missing": ["query_member_tasks"], "note": "tools_any — 任一即可"
- `forbidden_names_appeared`: appeared", "names": ["王天志"]

**回答预览 (前 200 字)**:
```
王天志目前没有已完成的任务记录。

这可能是因为：
1. 他的任务尚未标记为完成
2. 最近一周没有新增完成的任务

如果你想查看他**进行中**或**待办**的任务，我可以帮你查询。
```

### A-L2-0012 (A) — FAIL
**问题**: 王天志手上还有多少个未完成的任务？
- `stream_no_done`: _no_done", "severity": "fail", "expected": "done event", "actual": "no done event in stream", "context": "共 7 个事件，最后一个事件类型: error"
- `stream_error_event`: or_event", "severity": "fail", "expected": "no error event", "actual": "error: cannot access local variable 'final_text' where it is not associated with a value", "context": "SSE 流中出现 error 事件（应用错误传播到客户端）"
- `intent_mismatch`: mismatch", "expect": "search_info", "actual": "data_query"
- `missing_tools`: ng_tools", "missing": ["query_member_tasks"], "note": "tools_any — 任一即可"

**回答预览 (前 200 字)**:
```

```

### A-L2-0016 (A) — FAIL
**问题**: 杜同贺和周之超谁当前任务更多？
- `missing_tools`: ng_tools", "missing": ["query_member_tasks"], "note": "tools_any — 任一即可"
- `forbidden_names_appeared`: appeared", "names": ["杜同贺", "周之超"]

**回答预览 (前 200 字)**:
```
杜同贺当前有 **21 项任务**，周之超当前 **0 项任务**。

杜同贺的任务中，**进行中**的有 3 项（均为"完成 PMS 降解实验"，截止日期 2026-07-06），其余 18 项已完成。周之超目前没有分配任何任务。

**结论**：杜同贺的任务明显更多，且有 3 项待完成的实验任务需要在下周内完成。
```

### A-L2-0017 (A) — FAIL
**问题**: 我们课题组的博士生导师有哪几位？
- `intent_mismatch`: mismatch", "expect": "search_info", "actual": "data_query"
- `forbidden_names_appeared`: appeared", "names": ["王天志"]

**回答预览 (前 200 字)**:
```
根据课题组成员信息，目前课题组的博士生导师是：

**王天志**  
- 职称：副教授  
- 研究方向：微纳米气泡技术与应用  
- 角色：课题组负责人（admin）  
- 主要技能：项目管理、气泡生成、水处理、技术产业化  
- 简介：长期从事微纳米气泡技术研究与应用开发

目前数据库中仅有王天志副教授一位博士生导师。如果您需要了解其他教师成员或有其他查询需求，请随时告诉我。
```

### A-L2-0019 (A) — FAIL
**问题**: 课题组成员中谁的研究方向跟微纳米气泡相关？
- `forbidden_names_appeared`: appeared", "names": ["王天志", "杜同贺", "赵航佳", "杨慈", "宋洋", "贾琦", "李胜景", "周之超"]

**回答预览 (前 200 字)**:
```
课题组几乎所有成员的研究都围绕**微纳米气泡**展开，只是应用方向各有侧重。根据数据库中的成员资料，以下是与微纳米气泡直接相关的核心成员：

---

## 🔬 课题组负责人

**王天志**（副教授）
- **研究方向**：微纳米气泡技术与应用
- **技能**：项目管理、气泡生成、水处理、技术产业化
- **简介**：长期从事微纳米气泡技术研究与应用开发，是课题组整体方向的引领者

---


```

### A-L3-0007 (A) — FAIL
**问题**: 杜同贺和赵航佳都在研究什么方向？给我一个对比。
- `forbidden_names_appeared`: appeared", "names": ["杜同贺", "赵航佳"]

**回答预览 (前 200 字)**:
```
[综合阶段] 基于 query_members 和 search_knowledge 的返回结果，我已获取杜同贺和赵航佳的完整资料。现在进行对比分析。

杜同贺和赵航佳的研究方向对比如下：

## 杜同贺 vs 赵航佳 研究方向对比

| 维度 | 杜同贺 | 赵航佳 |
|------|--------|--------|
| **年级** | 研一 | 博一 |
| **研究方向** | 污染
```

### A-L3-0010 (A) — FAIL
**问题**: 列出王天志所在团队的全部成员及其研究方向。
- `intent_mismatch`: mismatch", "expect": "search_info", "actual": "data_query"
- `forbidden_names_appeared`: appeared", "names": ["王天志", "杜同贺", "赵航佳", "杨慈", "宋洋", "贾琦", "李胜景", "周之超", "测试"]

**回答预览 (前 200 字)**:
```
王天志是课题组负责人，其所在团队的全部成员及研究方向如下：

**核心管理成员（Admin/Leader）：**
- **王天志**（副教授）：微纳米气泡技术与应用
- **赵航佳**（博一）：黑臭水体治理
- **杜同贺**（研一）：污染控制与水质提升
- **陈金薪**（研二，Leader）：气泡成核过程调控

**研究成员：**
- **周之超**（大三）：表面污染去除
- **关小未**（
```

### A-L3-0013 (A) — FAIL
**问题**: 杨慈上周三有什么安排？
- `intent_mismatch`: mismatch", "expect": "search_info", "actual": "data_query"
- `missing_tools`: ng_tools", "missing": ["query_member_tasks"], "note": "tools_any — 任一即可"
- `forbidden_names_appeared`: appeared", "names": ["杨慈"]

**回答预览 (前 200 字)**:
```
杨慈上周三（6月24日）没有安排会议，也没有任务到期。

他目前所有任务（共4项）都已全部完成：
1. **准备毕业答辩**（5月26日完成）
2. **参加毕业答辩，大论文修改，准备并提交学位申请材料**（6月3日完成）
3. **实验室危废化学品回收**（5月25日完成）
4. **帮老师汇总高被引论文情况**（5月20日完成）

需要我帮杨慈新建任务或安排会议吗？
```

### A-L3-0014 (A) — FAIL
**问题**: 本月逾期未完成的任务都有哪些？谁负责？
- `intent_mismatch`: mismatch", "expect": "search_info", "actual": "data_query"
- `forbidden_names_appeared`: appeared", "names": ["宋洋", "测试"]

**回答预览 (前 200 字)**:
```
本月（2026年7月）逾期未完成的任务共有 **6 项**，均处于 `in_progress` 状态：

| # | 任务标题 | 负责人 | 截止日期 | 优先级 |
|---|---------|--------|----------|--------|
| 1 | 撰写第二篇文章 | **吴孟铨** | 2026-06-05 | 中 |
| 2 | 准备数学考试 | **张懿** | 202
```

### A-L3-0015 (A) — FAIL
**问题**: 下个月王天志有哪些会议要参加？
- `intent_mismatch`: mismatch", "expect": "search_info", "actual": "data_query"
- `forbidden_names_appeared`: appeared", "names": ["王天志"]

**回答预览 (前 200 字)**:
```
工具返回空，说明数据库中没有找到王天志在2026年8月的会议记录。这可能意味着他下个月没有安排会议，或者会议尚未录入系统。我需要如实告知用户查询结果。

根据回复模式（数据/操作），直接展示工具结果即可，不要强行延展。所以应该简短回复：没有找到相关会议记录。

另外，用户是管理员，可能需要更详细的信息，但工具返回为空，我只能如实告知。不需要附加其他内容。

开始回复。</think>查询结果显示，
```

### A-L3-0018 (A) — FAIL
**问题**: 王天志和李松泽的研究方向有什么交叉？
- `fake_xml_leaked`: l_leaked", "patterns": ["<function\\s*=[^>]+>"]
- `missing_tools`: ng_tools", "missing": ["query_members"], "note": "tools_any — 任一即可"
- `forbidden_names_appeared`: appeared", "names": ["王天志", "李松泽"]

**回答预览 (前 200 字)**:
```
王天志的研究方向已获取，但李松泽未找到，可能姓名有误。让我尝试模糊搜索：<tool_call>
<function=query_members>
<parameter=keyword>李松泽</parameter>
</function>
</tool_call><tool_call>
<function=query_members>
<parameter=keyword>李松泽</paramet
```

### B-L1-0081 (B) — FAIL
**问题**: 王天志现在有哪些任务？
- `stream_no_done`: _no_done", "severity": "fail", "expected": "done event", "actual": "no done event in stream", "context": "共 5 个事件，最后一个事件类型: error"
- `stream_error_event`: or_event", "severity": "fail", "expected": "no error event", "actual": "error: Error code: 429 - {'error': {'code': '429', 'message': 'Too many requests', 'type': 'limitation'}}", "context": "SSE 流中出现 error 事件（应用错误传播到客户端）"
- `stream_error_event`: or_event", "severity": "fail", "expected": "no error event", "actual": "error: Error code: 429 - {'error': {'code': '429', 'message': 'Too many requests', 'type': 'limitation'}}", "context": "SSE 流中出现 error 事件（应用错误传播到客户端）"
- `intent_mismatch`: mismatch", "expect": "search_info", "actual": "data_query"
- `missing_tools`: ng_tools", "missing": ["query_member_tasks"], "note": "tools_any — 任一即可"

**回答预览 (前 200 字)**:
```

```

### B-L2-0082 (B) — FAIL
**问题**: 杜同贺正在进行中的任务有哪些？
- `intent_mismatch`: mismatch", "expect": "data_query", "actual": "search_info"
- `missing_tools`: ng_tools", "missing": ["query_member_tasks"], "note": "tools_any — 任一即可"
- `forbidden_names_appeared`: appeared", "names": ["杜同贺"]

**回答预览 (前 200 字)**:
```
杜同贺目前有 **3 条进行中的任务**，都是同一项工作：

| 任务 | 截止日期 | 优先级 | 进度 |
|------|----------|--------|------|
| 完成 PMS 降解实验 | 2026-07-06（下周一） | 中 | 0% |

任务描述：要求在 **2026年7月6日** 前完成 PMS（过一硫酸盐）降解实验。

⚠️ 距离截止日期仅剩 **4 天**，
```

### B-L2-0083 (B) — FAIL
**问题**: 我有什么未完成的任务？
- `hallucinated_names`: ed_names", "names": ["王天志"]
- `intent_mismatch`: mismatch", "expect": "search_info", "actual": "data_query"
- `missing_tools`: ng_tools", "missing": ["query_my_tasks"], "note": "tools_any — 任一即可"
- `forbidden_names_appeared`: appeared", "names": ["王天志"]

**回答预览 (前 200 字)**:
```
你目前有 **3 个未完成任务**：

1. **明天下午3点跟王天志讨论论文** — 进度 0%，截止 2026-07-03
2. **整理课题组上半年的会议纪要** — 进度 0%，截止 2026-07-31
3. **跟王天志讨论论文** — 进度 0%，截止 2026-07-03

前两个任务的截止日期都在近期，尤其是明天下午的论文讨论，记得提前准备好材料哦。
```

### B-L2-0084 (B) — FAIL
**问题**: 赵航佳最近的逾期任务有几条？
- `fake_xml_leaked`: l_leaked", "patterns": ["<function\\s*=[^>]+>"]
- `intent_mismatch`: mismatch", "expect": "search_info", "actual": "data_query"
- `missing_tools`: ng_tools", "missing": ["query_member_tasks"], "note": "tools_any — 任一即可"
- `forbidden_names_appeared`: appeared", "names": ["赵航佳"]

**回答预览 (前 200 字)**:
```
<tool_call>
<function=query_tasks>
<parameter=assignee_name>赵航佳</parameter>
<parameter=status>overdue</parameter>
</function>
</tool_call>
```

### B-L2-0085 (B) — FAIL
**问题**: 杨慈上一周新增了几个任务？
- `fake_xml_leaked`: l_leaked", "patterns": ["<function\\s*=[^>]+>"]
- `missing_tools`: ng_tools", "missing": ["query_member_tasks"], "note": "tools_any — 任一即可"
- `forbidden_names_appeared`: appeared", "names": ["杨慈"]

**回答预览 (前 200 字)**:
```
<tool_call>
<function=query_tasks>
<parameter=assignee_name>杨慈</parameter>
<parameter=status>in_progress</parameter>
</function>
</tool_call><tool_call>
<function=get_task_stats>
<parameter=member_nam
```

### B-L2-0086 (B) — FAIL
**问题**: 课题组最近一周谁完成了最多任务？
- `intent_mismatch`: mismatch", "expect": "search_info", "actual": "data_query"
- `missing_tools`: ng_tools", "missing": ["query_tasks", "query_team_stats"], "note": "tools_any — 任一即可"
- `forbidden_names_appeared`: appeared", "names": ["杜同贺", "赵航佳", "李胜景", "测试"]

**回答预览 (前 200 字)**:
```
根据任务数据统计，**最近一周（6月25日-7月2日）完成任务最多的成员是：**

## 🏆 **杜同贺** — 完成 **14 个任务**

**完成的任务包括：**
- 配置服务器
- MDPI投稿
- 学习四六级监考
- 模拟任务
- 上传个人文献、PPT及实验记录至'小七助手'知识库
- 整理报销材料
- 测试腾讯会议与听会是否冲突
- 准备6月1日团建活动的游戏题目
- 英语上机考试
-
```

### B-L2-0087 (B) — WARN
**问题**: 本周有哪些高优先级逾期任务？
- `intent_mismatch`: mismatch", "expect": "search_info", "actual": "data_query"

**回答预览 (前 200 字)**:
```
本周高优先级逾期任务有 1 项：

**准备数学考试** — 负责人：张懿，截止日期：2026-06-20，当前进度 0%，状态：进行中。

该任务已逾期 12 天，建议尽快跟进。
```

### B-L2-0096 (B) — FAIL
**问题**: 我们课题组任务完成率是多少？
- `stream_no_done`: _no_done", "severity": "fail", "expected": "done event", "actual": "no done event in stream", "context": "共 7 个事件，最后一个事件类型: error"
- `stream_error_event`: or_event", "severity": "fail", "expected": "no error event", "actual": "error: Error code: 429 - {'error': {'code': '429', 'message': 'Too many requests', 'type': 'limitation'}}", "context": "SSE 流中出现 error 事件（应用错误传播到客户端）"
- `stream_error_event`: or_event", "severity": "fail", "expected": "no error event", "actual": "error: Error code: 429 - {'error': {'code': '429', 'message': 'Too many requests', 'type': 'limitation'}}", "context": "SSE 流中出现 error 事件（应用错误传播到客户端）"
- `intent_mismatch`: mismatch", "expect": "search_info", "actual": "data_query"
- `missing_tools`: ng_tools", "missing": ["query_tasks", "query_team_stats"], "note": "tools_any — 任一即可"

**回答预览 (前 200 字)**:
```

```

### B-L3-0088 (B) — FAIL
**问题**: 课题组成员中谁手上的任务负担最重？
- `intent_mismatch`: mismatch", "expect": "search_info", "actual": "data_query"
- `missing_tools`: ng_tools", "missing": ["query_member_tasks", "query_team_stats"], "note": "tools_any — 任一即可"
- `forbidden_names_appeared`: appeared", "names": ["王天志", "杜同贺", "赵航佳", "李胜景", "测试"]

**回答预览 (前 200 字)**:
```
根据任务数据，我来统计一下各成员的**进行中任务**数量：

| 成员 | 进行中任务数 | 主要任务 |
|------|-------------|----------|
| **陈天祥** | **7个** | 200L新机器壳子定制、测试水样、英语上机考试、编辑招聘启事、文献调研、雾化喷头选购 |
| **李胜景** | **5个** | 修改论文、集装箱展板、催麦蜂网站视频、微生物送样前
```