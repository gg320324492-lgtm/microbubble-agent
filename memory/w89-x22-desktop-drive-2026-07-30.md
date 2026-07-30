# W89-X-22 DesktopFileCommentsView 真修 (2026-07-30)

> base ref: `a000d0bf2` (本地 main tip 实测); 分支: `claude/w89-x22-desktop-drive`; worktree: `E:\microbubble-agent\agent-w89-x22-desktop-drive`.

## 真因校核

- `DesktopFileCommentsView.vue` 修前 0 处 `route.query` / `useRoute`: `?top=1`, `?thread=1`, `?focus=1` 全被忽略。X-10 的同 viewport 四张图因此同 blob。
- dark CSS 虽有 `[data-theme="dark"]` 非 scoped 规则，但视觉 spec 只设置 Chromium `colorScheme: dark`; theme store 初始仍固定 light，组件也没有 dark className，light/dark 同 blob。
- 第一次按 brief 直接用默认 mock token 真跑会 401 并被重定向到 dashboard；已按 X-10 类 20.25 教训改用真实测试账号 token 重跑，逐张确认是文件评论页。

## 修法

- 引入 `useRoute`，初始化并监听 `route.query`；`tab` 只接受 open/all/resolved。
- `focus` 驱动 `DesktopCommentInput` auto-focus；`top` / `thread` 驱动评论区域和目标项高亮、加载后滚动。即使测试数据库暂无 id=1 评论，query variant 仍有清晰可见状态，避免零信息 baseline。
- 引入 `useThemeStore`; 根节点绑定 `theme-dark`; 没有持久化主题时把浏览器 `prefers-color-scheme: dark` 同步到 store。只复用现有 dark CSS，不新建或改全局 dark 样式。

## 真跑验证

- `SKIP_DB_SETUP=1 pytest tests/desktop_drive_x22/ -v`: **2 passed**。
- `npm --prefix web run build`: **PASS** (按项目纪律走 postbuild；随后恢复 `web/dist/`，0 dist 改动)。
- `TEST_TOKEN=<真实 xiaoqi_testbot JWT> BASE_URL=http://localhost:3000 SKIP_DB_SETUP=1 npx playwright test tests/visual/desktop/desktop_drive_comments.spec.mjs --project=desktop-comments --update-snapshots --reporter=list`: **22 passed**。
- 不带 `--update-snapshots` 稳定复跑: **22 passed**。
- baseline 文件数仍是 spec 的 22 张（不是 brief 预测的 30+；严禁为凑数改 spec）。信息量据实提升: 1280/1440/1680 的 4 query variant 从 1 个唯一 blob 提升到 3 个；1920 light/dark 已明确不同。
- 逐张 Read 抽查: list / top 橙色顶边 / thread 橙色左边 / focus 输入框态 / dark 全局深色均为真实评论页。

## 边界

- production 仅改 `web/src/views/desktop/DesktopFileCommentsView.vue`。
- 新增 `tests/desktop_drive_x22/test_route_query.py` 与 22 张 X-10 缺失的 Windows 本地 baseline。
- 未改 spec、其它业务代码、dark 全局 CSS、`app/`、`alembic/`、`nginx/`、`docker/`、`web/dist/`、`commercial/`。

## 派工 v6 §5 反馈 — 类 20.77

**DesktopFileCommentsView 真修必 route.query + dark mode className（非全 CSS 重写）**：视觉用例通过 query 声称多个 variant 时，组件必须实际读取并响应 query；dark 用例不能只依赖 Playwright colorScheme，组件主题状态必须有 class/data-theme 落点。修后必须用真实登录态逐张抽查 + hash 去重，不能把 mock-token 重定向页或同 blob 当覆盖度。
