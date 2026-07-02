"""v2 PR6-P8: notification rich title/body 单元测试

覆盖范围:
1. _build_title_body: 5 种 context × 各种 meta (comment/reply/star/share/mention)
2. _simplify_file_type: 9 种 MIME/扩展名 → 简化分类
3. _lookup_rich_metadata: file_name + file_type + comment_preview 拼装
4. dedup 命中时 title 重拼 (title/body 含 repeated_count)

不依赖 DB (纯函数为主, async _lookup 用 testbot 用户 mock)
"""
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from app.services.notification_service import (
    NotificationService,
    _simplify_file_type,
    BODY_PREVIEW_MAX_CHARS,
)


# ============================================================
# _simplify_file_type 测试 (纯函数, 9 分类覆盖)
# ============================================================

class TestSimplifyFileType:
    """v2 PR6-P8: MIME → 简化分类"""

    def test_pdf_mime(self):
        assert _simplify_file_type("application/pdf", None) == "pdf"

    def test_pdf_extension_fallback(self):
        assert _simplify_file_type(None, "实验报告.pdf") == "pdf"

    def test_word_mime(self):
        assert _simplify_file_type("application/msword", None) == "doc"
        assert _simplify_file_type(
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document", None
        ) == "doc"

    def test_word_extension(self):
        assert _simplify_file_type(None, "paper.docx") == "doc"

    def test_excel_mime(self):
        assert _simplify_file_type("application/vnd.ms-excel", None) == "excel"
        assert _simplify_file_type(
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", None
        ) == "excel"

    def test_excel_extension(self):
        assert _simplify_file_type(None, "data.xlsx") == "excel"

    def test_ppt(self):
        assert _simplify_file_type(None, "slides.pptx") == "ppt"

    def test_image_mime_prefix(self):
        """image/* 前缀通配"""
        for mime in ("image/png", "image/jpeg", "image/gif", "image/webp", "image/heic"):
            assert _simplify_file_type(mime, None) == "image", f"failed for {mime}"

    def test_audio_mime_prefix(self):
        for mime in ("audio/mpeg", "audio/wav", "audio/mp4"):
            assert _simplify_file_type(mime, None) == "audio", f"failed for {mime}"

    def test_video_mime_prefix(self):
        for mime in ("video/mp4", "video/quicktime"):
            assert _simplify_file_type(mime, None) == "video", f"failed for {mime}"

    def test_archive_extension(self):
        assert _simplify_file_type(None, "code.zip") == "archive"
        assert _simplify_file_type(None, "data.tar") == "archive"

    def test_text(self):
        assert _simplify_file_type("text/plain", None) == "text"
        assert _simplify_file_type(None, "readme.md") == "text"

    def test_other_fallback(self):
        """未知 MIME + 无扩展 → other"""
        assert _simplify_file_type("application/x-binary", None) == "other"
        assert _simplify_file_type(None, "blob") == "other"
        assert _simplify_file_type(None, None) == "other"

    def test_mime_priority_over_extension(self):
        """MIME 精确优先, 扩展兜底"""
        # PDF MIME + word 扩展 → MIME 赢
        assert _simplify_file_type("application/pdf", "docx") == "pdf"


# ============================================================
# _build_title_body 测试 (纯函数, 5 context 模板覆盖)
# ============================================================

