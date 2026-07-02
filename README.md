# 微纳米气泡课题组智能Agent系统

> "小气" - 约 20 人研究实验室的 AI 智能助手
>
> 📝 完整更新日志见 [CHANGELOG.md](CHANGELOG.md) · 项目铁律见 [CLAUDE.md](CLAUDE.md) · 历史与路线图见 [ROADMAP.md](ROADMAP.md)

## 功能

- **智能对话** - 文字/语音/图片/文件多模态 Agent，SSE 流式 + Rich Block 渲染
- **知识库 V1+V2+V3** - 文献管理（PDF/Word/Excel/PPT/Markdown）、pgvector 语义搜索（**Qwen3-Embedding-0.6B 1024d**）、RAG 问答、知识图谱、**多模态 OCR**（图片/公式/表格/图表识别入库，4 篇 PDF 100% 端到端）
- **v28 智能论文阅读器** - PDF 12 列结构化字段 + 内嵌图 confidence ≥ 0.85 + IO Hysteresis 防跳变 + RightImageRail 精准推荐
- **任务管理** - 创建/分配/追踪 + 软删除垃圾桶（3 天自动清除，5 级紧急度颜色）
- **主动提醒** - 企业微信推送（11:00 AM 北京时间窗口，Redis 24h 去重）
- **会议系统** - 录音机模式（点"开始听会"即录）+ 离线后处理（ASR + 声纹 + AI 摘要）
- **声纹识别** - 3D-Speaker ERes2Net + pgvector 实时识别发言人（100% 段有效，已修 ERes2Net batch bug）
- **项目管理** - 课题/里程碑/进度追踪
- **企业微信** - 群机器人对话 + 任务派发 + 到期提醒
- **长期记忆** - 用户偏好 + 对话摘要 + 知识图谱
- **🐰 宠物乐园** - 仪表盘两只 CSS 3D 兔子，60fps 自主走动 + XP 成长
- **📱 移动端 PWA** - 路由级双栈（桌面 Element Plus / 移动 NutUI 4），18 个移动端页面 + iOS/Android 全兼容

## 最新里程碑（2026-07-02 晚班 — v2 网盘 PR6-P15 personal_wechat_id + 听会 v4 + LLM 3-Way Benchmark 收官）

