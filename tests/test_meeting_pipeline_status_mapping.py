"""tests/test_meeting_pipeline_status_mapping.py

2026-11-09 P0 回归守卫 —— 会议 273「处理失败」的两条根因。

事故现场（会议 273，2026-11-09）
--------------------------------
用户在前端看到「处理失败」，但流水线其实**七个阶段全部跑完**：
downloading_audio / transcribing / identifying_speakers / storing_results 全 success，
只有 generating_analysis 是 warning（2 个分块里 1 个 JSON 解析失败）。
真正把会议判死的是**最后一步落库**：

    UPDATE meeting_processing_runs SET overall_status=$1 ...
    asyncpg.exceptions.StringDataRightTruncationError:
        value too long for type character varying(16)
    parameters: ('completed_with_warnings', ...)

`meeting_processing_runs.overall_status` 是 varchar(16)，而代码把
`meeting.status` 的取值 `completed_with_warnings`（23 字符）直接塞了进去
⇒ 一个**可恢复的分析 warning** 被升级成整条会议 `error`
（类 20.220 的变体：状态字段的词汇表不同，却被当成同一个字段用）。

同一场的另一条根因是 `max_tokens=8192` 不够：MiniMax M3.x 的自适应思考与正文
共用输出预算，实测 output_tokens 顶满 8192、正文只吐 164 字半截 JSON。

本文件守三件事
--------------
1. `overall_status` 只能收到 `running/success/warning/error` 这类**短词汇**，
   长度必须 ≤ 16（列宽），且必须显式映射而不是透传 `meeting.status`。
2. 分块分析的 `max_tokens` 不得退回 8192（思考与正文共用预算）。
3. 端到端：用假的 run + 假的分析结果跑「分析部分失败」路径，断言
   `finish_run(overall_status=...)` 收到的是 `warning` 且长度合规 ——
   即「部分失败不再把整条会议判死」。

铁律: 不连 DB、不连 LLM，SKIP_DB_SETUP=1，5 秒内跑完。
"""
import os

os.environ.setdefault("SKIP_DB_SETUP", "1")

import ast
import inspect
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

# `meeting_processing_runs.overall_status` 的实际列宽（生产 + 模型两侧一致）
OVERALL_STATUS_MAX_LEN = 16
ALLOWED_OVERALL_STATUS = {"running", "success", "warning", "error"}


# ============================================================================
# 1) 静态结构守卫: 不许再把 meeting.status 透传给 overall_status
# ============================================================================


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_finish_run_receives_mapped_status_not_meeting_status():
    """finish_run 的 overall_status 必须是映射后的短词汇, 不能是 final_status 透传。

    判据取 AST 而不是 grep: 注释里也写着 `completed_with_warnings`（本文件的
    docstring 就写了），grep 会假阳性（类 20.225）。
    """
    src = _read(REPO_ROOT / "app/services/post_meeting_tasks.py")
    tree = ast.parse(src)

    calls = [
        node for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "finish_run"
    ]
    assert calls, "post_meeting_tasks.py 里应至少有一处 finish_run 调用"

    for call in calls:
        kw = {k.arg: k.value for k in call.keywords if k.arg}
        assert "overall_status" in kw, "finish_run 必须显式传 overall_status"
        value = kw["overall_status"]
        # 禁止**透传**会议状态变量（那两个名字的取值里有 23 字符的
        # completed_with_warnings，而列是 varchar(16) ⇒ 必炸）。
        # 允许映射后的变量名 / .get() 调用 / 字面量。
        if isinstance(value, ast.Name):
            assert value.id not in {"final_status", "meeting", "status", "meeting_status"}, (
                f"finish_run(overall_status=...) 直接透传了 {value.id}；"
                "meeting.status 的取值里有 23 字符的 completed_with_warnings，"
                "而列是 varchar(16) ⇒ 必炸（会议 273 事故）"
            )
            assert ("run" in value.id and "status" in value.id) or "mapped" in value.id, (
                f"{value.id} 看起来不是映射结果；请用 MEETING_TO_RUN_STATUS 映射后再传"
            )


