"""DFT/MD 工具服务包 — Phase 5 集成 (E:\\sci-software 接入).

设计原则:
- 复用 E:\\sci-software\\workflows 下的 gaussian_runner / gromacs_runner / mace_relaxation,
  不重写底层算法。
- 暴露统一的 Python API (gaussian_runner / gromacs_runner / mace_runner / multimodel_runner)
  + Agent @tool 装饰器工具 (tool_definitions)。
- 任务状态用 dft_jobs 表 (alembic 099) 持久化, 异步通过 asyncio 跑, 不阻塞 HTTP。

调用方:
- app/agent/tools/dft_tools.py (Agent @tool)
- app/api/v1/dft.py (FastAPI 路由)
- app/services/dft/integrations/* (legacy/高级用户直接 import)
"""

__all__ = [
    "gaussian_runner",
    "gromacs_runner",
    "mace_runner",
    "multimodel_runner",
    "tool_definitions",
    "SCISOFTWARE_BASE",
    "WORKFLOWS",
    "DFT_OUTPUT_ROOT",
]

from app.services.dft.paths import SCISOFTWARE_BASE, WORKFLOWS, DFT_OUTPUT_ROOT

# 触发工具注册 (decorator side-effect)
from app.services.dft import (
    gaussian_runner,  # noqa: F401
    gromacs_runner,  # noqa: F401
    mace_runner,  # noqa: F401
    multimodel_runner,  # noqa: F401
    tool_definitions,  # noqa: F401
)
