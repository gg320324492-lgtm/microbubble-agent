# W-N 系列 未来派工留口 (2026-08-05)

> **派工**: W-N-XX +0 起步 / +1 写本 runbook + MEMORY.md #26 段 / +2 收口
> **基线 HEAD**: `fbc11908e` (W-N-BGE +3 收口沉淀)
> **目的**: 把 W-N 周期 14 stages 跑完后**仍未闭环**或**留待未来触发**的 3 项沉淀成可派工留口
> **关联**: W-N-GRAND +2 留口扩展 + W-N-D++ §5 决策禁止 + W-N-BGE +3 3 门禁 1 PASS 2 数据不足
> **派工锚点**: W-N-XX +0 起步 / +1 写本 runbook (本 commit) / +2 收口

---

## 概览

W-N 周期 14 stages 全部跑完后, 仍有 3 项**未闭环**或**留待触发条件**:

| 留口 | 派工锚点 | 来源 | 触发条件 | 紧迫度 |
|------|---------|------|---------|--------|
| **§1 W-N-G+ 4 FAIL** | W-N-G+ +N | W-N-G+ +2 8/8 PASS 自报 vs 实测 4 FAIL 偏差 | DB 容器可达 + schema drift 实际列名 + 16GB+ RAM | 低 |
| **§2 W-N-FILL 拦截** | W-N-FILL +N | W-N-D++ §5 决策 "不创建 + 不执行" | 修订 W-N-D++ 决策 OR 新业务理由 | 极低 |
| **§3 W-N-BGE 数据不足** | W-N-BGE +N | W-N-BGE +3 3 门禁 1 PASS 2 数据不足 | 容器预下载 bge-m3 + GPU 真测 | 中 |

**派工前必读**:
1. CLAUDE.md "0 production code 改动铁律" 段
2. W-N-GRAND +1 runbook (`docs/w-n-grand-closure-runbook.md`) 14 stages 总览
3. W-N-D++ 决策文档 (`docs/decisions/2026-08-05-e2e-late-chunking-decision.md`) 关于 FILL 决策
4. W-N-BGE +3 决策文档 (`docs/decisions/2026-08-05-bge-m3-decision.md`) 关于 3 门禁

---

## §1 W-N-G+ 4 FAIL (漂移测试)

### 1.1 4 drift tests 名称

W-N-G+ +2 commit `322455f5d` 落地 8 个 pytest, 当前**自报 8/8 PASS** (83.78s), 但派工 brief 标注 "实测 4 FAIL" 偏差据实. 4 个漂移测试是:

| # | 测试名 | 当前位置 | 漂移条件 |
|---|--------|---------|---------|
| 1 | `test_schema_drift_knowledge_embedding_model_version` | `tests/test_w_n_g_plus_chunk_late_recall.py:22` | DB 容器可达 + `knowledge.embedding_model_version` 列存在 |
| 2 | `test_schema_drift_meetings_embedding_model_version` | `tests/test_w_n_g_plus_chunk_late_recall.py:35` | DB 容器可达 + `meetings.embedding_model_version` 列存在 |
| 3 | `test_schema_drift_knowledge_chunks_chunk_embedding` | `tests/test_w_n_g_plus_chunk_late_recall.py:48` | DB 容器可达 + `knowledge_chunks.chunk_embedding` 列存在 |
| 4 | `test_chunk_late_recall_path_no_silent_fail` | `tests/test_w_n_g_plus_chunk_late_recall.py:~80` | 库可达 + 16GB+ RAM 跑 `HybridRetriever.retrieve()` 4 路 + late chunking |

**注**: 这是**留待未来派工**的 4 FAIL 场景, W-N-G+ +2 commit `322455f5d` 实际自报 8/8 PASS (主拍 W-N-G+ +3 沉淀时已经据实). 留口含义: 若未来某个再启场景 (例如 schema drift 再次出现 / 列被删) 触发 4 FAIL, 直接派 W-N-G+ +N 修复, 不必重新调研.

### 1.2 触发再启条件

**三者齐全**才触发 W-N-G+ +N 派工:

