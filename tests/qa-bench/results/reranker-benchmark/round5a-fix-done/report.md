# QA Bench Report — 2026-07-02T01:08:02.878209

**总题数**: 200 | **PASS**: 3 | **WARN**: 1 | **FAIL**: 71 | **ERROR**: 125

**通过率**: 1.5%

## 按分类

| 分类 | PASS | WARN | FAIL | ERROR |
|---|---|---|---|---|
| A | 1 | 1 | 17 | 0 |
| B | 1 | 0 | 18 | 0 |
| C | 1 | 0 | 18 | 0 |
| D | 0 | 0 | 18 | 0 |
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
| `missing_tools` | 55 |
| `intent_mismatch` | 38 |
| `fake_xml_leaked` | 30 |
| `forbidden_names_appeared` | 29 |
| `stream_error_event` | 24 |
| `duration_warn` | 10 |
| `placeholder_text` | 2 |
| `tool_error_with_excuse` | 2 |
| `filler_phrases` | 1 |

## 7 维评分汇总 (v3.0)

**评分题数**: 75 | **一票否决**: 54


### 维度均分

| 维度 | 权重 | 均分 |
|---|---|---|
| intent | 10% | 0.49 |
| tool | 25% | 0.27 |
| content | 30% | 0.56 |
| rich | 5% | 0.72 |
| defense | 15% | 0.78 |
| perf | 10% | 0.95 |
| consistency | 5% | 1.00 |

### 分级分布

| 等级 | 范围 | 题数 |
|---|---|---|
| A | 90-100 | 3 |
| B | 75-89 | 5 |
| C | 60-74 | 6 |
| D | 40-59 | 7 |
| F | 0-39 | 54 |

## 失败题详情


### A-L1-0002 (A) — FAIL
**问题**: 杜同贺是学生吗？他的研究方向是什么？
- `forbidden_names_appeared`: appeared", "names": ["杜同贺"]

