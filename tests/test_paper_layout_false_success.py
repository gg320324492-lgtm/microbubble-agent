"""论文 layout 管线「假成功」bug 回归测试 (2026-10-09)

背景事故（与 OCR 管线 commit 0ec63ee32 同型）
--------------------------------------------
`paper_layout_service.analyze_page_layout` 在 vision 调用失败 / PyMuPDF 未装 /
页越界 / 渲染异常时**不抛异常**，而是返回一个带 `error` 键的 dict：
    {"page_number": N, "blocks": [], "error": "..."}

但 `scan_paper_layout` 用 `isinstance(r, Exception)` 判失败 —— `r` 是 dict，
判定**永远为 False** → 全部页失败的文档仍产出非空 `page_layouts`（每页
blocks=[]）→ 通过 `scan_paper_layout_task` 的 `if not page_layouts` 守卫
→ 当"成功 layout"写入 knowledge_layouts（total_blocks=0）。

本测试锁定修复后的行为：
1. `analyze_page_layout` 失败 dict（含 error 键）→ scan_paper_layout 仍返回该页，
   但该页被 ocr_result_failed 判定为失败。
2. 全部页失败 → scan_paper_layout_task **不落库**，返回 status=error。
3. 页面本来就没内容块（正常返回、blocks 空、无 error 键）→ 仍算成功。
4. gather 意外异常（真 Exception）→ 仍判失败（原 isinstance 分支保留）。

变异测试（见文件末注释）：把 scan_paper_layout 的 `ocr_result_failed(r)` 判定
退回 `isinstance(r, Exception)`，则 *failure* 用例会红。
"""
import os

import pytest

os.environ.setdefault("SKIP_DB_SETUP", "1")

from unittest.mock import AsyncMock, MagicMock, patch

from app.services.paper_layout_service import PaperLayoutService, ocr_result_failed


# ============================================================================
# 1. 判据契约：paper_layout 失败 dict 与 ocr_service 同一份（复用 ocr_result_failed）
# ============================================================================


class TestFailureCriterion:
    def test_reuses_ocr_criterion(self):
        """paper_layout_service 必须复用 ocr_service.ocr_result_failed（避免两份判据漂移）。"""
        import app.services.paper_layout_service as pls

        from app.services.ocr_service import ocr_result_failed as orig

        assert pls.ocr_result_failed is orig

    def test_error_dict_is_failure(self):
        assert ocr_result_failed(
            {"page_number": 3, "blocks": [], "error": "pymupdf_not_installed"}
        ) == "pymupdf_not_installed"

    def test_legit_empty_page_is_not_failure(self):
        """页面本来就没内容块（无 error 键）→ 不是失败。"""
        assert ocr_result_failed({"page_number": 3, "blocks": []}) is None

    def test_page_with_blocks_is_not_failure(self):
        page = {"page_number": 1, "blocks": [{"type": "paragraph", "text": "hi"}]}
        assert ocr_result_failed(page) is None


# ============================================================================
# 2. scan_paper_layout —— 失败页被识别（不是"空 blocks 的成功"）
# ============================================================================


def _pdf_bytes():
    return b"%PDF-1.4 fake"


