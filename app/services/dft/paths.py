"""DFT 工具路径常量与 sci-software 接入

约定:
- SCISOFTWARE_BASE = E:/sci-software
- WORKFLOWS = E:/sci-software/workflows
- DFT_OUTPUT_ROOT = E:/microbubble-agent/data/dft_jobs  (job 输出根目录)

WSL/Gaussian 路径在 Windows 上, 用 raw 字符串, 不做 path conversion。
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

# ------------------------------------------------------------------
# 路径常量 — 集中管理, 改路径只改这里
# ------------------------------------------------------------------
SCISOFTWARE_BASE = Path(
    os.environ.get("SCISOFTWARE_BASE", "E:/sci-software")
).resolve()

WORKFLOWS = Path(
    os.environ.get("SCISOFTWARE_WORKFLOWS", SCISOFTWARE_BASE / "workflows")
).resolve()

# 输出根目录 — dft_jobs/*.log, *.gjf, *.gro, *.xtc 全部在这里
DFT_OUTPUT_ROOT = Path(
    os.environ.get(
        "DFT_OUTPUT_ROOT",
        Path(__file__).parent.parent.parent.parent / "data" / "dft_jobs",
    )
).resolve()
DFT_OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)


# ------------------------------------------------------------------
# 把 WORKFLOWS 加到 sys.path, 让 app.services.dft 包内部能直接
#   from gaussian_runner import gen_gjf, submit_gjf, parse_log
# 不依赖外部 PYTHONPATH
# ------------------------------------------------------------------
if str(WORKFLOWS) not in sys.path:
    sys.path.insert(0, str(WORKFLOWS))


def workflows_available() -> bool:
    """检查 sci-software/workflows 是否可访问 (Gaussian/GROMACS/MACE 包装代码)"""
    return WORKFLOWS.is_dir() and any(WORKFLOWS.glob("*.py"))


def gaussian_binary_exists(path: str | None = None) -> bool:
    """Gaussian 16W 可执行文件是否存在"""
    default = SCISOFTWARE_BASE / "g16w" / "g16.exe"
    p = Path(path) if path else default
    return p.exists()


def wsl_gromacs_available(distro: str = "Ubuntu") -> bool:
    """WSL 内 GROMACS 是否可用 — Windows 专属 check"""
    import shutil
    import subprocess

    if not shutil.which("wsl.exe"):
        return False
    try:
        out = subprocess.run(
            ["wsl.exe", "-d", distro, "bash", "-c", "command -v gmx"],
            capture_output=True, text=True, timeout=10,
        )
        return out.returncode == 0 and "gmx" in out.stdout
    except Exception:
        return False


def mace_python_available(python: str | None = None) -> bool:
    """MACE 是否可用 — 检查 mace-torch 是否装在某个 Python 环境里"""
    py = python or sys.executable
    try:
        import subprocess
        out = subprocess.run(
            [py, "-c", "import mace; print(mace.__version__)"],
            capture_output=True, text=True, timeout=10,
        )
        return out.returncode == 0
    except Exception:
        return False
