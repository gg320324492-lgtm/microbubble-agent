r"""DFT/MD 域工具 — 2026-08-30 起走 HTTP 调独立 dft-service (E:\dft-service)

- run_gaussian_calculation: Gaussian 16W DFT (SCRF 溶剂真实生效)
- submit_gromacs_md: GROMACS MD (WSL)
- mace_relax_structure: MACE-MP 快速几何优化 (GPU)
- run_pyscf_calculation: PySCF (scichem / WSL 回退, RDKit 3D)
- list_available_dft_tools: 健康检查 (含 Psi4)

工具名与 schema 保持外置前兼容 (LLM prompt 不受影响); 计算结果由
dft_service.submit_and_wait 提交 + 轮询到终态后返回, 语义同旧版同步工具。
"""
import asyncio
import logging
import time
from typing import Optional

from pydantic import BaseModel, Field

from app.agent.tool_registry import ToolContext, tool
from app.services import dft_client

logger = logging.getLogger("microbubble.agent.tools.dft")


# =============================================================
# 1. run_gaussian_calculation
# =============================================================
class RunGaussianInput(BaseModel):
    smiles: str = Field(..., min_length=1, description="分子 SMILES (如 'CCO' = 乙醇)")
    xc: str = Field("B3LYP", description="泛函 (B3LYP / M06-2X / wB97X-D / ...)")
    basis: str = Field("6-31G(d)", description="基组 (6-31G(d) / def2-TZVP / ...)")
    job: str = Field("opt", description="任务类型 (opt / sp / freq)")
    solvent: str = Field(
        "none", description="SMD 隐式溶剂 (water / ethanol / dmso / ...; none=气相)")
    charge: Optional[int] = Field(
        None, ge=-10, le=10, description="体系总电荷; 缺省从 SMILES 自动推断")
    multiplicity: Optional[int] = Field(
        None, ge=1, le=10, description="自旋多重度; 缺省从 SMILES 自动推断")
    timeout_s: float = Field(7200.0, ge=10.0, le=86400.0,
                              description="超时秒 (默认 2 小时)")


class GaussianResult(BaseModel):
    status: str
    smiles: str
    xc: str
    basis: str
    job: str
    energy_hartree: Optional[float] = None
    energy_ev: Optional[float] = None
    n_opt_steps: Optional[int] = None
    converged: Optional[bool] = None
    log_path: Optional[str] = None
    gjf_path: Optional[str] = None
    work_dir: Optional[str] = None
    elapsed_s: Optional[float] = None
    error_msg: Optional[str] = None
    extra: dict = Field(default_factory=dict)
    rich_block_type: str = "dft_gaussian"


@tool(
    name="run_gaussian_calculation",
    description=(
        "跑 Gaussian 16W DFT 计算 (B3LYP/6-31G(d) opt 默认, SCRF/SMD 溶剂可选)。"
        "用户给 SMILES 想算分子能量 / 优化几何 / 频率时调用。"
        "离子/自由基务必给 charge 和 multiplicity。"
        "阻塞等待结果 (可能 30s-数小时), 适合单分子小体系。"
    ),
    input_model=RunGaussianInput,
    output_model=GaussianResult,
    requires_db=False,
)
async def run_gaussian_calculation(input: RunGaussianInput, ctx: ToolContext) -> dict:
    """Gaussian 16W DFT 计算 (经 dft-service)"""
    result = await dft_client.submit_and_wait("gaussian", {
        "smiles": input.smiles,
        "xc": input.xc,
        "basis": input.basis,
        "job": input.job,
        "solvent": input.solvent,
        "charge": input.charge,
        "multiplicity": input.multiplicity,
        "timeout_s": input.timeout_s,
    }, timeout_s=input.timeout_s + 60)
    result["rich_block_type"] = "dft_gaussian"
    return result


# =============================================================
# 2. submit_gromacs_md
# =============================================================
class SubmitGromacsInput(BaseModel):
    smiles: str = Field(..., min_length=1, description="溶质 SMILES (单组分)")
    n_molecules: int = Field(100, ge=1, le=10000, description="分子数")
    box_nm: float = Field(3.0, gt=0.0, le=20.0, description="盒子边长 (nm)")
    time_ns: float = Field(1.0, gt=0.0, le=100.0, description="模拟时长 (ns)")
    temperature_K: float = Field(300.0, ge=0.0, le=1000.0, description="温度 (K)")


