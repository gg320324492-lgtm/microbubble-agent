# GitHub Actions Workflow 审计 (2026-10-10)

> **只读审计** —— 本次未修改任何 workflow / 代码 / 容器状态。运行记录经 `gh run list` /
> `gh api` 实测取得（非推测）；静态路径经文件系统逐个 `test -e` 核验。

## 审计方法与取证来源

| 项 | 手段 | 结果 |
|---|---|---|
| 运行历史 | `gh run list --workflow=<file> --limit 12` | ✅ 可用（account `gg320324492-lgtm`，scope `repo`） |
| 失败详情 | `gh run view <id> --log-failed` | ✅ 可用（仅 `upload-download-page` 日志已过保留期） |
| 引用路径 | 对每个 `paths:` / `run:` / `uses:` 引用逐个 `test -e` | ✅ 全部核验 |
| 分支保护 | `gh api repos/:owner/:repo/branches/main/protection` | ✅ **404 Branch not protected** |
| Rulesets | `gh api repos/:owner/:repo/rulesets` | ✅ **`[]` 空** |

---

## 🔴 头号发现：11 个 workflow **无一阻塞合并**

```
$ gh api repos/:owner/:repo/branches/main/protection
{"message":"Branch not protected", "status":"404"}

$ gh api repos/:owner/:repo/rulesets
[]
```

`main` **没有分支保护，没有任何 required status check，也没有任何 ruleset**。

**这直接证伪了 `server-tests-baseline.yml:15-18` 的注释**：

> 「**2026-09-30 收敛完成 → 已转硬门** …… 现摘除 `continue-on-error` —— 任一片出现
> failed/error 即红, **阻塞合并**」

`continue-on-error` 确实摘了，workflow 确实会红，但**红的是一个 GitHub 页面上的红叉，
不是合并门禁**。主分支无保护 + 零 required check ⇒ 任何人在本地 `git push main` 都能
直接落地，11 个 workflow 全部是**建议性（advisory）**的。

> 这正是本项目**类 20.220**（「自动化守门必须验副作用是否真的发生，不能信状态字段」）
> 的同型事故：workflow 文件声称自己是硬门，实际上没有任何机制让它具备硬门的能力。

---

## 逐 workflow 审计

### 1. `secret-scan.yml` — Secret Scan (gitleaks)

- **触发条件**：`pull_request`(main, dev) + `push`(main, dev) + `schedule` 每周一 06:00 UTC
- **实际作用**：`gitleaks-action@v2` 扫凭据，SARIF 上传 Code Scanning
- **阻塞合并**：❌ 否（无分支保护）
- **引用路径**：✅ `.gitleaks.toml` 存在
- **最近运行**：全绿，约 30s/次，最近一次 2026-10-10 11:34
- **判定**：✅ **保留**
- **理由**：唯一覆盖凭据泄漏的 workflow，常绿、极快、零误报噪声。唯一瑕疵见下。

> ⚠️ **轻微悬挂引用**：`on:` 里列了 `dev` 分支，但 `gh api repos/:owner/:repo/branches`
> 实测**仓库只有 `main` 一个分支**。`dev` 触发臂是死配置（不报错，只是永不触发）。
> 无害，但属"看起来配置了实际不存在"的一类。

---

### 2. `desktop-release.yml` — 桌面端发布

- **触发条件**：`push` tag `v*` + `workflow_dispatch`（可指定 tag）
- **实际作用**：pnpm workspace 安装 → `apps/desktop/scripts/release.mjs` 跑
  `version clean native gates package smoke latest verify` → 建 GitHub Release →
  OSS 镜像（`releases/`）→ 上传 artifact
- **阻塞合并**：❌ 否（tag 发布本来也不涉及合并）
- **引用路径**：✅ 全存在（`apps/desktop/scripts/release.mjs`、`package.json`、
  `upload-release-oss.mjs`、`pnpm-workspace.yaml`）
- **最近运行**：2026-09-29 `v1.3.2` / `v1.3.2-ci.2` 均 success（3m09s / 3m31s）
- **判定**：✅ **保留**
- **理由**：唯一真实发布流水线，最近成功用过（v1.3.1/v1.3.2 连续 6 次跑）。
  注：v1.3.0 因 OSS 跨境 87MB PUT 超时（undici 5 分钟硬超时）改用 curl 修复过，
  属真实生产链路。

---

### 3. `upload-download-page.yml` — 落地页单发

