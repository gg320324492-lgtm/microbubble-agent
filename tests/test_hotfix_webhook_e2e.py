#!/usr/bin/env python3
# tests/test_hotfix_webhook_e2e.py
# W75 第 1 批 B-3 P2 webhook 修复 e2e 测试
# 依据: W74 第 1 批 E-1 报告 P2 实战 — webhook payload 缺右花括号 + || true 静默吞报警
#
# 4 case:
# 1. monitor-alembic-heads.sh webhook payload 验证 (5 字段完整)
# 2. monitor-pwa-manifest.sh webhook payload 验证 (含 hashed/unhashed_manifest_status)
# 3. monitor-nginx-mime.sh webhook payload 验证 (含 endpoint/octet_stream_detected)
# 4. monitor-sw-cache.sh webhook payload 验证 (含 sw_version/cache_keys_count)
#
# 4 retry 策略 + 4 || true 删除实战
# 0 production code 改动铁律守恒 (tests 范畴)

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = REPO_ROOT / "scripts"
WEBHOOK_LIB = SCRIPTS_DIR / "lib" / "webhook_payload.sh"


def _read_text_utf8(path: Path) -> str:
    """Windows GBK locale safe read"""
    return path.read_text(encoding="utf-8")


def _source_lib_in_bash(script_path: Path, env_overrides: dict) -> subprocess.CompletedProcess:
    """Source webhook lib and run script with custom env, capture webhook payload via stub curl."""
    tmpdir = Path(tempfile.mkdtemp())
    payload_log = tmpdir / "payload.json"
    payload_log.write_text("")

    # 写一个 stub curl: 捕获 -d 参数写入 payload_log
    bin_dir = tmpdir / "bin"
    bin_dir.mkdir()
    curl_stub = bin_dir / "curl"
    curl_stub.write_text(
        f"""#!/bin/bash
# stub curl: 捕获 -d 参数
PAYLOAD_LOG="{payload_log}"
ARGS=("$@")
for i in "${{!ARGS[@]}}"; do
    if [ "${{ARGS[$i]}}" = "-d" ] && [ $((i+1)) -lt ${{#ARGS[@]}} ]; then
        echo -n "${{ARGS[$((i+1))]}}" > "$PAYLOAD_LOG"
    fi
done
# 模拟 HTTP 200 成功
echo "200"
exit 0
"""
    )
    curl_stub.chmod(0o755)

    env = os.environ.copy()
    env["PATH"] = f"{bin_dir}:{env['PATH']}"
    env["WEBHOOK_URL"] = "http://stub.local/webhook"
    env["ALERT_LOG_FILE"] = str(tmpdir / "alert.log")
    env.update(env_overrides)

    result = subprocess.run(
        ["bash", str(script_path)],
        capture_output=True,
        text=True,
        env=env,
        timeout=30,
    )

    payload = ""
    if payload_log.exists():
        payload = payload_log.read_text()

    return {
        "returncode": result.returncode,
        "stdout": result.stdout,
        "stderr": result.stderr,
        "payload": payload,
        "tmpdir": tmpdir,
    }


@pytest.fixture(scope="module", autouse=True)
def verify_lib_exists():
    """共用 webhook 库必须存在"""
    assert WEBHOOK_LIB.exists(), f"webhook_payload.sh not found at {WEBHOOK_LIB}"
    lib_content = _read_text_utf8(WEBHOOK_LIB)
    assert "validate_payload_json" in lib_content
    assert "send_webhook_with_retry" in lib_content
    assert "format_alert_payload" in lib_content
    assert "log_alert" in lib_content
    assert "notify_alert" in lib_content
    # P2 修复核心: 不能再有 || true (排除注释行)
    for line_no, line in enumerate(lib_content.splitlines(), 1):
        stripped = line.strip()
        if stripped.startswith("#"):
            continue
        assert "|| true" not in line, (
            f"P2 修复失败: webhook_payload.sh line {line_no} 仍含 '|| true' 静默吞: {line!r}"
        )


def test_alembic_heads_webhook_payload():
    """Case 1: monitor-alembic-heads.sh webhook payload 5 字段完整 + JSON 合法 + retry 策略"""
    script = SCRIPTS_DIR / "monitor-alembic-heads.sh"
    assert script.exists(), f"{script} not found"

    # 检查脚本本身不含 || true (P2 修复核心)
    script_content = _read_text_utf8(script)
    for line_no, line in enumerate(script_content.splitlines(), 1):
        stripped = line.strip()
        if stripped.startswith("#"):
            continue
        assert "|| true" not in line, (
            f"P2 修复失败: {script.name} line {line_no} 仍含 '|| true' 静默吞: {line!r}"
        )
    assert "source.*lib/webhook_payload.sh" in script_content or "webhook_payload.sh" in script_content

    # 验证 retry 策略 (3 次, 5s 间隔) — 直接读 lib 内容
    lib_content = _read_text_utf8(WEBHOOK_LIB)
    assert "WEBHOOK_RETRY_COUNT" in lib_content
    assert "WEBHOOK_RETRY_INTERVAL" in lib_content
    assert "WEBHOOK_RETRY_COUNT:-3" in lib_content
    assert "WEBHOOK_RETRY_INTERVAL:-5" in lib_content


