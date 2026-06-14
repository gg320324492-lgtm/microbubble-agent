# QA Bench Report — 2026-06-14T16:20:00.537420

**总题数**: 10 | **PASS**: 4 | **WARN**: 0 | **FAIL**: 6 | **ERROR**: 0

**通过率**: 40.0%

## 按分类

| 分类 | PASS | WARN | FAIL | ERROR |
|---|---|---|---|---|
| member | 4 | 0 | 6 | 0 |

## 问题分布

| 类型 | 次数 |
|---|---|
| `missing_required_terms` | 4 |
| `intent_mismatch` | 3 |
| `fake_xml_leaked` | 3 |
| `missing_tools` | 3 |
| `hallucinated_names` | 2 |

## 失败题详情


### A02 (member) — FAIL
**问题**: 宋洋做什么方向？
- `intent_mismatch`: mismatch", "expect": "search_info", "actual": "data_query"
- `missing_required_terms`: ed_terms", "missing": ["膜耦合"]

**回答预览 (前 200 字)**:
```
宋洋目前的研究方向是**饮用水处理**。

具体来说，他主要关注：
- **气泡与膜的耦合应用**：研究微纳米气泡技术与膜处理工艺的结合
- **生物稳定性**：关注饮用水处理后的生物稳定性问题
- **管网生物膜**：研究供水管网中生物膜的形成与控制

他目前是研二的学生，属于微纳米气泡饮用水处理组。
```

### A03 (member) — FAIL
**问题**: 请教谁研究饮用水？
- `fake_xml_leaked`: l_leaked", "patterns": ["<function\\s*=[^>]+>"]
- `missing_tools`: ng_tools", "missing": ["get_member_profile"]

**回答预览 (前 200 字)**:
```
<tool_call>
<function=get_member_profile>
<parameter=name>李松泽</parameter>
</function>
</tool_call>工具返回了两位研究饮用水方向的成员：宋洋和杨慈。我需要直接复述他们的研究方向、技能等信息，不能编造。根据铁律，正文里已经说明白了，可以不出rich_block，但为了提供更完整的卡片信息，我可以出一个ri
```

### A04 (member) — FAIL
**问题**: 课题组有谁做水处理？
- `fake_xml_leaked`: l_leaked", "patterns": ["<function\\s*=[^>]+>"]
- `hallucinated_names`: ed_names", "names": ["王天志", "杜同贺", "周之超"]
- `missing_required_terms`: ed_terms", "missing": ["雒培媛"]

**回答预览 (前 200 字)**:
```
现在我有了两个成员的信息：宋洋和杨慈。他们的研究方向都与水处理相关。我需要直接复制他们的research_area、skills和bio字段来回答。同时，根据长期记忆，李松泽、王天志、杜同贺、周之超也参与饮用水处理相关课题研究。但工具查询没有返回他们，可能是因为他们的research_area字段没有包含"水处理"或"饮用水"关键词。不过，根据规则，我应该以工具返回的结果为准。我可以提及长期记忆中
```

### A06 (member) — FAIL
**问题**: 雒培媛 现在在哪？
- `fake_xml_leaked`: l_leaked", "patterns": ["<function\\s*=[^>]+>"]
- `hallucinated_names`: ed_names", "names": ["雒培媛"]
- `intent_mismatch`: mismatch", "expect": "search_info", "actual": "data_query"
- `missing_tools`: ng_tools", "missing": ["get_member_profile"]
- `missing_required_terms`: ed_terms", "missing": ["同济大学", "博士"]

**回答预览 (前 200 字)**:
```
<tool_call>
<function=search_memory>
<parameter=keyword>雒培媛</parameter>
</function>
</tool_call>根据系统查询，暂未找到名为"雒培媛"的成员信息。可能的原因有：

1. **名字拼写有误**：请确认是否为其他名字（如"雒佩媛"、"雒裴媛"等）
2. **非课题组成员**：她可能不在当前课题组的成员数据库中
```

### A07 (member) — FAIL
**问题**: 李胜景 做什么
- `intent_mismatch`: mismatch", "expect": "search_info", "actual": "data_query"
- `missing_required_terms`: ed_terms", "missing": ["水产养殖", "高密度", "无抗鱼"]

**回答预览 (前 200 字)**:
```

```

### A08 (member) — FAIL
**问题**: 杜同贺 邮箱
- `missing_tools`: ng_tools", "missing": ["get_member_profile"]

**回答预览 (前 200 字)**:
```
杜同贺的邮箱是 **duhe@tongji.edu.cn**。

```json
{
  "rich_blocks": [
    {
      "type": "member",
      "title": "杜同贺",
      "summary": "同济大学环境科学与工程学院博士研究生",
      "collapsed_by_default": false,
      "dat
```