class GromacsResult(BaseModel):
    status: str
    smiles: str
    n_molecules: int
    box_nm: float
    time_ns: float
    temperature_K: float
    trajectory_path: Optional[str] = None
    md_log: Optional[str] = None
    work_dir: Optional[str] = None
    elapsed_s: Optional[float] = None
    error_msg: Optional[str] = None
    rich_block_type: str = "dft_gromacs"


@tool(
    name="submit_gromacs_md",
    description=(
        "跑 GROMACS 经典 MD 模拟 (WSL Ubuntu-24.04 + gmx)。"
        "包含: prep_system → energy_minimize → run_md 完整流程, 输出 .xtc 轨迹。"
        "大体系 / 长时模拟建议拆小批量。"
    ),
    input_model=SubmitGromacsInput,
    output_model=GromacsResult,
    requires_db=False,
)
async def submit_gromacs_md(input: SubmitGromacsInput, ctx: ToolContext) -> dict:
    """GROMACS MD 模拟 (经 dft-service)"""
    timeout_s = max(600.0, input.time_ns * 600.0 + 600.0)
    result = await dft_client.submit_and_wait("gromacs", {
        "smiles": input.smiles,
        "n_molecules": input.n_molecules,
        "box_nm": input.box_nm,
        "time_ns": input.time_ns,
        "temperature_K": input.temperature_K,
        "timeout_s": timeout_s,
    }, timeout_s=timeout_s + 60)
    result["rich_block_type"] = "dft_gromacs"
    return result


# =============================================================
# 3. mace_relax_structure
# =============================================================
class MaceRelaxInput(BaseModel):
    smiles: str = Field(..., min_length=1, description="分子 SMILES")
    fmax_ev_A: float = Field(0.05, gt=0.0, le=1.0, description="力收敛阈值 (eV/Å)")
    max_steps: int = Field(200, ge=1, le=5000, description="最大优化步数")
    model: str = Field("medium", description="MACE 模型: small/medium/large")
    device: str = Field("auto", description="cuda / cpu / auto")


class MaceRelaxResult(BaseModel):
    status: str
    smiles: str
    model: str
    fmax_ev_A: float
    max_steps: int
    energy_ev: Optional[float] = None
    n_steps: Optional[int] = None
    converged: Optional[bool] = None
    trajectory_path: Optional[str] = None
    work_dir: Optional[str] = None
    elapsed_s: Optional[float] = None
    error_msg: Optional[str] = None
    rich_block_type: str = "dft_mace"


@tool(
    name="mace_relax_structure",
    description=(
        "用 MACE-MP 机器学习力场快速优化分子结构 (GPU 加速秒级)。"
        "比 Gaussian 快 100-1000x, 但精度略低 — 适合初猜优化 / 大量筛选。"
    ),
    input_model=MaceRelaxInput,
    output_model=MaceRelaxResult,
    requires_db=False,
)
async def mace_relax_structure(input: MaceRelaxInput, ctx: ToolContext) -> dict:
    """MACE-MP 快速结构优化 (经 dft-service)"""
    timeout_s = 900.0
    result = await dft_client.submit_and_wait("mace", {
        "smiles": input.smiles,
        "fmax_ev_A": input.fmax_ev_A,
        "max_steps": input.max_steps,
        "model": input.model,
        "device": input.device,
        "timeout_s": timeout_s,
    }, timeout_s=timeout_s + 60)
    result["rich_block_type"] = "dft_mace"
    return result


# =============================================================
# 4. run_pyscf_calculation
# =============================================================
class RunPySCFInput(BaseModel):
    smiles: str = Field(..., min_length=1, description="分子 SMILES")
    method: str = Field("B3LYP", description="DFT 方法 (B3LYP / PBE / M06-2X / ...)")
    basis: str = Field("6-31G*", description="基组")
    operation: str = Field("energy", description="操作: energy / optimize")
    solvent: str = Field(
        "none", description="C-PCM 隐式溶剂 (water / ethanol / ...; none=气相)")
    charge: int = Field(0, ge=-10, le=10, description="总电荷")
    spin: int = Field(0, ge=0, le=10, description="未配对电子数 2S (0=闭壳层, >0 自动 UKS)")


