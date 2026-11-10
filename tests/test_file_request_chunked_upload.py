"""10GB 外部收件分片上传 (2026-11-09) 回归测试。

覆盖三类, 每类对应一次真实事故形态:

A. **门禁逻辑** —— 匿名写端点如果没有总量/次数/活跃会话闸, token 一外泄就是
   公共灌盘口 (类 20.226 "判某组件能不能用必须跑双指标"的同族: 能力上线前
   先证明拦住负例)。

B. **无损与校验链** —— 逐片 hash 不一致必须拒收、合并长度不符必须丢弃对象、
   checksum 不符必须丢弃 (类 20.220: 不能只看"compose 返回成功"这个状态字段)。

C. **结构守卫** —— 断言的是**跨文件的同源关系**, 单点行为测试覆盖不到:
   - 两条写入路径必须调**同一个** gates 函数 (类 20.250 ①, 本仓修了原始流水线
     却漏了重跑路径, 三个月后才暴露)
   - 分片 PUT 必须落在 chunked_upload tier 而不是 write tier (否则 320 片被
     30/min 掐死, 症状与"网络断了"一模一样 —— 类 20.218 会议 255 心跳同型)
   - 新 celery task 必须进 celery_app.conf.imports (类 20.219, 本仓已 4 例
     "派发被静默丢弃、功能从未执行、且不报错")
   - 三处上限不得退回写死的 2 GiB 字面量

全部不连 DB、不连 MinIO ⇒ CI 可跑。
"""
import ast
import inspect
import os
import re
from datetime import datetime, timedelta
from types import SimpleNamespace

import pytest

from app.config import settings
from app.services import file_request_gates as gates
from app.services import file_request_upload_service as frus


REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


# ============================================================================
# fixtures
# ============================================================================

def make_request(
    *,
    active: bool = True,
    expires_at=None,
    max_submissions: int = 5,
    max_total_mb: int = 30720,
    used_mb: int = 0,
    submission_count: int = 0,
    max_file_size_mb=None,
    allowed_extensions=None,
    auto_close_on_limit: bool = True,
    require_uploader_name: bool = False,
):
    """造一个 FileRequest 形状的替身 (不落库)。"""
    return SimpleNamespace(
        id=1,
        token="tok" * 10,
        title="外部视频收件",
        is_active=active,
        expires_at=expires_at,
        max_submissions=max_submissions,
        max_total_bytes=(
            int(max_total_mb) * 1024 * 1024 if max_total_mb is not None else None
        ),
        used_bytes=int(used_mb) * 1024 * 1024,
        submission_count=submission_count,
        max_file_size_mb=max_file_size_mb,
        allowed_extensions=allowed_extensions,
        auto_close_on_limit=auto_close_on_limit,
        require_uploader_name=require_uploader_name,
        created_by=7,
        target_folder_id=3,
    )


def make_session(
    *,
    total_chunks: int = 4,
    chunk_size: int = 5 * 1024 * 1024,
    uploaded=None,
    status: str = "uploading",
    expires_at=None,
):
    return SimpleNamespace(
        id=1,
        upload_id="upl_test",
        request_id=1,
        filename="clip.mp4",
        file_size=total_chunks * chunk_size,
        chunk_size=chunk_size,
        total_chunks=total_chunks,
        uploaded_chunks=uploaded if uploaded is not None else [],
        status=status,
        expires_at=expires_at if expires_at is not None else datetime.utcnow() + timedelta(hours=1),
        checksum=None,
        verified_sha256=None,
        knowledge_id=None,
        uploader_name="外部人",
    )


class FakeResult:
    def __init__(self, value):
        self._value = value

    def scalar_one(self):
        return self._value

    def scalar_one_or_none(self):
        return self._value


class FakeDB:
    """只支持 execute(select(...)).scalar_one()/scalar_one_or_none() 的最小替身。"""

    def __init__(self, scalar=None):
        self._scalar = scalar
        self.committed = 0

    async def execute(self, *a, **kw):
        return FakeResult(self._scalar)

    async def commit(self):
        self.committed += 1

    def add(self, obj):
        pass

    async def refresh(self, obj):
        pass


# ============================================================================
# A. 门禁逻辑
# ============================================================================

class TestSingleFileLimit:
    def test_limit_is_min_of_three_sources(self):
        """请求写了 20 GiB 也不能超过网盘天花板 ⇒ 三重取最小。"""
        req = make_request(max_file_size_mb=999_999_999)
        assert gates.single_file_limit_bytes(req) == min(
            int(settings.DRIVE_MAX_FILE_SIZE_MB),
            int(settings.FILE_REQUEST_MAX_SINGLE_MB),
        ) * 1024 * 1024

    def test_request_own_cap_still_binds(self):
        req = make_request(max_file_size_mb=100)
        assert gates.single_file_limit_bytes(req) == 100 * 1024 * 1024

    def test_no_request_means_settings(self):
        assert gates.single_file_limit_bytes(None) == min(
            int(settings.DRIVE_MAX_FILE_SIZE_MB),
            int(settings.FILE_REQUEST_MAX_SINGLE_MB),
        ) * 1024 * 1024


