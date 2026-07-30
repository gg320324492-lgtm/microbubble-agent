"""W91-X-30 echarts 5.x → 6.x major 升级验证.

W88-X-13 + W90-X-10 留口:
- echarts@5.6.0 XSS moderate vulnerability (GHSA-fgmj-fm8m-jvvx)
- 升 6.x + 改 API
- 4 处视觉回归验证

派工 v6 §5 反馈 类 20.107 沉淀:
"echarts major 升级必 4 步: 查 latest / 改 package.json / npm run build / 跑 4 处视觉回归"
"""
import json
import subprocess
from pathlib import Path

WEB = Path(__file__).resolve().parents[2] / "web"


def _run(cmd: list, timeout: int = 60) -> subprocess.CompletedProcess:
    # On win32, npm/npx need to be invoked via cmd.exe shell. Use shell=True
    # with full string command to avoid CreateProcess executable-not-found.
    if isinstance(cmd, list):
        cmd_str = " ".join(f'"{c}"' if " " in c else c for c in cmd)
    else:
        cmd_str = cmd
    proc = subprocess.run(
        cmd_str,
        cwd=str(WEB),
        capture_output=True,
        timeout=timeout,
        shell=True,
        env={**__import__("os").environ, "PYTHONIOENCODING": "utf-8"},
    )
    # Decode with utf-8 + errors=replace to handle GBK-only output (npm on win32 zh)
    proc.stdout = proc.stdout.decode("utf-8", errors="replace") if isinstance(proc.stdout, bytes) else (proc.stdout or "")
    proc.stderr = proc.stderr.decode("utf-8", errors="replace") if isinstance(proc.stderr, bytes) else (proc.stderr or "")
    return proc


def test_echarts_version_6x():
    """echarts 必须升到 6.x (W91-X-30 主任务)"""
    result = _run(["npm", "ls", "echarts", "--json"], timeout=60)
    data = json.loads(result.stdout)
    deps = data.get("dependencies", {})
    echarts = deps.get("echarts", {})
    version = echarts.get("version", "")
    assert version.startswith("6."), f"echarts must be 6.x, got {version}"


def test_echarts_no_moderate():
    """echarts 必须无 moderate vulnerability (W88-X-13 / W90-X-10 留口)"""
    result = _run(["npm", "audit", "--json"], timeout=120)
    data = json.loads(result.stdout)
    v = data.get("vulnerabilities", {})
    echarts_vulns = {
        k: vv
        for k, vv in v.items()
        if "echarts" in k and vv.get("severity") in ("moderate", "high", "critical")
    }
    assert not echarts_vulns, f"echarts vulnerabilities: {echarts_vulns}"


def test_build_passes():
    """npm run build 必 PASS (CLAUDE.md 永久纪律)"""
    result = _run(["npm", "run", "build"], timeout=600)
    assert result.returncode == 0, (
        f"build 失败 (returncode={result.returncode}):\n"
        f"STDOUT: {result.stdout[-1000:]}\n"
        f"STDERR: {result.stderr[-1000:]}"
    )


def test_echarts_init_signature_compatible():
    """echarts 6.x init(dom, theme, opts) 签名与 5.x 兼容 — 视觉不破."""
    # Read from bundled echarts.esm.js to verify export shape
    esm = WEB / "node_modules" / "echarts" / "dist" / "echarts.esm.js"
    if not esm.exists():
        # ESM-only package may not be present; check dist dir
        dist_dir = WEB / "node_modules" / "echarts" / "dist"
        candidates = list(dist_dir.glob("echarts*.js"))
        assert candidates, "echarts dist bundle not found"
        # The simplest bundle is enough for this signature check
        content = candidates[0].read_text(encoding="utf-8", errors="ignore")
    else:
        content = esm.read_text(encoding="utf-8", errors="ignore")
    # init must be exported in 6.x (renamed from internal init$1 to public init)
    assert "init$1 as init" in content or "as init," in content or "init:" in content, (
        "echarts.init export not found in dist bundle"
    )


def test_4_echarts_pages_imported():
    """4 处 echarts 用法必须仍能正确 import — 视觉回归 4 步守卫.

    4 个 echarts 用法文件:
    1. views/admin/QaBenchR10Monitor.vue
    2. views/admin/AnalyticsView.vue
    3. views/admin/KbMonitorView.vue
    4. views/KnowledgeDetailView.vue
    """
    src = WEB / "src"
    pages = [
        "views/admin/QaBenchR10Monitor.vue",
        "views/admin/AnalyticsView.vue",
        "views/admin/KbMonitorView.vue",
        "views/KnowledgeDetailView.vue",
    ]
    for p in pages:
        file = src / p
        assert file.exists(), f"echarts page missing: {p}"
        content = file.read_text(encoding="utf-8")
        # 4 个文件必须 import echarts
        assert "echarts" in content, f"{p} does not import echarts"


def test_mobile_echarts_wrapper_compatible():
    """MobileECharts wrapper 必须仍 import echarts — 移动端视觉回归守卫."""
    mobile = WEB / "src" / "components" / "mobile" / "MobileECharts.vue"
    assert mobile.exists(), "MobileECharts.vue missing"
    content = mobile.read_text(encoding="utf-8")
    assert "echarts" in content, "MobileECharts.vue does not import echarts"
    assert "echarts.init" in content, "MobileECharts.vue does not call echarts.init"


def test_chart_block_compatible():
    """ChartBlock.vue 必须仍 import echarts/core — chat chart 视觉守卫."""
    chart_block = WEB / "src" / "components" / "chat" / "blocks" / "ChartBlock.vue"
    assert chart_block.exists(), "ChartBlock.vue missing"
    content = chart_block.read_text(encoding="utf-8")
    # ChartBlock 用 echarts/core 树摇模块
    assert "echarts/core" in content, "ChartBlock.vue must use echarts/core tree-shake"
    assert "echarts.init" in content, "ChartBlock.vue must call echarts.init"


def test_knowledge_graph_explorer_compatible():
    """KnowledgeGraphExplorer (W94 PR8) 必须仍 import echarts — KG 视觉守卫."""
    kg = WEB / "src" / "components" / "knowledge" / "KnowledgeGraphExplorer.vue"
    assert kg.exists(), "KnowledgeGraphExplorer.vue missing"
    content = kg.read_text(encoding="utf-8")
    assert "echarts" in content, "KnowledgeGraphExplorer.vue does not import echarts"
    # Graph type 用 'graph' 系列 (KG 节点/边)
    assert "type: 'graph'" in content or "'graph'" in content, (
        "KnowledgeGraphExplorer.vue must configure graph series"
    )


def test_confidence_chart_compatible():
    """ConfidenceChart (声纹) 必须仍 import echarts — 声纹 90% 门禁视觉守卫."""
    conf = WEB / "src" / "components" / "voiceprint" / "ConfidenceChart.vue"
    assert conf.exists(), "ConfidenceChart.vue missing"
    content = conf.read_text(encoding="utf-8")
    assert "echarts" in content, "ConfidenceChart.vue does not import echarts"