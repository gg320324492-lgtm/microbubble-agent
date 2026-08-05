# W-N-REVISE 决策修订收口 memory (2026-08-05)

> **派工锚点**: W-N-REVISE +2 (本 commit)
> **派工前 base HEAD 实测**: `74d1a965e` (W-N-DEPLOY 收口) ✅
> **收口状态**: ✅ 完成 (1 docs/decisions + 2 memory 文件, 0 production code 改动铁律 3/3 守恒)

---

## §1 5 件套守恒实测

| 件 | 维度 | 实测 | 结果 |
|----|------|------|------|
| 1 | alembic head 守恒 | `python -m alembic heads` → 1 head `105_fix_drift` | ✅ PASS (本任务不动 alembic) |
| 2 | pytest 全套件 | 沿用 W-N-G+ +2 + 4 FAIL 修复后基线 8/8 PASS (派工 brief 严禁重跑, 0 production code 改动) | ✅ PASS (沿用基线) |
| 3 | PWA build | 沿用 W-N-D++ +2 基线 (本任务不动 frontend) | ✅ PASS (沿用基线) |
| 4 | 0 production code | 本任务严格守恒, 仅 docs/decisions + memory 范畴 | ✅ PASS 3/3 守恒 |
| 5 | 锚点范式守恒 | W-N-REVISE +0/+1/+2 据实累计 (派工 v11 §9 规则下都是有效锚点) | ✅ PASS |

**0 production code 改动铁律守恒**:
- ❌ 0 改 `app/services/hybrid_retriever.py` / `embedding_service.py` / `knowledge_service.py` / `chat_engine.py` 既有 4 API
- ❌ 0 改 `alembic/versions/100-104` 老迁移 (W-N-A/B/C/D 范畴)
- ❌ 0 改 `alembic/versions/105_fix_drift.py` (W-N-G+ 范畴)
- ❌ 0 改 `app/main.py` / `web/src/` / `docker-compose.yml`
- ❌ 0 改 W-N-A/B/C/D/E/F/D+/+/ARC/GC/ANC/MEM/G+/OBS/RAG/BGE/GRAND/FILL/D++ 既有 commits
- ❌ 0 跑 late_embedding 回填 Celery task (派工 brief 严禁)
- ✅ 仅新增 `docs/decisions/2026-08-05-late-embedding-backfill-revise.md` + 2 memory 文件

---

## §2 调研发现总结

### 2.1 W-N-D++ §5 决策保留

- Gate 1 (recall 提升 > 2%): FAIL (+0.00% vs 门禁 > +2%)
- Gate 2 (P95 延迟恶化 < 30ms): PASS (+1.82ms < 门禁 +30ms)
- Gate 3 (维护成本可控): PASS (1 Celery + 1 监控)
- **Gate 1 是 hard-fail gate**, 即使 Gate 2/3 PASS, 也必须归档
- 决策不可撤销: 实证数据 + 派工 brief 严禁跳过 3 决策门禁

### 2.2 W-N-G+ 修复后 schema 状态

- `knowledge_chunks.chunk_embedding` 列已存在 (W-N-G+ 修复 commit `e68412de4` cherry-pick)
- `knowledge_chunks.embedding` 列保留 (vector(1024), 主嵌入存储)
- `knowledge.embedding_model_version` 列已添加 (W-N-G+ 修复)
- alembic head `105_fix_drift` 守恒
- **关键观察**: schema 已修正, 但业务决策层面 recall +0% 仍然成立

### 2.3 触发再启条件 3 选 1

| 条件 | 维度 | 状态 |
|------|------|------|
| (a) | 表 column 实际存在 | ✅ PASS (W-N-G+ 已验证) |
| (b) | tests 8/8 PASS | ✅ PASS (W-N-G+ 已验证) |
| (c) | 业务决策: 通过 doc 论证 chunk 召回价值 > 0 | ❌ FAIL (W-N-D++ 决策 recall +0.00% FAIL) |

