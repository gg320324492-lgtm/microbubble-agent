# W89-P-7 visual snapshot 漂移真因查清 — 2026-07-30

> W89 第 1 批收尾 P-7 路线。任务边界：只查真因，不改 spec、production code 或 snapshot。
> base ref 实测：`3a1ab24b3`（`origin/main` 与本地 `main` 一致）。

## 1. 结论

`desktop_drive_comments` 报告的 4 case timeout **不是 snapshot 像素漂移，也不是登录、路由或评论数据加载慢**。四个 case 都精确卡在：

```text
waitForDesktopCommentsUI()
  -> page.waitForLoadState('networkidle')
```

页面的 `load` 事件已经触发，桌面评论 UI 也已经渲染；但页面在挂载后建立长期 WebSocket 通知连接，并启动健康探测/通知轮询，因而不满足该测试对 `networkidle` 的等待假设。测试直到全局 timeout 才退出，后续 selector、正文断言和 `toHaveScreenshot()` 均未执行。

因此 W89-P-4 所称“visual snapshot 漂移”需纠正为：**实时连接页面错误使用 `networkidle` 作为 UI ready 条件导致的测试等待策略阻塞**。

## 2. 当前状态与环境校核

- worktree：`E:/microbubble-agent/agent-w89-p7-visual-debug`
- branch：`claude/w89-p7-visual-debug`
- base：`3a1ab24b3`
- spec：`web/tests/visual/desktop/desktop_drive_comments.spec.mjs`
- Docker 既有主栈：`microbubble-agent-app-1` healthy，`microbubble-agent-db-1` / Redis / nginx 均在运行
- `GET http://localhost:8000/health`：HTTP 200
- `http://localhost:3000` 与 `http://localhost:5173`：未启动；spec 默认 URL 是 3000，但 W89-P-4 的真实复现场景使用 nginx `BASE_URL=http://localhost`
- 未重复启动 dev compose：`docker-compose.dev.yml` app 映射 8000，会与既有 healthy 主栈冲突；按类 20.52 复用既有栈

## 3. 4 case 真实复现

使用真实登录取得 JWT 后，按 W89-P-4 的 `desktop-chrome` project 单跑 desktop-1280 的 4 个页面：

```bash
BASE_URL=http://localhost TEST_TOKEN=<real-jwt> \
  npx playwright test \
  tests/visual/desktop/desktop_drive_comments.spec.mjs \
  --project=desktop-chrome \
  --grep 'desktop-1280' \
  --reporter=list --timeout=60000 --trace=on
```

结果：

```text
4 failed, each 60.0s
Test timeout of 60000ms exceeded.
Error: page.waitForLoadState: Test timeout of 60000ms exceeded.
"load" event fired
at waitForDesktopCommentsUI (...spec.mjs:78:14)
```

四条路径 `/drive/file/99/comments`、`?top=1`、`?thread=1`、`?focus=1` 的失败位置完全一致，尚未走到截图断言。

另做 headed 单 case：

```bash
BASE_URL=http://localhost TEST_TOKEN=<real-jwt> \
  npx playwright test \
  tests/visual/desktop/desktop_drive_comments.spec.mjs \
  --project=desktop-chrome \
  --grep 'desktop-1280.*01-list' \
  --headed --timeout=10000 --trace=on
```

结果仍在 10.1s 精确卡于 `page.waitForLoadState('networkidle')`。headed/trace 中可见页面已显示评论标题、tabs、空态和输入栏，不是白屏或路由阻塞。

调试产物（gitignored，不提交）：

- `web/test-results/desktop-desktop_drive_comm-e8414--header-tabs-列表-sticky-输入栏--desktop-chrome/trace.zip`
- 同目录 `error-context.md`
- trace 内页面 JPEG 资源

## 4. trace 网络证据

trace 显示关键页面及资源/API 都成功：

- `GET /drive/file/99/comments` → 200
- JS/CSS chunks → 200
- `GET /api/v1/auth/me` → 200
- `GET /api/v1/notifications?...` → 200
- `GET /api/v1/members` → 200
- `GET /api/v1/meetings?...` → 200
- `GET /health` → 200，并在 60s trace 中重复出现
- `GET ws://localhost/api/v1/ws/notifications?token=...` → **101，长期连接**

