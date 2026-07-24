---
name: w68-route-12-b3-d7-baseline-ci-2026-07-24
description: "W68 第 12 批 B-3 qa-bench D7 baseline CI 自动化：PR/manual workflow、fail-loud shell gate、D5 workflow audit step、Slack/PR failure notification，71 PASS + 7 SKIP 守恒，锚点范式第 150 守恒。"
metadata:
  node_type: memory
  type: project
  originSessionId: W68-12-B3-D7
  modified: 2026-07-24T00:00:00.000Z
---

# W68 第 12 批 B-3：qa-bench D7 baseline CI 自动化

## TL;DR

W68 第 12 批 B-3 将 qa-bench 的历史 baseline 契约自动化：每个 PR 在打开、重开或同步时运行 D7，手动 dispatch 也可复跑；D5 质量门禁旁新增 baseline audit；失败时尝试 PR/GitHub CLI 通知与 Slack webhook 通知。验证目标固定为 **71 PASS + 7 SKIP、0 fail/error、`app import OK`**。本任务只修改 workflow、scripts、docs、memory，**0 production code 改动**，锚点范式第 **150** 次守恒。

## 背景与缺口

W68 第 5 批 #6 已建立 qa-bench D6 80% gate workflow，但质量题库通过率与项目基础回归不是同一类证据。D5 可以达到 80%，同时仍然漏掉 baseline 文件漂移、stale 测试重新出现、核心 app 包无法导入等问题。历史 baseline 由 9 个文件组成，共收敛为 78 个 collected tests，其中 71 个通过、7 个在 `SKIP_DB_SETUP=1` 下按设计跳过。

此前 baseline 主要依靠主指挥手工运行，CI 没有对每次 PR 自动执行。因此本批将“71 + 7”从文档约定提升为可执行、可报警、可追踪的 CI 契约。

## 交付物

### 1. 独立 workflow

`.github/workflows/qa-bench-baseline.yml` 提供：

- `pull_request` 的 `opened`、`reopened`、`synchronize` 触发；
- `workflow_dispatch` 手动触发；
- Python 3.11；
- Redis 7 service container；
- qa-bench requirements 与 baseline runtime dependencies 安装；
- `python tests/test_baseline_audit.py` 模块 smoke；
- 39 条 audit assertions；
- 9 文件 baseline 契约执行；
- `python -c "import app; print('app import OK')"`；
- 失败日志 artifact；
- PR/GitHub CLI 与 Slack webhook 的失败通知。

### 2. 本地/CI shell gate

`scripts/ci_qa_bench_baseline.sh` 是主指挥和 CI 共用入口。它：

1. 固定 9 个 baseline 文件；
2. 执行 audit 模块与 audit assertions；
3. 执行 9 文件 pytest；
4. 严格解析 `71 passed` 与 `7 skipped`；
5. 拒绝 failed/error 或非零退出码；
6. 执行 app import smoke；
7. 将全部输出写入 `logs/ci-baseline-$(date +%Y%m%d).log`；
8. 任意失败退出码为 1。

日志目录在仓库中被忽略，避免把运行期内容提交进 Git，但 CI 会上传日志 artifact 供排障。

### 3. D5 workflow 并行 audit

`.github/workflows/qa-bench-ci.yml` 在 D5 报告上传后增加 D7 audit step。该 step 在已经启动的 `app-test` 容器内执行，复用完整应用运行时与内部服务 DNS；`SKIP_DB_SETUP=1` 保持 baseline 只做测试，不初始化或污染业务数据库。D7 不替换 D5 的 80% gate，两者都是独立检查。

### 4. 文档

`docs/qa-bench-d7-baseline-ci.md` 记录触发器、依赖、执行顺序、通知、故障处理、本地运行和部署必做事项。

## 真实验证

### Baseline audit

```text
SKIP_DB_SETUP=1 python -m pytest tests/test_baseline_audit.py -q
39 passed in 2.91s
```

### 9 文件完整契约

本地 Windows 宿主没有映射 Redis 6379，因此直接运行会得到 connection refused；这是环境边界，不是 baseline drift。启动临时 Redis 7 容器后使用 `REDIS_URL=redis://localhost:16379/0` 验证：

```text
71 passed, 7 skipped, 16 warnings in 1.79s
```

这与历史契约完全一致。7 个 skip 来自需要真实数据库的 `tests/scripts/test_kb_dedup_admin_cli_e2e.py`，并非失败。

