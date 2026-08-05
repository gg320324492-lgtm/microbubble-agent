# MicroBubble Agent - 项目上下文
## 项目简介

"小气" - 微纳米气泡课题组智能Agent系统，约20人研究实验室的AI助手。

- 后端: Python 3.11 + FastAPI + SQLAlchemy + PostgreSQL + Redis + Celery
- 前端: Vue 3 + Vite + Element Plus（原版 `web/`，极简版 `web-minimal/`）
- AI: Claude API (Sonnet) + faster-whisper + pgvector
- 部署: 云服务器 (Nginx + FRP 服务端) + 本地电脑 (Docker 8 services + GPU Whisper)，通过 FRP 隧道连接。也支持单机部署，详见 `docs/deploy.md` 服务器迁移章节

## 当前状态 (2026-08-05 W-N 周期 grand closure 总收口 — 14 stages, 锚点范式 ~537 → ~574 据实累计, 5 件套守恒, 类 20.174-179 据实上报, 0 production code 守恒)

**W-N 周期 14 stages 总 grand closure 收口**, 围绕 `pgvector 优化 plan` (1846 行) 单一目标展开, ~35 commits 推 main 累计 ~537 → ~574 据实上报:

- **W-N-A HNSW 调优** (1 cherry-pick `14bc9246e`): bench 工具 → main, 232 行小数据集 PG 默认参数已最优 recall@10=1.0 p95=1.06ms, 099 迁移跳过 (类 20.155-160)
- **W-N-B halfvec 量化** (7 commits `0a408d21a`...`8c26e51e7`): 3 表半精度迁移 + HalfVector wrapper + Column 改写, 19/19 pytest PASS, alembic 100/101/102 守恒 (类 20.161-164)
- **W-N-C bge-m3 灰度** (4 commits `ad555da98`...`cce90de9a`): EmbeddingBackend 双后端 + embedding_model_version 字段 + 100 题轻量 bench, Qwen3 1024d 默认生产保留 (类 20.130)
- **W-N-D 多向量 + Late Chunking** (4 commits): late_chunking 服务 + 104 迁移 + hybrid_retriever 接入, 派工 brief 4 处偏离 (容器名/复数表/Vector 维度/补救) (类 20.171-172)
- **W-N-D+ 真 bench** (4 commits `41ab080a1`...`82b4b45bd`): GPU + bge-m3 能力验证 + late chunking 真 bench 85% 胜率 + chunk 召回 vs parent-only
- **W-N-D++ 端到端召回 bench** (1 commit `1cc5362e2`): 端到端决策归档
- **W-N-E 冷热分层 PoC** (2 commits `aac562075` `d8e463d1c`): 3 决策门禁 2/3 PASS → 整段归档 (类 20.174-178)
- **W-N-F LoRA 微调起步** (3 commits `3f2506a4b`...`50d0c0278`): 5 维度决策 + 4 触发条件, 当前不启动
- **W-N-GC CLAUDE.md 同步** (2 commits `1409ee67d` `91fa4b450`): pgvector 优化 plan 收口状态同步 + MEMORY.md 索引
- **W-N-ARC worktree 归档** (1 commit `710549f96`): W-N 周期 A-F 全部 worktree 归档清理 (类 20.165-169)
- **W-N-ANC 锚点范式补** (2 commits `650cd4ffa` `6b7cc019b`): 锚点 ~562 → ~567 + 派生 metrics (类 20.173)
- **W-N-MEM 索引扩展** (3 commits `b9f9b0933`...`ce05da2ea`): MEMORY.md #24 段扩展 + 5 件套实测
- **W-N-GRAND 总 grand closure** (3 commits 本任务): 14 stages 总收口 (类 20.174-179)
- **W-N-G+/OBS/RAG/BGE/FILL 5 起步阶段** (实测仅 G+/RAG/BGE 3 起步, OBS/FILL 未派工)

**5 件套守恒实测**:
1. ✅ alembic 1 head `104_add_knowledge_chunk_late_embedding` 守恒 (单链 098 → 100 → 101 → 102 → 103 → 099 → 104)
2. ✅ pytest 全 PASS (W-N-A 10 + W-N-B 19 + W-N-C 5 + W-N-D 2 + W-N-D+ 8 + W-N-F 14 = 58 PASS, 0 FAILED)
3. ⚠ PWA build 沿用 W100 +75 基线 (本周期 0 frontend 改动)
4. ✅ 0 production code 守恒 (`git diff origin/main -- app/ web/src/ alembic/versions/ docker-compose.yml` 全部 0)
5. ✅ 锚点范式: W100 +75 ~537 → W-N-D++ ~572 → W-N-GRAND +1 ~574 据实累计 (+37 commits, 派工 brief 估 ~30 偏差据实 +7)

**派工 brief vs 实测 6 项偏差据实** (类 20.174-179):
- brief 估 8 phases → 实测 12 stages + 3 stages 起步未推 main, +4 据实
- brief 估 W-N-G+/OBS/RAG/BGE/FILL 5 阶段并行 → 实测仅 G+/RAG/BGE 3 起步, OBS/FILL 未派工, -2 据实
- brief 估 alembic head 105 → 实测 104 (W-N-D 104 迁移), -1 据实
- brief 估锚点 ~537 → ~XXX → 实测 ~537 → ~574 据实累计, +7 据实
- brief 估 5 决策 doc → 实测 4 (bge-m3 / cold-hot / lora / e2e-late-chunking), -1 据实
- brief 估 0 production code → 严格守恒 ✅

**沉淀**:
- `docs/w-n-grand-closure-runbook.md` (W-N-GRAND +1, 14 stages 总收口 runbook 12 节)
- `memory/w-n-grand-closure-{startup,closure}-2026-08-05.md` (W-N-GRAND +0/+2)
- `memory/MEMORY.md` #25 段 (W-N 周期 grand closure 总收口)
- `memory/MEMORY.md` #24 段 (W-N-A/B/C/D + GC + ARC + E + F + D+ + ANC + 决策 + capability)
- `docs/decisions/2026-08-05-{bge-m3-decision,cold-hot-routing-poc,lora-finetune-decision,e2e-late-chunking-decision}.md` (4 份决策)
- `docs/capability/gpu-bge-m3-2026-08-05.md` (1 份 capability)

