# QA Bench Report — 2026-06-14T21:43:47.611559

**总题数**: 495 | **PASS**: 3 | **WARN**: 0 | **FAIL**: 5 | **ERROR**: 487

**通过率**: 0.6%

## 按分类

| 分类 | PASS | WARN | FAIL | ERROR |
|---|---|---|---|---|
| casual | 0 | 0 | 0 | 30 |
| cross | 0 | 0 | 0 | 55 |
| extreme | 0 | 0 | 0 | 20 |
| knowledge | 0 | 0 | 0 | 60 |
| meeting | 0 | 0 | 0 | 70 |
| member | 3 | 0 | 5 | 82 |
| memory | 0 | 0 | 0 | 30 |
| project | 0 | 0 | 0 | 60 |
| task | 0 | 0 | 0 | 80 |

## 问题分布

| 类型 | 次数 |
|---|---|
| `missing_tools` | 5 |
| `intent_mismatch` | 1 |

## 失败题详情


### M002 (member) — FAIL
**问题**: 对了刘莫菲 有什么产出？
- `missing_tools`: ng_tools", "missing": ["get_member_profile", "query_members"], "note": "tools_any — 任一即可"

**回答预览 (前 200 字)**:
```

```

### M003 (member) — FAIL
**问题**: 诶诶AI 一下 蒋芦笛
- `intent_mismatch`: mismatch", "expect": ["data_query", "recommend_person", "search_info"], "actual": "casual_chat", "note": "intent_any — 任一即可"
- `missing_tools`: ng_tools", "missing": ["get_member_profile", "query_members"], "note": "tools_any — 任一即可"

**回答预览 (前 200 字)**:
```

```

### M004 (member) — FAIL
**问题**: 话说做黑臭水体的
- `missing_tools`: ng_tools", "missing": ["get_member_profile", "query_members"], "note": "tools_any — 任一即可"

**回答预览 (前 200 字)**:
```

```

### M005 (member) — FAIL
**问题**: 关小未 在读研几？
- `missing_tools`: ng_tools", "missing": ["get_member_profile", "query_members"], "note": "tools_any — 任一即可"

**回答预览 (前 200 字)**:
```

```

### M007 (member) — FAIL
**问题**: 对了咱们组里做水产的
- `missing_tools`: ng_tools", "missing": ["get_member_profile", "query_members"], "note": "tools_any — 任一即可"

**回答预览 (前 200 字)**:
```

```