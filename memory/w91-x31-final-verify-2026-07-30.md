# W91-X-31 集成 e2e 真跑 main 收官报告

> **结论先行**: **派工前提不成立**。派工 brief 假设 "W91-WR-1 + W91-X-15 ~ X-30 全部完成后" 已 merge 进 main,
> 实测 main tip `f57206c7c` 上 **43 个 brief 列出的套件目录只存在 10 个, 33 个不存在**;
> 5 个 W91 分支 (X-16 / X-18 / X-24 / X-28 / X-29) 仍 **未 merge**。
> 真跑结果 **不是 0 FAILED**: 新套件 6 FAIL + 老 pytest 177 FAIL / 424 ERROR + Playwright a11y 25 FAIL + root Playwright 194 FAIL。
> **本任务 0 修复 (只验证不修), 据实上报。** 沿用 W90-X-14 "派工前提不成立" 同源模式 (类 20.13 实战)。

---

## 1. main tip

- **验证基准 = `f57206c7c`** — `chore(w94-merge-04): 清理 MERGE-04 工作区遗留 (memory + 据实上报, ...)`
- 前序: `855130e1b` merge PR8 知识图谱深度联动 (alembic 090 → 091, 锚点 459 → 476)
- 本任务分支 `claude/w91-x31-final-verify`, base = `f57206c7c`, **0 文件改动** (仅本 memory)

> ⚠️ **main 在本任务执行期间前进 11 commits**: `f57206c7c` → **`f13636888`**。
> 本报告所有数据均为 **`f57206c7c` 实测**, 未包含其后 11 commits。
> 主指挥若需 `f13636888` 口径, 须重跑。(类 20.32 "base 必实测" 的时间维延伸:
> **长时验证任务的 base 会漂移, 报告必须锚定 hash 而非 "main"**。)

## 2. docker (类 20.52 必先 docker ps)

**14 services up** ✅ (`microbubble-agent-*`):

| service | 状态 |
|---|---|
| app | Up (healthy) |
| db | Up (healthy) |
| redis | Up (healthy) |
| minio | Up (healthy) |
| nginx | Up |
| celery-worker | Up |
| celery-beat | Up |
| neo4j | Up (healthy) |
| ollama | Up (healthy) |
| sensevoice | Up |
| vision-mcp | Up |
| pg-exporter | Up |
| glitchtip | Up |
| glitchtip-dev | Up |

- `curl http://localhost:8000/health` → **http=200** ✅
- TEST_TOKEN 真登录 `xiaoqi_testbot` → **141 字符** ✅ (非 mock)

## 3. ⚠️ 派工前提校核 — 不成立 (核心发现)

### 3.1 33/43 套件目录在 main tip 不存在

派工 brief 步骤 4 列出 43 个 `tests/<suite>/`。实测 main tip 只有 **19 个** `tests/*/` 目录:

```
alembic api dist_health e2e gitleaks integration k6 npm_audit perf
pg_exporter precommit qa-bench rag request_context scripts sentry
trivy unit visual
```

| brief 列出 | 实测 |
|---|---|
| **EXIST (10)** | gitleaks / trivy / precommit / pg_exporter / k6 / sentry / request_context / dist_health / npm_audit / alembic / integration (11 含 integration) |
| **MISSING (33)** | playwright_ci / build_a11y / axe_sop / ci_trigger / ci_trigger_x / ci_deploy_x26 / ci_x12 / ci_real_x29 / dark_harden / dark_x20 / networkidle_fix / swipe_fix / swipe_x7 / vitest_x19a / vitest_x19b / vitest_x19c / vitest_x4 / desktop_drive_x22 / visual_x24 / dev_port_x25 / e2e_rename_x28 / src_tests_x5 / baseline_sync_x29 / brief_v4_x27 / prod_fix / vite_x13 / moderate_x10 / icon_wr1 / a11y_login_x18 / axe_violation_x19 / delete_x21 / echarts_x30 |

### 3.2 W91 分支 merge 状态实测

`git rev-list --count main..<branch>`:

| 分支 | ahead | 状态 |
|---|---|---|
| wr1-play-icon / x15 / x17 / x19 / x20 / x21 / x22 / x23 / x25 / x30 | **0** | 分支 tip == main tip, **0 commit** (未产出 或 已并) |
| **x16-alembic-091** | **1** | ⚠️ 未 merge |
| **x18-a11y-login** | **2** | ⚠️ 未 merge |
| **x24-alembic-all** | **3** (7 commits 含历史) | ⚠️ 未 merge |
| **x28-src-spec** | **1** | ⚠️ 未 merge |
| **x29-ci-real** | **2** (4 commits 含历史) | ⚠️ 未 merge |