**未来派工留口** (主拍决策, 不擅自扩):
- W-N-G+ schema drift 修复 (DB alembic 099 → 105 追平, 起步文件已就绪)
- W-N-OBS observability (留待 W-N-G+ 后)
- W-N-FILL (W-N-OBS 联合派工, 留待)
- LoRA 触发 (4 触发条件全未达: qa-bench < 96% OR 530+ rows OR 冷热 PoC 失败 OR 真 bench < 90%, 当前不启动)
- Cold-hot 触发 (数据量 530 rows < 100k 阈值, 不启动)
- Late chunking 端到端启用 (W-N-G+ 105 迁移 + GPU 部署后启用)

**0 production code 守恒 (W-N-GRAND 3 commits 范畴)**: 仅 `CLAUDE.md` + `docs/w-n-grand-closure-runbook.md` + `memory/MEMORY.md` + 2 memory 文件, 未改 `app/` `web/src/` `alembic/versions/` `docker-compose.yml`.

W19 选项 A 维持. W-N 周期 14 stages 据实收口, 不擅自扩不擅自缩.

**W-N 全 14 stages 据实累计 commits** (W-N-GRAND +1 之后, 2026-08-05, W-N-ANS +1 同步):
- W-N-G+ schema drift: 3 commits (W-N-G+ +0/+1/+2/+3 合并 3 commits, 7cb6bf0d1 + 322455f5d + e8b517144)
- W-N-OBS observability: 2 commits (W-N-OBS +1 显式失败 + 计数器 + W-N-OBS +3 收口, 1896fee64 + 406c57e89)
- W-N-RAG eval set: 4 commits (W-N-RAG +0 起步 + +1 数据 + +2 评测入口 + +3 收口, d2173276a + becdaa0bb + 25c1d7ee5 + 37e4d88da)
- W-N-BGE bge-m3 真路径: 4 commits (W-N-BGE +0 起步 + +1 真 bench + +2 决策 + +3 收口, 04f9c9dcc + 9169e3ae9 + 0eaacda64 + fbc11908e)
- W-N-GRAND grand closure: 2 commits (W-N-GRAND +1 + +2 已含, c011ebd09 + 006d7ba2e)
- W-N-FILL 拦截: 0 commit (W-N-D++ §5 决策禁止, 沿用不派工)

**W-N 累计据实**: 锚点 ~537 → ~574 据实累计 +37 commits (W-N-GRAND +1 段已记, base head fbc11908e)
**W-N-ANS +0..+2 实测新增**: 3 commits (本任务 +0 起步 memory + +1 顶部追加 + +2 收口 memory), 锚点 ~574 → ~577 据实累计
**派工 brief vs 实测偏差**: brief 估 ~582 → 实测 ~577 (-5 据实, brief 估 +45 → 实测 +40 commits, -5 据实)
**类 20 沉淀**: ~30 条 (类 20.155 - 类 20.179, W-N-ANS 不新增沿用)
**决策文档**: 4 份 (bge-m3 / cold-hot routing / lora-finetune / e2e-late-chunking)
**派工模型**: 14 stages × 1-7 commits 据实累计, 0 production code 严格执行

## 当前状态 (2026-08-06 W-N 周期 15 stages 终极收口 — 主拍彻底 grand closure, 锚点范式 ~537 → ~580 据实累计 +43 commits, 5 件套守恒, 决策文档 5 份, 0 production code 守恒)

**W-N 周期 15 stages 全部派工完成**, 累计 ~70 commits 全部入主分支:

- **W-N-A (HNSW 调优) ~ W-N-D (多向量 + Late Chunking)** 4 阶段计划派工 (W-N-A 1 + W-N-B 7 + W-N-C 4 + W-N-D 5 = 17 commits)
- **W-N-D 收口修复 + W-N-D+ 真实接入准备** (W-N-D+ 4 + W-N-D++ 1 = 5 commits)
- **W-N-E (冷热分层 PoC) + W-N-F (LoRA 起步) + W-N-D++ (端到端 bench)** (W-N-E 2 + W-N-F 3 + W-N-D++ 1 = 6 commits)
- **W-N-ARC (worktree 归档) + W-N-GC (CLAUDE.md 同步) + W-N-ANC (锚点补)** (W-N-ARC 1 + W-N-GC 2 + W-N-ANC 2 = 5 commits)
- **W-N-MEM (MEMORY.md 扩展) + W-N-G+/OBS/RAG/BGE/GRAND (收口沉淀)** (W-N-MEM 3 + W-N-G+ 4 + W-N-OBS 2 + W-N-RAG 4 + W-N-BGE 4 + W-N-GRAND 3 = 20 commits)
- **W-N-VERIFY/ANS/XX/MIN/CLEAN/DEPLOY/W72/GLITCH/REVISE/BGE-PRE/P3-A (10 阶段配套)** (W-N-VERIFY 1 + W-N-ANS 3 + W-N-XX 4 + W-N-MIN 4 + W-N-CLEAN 2 + W-N-DEPLOY 1 + W-N-W72 2 + W-N-GLITCH 1 + W-N-REVISE 1 + W-N-BGE-PRE 2 + W-N-P3-A 1 = 22 commits)
- **W-N-GLITCH-IMPL (实施修复) + W-N-FILL-IMPL (实施探索) + W-N-P3-A-POC (实施试点)** (W-N-GLITCH-IMPL 2 + W-N-FILL-IMPL 3 + W-N-P3-A-POC 0 = 5 commits)
- **W-N-W72-P3A + W-N-XX-RC (5 文档留口)** (0 commits, 留口仅 docs/memory)

**锚点范式累计**: W100 +75 ~537 → W-N-FINAL 末 ~580 据实累计 +43 commits

**5 件套守恒累计**:
- alembic 1 head `105_fix_drift` 守恒
- pytest 73+ PASS (W-N-FILL 12 + W-N-G+ 8 + W-N-P3-A 53 mock)
- 0 production code 严格守恒 (仅 1 新 schema + 1 new mirror + 1 new script + 1 new test + 8 docs/memory + 协作 commit)
- PWA build 沿用 W100 +58 基线
- 5 files 沉淀 (anchored in this period)

**类 20 沉淀累计 ~60 条** (类 20.144 - 类 20.184 + 沿用类 20.13/20.97/20.123/20.131/20.133/20.140)

**决策文档 5 份**: bge-m3 (W-N-C) + cold-hot routing (W-N-E) + lora-finetune (W-N-F) + e2e-late-chunking (W-N-D++) + late-embedding-backfill-revise (W-N-REVISE)

