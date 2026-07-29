# MicroBubble Agent RAG 系统总览 (PR10 W96 沉淀版)

> 来源: `C:\Users\pc\.claude\plans\rag-quirky-otter.md` v1.1 (2026-07-30) — RAG 工业级大改造 10 PR 系列收口文档
> 派工: PR10 (W96 +0 → +10, C 清理 + D 收口混合), 锚点范式 W88-W97 系列
> 配套: [RUNBOOK.md](./RUNBOOK.md) · [SCHEMAS.md](./SCHEMAS.md) · [ROADMAP.md](./ROADMAP.md) · [RISKS.md](./RISKS.md) · [EVAL.md](./EVAL.md) · [CHANGELOG.md](./CHANGELOG.md) · [FAQ.md](./FAQ.md) · [CHECKLIST.md](./CHECKLIST.md)

---

## 1. RAG 概述

MicroBubble Agent 的 RAG（Retrieval-Augmented Generation）体系服务于 20 人微纳米气泡课题组的知识大脑:

- **入库链**: `knowledge_service.py:63-371` `_run_analyze_and_embed` + `analyze_knowledge_task`（LLM 分析 → embedding → pgvector 落库 → 自动关联）
- **召回链**: `hybrid_retriever.py:25-104` `HybridRetriever.retrieve`（向量 + BM25 + 图谱 三路混合 + RRF 归一化）
- **合成链**: `knowledge_qa_service.py` RAG 问答（检索 → 阈值分类 → LLM 合成 → 来源引用）
- **进化链**: `auto_research_service.py` 自主研究（空白检测 → 联网搜索 → 提取 → 入库）
- **模型**: `Qwen/Qwen3-Embedding-0.6B` 1024d（instruction-tuned, query 侧 prefix `QUERY_PROMPT_ZH`）+ pgvector HNSW

改造目标: 升级到**工业级、可观测、可评估、长期可维护**的体系, 同时严格守住 CLAUDE.md §3 0 production code 改动铁律、alembic 串单链、派工 v10/v11 纪律。

## 2. 9 大缺口（改造动因）

| # | 缺口 | 量化证据 | 主责 PR |
|---|------|---------|--------|
| 1 | 嵌入不一致（3 档截断: 6000/无/500） | `embedding_recalc.py:145` vs `embedding_service.py:131` vs `knowledge_service.py:842/878` | PR1 |
| 2 | 无 chunking（单条平均 2605B, 超 6000 字符不可复现） | Knowledge 表 288 条单列 HNSW | PR2 |
| 3 | BM25 N 次全量重建 | `BM25Service.add_document` 每次全量 `_tokenize + BM25L` | PR3 |
| 4 | PG 全文索引缺失（OOV 必漏召回） | `chat_history_service.py:8` "MVP 阶段避免过度设计" | PR3 |
| 5 | query prefix 永不生效 | `embedding_prompts.py:16` 已写好, `embedding_service.py:151` `to_thread` 只透传 2 个位置参数 | PR1 |
| 6 | RAGEvaluator 零调用（4 RAGAS 指标已实现无 caller） | `rag_evaluator.py` 全文 | PR5 |
| 7 | SearchLog 前端未通 | `search_log.py:50-101` 埋点完整, 前端未消费 | PR6 |
| 8 | qa-bench 只测 Agent PASS 不测召回率/忠实度 | R8 200 题 93.5% | PR5 |
| 9 | 无统一 observability（召回耗时无按路分解） | 无 grafana 面板 | PR7 |

## 3. 10 PR 路线图