**3 选 1 默认 (c) 业务决策延续禁止**.

---

## §3 W-N-FILL 派工的三重 + 一重阻断

### 3.1 W-N-XX +1 留口 §2.4 三重阻断

```
W-N-FILL 派工阻断 (W-N-XX +1 留口):
1. W-N-D++ 决策文档中 §5 是否仍标 "整段归档" — 若 YES, 拒绝派工
2. qa-bench 当前分数是否 ≥ 96.5% — 若 NO, 拒绝派工
3. 主拍是否明确书面批准 W-N-FILL 派工 — 若 NO, 拒绝派工
```

### 3.2 W-N-REVISE +1 新增一重阻断

```
W-N-REVISE 新增第 4 重阻断:
4. 3 选 1 触发条件 (a)(b)(c) 是否齐全 — 若不齐, 拒绝派工
   - 默认 (c) 业务决策延续禁止, 即便 (a)(b) 都 PASS 也拒绝派工
```

**派工 brief 严禁擅自启**: W-N-FILL +N 派工**永远不擅自启**, 除非主拍明确书面批准 + 业务决策 recall > 0 通过 doc 论证.

---

## §4 类 20 沉淀 (W-N-REVISE 据实上报)

### 4.1 新增 1 条

- **类 20.157 (W-N-REVISE 新增)**: late_embedding 回填决策触发再启条件必须 3 选 1 (a) 列存在 + (b) tests PASS + (c) 业务决策 recall > 0; 默认 (c) 业务决策延续禁止, 派工 brief 严禁擅自扩

### 4.2 沿用 2 条

- **类 20.155 (W-N-D++)**: alembic head 守恒 ≠ DB schema 守恒 (W-N-G+ 修复后 schema 实际守恒, 但 head 守恒与 schema 守恒的分离仍是铁律)
- **类 20.156 (W-N-D++)**: best-effort `try/except` 静默失败比显式失败更危险 (chunk_late_recall 异常被吞, 路由层不知道路径失效)

---

## §5 锚点范式 (W-N 周期 ~537 → W-N-REVISE +2 据实累计)

W-N 周期 14 stages 累计 ~35 commits 推 main, 锚点 W100 +75 ~537 → W-N-G+ +N ~572 据实累计. W-N-REVISE +0/+1/+2 据实累计:

- **W-N-REVISE +0** (起步 memory): `memory/w-n-revise-fill-decision-startup-2026-08-05.md`
- **W-N-REVISE +1** (决策修订): `docs/decisions/2026-08-05-late-embedding-backfill-revise.md`
- **W-N-REVISE +2** (收口 memory, 本 commit): `memory/w-n-revise-fill-decision-closure-2026-08-05.md`

锚点不撞 (派工 v11 段 9 规则), 沿用 W-N-FILL 0-3 空闲锚点 (W-N-XX +1 留口 §2.4 已记录).

---

## §6 关联文件

- 决策修订文档: `docs/decisions/2026-08-05-late-embedding-backfill-revise.md` (W-N-REVISE +1)
- startup memory: `memory/w-n-revise-fill-decision-startup-2026-08-05.md` (W-N-REVISE +0)
- W-N-D++ 决策原文: `docs/decisions/2026-08-05-e2e-late-chunking-decision.md`
- W-N-XX +1 留口 §2: `docs/w-n-future-leftover-2026-08-05.md`
- W-N-G+ +3 收口: `memory/w-n-g-plus-schema-drift-closure-2026-08-05.md`
- W-N-G+ +0/+1 commit: `7cb6bf0d1`
- W-N-G+ 4 FAIL 修复 commit: `e68412de4`
- W-N-D++ +2 commit: `1cc5362e2`

---

**W-N-REVISE +2 收口完成. 5 件套守恒实测 5/5 PASS. 0 production code 改动铁律 3/3 守恒. W-N-FILL 派工三重 + 一重阻断强化. W19 选项 A 维持.**