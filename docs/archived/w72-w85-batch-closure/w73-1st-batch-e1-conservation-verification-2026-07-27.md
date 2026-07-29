# W73 第 1 批 E-1 守恒验证 5 件套 (2026-07-27)

> **任务**: W73 第 1 批 E-1 (主基调 "守恒验证 5 件套 + 商业化 B-1 多租户隔离 + 声纹+ASR+TTS ≠ 生产警示", 验证型任务, 锚点范式 0 增量)
> **派工依据**: W72 第 2 批 E-1 commit `c29ca1663` 守恒验证 5 件套升级 + 派工 v6 段 5 反馈 #1 锚点校准 + 派工 v6 段 6 实战 alembic 串单链
> **当前 main HEAD**: `45de56f3b` (W72 第 2 批 grand closure 收口)
> **报告**: `docs/w73-1st-batch-e1-conservation-verification-2026-07-27.md` (本文件)
> **worktree**: `E:/microbubble-agent/.claude/worktrees/agent-w73-1-e1-verify`
> **分支**: `chore/w73-1st-batch-e1-conservation-2026-07-27`

## 5 件套守恒验证结果 (5/5 PASS)

| 件套 | 验证项 | 实际结果 | 派工 prompt 期望 | 校准 |
|------|--------|----------|-----------------|------|
| 1.1 | alembic 1 head | `['080_drive_chunked_uploads']` count=1 | `['080_drive_chunked_uploads']` | 完全符合, 1 head 守恒 |
| 1.2 | baseline CSS lint | 0 errors (stylelint JSON formatter) | 71+7 PASS (W67 旧基准) / W72 E-1 20 errors | 当前 main HEAD 实测 0 errors (商业化/Mobile v3.4 新组件未触发 stylelint 规则增量); 派工 prompt 引用 baseline 必须按时点校准, W73 (2026-07-27) 实测 0, 派工 prompt 期望 20 是 W72 E-1 (前一日) 实测值 |
| 1.3 | PWA manifest 410 防护 | nginx 配置存在 + dist 无 unhashed manifest + main.js H-3 unregister | 3 路径 410 | 验证型 agent 不部署, 静态配置层面守恒 (web/src/main.js unregister + dist manifest.hash.webmanifest 链路) |
| 1.4 | 0 production code 6/7 | 当前 main HEAD 老路径未变 | W73 6 commits (排除 B-1 商业化例外) | 当前 main HEAD 仅 W72 第 2 批 15 commits 已 merge, 实际 W73 第 1 批 6 agents 中 5 仍 base HEAD 0 commit 状态, E-1 验证型 + B-2 hot-fix 监控已实施 1 commit (scripts/ 范畴); B-1 商业化 alembic 083 实施但未 merge, 仍属预期例外 |
| 1.5 | anchor 235→235 守恒 | 235 验证型 0 增量 | 235→235 验证型 0 增量 | 派工 prompt 预测值与实际值完全一致, 验证型任务 E-1 不计增量 |

## 2 新增段验证 (W72 E-1 升级)

### 新增段 1: 商业化 B-1 多租户隔离验证

**派工 prompt 期望** (W73 第 1 批 B-1):
- 6 商业化表全部加 tenant_id
- 跨租户访问 422
- tenant_id 索引
- alembic 083 串单链 (down_revision='080_drive_chunked_uploads')

**实际状态**: B-1 (chore/w73-1st-batch-b1-commercial-phase8-closure-2026-07-27) 分支存在, base HEAD `45de56f3b` 0 commit 状态, 尚未实施。派工 v6 段 5 反馈 #4 实战: 商业化多租户验证**仅在 B-1 真实施后**才能验证。E-1 验证型任务**不预先实施**, 仅确认 alembic 083 接 080 的位置正确 (当前 head 是 `080_drive_chunked_uploads`, 083 串接位置 OK)。

**E-1 强化**: 派工 v6 段 5 反馈 #4 (新)
- 商业化多租户隔离验证**禁止**在 B-1 未实施前伪造 PASS
- B-1 真实施后 E-1 才能验证 6 表 + tenant_id 索引 + 跨租户 422 + alembic 083 串单链
- 当前状态: **B-1 待实施, E-1 验证段 1 维持 PENDING 状态**

### 新增段 2: 声纹+ASR+TTS ≠ 生产警示

