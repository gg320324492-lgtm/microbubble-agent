# W70 主指挥最终决策建议 — W68 第 11 批 D-4 (2026-07-24)

> **作者**: Claude Fable 5 (W68 第 11 批 D-4 — 主指挥协调范式派工依据)
> **日期**: 2026-07-24
> **基线 HEAD**: `7b6f0305e` (W68 第 10 批 A-3 grand closure + 5 分支顺序合并 + Alembic 单链守恒)
> **前序文档**:
> - [`docs/w69-w70-roadmap-decision-2026-07-24.md`](./w69-w70-roadmap-decision-2026-07-24.md) (W68 第 9 批 D-5 — W69 + W70 季度排期 + 商业化路线, 锚点范式第 119 守恒)
> - [`docs/future-pr-decision-2026-07-21.md`](./future-pr-decision-2026-07-21.md) (W19 选项 A — 4 留未来 PR 主指挥决策)
> - [`memory/w68-task-mode-paradigm-plans-first-2026-07-24.md`](../memory/w68-task-mode-paradigm-plans-first-2026-07-24.md) (W68 第 4 批拍板: plans 优先 + 小修搭配)
> - [`memory/w68-route-10-a3-pr9-11-merge-2026-07-24.md`](../memory/w68-route-10-a3-pr9-11-merge-2026-07-24.md) (5 分支顺序合并 + Alembic 单链守恒, 锚点范式第 122 守恒)
> **任务来源**: 主指挥 W68 第 11 批 D-4 — 基于 W68 第 5+7+8+9+10+11 批累计产出, 输出**直接可执行**的 W70 主指挥最终拍板建议 (4 选项矩阵 + 10 步部署 checklist + 5 类失败回滚 + 商业化长期路线).
> **铁律**: 0 production code 改动 (本期仅 docs + memory) + W19 选项 A 维持 + 锚点范式持续单调上升 + 71 PASS + 7 SKIP baseline 守恒 + 季度拍板依 plans.
> **核心决策**: **主指挥拍板选项 A** (推荐) — 主指挥部署 W68 第 5+7+8+9+10+11 批到云 server, 真跑 Phase 2 1000 题 + VAPID 持久化 + Desktop v3.2 22 SKIP 真跑 + cleanup 真删, 预计 **120-180 min**.

---

## 🎯 TL;DR

| 选项 | 内容 | 派工数 | 周期 | 推荐度 |
|------|------|--------|------|--------|
| **A (推荐)** | 主指挥部署 W68 第 5-11 批到云 server + 真跑验证 (10 步 checklist) | 0 agents | 120-180 min | ⭐⭐⭐ |
| **B** | 派 W69 (子 plan ② 已在 W68 第 10 批实施 + 6 plans 留 W69 backlog) | 4-6 agents | 1-2 周 | ⭐⭐ |
| **C** | 选项 B + 起步 W70 (ppt-word PR2 回收站 + PR3 秒传) | 8-10 agents | 2-3 周 | ⭐ |
| **D** | 0 agents, 接受现状, 进入 Q4 商业化打包 | 0 agents | 24 人月 | — |

**Why 写这份最终决策建议**:
- W68 第 5-11 批累计 200 commits 已进 main (`7b6f0305e`), 但**尚未部署到云 server**. 部署缺口 = W68 全批次产出对用户不可见.
- W68 第 9 批 D-5 已锁定 W69 + W70 季度排期 (锚点范式第 119 守恒), 但缺**主指挥拍板的可执行 checklist**.
- 主指挥需要在 W68 收官前, 明确"下一步是部署验证 (选项 A) 还是继续派工 (选项 B/C) 还是转商业化 (选项 D)".
- **决策 ≠ 立即执行**: 本文档是主指挥拍板依据, 主指挥可按需选择 A/B/C/D 或组合.

**How to apply**:
1. 主指挥 review §2 选项矩阵 → 拍板 A/B/C/D.
2. 若选 A: 按 §3 10 步 checklist 逐项执行 (120-180 min).
3. 若选 B/C: 参照 `docs/w69-w70-roadmap-decision-2026-07-24.md` §2/§3 派工.
4. 若选 D: 参照 §4 商业化路线 (24 人月).
5. 任一步失败: 按 §5 5 类失败回滚路径处理, 不做第 3 次失败尝试 (W67 第 47 步铁律).

---

## §1 W68 第 11 批完工盘点

### 1.1 W68 第 11 批 15 agents 派工概览

W68 第 11 批延续任务模式基调 (plans 优先 + 小修搭配, W68 第 4 批拍板), 15 agents 分 4 路线派工:

| 路线 | agents | 内容 | 0 prod code |
|------|--------|------|-------------|
| A (合并收口) | 3 | W68 第 10 批 5 分支合并后 baseline 守恒验证 + Alembic 单链确认 + main push | ✅ 完全 |
| B (Drive v2 续) | 4 | Drive v2 PR11 path 物化收尾 + PR12 reactions + PR13 combined notifications 部署文档 | ⚠️ 已批新功能例外 |
| C (Mobile/Desktop 收口) | 3 | Desktop v3.2 22 SKIP e2e 占位 + Mobile v3.2 VAPID push 部署脚本 + iOS 分享收口 | ⚠️ 已批新功能例外 |
| D (文档/决策/沉淀) | 5 | D-1 部署验证脚本 + D-2 6 类文档同步 + D-3 baseline 守恒 + D-4 W70 最终决策 (本文档) + D-5 memory 沉淀 | ✅ 完全 |

### 1.2 5 调研发现小修整合

W68 第 11 批调研阶段 (4 阶段流程 v2 之 §2 调研) 发现 5 项小修, 已整合进对应 agent 派工范围:

1. **VAPID 密钥持久化缺口** — `app/models/push_subscription.py` + `alembic 065` 已落地, 但 VAPID public/private key 仍在内存生成, 重启即失效 → 整合进 C-3 (需 `scripts/setup_vapid_persistence.sh` 部署脚本 + `.env` 持久化).
2. **Desktop v3.2 e2e 占位未真跑** — 22 个 e2e case 标记 SKIP (需真实 nginx + Playwright), 整合进 C-1 (部署后主指挥真跑).
3. **drive MIME 类型 fallback** — Drive v2 上传 `.docx`/`.pptx` MIME 检测缺 fallback, 留 W69 backlog.
4. **distributed CSS token 未收敛** — Drive v2 PR12 reactions 组件字面色未 token 化, 留 W69 backlog (与 W70-W74 CSS token 收敛对齐).
5. **fizzy TabBar memoization** — 移动端 TabBar 重渲染 (已由 B-1 部分修), 剩余 memoized TabBar 优化 (B-2) + dazzling 动画调研留 W69 backlog.

### 1.3 锚点范式守恒

W68 第 11 批 D-4 = 锚点范式**第 145 守恒** (单调上升):
```
W7 12 → W66 27 → W67 28 → W68 第 1 批 30 → 第 3 批 42 → 第 4 批 57 → 第 5 批 72
→ 第 7 批 87 → 第 8 批 104 → 第 9 批 119 → 第 10 批 122 → 第 11 批 145
```

---

## §2 W70 主指挥拍板选项矩阵

### 选项 A (推荐) — 部署验证

> **主指挥部署 W68 第 5+7+8+9+10+11 批到云 server, 真跑 Phase 2 1000 题 + VAPID 持久化 + Desktop v3.2 22 SKIP 真跑 + cleanup 真删.**

- **前提**: 主仓库 main HEAD `7b6f0305e` 含 W68 累计 200 commits (Drive PR9-13 + Mobile/Desktop v3.2 + qa-bench Phase3 matrix + push_subscriptions 065-069 alembic 链).
- **执行**: §3 10 步 checklist.
- **周期**: 120-180 min (主指挥本地 PC + SSH 到云 server).
- **产出**: W68 全批次产出对用户可见 + Phase 2 1000 题真实 pass rate + VAPID push 持久化生效 + 15 worktree/16 分支清理.
- **风险**: 中 (5 个 alembic migration 062-069 需 cp + clear cache, 单链风险已由 W68 第 10 批 A-2/A-3 守恒).
- **推荐度**: ⭐⭐⭐ — 部署缺口是 W68 唯一未闭环项, 优先级最高.

### 选项 B — 派 W69

> **派 W69 (4-6 agents, 1-2 周)**: chatgpt 子 plan ② 完成 (B-1/B-2/B-3/B-4 已在 W68 第 10 批实施) + 6 plans 留 W69 backlog.

- **子 plan ② 状态**: chatgpt-structured-floyd.md §3 qa-bench 7 维评分 — B-1/B-2/B-3/B-4 (7 维算法 + save_to_kb 5 道防线 + Celery rollback + KB 闭环) 已在 W68 第 10 批实施, W69 仅需 Dashboard MVP + CI smoke 收尾 (1-2 agents).
- **6 plans 留 W69 backlog**:
  1. drive MIME fallback (§1.2-3)
  2. distributed CSS token 收敛 (§1.2-4)
  3. fizzy TabBar — B-1 已修, 剩余 memoized TabBar (B-2)
  4. dazzling 动画调研
  5. Desktop v3.2 e2e 剩余 case (若选项 A 部署时未全跑)
  6. qa-bench Phase 3 matrix Dashboard MVP
