# W-N-G+ schema drift 修复 起步 (2026-08-05)

## 1. 派工 brief 锚定 (W73 铁律)

- 任务 ID: W-N-G+ schema drift 修复
- 锚点范式: W-N-G+ +0..+3
- 当前 main HEAD: `1cc5362e2` (feat(rag): W-N-D++ 端到端 late chunking 召回 bench + 决策归档)
- 当前 alembic code head: `104_add_knowledge_chunk_late_embedding`
- 当前 DB alembic_version: `099_add_dft_jobs` (stale!)
- DB 是否可达: ✅ `docker ps | grep db-1` Up 6 hours (healthy)
- 0 production code 改动铁律: 仅 `alembic/versions/105_*.py` + `scripts/verify_chunk_late_recall.py` + `tests/`

## 2. 派工起点必 fetch (类 20.131 沿用)

派工 brief: "W-N-D++ 报告关键发现 (alembic 104 vs DB drift)"
- 已 fetch: 当前 main HEAD = `1cc5362e2` 验证守恒
- 已 fetch: W-N-D++ +1/+2/+3 已合入 main, 含决策归档

## 3. 实测 DB schema drift (派工 v6 §13 仓库实情真查)

**关键发现**: DB alembic_version 停在 `099_add_dft_jobs`, 但 columns 实际状态**部分**应用了 100-102 (halfvec 类型转换).

| 表 | 列 | 期望 (alembic 100-104) | 实际 DB | 状态 |
|----|----|----|----|----|
| `knowledge` | `embedding` | `halfvec(1024)` (100) | `halfvec(1024)` | ✅ OK |
| `knowledge` | `embedding_model_version` | VARCHAR(32) (103) | **缺失** | ❌ drift |
| `meetings` | `embedding` | `halfvec(1024)` (101) | `halfvec(1024)` | ✅ OK |
| `meetings` | `embedding_model_version` | VARCHAR(32) (103) | **缺失** | ❌ drift |
| `members` | `voice_embedding` | `halfvec(192)` (102) | `halfvec(192)` | ✅ OK |
| `knowledge_chunks` | `embedding` | `vector(1024)` | `vector(1024)` | ✅ OK |
| `knowledge_chunks` | `chunk_embedding` | ARRAY(Vector(1024)) (104) | **缺失** | ❌ drift |

**3 个实际 drift**:
1. `knowledge.embedding_model_version` 缺失 (W-N-C 加的)
2. `meetings.embedding_model_version` 缺失 (W-N-C 加的)
3. `knowledge_chunks.chunk_embedding` 缺失 (W-N-D 加的 late-chunking 多向量)

**注意**: 派工 brief 说 "knowledge_chunks 列名错 `chunk_embedding` vs 实际 `embedding`" — **实测无矛盾**: `embedding` 列存在且一直叫 `embedding`, 派工希望新增的 `chunk_embedding` 才是缺失的. 不需要重命名.

**注意**: DB 已有数据 (knowledge=530 行, knowledge_chunks=37 行, meetings=19 行), 所以 103/104 的迁移必须用 `server_default` 或 nullable=True 兼容.

## 4. alembic 链状态

- code head: `104_add_knowledge_chunk_late_embedding`
- DB stamp: `099_add_dft_jobs`
- 直接跑 `alembic upgrade head` 会尝试跑 100/101/102 → 但 100/101/102 的列类型已经是 halfvec, 重复 ALTER 会报错或 no-op

**关键决策**: 不能简单 `alembic upgrade head`, 因为:
- 100/101/102 的列类型已被改 (via manual SQL by previous operators), 直接跑会冲突
- 必须**手动 stamp** 到 102 (跳过已应用 100-102), 然后**只跑 103 + 104**

## 5. 修复策略 (W-N-G+ +1)

**Step 1**: `alembic stamp 102_voiceprint_halfvec` 把 DB 版本戳更新到 102 (跳过 100/101/102 已应用的列)
**Step 2**: `alembic upgrade 104_add_knowledge_chunk_late_embedding` 跑 103 + 104 (3 个缺失列)
**Step 3**: 验证 + commit

**备选方案 (W-N-G+ +1 不修改既有 100-104, 写新迁移 105)**:
- 派工 brief 要求 "写 `alembic/versions/105_fix_drift.py` (基于实测 drift, 不假设)"
- 必须严格按 brief 写新迁移 (105), 不能动 100-104
- 但**关键风险**: 105 接续 chain head = 104, 跑 upgrade head 仍会先跑 100/101/102 → 100/101/102 的 ALTER 在已 halfvec 列上会失败

**最终决策**:
1. 写 105_fix_drift.py 接续 104 (brief 要求)
2. 105 内容: 把 103+104 的同样动作**再做一遍** (IF NOT EXISTS 兼容已有)
3. 跑迁移前先 `alembic stamp 102_voiceprint_halfvec` (跳过 100-102 的列类型变更)
4. 再 `alembic upgrade head` 跑 103+104+105

## 6. 5 件套守恒实测 (W-N-G+ +3 收口时填)

## 7. W-N-G+ +0 起步 6 项 (W73 铁律)

- [x] 派工 brief 锚定
- [x] 派工起点 fetch (main HEAD = `1cc5362e2`)
- [x] 实测 DB schema (3 drift 锁定)
- [x] alembic 链状态确认 (code 104, DB 099)
- [x] 修复策略定 (105 + stamp 102 + upgrade)
- [ ] W73 B 类避坑 (老 voiceprint/memory 不动, 仅迁移 + verification 脚本)

## 8. W-N-G+ +1 / +2 / +3 任务分配

- **W-N-G+ +1**: 实测 DB schema + 写 `alembic/versions/105_fix_drift.py` + stamp + upgrade
- **W-N-G+ +2**: 写 `scripts/verify_chunk_late_recall.py` + pytest integration test + 输出 `results/chunk_late_recall_verify_2026-08.json`
- **W-N-G+ +3**: 5 件套守恒实测 + 收口 memory

## 9. 风险与注意事项

- **风险 1**: 105 迁移必须 idempotent (IF NOT EXISTS 或 try/except), 因为 103+104 在某些场景可能已部分应用
- **风险 2**: `_chunk_late_recall` 方法如果业务代码不存在, 必须**仅写 verification 脚本**, 不改业务代码 (0 production code)
- **风险 3**: alembic stamp 会跳版本, 必须**先确认 100-102 列类型已应用** (本任务已实测确认)
- **风险 4**: pytest integration test 不能 require live DB connection (用 fixture + mock 或 in-memory)

## 10. 实测确认 (派工 v6 §13 仓库实情真查)

```bash
$ docker exec microbubble-agent-db-1 psql -U postgres -d microbubble -c "SELECT version_num FROM alembic_version"
  version_num
--------------
 099_add_dft_jobs

$ docker exec microbubble-agent-db-1 psql -U postgres -d microbubble -c "\d knowledge" | grep embedding
 embedding         | halfvec(1024)
 embedding_model   | character varying   (老字段, 不动)
 embedding_model_version | (缺失!)

$ docker exec microbubble-agent-db-1 psql -U postgres -d microbubble -c "\d knowledge_chunks" | grep embedding
 embedding | vector(1024)   (chunk_embedding 缺失!)
```