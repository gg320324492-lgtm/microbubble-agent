r"""DFT/MD 工具 pytest — 2026-08-30 外置 dft-service 后的 HTTP 客户端测试

旧版 mock g16.exe/WSL/MACE 子进程; 现在 microbubble 侧只剩 HTTP 编排:
- 5 个 @tool 注册 + schema 校验
- submit_and_wait 提交→轮询→终态 全流程 (httpx.MockTransport)
- 服务不可达 → status=unavailable (不抛异常)
- 轮询超时 → status=timeout + task_id (任务仍在服务端)
- 5 工具 HTTP 化后 rich_block_type 语义不变

真实计算链路 (driver/g16/wsl/mace) 的测试在 E:\dft-service\tests\。
"""
import asyncio
import os
from unittest import mock

import httpx
import pytest

# 让 from app.* 不爆 HalfVector NameError
import app.models.types  # noqa: F401
from app.services import dft_client

os.environ.setdefault("SKIP_DB_SETUP", "1")


@pytest.fixture(autouse=True)
def _mock_transport(monkeypatch):
    """每个测试注入干净的 mock transport + 快轮询"""
    monkeypatch.setattr(dft_client, "_POLL_INTERVAL_S", 0.01)
    yield
    asyncio.run(dft_client.aclose())


def _install(monkeypatch, handler):
    client = httpx.AsyncClient(
        transport=httpx.MockTransport(handler),
        headers={"X-API-Key": "test-key"},
    )
    monkeypatch.setattr(dft_client, "_client", client)


# =============================================================
# 1. 工具注册 + schema
# =============================================================
def test_import_5_tools():
    from app.agent.tools.dft_tools import (
        run_gaussian_calculation,
        submit_gromacs_md,
        mace_relax_structure,
        run_pyscf_calculation,
        run_psi4_calculation,
        run_dft_auto,
        list_available_dft_tools,
    )
    from app.agent.tool_registry import TOOL_REGISTRY
    expected = [
        "run_gaussian_calculation",
        "submit_gromacs_md",
        "mace_relax_structure",
        "run_pyscf_calculation",
        "run_psi4_calculation",
        "run_dft_auto",
        "list_available_dft_tools",
    ]
    for name in expected:
        assert name in TOOL_REGISTRY, f"Tool {name} not registered"


def test_tool_schemas_valid():
    """5 工具的 input_schema 是合法 JSON Schema"""
    from app.agent.tool_registry import TOOL_REGISTRY, get_all_tool_schemas
    schemas = get_all_tool_schemas()
    dft_schemas = [s for s in schemas if any(
        kw in s["name"] for kw in ("gaussian", "gromacs", "mace", "pyscf",
                                   "psi4", "dft")
    )]
    assert len(dft_schemas) >= 7
    for s in dft_schemas:
        assert "parameters" in s or "input_schema" in s


def test_gaussian_schema_has_charge_multiplicity():
    """缺口 #2 回归: gaussian 工具暴露 charge/multiplicity 且默认 None (服务端
    自动推断); solvent 默认气相"""
    from app.agent.tools.dft_tools import RunGaussianInput
    fields = RunGaussianInput.model_fields
    assert "charge" in fields and "multiplicity" in fields
    assert fields["charge"].default is None
    assert fields["multiplicity"].default is None
    assert fields["solvent"].default == "none"


# =============================================================
# 2. submit_and_wait 全流程
# =============================================================
def test_gaussian_submit_poll_success(monkeypatch):
    """提交 → running → success: LLM 拿到能量, rich_block_type 语义不变"""
    from app.agent.tools.dft_tools import RunGaussianInput, run_gaussian_calculation

    polls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if request.method == "POST" and path.endswith("/dft/gaussian"):
            assert b"CCO" in request.content
            assert b'"charge":1' in request.content.replace(b" ", b"")
            return httpx.Response(200, json={
                "task_id": "abc123", "status": "queued",
                "submit_time": "2026-08-30T00:00:00+00:00", "tool": "gaussian",
            })
        if request.method == "GET" and path.endswith("/dft/result/abc123"):
            polls["n"] += 1
            if polls["n"] < 3:
                return httpx.Response(200, json={
                    "task_id": "abc123", "status": "running"})
            return httpx.Response(200, json={
                "task_id": "abc123", "status": "success",
                "result": {"status": "success", "energy_hartree": -76.4,
                           "converged": True},
            })
        return httpx.Response(404, json={"detail": "nope"})

    _install(monkeypatch, handler)
    result = asyncio.run(run_gaussian_calculation(
        RunGaussianInput(smiles="CCO", charge=1), ctx=None))
    assert result["status"] == "success"
    assert result["energy_hartree"] == -76.4
    assert result["task_id"] == "abc123"
    assert result["rich_block_type"] == "dft_gaussian"