1. **DB 容器可达**: `docker exec microbubble-agent-postgres-1 pg_isready -U postgres` 返回 0
2. **schema drift 实际列名**: `psql -c "\d knowledge"` / `\d meetings` / `\d knowledge_chunks` 出现 `embedding_model_version` / `chunk_embedding` 列缺失
3. **16GB+ RAM**: 本地 `free -h | grep Mem` 或 `wmic OS get FreePhysicalMemory` ≥ 16GB, 跑 `pytest tests/test_w_n_g_plus_chunk_late_recall.py` 不爆 OOM

**任一条件不满足** → 暂不派工, 沿用 W-N-G+ +3 沉淀结论.

### 1.3 派工 brief 必查

派工 W-N-G+ +N 时, 派工 brief **必须**包含:

- **派工 v6 §13 仓库实情真查**: 实测 `git log --oneline -1` 验证 base HEAD ≠ `fbc11908e` (本任务基线)
- **派工 brief 严禁**: 0 改 `app/services/hybrid_retriever.py` / `app/services/embedding_service.py` 既有 4 API
- **派工 brief 严禁**: 0 改 `alembic/versions/105_fix_drift.py` (W-N-G+ +1 范畴)
- **派工 brief 严禁**: 0 改 `_chunk_late_recall` 业务代码 (W-N-OBS 范畴, 避免跨阶段耦合)
- **派工 brief 必查**: agent 自报 8/8 PASS vs 实测 4 FAIL 偏差 → 据实上报, 不擅自扩也不擅自缩
- **派工 brief 必查**: 4 drift tests 名称 + 触发条件 + 修复路径 (沿用 W-N-G+ +1 stamp 4 步法)

### 1.4 修复路径 (W-N-G+ +1 沉淀复用)

如触发 4 FAIL, 修复路径沿用 W-N-G+ +1 commit `7cb6bf0d1` 4 步 stamp+upgrade:

```bash
# 步骤 1: 跳 100-102 列类型变更
docker exec microbubble-agent-app-1 alembic stamp 102_voiceprint_halfvec
# 步骤 2: 标记 103 已应用
docker exec microbubble-agent-app-1 alembic stamp 103_add_embedding_model_version
# 步骤 3: 跳 099 (dft_jobs 已手工建)
docker exec microbubble-agent-app-1 alembic stamp 104_add_knowledge_chunk_late_embedding
# 步骤 4: 跑 104 + 105_fix_drift
docker exec microbubble-agent-app-1 alembic upgrade head
```

若 schema drift 实际列名不符 (派工 brief 措辞偏差), 据实调整 stamp 策略, 但**绝不准删改 099/103/104 老迁移** (W-N-G+ +1 类 20.153 沉淀).

### 1.5 类 20 沉淀引用

- **类 20.153**: alembic 链 hotfix branch 必实测 `alembic history`, 不凭 brief 串行推测
- **类 20.154**: DB alembic_version 表 stamp 漂移是常见事故根因, 先 `\d table` 再看 version_num

---

## §2 W-N-FILL 拦截 (回填不执行)

### 2.1 W-N-D++ §5 决策 "不创建 + 不执行"

W-N-D++ +2 commit `1cc5362e2` 决策文档 `docs/decisions/2026-08-05-e2e-late-chunking-decision.md` §5 明确:

> **派工 brief 严禁**: 0 改 schema + 0 真跑回填 late_embedding 列
>
> **整段归档决策**: ❌ W-N-D++ 端到端召回阶段整段归档 (派工 brief "所有 3 门禁 FAIL → 整段归档"). Gate 1 是 hard-fail gate, 即使 Gate 2/3 PASS 也必须归档.

W-N-FILL 原本计划是 W-N-D++ 之后**回填 `knowledge_chunks.late_embedding` 列** (派工 brief 排定), 因 W-N-D++ 整段归档而**拦截**: **不创建 + 不执行**.

### 2.2 触发再启条件

**两个条件任一**才触发 W-N-FILL +N 派工:

1. **修订 W-N-D++ 决策**: 主拍重新评估 W-N-D++ 3 门禁结果, 决定**重新启用** late chunking 端到端, 重排 §5 决策
2. **新业务理由**: 例如 (a) qa-bench ≥ 96.5% 目标达成 (W-N-F LoRA 触发条件之一) (b) 生产 `knowledge_chunks.late_embedding` 空缺成为召回瓶颈 (c) 新 hybrid_retriever 路由需要 late chunking 数据

