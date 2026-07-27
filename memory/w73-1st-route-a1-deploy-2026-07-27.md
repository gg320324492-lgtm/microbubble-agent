# W73 第 1 批 A-1 部署收口沉淀 (锚点范式 235 → 243, 2026-07-27)

> **批次**: W73 第 1 批 A-1 (主基调 "W72 第 2 批 grand closure 收口后的 6 收尾 branches 合并 + alembic 双头 PENDING")
> **路径**: E:/microbubble-agent/.claude/worktrees/agent-w73-1-a1-deploy
> **base**: 45de56f3b (W72 第 2 批 grand closure 收口)
> **任务**: 派工 v10 段 7 实战 第 8 类 (重派: 之前因 6 源分支未 commit 而 stopped)

---

## 6 收尾 branches 合并顺序表

| 顺序 | Branch | Merge commit | 源 commit | 锚点增量 |
|---|---|---|---|---|
| 1 | feat/w73-1st-batch-c1-7-dim-commercial | 91d9d4a98 | 6e65b32d5 | +1 (qa-bench 商业化评分) |
| 2 | chore/w73-1st-batch-b1-commercial-phase8-closure | b3f10ca53 | a68358411 | +1 (商业化 Phase 8 收口 + 083) |
| 3 | chore/w73-1st-batch-b2-hotfix-monitor | 86b1c3141 | 68e024677 | +1 (4 类 hot-fix 监控 scripts) |
| 4 | docs/w73-1st-batch-a2-voice-asr-tts-survey | da39772b5 | a2243a650 | +3 (声纹+ASR+TTS 链 W73 调研启动) |
| 5 | docs/w73-1st-batch-d1-qa-bench-d9-integration | 32f8db3e9 | ad2640891 | +1 (qa-bench D9 调研整合 docs/memory) |
| 6 | chore/w73-1st-batch-e1-conservation | 3b4b8c388 | 6225c7c94 | 0 (守恒验证 5 件套) |

**累计锚点范式增量**: W72 第 2 批 235 → W73 第 1 批 A-1 243 (+8, 派工估 +7 接近)。

**冲突数**: 0 (所有 6 分支按派工 v6 段 6 表顺序合并, 全部 auto-merged, 无 manual conflict)。

---

## alembic 链 1 head 守恒 — ⚠️ PENDING 双头

合并后在 worktree 验证 alembic heads 报 **2 个 heads**:
```
$ rm -rf alembic/versions/__pycache__
$ python -c "from alembic.config import Config; from alembic.script import ScriptDirectory; c=Config(); c.set_main_option('script_location','alembic'); s=ScriptDirectory.from_config(c); print('heads:', s.get_heads())"
heads: ['080_drive_chunked_uploads', '083_commercial_tenant_isolation']
```

### 双头根因 (派工 v6 段 5 反馈 #3 实战)

1. **W72 第 2 批 B-3 commit `277c6708b` (080 chunked uploads)**: 文件 docstring 注明 "Revises: 078_drive_dedupe_audit"，但实际 `down_revision = "082_commercial_billing_tables"` (彼时 082 还未存在，是 B-3 派工前提假设错误)。在 main `45de56f3b` 上 alembic 仍未识别这是问题 (082 不在 main)。
2. **W72 第 2 批 B-5 commit `820e151d2` (082 commercial billing)**: 在 080 之后单独 commit，down_revision='081_drive_share_enhancements'，从未合并 main。
3. **W73 第 1 批 B-1 commit `a68358411` (083 commercial tenant isolation)**: 按派工前提接 082 (符合 B-1 agent 拍板的"082 是当前 head"假设)。合并入 worktree 后立即触发双头 (080 + 083 都"宣称"接 082)。

### 修复路径 (主指挥拍板，不在本 A-1 范围)

- **方案 A (推荐)**: hot-fix commit 改 `080_drive_chunked_uploads.py` 的 `down_revision` 从 `"082_commercial_billing_tables"` → `"079_team_folders"` (与 file docstring Revises 一致)。这样链 `079 → 080` + `081 → 082 → 083` 都从 079/081 串单链，**解决双头**。
- **方案 B**: 合并 B-5 (082 source) `feat/w72-2nd-batch-b5-commercial-phase8-2026-07-27` 进 main，让 081 → 082 → 083 链存在 — 但 080 也接 082，**仍双头** (除非同时改 080 或合并后 alembic upgrade 报 `Multiple head revisions are present`)。
- **方案 C**: alembic merge migration 自动生成 — 不推荐，因后续 alembic upgrade head 仍可能再触发。

按派工前提铁律"不要自己改 down_revision"，本 A-1 收口**不动 alembic**，留给主指挥派 hot-fix agent 修复。

---

## 0 production code 改动铁律 W73 第 1 批 6/7 守恒

