# Docker 数据布局与 C 盘腾挪 —— runbook（2026-10-22 建立）

> 本文件是**可复用的操作步骤**，随实际布局变化更新。"当前状态"只写在 `CLAUDE.md` 顶部段。
> 一次性取证过程见文末《取证台账》。

---

## 1. 现在的布局（2026-10-22 实测）

### Docker Desktop 的数据

```
E:\microbubble-agent\data\docker\
├── appdata\                 Docker 数据根（junction 的目标）
│   ├── wsl\
│   │   ├── main\ext4.vhdx   docker-desktop 发行版的 96 MB 系统盘
│   │   └── disk\docker_data.vhdx   62 GB 数据盘：全部镜像 / 容器 / 卷
│   ├── log\                 Docker Desktop 日志
│   ├── run\                 AF_UNIX socket 目录
│   └── tasks\
├── wsl\swap.vhdx            WSL 交换文件（8 GB），路径写在 .wslconfig
└── vhdx-backup\
```

指向它的两处 junction（**必须始终指向同一个物理目录**，见 §3.3）：

| 路径 | 指向 |
|---|---|
| `C:\Users\pc\AppData\Local\Docker` | `E:\microbubble-agent\data\docker\appdata` |
| `C:\Users\pc\AppData\Local\Packages\Claude_pzs8sxrjxfjjc\LocalCache\Local\Docker` | 同上 |

WSL 注册表里发行版的位置：

```
HKCU\Software\Microsoft\Windows\CurrentVersion\Lxss\{54d64d6e-...}
    DistributionName = docker-desktop
    BasePath         = \\?\E:\microbubble-agent\data\docker\appdata\wsl\main
```

