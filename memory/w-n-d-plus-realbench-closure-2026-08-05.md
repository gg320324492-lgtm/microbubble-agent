# W-N-D+ 真 bench 收口 (2026-08-05)

> 派工: GPU + bge-m3 能力验证 + late chunking 真 bench 准备.
> 实际交付: 能力验证 ✅ + **真 bench 真跑** (brief 原以为跑不了) + 触发条件留口.
> 锚点: W-N-D+ +0 起步 / +1 capability / +2 真 bench + 触发条件 / +3 收口 (本文件).

## 1. 交付物

| 锚点 | commit | 文件 |
|------|--------|------|
| W-N-D+ +0 | `ea30a694e` | `memory/w-n-d-plus-realbench-startup-2026-08-05.md` |
| W-N-D+ +1 | `41ab080a1` | `docs/capability/gpu-bge-m3-2026-08-05.md` |
| W-N-D+ +2 | `7387978e7` | `scripts/run_late_chunking_realbench.py` + 2 个 `results/*.json` |
| W-N-D+ +2 | `025bb505c` | `docs/bench/late_chunking_real_bench_threshold.md` |
| W-N-D+ +3 | (本文件) | `memory/w-n-d-plus-realbench-closure-2026-08-05.md` |

## 2. 核心结果

**late chunking 相比 parent 单向量, 召回确有增益** — 首次拿到真信号 (此前只有 mock).

| context | chunk_win | 胜率 | delta_mean | delta_p50 | delta_min |
|---------|-----------|------|-----------|-----------|-----------|
| `max_length=8192` | 17/20 | **85%** | +0.0540 | +0.0503 | −0.0357 |
| `max_length=32768` | 17/20 | **85%** | +0.0408 | +0.0434 | −0.0684 |

两组 context 长度胜率完全一致 → 结论不是某个截断长度的偶然产物.

配置: `Qwen/Qwen3-Embedding-0.6B` (生产默认) on RTX 5090, 4 篇真实长文档 × 5 条真实 query.

encode 开销: late chunking 与 parent **同量级** (32k: 1116ms vs 1068ms) — 因只 forward 一次,
滑窗 mean-pool 纯 numpy 后处理. 即增益近乎免费 (代价在存储: 每文档 N 个 1024d 向量).

## 3. 5 件套守恒实测

| # | 件 | 实测 | 结果 |
|---|----|------|------|
| 1 | alembic 1 head | `['104_add_knowledge_chunk_late_embedding']` | ✅ 守恒 (未动 alembic) |
| 2 | pytest | `tests/unit/test_late_chunking.py` + `tests/integration/test_late_chunking_recall.py` → **4 passed** | ✅ |
| 3 | PWA build | 本任务 0 frontend 改动 | ✅ 不涉及 (件 3 三档之"否") |
| 4 | 0 production code | 我的 4 个 commit `git show --stat` 全部只落 `memory/` `docs/` `scripts/` `results/` | ✅ 守恒 |
| 5 | 锚点范式 | W-N-D+ +0/+1/+2/+2/+3 = 5 commits (含收口) | ✅ 据实 |

件 4 详证 — 我的 commit 未触碰 `app/` `web/src/` `alembic/versions/` `docker-compose.yml`.
(注: `git diff 1409ee67d..HEAD -- app/` **非空**, 但那 3 个文件
`cold_hot_router.py` / `embedding_service.py` / `knowledge_service.py`
来自**并行 agent W-N-E/W-N-F**, 不是我的改动 — 逐 commit `--stat` 已隔离确认.)

## 4. 派工 brief 偏差据实上报 (4 处)

### 4.1 base HEAD 不符 (非错配)

brief 声明 `fb4343f29`, 实测 main HEAD = `1409ee67d`. `fb4343f29` 是其 parent —
brief 写就后主拍加了 `W-N-GC +1` (纯 CLAUDE.md docs). 与本任务范畴无交集 →
**在 `1409ee67d` 上继续, 不 reset** (回退会丢主拍收口文档).

### 4.2 工作目录在会话中被清空 (类 20.31 变体, 新增实战)

启动 cwd = worktree `bold-mendeleev-fdc0e8`. 会话开始数分钟内:
`git log` 仍正常返回 (git 元数据在), 但 `ls alembic app docs` 全部 No such file,
`ls -la <worktree>/` 只剩 `.` 和 `..`, 且该 worktree **已从 `git worktree list` 移除**.

推测被并行的 W-N-ARC (worktree 归档) 任务回收 —
main 里确有 `710549f96 docs(memory): W-N-ARC worktree 归档收口沉淀 (worktree + branch 永久删除)`.

处理: 主仓库 `E:\microbubble-agent` 完好 (工作区仅 1 个他人 untracked memory),
直接在主仓库工作, 不重建 worktree (本任务只新增文件, 无冲突风险).

**沉淀**: 会话中途 cwd 消失时, `git log` 可能仍成功 (元数据滞留) —
**不能**以 `git log` 成功推断工作目录健在, 必须 `ls` 实体文件.

### 4.3 "本机无 GPU" 前提被推翻 (最关键)

brief 写 "不真跑模型 (本机无 GPU)" 并给二分支:
GPU 可用 → 真 bench; GPU 不可用 → 留未来派工.