- **触发条件**：`workflow_dispatch` **仅手动**（无 push / schedule / PR）
- **实际作用**：`apps/desktop` 下 `node scripts/upload-release-oss.mjs --page scripts/download-page.html` 传落地页到 OSS
- **阻塞合并**：❌ 否
- **引用路径**：✅ 全部存在
- **最近运行**：🔴 **全生命周期仅 1 次运行，2026-09-28 17:37，`failure`，耗时 5 秒**
- **判定**：⚠️ **可疑 —— 事实上的死 workflow**
- **理由**：
  - 唯一一次运行就失败，且 5 秒即挂（典型的凭据缺失/前置条件不满足的秒失败）
  - 失败日志**已过 90 天保留期**，`gh run view --log-failed` 返回 `log not found`，
    **本次无法确认根因**
  - 之后 12 天从未再被手动触发过 ⇒ 无人使用、无人修复
  - ⚠️ 但它与 `desktop-release.yml:114-126` 的 OSS 镜像步共用同一脚本同源凭据，
    而后者最近**成功**跑过 ⇒ 该能力并未失效，失效的只是这个"独立手动入口"

> **不确定**：5 秒失败究竟是 secrets 未配、还是脚本参数问题，本次无法取证。
> 若 OSS 落地页已在 `desktop-release` 里覆盖，此 workflow 属纯冗余。

---

### 4. `server-tests-baseline.yml` — 服务端全量测试（**当前长期红灯**）

- **触发条件**：`push` main，**paths 过滤** `app/**` + `tests/**` + `requirements.txt`
  + 自身文件；另 `workflow_dispatch`
- **实际作用**：8 片 matrix，每片独立 `pgvector/pgvector:pg16` + `redis:7-alpine`
  service 容器（库隔离），`find tests -name "test_*.py"` 排序后 round-robin 分片，
  硬门跑全量 pytest + junit artifact，最后 `baseline-summary` job 合并统计
- **阻塞合并**：❌ **否 —— 尽管注释自称"硬门"**（见头号发现）
- **引用路径**：✅ 无外部脚本引用；`tests/` 下 400 个 `test_*.py`（8 片 × 50）
- **最近运行**：🔴 **连续 12 次全部 failure**
  ```
  2026-10-10 10:05  failure  10m48s
  2026-10-10 08:12  failure  11m57s
  2026-10-10 07:39  failure  12m22s
  2026-10-10 05:35  failure  10m19s
  2026-10-09 13:38  failure  14m17s
  ...（回溯至 2026-10-09 06:43 亦全红）
  ```
- **判定**：🟡 **可疑 —— 但必须修，不能删**
- **理由**：
  - 这是**全仓唯一跑全量 `tests/` 的 workflow**（400 文件）。CLAUDE.md 称
    「此前 451 个测试文件从未有任何 workflow 跑过全量」—— 这个补位是真实且必要的
  - 🔴 **但 CLAUDE.md「基线 829 条红灯经 R1-R6 六轮收敛归零 / passed 2926 failed 0」
    的记载已与现状不符**。实测最近一次红灯 **~38 条 test 级失败**（30 FAILED + 8 ERROR）：
    ```
    FAILED tests/rag/test_multimodal_retriever.py            × 18
    FAILED tests/rag/test_rag_multimodal_e2e.py             × 5
    FAILED tests/rag/test_rag_query_cache_e2e.py            × 2
    FAILED tests/rag/test_wp1_meeting_chunks.py             × 2
    FAILED tests/rag/test_wp2_drive_index.py                × 2
    FAILED tests/e2e/test_kb_dedup_e2e.py                   × 1
    ERROR  tests/unit/test_embedding_backend_bge_m3.py      × 6
    ERROR  tests/rag/test_query_cache.py                    × 1
    ERROR  tests/test_embedding_timeout_cancel.py           × 1
    ```
  - 失败**高度集中**：`test_multimodal_retriever` / `test_embedding_backend_bge_m3` /
    `test_embedding_timeout_cancel` 全部围绕
    `get_or_compute_query_embedding` 与 `generate_embeddings` 的 patch 点 ——
    与 2026-10-10「embedding 线程泄漏隔离（专用有界 executor）」那次重构同一批符号。
    符合**类 20.181**（`from X import Y` 直接引用 ⇒ patch 目标必须是被调用模块的本地绑定）：
    重构改了被调用方的符号名/签名，mock 的 patch 目标漂移 ⇒ 用例全挂。
  - 🔴 且因为**无分支保护**，这 38 条红灯**从未阻塞任何一次提交**，已连续红 12 次无人处理

