# QA Bench Report — 2026-06-30T20:56:24.909167

**总题数**: 3 | **PASS**: 0 | **WARN**: 0 | **FAIL**: 3 | **ERROR**: 0

**通过率**: 0.0%

## 按分类

| 分类 | PASS | WARN | FAIL | ERROR |
|---|---|---|---|---|
| A | 0 | 0 | 3 | 0 |

## 问题分布

| 类型 | 次数 |
|---|---|
| `stream_no_done` | 2 |
| `stream_error_event` | 2 |
| `missing_tools` | 1 |
| `fake_xml_leaked` | 1 |

## 7 维评分汇总 (v3.0)

**评分题数**: 3 | **一票否决**: 3


### 维度均分

| 维度 | 权重 | 均分 |
|---|---|---|
| intent | 10% | 1.00 |
| tool | 25% | 0.67 |
| content | 30% | 0.50 |
| rich | 5% | 1.00 |
| defense | 15% | 0.50 |
| perf | 10% | 1.00 |
| consistency | 5% | 1.00 |

### 分级分布

| 等级 | 范围 | 题数 |
|---|---|---|
| A | 90-100 | 0 |
| B | 75-89 | 0 |
| C | 60-74 | 0 |
| D | 40-59 | 0 |
| F | 0-39 | 3 |

## 失败题详情


### A-L1-0001 (A) — FAIL
**问题**: 王天志是干什么的？
- `stream_no_done`: _no_done", "severity": "fail", "expected": "done event", "actual": "no done event in stream", "context": "共 20 个事件，最后一个事件类型: error"
- `stream_error_event`: or_event", "severity": "fail", "expected": "no error event", "actual": "error: cannot access local variable 'final_text' where it is not associated with a value", "context": "SSE 流中出现 error 事件（应用错误传播到客户端）"

**回答预览 (前 200 字)**:
```

```

### A-L1-0002 (A) — FAIL
**问题**: 杜同贺是学生吗？他的研究方向是什么？
- `stream_no_done`: _no_done", "severity": "fail", "expected": "done event", "actual": "no done event in stream", "context": "共 7 个事件，最后一个事件类型: error"
- `stream_error_event`: or_event", "severity": "fail", "expected": "no error event", "actual": "error: cannot access local variable 'final_text' where it is not associated with a value", "context": "SSE 流中出现 error 事件（应用错误传播到客户端）"
- `missing_tools`: ng_tools", "missing": ["query_members"], "note": "tools_any — 任一即可"

**回答预览 (前 200 字)**:
```

```

### A-L2-0003 (A) — FAIL
**问题**: 我们课题组成员里谁在做臭氧氧化相关研究？
- `fake_xml_leaked`: l_leaked", "patterns": ["<function\\s*=[^>]+>"]

**回答预览 (前 200 字)**:
```
<tool_call>
<function=query_members>
<parameter=research_area>氧化</parameter>
</function>
</tool_call>
```