# W-N-P3-A Prisma 1 表试点 startup (2026-08-05)

> **锚点**: W-N-P3-A-POC +0 startup
> **base ref**: `cde003abc` (W-N-P3-A 决策(b) + W-N-GLITCH 收口)
> **任务**: Prisma 集成 1 张表试点 (派工 brief 严禁全栈集成)
> **派工范畴**: 1 schema.prisma + 1 prisma mirror (新文件) + 1 POC script + 1 docs + 2 memory
> **严禁**: 0 改 W-N-A/B/C/D/E/F/D+/+/ARC/GC/ANC/MEM/G+/OBS/RAG/BGE/GRAND/FILL/D++ commits + 0 改 alembic/versions/ + 0 改 app/models/ 既有文件 + 0 改 package.json/requirements.txt + 0 全栈集成

---

## 1. 任务定位

W-N-P3-A 决策(b) 暂不启动 (W19 选项 A 维持, ROI 负值 11.5-15 周 vs < 5% 收益). 主拍派工 PoC 1 表试点, 验证派工 brief 假设的 "1-2 周投入" 真实成本, 为后续决策修订提供数据基线.

**派工 brief 严禁**:
- 禁止全栈集成 (15-30 张表)
- 禁止改 alembic/versions/
- 禁止改 app/models/ 既有文件
- 禁止改 package.json / requirements.txt (不 pip install prisma)
- 禁止 pip install prisma / npm install prisma

**允许范畴**:
- 新建 `prisma/schema.prisma` (镜像 1 张表)
- 新建 `app/models/prisma_dft_jobs.py` (Prisma mirror, 不改既有 dft_job.py)
- 新建 `scripts/prisma_poc_test.py` (mock 测试, 不依赖 prisma 真安装)
- 新建 `docs/w-n-p3-a-poc-2026-08-05.md` (试点报告)
- 新建 `memory/w-n-p3-a-poc-{startup,closure}-2026-08-05.md` (起步 + 收口)

## 2. W73 铁律 6 项起步

### 2.1 派工 brief 验证 (类 20 沿用)
- 派工锚点: W-N-P3-A-POC +0 / +1 / +2
- 派工 brief 严禁擅自扩: 仅 1 表试点, 不启动全栈集成
- 0 production code 改动铁律守恒: `app/models/` 已有 + `alembic/versions/` + `package.json` + `requirements.txt` 全部不动

### 2.2 base head 实测 (类 20.46 + 20.32 沿用)
```
$ git log --oneline -3
cde003abc docs(decision): W-N-P3-A + W-N-GLITCH 5 文件 untracked commit 推 main (W-N-P3-A + W-N-GLITCH 收口)
821874cca docs(w-n-glitch): glitchtip-dev-1 restart loop 修复尝试 (W-N-GLITCH +1)
71e448595 docs(memory): W-N-BGE-PRE 收口 (W-N-BGE-PRE +2)
```
守恒 ✅ (W-N-P3-A + W-N-GLITCH 收口 commit 顶部).

### 2.3 工作范畴界定 (派工 brief 严格遵守)
- 允许: 新建 `prisma/schema.prisma` + `app/models/prisma_dft_jobs.py` + `scripts/prisma_poc_test.py` + `docs/w-n-p3-a-poc-2026-08-05.md` + `memory/w-n-p3-a-poc-{startup,closure}-2026-08-05.md` 共 6 文件
- 禁止: 改任何 `app/models/` 既有文件 + `alembic/versions/` + `package.json` + `requirements.txt` + `app/services/` + `app/api/` + `web/src/`
- 禁止: pip install prisma / npm install prisma (派工 brief 严禁)
- 禁止: 启动 Prisma 集成实施 (派工 brief 严禁)
- 禁止: 改 plan 文件 / 改 W-N 任何已沉淀 commit

### 2.4 试点表选择 (派工 brief 允许 dft_jobs 或 members)
- 选定: **`dft_jobs`** (W-N-DFT agent 写, 字段少, 单表最小迁移成本)
- 字段数: 9 列 (id UUID + user_id FK + tool + smiles + params JSONB + status + result JSONB + log_path + error_msg + submit_time + finish_time)
- 索引: 3 个 (PK + 2 单列 + 2 复合)
- 不依赖 pgvector/halfvec (Prisma 官方不支持)
- 不依赖 PostgreSQL enum / hstore / range types (Prisma 官方仅 enum 部分支持)
- 字段类型挑战: UUID (Prisma 原生支持) + JSONB (Prisma 原生 Json) + ForeignKey (Prisma 关系) + 复合 Index (Prisma @@index tuple 有限)

### 2.5 试点 7 步路线 (派工 brief 明确)
- Step 1: 选 1 张表 → done (`dft_jobs`)
- Step 2: 写 `app/models/prisma_dft_jobs.py` Prisma mirror (1 张表)
- Step 3: 写 `prisma/schema.prisma` 镜像 (dft_jobs 1 张表)
- Step 4: 写 `scripts/prisma_poc_test.py` mock 测试 (不依赖 prisma 真安装)
- Step 5: 跑 mock 测试 (派工 brief 严禁 pip install prisma)
- Step 6: 写 `docs/w-n-p3-a-poc-2026-08-05.md` 试点报告
- Step 7: commit docs/scripts/memory 范畴

### 2.6 调研边界
- 调研标"推断"必先实测 (类 20.109 沿用)
- 派工 brief 严禁 pip install prisma: mock 测试路线
- 不擅自扩范畴: 1 表试点 + 决策修订评估, 不启动集成
- 派工 v6 §13 仓库实情真查: 不凭 CLAUDE.md 历史, 必须实测

## 3. 起步状态实测

```
$ git log --oneline -3
cde003abc docs(decision): W-N-P3-A + W-N-GLITCH 5 文件 untracked commit 推 main (W-N-P3-A + W-N-GLITCH 收口)
821874cca docs(w-n-glitch): glitchtip-dev-1 restart loop 修复尝试 (W-N-GLITCH +1)
71e448595 docs(memory): W-N-BGE-PRE 收口 (W-N-BGE-PRE +2)
```
```
$ git status --short
(empty)
```
守恒: HEAD = `cde003abc`, 当前 branch = `main`, 0 commit ahead of base.

## 4. 下一步 (W-N-P3-A-POC +1)

- Step 2: 写 `app/models/prisma_dft_jobs.py` Prisma mirror (intent 模板 + 1 张表 dft_jobs)
- Step 3: 写 `prisma/schema.prisma` 镜像 dft_jobs
- Step 4: 写 `scripts/prisma_poc_test.py` mock 测试 (不依赖 prisma 安装, 纯解析 schema.prisma 字段做断言)
- Step 5: 跑 mock 测试 (Python stdlib 解析, 无需 pip install)
- Step 6: 写 `docs/w-n-p3-a-poc-2026-08-05.md` 试点报告 (实测数据 + 决策修订)
- Step 7: commit docs/scripts/memory 范畴

## 5. 关联沉淀索引

- W-N-P3-A 决策(b) 暂不启动 (W19 选项 A 维持, ROI 负值 11.5-15 周 vs < 5% 收益)
- W-N-DEPLOY 收口 (base `cde003abc`)
- W73 铁律 6 项起步
- 类 20.46 base ref 漂移拦截
- 类 20.32 协调 base 实测
- 类 20.109 调研标"推断"必先实测
- 类 20.153 ORM 切换 ROI 评估结论 (W-N-P3-A 决策)
- 类 20.154 pgvector/halfvec ORM 切换风险红线
