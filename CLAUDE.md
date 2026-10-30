# MicroBubble Agent - 项目上下文
## 项目简介

> **怎么读这个文件**（2026-09-30 三层重排后）：本文件分三层，按需读到哪层就停：
>
> | 层 | 内容 | 位置 |
> |---|---|---|
> | **现状** | 唯一描述现在什么状态的段落 | 顶部 `## 当前状态` |
> | **规范与铁律** | 架构决策 / 代码质量 / 服务层 / **永久铁律（类 20.xx）** | 文件中段，各 `##` 段 |
> | **档案** | 18 段历史状态快照（每段曾自称"当前"，实为当时快照） | `docs/incident/2026-08-04--2026-09-18-status-snapshots.md` |
>
> - 想知道"现在该怎么做" → 读顶部现状段 + 中段规范，**不必**翻档案
> - 想知道"当初为什么这么定" → `grep -n "类 20\." CLAUDE.md`（铁律本体在本文件中段）
> - 想知道"某次事故的完整过程" → `docs/incident/` 或 `docs/history/`
> - 想找其他项目文档 → **[`docs/README.md`](docs/README.md)**（按性质查找表 + 各目录权威性对照）

## 当前状态 (2026-10-26 所有模型改为按需启动 —— 显存从 31.5G 降到个位数 G)

> 主指挥决策: **本项目所有模型不常驻, 按需启动, 不用时释放显存**。
> 这反转了 v31.3 起「SenseVoice 常驻」的老设定。

### A. 改了什么（逐组件）

| 组件 | 原来 | 现在 |
|---|---|---|
| **SenseVoice**（容器, `app/sensevoice_server.py`） | `lifespan` 启动即加载 + 永不卸载（`resident_mode: true`） | 启动**不加载** → 首次 `/transcribe` 按需加载 → 空闲 600s 自动卸载并 `empty_cache()` |
| **embedding**（Qwen3-Embedding-0.6B, `app/services/embedding_service.py`） | app 启动时后台**预载**（`main.py` 的 `_warmup_embedding_background`）⇒ 常驻 | 启动**不预载**（该 create_task 已删）→ 首次检索按需加载 → 空闲 600s 自动卸载 |
| **reranker**（bge-reranker-v2-m3, `app/services/reranker_service.py`） | 惰性加载但**永不卸载** | 惰性加载 + 空闲 600s 自动卸载（`rerank()` 每次刷新活跃时间，防误卸正在用的模型） |
| **VibeVoice 流式 ASR**（`app/gpu_worker/streaming_server.py`） | 已有「按需 + 空闲 600s 卸载」机制 | 机制不变；**但发现 10-24 起的那个实例 loaded=true 而 active_sessions=0** ⇒ 白占显存，已重启该服务解决 |
| **VibeVoice 批处理 ASR**（`app/gpu_worker/server.py`） | 设计上「守护器自身不占显存, 子进程退出即归零」 | 不变（实测守护器 RSS 仅 6MB, 符合设计） |
| **ollama** | 按需 + `OLLAMA_KEEP_ALIVE=30m` | 不变（`ollama ps` 为空 ⇒ 未加载） |

### B. 实现要点（三处都是同一套模式）

1. **启动不加载**，只在**首次请求**时加载（`_ensure_model_loaded_async` / `_get_model`）。
2. **加锁 + 双检** ⇒ 并发首请求只有一个真的加载，其余等同一把锁拿同一实例（否则重复吃一份显存）。
3. **空闲自动卸载**：daemon 线程每 30s 检查「距上次使用 > 600s 且无活跃请求」⇒ 卸载 + `torch.cuda.empty_cache()`。
4. **活跃计数/时间戳**必须随每次使用刷新 ⇒ 否则会把「正在用的模型」误判为空闲而卸掉。
5. **调用方透明**：`app/voice/asr.py` 的健康检查只看 `/health` 的 **HTTP 200**（不看 `model_loaded`），
   转写请求超时 600s ⇒ 首次那次 ~19-36s 的加载完全在预算内。
6. ⚠️ **保留 `_warmup_ml_imports`**（`main.py`）：它只让 torch/transformers 进 `sys.modules`，**不占显存**，
   但能避免首屏 import 冻结事件循环（2026-09-14 事故）—— 与「模型不常驻」不冲突，别一起删掉。

### C. 实测

- 改前整卡 **31510 / 32607 MiB（96.6%）**；重启流式 ASR（释放 VibeVoice 7B）后降到 **18444 MiB**。
- sensevoice 按需加载实测：加载 36.0s（其中模型 28.6s）、二次调用 **0.000s**（不重复加载）、卸载后显存回落。
- 三个服务重启后 `/health`：`model_loaded: False, resident_mode: False, lazy_mode: True, idle_unload_sec: 600`。

### D. 新增永久铁律

见下方 **类 20.237**（模型常驻/按需的判定、实现与验证纪律）。
### D2. 同一天另外三件事（同属 2026-10-26，一并记在这里以免「当前状态」只反映一件）

**① 会议 259 入库（10-19 组会）**：微信接收目录里三份音频查重后**两份是重复**
（`三问园.m4a` = 已入库的 256、`三问园 2.m4a` = 257 —— **文件名相同不等于同一场**，
256/257 都在三问园录过），只有压缩包里的 `10.19_1.m4a`（3424s）是新的。
走**生产 API 四步链**入库（start-recording → audio-chunk → merge-chunks(auto→raw 字节拼接)
→ stop-recording），产物全套达标：摘要 321 字 / 要点 8 条 / 决议 6 条 / 转录 355 段 /
`meeting_chunks` 22 行 / 声纹认出王天志 271 轮 + 蒋芦笛 83 轮。
⚠️ **脚本导入的 `audio_duration` 记的是「导入耗时」不是录音时长**（本例 3 秒）⇒ 入库后要手改成
`media_duration_seconds`；前端优先读 media，显示不受影响。

**② 前端失败态 UI（桌面 + 移动端）**：新增 `web/src/utils/meetingFailure.js`，把 `error_reason`
归成 5 类失败、翻译成**用户能据此行动**的话，并给出补救动作判定；两端各加一张失败卡片
（标题 / 说明 / 技术详情折叠 / 补救按钮）。改前：桌面只有一枚「处理失败」徽标，
移动端**直接把裸技术串**（「录音超过 30min 未 stop, (last_chunk_index=-1, total_chunks=None),
[UA: ...]」）甩给用户；而后端早有 `reprocess` 补救能力、前端一处都没调用
⇒ 用户看到失败会议**完全无法自救**。补救动作判定与后端守卫同源
（`audio_url` 非空 或 `last_chunk_index >= 0`），否则会出现「前端显示可重试、后端回 400」。

**③ 云端磁盘 100% 满 ⇒ 部署静默中止 10 天（事故，见 `docs/incident/2026-10-25-cloud-disk-full-silent-deploy-failure.md`）**：
pm2 托管的 staging 实例缺 `JWT_ACCESS_SECRET` 启动即崩，**无限重启把同一段堆栈刷成 18 GB 日志**
⇒ 根分区 40G 满(Avail=0) ⇒ `deploy-auto.sh` 的磁盘检查自 **2026-10-15 起每次 push 都中止**
（6+ 次静默失败），磁盘满还让 webhook 连日志都写不进去 ⇒ **push 事件彻底丢失**。
⇒ 现象是 **push 成功 + CI 全绿 + 生产 `/health` 200，但生产跑的是旧版本** ——
**三个信号全对也骗人**，唯一硬判据是**比对生产首页的资源指纹与本地 `web/dist/index.html` 的指纹**。


### E. 2026-10-26 追加：停用三个无生产引用的容器 + 修掉 sensevoice 的 healthcheck 判据

**停用（`docker compose stop`，只停不删，定义保留、随时可起）**：

| 容器 | 内存 | 停用依据（查的是**生产链路引用**，不是 `depends_on`） |
|---|---|---|
| `ollama` | 516 MiB | `.env` 的 `LLM_BACKEND=openai_compat` ⇒ **ollama 后端代码路径根本不激活**（`app/core/llm.py` 只在 `backend == "ollama"` 时才走）；它只是「切回离线 batch 前要先起容器」 |
| `langfuse` | 148 MiB | 仅 LLM 调用追踪，`app/core/llm.py` 里 import 失败即 no-op ⇒ 停用只失去可观测性，不影响业务 |
| `pg-exporter` | 2.4 MiB | **全机没有 Prometheus/Grafana 采集端**（`observability/` 只有配置目录，无容器）⇒ 指标无人采集 |

⇒ 三者合计约 **667 MiB** 内存。`docker compose up -d` 会把它们再拉起。

**没停的（各有生产引用）**：`app`（隧道终点）/ `db` / `minio`（音频·头像·知识库原件）/ `redis` /
`nginx` / `celery-worker` / `celery-meeting-worker`（会议转写流水线）/
`sensevoice`（**ASR 回退路径**——GPU 7B 优先、它兜底）/ `neo4j`（实体知识图谱）/ `celery-beat`（定时调度）。
⇒ 停 `neo4j` / `celery-beat` / `sensevoice` 需主指挥单独拍板（各有功能代价）。

**⚠️ 顺带修掉一个我自己引入的回归**：sensevoice 改成按需加载后，原 healthcheck 判
`model_loaded` ⇒ **模型常态不加载 ⇒ 容器永远 unhealthy**（`docker ps` 显示 unhealthy，
却没有任何服务 `depends_on` 它要 `service_healthy` ⇒ 不会卡住别人，但状态字段在说谎的镜像版）。
⇒ 判据改为 **`service_ready`**（lifespan 已完成 ⇒ 服务可应答、模型可按需加载）；
`/health` 新增 `service_ready` 字段；同时把 `status` 由「模型是否加载」改为「服务是否就绪」
（否则会与 `docker ps` 的 healthy 自相矛盾）。实测：`status=healthy, model_loaded=False,
service_ready=True`，容器 **healthy**；重建后转写仍 HTTP 200 / 29.7s / 内容正确。


---

## 当前状态 (2026-10-22 Docker 数据进项目目录 + C 盘从 13.8G 腾到 60G + 守护脚本重写)

> 上一版"当前状态"停在 2026-10-13 声纹段；本节是 2026-10-22 这一天的产出。
> **本节最值钱的是「四层根因链」与「两个 Windows 假象」** —— 前者解释了一次
> 让 13 个容器停摆两小时的崩溃，后者会让排查整整绕一小时。

### A. Docker 数据已整体搬进项目目录（71 GB）

```
E:\microbubble-agent\data\docker\
├── appdata\wsl\disk\docker_data.vhdx   62 GB 数据盘（全部镜像/容器/卷）
├── appdata\wsl\main\ext4.vhdx           96 MB 发行版系统盘
├── appdata\{log,run,tasks}\             Docker 运行时目录
└── wsl\swap.vhdx                        8 GB WSL 交换文件
```

- **`E:\DockerData\` 已整个删除**；同名 junction 现指向
  `E:\microbubble-agent\data\docker\appdata`。
- ⚠️ **`%LOCALAPPDATA%\Docker` 有两个物理视图**（真实路径 + MSIX 包重定向路径），
  **两者必须同源**，否则 backend 必以 `AF_UNIX EADDRINUSE` 崩溃（见 D 段）。
- ⚠️ `Lxss` 注册表的 `BasePath` 带 `\\?\` 前缀，**该前缀不穿越 reparse point**
  ⇒ 搬数据根时**必须同步改注册表**，不能靠 junction 兜底。
- 同卷搬迁用 `Move-Item`（瞬时重命名，**ACL 完整保留、零拷贝**）。
- **runbook**：[`docker-data-layout-and-c-drive-2026-10-22.md`](docker-data-layout-and-c-drive-2026-10-22.md)

### B. C 盘腾挪：13.8 GB → 60.0 GB 可用（95.4% → 80.0%）

**用户级 `TEMP`/`TMP` 已改指 `E:\microbubble-agent\data\tmp`**（原先是
`C:\Users\pc\AppData\Local\Temp`）。存量 `lcp*`/`lcr*` 克隆目录已搬往
`E:\_displaced_temp_20261022`（**搬走不删**，带 `MANIFEST.txt`；实测 10,249 个条目）。
⚠️ 搬迁只动**6 小时前**修改的目录 ⇒ 正在跑的 LabCairn 会话（"Symlink 逃逸访问修复"）
的当前夹具**原封未动**（实测 108 个仍在原处、mtime 是几分钟前）。
⚠️ 那批目录含**悬空符号链接**，robocopy 必须加 `/SL`（默认跟随符号链接会 rc=9 失败）。

- **真正的灌水点不是本仓**：那 506 个 `lcp*` 目录是 **LabCairn**（`E:\LabCairn`）的
  测试 harness 克隆自己产生的，**测量时最新目录的 mtime 是 2 分钟前** ⇒ 一直在涨。
  ⇒ 光改本仓代码堵不住，**必须改 `%TEMP%`**。
- ⚠️ **Ubuntu-24.04 WSL 发行版（55 GB）在用，不许动**：`E:\dft-service` 的
  `wsl pkill` 跑在默认发行版里（类 20.212：判据是**被引用**，不是名字与年龄）。
- **本仓对 C 盘的足迹 ≈ 1.6 GB（占 284 GB 的 0.57%）**：electron Cache 624 MB、
  electron-builder 83 MB、ms-playwright 703 MB、npm-cache 190 MB、
  Electron userData 15.6 MB（**含会议附件与知识库原件**）、voice-alert 0.3 MB。
- **Docker 的镜像/容器/卷从来就不在 C 盘**（2026-06-17 已迁出，
  `memory/docker-desktop-fix-2026-06-17.md` + `docs/CHANGELOG-history-2026-07-23.md`）。
  "C 盘有 92 GB Docker"这个前提**不成立**。

### C. `scripts/docker-guard.ps1` 重写（213 → 1238 行，44 项单元测试全过）

新阶梯 **L0（非破坏性新增）→ L1 → L2 → L3（重写）**：

- **L0**：停进程并**轮询到真的停了** → `wsl --shutdown` → **修 `main\ext4.vhdx` 的 ACL**
  → 把 `run`/`docker-secrets-engine` **改名**（不删）→ 重建空 `run` → 启动 → 等 120 s。
- **L3 重写为实测配方**：`wsl --unregister` → **确认 `main\ext4.vhdx` 已不存在**
  （残留就改名，让 Docker 走 provisioning 分支）→ 确认 62 GB 数据盘仍在且大小未变
  → 重建空 `run` → 启动。
- 三个结构性修复：**全局互斥锁**（第二个实例立刻退出）/ **L3 闸门独立成文件 + 原子写 +
  原子抢占**（`state.json` 不再参与判断）/ **判定"恢复了"要验副作用**
  （`docker info` **且** `docker ps` 都成功）。
- 每次运行都检查 **AF_UNIX 前提**（两个 `%LOCALAPPDATA%\Docker` 视图是否同源），
  **不一致时拒绝执行破坏性的 L3**。
- ⚠️ 实测：并发读压测下 `Move-Item -Force` 产生 **143 次**破读、`Set-Content` 会直接抛
  IOException；**`MoveFileEx` 与 `File.Replace` 都是 0 次** ⇒ 原子写必须用后者两个。
- 单元测试：`scripts/ci/test-docker-guard.ps1`（用 AST 抽纯函数，**不执行守护脚本本身**）。
- ⚠️ 计划任务 `ExecutionTimeLimit` 实测是 **PT72H**（不是 8 分钟），最坏路径约 6.2 分钟 ⇒ 余量充足。
- ✅ **已做真实故障注入验证（2026-10-22 14:01）**：杀掉全部 `com.docker.backend`
  （daemon DOWN、0 容器运行）后**不干预**，守护任务自己那一轮 **16 秒完成自愈**：
  `14:01:02 WARN  escalating` → `14:01:07 INFO L0 system disk ACL repaired`
  （**当场补回被剥掉的 27 个 SID** —— 正是 10-19 事故的成因）→ `14:01:18 INFO
  Docker came up after L0 {containers_running: 13}`。自愈后与注入前**逐项比对：
  13 个容器 ID、14 个镜像 ID+tag、10 个卷名全部相同**，数据
  `meetings=28 / members=36 / knowledge=884 / chunks=519` 一致，生产域名 200。
  ⚠️ **「Docker 恢复了」≠「业务已就绪」** —— 守护判据是 Docker 层（`docker info` +
  `docker ps`），数据库 pre-fsync 恢复后业务端点还要再等 1–2 分钟（实测 14:01:18 → 14:02:47）。

### D. 🔴 本次事故的四层根因链（详见 runbook §3）

1. **05:06:51 空闲自动暂停后恢复失败**（`seeking /sys/fs/cgroup/procd-paused/cgroup.procs`）→ backend 崩。
2. **守护脚本把一次崩溃放大成雪崩**：55 秒内 3 次 L2、2.4 分钟内 2 次 L3。两个并发来源：
   ① `scripts/run-hidden.vbs:48` 用 `bWaitOnReturn=False` 起 powershell ⇒ **wscript 立刻退出**
   ⇒ 任务计划程序认为动作已完成 ⇒ 5 分钟后又起一个（`MultipleInstances=IgnoreNew` 看不见
   detached 子进程）；② L3 闸门读 `state.json`，而 `Set-State` 是"读-改-写"、`Set-Content`
   先截断 ⇒ 读者读到半个文件 ⇒ 闸门当成"从没跑过"⇒ 放行。
   ⇒ 每个并发实例都杀 Docker 再拉新的 ⇒ **两个 backend 争抢同一 AF_UNIX socket**。
3. **L3 本身无效且制造下一个故障**：`wsl --unregister` **不删** `main\ext4.vhdx`
   ⇒ 下次 `wslmigrate` 判 "WSL2 disk exists" ⇒ **跳过 provisioning** ⇒ 复用一个已注销的
   发行版 ⇒ 引擎永远起不来。
   ⇒ **实测有效配方**（06:41–06:49 一次跑通）：停进程 → `wsl --shutdown` →
   `wsl --unregister` → 确认 `ext4.vhdx` 已不存在而 `docker_data.vhdx` 完好 →
   确认 `run\` 存在且空 → 启动。
4. **AF_UNIX 冲突的真实机制**：`run\` 目录在 Win32 与 Linux 两侧枚举**都是空的**，
   却仍然 `EADDRINUSE` ⇒ 真因是**两个 backend 进程把 `%LOCALAPPDATA%\Docker` 解析成两个
   不同字符串却指向同一物理目录**，绑了同一个 socket。

### E. 本仓代码层的"防 C 盘回流"改造（已落地并实测）

| 文件 | 改动 | 实测 |
|---|---|---|
| `scripts/voice-alert.ps1` | 缓存 `$env:LOCALAPPDATA\voice-alert-cache` → `$ProjectRoot\data\voice-alert-cache` + **LRU 50 个**（原来无上限） | 塞 55 → 跑一次 → 裁到 50，留的是最新 3 个 ✓ |
| `apps/desktop/scripts/server/offsite-oss-sync.py` | `mkdtemp` 加 `dir=`（E 盘 `data\tmp`） | AST OK ✓ |
| `scripts/backup/rotate_offsite_passphrase.py` | 两处 `tempfile` 加 `dir=`（**`verify-` 目录里是用新口令解出的明文**） | AST OK ✓ |
| `app/services/audio_processor.py` | `import torch` 前设 `TORCH_HOME`（**仅 Windows 宿主**，容器内是 Linux 路径语义不能设） | 容器内导入 OK ✓ |
| `apps/desktop/package.json` + `scripts/lib/cache-env.mjs` + `scripts/with-cache-env.mjs` | `pack`/`dist`/`release.mjs` 注入 `ELECTRON_CACHE`/`ELECTRON_BUILDER_CACHE` | `node --check` OK ✓ |
| `.pnpmfile.cjs`（仓库根） | pnpm 生命周期子进程继承 pnpm 进程的 env ⇒ 在这里设同一组变量 | ⚠️ **实测 pnpm 9.15.9 只加载 `.pnpmfile.cjs`（带点）** —— 一次性目录里两个都放，只有带点的被加载 ✓ |
| `apps/desktop/src/main/index.ts` | **不改代码**：用用户级 `MNB_USER_DATA` 驱动已有的开关 | 旧 `Roaming\MicroBubbleWorkbench\data\` 的 8 个文件（含 `workbench.db`、`session-token.enc`）已**复制**到新位置，旧目录保留 ✓ |

**用户级环境变量**：`TEMP`/`TMP`=`E:\microbubble-agent\data\tmp`、
`ELECTRON_CACHE`、`ELECTRON_BUILDER_CACHE`、`PLAYWRIGHT_BROWSERS_PATH`、
`MNB_USER_DATA`（详见 runbook §2 的表）。
⚠️ **已在运行的进程不会自动切换**（Claude Desktop 及其子进程仍持旧 `%TEMP%`，需重启）。
⚠️ `npm config get cache` 实测是 **`D:\npm-cache`**（不是 C 盘）⇒ **不要改**。

### F. ⚠️ 「改了用户级环境变量 ⇒ 旧进程就会用新的」是错的（实测推翻）

原计划：改用户级 `TEMP`/`TMP` → 重启那个 LabCairn 会话 → 它就该写 E 盘了。
**实测不成立**，原因链条：

1. **子进程继承父进程的环境**，不是重新读注册表。
   Claude Desktop 主进程早于这次改动启动 ⇒ 它的 env 是**陈旧的**。
2. **实测证据**：我自己的会话（其进程早于改动启动）派生的**新** bash 进程，
   `%TEMP%` 仍是 `C:\Users\pc\AppData\Local\Temp`，而注册表里已是
   `E:\microbubble-agent\data\tmp`。
3. **重启会话也不够** —— 新起的会话进程仍然是 Claude Desktop 主进程的子进程，
   继承的还是旧 env。实测：给 `E:\LabCairn\.claude\settings.json` 加
   `env: {TEMP, TMP}` 并重启该会话后，**它仍写 C 盘**
   （`C:\...\Temp\claude\E--LabCairn--...` 有 17:09 的新写入）。
4. ⇒ **真正生效的时机是 Claude Desktop 本体重启**（用户级变量对新起的进程生效）。
   本次未强推（那会中断当前会话），已把话说明并留给用户决定。
5. ⇒ **兜底方案**（`scripts/ci/make-temp-a-junction.ps1`）：把
   `%LOCALAPPDATA%\Temp` 整个做成指向 E 盘的 junction，**新旧进程一律落到同一物理目录**。
   **本次未能执行**：① Claude Desktop 持有 `%TEMP%\claude` 的句柄，
   **连改名都拒绝访问**；② 另有约 20 个条目被活进程锁住，
   `Remove-Item -Recurse` 与普通 `robocopy` 都删不掉（超 MAX_PATH），
   脚本检测到 Temp 非空即**中止且不改动任何东西**（fail-loud）。
   ⇒ 待 Claude Desktop 退出、句柄释放后再跑。

### G. ⚠️ 搬走「别人的」临时目录前，必须先确认没有会话在用

本次把 `%TEMP%` 下 418 个 `lcp*` 克隆目录（20 GB，LabCairn 测试 harness 产生）
整体搬到 E 盘 ⇒ **搬走了 LabCairn 会话正在用的 `lcp111-scratch`** ⇒ 它的测试报
`No such file or directory` + `pytest exit: 1`。
**已全部搬回原位复原**（含 `lcp111-scratch`），C 盘剩余 44 GB。

**⇒ 但真工作从未受影响（该会话当场核实、我已复核）**：LabCairn 的活的工作在
**主仓 `E:\LabCairn`**（分支 `fix/g4-round-four` @ `86e0226`，`main` @ `5dcd6d0`，
**PR #107 开着**，验收草稿 `docs/acceptance/G4-acceptance.md` 未提交），
reviewer 的 harness 在 `C:\Users\pc\labcairn-g4\`，**都不在 `%TEMP%` 下**。
⚠️ 我最初核对的是**遗留 worktree**
`E:\LabCairn\.claude\worktrees\agent-a6cda21d6e6f80725`（25bad72 / PR #87 已 MERGED）
⇒ **据此给过用户和对方"成果没丢、PR 已合"的错误结论**（结论恰好无害，但依据是错的）。
⇒ **纪律**：核对"某项目有没有在跑的活工作"时，**必须看主仓 + 未提交改动 + 开着的 PR**，
**不能拿一个遗留 worktree 的干净状态当证据**。

**⇒ 附带查清的技术点（给 LabCairn）**：`lcp*` 那 20 GB **不是 pytest 造的**，
**pytest 的 `--basetemp` 覆盖不到它们** —— 它们由 `tempfile.gettempdir()` 决定：

| 位置 | 代码 | 产物 |
|---|---|---|
| `scripts/probes/pdf_spans.py:48` | `tempfile.mkdtemp(prefix="labcairn-probe-")` | `%TEMP%\labcairn-probe-*` |
| `src/labcairn/analysis/chart/render.py:267` | `MPL_CONFIG_DIR = Path(tempfile.gettempdir()) / "labcairn-matplotlib"` | `%TEMP%\labcairn-matplotlib`（**每次渲染都写**） |
| `tests/test_api_concurrency.py:278` | `tempfile.TemporaryDirectory(prefix="lcp-concurrency-")` | `%TEMP%\lcp-concurrency-*` |

⇒ 要动它们只能改 `TMPDIR`/`TEMP`/`TMP`（Windows 上 `tempfile` 依次读这三个，
再 `C:\TEMP`、`C:\`、`C:\Windows\Temp` 兜底），或在调用点显式传 `dir=`。

⇒ **纪律**：① 批量搬 `%TEMP%` 前先看 `list_sessions`（有在跑的会话就有在用的目录），
   并**看目录 mtime 是否在被持续更新**；⚠️ **注意 robocopy 移动本身会改写目录 mtime**
   ⇒ 搬完后无法再用 mtime 判活跃度，**必须在搬之前记录**；
② 别人的工作目录**搬走比留着更危险** —— 宁可少腾一点空间；
③ 搬之前**先问对方在用哪些**（本例应先要一份"还在用"的清单）。

### H. 本阶段新增的永久铁律

**类 20.231**（MSIX 包重定向）/ **类 20.232**（Windows 上"看不见"的三种假象）/
**类 20.233**（自愈脚本的并发要先查调度器语义）/ **类 20.234**（原子写的兜底分支必须同样安全）/
**类 20.235**（改用户级环境变量对已在运行的进程无效 —— 子进程继承父进程 env）
—— 见下方「永久铁律」段。

---

## 当前状态 (2026-09-30 阶段收尾全面收口 — CI 硬门转正 / 94GB 死重清零 / 41GB 生产依赖归位 / 远端补齐)

**服务端全量测试首次有真闸门 (S1.2 完成)**:
- `server-tests-baseline.yml` 8 片 matrix 跑 3112 用例；基线 **829 条红灯经 R1-R6 六轮
  收敛归零**（最终 passed 2926 / failed 0 / errors 0 / skipped 186），已摘
  `continue-on-error` —— 任一片失败即阻塞合并。**此前 451 个测试文件从未有任何
  workflow 跑过全量**（RAG-FW CI 只跑 `tests/rag_framework/` 一个子集）。
  > ⚠️ 本段是 **2026-09-30 快照**，数字已过时。实时值见下方「测试规范」段
  > （2026-10-15 实测 3565 用例 / 3376 passed / 189 skipped，run `38600849147` 全绿）。
- **87 个测试文件带模块级守卫**（一次性验收快照 / 环境依赖类，全部原位保留 +
  文件头写明恢复条件）。**守门类测试不得归档**（`test_no_prod_db_imports` 禁止测试
  直连生产库）。
- 容器跑 pytest：URL 必须 `postgresql+asyncpg://`；CI 里 `TEST_DATABASE_URL` 与
  `DATABASE_URL` **两个都要设**（conftest 从后者派生库名）。

**物理布局 (S1.1 / S2.1 完成)**:
- **alembic 单 head = `141_zb2_backup_kb_purge`**（容器 `alembic heads` 实测，2026-09-30）。
  本文件历史段落里出现的 084/085/104/105/139 等 head 号**都是当时的快照**，写断言时
  用「恰为 1 个 head」不变量，别写死编号（已有 084/085/087 三连修正先例）。
- 删死重 **94.4 GB**：`llama-cpp-tools/qwen3-14b-f16.gguf` 52.1G、`models/Qwen3-14B-FP16`
  28.2G、`.ollama/` 13.5G、`.claude/recovery-clones/`、零源码的 `web-minimal/`。
  **`data/ollama` 61.6G 是 ollama 容器挂载点，勿删**。
- 会议转写 41.7 GB 运行时已从隐藏的 `.workbuddy/vibevoice-test` 归位到
  **`data/vibevoice-test`**，位置由 `VIBEVOICE_HOME` 控制（4 个消费点：3 个
  `app/gpu_worker/*.py` + `scripts/start_gpu_asr_daemon.bat`，开机自启任务
  `MicroBubble-GPU-ASR-Daemon` 调它）。已实测 7B 链路 60s 音频 80s 转写通过。

**文档与远端 (S0.1 / S2.2 部分完成)**:
- `desktop-conversion/` 已建私有远端 `gg320324492-lgtm/microbubble-desktop-conversion`
  （此前 126 commits 只存在于本机单盘）。
- 阶段收尾全过程见 `desktop-conversion/docs/plans/2026-09-30-phase-closeout-plan.md`
  与 `docs/acceptance/2026-09-30-server-tests-baseline-v2.md`。
- **PWA 已于 2026-07-27 强制注销**（`36b0b2ec9`，`VitePWA({ disable: true })`）：
  dist 无 manifest / 无 sw.js 是**预期状态**，见下方 971 行失效警示。

## 当前状态 (2026-10-10 会议录音事故追查 → 系统性静默失效清理 → PPT 图片内容入 RAG)

> 上一版"当前状态"停在 2026-09-30；2026-10-08~10 这三天的工作如下。**`alembic` 单 head 已是
> `145_kpt_content_tsvector`**（本文件其他段落出现的 141/142/143/144 都是当时快照）。

### A. 会议 255 录音丢失事故 → 心跳机制三层修复（类 20.218）

- **事故**：2026-10-08 18:45 iPhone 组会录音 38min，全程 **0 心跳**，被
  `orphan_meeting_cleanup` 判 error、录音全丢 (`docs/incident/2026-10-08-meeting-255-orphan-cleanup.md`)。
- **真根因（非"iOS 后台挂起"这一表象）**：心跳 timer 是 `AudioRecorder` **组件局部变量**，
  而恢复路径 (`MeetingRoomView.vue` / `MobileMeetingRoom.vue` 的 onMounted) 直接调
  `useGlobalRecorder().start()`，**绕过**了唯一的心跳启动入口 `handleStart()`。
  **09-15 那次心跳修复从未在真机 iOS 上生效过**（会议 253 其实是失败事故，254 成功只因
  桌面 Chrome 触发 timeslice 有分片）。
- **修复**：心跳提升为**模块级单例** (`web/src/composables/useRecordingHeartbeat.js`)；
  恢复/续传路径显式 `ensureHeartbeat`；`visibilitychange`/`pageshow`/`focus` 切回前台立即补心跳；
  心跳**独立限流 tier** 且 **429 也写审计**；孤儿清理**有分片就不删 MinIO**。
- **验证**：用户用手机自带录音器补录的 m4a（2h48m）完整重跑 255 → `completed`，
  摘要 487 字 / 要点 8 条 / 决议 29 条全部合规。

### B. 一批"静默失效"链路被清出（全部是"看起来在工作、实际没工作"）

| 类别 | 问题 | 修复 |
|---|---|---|
| **celery 漏注册 ×3** | `meeting_chunk_service` / `drive_index_service` / `auto_rag_tasks` 定义了 task 但**从未进 `celery_app.conf.imports`** → 派发被 worker 静默丢弃。会议 RAG 的 `meeting_chunks` 路自 `d1aa07adb` 起**一直是空的** | 补注册 + 回填（类 **20.219**） |
| **`storage_mode` 漏过滤 ×3** | `rag_auto_ingest` / `knowledge_polling` / `admin_kb_monitor` 按 `analysis_status` 选行但**不看 `storage_mode`** → 把 drive 行的占位串 `[drive upload] <文件名>` 当正文切 chunk + embedding | 统一复用 `INGESTABLE_STORAGE_MODE` 判据 |
| **跨 event loop ×2** | `ocr_service` 模块级 `Semaphore`、`recall_observability` 单例 `Lock` 绑死创建时的 loop → celery 每次 `asyncio.run()` 新 loop 复用即炸（**OCR 实测 77% 失败率 4201/5446**） | 改按 `get_running_loop()` 惰性重建 |
| **"假成功" ×2** | `classify_and_extract` 失败**返回 dict 而非抛出**，下游 `isinstance(x, Exception)` 永远 False → 失败被标 `done`（**抹掉失败信号**）；`paper_layout_service` 同型（且叠了个 NameError 互相掩盖） | 改判 `error` 键是否存在 |
| **分块器不认 `[PAGE:N]`** | PPT/PDF 解析产物里 `\n\n` 出现 0 次，而分块器只按 `\n\n` 切 → **整份 17 页 deck 塌成 1 个 chunk** | 加 `page` 策略；全库 `[PAGE:]` chunk **2017 → 10549** |
| **`split_for_tsvector` 超长** | `max_chars=6000` 截的是**原始输入**，jieba 切词后输出可 >6000 撞 CHECK 约束 → 异常被吞成 warning，`search_text` **静默留空** | 改按 token 边界裁剪输出 |
| **`_parse_pptx` 不递归 group** | 只遍历 `slide.shapes` 顶层，**组合形状 (`p:grpSp`) 内文本整块丢失**（实测 559 页受影响、134 页损失 >20 字符、**10 页整页为 0**） | 加递归 + 深度上限 |

### C. PPT **图片内容**正式进入 RAG（这是本仓第一次让"图里的字"可检索）

- **背景**：241 个 drive 文件"只产 1 chunk"的主因**已由上面的分块器修复解决**（零成本、17 倍增益）；
  但**图片内容仍未进检索**（`python-pptx` 只抽文本框，图片型 deck 的文字抽不到）。
- **随机抽样定标**（269 页，两层 PPS，seed 固定）：全库真实产出率 **49.2%**（剔除第三方论文截图后 40.8%），
  **A/现有索引 = 1.05x**；但**产出率与现有文本量强反比** ——
  `native<20` 档 **A/索引 22.9x**、`20-59` 档 5.45x、`>=300` 档仅 **0.37x**（72% 是重复）。
  **结论：不做无差别全量，按 `native<143` 分档投喂**（该档占全库约 45%）。
- **已投喂 `native<143` 档**：**2495 行**入库新表 **`knowledge_page_transcripts`**
  （2229 页正文 + 266 页 metadata-only）；`A` 类纯新增 **~42 万字符**；embedding 全本地 Qwen3。
- **三条新增基础设施**（都在 `app/services/`）：
  - `image_decoration_filter.py` —— 母版装饰横幅判据（两信号交集：AR≥5+height≤300 **且** 同文档同尺寸跨≥2 页），
    写入侧 OCR **前**拦截 + 检索侧排除，两侧**结构上无法漂移**（同一常量）
  - `page_transcript_filter.py` —— 整页转写净化（三档词表 + `chrome_ratio` 拍摄屏幕拦截 + 尾随总结切尾），
    被拦页**只标 `blocked` 不删内容**（建议转人工）
  - `page_transcript_retriever.py` —— 独立召回路：**语义**（权重 0.10）+ **词法**（`content_tsvector` GIN，
    PG `simple` 保留整词 lexeme，罕见拉丁词 5/5 命中；rerank 后**回钉** 2 槽防被语义分截掉）
- **关键教训**：`jieba` 会把 `air-nanobubble` 劈成 `air` + `nanobubble`，`air` 高频稀释分数 →
  字面页 rank 10 掉出 top-5；**PG `simple` 保留整词 → rank 1**。词法路必须用 PG tsvector 而非复用 jieba BM25。

### D. 其他已收口项

- **L-14 DB 密码轮换去硬编码**：21 个文件改读 `.env`（**绝不把新密码写进 git**），
  交接文档 `desktop-conversion/docs/handoff/2026-10-09-L14-db-password-rotation-handoff.md`。
