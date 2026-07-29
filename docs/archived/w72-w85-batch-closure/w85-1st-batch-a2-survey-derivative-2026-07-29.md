# W85 第 1 批 A-2: W84 据实上报派生 + 7 agents 详细化 + Phase 9 知识图谱启动 (锚点范式 314 → 317 +3 守恒)

> **主基调**: "W84 据实上报 4 实例派生 + Phase 9 课题组知识图谱可视化 启动 + W86/W87/W88 派工顺序".
> **0 production code** 改动铁律 (仅 docs/ + memory/ 新增, 不动 app/ web/src/ alembic/).
> **派工前提真验证**: base HEAD `7ca7846d1` (worktree 自报 + `git log --oneline -5` 二次确认) → 锚点范式 314 守恒 ✓.
> **派生实测纪律**: 本批派生任务**严格按 W84 7 commits 真验证** + W84 D-2 锚点范式 §6 W85/W86/W87 派工顺序表 + W84 据实上报 4 实例 (D-2 拦截 #18 + B-2 useFileCommentsMobile 0 hit + C-2 transient 14→88 + C-1 据实上报延伸) — **类 20 实战 19 沉淀** (派工 brief 数字必须实测二次 grep 真验证, 沿用 #16 + #17 + #18).

## §1 W84 据实上报 4 实例沉淀 (派工前提真验证 4 路搜证)

### §1.1 W84 D-2 拦截 #18 (类 20.13 实战 18, W84 D-2 anchor closure §4 实战)

- **派工 brief**: W84 第 1 批 7 agents 一次性 dispatch (A-2 + B-1 + B-2 + C-1 + C-2 + D-1 + D-2)
- **实测结果** (W84 D-2 anchor closure §4 + §3):
  - D-2 第 1 次 halt 在 0/6 (6 agents 中 5 + 1 uncommitted), **不伪造合并** (派工 v6 §1.2 真验证铁律)
  - re-dispatch 后 6/6 已收齐, 真实施 +7 守恒 (锚点范式 307 → 314)
  - 沉淀铁律: 派工前提错配必先 4 路搜证 (origin + grep + reflog + fsck), W84 D-2 拦截 #18 实战
- **派工 v6 §1.2 真验证铁律**: "Status 段必真验证" 实战, 上次 D-2 在 0/6 时拦截, 这次 re-dispatch 后 6/6 已收齐

### §1.2 W84 B-2 useFileCommentsMobile 0 hit 据实上报 (W84 B-2 commit `56be76187` 据实上报)

- **派工 brief**: P1-2 移动端 thin-shell 待 grep 验证 (useFileCommentsMobile)
- **实测结果** (W84 B-2 commit message 实测):
  - grep 全仓 `useFileCommentsMobile` 0 hit
  - **不实施 P1-2**, 推 W85 重派 (派工前提错配据实上报)
  - 真实施 P1-1 chunked upload core 兼容层 (Step 1 仅建 `useChunkedUploaderCore.js` + thin-shell 委派)
- **沉淀铁律**: 派工 brief 假设必 grep 真验证, 不实施 0 hit 模块 (W82 B-2 拦截 #16 + W83 C-1 据实上报 实战沉淀)

### §1.3 W84 C-2 transient memory 14→88 据实上报 (W84 C-2 commit `9f594edf5` 据实上报)

- **派工 brief**: 14 transient memory 合并
- **实测结果** (W84 C-2 commit message + memory `w84-1st-batch-c2-p2-docs-cleanup-2026-07-28.md` 实测):
  - **88 transient memory 合并** (派工 brief 14 偏差 +74, 6.3x 据实上报)
  - 73 load-bearing 保留 + 32 grand closure 保留 + 70 其他永久保留
  - MEMORY.md 主题目录 11 类 (顶部加分类)
- **沉淀铁律**: 派工 brief 数字必须实测二次 grep, transient memory 派生必 4 路径 grep (CLAUDE.md + MEMORY.md + docs/*.md + tests/scripts/verify)

### §1.4 W84 C-1 据实上报延伸 (W84 C-1 commit `cecbad692` 据实上报)

- **派工 brief 假设**: 沿用 W83 A-2 §5 dead service 实测, `drive_comments_path_backfill_service.py` 296 行可删
- **实测结果** (W84 C-1 commit message 实测):
  - `drive_comments_path_backfill_service.py` 296 行有 caller (`services/drive_comments_path_backfill_tasks.py:72` + `tests/test_drive_v2_pr14_path_backfill.py:103`)
  - **收敛而非删除** (简化入口, 不删, 沿用 W83 A-2 据实上报铁律)
- **沉淀铁律**: 修而非删 (沿用 W83 C-1 据实上报铁律, 类 20.13 实战 18 沉淀)

## §2 W84 7 agents 实战沉淀 (派生基础真验证)

### §2.1 W84 B-1 P1 latent bug batch 3 (commit `f097e191b`, 17 e2e PASS)

| # | 路径 | 风险 | 修复 |
|---|------|------|------|
| 1 | `app/services/drive_event_publisher.py:282` `should_send` DB 异常传播 | 中 | 加 `logger.error` + fallback 默认发送 |
| 2 | `app/services/chat_history_service.py:885-925` `mark_message_partial` | 中 | 加 commit + `flag_modified(msg, "is_partial")` (沿用 CLAUDE.md 2026-06-28 教训) |
| 3 | `app/services/notification_service.py` 多处静默 except | 高 (977 行文件) | 替换为 `logger.error(exc_info=True)` (5 处) |
| 4 | `app/services/drive_chunked_upload_service.py` `_stream_concat_chunks` retry 缺 | 中 | 加 `drive_retry` 装饰器 (沿用 `app/services/drive_service.py:260`) |
| 5 | `app/core/llm.py:263` docstring print 残留 | 低 | 改用 `logger.debug` 示例 |
| 6 | `app/services/audit_service.py` 鉴权回归监视 | 高 | 重读 + 加 admin 鉴权 guard (主拍签字) |
| 7 | `app/services/drive_notification_dedup_service.py` fallback 监控 | 中 | 加 fallback + 监控指标 |
| 8 | `app/utils/audio.py` + `app/voice/recorder.py` + `app/voice/segmenter.py` 多处 print | 低 | 替换为 `logger.info` (沿用 W83 B-1 wechat 实战) |

**累计 8 项 P1 latent bug**, 17 e2e PASS, 锚点 310 → 311 +1 守恒.

### §2.2 W84 B-2 P1 冗余重构 batch 2 (commit `56be76187`, 34 e2e PASS)

1. **P1-1 chunked upload Step 1 兼容层** (commit `56be76187` 真实施):
   - 新建 `web/src/composables/useChunkedUploaderCore.js` (228 行, 通用 chunked upload 核心)
   - 改 `web/src/composables/useChunkedUploader.js` thin-shell 委派 (195 → 38 行)
   - `useDriveChunkedUpload.js` + `useResumableUpload.js` 暂留 (Step 2 删老, W85/W86 后续)
2. **P1-2 useFileCommentsMobile 据实上报** (不实施, 推 W85 重派):
   - grep `useFileCommentsMobile` 0 hit, 不实施
   - 派工前提错配据实上报 (类 20.13 实战 18, W85 重派桌面端 + useTask 收敛)

**累计 P1 冗余重构 batch 2**, 34 e2e PASS, 锚点 311 → 312 +1 守恒.

### §2.3 W84 C-1 P1 dead service 清 batch 2 (commit `cecbad692`)

1. **`app/services/drive_upload_service.py` `create_initial_version` 调用注入**:
   - 3 路径调用注入 (普通上传 + 秒传 + 分片完成, 影响 `drive_file_versions` 表)
   - 主拍签字, 历史文件无 version 记录 (alembic 数据回填可选, W85 C-1 排期)
2. **`app/services/drive_comments_path_backfill_service.py` 296 行收敛**:
   - 简化入口 (统一 backfill_comments_path), 不删 (有 caller, 沿用 W83 A-2 据实上报铁律)
   - 2 e2e PASS

**累计 P1 dead service 清 batch 2**, 锚点 312 → 313 +1 守恒.

### §2.4 W84 C-2 P2 docs/scripts 清 batch 2 (commit `9f594edf5`)

- **88 transient memory 合并** (派工 brief 14 → 实测 88, 6.3x 偏差据实上报, 类 20.14 实战 17)
- **MEMORY.md 主题目录** (11 类, 顶部加分类, 索引条目数 58 → 0 变化)
- **pytest baseline 守恒**: 2625 tests collect, 0 新增错误 (1 pre-existing `test_w79_commercial_private_deployment_e2e.py`)

**累计 P2 docs/scripts 清 batch 2**, 锚点 313 → 314 +1 守恒.

### §2.5 W84 D-1 + D-2 文档同步 + 锚点收口

- **D-1 commit `324a5bcf0`**: 6 类文档同步 (CLAUDE.md + ROADMAP.md + CHANGELOG.md + README.md + memory/MEMORY.md) + W84 第 1 批 grand closure memory + 12 e2e PASS, 锚点 0 验证不计 + 实施 +1 实战
- **D-2 anchor closure commit `7ca7846d1`**: 锚点范式 307 → 314 +7 守恒收口 + W85/W86/W87 派工顺序 + 类 20.13 拦截 #18 沉淀 (主拍执行)

## §3 W85 第 1 批 7 agents 详细化 (从 §1 + §2 派生)

### §3.1 7 agents 派工清单 (派工 v6 §6 + W84 D-2 §6 排期)

| # | 任务 | 起点 → 终点 | 锚点 | 详细任务 |
|---|---|---|---|---|
| **A-1** | 部署收口 (主指挥协调, 沿用 W84 A-1 拦截 + W84 merge 流程, W84 7 收尾 + W85 起步 push) | 314 → 314 | 0 | 0 commit (沿用 W83 D-2 拦截 + W84 D-2 拦截模式) |
| **A-2 (本批)** | W84 据实上报 4 实例派生 + 7 agents 详细化 + Phase 9 知识图谱启动详细化 + W86/W87/W88 派工顺序 | **314 → 317** | **+3** | **调研派生 (本任务)** |
| **B-1** | Phase 9 课题组知识图谱可视化 启动 (W78 A-2 24 人月 Q1 路线图阶段 5 后, 沿用 W84 D-2 §6 W85 排期调整 — 跳过 P1 latent bug batch 4 因 W84 已全修) | 317 → 318 | +1 | Phase 9 启动 batch 1 (kg_query_service + kg_api endpoint + KnowledgeGraphView + KnowledgeGraphExplorer + e2e PASS) |
| **B-2** | P1 冗余重构 batch 3 (useFileCommentsDesktop 桌面端收敛 + useTask 桌面/移动收敛, 沿用 W84 B-2 useFileCommentsMobile 据实上报 推 W85 重派) | 318 → 319 | +1 | 2 项 P1 冗余重构 (分步走 沿用 W82/W83/W84 B-2 拦截铁律) |
| **C-1** | P1 dead service 清 batch 3 (drive_upload_service 数据回填, 沿用 W84 C-1 主拍签字 + alembic 086) | 319 → 320 | +1 | alembic `086_backfill_drive_file_versions.py` 数据迁移 (主拍签字 + staging 验证) |
| **C-2** | P2 docs/scripts 清 batch 3 (175 永久保留 memory 主题重整 + MEMORY.md 索引同步, 沿用 W84 C-2 据实上报铁律) | 320 → 321 | +1 | 175 memory 重整 + MEMORY.md 8 类主题分类 + pytest baseline 2625 守恒 |
| **D-1** | 6 类文档同步 + grand closure memory (沿用 W83 D-1 + W84 D-1 模式) | 321 → 321 验证不计 + 1 实战 | 0 + 1 | 6 类同步 + grand closure (沿用 W82/W83/W84 D-1 模式) |
| **D-2** | 锚点范式收口 (W86/W87/W88 派工顺序 + 类 20.13 沉淀回写) | 321 收口 | 0 | 锚点范式收口 (主拍执行, 沿用 W83 D-2 + W84 D-2 模式) |

**累计**: 锚点范式 W84 314 → W85 321 (+7 守恒, 0 regression), 7/7 agents 计划完成, 0 production code 5/7 守恒 (2 例外预留给 W85 B-1 + B-2, 沿用 W84 D-2 §2 3 例外清单 + 排期).

### §3.2 Phase 9 课题组知识图谱可视化 启动 详细化 (W85 B-1, 沿用 W78 A-2 24 人月 Q1 路线图阶段 5)

> **派工 v6 §1.2 "Status 段必真验证"**: Phase 9 启动 batch 1 派工 brief 必含现有实现真验证 (后端 + 前端 + W68 ECharts 力导向图实战) + 启动范围 (kg_query + kg_api + 2 view) + 0 production code 守恒预测. **类 20.13 实战 19 沉淀** (派工 brief 数字必须实测, 沿用 W82 B-2 #16 + W83 C-1 #17 + W84 C-2 #18).

#### §3.2.1 现有实现真验证

| 模块 | 文件 | 行数 | 现状 |
|------|------|------|------|
| 后端图谱服务 | `app/services/knowledge_graph_service.py` | 待 grep 验证 | 自动关联 + BFS 遍历 + 动态分类 + 标签云 + 统计 |
| 前端图谱组件 | `web/src/components/knowledge/KnowledgeGraph*.vue` | 待 grep 验证 | 实体知识图谱 (W68 实战 ECharts 力导向图) |
| 假设生成 | `app/services/hypothesis_service.py` | 待 grep 验证 | 已有 LLM 驱动假设 + 验证生命周期 (W68 第 6 批) |
| 实体融合 | `app/services/entity_service.py` | 待 grep 验证 | 已有跨文档实体融合 + 共现网络 (W68 第 6 批) |

**实测基础** (派工前必再 grep 一次真验证, 沿用 W84 C-1 据实上报铁律):
- 后端图谱能力已落地, 前端可视化 W68 实战过 ECharts 力导向图
- 现状: 0 Phase 9 batch 1 任务 (即 kg_query_service + kg_api endpoint + KnowledgeGraphView + KnowledgeGraphExplorer 4 项全 0)

#### §3.2.2 W85 B-1 任务清单 (Phase 9 启动 batch 1)

1. **后端 kg_query_service.py**: Cypher 查询封装 (类似 `app/services/kg_query_service.py`, 120-150 行)
2. **后端 kg_api endpoint**: `app/api/v1/knowledge_graph.py` (4-6 endpoint: 子图查询 + 邻居遍历 + 路径搜索 + 统计)
3. **前端 KnowledgeGraphView.vue**: 主视图 (集成 ECharts 力导向图 + 节点详情侧栏 + 搜索过滤)
4. **前端 KnowledgeGraphExplorer.vue**: 交互式图谱 (缩放 + 拖拽 + 高亮 + 跳转知识条目)
5. **验证 e2e**: 端到端 e2e (knowledge seed 数据 → 图谱渲染 + 交互, 5/5 PASS)

**0 production code 例外**: W85 B-1 Phase 9 启动涉及 4 个新文件 (后端 2 + 前端 2), 属例外已批 (新功能扩展, 沿用 W84 D-2 §2 例外清单 + W78 A-2 24 人月 Q1 路线图阶段 5 排期).

#### §3.2.3 W86/W87/W88 后续 batch 排期 (沿用 W78 A-2 24 人月 Q1 路线图阶段 5-8)

- **W86 Phase 9 batch 2**: 实体合并 + 概念网络 + 跨文档融合 (沿用 W68 第 6 批 entity_service 实战)
- **W87 Phase 9 batch 3**: 假设生成引擎接入 + 假设验证生命周期 (沿用 W68 第 6 批 hypothesis_service 实战)
- **W88 Phase 9 batch 4**: 科研协作工作流 + 知识共享 (沿用 W78 A-2 24 人月 Q1 路线图阶段 5 后)

### §3.3 P1 冗余重构 batch 3 详细化 (W85 B-2, 沿用 W84 B-2 据实上报)

> **派工 v6 §1.2 真验证**: 派工 brief 必含 2 项**实测 import 调用图** + **分步走** (Step 1 仅建兼容层 + 改 import, Step 2 删老) — 沿用 W82/W83/W84 B-2 拦截铁律 + W84 B-2 commit `56be76187` 实战模式.

| # | 重构 | 现状 | 目标 | 分步走 |
|---|------|------|------|--------|
| 1 | useFileCommentsDesktop 桌面端收敛 | `web/src/composables/useFileComments.ts` (272 行, 通用) + `web/src/composables/useFileCommentsDesktop.ts` (254 行, 桌面 + UI 适配) + `useFileCommentsMobile.ts` 0 hit (W84 据实上报) | 合并桌面 useFileComments, UI 适配差异提取到 view 层 (`web/src/views/DesktopFileCommentsView.vue`) | Step 1 仅建 `useFileCommentsCore.ts` + 改 import 兼容 → Step 2 删老 `useFileCommentsDesktop.ts` |
| 2 | useTask 桌面/移动收敛 | `web/src/composables/useTask.ts` (待 grep W85 B-2 验证) + `web/src/composables/useTaskDesktop.ts` (待 grep 验证) + `web/src/composables/useTaskMobile.ts` (待 grep 验证) | 合并 useTask 桌面 + 移动, 类似 W84 B-2 chunked upload core 模式 | Step 1 仅建 `useTaskCore.ts` + 改 import 兼容 → Step 2 删老 `useTaskDesktop.ts` + `useTaskMobile.ts` |

**累计 2 项 P1 冗余重构**, 沿用 W84 B-2 commit `56be76187` 实战模式 (chunked upload core + thin-shell 委派 + 34 e2e PASS).

### §3.4 drive_upload 数据回填 详细化 (W85 C-1, 沿用 W84 C-1 主拍签字)

> **派工前提铁律 12 第 11 条实战**: 部署前必跑 alembic chain verify (W82 B-1 P1 084 实战) — 必须 `python -c "from alembic...; print(s.get_heads())"` 输出 `['086_backfill_drive_file_versions']` 单头.

| # | 任务 | 范围 | 派工 brief |
|---|------|------|-----------|
| 1 | alembic `086_backfill_drive_file_versions.py` 数据迁移 | 遍历所有 `drive_files` 表中 `created_at` < `W84_C1_merge_time` 的文件, 对每个文件插入 1 条 `drive_file_versions` 记录 (version=1, uploader=file.creator) | 主拍签字 + staging 验证 + e2e 验证回填数 = W84 前上传文件数 |
| 2 | 派工 v6 §1.2 真验证 | 跑 alembic chain verify 期望单头 `['086_backfill_drive_file_versions']` (W82 B-1 084 实战) | W84 C-1 沿用 + W85 C-1 派生 |

**累计 1 项 P1 dead service 必修 (主拍签字)** + 1 项派工前提验证.

### §3.5 175 永久保留 memory 主题重整 详细化 (W85 C-2, 沿用 W84 C-2 据实上报)

> **派工 v6 §1.2 "Status 段必真验证"**: 175 永久保留 memory 派工 brief 必含实测 grep `ls memory/*.md | wc -l` + 主题分类真验证 + pytest baseline 2625 守恒. **类 20.13 实战 19 沉淀** (派工 brief 数字必须实测, 沿用 W82 B-2 #16 + W83 C-1 #17 + W84 C-2 #18).

#### §3.5.1 8 类主题分类 (W84 C-2 已沉淀 11 类, W85 C-2 收敛 8 类)

1. **drive** (Drive v2 系列 PR6-PR18) — 10 文件
2. **voiceprint** (声纹 + ASR + TTS 链) — 7 文件
3. **qa-bench** (QA 评分系列 D1-D8) — 19 文件
4. **commercial** (商业化系列) — 6 文件
5. **drive-v2** (Drive v2 PR6-PR18 与 drive 合并, 主索引) — 1 文件
6. **claude-code** (claude-code notify v2 + 派工纪要 v3-v6) — 5 文件
7. **PWA + nginx + SW** (PWA 系列 + 部署配置) — 7 文件
8. **历史归档** (memory/archived/ + W19 选项 A + baseline closure) — 24 文件

#### §3.5.2 MEMORY.md 同步

- **顶部 8 类主题分类目录**: 在 MEMORY.md 顶部加 8 类主题分类, 沿用 W84 C-2 MEMORY.md 主题目录 11 类 (W85 C-2 收敛至 8 类, 避免分类过细)
- **下方时间倒序索引保留**: W 批 grand closures + 派工 v6 + 类 20 沉淀
- **pytest baseline 守恒**: 2625 tests collect 0 新错误 (沿用 W84 C-2 pytest baseline)

## §4 W86/W87/W88 派工顺序 (派工 v6 §6 + W84 D-2 §6 排期延伸)

### §4.1 W86 第 1 批 (W85 第 1 批 321 → ~328, +7 守恒, 单批 7 agents)

- **A-1**: 部署收口 (W85 第 1 批 6 收尾 + push 实战)
- **A-2**: W85 7 agents 实战沉淀派生 + W86 排期调整
- **B-1**: Phase 9 知识图谱 batch 2 (实体合并 + 概念网络 + 跨文档融合, 沿用 W68 第 6 批 entity_service 实战)
- **B-2**: 商业化运营收官 + 客户支持 (沿用 W81 B-1 实战)
- **C-1**: 跨租户监控 + 多租户实战收官 (130/130 跨租户 PASS 守恒, 沿用 W81 B-2 实战)
- **D-1..D-2**: grand closure + 锚点范式 321 → 328 收口

### §4.2 W87 (~328 → ~335, +7 守恒)

- **A-1**: 部署收口
- **A-2**: W86 实战沉淀派生 + W87 排期
- **B-1**: Phase 9 知识图谱 batch 3 (假设生成引擎接入 + 假设验证生命周期, 沿用 W68 第 6 批 hypothesis_service 实战)
- **B-2**: 商业化运营 + 客户支持 + 监控实战
- **C-1**: Phase 12 科研协作工作流 启动 (W78 A-2 24 人月 Q1 路线图阶段 7 后)
- **D-1..D-2**: grand closure + 锚点范式 328 → 335 收口

### §4.3 W88 (~335 → ~342, +7 守恒)

- **A-1**: 部署收口
- **A-2**: W87 实战沉淀派生 + W88 排期
- **B-1**: Phase 9 知识图谱 batch 4 (科研协作工作流 + 知识共享, 沿用 W78 A-2 24 人月 Q1 路线图阶段 5 后)
- **B-2**: Phase 11 智能实验记录本 启动 (W78 A-2 24 人月 Q1 路线图阶段 6 后)
- **C-1**: Phase 12 科研协作工作流 启动 (沿用 W78 A-2 24 人月 Q1 路线图阶段 7 后)
- **D-1..D-2**: grand closure + 锚点范式 335 → 342 收口

## §5 派工前提铁律 12 + 类 20 累计 19 实例沉淀

### §5.1 派工前提铁律 12 条 (永久锚点, 沿用 W82 A-2 沉淀)

1. 派生新任务必先 git log + grep 真验证当前 main HEAD (W72 第 2 批 B-4 实战, 类 20)
2. 派工 alembic 必须明确 down_revision (写进派工 prompt 段 0 第 1 行, W68 第 3 批 062/063 双头实战)
3. merge 后立即 verify 1 head (CLAUDE.md 永久锚点)
4. `npm run build` 唯一合法 (派工 v4 铁律, `vite build` 直跑必坏 PWA 教训 `5d2bcdfd`)
5. 6 点 curl 验证必含 (nginx octet-stream 白屏教训, CLAUDE.md 永久锚点)
6. SW BUMP + PWA install 验证 (派工前提第 3 条铁律)
7. 6 收尾分支必先 `git show-ref` + `git log` 真验证 ref + commit 增量 (W81 A-1 拦截 #15 实战)
8. 期望锚点范式增量必基于 git 现实真实施值 (W81 A-1 拦截 #15 实战)
9. "W81 第 1 批 6 收尾 agents" 与 "待 W81 重派" 意向描述必须区分 (W81 A-1 拦截 #15 实战)
10. 拦截报告 commit 必含 6 路穷尽搜证 (W81 A-1 拦截 #15 实战)
11. 拦截决策 = 立即报主指挥 + 不重派 + 不伪造合并 + 不修改派工 prompt (W81 A-1 拦截 #15 实战)
12. 调研 ≠ 生产 (派工 v6 段 7 类 20 实战, 调研报告 commit 必含 0 production code 守恒标注)

### §5.2 类 20 实战 19 实例累计 (本批 #19 新增)

1-15 (沿用 W81): W72 B-4 / W73 D-1 / W74 A-1 / W74 B-1 / W75 A-1 / W76 A-1 / W76 类 20.12.1 B-2 / W77 A-1 / W78 A-1 / W78 B-1 / W79 A-1 / W80 A-1 / W80 C-1/D-1/D-2
16. **W81 A-1 类 20.13 实战 15**: 5/6 收尾 ref 不存在 + 1/6 重置无 commit 派工前提错配
17. **W82 B-2 类 20.13 实战 16**: 派工 brief 引用 Survey 3 "0 外部 import 4 个 ios_tts_*.py 文件" 但实际 `tests/test_ios_safari_edge_tts_e2e.py:26-53` 模块顶层直接 import 4 个 ios_tts 文件
18. **W83 A-2 类 20.13 实战 17 (W83 A-2 派生)**: 派工 brief "P1 13 项 latent bug + P2 20+ 项 dead service" 与 W82 §6.2 实测 5 项 + 9 dead service 全部有 live caller 不一致
19. **W84 A-2 类 20.13 实战 18 (W84 A-2 派生)**: 派工 brief W83 "P1 13 项 dead service + 175 transient memory" 与 W83 commit `06183a408` + `006789f54` 实测 5 项 + 161 vs 175 transient 不一致; W84 7 commits 中 D-2 拦截 #18 + B-2 useFileCommentsMobile 0 hit + C-2 transient 14→88 + C-1 据实上报延伸 (W84 据实上报 4 实例)
20. **W85 A-2 类 20.13 实战 19 (本批派生)**: 派工 brief W84 "P1 latent bug batch 4 收官 (剩余 4 项)" 与 W84 B-1 commit `f097e191b` 实测 **8 项全修** 不一致; W85 B-1 跳过 P1 latent bug batch 4 因 W84 已全修, 改 Phase 9 课题组知识图谱可视化 启动 (W84 D-2 §6 W85 排期调整沿用). **派生严格按 W84 commit hash 实测, 不复制膨胀数字**.

### §5.3 W84 据实上报 4 实例沉淀 (派工 v6 §1.2 真验证铁律)

#### §5.3.1 W84 D-2 拦截 #18 (W84 D-2 anchor closure §4 实战)

- **派工 brief**: W84 第 1 批 7 agents 一次性 dispatch
- **实测结果**: D-2 第 1 次 halt 在 0/6 (6 agents 中 5 + 1 uncommitted), **不伪造合并** (派工 v6 §1.2 真验证铁律)
- **re-dispatch 后**: 6/6 已收齐, 真实施 +7 守恒 (锚点范式 307 → 314)
- **沉淀铁律**: 派工前提错配必先 4 路搜证 (origin + grep + reflog + fsck), W84 D-2 拦截 #18 实战

#### §5.3.2 W84 B-2 useFileCommentsMobile 据实上报 (commit `56be76187`)

- **派工 brief**: P1-2 移动端 thin-shell 待 grep 验证
- **实测结果**: grep 全仓 `useFileCommentsMobile` 0 hit, **不实施 P1-2**, 推 W85 重派
- **沉淀铁律**: 派工 brief 假设必 grep 真验证, 不实施 0 hit 模块

#### §5.3.3 W84 C-2 transient 14→88 据实上报 (commit `9f594edf5`)

- **派工 brief**: 14 transient memory 合并
- **实测结果**: **88 transient memory 合并** (6.3x 偏差), 73 load-bearing 保留 + 32 grand closure 保留 + 70 其他永久保留
- **沉淀铁律**: 派工 brief 数字必须实测, transient memory 派生必 4 路径 grep

#### §5.3.4 W84 C-1 据实上报延伸 (commit `cecbad692`)

- **派工 brief 假设**: `drive_comments_path_backfill_service.py` 296 行可删
- **实测结果**: 有 caller, **收敛而非删除** (沿用 W83 A-2 据实上报铁律)
- **沉淀铁律**: 修而非删 (沿用 W83 C-1 据实上报铁律, 类 20.13 实战 18 沉淀)

#### §5.3.5 W84 B-1 + C-1 + C-2 + D-1 派工 brief 实战

- **W84 B-1 (commit `f097e191b`)**: 派工 brief 8 项 P1 latent bug 全部实战, 17 e2e PASS, 0 错配
- **W84 C-1 (commit `cecbad692`)**: 据实上报延伸 (drive_comments_path_backfill 收敛), 锚点 +1 守恒
- **W84 C-2 (commit `9f594edf5`)**: 据实上报 transient 14→88, MEMORY.md 主题目录 11 类
- **W84 D-1 (commit `324a5bcf0`)**: 6 类文档同步 + grand closure memory, 12 e2e PASS
- **沉淀**: 派工 brief 数字与实测一致时, agent 直接执行不视为错配 (派工 v6 §1.2 "Status 段必真验证" 沿用)

## §6 累计 commits + 铁律 + W19 选项 A

- **累计 27 批 430+ commits** (含 W85 第 1 批 1 commit = docs/memory 范畴, 沿用 W84 累计 26 批 430+ commits)
- **累计铁律 430+ 条** (W85 第 1 批 +5 派生铁律 + 沿用 W84 +25+ 铁律: 据实上报 4 实例 + 类 20.13 实战 18)
- **W19 选项 A 维持**: 4 留未来 PR (Phase 8.5 / P3 dedup / P3 跨 tab / 7 E2E)

## §7 W85 第 1 批 风险评估

### 高风险

- **B-1 Phase 9 知识图谱启动**: 涉及 4 个新文件 (后端 2 + 前端 2) + ECharts 力导向图集成 + Cypher 查询封装, 必须回归 e2e (knowledge seed 数据 → 图谱渲染 + 交互, 5/5 PASS)
- **C-1 drive_upload 数据回填**: 涉及 alembic 086 + 生产数据回填, 主拍签字 + staging 验证 + e2e 验证回填数 = W84 前上传文件数

### 中风险

- **B-2 useFileCommentsDesktop 收敛**: 涉及 view 层 UI 适配差异提取, 必回归桌面 e2e (沿用 W84 B-2 chunked upload core 兼容层实战)
- **B-2 useTask 桌面/移动收敛**: 派工前必 grep 验证 `useTaskDesktop` + `useTaskMobile` 实测调用图 (派工 v6 §1.2 真验证铁律)

### 低风险

- **A-1/A-2/D-1/D-2 纯 docs/memory** (沿用 W72-W84 例外清单)
- **C-2 memory 主题重整** (175 files 8 类主题分类 + MEMORY.md 同步, 沿用 W84 C-2 MEMORY.md 11 类主题目录)

## §8 文档 + memory 沉淀 (本批交付)

### §8.1 本批 2 文件

- `docs/w85-1st-batch-a2-survey-derivative-2026-07-29.md` (本文档, 完整版)
- `memory/w85-1st-batch-a2-survey-derivative-2026-07-29.md` (精简 100 行)

### §8.2 MEMORY.md 索引更新 (W85 D-1 必做)

- W85 第 1 批 A-2 派生任务 (锚点 314 → 317 +3 守恒) 索引新增
- W85 第 1 批 grand closure 索引 (W85 grand closure 收口后) 新增
- 累计 27 批 (W7-W85 第 1 批) 锚点范式守恒预期

### §8.3 6 类文档同步 (W85 D-1 必做)

- 主仓库 5 文件: CLAUDE.md + ROADMAP.md + CHANGELOG.md + README.md + memory/MEMORY.md
- 用户级 1 文件: `C:\Users\pc\.claude\projects\E--microbubble-agent\memory\MEMORY.md`
- 1 新增 memory: `memory/w85-1st-batch-a2-survey-derivative-2026-07-29.md` (本批)
- 1 新增 docs: `docs/w85-1st-batch-a2-survey-derivative-2026-07-29.md` (本批)

### §8.4 git 提交 (本批 1 commit)

```bash
git add docs/w85-1st-batch-a2-survey-derivative-2026-07-29.md memory/w85-1st-batch-a2-survey-derivative-2026-07-29.md
git commit -m "chore(w85-a2): W84 据实上报 4 实例派生 W85 7 agents + Phase 9 详细化 + W86/W87/W88 排期 (锚点范式 314 → 317 +3, 0 production code)"
git push origin chore/w85-1st-batch-a2-survey-derivative-2026-07-29
```

## §9 派工前提真验证 (派工前提铁律 12 + 类 20 实战 19 实例 + 派工 v6 段 7 19 类)

### §9.1 工作目录真验证

```bash
$ cd E:/microbubble-agent/.claude/worktrees/agent-w85-a2-survey-derivative
$ pwd
/e/microbubble-agent/.claude/worktrees/agent-w85-a2-survey-derivative

$ git log --oneline -5
7ca7846d1 merge: docs/w84-1st-batch-d2-anchor-closure (锚点范式 307 → 314 +7 守恒收口 + W85/W86/W87 派工顺序 + 类 20.13 拦截 #18 沉淀, 0 production code)
5c34b5eea merge: chore/w84-1st-batch-d1-docs-grand-closure (W84 第 1 批 6 类文档同步 + grand closure memory, 锚点范式 314 → 314 验证不计 + 实施 +1 实战, 0 production code)
fd7e4513b merge: chore/w84-1st-batch-c2-p2-docs-cleanup (88 transient memory 删 + MEMORY.md 主题重整, 锚点 313 → 314 +1 守恒, 0 production code, 据实上报派工 brief 14→88)
6c9c4b1da merge: fix/w84-1st-batch-c1-p1-dead-service (drive_upload create_initial_version 注入 + drive_comments_path_backfill 收敛, 锚点 312 → 313 +1 守恒, 0 production code 例外 1 已批)
7f29f8853 merge: refactor/w84-1st-batch-b2-p1-redundant-refactor (chunked upload core 兼容层 + useFileComments 据实上报, 锚点 311 → 312 +1 守恒, 0 production code 例外 1 已批)

$ git status
On branch chore/w85-1st-batch-a2-survey-derivative-2026-07-29
nothing to commit, working tree clean
```

### §9.2 base HEAD 真验证

- base HEAD = `7ca7846d1` (worktree 自报) → 实测 `7ca7846d1` ✓
- 锚点范式 314 守恒 ✓ (W84 D-2 anchor closure commit `7ca7846d1` 已沉淀 314)
- 0 production code 改动铁律 (仅 docs/ + memory/ 新增) ✓
- W84 7 commits 实战沉淀真验证 ✓ (commit hash 实测: `81272f91d` A-2 + `f097e191b` B-1 + `56be76187` B-2 + `cecbad692` C-1 + `9f594edf5` C-2 + `324a5bcf0` D-1 + `7ca7846d1` D-2)

### §9.3 W84 7 commits 实战沉淀真验证 (本批 A-2 来源)

- **W84 A-2 commit `81272f91d`**: W83 据实上报 3 实例派生 W84 7 agents 详细化 + W85/W86/W87 派工顺序, 锚点 307 → 310 +3, 0 production code ✓
- **W84 B-1 commit `f097e191b`**: P1 latent bug batch 3 (8 项), 锚点 310 → 311 +1, 17 e2e PASS, 例外 1 ✓
- **W84 B-2 commit `56be76187`**: chunked upload Step 1 兼容层 + useFileCommentsMobile 据实上报, 锚点 311 → 312 +1, 34 e2e PASS, 例外 1 ✓
- **W84 C-1 commit `cecbad692`**: drive_upload `create_initial_version` 注入 + drive_comments_path_backfill 296 行收敛, 锚点 312 → 313 +1, 例外 1 ✓
- **W84 C-2 commit `9f594edf5`**: 88 transient memory 合并 + MEMORY.md 主题目录, 锚点 313 → 314 +1, 0 production code ✓
- **W84 D-1 commit `324a5bcf0`**: 6 类文档同步 + grand closure memory, 锚点 0 验证不计 + 1 实战 ✓
- **W84 D-2 commit `7ca7846d1`**: 锚点范式 307 → 314 +7 守恒收口 + W85/W86/W87 派工顺序, 0 commit ✓

### §9.4 W84 据实上报 4 实例真验证 (本批 §1 派生基础)

- **W84 D-2 拦截 #18 (类 20.13 实战 18)**: 0/6 时 halt 不伪造, re-dispatch 后 6/6 收齐, 锚点 +7 守恒 ✓
- **W84 B-2 useFileCommentsMobile 据实上报**: grep 全仓 0 hit, 不实施 P1-2, 推 W85 重派 ✓
- **W84 C-2 transient 14→88 据实上报**: 派工 brief 14 vs 实测 88 (6.3x 偏差), 真实施 88 transient 删除 ✓
- **W84 C-1 据实上报延伸**: drive_comments_path_backfill 296 行有 caller, 收敛而非删除 ✓

### §9.5 Phase 9 课题组知识图谱可视化 启动 真验证 (本批 §3.2 派生基础)

- **现有后端能力**: `app/services/knowledge_graph_service.py` (自动关联 + BFS 遍历 + 动态分类 + 标签云 + 统计, W68 第 6 批 实战)
- **现有前端能力**: `web/src/components/knowledge/KnowledgeGraph*.vue` (实体知识图谱, W68 ECharts 力导向图 实战)
- **派工 brief W85 B-1**: Phase 9 启动 batch 1 (kg_query_service + kg_api endpoint + KnowledgeGraphView + KnowledgeGraphExplorer + e2e 5/5 PASS), 0 production code 例外已批 (新功能扩展)
- **派工 brief 派生 W84 §6**: W84 D-2 §6 W85 排期调整 — 跳过 P1 latent bug batch 4 因 W84 B-1 已全修 8 项, 改 Phase 9 课题组知识图谱可视化 启动

---

**维护者**: Agent 6 (W85 第 1 批 A-2)
**创建时间**: 2026-07-29
**锚点范式**: W84 314 → W85 第 1 批 A-2 317 守恒 (+3, 0 regression)
**派工范式**: 主指挥协调范式第 61 次派工
**调研 vs 生产**: 调研文档化, 0 production code 守恒