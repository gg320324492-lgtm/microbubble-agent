# W89-P-8 visual 全 sweep 失败清单 — 2026-07-30

> W89 第 1 批收尾 P-8 路线。任务边界：全量执行默认 Playwright visual 配置，只列 PASS / FAIL / SKIP，不改 spec、production code 或 snapshot。
> 派工 v6 §5 反馈类 20.56：**visual sweep 必只列 FAIL，不擅自动 baseline；无 baseline 时普通 Playwright 运行写出的 actual 候选也必须清理，不能误提交为获批 baseline。**

## 1. 基线、worktree 与环境校核

- worktree：`E:/microbubble-agent/agent-w89-p8-visual-sweep`
- branch：`claude/w89-p8-visual-sweep`
- local `main`：`3a1ab24b37313785ad9a84fbd620fabe09da6f6c`
- `git ls-remote origin refs/heads/main`：同为 `3a1ab24b37313785ad9a84fbd620fabe09da6f6c`
- base commit 简写：`3a1ab24b3`
- frontend dependencies：`npm ci`，1140 packages 安装成功
- 浏览器运行目标：`BASE_URL=http://127.0.0.1`
- 登录态：每次运行前通过真实 `xiaoqi_testbot` 登录取得 JWT；报告中不保存 token

### Docker 据实结果

按 brief 原命令尝试：

```text
docker compose -f E:/microbubble-agent/agent-w89-p8-visual-sweep/docker-compose.dev.yml up -d app db
```

结果未新起 P-8 dev stack：worktree 中没有 `.env`，Compose 直接报 `env file .../.env not found`。同时宿主机已有同项目主栈占用 `8000`。按 W89-P-4 类 20.52 的已沉淀纪律，没有停止或覆盖其他 agent / 主栈容器，而是复用现有真环境：

```text
microbubble-agent-app-1  running  healthy
microbubble-agent-db-1   running  healthy
GET http://127.0.0.1:8000/health -> HTTP 200
GET http://127.0.0.1/             -> HTTP 200
```

因此本次是**真实 Docker + nginx + API 环境 sweep**，但不是“P-8 worktree 自己新起一套 dev compose”；此偏差不隐藏。

## 2. spec 数量校核：brief 的“剩 22 spec”与实测不符

### 文件系统

`web/tests/visual/**/*.spec.mjs` 实际有 **39 个 spec 文件**。

### 默认 Playwright 配置真实发现

```text
npx playwright test --list
Total: 232 tests in 35 files
```

默认 `web/playwright.config.js` 的 5 个 project 实际发现：

| Project | case 数 |
|---|---:|
| `mobile-iphone14` | 74 |
| `desktop-chrome` | 100 |
| `harmonyos-arkweb` | 6 |
| `mobile-comments` | 30 |
| `desktop-comments` | 22 |
| **合计** | **232** |

有 4 个文件存在于 visual 目录但不被默认 project `testMatch` 发现：

1. `a11y/a11y-baseline.spec.mjs` — 需 a11y 专用 config
2. `a11y/axe-chats.spec.mjs` — 需 a11y 专用 config
3. `local-only/pwa-manifest.spec.mjs` — 默认 project 无匹配规则
4. `pwa/sw-lifecycle-2026-07-22.spec.mjs` — 默认 project 无匹配规则

结论：W89-P-4 的“还剩约 22 visual spec”是估算，不是当前配置物证。本任务没有擅自裁成 22 个，而是执行默认配置发现的 **35 spec / 232 case**。

## 3. 权威执行结果

执行语义：

```bash
BASE_URL=http://127.0.0.1 TEST_TOKEN=<fresh-jwt> \
  npx playwright test --reporter=list
```

同时附加 JSON reporter 只为准确汇总，不改变测试语义；**没有**传 `--update-snapshots`。

