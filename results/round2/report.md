# QA Bench Report — 2026-06-14T16:58:09.343726

**总题数**: 100 | **PASS**: 0 | **WARN**: 0 | **FAIL**: 2 | **ERROR**: 98

**通过率**: 0.0%

## 按分类

| 分类 | PASS | WARN | FAIL | ERROR |
|---|---|---|---|---|
| casual | 0 | 0 | 0 | 5 |
| concept | 0 | 0 | 0 | 5 |
| cross | 0 | 0 | 0 | 5 |
| edge_hallucination | 0 | 0 | 0 | 15 |
| extreme | 0 | 0 | 0 | 10 |
| knowledge | 0 | 0 | 0 | 10 |
| meeting | 0 | 0 | 0 | 10 |
| member | 0 | 0 | 2 | 13 |
| memory | 0 | 0 | 0 | 5 |
| multiturn | 0 | 0 | 0 | 5 |
| project | 0 | 0 | 0 | 5 |
| task | 0 | 0 | 0 | 10 |

## 问题分布

| 类型 | 次数 |
|---|---|
| `missing_tools` | 2 |
| `hallucinated_names` | 1 |
| `forbidden_names_appeared` | 1 |
| `intent_mismatch` | 1 |
| `missing_required_terms` | 1 |

## 失败题详情


### A01 (member) — FAIL
**问题**: 杨慈是研究什么的？
- `hallucinated_names`: ed_names", "names": ["王天志", "杜同贺", "周之超"]
- `missing_tools`: ng_tools", "missing": ["query_members"]
- `forbidden_names_appeared`: appeared", "names": ["杜同贺", "王天志"]

**回答预览 (前 200 字)**:
```
根据课题组成员数据库，杨慈同学的研究方向如下：

## 杨慈的研究方向

**核心研究领域：饮用水安全**

杨慈同学专注于**微纳米气泡技术在饮用水安全保障领域的应用研究**，具体包括：

- **饮用水安全**：探索如何利用微纳米气泡技术提升饮用水水质
- **蜡样芽孢杆菌**：研究该类微生物的特性及其在水处理中的控制
- **微生物消杀**：利用微纳米气泡技术实现水中微生物的有效灭活

##
```

### A02 (member) — FAIL
**问题**: 宋洋做什么方向？
- `intent_mismatch`: mismatch", "expect": "search_info", "actual": "data_query"
- `missing_tools`: ng_tools", "missing": ["get_member_profile"]
- `missing_required_terms`: ed_terms", "missing": ["饮用水处理", "管网生物膜", "膜耦合"]

**回答预览 (前 200 字)**:
```

```