实测: **GPU 可用** (RTX 5090 32GB, 容器内 `torch.cuda.is_available()=True`),
但 brief 指定的 `bge-m3` **未缓存且禁止下载** → 落在二分支**之间**.

按 brief 字面走会误判为"留未来派工", 白白浪费一台可用 RTX 5090.
据实决策: 换用**已缓存且是生产默认**的 Qwen3 跑真 bench, bge-m3 触发条件另文留口.

换模型的正当性: 同 1024d / 同 `token_embeddings` 接口 / 零下载 /
**且 bench 结论直接适用生产** (Qwen3 是 `EMBEDDING_MODEL_NAME` 默认值,
bge-m3 只是尚未启用的灰度候选).

### 4.4 "hybrid_retriever 接入 (mock model)" 表述不准

brief 称 W-N-D 已落地 "late_chunking_service.py + hybrid_retriever 接入 (mock model)".
实测: `hybrid_retriever._chunk_late_recall()` 走的是**真 pgvector SQL**, 不是 mock;
mock 只存在于 `scripts/bench_late_chunking.py` 的 `MockModel`. 两者不是一回事.

## 5. 实测发现 3 处 (技术, 已写入 commit message)

1. **bfloat16 不能直转 numpy**: Qwen3 以 bf16 推理, `.cpu().numpy()` 抛
   `TypeError: Got unsupported ScalarType BFloat16` → 必须 `.float()` 再转.
   `_GpuModelAdapter` 与 `encode_parent` 两处都需要.

2. **`--n-docs 5` 实际只取到 4 篇**: DB 中 `length(content) >= 8000` 的 knowledge
   恰好只有 4 条 (实测 `SELECT count(*)` = 4), **非脚本 bug**. 据实报 4, 不合成文档凑 5.

3. **8192 组 `chunk_count` 全为 37 是截断信号**: 经算术验证 37 正是 8192 token 的满窗数
   (`chunk_size=256, overlap=32 → step=224`), 即 4 篇文档 (59K~134K 字符) **全被截断**,
   只编码了开头. → 补跑 32768 组交叉验证: `chunk_count` 变为 147/75/82/72 (随文档长度),
   证实未截断, 胜率仍 85%.

   **沉淀**: bench 里若某个"计数"指标在差异极大的输入上**恒为同一值**, 优先怀疑
   触到了上限/截断, 而不是巧合. 算一遍理论满值即可证伪.

## 6. 一处操作瑕疵 (据实)

commit `41ab080a1` 除我的 capability 报告外, 意外带入并行 agent (W-N-F) 的 2 个 memory 文件
(`w-n-f-lora-finetune-{startup,closure}-2026-08-05.md`). 原因: 我 `git add` 时只指定了自己的路径,
但**索引中已存在他人 staged 的内容** (并行 agent 在同一主仓库工作), `git commit` 连带提交.

影响评估: 内容本身正确且属 W-N-F 真实产物, 已推送, **无数据损失**, 未覆盖任何东西.
后续 commit 已改为 `git diff --cached --name-only` 先验证再提交.

**沉淀**: 多 agent 共享同一主仓库时, `git commit` 前必须 `git diff --cached --name-only`
核对暂存区, 不能假设"我只 add 了我的文件"就等于"只提交我的文件".

## 7. 未做 (铁律守恒)

- ❌ 未下载 bge-m3 (2.7GB, brief 严禁) — 全程只用已缓存模型
- ❌ 未改 `app/services/embedding_service.py` (W-N-C 已改, brief 严禁再改)
- ❌ 未改 `docker-compose.yml` / `app/main.py` / plan 文件 / W-N-A/B/C/D commits
- ❌ 未改 prod 配置 (`EMBEDDING_BACKEND` / `EMBEDDING_MODEL_NAME`)
- ❌ 未跑生产部署 — 仅 `docker exec` 只读 + `docker cp` 脚本 (未 restart 任何容器)
- ❌ 未动 alembic (1 head `104` 守恒)
- ❌ 未动他人 untracked memory 文件

## 8. 真 bench 触发条件 (下一步)

详见 `docs/bench/late_chunking_real_bench_threshold.md`. 摘要:

| 留口 | 阻塞条件 |
|------|---------|
| bge-m3 对照组 | 需主拍批准 2.7GB 下载 (**硬门禁**) |
| 显著性检验 | 需长文档 ≥20 篇 (放宽 `--min-chars 3000` 可得 50 篇) |
| 端到端 recall@k | 需 `knowledge_chunks.late_embedding` (alembic 104) **回填数据** |
| late chunking 上生产 | 需独立派工: 本 bench + 端到端 recall + 回填成本 + 存储开销 |

## 9. 类 20 实战沉淀 (3 条)

- **cwd 可在会话中途消失**: `git log` 成功 ≠ 工作目录健在 (git 元数据滞留),
  必须 `ls` 实体文件确认; 主仓库通常完好, 可直接切过去 (§4.2)
- **多 agent 共享主仓库时暂存区会串**: `git commit` 前必须
  `git diff --cached --name-only` 核对, 不能假设 `git add <我的文件>` 就够 (§6)
- **bench 计数指标恒定 = 截断信号**: 差异极大的输入产出同一计数时,
  先算理论满值证伪, 别当巧合 (§5.3)
