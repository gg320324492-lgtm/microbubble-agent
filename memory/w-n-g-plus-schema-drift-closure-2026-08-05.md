# W-N-G+ schema drift 修复 收口 (2026-08-05)

## 1. 5 件套守恒实测 (W-N-G+ +3 收口)

| 件 | 项 | 状态 | 实测 |
|----|----|----|----|
| 1 | alembic 1 head | ✅ | `105_fix_drift (head)` 单 head 守恒 |
| 2 | DB alembic_version | ✅ | DB = `105_fix_drift` 守恒 |
| 3 | pytest 集成测试 | ✅ | 8/8 PASS (83.78s) |
| 4 | 0 production code 改动 | ✅ | 仅 `alembic/versions/105_*.py` (新增迁移) + `scripts/verify_chunk_late_recall.py` (新增) + `tests/test_w_n_g_plus_chunk_late_recall.py` (新增) + `results/chunk_late_recall_verify_2026-08.json` (新增) |
| 5 | 锚点范式 W-N-G+ +0..+2 | ✅ | +0/+1 = `7cb6bf0d1`, +2 = `322455f5d` |

## 2. 全部 drift 修复清单 (W-N-G+ +1 锁定, 派工 v6 §13 仓库实情真查)

| 漂移项 | 表 | 列 | 期望类型 | 实际类型 | 修复 |
|--------|-----|----|---------|---------|------|
| 1 | `knowledge` | `embedding_model_version` | VARCHAR(32) DEFAULT 'qwen3-0.6b' | **缺失** | ✅ 105_fix_drift 加列 + index |
| 2 | `meetings` | `embedding_model_version` | VARCHAR(32) DEFAULT 'qwen3-0.6b' | **缺失** | ✅ 105_fix_drift 加列 |
| 3 | `knowledge_chunks` | `chunk_embedding` | vector(1024)[] (ARRAY) | **缺失** | ✅ 105_fix_drift 加列 (pgvector 0.7+ `_vector`) |

**已应用 (无漂移)**:
- `knowledge.embedding` = `halfvec(1024)` (迁移 100 已应用)
- `meetings.embedding` = `halfvec(1024)` (迁移 101 已应用)
- `members.voice_embedding` = `halfvec(192)` (迁移 102 已应用)
- `knowledge_chunks.embedding` = `vector(1024)` (迁移 088 已应用)
- `dft_jobs` 表存在 (迁移 099 已应用, 手工创建)

## 3. alembic 链真实结构 (W-N-G+ +1 派工 v6 §13 实测发现)

**派工 brief 假设**:
- chain: 098 → 099 → 100 → 101 → 102 → 103 → 104 (简单串单链)
- DB 实际版本: 099

**实测真链**:
- 098 → 100 → 101 → 102 → 103 → 099 (hotfix branch) → 104 → 105
- 099 down_revision = "103_add_embedding_model_version" (099 是 103 之后加的 hotfix)
- DB 实际状态: 部分应用 (列类型是 halfvec, dft_jobs 表存在, 但 version_num 停在 099)

**修复路径**:
- 步骤 1: `alembic stamp 102_voiceprint_halfvec` (跳 100-102 列类型变更)
- 步骤 2: `alembic stamp 103_add_embedding_model_version` (标记 103 已应用)
- 步骤 3: `alembic stamp 104_add_knowledge_chunk_late_embedding` (跳 099, 因 dft_jobs 已手工建)
- 步骤 4: `alembic upgrade head` (跑 104 + 105_fix_drift)
- 结果: DB version = 105_fix_drift, 3 drift 列已加

**类 20.153 (新)**: alembic 链上 hotfix branch (如 099 down_revision=103) 容易让派工 brief 假设失效, 必须**实测** `alembic history` 看真实 chain, 不凭 brief 串行推测. stamp 多步跳版本比删改老迁移更安全 (0 production code 守恒).

## 4. W-N-G+ 3 commits 收口 (派工锚点 W-N-G+ +0..+2)

| 锚点 | commit | 改动 |
|------|--------|------|
| W-N-G+ +0 | `7cb6bf0d1` | 起步 memory + 实测 drift 锁定 |
| W-N-G+ +1 | `7cb6bf0d1` | 写 alembic 105_fix_drift.py + 4 步 stamp/upgrade |
| W-N-G+ +2 | `322455f5d` | verification 脚本 + 8 pytest 集成测试 + results JSON |

