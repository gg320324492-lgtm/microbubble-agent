# 全项目结构调研报告 · 2026-09-30

> 范围：`E:\microbubble-agent` 全量遍历（顶层 33 个目录、约 24 万文件）＋代码/文档/物理三层审计
> 方法：3 个并行只读探查 agent（后端 `app/` / 前端+桌面端 / 文档体系）＋ 总指挥亲自复核所有关键断言
> 结论一句话：**代码分层不需要推倒重来，但有 3 处真实断裂必须先处理；真正失序的是物理布局——24 万文件里 99.96% 不是代码。**

---

## 零、先说结论

你问"是否有必要对全项目做层级整理、重新完整规划"。**我的答案是：要做，但不是"重新规划"，而是"补三处断裂 + 清一轮物理布局"。**

理由分三层：

| 层 | 判定 | 依据 |
|---|---|---|
| **代码分层** | **不需要重组** | 12 万行、snake_case 全覆盖、`FIXME`/`HACK` 各 **0** 处、Alembic **单 head 无冲突**、命名一致——这是一套被认真维护过的代码 |
| **测试闸门** | **有真实断裂，必须修** | 全量 `tests/` 451 个 py 从未被任何 CI 跑过；已实证存在红了 2 个月的文件 |
| **物理布局** | **严重失序，需要一轮清理** | 24 万文件 / ~240 GB，其中真实源码约 0.04%；同一模型三格式四份共 ~139 GB |
| **文档体系** | **需要一次收口** | 8 套"记忆"材料、5 处互斥陈述、最权威文档自身携带与代码相反的事实 |

**不建议做的事**：不要为了"看起来整齐"去重排 `app/` 的目录树。12 万行代码的目录结构是历史沉淀的真实映射，大动会带来无法预估的回归风险，而收益接近零。

---

## 一、必须先处理的三件事（按紧急度）

### 🔴 P0-1 `desktop-conversion/` 无远端，全部历史只存在一块磁盘

**总指挥已复核**：
```
git remote -v  →  （空）
commits = 126    工单 = 44    验收记录 = 61
```

桌面端项目从 09-16 到今天的**全部工程记忆**——126 次提交、44 张工单、61 份独立验收记录——**没有远端、没有镜像、只存在于本机 E 盘**。主仓有 GitHub 兜底，这里没有。

这是全项目**唯一一个"丢了就永久没了"的资产**。而它的内容恰恰是最难重建的：为什么当初判定 `is_team_shared` 是死字段、为什么备份必须走 `visibility='private'` 而不是它字段、Zb-1 为什么"代码对但目标没达成"——这些决策链只存在于那 61 份验收记录里。

**行动**：`git remote add` + 首次 push。10 分钟的事，风险为零。

### 🔴 P0-2 服务端全量测试无 CI 闸门，已实证长期红灯

**总指挥已复核并亲自跑出红灯**：

```
$ pytest tests/test_drive_v2_pr3_comment_v2_e2e.py
12 failed, 22 passed        ← 红了 2 个月
```

该文件最后改动 **2026-07-27**（commit `e06009d30 feat(w72-2nd-batch-b2)`），内容是对一个**已消失的临时代理 worktree** 做 `assert os.path.exists(...)`（`tests/test_drive_v2_pr3_comment_v2_e2e.py:88-91` 指向 `.claude/worktrees/agent-w72-2-b2-pr3comment/`）。

**为什么没人发现**——CI 实际闸门范围（已逐个 workflow 复核）：

| workflow | 触发 | 实际跑什么 |
|---|---|---|
| `rag-framework-ci.yml:62` | push/PR main | `pytest tests/rag_framework/` —— **仅此一个子集** |
| `qa-bench-ci.yml` | `app/**` push + 每周六 | LLM 质量基准（qa-bench），**不是单元测试** |
| `desktop-release.yml` | tag | 只跑 `apps/desktop`（782 条） |

**451 个服务端测试文件，没有任何 workflow 跑过全量。** 唯一的常驻自动化门是桌面端。