- 运行时长：`2025152 ms`，Playwright 汇总 **33.8 分钟**
- exit code：`1`
- 总 case：**232**
- PASS：**74**
- FAIL：**136**
- SKIP：**22**
- flaky：**0**
- 守恒：`74 + 136 + 22 = 232`

### FAIL 分类

| 分类 | 数量 | 说明 |
|---|---:|---|
| snapshot 类 | **113** | **113/113 全是 baseline 不存在**；真实像素 diff 漂移为 **0** |
| timeout | **13** | selector / login locator / model response / 30s test timeout |
| 其它 | **10** | UI 元素、断点、badge、204 JSON、429、DOM/tab、dark token 断言 |
| **FAIL 合计** | **136** | `113 + 13 + 10` |

## 4. 35 spec 逐项结果

| Spec | Project(s) | PASS | FAIL | SKIP | FAIL 分类 |
|---|---|---:|---:|---:|---|
| `mobile/drive-mobile-feed-2026-07-22.spec.mjs` | mobile-iphone14 | 2 | 5 | 2 | timeout 5 |
| `mobile/drive-mobile-routing-2026-07-22.spec.mjs` | mobile-iphone14 | 5 | 1 | 0 | timeout 1 |
| `mobile/drive-v2-integration-2026-07-22.spec.mjs` | mobile-iphone14 | 5 | 2 | 1 | 其它 2 |
| `mobile/mobile_drive_comments.spec.mjs` | mobile-iphone14 30 + mobile-comments 30 | 0 | 60 | 0 | snapshot 缺 baseline 60 |
| `mobile/mobile-ux-v3-dark-2026-07-24.spec.mjs` | mobile-iphone14 | 6 | 1 | 0 | 其它 1 |
| `mobile/mobile-ux-v3-idb-2026-07-24.spec.mjs` | mobile-iphone14 | 5 | 0 | 0 | — |
| `mobile/visual-regression.spec.mjs` | mobile-iphone14 | 0 | 9 | 0 | snapshot 缺 baseline 9 |
| `desktop/chat-append-message-404-fix.spec.mjs` | desktop-chrome | 0 | 1 | 0 | timeout 1 |
| `desktop/chat-login-real-2026-07-13.spec.mjs` | desktop-chrome | 0 | 1 | 0 | 其它 1 |
| `desktop/chat-login-vite-dev-2026-07-13.spec.mjs` | desktop-chrome | 0 | 1 | 0 | 其它 1 |
| `desktop/chat-qa-comprehensive-2026-07-13.spec.mjs` | desktop-chrome | 1 | 0 | 0 | — |
| `desktop/chat-session-persistence-2026-07-01.spec.mjs` | desktop-chrome | 6 | 0 | 0 | — |
| `desktop/chat-three-mode-2026-07-13.spec.mjs` | desktop-chrome | 5 | 1 | 0 | timeout 1 |
| `desktop/chat-topbar-6-themes.spec.mjs` | desktop-chrome | 0 | 0 | 18 | 全部登录重定向 skip，未到 snapshot |
| `desktop/desktop_drive_comments.spec.mjs` | desktop-chrome 22 + desktop-comments 22 | 0 | 44 | 0 | snapshot 缺 baseline 44 |
| `desktop/drive-folder-cascade-delete-2026-07-11.spec.mjs` | desktop-chrome | 2 | 0 | 0 | — |
| `desktop/drive-folder-delete-404-2026-07-10.spec.mjs` | desktop-chrome | 3 | 1 | 0 | 其它 1 |
| `desktop/drive-folder-nesting-2026-07-22.spec.mjs` | desktop-chrome | 5 | 1 | 0 | 其它 1 |
| `desktop/drive-selected-folder-ref-2026-07-14.spec.mjs` | desktop-chrome | 1 | 0 | 0 | — |
| `desktop/drive-team-shared-bug-A-diagnose.spec.mjs` | desktop-chrome | 1 | 0 | 0 | — |
| `desktop/drive-team-shared-debug-2026-07-12.spec.mjs` | desktop-chrome | 1 | 0 | 0 | — |
| `desktop/drive-team-shared-final-verify-2026-07-12.spec.mjs` | desktop-chrome | 1 | 0 | 0 | — |
| `desktop/drive-team-shared-isolation-pr6p19.spec.mjs` | desktop-chrome | 3 | 0 | 0 | — |
| `desktop/drive-team-shared-sub-folders-verify-2026-07-12.spec.mjs` | desktop-chrome | 1 | 0 | 0 | — |
| `desktop/grade-tag-extension-2026-07-01.spec.mjs` | desktop-chrome | 3 | 0 | 1 | — |
| `desktop/kb-monitor-d5-2026-06-30.spec.mjs` | desktop-chrome | 0 | 2 | 0 | 其它 1 + timeout 1 |
| `desktop/office-preview-sandbox-regression.spec.mjs` | desktop-chrome | 1 | 0 | 0 | — |
| `desktop/p0-2-bounce-recv2.spec.mjs` | desktop-chrome | 1 | 0 | 0 | — |
| `desktop/recording-cancel-rollback.spec.mjs` | desktop-chrome 2 + harmonyos 2 | 3 | 1 | 0 | timeout 1 |
| `desktop/recording-harmonyos-ua.spec.mjs` | desktop-chrome 1 + harmonyos 1 | 2 | 0 | 0 | — |
| `desktop/recording-mime-fallback.spec.mjs` | desktop-chrome 3 + harmonyos 3 | 3 | 3 | 0 | timeout 3 |
| `desktop/task-action-buttons-2026-07-13.spec.mjs` | desktop-chrome | 3 | 2 | 0 | 其它 2 |
| `desktop/verify-dutonghe-folder.spec.mjs` | desktop-chrome | 1 | 0 | 0 | — |
| `desktop/verify-folder-tree-threestates-2026-07-12.spec.mjs` | desktop-chrome | 3 | 0 | 0 | — |
| `desktop/verify-team-shared-nested.spec.mjs` | desktop-chrome | 1 | 0 | 0 | — |