- 🆕 **v2 网盘 PR6-P15 personal_wechat_id case-insensitive uniqueness 收官（commit `5bab3f15`）** — 6 文件 / +546 行 = **alembic 055 `UNIQUE INDEX ON LOWER(personal_wechat_id)` 兜底 + service `_IDENTIFIER_COLUMNS` 白名单扩到 3 列 (`{username, wechat_id, personal_wechat_id}`) + 新增 `_COLUMN_LABELS` 中文 label map + API POST/PUT 双保险预检查 + 20/20 pytest PASS + 65 passed, 9 skipped, 0 fail 合跑无回归**. **触发场景**: PR6-P13/14 通用化收官后, 个人微信号 `personal_wechat_id` 仍未保护, 当前 35 行 members 全部 `personal_wechat_id` 为空字符串 (psql 验证), `app/wechat/identity.py:79` `resolve_by_wechat_id()` 当前精确匹配, 但**未来若改 `lower()` 对齐 PR6-P4 mention 3 路模式**, 同样会有 map 撞车风险. 提前兜底比事后清理成本低 10×. **附带 .gitignore 修复**（永久教训）: `.ollama/` 整个目录 (含真实 OpenSSH 私钥 `id_ed25519` 387 字节) + 兜底规则 `**/id_ed25519` / `id_rsa` / `id_dsa` / `id_ecdsa` / `**/*.pem` / `**/*.key` 防任何 SSH 私钥 / TLS 私钥入库. **5 新铁律**: ① `_IDENTIFIER_COLUMNS` 白名单是唯一扩展点 (未来加 personal_email / phone 只改 2 处); ② `_COLUMN_LABELS` dict 中文 label 替代 if-else (加列 O(1) vs O(N)); ③ 未来 `lower()` 改写时撞 map 提前兜底 (vs PR6-P13 因 mention 解析撞 map 才发现问题); ④ PG 函数索引 NULL/空字符串不参与 UNIQUE (多空字符串安全); ⑤ 白名单 + 反射双保险 (防 SQL 注入 + 防止 password_hash 等敏感列被误用).
- 🆕 **听会 v4 三件套修复收官（commit `2cde346f`）** — 3 文件 / +36/-12 行 = **中文文件名下载 RFC 5987 标准化 + 文件夹拖拽层级 + 录音 chunked path meeting context**. **修复 1**: `app/api/v1/drive_files.py:build_content_disposition` 抽 helper, 仅输出 `filename*=UTF-8''<encoded>` (RFC 5987 标准化形式), 旧 `filename="中文.pptx"` 部分走 latin-1 codec 触发 `UnicodeEncodeError` 500 (用户实测触发: "组会ppt/冯懿鑫/2025.7.2 研一 冯懿鑫.pptx"), 4 处调用点统一 (download_drive_file range + 完整 / batch_download_drive_files zip / public_download_by_token range + 完整). **修复 2**: `web/src/composables/useFolderDropZone.js` 删错误赋值 `file.webkitRelativePath = relativePath`, `File.webkitRelativePath` 是 native read-only getter 赋值静默忽略 (Firefox 拖拽场景 relativePath 全 undefined 文件夹层级丢失), 改用 entries 数组直接存 relativePath 字段. **修复 3**: `web/src/views/MeetingRoomView.vue` AudioRecorder 显式 `:meeting-id="meetingId"` + `:meeting-title="pageTitle"` (lazy computed 不传 prop 读不到值, chunked upload 路径触发后丢失 meeting context). **配套 commit 链**: `38487056` (v2 听会修) → `6c297703` (MeetingRoomView v3 修) → `7d0daadf` (chunked_upload rate-limit) → 本次 `2cde346f` (v4 收官).
- 🆕 **LLM 3-Way Benchmark (mimo cloud vs qwen3:8b vs qwen3:14b) 收官** — **生产决策: 保持 `LLM_BACKEND=openai_compat` (mimo cloud)**, 8b 作 offline fallback. **结果 (10 题 subset)**: mimo 50% (5/10) ≈ qwen3:8b 50% (5/10) **平局**, 加权综合分 mimo 0.937 > 8b 0.906 (3% 差距); **35 题完整**: mimo 14.3% > 8b 11.4% (2.9% 差距); **qwen3:14b (9.27GB Q4_K_M, 14.8B params)**: 单题 40-230s (8b 的 5-10×), 80% 题 duration_too_long, 通过率反低 30% — 不适合实时对话, 推荐离线 batch (知识库生成/长文润色). **7 维评分对比 (10 题)**: 8b intent 0.70 > mimo 0.50 (+20%); mimo tool 1.00 > 8b 0.90 (+10%); mimo content 0.97 vs 8b 0.91 (+6%); defense/rich/consistency 都 1.00. **mimo 35 题发现 3 大问题**: ① `fake_xml_leaked` 3/35 (8.6%) `<function=...>` XML 模板泄露给用户 ② `duration_too_long` 2/35 (5.7%) thinking 超过 60s ③ `intent_mismatch` 27/35 (77%) prompts.py intent 分类对所有 LLM 都不友好. **8b 优势**: defense 1.00 (无 fake XML) + 不依赖 mimo rate limit + 5.2GB VRAM 16GB 显卡可装. **5 文件**: `docs/llm-benchmark-2026-07-02.md` (新, 263 行聚合报告) + 4 个 benchmark 报告目录 + reranker 跨模型评估 + `memory/llm-benchmark-2026-07-02.md` (7 铁律) + `tests/manual-test/playwright-e2e-recording.mjs`.
- 🆕 **v2 网盘 PR6-P11 Celery retention 二次确认守卫（commit pending, work in progress）** — 5 文件 + 14 单测 / +213 行 = **3 个 Celery cleanup task (chat_history/drive_cleanup/file_mention) 顶部统一守卫 + 新模块 `app/services/cleanup_safety.py` 双重 API**。继 PR6-P9 误传 `retention_days=0` 删 31 条生产 file_mentions (用户接受丢失) + PR6-P10 backup_before_delete + restore CLI 兜底之后的**第二道防线**：retention ≠ settings 默认值时, 延迟 `RETENTION_OVERRIDE_CONFIRM_DELAY_SEC=0.5s` + logger.warning 二段打印 (检测到 + 二次确认通过), 让人手能在 0.5s 内 Ctrl+C 取消。双重 API: `confirm_retention_param` (延迟+warn+proceed=True, 用户友好, 3 task 默认走这个) + `confirm_retention_param_or_skip` (严格模式, 非默认就拒绝, 留给未来 critical 场景如 Sentry 监控)。**首次集成测试踩坑（永久教训沉淀）**: 测试之前没真 mock service, 守卫 proceed=True 后 task 真跑 cleanup → 真 DELETE 了 4 条 chat_sessions, 用 PR6-P10 `restore_from_backup.py --apply --confirm` 救回, 测试改用 `_make_async_return(0)` mock service 返 0 行 — 守住"测试只验证守卫被触发, 不真删数据"。**5 新铁律 (永久沉淀)**: ① Celery retention 类参数必须 `confirm_retention_param` 守卫 (3 task 顶部统一 import) ② 默认值 == settings 默认时**不触发**守卫 (周期性 `task.delay()` 永远走 None 路径不延迟) ③ 延迟秒数从 settings 读, 紧急场景可设 0 关闭 ④ 测试时必须 mock service 函数返 0, 守卫 proceed=True 后面是真 destructive cleanup ⑤ 严格版 `confirm_retention_param_or_skip` 留给 critical 场景, 默认 3 task 用友好版。**端到端验证**: pytest 14/14 PASS + 3 task 集成测试模拟 retention=0 误传, 守卫 delay + warn 触发成功, 0 真 DELETE。`settings.RETENTION_OVERRIDE_CONFIRM_DELAY_SEC` 可在 `.env` 调: 0.5 默认 / 0 紧急关闭 / 2.0+ CI 审计。
- 🆕 **v2 网盘 PR6-P10 backup_before_delete + restore CLI** (前置, 已在 commit `54e24fb8`) — 7 文件 + 18 单测 / +670 行 / net +550 行 = 3 个 Celery cleanup schedule 全部加 backup 机制 + standalone restore CLI 可单条重 INSERT, PR6-P9 事故根因修复