页面 accessibility snapshot 已包含完整桌面布局和评论 UI。这排除了：

1. **登录失败**：真实 JWT 注入，`/auth/me` 200，页面显示真实测试管理员身份。
2. **路由阻塞**：页面主路由 200，`load` 已触发，评论 View 已渲染。
3. **数据请求慢**：所见 API 均已 200；页面已进入评论空态。即使 file 99 无评论数据，也不应阻止 ready。
4. **dev server 未启**：3000/5173 确实未启，但本次与 W89-P-4 复现明确通过 `BASE_URL=http://localhost` 使用运行中的 nginx；这不是 4 个 30s timeout 的原因。若遗漏 BASE_URL，则会立即 `ERR_CONNECTION_REFUSED`，约 2.5s 失败，而非 30/60s timeout。

直接触发链：

- `NotificationBell.vue` mounted 调 `store.startWs()`、`startPolling(30000)`；
- `useNotifications.js` 建立 WebSocket，并有 heartbeat / unread-count polling；
- 页面还有健康探测请求；
- spec 在 `page.goto(..., waitUntil: 'domcontentloaded')` 后又等待 `networkidle`；
- 对实时连接页面，`networkidle` 不是可靠的业务 ready 信号。

## 5. 修法建议（留 W89+ 派修，本任务不实施）

优先建议：

1. 删除此 spec 的 `page.waitForLoadState('networkidle')`。
2. 改为等待确定的 UI 状态，例如 `.desktop-file-comments-view` 出现，且 `.dfcv-loading` 消失；评论空态或列表任一可见即 ready。
3. 视觉测试需要确定性时，在测试内 mock/abort WebSocket、通知轮询与健康探测；不要把生产实时连接的静默当作页面完成条件。
4. 保留 `page.goto(..., { waitUntil: 'domcontentloaded' })`，随后只用 locator/response 级业务条件等待。
5. 修复等待后再确认 snapshot 状态。当前 main 中未找到 `desktop_drive_comments.spec.mjs-snapshots/*.png`，所以后续可能进入“缺 baseline/生成 actual”阶段，但这与本次 timeout 是两个独立问题，不应混称为 snapshot 漂移。

不建议：简单把 timeout 从 30s 加到 60s/120s。长期连接不会因扩大 timeout 自动进入 `networkidle`，只会拉长失败时间。

## 6. 四项排查归档

| 排查项 | 结论 | 证据 |
|---|---|---|
| 登录 | 成功 | 真实 JWT；`/auth/me` 200；页面显示测试管理员 |
| 路由 | 成功 | route 200；`load` fired；评论 UI 已渲染 |
| 数据 | 非阻塞 | API 200；评论空态已显示；不是慢请求卡住 |
| dev server | nginx 可用，3000/5173 未启 | `BASE_URL=http://localhost` 复现；遗漏 BASE_URL 会立即 refused，不会形成 30s timeout |

## 7. 派工 v6 §5 反馈：类 20.55

**类 20.55：Playwright timeout 排查必查 4 件：登录 / 路由 / 数据 / dev server。对 WebSocket、SSE、polling、长轮询页面，禁止把 `networkidle` 当业务 ready 条件；必须以确定的 UI locator 或目标 API response 为准。trace 必检查持续连接与重复请求，不能把未执行到的截图断言误报为 snapshot 漂移。**

本次实战进一步证明：

- 相同外观的 timeout 可由完全不同层导致；
- trace 的失败 action 和最后一条未结束网络连接比提高 timeout 更有诊断价值；
- “页面已经渲染”与“网络完全静默”是两件事。

## 8. 边界与诚实报告

- 未改任何 spec。
- 未改 `app/`、`web/src/`、`alembic/`、`nginx/`、`docker/`、`web/dist/` 或 `commercial/`。
- 未更新/生成并提交 snapshot。
- 仅提交本 memory 文件；trace/test-results 保持 gitignored。
- 真因已明确到 `spec.mjs:78` 的 `networkidle` 等待及页面实时连接链，不编造 snapshot diff 数字。

锚点口径：base 338（`3a1ab24b3`）→ 本路线 tip +1；派工报告中出现的 342/343 与实际 base 锚点不一致，按实测 base 据实上报，不凑数。