## 5. snapshot 类 FAIL：113 个，全部是“缺 baseline”而非像素漂移

仓库 base 中：

```text
git ls-files 'web/tests/visual/**/*-snapshots/*'
# 空输出
```

Playwright 报错签名统一为：

```text
Error: A snapshot doesn't exist at ... , writing actual.
```

没有任何一例 `Screenshot comparison failed`，所以当前不能声称“有 113 处视觉漂移”；准确口径是 **113 个 snapshot case 没有已提交 baseline**。

### 5.1 `mobile/mobile_drive_comments.spec.mjs` — 60 FAIL

该 spec 被两个 project 重复发现：

- `mobile-iphone14`：30 case
- `mobile-comments`：30 case

每个 project 的 30 case 都是：

- 7 viewport × 4 页面 = 28
  - viewport：`iphone-se` / `iphone-12` / `iphone-14-promax` / `ipad` / `galaxy-s20` / `pixel-5` / `oneplus-8`
  - 页面：`01-list` / `02-top` / `03-thread` / `04-input`
- `iphone-12-01-list-dark`
- `iphone-12-05-longpress-menu`

共 `30 × 2 = 60` 个缺 baseline FAIL。

### 5.2 `mobile/visual-regression.spec.mjs` — 9 FAIL

缺 baseline 的 9 路由：

1. `01-dashboard`
2. `06-knowledge`
3. `03-chat`
4. `04-tasks`
5. `05-meetings`
6. `07-settings`
7. `08-workspace-projects`
8. `09-workspace-members`
9. `10-project-stats`

### 5.3 `desktop/desktop_drive_comments.spec.mjs` — 44 FAIL

该 spec 被两个 project 重复发现：

- `desktop-chrome`：22 case
- `desktop-comments`：22 case

每个 project 的 22 case 都是：