| PR | 锚点区间 | 标题 | 类型 | alembic | 前端 | 关键门禁 |
|----|---------|------|------|--------|------|---------|
| PR1 | W88 +0→+7 | 嵌入一致化 + query prefix 生效 | B | 否 | 否 | L2 ≤ 1e-4; for_query ≥ 80% |
| PR2 | W88 +8→+21 | knowledge_chunk 子表 + parent-child | B | 088 | 否 | chunk ∈ [1.5x, 6x]; P95 ≤ 80ms |
| PR3 | W89 +0→+16 | BM25 增量 + pg_trgm + tsvector | B | 089 | 否 | 1000 条 P95 ≤ 30s; GIN ≤ 120s |
| PR4 | W90 +0→+14 | HybridRetriever 召回侧量化 | B | 否 | 否 | 四路权重可配; synonym ≥ 200 |
| PR5 | W91 +0→+18 | RAGEvaluator 真召回率激活 | B | 090 | 是 | NDCG@10 ≥ 0.65, MRR ≥ 0.55 |
| PR6 | W92 +0→+12 | SearchLog 前端接通 | B | 否 | 是 | ≥ 7 维; 回收率 ≥ 30% |
| PR7 | W93 +0→+14 | 全链路 observability | B | 否 | 否 | grafana ≥ 6 面板; P99 ≤ 200ms |
| PR8 | W94 +0→+20 | 知识图谱深度联动 | B | 091 | 否 | 实体链 hit ≥ 25%; 实体 ≥ 5000 |
| PR9 | W95 +0→+16 | auto-research 升级 | B | 否 | 否 | 入 KB ≥ 70%; 去重 ≥ 95% |
| PR10 | W96 +0→+10 | docs/deploy/eval 三件套沉淀 | C/D | 否 | 否 | README ≥ 12 节; 7 件套 schema; v11 落库 |

依赖关系严格串行: PR1 → PR2 → … → PR10。**禁止并行 alembic 派工**。详细时间线见 [ROADMAP.md](./ROADMAP.md)。

## 4. 评估框架（10 件套）

| # | 评估项 | 存在形式 | 阈值 |
|---|--------|---------|------|
| 1 | alembic 1 head verify | `scripts/verify_alembic_chain.sh` | heads = 1 |
| 2 | pgvector HNSW 性能 | `tests/perf/test_pgvector_hnsw.py` | 10w 向量 P95 ≤ 50ms |
| 3 | 三路召回对比 | `tests/perf/test_recall_three_ways.py` | hit@10 ≥ 0.5 且差 ≤ 10pp |
| 4 | 端到端 PASS rate | `tests/qa-bench/run_bench.py --r8` | ≥ 96%（R8 200 题） |
| 5 | 真 RAG 召回率 | `tests/rag/test_recall_quality.py`（PR5） | NDCG@10 ≥ 0.65, MRR ≥ 0.55 |
| 6 | RAG 忠实度 LLM-as-judge | `tests/rag/test_faithfulness.py`（PR5） | 引用准确率 ≥ 0.85 |
| 7 | SearchLog 回收率 | grafana + SQL 视图 | 点击/曝光 ≥ 30% |
| 8 | 回归基线 | `tests/regression/test_anchor_baseline.py` | 0 failure |
| 9 | 0 production code 守恒 | `scripts/check_production_code_diff.sh` | 老核心 diff = 0 |
| 10 | 锚点范式守恒 | `scripts/check_anchor_paradigm.sh` | W88..W97 +N 锚点全出现 |

实操细节见 [EVAL.md](./EVAL.md)。

## 5. 风险

10 项风险（R1 嵌入不一致 / R2 chunking 漂移 / R3 reranker 失活 / R4 GIN 阻塞 / R5 打分偏置 / R6 用户接受度 / R7 alembic 并行 / R8 chunk 表爆炸 / R9 评测集偏差 / R10 auto-research 误入）及缓解策略, 完整详解见 [RISKS.md](./RISKS.md)。高危三项: R1（截断统一 + L2 校验）、R2（FK 100% + 孤儿巡检）、R7（段 1 必填 down_revision + 派工前 `python -m alembic heads`）。

## 6. 部署

每个含 alembic 的 PR（PR2/3/5/8）部署必做:

```bash
# 1. cp 迁移 + 清 __pycache__（CLAUDE.md 752 行铁律）
docker cp alembic/versions/0XX_*.py microbubble-agent-app-1:/app/alembic/versions/
docker exec -e SKIP_DB_SETUP=1 microbubble-agent-app-1 rm -rf /app/alembic/versions/__pycache__
docker exec microbubble-agent-app-1 alembic upgrade head
# 2. 重启后端
docker compose restart app celery-worker
# 3. verify 1 head
```

