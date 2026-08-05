"""GROMACS 包装 — 复用 E:\\sci-software\\workflows\\gromacs_runner.py

通过 WSL 调用 GROMACS, 提供 prep_system + energy_minimize + run_md + analyze_md 同步包装。
"""
from __future__ import annotations

import asyncio
import logging
import time
from pathlib import Path
from typing import Any

from app.services.dft.paths import (
    DFT_OUTPUT_ROOT,
    workflows_available,
    wsl_gromacs_available,
)

logger = logging.getLogger("microbubble.dft.gromacs")


def _import_workflow():
    if not workflows_available():
        raise RuntimeError("sci-software workflows not available")
    from gromacs_runner import (  # type: ignore
        prep_system,
        energy_minimize,
        run_md,
        analyze_md,
    )
    return prep_system, energy_minimize, run_md, analyze_md


def submit_gromacs_md(
    smiles: str,
    n_molecules: int = 100,
    box_nm: float = 3.0,
    time_ns: float = 1.0,
    temperature_K: float = 300.0,
    wsl_distro: str = "Ubuntu",
    job_id: str | None = None,
) -> dict[str, Any]:
    """跑 GROMACS MD 模拟 (同步, WSL 阻塞)。

    完整流程: prep_system → energy_minimize → run_md → (可选) analyze_md
    """
    prep_system, energy_minimize, run_md, analyze_md = _import_workflow()
    t0 = time.time()
    job_id = job_id or f"gmx_{int(t0)}"
    work_dir = Path(DFT_OUTPUT_ROOT) / job_id
    work_dir.mkdir(parents=True, exist_ok=True)

    out: dict[str, Any] = {
        "tool": "gromacs",
        "smiles": smiles,
        "n_molecules": n_molecules,
        "box_nm": box_nm,
        "time_ns": time_ns,
        "temperature_K": temperature_K,
        "work_dir": str(work_dir),
        "elapsed_s": 0.0,
    }

    if not wsl_gromacs_available(wsl_distro):
        out["status"] = "unavailable"
        out["error_msg"] = (
            f"WSL '{wsl_distro}' 上 gmx 不可用 — 装 GROMACS 或检查 WSL 分发版"
        )
        out["elapsed_s"] = round(time.time() - t0, 2)
        return out

    try:
        # 1) prep
        paths = prep_system(
            smiles, n_mol=n_molecules, box_size=box_nm, output_dir=work_dir,
        )
        out["gro_path"] = str(paths["gro"])
        out["top_path"] = str(paths["top"])

        # 2) energy minimize
        em = energy_minimize(
            paths["gro"], None, work_dir / "em", wsl_distro=wsl_distro,
        )
        out["em_gro"] = str(em["gro"])
        out["em_log"] = str(em["log"])

        # 3) run_md
        md = run_md(
            em["gro"], work_dir / "md",
            time_ns=time_ns, temperature_k=temperature_K,
            wsl_distro=wsl_distro,
        )
        out["trajectory_path"] = str(md["xtc"])
        out["md_log"] = str(md["log"])
        out["final_gro"] = str(md["gro"])
        out["status"] = "success"
    except Exception as e:
        out["status"] = "failed"
        out["error_msg"] = repr(e)
        logger.exception("GROMACS MD failed")
    out["elapsed_s"] = round(time.time() - t0, 2)
    return out


async def submit_gromacs_async(
    smiles: str, **kwargs,
) -> dict[str, Any]:
    return await asyncio.to_thread(submit_gromacs_md, smiles, **kwargs)


def health_check() -> dict[str, Any]:
    return {
        "tool": "gromacs",
        "workflows_available": workflows_available(),
        "wsl_gromacs": wsl_gromacs_available(),
    }
