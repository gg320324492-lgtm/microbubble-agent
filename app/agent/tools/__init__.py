"""Agent 工具集合 — 按业务域拆分

每个子模块用 @tool 装饰器注册工具到 TOOL_REGISTRY。
import 这个包会触发所有子模块加载，所有工具自动注册。

迁移策略：
- 新工具直接用 @tool 装饰器
- 旧 core.py._execute_tool 的 25 个 if/elif 通过 dispatch_legacy 回退（tool_registry.py）
- 本目录实现高频工具 + 新增工具，逐步替换 legacy
"""

# 触发所有工具模块的 @tool 装饰器执行
from app.agent.tools import meeting_tools  # noqa: F401
from app.agent.tools import task_tools  # noqa: F401
from app.agent.tools import member_tools  # noqa: F401

__all__ = [
    "meeting_tools",
    "task_tools",
    "member_tools",
]
