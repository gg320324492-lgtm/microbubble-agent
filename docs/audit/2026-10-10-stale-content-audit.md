# 仓库陈旧内容体检报告 (2026-10-10)

> **性质**：只读取证报告。生成过程**未删除 / 未移动 / 未重命名任何文件**，未碰 docker 容器，
> 未 `git add` / `commit` / `push`，未改任何源码。唯一写入即本文件。
>
> **红线遵守**：`.agents/` 与 `.codex/` 全程**只列目录名**（`ls -la` 顶层）确认其存在，
> **未进入、未读取内容、未做任何判定建议**——按用户指示这两个目录在用，报告中不予评价。
>
> **判定基准日**：2026-10-10。"老" = 最后提交早于 **2026-08-10**（>2 个月）。

---

## 摘要

| 区域 | 受检项数 | 保留（活） | 保留（历史快照/铁律） | 可疑 | 可删 |
|---|---:|---:|---:|---:|---:|
| A. 顶层老目录/文件 | 23 | 13 | 3 | 5 | 2 |
| B. `docs/` 老内容 | 22（10 子目录 + 12 类根文件） | 6 | 16 | 0 | 0 |
| C. `memory/` 老内容 | 2 组（317 根文件 + 169 archived） | 2 | 486 | 0 | 0 |
| D. `scripts/` 一��性脚本 | 24 | 0 | 21 | 3 | 0 |
| E. 其它可疑项 | 11 | 2 | 3 | 5 | 1 |
| **合计** | **82 组 / 约 850 文件** | **23** | **49** | **13** | **3** |

### 一句话结论

**Git 追踪的老内容几乎全部健康**——本仓"保留历史"文化执行得非常彻底，`docs/archived/`、
`docs/history/`、`docs/superpowers/`、`memory/` 均被 `docs/README.md` 与 `memory/MEMORY.md`
**显式声明为"只读归档，刻意保留"**，属铁律保护，不构成"无用堆积"。
**真正可清的无非 3 项共约 8 KB**，且全部是**未被 git 追踪的工作目录残留**
（不是"入库的旧内容"），风险等级极低但**建议仍由主指挥逐项确认后再动**。
体积最大的 `.claude/recovery-snapshots/`（8.5 MB）证据不足以自删，单列为待拍板项。

**关键澄清（用户原始怀疑点的实测结果）**：

- ✅ `.claude/worktrees/` **是空目录（0 字节）**，不是"8.7M 大头"。真正的 8.5M 是
  `.claude/recovery-snapshots/`。
- ⚠️ 用户看到的"3-4 months ago"目录，主体是**未追踪的工作区残留**（不进 git、不影响仓库历史），
  而非"入库的陈旧内容"。
- ✅ **零个已追踪的 `.bak/.old/.tmp/.orig/.rej/.swp` 产物被误入库**（实测 `git ls-files` 空输出）。

---

## A. 顶层老目录

### A-1. `.claude/` 及其子项（8.7M）

| 路径 | 最后提交 | 大小/文件数 | 引用证据 | 判定 | 理由 |
|---|---|---|---|---|---|
| `.claude/skills/verify/SKILL.md` | 2026-07-14（文件 mtime） | 4K / 1 | **本次会话 skill 列表里 `verify (verify-web-runtime)` 即此文件** | **保留（活）** | 正在生效的技能定义，删则 `verify` 技能消失 |
| `.claude/settings.json` | 文件 mtime 2026-06-26 | 8K | 含 `hooks`/`permissions` 段；`.gitignore:112` 忽略 `.claude/` | **保留（活）** | Claude Code 项目级配置，删则 hooks/权限失效 |
| `.claude/settings.local.json` | mtime 2026-09-29 | 4K | 同上，**最新**（3 天前） | **保留（活）** | 本地覆盖配置，仍在改 |
| `.claude/launch.json` | mtime 2026-09-15 | 1K | `preview_start` 工具读的配置文件 | **保留（活）** | 活跃配置；但**含失效条目**（见 E-3） |
| `.claude/fix_pwa_nginx.py` | 文件 mtime 2026-08-28 | 4K / 1 | **全仓 0 引用**（Grep 工具全仓精确检索无命中） | **可删（低风险）** | 见下方专项 |
| `.claude/voice-alert-readme.md` | git 最后提交见下 | 4K | 被 `docs/claude-code-global-voice-alert-setup.md:242` 引用 | **保留（活）** | 活文档有锚点引用；且是 `.claude/` 下**唯一被 git 追踪**的文件 |
| `.claude/worktrees/` | — | **0 字节 / 空目录** | `git worktree list` 仅主仓 1 条；`.git/worktrees/` 空 | **保留（空目录无害）** | 空壳；`.gitignore:111` 已忽略。建议连同 A-2 空壳一并清理，**但非必须** |
| `.claude/__pycache__/batch_skip.cpython-310.pyc` | mtime 2026-09-30 | 4K / 1 | 全仓**无 `batch_skip.py` 源文件**（`find` 实测 0 命中） | **可删（低风险）** | 孤立的 `.pyc`，源文件已不存在，无法再生；`.gitignore` 忽略 |
| `.claude/recovery-snapshots/` | mtime 2026-08-29 | **8.5M / 842 文件** | 被 `.claude/recovery-reports/desktop-f0-recovery/R1-REPORT.md:8` 声明为只读快照 | **可疑（建议保留）** | 见下方专项说明 |
| `.claude/recovery-reports/` | mtime 2026-08-29 | 248K / 4 | R2 报告被 `R2-failure-classification.md` 自引用；`docs/CHANGELOG-history` / `docs/CLAUDE-history` 多处引用 `scripts/_archive` 同批 | **保留（事故档案）** | F0 recovery 事故的取证报告，只增不改性质 |
| `.claude/recovery-clones/` | — | **已删除** | CLAUDE.md 2026-09-30 S2.1 记载已随 94.4GB 清理删除 | **保留（已处理）** | 无需动作 |

