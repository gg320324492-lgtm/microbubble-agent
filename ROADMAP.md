# MicroBubble Agent - 路线图

> **本文件是项目未来规划 + 近期完成的高层摘要。**
> 详细 commit 流水账在 [HISTORY.md](HISTORY.md)（已存档 5730 行），权威变更日志在 [CHANGELOG.md](CHANGELELOG.md)。

## 当前状态（2026-07-24 W68 第 1 批 14+1 agents 收官 + Safari fix — 锚点范式第 30 守恒）

**W68 第 1 批跨主题收口**: 主指挥协调范式第 30 次派工 (锚点范式第 30 守恒). W68 第 1 批 14+1 agents 全部 merge 进 main (Drive v2 PR8 路线 A 7 commits + Mobile UX v3.0 路线 C 7 commits + 1 Safari iOS 空白页修复). 锚点范式单调上升 W7 12 → W66 27 → W67 28 → **W68 30**, 28+ baseline 守恒 (71 PASS + 7 SKIP, 跨 60+ commit 0 regression). 累计 8 批 42+ agent commits + W67 18+ commits + **W68 30 commits**. **0 production code 改动铁律维持** (Drive v2 PR8 + Mobile UX v3.0 + Safari fix 均不动 v1 老路径). W19 选项 A 维持. 详见 `memory/w68-grand-closure-2026-07-24.md`.

**W68 全栈交付**: 路线 A Drive v2 PR8 收官 (WS 通知增强 + 文件锁 + 预览 + 移动端 + e2e + 文档 + 协调) + 路线 C Mobile UX v3.0 (IndexedDB 队列 + iOS Safari PWA + 暗色精修 + 长按 + 响应式 + e2e + 文档) + Safari iOS 空白页修复 (SW v82→v83 + controller 兜底).

**W68 第 3 批 跨主题收口 (10 agents + 1 alembic 串单链修复, 锚点范式 30→42)**: 主指挥协调范式第 33-42 守恒. 10 agents + 1 alembic 串单链修复全部 merge 进 main — 路线 B (qa-bench D6 调研) 3 docs/memory + 路线 F (Drive v2 PR9) 3 source + 1 alembic 062/063 串单链修复 (commit `1852468a6`) + 路线 G (Mobile UX v3.1) 2 mobile + 路线 H (Drive PR9 部署 + Mobile v3.1 文档) 2 docs. 锚点范式单调上升 W68 第 1 批 30 → **W68 第 3 批 42**, 跨 72+ commit 0 regression. 累计 baseline 28+ 守恒. **0 production code 改动铁律维持** (Drive v2 PR9 是新功能扩展 + Mobile v3.1 续 + qa-bench 调研文档不动 v1 老路径). W19 选项 A 维持. 详见 `memory/w68-grand-closure-2026-07-24.md` + `memory/w68-route-{b,f,g,h}*-2026-07-24.md`.

**已交付（2026-07-22 W62 第二波 + 第三波 — Drive v2 PR6 闭环删除 + PR8 收官 + qa-bench v3.1 D1/D3/D6/D7/D8）**：

- ❌ **Drive v2 PR6 ActivityFeedView 已闭环删除（commit `d7d2e083`）** — 第三波主指挥拍板"功能没必要保留，已交付的也删除"，前端 `web/src/views/desktop/ActivityFeedView.vue` (450 行) + 测试 `ActivityFeedView.test.js` (218 行) + FolderTree 26 行引用全删；后端 `/api/v1/activities` endpoint 已删除（活动动态表 activity_events + audit log 完整保留复用）。**PR6 状态: ✅ 已交付 → ❌ 已闭环删除**（W62 第三波 2026-07-22 主指挥决策）。
- 🆕 **Drive v2 PR8a MobileKnowledgeView 移除 files tab ✅ 已交付**（commit `0e445005`）— `web/src/views/mobile/MobileKnowledgeView.vue` 移除冗余 files tab（网盘已独立 MobileDriveView），81 行新增测试覆盖。**PR8 partial → ✅**。
- 🆕 **Drive v2 PR8b MobileFilePreviewSwipe ✅ 已交付**（commit `022225d0`）— `web/src/views/mobile/MobileFilePreviewSwipe.vue`（518 行）+ `useSwipeGesture.js`（139 行）swipe 文件预览，178 行测试。`/mobile/drive/preview` 路由 + MobileDriveView 联动。**PR8 partial → ✅**。
- 🆕 **Drive v2 状态收官** — PR1-5 / PR6（已闭环删除）/ PR7 / PR8 全部收官（PR8 partial → ✅，PR6 已闭环删除）。
- 🆕 **qa-bench v3.1 D1/D3/D6/D7/D8**（commits `e53b2f79` D1 LLM config / `dd0fdc92` D3 retrieval cache / `cfdc4451` D6 CI 80% / `034d5f32` D7+D8 docs）+ final dist rebuild（`79371f98`）。

**W62 第三波（2026-07-22 晚）PR6 闭环删除段**：主指挥拍板"功能没必要保留，已交付的也删除" → 4 commit 链收口（`a132c003` 实施 → `69f5a60a` 第二波 merge → `d7d2e083` 删除 → `fa559a5d` SW 404 修复）。详见 `docs/2026-07-22-activity-feed-deletion.md` (W62 第三波 closure doc) + 5 新铁律沉淀。

## 当前状态（2026-07-22 W61 跨主题收口段 — pre-W61 88 commit (W51-W60 累计) + W61 1 commit = post-W61 89 commit + 53 memory + 58 docs + 23 baseline + 167 实战验证铁律）

**W61 502 Bad Gateway 真根因 3 层修复** (commit `2d73c9f8`): W60 22 baseline → W61 502 修复 (1 commit) → **23 baseline**. 主指挥亲自, **0 production code 改动铁律全程沿用**. 锚点范式单调上升 W60 22 → **W61 23**. **W61 502 修复穿透 3 层链路** (覆盖修正 W61 启动段原始错误 memory `nginx-ssl-cert-path-mismatch-502-2026-07-22.md`): ① 第 1 层 tunnel.conf SSL 路径 (`/etc/letsencrypt/live/...` → `/etc/nginx/ssl/...`) + 从云服务器拉证书到本地; ② 第 2 层 SSH reverse tunnel 孤儿 listener (sshd PID 1544507 session 7/20 启动 36h 占云 8000/9000/2222 端口) → `kill -9 1544507` + 重连 SSH tunnel 用 PowerShell `Start-Process -ArgumentList @(...)` 数组形式 + 双引号转义防 bash 替换空; ③ 第 3 层 `docker restart microbubble-agent-minio-1` (端口 LISTENING 但 curl 127.0.0.1:9000 返回 000, 容器内 200 OK). 6 点 curl 验证全过: `/minio/avatars/32593ab1.jpg` → 200 (23685 bytes) ✅ + HTML/SW/API/SPA/manifest 全正确. **2 新铁律** (累计 167): ① 502 排查必须穿透 3 层 (云 nginx error log → SSH tunnel listener → 目标服务响应), 不能只看云 nginx `upstream prematurely closed` 就下结论; ② PowerShell `Start-Process -ArgumentList @(...)` 数组形式 + 双引号转义环境变量, 防 bash 替换空字符串导致 SSH key 找不到. 累计 89 commit (W60 88 + W61 1), **0 production code 改动** (改的是 tunnel.conf + 部署脚本, 不属 production code).

