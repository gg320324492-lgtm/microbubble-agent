# W68 第 9 批 A-2: CLAUDE.md 顶部永久沉淀 W68 第 8 批锚点范式 (90 → 102)

> **锚点范式第 106 守恒** (CLAUDE.md + ROADMAP.md 顶部永久纪律固化, W68 第 9 批 A-2).
> 详见 `memory/w68-route-9-a2-claudmd-anchor-2026-07-24.md`.

## TL;DR

W68 第 9 批 A-2 agent (本任务) 把 W68 第 8 批 grand closure 的关键成果与锚点范式数字
(87 → 102, 15 守恒) 永久沉淀到 CLAUDE.md + ROADMAP.md 顶部 + memory/MEMORY.md 索引.
**0 production code 改动铁律 100% 维持** (纯 docs + memory 范畴).

## W68 第 8 批 grand closure 核心数据

| 维度 | 数据 | 备注 |
|------|------|------|
| 派工 agents | 15 | A-1 合并 + A-2 PR9-11 runbook + A-3 部署验证 + B-1 PR11 + B-2 PR12 + B-3 Mobile v3.2 + B-4 qa-bench D6 + C-1 hot-fix #18 + C-2 cleanup + C-3 grand closure + D-1 W68 第 7 批 6 小修 + D-2 docs 同步 + D-3 CLAUDE.md 沉淀 + D-4 hot-fix #18 监控 + D-5 任务模式最终验证 |
| 锚点范式 | 87 → 102 (+15 守恒) | 单调上升, 0 regression |
| 0 production code 改动铁律 | 12/15 守恒 | 3 例外已批: B-1 PR11 + B-2 PR12 + B-3 Mobile v3.2 |
| W19 选项 A | 维持 | 4 留未来 PR |
| alembic 单链 | 062→063→064→065→066→067 | 6 串单链迁移, 0 双头 |
| 任务模式基调 | plans 优先 + 小修搭配 | W68 第 5/6/7/8 批 4 批实战彻底验证 |

## 5 新铁律沉淀 (本任务)

1. **永久锚点必沉淀** — 跨多批次的纪律/数据/成果, 不只写在 memory/, 必须固化到 CLAUDE.md 顶部 + ROADMAP.md 顶部, 让未来会话读到 CLAUDE.md 即可了解所有审计/闭环/守恒纪律.
2. **单链验证** — alembic 并行派 agent 必须明确 `down_revision` 接续关系, merge 后立即 verify 只 1 个 head (`alembic upgrade head` 不报 Multiple head revisions). 0 双头.
3. **baseline 守恒** — 跨 PR / 跨批次 / 跨主指挥亲自修必须保持 baseline (test_baseline_audit.py) 不变. W68 第 8 批 30+ commit 0 regression.
4. **alembic 串单链纪律** — 串单链顺序按业务时间线排列: PR9 评论 (062) → PR9 版本 (063) → PR10 协同 (064) → PWA push (065) → PR11 path (066) → PR12 reactions (067). 一次只允许 1 个 head.
5. **主指挥拍板才改老路径** — 任何修改 `app/` `web/src/` `alembic/versions/` 老路径必须主指挥拍板 + 显式标"例外已批"才能 commit. 纯 docs/memory/scripts/ 范畴 agent 可自主 commit.

## 范围 (本任务不动)

- ❌ `app/` `web/src/` `alembic/versions/` 老路径 — 0 production code 改动铁律维持
- ❌ 修改 `app/services/task_service.py`/`meeting_service.py`/`knowledge_service.py` 等老模块的核心函数
- ❌ 修改 `web/src/views/Desktop*/index.vue` 老桌面页面组件
- ❌ 修改 `alembic/versions/0XX_老.py` 老迁移的 down_revision/up_revision

## 范围 (本任务允许)

- ✅ 修改 `CLAUDE.md` 顶部 `## 当前状态` 段, 追加 W68 第 8 批 grand closure 子段
- ✅ 修改 `ROADMAP.md` 顶部 `## 当前状态` 段, 同步追加 W68 第 8 批 grand closure 子段
- ✅ 修改 `memory/MEMORY.md` 加 1 行 W68 第 8 批 grand closure 索引行 (与 C-3 已加行并存)
- ✅ 新增 `memory/w68-route-9-a2-claudmd-anchor-2026-07-24.md` (本文档)

## 关联沉淀

- `CLAUDE.md` `## 当前状态` 顶部永久段: W68 第 8 批 grand closure (15 agents + 锚点范式 102 + 0 production code 改动铁律 + W19 选项 A + 任务模式基调)
- `ROADMAP.md` `## 当前状态` 顶部永久段: 同步追加
- `memory/MEMORY.md`: 加 1 行索引
- `memory/w68-grand-closure-8th-batch-2026-07-24.md` (C-3 已建): 跨主题收口总报告
- `memory/w68-route-8-d3-claudmd-discipline-2026-07-24.md` (D-3 已建): W68 第 6+7 批纪律沉淀

## 与 W68 第 6+7 批纪律沉淀协同

W68 第 6+7 批纪律 (D-3 沉淀到 CLAUDE.md 的 `## W68 第 6+7 批纪律沉淀 (永久锚点)` 节) + W68 第 8 批 grand closure summary (本任务 A-2 沉淀到 CLAUDE.md 顶部 `## 当前状态` 节) = 永久纪律双层固化:
- 顶部 `## 当前状态` 节: 跨批次数据 / commits / 锚点范式数字 (102) / W19 选项 A
- 中部 `## W68 第 6+7 批纪律沉淀 (永久锚点)` 节: 永久纪律铁律 / plans 审计纪律 / 0 production code 改动铁律例外清单

未来会话读 CLAUDE.md 即可访问全部 W68 跨主题永久纪律.

## 完成定义 (本任务)

- [x] CLAUDE.md `## 当前状态` 段追加 W68 第 8 批 grand closure 子段
- [x] ROADMAP.md `## 当前状态` 段同步追加 W68 第 8 批 grand closure 子段
- [x] memory/MEMORY.md 加 1 行 W68 第 8 批 grand closure 索引
- [x] memory/w68-route-9-a2-claudmd-anchor-2026-07-24.md (本文档) 创建
- [x] commit hash + push 成功

## 验证 (合并后)

- `git log --oneline -5 main` 看到本任务 commit (锚点范式第 106 守恒)
- `grep "W68 第 8 批 grand closure" CLAUDE.md` 命中顶部状态段
- `grep "W68 第 8 批 grand closure" ROADMAP.md` 命中顶部状态段
- `grep "W68 第 8 批 A-2" memory/MEMORY.md` 命中索引行

## 任务模式基调永久化

W68 第 4 批主指挥拍板的"plans 优先 + 小修搭配"基调用 W68 第 4+5+6+7+8 批 5 批实战验证
(累计 60+ agents 派工) 彻底固化. 未来 4-9 阶段流程:

1. 调研现有 plans list remaining
2. 主指挥拍板 plan 实施优先级
3. 派工实施 plan
4. 顺路小修 (fallback / cleanup / doc 同步)

不强求 plans 100%, 主指挥拍板决定节奏. W19 选项 A 4 留未来 PR 维持.