> ⚠️ `BasePath` 带 `\\?\` 前缀，而 **`\\?\` 路径不穿越 reparse point**（实测
> `[System.IO.File]::Exists('\\?\E:\DockerData\_junctest\...')` = False）。
> ⇒ **凡是改动数据根的位置，必须同时改这条注册表值**，不能靠 junction 兜底。

### C 盘的构成（2026-10-22 实测）

| 路径 | 体积 | 归属 |
|---|---:|---|
| `AppData\Local\wsl\` | 56.6 GB | WSL 发行版 Ubuntu-24.04（55 GB）+ playwright（1.6 GB） |
| `AppData\Local\Temp\` | 原 57 GB | **LabCairn 测试 harness 的克隆目录**（`lcp*` / `lcr*`，约 500 个） |
| `.cache\codex-runtimes` | 4.7 GB | Codex CLI |
| `AppData\Local\Claude-3p\` | 10.6 GB | Claude Desktop 自身 |
| `AppData\Local\ms-playwright\` | 703 MB | Playwright 浏览器（可迁 E 盘） |
| `AppData\Local\electron\Cache` | 624 MB | `apps/desktop` 的 electron 二进制 |
| `AppData\Local\npm-cache\` | 190 MB | npm |
| `AppData\Local\electron-builder\Cache` | 83 MB | electron-builder 工具 |
| `Roaming\MicroBubbleWorkbench` | 15.6 MB | `apps/desktop` 的 Electron userData（**含会议附件与知识库原件**） |
| `AppData\Local\voice-alert-cache` | 0.3 MB | `scripts/voice-alert.ps1`（**无上限**） |

**本仓对 C 盘的贡献约 1.6 GB（占 C 盘 284 GB 的 0.57%）。**
Docker 的镜像/容器/卷**从来就不在 C 盘**（2026-06-17 已迁出，见 `memory/docker-desktop-fix-2026-06-17.md`）。

---

## 2. C 盘为什么会被填满

**腾挪结果（2026-10-22 实测）：C 盘可用 `13.8 GB → 60.0 GB`（95.4% → 80.0%）。**
搬走的是 10,249 个 `%TEMP%` 条目（`E:\_displaced_temp_20261022`，**搬走不删**，带
`MANIFEST.txt`）；`%TEMP%` 里剩下的 687 个是**正在使用**的（含一个并行 LabCairn 会话的
当前夹具），不动。

| 灌水点 | 机制 | 处置 |
|---|---|---|
| **LabCairn 的测试 harness** | 每次跑测试把仓库克隆进 `%TEMP%\lcp*`（实测 506 个、35 GB，且**仍在持续产生**，最新目录的 mtime 是测量前 2 分钟） | **用户级 `TEMP`/`TMP` 改指 `E:\microbubble-agent\data\tmp`**；存量的搬往 `E:\_displaced_temp_20261022` |
| WSL Ubuntu-24.04 | `E:\dft-service` 的 `wsl pkill` 跑在默认发行版里 ⇒ **在用，不能迁**（类 20.212：判据是被引用，不是名字与年龄） | 保持不动 |
| `apps/desktop` 的 electron / electron-builder 缓存 | 每次版本升级重新下载到 `%LOCALAPPDATA%` | `ELECTRON_CACHE` / `ELECTRON_BUILDER_CACHE` → `E:\microbubble-agent\data\` |
| `apps/desktop` 的 Electron userData | Chromium Cache + **会议附件、知识库原件、workbench.db** | `MNB_USER_DATA` → `E:\microbubble-agent\data\desktop-userdata` |
| Playwright 浏览器 | 一次性 703 MB | `PLAYWRIGHT_BROWSERS_PATH` → `E:\microbubble-agent\data\ms-playwright` |
| npm cache | 每次 `npm run build` | `npm config set cache E:\microbubble-agent\data\npm-cache` |
| `voice-alert.ps1` 的 MP3 缓存 | **无上限、无清理** | 改到 `data\voice-alert-cache` + LRU 50 个 |
| `offsite-oss-sync.py` / `rotate_offsite_passphrase.py` 的临时文件 | `tempfile` 默认落 `%TEMP%`（C 盘）；**后者解出的是明文** | `mkdtemp(dir=)` → E 盘 |

### 已落地的代码层改造（2026-10-22）

> ⚠️ 下表的"实测"列是**真的执行过**的结果，不是"应该能work"。
> 可复跑：`python scripts/ci/verify_c_drive_changes.py`

| 文件 | 改动 | 实测（执行结果） |
|---|---|---|
| `scripts/voice-alert.ps1` | 缓存目录 `$env:LOCALAPPDATA\voice-alert-cache` → `$ProjectRoot\data\voice-alert-cache`；加 LRU（只留最近 50 个 MP3） | 塞 55 个假 MP3 → 跑一次 → **裁到 50**，保留的是最新的 3 个 ✓ |
| `apps/desktop/scripts/server/offsite-oss-sync.py` | `mkdtemp(prefix="offsite-enc-")` → 加 `dir=_TMP_ROOT`（`data\tmp`） | `mkdtemp` 实际建在 `E:\...\data\tmp\verify-oos-*` ✓；`--scan` **真跑通**（读真凭证、扫真备份目录、识别出 2 个待上传的加密文件）✓ |
| `scripts/backup/rotate_offsite_passphrase.py` | `NamedTemporaryFile` 与 `mkdtemp(prefix="verify-")`（**里面是明文**）都加 `dir=_TMP_ROOT` | 两种临时文件都实测建在 `E:\...\data\tmp\` ✓ |
| `app/services/audio_processor.py` | `import torch` **之前**设 `TORCH_HOME`（**仅 Windows 宿主**，容器内是 Linux 路径语义不能设） | 实跑 `segment_audio`：`TORCH_HOME=E:\microbubble-agent\models\torch_hub`，日志 `Using cache found in E:\...\models\torch_hub\hub\snakers4_silero-vad_master` ⇒ **模型真的从 E 盘加载** ✓ |
| `apps/desktop/package.json` + `scripts/lib/cache-env.mjs` + `scripts/with-cache-env.mjs` | `pack`/`dist` 与 `release.mjs` 注入 `ELECTRON_CACHE` / `ELECTRON_BUILDER_CACHE` | **A/B 对照**：过 wrapper 两个变量指向 E 盘且 PATH 含 `node_modules/.bin`；不过 wrapper 两者皆 `undefined` ✓ |
| `.pnpmfile.cjs`（**仓库根**） | pnpm 的生命周期子进程继承 pnpm 进程的 env ⇒ 在这里设同一组变量，覆盖 `pnpm install` 路径 | 实跑 `pnpm --filter @mb/desktop exec node -e ...` → 子进程里两个变量**都被注入** ✓；⚠️ 实测 pnpm 9.15.9 加载的是 `.pnpmfile.cjs`（**带点**），不是 `pnpmfile.cjs` —— 一次性目录里同时放两个文件实测，只有带点的那个被加载 ✓ |
| `apps/desktop/src/main/index.ts` | 不改代码：用用户级 `MNB_USER_DATA` 环境变量驱动已有的 `MNB_USER_DATA` 开关 | 用户级 `MNB_USER_DATA` 已设且指向 E 盘；`workbench.db`(258,048 B) 与 `session-token.enc` 已到位 ✓；⚠️ **本进程仍读到旧值**（它早于改动启动）—— 新进程才拿得到 |

**用户级环境变量（已写入，机器重启后仍生效）**

| 键 | 值 |
|---|---|
| `TEMP` / `TMP` | `E:\microbubble-agent\data\tmp` |
| `ELECTRON_CACHE` | `E:\microbubble-agent\data\electron-cache` |
| `ELECTRON_BUILDER_CACHE` | `E:\microbubble-agent\data\electron-builder-cache` |
| `PLAYWRIGHT_BROWSERS_PATH` | `E:\microbubble-agent\data\ms-playwright` |
| `MNB_USER_DATA` | `E:\microbubble-agent\data\desktop-userdata` |

⚠️ **已在运行的进程不会自动切换**：Claude Desktop 及其子进程（含那个并行 LabCairn 会话）
仍持有旧的 `%TEMP%`，**要等它们重启**才会改用 E 盘。

⚠️ `npm config get cache` 实测是 **`D:\npm-cache`**（不是 C 盘默认路径）⇒ **不要改**。


---

## 3. 2026-10-22 Docker 崩溃事故：完整根因链

当天 05:06 起 Docker Desktop 反复崩溃，13 个容器全停，本地 API 不可用。**根因有四层，逐层剥开**：

### 3.1 第一层：空闲自动暂停后的恢复失败

```
[05:06:51] Got an error resuming Docker Desktop:
           seeking `/sys/fs/cgroup/procd-paused/cgroup.procs`