- 5 viewport × 4 页面 = 20
  - viewport：`desktop-1280` / `desktop-1440` / `desktop-1680` / `desktop-1920` / `desktop-2560`
  - 页面：`01-list` / `02-top` / `03-thread` / `04-input`
- `desktop-1920-01-list-dark`
- `desktop-1440-05-sticky-input`

共 `22 × 2 = 44` 个缺 baseline FAIL。

### 与 W89-P-7 的关系

W89-P-7 在 `BASE_URL=http://localhost` 下证明 `desktop_drive_comments` 会因 WebSocket 101 + polling 卡在 `networkidle`，尚未走到截图。本次按 verify skill 使用 `http://127.0.0.1`，通知 WebSocket 返回 404，`networkidle` 得以结束，44 case 继续走到 `toHaveScreenshot()` 后暴露缺 baseline。

两份结论不冲突：

- `localhost` 环境：先被实时连接等待策略阻塞；
- `127.0.0.1` 环境：等待阻塞未出现，随后暴露 baseline 缺失；
- host 不同导致 WS 行为不同，本身也是后续修复/基线生成前必须统一的环境条件。

## 6. timeout FAIL：13 个

### Mobile Drive selector timeout — 6

1. `mobile/drive-mobile-feed-2026-07-22.spec.mjs` D：等待 `.mobile-drive-view, .drive-page, .desktop-drive-view`，15s timeout
2. 同 spec E：等待 `.drive-tab-btn, .drive-page, .desktop-drive-view`，15s timeout
3. 同 spec G：等待 Drive view，15s timeout
4. 同 spec H：等待 Drive view，15s timeout
5. 同 spec I：等待 Drive view，15s timeout
6. `mobile/drive-mobile-routing-2026-07-22.spec.mjs` A：等待 `.mobile-drive-view, .drive-page`，15s timeout

### Chat timeout — 2

7. `desktop/chat-append-message-404-fix.spec.mjs`：在 `/login` 等 `input[name="username"]`，全局 30s timeout
8. `desktop/chat-three-mode-2026-07-13.spec.mjs` D：deep mode `page.evaluate` 超过默认 30s；spec 内 fetch AbortController 180s 不能覆盖 Playwright case 的 30s 上限

### KB monitor timeout — 1

9. `desktop/kb-monitor-d5-2026-06-30.spec.mjs` 第二 case：等待并点击 `KB 入库监控` tab，30s timeout

### HarmonyOS project login locator timeout — 4

10. `desktop/recording-cancel-rollback.spec.mjs` 的 harmonyos project：等待 `input[name="login-username"]`，30s timeout
11. `desktop/recording-mime-fallback.spec.mjs` iOS Safari case 的 harmonyos project：同一 login locator timeout
12. 同 spec desktop Chrome MIME case 的 harmonyos project：同一 login locator timeout
13. 同 spec老 WebView case 的 harmonyos project：同一 login locator timeout

对照：上述 recording case 在 `desktop-chrome` project 均 PASS，说明是 harmonyos project + 当前登录页 locator/渲染组合问题，不应擅自归为 production regression。

## 7. 其它 FAIL：10 个

