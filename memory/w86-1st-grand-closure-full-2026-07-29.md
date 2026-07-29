# W86 第 1 批 grand closure (2026-07-29)

**W86 第 1 批 grand closure** (主基调 "W85 据实上报 2 实例派生 W86 5 agents + P0 安全/合规 4 路线并行启动: gitleaks + Trivy + pre-commit + pg_exporter + X-2 e2e 修复 + D-2 6 类文档同步"). 主指挥协调范式第 62 次派工. 锚点范式单调上升 W85 第 1 批 320 → **W86 第 1 批 324** (+4, 4 路线 merge +1 each, X-2 e2e 修复据实不算, D-2 文档同步 +1 实战). 累计 28 批 450+ commits + 450+ 铁律 (W86 第 1 批 +24+ 新铁律). **0 production code 改动铁律 4/4 守恒** (4 路线全部是装机 + 扫描脚本 + e2e, 不动 production code). W19 选项 A 维持. 详见 `memory/w86-1st-grand-closure-full-2026-07-29.md` (本文件, W86-X-2 D-2 沉淀).

## 锚点范式真实施 (派工 v6 §1.2 + W85 D-2 拦截 #19 实战 + W86 X-1 据实上报)

**起点 (W85 closure)**: 320 (commit `9564f2dc9`, hotfix(w85) knowledge.original_parent_id)

| agent | branch tip | merge commit | 锚点增量 | 据实上报 |
|-------|-----------|--------------|----------|----------|
| A-1 gitleaks | `chore/w86-1st-batch-a1-gitleaks-2026-07-29` → `82b11e92d` | `c32f50701` | +1 (320→321) | gitleaks 装机 + .gitleaks.toml + workflow + scan-history.sh + 装机说明 + e2e (10 case, 4 fixture PASS + 6 binary SKIP 待装机). 8 允许文件, 0 production code |
| C-1 Trivy | `chore/w86-1st-batch-c1-trivy-2026-07-29` → `48886a568` | `5cdd89a0e` | +1 (321→322) | trivy 镜像扫描 + 9 Dockerfile base image 钉死 + workflow + scripts + e2e (47→48 PASS, X-2 修复后 48/48). 0 production code |
| D-1 pre-commit | `chore/w86-1st-batch-d1-pre-commit-2026-07-29` → `8394dd94b` | `7723095fc` | +1 (322→323) | pre-commit 框架接入 + 5 hook 整合 (trivy/check_pinned_images + alembic/check_single_head + web/check_dist_manifest + check_typing_imports + 兼容 setup-hooks.sh) + e2e. 0 production code |
| F-1 pg_exporter | `chore/w86-1st-batch-f1-pg-exporter-2026-07-29` → `b3b2413ce` | `a4d773dfd` | +1 (323→324) | pg_exporter 安装 + 3 compose service (production/dev/test) + scripts + e2e (3 service × 5 case + 1 覆盖率 = 16 case PASS). 0 production code |
| X-1 合并 | 主拍 | `c32f50701`~`a4d773dfd` | +0 (4 merge commits 已含) | 4 路线 merge, 据实上报 2 e2e FAIL (test_refs_discovered 5→6 + _is_pinned 不接受 v 前缀) |
| X-2 e2e 修复 | (本任务 commit 1) | (本任务 commit) | +0 (修测试, 沿用 CLAUDE.md 锚点范式"功能/文档收口 commit +1"口径, 测试修不算) | 选项 A 最小改动 2 行: `len(image_refs) == 5 → 6` + `_is_pinned` 正则加 `v?` 前缀. 集成 4 套件 90 PASS + 10 SKIP + 0 FAIL |
| D-2 6 类文档同步 | (本任务 commit 2) | (本任务 commit) | +1 验证不计 + 1 实施 (5 段同步 + runbook + memory) | 沿用 W85 D-1 模式. CLAUDE.md + ROADMAP.md + CHANGELOG.md + README.md + memory/MEMORY.md + memory/w86-1st-grand-closure-full-2026-07-29.md (新建完整沉淀) |

