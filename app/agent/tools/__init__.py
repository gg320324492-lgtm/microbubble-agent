"""Agent 工具集合 — 按业务域拆分

每个子模块用 @tool 装饰器注册工具到 TOOL_REGISTRY。
import 这个包会触发所有子模块加载，所有工具自动注册。

2026-06-14 方案 C 收官: 旧 core.py._execute_tool 的 25 个 if/elif 已全部迁移完毕 (commit 5ce1203 系列)
2026-07-12 死代码清理: 移除 dispatch_legacy 桥接注释 (core.py 已删, 全部走 @tool)
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
from app.agent.tools import feedback_tools  # noqa: F401
from app.agent.tools import voice_tools  # noqa: F401
from app.agent.tools import extra_task_tools  # noqa: F401
from app.agent.tools import research_tools  # noqa: F401
from app.agent.tools import graph_tools  # noqa: F401
from app.agent.tools import transcript_tools  # noqa: F401
from app.agent.tools import meeting_create_tools  # noqa: F401
from app.agent.tools import drive_tools  # noqa: F401  # PR2.9 课题组网盘工具

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
    "feedback_tools",
    "voice_tools",
    "extra_task_tools",
    "research_tools",
    "graph_tools",
    "transcript_tools",
    "meeting_create_tools",
    "drive_tools",
    "TOOLS",
]
