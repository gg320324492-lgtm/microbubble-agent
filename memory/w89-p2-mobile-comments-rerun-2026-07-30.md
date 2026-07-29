# W89-P-2 mobile-comments 限流修复 (2026-07-30)

> **主基调**: 派工 v6 §5 反馈 类 20.49 沉淀 + mobile-comments 5 case 限流根因 + beforeAll 共享 token 实战 + W89-P-1 派工依赖登记.

## 任务边界 (W89-P-2 派工 brief 据实)

派工 brief 描述:

- **W88-G-2 报告**: mobile-comments 5 case 因 login API 429 限流失败
- **W89-P-2 修法**: 改 `web/tests/visual/a11y/axe-chats.spec.mjs` 用 `beforeAll` 共享 token
- **新硬门禁**: `web/tests/visual/a11y/auth-shared-token.spec.mjs` (5 case PASS)
- **不动 `app/`**: 不要改限流或测试账号
- **base ref**: main tip `5ace8015e` (W87 第 1 批 grand closure merge 收口, 锚点 337)

派工 brief 还提到:

- `injectAuth()` W88-G-2 已实现 "三段注入 (token / API / form)"
- "form 登录 + 5 次/分/IP 限流 (API mode 不限流)"

**⚠️ 类 20.13 实战 16 据实上报**: 派工 brief 描述的 `injectAuth()` **三段形态 与实际代码不符**.
本任务基线 base `5ace8015e` 上 `injectAuth()` 只有 cookie + localStorage 双段注入 (读 `TEST_TOKEN` env var),
**没有 form 登录分支**. W88-G-2 工作尚未 merge 入 main, W89-P-2 无权预改 `injectAuth()` 的形态.

W89-P-2 严格按"不动 app + 共享 token"两条铁律下, 实际修法:

1. `axe-config.mjs` 新增 `getAuthToken(request, opts)` helper (走 `request.post('/api/v1/auth/login')`)
2. `axe-chats.spec.mjs` 加 `beforeAll` 拿 1 次 token, `beforeEach` 注入 (沿用 injectAuth 形态, 仅 token 来源换成 `getAuthToken` 的产物)
3. 新增 `auth-shared-token.spec.mjs` 硬门禁 spec

不动 `app/`, 不动 `web/src/`, 不动限流逻辑.

## 根因链 (派工 v6 §1.2 真验证)

W88-G-2 mobile-comments 5 case 失败的根因链:

1. `app/api/v1/auth.py:65-77` login 端点 5 次/5 分钟/IP 限流 (AsyncRedisRateLimiter, Redis ZSET 后端)
2. 跑 `npx playwright test --project=mobile-comments tests/visual/a11y/auth-shared-token.spec.mjs`
   等同于 5 case × 各自 1 次 login = 5 次 login calls in <1 min
3. 第 6 次必触发 429 (实际上是前 5 次就触发: avg 5.5 算上 retry)
4. 429 后 `page.context()` + `addInitScript` 注入失败 → 被 router 守卫打回 `/login`
5. W88-G-2 报告: mobile-comments 5 case 全部失败 + 重定向到 `/login` 后扫到的是 login 页 (不是目标页)

派工 v6 §5 反馈 类 20.49 沉淀: **"Playwright 多 case 必 beforeAll 共享 token, 避免触发后端限流"**.

## W89-P-2 实战交付

### 文件改动 (3 文件 + 0 production code)

```
web/tests/visual/a11y/axe-config.mjs     |  45 ++++  (新增 getAuthToken helper)
web/tests/visual/a11y/axe-chats.spec.mjs  |  31 ++-  (改 beforeAll/beforeEach 共享 token)
web/tests/visual/a11y/auth-shared-token.spec.mjs  |  107 +++ (新, 硬门禁 spec)
```

边界检查 (派工 v6 §1.2 真验证):

