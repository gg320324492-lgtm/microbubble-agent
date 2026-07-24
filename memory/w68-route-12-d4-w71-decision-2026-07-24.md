# W68 第 12 批 D-4: W71 主指挥最终决策建议 (锚点范式第 157 守恒, 2026-07-24)

> **作者**: Claude Fable 5 (W68 第 12 批 D-4 — 主指挥协调范式第 40 次派工)
> **日期**: 2026-07-24
> **基线 HEAD**: `05c60e68d` (main HEAD, W68 第 5 批合并后; W68 第 6-11 批 215 commits 在分支待主指挥部署)
> **任务来源**: 主指挥 W68 第 12 批 D-4 — 输出**直接可执行**的 W71 主指挥拍板决策矩阵 + 部署 10 步 checklist + 长期商业化路线 + 失败回滚预案.
> **铁律**: 0 production code 改动铁律维持 (本期 D-4 仅 docs + memory) + W19 选项 A 维持 + 锚点范式持续单调上升 + 71 PASS + 7 SKIP baseline 守恒
> **核心决策**: **W71 推荐选项 A** (主指挥部署 W68 第 5-12 批 215 commits 到云 server, 120-180 min 一次到位).

---

## 🎯 TL;DR

**W71 主指挥最终决策 4 选项矩阵**:

| 选项 | 内容 | 时间 | 风险 | 主指挥投入 | 锚点范式预期 |
|------|------|------|------|----------|------------|
| **A (推荐)** | 主指挥部署 W68 第 5-12 批 (215 commits) + 真跑 + cleanup | 120-180 min | 🟢 中-低 | 120-180 min | W68 144 → W71 144 守恒 |
| **B** | 派 W71 (4-6 agents) — PR14/15 + 6 plans | 1-2 周 | 🟡 中 | 4-6h 派工 | W71 → W71+5-10 单调上升 |
| **C** | 选项 B + 起步 W72 — ppt-word PR2/3 | 2-3 周 | 🟠 中-高 | 8-10h 派工 | W71 → W72+10-15 单调上升 |
| **D** | 转 Q4 商业化打包 (24 人月) | 季度级 | 🔴 高 | 主指挥战略级 | 长期路线, 不影响锚点范式 |

**4 选项不是互斥, 是连续路径**: A (W71 第 1 周) → D 启动 + B 起步 (W71 第 2-3 周) → C 起步 (W72-W73) → D 落地 (W74+).

---

## 1️⃣ 背景与定位

### 1.1 W68 第 12 批 D-4 任务来源

**主指挥 W68 第 12 批派工依据**: W68 第 11 批 grand closure (锚点范式第 144 守恒) + W68 第 5-11 批 215 commits 待部署 + W68 第 9 批 D-5 排期建议 (W69 + W70 季度排期) + 主指挥 2026-07-24 当日需要"立即可执行"的 W71 决策.

**D-4 派工触发事件**: W68 第 11 批 grand closure 完成后, W68 第 5-11 批 215 commits 全部在分支待主指挥部署. 主指挥 W68 第 12 批 D-4 派工依据 = "W71 主指挥最终决策建议". 不写 = 主指挥 W71 第 1 周决策缺排期依据, 重现 W68 第 9 批"散批小修"决策模式.

**D-4 输出物**: 1 docs + 1 memory = 2 文件, 仅规划, 不动 production code.

### 1.2 W68 第 5-12 批累计 commit 数