> **这是本次审计最重要的可执行结论**：不是"workflow 该不该删"，而是
> **"号称唯一的硬门实际是红着且没人管的"**。

---

### 5. `lint-css.yml` — 前端 CSS / 体量 / 设计令牌漂移

- **触发条件**：`pull_request` + `push` main，**paths 过滤** 10 条：
  `web/src/**`、`web/.stylelintrc.json`、`web/package.json`、`web/package-lock.json`、
  `web/playwright.config.js`、`web/tests/**`、`packages/design-tokens/**`、
  `apps/desktop/package.json`、`scripts/check-design-tokens-drift.sh`、
  `scripts/sync-design-tokens.sh`、`scripts/frontend-size-budget-check.sh`、
  `scripts/frontend-size-budget.txt`、workflow 自身
- **实际作用**：stylelint + Vitest + design-tokens 副本漂移门禁 + 体量棘轮
- **阻塞合并**：❌ 否（无分支保护）
- **引用路径**：✅ **10/10 全部存在**（逐个 `test -e` 核验）
- **最近运行**：全绿，2m23s ~ 3m0s，最近 2026-10-10 10:05
- **判定**：✅ **保留**
- **理由**：paths 过滤设计得相当严谨（连"守卫文件自身"和"基线预算文件"都放进 paths，
  避免"改了棘轮却不触发棘轮门禁"的自指漏洞）。触发范围合理，不会被后端提交误触发。
  与 `playwright.yml` 的 `web/**` 过滤存在部分重叠，但职责不同（lint vs 视觉回归），
  **不构成冗余**。

---

### 6. `qa-bench-baseline.yml` — D7 历史回归基线审计

- **触发条件**：`pull_request`（`types: [opened, reopened, synchronize]`，**无 paths 过滤**）
  + `workflow_dispatch`。🔴 **无 `push` 触发**
- **实际作用**：`scripts/ci_qa_bench_baseline.sh` 跑九文件基线（期望 71 PASS + 7 SKIP
  守恒门禁）+ 校验 `tests/test_baseline_audit.py` 仍处 archived 态
- **阻塞合并**：❌ 否
- **引用路径**：✅ `scripts/ci_qa_bench_baseline.sh`、`tests/qa-bench/requirements.txt` 均存在
- **最近运行**：最近 3 次 `workflow_dispatch` 全绿（2026-10-06/06/07）；
  🔴 **最近一次 `push` 到 main 上的运行是 2026-08-01**（此后 2 个多月从未在 main push 上跑过）
- **判定**：⚠️ **可疑（低危）**
- **理由**：
  - 它的设计本来就是 **PR 门禁**（把历史回归契约变成可执行），无 push 触发**符合设计**
  - 脚本注释诚实记录了 D5 门禁退役、`test_baseline_audit.py` 已 archived 等状态，
    无悬挂引用
  - 但**无分支保护 ⇒ 这个 PR 门禁同样不阻塞合并**，其"可执行回归契约"实际只是提示

---

### 7. `build-image.yml` — GHCR app-test 预构建镜像

- **触发条件**：`push` main，**paths 过滤** `app/**`、`scripts/init_test_db_all.py`、
  `alembic/**`、`Dockerfile`、`requirements.txt`、自身文件；另 `workflow_dispatch`
- **实际作用**：`docker/build-push-action@v5` 构建并推送
  `ghcr.io/<owner>/microbubble-agent:app-test-latest`，`cache-from/to: type=gha,mode=max`，
  `timeout-minutes: 60`
- **阻塞合并**：❌ 否
- **引用路径**：✅ `Dockerfile`、`scripts/init_test_db_all.py` 均存在
- **最近运行**：全绿，2m09s ~ 13m35s，最近 2026-10-10 10:05
- **判定**：✅ **保留**
- **理由 —— 关于「W67 step 48 路线」是什么**：
  W67 第 48 步（2026-07-23）确立的是**"路线 2：pre-built"**架构：把 app-test 镜像的
  构建从「每个 CI run 重 build（cold cache 6-12 分钟）」改为「push to main 时构建一次
  推到 GHCR，下游 workflow 直接 `docker pull`」。
  - **该架构今天仍然完全有效且是承重的**：`qa-bench-smoke.yml:101-130` 正是
    `docker pull` + `docker tag` 复用它（注释自证「照抄 D5」，D5 已删但模式已内化）
  - 头注释里 3 处提到「`qa-bench-ci.yml` (D5 门禁) 已于 2026-10-07 退役」——
    **核实：`qa-bench-ci.yml` 文件确实已不存在**，这些是**正确的历史说明，不是悬挂引用**
  - 60 分钟 timeout 是实测论证过的（同一条 apt 步 407s vs 1352.8s，3.3 倍离散），
    并附带 GHA cache TTL 7 天死锁的根因分析 —— 注释质量高，不是拍脑袋
  - ⚠️ 缓存 key 缓存互斥问题（"Measure A 刻意不做"）是已知且**有意为之**的取舍，非疏忽