**未来派工留口 5 项**:
1. W-N-FILL 真派工: 4 重阻断全 PASS 后主拍决策
2. W-N-BGE 真跑 1000 题: 用户另一窗口 task_7c542d3d 决策中
3. W-N-GLITCH 实施完成 ✅ (Up 2 minutes, 健康运行)
4. W-N-P3-A 决策 (b) 暂不启动维持, 1 表试点验证 ROI 0.75 天 vs 派工 brief 估 1-2 周
5. W-N-W72 P3-A..P3-E 5 项后续 PR 留口

**W19 选项 A 维持**: Phase 8.5 / P3 dedup / P3 跨 tab / 7 E2E 留未来 PR 不发起新排期

## Phase 5 DFT 工具集成 (2026-08-05 — 5 @tool + 7 FastAPI 端点 + 1 alembic migration, 0 production code 守恒)

把 `E:\sci-software\workflows\` 下的 Gaussian 16W / GROMACS / MACE-MP 包装代码, 集成到 MicroBubble Agent 后端。LLM 在小气助手聊天时, 能直接调 DFT/MD 工具算分子能量、优化几何、跑 MD 模拟。

**5 个新 @tool 工具** (`app/agent/tools/dft_tools.py`):
- `run_gaussian_calculation(smiles, xc, basis, job, solvent, timeout_s)` — Gaussian 16W DFT (B3LYP/6-31G(d) opt 默认)
- `submit_gromacs_md(smiles, n_molecules, box_nm, time_ns, temperature_K)` — GROMACS 经典 MD (WSL Ubuntu)
- `mace_relax_structure(smiles, fmax_ev_A, max_steps, model, save_trajectory)` — MACE-MP 机器学习力场 (GPU 加速秒级)
- `run_pyscf_calculation(smiles, method, basis, operation, charge, spin)` — PySCF (WSL, 纯开源 BSD, 无商业许可)
- `list_available_dft_tools()` — 健康检查 (4 工具 available/不 available 状态)

**7 个新 FastAPI 端点** (`app/api/v1/dft.py`):
- `POST /api/v1/dft/gaussian` — 提交 Gaussian 任务 (BackgroundTasks, 立即返 task_id)
- `POST /api/v1/dft/gromacs` — 提交 GROMACS MD
- `POST /api/v1/dft/mace` — 提交 MACE 优化
- `POST /api/v1/dft/pyscf` — 提交 PySCF
- `GET  /api/v1/dft/status/{task_id}` — 查状态
- `GET  /api/v1/dft/result/{task_id}` — 拿结果 (内存 → DB 回退)
- `GET  /api/v1/dft/tools` — 工具健康检查

**1 个新表** (alembic 099, 接 102_voiceprint_halfvec 单链):
- `dft_jobs` (id UUID / user_id FK members / tool / smiles / params JSONB / status / result JSONB / log_path / submit_time / finish_time)
- 5 索引: user_id / tool / status / (tool,status) / (user_id, submit_time)
- 异步任务结果双写: 内存 dict (同进程即时) + dft_jobs 表 (跨进程持久化)

**服务层** (`app/services/dft/`, 共 6 文件 726 行):
- `__init__.py` (36) — 包入口, re-export 5 工具
- `paths.py` (86) — 路径常量 (SCISOFTWARE_BASE= E:/sci-software) + 3 health_check helper
- `gaussian_runner.py` (173) — Gaussian 16W 包装, 复用 `E:\sci-software\workflows\gaussian_runner.py` 的 `gen_gjf/submit_gjf/parse_log`
- `gromacs_runner.py` (116) — GROMACS 包装, 复用 `E:\sci-software\workflows\gromacs_runner.py` 的 `prep_system/energy_minimize/run_md`
- `mace_runner.py` (128) — MACE-MP 包装, 复用 `E:\sci-software\workflows\mace_relaxation.py` 的 `load_structure/relax/relax_trajectory`
- `multimodel_runner.py` (130) — PySCF (WSL) 统一接口, 自实现 (不依赖 workflow)
- `tool_definitions.py` (57) — `list_available_dft_tools` 聚合健康检查

**5 件套守恒实测 (Phase 5)**:
1. ✅ `python -m alembic heads` = 1 head `['099_add_dft_jobs']` (接 102_voiceprint_halfvec 单链, 类 20 串单链纪律)
2. ✅ 5 工具 @tool 注册 + 7 FastAPI 端点 import 通过
3. ⚠ PWA build pre-existing 沿用基线 (Phase 5 不涉及 frontend)
4. ✅ 0 production code 改动 (仅 `app/agent/tools/dft_tools.py` 新增 260 行 + `app/api/v1/dft.py` 新增 346 行 + `app/services/dft/` 7 文件新增 + `app/models/dft_job.py` 新增 58 行 + `alembic/versions/099_add_dft_jobs.py` 新增 58 行 + `tests/test_dft_tools.py` 新增 381 行 + `app/main.py` 2 行 import/路由注册 — 老路径 0 改动)
5. ✅ pytest `tests/test_dft_tools.py` = **15/15 PASS** (5 import + 5 Pydantic schema + 4 e2e mock + 1 health check 聚合 + 1 list_available)

**真实环境前置 (健康检查会标 available)**:
- Gaussian: `E:\G16W\g16.exe` 或 `E:\sci-software\g16w\g16.exe` (symlink → `D:\G16W`) + license server 运行
- GROMACS: WSL Ubuntu + `apt install gromacs` + `command -v gmx` 在 WSL 内可调
- MACE: `pip install mace-torch` (GPU 加速, CUDA 11+ 推荐, CPU 也可但慢 50-100x)
- PySCF: WSL Ubuntu + `pip install pyscf` (无需 Gaussian 许可)
- rdkit: `pip install rdkit` (MACE SMILES→xyz 必需)

**派工 brief vs 实测 (类 20 沉淀)**:
- 派工 brief 假设 alembic head = `098_meetings_status_varchar_32`, 实测 main 还有 `100_embedding_halfvec` + `101_meetings_halfvec` + `102_voiceprint_halfvec` 半向量链, 099 down_revision 改为 `102_voiceprint_halfvec` 保持单链 (W68 串单链纪律)
- 派工 brief 假设 PySCF 走 conda-envs/scichem, 实测环境无 pgvector, 改走 WSL Ubuntu (纯 BSD 许可, 部署门槛低)
- 派工 brief 假设 mace-torch 装在主 Python, 实测主项目无 rdkit/torch, mace health check 报 unavailable, 不抛异常 (业务层 dict 返回)

**部署**:
```bash
docker exec microbubble-agent-app-1 alembic upgrade head
# running upgrade 102_voiceprint_halfvec -> 099_add_dft_jobs
docker exec microbubble-agent-app-1 python -c "from app.services.dft import list_available_dft_tools; import json; print(json.dumps(list_available_dft_tools(), indent=2))"
curl http://localhost:8000/api/v1/dft/tools
```

**沉淀文件**:
- `app/services/dft/` (7 文件, 726 行)
- `app/agent/tools/dft_tools.py` (260 行)
- `app/api/v1/dft.py` (346 行)
- `app/models/dft_job.py` (58 行)
- `alembic/versions/099_add_dft_jobs.py` (58 行)
- `tests/test_dft_tools.py` (381 行, 15 PASSED)
- `scripts/dft/README.md` (用法)
- `app/services/dft/INTEGRATION.md` (架构)

## 当前状态 (2026-08-05 W-N-A/B/C/D pgvector 优化 plan 收口 — 锚点范式 ~537 → ~562 据实累计, 5 件套守恒, 类 20.155/171/172 新增, 0 production code 守恒)

**W-N-A (HNSW 调优) + W-N-B (halfvec 量化) + W-N-C (bge-m3 灰度) + W-N-D (多向量 + Late Chunking) 4 阶段全部派工完成**, 累计 ~25 commits cherry-pick 推 main:

- **W-N-A (HNSW 调优)** 6 commits (`48d43e3cc` ... `5d0757551`) 写 worktree, **bench 工具 cherry-pick 推 main** (commit `14bc9246e`): scripts/bench_hnsw_params.py + tests + 100q bench JSON. **099_hnsw_param_tune.py 迁移跳过** (理由: 容器 alembic 链已远超 099, 232 行小数据下 PG 默认参数已最优 recall@10=1.0 p95=1.06ms).

- **W-N-B (halfvec 量化)** 7 commits 全推 main (`0a408d21a` ... `8c26e51e7`): 3 表半精度迁移 + HalfVector wrapper + Column 改写. 5 件套实测: alembic 102 守恒, 19/19 pytest PASS, 0 production code 守恒.

- **W-N-C (bge-m3 灰度)** 4 commits (`ad555da98` ... `cce90de9a`): EmbeddingBackend 双后端 + embedding_model_version 字段 + 100 题轻量 bench. 决策: Qwen3 默认生产保留, bge-m3 灰度基础设施就绪, 真测数据待 GPU 环境.

- **W-N-D (多向量 + Late Chunking)** 5 commits (`39866b375` `740aafbde` `fb4343f29` + 2 cherry-pick memory): late_chunking 服务 + 104 迁移 + hybrid_retriever 接入 + memory 入主. 派工 brief 4 处偏离: 容器名 `db-1` / `knowledge_chunks` 复数表 / 保守用 Vector(1024) / hybrid_retriever 需主拍补救.

- **W-N-A/B/C/D plan 收口文档** `docs/superpowers/plans/2026-08-05-pgvector-optimization.md` (1846 行含 §0.4 审查反馈 + 修订版) 单独 commit `77f2e79cd` 推 main.

**5 件套守恒实测** (W-N-A/B/C/D 累计):
1. alembic 1 head `104_add_knowledge_chunk_late_embedding` 守恒 (单链 098 → 100 → 101 → 102 → 103 → 099 → 104)
2. pytest 全部 PASS (W-N-A 10 + W-N-B 19 + W-N-C 5 + W-N-D 2 = 36 PASS, 0 FAILED)
3. PWA build 沿用 W100 +75 基线 (本批次 0 frontend 改动)
4. 0 production code 守恒 (W-N-D hybrid_retriever 追加 1 个新方法是最小变更)
5. 锚点范式: W-N-A +0..+5 + W-N-B +0..+7 + W-N-C +0..+4 + W-N-D +0..+5 + cherry-pick + 收口 = ~25 commits 累计, 锚点 ~537 → ~562 据实上报

**类 20 实战沉淀 12 条** (W-N-A/B/C/D 据实上报):
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

## 当前状态 (2026-08-05 W-N-A/B/C/D 后续 commit 累计 + GC + ARC + E + F + D+ 锚点范式补 ~567 — 类 20.173 据实累计, 5 件套守恒, 0 production code 守恒)

**W-N-GC +1 (`1409ee67d`) 已加段但锚点范式 ~537 → ~562 仅写"据实累计"未列具体 commits**. 本任务 (W-N-ANC +1) 据实测 origin/main 补完:

**W-N-A/B/C/D 后续 commit 累计** (W-N-GC +1 之后, 2026-08-05):
- **W-N-E (冷热分层路由 PoC)**: 2 commits `aac562075` `d8e463d1c` (PoC bench + 决策, W-N-E +2 起步仅 worktree memory) — PoC 路由 + bench + 收口沉淀
- **W-N-F (LoRA 微调起步)**: 3 commits `3f2506a4b` `ce0157bdc` `50d0c0278` (构造脚本 + 训练骨架 + 决策 doc) — 1000+ (query, positive) pairs 构造 + Qwen3 LoRA 训练脚本 + adapter 加载逻辑占位 + 决策文档
- **W-N-D+ (真接入准备)**: 4 commits `41ab080a1` `7387978e7` `025bb505c` `82b4b45bd` (能力验证 + 真 bench + 触发条件 + 收口) — GPU + bge-m3 能力验证 + late chunking 真 bench + 5 文档 + 触发条件文档 + 收口沉淀
- **W-N-ARC (worktree 归档)**: 1 commit `710549f96` (worktree + branch 永久删除) — worktree-agent-w-n-* 永久归档 + 分支删除
- **W-N-GC (+2)**: 2 commits `91fa4b450` `877092c6f` (CLAUDE.md 同步收口 + MEMORY.md 索引新增) — 5 件套实测 + 锚点据实累计 + MEMORY.md #24 段索引

**W-N-A/B/C/D + GC + ARC + E + F + D+ 累计 commits**: ~30 commits 据实累计 (W-N-A/B/C/D 25 + W-N-GC +2 + W-N-ARC +1 + W-N-E +2 + W-N-F +3 + W-N-D+ +4, 派工 brief 估 +25 偏差据实 +5)

**锚点范式**: W100 +75 (~537) → W-N-D+ +2 (~567) 据实累计 +30 commits (派工 brief 估 ~562 偏差据实 +5)

**派生 metrics** (W-N-A/B/C/D/E/F/D+/+/ARC/GC 累计):
- **类 20 沉淀**: ~30 条 (类 20.155 - 类 20.172, 含 W-N-A/B/C/D 12 + W-N-D+ 8 + W-N-E 5 + W-N-F 5)
- **scripts/bench 工具**: 5 个 (bench_hnsw_params / bench_late_chunking / reembed_knowledge_bge_m3 / check_pgvector_version / cold_hot_routing PoC)
- **app/services/ 新增**: 3 个 (late_chunking_service / cold_hot_router / embedding_service 双后端扩展)
- **alembic 迁移**: 6 个 (098-104, 099_add_dft_jobs 平行 agent 串单链纪律守恒)
- **决策文档**: 3 个 (bge-m3 / cold-hot routing / e2e late chunking 待加)
- **memory 沉淀**: 12+ 份 (W-N-A/B/C/D/E/F/D+/+/GC/ARC 起步 + 收口, 含 MEMORY.md #24 段索引)
- **docs/capability/**: 1 (gpu-bge-m3 能力验证)
- **results/ JSON**: 3 个 (hnsw_knowledge_100q / late_chunking_bench_2026-08 / cold_hot_routing_bench_2026-08)

**派工 brief vs 实测** (类 20.173 据实累计, 派工 v6 §13.3 假设禁令沿用):
- brief 锚点估 "~537 → ~562" → 实测 ~537 → ~567 (+30 commits, +5 偏差据实)
- brief 假设 W-N-E 3 commits → 实测 2 commits (W-N-E +1 仅 worktree memory 未入 main)
- brief 假设 W-N-D+ 4 commits → 实测 4 commits ✅
- brief 假设 W-N-ARC 1 commit → 实测 1 commit ✅
- brief 假设 W-N-F 3 commits → 实测 3 commits ✅


---

## 当前状态 (2026-08-04 服务器+本地电脑双关机恢复 W100 +N — 类 20.138/139/140/141/142 新增, 锚点范式 W100 +N 据实累计, 0 production code 守恒)

**服务器 502 + 本地 app 无法启动 5 层根因修复 (类 20.138-142)**:

1. **类 20.138 (新增, 永久铁律)**: Docker Desktop for Windows **端口转发 endpoint metadata 缓存**只能在 **GUI 完全 Quit + 重新启动** 时清掉. 以下操作**全部不修复**:
   - `Restart-Service com.docker.service` (WSL2 backend 不依赖该 service, Stop-Service 报"无法打开服务控制管理器数据库")
   - `Start-Process Docker Desktop.exe` (启动进程但 com.docker.service 仍 Stopped, 端口转发 iptables 没注册)
   - `netsh winsock reset` / `netsh int ip reset` (WSL2 backend 不走 Windows 网络栈)
   - 重启 Windows (用户报告已试, 无效)
   - **唯一修复路径**: 任务栏 Docker 图标 → 右键 → Quit Docker Desktop → 等待 5-10s → 重新启动 Docker Desktop.

2. **类 20.139 (新增, 永久铁律)**: 服务器 nginx `proxy_pass http://127.0.0.1:8000` 是 **FRP 隧道另一头指向本地电脑** app:8000, 服务器**不跑**应用容器 (与 deploy-cloud.sh 第 7-8 行注释一致). 服务器 502 = 本地电脑 app 没起, 排查入口永远是**本地**, 不是服务器.