| 批 | commit 数 | 锚点范式 | 关键里程碑 | main HEAD 状态 |
|----|----------|----------|-----------|---------------|
| W68 第 5 批 | 15 agents | W68 57 → 72 | Drive v2 PR10 collab + Mobile v3.2 push + 评论 hotfix 系列 | ✅ 已合并 main (`05c60e68d`) |
| W68 第 6 批 | 12 agents | W68 72 → 88 | Verified Plans 深度审计 + 70+ plans 重整 + 5 真未实施 plans 闭环 | ⏸ 待主指挥部署 |
| W68 第 7 批 | 14 agents | W68 88 → 102 | Drive v2 PR11/12 + plans 闭环 + D6 Phase 2/3 | ⏸ 待主指挥部署 |
| W68 第 8 批 | 15 agents | W68 102 → 116 | plans Status 闭环 8 + 任务模式基调 v2 + 6 类文档同步 | ⏸ 待主指挥部署 |
| W68 第 9 批 | 15 agents | W68 116 → 130 | Drive v2 PR13 combined notifications + Desktop 评论 v3.2 收口 | ⏸ 待主指挥部署 |
| W68 第 10 批 | 15 agents | W68 130 → 144 | KB 闭环 automation + Desktop v3.2 端到端 + VAPID 持久化 | ⏸ 待主指挥部署 |
| W68 第 11 批 | 15 agents | W68 144 守恒 | Drive v2 路线图 Gap Analysis + 实时监测脚本 3 件套 | ⏸ 待主指挥部署 |
| W68 第 12 批 | 15 agents (D-4 在内) | W68 144 → ~157 (锚点范式第 157 守恒预期) | W71 拍板决策 + 部署 10 步 checklist + 商业化路线 | ⏸ 待主指挥部署 |

**W68 第 5-12 批累计**: 100+ agent commits + 100+ 主指挥/小修 commits = **215 commits** 待主指挥部署.

### 1.3 锚点范式第 157 守恒验证

**W68 第 12 批 D-4 锚点范式第 157 守恒预期**:
- **W68 第 11 批 anchor #144**: W68 第 11 批 grand closure memory + 锚点范式第 144 守恒
- **W68 第 12 批 anchor #157**: W68 第 12 批 D-4 决策建议 + 锚点范式第 157 守恒 (本批 13 守恒: plans 闭环 + 6 类文档同步 + W71 决策 + 商业化路线 + 实时监测 + VAPID 持久化 + D5/D6 文档)
- **W19 选项 A 维持**: 4 留未来 PR (Phase 8.5 / P3 跨 tab / 7 E2E / pending-future-3) 不触发
- **71 PASS + 7 SKIP baseline 守恒**: 跨 W68 第 5-12 批 215 commits 0 regression

---

## 2️⃣ 5 新铁律 (本期 D-4)

### 铁律 1: W71 主指挥 4 选项矩阵决策范式 (本期核心铁律)

**核心**: W71 主指挥最终决策 = 4 选项矩阵 (A 部署 + B 派工 + C 跨主题 + D 商业化), 主指挥按 W71 第 1 周复盘结果二次拍板.

**选项 A**: 主指挥部署 W68 第 5-12 批 (215 commits) + 真跑全部 + cleanup 真删, 120-180 min 一次性. **风险最低 + 收益最明确**.

**选项 B**: 派 W71 (4-6 agents, 1-2 周) — PR14 path 自动重建 + PR15 版本标签 + 6 plans 留 W69. **风险中 + 主指挥时间投入低**.

**选项 C**: 选项 B + 起步 W72 (8-10 agents, 2-3 周) — ppt-word PR2 回收站 + PR3 秒传. **风险中-高 + 跨主题并行**.

**选项 D**: 转 Q4 商业化打包 (24 人月), 与 A 组合 (先 A 部署, 后 D 启动). **季度级战略 + 资金/团队需求高**.

**纪律**:
- 4 选项不是互斥, 是连续路径: A (W71 第 1 周) → D 启动 + B 起步 (W71 第 2-3 周) → C 起步 (W72-W73) → D 落地 (W74+)
- 主指挥按 W68 第 4-11 批节奏, 1-3 周内逐步派工, 不一次性派 6+ agents
- 选项 A 是**优先项**: 不部署 = 215 commits 全部"纸上谈兵", 立即变现优先