**附带发现**：`qa-bench-ci.yml` 里写明它被收窄到"每周六心跳 + 服务器侧 paths"，理由是 *"2026-09-29 …1000 条全量 ~2 小时/次，攒 20 次就烧穿 2000 分钟/月私有仓额度"* —— **但仓库 09-29 已转 Public，这个额度墙已不存在**，收窄的前提消失了。

### 🟡 P0-3 物理布局：约 95 GB 可回收，另有 41 GB 藏错位置

**总指挥逐项复核了"是否还被引用"，两次修正了初判**：

| 目录 | 体量 | 判定 | 证据 |
|---|---|---|---|
| `llama-cpp-tools/qwen3-14b-f16.gguf` | **52.1 GB** | 🗑️ **死** | `Qwen3-14B`/`qwen3-14b`/`.gguf` 在全仓 py/yml/ps1/ts 中**零引用** |
| `models/Qwen3-14B-FP16/` | **28.2 GB** | 🗑️ **死** | compose 只挂载 `models/{hf_cache,modelscope,torch_hub}` 三个子目录，**不含它** |
| `.ollama/` | **13.8 GB** | 🗑️ **死** | ollama 容器实际挂载 `data/ollama`；两处存在**字节相同的 blob**（同 sha256，8.64 GB） |
| `.claude/recovery-clones/` | 1.26 GB | 🗑️ 残留 | 09-29 filter-repo 历史重写后的恢复克隆 |
| `web-minimal/` | 1.6 MB | 🗑️ **死** | 只有 `dist/`，**零源码**、零 git 跟踪、最后写入 2026-06-05 |
| **小计** | **≈ 95.4 GB** | | |
| `.workbuddy/vibevoice-test/` | 41.7 GB | ⚠️ **活的** | 见下 |
| `data/ollama/` | 61.6 GB | ✅ 活的 | ollama 容器挂载点 |
| `models/hf_cache` | 22.7 GB | ✅ 活的 | 被 **5 个容器**挂载 |

**这里有个必须点名的架构问题**：`vibevoice-test` 41.7 GB **不是废弃实验，是生产组件**——`app/gpu_worker/meeting_worker.py:41-43`、`streaming_server.py:29,39-40`、`server.py:53` **把绝对路径硬编码进生产代码**；`app/config.py:120-122` 与 `app/services/post_meeting_tasks.py:148` 让**会议转写优先走这条链路**；`scripts/register-gpu-asr-daemon-task.ps1:14` 注册开机自启。

也就是说：**41.7 GB 的模型权重与两个 venv（3.7 GB）躲在一个叫 `.workbuddy` 的隐藏 agent 工具目录里，被生产代码硬依赖。** 新人遍历项目时根本不会发现它，而删掉它会议转写立刻崩。这是全项目最隐蔽的单点。

**磁盘现状**：C 盘仅剩 **38.8 GB**，D 盘 1238 GB、E 盘 2629 GB 空闲。清理应优先做，但**不必恐慌**——项目主体在 E 盘，不构成 C 盘压力。

---

## 二、代码层审计

### 2.1 后端 `app/`（51 路由 / 205 service / 12 万行）

**健康的部分**（这些是"不要动"的依据）：
- 分层主干完整，依赖方向大体正确
- `FIXME` **0**、`HACK` **0**、`待实现` **0**；`TODO` 32 / `XXX` 36 集中在 task 线与 agent tools，抽样多为提示词文本与状态字面量，**是活跃开发的正常标记，不是积压债务**
- 文件名 **snake_case 100% 覆盖**，无驼峰无连字符
- **Alembic 单 head = `141_zb2_backup_kb_purge`**，112 个 revision 无重复 ID，两处分叉均已 merge，缺号是功能删除留下的空洞（`017_voice_embedding_192dim.py` 有注释解释跳过了 016）

**真实的渗漏**：
- `api/v1/knowledge.py`（1,413 行）内含 **61 处 ORM 调用** + 直接 `db.add/commit/delete` —— 持久化逻辑下沉到 API 层
- `api/v1/drive_files.py`（**3,423 行**）一个文件装下 49 路由 + **35 个内联 `BaseModel`**；`schemas/` 整个层只有 1,888 行
- `services/hybrid_retriever.py` 反向 import `app.rag`/`app.agent` **11 处** —— 循环依赖温床
- `services/drive_service.py`（2,527 行）单类 **49 个方法**