**真实累计**: 320 + 4 + 1 (D-2 实战) = **325** (4 路线真实施 + D-2 实战 +1). X-2 e2e 修复按 CLAUDE.md 锚点范式"功能/文档收口 commit 算 +1"口径不算, 实际累计 +5.

**注**: W86-X-1 报告锚点 324 守恒, 本任务 D-2 文档同步按 W85 D-1 模式 +1 实战 = 325. X-2 e2e 修复不算 (沿用 CLAUDE.md 锚点范式口径).

## W86 第 1 批 5 路线 + X-1 主拍 + X-2/D-2 收口 派工清单

- **A-1 gitleaks** (branch `chore/w86-1st-batch-a1-gitleaks-2026-07-29`, merge commit `c32f50701`, 锚点 +1): gitleaks 装机 + .gitleaks.toml (5 条自定义规则: anthropic/openai/private-key/jwt-bearer/minio-admin-default + github-token + anthropic-claude-api-key, 全 allowlist 段含 fixture + docs + 锁文件 + stopwords) + .github/workflows/secret-scan.yml (PR + push + 周一 6 点 cron, SARIF + JSON 双产物, 失败门禁 exit 1) + scripts/gitleaks/scan-history.sh (exit code 0/1/2 三档) + scripts/install-gitleaks.md (macOS/Linux/Windows/Docker 4 方案) + tests/gitleaks/test_scan_clean_repo.py (10 case: 6 binary 依赖 + 4 fixture) + memory/w86-1st-batch-a1-gitleaks-2026-07-29.md + memory/w86-1st-batch-a1-gitleaks-scan-2026-07-29.md + .gitignore (logs/gitleaks-report.{json,sarif} 兜底). 扫描结果 (本机 manual grep 模拟, 真 binary 未装): 0 真凭据泄漏 + 1 历史残留 (commit 6573f2b3 deleted tests/qa-bench/_login.json + _token.txt, admin JWT exp 2026-07-21 已过期 8 天, 待 W86-X-1 git filter-repo 重写) + 6 MinIO 默认凭据 (非 user:pass 配对, 不匹配规则 5) + 1 真生产 key 占位符模板 (.env.production.example W78 B-2 设计). e2e 验证: 4 fixture PASS + 6 binary SKIP (等装机).
- **C-1 Trivy** (branch `chore/w86-1st-batch-c1-trivy-2026-07-29`, merge commit `5cdd89a0e`, 锚点 +1): trivy 镜像扫描 (aquasecurity/trivy-action) + 9 Dockerfile base image 钉死 (8 Dockerfile + 1 compose 5 image → X-2 修后 6 image 含 pg-exporter v0.15.0) + .github/workflows/trivy-scan.yml (PR + push + 周日 3 点 cron, advisory-only) + scripts/trivy/scan-images.sh + scripts/install-trivy.md + tests/trivy/test_dockerfile_pinning.py (47→48 PASS X-2 修后) + tests/trivy/test_workflow_exists.py (7 PASS) + memory/w86-1st-batch-c1-trivy-2026-07-29.md + Dockerfile pin comment "pinned on 2026-07-29 for CVE tracking (W86-C-1 Trivy)". X-1 报告 2 FAIL (test_refs_discovered 5→6 + _is_pinned 不接受 v0.15.0), X-2 修复后 48/48 PASS.
- **D-1 pre-commit** (branch `chore/w86-1st-batch-d1-pre-commit-2026-07-29`, merge commit `7723095fc`, 锚点 +1): pre-commit 框架接入 + .pre-commit-config.yaml (5 hook: trivy/check_pinned_images.py + alembic/check_single_head.sh + web/check_dist_manifest.sh + check_typing_imports.sh + 兼容 setup-hooks.sh 入口) + tests/precommit/test_config_valid.py (6 PASS) + tests/precommit/test_hooks_executable.py (4 PASS + 4 SKIP binary + 4 集成 PASS) + memory/w86-1st-batch-d1-pre-commit-2026-07-29.md. 0 production code.
- **F-1 pg_exporter** (branch `chore/w86-1st-batch-f1-pg-exporter-2026-07-29`, merge commit `a4d773dfd`, 锚点 +1): pg_exporter 安装 (quay.io/prometheuscommunity/postgres-exporter:v0.15.0) + docker-compose.yml 3 service (production/dev/test, 端口 9187/9199) + scripts/pg-exporter/slow_query.sh (5 列 markdown table + shebang + strict mode + 密码 env) + tests/pg_exporter/test_compose_service_defined.py (3 service × 5 case + 1 覆盖率 = 16 PASS) + tests/pg_exporter/test_slow_query_script.py (6 PASS + 1 覆盖率) + memory/w86-1st-batch-f1-pg-exporter-2026-07-29.md. 0 production code.
- **X-1 主拍合并** (merge commits `c32f50701` `5cdd89a0e` `7723095fc` `a4d773dfd`): 主指挥派工 + 沿用 W82 A-1 拦截 #15 + W82 merge 流程, 4 merge commit + 据实上报 2 e2e FAIL (test_refs_discovered 5→6 + _is_pinned 不接受 v 前缀), 未推 D-2.
- **X-2 e2e 修复 + D-2 文档同步** (本任务, commit 1 e2e 修复 + commit 2 D-2 文档同步): 选项 A 最小改动 2 行 (tests/trivy/test_dockerfile_pinning.py:131 + `_is_pinned` 正则加 `v?`), 集成 4 套件 90 PASS + 10 SKIP + 0 FAIL. D-2 沿用 W85 D-1 模式 (5 段同步 + runbook + memory + 1 完整 grand closure 沉淀).

