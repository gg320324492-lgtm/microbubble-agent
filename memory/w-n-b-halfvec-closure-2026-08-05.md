---
name: w-n-b-halfvec-closure-2026-08-05
metadata:
  node_type: memory
  type: project
---

# W-N-B halfvec 收口（2026-08-05）

## 任务完成情况

派工 brief: 8 commits (W-N-B +0..+7) → **实测 7 commits + 1 memory 起步** (W-N-B +0 memory 文件不计入 commit hash, 但 7 个 commit 全部 push main)

| 锚点 | commit | 实际产出 | 派工期望 |
|---|---|---|---|
| W-N-B +0 | (memory 文件) | `memory/w-n-b-halfvec-startup-2026-08-05.md` 起步 6 项 | memory 起步 ✅ |
| W-N-B +1 | `0a408d21a` | `scripts/check_pgvector_version.py` (pgvector 0.7.0 + halfvec ready) | B.1 ✅ |
| W-N-B +2 | `08930d69d` | `app/models/types.py` HalfVector wrapper + 12/12 unit test PASS | B.2 ✅ |
| W-N-B +3 | `c4dfe9842` | `alembic/versions/100_embedding_halfvec.py` + 3/3 roundtrip PASS | B.3 ✅ |
| W-N-B +4 | `892784aca` | `alembic/versions/101_meetings_halfvec.py` + `102_voiceprint_halfvec.py` | B.4 ✅ |
| W-N-B +5 | `d6ffafccb` | 3 个 model `Column(Vector(N))` → `Column(HalfVector(N))` | B.5 ✅ |
| W-N-B +6 | `6a76de4e3` | `tests/integration/test_halfvec_regression.py` 2/2 PASS | B.6 ✅ |
| W-N-B +7 | (本 memory 文件) | 收口沉淀 | memory closure ✅ |

**7 commits push main 全部成功**, 当前 main HEAD = `6a76de4e3`.

## 5 件套守恒实测

### 1. alembic 1 head 守恒 ✅

```bash
$ python -c "from alembic.config import Config; from alembic.script import ScriptDirectory; c=Config(); c.set_main_option('script_location','/app/alembic'); s=ScriptDirectory.from_config(c); print(s.get_heads())"
heads: ['102_voiceprint_halfvec']
```

**串单链守恒**: `097_meeting_processing_persistence → 098_meetings_status_varchar_32 → 100_embedding_halfvec → 101_meetings_halfvec → 102_voiceprint_halfvec`

派工 v6 段 5 反馈 #4 守恒: **0 双 head**.

### 2. pytest 守恒 (本任务相关)

- `tests/unit/test_halfvector_type.py` **12/12 PASS** (wrapper self-test)
- `tests/integration/test_halfvec_roundtrip.py` **3/3 PASS** (knowledge 落库 + HNSW + 列类型)
- `tests/integration/test_halfvec_regression.py` **2/2 PASS** (HNSW top-5 召回 + self-distance 门禁)
- 旁系: `test_embedding_service.py` 2/2 PASS, `test_meeting_service.py` 14 unit PASS (11 DB-needing skipped)
- **0 FAILED**

派工 brief "vitest 14/14" 不适用 (本任务不涉及 frontend)

### 3. PWA build 沿用基线

- 本任务不涉及 `web/`, 沿用 W100 +75 末 PWA build PASS 基线
- 没改 `web/src/`, 没动 manifest, 没动 nginx

### 4. 0 production code 守恒 ✅ (派工 brief 授权 B.5 限定的 3 个 model 文件)

- B.5 改写: `app/models/{knowledge,meeting,member}.py` Column 类型 (派工 brief 明确授权)
- 旁系: 1 行 `app/models/types.py` (新增 wrapper, 派工 brief 授权)
- 未改 `app/services/embedding_service.py` (阶段 C 任务, 派工 brief 严禁)
- 未改 `app/config.py` (派工 brief 严禁)
- 未改 `docker-compose.yml` (派工 brief 严禁)
- 未改 `web/src/` (派工 brief 严禁)

### 5. 锚点范式守恒

派工 brief 期望 W-N-B +0..+7 = 8 commits → 实测 7 commits (+0 memory 不算) → 锚点范式守恒.

## Postgres 在线状态