```

Docker Desktop 空闲后把 WSL VM 暂停，恢复时读 paused cgroup 失败 → backend 崩溃。

### 3.2 第二层：守护脚本把一次崩溃放大成一场雪崩

`scripts/docker-guard.ps1` 原来的升级阶梯是 L1 清 `.stale` → L2 重启 Docker → L3 `wsl --unregister docker-desktop`。实测日志显示 **55 秒内触发了 3 次 L2**（05:11:02 / 05:11:09 / 05:11:57），**2.4 分钟内触发了 2 次 L3**（05:15:38 / 05:18:00）。

两个独立的并发来源：

1. **计划任务的动作是 `wscript.exe`**，而 `scripts/run-hidden.vbs:48` 用
   `shell.Run cmd, 0, False`（`bWaitOnReturn = False`）启动 powershell ——
   **wscript 立刻退出**，任务计划程序于是认为动作已完成，5 分钟后又起一个，
   而上一个 PowerShell 还在跑。`MultipleInstances=IgnoreNew` 只看得到 wscript 进程。
2. **L3 的 30 分钟闸门读 `state.json`，而 `Set-State` 是"读-改-写"**：
   `Set-Content` 先截断再写，读者会读到半个文件 ⇒ `Get-State` 返回 `$null`
   ⇒ 闸门当成"从没跑过"⇒ 放行。

⇒ 每个并发实例都会 `Stop-Process` 掉 Docker 再拉起新的 ⇒ **两个 backend 实例争抢同一个 AF_UNIX socket**。

### 3.3 第三层：L3 本身无效，且它制造了下一个故障

`wsl --unregister docker-desktop` **只注销注册，不删 `main\ext4.vhdx` 这个 96 MB 系统盘**（脚本自己的旧注释就写着"实测注销后该文件大小/mtime 不变"）。

⇒ 下次启动时 Docker 的 `wslmigrate` 判定 **"WSL2 disk exists"** → **跳过 provisioning 分支** → 去复用一个已被注销、无法挂载的发行版 → 引擎永远起不来。

**日志对比（决定性证据）**：

| | 成功那次 | 之后每次 |
|---|---|---|
| wslmigrate | `provisioning the WSL2 engine using a data disk` | `WSL2 disk exists` |
| distro | `docker-desktop not found, skipping terminate` → `copied distribution` → `setting up data disk` → `running bootstrap` | 无 |
| socketforward | `connected to WSL distro docker-desktop` | 无 |
| 结果 | **13 个容器全部健康** | `backend crashed ... AF_UNIX listen ... bind: Only one usage of each socket address` |

⇒ **实测有效的恢复配方**（指挥方 06:41–06:49 一次跑通）：

```bash
# a. 停掉所有 Docker 进程，并确认真的停了
taskkill /F /IM "Docker Desktop.exe" /IM com.docker.backend.exe /IM com.docker.build.exe
# b. WSL 彻底关停
wsl --shutdown
# c. 注销发行版（注意：这一步会把整个 main\ 目录连同 ext4.vhdx 一起删掉，
#    正是它让 Docker 下次走 provisioning 分支）
wsl --unregister docker-desktop
# d. 确认 wsl\main\ext4.vhdx 已不存在、而 wsl\disk\docker_data.vhdx（62 GB）完好
# e. 确认 run\ 目录存在且为空
# f. 启动 Docker Desktop
```

### 3.4 第四层：AF_UNIX socket 冲突的真实机制（最隐蔽的一层）

崩溃报 `bind: Only one usage of each socket address`，但：

- `run\` 目录在 **Win32 侧和 Linux 侧枚举都是空的**（没有残留文件）；
- `Remove-Item -Force` 删 socket 文件会**静默失败**（error 1920）—— 这是
  [docker/desktop-feedback#460](https://github.com/docker/desktop-feedback/issues/460) 描述的行为：
  AF_UNIX socket 是 **NTFS reparse point**，非正常退出后残留的 0 字节文件删不掉，
  而且**对 `Get-ChildItem` / `ls` 不可见**，却仍然占着 AF_UNIX 地址。

真正的机制是 **`%LOCALAPPDATA%\Docker` 存在两个视图**：

```
C:\Users\pc\AppData\Local\Docker                                   ← 真实路径
C:\Users\pc\AppData\Local\Packages\Claude_*\LocalCache\Local\Docker ← MSIX 包重定向视图
```

Docker Desktop 启动**两个** backend 进程（主进程 + `services` 子进程）。当两者把
`%LOCALAPPDATA%\Docker` 解析成**两个不同的字符串但指向同一个物理目录**时，
它们会绑同一个物理 socket ⇒ 后绑的那个必然 `EADDRINUSE`。

⇒ **治本的是 junction，不是 socket 文件**：两个视图必须**始终指向同一个物理目录**。
现在两处都是 junction，都指向 `E:\microbubble-agent\data\docker\appdata` ✓。

#### ⚠️ MSIX 包重定向陷阱（本次最贵的教训）

**Claude Desktop 是 MSIX 包。它启动的进程里，`C:\Users\pc\AppData\Local\<X>` 会被重定向到
`C:\Users\pc\AppData\Local\Packages\Claude_pzs8sxrjxfjjc\LocalCache\Local\<X>`。**

⇒ 后果一：2026-06-17 那个"把 Docker 挪到 E 盘"的 junction 是在**包上下文**里建的，
所以它落在 `...\LocalCache\Local\Docker`，**真实路径下根本没有这个 junction**。
⇒ 后果二：本次排查中我多次用 PowerShell 删/建 `%LOCALAPPDATA%\Docker\run`，
**全都作用在包视图上**，真实路径毫发无损 —— 所以"我明明删过了"却一直复现。
⇒ 后果三：Docker Desktop 若从包上下文启动，就会去包视图找数据根，真实路径的 junction 形同虚设。

**⇒ 纪律：凡要动 `%LOCALAPPDATA%` 下的东西，必须用「非包上下文」的进程。**
本仓已有现成做法：

```powershell
# scripts/ci/run-one-shot-task.ps1 —— 通过计划任务跑一个脚本，拿到干净的上下文
powershell -ExecutionPolicy Bypass -File scripts\ci\run-one-shot-task.ps1 `
    -ScriptPath E:\microbubble-agent\scripts\ci\<某个>.ps1
```

