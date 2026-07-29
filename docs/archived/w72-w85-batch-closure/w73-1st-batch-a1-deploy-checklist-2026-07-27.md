# W73 第 1 批 A-1 部署收口 10 段 Checklist (2026-07-27)

> **批次**: W73 第 1 批 A-1 部署收口重派 (派工 v10 段 7 实战)
> **依据**: W72 第 2 批 A-1 commit `45de56f3b` grand closure 部署收口模板
> **当前 main HEAD (base)**: `45de56f3b` (W72 第 2 批 grand closure)

---

## 段 1: merge 顺序表 + commit hash

| 顺序 | Branch | Merge commit | 源 commit |
|---|---|---|---|
| 1 | feat/w73-1st-batch-c1-7-dim-commercial | 91d9d4a98 | 6e65b32d5 |
| 2 | chore/w73-1st-batch-b1-commercial-phase8-closure | b3f10ca53 | a68358411 |
| 3 | chore/w73-1st-batch-b2-hotfix-monitor | 86b1c3141 | 68e024677 |
| 4 | docs/w73-1st-batch-a2-voice-asr-tts-survey | da39772b5 | a2243a650 |
| 5 | docs/w73-1st-batch-d1-qa-bench-d9-integration | 32f8db3e9 | ad2640891 |
| 6 | chore/w73-1st-batch-e1-conservation | 3b4b8c388 | 6225c7c94 |

**合并顺序严格按派工 v6 段 6 表**: feature → docs → grand closure。
**冲突数**: 0 (全部 auto-merged, 0 manual conflict)。

---

## 段 2: alembic 链验证

**WARNING: alembic 双头 PENDING** — 见下方 issue。

合并后用 alembic ScriptDirectory 验证 heads:
```
$ python -c "from alembic.config import Config; from alembic.script import ScriptDirectory; c=Config(); c.set_main_option('script_location','alembic'); s=ScriptDirectory.from_config(c); print('heads:', s.get_heads())"
heads: ['080_drive_chunked_uploads', '083_commercial_tenant_isolation']
```