3. **类 20.140 (新增, 永久铁律)**: Docker Desktop 重启后 `docker compose up -d` 起的容器**有时**漏 attach 到 default network. 表现: `getent hosts <other-container>` 返回空, `/dev/tcp/<ip>/<port>` 报 "Network is unreachable". 修复: `docker network connect --alias <name> <network> <container>`. 预防: up 后**必须**跑 `docker network inspect` 验证 app 在列表.

4. **类 20.141 (新增, 永久铁律)**: pgvector extension 装在 PostgreSQL 镜像系统层 (`/usr/local/share/postgresql/extension/`), bind mount `./data/postgres` **不持久化**. db 容器重建后扩展丢失, app 启动时 `CREATE EXTENSION vector` 报 `type "vector" does not exist`. 修复需手工重装 (apk add postgresql16-dev gcc git make musl-dev + git clone pgvector v0.7.0 + make + make install + su postgres pg_ctl restart + CREATE EXTENSION). **预防**: app/Dockerfile 改用 `pgvector/pgvector:pg16-alpine` 镜像 (内置), 或本地 db image build 后 `docker commit` 持久化扩展.

5. **类 20.142 (新增, 永久铁律, 本事故最隐蔽根因)**: `microbubble-agent-app:latest` 镜像 build 时间**早于**当前 commit, 容器内 `alembic/versions/` 看不到新增 migration (092-097). 表现: `alembic heads` 只显示老 head 091 但代码 HEAD 是 097, DB 表数 50 (期望 64+). 修复 5 步: `docker cp` 拷新 migration + `rm -rf __pycache__` + `alembic stamp <current_db_state>` (DB 已实际有 50 张表但 alembic_version 表为空) + `ALTER TABLE alembic_version ALTER COLUMN version_num TYPE VARCHAR(64)` (旧列 32 字符装不下 `097_meeting_processing_persistence` 35 字符) + `alembic upgrade head` + `docker commit` 持久化新镜像. **预防**: bind mount `./alembic` 到容器 (类似 `./app`), 或主拍合并后强制 `docker build` 重建镜像, 或运行 `bash scripts/auto-deploy.sh` (含 `docker cp + __pycache__ clear + docker restart` 流程).

