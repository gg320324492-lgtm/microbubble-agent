# W-N-W72 起步段 (2026-08-05, W72 后 v4 收官 + 后续 PR 列表调研)

> **任务 ID**: W-N-W72 +0 (主指挥 W72 全栈架构后续 agent 派工)
> **派工锚点**: W-N-W72 +0 / +1 / +2
> **base head**: `e68412de4` (历史 W-N-G+ 4 FAIL 修复, 守恒)
> **目标**: 查 W72 v4 收官状态 + 写后续 PR 列表 + docs/w72-post-v4-roadmap.md
> **范畴**: 严格 1 docs + 2 memory, 0 production code

---

## 6 项起步 (W73 铁律)

### 1. base head 验证 (派工前必查)

```bash
$ git log --oneline -3
e68412de4 fix(rag): W-N-G+ 4 FAIL 修复 (cherry-pick 自 claude/w-n-g-plus-4fail-fix)
30e7bf20a docs(memory): W-N-XX +2 收口沉淀 + MEMORY.md #26 段新增 (5 件套守恒 + 3 项未来派工留口完整沉淀)
08ded6718 docs(memory): W-N-XX +2 收口沉淀 + MEMORY.md #26 段新增 (5 件套守恒 + 3 项未来派工留口完整沉淀)
```

✅ base head = `e68412de4` 守恒 (派工 brief 期望, 实测匹配)
✅ working tree clean (本任务 0 commit 起步)

### 2. W72 v4 收官状态查证

W72 全栈架构收官段位于 CLAUDE.md 第 809-826 行, 复述关键:

- **架构终态**: 1 个 1469 行单文件 (`app/agent/core.py`) → 7 个 agent 模块 + 13 个按业务域拆分的 tools/ 文件
- **34 个 `@tool` 装饰器工具** — v2/v3/v4 累计 (任务 5 + 会议 7 + 项目 3 + 成员 2 + 知识 9 + 公式 1 + 假设 1 + 记忆 3 + 搜索 1 + 个性化 2 + 反馈 1)
- **12 类 Rich Block 组件** + 多会话并行 (Pinia + localStorage) + dark mode + ASR/TTS 完整语音链路 + 代码高亮
- **18 个移动端页面 + 12 个移动端组件 + 4 个 PWA 离线策略** (iOS Safari + Android Chrome 全兼容)
- **43 commits 累计** (v1 修复 + v2 6 + v3 5 + v4 6 + 文档 2 + 深夜收尾 4 + 多会话并行 2 + 移动端 10 PR + 文档 5 + 部署加固 1)
- **160+ 测试全过** (87 后端 + 73 前端 + 21 录音断网 + 2 移动端 + 21 多模态 OCR)
- **1014 次提交 / 135K 行代码 / 578 文件 / 30 开发天数** (app/stats.json)
- 当前状态 (2026-06-13 收官后, commit `9026c07`)

CLAUDE.md 顶层 ROADMAP-v2 第 419 行: `✅ v2/v3/v4 Agent 架构（34 个 @tool 装饰器工具 + 12 类 Rich Block + 多会话并行 + agent_traces 可观测性）`

**W72 已沉淀基础设施 (后续 PR 起点)**:
- Kit-2 跨端路由: `useIsMobile.js` + `resolveMobile.js` 路由适配
- 30+ 工具 `@tool` 装饰器 + Pydantic 校验
- 12 类 Rich Block: meeting / task_list / knowledge_ref / member / formula / hypothesis / project / transcript / chart + 2 兜底
- 18 个移动端页面 + 12 个移动端组件
- 4 个 PWA 离线策略 (manifest + sw + useSafeArea + IndexedDB)
- 多会话侧栏 + dark mode + ASR/TTS 完整链路
- agent_traces 可观测性 (Celery 异步写表 + /admin/agent-traces + AgentTracesView)

### 3. 现有 P3 派工顺序表 (W98 P2 收口后, CLAUDE.md 第 545 行)

> **P3 派工顺序表预留** (W98 P2 收口后, 主拍决策): P3-A 待派 (W98 系列延续) / P3-B chat 历史迁移到 PG (W74 chat 历史持久化深化) / P3-C qa-bench baseline 校准 / P3-D W98 系列总 grand closure.

**W19 选项 A 维持** (CLAUDE-history.md 第 7551 行, W18/19/20/21/22 沿用): 4 future PR 中, **P3 dedup 已于 W59 触发并实施完成**. 其余 3 项继续留未来:
1. Phase 8.5 异地容灾后续
2. P3 跨 tab 同步
3. 7 skipped E2E 真闭环

**评估基础**: 不因阶段收口自动发起剩余 PR, 继续按量化触发条件评估.

