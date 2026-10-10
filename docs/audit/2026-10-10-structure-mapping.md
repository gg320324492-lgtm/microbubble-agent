# 全项目结构测绘 (2026-10-10)

> **取证报告，非重构方案。** 全部数据为 2026-10-10 `main` @ `6a0dc9bd0` 只读测绘。
> 本次测绘**未移动、未删除、未重命名任何文件**，未 commit / push / git add / checkout / restore / stash / clean，
> 未改任何配置，未碰任何 docker 容器状态（未 restart/up/down/rm）。
> 唯一写入即本报告文件。

---

## 摘要

| 维度 | 数据 |
|---|---|
| 顶层条目 | **53** 个（`git ls-files` 第一段去重） |
| git 跟踪文件总数 | **3923** |
| 提交数 | 4617+ |
| tests/ 子目录 | **33** 个（顶层散装文件另有若干） |
| tests/ 中 `_xNN` 零引用目录 | **9** 个（已全部逐个取证，见 B2） |
| scripts/ 文件总数 | **247** = 顶层 **201** + 子目录 **46** |
| scripts/ 顶层 `.py` | **130** 个（"135 个"含子目录 py，实测顶层 130） |
| scripts/ 子目录 | **15** 个（不是 16） |
| CI 高危脚本��用 | **19** 个唯一路径 |
| 计划任务硬编码绝对路径 | **4** 个 MicroBubble 任务指向 `E:\microbubble-agent\scripts\` |

**风险分级**

- **🔴 高危（改动立刻炸）**：3 处 —— ① 4 个 Windows 计划任务硬编码 `E:\microbubble-agent\scripts\`；
  ② `docker-compose.yml` 的 4 类 volume mount（`./app` `./alembic/versions` `./nginx/*` `./web/dist`）；
  ③ `tests/` 30 个文件用 `Path(__file__).resolve().parents[2]` 反推仓库根。
- **🟡 中危（CI 会红）**：19 个 CI/pre-commit 引用脚本 + `web/package.json` 3 条 `../scripts/k6/` 跨边界路径��
- **🟢 低危（可��由动）**：`docs/` `memory/` `results/` `.agents/` `packages/` `commercial/` 内部布局。

**核心结论**

1. **改 `tests/` 目录结构不会让 `server-tests-baseline.yml` 红** —— 分片用 `find tests -name "test_*.py"`，
   **路径无关**，只认文件名模式。但**同 basename 会炸**（实测已有 1 组三重复）。
2. **改 `scripts/` 顶层文件名是最危险的动作** —— 4 个计划任务 + 19 处 CI 引用写死路径。
3. **`desktop-conversion/` 是独立 git 仓（193 commits + 私有远端），不在主仓 `git ls-files` 里** ——
   任何全仓重构脚本若用 `git ls-files` 驱动都会**静默漏掉它**。
4. **`pnpm-workspace.yaml` 只含 `apps/*` + `packages/*`，`web/` 不在 workspace 内** —— 三套前端各自独立构建。

---

## A. 顶层结构总表

体积列为 **git 跟踪字节**（`du -ch` of `git ls-files`），非磁盘占用（磁盘另含 `node_modules` 466M + `web/dist`）。

| 条目 | 类型 | 跟踪体积 | 文件数 | 被谁引用 | 归类建议 | 风险 |
|---|---|---|---|---|---|---|
| `web/` | 核心代码（Vue 3 前端） | — | **1038** | compose `./web/dist`；`lint-css.yml` `playwright.yml`(`web/tests/**`)；`web/package.json` | 核心代码 — 保持 | 🟡 |
| `docs/` | 文档 | 13M | 654 | 内部互相引用；`brief_v41_x6` 断言 `docs/dispatch-template-v4.1.md` | 文档 — 保持 | 🟢 |
| `tests/` | 测试 | 16M | 548 | `pytest.ini` `testpaths`；CI `tests/**`；`qa-bench-*.yml` `rag-framework-ci.yml` | 测试 — 保持 | 🔴（见 B） |
| `memory/` | 文档/记忆 | 993K | 487 | 无代码引用；69 文件含绝对路径 | 文档 — 保持 | 🟢 |
| `app/` | 核心代码（FastAPI） | 5.1M | 409 | compose `./app:/app/app` ×4 服务；`Dockerfile*`；`alembic` | 核心代码 — **不可动** | 🔴 |
| `scripts/` | 工具链 | 2.2M | 247 | **19 处 CI** + **4 计划任务** + pre-commit 10 处 | 工具链 — **可分类，勿改名** | 🔴 |
| `apps/` | 核心代码（Electron 桌面端） | 2.4M | 213 | `pnpm-workspace.yaml`；`desktop-release.yml`(wd=`apps/desktop`) | 核心代码 — 保持 | 🟡 |
| `alembic/` | 迁移 | 574K | 118 | compose `./alembic/versions` ×4；`alembic.ini` | 核心代码 — **不可动** | 🔴 |
| `results/` | 数据（bench 产物） | 4.9M | 65 | 无代码引用（`qa-bench-smoke.yml` 的 `results/` 是 `working-directory: tests/qa-bench` 下相对路径） | 数据/归档 — 可移 | 🟢 |
| `.agents/` | 工具链（skills） | — | 54 | 无代码引用；`.dockerignore` 排除 | 工具链 — 保持（红线：不碰） | 🟢 |
| `.github/` | CI 配置 | — | 11 | 全部 workflow | 构建部署 — **不可动** | 🔴 |
| `observability/` | 配置（Grafana provisioning） | 23K | 10 | **compose 里无任何 grafana/prometheus 服务引用** → 孤儿 | 边界模糊 → 建议并入 `deploy/` | 🟢 |
| `docker/` | 构建部署 | 41K | 7 | `Dockerfile.commercial` `visual-regression/` | 构建部署 — 保持 | 🟡 |
| `nginx/` | 构建部署 | 41K | 5 | compose `./nginx/nginx.conf` `./nginx/conf.d` `./nginx/ssl` ×ro | 构建部署 — **不可动** | 🔴 |
| `tunnel/` | 运维 | 25K | 4 | `tunnel/start-ssh-tunnel.vbs` 含绝对路径；被 `scripts/tunnel/guard-ssh-tunnel.ps1` 引用 | 运维 — 可并入 `scripts/ops/` | 🟡 |
| `mcp_server/` | 核心代码（MCP vision） | 14K | 4 | `Dockerfile.mcp` COPY（profile 隔离，默认不启） | 核心代码 — 保持 | 🟡 |
| `packages/` | 前端共享（design-tokens） | 89K | 2 | `pnpm-workspace.yaml` | 核心代码 — 保持 | 🟢 |
| `data/` | 运行时数据 | — | 2 | compose `./data:/app/data` ×4 + `./data/postgres` `./data/redis` `./data/neo4j` `./data/ollama` | 数据运行时 — **不可动** | 🔴 |
| `commercial/` | 核心代码（商业化） | 58K | 11 | `docker/Dockerfile.commercial:71` `COPY commercial/ /app/commercial/` | 边界模糊 → 建议并入 `app/` | 🟡 |
| `config/` | 配置 | 4K | 1 | **零引用** —— `config/intent_routing.yaml` 无任何代码/CI 引用 | 边界模糊 → 孤儿，需确认 | 🟢 |
| `.claude/` | 工具链 | — | 1 | 仅 `.claude/voice-alert-readme.md` | 保持（红线：不碰） | 🟢 |
| `.codex/` | 工具链 | — | 1 | 仅 `.codex/config.toml` | 保持（红线：不碰） | 🟢 |
| `.env.example` | 配置 | — | 1 | 文档/部署参考 | 保持（红线：不碰） | 🟢 |
| `.env.production.example` | 配置 | — | 1 | 同上 | 保持 | 🟢 |
| `Dockerfile` | 构建部署 | — | 1 | `build-image.yml`；`COPY . .` | 构建部署 — 保持 | 🟡 |
| `Dockerfile.db` | 构建部署 | — | 1 | compose | 构建部署 | 🟡 |
| `Dockerfile.funasr` | 构建部署 | — | 1 | compose | 构建部署 | 🟡 |
| `Dockerfile.mcp` | 构建部署 | — | 1 | compose profile `vision` | 构建部署 | 🟡 |
| `Dockerfile.voice-pipeline` | 构建部署 | — | 1 | compose | 构建部署 | 🟡 |
| `Dockerfile.whisper` | 构建部署 | — | 1 | compose | 构建部署 | 🟡 |
| `docker-compose.yml` | 构建部署 | — | 1 | 全部服务编排 | 构建部署 — **不可动** | 🔴 |
| `docker-compose.dev.yml` | 构建部署 | — | 1 | 本机开发 | 构建部署 | 🟡 |
| `docker-compose.test.yml` | 构建部署 | — | 1 | 测试栈；`:79` 引 `scripts/init_test_db_all.py` | 构建部署 — 不可动 | 🔴 |
| `funasr_entrypoint.sh` | 构建部署 | — | 1 | compose `:264` mount → `/app/entrypoint.sh` | 构建部署 — **不可动** | 🔴 |
| `whisper_entrypoint.sh` | 构建部署 | — | 1 | compose | 构建部署 | 🟡 |
| `alembic.ini` | 配置 | — | 1 | `script_location = alembic` | 配置 — 不可动 | 🔴 |
| `pytest.ini` | 配置 | — | 1 | `testpaths = tests` | 配置 — 不可动 | 🔴 |
| `package.json` | 配置（monorepo 根） | — | 1 | `pnpm --filter @mb/desktop` | 配置 — 不可动 | 🟡 |
| `pnpm-workspace.yaml` | 配置 | — | 1 | `apps/*` + `packages/*` | 配置 — 不可动 | 🟡 |
| `pnpm-lock.yaml` | 配置 | — | 1 | pnpm | 配置 | 🟡 |
| `requirements.txt` | 配置 | — | 1 | Dockerfile ×2 + CI `cache-dependency-path` | 配置 — 不可动 | 🔴 |
| `.pre-commit-config.yaml` | 配置 | — | 1 | 10 处 `scripts/` 引用 | 配置 — **不可动** | 🔴 |
| `.dockerignore` | 配置 | — | 1 | Docker build context | 配置 | 🟡 |
| `.gitignore` | 配置 | — | 1 | git | 配置 | 🟢 |
| `.gitleaks.toml` | 配置 | — | 1 | `secret-scan.yml` | 配置 | 🟡 |
| `.hintrc` | 配置 | — | 1 | webhint | 配置 | 🟢 |
| `setup.ps1` | 工具链 | — | 1 | 开发环境 | 工具链 | 🟢 |
| `restart_gpu_workers.bat` | ��维 | — | 1 | 含 4 处 `E:\microbubble-agent\...` 绝对路径 | 运维 | 🟡 |
| `CLAUDE.md` | 文档 | — | 1 | `brief_v41_x6/test_doc_exists.py` 断言它 | 文档 — **有测试依赖** | 🟡 |
| `AGENTS.md` | 文档 | — | 1 | 引用 `_archive` | 文档 | 🟢 |
| `CHANGELOG.md` | 文档 | — | 1 | — | 文档 | 🟢 |
| `README.md` | 文档 | — | 1 | — | 文档 | 🟢 |
| `ROADMAP.md` | 文档 | — | 1 | — | 文档 | 🟢 |

### A1. 边界模糊目录逐一判定

| 目录 | 判定 | 依据 |
|---|---|---|
| **`desktop-conversion/`** | **🔴 独立 git 仓，不在主仓** | 主仓 `git ls-files` 命中 **0**；磁盘上有独立 `.git/`；`git remote -v` = `https://github.com/gg320324492-lgtm/microbubble-desktop-conversion.git`；**193 commits**，branch `main`。**重构影响**：① 任何以 `git ls-files` 为驱动的批量脚本会**静默跳过**它（易被误认为"已处理"）；② 它有自己的 `docs/plans/` `docs/handoff/`，主仓 CLAUDE.md **反复引用**其文档；③ 无 `.gitmodules`，故**不是 submodule** —— 主仓 git 完全不知道它的存在，改名/删除主仓无感知，但**主仓文档引用会全悬空**。建议：**重构范围显式排除**，并在报告/方案里单列一条"主�� ↔ desktop-conversion 文档交叉引用表"。 |
| **`apps/` vs `web/` vs `packages/`** | **🟡 三套并存，非统一 workspace** | `pnpm-workspace.yaml` = `['apps/*', 'packages/*']` —— **`web/` 不在其中**。`package.json` 描述明写"web/ 仍为独立 npm 工程, N6 再接入"。`apps/desktop/package.json` name = `@mb/desktop`。`web/package.json` name = `microbubble-agent-web`，用 `npm`（有独立 `node_modules` 466M）。`packages/design-tokens/` = 共享 CSS 变量。三者构建互不触发。**重构影响**：改 `apps/` 或 `packages/` 会动 pnpm lock；改 `web/` 不影响 lock 但影响 compose mount。 |
| **`commercial/`** | **🟡 活代码但被 compose 忽略** | `docker/Dockerfile.commercial:71` `COPY commercial/ /app/commercial/`。主 `docker-compose.yml` **无 commercial 服务**（仅有 `Dockerfile.commercial` 存在）。`app/models/billing.py` 表 `commercial_plans`/`commercial_tenants`/`commercial_subscriptions` + `app/middleware/license_middleware.py` `tenant_middleware.py` + `app/api/v1/billing.py` `tenants.py` 构成完整链路（**这些在 `app/` 内，是活的**）。`commercial/` 包内 Python **几乎无人 import** —— 仅 `tests/test_w80_7d_commercial_operation_e2e.py` 有 `import commercial_7d_monitor`（那实际是 `scripts/` 里的文件，非本包）。建议：与 `app/` 边界需主指挥定夺。 |
| **`observability/`** | **🟢 孤儿** | compose 中无 grafana/prometheus/observability 服务（只有 `postgres-exporter` 镜像行）。10 个文件全是 Grafana provisioning + SQL query。重构自由度高。 |
| **`packages/`** | 🟢 仅 2 文件 | `design-tokens/package.json` + `variables.css`。 |
| **`mcp_server/`** | 🟡 活但 profile 隔离 | `Dockerfile.mcp` COPY `mcp_server/` + `app/config.py` + `app/services/vision_service.py` + `app/core/llm.py`；compose profile `vision` 默认不启。 |
| **`results/`** | 🟢 纯归档 | 65 文件 4.9M bench 产物，**零代码引用**。CI 里 `results/smoke` 等是 `working-directory: tests/qa-bench` 下的**相对路径**，与本目录无关。 |
| **`config/`** | 🟢 孤儿 | `config/intent_routing.yaml` — 全仓（`*.py` `*.yml` `*.yaml`）**零引用**。 |
| **`docker/`** | 🟡 | 7 文件：`Dockerfile.commercial` + `commercial/` + `visual-regression/`。 |
| **`tunnel/`** | 🟡 与 `scripts/tunnel/` 交叉引用 | `tunnel/` 4 文件（`README.md` `setup-ssh-key.ps1` `start-ssh-tunnel.ps1` `start-ssh-tunnel.vbs`）；`scripts/tunnel/` 4 文件（`guard-ssh-tunnel.ps1/.bat` `install-*.bat` `uninstall-*.bat`）。**非重复**：前者"建隧道"，后者"守护隧道"。但 `guard-ssh-tunnel.ps1:10` 引用 `tunnel/start-ssh-tunnel.ps1`（跨顶层目录），且计划任务 `MicroBubble-SSH-Tunnel-Guard` → `scripts/run-hidden.vbs` → `scripts/tunnel/guard-ssh-tunnel.ps1`。合并会打断这条链。 |

---

## B. tests/ 现状

### B1. 全部子目录表（33 个）

体积列为 git 跟踪字节。"CI 引用"列 = 是否被某 workflow 显式路径引用。

| 目录 | 文件数 | CI 引用 | conftest | 活/归档 | 可动? |
|---|---|---|---|---|---|
| `tests/qa-bench/` | 126 | ✅ `qa-bench-smoke.yml`(×5, wd=该目录) / `qa-bench-baseline.yml`(`requirements.txt`) | ✅ | 活 | 🟡 有 CI wd 依赖 |
| `tests/rag/` | 52 | ❌（但被 baseline 全量收） | ✅ | 活 | 🟡 5 文件用 `parents[2]` |
| `tests/unit/` | 40 | ❌ | ❌ | 活 | 🟢 |
| `tests/rag_framework/` | 11 | ✅ `rag-framework-ci.yml:120` `pytest tests/rag_framework/` | ✅ | 活 | 🟡 CI 显式路径 |
| `tests/integration/` | 9 | ❌ | ❌ | 活 | 🟢 |
| `tests/realenv/` | 7 | ❌ | ✅ | 活 | 🟢 |
| `tests/perf/` | 7 | ❌ | ✅ | 活 | 🟢 |
| `tests/e2e/` | 6 | ❌ | ❌ | 活 | 🟡 1 文件 `parents[2]` |
| `tests/request_context/` | 4 | ❌ | ❌ | 活 | 🟢 |
| `tests/rag_eval/` | 4 | ❌ | ❌ | 活 | 🟢 |
| `tests/visual/` | 3 | ✅ `playwright.yml:344,352,681` | ❌ | 活 | 🔴 CI 显式 3 处 |
| `tests/sentry/` | 3 | ❌ | ❌ | 活 | 🟡 3 文件 `parents[2]` |
| `tests/precommit/` | 3 | ❌ | ❌ | 活 | 🟡 2 文件 `parents[2]` |
| `tests/trivy/` | 2 | ❌ | ❌ | 活 | 🟡 2 文件 `parents[2]` |
| `tests/playwright_ci/` | 2 | ❌ | ❌ | 活 | 🟡 1 文件 `parents[2]` |
| `tests/pg_exporter/` | 2 | ❌ | ❌ | 活 | 🟡 2 文件 `parents[2]` |
| `tests/k6/` | 2 | ❌ | ❌ | 活 | 🟡 1 文件 `parents[2]` |
| `tests/api/` | 2 | ❌ | ❌ | 活 | 🟢 |
| `tests/alembic/` | 2 | ❌ | ❌ | 活 | 🟡 1 文件 `parents[2]` |
| **`tests/ci_real_x29/`** | 2 | ❌ | ❌ | 1 归档 | ✅（见 B2） |
| **`tests/brief_v41_x6/`** | 1 | ❌ | ❌ | 归档 | ✅ |
| **`tests/src_tests_x5/`** | 1 | ❌ | ❌ | **活** | ✅ |
| **`tests/icon_wr1/`** | 1 | ❌ | ❌ | 归档 | ✅ |
| **`tests/inject_auth_x4/`** | 1 | ❌ | ❌ | 归档 | ✅ |
| **`tests/axe_violation_x19/`** | 1 | ❌ | ❌ | 归档 | ✅ |
| **`tests/a11y_violation_x2/`** | 1 | ❌ | ❌ | 归档 | ✅ |
| **`tests/baseline_sync_x29/`** | 1 | ❌ | ❌ | **活** | ✅ |
| **`tests/a11y_login_x18/`** | 1 | ❌ | ❌ | **活** | ✅ |
| `tests/scripts/` | 1 | ❌ | ❌ | 活 | 🟢 |
| `tests/npm_audit/` | 1 | ❌ | ❌ | 活 | 🟡 1 文件 `parents[2]` |
| `tests/gitleaks/` | 1 | ❌ | ❌ | 活 | 🟢 |
| `tests/eval/` | 1 | ❌ | ❌ | 活 | 🟢 |
| `tests/dist_health/` | 1 | ❌ | ❌ | 活 | 🟡 1 文件 `parents[2]` |

**conftest.py 分布（6 个）**：`tests/conftest.py`（452 行，**唯一根锚**）、`tests/perf/`、`tests/qa-bench/`、`tests/rag/`、`tests/rag_framework/`、`tests/realenv/`。
仓库根**无** `conftest.py`（已实测 `ls conftest.py` → No such file）。

### B2. 9 个 `_xNN` 目录逐个

| 目录 | 测什么（文件头 docstring 一句话） | 文件 | 活/归档 | 建议归入 |
|---|---|---|---|---|
| `tests/a11y_login_x18/` | W91-X-18：a11y baseline 必**真登录态**生成 —— 防 `injectAuth()` 缺 `TEST_TOKEN` 时 `return false` 静默降级导致 3 次假绿 | `test_authed_field.py` | **活** | 与其它 3 个 a11y 守卫合并 → 新建 `tests/a11y/`（或并入 `tests/visual/` 下的 `visual/a11y/`，与 `web/tests/visual/a11y/` 对齐）。⚠️ 移动需同步改 `parents[2]` → `parents[1]` |
| `tests/a11y_violation_x2/` | W92-X-2：真违规为 0 守卫 —— 25 baseline × 274 处 violations 修完后的终态验证 | `test_no_real_violation.py` | 归档 | 同上（已归档，随 `a11y/` 一起搬） |
| `tests/axe_violation_x19/` | W91-X-19：真违规 axe rule 修门禁（color-contrast 72→0）。**本文件已因 basename 冲突被 rename 过**（原 `test_no_real_violation.py` 与 `a11y_violation_x2` 同名触发 pytest import mismatch） | `test_axe_x19_no_real_violation.py` | 归档 | 同上。**改名时务必保持 basename 全局唯一**（见 B3 风险） |
| `tests/baseline_sync_x29/` | W89-X-29：a11y baseline **必入 git** —— 断言 baseline 文件数 ≥25 且被 git 跟踪 | `test_sync.py` | **活** | 同 `a11y/` 组 |
| `tests/brief_v41_x6/` | 验收快照 —— 断言 `docs/dispatch-template-v4.1.md` 存在且含 6 个类号 | `test_doc_exists.py` | 归档 | 并入 `tests/precommit/` 或新建 `tests/docs_contract/` |
| `tests/ci_real_x29/` | W91-X-29：CI 真部署模拟 e2e（gated by `TEST_TOKEN`，需真服务器/凭据） | `__init__.py` + `test_deployment.py` | 归档 | 并入 `tests/realenv/`（语义最接近：需真环境） |
| `tests/inject_auth_x4/` | W92-X-4：`injectAuth` fail-loud 守卫（类 20.23 负向对照）—— 无 token 必 exit≠0 | `test_fail_loud.py` | 归档 | 并入 `a11y/` 组（它就是 a11y 假绿的根因守卫） |
| `tests/icon_wr1/` | W91-WR-1：`RAGEvalPanel.vue` 的 `Play` icon 不存在导致 `npm run build` exit 1 的 P0 硬门禁 | `test_play_to_video.py` | 归档 | 并入 `tests/dist_health/`（同为前端构建硬门） |
| `tests/src_tests_x5/` | W90-X-5：vitest spec 命名门禁 —— `web/src/__tests__/` 必无 `.spec.js` | `test_naming.py` | **活** | 并入 `tests/dist_health/` 或新建 `tests/web_conventions/` |

**汇总**：9 目录共 **11 个文件**，其中 **6 个已归档**（模块级 `pytest.skip(allow_module_level=True)`）、**3 个活的**（`a11y_login_x18` / `baseline_sync_x29` / `src_tests_x5`）。

### B3. CI 硬门约束 ★

**结论：把 `_xNN` 目录改名/合并，`server-tests-baseline.yml` 不会红。** 依据：

1. **分片逻辑路径无关**（`server-tests-baseline.yml:118-120`）：
   ```bash
   find tests -name "test_*.py" | sort | awk -v N=8 '{print > (".pytest-chunks/chunk-" (NR % N) ".txt")}'
   ```
   只按 **basename 模式** `test_*.py` 递归扫 `tests/`，**不枚举任何子目录名**。目录改名 → 文件仍被扫到 → 分片重算 → 正常。

2. **执行也路径无关**（`:141-145`）：
   ```bash
   tr '\n' '\0' < .pytest-chunks/chunk-N.txt | xargs -0 python -m pytest -q ...
   ```
   读文件清单逐个传参，不依赖 `tests/<name>` 字面量。

3. **触发条件宽**（`:23-27`）：`paths: ["app/**", "tests/**", "requirements.txt", ".github/workflows/server-tests-baseline.yml"]` —— 只认 `tests/` 前缀。

**但有 3 个真会让 CI 红的 tests/ 改动**：

| 触发条件 | 后果 | 依据 |
|---|---|---|
| **basename 冲突** | pytest `import file mismatch` collection error | 实测已存在 1 组三重复：`tests/test_intent_classifier.py` / `tests/unit/test_intent_classifier.py` / `tests/rag/test_intent_classifier.py`（靠 18 个 `__init__.py` 化解）。**移动文件时若脱离 `__init__.py` 保护层，冲突立刻复现** —— `axe_violation_x19` 就是为此被 rename 过一次 |
| **改 `tests/rag_framework/` 路径** | `rag-framework-ci.yml:120` 写死 `pytest tests/rag_framework/` | 该 workflow 独立于 baseline |
| **改 `tests/visual/` 路径** | `playwright.yml:344,352,681` 三处写死 `-c tests/visual/...mjs` / `VIZ_CONFIG=tests/visual/...` | 同上 |
| **改 `tests/qa-bench/` 路径** | `qa-bench-smoke.yml` **5 处** `working-directory: tests/qa-bench`；`qa-bench-baseline.yml:44,50,118` 3 处路径 | 同上 |

### B4. 🔴 tests/ 真正的头号约束：`parents[2]` 深度锁定

**实测：44 个 tests 文件用 `Path(__file__).resolve().parents[N]` 定位路径，其中 30 个用 `parents[2]` 反推仓库根。**

分布：`parents[2]`×42、`parents[1]`×23、`parents[3]`×3、`parents[4]`×1。

含义：`tests/<subdir>/<file>.py` 的 `parents[0]`=`<subdir>`、`parents[1]`=`tests/`、**`parents[2]`=仓库根**。
**任何把 `tests/<subdir>/` 变成 `tests/<a>/<b>/` 的"加一层"操作，会让这 30 个文件全���指向错误路径**（`tests/a/b/f.py` 的 `parents[2]` = `tests/`，不是仓库根）。

30 个文件清单（括号内为其拼出的目标）：

```
tests/a11y_login_x18/test_authed_field.py                    → <root>/web/tests/visual
tests/a11y_violation_x2/test_no_real_violation.py            → <root>/web/src        (归档)
tests/alembic/test_pre_commit_hook_passes.py                 → <root>/scripts/alembic/check_single_head.sh
tests/axe_violation_x19/test_axe_x19_no_real_violation.py     → <root>/web/src/assets/variables.css (归档)
tests/baseline_sync_x29/test_sync.py                          → <root>/web/tests/visual
tests/brief_v41_x6/test_doc_exists.py                        → <root>/docs/dispatch-template-v4.1.md + CLAUDE.md (归档)
tests/ci_real_x29/test_deployment.py                         → <root>/web + <root>/.github/workflows (归档)
tests/dist_health/test_no_orphan_chunks.py                   → <root>/web/dist
tests/e2e/test_anchor_scripts_smoke.py                       → sys.path.insert(<root>)
tests/icon_wr1/test_play_to_video.py                         → <root>/web (归档)
tests/inject_auth_x4/test_fail_loud.py                        → <root>/web/node_modules/.bin (归档)
tests/k6/test_scripts_exist.py                               → <root>/scripts/k6 + web/package.json
tests/npm_audit/test_known_vulnerabilities.py                → <root>/web
tests/pg_exporter/test_compose_service_defined.py            → <root>/docker-compose.{yml,dev,test}
tests/pg_exporter/test_slow_query_script.py                 → <root>/scripts/pg-exporter/slow-query-helper.sh
tests/playwright_ci/test_workflow_valid.py                    → <root>/.github/workflows/playwright.yml
tests/precommit/test_config_valid.py                         → <root>/.pre-commit-config.yaml
tests/precommit/test_hooks_executable.py                     → <root>
tests/rag/test_pr10_docs_e2e.py                              → <root>/docs/rag
tests/rag/test_pr3_e2e.py                                    → <root>/alembic/versions/089_gin_trgm_tsvector.py
tests/rag/test_pr7_e2e.py                                    → sys.path.insert(<root>)
tests/rag/test_rag_bugfix_w100_e2e.py                        → sys.path.insert(<root>)
tests/rag/test_w_n_obs_chunk_late_recall.py                  → sys.path.insert(<root>)
tests/sentry/test_config_off_by_default.py                   → <root>
tests/sentry/test_glitchtip_dockerfile_pinning.py            → <root> + base commit 1a3ebbea5
tests/sentry/test_main_js_conditional.py                     → <root>/web/src/main.js
tests/src_tests_x5/test_naming.py                            → <root>/web/src/__tests__
tests/test_drive_v2_pr7_file_request_e2e.py                  → <root>（注释：worktree 根 = parents[2]）
tests/trivy/test_dockerfile_pinning.py                       → <root>/Dockerfile* 列表
tests/trivy/test_workflow_exists.py                          → <root>/.github/workflows/image-scan.yml
```

**安全改法**：若要给 9 个 `_xNN` 目录加一层（如 `tests/a11y/`），必须
① 同步改这批文件的 `parents[2]`→`parents[3]`（仅限被移动的），
② 确认目标目录补 `__init__.py`（沿用现有 18 个的约定），
③ 移动后**必跑** `server-tests-baseline.yml` 本地等价命令验证分片仍全绿。

### B5. `tests/qa-bench/` 13M 是什么

- **不是 submodule**：仓库无 `.gitmodules`（实测 `cat .gitmodules` → No such file），`git submodule status` 无输出。**是普通 git 跟踪目录**。
- 构成（126 文件）：`results/`×32、`scoring/`×11、`sensevoice/`×6、`kb_queue/`×6、`mocks/`×5、`detectors/`×5、`data/`×4、`r10_replay_2026_07_28/`×3、`dashboard/`×3、`baselines/`×2、余 6 散装。
- 含 `requirements.txt`（`qa-bench-baseline.yml:44` 作 `cache-dependency-path`）+ `questions_fast_vs_deep.jsonl`（`qa-bench-smoke.yml:425`）。
- 有自己的 `conftest.py`、5 个 `__init__.py`。
- **CI 依赖最重**：`qa-bench-smoke.yml` 5 处 `working-directory: tests/qa-bench`。

---

## C. scripts/ 现状

### C1. 全部脚本清单

**规模**：247 文件 = 顶层 201 + 子目录 46。
扩展名分布：`py`×145、`sh`×53、`ps1`×21、`md`×7、`bat`×7、`sql`×5、`js`×3、`service`×2、`vbs`×1、`txt`×1、`token-orphan-allowlist`×1、`template`×1。

#### C1.1 顶层 130 个 `.py`

**① 数据回填 / 修复类（一次性或可重跑，~30 个）**
```
backfill_drive_comments_path.py      backfill_drive_content.py        backfill_drive_file_hash.py
backfill_drive_search_text.py        backfill_drive_to_kb.py          backfill_image_embeddings.py
backfill_kb_chunks.py                backfill_kb_search_text.py       backfill_kg_entities.py
backfill_late_embedding.py           backfill_meeting_index.py        backfill_resync_kb_indexes.py
migrate_kb_dedup_titles.py           migrate_kb_source_type.py        migrate_kb_tags.py
migrate_preview_cache_key.py         migrate_projects_cleanup.py      migrate-weights-v3-to-v4.py
rechunk_page_marker_docs.py          recompute_embeddings.py           reindex_all.py
reindex_monitor.py                   regen_meeting_summary.py          regen_meeting_titles.py
repair_knowledge_*.sql (见 C1.4)     resync / purge 系列（下）
```

**② 清理 / 净化类（~15 个）**
```
auto_intake_rollback.py    cleanup_benchmark_chat_data.py    cleanup_kb_duplicates.py
cleanup_orphan_meeting_audio.py    cleanup_voiceprint_embeddings_2026-09-07.py
dedup_kb_duplicates.py      kb_dedup_admin_cli.py            purify_voiceprints.py
purify_voiceprints_from_meeting.py  purge_banner_image_block_extractions.py
purge_banner_image_noise.py purge_test_user_data.py          repair_knowledge_backslashes.py
repair_knowledge_newlines.sql       repair_knowledge_round2.sql   sanitize_fixture.py
```

**③ 会议 / 语音处理类（~15 个）**
```
batch_repair_meetings.py   cleanup_orphan_meeting_audio.py   mark_voice_confirmed.py
measure_gpu_asr_rtf.py     prepare_asr_finetune_data.py     prepare_asr_finetune_data_db.py
recover_meeting_audio.py   regenerate_meeting* (见上)        replay_meeting.py
reprocess_meeting.py       reprocess_via_service.py         rollback_voiceprint.py
scan_meetings_with_historical_misid.py  verify_voiceprint_voting_v2.py
prepare_eval_audio.py      incremental_anchor.py           list_anchors.py
```

**④ RAG / bench / 评测类（~25 个）**
```
a43_pptx_page_analyse.py        a43_pptx_page_pipeline.py      a43_pptx_page_recon.py
a44_find_probe_terms.py         a44_ingest_page_transcripts.py a44_page_transcript_dryrun.py
a44_verify_e2e_semantic.py      a44_verify_probe_rank.py       a44_verify_retrieval.py
a44_verify_semantic.py          a45_verify_lexical_probe.py    a46_ingest_page_transcripts.py
a46_pptx_page_pipeline.py       a46_verify_e2e.py              a47_pptx_page_pipeline_band.py
analyze_rerank_topk_change.py   bench_cold_hot_routing.py      bench_e2e_late_chunking_recall.py
bench_hnsw_params.py            bench_late_chunking.py         benchmark_fast_vs_deep.py
build_eval_ground_truth.py      build_eval_set.py              build_finetune_pairs.py
build_rag_eval_set.py           check_pgvector_version.py      consistency_filter_v2.py
eval_recall.py                  lock_baseline.py               reembed_knowledge_bge_m3.py
run_bge_m3_realbench.py         run_late_chunking_realbench.py  run_llm_judge.py
run_rag_eval.py                 verify_chunk_late_recall.py    verify_learn_cycle.py
```

> ⚠️ `a43_*` / `a44_*` / `a45_*` / `a46_*` / `a47_*` 共 **15 个** 是 agent 会话编号前缀的一次性脚本 —— 与 tests/ 的 `_xNN` 是**同类命名债**，建议一并归入 `scripts/_archive/aXX-*/`。

**⑤ 微调 / 模型训练类（4 个）**
```
lora_finetune_embedding.py    build_finetune_pairs.py(见上)   convert_finetune_to_official.py
```

**⑥ 备份 / 恢复 / ���维类（~12 个）**
```
backup_minio_daily.py         backup_to_aliyun_oss.py        restore_from_backup.py
restore_from_oss.py           ensure_test_user.py            init_db.py
init_test_db_all.py           purge_test_user_data.py        verify_login_redis.py
verify_redis_rate_limiter.py  check_env_backend.py           update-stats.py
check-kb-deleted-at-filter.py generate_recovery_codes.py
```

**⑦ 报告生成 / 商业化 / 其它（~25 个）**
```
audit_broken_image_refs.py    audit_team_members.py          cloud_smoke_test.py
commercial_7d_monitor.py      commercial_operation_monitor.py export_avatars_zip.py
export_meeting_minutes.py     fix_broken_image_refs.py       fix_minio_mime.py
gen_advanced_report.py        gen_dim_report.py              gen_final_report.py
generate-changelog.py         generate_token_plan_doc.py     live_e2e_write_honesty.py
private_deployment_*.sh(见C1.4)  reassign_member_rows.py        rerun_failed_ocr.py
rerun_single_image_ocr.py     stability_check.py             test_chat_history_e2e.py
test_sidebar_remote.py        test_stream_persistence_e2e.py test_team_filter.py
upload_avatars_v2.py          webhook.py                     clean_project_descriptions.py
```

#### C1.2 顶层 68 个非 `.py` 脚本

**部署（7）**：`auto-deploy.sh` `deploy.sh` `deploy-auto.sh` `deploy-cloud.sh` `deploy-local.sh` `push-main.sh` `install-frps-systemd.sh`

**计划任务安装器（9）**：`install-auto-recovery.bat` `install-backup-scheduler.ps1` `install-local-ops.bat` `register-gpu-asr-daemon-task.ps1` `_register-task.ps1` `register_avatar_defenses.ps1` `local-backup.ps1` `local-build-verify.ps1` `local-watchdog.ps1`

**计划任务运行时（3，🔴 活）**：`auto-recovery-eventlog.ps1` `backup_scheduler.bat` `start_gpu_asr_daemon.bat` `run-hidden.vbs`

**备份/恢复（4）**：`backup_db.sh` `cron_sync_sequences.sh` `sync_sequences.sh` `restore_full_backup.sh` `dump_prod_to_fixture.sh`

**CI / pre-commit 门禁（8，🟡 高危）**：`check-design-tokens-drift.sh` `check-token-orphans.sh` `check-dist-before-commit.sh` `check-secrets-before-commit.sh` `check_observability_coverage.sh` `check_typing_imports.sh` `frontend-size-budget-check.sh` `frontend-size-budget.txt` `setup-hooks.sh` `sync-design-tokens.sh`

**监控（6）**：`monitor-9-table-index.sh` `monitor-alembic-heads.sh` `monitor-nginx-mime.sh` `monitor-pwa-manifest.sh` `monitor-sw-cache.sh` `monitor-tenant-isolation.sh`

**校验（7）**：`ci_qa_bench_baseline.sh` `verify_alembic_chain.sh` `verify_backup_restore.sh` `verify_dispatch_claim.sh` `verify_pr4_5_suite.sh` `verify_realenv_e2e.sh` `restart-recovery-after-gui-restart.sh`

**SQL（5）**：`alter_agent_traces_stage3.sql` `orphan_chunk_audit.sql` `repair_knowledge_backslashes.sql` `repair_knowledge_newlines.sql` `repair_knowledge_round2.sql`

**通知/服务（4）**：`voice-alert.ps1` `run-with-alert.ps1` `run-reprocess.ps1` `recreate-celery.ps1` `claude-code-notify-setup.sh` `start_ollama.ps1` `stop_ollama.ps1` `setup-ssl.ps1` `install-gitleaks.md` `install-k6.md` `install-pg-exporter.md` `install-trivy.md` `install-pre-commit.md`

#### C1.3 15 个子目录

| 子目录 | 文件数 | 内容 | 建议归类 |
|---|---|---|---|
| `scripts/qa-bench/` | 7 | `ci_secret_check.py` `endpoint_lock.py` `gate.py` `reranker_eval.py` `sanitize_fixture.py` `stress_tenant_isolation.py` `stress_tenant_perf.py` | 保持（CI 有引用） |
| `scripts/notify-templates/` | 7 | 6 个 `claude-voice-alert-*.ps1` + `settings.json.template` | `ops/notify/` |
| `scripts/rag/` | 6 | `check_anchor_paradigm.sh` `check_pgvector_hnsw.sh` `check_production_code_diff.sh` `check_recall_three_ways.sh` `verify_alembic_chain.sh` `verify_dispatch_claim.sh` | `rag/` 或 `checks/` |
| `scripts/k6/` | 5 | `chat_stream.js` `drive_collab.js` `ws_notifications.js` + 2 README | `bench/`（⚠️ `web/package.json` 3 条 `../scripts/k6/` 依赖） |
| `scripts/_archive/` | 5 | `2026-07-28-w83-p2-cleanup/verify_v31_2_{1_nested_path,1_xff_empty,2,2,3,5_restart}.py` | 保持归档 |
| `scripts/tunnel/` | 4 | `guard-ssh-tunnel.ps1/.bat` `install-tunnel-guard.bat` `uninstall-tunnel-guard.bat` | `ops/tunnel/`（⚠️ 计划任务依赖 + 跨引 `tunnel/`） |
| `scripts/trivy/` | 3 | `check_pinned_images.py` `scan-all.sh` `scan-images.sh` | `security/`（⚠️ pre-commit 引用） |
| `scripts/pg-exporter/` | 3 | `health.sh` `scrape.sh` `slow-query-helper.sh` | `ops/monitoring/`（⚠️ `tests/pg_exporter/` 引用） |
| `scripts/voiceprint/` | 2 | `replay_meeting_151.py` `reprocess_12_meetings.py` | `voiceprint/` |
| `scripts/web/` | 1 | `check_dist_manifest.sh` | `web/`（⚠️ pre-commit 引用） |
| `scripts/lib/` | 1 | `webhook_payload.sh` | `lib/`（保持） |
| `scripts/gitleaks/` | 1 | `scan-history.sh` | `security/`（⚠️ pre-commit 引用） |
| `scripts/alembic/` | 1 | `check_single_head.sh` | `checks/`（⚠️ pre-commit + `tests/alembic/` 引用） |

#### C1.4 `_archive/` 的 CHANGELOG 引用（审计疑虑澄清）

**实测：5 个 `verify_v31_*.py` 在代码/CI 中零引用**，仅被 `docs/CHANGELOG-history-2026-07-23.md` 第 1887/1915/1925/1936 行以**纯文本**提及（历史变更日志记录当时做了什么）。
→ **不是活引用**，改路径不会炸任何东西。但 CHANGELOG 是历史文档，**建议保持原样不动**（历史记录不该被重构改写）。归位到 `scripts/_archive/` 保持原位即可，无需迁出。

### C2. 被引用脚本的高危表

| 脚本 | 引用位置 | 类型 | 影响 |
|---|---|---|---|
| `scripts/auto-recovery-eventlog.ps1` | **计划任务 `MicroBubble-Auto-Recovery`** `powershell.exe -File "E:\...\scripts\auto-recovery-eventlog.ps1"` | 🔴 绝对路径 | **改名 = 自愈任务永久死亡且 `LastTaskResult` 仍报 0**（类 20.220 陷阱） |
| `scripts/backup_scheduler.bat` | **计划任务 `MicroBubble-Daily-Backup`** `Command = E:\microbubble-agent\scripts\backup_scheduler.bat` | 🔴 绝对路径 | 同上 |
| `scripts/start_gpu_asr_daemon.bat` | **计划任务 `MicroBubble-GPU-ASR-Daemon`** `Command` + `WorkingDirectory = E:\microbubble-agent` | 🔴 绝对路径 | 同上 |
| `scripts/run-hidden.vbs` → `scripts/tunnel/guard-ssh-tunnel.ps1` | **计划任务 `MicroBubble-SSH-Tunnel-Guard`** `wscript.exe "E:\...\scripts\run-hidden.vbs" "E:\...\scripts\tunnel\guard-ssh-tunnel.ps1"` | 🔴 绝对路径 ×2 | 同上；且���道断 = 全站不可用（类 20.214） |
| `scripts/backup_db.sh` | `backup_scheduler.bat:44` 绝对路径调用 | 🔴 传递 | 同上 |
| `scripts/backup_scheduler.bat` | `install-backup-scheduler.ps1` | 🟡 | 安装器 |
| `scripts/start_gpu_asr_daemon.bat` | `register-gpu-asr-daemon-task.ps1` | 🟡 | 安装器 |
| `scripts/auto-recovery-eventlog.ps1` | `scripts/_register-task.ps1` `scripts/install-auto-recovery.bat` | 🟡 | 安装器 |
| `scripts/init_test_db_all.py` | `build-image.yml` / `playwright.yml` / **`docker-compose.test.yml:79`** | 🔴 3 处 | **CI + compose 双依赖** |
| `scripts/init_db.py` | `playwright.yml` / `qa-bench-smoke.yml` | 🔴 2 workflow | CI |
| `scripts/ensure_test_user.py` | `playwright.yml` / `qa-bench-smoke.yml` | 🔴 2 workflow | CI |
| `scripts/benchmark_fast_vs_deep.py` | `qa-bench-smoke.yml` | 🔴 | CI |
| `scripts/ci_qa_bench_baseline.sh` | `qa-bench-baseline.yml` | 🔴 | CI |
| `scripts/check-design-tokens-drift.sh` | `lint-css.yml` | 🔴 | CI |
| `scripts/check-token-orphans.sh` | `lint-css.yml` | 🔴 | CI |
| `scripts/frontend-size-budget-check.sh` + `.txt` | `lint-css.yml` | 🔴 | CI |
| `scripts/sync-design-tokens.sh` | `lint-css.yml` | 🔴 | CI |
| `scripts/setup-hooks.sh` | `.pre-commit-config.yaml:5,13` | 🔴 | **所有开发者本地 commit 阻断** |
| `scripts/gitleaks/scan-history.sh` | `.pre-commit-config.yaml:34,36` | 🔴 | 同上 |
| `scripts/check-secrets-before-commit.sh` | `.pre-commit-config.yaml:36` | 🔴 | 同上 |
| `scripts/trivy/check_pinned_images.py` | `.pre-commit-config.yaml:50` | 🔴 | 同上 |
| `scripts/alembic/check_single_head.sh` | `.pre-commit-config.yaml:63` **+ `tests/alembic/test_pre_commit_hook_passes.py`** | 🔴 | CI + 测试双依赖 |
| `scripts/check_typing_imports.sh` | `.pre-commit-config.yaml:72,76` | 🔴 | 同上（CLAUDE.md 铁律 2） |
| `scripts/web/check_dist_manifest.sh` | `.pre-commit-config.yaml:89` | 🔴 | 同上 |
| `scripts/k6/{chat_stream,ws_notifications,drive_collab}.js` | **`web/package.json` 3 条 `load:*` scripts** | 🔴 | 跨顶层目录边界 |
| `scripts/pg-exporter/slow-query-helper.sh` | `tests/pg_exporter/test_slow_query_script.py` | 🟡 | 测试 |
| `scripts/backup_minio_daily.py` | `scripts/register_avatar_defenses.ps1` | 🟡 | ps1 |
| `scripts/check_orphan_avatars.py` | `scripts/register_avatar_defenses.ps1` | ⚠️ **目标文件不存在** | **既存坏引用**（见 E3） |
| `apps/desktop/scripts/release.mjs` | `desktop-release.yml`(wd=`apps/desktop`) | 🟡 | **非 `scripts/` 顶层** —— 重构须排除 `apps/desktop/scripts/` |
| `apps/desktop/scripts/upload-release-oss.mjs` + `download-page.html` | `desktop-release.yml` / `upload-download-page.yml`(wd=`apps/desktop`) | 🟡 | 同上 |

---

## D. 高危引用清单 ★最重要

### D1. Windows 计划任务（4 个活任务，全部硬编码绝对路径）

| 任务名 | 触发 | Execute | Arguments | WorkingDirectory |
|---|---|---|---|---|
| `MicroBubble-Auto-Recovery` | 事件/启动 | `powershell.exe` | `-NoProfile -ExecutionPolicy Bypass -File "E:\microbubble-agent\scripts\auto-recovery-eventlog.ps1"` | （默认） |
| `MicroBubble-Daily-Backup` | 每日 02:00 | `E:\microbubble-agent\scripts\backup_scheduler.bat` | — | （默认） |
| `MicroBubble-GPU-ASR-Daemon` | 启动 | `E:\microbubble-agent\scripts\start_gpu_asr_daemon.bat` | — | `E:\microbubble-agent` |
| `MicroBubble-SSH-Tunnel-Guard` | 每 5 分钟 | `wscript.exe` | `"E:\microbubble-agent\scripts\run-hidden.vbs" "E:\microbubble-agent\scripts\tunnel\guard-ssh-tunnel.ps1"` | （默认） |
| ~~`MicroBubble-DFT-Cleanup`~~ | — | `E:\dft-service\run-cleanup.bat` | — | **外部项目，与本仓无关**（CLAUDE.md 明令不许删） |

**改动影响**：脚本改名/移位 → 4 个任务的进程**从未启动**，但 `LastTaskResult` 仍可能报 0（类 20.220 已实证此陷阱）。
**安全改法**：���何 `scripts/` 结构变更后，**必须用 `schtasks /query /tn <name> /xml` 回读 Execute/Arguments 比对**，并手动触发一次 + **验证副作用产物**（日志文件是否生成），不能只看返回码。

### D2. docker-compose volume mount（8 个硬编码相对路径）

| compose 行 | 挂载 | 影响 |
|---|---|---|
| `docker-compose.yml:10-12` | `./nginx/nginx.conf` `./nginx/conf.d` `./nginx/ssl` → nginx | 🔴 nginx 起不来 = 全站白屏 |
| `docker-compose.yml:13` | `./web/dist` → `/usr/share/nginx/html` | 🔴 dist 路径变 = 前端 404 |
| `docker-compose.yml:35,294,360` | `./app:/app/app` ×3 服务 | 🔴 app/celery/beat 全挂 |
| `docker-compose.yml:36,295,361` | `./data:/app/data` ×3 | 🔴 |
| `docker-compose.yml:37,296,362` | `./logs:/app/logs` ×3 | 🔴 |
| `docker-compose.yml:38-41` | `./models/{hf_cache,torch_hub,modelscope}` ×3 | 🟡 |
| `docker-compose.yml:42,301,366` | `./alembic/versions:/app/alembic/versions` ×3 | 🔴 迁移链断 |
| `docker-compose.yml:101-102` | `./data/postgres` | 🔴 **生产数据** |
| `docker-compose.yml:119-120` | `./data/redis` | 🔴 |
| `docker-compose.yml:136-138` | `./data/neo4j/{data,logs}` | 🔴 |
| `docker-compose.yml:219-220` | `./data/ollama`（**61.6G，CLAUDE.md 明令勿删**） | 🔴 |
| `docker-compose.yml:260-263` | `./models` `./app/sensevoice_server.py` | 🟡 |
| `docker-compose.yml:264` | `./funasr_entrypoint.sh` → `/app/entrypoint.sh` | 🔴 |
| `docker-compose.yml:267` | `./app/sensevoice_server.py` | 🟡 |
| `docker-compose.yml:395-405` | beat 服务 `./app` `./data` `./logs` `./models/*` `./alembic/versions` | 🔴 |

**安全改法**：`app/` `data/` `alembic/` `nginx/` `web/dist/` `funasr_entrypoint.sh` **一律不要动**。改后跑 `docker compose config` 校验 + `docker inspect -f '{{range .Mounts}}{{.Source}} -> {{.Destination}}{{"\n"}}{{end}}'` 逐容器回读（类 20.215 纪律）。

### D3. Dockerfile COPY

| 文件 | COPY 指令 | 影响 |
|---|---|---|
| `Dockerfile:59,70` | `COPY requirements.txt .` / `COPY . .` | ✅ **全仓拷贝，路径无关** —— 但受 `.dockerignore` 影响 |
| `Dockerfile.mcp:22-25` | `COPY mcp_server/` `COPY app/config.py` `COPY app/services/vision_service.py` `COPY app/core/llm.py` | 🔴 精确路径 |
| `docker/Dockerfile.commercial:71-74` | `COPY commercial/` `COPY app/` `COPY alembic/` `COPY alembic.ini` | 🔴 精确路径 |
| `docker/visual-regression/Dockerfile` | 视觉回归栈 | 🟡 |

**好消息**：`COPY . .` 意味着**新增/删除目录不影响主镜像构建**；只有显式 `COPY <path>` 的 4 处需注意。

### D4. CI workflow 显式路径（11 个 workflow）

| workflow | 显式路径 | 影响 |
|---|---|---|
| `server-tests-baseline.yml` | `tests/**`（触发）、`find tests`（分片） | ✅ **路径无关** |
| `rag-framework-ci.yml:120` | `pytest tests/rag_framework/` | 🔴 |
| `playwright.yml:344,352,681` | `tests/visual/a11y/playwright.a11y.config.mjs`、`tests/visual/playwright.visual.config.mjs` | 🔴 |
| `playwright.yml:25,56` | `web/tests/**`（触发） | 🔴 |
| `lint-css.yml:12,40` | `web/tests/**`（触发） | 🔴 |
| `qa-bench-smoke.yml` | 5× `working-directory: tests/qa-bench`、`:21,29` 触发 `tests/qa-bench/**`、`:425` `tests/qa-bench/questions_fast_vs_deep.jsonl`、`:405` artifact `tests/qa-bench/results/smoke/` | 🔴 **最密集** |
| `qa-bench-baseline.yml:44,50,118` | `tests/qa-bench/requirements.txt`、`ARCHIVED_AUDIT=tests/test_baseline_audit.py` | 🔴 |
| `build-image.yml` | `scripts/init_test_db_all.py` | 🔴 |
| `desktop-release.yml` | `working-directory: apps/desktop`（5 处）、`apps/desktop/release/*` artifact | 🔴 |
| `upload-download-page.yml` | `working-directory: apps/desktop` | 🔴 |
| `image-scan.yml` / `secret-scan.yml` / `rag-framework-ci.yml` | 扫描全仓，路径无关 | 🟢 |

### D5. 前端 package 配置

| 位置 | 引用 | 影响 |
|---|---|---|
| `pnpm-workspace.yaml` | `['apps/*', 'packages/*']` | 🔴 改 `apps/`/`packages/` 目录名会破 workspace |
| `web/package.json` `load:chat/ws/drive` | **`../scripts/k6/*.js`** | 🔴 **跨顶层目录耦合** —— `scripts/k6/` 不能改名/上移 |
| `web/package.json` `build` | `node scripts/postbuild-fix-manifest.js` | 🟡 `web/scripts/` 相对路径 |
| `web/package.json` `test:playwright:a11y` | `-c tests/visual/a11y/playwright.a11y.config.mjs` | 🔴 `web/tests/visual/` |
| 根 `package.json` | `pnpm --filter @mb/desktop` | 🔴 |

### D6. 文档中的绝对路径（`E:/microbubble-agent`）

分布（**不含 `web/dist` / `node_modules`**）：
`memory/`×69、`docs/archived/w72-w85-batch-closure/`×20、`scripts/`×17、`docs/archived/2026-09-30-root-snapshots/`×9、`docs/`×9、`memory/archived/w68-batch-detail/`×8、`scripts/tunnel/`×3、`tunnel/`×2、`tests/qa-bench/`×2、`app/gpu_worker/`×3、`docs/rag/`×3 … 合计 **约 150 处 / 30+ 目录**。

代码与配置中的**功能性**绝对路径（39 处，已逐条列出）关键者：
```
app/gpu_worker/{server,meeting_worker,streaming_server}.py  → E:\microbubble-agent\data\vibevoice-test   (3 处 VIBEVOICE_HOME 默认值)
scripts/auto-recovery-eventlog.ps1        → E:\microbubble-agent\scripts
scripts/backup_scheduler.bat              → E:\microbubble-agent\scripts\backup_db.sh + logs\backup
scripts/backup_minio_daily.py             → E:\microbubble-agent\{.env, .env.webhook, backups\minio-daily}
scripts/tunnel/guard-ssh-tunnel.ps1       → E:\microbubble-agent\logs\tunnel-guard{,-ssh.err}.log
scripts/tunnel/guard-ssh-tunnel.bat       → E:\microbubble-agent\scripts\tunnel\guard-ssh-tunnel.ps1
scripts/tunnel/install-tunnel-guard.bat   → E:\microbubble-agent\scripts\tunnel\guard-ssh-tunnel.bat
scripts/register_avatar_defenses.ps1      → E:\microbubble-agent\scripts\{backup_minio_daily.py, check_orphan_avatars.py}
scripts/install-*.{ps1,bat}               → 各自 scripts 文件
scripts/cron_sync_sequences.sh            → E:/microbubble-agent/scripts/cron_sync_sequences.sh
scripts/upload_avatars_v2.py / export_avatars_zip.py / cleanup_voiceprint_embeddings_*.py → E:\microbubble-agent\backups\*
restart_gpu_workers.bat                   → E:\microbubble-agent\{.workbuddy\vibevoice-test (旧路径), logs\*}  ⚠️ 旧 VIBEVOICE_HOME
tunnel/start-ssh-tunnel.vbs               → E:\microbubble-agent\tunnel\start-ssh-tunnel.ps1
scripts/notify-templates/claude-voice-alert-stop.ps1 → E:\microbubble-agent\scripts\notify-templates\...
tests/test_meeting_batch_e4_e2e.py        → E:/microbubble-agent/app/services/meeting_reprocessing_service.py
tests/ARCHIVED.md + tests/test_no_prod_db_imports.py（守门类，不可归档）
docs/design-proposals/cohort-subgroup-2026-09/_shoot.js → E:/microbubble-agent/docs/design-proposals/...
```

**影响**：仓库根一旦搬家（如迁到别的盘符/路径），**全部 39 处功能性路径 + 4 个计划任务**会同时失效。文档里约 150 处为历史记录，**建议不改**（历史文档不改写）。

### D7. pytest / conftest

| 位置 | 内容 | 影响 |
|---|---|---|
| `pytest.ini` | `testpaths = tests` | 🔴 `tests/` 目录名不可改（改则 pytest 收集不到） |
| `pytest.ini` | `asyncio_mode = auto` 等 | 🔴 |
| `tests/conftest.py` | 452 行，**唯一根 conftest**；实测**不含** `__file__`/`parents`/`chdir` 路径逻辑（grep 无命中） | 🟡 相对安全 |
| `tests/*/conftest.py` ×5 | `perf` `qa-bench` `rag` `rag_framework` `realenv` | 🟡 子目录可移动，conftest 随之 |
| **18 个 `__init__.py`** | 消解同名 basename 冲突 | 🔴 **移动目录时必须维持 `__init__.py` 覆盖** |

---

## E. 重构约束（铁律 / CI / 硬编码）

### E1. 会阻止或高危的 CLAUDE.md 铁律

| 铁律 | 对重构的约束 |
|---|---|
| **类 20.133**（Vite 构建确定性） | `web/dist` **入库**。改 `web/` 目录结构会改 `BUILD_ID`/`BUILD_TIMESTAMP`（= 源输入清单 sha256）→ 需按"**先提交源码 → 再 build → 再提 dist**"的原子顺序，否则 dist 不可复现 |
| **类 20.215**（compose 注释实验必须逐字段圈界） | 改任何 compose 后必须跑 `docker compose config` + `docker inspect -f '{{.HostConfig.RestartPolicy.Name}}'` 抽验 |
| **类 20.216**（schtasks 反斜杠路径转义坑） | 注册计划任务的脚本路径含反斜杠时被吞成控制字符。**改路径后必须回读 `Get-ScheduledTask \| % Actions[0].Execute` 比对长度 + 无控制字符** |
| **类 20.217**（nginx healthcheck 用 `127.0.0.1`） | `nginx/` 不可动 |
| **类 20.219**（celery task 必须进 `celery_app.conf.imports`） | 约束**代码**不约束目录，但若移动 `app/services/` 需同步改 imports |
| **类 20.220**（自动化守门必须验副作用，不能信状态字段） | **本次 4 个计划任务全部适用** —— 改完后不能只看 `LastTaskResult=0`，必须查日志文件是否生成 |
| **类 20.212**（清理"残留"前必须查是否被生产引用） | `desktop-conversion/`、`observability/`、`commercial/`、`config/` 看似残留实则各有所属 —— **不得按"名字+年龄"判残留** |
| **类 20.221**（DB 存 UTC 主机 +0800） | 与结构重构无关，但 `results/` 归档若含时间戳需注意 |
| **CLAUDE.md "0 production code 改动铁律"** | `app/` `alembic/` `web/src/` 的核心函数受严格保护 |

### E2. 会因目录变化而红的 CI 检查

| 检查 | 触发条件 |
|---|---|
| `server-tests-baseline.yml` | 仅 `tests/` **basename 冲突**会红（见 B3）；目录改名本身安全 |
| `rag-framework-ci.yml` | `tests/rag_framework/` 路径 |
| `playwright.yml` | `tests/visual/` `web/tests/` 路径 |
| `qa-bench-smoke.yml` | `tests/qa-bench/` 路径 + wd |
| `qa-bench-baseline.yml` | `tests/qa-bench/requirements.txt` + `tests/test_baseline_audit.py` |
| `lint-css.yml` | `web/tests/**` 触发 + 4 个 `scripts/*.sh` |
| `desktop-release.yml` | `apps/desktop/` wd |
| `build-image.yml` | `scripts/init_test_db_all.py` |
| **pre-commit（本地，非 CI）** | 10 个 `scripts/` 路径 —— **改错会阻断所有开发者 commit** |
| **`tests/test_no_prod_db_imports.py`** | **守门类，禁止归档**（`tests/ARCHIVED.md:25`） |

### E3. 硬编码路径扫描的意外发现

| 发现 | 详情 | 影响 |
|---|---|---|
| ⚠️ **既有坏引用** | `scripts/register_avatar_defenses.ps1` 引用 `E:\microbubble-agent\scripts\check_orphan_avatars.py`，但该文件**在 git 中不存在**（`git ls-files` 0 命中，磁盘也无） | 这条 `.ps1` 当前**必然失败**。重构时应顺带确认是否删除该行（**本次未改，仅报告**） |
| ⚠️ **过时绝对路径** | `restart_gpu_workers.bat` 仍指向 `E:\microbubble-agent\.workbuddy\vibevoice-test\venv-gpu\...` —— CLAUDE.md 记载 2026-09-30 已迁至 `data\vibevoice-test` | 建议重构时同步修正（**本次未改**） |
| ⚠️ **孤儿目录** | `config/intent_routing.yaml` **零引用**；`observability/` compose 无引用 | 需主指挥确认是死配置还是遗漏接线 |
| ⚠️ **重复 CI 脚本路径陷阱** | `desktop-release.yml` 里的 `scripts/release.mjs` / `upload-release-oss.mjs` 看似指 `scripts/`，实为 `working-directory: apps/desktop` 下的 `apps/desktop/scripts/` | 批量脚本若按字符串 `scripts/` 匹配会**误伤 `apps/desktop/scripts/`** |
| ⚠️ **`tunnel/` 双目录** | 顶层 `tunnel/`（建隧道）与 `scripts/tunnel/`（守护隧道）互补且交叉引用 | 合并需同步改 2 处交叉引用 + 1 个计划任务 |
| ⚠️ **`desktop-conversion/` 不可见** | 不在主仓 `git ls-files`，`git ls-files` 驱动的脚本会静默跳过 | 重构必须**显式排除并单独处理** |

---

## F. 建议的重构分批顺序

> 每批独立可验证、可回滚。**先零风险，后高风险。**

### 批次 0（零风险，纯取证/准备）
- **内容**：补 `docs/structure-map.md` 索引、`scripts/_archive/aXX-*/` 整理（15 个 `a4X_*` 会话编号脚本）、确认 `config/` 与 `observability/` 的生死。
- **验证**：`git status` 干净 + 跑一次 `server-tests-baseline.yml` 本地等价分片命令确认基线绿灯。

### 批次 1（低风险：tests/ 9 个 `_xNN` 归位 ★用户已知任务）
- **内容**：9 目录 → `tests/a11y/`（4 个 a11y/axe/inject_auth 守卫）、`tests/realenv/`（+1 ci_real）、`tests/dist_health/`（+1 icon_wr）、`tests/docs_contract/`（+1 brief_v41）、`tests/web_conventions/`（+1 src_tests_x5）。
- **必须同步**：
  1. 被移动文件的 `parents[2]` → `parents[3]`（3 个活文件 + 归档文件若保留）；
  2. 新目录补 `__init__.py`（沿用现有 18 个约定）；
  3. **确认无 basename 冲突**（尤其 `test_no_real_violation.py` —— 已有前科）。
- **验证**：`python -m pytest tests/a11y tests/dist_health tests/web_conventions tests/realenv -q` + 复跑 8 片分片命令。

### 批次 2（中风险：scripts/ 分类，**只移动不重命名顶层文件**）
- **内容**：新建 `scripts/{ops,checks,bench,security,migrations,reports,_archive}/`，把**子目录内容**与**��外部引用的顶层脚本**迁入。
- **红线**：
  - **4 个计划任务引用的 6 个文件原地不动**（`auto-recovery-eventlog.ps1` `backup_scheduler.bat` `backup_db.sh` `start_gpu_asr_daemon.bat` `run-hidden.vbs` `tunnel/guard-ssh-tunnel.ps1`）；
  - **19 个 CI/pre-commit 引用脚本原地不动**；
  - 顶层 130 个 `.py` 建议**先只加索引文档，不搬**（零引用与否需逐一 grep 确认）。
- **验证**：改后逐个 `grep -rn "<旧路径>" .github/ .pre-commit-config.yaml docker-compose*.yml web/package.json` 应 0 命中；`schtasks /query /tn <名> /xml` 回读 4 个任务 Execute/Arguments 逐字节比对。

### 批次 3（中风险：tunnel 合并 + 孤儿归位）
- **内容**：`tunnel/` + `scripts/tunnel/` → 统一到一处；`config/` `observability/` `commercial/` 归位（需主指挥拍板）。
- **验证**：`MicroBubble-SSH-Tunnel-Guard` 手动触发 + **查 `logs/tunnel-guard.log` 是否新增行**（类 20.220）。

### 批次 4（高风险：仅在必要时）
- `web/` `apps/` `packages/` 结构调整 —— 触发类 20.133 构建确定性纪律，**必须最后做**。
- `desktop-conversion/` —— **不在主仓，需独立 PR 流程 + 文档交叉引用表**。

---

## 附录：本次测绘方法与局限

**方法**：全部为只读命令（`git ls-files` / `grep` / `cat` / `du` / `ls` / `schtasks /query`）。
`schtasks /query /tn <名> /xml` 用于读计划任务 XML；`Get-ScheduledTask` 走 `powershell.exe` 时被沙箱拒绝（Permission denied），
改用 `schtasks.exe` + XML 提取，**已取得等价数据**。

**局限（如实）**：
1. **未执行任何测试**，CI 绿灯结论基于静态代码分析（分片命令 `find tests -name "test_*.py"` 已逐字核对），非实测。
2. `parents[2]` 的 30 文件清单按 grep 提取，**未逐个运行验证**；个别文件可能同时用 `parents[2]` 做非 root 用途（`icon_wr1` 的 docstring 里那处是举例说明，非代码）。
3. 体积为 **git 跟踪字节**，非磁盘占用（磁盘另含 `node_modules` 466M、`web/dist`、`.git`）。
4. **未检查** `web/dist/` 内产物引用（有 `.min.js` 排除）、`logs/` `models/` `backups/` 等 gitignore 目录内的运行时路径。
5. `docs/` 654 文件中的交叉引用**未穷举**，仅统计了含绝对路径的文件数。
6. 未评估 `apps/desktop/` 内部结构（213 文件，仅确认了 workspace 与 CI wd 关系）。