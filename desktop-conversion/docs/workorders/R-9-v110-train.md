# 工单 R-9 · v1.1.0 发布列车：三热修 + 每日定时备份

- **签发**：总指挥，2026-09-20
- **优先级**：高（首批真实用户缺陷 + 课题组部署模式落地的最后一里）
- **执行端**：编码 agent（用户转交本工单全文）
- **版本目标**：**v1.1.0**（含新功能，按 semver 用 minor；正式 tag 不可变）
- **前置依赖（用户侧，非执行端阻塞项，但 tag 前必须完成）**：GitHub Secrets `OSS_UPLOAD_AK/SK` 统一为现役 AK（否则 CI 的 OSS 镜像上传会失败）

---

## 背景（真实事故与需求来源）

1. 真机首装暴露两缺陷：①登录/注册页没有任何窗口控制按钮；②安装版 userData 解析到 `@mb/desktop`（package.json name），与开发模式共用数据目录，导致首装用户被历史残留账号锁在登录页（注册页仅在空库出现）
2. 课题组部署模式已定：成员机器备份到**服务器共享目录**（每人子目录），OSS 仅作可选异地副本——缺「每日定时备份」触发器（目标目录/加密容器/恢复能力 v1.0.1 已具备）
3. feed 自定义域名 `https://releases.mnb-lab.cn` 已终验通过，`UPDATE_FEED_HOST` 切换是 `apps/desktop/src/shared/constants.ts:16` 注释预留的一行

参考教训（父项目备份体系复盘，2026-09-20 调研）：产物形态与扫描/清理规则必须同源锁定（父项目曾因模式不匹配导致 MinIO 备份静默不达 OSS）；禁止整文件进内存；失败必须可感知；禁止默认凭证回落。

---

## 阶段 A · 三热修

### A1 auth 页窗口控制
- 现状：窗口 `frame: false`（`src/main/index.ts:22`），自绘 `TitleBar.vue` 仅挂工作台布局；`LoginView.vue`/`SetupView.vue` 无任何 min/max/close，也无拖拽区
- 要求：auth 页提供最小化/最大化/关闭三键 + 标题栏拖拽区。实现方式执行端自定（抽出通用 WindowControls 组件复用 TitleBar 的 IPC 调用为佳，勿复制两份逻辑）
- **验收硬项**：登录页与注册页三键均可用（真机点击验证）；窗口可拖动

### A2 userData 归属修复
- 现状：打包产物 `app.getName()` 回退到 `"@mb/desktop"`（productName 未生效），首启创建 `%APPDATA%\@mb\desktop`；开发模式同路径
- 排查要求：先探明 electron-builder 为何未把 productName 注入 asar 内 package.json（检查打包配置与流程），再定修复
- 修复方向（二选一，探明后选择并说明理由）：a) 修打包注入使 productName 生效；b) `main/index.ts` 显式 `if (app.isPackaged) app.setPath('userData', join(app.getPath('appData'), 'MicroBubbleWorkbench'))`
- **验收硬项**：①打包产物首启 userData 落 `%APPDATA%\MicroBubbleWorkbench`；②dev 模式仍用原路径，互不影响；③**负责人机升级无缝**：从开始菜单启动 v1.1.0（不带任何环境变量），直接读到既有账号与数据（该目录现状已是 `%APPDATA%\MicroBubbleWorkbench`）；④不得迁移/触碰旧 `@mb` 目录
- 桌面残留说明：负责人桌面有临时启动器 `启动科研工作台.cmd`（内含 MNB_USER_DATA 覆盖），本项验收通过后即废弃，工单报告里注明即可，勿删用户文件

### A3 feed 域名切换
- `UPDATE_FEED_HOST`：`https://mnb-workbench-releases.oss-cn-beijing.aliyuncs.com` → `https://releases.mnb-lab.cn`（`src/shared/constants.ts:16`）
- 同步检查：引用该常量的测试用例、文档注释；`feed-config.ts` 纯函数用例须全绿
- **验收硬项**：测试全绿；打包产物内 feed 基址为 `https://releases.mnb-lab.cn/releases/`