## 当前状态（2026-07-22 W60 跨主题收口段 — pre-W60 75 commit (W51-W59 累计) + W60 13 commit = post-W60 88 commit + 50 memory + 58 docs + 22 baseline + 165 实战验证铁律）

**W51-W60 50 commit 阶段收官 final**：W58 20 baseline → W59 P3 dedup 实质开发模式首次启动 (`8f187cda`) → 21 baseline → W60 阶段收口 13 commit → **22 baseline**. W51 8 + W52 5 + W53 1 + W54 13 + W55 13 + W56 8 + W57 13 + W58 13 + W59 1 + W60 13 = 88 commit post-W60, 紧凑节奏 1.76x vs 原预排 50 commit. **锚点范式单调上升**: W2 10 → W5 11 → W7 12 → W52 13 → W54 16 → W55 17 → W56 18 → W57 19 → W58 20 → W59 21 → **W60 22** (production-grade 稳定黄金证据, 0 regression 跨 W60 13 commit). **0 production code / test / config 改动铁律沿用** (W60 不新增铁律, 165 实战验证铁律沿用). **4 future PR 4/4 不触发**: P3 dedup 已 W59 实质开发完成 (`8f187cda`), Phase 8.5 / P3 跨 tab / 7 E2E (选项 A) 仍留未来, 2026 Q4 主动排期 0. **5 pending items 5/5 100% 闭环** (沿用 W21 锚点范式). **fact-check 修正**: pre-existing fail 闭环 = 65/65 = 100% 真 fail (修正 W2 旧 64/84 = 76% 误读).

**W59 实质开发模式首次启动**: W19 选项 A → 选项 B 切换触发 (P3 dedup 用户多次反馈侧栏重复 ≥3 次), commit `8f187cda feat(chat): P3 dedup 标题时间戳 + 60s 首条消息检测` 实施. 改动 chatSessions.ts 标题时间戳后缀 + 60s 首条消息检测, vitest 25/25 PASS + web/ 699/699 PASS. W59 + W60 共同构成"W60 阶段收口 final"的两阶段闭环. 详见 `memory/p01-p02-deprecation-2026-07-21.md` + `memory/2026-07-22-final-summary-2026-07-22.md` (待主指挥拍板后 commit).


**已交付（2026-07-22 W51 启动段 + W52 跨主题收口 — 8 commit 主指挥亲自 + 0 production code 改动铁律沿用 + 13 baseline 71+7 不变）**：

- 🆕 **W51 启动段 8 commit (主指挥亲自)** — 沿用 W10 范式 5 文档同步: ① W51-1 superpowers 新增 `(grand-closure)` ② W51-2 superpowers 新增 `(baseline-13-stats)` ③ W51-3 superpowers 新增 `(multi-agent-w11)` 锚点范式 21 天实战 ④ W51-4 4 留未来 PR 触发评估单 PR (`2fa08252`) ⑤ W51-5 W51 跨主题终极收口 (`6b1bc600`) ⑥ W51-6 W11 13 次 baseline 累计数据 (`de7c67df`, σ ≈ 0.015s 历史最优持平) ⑦ W51-7 锚点范式 21 天实战 (`55dc08a6`, 165 实战验证铁律) ⑧ W51-8 4 留未来 PR 触发评估 (`0bf563c2`, 4/4 全不触发 + 选项 A 维持)
- 🆕 **W52 沿用 W10 范式 5 文档同步** — CLAUDE.md 顶部 / ROADMAP.md L6 / CHANGELOG.md L4 / MEMORY.md (双端 home dir + 项目 memory/) / CLAUDE-history.md, 5 commit cite "13 baseline 71+7 不变" (跨 18 commit 0 regression)
- 🆕 **W53 future PR 季度排期表更新** — 沿用 `docs/future-pr-roadmap-2026-07-21.md` 模板, 加 W51 trigger evaluation summary (Phase 8.5 不触发 / P3 dedup 不触发 / P3 跨 tab 不触发 / 7 E2E 选项 A 维持)
- 🆕 **跨 13 次 baseline 对齐** = W13 5 → W24 9 → W2 10 → W5 11 → W7 12 → **W52 13**, 0 regression 跨 18 commit (锚点范式单调上升)
- 🆕 **锚点 memory `multi-agent-task-orchestration-baseline.md` 实战验证 100% 适用** — 4 阶段标准流程 + 11 协调铁律在 76 commit / 90 任务 / 22 worker 实战中 0 偏离, 165 实战验证铁律

**未来待做（3 留未来 PR；P3 dedup 已于 W59 实施完成并移出列表）**：

| PR | 风险 | 一次性投入 | 触发条件 |
|---|---|---|---|
| Phase 8.5 异地冷备 (USB HDD) | 🟢 P4 | ¥2,000 + 1 人天 | 勒索软件事件 / 合规要求 |
| P3 跨 tab 同步 | 🟢 P3 | 0.5-1 人天 | 多 tab 用户反馈 ≥10 条/月 |
| 7 E2E 真闭环 | 🟢 选项 A | 1-2 人天 (选 B 启用) | 主指挥决策变更 (当前 维持 选项 A) |

- 详细排期: `docs/future-pr-roadmap-2026-07-21.md`
- 拍板记录: `docs/future-pr-decision-2026-07-21.md`
- W21 主指挥协调范式实战总结: `memory/multi-agent-coordination-grand-closure-2026-07-21.md`

## 当前状态（2026-07-20 — Multi-agent 协调范式锚点 + P2 候选 3/3 全部完成）

**已交付（2026-07-20 本会话新增 — 9 批 multi-agent 任务 + 17 commit + 8 memory 沉淀）**：