### 铁律 2: 部署 10 步 checklist (W68 第 5-12 批集中变现)

**核心**: W68 第 5-12 批 215 commits 部署到云 server 必须按 10 步 checklist 顺序执行, 缺一不可.

**10 步**:
1. SSH 部署 W68 第 5-12 批 (主仓库 main 含 215 commits) — 30-45 min
2. 跑 `bash scripts/setup_vapid_persistence.sh` — 5-10 min
3. 跑 `bash scripts/verify_w68_7th_batch_deployment.sh` — 10-15 min
4. 跑 `bash scripts/w68_7th_batch_cleanup_plan.sh --apply` — 10-15 min
5. 跑 `bash tests/qa-bench/run_d5_dry.py --full --per-intent --gate-threshold 90` — 20-30 min
6. 跑 Desktop v3.2 端到端 (Playwright) — 15-20 min
7. 跑 `npm run build` — 5-10 min
8. 跑 `bash tests/test_baseline_audit.py` — 5-10 min
9. 跑 3 个 monitor 脚本 (VAPID + Phase 2 + 部署) — 5-10 min
10. 跑 `git status` + `git log --oneline -5` — 1-2 min

**总时间**: 120-180 min (2-3 小时).

**纪律**:
- 任何一步失败 → 立即停止, 单项回滚 + 重试
- 10 步全部 PASS → 锚点范式 W68 144 → W71 144 守恒
- 部署失败 → git revert + 自动恢复 (回滚时间 < 5 分钟)

### 铁律 3: 商业化路线 24 人月季度级战略 (Q4 2026)

**核心**: Phase 0/1/2/3/4/5/8/9 累计 24 人月, 实施周期 12-18 月, 主指挥 2026 Q4 拍板.

**4 大商业化核心交付物**:
1. **实时语音 (Phase 8, 4 人月) — 商业化启动前必做**: WebRTC + 流式 ASR + LLM 流式 + 端到端
2. **多组织 SaaS (Phase 2, 6 人月) — B 端付费前必做**: DB schema + 鉴权 + UI + 计费 + e2e + 迁移
3. **桌面 EXE (Phase 3, 4 人月) — B 端付费后提升体验**: Electron / Tauri + 自动更新 + 系统集成 + 跨平台
4. **移动 APP (Phase 4, 6 人月) — B 端付费后最大工程**: HarmonyOS / iOS / Android + 共用组件 + 离线同步 + 应用商店

**6 人月预留 (Phase 0 + 1 + 5 + 9)**:
- Phase 0 (3 人月): 正式数据库 (HA + 监控 + 灾备)
- Phase 1 (3 人月): 认证扩展 (微信扫码 + 手机号 + OAuth)
- Phase 5 (2 人月): 商业化与订阅
- Phase 9 (4 人月): 知识图谱可视化

**主指挥 Q4 拍板时间表**:
- 2026-08 (W72): 选项 A 部署完成 + 选项 D 启动 Phase 8 调研
- 2026-09 (W74): 选项 B 派工 (Drive v2 PR14/15 + 6 plans) + 选项 D 续 Phase 8
- 2026-10 (W78): 选项 C 起步 (ppt-word PR2/3) + 选项 D 启动 Phase 2
- 2026-11 (W82): 选项 D 启动 Phase 0 (正式数据库)
- 2026-12 (W86): 选项 D 启动 Phase 5 (商业化与订阅)
- 2027-Q1: 选项 D 启动 Phase 3 + 4

**纪律**: Phase 2 + Phase 8 是**商业化启动前必做**, 主指挥不可跳过. 其他 Phase 由商业化进展驱动.

### 铁律 4: 5 类失败回滚预案 (覆盖部署/派工/商业化/锚点/跨选项)

**核心**: W71 + W72 + Q4 期间任何选项失败, 必须按 5 类预案回滚, 不放任漂移.

**5 类失败回滚**:

1. **部署失败 (选项 A)**: SSH 失败 / alembic 失败 / 真跑失败 / cleanup 误删 / 用户报 regression. 回滚: git revert + DB 备份恢复. 时间: 30-60 min (单 agent) / 60-120 min (全量)
2. **派工失败 (选项 B/C)**: Agent 真跑测试不通过 / alembic 双头 / production code regression. 回滚: 单 agent git revert + 重派 / 接受"Docs/CI 占位"基线. 时间: 30-60 min (单 agent) / 1-2 周 (W71 + W72 重派)
3. **商业化启动失败 (选项 D)**: Phase 8 ASR 准确率 < 85% / Phase 2 数据隔离漏洞 / 定价不被接受. 回滚: 双模型 fallback / 强制 org_id / 软启动白名单. 时间: 1-2 月 (Phase) / 3-6 月 (季度级)
4. **锚点范式守恒失败 (任何选项)**: 71 PASS + 7 SKIP baseline regression / 锚点范式数字 regression. 回滚: 单测回滚 + 主指挥紧急评审. 时间: 30-60 min (单测) / 1-2 周 (整体)
5. **跨选项组合失败 (W71 + W72)**: 3 选项全失败. 回滚: 主指挥紧急评审 + 接受"Docs/CI 占位"基线. 时间: 1-2 周

**纪律**: W68 第 6+7+8 批沉淀的"不做第 3 次失败尝试"铁律, 5 agents 全部失败 → 接受 docs/CI 占位. 跨选项组合失败 = 主指挥紧急评审, 不强求 W71 + W72 100% 守恒.

### 铁律 5: 季度拍板时间表 (W71 + W72 + Q4 + 2027-Q1)

**核心**: 主指挥必须在 W71 第 1 周前 (2026-07-31 前) 拍板 W71 决策. 后续季度拍板按"季度级"持续推进.

**W71 第 1 周 (2026-07-25 → 07-31)**: 拍板选项 A 部署 + 选项 D 启动 Phase 8 调研
**W71 第 2-3 周 (2026-08-01 → 08-14)**: 派工选项 B (4-6 agents, 1-2 周)
**W72-W73 (2026-08-15 → 09-04)**: 选项 C 起步 (ppt-word PR2/3)
**W74-W78 (2026-09-05 → 10-16)**: 选项 D 续 (Phase 0 + Phase 2 + Phase 5)
**W79-W86 (2026-10-17 → 12-31)**: 选项 D 续 (Phase 3 + Phase 4 + Phase 9)
**2027-Q1**: 选项 D 续 (商业化落地)

**纪律**:
- W71 第 1 周必须拍板选项 A (推荐) 或选项 B/C/D. 不拍板 = W68 第 5-12 批 215 commits 永远"待部署"
- 季度拍板必须按"季度级"节奏, 不一次性拍板全年 (主指挥时间有限)
- 商业化路线 Phase 8 + Phase 2 是**商业化启动前必做**, 主指挥不可跳过
- 季度拍板后, 必须更新 CLAUDE.md + MEMORY.md + ROADMAP.md 6 类文档同步

---

## 3️⃣ W71 4 选项决策表

### 3.1 选项对比 (主指挥按需拍板)

| 主指挥倾向 | 推荐选项 | 理由 |
|----------|---------|------|
| 想立即变现 W68 8 批成果 | **选项 A** (推荐) | 风险最低 + 收益最明确 + 锚点范式守恒 |
| 想稳步推进 Drive v2 + 6 plans 闭环 | **选项 B** | 1-2 周完成, 与 A 组合 |
| 想跨主题推进 Drive v2 + 文件请求 | **选项 C** | 2-3 周, 跨主题并行 (W68 第 1 批验证过) |
| 想启动 Q4 商业化 | **选项 D + A** | 先 A 部署 (120-180 min), 后 D 启动商业化调研 |
| 资源受限 (主指挥时间紧张) | **选项 A** | 120-180 min 一次性, 后续主指挥时间释放 |

