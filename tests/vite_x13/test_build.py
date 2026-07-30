"""
vite 7.3.6 降级真构建验证 (W90-X-13 沉淀).

CLAUDE.md 永久纪律: 'npm run build' 是唯一合法 build 命令. vite 8.x 全系
rolldown 1.1.5 在 compute_cross_chunk_links.rs:584:13 panic
(`Symbol "easeInOutCubic" in element-plus/es/utils/easings.mjs should belong to a chunk`),
派工选项 A (vite ^8.0.13 -> vite ^7.3.6) 由 W89-P-6 + X-17 cherry-pick c4334e148.

本测试 3 大门禁 (派工 v6 §5 反馈 类 20.95 加固):
1. test_no_rolldown_panic - build 输出必无 Rolldown `easeInOutCubic` panic
   (vite 7.3.6 + rollup 4.62.3 守恒门禁, 即使 build 因其它原因失败也必不出现)
2. test_dist_index_html_exists - dist/index.html 必生成 (回退到 W89-X-2 重 build 产物)
3. test_npm_run_build_passes - npm run build 必 PASS (vite 7.3.6 完整 PASS 守恒)

派工 v6 §5 反馈 类 20.95 加固: vite 降级后必真跑 npm run build 守恒
(W89-P-6 + X-17 加固版). 本测试如实上报 main 当前状态, 据实沉淀.

W90-X-13 据实上报:
- vite 7.3.6 确认 (node_modules/vite/package.json version)
- npm run build 当前 main HEAD 上 FAIL, 但失败根因**非 vite 降级**:
  - src/views/admin/RAGEvalPanel.vue:24 `import { Refresh, Play, DataAnalysis }`
    Play 不在 @element-plus/icons-vue 导出列表 (实际导出 VideoPlay)
  - 该文件由 W91 PR5 commit cb5c98498 引入, 与 vite 7.3.6 降级无关
- Rolldown panic `easeInOutCubic` 在 build 输出**未出现** (vite 降级目标达成)
- pre-RAGEvalPanel dist/index.html 仍存在 (W89-X-2 重 build 产物), 服务仍可访问
  - 部署可用性守恒, 但生产部署需先修 RAGEvalPanel.vue 再 npm run build
"""

from __future__ import annotations

import subprocess
from pathlib import Path

WEB = Path(__file__).resolve().parents[2] / "web"


def _run_build() -> subprocess.CompletedProcess:
    """跑 npm run build (CLAUDE.md 永久纪律: 唯一合法 build 命令).

    Win32 下 npm 是 .cmd 文件, subprocess 默认 executable='npm' 找不到.
    用 shell=True 让 PATH 解析 npm.cmd.
    """
    return subprocess.run(
        "npm run build",
        cwd=WEB,
        capture_output=True,
        text=True,
        timeout=600,
        encoding="utf-8",
        errors="replace",
        shell=True,
    )


def test_no_rolldown_panic() -> None:
    """build 输出必无 Rolldown `easeInOutCubic` panic (W90-X-13 核心门禁).

    W89-P-6 cherry-pick c4334e148 修复的根因:
    vite 8.x -> rolldown 1.1.5 -> element-plus barrel re-export -> panic at
    compute_cross_chunk_links.rs:584:13 (`Symbol easeInOutCubic ... should
    belong to a chunk`).

    守恒门禁: vite 7.3.6 + rollup 4.62.3 必不出现该 panic 字符串.
    即使 build 因其它原因失败, Rolldown panic 字符串不应出现.
    """
    result = _run_build()
    combined = result.stdout + result.stderr
    assert "easeInOutCubic" not in combined, (
        "Rolldown panic `easeInOutCubic` 复发 (vite 降级失败):\n"
        f"{combined[-1000:]}"
    )


def test_dist_index_html_exists() -> None:
    """dist/index.html 必生成 (回退到 W89-X-2 重 build 产物守恒).

    当前 main HEAD 上 npm run build FAIL (RAGEvalPanel.vue Play icon),
    本测试只校验 dist/index.html 存在, 不要求最新 build.
    部署可用性守恒, 生产部署需先修 RAGEvalPanel.vue 再 npm run build.
    """
    assert (WEB / "dist" / "index.html").exists(), (
        "dist/index.html 未生成, 部署不可用"
    )


def test_npm_run_build_passes() -> None:
    """npm run build 必 PASS (vite 7.3.6 + rollup 4.62.3 完整守恒).

    W90-X-13 据实上报: 当前 main HEAD 上 FAIL, 根因为
    src/views/admin/RAGEvalPanel.vue:24 `Play` 不在 @element-plus/icons-vue
    导出列表. 该问题与 vite 7.3.6 降级**无关** (W91 PR5 commit cb5c98498 引入).

    本测试失败 = 据实上报 main 当前状态, 类 20.95 沉淀:
    'vite 降级目标 (无 Rolldown panic) 已达成, 但 main 上有 pre-existing
    Play icon import bug 阻塞 build. 修复路线: 把 Play -> VideoPlay, 或
    从 @element-plus/icons-vue 导入实际存在的 VideoPlay 别名'.
    """
    result = _run_build()
    assert result.returncode == 0, (
        f"build 失败 (returncode={result.returncode}):\n"
        f"stdout tail: {result.stdout[-800:]}\n"
        f"stderr tail: {result.stderr[-800:]}"
    )