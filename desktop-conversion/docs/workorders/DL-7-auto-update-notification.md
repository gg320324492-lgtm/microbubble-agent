# 工单 DL-7：自动更新通知 + 应用内显示更新日志

> 签发：总指挥 · 2026-09-29 ｜ 优先级：**高（用户已立项；本单是 v1.3.2 列车主菜）**
> 基线：`v1.3.1` 已发布（exe sha256 `25ed0f7e…`）/ 接单时以 `git log -1 -- apps/desktop` 实测 HEAD 为准，报告注明
> 范围裁决（用户 2026-09-29 拍板）：**主菜 = 本单 Part A + Part B；捎带 Part C（④ 失败落 log）。演练发现 ②（负责人未上零感）与 ③（云备份未接 daily 调度）另开小单，不在本单。**

## 项目背景

「小气科研工作台」桌面端（Electron + electron-vite + Vue3 + TS strict，工作区 `E:\microbubble-agent\apps\desktop`）。测试基线 **761 条全绿**（`pnpm gate` = test && typecheck && build 串联，失败即停，绝不带失败提交）。

**现状**：自动更新**通道已通**（M6-1/M6-2 交付，R-8 切 stable 频道，feed = `https://releases.mnb-lab.cn/releases/latest.yml`），但用户拿不到「有新版本」和「这次改了什么」——组员不会自己盯落地页。

**本单要补的**：把「有新版了 + 更新日志」这两件事送到用户眼前，且**不依赖 GitHub**（国内直连 CDN，组员往往连不上 GitHub）。

**本机环境陷阱（必读，历代踩过）**：
- `AppData\Local` 实际在 **D 盘**（`D:\Users\pc\AppData\Local`），C 盘同名路径是空壳；安装版在 `D:\Users\pc\AppData\Local\Programs\MicroBubbleWorkbench`
- 本机沙箱 vitest SSR 临时文件间歇 EPERM → 本地测试计数会波动；跑到的全过即可提交，**全绿结论以 CI 为准**（仓库已转 Public，CI 无额度顾虑，一轮约 4–5 分钟）
- `node -e` 内嵌探测会静默失败——探测一律用**临时脚本文件**
- 凡「子进程探测 + 按退出码判定」的脚本，catch 路径必须 `process.exit(1)`（R-11 阶段 C 八轮红跑的真凶）
- 改仓库文件一律用 **Edit 工具**（Python 文本重写曾静默失效，且会把 CRLF 转 LF 造成整文件假 diff）；提交链用 `&&` 串联
- 仓库有 post-commit 自动 push 钩子（commit 即推 origin）；**gate 过了立即 commit**

---

## Part A：把更新日志注入更新源（releaseNotes）

**设计意图**：`latest.yml` 是 electron-updater 的唯一真相源。把 CHANGELOG 对应版本段落写进它的 `releaseNotes` 字段，应用端就能在**国内 CDN 直达**的前提下拿到更新日志，不依赖 GitHub Release notes。

**已定位的落点（总指挥已核实，勿凭猜测改动）**：
- `apps/desktop/scripts/lib/release-utils.mjs`
  - `buildLatestYml(input)`（第 48 行）：逐行数组 join 手工拼 YAML，当前字段为 `version / files[].url|sha512|size / path / sha512 / releaseDate`
  - `verifyLatestYml(ymlText, expected)`（第 69 行）：发布前自校验
  - 同文件已有 `extractAppVersion` / `checkVersionSync` 等纯函数先例，**新函数沿用纯函数 + 同文件导出的风格**
- `apps/desktop/scripts/release.mjs` → `stepLatest()`（第 257–270 行）：调 `assertVersionSync()` → 算 sha512/size → `buildLatestYml(...)` → 写盘 → `verifyLatestYml(...)` 自校验
- 更新日志来源：`apps/desktop/CHANGELOG.md`（v1.3.2 段落**发布时定稿**，本单开发期用当前版本已有段落自测）

**要求**：