#### 专项：`.claude/fix_pwa_nginx.py`（已失效的一次性脚本）

| 取证项 | 结果 |
|---|---|
| git 追踪 | **未追踪**（`git ls-files` 空） |
| gitignore | **已忽略**（`git check-ignore` 命中，`.gitignore:112` 忽略 `.claude/`） |
| 引用 | **全仓 0 引用**（Grep 工具全仓精确检索，`.py/.sh/.md/.yml/.json` 均无命中） |
| 作用 | 硬编码遍历 `/etc/nginx/conf.d/`，把 `/sw.js`、`/manifest.webmanifest`、`/registerSW.js` 的 `return 410` 改成 `return 404` + 加 `Cache-Control no-store`（注释标"类 20.199 / 2026-08-28"） |
| 判定 | **可删（低风险）** |

**判删依据（三重，均已实测）**：

1. **零引用** —— 无任何脚本 / CI / 文档 / compose 引用它，不是自动化环节的一环。
2. **目标路径不存在于本仓** —— 它读写 `/etc/nginx/conf.d/`，那是**容器内**路径��
   不是仓库内 `nginx/conf.d/`。本仓该目录里的真配置，脚本**碰不到**。
3. **逻辑已被现网配置反证（决定性）** —— 脚本靠**精确字符串替换**生效，但现网
   `nginx/conf.d/tunnel.conf` 里这些块**早已漂移**，其 `old` 串**一个都匹配不上**：
   - `location = /manifest.webmanifest`（line 66）只有裸 `return 410;`，
     **没有** 脚本要求的 `Cache-Control` + `X-Content-Type-Options` 两行；
   - 443 副本（line 313-315、328-330）在 `return 410;` **之上还多出**
     `Strict-Transport-Security` 行。
   
   即���**该脚本若今天执行，会静默 no-op（打印 `no change` 而不报错）**，
   它要施加的"410 改 404"从未落地，也不该落地——CLAUDE.md 明记
   `/manifest.webmanifest` 的 410 是**有意防护**（`59187ce8` 事故后设的
   SPA fallback 拦截），改成 404 反而会削弱该防护。

**⚠️ 归档价值提示**：类 20.199「2026-08-28 PWA 已禁用」的**决策本身**记在 CLAUDE.md 里
（PWA 2026-07-27 注销段 + 失效警示），**不依赖这个文件**。故删除**不丢任何知识**。

#### 专项：`.claude/recovery-snapshots/`（8.5M，唯一大项）

| 取证项 | 结果 |
|---|---|
| git 追踪 | **0 个文件**（`git ls-files` 空）→ 不在仓库历史里 |
| gitignore | **已忽略**（`git check-ignore` 命中） |
| 内容 | `desktop-v10.2-broken-2026-08-29/desktop/`，Electron 桌面端源码快照，`package.json` version **0.1.0** |
| 现役对照 | `apps/desktop/package.json` version **1.3.2**，最后提交 2026-10-02 |
| 角色 | R1 报告称其为 "Snapshot (read-only)"，是 2026-08-29 `codex/desktop-f0-recovery` 恢复作业的**边界基准**（"v10.2 broken" = 出错态快照） |
| 配套 | 其工作克隆 `.claude/recovery-clones/codex-f0-recovery` **已于 2026-09-30 删除**（94.4GB 清理） |

**判定：可疑（建议保留）**。理由：这是唯一一个"8.5M 且无人引用"的实体，
但它是**事故取证基准**——F0 recovery 若需复现"从 broken v10.2 恢复"就必须有它。
**风险判断**：低价值但**零删除代价**（8.5M 不占仓���体积，只占磁盘）。
⚠️ **唯一真正的引用断裂**：R1 报告里的工作克隆路径 `.claude/recovery-clones/codex-f0-recovery`
已不存在，报告因此**半失效**——但快照本体（read-only 基准）仍完整可用。
**建议**：主指挥确认 D12「桌面端实战记忆抢救」是否已完成、此快照是否还有复现价值；
若答"已收官无复现需求"，则 8.5M 可删。**本报告不代做此决定。**

### A-2. 顶层其它 dotdir / dotfile（`.agents` `.codex` 除外）