部署文档第 0 节必含 alembic chain 风险段。完整步骤 + 排错见 [RUNBOOK.md](./RUNBOOK.md)。

## 7. 回滚

- **无 alembic PR**（PR1/4/6/7/9/10）: `git revert <merge_commit>` 单 commit 撤销。
- **含 alembic PR**（PR2/3/5/8）: 先 `alembic downgrade -1`, 再 `git revert`, 再 verify 1 head。
- **紧急短路**: PR1 提供 `EMBEDDING_POLICY_DISABLED=1` 环境变量直接短路 policy 返回原文。
- **90% acceptance gate**（声纹范式复用）: 任何 embedding 变更前跑跨库回归, 不达标自动 rollback。

详见 [RUNBOOK.md](./RUNBOOK.md) §回滚。

## 8. 派工范式

- 全系列使用**派工 v10**（`docs/w72-prompt-paradigm-v10-2026-07-27.md`）段 0-9 必填; PR10 起升级 **v11**（`docs/w72-prompt-paradigm-v11-2027-04.md`, 本 PR 落库, v10 补 6 项）。
- 每 PR 一个 agent 独立 worktree + 分支（`chore/w8x-rag-prN-*`）, agent 不主动 merge/push 到 main。
- commit message 必含锚点范式数字 `[PRn W8x +N]` + Co-Authored-By。
- 据实上报铁律（W82/W84）: 禁止凑锚点、纸面 PASS、脑补 head; 主指挥核对发现"凑"必打回。
- 派工 v11 检查单模板见 [CHECKLIST.md](./CHECKLIST.md)。

## 9. 铁律速查

| 铁律 | 来源 | 一句话 |
|------|------|--------|
| 0 production code 改动 | CLAUDE.md §3 | 老核心 diff = 0, 例外必批（PR2/3/5/8 alembic 例外已批） |
| alembic 串单链 | CLAUDE.md §alembic | 段 1 必填 down_revision, merge 后 verify 1 head |
| `python -m alembic` | plan v1.1 | Windows Git Bash 直跑 `alembic` Permission denied |
| pytest 必 --ignore | plan v1.1 | `--ignore=tests/test_w79_commercial_private_deployment_e2e.py` |
| `npm run build` 唯一合法 | CLAUDE.md 2026-07-11 | `vite build` 直跑必坏 PWA（manifest 410） |
| QUERY_PROMPT_ZH 常量固化 | `embedding_prompts.py` | 改 prefix = 全量 re-embed |
| 测试 importorskip 守护 | plan §3.7 | 本机无 sentence_transformers 不崩 |
| 据实上报 | W82/W84 | 真实执行命令粘贴输出, 禁止"应该/大概/估计" |
| 22/22 PASS e2e 模式 | W85 B-1 | 每 PR e2e 必须全数字化断言 |
| 必复用资产 | plan §6 | 入库/召回/埋点样板禁止另起炉灶 |

## 10. Changelog

10 PR 逐条 changelog 汇总见 [CHANGELOG.md](./CHANGELOG.md)。主仓 `CHANGELOG.md` 同步一行摘要。

## 11. 联系方式

- **主指挥**: 课题组 Agent 系统维护者（CLAUDE.md 主指挥协调范式）
- **派工通道**: Claude Code 主会话派 PR agent（worktree 隔离）
- **问题反馈**: 主仓 issue / `memory/` 沉淀 / 派工 v11 段 5 反馈循环
- **文档位置**: `docs/rag/`（本目录 9 文件）+ `C:\Users\pc\.claude\plans\rag-quirky-otter.md`（原始 plan）

## 12. FAQ

常见问题（为什么 query prefix 一直没生效 / 为什么不能改 MATCH_THRESHOLD 式常量 / 为什么 chunking 用子表不改老表 / 本机没装 sentence_transformers 怎么跑测试 / rolldown panic 怎么办 等）见 [FAQ.md](./FAQ.md)。

---

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>
