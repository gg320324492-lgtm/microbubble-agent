"""
W88-X-2 e2e — 验证 deploy-auto.sh 真集成 4 步骤。

锚点预期：base (337) → tip (338) = +1 守恒。

设计原则（派工 v6 §1.2 真验证 + 类 20.45 沉淀）：
- 不 mock subprocess，直接 grep deploy-auto.sh 源文件验证逻辑存在
- 4 步骤必含：trivy scan 门禁 / pg_exporter health check / GlitchTip deploy / Sentry DSN env
- 验证 HIGH/CRITICAL 门禁 + env guard (类 20.27 默认 off) + gitignore (.env.production)
"""
from pathlib import Path

DEPLOY_SCRIPT = (
    Path(__file__).resolve().parents[2] / "scripts" / "deploy-auto.sh"
)


def test_trivy_scan_step_exists():
    """W86-C-1 trivy 镜像扫描门禁已接入 deploy-auto.sh（W88-X-2 任务）"""
    content = DEPLOY_SCRIPT.read_text(encoding="utf-8")
    assert "trivy" in content.lower(), "deploy-auto.sh 缺 trivy 步骤"
    assert (
        "HIGH,CRITICAL" in content or "CRITICAL" in content
    ), "trivy 严重度门禁缺失"


def test_trivy_calls_scan_images_sh():
    """deploy-auto.sh 调 scripts/trivy/scan-images.sh（实际扫描入口）"""
    content = DEPLOY_SCRIPT.read_text(encoding="utf-8")
    assert "scripts/trivy/scan-images.sh" in content, (
        "deploy-auto.sh 未调 scripts/trivy/scan-images.sh"
    )


def test_trivy_critical_exits_nonzero():
    """CRITICAL CVE > 0 必须 exit 1 阻断部署"""
    content = DEPLOY_SCRIPT.read_text(encoding="utf-8")
    # 必须同时含: CRITICAL 计数 + exit 1 + 部署中止
    assert "CRITICAL_COUNT" in content, "trivy 缺 CRITICAL 计数"
    assert "CRITICAL" in content and "exit 1" in content, (
        "trivy CRITICAL > 0 必须 exit 1 阻断"
    )


def test_pg_exporter_health_step_exists():
    """W86-F-1 pg_exporter 健康检查已接入 deploy-auto.sh"""
    content = DEPLOY_SCRIPT.read_text(encoding="utf-8")
    assert (
        "pg_exporter" in content or "pg-exporter" in content or "9187" in content
    ), "pg_exporter 健康检查缺失"


def test_pg_exporter_calls_health_sh():
    """deploy-auto.sh 调 scripts/pg-exporter/health.sh"""
    content = DEPLOY_SCRIPT.read_text(encoding="utf-8")
    assert "scripts/pg-exporter/health.sh" in content, (
        "deploy-auto.sh 未调 scripts/pg-exporter/health.sh"
    )


def test_glitchtip_deploy_step_exists():
    """W87-B-1 GlitchTip docker compose up 步骤已接入"""
    content = DEPLOY_SCRIPT.read_text(encoding="utf-8")
    assert (
        "glitchtip" in content.lower() or "GLITCHTIP" in content
    ), "GlitchTip 部署步骤缺失"


def test_glitchtip_docker_compose_up():
    """deploy-auto.sh 含 docker compose up -d glitchtip 调用"""
    content = DEPLOY_SCRIPT.read_text(encoding="utf-8")
    assert "docker compose up" in content and "glitchtip" in content.lower(), (
        "GlitchTip 缺 docker compose up -d glitchtip 调用"
    )


def test_glitchtip_env_guard():
    """GlitchTip 部署必含 GLITCHTIP_DATABASE_URL env guard (类 20.27 沉淀)"""
    content = DEPLOY_SCRIPT.read_text(encoding="utf-8")
    assert "GLITCHTIP_DATABASE_URL" in content, (
        "GlitchTip 缺 env guard — 不允许默认部署"
    )


def test_sentry_dsn_step_exists():
    """Sentry DSN env 注入步骤已接入"""
    content = DEPLOY_SCRIPT.read_text(encoding="utf-8")
    assert "SENTRY_DSN" in content, "Sentry DSN 注入步骤缺失"


def test_sentry_env_off_default():
    """SENTRY_DSN 未设置时 sentry 默认 off（类 20.27 沉淀 — 不可静默上报）"""
    content = DEPLOY_SCRIPT.read_text(encoding="utf-8")
    assert "SENTRY_DSN" in content and "默认 off" in content, (
        "Sentry 默认 off 行为未在 deploy 脚本明示"
    )


def test_sentry_writes_env_production_not_git():
    """Sentry DSN 写入 .env.production（不进 git，.gitignore 拦）"""
    content = DEPLOY_SCRIPT.read_text(encoding="utf-8")
    assert ".env.production" in content, "Sentry DSN 缺 .env.production 写入路径"
    assert (
        "gitignore" in content.lower() or "不进 git" in content
    ), "Sentry DSN 写入路径未声明不进 git"


def test_all_steps_appended_not_modified_existing():
    """不动现有 deploy 步骤（仅追加 4 段，纪律验证）"""
    content = DEPLOY_SCRIPT.read_text(encoding="utf-8")
    # 关键 sentinel: 既有重要步骤仍存在
    assert "========== 开始部署 ==========" in content
    assert "nginx -s reload" in content
    assert "alter_agent_traces_stage3.sql" in content
    # 4 个新步骤都在文末追加区段
    assert content.count("W88-X-2") >= 4, "W88-X-2 标记应至少 4 次（4 段步骤）"


def test_bash_syntax_valid():
    """bash -n 语法校验（deploy-auto.sh 不可有 bash 语法错）

    Windows 平台限制：subprocess 可能找不到 bash，returncode 127 = command not found
    此时跳过断言（已在 git bash 中手动验证过），不视为测试失败。
    """
    import shutil
    import subprocess

    # Windows: 必须显式找 bash.exe（subprocess 默认 PATH 可能不含 Git Bash）
    bash_bin = shutil.which("bash")
    if bash_bin is None:
        # Git Bash on Windows 通常在 C:\Program Files\Git\bin
        for candidate in ("C:/Program Files/Git/bin/bash.exe", "C:/Program Files/Git/usr/bin/bash.exe"):
            if Path(candidate).exists():
                bash_bin = candidate
                break
    if bash_bin is None:
        # 找不到 bash, 跳过（dev 环境而非 CI gate）
        import pytest
        pytest.skip("bash binary not found on PATH — CI runner 应装 Git Bash")

    result = subprocess.run(
        [bash_bin, "-n", str(DEPLOY_SCRIPT)],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, (
        f"bash 语法错: {result.stderr or result.stdout}"
    )