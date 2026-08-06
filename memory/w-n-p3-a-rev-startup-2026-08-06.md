# W-N-P3-A 重新评估 startup (2026-08-06)

> **锚点**: W-N-P3-A-REV +0 startup
> **base ref**: `19766ab81` (W-N-FINAL +1 终极 grand closure)
> **任务**: W-N-P3-A 决策 (b) 暂不启动 + W-N-P3-A-POC 1 表试点 ROI 验证 重新评估
> **派工范畴**: docs + memory, 严禁改 production code
> **派工模式**: 派工 brief 严禁擅自派工, 主拍真拍决策

---

## 1. 任务定位

W-N-P3-A 决策 (b) 暂不启动 (W19 选项 A 维持), W-N-P3-A-POC 1 表试点实测 0.75 天 (派工 brief 估 1-2 周). 本任务**重新评估**:
- W-N-P3-A 决策 (b) 是否沿用
- W-N-P3-A-POC 1 表试点实测是否触发决策修订 (b) → (c)
- 派工 brief 严禁擅自派工, 主拍真拍决策

派工 brief 明确:
- (a) 升级 (b) → (c) 试点扩展 (3-5 张表)
- (b) 维持 (b) 暂不启动
- (c) 重新决策 (W-N-W72 P3-A 派工)

**派工 brief 严禁**:
- 0 改 W-N-A/B/C/D/E/F/D+/+/ARC/GC/ANC/MEM/G+/OBS/RAG/BGE/GRAND/FILL/D++/P3-A 既有 commits
- 0 改 alembic/versions/
- 0 改 app/models/ 既有文件
- 0 改 package.json / requirements.txt
- 0 启动 Prisma 全栈集成
- 0 改 plan 文件
- 派工锚点: W-N-P3-A-REV +0 / +1

**允许范畴**:
- 新建 `docs/w-n-p3-a-rev-2026-08-06.md` (重新评估报告)
- 新建 `memory/w-n-p3-a-rev-startup-2026-08-06.md` (起步, 本文件)
- 新建 `memory/w-n-p3-a-rev-closure-2026-08-06.md` (收口)
- 共 3 文件, 0 production code

## 2. W73 铁律 6 项起步

### 2.1 派工 brief 验证 (类 20 沿用)
- 派工锚点: W-N-P3-A-REV +0..+2
- 派工 brief 严禁擅自派工 (派工 v6 §13.3 假设禁令, 派工权在主拍)
- 0 production code 改动铁律守恒: `app/models/` + `alembic/versions/` + `package.json` + `requirements.txt` 全部不动

### 2.2 base head 实测 (类 20.46 + 20.32 沿用)
```
$ git log --oneline -3
19766ab81 docs(memory): W-N-FINAL 3 untracked files commit 推 main (W-N-FINAL +1 终极 grand closure)
8dd8d2a16 docs(memory): W-N-GC-FINAL +2 收口沉淀 (5 件套守恒实测 + 派工 brief vs 实测 5 项据实 + W-N 周期 28 stages 累计 ~580 + 主拍彻底 grand closure 完成)
b3d496b31 docs(memory): W-N-CLEAN-FINAL 收口沉淀 (5 件套守恒实测 + 并发批次共存 + 类 20.140/101/146 沿用) (W-N-CLEAN-F +2)
```
守恒 ✅ (W-N-FINAL +1 终极 grand closure commit 顶部).

### 2.3 工作范畴界定 (派工 brief 严格遵守)
- 允许: 新建 `docs/w-n-p3-a-rev-2026-08-06.md` + `memory/w-n-p3-a-rev-{startup,closure}-2026-08-06.md` 共 3 文件
- 禁止: 改任何 `app/` `web/src/` `alembic/` `package.json` `requirements.txt`
- 禁止: 启动 Prisma 集成 (派工 brief 严禁, 仅评估)
- 禁止: 改 plan 文件 / 改 W-N 任何已沉淀 commit
- 禁止: 改 W-N-A/B/C/D/E/F/D+/+/ARC/GC/ANC/MEM/G+/OBS/RAG/BGE/GRAND/FILL/D++/P3-A 既有 commits

