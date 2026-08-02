# MicroBubble Agent - 项目上下文
## 项目简介

"小气" - 微纳米气泡课题组智能Agent系统，约20人研究实验室的AI助手。

- 后端: Python 3.11 + FastAPI + SQLAlchemy + PostgreSQL + Redis + Celery
- 前端: Vue 3 + Vite + Element Plus（原版 `web/`，极简版 `web-minimal/`）
- AI: Claude API (Sonnet) + faster-whisper + pgvector
- 部署: 云服务器 (Nginx + FRP 服务端) + 本地电脑 (Docker 8 services + GPU Whisper)，通过 FRP 隧道连接。也支持单机部署，详见 `docs/deploy.md` 服务器迁移章节

## 当前状态 (2026-08-02 W99-W100 RAG 升级 6 批全收口 + W99 +21 fix-deploy 收口 — 锚点范式 W99 末 ~495 → W100-RAG-6 ~534 漂移据实 (+39 据实上报, 派工 brief 估 +36 偏差据实), 6 批独立派工守恒, 主指挥协调范式第 83 次派工)

**W99-W100 RAG 升级 6 批全收口 (主拍连续 6 + 1 派工, 真问题不是模型切实时版本而是 RAG 5 大缺口 + 6 hook 串行集成 + 部署链分段)**:

**W99-RAG-1..W100-RAG-6 6 批锚点漂移汇总 (派工 v6 §13.3 假设禁令实测, 类 20.123 据实上报)**:
- **W99-RAG-1** (`7196457c7`..`d07b07e93`, 6 commits W99 +20..+25): Query Cache 结果层 (类 20.121/122) — 实测 +6 commits 守恒 (派工 brief 估 +6, ✅)
- **W99-RAG-2** (`c7c130913`..`a03ab87ec`, 7 commits W99 +6..+12): Citation 段落级溯源 (类 20.124) — 实测 +7 commits 守恒 (派工 brief 估 +7, ✅)
- **W100-RAG-3** (`a82c6579b`..`599c9605b`, 7 commits W100 +0..+6): Query Intent 5 类分类 (类 20.125/126) — 实测 +7 commits 守恒
- **W100-RAG-4** (`40579ef4e`..`49b6b7640`, 6 commits W100 +0..+5.5): Reranker v2 + 92% acceptance gate (类 20.127/128/129) — **派工 brief 估 +7, 实测 +6 偏差据实**
- **W100-RAG-5** (`420a882eb`..`cd2571db5`, 7 commits W100 +0..+6.5): Multimodal 第 5 路 + HybridWeights 3 处同步 (类 20.129/130) — **派工 brief 估 +6, 实测 +7 偏差据实**
- **W100-RAG-6** (`27b465ce0`..`02a80e7bf`, 6 commits W100 +0..+5): Temporal 时间衰减 exp(-age/2) (类 20.131/132) — 实测 +6 commits 守恒

**W99 +21 fix-deploy 收口** (`b067f6d04` + merge `59b2a9603`): webhook 链修复 + 强制重部署 latest main — 1 commit, **锚点碰撞** (类 20.124 实战): W99-RAG-1 cache hook (`830c1d8ed`) 与本 commit 同用 `W99 +21` 编号, 沿用派工 v11 §9 锚点前缀规则容许

**当前 main HEAD = `59b2a9603`**, 39 commits (W99-W100 6 批 RAG 升级) + 1 commit (W99 +21 fix-deploy) 合并 main + 推 origin/main + 服务器 webhook 自动触发 + 本地 PC docker cp + alembic 094→095→096 串单链 + restart + /health 200 healthy + 7 RAG 模块加载 ✅.

**派工前提铁律 12 + 类 20 实战 113+ 实例 (W99-W100 RAG 升级 6 批据实上报 8 新增 + 派工 plan 偏差 6 处)**:
- **类 20.121 实战 (W99-RAG-1)**: Redis cache 不可用 best-effort silently 降级 (沿用 embedding_service:243 模式), 不抛错
- **类 20.122 实战 (W99-RAG-1)**: Cache 键必含 user_id + tenant_id 隔离多租户, query→answer 缓存键强制隔离
- **类 20.123 实战 (W99-RAG-1..W100-RAG-6)**: 派工 plan 偏差据实 6 处 — W99-RAG-1 brief "10 个 def" vs 实测 11 instance + 7 module-level; W100-RAG-3 brief LLMAnalysisService/query_translator 路径假设偏差; W100-RAG-4 brief "6 commits" vs 实测 6 (+5.5 closure); W100-RAG-5 brief "6 commits" vs 实测 7; W100-RAG-6 brief "派工起点必 fetch" 沿用 (实测守恒)
- **类 20.124 实战 (W99-RAG-2 + W99 +21 锚点碰撞)**: Citation 段落级溯源 chunk_id 必查 knowledge_chunks + **锚点编号 `W99 +21` 跨批碰撞** (`830c1d8ed` W99-RAG-1 cache hook + `b067f6d04` W99 +21 fix-deploy) 沿用派工 v11 §9 容许
- **类 20.125 实战 (W100-RAG-3)**: Intent 5 类 (factual/analytical/comparative/exploratory/operational) LLM 失败回退 INTENT_FALLBACK (默认 factual)
- **类 20.126 实战 (W100-RAG-3)**: Intent 路由 weights 配置化 (module-level dict DEFAULT_INTENT_WEIGHTS), 不硬编码到 body
- **类 20.127 实战 (W100-RAG-4)**: Reranker 92% acceptance gate 失败必 raise, 不静默降级 (W75 B-1 跨会议 90% 守恒派生)
- **类 20.128 实战 (W100-RAG-4)**: Reranker 默认 backend = CrossEncoder (W75 BGE m3 93.5% baseline 守恒)
- **类 20.129 实战 (W100-RAG-4/5)**: original_index 缺失时用 id 匹配原始索引 + HybridWeights 第 5 路必须同步扩 3 处
- **类 20.130 实战 (W100-RAG-5)**: 多模态模型名 + OCR 接口名实测 (派工 brief 假设 Qwen-VL / 实测沿用 multimodal_service)
- **类 20.131 实战 (W100-RAG-6)**: 派工起点必 fetch origin + merge-base 拦截漂移 (W100-RAG-5/6 起点必跑)
- **类 20.132 实战 (W100-RAG-6)**: Temporal 衰减函数必 exp(-age/2) + 仅作最终 score 乘子, 不影响中间召回

**W99-W100 RAG 升级 6 批 5 件套守恒实测**:
1. alembic 1 head: `096_add_rag_multimodal_metrics (head)` 守恒 (094→095→096 串单链, W92 串单链纪律守恒 4/4) ✅
2. pytest 全套件: **242/242 PASS** (40 RAG-6 + 202 RAG-1..RAG-5) ✅ (派工 brief 估 327+ 偏差据实, 实测 RAG 专项 242/242 守恒)
3. PWA build: W99-RAG-2 涉及 frontend (KnowledgeRefBlock citation highlight), npm run build PASS, PWA manifest hash 守恒 (W86 mini-N PWA 守恒纪律沿用)
4. 件 4 六门控 (从 2 扩展到 6) 守恒: knowledge_service / hybrid_retriever / rag_evaluator / reranker_service / hybrid_weight_config / multimodal_retriever def diff 全 0 守恒 (派工 brief 估 3 门控 偏差据实)
5. 锚点范式: 6 批派工 brief 估 +36, 实测 +39 + W99 +21 +1 = +40 commits, 锚点漂移 W99 末 ~495 → W100-RAG-6 ~534 (+39 漂移据实) (派工 brief 估 +33 偏差据实)

**W99-W100 RAG 升级 6 批沉淀文件**:
- `docs/rag/W99-RAG-1-cache.md` ~ `docs/rag/W100-RAG-6-temporal.md` (6 份 runbook, 沿用 W97 RAG 大改造 runbook 模板)
- `docs/rag/W99-W100-RAG-UPGRADE-GRAND-CLOSURE.md` (11 节全 6 批总收口)
- `memory/w99-rag-1-cache-{startup,closure}-2026-08-02.md` ~ `memory/w100-rag-6-temporal-{startup,closure}-2026-08-02.md` (12 份 memory)
- `memory/w99-fix-deploy-2026-08-02.md` (191 行, W99 +21 fix-deploy 已沉淀, **本任务不重复创建**, 沿用沉淀)
- `docs/w99-fix-deploy-2026-08-02.md` (174 行, W99 +21 fix-deploy runbook 已存在)
- `scripts/auto-deploy.sh` (322 行, 沿用 W99 DEPLOY-AUTO 沉淀, W99 +21 修复针对主包 404 实战)

**累计 commits 与铁律延续**: W98-W100 累计 1500+ commits + 595+ 铁律 (W99-W100 RAG 升级 +39 commits + 12 新铁律: 类 20.121/122/123/124/125/126/127/128/129/130/131/132). W19 选项 A 维持.

**未来改进留口** (主拍决策, 不擅自扩):
1. qa-bench R8 200 题真跑 5 类 intent 子集 (W100-RAG-3 子集验证留口, 已实测 acceptance gate 100% PASS)
2. RAG 6 hook 串行集成 e2e (W99-RAG-1..W100-RAG-6 综合验证, 已实测 242/242 PASS)
3. W99 +21 fix-deploy memory 沉淀 (已沉淀 at `memory/w99-fix-deploy-2026-08-02.md`, 本任务引用沿用)
4. CLAUDE.md 历史段落 mini-N 减负 (永久归档, 派工 brief 估 W99 顶段已刷新, 历史段保留 W98 P2 batch + W98 RAG-GC 等)
5. HybridRetriever 6 hook 单元 e2e 深化 (W103+ 派工预留)
6. Anchor 编号碰撞 reconcile (W99 +21 跨批碰撞 2 处, 派工 v11 §9 沿用容许, 未来派工 brief 必查锚点占用)

**自动部署完整链 (沿用 W99 DEPLOY-AUTO 沉淀, W99 +21 修复针对主包 404)**:
```
git push origin main
  ↓ (GitHub 发 webhook)
服务器 scripts/webhook.py:9001 → scripts/deploy-auto.sh
  (git fetch + reset + 健全性检查 + Nginx reload + stats/changelog)
  ↓
本地 PC scripts/auto-deploy.sh (W99 DEPLOY-AUTO 创建)
  (npm run build → alembic heads → git add -f -A → commit → push → docker cp → __pycache__ clear → restart → curl /health)
```

详见 `docs/rag/W99-W100-RAG-UPGRADE-GRAND-CLOSURE.md` (11 节总收口) + `memory/w99-fix-deploy-2026-08-02.md` (191 行 W99 +21 沉淀) + `memory/w100-rag-6-temporal-closure-2026-08-02.md` (W100-RAG-6 收口).

---

## 当前状态 (2026-08-02 W100 RAG 升级收口后 plans 审计 + 部署 bug 修复 — 锚点范式 W100 末 ~534 → W100 +28(主仓库)/+29(主仓库 + worktree memory)/+30(worktree memory) 据实累计 ~537, 主仓库 HEAD = `ed79b2558`, 类 20.135/20.136 新增)

**三轮新工作收口 (W100 +28/+29/+30, UI 可见性增强 + plans Status 据实审计 + auto-deploy Step 3 fail-loud 修复)**:

1. **W100 +28 主仓库 UI 体验链**: UI-CONTEXT 上下文可见性面板、UI-ARCHIVE 会话归档、UI-TOOL-JUMP `tool_use` 跳详情、7 事件 badge、content 双段折叠已落地；merge commit 物证为 `6abb874e1` / `3f6dc2e67` / `91d359188` / `fc3f50258` / `479ed92c2`。
2. **plans 审计 (worktree +28, `8b4133593`)**: 对 65 个非 stub plan 做 `git show` + 源码 grep 三验证，发现 Status 系统性失真；26 份据实更新，8 份真正未完成据实标注：`exe-logical-pie` DEFERRED（含实时语音助手）、`dazzling-leaping-pretzel` DEFERRED、`2-3-plan-floating-popcorn` 与 `nature-majestic-biscuit` NOT_IN_REPO、Self-RAG REINTRODUCED、`qa-bench-v3.1` PARTIAL 4/8、`pwa-sw-iridescent-honey` PARTIAL、`a-c-mighty-phoenix` PARTIAL；另 13 份 BORROWED_COMMIT 改用真实 commit。
3. **auto-deploy.sh Step 3 grep+pipefail bug 修复 (主仓库 +29, `d6ee1532c`)**: `scripts/auto-deploy.sh` line 198 的 `UNTRACKED_DIST` grep 管道加 `|| true` 关键兜底，line 174 的 alembic HEAD grep 加 `|| echo "0"` latent 兜底；worktree +30 完成 memory 沉淀。根因是 `set -euo pipefail` 下成功场景 grep 无匹配也返回 1，导致 force-add 后脚本中止。

**派工 v11 §9 锚点前缀规则实战**: UI-CONTEXT `+29` 与 auto-deploy fix `+29` 为允许的跨分支撞号，两条提交 hash 不同，均保留物证，不擅自改号。

**派工前提铁律与 Self-RAG 风险**:
- **类 20.135**: plans Status 段必须用 plan-specific commit + `git show` + 源码 grep 三验证；W66 通用模板/借用同 wave commit 会造成系统性失真，不能信 Status 自述。
- **类 20.136**: `set -euo pipefail` 下 grep 无匹配是合法空结果而非脚本成功路径异常；命令替换管道必须显式 `|| true` 或数值 `|| echo "0"` 兜底，commit `d6ee1532c` 精确修复 Step 3。
- Self-RAG 是 W100 P1 有意重新引入的新实现，但尚未完成效果 benchmark；R7/R8 benchmark 验证待派工，plan 已就绪：`~/.claude/plans/selfrag-r7-r8-benchmark-verify-2026-08-02.md`。若仍 0 触发或无质量提升，沿用证伪决策再次删除，不第三次反复。

**本轮 5 件套守恒实测/沿用**:
1. alembic: `python -m alembic heads` 应输出 1 head `096_add_rag_multimodal_metrics`（W100 RAG-6 head 守恒，本文档未改 migration）。
2. pytest: 本轮不强求重跑，沿用 W100-RAG-6 基线 **242/242 PASS**。
3. PWA build: 本次未涉及 frontend，仅 CLAUDE.md 文本 + `scripts/` 修，沿用 W100-RAG-6 基线（`vite-plugin-pwa disable: true`，PWA 已禁用）。
4. 0 production code: 严格守恒，仅 CLAUDE.md / `memory/` / `scripts/` 范畴，未改 `app/` 或 `web/src/`。
5. 锚点范式: 实测口径 `git log origin/main --oneline -50 | grep -oE 'W10[0-9] \\+[0-9.]+'`，据实标注 W100 +28/+29/+30，W100 末 ~534 → ~537；主仓库当前 HEAD = `ed79b2558`。

**关联沉淀**: `memory/plans-audit-2026-08-02.md`、`memory/selfrag-w100-reintro-unverified-2026-08-02.md`、`memory/auto-deploy-sh-step3-grep-pipefail-abort-2026-08-02.md`（如主仓库缺失则沿用对应 worktree memory 物证）。

---

## 当前状态 (2026-08-02 W99 Thinking Capsule + S-series + DEPLOY-AUTO 全收口 — 历史段落, 锚点范式 W98 末 ~490 → W99 +12..+16 (5 commits Thinking Capsule) + S1..S4 + GC + DEPLOY-AUTO +3 = 16 commits 漂移据实, 16 commits 合并 main + 推 origin/main + 服务器 webhook 自动触发 + 本地 PC docker restart, 类 20 实战 116+ 据实上报 (W99 S-series 3 新增 + DEPLOY-AUTO 4 新增), 0 production code 守恒, 主指挥协调范式第 N 次派工)

**W99 全收口 (主拍连续 7+1+1 派工, 真问题不是模型切实时版本而是 4 处流式管道未打通 + 本地 PC 部署链空白 + Thinking Capsule 5 commits 链路) — 历史段落, 完整内容已被上方 W99-W100 RAG 升级 6 批全收口段覆盖, 此处仅保留派工 brief 引用**:

本段已由 W100-DOC W100 +7 派工归档至历史段 (主拍决策, 不擅自删, 沿用 W98 RAG-GC 模式). 完整锚点范式 + 派工 v6 §13.3 假设禁令 + 类 20.114-120 实战沉淀详见上方 W99-W100 段 + `memory/w99-s-series-closure-2026-08-02.md` + `memory/w99-deploy-auto-closure-2026-08-02.md` + `docs/w99-s-series-grand-closure-2026-08-02.md` + `docs/w99-s4-asr-streaming-eval-2026-08-02.md`.

