# GitHub Actions secret 部署 (W89-P-9 沉淀, 类 20.57 实战)

> **场景**: W89-P-3 写了 `.github/workflows/playwright.yml` (a11y + visual 2 job), 已 commit 在 `claude/w89-p3-playwright-ci` 分支 (待主指挥合并). CI 触发需要 3 个 secret. 本任务文档化部署命令 + 真机验证可达性.

## 必需 secret (派工 v6 §5 反馈 类 20.57)

| Secret 名 | 来源 | 用途 | 引用文件 |
|---|---|---|---|
| `PLAYWRIGHT_TEST_TOKEN` | `xiaoqi_testbot` 登录拿 JWT | Playwright a11y + visual 登录态注入 | `.github/workflows/playwright.yml` (2 job 都有) |
| `PLAYWRIGHT_TEST_USERNAME` | `xiaoqi_testbot` | login API 用户名 (留口备用) | 备用 (登录态已由 token 直接注入) |
| `PLAYWRIGHT_TEST_PASSWORD` | `testbot_pass_2026` | login API 密码 (留口备用) | 备用 (登录态已由 token 直接注入) |

**为什么 USERNAME/PASSWORD 也是 secret 而非 plaintext**:
- secret 是 GitHub 加密存储, repo Settings → Secrets → Actions 可见 (但非明文 log)
- 万一未来 workflow 改回 "动态登录拿 token" 模式 (而非直接 token 注入), USERNAME/PASSWORD 是必要输入
- 统一 3 secret 避免后续 workflow 改时还得返工部署

## 部署命令 (主指挥手动执行)

```bash
# 用 gh CLI (本机未装, 真部署留主指挥)
gh secret set PLAYWRIGHT_TEST_USERNAME --body "xiaoqi_testbot"
gh secret set PLAYWRIGHT_TEST_PASSWORD --body "testbot_pass_2026"
gh secret set PLAYWRIGHT_TEST_TOKEN --body "<token-from-login-api>"
```

### 拿 token 的 API 调用 (一次性)

```bash
# 本地 (假设 app 监听 8000)
TOKEN=$(curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"xiaoqi_testbot","password":"testbot_pass_2026"}' \
  | python -c "import json, sys; print(json.load(sys.stdin).get('access_token', ''))")

echo "Token 长度: ${#TOKEN}"

# CI 环境 (假设 app-test 监听 8001, docker-compose.test.yml)
TOKEN=$(curl -X POST http://localhost:8001/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"xiaoqi_testbot","password":"testbot_pass_2026"}' \
  | python -c "import json, sys; print(json.load(sys.stdin).get('access_token', ''))")
```

> **⚠️ 安全铁律**:
> - **绝不** commit token 到任何文件 (不入 git, 不入 .env.example, 不入测试 fixture)
> - **绝不** 在 PR 描述/issue 评论贴真 token
> - token 过期 (JWT 默认 24h TTL, 视后端配置) → CI 可能随机失败 → 考虑用 long-lived API key 而非 JWT

## 本机限制报告 (W89-P-9 实测)

| 项目 | 状态 | 说明 |
|---|---|---|
| gh CLI | ❌ 未装 (`which gh` 0 hit) | 真 secret 部署留主指挥 |
| docker ps app 状态 | ✅ Up 37 minutes (healthy) | app 监听 8000 可调 |
| xiaoqi_testbot 账号存在? | ❓ 未知 (派工 brief 假设存在) | 本机没数据库 root 凭据验证 |
| 拿 token 验证 | ⏸ 跳过 | 本机不写 secret 到文件, 不真请求 login |
| 真 CI 触发 (workflow_dispatch) | ⏸ 跳过 | gh CLI 未装 |

## 真部署步骤 (主指挥执行清单)

```bash
# 1. 确认 gh CLI 已装 + auth 状态
gh --version && gh auth status

# 2. 合并 W89-P-3 branch (含 .github/workflows/playwright.yml + web/package.json scripts + tests/playwright_ci/)
git checkout main
git merge --no-ff claude/w89-p3-playwright-ci -m "merge(w89): P-3 Playwright CI 接入 (a11y + visual 2 job, 锚点 +1)"
git push origin main

# 3. 部署 3 secret
gh secret set PLAYWRIGHT_TEST_USERNAME --body "xiaoqi_testbot"
gh secret set PLAYWRIGHT_TEST_PASSWORD --body "testbot_pass_2026"
gh secret set PLAYWRIGHT_TEST_TOKEN --body "<从 CI 环境 login API 拿的 JWT>"

# 4. 触发 workflow_dispatch 验证
gh workflow run playwright.yml --ref main

# 5. 看 CI 日志
gh run list --workflow=playwright.yml --limit 5
gh run view <run-id> --log
```

## 类 20.57 新增铁律

> **Playwright CI secret 部署必含**:
> 1. **3 secret 名 (TOKEN/USERNAME/PASSWORD) 必文档化** — 仅 TOKEN 必传, USERNAME/PASSWORD 留口备用
> 2. **gh CLI 必先验证** — `which gh` + `gh auth status` 必须先过, 否则部署会半途失败
> 3. **真 token 拿法必含 login API 调用模板** — curl + json parse 必写出, 留主指挥直接复制
> 4. **本机限制必诚实报告** — gh 未装/账号未验证/token 未实测, 据实上报不伪造
> 5. **CI 触发必配 workflow_dispatch** — 仅 push 触发不够, 留手动触发兜底

## memory 沉淀

详见 `memory/w89-p9-ci-trigger-2026-07-30.md` (本任务同 commit 沉淀).