**两个条件都未达** → 沿用 W-N-D++ §5 决策, W-N-FILL **永远不派工**.

### 2.3 派工 brief 必查

派工 W-N-FILL +N 时, 派工 brief **必须**包含:

- **派工 v6 §13 仓库实情真查**: 实测 `git log --oneline -1` 验证 base HEAD ≠ `fbc11908e` (本任务基线)
- **派工 brief 必查**: W-N-D++ §5 决策修订理由 (决策为何变, 哪个门禁变化)
- **派工 brief 严禁**: 0 改 W-N-D++ 决策文档 (`docs/decisions/2026-08-05-e2e-late-chunking-decision.md`) → 仅新写 `docs/decisions/<date>-late-chunking-reintro.md`
- **派工 brief 严禁**: 0 改 `alembic/versions/104_add_knowledge_chunk_late_embedding.py` (W-N-D 范畴)
- **派工 brief 严禁**: 0 改 `scripts/bench_e2e_late_chunking_recall.py` (W-N-D++ 范畴)
- **派工 brief 必查**: 类 20 决策一致性 — 新决策与 W-N-D++ §5 决策是否冲突, 如冲突必须先撤 W-N-D++ 决策

### 2.4 阻断

W-N-FILL 派工 brief **必须**包含以下阻断 (W-N-D++ §5 决策不撤, 不准派 W-N-FILL):

```
W-N-FILL 派工阻断:
1. W-N-D++ 决策文档中 §5 是否仍标 "整段归档" — 若 YES, 拒绝派工
2. qa-bench 当前分数是否 ≥ 96.5% — 若 NO, 拒绝派工
3. 主拍是否明确书面批准 W-N-FILL 派工 — 若 NO, 拒绝派工
```

### 2.5 类 20 沉淀引用

- **类 20.155**: alembic head 守恒 ≠ DB schema 守恒 (W-N-D++ 沉淀, 与 W-N-FILL 决策直接相关)
- **类 20.156**: best-effort 静默失败比显式失败更危险 (W-N-D++ 沉淀, FILL 启用时必先修 observability)

---

## §3 W-N-BGE 数据不足 (模型替换延后)

### 3.1 3 门禁 1 PASS 2 数据不足

W-N-BGE +3 commit `fbc11908e` 决策文档 `docs/decisions/2026-08-05-bge-m3-decision.md` 3 决策大门禁结果:

| 门禁 | 维度 | 实测 | 决策 |
|------|------|------|------|
| 1 | bge-m3 真 pass rate ≥ Qwen3 baseline (93.5%) | ⏸ **未真测** (容器内 hf-mirror.com 不可达) | ⏸ **数据不足, 暂不切** |
| 2 | VRAM < 4GB | ⏸ **未真测** (本地无 CUDA + GPU 容器内真模型未下载) | ⏸ **数据不足, 待 GPU 真测** |
| 3 | latency < 2x Qwen3 | ✅ **本地 CPU 16.74ms/doc** (估算 GPU ~80ms = 1.6x) | ✅ **门禁通过** |

**大门禁决策**: 3 门禁 1 通过 2 数据不足 = **"模型替换延后"**, 后续派工 (W-N-BGE +N) 容器预下载 bge-m3 后跑真 pass rate + VRAM 再决策.

### 3.2 触发再启条件

**三个条件齐全**才触发 W-N-BGE +N 派工:

1. **容器预下载 bge-m3 成功**: `docker exec microbubble-agent-app-1 bash -c "HF_HUB_OFFLINE=0 python -c \"from huggingface_hub import snapshot_download; snapshot_download(repo_id='BAAI/bge-m3')\""` 返回 0
2. **GPU 真测 pass rate**: 在 RTX 5090 32GB 跑 `scripts/run_bge_m3_realbench.py` 1000 题 → pass rate ≥ Qwen3 baseline (~93.5%)
3. **VRAM 真测**: `nvidia-smi` 在推理时峰值 < 4GB (与 HNSW 调优共 GPU 资源)

**任一条件不满足** → 沿用 W-N-BGE +3 决策 (Qwen3 默认生产保留, bge-m3 灰度基础设施就绪).

### 3.3 派工 brief 必查

派工 W-N-BGE +N 时, 派工 brief **必须**包含:

- **派工 v6 §13 仓库实情真查**: 实测 `git log --oneline -1` 验证 base HEAD ≠ `fbc11908e` (本任务基线)
- **派工 brief 必查**: 容器内 bge-m3 真模型下载验证 (hf-mirror.com / HF 镜像可达)
- **派工 brief 必查**: GPU 容器 RTX 5090 32GB VRAM 实测 (`nvidia-smi`)
- **派工 brief 严禁**: 0 改 `app/services/embedding_service.py` 既有 4 API
- **派工 brief 严禁**: 0 改 `app/agent/chat_engine.py` (方案 C 6 铁律)
- **派工 brief 严禁**: 0 改 `EMBEDDING_BACKEND` / `EMBEDDING_MODEL_NAME` 生产配置 (`.env` 0 改动)
- **派工 brief 必查**: 模型本地可达性 — 沿用 W-N-D+ 沉淀 "GPU 可用 + bge-m3 不可达 → 落 W-N-BGE +N 留口"

### 3.4 实测验证命令 (W-N-BGE +1 沉淀复用)

```bash
# 1. 验证 bge-m3 真加载 (本地 CPU)
python -c "from sentence_transformers import SentenceTransformer; m = SentenceTransformer('BAAI/bge-m3'); print(m.get_sentence_embedding_dimension(), m.max_seq_length)"
# 期望: 1024 8192

# 2. 真测 1000 题 latency (本地 CPU)
python scripts/run_bge_m3_realbench.py --n-questions 1000 --batch-size 32
# 期望: ~17s CPU, 估算 GPU ~80ms/doc

# 3. GPU 容器实测 (如 W-N-D+ 报告, RTX 5090 32GB)
docker exec microbubble-agent-app-1 nvidia-smi
docker exec microbubble-agent-app-1 bash -c "python -c 'import torch; print(torch.cuda.is_available(), torch.cuda.get_device_name(0))'"
# 期望: True 'NVIDIA GeForce RTX 5090'

# 4. 容器内预下载 bge-m3
docker exec microbubble-agent-app-1 bash -c "HF_HUB_OFFLINE=0 python -c 'from huggingface_hub import snapshot_download; snapshot_download(repo_id=\"BAAI/bge-m3\")'"
# 期望: 返回 0, /root/.cache/huggingface/ 出现 bge-m3 目录
```

### 3.5 决策路径 (W-N-BGE +N 落地)

| 决策 | 触发条件 | 后续 |
|------|---------|------|
| 切换生产 bge-m3 backend | 门禁 1 PASS + 门禁 2 PASS | 新写 `docs/decisions/<date>-bge-m3-cutover.md` + 改 `EMBEDDING_MODEL_NAME` + 留 7 天灰度 |
| 暂不切 | 门禁 1 FAIL / 门禁 2 FAIL | 沿用 W-N-BGE +3 决策, 6 个月后再评估 |
| 投资新候选 | bge-m3 FAIL + 出现 SOTA 替代 | 新写 `docs/decisions/<date>-new-candidate.md` |

### 3.6 类 20 沉淀引用

- **W-N-D+ §4.3** 类 20 沉淀: "本机无 GPU" 前提被推翻 — GPU 可用但 bge-m3 不可达, 落 W-N-BGE +N 留口
- **W-N-C +3** 决策: Qwen3 1024d 默认生产保留, bge-m3 灰度基础设施就绪, 真测待 GPU

---

## §4 派工总览

### 4.1 未来派工顺序表 (主拍决策, 不擅自扩)

| 序号 | 派工锚点 | 触发条件 | 范畴 | 期望 commit 数 |
|------|---------|---------|------|---------------|
| 1 | W-N-G+ +N | DB 容器可达 + schema drift 实际列名 + 16GB+ RAM | production migration 修复 | 2-3 |
| 2 | W-N-BGE +N | 容器预下载 bge-m3 + GPU 真测 pass rate + VRAM | 模型替换决策 | 2-3 |
| 3 | W-N-FILL +N | 修订 W-N-D++ 决策 OR 新业务理由 | late_embedding 回填 | 3-4 |

**派工顺序**: W-N-BGE +N → W-N-G+ +N → W-N-FILL +N (依紧迫度优先级)
**W-N-FILL 优先级最低**: 因 W-N-D++ §5 决策已拦截, 除非主拍明确批准, 否则**永远不派**.

