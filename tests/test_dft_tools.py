"""DFT/MD 工具 pytest — Phase 5 集成

测试覆盖:
- 5 个 @tool 的 import + Pydantic schema 校验
- 1 个 Gaussian e2e (mock g16.exe, 验证 submit_gjf + parse_log 流程)
- 1 个 GROMACS e2e (mock WSL, 验证 prep_system + energy_minimize)
- 1 个 MACE e2e (mock calculator, 验证 relax)
- 1 个 PySCF e2e (mock WSL subprocess, 验证能量解析)
- 1 个 FastAPI 端点测试 (TestClient)
- 1 个 health check 测试

注: 真实跑 g16/wsl/mace 会卡住 license / 启动时间长, 这里走 mock 路径。
"""
import asyncio
import json
import os
import sys
import time
from pathlib import Path
from unittest import mock

import pytest

# 让 from app.* 不爆 HalfVector NameError
import app.models.types  # noqa: F401

# 防止真正起 WSGI
os.environ.setdefault("SKIP_DB_SETUP", "1")


# =============================================================
# Fixtures
# =============================================================
@pytest.fixture
def tmp_workdir(tmp_path, monkeypatch):
    """重定向 DFT 输出到 tmp 目录"""
    monkeypatch.setenv("DFT_OUTPUT_ROOT", str(tmp_path / "dft_jobs"))
    (tmp_path / "dft_jobs").mkdir(parents=True, exist_ok=True)
    return tmp_path / "dft_jobs"


# =============================================================
# 1. 5 工具 import 测试
# =============================================================
def test_import_5_tools():
    from app.agent.tools.dft_tools import (
        run_gaussian_calculation,
        submit_gromacs_md,
        mace_relax_structure,
        run_pyscf_calculation,
        list_available_dft_tools,
    )
    from app.agent.tool_registry import TOOL_REGISTRY
    expected = [
        "run_gaussian_calculation",
        "submit_gromacs_md",
        "mace_relax_structure",
        "run_pyscf_calculation",
        "list_available_dft_tools",
    ]
    for name in expected:
        assert name in TOOL_REGISTRY, f"Tool {name} not registered"


def test_tool_schemas_valid():
    """5 工具的 input_schema 是合法 JSON Schema"""
    from app.agent.tool_registry import TOOL_REGISTRY, get_all_tool_schemas
    schemas = get_all_tool_schemas()
    dft_schemas = [s for s in schemas if any(
        kw in s["name"] for kw in ("gaussian", "gromacs", "mace", "pyscf", "dft")
    )]
    assert len(dft_schemas) == 5
    for s in dft_schemas:
        assert "name" in s
        assert "description" in s
        assert "input_schema" in s
        assert s["input_schema"].get("type") == "object"


# =============================================================
# 2. Gaussian e2e (mock g16.exe)
# =============================================================
def test_gaussian_e2e_mocked(tmp_workdir):
    """mock submit_gjf 直接返回 .log 路径, 验证 parse_log 拿到能量"""
    fake_log = """\
 Entering Gaussian System
 SCF Done:  E(RB3LYP) =  -76.4000000000     A.U. after    8 cycles
 Step number   1
 Step number   2
 Normal termination of Gaussian 16
"""
    log_path = tmp_workdir / "test_gaussian.log"
    log_path.write_text(fake_log, encoding="utf-8")
    gjf_path = log_path.with_suffix(".gjf")
    gjf_path.write_text("%nproc=8\n# B3LYP/6-31G(d) opt\n\ntitle\n\n0 1\n", encoding="utf-8")

    # GaussianResult 从 workflow 包 import — test 不依赖 workflow, 用本地 mock
    class _FakeGR:
        def __init__(self, **kw):
            for k, v in kw.items():
                setattr(self, k, v)

    with mock.patch("app.services.dft.gaussian_runner._import_workflow") as imw:
        imw.return_value = (
            mock.Mock(return_value=gjf_path),  # gen_gjf
            mock.Mock(return_value=log_path),   # submit_gjf
            mock.Mock(return_value=_FakeGR(  # parse_log
                energy_hartree=-76.4,
                energy_ev=-76.4 * 27.2114,
                n_opt_steps=2,
                converged=True,
                extra={},
                error_msg=None,
            )),
            _FakeGR,
        )
        from app.services.dft.gaussian_runner import run_gaussian_calculation
        result = run_gaussian_calculation(
            smiles="O", xc="B3LYP", basis="6-31G(d)", job="opt",
        )
        assert result["status"] == "success"
        assert abs(result["energy_hartree"] - (-76.4)) < 1e-6
        assert result["converged"] is True
        assert result["n_opt_steps"] == 2
        assert result["smiles"] == "O"
        assert "log_path" in result