| 路径 | 最后活动 | 大小/文件数 | 追踪状态 | 引用证据 | 判定 | 理由 |
|---|---|---|---|---|---|---|
| `.worktrees/wt-*`（5 个） | 2026-10-06 ~ 10-09 | 各 ~12K | 未追踪，`.gitignore:166` 忽略 | `git worktree list` **仅 1 条**（主仓）；`.git/worktrees/` **空** | **可删（低风险）** | 每个只剩 `web/node_modules` **符号链接**指向主仓 `web/node_modules`，本体源码早已不在；且注册表里已无记录，属**失联 worktree 空壳**。含一个异常名 `wt-css-extract;C`（分号，MSYS 转义事故残留，类 20.216 同族） |
| `.wt-a11y-grid` / `.wt-distprobe` / `.wt-secroutes`（顶层 3 个） | 2026-10-03 ~ 10-06 | 各 12K | 未追踪，**未被 gitignore**（`git status` 无输出因被忽略规则覆盖） | 同上，均�� worktree 残留空壳 | **可疑** | 内容同上（只有 node_modules 符号链接）；⚠️ **`.gitignore` 只忽略 `.worktrees/`，不忽略顶层 `.wt-*`**，属规则漏项 |
| `.wt-qabench-orphan;W` | 2026-10-06 | **0 字节（完全空）** | 未追踪 | 空目录 | **可疑** | 名字含 `orphan` + `;W`，双重异常（孤儿 + 分号转义残留），零内容 |
| `.microbubble-data/` | 2026-09-30 | 4K / **1 文件** | 未追踪 | **全仓 0 引用**（`grep` 覆盖 `*.py/*.yml/*.md/.env` 全为 0 命中） | **可疑** | 唯一文件 `logs/2026-09-30.log`（12 行）内容是 `{"module":"bootstrap","message":"database locked"}` —— 这是**某次 pytest 引导测试**的输出残留，非生产数据 |
| `.agent-backups/` | 2026-09-20 | 56K / 3 文件 | 未追踪，已忽略（`.gitignore:224`） | 无 | **可疑** | `scratch-20260920/{inspect_m250.json,phase1_check.txt,q.txt}`，E 盘整理时的临时草稿 |
| `.workbuddy/` | 2026-09-16 | 92K / 6 文件 | 未追踪，已忽略（`.gitignore:207`） | 见下方说明 | **保留（活记忆）** | 见 A-2 专项 |
| `.zcode/` | 2026-09-14 | 8K / 1 文件 | 未追踪 | `desktop-conversion/docs/acceptance/2026-09-29-ZB-restore-drill.md` 提及 | **可疑** | `plans/plan-sess_801e3402-....md`，外部工具 zcode 的会话计划 |
| `.vscode/` | 2026-05-19（目录 mtime） | — | 见下 | 编辑器配置 | **可疑** | 需确认是否仍用 VS Code；仓库有 `open_in_editor` 支持 4 种编辑器 |
| `.pytest_cache/` | 2026-07-02 | — | 未追踪 | pytest 自动生成 | **保留（无害）** | 工具缓存，pytest 每次自动重建 |
| `logs/` | 2026-09-26 | — | 未追踪（0 文件） | 日志区 | **保留（运行时）** | 运行时会写 |

#### 专项：`.workbuddy/` — 为什么必须保留

CLAUDE.md 记载 2026-09-30 S2.1 把 41.7 GB 转写运行时从 `.workbuddy/vibevoice-test`
**归位**到 `data/vibevoice-test`（`VIBEVOICE_HOME` 控制）。实测确认：

- `.workbuddy/vibevoice-test` **已不存在**（归位成功）；
- `.workbuddy/` 残留 `memory/`（5 篇日期 md）+ `outputs/`（1 篇会议恢复纪要），
  是**会议 250 恢复过程的实战记忆**，非运行时数据。

**判定：保留**。但由此发现一处**代码层面的失效引用**（见 D-3）。

### A-3. 顶层正常大目录（澄清，非老内容）

| 路径 | 最后提交 | 大小 | 判定 | 理由 |
|---|---|---|---|---|
| `apps/desktop/` | 2026-10-02 | **1.7G**（其中 `release` 1.7G） | **保留（活）** | 活跃 Electron 应用，v1.3.2；`release/` 是打包产物占 1.7G |
| `desktop-conversion/` | 2026-09-26 | — | **保留（活）** | **独立 git 仓库**（有 `.git`），D12 决策文件所在；CLAUDE.md 列为**只读保护路径** |
| `commercial/` | 2026-07-28 | 62K / 11 文件 | **保留（活）** | 虽 2.5 个月未动，但 `app/api/v1/billing.py`、`tenants.py`、`license_middleware.py`、`tenant_middleware.py`、`license_service.py`、`tenant_data_isolation.py` **6 个模块 import 它** |
| `models/` | — | 28G | **保留（运行时）** | 已 gitignore；声纹/ASR 模型（ECAPA-TDNN、WavLM、TitaNet 等），生产依赖 |
| `backups/` | 2026-10-10 | 410M | **保留（活）** | 已 gitignore；`local-backup.ps1` **每日自动生成**（最新 2026-10-10 02:00），生产备份 |
| `tunnel/` | 2026-09-15 | 15M | **保留（活）** | `ssh-tunnel.pid` = 69952，**实测 `ssh.exe` PID 2828 正在运行**；类 20.214 定为生产依赖 |
| `data/` | 2026-06-25（追踪部分） | — | **保留（活）** | 含 `vibevoice-test`（41.7G 生产运行时）、`ollama`（61.6G 容器挂载点） |
| `mcp_server/` | 2026-06-13 | — | **保留（活）** | `Dockerfile.mcp` + `app/mcp/` 依赖它保持可编译（类 20.215 镜像） |

