# MicroBubble Agent - 路线图

> **本文件是项目未来规划 + 近期完成的高层摘要。**
> 详细 commit 流水账在 [HISTORY.md](HISTORY.md)（已存档 5730 行），权威变更日志在 [CHANGELOG.md](CHANGELOG.md)。

## 当前状态（2026-07-01 早班收官）

**已交付（2026-07-01 早班新增）**：
- 🆕 **post_meeting_tasks 简化（commit `4b215220`）** — 124 行 → 26 行 (-98, -79%)，移除下划线前缀临时变量 (`_n_expected`/`_labels`/`_optimal_k`) → 直接命名 + 同步重命名 `cluster_centers`/`cluster_representatives` + 修复 UnboundLocalError 闭包 lazy 求值隐患
- 🆕 **v78 tabs 集成 spec + 临时启用 desktop-chrome（commit `6b6a91f4`）** — `web/tests/visual/desktop/templates-tab-integration-2026-06-30.spec.mjs` (116 行) 端到端验证 `/meetings` 2 tabs 集成（会议列表 / 模板管理）+ 批量操作 toolbar + 编辑按钮真实打开 MeetingTemplateDialog；`web/playwright.config.js` 临时启用 desktop-chrome project
- 🆕 **`scripts/generate_token_plan_doc.py` 项目状况报告 Word 生成（commit `763244ae`）** — 1195 行一次性脚本（不入 CI），依赖 python-docx，产物 `docs/MicroBubble_Agent_开发状况报告_2026-06-30.docx` (71KB)
- 🆕 **移除 dedup toggle UI + displayedItems 永远 default-on（commit `425e5799`）** — 用户决策"dedup 是产品应该自动做的事，不应让用户在 UI 上控制开关"。删 `el-switch` + `dedupEnabled` prop + `toggle-dedup` emit + `dedupView` ref + `DEDUP_STORAGE_KEY` 常量 + `watch(localStorage)` 同步（22 行）；`displayedItems` computed 永远按 title 分组取 id 最小
- 🆕 **chore: qa-bench v3 W3-W6 数据集 + ASR benchmark 入库 + .gitignore 兜底 admin token（commit `6573f2b3`）** — 8 个 GitHub Actions dump 删除 + `tests/qa-bench/_login.json` + `_token.txt` **admin JWT 凭据泄露风险修复** + `results/asr_benchmark_2026-06-30/` (105KB) + `tests/qa-bench/results/` (292KB) 提交 + `.gitignore` 加 `_login.json` / `_token.txt` / `*.json` 兜底规则

**统计（2026-07-01 自动重算）**：**1588 commits / 196K 行源代码（去除 dist/models/data） / 1202 git tracked 文件 / 47 开发天数**

---

## 历史状态（2026-06-30 晚班收官）

**已交付（晚班新增）**：
- 🆕 **v78 UI redesign — 3-zone 对话窗口 + EP icons + 4-attr a11y（commit `34e82fd9`）** — SessionSidebar overlap 修复（`flex min-width:0`）+ 右键/long-press 上下文菜单 + sortedSessions 置顶冒泡 + NavRail.vue + ChatViewSSE 3-zone 重构（`≡` / `ChatBreadcrumb` / `+FAB`）+ ThinkingModeSwitch segmented（替代 🧠/🧠 双 toggle 冲突）+ 移动端 EP icons 同步 + variables.css `--icon-size-*` token；8 条新铁律
- 🆕 **#009 Self-RAG 重检索 + 用户深度思考开关（4 commits `740ac4c1` + `a49bd644` + 后续 hook 收尾）** — Phase 0.5 双重 hook（Haiku judge 800ms + refined_query）+ **3-tier 阈值分档**（高≥0.8 直接出 / 中高≥0.6 不重 / 中≥0.4+can_answer 不重 / 低<0.4 触发重检索）+ 前端 useUiStore useDeepThinking + 7 个 AGENT_SELF_RAG_* flag + `agentic_loop.py:615-665` 实施；8 条新铁律
- 🆕 **qa-bench v3.0 6 周冲刺完整收官（W1-W6 6 阶段交付）**：
  - **W1 基建**（commit `d5b6e6c5`） — 700 题题库（业务 500 + P 高级 100 + K 横切 100）+ 3 个 P0 检测器（stream_interrupt / tool_error_propagated / first_token_latency）+ 7 维评分
  - **W2 题库生产** — 229 手工 + 107 DB + 144 模板 + 15 expert = **535 题合并去重**
  - **W3 跑测 + 维度报告** — 端到端 SSE 跑测发现 Self-RAG 回归 bug（`MicroBubbleAgent.chat_stream` 缺 model 参数）+ intent 标签重生成 + 14 业务域 × 6 intent × 4 难度矩阵
  - **W4 高级能力专项** — P 高级 102 题（Self-RAG 21 + fan-out 21 + plan_step 15 + 持久化 15 + abort 15 + grounding 15）+ 3-tier 阈值分档实施
  - **W5 KB 入库 + 回归 + 稳定性** — `save_to_kb.py` 5 道防线（分数≥4 / 内容≥200字 / 意图白名单 / 灰度 `--enable-intake` / 备份+7天rollback）+ 200 题 smoke 套件 + 回归基线 v3.0 锁定
  - **W6 D5 KB 入库监控** + 7 维雷达图 + ROI 100-150% + 8 项决策清单
  - **关键文件**：`tests/qa-bench/{runner.py, gen780.py, questions_*.jsonl, dashboard/}` + `scripts/{auto_intake_rollback.py, gen_advanced_report.py, gen_final_report.py, gen_dim_report.py, aggregate_metrics.py, lock_baseline.py, stability_check.py}` + `.github/workflows/qa-bench-smoke.yml` (CI 200 题 5min 80% 阈值)