- 🆕 **Multi-agent 协调范式锚点 memory** — 4 阶段流程 (出指令 / 监控 / 审核+合并 / 上线+沉淀) + 5 协调铁律 (总指挥 ≠ 总执行 / 多 worker stash 隔离 / 严禁 main commit / 边界立即拍板 / 6 点 curl 硬指标) + 6 技术铁律 (默认值改动 4 重证据 / 测试契约漂移优先改测试 / rejection matcher 提前注册 / 配置改动 commit cite 证据 / 测试 fix ≠ 改生产代码 / pre-existing fail 优先改测试). 详见 `memory/multi-agent-task-orchestration-baseline.md`.
- 🆕 **W2 T3 审计 + P2 候选 3/3 全部完成** — 锚点 memory 提到 `sessionPollingInterval` 字面量在代码库 0 匹配, 回归到真实代码语义, 5 项审计 + 3 P2 候选全部当日完成:
  - **P2-A 过期 chat_share Celery 清理** (commit `a37ef09b`) — 复用 PR6-P10 backup_before_delete 范式, 8/8 pytest
  - **P2-C KB polling + chat fetch 30s timeout** (commit `f3e637cf`) — axios timeout 30s, 43 vitest PASS
  - **P2-B localStorage chat session 90 天 TTL** (commit `1a0ecbed`) — lazy migration + 过期清 3 key, 20/20 vitest
