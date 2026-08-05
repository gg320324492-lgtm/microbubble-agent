# W-N-P3-A Prisma 集成评估 closure (2026-08-05)

> **锚点**: W-N-P3-A +2 收口
> **base ref**: `74d1a965e` (W-N-DEPLOY 收口)
> **派工范畴**: docs + memory, 0 production code 守恒
> **结论**: **决策 (b) 暂不启动, W19 选项 A 维持**

---

## 1. 交付物 (3 文件, 0 production code)

| 文件 | 类别 | 行数 | 内容 |
|------|------|------|------|
| `memory/w-n-p3-a-prisma-eval-startup-2026-08-05.md` | memory +0 | ~80 行 | W73 铁律 6 项起步 + 数据采集 |
| `docs/w-n-p3-a-prisma-eval-2026-08-05.md` | doc +1 | ~280 行 | 4 段决策建议 (现状/ROI/风险/决策) |
| `memory/w-n-p3-a-prisma-eval-closure-2026-08-05.md` | memory +2 | 本文件 | 5 件套守恒 + 收口沉淀 |

## 2. 5 件套守恒实测

### 2.1 件 1: alembic 1 head 守恒

```
$ python -m alembic heads
105_fix_drift (head)
```

✅ 守恒: 单 head `105_fix_drift` (W-N-DEPLOY 收口后无 alembic 改动, 派工 brief 严禁改 alembic/versions/).

### 2.2 件 2: pytest 沿用基线

- 派工范畴不涉及 pytest, 沿用 W-N-DEPLOY 收口基线 (W100 +49..+58 chat UI 14/14 + W100 RAG 6 批 242/242 + W100 +68..+74 e2e 7/7 + W100 +34..+38 meeting pipeline 44/44 = pytest 全套件 300+ PASS)
- 0 test pollution: 本任务未运行 pytest, 无任何 test 改动
- ✅ 守恒

### 2.3 件 3: PWA build 沿用基线

- 派工范畴不涉及 frontend
- 沿用 W100 +58 PWA build PASS 基线 (vite-plugin-pwa disable: true, manifest hash 守恒)
- 0 dist 改动: 本任务无 `web/` 任何文件改动
- ✅ 守恒

### 2.4 件 4: 0 production code 改动铁律

```
$ git diff 74d1a965e -- app/ web/src/ alembic/versions/ package.json requirements.txt
(空输出)
```

✅ 守恒: 严格 0 production code 改动. 仅 3 文件 (1 docs + 2 memory).

### 2.5 件 5: 锚点范式 W-N-P3-A +0..+2 守恒

```
W-N-P3-A +0  → memory/w-n-p3-a-prisma-eval-startup-2026-08-05.md  (commit 待主拍)
W-N-P3-A +1  → docs/w-n-p3-a-prisma-eval-2026-08-05.md              (commit 待主拍)
W-N-P3-A +2  → memory/w-n-p3-a-prisma-eval-closure-2026-08-05.md    (commit 待主拍)
```

✅ 守恒: 锚点编号 W-N-P3-A +0..+2, 据实累计 3 commits (派工 brief 估 3 commits, 实测 3 commits, **完美守恒**).

## 3. 决策建议摘要

### 3.1 三选项 ROI 对照

| 选项 | 投入 | 收益 | 风险 | 建议 |
|------|------|------|------|------|
| (a) 启动集成 | 11.5-15 周 | < 5% | ★★★★★ | **强烈不推荐** |
| (b) 暂不启动 | 0 | 维持 | 0 | **采纳 (推荐)** |
| (c) 试点 1-2 表 | 1-2 周 | 验证 | ★★★ | 可选 |

### 3.2 决策依据 5 条

1. **ROI 负值**: 11.5-15 周 vs < 5% 收益 (派工 brief 估 3-5 周, 实测偏上限 3-4 倍)
2. **范式成熟**: SQLAlchemy 2.0 + alembic 96 串单链 + pgvector 集成, 无明确痛点
3. **风险红线**: alembic 链断裂 + pgvector/halfvec 退化 = 灾难级
4. **团队现状**: 20 人已用 1+ 年, 切换成本极高
5. **W19 选项 A**: Phase 8.5 / P3 dedup / P3 跨 tab / 7 E2E 优先做

