# W100-RAG-3 Query Intent 分类派工起步 (2026-08-02)

> **派工前提 (实测, 非台账)**:
> - base ref: `a03ab87ecefec64eb678e09b2ce6969f7f1ea1b6` (origin/main HEAD, W99-RAG-2 收口后)
> - 本地 HEAD: `a03ab87ec` (与 origin/main 同步, 工作树干净)
> - worktree: `worktree-agent-w100-rag-3` @ `E:\microbubble-agent\.claude\worktrees\w100-rag-3`
> - alembic HEAD: `095_add_rag_citation_metrics` (W100-RAG-3 不动 schema)
> - 派工 plan: `C:\Users\pc\.claude\plans\plan-spicy-raccoon.md` 模块 3 段
> - 派工 brief v4.1 6 必读段: 全遵守

## 派工 plan 偏差据实 (类 20.123)

| 偏差项 | 派工 plan 假设 | 实测 | 处理 |
|--------|---------------|------|------|
| LLMAnalysisService 接口 | "line 170 单例" | 只有 `analyze_content` 一个方法, 单例在 line 170 | 沿用 (本任务没用到) |
| query_translator 现有方法 | plan 没列 | 实测 5 个: `multi_query / hyde / decompose / translate / expand_and_search` | 全部沿用 (未来 PR 可串联 intent → translate) |
| INTENT_FALLBACK 默认值 | 未明文 (派工 brief 隐含) | `INTENT_FALLBACK = "factual"` (默认最常见) | 沿用 + 文档明示 |

## 派工 brief v4.1 段 0.1-0.6 实测

- **段 0.1 base ref 实测**: `a03ab87ec` ✅ (不照抄 plan 写的 `63aeb4c37` / `2ebf8f1d5` / `d07b07e93` 等落后值)
- **段 0.2 分支与 hash 实测**: worktree 分支 `worktree-agent-w100-rag-3` ✅
- **段 0.3 套件路径存在性探测**: `app/rag/intent_classifier.py` `app/rag/intent_router.py` `tests/rag/` 实测不存在 ✅ (待新增)
- **段 0.4 merge-base 假阳性拦截**: 沿用 `git rev-list --count` ✅
- **段 0.5 收官验证 6 步**: 本任务 alembic skip (不动 schema) ✅
- **段 0.6 调研标"推断"必先实测**: 派工 plan 偏差 2 处已据实上报 ✅

## 派工前提铁律 + 类 20 沉淀

- **类 20.115 实战 (派工 v6 §13.3 假设禁令)**: 实施前必 Read `llm_analysis_service.py` 真实接口 (line 170 单例 vs analyze_content 1 方法)
- **类 20.121-122 (W99-RAG-1)**: 沿用 cache hook best-effort 静默降级 + cache key 多租户隔离
- **类 20.123 (新)**: 派工 plan 偏差据实 (本任务 2 处)
- **类 20.124 (W99-RAG-2)**: 沿用 citation hook 不破坏返回类型
- **类 20.125 (新, W100-RAG-3)**: intent 分类必 5 类 + 失败回退 INTENT_FALLBACK
- **类 20.126 (新, W100-RAG-3)**: intent 路由 weights 配置化 (module-level dict 不硬编码)
- **派工 v11 段 9**: 锚点前缀 `W100-RAG-3` 防冲突

## 件 4 三门控 (派工前提铁律)

- **门控 A**: `app/services/knowledge_service.py` def diff = 0 ✅
- **门控 B**: `app/services/hybrid_retriever.py` def diff = 0 ✅ (intent hook 只 body 追加, 不改签名)
- **门控 C**: `app/services/rag_evaluator.py` def diff = 0 ✅

## 5 件套守恒预期

1. alembic: 1 head `095` (本任务不动) ✅
2. pytest: 25 (单测) + 22 (e2e) + 132 (W99-RAG-1/2 回归) = 179/179 PASS 预期
3. PWA build: 本任务不涉及 frontend
4. 0 production code: 件 4 三门控实测 = 0
5. 锚点范式: 派工 brief 估 +6 commits, 实测 ≥ 6 (本任务: 1 起步 + 1 intent_classifier + 1 intent_router + 1 hybrid hook + 1 config + 1 test + 1 docs = 6+)

## W100-RAG-3 派工顺序

1. **commit 1**: feat(rag/intent): intent_classifier.py 新增 (本文件)
2. **commit 2**: feat(rag/intent): intent_router.py 新增
3. **commit 3**: feat(rag/intent): hybrid_retriever 入口加 intent hook (件 4 门控 B 守恒)
4. **commit 4**: feat(rag/intent): config 新增 INTENT_CLASSIFIER_ENABLED + INTENT_FALLBACK
5. **commit 5**: test(rag/intent): 单测 25 + e2e 22 (含 5 类 intent 路由测试)
6. **commit 6**: docs(rag/intent): runbook + memory 沉淀

## 派工纪律 (沿用 CLAUDE.md 已落库)

1. **派工 v6 §13.3 假设禁令**: 不要假设 LLM client 怎么实例化 — Read 源码
2. **类 20.115 模式**: commit + 报告主指挥, 不自己 merge
3. **0 production code 守恒**: 件 4 三门控实测 = 0
4. **类 20.123 派工 plan 偏差据实**: 2 处已据实上报, 不擅自扩不擅自缩
5. **commit message 用 W100-RAG-3 前缀**: 防止锚点编号冲突 (派工 v11 段 9)
6. **本任务不动 schema**: 无 alembic 步骤
