# W-N-BGE-PRE bge-m3 真模型下载预跑 起步 (2026-08-05)

> **派工**: W-N-BGE-PRE +0 startup (W-N-DEPLOY 收口后 + W-N-BGE 真路径回归沉淀后派工, base head `74d1a965e`)
> **目的**: 用 `HF_ENDPOINT=https://hf-mirror.com` 试下载 BAAI/bge-m3 真模型, 失败则留口
> **派工 brief 严禁**: 真模型推理 / 改 .env / 改 docker-compose.yml / 真切换生产
> **关联 commit**: W-N-DEPLOY `74d1a965e` (base) + W-N-BGE 4 commits `04f9c9dcc` `9169e3ae9` `0eaacda64` + `w-n-bge-m3-realpath-closure-2026-08-05.md`

---

## 1. 任务背景

### 1.1 W-N-BGE 真测已沉淀 (本任务前置)

W-N-BGE (`04f9c9dcc` `9169e3ae9` `0eaacda64` + closure) 实测:

- ✅ 本地 CPU 真加载 bge-m3 成功 (`dim=1024, max_seq=8192, load_time=13.15s`)
- ✅ 16.74ms/doc (本地 CPU, batch=32)
- ❌ **GPU 容器内 bge-m3 真模型未下载**: hf-mirror.com 不可达 → mock fallback
- ⏸ 3 决策大门禁 (pass rate / VRAM / latency): 1 通过 + 2 数据不足 → "模型替换延后"

### 1.2 本任务派生

主拍派 W-N-BGE-PRE +0/+1/+2 任务, **仅试试镜像源可用性**, 不真跑推理. 派工 brief 严禁:
- 0 跑 ollama pull bge-m3 (派工 brief 严禁)
- 0 改 W-N-A/B/C/D/E/F/D+/+/ARC/GC/ANC/MEM/G+/OBS/RAG/BGE/GRAND/FILL/D++ commits
- 0 改 alembic/versions/
- 0 改 app/ web/src/
- 0 改 docker-compose.yml
- 0 改 .env
- 0 真切换生产 backend

### 1.3 关键约束

- 工作仓库: `E:\microbubble-agent\` (主仓库)
- 派工锚点: W-N-BGE-PRE +0..+2 (3 commits)
- 严格只在 1 docs + 2 memory 文件范畴

---

## 2. 起步 6 项 (W73 铁律)

### 2.1 派工 brief vs 实测错配排查

| 派工 brief 假设 | 实测 | 决策 |
|---|---|---|
| 派工起点 base head `74d1a965e` | ✅ `git log --oneline -1` = `74d1a965e docs(deploy-status): W-N-DEPLOY 部署状态验证报告 + 起步 + 收口` | ✅ 守恒 |
| 锚点范式 `W-N-BGE-PRE +0..+2` | 派工 brief 排定 +0/+1/+2, 3 commits | ✅ 沿用 |
| W-N-BGE 报告"容器内 hf-mirror.com 不可达" | ✅ W-N-BGE +3 closure memory 第 95 行 (`❌ hf-mirror.com 不可达`) | ✅ 复用派工前提 |
| `HF_ENDPOINT=https://hf-mirror.com` 已在 .env | ✅ `cat .env` 含 `HF_ENDPOINT=https://hf-mirror.com` + `HF_HUB_OFFLINE=1` | ✅ 沿用 |

### 2.2 锚点范式

W-N-BGE-PRE +0 (本 memory startup) → +1 (1 commit, 真测报告 + docs 留口) → +2 (1 commit, memory 收口 + 5 件套守恒).

派工 brief 严禁跳锚点, 沿用 W-N-BGE 锚点范式 (~575 → ~578 据实累计).

### 2.3 5 件套守恒 (派工 brief 严禁违反)

- 件 1: alembic 1 head `105_fix_drift` (W-N-DEPLOY 收口后) 守恒 (本任务不动)
- 件 2: pytest 全套件 PASS (本任务不强求, 沿用 W-N-DEPLOY baseline)
- 件 3: PWA build (本任务不涉及 frontend, 沿用 W-N-DEPLOY baseline)
- 件 4: **0 production code 改动** (派工 brief 严禁改 `app/` `web/src/` `alembic/versions/`)
- 件 5: 锚点范式 W-N-BGE-PRE +0..+2 据实累计

### 2.4 严禁清单 (派工 brief 严禁)

- ❌ 改 `app/services/embedding_service.py` 既有 4 个 API
- ❌ 改 `app/agent/chat_engine.py`
- ❌ 改 `alembic/versions/`
- ❌ 改 W-N-A/B/C/D/E/F/D+/+/ARC/GC/ANC/MEM/G+/OBS/RAG/BGE/GRAND/FILL/D++ commits
- ❌ 真切换生产 bge-m3 backend (`EMBEDDING_BACKEND=bge_m3` 仅 bench, 不改 .env)
- ❌ 改 plan 文件
- ❌ 跑 `docker exec -e HF_ENDPOINT=... ollama pull bge-m3` (派工 brief 严禁)
- ❌ 改 .env / docker-compose.yml

### 2.5 任务路径

派工前 `git log --oneline -3` 验证 base head ✅. 本任务 W-N-BGE-PRE +1 执行:

1. Step 1: `docker exec microbubble-agent-app-1 env | grep HF_ENDPOINT` (看当前 HF env)
2. Step 2: 用 `HF_ENDPOINT=https://hf-mirror.com` 试加载 BAAI/bge-m3 真模型
3. Step 3: 如 OK → 写 prep 报告 (耗时 / VRAM / 1000 题 bench 估算); 如 FAIL → 写决策文档 (失败原因 + 备选方案)
4. Step 4: 写 `docs/w-n-bge-m3-preload-2026-08-05.md` 留口 (派工 brief 严禁擅自派工)
5. Step 5: commit docs/memory 范畴

### 2.6 决策门禁 (派工 brief 严禁跳过)

**派工后主拍决策节点**: 容器预下载 bge-m3 真模型成功后, 主拍决策是否派 W-N-BGE +N 跑真 pass rate + VRAM + 决策"切换/暂不切/投资新候选".

---

## 3. 派工 brief 路径起点 base head 验证

```
$ git log --oneline -3
74d1a965e docs(deploy-status): W-N-DEPLOY 部署状态验证报告 + 起步 + 收口 (W-N-DEPLOY +0/+1/+2)
3d45465c1 docs(memory): W-N-MIN (b) 实施收口 (W-N-MIN +6)
d49057d39 docs(memory): CLAUDE.md 顶层 mini-N 减负 (W-N-MIN +5)
```

✅ base head `74d1a965e` 守恒. 派工起点合法.

---

## 4. 起步沉淀

**派工前提确认**: 本任务起点 = `74d1a965e` + 5 件套守恒 + 严禁清单 + HF_ENDPOINT 真试.

**W-N-BGE-PRE +1 待执行**: 实测 HF_ENDPOINT 真加载 + 写 prep 报告 / 决策文档 + 留口.

**W-N-BGE-PRE +2 待执行**: 5 件套守恒实测 + 据实上报收口.

**派工 v6 §13 仓库实情真查**: 本任务起点已实测 (W-N-BGE realpath + W-N-DEPLOY 收口), 派工 brief 假设路径守恒.
