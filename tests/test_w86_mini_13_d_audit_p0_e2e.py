"""W86 mini-11 D — audit P0 summary cartesian + P1 duration + P2 W72 share action + P3 UI dead options + P5 cleanup beat.

派工前提铁律 12 + 派工 v4 铁律 3 + 派工 v6 §1.2: 5 修复全部 3 路搜证 + 真验证

5 子测试:
1. P0 summary by_action 不再有笛卡尔积 (子查询内部 group_by)
2. P0 summary by_status 同理
3. P1 duration_ms 真实值 (rate_limit 中间件记录 start, 响应后算 wall-clock)
4. P2 VALID_ACTIONS 含 W72 share_created/downloaded/revoked 3 个
5. P3 audit_service.cleanup_old_logs 已注册 Celery beat
"""
from __future__ import annotations

import ast
import inspect
import os
import re

os.environ.setdefault("SKIP_DB_SETUP", "1")


def _get_function_source(module, fn_name: str) -> str:
    """从模块源码中精准抽出指定函数的完整源代码 (含缩进 + decorator + body).

    用 ast.iter_child_nodes 走模块顶层节点 (避免 ast.get_source_segment 的 lineno 问题).
    """
    source = inspect.getsource(module)
    tree = ast.parse(source)
    # admin_audit.py 用 @router.get 装饰器, 顶层是 AsyncFunctionDef
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == fn_name:
            lines = source.splitlines(keepends=True)
            start = node.lineno - 1  # 0-indexed
            end = node.end_lineno  # inclusive
            return "".join(lines[start:end])
    return ""


# === P0: summary 笛卡尔积修复验证 ===

def test_p0_summary_no_cartesian_product_in_admin_audit():
    """P0: admin_audit.py audit_summary 不能再有 select_from(subquery) + group_by 外层表"""
    from app.api.v1 import admin_audit

    fn_body = _get_function_source(admin_audit, "audit_summary")
    assert fn_body, "audit_summary 函数体未找到"

    # 修复后, audit_summary 内不应再有 select_from(base_q.subquery()) 这种
    # 隐式 CROSS JOIN 模式 + group_by(AuditLog.action)
    # 正确模式: 直接 select(AuditLog.action, func.count(...)) + group_by(AuditLog.action)
    cross_join_pattern = re.search(  # noqa: F821 (re imported below)
        r"select_from\(base_q\.subquery\(\)\)\s*\.\s*group_by\(AuditLog\.action\)", fn_body
    )
    assert cross_join_pattern is None, (
        "P0 bug 仍在: select_from(base_q.subquery()) + group_by(AuditLog.action) "
        "会产生隐式 CROSS JOIN, 数字 × 57,130 倍"
    )

    # 修复后应该有新注释提及 W86 mini-11 D fix
    assert "W86 mini-11 D" in fn_body or "mini-11 D" in fn_body, (
        "admin_audit.py audit_summary 缺 W86 mini-11 D fix 标识"
    )


def test_p0_summary_by_action_no_implicit_cross_join_in_sql():
    """P0: SQL 字符串层面不能再有跨子查询引用 AuditLog.action 的隐式 CROSS JOIN

    修复后 audit_summary 用直接 query + group_by, 不再 select_from(subquery)
    """
    from app.api.v1 import admin_audit

    fn_body = _get_function_source(admin_audit, "audit_summary")
    assert fn_body, "audit_summary 函数体未找到"

    # 修复后, audit_summary 函数体内 select_from(...) 只剩 1 处真实代码 (total 计数 line 82)
    # 老 bug 有 3 处 (total + by_action + by_status) 全用 subquery
    # 注释里有 1 处提及老模式, 合计字符串里 2 处出现 (1 真代码 + 1 注释)
    # 验证: 真实 select_from( 调用只剩 1 处 (行 82)
    # 用正则排除注释行里的 select_from(
    real_select_from = 0
    for line in fn_body.splitlines():
        stripped = line.strip()
        if stripped.startswith("#"):
            continue
        if "select_from(" in line:
            real_select_from += 1
    assert real_select_from == 1, (
        f"P0 修复后 audit_summary 函数体真实代码 select_from 应只剩 1 处 (total), "
        f"实际 {real_select_from} 处"
    )


# === P1: duration_ms 真实值 ===