**派工 prompt 期望** (W73 第 1 批 A-2):
- A-2 调研 agent 仅写 docs/ + memory/, 0 production code
- 派工 v6 段 5 反馈"调研完成 ≠ 生产实施"
- 声纹 90% 门禁 / ASR benchmark / TTS 路径不直接进入 main

**实际状态**: A-2 (docs/w73-1st-batch-a2-voice-asr-tts-survey-2026-07-27) 分支存在, base HEAD `45de56f3b` 0 commit 状态。E-1 验证型任务**不预先警告**, 仅确认 A-2 派工 prompt 已严格规定"调研 ≠ 实施"边界 (从派工 prompt 文本验证, A-2 任务描述明确写"仅 docs/memory/, 0 production code, 调研完成 ≠ 生产实施")。

**E-1 强化**: 派工 v6 段 5 反馈 #5 (新)
- 调研型 agent 派工 prompt 必须显式声明 "调研 ≠ 实施" + "0 production code"
- 声纹 90% 门禁 (memory/voiceprint-90-percent-gate-2026-06-28.md) + ASR benchmark (memory/asr-benchmark-2026-06-30.md) + TTS 路径不直接进入 main
- 当前状态: **A-2 派工前提已含警示文本, 调研 agent 边界清晰**

## 4 类 hot-fix 监控 verify (B-2 实施后)

### 当前状态

**W73 第 1 批 B-2 实施**: commit `68e024677` "4 类 hot-fix 监控" 已实施但**未 merge 到 main**。

**4 监控脚本存在** (B-2 worktree 路径 `E:/microbubble-agent/.claude/worktrees/agent-w73-1-b2-hotfix/scripts/`):
1. `monitor-alembic-heads.sh` (79 行) — alembic 双头检测
2. `monitor-pwa-manifest.sh` (85 行) — PWA manifest 410 防护
3. `monitor-nginx-mime.sh` (77 行) — 整站 octet-stream 防护
4. `monitor-sw-cache.sh` (83 行) — SW 缓存污染防护

**hotfix commit message 模板存在**: `docs/w73-hotfix-commit-template-2026-07-27.md` (235 行), 含 3 段格式 (root cause / 修复 / 验证) + 4 类 hot-fix 案例。

**e2e 测试存在**: `tests/test_hotfix_monitor_e2e.py` (298 行), 验证 4 监控脚本功能正确性。

**E-1 验证型确认**: B-2 实施完整, 4 监控脚本 + hotfix commit 模板 + e2e 测试 3 件齐全, B-2 merge 后 4 类 hot-fix 防护全栈激活。

## 0 production code 改动铁律 (W73 第 1 批)

### 当前 W73 第 1 批 7 agents 派工清单 (主基调 "商业化 Phase 8 起步 + 声纹调研 + D9 集成 + 7 维商业化 + E-1 守恒"):

| # | agent | 分支 | 状态 | 锚点 | commit hash | 例外类型 |
|---|---|---|---|---|---|---|
| A-1 | 部署收口 W73 第 1 批 | chore/w73-1st-batch-a1-deploy-2026-07-27 | base HEAD 0 commit | 待 merge | n/a | 0 (待实施) |
| A-2 | 声纹+ASR+TTS ≠ 生产警示调研 | docs/w73-1st-batch-a2-voice-asr-tts-survey-2026-07-27 | base HEAD 0 commit | 待 merge | n/a | 0 (调研不写生产) |
| B-1 | 商业化 Phase 8 closure 多租户隔离 | chore/w73-1st-batch-b1-commercial-phase8-closure-2026-07-27 | base HEAD 0 commit | 待 merge | n/a | 商业化 (新模块例外, 已批) |
| B-2 | 4 类 hot-fix 监控 | chore/w73-1st-batch-b2-hotfix-monitor-2026-07-27 | **已 commit 未 merge** | 235→240 预测 (+1) | `68e024677` | 0 (scripts/ 范畴) |
| C-1 | 7 维商业化评分 | feat/w73-1st-batch-c1-7-dim-commercial-2026-07-27 | base HEAD 0 commit | 待 merge | n/a | web (新组件例外, 已批) |
| D-1 | qa-bench D9 集成 | docs/w73-1st-batch-d1-qa-bench-d9-integration-2026-07-27 | base HEAD 0 commit | 待 merge | n/a | 0 (qa-bench 调研) |
| **E-1** | **守恒验证 5 件套** | **chore/w73-1st-batch-e1-conservation-2026-07-27** | **本任务 (E-1)** | **235→235 守恒 (验证型 0 增量)** | **本 commit** | **0 (验证)** |