- 🆕 **Whisper → SenseVoice 迁移收官（commit `9effb8ed`）** — 5 维度实测对比 SenseVoice 全胜：VRAM 0.93 vs 8.0 GB (-88%) / RTF 0.01-0.09 vs 0.08-0.25 (3-25x) / 中文 CER 15.6 vs 25.7% (改善 39%) / 20 min 会议覆盖 500 vs 105 字 (4.7x) / 中文标点 + ITN 原生支持；chunked 推理 (60s + `cache={}`) 防 20 min 长会议 OOM (peak 25.77 GB → 安全)；torch 2.7+cu128 支持 RTX 5090 sm_120；内联 `strip_all_tags` 避免跨容器 import
- 🆕 **KB 数据清洁：B 物理删 + C 前端 dedup toggle（commit `cfd486b6`）** — `scripts/migrate_kb_dedup_titles.py` ~560 行 + 19 单测全 PASS + 5 类 FK 防御（`knowledge_relations` CASCADE + `images` CASCADE + `extractions` CASCADE + `gaps` ARRAY `&&` + `rag_evaluations.context` ILIKE 数字边界）+ JSON 备份 `backups/kb-dedup-20260630/`（28936 字节，1 条待恢复）+ 前端 dedup toggle 默认 ON（`mnb:kb:dedupView`，仅影响"📋 最近知识"显示策略，不动 stats 计数）；8 条新铁律
- 🆕 **KB 卡片 source_type 重分类（commit `9964f7e4`）** — 180 张 `[拓展-XX]` 卡片从 NULL → `'auto_expansion'`（chip 显示 0 → 180）+ 踩坑：SQLAlchemy `regexp_match` 转义陷阱（11 条误伤）→ 改用 `Knowledge.title.startswith("[拓展")` (SQL 层 `LIKE 'X%'`)
- 🆕 **KB 入库监控 D5（commits `ee442125` + `9ea0f87d`）** — 后端 `GET /api/v1/knowledge/auto-intake-summary`（today_intake + weekly_intake[7] + hit_rate + negative_feedback_rate + rollback_count + total_in_db=179）+ 前端 `web/src/composables/useKbMonitor.js`（polling 5min Q5 setInterval）+ `web/src/views/ProjectStatsView.vue` 第 3 个 tab（4 metric card + 7 日趋势 CSS 柱状图 + 系统状态卡）+ empty placeholder + today 高亮（防误导）
- 🆕 **声纹循环净化 4 会议累计收官** — #083 杜同贺 86.7%→100%（P0 防护 `sil_floor` + `cluster_centers` 合并 + `strict` 策略）+ #135 错标诊断 + **#151 王天志 90% 识别率硬门禁 rollback** + **#167 段 15-18 修正 + 低占比发言人过滤规则（1.5s/3s/5%）**；9 条铁律 + 4 个 memory 沉淀
- 🆕 **KB "5 个统计全 0" 修复 4 commits 收官（`7ee94f8e` + `765c3dd6` + `74c58e06` + `7b4df117`）** — filter 残留重置 + SW 缓存空 items 拒绝 + 三态空态（loading/error/empty）+ sub-entity total 主动 fetch + stats GROUP BY 显式补 0 + fetchCategories shape dict vs list 适配 + MemberView 排序博X系列；6 条新铁律
- 🆕 **KB 数据清洁 — 自动生成 tags 归并 + 测试样板删除（commit `037f4aa1` + `aff75dce`）** — `scripts/migrate_kb_tags.py` 303 行 + 16 单测 + scope 双模式（`auto_expansion` 默认 / `notes_category` 笔记 admin 手动测试卡）+ 防御性 WHERE `source_type='auto_expansion'` 隔离真实用户（不误伤 `"NTA测试方法"` / `"DLS动态光散射测试"` 真实术语）+ 三段式（scan → 人审 → apply + `--confirm`）+ JSON 备份 12 字段 + 真实用户 0 改动
- 🆕 **文档 + 报告批量沉淀**：
  - **新增 12 个 memory**（含 v78 / self-rag / qa-bench-v3 w1-w6 / kb-monitor / low-occupancy / asr-migration）
  - **新增 4 个文档**：`docs/asr-alternatives.md` + `docs/asr-benchmark-2026-06-30.md` + `docs/MicroBubble_Agent_开发狀況報告_2026-06-30.docx` + `memory/asr-benchmark-2026-06-30.md`

