"""W98 Drive → KB 入库管线 e2e 测试 (drive_to_kb_service)

覆盖:
- 单文件入库: drive 行 → kb 行, 原 drive 行保留, 关联字段正确
- 幂等: 同 drive file_id 重复调用不重复建 kb 行
- 解析失败容错: 坏文件/空解析 → 元数据兜底条目, 不崩 (2026-09-05 全格式默认入库)
- 批量入库计数: ingest_folder / ingest_team_files (dry_run + 实际)
- 全格式分级: binary 元数据兜底 (不下载) / 图片 OCR / 音视频 ASR / 压缩包文本成员
- 版本更新 reingest: 原地刷新既有 kb 行 (不新建)

跑法 (本地, 测试栈 DB localhost:5433):
    TEST_DATABASE_URL=postgresql+asyncpg://postgres:test_password@localhost:5433/microbubble_test \
    SKIP_DB_SETUP=1 python -m pytest tests/test_drive_to_kb_e2e.py -v
"""
import os
import uuid as _uuid_lib

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool
from sqlalchemy import select

TEST_DB_URL = os.getenv(
    "TEST_DATABASE_URL",
    "postgresql+asyncpg://postgres:test_password@localhost:5433/microbubble_test",
)


@pytest_asyncio.fixture
async def db_factory():
    """独立 NullPool engine + sessionmaker (跨 loop 安全)"""
    engine = create_async_engine(TEST_DB_URL, poolclass=NullPool)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with factory() as session:
        from app.core.database import Base
        import app.models  # noqa: F401
        await session.execute(select(1))
        # 清空 (幂等, 防并行残留)
        from sqlalchemy import text
        await session.execute(text("SET session_replication_role = 'replica'"))
        await session.execute(text("DELETE FROM knowledge"))
        await session.execute(text("DELETE FROM members"))
        await session.execute(text("RESET session_replication_role"))
        await session.commit()

    yield factory

    async with factory() as session:
        from sqlalchemy import text
        await session.execute(text("SET session_replication_role = 'replica'"))
        await session.execute(text("DELETE FROM knowledge"))
        await session.execute(text("DELETE FROM members"))
        await session.execute(text("RESET session_replication_role"))
        await session.commit()
    await engine.dispose()


async def _make_member(db: AsyncSession, tag: str) -> object:
    from app.models.member import Member
    u = _uuid_lib.uuid4().hex[:8]
    m = Member(
        username=f"d2kb_{tag}_{u}",
        name=f"Drive2KB {tag}",
        password_hash="hash",
        role="member",
        grade="测试",
        is_active=True,
        wechat_id=f"__TEST_BACKFILL_{u}_{tag}__",
    )
    db.add(m)
    await db.commit()
    await db.refresh(m)
    return m


async def _make_drive_file(
    db: AsyncSession,
    *,
    member,
    title="d2kb_test.txt",
    file_name="d2kb_test.txt",
    file_type=".txt",
    file_path="drive/test/d2kb.txt",
    content="[drive upload] placeholder",
    visibility="team",
    folder_id=None,
    is_latest=True,
):
    from app.models.knowledge import Knowledge
    k = Knowledge(
        title=title,
        content=content,
        file_path=file_path,
        file_name=file_name,
        file_type=file_type,
        file_size=len(content or ""),
        storage_mode="drive",
        visibility=visibility,
        folder_id=folder_id,
        created_by=member.id,
        source_type="drive",
        is_latest=is_latest,
    )
    db.add(k)
    await db.commit()
    await db.refresh(k)
    return k


@pytest_asyncio.fixture
async def member(db_factory):
    factory = db_factory
    async with factory() as db:
        m = await _make_member(db, "alice")
    yield m
    async with factory() as db:
        from sqlalchemy import text
        await db.execute(text("SET session_replication_role = 'replica'"))
        await db.execute(
            text("DELETE FROM members WHERE username LIKE :p"),
            {"p": f"d2kb_%"},
        )
        await db.execute(text("RESET session_replication_role"))
        await db.commit()