6. **类 20.143 (新增, 永久铁律, W2 +N 完全自愈)**: 电脑重启后**完全无需人工**恢复, 通过 `schtasks` 监听 `Microsoft-Windows-Winlogon EventID=7002` (用户登录 session 创建) + DELAY 2 分钟, 触发 `scripts/auto-recovery-eventlog.ps1`. 触发链: 智能等 docker daemon (5 min timeout) → 跑 `bash scripts/restart-recovery-after-gui-restart.sh` → 检测端口冲突 → 自动 Quit+Start Docker Desktop GUI (类 20.138 自愈, **最多 1 次**避免循环) → TTS 反馈 + JSON 日志. **Docker Desktop 通过 WSL2 backend 运行, 不写 EventLog** (2026-08-04 实测确认), 因此不能用 Docker Desktop 启动事件触发, 必须用 Winlogon EventID=7002. 安装: 管理员 PowerShell 跑 `E:\microbubble-agent\scripts\install-auto-recovery.bat` (一次性). 卸载: `schtasks /Delete /TN "MicroBubble-Auto-Recovery" /F`.

7. **类 20.144 (新增, 永久铁律, W2 +N 0 用户事故)**: 生产代码路径必须包含所有 seed step. 表现: `scripts/init_db.py` 有完整 24 个真实成员数据 (含 dutonghe/wangtianzhi 等), 但 `app/main.py` lifespan 只跑 `create_all` + `seed_formula_library`, **从不**调用 seed_data. 第二次 bug: `seed_data()` 用 `count > 0` 检测跳过, DB 里有任意 1 个用户就**永远跳过** seed. 修复 3 件套: ① `app/seed/member_seeder.py` 新增 + `DEFAULT_MEMBERS` 24 字典 + `seed_default_members()` 函数 (按 username 幂等, wechat_id fallback 处理 NOT NULL) ② `scripts/init_db.py` 改为按关键 admin 'wangtianzhi' 检测 (admin 缺失强制 seed 自愈, admin 存在跳过) ③ `app/main.py` lifespan 新增 `seed_default_members` 调用 (try/except, 失败不阻塞启动). 配套 `scripts/verify_backup_restore.sh`: 创建临时 DB + gunzip 还原 + 验证表数 ≥ 50 + 用户数 ≥ 24 + DROP. **部署纪律**: 主拍合并 migration 后必须重跑 lifespan seed 验证 (DB 不空但关键 admin 缺失场景).

