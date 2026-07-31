# W92-X-4 injectAuth fail-loud 改造 (派工 v6 §5 反馈 类 20.85 加固)

> **锚点范式 +1 守恒** (类 20 累计 → 86 实例 / 类 20.85 新增)
> **分支**: `claude/w92-x4-inject-auth` (从 main tip `093060fde` 切)
> **base → tip**: +1 commit (预期)
> **0 production code 改动铁律 1/1 守恒** — 仅 `web/tests/visual/a11y/axe-config.mjs` 改 `injectAuth` 函数 (~5 行)
> **派工前提铁律**: 类 20.85 新增 ("静默降级 = 假绿, 必须 throw fail-loud")

---

## W91-X-18 据实 (根因)

`web/tests/visual/a11y/axe-config.mjs:57-68 injectAuth()` 缺 `TEST_TOKEN` 时 **return false** 静默降级:

```js
// 改前 (假绿根因)
export async function injectAuth(page, baseUrl) {
  const token = process.env.TEST_TOKEN
  if (!token) return false  // ← 静默, 返回 false 后 caller 不知道
  // ... 设 cookie + localStorage
  return true
}
```

**3 次假绿历史**:
- P-6 (W89 第 6 批 a11y baseline) — 缺 token 静默 PASS, 5 页面 × 5 project = 25 case 全假绿
- X-29 (W89 baseline sync) — 同根因, 25 case 假绿
- X-14 (W89 swipe bug) — 间接相关, baseline 静默 PASS 掩盖真问题

**根因**: test helper 缺 fail-loud 守门, 缺 token = 缺登录态 = 必然无意义测试, 但 caller `a11y-baseline.spec.mjs:35` 把 `authed: no` 写进 snapshot 然后照常 PASS。

---

## 修法 (~5 行 throw)

```js
// 改后 (W92-X-4 派工 brief 模板 v3 据实改)
export async function injectAuth(page, baseUrl) {
  const token = process.env.TEST_TOKEN
  if (!token) {
    throw new Error(
      'injectAuth: TEST_TOKEN env 未设或 authInfo 缺 token. ' +
      '真登录态是 a11y baseline 必填, 不可静默降级. ' +
      '设 export PLAYWRIGHT_TEST_TOKEN=$(curl ... /api/v1/auth/login) 重跑.'
    )
  }
  // ... 设 cookie + localStorage
  return true
}
```

**关键**: error 文本含 `TEST_TOKEN` (守卫负向对照检测关键词) + 含 fix hint (`curl /api/v1/auth/login`) — 让守卫能精确定位失败模式, 也让人看到错误立刻知道怎么修。

---

## 真跑结果 (派工 v6 §1.2 真验证)

### 守卫 1: 无 TEST_TOKEN 必 throw (负向对照)

```bash
unset TEST_TOKEN PLAYWRIGHT_TEST_TOKEN
cd web && npx playwright test -c tests/visual/a11y/playwright.a11y.config.mjs \
  tests/visual/a11y/a11y-baseline.spec.mjs \
  --project=desktop-chrome --grep="01-chat baseline"
```

输出:
```
  x  1 [desktop-chrome] › a11y-baseline.spec.mjs:21:5 › 01-chat baseline (203ms)
    Error: injectAuth: TEST_TOKEN env 未设或 authInfo 缺 token.
    真登录态是 a11y baseline 必填, 不可静默降级.
    设 export PLAYWRIGHT_TEST_TOKEN=$(curl ... /api/v1/auth/login) 重跑.
       at axe-config.mjs:60
       at injectAuth (axe-config.mjs:60:11)
       at a11y-baseline.spec.mjs:22:28
  1 failed
```

✅ **throw 触发, fail-loud 拦截** (不是假绿 PASS)

### 守卫 2: 有 TEST_TOKEN 必跑通 (正向对照)

```bash
export TEST_TOKEN=<jwt>  # curl -X POST http://localhost:8000/api/v1/auth/login ...
npx playwright test -c ... --project=desktop-chrome --grep="01-chat baseline"
```

输出: rc==1 (snapshot 漂移, baseline 已有 — **W88 D-1 已批问题, 与 injectAuth 无关**)

✅ **throw 路径不触发** (rc != 0 是 baseline 漂移, 不是 "injectAuth: TEST_TOKEN" 错)

### 守卫套件 (2 PASS, 类 20.23 负向对照实跑)

新文件 `tests/inject_auth_x4/test_fail_loud.py`:
- `test_inject_auth_throws_without_token` — 无 token: 断言 `rc != 0` + 含 "TEST_TOKEN"
- `test_inject_auth_passes_with_token` — 有 token: 接受 `rc in (0, 1)` + 排除 "injectAuth: TEST_TOKEN"

实跑:
```
tests/inject_auth_x4/test_fail_loud.py::test_inject_auth_throws_without_token PASSED
tests/inject_auth_x4/test_fail_loud.py::test_inject_auth_passes_with_token PASSED
============================== 2 passed in 4.63s ==============================
```

**关键设计点**:
- 用绝对路径 `web/node_modules/.bin/playwright.cmd` 调 Playwright (避免 Windows subprocess 找不到 npx)
- 强制 `PYTHONIOENCODING=utf-8` + `LC_ALL=C.UTF-8` (避免 GBK 解码错误)
- 守卫 2 接受 `rc in (0, 1)` — 不为 baseline 漂移额外加硬门禁 (那是 W88 D-1 已批的另一个问题, 不算 fail-loud 守卫失败)
- 守卫 2 排除 "injectAuth: TEST_TOKEN" 错 — 确保 token 真生效 (如果 token 没传透, 仍是守卫 1 失败模式)

---