- **周期**: 1-2 周 (4-6 agents × 3-5h).
- **推荐度**: ⭐⭐ — 部署 (选项 A) 应先于新派工.

### 选项 C — 派 W69 + 起步 W70

> **选项 B + 起步 W70 (8-10 agents, 2-3 周)**: ppt-word 路线图 PR2 回收站实施 + PR3 秒传.

- **ppt-word PR2** (回收站 + 多选批量 + 收藏星标 + 排序/筛选, 5d): `web/src/components/drive/FolderTree.vue` 顶部 3 固定项 + 多选批量删除进回收站 → 恢复验证. 详见 [`ppt-word-replicated-swing.md`](C:/Users/pc/.claude/plans/ppt-word-replicated-swing.md) §PR2.
- **ppt-word PR3** (秒传 hash + 版本历史, 6d, M2 招牌功能): MinIO `copy_object` 零带宽秒传 + `create_instant_upload(file_hash, ...)` + `DriveUploadDialog.vue` 上传前算 hash. 详见 ppt-word §PR4.
- **周期**: 2-3 周 (8-10 agents × 3-5h).
- **推荐度**: ⭐ — 跨度大, 建议 W68 收官部署 (选项 A) 稳定后再启动.

### 选项 D — 转商业化

> **0 agents, 0 周, 接受现状, 进入 Q4 商业化打包 (24 人月).**

- **前提**: W68 全批次已部署 (即先做选项 A), 系统稳定, 无阻塞 bug.
- **内容**: §4 商业化长期路线 (Phase 8 实时语音 + 多组织 SaaS + 桌面 EXE + 多平台 APP).
- **周期**: 24 人月 (2026 Q4 主指挥拍板).
- **推荐度**: — (与 A 组合: 先 A 部署, 稳定后转 D).

---

## §3 主指挥决策 checklist (选项 A, 预计 120-180 min)

> ⚠️ **纪律**: 主指挥在**本地 PC** 执行 (deploy-auto.sh 已改"主指挥本地 PC"提示, 云 server 不用 docker). SSH 到云 server 部署主仓库 main. alembic migration 062-069 必须 cp + clear cache (CLAUDE.md 752 行铁律 + W68 alembic 单链纪律).

| # | 步骤 | 命令 | 预计 | 验收 |
|---|------|------|------|------|
| 1 | SSH 部署 W68 第 5+7+8+9+10+11 批到云 server | `bash scripts/deploy-auto.sh` (主仓库 main 含 200 commits) | 30-40 min | webhook 30s + `git log --oneline -5` = `7b6f0305e` |
| 2 | 跑 VAPID 持久化 (C-3 部署必做) | `bash scripts/setup_vapid_persistence.sh` (**一次**) | 5-10 min | `.env` 含 `VAPID_PUBLIC_KEY` / `VAPID_PRIVATE_KEY` |
| 3 | 跑部署验证 (13 段) | `bash scripts/verify_w68_7th_batch_deployment.sh` | 10-15 min | 13 段全 PASS |
| 4 | cleanup 删 15 worktree + 16 分支 | `bash scripts/w68_7th_batch_cleanup_plan.sh --apply` | 5 min | worktree + 分支清理完成 |
| 5 | 真跑 Phase 2 1000 题 | `python tests/qa-bench/run_d5_dry.py --full --per-intent --gate-threshold 90` | 30-60 min | pass rate + per-intent 表 + gate 判定 |
| 6 | 验证 VAPID 持久化 | `bash scripts/setup_vapid_persistence.sh --verify` | 2 min | key 重启后不变 |
| 7 | 跑 Desktop v3.2 端到端 (C-3 真跑 e2e) | Playwright 22 SKIP → 真跑 (需真实 nginx) | 15-20 min | 22 e2e case 真跑结果 |
| 8 | 验证 baseline 守恒 | `python tests/test_baseline_audit.py` | 5 min | 71 PASS + 7 SKIP (W62 第 24 次守恒) |
| 9 | 验证 git 状态 | `git status && git log --oneline -5` | 1 min | working tree clean + HEAD = `7b6f0305e` |
| 10 | 验证 cleanup | `git branch -r --merged main \| wc -l` | 1 min | merged 分支数减少 16 |

> **总计**: 120-180 min. 步骤 1-4 (部署 + 验证 + 清理) 约 50-70 min, 步骤 5-10 (真跑 + 验收) 约 70-110 min.

> ⚠️ **步骤 2/4/6/7 脚本待建**: `scripts/setup_vapid_persistence.sh` (C-3) + `scripts/w68_7th_batch_cleanup_plan.sh` 由主指挥部署前确认存在; 若缺失, 由 W68 第 11 批 C-3/A-3 补建 (仅 scripts/, 0 production code 改动). Desktop v3.2 e2e (步骤 7) 需真实 nginx + Playwright 环境.