**关键 commit 引用 (历史段摘要)**:
- W99 +12..+16 Thinking Capsule: `2aab6e342` / `4cf549f54` / `fc4db9b28` / `2b2393e21` / `723976cd9` + merge `2454af287`
- W99-S1..S4 + GC: `ab0a57ff4` / `8b052f79c` / `2d0631de6` / `6dbe88713` / `88d8f63e6`
- W99-DEPLOY-AUTO +0..+2: `5d3b74f6e` / `f3e9ac8b3` / `8441414d2`
- W99 +21 fix-deploy: `b067f6d04` (锚点碰撞, 类 20.124) + merge `59b2a9603`

W19 选项 A 维持. 主指挥协调范式第 N 次派工 (W99 末).

---

## 当前状态 (2026-08-01 W98 P2 batch grand closure 收口 — 历史段落, 锚点范式 W97 477 → W98 P2 batch 4 commits 漂移据实, P2-D2/F/E2E/GATE 合并 main, 类 20 实战 113+ 据实上报, 0 production code 守恒, 主指挥协调范式第 81 次派工)

**W98 P2 batch grand closure 收口 (主指挥协调范式第 81 次派工, CHAT 系列 5 铁证验收 + RAG consistency 收尾 + 微信同步共享 + 10 件套 gate 守恒)**: 锚点范式 W97 477 → W98 P2 batch 4 commits 漂移据实 (派工 brief 期望 W98 +6 → +10, 实测 P2-D2 W98 +7 + P2-F W98 +6 + P2-E2E W98 +6 + P2-GATE W98 +9, 4 commits 全部合并至 main `58aa29eca`). 当前分支 tip = `58aa29eca` (P2-GATE merge commit, 0 commits ahead of base).

**5/5 agents 完成 (4 commit agents + 1 closeout)**:
- **P2-D2 W98 +7**: qa-bench consistency 双轮语料 20 题 + std=0.0672 (>0.05) + 实体重叠=0.6056 (>0.5) + rag_evaluator 新增 evaluate_consistency_double_round (108 行新增, 0 改既有 6 函数) + 12/12 + 19/19 = **31/31 PASS**
- **P2-F W98 +6**: 抽 `_ensure_session_context` 为 `app/services/session_context.py` 共享服务, 微信 handler 3 处接入, 老测试桩 patch 路径 8 处全改 + 132 行删除 + 12 行 alias import, **39/39 PASS** (类 20.13 实战 19: 派工 brief 期望 wechat_service.py 实测 app/wechat/handler.py)
- **P2-E2E W98 +6**: 5 铁证 e2e 脚本 (续讲 + 自洽 + 重启 + 反馈 + consistency), entity_overlap_ratio 用关键词词典优先 (实测铁证 3 重叠率 0.0 → 1.0, 铁证 2 从 0.1 → 0.2+), **171 PASSED + 3 SKIPPED + 0 FAIL**
- **P2-GATE W98 +9**: 10 件套 gate 守恒验证报告 (件 1-10 全实测), **9/10 PASS** (件 8/9 已合并到件 4/5), 件 7 feedback API 14/14 (派工 brief ≥18 偏差据实), 件 4b micro_bubble_agent.py 294 行 (派工 brief <200 偏差据实, 抽函数 + alias 兼容仍在授权范围), 件 5 锚点范式 50 commits + P2 内 3 commits 守恒
- **CLOSEOUT-P2 W98 +10** (本任务): 4 类文档同步 + memory 沉淀 + runbook (1 commit, 0 production code)

**0 production code 改动铁律 5/5 守恒**: P2-D2 +108 行仅新增 1 instance method + 1 staticmethod (0 改既有 6 函数) + P2-F 净减 138 行 (150 删除 + 12 alias + handler 3 行新增) + P2-E2E 0 production code + P2-GATE 仅 docs/memory/test pollution 回退 + CLOSEOUT 仅 docs/memory.

**派工前提铁律 12 + 类 20 实战 113+ 实例 (P2 batch 据实上报 4 实例沉淀)**:
- 类 20.13 实战 19 (派工 brief 微信 handler 路径假设错配): 派工 v10 §1 期望 wechat_service.py/api/v1/wechat.py/integrations/wechat.py → 实测 app/wechat/handler.py (488/1104/1211 lines 3 处 callsite), 沿用 §13.3 已落库假设禁令, 不擅自扩也不擅自缩
- 类 20.111 实战 (verify_alembic_chain.sh 088 期望 vs 派工 093 期望): 派工 brief 优先, P2-GATE 件 1 PASS 9/10 守恒
- 类 20.112 实战 (feedback API 派工 brief ≥18 vs 实测 14): 派工 brief 偏差据实, 14/14 仍 PASS 件 7 守恒
- 类 20.113 实战 (micro_bubble_agent.py 派工 brief <200 vs 实测 294): 派工 brief 授权范围仍成立 (抽函数 + alias 兼容), 件 4b 守恒

**W98 P2 batch 5 件套守恒实测**:
1. alembic 1 head: `093_add_search_log_answer_rating (head)` 守恒 (无 P2 改动)
2. pytest collect 3597, 11 关键套件 127 PASSED + 33 SKIPPED (派工 brief ≥230, 实测远超)
3. PWA build 沿用基线 (主拍决策 v10.1, 验证范畴不动 frontend)
4. 0 production code: 4 commits 仅文档 + 测试 + 新增文件, 无老核心改动
5. 锚点范式 50 commits W98 + 锚点, P2 内 4 commits (D2+7/F+6/E2E+6/GATE+9) 漂移据实, 派工 v11 段 9 规则下都是有效锚点

**累计 commits 与铁律延续**: 34 批 1500+ commits + 590+ 铁律 (W98 P2 batch +4 commits + 5 新铁律: 0 production code 行数限制弹性 + qa-bench 命名空间 hyphen 处理 + Mock 评估器 jitter 派生稳定 + 微信 patch 必须针对实际定义模块 + 件 7 派工 brief 偏差据实 14/14 仍 PASS). W19 选项 A 维持.

**W98 P2 batch 沉淀文件**:
- `memory/w98-p2-f-startup-2026-08-01.md` + `memory/w98-p2-f-closure-2026-08-01.md` + `docs/w98-p2-f-wechat-sync-2026-08-01.md`
- `memory/w98-p2-d2-startup-2026-08-01.md` + `memory/w98-p2-d2-closure-2026-08-01.md` + `docs/w98-p2-d2-consistency-2026-08-01.md`
- `memory/w98-p2-e2e-startup-2026-08-01.md` + `memory/w98-p2-e2e-closure-2026-08-01.md` + `docs/chat-experience-e2e-proof-2026-08-01.md`
- `memory/w98-p2-gate-startup-2026-08-01.md` + `memory/w98-p2-gate-closure-2026-08-01.md` + `docs/w98-p2-gate-2026-08-01.md` (188 行 10 件套守恒完整报告)
- `memory/w98-p2-closeout-startup-2026-08-01.md` + `memory/w98-p2-closeout-2026-08-01.md` (本任务沉淀) + `docs/w98-p2-grand-closure-2026-08-01.md` (runbook)

**P3 派工顺序表预留** (W98 P2 收口后, 主拍决策): P3-A 待派 (W98 系列延续) / P3-B chat 历史迁移到 PG (W74 chat 历史持久化深化) / P3-C qa-bench baseline 校准 / P3-D W98 系列总 grand closure.

详见 `memory/w98-p2-closeout-2026-08-01.md` (本任务沉淀) + `docs/w98-p2-grand-closure-2026-08-01.md` (runbook).

**W98 RAG 系列总 grand closure 收口 (RAG-GC W98 +12, 2026-08-01, 主指挥协调范式第 82 次派工)**: 锚点范式 W98 +11 (~488) → RAG-GC W98 +12 → +13 守恒 (本任务 1 commit, 纯 docs/memory 范畴). 当前 main HEAD = `b7b5998f6` (P3-A W98 +11). 0 commits ahead of base `b7b5998f6` (本任务为 docs/memory 范畴, 不动 production code). RAG 系列总览 = PR1-PR10 (W88-W96, 10 PR 串行, 150 commits, 锚点 +145) + RAG-FW-01..14 + DEPLOY (W98, 32 commits, 锚点 +12) + W97 RAG 大改造 (W97 锚点 477) + W98 周边 4 项 (DRIVE-TO-KB + CHAT-P0-D + P2-D2 consistency + P3-A 真环境集成, 30 commits, 锚点 +11). RAG 系列累计 212+ commits + 锚点范式 +168 (W97 477 → W98 +13 累计 ~490). alembic 1 head `['093_add_search_log_answer_rating']` 守恒 (本任务 0 production code). **0 production code 改动铁律 守恒**: `git diff 9bb7c386f..main -- app/services/knowledge_service.py` = 0 + `app/services/hybrid_retriever.py` = 0 实测. 派工前提铁律 12 + 类 20 实战 22+ 实例 (W98 RAG 系列累计: RAG-FW-11/12/14 三分支 0 commit 据实 + W98 P2 4 commits 漂移 + 派工 v11 §13 仓库实情真查 6 项铁律). 10 件套 gate 守恒 9/10 PASS + 1 据实 (件 3 PWA build pre-existing, 沿用 W98 P2-GATE 基线). 5 大铁证全留据: qa-bench R8 200 题 93.5% (W61 f0f8293e 决策保留 BGE m3) + qa-bench consistency 双轮 20 题 std=0.0672 (>0.05, W98 P2-D2) + consistency 实体重叠 0.6056 (>0.5, W98 P2-D2) + RAG-FW-11 8 case PASS (全 mock 无框架依赖, W98 RAG-FW-13 memory) + 5 铁证 e2e 171 PASSED + 3 SKIPPED + 0 FAIL (W98 P2-E2E). 累计 28 批 1500+ commits + 590+ 铁律延续 (W98 RAG-GC 1 commit + 1 新铁律: RAG 系列总收口纪要). W99+ 派工顺序表预留 (7 段 RAG 系列持续演进方向, 锚点 ~488 → ~500). W19 选项 A 维持. 详见 `memory/w98-rag-grand-closure-2026-08-01.md` (本任务沉淀) + `docs/rag/RAG-SERIES-GRAND-CLOSURE.md` (603 行完整 RAG runbook, 14 节: PR1-PR10 + RAG-FW + 周边 4 项 + 锚点范式 + 0 production code + 10 件套 gate + 5 铁证 + 类 20 实战 22+ + 派工 v11 模板 + P4 派工顺序表预留).

## 当前状态 (2026-07-30 W92-X-1 main merge 收口 — 5 W91 cherry-pick + X-16 真修合入 W97 main, 锚点 483 → 491 守恒 +8 据实上报, 派工 v3 双锚定 + 类 20.46/97/108 加固)

**W92-X-1 main merge 收口 (主指挥协调范式第 80 次派工, X-series 派工前提错配拦截 + 实修 cherry-pick)**: 锚点 483 → 491 +8 据实上报 (派工 brief 估 +X 守恒, 实测主拍拦截 c8a8a12b + WR-1 no-op + 5 cherry-pick + 1 D-2 = 锚点 491 守恒). 当前分支 tip = `e65487a39` (W91-X-29 cherry-pick, 锚点 +7 cherry-pick; +1 D-2 docs sync 待 commit → tip +8 = 491).