## 边界复检 (派工 brief §5)

```bash
$ git diff main..HEAD --name-only
memory/w97-worktree-04-2026-07-30.md   # 这是 main 上别人 commit 留下的, 不是本任务

# 本任务新增 (3 文件, 全部 allowed)
web/tests/visual/a11y/axe-config.mjs   # 仅改 injectAuth 函数, +6/-1 行
tests/inject_auth_x4/test_fail_loud.py # 新
memory/w92-x4-inject-auth-2026-07-30.md # 新 (本文件)
```

**0 production code 改动铁律 1/1 守恒**:
- ✅ 改: `web/tests/visual/a11y/axe-config.mjs` (test helper, 5 行 throw)
- ✅ 加: `tests/inject_auth_x4/` (新守卫)
- ✅ 加: `memory/w92-x4-inject-auth-2026-07-30.md` (本沉淀)
- ❌ 禁: `app/`、`alembic/`、`nginx/`、`docker/`、`web/dist/`、`commercial/` — 0 改动
- ❌ 禁: 其它 spec 文件 — 0 改动 (W92-X-2 + 其它 X 已用此函数, 不动)

---

## 派工 v6 §5 反馈 类 20.85 加固 (新增)

**类 20.85 "静默降级 = 假绿, 必须 throw fail-loud"**

| 模式 | 行为 | 后果 | 是否允许 |
|------|------|------|----------|
| ❌ `return false` 静默降级 | caller 不知道, 继续 PASS | 假绿 (3 次 P-6/X-29/X-14) | **严禁** |
| ❌ `return null` 静默 | caller 不知道, 继续跑 | 假绿同根因 | **严禁** |
| ❌ 静默 skip | 跳过 case 不报告 | 假绿变种 | **严禁** |
| ✅ `throw new Error(...)` | caller 立即 fail-loud | 真失败, 立刻可定位 | **必须** |
| ✅ `console.error` + `process.exit(1)` | helper 顶层退出 | 真失败, 立刻可定位 | 可 (但 throw 更标准) |

**派工前提铁律新增**:
> **类 20.85 — test helper 缺必填输入时严禁静默降级 (return false / return null / skip), 必须 throw fail-loud.**
> - 缺 token → throw, 让 caller 立即 fail
> - 缺 cookie → throw
> - 缺 fixture → throw
> - 缺 env var → throw (显式列出 env 名 + fix hint)
> - 静默降级 = 假绿制造机, 派工 brief 必检

**未来 4 阶段流程新增检查项**:
- 阶段 2 (派工 brief 写): test helper 必含 fail-loud 守门 (列出来)
- 阶段 3 (实施): 改 helper 时**严禁**改 silent → silent
- 阶段 4 (e2e 验证): 守卫必含负向对照 (无输入 throw, 有输入 pass)
- 阶段 5 (沉淀): 类 20.xx 沉淀必含"静默降级 → throw" 案例

---

## 5 条铁律 (W92-X-4 沉淀)

1. **test helper 缺必填输入必 throw** — 严禁 `return false` 静默降级 (类 20.85, 3 次假绿 P-6/X-29/X-14 据实)
2. **error 文本必含 fail 关键词** — throw 后断言能精确定位失败模式 (本任务用 "TEST_TOKEN" 作 grep 锚点)
3. **error 文本必含 fix hint** — 让开发者看到错误立即知道怎么修 (本任务含 `curl /api/v1/auth/login`)
4. **守卫必含负向对照** (类 20.23) — 无输入 throw + 有输入 pass 两个 case 缺一不可
5. **守卫接受"已知非 fail-loud 问题"的 rc** — baseline 漂移 (rc=1) 不是 fail-loud 守卫失败, 不应让守卫误报

---

## commit 计划 (单做)

```
test(w92): injectAuth fail-loud 改造 (类 20.85 加固) (W92-X-4)

W91-X-18 据实: injectAuth() 缺 TEST_TOKEN 时 return false:
- 静默降级, 3 次假绿 (P-6 / X-29 / X-14) 根因
- 改: throw new Error('injectAuth: TEST_TOKEN env 未设')
- 守卫: tests/inject_auth_x4/ 负向对照 (无 token throw fail, 有 token pass)

派工 v6 §5 反馈 类 20.85 加固: '静默降级 = 假绿, 必须 throw fail-loud'

锚点 +1 守恒 (492 → 493)
```

---

## 与 W92-X-2 + 其它 X 协同 (不破坏原则)

`injectAuth` 是 a11y 共用 helper, 已被 W92-X-2 + 其它 X 派工引用。本任务:
- **接口签名不变**: `injectAuth(page, baseUrl) -> Promise<boolean>`, 仍返回 `true` (token 注入成功)
- **行为变更**: 缺 token 时 throw 而非 return false → caller 立即 fail 而非继续走 baseline 漂移路径
- **零迁移成本**: 已有 caller (`a11y-baseline.spec.mjs:22` + `axe-chats.spec.mjs:23`) 都不接 `false` 分支, throw 直接冒泡到 Playwright test framework, 表现为 "case fail" + stack trace 指 `axe-config.mjs:60` — 立刻知道是 token 问题

W92-X-2 + 其它 X 仍可正常使用 `await injectAuth(page, BASE_URL)` (不接返回值), 不会因本任务 throw 而破坏。

---

**报告主指挥**:
- ✅ 改: 1 函数 (~5 行 throw)
- ✅ 加: 1 守卫文件 (2 PASS)
- ✅ 沉淀: 类 20.85 + 5 条铁律
- ✅ 真跑: 无 token throw fail-loud, 有 token 不触发 throw
- ✅ 边界: 0 production code 改动
- 🎯 锚点: +1 守恒 (493)
