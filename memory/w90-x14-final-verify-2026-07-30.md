# W90-X-14 集成 e2e 真跑 main 收官报告

> **日期**: 2026-07-30
> **分支**: `claude/w90-x14-final-verify`
> **worktree**: `E:\agent-w90-x14-final-verify`
> **base ref**: main tip `034343f8a` (实测 `git log --oneline -1 main`, 类 20.32 遵守)
> **性质**: 只验证不修 (0 production code, 0 测试改动, 仅新增本 memory)

---

## ⚠️ 头条: 派工前提错配 (类 20.13 / 20.29 / 20.32 实战)

派工 brief 前提为 **"W89 + W90 第 1 批 14 commit merge 后, 在 main 上真跑全套 e2e"**, 并列出 27 个 W89/W90 新增套件路径。

**实测结论: 该前提不成立。main 上不存在任何一个 brief 所列的 W89/W90 X-series 新套件。**

### 证据 1 — 27 个 brief 套件路径全部 MISS

```
MISS tests/playwright_ci      MISS tests/build_a11y      MISS tests/axe_sop
MISS tests/ci_trigger         MISS tests/ci_trigger_x    MISS tests/ci_deploy_x26
MISS tests/ci_x12             MISS tests/dark_harden     MISS tests/dark_x20
MISS tests/networkidle_fix    MISS tests/swipe_fix       MISS tests/swipe_x7
MISS tests/vitest_x19a        MISS tests/vitest_x19b     MISS tests/vitest_x19c
MISS tests/vitest_x4          MISS tests/desktop_drive_x22  MISS tests/visual_x24
MISS tests/dev_port_x25       MISS tests/e2e_rename_x28  MISS tests/src_tests_x5
MISS tests/baseline_sync_x29  MISS tests/brief_v4_x27    MISS tests/prod_fix
MISS tests/vite_x13           MISS tests/moderate_x10    MISS tests/integration/test_build_a11y.py
```

main 上 `tests/` 实际仅 19 个子目录:
`alembic api dist_health e2e gitleaks integration k6 npm_audit perf pg_exporter precommit qa-bench rag request_context scripts sentry trivy unit visual`

### 证据 2 — main 的 "W89/W90" 是**另一条工作流** (RAG PR 系列), 非 X-series

`git log --oneline -60 main | grep -iE "w89|w90"` 命中的全部是 RAG PR merge:

| commit | 内容 |
|---|---|
| `034343f8a` | chore(w91-merge-03) 清理工作区遗留 |
| `5fdcb6819` | merge PR5 RAGEvaluator (锚点 444 → 458) |
| `a000d0bf2` | merge-02 W89 PR3 BM25 + pg_trgm + tsvector (锚点 430 → 444) |
| `e65f3357c` | merge-01 W89 PR2 knowledge_chunk (锚点 415 → 430) |
| `185226e0b` | merge-01 W89 PR4 HybridRetriever (W90, 锚点 359 → 373) |

即 main 上的 "W89 / W90" 语义 = **RAG 路线的 PR3 / PR4 批次编号**, 与 brief 所指的 "W89/W90 第 1 批 X-series agent" 完全是两套编号体系。

### 证据 3 — X-series 分支实测 ahead 数: 绝大多数**未 merge**

W90 X-series:

| 分支 | ahead of main | 说明 |
|---|---|---|
| `claude/w90-x7-swipe-bug` | 0 | tip == main, **无 commit** |
| `claude/w90-x8-prod-chunk` | 0 | tip == main, **无 commit** |
| `claude/w90-x10-moderate` | 0 | tip == main, **无 commit** |
| `claude/w90-x13-vite-verify` | 0 | tip == main, **无 commit** |
| `claude/w90-x9-axe-rest` | 1 | 未 merge |
| `claude/w90-x11-win32` | 1 | 未 merge |