1. `mobile/drive-v2-integration-2026-07-22.spec.mjs` B：`.drive-fab` 10s 内不存在，ActionSheet 上传链未进入
2. 同 spec E：团队 tab 找不到刚上传的 team-root 文件，预期 `true`、实际 `false`
3. `mobile/mobile-ux-v3-dark-2026-07-24.spec.mjs` F：iPhone 主流宽度断点预期 `sm`、实际 `xs`（复现 W89-P-4 已知点）
4. `desktop/chat-login-real-2026-07-13.spec.mjs`：切 balanced 后 badge 仍为 `fast qwen3:8b ...`，mode 断言失败
5. `desktop/chat-login-vite-dev-2026-07-13.spec.mjs`：同样 balanced badge 仍为 fast
6. `desktop/drive-folder-delete-404-2026-07-10.spec.mjs` C：DELETE 204 No Content 后仍执行 `delResp.json()`，报 `Unexpected end of JSON input`
7. `desktop/drive-folder-nesting-2026-07-22.spec.mjs` F：L7 创建连续遇到 429，`l7_id` 仍为 null
8. `desktop/kb-monitor-d5-2026-06-30.spec.mjs` 第一 case：预期 3 个 `.el-tabs__item`，实际 0
9. `desktop/task-action-buttons-2026-07-13.spec.mjs` dark-orange：预期 neutral `rgba(144,147,153,0.04)`，实际 `rgba(168,170,176,0.04)`
10. 同 spec dark-ocean：同一 dark neutral token 差异

## 8. SKIP：22 个

### 数据/功能条件 skip — 4

1. `mobile/drive-mobile-feed-2026-07-22.spec.mjs` B：testbot recent 为空，无法验字段
2. 同 spec F：运行时走 desktop fallback，无 mobile FAB
3. `mobile/drive-v2-integration-2026-07-22.spec.mjs` H：mobile 尚无 desktop specialView nodes
4. `desktop/grade-tag-extension-2026-07-01.spec.mjs` P0-2：mobile members 未渲染 `.member-info .el-tag`

### `chat-topbar-6-themes` 全矩阵 skip — 18

`orange/ocean/forest × light/dark × desktop/tablet/mobile = 18`，全部因 `.chat-header` 不存在（登录重定向）而调用 `test.skip()`；因此这 18 case **没有验证视觉，也没有形成 snapshot FAIL**。

## 9. PASS：74 个（按 spec 详细归档）

- `mobile/drive-mobile-feed`：A schema 200；C 无 token 401（2）
- `mobile/drive-mobile-routing`：starred / recent / team query；trash fallback；desktop viewport fallback（5）
- `mobile/drive-v2-integration`：登录与四 tabs；starred；recent；mobile-feed；mobile/dashboard（5）
- `mobile/mobile-ux-v3-dark`：系统 dark；手动 toggle + localStorage；long press + vibrate；移动取消；横屏；useIsMobile 响应（6）
- `mobile/mobile-ux-v3-idb`：IDB 写读；跨页；离线重连；离线队列 flush；storage quota（5）
- `desktop/chat-qa-comprehensive`：6 题 × 3 mode 的单一综合 case（1）
- `desktop/chat-session-persistence`：A/B/C/D/E + 删除后不复活 I（6）
- `desktop/chat-three-mode`：A/B/C/E/F；仅 D timeout（5）
- `desktop/drive-folder-cascade-delete`：A/B（2）
- `desktop/drive-folder-delete-404`：A/B/D（3）
- `desktop/drive-folder-nesting`：A/B/C/D/E（5）
- `desktop/drive-selected-folder-ref`（1）
- `desktop/drive-team-shared-bug-A-diagnose`（1）
- `desktop/drive-team-shared-debug`（1）
- `desktop/drive-team-shared-final-verify`（1）
- `desktop/drive-team-shared-isolation-pr6p19`：API / UI 隔离 / upload dialog（3）
- `desktop/drive-team-shared-sub-folders`（1）
- `desktop/grade-tag-extension`：P0-1 / P0-3 / P0-4（3）
- `desktop/office-preview-sandbox-regression`（1）
- `desktop/p0-2-bounce-recv2`（1）
- `desktop/recording-cancel-rollback`：desktop 两 case + harmonyos getUserMedia timeout case（3）
- `desktop/recording-harmonyos-ua`：desktop + harmonyos project（2）
- `desktop/recording-mime-fallback`：desktop project 三 case（3）
- `desktop/task-action-buttons`：light-orange / light-ocean / complete-btn regression（3）
- `desktop/verify-dutonghe-folder`（1）
- `desktop/verify-folder-tree-threestates`：empty / loading / error（3）
- `desktop/verify-team-shared-nested`（1）