class TestExtensionGate:
    def test_none_means_unlimited(self):
        gates.check_extension(make_request(allowed_extensions=None), "a.zip")

    def test_video_allowed_when_whitelist_is_video(self):
        req = make_request(allowed_extensions=["mp4", "mov"])
        gates.check_extension(req, "会议录像.MP4")  # 大小写不敏感

    def test_non_video_rejected_with_415(self):
        req = make_request(allowed_extensions=["mp4", "mov"])
        with pytest.raises(gates.FileRequestGateError) as ei:
            gates.check_extension(req, "payload.exe")
        assert ei.value.status_code == 415

    def test_dot_prefix_in_whitelist_normalized(self):
        """白名单写成 ['.mp4'] 也要能命中 (创建端点两种写法都出现过)。"""
        req = make_request(allowed_extensions=[".mp4"])
        gates.check_extension(req, "clip.mp4")

    def test_no_extension_rejected(self):
        req = make_request(allowed_extensions=["mp4"])
        with pytest.raises(gates.FileRequestGateError):
            gates.check_extension(req, "README")


@pytest.mark.parametrize(
    "kw,expect_code",
    [
        (dict(active=False), 410),
        (dict(expires_at=datetime.utcnow() - timedelta(seconds=5)), 410),
    ],
)
async def test_closed_or_expired_link_is_410(kw, expect_code):
    req_kwargs = {"active": True, "expires_at": None}
    req_kwargs.update(kw)
    db = FakeDB(scalar=make_request(**req_kwargs))
    with pytest.raises(gates.FileRequestGateError) as ei:
        await gates.load_open_request(db, "tok" * 10)
    assert ei.value.status_code == expect_code


async def test_missing_token_is_404():
    with pytest.raises(gates.FileRequestGateError) as ei:
        await gates.load_open_request(FakeDB(scalar=None), "nope")
    assert ei.value.status_code == 404


async def test_total_bytes_gate_blocks_fourth_video():
    """30 GiB 上限: 已用 25 GiB + 本次 10 GiB ⇒ 413, 不是放行。"""
    req = make_request(max_total_mb=30_720, used_mb=25_600)
    with pytest.raises(gates.FileRequestGateError) as ei:
        await gates.check_gates(FakeDB(0), req, incoming_bytes=10 * 1024 ** 3)
    assert ei.value.status_code == 413


async def test_total_bytes_gate_allows_when_under():
    req = make_request(max_total_mb=30_720, used_mb=0)
    await gates.check_gates(FakeDB(0), req, incoming_bytes=10 * 1024 ** 3)


async def test_submission_count_gate_blocks_when_full():
    req = make_request(max_submissions=5, submission_count=5)
    with pytest.raises(gates.FileRequestGateError) as ei:
        await gates.check_gates(FakeDB(0), req, incoming_bytes=1024)
    assert ei.value.status_code == 409


async def test_active_session_gate_blocks_dos():
    """init 不花钱 ⇒ 只数 submission_count 会被无限建会话灌 staging (DoS)。

    这里 submission_count=0 (一个都没收完), 但已有 5 个进行中的会话,
    max_submissions=5 ⇒ **必须拦**。不数活跃会话的实现会放行。
    """
    req = make_request(max_submissions=5, submission_count=0)
    db = FakeDB(scalar=5)
    with pytest.raises(gates.FileRequestGateError) as ei:
        await gates.check_gates(
            db, req, incoming_bytes=1024, count_active_sessions=True
        )
    assert ei.value.status_code == 409


async def test_active_session_gate_ignored_on_single_shot_path():
    """单请求通路没有"会话"概念 ⇒ 不该因为活跃会话数被拦。"""
    req = make_request(max_submissions=5, submission_count=0)
    await gates.check_gates(
        FakeDB(scalar=99), req, incoming_bytes=1024, count_active_sessions=False
    )


async def test_none_limits_mean_unlimited():
    req = make_request(max_submissions=None, max_total_mb=None)
    await gates.check_gates(FakeDB(0), req, incoming_bytes=1024 ** 3 * 999)


class TestAccounting:
    def test_used_bytes_and_count_both_advance(self):
        """原先只 +1 submission_count, used_bytes 永远 0 ⇒ 总量闸形同不存在。"""
        req = make_request(max_submissions=5, submission_count=1, used_mb=1_024)
        gates.apply_accounting(req, 3 * 1024 ** 3)
        assert req.submission_count == 2
        assert req.used_bytes == 1_024 * 1024 ** 2 + 3 * 1024 ** 3

    def test_auto_close_when_reaching_limit(self):
        req = make_request(max_submissions=5, submission_count=4)
        closed = gates.apply_accounting(req, 1024)
        assert closed is True
        assert req.is_active is False

    def test_no_auto_close_when_disabled(self):
        req = make_request(max_submissions=5, submission_count=4, auto_close_on_limit=False)
        assert gates.apply_accounting(req, 1024) is False
        assert req.is_active is True

    def test_return_value_is_not_merely_link_state(self):
        """链接因**过期**而 is_active=False 时, 不能被报成"你传满了所以关闭"。"""
        req = make_request(max_submissions=5, submission_count=0, active=False)
        assert gates.apply_accounting(req, 1024) is False


