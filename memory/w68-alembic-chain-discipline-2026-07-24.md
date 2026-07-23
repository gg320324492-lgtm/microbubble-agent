# 2026-07-24 W68 alembic 并行 agent 串单链纪律 (锚点范式第 46 守恒)

> **一句话**: W68 第 3 批 F-1 + F-2 两个 agent 并行写 alembic migration, 都 `down_revision=061` → merge 后 Multiple head revisions → 主指挥改 063 接 062 串成单链 (commit `1852468a6`)。5 条新铁律沉淀到 CLAUDE.md「2026-07-24 alembic 并行 agent 串单链纪律」节。**0 production code 改动铁律维持** (本次纪律沉淀仅 docs + memory)。

## 定位

- **锚点范式**: 第 46 守恒 (W68 第 4 批纪律沉淀段)
- **上游锚点**: `multi-agent-task-orchestration-baseline.md` (4 阶段流程 + 11 协调铁律) — 本次是"派工 prompt 边界不明确"类协调事故的第一个 alembic 实例
- **同类先例**: 053/054/055/056 四连 CI unique 迁移 (PR6-P13~P16) — 当时**串行**派工, 每张迁移严格单链, 0 事故。W68 第 3 批首次**并行**派两个 migration agent, 立即踩坑
- **main HEAD (修复时)**: `1852468a6` → 后续 merge 链至 `26c7c5620`

## 完整时间线

### T0: W68 第 3 批派工 (2026-07-24 凌晨)

主指挥并行派 3 个 Drive v2 PR9 路线 agent:

| Agent | 路线 | 交付 | alembic |
|---|---|---|---|
| F-1 | 评论 thread 后端 | branch `feat/drive-v2-pr9-comments-2026-07-24` (commit `0bfe36751`) | `062_drive_comments.py` |
| F-2 | 文件版本历史 | branch `feat/drive-v2-pr9-versions-2026-07-24` (commit `04e06f6fd`) | `063_drive_file_versions.py` |
| F-3 | 移动端评论 UI | branch `feat/mobile-drive-comments-ui-2026-07-24` (commit `a6f183511`) | 无 (纯前端) |

**派工 prompt 缺陷**: F-1 / F-2 的 prompt 都只写"alembic 接现有链最新 (061_drive_folder_share)", **没有写两者之间的接续关系** (因为并行, 派工时两个编号都还不存在)。

### T1: 两 agent 各自交付

- F-1: `062_drive_comments.py` → `down_revision = "061_drive_folder_share"` ✅ (对它自己而言合理)
- F-2: `063_drive_file_versions.py` → `down_revision = "061_drive_folder_share"` ⚠️ (它不知道 062 存在)

各自 branch 内 `alembic upgrade head` 都 PASS — **单 branch 视角完全正常, 问题只在 merge 后暴露**。

### T2: H-1 agent 派工发现 (部署文档路线)

W68 第 3 批同时派了 H-1 agent 写 Drive v2 PR9 部署文档。H-1 在梳理三个 branch 的迁移时**第一个发现**双头问题, 在交付物中记录:

- `docs/drive-v2-pr9-deployment.md` **第 0 节「⚠️ 部署前必读: alembic 双头 (multi-head) 问题」** — 完整复现 + 两种解法对比:
  - **解法 A (推荐)**: merge 后改 063 `down_revision = "062_drive_comments"` 串单链
  - **解法 B (不推荐)**: `alembic upgrade heads` 保持双头 — `alembic current` 显示两个 revision, `downgrade -1` 语义歧义 (需要 `062_drive_comments@-1` 分支限定语法), 未来 064 接链需要 `alembic merge` 留坑
- `docs/drive-v2-pr9-rollout-checklist.md` **checklist 1.1** — merge 顺序 + verify 步骤

### T3: 主指挥 merge 修复 (commit `1852468a6`)

主指挥采纳解法 A:

1. 先 merge F-1 (062, 上游)
2. merge F-2 时改一行:
   ```python
   # alembic/versions/063_drive_file_versions.py
   down_revision: Union[str, None] = "062_drive_comments"   # 原为 061_drive_folder_share
   ```
3. commit `1852468a6 fix(alembic): 063 drive_file_versions 接 062_drive_comments (串单链, 防 merge 多头)`
4. verify: `ScriptDirectory.get_heads()` → `['063_drive_file_versions']` 单 head ✅

链最终形态: `... → 061_drive_folder_share → 062_drive_comments → 063_drive_file_versions` (单链)。

### T4: W68 第 4 批纪律沉淀 (本 memory)

主指挥调研发现: H-1 部署文档 + checklist 已记录**流程**, 但 CLAUDE.md **未沉淀为永久铁律** — 下次并行派 migration agent 仍会踩同一坑 (部署文档是 per-PR 的, CLAUDE.md 是每会话必读的)。→ 派本 agent 补 3 文件:

1. CLAUDE.md 新增「### 2026-07-24 alembic 并行 agent 串单链纪律 (commit `1852468a6`)」节 (放在 PWA manifest 410 回归段之后, 同类事故段格式)
2. ROADMAP.md 顶部 W68 段追加简短引用
3. 本 memory 文件