---

## §4 长期路线 (Q4 2026 商业化打包, 24 人月)

> **前提**: W68 全批次已部署 (选项 A), 系统稳定. 商业化 = 从"课题组内部 AI 助手"升级为"可对外售卖的科研 SaaS 产品".

### 4.1 Phase 8 实时语音科研助手 (4 人月)

- **内容**: ASR/TTS 真流式 (边录音边出文字) + 实时会议纪要 + 语音指令直接触发 Agent 工具调用.
- **依据**: 方案 C "没做的" 明确范围外项 (ASR/TTS 真流式 + 流式 ChartBlock 渐进渲染).
- **风险**: 高 (faster-whisper GPU 流式 + Edge-TTS 边界处理).

### 4.2 多组织 SaaS (4 人月)

- **内容**: 多租户隔离 (org_id 全表加列) + 组织级配额 + 按席位计费 + 独立知识库/成员/会议命名空间.
- **依据**: 当前单组织架构 (20 人实验室), SaaS 需租户隔离 + 计费.
- **风险**: 中-高 (全表 org_id 迁移 + 越权防护跨所有 service).

### 4.3 桌面 EXE 打包 (4 人月)

- **内容**: Electron 打包桌面客户端 + 本地 GPU Whisper 集成 + 离线优先 + 自动更新.
- **依据**: 当前 web + FRP 隧道架构, 桌面 EXE 降低部署门槛.
- **风险**: 中 (Electron + Docker 本地服务集成 + 签名).

### 4.4 多平台原生 APP (6 人月)

- **内容**: iOS + Android 原生 APP (React Native / Flutter) 替代当前 PWA + 原生推送 + 生物识别 + 离线同步.
- **依据**: 当前移动端双栈 (NutUI + EP) PWA, 原生 APP 体验更佳.
- **风险**: 高 (双平台原生 + 后端 API 兼容 + 应用商店审核).

> **合计**: 4 + 4 + 4 + 6 + (预留 6 人月集成/测试/运营) = **约 24 人月** (2026 Q4 主指挥拍板启动时间表 + 团队扩编).

---

## §5 失败回滚 (5 类回滚路径)

| # | 失败场景 | 回滚路径 | RTO |
|---|----------|----------|-----|
| 1 | **部署失败** (步骤 1 webhook 未生效 / 500) | `git revert <deploy-commit>` + 重跑 `deploy-auto.sh` + 验证 6 点 curl (HTML/CSS/JS/PNG/manifest/sw.js) | < 15 min |
| 2 | **alembic 双头** (步骤 1 `Multiple head revisions`) | `alembic heads` 确认 → 改下游 `down_revision` 串单链 (W68 alembic 单链纪律) + cp + clear `__pycache__` | < 20 min |
| 3 | **Phase 2 gate 未过** (步骤 5 pass rate < 90%) | 退回 docs/CI 占位 (与 W67 第 47 步一致), 不做第 3 次失败尝试; 记录真实 pass rate 留 W69 分析 | < 5 min (接受现状) |
| 4 | **VAPID 持久化失败** (步骤 6 key 重启变化) | 检查 `.env` 是否写入 + `docker compose restart app`; 失败则回退到内存生成 (push 功能降级, 不阻塞主流程) | < 10 min |
| 5 | **cleanup 误删** (步骤 4 删了未合并分支) | `git reflog` 恢复分支 + `git worktree add` 重建 worktree; cleanup 脚本必须 dry-run 先看清单再 `--apply` | < 15 min |

> **失败纪律**: 任一步失败, 优先回滚 + 记录, 不做第 3 次失败尝试 (W67 第 47 步铁律). 部署 (步骤 1-4) 与真跑 (步骤 5-10) 相互独立, 真跑失败不影响部署产出对用户可见.

---

## §6 总结

- **W68 第 11 批 D-4 = 锚点范式第 145 守恒** — 仅 docs + memory, 0 production code 改动铁律维持.
- **推荐选项 A** — 主指挥部署 W68 第 5-11 批到云 server + 真跑验证 (10 步 checklist, 120-180 min). 部署缺口是 W68 唯一未闭环项.
- **选项 B/C** — 派 W69/W70 (子 plan ② 已实施 + 6 plans backlog + ppt-word PR2/PR3), 建议部署稳定后启动.
- **选项 D** — 转 Q4 商业化打包 (24 人月), 与选项 A 组合 (先部署稳定, 后转商业化).
- **W19 选项 A 维持** — 4 留未来 PR 不发起新排期.

---

*本文档由 W68 第 11 批 D-4 Agent 产出, 主指挥拍板依据. 部署 checklist 由主指挥本地 PC 执行.*
