# W84 第 1 批 A-2: W83 据实上报派生 + 7 agents 详细化 (锚点范式 307 → 310 +3 守恒)

> 主指挥协调范式第 60 次派工. 主基调 "W83 7 agents 实战沉淀派生 W84 7 agents 详细化 + 据实上报 3 实例二次 grep 真验证 + W85/W86/W87 派工顺序". 0 production code. 锚点范式 W83 307 → W84 310 (+3 守恒, 0 regression).

## §1 W83 据实上报 3 实例沉淀 (派工前提真验证实战)

### §1.1 W83 A-2 据实上报 (类 20.13 实战 17)

- 派工 brief: 9 dead service 可删 (1935 行)
- 实测: 9 service 全部有 live caller, 0 行可删
- 仅 `drive_comments_path_backfill_service.py` 296 行可收敛 (简化入口, 不删)
- 沉淀铁律: 派生 dead service 任务必先 3 路 import 调用图实测

### §1.2 W83 C-1 据实上报 5/7 错配拦截 (commit `06183a408`)

- 派工 brief: 7 service 可删
- 实测: 5 service 有 caller (drive_upload + tts_mainplay + bm25 + low_occupancy + mention_parser), 2 真 0 调用 (payment + subscription)
- 真可删 2 service (377 行) + 2 test (bm25 jieba 缺 + low_occupancy dead, -907 行净)
- 沉淀铁律: 派工 brief 数字与实测不符必须据实上报, 不擅自扩也不擅自缩

### §1.3 W83 C-2 据实上报 P2-2 跳过 147 load-bearing 引用 (commit `006789f54`)

- 派工 brief: 175 transient memory 可合并
- 实测: 161 transient, 147 是 `docs/*.md` load-bearing 引用, 仅 14 真孤儿可合并
- 实际 19 docs 迁 `docs/history/dispatch/` + 5 verify scripts 迁 `scripts/_archive/2026-07-28-w83-p2-cleanup/`
- 沉淀铁律: 派工 brief 数字必须实测, transient memory 派生必先 grep `docs/*.md` cross-ref

## §2 W83 7 agents 实战沉淀

| agent | commit | 起点 → 终点 | 锚点 | 范围 |
|-------|--------|-------------|------|------|
| A-2 | `37c9e2f32` | 300 → 303 | +3 | W82 5 份 Survey 派生 W83 7 agents 详细化 |
| B-1 | `752cd3821` | 303 → 304 | +1 | rate_limit + license + wechat logger + agentic_loop 静默 except |
| B-2 | `79a9000ec` | 304 → 305 | +1 | TTS cache 合并 + useViewport 兼容层 |
| C-1 | `06183a408` | 305 → 306 | +1 | 据实上报 5/7 错配, 真可删 2 service + 2 test |
| C-2 | `006789f54` | 306 → 307 | +1 | 据实上报 14 transient, 19 docs + 5 verify scripts 迁 |
| D-1 | `adea403a4` | 307 → 307 | 0 + 1 | 6 类文档同步 + grand closure memory |
| D-2 | `9d607a924` | 307 收口 | 0 | 锚点范式收口 + W84/W85/W86 派工顺序 |

**累计**: W83 第 1 批 7 agents +7 守恒, 0 production code 5/7 守恒 (2 例外已批 W83 B-1 + B-2).

## §3 W84 第 1 批 7 agents 详细化 (从 §1 + §2 派生)

### §3.1 7 agents 派工清单

| # | 任务 | 起点 → 终点 | 锚点 | 详细 |
|---|---|---|---|---|
| A-1 | 部署收口 | 307 → 307 | 0 | W83 6 收尾 + push (主拍执行) |
| **A-2 (本批)** | W83 据实上报派生 | **307 → 310** | **+3** | **调研派生 (本任务)** |
| B-1 | P1 latent bug 修 batch 3 | 310 → 311 | +1 | 8 项: drive_event_publisher + chat_history partial + notification_service + drive_chunked_upload retry + llm docstring + audit_service + dedup fallback + audio.py print |
| B-2 | P1 冗余重构 batch 2 | 311 → 312 | +1 | chunked upload 3+ 套合并 + useFileComments 桌面/移动收敛 (分步走) |
| C-1 | P1 dead service 清 batch 2 | 312 → 313 | +1 | drive_upload `create_initial_version` 注入 + drive_comments_path_backfill 296 行收敛 |
| C-2 | P2 docs/memory 清 batch 2 | 313 → 314 | +1 | 14 transient memory 合并 + MEMORY.md 索引同步 + 175 永久保留部分重整 |
| D-1 | 6 类文档同步 + grand closure | 314 → 314 | 0 + 1 | 6 类同步 + grand closure memory (沿用 W82/W83 D-1 模式) |
| D-2 | 锚点范式收口 | 314 收口 | 0 | W85/W86/W87 派工顺序 + 类 20.13 沉淀回写 (主拍执行) |