## 根因分析 (3 层)

1. **表层**: 062 + 063 都 `down_revision="061_drive_folder_share"` → alembic 链分叉 → `Multiple head revisions are present`
2. **中层**: 并行开发的两个 agent **互相不可见** — 各自 branch 里链都是合法单链, CI / 本地测试全绿, 问题只在 merge 时刻出现。这是"分布式开发 + 全局单链约束"的经典冲突 (类比: 两人同时基于同一 commit 开 PR 改同一行)
3. **深层**: 派工 prompt 没有把 alembic 的**全局单链约束**显式传递给 worker agent。worker 只知道"接最新", 不知道"还有一个兄弟 agent 也在接最新"。**协调层信息 (并行拓扑) 必须由主指挥在派工时注入, worker 自己推不出来**

## 5 条新铁律 (已写入 CLAUDE.md)

1. **并行派 alembic migration agent 必须明确接续关系** — 派工 prompt 必须写清楚"down_revision 接 X", 不写就默认接最新。两个 agent 同时接同一个上游 = merge 必双头。并行时主指挥应**预先分配编号 + 接续序** (如"F-1 写 062 接 061, F-2 写 063 接 062 (即使 062 还没 merge, 按约定编号写)")
2. **merge 顺序必须按 alembic 链** — 先 merge 最上游的 migration, 再 merge 下游的。不能并行 merge (无依赖关系时除外)
3. **merge 后立即 verify** — 期望只 1 个 head:
   ```bash
   python -c "from alembic.config import Config; from alembic.script import ScriptDirectory; c=Config(); c.set_main_option('script_location','alembic'); s=ScriptDirectory.from_config(c); print(s.get_heads())"
   # 期望输出: ['063_drive_file_versions'] (单元素 list)
   ```
4. **部署文档第 0 节必含 alembic chain 风险** — 任何写 alembic migration 的 PR 必须在部署文档顶部加"alembic 链风险"段, 提醒主指挥 merge 顺序 (H-1 的 `docs/drive-v2-pr9-deployment.md` 第 0 节是模板)
5. **跨 PR 部署 alembic 必须 cp + clear cache** — CLAUDE.md 752 行铁律升级:
   ```bash
   docker cp alembic/versions/0XX_*.py microbubble-agent-app-1:/app/alembic/versions/
   docker exec -e SKIP_DB_SETUP=1 microbubble-agent-app-1 rm -rf /app/alembic/versions/__pycache__
   docker exec microbubble-agent-app-1 alembic upgrade head
   ```
   `__pycache__` 残留会让容器内老 `down_revision` 继续生效 → 双头"假修复" (源码改了但 pyc 没变), 症状与未修复完全一致, 极难排查

## 为什么不用解法 B (`upgrade heads`)

| 维度 | 解法 A 串单链 | 解法 B 保持双头 |
|---|---|---|
| `alembic upgrade head` | ✅ 正常 | ❌ 报错, 必须 `heads` 复数 |
| `alembic current` | 1 个 revision | 2 个 revision (困惑) |
| `downgrade -1` | ✅ 正常 | ❌ 语义歧义, 需 `062_drive_comments@-1` 分支限定 |
| 未来 064 接链 | 直接接 063 | 需要 `alembic merge` 生成 merge revision (链图永久复杂化) |
| 改动成本 | 1 行 (merge 时) | 0 行 (但债务后置) |

解法 B 唯一适用场景: 紧急上线来不及改代码。本项目**永远选 A**。

## 与锚点范式的关系

- **锚点范式第 46 守恒**: 本次纪律沉淀 0 production code 改动 (修复 commit `1852468a6` 本身是 F-2 branch merge 的组成部分, 属 Drive v2 PR9 新功能范围, 不动 v1 老路径; 本沉淀 commit 仅 docs + memory), baseline 71 PASS + 7 SKIP 守恒不变
- **协调铁律扩展**: `multi-agent-task-orchestration-baseline.md` 的"边界立即拍板"铁律在本次的具体化 — **全局约束资源 (alembic 链 / 路由表 / 端口 / 唯一编号) 并行派工前必须由主指挥预分配**, 这是第 12 条协调铁律候选
- **锚点范式单调上升**: W7 12 → W66 27 → W67 28 → W68 30 → 第 46 守恒 (本次)

## 参考

- CLAUDE.md「### 2026-07-24 alembic 并行 agent 串单链纪律 (commit `1852468a6`)」(永久铁律, 本次新增)
- `docs/drive-v2-pr9-deployment.md` 第 0 节 (H-1, 双头问题完整复现 + 解法对比)
- `docs/drive-v2-pr9-rollout-checklist.md` 1.1 (merge 顺序 checklist)
- `memory/multi-agent-task-orchestration-baseline.md` (协调范式锚点)
- `memory/v2-drive-pr6-p13-username-ci-unique-2026-07-02.md` ~ P16 (053-056 串行单链先例)
- commit `1852468a6` (修复) / `0bfe36751` (F-1) / `04e06f6fd` (F-2)