---

### 8. `image-scan.yml` — Trivy 镜像漏洞扫描 🔴 **长期全红**

- **触发条件**：`pull_request`（paths: `Dockerfile*`、`docker/**`、`docker-compose*.yml`、
  `web/Dockerfile`、自身）+ `schedule` 每周一 05:00 UTC + `workflow_dispatch`
- **实际作用**：8 个镜像（app/db/funasr/mcp/voice-pipeline/whisper/web/commercial）
  各跑 config 扫描 + 真实 `docker build` + image 扫描。PR 上 `continue-on-error: true`
  （advisory），schedule/manual 上 `exit-code: '1'`（HIGH/CRITICAL 即 fail）
- **阻塞合并**：PR 上 ❌ 否（`continue-on-error`）；schedule 上本就没有合并概念
- **引用路径**：✅ **8/8 Dockerfile 全部存在**（逐个 `test -e`）
- **最近运行**：🔴 **最近 12 次里 11 次 failure，仅 1 次 success**
  ```
  2026-10-08 14:09  failure  1h00m16s  workflow_dispatch
  2026-10-07 13:43  failure  1h13m03s  workflow_dispatch
  2026-10-07 07:48  failure    15m47s  workflow_dispatch
  2026-10-07 07:35  failure     8m18s  workflow_dispatch (branch ci/l9-reverse-verify)
  2026-10-07 07:31  failure    15m11s  workflow_dispatch
  2026-10-05 14:54  success    48m29s  pull_request (fix/visual-flaky-vite-dep-reload)
  2026-10-05 11:57  failure    51m19s  schedule
  2026-09-28 11:21  failure    17m32s  schedule
  2026-09-21 10:19  failure    12m22s  schedule
  2026-09-14 10:13  failure    13m55s  schedule
  2026-09-07 09:51  failure  2h01m07s  schedule
  2026-08-31 11:15  failure     9m11s  schedule
  ```
- **判定**：🔴 **建议删 / 或必须重做基线**
- **理由 —— 这是最典型的"类 20.220 失效绿灯/常红"样本**：
  - **自 2026-08-31 起，每周一的定时安全扫描全部红**，已连续 5 周 + 5 次手动全红
  - 🔴 **每次烧掉 8-120 分钟 GitHub Actions 额度**（`docker build` 8 个镜像 × 每次，
    最近两次直接 1 小时起步），**产出为零**：没人看 SARIF、没人 triage
  - 唯一那次 success 还是 **PR 上**（`continue-on-error: true` 的 PR 路径，
    即 advisory 路径）—— 说明**硬路径（schedule）从来没绿过**
  - 根因几乎可以肯定是：**基础镜像本身带 HIGH/CRITICAL CVE**，
    而 `exit-code: '1'` 的门禁无任何 `.trivyignore` / 基线豁免文件 ⇒ 永久红
  - ⚠️ 它自己的注释（71-76 行）记录了 **L-9 缺陷**：曾经
    `continue-on-error: true` 让"构建失败 → 后续扫描全 skip → job 无失败步 → 结论 success"，
    造成"扫了空气还报平安"。**那个缺陷修好了（该红的红），但修好之后暴露的是
    「真实漏洞基线从未被治理」这第二层问题**，而第二层没人处理。
    这正是类 20.220 的「**修上游缺陷会暴露下游缺陷，一次连修三层才能到底**」。

> **建议**：要么建 `.trivyignore` + 记录"可接受 CVE 基线"让 schedule 变绿，
> 要么删掉 —— 但**不要留着每周烧 1 小时额度换一个永远红的红叉**。

---

### 9. `rag-framework-ci.yml` — RAG 框架测试（无 paths 过滤）

- **触发条件**：`push` main（**无 paths 过滤**）+ `pull_request` main（无过滤）
  + `workflow_dispatch`
- **实际作用**：① `pytest tests/rag_framework/ -v`（mock 模式，`SKIP_DB_SETUP=1`）；
  ② **alembic 单 head 守卫**（断言"恰为 1 个 (head)"，刻意不写死编号）