**关键**: X-16 / X-24 的 commit 正是 alembic `087 → 091` 修复;
X-18 正是 a11y baseline 真登录态重录。这两项修复**未进 main**,
直接导致下方 §4 对应 FAIL。

## 4. e2e 真跑结果 (main tip, 0 修改)

| 套件 | PASS | SKIP | FAIL | ERROR |
|---|---|---|---|---|
| W86-W91 新套件 (实存 11 个) | 189 | 15 | **6** | 0 |
| 老 pytest (排除新套件 + visual/e2e + 1 语法错文件) | 2156 | 231 | **177** | **424** |
| Playwright a11y (真 TEST_TOKEN) | 25 | 0 | **25** | — |
| Playwright root (visual + e2e) | 34 | 4 | **194** | — |
| **总计** | **2404** | **250** | **402** | **424** |

**期望 0 FAILED → 实测 402 FAILED + 424 ERROR。硬门禁未通过。**

### 4.1 新套件 6 FAIL 明细

| 测试 | 根因 |
|---|---|
| `precommit/test_hooks_executable.py::test_typing_imports_exit_zero` | `check_typing_imports.sh` **超时 180s** (类 20.33 "pytest timeout 必 ≥ 实测 × 2" 再现) |
| `dist_health/test_no_orphan_chunks.py::test_no_orphan_index_chunks` | orphan chunk `{'be8f90c0'}` — dist 内 index.html 未引用 (类 20.36 "cherry-pick 改 deps 必重跑 npm run build") |
| `alembic/test_pre_commit_hook_passes.py::test_actual_alembic_head_count_is_one` | 期望 `087_add_knowledge_original_parent_id`, 实际 **`091_add_kg_entity`** — **X-16/X-24 未 merge** |
| `integration::test_deep_mode_uses_deepseek_r1` | 期望 `deepseek-r1-distill-qwen:7b`, 实际 `deepseek-r1:7b` |
| `integration::test_chat_with_image_accepts_thinking_mode_form` | `Form(None)` 断言口径与 FastAPI 实际 repr 不符 |
| `integration::test_chat_with_file_accepts_thinking_mode_form` | 同上 |

### 4.2 老 pytest 177 FAIL + 424 ERROR

- **424 ERROR 全部集中在 `tests/test_w86_mini_4_entity_graph_perf_e2e.py` 等**, 根因 `ConnectionRefusedError [WinError 1225]` — 测试直连 DB/Redis 宿主端口, worktree 环境未暴露。**环境性, 非代码回归。**
- `tests/test_w79_commercial_private_deployment_e2e.py` **SyntaxError**: `closing parenthesis ']' does not match opening parenthesis '('` → 整文件 collection 中断, 已 `--ignore` 后单列。
- 177 FAIL 与 W91-X-25 "老 pytest 175 调研" 数量同量级 (175 → 177), **pre-existing 据实**, 不在本任务范围。

### 4.3 Playwright a11y 25 FAIL (真 TEST_TOKEN 下)

**注意**: `--reporter=list` 输出尾部先打 25 failed 再打 `25 passed`,
仅 `tail -20` 会**只看到 "25 passed" 而误判全绿** — 类 20.25
"a11y 全绿是可疑信号" 的**新变体: 截断读数造成的假全绿**。实际 `Running 50 tests`。

失败根因统一为 baseline 快照口径:
```
 page: 01-chat  route: /chat
 project: mobile-iphone14
-authed: no   redirected-to-login: yes
```
main tip 的 25 个 `.txt` baseline 记录的是**未登录态**;
本任务注入真 TEST_TOKEN 后为**已登录态** → snapshot 不匹配。
**这正是未 merge 的 W91-X-18 (a11y baseline 真登录态重录) 要修的内容。**

### 4.4 Playwright root 194 FAIL

- 主导错误 `GET http://localhost:3100/ | net::ERR_CONNECTION_REFUSED`
- `playwright.config.js:53` `baseURL = http://localhost:3000`, **无 `webServer` 块**;
  部分 spec 硬编码 3100。实测 3100 **无监听** (curl → 000 REFUSED)。
