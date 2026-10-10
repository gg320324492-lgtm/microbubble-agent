"""tests/test_orphan_meeting_cleanup_audio_chunks.py

2026-07-16 扩展的孤儿会议清理单测

覆盖 (app/services/orphan_meeting_cleanup.py):
- _scan_and_cleanup() 选择 30min 窗口外的孤儿 meeting (status='recording')
- error_reason 拼接 UA 片段 (line 80-84)
- 上传状态 cleanup → MinIO chunks 清理 + WS 通知
- 半成品 (last_chunk_index >= 0 但用户从未 stop) → 清理
- 24h 窗口外 → 不清理

策略: chunked_upload_service / progress_service 用 MagicMock 注入到 sys.modules,
redis.asyncio 用 autouse function-scope fixture 隔离 + 测试结束 restore —
避免污染其它测试文件 (e.g. test_meeting_transcript_buffer 用真 redis.asyncio).
Meeting 用真的 ORM (SKIP 模式下也能 import, 让 select(Meeting) 能正常构造 SQL).
create_celery_engine_and_session 通过 patch 注入.

铁律: SKIP_DB_SETUP=1 mock, 不依赖数据库, 5s 内跑完

⚠️ 2026-07-20 修复 (W8 pre-existing bug): 模块顶层用 sys.modules.setdefault 注入
redis.asyncio stub 会永久污染 sys.modules — 反序跑 (orphan 在前) 时, 后跑测试
(如 test_meeting_transcript_buffer) `import redis.asyncio` 拿到 MagicMock, 报
`TypeError: object MagicMock can't be used in 'await' expression`.
修法: 用 function-scope autouse fixture + 显式 save/restore sys.modules.

⚠️⚠️ 2026-10-06 订正: 上面这段 "修复" **并未真正生效**。它把注入从模块顶层搬到了
function-scope fixture, 解决了"永久污染"但引入了新问题: 只 monkeypatch
sys.modules 而没绑父包属性, 而生产代码的 `import redis.asyncio as aioredis`
走父包属性解析、**不查 sys.modules** ⇒ stub 始终没被用上, 本文件一直连的是真
Redis。后果: 本文件单跑 7 failed, 被 test_meeting_transcript_buffer.py 排在前面
时 11 passed —— 通过与否纯看 import 顺序。现已在 fixture 里同时绑父包属性,
详见 fixture 内注释。
"""
import os
os.environ.setdefault("SKIP_DB_SETUP", "1")

import sys
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent))


# ============================================================================
# Module-level stubs: chunked_upload_service + progress_service
# (这些 mock 只挂属性, 不替换整个 sys.modules entry, 不污染其它测试)
# ============================================================================
_chunked_stub = MagicMock()
_chunked_stub.delete_chunks = AsyncMock(return_value=0)
_chunked_stub_module = MagicMock()
_chunked_stub_module.chunked_upload_service = _chunked_stub

_update_progress_stub = AsyncMock(return_value=None)
_progress_stub_module = MagicMock()
_progress_stub_module.update_progress = _update_progress_stub
_progress_stub_module.ProgressStage = MagicMock()