---

## 历史里程碑（2026-07-01 早班）

- 🆕 **post_meeting_tasks 简化（commit `4b215220`）** — 124 行 → 26 行 (-98, -79%)，移除下划线前缀临时变量 → 直接命名 + 修复 UnboundLocalError 闭包 lazy 求值隐患
- 🆕 **v78 tabs 集成 spec + 临时启用 desktop-chrome（commit `6b6a91f4`）** — 116 行 Playwright spec 验证 `/meetings` 2 tabs 集成 + 批量操作 toolbar + 编辑按钮真实打开 MeetingTemplateDialog
- 🆕 **`scripts/generate_token_plan_doc.py` 项目状况报告 Word 生成（commit `763244ae`）** — 1195 行一次性脚本（不入 CI），产物 71KB docx
- 🆕 **移除 dedup toggle UI + displayedItems 永远 default-on（commit `425e5799`）** — 用户决策"dedup 是产品应该自动做的事，不应让用户在 UI 上控制开关"，删 el-switch + 22 行 localStorage 同步代码
- 🆕 **chore: qa-bench v3 W3-W6 数据集 + ASR benchmark 入库 + .gitignore 兜底 admin token（commit `6573f2b3`）** — 8 个 GitHub Actions dump + `_login.json` + `_token.txt` **admin JWT 凭据泄露风险修复** + 397KB results/ 数据集提交 + `.gitignore` 兜底规则防再泄露