---

## 历史状态（2026-06-30 早班）
- 🆕 **前端视觉 5 件套 + 视觉收官延伸（11 commits 收尾 2026-06-30）**：
  - **KnowledgeToolbar 4 按钮**（commit `558962b1`）—— `.btn-text` utility class 同名冲突修复
  - **MemberView 录入声纹 ghost primary**（commit 845803c3）—— `variables.css` 加 default + `[data-accent]` 双块规则 + `font-weight:600`
  - **VoiceprintView 波形颜色不一致**（commit 36e64fb4）—— 老成员 stale embedding |value|≈0 alpha≈0 不可见，`barColor()` per-card max 归一化 + min alpha floor 0.12
  - **SettingsView Hero 跟随主题**（commit `054668f7`）—— non-scoped `[data-theme=dark].hero-bg` 硬编码 hex 永远赢 scoped 变量
  - **VoiceprintEnrollFlow mobile icon + 5 处 transition token + webhint devDep**（commit `e3b32b86`）—— 全项目扫描 38 个非 scoped style 块 + 1 mobile inline style 全部干净
- 🆕 **nginx HSTS server-level + gzip_types 扩展（3 commits 真实安全加固）**：
  - commit `71e743f7` — HSTS server-block + gzip_types 扩展 (agent + mnb-lab)
  - commit `289338fb` — 4 个 location 补 HSTS（/favicon.ico / /sw.js / /manifest.webmanifest / static regex）
  - commit `34128fbd` — agent `/` location HSTS 升级 includeSubDomains 对齐
  - **效果**：`strict-transport-security 12→0 errors/route`（9 路由全过），`gzip_types` 9 → 15 MIME（含 `font/woff2` / `application/wasm` 等）
- 🆕 **Knowledge 卡 `analysis_status` 真 bug 修复（commit `3653890b`）**：
  - Step 7 `_reset_multimodal_data` 无条件覆盖终态 → 加 `reset_status=False` 参数（区分 pipeline vs manual UI）
  - `_run_analyze_and_embed` 末尾加 Step 8 最终终态防御
  - `KnowledgeCard.vue` 加 `partial` 状态 tag
  - **DB 清理**：2 张 5 月预存 stuck 卡（KB #14 #19）验证 content 完整后 UPDATE → done
  - **全表状态**：199 done / 1 completed (legacy) / **0 analyzing** / 0 pending
- 🆕 **v77 P2.6-G.2 meeting-template batch + bar color enum class**：
  - `d01420dd` refactor(voiceprint): 收敛 VoiceprintCard bar 颜色到 .bar--low/mid/high class
  - `8c14a0c8` / `95e53955` / `31acafcb` / `d5521a70` meeting-template batch/list endpoint + 11 个 service 单测
  - `0c96331f` admin 桌面端 el-table + MeetingView query.tab
- 🆕 **v77 P2.6-F.2 MeetingView 1088 → 359 行拆分（5 commits）**：
  - **v77 P2.6-F.2 Step 4**（commit `e5ba60e2`）— 听会 UX 全屏化（800px 弹窗 → `/meetings/room` 全屏 MeetingRoomView，与移动端对齐）+ style 拆到独立 `web/src/views/meeting/meeting-view.css`（498 行）
  - **v77 P2.6-F.2 Step 3**（commit `a3663d04`）— 抽 `MeetingTemplateDialog` 子组件（MeetingView -125 行, 新组件 180 行 + 12 Vitest 单测覆盖 TDZ 防御）
  - **v77 P2.6-F.2 Step 2**（commit `f2eb8cfc`）— 抽 `MeetingMinutesDialog` 子组件（MeetingView -21 行, 新组件 86 行 + 7 Vitest 单测）
  - **v77 P2.6-F.2 Step 1**（commit `298ed5c5`）— MeetingView 死代码清理（未用 imports/refs/functions -60 行）
- 🆕 **v77 P2.6-E/F 视觉/代码质量延伸（4 commits）**：
  - **v77 P2.6-F.1**（commit `e362ad8e`）— transition: all 0.Xs token 化（27 处 / 17 文件 → `var(--transition-all-*)`）+ scripts/replace-transition-all-literals.js Node.js 脚本
  - **v77 P2.6-E.3**（commit `c06482b5`）— KnowledgeView 1599 → 501 行拆分（抽 4 tab + 1 dialog 5 个新组件，entityChartInstance 生命周期从父移到子避免内存泄漏）
  - **v77 P2.6-E.2**（commit `dcd1657b`）— 缓动字面量 token 化（70 处 → `var(--ease-*)` + `--ease-out` 升级 Material Decelerate + `--ease-quad` 新增 + scripts/replace-easing-literals.js Node.js 脚本）
  - **v77 P2.6-E.1**（commit `ed5e5e16`）— CSS-in-JS 收官（8 处 runtime `:style` → 7 个枚举 class，scss 55→105 行）