---

## 阶段 B · 每日定时备份

- 触发：应用运行中的每日定时（设置页：开关 + 时间点，默认建议凌晨用户大概率不在线，故默认「**当天首次启动后延迟 10 分钟**执行一次」并允许改为固定时刻；错过不补跑，第二天再触发）。仅在「备份密码」已配置时生效
- 行为：调用既有 `BackupService.createBackup`（加密容器：SQLite 快照 + files 打包，AES-256-GCM）落到配置的「备份目标目录」（本地/UNC/映射盘均须支持，v1.0.1 已参数化）
- **保留策略（硬要求）**：同前缀保留最近 N 份（默认 7，可配 0=不清理），超出删最旧。删除规则必须与 `createBackup` 产物命名**同一常量来源**，只删本应用命名模式的文件（防误删用户文件——父项目断链教训）
- **失败可感知（硬要求）**：定时备份失败 → 系统通知（Notification 已在依赖内）+ 设置页备份区块显示最近一次定时备份结果与时间
- 大文件防护：评估 files 目录体积，若容器打包当前为整内存读，本期至少做到「超阈值（建议 ≥1GB）检测 + 明确报错并跳过 + 通知」，流式/分块列入后续单
- 范围外：退出自动备份（S1 ④）不并入本单；服务器侧 OSS 异地同步脚本见阶段 C
- **验收硬项**：纯函数（节拍决策/错过不补/保留清理/命名同源）单测锁死；真机验证一轮完整链路（定时触发→生成容器→保留清理删最旧→失败注入→通知出现）

---

## 阶段 C · 服务器侧异地同步脚本（交付物，非应用代码）

- 新增 `apps/desktop/scripts/server/offsite-oss-sync.py`（零第三方依赖，复用父项目 `scripts/backup_to_aliyun_oss.py` 的手写 SigV4 + SSE 模式）：把服务器备份共享目录镜像到指定 OSS 前缀，`--scan / --apply --confirm / --cleanup N` 三段式 CLI，同名同大小跳过
- 配套 `apps/desktop/scripts/server/install-offsite-scheduler.ps1`（schtasks 注册，ASCII-only，参考父项目 `backup_scheduler.bat` 防坑写法）
- 本阶段不进 CI、不打包，仅在交付报告中给出服务器部署三步说明（用户自行部署到课题组服务器）

---

## 发布与验收材料

- 版本：`package.json` + `src/shared/constants.ts` APP_VERSION → **1.1.0**（两处同步）；CHANGELOG.md 增补（新功能：每日定时备份/服务器备份方案；修复：auth 窗口控制、userData 归属；变更：feed 域名）
- test tag `v1.1.0-ci.1` 首航 → 产物可运行性验证（CI smoke 门禁）→ 正式 tag `v1.1.0`
- 交付报告必含：变更文件清单、测试输出原文、真机验收逐项对照（A1/A2/A3/B 各硬项）、tag↔commit 核对
- **红线**：禁 `git add -A`；禁新增 npm 依赖（electron-updater 唯一例外）；保护路径零改动（`app/`、`web/`、`alembic/`、`nginx/`、`docker-compose*`、`.env`、`desktop-conversion/`；`.github/` 仅 `desktop-release.yml`）；OSS Secret 不落明文不入报告

---

## 进度状态（签发时点）

- 已完成：前置调研（缺陷定位 ×2、父项目备份体系复盘）、需求裁决（服务器中枢模式、保留策略、通知要求）
- 正在做：无（待执行端接单）
- 剩余：阶段 A → 阶段 B → 阶段 C → v1.1.0 发布
- 进度粗估：A 半天内；B 一天内；C 半天内；发布半天内，合计约 2.5–3 个工作单元