```
$ git status
On branch claude/w89-p2-mobile-comments-rerun
Changes not staged for commit:
	modified:   web/tests/visual/a11y/axe-chats.spec.mjs
	modified:   web/tests/visual/a11y/axe-config.mjs
Untracked files:
	web/tests/visual/a11y/auth-shared-token.spec.mjs
```

**不动**: `app/`, `web/src/`, `alembic/versions/`, `nginx/`, `docker/`, `web/dist/`, `commercial/`
**新增**: `web/tests/visual/a11y/auth-shared-token.spec.mjs` (W89-P-2 硬门禁 spec)
**修改**: `web/tests/visual/a11y/axe-config.mjs` (新增 `getAuthToken()` helper)
**修改**: `web/tests/visual/a11y/axe-chats.spec.mjs` (改 token 来源为 beforeAll 共享)

### 真验证 (派工 v6 §1.2 必跑真启 + 真跑)

#### 1. 真启 dev 环境

```bash
docker compose version  # v5.3.1
docker ps  # microbubble-agent-app-1 (healthy) 已起在 port 8000
curl -sf http://localhost:8000/health -o /dev/null -w "app http=%{http_code}\n"
# app http=200
curl -sf -X POST http://localhost:8000/api/v1/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"username":"xiaoqi_testbot","password":"testbot_pass_2026"}' \
  | python -c 'import sys,json; print(len(json.load(sys.stdin)["access_token"]))'
# 141 (JWT 长度, 真实 token 返回)
```

#### 2. mobile-comments project 真跑 auth-shared-token.spec.mjs

```bash
cd web
BASE_URL=http://localhost API_BASE_URL=http://localhost:8000 \
  npx playwright test -c tests/visual/a11y/playwright.a11y.config.mjs \
  --project=mobile-comments \
  tests/visual/a11y/auth-shared-token.spec.mjs
```

结果:

```
Running 5 tests using 1 worker

[a11y-shared] /chat
        url=http://localhost/chat
        total violations=2  critical/serious=2
          - aria-command-name [serious] ×1
          - color-contrast [serious] ×6
  ok 1  mobile-comments /chat a11y (shared token) (17.4s)

[a11y-shared] /drive
        url=http://localhost/drive
        total violations=2  critical/serious=2
          - aria-command-name [serious] ×1
          - color-contrast [serious] ×11
  ok 2  mobile-comments /drive a11y (shared token) (17.4s)

[a11y-shared] /tasks
        url=http://localhost/tasks
        total violations=3  critical/serious=3
          - aria-command-name [serious] ×1
          - color-contrast [serious] ×110
          - nested-interactive [serious] ×19
  ok 3  mobile-comments /tasks a11y (shared token) (17.7s)

[a11y-shared] /meetings
        url=http://localhost/meetings
        total violations=2  critical/serious=2
          - aria-command-name [serious] ×1
          - color-contrast [serious] ×43
  ok 4  mobile-comments /meetings a11y (shared token) (17.5s)

[a11y-shared] /knowledge
        url=http://localhost/knowledge
        total violations=3  critical/serious=3
          - aria-command-name [serious] ×1
          - color-contrast [serious] ×90
          - nested-interactive [serious] ×20
  ok 5  mobile-comments /knowledge a11y (shared token) (17.6s)

  5 passed (1.5m)
```

**5/5 PASS** — 限流修复目标达成: 全部 5 case 都到达目标路由, 未被 router 守卫打回 /login.

#### 3. 跨 5 project 全跑 (回归确认)

```bash
npx playwright test -c tests/visual/a11y/playwright.a11y.config.mjs \
  tests/visual/a11y/auth-shared-token.spec.mjs
```

结果: **25 passed (7.4m)** — 5 pages × 5 projects (mobile-iphone14 / desktop-chrome / harmonyos-arkweb / mobile-comments / desktop-comments) 全过.

#### 4. axe-chats.spec.mjs + a11y-baseline.spec.mjs 回归 (本任务改动文件)

- `axe-chats.spec.mjs` 改 beforeAll: **5/5 PASS** in mobile-comments project (12.1s)
- `a11y-baseline.spec.mjs` 未改: **5/5 PASS** in mobile-comments project (11.4s)