class TestScanPaperLayoutFailure:
    @pytest.mark.asyncio
    async def test_failed_page_dict_is_detected_as_failure(self):
        """核心回归：analyze_page_layout 返回带 error 的 dict → 该页被识别为失败。"""
        svc = PaperLayoutService()

        # mock 掉 fitz（scan_paper_layout 用它数页），并让 analyze_page_layout 返回失败 dict
        fake_doc = MagicMock()
        fake_doc.__len__ = MagicMock(return_value=2)
        fake_fitz = MagicMock()
        fake_fitz.open.return_value = fake_doc

        async def _fake_analyze(pdf_bytes, page_number):
            if page_number == 1:
                return {"page_number": 1, "blocks": [{"type": "paragraph", "text": "ok"}]}
            # 失败：dict 带 error 键（不抛异常）
            return {"page_number": 2, "blocks": [], "error": "vision_401"}

        with patch.dict("sys.modules", {"fitz": fake_fitz}), patch.object(
            svc, "analyze_page_layout", side_effect=_fake_analyze
        ):
            results = await svc.scan_paper_layout(_pdf_bytes())

        assert len(results) == 2
        by_page = {p["page_number"]: p for p in results}
        # page 1 成功（无 error）
        assert ocr_result_failed(by_page[1]) is None
        # page 2 失败（error 键被识别）
        assert ocr_result_failed(by_page[2]) == "vision_401"

    @pytest.mark.asyncio
    async def test_all_pages_failed_produces_all_failure_dicts(self):
        """全部页失败 → 返回 list 里每页都是失败 dict（不是"空 blocks 的成功"）。"""
        svc = PaperLayoutService()

        fake_doc = MagicMock()
        fake_doc.__len__ = MagicMock(return_value=3)
        fake_fitz = MagicMock()
        fake_fitz.open.return_value = fake_doc

        async def _fake_analyze(pdf_bytes, page_number):
            return {"page_number": page_number, "blocks": [], "error": "boom"}

        with patch.dict("sys.modules", {"fitz": fake_fitz}), patch.object(
            svc, "analyze_page_layout", side_effect=_fake_analyze
        ):
            results = await svc.scan_paper_layout(_pdf_bytes())

        assert len(results) == 3
        assert all(ocr_result_failed(p) == "boom" for p in results)

    @pytest.mark.asyncio
    async def test_gather_exception_still_marked_failure(self):
        """analyze_page_layout 真抛异常（逃过内部兜底）→ 仍判失败（原 isinstance 分支保留）。"""
        svc = PaperLayoutService()

        fake_doc = MagicMock()
        fake_doc.__len__ = MagicMock(return_value=1)
        fake_fitz = MagicMock()
        fake_fitz.open.return_value = fake_doc

        with patch.dict("sys.modules", {"fitz": fake_fitz}), patch.object(
            svc, "analyze_page_layout", side_effect=RuntimeError("unexpected")
        ):
            results = await svc.scan_paper_layout(_pdf_bytes())

        assert len(results) == 1
        assert ocr_result_failed(results[0]) is not None

    @pytest.mark.asyncio
    async def test_legit_empty_page_not_marked_failure(self):
        """反向断言：页面本来就没内容块（正常返回、blocks 空、无 error）→ 不算失败。"""
        svc = PaperLayoutService()

        fake_doc = MagicMock()
        fake_doc.__len__ = MagicMock(return_value=2)
        fake_fitz = MagicMock()
        fake_fitz.open.return_value = fake_doc

        async def _fake_analyze(pdf_bytes, page_number):
            # 空白页（无 error 键）——合法
            return {"page_number": page_number, "blocks": []}

        with patch.dict("sys.modules", {"fitz": fake_fitz}), patch.object(
            svc, "analyze_page_layout", side_effect=_fake_analyze
        ):
            results = await svc.scan_paper_layout(_pdf_bytes())

        assert len(results) == 2
        assert all(ocr_result_failed(p) is None for p in results)


# ============================================================================
# 3. scan_paper_layout_task —— 全部页失败时不落库
# ============================================================================


def _fake_session_ctx(knowledge_row):
    fake_db = MagicMock()
    fake_db.add = MagicMock()
    fake_db.commit = AsyncMock()

    def _execute(stmt):
        result = MagicMock()
        # select(Knowledge) 与 select(KnowledgeLayout) 都返回同一行替身；
        # KnowledgeLayout 查询期望 None（无既有行）——用 __iter__ 无关，见下方
        # scalar_one_or_none 统一返回 knowledge_row（KnowledgeLayout 分支会
        # 拿到 truthy → 走 update 分支，同样不调用 db.add；因此断言用 commit）。
        result.scalar_one_or_none.return_value = knowledge_row
        return AsyncMock(return_value=result)()

    fake_db.execute = _execute

    ctx = MagicMock()
    ctx.__aenter__ = AsyncMock(return_value=fake_db)
    ctx.__aexit__ = AsyncMock(return_value=False)
    return ctx, fake_db