（判别方法：`Get-Item 'C:\Users\pc\AppData\Local\Docker' -Force` 的 `.Target`
在包上下文里会显示成 `...\Packages\Claude_*\LocalCache\Local\Docker\...`。）

**⇒ 另注：WSL 的 9P 驱动看不到跨卷 junction** ——
`wsl -d Ubuntu -- ls /mnt/c/Users/pc/AppData/Local/Docker` 报 `No such file or directory`，
**不代表该路径不存在**，只代表它指向 E:（出了 9P 的挂载范围）。
要确认真实路径请用 Windows 侧 API。

---

## 4. 常用操作

### 4.1 日常检查

```bash
docker info                                   # daemon 是否活着
docker ps -a --format '{{.Names}}\t{{.Status}}'
curl -s http://127.0.0.1:8000/health          # 期望 {"status":"healthy"}
powershell -NoProfile -Command "Get-ScheduledTask -TaskName 'MicroBubble-Docker-Guard' | Select-Object State"
```

### 4.2 守护脚本自愈阶梯（2026-10-22 重写后）

> **已做真实故障注入验证（2026-10-22 14:01）**，不是只做过静态检查。
> 注入方式：杀掉全部 `com.docker.backend` 进程（daemon DOWN、0 容器运行），
> 然后**不干预**，等计划任务自己那一轮：
>
> ```
> 14:01:02 WARN  Docker daemon unavailable, escalating   {'detail': 'docker info exit 1', 'from_level': 'OK'}
> 14:01:07 INFO  L0 system disk ACL repaired             {'granted 27 SID(s) ... RESULT: OK'}
> 14:01:07 INFO  L0 runtime socket dirs moved aside      {'moved': [真实路径\Docker\run, 包重定向路径\Docker\run, docker-secrets-engine]}
> 14:01:18 INFO  Docker came up after L0                 {'containers_running': 13, 'containers_total': 13}
> ```
>
> **⇒ 16 秒完成自愈，全程无人干预。** 关键细节：杀 backend 时系统盘
> `main\ext4.vhdx` 的 **27 个 `S-1-5-83-1-*` ACE 已经被剥掉了**（正是 2026-10-19 事故的
> 成因），L0 在 WSL 挂载失败之前就把它补了回来 —— 这次 ACL 修复不是"预防性代码"，
> 是**当场救了场**。
>
> 自愈后与注入前逐项比对：**13 个容器 ID、14 个镜像 ID+tag、10 个卷名全部逐一相同**；
> 数据库 `meetings=28 / members=36 / knowledge=884 / chunks=519` 一致；
> `app:8000/health` 与生产域名 `agent.mnb-lab.cn/health` 均 200。
>
> ⚠️ **「Docker 恢复了」≠「业务已就绪」**：守护脚本的判据是 `docker info` + `docker ps`
> （Docker 层），而数据库重启后要做 pre-fsync 恢复、业务端点还要再等 1–2 分钟
> （实测 14:01:18 Docker 恢复 → 14:02:47 app 才 healthy）。

