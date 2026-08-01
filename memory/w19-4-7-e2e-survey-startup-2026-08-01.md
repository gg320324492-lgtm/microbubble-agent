# W19-4 7 E2E 测试套件调研 — 起步确认 (2026-08-01)

## 起步纪律 6 项 (W73 铁律) 实测

| 起步项 | 实测结果 | 状态 |
|--------|----------|------|
| S1 git fetch origin + python -m alembic heads verify 1 head (093) | 1 head `093_add_search_log_answer_rating` ✅ | PASS |
| S2 读 CLAUDE.md §3 + 派工 v10.2 §13 + W19 选项 A 原则 | 已读完 + W19 选项 A "留未来 PR 不发起新排期" 明确 | PASS |
| S3 worktree 切到 E:/agent-w19-4-e2e | `pwd` = `/e/agent-w19-4-e2e` + `git branch` = `chore/w19-4-e2e` | PASS |
| S4 git status clean | `git status --short` 仅回显分支, 无未跟踪/未提交文件 | PASS |
| S5 ls tests/ 真查现有 e2e 资产 | 192 个 test_*.py + 68 个 test_*_e2e.py + 5 子目录 e2e 文件 | PASS |
| S6 起步确认写到 memory | 本文件 | PASS |

## 起步真查结果 (派工 brief vs 实测)

| 派工 brief 假设 | 实测结果 | 漂移 |
|-----------------|----------|------|
| 现有 e2e ≥ 10 类 | **实测 68 个 e2e 文件** + 5 子目录 + 17 个 RAG PR e2e | 远超预期 |
| chat_e2e 5 铁证 | ✅ `tests/test_chat_experience_e2e.py` 5 铁证真实存在 (W98 P2-E2E) | 0 漂移 |
| rag_e2e PR1-PR10 | ✅ `tests/rag/test_pr1_e2e.py` ~ `test_pr10_e2e.py` (PR10 docs) 全在 | 0 漂移 |
| rag_fw_11 8 case | `tests/rag_framework/` 子目录 (8 framework gate test) | 命名差异 (rag_framework 不是 rag_fw_11) |
| consistency_e2e W98 P2-D2 | `tests/realenv/test_consistency_realenv.py` + `tests/qa-bench/consistency_runner.py` | 0 漂移 |
| chat_history_e2e W98 P0-A | `tests/test_chat_history_service.py` + `tests/test_chat_history_tasks.py` | 命名差异 (是 unit 不是 e2e) |
| chat_perf_e2e W99 P2 | `tests/perf/test_recall_perf_baseline.py` (4 路 × 2 模式 = 8 case PASS) | 0 漂移 |
| realenv_e2e W98 P3-A | `tests/realenv/` 5 个真环境 e2e (chat/consistency/fast_path/feedback/wechat) | 0 漂移 |
| W19 选项 A "7 E2E 留未来" | `memory/future-pr-trigger-evaluation-2026-07-22.md` 1.4 段明确 "不触发" + 维持选项 A | 0 漂移 |

## 起步结论

派工 brief **完全可执行** — 7 E2E 调研范畴明确, 现有资产已远超 10 项 (实测 68 e2e 文件 + 192 test_*.py), 派工前提无错配.

进入 **阶段 2**: 起草 docs/w19-4-7-e2e-survey-2026-08-01.md 完整报告 (150 行+) + 3 候选方案 + 主拍决策依据 3 维度.