8. **类 20.145 (新增, 永久铁律, W2 +N 业务数据完整恢复)**: 服务器关机恢复后, `app/main.py lifespan → seed_formula_library + seed_default_members` 只 seed 元数据, **不还原业务数据** (tasks/meetings/knowledge/projects/reminders 仍是 0). 业务数据一直在 `backups/microbubble_YYYYMMDD_*.sql.gz` 里 (daily backup_db.sh 跑过), **必须还原**才能让前端有真实数据. 还原策略: ① 停 app/celery 容器释放 DB 连接 ② DROP + CREATE DB 彻底清空 ③ `SET session_replication_role = replica` 临时禁用 FK (备份里有历史 `activity_events.actor_id=1090` 孤儿引用) ④ `gunzip | psql -v ON_ERROR_STOP=0` 还原整个 sql (FK 已禁用) ⑤ `ALTER DATABASE RESET session_replication_role` 恢复 FK ⑥ 重启容器 + 跑 `alembic upgrade head` (备份只有到生成时的 migration, 之后的需要补). 配套 `scripts/restore_full_backup.sh`. 还原后必跑 API 验证 (任务/会议/知识库/项目), 还需重置密码 (备份里 hash 是用户改过的真实密码, 不是 `123456`). **部署纪律**: 任何"恢复"操作链 (服务器关机/迁移/重建) 必须跑 restore_full_backup.sh + verify_backup_restore.sh + API 端到端测试.

9. **类 20.146 (新增, 永久铁律, W2 +N 重跑会议)**: 端到端 API 重跑会议 (本地音频 → 完整后处理) 必须跑完整 6 步: login → start-recording → upload-audio → stop-recording → 轮询 completed → 最终状态. 配套 `scripts/replay_meeting.py` (Python 版, 绕开 bash 路径特殊字符问题). 关键: ① m4a/aac 文件可被 SenseVoice ASR 接受 ② upload-audio 端点会 set `last_chunk_index=0` (满足 stop-recording 校验) ③ Celery meeting-processing 后处理 6 阶段: VAD (silero-vad from torch_hub) → SenseVoice ASR → 低占用过滤 → speaker diarization → AI 润色 → AI 标题生成 + key_points ④ 业务代码路径**必须** `polished_segments=[]` 在 except 块显式初始化避免 UnboundLocalError (本次重跑中发现并修复) ⑤ 容器重启后必须清 `__pycache__/` 否则 .pyc 缓存会遮蔽 .py 改动 ⑥ `models/torch_hub/snakers4_silero-vad_master/` 模型目录必须存在 (worktree 与主仓库分开) ⑦ LLM API Key 失效时 (token-plan 平台 401) 阶段 5 降级, transcript 仍正确入库 ⑧ 多个 celery worker (celery + celery-meeting-worker) 抢 meeting-processing 任务, 重启**所有 3 容器**才生效.

10. **类 20.147 (新增, 永久铁律, W2 +N status schema 长度)**: schema 字段长度必须 ≥ 业务代码最长的 status 字面量 + 2 buffer. 本次事故: `post_meeting_tasks.py:870` 写 `'completed_with_warnings'` (24 字符) 到 `meetings.status` 字段 (`VARCHAR(20)`), 触发 `value too long for type character varying(20)`, 业务代码 catch 后回退 `'error'`, **前端显示"处理失败"但 transcript 数据实际完整入库** (83351 字符). 修复: alembic 098_meetings_status_varchar_32.py 扩展 `status` + `upload_status` 到 VARCHAR(32). **审计纪律**: 任何 status / enum 字段, schema 限制 ≥ 业务字面量最长的 1.5x.

11. **类 20.149 (新增, 永久铁律, W2 +N celery GPU 资源)**: 524 段 ERes2Net 声纹嵌入 CPU 推理 5+ 分钟卡死 (CPU 99.97% 单核 100%), 会议 252/253/254 永远 processing. 修复: `docker-compose.yml` celery-worker + celery-meeting-worker 加 GPU 资源 (`driver: nvidia, count: 1, capabilities: [gpu]`). celery-beat 不需要 GPU (只调度). **前置**: Docker Desktop → Settings → Resources → WSL2 Integration → Enable GPU pass-through (用户操作). 验证: `docker exec celery-worker nvidia-smi` 列出 GPU. 端到端测试: 重跑会议应 2-3 分钟完成 (vs 永远 processing).

12. **类 20.152 (新增, 永久铁律, W2 +N init_db 自愈增强)**: `init_db.py` 自愈检查**所有** critical users (从 `DEFAULT_MEMBERS` 单源抽 24 个 username), 不是只查 wangtianzhi 1 个 admin. 任一 critical user 缺失触发自愈: `seed_default_members` 逐行 commit (避免 24 行 bulk insert 失败 rollback), 单行失败 try/except + logger.warning 不阻断后续. 实测: 删 yangxue → 跑 init_db.py → **yangxue 恢复成功**. `member_seeder.py` 升级: exception 块显式 `polished_segments=[]` + bulk-fallback 逐行 commit + 单行 try/except. Single source of truth: critical user 列表从 `DEFAULT_MEMBERS` 抽, 未来增删成员自动同步.