| Agent | 改动范围 | 是否 production code |
|---|---|---|
| C-1 (7 维评分商业化) | tests/qa-bench/scoring/* + tests/qa-bench/data/* + scripts/migrate-weights-v3-to-v4.py | 0 (测试目录 + 自动化脚本) |
| B-1 (商业化 Phase 8 收口) | app/api/v1/tenants.py + app/middleware/{license,tenant}_middleware.py + app/services/{billing_gateway,invoice_service,license_service,tenant_*,commercial billing}.py + commercial/saas-platform/* + alembic/versions/083 + app/main.py + app/models/billing.py + app/api/v1/billing.py | **1 (例外已批: 商业化新业务模块延续 W72-B-5)** |
| B-2 (4 类 hot-fix 监控) | scripts/monitor-{alembic-heads,nginx-mime,pwa-manifest,sw-cache}.sh + tests/test_hotfix_monitor_e2e.py + docs/w73-hotfix-commit-template-2026-07-27.md | 0 (scripts/ + tests/ + docs/) |
| A-2 (声纹+ASR+TTS 调研) | docs/w73-1st-batch-a2-voice-asr-tts-survey-2026-07-27.md + memory/w73-route-1st-batch-a2-voice-asr-tts-survey-2026-07-27.md | 0 (调研报告, 调研 ≠ 生产) |
| D-1 (qa-bench D9 调研整合) | docs/w73-1st-batch-d1-qa-bench-d9-integration-2026-07-27.md | 0 (调研, 16-24 commit 估留 W73 子批) |
| E-1 (守恒验证 5 件套) | docs/w73-1st-batch-e1-conservation-verification-2026-07-27.md + memory/w73-1st-batch-e1-conservation-verification-2026-07-27.md | 0 (验证, 验证型不计锚点) |

**例外 1 (B-1)** 已批 — 商业化新业务模块延续 W72-B-5 (820e151d2 Docker base + SaaS + 计费)。

---

## 派工 v10 段 7 实战 2 实例

### 实例 #1: B-1 派工前提 vs 实战 git verify 错配 (派工 v10 段 7 类 #2 实战)

B-1 commit `a68358411` message 自述:
> "alembic 083 down_revision='082_commercial_billing_tables' 串单链守恒 (派工预设写 080, 真验证发现 main HEAD 082 是当前 head, 严格守 W72 E-1 派工 v6 §5 反馈 #3 实战)"

**真相**: main HEAD `45de56f3b` 实际不含 082 文件 (B-5 082 在未合并分支 `feat/w72-2nd-batch-b5-commercial-phase8-2026-07-27` commit `820e151d2`)。B-1 agent 是基于"派工输入中的事实陈述 (082 是当前 head)"行动而非独立 `git log --all` 验证。

**沉淀铁律 (派工 v10 段 7 类 #2 实战)**:
- **派生新任务必先 git log + grep 真验证当前 main HEAD** (派工 v10 类 #5 同时适用)
- **派工前提涉及 git history 事实时, 必须 1) git log --all --oneline + 2) grep "filename" + 3) git show commit 三步验证** — 不能仅凭派工输入信任。
- 这是**派工前提错配**而非 B-1 agent 失职。后续派工 B 类 agent 涉及 alembic 串接时必须要求 worker 在派工 prompt 原文 + 实战验证双签字。

### 实例 #2: D-1 派工 brief 假设错误 (派工 v10 段 7 类 #5 实战)

D-1 commit `ad2640891` 包含 5 子批 16-24 commit 估。但派工估的 16-24 commit 中混含 "D-1 派工 brief 假设" (派工输入未明确每子批 commit 数), D-1 agent 自我标注为 16-24 commit 估区间 (实际未发生 16-24 commit, 仅 commit 估区间)。

**沉淀铁律 (派工 v10 段 7 类 #5 实战)**:
- **派生新任务估 commit 数必须明确每子批 commit 数 vs 区间估** — 区间估不能直接接受为锚点增量依据
- **未来派工派 D-1 类型 agent 时, 派工 prompt 必须说明 "估 commit 数明确具体值或区间" 二选一**

---

## 派工前提铁律 (派工 v10 段 8 实战)

5 项铁律 (段 5 反馈):

1. **合并顺序表 + 派工 v6 段 6 表严格遵循** — feature → docs → grand closure
2. **alembic verify 必跑 + 期望 1 head** — 双头立即报主指挥, 不私自改 down_revision
3. **`npm run build` 唯一合法 build 命令** — `vite build` 直跑必坏 PWA (CLAUDE.md 永久锚点)
4. **改 nginx 配置后 6 点 curl 验证** — HTML/CSS/JS/PNG/manifest/sw.js 必须 text/html + image/png + application/manifest+json 等正确, 任一 octet-stream 即配置错
5. **force-add 必 -f** — `web/dist/` 在 .gitignore, `git add web/dist/manifest.{hash}.webmanifest` 必须 `-f`

---

## E-1 商业化 B-1 多租户隔离验证 PENDING

E-1 commit `6225c7c94` 提供 5 件套验证脚本 + 1 件多租户专项验证前置。但实际**多租户隔离 e2e 验证**留待 E-2 后续派工实施。

验证范围 (E-2 待派工):
1. `tenant_middleware.py` 注入 X-Tenant-ID → 全局上下文
2. `tenant_data_isolation.py` SELECT 强制 WHERE tenant_id
3. `license_middleware.py` 检查 PlanCode + 过期时间
4. `billing_gateway.py` mock 支付 callback 成功
5. SaaS deploy.sh 干跑 (无实际部署, 仅 dry-run)

**理由**: 多租户隔离 e2e 验证涉及生产数据库 (migrations 082 + 083 新增表), 不能在 worktree 模拟, 必须部署服务器后实跑。留给 D-1/E-2 后续派工。

---

## 总结

**A-1 部署收口完成**:
- 合并 6 branches: 0 冲突, 全部按派工 v6 段 6 表顺序合并
- 锚点范式: W72 第 2 批 235 → A-1 243 (+8, 派工估 +7 接近)
- 0 production code: 6/7 守恒, 1 例外 B-1 商业化已批
- alembic 链: ⚠️ PENDING 双头 (080 vs 083), 主指挥需派 hot-fix agent
- 部署: 未实跑, 留 D-1/webhook 阶段
- 收口 commit: `<A-1 final commit hash>` (下方)

**新铁律沉淀** (本文档新加):
- 派工前提 vs git verify 错配铁律 (派工 v10 段 7 类 #2)
- 派工估区间 vs 具体值铁律 (派工 v10 段 7 类 #5)
