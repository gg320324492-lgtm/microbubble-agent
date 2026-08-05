# DFT/MD 工具集成 (Phase 5)

把 `E:\sci-software\workflows\` 下的 Gaussian/GROMACS/MACE 包装代码, 集成到 MicroBubble Agent 后端。
纯开源 PySCF 走 WSL, 作为无商业许可的备选。

## 工具列表

| 工具 | 后端 | 许可 | 速度 | 适用场景 |
|------|------|------|------|----------|
| `run_gaussian_calculation` | Gaussian 16W (Windows g16.exe) | 商业 | 慢 (s-min/分子) | 精度最高 / 工业标准 |
| `submit_gromacs_md`        | GROMACS (WSL Ubuntu)         | LGPL  | 中 (ns/天)    | 经典 MD / 大体系 |
| `mace_relax_structure`    | MACE-MP-0 (GPU)              | Apache| 快 (s/分子)   | 大量筛选 / 粗优化 |
| `run_pyscf_calculation`   | PySCF (WSL Ubuntu)           | BSD   | 中             | 无商业许可场景 |
| `list_available_dft_tools`| 健康检查                      | -     | 即时           | 看哪个工具能用 |

## 快速开始

### 1. Agent 工具 (LLM 调用)

LLM 通过 `app.agent.tools.dft_tools` 自动发现 5 个 @tool 装饰器, 描述写在 docstring。
用户在小气助手聊天说"帮我算水的能量", LLM 就会调 `run_gaussian_calculation(smiles="O", job="sp")`。

### 2. FastAPI 端点

```bash
# 列出可用工具
curl http://localhost:8000/api/v1/dft/tools

# 提交 Gaussian 任务 (异步, 立即返回 task_id)
curl -X POST http://localhost:8000/api/v1/dft/gaussian \
     -H "Content-Type: application/json" \
     -d '{"smiles": "O", "xc": "B3LYP", "basis": "6-31G(d)", "job": "opt"}'
# 返 {"task_id": "abc123...", "status": "queued", "tool": "gaussian", "submit_time": "..."}

# 查状态
curl http://localhost:8000/api/v1/dft/status/abc123...

# 拿结果
curl http://localhost:8000/api/v1/dft/result/abc123...
```

### 3. Python 直接调用 (脚本/批处理)

```python
from app.services.dft import (
    run_gaussian_calculation,
    submit_gromacs_md,
    mace_relax_structure,
    run_pyscf_calculation,
    list_available_dft_tools,
)

# 健康检查
print(list_available_dft_tools())

# Gaussian 单点
result = run_gaussian_calculation("O", xc="B3LYP", basis="6-31G(d)", job="sp")
print(result["energy_hartree"])  # -76.4 (近似)
```

## 路径配置 (环境变量)

| 变量 | 默认 | 备注 |
|------|------|------|
| `SCISOFTWARE_BASE` | `E:/sci-software` | sci-software 根目录 |
| `SCISOFTWARE_WORKFLOWS` | `<SCISOFTWARE_BASE>/workflows` | workflow 文件夹 |
| `DFT_OUTPUT_ROOT` | `<project>/data/dft_jobs` | 任务输出根目录 |

## 数据库

新建 1 张表 `dft_jobs` (alembic 099), 记录每个任务:
- `id` (UUID) / `user_id` / `tool` / `smiles` / `params` (JSONB)
- `status` (queued/running/success/failed/unavailable)
- `result` (JSONB) / `log_path` / `submit_time` / `finish_time`

异步任务结果先落内存 dict, BackgroundTasks 完成后写 dft_jobs 表。

## 部署

```bash
# 1. 同步代码
git pull

# 2. 跑 alembic
docker exec microbubble-agent-app-1 alembic upgrade head
# 应输出 "running upgrade 102_voiceprint_halfvec -> 099_add_dft_jobs"

# 3. 验证 tools 注册
docker exec microbubble-agent-app-1 python -c "
from app.agent.tools.dft_tools import list_available_dft_tools
from app.services.dft.tool_definitions import list_available_dft_tools as f
import json; print(json.dumps(f(), indent=2))
"

# 4. 健康检查端点
curl http://localhost:8000/api/v1/dft/tools
```

## 测试

```bash
SKIP_DB_SETUP=1 python -m pytest tests/test_dft_tools.py -v
# 15 passed in 1.33s
```

测试覆盖:
- 5 工具 import + @tool 注册
- 5 工具 Pydantic schema
- Gaussian e2e (mock g16)
- GROMACS e2e (mock WSL)
- MACE e2e (mock calculator)
- PySCF e2e (mock subprocess)
- 3 FastAPI 端点
- 健康检查
- PySCF energy 解析

## 真实环境前置

| 工具 | 必须 |
|------|------|
| Gaussian | `E:\G16W\g16.exe` 或 `E:\sci-software\g16w\g16.exe` + license server |
| GROMACS  | WSL Ubuntu + `apt install gromacs` + `command -v gmx` |
| MACE     | `pip install mace-torch` (GPU 加速, CUDA 11+) |
| PySCF    | WSL Ubuntu + `pip install pyscf` |
| rdkit    | `pip install rdkit` (MACE SMILES→xyz 必需) |

健康检查 `GET /dft/tools` 会列出每个的 `available: bool` + `details`。