以上合计 **74 PASS**。

## 10. 主指挥拍板建议：当前不直接 update baseline

### 当前没有可称为“符合预期的真像素漂移”case

- snapshot FAIL 113 个全部是**缺 baseline**，不是 expected/actual 像素差。
- `chat-topbar-6-themes` 18 个视觉 case 全 skip，没有验证目标 UI。
- 多个非 snapshot case 仍有 selector、mode、rate-limit、tab/DOM 和 host-sensitive WebSocket 问题。

因此本任务不建议直接跑全局：

```text
npx playwright test --update-snapshots
```

它会把环境差异、登录重定向、空态或未确认页面一次性接受为 baseline，违反双锚定纪律。

### 可留给主指挥逐组审阅的 baseline 候选

只有以下三组真正走到了 `toHaveScreenshot()`：

1. `mobile/mobile_drive_comments.spec.mjs` — 30 逻辑 case，但默认配置重复为两个 project / 60 文件
2. `mobile/visual-regression.spec.mjs` — 9 case
3. `desktop/desktop_drive_comments.spec.mjs` — 22 逻辑 case，但默认配置重复为两个 project / 44 文件

拍板前必须先决定：

- canonical project 是专用 `mobile-comments` / `desktop-comments`，还是通用 `mobile-iphone14` / `desktop-chrome`；否则会保留双份近似 baseline；
- baseline 的 canonical host 是 `localhost` 还是 `127.0.0.1`；两者当前 WebSocket 行为不同；
- 先修 P-7 的 `networkidle` 等待策略，还是在测试内稳定 mock/abort 实时连接；
- 逐张人工确认页面不是登录页、空白页、错误页或意外空态。

建议后续使用**按 spec + project 的 scoped 命令**，不要全局更新；本任务不执行这些命令。

## 11. 边界复检与产物清理

普通 Playwright 在 baseline 不存在时会把 actual PNG 写进 `*-snapshots/`，即使没有 `--update-snapshots`。本次运行产生的候选已全部删除：

- `web/tests/visual/mobile/mobile_drive_comments.spec.mjs-snapshots/`
- `web/tests/visual/mobile/visual-regression.spec.mjs-snapshots/`
- `web/tests/visual/desktop/desktop_drive_comments.spec.mjs-snapshots/`
- `web/tests/visual/desktop/screenshots/*.png`
- `web/test-results/`
- `web/playwright-report/`

清理后：

```text
git status --short -- web/tests/visual
# 空输出

git status --short
# 仅本报告写入前为空；提交时只 add 本 memory 文件
```

边界守恒：

- 未改任何 spec
- 未改任何 baseline snapshot
- 未改 `app/`、`web/src/`、`alembic/`、`nginx/`、`docker/`、`web/dist/` 或 `commercial/`
- 未执行 `--update-snapshots`
- 最终只提交 `memory/w89-p8-visual-sweep-failures-2026-07-30.md`

## 12. 类 20.56 沉淀

**类 20.56：visual sweep 必只列 FAIL，不擅自动 baseline。进一步补强：仓库无 baseline 时，即使不带 `--update-snapshots`，Playwright 仍会写 actual 候选；验证 agent 必在汇总后清理这些候选并用 `git status` 证明 baseline 目录零改动。snapshot FAIL 必区分“缺 baseline”与“像素漂移”，两者不能混报。**

## 13. 锚点口径

- 实测 base commit：`3a1ab24b3`（origin/main 与 local main 一致）
- 本路线产出：仅本 memory commit，commit 增量 `+1`
- 当前 base 对应历史文档锚点为 338；brief 中同时出现 `342 → 343` 与 `338 → 339` 两套数字，当前分支无法从 git 物证独立证明 342，因此不凑数、不伪造全局锚点。主指挥合并时按实际合并顺序统一结算。