---

## 历史里程碑（2026-06-30 晚班）

- 🆕 **v78 UI redesign — 3-zone 对话窗口 + EP icons + 4-attr a11y（commit `34e82fd9`）** — SessionSidebar overlap 修复 (`flex min-width:0`) + 右键/long-press 上下文菜单 + sortedSessions 置顶冒泡 + 新 NavRail.vue + ChatViewSSE 3-zone 重构 + ThinkingModeSwitch segmented 替代双 toggle 冲突 + 移动端 EP icons 同步 + `--icon-size-*` token；8 条新铁律
- 🆕 **#009 Self-RAG 重检索 + 用户深度思考开关（4 commits）** — Phase 0.5 双重 hook（Haiku judge 800ms + refined_query）+ 3-tier 阈值分档（高≥0.8 直接出 / 中高≥0.6 不重 / 中≥0.4+can_answer 不重 / 低<0.4 触发重检索）+ 前端 useUiStore useDeepThinking + 7 个 AGENT_SELF_RAG_* flag；8 条新铁律
- 🆕 **qa-bench v3.0 6 周冲刺完整收官** — 700 题题库（业务 500 + P 高级 100 + K 横切 100）+ 3 个 P0 检测器 + 7 维评分 + 535 题合并去重 + 14 业务域 × 6 intent × 4 难度矩阵 + KB 入库 5 防线 + 200 题 smoke 套件 + 7 维雷达图 + ROI 100-150% + 8 项决策清单；GitHub Actions CI 200 题 5min 80% 阈值门禁
- 🆕 **Whisper → SenseVoice 迁移收官（commit `9effb8ed`）** — 5 维度实测对比 SenseVoice 全胜：VRAM 0.93 vs 8.0 GB (-88%) / RTF 0.01-0.09 vs 0.08-0.25 (3-25x) / 中文 CER 15.6 vs 25.7% (改善 39%) / 20 min 会议覆盖 500 vs 105 字 (4.7x) / 中文标点 + ITN 原生支持；chunked 推理 (60s + `cache={}`) 防长会议 OOM；torch 2.7+cu128 支持 RTX 5090 sm_120
- 🆕 **KB 数据清洁：B 物理删 1 字节相同副本 + C 前端 dedup toggle（commit `cfd486b6`）** — `scripts/migrate_kb_dedup_titles.py` 5 类 FK 防御 (`knowledge_relations`/`images`/`extractions`/`gaps` ARRAY/`rag_evaluations.context` ILIKE) + 19 单测全 PASS + JSON 备份 28936 字节 + 前端 dedup toggle 默认 ON (`localStorage` key `mnb:kb:dedupView` 仅影响显示策略，不动 stats)；8 条新铁律
- 🆕 **KB 卡片 source_type 重分类（commit `9964f7e4`）** — 180 张 `[拓展-XX]` 卡片从 NULL 重分类到 `auto_expansion`（chip 显示 0 → 180），用 `Knowledge.title.startswith("[拓展")` 避开 SQLAlchemy `regexp_match` 转义陷阱（11 条早期手写数据不动）
- 🆕 **KB 入库监控 D5（commits `ee442125` + `9ea0f87d`）** — 后端 `GET /api/v1/knowledge/auto-intake-summary`（today_intake + weekly_intake[7] + hit_rate + negative_feedback_rate + rollback_count + total_in_db=179）+ 前端 `useKbMonitor.js` polling 5min + ProjectStatsView 第 3 个 tab（4 metric card + 7 日趋势 CSS 柱状图 + 系统状态卡）+ empty placeholder + today 高亮；2 铁律
- 🆕 **声纹循环净化 4 会议累计收官** — #083 杜同贺 86.7%→100% + #135 错标诊断 + #151 王天志 90% 门禁 rollback + #167 段 15-18 修正 + **低占比发言人过滤规则**（1.5s/3s/5%）；9 条铁律 + 4 个 memory 沉淀
- 🆕 **KB "5 个统计全 0" 修复 4 commits 收官** — `7ee94f8e` filter 重置 + chip 再点清除 + 三态空态 + sub-entity total / `765c3dd6` stats GROUP BY 显式补 0 / `74c58e06` fetchCategories shape 适配 dict vs list / `7b4df117` MemberView 排序博X系列；6 条新铁律
- 🆕 **KB 数据清洁 — 自动生成 tags 归并 + 测试样板删除（commit `037f4aa1` + `aff75dce`）** — `scripts/migrate_kb_tags.py` 303 行 + 16 单测全 PASS + scope 双模式（auto_expansion 默认 / notes_category）+ 防御性 WHERE `source_type='auto_expansion'` 隔离真实用户 + 三段式（scan → 人审 → apply + `--confirm`）+ JSON 备份 12 字段 + 真实用户 0 改动
- 🆕 **v78 UI redesign** + **#009 Self-RAG** + **qa-bench v3.0** + **Whisper→SenseVoice** + **KB 清洁** + **声纹循环净化** + 12 个 memory + 4 文档 + 8 scripts + 1 CI workflow 新增 — **详见 [CHANGELOG.md](CHANGELOG.md) [Unreleased] section**