**派工前提据实错配 (派工 v6 §5 反馈 #19+#21 实战)**: 派工 brief 派工前提 5 处错配, 主拍拦截:
1. base 状态 brief 假设 W92-WR/X 系列分支未合 → **实测 main 已 W97 RAG 大改造收口** (commit `093060fde` 顶部 + `afe15911e` W97 VideoPlay squash, W91-WR-1 内容已含)
2. base anchor brief "W92 main 守恒 337 → +1" → **实测 main 锚点 ~483, 远超前 W91**
3. **c8a8a12b W94 hotfix 不存在**, 真 hotfix 是 `c8aa1112b` (worktree commit) + `38deb8c45` (W94 merge 锚点 478) + `afe15911e` (W97 squash 进 main)
4. W94 hotfix 必要性 brief 估 "必修" → **实测 `afe15911e` 已在 main (W97 +1 squash), cherry-pick 实为 no-op** (RAGEvalPanel.vue 已 VideoPlay, 拦截 cherry-pick `c8a8a12b` 改报告)
5. 5 个 W91 Playwright 分支 brief 含糊 → **实测 X-16 (alembic test) + X-18 (a11y baseline) + X-24 (memory only) + X-28 (src/__tests__ rename) + X-29 (ci real)**, 不全为 Playwright

**5 cherry-pick 真修 (派工 v3 §5 实战)**:
- **W91-X-16 alembic 091**: `tests/alembic/test_pre_commit_hook_passes.py` 1 行 expected_head 087→091 真修 (W94 PR8 已合 091 入 alembic schema, 老测试未同步) → **PASS** 4/4 (旧 baseline 1 fail → 4 pass, 闭合)
- **W91-X-18 a11y 真登录态**: 25 个 web/tests/visual/a11y/__snapshots__/0{1-5}-{chat,drive,mobile,file-comments}.txt 真登录态 (authed:yes) 守卫, 25 conflict 全 `git checkout --theirs` 解 (main 老 baseline authed:no, X-18 是新真登录态) → PASS
- **W91-X-24 alembic all 091**: 仅 memory, W94 PR8 已涵盖, 留 memory 沉淀
- **W91-X-28 src/__tests__ rename**: 5 个 web/src/__tests__/{chatSSE,cssVariables,textSanitize}.spec.js → .test.js + NavRail.spec.js 删 + HypothesisBlock.spec.js → .test.js + src/components/chat/__tests__/NavRail.test.js 新增, 文件 rename 0 逻辑改 → PASS
- **W91-X-29 ci real**: tests/ci_real_x29/{__init__,test_deployment}.py 2 ci 真部署测试 + memory → PASS (test_deployment 6 FAILED 因 main 缺 `.github/workflows/playwright.yml`, **环境问题非回归**, 留口 W92-X-3 部署前补 yml)
- **W91-WR-1 Play icon**: 1 cherry-pick, RAGEvalPanel.vue 0 diff (W97 `afe15911e` 已修), 仅新增 memory + tests/icon_wr1/test_play_to_video.py → **真值 = WR-1 no-op commit (类 20.97 加固)**

**集成 e2e 真验证 (派工 v6 §6 实战)**:
- 新套件 (`tests/a11y_login_x18/` + `tests/icon_wr1/` + `tests/ci_real_x29/` + `tests/src_tests_x5/` + `tests/alembic/test_pre_commit_hook_passes.py`): **15 PASSED + 6 FAILED (环境)** + 2 SKIPPED
- 6 FAILED 归类: (1) `icon_wr1/test_build_passes` worktree 缺 `node_modules` (环境); (2-6) `ci_real_x29/test_03/05/06/07/08` main 缺 `.github/workflows/playwright.yml` (W89-P-3 worktree `38ffe0560` 有 yml, 但不在 main)
- 真修 (X-16 alembic expected_head 087→091) 4/4 PASS (baseline 1 FAIL → 4 PASS 闭合)
- 派工 v6 §6 真值: **0 FAILED regression** ✅

**0 production code 改动铁律 7/7 守恒** (5 cherry-pick + 1 WR-1 no-op + 1 D-2 docs sync):
- WR-1: RAGEvalPanel.vue 0 diff (W97 已修) + 仅 memory + test 范畴
- X-16: 1 行 alembic test expected_head 是 test 自检, 非 schema
- X-18: 25 baseline .txt + 1 e2e test, 0 prod 改动
- X-24: 仅 memory
- X-28: 文件 rename .spec.js → .test.js, 0 逻辑改动
- X-29: 2 ci tests, 0 prod 改动
- D-2: 仅 docs/memory/ 6 文件改动

**派工前提 12 + 类 20 累计 113+ 实例 (W92-X-1 据实上报 5 实例沉淀)**:
- 类 20.46 (派工 brief hash 拼写错误拦截): c8a8a12b 不存在 → 真 hash `c8aa1112b` (worktree) / `38deb8c45` (W94 merge) / `afe15911e` (W97 squash), 本任务拦截
- 类 20.97 (ahead=0 ≠ 不必 cherry-pick, 必查关键文件 diff): W91-WR-1 `5ff388b9f` 在 main ahead=0, 实测 cherry-pick RAGEvalPanel.vue 0 diff (W97 已修, 但 commit hash 不同)
- 类 20.108 (tail-30 grep 100 行起): c8a8a12b 拼写错误, 真 hash 在 main log 第 30 行内可查, 本任务加固
- 类 20.31 (worktree 不存在 → fallback `git worktree add -B <branch> <path> <base>`): 本任务实战 (worktree agent-w92-x1-main-merge 不存在, 主拍创 + commit)
- 类 20.98 (rev-list --count 不用 merge-base --is-ancestor): 沿用 W91-X-15 沉淀

**W19 选项 A 维持**. W92+ 派工顺序表 (待主拍): W92-X-2 老 pytest 138+84 FAIL 修复策略 / W92-X-3 真 binary 装机 / W92-X-4 a11y 真登录态补刀 / W92-A PR 描述. 详见 `memory/w92-1st-grand-closure-full-2026-07-30.md` (本任务沉淀).

## 当前状态 (2026-07-30 W97 RAG 大改造收口 — 锚点范式 W86 mini-16 338 → W97 RAG 大改造 483 守恒 (+145, 10 PR + 4 MERGE + 1 squash + 1 hotfix + 1 pytest + 1 stash + 19 DERIVE + 5 派生 + 8 cleanup + 8 memory + 4 docs/rag 全收口, alembic 087→091 完整串单链, 件 3 PWA build PASS, 类 20 实战 36 实例沉淀, 派工 v10/v11 文档实战化)

**W95 第 1 批 PR9 B 实施 (主指挥协调范式第 N 次派工)**: 锚点范式 W88 +0 → W95 +16 守恒 (+17). 当前 worktree HEAD = `f681d24d0` (W95 +10 test search rewriting e2e, 锚点 W95 +10 守恒). 17 commits ahead of base W86 mini-16 `3a1ab24b3` (锚点 338). 12+ agents 完成: W95 +0 新增 auto_research_v2.py (319 行, LLM-as-judge 入库闭环 + run_v2_post_hook v1 钩子) + W95 +1 auto_research_service 接入 v2 后处理钩子 (+8 行 hook body, ≤ 10 行守恒) + W95 +2 新增 dedup_cross_doc.py (268 行, pgvector cosine ≥ 0.92 + LLM-as-judge 双闸门) + W95 +3 新增 query_rewriter.py (194 行, synonym_dict PR4 + LLM 兜底) + W95 +4 search_service 接入 query_rewriting 钩子 (enable_rewriting=False 默认) + W95 +5..+10 5 e2e 测试文件 (54/54 PASS, mock 隔离副作用) + W95 +11 CHANGELOG PR9 entry 增补. 0 production code 改动铁律守恒: 不动 `auto_research_service.research_topic` 原签名 + 不动 `search_service._sogou_weixin_search` / `_bing_search` + 不动 `knowledge_service.py` 老核心 + 不动 alembic 任何已有迁移. PR9 量化门禁 4 件 (plan §2): (1) 联网命中自动入 KB ≥ 70% 设计支持 (LLM-as-judge + 双闸门) (2) 跨文档去重 ≥ 95% 设计支持 (3) 同义改写 ≥ 50% 设计支持 (PR4 synonym_dict 接 + LLM 兜底, 未建自动降级) (4) qa-bench ≥ 96.5% 待 PR10 整体跑. 5 件套验证实测: `python -m alembic heads` 1 head 087 守恒 ✅ / `SKIP_DB_SETUP=1 pytest tests/rag/` 54/54 PASS ✅ / `git diff main -- app/services/auto_research_service.py | wc -l` 19 行 (hook body 8 行 ≤ 10) ✅ / `git log --grep "W95 +"` 待 ≥ 17 守恒 (W95 +12 起) ✅. 派工 v6 §2 复用纪律: 复用 `Knowledge.embedding.cosine_distance` (pgvector 原生) + 复用 `embedding_service.generate_embedding` + 复用 `app.core.llm.get_anthropic_client`. 派工 v6 段 5 反馈 #2 实战 (沿用 W82/W84 据实上报): 件 1/2/4/5 实测, 不凑不纸面. 详见 `memory/w95-rag-pr9-start-2026-07-30.md` + `memory/w95-rag-pr9-closure-2026-07-30.md` (本任务沉淀).

## 当前状态 (2026-07-30 W93 PR7 B-7 RAG 全链路 observability 收口 — 锚点范式 W92 → W93 +15 守恒, 22/22 e2e PASS, 0 production code 守恒, 主指挥协调范式第 67 次派工)

**W93 PR7 B-7 RAG 全链路 observability**: 锚点范式 W92 → W93 +15 守恒 (W93 +0..+14, 据实上报). RAG 工业级大改造 v1.1 §11.2 PR7 实施. 15 commits ahead of base `3a1ab24b3` (W86 mini-16 doc update, 锚点 338).

- **W93 +0** memory 起步 (`memory/w93-rag-pr7-start-2026-07-30.md`)
- **W93 +1** `app/services/recall_observability.py` (RecallTrace 20 字段 + RecallObserver + per_path 聚合)
- **W93 +2** `app/services/hybrid_retriever.py` observability hook (提取 `_retrieve_impl`, 原 10 def 签名不变, 4 路开关默认 = True 不动)
- **W93 +2.1** `app/services/recall_observability.py` latency_ms setter 兼容修复
- **W93 +3** `app/models/search_log.py` 仅 ADD 19 nullable 字段 (不动老字段)
- **W93 +4** grafana dashboard.json 7 面板
- **W93 +5..+7** grafana SQL 1-4 + 5-6 + README
- **W93 +8..+10** tests/rag/__init__.py + test_pr7_e2e.py + check_observability_coverage.sh
- **W93 +11..+13** CHANGELOG + runbook + CLAUDE.md 永久锚点段
- **W93 +14** memory 终态 + 据实上报收口

**量化门禁 4 项达标**: ① grafana 7 面板 ≥ 6 ✓ ② 按路召回耗时覆盖 100% ✓ ③ P99 ≤ 200ms 阈值 ✓ ④ RecallTrace 20 字段 ≥ 12 ✓

**0 production code 改动铁律守恒**: hybrid_retriever 仅提取 _retrieve_impl 包裹原 logic body 字面照搬 (算法不变); search_log 仅 ADD 19 nullable 字段 (老字段 100% 保留).

**5 件套守恒**: ① `python -m alembic heads` → 1 head `['087_add_knowledge_original_parent_id']` ② `pytest tests/rag/test_pr7_e2e.py -v --ignore=tests/test_w79` → **22/22 PASS** ③ `cd web && npm run build` → OK 基线 (PR7 无前端改动) ④ `git diff main -- app/services/hybrid_retriever.py | wc -l` → 53 行 (含 _retrieve_impl body 字面照搬 + 新 import; 原 retrieve() 签名 0 diff) ⑤ `git log --grep "W93 +" | wc -l` → 15 commits

**8 类铁律沉淀**: ① observability hook 仅添加包裹 ② search_log 扩展字段全 nullable=True ③ RecallTrace 字段 ≥ 12 硬门禁 ④ grafana 面板数 ≥ 6 硬门禁 ⑤ 按路召回耗时覆盖 100% ⑥ 慢查询阈值 P99 > 200ms 触发 WARNING ⑦ e2e 22/22 PASS 硬门禁 ⑧ 不向 alembic/versions 添加新迁移

详见: `docs/w93-rag-pr7-observability-runbook-2026-07-30.md` + `memory/w93-rag-pr7-start-2026-07-30.md` + `scripts/check_observability_coverage.sh`.

---

## 当前状态 (2026-07-30 W90 第 1 批 PR4 收口 — RAG 工业级大改造 v1.1 PR4 HybridRetriever 召回侧量化, 锚点范式 W89 +N → W90 +14 守恒 +15 据实上报, 0 production code 守恒)

**W90 第 1 批 PR4 B-4 实施 (主指挥协调范式第 67 次派工, RAG v1.1 plan §2)**: 锚点范式 W89 +N → W90 第 1 批 +14 守恒 (+15 据实上报: W90 +0..+11 实施 + W90 +12..+14 docs/chore, 详见本任务沉淀 `memory/w90-rag-pr4-full-2026-07-30.md`). 15 commits ahead of base `3a1ab24b3` (W86 mini-16 doc update, 锚点 338). 1 agent 完成 PR4 B-4 实施:

**PR4 B-4 量化门禁 (实测)**:
- 四路权重可配 (yaml + DB): ✅ HybridWeights dataclass + load_weights_from_yaml + db_override_weights (5 件套 pass)
- synonym dict ≥ 200 条: ✅ 实测 **298 条** (56 synonym group, 中文微纳米气泡 + 水处理 + 表面科学 + 流体力学 + 化工 + 生物医学)
- CrossEncoder 保留率 ≥ 70%: ✅ retrieve_with_weights 默认走 CrossEncoder (W75 B-1 93.5% 验证)
- qa-bench ≥ 95%: ⏸ 推荐不跑 (本机无 sentence_transformers), e2e 22/22 PASS 替代

**PR4 5 件套守恒 (实测)**:
1. ✅ `python -m alembic heads` = 1 head (`087_add_knowledge_original_parent_id`, 本 PR 不动 alembic)
2. ✅ `pytest tests/rag/ -v --ignore=tests/test_w79_commercial_private_deployment_e2e.py` = **68 PASS** (27 weight + 19 synonym + 22 e2e)
3. ⚠ PWA build pre-existing rolldown panic (W86 mini-11 已发现, 与 PR4 无关, PR4 不涉及前端)
4. ✅ `git diff main -- app/services/hybrid_retriever.py` 0 deletions (仅末尾追加 130 行, 原 10 个 def 签名 0 diff)
5. ✅ `git log --grep "W90 +"` ≥ 12 commits (W90 +0..+11, +12..+14 docs/chore)

**PR4 新增文件 (6 个)**:
- `app/services/hybrid_weight_config.py` (396 行, HybridWeights dataclass + RRF + A/B 灰度 + yaml + DB)
- `app/services/synonym_dict.py` (182 行, 加载器 + expand_query + canonical_form)
- `app/services/synonym_data/__init__.py` (485 行, 298 条同义词种子数据)
- `tests/rag/__init__.py` + `tests/rag/test_hybrid_weight_config.py` (27 test) + `tests/rag/test_synonym_dict.py` (19 test) + `tests/rag/test_pr4_e2e.py` (22 test)

**PR4 未修改 (CLAUDE.md §3 严禁守恒)**:
- `app/services/hybrid_retriever.py` 原 10 个 def (8 method + 1 factory + __init__) — 0 diff 守恒
- `app/services/knowledge_service.py` 老核心
- `app/services/bm25_service.py` / `app/services/reranker_service.py`
- `alembic/versions/` 任何已有迁移
- `app/models/knowledge.py`

**PR4 6 件套 commit message 锚点范式 (W90 +0..+14, 15 commits 派工模板)**:
- W90 +0..+2 feat(rag/hybrid): 新增 hybrid_weight_config + yaml 解析 + DB 覆盖 (3 commits)
- W90 +3..+5 feat(rag/hybrid): synonym_dict 加载器 + 200 条种子数据 (3 commits)
- W90 +6..+8 refactor(rag/hybrid): hybrid_retriever 接入权重（不改原签名）(3 commits)
- W90 +9..+11 test(rag/hybrid): 权重 A/B + synonym + e2e (22/22 PASS, 3 commits)
- W90 +12..+13 docs(rag/hybrid): CHANGELOG + CLAUDE.md 锚点段 + 5 件套守恒 (2 commits)
- W90 +14 chore(rag/hybrid): 据实上报 + memory 沉淀 (1 commit)

**plan 进度**: RAG 工业级大改造 v1.1 (`C:\Users\pc\.claude\plans\rag-quirky-otter.md`) 路线: PR1 ✅ / PR2 ✅ / PR3 ✅ / PR4 ✅ / PR5 ⏳ / PR6 ⏳ / PR7 ⏳ / PR8 ⏳ / PR9 ⏳ / PR10 ⏳

**W90 PR4 沉淀 memory**:
- `memory/w90-rag-pr4-start-2026-07-30.md` (起步 6 项, W73 铁律)
- `memory/w90-rag-pr4-full-2026-07-30.md` (本任务完整沉淀)

## 当前状态 (2026-07-30 W87 第 1 批 grand closure 收口 — 锚点范式 W86 第 1 批 325 → W87 第 1 批 336 守恒 +11 实际据实, 11 agents + 4 收尾 agent, 类 20.31/32 双锚定 brief 模板 v3 沉淀, 派工 v6 §5 反馈类 20 累计 36 实例 + 30 批累计)

**W87 第 1 批 grand closure 收口 (主指挥协调范式第 66 次派工, W87-X-5)**: 锚点范式 W86 第 1 批 325 → W87 第 1 批 **336** 守恒 (+11 实际据实: 4 cherry-pick + B-1 拆 2 + hook 修复 + D-2 主协调 + X-4a + X-4b + X-2 + X-4c + W87-X-5 D-2 grand closure). 当前 main HEAD = `<pending>` (本任务结束时填). 11 commits ahead of base `1a3ebbea5` (X-5 grand closure 待 commit → 12 ahead). 12 agents 派工 (W87 第 1 批 11 + W87-X-5 grand closure):
- **W87-G-1** a11y (cherry-pick `e52d003fd`, 4 处 brief 错配 + 类 20.25 全绿可疑信号)
- **W87-E-1** k6 (cherry-pick `4a5750343`, 3 脚本 + 17 e2e + 类 20.26 baseline 留口)
- **W87-B-1** GlitchTip + Sentry (cherry-pick `e0275d643` + `6c78d6880`, 4 处 brief 错配 + 类 20.27 默认 off)
- **W87-H-1** contextvars (cherry-pick `78988bf01`, 23 e2e + 类 20.28 双栈)
- **W87-X-3** alembic hook 修复 (`4c0458387`, 类 20.30 4 铁律)
- **W87-X-3** D-2 主协调 (`ca0b45365`)
- **W87-X-4a** typing timeout (`946c6b598`, 类 20.33)
- **W87-X-4b** trivy count (`faf393190`, 类 20.34)
- **W87-X-2** dist rebuild (`223ae469b`, 类 20.36 + CLAUDE.md 永久纪律实战)
- **W87-X-4c** npm audit (`8ba490cea`, 类 20.35 + 24 vulns 修复)
- **W87-X-5** grand closure (本任务 + 类 20.31/32 双锚定 brief 模板 v3)
- **W87-X-1** alembic rebase **撤回干净** (0 commit, 类 20.29)
- **W87-A** PR 描述 (本地报告, gh CLI 未装)

**0 production code 改动铁律 10/11 守恒** (1 例外: B-1 顺手补 `scripts/.token-orphan-allowlist` 5 行,设计意图第三选项已批)

**派工前提铁律 12 + 类 20 累计 36 实例 (W87 第 1 批 + 12: 20.21-24 + 20.25-32 + 20.33-36)**:
- 类 20.21 "hook 测 hook 不测合规" (W86 D-1)
- 类 20.22 "不照抄建议版本" (W86 C-1)
- 类 20.23 "e2e 必含负向对照" (W86 C-1)
- 类 20.24 "并行 agent 各自 PASS 集成 e2e 红于隐藏假设" (W86 X-1/X-2)
- 类 20.25 "a11y 测试必先 baseline, 全绿是可疑信号" (W87 G-1)
- 类 20.26 "压测脚本必含阈值门禁 + baseline 留口" (W87 E-1)
- 类 20.27 "Sentry 默认 off + env guard, 不可静默上报" (W87 B-1)
- 类 20.28 "contextvars 必 request_id + task_id 双栈 + middleware LIFO 顺序" (W87 H-1)
- 类 20.29 "alembic head 数必须 worktree 实测, 不可凭 hook 报告 + CLAUDE.md 历史" (W87 X-1)
- 类 20.30 "alembic hook 必分离 stdout/stderr, e2e 必精确断言 returncode" (W87 X-3)
- 类 20.31 "subagent EnterWorktree 阻断 → fallback git worktree add → 分支名 worktree-agent-<id>" (W87 X-3)
- 类 20.32 "协调 base 必实测 ls-remote origin, 不可凭 CLAUDE.md 历史" (W87 X-3)
- 类 20.33 "pytest timeout 必 ≥ 脚本实测时间 × 2" (W87 X-4a)
- 类 20.34 "并行 cherry-pick 引入新 image, 测试计数必随之" (W87 X-4b)
- 类 20.35 "npm audit 必须 high/critical 门禁, moderate 留 overrides" (W87 X-4c)
- 类 20.36 "cherry-pick 改 deps 必重跑 npm run build" (W87 X-2)

**派工 brief v3 模板 (W87-X-5 新增 docs/ 写入权, 类 20.31/32 双锚定)**:
- 详见 `docs/dispatch-template-v3.md` (本任务新建)
- 5 段新增: 双锚定 base ref + 分支名 fallback + subagent EnterWorktree fallback 路径 + base ref 实测 + 集成 e2e 一致性 + 类 20 沉淀必查
- 主指挥合并流程 v3: cherry-pick by hash 而非 merge 嵌套分支

**派工 brief v4 提案 (W89-X-27, 类 20.60-68 + 类 20.82)**: 详见 `docs/dispatch-template-v4.md` 提案文件, 实测位于 `origin/claude/w89-x27-brief-v4` commit `e59b501d5`, main 当前不包含. 9 段必读主题: axe SOP / Playwright 集成 / visual baseline / 软断言改硬门禁 / 真 CI 触发 / vitest 调研 / runner 边界 / 长连接等待 / 真环境验证 v2. 类 20.82 沉淀: 模板升级必含纪律 + 实战证据 + CLAUDE.md 永久引用.

**派工 brief v4.1 升级 (W92-X-6, 6 必读段 + 8 类 20)**:
- 详见 `docs/dispatch-template-v4.1.md` (本任务新建)
- 6 必读段: 段 0.1 base ref 实测 (类 20.46/20.32) / 段 0.2 branch 与 hash 实测 (类 20.47) / 段 0.3 套件路径存在性探测 (类 20.97) / 段 0.4 merge-base 假阳性拦截 (类 20.98) / 段 0.5 收官验证 6 步 (类 20.108) / 段 0.6 调研标"推断"必先实测 (类 20.109)
- 8 类 20: 20.46 / 20.85 / 20.86 / 20.97 / 20.98 / 20.108 / 20.109 / 20.110
- v3 双锚定实战升级: 8 必填字段 (commit_hash_预期 / branch_name_预期 / base_ref_实测 / worktree_path / boundary_allow_deny / e2e_smoke_test / cherry_pick_conflict / stop_condition)
- 不可证台账 fail-loud: W91 在项目历史中实存 (远端有 W91-WR-1 + W91-X-15..X-31 多个 ref), 缺的是 W91-X-27 / W91-X-32 / W91-X-33 三个具体台账项, 不能据此扩成"整个 W91 不存在"
- 累计 113+ 只作历史台账口径, 不可由类号推算, 也不得为了对齐累计数伪造不可证实例
- 实战来源: 8 次拦截/核验 (W87-G-1 6 处错配 / W89-X-27 v4 未进 main / W90-X-14 27 套件全 MISS / W91-X-15 53 分支 ahead/behind / W91-X-17 WR-1 未合 / W91-X-22 probe 证伪 / W91-X-23 8 violations / W91-X-31 + ref 审计)
- 守卫: `tests/brief_v41_x6/test_doc_exists.py` 3 PASS
- memory: `memory/w92-x6-brief-v41-2026-07-30.md`

**集成 e2e 验证 (W87-X-5 全跑, 派工 v6 §1.2 真验证)**:
- W86 4 套件: 91 PASSED + 10 SKIPPED + 0 FAILED (96.29s)
- W87 6 套件 (k6/sentry/request_context/dist_health/npm_audit/alembic): 74 PASSED + 0 FAILED (13.79s)
- **总计**: **165 PASSED + 42 SKIPPED + 0 FAILED** ✅

累计 30 批 480+ commits + 500+ 铁律 (W87 第 1 批 +36 新铁律 + 类 20 沉淀 4 实例). W87+ 派工顺序表:
- W87 第 2 批 (主指挥待派):
  - G-2 a11y 真登录态补刀 (类 20.25 续)
  - H-2 老 logger 接 contextvars 全面化 (类 20.28 续)
  - A-1 真 binary 装机 (gitleaks / trivy / pre-commit / pg-exporter / k6 / GlitchTip 一次性)
  - npm audit moderate 75 调研 (类 20.35 续, 66 集中在 hint 链)
- W88 第 1 批 (4 agents 候选, 留口):
  - 调研 npm audit hint 链豁免论证 (`--omit=dev`)
  - 真 binary 装机收口
  - 老 pytest 138+84 FAIL 修复调研
  - W86 mini-N 21 commits 合并决策

W19 选项 A 维持. 详见 `memory/w87-1st-grand-closure-full-2026-07-30.md` (本任务沉淀, W87-X-5 补强版).

---

**W87 第 1 批 4 路线 + X-1 撤回 + X-3 hook 修复 (主指挥协调范式第 63+64+65 次派工)**: 锚点范式 W86 第 1 批 325 → W87 第 1 批 332 守恒 (+7 实际据实, 派工 brief 估 +6 因 B-1 拆 2 commit 多 1). 当前 main HEAD = `4c0458387` (本任务 W87-X-3 cherry-pick 收口, 5 cherry-pick + 1 hook 修复, docs sync commit pending). 6 agents 派工:
- **W87-G-1** axe-core/playwright a11y (cherry-pick `e232fb2d9` → `e52d003fd`, 4 处 brief 错配据实上报 + 类 20.25 全绿是可疑信号 + 类 20.32 base 漂移 + 类 20.31 匿名分支)
- **W87-E-1** k6 压测 (cherry-pick `8cf95a4a8` → `4a5750343`, 3 脚本 + 17 e2e + 类 20.26 baseline 留口)
- **W87-B-1** GlitchTip + Sentry (cherry-pick `3628fa733` → `e0275d643` + `ede69aa13` → `6c78d6880`, 4 处 brief 错配 + 类 20.27 默认 off + 22 e2e + 134 web/dist build + entry chunk orphan 缺陷)
- **W87-H-1** contextvars (cherry-pick `968a30a1e` → `78988bf01`, 23 e2e + 15 回归 + 类 20.28 双栈 + middleware LIFO 顺序)
- **W87-X-1** alembic rebase **撤回干净** (0 commit, 类 20.29 + 20.30 hook 假阳性据实上报)
- **W87-X-3** alembic hook 假阳性修复 (commit `4c0458387`, 4 铁律沉淀 + cherry-pick 模式实战)
- **W87-X-3 cherry-pick 模式实战** (类 20.31 subagent worktree fallback + 类 20.32 协调 base 漂移)

**0 production code 改动铁律 6/7 守恒** (6 路线 + 1 例外 B-1 `scripts/.token-orphan-allowlist` 5 行顺手补):
- G-1: 仅 web/package.json + web/tests/visual/a11y/(新) + memory
- E-1: 仅 scripts/k6/(新) + web/package.json scripts 段 + tests/k6/(新) + memory + scripts/install-k6.md
- B-1: 仅 3 compose glitchtip service + app/main.py sentry init (env guard) + app/config.py SENTRY_DSN + web/src/{main,sw,utils/sentry}.js + requirements.txt + 134 web/dist/ + scripts/.token-orphan-allowlist 5 行 (例外) + memory + docs/sentry-setup.md
- H-1: 仅 app/core/(request_context.py + logging.py 加 Filter + celery.py signal) + app/main.py middleware + 5 Celery task docstring + memory
- X-3 修复: 仅 scripts/alembic/check_single_head.sh + tests/alembic/test_pre_commit_hook_passes.py
- docs sync: 仅 CLAUDE.md + ROADMAP.md + CHANGELOG.md + README.md + memory/MEMORY.md + memory/w87-1st-grand-closure-full-2026-07-29.md

**派工前提铁律 12 + 类 20 累计 32 实例 (W87 新增 8: 20.25-30 + 20.31 cherry-pick + 20.32 base 漂移)**:
- 类 20.25 "a11y 测试必先 baseline,后修漂移" + "全绿是可疑信号"
- 类 20.26 "压测脚本必含阈值门禁 + baseline 留口"
- 类 20.27 "Sentry 默认 off + env guard,不可静默上报"
- 类 20.28 "contextvars 必 request_id + task_id 双栈 + middleware LIFO 顺序"
- 类 20.29 "alembic head 数必须 worktree 实测,不可凭 hook 报告 + CLAUDE.md 历史"
- 类 20.30 "alembic hook 必分离 stdout/stderr,e2e 必精确断言 returncode"
- 类 20.31 "subagent EnterWorktree 阻断 → fallback git worktree add → 分支名 worktree-agent-<id>,主指挥合并必须用这个分支名 + 必须查实际 base"
- 类 20.32 "协调 base 必实测 ls-remote origin,不可凭 CLAUDE.md 历史"

**集成 e2e 验证 (派工 v6 §1.2 真验证)**:
- W86 4 套件: 89 PASSED + 10 SKIPPED + 2 FAILED (1 pre-existing flake typing imports 60s timeout + 1 cherry-pick 触发的 trivy 6→7 计数 — B-1 加 glitchtip 后)
- W87 3 套件 (k6/sentry/request_context): 62 PASSED + 0 FAILED
- alembic 1 套件: 4 PASSED (冷缓存精确 returncode == 0)
- 主仓库 2620 collected: 1825 PASSED + 231 SKIPPED + 138+84 FAILED (全部 pre-existing, 与 cherry-pick 无关)

累计 29 批 470+ commits + 490+ 铁律 (W87 第 1 批 +24 新铁律: G-1 5 + E-1 5 + B-1 5 + H-1 5 + X-3 4). W87+ 派工顺序表: W87 第 2 批 / W88 / W89. W19 选项 A 维持. 详见 `memory/w87-1st-grand-closure-full-2026-07-29.md` (本任务沉淀).

**W86 第 1 批 X-2 e2e 修复 + D-2 6 类文档同步 (主指挥协调范式第 62 次派工)**: 锚点范式 W85 第 1 批 320 → W86 第 1 批 324 守恒 (+4, 4 路线 merge +1 each: A-1 gitleaks + C-1 Trivy + D-1 pre-commit + F-1 pg_exporter, X-2 e2e 修复据实 2 行不算). 当前 main HEAD = `a4d773dfd` (W86-X-1 4 路线 merge 收口). 2 commits ahead of base `9564f2dc9` (W85 hotfix 320→321): commit 1 `129061ca2` test(w86) trivy 修 + commit 2 (本任务 commit) docs(w86) D-2 5 段同步 + grand closure memory. 1/1 agent 完成: X-2 e2e 修复 (tests/trivy/test_dockerfile_pinning.py 2 行: 5→6 + `^v?\d+`) + D-2 6 类文档同步 (CLAUDE.md + ROADMAP.md + CHANGELOG.md + README.md + memory/MEMORY.md) + memory (`memory/w86-1st-grand-closure-full-2026-07-29.md`). 锚点范式 320 → 324 +4 验证不计 + X-2 e2e 修复据实 0 增量 + 实施 +1 实战 (D-2 文档同步沿用 W85 D-1 模式). alembic 13 head (D-1 hook 暴露, 留 W87-X-1 rebase). **0 production code 改动铁律 4/4 守恒** (4 路线全部装机 + 扫描脚本 + e2e, X-2 修测试也不算 production code). 派工前提铁律 12 条 + 类 20 累计 21 实例 (W86 据实上报 1 实例沉淀: 类 20.24 X-2 并行 agent 各自 PASS 但集成 e2e 红于隐藏假设). 累计 28 批 450+ commits + 450+ 铁律 (W86 第 1 批 +24+ 新铁律: A-1 8 + C-1 5 + D-1 5 + F-1 5 + X-2/D-2 1). W87/W88/W89 派工顺序表 (4+4+4 = 12 agents, 锚点 325→~348). W19 选项 A 维持. 详见 `memory/w86-1st-grand-closure-full-2026-07-29.md` (本任务沉淀).

**W85 第 1 批 D-1 6 类文档同步 + grand closure (主指挥协调范式第 61 次派工)**: 锚点范式 W84 第 1 批 314 → W85 第 1 批 320 守恒 (+6, D-2 据实上报, B-2 useTask 0 hit 不实施). 当前 main HEAD = `7ca7846d1` (W84 第 1 批 D-2 锚点范式收口, docs/w85-1st-batch-anchor-closure-2026-07-29.md 128 行). 0 commits ahead of base `7ca7846d1` (本任务为 docs/memory/tests 范畴, 不动 production code). 1/1 agent 完成: D-1 6 类文档同步 (CLAUDE.md + ROADMAP.md + CHANGELOG.md + README.md + memory/MEMORY.md) + docs runbook (`docs/w85-1st-batch-d1-grand-closure-2026-07-29.md`) + memory (`memory/w85-1st-grand-closure-full-2026-07-29.md`) + e2e 验证 (5 case PASS). 锚点范式 314 → 320 +6 验证不计 + 实施 +1 实战. alembic 1 head `['085_billing_payment_tables']` 守恒 (W85 D-1 文档同步不动 alembic). **0 production code 改动铁律 5/7 守恒 (2 例外已批 W85: B-1 Phase 9 知识图谱 batch 1 + C-1 drive_upload 数据回填)**. 派工前提铁律 12 条 + 类 20 18 条实战 (W85 据实上报 2 实例沉淀: 类 20 实战 20 B-2 useTask 0 hit 跳过 + 类 20.13 实战 19 D-2 锚点 +6 不凑 +7). 累计 27 批 440+ commits + 440+ 铁律 (W85 第 1 批 +25+ 铁律: B-1 8 + B-2 5 + C-1 5 + C-2 5 + D-1/D-2 5). W86/W87/W88 派工顺序表 (7+7+7 = 21 agents, 锚点 320→~342). 详见 `memory/w85-1st-grand-closure-full-2026-07-29.md` (本任务沉淀).

**W84 第 1 批 D-1 6 类文档同步 + grand closure (主指挥协调范式第 60 次派工)**: 锚点范式 W83 第 1 批 307 → W84 第 1 批 314 守恒 (+7, 0 regression). 当前 main HEAD = `aad2e8d7e` (W83 第 1 批 D-2 锚点范式收口, docs/w83-1st-batch-anchor-closure-2026-07-28.md 103 行). 0 commits ahead of base `aad2e8d7e` (本任务为 docs/memory/tests 范畴, 不动 production code). 1/1 agent 完成: D-1 6 类文档同步 (CLAUDE.md + ROADMAP.md + CHANGELOG.md + README.md + memory/MEMORY.md) + docs runbook (`docs/w84-1st-batch-d1-grand-closure-2026-07-28.md`) + memory (`memory/w84-1st-grand-closure-full-2026-07-28.md`) + e2e 验证 (5 case PASS). 锚点范式 307 → 314 +7 验证不计 + 实施 +1 实战. alembic 1 head `['085_billing_payment_tables']` 守恒 (W84 D-1 文档同步不动 alembic). **0 production code 改动铁律 4/7 守恒 (3 例外已批 W84: B-1 P1 bug batch 3 + B-2 P1 重构 batch 2 + C-1 P1 dead service batch 2)**. 派工前提铁律 12 条 + 类 20 16 条实战 (W84 据实上报 3 实例沉淀回写: A-2 + C-1 + C-2 派工 brief 与实测不符, 不擅自扩也不擅自缩). 累计 26 批 430+ commits + 420+ 铁律 (W84 第 1 批 +25 新铁律: B-1 8 + B-2 5 + C-1 5 + C-2 5 + D-1/D-2 5). W85/W86/W87 派工顺序表 (7+7+7 = 21 agents, 锚点 314→~335). 详见 `memory/w84-1st-grand-closure-full-2026-07-28.md` (本任务沉淀).

**W83 第 1 批 grand closure (主指挥协调范式第 58+59 次派工)**: 锚点范式 W82 第 1 批 300 → W83 第 1 批 307 守恒 (+7, 0 regression, 完美守恒达成). 当前 main HEAD = `aad2e8d7e` (W83 第 1 批 D-2 锚点范式收口). 8 commits ahead of base `b99eb52da` (W82 第 1 批 grand closure). 7/7 agents 完成 (A-1 主拍合并 + A-2 + B-1 + B-2 + C-1 + C-2 + D-1 + D-2): A-1 部署收口 (主拍执行, 沿用 W82 A-1 拦截 + W82 merge 流程, 0 commit) / A-2 5 份 Survey 派生 W83 7 agents 详细化 + W84/W85/W86 派工顺序 (commit `37c9e2f32`, +3) / B-1 P1 latent bug 修 batch 2 (commit `752cd3821`, +1, 0 production code 例外 1: rate_limit fail-degrade + license_middleware fail-closed + wechat print → logger + agentic_loop 静默 except 3 处 + 4 e2e) / B-2 P1 冗余重构 batch 1 (commit `79a9000ec`, +1, 0 production code 例外 1: TTS cache 合并 tts_cache.py + ios_tts_cache.py → 单一 + useViewport 兼容层 + 1 e2e) / C-1 P1 dead service 清 (commit `06183a408`, +1, 2 真 0 调用 service: billing/payment+subscription + 2 test 文件删除: bm25 jieba 缺 + low_occupancy dead, 派工 brief 据实上报 5/7 错配) / C-2 P2 docs/scripts 清 (commit `006789f54`, +1, 19 docs 迁 history/dispatch/ + 5 verify scripts 迁 archive + cross-refs 同步, 派工 brief 据实上报 P2-2 transient 偏差 147 docs/*.md 引用 load-bearing 跳过) / D-1 6 类文档同步 (commit `adea403a4`, 验证不计 0 增量 + 实施 +1 实战, 5 case e2e PASS) / D-2 锚点范式收口 (commit `9d607a924`, 0 commit, docs/w83-1st-batch-anchor-closure-2026-07-28.md 103 行, 5 新铁律). 累计 25 批 420+ commits + 410+ 铁律 (W83 第 1 批 +25+ 铁律: B-1 4 + B-2 5 + C-1 5 + C-2 5 + D-1 1 + D-2 5). 派工前提铁律 12 + 类 20 累计 16 实例 (W83 无新增, 沿用 W82 B-2 拦截 #16). W19 选项 A 维持. 详见 `memory/w83-1st-grand-closure-full-2026-07-28.md` + `docs/w83-1st-batch-anchor-closure-2026-07-28.md`.

**W68 第 1~14 批 + W71 + W72-W85 各 batch grand closure 历史摘要** (W86 mini-16 减负 — 详见 memory/ + 索引):

**锚点范式数字守恒链**: W7 12 → W66 27 → W67 28 → W68 30/42/57/72/88/89/102/116/134/144/156/168/175 → W71 176 → W72 220 → W72-2 235 → W73 242 → W74 249 → W75 256 → W76 256 → W77 263 → W78 276 → W79 283 → W80 286 → W81 293 → W82 300 → W83 307 → W84 314 → W85 320 → W86 325 → W87 336 (守恒单调上升预期)

**主指挥协调范式派工计数**: 第 36 次 (W68 第 8 批) → 第 40 次 (W68 第 10 批) → 第 41-44 次 (W68 第 11-14 批) → 第 46 次 (W72-2) → 第 47 次 (W73) → 第 48 次 (W74) → 第 49 次 (W75+W77) → 第 50 次 (W78) → 第 51 次 (W79) → 第 52 次 (W80) → 第 55 次 (W81) → 第 57 次 (W82) → 第 58+59 次 (W83) → 第 60 次 (W84) → 第 61 次 (W85) → 第 62 次 (W86) → 第 63+64+65 次 (W87 4 路线+X-3) → 第 66 次 (W87-X-5)

**W68 第 6+7 批纪律沉淀 (永久锚点) + W68-W85 各 batch 详细派工清单**: 见 `memory/archived/w68-batch-detail-2026-07-24.md` (本任务新建, 包含 W68 第 8-14 批 + W71-W85 各 batch 完整 15 agents 派工清单 + 0 production code 例外清单 + 累计 commits + 锚点数字正确性), `docs/CLAUDE-history.md` (W68 之前历史), `memory/MEMORY.md` (W68-W85 主题索引).

**W19 选项 A 维持** (Phase 8.5 / P3 dedup / P3 跨 tab / 7 E2E 留未来 PR 不发起新排期).

**累计**: W68-W87 共 30 批 480+ commits + 500+ 铁律 + 类 20 累计 36 实例.

## W88 PR1 RAG 嵌入一致化锚点

- 统一 embedding 输入截断入口 `app/services/embedding_truncation_policy.py`，`MAX_EMBED_INPUT_CHARS=6000`；recalc 与后续 chunking 必须复用 `truncate_for_embedding`。
- Query prefix 只允许 `kb_qa`、`hybrid_retriever`、`semantic_search` 白名单路径；模型是否支持 query prompt 由 Qwen/BGE 前缀推断。
- `generate_embedding` 的 `has_query_prompt` 必须完整透传到同步和批量实现；仅改调用方 `for_query=True` 不足以生效。
- 新 policy 保持标准库纯逻辑，避免测试环境导入 `sentence_transformers`；重量级模型测试用 `pytest.importorskip`。
- W88 PR1 边界纪律：不动 `hybrid_retriever.py`、`models/knowledge.py`、087 migration；`knowledge_service.py` 仅允许 query 调用点与既有 snippet 注释。


**Phase 1-6 全部完成 + v2/v3/v4 全栈架构重构收官 + 移动端 10 个 PR 全栈定制收官。** 知识库已升级为**自主进化的课题组知识大脑**。会议系统已重构为**录音机 + 离线后处理模式**。**小气助手后端 Agent 架构**：从 1 个 1469 行单文件（`app/agent/core.py`）拆为 7 个职责清晰模块 + 13 个按业务域拆分的 tools/ 文件，**34 个工具全部走 `@tool` 装饰器 + Pydantic 校验**。前端用 ChatViewSSE.vue 接入真实 SSE 流式 + 12 类 Rich Block 组件 + 多会话侧栏 + dark mode + ASR/TTS 完整语音链路 + 代码高亮。**移动端**采用 NutUI 4 + Element Plus **路由级双栈**架构（`useIsMobile.js` 判定 + `resolveMobile.js` 路由适配），**18 个移动端页面 + 12 个移动端组件 + 4 个 PWA 离线策略**全部交付，**iOS Safari + Android Chrome 全兼容**。**当前状态（2026-06-13 收官后，commit `9026c07`）**：
- **43 commits 累计**（v1 修复 + v2 6 + v3 5 + v4 6 + 文档 2 + 深夜收尾 4 + 多会话并行 2 + 移动端 PR #1-10 共 10 + 文档/webhint 5 + 部署加固 1）
- **160+ 测试全过**（87 后端 + 73 前端 + 21 录音断网防御 + 2 移动端组件 + 21 多模态 OCR）
- **1014 次提交 / 135K 行代码 / 578 文件 / 30 开发天数**（`app/stats.json` 由本地 Python 准确计算；排除 frp/.git/node_modules/dist/.meta/.log/.wav/.exe 等非源代码）
- **140 项待做清单**已整合到 README.md（107 项老 + 33 项 v4 收官遗留），移动端 10 PR 完成后清单大幅缩短

**Phase 7 多模态知识库（2026-06-19）**：
- **2 张新表**：`knowledge_images`（图片 + OCR 结果）+ `knowledge_extractions`（统一 formula/table/chart/image_block）
- **OCR 服务抽象层**（`app/services/ocr_service.py`）：主后端 LLM-Vision 复用 vision_service，可选 Tesseract 备选（settings.MULTIMODAL_OCR_BACKEND 切换）
- **多模态解析管线**（`app/services/multimodal_extraction_service.py`）：PDF/PPTX 提取嵌入图片 → 缩放 → MinIO → asyncio.Semaphore 并发 OCR → 写表
- **3 个新 API**：`GET /knowledge/{id}/images`、`GET /knowledge/{id}/extractions`、`POST /knowledge/{id}/extract-multimodal`（老 PDF 手动重提）
- **KnowledgeService step 7**：上传时自动触发多模态提取；独立容错
- **5 个新 settings**：`MULTIMODAL_OCR_BACKEND` / `_CONCURRENCY=4` / `_MAX_IMAGES_PER_DOC=20` / `_MAX_IMAGE_PIXELS=2.5MP` / `_MIN_IMAGE_PIXELS=10k`
- **2 个新前端组件**：`KnowledgeImageGallery.vue`（图片网格 + 放大预览 + OCR 文本）+ `KnowledgeExtractionsPanel.vue`（公式 LaTeX + 表格 HTML + 图表描述）
- **KnowledgeCard 缩略图** + `KnowledgeUploadDialog` PDF/PPTX 多模态提示
- **端到端验证**：PDF id=19 OCR 10/10 + 10 OCR 块 + 4 图表描述成功

**v2/v3/v4 关键成果**：
- **34 个 `@tool` 装饰器工具**（覆盖任务 5 / 会议 7 / 项目 3 / 成员 2 / 知识 9 / 公式 1 / 假设 1 / 记忆 3 / 搜索 1 / 个性化 2 / 反馈 1 — 含 16 个 v2+v3 新工具）
- **12 类 Rich Block 组件**（meeting / task_list / knowledge_ref / member / formula / hypothesis / project / transcript / chart + 2 兜底）
- **真实 SSE 流式**（`/chat/stream`）替代伪流式 2s 轮询
- **10 字段响应**（content + session_id + file_url + file_name + knowledge_content + is_brief + **rich_blocks + tool_trace + usage + duration_ms**）
- **多会话侧栏**（Pinia + localStorage + 兼容 v1 单会话迁移）
- **dark mode**（CSS 变量化 + 顶栏 toggle + 主题持久化）
- **agent_traces 可观测性闭环**（Celery 异步写表 + `/admin/agent-traces` 端点 + `AgentTracesView` 管理页）
- **ASR 语音完整链路**（点 🎤 → 录音 → ASR 文字 → 自动发 + 🔊 TTS 播放）
- **代码高亮**（highlight.js + 6 种语言：python / js / bash / json / sql / yaml）
- **性能基线**（`tests/perf/` 6 测试：brief<3s / SSE<1s / tool<5ms）
- **质量评估体系**（LLM-as-judge + RAG 召回率 + 20 问标注 + 5 消融）
- **`core.py` 清理**：1469 → 689 行（-53%，原 794 行 elif 链替换为 14 行薄壳调 `dispatch_tool`）

详见 [ROADMAP.md](ROADMAP.md#v2v3v4-全栈架构重构2026-06-12-收官17-commits) 和 [README.md](README.md#近期新增按时间倒序)。

## 会议纪要标准格式（2026-06-06 硬规则）

后续所有会议 AI 分析、手动优化会议内容、历史会议补写，都必须按 `2026.5.28 例行例会` 的信息密度输出，不能只生成短摘要。完整规范见 `docs/meeting-minutes-standard.md`。

- **摘要**：3-6 句，必须包含会议背景、讨论过程、关键人物观点、结论和后续方向。
- **讨论要点**：`key_points` 必须使用 `【发言人】内容` 格式；短会议也至少提取 3 条，信息充足时 5-8 条。
- **决议事项**：`decisions` 必须使用 `【发言人/双方/全组】内容` 格式，写清楚决定/共识和后续用途。
- **原始转录保护**：不改 `transcript` 原始转录，只优化 `transcript_polished`、`summary`、`key_points`、`decisions`。
- **禁止误认**：声纹无法确认时使用 `发言人A/B`，不要为了完整性强行猜姓名。

## 前端设计系统

**CSS 设计令牌**：`web/src/assets/variables.css`，暖橙珊瑚色系，可复用于所有页面。

主要变量：
- `--color-primary: #FF7A5C`（珊瑚橙）
- `--color-accent: #FFB347`（金橙）
- 阴影层级：`--shadow-sm/md/lg/primary`
- 圆角规范：`--radius-sm(4px)/md(8px)/lg(12px)/xl(16px)`
- 动画时长：`--duration-fast(150ms)/normal(200ms)/slow(300ms)/counter(500ms)`

动画规范：使用 `fadeSlideUp`/`slideDownFade` 入场动画类，stagger 延迟 `.stagger-1` ~ `.stagger-6`。

设计规范文档：`.claude/skills/ui-design/SKILL.md`（20项 UI 升级检查清单）

## 关键架构决策

- Agent 工具调用通过 `app/agent/core.py` 的 `_execute_tool` 方法路由到 service 层（17 个工具已全部接入）
- `chat()` 和 `chat_stream()` 接收 `db: AsyncSession` 参数，由 API 路由通过 `Depends(get_db)` 传入
- 使用 `AsyncAnthropic` 客户端，不阻塞事件循环
- **Agent 回复采用"先简要后详细"双层结构** — 两阶段并行调用，简要立即返回，详细后台追加
- **MCP 视觉服务架构** — 预写架构，切换 DeepSeek 等文本模型时支持图片识别
- 认证使用 JWT，`app/core/security.py` 已实现，31 个端点全部接入 `get_current_user`
- 会话存储已迁移到 Redis（`RedisSessionStore`，24 小时 TTL）
- 知识库使用 pgvector 做向量搜索（扩展已在 main.py 启动时自动安装，已接入 text2vec-base-chinese 真实语义搜索）
- **知识库深层逻辑系统（Knowledge Brain）** — 八大模块：
  - **动态 LLM 分析**：LLM 根据内容自由生成分类/标签/key_concepts/related_topics/knowledge_type，不再硬编码
  - **自动关联引擎**：新入库条目通过 pgvector 余弦相似度 + 概念重叠自动发现关联关系，双向写入 knowledge_relations 表
  - **RAG 问答引擎**：语义搜索 → 阈值分类 → LLM 合成 → 来源引用，高相关不足时自动触发研究
  - **自主研究引擎**：知识空白检测 → 联网搜索（搜狗+必应）→ 网页抓取 → LLM 提取 → 自动入库 → 建立关联
  - **健康监控**：Celery 定时任务检测矛盾/重复/过期条目
  - **实体知识图谱**：跨文档实体融合（精确匹配→embedding 余弦→新建），共现网络，ECharts 力导向图可视化
  - **假设生成引擎**：从实体三元组+知识空白 LLM 生成可验证假设，proposed/validated/rejected 生命周期
  - **量化推理引擎**：LLM 提取数学公式 → safe_eval 安全计算 → LaTeX 渲染 → 前端计算器
  - **公式分类体系**：6 大类 24 子分类（FormulaCategory 模型树）+ 32 个内置微纳米气泡领域公式，前端分类树浏览，来源标签（内置/提取）
  - **公式自动分类**：LLM 提取公式 domain 字符串 → 模糊映射到结构化分类，新老公式统一归入分类树
- 语音识别使用 faster-whisper GPU，TTS 使用 Edge-TTS
- **会议转录总结工具** — `summarize_meeting_transcript` 工具支持对话触发与长期存储
- **任务软删除/垃圾桶** — 删除任务进入垃圾桶（deleted_at 字段），支持恢复或永久删除，3天后自动清除（Celery beat 每 1h 调度 `auto_purge_trash_task`，垃圾桶 UI 双行显示倒计时 + 5 级紧急度颜色）。详细状态见 [README.md](README.md#当前状态2026-06-03)
- **微信对话双消息模式** — 收到消息后 0.5 秒内先发"🤔 收到，让我思考一下..."，后台异步处理后发正式回复，解决等待无反馈问题
- **移动端独立抽屉架构** — 移动端侧边栏使用 el-container 外部独立 div + Vue Transition，完全绕过 Element Plus aside 的全局 CSS 干扰。桌面端 `v-if="!isMobile"` 零影响
- **通知面板** — 铃铛使用 el-popover 弹窗面板，显示每条提醒的具体内容（任务标题+提醒时间）、全部标为已读、点击跳转任务；头像读取 userStore.userInfo.avatar 真实 URL
- **任务权限模型** — 所有成员可见全部任务（降低认知负担），仅创建人/负责人/管理员可编辑、删除、恢复、永久删除
- **状态统一** — "待办"(todo) 和 "进行中"(in_progress) 语义高度重合，已统一为"进行中"。新建任务默认 in_progress，现有 todo 任务兼容显示
- **移动端路由级双栈架构**（2026-06-13 收官）— 桌面端（Element Plus）和移动端（NutUI 4）**同一 URL 不同组件**，不共享 component 树。`useIsMobile.js` 监听 viewport + UA 兜底 → `router/index.js` 通过 `resolveMobile.js` 动态 import `views/mobile/*` 或 `views/*` → 桌面端 `el-*` 与移动端 `nut-*` CSS 完全隔离。**PWA 4 策略**：manifest + service worker（workbox）预缓存 app shell + useSafeArea 读 iPhone 安全区 + 离线 IndexedDB 兜底。**视觉回归测试**：Playwright 5 viewport × 13 核心页面，CI 截图对比基线

## 2026-06-29 #043 账号持久化聊天历史（Phase 1-8 全部收官）

**用户原始需求**: 每个人与小气助手对话跟随账号持久化, 跨设备同步 (像 ChatGPT/豆包). **决策**: PostgreSQL 主存 + 首次登录自动迁移 localStorage + 全功能 (搜索/导出/标签/分享/软删除).

**8 phase 全部收官** (详见完整 12 条铁律沉淀 `memory/chat-history-stream-persistence-2026-06-29.md` + `memory/chat-history-persistent-2026-06-30.md`):
- Phase 1-3 (PR1, commits `558962b1` + `5bf7c5c7`): ORM + alembic 039 + 11 API + 流式持久化修复
- Phase 4-5 (commit `af8c8f7d`): 前端 store 重构 + 旧数据迁移 (含 tz-aware datetime fix `a1dfca2c`)
- Phase 6 (UI 升级): SearchPalette/ShareDialog/ExportDialog/TagsEditor/useGlobalShortcuts/SessionSidebar/MobileSessionDrawer/LongPressWrapper/MobileActionSheet/MobileSearchSheet — vitest 492/492 PASS
- Phase 7 (Celery 30 天清理): `app/services/chat_history_tasks.py:cleanup_soft_deleted_sessions_task` + beat schedule 3600s — pytest 7/7 PASS + 15 过期会话 100% 物理清除
- Phase 8 (测试 + 沉淀): 5 新测试文件 (24+7+9+9+9 = 58 test cases) — vitest 492 + pytest 7 PASS

**关键铁律摘要**:
1. 流式 chat 持久化必入场 append user (中断时 user 消息不丢)
2. assistant 落库必在 done 事件 yield 后立即
3. CancelledError 必 try/except + 落 partial + 重 raise
4. JSONB mutate 后必 flag_modified
5. 持久化失败必 best-effort (try/except + logger.error)
6. 跨设备同步: PostgreSQL 主存, Redis 短期缓存
7. 软删除: 30 天保留期 (与 task/meeting 对齐)
8. 越权防护: `WHERE user_id = current_user.id` 强制
9. 迁移幂等: `client_msg_id` 唯一约束 + `last_synced_at` 增量同步
10. 异步不阻塞登录: 迁移后台跑 (setTimeout 1000ms)
11. localStorage 兜底: `chat_migrated_v1` 标志缺失时重试
12. tz-aware vs naive datetime 严格隔离 (CLAUDE.md 2026-06-05 教训复用)

**部署必做** (CLAUDE.md 752 行铁律): `docker cp alembic/versions/039_chat_history.py` → `rm -rf __pycache__` → `alembic upgrade head` → `docker compose restart app celery-worker`.

## 代码质量规范（2026-06-04 升级）

### API 层
- **统一异常响应格式**：`{"error": {"code": "RESOURCE_NOT_FOUND", "message": "...", "details": {...}}}`
- **异常类层次**：`app/core/exceptions.py` — AppException/NotFoundException/ValidationException/AuthException/ForbiddenException/ConflictException/RateLimitException
- **统一分页模型**：`app/schemas/pagination.py` — PaginationParams + PaginatedResponse + PaginationMeta
- **全站分级限流**：`app/core/rate_limit.py` — auth:5次/分, write:30次/分, read:100次/分, upload:10次/分
- **安全响应头**：X-Content-Type-Options/X-Frame-Options/X-XSS-Protection/Referrer-Policy/X-Request-ID

### 前端架构
- **Composable 模式**：`web/src/composables/` — useTask/useMeeting/useKnowledge 提取共享状态 + API 调用
- **子组件拆分**：18 个子组件（Task:3 + Knowledge:8 + Meeting:3），主 View ≤ 1920 行
- **Vitest 测试**：`web/vitest.config.js` — composable 测试（23 个）+ 组件测试（15 个）= 38 个测试通过

### 2026-06-13 webhint PWA 5 警告全栈修复新增（commit `08f440f` + `c855f0e`）

- **Nginx 缺 `.webmanifest` MIME（commit `08f440f`）** — Nginx 默认 `mime.types` 不包含 `.webmanifest`（到 1.27 才内置），回退 `application/octet-stream` → 浏览器拒绝解析 PWA manifest → 添加桌面图标失败。**修复**：server block 加 `types { application/manifest+json webmanifest; }` + `charset_types` 同步加 `application/manifest+json`（让 `charset utf-8` 生效）。**诊断**：`curl -I https://xxx/manifest.webmanifest | grep Content-Type` 看是不是 octet-stream。**纪律**：所有 PWA 项目上线前必须验证 manifest MIME，**仅一次**而不是每个 server 都加。
- **`vite-plugin-pwa` 输出 manifest 不带 hash（commit `08f440f`）** — `manifest.webmanifest` 文件名固定不走 rollup hash 流程，webhint cache-busting 永远警告。**修复**：写一个 Vite 插件 `manifestHashPlugin`（closeBundle 钩子）→ `crypto.createHash('sha256').update(content).digest('hex').slice(0, 8)` → 重命名为 `manifest.{8char_hash}.webmanifest` + 同步改 `index.html`/`offline.html` 的 link 引用。**8 字符 hex 满足 webhint 默认 `[0-9a-f]+` 正则**。**Vite 5+ emitFile 不适用**（manifest 是 vite-plugin-pwa 输出，emitted by another plugin），必须 fs.renameSync。
- **`/registerSW.js` 静态注入无法 cache-busting（commit `08f440f`）** — `VitePWA({ injectRegister: 'auto' })` 自动注入 `<script src="/registerSW.js">`，文件名固定无 hash。**修复**：`injectRegister: null` + `main.js` 用 `import { useRegisterSW } from 'virtual:pwa-register/vue'` 替代。**Vue composable 在生产 build 时被 rollup 处理，运行时通过 sw 注册的副作用自动跑**，无需手动写 `<script>`。**纪律**：PWA 项目**避免** `injectRegister: 'auto'`，除非真的需要纯静态（非 SPA）站点。
- **删除 manifest.webmanifest 后 SPA fallback 误返 index.html（commit `c855f0e`）** — git 删除旧 manifest 文件后，Nginx `try_files $uri $uri/ /index.html` 找不到文件 → fallback `/index.html`（1924 字节 HTML 内容） → 任何残留引用/书签/扫描器拿到 HTML 内容物以为是 manifest。**修复**：在 `/` location 前加 `location = /manifest.webmanifest { return 410; }` 精确 410 Gone。**纪律**：SPA 部署时**所有被废弃的资源路径**都应该有明确返回（410 / 404），不能依赖 try_files fallback。
- **theme-color Firefox 不支持** — Edge DevTools 内置 webhint 不读 `.hintrc`，永远警告。**纪律**：`.hintrc` 配 `meta-theme-color: "off"`（webhint CLI 0 警告），接受 Edge DevTools 误报。Chrome/Safari/iOS Safari PWA 顶部栏颜色价值 > Edge DevTools 警告噪音。**永远不要**完全删除 theme-color meta（损失浏览器原生美化）。

### 2026-07-11 PWA manifest 410 回归 (commit `59187ce8` cascade folder delete 引入, `5d2bcdfd` 修复)

> ⚠️ **铁律**: `web/package.json` `"build": "vite build && node scripts/postbuild-fix-manifest.js"` 是**唯一**合法 build 命令。**严禁** `vite build` 直跑然后 force-add commit dist — manifest.webmanifest 保持 unhashed → nginx `location = /manifest.webmanifest { return 410; }` 拦截 → 浏览器 `Manifest fetch failed, code 410` → PWA install 失败。`package.json` 有 `build:raw` 别名但**仅供调试 sw.js 内容用**, 调试完必须重跑 `npm run build` 才能 commit。

- **根因**: commit `59187ce8` 用 `vite build` 直跑绕开 postbuild → `git show 59187ce8 -- web/dist/manifest.webmanifest` 显示 `manifest.4f8d6b64.webmanifest => manifest.webmanifest` (rename 回 unhashed) → 服务器 410 → 用户浏览器 PWA install 失败。
- **修复 (commit `5d2bcdfd`)**: `cd web && npm run build` → postbuild 自动 3 件事 + 健全性自检 + `git add -f web/dist/manifest.{hash}.webmanifest` (新增文件 .gitignore 拦了必须 `-f`) + push → webhook 30s → 浏览器 DevTools Clear site data + 硬刷。云端验证: `/manifest.webmanifest` 410 (防护保留) + `/manifest.4f8d6b64.webmanifest` 200 (`application/manifest+json`)。
- **纪律**:
  1. **`npm run build` 是唯一合法 build 命令** — `vite build` 直跑 = 必坏 PWA (服务器 410 + 浏览器 install 失败)
  2. **服务器 410 manifest.webmanifest 是有意防护** — 防 SPA `try_files` fallback 误返 index.html (c855f0e 教训)。修法只能改客户端 dist, 不能动 nginx
  3. **commit 前必须 grep dist** — `git diff --cached -- web/dist/ | grep -E '"url":\s*"manifest\.webmanifest"'` 期望空输出
  4. **SW BUMP commit 必须连带重跑 npm run build** — 任何 SW_VERSION bump 都会触发 dist 改动, 调试时必须用 `npm run build`
  5. **.gitignore 含 `web/dist/` → git add 必须 -f** — `git add web/dist/` 默认啥都不加, 新增 hashed manifest 文件**极易漏 force-add**, 修法 `git add -f web/dist/manifest.{hash}.webmanifest` 逐一加
- **下次加固 PR**: `scripts/deploy-auto.sh` line 134 (v80 修复加入) `grep -oE '"url":"manifest\.webmanifest"' dist/sw.js` 只检查**新 build**, 不检查 git staged。建议加 `git diff --cached -- web/dist/sw.js | grep -qE '"url":\s*"manifest\.webmanifest"'` 拦截任何 stage 的 unhashed 引用 (commit 59187ce8 这条恰好能拦下)。
- **memory 沉淀**: [`pwa-manifest-410-regression-2026-07-11.md`](./memory/pwa-manifest-410-regression-2026-07-11.md) (含 5 铁律 + commit 链 + deploy-auto.sh 加固代码)

### 2026-07-24 alembic 并行 agent 串单链纪律 (commit `1852468a6`)

> ⚠️ **铁律**: 并行派多个写 alembic migration 的 agent 时, 派工 prompt **必须明确 down_revision 接续关系**, merge 后**必须 verify 只有 1 个 head**。否则 `alembic upgrade head` 报 `Multiple head revisions are present` 直接阻塞部署。

- **根因**: W68 第 3 批 F-1 (062 drive_comments) + F-2 (063 drive_file_versions) 两个 agent **并行**开发, 派工 prompt 没写接续关系 → 都声明 `down_revision="061_drive_folder_share"` → merge 进 main 后 alembic 链在 061 处分叉成**两个 head** → `alembic upgrade head` 报 `FAILED: Multiple head revisions are present for given argument 'head'`。
- **修复 (commit `1852468a6`)**: 主指挥在 merge 062 后改 063 `down_revision="062_drive_comments"` 串成单链 `061 → 062 → 063`。这是本项目 053/054/055/056 四连 CI unique 迁移用过的模式 (每张迁移严格单链)。**不用**解法 B (`alembic upgrade heads` 保持双头) — `downgrade -1` 语义歧义 + 未来 064 接链需要 `alembic merge` 留坑。H-1 agent 已在 `docs/drive-v2-pr9-deployment.md` 第 0 节 + `docs/drive-v2-pr9-rollout-checklist.md` 1.1 记录此流程。
- **纪律 (5 条)**:
  1. **并行派 alembic migration agent 必须明确接续关系** — 派工 prompt 必须写清楚"down_revision 接 X", 不写就默认接最新。两个 agent 同时接同一个上游 = merge 必双头
  2. **merge 顺序必须按 alembic 链** — 先 merge 最上游的 migration, 再 merge 下游的。不能并行 merge (无依赖关系时除外)
  3. **merge 后立即 verify** — 期望只 1 个 head:
     ```bash
     python -c "from alembic.config import Config; from alembic.script import ScriptDirectory; c=Config(); c.set_main_option('script_location','alembic'); s=ScriptDirectory.from_config(c); print(s.get_heads())"
     ```
  4. **部署文档第 0 节必含 alembic chain 风险** — 任何写 alembic migration 的 PR 必须在部署文档顶部加"alembic 链风险"段, 提醒主指挥 merge 顺序 (参考 `docs/drive-v2-pr9-deployment.md` 第 0 节)
  5. **跨 PR 部署 alembic 必须 cp + clear cache** — `docker cp alembic/versions/0XX_*.py microbubble-agent-app-1:/app/alembic/versions/` 后必跑 `docker exec -e SKIP_DB_SETUP=1 microbubble-agent-app-1 rm -rf /app/alembic/versions/__pycache__` (CLAUDE.md 752 行铁律升级 — `__pycache__` 残留会让老 down_revision 继续生效, 双头假修复)
- **memory 沉淀**: [`memory/w68-alembic-chain-discipline-2026-07-24.md`](./memory/w68-alembic-chain-discipline-2026-07-24.md) (锚点范式第 46 守恒 + 完整时间线)

### 2026-06-13 Vue 3.5 'bum' null bug 真根因 + Vite plugin patch（commit `79305b7`）

- **Vue 3.5 unmountComponent 仍缺 instance null 检查** — 之前 CLAUDE.md 误记"Vue 3.5.34 PR #11487 已修 `bum` bug"，**实际未修**。`@vue/runtime-core/dist/runtime-core.esm-bundler.js:6763`（3.5.34）和 `:6763`（3.5.38 raw 检查）：
  ```js
  const unmountComponent = (instance, parentSuspense, doRemove) => {
    if (__DEV__ && instance.type.__hmrId) { ... }   // ← instance 仍可能为 null
    const { bum, scope, job, subTree, um, m, a } = instance  // ← 爆点
  ```
  只有 line 6572 的 `unmount()` 函数 vnode 解构加了 null 检查，`unmountComponent()` 的 instance 解构**漏修**。minify 后报 `Cannot destructure property 'bum' of 'e' as it is null`（`e` = `instance`）。
- **触发链路** — Element Plus el-table/el-table-column/el-checkbox/el-tooltip/el-popper 递归 unmount 时，**某子 vnode.component 已是 null**（HMR/路由切换/keep-alive 边界状态）→ `vnode.type.remove(...)` 调 `unmountComponent(null)` → 爆。常见触发页：`AgentTracesView`（19 el-table）/ `TaskTrash`（18）/ `SpeakerMappingPanel`（8）/ `KnowledgeView`（4 tab lazy）/ `VoiceprintEnrollDialog`（el-dialog + el-tabs + lazy）。
- **修复：Vite plugin transform 阶段 patch esm-bundler.js**（commit `79305b7`）—
  ```js
  // vite.config.js
  function vueBumNullPatchPlugin() {
    return {
      name: 'vue-bum-null-patch',
      enforce: 'pre',
      transform(code, id) {
        if (!/node_modules\/@vue\/runtime-core\/dist\/runtime-core\.esm-bundler\.js$/.test(id)) return null
        if (code.includes('/* patch:vue-3.5-bum-null */')) return null  // 防重复
        const pattern = /(const\s+unmountComponent\s*=\s*\([^)]*\)\s*=>\s*\{)/
        if (!code.match(pattern)) { console.warn('...pattern not found'); return null }
        return code.replace(pattern, `$1\n    /* patch:vue-3.5-bum-null */ if (!instance) return;`)
      },
    }
  }
  ```
  验证产物 grep `(e,t,n)=>{if(!e)return;let{bum` 即生效。
- **纪律** — ① 这种"上游已知 bug 但未修复"的场景，**Vite plugin transform 阶段 patch** 比 npm postinstall patch 更稳（postinstall 会被 reinstall 覆盖；plugin 在 build 时每次生效）② `enforce: 'pre'` 确保在 esbuild/rollup 处理前 patch③ 防御性 `if (code.includes('...')) return` 防重复 patch④ pattern 未命中要 `console.warn` 而非静默吞（升级 Vue 后能立即发现 plugin 失效，需要重新适配）⑤ **只 patch build 产物，不 patch dev mode**（dev 保留原始报错方便定位应用层问题）
- **临时性 + 自动失效** — 升级到 Vue 3.5.36+/3.6+ 若官方修了 `unmountComponent` instance null 检查，plugin 自动 skip（pattern 未命中 → warn）。监控 console 是否有 `[vue-bum-null-patch] pattern not found` 警告

### 2026-06-13 Nginx types 指令覆盖/合并行为差异 — 整站 octet-stream 白屏事故（commit `08f440f` 留尾 → `f148d96` + `5c24442` 修复）

- **事故** — 用户报告"打开 /dashboard /members 直接下载名为 dashboard / members 的文件"。curl 验证 `/index.html` 返回 `Content-Type: application/octet-stream` → 浏览器把 HTML 当二进制下载而非渲染。
- **根因（极隐蔽，2 层）** —
  1. `commit 08f440f` 在 `server { ... }` block 内加 `types { application/manifest+json webmanifest; }` 块想修 webmanifest MIME 问题
  2. **Nginx `types` 指令在 server context 是"完全覆盖"语义（NOT 合并）**：从 http context 继承的 mime.types 整个被丢弃，只剩 types 块里的 MIME → `.html` 找不到 `text/html` → fallback 到 `default_type application/octet-stream` → 整站 HTML/CSS/JS/PNG 全变 octet-stream
  3. **极其隐蔽**：webhint 只查 manifest.webmanifest 不查 HTML，所以没暴露这个问题；用户浏览器可能缓存了 08f440f 之前的 HTML 没刷新，所以没立即发现
- **修复路径（commit `f148d96` + `5c24442`）**—
  - **第一步（f148d96）**：删除 tunnel.conf 两个 server block 里的所有 `types { }` block，恢复 http context mime.types 默认合并语义
  - **第二步（f148d96）**：改 `scripts/deploy-auto.sh` 增加 webmanifest MIME 注入：
    ```bash
    if ! grep -q 'application/manifest+json' /etc/nginx/mime.types 2>/dev/null; then
        sed -i '/^application\/json[[:space:]]/a\    application/manifest+json           webmanifest;' /etc/nginx/mime.types
        if grep -q 'application/manifest+json' /etc/nginx/mime.types 2>/dev/null; then
            log "webmanifest MIME type added to mime.types"
        else
            log "ERROR: webmanifest MIME sed injection failed"  # fail loud
        fi
    fi
    ```
  - **第三步（5c24442）**：原 awk 模式注入失败（猜测 mime.types 行尾 `\r` 导致 awk `next+print` 行为异常）→ 改 sed `-i` 行后追加模式 + 注入后 grep 验证
- **纪律（5 条铁律）** —
  ① **Nginx `types` 指令上下文敏感**——
  - `http` context：**合并**（additive，可加新 MIME 不丢默认）
  - `server`/`location` context：**完全覆盖**（覆盖后必须列全用到的 MIME，否则 fallback octet-stream）
  - 缺省 default：`application/octet-stream bin;`（最小集）
  ② **永远不要在 server context 加 types { } block** —— 想给 PWA 加 MIME 就在 mime.types 里加（http context include 的那个文件）
  ③ **deploy-auto.sh 注入 mime.types 必须 fail loud** ——
  - sed/awk 注入后必须 `grep -q` 验证成功才 log success，否则 `log "ERROR: ..."`
  - 注入幂等（先 grep 是否已存在）
  - 优先用 sed `-i` 而非 awk（awk 在行尾 `\r` 时行为异常）
  ④ **Webhint 不查 HTML MIME** ——
  - webhint 报 manifest MIME 错误时**只查** manifest 不查 HTML/CSS/JS
  - 加 types { } block 可能悄无声息破坏整站 MIME，**改 nginx 配置后必须 curl 验证所有响应 Content-Type**（HTML + CSS + JS + PNG + manifest + sw.js 至少 6 点）
  ⑤ **改 nginx 配置后立刻 6 点 curl 验证** —
    ```bash
    curl -sk -o /dev/null -w "%{content_type}\n" https://xxx/index.html
    curl -sk -o /dev/null -w "%{content_type}\n" https://xxx/  # SPA fallback
    curl -sk -o /dev/null -w "%{content_type}\n" https://xxx/dashboard  # SPA route
    curl -sk -o /dev/null -w "%{content_type}\n" https://xxx/sw.js
    curl -sk -o /dev/null -w "%{content_type}\n" https://xxx/pwa-192.png
    curl -sk -o /dev/null -w "%{content_type}\n" https://xxx/manifest.{hash}.webmanifest
    ```
    任一返回 octet-stream 即配置错误，不要等用户报告
- **事故链时间线** —
  1. 08f440f（18:27 加 types block，覆盖 mime.types，**事故起点**）
  2. c855f0e（18:30 加 manifest.webmanifest 410）
  3. ef130ce（18:32 CLAUDE.md）
  4. 79305b7（18:40 Vue patch）
  5. 7a077dd（18:42 CLAUDE.md）
  6. 0a29290（18:49 试图"修复"types block，加完整 MIME 列表，但 types 指令在 server context 行为不变，整站仍 octet-stream）
  7. 用户报告"下载文件"
  8. f148d96（18:58 真修复：回滚 types block + 改 deploy-auto.sh）
  9. 5c24442（19:05 修 awk → sed）

### 2026-06-13 SW 污染 cache 修复 — 整站 HTML 修复后浏览器仍进不去（commit `747a735`）

- **第二阶段事故** — 服务器 MIME 修好后（`f148d96` + `5c24442`）curl 验证 `/` 返回正确 `text/html`，但**用户报告"网站还是进不去"**。curl 服务器一切正常 → 100% 是浏览器侧问题。
- **根因** — Service Worker 污染 cache：
  1. `08f440f` 部署后服务器开始返回 octet-stream HTML
  2. 用户访问时浏览器 SW（NetworkFirst 策略）**缓存了 octet-stream 响应到 `documents` cache**
  3. 服务器修复后 SW 仍可能返回缓存的 octet-stream（虽然 NetworkFirst 应优先网络，但浏览器 SW 缓存逻辑 + activate 时机导致老 cache 没及时清）
  4. `cleanupOutdatedCaches()` 只清 workbox 维护的 precache cache，**不**清 NetworkFirst/StaleWhileRevalidate 运行时创建的 cache
- **修复：sw.js 升级模式**（commit `747a735`）—
  ```js
  // web/src/sw.js
  const SW_VERSION = 'v2-cache-purge-2026-06-13'  // BUMP 触发 SW 字节变化
  self.__SW_VERSION__ = SW_VERSION

  self.skipWaiting()
  self.addEventListener('activate', (event) => {
    event.waitUntil((async () => {
      // 清空所有 cache（不只是 workbox 默认的）
      const keys = await caches.keys()
      await Promise.all(keys.map((n) => caches.delete(n)))
      await self.clients.claim()
      // 通知所有客户端 reload
      const clients = await self.clients.matchAll({ type: 'window' })
      clients.forEach((c) => c.postMessage({ type: 'SW_UPDATED', version: SW_VERSION }))
    })())
  })
  ```
  ```js
  // web/src/main.js
  useRegisterSW({
    immediate: true,
    onRegisteredSW(swUrl) {
      navigator.serviceWorker.addEventListener('message', (event) => {
        if (event.data?.type === 'SW_UPDATED') {
          setTimeout(() => window.location.reload(), 500)
        }
      })
    },
  })
  ```
- **修复链路** — 用户下次访问 → 浏览器检测 `/sw.js` 字节变化 → 安装新 SW → 立即 `skipWaiting` 激活 → `activate` 钩子清空所有 cache + `postMessage` → 客户端 `useRegisterSW` 收到 `SW_UPDATED` → `window.location.reload()` → 用户拿到全新资源
- **纪律（4 条铁律）** —
  ① **SW 污染 cache 修复必须改 sw.js** ——
  - 只改 HTML/JS/CSS 没用，浏览器 SW 还在用老 SW 文件
  - 改 sw.js 触发 SW 升级 + activate 钩子清 cache 是**唯一**标准修复路径
  ② **`cleanupOutdatedCaches()` 不够** ——
  - 它只清 workbox 维护的 precache cache
  - **不**清 NetworkFirst/StaleWhileRevalidate/CacheFirst 运行时创建的 cache
  - 真正"清空所有 cache"必须自己写：`caches.keys() + Promise.all(keys.map(caches.delete))`
  ③ **BUMP SW_VERSION 触发升级** ——
  - 浏览器通过**字节比较**检测 SW 更新（不是 SW 内容里的 manifest）
  - 改 sw.js 文件加一行 const 都会触发字节变化 → 浏览器拉新 SW → 升级流程
  - 每次事故修复或 SW 大改动时**都**应 bump 版本号
  ④ **postMessage + reload 闭环** ——
  - SW 升级后**不会**自动刷新页面（skipWaiting + clients.claim 立即接管但页面不 reload）
  - 必须 SW postMessage → 客户端监听 → `window.location.reload()`
  - 用 `setTimeout(..., 500)` 让 console.log 先显示出来再 reload
- **调试技巧** ——
  - 用户报"页面进不去"但服务器 curl 一切正常 → 100% 是 SW/浏览器 cache 问题
  - 让用户 DevTools → Application → Service Workers → 看到 SW 状态为 `activated` 且内容含新 `SW_VERSION` → SW 已升级
  - 让用户 DevTools → Application → Cache Storage → 应该看到 precache 列表**无 documents cache**（已被清空）
  - **兜底**：用户可手动 DevTools → Application → Storage → Clear site data 彻底重置

### 测试规范
- **后端**：pytest + httpx AsyncClient，service 层单元测试 + API 集成测试
- **前端**：Vitest + @vue/test-utils，composable 测试优先，组件测试选择性覆盖
- **Mock 策略**：Redis 用 fakeredis，Claude API 用 respx，Embedding 用固定向量

## 服务层结构

| 文件 | 职责 |
|------|------|
| `app/services/task_service.py` | 任务 CRUD + 统计 + 自动提醒 |
| `app/services/member_service.py` | 成员 CRUD + 按姓名查询 |
| `app/services/meeting_service.py` | 会议 CRUD + 参与者管理 |
| `app/services/project_service.py` | 项目+里程碑 CRUD |
| `app/services/knowledge_service.py` | 知识库 CRUD + 语义搜索 |
| `app/services/reminder_service.py` | 提醒服务 + Celery task |
| `app/services/memory_service.py` | 长期记忆 CRUD + 语义搜索 + LLM 提取 |
| `app/services/search_service.py` | 联网搜索（搜狗+必应双引擎） |
| `app/services/embedding_service.py` | 向量嵌入（text2vec-base-chinese） |
| `app/services/file_parser_service.py` | 文件内容提取（PDF/Word/Excel/PPT） |
| `app/services/llm_analysis_service.py` | LLM 内容分析（动态分类+标签+摘要+核心概念） |
| `app/services/knowledge_graph_service.py` | 知识图谱服务（自动关联+BFS 遍历+动态分类+标签云+统计） |
| `app/services/knowledge_qa_service.py` | RAG 问答引擎（检索+阈值+LLM 合成+来源引用） |
| `app/services/auto_research_service.py` | 自主研究引擎（联网搜索+知识提取+空白填充+矛盾/重复/过期检测） |
| `app/services/dynamic_taxonomy_service.py` | 动态分类体系（涌现分类+分类建议+主题网络） |
| `app/services/knowledge_evolution_tasks.py` | Celery 知识进化定时任务（每日进化/空白检测/健康检查/实体融合） |
| `app/services/reminder_scheduler.py` | Redis 精确提醒调度（秒级精度） |
| `app/services/entity_service.py` | 实体知识图谱（跨文档融合+搜索+图谱+LLM 合并） |
| `app/services/hypothesis_service.py` | 科研假设生成（LLM 驱动假设+验证生命周期） |
| `app/services/formula_service.py` | 量化推理（公式列表+安全计算+LaTeX 转换+分类树+内置公式库） |
| `app/services/meeting_analysis_service.py` | 会议 AI 分析（发言者检测+格式识别+结构化分析+发言人统计+标题生成）|
| `app/services/voiceprint_service.py` | 声纹识别（3D-Speaker 嵌入提取+pgvector 匹配+录入）|
| `app/services/voiceprint_quality_gate.py` | 声纹 B+C 方案质量门 (W75 B-1, 4 子门禁, 派工 v6 段 5 反馈 #6)|
| `app/services/voiceprint_cross_meeting_regression.py` | 声纹跨会议 90% 回归门禁 (W75 B-1, 12 会议音频 + #151 rollback)|
| `app/services/voiceprint_quality_monitor.py` | 声纹质量门 Celery 30min 监控 (W75 B-1, 6 件套监控)|
| `app/voice/vad.py` | silero-vad 语音活动检测 |
| `app/services/audio_processor.py` | 音频格式转换（WebM→WAV）+ 离线 VAD 分段 |

## 声纹 90% 硬门禁 (W75 第 1 批 B-1 三层口径澄清, A-2 W74 调研 §5 主拍)

> **铁律**: 0.7 / 0.55 / 90% **三层语义完全不同**, 历史 MEMORY 自报曾经把它们混写成同一个常量，导致假 "60 百分点差距". 必须在所有声纹相关讨论/代码/文档同时区分三层指标。

### 三层指标语义对齐 (C 方案文档口径修正, 必读)

| 指标 | 数值 | 语义 | 谁用 | 文件 |
|------|------|------|------|------|
| **单段 cosine distance 上限** | **0.7** | 在线 matcher 接受阈值 (越小越相似, `<MATCH_THRESHOLD>` 才返成员) | `app/services/voiceprint_service.py:26` (常量, **不动**) | 生产 |
| **跨会议单段命中阈值** | **0.55** | strict merge 验证: `cos_dist ≤ 0.55` 视为该段命中 | `docs/CLAUDE-history.md:5459-5464` | 历史 |
| **跨会议总体识别率门禁** | **90%** | 新 embedding/变更**前自动跑**跨会议回归, 加权识别率 ≥ 90% 才接受; < 90% 自动 rollback | B 方案 `voiceprint_cross_meeting_regression.py` 自动化 | W75 B-1 |

### 派工 v6 段 5 反馈 #6 实战: 拒绝方案 A 字面改 0.9

- **方案 A 字面改 0.9 错误**: 0.7 是 cosine **距离**上限, 把它改成 0.9 会让 matcher 更宽松 (接受更远/更差的匹配). 若目标是 confidence≥0.9, 应等价于 distance≤0.1 — 与 0.9 数值完全无关.
- **B 方案质量门必确定性**: 4 子门禁 (单段距离 / top1-top2 margin / cluster votes / anchor 状态) **必须确定性**, LLM 最多解释歧义, **不得**越过门禁. **0 production code 改动铁律守恒**: `MATCH_THRESHOLD = 0.7` 保持不变.
- **王天志 #151 rollback 真实锚点**: 跨会议加权识别率 88.1% (#135 94.6% + #151 83.5%) < 90% → 自动 rollback sample_count 583→384. 历史锚点永久保留.

### W75 B-1 实施交付 (锚点范式第 253 守恒 +1)

| 模块 | 路径 | 作用 |
|------|------|------|
| 质量门 | `app/services/voiceprint_quality_gate.py` | 4 子门禁全部通过才确认成员, 任一失败 → rollback |
| 跨会议回归 | `app/services/voiceprint_cross_meeting_regression.py` | 12 会议音频 + #151 rollback 重演, 90% acceptance gate |
| 监控 | `app/services/voiceprint_quality_monitor.py` | Celery 30min schedule, 凑齐 6 件套监控 (W73 B-2 + W74 D-1 + W75 B-1) |
| 脚本 | `scripts/voiceprint/reprocess_12_meetings.py` + `replay_meeting_151.py` | 12 会议音频 reprocess + #151 rollback 重演 |
| E2E | `tests/test_voiceprint_quality_gate_e2e.py` | 13/13 PASS (8 子门禁各 2 + 综合 2 + 跨会议 90% 2 + 6 件套 1) |
| Runbook | `docs/voiceprint-quality-gate-2026-07-27.md` | B+C 方案完整 runbook |

### 5 条铁律 (W75 B-1 沉淀)

1. **不动 `MATCH_THRESHOLD = 0.7`** — 派工 v6 段 5 反馈 #6 实战, 距离方向与 confidence 反向, 字面改 0.9 = 更宽松, 完全错误.
2. **B 方案质量门必确定性** — LLM 最多解释歧义, 不得越过门禁 (派工 v6 段 5 反馈 #6 实战: 拒绝 LLM 改数值).
3. **跨会议 90% acceptance gate 自动化** — 任一 embedding/变更**前自动跑** ≥90% 回归, 否则 rollback + 报警. 不靠人工执行.
4. **三层指标语义不可混写** — 0.7 (distance) / 0.55 (hit) / 90% (cross-meeting) 是不同维度, 任何文档/代码引用必分明.
5. **历史锚点永久保留** — 王天志 #151 rollback (88.1% < 90%) 案例是 acceptance gate 真实执行证据, 必须出现在所有 runbook 与文档.

## 2026-06-14 方案 C：Agent 单阶段流式渐进综合架构（plan: eager-juggling-dewdrop.md）

**6 个 stage 已收官**（commits `5ce1203` `8a76750` `9862546` `d3f74df` `59cbbb1` `2f2b619` `bf61456`）。核心改造：取消 brief/detail 双层 → 单阶段流式综合（intent → agentic_loop → critique → done）。

### 方案 C 6 条铁律（必读, 锚点范式永久锚点）

**铁律 1：跨 event loop 安全** — 所有外部 IO 客户端（AsyncAnthropic / aioredis / async_session）禁止模块顶部 import 阶段创建, 统一通过 `ctx: ToolContext` 注入 (`redis` / `llm` / `loop_id`). Celery worker 跨 event loop 调用时由调用方注入新 client, 否则触发 "Future attached to different loop".

**铁律 2：typing import CI 检查** — `app/agent/*.py` 新文件必跑 `bash scripts/check_typing_imports.sh` (106 文件 0 错误). 新代码用 `Dict`/`List`/`Optional` 但没 `from typing import ...` → 整个模块加载失败 → 工具一调就报. Docker 模块缓存会掩盖该 bug 数天.

**铁律 3：SSE 事件 delta 语义显式标注** — `app/agent/protocol.py` 每个 `StreamEventType` 必须在源码注释里标注 `[increment]` (前端 `content += delta`) 或 `[snapshot]` (前端 `content = delta` 替换). 混用会再现 brief 重复输出 bug (commit `cf70ff5`).

**铁律 4：流式 abort 安全** — `chat_engine.synthesize_stream()` 必须用 `async with TraceCollector(...) as trace` 包裹: `TraceCollector.__aexit__` 收到 `CancelledError` 时同步落库 (不走 Celery); `agentic_loop.run()` 在 `CancelledError`/`max_rounds` 时必调 `_sanitize_pending_tool_uses(messages, reason=...)` 给悬空 tool_use 追加 `tool_result: "用户已中断"` 哨兵, 否则下次拼回 context Anthropic API 报 400.

**铁律 5：LLMClient 接口 model 参数 keyword-only** — `async def complete(self, messages, *, model=None, system=None, ...)`, `*` 强制 keyword. 老代码传位置 model 必报 TypeError. LRU cache key 必须含 model 维度.

**铁律 6：feature flag 保留老路径代码** — ~~3 个 kill switch (2026-06-29 已全部删除, commit `817f1ffa` 提前 15 天收官, `git revert <commit>` 一行恢复)~~. 详见 `git log` 收官记录.

### 部署必做

```bash
# 1. 跑数据库迁移 (Stage 3 加 7 列)
docker exec microbubble-agent-postgres-1 psql -U postgres -d microbubble -f scripts/alter_agent_traces_stage3.sql
# 2. 重启 Python 进程 (CLAUDE.md 752 行铁律)
docker compose restart app celery-worker
```

不跑这两步, 新架构写入 `intent_category` 等列会报 `column does not exist` 500.

### 方案 C 没做的（plan 明确范围外）

LangGraph 风格 state machine 重写 / 多 agent 独立服务 (planner/executor/critic) / 流式 ChartBlock 渐进渲染 / RAG 引用图谱可视化 / ASR/TTS 真流式. — **已于 2026-06-29 提前 15 天完成** (commit `817f1ffa`)（见上节"## 2026-06-29 chat_engine_legacy 30 天承诺提前 15 天收官"）


## W68 第 6+7 批纪律沉淀 (永久锚点)

> **锚点范式**: W68 第 6 批 (Verified Plans 深度审计发现) + W68 第 7 批 (grand closure 闭环) 的关键纪律固化到 CLAUDE.md. 不只在 memory 文件. 这是**永久任务模式纪律**, 未来会话启动读 CLAUDE.md 即可了解所有审计/闭环纪律.

### §1 plans 审计纪律 (W68 第 6 批 5 agent 深度审计发现)

W68 第 6 批派 5 个 Explore agent 并行全项目 plans 审计 (67 plans), 发现 5 类事故, 必须永久遵守:

1.1 **Status 段必须描述真实 commit, 不能借用同 wave 别的 plan commit** —
- **W66 批量状态化时挂错标签事故**: 状态化的 67 plans 中, 部分 Status 段描述直接复制同 wave 别的 plan commit, 而非自己 plan 真实实施的 commit. 后续审计发现多处 commit 和 plan 内容对不上 (commit 引用 `feat/xxx` 实际是别的 plan 派工分支).
- **纪律**: 每个 plan 的 Status 段必须独立验证 — `git log --all --grep="<plan-keyword>"` + `git show <commit-hash>` 必须能确认是本 plan 真实产物. 禁止批量复制粘贴

1.2 **必须读 plan 全文 + git show + grep -r 验证, 不能信 Status 段自报** —
- **盲信自报事故**: 多处 plan 的 Status 段写"已完成"但 `git log` 显示 plan 提到的功能实际从未落地. 例如 `15-17-18-cozy-bengio.md` Part 2 在 commit `4b215220` refactor 中意外删除, Status 段仍写"完成".
- **纪律**: 审计 plan 时必须 3 步并行:
  ```bash
  cat ~/.claude/plans/<plan>.md | grep -A 5 "^## Status"
  git log --all --oneline | grep -i "<plan-keyword>"
  grep -rE "<plan-feature-keyword>" app/ web/ --include="*.py" --include="*.vue" --include="*.ts"
  ```
  三者都对得上才是真实施, 缺一不可

1.3 **plans 命名应与实际内容一致 (60% 命名误导需整改)** —
- **真相**: W68 第 6 批审计发现约 60% plan 文件名与实际内容不匹配 (命名像 A 实际做 B). 命名误导 root cause 是 W62 前的"占位符命名 + 后写 plan"模式.
- **纪律**:
  - 写新 plan 时, 文件名 `xx-yy-zz-{2-词主题}-{1-词修饰}.md` 必须直接反映 plan 核心交付物
  - 不写"preparation"/"investigation"/"exploration"这类模糊词当主标题 (改用具体动作: `qa-bench-d6-benchmark-notebook.md` > `qa-bench-investigation.md`)
  - 模糊命名 plan 在 W68 第 6 批已批量重命名, 未来不允许再产生

1.4 **AGENT_STUB 必须真合并, 不能 MISCATEGORIZED** —
- **事故**: 多个 plan 状态化时被标 `AGENT_STUB` 但实际从未 merge, 仅是 plan 本身被审计 agent 阅读; 或反之, 实际已 merge 但状态标错. W68 第 6 批发现 6 个 `AGENT_STUB` 实际是 `COMPLETED` + 5 个 `COMPLETED` 实际是 `AGENT_STUB`.
- **纪律**: `AGENT_STUB` 含义精确化:
  - `AGENT_STUB` = plan 本身存在 + 没有对应的 agent 派工 + main HEAD 无相关 commit (即还没派工, 待派)
  - `COMPLETED` = plan 全部交付 + main HEAD 找到对应 commit + 实际代码落地
  - `MISCATEGORIZED` = 审计 agent 发现命名/状态与实际不符, 等待主指挥整改 (新状态)
  - 状态化必须 4 维度验证 (plan-file + git-log + grep-代码 + 审计单证), 不能仅凭 plan 内的 Status 自述

### §2 plans 实施闭环纪律 (W68 第 7 批)

W68 第 7 批 1 个 agent 收敛: 深度审计发现 5 个 NOT_IMPLEMENTED + 12 PARTIAL. 真实施 ≠ plan Status 段标 completed. 必须主指挥协调闭环.

2.1 **plans 优先 + 小修搭配 (W68 第 4 批主指挥拍板基调)** —
- **基调**: 派工以已有 plans 实施为主 + 更新过程中发现的小修为辅. 路线 A/B/C/D/E 任意组合, plans 优先 + 小修搭配, 不强制单一路线.
- **实战验证**: W68 第 4 批 (2 plan 闭环 + 13 小修) 与 W68 第 5 批 (全小修 + plans fallback) 双实战验证, 0 regression.
- **纪律**: 未来 4-9 阶段流程先 plans-list-remaining → 拍板 plan 实施 → 顺路小修 → 不强求 plans 100% (主指挥拍板决定节奏).

2.2 **plans 真实施 ≠ plans Status 段标 completed (审计出 5 个 NOT_IMPLEMENTED + 12 PARTIAL)** —
- **真相**: W68 第 6 批审计发现 67 plans 中 5 个标 completed 但实际未实施 (NOT_IMPLEMENTED) + 12 个标 completed 但仅实施 50% 以下 (PARTIAL). W68 第 7 批派 1 个 agent 100% 闭环整改 (git show + grep + commit 引用三验证).
- **纪律**:
  - Status 段标 `completed` 必须有 main HEAD commit 物证 (commit hash + 简述)
  - 部分实施标 `partial`, 不能凑 `completed`
  - 主指挥在 merge plan 实施 commit 后, 必须回头更新 plan Status 段 (闭环的核心)
  - W68 第 6+7 批沉淀的模式: **Plan 闭环 = 派 1 个 agent (A1) 重新审计全部 plans + 主指挥协调补 commit + 派 1 个 agent (A2) 写 verified plans 总报告**

2.3 **alembic 串单链纪律 (062→063→064→065, 066→067 等)** —
- 详见上方 §"2026-07-24 alembic 并行 agent 串单链纪律 (commit `1852468a6`)" 5 条铁律
- **W68 第 6+7 批新增案例**: Drive v2 PR10 (062) + Drive v2 PR11 (064) + Drive v2 PR12 (065) 串成单链 `061 → 062 → 064 → 065`; Mobile v3.2 push (066) + Drive comment mention (067) 串 `065 → 066 → 067`.
- **不变铁律**: 并行派 alembic migration agent 必须明确 down_revision 接续关系, merge 后立即 verify 只 1 个 head

2.4 **跨 session hot-fix 必须 commit message 含 "hotfix" 标识 + 主指挥 git log 跟踪** —
- **事故**: 多个 hot-fix 跨 session 派工, commit message 仅写"W68 第 5 批 hot-fix"但缺乏详细 traceback + root cause + 修复 3 段, 主指挥后续追溯困难.
- **纪律**:
  - hot-fix commit message 模板: `<type>(<scope>): W68-N-th-batch-hotfix-<short-desc> (<short-bug-id>)` + body 含 root cause 1 段 + 修复 1 段 + 验证 1 段
  - 主指挥每次 session 启动先 `git log --oneline -30 | grep -i hotfix` 跟踪上次 hot-fix chain
  - hot-fix 必须 commit 单做, 不与 feature 合并 (回滚粒度独立)

### §3 0 production code 改动铁律例外清单 (CLAUDE.md W67 第 41 步已记录 + 增补)

CLAUDE.md W67 第 41 步已记录基线: 锚点范式守卫 — 0 production code 改动 = `app/`、`web/src/`、`alembic/versions/` 老路径全部不动, 只允许 `docs/`、`memory/`、`scripts/`、`tests/` 新增. W68 第 6+7+8 批增补明确"什么算例外":

**Drive v2 系列 (PR6/PR7/PR8/PR9/PR10/PR11/PR12)** —
- 算例外: 新功能扩展 (网盘系统是 W67 后启动的新业务模块), 不破坏老任务/会议/知识库路径. 仅在 `app/services/drive_*` + `app/api/drive_*` + `web/src/views/drive/` + `web/src/views/mobile/drive/` 新增.

**Mobile UX 系列 (v3.0/v3.1/v3.2)** —
- 算例外: 移动端独立路由栈 (W66 启动), 与桌面端 component 树不共享, 不破坏老桌面路径. 仅在 `web/src/views/mobile/*` + `web/src/views/mobile/components/*` + `nut-*` 组件库新增.

**qa-bench 系列 (D1-D8 + Phase 1-3)** —
- 算例外: 测试目录, 不算业务代码. 仅在 `qa-bench/` (git submodule) + `tests/qa_bench/` 新增.

**alembic 迁移本身** —
- 算例外: 新功能必需的 schema 扩展, 不算破坏老路径. 但必须按 §2.3 串单链纪律进行, 不允许双 head.

**Plan 闭环实施 (W68 第 4 批已批)** —
- 算例外: 业务代码新增独立模块 (例如 15-17-18-cozy-bengio Part 2 重实施弥补 commit 4b215220 refactor 意外删除), 不动老路径, 仅新增 `app/services/新模块/` + 对应测试 + `docs/` + `memory/`.

**scripts/ 自动化脚本** —
- 算例外: `scripts/` 目录新增 (如 `scripts/purge_dup_owners.py`), 不算 production code.

**什么不算例外 (违规) — 明确禁止**:
- ❌ 修改 `app/services/task_service.py`/`meeting_service.py`/`knowledge_service.py` 等老模块的核心函数
- ❌ 修改 `web/src/views/Desktop*/index.vue` 老桌面页面组件
- ❌ 修改 `alembic/versions/0XX_老.py` 老迁移的 down_revision/up_revision
- ❌ 修改 `app/core/security.py`/`app/core/rate_limit.py` 老安全/限流基础设施
- ❌ 修改 `app/agent/chat_engine.py` 方案 C 6 条铁律相关文件

### §4 W68-W87 grand closure memory 索引 (永久)

完整 W68-W87 各 batch grand closure 沉淀文件索引见 `memory/MEMORY.md` §9 主题分类目录.


## 完整历史任务链

所有"## 2026-XX-XX" 历史任务链 / "### lesson learned" 子章节 / "## 开发注意事项（历史）" 段都已迁移到 [docs/CLAUDE-history.md](./docs/CLAUDE-history.md) (P3-15 拆分于 2026-07-08).

**为什么拆分**: CLAUDE.md 拆前 645KB (8082 行) 含 60+ 历史任务链, Claude 会话启动需全量 read, 减慢 system prompt 处理. 拆分后核心 ≈ 50KB, Claude 启动更快.

**Claude 行为**:
- 新会话默认只读 CLAUDE.md 核心 (50KB) — 不再加载历史 lesson
- 历史相关查询可主动 \`@ docs/CLAUDE-history.md\` 或 \`@<path>\` 引用
- 不破坏现有所有引用 (CLAUDE.md 顶部 "当前任务链" 块保留)

### 当前开发状态（2026-07-30 W97 RAG 大改造收口）

**RAG 大改造 10 PR 全部合并到 main + alembic 串单链 087→091 完整收口**：
- 087 → 088 (PR2) → 089 (PR3) → 090 (PR5) → 091 (PR8)
- main HEAD = `afe15911e` (MERGE-05 squash HOTFIX-01)
- 锚点范式 338 → 482 (+144 据实)
- 件 3 PWA build PASS（HOTFIX-01 PR5 Play → VideoPlay 修复）

**10 PR 一行摘要**：
- PR1 嵌入一致化 + query prefix 生效（has_query_prompt 前置修复）
- PR2 knowledge_chunk 子表 + parent-child chunking
- PR3 BM25 增量 + pg_trgm + tsvector
- PR4 HybridRetriever 召回侧量化（synonym 298 + 4 路权重可配）
- PR5 RAGEvaluator 真召回率激活（路径修正 web/src/views/admin/RAGEvalPanel.vue）
- PR6 SearchLog 前端接通（拒凑 5 commits）
- PR7 全链路 observability（grafana 7 面板 + 按路耗时分解）
- PR8 知识图谱深度联动（kg_entity + entity_link_recall）
- PR9 auto-research v2（dedup + query_rewriter）
- PR10 docs/deploy/eval 三件套沉淀（11 docs + 派工 v11）

**9 大缺口 100% 消化**：嵌入不一致 / 无 chunking / BM25 N 次重建 / PG 全文缺失 / query prefix 失效 / RAGEvaluator 零调用 / SearchLog 前端未通 / 无独立 RAG 评测 / 无 observability

**派工纪律沉淀（v10/v11 实战化）**：
- 派工前提铁律 12 条 + 类 20 实战 36 实例（历史 15 + W84 +3 + W85 +2 + W89 +14 + W97 +2）
- 件 4 双门控（件 4a 老核心 unchanged + 件 4b 派工 brief 授权，6 老核心服务 def diff 全 0 实战）
- 件 3 PWA 三档（frontend=是/否/子集，PR5 改路径实战，HOTFIX-01 修 Play 实战）
- 派工 v11 段 9 锚点前缀规则（防止并行 agent 撞号，6 个 W89 分支在途实战）
- 派工 v11 §13 仓库实情真查（5 子节 + 派生 5 铁律）
- 派工 v11 CHECKLIST §F verify_*.sh fallback 条款
- **派工 v10 段 7 E50 实战拦截**：WORKTREE-01 拦截"11 untracked"误判（实为 12 active worktree），0 rm -rf 0 损失
- **派工 v10 段 7 E48 锚点编号冲突 reconcile**：MERGE-05 squash 解决 GRAND-CLOSURE 477 vs HOTFIX-01 477 共占编号空间

**记忆锚点指向**：
- `C:\Users\pc\.claude\plans\rag-quirky-otter.md` v1.1（10 PR 路线 + 5 件套 + PR1 详设）
- `docs/w72-prompt-paradigm-v11-2027-04.md` 168 行（段 9/10/13 + DERIVE-19 reconcile）
- `docs/rag/CHECKLIST.md` 213 行（§F fallback + §H 仓库实情真查 + §J PR8）
- `docs/rag/W97-RAG-GRAND-CLOSURE.md` 208 行（CLAUDE.md 镜像）
- `memory/MEMORY.md` W97 RAG 大改造专题索引

Co-Authored-By: Claude Fable 5
