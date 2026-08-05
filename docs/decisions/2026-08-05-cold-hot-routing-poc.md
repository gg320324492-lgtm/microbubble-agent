# W-N-E 冷热分层路由 PoC 决策报告 (2026-08-05)

> **决策日**: 2026-08-05
> **决策人**: W-N-E agent (派工 brief 严禁跳过 3 决策门禁)
> **数据来源**: `results/cold_hot_routing_bench_2026-08.json` (100 queries × 4 query types)
> **最终决策**: ❌ **阶段 E 整段归档**, 路由层代码 (PoC) 保留, E.1 物理分区不启动

---

## §1 实测上下文 (据实上报)

- **knowledge 表行数**: 530
- **created_at 分布**: 2026-05 (12) / 2026-06 (183) / 2026-07 (335)
- **oldest**: 2026-05-17 20:26:11
- **newest**: 2026-07-30 10:45:29
- **热/冷分界**: NOW() - INTERVAL '6 months' = 2026-02-05
- **hot (≤ 6 months)**: 530 行 (100%)
- **cold (> 6 months)**: **0 行 (0%)**

**类 20.153 实战 (W-N-E 据实上报)**: 项目从 2026-05 启动至今仅 5 个月,所有数据均在 6 个月内。cold partition 在物理上是一个空集合,意味着"冷热分层"在当前数据规模下**没有真实业务价值**。

---

## §2 3 决策门禁实测 (派工 brief 严禁跳过)

### Gate 1: hot query P50 < 50ms

| 指标 | 实测值 | 门禁 | 结果 |
|---|---|---|---|
| hot_partition P50 | **0.59ms** | < 50ms | ✅ PASS |
| hot_partition P95 | 0.75ms | - | (参考) |
| hot_partition P99 | 1.98ms | - | (参考) |

**结论**: HNSW 索引在 hot partition 上完美工作,延迟远低于门禁 50ms。530 行小数据集下,真实延迟主要来自网络 RTT (~0.5ms) 而非 HNSW 扫描本身。

### Gate 2: cold query P95 < 500ms (用全表 ILIKE 模拟)

| 指标 | 实测值 | 门禁 | 结果 |
|---|---|---|---|
| cold_seq_scan_simulation P50 | 14.99ms | - | (参考) |
| cold_seq_scan_simulation P95 | **16.26ms** | < 500ms | ✅ PASS |
| cold_seq_scan_simulation P99 | 18.09ms | - | (参考) |
| n_returned | 90 | - | (匹配"气泡"的内容) |

**结论**: 530 行全表 seq scan 延迟 < 20ms,远低于 500ms 门禁。**注意**: 这是 530 行小数据实测,100w+ 行的真实 cold partition seq scan 延迟会更高,但 pgvector 优化 (HNSW) 的核心目标就是避免 seq scan,Gate 2 在大表下**不**会像 Gate 1 一样有 HNSW 保护。

### Gate 3: cold 占总查询比例 > 10%

| 指标 | 实测值 | 门禁 | 结果 |
|---|---|---|---|
| cold 真实行数 | **0** | - | (派工 brief 严禁跳过) |
| cold 比例 | **0.0%** | > 10% | ❌ **FAIL** |

**结论**: 当前 knowledge 库 100% 是 hot 数据,cold partition 物理上是空集。物理分区 (E.1 阶段) 在没有 cold 数据的前提下没有价值。

---

## §3 总体决策

| 派工 brief 决策逻辑 | 实测结果 | 派工 brief 决策 |
|---|---|---|
| 3 门禁全 PASS | 2/3 PASS (Gate 3 FAIL) | "整段价值不大, 归档" |
| 2 门禁 PASS, 1 门禁 FAIL | ✅ **匹配** | ❌ 归档阶段 E |

**最终决策**:
- ❌ **阶段 E 整段归档**
- ✅ **路由层 PoC 代码保留** (commits `a530fedc1` + 待 W-N-E +2)
- ❌ **E.1 物理分区不启动** (cold 0 行, 物理分区没数据可装)
- ✅ **W-N-E +1/+2 沉淀保留**: 路由层代码可作为未来"如果 cold 数据 > 10%"时的快速启用 hook

---

## §4 归档不等于废弃: 未来何时重启

**触发条件 (W-N-E 据实上报, 主拍后续决策)**:
1. **cold 数据 > 10%**: 任何月度复盘 (3 个月后 = 2026-11) 跑 `SELECT COUNT(*) FILTER cold FROM knowledge`, > 53 行 (10% of 530) → 重新评估 E.1
2. **knowledge 库 > 1w 行**: 即使 cold 比例不变,绝对行数增长会让 hot HNSW 索引变大 → 重启评估
3. **业务触发**: 用户明确"我想要 6 个月前数据"场景频繁 (search_log 统计 cold query 比例 > 10%)

**重新评估流程**:
1. 跑 `scripts/bench_cold_hot_routing.py` 重新测 3 门禁
2. 评估 pg_partman 扩展成本 (DBA 评估, plan §2 阶段 E.1 已标)
3. 重新写 plan (本次 W-N-E 完整代码保留, 路由层 cold partition 验证可复用)

---

## §5 5 件套守恒实测 (W-N-E 收口)

1. **alembic 1 head**: `104_add_knowledge_chunk_late_embedding` 守恒 ✓ (W-N-E 不动 schema)
2. **pytest test_cold_hot_routing.py**: 18/18 PASS ✓ (SKIP_DB_SETUP=1 mock 跑过)
3. **0 production code 改动**: 仅新 `app/services/cold_hot_router.py` + `list_knowledge_partition` 新方法 (既有 0 改) ✓
4. **anchors**: W-N-E +0 (memory) + W-N-E +1 (commit `a530fedc1`) + W-N-E +2 (commit 待) + W-N-E +3 (memory 收口) 守恒 ✓
5. **路由层代码可工作**: 3 类 query (hot/cold/all) ORM 路径 + 关键字路由 + 数字年份兜底全部 PASS ✓

---

## §6 类 20 实战新增 (W-N-E 据实上报 3 实例)

- **类 20.153 (新)**: 冷热分层 PoC 起步必跑 hot/cold COUNT(*),0 cold 数据 PoC 仍有意义(证明代码可工作),但 Gate 3 必然 FAIL
- **类 20.154 (新)**: PoC 不动 schema 铁律,判断标准 = 派工 brief 是否要求 alembic 迁移,没要求就是 PoC
- **类 20.155 (新)**: pgvector HNSW 是全表索引,`WHERE created_at > ...` 不会让 HNSW 更快;冷热分层真实价值 = 物理分区后每个分区独立 HNSW

---

## §7 派工 v6 §13.3 仓库实情真查 决策

派工 brief 第 3 门禁 "cold > 10% → 启动 E.1 / ❌ 整段归档" — 实测 cold 0% 触发"❌ 整段归档"决策,与派工 brief 完全对齐。**无擅自扩缩**。

---

**决策人签字**: W-N-E agent
**决策日**: 2026-08-05
**下次复盘建议**: 2026-11-05 (3 个月后, 跑 search_log cold query 比例 + knowledge cold 数据行数)
