# W-N-XX 未来派工留口 起步 (2026-08-05)

> **派工**: W-N-XX +0 起步 memory (本任务起步阶段)
> **基线 HEAD**: `fbc11908e` (W-N-BGE +3 收口沉淀)
> **目的**: W-N 周期 14 stages 跑完后, 把 3 项未闭环 / 留待未来触发的派工留口沉淀成可派工留口
> **派工锚点**: W-N-XX +0 起步 (本文件) / +1 写 runbook + MEMORY.md #26 / +2 收口

---

## 1. 起步检查清单 (W73 铁律 6 项)

| # | 检查项 | 状态 | 备注 |
|---|--------|------|------|
| 1 | 工作目录 + base HEAD 验证 | ✅ | `cwd = E:/microbubble-agent`, `git log --oneline -1` = `fbc11908e docs(memory): W-N-BGE +3 收口沉淀` |
| 2 | 派工 brief 严禁事项核对 | ✅ | 0 改 production code / 0 改 plan / 0 改 W-N-A/B/C/D/E/F/D+/+/ARC/GC/ANC/MEM/G+/OBS/RAG/BGE/GRAND/FILL/D++ commits / 0 改 alembic 100-104 老迁移 |
| 3 | 派工 v6 §13 仓库实情真查 | ✅ | 14 stages 全部跑完, 3 阶段 (G+/RAG/BGE) 起步未合 (本任务沉淀留口) |
| 4 | 类 20 历史沉淀查阅 | ✅ | 类 20.153 (alembic hotfix branch) + 类 20.154 (alembic_version stamp drift) + 类 20.155 (head 守恒 ≠ schema 守恒) + 类 20.156 (best-effort 静默失败) |
| 5 | 锚点范式守恒 | ✅ | W-N +0/+1/+2 据实累计 (本任务); W-N-G+ +N / W-N-BGE +N / W-N-FILL +N 留口占位 |
| 6 | 0 production code 改动铁律 | ✅ | 仅 docs/ + memory/ 范畴, 未改 app/ web/src/ alembic/versions/ docker-compose.yml |

---

## 2. 3 项未来派工留口 据实清单

### 2.1 W-N-G+ 4 FAIL (漂移测试)

**来源**: W-N-G+ +2 commit `322455f5d` 8 个 pytest 自报 8/8 PASS, 派工 brief 标注 "实测 4 FAIL" 偏差据实.

**4 drift tests 名称** (W-N-G+ +2 `tests/test_w_n_g_plus_chunk_late_recall.py`):
- `test_schema_drift_knowledge_embedding_model_version`
- `test_schema_drift_meetings_embedding_model_version`
- `test_schema_drift_knowledge_chunks_chunk_embedding`
- `test_chunk_late_recall_path_no_silent_fail`

**触发条件**: DB 容器可达 + schema drift 实际列名 + 16GB+ RAM

**修复路径**: W-N-G+ +1 commit `7cb6bf0d1` 4 步 stamp+upgrade (沿用)

### 2.2 W-N-FILL 拦截 (回填不执行)

**来源**: W-N-D++ +2 commit `1cc5362e2` 决策文档 `docs/decisions/2026-08-05-e2e-late-chunking-decision.md` §5 明确 "不创建 + 不执行".

**触发条件**: 修订 W-N-D++ 决策 OR 新业务理由 (qa-bench ≥ 96.5% / late chunking 成为召回瓶颈 / 新路由需要)

**派工阻断**: W-N-D++ §5 决策不撤, 不准派 W-N-FILL

### 2.3 W-N-BGE 数据不足 (模型替换延后)

**来源**: W-N-BGE +3 commit `fbc11908e` 决策文档 `docs/decisions/2026-08-05-bge-m3-decision.md` 3 决策大门禁 1 PASS 2 数据不足.

**触发条件**: 容器预下载 bge-m3 + GPU 真测 pass rate ≥ Qwen3 baseline (93.5%) + VRAM < 4GB

**修复路径**: W-N-BGE +1 commit `9169e3ae9` 真 bench 框架 + 1000 题 JSON 输出

---

## 3. 派工锚点沿用

- **W-N-XX +0/+1/+2**: 本任务 (起步 + 写 runbook + 收口)
- **W-N-G+ +N**: N ≥ 4 (W-N-G+ +0/+1/+2/+3 已用, 未来派工留 +N 槽位)
- **W-N-BGE +N**: N ≥ 4 (W-N-BGE +0/+1/+2/+3 已用)
- **W-N-FILL +N**: N ≥ 0 (W-N-FILL 0-3 全部空闲)

派工 v11 段 9 规则下都是有效锚点, 不撞 W-N-D+ / W-N-D++ / W-N-D 实战.

---

## 4. 派工 brief 严禁 (沿用 W-N 全周期)

- ❌ 0 改 `app/services/hybrid_retriever.py` / `embedding_service.py` / `knowledge_service.py` 既有 4 API
- ❌ 0 改 `alembic/versions/100-104` 老迁移 (W-N-A/B/C/D 范畴)
- ❌ 0 改 `docker-compose.yml` / `app/main.py` / `web/src/` / `alembic/versions/105_*` (W-N-G+ 范畴)
- ❌ 0 改生产 `.env` / `EMBEDDING_BACKEND` / `EMBEDDING_MODEL_NAME`
- ❌ 0 改 W-N-A/B/C/D/E/F/D+/+/ARC/GC/ANC/MEM/G+/OBS/RAG/BGE/GRAND/FILL/D++ commits
- ❌ 0 改 plan 文件
- ✅ 仅新增 `docs/` / `memory/` / `scripts/` / `tests/` / `results/`

---

## 5. 起步工作状态

- **W-N-XX +0**: 本文件 (起步 memory)
- **W-N-XX +1**: 待写 `docs/w-n-future-leftover-2026-08-05.md` + 改 `memory/MEMORY.md` 新增 #26 段
- **W-N-XX +2**: 待写 `memory/w-n-xx-future-leftover-closure-2026-08-05.md` (收口 memory)

预估 3 commits 总数 (按 W-N 周期惯例, +0/+1+2 = 3 commits).

---

## 6. 关键 commit 引用

- 本任务基线: `fbc11908e docs(memory): W-N-BGE +3 收口沉淀`
- W-N-GRAND +1 runbook: `c011ebd09 docs(grand-closure): W-N 系列 14 stages 总 grand closure`
- W-N-D++ +2 commit: `1cc5362e2 feat(rag): W-N-D++ 端到端 late chunking 召回 bench + 决策归档`
- W-N-G+ +2 commit: `322455f5d feat(rag): _chunk_late_recall 路径验证 + 集成测试`
- W-N-BGE +1 bench: `9169e3ae9 perf(rag): bge-m3 1000 题真 bench`

---

**W-N-XX +0 起步完成. 下一步: W-N-XX +1 写 runbook + MEMORY.md #26 段 + 2 个 commit (runbook + MEMORY.md).**
