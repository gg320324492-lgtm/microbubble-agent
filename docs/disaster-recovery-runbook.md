# 异地容灾恢复 Runbook

> 用途：主磁盘损坏 / 换机 / 需要从阿里云 OSS 取回备份时，照本文操作。
> 建立于 2026-10-12（离站容灾重做）。**本文不含任何密钥**，只记录位置与步骤。

## 一句话说清现状

| 项 | 值 |
|---|---|
| 备份内容 | PostgreSQL dump（知识库 + 会议转写）+ `.env`（库密码 / JWT SECRET_KEY / MinIO 密钥） |
| 存放位置 | 阿里云 OSS，桶 `mnb-workbench-backup`（**私有**），前缀 `offsite-backup/microbubble/` |
| 加密 | 每个文件独立 AES-256-GCM 封装，后缀 `.enc` |
| 保留 | 远端 7 天（与本地 `scripts/backup_db.sh` 的 `KEEP_DAYS` 一致） |
| 频率 | 每日 03:30（计划任务 `MNB-OffsiteOssSync`） |
| 日志 | `apps/desktop/scripts/server/logs/offsite-sync-<日期>.log` |

## ⚠️ 最关键的一件事：解密口令在哪

**口令文件：`<仓库根>/.secrets/offsite_backup.passphrase`**（单文件，约 64 字节 URL-safe 文本）

- 它**不在 git 里**（`.gitignore` + `.dockerignore` 双排除），也不在任何环境变量中。
- 它**只在这台机器上**。**本机丢失 = 远端 410 MB 备份永久不可读**（GCM 没有后门，轮换口令也救不了旧密文）。
- 因此本机的 `.secrets/` 目录**需要随本项目一起备份**，或另存一份到密码管理器 / 离线介质。
  本项目的密钥存放约定（见 `.gitignore:15,16,75,76,229`）是「文件 + gitignore」，
  离站备份脚本刻意不读 `.env` / 不读环境变量 / 不内置口令，就是为了避免这些副本被一起传到 OSS。

> 换机流程：先确认手上有没有这个口令文件，**没有就不要先删旧机**。

### 把口令备份到 Bitwarden（可选但强烈建议）

口令在**两处**：本机 `.secrets/` 明文文件 + Bitwarden 加密库（云端同步）。
主密码丢了没有任何人能找回（Bitwarden 零知识架构），所以主密码务必与其它网站**不复用**。

**做法（网页版，30 秒）**：

1. `vault.bitwarden.com` → 右上「+」→ **笔记**（不是"登录"）
2. 名称填 `小气工作台-异地备份口令`
3. 备注粘贴口令（`Get-Content .secrets\offsite_backup.passphrase -Raw`，复制后终端 `cls` 清屏）
4. 可选自定义字段：`bucket` / `prefix` / `runbook` / `local_passphrase_file`

**⚠️ 不要用 CLI 自动化（实测踩坑，2026-10-12）**：

`scripts/backup/store_passphrase_in_bitwarden.py` 走 `bw create item`，在 Windows 上
**读不到管道输入** —— 喂合法 JSON 与喂 `NOT-JSON-AT-ALL` 报**完全相同**的
`Error parsing the encoded request data.`，等价于读到空 stdin。
payload 格式本身没问题（`type: 1/2`、`fields`、中文 name 全部试过，一样失败），
`bw` 是真 exe 非 shim，`status`/`sync`/`list` 全部 rc=0 正常。
⇒ 只有需要 stdin 的子命令挂。**故走网页/桌面端手动录入。**

⚠️ **CLI 的 session key 是进程级环境变量，不跨终端标签页** ——
`$env:BW_SESSION = ...` 只在设过它的那个标签里有效，新开标签仍是 `locked`。

## 恢复步骤

### 场景 A：取回某一天的数据库备份

```bash
# 1. 确认桶里有东西（只读，不改任何东西）
python apps/desktop/scripts/server/offsite-oss-sync.py --scan \
    --passphrase-file .secrets/offsite_backup.passphrase

# 2. 从 OSS 下载目标密文到本地（见下方"下载单个对象"），例如
#    offsite-backup/microbubble/microbubble_20261011_020002.sql.gz.enc

# 3. 解密（口令文件是唯一所需的外部参数，密文头自带 salt/chunk/长度）
python apps/desktop/scripts/server/offsite-oss-sync.py \
    --decrypt-into ./restored \
    --passphrase-file .secrets/offsite_backup.passphrase \
    ./restored/microbubble_20261011_020002.sql.gz.enc

# 4. 校验完整性 —— 解密成功即已过 GCM 认证，可再比 sha256
sha256sum ./restored/microbubble_20261011_020002.sql.gz
gunzip -t ./restored/microbubble_20261011_020002.sql.gz && echo "gzip 完整"

# 5. 恢复
gunzip -c ./restored/microbubble_20261011_020002.sql.gz.gz | \
    docker exec -i microbubble-agent-db-1 psql -U postgres -d microbubble
```