def test_gate_error_is_a_valueerror():
    """既有 API 层的 except ValueError 必须仍然接得住 (老行为逐字不变)。"""
    assert issubclass(gates.FileRequestGateError, ValueError)


def test_utcnow_is_naive():
    """tz-aware 传进 naive 列会 DataError (类 20.251 ①, 静默失败一个月的根因)。"""
    assert gates.utcnow_naive().tzinfo is None


# ============================================================================
# B. 分片几何与校验链
# ============================================================================

class TestChunkGeometry:
    def test_auto_chunk_size_scales_with_file(self):
        """10 GiB 必须自动用满 32 MiB 上限 ⇒ 320 片。

        用默认 5 MiB 会得到 2048 片, 既慢又更容易撞限流窗口。
        """
        assert int(settings.FILE_REQUEST_MAX_CHUNK_MB) * 1024 * 1024 >= 5 * 1024 * 1024
        size_max = frus._max_chunk_bytes()
        ten_gib = 10 * 1024 ** 3
        assert size_max == int(settings.FILE_REQUEST_MAX_CHUNK_MB) * 1024 * 1024
        assert -(-ten_gib // size_max) <= 10000, "S3 multipart part 上限"
        assert ten_gib % size_max != 0 or ten_gib // size_max == 320

    def test_min_chunk_is_five_mib(self):
        """低于 5 MiB 的非末片会让 UploadPartCopy 直接失败 ⇒ 必须在 init 就拒。"""
        assert frus.MIN_CHUNK_BYTES == 5 * 1024 * 1024

    def test_chunk_key_zero_padded_for_sort_order(self):
        """拼接顺序靠键名排序 ⇒ 必须零填充, 否则第 10 片排在第 2 片前面。"""
        keys = [frus._chunk_key("u", i) for i in (0, 2, 10, 100)]
        assert sorted(keys) == keys

    def test_final_key_keeps_extension_and_is_per_upload(self):
        a = frus._final_key(1, "uploadA", "会议录像.mp4")
        b = frus._final_key(1, "uploadB", "会议录像.mp4")
        assert a != b, "同请求同名不同会话绝不能共用对象键 (类 20.242 basename 碰撞)"
        assert a.endswith(".mp4")
        assert a.startswith(frus.FINAL_PREFIX + "/1/")

    def test_final_key_sanitizes_path(self):
        """filename 里带 ../ 不能越出前缀。"""
        k = frus._final_key(1, "u", "../../../etc/passwd.txt")
        assert ".." not in k
        assert k.startswith(frus.FINAL_PREFIX + "/1/")

    def test_content_type_guess_for_video(self):
        assert frus._guess_content_type("a.mp4") == "video/mp4"
        assert frus._guess_content_type("a.MOV") == "video/quicktime"
        assert frus._guess_content_type("a.zip") == "application/octet-stream"


class TestMissingChunks:
    def test_missing_reports_holes(self):
        assert frus.FileRequestUploadService._missing([0, 1, 3], 5) == [2, 4]

    def test_missing_capped_at_200(self):
        """响应体不能因为缺 9000 片就塞 9000 个整数。"""
        assert len(frus.FileRequestUploadService._missing([], 9000)) == 200


@pytest.mark.asyncio
async def test_put_chunk_rejects_bad_hash_before_writing(monkeypatch):
    """逐片校验必须是**写入前**拦, 不是写完再对账。"""
    req = make_request(max_submissions=None, max_total_mb=None)
    db = FakeDB(scalar=req)
    monkeypatch.setattr(gates, "load_open_request", lambda *a, **k: _ret(req))
    monkeypatch.setattr(
        frus.FileRequestUploadService, "_load_upload",
        staticmethod(lambda *a, **k: _ret(make_session())),
    )
    put = _Recorder()
    monkeypatch.setattr(frus.file_service, "upload_to_path", put)

    data = b"x" * (5 * 1024 * 1024)
    with pytest.raises(gates.FileRequestGateError) as ei:
        await frus.FileRequestUploadService.put_chunk(
            db, token="t", upload_id="upl_test", index=0, data=data,
            expected_sha256="0" * 64,
        )
    assert ei.value.status_code == 422
    assert put.calls == 0, "校验失败却已经写了对象 = 坏片留在盘上"


@pytest.mark.asyncio
async def test_put_chunk_rejects_short_non_last_chunk(monkeypatch):
    """非末片长度必须 == chunk_size, 否则合并位置全错。"""
    req = make_request(max_submissions=None, max_total_mb=None)
    db = FakeDB(scalar=req)
    monkeypatch.setattr(gates, "load_open_request", lambda *a, **k: _ret(req))
    monkeypatch.setattr(
        frus.FileRequestUploadService, "_load_upload",
        staticmethod(lambda *a, **k: _ret(make_session())),
    )
    put = _Recorder()
    monkeypatch.setattr(frus.file_service, "upload_to_path", put)
    with pytest.raises(gates.FileRequestGateError):
        await frus.FileRequestUploadService.put_chunk(
            db, token="t", upload_id="upl_test", index=0, data=b"short",
        )
    assert put.calls == 0


@pytest.mark.asyncio
async def test_put_chunk_accepts_good_hash(monkeypatch):
    import hashlib
    req = make_request(max_submissions=None, max_total_mb=None)
    db = FakeDB(scalar=req)
    up = make_session()
    monkeypatch.setattr(gates, "load_open_request", lambda *a, **k: _ret(req))
    monkeypatch.setattr(
        frus.FileRequestUploadService, "_load_upload",
        staticmethod(lambda *a, **k: _ret(up)),
    )
    monkeypatch.setattr(frus.file_service, "upload_to_path", _Recorder())
    data = b"y" * (5 * 1024 * 1024)
    out = await frus.FileRequestUploadService.put_chunk(
        db, token="t", upload_id="upl_test", index=0, data=data,
        expected_sha256=hashlib.sha256(data).hexdigest(),
    )
    assert out["uploaded_chunks"] == 1
    assert out["missing_chunks"] == [1, 2, 3]


class TestCompleteValidation:
    """合并后的三道校验 —— 每一道失败都必须**丢弃已合并的对象**。"""

    async def _run(self, monkeypatch, *, merged_size, real_sha, declared=None):
        import hashlib
        req = make_request(max_submissions=None, max_total_mb=None)
        up = make_session(total_chunks=2, chunk_size=5 * 1024 * 1024)
        up.file_size = 2 * 5 * 1024 * 1024
        up.uploaded_chunks = [0, 1]
        monkeypatch.setattr(gates, "load_open_request", lambda *a, **k: _ret(req))
        monkeypatch.setattr(
            frus.FileRequestUploadService, "_load_upload",
            staticmethod(lambda *a, **k: _ret(up)),
        )
        deleted = _Recorder()
        # mock 签名必须与被测代码的**关键字调用**对齐 (compose 用 src_object_names=)
        monkeypatch.setattr(
            frus.file_service, "compose_objects_async",
            lambda src_object_names, dst_object_name, content_type="": _ret(
                {"size": merged_size, "etag": "e",
                 "content_type": content_type, "content_type_matched": True}
            ),
        )
        monkeypatch.setattr(
            frus.file_service, "stream_sha256_async",
            lambda object_name, chunk_size=0: _ret(
                {"sha256": real_sha, "size": merged_size}
            ),
        )
        monkeypatch.setattr(
            frus.FileRequestUploadService, "_safe_delete",
            staticmethod(lambda names: deleted(names)),
        )
        created = _Recorder()

        class FakeDrive:
            def __init__(self, db):
                pass

            async def create_file(self, **kw):
                await created(**kw)
                return SimpleNamespace(id=42)

        monkeypatch.setattr(frus, "DriveService", FakeDrive)
        monkeypatch.setattr(
            frus.activity_service, "log", lambda *a, **k: _ret(None)
        )
        err = None
        out = None
        try:
            out = await frus.FileRequestUploadService.complete_upload(
                FakeDB(scalar=req), token="t", upload_id="upl_test",
                checksum=declared,
            )
        except gates.FileRequestGateError as e:
            err = e
        return err, out, deleted, created, up

    @pytest.mark.asyncio
    async def test_size_mismatch_discards_object(self, monkeypatch):
        wrong = "a" * 64
        err, out, deleted, created, up = await self._run(
            monkeypatch, merged_size=1, real_sha=wrong
        )
        assert err is not None and err.status_code == 500
        assert created.calls == 0, "合并结果不对却建了元数据行"
        assert deleted.calls >= 1, "残缺对象必须删掉"
        assert up.status == "aborted"

    @pytest.mark.asyncio
    async def test_checksum_mismatch_discards_object(self, monkeypatch):
        real = "b" * 64
        size = 2 * 5 * 1024 * 1024
        err, out, deleted, created, up = await self._run(
            monkeypatch, merged_size=size, real_sha=real, declared="c" * 64
        )
        assert err is not None and err.status_code == 422
        assert created.calls == 0
        assert deleted.calls >= 1

    @pytest.mark.asyncio
    async def test_success_writes_real_content_hash(self, monkeypatch):
        """file_hash 必须是服务端**实算**的内容哈希 ⇒ 秒传键不可由客户端伪造。"""
        import hashlib
        size = 2 * 5 * 1024 * 1024
        real = hashlib.sha256(b"z" * 100).hexdigest()
        err, out, deleted, created, up = await self._run(
            monkeypatch, merged_size=size, real_sha=real
        )
        assert err is None, err
        assert out["sha256"] == real
        assert created.kwargs["file_hash"] == real
        assert created.kwargs["storage_mode"] == "drive"
        assert up.status == "completed"
        assert up.knowledge_id == 42

    @pytest.mark.asyncio
    async def test_create_file_failure_removes_orphan_object(self, monkeypatch):
        """元数据建失败 ⇒ 对象必须跟着撤, 否则留下"只有对象没有行"的孤儿。"""
        size = 2 * 5 * 1024 * 1024

        class BoomDrive:
            def __init__(self, db):
                pass

            async def create_file(self, **kw):
                raise RuntimeError("db down")

        req = make_request(max_submissions=None, max_total_mb=None)
        up = make_session(total_chunks=1, chunk_size=5 * 1024 * 1024)
        up.file_size = size
        up.uploaded_chunks = [0]
        monkeypatch.setattr(gates, "load_open_request", lambda *a, **k: _ret(req))
        monkeypatch.setattr(
            frus.FileRequestUploadService, "_load_upload",
            staticmethod(lambda *a, **k: _ret(up)),
        )
        monkeypatch.setattr(
            frus.file_service, "compose_objects_async",
            lambda src_object_names, dst_object_name, content_type="": _ret(
                {"size": size, "etag": "e", "content_type": "video/mp4",
                 "content_type_matched": True}),
        )
        monkeypatch.setattr(
            frus.file_service, "stream_sha256_async",
            lambda object_name, chunk_size=0: _ret({"sha256": "d" * 64, "size": size}),
        )
        deleted = _Recorder()
        monkeypatch.setattr(
            frus.FileRequestUploadService, "_safe_delete",
            staticmethod(lambda names: deleted(names)),
        )
        monkeypatch.setattr(frus, "DriveService", BoomDrive)
        with pytest.raises(gates.FileRequestGateError):
            await frus.FileRequestUploadService.complete_upload(
                FakeDB(scalar=req), token="t", upload_id="upl_test"
            )
        assert deleted.calls >= 1

    @pytest.mark.asyncio
    async def test_incomplete_chunks_are_not_merged(self, monkeypatch):
        req = make_request(max_submissions=None, max_total_mb=None)
        up = make_session(total_chunks=4)
        up.uploaded_chunks = [0, 1]
        monkeypatch.setattr(gates, "load_open_request", lambda *a, **k: _ret(req))
        monkeypatch.setattr(
            frus.FileRequestUploadService, "_load_upload",
            staticmethod(lambda *a, **k: _ret(up)),
        )
        called = _Recorder()
        monkeypatch.setattr(
            frus.file_service, "compose_objects_async",
            lambda src, dst, content_type="": called(src, dst, content_type),
        )
        with pytest.raises(gates.FileRequestGateError) as ei:
            await frus.FileRequestUploadService.complete_upload(
                FakeDB(scalar=req), token="t", upload_id="upl_test"
            )
        assert ei.value.status_code == 409
        assert called.calls == 0, "片没齐就开合并"


# ============================================================================
# C. 结构守卫 —— 单点行为测试覆盖不到的跨文件不变量
# ============================================================================

def _source(rel_path: str) -> str:
    with open(os.path.join(REPO_ROOT, rel_path), encoding="utf-8") as f:
        return f.read()


def _attr_calls_in(rel_path: str, names) -> set:
    """AST 收集 `a.b(` 形态的被调属性名 (不用源码字符串 —— 类 20.226 ⑨)。"""
    tree = ast.parse(_source(rel_path))
    found = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute) and node.attr in names:
            found.add(node.attr)
    return found


