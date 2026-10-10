# 工单 M5-2：OSS 通道（手写签名 + 上传/下载/列表/删除 + 退出自动备份）

> 签发：总指挥 · 2026-09-18
> 上游：M5-1 已验收关闭（`59a73ae1f` + `50d751166`）；测试基线 **220** 条全绿
> 设计文档：`docs/plans/2026-09-18-sync-engine-design.md`（§6 OSS 通道为本单核心）

## 你的任务背景

M5-1 交付了加密备份容器与恢复安全网（`createBackup` 产物为 `.mnbbak` 文件）。本单接通**阿里云 OSS**：备份可上传云端、云端快照可列表/下载恢复/删除；并实现「退出时自动备份」。

**零新增 npm 依赖**：OSS V1 签名用 node:crypto 手写（HMAC-SHA1），HTTP 用注入式原语（与 M4 的 Tray/Notification 注入同模式）——服务与测试零 Electron import，单测用注入的假 HTTP 断言签名与请求形状。

**重要边界**：真实 OSS 凭据执行端不可得——真机联调（真实 bucket 上传/下载）由总指挥执行，你交付时以「注入假 HTTP 的单元测试 + 真机联调指引」收口，并如实标注。

## 常设红线（违反任一直接打回）

1. 保护路径零改动：`app/`、`web/`、`alembic/`、`nginx/`、`docker-compose*`、`.env`、`desktop-conversion/` 一律不碰；交付时贴 `git status --short` 自证
2. 禁止 `git add -A`；只提交：`git commit -- apps/desktop`；遇 `.git/index.lock` 等待重试，禁止删锁
3. 禁止新增任何 npm 依赖
4. 门禁：`pnpm test` 全绿（当前基线 **220** 条，需新增 ≥12 条）、`pnpm typecheck` 0 错、`pnpm build` 成功
5. IPC 白名单三处同步；新增配置走现有 settings 通道

## ⚠ 前车之鉴五项（交付前自查）

1. 重启 dev 实测生效（附截图）
2. fake 注入所需 fs 符号显式导入
3. **报告归属与数字以 git/测试输出为准**——连续多单在此翻车（R-3/M4 归属误述、M5-1 虚标测试数），本单交付前逐项核对，tag↔commit 对应关系逐行核对
4. 勿动缩放锁定与桌面集成既有行为
5. **OSS Secret 安全**：AccessKeySecret 经 safeStorage 加密存 settings，不落明文、不写日志、不出现在交付报告

## 交付物

### 1. OSS 签名与客户端（`src/main/services/backup/oss.client.ts`，纯逻辑 + 注入 HTTP）

- **V1 签名**：`Authorization: OSS AccessKeyId:signature`——signature = base64(HMAC-SHA1(secret, VERB + Content-MD5 + Content-Type + Date + CanonicalizedOSSHeaders + CanonicalizedResource))；Date 用 GMT；实现要点按 OSS 官方规范
- 操作（全部经注入 `httpRequest` 原语）：
  - `putObject(config, key, buffer)`：PUT，Content-MD5 头
  - `getObject(config, key)`：GET → Buffer
  - `listObjects(config, prefix)`：GET bucket → 解析 XML listing（Key/Size/LastModified，简单正则/手动解析即可，注明局限）
  - `deleteObject(config, key)`
- 配置对象：`{ bucket, endpoint, prefix, accessKeyId, accessKeySecret }`；**secret 由调用方解密后传入，客户端不落盘**

### 2. BackupService 扩展

- `uploadBackup(config, filePath)`：读 `.mnbbak` → putObject（key = `desktop-backup/<文件名>`）→ 返回远端 key 与大小
- `downloadBackup(config, key, targetDir)`：getObject → 写本地备份目录 → 返回本地路径（后续走既有 restoreBackup）
- `listRemoteBackups(config)`：listObjects(prefix) → 摘要列表
- `deleteRemoteBackup(config, key)`：deleteObject（确认逻辑在 UI 层）
- **退出自动备份**：settings 开关（默认关）+ 主进程退出钩子——触发 `createBackup`（读取已存 OSS 配置则直传，未配置则仅本地）；**失败不阻塞退出**（10s 超时保护 + 日志）；注入 quit 原语可测

### 3. Secret 安全

- AccessKeySecret 写 settings 前**必须经 safeStorage 加密**（`safeStorage.encryptString` → base64 存库），读取时解密
- 交付报告与日志不得出现 Secret 明文（AK ID 可出现）

### 4. IPC + UI

- 通道：`backup:oss-save-config / oss-test / oss-upload / oss-list-remote / oss-download / oss-delete-remote`（白名单三处同步 + 契约测试）
- 设置页「备份与恢复」区块扩展：
  - OSS 配置表单（bucket/endpoint/前缀/AK ID/Secret）+「测试连接」（listObjects 探测，成功绿字/失败红字原因）
  - 快照列表合并展示本地 + 云端（来源标注），操作：恢复（云端自动先下载）/删除
  - 「退出时自动备份」开关（默认关）+ 「备份后上传云端」开关（默认关）

### 5. 测试（≥12，全部离线，注入假 HTTP）

- V1 签名：固定输入 → 期望 signature（手工构造规范串断言）≥2 例
- 请求形状：putObject/getObject/listObjects/deleteObject 的 method/URL/关键 header 断言 ≥4 例
- listObjects XML 解析：正常/空列表/异常 XML 容错 ≥2 例
- 上传下载往返（假 HTTP 回传同 buffer）+ Secret safeStorage 加密往返 ≥2 例
- 退出自动备份：开关关不触发/开触发且失败不阻塞退出（注入 quit 与超时）≥2 例
- 现有 **220** 条零回归

## 定义完成（全部满足才算完）

- [ ] 门禁全过：test 220 + 新增 ≥12、typecheck 0 错、build 成功
- [ ] `git status --short` 无保护路径改动；Secret 无明文泄露（自查报告与日志）
- [ ] **重启 dev 实测确认**：设置页 OSS 表单与测试连接交互真实生效（截图留证；真实 bucket 联调由总指挥执行）
- [ ] 交付报告第 6 项：CHANGELOG 条目草稿
- [ ] 报告归属与数字逐项与 git/测试输出一致；**无 Secret 明文**

## 交付报告格式（七项制）

1. 变更/新增文件清单（路径+行数）
2. 门禁输出尾部（注明测试条数：基线 220 → 共 N 条）
3. commit hash + 提交信息
4. 自测记录：签名构造说明 + 各用例结果表 + Secret 安全自查声明
5. 遗留问题 / 对 M6（发布通道完整版）的建议
6. **版本迭代信息（CHANGELOG 条目草稿）**
7. **真机联调指引**（总指挥执行：配置 OSS → 测试连接 → 备份并上传 → 云端列表 → 下载恢复 → 删除云端快照）
