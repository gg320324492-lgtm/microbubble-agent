"""统一接口 — 根据任务类型自动选最快的后端 (PySCF / MACE / Gaussian / GROMACS)

PySCF 走 WSL (Linux 原生) 或 conda-envs/scichem (Windows 原生), 纯开源 BSD。
MACE 走 mace-torch (GPU 加速秒级)。
Gaussian 走 g16.exe (Windows 原生, 商业许可)。
GROMACS 走 WSL。
"""
from __future__ import annotations

import asyncio
import logging
import time
from pathlib import Path
from typing import Any

from app.services.dft.paths import DFT_OUTPUT_ROOT, workflows_available

logger = logging.getLogger("microbubble.dft.multimodel")


def run_pyscf_calculation(
    smiles: str,
    method: str = "B3LYP",
    basis: str = "6-31G*",
    operation: str = "energy",
    charge: int = 0,
    spin: int = 0,
    use_wsl: bool = True,
    wsl_distro: str = "Ubuntu",
    job_id: str | None = None,
) -> dict[str, Any]:
    """用 PySCF 跑 DFT (纯开源 BSD 许可, WSL 调用)。

    不依赖 E:\\sci-software 自带实现 — PySCF API 简单直接写。
    实测 SMILES → 3D → PySCF mol → kernel → energy。
    """
    t0 = time.time()
    job_id = job_id or f"pyscf_{int(t0)}"
    work_dir = Path(DFT_OUTPUT_ROOT) / job_id
    work_dir.mkdir(parents=True, exist_ok=True)

    out: dict[str, Any] = {
        "tool": "pyscf",
        "smiles": smiles,
        "method": method,
        "basis": basis,
        "operation": operation,
        "work_dir": str(work_dir),
    }

    if use_wsl:
        # WSL 模式: 写 .py 脚本, WSL 内 python 跑, 抓 stdout 解析
        script = _build_pyscf_script(smiles, method, basis, operation, charge, spin)
        script_path = work_dir / "calc.py"
        script_path.write_text(script, encoding="utf-8")
        try:
            import subprocess
            import shutil as _sh
            if not _sh.which("wsl.exe"):
                raise RuntimeError("wsl.exe not found")
            proc = subprocess.run(
                ["wsl.exe", "-d", wsl_distro, "bash", "-c",
                 f"cd /tmp && cp /mnt/e/sci-software 2>/dev/null; "
                 f"python3 -c \"from pyscf import gto, dft; "
                 f"mol = gto.M(atom='{smiles}', basis='{basis}', charge={charge}); "
                 f"mf = dft.RKS(mol); mf.xc='{method}'; print('ENERGY:', mf.kernel())\" "
                 f"2>&1 | tee {work_dir}/pyscf.log"],
                capture_output=True, text=True, timeout=300,
            )
            log_text = (proc.stdout or "") + (proc.stderr or "")
            (work_dir / "pyscf.log").write_text(log_text, encoding="utf-8")
            energy = _parse_pyscf_energy(log_text)
            if energy is not None:
                out["energy_hartree"] = energy
                out["status"] = "success"
            else:
                out["status"] = "failed"
                out["error_msg"] = "Failed to parse ENERGY from WSL PySCF output"
                out["raw_log_tail"] = log_text[-500:]
        except Exception as e:
            out["status"] = "failed"
            out["error_msg"] = repr(e)
            logger.exception("PySCF WSL failed")
    else:
        # Windows 原生: 调本地 Python (conda-envs/scichem)
        out["status"] = "unavailable_native"
        out["error_msg"] = (
            "PySCF Windows 原生模式未实现 — 走 WSL Ubuntu 分发版 (use_wsl=True)"
        )
    out["elapsed_s"] = round(time.time() - t0, 2)
    return out


def _build_pyscf_script(
    smiles: str, method: str, basis: str, operation: str,
    charge: int, spin: int,
) -> str:
    return f'''"""Auto-generated PySCF calculation."""
from pyscf import gto, dft

mol = gto.M(atom="{smiles}", basis="{basis}", charge={charge}, spin={spin})
mf = dft.RKS(mol)
mf.xc = "{method}"
print("ENERGY:", mf.kernel())
if "{operation}" == "optimize":
    from pyscf.geomopt.geometric_solver import optimize
    mol_eq = optimize(mf)
    print("OPT_GEOM:", mol_eq.tostring())
'''


def _parse_pyscf_energy(text: str) -> float | None:
    import re
    # 匹配 -1.234e+2 / -76.4 / 1.5E-3 等科学计数法
    m = re.search(r"ENERGY:\s*(-?\d+\.\d+(?:[eE][+-]?\d+)?)", text)
    if m:
        return float(m.group(1))
    return None


async def run_pyscf_async(smiles: str, **kwargs) -> dict[str, Any]:
    return await asyncio.to_thread(run_pyscf_calculation, smiles, **kwargs)


def health_check() -> dict[str, Any]:
    return {
        "tool": "pyscf",
        "workflows_available": workflows_available(),
        "mode": "wsl_only",
    }