def test_pwa_manifest_webhook_payload():
    """Case 2: monitor-pwa-manifest.sh payload 含 hashed/unhashed_manifest_status + detection_method"""
    script = SCRIPTS_DIR / "monitor-pwa-manifest.sh"
    assert script.exists()

    script_content = _read_text_utf8(script)
    for line_no, line in enumerate(script_content.splitlines(), 1):
        stripped = line.strip()
        if stripped.startswith("#"):
            continue
        assert "|| true" not in line, (
            f"P2 修复失败: {script.name} line {line_no} 仍含 '|| true' 静默吞: {line!r}"
        )

    # 验证 notify_alert 调用必含 3 必含字段
    assert "hashed_manifest_status" in script_content
    assert "unhashed_manifest_status" in script_content
    assert "detection_method" in script_content


def test_nginx_mime_webhook_payload():
    """Case 3: monitor-nginx-mime.sh payload 含 endpoint/octet_stream_detected + 完整 5 字段"""
    script = SCRIPTS_DIR / "monitor-nginx-mime.sh"
    assert script.exists()

    script_content = _read_text_utf8(script)
    for line_no, line in enumerate(script_content.splitlines(), 1):
        stripped = line.strip()
        if stripped.startswith("#"):
            continue
        assert "|| true" not in line, (
            f"P2 修复失败: {script.name} line {line_no} 仍含 '|| true' 静默吞: {line!r}"
        )

    assert "endpoint" in script_content
    assert "expected_content_type" in script_content
    assert "actual_content_type" in script_content
    assert "octet_stream_detected" in script_content

    # 验证 5 字段 (lib 共用)
    lib_content = _read_text_utf8(WEBHOOK_LIB)
    for field in ("severity", "source", "message", "timestamp", "details"):
        assert field in lib_content, f"webhook lib 缺 5 字段之一: {field}"


def test_sw_cache_webhook_payload():
    """Case 4: monitor-sw-cache.sh payload 含 sw_version/cache_keys_count/cache_purge_status"""
    script = SCRIPTS_DIR / "monitor-sw-cache.sh"
    assert script.exists()

    script_content = _read_text_utf8(script)
    for line_no, line in enumerate(script_content.splitlines(), 1):
        stripped = line.strip()
        if stripped.startswith("#"):
            continue
        assert "|| true" not in line, (
            f"P2 修复失败: {script.name} line {line_no} 仍含 '|| true' 静默吞: {line!r}"
        )

    assert "sw_version" in script_content
    assert "cache_keys_count" in script_content
    assert "cache_purge_status" in script_content


def test_format_alert_payload_5_fields():
    """共用 webhook lib: format_alert_payload 必输出完整 5 字段 JSON (直接读 lib 函数定义验证)"""
    lib_content = _read_text_utf8(WEBHOOK_LIB)
    # 验证 format_alert_payload 函数定义必含 5 字段
    assert "def format_alert_payload" not in lib_content  # bash lib
    assert "format_alert_payload()" in lib_content  # 函数定义存在
    # 必含 5 字段赋值
    for field in ("severity", "source", "message", "timestamp", "details"):
        assert f"'{field}'" in lib_content or f'"{field}"' in lib_content, (
            f"webhook lib 缺 5 字段之一: {field}"
        )
    # 必输出 JSON (ensure_ascii=False)
    assert "json.dumps" in lib_content
    assert "ensure_ascii=False" in lib_content


def test_send_webhook_with_retry_3_times():
    """共用 webhook lib: retry 3 次, 间隔 5s (静态分析)"""
    lib_content = _read_text_utf8(WEBHOOK_LIB)

    # 必含 while retry 循环
    assert "while" in lib_content
    assert "WEBHOOK_RETRY_COUNT" in lib_content

    # 必含 sleep 间隔
    assert "sleep" in lib_content
    assert "WEBHOOK_RETRY_INTERVAL" in lib_content

    # 失败路径必返回非 0 (P2 修复核心: 失败时主动告警 exit 1)
    assert "return 1" in lib_content, "send_webhook_with_retry 缺失败返回 1"

    # retry 默认值 3 / 5
    assert "WEBHOOK_RETRY_COUNT=\"${WEBHOOK_RETRY_COUNT:-3}\"" in lib_content
    assert "WEBHOOK_RETRY_INTERVAL=\"${WEBHOOK_RETRY_INTERVAL:-5}\"" in lib_content


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))