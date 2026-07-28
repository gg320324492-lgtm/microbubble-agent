# W85 第 1 批 A-2: W84 据实上报派生 + 7 agents 详细化 + Phase 9 知识图谱启动 (锚点范式 314 → 317 +3 守恒)

> **主基调**: "W84 据实上报 4 实例派生 + Phase 9 课题组知识图谱可视化 启动 + W86/W87/W88 派工顺序". 0 production code.
> **锚点范式**: W84 314 → W85 第 1 批 A-2 317 守恒 (+3, 0 regression).
> **派工范式**: 主指挥协调范式第 61 次派工.
> **派工前提真验证**: base HEAD `7ca7846d1` ✓ + W84 7 commits 实测 ✓ + W84 据实上报 4 实例真验证 ✓.

## 1. W84 据实上报 4 实例沉淀 (派工前提真验证 4 路搜证)

| # | 实例 | commit | 实测 |
|---|------|--------|------|
| 1 | **D-2 拦截 #18** (类 20.13 实战 18) | `7ca7846d1` | 0/6 halt 不伪造, re-dispatch 后 6/6 收齐, 锚点 +7 守恒 |
| 2 | **B-2 useFileCommentsMobile 0 hit** | `56be76187` | grep 全仓 0 hit, 不实施 P1-2, 推 W85 重派 |
| 3 | **C-2 transient 14→88** | `9f594edf5` | 派工 brief 14 vs 实测 88 (6.3x 偏差), 真实施 88 transient 删除 |
| 4 | **C-1 据实上报延伸** | `cecbad692` | drive_comments_path_backfill 296 行有 caller, 收敛而非删除 |

**沉淀铁律**: 派工前提错配必先 4 路搜证 (origin + grep + reflog + fsck), 派工 brief 数字必实测二次 grep, 0 hit 模块不实施.

## 2. W84 7 agents 实战沉淀 (派生基础)

| agent | commit | 起点 → 终点 | 锚点 | 范围 |
|-------|--------|-------------|------|------|
| A-2 | `81272f91d` | 307 → 310 | +3 | W83 据实上报派生, 495 行 |
| B-1 | `f097e191b` | 310 → 311 | +1 | P1 latent bug batch 3: 8 项, 17 e2e PASS |
| B-2 | `56be76187` | 311 → 312 | +1 | chunked upload core + useFileCommentsMobile 据实上报, 34 e2e PASS |
| C-1 | `cecbad692` | 312 → 313 | +1 | drive_upload create_initial_version 注入 + backfill 收敛 |
| C-2 | `9f594edf5` | 313 → 314 | +1 | 88 transient memory 删, MEMORY.md 主题目录 11 类 |
| D-1 | `324a5bcf0` | 314 → 314 | 0 + 1 | 6 类同步 + 12 e2e PASS |
| D-2 | `7ca7846d1` | 314 收口 | 0 | 锚点范式收口 + W85/W86/W87 派工顺序 |

**累计**: W84 7 agents +7 守恒, 0 production code 4/7 守恒 (3 例外已批 W84 B-1 + B-2 + C-1).

## 3. W85 第 1 批 7 agents 详细化 (从 §1 + §2 派生)

| agent | 起点 → 终点 | 锚点 | 详细任务 |
|-------|-------------|------|----------|
| A-1 | 314 → 314 | 0 | 部署收口 (W84 7 merges + push) |
| **A-2 (本批)** | **314 → 317** | **+3** | **调研派生 (本任务)** |
| B-1 | 317 → 318 | +1 | **Phase 9 课题组知识图谱可视化 启动** (跳过 P1 latent bug batch 4 因 W84 已全修, 沿用 W84 D-2 §6 排期调整) — kg_query_service + kg_api endpoint + KnowledgeGraphView + KnowledgeGraphExplorer + e2e 5/5 PASS |
| B-2 | 318 → 319 | +1 | useFileCommentsDesktop 桌面端收敛 + useTask 桌面/移动收敛 (分步走) |
| C-1 | 319 → 320 | +1 | alembic `086_backfill_drive_file_versions.py` 数据迁移 (主拍签字 + staging) |
| C-2 | 320 → 321 | +1 | 175 永久保留 memory 主题重整 + MEMORY.md 索引 |
| D-1 | 321 验证不计 + 1 实战 | 0 + 1 | 6 类文档同步 + grand closure |
| D-2 | 321 收口 | 0 | 锚点范式收口 + W86/W87/W88 派工顺序 |