@pytest.fixture
def mock_analysis():
    """屏蔽 analyze_knowledge_task (Celery delay + 同步降级全不跑)

    drive → kb 服务本身只负责: 查行/幂等/下载/解析/建 kb 行/入队。
    真正的 embedding + LLM 分析走 Celery worker (生产), 单测里 mock 掉
    避免真模型加载 + 真 LLM 调用 (7 分钟/用例)。
    """
    from unittest.mock import MagicMock, patch

    with patch("app.services.knowledge_service.analyze_knowledge_task") as mock_task:
        mock_task.delay = MagicMock()
        yield mock_task


# === 单文件入库 ===


@pytest.mark.asyncio
async def test_ingest_single_file_creates_kb_row(db_factory, member, mock_analysis):
    """正常入库: drive 行保留 + 新建 kb 行 + 关联字段 + 内容解析"""
    from app.services.drive_to_kb_service import DriveToKBService
    from unittest.mock import patch

    async with db_factory() as db:
        drive_file = await _make_drive_file(
            db, member=member,
            title="气泡动力学",
            file_name="bubble.txt",
            content="[drive upload] bubble",
        )

    async with db_factory() as db:
        with patch(
            "app.services.file_service.file_service.download_file",
            return_value="微纳米气泡动力学研究内容" .encode("utf-8"),
        ) as mock_dl:
            svc = DriveToKBService(db)
            result = await svc.ingest_drive_file(drive_file.id)
            mock_dl.assert_called_once_with("drive/test/d2kb.txt")

        assert result["already_ingested"] is False
        assert result["source_file_id"] == drive_file.id
        assert result["knowledge_id"] > 0

        # kb 行校验
        from app.models.knowledge import Knowledge
        kb = (await db.execute(
            select(Knowledge).where(Knowledge.id == result["knowledge_id"])
        )).scalar_one()
        assert kb.storage_mode == "kb"
        assert kb.source_type == "drive_extracted"
        assert kb.source == f"drive://file/{drive_file.id}"
        assert kb.original_path == drive_file.file_path
        assert kb.original_parent_id == drive_file.folder_id
        assert kb.meta.get("drive_source_file_id") == drive_file.id
        assert kb.created_by == member.id
        assert kb.visibility == "team"
        assert "微纳米气泡动力学" in kb.content
        assert kb.file_path == drive_file.file_path  # 复用 MinIO 对象

        # 原 drive 行保留且不变
        drive_row = (await db.execute(
            select(Knowledge).where(Knowledge.id == drive_file.id)
        )).scalar_one()
        assert drive_row.storage_mode == "drive"
        assert drive_row.deleted_at is None


@pytest.mark.asyncio
async def test_ingest_idempotent(db_factory, member, mock_analysis):
    """幂等: 同 drive file_id 第二次调用返回既有 kb 行, 不重复建"""
    from app.services.drive_to_kb_service import DriveToKBService
    from unittest.mock import patch

    async with db_factory() as db:
        drive_file = await _make_drive_file(db, member=member)

    async with db_factory() as db:
        with patch(
            "app.services.file_service.file_service.download_file",
            return_value=b"idempotent content 1234567890",
        ):
            svc = DriveToKBService(db)
            r1 = await svc.ingest_drive_file(drive_file.id)
            r2 = await svc.ingest_drive_file(drive_file.id)

        assert r1["already_ingested"] is False
        assert r2["already_ingested"] is True
        assert r1["knowledge_id"] == r2["knowledge_id"]

        from sqlalchemy import func
        from app.models.knowledge import Knowledge
        count = (await db.execute(
            select(func.count(Knowledge.id)).where(
                Knowledge.storage_mode == "kb",
                Knowledge.source_type == "drive_extracted",
            )
        )).scalar()
        assert count == 1


