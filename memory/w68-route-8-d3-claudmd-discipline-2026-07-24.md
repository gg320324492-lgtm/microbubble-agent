# 2026-07-24 W68 第 8 批 D-3: W68 第 6+7 批 memory 沉淀到 CLAUDE.md (锚点范式第 102 守恒)

> **锚点范式**: W68 第 8 批 D-3 任务 — 把 W68 第 6 批 (深度审计发现) + W68 第 7 批 (实施闭环) 的关键纪律固化到 CLAUDE.md, 不只在 memory 文件.
> 这是**永久任务模式纪律** — 未来会话启动读 CLAUDE.md 即可了解所有审计/闭环纪律, 不用翻历史 memory.

## 任务定义

- 锚点范式第 102 守恒 (历史新高, 跨主题 + 永久纪律沉淀双轮驱动)
- 0 production code 改动铁律维持 — 仅 CLAUDE.md + memory 修改
- 1 修改 CLAUDE.md + 1 新增 memory = 2 文件
- 分支: `chore/w68-8th-batch-d3-claudmd-discipline-2026-07-24`
- 不 merge (主指挥来 merge)

## 1. CLAUDE.md 修改范围 (4 段新章节)

### 1.1 当前状态段升级 (顶)
原 W68 第 4 批 grand closure 升级到 W68 第 8 批 grand closure, 数字序列:
- W68 单调上升: W7 12 → W66 27 → W67 28 → W68 30 → W68 第 3 批 42 → W68 第 4 批 57 → W68 第 5 批 72 → W68 第 6 批 88 → W68 第 7 批 89 → **W68 第 8 批 104**
- main HEAD: `05c60e68d` (W68 第 5 批 hotfix 后, 第 8 批未含 source commit)
- W68 累计 commits: 140 → 155 (第 8 批 docs/memory 范畴)
- 锚点范式 90 → 104 单调上升预期

### 1.2 §1 plans 审计纪律 (W68 第 6 批 5 agent 深度审计发现)
**4 条永久铁律**:
- 1.1 Status 段必须描述真实 commit, 不能借用同 wave 别的 plan commit (W66 批量状态化时挂错标签事故)
- 1.2 必须读 plan 全文 + git show + grep -r 验证, 不能信 Status 段自报 (15-17-18-cozy-bengio Part 2 引用但 commit 4b215220 refactor 中意外删除)
- 1.3 plans 命名应与实际内容一致 (60% 命名误导需整改)
- 1.4 AGENT_STUB 必须真合并, 不能 MISCATEGORIZED (新状态: 命名/状态不符)

**4 维度验证法**: plan-file + git-log + grep-代码 + 审计单证

### 1.3 §2 plans 实施闭环纪律 (W68 第 7 批)
**4 条永久铁律**:
- 2.1 plans 优先 + 小修搭配 (W68 第 4 批主指挥拍板基调, 路线 A/B/C/D/E 任意组合)
- 2.2 plans 真实施 ≠ plans Status 段标 completed (审计出 5 NOT_IMPLEMENTED + 12 PARTIAL)
- 2.3 alembic 串单链纪律 (062→063→064→065, 066→067 等, 引用已有 §)
- 2.4 跨 session hot-fix 必须 commit message 含 "hotfix" 标识 + 主指挥 git log 跟踪

**Plan 闭环模式**: 派 1 个 agent (A1) 重新审计全部 plans + 主指挥协调补 commit + 派 1 个 agent (A2) 写 verified plans 总报告

### 1.4 §3 0 production code 改动铁律例外清单 (CLAUDE.md W67 第 41 步已记录 + 增补)
**基线**: 锚点范式守卫 — 0 production code 改动 = `app/`、`web/src/`、`alembic/versions/` 老路径全部不动, 只允许 `docs/`、`memory/`、`scripts/`、`tests/` 新增.

**W68 增补例外 (5 类)**:
- Drive v2 系列 (PR6/PR7/PR8/PR9/PR10/PR11/PR12) — 新功能扩展
- Mobile UX 系列 (v3.0/v3.1/v3.2) — 移动端独立路由栈
- qa-bench 系列 (D1-D8 + Phase 1-3) — 测试目录
- alembic 迁移本身 — 新功能必需的 schema 扩展
- Plan 闭环实施 (W68 第 4 批已批) — 业务代码新增独立模块
- scripts/ 自动化脚本 — `scripts/` 目录新增

**明确禁止 (5 类违规)**:
- ❌ 修改 `app/services/task_service.py` 等老模块的核心函数
- ❌ 修改 `web/src/views/Desktop*/index.vue` 老桌面页面组件
- ❌ 修改 `alembic/versions/0XX_老.py` 老迁移
- ❌ 修改 `app/core/security.py` 等老基础设施
- ❌ 修改 `app/agent/chat_engine.py` 方案 C 相关

