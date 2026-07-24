---
name: w68-route-11-d4-w70-final-decision-2026-07-24
description: "W68 第 11 批 D-4 — 主指挥最终决策建议 (W70 拍板). 锚点范式第 145 守恒. 0 production code 改动铁律维持. 输出 1 docs (W70 最终决策: 4 选项矩阵 A/B/C/D + 10 步部署 checklist + 5 类失败回滚 + 商业化 24 人月路线) + 1 memory. 5 新铁律: 4 选项矩阵 / 10 步 checklist / 商业化 24 人月 / 5 类失败回滚 / 季度拍板."
metadata:
  node_type: memory
  type: project
  originSessionId: W68-Route-11-D4
  modified: 2026-07-24T00:00:00.000Z
---

# W68 第 11 批 D-4 — 主指挥最终决策建议 (W70 拍板) (2026-07-24)

> 锚点范式第 145 守恒: W68 第 11 批 D-4 输出 1 docs (W70 最终决策: 4 选项矩阵 + 10 步部署 checklist + 5 类失败回滚 + 商业化 24 人月路线) + 1 memory. 仅 docs + memory, 0 production code 改动铁律维持. W19 选项 A 维持.

## TL;DR

🎯 **W68 第 11 批 D-4 跨主题收官** — 主指挥协调范式派工. **D-4 输出**: 1 docs + 1 memory = 2 文件, 仅决策建议, 不动 production code.

- **docs/w70-final-decision-2026-07-24.md** (~250 行): W68 第 11 批完工盘点 + W70 主指挥拍板选项矩阵 (A/B/C/D) + 10 步部署 checklist + 商业化长期路线 + 5 类失败回滚
- **memory/w68-route-11-d4-w70-final-decision-2026-07-24.md** (本文件, ~150 行): 锚点范式第 145 守恒 + 5 新铁律沉淀

**锚点范式**: W7 12 → W66 27 → W67 28 → W68 第 1 批 30 → 第 3 批 42 → 第 4 批 57 → 第 5 批 72 → 第 7 批 87 → 第 8 批 104 → 第 9 批 119 → 第 10 批 122 → **第 11 批 145** 单调上升
**0 production code 改动铁律**: 完全守恒 (本批仅 docs/ + memory/)
**W19 选项 A**: 维持 (4 留未来 PR 不发起新排期)
**基线 HEAD**: `7b6f0305e` (W68 第 10 批 A-3 grand closure + 5 分支顺序合并 + Alembic 单链守恒)

---

## 1. 派工触发与依据

### 1.1 触发事件

W68 第 10 批 A-3 5 分支顺序合并 + Alembic 单链守恒 (锚点范式第 122 守恒, commit `7b6f0305e`) 后, W68 第 5-11 批累计 200 commits 已进 main 但**尚未部署到云 server**. 主指挥 W68 第 11 批 D-4 派工依据 = "W70 主指挥最终拍板建议". 不写 = W68 收官时缺主指挥可执行 checklist, 部署缺口无人跟进.

### 1.2 前序决策

- **W68 第 4 批拍板**: plans 优先 + 小修搭配 (memory/w68-task-mode-paradigm-plans-first-2026-07-24.md)
- **W68 第 9 批 D-5 拍板**: W69 + W70 季度排期 + 商业化路线 3 选项矩阵 (锚点范式第 119 守恒, docs/w69-w70-roadmap-decision-2026-07-24.md 682 行)
- **W19 选项 A**: 4 留未来 PR 不发起新排期 (docs/future-pr-decision-2026-07-21.md)

### 1.3 输出物

1. **docs/w70-final-decision-2026-07-24.md** (~250 行, 6 节):
   - §1 W68 第 11 批完工盘点 (15 agents 4 路线 + 5 调研发现小修整合 + 锚点范式第 145 守恒)
   - §2 W70 主指挥拍板选项矩阵 (A/B/C/D 4 选项)
   - §3 主指挥决策 checklist (10 步, 120-180 min)
   - §4 长期路线 (Q4 2026 商业化打包 24 人月)
   - §5 失败回滚 (5 类回滚路径)
   - §6 总结
2. **memory/w68-route-11-d4-w70-final-decision-2026-07-24.md** (本文件, ~150 行)

---

## 2. W70 4 选项矩阵核心决策

| 选项 | 内容 | 派工数 | 周期 | 推荐度 |
|------|------|--------|------|--------|
| **A (推荐)** | 部署 W68 第 5-11 批到云 server + 真跑验证 (10 步 checklist) | 0 agents | 120-180 min | ⭐⭐⭐ |
| **B** | 派 W69 (子 plan ② 已在 W68 第 10 批实施 + 6 plans 留 backlog) | 4-6 agents | 1-2 周 | ⭐⭐ |
| **C** | 选项 B + 起步 W70 (ppt-word PR2 回收站 + PR3 秒传) | 8-10 agents | 2-3 周 | ⭐ |
| **D** | 转 Q4 商业化打包 (24 人月), 与 A 组合 | 0 agents | 24 人月 | — |

**推荐选项 A** — 部署缺口是 W68 唯一未闭环项, 优先级最高. W68 第 5-11 批 200 commits 已进 main `7b6f0305e` 但对用户不可见.

**子 plan ② 已实施**: chatgpt-structured-floyd.md §3 qa-bench 7 维评分 (B-1/B-2/B-3/B-4) 已在 W68 第 10 批落地, W69 仅需 Dashboard MVP + CI smoke 收尾.

**6 plans 留 W69 backlog**: drive MIME fallback / distributed CSS token 收敛 / fizzy TabBar (B-1 已修, 剩 memoized TabBar B-2) / dazzling 动画调研 / Desktop v3.2 e2e 剩余 / qa-bench Phase 3 matrix Dashboard MVP.