**明确的重复**：分片上传 **4 件并存** —— `chunked_upload_service.py`(240) / `drive_chunked_upload_service.py`(352) / `generic_chunked_upload_service.py`(194) / `drive_chunked_upload_tasks.py`(29)。

**测试空白**：`voiceprint_voting.py`(895 行) 与 `post_meeting_tasks.py`(1,025 行) **零测试覆盖**；`tests/api/` 仅 2 个文件对应 52 个 API 模块。

### 2.2 前端 `web/` / 桌面端 `apps/desktop/`

**边界其实很清晰**——这点常被误判：
- `pnpm-workspace.yaml` 只圈 `apps/*` + `packages/*`；`web/` 用自己的 `package-lock.json`（npm 而非 pnpm），是**刻意的双包管理隔离**
- 桌面端与 `web/` **零耦合**：跨端搜索 4 处命中**全是注释**，无一行真实 import
- 桌面端 `out/`、`release/` gitignore 完整

**唯一的产物边界破损**：`.gitignore:78` 明确忽略 `web/dist/`，但 `git ls-files web/dist` 返回 **365 个文件**——历史 `git add -f` 遗留，且至今仍随功能提交更新。

**`packages/design-tokens` 的"共享"只对了一半**：桌面端 `main.ts:2` 确实 `import '@mb/design-tokens/variables.css'`，但 **`web/` 零引用**。两份 `variables.css` 当前 MD5 完全相同（零漂移），但**双份可写且无 CI 守卫**——web 侧一改就漂移。

**复杂度热点**（与布局问题独立）：`paperAdapter.js` **5,205 行**、`ChatViewSSE.vue` 2,840、`DriveDetailRail.vue` 2,100。

**注**：`router/index.js` 只有 29 条 path 而 `views/` 有 70 个 vue——因 `utils/resolveMobile.js:22-24` 用 `import.meta.glob` 做桌面/移动双栈，**不是死代码**，但路由表确实看不出全貌。

### 2.3 文档与"记忆"体系

**8 套材料、约 600 文件、5 处互斥陈述**（均为总指挥或 agent 实测）：

1. **AI 栈三个"当前"答案**：`AGENTS.md:15`「Claude + mimo-v2.5」／ `README.md:37`「mimo-v2.6-flash 现役」／ `CLAUDE.md:171`「qwen3.8:27b」
2. **最权威文档自身与代码相反**：`CLAUDE.md:937` 与 `:1176` 称嵌入模型为 `text2vec-base-chinese`，而**代码真值** `app/services/embedding_service.py:32` 是 `Qwen/Qwen3-Embedding-0.6B`。`docs/superpowers/plans/2026-08-05-pgvector-optimization.md:46-47` 早在 08-05 就判定该描述过时并给了替换文案——**指令存在，但从没落到 CLAUDE.md**
3. **`memory/MEMORY.md` 自相矛盾**：`:1` 说 163、`:12` 说 158、`:16` 说 225，三个数字互斥（实测 487 tracked）
4. **门禁基线过期 178 条**：`.workbuddy-ai/memory/MEMORY.md:35` 写「604 条全绿」，实际已 782
5. **部署拓扑互斥**：`AGENTS.md:16`「Docker 8 services」／ `handoff.md:12`「15 个容器」

**`CLAUDE.md` 的结构问题**：1,416 行里有 **25 个 `## 当前状态`** 倒序堆叠、全部自称"当前"；真正长期有效的铁律埋在第 903–1194 行——**读者要先读完约 900 行事故日志才能看到规则**。且 `:476` 与 `:485` 标题逐字重复。

**`AGENTS.md` 废弃未完成**：已标 DEPRECATED 且 README 已不再列出，但 `docs/meeting-minutes-standard.md:87` 是**现行流程规则**，仍要求 agent 去更新它——会把未来的改动引去改一个冻结文件。

**`memory/`（487 文件）已停更 40 天**（最后提交 2026-08-21），README 仍在宣传。

