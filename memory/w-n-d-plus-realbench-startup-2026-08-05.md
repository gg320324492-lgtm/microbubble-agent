# W-N-D+ 真 bench 准备起步 (2026-08-05)

> 派工: W-N-D+ 阶段 D 真接入准备 agent — GPU + bge-m3 能力验证 + late chunking 真 bench 准备.
> 范畴严格限定: 1 个 capability 报告 + 1 个 bench 脚本 + memory. 0 production code 改.

## 6 项起步 (W73 铁律)

### 1. base ref 实测 (派工 v4.1 §0.1, 类 20.46/20.32)

**派工 brief 声明**: `main HEAD = fb4343f29`

**实测 (2 处偏差, 据实上报)**:

| 项 | 派工 brief | 实测 | 处理 |
|----|-----------|------|------|
| main HEAD | `fb4343f29` | `1409ee67d` | brief 之后主拍又加了 1 个 commit (`W-N-GC +1` CLAUDE.md plan 状态同步, 纯 docs) — `fb4343f29` 是其 parent, 不是错配, 是 brief 写就后的正常前进 |
| 工作目录 | worktree `bold-mendeleev-fdc0e8` | **目录被清空 + 从 `git worktree list` 移除** | 见下方第 2 项 |

```
1409ee67d docs(claudemd): W-N-GC +1 pgvector 优化 plan 收口状态同步
fb4343f29 docs(memory): W-N-D late chunking 起步 + 收口沉淀   ← 派工 brief 的 base
740aafbde fix(rag): W-N-D 收口 (hybrid_retriever 接入 + alembic 串单链)
39866b375 feat(rag): late chunking 服务 + 104 迁移 + 多向量召回 (W-N-D cherry-pick)
```

`1409ee67d` 只动 CLAUDE.md, 与本任务范畴 (capability 报告 + bench 脚本) 无交集 → **在 `1409ee67d` 上继续, 不 reset 到 `fb4343f29`** (回退会丢主拍的收口文档).

### 2. 工作目录异常 (类 20.31 变体, 本任务新增实战)

启动 cwd = `E:\microbubble-agent\.claude\worktrees\bold-mendeleev-fdc0e8`. 会话开始数分钟内:

- `git log` / `git rev-parse HEAD` **仍正常返回** `fb4343f29` (git 元数据尚在)
- 但 `ls alembic app docs memory scripts` **全部 No such file or directory**
- `ls -la <worktree>/` → 只有 `.` 和 `..` (**空目录**)
- `git worktree list` → **该 worktree 已不在列表中**

即该 worktree 在会话进行中被外部清理 (推测: 另一 agent 或 `EnterWorktree` 生命周期回收). 主仓库 `E:\microbubble-agent` **完好无损**:

- `git status --short` → 仅 1 个 untracked (`memory/w-n-arc-worktree-archive-startup-2026-08-05.md`, 他人产物, **不动**)
- `app/services/late_chunking_service.py` 存在
- `alembic/versions/104_add_knowledge_chunk_late_embedding.py` 存在
- plan 文件 `docs/superpowers/plans/2026-08-05-pgvector-optimization.md` 存在 (64077 bytes)

**决定**: 直接在主仓库 `E:\microbubble-agent` 工作, 不重建 worktree (本任务仅新增 2 文件 + memory, 主仓库工作区干净, 无冲突风险).

### 3. W-N-D 已落地物证 (真查, 不信 brief 自述)

派工 brief 称 "late_chunking_service.py + hybrid_retriever 接入 (mock model)". 实测 `git show --stat`:

| 文件 | commit | 状态 |
|------|--------|------|
| `app/services/late_chunking_service.py` | `39866b375` | ✓ 65 行, 依赖注入 model (仅需 `.tokenizer` + `.forward`) |
| `alembic/versions/104_add_knowledge_chunk_late_embedding.py` | `39866b375` + `740aafbde` | ✓ down_revision 修正为 `099_add_dft_jobs` |
| `scripts/bench_late_chunking.py` | `39866b375` | ✓ 52 行, **MockModel 全 1 向量** |
| `results/late_chunking_bench_2026-08.json` | `39866b375` | ✓ `"mock": true` |
| `app/services/hybrid_retriever.py` `_chunk_late_recall()` | `740aafbde` | ✓ 38 行, best-effort 降级 |
| `tests/unit/test_late_chunking.py` (2) + `tests/integration/test_late_chunking_recall.py` | `39866b375` | ✓ |