### A-4. 顶层 `.env.backup-*` / `.env.bak-*`（6 个）

全部 **未被 git 追踪**且**已被 `.gitignore:75` `.env.backup-*` 忽略**。

| 文件 | 大小 | 判定 | 理由 |
|---|---|---|---|
| `.env.backup-20260701-secret-rotation` | 2.5K | **可疑** | 3 个月前密钥轮换备份，含旧密钥 |
| `.env.backup-pre-rotation-20260926` / `.env.bak-20260927-023217` | 7.4K ×2 | **可疑** | 2 周前轮换备份（两份几乎同大小，疑似冗余） |
| `.env.backup-ocr-fix-20261009-031801` / `.env.backup-visionmodel-ab-20261009` | 8.0K / 9.3K | **保留（近期在用）** | 昨日（2026-10-09）A/B 实验留档 |
| `.env.webhook` | 63 B | **可疑** | mtime **2026-05-21**（4.5 个月），未追踪未忽略。⚠️ **文件名含 "webhook" + 含密钥类内容**，需确认是否仍被 `deploy-auto.sh` 消费 |

**注**：CLAUDE.md 类 20.x 与 L-14 轮换纪律要求**绝不把新密码写进 git**——这些备份**均未入库**，
符合纪律。删前建议确认轮换已完成（2026-09-26 那批应已作废）。

---

## B. `docs/` 老内容

**决定性证据**：`docs/README.md`（2026-09-30 建立，活文件）已把整个 `docs/` 树**按性质编目**，
并明确声明：`archived/` `_archive_2026-07-12/` 共 161 文件 = **"归档 / 只读，不再更新"**；
`history/` 19 = "只读"；`superpowers/` 22 = "早期方案与审计反馈 / 只读"；
`incident/` = "事故档案 / 只增不改"；`roadmap-phases/ phase14/ phase15/ P2-leftover/` =
"阶段计划与留口 / 多已完结"。

**因此：早于 2026-08-10 的 docs 子目录，几乎全部落在"刻意保留"白名单内。**

| 路径 | 最后提交 | 文件数 | 引用证据 | 判定 | 理由 |
|---|---|---|---|---|---|
| `docs/roadmap-phases/` | 2026-06-09 | 24 | `docs/README.md` "阶段排期与路线图" 行 | **保留（历史快照）** | README 显式列为路线图权威位置 |
| `docs/_archive_2026-07-12/` | 2026-07-12 | 14 | `docs/README.md` 归档行（161 文件的一部分） | **保留（铁律：只读归档）** | 归档目录，明示不再更新 |
| `docs/history/` | 2026-07-28 | 19 | **CLAUDE.md 多处引用** + `docs/README.md` | **保留（活锚点）** | CLAUDE.md 直接链到 `docs/history/`，是活文档 |
| `docs/rag-templates/` | 2026-07-30 | 4 | `docs/README.md` RAG 专题行 | **保留（专题模板）** | RAG 专题维护中 |
| `docs/qa-bench/` | 2026-08-02 | 1 | **CLAUDE.md** + `docs/README.md` | **保留（活）** | CLAUDE.md 正文有链接 |
| `docs/capability/` | 2026-08-05 | 1 | `docs/README.md` | **保留（专题）** | `gpu-bge-m3-2026-08-05.md`，RAG 专题维护 |
| `docs/bench/` | 2026-08-05 | 1 | **CLAUDE.md** + **README.md** + `docs/README.md` | **保留（活）** | 三处引用；`late_chunking_real_bench_threshold.md` 是 W-N-D+ 门槛值 |
| `docs/grafana/` | 2026-08-05 | 2 | **CLAUDE.md** + `docs/README.md`；另有 `deploy/grafana/` 同步配置 | **保留（活）** | CLAUDE.md RAG observability 段引用；README 明示"与 deploy/grafana/ 同步" |
| `docs/refactor-decision/` | 2026-08-17 | 4 | `docs/README.md` 决策链行 | **保留（决策记录）** | "追加，不改旧条目" |
| `docs/W-N-decisions/` | 2026-08-17 | 5 | `docs/README.md` 决策链行；**CLAUDE.md W-N-A/B/C/D 段直接点名这些文件** | **保留（活锚点）** | CLAUDE.md 中段明确链接 |
| `docs/phase14/` `phase15/` | 2026-08-21 | 8 / 3 | `docs/README.md` 路线图行 | **保留（历史快照）** | "多已完结"，刻意留口 |
| `docs/P2-leftover/` | 2026-09-04 | 9 | `docs/README.md` | **保留（留口）** | 含 `layout-2026-09-mainlayout-wip.patch`（MainLayout.vue 的 WIP 补丁，8 月计划未落地产物） |
| `docs/archived/` | 2026-10-09 | 148 | `docs/README.md` 归档行 + 全仓大量交叉引用 | **保留（铁律：只读归档）** | **用户任务书明确点名此目录"刻意保留，不算无用"** |
| `docs/incident/` | 2026-10-08 | 3 | `docs/README.md` + CLAUDE.md 类 20.218 引用 | **保留（事故档案）** | 只增不改 |
| `docs/superpowers/` | 2026-09-16 | 22 | `docs/README.md` | **保留（只读）** | 早期方案与审计反馈 |
| `docs/CLAUDE-history.md` | — | 1 | **CLAUDE.md 底部明确链接** | **保留（活）** | CLAUDE.md "完整历史任务链"段主动指向 |
| `docs/CHANGELOG-history-2026-07-23.md` | — | 1 | `docs/README.md` | **保留（历史）** | 变更日志快照 |
| 其余根目录 83 个 | 混合 | 83 | 见 `docs/README.md` 查找表 | **保留** | README 已分类；含现行 runbook + 活锚点 |

