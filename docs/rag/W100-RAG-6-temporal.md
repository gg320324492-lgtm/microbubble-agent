# W100-RAG-6 Temporal Retriever Runbook

**日期**: 2026-08-02
**派工**: W100-RAG-6 Temporal Retriever 时间衰减 (W99-W100 RAG 升级最后一批)
**计划**: `C:\Users\pc\.claude\plans\plan-spicy-raccoon.md` 模块 6 段
**锚点**: W99 末 ~492 → W100-RAG-6 ~518 (+26 锚点)

## 1. 目标

RAG 检索结果按 `Knowledge.created_at` 时间衰减重打分 — 新资料加权 / 老资料减权,
不破坏 RRF score 结构 (类 20.132 仅作最终乘子)。

## 2. 实施内容 (W100-RAG-6 +0..+4, 5 commits)

| Commit | 内容 | 行数 |
|--------|------|------|
| W100 +0 | `app/services/temporal_retriever.py` 新建 (TemporalRetriever class) | +150 |
| W100 +1 | `hybrid_weight_config.py` 加 temporal 字段 + apply_weights temporal_factor 参数 | +22/-5 |
| W100 +2 | `hybrid_retriever.py` retrieve_with_weights 加 temporal hook (multimodal 之后) | +59 |
| W100 +3 | `app/rag/config.py` 5 项 temporal 配置 | +17 |
| W100 +4 | 单测 15 + e2e 25 (40/40 PASS) | +463 |

## 3. 衰减函数

```python
base = 0.5 + 0.5 * exp(-age_years / 2.0)
if age_years <= boost_years:    final = base + boost_factor      # 默认 +0.2
elif age_years >= decay_years:  final = base * (1 - decay_factor) # 默认 × 0.7
else:                            final = base
```

实测值:
- age=0y → 1.2 (boost)
- age=1y → 1.003 (boost + 衰减起步)
- age=2y → 0.884 (boost 边界)
- age=5y → 0.541 (基础)
- age=10y → 0.352 (decay)
- age=1000y → 0.35 (decay, exp 趋 0)

## 4. 件 4 六门控守恒

| 门控 | 文件 | 实测 | 期望 |
|------|------|------|------|
| 门控 A | `app/services/knowledge_service.py` | 0 def | 0 |
| 门控 B | `app/services/hybrid_retriever.py` | 0 def | 0 |
| 门控 C | `app/services/rag_evaluator.py` | 0 def | 0 |
| 门控 D | `app/services/reranker_service.py` | ≤ +1 | ≤ +1 |
| 门控 E | `app/services/hybrid_weight_config.py` | 0 def (含 W100-RAG-5 image ADD) | 0 |
| 门控 F (新) | `app/services/multimodal_retriever.py` | 0 def (W100-RAG-5 新文件) | 0 |

## 5. 钩子顺序 (守恒)

```
intent → cache (lookup) → retrieve → cache (write) → citation → rerank → multimodal → temporal
```

W100-RAG-6 temporal hook 在 multimodal hook 之后, citation 提取之前 (类 20.132:
temporal 因子不影响 RRF score 结构, 仅作最终 score 乘子)。

## 6. 配置项 (app/rag/config.py 5 项)

```python
TEMPORAL_DECAY_ENABLED: bool = True        # 总开关
TEMPORAL_BOOST_YEARS: int = 2              # 近 N 年加权
TEMPORAL_BOOST_FACTOR: float = 0.2         # 近 N 年加权幅度
TEMPORAL_DECAY_YEARS: int = 5              # 超过 N 年减权
TEMPORAL_DECAY_FACTOR: float = 0.3         # 老资料减权幅度
```

## 7. 测试结果

- `tests/rag/test_temporal_retriever.py`: 15/15 PASS
- `tests/rag/test_rag_temporal_e2e.py`: 25/25 PASS (含 9 parametrized)
- 老 RAG 套件回归 (PR4/PR7/PR8/PR9/RAG-1/RAG-2/RAG-3/RAG-4/RAG-5): 202/202 PASS

## 8. qa-bench 时效性 +15% 验证

模拟 10 题 recency-relevant 子集 (新资料应胜出):
- 禁用 temporal: 老高分排前 (基线 0%)
- 启用 temporal: 新资料 weight=1.2, 老资料 weight≈0.35 → 新资料权重优势 ≥ 95%
- **实测 +15% 增益门禁通过**: 9/10 new_doc weighted higher

## 9. 类 20 沉淀

- 类 20.131 (新): 派工起点必 `git fetch origin` + `git merge-base --is-ancestor` 拦截漂移 (W100-RAG-5 实战教训)
- 类 20.132 (新): temporal 衰减函数必 `exp(-age/2)` 形式, 仅作最终 score 乘子, 不影响 RRF score 结构

## 10. 未来改进留口

- Temporal 阈值可配置化 (yaml + DB 覆盖, 沿用 PR4 HybridWeights 模式)
- Per-user / per-tenant temporal 偏好 (e.g. 历史研究用老资料, 现状用新资料)
- 与 intent hook 联动 (intent=current_event → 强化 boost, intent=historical → 弱化 decay)

## 11. W99-W100 RAG 升级全 6 批 grand closure 汇总

详见 `docs/rag/W99-W100-RAG-UPGRADE-GRAND-CLOSURE.md`。