- **阻塞合并**：❌ 否
- **引用路径**：✅ `tests/rag_framework/` 存在（**9 个 `test_*.py`**）
- **最近运行**：全绿，36s-43s，**每个 commit 都跑**（含纯 docs 提交）
- **判定**：🟡 **可疑 —— 保留但需瘦身**
- **理由 —— 与 `server-tests-baseline.yml` 的重叠已取证**：
  - `tests/rag_framework/` 位于 `tests/` 之下，而 server-tests-baseline 用的是
    `find tests -name "test_*.py"`（全量 400 文件）⇒
    **这 9 个文件已被 server-tests-baseline 的 8 片全量扫覆盖**，测试执行层面**纯重复**
  - ✅ **唯一不可替代的价值 = alembic 单 head 守卫**（server-tests-baseline **没有**这个断言）。
    这条守卫直接对应 CLAUDE.md 2026-07-24「串单链纪律」事故
    （`Multiple head revisions are present` 阻塞部署），是真价值守卫，不该丢
  - ⚠️ **但它的执行代价与价值不成比例**：无 paths 过滤 ⇒ **纯 docs 提交也触发**
    （实测 `docs(structure): ...`、`docs(CLAUDE): ...` 全部触发了它），
    每次白跑 38s 装一遍 pip 依赖
  - ⚠️ 且它装的是**手写精简依赖列表**（不是 `-r requirements.txt`），注释里
    自证已因此漏过 `jieba` / `anthropic` / `pgvector` / `greenlet` 四个包，
    导致门禁长期红 —— 这是**用"手写列表"换"装 torch"的取舍留下的长期维护债**。
    现在 server-tests-baseline 已是唯一真源，这个取舍的理由不再成立

> **建议**：把 rag-framework-ci 瘦身为**只跑 alembic head 守卫**（约 20s，零依赖），
> 删掉 `pytest tests/rag_framework/` 那一段（已由 server-tests-baseline 覆盖），
> 或给它加 `paths: alembic/**` 过滤。

---

### 10. `playwright.yml` — Playwright（a11y + 视觉回归）

- **触发条件**：`pull_request`(main) + `push`(main)，**2026-10-09 刚补上 push 侧 paths 过滤**，
  11 条 paths；另 `workflow_dispatch`。`concurrency` 按 ref 分组 + `cancel-in-progress: true`
- **实际作用**：2 job 分跑（a11y axe-core / visual 快照），`web/tests/visual/` 下
  **46 个 `*.spec.mjs`**（含 49 张基线 PNG 快照）
- **阻塞合并**：❌ 否 —— 但注释自述 visual job 已于 2026-10-06 撤掉
  `continue-on-error` 转"硬门"，**这个"硬门"同样不阻塞**（无分支保护）
- **引用路径**：✅ 全部存在
  （`web/tests/visual/` 含 a11y/desktop/mobile/pwa/local-only 5 个子目录、
  `docker/visual-regression/` 4 文件、`docker-compose.test.yml`、
  `web/scripts/build-id.mjs`、`web/public`）
- **最近运行**：全绿，21m55s ~ 24m35s，最近 2026-10-10 10:05
  （2026-10-08 有 3 次 `cancelled` —— 即 2026-10-09 补 paths + concurrency 的动因）
- **判定**：✅ **保留**
- **理由**：paths 过滤清单写得极为克制且有论证（逐条列出**为何排除**
  `web/dist/**`、`scripts/init_db.py`），concurrency 闸门注释还专门解释了
  「为何 group 不带 `${{ github.job }}`」。是本次审计中注释质量最高的一个。
  ⚠️ 代价：单次 ~22 分钟，且 `web/src/**` 的任何改动都触发 —— 在无分支保护的前提下，
  这条 22 分钟的链路上的人等成本全部白付（因为没人被它挡住）。

---

### 11. `qa-bench-smoke.yml` — QA Bench 200 题 smoke（门禁已退役）

- **触发条件**：`pull_request`(main) + `push`(main)，**paths 极窄**：
  `app/agent/**`、`app/services/chat_history*.py`、`app/services/self_rag.py`、
  `app/services/reminder_*.py`（push 侧还少 `config.py`）、`tests/qa-bench/**`、自身文件
- **实际作用**：拉 GHCR 预构建镜像 → 起 test DB 栈（8001 端口）→ `init_db` +
  `ensure_test_user` → Login 取真 JWT → 主测 100 题 + 抽测 100 题
  （**经 OpenRouter 调真实 LLM**）→ 出 report
