# W96 RAG PR10 grand closure（docs/deploy/eval 三件套沉淀, 2026-07-30）

> 派工: PR10 B-10（C 清理 + D 收口混合）。plan `rag-quirky-otter.md` v1.1 §10 + §11.2。
> 分支: `chore/w96-rag-pr10-docs-2026-07-30`, base = main `3a1ab24b3`（W86 mini-16, 锚点 338）。
> 锚点范式: **W96 +0 → +10, 11 commits 全落地**。0 production code 守恒（app/ diff = 0, alembic 0 改动, frontend 0 改动）。

## 交付物清单（据实）

| 锚点 | commit | 交付 |
|------|--------|------|
| W96 +0 | `08ae9d2b5` | `docs/rag/README.md`（12 节总览）+ `memory/w96-rag-pr10-start-2026-07-30.md` |
| W96 +1 | `872cf9fe7` | `docs/rag/ROADMAP.md`（PR1-10 时间线 + 月度里程碑 2026-08→2027-05） |
| W96 +2 | `3aa8b7153` | 主仓 `README.md` RAG 链接 + `ROADMAP.md` RAG 大改造时间线段 + `CHANGELOG.md` 10 PR 一行摘要 |
| W96 +3 | `38843032e` | `docs/rag/RUNBOOK.md`（alembic 第 0 节风险 + 部署/回滚 + 12 项排错速查） |
| W96 +4 | `ff0ba0fc7` | `docs/rag/SCHEMAS.md`（7 件套: truncation_policy / query_policy / consistency_check / hybrid_weight / synonym_dict / recall_observability / auto_research_v2） |
| W96 +5 | `7d55d5a48` | `tests/rag/test_pr10_docs_e2e.py`（23 case）+ `tests/rag/__init__.py` + `tests/rag/conftest.py`（no-op DB 覆盖） |
| W96 +6 | `5dacc76aa` | `docs/rag/RISKS.md`（R1-R10 详解 + 缓解 + 覆盖矩阵） |
| W96 +7 | `1931cc59b` | `docs/rag/EVAL.md`（10 件套评估框架实操 + 跑批节奏） |
| W96 +8 | `f2cc4f646` | `docs/rag/CHANGELOG.md`（10 PR 汇总: PR1-9 规划态 + PR10 据实） |
| W96 +9 | `bc2576576` | `docs/w72-prompt-paradigm-v11-2027-04.md`（v10 补 6 项）+ `docs/rag/CHECKLIST.md`（速查版） |
| W96 +10 | 本 commit | `docs/rag/FAQ.md`（12 问）+ 本 memory + 5 件套守恒验证 |

## 量化门禁实测

| 门禁 | 目标 | 实测 |
|------|------|------|
| README 节数 | ≥ 12 | 12 节（`^## ` grep, e2e case 10 断言 PASS） |
| 7 件套 schema | 完整 | 7/7（e2e case 12 断言 PASS） |
| 派工 v11 落库 | ≥ 6 项新增 | 6 项 "v11 新增"（e2e 断言 PASS） |
| e2e | 22/22 | **23/23 PASS**（brief 22, 实际 23 case, 超额 +1 据实上报） |
| docs/rag/ 文件数 | 9 | 9（README/RUNBOOK/SCHEMAS/ROADMAP/RISKS/EVAL/CHANGELOG/FAQ/CHECKLIST） |

## 5 件套守恒回报表（v11 新增 6 格式, 命令输出原文）

| 件 | 命令 | 实测输出 | 判定 |
|----|------|---------|------|
| 1 | `python -m alembic heads` | `087_add_knowledge_original_parent_id (head)` | ✅ 1 head |
| 2 | `python -m pytest tests/rag/test_pr10_docs_e2e.py -v` | `23 passed, 2 warnings in 0.21s` | ✅ 23/23 |
| 3 | `cd web && npm run build` | worktree 无 node_modules; 主仓等价验证: rolldown panic `compute_cross_chunk_links.rs:584`, 3 连重试均 panic（pre-existing, 详见下节据实上报） | ⚠️ pre-existing FAIL, 非本 PR 引入 |
| 4 | `git diff main -- app/ \| wc -l` | `0` | ✅ 0 production code |
| 5 | `git log --grep "W96 +" --oneline \| wc -l` | 11（+0..+10） | ✅ ≥ 11 |