@pytest.mark.parametrize(
    "path",
    ["app/services/file_request_service.py",
     "app/services/file_request_upload_service.py"],
)
def test_both_write_paths_share_the_same_gate_functions(path):
    """同一个门禁两条写入路径 ⇒ 必须调**同一个** gates.check_gates/apply_accounting。

    本仓真实教训 (类 20.250 ①): 2026-10-09 给质量门禁修 ai_polish_skipped 只补了
    原始流水线, 重跑路径三个月后才暴露 —— "修好了"只对被改的那条路径成立。
    """
    called = _attr_calls_in(path, {"check_gates", "apply_accounting", "load_open_request"})
    assert "check_gates" in called, f"{path} 没有调用共享门禁"
    assert "apply_accounting" in called, f"{path} 自己记账 (会绕过总量闸)"


def test_no_local_duplicate_of_gate_logic():
    """分片服务里不得留一份自己的闸实现 (那正是漂移的起点)。"""
    src = _source("app/services/file_request_upload_service.py")
    tree = ast.parse(src)
    defined = {
        n.name for n in ast.walk(tree)
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
    }
    for name in ("_check_gates",):
        # 允许保留同名薄包装 (它必须转发给 gates), 但里面不得出现独立判定逻辑
        if name in defined:
            seg = src[src.index(f"async def {name}"):]
            assert "gates.check_gates" in seg.split("\n\n")[0] + seg, (
                f"{name} 未转发到 gates"
            )
    assert "used_bytes = int(req.used_bytes" not in src, "分片服务自己写记账了"