## 历史里程碑（2026-06-30 早班）

- 🆕 **#043 账号持久化聊天历史 8 phase 完整收官（ChatGPT/Doubao 模式）** — PostgreSQL 三表 + 11 API + 流式持久化 + localStorage 自动迁移 + UI 升级（搜索/分享/导出/标签）+ Celery 30 天清理 + 12 条新铁律（vitest 492/492 + pytest 7/7 PASS）
- 🆕 **voiceprint 视觉收官（5 commits，voiceprint-2026-06-30 任务号）** — VoiceprintCard class 化 + VoiceTestDialog Canvas getComputedStyle + ConfidenceChart ECharts 主题色 + Vitest 阈值 8 个单测 + Playwright 6 主题 smoke test；5 条新铁律
- 🆕 **v31.2.6 login_limiter Redis 化 + Retry-After 响应头** — `AsyncRedisRateLimiter` 替换内存 `RateLimiter`，登录端点 5/min + 429 响应头 `Retry-After: 300`（HTTP RFC 7231 §7.1.3 合规）+ pytest-asyncio 0.23.2 → 0.25 升级
- 🆕 **nginx HSTS server-level + gzip_types 扩展（3 commits 真实安全加固）**：
  - commit `71e743f7` — HSTS server-block + gzip_types 扩展（agent + mnb-lab 各一处）
  - commit `289338fb` — 4 个 location 补 HSTS（/favicon.ico / /sw.js / /manifest.webmanifest / static regex）
  - commit `34128fbd` — agent `/` location HSTS 升级 includeSubDomains 对齐
  - **效果**：`strict-transport-security 12→0 errors/route`（9 路由全过），`gzip_types` 9 → 15 MIME（含 `font/woff2` / `application/wasm` 等）
- 🆕 **Knowledge 卡 `analysis_status` 真 bug 修复（commit `3653890b`）**：
  - Step 7 `_reset_multimodal_data` 加 `reset_status=False` 参数（区分 pipeline vs manual UI）
  - `_run_analyze_and_embed` 末尾加 Step 8 最终终态防御
  - `KnowledgeCard.vue` 加 `partial` 状态 tag
  - **DB 清理**：2 张 5 月预存 stuck 卡（KB #14 #19）验证 content 完整后 UPDATE → done
  - **全表状态**：199 done / 1 completed (legacy) / **0 analyzing** / 0 pending