# =============================================================
# 3. GROMACS e2e (mock WSL)
# =============================================================
def test_gromacs_e2e_mocked(tmp_workdir):
    fake_gro = tmp_workdir / "system.gro"
    fake_gro.write_text("GRO file\n", encoding="utf-8")
    fake_top = tmp_workdir / "system.top"
    fake_top.write_text("; topology\n", encoding="utf-8")

    with mock.patch("app.services.dft.gromacs_runner._import_workflow") as imw, \
         mock.patch("app.services.dft.gromacs_runner.wsl_gromacs_available",
                    return_value=True):
        from app.services.dft.gromacs_runner import submit_gromacs_md
        prep_mock = mock.Mock(return_value={
            "gro": fake_gro, "top": fake_top,
            "pdb": tmp_workdir / "system.pdb",
        })
        em_mock = mock.Mock(return_value={
            "tpr": tmp_workdir / "em.tpr",
            "gro": fake_gro,
            "edr": tmp_workdir / "em.edr",
            "log": tmp_workdir / "em.log",
        })
        md_mock = mock.Mock(return_value={
            "tpr": tmp_workdir / "md.tpr",
            "gro": fake_gro,
            "xtc": tmp_workdir / "md.xtc",
            "edr": tmp_workdir / "md.edr",
            "log": tmp_workdir / "md.log",
        })
        imw.return_value = (prep_mock, em_mock, md_mock, mock.Mock())

        result = submit_gromacs_md(
            smiles="O", n_molecules=10, box_nm=2.0, time_ns=0.001,
        )
        assert result["status"] == "success"
        assert result["trajectory_path"].endswith("md.xtc")
        assert result["n_molecules"] == 10


def test_gromacs_unavailable_wsl():
    """WSL 不可用时, status=unavailable, 不抛异常"""
    with mock.patch("app.services.dft.gromacs_runner._import_workflow") as imw, \
         mock.patch("app.services.dft.gromacs_runner.wsl_gromacs_available",
                    return_value=False):
        imw.return_value = (mock.Mock(), mock.Mock(), mock.Mock(), mock.Mock())
        from app.services.dft.gromacs_runner import submit_gromacs_md
        result = submit_gromacs_md(smiles="O", n_molecules=10)
        assert result["status"] == "unavailable"
        assert "WSL" in result["error_msg"]


# =============================================================
# 4. MACE e2e (mock calculator)
# =============================================================
def test_mace_e2e_mocked(tmp_workdir):
    """mock mace relax 直接返回固定能量"""
    fake_atoms = mock.Mock()
    fake_atoms.get_potential_energy.return_value = -45.5
    fake_atoms.copy.return_value = fake_atoms

    # sys.modules 注入 fake rdkit
    fake_rdkit = mock.MagicMock()
    fake_chem = mock.MagicMock()
    fake_chem.MolFromSmiles.return_value = mock.Mock()
    fake_chem.AddHs.return_value = mock.Mock()
    fake_chem.AllChem.EmbedMolecule.return_value = 0
    fake_chem.AllChem.MMFFOptimizeMolecule.return_value = 0
    mol = mock.Mock()
    mol.GetNumAtoms.return_value = 2
    atom_h = mock.Mock(); atom_h.GetSymbol.return_value = "H"
    atom_o = mock.Mock(); atom_o.GetSymbol.return_value = "O"
    mol.GetAtoms.return_value = [atom_o, atom_h]
    conf = mock.Mock()
    p = mock.Mock(); p.x = 0.0; p.y = 0.0; p.z = 0.5
    conf.GetAtomPosition.return_value = p
    mol.GetConformer.return_value = conf
    fake_chem.AddHs.return_value = mol

    fake_rdkit.Chem = fake_chem
    sys.modules["rdkit"] = fake_rdkit
    sys.modules["rdkit.Chem"] = fake_chem
    sys.modules["rdkit.Chem.AllChem"] = fake_chem.AllChem

    with mock.patch("app.services.dft.mace_runner._import_workflow") as imw, \
         mock.patch("app.services.dft.mace_runner.mace_python_available",
                    return_value=True):
        from app.services.dft.mace_runner import mace_relax_structure
        load_struct = mock.Mock(return_value=fake_atoms)
        relax_mock = mock.Mock(return_value=fake_atoms)
        imw.return_value = (load_struct, relax_mock, mock.Mock())

        result = mace_relax_structure(smiles="O", max_steps=50)
        assert result["status"] == "success"
        assert abs(result["energy_ev"] - (-45.5)) < 1e-6


def test_mace_unavailable_python():
    """mace-torch 未装时, status=unavailable"""
    with mock.patch("app.services.dft.mace_runner._import_workflow") as imw, \
         mock.patch("app.services.dft.mace_runner.mace_python_available",
                    return_value=False):
        imw.return_value = (mock.Mock(), mock.Mock(), mock.Mock())
        from app.services.dft.mace_runner import mace_relax_structure
        result = mace_relax_structure(smiles="O")
        assert result["status"] == "unavailable"
        assert "mace-torch" in result["error_msg"]


