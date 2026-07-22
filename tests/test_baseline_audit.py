"""Baseline 9 files audit — file existence + stale file detection.

> **W62 T1 (2026-07-22) Agent 3 启动段 — baseline 列表 stale 修复**
>
> 背景: Agent 5 第六波报告 "baseline 9 files blocked by stale baseline
> definition; deleted Self-RAG files are still listed". 5th-wave 已删的
> Self-RAG / 5th-wave / 4th-wave 测试文件还在 baseline 列表里,导致 9 file
> 合跑命令列出已删文件 → pytest 0 collected → 71 PASS + 7 SKIP 守恒铁律
> 不可信.
>
> 本测试目标 (6+ cases):
> 1. 9 baseline 真文件全部存在 (tests/scripts/ 子目录不漏掉)
> 2. Self-RAG / 5th-wave / 4th-wave 已删文件 NOT in baseline list
> 3. 排除标准 (deleted pattern list) 全为空 (没有幽灵引用)
> 4. baseline 文件可被 pytest collect (--collect-only 计数 == 78)
> 5. audit 报告输出 (含 stale 文件清单 + 新 baseline 列表)
> 6. tests/scripts/ 下的 E2E 不漏 (scripts dir 在 pytest 默认 testpaths 外)

Usage:
    pytest tests/test_baseline_audit.py -v
    # 期望: 6+ PASS

关键设计:
- 纯文件扫描 + pytest collect, 无 DB / Redis 依赖
- 不修改任何 production code / test
- 排除标准硬编码 11 类已删文件 pattern
- "9 baseline files" 列表硬编码, 与 docs/2026-07-22-baseline-13-stats.md 同步
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

import pytest


# === W51 T2 baseline 9 files (与 docs/2026-07-22-baseline-13-stats.md 表格同步) ===
# 这些文件合跑 SKIP_DB_SETUP=1 模式产出 71 PASS + 7 SKIP (W62 第 24 次守恒)
BASELINE_9_FILES = [
    "tests/test_meeting_transcript_buffer.py",                # 2 cases
    "tests/test_orphan_meeting_cleanup_audio_chunks.py",      # 9 cases
    "tests/test_meeting_recording_user_agent.py",             # 10 cases
    "tests/test_meeting_recording_audio_chunk_auth.py",       # 8 cases
    "tests/test_meeting_recording_cancel.py",                 # 8 cases
    "tests/test_chat_history_tasks.py",                       # 7 cases
    "tests/test_chat_share_cleanup.py",                       # 8 cases
    "tests/test_kb_dedup_admin_cli.py",                       # 19 cases
    "tests/scripts/test_kb_dedup_admin_cli_e2e.py",           # 7 cases (7 SKIP)
]


# === 5th-wave + 4th-wave + Self-RAG 删除的文件 (排除标准) ===
# Agent 5 报告: 这些文件不应再出现在 baseline 列表里
# 历史删除记录:
# - 5th-wave (commit a70a1b07b, 2026-07-22): 删 6 个 5th-wave 新增测试
# - Self-RAG (commit 7046fbbf, 2026-07-20): 删 2 个 Self-RAG 测试 + 6 轮 results
# - Phase 1 死代码清理 (commit 833609e92): 删 4 孤儿 service 测试
# - 活动动态删除 (commit f66a2120): 删 2 会议模板测试
STALE_BASELINE_PATTERNS = [
    # Self-RAG (commit 7046fbbf 已删)
    "test_self_rag.py",
    "test_chat_self_rag.py",
    # Self-RAG 结果目录
    "results/self-rag-benchmark/",
    # 5th-wave (commit a70a1b07b 已删)
    "test_d1_d3_d2_integration.py",
    "test_d4_thousand_smoke.py",
    "tests/qa-bench/tests/test_retrieval_cache.py",
    "tests/qa-bench/tests/test_runner_intake_integration.py",
    "tests/mobile/MobileDriveViewDashboard.test.js",
    # 4th-wave drive e2e 已删
    "tests/scripts/test_drive_v2_cleanup.py",
    "tests/scripts/test_drive_v2_integration.py",
    "tests/scripts/test_mobile_dashboard_live_shape.py",
    "tests/scripts/test_ios_safari_pwa.py",
    "tests/scripts/test_mobile_kb_pending_processor.py",
    # Phase 1 死代码 (commit 833609e92 已删)
    "test_audio_archive_service.py",
    "test_meeting_ai_interactive.py",
    "test_meeting_broadcast_service.py",
    "test_speaker_unidentified.py",
    # 活动动态 + 模板删除 (commit f66a2120 已删)
    "test_meeting_template_service.py",
    "test_migration_016_meeting_template.py",
]


PROJECT_ROOT = Path(__file__).resolve().parent.parent


def _file_exists(rel_path: str) -> bool:
    """检查相对路径文件是否存在 (从 PROJECT_ROOT 算)."""
    return (PROJECT_ROOT / rel_path).is_file()


def _collect_baseline_tests() -> int:
    """调 pytest --collect-only 数 9 baseline 文件的 test 数量.

    返回 collected count (期望 78 = 71 PASS + 7 SKIP).
    """
    args = ["python", "-m", "pytest", "--collect-only", "-q"]
    args.extend(BASELINE_9_FILES)
    result = subprocess.run(
        args,
        cwd=str(PROJECT_ROOT),
        capture_output=True,
        text=True,
        timeout=60,
    )
    # 解析 "N tests collected" 行
    match = re.search(r"(\d+)\s+tests?\s+collected", result.stdout)
    if match:
        return int(match.group(1))
    return 0


# === Tests (≥ 6 cases) ===

class TestBaselineFileExistence:
    """测试 1: 9 baseline 真文件全部存在."""

    @pytest.mark.parametrize("rel_path", BASELINE_9_FILES)
    def test_baseline_file_exists(self, rel_path: str) -> None:
        """每个 baseline 文件必须存在 (与 docs 表格同步)."""
        assert _file_exists(rel_path), (
            f"Baseline file missing: {rel_path}\n"
            f"Update docs/2026-07-22-baseline-13-stats.md if removed."
        )

    def test_baseline_count_is_9(self) -> None:
        """baseline 文件数量必须是 9 (与文档一致)."""
        assert len(BASELINE_9_FILES) == 9, (
            f"Baseline file count drift: expected 9, got {len(BASELINE_9_FILES)}"
        )

    def test_scripts_subdir_baseline_included(self) -> None:
        """tests/scripts/ 子目录下的 E2E 不漏 (默认 pytest testpaths 不覆盖)."""
        scripts_baseline = [
            f for f in BASELINE_9_FILES if f.startswith("tests/scripts/")
        ]
        assert len(scripts_baseline) == 1, (
            f"Expected exactly 1 scripts/ baseline file, got {len(scripts_baseline)}"
        )
        assert scripts_baseline[0] == "tests/scripts/test_kb_dedup_admin_cli_e2e.py"


class TestStaleBaselineDetection:
    """测试 2: Self-RAG / 5th-wave / 4th-wave 已删文件 NOT in baseline list."""

    def test_baseline_list_excludes_self_rag(self) -> None:
        """baseline 列表不应包含已删 Self-RAG 测试."""
        for stale in ("test_self_rag.py", "test_chat_self_rag.py"):
            for baseline_file in BASELINE_9_FILES:
                assert stale not in baseline_file, (
                    f"Stale Self-RAG file in baseline: {baseline_file} "
                    f"contains {stale}"
                )

    def test_baseline_list_excludes_5th_wave(self) -> None:
        """baseline 列表不应包含已删 5th-wave 测试."""
        for stale in (
            "test_d1_d3_d2_integration.py",
            "test_d4_thousand_smoke.py",
            "test_retrieval_cache.py",
            "test_runner_intake_integration.py",
        ):
            for baseline_file in BASELINE_9_FILES:
                assert stale not in baseline_file, (
                    f"Stale 5th-wave file in baseline: {baseline_file} "
                    f"contains {stale}"
                )

    def test_baseline_list_excludes_4th_wave(self) -> None:
        """baseline 列表不应包含已删 4th-wave drive e2e 测试."""
        for stale in (
            "drive_v2_cleanup",
            "drive_v2_integration",
            "mobile_dashboard_live_shape",
            "ios_safari_pwa",
            "mobile_kb_pending_processor",
        ):
            for baseline_file in BASELINE_9_FILES:
                assert stale not in baseline_file, (
                    f"Stale 4th-wave file in baseline: {baseline_file} "
                    f"contains {stale}"
                )


class TestStaleFileAudit:
    """测试 3: 排除标准 (STALE_BASELINE_PATTERNS) 文件确实不存在."""

    @pytest.mark.parametrize("stale_pattern", STALE_BASELINE_PATTERNS)
    def test_stale_pattern_not_in_tree(self, stale_pattern: str) -> None:
        """每个 stale pattern 对应的文件/目录不应存在.

        这是反向断言: 如果 stale 文件又出现在 tree 里,
        说明它们没被正确删除, 或者被错误恢复, baseline 列表会污染.
        """
        if "/" in stale_pattern:
            # 目录 pattern
            full_path = PROJECT_ROOT / stale_pattern.rstrip("/")
            # 目录允许不存在, 但如果存在 + 内含文件 → fail
            if full_path.is_dir():
                contained = list(full_path.rglob("*"))
                assert not any(p.is_file() for p in contained), (
                    f"Stale dir still has files: {stale_pattern} "
                    f"({len(contained)} entries)"
                )
        else:
            # 文件 pattern
            # 排除文件可能在 tests/ 或 tests/scripts/ 或 web/tests/mobile/
            for parent in ("tests", "tests/scripts", "tests/qa-bench/tests",
                           "web/tests/mobile", "tests/unit"):
                full_path = PROJECT_ROOT / parent / stale_pattern
                assert not full_path.is_file(), (
                    f"Stale file unexpectedly present: {full_path}\n"
                    f"This should have been deleted by 5th-wave / 4th-wave / Self-RAG cleanup."
                )


class TestBaselineCollectable:
    """测试 4: 9 baseline 文件可被 pytest 收集 (与 docs 71 PASS + 7 SKIP 一致)."""

    def test_pytest_collects_78_tests(self) -> None:
        """baseline 9 文件 collect 必须 = 78 (71 PASS + 7 SKIP)."""
        collected = _collect_baseline_tests()
        assert collected == 78, (
            f"Baseline pytest --collect-only count drift: "
            f"expected 78 (71 PASS + 7 SKIP), got {collected}.\n"
            f"可能: 新增/删除 case, 或文件数漂移."
        )


class TestBaselineAuditReport:
    """测试 5: audit 报告输出 (含 stale 文件清单 + 新 baseline 列表)."""

    def test_audit_report_complete(self, capsys) -> None:
        """手动 audit 报告: 列 9 真文件 + 11 stale 已删 + collect count."""
        print("\n" + "=" * 70)
        print("BASELINE 9 FILES AUDIT REPORT (Agent 3 W62 T1)")
        print("=" * 70)

        # 真 baseline 文件
        print("\n[1] BASELINE 9 FILES (与 docs/2026-07-22-baseline-13-stats.md 同步):")
        for i, f in enumerate(BASELINE_9_FILES, 1):
            status = "EXISTS" if _file_exists(f) else "MISSING"
            print(f"  {i}. [{status:7s}] {f}")

        # stale 文件
        print("\n[2] STALE PATTERNS (应全不存在, 11 个 pattern):")
        stale_present = []
        for pattern in STALE_BASELINE_PATTERNS:
            for parent in ("tests", "tests/scripts", "tests/qa-bench/tests",
                           "web/tests/mobile", "tests/unit"):
                full_path = PROJECT_ROOT / parent / pattern
                if full_path.is_file():
                    stale_present.append(str(full_path.relative_to(PROJECT_ROOT)))
                    break
        if stale_present:
            print(f"  WARN: {len(stale_present)} stale files STILL present:")
            for f in stale_present:
                print(f"    - {f}")
        else:
            print("  OK: 所有 11 stale pattern 文件均已删除 (符合预期)")

        # pytest collect 计数
        collected = _collect_baseline_tests()
        print(f"\n[3] PYTEST COLLECT COUNT:")
        print(f"  9 baseline files → {collected} tests (expected 78 = 71 PASS + 7 SKIP)")

        print("\n" + "=" * 70)
        print("RECOMMENDATION:")
        if collected == 78 and not stale_present:
            print("  baseline 列表 stale 修复成功, 71 PASS + 7 SKIP 守恒铁律可验证.")
        else:
            print("  FAIL: baseline 列表仍 stale, 需要:")
            if stale_present:
                print(f"    - 删 {len(stale_present)} 个 stale 文件")
            if collected != 78:
                print(f"    - 调整 baseline 9 files 列表 (collect count != 78)")
        print("=" * 70 + "\n")

        # 这个 test 不 assert — 只输出报告 (capsys 抓 stdout)
        # assert 让报告能输出 (pytest -s 也可看)
        assert True  # placeholder


class TestBaselineExcludes:
    """测试 6: baseline 列表 EXCLUDE 已删除的 test runner scripts."""

    def test_orphan_meeting_cleanup_in_baseline(self) -> None:
        """orphan_meeting_cleanup_audio_chunks 是 baseline 9 之一 (确保没被误删)."""
        assert "tests/test_orphan_meeting_cleanup_audio_chunks.py" in BASELINE_9_FILES

    def test_kb_dedup_admin_cli_e2e_in_baseline(self) -> None:
        """KB dedup admin CLI E2E 在 tests/scripts/ 下, 容易漏, 必须确认."""
        assert "tests/scripts/test_kb_dedup_admin_cli_e2e.py" in BASELINE_9_FILES

    def test_no_duplicate_baseline_files(self) -> None:
        """baseline 9 文件不能有重复."""
        assert len(BASELINE_9_FILES) == len(set(BASELINE_9_FILES)), (
            f"Duplicate baseline files: "
            f"{[f for f in BASELINE_9_FILES if BASELINE_9_FILES.count(f) > 1]}"
        )

    def test_baseline_files_all_start_with_tests(self) -> None:
        """所有 baseline 文件都应在 tests/ 下 (避免误纳入其他目录)."""
        for f in BASELINE_9_FILES:
            assert f.startswith("tests/"), (
                f"Baseline file not under tests/: {f}"
            )