### app import

```text
SKIP_DB_SETUP=1 python -c "import app; print('app import OK')"
app import OK
```

### Shell/YAML checks

```text
bash -n scripts/ci_qa_bench_baseline.sh
```

shell syntax check 通过。workflow 使用 GitHub Actions 标准 YAML 结构，包含服务容器、权限、artifact 与 failure 条件；提交前应由 GitHub Actions 进行最终 workflow parser 校验。

## 失败通知策略

通知不是质量 gate 的替代品：pytest 与 shell gate 的退出状态仍决定 job 是否失败。failure step 使用 `set +e`，避免 Slack 或组织专用 `gh notification` 扩展缺失时遮蔽原始错误。

- 有 `gh notification create` 扩展时，尝试创建 PR 通知；
- 普通 runner 回退到 `gh pr comment`；
- `SLACK_WEBHOOK_URL` 存在时发送 JSON Slack 消息；
- secret 缺失时打印跳过原因；
- workflow run URL、commit、期望值都进入通知正文。

仓库管理员如要启用 Slack，需要配置 repository secret `SLACK_WEBHOOK_URL`。通知链路本身采用 best-effort，不能把通知失败误报成测试成功。

## 5 条新铁律

1. **每次 PR 必跑 baseline**：baseline workflow 必须响应 PR opened/reopened/synchronize，不能只依靠人工或 push 后抽查。
2. **71 PASS + 7 SKIP 守恒**：期望值是精确回归契约，任何 PASS、SKIP、FAIL、ERROR 数字变化都必须先调查，不得通过放宽 grep 或修改阈值消除红灯。
3. **Slack/PR 通知**：baseline 失败必须尝试 PR/GitHub CLI 与 Slack webhook 通知；通知缺失只允许 best-effort 跳过，不能吞掉 gate 失败。
4. **失败退出码为 1**：脚本必须在 audit、baseline、import 任一失败时返回 1，并写入当日 dated log；CI 不能依靠日志文本判断成功。
5. **跨主题 baseline 守恒**：D5 题库 gate、D7 文件 audit、app import smoke 是三种互补证据；D5 通过不等于 D7 通过，任何跨主题代码/文档合并后都要保留 71/7 证据。

## 锚点范式第 150 守恒

本批沿用“0 production code 改动”纪律：没有修改 `app/`、`web/src/`、老 migration 或业务测试实现，仅增加 CI 自动化入口、脚本、运行文档与 memory。D7 把 W68 既有 baseline evidence 接入每个 PR，形成自动触发、精确断言、失败退出、日志留存、通知尝试的闭环，因此记为锚点范式第 150 次守恒。

趋势保持单调：W62 24 → W66 27 → W67 28 → W68 各批递增，历史 71 PASS + 7 SKIP 未被改写。

## 部署与合并必做

本任务不产生 alembic migration，不需要数据库升级，不需要生产 Docker 重建，不需要 Nginx 变更，也不应触发生产重启。主指挥合并前必须：

1. 检查 `git diff --stat`，确认只包含 5 个目标文件；
2. 运行 `bash -n scripts/ci_qa_bench_baseline.sh`；
3. 运行 baseline audit 与 app import；
4. 确认分支保护把 D7 与 D5 设为 required checks；
5. 在仓库 secrets 中配置 `SLACK_WEBHOOK_URL`（若需要 Slack）；
6. 合并后打开一个 PR 或手动 dispatch，确认 Actions 页面实际生成 D7 job；
7. 确认 artifact 中有 `ci-baseline-YYYYMMDD.log`；
8. 失败时沿用原始 traceback，不修改 expected counts 作为快速修复。

## 后续观察

- GitHub Actions runner 上的 `gh` 是否包含组织专用 `notification` 扩展由组织环境决定；普通 runner 会稳定走 `gh pr comment` fallback。
- Redis service health check 必须保持，避免 baseline 在 Redis 尚未 ready 时产生误红。
- 如果未来 baseline 文件增删，必须同步 `tests/test_baseline_audit.py`、`tests/conftest.py`、docs baseline 清单、D7 shell 数字和本 memory，并在新 commit 中明确说明守恒基线变化。
- 7 个真实 DB E2E skip 仍是有意留项，不应通过移除 `SKIP_DB_SETUP` 将 D7 变成数据库集成工作流。
