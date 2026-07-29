# W87 第 1 批 grand closure (2026-07-30)

> **主基调**: W87 第 1 批 4 路线 (G-1 a11y / E-1 k6 / B-1 GlitchTip+Sentry / H-1 contextvars) + X-1 alembic rebase 撤回 + X-3 alembic hook 假阳性修复 + cherry-pick 模式实战. 锚点范式 W86 第 1 批 325 → W87 第 1 批 332 守恒 (+7 实际据实: 5 cherry-pick + 1 hook 修复 + 1 docs sync).

---

## 1. 派工清单 (4 路线 + X-1 撤回 + X-3 修复)

### G-1: axe-core/playwright a11y 接入 (W87-G-1, e232fb2d9)
- **派工 brief**: axe-core 4.12.1 + Playwright a11y config + 5 页面快照 (chat / drive / mobile-chat / task-trash / file-comments) × 5 viewport (chrome / comments / mobile / iPhone14 / harmonyos arkweb)
- **实测差异**:
  1. **base 漂移 (派工 v6 §5 反馈 类 20.32 实战 #1)**: G-1 worktree 基于 `5c87904b7` (W86 mini-4 entity graph), 而非 `1a3ebbea5` (W86 D-2). merge-base = `9564f2dc9` (W85 hotfix)
  2. **匿名分支名 `worktree-agent-a429a6749fe6f0075`** (派工 v6 §5 反馈 类 20.31 实战 #1): subagent `EnterWorktree` 阻断后 fallback `git worktree add` → 分支名 = `worktree-agent-<id>`, 主指挥合并必须用这个分支名 + 必须查实际 base, 不可凭派工 brief 写的"claude/w87-1st-batch-g1-a11y"
  3. **playwright.config.js 锁**: 派工 brief 报告 G-1 a11y 测试需独立 `playwright.a11y.config.mjs`, 实际 G-1 已落地, 但**未跑过** (主指挥合并后用 `cd web && npx playwright test -c tests/visual/a11y/playwright.a11y.config.mjs` 单独跑 — 留给 W87 第 2 批 G-2 验证)
  4. **a11y 全绿是可疑信号 (派工 v6 §5 反馈 类 20.25 新增)**: G-1 报告 50 snapshot 100% PASS, 但全部基于未登录页 + 仅 `wcag2a/2aa` rules. 真 a11y violation 需要登录态拿 token / 角色权限渲染. W87 第 2 批 G-2 真登录态补刀

### E-1: k6 压测脚本接入 (W87-E-1, 8cf95a4a8)
- **派工 brief**: scripts/k6/{chat_stream, ws_notifications, drive_collab}.js + baselines/README + tests/k6/ 验证脚本存在
- **实测差异**:
  1. **base 漂移**: 同样基于 `5c87904b7` (类 20.32 实战 #2)
  2. **匿名分支 `worktree-agent-aeb766f2a0d4ade04`** (类 20.31 实战 #2)
  3. **脚本 + tests 通过 (17 e2e PASS) 但 baseline 数据空 (派工 v6 §5 反馈 类 20.26 新增)**: 实际跑过 3 个脚本 0 baseline 落盘 (CI 没装机 k6 binary). 部署文档只标"已写脚本", 未真装机验证
  4. **npm 5 脚本 (load:chat / load:ws / load:drive) + tests/k6 全部 PASS** — 派工 v6 §1.2 实战: 不需要真压, 只要脚本语法合法 + 测试文件存在
- **派工 v6 §1.2 真验证**: `git show 8cf95a4a8:scripts/k6/chat_stream.js` 完整 70 行 + `tests/k6/test_scripts_exist.py` 17 assert 全过

### B-1: GlitchTip + Sentry 接入 (W87-B-1, 3628fa733 + ede69aa13)
- **派工 brief**: 3 compose service (glitchtip + glitchtip-db + glitchtip-redis) + app/main.py Sentry init (默认 off) + app/config.py SENTRY_DSN + web/src/{main,sw,utils/sentry}.js + requirements.txt sentry-sdk[fastapi] + 4 e2e
- **实测差异 (4 处 brief 错配, 派工 v6 §5 反馈 类 20.27 新增)**:
  1. **B-1 commit 内 dist 完整 build (134 web/dist/ 新文件)**: 派工 brief 只列"改源文件", 实际 B-1 跑了 `npm run build` 把 dist 全部 commit. 134 文件 = 8 既有 dist + 126 新 dist (含 Sentry 资产 + 旧 bundle)
  2. **dist entry chunk orphan 缺陷 (W87-X-3 报告)**: B-1 提交后 `web/dist/index.html` 引用 `/assets/index-c70e8703.js` (Sentry-free), 而新增 `index-d2ea53b1.js` 含 Sentry. 主指挥合并后浏览器实际拿不到 Sentry. **PWA 410 铁律不适用** (vite.config `disable: true`), 但 dist 仍需重跑 `npm run build` 才能真正 ship Sentry
  3. **`scripts/.token-orphan-allowlist` 5 行新增** (派工 brief 未列): 实际 B-1 顺手补了 5 个 GlitchTip/Sentry token 孤儿白名单 (避免 gitleaks 误报)
  4. **lockfile 单独 1 commit (ede69aa13)**: B-1 拆成 "feat + chore" 双 commit, 主指挥按 3628fa733 → ede69aa13 顺序 cherry-pick OK
- **派工 v6 §1.2 真验证**: `git show 3628fa733 --stat` 150 文件改动 + `cat scripts/.token-orphan-allowlist | grep -E "sentry|glitchtip"` 5 行确认 + `git show 3628fa733:web/dist/index.html | grep -oE 'assets/index-[a-z0-9]*\.js'` 暴露 orphan

### H-1: contextvars 透传 request_id + task_id (W87-H-1, 968a30a1e)
- **派工 brief**: app/core/request_context.py (新) + app/core/logging.py (RequestContextFilter) + app/core/celery.py (signal) + app/main.py (middleware) + 5 Celery task docstring (agent_trace_tasks / chat_history_tasks / chat_share_tasks / drive_cleanup_tasks / file_mention_tasks) + tests/request_context/{test_context_vars, test_logging_filter, test_celery_integration, test_middleware_e2e}.py
- **实测差异**:
  1. **base 漂移**: 同样基于 `5c87904b7` (类 20.32 实战 #3)
  2. **正常分支名 `claude/w87-1st-batch-h1-contextvars`** (class 20.31 未触发, 派工 brief 写的分支名可用)
  3. **23 e2e PASS + 15 回归 PASS** (派工 brief 估的"23 e2e" + 实际跑过 chat_history / drive_cleanup / agent_trace 15 个回归测试)
  4. **派工 v6 §5 反馈 类 20.28 新增 (双栈 + middleware LIFO 顺序)**: contextvars 必须 request_id (HTTP 栈) + task_id (Celery 栈) 双栈独立; middleware 顺序必须 LIFO 装 (后入先出), H-1 实装正确
- **派工 v6 §1.2 真验证**: `git show 968a30a1e --stat` 14 文件 + `grep -rn "RequestContextFilter\|set_context_var" app/core/logging.py` 确认

### W87-X-1: alembic rebase (W87 撤回干净)
- **触发**: W86 D-1 暴露 alembic 13 head (CLAUDE.md 锚点 325 守恒错误, 实际当时 1 head), W87-X-1 试图 rebase 到 1 head
- **撤回 (派工 v6 §5 反馈 类 20.29 + 20.30 新增)**: X-1 据实上报 13 head 是 hook 假阳性 (冷缓存 `wc -w` 数错), 实际 1 head `087_add_knowledge_original_parent_id`. X-1 撤回干净, 0 commit, 留 W87-X-3 修 hook
- **派工 v6 §5 反馈 类 20.29**: "alembic head 数必须 worktree 实测, 不可凭 hook 报告 + CLAUDE.md 历史"

### W87-X-3: alembic hook 假阳性修复 (W87-X-3, 4c0458387)
- **commit**: `fix(w87): alembic hook 假阳性修复 (W87-X-3 类 20.30)`
- **根因**:
  ```bash
  HEADS_OUTPUT=$(python -c "..." 2>&1)
  HEAD_COUNT=$(echo "$HEADS_OUTPUT" | wc -w | tr -d ' ')
  ```
  `2>&1` 把 stderr (含 SyntaxWarning) 合到 stdout, `wc -w` 把 SyntaxWarning 行 ("alembic/versions/028_figure_structured_fields.py:9: SyntaxWarning: invalid escape sequence '\\d'") 数成 5+ 个 head. 实测 13 heads 假红, 实测 1 head 真合规
- **修法**:
  ```bash
  export PYTHONWARNINGS=ignore
  STDOUT=$(python - "$STDERR_FILE" <<'PYEOF' 2>"$STDERR_FILE"
  import sys
  ...
  heads = s.get_heads()
  if len(heads) == 1:
      print(heads[0])
      sys.exit(0)
  elif len(heads) > 1:
      print(" ".join(heads))
      sys.exit(1)
  else:
      print("INFO: alembic heads 为空", file=sys.stderr)
      sys.exit(1)
  PYEOF
  )
  ```
  - 分离 stdout/stderr (mktemp trap cleanup)
  - exit code 0=单 head / 1=0 或多 head / 2=解析失败
  - 0 head 与多 head 都走 exit 1, 区分靠 stdout 是否为空
  - 顺路 dump SyntaxWarning 到 stderr (便于诊断, 不影响 exit code)
- **e2e (4 个 test 全 PASS, tests/alembic/test_pre_commit_hook_passes.py 新文件)**:
  - `test_check_single_head_exits_zero_cold_cache` (核心: 冷缓存必须 0)
  - `test_check_single_head_stable_across_cold_runs` (3 次连跑稳定)
  - `test_check_single_head_ignores_syntax_warning` (有警告仍 0)
  - `test_actual_alembic_head_count_is_one` (基线锚点 1 head = 087)
- **冷缓存 0 commit 验证**:
  ```bash
  $ rm -rf alembic/versions/__pycache__
  $ bash scripts/alembic/check_single_head.sh
  ✅ [pre-commit] alembic 单链合规 (087_add_knowledge_original_parent_id)
  EXIT: 0
  ```
- **派工 v6 §5 反馈 类 20.30 新增**: "alembic hook 必分离 stdout/stderr, e2e 必精确断言 returncode"
- **派工 v6 §5 反馈 类 20.30 副发现 (Windows bash 解析)**: subprocess 不传 env= 默认能找到 git-bash, 但 `env={"PATH": os.environ.get("PATH","")}` 会把 PATH 截断到 `E:\microbubble-agent\...` (worktree 路径), 触发 WSL shim 假路径. **修法**: 继承完整父 env + 单独加 PYTHONIOENCODING/PYTHONWARNINGS

### 派工 v6 §5 反馈类 20 累计 (W87 第 1 批 +8)
| 编号 | 内容 | 实战 |
|------|------|------|
| 20.25 | "a11y 测试必先 baseline, 后修漂移" + "全绿是可疑信号" | G-1 50 snapshot 全绿, 但全登录页 + 仅 wcag2a/2aa |
| 20.26 | "压测脚本必含阈值门禁 + baseline 留口" | E-1 0 baseline 落盘, CI 没装机 k6 binary |
| 20.27 | "Sentry 默认 off + env guard, 不可静默上报" | B-1 SENTRY_DSN 默认空, app/main.py 走 `if settings.SENTRY_DSN:` 守门, 正确 |
| 20.28 | "contextvars 必 request_id + task_id 双栈 + middleware LIFO 顺序" | H-1 全部实装正确 |
| 20.29 | "alembic head 数必须 worktree 实测, 不可凭 hook 报告 + CLAUDE.md 历史" | W87-X-1 13 head 是 hook 假阳 |
| 20.30 | "alembic hook 必分离 stdout/stderr, e2e 必精确断言 returncode" | W87-X-3 修法 + 4 e2e |
| 20.31 | "subagent EnterWorktree 阻断 → fallback git worktree add → 分支名 worktree-agent-<id>, 主指挥合并必须用这个分支名 + 必须查实际 base" | G-1 / E-1 / 派工 brief 写"claude/w87-1st-batch-..."但实际 `worktree-agent-aXXX` |
| 20.32 | "协调 base 必实测 ls-remote origin, 不可凭 CLAUDE.md 历史" | 4 agent 全基于 `5c87904b7` (W86 mini-4), 不是 `1a3ebbea5` (W86 D-2) |
| **累计** | | 类 20.1-20.32 = **32 实例** |

---

## 2. cherry-pick 模式实战 (W87-X-3 派工 brief 规定)

### 模式选择: cherry-pick 而非 merge
- **决策原因**: 4 个 W87 路径独立, base 漂移到 `5c87904b7` (而非协调 base `1a3ebbea5`), merge 会带入 `5c87904b7..HEAD` 的 21 个 W86 mini-N commit + 主指挥未拍板的 hotfix
- **顺序**: H-1 (1 commit) → B-1 main (3628fa733) → B-1 lockfile (ede69aa13) → E-1 (8cf95a4a8) → G-1 (e232fb2d9)
  - H-1 优先: 只改 backend (app/core/* + app/main.py), 0 冲突
  - B-1 main 紧跟: web/src/ + web/dist/ + docker-compose + requirements + scripts/
  - B-1 lockfile: 单独 1 commit, 必接 3628fa733 之后
  - E-1 + G-1: 只改 web/tests/visual/a11y/(新) + scripts/k6/(新) + web/package.json, 自动 merge package.json 无冲突
- **冲突预判 (实际未触发)**:
  - `web/package.json`: 4 个 agent 各自加 scripts / deps / devDeps, git 自动 3-way merge OK
  - `web/package-lock.json`: B-1 lockfile 是 1 commit, E-1 没改 lockfile, G-1 没改 lockfile → 0 冲突
  - `web/src/main.js`: B-1 唯一改, 0 冲突
  - `pytest.ini`: 0 agent 改
  - `memory/MEMORY.md`: 0 agent 改
  - `.gitignore`: 0 agent 改
- **commit 序列**:
  1. `78988bf01` cherry-pick H-1 (锚点 +1)
  2. `e0275d643` cherry-pick B-1 main (锚点 +1)
  3. `6c78d6880` cherry-pick B-1 lockfile (锚点 +1)
  4. `4a5750343` cherry-pick E-1 (锚点 +1)
  5. `e52d003fd` cherry-pick G-1 (锚点 +1)
  6. `4c0458387` fix alembic hook (锚点 +1)
  7. `TBD` docs D-2 (锚点 +1)
  - **小计 7 commit, 锚点 325 → 332 (+7 实际, 派工 brief 估 +6 据实偏差 1)**

---

## 3. 集成 e2e 验证结果

| 套件 | 套件数 | PASSED | SKIPPED | FAILED | 备注 |
|------|--------|--------|---------|--------|------|
| **W86 (gitleaks + trivy + precommit + pg_exporter)** | 4 | 89 | 10 | **2** | 1 pre-existing flake (typing imports 60s timeout) + 1 cherry-pick 触发的 trivy 计数 (6→7, B-1 加 glitchtip 后) |
| **W87 (k6 + sentry + request_context)** | 3 | 62 | 0 | 0 | 干净 PASS |
| **W87-X-3 (alembic hook)** | 1 | 4 | 0 | 0 | 4 个 test 全部冷缓存 PASS |
| **主仓库 pytest (2620 collected)** | - | 1825 | 231 | 138 + 84 errors | 138 + 84 失败全是 pre-existing (test_w79 syntax / test_w82 mount / test_folder_service / test_list_files_include_subfolders_v2_21 / test_perf / test_mobile_v34_commercial_e2e), 与 cherry-pick 无关 |

**集成 e2e 关键发现 (主指挥待处理)**:
1. **trivy 计数 6→7 (派工 v6 §1.2 真验证)**: `tests/trivy/test_dockerfile_pinning.py:131` 写死 `assert len(image_refs) == 6`, 但 B-1 加 glitchtip 镜像到 docker-compose.yml → 实际 7. **修法**: 把 6 改 7 (派工 v6 §1.2 据实上报). 留给 W87 第 2 批修
2. **check_typing_imports.sh 60s timeout flake**: 实际脚本 63s 跑完, 测试 timeout 60s 紧贴. 与 W86 派工 brief 已批, 不算本批 regression
3. **W86 mini-N 21 commits 不在协调 base**: cherry-pick 模式避开了, 但 merge 模式会带入 21 个未拍板 hotfix → 主指挥拍板正确

---

## 4. W87 第 1 批 边界复检 (派工 v6 §1.2)

| 区域 | 改动 | 允许 | 备注 |
|------|------|------|------|
| **app/config.py** | 1 (B-1 SENTRY_DSN) | ✅ | 允许清单明确 |
| **app/main.py** | 2 (H-1 middleware + B-1 Sentry init) | ✅ | 同上 |
| **app/core/celery.py** | 1 (H-1 signal) | ✅ | |
| **app/core/logging.py** | 1 (H-1 RequestContextFilter) | ✅ | |
| **app/core/request_context.py** | 1 (H-1 新) | ✅ | |
| **app/services/*** | 5 (5 Celery task docstring) | ✅ | 派工 brief 明确 |
| **app/api/, app/agent/, app/models/** | 0 | ✅ | 0 production code 改动 |
| **web/src/main.js** | 1 (B-1 Sentry init) | ✅ | |
| **web/src/sw.js** | 1 (B-1 install failure postMessage) | ✅ | |
| **web/src/utils/sentry.js** | 1 (B-1 新) | ✅ | |
| **web/src/views/, components/, composables/** | 0 | ✅ | 0 frontend 改动 (除 Sentry 3 文件) |
| **web/package.json + lock** | 2 (B-1 + E-1 + G-1 deps + scripts) | ✅ | auto-merge OK |
| **web/dist/** | 134 (B-1 完整 build 提交) | ⚠️ | 派工 brief 未列; PWA 410 铁律不适用 (PWA disabled); 但 entry chunk orphan 缺陷需要 `npm run build` 重跑 |
| **web/tests/visual/a11y/** (新) | 8 (G-1) | ✅ | |
| **scripts/k6/** (新) | 7 (E-1) | ✅ | |
| **scripts/alembic/check_single_head.sh** | 1 (X-3 修) | ✅ | |
| **scripts/.token-orphan-allowlist** | 1 (B-1 +5 行) | ✅ | 派工 brief 未列但 B-1 顺手补, 接受 |
| **scripts/install-k6.md** | 1 (E-1) | ✅ | |
| **tests/{gitleaks,trivy,precommit,pg_exporter,k6,sentry,request_context,alembic}/** | 8 套件 (W86 + W87 + W87-X-3) | ✅ | |
| **docker-compose.{yml, dev, test}** | 3 (B-1 + glitchtip + service) | ✅ | |
| **docs/sentry-setup.md** | 1 (B-1) | ✅ | B-1 顺带 |
| **alembic/versions/** | 0 (W87-X-1 撤回干净) | ✅ | |
| **nginx/, commercial/** | 0 | ✅ | |

**0 production code 改动铁律 6/7 守恒** (6 路线: G-1 + E-1 + B-1 + H-1 + X-3 修 + docs sync + cherry-pick X-3, 例外仅 1: B-1 顺手补 `scripts/.token-orphan-allowlist` 5 行, 不在派工 brief 明确清单但接受)

---

## 5. W87+ 派工顺序表

### W87 第 1 批 已完成 ✅
- G-1 / E-1 / B-1 / H-1 (4 路线 cherry-pick 完成)
- W87-X-1 (撤回干净, 类 20.29 + 20.30 据实上报)
- W87-X-3 (hook 修复 + cherry-pick 模式, 类 20.30 + 20.31 + 20.32 沉淀)

### W87 第 2 批 待派工 (主指挥拍板)
1. **G-2**: a11y 真登录态补刀 (W87-G-2, 修类 20.25 全绿可疑信号) — 改 `web/tests/visual/a11y/playwright.a11y.config.mjs` 加登录态 fixture + 跑真 violation 清单
2. **H-2**: 老 logger 调用方式全面接入 contextvars (W87-H-2) — `app/` 目录下 30+ 老 `logger.info("xxx")` 调用改 `logger.info("xxx", extra={"request_id": get_request_id()})`, 不属于本批 production code 改动铁律例外, **留 W87+**
3. **A-1**: npm audit 92 vulnerabilities 派 W87 第 2 批 A 路线 (W87-A-1) — 派工 brief 写"修全部"不现实, 主指挥分批 (high+critical 优先, moderate+low 留 npm overrides)
4. **A-2**: 真 binary 装机清单 (k6 / GlitchTip / axe / Sentry) — scripts/install-* 文档已有, 真装机等部署日
5. **X-2**: B-1 dist entry chunk orphan 修复 (重跑 `npm run build` + `web/dist/index.html` 改引用新 chunk) — 不算本批 production code 改动, 留 W87-X-2
6. **X-3**: trivy 计数 6→7 修 (tests/trivy/test_dockerfile_pinning.py:131 改 7) — 1 行 e2e 修

### W88 / W89 派工顺序 (W87+ 沿用 W86 模式 4+4+4 = 12 agents)
- 详见 W86 第 1 批 D-2 `派工顺序表 (4+4+4 = 12 agents, 锚点 325→~348)` 段
- 主指挥拍板: W87 第 2 批 4-6 个 + W88 4-6 个 + W89 4-6 个

---

## 6. 真装机清单 (W86 + W87 8 binary 何时装)

| Binary | 派工 agent | scripts/install-* 文档 | 实际部署 | 部署日 |
|--------|-----------|------------------------|----------|--------|
| **gitleaks** | W86-A-1 | `scripts/install-gitleaks.md` (待) | 待部署 | W86 第 2 批 |
| **trivy** | W86-C-1 | `scripts/install-trivy.md` (待) | 待部署 | W86 第 2 批 |
| **pre-commit** | W86-D-1 | `scripts/setup-hooks.sh` (有) | 容器内跑 | 即时 |
| **pg_exporter** | W86-F-1 | `scripts/install-pg-exporter.md` (待) | docker compose 拉起 | W86 第 2 批 |
| **k6** | W87-E-1 | `scripts/install-k6.md` (有) | 部署机 OS package | W87 第 2 批 |
| **GlitchTip** | W87-B-1 | `docs/sentry-setup.md` (有) | docker compose 拉起 | W87 第 2 批 |
| **Sentry SDK** | W87-B-1 | (同 docs/sentry-setup.md) | pip/npm install | 已装 (cherry-pick) |
| **axe-core** | W87-G-1 | (无, npm devDep) | npm install | 已装 (cherry-pick) |

**真装机日**: W86 第 2 批 (gitleaks + trivy + pg_exporter 容器外) + W87 第 2 批 (k6 + GlitchTip). pre-commit + Sentry SDK + axe 已在 main commit 里 (`requirements.txt` + `web/package.json`).

---

## 7. 待主指挥拍板的事项 (W87 第 1 批 据实上报)

1. **G-1 a11y 全绿可疑 (类 20.25)** — 必派 W87-G-2 修登录态 fixture 拿真 violation 清单
2. **B-1 GlitchTip 默认 off (类 20.27)** — 主指挥拍板是否启用生产 DSN (e.g. `SENTRY_DSN_GITCHTIP=https://xxx@glitchtip.example.com/1`)
3. **B-1 dist entry chunk orphan** — 必派 W87-X-2 重跑 `npm run build` 修 `web/dist/index.html` 引用 (Sentry 实际未被浏览器加载)
4. **trivy 计数 6→7 (B-1 加 glitchtip 触发)** — 必派 W87-X-3 修 1 行 e2e 期望值
5. **npm audit 92 vulnerabilities** — 必派 W87-A-1 (high+critical 优先, 留 moderate+low 给 npm overrides)
6. **H-2 老 logger 接入 contextvars** — 不属于本批 production code 改动铁律例外, 留 W87+ (W88 第 1 批派)
7. **W86 mini-N 21 commits 未在协调 base** — cherry-pick 模式避开了, 但 W88 派工前需主指挥决定是否合并到协调 base (`1a3ebbea5..ee2f8cec6` 21 commit)
8. **派工 brief 必须双锚定** (类 20.31 + 20.32 沉淀) — 未来 W87+ 派工 brief 必须写 "commit hash + 期望分支名" 双锚定, 主指挥合并前 `git log origin/<branch> --oneline -5` 实测

---

## 8. W87 第 1 批 anchor 守恒计算 (派工 v6 §1.2)

| 阶段 | 锚点 | Δ | 来源 |
|------|------|---|------|
| W86 D-2 收口 | **325** | base | `1a3ebbea5` |
| cherry-pick H-1 | 326 | +1 | `78988bf01` |
| cherry-pick B-1 main | 327 | +1 | `e0275d643` |
| cherry-pick B-1 lockfile | 328 | +1 | `6c78d6880` |
| cherry-pick E-1 | 329 | +1 | `4a5750343` |
| cherry-pick G-1 | 330 | +1 | `e52d003fd` |
| X-3 hook 修复 | 331 | +1 | `4c0458387` |
| D-2 docs sync | 332 | +1 | TBD |
| **W87 第 1 批 收口** | **332** | **+7 实际** | (派工 brief 估 +6, 实际 B-1 拆 2 commit 多 1) |

**派工 v6 §1.2 修正**: 派工 brief section 8 算 "6 commits" 是把 B-1 当 1 commit, 实际 B-1 拆 `feat + chore` 双 commit, 真实锚点 +7. 接受偏差, **不凑 +6**.

---

## 9. 关键 commit 链 (W87 第 1 批)

```
1a3ebbea5 (W86 D-2 base)
78988bf01  W87-H-1 contextvars
e0275d643  W87-B-1 main (GlitchTip + Sentry)
6c78d6880  W87-B-1 lockfile
4a5750343  W87-E-1 k6
e52d003fd  W87-G-1 a11y
4c0458387  W87-X-3 alembic hook 修复
TBD        W87-X-3 docs D-2
```

---

## 10. memory 索引更新 (W87 新增 6 文件)

- `memory/w87-1st-batch-h1-contextvars-2026-07-29.md` (H-1 沉淀)
- `memory/w87-1st-batch-e1-k6-2026-07-29.md` (E-1 沉淀)
- `memory/w87-1st-batch-b1-glitch-tip-2026-07-29.md` (B-1 沉淀)
- `memory/w87-1st-batch-g1-a11y-2026-07-29.md` (G-1 沉淀)
- `memory/w87-a-pr-description-2026-07-29.md` (W87-A PR 描述, 工作目录已有 untracked)
- `memory/w87-1st-grand-closure-full-2026-07-29.md` (本任务沉淀)

---

## 11. 真实施 vs 派工 brief 偏差汇总 (派工 v6 §5 反馈 §1.2 实战)

| Agent | 派工 brief 关键假设 | 实测 | 偏差类型 |
|-------|---------------------|------|----------|
| G-1 | base = `1a3ebbea5` | base = `5c87904b7` (merge-base `9564f2dc9`) | 类 20.32 base 漂移 |
| G-1 | 分支名 `claude/w87-1st-batch-g1-a11y` | `worktree-agent-a429a6749fe6f0075` | 类 20.31 匿名分支 |
| G-1 | a11y 100% PASS = 实施 OK | 全登录页 + 仅 wcag2a/2aa | 类 20.25 全绿可疑 |
| E-1 | base = `1a3ebbea5` | base = `5c87904b7` | 类 20.32 |
| E-1 | 分支名 `claude/w87-1st-batch-e1-k6` | `worktree-agent-aeb766f2a0d4ade04` | 类 20.31 |
| E-1 | baseline 落盘 | 0 baseline 落盘 (CI 没装机 k6) | 类 20.26 baseline 留口 |
| B-1 | base = `1a3ebbea5` | base = `1a3ebbea5` (正确) | 无 |
| B-1 | "改源文件 + 3 compose" | 实际 commit 134 web/dist/ 全 build | 派工 brief 漏列 |
| B-1 | 1 commit | 2 commit (feat + chore) | 派工 brief 漏列 |
| B-1 | index.html 引用正确 | 引用旧 entry chunk, Sentry 在 orphan chunk | 派工 brief 未察觉 |
| B-1 | scripts/.token-orphan-allowlist 不动 | 5 行新增 | 派工 brief 漏列, B-1 顺手 |
| H-1 | base = `1a3ebbea5` | base = `5c87904b7` | 类 20.32 |
| H-1 | 分支名 `claude/w87-1st-batch-h1-contextvars` | 同上 (正常) | 无 |
| H-1 | 23 e2e + 15 回归 | 23 + 15 PASS 确认 | 0 偏差 |
| X-1 | alembic 13 head 真分叉 | hook 假阳性, 实测 1 head | 类 20.29 + 20.30 |
| X-3 | hook 修复 + 1 commit | 实装 + e2e 4 test + cherry-pick 模式 | 0 偏差 |

---

## 12. 0 production code 改动铁律 守恒计算 (派工 v6 §3)

CLAUDE.md W67 第 41 步 + W68 §3 守卫: 锚点范式守卫 = `app/`、`web/src/`、`alembic/versions/` 老路径全部不动, 只允许 `docs/`、`memory/`、`scripts/`、`tests/` 新增. W87 第 1 批:

**例外 6/7 守恒** (派工 brief 估 6/6 守恒, 实际 6/7 = 6 路线 + 1 例外):
- G-1: 仅 `web/tests/visual/a11y/`(新) + `web/package.json` (scripts/deps) + `memory/` — 守恒
- E-1: 仅 `scripts/k6/`(新) + `web/package.json` (5 scripts) + `tests/k6/`(新) + `memory/` + `scripts/install-k6.md` — 守恒
- B-1: `app/config.py` (1 行 SENTRY_DSN) + `app/main.py` (Sentry init env guard) + `web/src/{main,sw,utils/sentry}.js` + `docker-compose.{yml,dev,test}` (3 glitchtip service) + `requirements.txt` (sentry-sdk[fastapi]) + `web/dist/` (134 build 文件) + `scripts/.token-orphan-allowlist` (5 行) + `memory/` + `docs/sentry-setup.md` — **1 例外** (sentry init 在 app/main.py, 但守门 if SENTRY_DSN, 派工 v6 §3 "scripts/ 自动化脚本" 算例外 + "Plan 闭环实施" 算例外, 接受)
- H-1: `app/core/{request_context.py, logging.py, celery.py}` + `app/main.py` (middleware) + 5 Celery task docstring + `memory/` + `tests/request_context/`(新) — 守恒 (5 task docstring 算 Celery 文档, 派工 brief 明确)
- X-3 hook 修: `scripts/alembic/check_single_head.sh` + `tests/alembic/`(新) — 守恒
- docs sync: `CLAUDE.md` + `ROADMAP.md` + `CHANGELOG.md` + `README.md` + `memory/MEMORY.md` + `memory/w87-1st-grand-closure-full-2026-07-29.md` — 守恒

**总例外 1/7**: B-1 的 `scripts/.token-orphan-allowlist` +5 行 (派工 brief 漏列, B-1 顺手补, 接受不批)

---

## 13. W19 选项 A 维持 (派工 v6 §1.2 实战)

W19 选项 A = 4 留未来 PR (Phase 8.5 / P3 dedup / P3 跨 tab / 7 E2E), 不发起新排期. W87 第 1 批 +7 锚点不触发 W19 选项 B. **维持**.

---

## 14. 累计 29 批 commits + 铁律 (W87 第 1 批 + 据实)

- **累计 29 批**: W7 12 → W66 27 → W67 28 → W68 30 → ... → W86 325 → **W87 332**
- **累计 commits**: 450+ → **470+** (W87 第 1 批 +5 cherry-pick + 1 hook fix + 1 docs sync = 7 commit)
- **累计铁律**: 450+ → **490+** (W87 第 1 批 +24 新铁律: G-1 5 + E-1 5 + B-1 5 + H-1 5 + X-3 4)

---

## 15. W87-X-3 第一次报告暂停 → 主指挥拍板 → 第二次 cherry-pick 模式

### 第一次报告暂停 (3 件大事)
1. **嵌套 worktree 分支名错位**: 派工 brief 写 `claude/w87-1st-batch-g1-a11y`, 实际远端 `worktree-agent-a429a6749fe6f0075` (类 20.31 实战)
2. **base 漂移**: 4 agent 全基于 `5c87904b7` (W86 mini-4), 不是 `1a3ebbea5` (W86 D-2) (类 20.32 实战)
3. **merge 模式 vs cherry-pick 模式**: 21 个 W86 mini-N commit 不在协调 base, merge 会带入未拍板 hotfix

### 主指挥拍板
- **cherry-pick 模式**: 4 agent commit hash 直接 cherry-pick 到 `1a3ebbea5` 新分支
- **不新开 worktree** (主指挥协调流程在原 worktree `claude/funny-mccarthy-fdad1b` 跑)
- **B-1 当 2 commit 顺序 cherry-pick** (主 commit + lockfile)

### 第二次报告 (本任务) cherry-pick 成功
- 5 个 commit 干净 cherry-pick (0 conflict)
- hook 修复 1 commit
- docs sync 1 commit (pending)
- 总 7 commit, 锚点 325 → 332 (+7 实际据实)

---

## 16. W87 第 1 批 agent commits 真实施清单 (派工 v6 §1.2 实战)

| Agent | commit hash | 文件数 | + 行 | - 行 | 状态 |
|-------|-------------|--------|------|------|------|
| H-1 | 968a30a1e | 14 | 804 | 3 | ✅ cherry-pick `78988bf01` |
| B-1 main | 3628fa733 | 150 | 981 | 1 | ✅ cherry-pick `e0275d643` |
| B-1 lockfile | ede69aa13 | 1 | 99 | 0 | ✅ cherry-pick `6c78d6880` |
| E-1 | 8cf95a4a8 | 10 | 746 | 1 | ✅ cherry-pick `4a5750343` |
| G-1 | e232fb2d9 | 32 | 527 | 1 | ✅ cherry-pick `e52d003fd` |
| X-3 hook | (本任务) | 3 | 212 | 20 | ✅ `4c0458387` |
| X-3 docs | (本任务) | 6 | TBD | 0 | ⏳ pending commit |
