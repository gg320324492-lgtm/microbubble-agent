# W89-X-10 visual 113 缺 baseline 拍板重 sync (2026-07-30)

> **主基调**: W89-P-8 报告 35 spec / 232 case 实跑, 113 baseline FAIL, 集中 3 个 spec.
> 本任务拍板 canonical project + host, 逐 spec 重 sync, **据实上报 2 个真缺陷 + 1 个治理冲突**.
> base ref: `3a1ab24b3` (main tip, 实测 `git ls-remote origin main` = `3a1ab24b3...` 一致, 类 20.32 守恒).
> 分支: `claude/w89-x10-visual-baseline`, worktree `E:\agent-w89-x10-visual-baseline`.

---

## 1. 113 缺 baseline case 精确对账 (算术闭合)

P-8 只报总数 113 + 3 个 spec 名, 本任务**实测逐 spec 逐 project 对账**, 算术精确闭合:

| spec | case/project | 匹配 project | 小计 |
|------|--------------|--------------|------|
| `desktop/desktop_drive_comments.spec.mjs` | 22 (5vp×4pg + dark + sticky) | `desktop-chrome` + `desktop-comments` | 22×2 = **44** |
| `mobile/mobile_drive_comments.spec.mjs` | 30 (7vp×4pg + dark + longpress) | `mobile-iphone14` + `mobile-comments` | 30×2 = **60** |
| `mobile/visual-regression.spec.mjs` | 9 (9 routes) | `mobile-iphone14` | **9** |
| | | **总计** | **113** ✅ |

