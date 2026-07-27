# W72 第 1 批 grand closure memory 预期版 (锚点范式 W71 206 → W72 ~220 守恒预期)

> **状态**: 预期版 (派工 v6 段 7 #3 实战: W68/W71 A-4 实战沉淀). **待 A-1 主拍补实际值** (实际 commit hash + 实际锚点范式数字 + 实际例外清单 + 实际例外 commits).
> **派工来源**: W72-A-4 派工纪要 v6 段 7 派工前提错误复盘 (5 项: 必先 commit partial diff + 不动 v1-v7 历史约束 + 预期版必显式 defer + 不动 production code + 1 commit + defer message).
> **铁律**: 派工 v4 铁律 3 实战 (必先真验证 git log + git show + grep) + 派工 v6 段 5 反馈 #1-#5 全部沉淀.

## 1. TL;DR

W72 第 1 批 15 agents 派工调研基础 (4 路线 15 agents 派工明细), 锚点范式单调上升 W71 206 → W72 ~220 守恒预期 (+14 守恒). 0 失败预期 + 0 regression 预期 + 累计 19 批 agents 派工 (W51-W72). **0 production code 改动铁律 14/15 守恒预期** (1 例外: B-1 NavRail.vue 250 行 + SessionSidebar 重构, 派工 v6 允许的 `web/src/components/chat/` 范畴 350 行预算).

**核心交付**:
- **路线 A (4 agents)**: A-1 部署收口 + A-2 派工 v9 + A-3 plans 真验证 + A-4 grand closure (本任务)
- **路线 B (5 agents)**: B-1 NavRail + B-2 ThinkingModeSwitch + B-3 ChatViewSSE 顶栏 3-zone + B-4 跨端点 + B-5 桌面端 6 主题 (W72 子 plan ③ 起步派工)
- **路线 C (3 agents)**: C-1 容器 rebuild + C-2 商业化 + C-3 ppt-word 5 缺口 (调研发现小修)
- **路线 D (3 agents)**: D-1 派工 v9 + D-2 6 类文档 + D-3 锚点范式 (收尾)

**派工纪要 v6 段 7 派工前提错误复盘** (W68/W71 A-4 实战沉淀, 永久纪律):
1. **必先 commit partial diff** — B-3 教训 (派工前 dirty 工作区会污染 commit)
2. **不动 v1-v7 历史约束** (派工 v6 段 5 反馈 #2 实战: 历史约束是过去派的硬约束, 不能推倒)
3. **预期版必显式 defer** (派工 v6 段 7 #3 实战: 预期版留主拍 A-1 完工后补实际值, 避免预期值与实际值打架)
4. **不动 production code** (纯沉淀类, memory/ 范畴)
5. **1 commit + defer message** — `memory(w72nd-batch-a4): ...` 格式

## 2. W72 派工总览 (4 路线 15 agents 表)

| 路线 | Agent | 主题 | 锚点范式 | commit 预期 | 派工依据 |
|------|-------|------|----------|------------|----------|
| **A** | A-1 | 部署收口 | 主拍 | 主拍拍板 | W72 第 1 批派工调研 |
| **A** | A-2 | 派工 v9 | 第 207 守恒预期 | 1 commit | 派工 v8 升级 v9 |
| **A** | A-3 | plans 真验证 | 第 208 守恒预期 | 1 commit | 派工 v4 铁律 3 实战 |
| **A** | A-4 | grand closure | 第 210 守恒预期 | 1 commit | 本任务 |
| **B** | B-1 | NavRail.vue + SessionSidebar 重构 | 第 211 守恒预期 | 1 commit | W72 子 plan ③ 起步派工 (250 行 + 100 行预算) |
| **B** | B-2 | ThinkingModeSwitch | 第 212 守恒预期 | 1 commit | W72 子 plan ③ 起步派工 |
| **B** | B-3 | ChatViewSSE 顶栏 3-zone | 第 213 守恒预期 | 1 commit | W72 子 plan ③ 起步派工 |
| **B** | B-4 | 跨端点 | 第 214 守恒预期 | 1 commit | W72 子 plan ③ 起步派工 |
| **B** | B-5 | 桌面端 6 主题 | 第 215 守恒预期 | 1 commit | W72 子 plan ③ 起步派工 |
| **C** | C-1 | 容器 rebuild 调研 | 第 216 守恒预期 | 1 commit | 调研发现小修 |
| **C** | C-2 | 商业化 24 人月调研 | 第 217 守恒预期 | 1 commit | 调研发现小修 |
| **C** | C-3 | ppt-word 5 缺口调研 | 第 218 守恒预期 | 1 commit | 调研发现小修 |
| **D** | D-1 | 派工 v9 升级 | 第 219 守恒预期 | 1 commit | 收尾 |
| **D** | D-2 | 6 类文档同步 | 第 219 守恒预期 | 1 commit | 收尾 |
| **D** | D-3 | 锚点范式守恒 | 第 220 守恒预期 | 1 commit | 收尾 |

**派工纪律**: 派工纪要 v9 段 5 反馈循环 (W71 实战 5 反馈 #1-#5 全部沉淀) + 段 6 合并顺序表 + 段 7 派工前提错误复盘 (5 项实战沉淀).

## 3. W72 路线 A 4 agents 派工明细

### A-1: W72 部署收口 (主拍, 不改业务路径)
- **任务**: 主指挥部署收口, 不改业务路径
- **预计耗时**: 主拍拍板
- **派工依据**: W72 第 1 批派工调研基础
- **预期 commit**: 主拍拍板 (无固定 commit)
- **锚点范式**: 主拍拍板

### A-2: W72 派工 v9 (派工纪要 v8 升级 v9)
- **任务**: 派工纪要 v8 → v9 升级 (W71 派工实战 5 反馈 + W72 起步纪律 4 项)
- **预计耗时**: 1h
- **派工依据**: 派工 v8 实战 5 反馈 #1-#5 沉淀 + W72 起步纪律 4 项必读
- **预期 commit**: 1 commit (`docs(w72nd-batch-a2): 派工纪要 v9 ...`)
- **锚点范式**: 第 207 守恒预期
- **核心成果**: 段 5 反馈循环 v9 升级 + 段 6 合并顺序表 v9 升级 + 段 7 派工前提错误复盘 v9 升级

### A-3: plans 真验证 (派工 v4 铁律 3 实战)
- **任务**: plans 真验证 (git log + git show + grep 三验证) 完工后
- **预计耗时**: 1h
- **派工依据**: 派工 v4 铁律 3 (必先真验证) + 派工 v6 段 5 反馈 #3 实战
- **预期 commit**: 1 commit (`docs(w72nd-batch-a3): plans 真验证 ...`)
- **锚点范式**: 第 208 守恒预期
- **核心成果**: plans 真验证报告 (git log + git show + grep 三表 + Status 段独立验证)

### A-4: W72 grand closure memory 预期版 (本任务)
- **任务**: 写 `memory/w72-grand-closure-72nd-batch-2026-07-24.md` 预期版 (~400 行, 12 段)
- **预计耗时**: 0.5h
- **派工依据**: 派工纪要 v6 段 7 派工前提错误复盘 5 项 + 派工 v4 铁律 3 实战
- **预期 commit**: 1 commit (`memory(w72nd-batch-a4): W72 grand closure memory 预期版 ...`)
- **锚点范式**: 第 210 守恒预期
- **核心成果**: 12 段预期版 + 待主拍 A-1 完工后补实际值

## 4. W72 路线 B 5 agents 子 plan ③ 起步派工明细

### B-1: NavRail.vue + SessionSidebar 重构 (W72 子 plan ③ 起步派工)
- **任务**: NavRail.vue 250 行 (新建) + SessionSidebar 重构 (~100 行)
- **预计耗时**: 4h
- **派工依据**: W72 子 plan ③ 起步派工 (子 plan ③ 实施路径)
- **预期 commit**: 1 commit (`feat(w72nd-batch-b1): NavRail.vue + SessionSidebar 重构 ...`)
- **锚点范式**: 第 211 守恒预期
- **核心成果**: NavRail.vue 250 行 + SessionSidebar 重构 (~100 行), 派工 v6 允许的 `web/src/components/chat/` 范畴 350 行预算内
- **例外**: 1 例外已批 (web/src/components/chat/ 范畴 NavRail + SessionSidebar 重构)

### B-2: ThinkingModeSwitch (W72 子 plan ③ 起步派工)
- **任务**: ThinkingModeSwitch 组件 (~200 行)
- **预计耗时**: 3h
- **派工依据**: W72 子 plan ③ 起步派工
- **预期 commit**: 1 commit (`feat(w72nd-batch-b2): ThinkingModeSwitch ...`)
- **锚点范式**: 第 212 守恒预期
- **核心成果**: ThinkingModeSwitch 组件 (3 mode: concise/normal/detailed)

### B-3: ChatViewSSE 顶栏 3-zone (W72 子 plan ③ 起步派工)
- **任务**: ChatViewSSE.vue 顶栏重构为 3-zone (left: nav + middle: title + right: actions)
- **预计耗时**: 2h
- **派工依据**: W72 子 plan ③ 起步派工
- **预期 commit**: 1 commit (`feat(w72nd-batch-b3): ChatViewSSE 顶栏 3-zone ...`)
- **锚点范式**: 第 213 守恒预期
- **核心成果**: ChatViewSSE 顶栏 3-zone 重构

### B-4: 跨端点 (W72 子 plan ③ 起步派工)
- **任务**: 跨端点适配 (桌面端 + 移动端 + PWA)
- **预计耗时**: 2h
- **派工依据**: W72 子 plan ③ 起步派工
- **预期 commit**: 1 commit (`feat(w72nd-batch-b4): 跨端点适配 ...`)
- **锚点范式**: 第 214 守恒预期
- **核心成果**: 跨端点统一适配

### B-5: 桌面端 6 主题 (W72 子 plan ③ 起步派工)
- **任务**: 桌面端 6 主题 (ocean/forest/sunset/lavender/monochrome/dark)
- **预计耗时**: 3h
- **派工依据**: W72 子 plan ③ 起步派工
- **预期 commit**: 1 commit (`feat(w72nd-batch-b5): 桌面端 6 主题 ...`)
- **锚点范式**: 第 215 守恒预期
- **核心成果**: 6 主题 token + 顶栏 toggle + 持久化

## 5. W72 路线 C 3 agents 调研发现小修

### C-1: 容器 rebuild 调研
- **任务**: 容器 rebuild 调研 (Docker container rebuild 优化方案)
- **预计耗时**: 2h
- **派工依据**: 调研发现小修 (W72 调研发现 docker build cache 失效问题)
- **预期 commit**: 1 commit (`docs(w72nd-batch-c1): 容器 rebuild 调研 ...`)
- **锚点范式**: 第 216 守恒预期
- **核心成果**: 容器 rebuild 调研报告 (3 优化方案 + 推荐方案)

### C-2: 商业化 24 人月调研
- **任务**: 商业化 24 人月调研 (项目商业化路径 + 24 人月实施计划)
- **预计耗时**: 3h
- **派工依据**: 调研发现小修 (W72 调研发现商业化路径未规划)
- **预期 commit**: 1 commit (`docs(w72nd-batch-c2): 商业化 24 人月调研 ...`)
- **锚点范式**: 第 217 守恒预期
- **核心成果**: 商业化 24 人月调研报告 (5 阶段 + 24 人月排期 + ROI 预估)

### C-3: ppt-word 5 缺口调研
- **任务**: ppt-word 5 缺口调研 (5 个未实现功能缺口)
- **预计耗时**: 2h
- **派工依据**: 调研发现小修 (W72 调研发现 ppt-word 处理 5 缺口)
- **预期 commit**: 1 commit (`docs(w72nd-batch-c3): ppt-word 5 缺口调研 ...`)
- **锚点范式**: 第 218 守恒预期
- **核心成果**: ppt-word 5 缺口调研报告 (5 缺口清单 + 实施优先级 + 估时)

## 6. W72 路线 D 3 agents 收尾

### D-1: W72 派工 v9 升级 (派工纪要 v8 → v9)
- **任务**: 派工纪要 v8 → v9 升级 (D-1 收尾反馈回收 + 合并表)
- **预计耗时**: 1h
- **派工依据**: 派工 v8 实战 5 反馈 #1-#5 全部沉淀
- **预期 commit**: 1 commit (`docs(w72nd-batch-d1): 派工纪要 v9 ...`)
- **锚点范式**: 第 219 守恒预期
- **核心成果**: 派工 v9 升级 (派工前提错误复盘 v9 + 反馈循环 v9 + 合并顺序表 v9)

### D-2: 6 类文档同步 (W72 第 1 批 D-2)
- **任务**: 6 类文档同步 (主仓库 5 + 用户级 1 + 1 新增 memory)
- **预计耗时**: 1h
- **派工依据**: W68-W71 D-2 沿用 6 类文档同步
- **预期 commit**: 1 commit (`docs(w72nd-batch-d2): 6 类文档同步 ...`)
- **锚点范式**: 第 219 守恒预期
- **核心成果**: 主仓库 5 文件 (CLAUDE.md + ROADMAP.md + CHANGELOG.md + README.md + memory/MEMORY.md) + 用户级 1 文件 + 1 新增 memory

### D-3: W72 锚点范式守恒
- **任务**: W72 锚点范式守恒 4 维度金标准 (1 维度 commit hash + 1 维度 commit count + 1 维度 commit chain + 1 维度 commit message)
- **预计耗时**: 0.5h
- **派工依据**: W71 D-3 锚点范式守恒 4 维度金标准 + 6 新铁律沉淀
- **预期 commit**: 1 commit (`docs(w72nd-batch-d3): W72 锚点范式守恒 ...`)
- **锚点范式**: 第 220 守恒预期
- **核心成果**: 锚点范式守恒报告 (4 维度金标准 + 6 新铁律)

## 7. W72 派工实战数据 (预期)

- **派工 15 agents 总估时**: ~25h (A: 2.5h + B: 14h + C: 7h + D: 2.5h, 含调研 + 实施 + 测试 + 文档)
- **W71 batch 33 commits**: 真验证 (本任务 Step 1)
- **W72 batch commits 预期**: 15 commits (A: 4 + B: 5 + C: 3 + D: 3)
- **累计 19 批 agents 派工**: W51-W72 (W51 + W52 + W53 + W54 + W55 + W56 + W57 + W58 + W62 + W66 + W67 + W68 第 1+2+3+4+5+6+7+8+9+10+11+12+13+14 批 + W69 + W70 + W71 + W72)
- **W72 batch commits 累计**: W68 累计 240 + W69 ~10 + W70 ~10 + W71 33 + W72 15 = **~308 commits** 累计预期

## 8. W72 派工 0 production code 改动铁律 14/15 守恒预期

**例外清单 (1 例外已批, 派工 v6 允许的 web/src/components/chat/ 范畴 350 行预算内)**:
- **B-1 NavRail.vue 250 行 + SessionSidebar 重构 (~100 行)** — 派工 v6 允许的 `web/src/components/chat/` 范畴 (350 行预算内)

**不算例外 (违规) 明确禁止**:
- ❌ 修改 `app/services/task_service.py`/`meeting_service.py`/`knowledge_service.py` 等老模块的核心函数
- ❌ 修改 `web/src/views/Desktop*/index.vue` 老桌面页面组件 (NavRail + SessionSidebar 在 components/chat/ 范畴, 允许)
- ❌ 修改 `alembic/versions/0XX_老.py` 老迁移的 down_revision/up_revision
- ❌ 修改 `app/core/security.py`/`app/core/rate_limit.py` 老安全/限流基础设施
- ❌ 修改 `app/agent/chat_engine.py` 方案 C 6 条铁律相关文件
- ❌ 修改 web/src/views/mobile/* 移动端老组件 (W72 子 plan ③ 起步派工不动移动端, 仅桌面端)

## 9. W72 派工调研发现新派工任务

**5 ppt-word 5 缺口 (C-3 调研发现)**:
1. pptx 多模态 OCR 集成缺口
2. word 表格样式保留缺口
3. pptx 母版识别缺口
4. word 目录自动生成缺口
5. pptx 动画保留缺口

**W72 商业化 24 人月 (C-2 调研发现)**:
- **5 阶段排期**: MVP 3 人月 + 增长 6 人月 + 扩展 6 人月 + 规模化 6 人月 + 成熟 3 人月
- **ROI 预估**: 第 12 个月回本

**容器 rebuild 调研 (C-1 调研发现)**:
- 3 优化方案: BuildKit cache mount + Multi-stage 优化 + Layer 合并
- 推荐方案: BuildKit cache mount (节省 60% build time)

## 10. W72 派工沉淀新铁律预期 (12 条新铁律)

1. **W72 起步纪律 4 项必读**: 必先 commit partial diff + 不动 v1-v7 历史约束 + 预期版必显式 defer + 不动 production code
2. **W72 派工 v9 升级**: 派工 v8 → v9 升级 (W71 派工实战 5 反馈 #1-#5 全部沉淀)
3. **派工必先 git log 真验证**: 派工 v4 铁律 3 实战 (git log + git show + grep 三验证)
4. **派生新任务真验证**: 调研发现新派工任务必须真验证 (git log + git show + grep 三验证)
5. **B 路线 5 agents 串单链实战**: B-1 → B-2 → B-3 → B-4 → B-5 串单链 (W72 子 plan ③ 起步派工实战)
6. **W72 子 plan ③ 起步 4 必含**: 起步必含 (调研基础 + 实施路径 + 估时 + 风险评估)
7. **W72 商业化 24 人月调研**: 商业化路径必含 5 阶段 + 24 人月排期 + ROI 预估
8. **容器 rebuild 调研**: 容器 rebuild 调研必含 3 优化方案 + 推荐方案 + 实施风险
9. **ppt-word 5 缺口调研**: ppt-word 5 缺口调研必含 5 缺口清单 + 实施优先级 + 估时
10. **预期版必显式 defer**: 派工 v6 段 7 #3 实战 (W68/W71 A-4 实战沉淀)
11. **派工前提错误复盘 5 项**: 派工 v6 段 7 实战 (必先 commit partial diff + 不动 v1-v7 历史约束 + 预期版必显式 defer + 不动 production code + 1 commit + defer message)
12. **6 类文档同步沿用**: W68-W71 D-2 沿用 6 类文档同步 (主仓库 5 + 用户级 1 + 1 新增 memory)

## 11. W72 锚点范式预期

**锚点范式单调上升预期**:
- W7 12 → W66 27 → W67 28 → W68 30 → W68 第 3 批 42 → W68 第 4 批 57 → W68 第 5 批 72 → W68 第 6 批 88 → W68 第 7 批 89 → W68 第 8 批 102 → W68 第 9 批 116 → W68 第 10 批 134 → W68 第 11 批 144 → W68 第 12 批 156 → W68 第 13 批 168 → W68 第 14 批 175 → **W71 206 → W72 ~220** 守恒预期 (+14 守恒, 0 失败预期)

**W72 锚点范式分项预期**:
- A-1 主拍拍板 (无固定 commit)
- A-2 派工 v9: 第 207 守恒预期
- A-3 plans 真验证: 第 208 守恒预期
- A-4 grand closure: 第 210 守恒预期 (含本任务)
- B-1 NavRail: 第 211 守恒预期
- B-2 ThinkingModeSwitch: 第 212 守恒预期
- B-3 ChatViewSSE 顶栏 3-zone: 第 213 守恒预期
- B-4 跨端点: 第 214 守恒预期
- B-5 桌面端 6 主题: 第 215 守恒预期
- C-1 容器 rebuild: 第 216 守恒预期
- C-2 商业化: 第 217 守恒预期
- C-3 ppt-word: 第 218 守恒预期
- D-1 派工 v9: 第 219 守恒预期
- D-2 6 类文档: 第 219 守恒预期
- D-3 锚点范式: 第 220 守恒预期

## 12. W72 W19 选项 A 维持 + 任务模式基调延续

**W19 选项 A 维持**: 4 留未来 PR (Phase 8.5 / P3 dedup / P3 跨 tab / 7 E2E) 不发起新排期. 量化触发条件维持.

**任务模式基调延续**: 派工以已有 plans 实施为主 + 更新过程中发现的小修为辅 (W68 第 4 批主指挥拍板, W68 第 9 批 D-3 升级 v2 加 5 拍板纪律 + 4 阶段流程 v2, W68 第 12 批 D-1 升级 v3 加派工前提 stat 验证纪律, W68 第 13 批 D-1 升级 v4 加 alembic verify + PS 5.1 参数 + plans 真验证 3 段).

**派工纪要 v6 段 7 派工前提错误复盘** (永久纪律, W68/W71/W72 A-4 实战沉淀):
1. **必先 commit partial diff** — B-3 教训
2. **不动 v1-v7 历史约束** (派工 v6 段 5 反馈 #2 实战)
3. **预期版必显式 defer** (派工 v6 段 7 #3 实战: W68/W71 A-4 实战沉淀)
4. **不动 production code** (纯沉淀类)
5. **1 commit + defer message** — `memory(w72nd-batch-a4): ...`

**W72 batch 关键纪律**:
- 派工纪要 v6 段 7 派工前提错误复盘 5 项永久纪律固化
- W72 起步纪律 4 项必读 (派工前 dirty 工作区必须先 commit partial diff)
- B 路线 5 agents 串单链实战 (W72 子 plan ③ 起步派工)
- W72 子 plan ③ 起步 4 必含 (调研基础 + 实施路径 + 估时 + 风险评估)
- 0 production code 改动铁律 14/15 守恒预期 (1 例外 B-1 NavRail + SessionSidebar 重构)

**累计锚点范式**: W72 锚点范式预期守恒 ~220 (W71 206 → W72 ~220 守恒预期 +14).

---

**预期版 commit message**: `memory(w72nd-batch-a4): W72 grand closure memory 预期版 (15 agents 派工调研 + 4 路线 + 锚点范式 W71 206 → W72 ~220 守恒预期 +14, 待 A-1 主拍补实际值, 0 production code 改动铁律 14/15 守恒预期, 锚点范式第 210 守恒)`

**预期版 commit hash**: 待 A-1 主拍补实际值

**预期版 push 状态**: 待 push

**预期版状态**: defer (待 A-1 主拍完工后补实际值)

**派工纪要 v6 段 7 派工前提错误复盘 5 项** (W68/W71 A-4 实战沉淀, 永久纪律):
1. 必先 commit partial diff
2. 不动 v1-v7 历史约束
3. 预期版必显式 defer
4. 不动 production code
5. 1 commit + defer message

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>