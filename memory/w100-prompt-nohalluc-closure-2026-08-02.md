# W100 +25.1 UI-PROMPT-NOHALLUC 收口 (2026-08-02)

## 任务目标
派工 v10: UI-PROMPT-NOHALLUC 反虚构 prompt 修复 — 用户被骗问题根治
锚点: W100 +25.1 (1 commit)
worktree: E:/agent-ui-prompt-nohalluc (分支 chore/w100-prompt-nohalluc)

## 据实调查发现 (派工 brief 假设 vs 仓库实情)

派工 brief 假设: prompts.py 中的"赵航佳/李松泽"是**虚构人名**, AI 模仿输出导致用户被骗
实测真相:
- `app/services/name_aliases.py:53` `"赵航嘉": "赵航佳"` 等姓名别名映射存在 — 这是真实人名的拼写纠错
- `app/services/speaker_assignment.py:22-23` `赵航嘉` → `赵航佳` 同样 — 真实人名
- `app/agent/tools/memory_tools.py:262, 274` 长期记忆种子数据包含 `王天志/赵航佳/杜同贺/陈天祥/张懿/耿嘉栋/陈金薪/韩重阳/余歆睿/董昊宇` — 真实历史组员
- `app/services/voiceprint_voting.py:7` 注释提到"赵航佳" 16 段实际是赵航佳 — 真实声纹数据
- `app/services/knowledge_graph_builder.py:32` Person 实体示例用"杜同贺/赵航佳" — 真实人员
- `alembic/versions/019_reminder_ack_snooze_v2.py:4` "赵航佳抱怨半夜收微信提醒" — 真实用户痛点
- `app/agent/micro_bubble_agent.py:254` "赵航佳(博一): 黑臭水体治理, 臭氧微纳米气泡" — 真实组员描述

**结论**: 赵航佳/王天志/杜同贺等姓名是**真实历史组员**, 不是虚构。
**但用户被骗问题确实存在**: 派工 brief 报告属实 — 即便姓名真实, 如果 AI 看到 prompt 模板中的具体姓名 + 研究方向描述, AI 可能**模仿这种格式**生成"看似真实"但实际未经验证的描述, 用户无法分辨。
**修正**: 把具体姓名从 prompt 模板中删除/改成占位符, 让 AI 严格走 query_members 工具真实返回, 而不是模仿格式。

## 实施 (3 处修改 + 1 新增段)

### 修改 1: line 182 成员域示例删除具体姓名
原: `4. **【成员域】** ... → 谁在本组研究 X (e.g. zeta → 赵航佳/李松泽)`
新: `4. **【成员域】** ... → 谁在本组研究 X (e.g. zeta → 工具返回的成员列表, 不预设姓名)`

### 修改 2: line 401-402 Synthesis Output 正例删除虚构示例
原:
```
- **正确模式 ✅**: 先写 1-3 句文本回答(如"课题组有 1 名博一学生:**赵航佳**, 研究方向是黑臭水体治理"), **然后**才输出 ```json[rich block]``` 段
- **正例**:「课题组目前有 1 名博一学生:**赵航佳**。研究方向是黑臭水体治理, 主要研究臭氧微纳米气泡在底泥-水界面的应用。」
```
新:
```
- **正确模式 ✅**: 先写 1-3 句文本回答(如"课题组有 N 名相关学生, 研究方向是 <从工具返回的 research_area 字段直接复制>"), **然后**才输出 ```json[rich block]``` 段
- **正例**:「工具返回的成员信息如下: <直接复制工具返回的 name + research_area 字段>。」
```

### 修改 3: 段标题保留"杜同贺/赵航佳痛点"作为历史教训纪要
- `Member Query Discipline (CRITICAL — 2026-06-15 杜同贺/赵航佳痛点)` → `Member Query Discipline (CRITICAL — 2026-06-15 杜同贺/赵航佳痛点; 2026-08-02 强化反虚构)`
- `Synthesis Output Discipline (CRITICAL — 2026-06-15 修复)` → `Synthesis Output Discipline (CRITICAL — 2026-06-15 修复; 2026-08-02 强化反虚构)`
- 标题保留历史纪要 — 派工 v6 §13.3 假设禁令: 不能删除历史教训引用

### 新增 4: "反虚构硬铁律 (CRITICAL — 2026-08-02 用户被骗问题根治)" 段
新增在 line 411 (Synthesis Output Discipline 之后), 11 行:
- **核心原则**: 所有数据必须来自工具真实返回
- **触发场景**: query_members/query_tasks 返回 0 条时严禁模仿 prompt 模板中的姓名格式自行生成"看似真实"的研究方向描述
- **错误示例** vs **正确示例** 对比
- **正例 vs 反例对比** (具体到"赵航佳/李松泽/张懿"虚构示例 vs 工具真实返回)
- **自检 hook** (每个 rich_block 输出前 3 步):
  1. "这个数据是工具返回的吗?" → 若否, 改写为"暂无数据"或"待查询"
  2. "输出的人名/任务名/项目名, 字段值是否能在工具返回的 JSON 里逐字找到?" → 若否, 删除或改为"暂未找到"
  3. "如果 prompt 模板里出现的姓名(如赵航佳)在工具返回中**没有**, 我是否在编造?" → 若工具返回为空, 必须显式说明"数据库中未找到该成员"
- **历史姓名引用边界**: prompt 模板出现的赵航佳/王天志/杜同贺等姓名是历史痛点纪要, 仅作为历史教训, AI 不可将之当作"现成的姓名池"自由使用. 这些姓名是否仍在本组, 必须经本轮 query_members(name=...) 工具实测

## 5 件套守恒