- **DFT 已彻底移出本仓**（活代码 2026-09-13 即清零；本次只删 `scripts/dft/README.md`）。
  ⚠️ **`E:\dft-service\` 是用户的独立项目，不属本仓，不许删**（含其 `MicroBubble-DFT-Cleanup` 计划任务）；
  ⚠️ **`.dft` 前缀 ≠ DFT 计算**（`DriveFileTable.vue` 的 CSS 类）——grep 会大量假阳性。
- **`vision-mcp`** 改 compose profile 隔离（默认不启）；**glitchtip 不重建**（主拍结案）。
- **`pptx-pages` 缓存 key** `updated_at` → `file_path`（11 处调用点；`updated_at` 被行级改动刷新即全失效，
  实测命中率 **0/295 → 96/295**）。
- **`ocr_status` 拆出 `done_no_text`**：`done` 从此**全部有可检索文字**（0 例外），
  与"OCR 成功但图里没字"分离（类 **20.220** 同族：状态字段不许撒谎）。
- **`ai_polish` 默认关闭**（`MEETING_AI_POLISH_ENABLED=False`）：实测 68 批耗时 50-60min 而
  产物 100% 被"差异>10% 回退原文"兜底丢弃（`polish_real_change_ratio=0.0`），净收益为负。
- **LLM 后端已从 MIMO 切到 MiniMax**（MIMO key 失效）；⚠️ **`VISION_MODEL` 必须保持能用图片的模型**，
  切 `MiniMax-Text-01` 会让 OCR 立刻 500。
- **`knowledge_chunks` 双写者冲突 = 已缓解 (2026-10-10 复验结案, 无需改动)** ——
  曾担心 `rag_auto_ingest`(通用 kb 入库) 与 `drive_index`(drive 专用) 两个写者都调
  `write_chunks_for_knowledge`(先 DELETE 后 INSERT) 互相覆盖。**复验证据**: ①占位串 chunk
  `content LIKE '%[drive upload]%'` 全库 **0 行**(commit `67b5d2eb0` 当日有 48 行, 已随 drive
  回填清零); ②四个可能写者选行条件**互斥** —— `rag_auto_ingest`/`knowledge_polling` 共用一个
  `_ingestable_rows_clause()`(`analysis_status='pending' AND storage_mode='kb'`, 三处调用点
  254/321/330 全走它), `drive_index` 入口硬校验 `storage_mode != "drive"` 即 skip,
  `meeting_chunk_service` 写独立表 `meeting_chunks`, `drive_to_kb_service` 新建 kb 行后分析;
  ③抽查 drive 行 886(parent content 是占位串) 的 32 个 chunk **全是真解析 PPT 正文**;
  ④回归测试 23 passed。**唯一低风险点**: `drive_to_kb_service` 的 Celery 不可用降级路径
  (L684) 未被测试覆盖(目标仍是它新建的 kb 行, 不影响边界)。**此项不要再当待办重查**。
- **`generate_embedding(s)` 线程泄漏已隔离 (2026-10-10, 主拍方案 3 = 保持 1 + 观察一周)** ——
  原实现把 `model.encode()` 包在 `asyncio.to_thread`(= **默认共享池**) 再套 `asyncio.wait_for`。
  **超时只 cancel 协程、杀不死底层线程**, 于是每次超时泄漏一个仍持线程/GIL 的 worker;
  默认池被 `asyncio.to_thread` 的 **23 个文件**共用(drive/ocr/file_parser/audio/whisper…),
  打满后**全进程所有调用方一起排队**; 若 encode 卡在 torch/ST 内部锁上则**永久挂死**。
  修法: `embedding_service.py` 新增**专用有界 executor**(`_get_embedding_executor()`,
  `max_workers=_EMBEDDING_THREAD_POOL_SIZE` **默认 1**), 改走 `loop.run_in_executor`;
  超时置**进程级 degraded 标记** + 30s 限流告警(`is_embedding_degraded()` 可查)——
  **线程不可强杀, degraded 只增不减(重启才清零), 这是设计而非 bug**。
  ⚠️ **`max_workers=1` 是刻意取舍(主拍 2026-10-10)**: ST 对同一模型实例本已因内部锁串行,
  多 worker 只在超时时把泄漏面同比放大; 而泄漏 ⇒ **不可恢复的挂死**, 吞吐慢 ⇒ 只是慢。
  **实测代价**: 8 并发任务 / 单次 0.5s 编码 = **1.78s 串行排队**。**观察一周**
  `[embedding degraded]` 告警与排队耗时, 若确有压力再调 `_EMBEDDING_THREAD_POOL_SIZE`
  (代价 = 泄漏面同比放大)。**跨 loop 纪律**: 新代码**零** `asyncio.Semaphore`/`Lock`
  (天然规避绑 loop); executor 是**进程级刻意单例跨 `asyncio.run()` 复用**——
  线程泄漏本就是进程级资源, per-loop 独立 executor 反而会让每个新 loop 各泄漏一份;
  per-loop 状态用 `id(loop)` **整数**存(不持 loop 对象引用, 避免 loop 关闭后被强引用)。
  测试 `tests/test_embedding_timeout_cancel.py` (7 用例, 含"超时后放行慢线程、第二次调用正常")。

### E. 本阶段新增的永久铁律

**类 20.218**（录音心跳绑会话不绑组件，见上）/ **类 20.219**（新增 celery task 必须同时进
`celery_app.conf.imports`）/ **类 20.220**（自动化守门必须验"副作用是否真的发生"，不能信状态字段）/
**类 20.221**（DB 存 UTC、主机 +0800，跨系统对时必须显式换算）/
**类 20.222**（CI 硬门必须真的挡得住 —— 开保护前先修红、matrix 下 required checks 必须逐个 job 列，见上）/
**类 20.223**（判「依赖无用」必须查上游未声明的硬 import + import blocker 实测；能钉别删，见上）。

### F. 结构重构与 CI 收口（2026-10-10~12，8 批次全完成）

- **结构重构 8 批次全部完成**：tests 会话编号目录归位（9→语义化目录）/ 深度 3 违规 7→5 /
  删死文件 / 修坏引用 + 3 份索引文档 / aXX 脚本 15→0（拆活链路 `ppt_pages/` 与探针 `_archive/`）/
  5 份边界 README / `desktop-conversion/` 子仓并入主仓（176 文件，**gitlink 0**）/ 全链路验收 10 项全过。
  规划与验收：`docs/design/2026-10-10-structure-refactor-plan.md`（含 §七 CI 全红台账、§八 验收、§九 收口）。
  ⚠️ **此处"测试收集数 400"是 2026-10-10~12 重构期间的快照，不是现值** ——
  同日经 import blocker 实测确认零调用方后，连删三个 RAG-FW 专属测试文件
  （`e5333eb6f` + 删 agent_retriever 那次），当时降到 **397 文件 / 4119 函数**；
  此后 10-13 / 10-14 又新增 2 个文件回到 399 / 4141，10-15 再 +3 到 **402 / 4159**。
  **实时值见「测试规范」段**。
- **CI 连续 9+ 次全红已终结**：根因 = requirements.txt 里裸 `datasets` 那行传递引入
  `pyarrow>=24`，而同一文件里 `numpy==1.26.2` 那行把 numpy 写死在 1.26.2，
  pyarrow 26 起硬性要求 numpy≥2.0 →
  `embedding_service` import 失败 → 连锁 64 条红灯。**非 2026-10-10 改动引入**
  （10-09 的 run 已有 33 处同错），10-10 的 embedding executor 只是让它被更多测试 import 而暴露。
  修法 = 钉 `pyarrow==25.0.1`（与生产对齐），**不升 numpy 2.x**（ABI 破坏面）。
  ⚠️ `datasets` **仍是裸声明**，下次它升级可能再触发同类冲突。
- **workflow 审计**（`docs/audit/2026-10-12-workflow-audit.md`）：11 → 保留 5 / 删重复段 1；
  ⚠️ 审计报告曾误判 `image-scan` "建议删"，执行 agent 交叉验证后**推翻**
  （`tests/trivy/test_workflow_exists.py:20` 断言其存在且未归档，删了会打红硬门；
  且它是 L-8 **活跃治理项**，10-07/08/09 连落 3 commit）。
- **`.trivyignore` 已建并接线** ——
  ⚠️ **2026-10-12 订正：原文记的"4 条"与"升 websockets 12→15 会连带 uvicorn/fastapi
  栈改造"两条均已被实测推翻**，详见下方 `## 当前状态 (2026-10-12 ...)` B 段与 **类 20.224**。

## 当前状态 (2026-10-12 离站容灾重做 / image-scan 4 修 3 / 依赖归因连错三轮)

> 上一版"当前状态"停在 2026-10-10~12 的 F 段；2026-10-12 这批工作如下。
>
> **本次最大的教训不是某件工作本身，而是「依赖冲突的归因极易搞错，且错了会被文档悄悄继承
> 下去」** —— 同一个阻塞问题**连续三轮归因，错了两轮**，每一轮的错误结论都被写进
> `requirements.txt` 注释 / `.trivyignore` 注释，再成为下一轮判断的前提。由此新增 **类 20.224**。

### A. 离站容灾重做 —— 取证证明**这套东西从来没有真正备份过任何东西**

- **取证结论（主指挥裁定"到此为止，不再查主账号"）**：桶 `mnb-workbench-backup` 里**从未有过备份**，
  只有一个 2026-09-21 19:29:16 +0800 上传的 `说明.txt`（无凭据泄露），全桶活动锁在 **77 秒**内。
- **2026-09-21 那次 commit `79fc47f41` 写的"真实上传+幂等复扫已验证"验的不是备份** ——
  它验的是 **OSS 通路**（V1 签名修对、列举能通），**没验证有没有东西可传**：
  旧版 `scan_local` 的 `if p.name.startswith(".")` 把 `.env.*.bak` **整类静默跳过**，
  而当时 `backups/` 里**只有** `.env.*.bak` 和一个 8-30 的遗留 `.sql`；
  `microbubble_*.sql.gz` 要到 **10-04** 才出现。典型**类 20.220**（commit message 说成功，
  副作用根本没发生）。已排除"曾传后被删"：`mnb-workbench-releases` 的 `offsite-backup/`
  前缀 **0 对象**，9-21 同步时刻之后该桶无任何新对象。
- **重做后的实现**（`apps/desktop/scripts/server/offsite-oss-sync.py`，`eb9f55df0` + `da8688fba` +
  `85dea13f6`）：**加密无开关**（AES-256-GCM + PBKDF2-HMAC-SHA256 600k 轮 + 每文件独立 salt/nonce，
  分块 8MiB，DB dump 实测 41~82MB）；**口令只从 `--passphrase-file` 读**（不读 .env /
  不读环境变量 / 不内置，`.secrets/` 已入 `.gitignore` + `.dockerignore` 双排除）；
  **桶与凭据零默认值**，缺任一项即 fail-loud（旧版 `DEFAULT_BUCKET` 指向**公开**桶是重大隐患）；
  **`--subdir`（默认 `microbubble`）既是命名隔离也是权限边界** —— ⚠️ **`--cleanup` 不带
  `--subdir` 会连全组其他成员的备份一起删**（mock 实测会连带删掉 `说明.txt` + `负责人/`）。
- **⚠️ 桶权限边界（改配置前必读）**：`mnb-workbench-backup` = **私有**；
  `mnb-workbench-releases` = **匿名可读**（electron-updater 公开发布源），**备份绝不可用它**。
  当前凭据是 **SubUser（子账号）**，仅对象读写，桶级 `?versioning` / `?lifecycle` / `?versions`
  一律 **403**（`PolicyType: ResourceGroupLevelIdentityBasedPolicy` + `ImplicitDeny`）。
- **已闭环验证**：**40 个备份（410.9 MB，全部 `.enc`）真在阿里云**；82MB dump 从 OSS 下载 →
  解密 → **sha256 与本地完全一致**；幂等复跑 0 上传 40 跳过。计划任务 **`MNB-OffsiteOssSync`**
  每日 **03:30**（本地备份 02:00，间隔 1.5h）自跑，已实测注册在位（State=Ready）。
  ⚠️ **主体必须是当前用户 `pc` 而非 SYSTEM** —— OSS 凭据在 User 级环境变量，SYSTEM 读不到。
- **真实上传暴露了 3 个静态检查与容器内测试全都看不出来的缺陷**（类 20.220 的又一次）：
  ①**网络无重试** —— 首次全量 39 秒即 `URLError [WinError 10060]` 中断，40 个只传完 35 个，
  失败的恰是最大的几个；计划任务一天一次 ⇒ **一次抖动丢一天**。已加 5 次 / 300s /
  2-4-8-16s 指数退避。⚠️ **每次重试必须重新签名**（V1 的 Date 头 15 分钟有效，复用会拿 403
  `SignatureDoesNotMatch`，把可恢复抖动变成**不可恢复**失败）；HTTPError 不重试。
  ②**Windows 上解密失败抛 PermissionError 掩盖真实原因** —— 清理调用点在 `with dst.open("wb")`
  块内，句柄未关，`unlink` 抛 `[WinError 32]`，"口令错误"的清晰 `[FATAL]` 被无关 traceback 盖掉。
  ③**失败后磁盘残留已解出的明文** —— 错口令时半成品里正是**明文**。三场景实测零残留。
- **改这个脚本后必须跑往返矩阵**（0B / 5B / 恰好整块 / 短末块 / 40MB / 82MB）验字节全等，
  `py_compile` 与 `import` 都要做 —— 三个已修的真 bug（模块 import 就炸 / 短末块根本解不开 /
  `--cleanup` 删别人备份）**没有一个是语法问题**。
- **配套文档**：`docs/disaster-recovery-runbook.md`（**不含任何密钥**）。
  ⚠️ **解密口令只在本机** `<仓库根>/.secrets/offsite_backup.passphrase` ——
  **本机丢失 = 远端 410MB 备份永久不可读**（GCM 没有后门，轮换口令也救不了旧密文）。
  换机流程：先确认口令文件，**没有就不要先删旧机**。
- **密钥处置纪律**：密钥（口令/密码/token）**任何情况下不得 print 到终端或对话**，含调试中间态；
  需要读进程序就走文件/stdin，校验用 **sha256 前 12 位指纹**而非内容本身。
  本次起因就是我为排查 Bitwarden CLI payload 直接 `print` 了含口令的 JSON，导致 64 字节的
  备份加密口令明文进了终端滚动缓冲与对话记录（那串口令能解开含库密码 / JWT SECRET_KEY /
  MinIO 密钥的 410MB 备份）。**Bitwarden 条目走网页版手动录入，不要写 CLI 自动化** ——
  实测 Windows 上 `bw create item` 读不到管道 stdin（喂合法 JSON 与喂 `NOT-JSON-AT-ALL`
  报**完全相同**的错，等价于读到空输入）；且 **`BW_SESSION` 是进程级环境变量，不跨终端标签页**。
  口令轮换走 `scripts/backup/rotate_offsite_passphrase.py`（`--dry-run` 先看计划），
  铁律三条：绝不先删远端、绝不未验证就覆盖本地口令、**绝不跳过"以远端为准逐个实解"** ——
  本次首轮就因为按**本地**文件列表走而漏掉 2 个远端孤儿（本地 `KEEP_DAYS=7` 已清、远端还在）。

### B. image-scan 4 条 CVE **暴露面已全部消除**（3 条靠升 uvicorn + mcp，1 条靠删 langchain 依赖）

| CVE | 包 | 状态 |
|---|---|---|
| CVE-2025-66416 / 52869 / 59950 | mcp | ✅ 已修（升 uvicorn + mcp 下限抬到 `>=1.28.1,<2`），**已在生产镜像实测生效** |
| CVE-2026-34070 | langchain-core 0.3.86 | ✅ **暴露面已消除**（删依赖，非升级）—— 四包已从镜像移除，见 C 段 |

- ⚠️ **归因已被实测推翻**：注释里"mcp 要 websockets>=15，撞 websockets==12.0 硬钉"**是错的** ——
  `mcp 1.28.1 + websockets 12.0` 与 `+15.0` **均**可解，**唯一阻塞点是 uvicorn**
  （`mcp>=1.13.0` 把 uvicorn 下限从 `>=0.23.1` 抬到 `>=0.31.1`，不存在"既修 CVE 又不动 uvicorn"
  的版本）。而 websockets **早在 2026-10-11 就已放宽成 `>=12.0,<16.0`**，容器实测装 **15.0.1**
  ⇒ 第 1 轮的前提写下时就已是假的。完整三轮台账见 **类 20.224**。
- **爆炸半径实测为零**：dry-run 确认**不牵动** fastapi / starlette / websockets / anyio / numpy，
  仅 uvicorn 自身 + mcp 变化；代码级全仓 3 处 `import uvicorn` 用的都是
  `uvicorn.run(app, host=, port=)`，该签名 0.24→0.31 **未变**（其余 5 处是命令行
  `uvicorn app.main:app`）。⇒ **升 ASGI 栈前先查这几处，签名稳定就不是栈级改造**。
- ✅ **镜像已重建，变更已在生产生效**（2026-10-12 实测，**在运行中的容器里查的版本，
  不是读 Dockerfile**）：uvicorn **0.24.0 → 0.31.1**、mcp **1.12.4 → 1.30.0**；
  **langchain / langchain-core / langchain-anthropic / langchain-community 四包全部
  未安装**（`ModuleNotFoundError`）；fastapi 0.143.0 / starlette 1.7.0 / websockets 15.0.1 /
  numpy 1.26.2 **完全不变**（印证上面的"爆炸半径为零"）。app / celery-worker / celery-beat /
  celery-meeting-worker 四个服务重建后全部 healthy 且同在 `microbubble-agent_default`；
  本机 `/health` 200、**生产域名 `https://agent.mnb-lab.cn/health` 200**、首页 200，
  worker `ready`、beat 正常调度。
  **复验方式（务必在运行容器里查，别读 Dockerfile）**：
  `docker exec microbubble-agent-app-1 python -c "import importlib.metadata as m; print(m.version('uvicorn'))"`
  —— 多阶段构建下 builder 与 runtime 是两个文件系统，**Dockerfile 里写着装了 ≠ 成品镜像里装了**
  （类 20.220 第 4 种形态，`setuptools 79.0.1` 事故同型）。
- ✅ **CI 已验证转绿**（2026-10-12，run `38226873852`，head `faf57b501`，
  event=push，结论 **success**）—— 这是 4 条 CVE 首次拿到 **CI 级证明**：
  - `trivy deps app` / `commercial` / `voice-pipeline` **三个 job 全绿**，
    全量 job 被 `if` 正确 skip ⇒ 新的 push 触发器 + 两 job 分流首次实跑成功；
  - 三个 job 都**真跑了扫描**（日志含 `Detected OS family="debian" version="12.15"`
    + `[python-pkg] Detecting vulnerabilities...` + Report Summary），
    **不是"扫了空气报平安"** —— 类 20.220 的检查项，逐项验过；
  - **决定性判据是退出码不是日志**：push 事件下 gate 的 `exit-code` 表达式返回 `'1'`
    （硬失败语义），三个 job 仍 success ⇒ **门禁参数下无任何 HIGH/CRITICAL 有修复版命中**。
  ⇒ **4 条 CVE（mcp 三条 + CVE-2026-34070）已全部消除并经 CI 证明。**
  历史留档：上一版运行 `38164723646`（head `09769e415`，failure）三个 job 红，
  **唯一原因**就是 `langchain-core (METADATA) │ CVE-2026-34070`，而 langchain 的
  删除发生在那次运行**之后** ⇒ 那次是真的红，**不是误报，也不是"未验证"能搪塞过去的**。