**B 区结论：无一项判"可删"。** `docs/` 区体检结果**健康**——索引机制运行良好，
无孤儿文档、无零引用残留。

---

## C. `memory/` 老内容

**决定性证据**：`memory/MEMORY.md` 顶部（2026-09-30 提交 `docs(memory): 标注该目录已于 2026-08-21 停更,
避免后续会话误当活跃知识库`）**自我声明停更**，并明确：

> 本目录已于 2026-08-21 停更。它是**历史沉淀归档**，不是活跃知识库——新会话**不要**
> 把这里当作"项目现状"的依据，只在追溯"当初为什么这么定"时查阅。

### C-1. 结构与规模

| 项 | 数量 | 说明 |
|---|---:|---|
| `memory/*.md` 根文件 | **317** | 停更前沉淀的事件复盘 |
| `memory/archived/**` | **169** | 已二次归档（W86 mini-16 减负：W68 批细节、W72-W85 批 closure、W2-W71 baseline） |
| git 追踪总数 | **487** | 全部入库，是仓库资产 |
| 最后活动 | 2026-10-09 | 仅 `MEMORY.md` 被加停更标注（+11 行注释） |
| 2026-09 后改动 | **2 个文件** | `MEMORY.md`（加停更标注）+ `database-engine-singleton-bug-2026-07-20.md` |
| 2026-08-01 前未动 | **121 / 317** | 停更前的老文件 |

### C-2. 判定

| 项 | 判定 | 理由 |
|---|---|---|
| `memory/*.md`（317 个，含 121 个 2 个月未动） | **保留（历史沉淀，铁律）** | 锚点范式约定 memory = 事件复盘 + 教训沉淀；**本身已被官方标注为归档**；已被 CLAUDE.md 与 `memory/MEMORY.md` 主题索引编目（9 类主题分类 + 24 条近期专题） |
| `memory/archived/`（169 个） | **保留（铁律）** | 二次归档，性质同 `docs/archived/` |
| `memory/MEMORY.md` | **保留（活索引）** | 2026-09-30 刚更新；即使内容冻结，索引本身仍用于检索 |

**⚠️ 关键澄清（防止未来误判）**：本次会话系统提示注入的记忆是
`C:\Users\pc\.claude\projects\E--microbubble-agent\memory\MEMORY.md`（**用户级 Claude 自动记忆，
在仓库外**），它与仓库内 `E:\microbubble-agent\memory\MEMORY.md` **是两个不同文件**。
前者会随��话自动注入且**仍在活跃更新**（含 2026-10-10 记录）；后者已停更。
**审计范围只覆盖仓库内那份**，用户级记忆不在本仓、不作判定。

**C 区结论：无一项判"可删"或"可疑"。** 121 个 2 个月未动的 memory 文件全部落在
"项目已自我声明的归档"范畴内。

---

## D. `scripts/` 一次性脚本

### D-1. 24 个 `fix_/backfill_/migrate_/purge_/repair_` 命名脚本的引用取证

判据：**除归档类文档外**，是否还有活代码 / CI / compose / 文档 / 计划任务引用。