> `merge-base --is-ancestor` 对 x10/x13 报 "MERGED" 是假阳性 — 它们 tip 就是 main 本身 (0 commit 空分支), 不是内容被合入。**类 20.29 同型陷阱: 不可凭祖先关系断言已合并, 必须查 ahead 数。**

W89 X-series 23 个分支 **全部 ahead ≥ 1 且未 merge** (x9-grand-closure ahead=0 为空分支):
x10=1, x11=2, x12=3, x13=1, x14=1, x15=3, x16=1, x17=17, x18=1, x19a=5, x19b=4, x19c=1,
x20=8, x21=1, x22=1, x23=1, x24=1, x25=1, x26=4, x27=1, x28=1, x29=2

**结论**: "W89 + W90 第 1 批 14 commit merge 后" 这一前提**从未发生**。X-series 成果仍分散在 29 个未合并分支上。

**处置** (遵守"只验证不修"+"诚实报告"): 不伪造 27 套件结果, 不擅自 merge 分支, 据实上报并跑通**真实存在**的部分。

---

## main tip

- 验证时 base: `034343f8a` — chore(w91-merge-03): 清理 MERGE-02 工作区遗留
- ⚠️ **base 漂移 (类 20.32 实战)**: 本任务执行期间 (~30min) main 被推进到 `855130e1b`
  (`[merge-04 W94 +0] merge: PR8 知识图谱深度联动, alembic 090 → 091, 锚点 459 → 476`)
- 本报告全部数据基于 `034343f8a` 实测。W94 PR8 引入 alembic **091**, 故 FAIL 1 的
  期望值脱节会进一步扩大 (087 期望 vs 实际已达 091), FAIL 2 orphan chunk 亦可能变化
- 边界复检以真实 base `034343f8a` 为准, 非漂移后的 main

---

## docker 真环境 (类 20.52 必先 docker ps)

`docker ps` 实测 **14 services up** (brief 期望 12, 实际多 2):

| service | status |
|---|---|
| app-1 | Up 14 hours (**healthy**) |
| db-1 | Up 23 hours (healthy) |
| redis-1 | Up 15 hours (healthy) |
| minio-1 | Up 15 hours (healthy) |
| neo4j-1 | Up 23 hours (healthy) |
| ollama-1 | Up 23 hours (healthy) |
| celery-worker-1 | Up 13 hours |
| celery-beat-1 | Up 13 hours |
| nginx-1 | Up 13 hours |
| sensevoice-1 | Up 23 hours |
| vision-mcp-1 | Up 23 hours |
| glitchtip-1 | Up 15 hours |
| pg-exporter-1 | Up 15 hours |
| **glitchtip-dev-1** | ⚠️ **Restarting (1)** — crash loop, 据实上报 |

- `curl /health` → **http=200** `{"status":"healthy"}` ✅
- 真 token 获取成功, 长度 **141** ✅ (`xiaoqi_testbot` 登录)
- 未执行 `docker compose up` — 主栈已在运行, 避免打断既有服务

---

## e2e 真跑结果

| 套件 | PASS | SKIP | FAIL |
|---|---|---|---|
| W89 + W90 新加套件 (27 个) | — | — | **N/A 不存在** |
| 老 10 套件 (pytest) | 163 | 10 | **2** |
| Playwright a11y (axe 扫描) | 25 | 0 | 0 |
| Playwright a11y (baseline 比对) | 0 | 0 | **25** |
| Playwright visual + e2e (默认 config) | 34 | 4 | 0 |
| **总计** | **222** | **14** | **27** |

> 期望 0 FAILED — **未达成**。27 FAILED 全部据实, 无一编造。

### 老 10 套件命令

```bash
SKIP_DB_SETUP=1 python -m pytest tests/gitleaks/ tests/trivy/ tests/precommit/ \
  tests/pg_exporter/ tests/k6/ tests/sentry/ tests/request_context/ \
  tests/dist_health/ tests/npm_audit/ tests/alembic/ -q
# → 2 failed, 163 passed, 10 skipped in 167.10s
```

