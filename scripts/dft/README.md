# DFT/MD 工具集成 — 2026-08-30 起外置到 E:\dft-service

> **架构变更**: 计算实现已从本仓库整体迁出到独立服务 `E:\dft-service\`
> (FastAPI + SQLite + scichem python driver, 补齐 Psi4 / auto 选路 / 鉴权 / 持久化,
> 并修复 8 个功能缺口 + GROMACS 链路 6 个真 bug)。
> 本仓库只剩 **HTTP 客户端** + **agent @tool** + **API 薄代理**。

## 当前结构

| 层 | 位置 | 说明 |
|----|------|------|
| 独立服务 | `E:\dft-service\` | 5 后端 (Gaussian/GROMACS/MACE/PySCF/Psi4) + auto 智能选路, 全部计算在这边 |
| HTTP 客户端 | `app/services/dft_client.py` | submit_and_wait (提交+轮询) / dft_get / dft_post |
| Agent 工具 | `app/agent/tools/dft_tools.py` | 同名 5 个 @tool, schema 兼容, LLM 无感 |
| API 代理 | `app/api/v1/dft.py` | `/api/v1/dft/*` 路径形状不变, 前端 DftView 无感 |
| 配置 | `DFT_SERVICE_URL` / `DFT_SERVICE_API_KEY` (app/config.py) | 默认 http://127.0.0.1:8620 |

## 工具列表 (5 后端)

| 工具 | 后端 | 许可 | 速度 | 适用场景 |
|------|------|------|------|----------|
| `run_gaussian_calculation` | Gaussian 16W (g16.exe) | 商业 | 慢 (s-min/分子) | 精度最高 / 工业标准, SMD 溶剂 |
| `submit_gromacs_md`        | GROMACS 2023.3 (WSL Ubuntu-24.04) | LGPL | 中 | 经典 MD / 大体系 |
| `mace_relax_structure`     | MACE-MP (GPU cu128) | Apache | 快 (s/分子) | 大量筛选 / 粗优化 |
| `run_pyscf_calculation`    | PySCF (scichem / WSL 回退) | BSD | 中 | 无商业许可, C-PCM + UKS |
| `list_available_dft_tools` | 健康检查 (含 Psi4) | - | 即时 | 看哪个工具能用 |

## 启动依赖

microbubble 侧无需任何计算环境, 只需 dft-service 在跑:

```bash
# 计算机上 (dft-service)
cd E:\dft-service
.venv\Scripts\python run.py          # → http://127.0.0.1:8620
```

服务没起时 agent 工具返回 `status=unavailable` (不抛异常, LLM 可读)。

## 快速开始

### 1. Agent 工具 (LLM 调用) — 不变

用户在小气助手聊天说"帮我算水的能量", LLM 调 `run_gaussian_calculation(smiles="O", job="sp")`,
工具内部提交到 dft-service + 轮询到终态, 返回能量 dict。

### 2. FastAPI 端点 — 形状不变

```bash
curl http://localhost:8000/api/v1/dft/tools
curl -X POST http://localhost:8000/api/v1/dft/gaussian \
     -H "Content-Type: application/json" \
     -d '{"smiles": "O", "xc": "B3LYP", "basis": "6-31G(d)", "job": "opt"}'
curl http://localhost:8000/api/v1/dft/result/<task_id>
curl "http://localhost:8000/api/v1/dft/jobs?status=success"   # 新增: 任务列表
```

### 3. 直连 dft-service (跳过本项目)

```bash
curl http://127.0.0.1:8620/dft/tools
curl -X POST http://127.0.0.1:8620/dft/auto \
     -d '{"smiles":"O","task":"optimize","quality":"fast"}' \
     -H "Content-Type: application/json"
```

## 数据库

- **dft-service**: SQLite `E:\dft-service\data\dft_service.db` (任务真源, 重启可查)
- **本项目**: PostgreSQL `dft_jobs` 表 (alembic 099) 保留但不再写入, 未删 (无风险)

## 测试

```bash
SKIP_DB_SETUP=1 python -m pytest tests/test_dft_tools.py -v
# 9 passed — mock httpx; 真实计算链路测试在 E:\dft-service\tests\ (14 passed)
```
