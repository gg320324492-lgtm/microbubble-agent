"""2026-07-27 W71 B-3 — qa_bench_tasks Celery 单元测试

覆盖 Celery beat 7 天 auto_intake_rollback task: 注册 / beat schedule / 7 天前 rollback / 7 天内不 rollback
"""
import json
import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import patch, MagicMock

from app.core.celery import celery_app
from app.services.qa_bench_tasks import auto_intake_rollback_task


class TestRollbackCeleryTask:
    def test_task_默认_7天(self):
        """不传 retention_days → 默认 7 天"""

        with patch("app.services.qa_bench_tasks.create_celery_engine_and_session") as mock_factory:
            mock_engine = MagicMock()
            mock_factory.return_value = (mock_engine, MagicMock())

            with patch("app.services.qa_bench_tasks.asyncio.run") as mock_run:
                mock_run.return_value = []
                result = auto_intake_rollback_task()
                assert result["status"] == "ok"
                assert result["rolled_back"] == 0
                assert result["retention_days"] == 7

    def test_task_自定义_retention_days(self):
        """传 retention_days=14 → 默认 14 天"""

        with patch("app.services.qa_bench_tasks.create_celery_engine_and_session") as mock_factory:
            mock_engine = MagicMock()
            mock_factory.return_value = (mock_engine, MagicMock())

            with patch("app.services.qa_bench_tasks.asyncio.run") as mock_run:
                mock_run.return_value = [(42, "test entry", datetime.now(timezone.utc))]
                result = auto_intake_rollback_task(retention_days=14)
                assert result["status"] == "ok"
                assert result["rolled_back"] == 1
                assert result["retention_days"] == 14

    def test_task_异常_不抛_返回_error(self):
        """DB 错误 → task 返回 {status: error}，不抛 Celery 重试链"""
        with patch("app.services.qa_bench_tasks.create_celery_engine_and_session") as mock_factory:
            mock_engine = MagicMock()
            mock_factory.return_value = (mock_engine, MagicMock())

            with patch("app.services.qa_bench_tasks.asyncio.run") as mock_run:
                mock_run.side_effect = Exception("DB down")
                result = auto_intake_rollback_task()
                assert result["status"] == "error"
                assert "DB down" in result["error"]
                assert result["rolled_back"] == 0

    def test_beat_schedule_包含_qa_bench_rollback(self):
        """Celery beat schedule 必须含 'qa-bench-auto-intake-rollback-daily' entry"""
        beat = celery_app.conf.beat_schedule
        assert "qa-bench-auto-intake-rollback-daily" in beat, \
            f"beat_schedule keys: {list(beat.keys())}"
        entry = beat["qa-bench-auto-intake-rollback-daily"]
        assert entry["task"] == "app.services.qa_bench_tasks.auto_intake_rollback_task"
        assert entry["schedule"] == 24 * 3600.0

    def test_task_注册成功(self):
        """Celery app.tasks 必须含 auto_intake_rollback_task"""
        from app.services.qa_bench_tasks import auto_intake_rollback_task
        assert auto_intake_rollback_task.name == "app.services.qa_bench_tasks.auto_intake_rollback_task"

    def test_task_软删除而非物理删除(self):
        """必须用 `deleted_at` 软删除, 不能物理 DELETE

        ⚠️ 2026-10-31 订正: 原断言是 `"is_active" in source` —— 但 **Knowledge 模型
        根本没有 is_active 列** (软删除字段是 `deleted_at`) ⇒ 旧断言等于把 bug 焊死,
        而且旧用例整体 mock 掉 `asyncio.run` ⇒ SQL 从未真跑 ⇒ 一直绿。
        """
        import ast
        import inspect
        from app.services.qa_bench_tasks import auto_intake_rollback_task
        source = inspect.getsource(auto_intake_rollback_task)
        # 禁止物理 DELETE FROM knowledge (应软删除 deleted_at)
        assert "DELETE FROM knowledge" not in source, \
            "rollback 必须软删除 (deleted_at), 禁止物理 DELETE FROM knowledge"

        used = set()
        for node in ast.walk(ast.parse(source)):
            if isinstance(node, ast.Attribute):
                used.add(node.attr)
            elif isinstance(node, ast.keyword) and node.arg:
                used.add(node.arg)
            elif isinstance(node, ast.Dict):
                for key in node.keys:
                    if isinstance(key, ast.Constant) and isinstance(key.value, str):
                        used.add(key.value)
        assert "deleted_at" in used, \
            f"代码里必须真的写到 deleted_at (用到的字段: {sorted(used)})"

    def test_task_不再引用不存在的_is_active_列(self):
        """Knowledge 没有 is_active 列 —— 写它会在 SQL 编译期直接炸

        ⚠️ 判据用 **AST**, 不用 `grep`/源码字符串: docstring 里**提到** `is_active`
        (说明为什么不用它) 不等于**用到**它 —— 类 20.225 的同型坑。
        """
        import ast
        import inspect
        from app.services.qa_bench_tasks import auto_intake_rollback_task
        from app.models.knowledge import Knowledge

        assert not hasattr(Knowledge, "is_active"), \
            "前提变了: 若 Knowledge 将来真有 is_active 列, 这里的断言需要重新评估"

        source = inspect.getsource(auto_intake_rollback_task)
        tree = ast.parse(source)
        used = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Attribute):
                used.add(node.attr)
            elif isinstance(node, ast.keyword) and node.arg:
                used.add(node.arg)
            elif isinstance(node, ast.Dict):
                for key in node.keys:
                    if isinstance(key, ast.Constant) and isinstance(key.value, str):
                        used.add(key.value)
        assert "is_active" not in used, \
            f"代码里真的用了不存在的 is_active 列 (用到的字段: {sorted(used)})"

    def test_保留期守卫_非默认值走统一入口(self):
        """retention_days 非默认值必须过 confirm_retention_param_auto (PR6-P9 事故防线)"""
        import inspect
        from app.services.qa_bench_tasks import auto_intake_rollback_task
        source = inspect.getsource(auto_intake_rollback_task)
        assert "confirm_retention_param_auto" in source, \
            "必须用仓库统一的保留期守卫, 别裸传 retention_days"