### 3.3 何时重新评估 (4 触发条件)

- Prisma 官方支持 pgvector
- 团队规模扩大 + 引入 TS/Go 前端
- alembic 链出现痛点 (目前无)
- 部署链频繁断裂 (目前稳定)

## 4. 类 20 沉淀 (本任务新增)

### 4.1 类 20.153 (新): Prisma 集成 ROI 评估结论 (本任务派生)

- **铁律**: 任何 ORM 切换评估必须 5 维实测 — 文件数 + 行数 + class 数 + migration 数 + PG-specific 特性数. 仅凭派工 brief 估算投入会严重低估 3-4 倍
- **实战**: 本任务实测 40 文件 / 4233 行 / 70 classes / 96 migrations / 76 PG-specific, 派工 brief 估 3-5 周实测 11.5-15 周
- **决策守恒**: W19 选项 A 维持 (Phase 8.5 / P3 dedup / P3 跨 tab / 7 E2E 留未来 PR, ORM 切换不进)

### 4.2 类 20.154 (新): pgvector/halfvec ORM 切换风险红线

- **铁律**: 任何 ORM 切换评估必查 pgvector/HALFVEC 支持. Prisma 官方不支持 = RAG 质量退化 + 性能损失 = 红线
- **实战**: models/knowledge.py (464 行) + kg_entity.py + knowledge_chunk.py 均用 `Vector(dim)`, W100 +100/101/102 演进 halfvec (pgvector 0.7.0+ 特性)
- **决策守恒**: 切换 ORM 必须先确认目标 ORM 支持向量类型 + 半精度, 否则维持现状

## 5. 派工 brief 严格遵守清单

- ✅ 0 改 W-N-A/B/C/D/E/F/D+/+/ARC/GC/ANC/MEM/G+/OBS/RAG/BGE/GRAND/FILL/D++ commits
- ✅ 0 改 alembic/versions/
- ✅ 0 改 app/models/ 任何文件
- ✅ 0 改 package.json / requirements.txt
- ✅ 锚点范式 W-N-P3-A +0..+2 守恒
- ✅ 派工前 base head 验证 `74d1a965e` 守恒
- ✅ 0 改 plan 文件
- ✅ 严禁启动 P3-A 集成实施 (派工 brief 严禁)

## 6. 关联沉淀索引

### 6.1 本任务 3 文件

- `memory/w-n-p3-a-prisma-eval-startup-2026-08-05.md` (+0 起步)
- `docs/w-n-p3-a-prisma-eval-2026-08-05.md` (+1 评估主报告)
- `memory/w-n-p3-a-prisma-eval-closure-2026-08-05.md` (+2 收口, 本文件)

### 6.2 历史参考

- `CLAUDE.md` "W19 选项 A 维持" 段 (Phase 8.5 / P3 dedup / P3 跨 tab / 7 E2E 留未来 PR)
- W72 +1 P3-A..P3-E 后续 PR 列表
- W97 PR2 knowledge_chunk pgvector parent-child chunking
- W100 +100/101/102 halfvec 演进
- W-N-DEPLOY 收口 (base `74d1a965e`)
- 类 20.46 base ref 漂移拦截
- 类 20.32 协调 base 实测
- 类 20.109 调研标"推断"必先实测
- 类 20.153 ORM 切换 ROI 评估结论 (本任务新增)
- 类 20.154 pgvector/halfvec ORM 切换风险红线 (本任务新增)

## 7. W-N-P3-A +N 后续

- **本任务完结**: W-N-P3-A +0..+2 据实累计 3 commits, 0 production code
- **未来重评估触发**: 见 §3.3 (4 触发条件)
- **季度复盘节奏**: 1 次/季度, 跟踪 Prisma pgvector 支持进度
- **W-N-P3-B..P3-E**: 与本任务无关, 由主拍按 W72 +1 列表派工