### 4. W72 后续 PR 列表方向 (主拍决策, 派工 brief 严禁擅自派工)

W-N-W72 +1 收口 PR 列表 (主拍决策参考, 实际派工权在主指挥):

| PR 代号 | 名称 | 链接锚点 | 评级 |
|--------|------|---------|------|
| P3-A | Prisma 集成 (与 SQLAlchemy 兼容) | 主拍决策预留 | 待派 |
| P3-B | RAG 双 backend (Qwen3 + bge-m3 切流) | 主拍决策预留 | 待派 |
| P3-C | 实时 push (WebSocket 标准化) | 主拍决策预留 | 待派 |
| P3-D | W98 系列 total grand closure | 主拍决策预留 | 待派 |
| P3-E | ChatKit-3 集成 (Vue 3.5 ChatKit) | 主拍决策预留 | 待派 |

**派工纪律**: docs/w72-post-v4-roadmap.md 必须明确写**严禁擅自派工**, 仅作主拍决策参考.

### 5. 锚点范式守恒 + W-N-W72 +0..+2 派工

- 锚点范式当前: W86 325 → W87 336 → W92 491 → W97 482 → W98 +13 累计 ~490 → W100 末 ~537 → W100 +49..+58 +49..+58 → W100 +75 收尾 ~537
- W-N-W72 +0..+2 据实上报: 起步 + 1 docs + 1 收口 memory (= 3 commits)
- W-N-W72 +1 docs 范畴 (1 docs/w72-post-v4-roadmap.md): 实际第 1 commit 含 docs 1 commit
- W-N-W72 +2 收口 memory: 实际第 2 commit 含 1 memory (如 docs + memory 合并 → 1 commit, 否则 2 commits)

### 6. 0 production code 守恒 + 严禁清单

**0 production code 守恒 3/3 守恒预期**:
- W-N-W72 +0: 起步 memory (0 production code)
- W-N-W72 +1: docs/w72-post-v4-roadmap.md (0 production code)
- W-N-W72 +2: 收口 memory (0 production code)

**严禁 (派工 brief 明确)**:
- ❌ 改 plan 文件 (主拍决策独占)
- ❌ 改 W-N-A/B/C/D/E/F/D+/+/ARC/GC/ANC/MEM/G+/OBS/RAG/BGE/GRAND/FILL/D++ commits (派工编号保护)
- ❌ 改 CLAUDE.md 顶层 (另 agent 任务 #33 范畴)
- ❌ 改 alembic/versions/ (0 migration 守恒)
- ❌ 改 app/ web/src/ (production code 守恒)
- ❌ 改 docker-compose.yml (infra 守恒)

**严格范畴**: 1 docs + 2 memory (起步 + 收口) + 1 docs/w72-post-v4-roadmap.md (= 1 docs + 2 memory 总计)

---

## 下一步 (W-N-W72 +1)

1. 读 CHANGELOG.md + ROADMAP.md + PROJECT_INTRO.md (W72 v4 收官状态二次确认)
2. 写 `docs/w72-post-v4-roadmap.md`:
   - §1 背景 (W72 v4 收官, 引用 CLAUDE.md 第 809-826 行)
   - §2 已沉淀基础设施 (Kit-2C, 30+ 工具, 12 类 Rich Block, 18 个移动端页面, 4 个 PWA 策略)
   - §3 后续 PR 列表 (P3-A..P3-E, 派工 brief 严禁擅自派工)
   - §4 关键决策 (W19 选项 A 维持)
   - §5 未来派工触发条件
3. commit 1 docs 范畴

---

## 锚点漂移据实上报

W-N-W72 +0 起步: 0 commit (本任务已记录起步项, 收口时一并 commit, 沿用 W-N-XX +2 模式)
实际漂移: W-N-W72 +1 +2 据实上报 (1 docs + 1 memory = 2 commits)
派工 brief 期望: +0..+2 = 3 commits (含起步)
据实偏差: 沿用 W-N-XX +2 模式, 起步与收口合并 = 2 commits, +1 单独 1 commit

W-N-W72 +0 据实口径: 0 commit (本任务 6 项起步沉淀, 收口时并 commit)
W-N-W72 +1 据实口径: 1 commit (docs/w72-post-v4-roadmap.md)
W-N-W72 +2 据实口径: 1 commit (memory/w-n-w72-post-v4-closure-2026-08-05.md)
总计: 2 commits 漂移据实 (vs 派工 brief 期望 3 commits 含起步拆分)

派工 v6 §13.3 假设禁令沿用: 据实上报, 不擅自扩也不擅自缩.

---

**沉淀**: memory/w-n-w72-post-v4-startup-2026-08-05.md (本任务 W-N-W72 +0 起步, 沿用 W73 铁律 6 项起步).
