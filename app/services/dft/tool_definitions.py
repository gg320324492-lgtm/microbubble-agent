"""DFT/MD 工具统一健康检查 — 列出所有 4 个后端的可用性"""
from __future__ import annotations

from typing import Any


def list_available_dft_tools() -> dict[str, Any]:
    """列出所有 DFT/MD 工具和它们的健康状态。

    Returns:
        {
            "status": "success",
            "tools": [
                {"name": "gaussian", "available": bool, "details": {...}},
                {"name": "gromacs",  "available": bool, "details": {...}},
                {"name": "mace",     "available": bool, "details": {...}},
                {"name": "pyscf",    "available": bool, "details": {...}},
            ],
            "rich_block_type": "dft_tools"
        }
    """
    from app.services.dft.gaussian_runner import health_check as gauss_hc
    from app.services.dft.gromacs_runner import health_check as gmx_hc
    from app.services.dft.mace_runner import health_check as mace_hc
    from app.services.dft.multimodel_runner import health_check as pyscf_hc

    healths = [
        ("gaussian", gauss_hc()),
        ("gromacs", gmx_hc()),
        ("mace", mace_hc()),
        ("pyscf", pyscf_hc()),
    ]
    tools = []
    for name, hc in healths:
        # available 判定: workflows_available=True + 各自专属 check
        if name == "gaussian":
            avail = hc.get("workflows_available") and hc.get("g16_exists")
        elif name == "gromacs":
            avail = hc.get("workflows_available") and hc.get("wsl_gromacs")
        elif name == "mace":
            avail = hc.get("mace_python")
        elif name == "pyscf":
            avail = hc.get("workflows_available")
        else:
            avail = False
        tools.append({
            "name": name,
            "available": avail,
            "details": hc,
        })
    return {
        "status": "success",
        "tools": tools,
        "count": len(tools),
        "available_count": sum(1 for t in tools if t["available"]),
        "rich_block_type": "dft_tools",
    }
