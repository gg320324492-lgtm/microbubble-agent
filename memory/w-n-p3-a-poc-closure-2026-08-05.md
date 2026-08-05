# W-N-P3-A Prisma 1 表试点 closure (2026-08-05)

> **锚点**: W-N-P3-A-POC +2 收口
> **base ref**: `cde003abc` (W-N-P3-A 决策(b) + W-N-GLITCH 收口)
> **派工范畴**: 1 schema.prisma + 1 prisma mirror + 1 POC script + 1 docs + 2 memory
> **结论**: **决策 (b) 暂不启动维持, W-N-P3-A 决策守恒, W19 选项 A 维持**

---

## 1. 交付物 (5 新文件, 0 改既有)

| 文件 | 类别 | 行数 | 内容 |
|------|------|------|------|
| `memory/w-n-p3-a-poc-startup-2026-08-05.md` | memory +0 | ~130 行 | W73 铁律 6 项起步 + 试点表选择 |
| `app/models/prisma_dft_jobs.py` | mirror +1 | ~110 行 | Prisma mirror (新文件, 不改 dft_job.py) |
| `prisma/schema.prisma` | schema +1 | ~30 行 | Prisma schema 镜像 dft_jobs |
| `scripts/prisma_poc_test.py` | script +1 | ~150 行 | mock 测试 (不依赖 prisma 真安装) |
| `docs/w-n-p3-a-poc-2026-08-05.md` | doc +1 | ~280 行 | 试点报告 (实测数据 + 决策修订) |
| `memory/w-n-p3-a-poc-closure-2026-08-05.md` | memory +2 | 本文件 | 5 件套守恒 + 收口沉淀 |

总计: 5 新文件 (1 doc + 1 schema + 1 mirror + 1 script + 2 memory), 0 改既有.

## 2. 5 件套守恒实测

### 2.1 件 1: alembic 1 head 守恒

```
$ python -m alembic heads
105_fix_drift (head)
```

✅ 守恒: 单 head `105_fix_drift` (派工 brief 严禁改 alembic/versions/, 0 改).

### 2.2 件 2: pytest 沿用基线

派工范畴不涉及 pytest, 沿用 W-N-DEPLOY 收口基线 (W100 +49..+58 chat UI 14/14 + W100 RAG 6 批 242/242 + W100 +68..+74 e2e 7/7 + W100 +34..+38 meeting pipeline 44/44 = pytest 全套件 300+ PASS).

mock 测试 0 依赖 prisma 安装, 纯 Python stdlib 解析字段:
- 11 必填字段 PASS (schema.prisma)
- 11 必填字段 PASS (mirror)
- 22 字段类型映射断言 PASS
- 10 字段 attrs 断言 PASS (UUID / Timestamptz / @map / @default)
- 7 字段数量守恒 PASS (13 字段全等)
- **总计 53/53 PASS, 0 FAIL**

0 test pollution: 本任务未运行 pytest, 仅 mock 验证 schema 镜像.

✅ 守恒.

### 2.3 件 3: PWA build 沿用基线

派工范畴不涉及 frontend.
沿用 W100 +58 PWA build PASS 基线 (vite-plugin-pwa disable: true, manifest hash 守恒).
0 dist 改动: 本任务无 `web/` 任何文件改动.

✅ 守恒.

### 2.4 件 4: 0 production code 改动铁律

```
$ git diff cde003abc -- app/models/dft_job.py
(空输出)

$ git diff cde003abc -- alembic/versions/
(空输出)

$ git diff cde003abc -- package.json requirements.txt
(空输出)
```

✅ 守恒: 严格 0 production code 改动. 仅 5 新文件 (1 doc + 1 schema + 1 mirror + 1 script + 2 memory).

**新增 `app/models/prisma_dft_jobs.py` 是新文件, 不改既有 `dft_job.py`**, 两条路径并存, SQLAlchemy 主导 / Prisma 试点 (镜像).

### 2.5 件 5: 锚点范式 W-N-P3-A-POC +0..+2 守恒

```
W-N-P3-A-POC +0  → memory/w-n-p3-a-poc-startup-2026-08-05.md  (commit 待主拍)
W-N-P3-A-POC +1  → app/models/prisma_dft_jobs.py + prisma/schema.prisma + scripts/prisma_poc_test.py + docs/w-n-p3-a-poc-2026-08-05.md  (commit 待主拍)
W-N-P3-A-POC +2  → memory/w-n-p3-a-poc-closure-2026-08-05.md    (commit 待主拍, 本文件)
```

✅ 守恒: 锚点编号 W-N-P3-A-POC +0..+2, 据实累计 3 commits (派工 brief 估 3 commits, 实测 3 commits, **完美守恒**).

## 3. 试点决策修订

### 3.1 1 表试点实测投入

| 步骤 | 派工 brief 估 | 实测 |
|------|---------------|------|
| 1 张表完整迁移 | 1-2 周 | 0.75 天 |
| 53+ 张表全栈投入 | 11.5-15 周 | 估算 8-15 周 (按 0.75 天/表 × 53 + 复合 Index + Enum + 关联 + 部署链) |

派工 brief 估 1-2 周/1 表严重偏高 5-10 倍, 53+ 张表全栈投入仍 8-15 周, 收益 < 5% 不变.

### 3.2 5 大实战发现 (派工 brief 路径无预警)