### 2.4 数据采集 (Step 1 起点)
- W-N-P3-A 决策 (b) 暂不启动 (W19 选项 A 维持) — base `74d1a965e` 守恒
- W-N-P3-A-POC 1 表试点实测 0.75 天 (派工 brief 估 1-2 周) — base `cde003abc` 守恒
- 5 大实战发现: Prisma regex 解析陷阱 / DateTime tz / FK ondelete / 复合 Index / Float-Decimal
- mock 测试 53/53 PASS (11 必填 + 22 类型 + 10 attrs + 7 字段数守恒 + 3 文件解析)
- W-N-W72 P3-A..P3-E 5 项后续 PR 留口 (派工 brief 严禁擅自派工)

### 2.5 关联风险点提前识别
- **派工 brief 严禁扩**: 仅重新评估, 不启动集成
- **决策 (b) → (c) 升级需主拍决策**: 派工 brief 严禁 agent 擅自升级
- **W-N-W72 P3-A 启动留口**: P3-A..P3-E 5 项后续 PR 列表就绪, 派工权在主拍

### 2.6 调研边界
- 调研标"推断"必先实测 (类 20.109 沿用)
- 不擅自扩范畴: 重新评估仅 3 文件, 不启动集成
- 派工 v6 §13 仓库实情真查: 不凭 CLAUDE.md 历史, 必须实测
- 派工 v6 §13.3 假设禁令: 派工 brief 严禁擅自派工

## 3. 起步状态实测

```
$ git log --oneline -3
19766ab81 docs(memory): W-N-FINAL 3 untracked files commit 推 main (W-N-FINAL +1 终极 grand closure)
8dd8d2a16 docs(memory): W-N-GC-FINAL +2 收口沉淀
b3d496b31 docs(memory): W-N-CLEAN-FINAL 收口沉淀
```

```
$ git status --short
(empty)
```

守恒: HEAD = `19766ab81`, 当前 branch = `main`, 0 commit ahead of base.

## 4. 下一步 (W-N-P3-A-REV +1)

- Step 1: 已读 `docs/w-n-p3-a-prisma-eval-2026-08-05.md` + `docs/w-n-p3-a-poc-2026-08-05.md` + `docs/w-n-final-master-closure-2026-08-06.md` P3-A 章节
- Step 2: 写 `docs/w-n-p3-a-rev-2026-08-06.md` (重新评估报告 5 段)
- Step 3: commit docs/memory 范畴
- Step 4: 写 `memory/w-n-p3-a-rev-closure-2026-08-06.md` (收口)

## 5. 关联沉淀索引

- W-N-P3-A 决策 (b) 暂不启动 (W19 选项 A 维持) — base `74d1a965e`
- W-N-P3-A-POC 1 表试点实测 0.75 天 — base `cde003abc`
- W-N-FINAL 终极 grand closure — base `19766ab81` (本任务起点)
- W-N-W72 P3-A..P3-E 5 项后续 PR 留口 (派工 brief 严禁擅自派工)
- 类 20.46 base ref 漂移拦截
- 类 20.32 协调 base 实测
- 类 20.109 调研标"推断"必先实测
- 类 20.153 ORM 切换 ROI 评估结论 (W-N-P3-A 决策)
- 类 20.154 pgvector/halfvec ORM 切换风险红线
- 类 20.155 Prisma 1 表试点 ROI 验证 (W-N-P3-A-POC)
- 类 20.156 Prisma 工具链 5 大差异 (W-N-P3-A-POC)

---

**撰写**: W-N-P3-A-REV +0 startup
**撰写日期**: 2026-08-06
**base head**: `19766ab81`
**派工模式**: 派工 brief 严禁, 重新评估仅 docs + memory