- 次要: `ws://127.0.0.1/api/v1/ws/notifications` handshake **404**。
- 结论: **缺 dev server 前置**, 环境性为主, 非单纯代码回归。

## 5. 边界复检

```
git diff main..HEAD --name-only
→ memory/w91-x31-final-verify-2026-07-30.md   (仅本文件)
```

- ✅ **0 业务代码改动**
- ✅ **0 spec 改动**
- ✅ **0 baseline 改动** (未 `--update-snapshots`, 不掩盖 25 FAIL)
- 例外: `web/node_modules/` 为跑 Playwright 执行 `npm ci` 安装 (gitignore, 不入 commit)

## 6. 派工 v6 §5 反馈

### 类 20.108 加固 (原文)
> "W91 grand closure 真环境验证必含 docker ps + 14 services + 全套 e2e + Playwright + 真功能 8 步曲"

**本任务实战补强 4 条**:

- **类 20.108.1 — 验证 agent 必先校核套件目录存在性, 再跑**
  brief 列 43 套件, 实存 10。若直接把 43 个路径喂 pytest,
  `ERROR: file or directory not found` 会**整批中断**, 得不到任何真数据。
  **必须先 `ls -d tests/*/` + 逐项 EXIST/MISSING 对表。**

- **类 20.108.2 — "全部完成" ≠ "已 merge", 必须 `git rev-list --count main..<branch>` 实测**
  10/15 W91 分支 ahead=0, 5 个 ahead≥1 未 merge。
  沿用类 20.32 "协调 base 必实测" → 扩展为 **"派工前提中的『已完成』必实测 merge 状态"**。

- **类 20.108.3 — Playwright/pytest 摘要禁止只读 `tail -N`**
  a11y 真实为 `25 failed + 25 passed`, `tail -20` 只截到 `25 passed` → **假全绿**。
  **必须 `grep -aE "passed|failed|skipped"` 抓完整摘要行, 并核对 `Running N tests` 总数。**
  (类 20.25 "全绿是可疑信号" 的读数层新变体)

- **类 20.108.4 — 真环境验证必先确认 dev server / 端口前置**
  root Playwright 194 FAIL 主因 3100 无监听、config 无 `webServer`。
  **e2e 派工 brief 必须写明 baseURL + 谁负责起 dev server**, 否则 FAIL 数无意义。

- **类 20.108.5 — 长时验证任务必锚定 base hash, 因 main 会漂移**
  本任务跑了约 40 分钟, 期间 main 由 `f57206c7c` 前进 **11 commits** 至 `f13636888`。
  报告若写 "main 收官 0 FAILED" 而不写 hash, 下一批复现时口径已不同。
  **所有 e2e 收官报告标题/结论必须带 base hash。**

- **类 20.108.6 — 验证 agent 必 `git status` 复检, 测试会写脏工作区**
  本任务跑完后 `tests/qa-bench/scoring/migration_v3_to_v4_log.json` 被测试**写脏**。
  "只验证不修" 的 agent 若直接 `git add -A` 会**误提交测试副作用**。
  **必须 `git diff HEAD --name-only` 复检并 `git checkout --` 还原非目标文件。**

### 与 W90-X-14 同源
W90-X-14 据实 "派工前提不成立, 27 FAIL";本任务 W91-X-31 **同源复现**
(前提不成立 + 402 FAIL)。连续两批同类 → 建议主指挥在**派工前**加一道
`ls -d tests/*/ && git rev-list --count main..<各分支>` 的前置校核,
而非由收官 agent 事后发现。

## 7. 主指挥待决

1. **X-16 / X-24 (alembic 091)** — 未 merge, merge 后可消 1 个新套件 FAIL
2. **X-18 (a11y baseline 真登录态)** — 未 merge, merge 后可消 25 个 a11y FAIL
3. **X-28 / X-29** — 未 merge
4. **33 个 MISSING 套件** — 是否真存在于其他未 merge 分支, 需主指挥核对派工台账
5. **`test_w79_commercial_private_deployment_e2e.py` SyntaxError** — 阻断 collection, 建议单派 hotfix
6. **root Playwright dev server 前置 (3100)** — 需明确归属
7. **老 pytest 177 FAIL / 424 ERROR** — pre-existing, 沿 W91-X-25 调研口径处置

## 8. 锚点

- base `f57206c7c` → tip **+1** (本 memory commit)
- 本任务 **0 production code 改动铁律守恒 1/1** ✅
