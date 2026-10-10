# DL-7 执行报告：自动更新通知 + 应用内显示更新日志（2026-09-29）

## 结论

Part A/B/C 全部交付：更新日志经 `buildLatestYml` 安全注入 `latest.yml`（js-yaml 同源解析器往返逐字一致，特殊字符矩阵全过）；真实 electron-updater 吃下该产物并触发应用内弹窗（版本号 + 多行 Markdown 日志 + 两按钮，稍后 24h 节流、重启不重弹、每日自动检查节流生效）；备份失败原因落主进程日志。`pnpm gate` **73 文件 781/781 全绿**（typecheck 0 / build 0）。待总指挥复核。

## 基本信息

- **实际 HEAD**：接单时 `e102ff9ad`（v1.3.2 必带四修复的最后一个,均在 main ✓）；交付 commit **`ac2dc7c45`**（主交付）→ **`7ebea1ae7`**（CRLF 规范化 + CHANGELOG 草稿）→ **`8c09434b2`**（透明度单列：tray 降级守卫）,post-commit hook 均已推 origin
- **测试计数**：761 → **781**（+20：release-utils +9 [抽取 3/YAML 往返矩阵 5/verify 对称 1]、update-state +2、update-service +3、弹窗 DOM +6）
- **现网 feed 零接触**：本单只改生成逻辑（scripts/）,`releases.mnb-lab.cn` 现网文件未被读取或写入

## Part A：更新日志注入更新源

- `extractChangelogSection(changelogSource, version)` 纯函数：按 `## <version>` 标题切段（标题行允许版本号后带后缀如 `## v1.3.1（…）`;前缀防误吞,v1.3 ≠ v1.3.1）;找不到返回 **null**;**CRLF→LF 规范化**（真实仓库实测 CRLF,验收 smoke 抓到后补,附守护用例）
- `buildLatestYml(input, releaseNotes?)`：块标量 `|`（输入以 \n 结尾）/`|-` 双 chomp,块体逐行缩进 4 空格——任意 Markdown（`:`/`#`/`---`/缩进/空行/引号/反斜杠/中文/tab）整块转义;空参时输出与历史**逐字一致**（有专测）
- `verifyLatestYml`：expected 带日志 → 校验块表示存在且逐字一致;expected 未带 → 要求字段省略（两侧不对称同判失败）
- `stepLatest()`：读 `CHANGELOG.md` → 抽 `v{version}` 段 → 传入生成/自校验,命中（`更新日志命中：…N 字符`）/未命中（`[warn] … 不含 releaseNotes`）显式日志
- **取舍说明**：未采用「releaseNotes 传 URL」形态——块标量在现构建方式下可靠（往返矩阵实证）,且省一次 CDN 往返与 404 面
- 单测 19 个,往返解析器用 `createRequire(electron-updater/package.json)('js-yaml')` = **electron-updater 实际解析器同源**（4.3.2）

## Part B：应用内更新通知

- **releaseNotes 通路**：updater-adapter 捕获 `updateInfo.releaseNotes`（字符串才采纳;GitHub 回退路径该字段为 `ReleaseNoteInfo[]` → 视为无日志,弹窗降级）→ `check-available` 事件携带 → `UpdateState.releaseNotes?`（仅在有值时落键,历史形状兼容）→ 渲染层经既有 `UPDATE_STATE_EVENT` 通道获取。**`skipped` 语义原样保留**（updater-adapter.ts:69-91 一字未动）
- **启动自动检查**：复用 `scheduleAutoCheck`（5s 延迟）+ 新增**每日节流**：`getLastAutoCheckAt/setLastAutoCheckAt` 注入,userData 小 JSON 持久化（登录无关——5s 触发时可能未登录,settings 通道会被 AUTH_REQUIRED 挡）;20h 窗口;时间戳在**发请求前**记录（失败也算当日已检,避免失败风暴）
- **弹窗** `UpdateNotifyDialog.vue`（App.vue 挂载）：版本号 + 日志正文（pre-wrap,空日志降级「本次更新未提供更新日志」不渲染空框）+ 立即更新/稍后;立即更新 = `download()` → 进度 % → ready 自动 `install()`（显式授权链路收尾,关窗即取消;install 返回 false 解除武装）;**稍后**按版本号 localStorage 记 24h;**设置页在场不弹**（与 M6-1 `AboutUpdateSection` 共用同一状态机与通道,零新逻辑零打架）;Esc 可关;失败展示 `state.error` 不卡死;暖白学院风令牌,浮层与 CommandPalette 同族
- **DOM 测试 6 用例**：呈现/稍后节流+恢复/空日志降级/下载链路+错误不卡死/设置页不弹/非 available 不弹