**根因 = 双 project 匹配重复计数** (P-8 拍板建议 #1 "决定 canonical project 避免重复 baseline" 得到实测确认):
- `playwright.config.js` `desktop-chrome.testMatch = /desktop\/.*\.spec\.mjs/` (宽) 与 `desktop-comments.testMatch = /desktop\/desktop_drive_comments\.spec\.mjs$/` (窄) **同时命中**同一 spec
- `mobile-iphone14.testMatch = /mobile\/.*\.spec\.mjs/` 与 `mobile-comments` 同理
- 所以 44 / 60 不是 44 / 60 张**独立**截图, 而是 22 / 30 张 × 2 套重复 baseline

**git 史实测**: `git ls-files | grep visual` → 仅 25 个 a11y `.txt`, **0 个 PNG baseline 入 git**. 113 全缺不是"漂移", 是**从未存在**.

---

## 2. canonical 决策记录 (遵循主指挥 brief, 不擅自扩)

| 项 | 决策 | 依据 |
|----|------|------|
| canonical project | `desktop-comments` (桌面评论) / `mobile-iphone14` (visual-regression) | brief 指定 desktop-chrome + mobile-iphone14 为 canonical; 但 `desktop_drive_comments` 专用 project `desktop-comments` 才带正确 1280×800 + UA, `desktop-chrome` 是宽匹配兜底 → **专用优先, 宽匹配不再生成第 2 套** |
| host | `localhost` 统一 | brief 指定; `BASE_URL` 默认已是 `http://localhost:3000`, 未覆盖 |
| mock 实时连接 (WS) 修复 | **留 W89+** | brief 明示 |
| 逐 spec 更新 | 只做 3 个集中 spec | brief 明示 |
| 逐张确认非登录/空白/错误页 | **执行, 且拦下 2 个真缺陷** | brief step 3 item 5 — 见 §4 |

**环境**: `web/node_modules` 用 junction 链主仓库 (worktree 无 node_modules); vite dev server `npx vite --port 3000 --strictPort` 实起 (port 3000 原本 down, port 80 nginx + app:8000 healthy).

---

## 3. 逐 spec 重 sync 结果

| spec | project | --update-snapshots | 复跑验证 (无 update) | 结论 |
|------|---------|-------------------|---------------------|------|
| `desktop_drive_comments` | `desktop-comments` | 22 PASS | **22 PASS × 2 连跑** | ✅ **稳定, 已 commit** |
| `mobile_drive_comments` | `mobile-comments` | **0 PASS / 4 FAIL (iphone-se 抽样)** | — | ❌ **production bug 阻断, 见 §4.2** |
| `visual-regression` | `mobile-iphone14` | 9 PASS | **3~4 FAIL 每次不同** | ⚠️ **本质 flaky, 见 §4.3** |

---

## 4. 据实上报 (派工 v6 §1.2 真验证 — 3 项)

### 4.1 mock-token 静默重定向 → 22 张假 baseline (本任务自查拦下, 已废弃重生成)

**第一轮**用 spec 默认 `TEST_TOKEN || 'mock-token'` 跑, 22 + 9 全 PASS "全绿". 但 brief step 3 item 5 要求逐张确认 → **Read PNG 发现 `desktop-1280-01-list` 截的是仪表盘, 不是评论页**.

实测 probe:
```
final URL : http://localhost:3000/dashboard      ← 期望 /drive/file/99/comments
dfcv nodes: 0
console   : 401 Unauthorized ×4 + [DesktopComments] batchResolveMembers failed 401
```
`mock-token` → 后端 401 → router 守卫重定向 `/dashboard`.

**visual-regression 更露骨**: 9 张 baseline **md5 只有 2 个唯一值**, 8 张**字节完全相同** — 正是 spec 头注释警告的历史坑原文:
> "仅 cookie 注入会导致 router 守卫拦截重定向 /login (历史踩坑, 3 张旧 baseline 字节数完全相同 = 登录页)"

**修法**: 真登录拿 token (`POST /api/v1/auth/login` `xiaoqi_testbot` / `testbot_pass_2026`, 来源 `scripts/test_pr6_p7_dedup.py:31-38`) → 10/10 路由不再重定向 → `rm -rf` 全部 mock-token baseline 重生成 → 9 张 md5 **9/9 唯一** + desktop 复检截到真评论页 (面包屑「文件评论」+ 未解决/全部/已解决 tabs + emoji bar + 输入框).

**类 20.25 "全绿是可疑信号" 再次实战命中** — 全绿恰是 baseline 全是同一张重定向页.

### 4.2 `MobileFileCommentsView.vue:124` production bug — 60 case 全阻断 (0 production code 铁律, 不修)

`mobile_drive_comments` 60 case **无法生成 baseline**, 页面白屏 `bodyText.length = 0`:
```
PAGEERROR: useMobileKeyboard is not defined
```
- `web/src/views/mobile/MobileFileCommentsView.vue:124` → `const keyboard = useMobileKeyboard()`
- **该文件 0 处 import 语句** (`grep "import.*useMobileKeyboard"` → 无)
- composable 真实存在于 `web/src/composables/useMobileKeyboard.ts` → **纯缺 import**
- 4 个 query 变体 (`` / `?top=1` / `?thread=1` / `?focus=1`) 全部 `#app` innerHTML = 245 字节空壳

**spec 守卫工作正常**: `expect(bodyText.length).toBeGreaterThan(10)` 在 `toHaveScreenshot` **之前**, 4/4 FAIL 且**不写空白 baseline** — 这是 spec 设计正确, 不是 spec 缺陷.

**不修**: 属 `web/src/`, brief 明令禁改 + 0 production code 铁律. **留 W89+ 派 1 行 import 修复**, 修完 60 case 才可能生成.

### 4.3 `visual-regression` 9 case 本质 flaky (async 数据竞态, 非视觉回归)

warm cache 重生成 9 PASS 后, **连跑 2 次: 4 FAIL / 3 FAIL, 失败集合每次不同**. diff ratio 3~6% (门禁 0.2%).

读 diff PNG 定因: baseline 截到**空态**「暂无任务」, 复跑截到**已加载真数据** (陈天祥 / 文献调研 / 英语上机考试 3 条任务). 即 `waitForTimeout(800)` 固定等待跑不过异步数据加载 → **数据竞态, 不是视觉退化**.

稳定化需改 spec 等待逻辑 (`waitForSelector` 数据就绪), 属 brief 明令"**绝对不动 spec 内容**" → **不改, 留 W89+**.

### 4.4 22 张 baseline 实际只有 5 张唯一图 — query 参数从未实现 (commit 后 blob 去重发现)

commit 后 `git ls-tree` blob 去重: **22 张 baseline 只有 5 个唯一 blob**.

分组结果 — 同 viewport 的 4 个 "页面" 完全同一张图:
```
9aa7f9  desktop-1280-{01-list, 02-top, 03-thread, 04-input}     ← 4 张同 blob
b17f2d  desktop-1440-{01-list, 02-top, 03-thread, 04-input}     ← 4 张同 blob (+05-sticky 另计)
7f2d81  desktop-1680-{01-list, 02-top, 03-thread, 04-input}     ← 4 张同 blob
5c07d9  desktop-1920-{01-list, 02-top, 03-thread, 04-input, 01-list-dark}  ← 5 张同 blob (含 dark!)
740597  desktop-2560-{01-list, 02-top, 03-thread, 04-input}     ← 4 张同 blob
```

**根因**: `web/src/views/desktop/DesktopFileCommentsView.vue` **0 处 `route.query`** (`grep -c route.query` → 0).
spec 设计的 4 个视图靠 query 区分:
```js
{ name: '01-list',   path: '/drive/file/99/comments'          }
{ name: '02-top',    path: '/drive/file/99/comments?top=1'    }
{ name: '03-thread', path: '/drive/file/99/comments?thread=1' }
{ name: '04-input',  path: '/drive/file/99/comments?focus=1'  }
```
组件**从不读这些 query** → 4 个 path 渲染完全相同 → 4 张 baseline 字节相同.

**更严重**: `desktop-1920-01-list-dark` 与 light 版**同一 blob** — spec `test.use({ colorScheme: 'dark' })` 设了 dark, 但截图与 light 完全一致
⇒ **dark mode 在该页面根本没生效** (对照 CLAUDE.md 铁律 13 "dark mode 跨组件必须非 scoped 块", v60-v67 第 5 次强化).

**结论**: 22 case "PASS" 且双跑稳定, 但**信息量只有 5 张图 + 17 张冗余**; 且暴露 2 个真实产品缺陷 (query 未实现 + dark 未生效).
这正是 `5522ad5a8` 废弃理由 "**真实 bug 拦截率低**" 的机理 — baseline 数量虚高掩盖了零信息增量.
**未改 spec / 未改组件** (brief 禁改), 据实上报, 留 W89+.

### 4.5 治理冲突: 本任务生成物与 2026-06-29 废弃决策直接冲突 (**最重要, 请主指挥拍板**)

`git log --diff-filter=D` 查出这些 baseline **曾经存在且被刻意删除**:

- `f08e18584` "fix(visual): 删 baseline png" — 根因原文: **"我本地 Windows 生成的 baseline 是 `*-win32.png`, Linux runner 期望 `*-linux.png`, 平台差异导致 baseline 不能跨平台共用"**
- `5522ad5a8` "chore: 废弃 v76 视觉回归 — CI 失败率 40%" — 50 runs 中 20 FAIL **全是 visual regression job 自身问题**; 列明废弃理由含 "**OS suffix 跨平台坑**" + "真实 bug 拦截率低"
- `.github/workflows/lint-css.yml:206-211` → `visual-regression-deprecated:` `if: false # 永远跳过`, 注释 "**保留 baseline PNG 和 spec 文件作本地 dev 用, 不进 CI**"
- `playwright.config.js` 头注释 "v77 状态 (2026-06-29): CI 中已禁用 visual-regression job (40% 失败率, 价值低于成本), baseline png 已 git rm"

**本任务产出 31 张全部是 `-win32.png`** (`ls | grep -vc win32` → 0), 即**与 `f08e18584` 删除根因完全同一形态**. commit 它们 = 把一年前刻意 `git rm` 的东西按原样放回, 且 CI 永久 `if: false` 不消费.

**本任务处置**: 仍 commit `desktop-comments` 22 张 (唯一双跑稳定 + brief 交付要求), 但**据实标注 win32-only + 仅本地 dev 有效**, 并把 9 张 flaky 的 visual-regression **排除出 commit** (双跑不稳, 入 git 即制造 40% 失败率复发的种子). 是否保留 22 张 / 是否复活整套视觉回归 → **请主指挥拍板**.

---

## 5. commit 边界

**入 commit**:
- `web/tests/visual/desktop/desktop_drive_comments.spec.mjs-snapshots/` — 22 张 (`-win32.png`, 真评论页, 双跑 22/22 稳定)
- `memory/w89-x10-visual-baseline-2026-07-30.md` — 本文件

**不入 commit (据实)**:
- `visual-regression` 9 张 — 本质 flaky (§4.3), 入 git 即复发 40% 失败率
- `mobile_drive_comments` 0 张 — production bug 阻断 (§4.2), 无法生成

**0 production code 铁律守恒**: 未动 `app/` `web/src/` `alembic/` `nginx/` `docker/` `web/dist/` `commercial/`; **未改任何 spec 内容**; `web/node_modules` junction + `probe*.mjs` 探针 + `test-results/` 已清理.

---

## 6. 派工 v6 §5 反馈 — 类 20.62 新增 (+ 3 条既有铁律实战)

**类 20.62 (新增)**: **"visual baseline 重 sync 必逐 spec + 统一 canonical project + 拍板"**

四个子条款 (本任务实测支撑):
1. **逐 project 对账再动手** — 缺 baseline 总数须按 `spec × 匹配 project` 展开; 宽 `testMatch` 与专用 project 同时命中 → 总数虚高 1 倍 (113 = 22×2 + 30×2 + 9). 先删重复匹配再谈生成, 否则生成 2 套永不被消费的 baseline.
2. **baseline 必真登录态, 且必查 md5 唯一性** — `mock-token` → 401 → 静默重定向, 产出"全绿"假 baseline. **md5 去重是最廉价的自动化哨兵**: N 张 baseline 只有 1~2 个唯一 hash = 全是同一张重定向页. 逐张肉眼 Read 抽查 + 全量 md5 双保险.
3. **平台 suffix 是 baseline 入 git 的前置门禁** — Playwright 按 `{name}-{project}-{platform}.png` 找 baseline. Windows 产 `-win32`, CI Linux 找 `-linux` → 必 FAIL. **入 git 前必查 `ls | grep -v <ci-platform>`**; 跨平台不可共用, 本地 dev baseline 与 CI baseline 是两套东西.
4. **重 sync 前必查废弃史** — `git log --diff-filter=D -- <baseline-path>` + CI workflow `if:` 条件. 若曾被刻意 `git rm` 且 CI 永久跳过, "补齐缺失 baseline" 实为**复活已废弃资产**, 须主指挥拍板而非默认执行.
5. **commit 后必做 blob 去重复检** — `git ls-tree -r HEAD | awk '{print $1}' | sort -u | wc -l` 对比文件数. 22 张只有 5 个唯一 blob = 17 张零信息增量, 且反向暴露产品缺陷 (query 未实现 / dark 未生效). **baseline 数量 ≠ 覆盖度**; 唯一 blob 数才是真覆盖上限.

**既有铁律实战命中**:
- **类 20.25 "a11y/视觉测试必先 baseline, 全绿是可疑信号"** — 实战第 2 次. 首轮 31/31 全绿, 真相是全部截同一张仪表盘.
- **类 20.32 "base 必实测 ls-remote origin"** — 实测 `3a1ab24b3` 与本地 main 一致, 守恒.
- **类 20.31 "subagent worktree fallback"** — `git worktree add ../<dir> main` 报 `'main' is already used by worktree`; fallback `git worktree add -b <branch> <dir> main` 成功.

**新增副产物铁律 (0 production code 场景)**: spec 的 `bodyText.length > 10` 前置断言必须排在 `toHaveScreenshot` **之前** — 本任务正因此顺序才拦下 60 张空白 baseline 入库. 任何视觉 spec 都应有此"非空白页"守卫.

---

## 7. 留 W89+ (4 项)

| # | 项 | 优先级 | 说明 |
|---|-----|--------|------|
| 1 | `MobileFileCommentsView.vue` 补 `useMobileKeyboard` import | **P0** | 1 行修复; 移动端文件评论页当前**生产白屏**, 非仅测试问题 |
| 2 | `playwright.config.js` 收窄 `desktop-chrome` / `mobile-iphone14` testMatch | P1 | 排除已有专用 project 的 spec, 消除双 project 重复 baseline |
| 3 | `visual-regression` 等待逻辑改数据就绪 (`waitForSelector`) | P2 | 现 `waitForTimeout(800)` 竞态 → 3~6% diff flaky |
| 4 | `DesktopFileCommentsView.vue` 补 `route.query` (top/thread/focus) 处理 | P1 | 现 0 处 `route.query` → spec 4 个视图渲染同一张图, 22 张 baseline 仅 5 唯一 |
| 5 | `DesktopFileCommentsView` dark mode 未生效 | P1 | `colorScheme:'dark'` 截图与 light 同 blob; 对照铁律 13 非 scoped 块 |
| 6 | 视觉回归整体存废 + baseline 平台策略拍板 | **P0 (治理)** | 2026-06-29 已废弃 + CI `if: false`; 若复活须解 OS suffix (CI 内 `--update-snapshots` 产 `-linux`) |

## 8. 锚点

base `3a1ab24b3` (338) → tip = **339** (+1 守恒, 1 commit: 22 baseline + memory).
