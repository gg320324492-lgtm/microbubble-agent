# W-N-REVISE 决策修订起步 memory (2026-08-05)

> **派工锚点**: W-N-REVISE +0 (本 commit)
> **派工前 base HEAD 实测**: `74d1a965e` (W-N-DEPLOY 收口) ✅
> **任务**: W-N-FILL 决策重审 — W-N-D++ §5 决策禁止 late_embedding 回填调研 + 写决策修订

---

## §1 派工来源 (主拍 W-N-REVISE 拍板)

**主拍决策理由**:
- W-N-FILL 决策 (W-N-XX +1 留口 §2.2 拦截) 默认沿用 W-N-D++ §5 "不创建 + 不执行"
- 但 W-N-G+ 4 FAIL 修复后, schema 已修正 (`chunk_embedding` 列已存在, commit `e68412de4` cherry-pick 105_fix_drift 自 `claude/w-n-g-plus-4fail-fix`)
- 派工 brief 严禁擅自扩, 但决策文档需据实刷新:
  - 触发再启条件 (a) 表 column 实际存在 (W-N-G+ 已验证)
  - 触发再启条件 (b) tests 8/8 PASS (W-N-G+ 已验证)
  - 触发再启条件 (c) 业务决策: 通过 doc 论证 chunk 召回价值 > 0 (W-N-D++ 决策 recall +0.00%)
- 修订后: 3 选 1, **默认 (c) 业务决策延续禁止**, 派工 brief 严禁擅自启

---

## §2 6 项起步 (W73 铁律)

1. **派工前 base HEAD 实测**: `git log --oneline -3` → `74d1a965e docs(deploy-status): W-N-DEPLOY 部署状态验证报告 + 起步 + 收口 (W-N-DEPLOY +0/+1/+2)` ✅
2. **W-N 周期 commits 现状**: `git log --oneline --all | grep -E "W-N-"` 共 18 commits (A/B/C/D/D+/D++/E/F/G+/OBS/RAG/BGE/GRAND/XX/ANS/DEPLOY/REVISE)
3. **派工锚点不撞**: W-N-REVISE +0/+1/+2 不撞历史 (REVISE 锚点空闲, 派工 v11 §9 规则下有效)
4. **下游 doc/memory 路径实测**:
   - `docs/decisions/2026-08-05-e2e-late-chunking-decision.md` 存在 (W-N-D++ +2 commit)
   - `docs/w-n-future-leftover-2026-08-05.md` 存在 (W-N-XX +1 commit)
   - 新写 `docs/decisions/2026-08-05-late-embedding-backfill-revise.md` 待 commit
5. **DB schema 实测**: `knowledge_chunks` 表列名 (`embedding` vector(1024) + `chunk_embedding` ARRAY) 均存在, alembic head `105_fix_drift` 守恒
6. **派工 v6 §13 仓库实情真查**: 当前 base HEAD ≠ W-N-XX +1 留口基线 `fbc11908e` (已演进 ~5 commits), 决策修订针对新 base

---

## §3 调研发现 (本任务沉淀)

### 3.1 W-N-G+ 4 FAIL 修复后 schema 验证

**W-N-G+ +0/+1 commit `7cb6bf0d1` 落地 105_fix_drift migration** (W-N-G+ 范畴), 加 `chunk_embedding` 列到 `knowledge_chunks` 表.

**W-N-G+ +N 修复 commit `e68412de4`** (cherry-pick 自 `claude/w-n-g-plus-4fail-fix` 分支):
- 4 FAIL 修复 (drift tests): `embedding_model_version` / `chunk_embedding` 列已添加
- 8/8 PASS 测试通过 (W-N-G+ 自报)

**实测 schema 状态** (本任务实测, 2026-08-05):
```
column_name   | data_type
--------------+-------------
id            | integer
knowledge_id  | integer
chunk_index   | integer
content       | text
embedding     | USER-DEFINED (vector(1024))
char_start    | integer
char_end      | integer
char_count    | integer
strategy      | character varying
chunk_metadata| jsonb
created_at    | timestamp without time zone
updated_at    | timestamp without time zone
chunk_embedding | ARRAY
alembic_version: 105_fix_drift
```