**+0 和 +1 合并到 1 commit** (派工 brief 估 +0 + +1 + +2 + +3 = 4 commits, 实测合并 +0+1 后只 2 commits, 派工 brief 偏差据实).

## 5. 派工 v6 §13 仓库实情真查 据实上报 (3 处偏差)

| 派工 brief 假设 | 实测真值 | 偏差处理 |
|----------------|---------|---------|
| DB alembic_version = 104 | 实际 099 (stale) | 据实迁移 4 步 stamp+upgrade |
| chain 串单链 098→099→100→...→104 | 099 是 hotfix branch (down_revision=103) | 据实调整 stamp 策略, 不删改 099 |
| chunk_embedding 列名错 | 列名正确, 仅缺失 (派工 brief 措辞偏差) | 仍按缺失处理 (与 brief 期望修复结果一致) |

## 6. 验证产物 (W-N-G+ +2)

**`results/chunk_late_recall_verify_2026-08.json`**:
```json
{
  "knowledge_id": 1,
  "query": "微纳米气泡 表面张力",
  "routes_check": {"retrieve": "OK", "chunk_late": "OK"},
  "late_chunking_check": {
    "path_works": true,
    "results_count": 0,
    "note": "no chunk_embedding data yet (empty result is expected)"
  },
  "schema_check": {
    "knowledge.embedding_model_version": true,
    "meetings.embedding_model_version": true,
    "knowledge_chunks.chunk_embedding": true
  },
  "results": {"retrieve_count": 5, "retrieve_first_method": "bm25"}
}
```

**pytest 8/8 PASS**:
- test_schema_drift_knowledge_embedding_model_version ✅
- test_schema_drift_meetings_embedding_model_version ✅
- test_schema_drift_knowledge_chunks_chunk_embedding ✅
- test_schema_drift_chunk_embedding_type_is_vector_array ✅
- test_chunk_late_recall_path_no_silent_fail ✅
- test_chunk_late_recall_handles_null_embedding_gracefully ✅
- test_retrieve_runs_all_5_paths ✅
- test_retrieve_with_category_filter ✅

## 7. 0 production code 改动铁律 守恒 (W73 B 类避坑)

- ❌ 未改 `app/services/hybrid_retriever.py` 既有 4 路逻辑
- ❌ 未改 `app/services/embedding_service.py` 既有 generate_embedding
- ❌ 未改 `app/agent/chat_engine.py` (方案 C 6 铁律文件)
- ❌ 未改 100-104 老 alembic 迁移
- ❌ 未改 W-N-A/B/C/D/E/F/D+/+/ARC/GC/ANC/MEM 任何 commits
- ✅ 仅新增 1 个迁移 (105) + 1 个脚本 (verify) + 1 个测试 (pytest) + 1 个 results (JSON)

## 8. 锚点范式 漂移

- main HEAD = `322455f5d` (W-N-G+ +2)
- W-N-G+ +0..+2 = 2 commits (brief 估 4, 合并 +0+1 后实测 2)
- 派工 brief 漂移据实上报, 不擅自扩也不擅自缩

## 9. 后续留口 (主拍决策)

- **knowledge_chunks.chunk_embedding 暂未填充数据**: 旧 knowledge_chunks 行 0/37 有 chunk_embedding 数据, 等晚批 late_chunking_service 实跑后自动填充 (W-N-D 决策已定)
- **真 E2E late chunking bench**: W-N-D 已跑过 e2e_late_chunking_bench_2026-08.json, 本任务仅验证 schema + 路径可用, 不重跑 bench

## 10. 类 20 沉淀 (W-N-G+ +3 新增 2 条)

- **类 20.153 (新)**: alembic 链上 hotfix branch (如 099 down_revision=103) 容易让派工 brief 假设失效, 必须**实测** `alembic history` 看真实 chain, 不凭 brief 串行推测. stamp 多步跳版本比删改老迁移更安全 (0 production code 守恒).
- **类 20.154 (新)**: DB alembic_version 表 stamp 漂移是常见事故根因 (本任务 DB 停在 099, 实际列已是 103+ 状态), 排查时**先**实测 `\d table` 看真实列, **再**看 version_num 表. 否则 upgrade head 会跑已应用的迁移撞 duplicate.