class PySCFResult(BaseModel):
    status: str
    smiles: str
    method: str
    basis: str
    operation: str
    energy_hartree: Optional[float] = None
    scf_converged: Optional[bool] = None
    work_dir: Optional[str] = None
    elapsed_s: Optional[float] = None
    error_msg: Optional[str] = None
    rich_block_type: str = "dft_pyscf"


@tool(
    name="run_pyscf_calculation",
    description=(
        "用 PySCF 跑 DFT — 纯开源 BSD 许可, 无商业授权 "
        "(scichem 环境或 WSL 回退自动择一)。支持 C-PCM 溶剂与开壳层 UKS。"
        "适合不想依赖 Gaussian 16W 的场景。"
    ),
    input_model=RunPySCFInput,
    output_model=PySCFResult,
    requires_db=False,
)
async def run_pyscf_calculation(input: RunPySCFInput, ctx: ToolContext) -> dict:
    """PySCF DFT (经 dft-service)"""
    timeout_s = 1800.0
    result = await dft_client.submit_and_wait("pyscf", {
        "smiles": input.smiles,
        "method": input.method,
        "basis": input.basis,
        "operation": input.operation,
        "solvent": input.solvent,
        "charge": input.charge,
        # 服务端语义是自旋多重度 (2S+1); 工具层沿用 2S 入参
        "multiplicity": input.spin + 1,
        "timeout_s": timeout_s,
    }, timeout_s=timeout_s + 60)
    result["rich_block_type"] = "dft_pyscf"
    return result


# =============================================================
# 5. list_available_dft_tools
# =============================================================
class ListDFTToolsInput(BaseModel):
    pass


class DFTToolItem(BaseModel):
    name: str
    available: bool
    details: dict


class ListDFTToolsOutput(BaseModel):
    status: str
    tools: list[DFTToolItem]
    count: int
    available_count: int
    rich_block_type: str = "dft_tools"


@tool(
    name="list_available_dft_tools",
    description=(
        "列出所有可用的 DFT/MD 工具 (Gaussian / GROMACS / MACE / PySCF / Psi4) "
        "和它们的健康状态 — 用户问「我有哪些计算工具」时调用。"
    ),
    input_model=ListDFTToolsInput,
    output_model=ListDFTToolsOutput,
    requires_db=False,
)
async def list_available_dft_tools(input: ListDFTToolsInput, ctx: ToolContext) -> dict:
    """DFT/MD 工具健康检查 (经 dft-service /dft/tools)"""
    result = await dft_client.dft_get("/dft/tools")
    result.setdefault("rich_block_type", "dft_tools")
    return result


# =============================================================
# 6. run_psi4_calculation (2026-08-30 随服务端 Psi4 后端补齐)
# =============================================================
class RunPsi4Input(BaseModel):
    smiles: str = Field(..., min_length=1, description="分子 SMILES")
    method: str = Field("B3LYP", description="DFT 方法 (B3LYP / PBE / M06-2X / ...)")
    basis: str = Field("6-31G*", description="基组")
    operation: str = Field(
        "energy", description="energy / optimize / properties (偶极+HOMO-LUMO)")
    charge: Optional[int] = Field(None, ge=-10, le=10, description="总电荷; 缺省从 SMILES 推断")
    multiplicity: Optional[int] = Field(None, ge=1, le=10, description="自旋多重度; 缺省推断")
    timeout_s: float = Field(3600.0, ge=10.0, le=86400.0, description="超时秒")


class Psi4Result(BaseModel):
    status: str
    smiles: str
    method: str
    basis: str
    operation: str
    energy_hartree: Optional[float] = None
    dipole_debye: Optional[float] = None
    homo_lumo_gap_eV: Optional[float] = None
    work_dir: Optional[str] = None
    elapsed_s: Optional[float] = None
    error_msg: Optional[str] = None
    rich_block_type: str = "dft_psi4"


