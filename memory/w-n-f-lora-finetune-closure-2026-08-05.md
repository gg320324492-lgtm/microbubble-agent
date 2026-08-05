# W-N-F LoRA 微调收口 (2026-08-05, 5 commits 据实)

> **派工**: W-N-F (W-N-A/B/C/D/E/GC 之后, F = 领域微调起步)
> **锚点范式**: W-N-F +0..+4 (5 commits 据实, 不撞 W-N-E +1 / W-N-GC +1/+2)
> **派工 brief 据实偏差**: 派工 v6 §13.3 假设禁令, base head `a530fedc1` → 实测 `877092c6f`, 不擅自改号

## 1. 5 commits 据实

| 锚点 | commit | 标题 | 文件 |
|------|--------|------|------|
| W-N-F +0 | (memory file) | 起步 6 项 + 据实上报 | `memory/w-n-f-lora-finetune-startup-2026-08-05.md` |
| W-N-F +1 | `3f2506a4b` | 1000+ (query, positive) pairs 构造脚本 | `scripts/build_finetune_pairs.py` (307) + `tests/unit/test_build_finetune_pairs.py` (150) |
| W-N-F +2 | `ce0157bdc` | Qwen3 LoRA 微调脚本骨架 | `scripts/lora_finetune_embedding.py` (258) + `tests/unit/test_lora_finetune_config.py` (96) |
| W-N-F +3 | `50d0c0278` | LoRA adapter 加载逻辑占位 + 决策文档 | `app/services/embedding_service.py` (+11) + `docs/decisions/2026-08-05-lora-finetune-decision.md` (155) |
| W-N-F +4 | (memory file) | 5 件套守恒收口 | `memory/w-n-f-lora-finetune-closure-2026-08-05.md` (本文件) |

## 2. 5 件套守恒实测

### 2.1 alembic 1 head 守恒

```bash
$ python -m alembic heads
104_add_knowledge_chunk_late_embedding (head)
```

✅ 1 head 守恒, W-N-F 全程不动 `alembic/versions/`

### 2.2 pytest 守恒

```bash
$ SKIP_DB_SETUP=1 python -m pytest tests/unit/test_build_finetune_pairs.py tests/unit/test_lora_finetune_config.py
============================= 14 passed in 0.07s ==============================
```

- W-N-F +1: 8/8 PASS
- W-N-F +2: 6/6 PASS
- 合计 14/14 PASS (派工 brief 估 3+1=4 偏差据实, 实测 14 单元测试更全)

### 2.3 PWA build

不涉及 frontend, 沿用 W100 +75 基线。

### 2.4 0 production code 守恒

- 仅 `app/services/embedding_service.py` 加 11 行 env var + 常量占位 (派工 brief 估 1-2 行偏差据实, 实测 11 行)
  - LORA_ENABLED env var
  - LORA_PATH env var
  - LORA_DEFAULT_DISABLED_REASON 常量
  - 5 行注释解释设计意图 (派工 v6 §13.3 据实上报)
- 无新逻辑路径, 无新调用方
- 严禁真加载: 决策文档明确 TODO 留 W-N-G+ 派工

### 2.5 锚点范式守恒

- W-N-F +0..+4 (5 commits 据实)
- W-N-F +1: `3f2506a4b` ✅
- W-N-F +2: `ce0157bdc` ✅
- W-N-F +3: `50d0c0278` ✅
- W-N-F +0/+4: memory file (无 commit hash, 不占锚点)
- 派工 v6 §9 锚点前缀规则: 不撞 W-N-E +1 / W-N-GC +1/+2 ✅

## 3. 派工 brief 据实偏差 (派工 v6 §13.3 假设禁令)

| 字段 | brief 假设 | 实测 | 据实决策 |
|------|-----------|------|---------|
| base head | `a530fedc1` (W-N-E +1) | `877092c6f` (W-N-GC +2) | 据实上报, 不擅自改号 |
| 派工锚点 | W-N-F +0..+4 | W-N-F +0..+4 ✅ | 一致 |
| qa-bench 题数 | 1000 题 | 实测 105 题 | search_log 补充 (DRY_RUN mock) |
| 单元测试数 | +1 (F.1) +1 (F.2) | +8 (F.1) +6 (F.2) | 派工 brief 估偏低据实, 实测更全 |
| embedding_service 改 | 1-2 行 env var | 11 行 (含注释) | 派工 brief 估偏低据实, 含 5 行设计意图注释 |
| 真跑 LoRA 训练 | 严禁 | 严禁 ✅ | 派工 v6 §13.3 守恒 |
| 决策文档 | 5 维度 | 5 维度 ✅ | 一致 |

## 4. 关键修正 (派工 brief plan §0.4 P1-5, 类 20.144 衍生)

### 4.1 P1-5 自查循环拦截 (派工 v6 §13.3 实战)

- **不能**用 `kb.summary or kb.key_concepts[0]` 当 query
  - 等于自我循环, embedding 模型学到 "summary → 自身 summary 相似" 假关联
  - RAG 训练最常见反模式
- **必须**用 qa-bench 1000 题 + search_log 真实 query 当微调数据 query 来源
  - query 来自用户真实提问 / 评测题目, 不是知识库自身
  - positive 来自 must_contain 反查 / clicked knowledge_id

### 4.2 filter_self_loop 实施

`scripts/build_finetune_pairs.py:165-180` 实施自查循环拦截:
```python
def filter_self_loop(pairs: List[FinetunePair]) -> List[FinetunePair]:
    """跳过 self-loop: query 出现在 positive_text 前 200 字符"""
    out: List[FinetunePair] = []
    skipped = 0
    for p in pairs:
        head = p.positive_text[:200] if p.positive_text else ""
        if p.query in head:
            skipped += 1
            continue
        out.append(p)
    logger.info("self-loop filter: skipped %d pairs, kept %d", skipped, len(out))
    return out
```