1. 在 `release-utils.mjs` 新增纯函数 `extractChangelogSection(changelogSource, version)`：按 `## <version>` 标题切出该版本到下一个 `## ` 之间的正文；**找不到该版本时返回 `null`**（不得静默返回整篇，也不得抛未捕获异常）。
2. `buildLatestYml` 增加可选入参 `releaseNotes?: string`，非空时输出 `releaseNotes` 字段。**保持向后兼容**：入参缺省时输出与今天逐字一致（现有 feed-config / release 链路不能因此红）。
3. `verifyLatestYml` 同步扩展：当 expected 带了 `releaseNotes` 时校验其存在且与预期一致；`stepLatest` 的自校验要把这一项纳入（**否则自校验形同虚设**）。
4. `stepLatest()` 接线：读 `CHANGELOG.md`（路径相对 `apps/desktop` 解析）→ 抽取 → 传入 → 打印命中/未命中的明确日志。
5. **`releaseNotes` 取不到时的行为由你定，但必须显式**：建议「字段省略 + 明确 warn 日志」，**不得**写入空字符串或 `null` 破坏 YAML 结构。

### Part A 红线（本项目最大的坑在这）

`buildLatestYml` 是**手工逐行拼 YAML**，而更新日志是**任意多行 Markdown**（含 `:`、`#`、`-`、反引号、缩进、空行，甚至 `---`）。直接内联会让 `latest.yml` 解析失败，**后果是全体组员更新通道一起挂**——比不做这个功能严重得多。

- 必须用**安全的 YAML 表示**（块标量 `|` 或严格转义的引号串），并保证输出能被 `js-yaml`（electron-updater 实际使用的解析器）**原样解回**同一段文本
- 必须补**单测**覆盖：含 `:` / `#` / 缩进 / 空行 / `---` / 中文 / 反斜杠 / 引号 的日志段落
- 必须补**往返测试**：`buildLatestYml` → `js-yaml.safeLoad` → 断言 `releaseNotes` 与输入**逐字一致**（不要用 `==` 之外的方式糊弄，`\n` 与结尾空行差异要显式断言）
- 若无法在现有构建方式下取得可靠转义，**允许改用 electron-updater 支持的「releaseNotes 传 URL」形态**指向 `releases.mnb-lab.cn` 上的静态 md ——但需在报告中说明取舍，且 URL 必须匿名可 200。

---

## Part B：应用内更新通知（自动检查 + 弹窗 + 日志展示）

**已定位的落点（勿重造既有轮子）**：
- `src/main/services/update/`：`updater-adapter.ts`（唯一 `electron-updater` import 在此，已装 `autoDownload=false` / `autoInstallOnAppQuit=false` / `allowPrerelease` 稳定频道策略 / `onProgress` / `onDownloaded`）、`update.service.ts`（服务层 + `UpdaterPort`）、`update-state.ts`（状态机）、`feed-config.ts`（14 用例守护，纯函数）
- `updater-adapter.ts:69-91` 已有 `checkForUpdates`，且**已正确处理 `isUpdaterActive()` 跳过语义**（返回 `{skipped:true}` 而非伪装「已是最新」）——**本单不得破坏这个语义**

**要求**：

1. **启动自动检查**：应用启动后自动跑一次 `checkForUpdates`（须尊重既有 `skipped` 语义：未打包/无 feed 时静默跳过，**不得**弹「已是最新版本」）。给出检查时机（建议启动后延迟一小段时间，不与首屏渲染抢资源），并做**每日至多一次**的节流，避免每次开应用都打网络。
2. **有新版本时弹窗**：显示 **新版本号 + 更新日志正文**（正文来自 `updateInfo.releaseNotes`，即 Part A 注入的内容；为空时优雅降级为「无更新日志」文案，不得渲染空白框）。
3. **按钮两个**：
   - 「立即更新」→ `downloadUpdate` → 展示下载进度（复用既有 `onProgress`）→ `onDownloaded` → `quitAndInstall`
   - 「稍后」→ 关闭，不做任何事；**不**在本会话内反复弹（同一版本号每天最多打扰一次）