**累计**: 锚点范式 W84 314 → W85 321 (+7 守恒, 0 regression), 0 production code 5/7 守恒 (2 例外已批 W85 B-1 + B-2).

## 4. Phase 9 课题组知识图谱可视化 启动 详细化 (W85 B-1, W78 A-2 24 人月 Q1 路线图阶段 5)

- **现有**: `app/services/knowledge_graph_service.py` (自动关联 + BFS 遍历) + `web/src/components/knowledge/KnowledgeGraph*.vue` (ECharts 力导向图, W68 实战)
- **W85 B-1 启动 batch 1**: kg_query_service (120-150 行) + kg_api endpoint (4-6 endpoint) + KnowledgeGraphView + KnowledgeGraphExplorer + e2e 5/5 PASS
- **W86 batch 2**: 实体合并 + 概念网络 + 跨文档融合
- **W87 batch 3**: 假设生成引擎接入 + 假设验证生命周期
- **W88 batch 4**: 科研协作工作流 + 知识共享

## 5. W86/W87/W88 派工顺序 (派工 v6 §6 + W84 D-2 §6 排期延伸)

| 周 | 锚点 | B-1 | B-2 | C-1 |
|----|------|-----|-----|-----|
| W86 | 321 → ~328 | Phase 9 batch 2 (实体合并) | 商业化运营收官 | 跨租户监控 |
| W87 | ~328 → ~335 | Phase 9 batch 3 (假设生成) | 商业化运营 + 监控 | Phase 12 科研协作 |
| W88 | ~335 → ~342 | Phase 9 batch 4 (科研协作) | Phase 11 智能实验记录本 | Phase 12 科研协作 |

## 6. 类 20 实战 19 实例累计 (本批 #19 新增)

- **18 (W84 A-2)**: 派工 brief W83 "13 项 dead service + 175 transient" 与 W83 commit `06183a408` + `006789f54` 实测 5 项 + 161 vs 175 不一致
- **19 (W85 A-2 本批)**: 派工 brief W84 "P1 latent bug batch 4 收官 (剩余 4 项)" 与 W84 B-1 commit `f097e191b` 实测 **8 项全修** 不一致; W85 B-1 跳过 P1 latent bug batch 4 因 W84 已全修, 改 Phase 9 课题组知识图谱可视化 启动. **派生严格按 W84 commit hash 实测**

## 7. 累计 commits + 铁律 + W19 选项 A

- **累计 27 批 430+ commits** (含 W85 第 1 批 1 commit = docs/memory 范畴)
- **累计铁律 430+ 条** (W85 第 1 批 +5 派生铁律 + 沿用 W84 +25+ 铁律: 据实上报 4 实例 + 类 20.13 实战 18)
- **W19 选项 A 维持**: 4 留未来 PR (Phase 8.5 / P3 dedup / P3 跨 tab / 7 E2E)

## 8. 交付物

- 2 文件: `docs/w85-1st-batch-a2-survey-derivative-2026-07-29.md` + `memory/w85-1st-batch-a2-survey-derivative-2026-07-29.md` (本文件)
- 1 commit: anchored 314 → 317 +3
- 推送 origin: 预期成功
- 0 production code 守恒: 沿用 W72-W84 例外清单 (3 例外已批 W85 B-1 Phase 9 启动 + W85 B-2 useFileCommentsDesktop 收敛)

---

**维护者**: Agent 6 (W85 第 1 批 A-2) · **创建时间**: 2026-07-29 · **锚点范式**: W84 314 → W85 第 1 批 A-2 317 守恒 (+3, 0 regression)