**双头原因** (派工 v6 段 5 反馈实战 #3 沉淀):
1. **W72 第 2 批 B-3 commit `277c6708b` (080)** 文件 docstring 注明 "Revises: 078_drive_dedupe_audit"，实际 `down_revision = "082_commercial_billing_tables"` (彼时 082 还未存在)。
2. **W72 第 2 批 B-5 commit `820e151d2` (082)** 在 080 之后单独 commit，down_revision='081_drive_share_enhancements'，从未合并 main。
3. **W73 第 1 批 B-1 commit `a68358411` (083)** 接 082 (与派工前提一致)，合并入 worktree 后立即触发双头。

**修复路径** (主指挥拍板):
- **方案 A (推荐)**: 改 080 的 down_revision='079_team_folders' (与 docstring 一致)，让 080 → 082 → 083 与 079 串成单链。需要单独 hot-fix commit，不在 A-1 合并提交中改。
- **方案 B**: 合并 B-5 (082 来源) 到 main，让 080 被 081/082/083 覆盖 → 但 080 的 down_revision 写 082 表示 080 想接 082 而非接 081，逻辑混乱。

按派工前提铁律 "如遇 alembic 双头 → 立即报主指挥, 不要自己改 down_revision"，本 A-1 收口 commit **不动 alembic**，留给主指挥派 hot-fix agent。

---

## 段 3: baseline Lint 验证

**未实跑** (本 worktree 不含完整 dev env, 待部署后服务器 lint)。CLAUDE.md 永久锚点 Lint baseline 71 PASS + 7 SKIP 应守恒。

---

## 段 4: web dist rebuild 验证

**未实跑** (本批 6 分支全 docs/memory/scripts/qa-bench/commercial 范畴, 无 web/src 改动, 0 触发 PWA manifest rebuild)。CLAUDE.md 永久锚点 `npm run build` 唯一合法, **`vite build` 直跑必坏 PWA**。

---

## 段 5: nginx 6 点 curl 验证

**未实跑** (本地 worktree, 无服务器访问)。部署后必跑:
```bash
curl -sk -o /dev/null -w "%{content_type}\n" https://xxx/index.html     # 期望 text/html
curl -sk -o /dev/null -w "%{content_type}\n" https://xxx/sw.js          # 期望 application/javascript
curl -sk -o /dev/null -w "%{content_type}\n" https://xxx/manifest.webmanifest  # 期望 410
curl -sk -o /dev/null -w "%{content_type}\n" https://xxx/registerSW.js  # 不存在 (production)
curl -sk -o /dev/null -w "%{content_type}\n" https://xxx/manifest.{hash}.webmanifest  # 期望 application/manifest+json
curl -sk -o /dev/null -w "%{content_type}\n" https://xxx/pwa-192.png    # 期望 image/png
```

任一返回 octet-stream 即配置错误，参考 CLAUDE.md 永久锚点 nginx types 教训。

---

## 段 6: 部署 webhook 30s 验证

**未实跑** (部署阶段由 D-1/Webhook 自动化触发)。

---

## 段 7: 浏览器 SW cache 验证

**未实跑** (部署后浏览器 DevTools 验证)。

---

## 段 8: PWA install 端到端

**未实跑** (部署后浏览器验证)。

---

## 段 9: 0 production code 改动铁律自查

**W73 第 1 批 6/7 守恒 (1 例外已批)**:
- B-1 商业化 Phase 8 收口 (alembic 083 多租户 + License + 计费 + SaaS + 中间件) — **例外已批**, 商业化路线延续 W72-B-5 是新一代新业务模块。
- C-1 (qa-bench 商业化评分, tests/qa-bench/scoring/* — 测试目录)
- B-2 (4 类 hot-fix 监控脚本, scripts/* — 自动化脚本)
- A-2 (声纹 + ASR + TTS 调研, docs/* + memory/*)
- D-1 (qa-bench D9 整合, docs/*)
- E-1 (守恒验证 5 件套, docs/* + memory/*)

**累计锚点范式守恒**: W72 第 2 批 235 → W73 第 1 批 A-1 243 (+8: C-1 +1 + B-1 +1 + B-2 +1 + A-2 +3 + D-1 +1 (估, 含 6 子批派工估一部分本批) + E-1 0 守恒)。注: D-1 +7 在派工前提估中含 1 本批收口 + 6 子批后续, 实际本批锚点增量 +7 来自 D-1 (qa-bench D9 W73 调研整合本身是 docs commit 而不含代码), 派工估需按实际情况校准。

---

## 段 10: 商业化 B-1 多租户隔离验证 (PENDING)

**未实跑**: E-1 commit `6225c7c94` 已提供 5 件套验证脚本 + 1 件多租户专项验证前置。本 A-1 收口不实施验证，留给 E-2 后续派工。

验证范围 (E-2 待派):
1. `tenant_middleware.py` 注入 X-Tenant-ID → 全局上下文 (PENDING 验证)
2. `tenant_data_isolation.py` SELECT 强制 WHERE tenant_id (PENDING 验证)
3. `license_middleware.py` 检查 PlanCode + 过期时间 (PENDING 验证)
4. `billing_gateway.py` mock 支付 callback 成功 (PENDING 验证)
5. SaaS deploy.sh 干跑 (PENDING 验证)

---

## 派工 v10 段 7 实战 2 实例沉淀

### 实例 #1: B-1 派工前提 vs 实战 git verify 错配 (派工 v10 段 7 #2 实战)
B-1 commit `a68358411` message 自述: "alembic 083 down_revision='082_commercial_billing_tables' 串单链守恒 (派工预设写 080, 真验证发现 main HEAD 082 是当前 head, 严格守 W72 E-1 派工 v6 §5 反馈 #3 实战)"。

**问题**: main HEAD `45de56f3b` 实际不含 082 (B-5 082 在未合并分支)。派工前提假设 "082 是当前 head" 与真实 git history 不符。

**沉淀**: B-1 agent 是基于"派工输入中的事实陈述"行动而非独立 `git log --all` 验证。这是 **派工 v10 段 7 类 #2 (派工前提错配)** 的典型案例。

### 实例 #2: D-1 派工 brief 假设错误 (派工 v10 段 7 类 #5 实战)
D-1 commit `ad2640891` 包含 5 子批 16-24 commit 估 + 起步纪律 6 项 + 类 20 实战。但派工估的 16-24 commit 中混含 "D-1 派工 brief 假设" (派工输入未明确每子批 commit 数), 估偏高。

**沉淀**: 派生新任务必先 git log + grep 真验证当前 main HEAD (派工 v10 段 7 类 #5)。

---

## PENDING 事项汇总

| ID | 描述 | 处理方 |
|---|---|---|
| PENDING-1 | alembic 双头 `['080', '083']` 修复 | 主指挥派 hot-fix agent |
| PENDING-2 | 部署 webhook 触发 | 部署阶段自动化 |
| PENDING-3 | nginx 6 点 curl 验证 | 部署后主指挥 |
| PENDING-4 | 浏览器 SW cache / PWA install 验证 | 部署后用户 |
| PENDING-5 | B-1 多租户 5 件套 e2e 验证 | 主指挥派 E-2 agent |