- **阻塞合并**：❌ **否 —— 且已主动退役门禁**
- **引用路径**：✅ `tests/qa-bench/` 存在（56 个 py 文件）；
  `scripts/init_db.py`、`scripts/ensure_test_user.py`、`scripts/benchmark_fast_vs_deep.py` 均存在
- **最近运行**：最近 3 次全绿（2026-10-07 退役后），此前 2026-10-06 连续 4 次 failure
- **判定**：🟡 **可疑 —— 已是纯探针，需决策去留**
- **理由**：
  - 🔴 **门禁已于 2026-10-07 主动退役**（commit `fa66f4f66`，
    "smoke 80% 通过率门禁退役, 仅报数保留探针"）。
    现在只剩 `if [ -f results/... ]` 的**文件存在性检查** —— 它**不校验通过率**，
    即"跑完 200 题就算过"，与 CLAUDE.md 记载的「5 分钟内必须通过，否则 PR 红 ✗ 阻断 merge」
    **完全脱节**
  - 🔴 它**每次运行都通过 OpenRouter 调真实 LLM 跑 200 题**（注释自述换真 LLM 后
    预算复算 15→30 分钟）—— **这是唯一一个花钱的 workflow，且产出的结论没人看**（门禁已退役）
  - ⚠️ paths 过滤**严重滞后**：只盯 `app/agent/**` + 4 个 services 文件，
    而按 CLAUDE.md，聊天链路的重心早已扩散（`page_transcript_retriever`、
    `embedding_service`、`hybrid_retriever` 等均不在过滤内）
  - ✅ 好的一面：注释**诚实记录了 D5 已退役**（"qa-bench-ci.yml 2026-10-07 已退役删除"），
    无悬挂文件引用；D7 退役后连续 3 次绿灯

---

## 重复 / 职责重叠判定

| 对 | 重叠程度 | 结论 |
|---|---|---|
| `qa-bench-smoke` ↔ `qa-bench-baseline` | 🟢 **不重叠** | smoke = 200 题端到端对话链（真 LLM、探针性质）；baseline = 71 PASS + 7 SKIP 历史回归契约守恒（离线、无 LLM）。**职责正交，两者都保留** |
| `build-image` ↔ `image-scan` | 🟢 **不应合并** | build = 构建推 GHCR（供下游 pull）；scan = 漏洞扫描（8 镜像）。前者是**制品生产**，后者是**制品审计**，构建顺序上还是 scan 依赖 build 的产物。合并会让"推制品"和"判红"耦合 |
| `rag-framework-ci` ↔ `server-tests-baseline` | 🔴 **真重叠** | 9 个 `tests/rag_framework/*.py` 已被 server-tests-baseline 的 `find tests -name "test_*.py"` 全量覆盖。**唯一不可替代的是 alembic 单 head 守卫** |
| `server-tests-baseline` ↔ `qa-bench-smoke` | 🟡 **部分冲突** | `tests/qa-bench/` 下 10 个 `test_*.py` **同时被** server-tests-baseline 的 400 文件全量扫收走。而 `tests/conftest.py:238/264` 有 `DROP SCHEMA public CASCADE` —— server-tests-baseline 靠"每片独立 service 容器"规避了 shard 间互砸，但**它与 qa-bench-smoke 在两个不同 workflow / 两套不同 DB 栈里跑 qa-bench 测试**，隔离边界不清晰，值得复核 |
| `lint-css` ↔ `playwright` | 🟢 **不重叠** | 前者 stylelint + 体量棘轮 + 令牌漂移；后者浏览器内 a11y + 像素级视觉回归。paths 有交集但判据不同 |

---

## 🔴 失效"永久绿灯" / "永久红灯"风险清单