---

## FAIL 明细 (3 类, 全部为 main 上真实回归)

### FAIL 1 — `tests/alembic/test_pre_commit_hook_passes.py::test_actual_alembic_head_count_is_one`

```
AssertionError: alembic head 应为 087_add_knowledge_original_parent_id.
                实际: 090_add_rag_eval_report
assert '090_add_rag_eval_report' == '087_add_know...nal_parent_id'
```

- **head 数量 = 1 ✅** (单链守恒未破, `count == 1` 断言先过)
- 失败点是**硬编码 head 名期望值过期**: RAG merge 链 088 (knowledge_chunk) → 089 (pg_trgm/tsvector) → 090 (rag_eval_report) 已推进 head
- 性质: **测试期望值脱节**, 非 alembic 链断裂。属类 20.46 "文档/测试与实测脱节" 同型
- 本任务不修 (严格边界), 留主指挥派工同步 087 → 090

### FAIL 2 — `tests/dist_health/test_no_orphan_chunks.py::test_no_orphan_index_chunks`

```
AssertionError: orphan index chunks (在 dist 但 index.html 未引用): {'be8f90c0'}
```

实测:
```
dist/assets/ 实际:  index-be8f90c0.js  index-d64e7046.js
index.html  引用:   index-d64e7046.js          ← be8f90c0 无人引用
```

- orphan `index-be8f90c0.js` 引入自 `ddb7ab93c [merge-01 W89] merge: PR6 SearchLog 前端接通`
- `web/dist/index.html` 最后一次 rebuild 是 `5290cab5b` (W86 mini-15), **早于** PR6 merge
- 根因: **RAG PR6 merge 改了前端 deps/源码但未重跑 `npm run build`** → 正是 **类 20.36 "cherry-pick 改 deps 必重跑 npm run build"** 的再次复发
- 本任务不修, 留主指挥派工 `cd web && npm run build` 收口

### FAIL 3 — Playwright a11y baseline 25/25 全红

```
- authed: no   redirected-to-login: yes
- violations: 0
+ authed: yes  redirected-to-login: no
+ violations: 2
+   aria-command-name [serious] ×1
+   color-contrast [serious] ×6
```

- 实测 25 份 baseline snapshot **全部**记录为 `authed: no / redirected-to-login: yes / violations: 0`
- 即基线是在**未登录 → 被重定向到登录页**状态下录制的, 扫的是登录页而非目标页
- 本次注入真 `TEST_TOKEN` (141 字符) 后进入真登录态, 真实页面 a11y 违规暴露:
  - `aria-command-name` [serious] ×1
  - `color-contrast` [serious] ×6~7
- 性质: **类 20.25 "a11y 测试必先 baseline, 全绿是可疑信号" 的教科书级实证** — 旧 baseline 的 `violations: 0` 正是"假全绿"
- 同 config 下 `axe-chats.spec.mjs` 的 25 个 axe 扫描 case **全部 PASS** (它不比对 baseline, 只做阈值扫描)
- 本任务不修 baseline (严格边界), 留主指挥派工真登录态重录

---

## pre-existing 老 pytest (不在本任务范围)

- 138+ 老 pytest FAIL (CLAUDE.md 历史记录, 与本次验证无关)
- 84 ERROR (同上)
- 本次**未**跑主仓库 2620 全量 collect, 仅跑 brief 指定的 10 老套件 + Playwright

---

## 边界复检

```bash
git diff main..HEAD --name-only
# → memory/w90-x14-final-verify-2026-07-30.md   (唯一新增)
```

- ✅ **0 production code 改动** (`app/` `web/src/` `alembic/versions/` 零 diff)
- ✅ **0 测试文件改动** (2 个 pytest FAIL + 25 个 a11y FAIL 全部保留原状, 未"修绿")
- ✅ **0 spec 文件改动**
- ⚠️ `web/node_modules/` 因 `npm ci` 生成 — 已被 `.gitignore` 拦截, 不进 diff