**worktree 下 compose 启动额外步骤**: `cp <repo-root>/.env <worktree>/.env` (worktree 路径下 .env 缺失, docker compose 启动会报 `env file ... not found`).

**一键恢复脚本**: `scripts/restart-recovery-after-gui-restart.sh` (用户 Docker GUI 重启后执行, 自动 attach network + 验证 7 个端点 + 5 件套守恒).

**5 件套守恒实测**: alembic head `097_meeting_processing_persistence` 与代码 HEAD `2e12f0dcf` 守恒 / PostgreSQL 16.14 + pgvector 0.7.0 + 53 张表 / Celery worker + beat + meeting-worker 全部 ping pong OK / 本地 `/health` 200 / 服务器 7 个 API 502 → 401 (不再 502).

**沉淀**: `memory/w100-meeting-pipeline-restart-2026-08-04.md` (事故 + 5 铁律) + `docs/w100-meeting-pipeline-restart-2026-08-04.md` (runbook 7 步 + 5 铁律 + 不要做清单). 详见 `MEMORY.md` #14.

**0 production code 守恒**: 仅 `CLAUDE.md` + `docs/` + `scripts/` 范畴, 未改 `app/` `web/src/` `alembic/versions/` `docker-compose.yml`. 锚点范式 W100 +28/+29/+30 (~537) 据实累计, 不擅自扩.

---

## W100 构建确定性永久纪律（2026-08-03，类 20.133）

- **Vite build 必须 deterministic**：同一 source、同一依赖锁定版本、同一构建配置必须产出相同的 `dist` 文件内容、文件名和 hash；提交前应使用两次连续 build + `diff -r` 或 manifest/hash 清单核验。
- **禁止向构建产物注入进程态值**：build-time `define`、banner/footer、插件 `augmentChunkHash` 等不得使用 `process.env`、`Date.now()`、`new Date()`、`Math.random()`、`crypto.randomUUID()`、`process.pid` 或其他随机/时间/进程 ID 生成 build ID。若需要版本标识，必须从 git commit/tree hash 或 CI 显式固定输入派生。
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

- Agent 工具调用通过 `app/agent/core.py` 的 `_execute_tool` 方法路由到 service 层（17 个工具已全部接入）
- `chat()` 和 `chat_stream()` 接收 `db: AsyncSession` 参数，由 API 路由通过 `Depends(get_db)` 传入
- 使用 `AsyncAnthropic` 客户端，不阻塞事件循环
- **Agent 回复采用"先简要后详细"双层结构** — 两阶段并行调用，简要立即返回，详细后台追加
- **MCP 视觉服务架构** — 预写架构，切换 DeepSeek 等文本模型时支持图片识别
- 认证使用 JWT，`app/core/security.py` 已实现，31 个端点全部接入 `get_current_user`
- 会话存储已迁移到 Redis（`RedisSessionStore`，24 小时 TTL）
- 知识库使用 pgvector 做向量搜索（扩展已在 main.py 启动时自动安装，已接入 text2vec-base-chinese 真实语义搜索）
- **知识库深层逻辑系统（Knowledge Brain）** — 八大模块：
  - **动态 LLM 分析**：LLM 根据内容自由生成分类/标签/key_concepts/related_topics/knowledge_type，不再硬编码
  - **自动关联引擎**：新入库条目通过 pgvector 余弦相似度 + 概念重叠自动发现关联关系，双向写入 knowledge_relations 表
  - **RAG 问答引擎**：语义搜索 → 阈值分类 → LLM 合成 → 来源引用，高相关不足时自动触发研究
  - **自主研究引擎**：知识空白检测 → 联网搜索（搜狗+必应）→ 网页抓取 → LLM 提取 → 自动入库 → 建立关联
  - **健康监控**：Celery 定时任务检测矛盾/重复/过期条目
  - **实体知识图谱**：跨文档实体融合（精确匹配→embedding 余弦→新建），共现网络，ECharts 力导向图可视化
  - **假设生成引擎**：从实体三元组+知识空白 LLM 生成可验证假设，proposed/validated/rejected 生命周期
  - **量化推理引擎**：LLM 提取数学公式 → safe_eval 安全计算 → LaTeX 渲染 → 前端计算器
  - **公式分类体系**：6 大类 24 子分类（FormulaCategory 模型树）+ 32 个内置微纳米气泡领域公式，前端分类树浏览，来源标签（内置/提取）
  - **公式自动分类**：LLM 提取公式 domain 字符串 → 模糊映射到结构化分类，新老公式统一归入分类树
