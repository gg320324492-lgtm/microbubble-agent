# QA Bench Report — 2026-07-01T23:34:41.643142

**总题数**: 200 | **PASS**: 1 | **WARN**: 1 | **FAIL**: 150 | **ERROR**: 48

**通过率**: 0.5%

## 按分类

| 分类 | PASS | WARN | FAIL | ERROR |
|---|---|---|---|---|
| A | 0 | 0 | 19 | 0 |
| B | 0 | 0 | 19 | 0 |
| C | 0 | 0 | 19 | 0 |
| D | 0 | 0 | 18 | 0 |
| E | 1 | 1 | 17 | 0 |
| F | 0 | 0 | 18 | 0 |
| G | 0 | 0 | 18 | 0 |
| H | 0 | 0 | 19 | 0 |
| K | 0 | 0 | 3 | 20 |
| M | 0 | 0 | 0 | 19 |
| P | 0 | 0 | 0 | 9 |

## 问题分布

| 类型 | 次数 |
|---|---|
| `stream_error_event` | 175 |
| `missing_tools` | 120 |
| `stream_no_done` | 104 |
| `intent_mismatch` | 51 |
| `fake_xml_leaked` | 30 |
| `forbidden_names_appeared` | 11 |
| `duration_warn` | 4 |
| `filler_phrases` | 1 |
| `placeholder_text` | 1 |
| `llm_excuse_no_tool_error` | 1 |

## 7 维评分汇总 (v3.0)

**评分题数**: 152 | **一票否决**: 141


### 维度均分

| 维度 | 权重 | 均分 |
|---|---|---|
| intent | 10% | 0.66 |
| tool | 25% | 0.21 |
| content | 30% | 0.51 |
| rich | 5% | 0.76 |
| defense | 15% | 0.34 |
| perf | 10% | 0.99 |
| consistency | 5% | 1.00 |

### 分级分布

| 等级 | 范围 | 题数 |
|---|---|---|
| A | 90-100 | 1 |
| B | 75-89 | 2 |
| C | 60-74 | 6 |
| D | 40-59 | 2 |
| F | 0-39 | 141 |

## 失败题详情


### A-L1-0001 (A) — FAIL
**问题**: 王天志是干什么的？
- `fake_xml_leaked`: l_leaked", "patterns": ["<function\\s*=[^>]+>"]
- `missing_tools`: ng_tools", "missing": ["query_members"], "note": "tools_any — 任一即可"

**回答预览 (前 200 字)**:
```
<tool_call>
<function=get_member_profile>
<parameter=name>王天志</parameter>
</function>
</tool_call>
```

### A-L1-0002 (A) — FAIL
**问题**: 杜同贺是学生吗？他的研究方向是什么？
- `stream_no_done`: _no_done", "severity": "fail", "expected": "done event", "actual": "no done event in stream", "context": "共 21 个事件，最后一个事件类型: error"
- `stream_error_event`: or_event", "severity": "fail", "expected": "no error event", "actual": "error: cannot access local variable 'final_text' where it is not associated with a value", "context": "SSE 流中出现 error 事件（应用错误传播到客户端）"

**回答预览 (前 200 字)**:
```

```

### A-L2-0003 (A) — FAIL
**问题**: 我们课题组成员里谁在做臭氧氧化相关研究？
- `duration_warn`: ion_warn", "duration_ms": 35157
- `forbidden_names_appeared`: appeared", "names": ["赵航佳"]

**回答预览 (前 200 字)**:
```
根据课题组成员数据库，以下成员的研究方向与**臭氧氧化**直接相关：

## 🔬 核心相关成员

### 1. **赵航佳**（博一）
- **研究方向**：黑臭水体治理
- **技能**：臭氧微纳米气泡、底泥-水界面、污染物去除
- **简介**：围绕微纳米气泡在黑臭水体治理中的应用开展研究，重点关注微纳米气泡与底泥-水界面污染物之间的相互作用机制
- **联系方式**：zhaohangjia@
```

### A-L2-0004 (A) — FAIL
**问题**: 杨慈是在读博士吗？
- `missing_tools`: ng_tools", "missing": ["query_members"], "note": "tools_any — 任一即可"
- `forbidden_names_appeared`: appeared", "names": ["杨慈"]

**回答预览 (前 200 字)**:
```
工具返回显示杨慈的年级是“研三”，即硕士三年级，因此他目前是在读硕士，而不是在读博士。他的研究方向是饮用水安全，主要探索微纳米气泡在饮用水安全保障领域的应用。
```

### A-L2-0005 (A) — FAIL
**问题**: 我们课题组的博士后有哪几位？
- `stream_no_done`: _no_done", "severity": "fail", "expected": "done event", "actual": "no done event in stream", "context": "共 7 个事件，最后一个事件类型: error"
- `stream_error_event`: or_event", "severity": "fail", "expected": "no error event", "actual": "error: cannot access local variable 'final_text' where it is not associated with a value", "context": "SSE 流中出现 error 事件（应用错误传播到客户端）"

**回答预览 (前 200 字)**:
```

```

### A-L2-0006 (A) — FAIL
**问题**: 王天志的导师是谁？
- `fake_xml_leaked`: l_leaked", "patterns": ["<function\\s*=[^>]+>"]
- `filler_phrases`: _phrases", "count": 1
- `missing_tools`: ng_tools", "missing": ["query_members"], "note": "tools_any — 任一即可"
- `forbidden_names_appeared`: appeared", "names": ["王天志"]

**回答预览 (前 200 字)**:
```
我来帮你查询王天志的导师信息。<tool_call>
<function=get_member_profile>
<parameter=name>王天志</parameter>
</function>
</tool_call>
```

### A-L2-0008 (A) — FAIL
**问题**: 赵航佳目前带几个学生？
- `fake_xml_leaked`: l_leaked", "patterns": ["<function\\s*=[^>]+>"]
- `missing_tools`: ng_tools", "missing": ["query_members"], "note": "tools_any — 任一即可"
- `forbidden_names_appeared`: appeared", "names": ["赵航佳"]

**回答预览 (前 200 字)**:
```
<tool_call>
<function=get_member_profile>
<parameter=name>赵航佳</parameter>
</function>
</tool_call>
```

### A-L2-0009 (A) — FAIL
**问题**: 我们课题组现在有多少在读硕士研究生？
- `fake_xml_leaked`: l_leaked", "patterns": ["<function\\s*=[^>]+>"]
- `intent_mismatch`: mismatch", "expect": "search_info", "actual": "data_query"
- `missing_tools`: ng_tools", "missing": ["query_members", "query_team_stats"], "note": "tools_any — 任一即可"

**回答预览 (前 200 字)**:
```
<tool_call>
<function=query_members>
<parameter=grade>硕士</parameter>
</function>
</tool_call>
```

### A-L2-0011 (A) — FAIL
**问题**: 王天志最近一周完成了哪些任务？
- `fake_xml_leaked`: l_leaked", "patterns": ["<function\\s*=[^>]+>"]
- `missing_tools`: ng_tools", "missing": ["query_member_tasks"], "note": "tools_any — 任一即可"
- `forbidden_names_appeared`: appeared", "names": ["王天志"]

**回答预览 (前 200 字)**:
```
<tool_call>
<function=query_tasks>
<parameter=assignee_name>王天志</parameter>
<parameter=status>Done</parameter>
</function>
</tool_call><tool_call>
<function=query_tasks>
<parameter=assignee_name>王天志</
```

### A-L2-0012 (A) — FAIL
**问题**: 王天志手上还有多少个未完成的任务？
- `stream_no_done`: _no_done", "severity": "fail", "expected": "done event", "actual": "no done event in stream", "context": "共 5 个事件，最后一个事件类型: error"
- `stream_error_event`: or_event", "severity": "fail", "expected": "no error event", "actual": "error: Error code: 429 - {'error': {'code': '429', 'message': 'Too many requests', 'type': 'limitation'}}", "context": "SSE 流中出现 error 事件（应用错误传播到客户端）"
- `stream_error_event`: or_event", "severity": "fail", "expected": "no error event", "actual": "error: Error code: 429 - {'error': {'code': '429', 'message': 'Too many requests', 'type': 'limitation'}}", "context": "SSE 流中出现 error 事件（应用错误传播到客户端）"
- `missing_tools`: ng_tools", "missing": ["query_member_tasks"], "note": "tools_any — 任一即可"

**回答预览 (前 200 字)**:
```

```

### A-L2-0016 (A) — FAIL
**问题**: 杜同贺和周之超谁当前任务更多？
- `stream_no_done`: _no_done", "severity": "fail", "expected": "done event", "actual": "no done event in stream", "context": "共 5 个事件，最后一个事件类型: error"
- `stream_error_event`: or_event", "severity": "fail", "expected": "no error event", "actual": "error: Error code: 429 - {'error': {'code': '429', 'message': 'Too many requests', 'type': 'limitation'}}", "context": "SSE 流中出现 error 事件（应用错误传播到客户端）"
- `stream_error_event`: or_event", "severity": "fail", "expected": "no error event", "actual": "error: Error code: 429 - {'error': {'code': '429', 'message': 'Too many requests', 'type': 'limitation'}}", "context": "SSE 流中出现 error 事件（应用错误传播到客户端）"
- `missing_tools`: ng_tools", "missing": ["query_member_tasks"], "note": "tools_any — 任一即可"

**回答预览 (前 200 字)**:
```

```

### A-L2-0017 (A) — FAIL
**问题**: 我们课题组的博士生导师有哪几位？
- `stream_no_done`: _no_done", "severity": "fail", "expected": "done event", "actual": "no done event in stream", "context": "共 8 个事件，最后一个事件类型: error"
- `stream_error_event`: or_event", "severity": "fail", "expected": "no error event", "actual": "error: cannot access local variable 'final_text' where it is not associated with a value", "context": "SSE 流中出现 error 事件（应用错误传播到客户端）"

**回答预览 (前 200 字)**:
```

```

### A-L2-0019 (A) — FAIL
**问题**: 课题组成员中谁的研究方向跟微纳米气泡相关？
- `forbidden_names_appeared`: appeared", "names": ["王天志"]