@pytest.fixture(autouse=True)
def _stub_function_level_imports(monkeypatch):
    """function-scope autouse: 隔离 redis.asyncio stub + 注入其它 module-level mocks.

    orphan_meeting_cleanup.py 在 _scan_and_cleanup() 函数内
    `import redis.asyncio as aioredis`, 所以必须让 sys.modules["redis.asyncio"]
    在测试期间指向 MagicMock. 但模块顶层不能 setdefault (会污染其它测试文件).

    修法: 用 monkeypatch.setitem 在 fixture 生命周期内替换, fixture exit 自动恢复.
    """
    # chunked_upload_service + progress_service: 注入到 sys.modules
    # (生产代码函数内 from-import 会拿到这些 stub)
    monkeypatch.setitem(sys.modules, "app.services.chunked_upload_service", _chunked_stub_module)
    monkeypatch.setitem(sys.modules, "app.services.progress_service", _progress_stub_module)

    # redis.asyncio: 整个模块替换为 MagicMock, 让 aioredis.from_url(...) 返可控对象。
    #
    # ⚠️ 2026-10-06 修复: 必须**同时**写 sys.modules 和父包属性, 只写前者无效。
    #   orphan_meeting_cleanup.py:62 写的是 `import redis.asyncio as aioredis`,
    #   该形式对 dotted name 走的是**父包属性查找** (redis.__dict__["asyncio"]),
    #   不查 sys.modules —— 实测:
    #       sys.modules["redis.asyncio"] = stub; import redis.asyncio as r
    #       => r is stub 为 False (拿到的是真模块)
    #   所以 2026-07-20 那两条"已修 sys.modules 污染"的注释是假的: 旧 fixture
    #   从未真正生效过, 本文件一直连的是真 Redis。这解释了为什么单跑 7 failed
    #   而全套跑 11 passed —— 通过与否取决于**别的文件有没有先 import 真
    #   redis.asyncio**, 纯靠 import 顺序的偶然绿。
    #   现在两边都绑, 心跳守卫被确定性触发, 不再依赖文件顺序 / 环境里有没有真 Redis。
    #
    # exists=0 = 心跳不存在 = 前端已消失 = 真孤儿 = 该清理。
    # 缺这一行时 is_recording_alive 拿到的是 MagicMock 的 exists, await 抛 TypeError,
    # 被 recording_heartbeat.py:100 的 except 吞掉并**保守判定为存活** (09-14 事故后
    # 刻意设计: 宁可漏清一个孤儿, 也不误杀一场正在进行的真实会议) —— 于是每个
    # orphan 都被 skipped, 被断言的删除路径从未执行。
    _redis_client_stub = MagicMock()
    _redis_client_stub.aclose = AsyncMock(return_value=None)
    _redis_client_stub.exists = AsyncMock(return_value=0)
    _redis_asyncio_stub = MagicMock()
    _redis_asyncio_stub.from_url = MagicMock(return_value=_redis_client_stub)
    monkeypatch.setitem(sys.modules, "redis.asyncio", _redis_asyncio_stub)
    # 父包属性: 让 `import redis.asyncio as aioredis` 真正解析到上面的 stub。
    # raising=False: 首次 import 时 redis 包上可能还没有 asyncio 属性。
    import redis as _redis_pkg

    monkeypatch.setattr(_redis_pkg, "asyncio", _redis_asyncio_stub, raising=False)

    yield

    # monkeypatch 自动在 function 结束时 setitem/setattr 回去, 无需手动 restore


def _make_orphan_meeting(
    meeting_id: int = 301,
    created_at: datetime = None,
    last_chunk_index: int = 3,
    total_chunks: int = 4,
    user_agent: str = "Mozilla/5.0 Test UA",
):
    m = MagicMock()
    m.id = meeting_id
    m.created_by = 7
    m.status = "recording"
    m.recording_started_at = created_at or (datetime.utcnow() - timedelta(minutes=45))
    m.last_chunk_index = last_chunk_index
    m.total_chunks = total_chunks
    m.user_agent = user_agent
    m.error_reason = None
    # 2026-10-10 CI 全红修复 (与 pyarrow 无关的独立存量 bug):
    # 本 helper 建的是 MagicMock, 未显式赋值的属性会**自动生成一个真值 MagicMock**,
    # 于是服务里 2026-10-08 P0-4 新增的判据
    #     presence_recent = bool(m.recording_presence_at and (threshold <= m.recording_presence_at))
    # 走到 `threshold <= MagicMock()` 抛 TypeError, 被扫描循环的
    # `except Exception as e: errors.append(...)` 吞掉。
    # 后果: 第 121 行 `m.status = "error"` 已执行, 第 153 行 `m.error_reason = ...`
    # 永远到不了 → 7 个用例报 "TypeError: argument of type 'NoneType' is not iterable"
    # (在 assert "..." in orphan.error_reason 处), 且 status 断言反而先过了, 极具误导性。
    # 该列在 app/models/meeting.py:60 是 nullable=True, 真实 DB 里"没有 presence 信号"
    # 就是 NULL → 这里必须显式赋 None, mock 才忠实于真实行。
    m.recording_presence_at = None
    return m


def _setup_session(orphan_meetings, filter_meetings=False):
    """构造 mock db session + engine, 使 _scan_and_cleanup 能跑通.

    filter_meetings=True: 模拟真实 select(Meeting).where(...) 过滤 — 返空 list
    (代表 meeting 不在 30min 窗口内或不是 recording 状态).
    filter_meetings=False: 返 orphan_meetings (代表 meeting 命中 SELECT 条件).
    """
    if filter_meetings:
        meetings_to_return = []
    else:
        meetings_to_return = orphan_meetings

    scalars = MagicMock()
    scalars.all = MagicMock(return_value=meetings_to_return)
    execute_result = MagicMock()
    execute_result.scalars = MagicMock(return_value=scalars)

    session = MagicMock()
    session.execute = AsyncMock(return_value=execute_result)
    session.commit = AsyncMock(return_value=None)

    session_factory = MagicMock()
    session_factory.return_value.__aenter__ = AsyncMock(return_value=session)
    session_factory.return_value.__aexit__ = AsyncMock(return_value=None)

    engine = MagicMock()
    engine.dispose = AsyncMock(return_value=None)

    create_engine_session = MagicMock(return_value=(engine, session_factory))
    return create_engine_session, session


