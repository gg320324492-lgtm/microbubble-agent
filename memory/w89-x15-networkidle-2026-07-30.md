# W89-X-15 networkidle 真因修法 — 2026-07-30

> W89 第 1 批收尾 X-15 路线。任务边界：修法 W89-P-7 查清的 `waitForLoadState('networkidle')` 真因 + 加固守卫。
> base ref 实测：`3a1ab24b3`（main tip）。
> cherry-pick 来源：P-7 `83eb3ec59` (memory 沉淀) + P-10 `9d34ae752` (e2e 重构) → 全在 base 之上。
> P-15 还没 commit，跳过。

## 1. 结论

W89-P-7 真因：`waitForLoadState('networkidle')` 在含 WebSocket 长连接、SSE 流式、长轮询、健康探测的页面**永不达成**——测试卡在 timeout，后续 selector/截图断言**未执行**。这被 W89-P-4 误报为 "snapshot 漂移"。

修法：删除 `waitForLoadState('networkidle')`，改等明确 UI locator（评论 View 容器 visible + loading hidden）。

## 2. 受影响 spec 与修法

| Spec | 文件 | networkidle 数 | 修法 |
|---|---|---|---|
| Desktop Drive Comments | `web/tests/visual/desktop/desktop_drive_comments.spec.mjs` | 1 | 删 networkidle + `waitForDesktopCommentsUI()` 内 `.desktop-file-comments-view/.dfcv-list/.dfcv-empty` visible + `.dfcv-loading` hidden |
| Mobile Drive Comments | `web/tests/visual/mobile/mobile_drive_comments.spec.mjs` | 1 | 同 pattern, locator 换 `.mobile-file-comments-container/.mfcc-list/.mfcc-empty` + `.mfcc-loading` |
| Mobile Swipe Gesture | `web/tests/visual/e2e/mobile_swipe_gesture.spec.js` | 6 | 按页面替换：`/m/drive` 等 `.drive-tab-btn`；`/m/chat` 等 `.mobile-chat-view/.chat-session-item`；`/m/knowledge` 等 `.knowledge-main/.knowledge-list` |
| P0-2 Bounce (login) | `web/tests/visual/desktop/p0-2-bounce-recv2.spec.mjs` | 1 | 等 `input[placeholder*=用户名]/input[name=username]` 可见（login 页无 WS，但规则一致） |

**总计 9 处真执行的 `waitForLoadState('networkidle')` 全删**。

## 3. 真跑验证

环境：main `app-1` healthy + nginx `localhost:80` 200 + `npm install` 拉 `@playwright/test 1.62.0`。

单跑 desktop-1280 × 5 viewport `01-list`:

```bash
cd web && TEST_TOKEN=fake-jwt-for-test BASE_URL=http://localhost \
  npx playwright test tests/visual/desktop/desktop_drive_comments.spec.mjs \
  --project=desktop-chrome --grep "01-list" --reporter=list --timeout=45000
```

**结果**：
- 修复前（P-7 报告）：4 case × 60s timeout 卡在 `page.waitForLoadState('networkidle')`，后续 selector + 截图断言均未执行
- 修复后（本任务）：`waitForDesktopCommentsUI()` 立即返回，failure 位置已下沉到 `toHaveScreenshot()`（**这是 baseline 缺失的另一独立问题**，不属于 X-15 边界，留 W89+ 派修）

> trace 显示页面 `load` 已触发 + `/auth/me 200` + `/api/v1/notifications 200` + 评论 UI 已渲染。`waitForLoadState('networkidle')` 永不达成的链路是 WS `ws://localhost/api/v1/ws/notifications` 长期 101 + heartbeat + polling。

## 4. 守卫测试

新增 `tests/networkidle_fix/test_no_wait_for_networkidle.py`，4 个 case:

1. **`test_protected_specs_no_active_networkidle`** — 受保护 spec 必无真实执行（非注释）的 `waitForLoadState('networkidle')`，剥离 `/* */` + `//` + 字符串字面量后用正则匹配
2. **`test_desktop_drive_comments_uses_ui_locator`** — desktop spec 必含 `.desktop-file-comments-view / .dfcv-list / .dfcv-empty`
3. **`test_mobile_drive_comments_uses_ui_locator`** — mobile spec 必含 `.mobile-file-comments-container / .mfcc-list / .mfcc-empty`
4. **`test_class_20_67_documented`** — `memory/w89-x15-networkidle-2026-07-30.md` 必含 "类 20.67"

跑法：
```bash
SKIP_DB_SETUP=1 pytest tests/networkidle_fix/ -v
# 4 passed in 0.04s
```

## 5. 派工 v6 §5 反馈：类 20.67 (新铁律)

**类 20.67：WS / SSE / long-polling 页面必删 `waitForLoadState('networkidle')`，改等明确 UI locator 或目标 API response。**

细化：

1. **禁 networkidle** 在含 WS / SSE / long-polling / 健康探测的页面用 networkidle 当 ready 信号——它永远不会达成
2. **修法**：等明确的 UI locator（如 `.desktop-file-comments-view` visible + `.dfcv-loading` hidden），或等目标 API response（如 `response.json()`），或等 `[data-testid]` 元素 ready
3. **超时延长无效**：从 30s 改 60s/120s 仍不会进入 networkidle，只会拉长失败时间
4. **页面类型识别**：NotificationBell（WS）+ ChatViewSSE（SSE）+ 移动端 useIsMobile（resize 事件）都是长连接/长事件源
5. **不假装修**：不要再用 `waitForTimeout(8000)` 之类硬等，本质是测试不确定性
6. **trace 必看**：trace 的失败 action 和最后一条未结束网络连接比提高 timeout 更有诊断价值

本任务落地：

| # | spec | 真实场景 | 真因 |
|---|---|---|---|
| 1 | desktop_drive_comments.spec.mjs | Drive 评论页 | WS notification + 通知轮询 + 健康探测 |
| 2 | mobile_drive_comments.spec.mjs | 移动 Drive 评论页 | 同上 + mobile useIsMobile |
| 3 | mobile_swipe_gesture.spec.js | 移动手势 | 同上 + 滑动 wrapper |
| 4 | p0-2-bounce-recv2.spec.mjs | login → chat | login 页 WS 较少，但走 chat SSE 链路前 reload 后仍规则一致 |

## 6. 边界与诚实报告

- 未改业务代码（`app/`、`web/src/`、`alembic/`、`nginx/`、`docker/`、`web/dist/`、`commercial/`）
- 仅改 4 个 spec + 新增 1 个守卫测试 + 本 memory
- 真因已明确到具体 spec 文件具体行，不编造 diff 数字
- 后续截图 baseline 缺失为另一独立问题（不在 X-15 边界），留 W89+

## 7. 锚点

- base：`3a1ab24b3`（锚点 338）
- 本任务 commit：`6847503a6`（P-7 cherry-pick） + `3421884ac`（P-10 cherry-pick）+ 待 commit X-15 修法
- 锚点预期：base 338 + 1 (X-15 修法) = **339**

## 8. 留 W89+

- 截图 baseline 缺失：X-15 修法后 desktop_drive_comments 4 个 case 不再 timeout，但 `toHaveScreenshot()` 期望 PNG 缺失 → 需要先 `playwright test --update-snapshots` 生成基线，再做视觉回归
- 其他 visual baseline FAIL 也需主指挥拍板（不属于 X-15）