def test_file_size_limits_are_settings_driven():
    """三处 2 GiB 硬闸不得退回字面量 (10GB 会被 413 拒)。"""
    from app.services import drive_service as ds
    from app.services import generic_chunked_upload_service as gc
    from app.services import drive_chunked_upload_service as dc

    expected = int(settings.DRIVE_MAX_FILE_SIZE_MB) * 1024 * 1024
    assert ds.MAX_DRIVE_FILE_SIZE_BYTES == expected
    assert gc.MAX_DRIVE_FILE_SIZE_BYTES == expected
    assert dc.MAX_FILE_SIZE == expected
    assert ds.MAX_DRIVE_FILE_SIZE_BYTES >= 10 * 1024 ** 3, "至少要容得下 10 GiB"


def test_chunked_upload_schema_no_longer_caps_at_two_gib():
    """旧版 drive init 的 Pydantic 也一并抬 (原先 le=2GiB / total_chunks<=2000)。"""
    from app.api.v1.drive_files import ChunkedUploadInitRequest as M

    fields = M.model_fields
    size_le = [getattr(c, "le", None) for c in (fields["file_size"].metadata or [])]
    size_le = [v for v in size_le if v is not None]
    assert size_le, "file_size 必须仍有上限 (否则 DoS 面无限)"
    assert max(size_le) >= 10 * 1024 ** 3, (
        f"file_size 上限 {max(size_le)} 容不下 10 GiB"
    )
    chunk_le = [getattr(c, "le", None) for c in (fields["total_chunks"].metadata or [])]
    chunk_le = [v for v in chunk_le if v is not None]
    assert max(chunk_le) >= 10000, (
        "5 MiB × 2000 = 9.77 GiB, 连 10 GiB 都进不来"
    )