## 据实上报（brief vs 实测偏差, 4 项）

1. **pytest baseline 偏差**: plan v1.1 记载 "2701 collected + 1 error (test_w79)"; W96 实测 **2860 collected + 1 error**, 且 error 变为 `tests/trivy/test_dockerfile_pinning.py` 与 `tests/sentry/test_dockerfile_pinning.py` 同 basename import mismatch（test_w79 已被修复）。预先存在于 main, 本任务 0 production code 不修, 待主指挥拍板（改唯一 basename 或测试目录加 `__init__.py`）。
2. **PWA build pre-existing FAIL**: worktree 无 `web/node_modules`（不随 worktree 携带）→ 主仓等价验证; 主仓 build 先暴露 `@sentry/vue` 未装（`npm install`/`npm ci` 后解决）, 再暴露 **rolldown 1.1.5 panic**（`compute_cross_chunk_links.rs:584`, 上游 bug, 3 连重试均败）。与本 PR 无关（本 PR 0 web 改动）。**副作用已处理**: build 失败删除了主仓 tracked `web/dist` 文件, 已 `git restore web/dist/` 恢复, 主仓 git status 干净（仅遗留 untracked `docs/rag-templates/` + `scripts/rag/`, 非本任务产物, 未动）。
3. **e2e case 数**: brief 写 22/22, 实际 23 case（9 参数化存在性 + 14 断言）, 超额 +1, 全 PASS。
4. **tests/rag/conftest.py 计划外新增**: 父级 `tests/conftest.py` 的 autouse `setup_db`（function-scope drop_all/create_all）需要真 PostgreSQL, 本机无 DB 时 docs e2e 全 ERROR ConnectionRefused。新增局部 no-op 覆盖（docs e2e 纯文件断言不需要 DB）, 已在文件 docstring 注明后续需 DB 的 tests/rag 测试应显式用 `db` fixture 不受影响。plan §11.2 未列此文件, 属实施必需最小新增, 据实上报。

## 派工前提错配沉淀（类 20 候选）

- **类 20 候选 A（同 basename 测试文件 collection error）**: 并行 batch 各自建 `tests/<topic>/test_dockerfile_pinning.py` 导致 import mismatch — 新建测试文件必查 `find tests -name "<basename>"` 唯一性（已写入派工 v11 新增 2 + FAQ Q6）。
- **类 20 候选 B（worktree 依赖基线缺失）**: worktree 不带 node_modules, brief 起步项 "cd web && npm run build" 在 worktree 内必败 — 依赖基线自检 + 主仓等价验证纪律（已写入派工 v11 新增 5 + FAQ Q8）。
- **类 20 候选 C（build 失败副作用删 tracked dist）**: 主仓 build 失败会先清 `web/dist` 再 panic, 留下 tracked 文件删除态 — build 验证后必查 `git status web/` 并 restore（已写入 FAQ Q7）。

## 待主指挥拍板

1. 合并 `chore/w96-rag-pr10-docs-2026-07-30`（11 commits）到 main。
2. trivy/sentry 同 basename collection error 修复派工（建议独立小修, 1 commit）。
3. rolldown panic 调研派工（升级/降级 rolldown 或上报 issue; 当前主仓 `npm run build` 不可用会阻塞下一个前端 PR 部署）。
4. 主仓 untracked `docs/rag-templates/` + `scripts/rag/` 归属确认（非本任务产物）。
5. 派工 v11 正式生效时点（v11 文档已落库, 按文档约定 merge 后生效）。

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>
