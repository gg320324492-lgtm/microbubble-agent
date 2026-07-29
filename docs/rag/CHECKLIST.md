# 派工 v11 检查单（RAG PR 派工速查版）

> 完整模板: [`docs/w72-prompt-paradigm-v11-2027-04.md`](../w72-prompt-paradigm-v11-2027-04.md)（v10 + 6 项新增）。本文件是主指挥派工前 / agent 收口前的一页速查。

## A. 主指挥派工前检查（brief 必填）

- [ ] 段 0: 目标一句话 + 边界（范围/不范围）+ 派工类型（A 调研 / B 实施 / C 清理 / D 收口）+ 锚点区间 `W8x +0 → +N`
- [ ] 段 0: **锚点起点实测**（`git log --grep` 确认未被占用; 被占用即顺延, 禁止让 agent 脑补）
- [ ] 段 1: alembic down_revision 显式（不产迁移也要写"本 PR 不产生迁移"）+ 命令形态 `python -m alembic`（v11 新增 1）
- [ ] 段 2: 新增/修改文件清单精确到行号 + 严禁修改清单（0 production code 例外与否显式声明）
- [ ] 段 3: e2e 目标数字化（N/N PASS）+ 重依赖 importorskip 策略
- [ ] 段 4: pytest 白名单完整 `--ignore` 清单 + baseline collected 数（v11 新增 2）
- [ ] 段 4: 5 件套守恒命令逐条列出
- [ ] 段 8: 起步 6 项含**依赖基线自检**（node_modules / sentence_transformers 等, v11 新增 5）
- [ ] 段 9: commit message 模板含 `[PRn W8x +N]` 锚点数字 + Co-Authored-By

## B. Agent 起步检查（开工前）

- [ ] Read plan 对应 § 全文（禁止只读派工摘要）
- [ ] worktree 建立: `git worktree add .claude/worktrees/<name> -b <branch> main`
- [ ] `python -m alembic heads` → 恰 1 head, 输出粘贴
- [ ] pytest baseline collect, collected 数与 brief 对比, 不符**据实上报差值**（v11 新增 3）
- [ ] `cd web && npm run build` 基线（worktree 无 node_modules 时主仓等价验证 + 上报）
- [ ] 起步 memory 落库 `memory/w8x-<topic>-start-<date>.md`

## C. Agent 收口检查（回报前）

- [ ] 5 件套回报表（v11 新增 6, 每格命令输出原文粘贴, 禁止"应该/大概/估计"）:

| 件 | 命令 | 判定 |
|----|------|------|
| 1 | `python -m alembic heads` | 1 head |
| 2 | `pytest <本 PR e2e> -q` | N/N PASS |
| 3 | `cd web && npm run build` | OK / pre-existing FAIL 据实标注 |
| 4 | `git diff main -- app/ \| wc -l` | 0（非例外 PR） |
| 5 | `git log --grep "W8x +" --oneline \| wc -l` | ≥ 目标 commit 数 |

- [ ] docs-only 门禁已断言化进 pytest（v11 新增 4, 章节数/关键词/链接/diff）
- [ ] 每 commit message 含锚点数字 + Co-Authored-By
- [ ] brief vs 实测偏差清单（0 项也要写"0 偏差"）
- [ ] memory 沉淀 + 主仓 CHANGELOG 条目
- [ ] 未 merge 未 push main（agent 不主动 merge, 主指挥拍板）

## D. 主指挥合并检查

- [ ] 按 PR 编号串行合并（禁止并行 alembic 派工）
- [ ] merge 后立即 `python -m alembic heads` verify 1 head
- [ ] 含前端 PR: `npm run build` + 6 点 curl 验证
- [ ] 收口后回填 plan Status 段（真 commit hash, 部分实施标 partial 不凑 completed）
- [ ] 派工前提错配实例沉淀（类 20 系列）+ CLAUDE.md 锚点段更新

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>