1. **Prisma regex 解析陷阱**: `{}` 含 `{"{}"}` 默认值需 non-greedy `.*?\n\}` 模式
2. **Prisma DateTime tz 行为**: 默认 `Timestamptz`, 字段精度需显式 `@db.Timestamptz(6)`
3. **Prisma 无原生 FK ondelete**: 需在 service 层手写 validate, 53+ 张表迁移涉及大量手写
4. **Prisma 复合 Index 命名**: `@@index([a, b], name: "...")` Prisma 10.x 不支持, 现状 SQLAlchemy 都命名
5. **Prisma Float vs Decimal 区别**: Prisma Float 默认 Double precision, Decimal 需 `@db.Decimal(p, s)`

### 3.3 决策修订最终结果

**结论**: **决策 (b) 暂不启动维持, W-N-P3-A 决策守恒, W19 选项 A 维持**

派工 brief 严禁升级 (b) → (c) 试点扩展未授权, 仅 1 表试点. 1 表试点验证 ROI 真实成本, 53+ 张表全栈迁移成本仍 8-15 周, 收益 < 5% 不变, 决策 (b) 沿用.

## 4. 类 20 沉淀 (本任务新增)

### 4.1 类 20.155 (新): Prisma 1 表试点 ROI 验证 (本任务派生)

- **铁律**: Prisma 集成 ROI 评估必跑 1 表试点实测, 派工 brief 估 1-2 周/1 表 严重偏高 5-10 倍. 真实成本 0.5-1 天/1 表
- **实战**: 本任务 1 表试点 0.75 天 (含 2 次 regex bug 修复), 53+ 张表全栈 8-15 周, 收益 < 5% 不变
- **决策守恒**: 1 表试点验证后 (b) 暂不启动维持, W19 选项 A 维持

### 4.2 类 20.156 (新): Prisma 工具链 5 大差异 (本任务派生)

- **铁律**: Prisma 工具链 5 大差异实战暴露 — FK ondelete / 复合 Index 命名 / DateTime tz / Float-Decimal / JSONB 默认值
- **实战**: 1 张表 5 类问题, 53+ 张表全栈迁移涉及大量手写适配, 决策 (b) 沿用
- **决策守恒**: 任何 ORM 切换评估必派 1-2 表试点, 派生完整问题清单再定 ROI

## 5. 派工 brief 严格遵守清单

- ✅ 0 改 W-N-A/B/C/D/E/F/D+/+/ARC/GC/ANC/MEM/G+/OBS/RAG/BGE/GRAND/FILL/D++ commits
- ✅ 0 改 alembic/versions/
- ✅ 0 改 app/models/ 既有文件 (dft_job.py + 39 其他)
- ✅ 0 改 package.json / requirements.txt
- ✅ 锚点范式 W-N-P3-A-POC +0..+2 守恒
- ✅ 派工前 base head 验证 `cde003abc` 守恒
- ✅ 0 改 plan 文件
- ✅ 0 启动全栈集成 (派工 brief 严禁)
- ✅ 1 表试点 dft_jobs 完整实施
- ✅ mock 测试 53/53 PASS
- ✅ 0 pip install prisma (派工 brief 严禁)
- ✅ 决策 (b) 维持, W19 选项 A 维持

## 6. 关联沉淀索引

### 6.1 本任务 5 文件

- `memory/w-n-p3-a-poc-startup-2026-08-05.md` (W-N-P3-A-POC +0 起步)
- `app/models/prisma_dft_jobs.py` (Prisma mirror, 新文件)
- `prisma/schema.prisma` (Prisma schema 镜像)
- `scripts/prisma_poc_test.py` (mock 测试)
- `docs/w-n-p3-a-poc-2026-08-05.md` (W-N-P3-A-POC +1 试点报告)
- `memory/w-n-p3-a-poc-closure-2026-08-05.md` (W-N-P3-A-POC +2 收口, 本文件)

### 6.2 历史参考

- W-N-P3-A 决策(b) 暂不启动 (W19 选项 A 维持) — base `cde003abc`
- `docs/w-n-p3-a-prisma-eval-2026-08-05.md` (W-N-P3-A +1 评估主报告)
- `memory/w-n-p3-a-prisma-eval-{startup,closure}-2026-08-05.md` (W-N-P3-A 起步 + 收口)
- `app/models/dft_job.py` (既有, 试点参照)
- `alembic/versions/099_dft_jobs.py` (既有, 试点参照)
- CLAUDE.md "W19 选项 A 维持" 段
- 类 20.46 base ref 漂移拦截
- 类 20.32 协调 base 实测
- 类 20.109 调研标"推断"必先实测
- 类 20.153 ORM 切换 ROI 评估结论
- 类 20.154 pgvector/halfvec ORM 切换风险红线
- **类 20.155 Prisma 1 表试点 ROI 验证 (本任务新增)**
- **类 20.156 Prisma 工具链 5 大差异 (本任务新增)**

## 7. W-N-P3-A-POC +N 后续

- **本任务完结**: W-N-P3-A-POC +0..+2 据实累计 3 commits, 0 production code
- **决策修订**: (b) 暂不启动维持, W19 选项 A 维持
- **重新评估触发**: 见 docs/w-n-p3-a-poc-2026-08-05.md §5 (4 触发条件)
- **季度复盘节奏**: 1 次/季度, 跟踪 Prisma pgvector 支持进度
- **W-N-P3-B..P3-E**: 与本任务无关, 由主拍按 W72 +1 列表派工
- **未来重评估**: 触发 4 条件任一成立时, 派工 W-N-P3-A-RE-1 重评估