## Part C：备份失败可观测性

1. `cloud-backup.service.ts notifyFail` 补 `this.log('[backup] {title}：{body}')`（与通知内容一致,失败原因进日志）
2. `ipc.ts` 云备份 notify 注入空 catch → 记 `console.log('[backup] 系统通知发送失败：…')`,**不重抛**（通知失败不影响备份主流程,语义保留）
3. `ipc.ts:1659` 附近 daily-backup notify 注入：**实测 `desktopNotify` 内部无兜底**（`new Notification().show()` 裸调）→ 同类静默风险成立 → 包 try/catch 记 `[daily-backup] 系统通知发送失败：…`
4. **证据**：`zb-cloud-backup.test.ts` 真实 `CloudBackupService` 实例 + 失败上传注入,断言新日志行并原样打印片段——`[DL-7 Part C 主进程日志片段] [backup] 云端备份失败：网络不可用`（与主进程 console.log 同一调用路径）。说明：runOnce 的真实触发门需要云端登录（gate=online+loggedIn+due）,离线沙箱无法直达,故以真实服务类+失败注入作为等效证据;e2e 中另对 `BackupService.uploadBackup`（非本单改动路径）做了一次真实不可达 endpoint 失败（`failed-as-expected`,见 report.json）

## 验收证据（assets/2026-09-29-DL7/）

方法：本地 HTTP 服务喂**真实 buildLatestYml 产物**（served-latest.yml 存档）→ 真实 electron-updater 经 `MNB_UPDATE_FEED` 拉取 → 全链真渲染。

- `dl7-update-dialog.png`：弹窗「发现新版本 v99.0.0」+ 多行 Markdown 日志逐字呈现（含 `:`/`#`/`---`/围栏）+ 立即更新/稍后;数值断言 dialog.version/notes/updateBtn/laterBtn
- `dl7-after-later.png` + `dialogClosedAfterLater: true`
- `dl7-second-launch-no-repop.png` + `secondLaunch.dialogVisible: false`,且 feed-server 全程**仅一次 GET**（第二轮自动检查被节流,throttle 文件 `{"at":…}` 只写一次,存档于报告引用）
- `dl7-settings-regression.png` + `settingsHasUpdateSection: true`（M6-1 既有入口存活,同状态机）
- `main-log.txt`：`[updater] Found version 99.0.0`（真实解析证据）
- `dl7-e2e-driver.mjs`：可独立复跑

## 透明度说明（单列,均为 DL-7 功能生存性/正确性所必需,非顺手修复）

1. **setupTray 降级守卫（`8c09434b2`）**：验收演练实测——以 main 脚本路径直启（非打包联调形态）时 `app.getAppPath()=out/main`,托盘图标解析落空 → `new Tray` **抛异常** → whenReady 链在 setupTray 处死亡,**下一行的 scheduleAutoCheck（及退出备份/activate 注册）全部静默失联、零日志**（本轮验收若无此修复则启动自动检查整体不工作）。打包态图标经 extraResources 落位暂不受影响,但任何图标缺失环境即整体杀死本单功能。守卫=失败仅记日志降级,不改变托盘正常行为
2. **electron-updater 未打包态"当前版本"= Electron 版本（32.3.3）而非 APP_VERSION**：探针实测。只影响离线联调形态（真机安装版正确）,已在驱动中以 v99.0.0 规避,不改产品代码
3. **extractChangelogSection 的 CRLF 规范化**：真实仓库 CHANGELOG.md 为 CRLF,不规范化则 releaseNotes 混入 `\r`（`7ebea1ae7`,附守护用例）
4. **js-yaml 引用方式**：测试经 `createRequire(electron-updater)` 解析（pnpm 严格布局下唯一正路,且保证与真实解析器同版本）;**未新增任何 npm 依赖**,`release-utils.mjs` 本体保持零 import（verify 用块表示逐字比对,不引解析器）

## 范围红线自查

backup 容器格式（MNBBK1）/备份恢复业务逻辑/零感自动配置逻辑零改动;`is_team_shared` 零接触;无自动强推/静默更新;无新增依赖;`app/`、`web/`、`alembic/`、`nginx/`、`docker-compose*`、`.env` 零改动。演练发现 ②③ 未动（明确不在本单）。

## 下一步

总指挥独立复跑 gate + 逐字核对 diff → v1.3.2 列车（release 时 CHANGELOG 定稿,`stepLatest` 将自动抽取 v1.3.2 段注入 latest.yml）。