def test_chunk_put_rate_limit_is_not_write_tier():
    """⭐ 分片 PUT 必须落 chunked_upload tier (120/min), 不能落 write (30/min)。

    10 GiB / 32 MiB = 320 片 ⇒ 30/min 会在第十秒把上传掐死, 而前端只看到 429
    刷屏, 症状与"网络断了"一模一样。会议 255 那次心跳共用 write tier 导致
    38 分钟录音 0 心跳、录音全丢 (类 20.218) —— 同一个坑的第二种踩法。
    """
    from app.core.rate_limit import _get_rate_limit_type

    def tier(method: str, path: str) -> str:
        # ⚠️ 判据必须是**真实生产函数** _get_rate_limit_type, 不是任何手算的镜像。
        # 之前这版测试调了一个根本不存在的 _resolve_tier, 于是它一直 ImportError,
        # 却被日志噪声盖住、被我误读成"通过" —— 正是类 20.229 的"长得像证据的文本"。
        fake = SimpleNamespace(
            method=method,
            url=SimpleNamespace(path=path, query=""),
            headers=[],
            client=SimpleNamespace(host="1.2.3.4"),
        )
        return _get_rate_limit_type(fake)

    assert tier("PUT", "/api/v1/file-requests/tok123/uploads/upl_abc/chunks/17") \
        == "chunked_upload", "分片 PUT 落在 write tier ⇒ 320 片必被 30/min 掐死"
    # ⚠️ init/complete/abort 这三个 POST 落 `upload` 档 (10/min), **不是 write** ——
    # 因为它们路径含子串 `/upload`, 命中限流规则第 7 条"含 /upload → upload"。
    # 实测坐实 (本条测试第一次跑就把我"应该是 write"的臆断证伪了)。
    # 对产品**无害**: 真正高频的是分片 PUT (已正确落 120/min), 而 init/complete
    # 每个文件各只调一次, 10/min 足够。这里如实钉住实际档位, 不让产品迁就错预期。
    assert tier("POST", "/api/v1/file-requests/tok123/uploads") == "upload"
    assert tier("POST", "/api/v1/file-requests/tok123/uploads/upl_abc/complete") == "upload"
    assert tier("GET", "/api/v1/file-requests/tok123/info") == "read"
    # 会议音频分片的老行为不许被动到
    assert tier("PUT", "/api/v1/meetings/265/audio-chunk") == "chunked_upload"


def test_new_celery_task_is_registered_in_imports():
    """⭐ 类 20.219: 定义了 @celery_app.task 却没进 imports ⇒ worker 静默丢弃。

    本仓已有 4 例 (meeting_chunk / drive_index / auto_rag / rag_eval_runner),
    症状全是"功能看着在、其实从未跑过、且不报任何错"。这里不靠 grep 文本,
    直接读 celery_app.conf.imports 的实际值。
    """
    from app.core.celery import celery_app

    assert "app.services.file_request_upload_tasks" in list(celery_app.conf.imports)

    # 并且任务名要能在 beat 里找到, 否则注册了也没人调度
    names = [v.get("task") for v in (celery_app.conf.beat_schedule or {}).values()]
    assert any(
        n and n.endswith("cleanup_file_request_uploads_task") for n in names
    ), "任务已注册但没有 beat 条目 ⇒ staging 永不清理"


def test_compose_does_not_call_imaginary_validate():
    """⭐ file_service.compose_objects_async 不得对 ComposeSource 调 `.validate()`。

    minio 7.2.0 的 ComposeSource **没有公开 validate()** —— 我之前想当然写了
    `for s in sources: s.validate()`, compose **探针实测**当场 AttributeError。
    单测里 compose 全程被 mock, 所以这条错误 mock 挡不住、只有真碰 MinIO 才暴露
    (类 20.220 "跑过≠发生" 的又一形态)。part 尺寸校验由 compose_object 内部做。

    ⚠️ 判据必须用 **AST 匹配真实调用**, 不能用源码字符串匹配 —— 本守卫第一版写的是
    `".validate()" not in seg`, 结果被 file_service 里那句**解释为什么不能调**的注释
    (`` `s.validate()` ``) 判成"有调用"而误红。这正是类 20.225: 「判某文件是否使用 X
    必须匹配用法, 不能匹配提及」—— 而注释里的提及正是最高发的假阳性来源。
    """
    tree = ast.parse(_source("app/services/file_service.py"))
    fn = next(
        (n for n in ast.walk(tree)
         if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
         and n.name == "compose_objects_async"),
        None,
    )
    assert fn is not None, "compose_objects_async 不见了"

    calls = {
        n.func.attr
        for n in ast.walk(fn)
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
    }
    assert "validate" not in calls, "别给 ComposeSource 加臆造的 validate() 调用"
    # 反向锚点: 必须真的调 compose_object, 不是又退回 read()+put 全内存老路
    assert "compose_object" in calls, "服务端拼接不能退化成整文件入内存"