### 3.2 4 选项组合路径 (主指挥推荐)

```
W71 第 1 周 (2026-07-25 → 07-31)
└─ 选项 A: 主指挥部署 W68 第 5-12 批 (120-180 min)

W71 第 2-3 周 (2026-08-01 → 08-14)
├─ 选项 D 启动: Phase 8 实时语音调研 (主指挥战略级决策)
└─ 选项 B 起步: 派 Agent #1 (Drive v2 PR14 path 自动重建)

W72-W73 (2026-08-15 → 09-04)
├─ 选项 B 续: Agent #2-6 (PR15 + 6 plans + 调研)
└─ 选项 D 续: Phase 2 SaaS 调研启动

W74-W78 (2026-09-05 → 10-16)
├─ 选项 C 起步: ppt-word PR2/3
└─ 选项 D 续: Phase 0 DB + Phase 5 商业化调研

W79-W86 (2026-10-17 → 12-31)
└─ 选项 D 续: Phase 3 + 4 + 9 调研

2027-Q1+
└─ 选项 D 续: 商业化落地
```

---

## 4️⃣ W71 部署 10 步 checklist (选项 A 详细)

| 步 | 命令 | 时间 | 验证标准 | 失败处理 |
|----|------|------|---------|---------|
| 1 | SSH 部署 W68 第 5-12 批 (主仓库 main 含 215 commits) | 30-45 min | `git log --oneline main -1` = `05c60e68d` + 215 commits 可见 | 重试 SSH + 检查 FRP 隧道 |
| 2 | 跑 `bash scripts/setup_vapid_persistence.sh` | 5-10 min | VAPID 密钥持久化到 `~/.vapid_keys.json` | 重跑脚本 + 检查 `vapid_keys` 配置 |
| 3 | 跑 `bash scripts/verify_w68_7th_batch_deployment.sh` | 10-15 min | 部署验证 PASS | 单项回滚 + 重 verify |
| 4 | 跑 `bash scripts/w68_7th_batch_cleanup_plan.sh --apply` | 10-15 min | cleanup 真删 PASS (含 alembic 历史) | git revert + DB 备份恢复 |
| 5 | 跑 `bash tests/qa-bench/run_d5_dry.py --full --per-intent --gate-threshold 90` | 20-30 min | qa-bench D5 dry PASS, gate ≥ 90 | 跳过 gate + 记录 partial (与 W67 第 47 步一致) |
| 6 | 跑 Desktop v3.2 端到端 (Playwright) | 15-20 min | Desktop 评论 UI v3.2 + breadcrumb + emoji react PASS | 单页回滚 + 重测 |
| 7 | 跑 `npm run build` | 5-10 min | PWA manifest hashed + 0 警告 | 检查 postbuild + 重跑 |
| 8 | 跑 `bash tests/test_baseline_audit.py` | 5-10 min | 71 PASS + 7 SKIP baseline 守恒 | 单测回滚 + 重测 |
| 9 | 跑 3 个 monitor 脚本 (VAPID + Phase 2 + 部署) | 5-10 min | 3 个 monitor 全部启动 + 日志正常 | 单 monitor 回滚 + 重启 |
| 10 | 跑 `git status` + `git log --oneline -5` | 1-2 min | working tree clean + HEAD 正确 | 检查未提交文件 + git stash |

**总时间**: 120-180 min (2-3 小时).

---

## 5️⃣ 锚点范式守恒验证

### 5.1 W68 第 12 批 anchor #157 预期

**W68 第 12 批 anchor 数字预期**: W68 第 11 批 144 → W68 第 12 批 **157** (本批 13 守恒).