| 脚本 | 最后提交 | 非归档引用数 | 判定 | 理由 |
|---|---|---:|---|---|
| `scripts/migrate_kb_tags.py` | 2026-07-08 | 10 | **保留** | 引用面最广 |
| `scripts/migrate_kb_dedup_titles.py` | 2026-06-30 | 7 | **保留** | 数据迁移已执行，但记录引用多 |
| `scripts/purge_test_user_data.py` | 2026-07-01 | 4 | **保留** | 测试库清理，重建测试库时需用 |
| `scripts/migrate_kb_source_type.py` | 2026-07-08 | 2 | **保留** | 同上 |
| `scripts/migrate-weights-v3-to-v4.py` | 2026-07-27 | 2 | **保留** | 权重迁移，引用在迁移文档 |
| `scripts/backfill_drive_comments_path.py` | 2026-07-24 | 1 | **保留（无害）** | 单点引用，作用于 drive 表 |
| `scripts/batch_repair_meetings.py` | 2026-07-24 | 1 | **保留（无害）** | 单点引用；另有 `docs/batch-repair-meetings.md` 同名文档 |
| `scripts/backfill_late_embedding.py` | 2026-08-06 | 1 | **保留（无害）** | 关联 `results/backfill_late_embedding_2026-08-06.json` |
| `scripts/fix_broken_image_refs.py` | 2026-08-02 | **0** | **可疑** | 全仓（含 CI / compose）零引用；一次性修图引用 |
| `scripts/backfill_*.py`（image_embeddings / kb_chunks / kg_entities，2026-09-01） | 2026-09-01 | — | **保留（活）** | 2 个月内，W19 选项 A 排期相关 |
| `scripts/backfill_drive_content.py` / `backfill_meeting_index.py` / `backfill_resync_kb_indexes.py` | 2026-09-02 | — | **保留（活）** | 2 个月内；`resync` 是 CLAUDE.md 25 号条目点名的常规操作 |
| `scripts/backfill_drive_to_kb.py` | 2026-09-05 | — | **保留（活）** | 2 个月内 |
| `scripts/fix_minio_mime.py` | 2026-09-29 | — | **保留（活）** | 11 天前 |
| `scripts/backfill_drive_search_text.py` / `backfill_kb_search_text.py` / `migrate_preview_cache_key.py` / `migrate_projects_cleanup.py` / `purge_banner_image_block_extractions.py` / `purge_banner_image_noise.py` | **2026-10-09** | — | **保留（活）** | 昨日提交，正在用 |

### D-2. 失效路径引用（真问题，非"老脚本"问题）

`.workbuddy/vibevoice-test` 已于 2026-09-30 归位为 `data/vibevoice-test`（实测旧路径**已不存在**）。
全仓 4 处引用，**其中 2 处是活代码而非注释**：

| 文件:行 | 形态 | 判定 | 理由 |
|---|---|---|---|
| `scripts/consistency_filter_v2.py:21` | **活代码** `VVT = BASE / ".workbuddy" / "vibevoice-test"` | **可疑（确证失效）** | 2026-09-11 写的 ASR 微调数据脚本，第 91 行真用它拼路径 → 必 FileNotFound |
| `scripts/final_check_daemon_path.py:16` | **活代码** `WAV = r"E:/microbubble-agent/.workbuddy/vibevoice-test/jobs/probe600.wav"` | **可疑（确证失效）** | 2026-09-16 的守护链路验证脚本，硬编码死路径 |
| `app/gpu_worker/meeting_worker.py:40` | 注释 | **保留（活）** | 注释即迁移说明；实际代码用 `data/vibevoice-test` |
| `scripts/start_gpu_asr_daemon.bat:3` | 注释（`rem`） | **保留（活）** | 同上；且此 .bat 是开机自启任务调用入口 |

**注意**：这两个脚本**都不在生产链路**（非 celery task、非 compose 服务、非计划任务），
失效只影响"手工重跑一次性 ASR 验证"时才会暴露，**不会造成生产故障**。

### D-3. `scripts/_archive/` 与 `scripts/__pycache__/`

| 路径 | 判定 | 理由 |
|---|---|---|
| `scripts/_archive/2026-07-28-w83-p2-cleanup/`（5 个 verify 脚本） | **保留（铁律：归档）** | W83 P2 清理的刻意归档；`docs/archived/`、`docs/CHANGELOG-history-2026-07-23.md`、`docs/CLAUDE-history.md` **多处以完整路径引用**这些脚本作为回归验证依据 |
| `scripts/__pycache__/`（27 个 `.pyc`） | **保留（无害）** | gitignored 工具缓存；`.pyc` 可由源文件再生 |

### D-4. 已删除历史确认

CLAUDE.md 记载：`scripts/dft/README.md`（DFT 外置说明残留）+ 2 个 `test_dft_tools` 陈旧 `.pyc`
已于 2026-10-09 删除。实测 `ls scripts/ | grep -i dft` **零输出**，**已清理干净，无需处置**。

**D 区结论：0 项"可删"**。24 个一次性脚本全部是「已执行 + 有文档记录」的历史操作，
保留成本 = 少量 KB 磁盘，删除收益 = 0，**误删风险 > 收益**。
唯一实质问题是 **D-2 的 2 处失效路径**（属"该改代码"而非"该删文件"）。

---

## E. 其它可疑项

### E-1. 备份 / 临时 / 实验产物