### 场景 B：换机重建

1. clone 本仓，确认 `.secrets/offsite_backup.passphrase` **在手**（没有就先从旧机取回）
2. 按 `.env` 恢复本地配置 —— `.env` 本身也在离站备份里（`.env.*.bak.enc`，同一口令解密）
3. `docker compose up -d`，按仓库 README 走常规部署
4. 若要用 3.12 解释器跑同步（**默认 `python` 是 3.10，缺 `cryptography`，会静默失败**）：
   ```powershell
   powershell -ExecutionPolicy Bypass -File apps/desktop/scripts/server/install-offsite-scheduler.ps1 `
       -Root "<仓库根>\backups" -Time "03:30" `
       -PythonExe "C:\Users\pc\AppData\Local\Programs\Python\Python312\python.exe"
   ```
5. 首次触发后**必须确认日志真的生成了**（别只信 `LastTaskResult`，见下）

## 手动下载单个对象（脚本没封装下载）

`offsite-oss-sync.py` 有 scan / apply / cleanup / decrypt，**没有 download**。临时取回用一段
内联 Python（V1 签名，sign 与上传同一套）：

```python
import importlib.util, pathlib
spec = importlib.util.spec_from_file_location('oos', 'apps/desktop/scripts/server/offsite-oss-sync.py')
m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
c = m.load_credentials(None)                    # 读 OSS_* 环境变量
key = 'offsite-backup/microbubble/microbubble_20261011_020002.sql.gz.enc'
st, body = m._request(c, 'GET', key)          # 复用已验证的 V1 签名实现
assert st == 200, st
pathlib.Path('restore').mkdir(exist_ok=True)
pathlib.Path('restore')/pathlib.Path(key).name).write_bytes(body)
```

## 排障

| 现象 | 真因与处置 |
|---|---|
| `[FATAL] 口令文件不存在` | 口令没生成或不在 `.secrets/`。**不要**改脚本绕过 —— 没有降级路径是刻意的 |
| `[FATAL] 缺少必需配置: OSS_BUCKET...` | 计划任务账户读不到 **User 级**环境变量。任务主体必须是当前用户，不能是 SYSTEM |
| `[FATAL] 需要 cryptography` | 解释器选错。`python` on PATH 是 **3.10（无该包）**，须显式指向 Python312 |
| `[FATAL] 第 N 块 GCM 校验失败` | 口令错，或密文被篡改/块序乱。两者无法区分，如实报错 |
| 任务 `LastTaskResult=0` 但没日志 | **状态字段会骗人**。先看 `logs/offsite-sync-<日期>.log` 是否真的存在且非空 |
| `--cleanup` 删掉了别人的备份 | 必须带 `--subdir`（默认 `microbubble`）。桶内 `offsite-backup/说明.txt` 规则 1：每人一个子目录 |

## 已知的坑（都实测踩过，勿重复）

1. **加密信封常量必须定义在使用它的函数之前** —— `encrypted_size()` 把 `ENC_CHUNK_BYTES` 用作默认参数值，默认参数在 `def` 执行时即求值。`py_compile` 查不出，只有真 import 才炸。
2. **解密末块通常是短块** —— 加密侧 `fin.read()` 在 EOF 自然返回短块，解密侧必须按实际长度校验，否则任何非 8MiB 整数倍的文件都解不开（DB dump 实测 41~82MB，必然落在该区间）。
3. **失败后不留明文** —— 清理半成品必须在 `with` 块**外**（Windows 下句柄未关时 `unlink` 抛 `PermissionError`），且失败清理绝不能抛异常，否则掩盖真实原因。
4. **网络重试必须重新签名** —— V1 的 Date 头 15 分钟有效，退避后复用会拿到 `403 SignatureDoesNotMatch`，把可恢复的抖动变成不可恢复的失败。
5. **默认桶曾是公开桶** —— 旧版 `DEFAULT_BUCKET = mnb-workbench-releases`（electron-updater 匿名可读源）。现已零默认值 + fail-loud。**任何时候都不要给备份配默认桶**。

## 相关

- 脚本：`apps/desktop/scripts/server/offsite-oss-sync.py`
- 安装/更新任务：`apps/desktop/scripts/server/install-offsite-scheduler.ps1`
- 本地备份：`scripts/backup_db.sh` + `scripts/backup_scheduler.bat`（`MicroBubble-Daily-Backup`，每日 02:00）
- 桶内说明：`offsite-backup/说明.txt`（2026-09-20，全组约定）