def test_compose_minio_byte_identical():
    """真实 MinIO 上验: N 个 ≥5MiB 分片 compose 后, 回读 SHA256 == 拼接前期望值。

    这是"画质无损"最硬的一条证据 —— 且**只能真跑 MinIO 才有意义** (mock 测的是
    我的调用形状, 不是 MinIO 的行为)。本机有 MinIO 就跑, CI 无则模块级 skip
    (与本仓 tests/test_generic_chunked_upload.py 同约定)。
    """
    import asyncio
    import hashlib
    import io

    from app.services.file_service import file_service

    MB = 1024 * 1024
    parts = [os.urandom(6 * MB), os.urandom(6 * MB), os.urandom(12345)]
    keys = []
    expected = hashlib.sha256()
    try:
        for i, p in enumerate(parts):
            k = f"zz-selftest-{os.getpid()}/chunk_{i:06d}"
            file_service.client.put_object(
                file_service.bucket, k, io.BytesIO(p),
                length=len(p), content_type="application/octet-stream",
            )
            keys.append(k)
            expected.update(p)
        final = f"zz-selftest-{os.getpid()}/final.bin"
        res = asyncio.run(file_service.compose_objects_async(
            src_object_names=keys, dst_object_name=final, content_type="video/mp4",
        ))
        assert res["size"] == sum(len(p) for p in parts)
        hr = asyncio.run(file_service.stream_sha256_async(final))
        assert hr["sha256"] == expected.hexdigest(), "compose 改动了字节 = 有损"
        assert res["content_type"] == "video/mp4"
    except Exception as exc:  # MinIO 不可达 ⇒ 环境缺口不是代码缺陷 (类 20.220)
        msg = str(exc).lower()
        if any(t in msg for t in ("connection", "refused", "name resolution",
                                  "max retries", "urlopen")):
            pytest.skip(f"MinIO 不可达 (CI 环境), 该守卫只在有 MinIO 时有效: {exc}")
        raise
    finally:
        for k in keys + [f"zz-selftest-{os.getpid()}/final.bin"]:
            try:
                file_service.delete_file(k)
            except Exception:
                pass


def test_complete_upload_return_branches_are_shape_identical():
    """⭐ complete_upload 的两个完成分支 (首次成功 / already_completed) 必须**逐字同形**。

    命中类 20.250 ④: 同一个键在两个写入方下不能有两种形状 ⇒ 读方按哪个解析都可能
    静默错。前端 agent 2026-11-09 实测就是被"already_completed 分支缺 size/
    request_closed"坑到, 重复点完成时误报"链接还开着"。

    判据用 AST 直读两处 return 的键集 (不是跑一次调用 —— 两分支要 DB 状态不同才走到,
    单测里凑不出真实第二分支), 且**只要有人改回不同形状就红**。
    """
    path = os.path.join(REPO_ROOT, "app", "services", "file_request_upload_service.py")
    tree = ast.parse(_source(os.path.relpath(path, REPO_ROOT)))
    branch_keys = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Return) and isinstance(node.value, ast.Dict):
            keys = {
                k.value for k in node.value.keys
                if isinstance(k, ast.Constant) and isinstance(k.value, str)
            }
            # 完成分支的特征键: 同时有 success + sha256 + content_type_in_minio
            if {"success", "sha256", "content_type_in_minio"} <= keys:
                branch_keys.append(keys)
    assert len(branch_keys) == 2, (
        f"应有恰好 2 个完成分支, 实得 {len(branch_keys)} —— 若新增/删了分支请一并更新本守卫"
    )
    assert branch_keys[0] == branch_keys[1], (
        f"两个完成分支返回形状不一致: 差集 = "
        f"{branch_keys[0] ^ branch_keys[1]}"
    )


def test_new_migration_revision_id_within_32_chars():
    """alembic_version.version_num 在 CI 是 VARCHAR(32)、生产是 VARCHAR(64)
    ⇒ 本地/生产全绿、只有 CI 红。判据只能是长度 (类 20.227 ③)。"""
    for name in os.listdir(os.path.join(REPO_ROOT, "alembic", "versions")):
        if not name.startswith("150_") or not name.endswith(".py"):
            continue
        src = _source(os.path.join("alembic", "versions", name))
        m = re.search(r'^revision:?\s*(?:str)?\s*=\s*["\']([^"\']+)["\']', src, re.M)
        assert m, f"{name} 没解析出 revision"
        assert len(m.group(1)) <= 32, f"revision {m.group(1)!r} 长 {len(m.group(1))} >32"


