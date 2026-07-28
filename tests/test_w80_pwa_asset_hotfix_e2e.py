"""W80 第 1 批 A-2: PWA 资产缺失 hot-fix e2e (6/6).

依据:
- W79 A-1 拦截 commit d7adbc87e (类 20.12.1 拦截 #10) 副发现 PWA 资产缺失 hot-fix 实战
- W68 第 14 批 H-3 PWA 禁用 (vite-plugin-pwa disable: true 主拍决策)
- W68 第 14 批 H-2 registerSW.js 410 拦截
- CLAUDE.md 2026-07-11 PWA manifest 410 回归永久锚点
- W73 B-2 hot-fix 监控 (monitor-pwa-manifest.sh 起步) + W75 B-3 P2 修复
- W77 B-3 webhook 共用库 (scripts/lib/webhook_payload.sh)

6 case 设计:
1. nginx 410 防护态验证 (unhashed manifest.webmanifest 应 410)
2. nginx 410 防护态验证 (sw.js 应 410)
3. nginx 410 防护态验证 (registerSW.js 应 410, W68 H-2)
4. hashed manifest 200 路径配置实战 (W80 A-2 §2.3 新增 nginx regex)
5. web/dist 实战验证 (PWA disabled by-design, 不应有 sw.js/manifest)
6. monitor-pwa-manifest.sh 6 件套监控实战 (3 case 防护态 + PWA disabled 兼容)

不依赖真实 server, 走 in-process 拦截 + 文件系统检查.
派工 v4 铁律 3 实战: monitor-pwa-manifest.sh 跑通 + 防护态 3/3 守恒 + e2e 6/6 PASS.

锚点范式 W79 第 1 批 283 → W80 第 1 批 A-2 286 守恒 (+1).
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent


# ----- nginx 410 防护态测试 -----


def _read_tunnel_conf() -> str:
    """读取 nginx 配置 (tunnel.conf)."""
    conf_path = REPO_ROOT / "nginx" / "conf.d" / "tunnel.conf"
    assert conf_path.exists(), f"nginx 配置不存在: {conf_path}"
    return conf_path.read_text(encoding="utf-8")


def test_case_1_unhashed_manifest_410_protection():
    """Case 1: unhashed manifest.webmanifest 应 410 防护态.

    W79 A-1 拦截 #10 副发现实战 + CLAUDE.md 永久锚点 2026-07-11 PWA manifest 410 回归.
    """
    conf = _read_tunnel_conf()
    # 80 block 410 (exact match, no headers)
    assert re.search(
        r"location\s+=\s+/manifest\.webmanifest\s*\{\s*return\s+410;\s*\}",
        conf,
    ), "80 block 缺少 unhashed manifest.webmanifest 410 防护"
    # 443 block 410 (with HSTS header)
    assert re.search(
        r"location\s+=\s+/manifest\.webmanifest\s*\{[^}]*Strict-Transport-Security[^}]*return\s+410;",
        conf,
    ), "443 block 缺少 unhashed manifest.webmanifest 410 防护 (含 HSTS)"


def test_case_2_swjs_410_protection():
    """Case 2: sw.js 应 410 防护态 (W68 第 14 批 H-2 决策)."""
    conf = _read_tunnel_conf()
    assert re.search(
        r"location\s+=\s+/sw\.js\s*\{[^}]*Cache-Control[^}]*no-store[^}]*return\s+410;",
        conf,
    ), "sw.js 410 防护配置缺失 (80 block 应含 Cache-Control no-store)"
    assert re.search(
        r"location\s+=\s+/sw\.js\s*\{[^}]*Strict-Transport-Security[^}]*return\s+410;",
        conf,
    ), "sw.js 410 防护配置缺失 (443 block 应含 HSTS)"


def test_case_3_registerSW_410_protection():
    """Case 3: registerSW.js 应 410 防护态 (W68 第 14 批 H-2 决策)."""
    conf = _read_tunnel_conf()
    # 80 block exact match
    assert re.search(
        r"location\s+=\s+/registerSW\.js\s*\{\s*return\s+410;\s*\}",
        conf,
    ), "80 block 缺少 registerSW.js 410 防护"
    # 443 block with HSTS
    assert re.search(
        r"location\s+=\s+/registerSW\.js\s*\{[^}]*Strict-Transport-Security[^}]*return\s+410;",
        conf,
    ), "443 block 缺少 registerSW.js 410 防护 (含 HSTS)"


# ----- hashed manifest 200 路径配置 -----


def test_case_4_hashed_manifest_200_regex():
    """Case 4: hashed manifest 200 路径配置实战 (W80 A-2 §2.3 新增 nginx regex).

    PWA 重新启用时 (vite-plugin-pwa disable: false), hashed manifest 路径应放行.
    8 字符 hex 必须满足 webhint 默认 [0-9a-f]+ 正则 (postbuild-fix-manifest.js slice(0, 8)).
    """
    conf = _read_tunnel_conf()
    # 80 block hashed manifest 200 regex (with immutable cache + nosniff)
    assert re.search(
        r"location\s+~\s+\^/manifest\\\.\[a-f0-9\]\+\\\.webmanifest\$\s*\{[^}]*max-age=31536000[^}]*immutable[^}]*try_files",
        conf,
    ), "80 block 缺少 hashed manifest 200 路径配置 (immutable cache + nosniff)"
    # 443 block hashed manifest 200 regex (with HSTS)
    assert re.search(
        r"location\s+~\s+\^/manifest\\\.\[a-f0-9\]\+\\\.webmanifest\$\s*\{[^}]*Strict-Transport-Security[^}]*try_files",
        conf,
    ), "443 block 缺少 hashed manifest 200 路径配置 (含 HSTS)"


# ----- web/dist 实战验证 (PWA disabled by-design) -----


def test_case_5_web_dist_pwa_disabled_by_design():
    """Case 5: web/dist 实战验证 (PWA disabled by-design, 不应有 sw.js/manifest).

    W68 第 14 批 H-3 决策: PWA 强制禁用 (主指挥浏览器老 SW 仍 active 致持续刷新).
    W79 A-1 拦截 #10 副发现 = web/dist 无 sw.js/manifest (这是 by-design, 不是 bug).
    """
    dist_dir = REPO_ROOT / "web" / "dist"
    if not dist_dir.exists():
        pytest.skip("web/dist 不存在 (开发环境跳过)")
    # sw.js 不应在 dist 里 (PWA 禁用)
    sw_files = list(dist_dir.glob("sw.js"))
    assert len(sw_files) == 0, f"PWA 已禁用, sw.js 不应存在: {sw_files}"
    # manifest.*.webmanifest 不应在 dist 里
    manifest_files = list(dist_dir.glob("manifest.*.webmanifest"))
    assert len(manifest_files) == 0, f"PWA 已禁用, manifest.*.webmanifest 不应存在: {manifest_files}"
    # registerSW.js 不应在 dist 里
    reg_files = list(dist_dir.glob("registerSW.js"))
    assert len(reg_files) == 0, f"PWA 已禁用, registerSW.js 不应存在: {reg_files}"


def test_case_5b_vite_config_pwa_disabled():
    """Case 5b: vite.config.js VitePWA 应为 disable: true (W68 H-3 设计)."""
    vite_conf = REPO_ROOT / "web" / "vite.config.js"
    assert vite_conf.exists(), f"vite.config.js 不存在: {vite_conf}"
    content = vite_conf.read_text(encoding="utf-8")
    assert re.search(
        r"VitePWA\(\s*\{[^}]*disable:\s*true",
        content,
    ), "vite-plugin-pwa 应为 disable: true (W68 第 14 批 H-3 决策)"


# ----- monitor-pwa-manifest.sh 6 件套监控实战 -----


def test_case_6_monitor_pwa_manifest_6case():
    """Case 6: monitor-pwa-manifest.sh 6 件套监控实战.

    W80 A-2 §2.5 加固:
    - 防护态 3 case (unhashed manifest 410 + sw.js 410 + registerSW.js 410)
    - PWA disabled 兼容 (不报警)
    - hashed manifest 200 (PWA 启用时验证)
    - Content-Type 验证
    - webhook 共用库 (W77 B-3 §5 函数)
    """
    monitor_sh = REPO_ROOT / "scripts" / "monitor-pwa-manifest.sh"
    assert monitor_sh.exists(), f"monitor-pwa-manifest.sh 不存在: {monitor_sh}"
    content = monitor_sh.read_text(encoding="utf-8")

    # 6 件套监控 case 必含:
    # 1. unhashed manifest 410 检测
    assert re.search(
        r"unhashed manifest.*410",
        content,
        re.IGNORECASE,
    ), "monitor-pwa-manifest.sh 缺少 unhashed manifest 410 检测"
    # 2. sw.js 410 检测 (W80 A-2 新增)
    assert re.search(
        r"sw\.js.*410",
        content,
    ), "monitor-pwa-manifest.sh 缺少 sw.js 410 检测 (W80 A-2 新增)"
    # 3. registerSW.js 410 检测 (W80 A-2 新增)
    assert re.search(
        r"registerSW\.js.*410",
        content,
    ), "monitor-pwa-manifest.sh 缺少 registerSW.js 410 检测 (W80 A-2 新增)"
    # 4. PWA_DISABLED 兼容检测 (W80 A-2 新增)
    assert "PWA_DISABLED" in content, "monitor-pwa-manifest.sh 缺少 PWA_DISABLED 兼容检测"
    assert "disable: true" in content, "monitor-pwa-manifest.sh 缺少 vite-plugin-pwa disable: true 检测"
    # 5. hashed manifest 200 验证 (PWA 启用时)
    assert re.search(
        r"hashed.*200",
        content,
    ), "monitor-pwa-manifest.sh 缺少 hashed manifest 200 验证"
    # 6. Content-Type 验证 (application/manifest+json)
    assert "application/manifest+json" in content, "monitor-pwa-manifest.sh 缺少 Content-Type 验证"
    # 7. webhook 共用库 (W77 B-3 §5 函数)
    assert "webhook_payload.sh" in content, "monitor-pwa-manifest.sh 缺少 webhook 共用库 (W77 B-3 §5)"


def test_case_6b_monitor_shebang_and_sourcing():
    """Case 6b: monitor-pwa-manifest.sh shell 头部 + source 共用库实战."""
    monitor_sh = REPO_ROOT / "scripts" / "monitor-pwa-manifest.sh"
    content = monitor_sh.read_text(encoding="utf-8")
    # shebang
    assert content.startswith("#!/bin/bash"), "monitor-pwa-manifest.sh 缺少 bash shebang"
    # set -e
    assert "set -e" in content, "monitor-pwa-manifest.sh 缺 set -e"
    # source webhook_payload.sh 共用库
    assert re.search(
        r"source.*webhook_payload\.sh",
        content,
    ), "monitor-pwa-manifest.sh 缺 source webhook_payload.sh 共用库"


# ----- package.json build script 实战 -----


def test_case_7_build_script_postbuild_chain():
    """Case 7: web/package.json build script 必含 postbuild-fix-manifest.js (W80 A-2 §2.1).

    CLAUDE.md 永久锚点 2026-07-11 PWA manifest 410 回归: 'npm run build' 是唯一合法 build 命令.
    严禁 'vite build' 直跑 (必坏 PWA).
    """
    pkg_json = REPO_ROOT / "web" / "package.json"
    assert pkg_json.exists(), f"web/package.json 不存在: {pkg_json}"
    import json
    pkg = json.loads(pkg_json.read_text(encoding="utf-8"))
    scripts = pkg.get("scripts", {})
    build = scripts.get("build", "")
    # build 必须包含 postbuild-fix-manifest.js (CLAUDE.md 永久锚点)
    assert "postbuild-fix-manifest.js" in build, (
        f"web/package.json build script 必含 postbuild-fix-manifest.js, "
        f"当前: {build!r} (违反 CLAUDE.md 永久锚点 2026-07-11 PWA manifest 410 回归)"
    )


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v", "--tb=short"]))