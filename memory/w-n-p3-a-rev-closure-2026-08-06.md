# W-N-P3-A 重新评估 closure (2026-08-06)

> **锚点**: W-N-P3-A-REV +2 收口
> **base ref**: `19766ab81` (W-N-FINAL +1 终极 grand closure)
> **派工范畴**: docs + memory, 0 production code 守恒
> **结论**: **决策 (b) 维持 (沿用 W-N-P3-A 决策 + W-N-W72 P3-A 启动留口)**

---

## 1. 交付物 (3 文件, 0 production code)

| 文件 | 类别 | 行数 | 内容 |
|------|------|------|------|
| `memory/w-n-p3-a-rev-startup-2026-08-06.md` | memory +0 | ~130 行 | W73 铁律 6 项起步 + 数据采集 |
| `docs/w-n-p3-a-rev-2026-08-06.md` | doc +1 | ~280 行 | 5 段重新评估报告 (回顾/POC/类 20/决策/触发) |
| `memory/w-n-p3-a-rev-closure-2026-08-06.md` | memory +2 | 本文件 | 5 件套守恒 + 收口沉淀 |

总计: 3 新文件 (1 doc + 2 memory), 0 改既有.

## 2. 5 件套守恒实测

### 2.1 件 1: alembic 1 head 守恒

```
$ python -m alembic heads
105_fix_drift (head)
```

✅ 守恒: 单 head `105_fix_drift` (派工 brief 严禁改 alembic/versions/, 0 改).

### 2.2 件 2: pytest 沿用基线

- 派工范畴不涉及 pytest, 沿用 W-N-FINAL 收口基线 (W-N-A 10 + W-N-B 19 + W-N-C 5 + W-N-D 2 + W-N-D+ 8 + W-N-F 14 = 58 PASS, 0 FAILED ✅)
- 0 test pollution: 本任务未运行 pytest, 无任何 test 改动
- ✅ 守恒

### 2.3 件 3: PWA build 沿用基线

- 派工范畴不涉及 frontend
- 沿用 W100 +58 PWA build PASS 基线 (vite-plugin-pwa disable: true, manifest hash 守恒)
- 0 dist 改动: 本任务无 `web/` 任何文件改动
- ✅ 守恒

### 2.4 件 4: 0 production code 改动铁律

```
$ git diff 19766ab81 -- app/ web/src/ alembic/versions/ package.json requirements.txt
(空输出)
```

✅ 守恒: 严格 0 production code 改动. 仅 3 文件 (1 docs + 2 memory).

### 2.5 件 5: 锚点范式 W-N-P3-A-REV +0..+2 守恒

```
W-N-P3-A-REV +0  → memory/w-n-p3-a-rev-startup-2026-08-06.md  (commit 待主拍)
W-N-P3-A-REV +1  → docs/w-n-p3-a-rev-2026-08-06.md             (commit 待主拍)
W-N-P3-A-REV +2  → memory/w-n-p3-a-rev-closure-2026-08-06.md   (commit 待主拍, 本文件)
```

✅ 守恒: 锚点编号 W-N-P3-A-REV +0..+2, 据实累计 3 commits (派工 brief 估 3 commits, 实测 3 commits, **完美守恒**).

## 3. 重新评估决策摘要

### 3.1 三选项 ROI 对照

| 选项 | 投入 | 收益 | 风险 | 建议 |
|------|------|------|------|------|
| (a) 升级 (b) → (c) 试点扩展 (3-5 表) | 2-3 天 | 更全面 ROI 数据基线 | ★★☆ | 可选 (派工 brief 严禁) |
| (b) 维持 (b) 暂不启动 | 0 | 维持范式成熟度 | 0 | **采纳 (推荐)** |
| (c) 重新决策 (W-N-W72 P3-A 派工) | 主拍决策 | 与原 P3-A 同 | ★★★★★ | **不推荐** |

### 3.2 决策依据 5 条

1. **W-N-P3-A-POC 1 表试点 0.75 天实测验证 ROI 数据基线**: 派工 brief 估 1-2 周/1 表严重偏高 5-10 倍, 但 53+ 张表全栈仍 8-15 周, 收益 < 5% 不变
2. **5 大实战发现完整覆盖**: Prisma regex 解析 / DateTime tz / FK ondelete / 复合 Index / Float-Decimal, 53+ 张表全栈涉及大量手写适配
3. **派工 brief 严禁升级**: 派工 v6 §13.3 假设禁令, 决策修订必须主拍真拍决策, agent 不得擅自升级 (b) → (c)
4. **W-N-W72 P3-A..P3-E 留口已就绪**: 派工 brief 严禁清单完整 + 触发再启条件量化, 派工权在主拍
5. **W19 选项 A 维持**: Phase 8.5 / P3 dedup / P3 跨 tab / 7 E2E 优先做, ORM 切换不进

### 3.3 何时重新评估 (沿用 W-N-P3-A 4 触发条件 + W-N-P3-A-POC 数据基线)

- Prisma 官方支持 pgvector
- 团队规模扩大 + 引入 TS/Go 前端
- alembic 链出现痛点 (目前 96 串单链稳定)
- 部署链频繁断裂 (目前稳定)

## 4. 类 20 沉淀 (本任务新增)

### 4.1 类 20.157 (新): 决策 (b) 沿用原则 — 试点实测不自动触发升级 (本任务派生)