- 🆕 **v77 P2.6 视觉体系 4 子任务全面收官**（7 commits：A/B/C/D 阶段）：
  - **v77 P2.6-D**（4 commits `19f42924` + `2096d3e0` + `fe896004` + `b251fc22`）— PWA Service Worker 强化（Background Sync 4 写场景 + Navigation Preload + Local Notification）+ 动效治理（6 处重复 keyframes 清理 + 12 --animation-* + 3 --ease-*）+ CSS-in-JS 收敛（3 处 avatar color → .avatar-color-N 枚举 class）+ Baseline 扩到 9 路由（+projects /+members /+project-stats）
  - **v77 P2.6-C**（commit `db3a31e1`）— EP 多主题透传补全（143 条规则）+ Mobile baseline 6 路由 + 登录态双注入修复
  - **v77 P2.6-B**（commit `8905003a`）— Bug 修复（PaperHeader plain 按钮 dark bug）+ 移动端 14 view + 6 组件 + 1 Block dark 化 + Desktop Baseline 6 路由
  - **v77 P2.6-A**（commit `36049629`）— paper 14 组件 + 桌面 5 view + ChartBlock token dark 全面化（移动端 9/15 → 15/15 + Rich Block 11/11 dark 化收官）
- 🆕 **3 个生产 bug 修复** — pgvector embedding truth value bug + SQLAlchemy JSONB flag_modified + AudioPlayer Infinity:NaN（详见 [memory/embedding-truth-value-bug-2026-06-28.md](memory/embedding-truth-value-bug-2026-06-28.md) + [memory/sqlalchemy-jsonb-flag-modified-2026-06-28.md](memory/sqlalchemy-jsonb-flag-modified-2026-06-28.md) + [memory/audio-player-infinity-duration-2026-06-28.md](memory/audio-player-infinity-duration-2026-06-28.md)）
- 🆕 **会议 153 ASR 谐音/错识全链路清洗 hook** — `name_aliases` 扩容 7 条会议 153 真实误识 + `post_meeting_tasks` hook 推到主路径，所有未来会议自动清洗（[memory/name-aliases-phonetic-correction-2026-06-27.md](memory/name-aliases-phonetic-correction-2026-06-27.md)）
- ✅ v1-v6 完整后端架构（Python 3.11 + FastAPI + SQLAlchemy + PostgreSQL + Redis + Celery + MinIO）
- ✅ v2/v3/v4 Agent 架构（34 个 `@tool` 装饰器工具 + 12 类 Rich Block + 多会话并行 + agent_traces 可观测性）
- ✅ 知识库 V1 + V2（动态 LLM 分析 + 知识图谱 + RAG 问答 + 自主研究引擎 + 公式分类 + 假设生成）
- ✅ 知识库 V3（多模态 OCR：图片 + 公式 + 表格 + 图表识别入库，10/10 PDF 端到端通过）
- ✅ 会议系统 v1-v4（录音机 + 离线后处理 + ASR + 声纹 + AI 摘要 + 三级润色 + **v70~v73 视觉迭代 + v77 P2.6 dark 化**）
- ✅ 声纹识别 v2（3D-Speaker + pgvector + HNSW 索引 + **修复 ERes2Net batch bug** 100% 段有效）
- ✅ 会议发言人重处理流程（[reprocess_meeting.py](scripts/reprocess_meeting.py) 9 步 CLI + 主机端 wrapper）
- ✅ 移动端 PWA 收官（18 个移动端页面 + 12 个移动端组件 + 路由级双栈 + 4 个 PWA 离线策略）
- ✅ v2 任务提醒体系（11AM 窗口 + acknowledged 状态 + Redis 24h 去重）
- ✅ **v28 智能论文阅读器**（8 phases + step 109.x 打磨：4 篇 PDF 37 张图 100% 核心不变量 + 12 列结构化字段 + 内嵌图 confidence 阈值 + IO Hysteresis 防跳变）
- ✅ **v29 Qwen3 全量迁移**（GPU 启用 + Qwen3 wrapper + 双模型 dispatch + alembic 030 + 知识库 350/351 条重算 + 列原子切换）
- ✅ **sentence-transformers 5.6.0 升级**（跨 3 大版本，0 breaking，删 170 行 wrapper，Qwen3 max_seq_length 4x → 32K，qa-bench 38%→42%）
- ✅ **v31 检索质量监控埋点**（3 endpoint + 5 指标 dashboard + per-user 维度 + qa-bench 360 题）
- ✅ **v31.2.x rate-limit 基建收尾**（XFF 空 IP 兜底 + analytics regex + user_id 维度 + X-RateLimit-Policy 头 + SSE tier + Redis ZSET 持久化）
- ✅ **v31.3 Whisper 常驻 GPU 8GB + bind mount**（聊天 ASR 时效性优先，源码 bind mount 免 `docker cp`）
- ✅ **v68 桌面主题切换 + SettingsView 玻璃态**
- ✅ **v69 P0+P1 dark mode 全面重构**（3 阶段：基础 5 token + 14 EP 覆盖；6 套主题切换；10 桌面视图 dark 适配）
- ✅ **v70 P0~P3 字面色 token 化 + 会议纪要 TL;DR + Stylelint 字面色禁用**
- ✅ **v71 P1 议程 timeline + 每 speaker 8 条常驻**
- ✅ **v72 P1 摘要+重点摘要合并主题色卡**
- ✅ **v74/v75/v76 测试基建**（CSS variable 6 主题组合自动化 + 9 个旧 fail 修复 + 视觉回归 5 件套）
- ✅ **pre-commit hook auto-add web/dist/**（CLAUDE.md 教训第 4 次沉淀后兜底）

**统计**（[app/stats.json](app/stats.json), 2026-06-30 自动重算）：
- **1545 commits / 313K 行代码 / 799 文件 / 46 开发天数**（[app/stats.json](app/stats.json)，2026-06-30 01:12 自动重算）
- 9 个 Docker 服务运行中
- 87 后端 + 73 前端 + 17 移动端 + 8 ST 集成 + 11 visual-regression = 196+ 测试
- 知识库 64→247+ → 350+ 条（Qwen3 重算后，alembic 030 双列原子切换 text2vec 768d → Qwen3-Embedding-0.6B 1024d）
- **2026-06-24~28 起 20+ 铁律沉淀**（清华源/ONNX 反优化/docker build 污染/pre-commit hook/dist 漏 commit/Stylelint/PowerShell BOM/Background Sync/playwright dev server/token 渐进收敛/v-model 子组件 props 禁用/word-boundary 正则 等，详见 [CLAUDE.md](CLAUDE.md) 末尾）

**最新里程碑**：
- 🆕 [v77 P2.6-E/F 视觉/代码质量延伸（4 commits）](CHANGELOG.md#2026-06-28-v77-p26-ef-视觉代码质量延伸-4-commits) - CSS-in-JS 收官 + 缓动 token 化 + KnowledgeView 拆分 + transition: all token 化
- 🆕 [v77 P2.6 视觉体系 4 子任务全面收官（A/B/C/D）](CHANGELOG.md#2026-06-28-v77-p26-视觉体系-4-子任务全面收官abc-d-共-7-commits) - 7 commits + 143 条 dark 规则 + 18 张 baseline
- 🆕 [3 个生产 bug 修复](CHANGELOG.md#2026-06-28-3-个生产-bug-修复会议-64-报-500--audioplayer-infinitynan) - pgvector truth value + SQLAlchemy JSONB + AudioPlayer Infinity
- 🆕 [会议 153 ASR 谐音/错识全链路清洗 hook](CHANGELOG.md#2026-06-27-会议-153-asr-谐音错识全链路清洗-hookname_aliases-推到主路径) - name_aliases 推到主路径 + 7 条防御性映射
- 🆕 [v76.2 视觉回归测试 5 件套收官](CHANGELOG.md#2026-06-27-v762-视觉回归测试-5-件套收官) - Playwright baseline + CI hard fail
- 🆕 [v72 P1 摘要+重点摘要合并主题色卡](CHANGELOG.md#2026-06-27-v72-p1-会议纪要-摘要-重点摘要-合并) - color-mix + var(--color-primary)
- 🆕 [v71 P1 议程 timeline + 每 speaker 8 条常驻](CHANGELOG.md#2026-06-27-v71-p1-议程-timeline--每-speaker-8-条常驻)
- 🆕 [v70 P0~P3 字面色 → token + TL;DR 卡](CHANGELOG.md#2026-06-27-v70-p0~p3-字面色-token-化--会议纪要-tldr) - 4 个 phase
- 🆕 [v69 P0+P1 dark mode 全面重构](CHANGELOG.md#2026-06-27-v69-桌面端-dark-mode-全面重构3-阶段) - 3 阶段收官
- 🆕 [v68 桌面主题切换按钮 + SettingsView 玻璃态](CHANGELOG.md#2026-06-27-v68-桌面主题切换按钮--settingsview-玻璃态)
- 🆕 [v31.3 Whisper 常驻 + 推理加速](CHANGELOG.md#2026-06-26-v31-3-whisper-常驻--推理加速用户决策chat-asr-时效性优先) - 模型常驻 GPU 8GB
- 🆕 [v31.2.5 rate-limit Redis ZSET 持久化](CHANGELOG.md#2026-06-26-v31-2-5-rate-limit-收官启用-redis-zset-持久化) - 抗 docker restart

## 未来规划（从浅入深路线图）

### 🔴 高优先级（核心能力扩展）

| Phase | 目标 | 周期 | 状态 |
|-------|------|------|------|
| **#043** | **账号持久化聊天历史（ChatGPT 模式）** — chat_sessions + chat_messages + chat_shares 三表 + 11 API + 流式持久化 + localStorage 自动迁移 + 搜索/导出/标签/分享 + 软删除 30 天清理 | 3-4 天 | **✅ 8/8 phase 完整收官**（commits `558962b1` + `5bf7c5c7` + `af8c8f7d` + `a1dfca2c` + `b9aea177` 等，Phase 6 UI 升级 11 sub-tasks + Phase 7 Celery 30 天清理 + Phase 8 测试沉淀 + 12 条铁律） |
| **Phase 7** | 多模态知识库（图片/公式/表格识别入库） | 4-6 周 | **✅ 已完成 V3**（2026-06-19 收官，knowledge_images + knowledge_extractions 两表 + 21 个 OCR 单测 + 4 篇 PDF 端到端 100% 通过） |
| **Phase 8** | 科研数据自动备份（DB + 文件定时备份 + 异地容灾） | 2-3 周 | 待启动 |
| **Phase 11** | 智能实验记录本（结构化记录 + 模板 + 搜索 + 版本控制） | 4-6 周 | 待启动 |
| **Phase 12** | 科研协作工作流（任务分配 + 进度追踪 + 评审流程 + 通知提醒） | 4-6 周 | 待启动 |
| **Phase 16** | 深度论文理解（解析 + 关键信息提取 + 对比分析 + 趋势发现） | 4-6 周 | 待启动 |

### 🟡 中优先级（AI 能力深化）

| Phase | 目标 | 周期 |
|-------|------|------|
| **Phase 9** | 课题组知识图谱可视化（实体关系网络 + 交互式探索 + 路径发现） | 3-4 周 |
| **Phase 10** | 实时语音科研助手（语音对话 + 实时转录 + AI 问答 + 多语言） | 6-8 周 |
| **Phase 13** | 自动化文献综述（文献检索 + 摘要 + 引用管理 + 综述草稿） | 6-8 周 |
| **Phase 14** | 智能实验方案生成（基于知识库 + 参数推荐 + 风险评估） | 6-8 周 |
| **Phase 15** | 实验数据分析平台（数据导入 + 统计分析 + 可视化 + 报告） | 6-8 周 |
| **Phase 17** | AI 辅助论文写作（大纲 + 内容建议 + 格式检查 + 查重） | 6-8 周 |
| **Phase 20** | AI 科研助手移动端（移动 App + 语音交互 + 离线 + 推送） | 6-8 周 |

### 🟢 低优先级（远期愿景）

| Phase | 目标 | 周期 |
|-------|------|------|
| **Phase 18** | 智能实验设备管理（设备预约 + 使用记录 + 维护提醒） | 4-6 周 |
| **Phase 19** | 课题组专属 AI 研究员（自主研究 + 假设验证 + 论文草稿 + 实验设计） | 8-12 周 |

## 近期完成（按主题）

### 🎨 2026-06-28 v77 P2.6-E/F 视觉/代码质量延伸（4 commits）

- **v77 P2.6-E.1 CSS-in-JS 收官**（commit `ed5e5e16`）— 8 处 runtime `:style` → 7 个枚举 class（status-dot--* / role--* / bar--* / conf-bar--* / quick-icon--* / theme-preview--* / card-file-hero--* / category-badge--*）；`_runtime-style-tokens.scss` 55 → 105 行；VoiceprintCard 保留 per-pixel rgba()（dynamic 必须保留）
- **v77 P2.6-E.2 缓动字面量 token 化**（commit `dcd1657b`）— 70 处 → `var(--ease-*)`；`--ease-out` 升级 Material Decelerate `cubic-bezier(0, 0, 0.2, 1)`（BC break < 5%）；新增 `--ease-quad`（DashboardPet outlier）；`scripts/replace-easing-literals.js` Node.js 脚本（UTF-8 无 BOM）
- **v77 P2.6-E.3 KnowledgeView 拆分**（commit `c06482b5`）— 1599 → 501 行（-68%），抽 4 tab + 1 dialog 5 个新组件：KnowledgeEntityTab（含 ECharts force layout + entityChartInstance 内部 lifecycle dispose）/ HypothesisTab / FormulaTab / MemoryTab / CreateDialog；el-pagination v-model:current-page 改为 :current-page + @current-change 避免子组件 props 直接 v-model 编译错误
- **v77 P2.6-F.1 transition: all token 化**（commit `e362ad8e`）— 27 处 / 17 文件 → `var(--transition-all-fast/normal/slow/slower)`；`scripts/replace-transition-all-literals.js` Node.js 脚本（正则 word-boundary 避免误匹配 0.2s vs 0.25s）；剩余 7 处 `transition: all Xs ease` 字面量（含 !important）保留手工处理
- **4 条新铁律**（[memory/v77-p26-e-and-f-visual-quality.md](memory/v77-p26-e-and-f-visual-quality.md)）：
  ① v-model 不能直接绑定子组件 props（Vue 3 编译期错误）→ 用 `:model-value` + `@update:model-value` 或 computed `{ get, set }` 桥接
  ② el-pagination v-model:current-page 在子组件 props 场景必须改用 :current-page + @current-change，父用 emit('page-change', p) 接收
  ③ Node.js 脚本批量替换 .vue/.css 字面量时，正则必须用 word-boundary `(?!\w)` 避免 0.2s 误匹配 0.25s
  ④ 拆分巨型主 View 时，状态所有权（如 ECharts instance）必须从父移到子组件，子组件 onBeforeUnmount dispose 避免内存泄漏

### 🎨 2026-06-27~28 v77 P2.6 视觉体系 4 子任务全面收官

- **v77 P2.6-A**（commit `36049629`）— paper 14 组件 + 桌面 5 view + ChartBlock token dark 全面化（移动端 9/15 → 15/15 + Rich Block 11/11 dark 化收官）
- **v77 P2.6-B**（commit `8905003a`）— PaperHeader plain 按钮 dark bug 修复 + 移动端 14 view + 6 组件 + 1 Block dark 化 + Desktop Baseline 6 路由
- **v77 P2.6-C**（commit `db3a31e1`）— EP 多主题透传补全（143 条规则：el-tree-select / date-picker / table 展开行 / cascader / transfer 等）+ Mobile Baseline 6 路由 + 登录态双注入（cookie + localStorage 解决 baseline 拍登录页）
- **v77 P2.6-D**（4 commits `19f42924` + `2096d3e0` + `fe896004` + `b251fc22`）— PWA Service Worker 强化（Background Sync 4 写场景 + Navigation Preload + Local Notification）+ 动效治理（6 处重复 keyframes 清理 + 12 --animation-* + 3 --ease-*）+ CSS-in-JS 收敛（3 处 avatar color → .avatar-color-N 枚举 class）+ Baseline 9 路由（+projects /+members /+project-stats）
- **4 条新铁律**（[memory/v77-p26-d-swng-anim-css-baseline.md](memory/v77-p26-d-swng-anim-css-baseline.md)）：
  ① PowerShell `Set-Content -Encoding UTF8` 写 UTF-8 BOM 是隐形地雷
  ② Background Sync 仅适合幂等短写请求（SSE/WS/大文件不能加）
  ③ playwright baseline 必须 dev server 后台启（nohup + sleep 12 兜底）
  ④ token 化拆分渐进优于一次性铺开（先 5-10% 关键部分 + 每步 build 验证）

### 🐛 2026-06-28 三个生产 bug 修复（会议 64 报 500 系列）

- **pgvector embedding truth value bug** — `if not embedding:` 对 numpy.ndarray 抛 `ValueError: truth value ambiguous` → 改 `is None`，2 处生产代码修复 + 3 case 验证
- **SQLAlchemy JSONB flag_modified bug** — `Meeting.transcript_polished` 内部元素 mutate 后 `commit()` 静默不持久化 → 改 `flag_modified(m, "field")` 强制 UPDATE
- **AudioPlayer Infinity:NaN 修复** — `audio.duration` 初始 `Infinity`（WebM 流式 metadata 还没解析），UI 显示 "Infinity:NaN" → 加 `duration` prop + `formatTime` 防御 `Number.isFinite` + 后端预知时长

### 🛠 2026-06-19 全量审计 + CardList 修复 + 开始听会配置

- 5 处 P0 必修（ChatViewSSE `window.open` 运行时错误 / KnowledgeHealth 整页 / ProjectView 编辑 TODO / 移动端 3 处"开发中" / 移动端 2 处误导注释）
- 9 处 P1 死代码清理（4 处死 ref 复活 / ChatView 整文件删 / 6 个孤儿 view 删 / 4 个孤儿 composable 删 / 5 个死 helper 删 / 9 个 dashboard 死 computed 删）
- 13 个孤儿文件清空（knowledge/{Dashboard,Hypotheses,Formulas,Entities,Search}.vue + meeting/{List,Stats}.vue + 3 个 composable + 1 个 component）
- **CardList #item-actions slot 静默丢失根因修复**（用户原报"找不到声纹录入入口"）
- 3 个新移动端 view（MobileMemberDetailView / MobileProjectDetailView / MobileTaskTrash 自给自足）
- 4 个新移动端路由（projects/:id / members/:id / tasks/trash / mobile 移动）
- 17 个新单元测试（SpeakerSearchSheet 8 + MobileMemberDetailView 5）
- **开始听会不再自动建任务**（加 `ENABLE_AUTO_TASK_FROM_MEETING=False` settings 开关，3 处守卫）

### 📱 2026-06-18 移动端 26 commits 全面修复 + 三连环修复

- **移动端 13 个隐藏 bug**（图标 / 路由 / 端点 / 布局 / 指示器 / v-model / ASR / 被动事件 / 知识 / 头像）一次性修复
- **EP useOrderedChildren.removeChild null 崩溃**（Vite plugin patch EP 源码）
- **桌面"正在听会"指示器不接进度**（新建 MeetingRoomView 镜像 MobileMeetingRoom）
- **/auth/me 完全豁免限流**（高频 polling 429 根因）

