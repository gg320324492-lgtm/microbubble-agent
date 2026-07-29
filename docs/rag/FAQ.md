# RAG 大改造 FAQ

> 常见问题速答。深入内容跳转对应文档: [README](./README.md) / [RUNBOOK](./RUNBOOK.md) / [SCHEMAS](./SCHEMAS.md) / [RISKS](./RISKS.md) / [EVAL](./EVAL.md)。

## Q1: 为什么 query prefix 写好了却一直没生效？

`embedding_prompts.py:16` 的 `QUERY_PROMPT_ZH` 早已写好, 但 `embedding_service.py:151` 的 `to_thread(generate_embedding_sync, text, for_query)` 只透传 2 个位置参数, `has_query_prompt` 永远默认 False → `build_embedding_prompt(True, False)` 恒返 None。**即便调用方改 `for_query=True` 也零效果**。PR1 §3.0 前置修复三处透传是本系列第一刀。

## Q2: 为什么不能直接改 QUERY_PROMPT_ZH 或截断常量？

prefix 是 embedding 模型输入的一部分, 向量空间与 prefix 强绑定 — 改内容 = 所有历史入库向量全部失效, 必须配套全量 re-embed。同理 `MAX_EMBED_INPUT_CHARS = 6000` 一旦发布即固化。这与声纹 `MATCH_THRESHOLD = 0.7` 不动铁律同源: **常量语义与数据绑定, 字面改数字 = 灾难**。

## Q3: 为什么 chunking 用子表而不改 Knowledge 老表？

CLAUDE.md §3 0 production code 铁律: 老表 schema (`app/models/knowledge.py`) 不破坏, 新功能走独立子表 `knowledge_chunk` (alembic 088, 主拍例外已批) + FK 关联。老召回路径可随时回退, chunk 路径灰度上线。

## Q4: 本机没装 sentence_transformers 怎么跑测试？

plan §3.7 三板斧: (1) 新逻辑落纯逻辑层（truncation/query/consistency 三 policy 只依赖标准库, 单测直接 import）(2) e2e 用 `unittest.mock` patch `model.encode` (3) 测试文件 `pytest.importorskip("sentence_transformers")` 守护 — 本机 SKIP, CI 真跑。**禁止**为了本机能跑去改 `embedding_service.py` 的模块级 import。

## Q5: `alembic heads` 报 Permission denied？

Windows Git Bash 直跑 `alembic` 的已知问题, 一律用 `python -m alembic heads`（plan v1.1 基线修正, 派工 v11 新增 1）。

## Q6: pytest 收集就报错怎么办？

两个已知 collection error: (1) `tests/test_w79_commercial_private_deployment_e2e.py` → 必加 `--ignore`（plan v1.1）(2) `tests/trivy/test_dockerfile_pinning.py` 与 `tests/sentry/` 同 basename import mismatch（W96 实测, 预先存在于 main, 待主指挥拍板改名）。新建测试文件先查 basename 唯一性。

## Q7: rolldown `Panic in async function` build 失败怎么办？

W96 PR10 实测: 主仓 `npm run build` 在 `compute_cross_chunk_links.rs:584` panic, 3 连重试均 panic（rolldown 1.1.5 上游 bug, 非本项目代码问题）。处理: `npm ci` 恢复 lockfile → 重试 → 仍败则据实上报 pre-existing FAIL, **不算 docs-only PR 的 FAIL, 也不得顺手改 web 配置**（0 production code）。同时注意: build 失败会删 tracked `web/dist` 文件, 必须 `git restore web/dist/`。

## Q8: worktree 里 npm run build 直接说找不到 vite？

worktree 不携带 `node_modules`（.gitignore）。docs-only PR 在主仓等价验证 build 基线 + 据实上报即可; 前端 PR 需在 worktree 内 `npm ci` 后再 build（派工 v11 新增 5 依赖基线自检）。

## Q9: 门禁数字（qa-bench ≥ 96% 等）达不到怎么办？

不达标即回滚本 PR, 不允许"下个 PR 再补"（EVAL.md 件 4）。月度时间线顺延 1 周期不可压缩（ROADMAP §2）。据实上报铁律: 禁止凑数、纸面 PASS、脑补 head。

## Q10: 10 个 PR 能并行派几个？

**一个都不能并行**。alembic 088→089→090→091 单链 + PR 间依赖严格串行（PR2 依赖 PR1 的 truncate 入口, PR4 依赖 PR3 的 tsvector 路, ...）。历史教训: 062/063 并行派工双头直接阻塞部署（CLAUDE.md 2026-07-24 铁律）。

## Q11: RAGEvaluator 已经实现了为什么还要 PR5？

`rag_evaluator.py` 4 RAGAS 指标**零调用**（缺口 6）— 实现了但没有 caller、没有 ground-truth、没有定时跑、没有报告表。PR5 的活是"激活": runner + 题库 + 夜跑 + `rag_eval_report` 表 + 前端面板。

## Q12: SearchLog 数据在哪, 为什么前端看不到？

后端埋点完整（`app/models/search_log.py:50-101` + `app/api/v1/analytics.py`）, 只是前端从未消费（缺口 7）。PR6 只做"接通", 禁止新写埋点框架（必复用资产纪律, plan §6）。

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>
