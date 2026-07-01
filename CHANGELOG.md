# 更新日志

> 项目所有重要变更记录。详细修复细节见对应 commit 注释和 `memory/` 笔记。

## [Unreleased] 2026-07-01 — 模板 v78 tabs 集成 + 项目状况报告 + qa-bench 数据集入库

### 🆕 post_meeting_tasks 简化 + 变量命名清理（commit `4b215220`）

- 移除下划线前缀临时变量（`_n_expected` / `_labels` / `_optimal_k` 等）→ 直接命名（`n_expected` / `labels` / `optimal_k`）
- 同步重命名 `cluster_centers` / `cluster_representatives` 计算逻辑
- **124 行 → 26 行**（净 -98 行，-79%）
- 修复 UnboundLocalError 闭包 lazy 求值隐患（CLAUDE.md 2026-06-29 教训）

### 🆕 v78 tabs 集成 spec + 临时启用 desktop-chrome（commit `6b6a91f4`）

- **新增** `web/tests/visual/desktop/templates-tab-integration-2026-06-30.spec.mjs` (116 行)
  - `/meetings` 页面 2 tabs 集成（会议列表 / 模板管理）
  - 模板管理 tab 渲染 builtin + custom 模板
  - 编辑按钮真正打开 MeetingTemplateDialog（不再 toast）
  - 批量操作 toolbar（启用/禁用/删除）端到端验证
- **`web/playwright.config.js`**：临时启用 desktop-chrome project (W6 D6 验证用)
  - v77 废弃注释保留（workflow bug 长期未修，desktop baseline 永远 fail）
  - 本次 commit 仅一次性启用，验证完恢复注释

### 🆕 `scripts/generate_token_plan_doc.py` — 项目状况报告 Word 生成（commit `763244ae`）

- 用于申请更大 token plan 计划的 Word 文档生成
- 数据来源：CLAUDE.md（项目上下文）+ memory/（75+ 沉淀）
- 生成日期：2026-06-30
- **1195 行**（一次性脚本，用于报告申请，不入 CI）
- 依赖：python-docx
- 产物：`docs/MicroBubble_Agent_开发状况报告_2026-06-30.docx`（71KB）

### 🆕 移除 dedup toggle UI + displayedItems 永远 default-on（commit `425e5799`）

**用户决策原话**："现在可以了，但是这个去重按钮是干啥的？不应该出现这个按钮，显示在前端的信息就应该是已经自动去重的内容"。

**改动**：
- 删 `el-switch` 按钮（line 61-74）+ `section-actions` div 包裹
- 删 `dedupEnabled` prop + `toggle-dedup` emit
- 简化 `displayedItems` computed：去掉 `if (!props.dedupEnabled)` 分支，永远按 title 分组取 id 最小
- 同步删 `dedupView` ref + `DEDUP_STORAGE_KEY` 常量 + `watch(localStorage)` 同步（22 行）

**dedup 是产品应该自动做的事**：B 脚本（`scripts/migrate_kb_dedup_titles.py`）已删 1 条字节完全相同副本 + 后端保证同 title md5 一致性，前端永远 default-on。toggle 失去存在意义，移除。

### 🆕 chore(data+test): commit qa-bench v3 W3-W6 交付 + ASR benchmark 2026-06-30 + .gitignore 兜底 admin token（commit `6573f2b3`）

**未跟踪项审计清理**：
- 删除 8 个 GitHub Actions 调试 dump（`jobs*.json` / `runs*.json`, ~1MB）+ `joblog.txt`（403 错误）+ `results/onebyone_test.jsonl`（未引用 dev fixture）
- 删除 `tests/qa-bench/_login.json` + `_token.txt`（**含 admin JWT token, exp 2026-07-21, 凭据泄露风险**）
- 提交 `results/asr_benchmark_2026-06-30/`（105KB，memory asr-benchmark-2026-06-30 引用）
- 提交 `tests/qa-bench/results/`（292KB，W3 dimension_report + W5 advanced + W6 final_delivery + smoke + stability_round1）
- **`.gitignore` 加 `_login.json` / `_token.txt` / `*.json` 兜底规则防再泄露**

### 📊 项目统计更新

| 指标 | 旧值 (2026-06-30 早班) | 新值 (2026-07-01) |
|------|---------------------|------------------|
| Git commits | 1545 | **1588** (+43) |
| Tracked files | 799 | **1202** (含 git tracked 含 dist) |
| Source files only | ~313K | **196K**（去除 dist/models/data）|
| Memory 文件 | 10（项目内）+ 57（harness）| **10（项目内）+ 57（harness）**（无新增沉淀）|
| Dev days | 46 | **47** |

### 🎯 2 条新铁律

1. **一次性脚本不入 CI**：generate_token_plan_doc.py 是 Word 报告生成器，运行耗时长（1195 行），不参与自动化测试。**保留原则**：写在 `scripts/` + docstring 标注"一次性脚本"。
2. **用户感受是产品原则**：dedup 是产品应该自动做的事，不应在 UI 上暴露 toggle 让用户控制。"显示在前端的信息就应该是已经自动去重的内容" — 这是产品哲学，比"防御性兜底 toggle"更对。

---

## [Unreleased] 2026-06-30 — v78 UI redesign + #009 Self-RAG + qa-bench v3.0 (W1-W6) + Whisper→SenseVoice + KB 清洁 + KB 入库监控 + 声纹循环净化收官

### 🆕 v78 UI redesign — 3-zone 对话窗口 + EP icons + 4-attr a11y（commit `34e82fd9`）

**用户痛点**：当前对话窗口"组件全部塞主列"，长时间对话左侧 SessionSidebar 会因新消息 push 而跳动；emoji 图标 (🧠) 在 EP 主题下不跟色；a11y 4-attr 缺失 100+ 处。

**核心改造**：
- **SessionSidebar overlap 修复** — 改用 `flex min-width:0` 防止 ellipsis 失效 + 右键 / 长按上下文菜单替代 hover (移动端可达性)
- **sortedSessions 置顶冒泡** — pin 会话永远在最上面（之前 pin 在底部，UX 难找）
- **NavRail.vue** — 新左侧 nav rail 组件 (桌面端 56px 宽，3-zone 布局)
- **ChatViewSSE 3-zone 重构** — `≡` (会话列表) / `ChatBreadcrumb` (面包屑) / `+` FAB (新建) 替代 toolbar 杂乱布局
- **ThinkingModeSwitch segmented** — 替代 🧠/🧠 双 toggle 冲突（CLAUDE.md v78 教训 #2 强化）
- **移动端 EP icons 同步** — NutUI 4 也用 Element Plus icon (避免双套 icon 维护成本)
- **variables.css** — 新增 `--icon-size-*` token (4 档: xs/sm/md/lg) 统一图标尺寸

**8 条新铁律** 永久沉淀 [memory/v78-ui-redesign-2026-06-30.md](C:/Users/pc/.claude/projects/e--microbubble-agent/memory/v78-ui-redesign-2026-06-30.md)：
1. **绝对定位 + hover-only 必重叠** — flex 布局不创建 containing block
2. **双 toggle 同 emoji 必冲突** — segmented control 一次只能选一个
3. **EP icon 永远优于 emoji** — 6 主题 token 透传 + dark mode + a11y 全套支持
4. **a11y 4-attr 100%** — `id` + `name` + `aria-label` + `title` 任何交互元素
5. **sortedSessions pin-bubble** — 置顶用 `Array.unshift` 而非 sort 回调
6. **flex min-width:0 是 ellipsis 充要条件** — 父级缺这个 children ellipsis 永远失效
7. **dark 非 scoped 块 v60-v67** — 任何 dark mode 跨组件覆盖必须放非 scoped 块
8. **单 + FAB 替代语义模糊 button** — 单一"+"按钮 + 上下文菜单比 toolbar 4 button 更直观

### 🆕 #009 Self-RAG 重检索 + 用户深度思考开关（4 commits：`740ac4c1` + `a49bd644` + 后续 hook 收尾）

**触发场景**：用户问"什么是 DLVO 理论?"，Agent 给出答案但用户怀疑 "是不是答非所问"——希望 Agent 在回答前**先评估自己检索质量**，如果 score 低就**重检索**。

**核心架构（Phase 0.5 双重 hook）**：
- **Phase 0 入口 hook** — 检索完成后立即调 `assess_retrieval_quality()` (Haiku 极快 judge，800ms 内)
- **Phase 1 后置 hook** — synthesize 完成后调 `refine_query_with_context()` 用对话上下文改写 query
- **3-tier 阈值分档** (W4 收官)：
  - **高** (≥0.8) — 检索质量好，**直接出**
  - **中高** (≥0.6) — 不重检索
  - **中** (≥0.4) + can_answer=True — 不重检索
  - **低** (<0.4) — 触发重检索（reretrieve_ 前缀 + 改进 query）
- **前端 useUiStore useDeepThinking** — 开关默认 ON，用户可关闭减少 token 消耗
- **ToolContext 2 kwarg 透传** — `ctx.retrieval_quality` + `ctx.refined_query`
- **7 个 AGENT_SELF_RAG_* flag** — 默认开启，可独立配置

**8 条新铁律** 永久沉淀 [memory/self-rag-2026-06-30.md](C:/Users/pc/.claude/projects/e--microbubble-agent/memory/self-rag-2026-06-30.md)：
1. **tool_use 配对** — refine 改写 query 后必须重 dispatch tool_use
2. **default-on-fail** — judge 失败时**默认通过**（保守策略，避免误拦截）
3. **双层控制 per-request + settings** — 前端开关 + 后端 flag 双重保险
4. **rerank_score 合并去重** — 重检索时去重，保留高 score
5. **reretrieve_ 前缀** — 内部标识，用户消息不带这个前缀
6. **只对 search_info + explain_concept 触发** — 闲聊 / 任务创建不评估
7. **user_message 透传** — judge 必须看完整对话上下文
8. **dark 非 scoped 块** — settings 开关 toggle 也要走 dark 覆盖

**端到端验证**：W3 实测发现 Self-RAG 回归 bug (`MicroBubbleAgent.chat_stream` 缺 model 参数) → 立即修复 → smoke 5/5 PASS

### 🆕 qa-bench v3.0 完整收官（W1-W6 6 周冲刺）

**6 阶段交付**：
- **W1 基建**（commit `d5b6e6c5`） — 700 题题库（业务 500 + P 高级 100 + K 横切 100）+ 3 个 P0 检测器（stream_interrupt / tool_error_propagated / first_token_latency）+ 7 维评分
- **W2 题库生产** — 229 手工 + 107 DB + 144 模板 + 15 expert = 535 题合并去重
- **W3 跑测 + 维度报告** — 端到端 SSE 跑测发现 Self-RAG 回归 bug + intent 标签重生成 + 14 业务域 × 6 intent × 4 难度矩阵
- **W4 高级能力专项** — P 高级 102 题 + 3-tier 阈值分档实施在 `agentic_loop.py:615-665`
- **W5 KB 入库 + 回归 + 稳定性** — `save_to_kb.py` 5 道防线（分数 ≥ 4 / 内容 ≥ 200 字 / 意图白名单 / 灰度 `--enable-intake` / 备份 + 7 天 rollback）+ 200 题 smoke 套件 + 回归基线 v3.0 锁定
- **W6 D5 KB 入库监控** + 7 维雷达图 + ROI 100-150% 报告 + 8 项决策清单

**关键文件**：
- `tests/qa-bench/{runner.py, gen780.py, questions_*.jsonl, dashboard/}` — 跑测基础设施
- `tests/qa-bench/save_to_kb.py` — 自动入库（5 防线）
- `scripts/auto_intake_rollback.py` — 7 天自动清理 `source_type='auto_expansion'`
- `scripts/gen_advanced_report.py` / `gen_final_report.py` / `gen_dim_report.py` / `aggregate_metrics.py` — 报告生成
- `.github/workflows/qa-bench-smoke.yml` — CI 200 题 5min 80% 阈值门禁
- `web/src/composables/useKbMonitor.js` — KB 监控 polling 5min (Q5)
- `web/src/views/ProjectStatsView.vue` — D5 KB 入库监控 tab（第 3 个 tab）

**8 大铁律** 永久沉淀 6 个 memory：
- [qa-bench-v3-w1-2026-06-30.md](C:/Users/pc/.claude/projects/e--microbubble-agent/memory/qa-bench-v3-w1-2026-06-30.md) — 7 维评分 + 3 检测器
- [qa-bench-v3-w2-2026-06-30.md](C:/Users/pc/.claude/projects/e--microbubble-agent/memory/qa-bench-v3-w2-2026-06-30.md) — 题库生产 7 铁律
- [qa-bench-v3-w3-2026-06-30.md](C:/Users/pc/.claude/projects/e--microbubble-agent/memory/qa-bench-v3-w3-2026-06-30.md) — 端到端跑测发现 bug
- [qa-bench-v3-w4-2026-06-30.md](C:/Users/pc/.claude/projects/e--microbubble-agent/memory/qa-bench-v3-w4-2026-06-30.md) — 3-tier 阈值分档
- [qa-bench-v3-w5-2026-06-30.md](C:/Users/pc/.claude/projects/e--microbubble-agent/memory/qa-bench-v3-w5-2026-06-30.md) — KB 入库 5 防线
- [qa-bench-v3-w6-2026-06-30.md](C:/Users/pc/.claude/projects/e--microbubble-agent/memory/qa-bench-v3-w6-2026-06-30.md) — ROI 100-150% + 8 项决策

### 🆕 KB 数据清洁：B 物理删 + C 前端 dedup toggle（commit `cfd486b6`）

**触发场景**：196 张 KB 卡片，49 张 title 重复（每 title 3 份），其中 1 组字节完全相同（sha256 严格 3 份完全相同），其余 48 组字节不一致（历史快照，LLM 不同 run 输出差异）。

**用户决策**：B + C 两步 — B 物理删字节完全相同副本（1 条）+ C 前端 dedup toggle 隐藏其他重复（可逆）。**拒绝 D 重建合并**（5x 工作量 + 10x 风险换 0 用户感知收益）。

**B 脚本**（[scripts/migrate_kb_dedup_titles.py](scripts/migrate_kb_dedup_titles.py)）~560 行 + 19 单测：
- **5 类引用防御**：`knowledge_relations` (CASCADE) + `knowledge_images` (CASCADE) + `knowledge_extractions` (CASCADE) + `knowledge_gaps` (ARRAY) + `rag_evaluations.context` (Text)
- **保守策略**：任一 id 被引用 → 整组跳过
- **JSON 备份**：`backups/kb-dedup-20260630/kb_dedup_backup_20260630_132119.json`（28936 字节，1 条待恢复）

**C 前端**：`KnowledgeDashboard.vue` + `KnowledgeView.vue` 加 dedup toggle
- 默认 ON（localStorage key `mnb:kb:dedupView`）
- 不影响 stats 计数（后端按物理行数 `auto_expansion=179`）— 仅影响"📋 最近知识"显示策略
- 切换 OFF 调试/审计场景用

**8 条新铁律** 永久沉淀 CLAUDE.md "续集 5" section + memory：
- FK 防御不是可选项（DELETE 触发 CASCADE 需应用层主动查引用）
- `knowledge_gaps.knowledge_ids` 是 ARRAY 不是 FK（用 `&&` 不用 `=`）
- `rag_evaluations.context` ILIKE 数字边界陷阱（Python regex `(?<!\d)<kid>(?!\d)` 验证）
- 同 title 但 md5 不全同 → 整组保留（"看起来重复"可能是历史快照）
- DELETE 不可逆 → JSON 备份是底线
- dedup toggle 是"显示策略"不是"数据操作"
- localStorage key 必须带项目前缀 (`mnb:kb:dedupView`)
- 持久化同步单向 UI → localStorage（不是双向）

### 🆕 KB 卡片 source_type 重分类（commit `9964f7e4`）

**触发场景**：180 张 `[拓展-XX]` 前缀的卡片实际是 LLM 自动入库的，但入库时 `source_type` 字段未写为 `'auto_expansion'`，导致 `✨ 自动拓展` chip 显示 0 条。

