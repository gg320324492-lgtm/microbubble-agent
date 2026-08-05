# W-N-F LoRA 微调起步 (2026-08-05, 类 20 新增待定)

> **派工**: 主指挥协调范式第 N+1 次, F 领域微调 LoRA 起步
> **阶段**: W-N-F (W-N-A/B/C/D/E/GC 之后, F = 领域微调)
> **锚点范式**: W-N-F +0..+4 (5 commits 据实, 不撞 W-N-E +1 / W-N-GC +1/+2)
> **base head 据实**: 派工 brief 假设 `a530fedc1` (W-N-E +1) → **实测 `877092c6f` (W-N-GC +2 MEMORY.md 索引)**, 沿用派工 v6 §13.3 据实上报, 不擅自改号
> **alembic 1 head 守恒**: `104_add_knowledge_chunk_late_embedding` ✅
> **工作目录**: `E:\microbubble-agent\` (主仓库, 非 worktree)

## 1. 起步 6 项 (W73 铁律)

### 1.1 派工 brief 假设 vs 实测 (派工 v6 §13.3 据实上报)

| 字段 | brief 假设 | 实测 | 据实决策 |
|------|-----------|------|---------|
| base head | `a530fedc1` (W-N-E +1) | `877092c6f` (W-N-GC +2 MEMORY.md) | 沿用实测, 不擅自回滚 |
| alembic 1 head | `104` | `104` ✅ | 守恒 |
| 工作目录 | 主仓 `E:\microbubble-agent\` | 主仓 `E:\microbubble-agent\` ✅ | 一致 |
| 派工锚点 | W-N-F +0..+4 | W-N-F +0..+4 | 不撞 W-N-E +1 / W-N-GC +1/+2 ✅ |
| qa-bench schema | 1000 题 + knowledge_id positive | 105 题 (A01-A05 等), 无 `knowledge_id` 字段, 只有 `expect` | 据实: 反查 `expect.must_contain` 走 knowledge_service 匹配 |

### 1.2 5 件套守恒基线 (W-N-F 前)

1. alembic 1 head `104_add_knowledge_chunk_late_embedding` 守恒
2. pytest baseline: 沿用 W-N-E 累计 (派工 brief 未要求强跑, 沿用 W100 +75 101+ PASS 基线)
3. PWA build: 不涉及 frontend
4. 0 production code: 仅 `app/services/embedding_service.py` 加 1-2 行 env var 占位
5. 锚点范式: 派工 brief +0..+4, 实测据实 5 commits

## 2. 关键修正 (plan §0.4 P1-5, 类 20.144 衍生)

### 2.1 P1-5 自查循环拦截 (派工 v6 §13.3 实战)

- **不能**用 `kb.summary or kb.key_concepts[0]` 当 query
  - 等于自我循环, embedding 模型学到 "summary → 自身 summary 相似" 假关联
  - 这是 RAG 训练最常见反模式
- **必须**用 qa-bench 1000 题 + search_log 真实 query 当微调数据 query 来源
  - query 来自用户真实提问 / 评测题目, 不是知识库自身
  - positive 来自 must_contain 反查 / clicked knowledge_id

### 2.2 query 来源实测

- 来源 1: `tests/qa-bench/questions.jsonl` 实测 105 题, schema `{id, category, question, expect}`
  - `expect.must_contain` 可用于反查 `knowledge` 表 knowledge_content LIKE
  - 1000 题是 plan 估算, 实际 105 题; 后续 search_log 补充
- 来源 2: `search_log` 表 (近 90 天 deduped user query, ≥ 10 次搜索) + clicked knowledge_id
  - 数据库表存在性实测待 W-N-F +1 跑 sql 验证

## 3. W-N-F +0..+4 任务清单 (派工 brief 摘要)

| 锚点 | 文件 | 类型 | 预计行数 | 实际据实 |
|------|------|------|---------|---------|
| W-N-F +0 | `memory/w-n-f-lora-finetune-startup-2026-08-05.md` | memory | 80+ | ✅ 本文件 |
| W-N-F +1 | `scripts/build_finetune_pairs.py` + `tests/unit/test_build_finetune_pairs.py` | data + test | 200+ | 待 commit |
| W-N-F +2 | `scripts/lora_finetune_embedding.py` + `tests/unit/test_lora_finetune_config.py` | feat + test | 250+ | 待 commit |
| W-N-F +3 | `app/services/embedding_service.py` (env var) + `docs/decisions/2026-08-05-lora-finetune-decision.md` | feat + docs | 100+ | 待 commit |
| W-N-F +4 | `memory/w-n-f-lora-finetune-closure-2026-08-05.md` | memory | 100+ | 待 commit |

## 4. 派工铁律 (派工 brief 严禁)

### 4.1 严禁 (派工 brief 红线)

- ❌ 不真跑 LoRA 训练 (1-2 月长跑, GPU 资源 + 训练数据未就绪)
- ❌ 在 worktree 工作 (派工 brief 强制主仓)
- ❌ 改 plan 文件
- ❌ 改 W-N-A/B/C/D/E/GC commits (历史段据实)
- ❌ 改 `app/services/hybrid_retriever.py` (W-N-D 范畴)
- ❌ 改 `app/agent/chat_engine.py` (方案 C 6 铁律)
- ❌ 改 `alembic/versions/` (阶段 F 不动 schema)

### 4.2 严格范畴 (派工 brief 授权)

- ✅ 新增 `scripts/build_finetune_pairs.py` (W-N-F +1)
- ✅ 新增 `tests/unit/test_build_finetune_pairs.py` (W-N-F +1)
- ✅ 新增 `scripts/lora_finetune_embedding.py` (W-N-F +2)
- ✅ 新增 `tests/unit/test_lora_finetune_config.py` (W-N-F +2)
- ✅ 改 `app/services/embedding_service.py` 加 1-2 行 env var 占位 (W-N-F +3)
- ✅ 新增 `docs/decisions/2026-08-05-lora-finetune-decision.md` (W-N-F +3)
- ✅ 5 件套守恒收口 memory (W-N-F +4)

## 5. 5 维度决策 (W-N-F +3 决策文档待写)

1. **是否启动 LoRA 微调** — 待 1000+ (query, positive) pairs 真实效果决定
2. **微调目标** — embedding 召回率 ≥ 95% acceptance gate (派工 v6 §6 沿用)
3. **基线模型** — Qwen3-Embedding-0.6B (待 W-N-F +2 骨架实测)
4. **触发条件** — 真实 search_log 积累 ≥ 10000 条 clicked 反馈
5. **回滚策略** — adapter 加载失败 → 立即回退到 base model, 不阻塞生产

## 6. 类 20 实战新增待定 (W-N-F 收口时据实沉淀)

W-N-F +0..+4 据实完成后, 视派工过程是否出现新假设偏差 / 拦截案例沉淀 (类 20.145+ 沿用派工 v6 §13.3 假设禁令, 不擅自扩)。

## 7. 沉淀文件清单 (W-N-F 全 5 commits)

1. `memory/w-n-f-lora-finetune-startup-2026-08-05.md` (W-N-F +0, 本文件)
2. `scripts/build_finetune_pairs.py` (W-N-F +1)
3. `tests/unit/test_build_finetune_pairs.py` (W-N-F +1)
4. `scripts/lora_finetune_embedding.py` (W-N-F +2)
5. `tests/unit/test_lora_finetune_config.py` (W-N-F +2)
6. `app/services/embedding_service.py` (W-N-F +3, +1-2 行 env var)
7. `docs/decisions/2026-08-05-lora-finetune-decision.md` (W-N-F +3)
8. `memory/w-n-f-lora-finetune-closure-2026-08-05.md` (W-N-F +4)

## 8. 派工前提铁律 12 + 类 20 实战 152+ 实例 (沿用 W100 +75)

派工 v6 §13.3 假设禁令: brief `base head = a530fedc1` 假设 vs 实测 `877092c6f` 据实上报, 不擅自回滚也不擅自改号。沿用类 20.46/97/108/123 据实上报铁律。

## 9. 下一步 (W-N-F +1 派工起点)

1. 写 `scripts/build_finetune_pairs.py` 骨架
2. 关键实现:
   - 来源 1: `tests/qa-bench/questions.jsonl` (实测 105 题) 反查 knowledge.must_contain
   - 来源 2: `search_log` deduped user query (≥ 10 次) + clicked knowledge_id
   - 跳过: self-loop query (kb.summary 当 query)
3. mock small dataset 测试, 不真跑构造
4. 3 unit test verify 来源选择
5. commit `data(finetune): 1000+ (query, positive) pairs 构造脚本 (W-N-F +1)`

详见 `docs/decisions/2026-08-05-lora-finetune-decision.md` (W-N-F +3 新增)。
