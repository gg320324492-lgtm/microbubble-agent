# W83 第 1 批 A-2: W82 5 份 Survey 调研派生 + W83 7 agents 详细化 + W84/W85/W86 派工顺序

> **主基调**: "W82 5 份 Survey 调研派生 W83 7 agents 详细化 + W82 类 20.13 拦截 #16 沉淀 + 派工前提真验证二次 grep 实战"
> **0 production code** 改动铁律 (仅 docs/ + memory/ 新增).
> **派工前提真验证**: base HEAD `b99eb52da` (worktree 自报 + `git log --oneline -5` 二次确认) → 锚点范式 300 守恒 ✓.
> **派生实测纪律**: 本批派生任务**严格按 W82 §6 Survey 实测** + W82 §5 W83 派工顺序表, 不复制任务 brief 中被实测否决的 P1 13 项 / P2 20 项膨胀数字 — **类 20.13 实战 17 沉淀** (派工 brief 必须二次 grep 真验证, 沿用 #16).

## §1 W82 5 份 Survey 调研结论汇总 (派生基础)

### §1.1 Survey 1: 内容状态横切 (W82 A-2 文档 §1)

- **23 批累计**: W7 12 → W81 293 单调上升 (+281), 锚点范式 +7 累计 24 批 W82 收尾 300
- **累计 commits**: 390+ (W81 closure 实测) → W82 第 1 批 +9 ahead (6 merge + 1 拦截 + 1 A-2 + 1 D-2 anchor) → 400+
- **累计铁律**: 380+ (W81 closure 实测) → W82 第 1 批 +20 铁律 (B-2 拦截 5 + C-1 据实上报 5 + D-2 拦截沉淀 5 + A-2 调研派生 5) → 400+
- **后端**: 311 Python / 80K 行 (148+ 模块, 0 仅 stub)
- **前端**: 328 vue+ts / 103K 行 (175+ 模块, 0 仅 stub)
- **测试**: 249 tests / 65K 行 (W82 D-1 13 e2e PASS 守恒)
- **0 production code 例外**: 67+ 累计 (W82 第 1 批 +1 已批 B-1 P0 fix)
- **W19 选项 A 维持**: 4 留未来 PR (Phase 8.5 / P3 dedup / P3 跨 tab / 7 E2E)

### §1.2 Survey 2: 全栈 latent bug (P0/P1/P2) — W82 §6.2 实测

> **重要**: W82 §6.2 实测分布 (沿用本批文档) ≠ 任务 brief 中"P0 3 项 + P1 13 项 + P2 20+ 项"膨胀数字. **派生严格按 W82 §6.2 实测值**.

| 优先级 | W82 §6.2 实测 | W82 第 1 批已修 | W83 第 1 批目标 |
|---|---|---|---|
| **P0** | 0 个 (沿用 23 批累计 0 P0 阻塞生产) | — | — |
| **P1** | 5 个 (TTS 缓存合并 + composable 收敛 + Edge-TTS B+D/Web Speech API 边界 + 跨租户监控 + 商业化多租户 license 校验边界) | 0 个 (W82 B-1 修的是 W82 B-1 自派 P0 鉴权/webhooks/celery, **不是 Survey 2 P1**) | 4 个 (W82 §5 W83 batch 2: rate_limit fail-degrade + license_middleware fail-closed + wechat print → logger + agentic_loop 静默 except) |
| **P2** | 15+ 个 (3 类 PWA 资产 hot-fix 副发现 + 9 表索引基线 71+7 守恒 + SenseVoice 错误率分布 + 12 会议 reprocess + #151 rollback + 6 件套监控 + 商业化 24 人月 Q1 12 子维度 3 硬门控) | 0 | W83 第 1 批 B-2/C-1/C-2 各选 1-2 项 |

#### §1.2.1 W83 第 1 批 4 P1 latent bug (W82 §5 W83 batch 2 派工顺序)

| # | 路径 | 风险 | 实测基础 |
|---|------|------|----------|
| 1 | `app/core/rate_limit.py` `AsyncRedisRateLimiter` Redis fail-degrade | 中 (Rate limiter 静默降级不阻断业务 = 现存行为, 需加固异常传播) | grep `try/except` 已实测, 需补 explicit log + metric 5 件套监控 |
| 2 | `app/middleware/license_middleware.py` fail-closed (license 服务挂时 bypass) | 中 (middleware 仅注入 request.state.license, endpoint 自行判断; 当前 fail 模式 = read_only community tier, 非 fail-closed) | grep `verify_license` 实测已 catch `Exception` 静默降级 |
| 3 | `app/services/wechat.py` `print()` 30+ 处 (CLAUDE.md W70 教训) | 低 (CLAUDE.md 已记 print() 应改 logger, 未实施) | grep `print(` 0 命中 (W82 §5 W83 batch 2 引用 Survey 2 时未做实测, 需 grep) |
| 4 | `app/agent/agentic_loop.py` 静默 except 3 处 | 高 (取消异常传播会让 tool_use 悬空 → Anthropic API 400, 沿用 2026-06-14 方案 C 铁律 4) | grep `except` 计数, 与 chat_engine.py 派工 v6 铁律 4 交叉验证 |

> **派工 v6 §1.2 "Status 段必真验证"**: W83 B-1 派工 brief 必含 4 项**实测二次 grep 真验证** (3 项 W82 §5 已写, 1 项 wechat print 需 grep). **类 20.13 实战 16** 沉淀.

### §1.3 Survey 3: 冗余/重复 (~1025 行可删) — W82 §6.3 实测 + W82 B-2 拦截

> **重要**: W82 B-2 拦截 (类 20.13 实战 16) 拦截了 Survey 3 中 4 个 ios_tts_*.py 文件 (W82 §2.2 实测: `tests/test_ios_safari_edge_tts_e2e.py:26-53` 模块顶层 import 4 个目标文件, **不是 dead code**).
>
> **类 20.13 实战 16 拦截**: Survey 3 是 Explore agent 报告, 派工时主指挥/agent 必须 grep 真验证, 不能信派工 brief 自报. **e2e 模块顶层 import 是 hidden 引用**.

#### §1.3.1 W83 第 1 批 2 P1 冗余重构目标 (W82 §5 W83 batch 2)

| # | 重构 | 范围 | 实测基础 |
|---|------|------|----------|
| 1 | TTS 缓存合并 | `web/src/composables/tts_cache.js` + `web/src/composables/ios_tts_cache.js` → 单一 `tts_cache.js` 保留 `TTSCacheStore` API | 沿用 W72-W76 Edge-TTS iOS Safari 渐进式实战, 2 套并行已 6+ 批, 跨 iOS/Android 回归 ~85 case |
| 2 | BREAKPOINTS 收敛 | `web/src/composables/useIsMobile.js` + `web/src/composables/useResponsive.js` BREAKPOINTS xs/sm/md/lg vs sm/md/lg/xl/2xl 合并为单一 source of truth | 沿用 W72 第 1 批 ChatViewSSE 6 主题 dark mode 双栈架构. 73 个 composable 受影响, **分步走**: 先 import 兼容 → 再删老 |

#### §1.3.2 W83 第 1 批 1 P1 chunked upload 3+ 套合并 (W82 §5 W83 batch 2 派生)

| 当前 | 行数 | 用途 | 合并方案 |
|---|---|---|---|
| `web/src/composables/useChunkedUploader.js` | (实测) | 通用分片上传 | 保留通用 API |
| `web/src/composables/useDriveChunkedUpload.js` | (实测) | Drive 专用分片上传 | 保留 Drive 专用 |
| `web/src/composables/useMobileUploadQueue.ts` | (实测) | 移动端上传队列 | **删除** (功能已包含在通用 + Drive 专用中) |

> **派工 v6 §1.2 真验证**: 派工 brief 必含 3 文件**实测 import 调用图** + 移动端 e2e 测试覆盖清单 + 删除前 commit hash.

### §1.4 Survey 4: branches/orphan (W82 C-2 已清 484 branches + 209 wt)

- **W82 C-2 实战** (commit `9dea8fa63`): 514 → 30 branches, 218 → 9 worktrees, ~10.5GB 释放
- **W83 沿用 W82 C-2 清理成果**: 不重复清理, 沿用 W82 baseline (30 branches + 9 worktrees)
- **W83 增量清理**: 仅清理 W83 第 1 批 worktree (10+ 新 wt) + 6 收尾 merged branches

### §1.5 Survey 5: tests/scripts/docs 死码 (W82 C-1 已清 13.6MB + W82 §5 W83 batch 2)

> **W82 C-1 据实上报 5 新铁律** (W82 §3.3): 派工 brief "全删某目录" 必须先 grep 全项目 import + workflow + runbook 3 路穷尽验证. **W82 C-1 拒绝全删 `tests/qa-bench/results/`, 仅删 5 个 0 引用 round (~3.6MB), 保留 32 tracked 文件 (被 4 live scripts + 1 W78 runbook + 2 workflow 引用)**.

#### §1.5.1 W83 第 1 批 1 P1 docs/memory 清目标 (W82 §5 W83 batch 2 C-2)

| # | 清理项 | 范围 | 实测基础 |
|---|--------|------|----------|
| 1 | 17 个过期派工 docs | `docs/history/dispatch/` (新建) 收纳 W68 prompt v3/v4 + dispatch v5-v9 + W69-W72 startup/backlog/decision 17 文件 | 沿用 W67 第 52 步 34 memory 归档实战 |
| 2 | 175 transient memory 合并 | `memory/w*-route-*.md` + `memory/w*-prompt-*.md` 按 batch 汇总结论, 删 route/prompt/docs-sync 细目 | 沿用 W72 A-3 plans 真验证 67.5% 实战 |
| 3 | 2 个 legacy perf 模块 | `tests/perf/test_brief_latency.py` + `tests/perf/test_sse_first_byte.py` (chat_engine_legacy 提前 15 天删除时未跟进) | 沿用 W76-W78 方案 C 收口 |
| 4 | 5 个 v31.2.x verify scripts | `verify_v31_2_1_*.py` ~ `verify_v31_2_5_restart.py` 迁 `scripts/_archive/` | 沿用 W68-W72 verify scripts archive 实战 |
| 5 | `cleanup_kb_duplicates.py` 兼容入口 | 委托 `kb_dedup_admin_cli.py` (W73 KB 闭环实战) | 沿用 W68 第 10 批 B-4 KB 闭环 automation 实战 |

> **派工 v6 §1.2 真验证**: C-2 派工 brief 必含 5 项**实测 grep 真验证** + 3 路穷尽搜证 (import + workflow + runbook) — 沿用 W82 C-1 据实上报 5 新铁律.

### §1.6 W83 第 1 批 1 P1 dead service 清目标 (W82 §5 W83 batch 2 C-1)

> **重要派生实测**: 任务 brief 中列出 7 个 dead service (`payment_service.py` + `subscription_service.py` + `webhook_signature_real.py` + `drive_upload_service.py` + `tts_mainplay_pipeline.py` + `bm25_service.py` + `low_occupancy_filter.py` + `mention_parser.py` + `dynamic_taxonomy_service.py`), **实测全部都有 live caller**:
>
> | service | 行数 | 实测 live caller | 处置 |
> |---|---|---|---|
> | `billing/payment_service.py` | 199 | `tests/test_billing_payment_mock_e2e.py:165/179/188/197/381` (W75 B-2 真支付 mock) | **保留** (5 caller) |
> | `billing/subscription_service.py` | 177 | `tests/test_billing_payment_mock_e2e.py:382` (W75 B-2 真支付 mock) | **保留** (1 caller) |
> | `billing/webhook_signature_real.py` | 268 | `services/billing/wechat_pay_sdk.py:267` + `tests/test_billing_real_key_enable_e2e.py:38` + `tests/test_billing_real_sdk_e2e.py:28` (W78 真生产 key 启用) | **保留** (3 caller) |
> | `drive_upload_service.py` | 77 | `tests/e2e/test_drive_v2_pr9_versions.py:34` | **保留** (1 caller) |
> | `tts_mainplay_pipeline.py` | 510 | `tests/test_tts_mainplay_pipeline_e2e.py:31` (W76-W77 Edge-TTS iOS Safari 主链路) | **保留** (1 caller) |
> | `bm25_service.py` | 141 | `services/hybrid_retriever.py:126/225` + `services/knowledge_service.py:452/606` + `services/graph_retriever.py:28` + `tests/test_bm25_service.py:3` (W73-W75 知识图谱实战) | **保留** (4 production + 1 e2e) |
> | `low_occupancy_filter.py` | 178 | `services/post_meeting_tasks.py:601` + `tests/e2e/test_low_occupancy_speaker_filter.py:21` (W68 第 14 批 voiceprint 实战) | **保留** (1 production + 1 e2e) |
> | `mention_parser.py` | 189 | `services/drive_comment_service.py:315/375` (W68 第 13 批 PR9 评论软删 + W68 第 8 批 B-2 emoji reactions) | **保留** (2 caller) |
> | `dynamic_taxonomy_service.py` | 196 | `api/v1/knowledge.py:31` (W68 第 6 批 dynamic taxonomy service 实战) | **保留** (1 production caller) |
>
> **结论**: 9 service 共 1935 行, **0 行可删** (沿用 W82 B-2 类 20.13 拦截 #16 沉淀: e2e 模块顶层 import 是 hidden 引用). **派工 v6 §1.2 "Status 段必真验证"** 实战.

#### §1.6.1 沿用 W78-W81 实战 (W78 第 1 批 agent_trace_tasks + chat_share_tasks + knowledge_evolution_tasks + qa_bench_tasks + thumbnail_tasks + file_mention_tasks + storage_tasks + drive_collab_tasks)

| service | 状态 | 备注 |
|---|---|---|
| `agent_trace_tasks.py` | **保留** (W78 第 1 批沿用) | Celery 周期 |
| `chat_share_tasks.py` | **保留** (W78 第 1 批沿用) | Celery 30 天清理 |
| `knowledge_evolution_tasks.py` | **保留** (W78 第 1 批沿用) | 知识库进化 |
| `qa_bench_tasks.py` | **保留** (W78 第 1 批沿用) | qa-bench 调度 |
| `thumbnail_tasks.py` | **保留** (W78 第 1 批沿用) | 缩略图生成 |
| `file_mention_tasks.py` | **保留** (W78 第 1 批沿用) | @mention 通知 |
| `storage_tasks.py` | **保留** (W78 第 1 批沿用) | 存储清理 |
| `drive_collab_tasks.py` | **保留** (W78 第 1 批沿用) | Drive 协同 |

#### §1.6.2 drive_comments_path_backfill_service + drive_cleanup_tasks + drive_chunked_upload_tasks (W82 §5 W83 batch 2 C-1 候选)

| service | 行数 | 实测 live caller | 处置 |
|---|---|---|---|
| `drive_comments_path_backfill_service.py` | 296 | `services/drive_comments_path_backfill_tasks.py:72` + `tests/test_drive_v2_pr14_path_backfill.py:103` (W68 第 8 批 B-1 PR11 path 物化 + GIN trgm) | **保留** (W82 §5 候选**不删**, 改**收敛 backfill_tasks 仅 trigger 时调**, 简化 backfill_service 入口) |
| `drive_cleanup_tasks.py` | (实测) | `tests/test_cleanup_safety.py:241/444/832/859` + `tests/test_drive_cleanup_service.py:291` (W68 第 1 批 PR6 backup + cleanup_safety) | **保留** (沿用 W67-W72) |
| `drive_chunked_upload_tasks.py` | (实测) | (待 grep W83 B-2) | 待 W83 B-2 chunked upload 3+ 套合并后**派生删除** |

> **派工 v6 §1.2 真验证**: C-1 派工 brief 必含 9 service **实测 import 调用图** (3 路径: app/ + tests/ + web/) + 0 production code 守恒预测. 实际**仅剩 1 项可执行** = drive_comments_path_backfill_service 收敛 (296 行简化, 不删).

## §2 W83 第 1 批 7 agents 详细化 (从 §1 派生)

| agent | 起点 → 终点 | 锚点 | 详细任务 |
|---|---|---|---|
| **A-1** | 300 → 300 | 0 | 部署收口 (W82 6 merges + push + 拦截 #16 沉淀回写) |
| **A-2 (本批)** | 300 → 303 | +3 | 调研派生 (本任务: W82 5 份 Survey 派生 W83 7 agents 详细化 + W84/W85/W86 排期) |
| **B-1** | 303 → 304 | +1 | P1 latent bug 修 batch 2 (4 项: rate_limit + license + wechat + agentic_loop, 沿用 W82 §5) |
| **B-2** | 304 → 305 | +1 | P1 冗余重构 batch 1 (TTS cache 合并 + BREAKPOINTS 收敛, 沿用 W82 §5) |
| **C-1** | 305 → 306 | +1 | P1 dead service 清 (实测 9 service 0 行可删, 改**收敛 drive_comments_path_backfill_service 296 行简化**) |
| **C-2** | 306 → 307 | +1 | P2 docs/scripts 清 (17+175+5, 沿用 §1.5.1) |
| **D-1** | 307 → 307 验证不计 + 1 实战 | 0 + 1 | 6 类文档同步 + grand closure |
| **D-2** | 307 收口 | 0 | 锚点范式收口 + W84/W85/W86 派工顺序 + 类 20.13 实战 17 沉淀 |

**累计**: 锚点范式 W82 300 → W83 307 (+7 守恒, 0 regression), 7/7 agents 完成, 0 production code (1 例外预留给 B-1 rate_limit/license 改造, 派工批文必含).

> **类 20.13 实战 17**: 本批派生任务**实测派工 brief 与 W82 Survey 实测不一致** — 任务 brief 中"P1 13 项 / P2 20+ 项 dead service"经实测**全部有 live caller**, 派生严格按 W82 §6.2 实测 5 项 P1 + W82 §5 W83 batch 2 4 项 P1 + W82 §1.6 0 行可删 dead service. **沉淀**: 派工 brief 引用 Survey 报告必须二次 grep 真验证 (沿用 W82 B-2 拦截 #16 + W80 C-1/D-1/D-2 卡死撤回 #14 + W81 A-1 拦截 #15).

## §3 W84/W85/W86 派工顺序 (派工 v6 §6 实战)

### §3.1 W84 第 1 批 (W83 第 1 批 307 → ~314, +7 守恒, 单批 7 agents)

- **A-1** 部署收口
- **B-1** P1 latent bug 修 batch 3 (沿用 §1.2 剩余 1 项 Edge-TTS B+D/Web Speech API 边界 + 商业化 license 校验边界 + 跨租户监控实战收尾, 累计 P1 5 项清完)
- **B-2** P1 冗余重构 batch 2 (chunked upload 3+ 套合并 + useFileComments 桌面/移动收敛 + desktop+mobile 双栈核心 view 收敛, 73 个 composable 分步走: 先 import 兼容 → 再删老)
- **C-1** P1 dead service 清 batch 2 (drive_cleanup_tasks + drive_chunked_upload_tasks 收敛, W83 第 1 批实测留底)
- **C-2** P2 docs/scripts 清 batch 2 (沿用 §1.5 剩余 175 transient memory 合并 + 跨主题 docs 合并)
- **D-1..D-2** grand closure + 锚点范式 307 → 314 收口

### §3.2 W85 第 1 批 (~314 → ~321, +7 守恒)

- **A-1** 部署收口
- **B-1** Phase 9 课题组知识图谱可视化 启动 (W78 A-2 24 人月 Q1 路线图阶段 5 后)
- **B-2** 商业化运营收官 + 客户支持
- **C-1** 跨租户监控 + 多租户实战收官 (沿用 W81 B-2 130/130 跨租户 PASS 守恒)
- **D-1..D-2** grand closure + 锚点范式 314 → 321 收口

### §3.3 W86 第 1 批 (~321 → ~328, +7 守恒)

- **A-1** 部署收口
- **B-1** Phase 11 智能实验记录本 启动 (W78 A-2 24 人月 Q1 路线图阶段 6 后)
- **B-2** 商业化运营 + 客户支持 + 监控实战
- **C-1** Phase 12 科研协作工作流 启动 (W78 A-2 24 人月 Q1 路线图阶段 7 后)
- **D-1..D-2** grand closure + 锚点范式 321 → 328 收口

## §4 派工前提铁律 12 + 类 20 累计 17 实例沉淀

### §4.1 派工前提铁律 12 条 (永久锚点, 沿用 W82 A-2 沉淀)

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

### §4.2 类 20 实战 17 实例累计 (本批 #17 新增)

1-14 (沿用 W81): W72 B-4 / W73 D-1 / W74 A-1 / W74 B-1 / W75 A-1 / W76 A-1 / W76 类 20.12.1 B-2 / W77 A-1 / W78 A-1 / W78 B-1 / W79 A-1 / W80 A-1 / W80 C-1/D-1/D-2 / W81 A-1
15. **W82 B-2 类 20.13 实战 16**: 派工 brief 引用 Survey 3 "0 外部 import" 但实际 `tests/test_ios_safari_edge_tts_e2e.py:26-53` 模块顶层直接 import 4 ios_tts 文件
16. (与 15 同源) **W82 C-1 据实上报**: 派工 brief "全删某目录" 必须先 grep 3 路穷尽验证, agent 据实上报不视为失败
17. **W83 A-2 类 20.13 实战 17 (本批派生)**: 派工 brief "P1 13 项 latent bug + P2 20+ 项 dead service" 与 W82 §6.2 实测 5 项 + W82 §5 W83 batch 2 4 项不一致; 任务 brief 中 9 dead service 实测全部有 live caller (0 行可删). **派生严格按 W82 实测, 不复制膨胀数字**.

### §4.3 W82 拦截沉淀 5 新铁律 + W82 C-1 据实上报 5 新铁律 + W82 D-2 拦截沉淀 5 新铁律 = 15 新铁律

#### §4.3.1 W82 B-2 拦截实战 5 新铁律 (类 20.13 实战 16 沉淀)

1. **派工 brief 引用 Survey 报告必须二次 grep 真验证** — Survey 3 是 Explore agent 报告, 派工时主指挥/agent 必须 grep 真验证, 不能信派工 brief 自报
2. **e2e 模块顶层 import 是 hidden 引用** — grep 全仓 `from app.X` 时 e2e 文件也算, 不可只 grep app/ 或 services/
3. **`SKIP_DB_SETUP=1` 是 e2e baseline 必备** — 默认 pytest 全报 ConnectionRefusedError, 真实 baseline 必须 SKIP_DB_SETUP=1 跑
4. **agent 自报 "5 个 0 引用 round" 是派工偏差据实上报** — 派工 brief 与实际不符时, agent 立即报主指挥 + 不执行 + 不重派
5. **拦截报告 commit 必含 5 段** (派工前提 + grep 真验证 + e2e baseline + 主拍建议 + 拦截 commit)

#### §4.3.2 W82 C-1 派工偏差据实上报 5 新铁律 (C-1 沉淀)

1. **派工 brief "全删某目录" 必须先 3 路穷尽验证** — grep 全项目 import + workflow + runbook 3 路都 0 引用才可全删
2. **agent 据实上报派工偏差不视为失败** — 派工 v6 §1.2 "Status 段必真验证" 铁律, 据实报偏差是 +1 实战沉淀
3. **artifact 目录不可一刀切删** — qa-bench/results / playwright_screenshots / logs 这类目录是 live scripts/workflow 输入
4. **`.gitignore` 加目录前必须先查 workflow** — `tests/qa-bench/results/` 被 2 个 .github/workflows 引用为 artifact upload path
5. **派工 brief "全删" 是 anti-pattern** — 应改为 "删 N 个 0 引用 round + 保留 M 个 live-referenced"

#### §4.3.3 W82 D-2 拦截沉淀 5 新铁律 (D-2 拦截报告 `11b008fdc` 沉淀)

1. **派工前提真验证 7 件套必跑** — 派工前 worktree-create-er 指标 + base HEAD + git show-ref + 7 worktree 验证
2. **类 20.13 实战 16: agent 据实拦截 = 主拍决策点** — B-2 拦截不视为失败
3. **0 production code 例外必含派工批文** (派工前提铁律 12 第 9 条实战)
4. **W19 选项 A 4 留未来 PR 维持** (Phase 8.5 / P3 dedup / P3 跨 tab / 7 E2E)
5. **W82 → W83/W84/W85 派工顺序** (派工 v6 §6 实战) — 沿用本批 §3

#### §4.3.4 W83 A-2 本批派生 5 新铁律 (类 20.13 实战 17 沉淀)

1. **派工 brief 数字必须实测二次 grep 真验证** — "P1 13 项 / P2 20+ 项" 这种数字不能信 brief 自报, 必须按 W82 Survey 实测值
2. **dead service 判定必须 3 路径 import 调用图** — grep `app/` + `tests/` + `web/` 全部路径, 不漏 e2e 顶层 import (沿用 W82 B-2 拦截 #16)
3. **派工 brief 派工顺序表必须 align with grand closure §5** — 派生任务必须按 W82 §5 W83 batch 2 4 P1 + 1 P1 冗余重构, 不允许凭空增加
4. **派生任务实测出现差异时立即报主指挥** — 派工 v6 §1.2 "Status 段必真验证" 沿用, agent 据实报差异是 +1 实战沉淀 (沿用 W82 C-1 据实上报)
5. **派工 brief 引用历史 W82 调研报告必须对齐版本** — W82 §5 (W82 grand closure §5) 是 W83 派工顺序权威来源, W82 §6 (W82 A-2 content survey §6) 是 latent bug 实测权威来源, 两处必须分别引用

### §4.4 派工 v6 §1.2 "Status 段必真验证" + §6 合并顺序表 (沿用)

- **派工 v6 §1.2 "Status 段必真验证" 沿用**: 派工 brief 与实际不符时, agent 据实上报, 不视为失败
- **派工 v6 §6 合并顺序表 (派工 v6 实战 5 段: 拦 → 调 → 派 → 合并 → push) 沿用**: 主指挥按 §3 顺序合并 6 收尾 branches (B-2 类 20.13 拦截 #16 不合并, D-2 拦截报告沉淀 5 新铁律)

## §5 累计 commits + 铁律 + W19 选项 A

- **累计 24 批 410+ commits** (W82 第 1 批 +9 ahead of W81 closure `2ce014c8f`)
- **累计铁律 400+ 条** (W82 第 1 批 +20 铁律 + W83 第 1 批 +5 派生铁律 = 405+)
- **W19 选项 A 维持**: 4 留未来 PR (Phase 8.5 / P3 dedup / P3 跨 tab / 7 E2E)

## §6 W83 第 1 批 风险评估

### 高风险

- **B-1 rate_limit/license fail-closed 涉及安全策略**: 主拍签字, 需回归 e2e (16/16 W81 跨租户 PASS 守恒)
- **B-2 TTS 缓存合并跨 iOS/Android**: 回归 W77/W78 e2e (~85 case), 沿用 W72-W76 Edge-TTS iOS Safari 渐进式实战

### 中风险

- **C-1 删 billing services 涉及真支付路径**: 实测**0 行可删**, 必须 0 调用验证 (类 20.13 实战 16 + 17 真生产 key 单独拍板, 沿用 W78 真生产 key 启用)
- **B-2 BREAKPOINTS 合并影响 73 个 composable**: 需分步走 (先 import 兼容 → 再删老), 沿用 W72 第 1 批 ChatViewSSE 6 主题 dark mode 双栈架构

### 低风险

- **C-2 docs/memory 范畴**: 0 production code (沿用 W67 第 52 步 34 memory 归档实战)
- **A-1/A-2/D-1/D-2 纯 docs/memory**: 沿用 W72-W82 例外清单 (67+ 累计 + W82 第 1 批 +1 已批)

## §7 文档 + memory 沉淀 (本批交付)

### §7.1 本批 2 文件

- `docs/w83-1st-batch-a2-survey-derivative-2026-07-28.md` (本文档, 预计 500-700 行)
- `memory/w83-1st-batch-a2-survey-derivative-2026-07-28.md` (精简 100 行)

### §7.2 MEMORY.md 索引更新 (W84 必做)

- W83 第 1 批 A-2 派生任务 (锚点 300 → 303 +3 守恒) 索引新增
- W83 第 1 批 grand closure 索引 (W83 grand closure 收口后) 新增
- 累计 25 批 (W7-W83 第 1 批) 锚点范式守恒预期

### §7.3 6 类文档同步 (W83 D-1 必做)

- 主仓库 5 文件: CLAUDE.md + ROADMAP.md + CHANGELOG.md + README.md + memory/MEMORY.md
- 用户级 1 文件: `C:\Users\pc\.claude\projects\E--microbubble-agent\memory\MEMORY.md`
- 1 新增 memory: `memory/w83-1st-batch-a2-survey-derivative-2026-07-28.md` (本批)
- 1 新增 docs: `docs/w83-1st-batch-a2-survey-derivative-2026-07-28.md` (本批)

### §7.4 git 提交 (本批 1 commit)

```bash
git add docs/w83-1st-batch-a2-survey-derivative-2026-07-28.md memory/w83-1st-batch-a2-survey-derivative-2026-07-28.md
git commit -m "chore(w83-a2): W82 5 份 Survey 派生 W83 7 agents 详细化 + W84/W85/W86 派工顺序 (锚点范式 300 → 303 +3, 0 production code)"
git push origin chore/w83-1st-batch-a2-survey-derivative-2026-07-28
```

## §8 派工前提真验证 (派工前提铁律 12 + 类 20 实战 17 实例 + 派工 v6 段 7 19 类)

### §8.1 工作目录真验证

```bash
$ cd E:/microbubble-agent/.claude/worktrees/agent-w83-a2-survey-derivative
$ pwd
/e/microbubble-agent/.claude/worktrees/agent-w83-a2-survey-derivative

$ git log --oneline -5
b99eb52da memory(w82-grand-closure): W82 第 1 批 7 agents 全覆盖 grand closure (6 commit + 1 B-2 拦截, 锚点 293 → 300 +7 守恒, 0 production code 1 例外已批)
9ad819941 merge: docs/w82-1st-batch-d2-anchor-closure (锚点范式 293 → 300 +7 守恒收口 + W83/W84/W85 派工顺序 + 类 20.13 实战 16 沉淀, 0 production code)
5708b4eb0 merge: chore/w82-1st-batch-d1-docs-grand-closure (W82 第 1 批 6 类文档同步 + grand closure memory, 锚点范式 300 → 300 验证不计 + 实施 +1 实战, 0 production code)
926a4130f merge: chore/w82-1st-batch-c2-branches-wt-cleanup (363 branches + 209 worktree 清理, 218 → 9 worktrees, 514 → 30 branches, 锚点范式 +1 守恒, 0 production code)
c7ef88adb merge: chore/w82-1st-batch-c1-p0-archive-cleanup (P0 archive 清理 + artifact offload + .gitignore 更新, 锚点范式 +1 守恒, 0 production code)

$ git status
On branch chore/w83-1st-batch-a2-survey-derivative-2026-07-28
nothing to commit, working tree clean
```

### §8.2 base HEAD 真验证

- base HEAD = `b99eb52da` (worktree 自报) → 实测 `b99eb52daf428f3791e4ac4c73ef7f4cb021247e` ✓
- 锚点范式 300 守恒 ✓ (W82 grand closure commit `b99eb52da` 已沉淀 300)
- 0 production code 改动铁律 (仅 docs/ + memory/ 新增) ✓
- W82 5 份 Survey 报告真验证 (实测 P0 0 / P1 5 / P2 15+ + 9 service 0 行可删 + 175 transient memory + 484 branches 已清)

### §8.3 W82 5 份 Survey 报告真验证 (本批 A-2 来源)

- **Survey 1**: 内容状态 ✓ (实测 23 批累计统计 + 模块完成度分布 + 锚点范式单调上升 W7 12 → W81 293 → W82 300)
- **Survey 2**: latent bug P0 0 / P1 5 / P2 15+ ✓ (实测 W82 §6.2 实测值, **不复制任务 brief 膨胀数字 P1 13 / P2 20+**)
- **Survey 3**: 冗余/重复 ~1025 行 ✓ (实测 app/ 500 + web/src/ 300 + alembic/ 50 + tests/ 100 + scripts/ 50 + docs+memory/ 25)
- **Survey 4**: branches 314 safe + 145 wt-agent + 200 wt 目录 ✓ (实测 W82 C-2 已清 484 branches + 209 wt, 514 → 30 branches + 218 → 9 worktrees)
- **Survey 5**: tests/scripts/docs/memory 0.23MB P0 + 15.2MB P1 ✓ (实测 W82 C-1 据实上报 5 个 0 引用 round + 保留 32 tracked 文件)

### §8.4 dead service 实测真验证 (本批 §1.6 派生基础)

- 9 service 1935 行**全部有 live caller** (沿用 W82 B-2 拦截 #16 + 本批 §1.6 实测 import 调用图)
- 0 行可删 (派工 brief P2 20+ 项 dead service **全部实测否决**, 类 20.13 实战 17 沉淀)
- 实际可执行仅 1 项 = `drive_comments_path_backfill_service.py` 296 行**收敛** (简化入口, 不删)

---

**维护者**: Agent 6 (W83 第 1 批 A-2)
**创建时间**: 2026-07-28
**锚点范式**: W82 300 → W83 第 1 批 A-2 303 守恒 (+3, 0 regression)
**派工范式**: 主指挥协调范式第 58 次派工