class TestOrphanMeetingCleanup:
    """孤儿会议清理 (app/services/orphan_meeting_cleanup.py)."""

    async def test_window_under_threshold_no_cleanup(self):
        """SKIP_DB_SETUP=1 mock 模式下, db.execute 返 [] 模拟"无 orphan meeting"
        (等价于 meeting.recording_started_at 不在 30min 窗口内 → select 过滤掉).

        这里关键不是验时间窗口选择 (需要真 SQL), 而是验证:
        - select 返空 list 时, 状态不被改
        - commit 不被调
        """
        from app.services.orphan_meeting_cleanup import _scan_and_cleanup

        # 不创建任何 orphan, 模拟 SQL 已过滤
        _chunked_stub.delete_chunks.reset_mock()
        create_engine_session, session = _setup_session([], filter_meetings=True)

        with patch(
            "app.services.orphan_meeting_cleanup.create_celery_engine_and_session",
            create_engine_session,
        ):
            result = await _scan_and_cleanup()

        assert result["cleaned"] == []
        assert result["count"] == 0
        assert result["errors"] == []
        # 没 commit (无状态变更)
        session.commit.assert_not_awaited()
        # 没触发 chunked 清理
        _chunked_stub.delete_chunks.assert_not_awaited()

    async def test_window_over_threshold_marks_as_error(self):
        """录音 45min (超 30min 阈值) → 标 status='error', 写 error_reason."""
        from app.services.orphan_meeting_cleanup import _scan_and_cleanup

        orphan = _make_orphan_meeting(
            meeting_id=301,
            created_at=datetime.utcnow() - timedelta(minutes=45),
            last_chunk_index=5,
            total_chunks=6,
            user_agent="Mozilla/5.0 (Macintosh; Chrome/120) Test",
        )
        _chunked_stub.delete_chunks.reset_mock()
        _chunked_stub.delete_chunks.return_value = 6
        _update_progress_stub.reset_mock()
        create_engine_session, _ = _setup_session([orphan])

        with patch(
            "app.services.orphan_meeting_cleanup.create_celery_engine_and_session",
            create_engine_session,
        ):
            result = await _scan_and_cleanup()

        assert orphan.status == "error"
        assert "录音超过 30min 未 stop" in orphan.error_reason
        assert "last_chunk_index=5" in orphan.error_reason
        assert "total_chunks=6" in orphan.error_reason
        assert "[UA:" in orphan.error_reason
        # 2026-10-10: 原断言是 delete_chunks.assert_awaited_once_with(301), 但那是
        # **2026-10-08 P0-4 之前**的契约。会议 255 孤儿清理误删了用户音频后, 有意改成
        # 「有分片就不删 MinIO」, 给用户留补传 / POST /reprocess 的补救机会
        # (见 app/services/orphan_meeting_cleanup.py 的 preserve_chunks 分支)。
        # 本用例 last_chunk_index=5 → has_chunks=True → preserve_chunks=True,
        # 因此 delete_chunks **正确地不被调用**。原断言与新契约直接矛盾, 必须反过来断言。
        assert "chunks_preserved=6" in orphan.error_reason
        _chunked_stub.delete_chunks.assert_not_awaited()
        _update_progress_stub.assert_awaited_once()
        assert 301 in result["cleaned"]
        assert result["count"] == 1

    async def test_half_finished_orphan_cleaned_up(self):
        """关键修复 (2026-07-16 扩展): 录了 30 分钟突然刷新离开 (last_chunk_index >= 0) → 也被清理."""
        from app.services.orphan_meeting_cleanup import _scan_and_cleanup

        half_finished = _make_orphan_meeting(
            meeting_id=302,
            created_at=datetime.utcnow() - timedelta(minutes=35),
            last_chunk_index=10,
            total_chunks=11,
        )
        _chunked_stub.delete_chunks.reset_mock()
        _chunked_stub.delete_chunks.return_value = 11
        create_engine_session, _ = _setup_session([half_finished])

        with patch(
            "app.services.orphan_meeting_cleanup.create_celery_engine_and_session",
            create_engine_session,
        ):
            result = await _scan_and_cleanup()

        assert half_finished.status == "error"
        assert "last_chunk_index=10" in half_finished.error_reason
        assert "total_chunks=11" in half_finished.error_reason
        assert 302 in result["cleaned"]

    async def test_no_chunks_orphan_cleaned_up(self):
        """半成品孤儿: last_chunk_index = -1 (录音 30min 但从未收到 chunk) → 也被清理."""
        from app.services.orphan_meeting_cleanup import _scan_and_cleanup

        no_chunks = _make_orphan_meeting(
            meeting_id=303,
            created_at=datetime.utcnow() - timedelta(minutes=40),
            last_chunk_index=-1,
            total_chunks=None,
        )
        _chunked_stub.delete_chunks.reset_mock()
        _chunked_stub.delete_chunks.return_value = 0
        create_engine_session, _ = _setup_session([no_chunks])

        with patch(
            "app.services.orphan_meeting_cleanup.create_celery_engine_and_session",
            create_engine_session,
        ):
            result = await _scan_and_cleanup()

        assert no_chunks.status == "error"
        assert "last_chunk_index=-1" in no_chunks.error_reason
        assert 303 in result["cleaned"]

    async def test_threshold_uses_settings_constant(self):
        """防御: 阈值应来自 settings.ORPHAN_MEETING_TIMEOUT_MINUTES (单点配置)."""
        from app.config import settings

        assert settings.ORPHAN_MEETING_TIMEOUT_MINUTES == 30

    async def test_threshold_boundary_31min_just_over(self):
        """31 分钟 (刚超 30min 阈值) → 清理."""
        from app.services.orphan_meeting_cleanup import _scan_and_cleanup

        boundary = _make_orphan_meeting(
            meeting_id=304,
            created_at=datetime.utcnow() - timedelta(minutes=31),
        )
        _chunked_stub.delete_chunks.reset_mock()
        create_engine_session, _ = _setup_session([boundary])

        with patch(
            "app.services.orphan_meeting_cleanup.create_celery_engine_and_session",
            create_engine_session,
        ):
            result = await _scan_and_cleanup()

        assert boundary.status == "error"
        assert 304 in result["cleaned"]

    async def test_error_reason_contains_ua_snippet(self):
        """P0 (2026-07-16): error_reason 拼 UA 片段便于事后排查 HarmonyOS ArkWeb."""
        from app.services.orphan_meeting_cleanup import _scan_and_cleanup

        ua = "Mozilla/5.0 (Linux; Android 12; HarmonyOS; ArkWeb/45.10.0)"
        orphan = _make_orphan_meeting(
            meeting_id=305,
            created_at=datetime.utcnow() - timedelta(minutes=45),
            user_agent=ua,
        )
        _chunked_stub.delete_chunks.reset_mock()
        create_engine_session, _ = _setup_session([orphan])

        with patch(
            "app.services.orphan_meeting_cleanup.create_celery_engine_and_session",
            create_engine_session,
        ):
            await _scan_and_cleanup()

        # UA 截断 80 字符
        assert f"[UA: {ua[:80]}]" in orphan.error_reason

    async def test_error_reason_for_null_ua_says_unknown(self):
        """user_agent=None → 'unknown' (line 79 fallback)."""
        from app.services.orphan_meeting_cleanup import _scan_and_cleanup

        orphan = _make_orphan_meeting(
            meeting_id=306,
            created_at=datetime.utcnow() - timedelta(minutes=45),
            user_agent=None,
        )
        _chunked_stub.delete_chunks.reset_mock()
        create_engine_session, _ = _setup_session([orphan])

        with patch(
            "app.services.orphan_meeting_cleanup.create_celery_engine_and_session",
            create_engine_session,
        ):
            await _scan_and_cleanup()

        assert "[UA: unknown]" in orphan.error_reason

    async def test_chunk_cleanup_failure_continues(self):
        """MinIO delete_chunks 失败 → 不影响 status 标 error (line 86-91 warning)."""
        from app.services.orphan_meeting_cleanup import _scan_and_cleanup

        orphan = _make_orphan_meeting(
            meeting_id=307,
            created_at=datetime.utcnow() - timedelta(minutes=45),
        )
        _chunked_stub.delete_chunks.reset_mock()
        _chunked_stub.delete_chunks.side_effect = Exception("MinIO 500")
        create_engine_session, _ = _setup_session([orphan])

        with patch(
            "app.services.orphan_meeting_cleanup.create_celery_engine_and_session",
            create_engine_session,
        ):
            result = await _scan_and_cleanup()

        # 关键: MinIO 失败时, status 仍标 error
        assert orphan.status == "error"
        assert 307 in result["cleaned"]