@pytest.mark.asyncio
async def test_ingest_parse_failure_metadata_fallback(db_factory, member, mock_analysis):
    """解析失败: 不抛错, 元数据兜底条目落库 (2026-09-05 全格式默认入库)"""
    from app.services.drive_to_kb_service import DriveToKBService
    from unittest.mock import patch

    async with db_factory() as db:
        drive_file = await _make_drive_file(
            db, member=member,
            title="corrupt.docx", file_name="corrupt.docx",
            file_path="drive/test/corrupt.docx", file_type=".docx",
        )

    async with db_factory() as db:
        with patch(
            "app.services.file_service.file_service.download_file",
            return_value=b"\x00\x01corrupted-docx",
        ):
            svc = DriveToKBService(db)
            result = await svc.ingest_drive_file(drive_file.id)
            assert result["already_ingested"] is False
            assert result["ingest_mode"] == "document"

        from app.models.knowledge import Knowledge
        row = (await db.execute(
            select(Knowledge).where(
                Knowledge.storage_mode == "kb",
                Knowledge.source_type == "drive_extracted",
            )
        )).scalar_one()
        # 元数据兜底正文: 文件名可检索
        assert "corrupt.docx" in (row.content or "")
        assert "自动归档" in (row.content or "")
        assert (row.meta or {}).get("drive_ingest_mode") == "document"


@pytest.mark.asyncio
async def test_ingest_empty_parse_metadata_fallback(db_factory, member, mock_analysis):
    """解析结果为空 (扫描件) → 元数据兜底条目, 不再 422"""
    from app.services.drive_to_kb_service import DriveToKBService
    from unittest.mock import patch

    async with db_factory() as db:
        drive_file = await _make_drive_file(db, member=member)

    async with db_factory() as db:
        with patch(
            "app.services.file_service.file_service.download_file",
            return_value=b"   \n  ",
        ):
            svc = DriveToKBService(db)
            result = await svc.ingest_drive_file(drive_file.id)
            assert result["content_length"] > 0  # 兜底正文非空

        from sqlalchemy import func
        from app.models.knowledge import Knowledge
        count = (await db.execute(
            select(func.count(Knowledge.id)).where(
                Knowledge.storage_mode == "kb",
                Knowledge.source_type == "drive_extracted",
            )
        )).scalar()
        assert count == 1


@pytest.mark.asyncio
async def test_ingest_binary_metadata_only_no_download(db_factory, member, mock_analysis):
    """二进制类型 (.exe) → 元数据兜底, 全程不触发 MinIO 下载"""
    from app.services.drive_to_kb_service import DriveToKBService
    from unittest.mock import patch

    async with db_factory() as db:
        drive_file = await _make_drive_file(
            db, member=member,
            title="tool.exe", file_name="tool.exe",
            file_type=".exe", file_path="drive/test/tool.exe",
        )

    async with db_factory() as db:
        with patch(
            "app.services.file_service.file_service.download_file"
        ) as mock_dl:
            svc = DriveToKBService(db)
            result = await svc.ingest_drive_file(drive_file.id)
            assert result["ingest_mode"] == "metadata"
            mock_dl.assert_not_called()

        from app.models.knowledge import Knowledge
        row = (await db.execute(
            select(Knowledge).where(Knowledge.storage_mode == "kb")
        )).scalar_one()
        assert "tool.exe" in (row.content or "")
        assert (row.meta or {}).get("drive_ingest_mode") == "metadata"


@pytest.mark.asyncio
async def test_ingest_image_ocr(db_factory, member, mock_analysis):
    """图片 → OCR 文本入库 (mock ocr_service)"""
    from unittest.mock import AsyncMock, patch

    from app.services.drive_to_kb_service import DriveToKBService

    async with db_factory() as db:
        drive_file = await _make_drive_file(
            db, member=member,
            title="zeta 曲线.png", file_name="zeta 曲线.png",
            file_type=".png", file_path="drive/test/zeta.png",
        )

    async with db_factory() as db:
        with patch(
            "app.services.file_service.file_service.download_file",
            return_value=b"\x89PNG-fake-bytes",
        ), patch(
            "app.services.ocr_service.ocr_service.classify_and_extract",
            new_callable=AsyncMock,
            return_value={"category": "chart", "text": "Zeta 电位 -30mV",
                          "latex": None, "table_md": None,
                          "chart_description": "zeta 随 pH 下降", "caption": None},
        ):
            svc = DriveToKBService(db)
            result = await svc.ingest_drive_file(drive_file.id)
            assert result["ingest_mode"] == "image_ocr"
            assert result["content_length"] > 0

        from app.models.knowledge import Knowledge
        row = (await db.execute(
            select(Knowledge).where(Knowledge.storage_mode == "kb")
        )).scalar_one()
        assert "Zeta 电位 -30mV" in (row.content or "")
        assert "zeta 随 pH 下降" in (row.content or "")


