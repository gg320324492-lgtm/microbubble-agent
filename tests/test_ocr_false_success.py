"""OCR 管线「假成功」bug 回归测试 (2026-10-09)

背景事故
--------
`ocr_service.classify_and_extract` / `extract_figure_structured` 在后端调用失败时
**不抛异常**，而是返回一个带 `error` 键的 dict。下游
`multimodal_extraction_service._process_one` 用 `isinstance(result, Exception)` 判失败
→ 拿到的是 dict，判定**永远为 False** → 失败的图被当作 `ok=True` 走成功分支，
落库 `ocr_status='done'` 且 `ocr_text` 为空 —— **抹掉失败信号**。
实测：20 张图因 MIMO 401 失败全被标 done；生产库现存量
`ocr_status='done' AND ocr_text 空` 共 372 行。

本测试锁定修复后的行为：
- OCR 调用失败（401 / timeout / 网络错）→ 图标 failed，错误保留，ocr_text 空 ≠ 成功
- 图里真没文字（后端正常返回、text 为空）→ 标 **done_no_text**（合法空，不得判 failed）
- 结构化调用失败 → 不把默认值当真实结果写库

2026-10-09（agent31）续修：`done` 原先同时表示「成功且有字」和「成功但没字」
两种**语义相反**的状态（存量 3317 行），排查时无法区分。现拆为
`done`（有字）/ `done_no_text`（跑完但没字），迁移 `143_ocr_status_done_no_text`。
不变式：**`done` ⟺ 本次调用抽到了东西**。

变异测试（见文件末注释）：把 `_process_one` 的 `ocr_result_failed` 判定退回
`isinstance(x, Exception)`，下列 *failure* 用例会红。
"""
import os

import pytest

os.environ.setdefault("SKIP_DB_SETUP", "1")

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch


# ============================================================================
# 1. 判据单元：ocr_result_failed —— 唯一失败判据 = presence of `error` 键
# ============================================================================


class TestOcrResultFailed:
    def test_failure_dict_returns_error_string(self):
        from app.services.ocr_service import ocr_result_failed

        failed = {
            "category": "figure",
            "text": "",
            "latex": None,
            "table_md": None,
            "chart_description": None,
            "caption": None,
            "error": "LLM-Vision OCR 失败: 401 Unauthorized",
        }
        err = ocr_result_failed(failed)
        assert err == "LLM-Vision OCR 失败: 401 Unauthorized"

    def test_success_with_text_returns_none(self):
        from app.services.ocr_service import ocr_result_failed

        ok = {"category": "chart", "text": "Zeta 电位 -30mV"}
        assert ocr_result_failed(ok) is None

    def test_success_with_empty_text_returns_none(self):
        """关键：图里没文字（无 error 键，text 空）不得判失败。"""
        from app.services.ocr_service import ocr_result_failed

        ok_empty = {
            "category": "figure",
            "text": "",
            "latex": None,
            "table_md": None,
            "chart_description": None,
            "caption": None,
        }
        assert ocr_result_failed(ok_empty) is None

    def test_parse_fallback_marker_is_not_failure(self):
        """JSON 解析失败 fallback 不算 OCR 失败（LLM 有响应，只是非 JSON）。"""
        from app.services.ocr_service import ocr_result_failed

        fallback = {"category": "figure", "text": "some raw text", "_parse_failed": True}
        assert ocr_result_failed(fallback) is None

    def test_empty_or_blank_error_not_counted(self):
        from app.services.ocr_service import ocr_result_failed

        assert ocr_result_failed({"text": "", "error": ""}) is None
        assert ocr_result_failed({"text": "", "error": "   "}) is None

    def test_non_dict_returns_none(self):
        from app.services.ocr_service import ocr_result_failed

        assert ocr_result_failed(None) is None
        assert ocr_result_failed("oops") is None
        assert ocr_result_failed({"ok": True}) is None


# ============================================================================
# 2. _ocr_images_concurrent._process_one —— 失败 dict 必须判 ok=False
# ============================================================================