**回答预览 (前 200 字)**:
```
课题组中有一位成员的研究方向与微纳米气泡直接相关：**王天志**，副教授，课题组负责人。他的研究方向是**微纳米气泡技术与应用**，长期从事该领域的研究与应用开发，技能涵盖项目管理、气泡生成、水处理及技术产业化 [1]。

```json
{
  "type": "member",
  "data": {
    "members": [
      {
        "id": 1,
    
```

### A-L3-0007 (A) — FAIL
**问题**: 杜同贺和赵航佳都在研究什么方向？给我一个对比。
- `stream_no_done`: _no_done", "severity": "fail", "expected": "done event", "actual": "no done event in stream", "context": "共 10 个事件，最后一个事件类型: error"
- `stream_error_event`: or_event", "severity": "fail", "expected": "no error event", "actual": "error: cannot access local variable 'final_text' where it is not associated with a value", "context": "SSE 流中出现 error 事件（应用错误传播到客户端）"
- `missing_tools`: ng_tools", "missing": ["query_members"], "note": "tools_any — 任一即可"

**回答预览 (前 200 字)**:
```

```

### A-L3-0010 (A) — FAIL
**问题**: 列出王天志所在团队的全部成员及其研究方向。
- `forbidden_names_appeared`: appeared", "names": ["王天志", "杜同贺", "赵航佳", "杨慈", "宋洋", "贾琦", "李胜景", "周之超", "测试"]

**回答预览 (前 200 字)**:
```
王天志是课题组负责人，研究方向为**微纳米气泡技术与应用**。以下是课题组全部成员及其研究方向：

## 课题组成员及研究方向

| 姓名 | 年级 | 研究方向 | 技能/专长 |
|------|------|----------|-----------|
| **王天志** | 副教授 | 微纳米气泡技术与应用 | 项目管理、气泡生成、水处理、技术产业化 |
| **赵航佳** | 博一 |
```

### A-L3-0013 (A) — FAIL
**问题**: 杨慈上周三有什么安排？
- `stream_no_done`: _no_done", "severity": "fail", "expected": "done event", "actual": "no done event in stream", "context": "共 5 个事件，最后一个事件类型: error"
- `stream_error_event`: or_event", "severity": "fail", "expected": "no error event", "actual": "error: Error code: 429 - {'error': {'code': '429', 'message': 'Too many requests', 'type': 'limitation'}}", "context": "SSE 流中出现 error 事件（应用错误传播到客户端）"
- `stream_error_event`: or_event", "severity": "fail", "expected": "no error event", "actual": "error: Error code: 429 - {'error': {'code': '429', 'message': 'Too many requests', 'type': 'limitation'}}", "context": "SSE 流中出现 error 事件（应用错误传播到客户端）"
- `missing_tools`: ng_tools", "missing": ["query_member_tasks"], "note": "tools_any — 任一即可"

**回答预览 (前 200 字)**:
```

```

### A-L3-0014 (A) — FAIL
**问题**: 本月逾期未完成的任务都有哪些？谁负责？
- `stream_no_done`: _no_done", "severity": "fail", "expected": "done event", "actual": "no done event in stream", "context": "共 5 个事件，最后一个事件类型: error"
- `stream_error_event`: or_event", "severity": "fail", "expected": "no error event", "actual": "error: Error code: 429 - {'error': {'code': '429', 'message': 'Too many requests', 'type': 'limitation'}}", "context": "SSE 流中出现 error 事件（应用错误传播到客户端）"
- `stream_error_event`: or_event", "severity": "fail", "expected": "no error event", "actual": "error: Error code: 429 - {'error': {'code': '429', 'message': 'Too many requests', 'type': 'limitation'}}", "context": "SSE 流中出现 error 事件（应用错误传播到客户端）"
- `missing_tools`: ng_tools", "missing": ["query_tasks"], "note": "tools_any — 任一即可"

**回答预览 (前 200 字)**:
```

```

### A-L3-0015 (A) — FAIL
**问题**: 下个月王天志有哪些会议要参加？
- `stream_no_done`: _no_done", "severity": "fail", "expected": "done event", "actual": "no done event in stream", "context": "共 7 个事件，最后一个事件类型: error"
- `stream_error_event`: or_event", "severity": "fail", "expected": "no error event", "actual": "error: cannot access local variable 'final_text' where it is not associated with a value", "context": "SSE 流中出现 error 事件（应用错误传播到客户端）"

**回答预览 (前 200 字)**:
```

```

### A-L3-0018 (A) — FAIL
**问题**: 王天志和李松泽的研究方向有什么交叉？
- `forbidden_names_appeared`: appeared", "names": ["王天志", "李胜景", "李松泽"]

**回答预览 (前 200 字)**:
```
[综合阶段] 已获取 query_members 结果，开始整合回答。根据查询结果，课题组成员数据库中**没有找到名为"李松泽"的成员**。以下是王天志的研究方向信息：

---

## 王天志的研究方向

**王天志**是课题组副教授、负责人，研究方向为**微纳米气泡技术与应用**，主要技能包括项目管理、气泡生成、水处理、技术产业化。长期从事微纳米气泡技术研究与应用开发。

---

## 关于
```

### B-L1-0081 (B) — FAIL
**问题**: 王天志现在有哪些任务？
- `stream_no_done`: _no_done", "severity": "fail", "expected": "done event", "actual": "no done event in stream", "context": "共 7 个事件，最后一个事件类型: error"
- `stream_error_event`: or_event", "severity": "fail", "expected": "no error event", "actual": "error: cannot access local variable 'final_text' where it is not associated with a value", "context": "SSE 流中出现 error 事件（应用错误传播到客户端）"
- `missing_tools`: ng_tools", "missing": ["query_member_tasks"], "note": "tools_any — 任一即可"

**回答预览 (前 200 字)**:
```

```

### B-L2-0082 (B) — FAIL
**问题**: 杜同贺正在进行中的任务有哪些？
- `stream_no_done`: _no_done", "severity": "fail", "expected": "done event", "actual": "no done event in stream", "context": "共 5 个事件，最后一个事件类型: error"
- `stream_error_event`: or_event", "severity": "fail", "expected": "no error event", "actual": "error: Error code: 429 - {'error': {'code': '429', 'message': 'Too many requests', 'type': 'limitation'}}", "context": "SSE 流中出现 error 事件（应用错误传播到客户端）"
- `stream_error_event`: or_event", "severity": "fail", "expected": "no error event", "actual": "error: Error code: 429 - {'error': {'code': '429', 'message': 'Too many requests', 'type': 'limitation'}}", "context": "SSE 流中出现 error 事件（应用错误传播到客户端）"
- `intent_mismatch`: mismatch", "expect": "data_query", "actual": "search_info"
- `missing_tools`: ng_tools", "missing": ["query_member_tasks"], "note": "tools_any — 任一即可"

**回答预览 (前 200 字)**:
```

```

### B-L2-0083 (B) — FAIL
**问题**: 我有什么未完成的任务？
- `stream_no_done`: _no_done", "severity": "fail", "expected": "done event", "actual": "no done event in stream", "context": "共 5 个事件，最后一个事件类型: error"
- `stream_error_event`: or_event", "severity": "fail", "expected": "no error event", "actual": "error: Error code: 429 - {'error': {'code': '429', 'message': 'Too many requests', 'type': 'limitation'}}", "context": "SSE 流中出现 error 事件（应用错误传播到客户端）"
- `stream_error_event`: or_event", "severity": "fail", "expected": "no error event", "actual": "error: Error code: 429 - {'error': {'code': '429', 'message': 'Too many requests', 'type': 'limitation'}}", "context": "SSE 流中出现 error 事件（应用错误传播到客户端）"
- `missing_tools`: ng_tools", "missing": ["query_my_tasks"], "note": "tools_any — 任一即可"

**回答预览 (前 200 字)**:
```

```

### B-L2-0084 (B) — FAIL
**问题**: 赵航佳最近的逾期任务有几条？
- `stream_no_done`: _no_done", "severity": "fail", "expected": "done event", "actual": "no done event in stream", "context": "共 5 个事件，最后一个事件类型: error"
- `stream_error_event`: or_event", "severity": "fail", "expected": "no error event", "actual": "error: Error code: 429 - {'error': {'code': '429', 'message': 'Too many requests', 'type': 'limitation'}}", "context": "SSE 流中出现 error 事件（应用错误传播到客户端）"
- `stream_error_event`: or_event", "severity": "fail", "expected": "no error event", "actual": "error: Error code: 429 - {'error': {'code': '429', 'message': 'Too many requests', 'type': 'limitation'}}", "context": "SSE 流中出现 error 事件（应用错误传播到客户端）"
- `missing_tools`: ng_tools", "missing": ["query_member_tasks"], "note": "tools_any — 任一即可"

**回答预览 (前 200 字)**:
```

```

### B-L2-0085 (B) — FAIL
**问题**: 杨慈上一周新增了几个任务？
- `stream_no_done`: _no_done", "severity": "fail", "expected": "done event", "actual": "no done event in stream", "context": "共 5 个事件，最后一个事件类型: error"
- `stream_error_event`: or_event", "severity": "fail", "expected": "no error event", "actual": "error: Error code: 429 - {'error': {'code': '429', 'message': 'Too many requests', 'type': 'limitation'}}", "context": "SSE 流中出现 error 事件（应用错误传播到客户端）"
- `stream_error_event`: or_event", "severity": "fail", "expected": "no error event", "actual": "error: Error code: 429 - {'error': {'code': '429', 'message': 'Too many requests', 'type': 'limitation'}}", "context": "SSE 流中出现 error 事件（应用错误传播到客户端）"
- `missing_tools`: ng_tools", "missing": ["query_member_tasks"], "note": "tools_any — 任一即可"

**回答预览 (前 200 字)**:
```

```

### B-L2-0086 (B) — FAIL
**问题**: 课题组最近一周谁完成了最多任务？
- `stream_no_done`: _no_done", "severity": "fail", "expected": "done event", "actual": "no done event in stream", "context": "共 5 个事件，最后一个事件类型: error"
- `stream_error_event`: or_event", "severity": "fail", "expected": "no error event", "actual": "error: Error code: 429 - {'error': {'code': '429', 'message': 'Too many requests', 'type': 'limitation'}}", "context": "SSE 流中出现 error 事件（应用错误传播到客户端）"
- `stream_error_event`: or_event", "severity": "fail", "expected": "no error event", "actual": "error: Error code: 429 - {'error': {'code': '429', 'message': 'Too many requests', 'type': 'limitation'}}", "context": "SSE 流中出现 error 事件（应用错误传播到客户端）"
- `intent_mismatch`: mismatch", "expect": "search_info", "actual": "data_query"
- `missing_tools`: ng_tools", "missing": ["query_tasks", "query_team_stats"], "note": "tools_any — 任一即可"

**回答预览 (前 200 字)**:
```

```

### B-L2-0087 (B) — FAIL
**问题**: 本周有哪些高优先级逾期任务？
- `stream_no_done`: _no_done", "severity": "fail", "expected": "done event", "actual": "no done event in stream", "context": "共 5 个事件，最后一个事件类型: error"
- `stream_error_event`: or_event", "severity": "fail", "expected": "no error event", "actual": "error: Error code: 429 - {'error': {'code': '429', 'message': 'Too many requests', 'type': 'limitation'}}", "context": "SSE 流中出现 error 事件（应用错误传播到客户端）"
- `stream_error_event`: or_event", "severity": "fail", "expected": "no error event", "actual": "error: Error code: 429 - {'error': {'code': '429', 'message': 'Too many requests', 'type': 'limitation'}}", "context": "SSE 流中出现 error 事件（应用错误传播到客户端）"
- `intent_mismatch`: mismatch", "expect": "search_info", "actual": "data_query"
- `missing_tools`: ng_tools", "missing": ["query_tasks"], "note": "tools_any — 任一即可"

**回答预览 (前 200 字)**:
```

```

### B-L2-0096 (B) — FAIL
**问题**: 我们课题组任务完成率是多少？
- `missing_tools`: ng_tools", "missing": ["query_tasks", "query_team_stats"], "note": "tools_any — 任一即可"

**回答预览 (前 200 字)**:
```
根据最新的任务统计数据，课题组的任务完成情况如下：

## 📊 课题组任务完成率

**总任务数**：93 项  
**已完成**：72 项  
**进行中**：20 项  
**已取消**：1 项  
**逾期**：6 项  

### 📈 完成率计算
- **任务完成率** = (已完成任务数 / 总任务数) × 100%  
- **计算结果** = (72 / 93) × 100% ≈ *
```

### B-L3-0088 (B) — FAIL
**问题**: 课题组成员中谁手上的任务负担最重？
- `stream_no_done`: _no_done", "severity": "fail", "expected": "done event", "actual": "no done event in stream", "context": "共 5 个事件，最后一个事件类型: error"
- `stream_error_event`: or_event", "severity": "fail", "expected": "no error event", "actual": "error: Error code: 429 - {'error': {'code': '429', 'message': 'Too many requests', 'type': 'limitation'}}", "context": "SSE 流中出现 error 事件（应用错误传播到客户端）"
- `stream_error_event`: or_event", "severity": "fail", "expected": "no error event", "actual": "error: Error code: 429 - {'error': {'code': '429', 'message': 'Too many requests', 'type': 'limitation'}}", "context": "SSE 流中出现 error 事件（应用错误传播到客户端）"
- `missing_tools`: ng_tools", "missing": ["query_member_tasks", "query_team_stats"], "note": "tools_any — 任一即可"

**回答预览 (前 200 字)**:
```

```

### B-L3-0089 (B) — FAIL
**问题**: 我们需要给新生分配几个入门任务，谁手上任务少能指导新人？
- `fake_xml_leaked`: l_leaked", "patterns": ["<function\\s*=[^>]+>"]
- `missing_tools`: ng_tools", "missing": ["query_member_tasks"], "note": "tools_any — 任一即可"

**回答预览 (前 200 字)**:
```
<tool_call>
<function=query_all_member_tasks>
</function>
</tool_call>
```

### B-L3-0090 (B) — FAIL
**问题**: 过去一个月谁的任务完成率最高？
- `stream_no_done`: _no_done", "severity": "fail", "expected": "done event", "actual": "no done event in stream", "context": "共 5 个事件，最后一个事件类型: error"
- `stream_error_event`: or_event", "severity": "fail", "expected": "no error event", "actual": "error: Error code: 429 - {'error': {'code': '429', 'message': 'Too many requests', 'type': 'limitation'}}", "context": "SSE 流中出现 error 事件（应用错误传播到客户端）"
- `stream_error_event`: or_event", "severity": "fail", "expected": "no error event", "actual": "error: Error code: 429 - {'error': {'code': '429', 'message': 'Too many requests', 'type': 'limitation'}}", "context": "SSE 流中出现 error 事件（应用错误传播到客户端）"
- `intent_mismatch`: mismatch", "expect": "search_info", "actual": "data_query"
- `missing_tools`: ng_tools", "missing": ["query_tasks"], "note": "tools_any — 任一即可"

**回答预览 (前 200 字)**:
```

```

### B-L3-0091 (B) — FAIL
**问题**: 帮我创建一个任务：明天下午 3 点跟王天志讨论论文。
- `stream_no_done`: _no_done", "severity": "fail", "expected": "done event", "actual": "no done event in stream", "context": "共 7 个事件，最后一个事件类型: error"
- `stream_error_event`: or_event", "severity": "fail", "expected": "no error event", "actual": "error: Error code: 429 - {'error': {'code': '429', 'message': 'Too many requests', 'type': 'limitation'}}", "context": "SSE 流中出现 error 事件（应用错误传播到客户端）"
- `stream_error_event`: or_event", "severity": "fail", "expected": "no error event", "actual": "error: Error code: 429 - {'error': {'code': '429', 'message': 'Too many requests', 'type': 'limitation'}}", "context": "SSE 流中出现 error 事件（应用错误传播到客户端）"
- `intent_mismatch`: mismatch", "expect": "execute_action", "actual": "search_info"

**回答预览 (前 200 字)**:
```

```

### B-L3-0092 (B) — FAIL
**问题**: 给杜同贺分配一个任务：下周一前完成 PMS 降解实验。
- `stream_no_done`: _no_done", "severity": "fail", "expected": "done event", "actual": "no done event in stream", "context": "共 7 个事件，最后一个事件类型: error"
- `stream_error_event`: or_event", "severity": "fail", "expected": "no error event", "actual": "error: Error code: 429 - {'error': {'code': '429', 'message': 'Too many requests', 'type': 'limitation'}}", "context": "SSE 流中出现 error 事件（应用错误传播到客户端）"
- `stream_error_event`: or_event", "severity": "fail", "expected": "no error event", "actual": "error: Error code: 429 - {'error': {'code': '429', 'message': 'Too many requests', 'type': 'limitation'}}", "context": "SSE 流中出现 error 事件（应用错误传播到客户端）"
- `intent_mismatch`: mismatch", "expect": "execute_action", "actual": "search_info"

**回答预览 (前 200 字)**:
```

```

### B-L3-0093 (B) — FAIL
**问题**: 帮我新建任务：整理课题组上半年的会议纪要，截止月底。
- `stream_no_done`: _no_done", "severity": "fail", "expected": "done event", "actual": "no done event in stream", "context": "共 7 个事件，最后一个事件类型: error"
- `stream_error_event`: or_event", "severity": "fail", "expected": "no error event", "actual": "error: Error code: 429 - {'error': {'code': '429', 'message': 'Too many requests', 'type': 'limitation'}}", "context": "SSE 流中出现 error 事件（应用错误传播到客户端）"
- `stream_error_event`: or_event", "severity": "fail", "expected": "no error event", "actual": "error: Error code: 429 - {'error': {'code': '429', 'message': 'Too many requests', 'type': 'limitation'}}", "context": "SSE 流中出现 error 事件（应用错误传播到客户端）"
- `intent_mismatch`: mismatch", "expect": "execute_action", "actual": "search_info"

**回答预览 (前 200 字)**:
```

```

### B-L3-0095 (B) — FAIL
**问题**: 我要给赵航佳布置 5 个实验验证任务，分别做 5 组对照。
- `intent_mismatch`: mismatch", "expect": "execute_action", "actual": "search_info"
- `missing_tools`: ng_tools", "missing": ["create_task"], "note": "tools_any — 任一即可"
- `forbidden_names_appeared`: appeared", "names": ["赵航佳"]

**回答预览 (前 200 字)**:
```
赵航佳是课题组成员，博一学生，研究方向是黑臭水体治理，技能包括臭氧微纳米气泡、底泥-水界面、污染物去除。现在用户要给他布置5个实验验证任务，分别做5组对照。我需要询问具体的任务内容，比如每个实验验证什么，对照组的设置等。用户可能希望我直接创建任务，但任务标题和描述需要明确。我可以先询问用户这5个实验验证任务的具体内容，或者让用户给出任务列表。但根据用户当前的表述，可能希望我直接创建5个任务，但内容
```

### B-L3-0097 (B) — FAIL
**问题**: 上周任务完成率下降了，是什么原因？
- `stream_no_done`: _no_done", "severity": "fail", "expected": "done event", "actual": "no done event in stream", "context": "共 5 个事件，最后一个事件类型: error"
- `stream_error_event`: or_event", "severity": "fail", "expected": "no error event", "actual": "error: Error code: 429 - {'error': {'code': '429', 'message': 'Too many requests', 'type': 'limitation'}}", "context": "SSE 流中出现 error 事件（应用错误传播到客户端）"
- `stream_error_event`: or_event", "severity": "fail", "expected": "no error event", "actual": "error: Error code: 429 - {'error': {'code': '429', 'message': 'Too many requests', 'type': 'limitation'}}", "context": "SSE 流中出现 error 事件（应用错误传播到客户端）"
- `intent_mismatch`: mismatch", "expect": "search_info", "actual": "data_query"
- `missing_tools`: ng_tools", "missing": ["query_tasks"], "note": "tools_any — 任一即可"

**回答预览 (前 200 字)**:
```

```

### B-L3-0098 (B) — FAIL
**问题**: 按优先级统计本月任务分布。
- `stream_no_done`: _no_done", "severity": "fail", "expected": "done event", "actual": "no done event in stream", "context": "共 7 个事件，最后一个事件类型: error"
- `stream_error_event`: or_event", "severity": "fail", "expected": "no error event", "actual": "error: Error code: 429 - {'error': {'code': '429', 'message': 'Too many requests', 'type': 'limitation'}}", "context": "SSE 流中出现 error 事件（应用错误传播到客户端）"
- `stream_error_event`: or_event", "severity": "fail", "expected": "no error event", "actual": "error: Error code: 429 - {'error': {'code': '429', 'message': 'Too many requests', 'type': 'limitation'}}", "context": "SSE 流中出现 error 事件（应用错误传播到客户端）"
- `intent_mismatch`: mismatch", "expect": "search_info", "actual": "data_query"
- `missing_tools`: ng_tools", "missing": ["query_tasks", "query_team_stats"], "note": "tools_any — 任一即可"

**回答预览 (前 200 字)**:
```

```

### B-L3-0099 (B) — FAIL
**问题**: 预警：哪些任务接近截止日期还没完成？
- `stream_no_done`: _no_done", "severity": "fail", "expected": "done event", "actual": "no done event in stream", "context": "共 5 个事件，最后一个事件类型: error"
- `stream_error_event`: or_event", "severity": "fail", "expected": "no error event", "actual": "error: Error code: 429 - {'error': {'code': '429', 'message': 'Too many requests', 'type': 'limitation'}}", "context": "SSE 流中出现 error 事件（应用错误传播到客户端）"
- `stream_error_event`: or_event", "severity": "fail", "expected": "no error event", "actual": "error: Error code: 429 - {'error': {'code': '429', 'message': 'Too many requests', 'type': 'limitation'}}", "context": "SSE 流中出现 error 事件（应用错误传播到客户端）"
- `intent_mismatch`: mismatch", "expect": "search_info", "actual": "data_query"
- `missing_tools`: ng_tools", "missing": ["query_tasks"], "note": "tools_any — 任一即可"

**回答预览 (前 200 字)**:
```

```

### B-L4-0094 (B) — FAIL
**问题**: 紧急！给我创建一个高优先级任务，立刻！
- `stream_no_done`: _no_done", "severity": "fail", "expected": "done event", "actual": "no done event in stream", "context": "共 5 个事件，最后一个事件类型: error"
- `stream_error_event`: or_event", "severity": "fail", "expected": "no error event", "actual": "error: Error code: 429 - {'error': {'code': '429', 'message': 'Too many requests', 'type': 'limitation'}}", "context": "SSE 流中出现 error 事件（应用错误传播到客户端）"
- `stream_error_event`: or_event", "severity": "fail", "expected": "no error event", "actual": "error: Error code: 429 - {'error': {'code': '429', 'message': 'Too many requests', 'type': 'limitation'}}", "context": "SSE 流中出现 error 事件（应用错误传播到客户端）"
- `intent_mismatch`: mismatch", "expect": "execute_action", "actual": "search_info"
- `missing_tools`: ng_tools", "missing": ["create_task"], "note": "tools_any — 任一即可"

**回答预览 (前 200 字)**:
```

```

### C-L1-0151 (C) — FAIL
**问题**: 我们课题组最近的会议有哪些？
- `stream_no_done`: _no_done", "severity": "fail", "expected": "done event", "actual": "no done event in stream", "context": "共 5 个事件，最后一个事件类型: error"
- `stream_error_event`: or_event", "severity": "fail", "expected": "no error event", "actual": "error: Error code: 429 - {'error': {'code': '429', 'message': 'Too many requests', 'type': 'limitation'}}", "context": "SSE 流中出现 error 事件（应用错误传播到客户端）"
- `stream_error_event`: or_event", "severity": "fail", "expected": "no error event", "actual": "error: Error code: 429 - {'error': {'code': '429', 'message': 'Too many requests', 'type': 'limitation'}}", "context": "SSE 流中出现 error 事件（应用错误传播到客户端）"
- `missing_tools`: ng_tools", "missing": ["query_meetings"], "note": "tools_any — 任一即可"

**回答预览 (前 200 字)**:
```

```

### C-L2-0152 (C) — FAIL
**问题**: 我今天有哪些会议？
- `stream_no_done`: _no_done", "severity": "fail", "expected": "done event", "actual": "no done event in stream", "context": "共 5 个事件，最后一个事件类型: error"
- `stream_error_event`: or_event", "severity": "fail", "expected": "no error event", "actual": "error: Error code: 429 - {'error': {'code': '429', 'message': 'Too many requests', 'type': 'limitation'}}", "context": "SSE 流中出现 error 事件（应用错误传播到客户端）"
- `stream_error_event`: or_event", "severity": "fail", "expected": "no error event", "actual": "error: Error code: 429 - {'error': {'code': '429', 'message': 'Too many requests', 'type': 'limitation'}}", "context": "SSE 流中出现 error 事件（应用错误传播到客户端）"
- `missing_tools`: ng_tools", "missing": ["query_my_meetings"], "note": "tools_any — 任一即可"

**回答预览 (前 200 字)**:
```

```

### C-L2-0153 (C) — FAIL
**问题**: 下周的会议安排是什么？
- `stream_no_done`: _no_done", "severity": "fail", "expected": "done event", "actual": "no done event in stream", "context": "共 5 个事件，最后一个事件类型: error"
- `stream_error_event`: or_event", "severity": "fail", "expected": "no error event", "actual": "error: Error code: 429 - {'error': {'code': '429', 'message': 'Too many requests', 'type': 'limitation'}}", "context": "SSE 流中出现 error 事件（应用错误传播到客户端）"
- `stream_error_event`: or_event", "severity": "fail", "expected": "no error event", "actual": "error: Error code: 429 - {'error': {'code': '429', 'message': 'Too many requests', 'type': 'limitation'}}", "context": "SSE 流中出现 error 事件（应用错误传播到客户端）"
- `intent_mismatch`: mismatch", "expect": "search_info", "actual": "data_query"
- `missing_tools`: ng_tools", "missing": ["query_meetings"], "note": "tools_any — 任一即可"

**回答预览 (前 200 字)**:
```

```

### C-L2-0154 (C) — FAIL
**问题**: 课题组成员最近一个月的会议次数统计。
- `fake_xml_leaked`: l_leaked", "patterns": ["<function\\s*=[^>]+>"]
- `missing_tools`: ng_tools", "missing": ["query_meetings", "query_team_stats"], "note": "tools_any — 任一即可"

**回答预览 (前 200 字)**:
```
我来查询课题组最近一个月的会议数据，统计各成员的参会情况。

```python
# 查询最近一个月的会议（2026-06-01 至 2026-07-01）
query_meetings(date_from="2026-06-01", date_to="2026-07-01")
```<tool_call>
<function=query_meetings>
<parameter=date_fro
```

### C-L2-0155 (C) — FAIL
**问题**: 6/25 例会讨论了什么内容？
- `stream_no_done`: _no_done", "severity": "fail", "expected": "done event", "actual": "no done event in stream", "context": "共 5 个事件，最后一个事件类型: error"
- `stream_error_event`: or_event", "severity": "fail", "expected": "no error event", "actual": "error: Error code: 429 - {'error': {'code': '429', 'message': 'Too many requests', 'type': 'limitation'}}", "context": "SSE 流中出现 error 事件（应用错误传播到客户端）"
- `stream_error_event`: or_event", "severity": "fail", "expected": "no error event", "actual": "error: Error code: 429 - {'error': {'code': '429', 'message': 'Too many requests', 'type': 'limitation'}}", "context": "SSE 流中出现 error 事件（应用错误传播到客户端）"
- `missing_tools`: ng_tools", "missing": ["query_meeting_detail"], "note": "tools_any — 任一即可"

**回答预览 (前 200 字)**:
```

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
- `stream_no_done`: _no_done", "severity": "fail", "expected": "done event", "actual": "no done event in stream", "context": "共 5 个事件，最后一个事件类型: error"
- `stream_error_event`: or_event", "severity": "fail", "expected": "no error event", "actual": "error: Error code: 429 - {'error': {'code': '429', 'message': 'Too many requests', 'type': 'limitation'}}", "context": "SSE 流中出现 error 事件（应用错误传播到客户端）"
- `stream_error_event`: or_event", "severity": "fail", "expected": "no error event", "actual": "error: Error code: 429 - {'error': {'code': '429', 'message': 'Too many requests', 'type': 'limitation'}}", "context": "SSE 流中出现 error 事件（应用错误传播到客户端）"
- `missing_tools`: ng_tools", "missing": ["query_meeting_detail"], "note": "tools_any — 任一即可"

**回答预览 (前 200 字)**:
```

```

### C-L3-0157 (C) — FAIL
**问题**: 对比两次组会的关键决策点。
- `stream_no_done`: _no_done", "severity": "fail", "expected": "done event", "actual": "no done event in stream", "context": "共 5 个事件，最后一个事件类型: error"
- `stream_error_event`: or_event", "severity": "fail", "expected": "no error event", "actual": "error: Error code: 429 - {'error': {'code': '429', 'message': 'Too many requests', 'type': 'limitation'}}", "context": "SSE 流中出现 error 事件（应用错误传播到客户端）"
- `stream_error_event`: or_event", "severity": "fail", "expected": "no error event", "actual": "error: Error code: 429 - {'error': {'code': '429', 'message': 'Too many requests', 'type': 'limitation'}}", "context": "SSE 流中出现 error 事件（应用错误传播到客户端）"
- `missing_tools`: ng_tools", "missing": ["query_meeting_detail"], "note": "tools_any — 任一即可"

**回答预览 (前 200 字)**:
```

```

### C-L3-0158 (C) — FAIL
**问题**: 分析上个月组会的趋势：实验进展 vs 文献讨论占比。
- `stream_no_done`: _no_done", "severity": "fail", "expected": "done event", "actual": "no done event in stream", "context": "共 5 个事件，最后一个事件类型: error"
- `stream_error_event`: or_event", "severity": "fail", "expected": "no error event", "actual": "error: Error code: 429 - {'error': {'code': '429', 'message': 'Too many requests', 'type': 'limitation'}}", "context": "SSE 流中出现 error 事件（应用错误传播到客户端）"
- `stream_error_event`: or_event", "severity": "fail", "expected": "no error event", "actual": "error: Error code: 429 - {'error': {'code': '429', 'message': 'Too many requests', 'type': 'limitation'}}", "context": "SSE 流中出现 error 事件（应用错误传播到客户端）"
- `missing_tools`: ng_tools", "missing": ["query_meeting_detail", "query_team_stats"], "note": "tools_any — 任一即可"

**回答预览 (前 200 字)**:
```

```

### C-L3-0159 (C) — FAIL
**问题**: 帮我写一份昨天组会的纪要。
- `fake_xml_leaked`: l_leaked", "patterns": ["<function\\s*=[^>]+>"]
- `intent_mismatch`: mismatch", "expect": "execute_action", "actual": "search_info"
- `missing_tools`: ng_tools", "missing": ["generate_meeting_minutes"], "note": "tools_any — 任一即可"

**回答预览 (前 200 字)**:
```
<tool_call>
<function=query_meetings>
<parameter=keyword>组会</parameter>
<parameter=date_from>2026-06-30</parameter>
<parameter=date_to>2026-06-30</parameter>
</function>
</tool_call>
```

### C-L3-0160 (C) — FAIL
**问题**: 把 6/25 例会的会议纪要发给我。
- `fake_xml_leaked`: l_leaked", "patterns": ["<function\\s*=[^>]+>"]
- `missing_tools`: ng_tools", "missing": ["query_meeting_detail"], "note": "tools_any — 任一即可"

**回答预览 (前 200 字)**:
```
<tool_call>
<function=query_meetings>
<parameter=date_from>2025-06-25</parameter>
<parameter=date_to>2025-06-25</parameter>
</function>
</tool_call>
```

### C-L3-0161 (C) — FAIL
**问题**: 我想了解一下上个月的所有纪要主题。
- `fake_xml_leaked`: l_leaked", "patterns": ["<function\\s*=[^>]+>"]
- `stream_no_done`: _no_done", "severity": "fail", "expected": "done event", "actual": "no done event in stream", "context": "共 20 个事件，最后一个事件类型: error"
- `stream_error_event`: or_event", "severity": "fail", "expected": "no error event", "actual": "error: Error code: 429 - {'error': {'code': '429', 'message': 'Too many requests', 'type': 'limitation'}}", "context": "SSE 流中出现 error 事件（应用错误传播到客户端）"
- `stream_error_event`: or_event", "severity": "fail", "expected": "no error event", "actual": "error: Error code: 429 - {'error': {'code': '429', 'message': 'Too many requests', 'type': 'limitation'}}", "context": "SSE 流中出现 error 事件（应用错误传播到客户端）"
- `intent_mismatch`: mismatch", "expect": "search_info", "actual": "data_query"
- `missing_tools`: ng_tools", "missing": ["query_meetings"], "note": "tools_any — 任一即可"

**回答预览 (前 200 字)**:
```
<tool_call>
<function=query_meetings>
<parameter=date_from>2026-06-01</parameter>
<parameter=date_to>2026-06-30</parameter>
</function>
</tool_call>
```

### C-L3-0164 (C) — FAIL
**问题**: 分析 5/30 组会的发言人贡献度。
- `stream_no_done`: _no_done", "severity": "fail", "expected": "done event", "actual": "no done event in stream", "context": "共 10 个事件，最后一个事件类型: error"
- `stream_error_event`: or_event", "severity": "fail", "expected": "no error event", "actual": "error: cannot access local variable 'final_text' where it is not associated with a value", "context": "SSE 流中出现 error 事件（应用错误传播到客户端）"
- `missing_tools`: ng_tools", "missing": ["query_meeting_detail"], "note": "tools_any — 任一即可"

**回答预览 (前 200 字)**:
```

```

### C-L3-0165 (C) — FAIL
**问题**: 找出会议中提到'臭氧'的所有段落。
- `stream_no_done`: _no_done", "severity": "fail", "expected": "done event", "actual": "no done event in stream", "context": "共 13 个事件，最后一个事件类型: error"
- `stream_error_event`: or_event", "severity": "fail", "expected": "no error event", "actual": "error: Error code: 429 - {'error': {'code': '429', 'message': 'Too many requests', 'type': 'limitation'}}", "context": "SSE 流中出现 error 事件（应用错误传播到客户端）"
- `stream_error_event`: or_event", "severity": "fail", "expected": "no error event", "actual": "error: Error code: 429 - {'error': {'code': '429', 'message': 'Too many requests', 'type': 'limitation'}}", "context": "SSE 流中出现 error 事件（应用错误传播到客户端）"
- `missing_tools`: ng_tools", "missing": ["query_meeting_detail", "search_knowledge"], "note": "tools_any — 任一即可"

**回答预览 (前 200 字)**:
```
我来搜索会议中提到"臭氧"的所有段落。
```

### C-L3-0166 (C) — FAIL
**问题**: 昨天的转录里有没有提到会议纪要规范的内容？
- `fake_xml_leaked`: l_leaked", "patterns": ["<function\\s*=[^>]+>"]
- `stream_no_done`: _no_done", "severity": "fail", "expected": "done event", "actual": "no done event in stream", "context": "共 23 个事件，最后一个事件类型: error"
- `stream_error_event`: or_event", "severity": "fail", "expected": "no error event", "actual": "error: Error code: 429 - {'error': {'code': '429', 'message': 'Too many requests', 'type': 'limitation'}}", "context": "SSE 流中出现 error 事件（应用错误传播到客户端）"
- `stream_error_event`: or_event", "severity": "fail", "expected": "no error event", "actual": "error: Error code: 429 - {'error': {'code': '429', 'message': 'Too many requests', 'type': 'limitation'}}", "context": "SSE 流中出现 error 事件（应用错误传播到客户端）"
- `missing_tools`: ng_tools", "missing": ["query_meeting_detail"], "note": "tools_any — 任一即可"

**回答预览 (前 200 字)**:
```
<tool_call>
<function=query_meetings>
<parameter=keyword>转录</parameter>
<parameter=date_from>2026-06-30</parameter>
<parameter=date_to>2026-06-30</parameter>
</function>
</tool_call>
```

### C-L3-0167 (C) — FAIL
**问题**: 用组会模板帮我快速创建一个会议。
- `stream_no_done`: _no_done", "severity": "fail", "expected": "done event", "actual": "no done event in stream", "context": "共 5 个事件，最后一个事件类型: error"
- `stream_error_event`: or_event", "severity": "fail", "expected": "no error event", "actual": "error: Error code: 429 - {'error': {'code': '429', 'message': 'Too many requests', 'type': 'limitation'}}", "context": "SSE 流中出现 error 事件（应用错误传播到客户端）"
- `stream_error_event`: or_event", "severity": "fail", "expected": "no error event", "actual": "error: Error code: 429 - {'error': {'code': '429', 'message': 'Too many requests', 'type': 'limitation'}}", "context": "SSE 流中出现 error 事件（应用错误传播到客户端）"
- `intent_mismatch`: mismatch", "expect": "execute_action", "actual": "search_info"
- `missing_tools`: ng_tools", "missing": ["create_meeting"], "note": "tools_any — 任一即可"

**回答预览 (前 200 字)**:
```

```

### C-L3-0168 (C) — FAIL
**问题**: 给我新建一对一的会议。
- `stream_no_done`: _no_done", "severity": "fail", "expected": "done event", "actual": "no done event in stream", "context": "共 56 个事件，最后一个事件类型: error"
- `stream_error_event`: or_event", "severity": "fail", "expected": "no error event", "actual": "error: Error code: 429 - {'error': {'code': '429', 'message': 'Too many requests', 'type': 'limitation'}}", "context": "SSE 流中出现 error 事件（应用错误传播到客户端）"
- `stream_error_event`: or_event", "severity": "fail", "expected": "no error event", "actual": "error: Error code: 429 - {'error': {'code': '429', 'message': 'Too many requests', 'type': 'limitation'}}", "context": "SSE 流中出现 error 事件（应用错误传播到客户端）"
- `intent_mismatch`: mismatch", "expect": "execute_action", "actual": "search_info"
- `missing_tools`: ng_tools", "missing": ["create_meeting"], "note": "tools_any — 任一即可"

**回答预览 (前 200 字)**:
```
我需要先了解您想创建会议的具体信息。请问：

1. **会议主题**是什么？（例如：项目进度讨论、论文指导、实验方案评审等）
2. **参会人员**有哪些？（除了您之外，还需要邀请谁？）
3. **建议时间**是？（请提供具体的日期和时间段，如：2026-07-02 14:00-15:00）
4. **会议时长**预计多久？（例如：30分钟、1小时）
5. **会议地点**是？（线上会议平台链接，
```

### C-L3-0169 (C) — FAIL
**问题**: 我想新建一个立项会，需要哪些信息？
- `placeholder_text`: der_text", "phrases": ["技术问题"]
- `llm_excuse_no_tool_error`: ol_error", "severity": "fail", "expected": "no excuse when tool succeeded", "actual": "LLM 编造借口: '技术问题'", "context": "工具调用成功但 LLM 仍借口系统故障（典型 LLM hallucinate）"
- `intent_mismatch`: mismatch", "expect": "execute_action", "actual": "search_info"
- `missing_tools`: ng_tools", "missing": ["create_meeting"], "note": "tools_any — 任一即可"

**回答预览 (前 200 字)**:
```
要新建一个立项会，通常需要准备以下信息：

---

## 📋 立项会基本信息

### 1. 会议基本信息
- **会议标题**：例如"XX项目立项评审会"
- **会议时间**：具体日期和时间段
- **会议地点**：线下会议室或线上会议链接
- **主持人**：通常为课题组负责人或项目发起人

### 2. 项目信息
- **项目名称**：清晰、规范的项目全称
- **项目来源**：如国家自
```

### C-L4-0162 (C) — FAIL
**问题**: 上次组会有谁缺席？原因是什么？
- `stream_no_done`: _no_done", "severity": "fail", "expected": "done event", "actual": "no done event in stream", "context": "共 9 个事件，最后一个事件类型: error"
- `stream_error_event`: or_event", "severity": "fail", "expected": "no error event", "actual": "error: Error code: 429 - {'error': {'code': '429', 'message': 'Too many requests', 'type': 'limitation'}}", "context": "SSE 流中出现 error 事件（应用错误传播到客户端）"
- `stream_error_event`: or_event", "severity": "fail", "expected": "no error event", "actual": "error: Error code: 429 - {'error': {'code': '429', 'message': 'Too many requests', 'type': 'limitation'}}", "context": "SSE 流中出现 error 事件（应用错误传播到客户端）"
- `intent_mismatch`: mismatch", "expect": "search_info", "actual": "data_query"
- `missing_tools`: ng_tools", "missing": ["query_meeting_detail"], "note": "tools_any — 任一即可"

**回答预览 (前 200 字)**:
```

```

### D-L1-0221 (D) — FAIL
**问题**: 我们课题组现在有几个进行中的项目？
- `stream_no_done`: _no_done", "severity": "fail", "expected": "done event", "actual": "no done event in stream", "context": "共 8 个事件，最后一个事件类型: error"
- `stream_error_event`: or_event", "severity": "fail", "expected": "no error event", "actual": "error: cannot access local variable 'final_text' where it is not associated with a value", "context": "SSE 流中出现 error 事件（应用错误传播到客户端）"
- `intent_mismatch`: mismatch", "expect": "search_info", "actual": "data_query"

**回答预览 (前 200 字)**:
```

```

### D-L2-0222 (D) — FAIL
**问题**: 列出所有基金类项目。
- `stream_no_done`: _no_done", "severity": "fail", "expected": "done event", "actual": "no done event in stream", "context": "共 7 个事件，最后一个事件类型: error"
- `stream_error_event`: or_event", "severity": "fail", "expected": "no error event", "actual": "error: cannot access local variable 'final_text' where it is not associated with a value", "context": "SSE 流中出现 error 事件（应用错误传播到客户端）"

**回答预览 (前 200 字)**:
```

```

### D-L2-0223 (D) — FAIL
**问题**: 下个月有哪些项目要结题？
- `stream_no_done`: _no_done", "severity": "fail", "expected": "done event", "actual": "no done event in stream", "context": "共 5 个事件，最后一个事件类型: error"
- `stream_error_event`: or_event", "severity": "fail", "expected": "no error event", "actual": "error: Error code: 429 - {'error': {'code': '429', 'message': 'Too many requests', 'type': 'limitation'}}", "context": "SSE 流中出现 error 事件（应用错误传播到客户端）"
- `stream_error_event`: or_event", "severity": "fail", "expected": "no error event", "actual": "error: Error code: 429 - {'error': {'code': '429', 'message': 'Too many requests', 'type': 'limitation'}}", "context": "SSE 流中出现 error 事件（应用错误传播到客户端）"
- `intent_mismatch`: mismatch", "expect": "search_info", "actual": "data_query"
- `missing_tools`: ng_tools", "missing": ["query_projects"], "note": "tools_any — 任一即可"

**回答预览 (前 200 字)**:
```

```

### D-L2-0224 (D) — FAIL
**问题**: 我负责哪些项目？
- `stream_no_done`: _no_done", "severity": "fail", "expected": "done event", "actual": "no done event in stream", "context": "共 12 个事件，最后一个事件类型: error"
- `stream_error_event`: or_event", "severity": "fail", "expected": "no error event", "actual": "error: cannot access local variable 'final_text' where it is not associated with a value", "context": "SSE 流中出现 error 事件（应用错误传播到客户端）"

**回答预览 (前 200 字)**:
```

```

### D-L2-0226 (D) — FAIL
**问题**: 国家自然科学基金面上项目的摘要。
- `fake_xml_leaked`: l_leaked", "patterns": ["<function\\s*=[^>]+>"]
- `missing_tools`: ng_tools", "missing": ["query_project_detail"], "note": "tools_any — 任一即可"

**回答预览 (前 200 字)**:
```
知识库中没有直接关于"面上项目摘要"的定义，让我再搜索一下更具体的信息。<tool_call>
<function=web_search>
<parameter=query>国家自然科学基金面上项目摘要 字数要求 撰写规范</parameter>
<parameter=num_results>5</parameter>
</function>
</tool_call>知识库返回的是微纳米气泡相关的
```

### D-L2-0234 (D) — FAIL
**问题**: 浙江省重点研发计划的目标是什么？
- `stream_no_done`: _no_done", "severity": "fail", "expected": "done event", "actual": "no done event in stream", "context": "共 5 个事件，最后一个事件类型: error"
- `stream_error_event`: or_event", "severity": "fail", "expected": "no error event", "actual": "error: Error code: 429 - {'error': {'code': '429', 'message': 'Too many requests', 'type': 'limitation'}}", "context": "SSE 流中出现 error 事件（应用错误传播到客户端）"
- `stream_error_event`: or_event", "severity": "fail", "expected": "no error event", "actual": "error: Error code: 429 - {'error': {'code': '429', 'message': 'Too many requests', 'type': 'limitation'}}", "context": "SSE 流中出现 error 事件（应用错误传播到客户端）"
- `missing_tools`: ng_tools", "missing": ["query_project_detail"], "note": "tools_any — 任一即可"

**回答预览 (前 200 字)**:
```

```

### D-L2-0235 (D) — FAIL
**问题**: 校企合作项目的经费来源？
- `stream_no_done`: _no_done", "severity": "fail", "expected": "done event", "actual": "no done event in stream", "context": "共 5 个事件，最后一个事件类型: error"
- `stream_error_event`: or_event", "severity": "fail", "expected": "no error event", "actual": "error: Error code: 429 - {'error': {'code': '429', 'message': 'Too many requests', 'type': 'limitation'}}", "context": "SSE 流中出现 error 事件（应用错误传播到客户端）"
- `stream_error_event`: or_event", "severity": "fail", "expected": "no error event", "actual": "error: Error code: 429 - {'error': {'code': '429', 'message': 'Too many requests', 'type': 'limitation'}}", "context": "SSE 流中出现 error 事件（应用错误传播到客户端）"
- `missing_tools`: ng_tools", "missing": ["query_project_detail"], "note": "tools_any — 任一即可"

**回答预览 (前 200 字)**:
```

```

### D-L2-0236 (D) — FAIL
**问题**: 延期项目有哪些？
- `fake_xml_leaked`: l_leaked", "patterns": ["<function\\s*=[^>]+>"]
- `intent_mismatch`: mismatch", "expect": "search_info", "actual": "data_query"
- `missing_tools`: ng_tools", "missing": ["query_projects"], "note": "tools_any — 任一即可"

**回答预览 (前 200 字)**:
```
<tool_call>
<function=query_projects>
<parameter=status>延期</parameter>
</function>
</tool_call>
```

### D-L3-0225 (D) — FAIL
**问题**: 近 3 年我们共申请到多少项目？总经费多少？
- `stream_no_done`: _no_done", "severity": "fail", "expected": "done event", "actual": "no done event in stream", "context": "共 5 个事件，最后一个事件类型: error"
- `stream_error_event`: or_event", "severity": "fail", "expected": "no error event", "actual": "error: Error code: 429 - {'error': {'code': '429', 'message': 'Too many requests', 'type': 'limitation'}}", "context": "SSE 流中出现 error 事件（应用错误传播到客户端）"
- `stream_error_event`: or_event", "severity": "fail", "expected": "no error event", "actual": "error: Error code: 429 - {'error': {'code': '429', 'message': 'Too many requests', 'type': 'limitation'}}", "context": "SSE 流中出现 error 事件（应用错误传播到客户端）"
- `missing_tools`: ng_tools", "missing": ["query_projects", "query_team_stats"], "note": "tools_any — 任一即可"

**回答预览 (前 200 字)**:
```

```

### D-L3-0227 (D) — FAIL
**问题**: 我参与的项目都获得了什么成果？
- `missing_tools`: ng_tools", "missing": ["query_project_detail"], "note": "tools_any — 任一即可"

**回答预览 (前 200 字)**:
```
我需要先查询您参与的项目信息。让我调用工具来获取相关数据。
```

### D-L3-0228 (D) — FAIL
**问题**: 我们项目的主要风险点有哪些？
- `stream_no_done`: _no_done", "severity": "fail", "expected": "done event", "actual": "no done event in stream", "context": "共 5 个事件，最后一个事件类型: error"
- `stream_error_event`: or_event", "severity": "fail", "expected": "no error event", "actual": "error: Error code: 429 - {'error': {'code': '429', 'message': 'Too many requests', 'type': 'limitation'}}", "context": "SSE 流中出现 error 事件（应用错误传播到客户端）"
- `stream_error_event`: or_event", "severity": "fail", "expected": "no error event", "actual": "error: Error code: 429 - {'error': {'code': '429', 'message': 'Too many requests', 'type': 'limitation'}}", "context": "SSE 流中出现 error 事件（应用错误传播到客户端）"
- `missing_tools`: ng_tools", "missing": ["query_project_detail"], "note": "tools_any — 任一即可"

**回答预览 (前 200 字)**:
```

```

### D-L3-0229 (D) — FAIL
**问题**: 对比两个项目的预算和进度。
- `fake_xml_leaked`: l_leaked", "patterns": ["<function\\s*=[^>]+>"]
- `intent_mismatch`: mismatch", "expect": "search_info", "actual": "data_query"
- `missing_tools`: ng_tools", "missing": ["query_project_detail"], "note": "tools_any — 任一即可"

**回答预览 (前 200 字)**:
```
用户没有指定具体是哪两个项目，我需要先展示项目列表，让用户选择要对比的项目。<tool_call>
<function=get_project_detail>
<parameter=project_id>2</parameter>
</function>
</tool_call><tool_call>
<function=get_project_detail>
<parameter=project
```

### D-L3-0230 (D) — FAIL
**问题**: 我打算做一个微气泡降解抗生素的实验，帮我出一份研究计划。
- `stream_no_done`: _no_done", "severity": "fail", "expected": "done event", "actual": "no done event in stream", "context": "共 5 个事件，最后一个事件类型: error"
- `stream_error_event`: or_event", "severity": "fail", "expected": "no error event", "actual": "error: Error code: 429 - {'error': {'code': '429', 'message': 'Too many requests', 'type': 'limitation'}}", "context": "SSE 流中出现 error 事件（应用错误传播到客户端）"
- `stream_error_event`: or_event", "severity": "fail", "expected": "no error event", "actual": "error: Error code: 429 - {'error': {'code': '429', 'message': 'Too many requests', 'type': 'limitation'}}", "context": "SSE 流中出现 error 事件（应用错误传播到客户端）"
- `missing_tools`: ng_tools", "missing": ["generate_project_plan"], "note": "tools_any — 任一即可"

**回答预览 (前 200 字)**:
```

```

### D-L3-0231 (D) — FAIL
**问题**: 我们要申报一个省级重点项目，帮我列 10 个创新点。
- `missing_tools`: ng_tools", "missing": ["generate_project_plan"], "note": "tools_any — 任一即可"

**回答预览 (前 200 字)**:
```
基于课题组在微纳米气泡领域的研究积累，结合当前环境治理、绿色农业和碳中和的国家战略需求，为您梳理了以下 **10 个具有竞争力的创新点**。这些点涵盖了从基础理论到工程应用的全链条，适合省级重点项目的申报定位：

### 一、 基础理论与机制创新

1.  **微纳气泡界面电场与自由基耦合机制**
    *   **创新内容**：突破传统“气泡尺寸”研究范式，深入揭示微纳气泡独特的**界面电场（
```

### D-L3-0233 (D) — FAIL
**问题**: 这个项目的研究路线不清晰，请重新整理。
- `stream_no_done`: _no_done", "severity": "fail", "expected": "done event", "actual": "no done event in stream", "context": "共 10 个事件，最后一个事件类型: error"
- `stream_error_event`: or_event", "severity": "fail", "expected": "no error event", "actual": "error: cannot access local variable 'final_text' where it is not associated with a value", "context": "SSE 流中出现 error 事件（应用错误传播到客户端）"
- `intent_mismatch`: mismatch", "expect": "search_info", "actual": "execute_action"
- `missing_tools`: ng_tools", "missing": ["generate_project_plan"], "note": "tools_any — 任一即可"

**回答预览 (前 200 字)**:
```

```

### D-L3-0237 (D) — FAIL
**问题**: 按类型和金额对项目进行分类统计。
- `stream_no_done`: _no_done", "severity": "fail", "expected": "done event", "actual": "no done event in stream", "context": "共 5 个事件，最后一个事件类型: error"
- `stream_error_event`: or_event", "severity": "fail", "expected": "no error event", "actual": "error: Error code: 429 - {'error': {'code': '429', 'message': 'Too many requests', 'type': 'limitation'}}", "context": "SSE 流中出现 error 事件（应用错误传播到客户端）"
- `stream_error_event`: or_event", "severity": "fail", "expected": "no error event", "actual": "error: Error code: 429 - {'error': {'code': '429', 'message': 'Too many requests', 'type': 'limitation'}}", "context": "SSE 流中出现 error 事件（应用错误传播到客户端）"
- `missing_tools`: ng_tools", "missing": ["query_projects", "query_team_stats"], "note": "tools_any — 任一即可"

**回答预览 (前 200 字)**:
```

```

### D-L3-0238 (D) — FAIL
**问题**: 项目中可能的伦理/合规问题有哪些？
- `duration_warn`: ion_warn", "duration_ms": 43324
- `missing_tools`: ng_tools", "missing": ["query_project_detail"], "note": "tools_any — 任一即可"

**回答预览 (前 200 字)**:
```
[Self-RAG 重检索 #1] 使用改写 query 重检索
[Self-RAG 重检索 #2] 使用改写 query 重检索
[Self-RAG 重检索 #3] 使用改写 query 重检索
[Self-RAG 重检索 #4] 使用改写 query 重检索
[Self-RAG 重检索 #5] 使用改写 query 重检索
[Self-RAG 重检索 #6] 使用改写 query 重检索
[S
```

### D-L4-0232 (D) — FAIL
**问题**: 立项答辩 PPT 怎么设计？
- `stream_no_done`: _no_done", "severity": "fail", "expected": "done event", "actual": "no done event in stream", "context": "共 7 个事件，最后一个事件类型: error"
- `stream_error_event`: or_event", "severity": "fail", "expected": "no error event", "actual": "error: cannot access local variable 'final_text' where it is not associated with a value", "context": "SSE 流中出现 error 事件（应用错误传播到客户端）"
- `missing_tools`: ng_tools", "missing": ["generate_project_plan"], "note": "tools_any — 任一即可"

**回答预览 (前 200 字)**:
```

```

### E-L1-0261 (E) — FAIL
**问题**: 什么是微纳米气泡？
- `intent_mismatch`: mismatch", "expect": "search_info", "actual": "explain_concept"
- `forbidden_names_appeared`: appeared", "names": ["王天志", "赵航佳", "宋洋"]

**回答预览 (前 200 字)**:
```
## 什么是微纳米气泡？

### 一、定义与物理化学意义

微纳米气泡是指**直径在微米至纳米级别**的气泡，通常分为两类 [1]：

| 类型 | 直径范围 | 特征 |
|------|----------|------|
| **微米级气泡** | 1–100 μm | 肉眼不可见，水中呈乳白色 |
| **纳米级气泡** | < 1 μm | 完全透明，需专业仪器检测 |

与普通气泡（
```

### E-L2-0262 (E) — FAIL
**问题**: 高级氧化技术有哪些分类？
- `stream_no_done`: _no_done", "severity": "fail", "expected": "done event", "actual": "no done event in stream", "context": "共 5 个事件，最后一个事件类型: error"
- `stream_error_event`: or_event", "severity": "fail", "expected": "no error event", "actual": "error: Error code: 429 - {'error': {'code': '429', 'message': 'Too many requests', 'type': 'limitation'}}", "context": "SSE 流中出现 error 事件（应用错误传播到客户端）"
- `stream_error_event`: or_event", "severity": "fail", "expected": "no error event", "actual": "error: Error code: 429 - {'error': {'code': '429', 'message': 'Too many requests', 'type': 'limitation'}}", "context": "SSE 流中出现 error 事件（应用错误传播到客户端）"
- `missing_tools`: ng_tools", "missing": ["search_knowledge"], "note": "tools_any — 任一即可"

**回答预览 (前 200 字)**:
```

```

### E-L2-0263 (E) — FAIL
**问题**: zeta 电位如何测量？
- `duration_warn`: ion_warn", "duration_ms": 46343
- `stream_no_done`: _no_done", "severity": "fail", "expected": "done event", "actual": "no done event in stream", "context": "共 1022 个事件，最后一个事件类型: error"
- `stream_error_event`: or_event", "severity": "fail", "expected": "no error event", "actual": "error: cannot access local variable 'final_text' where it is not associated with a value", "context": "SSE 流中出现 error 事件（应用错误传播到客户端）"

**回答预览 (前 200 字)**:
```
[Self-RAG 重检索 #1] 使用改写 query 重检索
[Self-RAG 重检索 #2] 使用改写 query 重检索
[Self-RAG 重检索 #3] 使用改写 query 重检索
[Self-RAG 重检索 #4] 使用改写 query 重检索
[Self-RAG 重检索 #5] 使用改写 query 重检索
[Self-RAG 重检索 #6] 使用改写 query 重检索
[S
```

### E-L2-0265 (E) — FAIL
**问题**: 我们课题组关于微纳米气泡发表的论文列表。
- `stream_no_done`: _no_done", "severity": "fail", "expected": "done event", "actual": "no done event in stream", "context": "共 5 个事件，最后一个事件类型: error"
- `stream_error_event`: or_event", "severity": "fail", "expected": "no error event", "actual": "error: Error code: 429 - {'error': {'code': '429', 'message': 'Too many requests', 'type': 'limitation'}}", "context": "SSE 流中出现 error 事件（应用错误传播到客户端）"
- `stream_error_event`: or_event", "severity": "fail", "expected": "no error event", "actual": "error: Error code: 429 - {'error': {'code': '429', 'message': 'Too many requests', 'type': 'limitation'}}", "context": "SSE 流中出现 error 事件（应用错误传播到客户端）"
- `intent_mismatch`: mismatch", "expect": "search_info", "actual": "data_query"
- `missing_tools`: ng_tools", "missing": ["query_papers", "search_knowledge"], "note": "tools_any — 任一即可"

**回答预览 (前 200 字)**:
```

```

### E-L2-0276 (E) — FAIL
**问题**: Smoluchowski 公式是什么？
- `stream_no_done`: _no_done", "severity": "fail", "expected": "done event", "actual": "no done event in stream", "context": "共 29 个事件，最后一个事件类型: error"
- `stream_error_event`: or_event", "severity": "fail", "expected": "no error event", "actual": "error: cannot access local variable 'final_text' where it is not associated with a value", "context": "SSE 流中出现 error 事件（应用错误传播到客户端）"
- `intent_mismatch`: mismatch", "expect": "search_info", "actual": "explain_concept"

**回答预览 (前 200 字)**:
```

```

### E-L2-0277 (E) — FAIL
**问题**: 亨利常数是什么？如何应用？
- `fake_xml_leaked`: l_leaked", "patterns": ["<function\\s*=[^>]+>"]
- `missing_tools`: ng_tools", "missing": ["list_formulas"], "note": "tools_any — 任一即可"

**回答预览 (前 200 字)**:
```
<tool_call>
<function=search_knowledge>
<parameter=query>亨利常数</parameter>
<parameter=top_k>5</parameter>
</function>
</tool_call>
```

### E-L3-0266 (E) — FAIL
**问题**: 请帮我总结 DLVO 理论的要点。
- `stream_no_done`: _no_done", "severity": "fail", "expected": "done event", "actual": "no done event in stream", "context": "共 27 个事件，最后一个事件类型: error"
- `stream_error_event`: or_event", "severity": "fail", "expected": "no error event", "actual": "error: cannot access local variable 'final_text' where it is not associated with a value", "context": "SSE 流中出现 error 事件（应用错误传播到客户端）"
- `intent_mismatch`: mismatch", "expect": "search_info", "actual": "explain_concept"

**回答预览 (前 200 字)**:
```

```

### E-L3-0267 (E) — FAIL
**问题**: 催化剂的 BET 表面积与活性之间有什么关系？
- `fake_xml_leaked`: l_leaked", "patterns": ["<function\\s*=[^>]+>"]

**回答预览 (前 200 字)**:
```
<tool_call>
<function=search_knowledge>
<parameter=query>BET 表面积 催化剂 活性 关系</parameter>
<parameter=top_k>5</parameter>
</function>
</tool_call>
```

### E-L3-0268 (E) — FAIL
**问题**: 给我一个关于 zeta 电位的知识摘要。
- `stream_no_done`: _no_done", "severity": "fail", "expected": "done event", "actual": "no done event in stream", "context": "共 5 个事件，最后一个事件类型: error"
- `stream_error_event`: or_event", "severity": "fail", "expected": "no error event", "actual": "error: Error code: 429 - {'error': {'code': '429', 'message': 'Too many requests', 'type': 'limitation'}}", "context": "SSE 流中出现 error 事件（应用错误传播到客户端）"
- `stream_error_event`: or_event", "severity": "fail", "expected": "no error event", "actual": "error: Error code: 429 - {'error': {'code': '429', 'message': 'Too many requests', 'type': 'limitation'}}", "context": "SSE 流中出现 error 事件（应用错误传播到客户端）"
- `missing_tools`: ng_tools", "missing": ["search_knowledge"], "note": "tools_any — 任一即可"

**回答预览 (前 200 字)**:
```

```

### E-L3-0269 (E) — FAIL
**问题**: 我们课题组关于高级氧化的核心论文有哪些？
- `stream_no_done`: _no_done", "severity": "fail", "expected": "done event", "actual": "no done event in stream", "context": "共 12 个事件，最后一个事件类型: error"
- `stream_error_event`: or_event", "severity": "fail", "expected": "no error event", "actual": "error: cannot access local variable 'final_text' where it is not associated with a value", "context": "SSE 流中出现 error 事件（应用错误传播到客户端）"
- `missing_tools`: ng_tools", "missing": ["query_papers"], "note": "tools_any — 任一即可"

**回答预览 (前 200 字)**:
```

```

### E-L3-0271 (E) — FAIL
**问题**: 我们课题组目前有哪些研究假设需要验证？
- `stream_no_done`: _no_done", "severity": "fail", "expected": "done event", "actual": "no done event in stream", "context": "共 8 个事件，最后一个事件类型: error"
- `stream_error_event`: or_event", "severity": "fail", "expected": "no error event", "actual": "error: cannot access local variable 'final_text' where it is not associated with a value", "context": "SSE 流中出现 error 事件（应用错误传播到客户端）"
- `intent_mismatch`: mismatch", "expect": "search_info", "actual": "data_query"

**回答预览 (前 200 字)**:
```

```

### E-L3-0272 (E) — FAIL
**问题**: 如何验证 H1 假设（微气泡强化臭氧传质）？
- `missing_tools`: ng_tools", "missing": ["list_hypotheses"], "note": "tools_any — 任一即可"

**回答预览 (前 200 字)**:
```
[已执行工具: search_knowledge] [已完成工具: search_knowledge][计划阶段] 我已主动查询 1 个工具获取背景信息。
```

### E-L3-0274 (E) — FAIL
**问题**: 把 H2 假设标记为已验证。
- `fake_xml_leaked`: l_leaked", "patterns": ["<function\\s*=[^>]+>"]
- `intent_mismatch`: mismatch", "expect": "execute_action", "actual": "search_info"
- `missing_tools`: ng_tools", "missing": ["update_hypothesis"], "note": "tools_any — 任一即可"

**回答预览 (前 200 字)**:
```
<tool_call>
<function=list_hypotheses>
</function>
</tool_call>
```

### E-L3-0275 (E) — FAIL
**问题**: 我们假设之间有冲突吗？
- `stream_no_done`: _no_done", "severity": "fail", "expected": "done event", "actual": "no done event in stream", "context": "共 5 个事件，最后一个事件类型: error"
- `stream_error_event`: or_event", "severity": "fail", "expected": "no error event", "actual": "error: Error code: 429 - {'error': {'code': '429', 'message': 'Too many requests', 'type': 'limitation'}}", "context": "SSE 流中出现 error 事件（应用错误传播到客户端）"
- `stream_error_event`: or_event", "severity": "fail", "expected": "no error event", "actual": "error: Error code: 429 - {'error': {'code': '429', 'message': 'Too many requests', 'type': 'limitation'}}", "context": "SSE 流中出现 error 事件（应用错误传播到客户端）"
- `missing_tools`: ng_tools", "missing": ["list_hypotheses"], "note": "tools_any — 任一即可"

**回答预览 (前 200 字)**:
```

```

### E-L3-0278 (E) — FAIL
**问题**: 微气泡的浮升速度用什么公式计算？
- `stream_no_done`: _no_done", "severity": "fail", "expected": "done event", "actual": "no done event in stream", "context": "共 16 个事件，最后一个事件类型: error"
- `stream_error_event`: or_event", "severity": "fail", "expected": "no error event", "actual": "error: cannot access local variable 'final_text' where it is not associated with a value", "context": "SSE 流中出现 error 事件（应用错误传播到客户端）"

**回答预览 (前 200 字)**:
```

```

### E-L3-0279 (E) — FAIL
**问题**: 帮我算一下 0.001 M NaCl 溶液的电导率。
- `stream_no_done`: _no_done", "severity": "fail", "expected": "done event", "actual": "no done event in stream", "context": "共 5 个事件，最后一个事件类型: error"
- `stream_error_event`: or_event", "severity": "fail", "expected": "no error event", "actual": "error: Error code: 429 - {'error': {'code': '429', 'message': 'Too many requests', 'type': 'limitation'}}", "context": "SSE 流中出现 error 事件（应用错误传播到客户端）"
- `stream_error_event`: or_event", "severity": "fail", "expected": "no error event", "actual": "error: Error code: 429 - {'error': {'code': '429', 'message': 'Too many requests', 'type': 'limitation'}}", "context": "SSE 流中出现 error 事件（应用错误传播到客户端）"
- `missing_tools`: ng_tools", "missing": ["calculate_formula"], "note": "tools_any — 任一即可"

**回答预览 (前 200 字)**:
```

```

### E-L4-0270 (E) — WARN
**问题**: 我想了解某个特定课题的概念，给我一个详细的解释。
- `intent_mismatch`: mismatch", "expect": "search_info", "actual": "explain_concept"

**回答预览 (前 200 字)**:
```
[Self-RAG 重检索 #1] 使用改写 query 重检索
```

### E-L4-0273 (E) — FAIL
**问题**: 假设 H1 如果被证伪意味着什么？
- `fake_xml_leaked`: l_leaked", "patterns": ["<function\\s*=[^>]+>"]
- `stream_no_done`: _no_done", "severity": "fail", "expected": "done event", "actual": "no done event in stream", "context": "共 14 个事件，最后一个事件类型: error"
- `stream_error_event`: or_event", "severity": "fail", "expected": "no error event", "actual": "error: Error code: 429 - {'error': {'code': '429', 'message': 'Too many requests', 'type': 'limitation'}}", "context": "SSE 流中出现 error 事件（应用错误传播到客户端）"
- `stream_error_event`: or_event", "severity": "fail", "expected": "no error event", "actual": "error: Error code: 429 - {'error': {'code': '429', 'message': 'Too many requests', 'type': 'limitation'}}", "context": "SSE 流中出现 error 事件（应用错误传播到客户端）"
- `missing_tools`: ng_tools", "missing": ["list_hypotheses"], "note": "tools_any — 任一即可"

**回答预览 (前 200 字)**:
```
<tool_call>
<function=list_hypotheses>
<parameter=query>H1</parameter>
</function>
</tool_call>
```

### F-L1-0311 (F) — FAIL
**问题**: 列出所有水处理相关的公式。
- `stream_no_done`: _no_done", "severity": "fail", "expected": "done event", "actual": "no done event in stream", "context": "共 5 个事件，最后一个事件类型: error"
- `stream_error_event`: or_event", "severity": "fail", "expected": "no error event", "actual": "error: Error code: 429 - {'error': {'code': '429', 'message': 'Too many requests', 'type': 'limitation'}}", "context": "SSE 流中出现 error 事件（应用错误传播到客户端）"
- `stream_error_event`: or_event", "severity": "fail", "expected": "no error event", "actual": "error: Error code: 429 - {'error': {'code': '429', 'message': 'Too many requests', 'type': 'limitation'}}", "context": "SSE 流中出现 error 事件（应用错误传播到客户端）"
- `missing_tools`: ng_tools", "missing": ["list_formulas"], "note": "tools_any — 任一即可"

**回答预览 (前 200 字)**:
```

```

### F-L2-0312 (F) — FAIL
**问题**: 给我看看吸附等温线相关的公式。
- `stream_no_done`: _no_done", "severity": "fail", "expected": "done event", "actual": "no done event in stream", "context": "共 5 个事件，最后一个事件类型: error"
- `stream_error_event`: or_event", "severity": "fail", "expected": "no error event", "actual": "error: Error code: 429 - {'error': {'code': '429', 'message': 'Too many requests', 'type': 'limitation'}}", "context": "SSE 流中出现 error 事件（应用错误传播到客户端）"
- `stream_error_event`: or_event", "severity": "fail", "expected": "no error event", "actual": "error: Error code: 429 - {'error': {'code': '429', 'message': 'Too many requests', 'type': 'limitation'}}", "context": "SSE 流中出现 error 事件（应用错误传播到客户端）"
- `missing_tools`: ng_tools", "missing": ["list_formulas"], "note": "tools_any — 任一即可"

**回答预览 (前 200 字)**:
```

```

### F-L2-0313 (F) — FAIL
**问题**: 热力学相关公式有哪些？
- `stream_no_done`: _no_done", "severity": "fail", "expected": "done event", "actual": "no done event in stream", "context": "共 5 个事件，最后一个事件类型: error"
- `stream_error_event`: or_event", "severity": "fail", "expected": "no error event", "actual": "error: Error code: 429 - {'error': {'code': '429', 'message': 'Too many requests', 'type': 'limitation'}}", "context": "SSE 流中出现 error 事件（应用错误传播到客户端）"
- `stream_error_event`: or_event", "severity": "fail", "expected": "no error event", "actual": "error: Error code: 429 - {'error': {'code': '429', 'message': 'Too many requests', 'type': 'limitation'}}", "context": "SSE 流中出现 error 事件（应用错误传播到客户端）"
- `missing_tools`: ng_tools", "missing": ["list_formulas"], "note": "tools_any — 任一即可"

**回答预览 (前 200 字)**:
```

```

### F-L2-0314 (F) — FAIL
**问题**: 流体力学常用公式。
- `stream_no_done`: _no_done", "severity": "fail", "expected": "done event", "actual": "no done event in stream", "context": "共 24 个事件，最后一个事件类型: error"
- `stream_error_event`: or_event", "severity": "fail", "expected": "no error event", "actual": "error: cannot access local variable 'final_text' where it is not associated with a value", "context": "SSE 流中出现 error 事件（应用错误传播到客户端）"

**回答预览 (前 200 字)**:
```

```

### F-L2-0323 (F) — FAIL
**问题**: 100 mM NaOH 等于多少 g/L（Mr NaOH = 40）？
- `stream_no_done`: _no_done", "severity": "fail", "expected": "done event", "actual": "no done event in stream", "context": "共 5 个事件，最后一个事件类型: error"
- `stream_error_event`: or_event", "severity": "fail", "expected": "no error event", "actual": "error: Error code: 429 - {'error': {'code': '429', 'message': 'Too many requests', 'type': 'limitation'}}", "context": "SSE 流中出现 error 事件（应用错误传播到客户端）"
- `stream_error_event`: or_event", "severity": "fail", "expected": "no error event", "actual": "error: Error code: 429 - {'error': {'code': '429', 'message': 'Too many requests', 'type': 'limitation'}}", "context": "SSE 流中出现 error 事件（应用错误传播到客户端）"
- `missing_tools`: ng_tools", "missing": ["unit_convert"], "note": "tools_any — 任一即可"

**回答预览 (前 200 字)**:
```

```

### F-L2-0324 (F) — FAIL
**问题**: 1 atm 等于多少 kPa？
- `stream_no_done`: _no_done", "severity": "fail", "expected": "done event", "actual": "no done event in stream", "context": "共 18 个事件，最后一个事件类型: error"
- `stream_error_event`: or_event", "severity": "fail", "expected": "no error event", "actual": "error: cannot access local variable 'final_text' where it is not associated with a value", "context": "SSE 流中出现 error 事件（应用错误传播到客户端）"
- `missing_tools`: ng_tools", "missing": ["unit_convert"], "note": "tools_any — 任一即可"

**回答预览 (前 200 字)**:
```

```

### F-L3-0315 (F) — FAIL
**问题**: 哪些公式跟臭氧氧化动力学相关？
- `fake_xml_leaked`: l_leaked", "patterns": ["<function\\s*=[^>]+>"]

**回答预览 (前 200 字)**:
```
<tool_call>
<function=list_formulas>
<parameter=search>臭氧</parameter>
</function>
</tool_call>
```

### F-L3-0316 (F) — FAIL
**问题**: 我们课题组经常用到的公式有哪几类？
- `fake_xml_leaked`: l_leaked", "patterns": ["<function\\s*=[^>]+>"]
- `missing_tools`: ng_tools", "missing": ["list_formulas"], "note": "tools_any — 任一即可"

**回答预览 (前 200 字)**:
```
<tool_call>
<function=list_formulas>
</function>
</tool_call>
```

### F-L3-0317 (F) — FAIL
**问题**: 计算 25°C、1 atm 下 O3 在水中的溶解度（亨利常数 H=0.082 mol/(L·atm)）。
- `missing_tools`: ng_tools", "missing": ["calculate_formula"], "note": "tools_any — 任一即可"

**回答预览 (前 200 字)**:
```
[结论阶段]

## 臭氧（O₃）在水中的溶解度计算

根据亨利定律（Henry's Law），气体在液体中的溶解度与该气体在液面上的分压成正比。

### 1. 计算公式

$$C = H \times P$$

其中：
- $C$：气体在水中的溶解度（mol/L）
- $H$：亨利常数，题目给定 $H = 0.082 \text{ mol/(L·atm)}$
- $P$：气体分压，题目给定 $
```

### F-L3-0318 (F) — FAIL
**问题**: 用 Langmuir 等温式计算单分子层吸附量。q_max=120 mg/g, K=0.5 L/mg, C_e=10 mg/L。
- `fake_xml_leaked`: l_leaked", "patterns": ["<function\\s*=[^>]+>"]
- `missing_tools`: ng_tools", "missing": ["calculate_formula"], "note": "tools_any — 任一即可"

**回答预览 (前 200 字)**:
```
<tool_call>
<function=list_formulas>
<parameter=search>吸附</parameter>
</function>
</tool_call>
```

### F-L3-0319 (F) — FAIL
**问题**: 水的黏度 20°C 时是多少？用 Arrhenius 公式估算。
- `stream_no_done`: _no_done", "severity": "fail", "expected": "done event", "actual": "no done event in stream", "context": "共 5 个事件，最后一个事件类型: error"
- `stream_error_event`: or_event", "severity": "fail", "expected": "no error event", "actual": "error: Error code: 429 - {'error': {'code': '429', 'message': 'Too many requests', 'type': 'limitation'}}", "context": "SSE 流中出现 error 事件（应用错误传播到客户端）"
- `stream_error_event`: or_event", "severity": "fail", "expected": "no error event", "actual": "error: Error code: 429 - {'error': {'code': '429', 'message': 'Too many requests', 'type': 'limitation'}}", "context": "SSE 流中出现 error 事件（应用错误传播到客户端）"
- `missing_tools`: ng_tools", "missing": ["calculate_formula"], "note": "tools_any — 任一即可"

**回答预览 (前 200 字)**:
```

```

### F-L3-0320 (F) — FAIL
**问题**: 微气泡半径 50 μm 时浮升速度。
- `stream_no_done`: _no_done", "severity": "fail", "expected": "done event", "actual": "no done event in stream", "context": "共 23 个事件，最后一个事件类型: error"
- `stream_error_event`: or_event", "severity": "fail", "expected": "no error event", "actual": "error: cannot access local variable 'final_text' where it is not associated with a value", "context": "SSE 流中出现 error 事件（应用错误传播到客户端）"
- `missing_tools`: ng_tools", "missing": ["calculate_formula"], "note": "tools_any — 任一即可"

**回答预览 (前 200 字)**:
```

```

### F-L3-0322 (F) — FAIL
**问题**: 帮我把单位 mg/L 转为 ppm（密度 1 g/cm³）。
- `stream_no_done`: _no_done", "severity": "fail", "expected": "done event", "actual": "no done event in stream", "context": "共 5 个事件，最后一个事件类型: error"
- `stream_error_event`: or_event", "severity": "fail", "expected": "no error event", "actual": "error: Error code: 429 - {'error': {'code': '429', 'message': 'Too many requests', 'type': 'limitation'}}", "context": "SSE 流中出现 error 事件（应用错误传播到客户端）"
- `stream_error_event`: or_event", "severity": "fail", "expected": "no error event", "actual": "error: Error code: 429 - {'error': {'code': '429', 'message': 'Too many requests', 'type': 'limitation'}}", "context": "SSE 流中出现 error 事件（应用错误传播到客户端）"
- `missing_tools`: ng_tools", "missing": ["unit_convert"], "note": "tools_any — 任一即可"

**回答预览 (前 200 字)**:
```

```

### F-L3-0325 (F) — FAIL
**问题**: 将 25 μg/m³ 转为 ppm（气体，mol weight = 50 g/mol）。
- `missing_tools`: ng_tools", "missing": ["unit_convert"], "note": "tools_any — 任一即可"

**回答预览 (前 200 字)**:
```
## 单位换算：μg/m³ → ppm

### 计算公式

在标准状况（STP：0°C，1 atm）下，气体浓度单位换算公式为：

$$
\text{ppm} = \frac{\text{μg/m}^3 \times 24.45}{\text{分子量 (g/mol)}}
$$

其中 **24.45** 是理想气体在 STP 下的摩尔体积（24.45 L/mol）。

> **注意**：如果条件
```

### F-L3-0326 (F) — FAIL
**问题**: 微泡数量 10^6 个/mL，每个 5 μm 直径，气泡总表面积多少？
- `missing_tools`: ng_tools", "missing": ["calculate_formula", "unit_convert"], "note": "tools_any — 任一即可"

**回答预览 (前 200 字)**:
```
我来帮你计算微纳米气泡的总表面积。

## 计算过程

### 已知条件
- 气泡数量浓度：$n = 10^6$ 个/mL
- 气泡直径：$d = 5\ \mu m$，即半径 $r = 2.5\ \mu m = 2.5 \times 10^{-6}\ m$

### 计算公式

**单个气泡的表面积**（球体）：
$$S_{single} = 4\pi r^2 = \pi d^2$$

**气泡总
```

### F-L3-0327 (F) — FAIL
**问题**: 标准焓变 ΔH_f(H2O,l)=-285.83 kJ/mol, ΔH_f(CO2,g)=-393.51 kJ/mol 等。CH4 燃烧焓？
- `stream_no_done`: _no_done", "severity": "fail", "expected": "done event", "actual": "no done event in stream", "context": "共 16 个事件，最后一个事件类型: error"
- `stream_error_event`: or_event", "severity": "fail", "expected": "no error event", "actual": "error: cannot access local variable 'final_text' where it is not associated with a value", "context": "SSE 流中出现 error 事件（应用错误传播到客户端）"
- `missing_tools`: ng_tools", "missing": ["calculate_formula"], "note": "tools_any — 任一即可"

**回答预览 (前 200 字)**:
```

```

### F-L4-0321 (F) — FAIL
**问题**: 计算反应活化能 Ea（频率因子 A=10^13, k=10^-3, T=300K, R=8.314）。
- `stream_no_done`: _no_done", "severity": "fail", "expected": "done event", "actual": "no done event in stream", "context": "共 5 个事件，最后一个事件类型: error"
- `stream_error_event`: or_event", "severity": "fail", "expected": "no error event", "actual": "error: Error code: 429 - {'error': {'code': '429', 'message': 'Too many requests', 'type': 'limitation'}}", "context": "SSE 流中出现 error 事件（应用错误传播到客户端）"
- `stream_error_event`: or_event", "severity": "fail", "expected": "no error event", "actual": "error: Error code: 429 - {'error': {'code': '429', 'message': 'Too many requests', 'type': 'limitation'}}", "context": "SSE 流中出现 error 事件（应用错误传播到客户端）"
- `missing_tools`: ng_tools", "missing": ["calculate_formula"], "note": "tools_any — 任一即可"

**回答预览 (前 200 字)**:
```

```

### F-L4-0328 (F) — FAIL
**问题**: 反应速率常数 k = 0.5 s^-1, 反应物浓度 0.1 M, 计算半衰期。
- `stream_no_done`: _no_done", "severity": "fail", "expected": "done event", "actual": "no done event in stream", "context": "共 21 个事件，最后一个事件类型: error"
- `stream_error_event`: or_event", "severity": "fail", "expected": "no error event", "actual": "error: cannot access local variable 'final_text' where it is not associated with a value", "context": "SSE 流中出现 error 事件（应用错误传播到客户端）"
- `missing_tools`: ng_tools", "missing": ["calculate_formula"], "note": "tools_any — 任一即可"

**回答预览 (前 200 字)**:
```

```

### G-L1-0341 (G) — FAIL
**问题**: 我们目前有哪些研究假设？
- `fake_xml_leaked`: l_leaked", "patterns": ["<function\\s*=[^>]+>"]
- `missing_tools`: ng_tools", "missing": ["list_hypotheses"], "note": "tools_any — 任一即可"

**回答预览 (前 200 字)**:
```
我来查询课题组目前的研究假设。<tool_call>
<function=list_hypotheses>
</function>
</tool_call>
```

### G-L2-0342 (G) — FAIL
**问题**: 按状态分类的假设。
- `stream_no_done`: _no_done", "severity": "fail", "expected": "done event", "actual": "no done event in stream", "context": "共 7 个事件，最后一个事件类型: error"
- `stream_error_event`: or_event", "severity": "fail", "expected": "no error event", "actual": "error: cannot access local variable 'final_text' where it is not associated with a value", "context": "SSE 流中出现 error 事件（应用错误传播到客户端）"

**回答预览 (前 200 字)**:
```

```

### G-L2-0343 (G) — FAIL
**问题**: 列出置信度大于 0.8 的所有假设。
- `missing_tools`: ng_tools", "missing": ["list_hypotheses"], "note": "tools_any — 任一即可"

**回答预览 (前 200 字)**:
```
我来查询置信度大于 0.8 的所有假设。
```

### G-L2-0344 (G) — FAIL
**问题**: 假设 H1 的具体内容是？
- `stream_no_done`: _no_done", "severity": "fail", "expected": "done event", "actual": "no done event in stream", "context": "共 31 个事件，最后一个事件类型: error"
- `stream_error_event`: or_event", "severity": "fail", "expected": "no error event", "actual": "error: cannot access local variable 'final_text' where it is not associated with a value", "context": "SSE 流中出现 error 事件（应用错误传播到客户端）"
- `intent_mismatch`: mismatch", "expect": "search_info", "actual": "explain_concept"

**回答预览 (前 200 字)**:
```

```

### G-L3-0345 (G) — FAIL
**问题**: 过去 6 个月新提出的假设有几个？
- `stream_no_done`: _no_done", "severity": "fail", "expected": "done event", "actual": "no done event in stream", "context": "共 9 个事件，最后一个事件类型: error"
- `stream_error_event`: or_event", "severity": "fail", "expected": "no error event", "actual": "error: cannot access local variable 'final_text' where it is not associated with a value", "context": "SSE 流中出现 error 事件（应用错误传播到客户端）"

**回答预览 (前 200 字)**:
```

```

### G-L3-0346 (G) — FAIL
**问题**: 按研究者统计假设贡献。
- `stream_no_done`: _no_done", "severity": "fail", "expected": "done event", "actual": "no done event in stream", "context": "共 5 个事件，最后一个事件类型: error"
- `stream_error_event`: or_event", "severity": "fail", "expected": "no error event", "actual": "error: Error code: 429 - {'error': {'code': '429', 'message': 'Too many requests', 'type': 'limitation'}}", "context": "SSE 流中出现 error 事件（应用错误传播到客户端）"
- `stream_error_event`: or_event", "severity": "fail", "expected": "no error event", "actual": "error: Error code: 429 - {'error': {'code': '429', 'message': 'Too many requests', 'type': 'limitation'}}", "context": "SSE 流中出现 error 事件（应用错误传播到客户端）"
- `intent_mismatch`: mismatch", "expect": "search_info", "actual": "data_query"
- `missing_tools`: ng_tools", "missing": ["list_hypotheses", "query_team_stats"], "note": "tools_any — 任一即可"

**回答预览 (前 200 字)**:
```

```

### G-L3-0347 (G) — FAIL
**问题**: H1 假设和哪些论文相关？
- `duration_warn`: ion_warn", "duration_ms": 39515
- `stream_no_done`: _no_done", "severity": "fail", "expected": "done event", "actual": "no done event in stream", "context": "共 20 个事件，最后一个事件类型: error"
- `stream_error_event`: or_event", "severity": "fail", "expected": "no error event", "actual": "error: cannot access local variable 'final_text' where it is not associated with a value", "context": "SSE 流中出现 error 事件（应用错误传播到客户端）"

**回答预览 (前 200 字)**:
```

```

### G-L3-0348 (G) — FAIL
**问题**: H2 与 H1 是否有协同关系？
- `stream_no_done`: _no_done", "severity": "fail", "expected": "done event", "actual": "no done event in stream", "context": "共 20 个事件，最后一个事件类型: error"
- `stream_error_event`: or_event", "severity": "fail", "expected": "no error event", "actual": "error: cannot access local variable 'final_text' where it is not associated with a value", "context": "SSE 流中出现 error 事件（应用错误传播到客户端）"

**回答预览 (前 200 字)**:
```

```

### G-L3-0349 (G) — FAIL
**问题**: H3 假设依赖哪些知识？
- `fake_xml_leaked`: l_leaked", "patterns": ["<function\\s*=[^>]+>"]
- `missing_tools`: ng_tools", "missing": ["list_hypotheses"], "note": "tools_any — 任一即可"

**回答预览 (前 200 字)**:
```
<tool_call>
<function=list_hypotheses>
<parameter=topic>H3</parameter>
</function>
</tool_call>
```

### G-L3-0350 (G) — FAIL
**问题**: H5 和 H6 是否互相矛盾？
- `stream_no_done`: _no_done", "severity": "fail", "expected": "done event", "actual": "no done event in stream", "context": "共 29 个事件，最后一个事件类型: error"
- `stream_error_event`: or_event", "severity": "fail", "expected": "no error event", "actual": "error: cannot access local variable 'final_text' where it is not associated with a value", "context": "SSE 流中出现 error 事件（应用错误传播到客户端）"
- `intent_mismatch`: mismatch", "expect": "search_info", "actual": "explain_concept"

**回答预览 (前 200 字)**:
```

```

### G-L3-0352 (G) — FAIL
**问题**: 假设之间的引用关系是怎样的？
- `fake_xml_leaked`: l_leaked", "patterns": ["<function\\s*=[^>]+>"]
- `missing_tools`: ng_tools", "missing": ["list_hypotheses", "search_knowledge"], "note": "tools_any — 任一即可"

**回答预览 (前 200 字)**:
```
<tool_call>
<function=list_hypotheses>
</function>
</tool_call>
```

### G-L3-0353 (G) — FAIL
**问题**: 帮我设计 H1 的验证实验。
- `stream_no_done`: _no_done", "severity": "fail", "expected": "done event", "actual": "no done event in stream", "context": "共 7 个事件，最后一个事件类型: error"
- `stream_error_event`: or_event", "severity": "fail", "expected": "no error event", "actual": "error: cannot access local variable 'final_text' where it is not associated with a value", "context": "SSE 流中出现 error 事件（应用错误传播到客户端）"
- `intent_mismatch`: mismatch", "expect": "execute_action", "actual": "search_info"
- `missing_tools`: ng_tools", "missing": ["design_experiment"], "note": "tools_any — 任一即可"

**回答预览 (前 200 字)**:
```

```

### G-L3-0354 (G) — FAIL
**问题**: H5 假设需要哪些数据来验证？
- `stream_no_done`: _no_done", "severity": "fail", "expected": "done event", "actual": "no done event in stream", "context": "共 19 个事件，最后一个事件类型: error"
- `stream_error_event`: or_event", "severity": "fail", "expected": "no error event", "actual": "error: cannot access local variable 'final_text' where it is not associated with a value", "context": "SSE 流中出现 error 事件（应用错误传播到客户端）"
- `intent_mismatch`: mismatch", "expect": "execute_action", "actual": "search_info"
- `missing_tools`: ng_tools", "missing": ["design_experiment"], "note": "tools_any — 任一即可"

**回答预览 (前 200 字)**:
```

```

### G-L3-0355 (G) — FAIL
**问题**: H2 验证的样本量怎么确定？
- `fake_xml_leaked`: l_leaked", "patterns": ["<function\\s*=[^>]+>"]
- `intent_mismatch`: mismatch", "expect": "execute_action", "actual": "search_info"
- `missing_tools`: ng_tools", "missing": ["design_experiment"], "note": "tools_any — 任一即可"

**回答预览 (前 200 字)**:
```
<tool_call>
<function=search_knowledge>
<parameter=query>假设检验 样本量 计算 功效分析 power analysis</parameter>
<parameter=top_k>5</parameter>
</function>
</tool_call>
```

### G-L3-0356 (G) — FAIL
**问题**: 为 H7 实验采购什么设备？
- `stream_no_done`: _no_done", "severity": "fail", "expected": "done event", "actual": "no done event in stream", "context": "共 5 个事件，最后一个事件类型: error"
- `stream_error_event`: or_event", "severity": "fail", "expected": "no error event", "actual": "error: Error code: 429 - {'error': {'code': '429', 'message': 'Too many requests', 'type': 'limitation'}}", "context": "SSE 流中出现 error 事件（应用错误传播到客户端）"
- `stream_error_event`: or_event", "severity": "fail", "expected": "no error event", "actual": "error: Error code: 429 - {'error': {'code': '429', 'message': 'Too many requests', 'type': 'limitation'}}", "context": "SSE 流中出现 error 事件（应用错误传播到客户端）"
- `intent_mismatch`: mismatch", "expect": "execute_action", "actual": "search_info"
- `missing_tools`: ng_tools", "missing": ["design_experiment"], "note": "tools_any — 任一即可"

**回答预览 (前 200 字)**:
```

```

### G-L3-0358 (G) — FAIL
**问题**: 假设验证失败后该如何调整？
- `stream_no_done`: _no_done", "severity": "fail", "expected": "done event", "actual": "no done event in stream", "context": "共 5 个事件，最后一个事件类型: error"
- `stream_error_event`: or_event", "severity": "fail", "expected": "no error event", "actual": "error: Error code: 429 - {'error': {'code': '429', 'message': 'Too many requests', 'type': 'limitation'}}", "context": "SSE 流中出现 error 事件（应用错误传播到客户端）"
- `stream_error_event`: or_event", "severity": "fail", "expected": "no error event", "actual": "error: Error code: 429 - {'error': {'code': '429', 'message': 'Too many requests', 'type': 'limitation'}}", "context": "SSE 流中出现 error 事件（应用错误传播到客户端）"
- `missing_tools`: ng_tools", "missing": ["design_experiment"], "note": "tools_any — 任一即可"

**回答预览 (前 200 字)**:
```

```

### G-L4-0351 (G) — FAIL
**问题**: 所有当前活跃假设与项目 52170001 的关联矩阵？
- `stream_no_done`: _no_done", "severity": "fail", "expected": "done event", "actual": "no done event in stream", "context": "共 5 个事件，最后一个事件类型: error"
- `stream_error_event`: or_event", "severity": "fail", "expected": "no error event", "actual": "error: Error code: 429 - {'error': {'code': '429', 'message': 'Too many requests', 'type': 'limitation'}}", "context": "SSE 流中出现 error 事件（应用错误传播到客户端）"
- `stream_error_event`: or_event", "severity": "fail", "expected": "no error event", "actual": "error: Error code: 429 - {'error': {'code': '429', 'message': 'Too many requests', 'type': 'limitation'}}", "context": "SSE 流中出现 error 事件（应用错误传播到客户端）"
- `intent_mismatch`: mismatch", "expect": "search_info", "actual": "data_query"
- `missing_tools`: ng_tools", "missing": ["list_hypotheses", "query_project_detail"], "note": "tools_any — 任一即可"

**回答预览 (前 200 字)**:
```

```

### G-L4-0357 (G) — FAIL
**问题**: H1 实验中遇到的 outlier 应该如何处理？
- `missing_tools`: ng_tools", "missing": ["design_experiment"], "note": "tools_any — 任一即可"

**回答预览 (前 200 字)**:
```
[Self-RAG 重检索 #1] 使用改写 query 重检索
```

### H-L1-0371 (H) — FAIL
**问题**: 你还记得我刚才问了什么吗？
- `fake_xml_leaked`: l_leaked", "patterns": ["<function\\s*=[^>]+>"]
- `intent_mismatch`: mismatch", "expect": "search_info", "actual": "casual_chat"
- `missing_tools`: ng_tools", "missing": ["query_short_memory"], "note": "tools_any — 任一即可"

**回答预览 (前 200 字)**:
```
<tool_call>
<function=search_memory>
<parameter=query>最近对话</parameter>
</function>
</tool_call>
```

### H-L1-0376 (H) — FAIL
**问题**: 你记得我的研究兴趣吗？
- `stream_no_done`: _no_done", "severity": "fail", "expected": "done event", "actual": "no done event in stream", "context": "共 5 个事件，最后一个事件类型: error"
- `stream_error_event`: or_event", "severity": "fail", "expected": "no error event", "actual": "error: Error code: 429 - {'error': {'code': '429', 'message': 'Too many requests', 'type': 'limitation'}}", "context": "SSE 流中出现 error 事件（应用错误传播到客户端）"
- `stream_error_event`: or_event", "severity": "fail", "expected": "no error event", "actual": "error: Error code: 429 - {'error': {'code': '429', 'message': 'Too many requests', 'type': 'limitation'}}", "context": "SSE 流中出现 error 事件（应用错误传播到客户端）"
- `missing_tools`: ng_tools", "missing": ["query_long_memory"], "note": "tools_any — 任一即可"

**回答预览 (前 200 字)**:
```

```

### H-L2-0372 (H) — FAIL
**问题**: 前 3 轮对话我都问过什么？
- `fake_xml_leaked`: l_leaked", "patterns": ["<function\\s*=[^>]+>"]
- `intent_mismatch`: mismatch", "expect": "search_info", "actual": "data_query"
- `missing_tools`: ng_tools", "missing": ["query_short_memory"], "note": "tools_any — 任一即可"

**回答预览 (前 200 字)**:
```
<tool_call>
<function=search_memory>
<parameter=query>会议</parameter>
<parameter=top_k>10</parameter>
</function>
</tool_call>
```

### H-L2-0373 (H) — FAIL
**问题**: 本次会话里我提到的具体数字有哪些？
- `stream_no_done`: _no_done", "severity": "fail", "expected": "done event", "actual": "no done event in stream", "context": "共 126 个事件，最后一个事件类型: error"
- `stream_error_event`: or_event", "severity": "fail", "expected": "no error event", "actual": "error: Error code: 429 - {'error': {'code': '429', 'message': 'Too many requests', 'type': 'limitation'}}", "context": "SSE 流中出现 error 事件（应用错误传播到客户端）"
- `stream_error_event`: or_event", "severity": "fail", "expected": "no error event", "actual": "error: Error code: 429 - {'error': {'code': '429', 'message': 'Too many requests', 'type': 'limitation'}}", "context": "SSE 流中出现 error 事件（应用错误传播到客户端）"
- `missing_tools`: ng_tools", "missing": ["query_short_memory"], "note": "tools_any — 任一即可"

**回答预览 (前 200 字)**:
```
本次会话中，你提到的具体数字有：

- **1**（"1 个问题"）
- **2**（"2 个问题"）
- **3**（"3 个问题"）
- **4**（"4 个问题"）
- **5**（"5 个问题"）
- **10**（"10 个问题"）
- **20**（"20 个问题"）
- **100**（"100 个问题"）
- **1000**（"1000 个问题"）
- **10000**（"10
```

### H-L2-0377 (H) — FAIL
**问题**: 我之前有没有说过我不喜欢哪种实验方法？
- `stream_no_done`: _no_done", "severity": "fail", "expected": "done event", "actual": "no done event in stream", "context": "共 5 个事件，最后一个事件类型: error"
- `stream_error_event`: or_event", "severity": "fail", "expected": "no error event", "actual": "error: Error code: 429 - {'error': {'code': '429', 'message': 'Too many requests', 'type': 'limitation'}}", "context": "SSE 流中出现 error 事件（应用错误传播到客户端）"
- `stream_error_event`: or_event", "severity": "fail", "expected": "no error event", "actual": "error: Error code: 429 - {'error': {'code': '429', 'message': 'Too many requests', 'type': 'limitation'}}", "context": "SSE 流中出现 error 事件（应用错误传播到客户端）"
- `intent_mismatch`: mismatch", "expect": "search_info", "actual": "data_query"
- `missing_tools`: ng_tools", "missing": ["query_long_memory"], "note": "tools_any — 任一即可"

**回答预览 (前 200 字)**:
```

```

### H-L2-0378 (H) — FAIL
**问题**: 我父亲的生日是什么时候？
- `stream_no_done`: _no_done", "severity": "fail", "expected": "done event", "actual": "no done event in stream", "context": "共 5 个事件，最后一个事件类型: error"
- `stream_error_event`: or_event", "severity": "fail", "expected": "no error event", "actual": "error: Error code: 429 - {'error': {'code': '429', 'message': 'Too many requests', 'type': 'limitation'}}", "context": "SSE 流中出现 error 事件（应用错误传播到客户端）"
- `stream_error_event`: or_event", "severity": "fail", "expected": "no error event", "actual": "error: Error code: 429 - {'error': {'code': '429', 'message': 'Too many requests', 'type': 'limitation'}}", "context": "SSE 流中出现 error 事件（应用错误传播到客户端）"
- `missing_tools`: ng_tools", "missing": ["query_long_memory"], "note": "tools_any — 任一即可"

**回答预览 (前 200 字)**:
```

```

### H-L2-0379 (H) — FAIL
**问题**: 我擅长什么？
- `stream_no_done`: _no_done", "severity": "fail", "expected": "done event", "actual": "no done event in stream", "context": "共 5 个事件，最后一个事件类型: error"
- `stream_error_event`: or_event", "severity": "fail", "expected": "no error event", "actual": "error: Error code: 429 - {'error': {'code': '429', 'message': 'Too many requests', 'type': 'limitation'}}", "context": "SSE 流中出现 error 事件（应用错误传播到客户端）"
- `stream_error_event`: or_event", "severity": "fail", "expected": "no error event", "actual": "error: Error code: 429 - {'error': {'code': '429', 'message': 'Too many requests', 'type': 'limitation'}}", "context": "SSE 流中出现 error 事件（应用错误传播到客户端）"
- `missing_tools`: ng_tools", "missing": ["query_long_memory"], "note": "tools_any — 任一即可"

**回答预览 (前 200 字)**:
```

```

### H-L2-0384 (H) — FAIL
**问题**: 请忘掉我父亲的生日。
- `stream_no_done`: _no_done", "severity": "fail", "expected": "done event", "actual": "no done event in stream", "context": "共 5 个事件，最后一个事件类型: error"
- `stream_error_event`: or_event", "severity": "fail", "expected": "no error event", "actual": "error: Error code: 429 - {'error': {'code': '429', 'message': 'Too many requests', 'type': 'limitation'}}", "context": "SSE 流中出现 error 事件（应用错误传播到客户端）"
- `stream_error_event`: or_event", "severity": "fail", "expected": "no error event", "actual": "error: Error code: 429 - {'error': {'code': '429', 'message': 'Too many requests', 'type': 'limitation'}}", "context": "SSE 流中出现 error 事件（应用错误传播到客户端）"
- `missing_tools`: ng_tools", "missing": ["forget_long_memory"], "note": "tools_any — 任一即可"

**回答预览 (前 200 字)**:
```

```

### H-L2-0385 (H) — FAIL
**问题**: 清理关于上次合作失败的所有记忆。
- `stream_no_done`: _no_done", "severity": "fail", "expected": "done event", "actual": "no done event in stream", "context": "共 7 个事件，最后一个事件类型: error"
- `stream_error_event`: or_event", "severity": "fail", "expected": "no error event", "actual": "error: Error code: 429 - {'error': {'code': '429', 'message': 'Too many requests', 'type': 'limitation'}}", "context": "SSE 流中出现 error 事件（应用错误传播到客户端）"
- `stream_error_event`: or_event", "severity": "fail", "expected": "no error event", "actual": "error: Error code: 429 - {'error': {'code': '429', 'message': 'Too many requests', 'type': 'limitation'}}", "context": "SSE 流中出现 error 事件（应用错误传播到客户端）"
- `missing_tools`: ng_tools", "missing": ["clear_short_memory", "forget_long_memory"], "note": "tools_any — 任一即可"

**回答预览 (前 200 字)**:
```

```

### H-L3-0374 (H) — FAIL
**问题**: 总结一下我们本次对话的核心观点。
- `stream_no_done`: _no_done", "severity": "fail", "expected": "done event", "actual": "no done event in stream", "context": "共 5 个事件，最后一个事件类型: error"
- `stream_error_event`: or_event", "severity": "fail", "expected": "no error event", "actual": "error: Error code: 429 - {'error': {'code': '429', 'message': 'Too many requests', 'type': 'limitation'}}", "context": "SSE 流中出现 error 事件（应用错误传播到客户端）"
- `stream_error_event`: or_event", "severity": "fail", "expected": "no error event", "actual": "error: Error code: 429 - {'error': {'code': '429', 'message': 'Too many requests', 'type': 'limitation'}}", "context": "SSE 流中出现 error 事件（应用错误传播到客户端）"
- `missing_tools`: ng_tools", "missing": ["summarize_session"], "note": "tools_any — 任一即可"

**回答预览 (前 200 字)**:
```

```

### H-L3-0375 (H) — FAIL
**问题**: 我刚才提到'那个实验'，指的是哪个？
- `stream_no_done`: _no_done", "severity": "fail", "expected": "done event", "actual": "no done event in stream", "context": "共 5 个事件，最后一个事件类型: error"
- `stream_error_event`: or_event", "severity": "fail", "expected": "no error event", "actual": "error: Error code: 429 - {'error': {'code': '429', 'message': 'Too many requests', 'type': 'limitation'}}", "context": "SSE 流中出现 error 事件（应用错误传播到客户端）"
- `stream_error_event`: or_event", "severity": "fail", "expected": "no error event", "actual": "error: Error code: 429 - {'error': {'code': '429', 'message': 'Too many requests', 'type': 'limitation'}}", "context": "SSE 流中出现 error 事件（应用错误传播到客户端）"
- `intent_mismatch`: mismatch", "expect": "search_info", "actual": "data_query"
- `missing_tools`: ng_tools", "missing": ["resolve_reference"], "note": "tools_any — 任一即可"

**回答预览 (前 200 字)**:
```

```

### H-L3-0380 (H) — FAIL
**问题**: 我是哪天注册的？什么时候加入了课题组？
- `stream_no_done`: _no_done", "severity": "fail", "expected": "done event", "actual": "no done event in stream", "context": "共 5 个事件，最后一个事件类型: error"
- `stream_error_event`: or_event", "severity": "fail", "expected": "no error event", "actual": "error: Error code: 429 - {'error': {'code': '429', 'message': 'Too many requests', 'type': 'limitation'}}", "context": "SSE 流中出现 error 事件（应用错误传播到客户端）"
- `stream_error_event`: or_event", "severity": "fail", "expected": "no error event", "actual": "error: Error code: 429 - {'error': {'code': '429', 'message': 'Too many requests', 'type': 'limitation'}}", "context": "SSE 流中出现 error 事件（应用错误传播到客户端）"
- `intent_mismatch`: mismatch", "expect": "search_info", "actual": "data_query"
- `missing_tools`: ng_tools", "missing": ["query_long_memory"], "note": "tools_any — 任一即可"

**回答预览 (前 200 字)**:
```

```

### H-L3-0381 (H) — FAIL
**问题**: 我经常使用的提醒事项有哪些？
- `stream_no_done`: _no_done", "severity": "fail", "expected": "done event", "actual": "no done event in stream", "context": "共 5 个事件，最后一个事件类型: error"
- `stream_error_event`: or_event", "severity": "fail", "expected": "no error event", "actual": "error: Error code: 429 - {'error': {'code': '429', 'message': 'Too many requests', 'type': 'limitation'}}", "context": "SSE 流中出现 error 事件（应用错误传播到客户端）"
- `stream_error_event`: or_event", "severity": "fail", "expected": "no error event", "actual": "error: Error code: 429 - {'error': {'code': '429', 'message': 'Too many requests', 'type': 'limitation'}}", "context": "SSE 流中出现 error 事件（应用错误传播到客户端）"
- `missing_tools`: ng_tools", "missing": ["query_long_memory", "query_reminders"], "note": "tools_any — 任一即可"

**回答预览 (前 200 字)**:
```

```

### H-L3-0382 (H) — FAIL
**问题**: 我最近一次提到家人是什么时候？
- `fake_xml_leaked`: l_leaked", "patterns": ["<function\\s*=[^>]+>"]
- `missing_tools`: ng_tools", "missing": ["query_long_memory"], "note": "tools_any — 任一即可"

**回答预览 (前 200 字)**:
```
<tool_call>
<function=search_memory>
<parameter=query>家人 家庭 父母 爸爸 妈妈 妻子 丈夫 孩子 家里</parameter>
<parameter=top_k>10</parameter>
<parameter=memory_type>user_fact</parameter>
</function>
</tool_call>
```

### H-L3-0383 (H) — FAIL
**问题**: 你了解过我的科研风格吗？
- `stream_no_done`: _no_done", "severity": "fail", "expected": "done event", "actual": "no done event in stream", "context": "共 20 个事件，最后一个事件类型: error"
- `stream_error_event`: or_event", "severity": "fail", "expected": "no error event", "actual": "error: cannot access local variable 'final_text' where it is not associated with a value", "context": "SSE 流中出现 error 事件（应用错误传播到客户端）"
- `missing_tools`: ng_tools", "missing": ["query_long_memory"], "note": "tools_any — 任一即可"

**回答预览 (前 200 字)**:
```

```

### H-L3-0386 (H) — FAIL
**问题**: 忘掉我过去 2 周的所有临时想法。
- `stream_no_done`: _no_done", "severity": "fail", "expected": "done event", "actual": "no done event in stream", "context": "共 7 个事件，最后一个事件类型: error"
- `stream_error_event`: or_event", "severity": "fail", "expected": "no error event", "actual": "error: Error code: 429 - {'error': {'code': '429', 'message': 'Too many requests', 'type': 'limitation'}}", "context": "SSE 流中出现 error 事件（应用错误传播到客户端）"
- `stream_error_event`: or_event", "severity": "fail", "expected": "no error event", "actual": "error: Error code: 429 - {'error': {'code': '429', 'message': 'Too many requests', 'type': 'limitation'}}", "context": "SSE 流中出现 error 事件（应用错误传播到客户端）"
- `intent_mismatch`: mismatch", "expect": "execute_action", "actual": "search_info"
- `missing_tools`: ng_tools", "missing": ["forget_long_memory"], "note": "tools_any — 任一即可"

**回答预览 (前 200 字)**:
```

```

### H-L3-0387 (H) — FAIL
**问题**: 我希望你忘记前面说过的话，从头开始。
- `intent_mismatch`: mismatch", "expect": "execute_action", "actual": "search_info"
- `missing_tools`: ng_tools", "missing": ["reset_session"], "note": "tools_any — 任一即可"

**回答预览 (前 200 字)**:
```
好的，已清空对话上下文。有什么可以帮你的？好的，上下文已清空。我是小气，你的全能 AI 助手。请问有什么可以帮你的？
```

### H-L3-0388 (H) — FAIL
**问题**: 帮我忘掉关于前公司的一切。
- `stream_no_done`: _no_done", "severity": "fail", "expected": "done event", "actual": "no done event in stream", "context": "共 5 个事件，最后一个事件类型: error"
- `stream_error_event`: or_event", "severity": "fail", "expected": "no error event", "actual": "error: Error code: 429 - {'error': {'code': '429', 'message': 'Too many requests', 'type': 'limitation'}}", "context": "SSE 流中出现 error 事件（应用错误传播到客户端）"
- `stream_error_event`: or_event", "severity": "fail", "expected": "no error event", "actual": "error: Error code: 429 - {'error': {'code': '429', 'message': 'Too many requests', 'type': 'limitation'}}", "context": "SSE 流中出现 error 事件（应用错误传播到客户端）"
- `intent_mismatch`: mismatch", "expect": "execute_action", "actual": "search_info"
- `missing_tools`: ng_tools", "missing": ["clear_short_memory", "forget_long_memory"], "note": "tools_any — 任一即可"

**回答预览 (前 200 字)**:
```

```

### H-L4-0389 (H) — FAIL
**问题**: 请忘记我跟你说过的所有工作秘密。
- `stream_no_done`: _no_done", "severity": "fail", "expected": "done event", "actual": "no done event in stream", "context": "共 5 个事件，最后一个事件类型: error"
- `stream_error_event`: or_event", "severity": "fail", "expected": "no error event", "actual": "error: Error code: 429 - {'error': {'code': '429', 'message': 'Too many requests', 'type': 'limitation'}}", "context": "SSE 流中出现 error 事件（应用错误传播到客户端）"
- `stream_error_event`: or_event", "severity": "fail", "expected": "no error event", "actual": "error: Error code: 429 - {'error': {'code': '429', 'message': 'Too many requests', 'type': 'limitation'}}", "context": "SSE 流中出现 error 事件（应用错误传播到客户端）"
- `missing_tools`: ng_tools", "missing": ["forget_long_memory", "mark_confidential_cleanup"], "note": "tools_any — 任一即可"

**回答预览 (前 200 字)**:
```

```

### K-L1-0001 (K) — FAIL
**问题**: 杨慈的研究方向？
- `stream_no_done`: _no_done", "severity": "fail", "expected": "done event", "actual": "no done event in stream", "context": "共 19 个事件，最后一个事件类型: error"
- `stream_error_event`: or_event", "severity": "fail", "expected": "no error event", "actual": "error: cannot access local variable 'final_text' where it is not associated with a value", "context": "SSE 流中出现 error 事件（应用错误传播到客户端）"
- `intent_mismatch`: mismatch", "expect": "DATA", "actual": "search_info"

**回答预览 (前 200 字)**:
```

```

### K-L1-0002 (K) — FAIL
**问题**: 杜同贺最近在做什么？
- `stream_no_done`: _no_done", "severity": "fail", "expected": "done event", "actual": "no done event in stream", "context": "共 5 个事件，最后一个事件类型: error"
- `stream_error_event`: or_event", "severity": "fail", "expected": "no error event", "actual": "error: Error code: 429 - {'error': {'code': '429', 'message': 'Too many requests', 'type': 'limitation'}}", "context": "SSE 流中出现 error 事件（应用错误传播到客户端）"
- `stream_error_event`: or_event", "severity": "fail", "expected": "no error event", "actual": "error: Error code: 429 - {'error': {'code': '429', 'message': 'Too many requests', 'type': 'limitation'}}", "context": "SSE 流中出现 error 事件（应用错误传播到客户端）"
- `intent_mismatch`: mismatch", "expect": "DATA", "actual": "search_info"
- `missing_tools`: ng_tools", "missing": ["query_members"], "note": "tools_any — 任一即可"

**回答预览 (前 200 字)**:
```

```

### K-L1-0003 (K) — FAIL
**问题**: 王天志带几个学生？
- `fake_xml_leaked`: l_leaked", "patterns": ["<function\\s*=[^>]+>"]
- `intent_mismatch`: mismatch", "expect": "DATA", "actual": "data_query"
- `missing_tools`: ng_tools", "missing": ["query_members"], "note": "tools_any — 任一即可"
- `forbidden_names_appeared`: appeared", "names": ["王天志"]

**回答预览 (前 200 字)**:
```
<tool_call>
<function=get_member_profile>
<parameter=name>王天志</parameter>
</function>
</tool_call>
```