# =============================================================
# 5. PySCF e2e (mock WSL subprocess)
# =============================================================
def test_pyscf_e2e_mocked(tmp_workdir):
    fake_stdout = "some pyscf init\nENERGY: -75.9876543\n"
    fake_proc = mock.Mock(returncode=0, stdout=fake_stdout, stderr="")

    with mock.patch("subprocess.run", return_value=fake_proc), \
         mock.patch("shutil.which", return_value="C:/wsl.exe"):
        from app.services.dft.multimodel_runner import run_pyscf_calculation
        result = run_pyscf_calculation(smiles="O", method="B3LYP", basis="6-31G*")
        assert result["status"] == "success"
        assert abs(result["energy_hartree"] - (-75.9876543)) < 1e-6


def test_pyscf_parse_energy():
    from app.services.dft.multimodel_runner import _parse_pyscf_energy
    # 基本
    assert _parse_pyscf_energy("ENERGY: -76.4") == -76.4
    # 科学计数法
    assert abs(_parse_pyscf_energy("ENERGY: -1.234e+2") - (-123.4)) < 1e-3
    # 大写 E
    assert abs(_parse_pyscf_energy("ENERGY: 1.5E-3") - 0.0015) < 1e-6
    # 无匹配
    assert _parse_pyscf_energy("no energy here") is None
    assert _parse_pyscf_energy("") is None


# =============================================================
# 6. Health check
# =============================================================
def test_list_available_dft_tools():
    from app.services.dft.tool_definitions import list_available_dft_tools
    with mock.patch("app.services.dft.gaussian_runner.health_check",
                    return_value={"tool": "gaussian",
                                  "workflows_available": True,
                                  "g16_exists": True}), \
         mock.patch("app.services.dft.gromacs_runner.health_check",
                    return_value={"tool": "gromacs",
                                  "workflows_available": True,
                                  "wsl_gromacs": False}), \
         mock.patch("app.services.dft.mace_runner.health_check",
                    return_value={"tool": "mace",
                                  "mace_python": True}), \
         mock.patch("app.services.dft.multimodel_runner.health_check",
                    return_value={"tool": "pyscf",
                                  "workflows_available": True}):
        result = list_available_dft_tools()
        assert result["status"] == "success"
        assert result["count"] == 4
        assert result["available_count"] == 3  # gaussian/mace/pyscf available
        names = [t["name"] for t in result["tools"]]
        assert set(names) == {"gaussian", "gromacs", "mace", "pyscf"}


# =============================================================
# 7. FastAPI 端点测试 (用 TestClient, 调 /dft/tools 不需 DB)
# =============================================================
def test_fastapi_dft_tools_endpoint():
    """GET /dft/tools 返回工具健康状态"""
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from app.api.v1.dft import router as dft_router
    from app.core.security import get_current_user_optional

    # 覆盖鉴权依赖
    app = FastAPI()
    app.include_router(dft_router, prefix="/api/v1")
    app.dependency_overrides[get_current_user_optional] = lambda: None

    client = TestClient(app)
    resp = client.get("/api/v1/dft/tools")
    assert resp.status_code == 200
    data = resp.json()
    assert "tools" in data
    assert data["count"] == 4
    assert len(data["tools"]) == 4


def test_fastapi_dft_submit_gaussian_returns_task_id():
    """POST /dft/gaussian 立即返回 task_id (BackgroundTasks)"""
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from app.api.v1.dft import router as dft_router, _TASKS
    from app.core.security import get_current_user_optional

    app = FastAPI()
    app.include_router(dft_router, prefix="/api/v1")
    app.dependency_overrides[get_current_user_optional] = lambda: None

    with mock.patch("app.services.dft.gaussian_runner.run_gaussian_async",
                    new=mock.AsyncMock(return_value={
                        "status": "success", "energy_hartree": -76.4,
                    })):
        client = TestClient(app)
        resp = client.post("/api/v1/dft/gaussian", json={
            "smiles": "O", "xc": "B3LYP", "basis": "6-31G(d)", "job": "sp",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert "task_id" in data
        assert data["status"] == "queued"
        assert data["tool"] == "gaussian"


def test_fastapi_status_404():
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from app.api.v1.dft import router as dft_router
    from app.core.security import get_current_user_optional

    app = FastAPI()
    app.include_router(dft_router, prefix="/api/v1")
    app.dependency_overrides[get_current_user_optional] = lambda: None

    client = TestClient(app)
    resp = client.get("/api/v1/dft/status/nonexistent")
    assert resp.status_code == 404


# =============================================================
# 8. Pydantic schema validation
# =============================================================
def test_pydantic_input_validation():
    """空 smiles 应该被 Pydantic 拒绝"""
    from app.agent.tools.dft_tools import RunGaussianInput
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        RunGaussianInput(smiles="")

    # 合法输入
    inp = RunGaussianInput(smiles="O", xc="B3LYP", basis="6-31G(d)")
    assert inp.xc == "B3LYP"
    assert inp.solvent == "water"  # 默认值


def test_pyscf_input_validation():
    from app.agent.tools.dft_tools import RunPySCFInput
    from pydantic import ValidationError
    with pytest.raises(ValidationError):
        RunPySCFInput(smiles="O", charge=999)  # 超出 [-10, 10]
    inp = RunPySCFInput(smiles="O", method="PBE")
    assert inp.method == "PBE"
