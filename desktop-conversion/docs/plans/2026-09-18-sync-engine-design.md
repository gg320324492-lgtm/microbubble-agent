# M5 同步引擎设计（快照备份式 · OSS 直连）

> 2026-09-18 · 总指挥出设计。依据决策 S1/S2（用户拍板推荐组合）。
> 产品哲学对齐：D5——本地是主库，云端只是加密备份副本；能本地尽本地，零新增 npm 依赖。

## 1. 目标与非目标

**目标**：用户可用设置页把全部工作数据（SQLite 库 + 附件文件）做成一个**加密备份包**，存本地目录或阿里云 OSS；需要时从任一快照完整恢复。
**非目标（本期不做）**：记录级增量同步、多设备实时同步、自动冲突合并、网页端后端 API 对接、共享/协作。

## 2. 架构

```
[设置页 备份与恢复]
   │ 密码(不落盘)
   ▼
BackupService (main, 注入 http/crypto/fs)
   ├─ createBackup(): VACUUM INTO 快照 + 收集 files/ 目录 → 容器打包 → AES-256-GCM 加密
   │    → 写本地目录(targetDir) → [M5-2] 可选上传 OSS
   ├─ restoreBackup(): 解密校验 → 恢复前自动快照当前数据(安全网) → 覆盖库与文件 → 提示重启
   └─ listBackups(): 读容器 manifest（本地 / [M5-2] OSS 列表）
```

## 3. 备份容器格式（`MNBBK1`，自实现，零依赖）

```
magic "MNBBK1"(6B) | salt(16B) | iv(12B) |
gzip 容器({ aes-256-gcm 加密 }):
  payload = gzip( JSON头部(版本/时间/app_version/清单+各段sha256) + sqlite段 + 文件段们 )
authTag(16B)
```
- 密钥：`scrypt(password, salt, N=16384, r=8, p=1, keylen=32)`；加密 AES-256-GCM（authTag 防篡改）
- 恢复流程：读 salt/iv → 派生密钥 → 解密验 tag（密码错/篡改在此失败）→ gunzip → 校验各段 sha256 → 落地
- 命名：`workbench-<YYYYMMDD-HHmmss>.mnbbak`

## 4. 范围

- **SQLite**：`VACUUM INTO` 全量快照（双运行时可用；含六业务表/会话/审计/FTS 数据，恢复后 FTS 由迁移期逻辑随库自带）
- **files/**：`knowledge/`、`meetings/`、`experiments/` 附件副本整目录（含中文路径）
- **排除**：模型 Key 与 Provider 配置（安全敏感，恢复后需用户重配或由 safeStorage 现存值自理）、`.agent-backups/`、缓存类数据

## 5. 恢复安全网（硬性）

恢复前自动把**当前**库 + files 打包为 `pre-restore-<时间戳>.mnbbak` 存本地备份目录（不加密也可，含密码则同流程），确认弹窗明示「恢复将覆盖当前全部数据，已为你保留恢复前快照」。恢复完成后返回 `needRestart: true`，前端提示重启应用重载数据。

## 6. OSS 通道（M5-2）

- 手写 OSS V1 签名（HMAC-SHA1，node:crypto）：PutObject / GetObject / GetBucket(prefix 列表) / DeleteObject
- 配置存 settings：bucket / endpoint / 前缀 `desktop-backup/` / AccessKeyId / **AccessKeySecret 经 safeStorage 加密**
- 对象命名：`desktop-backup/workbench-<时间戳>.mnbbak`
- 单元测试注入假 HTTP（断言签名头与请求形状）；真机联调需用户准备 bucket + 子账号 AK/SK

## 7. 触发

- 手动：设置页「立即备份」（输密码）/「从备份恢复」（选快照 + 输密码 + 危险确认）
- 退出自动（M5-2，默认关，settings 开关）：退出流程中同步执行（体积小可接受；上限提示）
- 每日定时：产品池

## 8. 拆单与前置条件

- **M5-1**：容器 + 加密 + BackupService + 恢复安全网 + 设置页区块（本地快照）——纯本地全离线可测
- **M5-2**：OSS 通道 + 退出自动 + 快照管理增强——**前置条件：用户提供阿里云 OSS bucket（私有读写）+ 子账号 AK/SK**（仅该 bucket 权限）