---

## 3. 10 步部署 checklist (选项 A, 120-180 min)

1. SSH 部署 W68 第 5+7+8+9+10+11 批到云 server (`deploy-auto.sh`, 主仓库 main 含 200 commits)
2. 跑 VAPID 持久化 (`setup_vapid_persistence.sh`, 一次, C-3 部署必做)
3. 跑部署验证 (`verify_w68_7th_batch_deployment.sh`, 13 段)
4. cleanup 删 15 worktree + 16 分支 (`w68_7th_batch_cleanup_plan.sh --apply`)
5. 真跑 Phase 2 1000 题 (`run_d5_dry.py --full --per-intent --gate-threshold 90`)
6. 验证 VAPID 持久化 (`setup_vapid_persistence.sh --verify`)
7. 跑 Desktop v3.2 端到端 (Playwright 22 SKIP → 真跑, 需真实 nginx)
8. 验证 baseline 守恒 (`test_baseline_audit.py`, 71 PASS + 7 SKIP)
9. 验证 git 状态 (`git status && git log --oneline -5`)
10. 验证 cleanup (`git branch -r --merged main | wc -l`)

**待建脚本**: `setup_vapid_persistence.sh` (C-3) + `w68_7th_batch_cleanup_plan.sh` 由主指挥部署前确认存在, 缺失则由 C-3/A-3 补建 (仅 scripts/, 0 production code 改动).

---

## 4. 商业化长期路线 (Q4 2026, 24 人月)

- **Phase 8 实时语音科研助手** (4 人月): ASR/TTS 真流式 + 实时会议纪要 + 语音指令触发 Agent 工具
- **多组织 SaaS** (4 人月): 多租户隔离 (org_id 全表加列) + 席位计费 + 命名空间隔离
- **桌面 EXE 打包** (4 人月): Electron + 本地 GPU Whisper + 离线优先 + 自动更新
- **多平台原生 APP** (6 人月): iOS + Android 原生 (RN/Flutter) + 原生推送 + 生物识别
- **合计**: 4+4+4+6 + 预留 6 (集成/测试/运营) = 约 24 人月

---

## 5. 5 类失败回滚路径

1. **部署失败**: `git revert <deploy-commit>` + 重跑 deploy-auto.sh + 6 点 curl 验证 (RTO < 15 min)
2. **alembic 双头**: `alembic heads` + 改下游 down_revision 串单链 + cp + clear `__pycache__` (RTO < 20 min)
3. **Phase 2 gate 未过**: 退回 docs/CI 占位 (W67 第 47 步一致), 不做第 3 次失败尝试 (RTO < 5 min)
4. **VAPID 持久化失败**: 检查 `.env` + restart app; 失败则回退内存生成 (push 降级, 不阻塞) (RTO < 10 min)
5. **cleanup 误删**: `git reflog` 恢复 + `git worktree add` 重建; cleanup 必须 dry-run 先看清单 (RTO < 15 min)

---

## 6. 5 新铁律

### 铁律 1: 4 选项矩阵 (A 部署 / B 派 W69 / C 派 W69+起步 W70 / D 转商业化)

主指挥季度拍板必须给出 3-4 个可对比选项 + 推荐度 (⭐⭐⭐), 不给单一建议. 选项 A (部署验证) 优先于新派工 (选项 B/C) — 部署缺口是唯一未闭环项. 选项 D (商业化) 必须与 A 组合 (先部署稳定, 后转商业化).

### 铁律 2: 10 步部署 checklist (可执行命令 + 预计工时 + 验收标准)

主指挥拍板 checklist 每步必须含: 命令 + 预计工时 + 验收标准 (三元组). 部署 (步骤 1-4, 50-70 min) 与真跑 (步骤 5-10, 70-110 min) 相互独立 — 真跑失败不影响部署产出对用户可见.

### 铁律 3: 商业化 24 人月 (4 方向 + 预留 6)

长期商业化路线拆 4 方向 (实时语音 4 + SaaS 4 + EXE 4 + 原生 APP 6) + 预留 6 人月 (集成/测试/运营). 每方向标风险等级 (高/中-高/中). Q4 2026 主指挥拍板启动时间表 + 团队扩编.

### 铁律 4: 5 类失败回滚 (场景 + 路径 + RTO)

主指挥拍板必附失败回滚矩阵: 每类含 失败场景 + 回滚路径 + RTO (< 5-20 min). 部署 / alembic 双头 / gate 未过 / VAPID 失败 / cleanup 误删 = 5 类. 失败纪律: 不做第 3 次失败尝试 (W67 第 47 步铁律), 优先回滚 + 记录.

### 铁律 5: 季度拍板依 plans

W70 决策依据 = W68 第 9 批 D-5 季度排期 (chatgpt 子 plan ② + ppt-word PR2/PR3) + 4 留未来 PR (W19 选项 A). 不凭空拍板, 所有选项映射到已有 plans. 排期 ≠ 立即派工 — 主指挥可按需选择 A/B/C/D 或组合.

---

## 7. 完成定义 (DoD)

- ✅ 1 新建 W70 decision docs (~250 行, 6 节) + 1 新增 memory (~150 行) = 2 文件
- ✅ 4 选项矩阵 A/B/C/D 完整 (含推荐度 + 派工数 + 周期)
- ✅ 10 步 checklist (命令 + 工时 + 验收) + 5 失败回滚 (场景 + 路径 + RTO)
- ✅ 商业化 24 人月路线 (4 方向 + 预留 6)
- ✅ 0 production code 改动铁律维持 (仅 docs + memory)
- ✅ 锚点范式第 145 守恒 + W19 选项 A 维持
- ✅ commit + push origin/docs/w70-final-decision-2026-07-24 (不 merge, 主指挥来 merge)
