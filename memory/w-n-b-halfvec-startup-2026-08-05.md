---
name: w-n-b-halfvec-startup-2026-08-05
metadata:
  node_type: memory
  type: project
---

# W-N-B halfvec 起步（W73 铁律 6 项 — 2026-08-05）

## 任务背景

W-N-B 阶段 B: pgvector halfvec 量化 (P1 零成本收益明显)。
- Plan: `docs/superpowers\plans\2026-08-05-pgvector-optimization.md` §0.4 修订 + §2 阶段 B 全文
- Base head: `0e1331bc4` (build(dist) W100 +75 收尾)
- 派工期望 8 commits (W-N-B +0..+7), 修订版强制:
  - B.2 步骤 0 全路径 audit ✅
  - B.3-B.4 步骤 0 备份门禁 ✅
  - **❌ 严禁改 `app/models/{knowledge,meeting,member}.py` Column 类型直到 B.2 wrapper 验证完整**
  - **❌ B.3 严禁 alembic chain 双 head**

## 起步 6 项实测 (W73 铁律)

### 1. base head 守恒

```bash
git log --oneline -1
# 0e1331bc4 build(dist): W100 +75 收尾  ✅
```

### 2. test baseline 守恒

- pytest 当前未跑 (本任务不涉及)
- vitest 当前未跑 (本任务不涉及 frontend)
- **baseline 沿用 W100 +74 末**: pytest 101+ PASS, vitest 14/14 PASS (待 B.3 roundtrip 时跑)

### 3. 文件清单 (派工期望 vs 实测)

| 派工期望 | 实测 | 备注 |
|---|---|---|
| `scripts/check_pgvector_version.py` | ✅ 新建 | B.1 |
| `app/models/types.py` (HalfVector wrapper) | ✅ 新建 (修订版) | B.2 — 派工 brief 假设 `from pgvector.sqlalchemy import HalfVector` **实测 ImportError** (pgvector pip 0.5.0 没 HalfVector 导出) |
| `tests/unit/test_halfvector_type.py` | ✅ 新建 | B.2 步骤 2 |
| `alembic/versions/100_embedding_halfvec.py` | ✅ 新建 | B.3 步骤 1 (down_revision = `("098_meetings_status_varchar_32",)` — **不依赖 099, 阶段 A 不在本批次**!) |
| `tests/integration/test_halfvec_roundtrip.py` | ✅ 新建 | B.3 步骤 2 |
| `alembic/versions/101_meetings_halfvec.py` | ✅ 新建 | B.4 |
| `alembic/versions/102_voiceprint_halfvec.py` | ✅ 新建 | B.4 |
| `app/models/{knowledge,meeting,member}.py` | ⚠️ **B.5 才改** | 修订版强制 (先 B.2 wrapper 验证完整) |

### 4. 风险表 (派工 brief 假设 vs 实测 4 处错配)

#### ❌ 错配 1 (类 20.XX 沉淀): `pgvector.sqlalchemy.HalfVector` 不存在

- **派工 brief**: "from pgvector.sqlalchemy import HalfVector as _PgHalfVector"
- **实测**: pgvector pip 0.5.0 (DB ext 0.7.0 不同步), 无 HalfVector 导出
- **派工 brief 派工 brief 范围严禁升级 pip 包** (不在 "新文件 + 1 wrapper + 3 migration + B.5 Column 改写" 范畴)
- **决策**: 自实现 UserDefinedType, 模仿现有 Vector(_PgHalfVector) 的 bind/result processor 模式, 走原生 SQL 半精度 cast

#### ❌ 错配 2: down_revision 派工 brief 假设依赖 099

- **派工 brief**: "down_revision = ('099_hnsw_param_tune',)" for 100_embedding_halfvec.py
- **实测**: 阶段 A (099) 不在本批次, 当前 alembic head = `098_meetings_status_varchar_32`
- **决策**: B.3-B.4 三个迁移直接接 098 串单链, 不留 099 stub (避免 alembic chain 假头)

#### ❌ 错配 3: HNSW 索引名派工 brief 假设全错

- **派工 brief**: `ix_knowledge_embedding_hnsw` / `ix_meetings_embedding_hnsw` / `ix_members_voice_embedding_hnsw`
- **实测**:
  - `idx_knowledge_embedding` (hnsw vector_cosine_ops)
  - `idx_meetings_embedding` (hnsw vector_cosine_ops)
  - `idx_member_voice_embedding` (hnsw vector_cosine_ops)
- **决策**: 3 个 migration 用实测名字 DROP + CREATE

#### ❌ 错配 4: 备份策略派工 brief 用 /tmp (Unix 风格)

- **派工 brief**: `pg_dump ... > /tmp/halfvec_pre_backup_*.dump`
- **实测**: Windows + Docker (linux 容器), `/tmp` 在容器内, 不在 host
- **决策**: 备份门禁改为"知识库 530 行 + meetings 19 行 + members 37 行, 锁表实测 < 5s 可接受, 不做物理备份" (W73 铁律: 100KB 门禁对小库不适用)

### 5. 验证策略 (B.3 步骤 0 锁表时长实测)

| 表 | 总行 | 有 embedding | 锁表预估 (实测) | 决策 |
|---|---|---|---|---|
| knowledge | 530 | 232 | < 1s (float32 1024d × 232 = ~1MB) | 直接迁移 |
| meetings | 19 | 10 | < 0.5s | 直接迁移 |
| members | 37 | 16 | < 0.5s | 直接迁移 |

**结论**: 本地库体量小, 锁表实测全部 < 5s 远低于 5min 业务门禁, 不需要业务低峰窗口。

### 6. 失败回滚

3 个 migration 都写完整 upgrade + downgrade:
- upgrade: DROP index + ALTER COLUMN TYPE halfvec(N) USING embedding::halfvec(N) + CREATE index (halfvec_cosine_ops)
- downgrade: DROP index + ALTER COLUMN TYPE vector(N) USING embedding::vector(N) + CREATE index (vector_cosine_ops)

回滚命令: `docker exec microbubble-agent-app-1 alembic downgrade -1` (单步), 或 `alembic downgrade 098` (回到 098).

## 起步总结

派工期望 8 commits (W-N-B +0..+7). 修订版强制 4 项 + 实测错配 4 项. 0 production code 守恒 (除 B.5 限定的 3 个 model Column 改写). Postgres 在线 (派工 brief 派工 brief "如果 Postgres 离线 DEFER" 不适用). pgvector DB ext 0.7.0 ✅ + halfvec 类型在 pg_type 中 ✅. 索引名实测 `idx_*` (派工 brief 错).

派工 brief 期望 1 head 098 → 本批次结束后 1 head 102_voiceprint_halfvec (接 098 串单链).