4. **失败可感知但不阻塞**：检查失败 / 下载失败要有明确提示，**不得**让弹窗卡死或阻断主界面。
5. **不破坏既有设置页更新入口**：M6-1 已在设置页做过更新 UI，本单是**新增启动期通知**，两者共用同一状态机与文案来源，**不允许出现两套互相打架的更新逻辑**。
6. UI 沿用 `packages/design-tokens` 与 M7 确立的「暖白学院风」标准（`docs/design/ui-style-proposals.html` 为唯一源），**不引入新的视觉语言**。

---

## Part C（捎带）：备份失败可观测性（演练发现 ④）

**问题**：备份失败只弹系统通知，主进程日志零痕迹——ZB 恢复演练排查 422 全靠翻服务器访问日志反推。

**落点（已核实）**：
- `src/main/services/backup/cloud-backup.service.ts:164-166` `notifyFail()`：**只调 `this.deps.notify?.()`，不落日志**（同文件 `this.log` 依赖已存在，130/141 行在用）
- `src/main/ipc.ts:1838-1844`：云备份的 `notify` 注入内 `catch { /* 通知不可用不影响备份 */ }` —— **空 catch 静默吞异常**

**要求**：
1. `notifyFail()` 内补 `this.log(...)`，与通知内容一致（保留 title + body，失败原因必须进日志）
2. `ipc.ts:1838-1844` 的空 catch 改为记录错误（用该文件既有日志风格），**保留「通知失败不影响备份主流程」的语义**（即：记日志，不重抛）
3. 同样审视 `ipc.ts:1659` 附近 daily-backup 的 notify 注入是否有同类静默吞异常

---

## 范围红线

- **不动** backup 容器格式（`MNBBK1`）、不动备份/恢复业务逻辑、不动零感自动配置逻辑
- **不动** `is_team_shared` 相关任何代码（该字段已退役，与本单无关）
- 不做「立即重启安装」之外的自动强推；不做静默后台强制更新（用户未授权）
- 不新增 npm 依赖（`electron-updater` 是唯一已授权例外，本单不需要新依赖）
- 保护路径零改动：`app/`、`web/`、`alembic/`、`nginx/`、`docker-compose*`、`.env`、`desktop-conversion/`
- 演练发现 ②（负责人本人未上零感备份）与 ③（云备份未接 daily 调度）**明确不在本单**，如发现必须动，单列说明

---

## 验收证据（整单，缺一退回）

1. **Part A 单测**：更新日志抽取 + YAML 安全往返（含特殊字符矩阵）
2. **Part B 真实渲染证据**：Playwright `_electron` 或 gate 内启动产物，构造「有新版本」场景，截图证明——弹窗含版本号 + 更新日志正文 + 两个按钮；「稍后」不重复弹
3. **Part C**：制造一次备份失败，主进程日志中可见明确失败原因（贴日志片段）
4. `pnpm gate` 全绿，报告注明：实际 HEAD、测试计数（761 ± 变化）、每处改动理由
5. **回归自查**：M6-1 既有设置页更新入口仍可用（贴截图或说明）；`releases.mnb-lab.cn` 现网 feed 不因本单被改动（**本单只改生成逻辑，不碰现网文件**）

## 交付

- 提交链干净（post-commit hook 自动推 origin）；报告贴出后**总指挥独立复跑 gate 并逐字核对 diff，不采信报告**
- 本单交付验收后走 **v1.3.2 列车**（CHANGELOG 随单起草段落，发布时定稿）
- **v1.3.2 必带清单**（总指挥已核实均在 main 上，执行端无需重复实现）：
  - `d7b8a46f4` 小文件上传改 multipart（≤4MB 上传与备份容器全废）
  - `7f0ebfed2` requestWithAuth 转发 contentType（multipart 被标 application/json 致 422）
  - `49cab7627` 附件段名带完整子目录层（子目录附件恢复错位/同名覆盖）
  - `e102ff9ad` setAppUserModelId 统一 Windows 应用身份