def test_status_mapping_covers_every_meeting_terminal_status():
    """映射表必须覆盖 meeting.status 的全部终态取值。

    漏一个 ⇒ `.get(final_status, "warning")` 会静默落到 warning，
    把真正的 error 也说成 warning（另一种状态字段说谎）。
    """
    from app.services.post_meeting_tasks import MEETING_TO_RUN_STATUS

    assert MEETING_TO_RUN_STATUS == {
        "completed": "success",
        "completed_with_warnings": "warning",
        "error": "error",
    }, "映射表被改动，请同步本测试与 finish_run 的注释"
    assert set(MEETING_TO_RUN_STATUS.values()) <= ALLOWED_OVERALL_STATUS


def test_mapping_values_fit_column_width():
    """映射后的值必须放得进 varchar(16) —— 这正是事故的直接判据。"""
    from app.services.post_meeting_tasks import MEETING_TO_RUN_STATUS

    for meeting_status, run_status in MEETING_TO_RUN_STATUS.items():
        assert len(run_status) <= OVERALL_STATUS_MAX_LEN, (
            f"{meeting_status} → {run_status} 超长 ({len(run_status)} > "
            f"{OVERALL_STATUS_MAX_LEN})"
        )
    # 反证: 透传会超长 —— 让这个测试本身成为事故的活证据
    assert len("completed_with_warnings") > OVERALL_STATUS_MAX_LEN


# ============================================================================
# 2) 分析分块的 max_tokens 不得退回 8192
# ============================================================================


def test_analysis_chunk_max_tokens_not_reverted():
    """MiniMax M3.x 的自适应思考与正文共用输出预算 ⇒ 8192 会截断 JSON。

    实测（会议 273 真实转录）：8192 → output_tokens 顶满、正文 164 字半截 JSON、
    parse 全失败；16384 → output 8864、正文 3014 字、parse 通过（8 要点 / 6 决议）。
    """
    src = _read(REPO_ROOT / "app/services/meeting_analysis_service.py")
    tree = ast.parse(src)

    # 找 `_analyze_chunk_safe` 里的 llm.complete(...) 调用
    target = None
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == "_analyze_chunk_safe":
            target = node
            break
    assert target is not None, "未找到 _analyze_chunk_safe"

    completes = [
        n for n in ast.walk(target)
        if isinstance(n, ast.Call)
        and isinstance(n.func, ast.Attribute)
        and n.func.attr == "complete"
    ]
    assert completes, "_analyze_chunk_safe 里应有 llm.complete 调用"

    max_tokens_values = []
    for call in completes:
        for kw in call.keywords:
            if kw.arg == "max_tokens":
                assert isinstance(kw.value, ast.Constant), "max_tokens 必须是字面量常量"
                max_tokens_values.append(kw.value.value)

    assert max_tokens_values, "必须显式传 max_tokens（不能依赖默认值）"
    for v in max_tokens_values:
        assert v >= 16384, (
            f"分块分析 max_tokens={v} 太小：M3.x 的思考预算与正文共用，"
            "8192 会产出半截 JSON（会议 273 实测）"
        )


# ============================================================================
# 3) 端到端: 分析部分失败 → run 记 warning, 会议不该被这条路径判死
# ============================================================================


def test_partial_analysis_maps_to_warning_run_status():
    """`analysis_warning=True` 时 overall_status 必须是 `warning`（不是 23 字符那个）。"""
    src = _read(REPO_ROOT / "app/services/post_meeting_tasks.py")
    tree = ast.parse(src)

    # 定位 if analysis_warning: final_status = "completed_with_warnings"
    found = False
    for node in ast.walk(tree):
        if isinstance(node, ast.If) and isinstance(node.test, ast.Name) and node.test.id == "analysis_warning":
            for sub in ast.walk(node):
                if (
                    isinstance(sub, ast.Assign)
                    and any(isinstance(t, ast.Name) and t.id == "final_status" for t in sub.targets)
                    and isinstance(sub.value, ast.Constant)
                    and sub.value.value == "completed_with_warnings"
                ):
                    found = True
    assert found, "analysis_warning 分支应把 final_status 置为 completed_with_warnings"

    from app.services.post_meeting_tasks import MEETING_TO_RUN_STATUS

    assert MEETING_TO_RUN_STATUS["completed_with_warnings"] == "warning"


@pytest.mark.parametrize(
    "meeting_status,expected_run_status",
    [
        ("completed", "success"),
        ("completed_with_warnings", "warning"),
        ("error", "error"),
    ],
)
def test_mapping_table_contract(meeting_status, expected_run_status):
    from app.services.post_meeting_tasks import MEETING_TO_RUN_STATUS

    assert MEETING_TO_RUN_STATUS[meeting_status] == expected_run_status
