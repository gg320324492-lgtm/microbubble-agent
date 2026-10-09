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

## 当前状态 (2026-09-30 阶段收尾全面收口 — CI 硬门转正 / 94GB 死重清零 / 41GB 生产依赖归位 / 远端补齐)

**服务端全量测试首次有真闸门 (S1.2 完成)**:
- `server-tests-baseline.yml` 8 片 matrix 跑 3112 用例；基线 **829 条红灯经 R1-R6 六轮
  收敛归零**（最终 passed 2926 / failed 0 / errors 0 / skipped 186），已摘
  `continue-on-error` —— 任一片失败即阻塞合并。**此前 451 个测试文件从未有任何
  workflow 跑过全量**（RAG-FW CI 只跑 `tests/rag_framework/` 一个子集）。
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
> 覆盖类 20.155–219，共 29 条。

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
- **类 20.214**: 生产依赖的裸进程单点 (ssh.exe 反向隧道) 必须有判活守护 + runbook;
  隧道 -R 端口与容器发布端口的对应关系 (9000↔minio) 必须文档化, 否则换端口/重建即静默断线。

- **类 20.215**: 注释实验块必须**逐字段圈界** — app 的 `deploy/mem_limit` 实验连带把
  `healthcheck` 和 `restart: unless-stopped` 一起注释掉, 事故潜伏整个 8 月。生产服务 compose
  里 `restart` 策略缺失 = 重启必断; 每次改 compose 后跑 `docker compose config` 并
  `docker inspect -f '{{.HostConfig.RestartPolicy.Name}}'` 抽验核心容器。
- **类 20.216**: 用脚本/ps1/heredoc 写 schtasks `/TR` 或任何含反斜杠路径时, `\r` `\n` `\t`
  会被转义吞成控制字符 (本次 2 个任务路径腐坏: `scripts\tunnel`→`scripts< TAB>unnel`、
  `dft-service\run`→`dft-service<CR>un`), 任务永远 exit 1 且**日志一行不写** (进程根本没启动)。
  注册后必须 `Get-ScheduledTask | % Actions[0].Execute` 回读比对长度 + 无控制字符。
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
- **遗留 (主拍待决)**: `MicroBubble-Auto-Recovery` 事件任务 (Winlogon 7002) LastRunTime 停在
  8/4, 本次重启未触发 (类 20.143 宣称的自愈实际失能)。
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
- **glitchtip 遗留已失效, 待复核**: 原记 "glitchtip + vision-mcp 重启前即 unhealthy;
  `2ab45943b910_`/`737c1a285543_` 前缀两个老改名容器与 `microbubble-agent-glitchtip-1`
  Exited 4 周残留并存" —— 2026-10-09 实测 `docker ps -a` 全量 15 个容器, **这三个容器均已不存在**
  (既非 Exited 也非残留, 是彻底没了)。故该条描述已过时, 但**是否要重建 glitchtip 服务属产品决策,
  待主拍**, 此处只更正事实、不擅自处置。


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
  规模：`tests/` 下 **381 个测试文件 / 3782 个 test 函数**；CI 硬门 `server-tests-baseline.yml`
  8 片实跑 **3112 用例**（2926 passed / 186 skipped）
  - ⚠️ **87 个测试文件已归档**（模块级 `pytest.skip`）—— 断言历史 commit / 已下线功能 /
    一次性验收 gate / 需真环境。**恢复流程与分类清单见 [`tests/ARCHIVED.md`](tests/ARCHIVED.md)**。
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

## 声纹 90% 硬门禁 (W75 第 1 批 B-1 三层口径澄清, A-2 W74 调研 §5 主拍)

> **铁律**: 0.7 / 0.55 / 90% **三层语义完全不同**, 历史 MEMORY 自报曾经把它们混写成同一个常量，导致假 "60 百分点差距". 必须在所有声纹相关讨论/代码/文档同时区分三层指标。

### 三层指标语义对齐 (C 方案文档口径修正, 必读)

| 指标 | 数值 | 语义 | 谁用 | 文件 |
|------|------|------|------|------|
| **单段 cosine distance 上限** | **0.7** | 在线 matcher 接受阈值 (越小越相似, `<MATCH_THRESHOLD>` 才返成员) | `app/services/voiceprint_service.py:26` (常量, **不动**) | 生产 |
| **跨会议单段命中阈值** | **0.55** | strict merge 验证: `cos_dist ≤ 0.55` 视为该段命中 | `docs/CLAUDE-history.md:5459-5464` | 历史 |
| **跨会议总体识别率门禁** | **90%** | 新 embedding/变更**前自动跑**跨会议回归, 加权识别率 ≥ 90% 才接受; < 90% 自动 rollback | B 方案 `voiceprint_cross_meeting_regression.py` 自动化 | W75 B-1 |

### 派工 v6 段 5 反馈 #6 实战: 拒绝方案 A 字面改 0.9

- **方案 A 字面改 0.9 错误**: 0.7 是 cosine **距离**上限, 把它改成 0.9 会让 matcher 更宽松 (接受更远/更差的匹配). 若目标是 confidence≥0.9, 应等价于 distance≤0.1 — 与 0.9 数值完全无关.
- **B 方案质量门必确定性**: 4 子门禁 (单段距离 / top1-top2 margin / cluster votes / anchor 状态) **必须确定性**, LLM 最多解释歧义, **不得**越过门禁. **0 production code 改动铁律守恒**: `MATCH_THRESHOLD = 0.7` 保持不变.
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

1. **不动 `MATCH_THRESHOLD = 0.7`** — 派工 v6 段 5 反馈 #6 实战, 距离方向与 confidence 反向, 字面改 0.9 = 更宽松, 完全错误.
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