- 🆕 **前端视觉 5 件套（5 commits 一日扫清）**：
  - **KnowledgeToolbar 4 按钮**（commit `558962b1`）—— `.btn-text` utility class 同名冲突修复
  - **MemberView 录入声纹 ghost primary**（commit 845803c3）—— `variables.css` 加 default + `[data-accent]` 双块规则 + `font-weight:600`
  - **VoiceprintView 波形颜色不一致**（commit 36e64fb4）—— 老成员 stale embedding |value|≈0 alpha≈0 不可见，`barColor()` per-card max 归一化 + min alpha floor 0.12
  - **SettingsView Hero 跟随主题**（commit `054668f7`）—— non-scoped `[data-theme=dark].hero-bg` 硬编码 hex 永远赢 scoped 变量
  - **VoiceprintEnrollFlow mobile icon + 5 处 transition token + webhint devDep**（commit `e3b32b86`）—— 全项目扫描 38 个非 scoped style 块 + 1 mobile inline style 全部干净
- 🆕 **v77 P2.6-G.2 meeting-template batch + bar color enum class**：
  - commit `d01420dd` refactor(voiceprint): 收敛 VoiceprintCard bar 颜色到 .bar--low/mid/high class
  - `8c14a0c8` / `95e53955` / `31acafcb` / `d5521a70` meeting-template batch/list endpoint + 11 个 service 单测
  - `0c96331f` admin 桌面端 el-table + MeetingView query.tab
- 🆕 **v77 P2.6-E/F 视觉/代码质量延伸（4 commits）**
  - **P2.6-E.1 CSS-in-JS 收官**（commit `ed5e5e16`，8 处 runtime `:style` → 7 个枚举 class，scss 55→105 行）
  - **P2.6-E.2 缓动字面量 token 化**（commit `dcd1657b`，70 处 → `var(--ease-*)` + `--ease-out` 升级 Material Decelerate + `--ease-quad` 新增 + scripts/replace-easing-literals.js Node.js 脚本）
  - **P2.6-E.3 KnowledgeView 拆分**（commit `c06482b5`，1599 → 501 行，抽 4 tab + 1 dialog 5 个组件，entityChartInstance 生命周期从父移到子避免内存泄漏）
  - **P2.6-F.1 transition: all token 化**（commit `e362ad8e`，27 处 / 17 文件 → `var(--transition-all-*)` + scripts/replace-transition-all-literals.js）
- 🆕 **v77 P2.6 视觉体系 4 子任务全面收官（A/B/C/D 共 7 commits）**
  - **P2.6-A paper 14 组件 + 桌面 5 view + ChartBlock token dark 全面化**（commit `36049629`，移动端 9/15 → 15/15 + Rich Block 11/11 dark 化收官）
  - **P2.6-B Bug 修复 + 移动端 14 view + 6 组件 + 1 Block dark 化 + Desktop Baseline 6 路由**（commit `8905003a`，PaperHeader plain 按钮 dark bug + FallbackBlock dark 化）
  - **P2.6-C EP 多主题透传补全 (143 条规则) + Mobile baseline 6 路由（双注入登录态）**（commit `db3a31e1`，el-tree-select / date-picker / table 展开行全覆盖）
  - **P2.6-D PWA SW + 动效 + CSS-in-JS + Baseline 9 路由**（4 commits `19f42924` + `2096d3e0` + `fe896004` + `b251fc22` + `94bbe3c6`，Background Sync 4 写场景 + 6 处重复 keyframes 清理 + 12 --animation-* + 18 张 baseline）