| 风险 | workflow | 证据 |
|---|---|---|
| 🔴 **自称硬门、实际不阻塞** | `server-tests-baseline` | `branches/main/protection` 404 + `rulesets` `[]`；注释 L15-18 明确写"阻塞合并" |
| 🔴 **自称硬门、实际不阻塞** | `playwright` (visual) | 注释自述 2026-10-06 撤 `continue-on-error` 转硬门；同样无 required check |
| 🔴 **自称硬门、实际不阻塞** | `lint-css` / `secret-scan` / `rag-framework-ci` / `qa-bench-baseline` | 同上 |
| 🔴 **连续 12 次红灯无人管** | `server-tests-baseline` | ~38 条 test 级失败，集中在 embedding 重构的 patch 漂移（类 20.181） |
| 🔴 **连续 5 周定时红灯 + 烧额度** | `image-scan` | schedule 自 2026-08-31 全红，每次 8-120 分钟，产出为零 |
| 🟡 **门禁名存实亡** | `qa-bench-smoke` | 80% 通过率门禁 2026-10-07 退役，只剩文件存在性检查；但仍跑 200 题真 LLM |
| 🟡 **悬挂分支引用** | `secret-scan` | `on: dev` 分支，但仓库实测只有 `main` 一个分支 |
| 🟡 **1 次运行即失败、日志已过期** | `upload-download-page` | 全生命周期仅 1 次运行（failure, 5s, 2026-09-28），根因无法取证 |
| 🟢 **注释里的 "已退役 D5" 是正确历史说明，非悬挂引用** | `build-image` / `qa-bench-smoke` | `qa-bench-ci.yml` 确认已不存在，注释如实记录 |
| 🟢 **无被注释掉的 job / step 残留** | 全部 11 个 | `grep` 全仓 workflow 未发现整段注释掉的 job |

---

## 汇总表

| # | workflow | 触发 | 阻塞合并 | 路径齐全 | 最近状态 | 判定 |
|---|---|---|---|---|---|---|
| 1 | `secret-scan.yml` | PR/push(main,dev)/周cron | ❌ | ✅ | ✅ 绿 30s | **保留** |
| 2 | `desktop-release.yml` | tag `v*`/dispatch | ❌ | ✅ | ✅ 绿（09-29） | **保留** |
| 3 | `upload-download-page.yml` | dispatch only | ❌ | ✅ | 🔴 1 次运行即红 | **可疑** |
| 4 | `server-tests-baseline.yml` | push(paths)/dispatch | ❌* | ✅ | 🔴 **连红 12 次** | **可疑（必修）** |
| 5 | `lint-css.yml` | PR/push(paths) | ❌ | ✅ 10/10 | ✅ 绿 2m | **保留** |
| 6 | `qa-bench-baseline.yml` | PR(no paths)/dispatch | ❌ | ✅ | ✅ 绿（无 push） | **可疑（低危）** |
| 7 | `build-image.yml` | push(paths)/dispatch | ❌ | ✅ | ✅ 绿 | **保留** |
| 8 | `image-scan.yml` | PR(paths)/周cron/dispatch | ❌ | ✅ 8/8 | 🔴 **连红 5 周+** | **建议删/重做** |
| 9 | `rag-framework-ci.yml` | push **无过滤**/PR/dispatch | ❌ | ✅ | ✅ 绿 38s | **可疑（瘦身）** |
| 10 | `playwright.yml` | PR/push(paths 11条)/dispatch | ❌* | ✅ | ✅ 绿 22m | **保留** |
| 11 | `qa-bench-smoke.yml` | PR/push(paths 窄) | ❌ | ✅ | ✅ 绿（门禁已退役） | **可疑（决策）** |

**判定分布**：保留 **5** / 可疑 **5** / 建议删 **1**

\* 注释自称硬门，但因无分支保护实际不阻塞

---

## 清理建议（按优先级）

### P0 — 先修这个，它比"删不删 workflow"重要一个量级

**建议动作**：给 `main` 开分支保护 + 把 `server-tests-baseline` / `playwright` / `lint-css`
设为 required status check；**在修完 38 条红灯之前，先把 `server-tests-baseline`
设为 required**，让红色可见化。

- **风险**：⚠️ **中高**。一旦设为 required，**当前 38 条红灯会立刻锁死所有合并**，
  必须先修完红灯再开保护，否则全队（含自动化 agent）无法提交。
  建议顺序：① 修红灯 → ② 开保护 → ③ 修 image-scan。
- **收益**：🔴 **最高**。当前状态下 11 个 workflow 的全部投入（~22min Playwright、
  ~11min 全量测试、每周 1h Trivy）**对"代码能不能进主干"零影响**。
  开保护后这些成本才转化为质量保障。
- **备注**：这是本次审计**唯一一条"不该做就等于前面全白做"的建议**。
  在此之前，讨论"哪些 workflow 该删"是本末倒置。

### P1 — 修 `server-tests-baseline` 的 38 条红灯

**建议动作**：按失败聚类处理，90% 集中在 embedding 重构的 patch 漂移
（`get_or_compute_query_embedding` / `generate_embeddings`）—— 对照**类 20.181**
把 `patch()` 目标从被调用模块的本地绑定改回，或给新符号名补兼容别名。