**关键观察**:
- `embedding` 列 (vector(1024)) 是**早期** schema, 用于主嵌入存储
- `chunk_embedding` 列 (ARRAY) 是 W-N-D 范畴后期添加的 late_embedding 预留列
- 两列**共存**, 不冲突, 但实际 chunk-level 嵌入从未真正写入 `chunk_embedding` (W-N-D++ §1 据实上报: recall +0%)
- alembic head `105_fix_drift` 守恒 (类 20.155: head 守恒 ≠ schema 守恒 → 修复后 schema 实际守恒)

### 3.2 W-N-D++ §5 决策保留语义

**W-N-D++ §5 决策原文** (`docs/decisions/2026-08-05-e2e-late-chunking-decision.md:108-117`):
- ❌ Gate 1 (recall 提升 > 2%): FAIL (+0% vs 门禁 > +2%)
- ✅ Gate 2 (P95 延迟恶化 < 30ms): PASS (+1.82ms < 门禁 +30ms)
- ✅ Gate 3 (维护成本可控): PASS (1 Celery + 1 监控)
- **Gate 1 是 hard-fail gate**, 即使 Gate 2/3 PASS, 也必须归档

**结论**: W-N-D++ §5 决策**不撤销**, recall +0% 的硬门禁继续生效.

### 3.3 W-N-XX §2 决策拦截条件 (留口)

W-N-XX +1 留口文档 §2.2 触发再启条件**两个任一**:
1. 修订 W-N-D++ 决策: 主拍重新评估 W-N-D++ 3 门禁结果
2. 新业务理由: 例如 qa-bench ≥ 96.5% / 生产 `knowledge_chunks.late_embedding` 空缺成为召回瓶颈 / 新 hybrid_retriever 路由需要 late chunking 数据

**本任务调研**: 两个条件都**未达**:
- 条件 (1): W-N-D++ §5 决策**不修订**, recall 硬门禁生效
- 条件 (2): qa-bench 当前分数未达 96.5% (沿用 W-N-D++ 决策) + 生产 recall 未触发瓶颈

---

## §4 派工范围

**严格守恒 0 production code 改动铁律**:
- ❌ 0 改 `app/services/hybrid_retriever.py` / `embedding_service.py` / `knowledge_service.py` / `chat_engine.py` 既有 4 API
- ❌ 0 改 `alembic/versions/100-104` 老迁移
- ❌ 0 改 `app/main.py` / `web/src/` / `docker-compose.yml`
- ❌ 0 改 W-N-A/B/C/D/E/F/D+/+/ARC/GC/ANC/MEM/G+/OBS/RAG/BGE/GRAND/FILL/D++ 既有 commits
- ❌ 0 跑 late_embedding 回填 Celery task (派工 brief 严禁)
- ✅ 仅新增 `docs/decisions/2026-08-05-late-embedding-backfill-revise.md` + 2 memory 文件

---

## §5 锚点范式

- **W-N-REVISE +0** (本 commit): 起步 memory
- **W-N-REVISE +1**: 决策修订文档
- **W-N-REVISE +2**: 收口 memory + 5 件套守恒实测

锚点不撞 (派工 v11 段 9 规则), 沿用 W-N-FILL 0-3 空闲锚点 (W-N-XX +1 留口 §2.4 已记录).

---

## §6 关联文件

- 决策修订文档: `docs/decisions/2026-08-05-late-embedding-backfill-revise.md` (W-N-REVISE +1 commit)
- W-N-D++ 决策原文: `docs/decisions/2026-08-05-e2e-late-chunking-decision.md`
- W-N-XX +1 留口: `docs/w-n-future-leftover-2026-08-05.md` §2 W-N-FILL 拦截
- W-N-G+ +3 收口: `memory/w-n-g-plus-schema-drift-closure-2026-08-05.md`
- W-N-G+ 4 FAIL 修复 commit: `e68412de4`
- W-N-G+ +0/+1 commit: `7cb6bf0d1`
- W-N-D++ +2 commit: `1cc5362e2`

---

**W-N-REVISE +0 起步完成. W19 选项 A 维持. 派工锚点 W-N-REVISE +0/+1/+2 据实累计, 0 production code 守恒.**