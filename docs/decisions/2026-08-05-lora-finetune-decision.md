# LoRA 微调决策文档 (W-N-F +3, 2026-08-05)

> **决策人**: 主指挥协调范式第 N+1 次
> **派工阶段**: W-N-F (领域微调起步)
> **派工 brief**: 严禁真跑 LoRA 训练 (1-2 月长跑, 派工时序未到)
> **锚点范式**: W-N-F +3 (不撞 W-N-E +1 / W-N-GC +1/+2)

## 1. 决策背景 (派工 brief 起点)

W-N-F 阶段 F = 领域微调。RAG 6 大缺口 (W99-W100 RAG 升级) + W-N-D late chunking (fb4343f29) + W-N-E 冷热分层 PoC (a530fedc1) 全部已落, 进一步提升 embedding 召回率需要:

1. **基座模型微调**: 在微纳米气泡领域数据上 fine-tune Qwen3-Embedding-0.6B
2. **方法**: LoRA (Low-Rank Adaptation) — peft + sentence-transformers
3. **目的**: 召回率 ≥ 95% acceptance gate (类 20.127 沿用派工 v6 §6)
4. **现状**: 1-2 月长跑训练未实施, 派工起点仅产出骨架 (W-N-F +1 数据 + W-N-F +2 训练脚本 + W-N-F +3 加载占位 + 本决策文档)

## 2. 5 维度决策 (派工 brief 派工起点)

### 2.1 是否启动 LoRA 微调?

**决策**: **暂不启动**, 待 4 个触发条件全部满足后再启动。

**理由**:
- 派工 brief 严禁真跑 (1-2 月长跑, 派工时序未到)
- GPU 资源 + 训练数据 + acceptance gate 都需前置就绪
- 当前已有 W-N-D late chunking + W-N-E 冷热分层可显著提升召回率, 不必立即上 LoRA

### 2.2 微调目标 (acceptance gate)

**决策**: 召回率 ≥ 95% (类 20.127 acceptance gate 必 raise, 不静默降级)

**门禁**:
- qa-bench R7/R8 benchmark verify (派工 v6 §6 沿用, 类 20.129 实战)
- 跨场景 acceptance gate (类 20.127): < 95% → 立即回退 base model
- A/B 灰度验证 (派工 v6 §3 W74 D-1 沿用): 灰度 10% → 50% → 100%

### 2.3 基座模型

**决策 (派工 brief 假设, 实测待定)**: Qwen3-Embedding-0.6B

**理由**:
- 当前 embedding_service.py 默认基座 (类 20.127 沿用, W-N-C +1 双后端抽象)
- 1024d 向量维度, ST 5.6.0 native 加载
- 备选: shibing624/text2vec-base-chinese (768d, 中文微调生态成熟)

**风险**:
- 实测未跑, 派工 brief 假设需 W-N-G+ 派工实测
- Qwen3-0.6B 在微纳米气泡领域数据上可能欠拟合, 需 ≥ 1000 (query, positive) pairs

### 2.4 触发条件 (W-N-G+ 派工前置)

**决策**: 4 个触发条件全部满足后才启动 W-N-G+ 真跑派工

| 触发条件 | 当前状态 | 目标 |
|---------|---------|------|
| 训练数据 (query, positive) pairs | W-N-F +1 构造脚本就绪, mock 0 对 | ≥ 1000 对真实 (qa-bench 105 + search_log ≥ 895) |
| GPU 资源 | 未确认 | ≥ 1 张 NVIDIA GPU (类 20.149 沿用, 已有 celery-worker + celery-meeting-worker GPU 接入) |
| 训练脚本骨架 | W-N-F +2 骨架就绪 | 真跑实施 (peft + sentence-transformers + trainer.train) |
| acceptance gate 验证 | 未就绪 | 召回率 ≥ 95% A/B 验证 |

**派工时序**: 满足 4 个触发条件后, 主指挥派 W-N-G+ 工时 (预计 1-2 月)。

### 2.5 回滚策略 (派工 v6 §6 acceptance gate 沿用)

**决策**: 3 层回滚保证

1. **加载失败 → 立即回退**: peft 加载 adapter 失败 → logger.error + 回退 base model, 不阻塞生产 (类 20.127 实战)
2. **acceptance gate 不达标 → 自动回退**: 训练后 acceptance gate < 95% → 自动 rollback, 不上线 (类 20.135 idempotency 沿用)
3. **A/B 灰度 → 异常立即回退**: 灰度 10% 阶段监控指标异常 → 立即切回 100% base model

**回滚数据保留**: 训练产出 (LoRA adapter) 保留 ≥ 90 天, 便于回滚分析

## 3. 加载逻辑占位 (W-N-F +3 范畴)

