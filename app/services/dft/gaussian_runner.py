"""Gaussian 16W 包装 — 复用 E:\\sci-software\\workflows\\gaussian_runner.py

提供 run_gaussian_calculation 同步接口 + run_gaussian_async 异步接口 (FastAPI 友好)。
底层 import 自 E:\\sci-software\\workflows\\gaussian_runner.py, 不重写算法。

调用方:
- app/services/dft/tool_definitions.py (@tool run_gaussian_calculation)
- app/api/v1/dft.py (POST /dft/gaussian)
"""
from __future__ import annotations

import json
import logging
import time
from pathlib import Path
from typing import Any

from app.services.dft.paths import DFT_OUTPUT_ROOT, SCISOFTWARE_BASE, workflows_available

logger = logging.getLogger("microbubble.dft.gaussian")

# 默认 Gaussian 16W 路径 (E:/sci-software/g16w → D:/G16W symlink)
DEFAULT_GAUSSIAN_BIN = str(SCISOFTWARE_BASE / "g16w" / "g16.exe")


def _import_workflow():
    """懒 import E:\\sci-software\\workflows\\gaussian_runner。

    sys.path 已由 paths.py 注入, 这里直接 import。
    """
    if not workflows_available():
        raise RuntimeError(
            f"sci-software workflows not available at "
            f"{SCISOFTWARE_BASE}/workflows — install E:\\sci-software first"
        )
    try:
        from gaussian_runner import (
            gen_gjf,
            submit_gjf,
            parse_log,
            GaussianResult,
        )
    except ImportError as e:
        raise RuntimeError(
            f"Failed to import gaussian_runner from {SCISOFTWARE_BASE}/workflows: {e}"
        ) from e
    return gen_gjf, submit_gjf, parse_log, GaussianResult


def run_gaussian_calculation(
    smiles: str,
    xc: str = "B3LYP",
    basis: str = "6-31G(d)",
    job: str = "opt",
    solvent: str = "water",
    charge: int = 0,
    multiplicity: int = 1,
    nproc: int = 8,
    mem: str = "8GB",
    timeout_s: float = 7200.0,
    gaussian_path: str = DEFAULT_GAUSSIAN_BIN,
    job_id: str | None = None,
) -> dict[str, Any]:
    """跑 Gaussian 16W DFT 计算 (同步阻塞)。

    Args:
        smiles: 分子 SMILES
        xc: 泛函
        basis: 基组
        job: 任务类型 (opt / sp / freq)
        solvent: 隐式溶剂 (写入 .gjf comment, 实际 PCM 关键字由 caller 拼)
        charge / multiplicity / nproc / mem: Gaussian 输入参数
        timeout_s: 单任务超时秒
        gaussian_path: g16.exe 路径
        job_id: 任务 ID (用于输出目录命名)

    Returns:
        dict {energy_hartree, energy_ev, n_opt_steps, converged, log_path, elapsed_s,
              xc, basis, job, smiles, error_msg}
    """
    gen_gjf, submit_gjf, parse_log, GaussianResult = _import_workflow()

    t0 = time.time()
    job_id = job_id or f"gauss_{int(t0)}"
    work_dir = Path(DFT_OUTPUT_ROOT) / job_id
    work_dir.mkdir(parents=True, exist_ok=True)

    # 1) 写 .smi → gen_gjf
    smi_path = work_dir / "input.smi"
    smi_path.write_text(smiles + "\n", encoding="utf-8")

    # 隐式溶剂 — 简化: 拼到 title 行
    title = f"{smiles} {xc}/{basis} {job} solvent={solvent}"
    try:
        gjf_path = gen_gjf(
            smi_path, work_dir,
            xc=xc, basis=basis, job=job,
            charge=charge, multiplicity=multiplicity,
            nproc=nproc, mem=mem, title=title,
        )
    except Exception as e:
        return {
            "status": "failed",
            "stage": "gen_gjf",
            "error_msg": repr(e),
            "smiles": smiles, "xc": xc, "basis": basis, "job": job,
            "work_dir": str(work_dir),
            "elapsed_s": time.time() - t0,
        }

    # 2) submit_gjf (阻塞)
    try:
        log_path = submit_gjf(
            gjf_path, gaussian_path=gaussian_path, timeout=timeout_s,
        )
    except Exception as e:
        return {
            "status": "failed",
            "stage": "submit_gjf",
            "error_msg": repr(e),
            "gjf_path": str(gjf_path),
            "smiles": smiles, "xc": xc, "basis": basis, "job": job,
            "work_dir": str(work_dir),
            "elapsed_s": time.time() - t0,
        }

    # 3) parse_log
    parsed: GaussianResult = parse_log(log_path)
    elapsed = time.time() - t0

    result = {
        "status": "success" if parsed.converged else "completed_with_warnings",
        "energy_hartree": parsed.energy_hartree,
        "energy_ev": parsed.energy_ev,
        "n_opt_steps": parsed.n_opt_steps,
        "converged": parsed.converged,
        "log_path": str(log_path),
        "gjf_path": str(gjf_path),
        "work_dir": str(work_dir),
        "smiles": smiles,
        "xc": xc,
        "basis": basis,
        "job": job,
        "solvent": solvent,
        "elapsed_s": round(elapsed, 2),
        "extra": parsed.extra or {},
    }
    if parsed.error_msg:
        result["error_msg"] = parsed.error_msg
        result["status"] = "failed"
    return result


async def run_gaussian_async(
    smiles: str, **kwargs,
) -> dict[str, Any]:
    """异步包装 — FastAPI / Celery 友好, 内部用 asyncio.to_thread 跑阻塞。

    Args: 同 run_gaussian_calculation
    """
    import asyncio
    return await asyncio.to_thread(run_gaussian_calculation, smiles, **kwargs)


def health_check() -> dict[str, Any]:
    """Gaussian 工具健康状态 — 必查 g16.exe 与 workflows 路径"""
    from app.services.dft.paths import gaussian_binary_exists, workflows_available
    return {
        "tool": "gaussian",
        "workflows_available": workflows_available(),
        "g16_exists": gaussian_binary_exists(),
        "g16_path": DEFAULT_GAUSSIAN_BIN,
    }
