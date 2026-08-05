# DFT 工具包架构说明

## 目录结构

```
app/services/dft/
├── __init__.py              # 包入口, re-export 5 个工具
├── paths.py                 # 路径常量 + 3 个 health-check helper
├── gaussian_runner.py       # Gaussian 16W 包装 (E:\sci-software\workflows\gaussian_runner.py)
├── gromacs_runner.py        # GROMACS 包装 (E:\sci-software\workflows\gromacs_runner.py)
├── mace_runner.py           # MACE-MP 包装 (E:\sci-software\workflows\mace_relaxation.py)
├── multimodel_runner.py     # PySCF (WSL) + 统一接口预留
├── tool_definitions.py      # list_available_dft_tools 聚合健康检查
└── INTEGRATION.md           # 本文件
```

## 调用链

```
┌─────────────────────────────────────────────────────────────────┐
│  LLM Agent (app/agent/tools/dft_tools.py)                       │
│  @tool decorator 注册 5 个工具 → TOOL_REGISTRY                  │
│  LLM 在 chat 时根据描述选 tool → dispatch_tool                  │
└─────────────────────────────┬───────────────────────────────────┘
                              │ async 调用
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│  app/services/dft/{gaussian,gromacs,mace,pyscf}_runner.py       │
│  内部 asyncio.to_thread(submit_xxx, ...) 阻塞 IO 异步化         │
└─────────────────────────────┬───────────────────────────────────┘
                              │ import + sys.path 注入
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│  E:\sci-software\workflows\                                       │
│  gaussian_runner.py / gromacs_runner.py / mace_relaxation.py    │
│  真实跑 g16.exe / wsl gmx / mace-torch                          │
└─────────────────────────────────────────────────────────────────┘

平行通道:
┌─────────────────────────────────────────────────────────────────┐
│  FastAPI (app/api/v1/dft.py)                                    │
│  POST /dft/{gaussian,gromacs,mace,pyscf} → BackgroundTasks      │
│  _TASKS 内存 dict + dft_jobs 表双写                              │
└─────────────────────────────────────────────────────────────────┘
```

## 关键设计

### 1. 不重写 sci-software
- 路径常量集中在 `paths.py`, sys.path 自动注入 `E:\sci-software\workflows`
- 4 个 runner 都通过 `_import_workflow()` 懒 import, 避免模块加载时依赖
- 业务代码只调 `gen_gjf/submit_gjf/parse_log/prep_system/relax/...`, 不重写算法

### 2. 健康检查
- 4 个 health_check 各自独立 (g16.exe 存在 / wsl gmx 可用 / mace-torch 装好 / workflows 路径)
- `list_available_dft_tools` 聚合, 返回 dict 给 Agent 和 FastAPI 端点

### 3. 异步策略
- 同步: `run_gaussian_calculation(smiles, ...)` 直接调, 阻塞 30s-数小时
- 异步包装: `await run_gaussian_async(...)` 内部 `asyncio.to_thread`
- FastAPI 端点: BackgroundTasks + 内存 dict + dft_jobs 表落库

### 4. 错误处理
- 不可用 (license server 死 / WSL 没装) → 返回 `status="unavailable"` 不抛异常
- 计算失败 (Gaussian 不收敛) → `status="failed"` + `error_msg`
- 业务层永远不 raise, 把异常包成 dict 让 LLM 知道

### 5. dft_jobs 表 (alembic 099)
- user_id 可空 (允许未登录用户跑)
- params / result 走 JSONB, 灵活存任何 dict
- 5 个索引: user_id / tool / status / (tool,status) / (user_id, submit_time)
- 跨进程查结果用 `GET /dft/result/{task_id}` 回退 DB 查询

## 环境变量

```python
# app/services/dft/paths.py
SCISOFTWARE_BASE = "E:/sci-software"  # 改路径只改这里
WORKFLOWS = "<SCISOFTWARE_BASE>/workflows"
DFT_OUTPUT_ROOT = "<project>/data/dft_jobs"
```

## 升级到 Celery (后续)

当前 BackgroundTasks 模式在进程重启后会丢内存 dict, 结果只能从 DB 查。
Phase 6 建议把 `_run_and_store` 改成 Celery task, 加 redis broker,
保留 dft_jobs 表做持久化 + 状态机。

## 已知限制

1. **WSL 路径硬编码 Ubuntu** — 改 distro 需 caller 传 `wsl_distro` 参数
2. **dft_jobs 表 user_id 允许 0** — 未登录用户 (TaskIdResponse 不要求鉴权)
3. **mace-torch / rdkit 装在主项目 Python** — 否则走 `use_wsl=True` 或 `mace_python_available()` 拦截
4. **BackgroundTasks 不是分布式** — 多 worker 部署时改 Celery