def test_p1_duration_ms_no_longer_hardcoded_zero():
    """P1: rate_limit.py 不能再硬编码 duration_ms=0

    修复后应在中间件起点记录 _rl_start_ts, 响应后算 (time.time() - _rl_start_ts) * 1000
    """
    from app.core import rate_limit

    source = inspect.getsource(rate_limit)

    # 老 bug: duration_ms=0, # rate_limit 阶段拿不到原始 start, 简化 0
    assert "duration_ms=0,  # rate_limit 阶段拿不到原始 start" not in source, (
        "P1 bug 仍在: rate_limit.py 硬编码 duration_ms=0"
    )

    # 修复后: 应有 _rl_start_ts = time.time() 记录 + _duration_ms = int((time.time() - _rl_start_ts) * 1000)
    assert "_rl_start_ts" in source, "P1 修复后应有 _rl_start_ts 起点 wall-clock 记录"
    assert "_duration_ms" in source or "duration_ms = int((time.time() - _rl_start_ts)" in source, (
        "P1 修复后应有 _duration_ms 真实值计算"
    )


# === P2: W72 share 3 个 action ===

def test_p2_valid_actions_contains_w72_share_actions():
    """P2: audit_service.VALID_ACTIONS 必须含 W72 第 2 批 B-1 差量的 3 个 share action

    老 bug: VALID_ACTIONS 不含 share_created/downloaded/revoked
    → audit_middleware 分类后写入被 fallback 'read' + warning → DB 0 行
    """
    from app.services.audit_service import VALID_ACTIONS

    assert "share_created" in VALID_ACTIONS, (
        "P2 修复后 VALID_ACTIONS 必须含 'share_created' (W72 第 2 批 B-1)"
    )
    assert "share_downloaded" in VALID_ACTIONS, (
        "P2 修复后 VALID_ACTIONS 必须含 'share_downloaded' (W72 第 2 批 B-1)"
    )
    assert "share_revoked" in VALID_ACTIONS, (
        "P2 修复后 VALID_ACTIONS 必须含 'share_revoked' (W72 第 2 批 B-1)"
    )


# === P5: cleanup_old_logs Celery beat 注册 ===

def test_p5_cleanup_old_logs_registered_in_celery_beat():
    """P5: celery.py beat_schedule 必须注册 audit_service.cleanup_old_logs"""
    from app.core import celery

    source = inspect.getsource(celery)

    # 修复后 beat_schedule 应有 cleanup-old-audit-logs-* 项
    assert "audit_service.cleanup_old_logs" in source, (
        "P5 修复后 celery.py 必须注册 audit_service.cleanup_old_logs Celery task"
    )
    assert "cleanup-old-audit-logs" in source, (
        "P5 修复后 celery.py 必须含 cleanup-old-audit-logs beat key"
    )

    # 也要在 imports 列表里
    assert '"app.services.audit_service"' in source or "'app.services.audit_service'" in source, (
        "P5 修复后 celery.py imports 必须含 'app.services.audit_service' "
        "(否则 worker 启动时不会 import 该模块)"
    )


# === P3: AuditLogView UI 死选项 (仅 source check) ===

def test_p3_audit_log_view_no_hardcoded_common_actions():
    """P3: AuditLogView.vue 不应再硬编码 18 个 COMMON_ACTIONS

    老 bug: COMMON_ACTIONS 写死 18 个, 实际只有 6 种, 12 个是死选项
    修复后用 availableActions 从 summary.by_action 动态派生
    """
    from pathlib import Path

    view_path = Path("web/src/views/admin/AuditLogView.vue")
    assert view_path.exists(), "AuditLogView.vue missing"
    source = view_path.read_text(encoding="utf-8")

    # 修复后: COMMON_ACTIONS 不应再存在
    assert "COMMON_ACTIONS" not in source, (
        "P3 修复后 AuditLogView.vue 不应再有 COMMON_ACTIONS 硬编码"
    )

    # 修复后: 应有 availableActions computed 从 summary 派生
    assert "availableActions" in source, (
        "P3 修复后 AuditLogView.vue 应有 availableActions computed 从 summary 派生"
    )

    # 模板 el-option 应绑 availableActions (而非 COMMON_ACTIONS)
    assert "v-for=\"a in availableActions\"" in source or "v-for='a in availableActions'" in source, (
        "P3 修复后 template 应绑 availableActions"
    )