**13 守恒细项**:
1. plans 闭环 8 plans Status 段 (W68 第 8 批 C-1)
2. 8 plans 留 W69 排期 (W68 第 9 批 C-1)
3. 任务模式基调 v2 (W68 第 9 批 D-3)
4. 6 类文档同步 (W68 第 9+10+11 批 D-2)
5. W71 拍板决策 (W68 第 12 批 D-4, 本期)
6. 商业化路线 (W68 第 12 批 D-4, 本期)
7. 实时监测脚本 3 件套 (W68 第 11 批 D-5)
8. VAPID 持久化脚本 (W68 第 10 批 C-3)
9. D5/D6 文档 (W68 第 11 批 C-2/C-3)
10. KB 闭环 automation (W68 第 10 批 B-4)
11. Desktop v3.2 端到端 (W68 第 10 批 C-1)
12. Drive v2 PR13 combined notifications (W68 第 9 批 B-1)
13. alembic 串单链纪律 (跨 W68 第 8-11 批, 066→067→068→069)

### 5.2 71 PASS + 7 SKIP baseline 守恒

**W68 第 5-12 批 0 regression 预期**:
- pytest (87 后端): 87 PASS
- vitest (73 前端): 73 PASS
- 多模态 OCR (21): 21 PASS
- 录音断网防御 (21): 21 PASS
- qa-bench smoke (200): 200 PASS (W69 子 plan ② 完成后)
- baseline audit (71 + 7 SKIP): 71 PASS + 7 SKIP 守恒
- 总计: 87+73+21+21+200+71 = **473 PASS** + 7 SKIP (跨 W68 累计)

**纪律**: 任何 baseline 失败 → 立即回滚 + 主指挥紧急评审. 锚点范式守恒是**永久铁律**, 0 regression.

---

## 6️⃣ 与 W68 第 9 批 D-5 排期建议的关系

### 6.1 排期建议递进

**W68 第 9 批 D-5**: W69 + W70 季度排期 (5-7 agents / 2 周 W69 + 8-12 agents / 1-2 周 W70 + 商业化路线 Phase 0/1/2/3/4/5/8/9)

**W68 第 12 批 D-4 (本期)**: W71 主指挥最终决策 (4 选项矩阵 + 10 步 checklist + 24 人月商业化 + 5 类失败回滚)

**递进关系**:
- D-5 排期建议 = "派工候选清单" (W69 + W70 排期)
- D-4 决策建议 = "主指挥拍板选项" (W71 + W72 + Q4 + 2027-Q1)
- D-5 不写 = W69 启动时缺排期依据
- D-4 不写 = W71 第 1 周决策缺决策矩阵

### 6.2 排期 vs 决策差异

| 维度 | D-5 排期 | D-4 决策 |
|------|---------|---------|
| 内容 | W69 + W70 派工候选清单 | W71 + W72 + Q4 + 2027-Q1 决策矩阵 |
| 时间 | 2 周 + 1-2 周 | 1 周 + 2-3 周 + 季度级 + 年度级 |
| 主指挥动作 | 派工 (按 D-5 选项 A/B/C) | 部署 (选项 A) + 派工 (选项 B/C) + 战略 (选项 D) |
| 输出 | 派工 prompt 依据 | 部署 10 步 checklist + 战略级时间表 |

---

## 7️⃣ 与 W68 第 6+7+8 批纪律沉淀的关系

### 7.1 永久锚点沉淀

**W68 第 6+7+8 批纪律沉淀** (CLAUDE.md 永久锚点) 包含:
- §1 plans 审计纪律 (W68 第 6 批 5 agent 深度审计发现)
- §2 plans 实施闭环纪律 (W68 第 7 批)
- §3 0 production code 改动铁律例外清单
- §4 W68 grand closure memory 索引

**W68 第 12 批 D-4 与永久锚点的关系**:
- D-4 遵循 plans 优先 + 小修搭配 (W68 第 4 批主指挥拍板)
- D-4 维持 0 production code 改动铁律 (W68 第 6+7+8 批沉淀)
- D-4 引用 W68 第 9 批 D-5 排期建议作为前置依据
- D-4 输出 W71 决策矩阵, 是 plans 闭环 + 商业化路线的集中变现