- ✅ **同日补上根因：给 image-scan 加了 `push` 触发器** —— 之所以会出现"整轮治理做完了、
  CI 一次都没验证过"，是因为 `.github/workflows/image-scan.yml` **原本只有
  `pull_request`（限 Dockerfile / docker/** / docker-compose*.yml）/ `schedule`
  （周一 05:00 UTC）/ `workflow_dispatch`，没有 `push`**，而 L-8 这 4 条 CVE
  **全是改 `requirements.txt` 修的**（升 uvicorn + mcp、删 langchain）
  ⇒ **改依赖从不触发任何门禁**，当晚的 schedule 纯属偶然兜住。
  现已加 `push: paths: [requirements.txt, .trivyignore, 本文件]`（带 `.trivyignore` 是因为
  改豁免清单同样改变门禁结果，"改豁免可以不验证"正是 `.trivyignore` 第 5-14 行原则要防的）。
- ⚠️ **push 时只跑真正读 `requirements.txt` 的 3 个镜像（app / commercial /
  voice-pipeline，约 12-15 分钟；全量 8 个约 30 分钟），实现方式是拆成两个 job**
  （`scan` / `scan-deps`，各用 job 级 `if` 分流）。**两条走错路的记录，别重蹈**：
  - ① **job 级 `if` 拿不到 `matrix` 上下文** —— `if` 在 matrix **展开之前**求值，
    可用上下文只有 `github` / `inputs` / `needs` / `vars`。写成
    `if: ... || matrix.name == 'app'` 会让整个 workflow 报 `Invalid workflow file`
    且**一个 job 都不起**（实测 `event=push` 直接 failure、jobs API 返回空数组）。
  - ② **`strategy.matrix` 是静态配置，`include` / `exclude` 都不接受 `${{ }}` 表达式**
    —— 换成 `exclude` 表达式后**仍然**同样失败。
  ⇒ **两条纪律**：①**「本地 actionlint 绿」不等于「CI 能跑」** —— actionlint 只做静态
  语法检查、不做运行时会话验证，这两种写法它**都报 0 问题**。它仍值得跑（能查基础语法），
  ```bash
  MSYS_NO_PATHCONV=1 docker run --rm -v "E:/microbubble-agent:/repo" -w /repo rhysd/actionlint:latest
  ```
  但**不能**当作"CI 会跑"的证据。⚠️ Git Bash 下 `$(pwd)` 会被改写成
  `C:/Program Files/Git/repo`，必须用 Windows 绝对路径 + `MSYS_NO_PATHCONV=1`（类 20.214 同型）。
  ②**GitHub 对 workflow 文件错误只给一句通用提示**（`This run likely failed because of
  a workflow file issue`）**不给行号** —— 第一次的根因是靠 actionlint 的离线报错直接指出来的，
  否则那一次只能瞎猜。
- ⚠️ **改了 Dockerfile / docker-compose 必须手动 `gh workflow run` 一次** ——
  `push.paths` **故意只含 `requirements.txt` / `.trivyignore` / 本 workflow 自身**
  （2026-10-13 实测：推 `770b6dedf`（改 Dockerfile）**没有**触发 image-scan）。
  **不要为了"覆盖全"把 `Dockerfile*` / `docker/**` 加进 push.paths** —— push 触发时跑的是
  `scan-deps`，只含 app / commercial / voice-pipeline **三个**镜像；而改
  `Dockerfile.funasr` 真正要扫的是 funasr，**它不在这三个里** ⇒ workflow 会跑、会绿、
  UI 显示"扫描通过"，**而真正受影响的镜像根本没被扫**（类 20.220：状态字段在说谎）。
  正确做法 = 手动 dispatch 全量 8 个：
  ```bash
  gh workflow run ".github/workflows/image-scan.yml" --ref main
  ```
  ⚠️ **不加 required checks —— 2026-10-12 主指挥已拍板"不加"，且这不是"再等等就能加"**：
  - main 的 required checks 仍是 9 个 Server Tests Baseline context，**不含 image-scan**
    ⇒ 现在 push 红了只是可见红叉，挡不住合并。
  - ⚠️ **但也不能直接加** —— `push` 触发器带 `paths` 过滤（requirements.txt /
    .trivyignore / 本文件），**推一个只改 README/CLAUDE.md 的 commit 时 image-scan
    根本不触发** ⇒ 那个 required check **永远不会出现** ⇒ 推送被永久卡在
    "Expected — Waiting for status to be reported"。
    **实测依据**：`a27ea3501`（只改 CLAUDE.md）image-scan 未触发，
    `5a313af6`（改了 .trivyignore）触发 —— paths 过滤确实生效。
    ⇒ **加了 required 等于把"改文档"变成不能推送的操作**（类 20.222 警告的
    "配置看着在挡、实际挡住所有事"的镜像）。
  - 将来若要变硬门，**必须同时**解决触发覆盖问题（三选一）：
    ① 去掉 `paths` 过滤（代价：每次 push 都跑 3 个镜像构建 + 扫描，各 12-15 分钟，
    按本仓 direct-push 频率约 2250 分钟/月，**可能超公开仓库 2000 分钟/月免费额度**，
    加之前须先查 Settings → Billing 实际用量）；② 改用 GitHub Rulesets 的
    required-workflow 语义（**本项目未验证其 path-filter 跳过时是否放行**，别当成已知）；
    ③ 拆出一个只做轻量检查（如 `pip list` 落 lock 文件 diff）的快 job 进 required，
    真正的镜像扫描仍作可见红叉。**在 ① 未落实前不要动 required。**
  - 当前 image-scan 的真实价值已经拿到了（2026-10-12 连续 3 轮 push run success）：
    **"改依赖会触发扫描"** 与 **"门禁真会红"** 这两点正是此前缺失的。

- ~~**langchain-core CVE-2026-34070 故意不登记进 `.trivyignore`**~~ —— 该判断（同日稍后被推翻）：
  当时认为它「有修复版但升不动」，按 `.trivyignore` 第 5-14 行「有修复版但未升不登记」的
  原则故意不豁免。**最终解法不是登记豁免，而是把依赖删掉**（见下方 C 段）——
  **这才是该原则的正解**：既真修掉暴露面，又不新增任何豁免条目。

### C. 三个 RAG-FW 孤立模块已删 + **langchain 依赖全部移除**（CVE-2026-34070 零改造消失）

- **删** `app/rag/multi_hop_engine.py`(177 行) 与 `app/rag/semantic_chunker.py`(172 行)，
  **四层证据 + import blocker 运行时实测**（类 20.223 第四步）结论一致"零调用方"：
  生产容器内屏蔽这两模块后全扫 **298 个** services/api/agent/rag 模块，唯一 import 失败的
  就是它们自己。连带移除 `requirements.txt` 的 **`langchain-community`**（全仓唯一使用者是
  已删的 multi_hop_engine），顺带消除 `langchain-experimental` 这个**未在声明里、靠传递依赖
  进来**的隐式依赖。
- ⚠️ **差点误判的点**：`docs/rag/HYBRID-RAG-STACK.md` 记着这两个能力由 `MULTI_HOP_ENABLED` /
  `SEMANTIC_CHUNKER_ENABLED` 控制且**默认值 `"1"`（默认开）** —— 只看这个会以为它们是活接线。
  但开关只是**模块内部自读**（传给 framework_gate 装饰器），而 `gate.py` 里的 framework_gate
  只在本模块内使用，**没有任何外部代码 import 这两个模块**。
  **"配置齐全 + 开关默认开 + 调用方为零"是最容易骗过静态检查的一种形态。**
  ⚠️ `app/services/graph_retriever.py` 的 `multi_hop_retrieve` 是**图检索的另一套实现**，
  同名不同物，已核实未动。
- ⚠️ **下面这条结论已被同一天的进一步取证推翻并订正**（保留原文以留痕，勿再引用）：
  ~~"langchain 1.x 建议不升"~~ —— 当时的判断是"升 1.x 会打断唯一那条活接线
  `app/rag/agent_retriever.py`"。但随后用 **import blocker 运行时实测**（296 模块全扫）
  发现**它同样是零调用方的孤立模块**，于是**根本不需要迁移**：
  **已连同 `app/rag/config.py` 的 4 个死开关一起删除，并移除全部四个 langchain 包**
  （`langchain` / `langchain-core` / `langchain-anthropic` / `langchain-community`）。
  ⇒ **CVE-2026-34070 零改造消失**，`git grep langchain -- app/` 现零命中。

  ⇒ **教训（比结论更重要）**：我在写下"它是唯一活接线"时，依据是
  `hybrid_retriever.py` 一句**过时注释**（"保留: agent_retriever._bm25_only 兜底用"）
  + 文档里"开关默认开"。**两者都不是调用关系。** 类 20.223 要求的
  **import blocker 运行时实测**才是判据，而它当时没做 —— 直到被当成正式立项去做才补上。

  ⚠️ 判据本身也有坑：**计数式探针必须想清楚分母**。我的第一版把"被屏蔽模块自身"
  也算进 `newly_broken`，于是得出"有调用方"的错误结论；改成"排除自身后"才拿到
  `0` 这个正确判据。
- **删 langchain 依赖前查过上游未声明的硬 import**（类 20.223）：唯一疑点是 `langfuse`
  （本仓在用，`app/core/llm.py` + `app/rag/lc_tracing.py`，其 metadata 含
  `langchain (>=0.0.309)`）。实测确认那是 **`extra == "langchain"` 的可选依赖**，
  本仓未装该 extra —— 一次性容器里只装 langfuse 不装 langchain，`import langfuse`
  正常（2.60.10）且 langchain 不会被带入。（`sentry-sdk` 那个同理也是 extra。）
  **若将来要重新引入 langchain**：CVE 修复版是 **1.2.22**（0.3.86 是 0.3.x 末版，
  没有更高的 0.3.x），且必须四包同升 —— `langchain-community` **没有 1.x**
  （PyPI 最高 0.4.2，且要求 core>=1.4.0），`langchain-anthropic` 要到 1.0.0
  才放开 core<0.4.0 的限制。

### D2. `Dockerfile` 改 multi-stage —— 626 → **293** 条，生产已切换（2026-10-13，commit `770b6dedf`）

扫 `microbubble-agent-app:latest`，HIGH/CRITICAL 626 条里，**裸基础镜像只有 65 条**，
**325 条是构建期 dev 包带进来的**：`linux-libc-dev` **196**（`gcc` 拉入，CVE 最早到 2015）
+ 8×`libav*-dev` 各 16 + `libssl-dev`。改成 builder / runtime 两段后 ——

| 项 | 改造前 | 改造后 |
|---|---|---|
| CVE 合计 | 626 | **293**（debian 290 + python-pkg 3），**−333 / −53.2%** |
| `-dev` 包残留 | 2 | **0** |
| `gcc` | 在 | **无** |
| 镜像体积 | 13.5 GB | **13.2 GB** |

- **真正需要现场编译的只有 2 个包**（扫了全镜像 257 个 `.dist-info/WHEEL`，254 个有预编译 wheel）：
  `pilk`（PyPI 只有 Windows wheel）与 `crcmod`（只有 `.tar.gz`，传递依赖自 `oss2`）。
  ⇒ **runtime 段必须从 builder 整份搬运 site-packages，绝不能重新 pip install**。
- ⚠️ **`crcmod` 无 gcc 时会静默降级**：pip **不报错**，但 `_crcfunext` 缺失、退化成纯 Python
  `_crcfunpy`，CRC 结果仍正确 ⇒ 功能在、速度掉几个数量级，**构建/CI/测试全绿都发现不了**。
  判据固定用 `hasattr(crcmod, "_crcfunext")`。
- ⚠️ **COPY 是合并语义，永不删除目标侧独有的文件** —— 不先 `rm -rf` 就 COPY，会让基础镜像
  自带的 `setuptools-79.0.1.dist-info` 与 builder 的 84.0.0 **两份 dist-info 并存**，
  `import setuptools` 命中旧元数据 ⇒ trivy 反而**多 2 条** CVE。实测残留 216 个文件。
  ⇒ 搬运 = **清空 + 全量拷贝**。
- 残留 top5 是 `ffmpeg` / `libavcodec59` / `libavdevice59` / `libavfilter8` / `libavformat59`
  （各 16）—— **运行时必需，删不得**。
- **同类文件尚未改造**：`Dockerfile.funasr` / `.whisper`（单阶段但**无 gcc**，风险更低）；
  `docker/Dockerfile.commercial` **已是 multi-stage**，但 runtime 缺 ffmpeg+libreoffice，
  **照抄本 PR 会跑不起来**；`Dockerfile.mcp` 无 apt 包不用动；
  `Dockerfile.voice-pipeline` 装 `python3.11-dev` 但**未取证**。
- ⚠️ bookworm → trixie 迁移（可再收一批）**暂缓**：跨 debian 大版本、
  `libavutil57→59` soname 变化、gcc 12→14，且实测 trixie 在 `deb.debian.org` 的 apt
  会进 `Ign` 死循环；而**只改 `FROM` 行是危险的** —— `Dockerfile:20-23` 硬编码 bookworm 源，
  改 FROM 后 apt 仍装 bookworm 包，**构建 RC=0 但产出缝合怪镜像**（类 20.220）。

### D3. 会议 256 全流程验收（2026-10-13）—— 流程通，但撞出 4 个待处置问题

用真实 2h24m 录音（73.7MB m4a）从建会跑到出纪要，**全程 17 分 04 秒**，产物达标
（摘要 344 字 / 讨论要点 8 条 / 决议 29 条，全部符合《会议纪要标准格式》）。以下是验收中
撞出的问题，**均未修**，等主指挥逐项处置：

> ⚠️ **2026-10-15 复核订正：下表 1/2/3 三条的「待修」标记全部已过期，无一需再做。**
> 逐条实测证据如下（**别照着旧表重复开工**）：
> - **#1 已完全闭环**（`24c60a76f` 代码 + `63960a6e1` dist）：`app/schemas/meeting.py:75`
>   已加 `media_duration_seconds`；后端 `meeting_recording.py:673` 与
>   `api/v1/meeting.py:143`、`agent/tools/meeting_tools.py:163,272` 三处**都已同时给出两字段**
>   并注明"展示必须优先 media"；前端 `MeetingDetailView.vue:490` 已是
>   `media_duration_seconds || audio_duration || 0`；**真数据已回填**
>   （DB 实测：256 `media=8669`、255 `media=10118`，而两者 `audio_duration` 仍是错的 39/NULL
>   —— 这恰好反证前端改读 media 是对的）。
> - **#3 已修**（`3613c54b9`）：`post_meeting_tasks.py:147` 已有 `_t_stage_download = _stage_now()`
>   并透传 `_persist_stage(..., started_at=...)`，即"阶段开工前掐表"。
> - **#2 不是待修，是已裁定不做**：见下方「会议通知：开始与完成都不做」段，
>   2026-10-13 主指挥明确拍板。它原先被标「待修」本身就是个文档失真。

| # | 问题 | 位置 | 状态（2026-10-15 复核） |
|---|---|---|---|
| ✅ **1** | **会议时长显示错**：`audio_duration` 存的是**录音会话墙钟时长**，媒体真实时长在 `media_duration_seconds`。实测 **256 的 `audio_duration=39` 而真实 8669 秒（差 222 倍）**；**255 的 `audio_duration` 是 NULL** ⇒ 前端 `v-if` 直接把时长标签**整个隐藏** | `app/api/v1/meeting_recording.py:672` + `web/src/views/MeetingDetailView.vue:49,51,500` | ✅ **已修**（`24c60a76f` + dist `63960a6e1` + 真数据已回填） |
| ⛔ **2** | **处理完成无通知**：docstring 写着"6. done — 完成通知"，但全文件**无任何 notify 调用**（2026-10-15 实测 `grep -n notify` 零命中；旧表写的 `:1071` 是已位移的过期行号）。成功完成后 `unread_count` 仍为 0 ⇒ 本次要盯 17 分钟，中途离开就不知道跑完了 | `app/services/post_meeting_tasks.py` | ⛔ **已裁定不做**（非待修）—— docstring 那句已于 `d2a425cfb` 清掉 |
| ✅ **3** | **`latency_ms` 名不符实**：`meeting_processing_stages` 里它记的是**落库调用本身**耗时（downloading 18ms / transcribing 59ms / 声纹 4ms），而阶段实际耗时是 60s / 603s / 117s ⇒ **用它做耗时监控会得到完全错误的结论**（又一个类 20.220） | `meeting_processing_stages` 写入处 | ✅ **已修**（`3613c54b9`，开工前掐表） |
| ✅ **4** | **SenseVoice 曾跑在 CPU 上** —— **2026-10-13 重建容器后已自动恢复**（当时记为"待排查"，实测**不需要排查，重建即恢复**） | GPU 侧 | ✅ 已解决 |

#### 问题 4 的真相：GPU 状态是**容器级**的，重建即恢复（2026-10-13 实测）

| 指标 | 旧容器（Up 5 days） | 重建后 |
|---|---|---|
| `active_device` | **cpu** | **cuda** |
| `gpu_broken` | **true** | **false** |
| `vram_mib` | 5874 | **18426** |
| `model_load_time_sec` | 67.5 | **13.7** |
| 稳态 rtf | 0.05–0.15 | **0.023**（快 2–6 倍） |

⇒ **配置本身没问题**（`SENSEVOICE_DEVICE` 一直是 `cuda`），是那个跑了 5 天的容器里
GPU 状态坏了。⇒ **遇到 `gpu_broken: true` 先重建容器再排查**，别急着重配 device。
对 256 那类 2h24m 会议意味着转写从 ~10 分钟降到 ~3.5 分钟。

#### 重建后的真转写验收（2026-10-13，四轮全绿）

用 `data/asr_eval/synthetic/01_basics.wav` 建基线，重建后跑 4 次：

    HTTP 200  0.09s  rtf=0.023  backend=sensevoice  segments=1
    text 逐字一致 ✅  '今天天气真好，我们一起去公园散步吧。'

⚠️ **首次推理有 ~15 秒的 CUDA 上下文初始化开销**（实测 14.85s），第二次起降到 0.09s
—— **别把第一次的慢当成性能回退**。基线那次是 0.3s（跑在 CPU 上），所以
"重建后反而慢了"的直觉是错的，要跑第二次以上再判断。

⚠️ 验证脚本用 `j["backend"]` 会 `KeyError` —— **`/transcribe` 返回的字段名是
`_backend`（带下划线）**，而 `/health` 里是 `backend`。两个端点命名不一致，别混。

#### 缺陷 1 的修法与验收要点（承接上表）
⚠️ 2026-10-13 订正: 本段原先被错挂在下面的「Alembic 单 head 守卫」标题下，**标题与内容完全不符**（类 20.224 的错误继承）。已在原位改正。


**缺陷 1 的修法比想象的宽 —— 要动三处 + 重建 dist**：`app/schemas/meeting.py:71`
只有 `audio_duration`、**没有** `media_duration_seconds`；前端全仓**从未引用过**
`media_duration`。⇒ schema 加字段 → 后端改用 `media_duration_seconds`（回退
`audio_duration`）→ 前端两处改读 → **`npm run build` 重建 `web/dist`**（W100 确定性构建）。
**只改后端不改 dist 没用**，用户看到的仍是旧的。

**验收中值得肯定的两点**（别在后续重构里弄丢）：
- 上传链路无损：18 片（`4MB×17 + 尾片 2.37MB`，前端因 73.7MB > 40MB 安全线自动切分片）
  5 秒传完，合并产物与源文件 **AAC 码流 MD5 完全一致**；合并产物小 3.9MB 是 `faststart`
  重排剥掉的容器 padding，**时长 8669.397333s 逐位相同** —— 不是数据丢失
  （这正是类 20.220 的"别只看合并成功这个状态字段"）。
- `meeting_chunks` 落 **70 行**，RAG 索引在线 ⇒ 类 20.219 的 celery 补注册修复有效。
- 音频经**生产域名** Range 请求返回 `HTTP 206 / Content-Range: bytes 0-1048575/69789478`
  ⇒ 隧道与回放链路正常。

⚠️ **`/transcribe` 的表单参数名是 `audio` 不是 `file`**（`app/sensevoice_server.py:219`
`audio: UploadFile = File(...)`）。写成 `-F "file=@..."` 会得 **HTTP 400**，很容易误判成
"服务坏了"。容器内有 `requests`，用它构造 multipart 最稳。

#### 会议通知：**开始与完成都不做**（2026-10-13 主指挥裁定）

会议处理跑完**不给任何人任何通知** —— 这是有意为之，不是遗漏。

**历史真相**（2026-10-13 全仓核实，此前无人发现）：

| 环节 | 文档/代码怎么说 | 实际 |
|---|---|---|
| **完成通知** | `post_meeting_tasks.py` docstring 第 10 行写着 `6. done — 完成通知` | **从未实现** —— 全流程唯一的"通知"是 `update_progress(DONE)` → Redis HSET + pub/sub（**1h TTL 不持久化**），消费方只是会议页进度条，关掉页面即失效 |
| **开始通知** | 有 `reminder_service.send_meeting_reminder()` 完整实现（约 89 行，走 `notify_user(context="meeting_reminder")`） | **死代码** —— `process_reminders` 主循环不做 target_type 分发，**全仓零调用点**；已删除 |

⇒ 二者都是类 20.220 的「注释在描述一个不存在的东西」：读代码的人（包括接手的新会话）
会以为会议有通知，用户实际一次都没收到过。会议 256 验收时"盯着 17 分钟"就是缺口的暴露。

⚠️ **若将来要恢复通知，收件人判据别用 `meetings.created_by`** —— 实测 **26 场会议里 4 场
为 NULL**（**含 255 与 256**），按它选人这两场会静默收不到。现役正确判据是
`reminder_service` 里的「**全部 active 参会者**」（join `MeetingParticipant` +
`Member.is_active`）。

⚠️ 铃铛（`NotificationBell`）走不通：`notification_service.py` 顶部写明「本服务**只**管
`file_mentions`（drive 协作提醒）」，而 `FileMention.file_id` 是 `nullable=False` 的 FK →
`knowledge.id`，**会议进不去**。要红点真亮得改 schema + 前端。
### D. CI 长期红灯：Alembic 单 head 守卫连续 6 次红 —— 根因是**漏装 pgvector**（`6889f3c32`）

- 守卫只装了 alembic 一个包，注释理由是"不连 DB 故无需 sqlalchemy"。**该前提不成立**：
  `alembic heads` 虽不加载 `env.py` / 不连 DB，但**会 import 每个 `versions/*.py` 以构建
  revision map**，而 `001_initial.py:12` 在**模块顶层** `from pgvector.sqlalchemy import Vector`
  ⇒ ModuleNotFoundError，守卫全红。已补装 pgvector + sqlalchemy，一次性容器实测
  `alembic heads` 输出 `145_kpt_content_tsvector (head)` 计数 1。
- ⚠️ **该红灯横跨 2026-10-11 的全部 commit**（含与 alembic 毫无关系的备份/隧道/drive 改动）——
  **红的原因与它们无关**，类 20.220 的变体：**红灯 ≠ 上次改动引入**。
  类 20.222 的"开保护前先修红"纪律要求把红查到底，而这项此前一直没人查。

### E. 本阶段新增的永久铁律

**类 20.224**（查依赖冲突必须 `pip install --dry-run` 逐对实测；不得引用文档里的"冲突链"，
且测解析**禁止 `--quiet`** —— 见下节正文）。

---

## 当前状态 (2026-10-13 声纹真值采集与质心重建 —— 一天重建 5 人 / 停用 1 人 / 否决 3 人)

> 上一版"当前状态"停在 2026-10-12 的 E 段；本节是 2026-10-13 一整天的工作。
> **本节最值钱的是"三次否决"与"六条方法论教训"** ——
> 前者各自挡住一次会写坏生产数据的改动，后者记录了**今日四次"自造阈值/自造测试"造成的误判**
> （其中两次是主指挥复核才发现的）。

### A. 起点：一个从未被发现的"大象"

`members` 表里 **15 对成员的质心两两余弦距离 < `MATCH_THRESHOLD`(0.65)**，即在线 argmin
**在纯静态层面就没有唯一答案**。最典型的：

| 成员对 | 余弦距离 |
|---|---|
| 杜同贺 ↔ 陈金薪 | 0.4522 |
| 王天志 ↔ 耿嘉栋 | 0.4620 |
| 贾琦 ↔ 蒋芦笛 / 赵航佳 ↔ 蒋芦笛 / 陈金薪 ↔ 周之超 / 关小未 ↔ 蒋芦笛 / 赵航佳 ↔ 耿嘉栋 | 0.58–0.64 |

### B. 转录里的 speaker 标签**双向不可信**，且规律干净

主指挥花一天逐段听辨（**100 段 / 19 人**），台账固化在
[`docs/voiceprint-confirmed-blocks-2026-10-13.json`](docs/voiceprint-confirmed-blocks-2026-10-13.json)：

| 现标签 | 人工确认准确率 |
|---|---|
| 王天志 / 张宏魁 / 赵航佳 / 耿嘉栋（**主讲人**） | **100%** |
| 蒋芦笛 | **25%** |
| 杜同贺（250 场）/ 陈金薪 | **0%** |

**规律：主讲人单次连续发言 100 秒以上 ⇒ embedding 稳 ⇒ 标签 100% 准；
插话型成员最长连续发言只有 5–19 秒 ⇒ embedding 噪声大 ⇒ 标签 0–33% 准。**
⇒ 任何"按标签筛选/统计/建库"的操作，**其可信度取决于该说话人的发言时长，不是取决于操作本身**。

### C. 蒋芦笛 n=369 —— 全库最大声纹，也是最脏的（反直觉）

| 证据 | 结果 |
|---|---|
| `voice_enrolled_at` 与 `voice_confirmed_at` 之差 | **11 微秒**（其余 5 个 anchor 是 8 分钟 ~ 103 天）⇒ **单条 SQL 一次写入**，不可能是 369 次 API 调用 |
| `member_voice_history` 中她的记录 | **0 行**（该表只存向量不存音频来源，无法反查） |
| 来源 | `voice_confirmed_meeting_id = 250`，且同日 memory 记载那 369 条**原被标成「贾琦」后被批量改判给她** |
| 质心是否退化（369 个同一向量求均值） | **否** —— 扫会议 250 全长 95 个时间窗，与她质心最近者仅 **0.1303**（退化应 ≈0.00）。**错的只是标签，不是时间键** |
| 实际危害 | 她吸走 **33/55** 段他人语音（含主讲人张宏魁、耿嘉栋、赵航佳） |

⚠️ **"n 大 = 可靠"是陷阱**：n 是**按标签统计**的，标签错则 n 越大约越脏。

⚠️ **且她是 anchor**（`voice_confirmed_at` 非空，语义"永不再修改"）
⇒ 一次批量污染就是**永久**的，系统永远不会自动修正她。

### D. ✅ 王天志重建成功（当日第一个，且经段级独立验证）

**方法**：用户逐段听辨确认 34 段 / 4 场会议 → 与写库前的 121 段原质心做 **alpha=0.8 线性融合**
→ 在 **40 正样本 / 55 负样本**（覆盖 18 个说话人）上留一场交叉验证。

| alpha | 跨场召回 | 误抢（**绝对数**，非比例） |
|---|---|---|
| 0.00（纯替换） | 87.5% | **8 段** |
| 0.75 | 80.0% | 3 段 |
| **0.80** | **77.5%** | **2 段（仅宋洋）** |
| 1.00（写库前原值） | 72.5% | 2 段 |

写库后在**同一测试集**上回读复验：**召回 72.5% → 77.5%（+5 个点），误抢不变**。
回滚点 `members_backup_before_wang_rebuild`（样本=121 原值）。

⚠️ **第一次尝试（单场 478 秒直接替换）失败**：top1 **81.2% → 75.0%**，
质心吸走 3 段他人语音（赵航佳/耿嘉栋/张宏魁各 1）。
**根因是单场样本过拟合到那一场的声学环境** ⇒ 跨场累积是硬要求，不是"数据更多点就行"。

### E. ⛔ 负结果（各自挡住一次错误改动；F 段有完整台账）

**① "把蒋芦笛移出匹配"是净负收益** —— 实测：她吸走的 55 段**只是被挪给了别人**
（刘莫菲/宋洋/肖佐林等 7 人**根本没有声纹**，判给谁都是错的），同时她本人 8 段里
**原本判对的 5 段全变错误**。且 `get_anchor_members` 只判 `voice_confirmed_at IS NOT NULL`
（**不看 `voice_sample_count`**），而会议流水线主路径正是 `identify_speaker_anchored`
⇒ **清 anchor = 直接把她从主链路摘出去**，不是"改元数据"。

**② 给 9 位"无声纹"成员录入声纹是净负收益** —— 逐人留一验证，**全部 5 人认回 0 段，
却各抢走 4–9 段他人语音**：

| 人 | 块数 | 场次 | 留一认回 | 抢走他人 |
|---|---|---|---|---|
| 刘莫菲 | 6 | 2 | **0/6** | 8 段（吴怡霏 5 + 关小未 3） |
| 宋洋 | 4 | 2 | **0/4** | 9 段 |
| 胡小琪 | 4 | 2 | **0/4** | 1 段 |
| 吴怡霏 | 2 | 2 | **0/2** | 6 段 |
| 刘子煜 | 2 | 1 | **0/2** | 4 段 |

⇒ **短促插话型成员之间 embedding 不可分**，这不是"样本量不够"，是**信号本身不足**。
对照：蒋芦笛那个污染 75% 的质心反而能认回 8 段中的 5 段 —— 因为 **n=369 的平均效应**
压下了噪声。**但补录另一个人替代不了平均效应。**

**③ 赵航佳 n=1 但有 12 段 / 2 场** —— 她其实是够条件的（242 场转录**只有 text+speaker、
无任何时间戳**故不可用）。暂未动手，等 5 人录入这条路被证伪后重新评估。

### F. ✅ 今日最终结果（重建 5 人 / 停用 1 人 / 否决 3 人 / 不启用 1 人）

真值台账：**171 段 / 20 人**（[`docs/voiceprint-confirmed-blocks-2026-10-13.json`](docs/voiceprint-confirmed-blocks-2026-10-13.json)），
全部来自主指挥**逐段听辨**，不使用任何标签作为真值。

| 处置 | 人 | 确认块 | 场次 | 效果 |
|---|---|---|---|---|
| ✅ 重建 | **王天志** | **59** | **7** | **段级（生产粒度）74.2% → 88.3%**；全场正确 109/171（与旧版**打平**） |
| ✅ 重建 | 蒋芦笛 | 28 | 3 | 全场正确 18 → **45** |
| ✅ 重建 | 赵航佳 | 12 | 2 | 29 → **41** |
| ✅ 重建 | 张宏魁 | 11 | 2 | 29 → **40**（抢走 0） |
| ✅ 重建+**再收紧** | 宋洋 | 6 | 1 | 246 外部会议误抢 **18/74 → 10/74（−44%）** |
| 🔴 停用 | **关小未** | 10 | 1 | 原声纹是蒋芦笛的声音 |
| ⛔ 否决 | 杜同贺 | 8 | 1 | 同分但多抢 **27** 块 |
| ⛔ 否决 | 刘莫菲 | 7 | 2 | **+1**（背 25 块误标） |
| ⛔ 否决 | 胡小琪 | 4 | 2 | **−2** |
| ⛔ **不启用** | **耿嘉栋** | 4 | 1 | 有 `n=60` 声纹但非 anchor；实测**启用仅 +2 块（+1.2 点）**，却与王天志相距 **0.32** ⇒ 不值（见 H.4） |

全部重建项均带 `voice_confirmed_by='rebuild-2026-10-13'` + 独立备份表 + 回读校验。

**当前 anchor 池 9 人**：王天志(59) 陈金薪(38) 蒋芦笛(27) 贾琦(12) 赵航佳(12)
张宏魁(11) 周之超(11) 宋洋(6) 杜同贺(4)。
**杜同贺(4) 与宋洋(6) 是全池最弱的两块**，已实测取舍，不重开。

### F2. 会议信息同步刷新（转录 + 纪要）

250 / 254 / 255 的说话人标签与摘要全部刷新（256 早些时候已做）。
`transcript` / `transcript_polished` / `speaker_stats` 三处同步，
**`start`/`end`/`speaker_label` 全部保留（缺失 0 条）**，各有 `meeting_<id>_backup_pre_label_refresh`。

| 会议 | 标签订正 | 要点 | 决议 |
|---|---|---|---|
| 250 | 115 段 | 8 | 4 → 12 |
| 254 | 115 段 | 8 | 3 → 8 |
| 255 | 374 段 | 8 | 7 → 27 |

**⚠️ 刷新前的摘要已被证伪**：250 曾有条要点写「【王天志】提出"团结、紧张、严肃、活泼"八字方针」，
而那段（36:05–38:39）在真值台账里是**「视频」**。旧摘要依据 25% 准确率的标签生成，**不可信**。

### G. 🔴 关小未：一个成员**从来没拥有过自己的声纹**

`voice_sample_count=3`，但那 3 个样本**全部是蒋芦笛的声音**：

| 音频 | → 关小未质心 |
|---|---|
| 蒋芦笛的 254 六段 | **0.037–0.080**（同一份声音） |
| 关键块 254·2459–2512（主指挥确认是蒋） | 0.0396 |
| 关小未**真声音** 254·824–903 | **0.82–0.85** |

**误判链**：254·2459–2512 夹在两段蒋的语音之间，却在批次4 里因
「主指挥未点名 ⇒ 标签正确」的约定被归给关小未 ⇒ 成了她那 `n=3` 声纹的建库来源。

⚠️ **但她的真声音与蒋相距 0.618，两人本来是可分的** —— 坏的是那个质心，
不是模型能力边界。（对照：同一人跨录音的留出距离是 0.10–0.19。）

### H. 十条方法论教训（今日全部踩过，其中 4 条是**自造阈值/自造测试**造成的）

1. **⛔ 阈值不能凭空设** —— 我用「距王天志 < 0.35」筛"哪些会议有他"，
   而 0.35 是从**他熟悉环境里的留出距离 0.10–0.19**类推的。
   实测 243/247 的真值块距离是 **0.39–0.43**，**整场被我判成"他没来"**，
   是主指挥要求复核才发现。**余弦距离的分布随声学环境变化，固定阈值不成立。**
   ⇒ 正确做法是**把距离报给人判断**，而不是拿一个自造的数下结论。

2. **⛔ 验证的粒度必须等于生产的粒度** —— 我的 CV 跑的是 **20–40 秒合并块**，
   而会议流水线处理的是**原始段（会议 250 均长仅 2.3 秒，1766/1906 不到 5 秒）**。
   同一个人：块级召回 77.5%，段级只有 87.9%（重建前）/ 94.6%（重建后）。
   **两个粒度的数字不能互相搬用。**

3. **⛔ 分母不能含"取不到样本"的段** —— 第一次算段级召回时，把 `emb_at` 返回 None
   （太短/ffmpeg 失败）的段留在分母里，**虚高 3.7 个百分点**（91.0% → 实际 94.6% 是修正后）。
   ⇒ 报百分比前先确认**分母 = 实际参与计算的样本数**。

4. **⛔ 测"移除某组件的影响"，测试本身必须复现生产的过滤条件** ——
   我第一版影响测试写成 `WHERE voice_embedding IS NOT NULL OR name='蒋芦笛'`，
   导致**清前清后她都必然在候选集** ⇒ 测出"零影响"的**假结论**。
   生产实际是两条不同链路：
   `get_anchor_members` 判 `voice_confirmed_at IS NOT NULL`（**不看 count**）、
   `identify_speaker` 判 `voice_sample_count > 0`。

5. **判据是「净增益显著为正」，不是「段数够 + 2 场」** ——
   同样是 **7 段 / 2 场**，宋洋 **+7**、刘莫菲 **+1**。
   差别不在段数，在**样本对该说话人是否真有代表性**。
   ⇒ **1 场 → 不重建（实测多抢 27 块）；2 场但净增益 < 5 → 也不值得**
   （+1 换 25 块新错名，比"认不出是谁"更误导）。

6. **⚠️ `voice_confirmed_at` 非空 = 该成员**永不再修改** —— 一次批量污染因此是**永久**的**。
   杜同贺的 `n=4` 垃圾质心至今是 anchor，且距王天志 **0.6116**（阈值内），
   每次识别都在参战。这是**已知取舍**（重建会更差），不是疏漏。

7. **⛔ 段级计数与块级计数不能混着说** —— 我把"耿嘉栋被王天志抢走 **42 段**"
   说成"42 块被白拿走"，实际那 42 是**块内子段**，他的确认块只有 **4 个**。
   ⇒ 报"被抢走 N"时**必须同时报粒度**，否则会把 1 块≈5 段的换算关系掩盖掉，
   进而高估收益/损失（本次差点据此做出错误的启用决策）。

8. **⛔ "抢走"要区分「抢占」与「兜底」** —— 新王天志质心实测抢走 171 个子段，
   但拆开看：**135 段的主人根本没有声纹**（肖佐林/陈天祥/刘莫菲/关小未/韩重阳等），
   它们改判前也无人认领，**不是抢占，是把无主的话挂到最活跃的人名下**；
   真正的抢占只有 36 段。**不区分这两者，会把"兜底"误判成"破坏"而白白回滚。**

9. **⚠️ `reanalyze_with_speakers` 会毁数据，别用它** ——
   `app/services/meeting_service.py:313` 重建 transcript 时只写
   `{"speaker", "text"}`，**丢掉 `start`/`end`/`speaker_label`**，
   并把 `speaker_mapping` 整个覆盖成传入的映射。
   ⇒ 正确路径：`transcript_editor.update_transcript_speaker`（`_copy_entries` 保字段、
   同步 raw+polished）+ **只**调 `meeting_analysis.analyze_transcript` 重跑摘要
   + `compute_speaker_stats` 重算统计。本次 4 场会议刷新后字段缺失 **0 条**。

10. **⛔「有质心」≠「该启用」** —— `get_anchor_members` 判
    `voice_confirmed_at IS NOT NULL`，**不看 count**，所以**有向量但没被确认过的成员
    从不参战**。实测耿嘉栋（`n=60`）若启用，净增益**仅 +2 块 / +1.2 个百分点**，
    而他与王天志相距 **0.32**（阈值内，等于给最活跃的说话人挂个贴身对手）⇒ **不启用**。
    ⇒ 决策依据必须是**启用后的实测净增益**，不是"他有没有质心"。

**当前阈值内互撞 11 对，全部是实测确认过的取舍**：
王-耿 0.3204、王-赵 0.4654、杜-陈 0.4522、王-宋 0.5463、王-蒋 0.5652、
贾-蒋 0.5947、陈-周 0.5968、王-陈 0.6001、王-杜 0.6116、耿-宋 0.6116、王-周 0.6391。
⚠️ **距离 < 阈值 ≠ 实际会抢**（实测宋洋距王天志 0.55 时只抢 8 段），
所以互撞表是**风险提示**而非结论，**结论只能来自实测净正确数**。

### I. 仍未解决

| 事项 | 阻塞原因 |
|---|---|
| 关小未（10 段 / **仅 254 一场**） | 需第二场录音 |
| ⚠️ **宋洋**（7 段 / 2 场）在会议 246 单场吸走 **150/693** 段 | 已排除质心过松（自身距离中位 0.103）；疑为**声纹落在人群密集区**（距王天志 0.5576 / 距蒋芦笛 0.6303，均 < 阈值）。重建验证集**不含 246**故未覆盖，待主指挥自查 |
| 肖佐林（8 段 / 仅 250）、韩重阳（3 段）、陈天祥/李胜景/王书馨（各 1 段） | 素材量不足，**非挖掘深度问题** —— 有音频的 9 场会议已全部处理完 |
| 会议 **242**（591 段，含赵航佳/宋洋/韩重阳） | 转录每段**只有 `text`+`speaker`、零时间信息** ⇒ 无法做时间区间提取；除非重跑 ASR 重新生成带时间戳的转录 |
| 会议 **246**（08-21，693 段） | 主指挥确认**全场是现场会议、全是外部人员**，整场作废 |
| 宋洋的**第三场**样本 | 扫完 250 全场，距他最近的 18 段里**只有 1 段**是他（且主指挥判为"还不清晰"）；其余 12 段实为王天志、1 段外部视频 ⇒ **250 里他几乎无可用第三场** |
| 短语音成员的算法层改动（按时长/质量降权） | **新立项**，本次未做 |

## 类 20.224：查依赖冲突必须实测，不得引用文档里的"冲突链"

**规则**：判断两个包能否共存（或某个上限版本卡在哪），唯一可信办法是
**`pip install --dry-run` 逐对组合实测**。**不得**引用 `requirements.txt` 注释、
`.trivyignore` 注释或历史 commit message 里写的"冲突链"。且**测解析时禁止 `--quiet`**。

**Why（2026-10-12，同一阻塞问题连续三轮归因、错了两轮）**：

| 轮次 | 当时写下的"冲突链" | 实测真相 |
|---|---|---|
| 第 1 轮 | `mcp` 要 `websockets>=15`，撞 `websockets==12.0` 硬钉 | **不成立**。`mcp 1.28.1 + websockets 12.0` 与 `+15.0` **均**可解；唯一阻塞是 uvicorn。且 websockets 早在 2026-10-11 已放宽成 `>=12.0,<16.0`，容器实测装 15.0.1 |
| 第 2 轮 | "改 mcp 任何版本都无效，必须先做 ASGI 栈升级立项" | **属实**，但前提是"不动 uvicorn" |
| 第 3 轮 | 我自己：测 `langchain-community==1.0.0` 用了 `--quiet` | **该版本根本不存在**（PyPI 最高 0.4.2），但 `No matching distribution found` **被 `--quiet` 吞掉**，看起来像"可解" |

⇒ **关键机制：冲突链会随别的改动悄悄作废，而文档/注释里的结论不会自动更新。**
第 1 轮的错误结论就因为写进了 `requirements.txt` 注释，成了第 2 轮推理的前提 ——
错误被**静默继承**，且每轮都"看起来严谨"。

⇒ **两条配套纪律**：
1. **实测**：`pip install --dry-run "A==x" "B==y"` 逐对跑，**不加 `--quiet`**
   （它会吞掉解析失败、制造"可解"假象）。结论要写成"实测 + 组合清单"，不写"根据文档"。
2. **注释里写冲突链时必须标注日期与复核条件**，否则读者无从判断它是否过期。

**配套坑（同一轮踩到）**：**计数式探针必须想清楚分母**。判"某模块是否孤儿"时用
import blocker 屏蔽它再全扫 import，若把**被屏蔽模块自身**也算进"新增失败"，
会得出"有调用方"的错误结论 —— 正确判据是**排除自身后**新增失败数。
（这条与类 20.223 的 import blocker 是同一个工具的两个使用细节。）

## 状态快照档案（2026-08-04 → 2026-09-18）

> **2026-09-30 三层重排**：以下 18 段是**历史状态快照**（每段自称「当前状态」实为
> 当时快照），已迁至 [`docs/incident/2026-08-04--2026-09-18-status-snapshots.md`]
> (../docs/incident/2026-08-04--2026-09-18-status-snapshots.md)，原 CLAUDE.md 行 43–926。
> 留在原地会让读者要先读完 900 行事故日志才能看到规则。
>
> 从中提炼的 **类 20.xx 永久铁律**已上移到下方 `## 永久铁律` 章节。
>
> 快照目录：
> - 当前状态
> - 当前状态
> - 当前状态
> - 当前状态
> - 当前状态
> - 当前状态
> - 当前状态
> - 当前状态
> - 当前状态
> - 当前状态
> - 当前状态
> - 当前状态
> - 当前状态
> - 当前状态
> - 当前状态
> - 当前状态
> - Phase 5 DFT 工具集成
> - 当前状态
> - 当前状态
> - 当前状态

---

## 永久铁律（类 20.xx — 从事故提炼，2026-09-30 提取独立成章）

> 每条对应一次真实事故，是**现在该怎么做**的规则，不是历史记录。
> 事故上下文见 `docs/incident/2026-08-04--2026-09-18-status-snapshots.md`。
> 覆盖类 20.155–228（编号不连续，20.165–20.170 / 20.173–20.179 /
> 20.189–20.211 无对应条目）。
> ⚠️ **本行原先写死"共 36 条"，已删** —— 条数会随新增漂移，写死即失真（类 20.224 的教训）。
> 要数就现场数：`grep -cE '^- \*\*类 20\.[0-9]+\*\*' CLAUDE.md`。

- **类 20.155**: bench 脚本 --help 子进程必须显式 PYTHONPATH=REPO_ROOT
- **类 20.156**: argparse --help 在某些版本重定向到 stderr, subprocess 必须 capture_output=True
- **类 20.157**: `embedding::text` 返回 string, 不是 list, Python 端需 `str.strip('[]').split(',')`
- **类 20.158**: 容器 alembic 链可能与 worktree 完全不同步, 必须实测容器 (W-N-A +5 实战)
- **类 20.159**: 索引名 `idx_*` vs `ix_*_hnsw` 实际两种前缀, 必须 psql \di 实测
- **类 20.160**: plan 假设 `knowledge` 表有 HNSW 索引, 实测 knowledge 无 HNSW 索引 (W97 PR2 段落级更关键)
- **类 20.161**: pgvector asyncpg 必须 `embedding::text` 字符串参数
- **类 20.162**: `halfvec_cosine_ops` vs `vector_cosine_ops` 必须匹配列类型
- **类 20.163**: 232 行小数据集 HNSW recall 必 1.0, 真实退化要 10w+ 行
- **类 20.164**: 派工 brief 假设 `ALTER INDEX SET (m)` 是 pd 工具, 实测是 no-op (W-N-A +4 实战)
- **类 20.171**: plan "single cherry-pick" 不可信, 主拍收口必复核 alembic heads + 关键改动是否真进 main (W-N-D 收口实战)
- **类 20.172**: 并行 agent 锚点编号冲突 (DFT 集成 agent 用了 W-N-D +1/+2 锚点), 派工 brief 锚点编号应预留 buffer

**W-N-A/B/C/D 沉淀**:
- `docs/superpowers/plans/2026-08-05-pgvector-optimization.md` (1846 行, 计划 + 审查修订)
- `memory/w-n-{a,b,c,d}-{startup,closure}-2026-08-05.md` (8 份)
- `scripts/bench_hnsw_params.py` + `scripts/bench_late_chunking.py` (2 个 bench 工具)
- `scripts/reembed_knowledge_bge_m3.py` + `scripts/check_pgvector_version.py` (2 个 utility)
- `app/services/late_chunking_service.py` (新服务)
- `app/models/types.py` (HalfVector wrapper)
- `app/services/embedding_service.py` (双后端扩展, +145 行 0 改老 API)
- `app/models/{knowledge,meeting,member}.py` (HalfVector Column 改写)
- `app/services/hybrid_retriever.py` (追加 _chunk_late_recall 方法)
- `alembic/versions/099-104_*.py` (6 个新迁移)
- `docs/decisions/2026-08-05-bge-m3-decision.md` (bge-m3 决策文档)
- `results/{hnsw_knowledge_100q,late_chunking_bench_2026-08,round11-bge-m3-100}.json` (3 个 bench JSON)

**W19 选项 A 维持** (W-N-D+ 真接入, W-N-E 冷热分层 PoC, W-N-F 领域微调起步 留未来 PR 不发起新排期)

**未来 PR 派工顺序** (W-N-A/B/C/D 收口后):
- W-N-D+ 真接入: GPU + bge-m3 模型下载后立即跑真 bench
- W-N-E PoC: 冷热分层路由层实测 (1 周)
- W-N-F 起步: 领域微调 LoRA 数据构造 (1-2 月长跑)

- **类 20.180**: W-N-B delivery 漏修 — HalfVector 漏 comparator_factory → cosine_distance 全 500
- **类 20.181**: `from X import Y` 创建直接引用, patch 目标必须是被调用模块的本地绑定
- **类 20.182**: conftest `import app.models` 覆盖 `from app.main import app` 的 FastAPI 绑定 → 用 as 别名
- **类 20.183**: (历史, 2026-09 失效) NOT NULL 字段 (wechat_id) 在 test fixture 必须显式提供 — wechat_id 列已随企业微信下线删除 (alembic 139)
- **类 20.184**: server_default 字符串必须 text() 包裹, 纯字符串被字面量引用

- **类 20.185**: `.session-item` / `.session-item-wrapper` `display: flex; align-items: center` + `.session-actions { flex-shrink: 0 }` + 内部 button `::before { inset: -8px }` 把 actions 最小高度撑到 ~44px;`.session-content` 默认 `flex-shrink: 1` 被压扁成单行,`title + meta + preview` 三行文字叠在一起
- **类 20.186**: `SessionItemRow.vue` **完全无 `<style scoped>` 块** — virtual 模式渲染时所有 `.session-item` 0 padding/margin/min-height, 全裸奔堆在 (0,0)。**任何独立渲染组件必须自包含 `<style scoped>`** 或由父 scoped 传递
- **类 20.187**: `SESSION_ITEM_HEIGHT = 56`(V-N-I 估算)远小于实际渲染卡片 ~64-72px,在 SessionItemRow virtual 模式下每对相邻卡片 top: 0/56 视觉重叠 8px(Virtual 模式用 `position: absolute; top: virtualTop + 'px'`,但 spacer 高度 < total real height)
- **类 20.188**: 移动端使用 `MobileSessionDrawer.vue`,不是桌面 `SessionSidebar.vue`,二者 class 名 `.session-item` 但 CSS scope 独立,**对话重叠截图必须先确认是 mobile 还是 desktop**,移动端修 `MobileSessionDrawer.vue`,桌面修 `SessionSidebar.vue`

**统一修复模式** (适用所有 3 组件):
- `.session-item[.session-item-wrapper]` 加 4 件强约束:`min-height: 64px !important; overflow: hidden !important; position: relative !important; box-sizing: border-box !important`
- `.session-content` / `.session-item` 加 `flex-shrink: 0` 防 flex 容器压扁
- `.session-item` margin `2px 8px` → `2px 8px 8px`(卡片间 8px 间距)+ `box-shadow: 0 1px 3px rgba(0,0,0,0.04)` 视觉立体感
- `.session-preview` 用 `-webkit-line-clamp: 2; line-clamp: 2; display: -webkit-box; overflow: hidden` 强制 2 行截断(LLM 消息 preview 数据常含 `\n`,旧 `nowrap` 不截断导致卡片极高)
- 桌面版再调 `SESSION_ITEM_HEIGHT: 56 → 72` + `SESSION_VIRTUAL_THRESHOLD: 50 → 200`(小数据自动 inline flow,不触发 virtual 模式 absolute 定位)

- **类 20.212**: 清理"残留"容器/compose 栈前必须 `docker inspect` 查 mounts + 生产
  端口依赖 —— desktop-conversion-plan 栈和 app-revived 看着像残留实为 8/28 救急生产
  接线, 按"名字+年龄"判残留误删会断生产。判据 = 是否被生产链路引用, 不是名字。
- **类 20.213**: `docker compose up -d` 后的验证必须全链路: 每个重建容器 `docker
  network inspect` 查网络归属 (类 20.140 漏网偶发) + nginx health 必须等到 healthy
  + **生产路径 curl** (云端域名), 只 curl 本机端口的自己服务不够 — minio 漏网 +
  9000 断线两层问题在切换当时都已存在, 只验 DFT 代理全绿照样漏过。
  **⚠️ 2026-10-12 头像事故补充: A/B 对照实验的两侧必须同层, 且路径要选对** ——
  本规则要求的"打生产域名 curl"反过来被我用成了对照实验, 却**对照了两台服务器**:
    错: `curl -H "Host: agent.mnb-lab.cn" http://localhost/...` → 打的是**本机** nginx
        `curl https://agent.mnb-lab.cn/...`                    → 打的是**云端** nginx
    (`agent.mnb-lab.cn` 解析到 60.205.93.8 = 云服务器, **不是本机**)
  两侧差异被我归因成"同一份配置里 HTTP 块对、HTTPS 块错", 实则是**两台机器的两套配置**,
  结论完全建立在错误对照上, 并据此差点把一份会打断云端的错误改动推上线。
  ⇒ **纪律**: ①对照实验两侧必须**同一层**(同机同协议, 或同机不同协议且确属同一配置);
  ②判"某层有没有问题"前先确认**请求实际落到哪台机器**(`nslookup` 看解析, 不是想当然);
  ③**两者都"变好/变坏"都不构成因果证据** —— 尤其当两次测试的机器/配置/上下文任一项不同时。
  这是类 20.220 的变体: 不止状态字段会骗人, **对照组本身选错也会编出一个看似严谨的假结论**。
- **类 20.214**: 生产依赖的裸进程单点 (ssh.exe 反向隧道) 必须有判活守护 + runbook;
  隧道 -R 端口与容器发布端口的对应关系 (9000↔minio) 必须文档化, 否则换端口/重建即静默断线。
  **⚠️ 2026-10-12 头像事故补充两条, 两条都是本规则本已隐含、但没落到可执行检查的**:
  ④ **手工起隧道必须转发 `$FORWARDS` 全部条目, 不能只抄一部分** ——
     `tunnel/start-ssh-tunnel.ps1:15-19` 定义 **三条** `-R`(8000 app / 9000 minio / 2222 ssh)。
     主指挥手工起隧道时只抄了 8000 与 2222, **漏 9000** ⇒ 云端 nginx 的
     `proxy_pass http://127.0.0.1:9000/` 无处可代理 ⇒ **全站头像 502**(页面静态资源
     照常显示, 只有 API/头像挂, 极易误判成"前端 bug")。起隧道后**必须逐条核对
     `ss -tln` 三端口齐全**, 不能只看 `ssh` 进程活着就算好。
  ⑤ **本机 `nginx/conf.d/tunnel.conf` 是云端的配置源, 不是"本机私有配置"** ——
     `scripts/deploy-auto.sh:242`(在**云端**执行)会
     `cp "$PROJECT_DIR/nginx/conf.d/tunnel.conf" /etc/nginx/conf.d/default.conf`。
     ⇒ 改这份文件**必须同时站在云端视角验**: 云端与本机的 `127.0.0.1` 指向**不同机器**
     (云端 = 隧道端点; 本机 nginx 容器 = 容器自己)。实测云端 `getent hosts minio`
     **解析失败**, 所以把 `127.0.0.1:9000` 改成容器网络名 `minio:9000` **会直接打断云端路由**,
     且因为本地测本机 nginx 反而"变绿"而更隐蔽 —— 该改动必须回滚。
  ⑥ **云端服务器不跑 MicroBubble 的任何容器 —— Docker 全在本地 PC** (2026-10-25 实测澄清) ——
     拓扑: `nginx(云端) → SSH 反向隧道 → frpc(本地 PC) → Docker app/celery/db/minio(本地 PC)`。
     云端只跑三样: nginx、webhook 服务(`/opt/microbubble-agent/scripts/webhook.py`, 端口 9001)、
     以及另一个项目 lab-miniapp 的 node 进程。
     ⚠️ **云端 `docker info` 仍可能返回 200** (snap 装的 docker 包还在, 历史上云端确实跑过
     MicroBubble 容器, 迁到本地后镜像/容器成了残留) ⇒ **"docker 能用"不等于"云端该跑容器"**。
     2026-10-25 实测: 云端 `docker system df` 仍显示 4 镜像 / 3 个**停止的**容器而 `docker ps` 为空
     —— 全是历史残留, 删掉不影响生产; 而 `scripts/deploy-auto.sh` 的部署日志每次都在打
     「未找到 postgres 容器」/「数据库容器未运行」, 正是它让人误以为云端该有容器。
     ⇒ 判「某操作该在哪台机器做」的正确问法是**「它要动的是本地 PC 的容器, 还是云端的文件」**,
     **不是**「这台机器上 docker 能不能跑」。
     ⚠️ 同源教训: `scripts/deploy-auto.sh` **同一个文件里两种说法** —— 第 137 行注释写对了
     拓扑(「Docker app (本地 PC)」), 而第 290 / 326 行却写成「在云端 `docker ps` 找 db 容器」
     ⇒ 读者取到哪一种**取决于读到哪一段**。已把两处改成「云端不跑容器(预期) → 提示在本地 PC 执行」
     并把过时的容器名 `microbubble-agent-app-revived` 改成现役的 `microbubble-agent-db-1`
     (旧名与 `scripts/sync_sequences.sh` 不一致 ⇒ 那段检查在任何机器上都是死代码)。
  **三条排障陷阱 (2026-10-11 SSH 故障排查实测)**:
  ①**隧道与 GitHub SSH 是两条独立链路** —— 隧道目标 `agent.mnb-lab.cn`, 用本机 key
  对云服务器, **不连 GitHub**。看到"SSH 挂了"不要先怀疑隧道 (若它依赖 GitHub, 早死了);
  ②**判活日志写 `logs/tunnel-guard.log`, 不是 `tunnel/ssh-tunnel.log`** —— 后者停在
  2026-09-21 且尾部有陈旧的 exit 255 重启循环, **排障时被它误导过一次**;
  权威判活证据 = `logs/tunnel-guard.log` 每 5 分钟一条 `alive (pid=N) - no action`;
  ③**`tunnel/ssh-tunnel.pid` 内容是陈旧的** (实测写 69952, 实际进程 2828) ——
  判活以日志里的 pid 为准, **别信这个文件**。
  **git remote 保持 HTTPS** (2026-10-11 定): GitHub 曾对本机 IP:22 短时阻断
  (`Connection reset by 20.205.243.166`), 443 与 gitlab:22 同时正常 ⇒ 排除本机防火墙,
  锁定 GitHub 侧。已自愈, 但**证明 SSH 是会随机断的依赖**; HTTPS 凭
  `gh auth git-credential` 零摩擦。若确需 SSH 走 `ssh.github.com:443` 而非 `:22`。

- **类 20.215**: 注释实验块必须**逐字段圈界** — app 的 `deploy/mem_limit` 实验连带把
  `healthcheck` 和 `restart: unless-stopped` 一起注释掉, 事故潜伏整个 8 月。生产服务 compose
  里 `restart` 策略缺失 = 重启必断; 每次改 compose 后跑 `docker compose config` 并
  `docker inspect -f '{{.HostConfig.RestartPolicy.Name}}'` 抽验核心容器。
- **类 20.216**: 用脚本/ps1/heredoc 写 schtasks `/TR` 或任何含反斜杠路径时, `\r` `\n` `\t`
  会被转义吞成控制字符 (本次 2 个任务路径腐坏: `scripts\tunnel`→`scripts< TAB>unnel`、
  `dft-service\run`→`dft-service<CR>un`), 任务永远 exit 1 且**日志一行不写** (进程根本没启动)。
  注册后必须 `Get-ScheduledTask | % Actions[0].Execute` 回读比对长度 + 无控制字符。
  **⚠️ 同源第 2 形态 (2026-10-12 实战, 当日自查抓到 7 次): Git Bash 的 GBK 环境
  会把 heredoc 里的中文吞成 U+FFFD (`\xef\xbf\xbd`)** —— 表现为 commit message
  或文件里个别汉字消失/变成替换字符, **git 不报错、CI 不报错、测试不报错**,
  只有主动 `grep -o $'\xef\xbf\xbd'` 才看得见 (今日 7 次全靠这条自查拦住,
  否则污染会永久进 git 历史且**不可见**)。
  **同源第 3 形态**: 本机 Python 读中文文件默认 GBK,
  `open(p,encoding='utf-8')` 缺失即 `UnicodeDecodeError: 'gbk' codec`。
  **三条纪律**:
  ① **写含中文的内容一律走文件 + 显式编码**, 不直接写 heredoc:
     `git log -1 --format=%B > f; PYTHONUTF8=1 python -c "改字节"`;
 ② **改完必自查**: `grep -o $'\xef\xbf\xbd' <file> | wc -l` 期望 **0**
     (commit message 用 `git log -1 --format=%B | grep -c $'\xef\xbf\xbd'`);
  ③ **修字节用 Python 字节层替换, 不用 str.replace** ——
     str 层会再经一次编码转换, 改完往往还是坏的; 实测用
     `raw.replace(b'...'.encode()+B*3+b'...', b'...')` 一次到位;
     已污染的用 `git commit --amend -F <file>` 修 (未 push 时安全,
     已 push 用 `git push --force-with-lease`)。
  ⚠️ 本机 Python **默认 GBK**, 任何 `print()` 中文都可能抛
  - **同源第 4 形态（2026-10-13 实测踩 3 次）: 含中文的 `.ps1` **必须带 UTF-8 BOM**，否则
    PowerShell 5.1 按 GBK 解码 ⇒ 中文乱码把引号吃掉 ⇒ 报 `MissingExpressionAfterToken` /
    「字符串缺少终止符」这类**看起来像语法错、其实是编码错**的解析错误。
    本仓既有约定实测为: **含中文的加 BOM**（`voice-alert.ps1`）、**纯 ASCII 的不加**
    （`install-offsite-scheduler.ps1`）。⇒ **每次重写含中文的 .ps1 都要重新确认 BOM**
    （工具重写不带 BOM）。自查 `head -c 3 f.ps1 | od -An -tx1` 应为 `efbbbf`。
  - **同源第 5 形态（2026-10-13）: Task Scheduler 回读的 `DaysOfWeek` 是 **COM 编号**
    （Sun=1 Mon=2 Tue=3...），**不是** .NET 的 `DayOfWeek`（Sun=0 Mon=1 Tue=2...）。
    拿 .NET 枚举解释会把 `Monday(2)` 误判成 `Tuesday`，**连断言都跟着写错**。
    正确判定: `$svc = New-Object -ComObject Schedule.Service; $svc.Connect();
    $svc.GetFolder('').GetTask('<name>').Definition.Triggers.Item(1).DaysOfWeek`
  - **同源第 6 形态（2026-10-13）: 改文件时**必须保留原行尾**。本仓存在**混合行尾**
    文件（`app/services/reminder_service.py` 是 CRLF，而 `CLAUDE.md` /
    `app/services/notification_service.py` 是 LF）。用 Python 写文件若用默认换行，
    会把 CRLF 全压成 LF ⇒ `git diff` 把整个文件视为重写（预期删 89 行、实际
    **510 insertions / 590 deletions**）。⇒ Python 读写一律 `newline=''` 保住原样；
    **改完必查 `git diff --stat` 规模是否与预期相符**，不符先 `git checkout --` 恢复重做。  `UnicodeEncodeError: 'gbk' codec can't encode character <U+FFFD>` ——
  见到这个报错就是编码问题, 不是代码逻辑问题。
- **类 20.217**: alpine 容器里 healthcheck 用 `localhost` = 解析 `::1`, nginx 只听 IPv4 时
  探针永远 connection refused → 假 unhealthy 长期遮蔽真状态; 探针一律 `127.0.0.1` 字面量,
  且优先探"穿过反代到上游"的路径 (/health 经 nginx→app) 让 healthcheck 本身就是端到端验证。
- **类 20.218**: **录音心跳必须绑「录音会话」(模块级单例), 不能绑 UI 组件** ——
  2026-10-08 会议 255 事故 (`docs/incident/2026-10-08-meeting-255-orphan-cleanup.md`)。
  全站 `<router-view>` 无 `<keep-alive>`, 组件卸载即心跳死亡; 而**恢复/续传路径**
  (`MeetingRoomView.vue` / `MobileMeetingRoom.vue` 的 onMounted) 直接调
  `useGlobalRecorder().start()`, **绕过** `AudioRecorder.handleStart()` —— 09-15 的
  心跳守卫唯一启动入口在按钮上, 于是会议 255 录音 38min **全程 0 心跳**, 被
  `orphan_meeting_cleanup` 判死。**该修复从未在真机 iOS 上生效过** (会议 253 其实是
  失败事故, 254 成功只因桌面 Chrome 触发 timeslice 有分片)。
  **四个必须同时满足**: ①心跳状态是模块级变量, 与 `useGlobalRecorder` 同寿命,
  **不在 `onUnmounted` 里停** (组件卸载 ≠ 录音结束; 只有 stop-recording /
  cancel-recording / merge 完成才停); ②meetingId 到位**立刻**补心跳, 且**不用
  `if (isActive())` 做前置守卫** —— 恢复路径时序是「先设 meetingId (MediaRecorder
  还没启动) → 后 start()」, 带守卫的 watch 必然一次都不触发; ③恢复/续传路径必须与
  新建路径**同样**启动心跳, 不许"按钮路径有、恢复路径没有"; ④`visibilitychange →
  visible` / `pageshow(persisted)` / `focus` 切回前台必须**立即**补一次心跳 (iOS
  后台挂起后 interval 会被冻结, 那 60s 正是误杀窗口)。
  **配套后端纪律**: 孤儿清理**有分片就不删 MinIO** (原版无条件删 = 用户连补救机会
  都没有); 心跳端点必须走**独立限流 tier** 且 **429 也要写审计** (否则"audit 无心跳
  = 前端未发"的排查方法学失效, 本次白查 2 小时)。
- **类 20.219**: **新增 celery task 模块必须同时进 `celery_app.conf.imports` 显式列表** ——
  2026-10-08 会议 255 事故追查发现。`app/services/meeting_chunk_service.py` 定义了
  `index_meeting_chunks_task`, 但该模块从未进 imports, autodiscover 也覆盖不到
  (`related_name=None` 只 import 主模块, 且 imports 才是权威列表) → worker 记
  `Received unregistered task of type '...'` 后**静默丢弃**。派发点
  (`post_meeting_tasks.py:1014`) 只打 INFO 不校验, 于是**自 `d1aa07adb` 起每条新会议
  转录都没进 `meeting_chunks`**, 会议这一路 RAG (`hybrid_retriever.py:450` 第 5 路
  meeting_chunks 向量召回) 实际为空, 无人察觉。
  **纪律**: ①`grep -rl "@celery_app.task" app/services/` 的结果**逐个**比对 imports 列表,
  漏一个就是一条静默失效的链路; ②`.delay()` 派发点必须能区分"派发成功"与"worker 认领",
  只 log INFO 等于没校验; ③worker 日志 `grep -i unregistered` 应作为**部署后固定验证项**;
  ④验证用 `celery inspect registered` 回读任务名, 别只看容器 healthy (容器健康不代表
  任务注册完整)。
  **同源第 2 例 (2026-10-09, commit `381958bea`)**: `app/services/drive_index_service.py`
  (`index_drive_content_task`, 自 `bd9c09bcf` 2026-09-02 落盘起同样漏注册)。**存量后果
  不是"零 chunk"而是更隐蔽的脏数据**——`rag_auto_ingest_service` (已注册, hourly beat)
  按 `analysis_status=='pending'` 选行而**不按 `storage_mode` 过滤**, 会把 drive 行的占位
  `content = "[drive upload] <file_name>"` 当正文切 chunk + embedding, 于是 drive 检索命中
  的是 30 字符占位串而非 PPT/PDF 真内容 (实测 326 文件: 275 有真 chunk 来自一次性
  `backfill_drive_content.py` 手工回填, 48 只有占位垃圾, 3 个零 chunk)。
  **补纪律 ⑤**: 漏注册的链路**未必表现为空**, 会被别的已注册 task 用占位/低质量数据
  "兜底"填充, 检索层看起来有数据实则全是垃圾——排查时必须**抽查 chunk 正文**, 不能只
  `count(*)` 行数; ⑥`rag_auto_ingest_service` 这类**通用 ingestion task 应按
  `storage_mode` 过滤**, 否则会抢占 domain-specific 索引 (drive/meeting) 的职责。
- **类 20.220**: **自动化守门机制必须验"副作用是否真的发生", 不能信状态字段** ——
  2026-10-09 修 `MicroBubble-Auto-Recovery` 时, 一个任务挖出**三层叠加缺陷**, 每层都伪装成"正常":
  ① **触发器订阅 `Winlogon EventID=7002`, 而该事件新版 Windows 已不再产生** → 任务自 2026-08-04
  起从未触发, 但 CLAUDE.md 类 20.143 一直宣称"自愈已生效"; ② **Action 直接指向 `.ps1` 文件,
  没写解释器** —— 任务计划程序不把 `.ps1` 当可执行文件, 进程**从未启动**, 而它上报的
  `LastTaskResult = 0`(成功) —— 第 ① 层因此被完全掩盖; ③ **恢复脚本里 alembic 断言写死 head
  编号 `105_fix_drift`**, 实际 head 早已推进到 `142` → 前 7 步(含 7/7 端点全绿)全过, 却在最后
  一步误判 fail、上报 `success:false`。
  **⚠️ 2026-10-13 订正 —— 上面这三层的"修复"其实只落地了第 ③ 层**, ①② 原样未动,
  该任务**至今从未自动执行过一次**(触发器仍是 Winlogon 7002 订阅、Action 仍无
  `powershell.exe`)。逐层实测表 + 修复脚本见上方「遗留 (主拍待决)」条。
  ⇒ **这条铁律要再加一条纪律 ④**: 判"某自动化已修好"**必须逐层回读任务的实际定义**
  (`Get-ScheduledTask` 的 Trigger/Action), **不能因为 commit message 写了"修了三层"
  就采信** —— 本例正是"修上游缺陷会暴露下游缺陷"这条纪律的**反向失败**:
  当时连修三层的动作只做完了底层, 而文档按"已完成"记档, 于是**错误结论被继承至今**。
  **"手动触发跑通了"≠"调度器拉得起来"** —— 后者才是自动化守门的前提。
  **三条纪律**: ①**状态字段会说谎** —— `LastTaskResult=0` / 容器 healthy / 服务 200 都只证明
  "调度器认为成功", 不证明"代码跑过"; **验证必须查副作用产物**(日志文件是否生成 / 数据是否真变),
  本次正是靠"今天的日志文件没生成"才抓到第 ② 层; ②**修上游缺陷会暴露下游缺陷**, 一次连修三层
  才能到底, 只修一层就收工会把下一层当成"修好了"; ③**自动化断言禁止写死会变的编号**(见类 20.219
  与 `scripts/restart-recovery-after-gui-restart.sh` 的修法), 改校验不变量: 恰为 1 个 head +
  current == head。
  **附带教训**: `alembic current` 的 INFO 前缀行走 **stderr**、版本号走 **stdout**, 用
  `2>&1 | head -1` 会抓到 INFO 行而非版本号 —— 解析命令输出前必须确认流归属。
  **第 4 种"状态字段说谎"形态 (2026-10-12 实战): `exit code 0` 也会骗人** ——
  pytest 的 stdout 被管道截断 (`| head` / `tee` 中断) 时**仍返回 0**,于是
  "跑完了"不等于"跑过了"。某 agent 首报"exit code 0, 16 文件 130 passed",
  逐文件重跑后发现**其中 22 个其实是 failed**, 只是被管道吞掉了。
  ⇒ **纪律**: 报告测试结果**必须给逐文件/分组的 passed-failed 数字**,不能只报
  exit code; 且 `pytest ... | head` 这类截断管道**禁止用于判定成败**。
  ⚠️ **同源第 3 形态 (2026-10-12 image-scan 三轮实战): "Dockerfile 里写着装了" ≠
  "成品镜像里装了" —— 多阶段构建的副作用会整段丢失**。
  `docker/Dockerfile.commercial` 的 `pip install --upgrade setuptools` 写在 **builder** 段
  (装进 builder 的 `/usr/local`), 而 runtime 段是**全新的 `FROM python:3.11.17-slim`**
  且只 `COPY --from=builder /root/.local` ⇒ **升级后的 setuptools 根本没进最终镜像**,
  成品里留的是基础镜像自带的 **79.0.1**, 而 79.0.1 的 `_vendor/` 带着 2 条 CVE
  (`jaraco.context 5.3.0` / `wheel 0.45.1`; 84.0.0 vendor 的是已修复的 6.1.0/0.46.3)。
  构建成功、Dockerfile 写得对、**副作用却没发生在成品里**。
  ⇒ **纪律**: 判"某个包装上了没有 / 某次升级生效没有",唯一可靠依据是
  **最终镜像内实测**(如 `docker run <img> python -c "import setuptools; print(...)"`),
  **不能读 Dockerfile 就以为它装过** —— 多阶段构建里 builder 与 runtime 是两个文件系统。
  **配套 (同一轮踩到)**: 排查 CVE 时**先看 trivy 报的文件路径**再决定改哪里 ——
  报出的老版本若在 `pip/_vendor/` 或 `setuptools/_vendor/` 下, 那是**工具自带的副本**,
  改 `requirements.txt` **完全无效**(真装的包本来就是干净的); 只有报在 `site-packages/`
  下的才能靠 requirements.txt 修。image-scan 四轮里 3 类载体(pip vendor /
  setuptools vendor / 真装的包)各占一批, 不看路径就会在错误的文件里找原因。
  同源第 2 例: 容器镜像不含 `docs/`(实测 `/app/docs` No such file),而
  `tests/rag/test_pr10_docs_e2e.py:18` 用 `REPO_ROOT/"docs"/"rag"` 取**宿主**
  文档 —— 该测试**设计上只能在宿主跑**(其 docstring 自述"本机可直接跑")。
  故容器内跑它的 22 个 failed 是**环境缺口不是代码缺陷**, 别误判成回归。
  **容器内 pytest 的已知不可信项**: ①镜像不含 `docs/`; ②镜像早于 worktree
  (常缺 `fakeredis` 等新依赖 + 持有已删文件的陈旧副本) ⇒ **本地容器结果一律
  低于 CI 的可信度**, 冲突时以 CI 为准。
- **类 20.221**: **DB 存 UTC、主机存 +0800 —— 跨系统对时间必须显式换算** ——
  2026-10-09 查 `MULTIMODAL_INLINED` 链路时, 三个 agent 连续在同一个坑上栽: 把
  `meetings` / `knowledge_images` / `knowledge_chunks` 的 `created_at` / `updated_at`
  当本地时间读, 于是把**昨天 21:41 的全量重跑误判成今天**, 一度得出"今天的 OCR 全量
  引入了回归"的错误结论。实际: DB 列是 `timestamp without time zone`, 写入用
  `datetime.utcnow()`; 主机与 docker logs 是 **+0800**; 两边差 **8 小时**。
  **纪律**: ①凡跨 DB / 容器日志 / 主机文件 / `date` 比对时间, **先声明各自时区**再比,
  结论里写明用了哪个时区; ②判"某操作发生在什么时候"必须用**相对证据**(如 `min(children.created_at)`
  vs `min(parent.updated_at)`、chunk 的 `char_end` 与 content 长度对账), 不要只靠绝对时间戳;
  ③报给用户的时间一律换算成本地 +0800, 避免"凌晨 3 点重跑"这类误导。
  **同源提示**: `data/` 下的备份文件由宿主机脚本生成, 时间戳是 **+0800**, 与 DB 的 UTC 混排时
  极易误判 (本次 184MB SQL dump 的 mtime 是本地 14:42, 内容却是 06:42 的 UTC 数据)。
- **多模态 inline 回填链路 = 未启用特性 (2026-10-09 裁定)** ——
  `knowledge_extractions` 的 formula/table/chart 通过 `inline_extractions_to_content` 回填进
  `knowledge.content`, 靠哨兵 `<!-- MULTIMODAL_INLINED v2 -->` 做幂等。实测全库 **755 篇里
  只有 1 篇 (id=2809) 含 `[FIGURE:N]`** —— 因为 `file_parser_service` 只在正文出现**英文
  "Fig. N"** 时插占位符, **中文论文写"图 N", 该机制从未对中文文档生效过**。
  2026-10-09 追查 `MULTIMODAL_INLINED` 标记全库为 0 时确认: 标记是被 `_reset_multimodal_data`
  的 `split(MARKER)[0]` 剥掉的(字节级铁证: chunk 15866 的 `char_end=1714` 超出当前 content
  长度 1681, 正是剥离位置), **但 inline markdown 本身在哨兵之前、活下来了** (5 篇文档的
  `![图(...)]` 完好), **主文本 RAG 没少东西**(哨兵是 HTML 注释, 不进 tsvector)。
  真正的损失只有: ①幂等哨兵丢失 → 下次回填会与现存 inline 内容**叠加重复**(修前勿跑);
  ②1 个孤儿 chunk。**主指挥 2026-10-09 裁定: 按"未启用特性"处理, 不启用、不回填、不修中文
  占位符**。将来若论文改写英文 "Fig. N" 或确有回填需求, 必须先修幂等缺陷再动。
- **类 20.222**: **CI 硬门必须真的挡得住 —— 开保护前先修红、绿了再开** ——
  2026-10-12 实测 `gh api branches/main/protection` → **404**、`rulesets` → **`[]`**,
  即**从未有过任何 required check**。而 `server-tests-baseline.yml:15-18` 注释白纸黑字写
  "任一片失败即红, **阻塞合并**", `continue-on-error` 也确实摘了 —— **红叉亮着, 却从未
  挡过任何一次 push**。同轮审计还发现该 workflow **连续 9+ 次全红** (2026-09~10-10)。
  **三条纪律**:
  ①**"注释宣称阻塞"与"实际阻塞"是两件事** —— 类 20.220 的变体: 不止状态字段会骗人,
     **配置注释也会骗人**。判断门禁是否真实, 唯一可靠办法是
     `gh api repos/<owner>/<repo>/branches/main/protection` 回读, **不是读 yml**。
  ②**开保护前必须先把红修绿** —— 反序会让每次 push 都被挡, 寸步难行。
     本次顺序: 定位 4 类根因 → 一次推送转绿 → **连续 3/3 全绿** → 才开保护。
  ③**required checks 在 matrix 下必须逐个 job 列出** —— 本仓是 8 片 matrix
     (`shard 0`~`shard 7` + `Merge baseline summary` 共 **9 个 context**)。
     只填 workflow 名 `Server Tests Baseline (full tests/)` **一个都匹配不上, 等于没保护**。
     取精确名的方法: `gh api repos/<repo>/commits/<sha>/check-runs --jq '.check_runs[].name'`。
  **2026-10-12 已开启的配置** (`enforce_admins=false` ⇒ **管理员直推不受影响**,
  实测 empty commit 推送成功): required 9 个 context / `strict=true` /
  `allow_force_pushes=true` / **`allow_deletions=false`** (禁删 main)。
  ⚠️ `enforce_admins=false` 的含义是**管理员也能绕过** —— 这道门防误推与非管理员误操作,
  **防不住主动绕过**; 若哪天要求连管理员也必须等 CI, 改 `true`, 但日常推送会变成
  "推分支 → 等 13min CI → 合 main"。
  ⚠️ **`gh api -f` 全按字符串传**, `enforce_admins=false` 会报
  `"false" is not a boolean`; 且 **`required_pull_request_reviews` / `restrictions`
  即使要设 null 也必须显式传**, 否则 422 `weren't supplied`。
  正确姿势: `--input <json>` 一次性传完整 body。
- **类 20.223**: **判「某依赖无用」不能只看 `Required-by: 空` + 本仓零 import ——
  必须查它有没有「metadata 未声明的硬 import」(上游打包 bug)** ——
  2026-10-12 实战: 主指挥据 4 条证据判定 `datasets` 零用途并**已提交删除**
  (`7f8719035`), 被并行 agent 用 import blocker 当场证伪, 下一 commit 撤销
  (`3247085c5`)。**漏掉的那条证据** = `modelscope 1.40.0` 有一条**无try 包裹的
  顶层裸 import**:
      modelscope/pipelines/base.py:16   from modelscope.msdatasets import MsDataset
        → modelscope/msdatasets/ms_dataset.py:9
            from datasets import (Dataset, DatasetDict, Features, ...)
  实测: 屏蔽 `datasets` 后 `from modelscope.pipelines import pipeline` **直接
  ModuleNotFoundError**; 而 `modelscope` 的 metadata **根本不声明 datasets**
  (只声明 filelock/hub/packaging/requests/setuptools/tqdm/urllib3)
  ⇒ **requirements.txt 那一行是它唯一的供给来源**。
  **为什么两条直觉判据都不够**:
  ①`pip show X → Required-by: 空` 只扫 **base 依赖**, 看不到
     "metadata 不声明、代码却硬 import" 的上游 bug;
  ②`grep -rn "import X" app/ scripts/` 只看**自己的代码**, 依赖内部的
     顶层 import 完全不可见。
  **正确判据(删任何顶层依赖前必做)**:
  ①`pip show X` 看 Required-by; ②全仓 grep 自己的代码;
  ③**读 `pip show X` 的 `Requires` 并逐个核实其 import 链**, 重点查
     那些 **extras 声明**的包 —— extras 不装不代表没人 import;
  ④**用 import blocker 做运行时实测**(`sys.meta_path` 插一个 finder 屏蔽 X,
  再 import 各关键模块), 这是唯一能证伪"删了没事"的一步。
  **危害形态最恶劣的一点**: `voiceprint_service.py:42` 把 modelscope import
  包在 `except Exception` 里(设计意图"不让 WS 崩"), 于是**删掉不报任何错**,
  只是 `_load_pipeline` 恒失败 → **所有发言人退化成 unknown**。类 20.220
  的完整形态: 状态字段不撒谎、也没有报错、但**副作用没发生**。
  ⇒ 推论: **"删一个依赖"的爆炸半径永远大于"钉一个版本"**。裸声明会漂移,
  但漂移是可见的 CI 红; 而删错一个软 import 兜底包, 后果可能在生产跑很久
  之后才以"功能静默失效"的形式出现。**能钉就钉, 别删。**
- **类 20.224**: **查依赖冲突必须 `pip install --dry-run` 逐对实测, 不得引用文档 / 注释里
  写的"冲突链"; 测依赖解析时禁止 `--quiet`** ——
  2026-10-12 实战: 同一个 image-scan/mcp 阻塞问题**连续三轮归因, 错了两轮**,
  而**每一轮的错误结论都被写进文档, 于是成为下一轮判断的前提** ⇒ 错误会"继承"。
  三轮台账:

  | 轮次 | 谁写的 | 当时的结论 | 实测结果 |
  |---|---|---|---|
  | 第 1 轮 | 前人写进 `requirements.txt` 注释 | "mcp 要 `websockets>=15`, 撞 `websockets==12.0` 硬钉" | ❌ **证伪**: `mcp 1.28.1 + websockets 12.0` 与 `+15.0` **均**可解 |
  | 第 2 轮 | 同文件注释 | "mcp 那行改任何版本都是无效改动, 必须先完成 ASGI 栈升级立项" | ✅ **属实**, 该立项 2026-10-12 已完成 |
  | 第 3 轮 | **本轮自己** | 测 `langchain-community==1.0.0` 用了 `pip install --quiet`, `No matching distribution found` 被吞, 看起来像"可解" | ❌ **该版本根本不存在** (PyPI 最高 0.4.2) |

  **唯一真实阻塞点是 uvicorn**: `mcp>=1.13.0` 把 uvicorn 下限从 `>=0.23.1` 抬到
  `>=0.31.1`, 不存在"既修 CVE 又不动 uvicorn"的版本。而 websockets **早在 2026-10-11
  就已放宽成 `>=12.0,<16.0`**(容器实测装 **15.0.1**) ⇒ **第 1 轮的前提在写下时就已是假的**,
  只是没人回去核。这就是"错误被继承"的完整机制: 冲突链会随**别的**改动作废,
  而文档里的结论**不会自动更新**, 于是它持续以权威口吻误导下一个读它的人。
  **四条纪律**:
  ①**冲突结论必须自己实测**: `pip install --dry-run "A==x" "B==y"` 逐对跑, 不引用
     注释 / 文档 / issue 里写的冲突链 —— 那些是**某一刻的快照**, 不是不变量。
     已在 `requirements.txt:5-16` 把第 1 轮的误判就地订正并附 dry-run 证据。
  ②**测依赖解析禁止 `--quiet`**: 它会把 `No matching distribution found` /
     `ResolutionImpossible` 吞掉, **制造"可解"的假象**(第 3 轮就是被它骗的)。
     同样禁用的还有 `--log` 截断; 要判成败必须拿到**完整的解析输出**。
  ③**冲突链写成文档时必须写"有效期/复查条件"**: `.trivyignore` 每条都带
     「上游发布 X 后删掉本行」, langsmith 那条更进一步写死了
     「一旦动了 websockets / uvicorn / fastapi 版本, 必须回来删掉这行」——
     **2026-10-12 这三个条件全部触发, 该行当天被删除**。这是本项目少见的
     **"文档主动要求自我作废"的设计, 第一次被执行, 应当推广到所有会漂移的注释**。
  ④**推翻旧结论时必须留下"被什么证据推翻"的锚点**(dry-run 命令 + 输出), 不要静默改写 ——
     否则下一个人会以为那条结论从未存在过, 又重新推导一遍。
  ⚠️ **同源第 2 形态(今日踩到)**: `.trivyignore` 的**复查条件达成 ≠ 门禁会转绿** ——
  那条豁免删掉后门禁仍红, 因为真因是另一批"有修复版但未升级"的依赖。
  删豁免与修依赖是两件事, 别用前者冒充后者(类 20.220)。
- **类 20.225**: **判「某文件是否使用/依赖 X」必须匹配「用法」, 不能匹配「提及」——
  注释里谈论 X 会让 `grep -q X` 假阳性** ——
  2026-10-12 实战: 为给 image-scan 加 `push` 触发器, 需先确认"哪些镜像读
  `requirements.txt`"。用 `grep -q "requirements.txt" Dockerfile.mcp` 得"读",
  **实测是假阳性** —— 该文件第 18 行就写着
  `⚠️ **本文件不读 requirements.txt**`, grep 命中的是**那句注释本身**。
  若据此把 mcp 算进受影响范围, 加触发器的成本会多估近一倍 (7 个镜像 vs 实际 3 个)。
  **同型坑本仓已有**: `.dft` 前缀(见下方 DFT 段——那是 CSS 类名, grep `dft` 大量假阳性)。
  ⇒ **纪律**: ①判"用没用 X"要用**用法模式**, 例如
  `grep -nE "COPY requirements\.txt|pip install .*-r requirements\.txt"`(匹配真正的消费点),
  而不是 `grep -q "requirements\.txt"`(匹配任意提及);
  ②**凡是要据此算成本/影响面的 grep, 先把命中的那几行读出来看**, 别只看退出码;
  ③特别警惕"否定式注释"—— 写着"不读 X""不走 X""已删除 X"的行, 是假阳性的高发区;
  ④**CI workflow 的「显示名」≠「文件名」** —— `rag-framework-ci.yml` 在
  `gh run list` / required checks 里显示为 **"Alembic Single-Head Guard"**
  (它只有一个 job `alembic-single-head`)。2026-10-14 我据此一度以为"它没跑",
  实际跑了。判"某 workflow 跑没跑"用 `gh run list --workflow=<文件名>`,
  **别只认显示名**; 且 push 后十几秒就查可能漏掉尚未启动的, 要隔一会儿复查。
  ⑤**判「某改动会不会触发某 workflow」不要 grep 文件名, 要 YAML 解析** ——
  `grep -q CLAUDE.md .github/workflows/*.yml` 命中 6 个, **全是注释**
  ("这条纪律已写进 CLAUDE.md"), paths 列表里根本没有。正解（**可直接跑**；
  ⚠️ 顶层 `on:` 会被 YAML 解析成**布尔 `True`**，写 `d["on"]` 必 `KeyError`；
  ⚠️ **`paths` 为 None 有两种含义，必须分开**——"无过滤"与"压根没有 push 触发"）：
  ```python
  import yaml
  d = yaml.safe_load(open(f, encoding='utf-8'))
  on = d.get(True, d.get('on')) or {}          # ← on 是 True 不是 "on"
  push = on.get('push')
  if push is None:
      verdict = '无 push 触发器, 永不触发'
  elif 'tags' in push or 'tags-ignore' in push:
      verdict = f'只按 tags/refs 触发 ({list(push)})'
  elif push.get('paths'):                     # ← 必须先判 paths:
      verdict = '有过滤: ' + ('⚠ 命中' if any('CLAUDE.md' in str(p) for p in push['paths']) else '不命中')
  else:                                       #   省略 branches = 所有分支(含 main), 不是"不触发"
      verdict = f'⚠ push({push.get("branches", "未限定=所有分支")}) 且无 paths 过滤 = 必触发'
  ```
  ⚠️ **推之前先算成本**: 带 paths 过滤的不含该文件 ⇒ 不触发; **无 paths 过滤的**
  (`push: branches: [main]`) **一律触发** —— 实测推一个纯 CLAUDE.md 提交
  触发 2 个共 45 秒, 而若捎带 `.github/workflows/**` 则触发 8 个 30+ 分钟。
- **类 20.226**: **判「某个 X 能不能重建/能不能用」必须先跑「留一认回率 + 抢走率」
  双指标实测，不能凭「样本量够」「基线是 0 所以没损失」推断** ——
  2026-10-13 声纹重建实战，**同日连续三次差点写坏生产数据，全被双指标拦下**：

  | 我当时的推断 | 双指标实测 | 真实后果 |
  |---|---|---|
  | 「479 秒单场可以重建」 | top1 **81.2% → 75.0%**，质心吸走 3 段他人语音 | 过拟合到单场声学环境 |
  | 「清掉蒋芦笛的 anchor 只是改元数据」 | 她吸走的 55 段**只是被挪给别人**，而她本人 8 段里原本判对的 5 段全变错 | 净负收益 |
  | 「给 9 位无声纹者录声纹能补上漏洞」 | 逐人留一：**5 人全部认回 0 段**，却各抢走 4–9 段 | 净负收益 |

  **Why**：这三次的共同错误是**用「数量指标」代替「质量指标」** ——
  478 秒 > 0 所以能建、改元数据不动向量所以安全、段数 ≥2 所以能录。
  但**真正决定成败的是"认回率"和"抢走率"，它们与数量无关**。

  **四条纪律**：
  ① **重建任何「模型/向量/索引」前，先跑留一验证**（用**未参与构建**的样本），
     同时报 `认回率` 与 `抢走率`。**只报认回率是不够的** —— 认回 0 段但抢走 9 段
     是典型的"看着无损失、实则破坏"。
  ② **留出集必须与建库样本不相交，且跨环境**。同一场景内的留出集会给出虚高结论
     （本次第一次失败就是单场样本）；"跨场"不是可选项，是**发现过拟合的唯一手段**。
  ③ **误抢要看绝对数不是比例**。分母随负样本增加而膨胀，会把"恒定 8 段"
     显示成"从 8.7% 涨到 16.7%"，曾让我误判"新方案更差"。
  ④ **「基线是 0 所以没损失」是伪安全**。零基线意味着**无从判断改好还是改坏** ——
     写坏了测不出来，只能靠留一验证提前判。

  **同源判据（本次一并确立）**：判某个成员的样本**能不能用**，
  前置条件是**该成员发言的时长分布**，而不是段数 —— 实测**单次连续发言
  100 秒以上（主讲人）的标签准确率 100%**，而**最长仅 5–19 秒（插话型）的只有 0–33%**。
  短语音成员之间 embedding 本身不可分，**补样本改变不了信号不足**，
  那是算法层问题（按时长/质量降权），不是数据量问题。

  **⚠️ 同日追加的四条（全部踩过，其中三条是"自造的数"造成的）**：

  ⑤ **阈值不能凭空设** —— 我用「距王天志 < 0.35」筛"哪些会议有他"，
     而 0.35 是从**他熟悉环境里的留出距离 0.10–0.19**类推的。实测别的会议里
     他的真值块是 **0.39–0.43**，**整场被我判成"他没来"**，是主指挥复核才发现。
     ⇒ **余弦距离的分布随声学环境变化，固定阈值不成立**。要报距离给人判断，
     不要拿自造的界下结论。同类：本条铁律第 ③ 条的"绝对数"也是自造判据的补丁。

  ⑥ **验证粒度必须等于生产粒度** —— 我的 CV 跑 20–40 秒**合并块**，
     而会议流水线处理的是**原始段（会议 250 均长 2.3 秒，1766/1906 不到 5 秒）**。
     同一个人块级 77.5% / 段级 87.9%（改前）—— **两个粒度的数字不能互相搬用**。
     ⚠️ 且**分母不能含"取不到 embedding"的段**，否则虚高（本次虚高 3.7 个点）。

  ⑦ **测「移除某组件的影响」时，测试本身必须复现生产的过滤条件** ——
     我第一版写成 `voice_embedding IS NOT NULL OR name='X'`，
     导致**测与没测两种状态下 X 都必然在候选集** ⇒ 得出"零影响"的**假结论**。
     生产是两条不同链路（anchor 池判 `voice_confirmed_at`、通用池判 `voice_sample_count > 0`）。

  ⑧ **「够不够」的判据是净增益显著为正，不是「段数够 + 两场」** ——
     同为 **7 段 / 2 场**，宋洋 **+7** 而刘莫菲 **+1**；差别在样本代表性。
     实测 **1 场重建会多抢 27 块**（单场过拟合），而 **+1 换 25 块新错名**
     比"认不出是谁"更误导 ⇒ **净增益 < 5 一律不写库**。

  **采样脚本的两个已踩坑（都属于"看起来在做、实际没做"）**：
  - 「已用区间」排除若用严格 `<` / `>`，会在**边界相邻**时误杀整块
    —— 曾把一个 **237 秒**的块因末尾差 **0.3 秒**判为已用而丢弃；
  - 「先设一个时长门槛」在**样本本身偏短**时会**静默返回空**，
    "没有数据"与"门槛设错"必须分开判——曾因设 15 秒门槛而把一个最长仅 14.5 秒的会议整场滤空。

  **⑨ 探针只能产候选，不能产结论；且判「某框架是否在用」的 grep 不能加行首锚点**
  —— 2026-10-14 写了个 AST 探针扫 406 个 `.py` 找「docstring 声称了某动作」的行，
  判据是"docstring 提到的符号有没有出现在本文件里"。结果 **13 条判"缺符号"，
  人工读代码后 12 条是假阳性**：docstring 里写的是**表名**（`写入 agent_traces 表`）、
  **跨模块符号**（原文就写"业务代码调用…"）、**别种语言的 API**
  （`speechSynthesis.speak()` 是 JS）—— 这些本就不该出现在该 `.py` 文件里。

  ⛔ **同一探针的 grep 分支漏掉全部延迟 import，错误结论被写进了 docstring**：
  查 `llama_index` 是否在用时用了 `^(from|import)` **锚定行首**，于是函数体内的
  延迟 import 一条没匹配到，据此判「llama-index 零使用」并**把这个结论写进
  `app/rag/__init__.py`**，靠复查才发现实际有 7 处（`dense_sparse_routing.py`
  的 VectorStoreIndex/BM25Retriever + `multimodal_parser.py` 的 PDFReader 等）。
  **本仓的可选依赖普遍用函数内延迟 import**（`framework_gate` 那套"失败自动回退
  手写实现"的设计）⇒ 判「某框架/某包是否在用」必须匹配 `from X` / `import X`
  **任意缩进**，**绝不能加 `^`**；且真要用框架做判断，先确认它装没装。

- **类 20.227**: **改 `.env` 里的 LLM 配置必须同时对齐「后端」与「模型名」两个维度，
  且必须实测 tools 支持；另: CI 的 `paths` 过滤会让 workflow 因"没跑"而显示绿** ——
  2026-10-14 小气助手对话失效，三层叠加，逐层修好才看得见下一层：

  > 🔴 **交接必读：第 1 层的修复不在 git 里**（`.env` 未入库、含密钥）⇒
  > **换机 / 重建 `.env` / 交接环境时必须手动同步那 7 行**，否则本故障原样复现。
  > ⚠️ **只改第 1 层不够** —— 改完模型名，第 2 层（tool 协议）会立刻浮出来，
  > 此时对话**仍然报错**。第 1 层是**环境问题**、第 2 层是**代码缺陷**
  > （已随 commit `33490d7ea` 入库），两者缺一不可。
  > ⚠️ 改完 `.env` 必须 `docker compose up -d --force-recreate`，
  > **`restart` 不刷新容器 env**（本次实际踩过）。
  > 完整交接单见 `desktop-conversion/docs/handoff/2026-10-14-env-llm-model-name-handoff.md`。

  | 层 | 报错 | 根因 | 性质 |
  |---|---|---|---|
  | 1 | `unknown model 'qwen3.8:27b'` | `LLM_BACKEND=openai_compat`(→MiniMax) 但 **7 个 `AGENT_*_MODEL` 是 Ollama 模型名** | **环境**（`.env`，未入库） |
  | 2 | `tool result's tool id(plan_00_...) not found` | **系统代查结果冒充模型 tool_call**（见 ②） | **代码**（commit `33490d7ea`） |
  | 3 | CI `value too long for VARCHAR(32)` | alembic revision id 起成 **33 字符** | **代码**（commit `1fb9c0ab1`） |

  **① 后端与模型名是两个独立维度，改一个极易漏另一个**。判"该往哪边修"的唯一办法是
  **同一模型名分别打两个后端实测**（本次: `MiniMax-Text-01`@MiniMax=200 /
  `qwen3.8:27b`@MiniMax=`unknown model` / `qwen3.8:27b`@Ollama=200 ⇒ 后端是好的、
  是模型名错）。**且必须同时验 tools 支持** —— 否则重演 2026-09-09 那次
  "不支持 tools → `tool_calls=0` → 全靠编"（**类 20.220: 不报错、但副作用没发生**）。
  ⚠️ **`.env` 未入库（含密钥）⇒ 这类修复只在本机**，换机/重建/交接需**手动同步**。

  **② 系统代查的工具结果不得冒充模型的 tool_call**。`agentic_loop.py` 两处
  （Phase 0 计划 / tool-nudge 补查）曾把结果当 Anthropic `tool_result` 块注入，
  但 `tool_use_id` 是**本地合成**的（`plan_{idx}_{name}` / `nudge_{j}`），
  **从没经过模型**；而前面只有一条**纯 text 的 assistant 轮** ⇒ OpenAI 协议下
  `role="tool"` 成**孤儿** ⇒ 严格后端（MiniMax）**400**。
  ⚠️ **Ollama 兼容层宽松所以长期隐形**，一换严格后端立刻炸 —— 且代码注释里
  **早就预见过**这个风险（当时只是"退化成纯 text"，没修协议）。
  ⇒ **判据: `tool_use_id` 是否来自模型**。来自模型的（`tu["id"]`）协议正确、勿动；
  系统代查的应作**纯文本上下文**注入，不谎报工具来源。

  **③ 🔴 CI 会因为「没跑」而显示绿** —— `server-tests-baseline.yml` 与
  `qa-bench-smoke.yml` **都有 `paths` 过滤**，而 **`qa-bench-smoke` 的清单里没有
  `alembic/**`**。改迁移的那次 push **两个都不触发**，CI 面板"绿"但**根本没验证**
  （类 20.220 的形态: 绿不是因为修好了, 是因为没跑）。
  **补救 = 手动 dispatch**：
  ```bash
  gh workflow run ".github/workflows/qa-bench-smoke.yml" --ref main
  gh workflow run ".github/workflows/server-tests-baseline.yml" --ref main
  ```
  ⚠️ **`qa-bench-smoke` 是唯一会 `alembic stamp head` 的 job** ⇒ 只有它能抓到
  revision 名过长这类问题；它不触发则缺陷静默进 main。
  **同名纪律**: revision id **必须 ≤32 字符**（`alembic_version.version_num` 在
  **CI 是 VARCHAR(32)、生产是 VARCHAR(64)** ⇒ **本地/生产全绿、只有 CI 红**，
  判据只能是跑 CI）。命名约定早见于 017/030/031 三个迁移的 docstring（055 也为此刻意重命名）。
  ✅ **2026-10-14 已修**：`alembic/**` 加进 `qa-bench-smoke` 的 push.paths
  （本条 ③ 的漏洞自此关闭）；顺带把 push 段漏掉的 `app/services/reminder_*.py`
  与 pull_request 段对齐。

- **类 20.228**: **凡「按绝对 offset 往文本里插入」，必须检查会不会把既有结构化
  标记从中间切开；且脚本 docstring 声称的动作必须逐条对照代码核实** ——
  2026-10-14 处理 `ER-26-18027.pdf`（83 页 Word 稿件）时连踩两个坑：

  **① 按 offset 插入会劈开结构化标记**（改动前既有缺陷，非本次引入）。
  `[FIGURE:N]` 占位符按**绝对 offset** 插入，若该 offset 落在某个 `[PAGE:N]`
  标记**内部**，插入就把标记切开：

      [PAG  +  \n[FIGURE:99]\n  +  E:81]
        ↑ 正则 \[PAGE:(\d+)\] 匹配不到 ⇒ **按 [PAGE:N] 切块的分块器认为该页不存在**，
          该页内容被并进前一页

  **触发条件不是巧合**：第 81 页是**整页图片**（9 张图 + 1227 字符的化学式碎片，
  全页找不到任何 `Fig. N` 引用）⇒ 9 个占位符**全部落到同一 offset**（页尾），
  而该 offset 恰是下一页标记起点 +4。
  ⇒ **任何「整页无图注文」的页（图片页 / 图表页 / 参考文献页）都会命中**，
  不是孤例。**修法**：插入前把落在标记内部的 offset **吸附到标记之后**。
  **纪律**：①凡代码里有 `text[:pos] + X + text[pos:]` 这类**绝对 offset 插入**，
  必须问「pos 会不会落进某个结构化标记里」；②**按位置倒序插入**可保证已处理部分
  不受影响，这是这类修改的安全前提；③测试要**遍历 offset 相对量**（实测用 -6~+11）
  验证「标记数与插入物数量**始终守恒**」，只测单一案例会漏。

  **② docstring 说的和代码做的不一致**。`scripts/backfill_kb_chunks.py` 开头写
  「切分 + 落库 + **chunk embedding 批量回填**」，但函数体里**根本没有 embedding
  回填**——只切 chunk 就结束了。若照 docstring 理解，跑完会以为检索已就绪，
  实际 `chunk_embedding` 全 NULL（类 20.220 又一形态：**注释在描述一个不存在的动作**）。
  ⇒ **纪律：动一个脚本前，先把它的每个"声称的动作"对到具体代码行**；
  本次正是因此才发现真正要跑 embedding 回填得用
  `scripts/backfill_late_embedding.py --knowledge-id N [--apply]`。

  **③ 连带暴露：版面碎片是检索噪声**。标记修好后 page 策略生效，chunk 从 79 →
  **338**，但实测 **164 个（48.5%）是 <50 字符碎片**（`O3` / `914` / `1213` /
  `335` —— Word 把化学式排成一行一个符号）。**纯数字串会匹配任何含数字的查询**，
  把无关 chunk 顶上来。已在 `ChunkConfig` 加 `min_chars`（**默认 0 = 不改既有
  行为**，只在重切时启用）。

- **类 20.229**: **写「验证纪律」时，只写「别信 X」是不够的 —— 必须同时写明
  「那该信 Y」，且 Y 要是一条可直接执行的命令** ——
  2026-10-14 一次会话里**连续三次**把「长得像证据的文本」当成证据，
  而其中**两次违反的是本仓早已存在的铁律**（类 20.225 / 20.226）。
  规则明明写着还是栽 ⇒ 说明"禁令"本身不产生正确行为，**缺的是可执行的替代动作**。

  | 我误信的 X（长得像证据） | 当时该信的 Y（可直接执行） |
  |---|---|
  | AST 探针判「符号不在本文件 ⇒ 声称的动作不存在」（13 条里 12 条假阳性） | **探针只产候选；结论必须人工读代码**。见类 20.226 ⑨ |
  | `grep ^(from\|import)` 判「llama_index 零使用」（漏掉全部 7 处延迟 import） | `grep -nE "from llama_index\|import llama_index" app/ --include=*.py`（**不加 `^`**）。见类 20.226 ⑨ |
  | `grep -q CLAUDE.md .github/workflows/` 判「会触发 6 个 CI」（命中全是注释） | `yaml.safe_load(...)` 解出 `push.paths`（⚠️ `on` 是布尔 `True`）。见类 20.225 ⑤ |
  | 日志里 `tot = {"tests": 0, ...}`（带 ANSI 色码的 **heredoc 脚本源码回显**） | `gh run download <run> -n <artifact>` 后读 `<testsuite tests= failures= errors= skipped=>`。见类 20.220 |
  | workflow 没出现在列表里 = 没跑（`rag-framework-ci.yml` 显示名是 "Alembic Single-Head Guard"） | `gh run list --workflow=<文件名>`。见类 20.225 ④ |

  **三条通用纪律**：
  ①**任何"未命中"类判据（grep 无结果 / 符号查不到 / glob 空）先假设探针错了**，
     再假设事实如此 —— 尤其当"未命中"会推出一个**看起来很合理的坏结论**时
     （本次 llama_index 那次差点把错误结论写进 docstring）；
  ②**"看起来像证据"的文本有三类同形陷阱**：**注释里的提及**（类 20.225）、
     **脚本里的字面量**（heredoc 回显）、**名字与实体不一致**（显示名 ≠ 文件名）。
     判据：这条文本是**被程序消费**的，还是**被人读的**？
  ③**误判已发生时要先查自己的产物**（docstring / 注释 / 报告），错误结论一旦写进
     文件就会像本条 20.220 那样被静默继承 —— 清理死代码时反而制造了新的死代码。

  ⚠️ **本条是元规则**：它不改任何具体操作，只要求**今后新增任何一条验证类铁律时，
  必须连同"替代判据"一起写**。已有条目的替代判据陆续回填中（本次补了
  类 20.225 ④⑤ 与 类 20.226 ⑨）。

- **类 20.230**: **改 `.github/workflows/**` 之前，必须先 `grep` 测试目录里谁在断言它
  —— 本仓有测试直接读 workflow 文件内容做字面量断言** ——
  2026-10-15 实战：把 9 个 workflow 的 15 处 `runs-on: ubuntu-latest` 钉成
  `ubuntu-24.04`，**漏改** `tests/playwright_ci/test_workflow_valid.py` 里两条
  `assert job["runs-on"] == "ubuntu-latest"` ⇒ `Server Tests Baseline` **shard 0
  红 2 条**，其余 7 片全绿。代价是**白跑一轮 8 个 workflow / 30+ 分钟算力**。

  **改前必做的 grep**（改任何 workflow 的字面量之前）:
  ```bash
  grep -rn "<你正在改的那个字面量>" tests/ --include=*.py
  ```
  已知会读 workflow 的测试文件（2026-10-15 实测 **6 个**，改动前请重数）：
  `tests/ci/test_deployment.py` / `tests/gitleaks/test_scan_clean_repo.py` /
  `tests/playwright_ci/test_workflow_valid.py` / `tests/rag/test_pr5_e2e.py` /
  `tests/test_workflow_yaml_syntax.py` / `tests/trivy/test_workflow_exists.py`。

  **修法：断言「性质」而不是「某个具体值」** —— 本次没写成
  `== "ubuntu-24.04"`（那样下次升 runner 又要改一次测试），而是:
  ```python
  assert job["runs-on"].startswith("ubuntu-"), "runner 必须是 ubuntu"
  assert job["runs-on"] != "ubuntu-latest", "必须钉死版本, 不能用浮动 latest"
  ```
  ⇒ 升到 `ubuntu-26.04` 时测试不用动，而**一旦有人改回浮动 `latest` 会立刻红** ——
  把当初的意图固化进测试，**减少下一次同类漏改的机会**。

  ⚠️ **验证这类改动不要用容器内 pytest** —— 镜像里的 `.github/` 是**构建时的旧副本**
  （镜像早于本次改动），会给出与仓库不符的结果。判据取**宿主**或 **CI**。
  （类 20.220 已记"容器内 pytest 的已知不可信项②"。）

  **同族**: 类 20.225 ④⑤（判 workflow 触发/身份别用 grep）—— 本条是它的**反向**：
  **改 workflow 时要主动 grep，因为有人在断言它**。

- **类 20.231**: **在 Claude Desktop 里起的进程，`%LOCALAPPDATA%\<X>` 会被 MSIX 包重定向
  到 `Packages\Claude_*\LocalCache\Local\<X>`** —— 你以为改的是真实路径，其实改的是包视图 ——
  2026-10-22 Docker 事故排查整整绕一小时的主因。
  **Why**：Claude Desktop 是 MSIX 包，包内进程访问 `C:\Users\<u>\AppData\Local\<X>`
  时被重定向到该包的 LocalCache。实测后果：① 2026-06-17 那个"把 Docker 挪到 E 盘"的
  junction 是在**包上下文**里建的 ⇒ 它落在包 LocalCache 里，**真实路径下根本没有这个
  junction**；② 我多次用 PowerShell "删掉" `%LOCALAPPDATA%\Docker\run` 下的残留，
  **全都作用在包视图上**，真实路径毫发无损 ⇒ "我明明删过了"却一直复现；③ Docker Desktop
  若从包上下文启动，就会去包视图找数据根。
  **⇒ 纪律**：①凡要动 `%LOCALAPPDATA%`（或任何用户目录）下的东西，**必须用非包上下文的进程**
  —— 本仓现成做法 `scripts/ci/run-one-shot-task.ps1`（通过计划任务跑，拿到干净上下文）；
  ②**判别方法**：`Get-Item 'C:\Users\pc\AppData\Local\Docker' -Force` 的 `.Target`
  在包上下文里会显示成 `...\Packages\Claude_*\LocalCache\Local\Docker\...`；
  ③**凡写脚本要操作用户目录，也要考虑它可能被包上下文调用**（本仓的 `docker-guard.ps1`
  因此用 `User Shell Folders\Local AppData` 从注册表读**真实** LocalAppData）。
  ⚠️ **同一现象的两个方向**：包重定向是**写**的重定向（路径被换掉），
  而 `Get-Item` 的 `.Target` 显示的是**解析后**的目标 —— 两者叠加时
  `.Target` 会显示成一个**根本不存在**的路径（本次实测显示成 `C:\DockerData\appdata\run`，
  而 `C:\DockerData` 压根不存在）。**⇒ `.Target` 不可全信，必须用 `Test-Path` + 实际读取交叉验证。**

- **类 20.232**: **Windows 上"看不见"有三种不同的成因，别混为一谈** ——
  2026-10-22 Docker `AF_UNIX EADDRINUSE` 排查，三层各浪费一轮。
  **① AF_UNIX socket 是 NTFS reparse point**：非正常退出后残留 0 字节文件，
  `Remove-Item` / `del` / `rmdir` / `[System.IO.File]::Delete` / `fsutil reparsepoint delete`
  **全部失败（error 1920）**，且**对 `Get-ChildItem` 与 `ls -la` 都不可见**，
  却仍占着 AF_UNIX 地址 ⇒ 下次 bind 必报 `Only one usage of each socket address`。
  上游解法（docker/desktop-feedback#460 / #531）是**改名而不是删除**。
  **② `\\?\` 前缀路径不穿越 reparse point**：实测
  `[System.IO.File]::Exists('\\?\E:\DockerData\_junctest\...')` = **False**，
  而同一路径去掉 `\\?\` 则为 True ⇒ **WSL 注册表 `BasePath` 用 `\\?\` ⇒ 靠 junction 兜底是无效的**，
  必须直接改注册表值。
  **③ WSL 的 9P 驱动看不到跨卷 junction**：`wsl -d Ubuntu -- ls /mnt/c/Users/pc/AppData/Local/Docker`
  报 `No such file or directory`，**不代表该路径不存在**，只代表它的目标（E:）出了 9P 的挂载范围。
  **⇒ 纪律**：①**"枚举不到"≠"不存在"**，判存在性用 `Test-Path` + 实际打开文件交叉验证；
  ②**"删不掉"≠"该留着"**，先确认它是不是 reparse point；
  ③**WSL 视角只能证明 WSL 侧的事实**，Windows 侧的事实必须用 Windows API 取。

- **类 20.233**: **自愈/守护脚本的"并发"要先查调度器的实际语义，不能只看
  `MultipleInstances`** ——
  2026-10-22 Docker 事故：守护脚本 55 秒内触发 3 次 L2、2.4 分钟内触发 2 次 L3。
  **根因之一**：`scripts/run-hidden.vbs:48` 用 `shell.Run cmd, 0, False`（`bWaitOnReturn=False`）
  启动 powershell ⇒ **wscript 立刻退出** ⇒ 任务计划程序认为"动作已完成"⇒ 5 分钟后又起一个，
  **而上一个 PowerShell 还在跑** ⇒ `MultipleInstances=IgnoreNew` **看不见 detached 子进程**。
  **⇒ 纪律**：①**判"会不会并发"要追到动作的实际启动器**（`.vbs` / `cmd /c start` / `Start-Process`
  都会 detach），不是只看任务的 `MultipleInstances`；②**闸门状态不能放在"读-改-写"的文件里** ——
  `Set-Content` 先截断再写，读者会读到半个文件 ⇒ 判定函数返回"从没跑过"⇒ 闸门被绕过
  （本次实测 2.4 分钟内放行了两次）；③**原子写必须用 `MoveFileEx(MOVEFILE_REPLACE_EXISTING)`
  或 `File.Replace`** —— 实测并发读压测：`Move-Item -Force` **143 次**破读、
  `Set-Content` 直接抛 IOException，两者都是 **0 次**；
  ④**"抢锁"要用 `FileMode.CreateNew`**（真正的原子创建）而不是"检查再创建"；
  ⑤**进程级互斥锁（`Global\` 命名 Mutex）作为最后一道防线** —— 脚本层加锁比调度器层可靠，
  且能同时防住"人手动跑 + 计划任务跑"。

- **类 20.234**: **写「原子替换」这类代码时，兜底分支必须同样安全 —— 原子操作失败后
  回退到一个不安全实现，等于把保证悄悄降级掉** ——
  2026-10-22 Docker 事故复验时抓到：`Write-AtomicFile` 的原子替换（`MoveFileEx` /
  `File.Replace`）在读者持有目标文件时会被拒（sharing violation），而函数里有**两处
  `Set-Content` 兜底** —— 正好是它存在的目的所反对的"先截断再写"。
  **⇒ 目标文件被截断 ⇒ 并发读者拿到半个/空文件 ⇒ `Get-State` 返回 `$null`
  ⇒ L3 闸门把它读成「从没跑过」⇒ 闸门被打开** —— **正是 2026-10-22 事故的机制，
  只是这次发生在自己身上**（讽刺的是那个 `Set-Content` 兜底当初正是为了修这个才写的）。
  实测：失败那轮 reader 10,932 次读取里 **272 次（2.5%）**看到坏文件；
  去掉兜底后 12,000+ 次读取 **0 次**。
  **⇒ 纪律**：①**原子操作失败时，宁可保留旧内容也不截断写** —— 旧状态文件无害，
  坏掉的才有害（而且"保留旧内容"恰好让闸门读成"关闭"）；
  ②**关键状态要有第二个存放点**，写失败时用另一个兜底（本次：`state.json` 也存
  `last_l3`，`Get-L3GateState` 取两者更新的一个）；
  ③**降级路径只在高并发时才走到，低负载下永远测不出来** ⇒ 必须专门写并发读压测
  （本次：reader 用 `FileShare.ReadWrite|Delete` 持续读 2.5 s，writer 写 300 次，
  断言 reader 一次都没看到坏文件）—— **这类断言会偶发红，不要当 flaky 忽略掉**，
  抓出来往往就是真 bug（本次就是）。

- **类 20.235**: **改了用户级环境变量，对「已经在运行的进程」无效 —— 子进程继承父进程的
  env，不是重新读注册表** ——
  2026-10-22 实测推翻了一个看起来显然的方案。
  **原方案**：改用户级 `TEMP`/`TMP` 指向 E 盘 → 重启那个 LabCairn 会话 → 它就该写 E 盘了。
  **实测不成立**，链条：
  ① Claude Desktop 主进程早于改动启动 ⇒ 它的 env 陈旧；
  ② **子进程继承父进程 env** ⇒ 我自己会话派生的**新** bash 进程拿到的仍是旧的 `%TEMP%`
  （实测：注册表里已是 `E:\...\data\tmp`，进程里还是 `C:\...\Temp`）；
  ③ **重启会话也不够** —— 新会话进程仍是主进程的子进程；给
  `E:\LabCairn\.claude\settings.json` 加 `env: {TEMP, TMP}` 并重启该会话后，
  **它仍写 C 盘**（实测其 task 输出目录 `C:\...\Temp\claude\E--LabCairn--...`
  仍有 17:09 的新写入）。
  **⇒ 纪律**：①**改用户级 env 只对「改动之后新起的进程」生效** ⇒ 想让老进程切换，
  必须重启**它们的祖先进程**（这里是 Claude Desktop 本体）；
  ②**不要用「重启会话」当「刷新环境」的手段** —— 先确认会话进程是不是祖先进程派生的；
  ③**要同时覆盖新旧进程，唯一稳的办法是让两条路径指向同一物理目录**（目录 junction），
  而不是指望环境变量会"渗透"下去；
  ④**判定依据要用「派生链上的祖先进程」而不是「用了什么工具」**。

- **类 20.236**: **部署脚本会在执行中「改写自己」—— bash 按旧字节偏移继续读 ⇒ 部署执行的是
  「半新半旧」的内容** ——
  2026-10-25 实测：`scripts/deploy-auto.sh` 在云端执行，它自己会跑 `git reset --hard origin/main`，
  而**这个文件本身就在版本库里** ⇒ 被改写；**bash 是边执行边按字节偏移读脚本的** ⇒ 文件一改，
  后续行的偏移全错 ⇒ 实测「改了 deploy-auto.sh 并 push 后，同一次部署的日志仍打旧文案」
  （磁盘上已是新版、git HEAD 也是新提交，日志却是旧代码的输出）。
  ⇒ **改部署脚本后「同一次部署没生效」不是没 push 成功，是这个机制**。
  **修法**（已落地 `scripts/deploy-auto.sh`）：记录**执行前**的自身 sha256（`$0`），
  git 操作后若自身已被改写 ⇒ `exec bash "$0"` **重新执行磁盘上的新版本**；
  `PREV_HEAD` / `PY_CHANGED` 这类**依赖 reflog、只在第 1 次执行时算对**的量用环境变量带过去；
  `DEPLOY_SELF_SHA_BEFORE` 作递归守卫（第 2 次执行时 sha 相同 ⇒ 不再 exec）。
  ⚠️ 副作用：改了部署脚本的那一次部署会**跑两遍前半段**（git pull / 磁盘检查幂等，无害）。
  ⚠️ **修复机制本身也要「下一次部署」才装得上**：首次给 deploy-auto.sh 加这个自检的那次部署，
  磁盘上的脚本**还没有** sha_before 计算 ⇒ 检测不到 ⇒ 那次仍是「拼接执行」。
  ⇒ **验证这条链路必须再改一次 deploy-auto.sh 后 push**（第二次起才有 before/after 可比）。
  实测 2026-10-25 23:36 的验证日志（完整闭环）:
  `开始部署 → fetch+reset 成功 → 检测到本脚本已被 git 改写 ⇒ 重新 exec 新版本 → 开始部署(第2次)
   → fetch+reset 成功 → 部署完成`（第 2 次 sha 相同 ⇒ 不再 exec ⇒ 无递归）。
  **两条通用纪律**：①**凡「脚本会 git reset/pull 整个工作区」的脚本，都不能假设自己执行到一半
  文件还是原样**；②**验证部署脚本的改动是否生效，要看那一次部署的日志文案，不要看 git HEAD** ——
  git HEAD 对 ≠ 部署脚本跑的是新代码。

- **类 20.237**: **「模型不常驻、按需启动」是一类决策，不是一个开关 —— 判定、实现、验证三件事都要做全** ——
  2026-10-26 主指挥决策「本项目所有模型不常驻, 按需启动, 不用时释放显存」(反转 v31.3 起
  SenseVoice 常驻的老设定)。落地时踩到/确认了六条纪律：
  ① **「常驻」不只在一个地方**：本仓同时存在 ①容器服务 lifespan 启动即加载
     (`app/sensevoice_server.py` 的 `lifespan`) ②**应用启动预载**
     (`app/main.py` 的 `_warmup_embedding_background`) ③**惰性但永不卸载**的库
     (`embedding_service` / `reranker_service`) ④**外部服务的 keep_alive**
     (ollama 的 `OLLAMA_KEEP_ALIVE`) ⑤**调度器拉起的常驻进程**
     (计划任务 `MicroBubble-GPU-ASR-Daemon`) ⑥**子进程式守护器**(自身不占显存, 子进程退出才归零)。
     ⇒ **只改一处 = 没改**。逐个组件列出来再逐个改。
  ② **「加载」与「预热」要分开**：`import torch/transformers` 进 `sys.modules` 不占显存、但能让首屏不冻结，
     必须**保留**；真正加载权重占显存的才要改成按需。
  ③ **按需加载必须加锁 + 双检**，否则并发首请求会各加载一份 ⇒ 显存翻倍。
  ④ **空闲卸载必须判断「正在使用」**：每次使用刷新活跃时间戳 + 活跃计数，
     否则会把**正在推理的模型**卸掉（长会议 chunked 推理可超过 600s）。
  ⑤ **调用方必须透明**：`/health` 只能反映「服务活着」(HTTP 200)，**不能**用 `model_loaded` 当可用性判据
     —— 否则按需加载会让调用方直接判定服务不可用。客户端超时必须大于首次加载耗时。
  ⑥ **验证要看副作用, 不能看配置**：`/health` 的 `model_loaded` 由 false→true→false 才算验证通过；
     且**「进程在」不等于「模型在」** —— `ollama ps` 为空就是没加载, `nvidia-smi` 的 WDDM 模式
     **不按进程给显存**(容器进程完全列不出来), 归因只能靠「停服前后差值」或组件自报。
     ⚠️ **本机 18G 显存里相当一部分是桌面应用**(Edge/webview2/ToDesk/GameViewer)与 WSL2/Docker 的
     CUDA context, **不是本项目模型** —— 别把整卡占用都算到模型头上。
- **类 20.238**: **「push 成功 + CI 全绿 + 服务 200」三者全对，仍不能证明生产已更新** ——
  2026-10-25 实测踩中：云端磁盘被 18 GB 刷屏日志占满 ⇒ `deploy-auto.sh` 的磁盘检查
  **自 2026-10-15 起每次 push 都中止**（6+ 次静默失败），而磁盘满又让 webhook 连日志都写不进去
  ⇒ **push 事件彻底丢失**。于是 push 返回 0、GitHub CI 全绿、生产 `/health` 200 —— **三个信号全对，
  生产跑的却是旧版本**（本次新 dist 的资源指纹在生产 404，生产首页仍引用旧 chunk）。
  **三条纪律**：
  ① **判「部署成功」只能用指纹比对**：生产首页引用的资源指纹 == 本地 `web/dist/index.html`
     的指纹；**不能**用 push 返回值、CI 结论、`/health` 状态码任一组合代替。
  ② **部署日志在云端** `/var/log/webhook-deploy.log`（成功末行 =「部署成功 ✓」，
     失败 =「ERROR: 磁盘空间不足，部署中止」）⇒ **查部署只看本机日志是查不出来的**；
     而且 GitHub 侧投递记录也要看（`gh api .../hooks/{id}/deliveries`）——
     实测有过**投递 502 且请求根本没到云端 nginx**（云端 access.log 无记录）⇒ **两边都要看**。
  ③ **磁盘检查失败是「正确的防御」，缺的是告警**：脚本拦住了在磁盘满时写坏文件，
     问题在于**没人看它的日志** ⇒ 部署链路需要「投递失败 / 部署中止」的可见信号，
     否则一次磁盘满就能让部署静默失效十天。

- **类 20.239**: **「证书现在还有效」≠「续期链路是通的」—— 证书类判据必须是 dry-run，
  且续期失败必须有人看见** ——
  2026-10-29 `https://agent.mnb-lab.cn/drive` 报 `NET::ERR_CERT_DATE_INVALID`，
  根因**三层**，逐层修好才看得见下一层：

  | 层 | 事实 | 证据 |
  |---|---|---|
  | ① | certbot 那条 lineage 用 `authenticator = standalone`（需独占 80 端口），而 nginx 常驻占 80 ⇒ **每次 renew 都失败** | 日志 `Could not bind TCP port 80 because it is already in use`，自 2026-09-28 连续失败到 2026-10-28 12:03 过期 |
  | ② | 2026-09-02 **已经签出一张 SAN 覆盖 agent 的有效证书**（到 12-01），但 nginx 仍指向那条废弃 lineage ⇒ **有效证书白放着** | `certbot certificates` 显示 mnb-lab.cn 那条的 Domains 含 `agent.mnb-lab.cn`，而 nginx 443 block 指 `/etc/nginx/ssl/agent.mnb-lab.cn/` |
  | ③ | mnb-lab.cn 那条 lineage **其实也续不了** —— dry-run 才暴露 | `reader size limit exceeded` ⇒ LE 读到的是 SPA 的 index.html 而非挑战文件 |

  **五条纪律**：
  ① **判「证书链路健康」只能用 `certbot renew --cert-name <name> --dry-run`** ——
     它走 ACME staging，**不消耗生产限额**。`certbot certificates` 显示 `VALID` 只证明
     **当前这张**没过期，**不证明下次续期能成功**（本次两条 lineage 都是"当前有效、续不了"）。
  ② **certbot 续期的域名集来自 renewal conf 的 `[[webroot_map]]` 键** ——
     扩了 SAN 却没有把新域名写进 webroot_map ⇒ **下次续期会悄悄把它丢掉**
     （本次 agent 就是这么差点在 11-01 续期时从 SAN 里消失）。
     判据 = dry-run 输出里那行
     `Simulating renewal of an existing certificate for agent.mnb-lab.cn and 2 more domains`。
  ③ **nginx 的 server 级 `return` 在 rewrite 阶段执行、早于 location 匹配** ——
     凡有 ACME 挑战路径的 `:80` server block，**必须把跳转降级进 `location /`**，
     挑战路径单开 `location /.well-known/acme-challenge/ { root /var/www/certbot; }`。
     否则挑战请求也被 301 到 https 落到 SPA fallback（agent 的 :80 block 一直是对的，
     mnb-lab.cn 的裸 `return 301` 是错的 —— **两个域名的 :80 block 写法不一致，
     抄错就出事**）。
  ④ **改云端 nginx ≠ 修好** —— `nginx/conf.d/tunnel.conf` 是云端配置源，
     `scripts/deploy-auto.sh:273` 每次部署**无条件** `cp` 过去 ⇒ 只改云端会被下次部署冲回。
     判据 = **仓库里也改了且已推送**（类 20.214 ⑤ 的同一条纪律，此处再次确认）。
  ⑤ **续期成功后 nginx 不会自动换证书** ⇒ 必须挂 `renew_hook`（`nginx -t && nginx -s reload`）。
     没有 hook 时 certbot 报成功、线上仍是旧证书 —— 状态字段与实际生效分离（类 20.220）。
  ⑥ **自动化续期失败要有可见告警**：本次失败只写在 `/var/log/letsencrypt/letsencrypt.log` 里，
     `certbot.timer` 每天跑 4 次、**连续失败 30 天没有任何信号**（与类 20.238 的
     「部署中止没人看」同族）。

- **类 20.240**: **守护脚本判「活着」必须验端到端数据通路，不能只看进程在；
  Docker 宿主端口转发器会卡死，且症状伪装成"服务挂了"** ——
  2026-10-29 全站头像 502，**根因在 Docker 而不在被守护的隧道**：

  | 判据层 | 实测 | 说明 |
  |---|---|---|
  | 容器内 `curl 127.0.0.1:9000/minio/health/live` | **200** | MinIO 本身完全正常 |
  | app 容器走容器网络 `http://minio:9000/...` | **200，文件 846KB** | 应用链路完全正常 |
  | 宿主 `curl 127.0.0.1:9000/minio/health/live` | **Empty reply（curl exit 52）** | ← **真凶在这一层** |
  | 宿主 `curl 127.0.0.1:19000/...`（同容器另一个发布口） | 同样 Empty reply | ⇒ 是**转发器**坏了，不是单个端口 |
  | 云端 nginx | `upstream prematurely closed connection while reading response header` | TCP 能连上、HTTP 没有响应 |

  **五条纪律**：
  ① **守护脚本的判活口径必须是「端到端数据通路」**，不是「进程/参数还在」——
     本次隧道守卫全程日志 `alive (pid=…) - no action`（它只看 ssh 命令行里有 `-R`），
     而数据通路已经死了 **6.5 小时**。类 20.220 的完整形态：**状态字段说谎**。
     ⇒ 判据至少两级：**Local**（宿主 → 容器发布端口）+ **E2E**
     （云端 nginx → SSH 反向隧道 → 宿主 → 容器）。
  ② **"连得上但没有响应"要往「中间层」查，不要往「服务」查** —— 容器内 200 / 宿主
     Empty reply ⇒ 坏的是 Docker 的宿主端口转发（`com.docker.backend`），
     **不是 MinIO、也不是隧道、更不是 nginx**。修法：**`docker restart <容器>`
     即可重建转发**（数据在 volume 里，重启不丢；本次实测秒修）。
     区分「转发器坏」与「容器坏」的判据 = **同容器的另一个发布端口是否也不通**。
  ③ **探针必须带 `--noproxy '*'`** —— 本机用户级 `HTTP_PROXY=127.0.0.1:7897`（Clash）
     会劫持对外探针，而 `NO_PROXY` 只含 `localhost,127.0.0.1`
     ⇒ 不加这个参数，探针变成"代理通不通"而不是"隧道通不通"。
     （同理：测容器 IP 时会走代理并得到假的 502，别被它带偏。）
  ④ **自愈要防重启风暴** —— 容器启动不足 N 秒（本次取 120s）时探针失败**不重启**
     （它可能只是还在启动中）；否则守卫会在启动期反复重启。
  ⑤ **只探 minio 不够** —— 同一个转发器也承载主站 API（`127.0.0.1:8000`），
     它的失效面更大（全站不可用）。⇒ 两条通路都要探，且**端到端那条不通时只记日志、
     不自动重启隧道**（2026-09-15 教训：两个监管者判活口径不一致会互相不认账）。
     实装见 `scripts/tunnel/guard-ssh-tunnel.ps1`（`Test-Http200` / `Test-DataPath`）。

- **类 20.241**: **判「某人本场有没有发言」必须用「跨场人工台账」重建的真值质心，
  不能拿锚池质心当参照 —— 锚池自己可能就是污染的** ——
  2026-10-30 会议 259 声纹核对实战：库里标「蒋芦笛」的 **83 段整场汇报全部是刘子煜**，
  而蒋芦笛本人那场**一句话没说**。四条纪律：
  ① **锚池质心可能是污染的** —— 拿它当参照 = 把污染当真理。
     蒋芦笛的 anchor 早已被自己吸走的他人声音污染（2026-10-13 台账：吸走 33/55 段），
     于是「离蒋芦笛近 ⇒ 是蒋芦笛」这条推理**在数据上是循环的**。
     ⇒ 唯一可靠参照 = **人工台账里跨场确认块**重建的质心
     （本次用会议 255 的 16 个亲耳确认块重建 ⇒ 离主讲 0.594，离全场最近的一段 0.449）。
  ② **判「某人本场没发言」用全局最小距离** —— 若全场离该人真值**最近**的一段都还在异人量级
     （本次 0.449，异人是 0.59），即该人本场未发言。**不要只看中位数**。
  ③ **无阈值对照优于自造阈值** —— 逐段比「离 A 的真值更近还是离 B 的真值更近」，
     本次 **83/83 零例外**；比"d_阈值 ≤ 0.45"这类自造界可靠（后者会把已确认的赵航佳
     段误判成主讲人）。
  ④ **污染的代价是「整场被吞」** —— 本次一次污染就让**一整场 24 分钟的汇报**署名到别人名下，
     并连带把纪要摘要/要点全写错（"由蒋芦笛汇报"）。⇒ 发现任一人的 anchor 有吸收他人语音的记录，
     就要预期**该人在别的会议里也会整段消失**。
  ⑤ **负样本也要入台账** —— 「环境声 / 人群杂音」这类段要显式记为负样本
     （本次 9 条 + 12 条），否则重建声纹时会把噪声当语音样本
     （与类 20.225 的「配错对会假阳性」同源）。

- **类 20.242**: **缓存键必须包含完整对象标识，不能只用 basename —— basename 碰撞会让
  后一份静默复用前一份的数据，且「取错了」不会报错** ——
  2026-10-30 会议 259 声纹重建实战踩中（**当天先污染、后自查发现**）：
  取会议音频的脚本用 `os.path.basename(key)` 做本地缓存文件名，而 MinIO 里的键是
  `recordings/255/merged.m4a` / `recordings/256/merged.m4a` / `recordings/259/merged.m4a`
  ⇒ **basename 全是 `merged.m4a`** ⇒ 255 与 256 **静默复用了 259 的音频**，
  切出来的片段与嵌入全是错的。
  **唯一暴露它的信号 = 打印出来的音频长度**：三场都打成 `3424.4s`（= 259 的长度）；
  若当时没打印长度，这个错会一路流进「蒋芦笛的质心」，看起来完全合理。
  ⇒ **三条纪律**：
  ① **缓存键用完整对象键**（把 `/` 换成 `__`），不要用 basename，
     也**不要用固定名**（本仓 `scripts/voiceprint/reeval_speaker_distances.py` 原来
     固定叫 `audio.m4a` ⇒ 换 `AUDIO_KEY` 再跑就复用上一场的音频，**同一型**，
     2026-10-30 一并修掉）。
  ② **凡从对象存储取数据到本地缓存，必须带一项「取对了没有」的自检**：
     本例是**音频时长 ≥ 转录覆盖到的最大 end**（差 5% 即报错退出、不产出结果）——
     类 20.220 的「自动化守门必须验副作用是否真的发生」，
     **且退出要 fail-loud**（宁可这次跑不成，也不要产出错的）。
  ③ **凡「多份同名不同内容」的资源都按这条看**：`recordings/{id}/merged.m4a`、
     `web/dist/` 的 chunk、`*.sql.gz` 备份、`index.html`/`main.js` —— 
     **同名不等于同一份数据**（与类 20.225 的「文件名相同不等于同一场」同源，
     只是那一处是**同名不同物**、这一处是**同 key 撞缓存**）。
  ⚠️ **附带修掉一处用户可见的错误**：因这个 bug，桌面「待听片段」里标着
     `255_蒋芦笛_台账_01/02` 的两两段**其实是 259 的音频** ⇒ 已在 2026-10-30 重新导出
     （新增回读校验：产出 wav 的实际时长必须与请求区间一致，否则不产出文件），
     并把那份 `待听清单.md` 的描述一并更正 —— **给用户的说明文件出错，
     等于给了用户一个假证据**（类 20.225 的「注释里谈论 X 会让 grep 假阳性」的升级版：
     这里连**音频内容本身**都是错的）。

- **类 20.243**: **声纹的「距离基线」必须先实测出来，再谈阈值；
  短插话型说话人之间 embedding 互相不可分 —— 「认回率高」不等于「能建声纹」** ——
  2026-10-30 会议 259/250 声纹重建收口（8 场 9336 段全量嵌入 + 逐场留一验证）实测：

  | 基线/事实 | 实测值 | 出处 |
  |---|---|---|
  | **本项目「跨场同人」距离基线** | **≈ 0.50**（蒋芦笛 255质心↔250台账段 = **0.5038**；250质心↔255台账段 = 0.5536） | ⇒ **不是 0.20**（类 20.226 ⑤ 记的"留出距离 0.10–0.19"是**同环境**留出，不是跨场） |
  | 刘子煜质心 ↔ 王书馨质心 | **0.4039**（合并后 0.275） | ⇒ **比跨场同人基线还近 ⇒ 这两人在 3D-Speaker 下分不开** |
  | 刘子煜质心 ↔ 胡小琪/吴怡霏/刘莫菲质心 | 0.256 / 0.293 / 0.296 | ⇒ 一堆学生之间全在 0.25–0.35 |
  | **短插话型学生的段长** | 刘子煜台账 39 段中位 **7.1s**；被抢的 221 段中位 **2.9s** | ⇒ 抢走集中在短段（与类 20.226 ⑥「短段 embedding 不稳」同源） |
  | 段长分档后 | 抢走段中位 2.9s；刘子煜自己的段 6–12s 档 **13/13 认回**、12s+ 档 **9/9 认回** | ⇒ **长段可分、短段不可分** |

  ⇒ **五条纪律**：
  ① **判「距离 d 算近」之前，必须先量出本项目的基线** ——
     跨场同人 ≈ 0.50，所以「离某质心 0.40」**不能**当"是某人"的证据
     （实测 250 里离刘子煜 0.33–0.47 的那批段，同一批里王书馨的段离刘子煜也有 0.40–0.60）。
     ⇒ **标签传播（用某人的质心去反查别人）在本项目不可靠**。
  ② **「认回率高」≠「能建声纹」** —— 刘子煜的台账质心在**自己那两场**里认回 **92%**，
     但放到全库就抢走 **221 段**（净增益 **−182**）⇒ 判据必须是
     **净增益 = 认回 − 抢走（绝对数）**，且**抢走必须跨全部会议统计**（类 20.226 ③）。
  ③ **「抢走」要区分「真抢走」与「本来就没人认领」**（类 20.226 ⑧ 的延伸）：
     被抢的 221 段里，绝大部分**离自己真值质心只有 0.09–0.25**（确实是那个人），
     而**当前库里它们被挂在一个同样错的 anchor 名下**（如王天志/蒋芦笛）
     ⇒ 这类"抢走"只是**把一个错名换成另一个错名**，不构成"破坏"；
     但**离真值也远**的那些（王天志×16 中位 0.586）才是**真破坏**。
     ⇒ 报抢走时**必须同时报「离被抢者真值的距离中位」**。
  ④ **重建现有 anchor 之前，必须先测「冒名数」** ——
     类 20.226 ⑧ 只要求"净增益"，但**纯重建可能让冒名反而变多**：
     订正后台账下实测 **蒋芦笛 105 → 129 段、杜同贺 8 → 97 段、陈金薪 1 → 123 段、宋洋 1 → 39 段**，
     而王天志 428 → 404（唯一变好）。⇒ **重建只对「本人认回不降 且 冒名不升」的人才值得做**；
     本轮**谁的纯重建都不合格 ⇒ 现有 9 个 anchor 一个都不动**。
  ⑤ **改生产判据（加 margin）是「全局代价」，不能只看它对新人的收益** ——
     实测加"top1 必须比 top2 近 ≥0.15"能让刘子煜的抢走从 221 降到 45，
     但**现有 9 个 anchor 本来判对的段从 1367 掉到 1173（−194）**；
     margin 0.20 更降到 1061（−306）⇒ **全局准确率 84% → 65%**。
     ⇒ 这类改动**影响所有会议**，属主指挥拍板范围，**不得由 agent 自行决定**；
     且**任何 margin 阈值都必须同时报「新人净增益」与「现有 anchor 判对数」两栏**。
  ⑥ ⚠️ **判据必须复刻「生产路径」，不能复刻「看起来像的那条路」** ——
     2026-10-30 实测踩中：会议流水线的最终标签**不是** `identify_speaker_anchored` 给的，
     而是 `voiceprint_voting.vote_with_quality_gates` 的**聚类投票**
     （每段 vs **全体 enrolled** 池找最近邻，`match_threshold=0.7`，**不是 0.65**）。
     我第一版测的是 anchor 池 ⇒ **数字全部对不上生产**（重测后生产路径上 margin 0.10 的效果反而更好：
     错名率 30.0%→11.6%）。⇒ **改判据前必须先定位「最终标签到底由谁写」**
     （`post_meeting_tasks.py` 里 `seg["speaker"] = cluster_to_name[...]` 那一行往前追）。

  ### ✅ 落地（2026-10-30 主指挥拍板 margin=0.10）
  **判据**：`margin = 第一名必须比第二名强出 settings.VOICEPRINT_MIN_MARGIN (默认 0.10)`，
  否则**弃权**（宁可标「发言人?」也不猜错名字）。阈值设 `0` 即完全关闭，可随时灰度回退；
  `MATCH_THRESHOLD` (0.65) **不动**。
  **改了三处**（候选池各不相同 ⇒ margin 值在**每一池上各自实测**，未外推）：
  `app/services/voiceprint_voting.py::vote_with_quality_gates`（流水线主路径，enrolled 池）、
  `app/services/voiceprint_service.py::identify_speaker_anchored`（流水线逐段，anchor 池）、
  同文件 `identify_speaker` / `identify_speaker_by_embedding`（enrolled 池，`LIMIT 1→2` 取次近者）。
  **端到端实测**（直接调生产函数 `vote_with_quality_gates`，理想聚类=按台账真值分组，
  **44 组 / 2224 段**，2026-10-30 深夜复测；台账已含 262 的 8 个块）：
  | margin | 聚类级命名正确 | **命名错误** | 无名 | 段级命名率 | 段级**错名段** |
  |---|---|---|---|---|---|
  | 0.00（改前） | 9 | **2** | 33 | 58.9% | **4.4%** |
  | 0.03 | 8 | 1 | 35 | 52.7% | 2.3% |
  | **0.05**（现役） | 8 | **1** | 35 | 52.7% | **2.3%** |
  | 0.08 | 8 | 1 | 35 | 52.7% | 2.3% |
  | 0.10（原值） | 8 | 1 | 35 | 52.7% | 2.3% |
  | 0.15 | 7 | 0 | 37 | 49.6% | 0.0% |
  ⇒ **0.03–0.10 在理想聚类下结果完全一致** ⇒ 差异只在**真实流水线的 k-means 聚类**上显现（见下）。
  ⇒ **0.00 虽多 6 个百分点命名率，但错名段翻倍（2.3%→4.4%）⇒ 不要为了"有名字"而猜错**。
  ⇒ 0.15 起正确命名腰斩 ⇒ 过度。测试见 `tests/test_voiceprint_margin.py`（14 例，脱离 DB）。

  ⭐ **关键机制（2026-10-30 深夜查明）**：margin 的弃权是**段级不投票**，而最终标签按**簇**给
  ⇒ margin 过大 ⇒ 某些簇的 `votes_ratio` 跌破 0.30 / `min_votes` ⇒
  **整簇几百段一起变成「发言人?」** ⇒ 这才是"存量会议 30–63% 未识别"的来源，
  **不是逐段均匀弃权**。实测（段长仅 1.5–3 秒的短段会议，短段最近与次近天然拉近，类 20.245）：
  256 未识别 **63.3%(margin 0.10) → 9.7%(0.05) → 7.9%(0.00)**；250 1.8%→30.0%；243 15%→96%。
  ⇒ 且 **0.10 / 0.05 / 0.00 三档下台账真值分完全一样**（256 都是 719/722）
  ⇒ 在**已有人工台账+裁决表**的会议上 margin 的边际收益 = 0（真值已由裁决表保住），
  **代价全是弃权** ⇒ margin 的价值只在**没有台账的新会议**上。

  **✅ 现役取值 = 0.05**（2026-10-30 深夜主指挥拍板，自 0.10 下调；实现见
  `app/config.py` 的 `VOICEPRINT_MIN_MARGIN`）：
  ① 命名准确率与 0.10 **完全相同**（错名段 2.3%），而 0.00 的错名段翻倍 ⇒ 不要；
  ② 0.05 消掉了真实流水线下**整簇弃权**的副作用（256 未识别 63.3%→9.7%）；
  ③ 0.15 起正确命名腰斩 ⇒ 过度。
  ⇒ **两个质心互距 < 跨场同人基线(0.50) 时不能同时存在**（类 20.248 ⑥）——
  实测 陈天祥×吴孟铨 互距 0.311，单独造成会议 255 弃权 **+1590 段**。
  ⚠️ **存量会议的转写不会自动重算** —— 改动只影响**之后**新处理的会议；
  要让历史会议也变准需**逐个 reprocess**（那是另一件事，别默认要做）。
  ⚠️ **改 margin 后必须回归存量会议**：新阈值会让原先被弃权的簇重新拿到名字
  ⇒ 质量门的 `unknown_speaker_ratio` 与 `quality_status` 会随之变化。

- **类 20.244**: **人工真值要在重跑中存活, 必须有「裁决在最终赋值处优先」这条机制**；
  而**重标存量会议必须带两道安全闸 + 一层声学交叉验证** ——
  2026-10-30 按主指挥拍板「存量会议也按新判据重新署名」实战（8 场会议）：

  | 坑 | 现象 | 处置 |
  |---|---|---|
  | ① **裁决表只挡逐段识别, 不挡聚类投票** | 流水线里 v2 聚类投票(原始 embedding)决定最终标签且**优先于**逐段结果 ⇒ 裁决**从未生效**(会议 256 的 51 条全部挡不住) | 在**最终赋值处**再查一次裁决, 裁决赢(`post_meeting_tasks.py` 2.9) |
  | ② **人工标签压根不在裁决表里** | 裁决表只有会议 256 有 51 条; 250/254/255/259 的人工标签(两轮听辨)在**转录字段**里, 重跑必被覆盖 | 把**台账播种**进 `meeting_speaker_adjudications`(240 条, 覆盖 8 场); 与现有裁决冲突处按「裁决更细 ⇒ 优先」**裁剪**台账粗块 |
  | ③ **整段 clip 判断 ≠ 逐块人工判断** | 250 的 2667–2712s: 10-13 逐块记**胡小琪**, 2026-10-30 整段 clip 答**王书馨**; 声学逐段(seg785 0.149 vs 0.245)支持胡小琪 | **两个独立来源(逐块人工 + 声学)一致时, 以它们为准**, 整段 clip 的粗判断让位; 库内回滚 18 段 |
  | ④ **重标会把"刚修好的 bug"重新装回去** | 259 重标会给**蒋芦笛**安上 75 段 —— 而台账里她在 259 **一句都没说**(2026-10-30 确认) ⇒ 正是刚修好的「整场汇报被吞」复发 | **安全闸 B**: 不得让「台账里该场会议完全没出现过」的成员拿到 >10% 的段 ⇒ 259 被拦下, 保持人工修正版 |
  | ⑤ **重标后新增的名字要有声学交叉验证** | 255 重标新增 925 段「王天志」, 台账只确认了 93 段 ⇒ 靠台账验不了 | 比**距离分布**: 新增段到该人锚点中位 0.559(台账确认段 0.505, 同量级), 而它们改前各自的名字(杜同贺 0.638 / 宋洋 0.714 / 蒋芦笛 0.797)**都更远** ⇒ 判定成立 |

  ⇒ **三道安全闸(已实装进 `scripts/voiceprint/relabel_by_margin.py`)**:
  ① **台账真值判对数不得下降**(改后 < 改前 ⇒ 拒绝写库);
  ② **安全闸 B**: 不得让「台账里该场没出现过」的成员拿到 >10% 的段;
  ③ **声学交叉验证**: 新增姓名的段到该人锚点的距离分布须与台账确认段同量级,
     且**优于**它们改前的名字。
  ⇒ **实测结果**(8 场, 2269 段台账真值): 台账真值判对 **改前 ~92% → 改后 2266/2269 = 99.9%**;
  其中 229/243/247 从 **0% → 100%**(原先整场挂着一个无锚点的人, 现在如实标「发言人?」);
  250 从 98.3% → 100%; 256 从 85.3% → 99.6%。
  ⚠️ **重标必然把大量「台账外」的段从错名变成「发言人?」** —— 这是"宁可未识别, 不要猜错"的代价,
  **不是缺陷**; 台账覆盖率只有 2%–45%, 所以**台账外的改动无法用台账验证**, 只能靠安全闸 ③。
  ⚠️ **重标后纪要会与新标签不一致**(纪要里的「【某人】」来自旧标签) ⇒ 需**重生成纪要**
  (`scripts/voiceprint/regen_minutes.py`, 走生产 `analysis` 阶段 = 分块分析+汇总合并);
  ⚠️ 若新标签里几乎全是「发言人?」, 重生成的纪要会变成"发言人? 说了……" ⇒ 信息量下降,
  此时**宁可不重生成**(旧纪要虽然署名错, 但内容可读) —— 取舍要看实际生成结果, 别默认全重生成。
  ⚠️ **reprocess 的 `speaker_assignment` 阶段根本不重跑声纹识别**(`meeting_reprocessing_service.py:287`
  只重算 `speaker_stats`) ⇒ 要重标必须用 `scripts/voiceprint/relabel_by_margin.py`。


  ⛔ **附带订正两处旧结论**（保留原文以便追溯）：
  - 类 20.241 说的「蒋芦笛离主讲 0.594 = 异人量级」**措辞过头** ——
    0.594 只比跨场同人基线 0.5038 高一点，**不足以单凭距离下结论**；
    **结论仍然成立**，但依据是「主指挥亲耳确认的 block03」+「整场 87 段到该模板距离中位 0.310、
    最大 0.450、零段 ≥0.5」**这条同质性证据**，**不是**那个距离本身。
  - 类 20.226 ⑤ 里的「同一人跨录音的留出距离 0.10–0.19」**是同环境留出**，
    **不能**当跨场基线用（跨场是 ~0.50）。
  ⚠️ **本条同时给类 20.226 补了"替代判据"**（类 20.229 的要求）：
  **基线怎么量** = 取同一个人的**两场**人工确认块，分别建质心量互距
  （本例：蒋芦笛 250 块 vs 255 块 ⇒ 0.5038）；**净增益怎么算** =
  在**全部有台账会议**上模拟生产判据，统计 `认回` 与 `抢走`（绝对数），
  **并报被抢者离其真值质心的距离中位**。


- **类 20.245**: **声学在短段上系统性不可靠 ⇒ 短段的说话人判定必须「内容优先」，
  且用少量短段建质心会「系统性吸引短段」** ——
  2026-10-30 会议 259 逐段判定实战（285 个台账未覆盖段）:

  | 现象 | 实测 |
  |---|---|
  | 逐段最近邻（用 259 人工确认段建每人质心）给出 9 段与现标签不同 | 其中 **6 段**是「王天志 → 赵航佳」 |
  | 但这 6 段的**内容**明确是导师王天志 | 例 seg240「**我**为什么之前讲那个文章很平淡」= 第一人称指自己；seg337/340 延续 seg335（刘子煜提问）后的导师点评 |
  | ⇒ 声学结论被内容推翻 ⇒ **净改动 0 段** | |

  **根因**：赵航佳的质心只由 **8 个确认段**构成，且这些段**大多很短**（2–6 秒）
  ⇒ 短段在 3D-Speaker 空间里天然更靠近"短段质心" ⇒ **短段会被系统性地误判成该人**。
  这与类 20.226「短促插话型成员之间 embedding 不可分」是同一现象的另一面：
  **不只是"谁和谁分不开"，而是"短段会往短段的质心聚"**。

  ⇒ **三条纪律**：
  ① **同一件事上，声学与内容冲突时，内容优先** —— 人称/语气/接续关系
     （"我为什么之前讲…""一种是这像子玉说的"⇒ 引用他人 ⇒ 是导师）
     是比余弦距离**更强的**证据。
  ② **建质心时必须核对各人的确认段时长分布**；若某人的质心主要由短段构成，
     它会**主动吸引短段** ⇒ 用它判短段等于自证。
  ③ **「逐段声学判定与现标签不同的段数」本身就是质量指标**：本例只有 9/285 段不同
     ⇒ 说明现有标签在这场会议上**基本正确**，不必大改（避免为了"有事可做"而过度纠正）。
  ⚠️ 与类 20.229 的关系：这条给「声学 vs 内容冲突」补上了**替代判据**——
  **看上下文接续与人称指代**，而不是"距离最近的是谁"。
  ⚠️ 反过来也成立：**内容也读不出来时不要硬猜**（本例 seg178/188/236/344 我标「待定」，
  交主指挥听辨，而不是从距离里硬挑一个）。
  ⚠️ **给主指挥听的片段带余量时，「前面是X、后面是Y」指的是【余量里的上下文】，
  不是【段内】** —— 本例我给的每个 clip 含 ±1.5s 余量，主指挥说的"前面是王天志、后面是赵航佳"
  意思是**上一段是王天志、本段之后是赵航佳**，⇒ 本段归赵航佳（不是"段内前半段/后半段"）。
  **我自己因此判错了 4 段**（读成"段内混了两个人"⇒ 按内容判"维持王天志"），
  而主指挥与声学都指向赵航佳。
  ⇒ **纪律**：给主指挥的听辨片段**要么不带余量、要么在说明里写清余量含义**；
  收到"前面/后面"的回答时，**先按「余量=上一段/下一段」解释**，再按「段内切分」解释，
  并用声学/内容交叉验证取其一 —— **别默认自己那个解释对**。
  ⇒ 更稳的做法（本例应当如此）：**余量片段与"无余量纯段"分开导出**，
  前者问"上下文是谁"，后者问"这一段是谁"。

- **类 20.246**: **转录的「空档」要单独审计 —— 空档不是质量指标，是"某个人整段发言被漏抓"的藏身处** ——
  2026-10-30 会议 259 实战：主指挥说"三位主要发言人是陈天祥/刘子煜/肖佐林"，
  但**逐段声学扫遍 285 个台账未覆盖段都找不到陈天祥**，肖佐林也只有 18 秒 ⇒ 看似"两人没发言"。

  真因在 `meetings.quality_status` 里：质量评估报 `transcript_long_gap` **最长 215.19s**、
  `transcript_gap_count_gt5s = 12` ⇒ **录音 3424s 里共 460.9 秒（7 分 41 秒）有音频但没有转录**。
  把空档切出来重新分析才找到：
  - **空档 #4（1939.8–2118.5s）**：其中 **1969.8–2039.8s 的 7 个 10 秒窗最近者一致是肖佐林**
    （d=0.26–0.33，显著优于次近 0.41–0.51），且 ASR 文本里正是「这次**我汇报**…讲…文章」
    ⇒ **肖佐林有一段 70 秒的汇报，被 ASR 整段漏掉了**（SenseVoice 在这段只出 1 段、
    文本近乎乱码 ⇒ 该段音质差/静音多，正是流水线漏抓的地方）。
  - 空档 #6（2458.3–2673.5s）全部落在王天志/刘子煜/赵航佳 ⇒ 讨论，无新人。
  - **陈天祥：两段空档里都没有"离所有人都远"的窗**（最高 0.453）⇒ 确认他不在这段录音里。

  ⇒ **四条纪律**：
  ① **查"某人有没有发言"之前，先查转录的覆盖率** ——
     `meetings.quality_status='fail'` 且 `issue_codes` 含 `transcript_long_gap` 时，
     **先导出空档音频再看结论**；"逐段扫不到"≠"他没说话"。
  ② **空档要按 10 秒切窗做声纹判定**（不受 ASR 质量影响）——
     ASR 在漏抓段本来就失效，那段不能靠文本判断，只能靠声纹。
  ③ **"离所有已知人的质心都远"才是"没有声纹参照的新人"的信号** ——
     本项目三人（陈天祥/肖佐林/刘子煜）**都没有声纹**，
     建不出参照质心 ⇒ 只能靠人耳；**声纹方法天然发现不了没声纹的人**，
     必须辅以「ASR 文本线索」（"我汇报…"）。
  ④ **`transcript_long_gap` 是真实的证据缺口，不只是质量分** ——
     补转录/补标签时应把空档单独处理，而不是整场重跑。

  ⑤ ⚠️ **2026-10-30 晚间订正：长空档有三种来源，"补进转录"只对其中一种成立** ——
     全库体检（29 场）实测 **3983.6 秒（66 分钟）有音频但没转录**，
     逐段转写听内容后定性，发现**只有一种**是"漏抓了发言"：

     | 会议 | 最长空档 | 实际内容 | 该怎么办 |
     |---|---|---|---|
     | 257 安徽蒙城项目交流 | **298.31s** | **宣传片《乡村振兴早站》在放**（"王教授毕业于中国农业大学…把科技论文写在中国大地上"） | **不是发言** ⇒ 该会议转录里本来就有「**视频旁白**」这个发言人标签 ⇒ 要么按 视频旁白 补、要么留空，**绝不能当会议发言** |
     | 250 石油采出水处理 | **184.65s** | **唱歌**（"这是一首轻典的旋律""你别让我醉，怎么能够忘记""回到最初的年纪"） | **不是发言** ⇒ 留空；歌里夹的说话另算 |
     | 259 臭氧杀菌 | 215.19s | **真的漏抓了发言**（王天志主持讨论 + 刘子煜/赵航佳回答） | **要补**，且说话人必须人工确认 |

     ⇒ **三条纪律**：
     ① **「`quality_status=fail` 且 issue_codes 含 `transcript_long_gap`」只说明"这段没转录"，
        不说明"这段漏了发言"** ⇒ 补之前**必须先听音频定性**
        （用 SenseVoice 逐 6–8 秒窗转写，看文本是"汇报"还是"旁白/歌词"）。
        ⇒ **判"是不是漏抓"靠文本内容，不靠声学距离** ——
        唱歌与宣传片旁白的声学距离全在 **0.45–0.79**（离谁都远），
        **不构成任何证据**（类 20.241 ④ 的"离所有质心都远"只对"没有声纹的人"成立，
        对"不是人声的内容"同样成立 ⇒ **两种解释必须靠文本分开**）。
     ② **长空档的三种来源**：①**真的漏抓的会议发言**（要补，且要人工认人）
        ②**视频 / 宣传片在放**（该会议若已有「视频旁白」标签就按它标，否则留空）
        ③**唱歌 / 活动环节**（留空）。
     ③ **留空也是正确处理** —— 把视频旁白或歌词当会议发言塞进转录，
        比留一个洞**更有害**（会污染 `speaker_stats`、纪要、RAG 索引与 `meeting_chunks`）。
        ⇒ **先定性、再决定补不补**，不要一见长空档就开补。
- **类 20.247**: **判「说话人标签是识别结果还是兜底结果」要先看发言人有没有声纹 —— 没有声纹的人只会被塞进别人的质心；而「离所有已知质心都远」正是「这个人没建过声纹」的信号（与类 20.246 的判据方向相反）** ——
  2026-10-30 会议 262（10-26 组会）实战：主指挥给的 4 位主要发言人里 **3 位 `voice_sample_count=0` 且无向量**
  （陈天祥 / 王书馨 / 韩重阳；连刘子煜也是 0）。而生产标签写出来是
  「王天志 1616 段 / 张宏魁 201 / 蒋芦笛 157 / 发言人? 206」—— **那不是识别结果，是「最大类兜底」**。
  实测 599 个 10 秒窗：504 窗最近者是王天志（中位 d=0.328）、201 窗是张宏魁/蒋芦笛、
  **89 窗（890 秒）离全部 12 个已知质心都 > 0.55** ⇒ 那 890 秒是「没有任何人认领」的区段。
  ⇒ **四条纪律**：
  ① **先查「发言人有没有声纹」，再谈标签准不准**。`voice_sample_count=0` / `voice_embedding IS NULL`
     的人**永远不可能被识别出来** —— 他们的发言只会进入兜底。
     查法：`SELECT id,name,voice_sample_count,(voice_embedding IS NOT NULL) FROM members;`
  ② **「离所有已知质心都远」= 这个人没建过声纹**；⚠️ 与类 20.246 的判据**方向相反** ——
     那条是「离**主讲**质心远 ⇒ 某人本场没发言」，这条是「离**所有**质心都远 ⇒ 是个没建过声纹的人」。
     **两条不要混用。**
  ③ **质心会互相吸**：被污染的质心（蒋芦笛，类 20.241）会把**汇报者整段吞掉**
     （262 的汇报 #2，d=0.56–0.67 全判蒋芦笛）；最活跃的质心（王天志 n=59）会把**全场兜底**
     （504/599 窗）⇒ **「最近者分布」出现极端集中（> 80%）时，先怀疑兜底而不是相信。**
  ④ **没有声纹的人只能靠「人耳认人 + 留一验证」建库**：先按主题切出「每次文献汇报」的区段，
     导出片段让主指挥认人，再建质心；**建质心前必须跑留一认回率 + 抢走率双指标**（类 20.226）——
     本项目跨场同人距离基线 ≈ 0.50，**短插话型学生之间 embedding 不可分**（类 20.243），
     所以「认回率高」≠「能建声纹」。

  **配套：LLM 不可用时纪要怎么补（2026-10-30 MiniMax 额度用尽）** ——
  MiniMax 返回 HTTP 429「已达到 Token Plan 用量上限」(code 2056) ⇒ 纪要生成 / RAG / 对话全死
  （容器内 DNS/TCP/TLS 到 `api.minimaxi.com` **全通**，所以报错形态是 `APIConnectionError`，别当网络故障查）。
  此时**不要重写整份纪要**，按《会议纪要标准格式》只**追加**新增内容对应的要点/决议
  （确定性改名 + 追加；259 实测补 3 要点 + 1 决议），前提是**新增条目只写转录原文能对上的内容**，不做推断性扩写。
  ⚠️ 补录转录时**必须过 `sanitize_text`**（`app/services/meeting_quality_service.py`）——
  SenseVoice 会吐 `<|EMO_UNKNOWN|>`，不洗会让 quality 判 `control_token_leak` fail。
  ⚠️ 补空档后要**复算 gap**：`max_gap_fail_sec = 180`，**补掉最大的那个才算真修好**；
  **3–10 秒的小空档若逐窗转写只有「嗯 / 哦 / 嗯嗯」且最近质心距离 0.34–0.73 ⇒ 是真实静音，不要填**
  （填了只是往转录里灌噪声，且对门禁无影响）。
- **类 20.248**: **「跨场认回率低」时，先查验证集本身对不对，再判质心好坏**；
  而**人工台账必须按「逐窗切分后的区间」记，不能整块记** ——
  2026-10-30 会议 262（10-26 组会）建声纹实战：四位汇报者里三位**本来没有声纹**
  （陈天祥/王书馨/韩重阳，`voice_sample_count=0`），台账素材**全是 1.5–1.8 秒短段**
  （类 20.245：短段 embedding 不稳 ⇒ 质心会系统性吸引短段）⇒ **262 的 400–800 秒连续汇报
  是唯一可用的建库源**。

  | 人 | 跨场认回 | 认回距离中位 | 真抢走 | 结论 |
  |---|---|---|---|---|
  | 吴孟铨 | **28/31 (90.3%)** | 0.457 | 2 | 写（替换旧的 n=8） |
  | 韩重阳 | 11/23 | 0.597 | 0 | 写 |
  | 陈天祥 | **5/48 (10.4%)** | 0.619 | 0 | 写（但见下） |
  | 王书馨 | 18/32 | **0.526** | **12（关小未 8）** | **不写**（抢走了质心质量好的关小未） |

  ⇒ **五条纪律**：
  ① **验证集可能是错的** —— 实测 **陈天祥在 256 的 48 段里，36 段最近质心是王天志、12 段是耿嘉栋，
     一段都不是他自己**；**王书馨在 250 的 32 段里 21 段最近蒋芦笛**。
     ⇒ 那批块来自 2026-10-13 的听辨（当时记录的准确率只有 0–25%）⇒ **不能用可疑验证集
     否定一个由长素材建出的质心**。**判据 = 先看验证段的「最近质心分布」**：
     若稳定指向**另一个人** ⇒ 是验证块可能标错了人；若最近者随机散开 ⇒ 验证段太短不可用；
     若自己占多数（吴孟铨 25/31）⇒ 验证集可信。
  ② **判据必须复刻生产粒度，但"粒度不够"时要用长段子集复核**：
     吴孟铨的 1.8 秒中位段认回 90%，陈天祥的 1.7 秒中位段只有 10% —— 差别**不是**短段噪声
     （同样长的吴孟铨段距离 0.464），而是**质心与验证素材真的不匹配**。
  ③ **台账要按「逐窗切分后的区间」记，不能整块记** —— 实测会议 262 的第三次汇报块(2215–3020s)
     里**有 40 窗/400 秒是导师的追问**，不是汇报人；整块记会把导师的话记成汇报人，
     也会污染质心。⇒ 先按 10 秒窗逐窗判声学，**把汇报人与插话分开**，再记台账与裁决表。
  ④ **「没有声纹的人」在逐窗复验里会被吸给"最近的可用质心"** —— 王书馨（无质心）的 500 秒报告
     逐窗全被判给**韩重阳**（d≈0.47–0.56），而韩重阳在自己报告里 d=0.06–0.32
     ⇒ **这是类 20.247「没有声纹的人只会被兜底」的实例** ⇒ 她那段**只能靠人工听辨 + 裁决表**成立。
  ⑤ **新增质心会改变全体 enrolled 池 ⇒ 存量会议必须回归**（新质心可能抢走别人的段）。
     且**写库两个坑**：`member_voice_history.old_embedding/new_embedding` 是**裸 `vector(192)`**
     （不是 `HalfVector`）⇒ raw SQL 必须传 pgvector 文本 `'[f1,f2,...]'`，直接传 list 会
     `DataError: expected str, got list`；同表 `source` 是 `varchar(20)` ⇒ 别超长。
  ⑥ **新增质心会让存量会议的弃权率上升 —— 且要按"谁造成的"分别归因** ——
     2026-10-30 实测（新建 3 个质心后跑 7 场回归）：
     | 新质心 | 对会议 255 弃权率的影响 | 判定 |
     |---|---|---|
     | **陈天祥**（与吴孟铨互距 **0.311**，比跨场同人基线 0.50 还近） | **+1590 段**（1200 → 2790） | **不写** ⇒ 两个互不可分的质心会互咬，把大批段逼进 margin 不足 |
     | 吴孟铨 + 韩重阳 | **0 段**（1200 vs 1200 完全相同） | 写 |
     ⇒ **判据 = 逐个质心做 A/B 回滚对照**，别一次全上；
     ⇒ **互距 < 跨场同人基线(0.50) 的两个质心不能同时存在**（与类 20.243 的「刘子煜↔王书馨 0.4039」同型）。
  ⑦ **margin 判据在存量短段会议上会造成 30–63% 弃权，而质量门把"设计上的弃权"当成失败** ——
     实测：margin 0.10 ⇒ 会议 250 未识别 1.8%→**30.0%**、254 0%→18.5%、243 15%→**96%**、
     **256 8.2%→63.3%（质量 pass→fail）**、255 9.2%→12.3%；而 262 只有 9.8%。
     ⇒ 根因：这些会议的段是 **1.5–3 秒短段**（类 20.245：短段 embedding 不稳 ⇒ 最近与次近天然拉近）
     ⇒ margin 弃权是**规则在正常工作**，不是缺陷。
     ⇒ 但 `unknown_speaker_fail = 0.60` 把这种弃权算成失败 ⇒ **阈值与判据语义不匹配**
     （选项：调宽阈值 / 把 margin 弃权与"真未识别"分开统计 / 调小 margin —— **属全局取舍，须主指挥拍板**）。
     ⇒ ⭐ **实测：margin 0.10 / 0.05 / 0.00 三档下，台账真值分完全一样**（256 都是 719/722）
     ⇒ 在**已有人工台账+裁决表**的会议上，margin 的边际收益 = 0（真值已由裁决表保住），
     **代价全是弃权** ⇒ margin 的价值只体现在**没有台账的新会议**上 ⇒ **这是重新定阈值的依据**。
  ⑧ **⚠️ `relabel_by_margin.py` 的「不可复现」结论已被推翻（2026-10-30 晚更正）** ——
     原文曾记「同一份转录、同一套脚本，库内已存状态 vs 重跑**差 787 段**，
     而连续两次重跑完全一致 ⇒ 输出不可复现」。
     **更正**：那个 787 段**不是随机性，是「候选池变了」** ——
     255 的库内重标发生在 `13:45:11`，而**吴孟铨/韩重阳两个新质心写入于 `13:45:45`**
     （**相差 34 秒**）⇒ 库内那次用**小池**、重跑用**大池** ⇒ 差值来自**池效应**
     （类 20.249 ⑦：池越大 ⇒ `second_dist` 越小 ⇒ margin 弃权越多 ⇒ 未识别越多）。
     ⇒ **纪律仍然成立，但方向要改**：
     ①**「两次跑不一致」先查输入漂移（候选池/质心/台账/裁决表），再谈确定性**
     —— 查 `member_voice_history.created_at` 与 `meetings.updated_at` 的**先后**即可定位；
     ②**写库后仍要立刻重跑一遍比对**（类 20.220「副作用要真的发生且可复验」），
     但**比对的前提是输入未变**；输入变过时，正确的处置是**重新过闸 + 重标**，不是查随机种子；
     ③**报任何「未识别数」都要带上当时的候选池成员名单**（类 20.249 ⑦）。
     ⇒ 另注：**安静段补录的段会扰动聚类**（实测把 255 的 30 段安静空档拿掉 ⇒ 弃权 1200→734）
     ⇒ 补录后**必须重跑聚类并比对**，不能只看台账真值分。

- **类 20.249**: **margin 的弃权是「簇级雪崩」而非「段级渐变」；闸门若只看台账，
  在低覆盖率会议上必给假信号 —— 必须补「候选池覆盖」与「最近 anchor 交叉验证」两道判据** ——
  2026-10-30 存量会议按 margin=0.05 重标实战（9 场 dry-run 全矩阵验证 + 8 场台账 2269 段真值）。

  | 现象 | 实测 | 机制 |
  |---|---|---|
  | **margin 越大未识别越多，但不是渐变而是雪崩** | 同一场会从「几乎全有名字」直接掉到「整簇几百段变『发言人?』」 | margin 弃权是**逐段** `continue`（`voiceprint_voting.py:380`），而门控是**逐簇**：`votes < min_votes(3)` 或 `votes/total < 0.30` ⇒ **簇里本已投出票的段被连坐**，一起变成「发言人?」 |
  | **margin=0.10 的一次重标把 5 场会议的命名覆盖打崩** | 250: 34→572 未识别 / 256: 263→2023 / 243: 91→588 / 247: 6→87 / 255: 308→413 | 而它宣称的收益（台账真值）**已被裁决表接管** ⇒ 净效果是**纯破坏** |
  | **闸 A（台账真值不降）对台账外的崩塌完全失明** | 台账覆盖率 256 = 22.6% / 229 = 8.5% / 243 = 4.1% ⇒ 台账外的段占 77%–96% | 「台账真值不降」与「命名覆盖没崩」是**两件事** |

  ⇒ **六条纪律**：

  ① **闸必须有一条「全局未识别率不得上升」（闸 D）** —— 它是唯一拦得住上表第二行的判据。
     2026-10-30 能打崩 5 场，就是因为**当时没有任何一条闸看全局未识别数**。
     **替代判据**：`未识别段数(改后) ≤ 未识别段数(改前)`。

  ② **「台账里没出现过」≠「没发言」** —— 台账覆盖率低到 4%–23% 时，
     闸 B（台账外成员不得占 >10% 的段）会**把真正发了言的人误报**。
     实测：229 的杜同贺拿 31 段(10.9%) 触发闸 B，但**逐段最近 anchor 有 24/31 指向杜同贺**
     ⇒ 他确实发言了 ⇒ 闸 B 是**假阳性**。
     **替代判据**：算这些段的**逐段最近 anchor 分布**，多数指向该成员 ⇒ 告警作废（闸 B2）。

  ③ **候选池必须覆盖「台账真值里所有有声纹的人」**（闸 B1，**纯逻辑、不依赖任何阈值**）——
     模型**只能**从候选池里挑名字；真值人物若被 `context` 过滤踢出池 ⇒ 重标必然把段
     **兜底**给池里最接近的别人（类 20.247 的「最大类兜底」）。
     实测 **243**：池 = {宋洋,张宏魁,赵航佳,陈金薪,韩重阳}，而台账真值 25 段**全是王天志**
     ⇒ 613 段全部兜底给宋洋（到宋洋 anchor 中位距离 **1.19**，远超跨场同人基线 0.50）。
     ⇒ 推论：**闸 B2 单独用会给出假阳性**（宋洋在 243 里也是「最近 anchor 多数」）
     —— **必须先过 B1**。

  ④ **闸 C 的对照组是「同场同一人的人耳确认段」**，判据是**相对量**：
     新增段到该成员 anchor 的中位距离 ÷ 同场确认段的中位距离 ≤ **1.15**；
     且新增段的中位距离 ≤ 「仍未识别段」的中位距离（**符号判据**：新命名的段比留空的段还远
     ⇒ 这次命名是倒退）。
     ⚠️ **1.15 不是凭空设的数**（类 20.226 ⑤）：6 场实测的比值分两组 ——
     接受组 {0.957, 0.976, 1.010}、拒绝组 {1.242, 1.281}，两组之间有**空档 [1.010, 1.242]**
     ⇒ 阈值取空档中部。

  ⑤ **判「重标能不能写库」必须跑成「矩阵」而不是「单场」** ——
     实装五道闸（A / B1 / B2 / C / D）后，用**全部 9 场会议** dry-run 一遍，
     判据 = **闸的判定矩阵 == 人的判定矩阵**；单场通过不构成证据。

  ⑥ **回滚不是「回到备份态」** —— 备份态里可能带着**已知错名**
     （250 的旧态有 陈金薪 197 / 杜同贺 390 / 关小未 148，其中关小未的质心其实是
     蒋芦笛的声音、已停用）⇒ 回滚会**引入**错名。
     **替代判据**：比较**三态** —— `备份态 / 库内当前 / 新判据重算态`，
     逐场对比「台账真值分 + 未识别数 + 错名明细」，三态一起看。

  ⭐ **本次落地的判定矩阵（9 场 dry-run，2026-10-30 实测）**：

  闸的执行顺序 = **A → B1 → B2 → C → D**（**首个触发的闸就是有效判定**，
  后面的闸不再跑 ⇒ 报「谁拦的」必须按这个顺序，不要按「哪个判据更眼熟」）。

  | 会议 | 闸的判定（首个触发） | 人的判定 | 一致 | 关键数字 |
  |---|---|---|---|---|
  | **256** | **五闸全过** | 应用 | ✅ | 未识别 2023→309（63.3%→9.7%）；台账 719/722 **前后同为 99.6%**；3 条错名**改前改后完全相同**；闸C 比值 王天志 0.957 / 张宏魁 1.010；池 8 人 |
  | **229** | **五闸全过**（B2 告警被**最近 anchor 24/31 指向杜同贺**推翻） | 应用 | ✅ | 未识别 251→67（88.4%→23.6%）；台账 24/24；池 4 人 |
  | **243** | **B1 拦**（王天志不在 5 人池） | 不动 | ✅ | 613 段兜底给宋洋 |
  | **250** | **B1 拦**（吴孟铨/宋洋/张宏魁/赵航佳/陈金薪/韩重阳 被 `context` 踢出 3 人池） | 不动 | ✅ | ⚠️ **C 也会拦**（比值 **1.281 > 1.15**）—— 但 B1 在前，**有效判定是 B1** |
  | **255** | **B1 拦**（宋洋/陈金薪/韩重阳被踢出） | 不动 | ✅ | ⚠️ **D 也会拦**（未识别 413→863）；标签会变 450/3361 |
  | **247** | **B1 拦**（王天志不在 4 人池） | 不动 | ✅ | 标签会变 **0/89**（即便过闸也是 no-op） |
  | **254** | **五闸全过但 0 段会变**（真 no-op） | 不动 | ✅ | 标签会变 0/417；台账 163/163 |
  | **259** | **D 拦**（未识别 25→34） | 不动 | ✅ | ⚠️ **蒋芦笛会拿 75 段 = 类 20.241「整场汇报被吞」bug 复现** ⇒ D 拦得对 |
  | **262** | **D 拦**（未识别 213→257） | 不动 | ✅ | 标签会变 44/2180；池 6 人（陈天祥/王书馨**无质心**故不在池） |

  ⛔ **这张表曾经把 250 / 255 记成「C 拦」，是错的** —— 实测**首拦的是 B1**。
  报错的原因很具体：**闸顺序是串行的，B1 在 C 之前，`B1` 一拦就 `return`，C 根本没跑**
  ⇒ 「C 拦」是**读闸的顺序读错了**产生的结论。
  ⇒ **纪律**：报「哪个闸拦的」只能读**脚本里闸的实际执行顺序**，
  不能凭「这个判据的数值最刺眼」（类 20.225 的同族：**注释/文档在描述一个不存在的执行**）。

  ✅ **本次已写库（2026-10-30）**：**256**（写回 1714 段）与 **229**（写回 202 段），
  两场**五闸全过**。**验证方式是从 DB 读回、不是看脚本日志**（类 20.220）：

  | 会议 | 备份表 | 未识别（改前 → 改后） | 台账真值（改前 → 改后） | 错名明细 |
  |---|---|---|---|---|
  | **256** | `meeting_256_backup_pre_margin0p05_relabel` | 2023 → **309**（63.3% → 9.7%） | 719/722 → **719/722** | **改前改后完全相同**（`王天志->发言人?` 2 + `赵航佳->王天志` 1） |
  | **229** | `meeting_229_backup_pre_margin0p05_relabel` | 251 → **67**（88.4% → 23.6%） | 24/24 → **24/24** | 无 |

  ⇒ **迁移明细**：256 = `{发言人?->王天志 1537, 发言人?->张宏魁 177}`、**换名 0 条**；
  229 = `{发言人?->王天志 162, 发言人?->杜同贺 31, 王天志->发言人? 9}`、**换名 0 条**
  ⇒ **两场都是「补名」或「保守回退到发言人?」，没有一处把 A 的段改判成 B**。
  ⇒ `meetings.quality_status` 已回写（**10 场**的陈旧状态一并修正，
  256/229/259 均由 `fail` 变 `pass`；每场留 `meeting_<id>_backup_pre_quality_reeval` 备份）。
  ⚠️ **备份表名必须自带判据版本**（`margin0p05` 而非泛名 `margin`）——
  否则跑过多次不同 margin 的重标后**分不清是哪一次的前态**（类 20.220：名字在说谎）。

  ⚠️ **存量会议的转录不会自动重算** —— 改动只影响**之后**新处理的会议；
  要让历史会议变准需**逐个重标**（那是另一件事，别默认要做）。
  ⚠️ **重标后纪要会与新标签不一致**（纪要里的「【某人】」来自旧标签）⇒ 需**重生成纪要**
  （`scripts/voiceprint/regen_minutes.py`，走生产 `analysis` 阶段）。
  ⚠️ **重标后质量门的 `unknown_speaker_ratio` 与 `quality_status` 会随之变化** ⇒
  必须回写（`scripts/reeval_meeting_quality.py --write`），否则状态字段在说谎（类 20.220）。

  ⑦ ⭐ **「margin 的有效强度」依赖候选池规模 —— 加人进池会让 margin 变得更狠，不是更松** ——
     2026-10-30 实测（255，**同一天、同一个池、同一个脚本**，只改 margin）：

     | margin | 改后未识别 | 标签会变 | 簇级变化 |
     |---|---|---|---|
     | 0.10 | **1200** | 787/3361 | 簇 3（445 段）投票跌到 0 ⇒ **整簇无名** |
     | **0.05** | **863** | 450/3361 | 簇 3 拿到 250 票 ⇒ 恢复命名「王天志」 |

     ⇒ **margin 调小确实是更保守的**（0.05 严格优于 0.10）—— 但这**只是在池不变时**成立。
     **机制**：弃权条件是 `(second_dist - best_dist) < min_margin`，
     **候选池每多一个人，second_dist 就更小 ⇒ 同样 margin 下弃权更多**
     ⇒ 簇级雪崩（`votes < 3` 或 `votes/total < 0.30`）触发得更狠 ⇒ **未识别反而变多**。
     ⇒ **替代判据**：①**每次新建/重建质心后，所有存量会议的 margin 判据都漂移了**
     （类 20.248 ⑥ 说的「必须回归存量会议」，现在有了量化机制）；
     ②**报「某场的未识别数」必须同时报「当时的候选池成员」**，
     否则两个数字不可比（这正是下面 ⑧ 的成因）。

  ⑧ ⛔ **「两次重跑结果不一致」的第一嫌疑不是随机性，而是「输入变了」——
     而本仓最容易被忽略的输入是「候选池」** ——
     2026-10-30 实测坐实：255 在库内的「未识别 413」与当天重跑的「未识别 1200」**差 787 段**，
     当时按「不可复现」记账，并写下「已排除：段数、候选池成员、随机性」。
     **「候选池成员」其实变了** —— 库内那次的重标发生在 `13:45:11`，
     而**吴孟铨/韩重阳两个新质心写入于 `13:45:45`**（**相差 34 秒**）
     ⇒ 库内那次用的是**小池**，今天重跑用的是**大池** ⇒ 差值 = 池效应（见 ⑦），**与随机性无关**。
     ⇒ **三条纪律**：
     ①**复现性检查必须先冻结输入再谈确定性** —— 至少冻结
     **候选池成员名单 + 质心向量 + 台账 + 裁决表**四项；
     ②**「同一脚本两次跑不一致」不要直接写成「不可复现」** ——
     先查「两次之间库里的质心/台账/裁决表有没有变」（查 `member_voice_history.created_at`
     与 `meetings.updated_at` 的**先后顺序**即可定位）；
     ③**输入漂移导致的不一致是「需要重标」的信号，不是「脚本有 bug」的信号** ——
     处置是**重跑 + 重新过闸**，不是去查随机种子。


- ⚠️ **`MicroBubble-Auto-Recovery` 的"三层全修"是错的 —— 2026-10-13 逐层实测推翻**。
  原文（已废止，勿再引用）称"三层缺陷已于 2026-10-09 全修（触发器改 AtStartup /
  Action 补 powershell.exe 解释器 / alembic 断言改不变量），端到端验证 rc=0、`PASS 7/7`"。
  **逐层实测结果**（`Get-ScheduledTask` + 读脚本，非读 commit message）：

  | 层 | 声称 | 实测 | 判据 |
  |---|---|---|---|
  | ① 触发器改 AtStartup | 已修 | ❌ **未修** | 触发器仍是 `MSFT_TaskEventTrigger`，订阅 `Winlogon EventID=7002`；该任务不在 `MSFT_TaskBootTrigger` 列表里（同一批修好的 `MicroBubble-GPU-ASR-Daemon` **在**） |
  | ② Action 补解释器 | 已修 | ❌ **未修** | `Execute` 直接是 `.ps1` 路径，`Arguments`/`WorkingDirectory` 全空，无 `powershell.exe` |
  | ③ alembic 断言改不变量 | 已修 | ✅ **确已修** | `restart-recovery-after-gui-restart.sh:94-103` 确为「恰为 1 个 head」+「current == head」两条不变量 |
  | ④ 恢复脚本 UTF-8 BOM | 未提及 | ❌ **新发现** | `scripts/auto-recovery-eventlog.ps1` 含 **54 个汉字却无 BOM** ⇒ PS 5.1 按 GBK 解码 ⇒ 解析错误（类 20.216 第 4 形态）|

  **①②叠加 ⇒ 该任务从未自动执行过一次。** 判据是**副作用产物**而非状态字段：
  `logs/auto-recovery/` 下只有 `auto-recovery-20260804.log` 与 `auto-recovery-20261009.log`，
  此后再无新文件；`LastRunTime` 停在 2026-10-09、`LastTaskResult=1`。
  ⚠️ **2026-10-13 03:13 机器真实重启过，`LastRunTime` 仍纹丝不动** —— 这就是
  "下次重启后需再验证一次"那半句本该抓住的信号，当时没人回读它。
  ⇒ **`PASS 7/7` 只证明了 bash 恢复脚本本身能跑通，没证明任务能被调度器拉起来** ——
  这是类 20.220 的完整形态：**"手动触发能跑"被当成了"自动调度能跑"**。

  **已修（本次）**：④ 已补 BOM；① ② 的修复脚本 `scripts/ci/fix-autorecovery-task.ps1`
  已就位（含回读断言 + 控制字符检查 + 幂等）。
  ⚠️ **`Set-ScheduledTask` 需要管理员权限**，普通 shell 跑会得 `0x80070005` 拒绝访问
  （且失败发生在生效之前，任务定义不会被半改）。

  ✅ **2026-10-13 17:23 首次真实自动执行成功 —— 四层缺陷全部闭环**（判据是**副作用产物**，
  `logs/auto-recovery/auto-recovery-20261013.log` 2825 字节，`LastTaskResult=0`）：

  | 环节 | 结果 |
  |---|---|
  | 触发 | `MSFT_TaskBootTrigger(PT2M)` + `MSFT_TaskLogonTrigger(PT2M)`，双触发器 |
  | Step 1 等 Docker daemon | ready（0.2s） |
  | Step 2 查 8000 僵尸端口 | clean |
  | Step 3 跑 bash 恢复脚本 | **rc=0**（`PASS 7/7`、alembic 守恒过、celery 2 pong） |
  | 结果 | `success: true`、`gui_restarted: false`、耗时 15.5s |
  | 副作用 | 13 个容器仍 Up 14 hours，**未被重启** |

  ⚠️ 触发它的脚本里 `trigger` 字段**曾硬编码** `"Winlogon EventID=7002 + Delay 2min"`，
  而那时触发器早已改成 Boot+Logon ⇒ **日志在描述一个不存在的触发器**（类 20.220 的
  变体：连日志里的元数据都会骗人）。已改为**运行时读回任务定义**，实测输出
  `Boot(delay=PT2M), Logon(delay=PT2M)`。

  ⚠️ **第 ③ 层（alembic 断言）本次顺带被独立验证**：宿主直跑恢复脚本输出
  `alembic 守恒: 恰 1 head 且 current==head (145_kpt_content_tsvector)`。
  ⇒ 至此**四层全部有实测证据**，不再有任何一层依赖"当初说修好了"。

  `MicroBubble-DFT-Cleanup` **已于 2026-10-09 划归 `E:\dft-service` 独立项目, 不再是本仓遗留**
  (本仓 DFT 集成 2026-09-13 已整体移除, 见 commit `48e1cb0f2` / `0d70dd66e`; 该计划任务归那个
  项目的运维, 主指挥 2026-10-09 明确不许本仓处置它, 原"LastTaskResult=1 但功能未坏"的记录随
  之移交)。`MicroBubble-GPU-ASR-Daemon` (AtStartup) 与
  `MicroBubble-SSH-Tunnel-Guard` (每5min) 均验证正常, 无需处理。
- **DFT 已彻底移出本仓 (2026-10-09 复核, 主拍确认本项目不再有 DFT 业务)** —— 取证结论:
  ①**活代码早已清零**: `app/services/dft_client.py` / `app/agent/tools/dft_tools.py` /
  `app/api/v1/dft.py` / `tests/test_dft_tools.py` / 前端 `DftView` 与 `/dft` 路由, 均在
  2026-09-13 由 `48e1cb0f2` (移除集成) + `0d70dd66e` (清死配置) 删除, 2026-10-09 实测文件
  已不存在; ②`requirements.txt` **零 DFT 专属依赖** (无 pyscf/psi4/ase/scichem/gromacs),
  无可删项; ③compose / `.env` / `app/config.py` 均无 DFT 残留 (config 已无 `DFT_SERVICE_URL`);
  ④`dft_jobs` 表**存在但 0 行** (只读实测)。
  **唯一必须保留的残留 = `alembic/versions/099_add_dft_jobs.py`**: 容器实测 `alembic history`
  含该 revision 2 次 = **它在活链上** (`104_add_knowledge_chunk_late_embedding.py:12`
  `down_revision = "099_add_dft_jobs"`), 删它会**断 alembic 链**并阻塞部署。表可留, 代码已无。
  本次只删 `scripts/dft/README.md` (外置说明的唯一残留) + 2 个 `test_dft_tools` 陈旧 `.pyc`。
  ⚠️ **`E:\dft-service\` 是用户的独立项目, 不属本仓, 不许删** (含其
  `MicroBubble-DFT-Cleanup` 计划任务); 且 `~/.claude.json` **全局 mcpServers 仍注册 `dft`**
  (`E:\dft-service\.venv\Scripts\python.exe E:\dft-service\mcp_server.py`), Claude Code 会
  拉起它 —— 按类 20.212, "看着像残留" 实为**仍被引用的活链路**, 主指挥 2026-10-09 已裁定不处置。
- ⚠️ **`.dft` 前缀 ≠ DFT 计算**: `web/src/components/drive/DriveFileTable.vue` 用 `.dft` /
  `.dft-grid` / `.dft-head` / `.dft-c` 作 **DriveFileTable** 的 CSS 类前缀, `scripts/
  .token-orphan-allowlist` 的 `--dft-sb` 是其滚动条 token —— **两者都与化学 DFT 无关, 勿动**
  (grep `dft` 会大量命中此类假阳性)。同理 `app/services/research_profile.py` /
  `personalized_followup_generator.py` / `web/src/utils/paper/figures.js` 里的 "DFT" 是
  **科研画像与论文图表的领域关键词**, 属 RAG 业务语义, 非 DFT 服务集成。
- **vision-mcp 已处置 (2026-10-09)** —— 改为 compose profile 隔离, 默认不启动, 但服务定义完整保留。
  根因不是"当前没人调", 是**架构上走不通**: app 侧视觉走 **stdio 子进程**, 从不连这个容器 ——
  `app/config.py:79` `VISION_USE_MCP=False` / `:80` `VISION_MCP_TRANSPORT="stdio"` /
  `:81` `VISION_MCP_SERVER_CMD="python -m mcp_server.server"`, `app/mcp/client.py:21` 拿该 CMD 在
  **app 本进程内**起子进程; `app/config.py:82` 的 `VISION_MCP_BASE_URL="http://vision-mcp:8001"`
  经全仓 `git grep` 实测**除定义行外零引用**, 该 http 地址从未被连过 (无端口映射亦印证)。
  即便日后打开 `VISION_USE_MCP`, 默认仍走 stdio, 依旧用不到容器; 容器留着只为保住
  `Dockerfile.mcp` + `app/mcp/` 的可编译性 (类 20.215"实验块逐字段圈界"的镜像)。
  **启用方式**: `docker compose --profile vision up -d vision-mcp`;
  验默认不启: `docker compose config --services | grep vision-mcp` 应**无输出**。
  profile 命名跟随 `docker-compose.test.yml` 里 `minio-test` 的 `profiles: ["s3"]` (同为
  "服务定义保留 + 按需启用" 的同构场景, 用**能力名**); 本仓另一处 `disabled`
  (`docker-compose.dev.yml` / override 的 nginx) 语义不同, 那是"跑在别处、本机别起"。
  ⚠️ `depends_on` 会**传递性**拉起 profile 服务使 profile 形同虚设 (test.yml 踩过), 已 grep 确认
  **零个 depends_on 引用 vision-mcp**, 故不会被绕过。
  停容器用 `docker compose stop vision-mcp` (**只 stop 不 rm/down**), 停后其余 13 个服务
  uptime 未变、`/health` 经 nginx 端到端 200 (类 20.213)。
  处置说明另见 `docker-compose.yml` 该 service 块内的中文注释。
- **glitchtip 不重建 (2026-10-09 主拍结案)**: 原记 "glitchtip + vision-mcp 重启前即 unhealthy;
  `2ab45943b910_`/`737c1a285543_` 前缀两个老改名容器与 `microbubble-agent-glitchtip-1`
  Exited 4 周残留并存" —— 2026-10-09 实测 `docker ps -a` 全量 15 个容器, **这三个容器均已不存在**
  (既非 Exited 也非残留, 是彻底没了)。**主指挥拍板: 不重建 glitchtip**, 该条就此结案。
  `docker-compose.yml` 里的 glitchtip service 定义**原样保留**(不删, 避免日后要重建时从头写;
  类 20.215"实验块逐字段圈界"的镜像), 但**主指挥不重建 = 现状即终态**。
  ⚠️ **准确描述**: 该 service 挂在 compose **默认 profile** 上(`image: glitchtip/glitchtip:6.2.2`,
  `container_name: microbubble-agent-glitchtip-1`), 即 `docker compose config --services`
  **仍会列出 glitchtip** —— 它只是**从未被 `up` 过**, 所以 `docker ps -a` 里没有容器。
  这与 vision-mcp 的 `profiles: ["vision"]` 隔离**不是一回事**: vision-mcp 是被 profile
  显式排除出默认启动集, glitchtip 则是"定义在、默认也参与解析、但没人起它"。
  **不要**给 glitchtip 加 profile(那等于替主指挥做了"要不要隔离"的决定);
  **只要不执行 `docker compose up glitchtip` 就不会有任何影响**。验: `docker ps -a | grep
  glitchtip` 应无输出。


---

## W100 构建确定性永久纪律（2026-08-03，类 20.133）

- **Vite build 必须 deterministic**：同一 source、同一依赖锁定版本、同一构建配置必须产出相同的 `dist` 文件内容、文件名和 hash；提交前应使用两次连续 build + `diff -r` 或 manifest/hash 清单核验。
- **禁止向构建产物注入进程态值**：build-time `define`、banner/footer、插件 `augmentChunkHash` 等不得使用 `process.env`、`Date.now()`、`new Date()`、`Math.random()`、`crypto.randomUUID()`、`process.pid` 或其他随机/时间/进程 ID 生成 build ID。若需要版本标识，必须从**构建源输入内容哈希**（显式允许清单，绝不含自入库的产物目录——`web/dist` 入清单即哈希循环永不收敛）或 CI 显式固定输入派生。**HEAD 短哈希 / HEAD commit 时间不合格**：任何 commit（含纯 docs）都会变，会沿依赖图级联搅动全部 chunk（R-5 根治，2026-10-07，实现与反循环论证见 `web/vite.config.js` 顶部注释）。
- **R-5 根治落地（2026-10-07）**：`web/vite.config.js` 的 `BUILD_TIMESTAMP` = `git log -1 --format=%cI -- <SOURCE_INPUTS>`（语义 = **源码最后修改时间**，非构建时刻）；`BUILD_ID` = 源输入清单 sha256 前 12 hex（内容变才变，含未提交工作区改动）。dist/docs/测试提交不再改变二者 → 入库 dist 重建可逐字节复现。降级策略按模式分流：`vite build` 遇 git 不可用或浅克隆空 path-log → throw fail-loud（CI 实测从不跑 `vite build`）；dev/CI dev-server → **确定性**降级（浅克隆空 path-log 用 tip 提交时间；容器内 git 不可用用固定哨兵 `no-git-dev`），dev 产物不入库，防止 playwright.yml depth=1 浅克隆与 visual-vite 无 git 容器被误杀。**入库顺序纪律**：源输入改动必须**先提交、再 `npm run build`、再提 dist**——原子 src+dist（构建跑在提交前）会让 timestamp 滞后一个源提交，该提交上重建不恒等（e50631024 实战修正）；可复现点 = dist 提交。
- **`NODE_ENV` 必须在 build script 显式声明**：`NODE_ENV` 与 Vite `mode` 是两个独立维度；不得假定 `vite build` 的 production mode 会替代 `process.env.NODE_ENV`。跨平台脚本应使用仓库认可的环境变量注入方式，并在 CI 日志中打印并核验实际值。
- **Vite/Rollup 默认不会凭时间生成 chunk hash**：`[hash]` 是渲染内容及依赖关系的内容 hash；任何插件、loader、注入常量或非固定环境输入改变 chunk 字节，都会沿依赖图触发连锁 rename。调查证据见 `docs/research-build-determinism-2026-08-03.md`。
- **异常 fallback 也必须 fail-loud 或确定**：无 `.git`/detached 环境不得静默退回 PID+时间随机标识；应由 CI 提供固定 `VITE_BUILD_ID`/`VITE_BUILD_TIMESTAMP`，或明确失败并阻止发布。`f31901caf` 的现有 fallback 是后续加固留口，不得复制到新构建配置。
- **构建锁定纪律**：使用 `npm ci`、提交并校验 `package-lock.json`，固定 Node/Vite/Rollup 版本；不得用未锁定的 `npm install` 作为可复现 build 证据。

类 20.133 的实战证据与 18 项调查反馈详见 `docs/research-build-determinism-2026-08-03.md`；本任务仅新增文档/规则/memory，不修改 `app/`、`web/src/` 或构建实现。

---

## 会议纪要标准格式（2026-06-06 硬规则）

后续所有会议 AI 分析、手动优化会议内容、历史会议补写，都必须按 `2026.5.28 例行例会` 的信息密度输出，不能只生成短摘要。完整规范见 `docs/meeting-minutes-standard.md`。

- **摘要**：3-6 句，必须包含会议背景、讨论过程、关键人物观点、结论和后续方向。
- **讨论要点**：`key_points` 必须使用 `【发言人】内容` 格式；短会议也至少提取 3 条，信息充足时 5-8 条。
- **决议事项**：`decisions` 必须使用 `【发言人/双方/全组】内容` 格式，写清楚决定/共识和后续用途。
- **原始转录保护**：不改 `transcript` 原始转录，只优化 `transcript_polished`、`summary`、`key_points`、`decisions`。
- **禁止误认**：声纹无法确认时使用 `发言人A/B`，不要为了完整性强行猜姓名。

## 前端设计系统

**CSS 设计令牌**：`web/src/assets/variables.css`，暖橙珊瑚色系，可复用于所有页面。

主要变量：
- `--color-primary: #FF7A5C`（珊瑚橙）
- `--color-accent: #FFB347`（金橙）
- 阴影层级：`--shadow-sm/md/lg/primary`
- 圆角规范：`--radius-sm(4px)/md(8px)/lg(12px)/xl(16px)`
- 动画时长：`--duration-fast(150ms)/normal(200ms)/slow(300ms)/counter(500ms)`

动画规范：使用 `fadeSlideUp`/`slideDownFade` 入场动画类，stagger 延迟 `.stagger-1` ~ `.stagger-6`。

设计规范文档：`.claude/skills/ui-design/SKILL.md`（20项 UI 升级检查清单）

## 关键架构决策

- Agent 工具调用经 `app/agent/tools/` 工具注册表路由到 service 层（**15 个模块共 32 个 `@tool`**）。
  ~~`app/agent/core.py` 的 `_execute_tool`~~ 已于 2026-06-14 方案 C 全部迁出（`tools/__init__.py:6` 有迁移说明）
- `chat()` 和 `chat_stream()` 接收 `db: AsyncSession` 参数，由 API 路由通过 `Depends(get_db)` 传入
- 使用 `AsyncAnthropic` 客户端，不阻塞事件循环
- **Agent 回复采用"先简要后详细"双层结构** — 两阶段并行调用，简要立即返回，详细后台追加
- **MCP 视觉服务架构** — 预写架构，切换支持图片识别的文本模型时启用（如未来切 Claude 视觉）
- 认证使用 JWT，`app/core/security.py` 已实现；`app/api/` 下 **342 个路由装饰器**、330 处 `get_current_user` 引用
- 会话存储在 Redis（`RedisSessionStore`，**48 小时 TTL** — `app/config.py:250` `SESSION_TTL=172800`）
- 知识库使用 pgvector 做向量搜索（扩展已在 main.py 启动时自动安装；嵌入模型现役为 **Qwen/Qwen3-Embedding-0.6B**（1024d，`app/services/embedding_service.py:32`），`text2vec-base-chinese`（768d）仅为备选）
- **知识库深层逻辑系统（Knowledge Brain）** — 八大模块：
  - **动态 LLM 分析**：LLM 根据内容自由生成分类/标签/key_concepts/related_topics/knowledge_type，不再硬编码
  - **自动关联引擎**：新入库条目通过 pgvector 余弦相似度 + 概念重叠自动发现关联关系，双向写入 knowledge_relations 表
  - **RAG 问答引擎**：语义搜索 → 阈值分类 → LLM 合成 → 来源引用，高相关不足时自动触发研究
  - **自主研究引擎**：知识空白检测 → 联网搜索（搜狗+必应）→ 网页抓取 → LLM 提取 → 自动入库 → 建立关联
  - **健康监控**：Celery 定时任务检测矛盾/重复/过期条目
  - **实体知识图谱**：跨文档实体融合（精确匹配→embedding 余弦→新建），共现网络，ECharts 力导向图可视化
  - **假设生成引擎**：从实体三元组+知识空白 LLM 生成可验证假设，proposed/validated/rejected 生命周期
  - (2026-09-13 移除量化推理引擎/公式分类体系/公式自动分类 — 公式计算功能整体下线，文献多模态公式提取保留)
- 语音识别现役为 **SenseVoice**（`ASR_DEFAULT_BACKEND=sensevoice`，GPU 容器服务）；
  链路为 GPU 会议转写 7B（VibeVoice-ASR，运行时在 `data/vibevoice-test`）优先 + SenseVoice 分段回退。
  faster-whisper（`app/whisper_server.py`）保留为紧急回滚后端。TTS 主路径 Edge-TTS
- **会议转录总结工具** — `summarize_meeting_transcript` 工具支持对话触发与长期存储
- **任务软删除/垃圾桶** — 删除任务进入垃圾桶（deleted_at 字段），支持恢复或永久删除，3天后自动清除（Celery beat 每 1h 调度 `auto_purge_trash_task`，垃圾桶 UI 双行显示倒计时 + 5 级紧急度颜色）。详细状态见 [README.md](README.md#当前状态2026-06-03)
- ~~**微信对话双消息模式**~~ — 企业微信已于 2026-09-12 整体下线，此模式无现存代码
- **移动端独立抽屉架构** — 移动端侧边栏使用 el-container 外部独立 div + Vue Transition，完全绕过 Element Plus aside 的全局 CSS 干扰。桌面端 `v-if="!isMobile"` 零影响
- **通知面板** — 铃铛使用 el-popover 弹窗面板，显示每条提醒的具体内容（任务标题+提醒时间）、全部标为已读、点击跳转任务；头像读取 userStore.userInfo.avatar 真实 URL
- **任务权限模型** — 所有成员可见全部任务（降低认知负担）；2026-09-05 角色扁平化后所有登录成员等权，任意成员可编辑/删除/恢复/永久删除
- **状态统一** — "待办"(todo) 和 "进行中"(in_progress) 语义高度重合，已统一为"进行中"。新建任务默认 in_progress，现有 todo 任务兼容显示
- **移动端路由级双栈架构**（2026-06-13 收官）— 桌面端（Element Plus）和移动端（NutUI 4）**同一 URL 不同组件**，不共享 component 树。`useIsMobile.js` 监听 viewport + UA 兜底 → `router/index.js` 通过 `resolveMobile.js` 动态 import `views/mobile/*` 或 `views/*` → 桌面端 `el-*` 与移动端 `nut-*` CSS 完全隔离。**离线策略**：~~PWA 4（manifest + workbox SW 预缓存）~~ 已于 2026-07-27 强制注销（见下文 PWA 失效警示）；
  `useSafeArea` 读 iPhone 安全区仍有效。**视觉回归测试**：Playwright 5 viewport × 13 核心页面，CI 截图对比基线

## 代码质量规范（2026-06-04 升级）

### API 层
- **统一异常响应格式**：`{"error": {"code": "RESOURCE_NOT_FOUND", "message": "...", "details": {...}}}`
- **异常类层次**：`app/core/exceptions.py` — AppException/NotFoundException/ValidationException/AuthException/ForbiddenException/ConflictException/RateLimitException
- **统一分页模型**：`app/schemas/pagination.py` — PaginationParams + PaginatedResponse + PaginationMeta
- **全站分级限流**：`app/core/rate_limit.py:209-217` — auth:20次/分、write:30、read:200、upload:10；
  另有 sse:10、chunked_upload:60、drive_upload:50、drive_list:300、auth_refresh:60
- **安全响应头**：X-Content-Type-Options/X-Frame-Options/X-XSS-Protection/Referrer-Policy/X-Request-ID

### 前端架构
- **Composable 模式**：`web/src/composables/` — useTask/useMeeting/useKnowledge 提取共享状态 + API 调用
- **子组件拆分**：`web/src/components/` 下 **139 个 .vue**，分布 9 个子目录（mobile 27 / drive 25 / chat 25 / paper 13 / knowledge 7 / common 5 / desktop 4 / voiceprint 3）
- **Vitest 测试**：`web/vitest.config.js` — **96 个测试文件 / 1038 个用例**（composable 31 文件 + component 32 文件等）

> ⚠️ **本节已于 2026-07-27 失效（PWA 被强制注销）** —— commit `36b0b2ec9`
> （W68 第 14 批 H-3）把 `web/vite.config.js` 的 `VitePWA({ disable: true })` 打开，
> 理由是"主指挥浏览器老 SW 仍 active 致持续刷新"。**当前 dist 不含任何 PWA 产物**
> （无 `manifest.*.webmanifest`、无 `sw.js`、index.html 无 manifest link）——这是
> **预期状态，不是缺陷**。
>
> 因此以下内容**仅作历史记录**，不要照做：`manifestHashPlugin`、postbuild manifest
> hash 改名、nginx `location = /manifest.webmanifest { return 410; }`、部署时
> `git add -f web/dist/manifest.{hash}.webmanifest`。
> **若将来要重新启用 PWA**：先在 vite.config.js 把 `disable` 改回 false，再按本节
> 纪律补齐 manifest MIME / hash / SW 生命周期，并**清理浏览器端旧 SW 与 Cache Storage**
> （这正是当初禁用的根因）。
>
> 另注：nginx 侧 `types { application/manifest+json webmanifest; }` 曾因
> "server context 是完全覆盖语义"打挂整站 MIME（`08f440f` 事故），现已回滚——
> 那个坑与 PWA 是否启用无关，仍值得记住（见下方 nginx 段）。

### 2026-06-13 webhint PWA 5 警告全栈修复新增（commit `08f440f` + `c855f0e`）〔已失效，见上方警示〕

- **Nginx 缺 `.webmanifest` MIME（commit `08f440f`）** — Nginx 默认 `mime.types` 不包含 `.webmanifest`（到 1.27 才内置），回退 `application/octet-stream` → 浏览器拒绝解析 PWA manifest → 添加桌面图标失败。**修复**：server block 加 `types { application/manifest+json webmanifest; }` + `charset_types` 同步加 `application/manifest+json`（让 `charset utf-8` 生效）。**诊断**：`curl -I https://xxx/manifest.webmanifest | grep Content-Type` 看是不是 octet-stream。**纪律**：所有 PWA 项目上线前必须验证 manifest MIME，**仅一次**而不是每个 server 都加。
- **`vite-plugin-pwa` 输出 manifest 不带 hash（commit `08f440f`）** — `manifest.webmanifest` 文件名固定不走 rollup hash 流程，webhint cache-busting 永远警告。**修复**：写一个 Vite 插件 `manifestHashPlugin`（closeBundle 钩子）→ `crypto.createHash('sha256').update(content).digest('hex').slice(0, 8)` → 重命名为 `manifest.{8char_hash}.webmanifest` + 同步改 `index.html`/`offline.html` 的 link 引用。**8 字符 hex 满足 webhint 默认 `[0-9a-f]+` 正则**。**Vite 5+ emitFile 不适用**（manifest 是 vite-plugin-pwa 输出，emitted by another plugin），必须 fs.renameSync。
- **`/registerSW.js` 静态注入无法 cache-busting（commit `08f440f`）** — `VitePWA({ injectRegister: 'auto' })` 自动注入 `<script src="/registerSW.js">`，文件名固定无 hash。**修复**：`injectRegister: null` + `main.js` 用 `import { useRegisterSW } from 'virtual:pwa-register/vue'` 替代。**Vue composable 在生产 build 时被 rollup 处理，运行时通过 sw 注册的副作用自动跑**，无需手动写 `<script>`。**纪律**：PWA 项目**避免** `injectRegister: 'auto'`，除非真的需要纯静态（非 SPA）站点。
- **删除 manifest.webmanifest 后 SPA fallback 误返 index.html（commit `c855f0e`）** — git 删除旧 manifest 文件后，Nginx `try_files $uri $uri/ /index.html` 找不到文件 → fallback `/index.html`（1924 字节 HTML 内容） → 任何残留引用/书签/扫描器拿到 HTML 内容物以为是 manifest。**修复**：在 `/` location 前加 `location = /manifest.webmanifest { return 410; }` 精确 410 Gone。**纪律**：SPA 部署时**所有被废弃的资源路径**都应该有明确返回（410 / 404），不能依赖 try_files fallback。
- **theme-color Firefox 不支持** — Edge DevTools 内置 webhint 不读 `.hintrc`，永远警告。**纪律**：`.hintrc` 配 `meta-theme-color: "off"`（webhint CLI 0 警告），接受 Edge DevTools 误报。Chrome/Safari/iOS Safari PWA 顶部栏颜色价值 > Edge DevTools 警告噪音。**永远不要**完全删除 theme-color meta（损失浏览器原生美化）。

### 2026-07-11 PWA manifest 410 回归 (commit `59187ce8` cascade folder delete 引入, `5d2bcdfd` 修复) 〔已失效，见上方 2026-07-27 注销警示〕

> ⚠️ 本节铁律全部建立在"PWA 启用"前提上，该前提已于 2026-07-27 被
> `36b0b2ec9` 取消（`VitePWA({ disable: true })`）。**不要**再执行
> `git add -f web/dist/manifest.{hash}.webmanifest` 等操作——文件根本不存在。
> 保留本节仅为解释 `5d2bcdfd` 提交为何存在。

> ⚠️ **铁律**: `web/package.json` `"build": "vite build && node scripts/postbuild-fix-manifest.js"` 是**唯一**合法 build 命令。**严禁** `vite build` 直跑然后 force-add commit dist — manifest.webmanifest 保持 unhashed → nginx `location = /manifest.webmanifest { return 410; }` 拦截 → 浏览器 `Manifest fetch failed, code 410` → PWA install 失败。`package.json` 有 `build:raw` 别名但**仅供调试 sw.js 内容用**, 调试完必须重跑 `npm run build` 才能 commit。

- **根因**: commit `59187ce8` 用 `vite build` 直跑绕开 postbuild → `git show 59187ce8 -- web/dist/manifest.webmanifest` 显示 `manifest.4f8d6b64.webmanifest => manifest.webmanifest` (rename 回 unhashed) → 服务器 410 → 用户浏览器 PWA install 失败。
- **修复 (commit `5d2bcdfd`)**: `cd web && npm run build` → postbuild 自动 3 件事 + 健全性自检 + `git add -f web/dist/manifest.{hash}.webmanifest` (新增文件 .gitignore 拦了必须 `-f`) + push → webhook 30s → 浏览器 DevTools Clear site data + 硬刷。云端验证: `/manifest.webmanifest` 410 (防护保留) + `/manifest.4f8d6b64.webmanifest` 200 (`application/manifest+json`)。
- **纪律**:
  1. **`npm run build` 是唯一合法 build 命令** — `vite build` 直跑 = 必坏 PWA (服务器 410 + 浏览器 install 失败)
  2. **服务器 410 manifest.webmanifest 是有意防护** — 防 SPA `try_files` fallback 误返 index.html (c855f0e 教训)。修法只能改客户端 dist, 不能动 nginx
  3. **commit 前必须 grep dist** — `git diff --cached -- web/dist/ | grep -E '"url":\s*"manifest\.webmanifest"'` 期望空输出
  4. **SW BUMP commit 必须连带重跑 npm run build** — 任何 SW_VERSION bump 都会触发 dist 改动, 调试时必须用 `npm run build`
  5. **.gitignore 含 `web/dist/` → git add 必须 -f** — `git add web/dist/` 默认啥都不加, 新增 hashed manifest 文件**极易漏 force-add**, 修法 `git add -f web/dist/manifest.{hash}.webmanifest` 逐一加
- **下次加固 PR**: `scripts/deploy-auto.sh` line 134 (v80 修复加入) `grep -oE '"url":"manifest\.webmanifest"' dist/sw.js` 只检查**新 build**, 不检查 git staged。建议加 `git diff --cached -- web/dist/sw.js | grep -qE '"url":\s*"manifest\.webmanifest"'` 拦截任何 stage 的 unhashed 引用 (commit 59187ce8 这条恰好能拦下)。
- **memory 沉淀**: ~~`memory/pwa-manifest-410-regression-2026-07-11.md`~~ — 该文件已随
  2026-08 memory 目录停更清理而不存在（链接悬空，2026-09-30 核实修正）。5 条铁律的
  正文即本节上文，commit 链见 git log。

### 2026-07-24 alembic 并行 agent 串单链纪律 (commit `1852468a6`)

> ⚠️ **铁律**: 并行派多个写 alembic migration 的 agent 时, 派工 prompt **必须明确 down_revision 接续关系**, merge 后**必须 verify 只有 1 个 head**。否则 `alembic upgrade head` 报 `Multiple head revisions are present` 直接阻塞部署。

- **根因**: W68 第 3 批 F-1 (062 drive_comments) + F-2 (063 drive_file_versions) 两个 agent **并行**开发, 派工 prompt 没写接续关系 → 都声明 `down_revision="061_drive_folder_share"` → merge 进 main 后 alembic 链在 061 处分叉成**两个 head** → `alembic upgrade head` 报 `FAILED: Multiple head revisions are present for given argument 'head'`。
- **修复 (commit `1852468a6`)**: 主指挥在 merge 062 后改 063 `down_revision="062_drive_comments"` 串成单链 `061 → 062 → 063`。这是本项目 053/054/055/056 四连 CI unique 迁移用过的模式 (每张迁移严格单链)。**不用**解法 B (`alembic upgrade heads` 保持双头) — `downgrade -1` 语义歧义 + 未来 064 接链需要 `alembic merge` 留坑。H-1 agent 已在 `docs/drive-v2-pr9-deployment.md` 第 0 节 + `docs/drive-v2-pr9-rollout-checklist.md` 1.1 记录此流程。
- **纪律 (5 条)**:
  1. **并行派 alembic migration agent 必须明确接续关系** — 派工 prompt 必须写清楚"down_revision 接 X", 不写就默认接最新。两个 agent 同时接同一个上游 = merge 必双头
  2. **merge 顺序必须按 alembic 链** — 先 merge 最上游的 migration, 再 merge 下游的。不能并行 merge (无依赖关系时除外)
  3. **merge 后立即 verify** — 期望只 1 个 head:
     ```bash
     python -c "from alembic.config import Config; from alembic.script import ScriptDirectory; c=Config(); c.set_main_option('script_location','alembic'); s=ScriptDirectory.from_config(c); print(s.get_heads())"
     ```
  4. **部署文档第 0 节必含 alembic chain 风险** — 任何写 alembic migration 的 PR 必须在部署文档顶部加"alembic 链风险"段, 提醒主指挥 merge 顺序 (参考 `docs/drive-v2-pr9-deployment.md` 第 0 节)
  5. **跨 PR 部署 alembic 必须 cp + clear cache** — `docker cp alembic/versions/0XX_*.py microbubble-agent-app-1:/app/alembic/versions/` 后必跑 `docker exec -e SKIP_DB_SETUP=1 microbubble-agent-app-1 rm -rf /app/alembic/versions/__pycache__` (**重启纪律** 升级 —— 见下方「部署必做」段: 改完 Python 代码必 `docker compose restart app celery-worker`; `__pycache__` 残留会让老 down_revision 继续生效, 双头假修复。2026-10-09 起改为具名引用, 不再写会漂移的行号)
- **memory 沉淀**: [`memory/w68-alembic-chain-discipline-2026-07-24.md`](./memory/w68-alembic-chain-discipline-2026-07-24.md) (锚点范式第 46 守恒 + 完整时间线)

### 2026-06-13 Vue 3.5 'bum' null bug 真根因 + Vite plugin patch（commit `79305b7`）

- **Vue 3.5 unmountComponent 仍缺 instance null 检查** — 之前 CLAUDE.md 误记"Vue 3.5.34 PR #11487 已修 `bum` bug"，**实际未修**。`@vue/runtime-core/dist/runtime-core.esm-bundler.js:6763`（3.5.34）和 `:6763`（3.5.38 raw 检查）：
  ```js
  const unmountComponent = (instance, parentSuspense, doRemove) => {
    if (__DEV__ && instance.type.__hmrId) { ... }   // ← instance 仍可能为 null
    const { bum, scope, job, subTree, um, m, a } = instance  // ← 爆点
  ```
  只有 line 6572 的 `unmount()` 函数 vnode 解构加了 null 检查，`unmountComponent()` 的 instance 解构**漏修**。minify 后报 `Cannot destructure property 'bum' of 'e' as it is null`（`e` = `instance`）。
- **触发链路** — Element Plus el-table/el-table-column/el-checkbox/el-tooltip/el-popper 递归 unmount 时，**某子 vnode.component 已是 null**（HMR/路由切换/keep-alive 边界状态）→ `vnode.type.remove(...)` 调 `unmountComponent(null)` → 爆。常见触发页：`AgentTracesView`（19 el-table）/ `TaskTrash`（18）/ `SpeakerMappingPanel`（8）/ `KnowledgeView`（4 tab lazy）/ `VoiceprintEnrollDialog`（el-dialog + el-tabs + lazy）。
- **修复：Vite plugin transform 阶段 patch esm-bundler.js**（commit `79305b7`）—
  ```js
  // vite.config.js
  function vueBumNullPatchPlugin() {
    return {
      name: 'vue-bum-null-patch',
      enforce: 'pre',
      transform(code, id) {
        if (!/node_modules\/@vue\/runtime-core\/dist\/runtime-core\.esm-bundler\.js$/.test(id)) return null
        if (code.includes('/* patch:vue-3.5-bum-null */')) return null  // 防重复
        const pattern = /(const\s+unmountComponent\s*=\s*\([^)]*\)\s*=>\s*\{)/
        if (!code.match(pattern)) { console.warn('...pattern not found'); return null }
        return code.replace(pattern, `$1\n    /* patch:vue-3.5-bum-null */ if (!instance) return;`)
      },
    }
  }
  ```
  验证产物 grep `(e,t,n)=>{if(!e)return;let{bum` 即生效。
- **纪律** — ① 这种"上游已知 bug 但未修复"的场景，**Vite plugin transform 阶段 patch** 比 npm postinstall patch 更稳（postinstall 会被 reinstall 覆盖；plugin 在 build 时每次生效）② `enforce: 'pre'` 确保在 esbuild/rollup 处理前 patch③ 防御性 `if (code.includes('...')) return` 防重复 patch④ pattern 未命中要 `console.warn` 而非静默吞（升级 Vue 后能立即发现 plugin 失效，需要重新适配）⑤ **只 patch build 产物，不 patch dev mode**（dev 保留原始报错方便定位应用层问题）
- **临时性 + 自动失效** — 升级到 Vue 3.5.36+/3.6+ 若官方修了 `unmountComponent` instance null 检查，plugin 自动 skip（pattern 未命中 → warn）。监控 console 是否有 `[vue-bum-null-patch] pattern not found` 警告

### 2026-06-13 Nginx types 指令覆盖/合并行为差异 — 整站 octet-stream 白屏事故（commit `08f440f` 留尾 → `f148d96` + `5c24442` 修复）

- **事故** — 用户报告"打开 /dashboard /members 直接下载名为 dashboard / members 的文件"。curl 验证 `/index.html` 返回 `Content-Type: application/octet-stream` → 浏览器把 HTML 当二进制下载而非渲染。
- **根因（极隐蔽，2 层）** —
  1. `commit 08f440f` 在 `server { ... }` block 内加 `types { application/manifest+json webmanifest; }` 块想修 webmanifest MIME 问题
  2. **Nginx `types` 指令在 server context 是"完全覆盖"语义（NOT 合并）**：从 http context 继承的 mime.types 整个被丢弃，只剩 types 块里的 MIME → `.html` 找不到 `text/html` → fallback 到 `default_type application/octet-stream` → 整站 HTML/CSS/JS/PNG 全变 octet-stream
  3. **极其隐蔽**：webhint 只查 manifest.webmanifest 不查 HTML，所以没暴露这个问题；用户浏览器可能缓存了 08f440f 之前的 HTML 没刷新，所以没立即发现
- **修复路径（commit `f148d96` + `5c24442`）**—
  - **第一步（f148d96）**：删除 tunnel.conf 两个 server block 里的所有 `types { }` block，恢复 http context mime.types 默认合并语义
  - **第二步（f148d96）**：改 `scripts/deploy-auto.sh` 增加 webmanifest MIME 注入：
    ```bash
    if ! grep -q 'application/manifest+json' /etc/nginx/mime.types 2>/dev/null; then
        sed -i '/^application\/json[[:space:]]/a\    application/manifest+json           webmanifest;' /etc/nginx/mime.types
        if grep -q 'application/manifest+json' /etc/nginx/mime.types 2>/dev/null; then
            log "webmanifest MIME type added to mime.types"
        else
            log "ERROR: webmanifest MIME sed injection failed"  # fail loud
        fi
    fi
    ```
  - **第三步（5c24442）**：原 awk 模式注入失败（猜测 mime.types 行尾 `\r` 导致 awk `next+print` 行为异常）→ 改 sed `-i` 行后追加模式 + 注入后 grep 验证
- **纪律（5 条铁律）** —
  ① **Nginx `types` 指令上下文敏感**——
  - `http` context：**合并**（additive，可加新 MIME 不丢默认）
  - `server`/`location` context：**完全覆盖**（覆盖后必须列全用到的 MIME，否则 fallback octet-stream）
  - 缺省 default：`application/octet-stream bin;`（最小集）
  ② **永远不要在 server context 加 types { } block** —— 想给 PWA 加 MIME 就在 mime.types 里加（http context include 的那个文件）
  ③ **deploy-auto.sh 注入 mime.types 必须 fail loud** ——
  - sed/awk 注入后必须 `grep -q` 验证成功才 log success，否则 `log "ERROR: ..."`
  - 注入幂等（先 grep 是否已存在）
  - 优先用 sed `-i` 而非 awk（awk 在行尾 `\r` 时行为异常）
  ④ **Webhint 不查 HTML MIME** ——
  - webhint 报 manifest MIME 错误时**只查** manifest 不查 HTML/CSS/JS
  - 加 types { } block 可能悄无声息破坏整站 MIME，**改 nginx 配置后必须 curl 验证所有响应 Content-Type**（HTML + CSS + JS + PNG + manifest + sw.js 至少 6 点）
  ⑤ **改 nginx 配置后立刻 6 点 curl 验证** —
    ```bash
    curl -sk -o /dev/null -w "%{content_type}\n" https://xxx/index.html
    curl -sk -o /dev/null -w "%{content_type}\n" https://xxx/  # SPA fallback
    curl -sk -o /dev/null -w "%{content_type}\n" https://xxx/dashboard  # SPA route
    curl -sk -o /dev/null -w "%{content_type}\n" https://xxx/sw.js
    curl -sk -o /dev/null -w "%{content_type}\n" https://xxx/pwa-192.png
    curl -sk -o /dev/null -w "%{content_type}\n" https://xxx/manifest.{hash}.webmanifest
    ```
    任一返回 octet-stream 即配置错误，不要等用户报告
- **事故链时间线** —
  1. 08f440f（18:27 加 types block，覆盖 mime.types，**事故起点**）
  2. c855f0e（18:30 加 manifest.webmanifest 410）
  3. ef130ce（18:32 CLAUDE.md）
  4. 79305b7（18:40 Vue patch）
  5. 7a077dd（18:42 CLAUDE.md）
  6. 0a29290（18:49 试图"修复"types block，加完整 MIME 列表，但 types 指令在 server context 行为不变，整站仍 octet-stream）
  7. 用户报告"下载文件"
  8. f148d96（18:58 真修复：回滚 types block + 改 deploy-auto.sh）
  9. 5c24442（19:05 修 awk → sed）

### 2026-06-13 SW 污染 cache 修复 — 整站 HTML 修复后浏览器仍进不去（commit `747a735`）

- **第二阶段事故** — 服务器 MIME 修好后（`f148d96` + `5c24442`）curl 验证 `/` 返回正确 `text/html`，但**用户报告"网站还是进不去"**。curl 服务器一切正常 → 100% 是浏览器侧问题。
- **根因** — Service Worker 污染 cache：
  1. `08f440f` 部署后服务器开始返回 octet-stream HTML
  2. 用户访问时浏览器 SW（NetworkFirst 策略）**缓存了 octet-stream 响应到 `documents` cache**
  3. 服务器修复后 SW 仍可能返回缓存的 octet-stream（虽然 NetworkFirst 应优先网络，但浏览器 SW 缓存逻辑 + activate 时机导致老 cache 没及时清）
  4. `cleanupOutdatedCaches()` 只清 workbox 维护的 precache cache，**不**清 NetworkFirst/StaleWhileRevalidate 运行时创建的 cache
- **修复：sw.js 升级模式**（commit `747a735`）—
  ```js
  // web/src/sw.js
  const SW_VERSION = 'v2-cache-purge-2026-06-13'  // BUMP 触发 SW 字节变化
  self.__SW_VERSION__ = SW_VERSION

  self.skipWaiting()
  self.addEventListener('activate', (event) => {
    event.waitUntil((async () => {
      // 清空所有 cache（不只是 workbox 默认的）
      const keys = await caches.keys()
      await Promise.all(keys.map((n) => caches.delete(n)))
      await self.clients.claim()
      // 通知所有客户端 reload
      const clients = await self.clients.matchAll({ type: 'window' })
      clients.forEach((c) => c.postMessage({ type: 'SW_UPDATED', version: SW_VERSION }))
    })())
  })
  ```
  ```js
  // web/src/main.js
  useRegisterSW({
    immediate: true,
    onRegisteredSW(swUrl) {
      navigator.serviceWorker.addEventListener('message', (event) => {
        if (event.data?.type === 'SW_UPDATED') {
          setTimeout(() => window.location.reload(), 500)
        }
      })
    },
  })
  ```
- **修复链路** — 用户下次访问 → 浏览器检测 `/sw.js` 字节变化 → 安装新 SW → 立即 `skipWaiting` 激活 → `activate` 钩子清空所有 cache + `postMessage` → 客户端 `useRegisterSW` 收到 `SW_UPDATED` → `window.location.reload()` → 用户拿到全新资源
- **纪律（4 条铁律）** —
  ① **SW 污染 cache 修复必须改 sw.js** ——
  - 只改 HTML/JS/CSS 没用，浏览器 SW 还在用老 SW 文件
  - 改 sw.js 触发 SW 升级 + activate 钩子清 cache 是**唯一**标准修复路径
  ② **`cleanupOutdatedCaches()` 不够** ——
  - 它只清 workbox 维护的 precache cache
  - **不**清 NetworkFirst/StaleWhileRevalidate/CacheFirst 运行时创建的 cache
  - 真正"清空所有 cache"必须自己写：`caches.keys() + Promise.all(keys.map(caches.delete))`
  ③ **BUMP SW_VERSION 触发升级** ——
  - 浏览器通过**字节比较**检测 SW 更新（不是 SW 内容里的 manifest）
  - 改 sw.js 文件加一行 const 都会触发字节变化 → 浏览器拉新 SW → 升级流程
  - 每次事故修复或 SW 大改动时**都**应 bump 版本号
  ④ **postMessage + reload 闭环** ——
  - SW 升级后**不会**自动刷新页面（skipWaiting + clients.claim 立即接管但页面不 reload）
  - 必须 SW postMessage → 客户端监听 → `window.location.reload()`
  - 用 `setTimeout(..., 500)` 让 console.log 先显示出来再 reload
- **调试技巧** ——
  - 用户报"页面进不去"但服务器 curl 一切正常 → 100% 是 SW/浏览器 cache 问题
  - 让用户 DevTools → Application → Service Workers → 看到 SW 状态为 `activated` 且内容含新 `SW_VERSION` → SW 已升级
  - 让用户 DevTools → Application → Cache Storage → 应该看到 precache 列表**无 documents cache**（已被清空）
  - **兜底**：用户可手动 DevTools → Application → Storage → Clear site data 彻底重置

### 测试规范
- **后端**：pytest + httpx AsyncClient，service 层单元测试 + API 集成测试。
  规模：`tests/` 下 **402 个测试文件 / 4159 个 test 函数**（**实测 2026-10-15**；
  文件数 = `find tests -name "test_*.py" -not -path "*/__pycache__/*" | wc -l`，
  函数数 = `grep -rhoE "^\s*(async )?def test_" tests/ --include="*.py" | wc -l`
  —— 写死数字必然随增删漂移，改测试后请按上面两条命令回填）；CI 硬门
  `server-tests-baseline.yml` 8 片实跑 **3565 用例**（3376 passed / 0 failed /
  0 errors / 189 skipped，**该组数字是 2026-10-15 实测**，run `38600849147`，
  8 片 + Merge baseline summary 全绿）
  - ⚠️ **402 / 4159 的构成可对账**：399→402 是三个新文件
    （`test_pdf_layout_cleaner.py` 8 + `test_figure_anchor_snap.py` 4
    + `test_chunk_min_chars.py` 6），函数数 4141→4159 正好 +18，
    **与 CI 用例 3547→3565 的 +18 精确吻合**，无 unexplained 差额。
  - ⚠️ **上一轮 +2 的沿革**：397→399 曾是两个新文件
    （`test_meeting_processing_latency.py` 8 函数 + `test_speaker_adjudication.py` 14 函数），
    函数数 4119→4141 正好 +22。
  - ⚠️ **上一轮删文件的沿革**（397 曾是 2026-10-12 连删三个 RAG-FW 专属测试文件后的值，
    经 +2 → +3 两次新增现为 **402**）：400 → 398 → 397（函数数 4133 → 4128 → 4119），
    再 4119 → 4141（+2 文件）→ 4159（+3 文件）。
    三次删除分别是 `test_multi_hop_engine.py` / `test_semantic_chunker.py`（`e5333eb6f`）
    与 `test_agent_retriever.py`（删 agent_retriever 时）—— 三个模块均经
    **import blocker 运行时实测**确认零调用方后删除。
    两次都还需从**混合**的 `test_e2e_framework_gate.py` 里摘出对应用例并修
    `test_08` 冒烟循环（它逐个调用其余用例，漏改会直接 AttributeError），
    测别的能力的用例全部保留。
  - ⚠️ **87 个测试文件已归档**（模块级 `pytest.skip(allow_module_level=True)`，
    2026-10-12 实测仍是 87；⚠️ `grep -rln "pytest.skip"` 会得 116，**那是把函数内
    skip 也数进去了**，判归档必须带 `allow_module_level=True`）——
    断言历史 commit / 已下线功能 / 一次性验收 gate / 需真环境。**恢复流程与分类清单见
    [`tests/ARCHIVED.md`](tests/ARCHIVED.md)**。
    守门类测试（`test_no_prod_db_imports.py` 禁止测试直连生产库）**不得归档**。
- **前端**：Vitest + @vue/test-utils，composable 测试优先，组件测试选择性覆盖
- **Mock 策略**：Redis 用 fakeredis，Claude API 用 respx，Embedding 用固定向量

## 服务层结构

| 文件 | 职责 |
|------|------|
| `app/services/task_service.py` | 任务 CRUD + 统计 + 自动提醒 |
| `app/services/member_service.py` | 成员 CRUD + 按姓名查询 |
| `app/services/meeting_service.py` | 会议 CRUD + 参与者管理 |
| `app/services/project_service.py` | 项目+里程碑 CRUD |
| `app/services/knowledge_service.py` | 知识库 CRUD + 语义搜索 |
| `app/services/reminder_service.py` | 提醒服务 + Celery task |
| `app/services/search_service.py` | 联网搜索（搜狗+必应双引擎） |
| `app/services/embedding_service.py` | 向量嵌入（Qwen3-Embedding-0.6B, 1024d; 备选 text2vec-base-chinese） |
| `app/services/file_parser_service.py` | 文件内容提取（PDF/Word/Excel/PPT） |
| `app/services/llm_analysis_service.py` | LLM 内容分析（动态分类+标签+摘要+核心概念） |
| `app/services/knowledge_graph_service.py` | 知识图谱服务（自动关联+BFS 遍历+动态分类+标签云+统计） |
| `app/services/knowledge_qa_service.py` | RAG 问答引擎（检索+阈值+LLM 合成+来源引用） |
| `app/services/auto_research_service.py` | 自主研究引擎（联网搜索+知识提取+空白填充+矛盾/重复/过期检测） |
| `app/services/dynamic_taxonomy_service.py` | 动态分类体系（涌现分类+分类建议+主题网络） |
| `app/services/knowledge_evolution_tasks.py` | Celery 知识进化定时任务（每日进化/空白检测/健康检查/实体融合） |
| `app/services/reminder_scheduler.py` | Redis 精确提醒调度（秒级精度） |
| `app/services/entity_service.py` | 实体知识图谱（跨文档融合+搜索+图谱+LLM 合并） |
| `app/services/hypothesis_service.py` | 科研假设生成（LLM 驱动假设+验证生命周期） |
| `app/services/meeting_analysis_service.py` | 会议 AI 分析（发言者检测+格式识别+结构化分析+发言人统计+标题生成）|
| `app/services/voiceprint_service.py` | 声纹识别（3D-Speaker 嵌入提取+pgvector 匹配+录入）|
| `app/services/voiceprint_quality_gate.py` | 声纹 B+C 方案质量门 (W75 B-1, 4 子门禁, 派工 v6 段 5 反馈 #6)|
| `app/services/voiceprint_cross_meeting_regression.py` | 声纹跨会议 90% 回归门禁 (W75 B-1, 12 会议音频 + #151 rollback)|
| `app/services/voiceprint_quality_monitor.py` | 声纹质量门 Celery 30min 监控 (W75 B-1, 6 件套监控)|
| `app/voice/vad.py` | silero-vad 语音活动检测 |
| `app/services/audio_processor.py` | 音频格式转换（WebM→WAV）+ 离线 VAD 分段 |
| `app/services/image_decoration_filter.py` | 母版装饰横幅判据 (2026-10-09, 两信号交集; 写入侧 OCR 前拦截 + 检索侧排除共用同一常量) |
| `app/services/page_transcript_filter.py` | PPT 整页转写净化 (2026-10-09, 三档词表 + chrome_ratio 拍屏拦截 + 尾随总结; `blocked` 只建议不删内容) |
| `app/services/page_transcript_retriever.py` | 整页转写独立召回路 (2026-10-10, 语义权重 0.10 + `content_tsvector` 词法路 + rerank 后回钉) |

## 声纹 90% 硬门禁 (W75 第 1 批 B-1 三层口径澄清, A-2 W74 调研 §5 主拍)

> **铁律**: 0.7 / 0.55 / 90% **三层语义完全不同**, 历史 MEMORY 自报曾经把它们混写成同一个常量，导致假 "60 百分点差距". 必须在所有声纹相关讨论/代码/文档同时区分三层指标。

### 三层指标语义对齐 (C 方案文档口径修正, 必读)

| 指标 | 数值 | 语义 | 谁用 | 文件 |
|------|------|------|------|------|
| **单段 cosine distance 上限** | **0.65** | 在线 matcher 接受阈值 (越小越相似, `<MATCH_THRESHOLD>` 才返成员) | `app/services/voiceprint_service.py:27` (常量, **不动**) | 生产 |
| **跨会议单段命中阈值** | **0.55** | strict merge 验证: `cos_dist ≤ 0.55` 视为该段命中 | `docs/CLAUDE-history.md:5459-5464` | 历史 |
| **跨会议总体识别率门禁** | **90%** | 新 embedding/变更**前自动跑**跨会议回归, 加权识别率 ≥ 90% 才接受; < 90% 自动 rollback | B 方案 `voiceprint_cross_meeting_regression.py` 自动化 | W75 B-1 |

> ⚠️ **2026-10-13 订正 —— 本表第一行的数值曾漂移**: 实际常量是
> `**MATCH_THRESHOLD = 0.65`**（`voiceprint_service.py:27`，2026-09-07 由 0.7 收紧），
> 而本表、下方两条铁律、以及 `app/services/entity_link_recall.py:50` 的注释
> **长期都写着 0.7**（共 4 处）。⇒ **凡本文件再出现 `MATCH_THRESHOLD = 0.7` 的地方，
> 指的都是 2026-09-07 之前的旧值，现值是 0.65**。
> 铁律的**意图（别动这个阈值）依然有效**，只是数值不能再照抄。
> 这正是类 20.220 说的「配置注释也会骗人」—— 由 2026-10-13 的声纹准确率评估发现。

### 派工 v6 段 5 反馈 #6 实战: 拒绝方案 A 字面改 0.9

- **方案 A 字面改 0.9 错误**: 0.7（现 **0.65**，见上方订正）是 cosine **距离**上限, 把它改成 0.9 会让 matcher 更宽松 (接受更远/更差的匹配). 若目标是 confidence≥0.9, 应等价于 distance≤0.1 — 与 0.9 数值完全无关.
- **B 方案质量门必确定性**: 4 子门禁 (单段距离 / top1-top2 margin / cluster votes / anchor 状态) **必须确定性**, LLM 最多解释歧义, **不得**越过门禁. **0 production code 改动铁律守恒**: `MATCH_THRESHOLD` 保持不变（现值 **0.65**）。
- **王天志 #151 rollback 真实锚点**: 跨会议加权识别率 88.1% (#135 94.6% + #151 83.5%) < 90% → 自动 rollback sample_count 583→384. 历史锚点永久保留.

### W75 B-1 实施交付 (锚点范式第 253 守恒 +1)

| 模块 | 路径 | 作用 |
|------|------|------|
| 质量门 | `app/services/voiceprint_quality_gate.py` | 4 子门禁全部通过才确认成员, 任一失败 → rollback |
| 跨会议回归 | `app/services/voiceprint_cross_meeting_regression.py` | 12 会议音频 + #151 rollback 重演, 90% acceptance gate |
| 监控 | `app/services/voiceprint_quality_monitor.py` | Celery 30min schedule, 凑齐 6 件套监控 (W73 B-2 + W74 D-1 + W75 B-1) |
| 脚本 | `scripts/voiceprint/reprocess_12_meetings.py` + `replay_meeting_151.py` | 12 会议音频 reprocess + #151 rollback 重演 |
| E2E | `tests/test_voiceprint_quality_gate_e2e.py` | 13/13 PASS (8 子门禁各 2 + 综合 2 + 跨会议 90% 2 + 6 件套 1) |
| Runbook | `docs/voiceprint-quality-gate-2026-07-27.md` | B+C 方案完整 runbook |

### 5 条铁律 (W75 B-1 沉淀)

1. **不动 `MATCH_THRESHOLD`**（⚠️ 现值是 **0.65** 不是 0.7，见三层口径表上方的订正）— 派工 v6 段 5 反馈 #6 实战, 距离方向与 confidence 反向, 字面改 0.9 = 更宽松, 完全错误.
2. **B 方案质量门必确定性** — LLM 最多解释歧义, 不得越过门禁 (派工 v6 段 5 反馈 #6 实战: 拒绝 LLM 改数值).
3. **跨会议 90% acceptance gate 自动化** — 任一 embedding/变更**前自动跑** ≥90% 回归, 否则 rollback + 报警. 不靠人工执行.
4. **三层指标语义不可混写** — 0.7 (distance) / 0.55 (hit) / 90% (cross-meeting) 是不同维度, 任何文档/代码引用必分明.
5. **历史锚点永久保留** — 王天志 #151 rollback (88.1% < 90%) 案例是 acceptance gate 真实执行证据, 必须出现在所有 runbook 与文档.

## 2026-06-14 方案 C：Agent 单阶段流式渐进综合架构（plan: eager-juggling-dewdrop.md）

**6 个 stage 已收官**（commits `5ce1203` `8a76750` `9862546` `d3f74df` `59cbbb1` `2f2b619` `bf61456`）。核心改造：取消 brief/detail 双层 → 单阶段流式综合（intent → agentic_loop → critique → done）。

### 方案 C 6 条铁律（必读, 锚点范式永久锚点）

**铁律 1：跨 event loop 安全** — 所有外部 IO 客户端（AsyncAnthropic / aioredis / async_session）禁止模块顶部 import 阶段创建, 统一通过 `ctx: ToolContext` 注入 (`redis` / `llm` / `loop_id`). Celery worker 跨 event loop 调用时由调用方注入新 client, 否则触发 "Future attached to different loop".

**铁律 2：typing import CI 检查** — `app/agent/*.py` 新文件必跑 `bash scripts/check_typing_imports.sh` (106 文件 0 错误). 新代码用 `Dict`/`List`/`Optional` 但没 `from typing import ...` → 整个模块加载失败 → 工具一调就报. Docker 模块缓存会掩盖该 bug 数天.

**铁律 3：SSE 事件 delta 语义显式标注** — `app/agent/protocol.py` 每个 `StreamEventType` 必须在源码注释里标注 `[increment]` (前端 `content += delta`) 或 `[snapshot]` (前端 `content = delta` 替换). 混用会再现 brief 重复输出 bug (commit `cf70ff5`).

**铁律 4：流式 abort 安全** — `chat_engine.synthesize_stream()` 必须用 `async with TraceCollector(...) as trace` 包裹: `TraceCollector.__aexit__` 收到 `CancelledError` 时同步落库 (不走 Celery); `agentic_loop.run()` 在 `CancelledError`/`max_rounds` 时必调 `_sanitize_pending_tool_uses(messages, reason=...)` 给悬空 tool_use 追加 `tool_result: "用户已中断"` 哨兵, 否则下次拼回 context Anthropic API 报 400.

**铁律 5：LLMClient 接口 model 参数 keyword-only** — `async def complete(self, messages, *, model=None, system=None, ...)`, `*` 强制 keyword. 老代码传位置 model 必报 TypeError. LRU cache key 必须含 model 维度.

**铁律 6：feature flag 保留老路径代码** — ~~3 个 kill switch (2026-06-29 已全部删除, commit `817f1ffa` 提前 15 天收官, `git revert <commit>` 一行恢复)~~. 详见 `git log` 收官记录.

### 部署必做

```bash
# 1. 跑数据库迁移 (Stage 3 加 7 列)
docker exec microbubble-agent-db-1 psql -U postgres -d microbubble -f scripts/alter_agent_traces_stage3.sql
# 2. 重启 Python 进程 (**重启纪律**: 改完 app/ 代码必须重启, 否则容器仍跑旧代码。2026-10-09 起此处不再引用 CLAUDE.md 行号 —— 行号会随三层重排漂移, 纪律改内联自述)
docker compose restart app celery-worker
```

不跑这两步, 新架构写入 `intent_category` 等列会报 `column does not exist` 500.

#### 重建生产镜像的四条硬纪律（2026-10-13 实测，类 20.220 的四个变体）

**① `docker compose build` 必须串行, 禁止多服务并行**
4 个服务共用 `build: .`（app / celery-worker / celery-beat / celery-meeting-worker）。
一条 `docker compose build app celery-worker celery-beat celery-meeting-worker` 会走
**buildx bake 并行跑 4 个 apt 实例**，同时打 `deb.debian.org` 的 CDN ⇒ **稳定复现
`502 Bad Gateway`**，且**两次都挂在同一个包** `libdrm-nouveau2_2.4.114-1+b1`。
而单发 `docker run ... apt-get install libdrm-nouveau2` 同一包**秒装成功**
⇒ 纯**并发限流**，不是网络不通、不是代理坏、更不是 Dockerfile 写错。

正确写法（逐个来；共用 Dockerfile，第 2 个起会命中缓存，几分钟就完）：
```bash
docker compose build app
docker compose build celery-worker celery-beat celery-meeting-worker
```

**② 构建失败时 `exit code` 不可信 —— 判据必须是日志**
同一次失败，第一次 `docker compose build` 返回 **exit 0**、第二次 exit 1。
**只看退出码会把失败的构建当成成功的**，随后重建容器就会继续用**旧镜像**
（实测：镜像 ID 仍是旧值、体积未变、gcc 仍在、dev 包仍是 2 个）。
真实判据：
```bash
grep -c "ERROR:" <log>                      # >0 即失败
grep -c "did not complete successfully" <log> # >0 即失败
```
**③ `docker builder prune` 会连带清掉 apt 的 cache mount**
`Dockerfile` 里 apt 层用了 `--mount=type=cache,target=/var/cache/apt/archives`
—— 那些 `.deb` 平时躺在 **build cache** 里，prune 一次就得**全量重下 250 MB**，
把原本被缓存掩盖的源脆弱性顶了出来（本次就是这么撞上 ① 的 502）。
⇒ 清缓存前先想清楚代价；**生产出问题时不要顺手 prune**。

**④ 重建后必须在运行容器里验产物，不能只看 build 成功**
```bash
docker exec microbubble-agent-app-1 sh -c 'dpkg -l | grep -cE "\-dev[[:space:]]"; which gcc || echo "gcc 已移除"'
docker images --format "{{.Repository}} {{.ID}} {{.Size}}" | grep microbubble-agent-app
```
判据：**镜像 ID 变了** + 体积下降 + 关键包版本与基线一致 + 编译产物哨兵仍在
（本次是 `crcmod._crcfunext` —— 缺 gcc 时它会**静默降级**成纯 Python，
功能正常只是慢几个数量级，构建/CI/测试全绿都发现不了）。

### 方案 C 没做的（plan 明确范围外）

LangGraph 风格 state machine 重写 / 多 agent 独立服务 (planner/executor/critic) / 流式 ChartBlock 渐进渲染 / RAG 引用图谱可视化 / ASR/TTS 真流式. — **已于 2026-06-29 提前 15 天完成** (commit `817f1ffa`)（见上节"## 2026-06-29 chat_engine_legacy 30 天承诺提前 15 天收官"）


## W68 第 6+7 批纪律沉淀 (永久锚点)

> **锚点范式**: W68 第 6 批 (Verified Plans 深度审计发现) + W68 第 7 批 (grand closure 闭环) 的关键纪律固化到 CLAUDE.md. 不只在 memory 文件. 这是**永久任务模式纪律**, 未来会话启动读 CLAUDE.md 即可了解所有审计/闭环纪律.

### §1 plans 审计纪律 (W68 第 6 批 5 agent 深度审计发现)

W68 第 6 批派 5 个 Explore agent 并行全项目 plans 审计 (67 plans), 发现 5 类事故, 必须永久遵守:

1.1 **Status 段必须描述真实 commit, 不能借用同 wave 别的 plan commit** —
- **W66 批量状态化时挂错标签事故**: 状态化的 67 plans 中, 部分 Status 段描述直接复制同 wave 别的 plan commit, 而非自己 plan 真实实施的 commit. 后续审计发现多处 commit 和 plan 内容对不上 (commit 引用 `feat/xxx` 实际是别的 plan 派工分支).
- **纪律**: 每个 plan 的 Status 段必须独立验证 — `git log --all --grep="<plan-keyword>"` + `git show <commit-hash>` 必须能确认是本 plan 真实产物. 禁止批量复制粘贴

1.2 **必须读 plan 全文 + git show + grep -r 验证, 不能信 Status 段自报** —
- **盲信自报事故**: 多处 plan 的 Status 段写"已完成"但 `git log` 显示 plan 提到的功能实际从未落地. 例如 `15-17-18-cozy-bengio.md` Part 2 在 commit `4b215220` refactor 中意外删除, Status 段仍写"完成".
- **纪律**: 审计 plan 时必须 3 步并行:
  ```bash
  cat ~/.claude/plans/<plan>.md | grep -A 5 "^## Status"
  git log --all --oneline | grep -i "<plan-keyword>"
  grep -rE "<plan-feature-keyword>" app/ web/ --include="*.py" --include="*.vue" --include="*.ts"
  ```
  三者都对得上才是真实施, 缺一不可

1.3 **plans 命名应与实际内容一致 (60% 命名误导需整改)** —
- **真相**: W68 第 6 批审计发现约 60% plan 文件名与实际内容不匹配 (命名像 A 实际做 B). 命名误导 root cause 是 W62 前的"占位符命名 + 后写 plan"模式.
- **纪律**:
  - 写新 plan 时, 文件名 `xx-yy-zz-{2-词主题}-{1-词修饰}.md` 必须直接反映 plan 核心交付物
  - 不写"preparation"/"investigation"/"exploration"这类模糊词当主标题 (改用具体动作: `qa-bench-d6-benchmark-notebook.md` > `qa-bench-investigation.md`)
  - 模糊命名 plan 在 W68 第 6 批已批量重命名, 未来不允许再产生

1.4 **AGENT_STUB 必须真合并, 不能 MISCATEGORIZED** —
- **事故**: 多个 plan 状态化时被标 `AGENT_STUB` 但实际从未 merge, 仅是 plan 本身被审计 agent 阅读; 或反之, 实际已 merge 但状态标错. W68 第 6 批发现 6 个 `AGENT_STUB` 实际是 `COMPLETED` + 5 个 `COMPLETED` 实际是 `AGENT_STUB`.
- **纪律**: `AGENT_STUB` 含义精确化:
  - `AGENT_STUB` = plan 本身存在 + 没有对应的 agent 派工 + main HEAD 无相关 commit (即还没派工, 待派)
  - `COMPLETED` = plan 全部交付 + main HEAD 找到对应 commit + 实际代码落地
  - `MISCATEGORIZED` = 审计 agent 发现命名/状态与实际不符, 等待主指挥整改 (新状态)
  - 状态化必须 4 维度验证 (plan-file + git-log + grep-代码 + 审计单证), 不能仅凭 plan 内的 Status 自述

### §2 plans 实施闭环纪律 (W68 第 7 批)

W68 第 7 批 1 个 agent 收敛: 深度审计发现 5 个 NOT_IMPLEMENTED + 12 PARTIAL. 真实施 ≠ plan Status 段标 completed. 必须主指挥协调闭环.

2.1 **plans 优先 + 小修搭配 (W68 第 4 批主指挥拍板基调)** —
- **基调**: 派工以已有 plans 实施为主 + 更新过程中发现的小修为辅. 路线 A/B/C/D/E 任意组合, plans 优先 + 小修搭配, 不强制单一路线.
- **实战验证**: W68 第 4 批 (2 plan 闭环 + 13 小修) 与 W68 第 5 批 (全小修 + plans fallback) 双实战验证, 0 regression.
- **纪律**: 未来 4-9 阶段流程先 plans-list-remaining → 拍板 plan 实施 → 顺路小修 → 不强求 plans 100% (主指挥拍板决定节奏).

2.2 **plans 真实施 ≠ plans Status 段标 completed (审计出 5 个 NOT_IMPLEMENTED + 12 PARTIAL)** —
- **真相**: W68 第 6 批审计发现 67 plans 中 5 个标 completed 但实际未实施 (NOT_IMPLEMENTED) + 12 个标 completed 但仅实施 50% 以下 (PARTIAL). W68 第 7 批派 1 个 agent 100% 闭环整改 (git show + grep + commit 引用三验证).
- **纪律**:
  - Status 段标 `completed` 必须有 main HEAD commit 物证 (commit hash + 简述)
  - 部分实施标 `partial`, 不能凑 `completed`
  - 主指挥在 merge plan 实施 commit 后, 必须回头更新 plan Status 段 (闭环的核心)
  - W68 第 6+7 批沉淀的模式: **Plan 闭环 = 派 1 个 agent (A1) 重新审计全部 plans + 主指挥协调补 commit + 派 1 个 agent (A2) 写 verified plans 总报告**

2.3 **alembic 串单链纪律 (062→063→064→065, 066→067 等)** —
- 详见上方 §"2026-07-24 alembic 并行 agent 串单链纪律 (commit `1852468a6`)" 5 条铁律
- **W68 第 6+7 批新增案例**: Drive v2 PR10 (062) + Drive v2 PR11 (064) + Drive v2 PR12 (065) 串成单链 `061 → 062 → 064 → 065`; Mobile v3.2 push (066) + Drive comment mention (067) 串 `065 → 066 → 067`.
- **不变铁律**: 并行派 alembic migration agent 必须明确 down_revision 接续关系, merge 后立即 verify 只 1 个 head

2.4 **跨 session hot-fix 必须 commit message 含 "hotfix" 标识 + 主指挥 git log 跟踪** —
- **事故**: 多个 hot-fix 跨 session 派工, commit message 仅写"W68 第 5 批 hot-fix"但缺乏详细 traceback + root cause + 修复 3 段, 主指挥后续追溯困难.
- **纪律**:
  - hot-fix commit message 模板: `<type>(<scope>): W68-N-th-batch-hotfix-<short-desc> (<short-bug-id>)` + body 含 root cause 1 段 + 修复 1 段 + 验证 1 段
  - 主指挥每次 session 启动先 `git log --oneline -30 | grep -i hotfix` 跟踪上次 hot-fix chain
  - hot-fix 必须 commit 单做, 不与 feature 合并 (回滚粒度独立)

### §3 0 production code 改动铁律例外清单 (CLAUDE.md W67 第 41 步已记录 + 增补)

CLAUDE.md W67 第 41 步已记录基线: 锚点范式守卫 — 0 production code 改动 = `app/`、`web/src/`、`alembic/versions/` 老路径全部不动, 只允许 `docs/`、`memory/`、`scripts/`、`tests/` 新增. W68 第 6+7+8 批增补明确"什么算例外":

**Drive v2 系列 (PR6/PR7/PR8/PR9/PR10/PR11/PR12)** —
- 算例外: 新功能扩展 (网盘系统是 W67 后启动的新业务模块), 不破坏老任务/会议/知识库路径. 仅在 `app/services/drive_*` + `app/api/drive_*` + `web/src/views/drive/` + `web/src/views/mobile/drive/` 新增.

**Mobile UX 系列 (v3.0/v3.1/v3.2)** —
- 算例外: 移动端独立路由栈 (W66 启动), 与桌面端 component 树不共享, 不破坏老桌面路径. 仅在 `web/src/views/mobile/*` + `web/src/views/mobile/components/*` + `nut-*` 组件库新增.

**qa-bench 系列 (D1-D8 + Phase 1-3)** —
- 算例外: 测试目录, 不算业务代码. 仅在 `qa-bench/` (git submodule) + `tests/qa_bench/` 新增.

**alembic 迁移本身** —
- 算例外: 新功能必需的 schema 扩展, 不算破坏老路径. 但必须按 §2.3 串单链纪律进行, 不允许双 head.

**Plan 闭环实施 (W68 第 4 批已批)** —
- 算例外: 业务代码新增独立模块 (例如 15-17-18-cozy-bengio Part 2 重实施弥补 commit 4b215220 refactor 意外删除), 不动老路径, 仅新增 `app/services/新模块/` + 对应测试 + `docs/` + `memory/`.

**scripts/ 自动化脚本** —
- 算例外: `scripts/` 目录新增 (如 `scripts/purge_dup_owners.py`), 不算 production code.

**什么不算例外 (违规) — 明确禁止**:
- ❌ 修改 `app/services/task_service.py`/`meeting_service.py`/`knowledge_service.py` 等老模块的核心函数
- ❌ 修改 `web/src/views/Desktop*/index.vue` 老桌面页面组件
- ❌ 修改 `alembic/versions/0XX_老.py` 老迁移的 down_revision/up_revision
- ❌ 修改 `app/core/security.py`/`app/core/rate_limit.py` 老安全/限流基础设施
- ❌ 修改 `app/agent/chat_engine.py` 方案 C 6 条铁律相关文件

### §4 W68-W87 grand closure memory 索引 (永久)

完整 W68-W87 各 batch grand closure 沉淀文件索引见 `memory/MEMORY.md` §9 主题分类目录.


## 完整历史任务链

所有"## 2026-XX-XX" 历史任务链 / "### lesson learned" 子章节 / "## 开发注意事项（历史）" 段都已迁移到 [docs/CLAUDE-history.md](./docs/CLAUDE-history.md) (P3-15 拆分于 2026-07-08).

**为什么拆分**: CLAUDE.md 拆前 645KB (8082 行) 含 60+ 历史任务链, Claude 会话启动需全量 read, 减慢 system prompt 处理. 拆分后核心 ≈ 50KB, Claude 启动更快.

**Claude 行为**:
- 新会话默认只读 CLAUDE.md 核心 (50KB) — 不再加载历史 lesson
- 历史相关查询可主动 \`@ docs/CLAUDE-history.md\` 或 \`@<path>\` 引用
- 不破坏现有所有引用 (CLAUDE.md 顶部 "当前任务链" 块保留)

### 当前开发状态（2026-07-30 W97 RAG 大改造收口）

**RAG 大改造 10 PR 全部合并到 main + alembic 串单链 087→091 完整收口**：
- 087 → 088 (PR2) → 089 (PR3) → 090 (PR5) → 091 (PR8)
- main HEAD = `afe15911e` (MERGE-05 squash HOTFIX-01)
- 锚点范式 338 → 482 (+144 据实)
- 件 3 PWA build PASS（HOTFIX-01 PR5 Play → VideoPlay 修复）

**10 PR 一行摘要**：
- PR1 嵌入一致化 + query prefix 生效（has_query_prompt 前置修复）
- PR2 knowledge_chunk 子表 + parent-child chunking
- PR3 BM25 增量 + pg_trgm + tsvector
- PR4 HybridRetriever 召回侧量化（synonym 298 + 4 路权重可配）
- PR5 RAGEvaluator 真召回率激活（路径修正 web/src/views/admin/RAGEvalPanel.vue）
- PR6 SearchLog 前端接通（拒凑 5 commits）
- PR7 全链路 observability（grafana 7 面板 + 按路耗时分解）
- PR8 知识图谱深度联动（kg_entity + entity_link_recall）
- PR9 auto-research v2（dedup + query_rewriter）
- PR10 docs/deploy/eval 三件套沉淀（11 docs + 派工 v11）

**9 大缺口 100% 消化**：嵌入不一致 / 无 chunking / BM25 N 次重建 / PG 全文缺失 / query prefix 失效 / RAGEvaluator 零调用 / SearchLog 前端未通 / 无独立 RAG 评测 / 无 observability

**派工纪律沉淀（v10/v11 实战化）**：
- 派工前提铁律 12 条 + 类 20 实战 36 实例（历史 15 + W84 +3 + W85 +2 + W89 +14 + W97 +2）
- 件 4 双门控（件 4a 老核心 unchanged + 件 4b 派工 brief 授权，6 老核心服务 def diff 全 0 实战）
- 件 3 PWA 三档（frontend=是/否/子集，PR5 改路径实战，HOTFIX-01 修 Play 实战）
- 派工 v11 段 9 锚点前缀规则（防止并行 agent 撞号，6 个 W89 分支在途实战）
- 派工 v11 §13 仓库实情真查（5 子节 + 派生 5 铁律）

### 派工纪律 v12（2026-10-12 补 3 条，全部来自当日实战）

- **纪律 A（后台进程必须自己收尾）**：agent **返回报告前必须清理它自己启动的后台进程**
  （`docker exec -d`、pytest 长跑、`&` 起的脚本）。当日教训：某 agent 交完报告后，
  容器里**遗留 2 个跑 CPU 的 pytest**（`tests/rag/` 全量），既占资源又会跟后续测试
  **抢同一个测试库**（本项目已知坑：并发跑同库会互相 `DROP SCHEMA`）。
  **派工 prompt 必须写明"返回前清理自己启动的进程"**，并在交付报告里附清理证明。
  收尾自查用 `/proc/<pid>/cmdline` 遍历（容器内**无 `pgrep`**，`ps` 也常缺——
  静默返回 0 会让人误判成"进程没了"，见 2026-10-10 误判实录）。
  ⚠️ **自查时排除探测命令自己**：用 `bash -c "...pytest..."` 遍历时，探测命令的
  cmdline **自己就含 "pytest" 字样**，会被自己数进去 —— 实测因此差点误杀无辜 shell。
  必须 `[ "$pid" = "$$" ] && continue` 排除自身。
- **纪律 B（agent 的结论必须交叉验证后才入库）**：当日连续 3 次 agent 推翻主指挥判断，
  **每次都对** —— ①workflow 审计报告建议删 `image-scan`，执行 agent 交叉验证后推翻
  （有测试断言其存在 + 它是活跃治理项）；②主指挥派"补 `.trivyignore`"，agent 实测
  发现方向本身错（门禁带 `ignore-unfixed: true`）；③主指挥据 4 条证据判定 `datasets`
  可删并**已提交**，agent 用 import blocker 证伪（上游有未声明的硬 import）。
  ⇒ **纪律**: 主指挥给 agent 的"事实"若**来自上游 agent 的报告**，必须要求执行方
  **实测复现**而非转述；主指挥自己下判断前，若该判断会**删除/改动生产接线**，
  优先派一个**只做取证的 agent** 拿"可否证"的证据。
  **反向自省**: agent 推翻我 3 次 = 我这 3 次都只做了"看起来充分的静态取证"。
- **纪律 C（`docker exec -d` 必须重定向日志）**：后台启动的容器内命令若不重定向
  stdout/stderr，**出问题时既查不到进程也查不到输出**（当日两次因此误判进程已死）。
  标准写法: `docker exec -d ... sh -c '<cmd> > /tmp/x.log 2>&1'`。
  ⚠️ Git Bash 下 `docker exec` 的路径参数会被改写，需加 `MSYS_NO_PATHCONV=1`。
- 派工 v11 CHECKLIST §F verify_*.sh fallback 条款
- **派工 v10 段 7 E50 实战拦截**：WORKTREE-01 拦截"11 untracked"误判（实为 12 active worktree），0 rm -rf 0 损失
- **派工 v10 段 7 E48 锚点编号冲突 reconcile**：MERGE-05 squash 解决 GRAND-CLOSURE 477 vs HOTFIX-01 477 共占编号空间

**记忆锚点指向**：
- `C:\Users\pc\.claude\plans\rag-quirky-otter.md` v1.1（10 PR 路线 + 5 件套 + PR1 详设）
- `docs/w72-prompt-paradigm-v11-2027-04.md` 168 行（段 9/10/13 + DERIVE-19 reconcile）
- `docs/rag/CHECKLIST.md` 213 行（§F fallback + §H 仓库实情真查 + §J PR8）
- `docs/rag/W97-RAG-GRAND-CLOSURE.md` 208 行（CLAUDE.md 镜像）
- `memory/MEMORY.md` W97 RAG 大改造专题索引

Co-Authored-By: Claude Fable 5