# --------------------------------------------------------------------------------------
# 2026-10-31 回归守卫 —— tz-aware / naive 混用
#
# 事故: 本任务**每天都在失败** (beat 24h 一次), 日志里是
#   DataError: invalid input for query argument $2:
#   datetime.datetime(2026, 10, 23, 17, 35, ... tzinfo=timezone.utc)
#   (can't subtract offset-naive and offset-aware datetimes)
# 根因: `knowledge.created_at` 是 `TIMESTAMP WITHOUT TIME ZONE` (naive),
#       而 cutoff 传的是 `datetime.now(timezone.utc)` (tz-aware) ⇒ asyncpg 拒绝。
#
# ⛔ 为什么以前 6 个用例全是绿的: 它们**整体 mock 掉了 `asyncio.run`** ⇒
#    `_run()` 从未执行 ⇒ SQL 从未真跑过 ⇒ 类型错误永远碰不到。
#    ⇒ 下面这组用例**不 mock asyncio.run**, 让查询真的被构造出来并检查绑定参数。
# --------------------------------------------------------------------------------------


class _FakeResult:
    def __init__(self, rows):
        self._rows = rows

    def fetchall(self):
        return self._rows


class _FakeSession:
    """捕获真正构造出来的 SQL 语句 (而不是把执行也 mock 掉)"""

    def __init__(self, rows=()):
        self.statements = []
        self._rows = list(rows)

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    async def execute(self, statement):
        self.statements.append(statement)
        return _FakeResult(self._rows)

    async def commit(self):
        return None


class _FakeEngine:
    async def dispose(self):
        return None


def _bound_datetimes(statement):
    """把语句里所有绑定参数里的 datetime 挖出来"""
    out = []
    for value in statement.compile().params.values():
        if isinstance(value, datetime):
            out.append(value)
    return out