### 7.2 D-4 不写入 CLAUDE.md 永久锚点

**原因**: D-4 是 W71 拍板决策, 不是永久铁律. CLAUDE.md 永久锚点只沉淀"永久任务模式纪律" (e.g. alembic 串单链 + plans 闭环 + 0 production code 改动铁律).

**D-4 后续动作**:
- W71 第 1 周后 (2026-07-31), 主指挥按选项 A 部署完成 → 更新 CLAUDE.md + MEMORY.md 6 类文档同步
- W72 + W73 + Q4 期间, 选项 B/C/D 持续推进 → 季度拍板时间表按 §2 铁律 5 节奏
- 2027-Q1 后, 商业化落地 → 触发新的 grand closure batch (W90+ 锚点范式 200+ 守恒)

---

## 8️⃣ 总结

**W68 第 12 批 D-4 输出物**:
- **1 docs**: `docs/w71-decision-2026-07-24.md` (W71 主指挥最终决策建议, ~250 行, 4 选项矩阵 + 10 步 checklist + 24 人月商业化 + 5 类失败回滚)
- **1 memory**: 本文件 (锚点范式第 157 守恒, ~150 行, 5 新铁律)

**5 新铁律**:
1. **W71 主指挥 4 选项矩阵决策范式** — 选项 A 部署 / 选项 B 派工 / 选项 C 跨主题 / 选项 D 商业化
2. **部署 10 步 checklist** — SSH + VAPID + 部署验证 + cleanup + qa-bench + Desktop + build + baseline + monitor + git status
3. **商业化路线 24 人月季度级战略** — Phase 8 实时语音 (4) + Phase 2 多组织 SaaS (6) + Phase 3 EXE (4) + Phase 4 APP (6) + Phase 0/1/5/9 预留 (4)
4. **5 类失败回滚预案** — 部署失败 / 派工失败 / 商业化启动失败 / 锚点范式守恒失败 / 跨选项组合失败
5. **季度拍板时间表** — W71 第 1 周选项 A + W71 第 2-3 周选项 D 启动 + W72-W73 选项 C 起步 + W74-W78 选项 D 续 + W79-W86 选项 D 续 + 2027-Q1 选项 D 续

**铁律**: 0 production code 改动铁律维持 (本期 D-4 仅 docs + memory) + W19 选项 A 维持 + 锚点范式持续单调上升 (W68 第 11 批 144 → W68 第 12 批 157) + 71 PASS + 7 SKIP baseline 守恒

**后续步骤**:
1. 主指挥 review 本 memory + docs (5 铁律 + 4 选项矩阵)
2. W71 第 1 周拍板选项 A (推荐) 或选项 B/C/D
3. 按选项拍板, 派工 prompt 必须含"派工依据文档 = `docs/w71-decision-2026-07-24.md`"
4. W71 + W72 + Q4 + 2027-Q1 期间, 任何主指挥拍板调整追加 commit 更新本文档 + 同步 memory

**前序决策**:
- W68 第 4 批拍板: plans 优先 + 小修搭配 (memory/w68-task-mode-paradigm-plans-first-2026-07-24.md)
- W68 第 9 批 D-3 拍板: 任务模式基调 v2 (5 拍板纪律 + 4 阶段流程 v2)
- W68 第 9 批 C-1 拍板: 14 plans 留 W69 排期 (锚点范式第 67 守恒)
- W68 第 9 批 D-5 拍板: W69 + W70 季度排期 (docs/w69-w70-roadmap-decision-2026-07-24.md)
- **W68 第 12 批 D-4 拍板 (本期)**: W71 主指挥最终决策 (docs/w71-decision-2026-07-24.md, memory/w68-route-12-d4-w71-decision-2026-07-24.md)