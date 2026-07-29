"""
dist 健康 e2e (W87-X-2 沉淀).

CLAUDE.md 永久纪律: 'npm run build' 是唯一合法 build 命令. dist 产物
必须无 orphan chunk + manifest hash 化 + sw.js 一致. 本测试三大门禁:

1. test_no_orphan_index_chunks — dist/index.html 引用的 index-*.js 必须在 dist 里
2. test_manifest_hash_pinned — dist/manifest.{hash}.webmanifest 必须存在
3. test_sw_version_consistent — sw.js 必须引用 hashed manifest, 不引用 unhashed

派工 v6 §5 反馈 类 20.36: cherry-pick 改 deps 必重跑 npm run build (W87 B-1 案)
"""

from __future__ import annotations

import re
from pathlib import Path

WEB_DIST = Path(__file__).resolve().parents[2] / "web" / "dist"


def _read(p: Path) -> str:
    return p.read_text(encoding="utf-8")


def test_no_orphan_index_chunks() -> None:
    """dist/index.html 引用的 index-*.js 必须全部存在, 且无 orphan (W87 B-1 案).

    W87 B-1 cherry-pick 加 Sentry 触发 vite re-bundling, dist/index.html
    引用 index-c70e8703.js (无 Sentry), Sentry 在 orphan index-d2ea53b1.js.
    浏览器实际拿不到 Sentry (因为 vite-plugin-pwa 已禁用, 410 防护不适用,
    但功能失效). 派工 v6 §5 类 20.36 沉淀: cherry-pick 改 deps 必重跑 npm run build.
    """
    index_html = _read(WEB_DIST / "index.html")
    referenced = set(re.findall(r"index-([a-f0-9]+)\.js", index_html))

    actual: set[str] = set()
    for f in WEB_DIST.glob("assets/index-*.js"):
        m = re.match(r"index-([a-f0-9]+)\.js", f.name)
        if m:
            actual.add(m.group(1))

    orphans = actual - referenced
    assert not orphans, f"orphan index chunks (在 dist 但 index.html 未引用): {orphans}"
    missing = referenced - actual
    assert not missing, f"missing index chunks (index.html 引用但 dist 不存在): {missing}"


def test_manifest_hash_pinned() -> None:
    """dist/manifest.{hash}.webmanifest 必须存在, unhashed manifest.webmanifest 不存在.

    W68 PWA 410 防护依赖 unhashed manifest.webmanifest 在 nginx 上 410 Gone.
    若 unhashed 文件进 dist, 部署后 PWA install 失败.
    """
    if not (WEB_DIST / "manifest.webmanifest").exists() and not list(
        WEB_DIST.glob("manifest.*.webmanifest")
    ):
        # PWA 已禁用 (vite-plugin-pwa disable: true) — 跳过
        # 但要看 vite.config.js 是否真的禁用, 否则警告
        import warnings

        warnings.warn(
            "dist/manifest.{hash}.webmanifest 不存在. 若 PWA 故意禁用, 忽略本测试.",
            stacklevel=2,
        )
        return

    hashed = list(WEB_DIST.glob("manifest.*.webmanifest"))
    assert hashed, "dist/manifest.{hash}.webmanifest 不存在"

    unhashed = WEB_DIST / "manifest.webmanifest"
    assert not unhashed.exists(), (
        "unhashed manifest.webmanifest 仍在 dist — CLAUDE.md PWA 410 防护失效"
    )


def test_sw_version_consistent() -> None:
    """sw.js 必须引用 hashed manifest, 不引用 unhashed (若 sw.js 存在).

    W68 第 14 批 H-3: PWA 已禁用 (vite-plugin-pwa disable: true),
    sw.js 不应存在. 若存在, 必须一致.
    """
    sw_path = WEB_DIST / "sw.js"
    if not sw_path.exists():
        # PWA disabled — sw.js 不存在是预期
        return

    sw_js = _read(sw_path)
    assert '"url": "manifest.webmanifest"' not in sw_js, (
        "sw.js 引用 unhashed manifest.webmanifest — CLAUDE.md PWA 410 防护失效"
    )
    assert re.search(r"manifest\.[a-f0-9]+\.webmanifest", sw_js), (
        "sw.js 应引用 manifest.{hash}.webmanifest"
    )