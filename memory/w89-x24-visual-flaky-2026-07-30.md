# W89-X-24 visual-regression flaky 修法 (2026-07-30)

> **派工 brief v3 双锚定**: 改 spec 等待逻辑, 禁改业务代码, 派工 v6 §5 反馈类 20.79 新增。

## 真因 (W89-X-10 据实报告)

visual-regression 本质 flaky:
- diff 3-6% > 门禁 0.2% (playwright.config.js `maxDiffPixelRatio: 0.002`)
- 真因: **空态 vs 已加载数据竞态**

`waitUntil: 'networkidle'` 触发时机 = 500ms 内无新网络请求。但 Vue 子组件 mount 走异步 (路由懒加载 + chunk 解析 + onMounted + API 调用),**networkidle 触发时子组件常常处于"已 layout 但未填充数据"半挂载状态**。截图捕获的就是半挂载 DOM → diff 3-6% 远超 0.2% 门禁。

裸 `waitForTimeout(800)` 也无法解决 — Vue 子组件 mount 是事件循环驱动, 800ms 在网络慢/CPU 忙时仍不够, 在快时又过度等待导致误以为稳定。

## 修法 (W89-X-24)

```diff
- await page.goto(`${BASE_URL}${route.path}`, { waitUntil: 'networkidle' })
- await page.waitForTimeout(800)
+ await page.goto(`${BASE_URL}${route.path}`, { waitUntil: 'domcontentloaded' })
+ await page.waitForSelector(route.selector, { state: 'visible', timeout: 10_000 })
+ await page.waitForTimeout(300) // transition 收尾
```

`waitForSelector(state: 'visible')` 触发时机 = DOM 已 layout + 元素已渲染 + 父级链全部 visible = 真正的"已就绪"快照点。这是比 networkidle 更严格的等待(后者不等 visible)。

## 5 次稳定验证 (BASE_URL=http://127.0.0.1 nginx prod build)

| 路由 | RUN 1 | RUN 2 | RUN 3 | RUN 4 | RUN 5 |
|------|-------|-------|-------|-------|-------|
| /dashboard | PASS 698ms | PASS 943ms | PASS 714ms | PASS 744ms | PASS 720ms |

5/5 稳定 PASS, 无 flaky。`/dashboard` 是 9 路由中唯一在 prod build 直接挂载 mobile selector (`.mobile-dashboard`) 的, 其余路由 (`/knowledge` 等) prod build 走 desktop SPA fallback — 这是 prod build chunk 策略问题, 派工 brief 禁改业务代码不在本任务范围, 留 W89+ 调查。

## 类 20.79 新增 (派工 v6 §5 反馈 #5)

> **"visual-regression flaky 修法: 必等明确 UI locator / data-testid, 禁 networkidle 或裸 timeout"**

- 必等: `waitForSelector('.mobile-xxx', { state: 'visible' })` 或 `data-testid` 等明确 DOM 锚点
- 禁等: `networkidle` / `domcontentloaded` 单独 (DOM 已解析 ≠ 组件已 mount ≠ 数据已加载)
- 裸 timeout 不替代 locator: 800ms 慢时不够, 快时过度

## 静态 e2e 加固 (tests/visual_x24/test_stable.py)

6 个静态门禁, CI 不需 dev server 也可跑:

1. `test_spec_uses_wait_for_selector_visible` — spec 必含 `waitForSelector(state: 'visible')`
2. `test_spec_no_networkidle` — spec 代码区(去注释)必不含 `waitUntil: 'networkidle'`
3. `test_spec_no_bare_timeout_replacing_locator` — `waitForTimeout` ≤ 1 (动画收尾允许, 多于则疑退化)
4. `test_core_routes_have_selector` — 9 路由 + mobile 优先 selector 全配
5. `test_spec_docstring_records_class20_79` — docstring 必含 W89-X-24 + 类 20.79 引用
6. `test_no_business_code_modified` — spec 禁 import 业务代码 (`@/views/mobile/...`)

6/6 PASS。

## 严格边界 (派工 brief 守恒)

| 类别 | 改/加 | 不动 |
|------|-------|------|
| spec | `web/tests/visual/mobile/visual-regression.spec.mjs` (只改等待) | 其它 spec |
| 加固 | `tests/visual_x24/test_stable.py` (新) | — |
| 记忆 | `memory/w89-x24-visual-flaky-2026-07-30.md` (本文) | — |
| 业务 | — | `web/src/views/mobile/*.vue` |
| 架构 | — | `app/`, `alembic/`, `nginx/`, `docker/`, `web/dist/`, `commercial/` |

## 锚点范式

base `a000d0bf2` (W89 +0 merge-02 据实 锚点 444) → tip `<pending>` = +1 守恒 (spec 等待逻辑修法 + e2e 静态门禁 = 1 commit)

## W89+ 派工留口

- prod build chunk 策略: 为什么 `/knowledge` `/tasks` 等路由 prod build 走 desktop 而非 mobile (留 W89-A 类业务代码派工, 本任务禁改业务)
- 真 visual-regression 5 路由全跑: 需 dev server (3000), CI 维持禁用 (W76 §v77 决定), 本地 dev 跑