## 类 20 (派工前提错配) W86 新增

- **类 20.24 (X-1 + X-2 沉淀)**: "并行 agent 各自 PASS, 集成 e2e 红于隐藏假设". 4 路线 (gitleaks / Trivy / pre-commit / pg_exporter) 各自 e2e 都 PASS, 但集成 e2e (4 套件一起跑) 时 trivy 套件的 test_refs_discovered + test_no_floating_tag 同时 FAIL. 根因: 各 agent 独立设计 + 独立测试, 派工 brief 没说"集成 e2e 时必须考虑其他 agent 的新增产物" (F-1 加 pg-exporter 第 6 image 改变 trivy 的引用计数假设, 0.15.0 改变 `_is_pinned` 正则假设). **铁律**: 并行派多 agent 时, 派工 brief 必含"集成 e2e 一致性" 段, 各 agent 的 e2e 必须独立跑 + 集成跑 + 至少 1 个 cross-suite 集成验证 (本次遗漏, X-2 修后守恒).

## 类 20.21 / 20.22 / 20.23 (W86-X-1 报告里的 3 个非本任务沉淀, 留待主指挥确认)

W86-X-1 报告里提及"派工 v6 §5 反馈 3 新实例 (类 20.21 hook 不测合规 / 类 20.22 不照抄建议版本 / 类 20.23 负向对照)", 本任务未直接遇到这 3 个, 仅做 W86-X-2 据实上报. 主指挥可在后续 W86 closure memory 增补, 或留 W87 沉淀.

## 派工前提铁律 12 + W82/W83/W84/W85 沿用 (W86 X-2/D-2)