class TestTimezoneNaiveCutoff:
    """cutoff 必须是 naive UTC —— 不能是 tz-aware, 也不能是本地时间"""

    def test_helper_返回_naive(self):
        from app.services.qa_bench_tasks import utc_cutoff_naive
        cutoff = utc_cutoff_naive(7)
        assert cutoff.tzinfo is None, \
            "cutoff 必须 naive (列是 TIMESTAMP WITHOUT TIME ZONE), 收到 tz-aware 会让 asyncpg 报 DataError"

    def test_helper_是_UTC_不是本地时间(self):
        """防回归: 有人改成 `datetime.now()` (本地) 时这个用例会红"""
        from app.services.qa_bench_tasks import utc_cutoff_naive
        now_utc = datetime.now(timezone.utc)
        cutoff = utc_cutoff_naive(7)
        expected = (now_utc - timedelta(days=7)).replace(tzinfo=None)
        assert abs(cutoff - expected) < timedelta(minutes=1), \
            "cutoff 必须按 UTC 减, 不是按本地时间减"

        local_offset = datetime.now() - now_utc.replace(tzinfo=None)
        if abs(local_offset) > timedelta(minutes=1):
            # 本机时区不是 UTC ⇒ 本地时间减出来的值必须与 UTC 减出来的不一样
            local_based = datetime.now() - timedelta(days=7)
            assert abs(cutoff - local_based) > timedelta(hours=1), \
                "cutoff 与本地时间基准几乎相同 ⇒ 疑似用了 datetime.now() (本地) 而不是 UTC"

    def test_查询绑定参数里没有_tz_aware_datetime(self):
        """⭐ 真正会炸的那个守卫: 让 SQL 真被构造出来, 检查绑定的 datetime 是不是 naive

        这个用例在修复前会红 (bound param 是 tz-aware) ⇒ 就是它没能抓住事故的原因。
        """
        import inspect
        from app.services import qa_bench_tasks

        # 断言 task 源码里不再出现裸的 tz-aware cutoff
        source = inspect.getsource(qa_bench_tasks.auto_intake_rollback_task)
        assert "datetime.now(timezone.utc) - timedelta" not in source, \
            "cutoff 必须走 utc_cutoff_naive() (naive UTC), 不能直接用 tz-aware datetime"

        sess = _FakeSession()
        engine = _FakeEngine()

        with patch.object(qa_bench_tasks, "create_celery_engine_and_session",
                          return_value=(engine, lambda: sess)):
            result = qa_bench_tasks.auto_intake_rollback_task(retention_days=7)

        assert result["status"] == "ok", f"任务不该失败: {result}"
        assert sess.statements, "应当真的执行过查询 (不能把 execute 也 mock 掉)"

        checked = 0
        for statement in sess.statements:
            for value in _bound_datetimes(statement):
                checked += 1
                assert value.tzinfo is None, \
                    f"绑定了 tz-aware datetime 到 TIMESTAMP WITHOUT TIME ZONE 列: {value!r}"
        assert checked >= 1, "应当至少检查到一个绑定的时间参数"


class TestRollbackCountAggregation:
    """`GET /knowledge/auto-intake-summary` 的 rollback_count 聚合

    ⚠️ 2026-10-31 事故: 报告里的 timestamp 是 **tz-aware** ISO, 而聚合代码拿它跟
    naive 的 `datetime.now()` 相减 ⇒ TypeError ⇒ 被 `except Exception: pass` 吞掉
    ⇒ **rollback_count 恒为 0** (状态字段在说谎, 类 20.220)。
    """

    @staticmethod
    def _write_report(directory, name, payload):
        path = directory / name
        path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        return path

    def test_tz_aware_报告被正确计入(self, tmp_path):
        """⭐ 修复前会抛 TypeError ⇒ 计数恒为 0"""
        from app.api.v1.knowledge import sum_rollback_counts
        now = datetime.now(timezone.utc)
        self._write_report(tmp_path, "auto_intake_rollback_20261031_000000.json", {
            "timestamp": now.isoformat(),          # tz-aware —— 真实 writer 的格式
            "deleted_count": 83,
            "retention_days": 7,
        })
        assert sum_rollback_counts(tmp_path) == 83

    def test_naive_报告也计入(self, tmp_path):
        from app.api.v1.knowledge import sum_rollback_counts
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        self._write_report(tmp_path, "auto_intake_rollback_20261031_000001.json", {
            "timestamp": now.isoformat(),          # naive UTC
            "deleted_count": 5,
        })
        assert sum_rollback_counts(tmp_path) == 5

    def test_窗口外的报告不计入(self, tmp_path):
        from app.api.v1.knowledge import sum_rollback_counts
        old = datetime.now(timezone.utc) - timedelta(days=30)
        self._write_report(tmp_path, "auto_intake_rollback_20260901_000000.json", {
            "timestamp": old.isoformat(), "deleted_count": 999,
        })
        assert sum_rollback_counts(tmp_path) == 0

    def test_坏报告被跳过_不影响其它(self, tmp_path):
        from app.api.v1.knowledge import sum_rollback_counts
        (tmp_path / "auto_intake_rollback_20261031_000000.json").write_text(
            "{ not json", encoding="utf-8")
        now = datetime.now(timezone.utc)
        self._write_report(tmp_path, "auto_intake_rollback_20261031_000001.json", {
            "timestamp": now.isoformat(), "deleted_count": 7,
        })
        assert sum_rollback_counts(tmp_path) == 7

    def test_目录不存在返回0(self, tmp_path):
        from app.api.v1.knowledge import sum_rollback_counts
        assert sum_rollback_counts(tmp_path / "nope") == 0