- 🆕 **3 个生产 bug 修复** — pgvector embedding truth value bug + SQLAlchemy JSONB flag_modified + AudioPlayer Infinity:NaN（详见 [CHANGELOG.md](CHANGELOG.md) + [memory/embedding-truth-value-bug-2026-06-28.md](memory/embedding-truth-value-bug-2026-06-28.md) + [memory/sqlalchemy-jsonb-flag-modified-2026-06-28.md](memory/sqlalchemy-jsonb-flag-modified-2026-06-28.md) + [memory/audio-player-infinity-duration-2026-06-28.md](memory/audio-player-infinity-duration-2026-06-28.md)）
- 🆕 **会议 153 ASR 谐音/错识全链路清洗 hook** — `name_aliases.HARDCODED_ALIASES` 扩容 +7 条会议 153 真实 ASR 误识（`铜鹤/同客/铜棍` → `杜同贺`）+ `post_meeting_tasks` 后处理 hook 推到主路径，所有未来会议自动获得人名清洗
- ✅ **v76.2 视觉回归测试 5 件套收官** — Playwright baseline + ci-mode + max-increase + 组件级 CSS 测试，CI hard fail 拦截视觉回归（commit `f19cb780`）
- ✅ **v75 测试稳定性** — 9 个旧 fail 修复 + PR annotation + token orphan pre-commit 拦截（commit `ee46c34a`）
- ✅ **v74 CSS variable 6 主题组合自动化测试** — CI hard fail + token 白名单（commit `0f77bc29`）
- ✅ **v73 fallback 政策** — fallback orphan 修复 + CI 集成 + font-mono token（commit `1707c660` + `d8ae2a2f`）
- ✅ **v72 P1 摘要+重点摘要合并** — 主题色 TL;DR 卡显示 `meeting.summary` 完整段落，`color-mix()` + `var(--color-primary)` 6 套主题自适应（commit `eed0c409`）
- ✅ **v71 P1 议程 timeline + 每 speaker 8 条常驻** — `el-timeline` 金橙圆 dot + per-card "展开全部" 按钮（commit `46c85892`）
- ✅ **v70 P3 会议纪要视觉精简** — 顶部 TL;DR + 默认折叠发言人卡片 + Stylelint 字面色禁用（commit `bd41497e`）
- ✅ **v70 P0~P2 字面色 → token** — ~340 处 hex 替换 CSS 变量 + dark mode 全面修复（`5ea74dd5` / `f6a2bc3d` / `e4b2eec3`）
- ✅ **pre-commit hook auto-add web/dist/** — `scripts/check-dist-before-commit.sh` 自动检测 `web/src/` 改动 + 未 tracked dist 文件，避免 dist 漏 commit 导致服务器 404（commit `6565415a`，CLAUDE.md 教训第 4 次沉淀）
- ✅ **pre-commit hook 阻止凭据入库 + setup-hooks.sh 一键安装** — `scripts/check-secrets-before-commit.sh` hard block admin JWT / refresh token 入库（commit `63d5675c` + `a242624c`，CLAUDE.md 2026-07-01 安全事件沉淀）
- ✅ **v31.3.1 whisper 容器 bind mount** — Dockerfile 删 `COPY` + bind mount 源码（commit `3f9411cb`）
- ✅ **v31.3 Whisper 常驻 GPU 8GB** — 端到端 ASR 1s（commit `93de5151`）
- ✅ **v31.2.5 rate-limit Redis ZSET 持久化** — 抗 `docker compose restart` 清零（commit `0ea97c95`）
- ✅ **v70 性能优化** — 转录 tab 删除 LLM polish + 替换 `el-select` 为 `popover`，polish-text Redis 缓存 + 前端非阻塞润色
- ✅ **v69 P0+P1 dark mode 全面重构** — 3 阶段：P0 基础 5 token + 14 EP 覆盖；P1a 6 套主题切换；P1b 10 桌面视图 dark 适配
- ✅ **v68 主题切换按钮 + SettingsView 玻璃态视觉升级**

详见 [CHANGELOG.md](CHANGELOG.md) 最新条目 + [docs/upgrade-sentence-transformers-plan.md](docs/upgrade-sentence-transformers-plan.md)

**统计**（[app/stats.json](app/stats.json), 2026-07-01 自动重算）：**1588 commits / 321K 行代码 / 860 文件 / 47 开发天数**（py 74.9K / vue 53.2K / html 83.9K / md 51.1K / config 25.5K / js 23.5K / shell 3.4K / css 3.1K / ts 2.2K / docker 0.2K / other 0.1K / sql 0.1K）

## 技术栈

| 组件 | 技术 |
|------|------|
| 后端 | Python 3.11 + FastAPI + SQLAlchemy + PostgreSQL |
| 前端 | Vue 3.5 + Element Plus + Vite 8 + Pinia + ECharts |
| AI | Claude API (Sonnet) + mimo-v2.5 多模态 |
| 语音 | faster-whisper (GPU) + Edge-TTS + silero-vad |
| 声纹 | 3D-Speaker ERes2Net + pgvector |
| 缓存 | Redis (Session + 微信状态 + 提醒 ZSET) |
| 存储 | MinIO |
| 任务队列 | Celery |
| 部署 | Docker Compose + FRP 内网穿透 |

## 快速开始

```bash
# 1. 配置
cp .env.example .env
# 编辑 .env：CLAUDE_API_KEY、SECRET_KEY、数据库密码
# ⚠️ SECRET_KEY 不能用默认占位符 `change-this-to-a-...`！必须生成强随机
#    python -c "import secrets; print(secrets.token_urlsafe(64))"

# 2. 安装 git hooks (新成员必做, 防止 secrets 误入库 + dist 漏 commit)
bash scripts/setup-hooks.sh

# 3. 启动
start.bat                       # Windows 一键启动所有服务
# 或 docker compose up -d

# 4. 访问
http://localhost:5173           # 前端（开发）
http://localhost:8000           # API
https://agent.mnb-lab.cn        # 生产
```

**Hook 检查**：
```bash
bash scripts/setup-hooks.sh --check   # 验证所有 hook 是否正确配置
```

详细部署：[docs/deploy.md](docs/deploy.md)

## 运维工具

### 会议发言人重处理（用于修复历史会议识别质量）

```powershell
# 重处理某次会议（声纹 + DB + 纪要 + verify 一条龙）
powershell scripts/run-reprocess.ps1 -Meeting 120 -AudioPath "C:\path\audio.m4a"

# 只验证 8 字段无错标人
powershell scripts/run-reprocess.ps1 -Meeting 120 -Steps verify

# 只重生成 summary/key_points/decisions（复用 result.json）
powershell scripts/run-reprocess.ps1 -Meeting 120 -Steps regen
```

cmd.exe 用户：`scripts\run-reprocess.bat 120 verify`

详见 [docs/reprocess-meeting.md](docs/reprocess-meeting.md)。

## 项目结构

```
microbubble-agent/
├── app/           # 后端 FastAPI（agent / api / core / models / services / voice / wechat）
├── web/           # 前端 Vue 3（views / components / composables / stores）
├── scripts/       # 部署 + 运维脚本
├── frp/           # FRP 内网穿透
├── memory/        # 事件复盘笔记（incident reports / 铁律沉淀）
├── docs/          # 部署 / 迁移 / 纪要标准
├── docker-compose.yml
├── Dockerfile.whisper
├── alembic/       # 数据库迁移
├── CHANGELOG.md   # 完整更新日志
├── CLAUDE.md      # 开发铁律沉淀
└── ROADMAP.md     # 历史 + 路线图
```

## 开发工具

本地 PowerShell 三件套（已注册 schtasks）：

- `scripts/local-watchdog.ps1` — Docker 健康监控（每 5 分钟，异常时 Edge-TTS 告警）
- `scripts/local-backup.ps1` — 数据库每日备份（02:00，保留 7 天）
- `scripts/local-build-verify.ps1` — 前端 dist 校验

查看：`schtasks /Query /FO TABLE | findstr Microbubble`

## 详细文档

- 📝 [**CHANGELOG.md**](CHANGELOG.md) — 完整更新日志（按日期组织）
- 📚 [**ROADMAP.md**](ROADMAP.md) — 路线图 + 完整开发历史
- 🛡️ [**CLAUDE.md**](CLAUDE.md) — 项目开发铁律沉淀
- 🐛 [**memory/**](memory/) — 事件复盘 + 教训笔记
- 📖 [**docs/deploy.md**](docs/deploy.md) — 部署与迁移文档
- 📋 [**docs/meeting-minutes-standard.md**](docs/meeting-minutes-standard.md) — 会议纪要标准格式

## 许可证

私有项目，未经许可不得复制或分发。