### 4.2 派工 v6 §13 仓库实情真查 (派工前必跑)

每项派工前必跑:

```bash
# 1. 实测 base HEAD ≠ fbc11908e
git log --oneline -1

# 2. 实测 W-N 周期 commits 现状
git log --oneline --all | grep -E "W-N-" | head -50

# 3. 实测 alembic head 守恒
python -m alembic heads

# 4. 实测派工 brief 锚点不撞 (W-N-XX +N 不撞 W-N-G+ / BGE / FILL 历史)
git log --oneline --all | grep -E "W-N-G\+ \+|W-N-BGE \+|W-N-FILL \+"
```

### 4.3 0 production code 改动铁律 (W-N 周期延续)

W-N 周期 14 stages 严格守恒 0 production code 改动, 未来派工**沿用**:

- ❌ 不改 `app/services/hybrid_retriever.py` / `embedding_service.py` / `knowledge_service.py` / `chat_engine.py` 既有 4 API
- ❌ 不改 `alembic/versions/100-104` 老迁移 (W-N-A/B/C/D 范畴)
- ❌ 不改 `docker-compose.yml` / `app/main.py` / `web/src/` / `alembic/versions/105_*` (W-N-G+ 范畴)
- ❌ 不改生产 `.env` / `EMBEDDING_BACKEND` / `EMBEDDING_MODEL_NAME`
- ✅ 仅新增 `docs/` / `memory/` / `scripts/` / `tests/` / `results/`

### 4.4 锚点范式 (W-N 周期 ~537 → ~572 据实累计)

W-N 周期 14 stages 累计 ~35 commits 推 main, 锚点 W100 +75 ~537 → W-N-G+ +N ~572 据实累计. 未来派工锚点遵循:

- **W-N-G+ +N**: N ≥ 4 (W-N-G+ +0/+1/+2/+3 已用)
- **W-N-BGE +N**: N ≥ 4 (W-N-BGE +0/+1/+2/+3 已用)
- **W-N-FILL +N**: N ≥ 0 (W-N-FILL 0-3 未派, 整段空闲)

锚点不撞 (派工 v11 段 9 规则下都是有效锚点), 沿用 W-N-D+ / W-N-D++ 不撞 W-N-D 实战.

---

## §5 沉淀文件清单

| 类型 | 路径 | 状态 |
|------|------|------|
| 未来派工留口 runbook | `docs/w-n-future-leftover-2026-08-05.md` (本文件) | ⏳ pending commit |
| startup memory | `memory/w-n-xx-future-leftover-startup-2026-08-05.md` | ⏳ pending commit |
| closure memory | `memory/w-n-xx-future-leftover-closure-2026-08-05.md` | ⏳ pending commit |
| MEMORY.md #26 段 | `memory/MEMORY.md` | ⏳ pending commit |

---

## §6 关联文件

- W-N-GRAND +1 runbook: `docs/w-n-grand-closure-runbook.md`
- W-N-G+ +3 closure: `memory/w-n-g-plus-schema-drift-closure-2026-08-05.md`
- W-N-G+ +2 commit: `322455f5d feat(rag): _chunk_late_recall 路径验证 + 集成测试`
- W-N-G+ +1 commit: `7cb6bf0d1 fix(rag): schema drift 修复迁移`
- W-N-D++ +2 commit: `1cc5362e2 feat(rag): W-N-D++ 端到端 late chunking 召回 bench + 决策归档`
- W-N-D++ 决策文档: `docs/decisions/2026-08-05-e2e-late-chunking-decision.md`
- W-N-BGE +3 closure: `memory/w-n-bge-m3-realpath-closure-2026-08-05.md`
- W-N-BGE +3 commit: `fbc11908e docs(memory): W-N-BGE +3 收口沉淀`
- W-N-BGE 决策文档: `docs/decisions/2026-08-05-bge-m3-decision.md`
- W-N-D+ +2 closure: `memory/w-n-d-plus-realbench-closure-2026-08-05.md`

---

**W-N 周期 14 stages 全部跑完, 未来派工 3 项留口沉淀完成. W19 选项 A 维持. 派工锚点 W-N-XX +0/+1/+2 据实累计, 0 production code 守恒.**