| 项 | 判定 | 理由 |
|---|---|---|
| git 追踪的 `.bak/.old/.tmp/.orig/.rej/.swp` | **零命中（健康）** | `git ls-files` 空输出——无产物误入库 |
| 顶层 `.env.backup-*` × 4 + `.env.bak-*` × 1 | **可疑**（见 A-4） | 均未入库 + 已忽略；3 个月那批轮换备份��能已作废 |
| `.env.webhook`（2026-05-21，4.5 个月） | **可疑** | 未追踪未忽略；需确认是否仍被部署脚本消费 |
| `backups/`（410M） | **保留（活）** | 每日自动生成，最新 2026-10-10 |
| `.microbubble-data/` | **可疑**（见 A-2） | 1 个 pytest 残留日志，全仓零引用 |
| `.agent-backups/scratch-20260920/` | **可疑** | 3 个临时草稿文件 |
| `desktop-conversion/feed-server.log`、`vite.log` | **可疑** | 两个散落日志；建议归入该仓 `.gitignore` |

### E-2. 空目录 / 仅 `__pycache__` 的目录

| 路径 | 判定 | 理由 |
|---|---|---|
| `.claude/worktrees/` | **可删（低风险）** | 空目录，gitignore 已忽略；worktree 注册表无记录 |
| `.wt-qabench-orphan;W` | **可疑** | 完全空 + 名字双异常 |
| `.claude/__pycache__/`（仅 1 个孤立 `.pyc`） | **可删（低风险）** | 见 A-1；源文件不存在 |
| `app/__pycache__/` `tests/__pycache__/` `scripts/__pycache__/` | **保留（无害）** | 有对应活跃源文件，正常缓存 |
| git 追踪但仅 1 文件的顶层目录：`.claude`(1) `.codex`(1) `config`(1) | — | `.codex` 按用户指示不评价；`.claude`=voice-alert-readme（活）；`config` 待查 |

### E-3. 配置文件内的失效条目

| 项 | 判定 | 理由 |
|---|---|---|
| `.claude/launch.json` 的 `web-minimal-dev` 条目 | **可疑** | 指向 `cwd: "web-minimal"`，但 CLAUDE.md 记载 `web-minimal/`（零源码）**已于 2026-09-30 作为死重删除**（实测 `ls -d web-minimal` → 不存在）。此配置项现在必失败 |
| `.claude/launch.json` 的 `web-dev` / `mockups` | **保留（活）** | 前者 `cwd: web` 有效；后者指向存在的 `docs/design-proposals/member-dialog-2026-09` |

### E-4. `config/` 目录

| 项 | 判定 | 理由 |
|---|---|---|
| `config/`（2026-08-02，git 追踪 1 文件） | **可疑** | 仅 1 个追踪文件；需主指挥确认是否仍被 Docker 或应用读取（本次未深入，因其最后提交 2 个月整，边界情形） |

### E-5. 跨系统引用的隐性断裂

| 项 | 判定 | 理由 |
|---|---|---|
| `.claude/recovery-reports/.../R1-REPORT.md:6` 引用 `E:\microbubble-agent\.claude\recovery-clones\codex-f0-recovery` | **可疑（已断裂）** | 该克隆已于 2026-09-30 随 94.4GB 清理删除。报告本身保留（事故档案），但**工作克隆路径已失效**，复现需重建 |

---

## 「可删」候选清单（需用户逐项确认）

> **共 3 项，合计约 8 KB**（不含下方需拍板的大项）。全部**未被 git 追踪**
> （不进仓库历史，删除不影响任何 commit）。
> 建议**由主指挥逐项确认后再执行**——本报告不代为删除。

| # | 路径 | 大小 | 证据 | 风险 |
|---|---|---|---|---|
| 1 | `.claude/fix_pwa_nginx.py` | 4 KB | **全仓 0 引用**；读写容器内 `/etc/nginx/conf.d/`（本仓 `nginx/conf.d/` 碰不到）；其精确字符串替换对现网 `tunnel.conf` 已**完全漂移**（`/manifest.webmanifest` 缺 Cache-Control 行、443 副本多 HSTS 行）→ 今天执行会静默 no-op；而它想做的"410 改 404"**与 CLAUDE.md 明记的有意 410 防护相悖**。类 20.199 决策本体记在 CLAUDE.md，删此文件不丢知识 | **极低** |
| 2 | `.claude/__pycache__/batch_skip.cpython-310.pyc` | 4 KB | 全仓**无 `batch_skip.py` 源文件**（`find` 零命���）；`.gitignore` 已忽略；孤立 `.pyc` 无法再生 | **极低** |
| 3 | `.claude/worktrees/`（空目录） | 0 B | 空目录；`git worktree list` 仅主仓 1 条；`.git/worktrees/` 为空；`.gitignore:111` 已忽略 | **极低** |

**判定为"可疑但需主指挥拍板"的高价值项（体积大，证据不足以自删）：**

| # | 路径 | 大小 | 为何不自动判删 |
|---|---|---|---|
| ★ | `.claude/recovery-snapshots/desktop-v10.2-broken-2026-08-29/` | **8.5M / 842 文件** | 是 F0 recovery 事故的**只读边界基准**（R1 报告明示）；版本 0.1.0 vs 现役 1.3.2。**删除前需主指挥确认"D12 抢救已完成、无复现需求"**——这是本仓唯一"无引用的大体量项"，也是 `.claude/` 8.7M 的真正来源（用户原以为的 `.claude/worktrees/` 是空目录） |