1. **派生新任务必先 git log 真验证** — base HEAD `9564f2dc9` 验证 ✓ (W86-X-1 已 4 merge)
2. **0 production code 改动铁律**: docs/memory/tests/scripts 范畴, 不动 production code
3. **D-2 据实上报锚点真实施**: W86 X-2 锚点 324 守恒 (4 路线 +4), D-2 文档同步 +1 实战 = 325. commit message 必须如实写 +1, 不能写 +5
4. **5 段同步实战**: CLAUDE.md 当前状态 + ROADMAP.md + CHANGELOG.md + README.md + memory/MEMORY.md
5. **runbook + memory + e2e 必出**: 沿用 W85 D-1 模式 (本任务仅 memory, 无 runbook 因 W86 X-1 已 4 路线 memory 沉淀充分)
6. **W85 据实上报 2 实例 + W86 X-2 沉淀 1 实例**: 沉淀回写 5 段同步 (类 20 实战 20 + 类 20.13 实战 19 + 类 20.24 实战 21 W86 新增)
7. **W85 D-1 沿用**: 沿用 W85 D-1 commit 同模式 (5 段同步 + runbook + memory + e2e + commit)
8. **派工 v6 §1.2 + W84 D-2 拦截 #18**: 锚点必须如实写, 不能凑 +N (D-2 据实上报 +1 实战, X-2 e2e 修复不算)
9. **alembic 串单链**: 派工前必读 alembic 当前 1 head, 不擅自加双 head (CLAUDE.md W68 第 6+7 批纪律沉淀) — W86 4 路线不动 alembic
10. **4 路搜证不可省略**: 路径 1 origin log / 路径 2 git grep / 路径 3 reflog / 路径 4 commit hash, 派工前必全跑
11. **W82/W83/W84/W85 据实上报铁律**: 派工 brief 估错不擅自扩也不擅自缩 (X-2 修复据实 2 行, 不擅自重构 _is_pinned 整函数)
12. **git log 真验证**: 派生新任务前必须 `git log --oneline -5` 确认 base HEAD, 派工 brief 列举文件/函数前必须 grep 全仓验证

## W86 第 1 批核心成果

- **P0 安全/合规 4 路线并行启动 (A-1 + C-1 + D-1 + F-1)**: gitleaks 凭据扫描 + Trivy 镜像 CVE 扫描 + pre-commit 5 hook 接入 + pg_exporter 监控. W86 主线装机 + 扫描 + 监控合规化.
- **W86-X-2 e2e 修复 (本任务 commit 1)**: 选项 A 最小改动 2 行, 集成 4 套件 90 PASS + 10 SKIP + 0 FAIL. 类 20.24 沉淀"并行 agent 集成 e2e 隐藏假设".
- **W86-D-2 6 类文档同步 (本任务 commit 2)**: 沿用 W85 D-1 模式, 锚点如实写 +1 实战 (X-2 e2e 修复按 CLAUDE.md 锚点范式"功能/文档收口 commit 算 +1"口径不算).
- **派工 v6 §5 反馈类 20 累计 21 实例** (W86 新增 1: 类 20.24 并行 agent 隐藏假设).

## 累计 commits / 铁律

- **累计 28 批 450+ commits + 450+ 铁律** (W86 第 1 批 +24+ 新铁律: A-1 8 + C-1 5 + D-1 5 + F-1 5 + X-2/D-2 1)
- **alembic 13 head** — D-1 hook (alembic/check_single_head.sh) 暴露多 head, 实际是 D-1 hook 自身未跑 (本机 pre-commit binary 未装) 或 hook 设计缺陷, 留 W87-X-1 派 alembic rebase agent 处理
- **派工前提铁律 12 条 + 类 20 累计 21 实例** (W86 新增 1: 类 20.24 并行 agent 隐藏假设)

## W19 选项 A 维持

4 留未来 PR (Phase 8.5 / P3 dedup / P3 跨 tab / 7 E2E) 不发起新排期. 量化触发条件维持.

## W87/W88/W89 派工顺序表 (主指挥决策)

锚点范式 325 → ~348 (W87/W88/W89 三批 12 agents, 每批 ~4-5). 顺序:

- **W87 第 1 批 (4 agents)**: X-1 alembic rebase agent (D-1 hook 暴露 13 head 修复) + X-2 真 binary 装机 (gitleaks / trivy / pre-commit 各 binary 装上) + X-3 deploy-auto.sh 集成 trivy scan + pg-exporter health check + X-4 1 个常规新功能 agent
- **W88 第 1 批 (4 agents)**: 沿用 W87 4 agents 模板
- **W89 第 1 批 (4 agents)**: 沿用 W87 4 agents 模板

W87 第 1 批 4 agents 候选:
- **G-1 axe-core/playwright** (5/10 需求度, W85 A-2 调研派生)
- **E-1 k6 压测** (6/10 需求度, W85 A-2 调研派生)
- **B-1 GlitchTip** (9/10 需求度, 自托管外部依赖, 用户已确认要装)
- **K-1 Langfuse** (跳过, 已留口在 grand closure memory — Langfuse 是 SaaS, 不在本项目自托管范围)

## 待主指挥后续排期 (W86-X-2 D-2 沉淀)

1. **gitleaks / trivy / pre-commit / pg_exporter 真 binary 待装** (W86-X-2 没动 deploy-auto.sh)
2. **alembic 13 head** (D-1 hook 暴露, 需 W87-X-1 派 alembic rebase agent 处理)
3. **deploy-auto.sh 集成 trivy scan + pg-exporter health check** 留 W87+ 排期
4. **alembic 087 knowledge.original_parent_id** 已 hotfix commit `9564f2dc9` (W85 hotfix 实战), 但 alembic 多 head 仍未 rebase, 需 W87 处理

## 真装机清单 (W86-X-2 D-2 沉淀)

- **gitleaks binary**: macOS `brew install gitleaks` / Linux `apt install gitleaks` / Windows `choco install gitleaks` / Docker `aquasec/gitleaks`. 装机后跑 `bash scripts/gitleaks/scan-history.sh exit 0/1/2`. 详细见 `scripts/install-gitleaks.md`.
- **trivy binary**: macOS `brew install trivy` / Linux `apt install trivy` / Windows `choco install trivy`. 装机后跑 `bash scripts/trivy/scan-images.sh`. 详细见 `scripts/install-trivy.md`.
- **pre-commit binary**: `pip install pre-commit` + `pre-commit install` (安装 git hooks). 装机后跑 `pre-commit run --all-files`.
- **pg-exporter binary**: 已通过 docker-compose 集成 (quay.io/prometheuscommunity/postgres-exporter:v0.15.0), 装机 = `docker compose up -d pg-exporter`. 详细见 `scripts/install-pg-exporter.md`.

## 集成 e2e 验证 (W86-X-2 本任务硬门禁)

```
$ SKIP_DB_SETUP=1 pytest tests/gitleaks/ tests/trivy/ tests/precommit/ tests/pg_exporter/ -v
======================= 90 passed, 10 skipped in 59.39s =======================
```

- 90 PASSED + 10 SKIPPED + 0 FAILED
- 10 SKIP 全是 binary 依赖类 (gitleaks binary 未装 4 + trivy binary 未装 2 + pre-commit hook binary 未装 4), 等装机后跑
- 0 FAILED — W86-X-1 报告的 2 个 FAIL (test_refs_discovered + test_no_floating_tag) X-2 修复后全 PASS

## 累计 / 历史

- **W86 第 1 批** = 累计 28 批 (W2-W85 27 批 + W86 第 1 批)
- **0 production code 改动铁律**: 28/28 批全程守恒 (W86 4 路线 0 production code, X-2 修测试也不算 production code)
- **W19 选项 A**: 28/28 批维持
- **派工前提铁律 12 条**: 28/28 批沉淀
- **类 20 累计 21 实例**: W82 #15 + W82 #16 + W83 沿用 + W84 #17 #18 + W84 据实上报 3 + W85 据实上报 2 + W86 X-2 #24