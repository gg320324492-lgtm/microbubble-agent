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
from app.agent.tools import project_tools  # noqa: F401
from app.agent.tools import formula_tools  # noqa: F401
from app.agent.tools import hypothesis_tools  # noqa: F401
from app.agent.tools import knowledge_tools  # noqa: F401
from app.agent.tools import memory_tools  # noqa: F401
from app.agent.tools import search_tools  # noqa: F401

# 兼容旧 import 路径：旧 core.py 仍 `from app.agent.tools import TOOLS`
# 由于 app/agent/tools.py 文件被忽略（Python 优先选包），在此 shim 导出
from app.agent.tool_registry import get_all_tool_schemas

TOOLS = get_all_tool_schemas()

__all__ = [
    "meeting_tools",
    "task_tools",
    "member_tools",
    "project_tools",
    "formula_tools",
    "hypothesis_tools",
    "knowledge_tools",
    "memory_tools",
    "search_tools",
    "TOOLS",
]