class TestBuildTitleBody:
    """v2 PR6-P8: title/body 实时拼"""

    def test_comment_context(self):
        """'comment' context: '杜同贺 在 实验数据.xlsx 提到了你'"""
        meta = {
            "file_name": "实验数据.xlsx",
            "file_type": "excel",
            "comment_preview": "这个数据需要重新测一下",
        }
        title, body = NotificationService._build_title_body(
            actor_name="杜同贺", meta=meta, context="comment", repeated_count=1,
        )
        assert title == "杜同贺 在 实验数据.xlsx 提到了你"
        assert body == "这个数据需要重新测一下 · excel"

    def test_reply_context(self):
        """'reply:N' context: '王天志 回复了你的评论'"""
        meta = {
            "file_name": None,
            "file_type": "pdf",
            "comment_preview": "好的我知道了",
        }
        title, body = NotificationService._build_title_body(
            actor_name="王天志", meta=meta, context="reply:42", repeated_count=1,
        )
        assert title == "王天志 回复了你的评论"
        assert body == "好的我知道了 · 回复"

    def test_star_context(self):
        """'star' context: '赵航佳 收藏了你的文件'"""
        meta = {"file_name": "研究方案.docx", "file_type": "doc", "comment_preview": ""}
        title, body = NotificationService._build_title_body(
            actor_name="赵航佳", meta=meta, context="star", repeated_count=1,
        )
        assert title == "赵航佳 收藏了你的文件"
        assert body == "研究方案.docx · doc"

    def test_share_context(self):
        """'share' context: '贾琦 分享了 数据.xlsx 给你'"""
        meta = {"file_name": "数据.xlsx", "file_type": "excel", "comment_preview": ""}
        title, body = NotificationService._build_title_body(
            actor_name="贾琦", meta=meta, context="share", repeated_count=1,
        )
        assert title == "贾琦 分享了 数据.xlsx 给你"
        assert body == "数据.xlsx · excel"

    def test_mention_default_context(self):
        """'mention' / 其他 context: '杜同贺 在 报告.pdf 提醒了你'"""
        meta = {"file_name": "报告.pdf", "file_type": "pdf", "comment_preview": ""}
        title, body = NotificationService._build_title_body(
            actor_name="杜同贺", meta=meta, context="upload", repeated_count=1,
        )
        assert title == "杜同贺 在 报告.pdf 提醒了你"

    def test_null_actor_falls_back_to_system(self):
        """actor=None → '系统'"""
        meta = {"file_name": "a.pdf", "file_type": "pdf", "comment_preview": ""}
        title, _ = NotificationService._build_title_body(
            actor_name=None, meta=meta, context="comment", repeated_count=1,
        )
        assert title.startswith("系统")

    def test_null_file_name_fallback(self):
        """file_name=null → '文件 #X' 兜底"""
        meta = {"file_id": 540, "file_name": None, "file_type": "txt", "comment_preview": ""}
        title, _ = NotificationService._build_title_body(
            actor_name="A", meta=meta, context="comment", repeated_count=1,
        )
        assert "文件 #540" in title

    def test_repeated_count_appended(self):
        """dedup 命中 repeated_count > 1 → title 加 '(xN)'"""
        meta = {"file_name": "a.pdf", "file_type": "pdf", "comment_preview": ""}
        title, _ = NotificationService._build_title_body(
            actor_name="A", meta=meta, context="comment", repeated_count=3,
        )
        assert title.endswith("(x3)")

    def test_repeated_count_1_no_suffix(self):
        """repeated_count=1 → 不加 suffix"""
        meta = {"file_name": "a.pdf", "file_type": "pdf", "comment_preview": ""}
        title, _ = NotificationService._build_title_body(
            actor_name="A", meta=meta, context="comment", repeated_count=1,
        )
        assert "(x1)" not in title

    def test_comment_no_preview_fallback(self):
        """comment 无 preview → body 用 file_name + file_type"""
        meta = {"file_name": "a.pdf", "file_type": "pdf", "comment_preview": ""}
        _, body = NotificationService._build_title_body(
            actor_name="A", meta=meta, context="comment", repeated_count=1,
        )
        assert body == "a.pdf · pdf"

    def test_title_truncate_200_chars(self):
        """title 超 200 char → 截断防御"""
        meta = {"file_name": "a" * 300, "file_type": "pdf", "comment_preview": ""}
        title, _ = NotificationService._build_title_body(
            actor_name="A" * 100, meta=meta, context="comment", repeated_count=1,
        )
        assert len(title) <= 200

    def test_reply_no_preview_fallback(self):
        """reply 无 preview → body 用 file_name + file_type"""
        meta = {"file_name": "a.pdf", "file_type": "pdf", "comment_preview": ""}
        _, body = NotificationService._build_title_body(
            actor_name="A", meta=meta, context="reply:1", repeated_count=1,
        )
        # 无 preview 时 reply 走 default 分支
        assert body == "a.pdf · pdf"


# ============================================================
# _lookup_actor_name 测试 (mock DB session)
# ============================================================

class TestLookupActorName:
    """v2 PR6-P8: actor username/name 查询"""

    @pytest.mark.asyncio
    async def test_none_actor_returns_none(self):
        db = MagicMock()
        result = await NotificationService._lookup_actor_name(db, None)
        assert result is None

    @pytest.mark.asyncio
    async def test_actor_with_username(self):
        """优先 username (lowercase 短)"""
        db = MagicMock()
        # 模拟 db.execute(...).first() 返 row(username='du_tonghe', name='杜同贺')
        row = MagicMock(username="du_tonghe", name="杜同贺")
        execute_result = MagicMock()
        execute_result.first = MagicMock(return_value=row)
        db.execute = AsyncMock(return_value=execute_result)

        result = await NotificationService._lookup_actor_name(db, 59)
        assert result == "du_tonghe"

    @pytest.mark.asyncio
    async def test_actor_without_username_fallback_to_name(self):
        """username=null → fallback name"""
        db = MagicMock()

        class FakeRow:
            username = None
            name = "杜同贺"

        execute_result = MagicMock()
        execute_result.first = MagicMock(return_value=FakeRow())
        db.execute = AsyncMock(return_value=execute_result)

        result = await NotificationService._lookup_actor_name(db, 59)
        assert result == "杜同贺"

    @pytest.mark.asyncio
    async def test_actor_not_found(self):
        """用户不存在 → None"""
        db = MagicMock()
        execute_result = MagicMock()
        execute_result.first = MagicMock(return_value=None)
        db.execute = AsyncMock(return_value=execute_result)

        result = await NotificationService._lookup_actor_name(db, 99999)
        assert result is None


