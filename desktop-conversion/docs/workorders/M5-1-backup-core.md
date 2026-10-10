# 工单 M5-1：备份核心（容器格式 + AES 加密 + 恢复安全网 + 设置页区块）

> 签发：总指挥 · 2026-09-18
> 上游：R-4 已验收关闭（v0.1.3-alpha 上线）；测试基线 **205** 条全绿
> 设计文档：`docs/plans/2026-09-18-sync-engine-design.md`（决策 S1/S2——OSS 直连快照备份式；本单为 M5-1 纯本地部分）

## 你的任务背景

实现备份核心：把全部工作数据（SQLite 库 + 附件文件）打成**AES-256-GCM 加密容器**（`.mnbbak`），支持从任一容器完整恢复，恢复前自动保留当前数据快照。纯本地、零网络、断网全功能。OSS 上传属 M5-2，本单不做。

直接约束：**零新增 npm 依赖**（gzip 用 node:zlib、加密用 node:crypto、SQLite 备份用 `VACUUM INTO`——双运行时均可用）；主进程服务与单测绝不 import 依赖 Electron ABI 的模块。

## 常设红线（违反任一直接打回）

1. 保护路径零改动：`app/`、`web/`、`alembic/`、`nginx/`、`docker-compose*`、`.env`、`desktop-conversion/` 一律不碰；交付时贴 `git status --short` 自证
2. 禁止 `git add -A`；只提交：`git commit -- apps/desktop`；遇 `.git/index.lock` 等待重试，禁止删锁
3. 禁止新增任何 npm 依赖
4. 门禁：`pnpm test` 全绿（当前基线 **205** 条，需新增 ≥14 条）、`pnpm typecheck` 0 错、`pnpm build` 成功
5. IPC 白名单三处同步（`src/shared/ipc-channels.ts` / `main/ipc.ts` / `preload`），一致性测试自动校验

## ⚠ 前车之鉴四项（交付前自查）

重启 dev 实测生效（附截图）/ fake fs 符号显式导入 / 报告归属以 git 记录为准 / 勿动缩放锁定与桌面集成既有行为

## 交付物

### 1. 容器格式（`src/main/services/backup/container.ts`，纯函数可离线单测）

严格按设计文档 `docs/plans/2026-09-18-sync-engine-design.md` §3 实现（该文件是你在 desktop-conversion\ 内**第二个**允许读取的文件，仅读它）：
- 布局：`magic "MNBBK1"(6B) | salt(16B) | iv(12B) | gzip密文 | authTag(16B)`
- 密钥派生：`scrypt(password, salt, N=16384, r=8, p=1, keylen=32)`；AES-256-GCM
- 内部容器：JSON 头部（app_version/created_at/sqlite 段与文件段清单 + 各段 sha256）+ sqlite 段 + 文件段们，整体 gzip
- 命名：`workbench-<YYYYMMDD-HHmmss>.mnbbak`

### 2. BackupService（`src/main/services/backup/backup.service.ts`）

- `createBackup({ password, targetDir, dbPath, filesDirs })`：
  1. `VACUUM INTO` 临时快照（node:sqlite 与 better-sqlite3 均支持）
  2. 收集 `filesDirs`（knowledge/ meetings/ experiments/ 三目录，含子目录与中文文件名）
  3. 容器打包加密写出 targetDir
- `restoreBackup({ password, file, dbPath, filesDirs })`：
  1. 解密验签（密码错/篡改 → 明确错误）
  2. **恢复前安全网（硬性）**：先把当前库 + files 打包为 `pre-restore-<时间戳>.mnbbak` 存同一目录
  3. 覆盖库（用备份内 sqlite 覆盖 dbPath，注意 WAL 文件一并处理）与文件（先清后铺）
  4. 返回 `{ needRestart: true }`（前端提示重启应用重载数据）
- `listLocalBackups(targetDir)`：读各容器 manifest 摘要（时间/大小/app_version）
- 密码不落盘、不写日志

### 3. IPC 通道组（`backup:create / restore / list`，白名单三处同步 + 契约测试）

### 4. UI（设置页新增「备份与恢复」区块，`components/settings/BackupSection.vue`）

- 「立即备份」：密码输入（两次确认）+ 本地目录选择 → 成功显示快照名与大小
- 本地快照列表（时间/大小/app_version）+ 「恢复」按钮
- 恢复流程：选文件 + 输密码 + **危险样式确认弹窗**（明示「覆盖当前全部数据，已自动保留恢复前快照」）→ 完成后弹「恢复完成，需重启应用」
- OSS 配置占位文案（「云端备份将于下个版本提供」）

### 5. 测试（≥14，全部离线，真实临时目录 + node:sqlite）

- 容器往返（sqlite 段 + 多文件含中文路径与子目录）→ 恢复后表数据与文件逐字节一致
- 错误密码拒绝（明确错误非崩溃）/ authTag 篡改拒绝 / magic 错误拒绝
- 同日多次备份命名不冲突 / listLocalBackups 摘要正确
- **恢复安全网**：pre-restore 快照存在且可再解密
- files 空目录/空库边界 / 现有 **205** 条零回归

## 定义完成（全部满足才算完）

- [ ] 门禁全过：test 205 + 新增 ≥14、typecheck 0 错、build 成功
- [ ] `git status --short` 无保护路径改动
- [ ] 断网自证：备份 → 恢复 全流程离线可用
- [ ] **重启 dev 实测确认**：设置页区块真实生效（截图留证）
- [ ] 交付报告第 6 项：CHANGELOG 条目草稿

## 交付报告格式（七项制）

1. 变更/新增文件清单（路径+行数）
2. 门禁输出尾部（注明测试条数：基线 205 → 共 N 条）
3. commit hash + 提交信息
4. 自测记录：容器格式各字段验证 + 恢复安全网 + 异常路径结果表
5. 遗留问题 / 对 M5-2（OSS 通道）的接口建议
6. **版本迭代信息（CHANGELOG 条目草稿）**