@pytest.mark.asyncio
async def test_ingest_audio_asr(db_factory, member, mock_analysis):
    """音频 → ASR 转写入库 (mock asr_service)"""
    from unittest.mock import AsyncMock, patch

    from app.services.drive_to_kb_service import DriveToKBService

    async with db_factory() as db:
        drive_file = await _make_drive_file(
            db, member=member,
            title="组会录音.m4a", file_name="组会录音.m4a",
            file_type=".m4a", file_path="drive/test/rec.m4a",
        )

    async with db_factory() as db:
        with patch(
            "app.services.file_service.file_service.download_file",
            return_value=b"fake-m4a-bytes",
        ), patch(
            "app.voice.asr.asr_service.transcribe",
            new_callable=AsyncMock,
            return_value={"text": "今天讨论气泡发生器频率标定"},
        ):
            svc = DriveToKBService(db)
            result = await svc.ingest_drive_file(drive_file.id)
            assert result["ingest_mode"] == "asr"

        from app.models.knowledge import Knowledge
        row = (await db.execute(
            select(Knowledge).where(Knowledge.storage_mode == "kb")
        )).scalar_one()
        assert "气泡发生器频率标定" in (row.content or "")


@pytest.mark.asyncio
async def test_ingest_zip_archive_members(db_factory, member, mock_analysis):
    """压缩包 → 内嵌文本成员提取入库"""
    import io
    import zipfile
    from unittest.mock import patch

    from app.services.drive_to_kb_service import DriveToKBService

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("notes.md", "# 实验记录\n气泡粒径 50um")
        zf.writestr("data.csv", "size,count\n50,12")
        zf.writestr("binary.bin", b"\x00\x01\x02")  # 非文本成员跳过

    async with db_factory() as db:
        drive_file = await _make_drive_file(
            db, member=member,
            title="batch.zip", file_name="batch.zip",
            file_type=".zip", file_path="drive/test/batch.zip",
        )

    async with db_factory() as db:
        with patch(
            "app.services.file_service.file_service.download_file",
            return_value=buf.getvalue(),
        ):
            svc = DriveToKBService(db)
            result = await svc.ingest_drive_file(drive_file.id)
            assert result["ingest_mode"] == "archive"

        from app.models.knowledge import Knowledge
        row = (await db.execute(
            select(Knowledge).where(Knowledge.storage_mode == "kb")
        )).scalar_one()
        assert "气泡粒径 50um" in (row.content or "")
        assert "size,count" in (row.content or "")  # 原文照录, 不做 csv 重排
        assert "notes.md" in (row.content or "")
        assert "binary.bin" not in (row.content or "")