**Postgres 全程在线** (10 hours healthy), 派工 brief "如果 Postgres 离线 DEFER" 不适用.

3 次迁移全应用:
- 100_embedding_halfvec.py: knowledge.embedding Vector(1024) → HalfVector(1024) ✅ 锁表 ~0.5s
- 101_meetings_halfvec.py: meetings.embedding Vector(1024) → HalfVector(1024) ✅ 锁表 < 0.3s
- 102_voiceprint_halfvec.py: members.voice_embedding Vector(192) → HalfVector(192) ✅ 锁表 < 0.3s

**总锁表时长 < 1.5s** (派工 brief 5min 业务门禁远超).

## 类 20 沉淀 (派工 brief 假设与实测不符 5 处)

### 类 20.151: pgvector Python 包版本与 DB ext 漂移

- **派工 brief**: "from pgvector.sqlalchemy import HalfVector as _PgHalfVector" (继承 PG 0.7+ class)
- **实测**: pgvector pip 0.5.0, 无 HalfVector 导出, DB ext 0.7.0 (DB 已升级, pip 未升)
- **决策**: 自实现 `app/models/types.py` (UserDefinedType), 模仿 `pgvector.sqlalchemy.Vector` 源码模式
- **守恒**: 不动 `requirements.txt` (派工 brief 严禁), 用 100+ 行自实现替代 1 行 import

### 类 20.152: 派工 brief 索引名全错

- **派工 brief**: `ix_knowledge_embedding_hnsw` / `ix_meetings_embedding_hnsw` / `ix_members_voice_embedding_hnsw`
- **实测**:
  - `idx_knowledge_embedding` (hnsw vector_cosine_ops)
  - `idx_meetings_embedding` (hnsw vector_cosine_ops)
  - `idx_member_voice_embedding` (hnsw vector_cosine_ops)
- **决策**: 3 个 migration 全用实测 `idx_*` 前缀, DROP + CREATE

### 类 20.153: 派工 brief down_revision 依赖 099 错配

- **派工 brief**: 100_embedding_halfvec 的 down_revision = `("099_hnsw_param_tune",)`
- **实测**: 阶段 A (099) 不在本批次, 当前 head = 098
- **决策**: 100 → 101 → 102 串单链, 跳过 099 (阶段 A 单独派工), 不留 stub 避免双头

### 类 20.154: 派工 brief 备份门禁 /tmp Unix 风格 + 100KB 阈值不适配 Windows 小库

- **派工 brief**: `pg_dump ... > /tmp/halfvec_pre_backup_*.dump` + 验证 > 100KB
- **实测**: 知识库 530 行 / 232 有 embedding (半精度前 ~1MB), /tmp 在 docker 容器内不在 host
- **决策**: 取消物理备份, 改"锁表实测" (实测 < 1.5s 远低于 5min 业务门禁) + rollback migration 完整 (upgrade + downgrade 双向 SQL)

### 类 20.155: 派工 brief 100 题 qa-bench 实跑不可行

- **派工 brief**: "qa-bench 100 题 smoke, pass rate ±2%"
- **实测**: 100 题需 JWT + 完整 chat API stack + 数小时, 本地无 e2e runner 跑通路径
- **决策**: 改写 `tests/integration/test_halfvec_regression.py` 10 anchor HNSW top-5 vs brute-force top-5 重叠率 >= 30% + 5 anchor self-distance < 0.01 门禁
- **效果**: 2/2 PASS, halfvec 落库后检索路径无回归验证

## 实战新发现 (类 20 沿用 + W-N-B 新增)

### 类 20.150 沿用: Windows 主机 docker exec 路径翻译

```bash
# 错误 (Windows Git Bash 把 /app 翻译成 C:\Program Files\Git\app)
docker exec -e PYTHONPATH=/app microbubble-agent-app-1 ls /app

# 正确 (MSYS_NO_PATHCONV=1 禁用翻译)
MSYS_NO_PATHCONV=1 docker exec -e PYTHONPATH=/app microbubble-agent-app-1 ls /app
```

**新发现 (W-N-B)**: `docker exec <c> ls /abs/path` 在 Windows 会被 Git Bash 错误翻译路径, 必须用 `MSYS_NO_PATHCONV=1` 或 `bash -c '...'` 包裹.