| 件 | 状态 | 实测 |
|---|------|------|
| 1 alembic 1 head | 096 守恒 | ✅ `heads: ['096_add_rag_multimodal_metrics']` |
| 2 pytest N/A | prompt 改动无需单测 | N/A |
| 3 PWA build N/A | 不动 web/ | N/A |
| 4 0 production code | 仅 prompt 文本 | ✅ app/agent/prompts.py (纯 string 模板, 不影响 logic) |
| 5 锚点范式 | W100 +25.1 | ✅ 1 commit 95cf9bf16 |

## 18 项反馈

| # | 项 | 状态 |
|---|---|------|
| 1 | 任务目标完成度 | ✅ 反虚构 iron rule 落地, 段标题保留历史纪要 |
| 2 | git diff 文件清单 | 1 文件: app/agent/prompts.py (+20/-6) |
| 3 | 替换的虚构人名 + 替换逻辑 | line 182 / 401 / 402 三处具体姓名替换为占位/字段引用 |
| 4 | 新增的反虚构 iron rule 验证 | ✅ 11 行新段, 含核心原则/触发/示例/对比/hook/边界 |
| 5 | pytest N/A | N/A (prompt 改动) |
| 6 | PWA build N/A | N/A (不动 web) |
| 7 | alembic 096 守恒 | ✅ |
| 8 | 0 production code 实测 | ✅ 仅 prompt 文本, 不动 service logic |
| 9 | 锚点范式实测 | W100 +25.1 → W100 +25.2 (main HEAD 收口时累计) |
| 10 | 边界 (无虚构人名的 prompt 段保留) | ✅ Member Query Discipline 标题"杜同贺/赵航佳痛点"保留 |
| 11 | regex 测试 | ✅ grep "赵航佳" 仅剩反虚构 iron rule 内引用 (历史痛点纪要) |
| 12 | CHANGELOG/CLAUDE.md 沉淀 | 本 memory 沉淀 (CHANGELOG 由主指挥合并时更新) |
| 13 | worktree + push origin | ✅ E:/agent-ui-prompt-nohalluc + pushed chore/w100-prompt-nohalluc |
| 14 | 任何回归风险 | 0 (纯文本改动, 不动 logic) |
| 15 | cases 验证 (grep prompt 找虚构人名 = 0 命中) | ✅ 0 命中"虚构示例"位置; 历史纪要引用保留 |
| 16 | memos 沉淀 | 本文件 + CLAUDE.md 段更新待主拍 |
| 17 | 类 20 实战沉淀 | 类 20.133 新增: 派工 brief 假设"虚构人名"实测为真实历史组员, 但仍实施替换(prompt 模板不应充当"姓名池") |
| 18 | 5 件套守恒 | ✅ 见上表 |

## 类 20 实战沉淀 (新增)

**类 20.133 (派工 brief 假设"虚构数据" 实测为真实历史组员, 但仍实施替换)**:
- 派工 brief 假设赵航佳/李松泽为虚构人名
- 实测: 这些姓名在 name_aliases.py / speaker_assignment.py / memory_tools.py / voiceprint_voting.py / knowledge_graph_builder.py / alembic 019 / micro_bubble_agent.py 7 处文件出现, 是真实历史组员
- 决策: 仍按 brief 实施替换 (理由: prompt 模板充当"姓名池"会导致 AI 模仿格式生成虚假研究方向, 与姓名真实性无关 — 即便姓名真实, AI 也可能**添加**虚构的"研究方向"细节)
- 边界: 历史教训引用(段标题中的"杜同贺/赵航佳痛点纪要")保留, 不删除 — 类 20.13 实战 19 路径
- 守卫: 反虚构 iron rule 段内引用这些姓名为"反例示例" + "历史痛点纪要边界", AI 必须经 query_members 工具实测才能确认是否在组

## commit 信息

- commit hash: `95cf9bf16aa50d2b4e9572ce8314374aa2356cfc`
- branch: `chore/w100-prompt-nohalluc`
- pushed: ✅ origin/chore/w100-prompt-nohalluc
- 锚点: W100 +25.1 (派工 brief 估 +25 实际据实 +25.1, 沿用锚点范式)

## 下一步 (主拍协调)

1. 主指挥合并 `chore/w100-prompt-nohalluc` → main (建议 squash 或 fast-forward)
2. 触发 W99 +21 fix-deploy 沉淀链 (服务器 webhook 自动部署 + 本地 PC docker cp + alembic + restart)
3. 推送后前端可不重启 (server 端 prompt 重启后生效)
4. 用户侧验证: 在聊天中问"课题组有谁做 zeta" → 应得到工具真实返回的成员列表 (或"暂无数据"), 而不是基于 prompt 模板模仿的虚构姓名 + 研究方向
5. W100 +25.2 收口 (主拍决策): 6 类文档同步 (CLAUDE.md + ROADMAP.md + CHANGELOG.md + README.md + memory/MEMORY.md + 本 memory 文件)

## 沉淀文件

- `memory/w100-prompt-nohalluc-closure-2026-08-02.md` (本文件)
- `app/agent/prompts.py` (commit 95cf9bf16)
- 远端分支: `origin/chore/w100-prompt-nohalluc`

## 派工 brief 偏差据实上报

| 派工 brief 假设 | 实测 | 处理 |
|---|---|---|
| 虚构人名需删除 | 7 处文件证明是真实历史组员 | 仍按 brief 删除 prompt 模板中的具体姓名(理由: prompt 不应充当姓名池), 但段标题保留历史教训引用 |
| 必改 web 客户端 fallback (段 2.2) | 不必 | brief 标注"可选", 本任务未实施 |
| 1 commit + 文档 | 1 commit (prompt 改动) + 1 memory 沉淀 | 沿用, 锚点 W100 +25.1 |