def test_migration_chains_single_head():
    """迁移链必须恰好 1 个 head, 否则 `alembic upgrade head` 报 Multiple head
    revisions ⇒ 直接阻塞部署 (类 20.222 族, 本仓 062/063 双头真实发生过)。

    ⚠️ 判据用 alembic 自己的 ScriptDirectory, **不手写正则扫全树** ——
    手写正则一旦漏匹配某个带类型注解的 down_revision, head 数就算错,
    于是"守卫通过"与"链真的单头"脱钩 (类 20.229: "未命中"先怀疑探针)。
    且**只断言"恰为 1 个 head"这条不变量, 不写死编号** (编号随新增漂移)。
    """
    from alembic.config import Config
    from alembic.script import ScriptDirectory

    ini = os.path.join(REPO_ROOT, "alembic.ini")
    if not os.path.exists(ini):
        pytest.skip("alembic.ini 不在预期位置 (容器/CI 布局差异)")
    cfg = Config(ini)
    cfg.set_main_option("script_location", os.path.join(REPO_ROOT, "alembic"))
    heads = ScriptDirectory.from_config(cfg).get_heads()
    assert len(heads) == 1, f"alembic 应当恰好 1 个 head, 实得 {sorted(heads)}"


def test_new_migration_is_on_the_active_chain():
    """150 必须在活链上, 否则是孤儿迁移 —— 注册了但部署从不执行 (类 20.219 同族)。"""
    from alembic.config import Config
    from alembic.script import ScriptDirectory

    ini = os.path.join(REPO_ROOT, "alembic.ini")
    if not os.path.exists(ini):
        pytest.skip("alembic.ini 不在预期位置")
    cfg = Config(ini)
    cfg.set_main_option("script_location", os.path.join(REPO_ROOT, "alembic"))
    sd = ScriptDirectory.from_config(cfg)
    revs = {r.revision for r in sd.walk_revisions()}
    assert "150_file_request_uploads" in revs, "150 不在活链上 ⇒ 部署时不会被执行"


def test_anonymous_chunk_endpoints_exist_without_auth():
    """五个匿名分片端点必须存在, 且**不得**依赖 get_current_user。

    "外部人员没有会员账号"是这个需求的前提; 而反过来, 匿名**写**端点必须
    经上面的闸测试, 两者缺一不可。
    """
    from app.api.v1.file_requests import router

    paths = {}
    for r in router.routes:
        paths.setdefault(r.path, set()).update(r.methods)

    want = {
        "/file-requests/{token}/uploads",
        "/file-requests/{token}/uploads/{upload_id}",
        "/file-requests/{token}/uploads/{upload_id}/chunks/{index}",
        "/file-requests/{token}/uploads/{upload_id}/complete",
        "/file-requests/{token}/uploads/{upload_id}/abort",
    }
    assert want <= set(paths), f"缺匿名端点: {want - set(paths)}"

    src = _source("app/api/v1/file_requests.py")
    seg = src[src.index("# 匿名分片上传"):] if "# 匿名分片上传" in src else src[src.index("/{token}/uploads", src.index("@router.post(\"/{token}/uploads")):]
    for ep in ("/uploads\"", "/uploads/{upload_id}", "/complete", "/abort"):
        i = seg.find(ep)
        chunk = seg[i:i + 1200]
        assert "get_current_user" not in chunk, f"{ep} 混进了登录依赖"


def test_strict_defaults_are_actually_strict():
    """默认档不变量 (2026-11-10 主指挥改口径: 单文件 30GB / 单链接不限总量)。"""
    assert int(settings.FILE_REQUEST_MAX_SUBMISSIONS) == 5
    # 0 = 不限 (主指挥 2026-11-10 拍板); 不许悄悄改回"有限但没写明"的数
    assert int(settings.FILE_REQUEST_MAX_TOTAL_MB) == 0
    assert int(settings.FILE_REQUEST_MAX_SINGLE_MB) == 30_720
    assert int(settings.DRIVE_MAX_FILE_SIZE_MB) == 30_720
    assert int(settings.FILE_REQUEST_LINK_TTL_HOURS) == 72
    assert bool(settings.FILE_REQUEST_AUTO_CLOSE_ON_LIMIT) is True
    assert int(settings.FILE_REQUEST_MAX_CHUNK_MB) * 1024 * 1024 < 1024 * 1024 * 1024, (
        "单片必须远小于云端 nginx client_max_body_size 1024m —— 走分片就不用改 nginx 的前提"
    )


def test_video_extension_default_present():
    exts = gates.parse_extensions(settings.FILE_REQUEST_VIDEO_EXTS)
    assert {"mp4", "mov", "mkv", "webm"} <= set(exts)
    assert "exe" not in exts


# ============================================================================
# helpers
# ============================================================================

async def _ret(value):
    """把同步值包成 awaitable, 供 monkeypatch 替换 async 函数。"""
    return value


class _Recorder:
    """记录 async 调用: 直接当被替换函数用 (await rec(...) 可行)。"""

    def __init__(self):
        self.calls = 0
        self.args = []
        self.kwargs = {}

    async def __call__(self, *a, **kw):
        self.calls += 1
        self.args.append(a)
        self.kwargs = kw
        return None
