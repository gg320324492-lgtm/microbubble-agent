# 真 CI 触发 (W89-P-9 沉淀, 类 20.57 实战)

> **场景**: W89-P-3 已写 `.github/workflows/playwright.yml` (a11y + visual 2 job), 待主指挥合并 + 部署 secret 后真触发. 本任务文档化触发命令 + 预期行为 + 本机限制.

## 触发命令

### 方式 1: workflow_dispatch (手动触发)

```bash
# gh CLI
gh workflow run playwright.yml --ref main

# 或带 inputs (workflow 没定义 inputs, 标准 workflow_dispatch 即可)
```

### 方式 2: push 触发 (自动)

```bash
# 任何 push 到 main 都会触发 (web/** 或 playwright.yml 改动会触发 PR, push main 必触发)
git commit --allow-empty -m "ci: trigger Playwright e2e"
git push origin main
```

### 方式 3: PR 触发

```bash
# 改 web/** 自动触发 (paths 过滤已配)
gh pr create --base main --head feat/my-change --title "..."
```

## 预期行为

### Job 1: a11y (axe-core)

| 项目 | 预期 | 实测 (主指挥填) |
|---|---|---|
| timeout | 15 min | ⏸ |
| steps | 6 (checkout / setup-node / npm ci / npx playwright install / 起 test env / run a11y) | ⏸ |
| 默认结果 | hard fail (continue-on-error 没设) | ⏸ |
| 失败兜底 | upload artifact (test-results + playwright-report, 7d retention) | ⏸ |
| Teardown | always 跑 docker compose down -v | ⏸ |

### Job 2: visual regression

| 项目 | 预期 | 实测 (主指挥填) |
|---|---|---|
| timeout | 20 min | ⏸ |
| 默认结果 | **continue-on-error: true** (第一版非阻塞) | ⏸ |
| 触发策略 | 与 a11y 同 | ⏸ |
| Update snapshots | 仅 `push && refs/heads/main` 自动跑 | ⏸ |
| 失败兜底 | upload artifact (test-results, 7d retention) | ⏸ |
| 主指挥拍板 | baseline 稳定后撤掉 continue-on-error 改 hard fail | ⏸ |

## 本机限制 (W89-P-9 据实上报)

| 项目 | 状态 | 影响 |
|---|---|---|
| gh CLI 未装 | ❌ | 无法 workflow_dispatch / 看 CI 日志 / 设 secret |
| 真 CI 触发 | ❌ | 留主指挥手动执行 |
| 真部署 secret | ❌ | 留主指挥手动执行 |
| 本机 app 跑 | ✅ (Up 37 min healthy) | 仅供本机 dev 调试, 无关 CI |
| W89-P-3 已合并到 main? | ❌ (待合并) | 主指挥合并后 CI 才有 workflow 触发 |

## 主指挥合并清单 (W89-P-9 移交)

```bash
# 1. 合并 W89-P-3 branch
git checkout main
git merge --no-ff claude/w89-p3-playwright-ci -m "merge(w89): P-3 Playwright CI 接入 (a11y + visual 2 job)"
git push origin main

# 2. 合并 W89-P-9 branch (本任务: docs/ci-secret-setup.md + ci-trigger.md + tests/ci_trigger/ + memory/)
git merge --no-ff claude/w89-p9-ci-trigger -m "merge(w89): P-9 真 CI 触发文档化 + secret 部署留口"

# 3. 部署 3 secret (详见 docs/ci-secret-setup.md §"部署命令")
gh secret set PLAYWRIGHT_TEST_USERNAME --body "xiaoqi_testbot"
gh secret set PLAYWRIGHT_TEST_PASSWORD --body "testbot_pass_2026"
gh secret set PLAYWRIGHT_TEST_TOKEN --body "<token>"

# 4. 触发 workflow_dispatch 验证
gh workflow run playwright.yml --ref main

# 5. 看 CI 日志
gh run list --workflow=playwright.yml --limit 5
```

## 类 20.57 实战沉淀

详见 `docs/ci-secret-setup.md` §"类 20.57 新增铁律" + `memory/w89-p9-ci-trigger-2026-07-30.md`.

### 5 条铁律简记

1. **3 secret 名必文档化** (TOKEN/USERNAME/PASSWORD)
2. **gh CLI 必先验证** (`which gh` + `gh auth status`)
3. **真 token 拿法必含 login API 调用模板**
4. **本机限制必诚实报告** (不伪造可达性)
5. **CI 触发必配 workflow_dispatch** (留手动触发兜底)

## 相关文档

- `docs/ci-secret-setup.md` — secret 部署详细指南
- `.github/workflows/playwright.yml` — workflow 定义 (W89-P-3 写, 待合并)
- `memory/w89-p9-ci-trigger-2026-07-30.md` — 本任务 memory 沉淀
- `memory/w89-p3-playwright-ci-2026-07-30.md` — W89-P-3 workflow 设计沉淀