**累计**: 锚点范式 W83 307 → W84 314 (+7 守恒, 0 regression), 7/7 agents 计划完成, 0 production code 5/7 守恒 (2 例外预留给 W84 B-1 + B-2).

### §3.2 8 项 P1 latent bug 详细化 (W84 B-1 派生)

1. `app/services/drive_event_publisher.py:282` `should_send` DB 异常传播 — 加 `logger.error` + fallback
2. `app/services/chat_history_service.py:885-925` `mark_message_partial` — 加 commit + `flag_modified(msg, "is_partial")`
3. `app/services/notification_service.py` 多处静默 except — 替换为 `logger.error(exc_info=True)`
4. `app/services/drive_chunked_upload_service.py` `_stream_concat_chunks` — 加 `drive_retry` 装饰器
5. `app/core/llm.py:263` docstring print 残留 — 改用 `logger.debug` 示例
6. `app/services/audit_service.py` 鉴权回归监视 — 重读 + 加 admin 鉴权 guard
7. `app/services/drive_notification_dedup_service.py` fallback 监控 — 加 fallback + 监控指标
8. `app/utils/audio.py` + `app/voice/recorder.py` + `app/voice/segmenter.py` 多处 print — 替换为 `logger.info`

### §3.3 2 项 P1 冗余重构 batch 2 详细化 (W84 B-2 分步走)

1. **chunked upload 3+ 套合并**: 4 composable (useChunkedUploader 195 + useDriveChunkedUpload 282 + useMobileUploadQueue 664 + useResumableUpload 118) → 2 套 (通用 + drive 专用). Step 1 兼容层 → Step 2 删老.
2. **useFileComments 桌面/移动收敛**: 3 composable (useFileComments 272 + useFileCommentsDesktop 254 + useFileCommentsMobile 待 grep) → 合并 + UI 适配差异提取到 view 层.

### §3.4 2 项 P1 dead service 详细化 (W84 C-1 派生)

1. **`drive_upload_service.py` `create_initial_version` 注入**: docstring 提到调用但 0 调用, 影响 `drive_file_versions` 表永远空, PR9 版本历史失效. 修: 在 `drive_service.py` `create_file` / `complete_chunked_upload` 后注入 3 处调用. 主拍签字, 数据回填可选.
2. **`drive_comments_path_backfill_service.py` 296 行收敛**: 简化入口, 不删 (有 caller).

### §3.5 3 项 P2 docs/memory 清 batch 2 详细化 (W84 C-2 派生)

1. 14 transient memory 合并 (按 batch 汇总到 grand closure memory, 删细目)
2. MEMORY.md 索引同步 (W84 第 1 批 grand closure 条目)
3. 175 永久保留部分重整 (按 batch 分类, 删冗余)

## §4 W85/W86/W87 派工顺序

### §4.1 W85 (W84 第 1 批 314 → ~321, +7 守恒, 单批 7 agents)

- A-1 部署收口
- A-2 W84 实战沉淀派生 + W85 排期调整
- B-1 P1 latent bug 修 batch 4 收官 (剩余 4 项: drive_chunked_upload retry + llm docstring + audit_service 鉴权 + audio.py print)
- B-2 P1 冗余重构 batch 3 (useFileComments 收官 + useTask 桌面/移动收敛)
- C-1 P1 dead service 清 batch 3 (drive_upload `create_initial_version` 数据回填)
- C-2 P2 docs/scripts 清 batch 3 (175 永久保留 memory 重整收官 + MEMORY.md 索引)
- D-1..D-2 grand closure + 锚点范式 314 → 321 收口

### §4.2 W86 (~321 → ~328, +7 守恒)

- A-1 部署收口
- B-1 Phase 9 课题组知识图谱可视化 启动 (W78 A-2 24 人月 Q1 路线图阶段 5 后)
- B-2 商业化运营收官 + 客户支持
- C-1 跨租户监控 + 多租户实战收官 (130/130 跨租户 PASS 守恒)
- D-1..D-2 grand closure + 锚点范式 321 → 328 收口