def _img_record(image_id: int = 1, object_name: str = "knowledge/1/images/a.png"):
    return SimpleNamespace(
        id=image_id,
        image_object_name=object_name,
        mime_type="image/png",
        # _save_extractions 的 meta_by_id 会读这两个属性（来自 _upload_images 的行快照）
        page_number=1,
        position_data=None,
    )


def _failed_classify(msg: str = "LLM-Vision OCR 失败: 401"):
    return {
        "category": "figure",
        "text": "",
        "latex": None,
        "table_md": None,
        "chart_description": None,
        "caption": None,
        "error": msg,
    }


def _failed_structured(msg: str = "LLM-Vision OCR 失败: 401"):
    return {
        "figureNo": None,
        "figureType": "figure",
        "semanticTitle": None,
        "visualSummary": None,
        "sectionHint": None,
        "isCoreFigure": True,
        "isPublisherImage": False,
        "isSupportingFigure": False,
        "confidence": 0.0,
        "error": msg,
    }


class TestProcessOneFailureDetection:
    @pytest.mark.asyncio
    async def test_classify_failure_dict_marks_ok_false(self):
        """核心回归：classify 返回带 error 的 dict → ok=False（修复前 = True 假成功）。"""
        from app.services.multimodal_extraction_service import (
            multimodal_extraction_service as svc,
        )

        with patch(
            "app.services.multimodal_extraction_service.file_service.download_file",
            AsyncMock(return_value=b"\x89PNG-fake"),
        ), patch.object(
            svc.__class__,
            "_save_extractions",  # 不触 DB
            AsyncMock(return_value={}),
        ), patch(
            "app.services.ocr_service.ocr_service.classify_and_extract",
            AsyncMock(return_value=_failed_classify("LLM-Vision OCR 失败: 401 Unauthorized")),
        ), patch(
            "app.services.ocr_service.ocr_service.extract_figure_structured",
            AsyncMock(return_value=_failed_structured()),
        ):
            results = await svc._ocr_images_concurrent([_img_record(1)])

        assert len(results) == 1
        assert results[0]["ok"] is False
        assert "401" in results[0]["error"]

    @pytest.mark.asyncio
    async def test_classify_raises_exception_marks_ok_false(self):
        """抛异常路径仍是 ok=False（原 isinstance 分支保留）。"""
        from app.services.multimodal_extraction_service import (
            multimodal_extraction_service as svc,
        )

        with patch(
            "app.services.multimodal_extraction_service.file_service.download_file",
            AsyncMock(return_value=b"\x89PNG-fake"),
        ), patch(
            "app.services.ocr_service.ocr_service.classify_and_extract",
            AsyncMock(side_effect=RuntimeError("network down")),
        ), patch(
            "app.services.ocr_service.ocr_service.extract_figure_structured",
            AsyncMock(return_value=_failed_structured()),
        ):
            results = await svc._ocr_images_concurrent([_img_record(1)])

        assert results[0]["ok"] is False
        assert "network down" in results[0]["error"]

    @pytest.mark.asyncio
    async def test_success_with_empty_text_still_ok(self):
        """关键反向断言：图里没文字（后端正常返回、text 空）→ ok=True（合法空）。"""
        from app.services.multimodal_extraction_service import (
            multimodal_extraction_service as svc,
        )

        with patch(
            "app.services.multimodal_extraction_service.file_service.download_file",
            AsyncMock(return_value=b"\x89PNG-fake"),
        ), patch(
            "app.services.ocr_service.ocr_service.classify_and_extract",
            AsyncMock(return_value={
                "category": "figure",
                "text": "",
                "latex": None,
                "table_md": None,
                "chart_description": None,
                "caption": None,
            }),
        ), patch(
            "app.services.ocr_service.ocr_service.extract_figure_structured",
            AsyncMock(return_value={
                "figureNo": None, "figureType": "logo", "semanticTitle": None,
                "visualSummary": "Elsevier logo", "sectionHint": None,
                "isCoreFigure": False, "isPublisherImage": True,
                "isSupportingFigure": False, "confidence": 0.99,
            }),
        ):
            results = await svc._ocr_images_concurrent([_img_record(1)])

        assert results[0]["ok"] is True
        assert results[0]["parsed"]["text"] == ""

    @pytest.mark.asyncio
    async def test_structured_failure_is_normalized_to_none(self):
        """结构化调用失败 → structured 归一为 None（不写默认值假信号）。"""
        from app.services.multimodal_extraction_service import (
            multimodal_extraction_service as svc,
        )

        with patch(
            "app.services.multimodal_extraction_service.file_service.download_file",
            AsyncMock(return_value=b"\x89PNG-fake"),
        ), patch(
            "app.services.ocr_service.ocr_service.classify_and_extract",
            AsyncMock(return_value={
                "category": "figure", "text": "real text", "latex": None,
                "table_md": None, "chart_description": None, "caption": None,
            }),
        ), patch(
            "app.services.ocr_service.ocr_service.extract_figure_structured",
            AsyncMock(return_value=_failed_structured("401")),
        ):
            results = await svc._ocr_images_concurrent([_img_record(1)])

        assert results[0]["ok"] is True
        assert results[0]["structured"] is None  # 失败 dict 被归一（不再当真实结果）