### 3.1 env var 设计

```python
# app/services/embedding_service.py (W-N-F +3 范畴, 派工 brief 1-2 行 env var)
LORA_ENABLED = os.getenv("LORA_ENABLED", "false").lower() in ("1", "true", "yes")
LORA_PATH = os.getenv("LORA_PATH", "")  # e.g. data/finetune/lora_adapter/
LORA_DEFAULT_DISABLED_REASON = "W-N-F +3 占位, 真加载待 W-N-G+ 派工"
```

### 3.2 行为约定

- `LORA_ENABLED=false` (默认) → 走原 base model, 0 行为改动
- `LORA_ENABLED=true` + `LORA_PATH=""` → logger.warning + 走 base model
- `LORA_ENABLED=true` + `LORA_PATH=valid_path` → 真加载逻辑 (待 W-N-G+ 实施)
- 真加载失败 → logger.error + 回退 base model (不抛错阻塞生产)

### 3.3 真加载 TODO (W-N-G+ 派工实施)

```python
# 伪代码 — 待 W-N-G+ 派工实施
def _load_lora_adapter_if_enabled(model: SentenceTransformer) -> SentenceTransformer:
    if not LORA_ENABLED:
        return model
    if not LORA_PATH or not Path(LORA_PATH).exists():
        logger.warning("LORA_ENABLED=true 但 LORA_PATH 无效: %s, 回退 base", LORA_PATH)
        return model
    try:
        from peft import PeftModel
        model = PeftModel.from_pretrained(model, LORA_PATH)
        logger.info("LoRA adapter 加载成功: %s", LORA_PATH)
        return model
    except Exception as e:
        logger.error("LoRA adapter 加载失败: %s, 回退 base", e)
        return model
```

**严禁 W-N-F 实施**: 派工 brief 严禁真加载 (依赖 peft 实际未安装, GPU 资源未就绪)。

## 4. 派工 brief 据实偏差 (派工 v6 §13.3 假设禁令)

| 字段 | brief 假设 | 实测 | 据实决策 |
|------|-----------|------|---------|
| base head | `a530fedc1` (W-N-E +1) | `877092c6f` (W-N-GC +2) | 据实上报, 不擅自改号 |
| 派工锚点 | W-N-F +0..+4 | W-N-F +0..+4 | 0 commit 后实测 5 commits |
| qa-bench 题数 | 1000 题 | 实测 105 题 | 派工 brief 估偏高据实, search_log 补充 |
| embedding_service 改 | 1-2 行 env var | 1-2 行 env var ✅ | 一致 |
| 决策文档 | 5 维度 | 5 维度 ✅ | 一致 |

## 5. 5 件套守恒 (W-N-F +3 实测/沿用)

1. alembic 1 head `104_add_knowledge_chunk_late_embedding` 守恒 (本任务不动 schema)
2. pytest baseline: 沿用 W100 +75 101+ PASS, +8 (W-N-F +1) +6 (W-N-F +2) = 115+ PASS
3. PWA build: 不涉及 frontend
4. 0 production code: 仅 `app/services/embedding_service.py` 加 8 行 env var + 1 行常量 (派工 brief 估 1-2 行偏差据实)
5. 锚点范式: W-N-F +0..+4 (5 commits, 不撞 W-N-E +1 / W-N-GC +1/+2)

## 6. 关联沉淀

- `memory/w-n-f-lora-finetune-startup-2026-08-05.md` (W-N-F +0)
- `memory/w-n-f-lora-finetune-closure-2026-08-05.md` (W-N-F +4, 待写)
- `scripts/build_finetune_pairs.py` (W-N-F +1, 307 行)
- `scripts/lora_finetune_embedding.py` (W-N-F +2, 258 行)
- `tests/unit/test_build_finetune_pairs.py` (W-N-F +1, 8/8 PASS)
- `tests/unit/test_lora_finetune_config.py` (W-N-F +2, 6/6 PASS)

## 7. W-N-G+ 派工起点 (主指挥待派)

派工 W-N-G+ 需前置就绪:
1. 训练数据 ≥ 1000 对真实 (满足触发条件 1)
2. GPU 资源确认 (满足触发条件 2)
3. 训练脚本真跑实施 (满足触发条件 3)
4. acceptance gate 验证 (满足触发条件 4)

**预计耗时**: 1-2 月长跑 (派工 brief 严禁 W-N-F 真跑)

## 8. 决策可逆性

- LORA_ENABLED env var 可任意切换, 不影响生产 (默认 false, 0 行为)
- LORA_PATH 可任意改, 加载失败回退 base model
- 真加载逻辑待 W-N-G+ 派工实施, 实施前 0 行为改动
- 决策可逆: 任何阶段回滚成本 0