@pytest.mark.asyncio
async def test_ingest_reingest_updates_existing_row(db_factory, member, mock_analysis):
    """版本更新 reingest=True: 原地刷新既有 kb 行 (同 id, 内容更新), 不新建"""
    from unittest.mock import patch

    from app.services.drive_to_kb_service import DriveToKBService

    async with db_factory() as db:
        drive_file = await _make_drive_file(
            db, member=member,
            title="report.txt", file_name="report.txt",
            file_path="drive/test/report.txt", file_type=".txt",
        )

    async with db_factory() as db:
        with patch(
            "app.services.file_service.file_service.download_file",
            return_value="第一版内容".encode(),
        ):
            svc = DriveToKBService(db)
            r1 = await svc.ingest_drive_file(drive_file.id)
        assert r1["already_ingested"] is False

        # 幂等: 不带 reingest 不动
        r2 = await svc.ingest_drive_file(drive_file.id)
        assert r2["already_ingested"] is True
        assert r2["knowledge_id"] == r1["knowledge_id"]

        # 版本更新: reingest=True 原地刷新
        with patch(
            "app.services.file_service.file_service.download_file",
            return_value="第二版全新内容".encode(),
        ):
            r3 = await svc.ingest_drive_file(drive_file.id, reingest=True)
        assert r3["reingested"] is True
        assert r3["knowledge_id"] == r1["knowledge_id"]

        from sqlalchemy import func
        from app.models.knowledge import Knowledge
        count = (await db.execute(
            select(func.count(Knowledge.id)).where(Knowledge.storage_mode == "kb")
        )).scalar()
        assert count == 1  # 不新建行
        row = (await db.execute(
            select(Knowledge).where(Knowledge.id == r1["knowledge_id"])
        )).scalar_one()
        assert "第二版全新内容" in (row.content or "")
        assert row.analysis_status == "pending"  # 重新进分析管线


@pytest.mark.asyncio
async def test_ingest_missing_file_404(db_factory, member, mock_analysis):
    """文件不存在 → 404"""
    from app.services.drive_to_kb_service import DriveToKBError, DriveToKBService

    async with db_factory() as db:
        svc = DriveToKBService(db)
        with pytest.raises(DriveToKBError) as exc:
            await svc.ingest_drive_file(999999)
        assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_ingest_max_length_title_ok(db_factory, member, mock_analysis):
    """边界: title/file_name 恰好 200 (kb 侧 CHECK 上限) 入库成功, 不被截断破坏"""
    from app.services.drive_to_kb_service import DriveToKBService
    from unittest.mock import patch

    # DB 层硬约束: title varchar(200) + file_name CHECK <= 200 (全表生效,
    # 含 drive 行)。drive 侧 500 上限 (DriveFileUpdate schema) 超出时 DB 直接拒绝,
    # 服务层截断仅作防御。这里验证恰好在 200 边界时正常入库。
    max_title = "长" * 200
    max_name = "n" * 196 + ".txt"  # 恰好 200

    async with db_factory() as db:
        drive_file = await _make_drive_file(
            db, member=member,
            title=max_title,
            file_name=max_name,
            file_path=f"drive/test/{max_name}",
        )

    async with db_factory() as db:
        with patch(
            "app.services.file_service.file_service.download_file",
            return_value=b"max length boundary content",
        ):
            svc = DriveToKBService(db)
            result = await svc.ingest_drive_file(drive_file.id)
        assert result["already_ingested"] is False

        from app.models.knowledge import Knowledge
        kb = (await db.execute(
            select(Knowledge).where(Knowledge.id == result["knowledge_id"])
        )).scalar_one()
        assert len(kb.title) == 200
        assert len(kb.file_name) == 200


# === 批量入库 ===


@pytest.mark.asyncio
async def test_ingest_folder_batch_and_dry_run(db_factory, member, mock_analysis):
    """文件夹批量: dry_run 只统计, 实际入库计数正确"""
    from app.services.drive_to_kb_service import DriveToKBService
    from app.models.folder import Folder
    from unittest.mock import patch

    async with db_factory() as db:
        folder = Folder(
            name=f"f_{_uuid_lib.uuid4().hex[:6]}", owner_id=member.id,
            visibility="team", path="/", depth=0,
        )
        db.add(folder)
        await db.commit()
        await db.refresh(folder)

        f1 = await _make_drive_file(
            db, member=member, title="a.txt", file_name="a.txt", folder_id=folder.id)
        f2 = await _make_drive_file(
            db, member=member, title="b.txt", file_name="b.txt",
            file_path="drive/test/b.txt", folder_id=folder.id)

    async with db_factory() as db:
        svc = DriveToKBService(db)

        # dry_run
        dry = await svc.ingest_folder(folder.id, dry_run=True)
        assert dry["dry_run"] is True
        assert dry["total"] == 2
        assert dry["ingested"] == 0

        # 实际入库 (mock MinIO 下载)
        with patch(
            "app.services.file_service.file_service.download_file",
            side_effect=[b"folder file a content", b"folder file b content"],
        ):
            batch = await svc.ingest_folder(folder.id)
        assert batch["total"] == 2
        assert batch["ingested"] == 2
        assert batch["failed"] == 0
        assert len(batch["knowledge_ids"]) == 2

        # 再跑一次 → 全部幂等命中
        with patch(
            "app.services.file_service.file_service.download_file",
            side_effect=[b"folder file a content", b"folder file b content"],
        ):
            batch2 = await svc.ingest_folder(folder.id)
        assert batch2["ingested"] == 0
        assert batch2["already_ingested"] == 2