# ============================================================================
# 3. _save_extractions —— 落库断言：failed 图标 failed，合法空标 done
# ============================================================================


def _fake_session_ctx(images_by_id):
    """构造 async_session() 的上下文管理器替身，execute 时返回 re-fetch 的行。"""
    fake_db = MagicMock()
    fake_db.add = MagicMock()
    fake_db.commit = AsyncMock()

    def _execute(stmt):
        result = MagicMock()
        # re-fetch KnowledgeImage：返回所有已知行（测试里只有 1 行）
        result.scalars.return_value.all.return_value = list(images_by_id.values())
        return AsyncMock(return_value=result)()

    fake_db.execute = _execute

    ctx = MagicMock()
    ctx.__aenter__ = AsyncMock(return_value=fake_db)
    ctx.__aexit__ = AsyncMock(return_value=False)
    return ctx, fake_db


def _client_image_row(image_id: int = 1, knowledge_id: int = 10):
    return SimpleNamespace(
        id=image_id,
        knowledge_id=knowledge_id,
        ocr_status="pending",
        ocr_text=None,
        ocr_error=None,
        ocr_model=None,
        ocr_at=None,
        figure_type=None,
        figure_no=None,
        is_core_figure=None,
        is_publisher_image=None,
        is_supporting_figure=None,
        section_hint=None,
        visual_summary=None,
        vision_confidence=None,
        vision_model_used=None,
        vision_analyzed_at=None,
        page_number=1,
        position_data=None,
    )