@tool(
    name="run_psi4_calculation",
    description=(
        "用 Psi4 跑 DFT (开源) — 唯一支持 properties 任务的后端: "
        "偶极矩 / HOMO-LUMO 轨道能量差。也支持 energy/optimize。"
    ),
    input_model=RunPsi4Input,
    output_model=Psi4Result,
    requires_db=False,
)
async def run_psi4_calculation(input: RunPsi4Input, ctx: ToolContext) -> dict:
    """Psi4 DFT (经 dft-service)"""
    result = await dft_client.submit_and_wait("psi4", {
        "smiles": input.smiles,
        "method": input.method,
        "basis": input.basis,
        "operation": input.operation,
        "charge": input.charge,
        "multiplicity": input.multiplicity,
        "timeout_s": input.timeout_s,
    }, timeout_s=input.timeout_s + 60)
    result["rich_block_type"] = "dft_psi4"
    return result


# =============================================================
# 7. run_dft_auto (智能选路 — 不确定用哪个后端时让服务挑)
# =============================================================
class RunDftAutoInput(BaseModel):
    smiles: str = Field(..., min_length=1, description="分子 SMILES")
    task: str = Field(
        "energy", description="energy / optimize / freq / properties / md")
    quality: str = Field(
        "auto", description="fast (MACE 秒级) / accurate (量子化学) / auto")
    xc: str = Field("B3LYP", description="泛函 (accurate 路径用)")
    basis: str = Field("6-31G*", description="基组 (accurate 路径用)")
    solvent: str = Field("none", description="溶剂 (仅 gaussian/pyscf 支持)")
    timeout_s: Optional[float] = Field(None, description="超时秒; 缺省按后端定")


class DftAutoResult(BaseModel):
    status: str
    backend: Optional[str] = None
    reason: Optional[str] = None
    warnings: list[str] = Field(default_factory=list)
    smiles: str
    energy_hartree: Optional[float] = None
    work_dir: Optional[str] = None
    elapsed_s: Optional[float] = None
    error_msg: Optional[str] = None
    rich_block_type: str = "dft_auto"


@tool(
    name="run_dft_auto",
    description=(
        "DFT 智能选路 — 不确定该用哪个计算后端时调用。服务端按 task+quality "
        "自动择一: fast→MACE (秒级), accurate→Gaussian/Psi4/PySCF 择优, "
        "md→GROMACS。返回所选 backend 和理由; 不支持的参数会在 warnings 里说明。"
    ),
    input_model=RunDftAutoInput,
    output_model=DftAutoResult,
    requires_db=False,
)
async def run_dft_auto(input: RunDftAutoInput, ctx: ToolContext) -> dict:
    """DFT 智能选路 (经 dft-service /dft/auto)"""
    payload: dict = {
        "smiles": input.smiles,
        "task": input.task,
        "quality": input.quality,
        "xc": input.xc,
        "basis": input.basis,
        "solvent": input.solvent,
    }
    if input.timeout_s is not None:
        payload["timeout_s"] = input.timeout_s
    submit_resp = await dft_client.dft_post("/dft/auto", payload)
    if submit_resp.get("status") == "unavailable":
        submit_resp["rich_block_type"] = "dft_auto"
        return submit_resp
    task_id = submit_resp.get("task_id")
    timeout_s = input.timeout_s or 7200.0
    # auto 已在 submit 时派发; 轮询 task_id 到终态 (不重复提交)
    deadline = time.monotonic() + timeout_s + 60
    result: dict = {}
    while True:
        rec = await dft_client.dft_get(f"/dft/result/{task_id}")
        if rec.get("status") not in ("queued", "running", None):
            result = rec.get("result") or {}
            break
        if time.monotonic() > deadline:
            result = {"status": "timeout", "task_id": task_id,
                      "error_msg": f"等待 {timeout_s:.0f}s 未完成, 稍后查 "
                                   f"/dft/result/{task_id}"}
            break
        await asyncio.sleep(3)
    result.setdefault("task_id", task_id)
    result["backend"] = submit_resp.get("backend")
    result["reason"] = submit_resp.get("reason")
    result["warnings"] = submit_resp.get("warnings", [])
    result["rich_block_type"] = "dft_auto"
    return result