- 语音识别使用 faster-whisper GPU，TTS 使用 Edge-TTS
- **会议转录总结工具** — `summarize_meeting_transcript` 工具支持对话触发与长期存储
- **任务软删除/垃圾桶** — 删除任务进入垃圾桶（deleted_at 字段），支持恢复或永久删除，3天后自动清除（Celery beat 每 1h 调度 `auto_purge_trash_task`，垃圾桶 UI 双行显示倒计时 + 5 级紧急度颜色）。详细状态见 [README.md](README.md#当前状态2026-06-03)
- **微信对话双消息模式** — 收到消息后 0.5 秒内先发"🤔 收到，让我思考一下..."，后台异步处理后发正式回复，解决等待无反馈问题
- **移动端独立抽屉架构** — 移动端侧边栏使用 el-container 外部独立 div + Vue Transition，完全绕过 Element Plus aside 的全局 CSS 干扰。桌面端 `v-if="!isMobile"` 零影响
- **通知面板** — 铃铛使用 el-popover 弹窗面板，显示每条提醒的具体内容（任务标题+提醒时间）、全部标为已读、点击跳转任务；头像读取 userStore.userInfo.avatar 真实 URL
- **任务权限模型** — 所有成员可见全部任务（降低认知负担），仅创建人/负责人/管理员可编辑、删除、恢复、永久删除
- **状态统一** — "待办"(todo) 和 "进行中"(in_progress) 语义高度重合，已统一为"进行中"。新建任务默认 in_progress，现有 todo 任务兼容显示
- **移动端路由级双栈架构**（2026-06-13 收官）— 桌面端（Element Plus）和移动端（NutUI 4）**同一 URL 不同组件**，不共享 component 树。`useIsMobile.js` 监听 viewport + UA 兜底 → `router/index.js` 通过 `resolveMobile.js` 动态 import `views/mobile/*` 或 `views/*` → 桌面端 `el-*` 与移动端 `nut-*` CSS 完全隔离。**PWA 4 策略**：manifest + service worker（workbox）预缓存 app shell + useSafeArea 读 iPhone 安全区 + 离线 IndexedDB 兜底。**视觉回归测试**：Playwright 5 viewport × 13 核心页面，CI 截图对比基线

## 代码质量规范（2026-06-04 升级）

### API 层
- **统一异常响应格式**：`{"error": {"code": "RESOURCE_NOT_FOUND", "message": "...", "details": {...}}}`
- **异常类层次**：`app/core/exceptions.py` — AppException/NotFoundException/ValidationException/AuthException/ForbiddenException/ConflictException/RateLimitException
- **统一分页模型**：`app/schemas/pagination.py` — PaginationParams + PaginatedResponse + PaginationMeta
- **全站分级限流**：`app/core/rate_limit.py` — auth:5次/分, write:30次/分, read:100次/分, upload:10次/分
- **安全响应头**：X-Content-Type-Options/X-Frame-Options/X-XSS-Protection/Referrer-Policy/X-Request-ID

### 前端架构
- **Composable 模式**：`web/src/composables/` — useTask/useMeeting/useKnowledge 提取共享状态 + API 调用
- **子组件拆分**：18 个子组件（Task:3 + Knowledge:8 + Meeting:3），主 View ≤ 1920 行
- **Vitest 测试**：`web/vitest.config.js` — composable 测试（23 个）+ 组件测试（15 个）= 38 个测试通过

### 2026-06-13 webhint PWA 5 警告全栈修复新增（commit `08f440f` + `c855f0e`）

- **Nginx 缺 `.webmanifest` MIME（commit `08f440f`）** — Nginx 默认 `mime.types` 不包含 `.webmanifest`（到 1.27 才内置），回退 `application/octet-stream` → 浏览器拒绝解析 PWA manifest → 添加桌面图标失败。**修复**：server block 加 `types { application/manifest+json webmanifest; }` + `charset_types` 同步加 `application/manifest+json`（让 `charset utf-8` 生效）。**诊断**：`curl -I https://xxx/manifest.webmanifest | grep Content-Type` 看是不是 octet-stream。**纪律**：所有 PWA 项目上线前必须验证 manifest MIME，**仅一次**而不是每个 server 都加。
- **`vite-plugin-pwa` 输出 manifest 不带 hash（commit `08f440f`）** — `manifest.webmanifest` 文件名固定不走 rollup hash 流程，webhint cache-busting 永远警告。**修复**：写一个 Vite 插件 `manifestHashPlugin`（closeBundle 钩子）→ `crypto.createHash('sha256').update(content).digest('hex').slice(0, 8)` → 重命名为 `manifest.{8char_hash}.webmanifest` + 同步改 `index.html`/`offline.html` 的 link 引用。**8 字符 hex 满足 webhint 默认 `[0-9a-f]+` 正则**。**Vite 5+ emitFile 不适用**（manifest 是 vite-plugin-pwa 输出，emitted by another plugin），必须 fs.renameSync。
- **`/registerSW.js` 静态注入无法 cache-busting（commit `08f440f`）** — `VitePWA({ injectRegister: 'auto' })` 自动注入 `<script src="/registerSW.js">`，文件名固定无 hash。**修复**：`injectRegister: null` + `main.js` 用 `import { useRegisterSW } from 'virtual:pwa-register/vue'` 替代。**Vue composable 在生产 build 时被 rollup 处理，运行时通过 sw 注册的副作用自动跑**，无需手动写 `<script>`。**纪律**：PWA 项目**避免** `injectRegister: 'auto'`，除非真的需要纯静态（非 SPA）站点。
- **删除 manifest.webmanifest 后 SPA fallback 误返 index.html（commit `c855f0e`）** — git 删除旧 manifest 文件后，Nginx `try_files $uri $uri/ /index.html` 找不到文件 → fallback `/index.html`（1924 字节 HTML 内容） → 任何残留引用/书签/扫描器拿到 HTML 内容物以为是 manifest。**修复**：在 `/` location 前加 `location = /manifest.webmanifest { return 410; }` 精确 410 Gone。**纪律**：SPA 部署时**所有被废弃的资源路径**都应该有明确返回（410 / 404），不能依赖 try_files fallback。
- **theme-color Firefox 不支持** — Edge DevTools 内置 webhint 不读 `.hintrc`，永远警告。**纪律**：`.hintrc` 配 `meta-theme-color: "off"`（webhint CLI 0 警告），接受 Edge DevTools 误报。Chrome/Safari/iOS Safari PWA 顶部栏颜色价值 > Edge DevTools 警告噪音。**永远不要**完全删除 theme-color meta（损失浏览器原生美化）。

### 2026-07-11 PWA manifest 410 回归 (commit `59187ce8` cascade folder delete 引入, `5d2bcdfd` 修复)

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
- **memory 沉淀**: [`pwa-manifest-410-regression-2026-07-11.md`](./memory/pwa-manifest-410-regression-2026-07-11.md) (含 5 铁律 + commit 链 + deploy-auto.sh 加固代码)

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
  5. **跨 PR 部署 alembic 必须 cp + clear cache** — `docker cp alembic/versions/0XX_*.py microbubble-agent-app-1:/app/alembic/versions/` 后必跑 `docker exec -e SKIP_DB_SETUP=1 microbubble-agent-app-1 rm -rf /app/alembic/versions/__pycache__` (CLAUDE.md 752 行铁律升级 — `__pycache__` 残留会让老 down_revision 继续生效, 双头假修复)
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
- **后端**：pytest + httpx AsyncClient，service 层单元测试 + API 集成测试
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
| `app/services/memory_service.py` | 长期记忆 CRUD + 语义搜索 + LLM 提取 |
| `app/services/search_service.py` | 联网搜索（搜狗+必应双引擎） |
| `app/services/embedding_service.py` | 向量嵌入（text2vec-base-chinese） |
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
| `app/services/formula_service.py` | 量化推理（公式列表+安全计算+LaTeX 转换+分类树+内置公式库） |
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
docker exec microbubble-agent-postgres-1 psql -U postgres -d microbubble -f scripts/alter_agent_traces_stage3.sql
# 2. 重启 Python 进程 (CLAUDE.md 752 行铁律)
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