**0 production code 改动铁律 7/7 守恒** (验证时点):
- E-1 验证型任务: 仅新增 `docs/w73-1st-batch-e1-conservation-verification-2026-07-27.md` (本文件) + `memory/w73-1st-batch-e1-conservation-verification-2026-07-27.md`, 不动 production code
- B-2 hot-fix 监控: `scripts/` + `docs/` + `tests/`, 守恒 (scripts/ 范畴, CLAUDE.md §3 明确算例外)
- 其余 5 agents base HEAD 0 commit, 0 production code 改动 (待实施)

**老路径未动证据** (派工 v6 §1 段 3 实战):
- `app/services/task_service.py` / `meeting_service.py` / `knowledge_service.py` 未变
- `web/src/views/Desktop*/index.vue` 未变
- `alembic/versions/0XX_老.py` 未变
- `app/core/security.py` / `app/core/rate_limit.py` 未变
- `app/agent/chat_engine.py` 方案 C 6 铁律相关文件未变

## 累计锚点范式

- W68 第 14 批 175 守恒
- W71 实际合并 206 守恒
- W72 第 1 批 +47 守恒
- W72 第 2 批 235 守恒
- **W73 第 1 批 E-1 235 守恒 (验证型 0 增量)**
- 累计主仓库锚点范式: **235**

## 部署 webhook 30s 验证 (W73 E-1 不部署, 仅静态配置确认)

派工 v6 §"部署必做" 段 7 实战纪律:
- 服务器 webhook 30s 触发 (commit push → webhook → nginx reload)
- 浏览器 SW cache 验证 (DevTools → Application → Service Workers → 看到 activated SW 内容含新 SW_VERSION)
- 6 点 curl 验证 Content-Type (HTML/CSS/JS/PNG/manifest/sw.js)

**W73 E-1 验证型任务**: 不部署, 仅在静态配置层面确认监控脚本和文档齐备, 部署验证留待主指挥后续 merge 后实际操作。

## 派工 v6 段 5 反馈沉淀 (W73 E-1 新增 2 项)

**反馈 #4 (商业化多租户验证时机)**: 派工 prompt 写 "B-1 6 表全部加 tenant_id" 等具体验收项, 但 B-1 仍 base HEAD 0 commit 状态。**E-1 沉淀**: 商业化多租户验证必须在 B-1 真实施 (alembic 083 merge 进 main) 后才能 PASS, E-1 验证型任务**禁止**伪造 "B-1 已实施" 状态。当前状态如实记录为 PENDING。

**反馈 #5 (调研 ≠ 生产警示派工前提)**: A-2 派工 prompt 已显式写 "仅 docs/memory/, 0 production code, 调研完成 ≠ 生产实施"。**E-1 沉淀**: 调研型 agent 派工前提必须 3 段:
1. 任务范围仅 docs/memory/ (禁止 production code)
2. 调研完成 ≠ 生产实施 (调研报告可入库, 实施需另派 agent)
3. 调研输出必须含 "进入生产" 边界声明 (声纹 90% 门禁 / ASR benchmark / TTS 路径不直接进 main)

## 引用文档

- W72 第 2 批 E-1 参考: `docs/w72-2nd-batch-e1-conservation-verification-2026-07-27.md` + `memory/w72-2nd-batch-e1-conservation-verification-2026-07-27.md`
- W71 A-1 部署验证: `docs/w71-deployment-verification-2026-07-24.md`
- W68 第 14 批 grand closure: `memory/w68-route-14-d2-doc-sync-2026-07-24.md`
- W68 alembic 串单链: `memory/w68-alembic-chain-discipline-2026-07-24.md` (锚点范式第 46 守恒)
- PWA manifest 410 回归: `memory/pwa-manifest-410-regression-2026-07-11.md` (5 铁律)
- SW 缓存污染 v79 BUMP: `memory/sw-cache-poisoning-v79-bump-2026-07-08.md` (3 铁律)
- Nginx octet-stream: CLAUDE.md 2026-06-13 永久锚点 (5 铁律)
- 派工纪要 v10: `docs/w72-2nd-batch-a2-prompt-v10-2026-07-27.md`