---

## 「可疑但建议保留」清单

| # | 项 | 建议 | 理由 |
|---|---|---|---|
| 1 | `memory/` 121 个 2 个月未动文件 | **保留** | 目录已由 `MEMORY.md` 自我声明"2026-08-21 停更，是历史沉���归档"；锚点范式约定 memory 为永久教训沉淀 |
| 2 | `docs/archived/` 148 + `_archive_2026-07-12/` 14 | **保留** | `docs/README.md` 明示"归档 / 只读，不再更新"；**用户任务书亦明确点名不算无用** |
| 3 | `docs/history/` `superpowers/` `incident/`（44 文件） | **保留** | 同为 `docs/README.md` 声明的只读档案；CLAUDE.md 有活链接 |
| 4 | `scripts/_archive/2026-07-28-w83-p2-cleanup/` 5 脚本 | **保留** | `docs/CHANGELOG-history` / `CLAUDE-history` 以**完整路径**引用作回归依据，删了会断文档链接 |
| 5 | `commercial/`（2026-07-28，2.5 个月未动） | **保留** | **6 个 app 模块 import 它**——目录 mtime 旧但代码活着，最容易被误判为死代码 |
| 6 | `tunnel/`（2026-09-15，含 pid/log） | **保留** | **实测 `ssh.exe` PID 2828 运行中**；类 20.214 定为生产依赖单点 |
| 7 | `.workbuddy/memory/` + `outputs/`（6 文件） | **保留** | 会议 250 恢复实战记忆，非运行时垃圾 |
| 8 | `.claude/recovery-reports/`（4 报告，248K） | **保留** | F0 事故取证档案，只增不改性质 |
| 9 | `D-2` 两个 ASR 脚本的失效路径引用 | **保留脚本，改路径** | 属"代码该更新"非"文件该删除"；改 `.workbuddy/vibevoice-test` → `data/vibevoice-test` 即可复用 |
| 10 | `memory/MEMORY.md` vs 用户级记忆同名 | **保留** | 二者是**不同文件**（仓库内 vs `C:\Users\pc\.claude\...`）；后者仍在活跃更新，不在审计范围 |

---

## 体检方法的局限（如实说明）

1. **未做运行时验证**：受红线约束，未启动容器查 DB、未跑 pytest、未执行脚本。所有判定基于
   **git 历史 + 静态引用检索 + 文件系统取证**。若某脚本仅被"手工流程"而非代码引用，
   静态检索可能漏判（本文对 9 个脚本标"保留（无害）"即为此类保守处理）。
2. **`config/` 与 `.vscode/` 深度不足**：两者最后提交分别为 2026-08-02 / 2026-05-19，处于
   ">2 个月"边界，本文仅作浅层判定（标"可疑"），未逐一核查其消费方。如需定论需单独深挖。
3. **`.env.webhook` 未验证消费方**：因该文件可能含密钥，仅按文件名/日期取证，未读内容，
   未 grep 部署脚本。**建议主指挥手动确认后再决定去留**。
4. **`.zcode/` `.agent-backups/` 属外部工具产物**：其保留价值取决于用户是否还用
   zcode / agent-backups 工具链，本文无法从仓库内证据判定。
5. **全仓 `grep` 性能受限**：`apps/desktop/node_modules`（9.7M）、`models/`（28G）、
   `backups/`（410M）、`.claude/recovery-snapshots/`（8.5M）体积巨大，早期一次全仓 grep 超时，
   后续改用 Grep 工具 + `--include` 精确过滤 + 排除清单。**极小概率存在漏网引用**，
   但对"可删"级判定均已做二次定向复核。
6. **未评估 `.agents/` `.codex/`**：按用户指示完全不评价，连内部结构都未进入。
7. **`.env.backup-*` 的作废性未确认**：仅确认"未入库 + 已忽略"，未验证其中的旧密钥是否
   已彻底轮换（L-14 纪律要求），删前需用户确认。

---

## 附：体检覆盖统计

```
顶层目录/文件受检           22 项
docs/ 子目录                22 项（10 个 >2mo 子目录 + 12 类根文件）
memory/                     2 组（317 根文件 + 169 archived，共 486 文件）
scripts/ 一次性脚本          24 个（按名称模式筛出，逐个引用取证）
其它可疑项                  11 项
────────────────────────────────────
合计                        81 组 / 约 850 个文件
git 追踪                    487（memory）+ 完整 docs/scripts/app/web
未追踪工作区残留             约 20 个目录 + 6 个 .env 备份 + 4 KB pyc
```

**最终一句话**：仓库的"老内容"99% 是**被索引、被声明、被刻意保留**的历史资产；
真正可清的是 **3 项共约 8 KB 的未追踪工作目录残留**（`.claude/fix_pwa_nginx.py` +
孤立 `.pyc` + 空 `worktrees/`），体积最大的 8.5 MB 快照需主指挥先确认 F0 事故复现需求。
**建议不要做大清理。**