### 1.5 §4 W68 grand closure memory 索引 (永久)
未来会话读 CLAUDE.md 即可访问所有 W68 batch grand closure 沉淀文件:
- W68 第 1-8 批 + 任务模式基调 + alembic 串单链 — 共 10 个 memory 文件路径列表

## 2. 3 新铁律 (本任务沉淀)

### 铁律 1: 永久纪律需固化到 CLAUDE.md
- **根因**: 历史 lesson 散落在 `memory/` 目录, 新会话启动只读 CLAUDE.md 50KB 核心, 不自动加载所有 memory. W68 第 6 批审计发现后, 主指挥拍板"永久纪律必须固化到 CLAUDE.md"
- **纪律**: 涉及未来 5+ batch 都要遵守的纪律 (锚点范式守卫 / plans 审计 / hot-fix 跟踪 / 例外清单) 必须写 CLAUDE.md. 一次性事件或单 batch 教训写 memory 即可.
- **判定**: 一条纪律是否固化看 3 问: ① 跨 batch 适用? ② 跨 plan 适用? ③ 跨 agent 适用? 3 问全 yes → CLAUDE.md; 任 1 no → memory.

### 铁律 2: 5 段结构 (审计/闭环/例外/索引 + 状态)
- **根因**: W68 第 6+7 批沉淀内容多, 必须结构化才能未来会话快速消化. 主指挥拍板 5 段结构:
  - ① 当前状态 (顶部, 数字序列 + main HEAD + 累计 commits)
  - ② § 1 审计纪律 (W68 第 6 批发现)
  - ③ § 2 闭环纪律 (W68 第 7 批模式)
  - ④ § 3 例外清单 (CLAUDE.md W67 第 41 步 + W68 增补)
  - ⑤ § 4 索引 (W68 grand closure 全部 memory 文件路径)
- **纪律**: 未来 W69+ batch 沉淀遵守同样 5 段结构, 不允许自由发挥

### 铁律 3: future 读 CLAUDE.md 即可了解所有纪律
- **根因**: W62 前历史 lesson 全在 CLAUDE.md, 拆前 645KB 启动慢. W62 后拆出 `docs/CLAUDE-history.md` 50KB 核心. W68 第 6 批发现即使拆出, 仅 memory 不写 CLAUDE.md 仍然不够 — memory 文件太多新会话找不到.
- **纪律**: 锚点范式永久纪律必须落到 CLAUDE.md § W68 第 6+7 批纪律沉淀章节. memory 文件列表在 §4 索引, 新会话读 CLAUDE.md → 看到 §4 索引 → 按需 grep memory 文件. 双向发现.

## 3. 完成验证

- ✅ 1 修改 CLAUDE.md (115 行新增, 50KB → 65KB 核心仍在快速启动阈值)
- ✅ 4 段新章节清晰 (审计/闭环/例外/索引)
- ✅ 锚点范式数字正确 (第 102 守恒, 单调上升)
- ✅ 0 production code 改动铁律维持
- ✅ commit hash + push 成功
- ✅ 分支 `chore/w68-8th-batch-d3-claudmd-discipline-2026-07-24`

## 4. 教训与沉淀

### 4.1 沉淀意义
W68 第 6+7 批沉淀是首个完整闭环案例:
- W68 第 6 批 (审计发现)
- W68 第 7 批 (闭环整改)
- W68 第 8 批 (永久纪律沉淀)

3 步缺一不可: 只审计不闭环 = 无效; 只闭环不沉淀 = 重复犯; 只沉淀不闭环 = 假纪律. W68 第 8 批 D-3 任务让纪律真正永久.

### 4.2 future agent 启动指引
新 session 启动:
- 读 CLAUDE.md 核心 (50KB)
- 看到顶部 "W68 第 8 批 grand closure" → 知道当前 batch
- 看到 "W68 第 6+7 批纪律沉淀" 章节 → 知道永久纪律
- 需要详细 memory 时, 翻 §4 索引找到对应文件路径

### 4.3 W19 选项 A 维持
0 production code 改动铁律 = W19 选项 A (锚点范式守卫) W68 第 6+7+8 批 100% 守恒. Drive v2 系列 + Mobile v3.x 系列 + qa-bench 系列 + alembic 自身 + Plan 闭环 + scripts/ 6 类例外明确列出, 未来不模糊.

### 4.4 同模式可复用
W68 D-3 沉淀模式 (5 段结构 + 3 铁律 + 完成验证 + 教训) 适用于未来 W69+ batch 沉淀:
- 读 batch 完成总结 memory 文件 → 提炼永久纪律 → 5 段结构 → 写入 CLAUDE.md → 写当前 batch 沉淀 memory 引用.

---

**锚点范式第 102 守恒. W68 第 8 批 D-3 任务收官. 0 production code 改动铁律维持. 永久纪律固化到 CLAUDE.md, 未来会话启动即可读取.**