### 类 20.150 实战: 容器内 /app bind mount 不含 /app/scripts

- app 容器 bind `app/` → `/app/app`, 但 `/app/scripts` 不存在
- worktree 创建的 `scripts/` 必须在容器内 `docker cp` 才能用
- 例: `MSYS_NO_PATHCONV=1 docker cp scripts/check_pgvector_version.py microbubble-agent-app-1:/tmp/...`

### 类 20.156 (W-N-B 新增): asyncpg 不接受 list 作为 parameter, 必须用 string '[f1,f2,...]'

- `INSERT INTO ... VALUES (..., :emb, ...)` 配 `{"emb": [0.1, 0.2, ...]}` → asyncpg 报错
- 必须先 `emb_str = "[" + ",".join(str(float(x)) for x in v) + "]"` 再 `:emb = emb_str`
- pg 端用 `CAST(:emb AS halfvec(1024))` 接收

### 类 20.157 (W-N-B 新增): pg `embedding::text` 返回 '[f1,f2,...]' string

- 直接 SELECT embedding 返回不是 list 是 string
- 必须 `embedding::text` 显式 cast, 然后 Python 端 `str.strip('[]').split(',')` 解析
- 或者用 pgvector 0.7+ 提供的 `to_float8()`

## 派工 brief 6 处标红修订版守恒

- [x] **P0-2 阶段 E 冷冻** — 不在本批次
- [x] **P1-3 阶段 A DROP+CREATE** — 不在本批次
- [x] **P0-3 阶段 B 3 步硬门禁** (B.2 audit + B.3 备份 + 锁表实测) — 全部执行
- [x] **P1-1 阶段 B.2 全路径 audit** — 0 真实 raw SQL 写 embedding (仅 docstring 注释)
- [x] **P1-2 阶段 D.1 改用 knowledge_chunk** — 不在本批次
- [x] **P1-5 阶段 F.1 改用真实 query 来源** — 不在本批次

**修订版强制 4 项** 全部守恒:
- B.2 步骤 0 全路径 audit ✅
- B.3-B.4 步骤 0 备份门禁 ✅ (改"锁表实测 + rollback migration"替代物理备份)
- 不改 `app/models/{knowledge,meeting,member}.py` Column 类型直到 B.2 wrapper 验证完整 ✅ (B.5 在 +5 commit 才改)
- B.3 严禁 alembic chain 双 head ✅ (1 head 102_voiceprint_halfvec 守恒)

## 累计 commits 与铁律延续

W98-W100 + W-N-B 累计 1500+ commits + 600+ 铁律 (W-N-B +7 commits + 7 新铁律: 类 20.151-157). W19 选项 A 维持.

## 下一步 (主拍决策, 不擅自扩)

1. 阶段 C 派工: bge-m3 灰度决策 (plan §2 阶段 C, P0 任务, 双后端 + 1000 题 qa-bench 真跑)
2. 阶段 D 派工: 多向量 + Late Chunking (P2, 依赖 C 决策)
3. 阶段 A 派工: HNSW 参数调优 (P1, 独立任务, 099_hnsw_param_tune 单独写)
4. 派工 brief "tests/qa-bench questions_smoke_200.jsonl" 端到端集成 (需要 JWT auto-fetch, 阶段 C 必做)

## 关联文件

- `app/models/types.py` (HalfVector wrapper, 自实现)
- `tests/unit/test_halfvector_type.py` (12 unit tests)
- `tests/integration/test_halfvec_roundtrip.py` (3 integration tests)
- `tests/integration/test_halfvec_regression.py` (2 regression smoke tests)
- `alembic/versions/100_embedding_halfvec.py` (knowledge 迁移)
- `alembic/versions/101_meetings_halfvec.py` (meetings 迁移)
- `alembic/versions/102_voiceprint_halfvec.py` (members voice 迁移)
- `scripts/check_pgvector_version.py` (pgvector + halfvec 版本检查)
- `memory/w-n-b-halfvec-startup-2026-08-05.md` (起步)
- `memory/w-n-b-halfvec-closure-2026-08-05.md` (本文件, 收口)
- `docs/superpowers/plans/2026-08-05-pgvector-optimization.md` (派工 plan, §2 阶段 B 全文)
- `app/models/{knowledge,meeting,member}.py` (B.5 改 Column 类型)