### 🐳 2026-06-17 Docker Desktop 引擎崩溃 + 镜像源治理

- WSL2 `docker-desktop-data` 发行版丢失 + C 盘 24GB 缓存 → E 盘 junction 透明重定向
- huaweicloud 镜像源 404 → aliyun 正确路径
- aliyun PyPI 限速 → 清华源 + pip `--retries 10`
- `.dockerignore` 17 倍提速 build context（12GB → 700MB）
- 共释放 ~192 GB

### 🔔 2026-06-15 任务提醒 v2 + 会议 #95 声纹重置

- **主动提醒调度器补 11AM 窗口守卫**（修复凌晨 2:48 仍收提醒）
- **会议 #95 声纹重置 + KMeans 重识别**（80 段错标，清理 8 个 JSON 字段）
- **移动端声纹测试真全链路改造**（5 状态机 + 调真 /api/v1/voiceprint/test）

### 🧪 2026-06-27 测试基建收官（v74~v76.2）

- **v74 CSS variable 6 主题组合自动化测试** — 拦截字面色回归 + CI hard fail + token 白名单
- **v75 测试稳定性** — 9 个旧 fail 修复 + PR annotation + token orphan pre-commit 拦截
- **v76.2 视觉回归 5 件套** — Playwright baseline + ci-mode + max-increase + 组件级 CSS 测试