def test_service_unreachable_returns_unavailable(monkeypatch):
    """服务不可达 → status=unavailable (永不抛异常, LLM 能读懂)"""
    from app.agent.tools.dft_tools import (
        ListDFTToolsInput,
        list_available_dft_tools,
    )

    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused", request=request)

    _install(monkeypatch, handler)
    result = asyncio.run(list_available_dft_tools(
        ListDFTToolsInput(), ctx=None))
    assert result["status"] == "unavailable"
    assert "dft-service" in result["error_msg"]
    assert result["rich_block_type"] == "dft_tools"


def test_poll_timeout_returns_task_id(monkeypatch):
    """超时 → status=timeout + task_id (任务仍在服务端继续跑)"""
    from app.agent.tools.dft_tools import MaceRelaxInput, mace_relax_structure

    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if request.method == "POST":
            return httpx.Response(200, json={
                "task_id": "slow99", "status": "queued",
                "submit_time": "t", "tool": "mace"})
        return httpx.Response(200, json={
            "task_id": "slow99", "status": "running"})

    _install(monkeypatch, handler)

    # 假时钟: 每次 monotonic() 前进 100s → 2 次轮询即越过 deadline
    fake_now = {"t": 0.0}

    def fake_monotonic() -> float:
        fake_now["t"] += 100.0
        return fake_now["t"]

    monkeypatch.setattr(dft_client.time, "monotonic", fake_monotonic)

    result = asyncio.run(mace_relax_structure(
        MaceRelaxInput(smiles="O"), ctx=None))
    assert result["status"] == "timeout"
    assert result["task_id"] == "slow99"
    assert "dft/result" in result["error_msg"]


def test_pyscf_spin_maps_to_multiplicity(monkeypatch):
    """工具层 spin (2S) → 服务端 multiplicity (2S+1) 映射"""
    from app.agent.tools.dft_tools import RunPySCFInput, run_pyscf_calculation

    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "POST" and request.url.path.endswith("/dft/pyscf"):
            captured["payload"] = request.read()
            return httpx.Response(200, json={
                "task_id": "p1", "status": "queued",
                "submit_time": "t", "tool": "pyscf"})
        return httpx.Response(200, json={
            "task_id": "p1", "status": "success",
            "result": {"status": "success", "energy_hartree": -75.3,
                       "scf_converged": True}})

    _install(monkeypatch, handler)
    result = asyncio.run(run_pyscf_calculation(
        RunPySCFInput(smiles="O", spin=2), ctx=None))
    assert b'"multiplicity":3' in captured["payload"].replace(b" ", b"")
    assert result["status"] == "success"
    assert result["rich_block_type"] == "dft_pyscf"


# =============================================================
# 3. API 薄代理 (app/api/v1/dft.py)
# =============================================================
def test_api_router_endpoints_exist():
    """代理路由形状不变: tools / submit / status / result /jobs — 前端无感"""
    from app.api.v1.dft import router
    paths = {(r.path, tuple(sorted(r.methods))) for r in router.routes}
    assert ("/dft/tools", ("GET",)) in paths
    assert ("/dft/status/{task_id}", ("GET",)) in paths
    assert ("/dft/result/{task_id}", ("GET",)) in paths
    assert ("/dft/jobs", ("GET",)) in paths
    assert ("/dft/{tool}", ("POST",)) in paths


def test_proxy_rejects_unknown_tool():
    from app.api.v1.dft import _SUBMIT_TOOLS
    assert "gaussian" in _SUBMIT_TOOLS
    assert "auto" in _SUBMIT_TOOLS
    assert "../etc" not in _SUBMIT_TOOLS