@pytest.mark.asyncio
async def test_ingest_team_files_skips_private(db_factory, member, mock_analysis):
    """团队批量: 只处理 team/public, private 跳过"""
    from app.services.drive_to_kb_service import DriveToKBService
    from unittest.mock import patch

    async with db_factory() as db:
        pub = await _make_drive_file(db, member=member, visibility="public")
        team = await _make_drive_file(
            db, member=member, title="team.txt", file_name="team.txt",
            file_path="drive/test/team.txt", visibility="team")
        priv = await _make_drive_file(
            db, member=member, title="priv.txt", file_name="priv.txt",
            file_path="drive/test/priv.txt", visibility="private")

    async with db_factory() as db:
        svc = DriveToKBService(db)
        with patch(
            "app.services.file_service.file_service.download_file",
            side_effect=[b"public content", b"team content"],
        ):
            batch = await svc.ingest_team_files()
        assert batch["total"] == 2  # pub + team, private 不在候选
        assert batch["ingested"] == 2
        assert batch["failed"] == 0


@pytest.mark.asyncio
async def test_ingest_folder_private_forbidden(db_factory, member, mock_analysis):
    """private 文件夹批量入库不再 403 (2026-09-05 private 退役 + 全格式默认入库)"""
    from app.services.drive_to_kb_service import DriveToKBService
    from app.models.folder import Folder

    async with db_factory() as db:
        folder = Folder(
            name=f"p_{_uuid_lib.uuid4().hex[:6]}", owner_id=member.id,
            visibility="private", path="/", depth=0,
        )
        db.add(folder)
        await db.commit()
        await db.refresh(folder)

        svc = DriveToKBService(db)
        result = await svc.ingest_folder(folder.id)
        # 空文件夹: total=0, 不抛 403
        assert result["total"] == 0
        assert result["failed"] == 0


# === 可入库清单 ===


@pytest.mark.asyncio
async def test_list_ingestable(db_factory, member, mock_analysis):
    """清单: 全格式可入库 (png 也 True), 已转化条目不再出现, private 不在团队候选"""
    from app.services.drive_to_kb_service import DriveToKBService
    from unittest.mock import patch

    async with db_factory() as db:
        f_txt = await _make_drive_file(db, member=member, title="ok.txt", file_name="ok.txt")
        f_png = await _make_drive_file(
            db, member=member, title="pic.png", file_name="pic.png",
            file_path="drive/test/pic.png", file_type=".png")
        priv = await _make_drive_file(
            db, member=member, title="priv.txt", file_name="priv.txt",
            file_path="drive/test/priv.txt", visibility="private")

    async with db_factory() as db:
        svc = DriveToKBService(db)
        items = await svc.list_ingestable()
        by_id = {i["file_id"]: i for i in items}
        assert f_txt.id in by_id
        assert by_id[f_txt.id]["ingestable"] is True
        assert f_png.id in by_id
        # 2026-09-05 全格式默认入库: 图片也可入库 (OCR)
        assert by_id[f_png.id]["ingestable"] is True
        assert priv.id not in by_id  # private 不在团队候选

        # 转化后清单不再含该文件
        with patch(
            "app.services.file_service.file_service.download_file",
            return_value=b"ingest me now",
        ):
            await svc.ingest_drive_file(f_txt.id)
        items2 = await svc.list_ingestable()
        assert f_txt.id not in {i["file_id"] for i in items2}