无 regression.

## 类 20.49 铁律沉淀 (派工 v6 §5 反馈)

### 类 20.49 Playwright 多 case 共享 token

**铁律**: Playwright 多 case 跑同一后端测试账号时, **必** 在 `beforeAll` (或 worker 共享 fixture) 内拿一次 token, 然后 `beforeEach` 注入. 禁止每个 test 自调 `/api/v1/auth/login` (触发 5 次/分/IP 限流) 或 `form 登录按钮点击` (5 次 + form events 双重消耗).

**根因**: `app/api/v1/auth.py:77` login_limiter.check 5 次/5 分钟/IP 限流. 多 case 同 IP 同账号 = 必触发.

**反模式**:

```javascript
// ❌ 每个 test 调一次 login, 5 case × 1 login = 5 login calls
test.beforeEach(async ({ page }) => {
  await page.goto('/login')
  await page.fill('input[name=username]', 'xiaoqi_testbot')
  await page.fill('input[name=password]', 'testbot_pass_2026')
  await page.click('button[type=submit]')
  await page.waitForURL('/chat')
})
```

**正模式**:

```javascript
// ✅ beforeAll 拿一次 token, beforeEach 注入
let sharedToken
test.beforeAll(async ({ request }) => {
  const res = await request.post(`${API}/api/v1/auth/login`, {
    data: { username: 'xiaoqi_testbot', password: 'testbot_pass_2026' },
  })
  sharedToken = (await res.json()).access_token
})
test.beforeEach(async ({ page }) => {
  await page.context().addCookies([{ name: 'access_token', value: sharedToken, domain: 'localhost', path: '/' }])
  await page.addInitScript((tk) => localStorage.setItem('access_token', tk), sharedToken)
})
```

**适用场景**:

- 多 case 同账号访问后端 (任何端点)
- 任何会触发限流的端点 (login, refresh, OTP, password reset, 2FA)
- 任何跨 case 跑同一 IP 同账号的并行 worker (Playwright workers: 1 默认, 增加需注意 IP)

**例外**: 真测"登录失败 → 429 → 401 → 403"路径时, 故意 case 内调 login. 这些 case 之间需 sleep 6 分钟或清 Redis ZSET 限流 key 才能继续.

### 类 20.13 实战 16 据实上报补充 (派工 v6 §5)

**W89-P-2 派工 brief 不符点**:

- 派工 brief 描述 `injectAuth()` 已有"三段注入 (token / API / form)" — **实际基线只有 token 段**
- 派工 brief 暗示修改 `injectAuth()` 加 API / form 分支 — **W89-P-2 严格不动 injectAuth() 形态, 新增独立 `getAuthToken()` helper 兼容**
- 派工 brief 默认 "5 case PASS 等于无 critical/serious violations" — **实际 base 5ace8015e 上 5 路由均有真实 a11y violations, 这些是 W89-P-1 (parallel) 修复范围**

W89-P-2 处理方式:

- `axe-chats.spec.mjs` 沿用 `injectAuth()` 形态, 仅 token 来源由 env var 换成 `getAuthToken()` 共享 token
- `auth-shared-token.spec.mjs` 硬门禁只验"通过限流" (`landedOnLogin === false`), **不锁 critical/serious violations**
- 把 violations 数据写入 `__W89_P2_A11Y_REPORT__` 全局 + console, 留给 W89-P-1 cherry-pick 后转硬断言

## 真实 a11y violations (留给 W89-P-1)

W89-P-2 实测 base `5ace8015e` 上 5 路由的 critical/serious violations (mobile-comments project):

| 路由       | aria-command-name | color-contrast | nested-interactive |
|-----------|-------------------|----------------|--------------------|
| /chat     | 1                 | 6              | -                  |
| /drive    | 1                 | 11             | -                  |
| /tasks    | 1                 | 110            | 19                 |
| /meetings | 1                 | 43             | -                  |
| /knowledge| 1                 | 90             | 20                 |