现有 bench 的 mock 是**全 1 向量** (`np.ones((1,n,1024))`) → 所有 chunk 向量恒等 → `chunk_late_score` 恒为 1024.0 → **不含任何检索信号**. 这正是真 bench 要替换的部分.

### 4. alembic 1 head 守恒 (起步基线)

```
104_add_knowledge_chunk_late_embedding (head)
```
单链: 098 → 100 → 101 → 102 → 103 → 099 → 104. 本任务**不动 alembic**.

### 5. GPU 实测 (派工 brief 前提被推翻, 据实上报)

**派工 brief 前提**: "不真跑模型 (本机无 GPU)".

**实测**: 本机 **有 GPU 且容器内可用** —

- `nvidia-smi` → NVIDIA GeForce RTX 5090, 32607MiB, driver 610.74, CUDA UMD 13.3, 8318MiB 已用 (~24GB 空闲)
- `docker exec microbubble-agent-app-1 python -c "torch.cuda.is_available()"` → **True** (torch 2.13.0+cu130, device_name RTX 5090)
- `celery-worker` 容器同样 True (类 20.149 GPU pass-through 已生效)

→ brief 的 "本机无 GPU" 分支不成立. 但**不因此擅自扩范围**: 仍严守 "不改 prod 配置 / 不 pull 2.7GB 模型" 两条禁令.

### 6. 模型可用性实测 (决定真 bench 是否可跑)

HF 缓存 (`/root/.cache/huggingface/hub`) 实测:

| 模型 | 缓存 | 用途 |
|------|------|------|
| `Qwen/Qwen3-Embedding-0.6B` | ✓ **已缓存** | **生产默认** (`EMBEDDING_MODEL_NAME` 默认值) |
| `BAAI/bge-reranker-v2-m3` | ✓ 已缓存 | reranker, **非** embedding |
| `BAAI/bge-m3` | ✗ **未缓存** | 灰度候选 (`BGEM3Backend`), 需下载 2.7GB |
| `shibing624/text2vec-base-chinese` | ✓ 已缓存 | 老模型 |
| `cross-encoder/ms-marco-MiniLM-L-6-v2` | ✓ 已缓存 | reranker |
| `Systran/faster-whisper-large-v3` | ✓ 已缓存 | ASR |

`sentence_transformers 5.6.0` + `transformers 5.14.1`.

**关键能力实测** (用已缓存的 Qwen3, 零下载):

```
load_sec: 8.1
has_tokenizer: True
max_seq_length: 32768
dim: 1024
forward_keys: ['attention_mask', 'input_ids', 'sentence_embedding', 'token_embeddings']
token_embeddings_shape: (1, 281, 1024)
```

→ SentenceTransformer 在 GPU 上产出 `token_embeddings`, **正是 `LateChunkingService.encode()` 所需的接口** (`model.tokenizer` + `model.forward()` → `token_embeddings` + `attention_mask`). late chunking 真 bench 在**不下载 bge-m3** 的前提下即可跑通.

## 决策 (据实, 不凑 brief 的二分支)

派工 brief 给的二分支是 "GPU 可用 → 真 bench" / "GPU 不可用 → 脚本骨架 + 触发条件". 实测落在**两者之间**:

- GPU 可用 ✓
- bge-m3 **未缓存** ✗ (下载被 brief 明令禁止)
- 但 **Qwen3 已缓存且能力等价** (同 1024d, 同 `token_embeddings` 接口, 且是**生产默认模型** — 用它跑 bench 比 bge-m3 更贴近生产真实)

→ **真 bench 可跑, 用 Qwen3-Embedding-0.6B (生产默认) 而非 bge-m3**; bge-m3 路径写入触发条件文档, 留 future PR.

## 铁律遵守

- 不 `ollama pull bge-m3` / 不 `SentenceTransformer('BAAI/bge-m3')` 触发 2.7GB 下载
- 不改 `docker-compose.yml` / `app/main.py` / `app/services/embedding_service.py` (W-N-C 已改, brief 严禁再改)
- 不改 plan 文件 / 不改 W-N-A/B/C/D commits
- 不改 DFT 集成 dirty 文件
- 不动 prod 配置 (`EMBEDDING_BACKEND` env 不改)
- 范畴: `docs/capability/` + `scripts/` + `results/` + `docs/bench/` + `memory/`

## 锚点

W-N-D+ +0 (本文件) / +1 capability 报告 / +2 真 bench / +3 收口.