- **风险**：🟢 低（纯测试代码修复，不动 production code）
- **收益**：🔴 高。恢复 CLAUDE.md 声称的"全量 0 红灯"基线；否则该基线记载应立即更正，
  否则它就是**下一个"状态字段说谎"的实例**

### P2 — 处置 `image-scan.yml`（二选一）

- **方案 A（推荐）**：加 `.trivyignore` + 在 workflow 里写明「已接受 CVE 基线」，
  让 schedule 变**真绿**（当前红是基础镜像固有 CVE，不是新引入的）
- **方案 B**：直接删除。每周烧 8-120 分钟额度换一个没人看的红叉，是纯负收益

- **风险**：🟢 低（A 有"漏掉真漏洞"的风险，需配合定期人工 review；
  B 有"失去漏洞可见性"的风险，但**当前它本来就没有可见性**）
- **收益**：🟡 中高。省 GitHub Actions 额度 + 消除一个长期红灯对团队信号的污染

### P3 — 瘦身 `rag-framework-ci.yml`

**建议动作**：删掉 `pytest tests/rag_framework/` 那一 step（已由 server-tests-baseline
覆盖，9 文件全重复），只保留 **alembic 单 head 守卫**；并加 `paths: alembic/**` 过滤。

- **风险**：🟢 低。唯一需确认的是 9 个 rag_framework 测试在
  server-tests-baseline 里**真的被跑到了**（`find tests -name "test_*.py"` 覆盖 `tests/` 下全部，
  已实测 400 文件 / 8 片 × 50，逻辑上覆盖）
- **收益**：🟡 中。消除 100% commit（含纯 docs）触发的无谓 38s + pip 依赖安装；
  同时甩掉那条"手写精简依赖列表"的长期维护债（已漏过 4 个包）

### P4 — 决策 `qa-bench-smoke.yml` 的去留

**建议动作**：门禁已于 2026-10-07 退役（只剩文件存在性检查），但每次仍跑 200 题
**真 LLM**（OpenRouter 付费）。二选一：
① 要么把 paths 过滤拓宽到真实的聊天链路（`app/services/embedding_service.py`、
`hybrid_retriever.py`、`page_transcript_retriever.py` 等）并恢复真正的通过率门禁；
② 要么降级为手动 dispatch（与 `upload-download-page.yml` 同策），停止每次触发。

- **风险**：🟡 中。降级会丢失 RAG 改动的端到端信号（不过按现状它也没在门禁）
- **收益**：🟡 中。省 OpenRouter 调用成本 + 每次 3-30 分钟的 Actions 时间

### P5 — 清理悬挂引用（低危，10 分钟内可做完）

**建议动作**：
- `secret-scan.yml`：删掉 `dev` 分支（仓库实测只有 `main`）
- `upload-download-page.yml`：确认是否还需要（其能力已被
  `desktop-release.yml:114-126` 的 OSS 镜像步覆盖）。若确认冗余则删
- 更正 CLAUDE.md 中 `server-tests-baseline` 的「2926 passed / 0 failed」记载

- **风险**：🟢 极低
- **收益**：🟢 低（但消除"看起来配置了实际不存在"的误导项，符合类 20.220 的方法学）

---

## 本次审计的局限（如实说明）

1. **`upload-download-page` 失败根因无法取证** —— 唯一那次运行（2026-09-28）的日志
   已过 GitHub 默认 90 天保留期，`gh run view --log-failed` 返回 `log not found`。
   该 workflow 是否真的坏了**未经验证**，只能确认"跑过一次且失败，之后没人再用"。

2. **`image-scan` 红的具体 CVE 未逐条取证** —— 未拉取 SARIF artifact 逐条分析。
   "基础镜像固有 CVE"是基于 `exit-code: '1'` + 无 `.trivyignore` 的**推断**，
   非实测。若采纳方案 A，建议先拉一次 SARIF 确认。

3. **未做本地复现** —— 本次为纯只读审计，未在容器内复跑 pytest 验证 38 条红灯的
   根因分类（`patch` 漂移 vs 真回归）。P1 建议执行时需先本地复现确认。

4. **未评估 CI 额度成本** —— 未能查询实际 Actions minutes 消耗。
   「每周烧 1 小时」是基于 workflow 日志时长的推算，非账单数据。

5. **「阻塞合并」的结论基于当前配置** —— 若仓库管理员已在别处（如 org 级 ruleset、
   本地 pre-push hook）设置了门禁，本次 `rulesets: []` 的查询只覆盖 repo 级。
   建议与管理员确认后再执行 P0。