class TestSaveExtractionsStatus:
    @pytest.mark.asyncio
    async def test_failed_result_writes_failed_status_and_error(self):
        from app.services.multimodal_extraction_service import (
            multimodal_extraction_service as svc,
        )

        img = _client_image_row(1)
        img_snapshot = _img_record(1)
        ctx, _ = _fake_session_ctx({1: img})

        with patch(
            "app.services.multimodal_extraction_service.async_session",
            return_value=ctx,
        ):
            await svc._save_extractions(
                knowledge_id=10,
                image_records=[img_snapshot],
                ocr_results=[{
                    "image_id": 1,
                    "ok": False,
                    "error": "classify: LLM-Vision OCR 失败: 401 Unauthorized",
                    "structured": None,
                }],
            )

        assert img.ocr_status == "failed"
        assert "401" in (img.ocr_error or "")
        assert img.ocr_text is None  # 空文本不再是成功的标志

    @pytest.mark.asyncio
    async def test_legit_empty_text_writes_done_no_text(self):
        """合法空文本（图无文字）→ done_no_text，不得被判 failed。

        2026-10-09（agent31）改：原先这里断言 ``done``，那正是「状态字段撒谎」
        的根源 —— `done` 同时表示「成功且有字」和「成功但没字」。现在拆开：
        有字 → done，没字 → done_no_text，两者都不算 failed。
        """
        from app.services.multimodal_extraction_service import (
            multimodal_extraction_service as svc,
        )

        img = _client_image_row(1)
        img_snapshot = _img_record(1)
        ctx, _ = _fake_session_ctx({1: img})

        with patch(
            "app.services.multimodal_extraction_service.async_session",
            return_value=ctx,
        ):
            await svc._save_extractions(
                knowledge_id=10,
                image_records=[img_snapshot],
                ocr_results=[{
                    "image_id": 1,
                    "ok": True,
                    "parsed": {
                        "category": "figure", "text": "", "latex": None,
                        "table_md": None, "chart_description": None, "caption": None,
                    },
                    "structured": None,
                }],
            )

        assert img.ocr_status == "done_no_text"
        assert img.ocr_text is None  # 无文字 → 空；状态明确是「跑完但没字」

    @pytest.mark.asyncio
    async def test_empty_text_on_rerun_uses_this_run_not_stale_attr(self):
        """重跑老行且本次无产出时，状态按**本轮**判定，不被上一轮的残留文本带成 done。

        `done` 必须严格等价于「本次调用抽到了东西」，否则一条空产出能把
        上一轮的文字重新盖章成 done。
        """
        from app.services.multimodal_extraction_service import (
            multimodal_extraction_service as svc,
        )

        img = _client_image_row(1)
        img.ocr_status = "done"
        img.ocr_text = "上一轮残留的文字"   # 上一轮抽到过
        img_snapshot = _img_record(1)
        ctx, _ = _fake_session_ctx({1: img})

        with patch(
            "app.services.multimodal_extraction_service.async_session",
            return_value=ctx,
        ):
            await svc._save_extractions(
                knowledge_id=10,
                image_records=[img_snapshot],
                ocr_results=[{
                    "image_id": 1,
                    "ok": True,
                    "parsed": {
                        "category": "figure", "text": "", "latex": None,
                        "table_md": None, "chart_description": None, "caption": None,
                    },
                    "structured": None,
                }],
            )

        assert img.ocr_status == "done_no_text"  # 本轮没产出 → 不能是 done
        assert img.ocr_text == "上一轮残留的文字"  # 残留文本不被覆盖，也不重新盖章

    @pytest.mark.asyncio
    async def test_parse_failed_fallback_with_raw_text_writes_done(self):
        """JSON 解析失败 fallback（有原始 text）仍算成功 → done。"""
        from app.services.multimodal_extraction_service import (
            multimodal_extraction_service as svc,
        )

        img = _client_image_row(1)
        img_snapshot = _img_record(1)
        ctx, _ = _fake_session_ctx({1: img})

        with patch(
            "app.services.multimodal_extraction_service.async_session",
            return_value=ctx,
        ):
            await svc._save_extractions(
                knowledge_id=10,
                image_records=[img_snapshot],
                ocr_results=[{
                    "image_id": 1,
                    "ok": True,
                    "parsed": {
                        "category": "figure", "text": "raw llm text", "latex": None,
                        "table_md": None, "chart_description": None, "caption": None,
                        "_parse_failed": True,
                    },
                    "structured": None,
                }],
            )

        assert img.ocr_status == "done"
        assert img.ocr_text == "raw llm text"


# ============================================================================
# 变异测试说明（不自动执行；人工操作）
# ============================================================================
# 退回修复：把 multimodal_extraction_service._process_one 里
#   classify_err = ocr_result_failed(classify_result)
#   if classify_err: return {"ok": False, ...}
# 删掉（恢复成只看 isinstance(classify_result, Exception)），
# 则 TestProcessOneFailureDetection::test_classify_failure_dict_marks_ok_false
# 与 TestSaveExtractionsStatus::test_failed_result_writes_failed_status_and_error
# 会红（失败被当成功）。已人工验证见报告。