---

## 派工 v6 §5 反馈

### 类 20.96 加固 (brief 要求沉淀)

> **类 20.96**: "W90 grand closure 真环境验证必含 docker ps + 12 services + 全套 e2e + Playwright + 真功能 7 步曲"

本任务实战补强 4 点:

1. **docker ps 必看 STATUS 而非仅看存在** — 14 services 中 `glitchtip-dev-1` 处于 `Restarting (1)` crash loop, 只数容器个数会漏掉
2. **真 token 必验长度** — 141 字符即有效; 若登录失败返回空串, 后续 a11y 会静默退化为未登录态跑, 制造"假全绿"
3. **Playwright 必分两 config 跑** — `tests/visual/a11y/playwright.a11y.config.mjs` 与根 `playwright.config.js` 是独立套件, 只跑一个会漏掉一半
4. **fresh worktree 必先 `npm ci`** — 新建 worktree 无 `node_modules`, 否则 Playwright 直接无法启动

### 类 20.97 新增 (本任务实战)

> **类 20.97**: "收官验证 agent 必先实测 brief 所列套件路径是否存在, 全 MISS 时立即据实上报而非空跑"

- 本任务 27 个 brief 套件路径 100% MISS。若直接把整串路径喂给 pytest, 会因 `ERROR: file or directory not found` 一次性红掉, 极易被误读为"套件失败"而非"套件不存在"
- 正解: 先 `[ -e "$d" ]` 逐个探测 → 分类 OK/MISS → 再决定跑什么
- 与类 20.13 (派工前提错配) 同族, 但落点在**验证型 agent 的开工第一步**

### 类 20.98 新增 (本任务实战)

> **类 20.98**: "判定分支是否已合并必须查 ahead 数 (`git rev-list --count main..<branch>`), 不可仅凭 `merge-base --is-ancestor`"

- `claude/w90-x10-moderate` / `claude/w90-x13-vite-verify` 的 `--is-ancestor` 返回真 (报 MERGED), 但 `ahead=0` 且 tip 恰为 main — 它们是**从未提交过的空分支**, 内容根本不存在
- 把"空分支"误判为"已合并"会直接导致 grand closure 锚点虚高
- 与类 20.29 (不可凭 hook 报告断言 alembic head) 同源: **凡断言状态, 必取可证伪的实测量**

### 类 20.36 复发告警

- FAIL 2 (orphan chunk) 证明 **类 20.36 "改 deps 必重跑 npm run build"** 在 RAG PR6 merge 时再次被违反
- 建议: 把 `tests/dist_health/` 提为 merge 前硬门禁, 而非 merge 后才发现

---

## 待主指挥后续派工 (据实清单)

| # | 事项 | 依据 |
|---|---|---|
| 1 | **W89/W90 X-series 29 分支合并决策** — 全部未 merge, X-14 无法验证不存在的套件 | 证据 3 |
| 2 | `tests/alembic` 期望值 087 → 090 同步 | FAIL 1 |
| 3 | `cd web && npm run build` 重建 dist, 清 orphan `index-be8f90c0.js` | FAIL 2, 类 20.36 |
| 4 | a11y baseline 真登录态重录 25 份 | FAIL 3, 类 20.25 |
| 5 | 修复 a11y 真实违规: `aria-command-name` ×1 + `color-contrast` ×6 | FAIL 3 |
| 6 | `glitchtip-dev-1` crash loop 排查 | docker 段 |
| 7 | 锚点口径澄清: RAG 路线 "W89/W90" 与 X-series "W89/W90" 编号冲突 | 证据 2 |

---

## 锚点

- base `034343f8a` → tip **+1** (仅本 memory 文件)
- **不宣告 "W90 第 1 批 14 agents 全部完成 / 锚点 +5 守恒"** — 前提不成立, 拒绝伪造守恒数字 (类 20.13 纪律)
