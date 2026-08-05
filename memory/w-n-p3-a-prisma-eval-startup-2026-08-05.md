# W-N-P3-A Prisma 集成评估 startup (2026-08-05)

> **锚点**: W-N-P3-A +0 startup
> **base ref**: `74d1a965e` (W-N-DEPLOY +0/+1/+2 收口)
> **任务**: Prisma 集成 ROI 评估, 写 `docs/w-n-p3-a-prisma-eval-2026-08-05.md` 决策建议
> **派工范畴**: docs + memory, 严禁改 production code

---

## 1. 任务定位

W-N-W72 +1 已沉淀 P3-A..P3-E 后续 PR 列表. P3-A 是 "Prisma 集成评估". 本任务**只做评估**, 不启动集成. 决策建议必须沿用 W19 选项 A 维持 (Phase 8.5 / P3 dedup / P3 跨 tab / 7 E2E 留未来 PR).

## 2. W73 铁律 6 项起步

### 2.1 派工 brief 验证 (类 20 沿用)
- 派工锚点: W-N-P3-A +0..+2
- 派工 brief 严禁擅自派工 P3-A 集成实施 (评估 ≠ 启动)
- 0 production code 改动铁律守恒: `app/models/` + `alembic/versions/` + `package.json` + `requirements.txt` 全部不动

### 2.2 base head 实测 (类 20.46 + 20.32 沿用)
```
74d1a965e docs(deploy-status): W-N-DEPLOY 部署状态验证报告 + 起步 + 收口
3d45465c1 docs(memory): W-N-MIN (b) 实施收口
d49057d39 docs(memory): CLAUDE.md 顶层 mini-N 减负
```
守恒 ✅ (W-N-DEPLOY 收口 commit 顶部).

### 2.3 工作范畴界定 (派工 brief 严格遵守)
- 允许: 新建 `docs/w-n-p3-a-prisma-eval-2026-08-05.md` + `memory/w-n-p3-a-prisma-eval-{startup,closure}-2026-08-05.md` 共 3 文件
- 禁止: 改任何 `app/` `web/src/` `alembic/` `package.json` `requirements.txt`
- 禁止: 启动 Prisma 集成 (派工 brief 严禁)
- 禁止: 改 plan 文件 / 改 W-N 任何已沉淀 commit

### 2.4 数据采集 (Step 1+2 起点)
- `find app/models -name "*.py" | wc -l` = **40 文件** (含 `__init__.py` + `base.py` + `types.py`)
- `wc -l app/models/*.py` 总计 = **4233 行** (40 文件)
- ORM class 总计 = **70 classes** (跨 40 文件, 含 join table / 关联实体)
- alembic migrations = **96 文件** (从 `001_initial.py` 到 `105_fix_drift.py`)
- alembic head = `105_fix_drift (head)` (单 head, 串单链守恒)
- `app/api/` = **52 文件** + `app/services/` = **179 文件** 间接依赖 ORM
- 184 文件 `import app.models` (直接依赖点)
- PG-specific 特性 (JSONB / pgvector / halfvec / hnsw) 出现 **76 次** 在 models 中

### 2.5 关联风险点提前识别
- **pgvector 集成** (W97 PR2 + 100/101/102 halfvec 演进): models/knowledge.py 464 行含 `Vector(dim)` 自定义类型, Prisma 无原生 pgvector 支持
- **半精度向量 (halfvec)** (W100 +100/101/102): models 含 `HALFVEC` 自定义类型, 属于 PostgreSQL pgvector 0.7.0+ 特性
- **JSONB 列**: 76 次出现, 跨任务/会议/知识库/Agent/驱动/聊天 等多表
- **Custom Enum**: PostgreSQL enum 类型多处使用 (如 `meetings.status`, `tasks.priority`)
- **asyncpg + psycopg2 双驱动**: requirements.txt 实测 2 个 driver 并存 (async 主路径, sync alembic)

### 2.6 调研边界
- 调研标"推断"必先实测 (类 20.109 沿用)
- ROI 数据基线: 实测 W-N-P3-A +1 评估报告产出
- 不擅自扩范畴: P3-A 集成实施 + P3-B/C/D/E 5 个后续 PR 都不在本次任务范畴
- 派工 v6 §13 仓库实情真查: 不凭 CLAUDE.md 历史, 必须实测

---

## 3. 起步状态实测

```
$ git log --oneline -3
74d1a965e docs(deploy-status): W-N-DEPLOY 部署状态验证报告 + 起步 + 收口
3d45465c1 docs(memory): W-N-MIN (b) 实施收口
d49057d39 docs(memory): CLAUDE.md 顶层 mini-N 减负
```
```
$ git status --short
?? memory/w-n-revise-fill-decision-startup-2026-08-05.md  (其他任务, 与本任务无关)
```
守恒: HEAD = `74d1a965e`, 当前 branch = `main`, 0 commit ahead of base.

## 4. 下一步 (W-N-P3-A +1)

- Step 1 评估: 已采集 (40 文件 / 4233 行 / 70 classes / 96 migrations / 76 PG-specific)
- Step 2 ROI: 重写 53+ 张表 ORM = 3-5 周投入 vs 5-10% 收益估算
- Step 3 写 `docs/w-n-p3-a-prisma-eval-2026-08-05.md` (4 段决策建议)
- Step 4 commit docs/memory 范畴

## 5. 关联沉淀索引

- W19 选项 A 维持 (Phase 8.5 / P3 dedup / P3 跨 tab / 7 E2E 留未来 PR)
- W72 +1 P3-A..P3-E 后续 PR 列表
- W97 PR2 knowledge_chunk pgvector parent-child chunking
- W100 +100/101/102 halfvec 演进
- 类 20.46 base ref 漂移拦截 + 类 20.32 协调 base 实测
- 类 20.109 调研标"推断"必先实测