# GitHub Secrets 配置 (W67 必读)

> **版本**: W67 (2026-07-23)
> **生效**: qa-bench D5 gate 切 mimo cloud 后
> **目标读者**: 主指挥、运维、新人
> **配套文档**: [tests/qa-bench/GUIDE.md](../tests/qa-bench/GUIDE.md) + [deploy.md](./deploy.md)

## TL;DR

本项目 GitHub Actions 需要以下 5 个 Secret。缺失会导致对应 workflow 失败。

| Secret 名 | 来源 | 用途 |
|-----------|------|------|
| `MIMO_API_KEY` | https://token-plan-cn.xiaomimimo.com | qa-bench D5 gate 真实跑题 |
| `QA_TOKEN` | 后端 `/api/v1/auth/login` 拿的 JWT | qa-bench smoke (200 题 test DB) |
| `WEBHOOK_SECRET` | 主指挥本地生成 | push 触发 webhook 部署 |
| `DOCKERHUB_USERNAME` + `DOCKERHUB_TOKEN` | hub.docker.com | 镜像 push (如有) |

> **W67 关键改动**: qa-bench D5 gate 从 `ANTHROPIC_API_KEY` 切到 `MIMO_API_KEY`(本地 LLM 也已切 mimo cloud, OpenAI 兼容协议)。

## 必填 Secret (按 workflow 分组)

### 1. `MIMO_API_KEY` — qa-bench D5 gate 1000 题真实跑

| 字段 | 值 |
|------|-----|
| Name | `MIMO_API_KEY` |
| 来源 | https://token-plan-cn.xiaomimimo.com 控制台 |
| 格式 | `tp-...` (主指挥本地 `.env` 已有) |
| 用在哪 | `.github/workflows/qa-bench-ci.yml` 第 28-37 行 env block |

### 2. `QA_TOKEN` — qa-bench smoke 200 题 (test DB)

| 字段 | 值 |
|------|-----|
| Name | `QA_TOKEN` |
| 来源 | test DB 启动后 `POST /api/v1/auth/login` 返回的 JWT |
| 用在哪 | `.github/workflows/qa-bench-smoke.yml` `Run 200 题 smoke` 步骤 |

### 3. `WEBHOOK_SECRET` — push 触发 webhook 部署

| 字段 | 值 |
|------|-----|
| Name | `WEBHOOK_SECRET` |
| 来源 | 主指挥本地 `openssl rand -hex 32` 生成 (32 字符) |
| 用在哪 | webhook 接收脚本 (部署侧), 验证 header `X-Hub-Signature-256` |

### 4. (按需) `DOCKERHUB_USERNAME` + `DOCKERHUB_TOKEN`

仅当 PR 需要 build & push Docker 镜像时才用。一般不会走 GitHub Actions push 镜像(本地 build 推到阿里云个人 registry), 留空即可。

## 详细步骤: 添加 MIMO_API_KEY

1. 浏览器登录 GitHub: <https://github.com/gg320324492-lgtm/microbubble-agent/settings/secrets/actions>
2. 点击 **"New repository secret"**
3. Name: `MIMO_API_KEY`
4. Secret: 从 <https://token-plan-cn.xiaomimimo.com> 控制台复制 API key(格式 `tp-...`)
5. 点击 **"Add secret"**

> **注意**: GitHub Secret 一旦保存就**不可见**(只显示 `***`)。改值只能删了重建, 不能编辑。误填的话只能 Delete + Add new。

## 验证

加完后, 触发任意 workflow(push 一个 commit 或 `workflow_dispatch`), 在 Actions log 里搜 `MIMO_API_KEY` 应该看到:

- **日志里**显示 `MIMO_API_KEY=***`(GitHub 自动隐式 sensitive env)
- 紧接着 `python runner.py --rounds=3 ...` 真实跑题(无 `RuntimeError: MIMO_API_KEY not set`)

如果想本地验证 (不 push), 可手动 `workflow_dispatch` 触发 + 看 runner logs 的第一步。

## runner.py 自动检测 mimo backend

`tests/qa-bench/runner.py` 在以下条件时自动走 mimo cloud(无需改代码):

- `LLM_BACKEND=openai_compat` (env)
- `LLM_OPENAI_COMPAT_BASE_URL=https://token-plan-cn.xiaomimimo.com/v1`
- `LLM_OPENAI_COMPAT_MODEL=mimo-v2.5`
- `MIMO_API_KEY` env 或 `LLM_OPENAI_COMPAT_API_KEY` env 已设置

CI workflow 已配齐以上 4 个 env, runner 走 `/api/v1/chat/stream` 调用 mimo cloud 而不是本机 ollama(本地 qa-bench 跑也走 mimo, 见 `app/core/llm.py:LLM_BACKEND` 分支)。