**一个反直觉但重要的点**：`.workbuddy-ai/` 已被仓库自己判定为"工具残留"并 gitignore，但**它保存着唯一一份实战踩坑记录**——`MEMORY.md:6-8`「判断 API 真伪的手法：返回 HTML 就是 SPA 回退，返回 401/JSON 才是真 API」，这类内容在 session-log 里完全没有。**它该被废弃，但必须先抢救内容。**

---

## 三、建议的行动顺序

### 第 0 步（今天，10 分钟，最高优先）
```bash
cd E:\microbubble-agent\desktop-conversion
git remote add origin <你的仓库地址>
git push -u origin main
```
无风险、零副作用，**却消除唯一的"永久丢失"风险**。

### 第 1 步（本周，不改代码）
1. **删死重**：`llama-cpp-tools/qwen3-14b-f16.gguf`(52.1G) + `models/Qwen3-14B-FP16/`(28.2G) + `.ollama/`(13.8G) + `web-minimal/` + `.claude/recovery-clones/` → **回收约 95 GB**
2. **修 CI 盲区**：给 `rag-framework-ci.yml` 增加一个 `tests/` 全量 job（可先 `continue-on-error` 收集基线红灯清单，再逐步转硬门）；删掉那个红了 2 个月的文件或让它对准真实路径
3. **修 `web/dist` 边界**：`git rm -r --cached web/dist`（365 个产物不再入库，`.gitignore:78` 才真正生效）

### 第 2 步（需要决策，我不擅动）
4. **`vibevoice-test` 归位**：把 41.7 GB 从 `.workbuddy/` 迁到 `models/vibevoice/`，`app/gpu_worker/` 的硬编码路径改为读环境变量（有现成 `GPU_ASR_TMP` 模式可循）。**这消除"生产依赖藏在隐藏工具目录"的最大隐患**
5. **文档收口**：`desktop-conversion` 建远端后，把 `AGENTS.md` / `memory/` / `.workbuddy-ai/` 三者收敛为 `CLAUDE.md` + `docs/` 两层；抢救 `.workbuddy-ai` 的三条实战事实进 `DECISIONS.md`
6. **解 qa-bench 节流**：仓库已 Public，2000 分钟/月额度墙不再存在，撤掉"每周六心跳"收窄

### 明确**不建议**做
- ❌ 不要重排 `app/` 目录树——收益近零、回归风险不可控
- ❌ 不要为了"统一"把 `web/` 塞进 pnpm workspace——当前隔离是刻意的且有效
- ❌ 不要在 P0/P1 完成前动 `drive_files.py` / `drive_service.py` 的拆分——那是有真实回归风险的手术，等测试闸门修好再谈

---

## 四、本次调研的自我修正记录

为便于后续核验，记录我在调研过程中**被证据推翻的三次判断**：

| # | 初判 | 修正后 | 推翻它的证据 |
|---|---|---|---|
| 1 | VibeVoice 是废弃实验，可删 41.7 GB | **是生产组件，不可删** | `app/gpu_worker/meeting_worker.py:41-43` 等 6 处硬编码路径；`post_meeting_tasks.py:148` 优先走该链路 |
| 2 | `DECISIONS.md` 是 GBK 编码 | **UTF-8 无 BOM**，是我的读取器假象 | 前 3 字节 `23 20 E6`；PowerShell 5.1 默认 ANSI(cp936) 读取致乱码 |
| 3 | "CI 里没有任何 pytest" | 有 3 个 workflow 含 pytest，但**只 gate 了 `tests/rag_framework/` 一个子集** | `rag-framework-ci.yml:62` `pytest tests/rag_framework/` |

另外我先前报的 "`tests/` 1376 文件"是**所有文件**口径；实际 `.py` 为 **451 个**，顶层还有约 30 个疑似 QA 工单产物目录（`a11y_login_x18`、`axe_violation_x19` 等）混在其中。

---

## 五、待你裁决的点

1. **P0-1 的远端放哪**——GitHub 私有仓？本地 NAS？还是就接受单盘风险？（这是本报告唯一的"不可逆风险"项）
2. **第 1 步的 95 GB 删除是否照做**——技术判定已完成且证据充分，但删的是你机器上的真实文件
3. **是否现在就动 `vibevoice-test` 归位**——它涉及改生产代码的路径解析，建议排在 CI 闸门修好之后
