"""DFT/MD 域工具（Phase 5 集成）— 注册 5 个 @tool

- run_gaussian_calculation: Gaussian 16W DFT
- submit_gromacs_md: GROMACS MD (WSL)
- mace_relax_structure: MACE-MP 快速几何优化 (GPU)
- run_pyscf_calculation: PySCF (WSL) 纯开源 BSD
- list_available_dft_tools: 健康检查
"""
import logging
from typing import Optional

from pydantic import BaseModel, Field

from app.agent.tool_registry import ToolContext, tool

logger = logging.getLogger("microbubble.agent.tools.dft")


# =============================================================
# 1. run_gaussian_calculation
# =============================================================
class RunGaussianInput(BaseModel):
    smiles: str = Field(..., min_length=1, description="分子 SMILES (如 'CCO' = 乙醇)")
    xc: str = Field("B3LYP", description="泛函 (B3LYP / M06-2X / wB97X-D / ...)")
    basis: str = Field("6-31G(d)", description="基组 (6-31G(d) / cc-pVTZ / ...)")
    job: str = Field("opt", description="任务类型 (opt / sp / freq)")
    solvent: str = Field("water", description="隐式溶剂标签 (写进 .gjf 标题)")
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
        "跑 Gaussian 16W DFT 计算 (B3LYP/6-31G(d) opt 默认)。"
        "用户给 SMILES 想算分子能量 / 优化几何 / 频率时调用。"
        "同步阻塞 (可能 30s-数小时), 适合单分子小体系。"
    ),
    input_model=RunGaussianInput,
    output_model=GaussianResult,
    requires_db=False,
)
async def run_gaussian_calculation(input: RunGaussianInput, ctx: ToolContext) -> dict:
    """Gaussian 16W DFT 计算"""
    from app.services.dft.gaussian_runner import run_gaussian_async
    result = await run_gaussian_async(
        smiles=input.smiles,
        xc=input.xc, basis=input.basis,
        job=input.job, solvent=input.solvent,
        timeout_s=input.timeout_s,
    )
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
        "跑 GROMACS 经典 MD 模拟 (WSL Ubuntu + gmx)。"
        "包含: prep_system → energy_minimize → run_md 完整流程。"
        "大体系 / 长时模拟建议拆小批量。"
    ),
    input_model=SubmitGromacsInput,
    output_model=GromacsResult,
    requires_db=False,
)
async def submit_gromacs_md(input: SubmitGromacsInput, ctx: ToolContext) -> dict:
    """GROMACS MD 模拟"""
    from app.services.dft.gromacs_runner import submit_gromacs_async
    result = await submit_gromacs_async(
        smiles=input.smiles,
        n_molecules=input.n_molecules,
        box_nm=input.box_nm,
        time_ns=input.time_ns,
        temperature_K=input.temperature_K,
    )
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
    save_trajectory: bool = Field(False, description="是否保存每帧轨迹")


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
        "用 MACE-MP-0 机器学习力场快速优化分子结构 (GPU 加速秒级)。"
        "比 Gaussian 快 100-1000x, 但精度略低 — 适合初猜优化 / 大量筛选。"
    ),
    input_model=MaceRelaxInput,
    output_model=MaceRelaxResult,
    requires_db=False,
)
async def mace_relax_structure(input: MaceRelaxInput, ctx: ToolContext) -> dict:
    """MACE-MP 快速结构优化"""
    from app.services.dft.mace_runner import mace_relax_async
    result = await mace_relax_async(
        smiles=input.smiles,
        fmax_ev_A=input.fmax_ev_A,
        max_steps=input.max_steps,
        model=input.model,
        save_trajectory=input.save_trajectory,
    )
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
    charge: int = Field(0, ge=-10, le=10, description="总电荷")
    spin: int = Field(0, ge=0, le=10, description="自旋 2S (0=单重态)")


class PySCFResult(BaseModel):
    status: str
    smiles: str
    method: str
    basis: str
    operation: str
    energy_hartree: Optional[float] = None
    work_dir: Optional[str] = None
    elapsed_s: Optional[float] = None
    error_msg: Optional[str] = None
    raw_log_tail: Optional[str] = None
    rich_block_type: str = "dft_pyscf"


@tool(
    name="run_pyscf_calculation",
    description=(
        "用 PySCF 跑 DFT (WSL Ubuntu) — 纯开源 BSD 许可, 无商业授权。"
        "适合不想依赖 Gaussian 16W 的场景。"
    ),
    input_model=RunPySCFInput,
    output_model=PySCFResult,
    requires_db=False,
)
async def run_pyscf_calculation(input: RunPySCFInput, ctx: ToolContext) -> dict:
    """PySCF (WSL) DFT"""
    from app.services.dft.multimodel_runner import run_pyscf_async
    result = await run_pyscf_async(
        smiles=input.smiles,
        method=input.method, basis=input.basis,
        operation=input.operation,
        charge=input.charge, spin=input.spin,
    )
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
        "列出所有可用的 DFT/MD 工具 (Gaussian / GROMACS / MACE / PySCF) "
        "和它们的健康状态 — 用户问「我有哪些计算工具」时调用。"
    ),
    input_model=ListDFTToolsInput,
    output_model=ListDFTToolsOutput,
    requires_db=False,
)
async def list_available_dft_tools(input: ListDFTToolsInput, ctx: ToolContext) -> dict:
    """DFT/MD 工具健康检查"""
    from app.services.dft.tool_definitions import list_available_dft_tools as _lst
    return _lst()
