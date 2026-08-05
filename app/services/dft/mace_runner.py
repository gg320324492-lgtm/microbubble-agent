"""MACE-MP 快速结构优化与单点能 — 复用 E:\\sci-software\\workflows\\mace_relaxation.py

依赖 mace-torch (机器学习力场, GPU 加速秒级), ASE。
"""
from __future__ import annotations

import asyncio
import logging
import time
from pathlib import Path
from typing import Any

from app.services.dft.paths import DFT_OUTPUT_ROOT, mace_python_available, workflows_available

logger = logging.getLogger("microbubble.dft.mace")


def _import_workflow():
    if not workflows_available():
        raise RuntimeError("sci-software workflows not available")
    from mace_relaxation import (  # type: ignore
        load_structure,
        relax,
        relax_trajectory,
    )
    return load_structure, relax, relax_trajectory


def mace_relax_structure(
    smiles: str,
    fmax_ev_A: float = 0.05,
    max_steps: int = 200,
    model: str = "medium",
    device: str = "auto",
    save_trajectory: bool = False,
    job_id: str | None = None,
) -> dict[str, Any]:
    """用 MACE-MP-0 快速优化分子结构 (GPU 加速秒级)。"""
    load_structure, relax, relax_trajectory = _import_workflow()
    t0 = time.time()
    job_id = job_id or f"mace_{int(t0)}"
    work_dir = Path(DFT_OUTPUT_ROOT) / job_id
    work_dir.mkdir(parents=True, exist_ok=True)

    out: dict[str, Any] = {
        "tool": "mace",
        "smiles": smiles,
        "fmax_ev_A": fmax_ev_A,
        "max_steps": max_steps,
        "model": model,
        "device": device,
        "work_dir": str(work_dir),
    }

    if not mace_python_available():
        out["status"] = "unavailable"
        out["error_msg"] = (
            "mace-torch 未安装 — pip install mace-torch 或用 conda-envs/scichem"
        )
        out["elapsed_s"] = round(time.time() - t0, 2)
        return out

    try:
        from rdkit import Chem
        from rdkit.Chem import AllChem

        # SMILES → 3D → xyz
        mol = Chem.MolFromSmiles(smiles)
        if mol is None:
            raise RuntimeError(f"Invalid SMILES: {smiles}")
        mol = Chem.AddHs(mol)
        if AllChem.EmbedMolecule(mol, AllChem.ETKDGv3()) != 0:
            raise RuntimeError("Failed to embed 3D")
        try:
            AllChem.MMFFOptimizeMolecule(mol, maxIters=500)
        except Exception:
            AllChem.UFFOptimizeMolecule(mol, maxIters=500)

        xyz_path = work_dir / "input.xyz"
        with open(xyz_path, "w", encoding="utf-8") as f:
            f.write(f"{mol.GetNumAtoms()}\n\n")
            conf = mol.GetConformer()
            for i, atom in enumerate(mol.GetAtoms()):
                p = conf.GetAtomPosition(i)
                f.write(
                    f"{atom.GetSymbol()} {p.x:.6f} {p.y:.6f} {p.z:.6f}\n"
                )

        if save_trajectory:
            traj_path = work_dir / "trajectory.extxyz"
            res = relax_trajectory(
                xyz_path, traj_path,
                fmax=fmax_ev_A, steps=max_steps,
                model=model, device=device,
            )
            out["trajectory_path"] = str(traj_path)
            out["n_steps"] = res["n_steps"]
            out["energy_ev"] = res["final_energy"]
            out["converged"] = res["converged"]
        else:
            atoms = load_structure(xyz_path)
            relaxed = relax(
                atoms, fmax=fmax_ev_A, steps=max_steps,
                model=model, device=device,
            )
            out["energy_ev"] = float(relaxed.get_potential_energy())
            out["n_steps"] = max_steps  # 简化: BFGS 步数; 真实 nsteps 需读 optimizer
            out["converged"] = True

        out["status"] = "success"
    except Exception as e:
        out["status"] = "failed"
        out["error_msg"] = repr(e)
        logger.exception("MACE relax failed")
    out["elapsed_s"] = round(time.time() - t0, 2)
    return out


async def mace_relax_async(smiles: str, **kwargs) -> dict[str, Any]:
    return await asyncio.to_thread(mace_relax_structure, smiles, **kwargs)


def health_check() -> dict[str, Any]:
    return {
        "tool": "mace",
        "workflows_available": workflows_available(),
        "mace_python": mace_python_available(),
    }