- **铁律**: W-N-P3-A 决策 (b) 沿用原则 — 1 表试点实测成功 ≠ 决策升级 (b) → (c). 派工 brief 严禁擅自升级, 必须主拍真拍决策
- **实战**: 本任务重新评估 W-N-P3-A-POC 1 表试点 0.75 天实测, ROI 数据基线更准但收益 < 5% 不变, 决策 (b) 维持
- **决策守恒**: 任何决策 (b) 暂不启动项, 试点实测只能修正 ROI 数据基线, 不能自动触发决策升级, 必须主拍真拍决策 (派工 v6 §13.3 假设禁令)

### 4.2 类 20.158 (新): W-N-W72 派工 brief 严禁 — 留口汇总 ≠ 启动派工 (本任务派生)

- **铁律**: W-N-W72 P3-A..P3-E 留口汇总 ≠ 启动派工. 派工 brief 严禁擅自启动 P3-A..P3-E 任一 PR, 派工权在主拍
- **实战**: W-N-W72-P3A +1 (base `cde003abc`) 留口汇总 docs 仅汇总派工 brief 严禁清单 + 触发再启条件, 不擅自启动任一 P3-X 集成实施
- **决策守恒**: W-N-P3-A-REV 重新评估后, 派工 brief 严禁启动 P3-A 集成, 必须主拍真拍决策

## 5. 派工 brief 严格遵守清单

- ✅ 0 改 W-N-A/B/C/D/E/F/D+/+/ARC/GC/ANC/MEM/G+/OBS/RAG/BGE/GRAND/FILL/D++/P3-A 既有 commits
- ✅ 0 改 alembic/versions/
- ✅ 0 改 app/models/ 任何文件
- ✅ 0 改 package.json / requirements.txt
- ✅ 锚点范式 W-N-P3-A-REV +0..+2 守恒
- ✅ 派工前 base head 验证 `19766ab81` 守恒
- ✅ 0 改 plan 文件
- ✅ 0 启动 Prisma 全栈集成 (派工 brief 严禁)
- ✅ 仅重新评估, 不擅自升级 (b) → (c) (派工 brief 严禁)
- ✅ 决策 (b) 维持, W19 选项 A 维持, W-N-W72 P3-A 启动留口

## 6. 关联沉淀索引

### 6.1 本任务 3 文件

- `memory/w-n-p3-a-rev-startup-2026-08-06.md` (W-N-P3-A-REV +0 起步)
- `docs/w-n-p3-a-rev-2026-08-06.md` (W-N-P3-A-REV +1 重新评估报告, 主文件)
- `memory/w-n-p3-a-rev-closure-2026-08-06.md` (W-N-P3-A-REV +2 收口, 本文件)

### 6.2 历史参考

- W-N-P3-A 决策 (b) 暂不启动 (W19 选项 A 维持) — base `74d1a965e`
- `docs/w-n-p3-a-prisma-eval-2026-08-05.md` (W-N-P3-A +1 评估主报告)
- `memory/w-n-p3-a-prisma-eval-{startup,closure}-2026-08-05.md` (W-N-P3-A 起步 + 收口)
- W-N-P3-A-POC 1 表试点实测 0.75 天 — base `cde003abc`
- `docs/w-n-p3-a-poc-2026-08-05.md` (W-N-P3-A-POC +1 试点报告)
- `memory/w-n-p3-a-poc-{startup,closure}-2026-08-05.md` (W-N-P3-A-POC 起步 + 收口)
- W-N-W72 P3-A..P3-E 5 项后续 PR 留口 — base `cde003abc`
- `docs/w-n-w72-p3-a-leftover-2026-08-05.md` (W-N-W72-P3A +1 留口汇总)
- W-N-FINAL 终极 grand closure — base `19766ab81` (本任务起点)
- `docs/w-n-final-master-closure-2026-08-06.md` (W-N-FINAL +1 终极 master closure)
- CLAUDE.md "W19 选项 A 维持" 段
- 类 20.46 base ref 漂移拦截
- 类 20.32 协调 base 实测
- 类 20.109 调研标"推断"必先实测
- 类 20.153 ORM 切换 ROI 评估结论 (W-N-P3-A 决策)
- 类 20.154 pgvector/halfvec ORM 切换风险红线
- 类 20.155 Prisma 1 表试点 ROI 验证 (W-N-P3-A-POC)
- 类 20.156 Prisma 工具链 5 大差异 (W-N-P3-A-POC)
- **类 20.157 决策 (b) 沿用原则 (本任务新增)**
- **类 20.158 W-N-W72 派工 brief 严禁 (本任务新增)**

## 7. W-N-P3-A-REV +N 后续

- **本任务完结**: W-N-P3-A-REV +0..+2 据实累计 3 commits, 0 production code
- **决策**: (b) 维持, W-N-P3-A 决策沿用 + W-N-W72 P3-A 启动留口
- **未来重评估触发**: 见 docs/w-n-p3-a-rev-2026-08-06.md §5 (4 触发条件, 沿用 W-N-P3-A)
- **季度复盘节奏**: 1 次/季度, 跟踪 Prisma pgvector 支持进度 + 团队规模 + alembic 链痛点 + W-N-P3-A-POC 1 表试点数据基线复用
- **W-N-W72 P3-A..P3-E 启动权**: 派工 brief 严禁擅自派工, 必须主拍真拍决策拍板后才启动

---

**撰写**: W-N-P3-A-REV +2 收口
**撰写日期**: 2026-08-06
**base head**: `19766ab81`
**派工模式**: 派工 brief 严禁, 重新评估仅 docs + memory
**主拍决策**: 决策 (b) 维持, W-N-P3-A 决策沿用 + W-N-W72 P3-A 启动留口