def _patch_task_deps(ctx):
    """patch scan_paper_layout_task 的依赖：engine 工厂 + file_service（均为 _run 内局部 import）。"""
    from app.services import paper_layout_service as pls

    fake_engine = MagicMock(dispose=AsyncMock())
    fake_file_service = MagicMock(
        download_file=AsyncMock(return_value=_pdf_bytes())
    )
    return [
        patch.object(pls, "create_celery_engine_and_session",
                     return_value=(fake_engine, lambda: ctx)),
        patch("app.services.file_service.file_service", fake_file_service),
    ], fake_engine, fake_file_service


class TestTaskDoesNotPersistAllFailed:
    def test_all_pages_failed_does_not_write_layout(self):
        """全部页失败 → 不落库（commit 不被调用），返回 status=error/all_pages_failed。"""
        from app.services import paper_layout_service as pls

        knowledge = MagicMock()
        knowledge.id = 10
        knowledge.file_path = "knowledge/10/a.pdf"
        knowledge.file_type = "pdf"
        knowledge.analysis_status = "analyzing"

        ctx, fake_db = _fake_session_ctx(knowledge)

        async def _all_failed(pdf_bytes, **kwargs):
            return [
                {"page_number": 1, "blocks": [], "error": "vision_401"},
                {"page_number": 2, "blocks": [], "error": "vision_401"},
            ]

        patches, _, _ = _patch_task_deps(ctx)
        with patches[0], patches[1], patch.object(
            pls.paper_layout_service, "scan_paper_layout", side_effect=_all_failed
        ):
            result = pls.scan_paper_layout_task.run(knowledge_id=10)

        assert result["status"] == "error"
        assert result["reason"] == "all_pages_failed"
        assert result["failed_pages"] == [1, 2]
        fake_db.commit.assert_not_called()

    def test_partial_failure_still_persists(self):
        """部分页成功 → 仍落库（不误伤正常 layout），返回 status=ok 且带 failed_pages。"""
        from app.services import paper_layout_service as pls

        knowledge = MagicMock()
        knowledge.id = 10
        knowledge.file_path = "knowledge/10/a.pdf"
        knowledge.file_type = "pdf"
        knowledge.analysis_status = "analyzing"

        ctx, fake_db = _fake_session_ctx(knowledge)

        async def _partial(pdf_bytes, **kwargs):
            return [
                {"page_number": 1, "blocks": [{"type": "paragraph", "text": "ok"}]},
                {"page_number": 2, "blocks": [], "error": "vision_401"},
            ]

        patches, _, _ = _patch_task_deps(ctx)
        with patches[0], patches[1], patch.object(
            pls.paper_layout_service, "scan_paper_layout", side_effect=_partial
        ):
            result = pls.scan_paper_layout_task.run(knowledge_id=10)

        assert result["status"] == "ok"
        assert result["failed_pages"] == [2]
        fake_db.commit.assert_awaited()


# ============================================================================
# 变异测试说明（不自动执行；人工操作 + 实测结果）
# ============================================================================
# 实测（2026-10-09，容器内原位变异 + 回跑）:
#
# 变异 A：删掉 scan_paper_layout_task 里的 failed_pages 全失败守卫
#   （即退回修复前，只剩 `if not page_layouts` 守卫）→
#   TestTaskDoesNotPersistAllFailed 的 2 个用例变红（全部页失败仍落库 +
#   failed_pages 字段缺失）。**该守卫是本次修复的承载点**：scan_paper_layout
#   返回的 list 在修复前后都是"每页 dict 自带 error 键"，`if not page_layouts`
#   拦不住（list 非空）→ 老代码把"全空 blocks 的假 layout"写入 knowledge_layouts。
#
# 变异 B：把 scan_paper_layout 循环里的 `err = ocr_result_failed(r)` 退回
#   `isinstance(r, Exception)` → 6 个 scan/task 用例仍绿。原因：返回的 list
#   内容在修复前后相同（dict 自带 error 键），该循环改动是**可观测性/归一**
#   层面（failed_pages 统计 + 非 dict 归一 + 全失败 ERROR 日志），不是内容
#   语义的承载点。之所以仍保留该改动：①统一复用 ocr_result_failed 判据，
#   避免两份判据漂移；②提供 failed_pages 供 task 层守卫消费。
#   → 故 if 有人把该循环退回 isinstance，scan 层测试不会报警，属已知覆盖边界。
