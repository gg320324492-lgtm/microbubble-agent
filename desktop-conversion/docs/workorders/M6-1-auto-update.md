# 工单 M6-1：自动更新通道（electron-updater + 提示式更新 + v0.1.5-alpha 发布）

> 签发：总指挥 · 2026-09-18
> 上游：R-5 已验收关闭（v0.1.4-alpha 上线）；测试基线 **240** 条全绿
> 决策依据：D8（提示式更新 / electron-updater / GitHub Releases provider / allowPrerelease=true）

## 你的任务背景

应用已五版发布，全部靠手动下载安装。本单接入 **electron-updater**（D6 指定官方组件）实现**提示式自动更新**：启动时后台检查 + 设置页手动检查 → 发现新版 → 系统通知 + 设置页展示版本与下载进度 → **用户确认后**安装重启。不做静默强更。

**本单红线例外（唯一）**：允许新增依赖 **electron-updater**（锁最新稳定版，声明于 dependencies）——D8 决策明确。**其余依赖禁令不变**。

技术要点（含经典坑，直接采用）：
- 更新源：GitHub provider（owner `gg320324492-lgtm` / repo `microbubble-agent`）；**`autoUpdater.allowPrerelease = true` 必须设置**——我们全部版本均为 prerelease，默认会被忽略
- 无 publish 配置的工程：electron-builder 不生成 app-update.yml——dev 下用 `dev-app-update.yml` 或运行时 `setFeedURL` 注入（执行时调研落地方案并在报告说明）
- 未签名安装包：Windows 下 electron-updater 不强制签名校验（不配置 publisherName 即可），行为与现状一致
- **更新逻辑以适配层隔离**（updater 适配器注入，同 tray/notification 模式）：核心状态机（空闲→检查中→可更新→下载中→待安装）纯逻辑可离线单测；electron-updater 本体 mock
- 版本比较：语义化比较纯函数（prerelease 语义正确处理 0.1.5-alpha < 0.1.5）
- 真机验证方案：本地静态服务伪造更高版本 feed + 假安装包 → 全链路（检测/下载进度/安装提示）；无需真发布两个版本

技术栈约束同前：主进程服务与单测绝不 import 依赖 Electron ABI 的模块（electron-updater 仅在适配层出现，适配层由主进程装配）。

## 常设红线（违反任一直接打回；依赖例外见上）

1. 保护路径零改动：`app/`、`web/`、`alembic/`、`nginx/`、`docker-compose*`、`.env`、`desktop-conversion/` 一律不碰；交付时贴 `git status --short` 自证
2. 禁止 `git add -A`；只提交：`git commit -- apps/desktop`；遇 `.git/index.lock` 等待重试，禁止删锁
3. **依赖禁令例外**：仅允许新增 electron-updater；其余一律禁止
4. 门禁：`pnpm test` 全绿（当前基线 **240** 条，需新增 ≥8 条）、`pnpm typecheck` 0 错、`pnpm build` 成功
5. IPC 白名单三处同步；新增设置项走现有 settings 通道

## ⚠ 前车之鉴五项（交付前自查）

重启 dev 实测生效（附截图）/ fake 注入符号显式导入 / **报告归属与数字以 git/测试输出为准，tag↔commit 逐行核对** / 勿动缩放锁定与桌面集成既有行为 / **变更文件清单必填**（R-5 漏报教训）

## 交付物

### 1. 更新适配层（`src/main/services/update/`）

- `updater-adapter`：封装 electron-updater（checkForUpdates / downloadProgress / quitAndInstall），事件转状态机
- **更新状态机（纯逻辑类）**：`idle → checking → available(vX) → downloading(p%) → ready → error(原因)`；禁用状态（设置关/开发环境）直接 idle
- 版本比较纯函数：semver + prerelease 语义（0.1.5-alpha 与 0.1.5/0.1.4 的比较）

### 2. 触发与 UX（提示式）

- 启动后 5 秒后台检查（不阻塞启动、失败静默记日志）；设置页「关于与更新」区块：当前版本（读 APP_VERSION）+「检查更新」按钮 + 状态/进度展示 + 「安装并重启」按钮（仅 ready 态可用）
- 发现新版：系统通知（复用 M4 Notification 注入，点击聚焦并弹设置页）
- 下载中：设置页进度条；下载完成 toast + 「安装并重启」
- 全程**不自动安装**——一切安装动作由用户点击

### 3. 设置项

- settings 新增「自动检查更新」开关（默认开）；「安装并重启」前二次确认弹窗

### 4. 真机全链路验证（本单自带）

- 本地静态服务伪造 feed（更高版本号 latest.yml + 假 exe）→ 打包版应用内：检查 → 发现 0.1.5 → 下载进度 → 「安装并重启」→ 版本变为假包版本（假包用 NSIS 打一个最小应用或直接复用同版本号+1 的真实构建）
- 流程与截图全部进交付报告

### 5. 测试（≥8，全部离线）

- 版本比较（含 prerelease 语义）≥3 / 状态机流转（含错误态与禁用态）≥3 / 通知触发判定（复用 M4 模式）≥1 / 组件渲染与交互 ≥2
- 现有 **240** 条零回归

## 定义完成（全部满足才算完）

- [ ] 门禁全过：test 240 + 新增 ≥8、typecheck 0 错、build 成功
- [ ] `git status --short` 无保护路径改动；electron-updater 为唯一新增依赖且锁版本
- [ ] **重启 dev 实测**：设置页「关于与更新」区块生效（截图）
- [ ] 真机全链路验证完成（伪造 feed 方案，流程与截图进报告）
- [ ] 交付报告第 6 项：CHANGELOG 条目草稿
- [ ] 报告归属与数字如实；变更文件清单必填

## 交付报告格式（七项制）

1. 变更/新增文件清单（路径+行数）
2. 门禁输出尾部（注明测试条数：基线 240 → 共 N 条）
3. commit hash + 提交信息
4. 自测记录：状态机流转表 + 版本比较用例 + 真机伪造 feed 全链路记录
5. 遗留问题 / 对 M6-2 的建议
6. **版本迭代信息（CHANGELOG 条目草稿）**
7. electron-updater 集成方案说明（feed 注入方式/dev-app-update.yml 处理/allowPrerelease 设置点）

## 附：真机更新流程说明（写给总指挥，报告需转述）

本单发布 v0.1.5-alpha 后：v0.1.5 起「检查更新」可发现后续所有新版本并一键升级；v0.1.4 及更早版本不含更新器，仍需手动下载一次 v0.1.5，此后进入自动更新循环。