派工依赖: 这些 violations 的根因修复 = W89-P-1 mobile-comments a11y violation fix (派工 brief 提到 W88-G-2 是基线调研, W89-P-1 是真修). W89-P-1 完成后:

1. cherry-pick W89-P-1 修 a11y 的 commit(s) 到本分支
2. 把 `auth-shared-token.spec.mjs:91 expect(landedOnLogin).toBe(false)` 后追加 `expect(criticalOrSerious).toEqual([])`
3. 重跑 — 期望 5 case PASS 且 0 critical/serious violations
4. memory 更新 "W89-P-1 配合完成" 段

## 主拍要点

1. **派工 brief 描述与实际不符**: 不擅自扩/不擅自缩, 据实上报 (类 20.13 实战)
2. **不动 `app/`**: 严格遵守, 限流逻辑保留 (PR 不开)
3. **`getAuthToken()` 而非改 `injectAuth()`**: 兼容 + 不破坏既有 spec
4. **硬门禁只验限流修复**: 不锁 a11y violations (留给 W89-P-1)
5. **派工 v6 §5 反馈 类 20.49**: "Playwright 多 case 必 beforeAll 共享 token" 铁律沉淀

## 5 commit 单做 + push

```bash
git add web/tests/visual/a11y/auth-shared-token.spec.mjs \
        web/tests/visual/a11y/axe-chats.spec.mjs \
        web/tests/visual/a11y/axe-config.mjs \
        memory/w89-p2-mobile-comments-rerun-2026-07-30.md

git commit -m "test(w89): mobile-comments 5 case 限流修复 (beforeAll 共享 token) (W89-P-2)

W88-G-2 报告 mobile-comments 5 case 因 login API 429 限流全失败:
- app/api/v1/auth.py:77 + 91-92 record 5 次/分/IP 限流
- 5 case 各自调 login 触发限流
- 改为 beforeAll 拿一次 token + beforeEach 注入 cookie+localStorage
- axe-config.mjs 新增 getAuthToken() helper (request.post API mode)
- axe-chats.spec.mjs 改造兼容 (不破坏既有 spec)
- auth-shared-token.spec.mjs 硬门禁 spec (5 case × 5 project = 25 PASS)
- 仅改变 web/tests/visual/a11y/ + memory/, 0 production code, 不动 app/

派工 v6 §5 反馈 类 20.49 沉淀: 'Playwright 多 case 必 beforeAll 共享 token, 避免触发后端限流'

真验证:
- docker compose dev up + curl http 200 + JWT 141 字符
- mobile-comments project 5 case 17s/each 全过, 全部 url=目标路由 (非 /login)
- 5 projects × 5 pages = 25 case 全过 (7.4m)
- axe-chats 5/5 + a11y-baseline 5/5 回归无问题

锚点 +1 守恒 (337 → 338)"

git push -u origin claude/w89-p2-mobile-comments-rerun
```

## 完整 a11y violations 数据 (待 W89-P-1 修后归零)

mobile-comments project violations (base 5ace8015e):

- `/chat`: aria-command-name (1) + color-contrast (6)  → W89-P-1 应修 aria-hidden avatar button (CSS class `.user-info el-tooltip__trigger`)
- `/drive`: aria-command-name (1) + color-contrast (11) → W89-P-1 应修 mobile drive table 灰色 secondary text
- `/tasks`: aria-command-name (1) + color-contrast (110) + nested-interactive (19) → W89-P-1 应修 trash list card button-in-button (`MobileTaskTrash.vue` 8 裸 button 历史踩坑)
- `/meetings`: aria-command-name (1) + color-contrast (43) → W89-P-1 应修 mobile meeting list 日期 + status pill
- `/knowledge`: aria-command-name (1) + color-contrast (90) + nested-interactive (20) → W89-P-1 应修 knowledge list card nested buttons + tag pill 灰底白字对比

派工 brief 已 commit 暗示 W89-P-1 会真修这些, 本任务只交付"限流修复可达性".