## 主指挥本地手动跑题

```bash
# 1. 加载 .env (含 MIMO_API_KEY + LLM_OPENAI_COMPAT_*)
cd E:/microbubble-agent
set -a; source .env; set +a

# 2. 跑 smoke
python tests/qa-bench/runner.py --token "$JWT_TOKEN" --limit 200 --concurrency 3

# 3. 跑 D5 全量
python tests/qa-bench/runner.py --rounds=3 --verdict-consensus=2 --include-extra \
  --full-1000 --ci-gate --output=baseline_d5_1000.json
```

> **并发建议**: `--concurrency 3` 是经验值(mimo tier 限流保护), 30-60 min 跑完。报 429 时降到 1。

## qa-bench D5 gate CI 触发流程 (W67 第 30 步)

W67 起 D5 gate 完整 CI 流程:

1. **Setup Python + Install deps** — pip install requirements.txt (httpx + pyyaml + psygopg2 等)
2. **Start test DB stack** — Docker 起 pg-test (postgres:16) + app-test (uvicorn 8001), 复用 qa-bench-smoke 模板, 切 `LLM_BACKEND=openai_compat` 走 mimo cloud
3. **Init test DB** — init_db.py (create_all + seed 24 members) + alembic stamp head
4. **Ensure test user** — ensure_test_user.py (xiaoqi_testbot)
5. **Generate 1000 题题库** — gen780.py schema-only 生成 base 700 题 + 检查 questions_d4_extra_300.jsonl (300 题已存在)
6. **Run 1000 题 baseline** — runner.py --include-extra --rounds 3 --verdict-consensus majority (约 60 分钟)
7. **Upload baseline report** — artifacts (results/baseline_d5_1000/, 保留 30 天)
8. **Fail if pass_rate < 80%** — 硬门禁, 低于即 exit 1
9. **Teardown** — docker stop + rm + network rm

### 关键环境变量 (Step 6)

| 变量 | 值 | 来源 |
|------|-----|------|
| `MIMO_API_KEY` | `tp-...` | GitHub Secret (`secrets.MIMO_API_KEY`) |
| `LLM_BACKEND` | `openai_compat` | 切 mimo cloud (非本地 ollama) |
| `LLM_OPENAI_COMPAT_BASE_URL` | `https://token-plan-cn.xiaomimimo.com/v1` | mimo 端点 |
| `LLM_OPENAI_COMPAT_MODEL` | `mimo-v2.5` | mimo 模型 |
| `QA_TOKEN` | test DB JWT (mock 兜底) | GitHub Secret 或 fallback `mock` |

## app-test 健康检查 timeout 调整 (W67 第 32-33 步)

`Start test DB stack` 步骤里 `curl -sf http://localhost:8001/health` 等待循环:

| 时间 | Budget | 原因 |
|------|--------|------|
| W66 之前 | 90s (45 × 2s) | 假设 mimo SDK init < 18s |
| W67 第 32 步 | 240s (120 × 2s) | mimo SDK + 全套 import 慢 |
| W67 第 33 步 | 600s (300 × 2s) | 拆 build + run 后, 实际启动 6-10 min |
| W67 第 34 步 | 900s (450 × 2s) | 实测 909s, 差 9 秒 |
| W67 第 35 步 | 1500s (750 × 2s) | 提 1500s 留充分缓冲, uvicorn + mimo SDK 15+ min |

**关键修复 (W67 第 33 步)**: `docker build -q .` 在 `docker run` 同一行导致每次重 build. 拆成:

1. **Step 5a** `docker build -t app-test:ci .` (Build, 缓存 Docker layer)
2. **Step 5b** `docker run app-test:ci` (Run, 用已 build image, 启动 30-60s)

W67 第 36 步已改用 `docker/build-push-action@v5` + `cache-from: type=gha`，通过 GitHub Actions cache 跨 run 复用 Docker layers。详见下节。

如果你的环境 (Anthropic 直连 / 本地 ollama / mock) 启动快, 可以调回 240s. 但默认 900s 兼容 mimo cloud 套件 + 冷启动 (实测 610s, 留 290s 缓冲).

## 真 GHA cache (W67 第 36 步)

| 时间 | 方案 | 实测 build 时间 |
|------|------|------------------|
| W66 | `docker build -q .` (no cache) | 6-10 min |
| W67 第 33 步 | 拆 build + run (单 step build) | 6-10 min (首次) |
| W67 第 36 步 | `docker/build-push-action@v5` + `cache-from: type=gha` | 1-2 min (warm cache) / 6-10 min (cold) |