### 🎨 2026-06-26 会议纪要视觉迭代 4 阶段（v70~v72）

- **v70 P0~P2 字面色 → token** — ~340 处 hex 替换 CSS 变量 + dark mode 全面修复（`5ea74dd5` + `f6a2bc3d` + `e4b2eec3`）
- **v70 P3 会议纪要视觉精简** — 顶部 TL;DR 卡 + 默认折叠发言人卡片（`bd41497e`）
- **v70 P3 预防机制** — Stylelint 字面色禁用 + `docs/color-tokens.md` 规范
- **v71 P1 议程 timeline + 每 speaker 8 条常驻** — `el-timeline` 金橙圆 dot + per-card "展开全部" 按钮（`46c85892`）
- **v72 P1 摘要+重点摘要合并** — 主题色 TL;DR 卡显示 `meeting.summary` 完整段落（`eed0c409`）
- **v73 fallback 政策章节补全** — fallback orphan 修复 + CI 集成 + font-mono token（`1707c660` + `d8ae2a2f`）
- **pre-commit hook auto-add web/dist/** — `scripts/check-dist-before-commit.sh` 自动检测 `web/src/` 改动 + 未 tracked dist 文件，避免 dist 漏 commit 导致服务器 404（commit `6565415a`，CLAUDE.md 教训第 4 次沉淀）

### 🚀 2026-06-25~26 限流 / Whisper / 视觉 收官（v31 + v68 + v69）

- **v31.2.x rate-limit 基建收官** — XFF 空 IP 兜底 + analytics regex 永久化 + `request.state.user_id` 维度 + `X-RateLimit-Policy` 头 + SSE tier 10/min + auth prefix match + Redis ZSET 持久化
- **v31.3 Whisper 常驻 GPU 8GB** — 端到端 ASR 1s + `flash_attention` 暂禁用（Blackwell sm_120 上游不支持）
- **v31.3.1 whisper 容器 bind mount** — Dockerfile 删 `COPY` + bind mount 源码，本地改 `whisper_server.py` → `docker compose restart` 即生效
- **v68 桌面主题切换按钮 + SettingsView 玻璃态** — `<html data-accent>` 实时切换
- **v69 P0+P1 dark mode 全面重构** — 3 阶段：P0 基础 5 token + 14 EP 覆盖；P1a 6 套主题切换；P1b 10 桌面视图 dark 适配

### 🚀 2026-06-14 Agent 单阶段流式架构

- **方案 C 收官**（12 commits，取消 brief/detail 双层，用户问"请教谁"直接推荐 3 人 + 理由）
- **Agent 回答质量 5 大根因修复**（14 commits + qa-bench 360 题 84% 高分）
- **知识库 64→247 条**（+183 条 / +286%）

### 📱 2026-06-13 移动端 PWA 收官

- **10 PR × 18 commits**：从基建 → NutUI 4 → 18 个移动端页面 → PWA 离线策略 → Playwright 视觉回归
- 桌面端完全零影响（v-if="!isMobile" 隔离）
- 端到端实测修 5 bug（agentic_loop await / mimo-v2.5 thinking / TraceCollector None / CancelledError / Celery 守卫）

### 🛡️ 2026-06-12 会议录音全栈防御

- **5 阶段全栈防御**（IndexedDB 兜底 + 边录边传 + chunked 端点 + 硬校验 + Celery retry）
- webhint paint keyframes 治理（49+ 报告清零）
- 会议查询 bug 双层根因修复（UnboundLocalError + LLM 撒谎模式）
- Vite hash 改 hex 消除 cache-busting 误报

### 🗑️ 2026-06-03 垃圾桶系统 + 性能优化

- **垃圾桶 4 bug 全修**（精准倒计时双行显示）
- beat 调度 4h → 1h
- Webhook ThreadingHTTPServer（0.001s 响应）

## 详细文档

- 📜 [**HISTORY.md**](HISTORY.md) — 完整开发历史（按时间倒序 commit 流水账，已存档 5730 行）
- 📝 [**CHANGELOG.md**](CHANGELOG.md) — 权威更新日志（按日期组织，简洁）
- 🛡️ [**CLAUDE.md**](CLAUDE.md) — 项目开发铁律沉淀
- 🐛 [**memory/**](memory/) — 事件复盘 + 教训笔记
