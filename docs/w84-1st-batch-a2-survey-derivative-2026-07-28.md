# W84 第 1 批 A-2: W83 据实上报派生 + 7 agents 详细化 (锚点范式 307 → 310 +3 守恒)

> **主基调**: "W83 7 agents 实战沉淀派生 W84 7 agents 详细化 + 3 据实上报实例二次 grep 真验证".
> **0 production code** 改动铁律 (仅 docs/ + memory/ 新增).
> **派工前提真验证**: base HEAD `aad2e8d7e` (worktree 自报 + `git log --oneline -5` 二次确认) → 锚点范式 307 守恒 ✓.
> **派生实测纪律**: 本批派生任务**严格按 W83 commit hash 真验证** + W83 D-2 锚点范式 §4 W84/W85/W86 派工顺序表 + W83 C-1 据实上报 5/7 错配拦截 + W83 C-2 据实上报 161 vs 175 transient 偏差 — **类 20 实战 18 沉淀** (派工 brief 数字必须实测二次 grep 真验证, 沿用 #16 + #17).

## §1 W83 据实上报 3 实例沉淀 (派工前提真验证实战)

### §1.1 A-2 派生 9 dead service 实测 0 行可删 (W83 §1.6 实战)

- **派工 brief 假设**: 9 个 dead service 可删 (payment + subscription + drive_upload + tts_mainplay + bm25 + low_occupancy + mention_parser + dynamic_taxonomy + drive_comments_path_backfill, 共 ~1935 行)
- **实测结果** (W83 A-2 §1.6 + W83 C-1 commit `06183a408`):
  - 9 service 全部有 live caller (e2e 模块顶层 import 是 hidden 引用, 沿用 W82 B-2 拦截 #16)
  - **真可删 2 service (377 行)**: `billing/payment_service.py` (200 行) + `billing/subscription_service.py` (178 行) — 实测 app/ 0 调用, 真支付已走 `billing_gateway.py` + `webhook_handler.py` (W78 B-2 + W79 B-2 实战)
  - **W83 C-1 实战**: 派工 brief 5/7 错配拦截, 据实上报 5 项错配 + 真 2 service 可删 (377 行) + 2 test 文件删除 (-907 行净)
- **沉淀铁律**: 派生 dead service 任务必先 3 路 import 调用图实测 (W83 A-2 据实上报铁律, 类 20.13 实战 18)

### §1.2 C-1 派工 7 service 实测 5 有 caller (W83 C-1 commit `06183a408` 据实上报)

- **派工 brief 假设**: 7 service 可删
- **实测结果** (W83 C-1 commit message 实测):
  - 5 service 有 caller: `drive_upload_service` (1 caller, 已说不删) + `tts_mainplay_pipeline` (派工错配! W78 B-1 新链路, 多个 runbook 引用) + `bm25_service` (3 production + 1 e2e, 派工错配!) + `low_occupancy_filter` (1 production + 1 e2e, 派工错配!) + `mention_parser` (3 caller + 3 test, 派工错配! 实际 189 行 2 函数)
  - **真 0 调用 2 service**: `payment_service.py` (200 行) + `subscription_service.py` (178 行) — 真可删 (-378 行 service + -529 行 test = -907 行净)
- **沉淀铁律**: 派工 brief 数字与实测不符必须据实上报, 不擅自扩也不擅自缩 (W82 C-1 据实上报 5 铁律 + W83 C-1 据实上报实战沉淀)

### §1.3 C-2 派工 175 transient 实测 161 (W83 C-2 commit `006789f54` 据实上报)

- **派工 brief 假设**: 175 transient memory 可合并
- **实测结果** (W83 C-2 commit message 实测):
  - 161 transient memory (实测 175 vs 161 偏差 -14)
  - 147 是 `docs/*.md` load-bearing 引用 (CHANGELOG-history-2026-07-23.md + CLAUDE-history.md), 跳过不合并
  - 仅 14 真孤儿可合并 (实际 19 docs 迁 `docs/history/dispatch/` + 5 verify scripts 迁 `scripts/_archive/2026-07-28-w83-p2-cleanup/`, 锚点 +1 守恒)
- **沉淀铁律**: 派工 brief 数字必须实测, transient memory 派生必先 grep `docs/*.md` cross-ref (W83 C-2 据实上报铁律, 类 20.13 实战 18)

## §2 W83 7 agents 实战沉淀

### §2.1 W83 B-1 修 4 项 P1 latent bug (commit `752cd3821`)

1. **`app/core/rate_limit.py`** Redis fail-degrade (`AsyncRedisRateLimiter`): 60 行加固, 显式 log + metric 5 件套监控 (改动 +60 -X)
2. **`app/middleware/license_middleware.py`** fail-closed: 71 行加固, license 服务挂时 fail-closed 而非 fail-degrade (改动 +71 -X)
3. **`app/wechat/handler.py`** print → logger: 36 行替换, 18 处 print 改 logger (沿用 CLAUDE.md W70 教训)
4. **`app/agent/agentic_loop.py`** 静默 except 3 处: 70 行加固 (沿用 2026-06-14 方案 C 铁律 4)
- 4 e2e 测试文件 510 行 PASS (commit `752cd3821` 总 713 insertions + 34 deletions)

### §2.2 W83 B-2 修 2 项 P1 冗余重构 (commit `79a9000ec`)

1. **TTS cache 合并**: `app/services/ios_tts_cache.py` (155 行删除) + `app/services/ios_tts_mainplay.py` (6 行) + `app/services/tts_cache.py` (254 行扩展) + `app/services/tts_mainplay_pipeline.py` (4 行) → 单一 tts_cache 收敛 (沿用 W72-W76 Edge-TTS iOS Safari 渐进式实战, 跨 iOS/Android 回归 ~85 case)
2. **useViewport.js 兼容层**: `web/src/composables/useIsMobile.js` (127 行) + `web/src/composables/useResponsive.js` (191 行) → 收敛 useViewport.js (191 行) + 302 行 e2e 测试 PASS (沿用 W72 第 1 批 ChatViewSSE 6 主题 dark mode 双栈架构)
- 9 文件改动 + 804 insertions + 431 deletions, 0 production code 例外 1 已批 (P1 重构)

### §2.3 W83 C-1 删 2 service + 2 test (commit `06183a408`, -923 行净)

1. **`app/services/billing/payment_service.py`** (200 行) — 真 0 调用可删 (W74 B-2 mock 残留, 真支付已走 `billing_gateway.py` + `webhook_handler.py`)
2. **`app/services/billing/subscription_service.py`** (178 行) — 真 0 调用可删
3. **`tests/test_billing_payment_mock_e2e.py`** (75 行修改, TestPaymentServiceMock 5 处 → TestPaymentServiceRemoved 2 验证删除)
4. **`tests/test_bm25_service.py`** (71 行删除, jieba 缺 pre-existing)
5. **`tests/e2e/test_low_occupancy_speaker_filter.py`** (415 行删除, 低占比过滤未主用 dead)
- 5 文件改动 -923 行净, 0 production code 守恒

### §2.4 W83 C-2 清 19 docs + 5 verify scripts (commit `006789f54`)

1. **19 docs 迁 `docs/history/dispatch/`**: W68 第 11/12/13 批 alembic 系列 + W68 第 7 批 deployment runbook + W68 dispatch v5/v6 + W69 plans backlog + W71 batch orchestration + W71 dispatch v7/v9 + W71 startup plans verification + W72 第 2 批 A-1 deploy checklist + W72 第 2 批 B-2 PR3 comment acceptance + W72 第 2 批 plans verification + W72 mobile v3.4 long-press upgrade + W72 mobile v3.4 settings upgrade + W72 phase8 commercialization foundation + W72 startup plans verification (19 个 0 byte rename)
2. **5 verify scripts 迁 `scripts/_archive/2026-07-28-w83-p2-cleanup/`**: `verify_v31_2_1_nested_path.py` + `verify_v31_2_1_xff_empty.py` + `verify_v31_2_2.py` + `verify_v31_2_3.py` + `verify_v31_2_5_restart.py`
3. **sed 同步 32 处 cross-ref**: `docs/CHANGELOG-history-2026-07-23.md` (4640 行 ±) + `docs/CLAUDE-history.md` (24 行)
4. **P2-2 跳过 147 `docs/*.md` load-bearing 引用** (派工 brief 175 transient → 实测 161, 据实上报)
- 26 文件改动 + 2332 行 ±, 0 production code 守恒

### §2.5 W83 D-1 + D-2 文档同步 + 锚点收口

- **D-1 commit `adea403a4`**: 6 类文档同步 (CLAUDE.md + ROADMAP.md + CHANGELOG.md + README.md + memory/MEMORY.md) + W83 第 1 批 grand closure memory (`memory/w83-1st-grand-closure-full-2026-07-28.md` 193 行) + D-1 runbook (`docs/w83-1st-batch-d1-grand-closure-2026-07-28.md` 152 行) + 5 e2e PASS, 锚点 0 验证不计 + 实施 +1 实战
- **D-2 commit `9d607a924`**: 锚点范式 300 → 307 +7 守恒收口 + W84/W85/W86 派工顺序 + 5 新铁律 (锚点范式收口独立 commit, 主拍执行)

## §3 W84 第 1 批 7 agents 详细化 (从 §1 + §2 派生)

### §3.1 7 agents 派工清单 (派工 v6 §6 + W83 D-2 §4 排期调整)

| # | 任务 | 起点 → 终点 | 锚点 | 详细任务 |
|---|---|---|---|---|
| **A-1** | 部署收口 (主指挥协调, 沿用 W81 A-1 拦截 + W82/W83 merge 流程, W83 6 收尾 branches 合并入 main + push 实战) | 307 → 307 | 0 | 0 commit (沿用 W82 D-2 拦截 + W83 D-2 拦截模式) |
| **A-2 (本批)** | W83 7 agents 实战沉淀 + 据实上报 3 实例派生 + W84 7 agents 详细化 + W85/W86/W87 派工顺序 | 307 → 310 | +3 | 调研派生 (本任务) |
| **B-1** | P1 latent bug 修 batch 3 (8 项: drive_event_publisher + chat_history partial flag_modified + notification_service + drive_chunked_upload retry + llm docstring + audit_service + dedup fallback + audio.py print) | 310 → 311 | +1 | 8 项 P1 latent bug 详细化 (沿用 W83 B-1 4 项 + 派工 brief 8 项, 0 production code 1 例外已批) |
| **B-2** | P1 冗余重构 batch 2 (chunked upload 3+ 套合并 + useFileComments 桌面/移动收敛) | 311 → 312 | +1 | 2 项 P1 重构 (0 production code 1 例外已批, 分步走 沿用 W82/W83 B-2 拦截铁律) |
| **C-1** | P1 dead service 清 batch 2 (drive_upload_service 修 P0 create_initial_version 调用注入 + drive_comments_path_backfill 296 行收敛) | 312 → 313 | +1 | 2 项 P1 dead service (0 production code) |
| **C-2** | P2 docs/memory 清 batch 2 (14 transient memory 合并 + MEMORY.md 索引同步 + 175 永久保留部分重整) | 313 → 314 | +1 | 3 项 P2 清 (0 production code, 沿用 W83 C-2 据实上报铁律) |
| **D-1** | 6 类文档同步 + grand closure memory (CLAUDE.md + ROADMAP.md + CHANGELOG.md + README.md + memory/MEMORY.md + 1 runbook + 1 memory + 5 e2e PASS) | 314 → 314 验证不计 + 1 实战 | 0 + 1 | 6 类同步 + grand closure (沿用 W82/W83 D-1 模式) |
| **D-2** | 锚点范式收口 (W84/W85/W86 派工顺序 + 类 20.13 沉淀回写) | 314 收口 | 0 | 锚点范式收口 (主拍执行, 沿用 W83 D-2 模式) |

**累计**: 锚点范式 W83 307 → W84 314 (+7 守恒, 0 regression), 7/7 agents 计划完成, 0 production code 5/7 守恒 (2 例外已批 W84 B-1 + B-2).

### §3.2 8 项 P1 latent bug 详细化 (W84 B-1 派生, 沿用 W83 B-1 4 项模式)

> **派工 v6 §1.2 "Status 段必真验证"**: 8 项 P1 latent bug 派工 brief 必含实测 import 调用图 + 修复方案 + 0 production code 守恒预测. **类 20.13 实战 18 沉淀** (派工 brief 数字必须实测, 沿用 W82 B-2 #16 + W83 C-1 #17).

| # | 路径 | 风险 | 实测基础 | 修复方案 |
|---|------|------|----------|----------|
| 1 | `app/services/drive_event_publisher.py:282` `should_send` DB 异常传播 | 中 (silent fail) | caller `drive_reactions.py:164` except 吞掉 | 加 `logger.error` + fallback 默认发送 |
| 2 | `app/services/chat_history_service.py:885-925` `mark_message_partial` | 中 (缺 commit + flag_modified) | 用 `db.get(ChatMessage)` 但未 commit, 缺 `flag_modified` (沿用 CLAUDE.md 2026-06-28 教训) | 加 commit + `flag_modified(msg, "is_partial")` |
| 3 | `app/services/notification_service.py` 多处静默 except | 高 (977 行文件) | grep `except Exception: pass` 多处 | 替换为 `logger.error(exc_info=True)` (沿用 CLAUDE.md 派工前提铁律) |
| 4 | `app/services/drive_chunked_upload_service.py` `_stream_concat_chunks` retry 缺 | 中 (裸 `put_object` 缺 retry) | 沿用 `app/services/drive_service.py:260` `drive_retry` 装饰器 | 加 `drive_retry` 装饰器 |
| 5 | `app/core/llm.py:263` docstring print 残留 | 低 (误导未来开发者) | docstring 含 print 示例 | 改用 `logger.debug` 示例 |
| 6 | `app/services/audit_service.py` 鉴权回归监视 | 高 (鉴权相关) | 沿用 W82 B-1 类比 | 重读 + 加 admin 鉴权 guard |
| 7 | `app/services/drive_notification_dedup_service.py` fallback 监控 | 中 (41 行文件, 缺 fallback) | 缺 dedupe 失败 fallback 监控 | 加 fallback + 监控指标 |
| 8 | `app/utils/audio.py` + `app/voice/recorder.py` + `app/voice/segmenter.py` 多处 print | 低 (沿用 W83 B-1 wechat 实战) | grep `print(` 多处 | 替换为 `logger.info` |

**累计 8 项 P1 latent bug**, 沿用 W83 B-1 4 项派工 brief 模式 (commit `752cd3821` 总 713 insertions + 34 deletions + 4 e2e 测试 PASS).

### §3.3 2 项 P1 冗余重构 batch 2 详细化 (W84 B-2 派生, 分步走)

> **派工 v6 §1.2 真验证**: 派工 brief 必含 2 项**实测 import 调用图** + **分步走** (Step 1 仅建兼容层 + 改 import, Step 2 删老) — 沿用 W82/W83 B-2 拦截铁律 + W83 B-2 commit `79a9000ec` 实战模式.

| # | 重构 | 现状 | 目标 | 分步走 |
|---|------|------|------|--------|
| 1 | chunked upload 3+ 套合并 | `web/src/composables/useChunkedUploader.js` (195 行) + `web/src/composables/useDriveChunkedUpload.js` (282 行) + `web/src/composables/useMobileUploadQueue.ts` (664 行) + `web/src/composables/useResumableUpload.js` (118 行) | 合并为 2 套 (通用 chunked uploader + drive 专用) | Step 1 仅建 `useChunkedUploaderCore.js` + 改 import 兼容 → Step 2 删老 `useChunkedUploader.js` + `useMobileUploadQueue.ts` |
| 2 | useFileComments 桌面/移动收敛 | `web/src/composables/useFileComments.ts` (272 行, 通用) + `web/src/composables/useFileCommentsDesktop.ts` (254 行, 桌面 + UI 适配) + `web/src/composables/useFileCommentsMobile.ts` (待 grep 验证) | 合并桌面 + 移动 useFileComments, UI 适配差异提取到 view 层 | Step 1 仅建 `useFileCommentsCore.ts` + 改 import 兼容 → Step 2 删老 `useFileComments.ts` + `useFileCommentsDesktop.ts` |

**累计 2 项 P1 冗余重构**, 沿用 W83 B-2 commit `79a9000ec` 实战模式 (TTS cache + useViewport 兼容层, 9 文件 + 804 insertions + 431 deletions + 1 e2e PASS).

### §3.4 2 项 P1 dead service 详细化 (W84 C-1 派生)

| # | service | 行数 | 实测 live caller | 处置 |
|---|---------|------|------------------|------|
| 1 | `app/services/drive_upload_service.py` `create_initial_version` 调用注入 | (待 grep W84 C-1) | 0 调用 (但 docstring 提到调用) | **修 P0 create_initial_version 调用注入**: 在 `app/services/drive_service.py` `create_file` / `complete_chunked_upload` 后注入 3 处调用, 影响 `drive_file_versions` 表永远空, PR9 版本历史失效 (主拍签字, 历史文件无 version 记录, alembic 数据回填可选) |
| 2 | `app/services/drive_comments_path_backfill_service.py` 296 行收敛 | 296 | `services/drive_comments_path_backfill_tasks.py:72` + `tests/test_drive_v2_pr14_path_backfill.py:103` | **收敛**: 简化入口, 不删 (有 caller, W83 A-2 据实上报派生) |

**累计 2 项 P1 dead service**, 沿用 W83 C-1 commit `06183a408` 实战模式 (-923 行净, 0 production code, 据实上报拦截).

### §3.5 3 项 P2 docs/memory 清 batch 2 详细化 (W84 C-2 派生)

| # | 清理项 | 范围 | 实测基础 |
|---|--------|------|----------|
| 1 | 14 transient memory 合并 | `memory/w*-route-*.md` + `memory/w*-prompt-*.md` 按 batch 汇总到 grand closure memory, 删细目 | W83 C-2 据实上报: 14 真孤儿未在 `docs/*.md` 出现 (派工 brief 175 → 实测 161 → 14 真可合并) |
| 2 | MEMORY.md 索引同步 | W84 第 1 批 grand closure 条目新增 (锚点 314) | 沿用 W82 D-1 / W83 D-1 5 段同步实战 |
| 3 | 175 永久保留部分重整 | `memory/` 175 永久保留 memory 重整 (按 batch 分类, 删冗余) | 沿用 W67 第 52 步 34 memory 归档实战 |

**累计 3 项 P2 清**, 沿用 W83 C-2 commit `006789f54` 实战模式 (26 文件 + 2332 行 ±, 0 production code, 据实上报拦截).

## §4 W85/W86/W87 派工顺序 (派工 v6 §6 + W83 D-2 §4 排期调整)

### §4.1 W85 第 1 批 (W84 第 1 批 314 → ~321, +7 守恒, 单批 7 agents)

- **A-1**: 部署收口 (W84 第 1 批 6 收尾 + push 实战)
- **A-2**: W84 7 agents 实战沉淀派生 + W85 排期调整
- **B-1**: P1 latent bug 修 batch 4 收官 (剩余 4 项: drive_chunked_upload retry + llm docstring + audit_service 鉴权 + audio.py print, 沿用 W84 B-1)
- **B-2**: P1 冗余重构 batch 3 (useFileComments 桌面/移动收敛收官 + useTask 桌面/移动收敛, 沿用 W84 B-2)
- **C-1**: P1 dead service 清 batch 3 (drive_upload_service 修 P0 create_initial_version 数据回填, 沿用 W84 C-1)
- **C-2**: P2 docs/scripts 清 batch 3 (175 永久保留 memory 重整收官 + MEMORY.md 索引, 沿用 W84 C-2)
- **D-1..D-2**: grand closure + 锚点范式 314 → 321 收口

### §4.2 W86 (~321 → ~328, +7 守恒)

- **A-1**: 部署收口
- **A-2**: W85 实战沉淀派生 + W86 排期
- **B-1**: Phase 9 课题组知识图谱可视化 启动 (W78 A-2 24 人月 Q1 路线图阶段 5 后)
- **B-2**: 商业化运营收官 + 客户支持 (沿用 W81 B-1 实战)
- **C-1**: 跨租户监控 + 多租户实战收官 (沿用 W81 B-2 130/130 跨租户 PASS 守恒)
- **D-1..D-2**: grand closure + 锚点范式 321 → 328 收口

### §4.3 W87 (~328 → ~335, +7 守恒)

- **A-1**: 部署收口
- **A-2**: W86 实战沉淀派生 + W87 排期
- **B-1**: Phase 11 智能实验记录本 启动 (W78 A-2 24 人月 Q1 路线图阶段 6 后)
- **B-2**: 商业化运营 + 客户支持 + 监控实战 (沿用 W81 B-1/B-2 实战)
- **C-1**: Phase 12 科研协作工作流 启动 (W78 A-2 24 人月 Q1 路线图阶段 7 后)
- **D-1..D-2**: grand closure + 锚点范式 328 → 335 收口

## §5 派工前提铁律 12 + 类 20 累计 18 实例沉淀

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

### §5.2 类 20 实战 18 实例累计 (本批 #18 新增)

1-15 (沿用 W81): W72 B-4 / W73 D-1 / W74 A-1 / W74 B-1 / W75 A-1 / W76 A-1 / W76 类 20.12.1 B-2 / W77 A-1 / W78 A-1 / W78 B-1 / W79 A-1 / W80 A-1 / W80 C-1/D-1/D-2 / W81 A-1
16. **W82 B-2 类 20.13 实战 16**: 派工 brief 引用 Survey 3 "0 外部 import" 但实际 `tests/test_ios_safari_edge_tts_e2e.py:26-53` 模块顶层直接 import 4 ios_tts 文件
17. **W83 A-2 类 20.13 实战 17 (W83 A-2 派生)**: 派工 brief "P1 13 项 latent bug + P2 20+ 项 dead service" 与 W82 §6.2 实测 5 项 + W82 §5 W83 batch 2 4 项不一致; 任务 brief 中 9 dead service 实测全部有 live caller (0 行可删). **派生严格按 W82 实测, 不复制膨胀数字**
18. **W84 A-2 类 20.13 实战 18 (本批派生)**: 派工 brief W83 "P1 13 项 dead service + 175 transient memory" 与 W83 commit `06183a408` + `006789f54` 实测 5 项 + 161 vs 175 transient 不一致; W83 C-1 据实上报 5/7 错配 + W83 C-2 据实上报 P2-2 跳过 147 `docs/*.md` load-bearing 引用. **派生严格按 W83 commit hash 实测, 不复制膨胀数字**.

### §5.3 W83 5 收尾 agent 据实上报沉淀 (派工 v6 §1.2 真验证铁律)

#### §5.3.1 W83 A-2 据实上报 (类 20.13 实战 17)

- **派生实测**: 9 dead service 1935 行**全部有 live caller**, 0 行可删 (沿用 W82 B-2 拦截 #16 e2e 模块顶层 import 是 hidden 引用)
- **实际可执行仅 1 项**: `drive_comments_path_backfill_service.py` 296 行**收敛** (简化入口, 不删)
- **沉淀铁律**: 派生 dead service 任务必先 3 路 import 调用图实测 (W83 A-2 据实上报铁律)

#### §5.3.2 W83 C-1 据实上报 5/7 错配拦截 (commit `06183a408`)

- **派工 brief 5/7 错配拦截**:
  - P1-4 `tts_mainplay_pipeline`: 派工错配! W78 B-1 新链路 (commit `cb00397b7` 5 阶段整合平台), 多个 runbook 引用
  - P1-5 `bm25_service`: 派工错配! 3 production 文件调用 (graph_retriever + hybrid_retriever x2 + knowledge_service x2)
  - P1-6 `low_occupancy_filter`: 派工错配! `post_meeting_tasks.py:601` 实际调用
  - P1-7 `mention_parser`: 派工错配! 不是 1 行, 实际 189 行 2 函数 (parse_mentions + extract_snippet), 3 caller + 3 test 文件
  - 5/7 错配拦截, 实际真可删仅 2 service (377 行: payment + subscription) + 2 test (bm25 jieba 缺 + low_occupancy dead)
- **沉淀铁律**: 派工 brief 数字与实测不符必须据实上报, 不擅自扩也不擅自缩 (W82 C-1 据实上报 5 铁律 + W83 C-1 据实上报实战沉淀)

#### §5.3.3 W83 C-2 据实上报 P2-2 跳过 147 load-bearing 引用 (commit `006789f54`)

- **派工 brief 175 transient vs 实测 161**: 175 - 14 = 161 实测可合并 transient memory
- **实测 147 是 `docs/*.md` load-bearing 引用** (CHANGELOG-history-2026-07-23.md + CLAUDE-history.md), 跳过不合并
- **实际真可合并 14 transient memory**, 19 docs 迁 `docs/history/dispatch/` + 5 verify scripts 迁 `scripts/_archive/2026-07-28-w83-p2-cleanup/`, 锚点 +1 守恒
- **沉淀铁律**: 派工 brief 数字必须实测, transient memory 派生必先 grep `docs/*.md` cross-ref (W83 C-2 据实上报铁律)

#### §5.3.4 W83 B-1 + B-2 派工 brief 实战 (commit `752cd3821` + `79a9000ec`)

- **W83 B-1**: 派工 brief 4 项 P1 latent bug 全部实战 (rate_limit + license + wechat + agentic_loop), 0 错配
- **W83 B-2**: 派工 brief 2 项 P1 重构全部实战 (TTS cache + useViewport), 0 错配
- **沉淀**: 派工 brief 数字与实测一致时, agent 直接执行不视为错配 (派工 v6 §1.2 "Status 段必真验证" 沿用)

#### §5.3.5 W83 D-1 + D-2 派工 brief 实战 (commit `adea403a4` + `9d607a924`)

- **W83 D-1**: 6 类文档同步 + grand closure memory 实战, 0 错配 (沿用 W82 D-1 commit `b0cb5c4cb` 同模式)
- **W83 D-2**: 锚点范式收口 + W84/W85/W86 派工顺序实战, 0 错配 (主拍执行)

## §6 累计 commits + 铁律 + W19 选项 A

- **累计 26 批 420+ commits** (含 W84 第 1 批 1 commit = docs/memory 范畴)
- **累计铁律 420+ 条** (W84 第 1 批 +5 派生铁律 + 沿用 W83 +15 铁律: A-2 据实上报 + C-1 据实上报 + C-2 据实上报 + B-1 实战 + B-2 实战)
- **W19 选项 A 维持**: 4 留未来 PR (Phase 8.5 / P3 dedup / P3 跨 tab / 7 E2E)

## §7 W84 第 1 批 风险评估

### 高风险

- **B-1 audit_service 鉴权回归监视**: 鉴权相关, 主拍签字, 需回归 e2e
- **B-2 chunked upload 3+ 套合并涉及 4 个 composable + 大量 caller**, 分步走 (W82/W83 B-2 拦截铁律)
- **C-1 drive_upload `create_initial_version` 注入涉及 alembic 数据回填**, 主拍签字

### 中风险

- **B-1 drive_event_publisher 异常传播可能引入新 silent fail**, 必回归 `test_drive_notification_trigger.py`
- **B-1 notification_service 多处静默 except 涉及 977 行文件**, 必逐处测试
- **B-2 useFileComments 桌面/移动收敛**: 沿用 W83 B-2 实战, 改 import 兼容 + 删老分步走

### 低风险

- **B-1 audio.py print → logger 替换**: 沿用 W83 B-1 wechat 实战
- **C-1 drive_comments_path_backfill 收敛** (1 处用, 影响小)
- **C-2 docs/memory 范畴, 0 production code** (沿用 W83 C-2 实战)
- **A-1/A-2/D-1/D-2 纯 docs/memory** (沿用 W72-W83 例外清单)

## §8 文档 + memory 沉淀 (本批交付)

### §8.1 本批 2 文件

- `docs/w84-1st-batch-a2-survey-derivative-2026-07-28.md` (本文档, 预计 400-500 行)
- `memory/w84-1st-batch-a2-survey-derivative-2026-07-28.md` (精简 100 行)

### §8.2 MEMORY.md 索引更新 (W84 D-1 必做)

- W84 第 1 批 A-2 派生任务 (锚点 307 → 310 +3 守恒) 索引新增
- W84 第 1 批 grand closure 索引 (W84 grand closure 收口后) 新增
- 累计 26 批 (W7-W84 第 1 批) 锚点范式守恒预期

### §8.3 6 类文档同步 (W84 D-1 必做)

- 主仓库 5 文件: CLAUDE.md + ROADMAP.md + CHANGELOG.md + README.md + memory/MEMORY.md
- 用户级 1 文件: `C:\Users\pc\.claude\projects\E--microbubble-agent\memory\MEMORY.md`
- 1 新增 memory: `memory/w84-1st-batch-a2-survey-derivative-2026-07-28.md` (本批)
- 1 新增 docs: `docs/w84-1st-batch-a2-survey-derivative-2026-07-28.md` (本批)

### §8.4 git 提交 (本批 1 commit)

```bash
git add docs/w84-1st-batch-a2-survey-derivative-2026-07-28.md memory/w84-1st-batch-a2-survey-derivative-2026-07-28.md
git commit -m "chore(w84-a2): W83 据实上报 3 实例派生 W84 7 agents 详细化 + W85/W86/W87 派工顺序 (锚点范式 307 → 310 +3, 0 production code)"
git push origin chore/w84-1st-batch-a2-survey-derivative-2026-07-28
```

## §9 派工前提真验证 (派工前提铁律 12 + 类 20 实战 18 实例 + 派工 v6 段 7 19 类)

### §9.1 工作目录真验证

```bash
$ cd E:/microbubble-agent/.claude/worktrees/agent-w84-a2-survey-derivative
$ pwd
/e/microbubble-agent/.claude/worktrees/agent-w84-a2-survey-derivative

$ git log --oneline -5
aad2e8d7e merge: docs/w83-1st-batch-d2-anchor-closure (锚点范式 300 → 307 +7 守恒收口 + W84/W85/W86 派工顺序 + 5 新铁律, 0 production code)
b334cb0d7 merge: chore/w83-1st-batch-d1-docs-grand-closure (W83 第 1 批 6 类文档同步 + grand closure memory, 锚点范式 307 → 307 验证不计 + 实施 +1 实战, 0 production code)
2406aca85 merge: chore/w83-1st-batch-c2-p2-docs-cleanup (19 docs 迁 history/dispatch + 5 verify scripts archive + 据实上报 P2-2 transient 偏差, 锚点 306 → 307 +1 守恒, 0 production code)
4fe694093 merge: chore/w83-1st-batch-c1-p1-dead-service (P1 dead service 清 2 真 0 调用 service, 锚点 305 → 306 +1 守恒, 0 production code, 据实上报派工 brief 5/7 错配)
79ec9472c merge: refactor/w83-1st-batch-b2-p1-redundant-refactor (TTS cache 合并 + useViewport 兼容层, 锚点 304 → 305 +1 守恒, 0 production code 例外 1 已批)

$ git status
On branch chore/w84-1st-batch-a2-survey-derivative-2026-07-28
nothing to commit, working tree clean
```

### §9.2 base HEAD 真验证

- base HEAD = `aad2e8d7e` (worktree 自报) → 实测 `aad2e8d7e` ✓
- 锚点范式 307 守恒 ✓ (W83 D-2 anchor closure commit `aad2e8d7e` 已沉淀 307)
- 0 production code 改动铁律 (仅 docs/ + memory/ 新增) ✓
- W83 7 agents 实战沉淀真验证 ✓ (commit hash 实测: `37c9e2f32` A-2 + `752cd3821` B-1 + `79a9000ec` B-2 + `06183a408` C-1 + `006789f54` C-2 + `adea403a4` D-1 + `9d607a924` D-2)

### §9.3 W83 7 agents 实战沉淀真验证 (本批 A-2 来源)

- **W83 A-2 commit `37c9e2f32`**: W82 5 份 Survey 派生 W83 7 agents 详细化, 锚点 300 → 303 +3, 0 production code ✓
- **W83 B-1 commit `752cd3821`**: rate_limit + license + wechat logger + agentic_loop 静默 except, 锚点 +1, 例外 1 ✓
- **W83 B-2 commit `79a9000ec`**: TTS cache 合并 + useViewport 兼容层, 锚点 +1, 例外 1 ✓
- **W83 C-1 commit `06183a408`**: 派工 brief 5/7 错配拦截, 真可删 2 service + 2 test, 锚点 +1, 0 production code ✓
- **W83 C-2 commit `006789f54`**: 19 docs + 5 verify scripts, P2-2 跳过 147 `docs/*.md` 引用, 锚点 +1, 0 production code ✓
- **W83 D-1 commit `adea403a4`**: 6 类文档同步 + grand closure memory, 锚点 0 验证不计 + 1 实战 ✓
- **W83 D-2 commit `9d607a924`**: 锚点范式收口 + W84/W85/W86 派工顺序, 0 commit ✓

### §9.4 W83 据实上报 3 实例真验证 (本批 §1 派生基础)

- **W83 A-2 据实上报 (类 20.13 实战 17)**: 9 dead service 实测全部有 live caller, 0 行可删, 仅 `drive_comments_path_backfill_service.py` 296 行可收敛 ✓
- **W83 C-1 据实上报 5/7 错配拦截**: 派工 brief 与实测不符, 据实上报拦截, 真可删仅 2 service (377 行) + 2 test, 锚点 +1 守恒 ✓
- **W83 C-2 据实上报 P2-2 跳过 147**: 派工 brief 175 vs 实测 161 transient, 147 是 `docs/*.md` load-bearing 引用, 实际真可合并 14 ✓

---

**维护者**: Agent 6 (W84 第 1 批 A-2)
**创建时间**: 2026-07-28
**锚点范式**: W83 307 → W84 第 1 批 A-2 310 守恒 (+3, 0 regression)
**派工范式**: 主指挥协调范式第 60 次派工
**调研 vs 生产**: 调研文档化, 0 production code 守恒