# ============================================================
# _lookup_rich_metadata 测试 (mock DB)
# ============================================================

class TestLookupRichMetadata:
    """v2 PR6-P8: file_name + file_type + comment_preview 拼装"""

    @pytest.mark.asyncio
    async def test_comment_context_gets_latest_comment(self):
        """context='comment' → 查最新一条 comment"""
        db = MagicMock()

        # 第一次 db.execute: Knowledge (file_name + file_type)
        k_row = MagicMock(file_name="实验.pdf", file_type="application/pdf")
        # 第二次 db.execute: FileComment (id + content)
        c_row = MagicMock(id=123, content="这个数据需要重新测一下 " * 5)

        execute_results = [MagicMock(first=MagicMock(return_value=k_row)),
                           MagicMock(first=MagicMock(return_value=c_row))]
        db.execute = AsyncMock(side_effect=execute_results)

        result = await NotificationService._lookup_rich_metadata(
            db, file_id=540, context="comment",
        )
        assert result["file_name"] == "实验.pdf"
        assert result["file_type"] == "pdf"  # simplified
        assert "需要重新测一下" in result["comment_preview"]
        assert len(result["comment_preview"]) <= BODY_PREVIEW_MAX_CHARS
        assert result["comment_id"] == 123

    @pytest.mark.asyncio
    async def test_reply_context_gets_specific_comment(self):
        """context='reply:42' → 查 id=42 的 comment"""
        db = MagicMock()

        k_row = MagicMock(file_name="报告.pdf", file_type="application/pdf")
        c_row = MagicMock(id=42, file_id=540, content="回复内容")

        execute_results = [MagicMock(first=MagicMock(return_value=k_row)),
                           MagicMock(first=MagicMock(return_value=c_row))]
        db.execute = AsyncMock(side_effect=execute_results)

        result = await NotificationService._lookup_rich_metadata(
            db, file_id=540, context="reply:42",
        )
        assert result["comment_id"] == 42
        assert result["comment_preview"] == "回复内容"

    @pytest.mark.asyncio
    async def test_file_not_found(self):
        """file_id 不存在 → 全 None"""
        db = MagicMock()
        execute_result = MagicMock(first=MagicMock(return_value=None))
        db.execute = AsyncMock(return_value=execute_result)

        result = await NotificationService._lookup_rich_metadata(
            db, file_id=99999, context="comment",
        )
        assert result["file_name"] is None
        assert result["file_type"] is None
        assert result["comment_preview"] is None

    @pytest.mark.asyncio
    async def test_reply_invalid_id_format(self):
        """context='reply:abc' (非 int) → 不查 comment"""
        db = MagicMock()
        k_row = MagicMock(file_name="a.pdf", file_type="application/pdf")
        execute_result = MagicMock(first=MagicMock(return_value=k_row))
        db.execute = AsyncMock(return_value=execute_result)

        result = await NotificationService._lookup_rich_metadata(
            db, file_id=540, context="reply:abc",
        )
        # comment_preview 保持 None (parse ValueError 跳过)
        assert result["comment_preview"] is None
        assert result["file_name"] == "a.pdf"

    @pytest.mark.asyncio
    async def test_reply_id_wrong_file(self):
        """reply:N 的 N 属于其他 file → 安全拒绝"""
        db = MagicMock()

        k_row = MagicMock(file_name="a.pdf", file_type="application/pdf")
        # c_row.file_id != 540 → 防 cross-file reply 泄漏
        c_row = MagicMock(id=42, file_id=999, content="其他文件")

        execute_results = [MagicMock(first=MagicMock(return_value=k_row)),
                           MagicMock(first=MagicMock(return_value=c_row))]
        db.execute = AsyncMock(side_effect=execute_results)

        result = await NotificationService._lookup_rich_metadata(
            db, file_id=540, context="reply:42",
        )
        # file 不匹配 → comment 不返回
        assert result["comment_preview"] is None
        assert result["comment_id"] is None


# ============================================================
# Constants 验证
# ============================================================

class TestConstants:
    """v2 PR6-P8: 常量"""

    def test_body_preview_max_chars(self):
        """BODY_PREVIEW_MAX_CHARS == 60 (前端卡片 2 行省略号)"""
        assert BODY_PREVIEW_MAX_CHARS == 60