- 🆕 **W5+1 follow-up 4 层全闭环** — Redis LTRIM 200 契约回归 + monkeypatch sys.modules 污染 + pytest.ini loop_scope=function + app/core/redis.py lazy init. 4 commit 链: `081c55e8` → `f9130c34` → `641e402f` → `ca0fb0a3`.
- 🆕 **W2 留尾闭环** — useDriveFiles batchDownload 无 try/catch 修复 (commit `eafb2f47` round 2). **新铁律**: composable 方法风格必须统一 / 错误 fallback 文案兼容多 envelope / 测试断言反映真实契约.
- 🆕 **P0 上线 (#009 Self-RAG 删除)** — `7046fbbf` + `9301b0de` merge fix/office-preview-sandbox → main. 7/14 R5/R6 deep mode 6 轮 benchmark 证伪 7/13 commit `c2648120` "Self-RAG 防 deep 幻觉" 假设, 30 天承诺提前 30 天收官. 13+ 文件 (139 +4209/-12093).
- 🆕 **录音全链路 10 commit 上线** — MIME 探测 + getUserMedia 5s timeout + cancel endpoint + UA 落库 (alembic 060) + orphan cleanup + post_meeting NameError 修复. 详见 `memory/recording-comprehensive-fix-2026-07-16.md`.

**未来待做 (P3 收尾)**：
- 5 个 active fix/feature 分支清理 (等下次会话 24h 缓冲期)
- 僵尸 worktree 目录清理 (`.git/worktrees/agent-ac0b4b1084844e58b` 空目录)
- pytest-asyncio pre-existing fail 修复 (test_maxlen_200 单文件 fail, 根因 redis pool 单例绑首次 loop, W1 已修)

## 当前状态（2026-07-12 — chat-ux P0 三连修收官 + 工作树整理清零）

**已交付（2026-07-12 本会话新增 — P0-#1+#1.5+#1.6 + P0-#2 + Playwright PNG cleanup + 文档同步）**：

- 🆕 **chat-ux P0 三连修 + 工作树整理清零（11 commit 全 push origin/main）** — 详见 `memory/p0-2-chat-jump-to-top-bouncing-2026-07-12.md` + `memory/playwright-screenshot-cleanup-2026-07-12.md` + `memory/llm-backend-ollama-residual-connection-error-2026-07-12.md` + `memory/anthropic-msg-dict-wrapper-mimo-reasoning-content-2026-07-12.md` + `memory/session-load-server-fetch-fallback-2026-07-12.md` + `memory/ensure-session-loaded-cache-hit-orphan-2026-07-12.md`. 关键 commit 链:
  - **P0-#1 `.env LLM_BACKEND=ollama 残留`**: `20621c83` 仅 `.env` + force-recreate (`docker compose restart` 不重读 env_file 是大坑第 N 次踩)
  - **P0-#1.5 `_AnthropicMsgDict` wrapper**: `9b908f50` 4 文件 +263/-6 (dict 子类 `__getattr__` 递归包装实现 `resp.content` + `resp["content"]` 双访问后向兼容 12 caller, mimo reasoning_content wrap 成 `{type:thinking, thinking:...}` block, intent_classifier max_tokens 300→2048)
  - **P0-#1.6 v1 `ensureSessionLoaded` server fetch fallback**: `65d4493b` 4 文件 +128 (修左侧 session 列表 `hello (8 小时前 2 条)` 但点击进入主区空白)
  - **P0-#1.6 v2 orphan session `localStorage='[]'` 误判**: `a687cee7` 3 文件 +121 (加 `serverFetchedSessions` Set 独立追踪 + `parsed.length > 0` 才视为 cache hit)
  - **P0-#2 v1 `position: sticky`**: `494b2917` 3 文件 (修 ↑ 按钮 scrollTop>0 被卷出可见)
  - **P0-#2 v2 `&:active { transform: none }`**: `c2b1e50a` + 60fps 验证 (4 Playwright spec 修点击抖动反馈)
  - **P0-#2 v3 60fps 用户视角验证**: 同 commit `c2b1e50a` (real-user-flow / button-bouncing / final-verify / jump-to-top)
  - **P0-#2 v4 `transform: none !important` 防御 EP active transform**: `da94ce74` 1 文件 + dist
  - **P0-#2 audit 收尾**: `43383798` 仅留 60fps 用户视角 spec `p0-2-bounce-recv2.spec.mjs` 146 行
  - **Playwright PNG cleanup**: `c154f5d5` 1 .gitignore + 54 PNG 删除 (6.1MB, 7 历史 commit 来源: c2b1e50a / 0c1ed72c / e6b1ed64 / ff30e010 / 1dd92414 / 648b863b / bd00b692) + `.gitignore` 加 `web/tests/visual/**/screenshots/` glob 永久排除
  - **文档同步**: 本 commit (CLAUDE.md / README.md / ROADMAP.md / CHANGELOG.md / memory/MEMORY.md 全部更新)

- 🆕 **核心铁律沉淀 (12 条, 跨 3 个任务)** —
  - **P0-#1+#1.5**: `.env` 改动必须 force-recreate / wrapper shape 与 caller 期望必须对齐 / OpenAI thinking 模型 reasoning_content 必须 wrap / mimo-v2.5 max_tokens 至少 2048 / `for block in resp.content` 是 anthropic backend 假设
  - **P0-#1.6**: localStorage 不能唯一数据源 / server fetch 失败 best-effort / cache hit 必须看内容 `parsed.length > 0` / cache hit + server fetch 是不同维度必须独立 Set 追踪 / Playwright 验证 cloud dist 必看 served index hash
  - **P0-#2**: `position: sticky` 优于 `fixed` / EP active transform 必须显式禁用 / 60fps 验证优于静态截图 / `!important` 不是 anti-pattern 是 specificity battle 工具 / visual bug 修复必须 audit trail
  - **PNG cleanup**: Playwright 截图不进 git / 真正的 visual regression baseline 走 `*-snapshots/` / audit trail 在 commit message 不在 PNG / 6MB PNG 7 commit 累积就是隐患 / `git rm --cached` + `.gitignore` 双管齐下

- 🆕 **端到端验证清单** —
  - [x] P0-#1: curl SSE 验证 text_delta 正常 "你好！很高兴收到你的消息 🙋‍♂️..."
  - [x] P0-#1.5: curl 60s 验证 `intent_detected reasoning='用户询问 dutonghe是谁, 属于查找人员信息, 因此归类为search_info' + label 置信度 95%` (vs 旧 0%)
  - [x] P0-#1.6 v2: Playwright v2 回归 `.bubble count: 41` ✅ 与 server list count=41 完全一致 (修复前 v1 后 v2 前只渲染 38 条)
  - [x] P0-#2 v4: 60fps 采样 `delta = 0px` ✅ 按钮 y 位置完全稳定 (阈值 >4px 报失败)
  - [x] PNG cleanup: `git rm` 54 个 PNG, working tree clean, commit `c154f5d5` push 到 origin/main

## 当前状态（2026-07-09 — Drive 全家桶全面美化收官 + 待做清单核对沉淀）

**已交付（2026-07-09 本会话新增 — 文档同步 commit + 待做清单核对沉淀）**：

- 🆕 **Drive 全家桶全面美化收官 (5 commit 链 + 1 测试 commit, 全部 push origin/main)** — 详见 `memory/drive-view-beaute-2026-07-09.md`. 19 文件改动 (1 css + 1 mobile view + 1 desktop view + 13 子组件 + 2 test + 1 __init__ dir), 15 vitest PASS. 关键 commit 链: `295848df` (CSS+View) → `782c92b` (FileCard+Grid) → `0788f8bd` (FolderTree+Toolbar+chip) → `196cd9e` (10 dialog 玻璃态) → `7d5bfb0` (mobile 镜像) → `04c7fd2` (15 vitest PASS).

- 🆕 **待做清单核对沉淀** — 详见 `memory/2026-07-09-pending-items-audit.md`. 5 项未完成: PR6-P18 admin 填值 / Self-RAG 收尾 / voiceprint_relaxed 追踪 / MemberCreate schema / Phase 8 异地容灾.

- 🆕 **文档同步 (本会话 commit)** — CHANGELOG.md / README.md / ROADMAP.md 顶部加 2026-07-09 段落 (Drive 美化收官时漏补文档, 本次补齐).

**已交付（2026-07-08 本会话新增 — 30 个 commit 全部 push origin/main）**：

详细 commit 列表见 [CHANGELOG.md](CHANGELOG.md) 顶部 [Unreleased] 段, 总览见 `memory/2026-07-08-25-bug-fix-batch.md`.

- 🆕 **P0 必修 4 个** — 修生产事故 + 数据丢失:
  - `51d7e90f` celery worker 启动 ImportError 死循环 (17 天 backend 任务全死)
  - `badc9701` + `cb847755` Windows Task Scheduler 备份 (修 18 天无备份)
  - `68171064` mimo 429 fallback to ollama (修用户 5xx)
  - `043db721` fill_wechat_id_placeholders closure bug (修 admin 误传)

- 🆕 **P1 必修 5 个** — 修用户日常痛点 + 数据完整性:
  - `89487992` `_assert_identifier_unique` 跳过 placeholder 字符串
  - `9c905f6f` AudioRecorder meetingTitle reactive (修死路径)
  - `5e5289e5` useMentionAutocomplete name 字段统一 lowercase (修中文 mention)
  - `a3a3c43e` 5s dedup + markAllRead 语义冲突 (修用户漏看)
  - `74c206f4` SSH tunnel onboarding (替代 frp 死代码 + onboarding 文档)

- 🆕 **P2 必修 9 个** — 设计瑕疵 / 防御性:
  - `2e96d738` comment_service 同步删 file_mentions reply mention
  - `f104b9c6` dedup 保留首次 mention preview (不覆盖)
  - `ab734026` `_expand_concept_to_four_domain` 4 域前移 (修概念问答案质量)
  - `aa1486d3` NotificationBell `var(--color-bg-card-dark)` → `var(--color-bg-card)` (dark 模式)
  - `cfbe4754` mention-tag 改用 `var(--color-primary-rgb)` 透明度可调
  - `e17da752` useCommentTree cycle 检测防栈溢出
  - `53275f20` KnowledgeView filter 切换重置 currentPage 回归测试
  - `d50a0f64` migrate_kb_source_type docstring 180→179 同步
  - `d27d2263` migrate_kb_tags.py 加 SCOPE_ALL 选项
  - `3db3f6b4` pgvector embedding round-trip 端到端测试 (1024 维验证)
  - `f454b69c` restore_from_backup --upsert 改两步法 (PG 17 兼容)

- 🆕 **P3 修复 5 个** — 防御性 / 跨平台:
  - `4e0349fe` pre-commit hook head_dist case glob 改 `grep -qFx` (POSIX sh 严格兼容)
  - `09755234` SW Background Sync 排除 SSE 端点 (防重试让用户收不完整流)
  - `f8c33ecc` SW Notification 错误 `console.log` → `console.warn` (DevTools 可见)
  - `15aecfa4` webhook.py path 提取 query string 后再匹配
  - `bb949281` lint-css.yml 加 webhint CSS a11y 步骤
  - `c09bd10c` NotificationBell file type 颜色 token 化 (variables.css 加 4+4 token)
  - `5777b10b` CommentItem `data-depth="3"` selector 预留
  - `4f0e1e2c` install-frps-systemd.sh ss 命令 fallback netstat
  - `44569e17` **CLAUDE.md 拆分** (新会话启动 -81% read 量)

- 🆕 **非 bug 跳过 (6 个)** — 验证后无需修:
  - P3-4 memory_service 顶层 import (P0-1 已修)
  - P3-5 celery-beat alembic volume (beat 不跑 alembic)
  - P3-8-补丁 docker-compose.override.yml version (文件被 .gitignore)
  - P3-10 .env APP_ENV=production (文件被 .gitignore)
  - P3-13 _complete_openai_compat 日志 (P0-3 已有 5+ logger)
  - P3-14 frpc wrapper 清理 (P1-10 替代为 SSH tunnel, README 已写)

**新铁律 (本会话沉淀 13 条)**：

1. 模块级禁止副作用 (构造客户端/加载模型/连接 DB) — 全部走 lazy 函数
2. async session 必须显式 `await db.commit()` (with 退出默认 rollback)
3. backend-level fallback 必须用临时 client, 不修改 `self.backend`
4. 内层循环不要引用外层 closure 变量 — 用反查 dict 或 enumerate(zip(...))
5. filter 字段必须全部走统一的大小写处理 (lowercase + compare with ql)
6. dedup 查询条件按 (receiver, file, context, time window) 过滤, 不要按 is_read
7. dedup 命中区分 '静态内容' (title/body) vs '动态元数据' (mentioned_by/count/timestamp)
8. tree/recurse 构建前必须做 cycle 检测 + 防御性 maxDepth
9. PG UPSERT 行计数不可靠 (跨版本 + tuple move), 优先用两步法
10. sh 脚本里 list 字符串匹配优先用 grep/awk, 不要依赖 case glob 跨多行
11. Background Sync 路由 match function 一定要排除所有流式端点 (SSE/WS)
12. HTTP path 匹配必须用 `urlsplit(path).path` 提取 pathname 部分
13. CLAUDE.md 应该 < 150KB (< 1000 行), 历史任务链拆到 docs/CLAUDE-history.md

**端到端验证方法 (每项必跑)**：

- **后端 (P0/P1/P2)**: `SKIP_DB_SETUP=1 docker exec -w /app microbubble-agent-app-1 python -c "<mock script>"` 容器内跑真实 DB
- **后端 (alembic)**: `docker exec microbubble-agent-db-1 psql -U postgres -d microbubble -c "<SQL>"`
- **前端 (P2)**: `cd web && npx vitest run <test-file>` 跑单测
- **前端 (P3)**: `cd web && npm run build` + `grep` 静态检查
- **运维 (P3)**: `bash -n script.sh` syntax + `MSYS_NO_PATHCONV=1 docker exec ... python <test>`

## 当前状态（2026-07-02 晚班 — v2 网盘 PR6-P15 personal_wechat_id + 听会 v4 + LLM 3-Way 收官）

**已交付（2026-07-02 晚班新增）**：

- 🆕 **v2 网盘 PR6-P15 personal_wechat_id case-insensitive uniqueness（commit `5bab3f15`）** — 6 文件 / +546 行 = **alembic 055 `UNIQUE INDEX ON LOWER(personal_wechat_id)` 兜底 + service `_IDENTIFIER_COLUMNS` 白名单扩到 3 列 + `_COLUMN_LABELS` 中文 label map + API POST/PUT 双保险预检查 + 20/20 pytest PASS + 65 passed, 9 skipped, 0 fail 合跑无回归 (PR6-P13 17 + PR6-P14 20 + PR6-P15 20 + drive_notification 8)**. 触发场景：当前 35 行 members 全部 `personal_wechat_id` 为空字符串 (psql 验证), `app/wechat/identity.py:79` `resolve_by_wechat_id()` 当前精确匹配, 但**未来若改 `lower()` 对齐 PR6-P4 mention 3 路模式**, 同样会有 map 撞车风险. 提前兜底比事后清理成本低 10×. 附带修复 `.gitignore` 防 `.ollama/id_ed25519` SSH 私钥泄漏. **3 层防御**: ① alembic 055 函数索引兜底真唯一 ② service `_IDENTIFIER_COLUMNS` 白名单 + `_COLUMN_LABELS` dict 中文 label ③ API POST/PUT 双保险预检查.

- 🆕 **听会 v4 三件套修复（commit `2cde346f`）** — 3 文件 / +36/-12 行 = **中文文件名下载 RFC 5987 + 文件夹拖拽层级 + 录音 chunked path meeting context**:
  - **修复 1**: `app/api/v1/drive_files.py:build_content_disposition` 抽 helper, 仅输出 `filename*=UTF-8''<encoded>` (RFC 5987 标准化形式), 旧 `filename="中文.pptx"` 部分走 latin-1 codec 触发 `UnicodeEncodeError` 500 (用户实测触发: "组会ppt/冯懿鑫/2025.7.2 研一 冯懿鑫.pptx"), 4 处调用点统一
  - **修复 2**: `web/src/composables/useFolderDropZone.js` 删错误赋值 `file.webkitRelativePath = relativePath` (native read-only getter 静默忽略, Firefox 拖拽场景 relativePath 全 undefined), 改用 entries 数组直接存 relativePath 字段
  - **修复 3**: `web/src/views/MeetingRoomView.vue` AudioRecorder 显式 `:meeting-id="meetingId"` + `:meeting-title="pageTitle"` (lazy computed 不传 prop 读不到值, chunked upload 路径触发后丢失 meeting context)
  - **配套 commit 链**: `38487056` (v2) → `6c297703` (v3) → `7d0daadf` (chunked rate-limit) → `2cde346f` (v4 收官)

- 🆕 **LLM 3-Way Benchmark (mimo cloud vs qwen3:8b vs qwen3:14b) 收官** — **生产决策: 保持 `LLM_BACKEND=openai_compat` (mimo cloud), 8b 作 offline fallback**:
  - 10 题 subset: mimo 50% (5/10) ≈ qwen3:8b 50% (5/10) **平局**, 加权综合分 mimo 0.937 > 8b 0.906
  - 35 题完整: mimo 14.3% > 8b 11.4% (2.9% 差距)
  - qwen3:14b (9.27GB Q4_K_M, 14.8B params): 单题 40-230s (8b 的 5-10×), 80% 题 duration_too_long, 通过率反低 30% — 不适合实时对话
  - 5 文件: `docs/llm-benchmark-2026-07-02.md` (263 行) + 4 个 benchmark 报告目录 + reranker 跨模型评估 + `memory/llm-benchmark-2026-07-02.md` (7 铁律) + `tests/manual-test/playwright-e2e-recording.mjs`
  - **7 新铁律**: ① clash 代理必需 ② docker run 路径必须 `MSYS_NO_PATHCONV=1` ③ Ollama `--network host` bind IPv6 only 必须 `-p 11434:11434` ④ `docker compose restart` 不重读 env_file ⑤ qwen3:8b 是 cloud 备选不是替代品 ⑥ qwen3:14b 慢 4× 且通过率反低 ⑦ mimo openai_compat 3 大待修 (fake_xml_leaked / duration_too_long / intent_mismatch)

---

## 历史状态（2026-07-02 午班 — v2 网盘 PR6-P11 收官）

**已交付（2026-07-02 午班新增）**：

- 🆕 **v2 网盘 PR6-P11 Celery retention 二次确认守卫** — 5 文件 + 14 单测 / +213 行 = **3 个 Celery cleanup task 顶部统一守卫 + 新模块 `app/services/cleanup_safety.py` 双重 API**。继 PR6-P9 误传 `retention_days=0` 删 31 条 / PR6-P10 backup_before_delete + restore CLI 之后的**第二道防线**：retention ≠ settings 默认值时，延迟 `RETENTION_OVERRIDE_CONFIRM_DELAY_SEC=0.5s` + logger.warning 二段打印，让人手能在 0.5s 内 Ctrl+C 取消。双重 API：
  - `confirm_retention_param` — 延迟 + warn + proceed=True（用户友好，3 task 默认走这个）
  - `confirm_retention_param_or_skip` — 严格模式，非默认就拒绝（留给未来 critical 场景如 Sentry 监控）

  **首次集成测试踩坑（永久教训）**：测试之前没真 mock service，守卫 proceed=True 后 task 真跑 cleanup → **真 DELETE 了 4 条 chat_sessions**。用 PR6-P10 `restore_from_backup.py --apply --confirm` 救回。测试改用 `_make_async_return(0)` mock service 返 0 行 — 守住"测试只验证守卫被触发，不真删数据"。

  **5 新铁律（永久沉淀）**：
  1. **Celery retention 类参数必须 `confirm_retention_param` 守卫**（3 task 顶部统一 import）
  2. 默认值 == settings 默认时**不触发**守卫（`task.delay()` 永远走 None 路径不延迟）
  3. 延迟秒数从 settings 读，紧急场景可设 0 关闭
  4. 测试时必须 mock service 函数返 0，守卫 proceed=True 后面是真 destructive cleanup
  5. 严格版 `confirm_retention_param_or_skip` 留给 critical 场景，默认 3 task 用友好版

  **端到端验证**：pytest 14/14 PASS + 3 task 集成测试模拟 retention=0 误传，守卫 delay + warn 触发成功，0 真 DELETE。`settings.RETENTION_OVERRIDE_CONFIRM_DELAY_SEC` 可在 `.env` 调：0.5 默认 / 0 紧急关闭 / 2.0+ CI 审计。

  **互补 PR6-P10**：
  - **PR6-P10** (backup_before_delete) — 即便 DELETE 真发生，先 JSON 备份 + restore CLI 可恢复
  - **PR6-P11** (cleanup_safety) — 守卫提前拦截，让 DELETE 不发生（延迟时人手可 Ctrl+C）

  详见 [memory/v2-drive-pr6-p11-cleanup-safety-guard-2026-07-02.md](memory/v2-drive-pr6-p11-cleanup-safety-guard-2026-07-02.md) 完整复盘。

**详细文件改动**：
| 文件 | 操作 | 行数 |
|------|------|------|
| `app/services/cleanup_safety.py` | 新建 — `confirm_retention_param` + `confirm_retention_param_or_skip` 双重 API | +115 |
| `tests/test_cleanup_safety.py` | 新建 — 14 单测（8 unit + 3 or_skip + 1 settings + 4 integration） | +155 |
| `app/config.py` | 新增 `RETENTION_OVERRIDE_CONFIRM_DELAY_SEC: float = 0.5` | +7 |
| `app/services/chat_history_tasks.py` | 顶部加守卫 + skippable return | +18 |
| `app/services/drive_cleanup_tasks.py` | 同上 | +19 |
| `app/services/file_mention_tasks.py` | 同上 | +18 |
| **合计** | **5 文件 / +213 行** | |

**统计（commit pending）**：参见 `app/stats.json` 自动重算（本次新增 4 文件 + 修改 4 文件）。

---

## 历史状态（2026-07-01 早班收官）

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

**最新里程碑（2026-07-21 — Phase 8 完整闭环 + 6 次 baseline 对齐）**：

- 🆕 **Phase 8 完整闭环** = 8.1 本地 backup + 8.2 通用 restore CLI + 8.3 阿里云 OSS cloud 镜像 (commit `e4d58bd6`) + 8.4 OSS 恢复测试 (commit `e79a127b`, RTO < 1h SLA 验证). 详见 [`memory/phase-8-cloud-mirror-2026-07-21.md`](./memory/phase-8-cloud-mirror-2026-07-21.md).
- 🆕 **6 次 baseline 对齐（0 regression）** = W2 T2 → W17 T2 跨 33 commit 0 regression. 平均 2.13s. 详见 [`memory/w16-baseline-six-runs-closure-2026-07-21.md`](./memory/w16-baseline-six-runs-closure-2026-07-21.md).
- 🆕 **5 pending items 5/5 100% 闭环** (含 Phase 8 实施).
- 🆕 **W5+1 follow-up 11 commit 终极闭环** = redis.py lazy + database.py lazy + get_event_loop fallback + 2 test 期望漂移 + conftest 跨 scope lazy + setup_db scope fix + model import + sessionmaker 优化 + useChatStream onUnmounted timer cleanup. 详见 [`memory/w5-plus-one-followup-grand-closure-2026-07-20.md`](./memory/w5-plus-one-followup-grand-closure-2026-07-20.md).
- 🆕 **今日 (2026-07-21) 累计 48 commit + 13 memory + 73 任务**. 详见 [`memory/today-closure-2026-07-21.md`](./memory/today-closure-2026-07-21.md).

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

## 🆕 待做：产品扩展（商业化 + 多组织 + 桌面 + APP）

> **2026-06-28 决策沉淀**：在 Phase 7~20 现有高优/中优/低优路线图基础上，新增产品级扩展方向。完整规划见 [docs/product-expansion-plan.md](docs/product-expansion-plan.md)（待补充）+ plan 文件 [C:\Users\pc\.claude\plans\exe-logical-pie.md](C:/Users/pc/.claude/plans/exe-logical-pie.md)。
>
> **核心战略**：1 个前置 P0（40 人天，单租户内打地基）+ 6 个 Phase（24 人月 / 18 月工期）。从"内部 Web 工具"→"多组织 SaaS + 桌面 + 三端 APP"。

### 前置 P0（必须先完成，否则后期改造 10 倍成本）[40 人天]

- [ ] **#PRE-001** [5d][infra][P0] 24 张表加 `organization_id` 占位列（NULL 允许）+ GIN 索引 — **多租户改造前置占位**
- [ ] **#PRE-002** [8d][auth][P0] OAuth provider 抽象层 + JWT refresh rotation 框架
- [ ] **#PRE-003** [5d][infra][P0] PG 备份 + 监控 + 慢查询日志（pg_stat_statements + P95 < 200ms 告警）
- [ ] **#PRE-004** [4d][frontend][P0] 前端 API 层加 `X-Organization-ID` header 透传 + Pinia store 改造
- [ ] **#PRE-005** [6d][infra][P0] 审计日志中间件（写操作 + 登录 + 切换组织 + 异步队列 + 归档）
- [ ] **#PRE-006** [4d][infra][P0] 限流扩展到组织维度（5 tier → 组织 × 用户双维度）
- [ ] **#PRE-007** [5d][backend][P0] Celery 任务加 `organization_id` 上下文传递（`task_context` 装饰器）
- [ ] **#PRE-008** [3d][infra][P0] 部署架构文档化（Docker Compose 9 服务拆分到 K8s / 阿里云 ACK）
- [ ] **#PRE-009** [30-60d][legal][P0] **软著申请（中国版权中心，不可压缩 30-60 天，今天就启动）**
- [ ] **#PRE-010** [5d][legal][P0] 法务合规检查（个保法 + 数据安全法 + 用户协议 + 隐私协议 + 科研数据出境评估）

### Phase 0：正式数据库 [3 人月]

- [ ] **#P0-001** RDS PostgreSQL 16 HA 主从迁移（阿里云，自动备份 7 天 + PITR）
- [ ] **#P0-002** pgvector HNSW 索引重建（数据量 > 1000 万时 HNSW 优势明显）
- [ ] **#P0-003** Prometheus + Grafana + AlertManager（CPU / 内存 / 连接数 / 副本延迟）
- [ ] **#P0-004** Loki + Promtail 日志聚合（替代 SSH 看日志）
- [ ] **#P0-005** Sentry 前后端错误聚合
- [ ] **#P0-006** 9 个 Docker 服务拆分到 K8s namespace
- [ ] **#P0-007** 阿里云 OSS 冷数据归档（90 天后转归档存储）
- [ ] **#P0-008** 灾备演练：RPO < 5 分钟，RTO < 30 分钟

### Phase 1：认证扩展 [3 人月]

- [ ] **#P1-001** OAuth provider 抽象层（`app/services/auth/providers/base.py`）
- [ ] **#P1-002** 阿里云短信 SDK（手机号验证码，5 分钟 TTL，防刷 1 分钟 1 次）
- [ ] **#P1-003** 微信开放平台网站应用（PC 扫码登录，14 步标准流程）
- [ ] **#P1-004** 微信开放平台移动应用（独立 appid，资质认证 600 元/年）
- [ ] **#P1-005** JWT refresh token rotation（24h access + 30d refresh，单次使用）
- [ ] **#P1-006** 双因子认证（组织维度配置，可开关）
- [ ] **#P1-007** 设备指纹 + 异地登录告警
- [ ] **#P1-008** 密码强度策略升级（zxcvbn 评分）
- [ ] **#P1-009** 第三方登录首次绑定手机号流程

### Phase 2：多组织 SaaS [6 人月] ⚠️ **最高优先级**

- [ ] **#P2-001** `organizations` + `org_members` + `org_invitations` 表
- [ ] **#P2-002** PostgreSQL Row Level Security（RLS）策略，24 张表全加
- [ ] **#P2-003** `OrganizationMixin` + SQLAlchemy event listener（自动注入 WHERE）
- [ ] **#P2-004** API 层 `Depends(get_current_org)` 强制校验
- [ ] **#P2-005** 子域名路由（`{org_slug}.agent.example.com` + Let's Encrypt 通配 HTTPS 证书）
- [ ] **#P2-006** 组织切换器（Web 顶栏 + 移动端 + 桌面托盘菜单）
- [ ] **#P2-007** 创建 / 加入 / 邀请组织流程（链接 / 二维码 / 邮件，72 小时过期）
- [ ] **#P2-008** 三级 RBAC（组织管理员 / 普通成员 / 访客）
- [ ] **#P2-009** 组织级配额（成员数 / 存储 / API 调用 / GPU 分钟数）
- [ ] **#P2-010** 数据迁移脚本（现有 20 人数据合并到默认"原始课题组"组织）
- [ ] **#P2-011** 灰度方案（先 1 个外部组织白名单，全量后 30 天清理）

**3 层数据隔离防御**：API 层（`Depends(get_current_org)`）+ ORM 层（`OrganizationMixin`）+ DB 层（PG RLS 兜底）

### Phase 3：桌面 EXE [4 人月]

- [ ] **#P3-001** Electron MVP（Windows + macOS + Linux）
- [ ] **#P3-002** Tauri 并行试点（验证可行性，3 月后决策）
- [ ] **#P3-003** 自动更新（Electron Updater / Tauri updater）
- [ ] **#P3-004** 系统托盘 + 全局快捷键（Ctrl+Shift+A 唤起搜索）
- [ ] **#P3-005** 离线缓存（IndexedDB + Service Worker）+ 增量同步
- [ ] **#P3-006** Windows EV 代码签名（DigiCert ¥4000/年）
- [ ] **#P3-007** macOS Developer ID 签名 + Notarization 公证
- [ ] **#P3-008** Linux AppImage / deb / rpm 三格式打包
- [ ] **#P3-009** 协议注册（agent:// scheme）+ 文件关联（.pdf / .docx 拖入）

### Phase 4：移动 APP [6 人月] ⚠️ **最大工程量**

- [ ] **#P4-001** Flutter 3.24+ 框架定型（Dart 3.5）
- [ ] **#P4-002** 业务逻辑 TypeScript → Dart 移植（或 WebView 容器嵌入 H5 保守方案）
- [ ] **#P4-003** 微信开放平台移动应用 appid（独立申请）
- [ ] **#P4-004** 极光推送 JPush（多厂商通道：华为 / 小米 / OPPO / vivo / 魅族 / iOS APNs）
- [ ] **#P4-005** iOS TestFlight 内测（90 天有效期）
- [ ] **#P4-006** App Store 上架（首次 2-4 周审核，避免 4.7/4.2 拒绝）
- [ ] **#P4-007** Android 华为应用市场上架（最严，软著必填）
- [ ] **#P4-008** Android 小米 / OPPO / vivo / 应用宝多商店上架
- [ ] **#P4-009** 鸿蒙 NEXT 适配（Flutter 鸿蒙版 alpha 或原生 ArkTS 重写，预留 ¥30-50 万）
- [ ] **#P4-010** ICP 备案 + 公安备案（7-15 工作日）
- [ ] **#P4-011** 移动端专属（摄像头扫码 / 生物识别 / 后台保活）
- [ ] **#P4-012** 离线缓存（SQLite / Hive）+ 增量同步

### Phase 5：商业化 [2 人月]

- [ ] **#P5-001** 订阅模型 3 档（基础版 ¥299/月/20人 / 专业版 ¥999/月/50人 / 企业版 ¥9999/月/200人，学校 8 折）
- [ ] **#P5-002** 微信支付 V3 集成
- [ ] **#P5-003** 支付宝 APP 支付集成
- [ ] **#P5-004** 14 天免费试用流程
- [ ] **#P5-005** 续费 / 降级 / 退款流程
- [ ] **#P5-006** 发票系统（电子发票 + 增值税专票申请）
- [ ] **#P5-007** 学校 / 院系返点接口（10-20%）
- [ ] **#P5-008** 价格表页 + 商务对接入口
- [ ] **#P5-009** 销售漏斗 UTM 追踪 + 转化看板

### 关键决策（2026-06-28 拍板）

| # | 决策 | 拍板方案 |
|---|------|----------|
| 1 | 多租户数据库 | ✅ 阿里云 RDS PostgreSQL HA（省心优先） |
| 2 | 桌面框架 | ✅ Electron MVP + Tauri 并行试点（3 月后决策） |
| 3 | 移动框架 | ✅ Flutter 3.24+（性能 + 跨端） |
| 4 | 鸿蒙策略 | ✅ 预留 ¥30-50 万原生重写预算 |
| 5 | 商业化时间窗 | ✅ 边做边邀请（6 月起白名单） |
| 6 | 数据合规 | ✅ 承诺"数据不出境"，用户协议明示 |
| 7 | 付费模型 | ✅ 混合模式（基础版按组织，专业版按成员数），学校 8 折 |
| 8 | 招人 vs 外包 | ✅ 1 名 Flutter 全职 + 鸿蒙必要时外包 |

### 关键风险

| ID | 风险 | 等级 | 缓解 |
|----|------|------|------|
| RISK-01 | 鸿蒙 NEXT 2026-10 强制下架 Android APK，三方适配成本不可预估 | 高 | ¥30-50 万原生预算 + 1-2 人常驻 |
| RISK-02 | PG RLS 性能损耗 5-15% | 中 | 预读 + Redis 缓存 + 慢查询监控 |
| RISK-03 | 多租户改造后期成本是前期 10 倍 | 高 | **强制 PRE-001 占位列** |
| RISK-04 | 软著申请 30-60 天 | 高 | **今天就启动**（PRE-009） |
| RISK-05 | 微信网站应用与移动应用 appid 不互通 | 中 | 同时申请两个 appid |
| RISK-06 | macOS Notarization 公证被拒 | 中 | electron-builder 默认配置 + 测试机预审 |
| RISK-07 | 科研数据涉及人类遗传资源 / 数据出境 | 高 | 限定境内服务器 + 法务预审 |
| RISK-08 | App Store 4.7 / 4.2 拒绝，延期 2-4 周 | 中 | 提前对照审核指南 + 多次 TestFlight |
| RISK-09 | Electron 内存占用 200-400MB | 中 | Tauri 试点（5-10MB） |
| RISK-10 | 微信支付 V3 + 商户号审核 7-15 工作日 | 中 | 提前 30 天准备 |
| RISK-11 | 20 人历史数据迁移跨用户引用断裂 | 中 | 引用图分析 + 2 周 buffer |
| RISK-12 | Celery ORM 与 RLS 兼容 | 中 | `task_context` 装饰器统一 |

### 里程碑 KPI

- **6 月**：1-2 个外部课题组试用 + 软著到手 + 多组织 MVP
- **12 月**：5-10 个课题组付费 + 月活 100-300 + 桌面三平台 + iOS/Android 上线
- **18 月**：20+ 课题组 + 月活 500-1000 + 鸿蒙 + 微信小程序 + 盈亏平衡倒计时
- **24 月**：50+ 课题组 + 月活 2000+ + 双端占比 > 60% + ARR > ¥200 万

### 团队配置

- **短期 6 月**：前端 2 + 后端 2 + 移动 1 + 运维 0.5 + PM 0.5 = **6 人**
- **长期 12 月**：前端 3 + 后端 3 + 移动 2 + 运维 1 + 测试 1 + PM 1 + 运营 0.5 = **11.5 人**
- **招人顺序**：移动 Flutter（最稀缺 40-60K/月）→ 后端 RLS 专家 → 鸿蒙原生 → K8s 运维 → 科研背景 PM

### 立即启动项（本周内）

- ✅ **今天启动软著申请**（PRE-009，30-60 天不可压缩）
- ✅ **本周启动 PRE-001**（24 张表加 `organization_id` 占位列 + alembic 035 migration）
- ✅ **本月完成 PRE-002**（OAuth provider 抽象层）
- ✅ **本月启动 Phase 0**（RDS PostgreSQL HA 迁移）

---

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

## 项目动态更新 (W62-W65 截至 2026-07-23)

7 批 35+ agent commits 全部 merge 进 main. 5th-wave 主决策"测试内容以及其他的测试内容删去" (commit a70a1b07). 6th-wave 集成 5th-wave lessons (SafeIntakeContext + cache_drive_list + knowledge field constraints 7 铁律). 7th-wave 7 agent (PWA SW e2e + Nginx HSTS/TLS 1.3 + baseline stale fix + PWA InstallPrompt + Drive folder nesting e2e + rate limit 8 场景 + 6 批 v2.21 范式总结). 锚点范式 W7 12 -> W62 24 -> W65 26 单调上升, 26+ baseline 守恒 (71 PASS + 7 SKIP, 跨 60+ commit 0 regression). W19 选项 A 维持 (4 留未来 PR 不发起新排期). 全程沿用 0 production code 改动铁律 (除主指挥亲自 commit 的清理类).

- 📜 [**HISTORY.md**](HISTORY.md) — 完整开发历史（按时间倒序 commit 流水账，已存档 5730 行）
- 📝 [**CHANGELOG.md**](CHANGELOG.md) — 权威更新日志（按日期组织，简洁）
- 🛡️ [**CLAUDE.md**](CLAUDE.md) — 项目开发铁律沉淀
- 🐛 [**memory/**](memory/) — 事件复盘 + 教训笔记

## 项目动态更新 (W66 plans status 100% 状态化 截至 2026-07-23)

**W66 → W67 锚点范式第 28 次守恒** — 67 plans 全项目调研 100% 状态化: **47 completed + 16 agent-stub + 2 deleted** (`claude-pet` + `self-rag`) **+ 1 partial** (`15-17-18-cozy-bengio` Part 2 低占比发言人过滤 1.5s/3s/5% 在 commit `4b215220` refactor 中意外删除, 已由后续 memory 记录) **+ 1 not_started** (`2026-06-05-19-10-melodic-donut`)。锚点范式单调上升 W7 12 → W62 24 → W65 26 → **W66 27 → W67 28**，26+ baseline 守恒 (71 PASS + 7 SKIP, 跨 60+ commit 0 regression)。累计 5 批 35+ agent commits + 1 cleanup commit (main HEAD `34a3ce6a6` chore(cleanup): W66 stale worktree 清理 + memory anchor LF 标准化, 上一 commit `5ee6fccab`)。全程沿用 **0 production code 改动铁律** + W19 选项 A 维持 (4 留未来 PR 不发起新排期)。详见 `memory/plans-status-67-closure-w66-2026-07-23.md`。
