# QA Bench Report — 2026-07-02T04:00:54.507998

**总题数**: 10 | **PASS**: 1 | **WARN**: 0 | **FAIL**: 9 | **ERROR**: 0

**通过率**: 10.0%

## 按分类

| 分类 | PASS | WARN | FAIL | ERROR |
|---|---|---|---|---|
| A | 1 | 0 | 9 | 0 |

## 问题分布

| 类型 | 次数 |
|---|---|
| `stream_error_event` | 7 |
| `missing_tools` | 7 |
| `forbidden_names_appeared` | 4 |
| `fake_xml_leaked` | 4 |
| `intent_mismatch` | 1 |

## 7 维评分汇总 (v3.0)

**评分题数**: 10 | **一票否决**: 8


### 维度均分

| 维度 | 权重 | 均分 |
|---|---|---|
| intent | 10% | 0.90 |
| tool | 25% | 0.30 |
| content | 30% | 0.49 |
| rich | 5% | 0.80 |
| defense | 15% | 0.67 |
| perf | 10% | 1.00 |
| consistency | 5% | 1.00 |

### 分级分布

| 等级 | 范围 | 题数 |
|---|---|---|
| A | 90-100 | 1 |
| B | 75-89 | 1 |
| C | 60-74 | 0 |
| D | 40-59 | 0 |
| F | 0-39 | 8 |

## 失败题详情


### A-L1-0002 (A) — FAIL
**问题**: 杜同贺是学生吗？他的研究方向是什么？
- `forbidden_names_appeared`: appeared", "names": ["杜同贺", "杨慈"]

**回答预览 (前 200 字)**:
```
是的，**杜同贺是课题组的学生**，目前是**研一**（硕士一年级）。

他的研究方向是**污染控制与水质提升**，主要围绕微纳米气泡强化工艺开展研究，同时负责数据分析工作。具体信息如下：

- **年级**：研一
- **研究方向**：污染控制与水质提升
- **技能**：微纳米气泡、水质提升、数据分析
- **简介**：围绕污染控制与水质提升，开展微纳米气泡强化工艺研究与数据分析
- **邮箱
```

### A-L2-0003 (A) — FAIL
**问题**: 我们课题组成员里谁在做臭氧氧化相关研究？
- `stream_error_event`: or_event", "severity": "fail", "expected": "no error event", "actual": "error: Error code: 429 - {'error': {'code': '429', 'message': 'Too many requests', 'type': 'limitation'}}", "context": "SSE 流中出现 error 事件（应用错误传播到客户端）"
- `stream_error_event`: or_event", "severity": "fail", "expected": "no error event", "actual": "error: Error code: 429 - {'error': {'code': '429', 'message': 'Too many requests', 'type': 'limitation'}}", "context": "SSE 流中出现 error 事件（应用错误传播到客户端）"
- `missing_tools`: ng_tools", "missing": ["query_members"], "note": "tools_any — 任一即可"

**回答预览 (前 200 字)**:
```

```

### A-L2-0004 (A) — FAIL
**问题**: 杨慈是在读博士吗？
- `stream_error_event`: or_event", "severity": "fail", "expected": "no error event", "actual": "error: Error code: 429 - {'error': {'code': '429', 'message': 'Too many requests', 'type': 'limitation'}}", "context": "SSE 流中出现 error 事件（应用错误传播到客户端）"
- `stream_error_event`: or_event", "severity": "fail", "expected": "no error event", "actual": "error: Error code: 429 - {'error': {'code': '429', 'message': 'Too many requests', 'type': 'limitation'}}", "context": "SSE 流中出现 error 事件（应用错误传播到客户端）"
- `missing_tools`: ng_tools", "missing": ["query_members"], "note": "tools_any — 任一即可"

**回答预览 (前 200 字)**:
```

```

### A-L2-0005 (A) — FAIL
**问题**: 我们课题组的博士后有哪几位？
- `stream_error_event`: or_event", "severity": "fail", "expected": "no error event", "actual": "error: cannot access local variable 'final_text' where it is not associated with a value", "context": "SSE 流中出现 error 事件（应用错误传播到客户端）"

**回答预览 (前 200 字)**:
```

```

### A-L2-0006 (A) — FAIL
**问题**: 王天志的导师是谁？
- `fake_xml_leaked`: l_leaked", "patterns": ["<function\\s*=[^>]+>"]
- `missing_tools`: ng_tools", "missing": ["query_members"], "note": "tools_any — 任一即可"
- `forbidden_names_appeared`: appeared", "names": ["王天志"]

**回答预览 (前 200 字)**:
```
<tool_call>
<function=get_member_profile>
<parameter=name>王天志</parameter>
</function>
</tool_call>我来查询王天志的成员信息，包括他的导师信息。
```

### A-L2-0008 (A) — FAIL
**问题**: 赵航佳目前带几个学生？
- `fake_xml_leaked`: l_leaked", "patterns": ["<function\\s*=[^>]+>"]
- `intent_mismatch`: mismatch", "expect": "search_info", "actual": "data_query"
- `missing_tools`: ng_tools", "missing": ["query_members"], "note": "tools_any — 任一即可"
- `forbidden_names_appeared`: appeared", "names": ["赵航佳"]

**回答预览 (前 200 字)**:
```
<tool_call>
<function=get_member_profile>
<parameter=member_name>赵航佳</parameter>
</function>
</tool_call><tool_call>
<function=get_member_profile>
<parameter=name>赵航佳</parameter>
</function>
</tool_ca
```

### A-L2-0009 (A) — FAIL
**问题**: 我们课题组现在有多少在读硕士研究生？
- `fake_xml_leaked`: l_leaked", "patterns": ["<function\\s*=[^>]+>"]
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
- `stream_error_event`: or_event", "severity": "fail", "expected": "no error event", "actual": "error: Error code: 429 - {'error': {'code': '429', 'message': 'Too many requests', 'type': 'limitation'}}", "context": "SSE 流中出现 error 事件（应用错误传播到客户端）"
- `stream_error_event`: or_event", "severity": "fail", "expected": "no error event", "actual": "error: Error code: 429 - {'error': {'code': '429', 'message': 'Too many requests', 'type': 'limitation'}}", "context": "SSE 流中出现 error 事件（应用错误传播到客户端）"
- `missing_tools`: ng_tools", "missing": ["query_member_tasks"], "note": "tools_any — 任一即可"

**回答预览 (前 200 字)**:
```

```

### A-L2-0012 (A) — FAIL
**问题**: 王天志手上还有多少个未完成的任务？
- `fake_xml_leaked`: l_leaked", "patterns": ["<function\\s*=[^>]+>"]
- `missing_tools`: ng_tools", "missing": ["query_member_tasks"], "note": "tools_any — 任一即可"
- `forbidden_names_appeared`: appeared", "names": ["王天志"]

**回答预览 (前 200 字)**:
```
<tool_call>
<function=query_tasks>
<parameter=assignee_name>王天志</parameter>
<parameter=status>未完成</parameter>
</function>
</tool_call>
```