**回答预览 (前 200 字)**:
```
杜同贺是课题组的研一学生，研究方向是**污染控制与水质提升**。他主要围绕微纳米气泡强化工艺开展研究，同时负责数据分析工作。目前，他正在参与“饮用水水质提升与安全保障”项目，并承担了“完成 PMS 降解实验”等任务。

```json
{
  "type": "member",
  "data": {
    "members": [
      {
        "id": 3,
      
```

### A-L2-0003 (A) — FAIL
**问题**: 我们课题组成员里谁在做臭氧氧化相关研究？
- `fake_xml_leaked`: l_leaked", "patterns": ["<function\\s*=[^>]+>"]
- `forbidden_names_appeared`: appeared", "names": ["王天志", "赵航佳"]

**回答预览 (前 200 字)**:
```
知识库搜索结果显示，课题组有**臭氧微纳米气泡**相关的研究，但没有直接列出具体成员。我需要从成员列表中筛选出与臭氧氧化相关的成员。根据之前的成员列表，我注意到有几个成员的研究方向可能与臭氧氧化相关：

1. **赵航佳**：研究方向是"黑臭水体治理"，技能包括"臭氧微纳米气泡"，这直接提到了臭氧。
2. **胡小琪**：研究方向是"黑臭水体"，简介中提到"臭氧微纳米气泡对黑臭水体泥/水界面微生境
```

### A-L2-0004 (A) — FAIL
**问题**: 杨慈是在读博士吗？
- `forbidden_names_appeared`: appeared", "names": ["赵航佳", "杨慈"]

**回答预览 (前 200 字)**:
```
根据课题组成员数据库的查询结果，**杨慈目前不是在读博士**。

### 基本信息
- **姓名**：杨慈
- **年级**：**研三**（硕士三年级）
- **研究方向**：饮用水安全
- **邮箱**：yc3259672120@163.com
- **技能**：饮用水安全、蜡样芽孢杆菌、微生物消杀
- **个人简介**：探索微纳米气泡在饮用水安全保障领域的应用
- **参与项目**：饮用水水质
```

### A-L2-0005 (A) — WARN
**问题**: 我们课题组的博士后有哪几位？
- `duration_warn`: ion_warn", "duration_ms": 30378
- `intent_mismatch`: mismatch", "expect": "search_info", "actual": "data_query"

**回答预览 (前 200 字)**:
```
根据课题组成员数据库查询，目前没有博士后成员。

课题组现有成员的年级分布为：
- **博士**：1人（博一）
- **硕士**：研一、研二、研三
- **本科**：大三、大四
- **教职工**：副教授

如果您需要查询特定人员的信息，请提供姓名或研究方向，我可以进一步帮您查找。
```

### A-L2-0006 (A) — FAIL
**问题**: 王天志的导师是谁？
- `forbidden_names_appeared`: appeared", "names": ["王天志"]

**回答预览 (前 200 字)**:
```
**王天志**是本课题组的负责人（Admin），职称为**副教授**，长期从事微纳米气泡技术研究与应用开发。

关于"导师"这一信息，课题组的成员数据库中并未记录每位成员的导师归属关系。不过从角色和职称来看，王天志老师作为课题组负责人（副教授），实际上就是整个微纳米气泡课题组的指导教师，组内的研究生和本科生都在他的指导下开展研究工作。

如果你问的是某位特定同学的导师（比如是否由王天志老师亲自指导
```

### A-L2-0008 (A) — FAIL
**问题**: 赵航佳目前带几个学生？
- `intent_mismatch`: mismatch", "expect": "search_info", "actual": "data_query"
- `missing_tools`: ng_tools", "missing": ["query_members"], "note": "tools_any — 任一即可"
- `forbidden_names_appeared`: appeared", "names": ["赵航佳"]

**回答预览 (前 200 字)**:
```
根据查询结果，赵航佳目前是**博一**学生，主要研究方向是**黑臭水体治理**，专注于微纳米气泡在底泥-水界面污染物去除中的应用。

从返回的资料来看，**没有信息显示赵航佳目前有带学生**。他本人是博士一年级学生，角色为管理员，但没有带学生的记录。

如果您想了解课题组其他成员的带学生情况，或者需要查询更详细的团队结构信息，可以告诉我具体需求。
```

### A-L2-0009 (A) — FAIL
**问题**: 我们课题组现在有多少在读硕士研究生？
- `fake_xml_leaked`: l_leaked", "patterns": ["<function\\s*=[^>]+>"]
- `duration_warn`: ion_warn", "duration_ms": 36632
- `intent_mismatch`: mismatch", "expect": "search_info", "actual": "data_query"
- `forbidden_names_appeared`: appeared", "names": ["杜同贺", "杨慈", "宋洋", "李胜景"]

**回答预览 (前 200 字)**:
```
课题组目前有 **15 名在读硕士研究生**，具体年级分布如下：

**研一（6人）**
- 耿嘉栋、吴怡霏、刘莫菲、陈天祥、刘子煜、张懿、杜同贺

**研二（8人）**
- 关小未、宋洋、董昊宇、蒋芦笛、刘子毅、胡小琪、李胜景、王书馨、陈金薪、吴孟铨

**研三（4人）**
- 李锐远、杨慈、余歆睿、韩重阳、张宏魁

```json
{
  "type": "member",
  "data":
```

### A-L2-0011 (A) — FAIL
**问题**: 王天志最近一周完成了哪些任务？
- `intent_mismatch`: mismatch", "expect": "search_info", "actual": "data_query"
- `missing_tools`: ng_tools", "missing": ["query_member_tasks"], "note": "tools_any — 任一即可"
- `forbidden_names_appeared`: appeared", "names": ["王天志"]

**回答预览 (前 200 字)**:
```
王天志，副教授，课题组负责人，长期从事微纳米气泡技术研究与应用开发。研究方向是微纳米气泡技术与应用，技能包括项目管理、气泡生成、水处理、技术产业化。根据系统查询，**王天志**（副教授，课题组负责人）在最近一周内**没有已完成的任务记录**。

如果您想了解他的其他任务状态（如进行中或待办），可以告诉我进一步查询。
```

### A-L2-0012 (A) — FAIL
**问题**: 王天志手上还有多少个未完成的任务？
- `stream_error_event`: or_event", "severity": "fail", "expected": "no error event", "actual": "error: Error code: 429 - {'error': {'code': '429', 'message': 'Too many requests', 'type': 'limitation'}}", "context": "SSE 流中出现 error 事件（应用错误传播到客户端）"
- `stream_error_event`: or_event", "severity": "fail", "expected": "no error event", "actual": "error: Error code: 429 - {'error': {'code': '429', 'message': 'Too many requests', 'type': 'limitation'}}", "context": "SSE 流中出现 error 事件（应用错误传播到客户端）"
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
周之超当前没有任务。杜同贺有 2 个进行中的任务（均为 PMS 降解实验），而周之超的任务列表为空。因此，**杜同贺当前任务更多**。

**杜同贺进行中的任务：**
1. **完成 PMS 降解实验**（截止 2026-07-06，优先级中）
2. **完成 PMS 降解实验**（同上，可能是重复或分步任务）

**周之超：** 暂无分配的任务。
```

### A-L2-0017 (A) — FAIL
**问题**: 我们课题组的博士生导师有哪几位？
- `fake_xml_leaked`: l_leaked", "patterns": ["<function\\s*=[^>]+>"]
- `missing_tools`: ng_tools", "missing": ["query_members"], "note": "tools_any — 任一即可"

**回答预览 (前 200 字)**:
```
<tool_call>
<function=query_members>
<parameter=grade>博导</parameter>
</function>
</tool_call>
```

### A-L2-0019 (A) — FAIL
**问题**: 课题组成员中谁的研究方向跟微纳米气泡相关？
- `fake_xml_leaked`: l_leaked", "patterns": ["<function\\s*=[^>]+>"]
- `missing_tools`: ng_tools", "missing": ["query_members"], "note": "tools_any — 任一即可"

**回答预览 (前 200 字)**:
```
<tool_call>
<function=query_members>
<parameter=keyword>微纳米气泡</parameter>
</function>
</tool_call>
```

### A-L3-0007 (A) — FAIL
**问题**: 杜同贺和赵航佳都在研究什么方向？给我一个对比。
- `fake_xml_leaked`: l_leaked", "patterns": ["<function\\s*=[^>]+>"]
- `missing_tools`: ng_tools", "missing": ["query_members"], "note": "tools_any — 任一即可"
- `forbidden_names_appeared`: appeared", "names": ["杜同贺", "赵航佳"]

**回答预览 (前 200 字)**:
```
我来查询杜同贺和赵航佳的研究方向信息。<tool_call>
<function=get_member_profile>
<parameter=name>杜同贺</parameter>
</function>
</tool_call><tool_call>
<function=get_member_profile>
<parameter=name>赵航佳</parameter>
</functio
```

### A-L3-0010 (A) — FAIL
**问题**: 列出王天志所在团队的全部成员及其研究方向。
- `fake_xml_leaked`: l_leaked", "patterns": ["<function\\s*=[^>]+>"]
- `intent_mismatch`: mismatch", "expect": "search_info", "actual": "data_query"
- `missing_tools`: ng_tools", "missing": ["query_members"], "note": "tools_any — 任一即可"
- `forbidden_names_appeared`: appeared", "names": ["王天志"]

**回答预览 (前 200 字)**:
```
<tool_call>
<function=query_members>
<parameter=team_name>王天志</parameter>
</function>
</tool_call><tool_call>
<function=query_members>
<parameter=team_id>team_001</parameter>
</function>
</tool_call>
```

### A-L3-0013 (A) — FAIL
**问题**: 杨慈上周三有什么安排？
- `fake_xml_leaked`: l_leaked", "patterns": ["<function\\s*=[^>]+>"]
- `intent_mismatch`: mismatch", "expect": "search_info", "actual": "data_query"
- `missing_tools`: ng_tools", "missing": ["query_member_tasks"], "note": "tools_any — 任一即可"
- `forbidden_names_appeared`: appeared", "names": ["杨慈"]

**回答预览 (前 200 字)**:
```
<tool_call>
<function=get_member_profile>
<parameter=member_name>杨慈</parameter>
</function>
</tool_call>根据查询结果，**杨慈在上周三（2026年6月24日）没有会议安排**，也没有截止日期为该日的任务。

他目前有4个任务，但都已全部完成：
1. **准备毕业答辩**（截止2026-05-26
```

### A-L3-0014 (A) — FAIL
**问题**: 本月逾期未完成的任务都有哪些？谁负责？
- `fake_xml_leaked`: l_leaked", "patterns": ["<function\\s*=[^>]+>"]
- `duration_warn`: ion_warn", "duration_ms": 32048
- `intent_mismatch`: mismatch", "expect": "search_info", "actual": "data_query"
- `forbidden_names_appeared`: appeared", "names": ["宋洋", "测试"]

**回答预览 (前 200 字)**:
```
工具返回了6个逾期任务。现在，我需要筛选出截止日期在2026年7月的任务。查看所有任务的due_date：

1.  id:56, due_date:2026-06-05（6月）
2.  id:103, due_date:2026-06-20（6月）
3.  id:75, due_date:2026-06-04（6月）
4.  id:77, due_date:2026-05-29（5月）
5.  
```

### A-L3-0015 (A) — FAIL
**问题**: 下个月王天志有哪些会议要参加？
- `fake_xml_leaked`: l_leaked", "patterns": ["<function\\s*=[^>]+>"]
- `intent_mismatch`: mismatch", "expect": "search_info", "actual": "data_query"
- `missing_tools`: ng_tools", "missing": ["query_meetings"], "note": "tools_any — 任一即可"
- `forbidden_names_appeared`: appeared", "names": ["王天志"]

**回答预览 (前 200 字)**:
```
<tool_call>
<function=query_meetings>
<parameter=keyword>王天志</parameter>
<parameter=date_from>2026-08-01</parameter>
<parameter=date_to>2026-08-31</parameter>
</function>
</tool_call><tool_call>
<func
```

### A-L3-0018 (A) — FAIL
**问题**: 王天志和李松泽的研究方向有什么交叉？
- `forbidden_names_appeared`: appeared", "names": ["王天志", "李胜景", "李松泽"]

**回答预览 (前 200 字)**:
```
课题组中姓李的成员只有**李锐远**和**李胜景**，没有找到名为"**李松泽**"的成员。

---

### 王天志的研究方向

根据系统记录，**王天志**是课题组负责人（副教授），研究方向为：

| 项目 | 详情 |
|------|------|
| **研究方向** | 微纳米气泡技术与应用 |
| **技能** | 项目管理、气泡生成、水处理、技术产业化 |
| **简介** | 
```

### B-L1-0081 (B) — FAIL
**问题**: 王天志现在有哪些任务？
- `stream_error_event`: or_event", "severity": "fail", "expected": "no error event", "actual": "error: cannot access local variable 'final_text' where it is not associated with a value", "context": "SSE 流中出现 error 事件（应用错误传播到客户端）"
- `intent_mismatch`: mismatch", "expect": "search_info", "actual": "data_query"
- `missing_tools`: ng_tools", "missing": ["query_member_tasks"], "note": "tools_any — 任一即可"

**回答预览 (前 200 字)**:
```

```

### B-L2-0082 (B) — FAIL
**问题**: 杜同贺正在进行中的任务有哪些？
- `fake_xml_leaked`: l_leaked", "patterns": ["<function\\s*=[^>]+>"]
- `intent_mismatch`: mismatch", "expect": "data_query", "actual": "search_info"
- `missing_tools`: ng_tools", "missing": ["query_member_tasks"], "note": "tools_any — 任一即可"
- `forbidden_names_appeared`: appeared", "names": ["杜同贺"]

**回答预览 (前 200 字)**:
```
<tool_call>
<function=query_tasks>
<parameter=assignee_name>杜同贺</parameter>
<parameter=status>in_progress</parameter>
</function>
</tool_call>
```

### B-L2-0083 (B) — FAIL
**问题**: 我有什么未完成的任务？
- `fake_xml_leaked`: l_leaked", "patterns": ["<function\\s*=[^>]+>"]
- `intent_mismatch`: mismatch", "expect": "search_info", "actual": "data_query"
- `missing_tools`: ng_tools", "missing": ["query_my_tasks"], "note": "tools_any — 任一即可"
- `forbidden_names_appeared`: appeared", "names": ["测试"]

**回答预览 (前 200 字)**:
```
<tool_call>
<function=query_tasks>
<parameter=assignee_name>测试小助手</parameter>
</function>
</tool_call><tool_call>
<function=query_tasks>
<parameter=assignee_name>测试小助手</parameter>
</function>
</tool_c
```

### B-L2-0084 (B) — FAIL
**问题**: 赵航佳最近的逾期任务有几条？
- `missing_tools`: ng_tools", "missing": ["query_member_tasks"], "note": "tools_any — 任一即可"
- `forbidden_names_appeared`: appeared", "names": ["赵航佳"]

**回答预览 (前 200 字)**:
```
赵航佳目前没有逾期任务。
```

### B-L2-0085 (B) — FAIL
**问题**: 杨慈上一周新增了几个任务？
- `stream_error_event`: or_event", "severity": "fail", "expected": "no error event", "actual": "error: Error code: 429 - {'error': {'code': '429', 'message': 'Too many requests', 'type': 'limitation'}}", "context": "SSE 流中出现 error 事件（应用错误传播到客户端）"
- `stream_error_event`: or_event", "severity": "fail", "expected": "no error event", "actual": "error: Error code: 429 - {'error': {'code': '429', 'message': 'Too many requests', 'type': 'limitation'}}", "context": "SSE 流中出现 error 事件（应用错误传播到客户端）"
- `intent_mismatch`: mismatch", "expect": "search_info", "actual": "data_query"
- `missing_tools`: ng_tools", "missing": ["query_member_tasks"], "note": "tools_any — 任一即可"

**回答预览 (前 200 字)**:
```

```

### B-L2-0086 (B) — FAIL
**问题**: 课题组最近一周谁完成了最多任务？
- `duration_warn`: ion_warn", "duration_ms": 32080
- `intent_mismatch`: mismatch", "expect": "search_info", "actual": "data_query"
- `forbidden_names_appeared`: appeared", "names": ["杜同贺"]

**回答预览 (前 200 字)**:
```
根据任务系统数据，**最近一周（6月26日-7月2日）没有成员完成任务**。

目前所有已完成任务（72个）的截止日期均在7月2日之前，且最近完成的任务截止日期为6月30日（杜同贺：持续完善小气助手）。系统未记录具体完成时间，仅显示任务状态为“done”。

**当前任务概况：**
- 进行中：21个
- 已完成：72个
- 逾期：6个

如需查看特定成员的任务详情或更早时间段的任务完成情况，可进
```

### B-L2-0087 (B) — FAIL
**问题**: 本周有哪些高优先级逾期任务？
- `intent_mismatch`: mismatch", "expect": "search_info", "actual": "data_query"
- `forbidden_names_appeared`: appeared", "names": ["宋洋", "测试"]

**回答预览 (前 200 字)**:
```
工具返回了 6 条逾期任务，其中只有 1 条是高优先级（high）。让我整理一下：

---

**本周高优先级逾期任务：**

| 任务 | 负责人 | 截止日期 | 状态 |
|------|--------|----------|------|
| **准备数学考试** | 张懿 | 2026-06-20 | 进行中 |

---

**其他逾期任务（中等优先级）：**

| 任务 | 负责
```

### B-L2-0096 (B) — FAIL
**问题**: 我们课题组任务完成率是多少？
- `intent_mismatch`: mismatch", "expect": "search_info", "actual": "data_query"
- `missing_tools`: ng_tools", "missing": ["query_tasks", "query_team_stats"], "note": "tools_any — 任一即可"

**回答预览 (前 200 字)**:
```
根据当前任务统计，课题组的任务完成率如下：

**任务完成率：76.6%**（72/94）

**详细分布：**
- **已完成：** 72 项
- **进行中：** 21 项
- **已取消：** 1 项
- **待办：** 0 项
- **已阻塞：** 0 项
- **待审核：** 0 项
- **已逾期：** 6 项

**关键指标：**
- **进行中任务占比：** 22.3%
- **逾
```

### B-L3-0088 (B) — FAIL
**问题**: 课题组成员中谁手上的任务负担最重？
- `intent_mismatch`: mismatch", "expect": "search_info", "actual": "data_query"
- `missing_tools`: ng_tools", "missing": ["query_member_tasks", "query_team_stats"], "note": "tools_any — 任一即可"
- `forbidden_names_appeared`: appeared", "names": ["杜同贺", "赵航佳", "李胜景", "测试"]

**回答预览 (前 200 字)**:
```
根据任务数据统计，课题组成员任务负担情况如下：

**任务负担最重的成员：**

1. **陈天祥** - 进行中任务 **7 个**（最多）
   - 斜生栅藻SEM处理送样、配合空调测试臭氧浓度、看文献、200L新机器壳子定制、测试水样、英语上机考试、编辑招聘启事、文献调研、雾化喷头的选购

2. **李胜景** - 进行中任务 **5 个**
   - 修改论文、集装箱展板、催麦蜂网站视频、
```

### B-L3-0089 (B) — FAIL
**问题**: 我们需要给新生分配几个入门任务，谁手上任务少能指导新人？
- `stream_error_event`: or_event", "severity": "fail", "expected": "no error event", "actual": "error: Error code: 429 - {'error': {'code': '429', 'message': 'Too many requests', 'type': 'limitation'}}", "context": "SSE 流中出现 error 事件（应用错误传播到客户端）"
- `stream_error_event`: or_event", "severity": "fail", "expected": "no error event", "actual": "error: Error code: 429 - {'error': {'code': '429', 'message': 'Too many requests', 'type': 'limitation'}}", "context": "SSE 流中出现 error 事件（应用错误传播到客户端）"
- `missing_tools`: ng_tools", "missing": ["query_member_tasks"], "note": "tools_any — 任一即可"

**回答预览 (前 200 字)**:
```

```

### B-L3-0090 (B) — FAIL
**问题**: 过去一个月谁的任务完成率最高？
- `missing_tools`: ng_tools", "missing": ["query_tasks"], "note": "tools_any — 任一即可"
- `forbidden_names_appeared`: appeared", "names": ["杜同贺", "赵航佳", "杨慈", "贾琦"]

**回答预览 (前 200 字)**:
```
根据任务数据统计，**过去一个月任务完成率最高的成员是赵航佳**。

## 📊 任务完成情况统计

| 成员 | 已完成任务数 | 进行中任务数 | 总任务数 | 完成率 |
|------|-------------|-------------|---------|--------|
| **赵航佳** | 10 | 0 | 10 | **100%** |
| 杜同贺 | 15 | 2 | 17
```

### B-L3-0092 (B) — FAIL
**问题**: 给杜同贺分配一个任务：下周一前完成 PMS 降解实验。
- `intent_mismatch`: mismatch", "expect": "execute_action", "actual": "search_info"
- `forbidden_names_appeared`: appeared", "names": ["杜同贺"]

**回答预览 (前 200 字)**:
```
任务已创建成功！

- **任务标题**：完成 PMS 降解实验
- **负责人**：杜同贺
- **截止日期**：2026-07-06（下周一）
- **任务 ID**：284

已分配给杜同贺，他会收到任务通知。
```

### B-L3-0093 (B) — FAIL
**问题**: 帮我新建任务：整理课题组上半年的会议纪要，截止月底。
- `stream_error_event`: or_event", "severity": "fail", "expected": "no error event", "actual": "error: Error code: 429 - {'error': {'code': '429', 'message': 'Too many requests', 'type': 'limitation'}}", "context": "SSE 流中出现 error 事件（应用错误传播到客户端）"
- `stream_error_event`: or_event", "severity": "fail", "expected": "no error event", "actual": "error: Error code: 429 - {'error': {'code': '429', 'message': 'Too many requests', 'type': 'limitation'}}", "context": "SSE 流中出现 error 事件（应用错误传播到客户端）"

**回答预览 (前 200 字)**:
```

```

### B-L3-0095 (B) — FAIL
**问题**: 我要给赵航佳布置 5 个实验验证任务，分别做 5 组对照。
- `missing_tools`: ng_tools", "missing": ["create_task"], "note": "tools_any — 任一即可"
- `forbidden_names_appeared`: appeared", "names": ["赵航佳"]

**回答预览 (前 200 字)**:
```
我来帮你给赵航佳布置5个实验验证任务。请提供以下信息：

1. **任务标题**：每个任务的具体名称是什么？
2. **任务描述**：每个任务的具体内容和要求？
3. **截止日期**：任务需要在什么时间前完成？
4. **优先级**：任务的重要程度（高/中/低）？

你可以一次性提供所有5个任务的信息，我来帮你批量创建。
```

### B-L3-0097 (B) — FAIL
**问题**: 上周任务完成率下降了，是什么原因？
- `stream_error_event`: or_event", "severity": "fail", "expected": "no error event", "actual": "error: Error code: 429 - {'error': {'code': '429', 'message': 'Too many requests', 'type': 'limitation'}}", "context": "SSE 流中出现 error 事件（应用错误传播到客户端）"
- `stream_error_event`: or_event", "severity": "fail", "expected": "no error event", "actual": "error: Error code: 429 - {'error': {'code': '429', 'message': 'Too many requests', 'type': 'limitation'}}", "context": "SSE 流中出现 error 事件（应用错误传播到客户端）"
- `intent_mismatch`: mismatch", "expect": "search_info", "actual": "data_query"
- `missing_tools`: ng_tools", "missing": ["query_tasks"], "note": "tools_any — 任一即可"

**回答预览 (前 200 字)**:
```

```

### B-L3-0098 (B) — FAIL
**问题**: 按优先级统计本月任务分布。
- `fake_xml_leaked`: l_leaked", "patterns": ["<function\\s*=[^>]+>"]
- `missing_tools`: ng_tools", "missing": ["query_tasks", "query_team_stats"], "note": "tools_any — 任一即可"

**回答预览 (前 200 字)**:
```
我来调用任务查询工具获取本月（2026年7月）的任务分布数据。<tool_call>
<function=query_all_member_tasks>
</function>
</tool_call>
```

### B-L3-0099 (B) — FAIL
**问题**: 预警：哪些任务接近截止日期还没完成？
- `stream_error_event`: or_event", "severity": "fail", "expected": "no error event", "actual": "error: Error code: 429 - {'error': {'code': '429', 'message': 'Too many requests', 'type': 'limitation'}}", "context": "SSE 流中出现 error 事件（应用错误传播到客户端）"
- `stream_error_event`: or_event", "severity": "fail", "expected": "no error event", "actual": "error: Error code: 429 - {'error': {'code': '429', 'message': 'Too many requests', 'type': 'limitation'}}", "context": "SSE 流中出现 error 事件（应用错误传播到客户端）"
- `intent_mismatch`: mismatch", "expect": "search_info", "actual": "data_query"
- `missing_tools`: ng_tools", "missing": ["query_tasks"], "note": "tools_any — 任一即可"

**回答预览 (前 200 字)**:
```

```

### B-L4-0094 (B) — FAIL
**问题**: 紧急！给我创建一个高优先级任务，立刻！
- `stream_error_event`: or_event", "severity": "fail", "expected": "no error event", "actual": "error: Error code: 429 - {'error': {'code': '429', 'message': 'Too many requests', 'type': 'limitation'}}", "context": "SSE 流中出现 error 事件（应用错误传播到客户端）"
- `stream_error_event`: or_event", "severity": "fail", "expected": "no error event", "actual": "error: Error code: 429 - {'error': {'code': '429', 'message': 'Too many requests', 'type': 'limitation'}}", "context": "SSE 流中出现 error 事件（应用错误传播到客户端）"
- `missing_tools`: ng_tools", "missing": ["create_task"], "note": "tools_any — 任一即可"

**回答预览 (前 200 字)**:
```

```

### C-L2-0152 (C) — FAIL
**问题**: 我今天有哪些会议？
- `intent_mismatch`: mismatch", "expect": "search_info", "actual": "data_query"
- `missing_tools`: ng_tools", "missing": ["query_my_meetings"], "note": "tools_any — 任一即可"

**回答预览 (前 200 字)**:
```
今天（2026年7月2日）暂无安排会议。
```

### C-L2-0153 (C) — FAIL
**问题**: 下周的会议安排是什么？
- `fake_xml_leaked`: l_leaked", "patterns": ["<function\\s*=[^>]+>"]
- `intent_mismatch`: mismatch", "expect": "search_info", "actual": "data_query"
- `missing_tools`: ng_tools", "missing": ["query_meetings"], "note": "tools_any — 任一即可"

**回答预览 (前 200 字)**:
```
<tool_call>
<function=query_meetings>
<parameter=date_from>2026-07-06</parameter>
<parameter=date_to>2026-07-12</parameter>
</function>
</tool_call>
```

### C-L2-0154 (C) — FAIL
**问题**: 课题组成员最近一个月的会议次数统计。
- `forbidden_names_appeared`: appeared", "names": ["王天志", "杜同贺", "赵航佳", "宋洋", "贾琦", "李胜景", "测试"]

**回答预览 (前 200 字)**:
```
根据最近一个月（2026年6月2日至7月2日）的会议记录，共统计到 **10 场会议**。以下是各成员参与会议次数的统计：

## 📊 课题组成员会议次数统计（最近一个月）

| 成员 | 参与会议次数 | 主要参与会议 |
|------|------------|-------------|
| **王天志** | 6 次 | 研究方案讨论、实验安排、水产养殖技术、UV臭氧研究等 |
| **
```

### C-L2-0155 (C) — FAIL
**问题**: 6/25 例会讨论了什么内容？
- `fake_xml_leaked`: l_leaked", "patterns": ["<function\\s*=[^>]+>"]
- `intent_mismatch`: mismatch", "expect": "search_info", "actual": "data_query"
- `missing_tools`: ng_tools", "missing": ["query_meeting_detail"], "note": "tools_any — 任一即可"

**回答预览 (前 200 字)**:
```
<tool_call>
<function=web_search>
<parameter=query>微纳米气泡 2026年6月25日 例会 讨论内容</parameter>
</function>
</tool_call>
```

### C-L2-0156 (C) — FAIL
**问题**: 6/27 项目进展会上有哪些决策？
- `fake_xml_leaked`: l_leaked", "patterns": ["<function\\s*=[^>]+>"]
- `missing_tools`: ng_tools", "missing": ["query_meeting_detail"], "note": "tools_any — 任一即可"

**回答预览 (前 200 字)**:
```
<tool_call>
<function=query_meetings>
<parameter=keyword>项目进展</parameter>
<parameter=date_from>2026-06-27</parameter>
<parameter=date_to>2026-06-27</parameter>
</function>
</tool_call><tool_call>
<fun
```

### C-L2-0163 (C) — FAIL
**问题**: 昨天组会的转录文本能调出来吗？
- `intent_mismatch`: mismatch", "expect": "search_info", "actual": "data_query"
- `missing_tools`: ng_tools", "missing": ["query_meeting_detail"], "note": "tools_any — 任一即可"

**回答预览 (前 200 字)**:
```
昨天（2026-07-01）没有查到会议记录。可能组会是在其他日期召开的，或者会议记录尚未录入系统。你可以告诉我更具体的时间范围或会议主题，我再帮你查一下。
```

### C-L3-0157 (C) — FAIL
**问题**: 对比两次组会的关键决策点。
- `fake_xml_leaked`: l_leaked", "patterns": ["<function\\s*=[^>]+>"]
- `intent_mismatch`: mismatch", "expect": "search_info", "actual": "data_query"
- `missing_tools`: ng_tools", "missing": ["query_meeting_detail"], "note": "tools_any — 任一即可"

**回答预览 (前 200 字)**:
```
<tool_call>
<function=query_meetings>
<parameter=keyword>组会</parameter>
</function>
</tool_call>
```

### C-L3-0158 (C) — FAIL
**问题**: 分析上个月组会的趋势：实验进展 vs 文献讨论占比。
- `fake_xml_leaked`: l_leaked", "patterns": ["<function\\s*=[^>]+>"]
- `missing_tools`: ng_tools", "missing": ["query_meeting_detail", "query_team_stats"], "note": "tools_any — 任一即可"

**回答预览 (前 200 字)**:
```
工具调用出现了技术错误。让我再试一次，这次不指定日期范围，只查询最近的会议记录，看看能否获取到数据。

<tool_call>
<function=query_meetings>
<parameter=keyword>组会</parameter>
</function>
</tool_call>
```

### C-L3-0159 (C) — FAIL
**问题**: 帮我写一份昨天组会的纪要。
- `stream_error_event`: or_event", "severity": "fail", "expected": "no error event", "actual": "error: Error code: 429 - {'error': {'code': '429', 'message': 'Too many requests', 'type': 'limitation'}}", "context": "SSE 流中出现 error 事件（应用错误传播到客户端）"
- `stream_error_event`: or_event", "severity": "fail", "expected": "no error event", "actual": "error: Error code: 429 - {'error': {'code': '429', 'message': 'Too many requests', 'type': 'limitation'}}", "context": "SSE 流中出现 error 事件（应用错误传播到客户端）"
- `missing_tools`: ng_tools", "missing": ["generate_meeting_minutes"], "note": "tools_any — 任一即可"

**回答预览 (前 200 字)**:
```

```

### C-L3-0160 (C) — FAIL
**问题**: 把 6/25 例会的会议纪要发给我。
- `stream_error_event`: or_event", "severity": "fail", "expected": "no error event", "actual": "error: cannot access local variable 'final_text' where it is not associated with a value", "context": "SSE 流中出现 error 事件（应用错误传播到客户端）"
- `missing_tools`: ng_tools", "missing": ["query_meeting_detail"], "note": "tools_any — 任一即可"

**回答预览 (前 200 字)**:
```

```

### C-L3-0161 (C) — FAIL
**问题**: 我想了解一下上个月的所有纪要主题。
- `intent_mismatch`: mismatch", "expect": "search_info", "actual": "data_query"
- `forbidden_names_appeared`: appeared", "names": ["杜同贺", "宋洋", "贾琦", "李胜景", "测试"]

**回答预览 (前 200 字)**:
```
上个月（2026年6月）共有 **11 场会议**，以下是各场会议的纪要主题：

| 日期 | 会议标题 | 主要内容摘要 |
|------|----------|--------------|
| 06-30 | **设备功率电费核算方案讨论** | 讨论主要设备功率及电费核算，计算固定运行设备电费（每日152千瓦，约121.6元），总费用估计90天10000元。 |
| 06-28 | **
```

### C-L3-0164 (C) — FAIL
**问题**: 分析 5/30 组会的发言人贡献度。
- `fake_xml_leaked`: l_leaked", "patterns": ["<function\\s*=[^>]+>"]
- `intent_mismatch`: mismatch", "expect": "search_info", "actual": "data_query"
- `missing_tools`: ng_tools", "missing": ["query_meeting_detail"], "note": "tools_any — 任一即可"

**回答预览 (前 200 字)**:
```
<tool_call>
<function=web_search>
<parameter=query>5/30 组会 发言人 贡献度 分析</parameter>
</function>
</tool_call>
```

### C-L3-0165 (C) — FAIL
**问题**: 找出会议中提到'臭氧'的所有段落。
- `fake_xml_leaked`: l_leaked", "patterns": ["<function\\s*=[^>]+>"]
- `missing_tools`: ng_tools", "missing": ["query_meeting_detail", "search_knowledge"], "note": "tools_any — 任一即可"

**回答预览 (前 200 字)**:
```
<tool_call>
<function=query_meetings>
<parameter=keyword>臭氧</parameter>
</function>
</tool_call>
```

### C-L3-0166 (C) — FAIL
**问题**: 昨天的转录里有没有提到会议纪要规范的内容？
- `fake_xml_leaked`: l_leaked", "patterns": ["<function\\s*=[^>]+>"]
- `intent_mismatch`: mismatch", "expect": "search_info", "actual": "data_query"
- `missing_tools`: ng_tools", "missing": ["query_meeting_detail"], "note": "tools_any — 任一即可"

**回答预览 (前 200 字)**:
```
<tool_call>
<function=query_meetings>
<parameter=date_from>2026-06-25</parameter>
<parameter=date_to>2026-07-01</parameter>
<parameter=keyword>纪要</parameter>
</function>
</tool_call>昨天（2026-07-01）没有会议
```

### C-L3-0167 (C) — FAIL
**问题**: 用组会模板帮我快速创建一个会议。
- `missing_tools`: ng_tools", "missing": ["create_meeting"], "note": "tools_any — 任一即可"

**回答预览 (前 200 字)**:
```
我来帮你用组会模板创建一个会议。请提供以下信息：

1. **会议标题**（例如：2026年7月组会）
2. **会议时间**（日期和时间，例如：2026-07-04 14:00）
3. **会议地点**（例如：实验室会议室 / 线上会议）
4. **参会人员**（可选，默认全体成员）
5. **会议议程**（可选，我会用组会模板填充）

如果你只需要一个标准组会，告诉我**标题和时间**就行，其
```

### C-L3-0168 (C) — FAIL
**问题**: 给我新建一对一的会议。
- `stream_error_event`: or_event", "severity": "fail", "expected": "no error event", "actual": "error: Error code: 429 - {'error': {'code': '429', 'message': 'Too many requests', 'type': 'limitation'}}", "context": "SSE 流中出现 error 事件（应用错误传播到客户端）"
- `stream_error_event`: or_event", "severity": "fail", "expected": "no error event", "actual": "error: Error code: 429 - {'error': {'code': '429', 'message': 'Too many requests', 'type': 'limitation'}}", "context": "SSE 流中出现 error 事件（应用错误传播到客户端）"
- `missing_tools`: ng_tools", "missing": ["create_meeting"], "note": "tools_any — 任一即可"

**回答预览 (前 200 字)**:
```

```

### C-L3-0169 (C) — FAIL
**问题**: 我想新建一个立项会，需要哪些信息？
- `missing_tools`: ng_tools", "missing": ["create_meeting"], "note": "tools_any — 任一即可"

**回答预览 (前 200 字)**:
```
创建立项会需要以下信息：

1. **会议标题**（必填）：例如"XX项目立项评审会"
2. **会议时间**（必填）：开始时间、结束时间
3. **会议地点**（选填）：线下会议室或线上链接
4. **参会人员**（选填）：需要邀请的成员
5. **会议议程/摘要**（选填）：会议讨论的主要内容

请提供以上信息，我来帮你创建。
```

### C-L4-0162 (C) — FAIL
**问题**: 上次组会有谁缺席？原因是什么？
- `stream_error_event`: or_event", "severity": "fail", "expected": "no error event", "actual": "error: cannot access local variable 'final_text' where it is not associated with a value", "context": "SSE 流中出现 error 事件（应用错误传播到客户端）"
- `intent_mismatch`: mismatch", "expect": "search_info", "actual": "data_query"
- `missing_tools`: ng_tools", "missing": ["query_meeting_detail"], "note": "tools_any — 任一即可"

**回答预览 (前 200 字)**:
```

```

### D-L1-0221 (D) — FAIL
**问题**: 我们课题组现在有几个进行中的项目？
- `fake_xml_leaked`: l_leaked", "patterns": ["<function\\s*=[^>]+>"]
- `intent_mismatch`: mismatch", "expect": "search_info", "actual": "data_query"
- `missing_tools`: ng_tools", "missing": ["query_projects"], "note": "tools_any — 任一即可"

**回答预览 (前 200 字)**:
```
<tool_call>
<function=query_projects>
<parameter=status>in_progress</parameter>
</function>
</tool_call><tool_call>
<function=query_projects>
<parameter=status>进行中</parameter>
</function>
</tool_call>
```

### D-L2-0222 (D) — FAIL
**问题**: 列出所有基金类项目。
- `fake_xml_leaked`: l_leaked", "patterns": ["<function\\s*=[^>]+>"]
- `missing_tools`: ng_tools", "missing": ["query_projects"], "note": "tools_any — 任一即可"

**回答预览 (前 200 字)**:
```
<tool_call>
<function=query_projects>
<parameter=type>基金</parameter>
</function>
</tool_call><tool_call>
<function=query_projects>
<parameter=project_type>基金</parameter>
</function>
</tool_call>
```

### D-L2-0223 (D) — FAIL
**问题**: 下个月有哪些项目要结题？
- `fake_xml_leaked`: l_leaked", "patterns": ["<function\\s*=[^>]+>"]
- `intent_mismatch`: mismatch", "expect": "search_info", "actual": "data_query"
- `missing_tools`: ng_tools", "missing": ["query_projects"], "note": "tools_any — 任一即可"

**回答预览 (前 200 字)**:
```
<tool_call>
<function=query_projects>
<parameter=date_from>2026-08-01</parameter>
<parameter=date_to>2026-08-31</parameter>
</function>
</tool_call>
```

### D-L2-0224 (D) — FAIL
**问题**: 我负责哪些项目？
- `fake_xml_leaked`: l_leaked", "patterns": ["<function\\s*=[^>]+>"]
- `duration_warn`: ion_warn", "duration_ms": 31327
- `forbidden_names_appeared`: appeared", "names": ["测试"]

**回答预览 (前 200 字)**:
```
<tool_call>
<function=get_project_summary>
<parameter=project_name>微气泡降解抗生素实验研究</parameter>
</function>
</tool_call><tool_call>
<function=query_tasks>
<parameter=assignee_name>测试小助手</parameter>
<param
```

### D-L2-0226 (D) — FAIL
**问题**: 国家自然科学基金面上项目的摘要。
- `duration_warn`: ion_warn", "duration_ms": 38963
- `missing_tools`: ng_tools", "missing": ["query_project_detail"], "note": "tools_any — 任一即可"

**回答预览 (前 200 字)**:
```
国家自然科学基金面上项目摘要（Abstract）是申请书的“门面”，通常要求在 **400字以内**（中文）或 **3000字符以内**（英文），需高度凝练地概括项目的核心内容。以下是摘要的写作结构、要点和注意事项。

---

## 一、摘要的定义与作用

摘要是评审专家阅读的第一段文字，其作用是：
1. **快速传达项目核心**：让评审在30秒内理解你要做什么、为什么做、怎么做、预期成果。
2
```

### D-L2-0234 (D) — FAIL
**问题**: 浙江省重点研发计划的目标是什么？
- `duration_warn`: ion_warn", "duration_ms": 41619
- `missing_tools`: ng_tools", "missing": ["query_project_detail"], "note": "tools_any — 任一即可"

**回答预览 (前 200 字)**:
```
## 浙江省重点研发计划的目标

根据搜索到的信息，浙江省重点研发计划是浙江省科技厅为解决全省国民经济和社会发展中的重大科技需求而设立的省级科技计划。以下是其核心目标和定位：

---

### 一、总体目标

浙江省重点研发计划的核心目标是**聚焦浙江省国民经济和社会发展的重大科技需求**，通过组织关键核心技术攻关，推动科技创新与经济社会发展深度融合，支撑浙江"创新强省"和"人才强省"战略实施。
```

### D-L2-0235 (D) — FAIL
**问题**: 校企合作项目的经费来源？
- `placeholder_text`: der_text", "phrases": ["技术问题"]
- `duration_warn`: ion_warn", "duration_ms": 38315
- `tool_error_with_excuse`: h_excuse", "severity": "warn", "expected": "honest error message", "actual": "LLM 使用借口话术: '技术问题'", "context": "工具 (get_project_summary) 真出错，LLM 用借口话术（应诚实说明）"
- `missing_tools`: ng_tools", "missing": ["query_project_detail"], "note": "tools_any — 任一即可"
- `forbidden_names_appeared`: appeared", "names": ["测试"]

**回答预览 (前 200 字)**:
```
知识库中暂无直接关于"校企合作项目经费来源"的专题资料。不过，结合课题组的项目信息和通用科研管理知识，我可以为您梳理校企合作项目的典型经费来源。

## 校企合作项目的经费来源

校企合作项目的经费通常来自以下几个主要渠道：

### 1. **企业委托研发经费（横向课题）**
- **形式**：企业直接出资委托高校/课题组进行技术开发、产品测试、工艺优化等。
- **特点**：经费灵活，通常按合
```

### D-L2-0236 (D) — FAIL
**问题**: 延期项目有哪些？
- `fake_xml_leaked`: l_leaked", "patterns": ["<function\\s*=[^>]+>"]
- `intent_mismatch`: mismatch", "expect": "search_info", "actual": "data_query"

**回答预览 (前 200 字)**:
```
<tool_call>
<function=query_projects>
<parameter=status>active</parameter>
</function>
</tool_call><tool_call>
<function=query_tasks>
<parameter=status>overdue</parameter>
</function>
</tool_call>
```

### D-L3-0225 (D) — FAIL
**问题**: 近 3 年我们共申请到多少项目？总经费多少？
- `fake_xml_leaked`: l_leaked", "patterns": ["<function\\s*=[^>]+>"]
- `duration_warn`: ion_warn", "duration_ms": 30505
- `intent_mismatch`: mismatch", "expect": "search_info", "actual": "data_query"

**回答预览 (前 200 字)**:
```
<tool_call>
<function=get_project_summary>
</function>
</tool_call>工具返回了6个项目，但大部分项目的 `start_date` 为 null，只有部分项目有起始日期。我需要筛选出近3年（2023年7月2日至2026年7月2日）内开始的项目。

从工具返回的数据中，有起始日期的项目如下：
1.  **饮用水水质提升与安全保障**：s
```

### D-L3-0227 (D) — FAIL
**问题**: 我参与的项目都获得了什么成果？
- `fake_xml_leaked`: l_leaked", "patterns": ["<function\\s*=[^>]+>"]
- `filler_phrases`: _phrases", "count": 1
- `intent_mismatch`: mismatch", "expect": "search_info", "actual": "data_query"
- `missing_tools`: ng_tools", "missing": ["query_project_detail"], "note": "tools_any — 任一即可"
- `forbidden_names_appeared`: appeared", "names": ["测试"]

**回答预览 (前 200 字)**:
```
<tool_call>
<function=get_project>
<parameter=project_id>1</parameter>
</function>
</tool_call>我来帮你查询参与的项目成果。首先需要确认你的具体身份，因为系统中存在多个名为"测试小助手"的管理员账号。让我尝试查询项目信息：

<tool_call>
<function=get_project>
<para
```

### D-L3-0228 (D) — FAIL
**问题**: 我们项目的主要风险点有哪些？
- `placeholder_text`: der_text", "phrases": ["系统故障"]
- `tool_error_with_excuse`: h_excuse", "severity": "warn", "expected": "honest error message", "actual": "LLM 使用借口话术: '系统故障'", "context": "工具 (get_project_summary, get_project_summary, get_project_summary) 真出错，LLM 用借口话术（应诚实说明）"
- `intent_mismatch`: mismatch", "expect": "search_info", "actual": "data_query"
- `missing_tools`: ng_tools", "missing": ["query_project_detail"], "note": "tools_any — 任一即可"
- `forbidden_names_appeared`: appeared", "names": ["测试"]

**回答预览 (前 200 字)**:
```
所有项目查询工具都返回了相同的错误。根据系统规则，我不能以"系统故障"为借口不回答。我将基于已有的项目列表信息，从项目管理角度分析可能存在的风险点。

课题组目前有6个活跃项目，主要风险点可以从以下几个维度分析：

**1. 时间与进度风险**
- **项目2（饮用水水质提升）** 已于 **2026年6月30日** 到期，需确认是否已结题或申请延期。
- **项目1（黑臭水体治理）** 和 **
```

### D-L3-0229 (D) — FAIL
**问题**: 对比两个项目的预算和进度。
- `fake_xml_leaked`: l_leaked", "patterns": ["<function\\s*=[^>]+>"]
- `intent_mismatch`: mismatch", "expect": "search_info", "actual": "data_query"
- `missing_tools`: ng_tools", "missing": ["query_project_detail"], "note": "tools_any — 任一即可"

**回答预览 (前 200 字)**:
```
<tool_call>
<function=query_projects>
</function>
</tool_call><tool_call>
<function=query_projects>
</function>
</tool_call>
```

### D-L3-0230 (D) — FAIL
**问题**: 我打算做一个微气泡降解抗生素的实验，帮我出一份研究计划。
- `fake_xml_leaked`: l_leaked", "patterns": ["<function\\s*=[^>]+>"]
- `missing_tools`: ng_tools", "missing": ["generate_project_plan"], "note": "tools_any — 任一即可"

**回答预览 (前 200 字)**:
```
<tool_call>
<function=search_knowledge>
<parameter=query>微纳米气泡 降解抗生素 实验方案</parameter>
</function>
</tool_call><tool_call>
<function=search_knowledge>
<parameter=query>抗生素降解 微气泡 氧化 实验设计</parameter>
</f
```

### D-L3-0231 (D) — FAIL
**问题**: 我们要申报一个省级重点项目，帮我列 10 个创新点。
- `duration_warn`: ion_warn", "duration_ms": 40175
- `missing_tools`: ng_tools", "missing": ["generate_project_plan"], "note": "tools_any — 任一即可"

**回答预览 (前 200 字)**:
```
基于知识库的深度检索，我为您梳理了微纳米气泡领域的**10个创新点**，涵盖基础理论、生成技术、表征方法、应用拓展及交叉融合，可直接用于省级重点项目申报：

---

## 一、基础理论创新

### 1. **气泡-固体界面相互作用机制**
- **创新点**：揭示微纳米气泡在固体表面（如膜材料、土壤颗粒）的吸附、迁移与脱附行为，建立气泡-固体界面热力学与动力学模型。
- **理论支撑**：气泡
```

### D-L3-0233 (D) — FAIL
**问题**: 这个项目的研究路线不清晰，请重新整理。
- `intent_mismatch`: mismatch", "expect": "search_info", "actual": "execute_action"
- `missing_tools`: ng_tools", "missing": ["generate_project_plan"], "note": "tools_any — 任一即可"

**回答预览 (前 200 字)**:
```
您提到的"这个项目"具体是指哪一个呢？目前课题组有以下 6 个项目：

| # | 项目名称 | 状态 | 研究方向 |
|---|---------|------|---------|
| 1 | 微气泡降解抗生素实验研究 | 活跃 | 微纳米气泡技术/抗生素降解/水处理 |
| 2 | 微气泡降解抗生素研究 | 活跃 | 微纳米气泡用于抗生素降解 |
| 3 | 饮用水水质提升与安全保障 | 
```

### D-L3-0237 (D) — FAIL
**问题**: 按类型和金额对项目进行分类统计。
- `fake_xml_leaked`: l_leaked", "patterns": ["<function\\s*=[^>]+>"]
- `intent_mismatch`: mismatch", "expect": "search_info", "actual": "data_query"
- `missing_tools`: ng_tools", "missing": ["query_projects", "query_team_stats"], "note": "tools_any — 任一即可"

**回答预览 (前 200 字)**:
```
<tool_call>
<function=query_projects>
</function>
</tool_call>
```

### D-L3-0238 (D) — FAIL
**问题**: 项目中可能的伦理/合规问题有哪些？
- `stream_error_event`: or_event", "severity": "fail", "expected": "no error event", "actual": "error: Error code: 429 - {'error': {'code': '429', 'message': 'Too many requests', 'type': 'limitation'}}", "context": "SSE 流中出现 error 事件（应用错误传播到客户端）"
- `stream_error_event`: or_event", "severity": "fail", "expected": "no error event", "actual": "error: Error code: 429 - {'error': {'code': '429', 'message': 'Too many requests', 'type': 'limitation'}}", "context": "SSE 流中出现 error 事件（应用错误传播到客户端）"
- `missing_tools`: ng_tools", "missing": ["query_project_detail"], "note": "tools_any — 任一即可"

**回答预览 (前 200 字)**:
```

```

### D-L4-0232 (D) — FAIL
**问题**: 立项答辩 PPT 怎么设计？
- `stream_error_event`: or_event", "severity": "fail", "expected": "no error event", "actual": "error: cannot access local variable 'final_text' where it is not associated with a value", "context": "SSE 流中出现 error 事件（应用错误传播到客户端）"
- `missing_tools`: ng_tools", "missing": ["generate_project_plan"], "note": "tools_any — 任一即可"

**回答预览 (前 200 字)**:
```

```