### §4.3 W87 (~328 → ~335, +7 守恒)

- A-1 部署收口
- B-1 Phase 11 智能实验记录本 启动
- B-2 商业化运营 + 客户支持 + 监控实战
- C-1 Phase 12 科研协作工作流 启动
- D-1..D-2 grand closure + 锚点范式 328 → 335 收口

## §5 派工前提铁律 12 + 类 20 累计 18 实例沉淀

### §5.1 类 20 实战 18 实例累计 (本批 #18 新增)

1-16 (沿用 W83): W72 B-4 / W73 D-1 / W74 A-1 / W74 B-1 / W75 A-1 / W76 A-1 / W76 类 20.12.1 B-2 / W77 A-1 / W78 A-1 / W78 B-1 / W79 A-1 / W80 A-1 / W80 C-1/D-1/D-2 / W81 A-1 / W82 B-2
17. **W83 A-2 类 20.13 实战 17**: 派工 brief "P1 13 项 latent bug + P2 20+ 项 dead service" 与 W82 §6.2 实测 5 项 + 9 dead service 全部有 live caller (0 行可删) 不一致
18. **W84 A-2 类 20.13 实战 18 (本批)**: 派工 brief W83 "P1 13 项 dead service + 175 transient memory" 与 W83 commit `06183a408` + `006789f54` 实测 5 项有 caller + 161 vs 175 transient 不一致; W83 C-1 据实上报 5/7 错配 + W83 C-2 据实上报 P2-2 跳过 147 `docs/*.md` load-bearing 引用. **派生严格按 W83 commit hash 实测**.

### §5.2 W83 5 收尾 agent 据实上报沉淀 (派工 v6 §1.2 真验证铁律)

- **A-2 据实上报**: 9 dead service 0 行可删, 仅 `drive_comments_path_backfill_service.py` 296 行可收敛
- **C-1 据实上报 5/7 错配拦截**: 派工 brief 5/7 错配 (tts_mainplay + bm25 + low_occupancy + mention_parser + drive_upload 已说不删), 真可删仅 2 service (377 行) + 2 test
- **C-2 据实上报 P2-2 跳过 147**: 派工 brief 175 vs 实测 161, 147 是 `docs/*.md` load-bearing 引用, 实际 14 真可合并
- **B-1 + B-2 派工 brief 实战**: 0 错配, 直接执行
- **D-1 + D-2 派工 brief 实战**: 0 错配, 沿用 W82 D-1 / W83 D-2 同模式

## §6 累计 commits + 铁律 + W19 选项 A

- **累计 26 批 420+ commits** (含 W84 第 1 批 1 commit = docs/memory 范畴)
- **累计铁律 420+ 条** (W84 第 1 批 +5 派生铁律 + 沿用 W83 +15 铁律)
- **W19 选项 A 维持**: 4 留未来 PR (Phase 8.5 / P3 dedup / P3 跨 tab / 7 E2E)

## §7 W84 第 1 批 风险评估

### 高风险
- B-1 audit_service 鉴权回归监视: 主拍签字, 需回归 e2e
- B-2 chunked upload 3+ 套合并涉及 4 个 composable + 大量 caller, 分步走
- C-1 drive_upload `create_initial_version` 注入涉及 alembic 数据回填, 主拍签字

### 中风险
- B-1 drive_event_publisher 异常传播可能引入新 silent fail
- B-1 notification_service 多处静默 except 涉及 977 行文件
- B-2 useFileComments 桌面/移动收敛

### 低风险
- B-1 audio.py print → logger (沿用 W83 B-1 wechat 实战)
- C-1 drive_comments_path_backfill 收敛 (1 处用)
- C-2 docs/memory 范畴, 0 production code
- A-1/A-2/D-1/D-2 纯 docs/memory

## §8 文档 + memory 沉淀 (本批交付)

- `docs/w84-1st-batch-a2-survey-derivative-2026-07-28.md` (本文档, 完整版)
- `memory/w84-1st-batch-a2-survey-derivative-2026-07-28.md` (本精简版)

**维护者**: Agent 6 (W84 第 1 批 A-2)
**创建时间**: 2026-07-28
**锚点范式**: W83 307 → W84 310 守恒 (+3, 0 regression)
**派工范式**: 主指挥协调范式第 60 次派工