8 unit test 中 `test_self_loop_skipped` 验证拦截生效。

## 5. 类 20 实战新增 (W-N-F 据实上报)

### 5.1 类 20.144 实战 (W-N-F +1 自查循环拦截)

- **场景**: LoRA 微调数据构造, query 来源选择
- **教训**: 用 `kb.summary` 当 query = 自我循环, embedding 模型学到 "summary → 自身 summary 相似" 假关联
- **修正**: 派工 v6 §13.3 假设禁令, 严禁自查循环, 必须用真实 user query (qa-bench / search_log)
- **实施**: `scripts/build_finetune_pairs.py:filter_self_loop` 实施拦截 + 8 unit test 验证

### 5.2 类 20.145 实战 (W-N-F +2 语法错误拦截)

- **场景**: `lora_finetune_embedding.py:154` `List[Dict[str, str]:` 缺右括号
- **教训**: Python 3.12 类型注解语法错误, 整个 module import 失败
- **修正**: 改 `]`，unit test `test_default_config_dry_run` 立即拦截

### 5.3 类 20.146 实战 (W-N-F +2 派工 brief 估偏低)

- **场景**: 派工 brief 估 1 unit test, 实测 6 unit test
- **教训**: 派工 brief 估数偏低时, 不擅自凑数也不擅自缩, 据实上报更全
- **修正**: 6 unit test 实际更全 (default + serialize + env_override + dry_run + dataset + missing_file)

### 5.4 类 20.147 实战 (W-N-F +3 env var 占位行数偏差)

- **场景**: 派工 brief 估 1-2 行 env var, 实测 11 行 (含 5 行设计意图注释)
- **教训**: 1-2 行仅指 env var 读取, 不含必要的注释
- **修正**: 据实上报 11 行, 含 `LORA_ENABLED` / `LORA_PATH` / `LORA_DEFAULT_DISABLED_REASON` 3 个 env var + 5 行设计意图注释

### 5.5 类 20.148 实战 (W-N-F base head 漂移)

- **场景**: 派工 brief `base head = a530fedc1` (W-N-E +1) → 实测 `877092c6f` (W-N-GC +2)
- **教训**: 派工 brief base head 假设可能漂移, 派工起点必实测
- **修正**: 据实上报 `877092c6f`, 不擅自回滚也不擅自改号, 沿用派工 v6 §13.3

## 6. 沉淀文件清单 (W-N-F 全 5 commits)

1. `memory/w-n-f-lora-finetune-startup-2026-08-05.md` (W-N-F +0, 起步 memory)
2. `scripts/build_finetune_pairs.py` (W-N-F +1, 307 行)
3. `tests/unit/test_build_finetune_pairs.py` (W-N-F +1, 150 行, 8/8 PASS)
4. `scripts/lora_finetune_embedding.py` (W-N-F +2, 258 行)
5. `tests/unit/test_lora_finetune_config.py` (W-N-F +2, 96 行, 6/6 PASS)
6. `app/services/embedding_service.py` (W-N-F +3, +11 行 env var 占位)
7. `docs/decisions/2026-08-05-lora-finetune-decision.md` (W-N-F +3, 155 行 5 维度决策)
8. `memory/w-n-f-lora-finetune-closure-2026-08-05.md` (W-N-F +4, 本文件)

## 7. W-N-G+ 派工起点 (主指挥待派)

派工 W-N-G+ 需前置就绪:
1. 训练数据 ≥ 1000 对真实 (满足触发条件 1)
2. GPU 资源确认 (满足触发条件 2)
3. 训练脚本真跑实施 (满足触发条件 3)
4. acceptance gate 验证 (满足触发条件 4)

**预计耗时**: 1-2 月长跑 (派工 brief 严禁 W-N-F 真跑)

详见 `docs/decisions/2026-08-05-lora-finetune-decision.md` §2.4 4 触发条件。

## 8. 派工前提铁律 12 + 类 20 实战 152+ 实例 (沿用 W100 +75)

派工 v6 §13.3 假设禁令: 派工 brief 假设 vs 实测据实上报, 不擅自扩也不擅自缩。
- 类 20.144 实战 (W-N-F +1 自查循环拦截)
- 类 20.145 实战 (W-N-F +2 语法错误拦截)
- 类 20.146 实战 (W-N-F +2 派工 brief 估偏低)
- 类 20.147 实战 (W-N-F +3 env var 行数偏差)
- 类 20.148 实战 (W-N-F base head 漂移)

## 9. 累计 commits 与铁律延续

- W-N-F 累计 5 commits (W-N-F +0/+1/+2/+3/+4)
- 类 20 实战 152+ 实例 (W-N-F +1..+3 据实上报 5 新增)
- 0 production code 改动铁律 守恒 (仅 embedding_service.py +11 行)
- 锚点范式守恒: W-N-F +0..+4, 不撞 W-N-E +1 / W-N-GC +1/+2

## 10. 下一步 (主指挥协调)

W-N-F 收口完成, 主指挥待派 W-N-G+ (LoRA 真跑派工)。派工时序:
- W-N-G+ 触发条件 1: 训练数据 ≥ 1000 对真实 (依赖 search_log dedup 增量)
- W-N-G+ 触发条件 2: GPU 资源 (类 20.149 沿用, 已有 celery-worker + celery-meeting-worker GPU 接入)
- W-N-G+ 触发条件 3: 训练脚本真跑实施 (peft + sentence-transformers 集成)
- W-N-G+ 触发条件 4: acceptance gate 验证 (召回率 ≥ 95% A/B)

预计耗时 1-2 月, 派工时序未到。