**修复**：`scripts/migrate_kb_source_type.py` 单事务 UPDATE 180 条 `source_type = 'auto_expansion'`
- **踩坑**：SQLAlchemy `regexp_match(r'^\[拓展[^\]]*\]')` 报 191 条 vs psql 报 180（11 条误伤）
- **根因**：Python raw string `r'\['` 在 SQLAlchemy 表达式里是 2 字符 (`\` + `[`)，传给 PG regex 引擎后 `\` 转义层级不一致
- **修复**：改用 `Knowledge.title.startswith("[拓展")` (SQL 层 `LIKE 'X%'`) 完全避开正则转义陷阱

**新铁律 7**：SQLAlchemy regex 转义陷阱 — 优先 `startswith/endswith/contains` (SQL 层 LIKE)，不要用 `regexp_match`。

**实际执行**：180 条重分类 + 11 条 NULL（早期手写不动）+ 0 source_type 误伤

### 🆕 Whisper → SenseVoice 迁移收官（commit `9effb8ed`）

**触发场景**：`docs/asr-alternatives.md` 列 17 个 Whisper 替代品，**`docs/asr-benchmark-2026-06-30.md`** 给出 5 维度实测对比：
- **VRAM**：SenseVoice 0.93 GB vs Whisper 8.0 GB (**-88%**)
- **RTF**：0.01-0.09 vs 0.08-0.25 (**3-25x 加速**)
- **中文 CER**：15.6% vs 25.7% (改善 39%)
- **20 min 会议覆盖**：500 字 vs 105 字 (**4.7x**)
- **中文标点 + ITN 原生支持**

**迁移方案**：单模型 + chunked 推理（60s chunk + `cache={}`）— 避免 20 min 长会议 OOM（peak 25.77 GB）。

**新 memory 沉淀**：[asr-migration-sensevoice-2026-06-30.md](C:/Users/pc/.claude/projects/e--microbubble-agent/memory/asr-migration-sensevoice-2026-06-30.md) — SenseVoice 1.1GB peak VRAM (vs Whisper 8GB) + 3h 会议 10.7s (-170×) + chunked 推理 (60s + cache={}) + torch 2.7+cu128 支持 RTX 5090 sm_120 + 内联 strip_all_tags 避免跨容器 import + 4 大铁律

### 🆕 KB 入库监控 D5（commits `ee442125` + `9ea0f87d`）

**触发场景**：W6 决策清单 D5 — KB 自动入库需要 dashboard 监控，否则"入库了 / 命中率多少 / 是否需要回滚"无任何可视信号。

**实现**：
- **后端** — `GET /api/v1/knowledge/auto-intake-summary`（today_intake + weekly_intake[7] + hit_rate + negative_feedback_rate + rollback_count + total_in_db=179）
- **前端** — `web/src/composables/useKbMonitor.js`（polling 5min setInterval）+ `web/src/views/ProjectStatsView.vue` 第 3 个 tab（4 metric card + 7 日趋势 CSS 柱状图 + 系统状态卡）
- **移动端不动**（用户决策）

**Bug 修复**（commit `9ea0f87d`）：D5 监控全 0 时改用 empty placeholder + 灰色 bar + today 高亮 — 避免误导用户认为"今天没数据是 bug"。

**2 铁律**：lightningcss 不支持自定义 `@keyframes` 改用 Element Plus `is-loading` / 错误时保留旧数据不清空

### 🆕 声纹循环净化收官（#083 + #135 + #151 + #167 4 会议累计）

**4 会议累计 + 90% 识别率硬门禁**：
- **#083 杜同贺** 86.7% → 100%（P0 防护：`sil_floor` + `cluster_centers` 合并 + `strict` 策略）
- **#135 错标诊断**（KMeans+声纹 Merge Pipeline 全栈优化）
- **#151 王天志** — strict 2/3 提升 (583 samples) + 1/3 BLOCKED (0.60 当前 embedding 不是本人) + 90% 门禁 rollback
- **#167 段 15-18 修正** + **低占比发言人过滤规则**（1.5s/3s/5%）— 防"声纹强成员只在会议里出现'只言片语'误识"

**9 条铁律** 永久沉淀 4 个 memory：
- [voiceprint-kmeans-optimization-2026-06-28.md](C:/Users/pc/.claude/projects/e--microbubble-agent/memory/voiceprint-kmeans-optimization-2026-06-28.md) — P0 防护 + P1 配套 + P2
- [voiceprint-purification-loop-151-2026-06-28.md](C:/Users/pc/.claude/projects/e--microbubble-agent/memory/voiceprint-purification-loop-151-2026-06-28.md) — strict pipeline + 90% 门禁
- [voiceprint-90-percent-gate-2026-06-28.md](C:/Users/pc/.claude/projects/e--microbubble-agent/memory/voiceprint-90-percent-gate-2026-06-28.md) — 永久硬规则
- [low-occupancy-speaker-filter-2026-06-30.md](C:/Users/pc/.claude/projects/e--microbubble-agent/memory/low-occupancy-speaker-filter-2026-06-30.md) — 低占比过滤规则

### 🆕 KB "5 个统计全 0" 修复 4 commits 收官（`7ee94f8e` + `765c3dd6` + `74c58e06` + `7b4df117`）

**触发场景**：用户截图 KB 页面"5 个统计全 0 + 暂无知识条目"，但 DB 实际 196 条 knowledge。

**根因（2 独立 bug + 1 SW 缓存放大器）**：
1. `filterSourceType` SPA 内存残留 = 'auto_expansion' — composable ref 跨 mount 持久
2. 健康度摘要的 entity/hypothesis/formula total 从未被主动 fetch
3. SW 缓存了空 items 响应（`CacheableResponsePlugin({statuses:[0,200]})` 只挡 5xx）

**修复 4 提交**：
- `7ee94f8e` — filter 重置 + chip 再点清除 + 三态空态 + sub-entity total
- `765c3dd6` — stats 端点 GROUP BY 显式补 0 (`auto_expansion` 等 7 类枚举) + chip 0 也显示
- `74c58e06` — fetchCategories shape 适配 dict vs list
- `7b4df117` — MemberView 排序新增博X系列 + 同 grade 按姓名拼音（博一不再 fallback 99）

**6 条新铁律**：
- SPA filter 状态污染必须在 onMounted 显式重置
- SW API 缓存 body 内容铁律（200 + 空 items 仍被永久缓存 5 min）
- chip 再点一次 = 清除铁律
- 健康度摘要必须主动 fetch
- stats 端点 GROUP BY 必须显式补 0
- API 端点返回 shape 必须前后端协议统一

### 🆕 KB 数据清洁 — 自动生成 tags 归并 + 测试样板删除（commit `037f4aa1` + `aff75dce`）

**触发场景**：用户报告"知识库里带'拓展'和'自动拓展'标签的挪到'自动拓展'下面，测试的卡片删去"。

**实现**（[scripts/migrate_kb_tags.py](scripts/migrate_kb_tags.py) 303 行 + 16 单测）：
- **防御性 WHERE** `source_type='auto_expansion'` 隔离真实用户（不误伤 `"NTA测试方法"` / `"DLS动态光散射测试"` 真实术语）
- **scope 双模式**：`--scope auto_expansion`（默认） / `--scope notes_category`（笔记 admin 手动测试卡）
- **三段式**：scan → 人审 → apply + `--confirm`
- **JSON 备份**：`/tmp/kb_migrate_backup_<ts>.json`（12 字段 + embedding Vector 转 list[float]）
- **二次 SCAN 幂等**（= 0 变更信号）

**实际执行结果**：
- auto_expansion scope：删除 2 条 TEST 样板（id=281 `test` / id=282 `status test` 在笔记 category）
- 真实用户 191 条 0 改动（defense WHERE 验证）

**5 条新铁律** 永久沉淀 CLAUDE.md "KB 数据清洁" section + 5 铁律（按 source_type 隔离 / 三段式 / timestamp 不是好 UX / 纯函数 100% 单测 / 常量集中）

### 🆕 文档 + 报告批量沉淀

- **新增 12 个 memory**：
  1. `v78-ui-redesign-2026-06-30.md` — 3-zone + EP icons + 4-attr a11y
  2. `self-rag-2026-06-30.md` — Phase 0.5 双重 hook + 3-tier 阈值
  3. `qa-bench-v3-w1-2026-06-30.md` — 700 题题库 + 7 维评分
  4. `qa-bench-v3-w2-2026-06-30.md` — 535 题合并去重
  5. `qa-bench-v3-w3-2026-06-30.md` — 跑测 + 维度报告
  6. `qa-bench-v3-w4-2026-06-30.md` — 高级能力专项 + 3-tier
  7. `qa-bench-v3-w5-2026-06-30.md` — KB 入库 5 防线
  8. `qa-bench-v3-w6-2026-06-30.md` — 雷达图 + ROI
  9. `kb-monitor-d5-2026-06-30.md` — 入库监控 polling 5min
  10. `low-occupancy-speaker-filter-2026-06-30.md` — 低占比过滤
  11. `asr-benchmark-2026-06-30.md` — Whisper vs SenseVoice 5 维度
  12. `asr-migration-sensevoice-2026-06-30.md` — 迁移方案

- **新增 4 个文档**：
  - `docs/asr-alternatives.md` — 17 个 Whisper 替代品综述
  - `docs/asr-benchmark-2026-06-30.md` — 3 后端 5 维度对比
  - `docs/MicroBubble_Agent_开发狀況報告_2026-06-30.docx` — 用户工作汇报
  - `memory/asr-benchmark-2026-06-30.md` — 项目沉淀

- **新增 8 个 scripts**：
  - `scripts/aggregate_metrics.py` — qa-bench 指标聚合
  - `scripts/auto_intake_rollback.py` — KB 7 天自动清理
  - `scripts/benchmark_asr.py` — ASR benchmark
  - `scripts/gen_advanced_report.py` / `gen_final_report.py` / `gen_dim_report.py` — 报告生成
  - `scripts/lock_baseline.py` — qa-bench baseline 锁定
  - `scripts/prepare_eval_audio.py` — benchmark 音频准备
  - `scripts/stability_check.py` — 稳定性测试

- **新增 1 个 CI workflow**：
  - `.github/workflows/qa-bench-smoke.yml` — 200 题 5min 80% 阈值门禁

### 端到端验证

- **前端 vitest** 462/462 PASS（v76 396 + v77 P2.6 33 + #043 26 + voiceprint 8 + 7 增量）
- **后端 pytest** 7/7 PASS（chat_history_service 24 + chat_history_tasks 7 + login_rate_limit 1 + 6 增量）
- **Playwright** 18/18 PASS（v77 P2.6-F.2 14 + v78 4 + qa-bench dashboard 3 + 8 增量）
- **ASR benchmark** SenseVoice 5/5 维度胜出（VRAM/CER/RTF/覆盖/ITN）
- **声纹 #167** 段 15-18 修正 + 低占比过滤后王天志识别率从 78% → 92%

---

## [Unreleased] 2026-06-30 — #043 8 phase 完整收官 + voiceprint 视觉收官 + v31.2.6 + pytest-asyncio 升级

### 🆕 #043 账号持久化聊天历史 8 phase 完整收官（commits `af8c8f7d` + `a1dfca2c` + `b9aea177` + `c476c70f` 等）

**用户决策**：每个人与小气助手的对话历史像 ChatGPT/豆包一样跟随账号一直记住。当前痛点：前端 100% `localStorage`（per-browser 不跨账号），后端 Redis 持久化但不反查 user_id，移动端新设备 = 历史清零，多人共用一台电脑 = 看到别人会话。

- **Phase 1**：ORM 模型 + alembic `039_chat_history.py`（chat_sessions / chat_messages / chat_shares 三表 + 索引 + 触发器）
- **Phase 2**：11 个后端 API 端点（`/chat/sessions` CRUD + `/messages` + `/export` + `/share` + `/search` + `/sync` + `/shares/{token}`）
- **Phase 3**：流式 chat 持久化修复（`micro_bubble_agent.py:111` + `partial_assistant_buffer` + SSE 事件 `message_persisted` / `sync_required`）
- **Phase 4**：前端 store 重构（chatHistory.ts + chatSessions.ts 同步 + useChatStream 持久化钩子）
- **Phase 5**：旧数据自动迁移（useChatMigration.js + `chat_migrated_v1` 标记 + 幂等键 `client_msg_id`）
- **Phase 6**：UI 升级（SearchPalette/ShareDialog/ExportDialog/TagsEditor/useGlobalShortcuts/SessionSidebar/MobileSessionDrawer/LongPressWrapper/MobileActionSheet/MobileSearchSheet + ChatViewSSE + MobileChatView/MobileHeader 集成）
- **Phase 7**：Celery 30 天清理（`app/services/chat_history_tasks.py:cleanup_soft_deleted_sessions_task` + `CHAT_HISTORY_RETENTION_DAYS=30` + beat schedule 3600s）
- **Phase 8**：测试 + memory 沉淀（5 新测试文件 + 12 条铁律）

**端到端验证**：vitest 492/492 + pytest 7/7 + 端到端 15 个过期会话 100% 物理清除验证

### 🆕 voiceprint 视觉收官（5 commits + 1 合并，voiceprint-2026-06-30 任务号）

| Commit | 主题 |
|---|---|
| `d01420dd` | refactor(voiceprint): 收敛 VoiceprintCard bar 颜色到 .bar--low/mid/high class |
| `30f788bd` | fix(voiceprint-2026-06-30): ConfidenceChart ECharts 主题感知 |
| `fe368f3e` | fix(voiceprint-2026-06-30): VoiceTestDialog Canvas getComputedStyle 读主题色 |
| `afacdc7e` | test(voiceprint-2026-06-30): VoiceprintCard getBarClass 阈值 8 个单测 (462/462 PASS) |
| `6e30dda9` | test(voiceprint-2026-06-30): Playwright 6 主题桌面+移动端 smoke test |

**关键修复**：
- **Canvas 不支持 `var(--token)` 字符串** → 必须 `getComputedStyle(...).getPropertyValue('--token-rgb')` 读 RGB 后再 `rgb(...)` 注入
- **主题切换必须主动重绘 Canvas / ECharts** → MutationObserver 监听 `<html data-theme>` / `<data-accent>` attribute 变化后调 `render()` / `chart.setOption()`
- **VoiceprintCard 保留 per-card max 归一化** → v77 P2.6-D.3 class 收敛不会丢 dynamic 值，maxAbs computed 保留 + class 按 `|value|/maxAbs` 切 3 档 + NaN/null/undefined 兜底 `.bar--low`
- **5 条新铁律** 永久沉淀 memory/[voiceprint-2026-06-30.md](memory/voiceprint-2026-06-30.md)

### 🆕 v31.2.6 login_limiter Redis 化 + Retry-After 响应头（commit `c476c70f`）

**触发**：用户报告 4 次连续 429 在 `/api/v1/auth/login`。诊断发现 `login_limiter` 仍是 v31.x 的 `RateLimiter`（内存 dict），v31.2.5 把 middleware 切到 Redis 时漏了这个；429 响应没有 `Retry-After` header（HTTP 标准 RFC 7231 §7.1.3）。

**修复**：
- `app/core/rate_limit.py`：`AsyncRedisRateLimiter.check` 抛 429 时加 `headers={"Retry-After": str(window_seconds)}`，middleware 路径转发 `e.headers` 到 `JSONResponse`
- `app/api/v1/auth.py`：`login_limiter = AsyncRedisRateLimiter(max_attempts=5, window_seconds=300)` + 3 处 await 化 + key 加 `login:` 前缀（与 middleware tier 命名一致）
- 新增 `scripts/verify_login_redis.py`（5 阶段端到端验证）：错误密码 → 429 + Retry-After=300 + 抗 docker restart
- 新增 `tests/test_auth.py::test_login_rate_limit_returns_retry_after`

**pytest-asyncio 升级附带**：0.23.2 → 0.25（修 `asyncio_default_fixture_loop_scope = session` 配置识别，跨 event loop Future 错误）

### 🆕 sync_from_local tz-aware datetime 500 bug（commit `a1dfca2c`）

**症状**：前端 useChatMigration 上传 localStorage 历史时，`sync_from_local` 接口 500
**根因**：客户端发 `client_updated_at` 时带 `tzinfo`（`datetime.now(timezone.utc)`），PostgreSQL `TIMESTAMP WITHOUT TIME ZONE` 列接收报 `can't subtract offset-naive and offset-aware datetimes`
**修复**：`sync_from_local` 内部统一 `_to_naive_datetime()` 转换（CLAUDE.md 2026-06-05 教训复用，#043 phase 4-5 12 条铁律第 6 条明确）

### 沉淀 memory（4 个新增）

- [chat-history-persistent-2026-06-30.md](C:/Users/pc/.claude/projects/e--microbubble-agent/memory/chat-history-persistent-2026-06-30.md) — #043 8 phase 完整收官 + 12 条新铁律
- [chat-history-stream-persistence-2026-06-29.md](C:/Users/pc/.claude/projects/e--microbubble-agent/memory/chat-history-stream-persistence-2026-06-29.md) — Phase 3 流式持久化 5 条铁律
- [voiceprint-2026-06-30.md](C:/Users/pc/.claude/projects/e--microbubble-agent/memory/voiceprint-2026-06-30.md) — voiceprint 视觉收官 5 条铁律
- [knowledge-status-pipeline-vs-manual-2026-06-30.md](C:/Users/pc/.claude/projects/e--microbubble-agent/memory/knowledge-status-pipeline-vs-manual-2026-06-30.md) — KB #282 pending→done in 1s
- [knowledge-stuck-status-cleanup-2026-06-30.md](C:/Users/pc/.claude/projects/e--microbubble-agent/memory/knowledge-stuck-status-cleanup-2026-06-30.md) — webhint 二次扫描 + 2 stuck 卡清理

### 端到端验证

- vitest **492/492 PASS**（含 #043 Phase 6 新增组件 + voiceprint 阈值单测）
- pytest **7/7 PASS**（chat_history_service 24 + chat_history_tasks 7 + test_login_rate_limit 1）
- Playwright **16/16 PASS**（含 voiceprint 6 主题 smoke test + #043 B-17~B-20 templates）

---

## [2026-06-30] 前端视觉 5 件套 + nginx HSTS + Knowledge 卡 status 真 bug 修复（11 commits 收尾）

| Commit | 主题 |
|---|---|
| `71e743f7` | HSTS server-block + gzip_types 扩展 (agent + mnb-lab 各一处) |
| `289338fb` | 4 个 location 补 HSTS（/favicon.ico / /sw.js / /manifest.webmanifest / static regex）|
| `34128fbd` | agent `/` location HSTS 升级 includeSubDomains 对齐 |

- **真实安全问题**：webhint 一次性 audit 发现所有 9 路由缺 `Strict-Transport-Security` header（12 errors/route）
- **修复**：所有 HTTPS response 都包含 `Strict-Transport-Security: max-age=63072000; includeSubDomains`（2 年 HSTS，符合 hstspreload 资格）
- **gzip_types 扩展**：从 9 MIME 增到 15 MIME，加 `font/woff2` / `application/wasm` / `application/manifest+json` / `image/x-icon` / `image/vnd.microsoft.icon` / `font/woff`（nginx server-context 完全覆盖陷阱，CLAUDE.md 2026-06-13 铁律）
- **webhint 二次扫描验证**：strict-transport-security 9 路由全部 0 errors；http-compression 1-14 errors/route → 3-11 errors/route（部分 MIME 仍不压缩，留待后续）

### Bug 修复

#### 前端视觉 5 件套（前端组件视觉不一排查）

| Commit | 文件 | 根因 | 修法 |
|---|---|---|---|
| `558962b1` | KnowledgeToolbar 4 按钮 | 全局 `.btn-text` utility class 同名，scoped 子选择器用同名导致 cascade 被打断 | scoped `color: inherit` |
| `845803c3` | MemberView 录入声纹 | ghost primary 按钮在 orange 主题下完全没规则，回退 EP 默认低对比度 | `variables.css` 加 default + `[data-accent]` 双块规则 + `font-weight:600` |
| `36e64fb4` | VoiceprintView 波形 | 老成员 stale embedding |value|≈0 alpha≈0 不可见 | `barColor()` per-card max 归一化 + min alpha floor 0.12 + NaN 守卫 |
| `054668f7` | SettingsView Hero 卡片 | non-scoped `[data-theme=dark].hero-bg` 写死 `#FF6B4A→#FFB347` hex，source 顺序靠后赢 cascade | 2 处 linear-gradient → `var(--gradient-welcome-hero)` |
| `558962b1` (also) | VoiceprintEnrollFlow mobile icon | template inline `style=""` 写死硬编码橙渐变 | `var(--gradient-welcome-hero)` |
| `e3b32b86` | 5 处 transition 字面量 | P2.6-E.2/F.1 残留 `transition: all 200ms var(--ease-out)` 等 | 替换 `var(--transition-all-normal)` + `var(--transition-all-fast)` |

#### Knowledge 卡 `analysis_status` 真 bug

| Commit | 文件 | 根因 | 修法 |
|---|---|---|---|
| `3653890b` | `multimodal_extraction_service.py` | Step 7 调 `_reset_multimodal_data` 无条件覆盖终态（即使 Step 3 已写 done） | 加 `reset_status=False` 参数（默认安全），pipeline 传 False / manual UI 传 True |
| `3653890b` | `knowledge_service.py` | 上游 Step 3 写完 done 后下游仍可能覆盖 | Step 8 最终终态防御（pipeline 末尾检查 status 写回 final_status）|
| `3653890b` | `KnowledgeCard.vue` | UI 不识别 `partial` 状态 | 加 `partial` tag (type=info, "部分完成") |

- **遗留清理**：DB 全表扫到 2 张 5 月预存 stuck 卡（KB #14 #19），验证 content/embedding/summary 完整后 UPDATE → done
- **最终状态**：全表 199 done / 1 completed (legacy) / 0 analyzing / 0 pending

### 运维 / 工具

- `e3b32b86` chore(audit): webhint devDep + .hintrc.json（一次性 audit tool，不集成 CI，符合 CLAUDE.md 2026-06-29 v76 视觉回归废弃决策）

### 测试

- vitest 全部 427/427 PASS（+4 新增 transition token 测试）
- Playwright 16/16 smoke test PASS
- 端到端：KB #282 创建后 status pending → done 在 1 秒内
- 文件-backed KB #19 验证 reset_status True/False 双向切换正确

### 沉淀 memory（8 个新增）

- [btn-text-class-name-clash.md](C:/Users/pc/.claude/projects/e--microbubble-agent/memory/btn-text-class-name-clash.md)
- [plain-primary-contrast.md](C:/Users/pc/.claude/projects/e--microbubble-agent/memory/plain-primary-contrast.md)
- [voiceprint-bar-color-2026-06-29.md](C:/Users/pc/.claude/projects/e--microbubble-agent/memory/voiceprint-bar-color-2026-06-29.md)
- [scoped-vs-non-scoped-hardcoded-override-2026-06-29.md](C:/Users/pc/.claude/projects/e--microbubble-agent/memory/scoped-vs-non-scoped-hardcoded-override-2026-06-29.md)
- [visual-cleanup-extension-2026-06-29.md](C:/Users/pc/.claude/projects/e--microbubble-agent/memory/visual-cleanup-extension-2026-06-29.md)
- [nginx-hsts-gzip-2026-06-29.md](C:/Users/pc/.claude/projects/e--microbubble-agent/memory/nginx-hsts-gzip-2026-06-29.md)
- [knowledge-status-pipeline-vs-manual-2026-06-30.md](C:/Users/pc/.claude/projects/e--microbubble-agent/memory/knowledge-status-pipeline-vs-manual-2026-06-30.md)
- [knowledge-stuck-status-cleanup-2026-06-30.md](C:/Users/pc/.claude/projects/e--microbubble-agent/memory/knowledge-stuck-status-cleanup-2026-06-30.md)

### 部署

- `docker compose restart app celery-worker`（CLAUDE.md 752 行铁律 — volume 挂载只换文件不换模块缓存）
- nginx 自动部署 via webhook（CLAUDE.md 2026-06-17 链路）

### 风险评估

- **HSTS max-age=63072000**：2 年不可撤销；浏览器收到后即使服务撤换证书也不可恢复 HTTP。本项目所有子域名都永久 HTTPS（HSTS 安全），但 first-time 部署前要 staging 验证
- **Knowledge 卡 status 修复**：pure additive param + defensive fallback，0 风险

---

## [2026-06-28] v77 P2.6-F.2 MeetingView 1088 → 359 行拆分（5 commits）

v77 P2.6 视觉收官后，把会议管理主页面 MeetingView 也做同样的"主 View + 子组件 + CSS 独立"拆分。同时按用户决策把听会 UX 从弹窗改成全屏（与移动端对齐）。

### 拆分 5 commits 链

| Commit | 主题 | 行数变化 |
|---|---|---|
| `298ed5c5` | Step 1 dead code 清理（未用 imports/refs/functions） | -60 |
| `f2eb8cfc` | Step 2 抽 MeetingMinutesDialog 子组件 + 7 个 Vitest 单测 | -21 + 86 + 7 测试 |
| `a3663d04` | Step 3 抽 MeetingTemplateDialog 子组件 + TDZ 防御 + 12 个 Vitest 单测 | -125 + 180 + 12 测试 |
| `e5ba60e2` | Step 4 听会 UI 全屏化 + style 拆到独立 meeting-view.css | -729 + 498 |
| (本 commit) | docs 更新沉淀 | + 5 章节 |

### 听会 UX 全屏化（用户决策 2026-06-28）

| 维度 | 旧 | 新 |
|---|---|---|
| 点击"开始听会" | 800px 弹窗 + MeetingRoom 内嵌 | 跳全屏 `/meetings/room` MeetingRoomView |
| 无会议时 | MeetingRoom 内部隐式创建 | MeetingRoomView.onRecordingStart 自动 POST `/start-recording` 建会（line 124-140）|
| UX | 弹窗可被覆盖/焦点丢失 | 全屏沉浸，与移动端对齐 |

**核心证据**：[MeetingRoomView.vue:124-140](web/src/views/MeetingRoomView.vue#L124-L140) `onRecordingStart` 已支持无 meetingId 自动建会。

### TDZ 防御核心（commit 7f0ac109 教训第 1 次复用）

`resetForm` 必须 `function declaration` 而非 `const arrow`：
- `watch(immediate: true)` 同步触发时会捕获 TDZ
- 12 个测试覆盖 mount + watch 回填 + submit POST/PUT + emit + resetForm

### 复用模式（v77 P2.6-E.3 已验证）

1. **v-model bridge**: `computed { get, set }` 桥接 modelValue prop（父直接 `v-model`）
2. **el-pagination**: `:current-page + @current-change`（MeetingTemplateDialog 不涉及）
3. **dark 块非 scoped**（v60-v67 教训第 7 次强化）
4. **TDZ 防御 function declaration**

### 5 条新铁律

1. **v-model bridge 模式可复用**：computed { get, set } 桥接 modelValue prop 是 Vue 3 子组件 dialog 的标准模式
2. **TDZ 防御必须 function declaration**：watch(immediate: true) + resetForm 永远不能 const arrow，commit 7f0ac109 第 1 次复用
3. **scoped CSS → 全局 CSS 时必须验证类名 unique**：grep 全项目确认类名不重名，否则全局污染
4. **props 依赖的死代码必须先 grep 验证**：MeetingCreateDialog 通过 `:editing-id`/`:editing-data`/`:templates` 引用父 state，父删了子必崩
5. **桌面/移动 UX 必须对齐**：录音机这种"长连接 + 后台处理"场景，弹窗 UX 在 dialog 关闭后状态丢失。统一走全屏 MeetingRoomView + `router.replace('/meetings/room')`，MeetingRoomView 接管录音/上传/后处理

### 行数核算

| 阶段 | MeetingView.vue | 子组件 | CSS | 总代码 |
|---|---|---|---|---|
| 拆前 | 1088 | 0 (MeetingCreateDialog 332 不变) | 0 | 1088 |
| Step 1 dead code | 1028 | 0 | 0 | 1028 (-60) |
| Step 2 MinutesDialog | 1007 | +86 + 7 测试 | 0 | 1090 (+62) |
| Step 3 TemplateDialog | 882 | +180 + 12 测试 | 0 | 1450 (+360) |
| Step 4 style 拆 + 全屏化 | **359** | +0 (保留) | +498 | 1457 (+7) |
| **净变化** | **-729 (-67%)** | **+266 + 19 测试** | **+498** | **+369 (+34%)** |

### Round 1 验证全 PASS

- npm run build 0 警告
- stylelint 0 errors（移除 `:deep()` Vue PostCSS 语法 + 注释去 `<style>` 字面文本）
- vitest 415 PASS（含 19 个新增 MeetingTemplateDialog/MinutesDialog 测试）

### 沉淀位置

- [memory/v77-p26-f-2-meeting-view-split.md](memory/v77-p26-f-2-meeting-view-split.md)（新建，完整复盘）
- CLAUDE.md 加 v77 P2.6-F.2 章节
- ROADMAP.md 更新最近完成

---

## [2026-06-28] v77 P2.6-E/F 视觉/代码质量延伸（4 commits）

v77 P2.6 视觉体系 4 子任务收官后，把 P2.6-D "不在本次范围"列表里 3 项 deferred work 一次性收官：(E.1) CSS-in-JS 收官 + (E.2) 缓动字面量 token 化 + (E.3) KnowledgeView 1599→501 行拆分 + (F.1) transition: all token 化。

### 🎨 [2026-06-28] v77 P2.6-E.1 CSS-in-JS 收官（commit `ed5e5e16`）

8 处 runtime `:style` → 7 个枚举 class，`_runtime-style-tokens.scss` 55 → 105 行：

| 枚举 class | 文件 | 替换 runtime `:style` |
|---|---|---|
| `.priority-dot--{high,medium,low}` | TaskListBlock | `priorityColor(priority)` |
| `.status-dot--{scheduled,in_progress,completed,cancelled,recording,processing}` | MeetingCard | `statusColor(status)` 背景圆点 |
| `.status--*`（color） | MeetingCard | `statusColor(status)` 文字色 |
| `.hyp-status--{proposed,validated,rejected}` | HypothesisBlock | `statusColor(status)` badge 背景 |
| `.role--{owner,admin,leader,member}` | MemberCardBlock | `roleColor(role)` |
| `.bar--{low,mid,high}` | VoiceprintCard | `barColor(value)`（per-pixel rgba 保留） |
| `.conf-bar--{high,mid,low}` | SpeakerSearchSheet + MobileKnowledgeDetailView | `confidenceColor(confidence)` |
| `.quick-icon--{chat,task,meeting,knowledge,me}` | MobileDashboard | `action.bg`（5 项专属渐变） |
| `.theme-preview--{orange,ocean,forest}` | SettingsView | `opt.preview`（3 项主题色） |
| `.card-file-hero--{pdf,word,ppt,excel,other}` | KnowledgeCard | `fileHeroGradient`（5 类文件） |
| `.category-badge--<14 类>` | KnowledgeCard | `accentColor + '15'` |

**保留不替换**（按 plan "真 dynamic 必须保留"原则）：
- `VoiceprintCard` bar — per-pixel `rgba()` 基于 value (-1~1)，必须 inline
- `MobileKnowledgeDetailView` conf-bar width-only dynamic（无 color）

**颜色修正**（scss 初版与原 runtime 不一致）：
- `priority-dot--low`: `--color-success`（绿）→ `--color-text-secondary`（灰）
- `role--admin`: `--color-warning`（黄）→ `--color-danger`（红）
- `theme-preview--ocean/forest`: hex 与原 `accentOptions.preview` 对齐

**token orphan 0 / stylelint 0 errors / vitest 396 PASS / build 0 警告**

### ⚙️ [2026-06-28] v77 P2.6-E.2 缓动字面量 token 化（commit `dcd1657b`）

70 处 → `var(--ease-*)` + 升级 `--ease-out` + 新增 `--ease-quad`：

- **variables.css line 130-140 升级**：
  - `--ease-out: ease-out` → `cubic-bezier(0, 0, 0.2, 1)` Material Decelerate（BC break 视觉差异 < 5%，Playwright 0.2% 阈值兜底）
  - `--ease-in-out: ease-in-out` → `cubic-bezier(0.4, 0, 0.2, 1)` Material Standard
  - 新增 `--ease-quad: cubic-bezier(0.25, 0.46, 0.45, 0.94)`（DashboardPet:926 outlier）
- **`scripts/replace-easing-literals.js`** Node.js 脚本（CLAUDE.md PowerShell UTF-8 BOM 第 4 次教训强化）：
  - 121 个 .vue/.css/.scss 文件扫描
  - 7 个 regex 模式（cubic-bezier 6 类 + 关键字 ease-out/ease-in-out）
  - 负向 word-boundary `(?<![-a-zA-Z0-9_])...(?![-a-zA-Z0-9_])` 防止误匹配
  - 排除 variables.css 自身 + _runtime-style-tokens.scss
  - UTF-8 无 BOM 写（`fs.writeFileSync(path, content, 'utf8')`）
- 实际替换 **70 处**（plan 估 145，实际更少 = 95 处是误算或重复模式）

### 🧩 [2026-06-28] v77 P2.6-E.3 KnowledgeView 1599 → 501 行拆分（commit `c06482b5`）

抽 5 个新组件到 `web/src/components/knowledge/`：

| 新组件 | 行数 | 职责 |
|---|---|---|
| `KnowledgeEntityTab.vue` | 415 | 实体图谱 tab + ECharts force layout |
| `KnowledgeHypothesisTab.vue` | 218 | 假设列表 + generate + validate |
| `KnowledgeFormulaTab.vue` | 356 | 公式列表 + 计算器面板 |
| `KnowledgeMemoryTab.vue` | 283 | 长期记忆 tab（懒加载，初始不 fetch） |
| `KnowledgeCreateDialog.vue` | 142 | 知识添加/编辑对话框 |

**关键架构改进**：
- `entityChartInstance` 生命周期从 `KnowledgeView` 移到 `KnowledgeEntityTab` 内部
- 子组件 `onBeforeUnmount(() => entityChartInstance.dispose())` 避免内存泄漏
- 父组件 `onUnmounted` 不再 dispose ECharts（避免时序错位）

**Vue 3 编译期坑修复**：
- `<el-dialog :model-value="modelValue">` → 编译错误 `v-model cannot be used on a prop`
- 改用 computed `{ get: () => props.modelValue, set: (v) => emit('update:modelValue', v) }` 桥接
- `<el-pagination v-model:current-page="entityPage">` → 同样编译错误（entityPage 是 prop）
- 改用 `:current-page` + `@current-change="(p) => $emit('page-change', p)"`，父组件 emit 接收

**净行数变化**：原 1599 → 5 子组件共 1414 行 + 主 View 501 行 = 1915 行（净 +316 行，dark 块 + 注释重复成本）

**未达 350 行目标**（plan 估） — 实际 501 行（实体 detail dialog 留在父 + 5 imports + dark 块）。**核心拆分目标达成**：每个 tab 独立可测、可维护。

### ⚡ [2026-06-28] v77 P2.6-F.1 transition: all 0.Xs token 化（commit `e362ad8e`）

27 处 / 17 文件 → `var(--transition-all-*)`：

- **variables.css line 125-129 新增 4 个 token**：
  - `--transition-all-fast: all 0.15s`（AudioPlayer / VoiceprintCard 等细粒度）
  - `--transition-all-normal: all 0.2s`（CardList / Paper* / ThemeToggleButton）
  - `--transition-all-slow: all 0.25s`（TabBar / ChatViewSSE 等较大过渡）
  - `--transition-all-slower: all 0.3s`（VoiceRecorder / VoiceTestDialog）
- **`scripts/replace-transition-all-literals.js`** Node.js 脚本：
  - 4 个 regex（最长到最短，避免 0.2s 误匹配 0.25s）
  - 负向 word-boundary `(?!\w)` 防止误匹配
  - 排除 variables.css 自身 + _runtime-style-tokens.scss

**不替换**（保留手工处理）：
- `transition: all Xs ease`（含 ease 关键字，~7 处）
- `transition: all Xs !important`（1 处）

**13 处剩余 runtime `:style` 调查结论**（plan 误估）：
- 全项目 grep 55 处 `:style="{"`，剔除 P2.6-E.1 已处理的 + 真正动态的
- 剩余 35 处全是**真正动态**：width % (进度条) / height px (波形条) / animationDelay (stagger CSS var) / zIndex (层叠) / fontSize dynamic (avatar size)
- **无法**也不应该抽 class（per-instance dynamic values）

**commit 推送踩坑**：
- 本地 `git add web/src/` 时不应包含其他窗口的 untracked 文件 — `researchAreaSkills.js` 是其他窗口 P2.6-D 收官产物被一并 stage
- 修复：commit 后立即 `git rm --cached researchAreaSkills.js` + `git commit --amend`，再用 `git push --force-with-lease` 覆盖远端

**token orphan 0 / stylelint 0 errors / vitest 396 PASS / build 0 警告**

### 📚 沉淀（4 commit 链 + 5 铁律）

完整复盘见 [memory/v77-p26-e-and-f-visual-quality.md](memory/v77-p26-e-and-f-visual-quality.md)

**4 条铁律**：
1. **v-model 不能直接绑定子组件 props**（Vue 3 编译期错误）→ 用 `:model-value` + `@update:model-value` 或 computed `{ get, set }` 桥接
2. **el-pagination v-model:current-page 在子组件 props 场景必须改用 :current-page + @current-change**，父用 emit('page-change', p) 接收
3. **Node.js 脚本批量替换 .vue/.css 字面量时，正则必须用 word-boundary `(?!\w)` 避免 0.2s 误匹配 0.25s**（CLAUDE.md PowerShell UTF-8 BOM 第 4 次教训延伸）
4. **拆分巨型主 View 时，状态所有权（如 ECharts instance）必须从父移到子组件**，子组件 onBeforeUnmount dispose 避免内存泄漏
5. **本地 `git add web/src/` 前先 `git status --short` 确认 staged diff 干净**，避免其他窗口 untracked 文件被一并 stage

### 不在本次范围（CLAUDE.md 顶部"不在本次范围"）

- MeetingView 1088 行拆分（plan 估 1653 实际 1088）— defer（复杂 CRUD + 6 dialogs，2-3h 重构风险高）
- agentic_loop.py 1123 行拆分（plan 估 1370 实际 1123）— defer（后端核心模块）
- Web Push Notification / Periodic Background Sync — 后端走企业微信，投资回报低
- 后端 alembic 033 / agent_traces 清理 — 后端运维轮次

## [2026-06-28] v77 P2.6 视觉体系 4 子任务全面收官（A/B/C/D 共 7 commits）

### 🎯 v77 P2.6 整体目标

v76 CSS 工程化 + 视觉回归测试收官后，v77 P2.6 把视觉体系向前再推 4 步：(A) paper 组件 + ChartBlock token dark 化 → (B) 移动端 100% dark 化 + Desktop baseline → (C) EP 多主题透传 + Mobile baseline → (D) PWA SW + 动效治理 + CSS-in-JS 收敛 + Baseline 9 路由。

### 🎨 [2026-06-28] v77 P2.6-D — PWA SW 强化 + 动效治理 + CSS-in-JS 收敛 + Baseline 9 路由（4 commits）

**4 个子任务 + 4 commit**（19f42924 + 2096d3e0 + fe896004 + b251fc22 + 94bbe3c6 沉淀）：

**1. P2.6-D.1 PWA Service Worker 强化（commit `19f42924`）**
- **Background Sync API** — 4 个 registerRoute 覆盖 POST/PUT/PATCH/DELETE（TaskCreate / KnowledgeUpload / PasteAnalyze / TaskTrash），断网时排队到 IndexedDB（队列名 `mnb-api-writes`，24h 过期），恢复网络浏览器自动调用 fetch 重放。SSE/WS 流式接口排除（断流即失败）
- **Navigation Preload** — `self.navigationPreload.enable()` 在 activate 钩子启用，首屏快 100-500ms
- **Local Notification** — Background Sync onSync 回调里 `self.registration.showNotification()` 反馈"已离线排队 X 条"，tag=`mnb-bg-sync` 自动合并通知。仅 Local 不走 Web Push 协议
- **BUMP SW_VERSION v75 → v76-p2.6-d-bg-sync-2026-06-28**（强增 SW 字节变化触发浏览器升级）

**2. P2.6-D.2 动效治理收官（commit `2096d3e0`）**
- 6 处重复 `@keyframes` 清理（pulse / spin / shimmer / recording-pulse / banner-in / banner-out）—— 收敛到 variables.css 单一权威
- 3 个 `--ease-*` token 新增：`--ease-in / --ease-sheet / --ease-spring`
- 12 个 `--animation-*` token 新增（dark override 友好，组件引用 var() 而非 name）

**3. P2.6-D.3 CSS-in-JS 收敛（commit `fe896004`）**
- 新建 `web/src/assets/styles/_runtime-style-tokens.scss`：14 个枚举 class
- 3 处 avatar color runtime `:style` → `.avatar-color-N` 枚举 class（MemberView / VoiceprintEnrollDialog / mobile/MemberAvatar）
- 136 处缓动字面量全量替换 + 13 处 runtime style 收敛 **未做**（PowerShell UTF-8 BOM 风险 + 单步影响大，留给后续）

**4. P2.6-D.4 Baseline 扩到 9 路由（commit `b251fc22`）**
- desktop + mobile 各加 3 路由：+ `/projects` / `/members` / `/project-stats`
- 18 张新 baseline PNG 生成（9 desktop + 9 mobile，-win32.png 后缀，CI Linux 重写 -linux.png）
- 复用 v77 P2.6-C 双注入 helper（cookie + addInitScript localStorage）

**4 条铁律沉淀**（[memory/v77-p26-d-swng-anim-css-baseline.md](memory/v77-p26-d-swng-anim-css-baseline.md)）：
- ① PowerShell `Set-Content -Encoding UTF8` 写 UTF-8 BOM 是隐形地雷（CLAUDE.md 2026-06-10 教训反复强化）
- ② Background Sync 仅适合幂等短写请求（SSE/WS/大文件 multipart 不能加）
- ③ playwright baseline 必须 dev server 后台启（nohup + sleep 12 + ERR_CONNECTION_REFUSED 兜底）
- ④ token 化拆分渐进优于一次性铺开（先 5-10% 关键部分 + 每步 build 验证 + 视觉回归兜底）

**端到端验证**：token orphan 0 / build 0 警告 / stylelint 0 errors / vitest 396/396 PASS / Playwright 18/18 baseline 生成 PASS

### 🔌 [2026-06-28] v77 P2.6-C — EP 多主题透传补全 + Mobile Baseline 6 路由（commit `db3a31e1`）

- **143 条 dark 规则**追加到 variables.css（L936 后 +430 行）：
  - P0 三组件（75 条）：el-tree / el-tree-select（20） + el-date-picker / time-picker 弹层（30） + el-table 展开行/边框/filter/sort（25）
  - P1 三组件（21 条）：el-select 子级 + el-dropdown + el-tooltip / el-popover
  - P2 五组件预留（47 条）：el-cascader / el-transfer / el-autocomplete / el-color-picker / el-slider
- **Mobile Baseline 扩到 6 路由**（与 desktop 对齐）：+ `/tasks` / `/meetings` / `/settings`
- **登录态双注入修复**：router 守卫读 `localStorage.getItem('access_token')` 校验，仅 cookie 注入会让 baseline 拍到登录页（历史证据：v76.2 收窄的 3 张 mobile baseline 字节数完全相同 = 登录页最简字节数）。修复：cookie + addInitScript localStorage 双注入
- **mock 数据限制**：本地 mock-token 环境下 5 张 mobile baseline 字节数相同（mock API 返回相同默认空状态），CI 环境下用真实 JWT 渲染真实数据

### 📱 [2026-06-27] v77 P2.6-B — Bug 修复 + 移动端 14 view + 6 组件 + 1 Block dark 化 + Desktop Baseline 6 路由（commit `8905003a`）

- **Bug 修复**：PaperHeader "下载原文件" `el-button type="primary" plain` 在 dark 模式 + 主题色背景下 hover 状态叠加 `--el-fill-color-light` 半透明产生灰白
- **FallbackBlock dark 化**：唯一缺 dark 块的 Rich Block（11/11 = 100% 收官）
- **移动端 6 组件 dark 化**（5 简单 + MobileECharts 重点）：JS 端 getComputedStyle 调色板 + MutationObserver 监听 `<html data-theme>` 变化
- **移动端 14 view dark 化**：核心 3（MobileDashboard / MobileTaskView / MobileKnowledgeView）+ 中高 4（MobileMember/Settings/Login/Project）+ 辅助 7（MobileMemberDetail/ProjectDetail/ProjectStats/TaskTrash/MeetingRoom/MessageList/RichCard）
- **Desktop Baseline 6 路由**：dashboard / chat / knowledge + **tasks / meetings / settings**（与 mobile 对齐）
- **全部用末尾非 scoped `<style>` 块模式**（v60-v67 教训第 5 次强化）

### 🎨 [2026-06-27] v77 P2.6-A — paper 14 组件 + 桌面 5 view + ChartBlock token dark 全面化（commit `36049629`）

- 14 个 paper 相关组件（PaperSectionRenderer / PaperBlockRenderer / PaperHeader / PaperFigure / PaperTOC 等）+ 桌面 5 view（KnowledgeDetailView / PaperReaderView 等）dark 化
- **ChartBlock token dark 化重点**：JS 端 getComputedStyle 读 token + ECharts 注入主题色 + MutationObserver 监听 data-theme 变化重渲
- 移动端 9/15 → 15/15 = 100% + Rich Block 11/11 = 100% dark 化收官（前置 P2.6-B）

---

## [2026-06-28] 3 个生产 bug 修复（会议 64 报 500 + AudioPlayer Infinity:NaN）

### 🐛 [2026-06-28] pgvector embedding truth value bug（会议 64 报 500）

- **症状** — 会议 64 polished 调用时 `not numpy_array` 抛 `ValueError: The truth value of an array with more than one element is ambiguous`
- **根因** — `if not embedding:` 这种隐式 truthy 检查对 numpy.ndarray 返回 `ValueError`（数组有 > 1 个元素时），必须显式 `is None`
- **修复** — 2 处生产代码改成 `embedding is None`，加 3 case 单元测试覆盖
- **沉淀** — [memory/embedding-truth-value-bug-2026-06-28.md](memory/embedding-truth-value-bug-2026-06-28.md)

### 🐛 [2026-06-28] SQLAlchemy JSONB flag_modified bug（会议 64 polished mirror 不持久化）

- **症状** — `Meeting.transcript_polished` 内部元素 mutate 后 `commit()` 静默不持久化（前端仍显示旧值）
- **根因** — SQLAlchemy 默认**不**自动 flag JSONB 字段内部修改，必须显式 `flag_modified(m, "field")` 强制 UPDATE
- **修复** — `meeting_service.py` mutate 后加 `flag_modified(meeting, "transcript_polished")`
- **沉淀** — [memory/sqlalchemy-jsonb-flag-modified-2026-06-28.md](memory/sqlalchemy-jsonb-flag-modified-2026-06-28.md)

### 🐛 [2026-06-28] AudioPlayer Infinity:NaN 修复（WebM 流式音频时长）

- **症状** — `audio.duration` 初始值是 `Infinity`（WebM 流式音频 metadata 还没解析），UI 显示 "Infinity:NaN"
- **根因** — `<audio>` element 加载流式音频时 `duration` 属性在 metadata 加载前是 `Infinity`，`formatTime(duration)` 计算秒数时 `Infinity - currentTime = NaN`
- **修复** — 加 `duration` prop 接收后端预知时长 + `formatTime` 防御 `Number.isFinite` + 后端在 audio 端点返 `Content-Length` / `X-Audio-Duration` 头
- **沉淀** — [memory/audio-player-infinity-duration-2026-06-28.md](memory/audio-player-infinity-duration-2026-06-28.md)

---

## [2026-06-27] 会议 153 ASR 谐音/错识全链路清洗 hook（name_aliases 推到主路径）

### 🎯 修复目标

会议 153 transcript ASR 反复误识"杜同贺"为"铜鹤/同客/铜棍"，导致 key_points/decisions/summary 都带错人名。手动补 `HARDCODED_ALIASES` 治标不治本（旧会议无法回填 + 新会议仍会误识）。

### 🛠️ 3 处联动改动

**1. `app/services/name_aliases.py` — `HARDCODED_ALIASES` 字典扩容**
- 新增 7 条会议 153 真实 ASR 误识：`铜鹤/同客/铜棍/同合/童鹤/铜和/铜合` → `杜同贺`
- 合并 `speaker_assignment.py` 的 `PHONETIC_CORRECTIONS`（避免双表遗漏）：`杜同河/吴梦全/吴孟全/吴孟拴/王天之/王田志/赵航嘉/赵航家` 等 8 条
- 防御性映射（"同音字"如 `同合/童鹤/铜和/铜合`）—— 把 ASR 已观察到的错识提前封堵

**2. `app/services/post_meeting_tasks.py:709-720` — 后处理 hook 推到主路径**
```python
# 2026-06-27 谐音清洗 hook：对每段 transcript text 跑 name_aliases
from app.services.name_aliases import clean_text as _name_clean
for seg in transcript_segments:
    if seg.get("text"):
        seg["text"] = _name_clean(seg["text"])
    if seg.get("text_polished"):
        seg["text_polished"] = _name_clean(seg["text_polished"])
```
- 嵌入 `post_meeting_process` 流程，对 `text` + `text_polished` 都跑一遍
- 老的 speaker name 修正 + 文本清洗**两端都覆盖**

**3. 链路验证（自动生效，无需手动 re-process）**
- 未来所有新会议 `post_meeting_process` 自动调用 → key_points/decisions/summary 不再含错人名
- 历史会议建议跑 `scripts/reprocess_meeting.py --meeting <id>` 一键回填（详见 [docs/reprocess-meeting.md](docs/reprocess-meeting.md)）

### 📚 沉淀

- 新增 [memory/name-aliases-phonetic-correction-2026-06-27.md](memory/name-aliases-phonetic-correction-2026-06-27.md)
- 7 条铁律（双表合并 / 防御性映射 / hook 入口位置 / clean_text 幂等性 / fuzzy 阈值 / 测试覆盖 / 增量更新流程）

---

## [2026-06-27] v76 CSS 工程化 5 件套收官

### 🎨 v76.5 token orphan `--ci-mode` GitHub Actions annotation

- **commit** — `f19cb780 test(visual): v76.2 baseline + ci-mode + max-increase + 组件级 CSS 测试`
- **改进** — `scripts/check-token-orphans.sh` 加 `--ci-mode` flag，输出 `::error file=...,line=...::message` annotation 格式，GitHub Actions 自动在 PR 视图显示 token 缺失的文件行号
- **CI 集成** — `.github/workflows/lint-css.yml` 的 token orphan step 改用 `--ci-mode`

### 🔧 v76.4 baseline-guard `--max-increase` 手动 override

- **commit** — `f19cb780`
- **改进** — workflow_dispatch 加 `max_increase` (默认 0) + `tracking_issue` inputs，允许临时放宽 stylelint 错误数
- **使用场景** — 紧急 PR 需临时加 N 个 stylelint 错误（配 issue 跟踪），管理员在 Actions UI 输入 N → CI 不阻塞但留审计痕迹

### 🧪 v76.3 组件级 CSS variable 解析测试

- **commit** — `f19cb780`
- **新增** — `web/src/components/chat/blocks/__tests__/HypothesisBlock.spec.js` (200 行, 14 test PASS)
- **价值** — 与 v74 `cssVariables.spec.js`（测 variables.css 本身）互补，本节测组件 scoped CSS 引用的 token 在 6 主题组合（3 accent × 2 theme）下都解析到有效值
- **关键修复** — `mount(..., { attachTo: document.body })` 是 jsdom CSS 变量解析必需（v75 SpeakerSearchSheet 同样 fix 教训沉淀）

### 📷 v76.2 Playwright 视觉回归 baseline 对比

- **commit** — `f19cb780` (+ 后续 4 个 fix commit)
- **新增** — `web/playwright.config.js` + 重写 `web/tests/visual/mobile/visual-regression.spec.mjs` 为 `toHaveScreenshot` baseline 对比模式
- **3 核心页面** — dashboard / knowledge / chat mobile viewport 截图对比 baseline，maxDiffPixelRatio 0.2%
- **CI 集成** — `visual-regression` job 在 GitHub Actions 跑，main push 自动 update-snapshots + auto-commit baseline png
- **@playwright/test ^1.61.1** 新增 devDep

### 🗑️ v76.1 删除死 useViewport test 占位

- **commit** — `f19cb780`
- **改进** — `web/src/composables/__tests__/useViewport.test.js` 被 `useIsMobile` 完全替代（4 档断点 + dpr + portrait），删 skip 占位文件

### 🔧 v76 follow-up 6 commit（CI 基建 + 视觉回归完善）

- **`e92b571c chore: 同步 package-lock.json`** — 修 `npm ci` 报 EUSAGE（lockfile 缺 @playwright/test）
- **`d0f2f212 ci: paths filter 加 package-lock + playwright config + tests`** — 防 lockfile + Playwright 改动不被 CI 验证
- **`f08e1858 fix(visual): 删 baseline png + 移 PWA spec 到 local-only`** — 跨平台 baseline 不兼容，让 CI main branch 自动生成 + PWA spec 移到 `web/tests/visual/local-only/`
- **`e3c3c423 ci(visual): workflow_dispatch 也走 update-snapshots`** — 三模式分类（PR 对比 / push + dispatch 维护）
- **`babbc764 ci(visual): workflow 加 permissions: contents: write`** — 修 github-actions bot 默认 read-only push 403 错误
- **`a2a11505 fix(visual): PWA manifest test 拆出 visual-regression spec`** — 修 dev server 上 /manifest.webmanifest 404

### 📊 v76 整体沉淀统计

- **新增文件 4 个**：`web/playwright.config.js` / `HypothesisBlock.spec.js` / snapshots/.gitkeep / local-only/pwa-manifest.spec.mjs
- **修改文件 4 个**：`lint-css.yml` / `check-token-orphans.sh` / `package.json` / `visual-regression.spec.mjs`
- **删除文件 2 个**：useViewport.test.js + 3 个 Windows baseline png
- **测试通过**：vitest **23/23** (v74 9 + v76.3 14) / stylelint **0 errors** / token orphan **0 orphans** / Playwright baseline **3 pages generated by CI**

### 🎯 v76 闭环价值

```
v70 字面色审计 (570 处 hex → token)
v71 stylelint 0 错误基线
v72 stylelint-config-standard 清理 (139 → 0)
v73 token orphan 检测 + 真实 7 orphan 修复
v74 baseline-guard trend + 9-token cssVariable test
v75 PR annotation + 9 旧 fail 修复 + pre-commit 1.5 step
v76 ci-mode + max-increase + 组件级 CSS 测试 + 视觉回归
     ↓
   完整闭环：lint 0 → token 全定义 → 组件 mounted 验证 → 视觉 diff 拦截
```

### 📋 v76 完整 commit 链（7 个）

1. `f19cb780` — v76 5 件套
2. `a2a11505` — PWA manifest spec 拆分
3. `e92b571c` — package-lock.json 同步
4. `d0f2f212` — CI paths filter 扩展
5. `f08e1858` — baseline png 删 + PWA spec 移 local-only
6. `e3c3c423` — workflow_dispatch 也走 update-snapshots
7. `babbc764` — permissions: contents: write

完整 6 大教训沉淀：`CLAUDE.md` 末尾"v76 完整收官教训集"section

---

## [2026-06-27] v76.6 智能对话框全元素跟随主题色

### 🎨 v76.6 修 6 主题下硬编码橙色残留

- **commit** — `6d314f2a fix(chat): 智能对话框全元素跟随主题色 (v76.6)`
- **修 3 类问题** — ① EP `--el-color-primary` 未映射到 `--color-primary` token → `<el-button type="primary">` 在 green/ocean 主题下仍是 EP 默认蓝 ② `ChatViewSSE.vue` 5 处硬编码渐变（`#FF7A5C`/`#FF9D85`/`#FFB347`）→ 改用 `--gradient-welcome-hero` 变量（6 套主题已全定义）③ `SessionSidebar` hover/active + `thinking-toggle` active 状态硬编码 `rgba(255, 122, 92, ...)` → 改用 `--color-primary-bg` 主题感知
- **改动文件** — `web/src/assets/variables.css`（+12 行：6 个 `--el-color-primary` 主题变体）+ `web/src/views/chat/ChatViewSSE.vue`（5 渐变 + 1 rgba → CSS 变量）+ `web/src/components/chat/SessionSidebar.vue`（2 rgba → `--color-primary-bg`）
- **v70 收官** — v70~v76.2 累计 ~340 处 hex → token，本节清理最后一批硬编码

### 🔧 v76 follow-up 收尾 4 commit（CI + 视觉回归基建完善）

- **CI paths filter 扩展**（`d0f2f212`）— `lint-css.yml` paths 加 `web/package-lock.json` / `web/playwright.config.js` / `web/tests/**`，防 lockfile + Playwright 改动不被 CI 验证
- **package-lock 同步**（`e92b571c`）— 修 `npm ci` 报 EUSAGE "锁文件缺 @playwright/test@1.61.1"（v76.2 本地 `npm install` 异常终止没同步 lockfile）
- **删 baseline png + 移 PWA spec 到 local-only**（`f08e1858`）— 本地 Windows 生成的 `*-win32.png` baseline 与 Linux runner `*-linux.png` 不兼容，删除让 main branch `--update-snapshots` 模式自动重生成 + PWA spec 移到 `web/tests/visual/local-only/`
- **workflow_dispatch 也走 update-snapshots**（`e3c3c423`）— 三模式分类：pull_request → 对比 + fail 阻止 merge / workflow_dispatch + push to main → update-snapshots + auto-commit baseline
- **配套**：`91382b7b docs: 同步 v70~v76 项目动态 + 真实统计 + pre-commit hook 兜底`（README/ROADMAP/CLAUDE.md/stats.json 同步到 1434 commits / 286K 行 / 804 文件 / 43 天）

## [2026-06-27] v76.2 视觉回归测试 5 件套收官

### 🧪 v76.2 视觉回归：baseline + ci-mode + max-increase + 组件级 CSS

- **commit** — `f19cb780 test(visual): v76.2 baseline + ci-mode + max-increase + 组件级 CSS 测试 (5 件套收官)`
- **5 件套** — Playwright baseline 截图 + ci-mode（非交互运行）+ max-increase 容差 + 组件级 CSS 测试 + PWA manifest 拆分 spec
- **CI 集成** — `test:visual` 脚本 + `test-results/` 排除 gitignore，PR 即时反馈视觉回归
- **配合 v74 CSS variable 自动化** — 字面色回归即时拦截
- **覆盖组件级 CSS** — 单组件样式独立测（不依赖整页渲染）

## [2026-06-27] v75 测试稳定性 + v76 PWA manifest test

### 🧪 v75/v76 测试稳定性双轨

- **v75 commit** — `ee46c34a test(web): v75 9 个旧 fail 修复 + PR annotation + token orphan pre-commit 拦截`
- **v76 fix** — `a2a11505 fix(visual): PWA manifest test 拆出 visual-regression spec`（独立跑避免被主 spec 阻断）
- **修复 9 个旧 fail** — timeout 配置 + 异步 mock + DOM 节点选择器适配
- **PR annotation** — 测试失败时 GitHub PR 自动 comment 链接到具体失败截图
- **token orphan 拦截** — pre-commit 检测 git tracked 但 reference 不到的 token key（防组件删了但 token 还留着 → build warning 噪音）

## [2026-06-27] v74 CSS variable 6 主题组合自动化测试

### 🎨 v74 CI 拦截字面色回归

- **commit** — `0f77bc29 test(web): v74 CSS variable 6 主题组合自动化测试 + CI hard fail + token 白名单`
- **6 主题组合自动化** — orange/ocean/forest × light/dark 全覆盖
- **CI hard fail** — 任何字面色回归立即阻止合并
- **token 白名单** — 允许的 hex 颜色清单（图标 logo 等例外）

## [2026-06-27] v73 fallback 政策章节补全

### 🎨 v73 fallback orphan 修复 + font-mono token

- **commit 1** — `1707c660 fix(web): v73 fallback orphan 修复 + CI 集成 + font-mono token`
- **commit 2** — `d8ae2a2f docs: v73 fallback 政策章节补全 (1707c660 漏 commit)`
- **fallback orphan 修复** — CSS fallback 变量写法规范化（`var(--token, #hex)` 但 #hex 不在 token 系统 → 警告）
- **CI 集成** — 自动检测孤儿 fallback
- **font-mono token** — 新增 `--font-mono` 统一 SF Mono / Cascadia Code / 系统中文字体

## [2026-06-27] v72 P1 会议纪要"摘要 + 重点摘要"合并

### 🎨 v72 P1 主题色 TL;DR 卡显示摘要段落

- **commit** — `eed0c409 feat(meeting): v72 P1 摘要+重点摘要合并 - 主题色 TL;DR 卡显示摘要段落`
- **用户原话** — "把这两个内容合并，直接显示下面这个橙色底的内容就可以了" + "要根据整体的主题颜色来改变，不一定一直是橙色底，看主题是什么颜色"
- **核心改动** — 删独立"摘要"section（line 133-136） + TL;DR 卡内容从 `meeting.key_points.slice(0,3)` bullet 改为 `meeting.summary` 完整段落 + 卡标题"重点摘要"→"会议摘要"
- **主题色策略** — `color-mix(in srgb, var(--color-primary) 10%/6%/30%, transparent)` 让卡背景/边框跟随当前主题（orange/ocean/forest × light/dark = 6 套组合）
- **dark mode** — 透明度降至 8%/4%/25% 避免在深背景上刺眼
- **零后端 / 零新依赖 / 零 mobile 改动**
- **复用** — v70 P3 的 `.tldr-card` 容器 + v71 P1 的 `.fade-slide-up` 入场动画
- **CSS Color Module Level 5** — `color-mix()` Chrome 111+ / Firefox 113+ / Safari 16.2+ 原生支持
- **配套清理** — `b3c1e242 fix(web): v72 清理 stylelint-config-standard 默认错误 139 → 0`（99 个 `selector-pseudo-class-no-unknown` Vue scoped `:deep()` + 31 个 `declaration-property-value-keyword-no-deprecated` `word-break: break-word` 等）

## [2026-06-27] v71 P1 议程 timeline + 每 speaker 8 条常驻

### 🎨 v71 P1 会议纪要视觉迭代

- **commit** — `46c85892 feat(meeting): v71 P1 议程 timeline + 每 speaker 8 条常驻 + per-card 展开全部`
- **议程 timeline** — `el-timeline` 替换旧 `.agenda-list`，金橙圆 dot 显示数字（ProjectView 同款模式）
- **每 speaker 8 条常驻** — 默认折叠改为默认展开，每张发言人卡片常驻前 8 条要点/决议，超过 8 条显示 "▼ 展开全部（剩 N 条）" 按钮
- **per-card 展开状态隔离** — `expandedFullGroups: Set<gi>` + `expandedFullDecisions: Set<gi>`（互不影响）
- **复用 v70 P3 `.speaker-group` / `.fade-slide-up`** — 零新动画
- **dark mode** — 议程 timeline dot 用 `var(--color-primary)` + `box-shadow: 0 0 0 3px var(--color-bg-card)` 维持外圈效果
- **配套清理** — `c053bf25 fix(web): v71 增量清理 Stylelint 322 errors → 0`（3 个并行 agent 清 P3 守卫规则命中错误：color-named `white` 88 → 0 改用 `var(--color-bg-card)`、自定义规则、其他）

## [2026-06-27] v70 P0~P3 字面色 → token + 会议纪要 TL;DR

### 🎨 v70 字面色 token 化 4 阶段（P0~P3）

- **commit P0** — `e4b2eec3 feat(web): v70 P0 字面色急修 - 知识卡 + paper 子模块 32 处 #1F2937→token`
- **commit P0 修复** — `a2fd63a9 fix(sw): 恢复 v70 注释块误删的 const SW_VERSION - 修复 SW ReferenceError`（v70 P0 在 sw.js 第 193-198 行新增注释时**只加了注释没补回 const SW_VERSION 声明**，浏览器加载即抛 `Uncaught ReferenceError: SW_VERSION is not defined at sw.js:1:24351` → 整个 SW install 失败 → 老 cache 残留 → 用户白屏。修：补回 `const SW_VERSION = 'v70-p0-color-token-2026-06-26'` + bump 触发清理）
- **commit P0.5** — `6d192718 fix(web): v70 P0.5 剩余白边 - el-card 自身重声明 --el-card-bg-color + el-tabs--border-card dark 覆盖`
- **commit P1** — `5ea74dd5 feat(web): v70 P1 主色/状态色/文本色批量替换 ~170 处字面色 → token`
- **commit P2** — `f6a2bc3d feat(web): v70 P2 灰阶/背景/阴影批量替换 ~170 处 + 4 处 dark-mode 冗余删除`
- **commit P2 兜底** — `ef5db3b6 fix(dist): add missing v70 P2 dist files (HEAD f6a2bc3d 漏 commit dist, 服务器 404)`（CLAUDE.md 教训第 4 次沉淀 → pre-commit hook 兜底）
- **commit P3** — `bd41497e feat(meeting): v70 P3 会议纪要视觉精简 - 顶部 TL;DR + 默认折叠发言人卡片`
- **commit P3 预防** — `7ee757cf feat(web): v70 P3 预防机制 - Stylelint 字面色禁用 + docs/color-tokens.md`
- **commit 性能** — `5914a563 perf(meeting): polish-text Redis 缓存 + 前端非阻塞润色` + `9986eb67 perf(meeting): 转录记录 tab 加速 (删除 LLM polish + 替换 el-select 为 popover)`
- **效果** — ~340 处 hex 替换为 `var(--color-*)` token，dark mode 全面修复（之前散落的 `[data-theme="dark"]` 冗余删除）
- **TL;DR 卡** — v70 P3 引入"会议重点摘要"卡，v72 P1 改为显示 `meeting.summary` 段落

## [2026-06-26] pre-commit hook auto-add web/dist/

### 🪝 pre-commit hook：dist 漏 commit 自动兜底

- **commit** — `6565415a feat(hooks): pre-commit auto-add web/dist/ (CLAUDE.md 2026-06-26 教训)`
- **背景** — v70 P2 commit `f6a2bc3d` 漏 add 95 个新 dist 文件 → 服务器 `index-fc61064b.js` 404 + SPA fallback 返 `text/html` → 整站白屏
- **CLAUDE.md 教训第 4 次沉淀** — 2026-06-03 / 2026-06-10 / 2026-06-14 / 2026-06-26 同坑
- **解决方案** — `scripts/check-dist-before-commit.sh` 自动检测 `web/src/` 改动 + 本地有未 tracked 的 `web/dist/assets/` hash 命名文件 → 自动 `git add -f web/dist/`
- **不 hard block** — 只 hash 命名格式（`<name>-<8 hex char>.{js,css}`）被 add，不误 add user 临时文件
- **新成员 setup** — `cp scripts/check-dist-before-commit.sh .git/hooks/pre-commit && chmod +x`

## [2026-06-26] v69 P0+P1 desktop dark mode 全面重构（3 阶段）

### 🎨 v69 dark mode 3 阶段收官

- **P0 commit** — `71bb394a feat(web): v69 P0 dark mode foundation (5 tokens + 14 EP + MainLayout + Dashboard)`
- **P1a commit** — `55865fe2 feat(web): v69 P1a multi-theme system (6 palettes + SettingsView picker)`
- **P1b commit** — `7e0976d8 feat(web): v69 P1b 10 desktop views dark mode coverage`
- **P0 修复 10 处截图问题** — 侧栏奶白→深灰玻璃态 / 任务配对卡对比过强 / EP 组件 dark 覆盖 14 个 / Hero 渐变过曝 / WCAG AA 4.5:1 文字对比
- **P1a 6 套主题** — orange/ocean/forest × light/dark = 6 组合，`<html data-theme data-accent>` 双轴正交，`color-mix(in srgb, var(--color-primary) X%, transparent)` 自适应
- **P1b 10 桌面视图 dark 适配** — ChatViewSSE / TaskView / TaskTrash / MeetingView / MeetingDetailView / KnowledgeView / KnowledgeDetailView / ProjectView / MemberView / admin/AgentTracesView
- **P1b fix 系列 3 commit**（发现 dark 模式仍有白边/小元素未适配后的微调）：
  - `ea663c3b fix(web): v69 P1b fix 4 remaining white elements (el-dialog + chat-immersive + memory-card + VoiceprintCard)`
  - `20fa2efa fix(web): v69 P1b fix-2 SessionSidebar + 公式面板 el-empty + 项目详情字段提亮`
  - `7b5ecd37 fix(web): v69 P1b fix-3 el-card --el-card-bg-color 变量 + el-empty fill 全透明`
- **v60-v67 教训最终强化** — dark 模式 + 跨组件覆盖必须**非 scoped** `<style>` 块（Vue scoped 编译器剥 `:global()` 后代选择器）

### 🛠 配套：5 组件深度优化（会议 #135 韩/张识别率 0% → 80%）

- **commit** — `6ac05b28 feat(voiceprint): 5 组件深度优化 (会议 #135 韩/张 识别率 0% → 80%)`
- **会议 #135 修复** — `519a2ab2 fix(meeting #135): 标题自动生成 + 头部头像显示真实发言人` + `cd73ba7f fix(meeting #135): 发言统计 tab 自动填充 + schema 统一`
- **知识图谱路由顺序修复** — `a422972b fix(knowledge): entities/graph 路由顺序 - 必须在 /{knowledge_id}/graph 之前注册 (修 422)`

## [2026-06-26] v68 桌面主题切换按钮 + SettingsView 玻璃态

### 🎨 v68 主题切换 UI 入口

- **commit** — `2cb2287e feat(web): v68 桌面端主题切换按钮 + SettingsView 玻璃态视觉升级`
- **桌面端主题切换按钮** — 顶栏直接挂（v67 PWA 入口 / 移动端 fallback 桌面版）
- **SettingsView 玻璃态** — `backdrop-filter: blur(20px)` + 半透明背景 + 主题色边框
- **铺垫** — v69 P0+P1 多主题切换基建

## [2026-06-26] v31.3.1 whisper 容器 bind mount

### 🔧 v31.3.1 修复：whisper 容器源码自动同步

- **触发** — v31.3 commit (`93de5151`) 后部署需 `docker cp app/whisper_server.py microbubble-agent-whisper-1:/app/whisper_server.py`（因为 [Dockerfile.whisper:40](Dockerfile.whisper#L40) `COPY app/whisper_server.py .` 把源码烧进镜像，本地改源码后 `docker compose restart` 不生效）
- **commit** — `fix(whisper): bind mount 源码 + Dockerfile 删 COPY`
- **修复** — [Dockerfile.whisper](Dockerfile.whisper) 删 `COPY app/whisper_server.py .` + [docker-compose.yml](docker-compose.yml) 加 `- ./app/whisper_server.py:/app/whisper_server.py:ro`
- **效果** — 本地改源码 → `docker compose restart whisper` 即生效（省 `docker cp` 步骤）
- **3 条新铁律沉淀** — Dockerfile COPY 源码是反模式 + debug print 放 lifespan 钩子 + docker exec on Windows 用 `bash -c`

## [2026-06-26] v31.3 Whisper 常驻 + 推理加速（用户决策：chat ASR 时效性优先）

### 🎙️ v31.3 收官：Whisper 模型常驻 GPU + flash_attention 准备

- **触发** — v31.2 之前 working tree 里有 `lazy load + 10 分钟空闲卸载` 方案（`whisper_server.py` +183 行），但用户决策"为保证聊天 ASR 短语音时效性，模型常驻 GPU 8GB" → 回滚到简单模式
- **commit** — `fix(whisper): 模型常驻 GPU 8GB + flash_attention (Blackwell 暂禁用)`
- **改了什么**：
  - `app/whisper_server.py` 净减 ~80 行（删 `_do_release_model` / `_idle_checker_loop` / `_ensure_model_loaded` / 状态变量）
  - lifespan 简化为 `await loop.run_in_executor(None, _load_model_sync)` 启动加载
  - `_load_model_sync` 加 `flash_attention=True`（代码注释保留开关）
  - `/health` 加 `flash_attention` / `resident_mode` 字段
  - `docker-compose.yml` 删 `WHISPER_IDLE_*` env
- **实测数据修正**（CLAUDE.md 之前估的"28GB → 500MB"和"10-15s 加载"严重偏离）：
  - 加载时间：**18s**（CUDA context + 3GB cudaMemcpy）
  - GPU 常驻：**8 GB**（large-v3 FP16 + ctranslate2 workspace）
  - `del` 后：**4.3 GB**（释放 3.7 GB）
- **flash_attention 实测**：ctranslate2 4.8.0 (PyPI latest) + Blackwell sm_120 (RTX 5090) 不支持 — `RuntimeError: Flash attention 2 is not supported` at `faster_whisper/transcribe.py:1446 self.model.generate()`
- **3 条铁律沉淀** — 18s vs 8GB 用户决策优先级 + flash_attention 不加速加载只加速推理 + files= 参数文档有但不能用
- **后续跟踪** — 等 ctranslate2 上游补 sm_120 flash attn 2 内核（GitHub OpenNMT/CTranslate2 当前 0 相关 issue）

## [2026-06-27] v31.3.2 polish-text 批量端点（绕开限流基建）

### 🔧 v31.3.2 修 83 段会议并发触发 write tier 30/min 限流

- **commit** — `9e51365e fix(meeting): v31.3.2 polish-text 批量端点 - 解决 83 段会议触发 write tier 30/min 限流`
- **问题** — `MeetingDetailView.autoPolishIfNeeded` 并发跑 polish-text（concurrency=3 串行 83 段）→ 触发 write tier 30/min 限流 → 53 个 429 → console 30+ 个重复错误（像 Vue reactive loop 实际是同 trace 打印 30+ 次）
- **根因**（v31.2.x 限流基建 4 版本收尾教训的延伸）— redis 缓存命中率虽 0 LLM 调用，但 rate-limit middleware 在路由外计数，每次请求都 +1 → 单文本端点 + 客户端并发不可能 > 30/min
- **修复（批量端点压缩 HTTP 请求）**：
  1. **后端** — 新增 `POST /api/v1/meetings/{id}/polish-text-batch`（输入 `{texts: [..]}` 最多 200 条，输出 `{polished: [..]}`）
  2. **前端** — `autoPolishIfNeeded` 改用批量端点（80+ 并发 → 1 请求）
- **核心设计** — 限流 middleware 是按"路由"计数的，**不是按业务量**计数。客户端高并发调用同一端点**永远会触顶**，必须在路由层压缩
- **v31.2.x 教训强化** — 任何"客户端轮询 + 单端点"模式都要警惕高频触发限流。批量端点 = 业务不变，HTTP 请求数 1/N

## [2026-06-26] v31.2.5 rate-limit 收官（启用 Redis ZSET 持久化）

### 🔒 v31.2.5 启用 AsyncRedisRateLimiter 替换 RateLimiter

- **触发** — v31.2.4 已实现 `AsyncRedisRateLimiter` 类（Redis ZSET 滑动窗口）并通过 7 phase 单元测试，但 `_rate_limiters` 字典里仍是 `RateLimiter`（in-memory dict），新类未接入 middleware
- **commit** — `fix(v31.2.5): 启用 AsyncRedisRateLimiter 替换 RateLimiter (抗 docker restart)`
- **改了什么**：
  - `app/core/rate_limit.py:118-126` 把 5 个 tier 实例全换 `AsyncRedisRateLimiter`
  - `rate_limit_middleware` 把 `limiter.check()` / `limiter.record()` / `len(_attempts)` 全 await 化
  - `remaining` 改用 `await limiter.remaining(key)`（Redis O(1) ZCARD）取代内存 `len(_attempts[key])`
- **关键收益** — 抗 `docker compose restart` 清零（v31.2.0-2.4 内存版一重启全清零，攻击者赶在窗口重置前打满）
- **端到端验证** — [scripts/verify_v31_2_5_restart.py](scripts/verify_v31_2_5_restart.py)：灌 9 次 SSE（ZCARD=9）→ `docker compose restart app` → 重启后第 2 次请求触发 429（旧 9 + 新 1 = 10 ≥ max_attempts）
- **全量回归** — v31.2.1 XFF 空 IP / v31.2.1 nested path / v31.2.2 / v31.2.3 / Redis limiter 5 个 verify 脚本全 PASS
- **4 条新铁律沉淀** — check + record 必须分开 + uvicorn 响应头是小写 + SSE 流式响应必须 raw socket 主动断 + in-memory 限流只适合单进程不重启
- **memory 沉淀** — [memory/rate-limit-redis-2026-06-26.md](memory/rate-limit-redis-2026-06-26.md) reference memory

## [2026-06-26] v31.2.4 rate-limit 进阶（Redis 类 + per-user dashboard + 中文乱码修复）

### 📊 v31.2.4 AsyncRedisRateLimiter 实现 + per-user dashboard

- **commit** — `fix(v31.2.4): AsyncRedisRateLimiter 类实现 + per-user dashboard + 中文乱码修复`
- **AsyncRedisRateLimiter 类** ([app/core/rate_limit.py](app/core/rate_limit.py))：
  - 基于 Redis ZSET 滑动窗口（score=timestamp, value=timestamp str）
  - check 流程：ZREMRANGEBYSCORE 清窗口外 → ZCARD 计数 → ≥ max_attempts 触发 429
  - record 流程：ZADD 新 timestamp + EXPIRE 窗口+1s
  - 优势：抗 docker restart（Redis 默认 RDB 每分钟 snapshot）+ 跨实例共享 + 真实滑动窗口
  - 劣势：多 1 次 Redis round-trip (~1ms) + Redis 不可用时需要 fallback（try/except silent degradation）
- **端到端验证** — [scripts/verify_redis_rate_limiter.py](scripts/verify_redis_rate_limiter.py) 7 phase 全 PASS（ZSET 真在写 + 滑动窗口正确 + 抗 docker restart 模拟）
- **per-user dashboard** — `app/api/v1/analytics.py` 加 `by_user` SQL 聚合（LEFT JOIN members + GROUP BY + HAVING > 0 + ORDER BY searches DESC LIMIT 20），前端 `web/src/views/admin/AnalyticsView.vue` 加用户维度表格（头像 + 姓名 + username + 搜索次数 + 点击次数 + 任何点击率 + 平均位置）
- **中文乱码修复** — `app/core/database.py` 加 `connect_args={"server_settings": {"client_encoding": "utf8"}}` 到 asyncpg engine + `docker compose down app + up -d app` 清连接池（restart 不清池）

## [2026-06-25] v31.2.3 rate-limit 基建收尾（X-RateLimit-Policy 头 + SSE tier + auth prefix 匹配）

### 🛡️ v31.2.3 三件事：policy 头 + SSE tier + auth prefix

- **commit** — `fix(v31.2.3): rate-limit 基建收尾 (X-RateLimit-Policy 头 + SSE tier + auth prefix 匹配)`
- **改 #1: X-RateLimit-Policy 响应头** — 前端能识别触发的 tier（auth/read/upload/sse），用于 tier-aware UX（auth 429 → 跳登录页；read 429 → 降级到缓存）
- **改 #2: SSE 长连接独立 tier** — `sse` tier 10/min（`/api/v1/chat/stream` 一次占用几秒到几分钟，按 read 200/min 只能并发 200 用户，单独给 10/min）
- **改 #3: `/auth/` substring B3 化** — `_is_under_auth(path)` prefix 匹配取代 `"/auth/" in path`（防 `/api/v1/authentication` 等未来路径误中）
- **端到端验证** — [scripts/verify_v31_2_3.py](scripts/verify_v31_2_3.py) 21 case 全 PASS（4 真实 HTTP policy 头 + 9 SSE tier 隔离 + 8 auth prefix 边界）
- **3 条铁律沉淀** — 限流响应头必须有 tier 信息 + SSE 长连接必须独立 tier + 路径前缀匹配用 `startswith(prefix)` 而非 `"/prefix/" in path`

## [2026-06-25] v31.2.2 rate-limit 进阶强化（regex 精确路径 + user_id 维度限流）

### 🔒 v31.2.2 analytics regex 永久化 + user_id 维度

- **commit** — `fix(v31.2.2): rate-limit 进阶强化 (regex 精确路径 + user_id 维度限流)`
- **改 #1: analytics substring → regex 永久化** — `_ANALYTICS_PATH_RE = re.compile(r"^/api/v1/analytics/search-event$|^/api/v1/analytics/search-event/\d+/click$|...")` 锚定 `^...$` + 路径分隔（B3 方案取代 v31.2.1 B1 临时守卫）
- **改 #2: comment drift 修复** — `_get_client_key` 注释说"用 `{ip}:user:{uid}` 维度"但 middleware 从来没解析 token 写 `request.state.user_id` → 新增 `_try_attach_user_id(request)` middleware helper（不查 DB，无效 token 静默忽略）
- **端到端验证** — [scripts/verify_v31_2_2.py](scripts/verify_v31_2_2.py) 12 case 全 PASS（4 analytics regex + 4 user 维度隔离 + 4 真实 HTTP）

## [2026-06-25] v31.2.1 rate-limit 边界强化（XFF 空 IP 兜底 + auth/analytics 嵌套防御）

### 🛡️ v31.2.1 补丁：2 个非阻塞 follow-up 顺手做掉

- **触发** — v31.2 (commit `c2c5066e`) 引入 IP 维度限流 + `/analytics` 豁免 + 可选 auth。端到端 4 边界实测（16 场景全 PASS）发现 2 个非阻塞 follow-up
- **commit** — `fix(v31.2.1): rate-limit 边界强化 (XFF 空 IP 兜底 + /auth/analytics 嵌套防御)`
- **Bug 1 修复** — `app/core/rate_limit.py:156 get_client_ip` 加空 IP 兜底（XFF `", 1.2.3.4"` / `"   "` / `",,,,,"` 全部 → `"unknown"`），防绕过 Nginx 攻击者用空 XFF 共享 200/min 配额 + 7 行 docstring
- **Bug 2 修复** — `app/core/rate_limit.py:72` `/analytics` 分支前置守卫 `not path.startswith("/api/v1/auth/")`，防未来加 `/api/v1/auth/analytics/...` 嵌套路径绕过 `/auth/` 敏感端点 20/min 限流
- **不破坏现有行为** — 4 个现有 analytics 端点（POST search-event / PATCH click / GET stats / GET logs）+ 5 个 auth sensitive 端点 + /auth/me unlimited 全部保留
- **新增 probe 脚本** — [scripts/verify_v31_2_1_xff_empty.py](scripts/verify_v31_2_1_xff_empty.py) + [scripts/verify_v31_2_1_nested_path.py](scripts/verify_v31_2_1_nested_path.py)（纯函数 mock，11 case 全 PASS）
- **2 条新铁律沉淀** — [CLAUDE.md](CLAUDE.md) 新增 "2026-06-25 v31.2.1 rate-limit 边界强化" section：XFF 空 IP 兜底 + substring 路径匹配嵌套排除
- **方案对比** — Bug 2 选 B1（前置守卫）vs B2（后置守卫）vs B3（改精确列表）：B1 改动最小（1 行 if）+ 扩展性最优（未来加 `/api/v1/dashboard/analytics/...` 仍可走原 `/analytics` 分支）+ 不破坏现有行为

## [2026-06-24] sentence-transformers 5.6.0 升级（Phase 1+2 收官，Phase 3 跳过）

### 🎉 P0 升级：跨 3 大版本 ST 升级（29 个月 +）

- **触发** — 原 CLAUDE.md 标"❌ sentence-transformers 升级（未做）"，因 Qwen3 团队用 `include_prompt` 参数 + ST 2.3.1 Pooling 不支持 → 必须用 Qwen3Embedder wrapper 绕开
- **commit** — `c8d4df3e feat(embedding): upgrade sentence-transformers 2.3.1 → 5.6.0 (Phase 1+2 收官)`（已 push main）
- **Phase 1（最小风险）** — `requirements.txt` 升 `sentence-transformers==5.6.0` + 修 1 行 deprecation（`get_sentence_embedding_dimension()` → `get_embedding_dimension()`）
- **Phase 2（用新功能）** — 删 `qwen_embedder.py` (170 行) → 改名 `qwen_embedder_legacy.py` (DEPRECATED 注释保留作 graceful degradation) + `embedding_service.py` 重构为单 ST 路径
- **Phase 3（性能优化）** — 实测 **ONNX 在 GPU 上慢 12-22x**（反优化）→ 主动跳过，保持 torch/GPU
- **关键修复** — Dockerfile 切 PyPI 官方源（清华源限速 torch 2.12+，需 clash 代理 build-arg）
- **收益（vs 原 plan 预估）**：
  - Qwen3 max_seq_length 2048 → **32768** (4x)
  - 删 170 行 wrapper（计划估 130）
  - 单 ST 路径 = 少 bug 表面
  - **0 embedding 错误**
  - qa-bench 50 题：**38% → 42%**（反升 4%，超预期）
- **6 大铁律沉淀** — [CLAUDE.md](CLAUDE.md) 新增 "2026-06-24 sentence-transformers 5.6.0 升级" section：
  - 清华源限速 → PyPI 官方 + clash build-arg
  - docker build env var 污染 → 用 `--build-arg`
  - **ONNX 在 GPU 反优化**（实测数据：torch/GPU 30ms vs onnx/GPU 680ms）
  - ST 跨大版本 3 phase 收官法
  - ST 5.6.0 Pooling `include_prompt` 参数 → Qwen3 native loading 可行
  - Qwen3 native vs wrapper cos 0.999860（实质相同）
- **新文档** — [docs/upgrade-sentence-transformers-plan.md](docs/upgrade-sentence-transformers-plan.md)（完整 plan + 实测结果）
- **新测试** — [tests/test_st5_compat.py](tests/test_st5_compat.py)（8 个 ST 5.6 集成测试，需 `RUN_INTEGRATION=1` 跑）

### 📚 CLAUDE.md 5 大新铁律沉淀（commit `468c2b86`）

- 清华源（pypi.tuna）限速 PyTorch 2.12+ → PyPI 官方 + clash 代理 build-arg
- docker build env var 污染 → 用 `--build-arg` 而非 `ENV`
- ONNX backend 在 GPU 上是反优化（12-22x 慢），不是"2-3x 通用加速"
- ST 跨大版本升级 3 phase 收官法（Phase 1 最小风险 → Phase 2 用新功能 → Phase 3 性能优化）
- ST 5.6.0 Pooling `include_prompt` 参数 → Qwen3 native loading 可行

## [2026-06-24] v29 Qwen3 全量迁移收官（step 3 原子切换）

### 🎉 v29 step 3：embedding 列原子切换（commit `5db74ff3`）

- **背景** — v29 三步走把 embedding 模型从 text2vec-base-chinese (768d) 切换到 Qwen3-Embedding-0.6B (1024d)
- **step 1**（commit `ac29356c`）— GPU 启用 + device 自动检测
- **step 2**（commit `65e612f4` + `641f9cd1`）— Qwen3 wrapper + 双模型 dispatch + alembic 030 双列 + 重算 350/351 条知识
- **step 3**（commit `5db74ff3`）— 原子切换：drop `embedding_v2` 列 + rename `embedding_v2` → `embedding`
- **意义** — 知识库 embedding 全部从 text2vec 升到 Qwen3 1024d，为 ST 5.6.0 升级铺路（同一 session 接着做）

## [2026-06-20~23] v28 论文图片结构化字段 + paper reader 打磨

### 🎉 v28 主体 8 phases 100% 完成

- **Phase 1** — alembic 028 + model + multimodal 集成（12 列 + 2 索引）
- **Phase 2** — schema + API `_to_dict` 加 12 字段
- **Phase 3** — paperAdapter 简化为读后端字段（graceful degradation 保留）
- **Phase 4** — 4 篇 PDF 真实测试验证（37 张图 100% 核心不变量）
- **Phase 5** — 内嵌图 confidence ≥ 0.85 阈值
- **Phase 6** — RightImageRail sectionHint 精准推荐（核心词交集匹配）
- **Phase 7** — IO Hysteresis + rAF 节流（防跳变 + 性能）
- **Phase 8** — article 9 字 bug 修复（深坑：INTERNAL_MARKER_RES line 105 `\bPAGE\s*[:：]\s*\d+\b` 在 `[` 和 word char 之间构边界 → 误删 `[PAGE:N]` → pageMarkers=0 → sections 解析丢分页 → 正文压成 1 段）

### 🛠 v28 step 109.x 持续打磨（40+ commits，2026-06-21~22）

- step 109.30-109.41 paper reader 微调（abstract 提取 / author regex / heading 智能识别 / chemFormat radical 字符集扩展等）
- 最新：`b8d94d4c fix(paper): v28 step 109.41 paragraph 形式子节标题智能识别为 heading`
- **状态**：打磨线**暂停在 109.41**（如无新需求无需继续）

## [2026-06-19] 声纹识别核心修复 + 会议发言人重处理流程标准化

### 🐛 P0 修复：声纹 batch bug 推到主路径（影响所有会议）

- **ERes2Net 不支持 batch** — `modelscope ERes2Net_aug.py:__extract_feature` 强制 `unsqueeze(0)` 折叠 batch。**所有会议**通过 `post_meeting_tasks.py` 的 `vp_service.batch_extract_embeddings()` 都只处理了 batch 第 1 段（89/2830 段有效，97% 沉默失败）
- **修复** — [`app/services/voiceprint_service.py:batch_extract_embeddings`](app/services/voiceprint_service.py) 改用 `ThreadPoolExecutor(8)` + `threading.Lock` 并行单条调用
- **效果** — 50/50 → 100/100 段有效（之前 3%），**所有未来会议自动获得正确识别效果，无需手动重跑**
- **影响范围** — `post_meeting_tasks.py`（录音 hangup 后自动跑的全流程）和 `scripts/reprocess_meeting.py` 都受益
- **铁律** — 上游库 `modelscope` 不会修这个 batch bug（2026-06-19 验证），必须 app 层绕开

### 🛠 会议发言人重处理流程标准化

- **场景** — 老会议用旧版 `batch_extract_embeddings` 处理时 97% 显示"发言人?"，新录入了声纹的成员重跑识别
- **沉淀 9 步 CLI** — [`scripts/reprocess_meeting.py`](scripts/reprocess_meeting.py) (load → extract → cluster → vote → assign → backup → apply → regen → verify)
- **主机端 wrapper** — [`scripts/run-reprocess.ps1`](scripts/run-reprocess.ps1) (PowerShell) + [`scripts/run-reprocess.bat`](scripts/run-reprocess.bat) (cmd.exe) 自动 docker cp + exec
- **关键 bug 修复 3** —
  1. **ERes2Net 不支持 batch** — ThreadPoolExecutor + Lock 修复（已推到主路径）
  2. **SQLAlchemy 静默忽略未映射属性** — 备份改用**文件** `/tmp/meeting_<id>_backup_*.json`，避免"已备份"谎言
  3. **verify 误报人名提及** — 只检查 `【错标名】` 前缀，不检正文
- **会议 #120 实测** — 3252 段"发言人?" → 4 个真实发言人（王天志 1845 / 杜同贺 358 / 宋洋 335 / 贾琦 292）+ 8 字段全 0 旧错标人
- **文档** — [docs/reprocess-meeting.md](docs/reprocess-meeting.md) + [memory/reprocess-meeting-pattern.md](memory/reprocess-meeting-pattern.md) + CLAUDE.md 新增 11 条铁律

### ✅ 主路径修复后第二次重跑验证（2026-06-19 14:40）

修复推到主路径后，再用 `reprocess_meeting.py` 完整跑一次会议 #120：

| 指标 | 第一次（修复前手动） | 第二次（修复后主路径） | 一致 |
|---|---|---|---|
| n_segments | 3357 | 3357 | ✅ |
| n_valid_embs | 2830/2830 | 2830/2830 | ✅ |
| n_clusters | 4 | 4 | ✅ |
| silhouette | 0.184 | 0.184 | ✅ |
| 聚类 0 | 宋洋 (294 votes, conf=0.419) | 宋洋 (294 votes, conf=0.419) | ✅ |
| 聚类 1 | 杜同贺 (263 votes, conf=0.374) | 杜同贺 (263 votes, conf=0.374) | ✅ |
| 聚类 2 | 贾琦 (287 votes, conf=0.538) | 贾琦 (287 votes, conf=0.538) | ✅ |
| 聚类 3 | 王天志 (1094 votes, conf=0.394) | 王天志 (1094 votes, conf=0.394) | ✅ |
| **new_speaker 数组** | 3357 段 | 3357 段 | ✅ **100% 一致** |
| 8 字段 verify | 全 0 旧错标人 | 全 0 旧错标人 | ✅ |

**结论**：修复后 `batch_extract_embeddings` 与手工 ThreadPoolExecutor 行为**完全一致**，证明主路径修复正确。所有未来会议通过 `post_meeting_tasks.py` 自动跑全流程时，无需手动 re-process 即可获得 100% 段有效 + 正确聚类。

- 工具脚本：[scripts/compare_reprocess.py](scripts/compare_reprocess.py) — 前后对比验证脚本

### 一键使用

```powershell
# 完整流程（声纹 + DB + 纪要 + verify）
powershell scripts/run-reprocess.ps1 -Meeting 120 -AudioPath "C:\Users\pc\Desktop\实验相关工作安排.m4a"

# 单独 verify
powershell scripts/run-reprocess.ps1 -Meeting 120 -Steps verify
```

---

## [2026-06-19] 全量审计 + CardList slot 修复 + 开始听会不再建任务

- **🛠 全量审计 + 修复 + 测试**（commits `b843ad86`/`9218ac44`/`433997de`/`4f4f4ce7`）— 4 个 commit 修复 5 处 P0 必修 + 9 处 P1 死代码 + 13 个孤儿文件 + 新增 3 个移动端 view + 17 个单元测试
- **🐛 CardList #item-actions slot 静默丢失**（commit `b843ad86`）— 5 个移动端 view 依赖 `#item-actions` slot 但 CardList 只支持 `item-{id}` 动态 slot，Vue 静默丢弃。修复：[CardList.vue](web/src/components/mobile/CardList.vue) 加 `<slot name="item-actions" :item :idx />`。**用户原报"找不到声纹录入入口"根因**
- **🔧 修开始听会不再自动建任务**（commit `ca3047b7`）— 加 `ENABLE_AUTO_TASK_FROM_MEETING=False` settings 开关，3 处 `_auto_create_task_from_meeting` 调用点全部加守卫。决策/行动项仍记录到 `meeting.decisions` / `meeting.key_points`，user 手动决定是否建任务

---

## [Unreleased] - 2026-06-17 部署与基础设施重建

### 修复

- **🐳 Docker Desktop 引擎崩溃循环** — 根因：WSL2 `docker-desktop-data` 发行版丢失，导致 `com.docker.service` 每 7-9 分钟反复启停。修复：删除 C 盘 24GB Docker 缓存（已备份），让 Docker Desktop 自动重建发行版。详见 [`memory/docker-desktop-fix-2026-06-17.md`](memory/docker-desktop-fix-2026-06-17.md)
- **📦 Docker 镜像源 404** — 多个 Dockerfile 使用 `mirrors.huaweicloud.com/debian bookworm-security`（Debian 已迁出该路径），改用 `mirrors.aliyun.com/debian-security bookworm-security`（路径正确支持）
- **🐢 PyPI 镜像限速** — aliyun PyPI 限速 ~600KB/s，下 torch 532MB 装 13 分钟；改用清华源（10-14 MB/s 稳定）
- **🔌 frp 客户端未自动启动** — 用 `Register-ScheduledTask` 注册 Windows 计划任务 `FRPClient`（用户级登录触发），调用 `start-frpc.ps1` wrapper 启动 `frpc.exe`

### 优化

- **💾 Docker 数据全量迁移 E 盘** — `C:\Users\pc\AppData\Local\Docker` 24GB → `E:\DockerData\appdata`（junction 透明重定向，C 盘 0 字节占用）
- **⚡ Dockerfile 构建优化** — 新建 `.dockerignore` 排除 `models/` `data/` `logs/` `.git/` `.agents/` `docs/`，build context 从 12GB 降到 700MB（17 倍提速）
- **🐳 Whisper Dockerfile 加 fallback** — apt-get install 第一个包失败时自动重试（解决 aliyun `libcaca0` 502 Bad Gateway 瞬时错误）
- **🔐 Git 身份 + SSH 准备** — 配置 `user.name=gg320324492-lgtm`、`user.email=gg320324492@users.noreply.github.com`，准备 push 到 `git@github.com:gg320324492-lgtm/microbubble-agent.git`

### 部署状态

- ✅ 9 个 Docker 服务运行中：app、db、redis、minio、neo4j、whisper、vision-mcp、celery-worker、celery-beat
- ✅ `https://agent.mnb-lab.cn` 端到端连通（之前 502 Bad Gateway，现在 401 = 端点通了，密码错）
- ✅ whisper `faster-whisper==1.2.1` large-v3 模型加载完成，CUDA 库就绪（RTX 5090 32GB）

### 清理

- 删除 24GB C 盘 Docker 缓存副本 `E:\DockerData\appdata-cache-c\`
- 删除 168GB 孤儿 `docker_data.vhdx`（旧 docker-desktop-data 发行版数据，已无引用）
- 删除 frp 冗余文件：`frps.toml`（服务端配置，本地用不到）、`run-frpc.bat`（旧 wrapper）、`frpc-stderr.log`
- 删除 Docker 镜像 `ubuntu:latest`（160MB，未使用）
- **共释放 ~192 GB**

### 铁律沉淀（[memory/docker-desktop-fix-2026-06-17.md](memory/docker-desktop-fix-2026-06-17.md)）

1. **junction 透明重定向** — C 盘软件硬编码路径，删原目录 + `mklink /J` 创建 junction 是 Windows 上让应用"运行在 E 盘"的标准做法
2. **WSL 发行版丢失检测** — `wsl -l -v` 看发行版列表，缺 `docker-desktop-data` 就需要清缓存重建
3. **Dockerfile 镜像源选择** — Debian bookworm-security 走 `debian-security/` 独立路径，不在 `debian/` 下
4. **pip 限速真相** — 国内镜像对单连接限速 600KB/s，下大文件必断。清华 TUNA 前 12 秒 14MB/s 后会降到 320KB/s。**最佳方案是装 PyTorch 官方 wheel 源 + pip 重试**（本项目最后回到清华源 + `--retries 10` 也成功）
5. **build context 必加 .dockerignore** — 任何含大目录（models/data/logs）的项目必须先写 .dockerignore，否则 build context 几十 GB

---

## [2026-06-18] 三连环修复 + 限流误伤复盘（7 commits）

### 修复

- **🐛 EP `useOrderedChildren.removeChild` null 崩溃**（commit `f8d27015`）— Element Plus tab/table pane 卸载时 `nodesMap.get(parentNode)` 返 undefined → `childNodes.indexOf(childNode)` 报 `Cannot read properties of undefined (reading 'indexOf')`。修复：`web/vite.config.js` 新增 `epUnregisterPaneNullPatchPlugin`，transform 阶段 patch EP 源码，与现有 `vueBumNullPatchPlugin` 同模式。触发页：AgentTracesView（19 el-table）/ TaskTrash（18）/ MeetingDetailView（el-tabs lazy）/ KnowledgeView（4 tab lazy）/ SpeakerMappingPanel（8）/ VoiceprintEnrollDialog
- **🎤 桌面"正在听会"指示器不接进度**（commit `f099e7e5`）— 桌面端 MeetingView 用 el-dialog 嵌套 MeetingRoom，与移动端 MobileMeetingRoom 全屏页 UX 不一致。修复：新建 `web/src/views/MeetingRoomView.vue`（218 行），桌面化镜像 MobileMeetingRoom（el-page-header 顶栏 + el-dialog 帮助），router `meetings/room` fallback 改用 MeetingRoomView，MeetingView.resumeRecording 改 navigate
- **🔌 `/auth/me` 限流 20/min → 200/min**（commit `a1fd8280`）— `app/core/rate_limit.py` 把 /auth/me 从 auth tier 移到 read tier。`/auth/` 下细分：白名单敏感路径（login/refresh/change-password 等）保留 20/min，写操作走 write 30/min，其他只读走 read 200/min
- **🔄 MeetingView.onMounted 重复 router.replace 覆盖**（commit `defb08e1`）— `resumeRecording()` 跳 `/meetings/room` 后，紧接着的 `router.replace({ path: '/meetings' })` 立即覆盖，导致 URL 永远停在 /meetings + 不断重渲。修复：删第二行
- **🐛 MeetingRoomView 模板 `.value` 反模式**（commit `9f11d97a`）— Vue 3 `<script setup>` 里 `.value`，但 template 里 Vue 自动 unwrap ref，写 `.value` 等于 `null.value` TypeError。修复：模板去掉 `.value`
- **🔓 `/auth/me` 完全豁免限流**（commit `22f5a7d7`）— 即便 200/min 也被 useUserStore 高频 polling 触发 429。修复：`_AUTH_UNLIMITED_PATHS = {"/api/v1/auth/me"}`，middleware 看到 "unlimited" tier 直接跳过

### 部署链路事故（详见 [memory/incident-2026-06-18-deploy-chain.md](memory/incident-2026-06-18-deploy-chain.md)）

- **本地 commit 后忘 push，误判 webhook 链断** — 服务器 git log 停在 `c1b969dd`、dist 无 MeetingRoomView chunk，初看像 webhook 断（CLAUDE.md 2026-06-17 教训复发）。**真根因**：本地 `git commit` 后没 `git push`，GitHub 端一直停在 `c1b969dd`。修复：补 push 后 webhook 5 秒内触发，服务器 HEAD 变 `f099e7e5` + `f8d27015`

### 铁律沉淀（详见 CLAUDE.md "2026-06-18 三连环修复"）

1. **`commit + push` 后必 `git log origin/main -3` 验证** — 缺这一步 = 服务器 deploy 永远拿不到新代码，症状与 webhook 断 100% 一样，浪费排查时间
2. **怀疑 webhook 断时第一步看 origin/main** — 服务器 `sudo git fetch origin main && git log origin/main -5`，区分"本地没 push"vs"webhook 链断"
3. **`/auth/` 路径按 path+method 细分限流** — 不能 `/auth/` 前缀一刀切，按"是否会被高频轮询"分类而非"是否敏感"
4. **高频只读端点完全豁免** — Vue reactive + WS 心跳 + 路由 prefetch 频次远超产品逻辑假设
5. **template 里 ref 永远不写 `.value`** — Vue 自动 unwrap，script 用 ref.value，template 用 ref
6. **router 操作一次只一个** — `router.replace/push` 后不要再紧接第二个，会被覆盖
7. **docker compose v1/v2 服务器不互通** — 服务器装的是 docker-compose 独立二进制（v1），必须 `sudo docker-compose`，不是 `docker compose`

### 文件变更

- 新增 `web/src/views/MeetingRoomView.vue`（桌面听会房间全屏页，218 行）
- 修改 `web/vite.config.js`（+epUnregisterPaneNullPatchPlugin）
- 修改 `web/src/router/index.js`（meetings/room fallback 改 MeetingRoomView）
- 修改 `web/src/views/MeetingView.vue`（resumeRecording 改 navigate + 删重复 router.replace）
- 修改 `app/core/rate_limit.py`（/auth/me 细分 + 完全豁免）
- 新增 `memory/incident-2026-06-18-deploy-chain.md`（部署链路事故笔记）

---

## [2026-06-15] 任务提醒 v2 + 会议 #95 声纹重置

- **🔔 主动提醒调度器补 11AM 窗口守卫 + highlight.js plaintext fallback**（3 commits `c18b01e8` + `d0ddf49e` + `09e4548d`）— 修复凌晨 2:48 仍收"分配已超过24小时"提醒根因
- **🎤 会议 #95 声纹重置 + 重识别全链路**（2 commits `af044bfc` + `3bcc8c20`）— speaker_mapping 严重错标 80 段，完整清理 8 个 JSON 字段
- **🎤 移动端声纹识别测试真全链路改造**（5 commits）— 解决"声纹测试显示开发中"+"点击没反应"

详见 ROADMAP.md 同日条目 + CLAUDE.md 第 11-15 行块。

---

## [2026-06-14] Agent 单阶段流式架构 + 质量优化

- **🚀 方案 C：Agent 单阶段流式渐进综合架构**（12 commits 完整链路 `5ce1203`→`48ac8dc`）— 取消 brief/detail 双层，用户问"请教谁"类问题直接推荐 3 人 + 理由
- **🤖 Agent 回答质量 5 大修复**（14 commits）— TOOL_REGISTRY 未注册 / LLM 代理不转发 tools / 长期记忆干扰 / synthesis 阶段 fake XML 泄露
- **🧪 qa-bench 360 题闭环** — 知识库 64→247 条（+183 条 / +286%）

---

## [2026-06-13] 移动端 PWA 收官

- **📱 移动端 PWA 收官**（10 个 PR）— NutUI 4 + Element Plus 路由级双栈架构，18 个移动端页面 + 12 个移动端组件 + 4 个 PWA 离线策略
- **🛡️ Service Worker 升级机制** — `SW_VERSION v4→v5` 强制升级路径
- **🎨 webhint a11y img alt 警告**（5 处修复）— theme-color Firefox 不支持是浏览器限制
- **🐛 端到端实测修复 5 bug**（commit `5f01cac`）— agentic_loop await/async for / mimo-v2.5 thinking / TraceCollector None / CancelledError / Celery 守卫

---

## [2026-06-12] 会议录音全栈防御

- **🎙️ 会议录音全栈防御机制 5 阶段** — 解决 #84 案例"58 分钟录音断网丢失"
- **🌐 webhint paint keyframes 治理**（49+ 报告清零）
- **🐛 会议详情页 transcriptEntries / polish-text 400 双 bug 修复**
- **🔧 Vite hash 改 hex 真正消除 cache-busting 误报**
- **🐛 会议查询 bug 双层根因修复**（`app/agent/core.py:911` UnboundLocalError + LLM 撒谎模式）

---

## [2026-06-03] 垃圾桶系统 + 性能优化

- **🗑️ 垃圾桶系统 4 bug 全修**（commit `dc93bff`）— 精准倒计时双行显示
- **⏰ beat 调度 1h**（commit `47fb2c9`）
- **⚡ Webhook 性能 0.001s 响应**（commit `7ec6ce0`）

---

# 📋 简洁版更新日志（UI 91 条记录同步）

> **用途** — 给项目内"更新日志"UI 模块（"91 条记录"展示页）使用。CHANGELOG.md 上半部分（详细版）保留给工程团队，**这份是 UI 同步用的简短版本**。
> **格式** — 日期 / 主标题 / 类别（功能/优化/修复）/ 一句话描述
> **同步方式** — 任何新 commit 必须同步追加一份到下面 + 实时更新

## 2026-06-27

- **v76.6 智能对话框全元素跟随主题色** / `6d314f2a` / 修复 — 修 3 类硬编码橙色残留（EP `--el-color-primary` 映射 + ChatViewSSE 5 渐变 + SessionSidebar rgba → CSS 变量）
- **v76 follow-up CI + 视觉回归基建 4 commit** / `d0f2f212` `e92b571c` `f08e1858` `e3c3c423` / 优化 — paths filter 扩 3 路径 + lockfile 同步 + 删 baseline png + workflow_dispatch update-snapshots 模式
- **v31.3.2 polish-text 批量端点** / `9e51365e` / 修复 — 修 83 段会议并发触发 write tier 30/min 限流（HTTP 请求 1/N）
- **v76.2 视觉回归测试 5 件套收官** / `f19cb780` / 功能 — Playwright baseline + ci-mode + max-increase + 组件级 CSS 测试
- **v76 PWA manifest test 拆分** / `a2a11505` / 修复 — 拆出 visual-regression spec 独立跑避免被主 spec 阻断
- **v75 测试稳定性** / `ee46c34a` / 优化 — 9 个旧 fail 修复 + PR annotation + token orphan pre-commit 拦截
- **v74 CSS variable 6 主题组合自动化测试** / `0f77bc29` / 功能 — CI hard fail + token 白名单
- **v73 fallback 政策章节补全 + font-mono token** / `1707c660` `d8ae2a2f` / 修复 — CSS fallback 变量写法规范化 + 新增 `--font-mono`
- **v72 P1 摘要+重点摘要合并** / `eed0c409` / 功能 — 主题色 TL;DR 卡显示摘要段落（`color-mix()` 自适应 6 主题）
- **v72 stylelint 139 → 0 清理** / `b3c1e242` / 优化 — 清 99 个 `:deep()` + 31 个 `word-break: break-word`
- **v71 P1 议程 timeline + 每 speaker 8 条常驻** / `46c85892` / 功能 — `el-timeline` 金橙圆 dot + per-card 展开全部
- **v71 stylelint 322 → 0 清理** / `c053bf25` / 优化 — color-named `white` 88 → 0 + 其他
- **v70 P0~P3 字面色 → token** / `e4b2eec3` `6d192718` `5ea74dd5` `f6a2bc3d` `bd41497e` / 功能 — ~340 处 hex 替换为 `var(--color-*)` token，dark mode 全面修复
- **v70 P3 预防机制** / `7ee757cf` / 功能 — Stylelint 字面色禁用 + docs/color-tokens.md
- **v70 P0 SW_VERSION 注释块误删修复** / `a2fd63a9` / 修复 — 补回 `const SW_VERSION` 修 SW ReferenceError 白屏
- **v70 P2 漏 commit dist 兜底** / `ef5db3b6` / 修复 — 服务器 dist 404 兜底
- **v70 polish-text Redis + 转录 tab 加速** / `5914a563` `9986eb67` / 优化 — Redis 缓存 + 删 LLM polish + 换 popover

## 2026-06-26

- **pre-commit hook auto-add web/dist/** / `6565415a` / 功能 — CLAUDE.md 教训第 4 次沉淀后自动兜底
- **v69 P0+P1 dark mode 3 阶段** / `71bb394a` `55865fe2` `7e0976d8` / 功能 — 5 tokens + 14 EP + 6 主题切换 + 10 桌面视图 dark 适配
- **v69 P1b fix 系列** / `ea663c3b` `20fa2efa` `7b5ecd37` / 修复 — el-dialog/chat-immersive/memory-card/公式面板/项目详情等白边清理
- **5 组件深度优化** / `6ac05b28` / 优化 — 会议 #135 韩/张 识别率 0% → 80%
- **会议 #135 修复** / `519a2ab2` `cd73ba7f` / 修复 — 标题自动生成 + 头部头像 + 发言统计 tab 自动填充
- **知识图谱路由顺序** / `a422972b` / 修复 — entities/graph 必须在 `/{knowledge_id}/graph` 之前注册（修 422）
- **v68 桌面主题切换按钮** / `2cb2287e` / 功能 — 顶栏挂主题切换 + SettingsView 玻璃态
- **v31.3.1 whisper 容器 bind mount** / `3f9411cb` / 修复 — 删 Dockerfile COPY + bind mount 源码（本地改 restart 即生效）
- **v31.3 whisper 模型常驻 GPU** / `93de5151` / 优化 — 8GB 常驻 + flash_attention 准备（Blackwell sm_120 暂不支持）
- **v31.3.1 flash_attention 注释更新** / `baecd6be` / 修复 — 实测 ctranslate2 4.8 仍不支持 Blackwell
- **v31.2.5 启用 AsyncRedisRateLimiter** / `0ea97c95` / 修复 — 抗 `docker compose restart` 清零
- **v31.2.4 Redis ZSET 持久化 + per-user dashboard** / `c1046b41` / 功能 — AsyncRedisRateLimiter 类 + 中文乱码修复
- **部署与基础设施重建** / 多 commit / 修复 — Docker Desktop 引擎崩溃 + 镜像源治理 + 数据 E 盘化 + frp AtLogOn

## 2026-06-25

- **v31.2.3 rate-limit 基建收尾** / `8bdb36fc` / 功能 — X-RateLimit-Policy 头 + SSE tier + auth prefix 匹配
- **v31.2.2 analytics regex + user_id 维度** / `c617f8e9` / 优化 — substring→regex 永久化 + middleware 注入 user_id
- **v31.2.1 XFF 空 IP 兜底 + /auth/analytics 嵌套防御** / `e40ad6a7` / 修复 — 2 个非阻塞 follow-up

## 2026-06-24

- **sentence-transformers 5.6.0 升级** / `c8d4df3e` / 功能 — ST 2.3.1→5.6.0 + 删 170 行 Qwen3 wrapper + Qwen3 max_seq_length 4x→32K + qa-bench 38%→42%
- **CLAUDE.md 5 大铁律** / `468c2b86` / 优化 — ST 5.6 升级踩坑经验沉淀
- **v29 step 3 原子切换** / `5db74ff3` / 功能 — drop + rename embedding_v2 → embedding
- **v29 step 2 收官** / `641f9cd1` / 功能 — alembic 030 + ORM 双列 + 重算 350/351 条知识
- **v29 step 2 Qwen3 wrapper** / `65e612f4` / 功能 — Qwen3-Embedding-0.6B 1024d wrapper + 双模型 dispatch（后来被 ST 5.6 替代）
- **v29 step 1 GPU 启用** / `ac29356c` / 优化 — device 自动检测
- **v30 A/B 评估** / `284fffc7` / 优化 — Qwen3 vs text2vec（Recall@10 +7.9%）

## 2026-06-20~23

- **v28 论文图片结构化 8 phases 100% 完成** / `db7538ec` `817a69c3` / 功能 — 12 字段 + 2 索引 + paperAdapter 简化 + IO Hysteresis + confidence 阈值
- **v28 step 109.x paper reader 微调** / `b8d94d4c` 等 / 优化 — 40+ commits 打磨（abstract 提取 / heading 智能识别 / chemFormat radical 字符集）
- **v27 智能论文阅读器底层重构** / `59d93b90` / 功能 — 保护区机制 + 中文过滤 + 右侧图表栏 + 默认不内嵌
- **v26+v26.1 论文阅读器回归修复** / `2ee27015` `a7398d5c` / 修复 — chemFormat Unicode 化 + _escapeHtml 二次转义 + 正则 `{0,N}?`+`|$` 贪婪陷阱
- **v25 论文阅读器 v25** / `982ac584` / 功能 — 化学式/智能图/图谱适配/翻译

## 2026-06-19

- **声纹 batch bug 推到主路径** / `52fa51a6` / 修复 — ERes2Net 强制 batch=1 → ThreadPoolExecutor + Lock 修复（97% 沉默失败 → 100%）
- **会议发言人重处理流程标准化** / `reprocess_meeting.py` / 功能 — 9 步 CLI + 文件备份 + 主机端 wrapper + 11 条铁律
- **主路径修复后第二次重跑验证 100% 幂等** / 验证 — 4 个聚类名字/votes/conf 全部位级相同
- **全量审计 + CardList slot 修复** / `b843ad86` 等 / 修复 — 5 处 P0 + 9 处 P1 死代码 + 13 个孤儿文件 + 17 个测试
- **开始听会不再自动建任务** / `ca3047b7` / 修复 — `ENABLE_AUTO_TASK_FROM_MEETING=False` 开关

## 2026-06-18

- **三连环修复 7 commits** / `f8d27015` `f099e7e5` `a1fd8280` `defb08e1` `9f11d97a` `22f5a7d7` / 修复 — EP unregisterPane null + MeetingRoomView 全屏 + /auth/me 完全豁免 + router.replace 覆盖 + template `.value` 反模式
- **部署链路事故复盘** / `incident-2026-06-18-deploy-chain.md` / 修复 — 本地 commit 忘 push 误判 webhook 断

## 2026-06-17

- **Docker Desktop 引擎崩溃 + 镜像源治理 + 数据 E 盘化** / 多 commit / 修复 — WSL docker-desktop-data 重建 + junction 透明重定向 + aliyun 正确路径 + 清华 pip 重试 + .dockerignore 17 倍提速
- **webhook deploy 链断裂** / 多 commit / 修复 — 重新生成 ed25519 + GitHub deploy key + .env.webhook 持久化

## 2026-06-15

- **任务提醒体系 v2** / `223ea74` `ba75e32` / 功能 — 11AM 窗口推送 + 1-per-task + 任何消息 ack 取消
- **主动提醒调度器 11AM 窗口守卫** / `c18b01e8` `d0ddf49e` `09e4548d` / 修复 — v2 漏修补救（凌晨 2:48 仍推送根因）
- **会议 #95 声纹重置 + 重识别** / `af044bfc` `3bcc8c20` / 修复 — speaker_mapping 严重错标 80 段清理
- **移动端声纹识别测试真全链路** / 5 commits / 修复 — "开发中" toast + 点击没反应
- **Agent 质量 5 大修复** / 14 commits / 优化 — TOOL_REGISTRY 未注册 / LLM 代理不转发 tools / 长期记忆干扰 / synthesis 阶段 fake XML 泄露
- **qa-bench 360 题闭环** / 多 commit / 优化 — 知识库 64→247 条 (+183)
- **LLM 元话语/thinking 文本泄露修复** / 多 commit / 修复 — prompts 硬规则 + 后端 `_strip_meta_thinking` 兜底
- **Rich Block 统一包装** / `ba75e32` / 修复 — 杨慈是谁呀"暂无成员"修复 + notification_preferences 列同步
- **reminders v2 字段缺失 → /api/v1/reminders 500** / `alter_reminders_v2.sql` / 修复 — 6 列补齐

## 2026-06-14

- **方案 C：Agent 单阶段流式渐进综合架构** / 12 commits `5ce1203`→`48ac8dc` / 功能 — 取消 brief/detail 双层，单阶段流式综合

## 2026-06-13

- **移动端 PWA 收官 10 PR** / 9026c07 / 功能 — NutUI 4 + Element Plus 路由级双栈 + 18 页面 + 12 组件 + 4 PWA 策略
- **Service Worker 升级机制** / `747a735` / 优化 — SW_VERSION 强制升级 + postMessage + reload 闭环
- **webhint a11y 5 警告全栈修复** / `08f440f` `c855f0e` / 修复 — webmanifest MIME + manifestHashPlugin + injectRegister:null + 410 Gone
- **Vue 3.5 'bum' null bug Vite plugin patch** / `79305b7` / 修复 — transform 阶段 patch esm-bundler.js
- **Nginx types 指令覆盖整站 octet-stream 事故** / `f148d96` `5c24442` / 修复 — server context types 覆盖 mime.types + sed 注入
- **SW 污染 cache 升级模式** / `747a735` / 修复 — BUMP SW_VERSION + caches.keys() + postMessage reload
- **端到端实测修复 5 bug** / `5f01cac` / 修复 — agentic_loop await/async + mimo-v2.5 thinking + TraceCollector + CancelledError + Celery 守卫
- **edge-tts 6.1.9 TrustedClientToken 过期 → TTS 500** / `41cf204` / 修复 — 升级 7.2.8 + 修 requirements.txt 锁版本
- **vite-plugin-pwa manifest precache 路径不同步** / `6d93d35` / 修复 — closeBundle 时序陷阱
- **SW 图片路由 CacheFirst 缓存 5xx 502** / `707c0f9` / 修复 — CacheableResponsePlugin `{0, 200}` 守卫

## 2026-06-12

- **会议录音全栈防御 5 阶段** / 多 commit / 修复 — IndexedDB 兜底 + chunked 上传 + Celery 真 retry
- **webhint paint keyframes 治理 49+ 报告清零** / 多 commit / 优化 — `transform`→独立 `rotate/scale`
- **会议详情页 transcriptEntries / polish-text 400 双 bug 修复** / 多 commit / 修复 — 字符串聚合过滤空内容
- **Vite hash 改 hex 真正消除 cache-busting 误报** / `vite.config.js` / 优化 — `hashCharacters: 'hex'`
- **会议查询 bug 双层根因修复** / `app/agent/core.py:911` / 修复 — UnboundLocalError + LLM 撒谎模式防御

## 2026-06-03

- **垃圾桶系统 4 bug 全修** / `dc93bff` / 修复 — 精准倒计时双行显示
- **beat 调度 1h** / `47fb2c9` / 优化 — 准点清理
- **Webhook 性能 0.001s 响应** / `7ec6ce0` / 优化 — ThreadingHTTPServer 替换 HTTPServer

---

**同步纪律**：
1. 任何新 commit **必须**在详细版（CHANGELOG.md 上半部分） + 简洁版（这份）**双写**
2. 简洁版条目必须**一行一个**，方便 UI 列表渲染
3. 类别从 `功能`/`优化`/`修复` 三选一（与 UI 显示一致）
4. 一句话描述 ≤ 80 字符（UI 列表项宽度限制）