**机制**: 跨 run 复用 Docker layer cache. requirements.txt / Dockerfile 不变 → 命中 cache → 跳过 pip install + base image pull.

**setup-buildx-action 必加 (W67 第 38 步)**: `docker/build-push-action@v5` 默认用 docker driver, **不支持** `cache-from: type=gha` (这是 buildx-only 功能). 必须先 `setup-buildx-action@v3` 配 buildx. 0 config 即用 (默认 builder), 不需要 driver-opts. 装好后 buildx 取代默认 docker driver.

## setup-buildx 必加 (W67 第 38 步)

`docker/build-push-action@v5` 默认用 docker driver, **不支持 `cache-from: type=gha`** (这是 buildx-only 功能). 必须先 `setup-buildx-action@v3` 配 buildx.

`docker/setup-buildx-action@v3` 0 config 即用 (默认 builder), 不需要 `driver-opts`. 装好后 buildx 取代默认 docker driver.

## build context 修复 (W67 第 37 步)

`docker/build-push-action@v5` 默认 `context` = 当前 step 的 `working-directory` (或 GitHub workspace 根)。qa-bench-ci.yml 第 5 步 `Install Python dependencies` 设了 `working-directory: tests/qa-bench`, **后续 step 没显式 override 时会沿用该 working-directory**, 也就是 `context: .` 实际解析为 `tests/qa-bench/.`, 找不到仓库根的 `Dockerfile` → Step 6 Build 1 秒 fail。

**症状**: Build step log 报 `failed to solve: failed to read dockerfile: open Dockerfile: no such file or directory`

**修法 (两个 workflow 都改)**:

```yaml
- name: Build app-test image
  uses: docker/build-push-action@v5
  with:
    context: ${{ github.workspace }}    # ← 显式仓库根, 防止 working-directory 污染
    file: ${{ github.workspace }}/Dockerfile
    push: false
    load: true
    tags: app-test:ci
    cache-from: type=gha
    cache-to: type=gha,mode=max
```

**铁律**: GHA workflow 中, 任何带 `working-directory` 的 step 之后的 `docker/build-push-action` **必须显式 `context: ${{ github.workspace }}`**, 不依赖默认推断。

## 故障排除

- **CI 仍报 `ANTHROPIC_API_KEY missing`**: 你 push 的 commit **没**包含这次 workflow 改动。检查 `.github/workflows/qa-bench-ci.yml` 第 29 行用的是 `secrets.MIMO_API_KEY` 还是 `secrets.ANTHROPIC_API_KEY`。
- **runner.py 报 401 Unauthorized**: `MIMO_API_KEY` 填错了。重新从 mimo 控制台复制(格式 `tp-...` 前缀)。GitHub Secrets 不让看原值, 只能 Delete + Add new。
- **mimo cloud 超时**: 1000 题预计 30-60 分钟, `timeout-minutes: 60` 可能不够。在 `.github/workflows/qa-bench-ci.yml` 第 12 行改 `timeout-minutes: 90`(CI 最大 360 分钟)。
- **mimo 返回 429 Too Many Requests**: 跑题并发太高, mimo tier 限流。本地复跑时降低 `--concurrency` 或等待 1-2 分钟后重试。
- **本地跑题不知道走哪个 backend**: 看 `app/core/llm.py:LLM_BACKEND` 决定走 Anthropic / openai_compat / ollama。设 `LLM_BACKEND=openai_compat` 走 mimo cloud, 设 `LLM_BACKEND=ollama` 走本地 qwen3:8b(若有 GPU)。

## 历史 (W67 之前)

| 时间 | 改动 | 原因 |
|------|------|------|
| 2026-07-08 | `ANTHROPIC_API_KEY` 首次引入 | 早期 Anthropic 直连 |
| 2026-07-12 | 切 ollama (本地 qwen3:8b) | 离线跑题(本地 GPU) |
| 2026-07-23 | 本地切 mimo cloud (OpenAI 兼容) | 云端 GPU 不够, 走 mimo 远程 |
| 2026-07-23 | CI workflow 同步切 `MIMO_API_KEY` (本次提交) | 配套本地切换, 删 `ANTHROPIC_API_KEY` 引用 |

## 链接

- [tests/qa-bench/GUIDE.md](../tests/qa-bench/GUIDE.md) — qa-bench 用户指南
- [docs/deploy.md](./deploy.md) — 部署指南 (含云服务器 / Docker / FRP)
- [docs/rate-limit.md](./rate-limit.md) — 限流配置参考
- memory [2026-07-02-tool-call-converter-2026-07-01.md](../memory/tool-call-converter-2026-07-01.md) — mimo tool_call converter 收官

---

**变更记录**:

- v1.0 / W67 (2026-07-23): 初版，与 mimo cloud 切换同步