| 级 | 做什么 | 破坏性 |
|---|---|---|
| **L0** | 停进程并**轮询到真的停了** → `wsl --shutdown` → **修 `main\ext4.vhdx` 的 ACL** → 把 `run` / `docker-secrets-engine` **改名**为 `.stale-<时间戳>` → 重建空 `run` → 启动 Docker → 等 120 s | 无 |
| **L1** | 删 `run\` 里的 `*.stale*` 残留 | 无 |
| **L2** | 重启 Docker Desktop（**必须等旧进程真的退出**才启新的） | 无（容器会重启） |
| **L3** | `wsl --unregister` → **确认 `main\ext4.vhdx` 已不存在**（残留就改名）→ 确认 62 GB 数据盘仍在且大小未变 → 重建空 `run` → 启动 Docker | **有**（但数据盘不动） |

配套的三个结构性修复：

- **全局互斥锁** `Global\MicroBubbleDockerGuard` —— 第二个实例立刻退出。
- **L3 闸门独立成文件**（`logs/docker-guard/l3-gate.json`）+ **原子写**（`MoveFileEx` /
  `File.Replace`，**不是 `Set-Content`**）+ **原子抢占**（`FileMode.CreateNew`）。
  ⚠️ 实测并发读压测：`Move-Item -Force` 产生 **143 次**破读，`Set-Content` 更会直接抛
  IOException；`MoveFileEx` 与 `File.Replace` 都是 **0 次**。
- **判定"恢复了"验副作用**：`docker info` **且** `docker ps` 都成功才算恢复；
  只看退出码会把僵尸 daemon 当成健康。
- **AF_UNIX 前提守卫**：每次运行都检查两个 `%LOCALAPPDATA%\Docker` 视图是否同源，
  **不一致时拒绝执行破坏性的 L3**（那种状态下重建发行版也救不了）。

### 4.3 ACL 修复

```powershell
# WSL 把每个 VM 的 app-container SID（S-1-5-83-1-*）直接授权在 .vhdx 文件上
# （不继承自父目录）。实测：数据盘 27 个，系统盘 0 个 ⇒ WSL 挂载发行版报
# Wsl/Service/CreateInstance/MountDisk/HCS/E_ACCESSDENIED ⇒ Ingest server 起不来。
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\ci\fix-docker-wsl-vhdx-acl.ps1
```

### 4.4 改数据根的位置（会踩的坑）

1. Docker Desktop 必须**完全停掉**，`wsl --shutdown`。
2. 同卷搬迁用 `Move-Item`（瞬时重命名，**ACL 完整保留、零拷贝**）。
3. **必须同步改**：`Lxss` 注册表的 `BasePath`（`\\?\` 前缀不穿 junction）、
   `.wslconfig` 的 `swapFile`、以及**两处** `%LOCALAPPDATA%\Docker` junction。
4. **两处 junction 必须同源**，否则 backend 必以 `AF_UNIX EADDRINUSE` 崩溃。
5. 用 `scripts/ci/run-one-shot-task.ps1` 走计划任务执行 —— 包上下文会改写 `%LOCALAPPDATA%`。
6. 启动后验：`docker ps` 13 个容器、镜像 ID 与基线逐一相同、`docker system df` 数值不变。

### 4.5 本次用到的脚本

| 脚本 | 性质 | 作用 |
|---|---|---|
| `scripts/ci/run-one-shot-task.ps1` | 常备 | 通过计划任务跑一个脚本，拿到非 MSIX 包的干净上下文（**动 `%LOCALAPPDATA%` 前必用**） |
| `scripts/ci/fix-docker-wsl-vhdx-acl.ps1` | 常备 | 修 `main\ext4.vhdx` 的 WSL app-container ACL（幂等；守护脚本 L0 会调它） |
| `scripts/ci/docker-clean-start.ps1` | 常备 | 单实例干净启动 Docker，打印关键日志行与容器状态 |
| `scripts/ci/docker-restart-clean-context.ps1` | 常备 | 修包重定向视图的 junction + 从干净上下文启动 Docker |
| `scripts/ci/docker-rename-run-dir.ps1` | 常备 | 把 `run` / `docker-secrets-engine` 改名让位（不删 reparse point） |
| `scripts/ci/probe_localappdata_docker.ps1` | 常备 | 在干净上下文里看清 `%LOCALAPPDATA%\Docker` 到底是什么（MSIX 陷阱探测器） |
| `scripts/ci/probe-new-temp.ps1` | 常备 | 验证新进程拿到的 `%TEMP%` 已是 E 盘且可写 |
| `scripts/ci/test-docker-guard.ps1` | 常备 | 守护脚本的 44 项单元测试（用 AST 抽纯函数，**不执行守护脚本本身**） |
| `scripts/ci/verify_c_drive_changes.py` | 常备 | **实跑**验证防回流改动：tempfile 落点、TORCH_HOME 真加载模型、桌面端 userData 迁移 |
| `apps/desktop/scripts/ci/probe-cache-env.mjs` | 常备 | 探针：给 `with-cache-env.mjs` 用，打印子进程看到的缓存环境变量 |
| `scripts/ci/move-docker-data-to-project.ps1` | 一次性（已执行） | 把 Docker 数据根搬进项目目录（改注册表 BasePath + `.wslconfig` + junction） |
| `scripts/ci/redirect-temp-off-c.ps1` | 一次性（已执行） | 用户级 `TEMP`/`TMP` 改指 E 盘 + 存量搬迁 |
| `scripts/ci/rollback-dockerdata-junction.ps1` | 一次性（已执行） | 迁移中途回滚用的 junction 拆除 + 目录复原。**现在跑是安全的**：它的目标路径已不存在，只会 fail-loud |

> ⚠️ **本轮实测后删掉了三个脚本**，理由都是"看着有用、实际会坑人"：
> - `docker-unlink-run-dir.ps1`、`docker-restore-layout.ps1` —— 用来检验
>   "junction 导致 AF_UNIX 冲突"这个假设的实验脚本，**假设已被证伪**（真正成因见 §3.4）。
>   它们会把当前可用的 junction 布局拆掉 —— 正是守护脚本现在要守卫的不变量。
> - `recover-docker-wsl-distro.ps1` —— 路径还写着已删除的 `E:\DockerData\appdata`、
>   **从不启动 Docker**、**不做 ACL 修复**（正是它本该修的那个坑）、
>   且用 `Set-Content -Encoding UTF8` 改 Docker 的 `settings-store.json`
>   （PS 5.1 会写入 BOM）。
>
> ⇒ **保留一条已实测通过的恢复路径（守护脚本 L0/L3），好过留两条其中一条是坏的。**
> 机制留在本文 §3 的文字里即可，不需要留成可执行脚本。

---

## 5. 取证台账（一次性，可不复用）

- Docker 在 C 盘的历史：`memory/docker-desktop-fix-2026-06-17.md`、
  `docs/CHANGELOG-history-2026-07-23.md`（"Docker 数据全量迁移 E 盘 … C 盘 0 字节占用"）。
- 本次的完整时间线、日志对比、以及三个 agent 的审计报告，见本次会话记录。
- 审计结论：本仓对 C 盘的足迹 ≈ 1.6 GB；C 盘其余是别的项目（LabCairn、Codex、Claude Desktop）
  或系统设施（WSL）。
